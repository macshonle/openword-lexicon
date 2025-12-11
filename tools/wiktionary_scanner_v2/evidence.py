"""
Evidence extraction for v2 scanner.

This module extracts neutral "Evidence" objects from Wiktionary pages.
Evidence represents raw signals before code mapping - it has no knowledge
of POS codes, flags, or tags. The rule engine (rules.py) will convert
Evidence objects to Entry objects using BindingConfig lookups.

Architecture:
    XML dump -> stream_pages() -> extract_evidence() -> Evidence objects
                                                            |
                                                            v
                                                      rules.py (Entry)
"""

import bz2
import codecs
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional

from .wikitext_parser import (
    Template,
    WikitextParser,
    extract_labels as parser_extract_labels,
    extract_head_pos,
    find_templates,
)


@dataclass
class Evidence:
    """
    Raw signals extracted from a single sense, before code mapping.

    This is a neutral representation that captures all Wiktionary signals
    without mapping them to codes. The rule engine will use BindingConfig
    to convert these signals to codes.
    """

    # Page identity
    title: str  # Page title (the word)
    wc: int  # Word count (spaces + 1)

    # POS signals
    pos_header: str  # Raw POS header text (e.g., "Noun", "Proper noun")
    head_templates: list[Template] = field(default_factory=list)  # {{head}}, {{en-noun}}, etc.

    # Categories (full category strings without "Category:" prefix)
    categories: list[str] = field(default_factory=list)
    categories_lower: list[str] = field(default_factory=list)  # Pre-lowercased

    # Labels from {{lb|en|...}} templates
    labels: list[str] = field(default_factory=list)

    # Etymology section signals
    etymology_text: str = ""  # Raw etymology section text
    etymology_templates: list[Template] = field(default_factory=list)

    # Definition
    definition_text: str = ""  # The definition line text
    definition_level: int = 1  # 1 for #, 2 for ##, 3 for ###
    definition_type: str = "primary"  # primary, secondary, tertiary, quote, synonym, usage

    # Syllable signals (multiple sources for priority resolution)
    hyphenation_parts: list[str] = field(default_factory=list)  # From {{hyphenation|en|...}}
    rhymes_syllable_count: Optional[int] = None  # From {{rhymes|en|...|s=N}}
    syllable_category_count: Optional[int] = None  # From Category:English N-syllable words
    ipa_transcription: Optional[str] = None  # From {{IPA|en|...}}

    # Inflection signals
    inflection_template: Optional[Template] = None  # {{plural of}}, {{past tense of}}, etc.

    # Alternative form signals
    altform_template: Optional[Template] = None  # {{alt form}}, {{alternative spelling of}}, etc.

    # Phrase type signals (from headers before POS normalization)
    phrase_type_header: Optional[str] = None  # "idiom", "proverb", "prepositional phrase"

    # Spelling region signals
    spelling_labels: list[str] = field(default_factory=list)  # From {{tlb|en|...}}

    # Senseid signals
    senseid: Optional[str] = None  # From {{senseid|en|...}} - Wikidata QID or semantic identifier


# =============================================================================
# BZ2 streaming
# =============================================================================


class BZ2StreamReader:
    """Streaming BZ2 decompressor with progress feedback."""

    def __init__(self, filepath: Path, chunk_size: int = 256 * 1024):
        self.filepath = filepath
        self.chunk_size = chunk_size
        self.file = open(filepath, "rb")
        self.decompressor = bz2.BZ2Decompressor()
        self.buffer = b""
        self.total_compressed = 0
        self.total_decompressed = 0
        self.start_time = time.time()

    def read(self, size: int = -1) -> bytes:
        """Read decompressed data."""
        if size == -1:
            while not self.decompressor.eof:
                self._decompress_chunk()
            result = self.buffer
            self.buffer = b""
            return result

        while len(self.buffer) < size and not self.decompressor.eof:
            self._decompress_chunk()

        result = self.buffer[:size]
        self.buffer = self.buffer[size:]
        return result

    def _decompress_chunk(self):
        """Decompress one chunk."""
        if self.decompressor.eof:
            return

        compressed = self.file.read(self.chunk_size)
        if not compressed:
            return

        self.total_compressed += len(compressed)
        decompressed = self.decompressor.decompress(compressed)
        self.buffer += decompressed
        self.total_decompressed += len(decompressed)

    def close(self):
        self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


# =============================================================================
# XML streaming
# =============================================================================

# Simple extraction patterns (no full XML parsing)
TITLE_PATTERN = re.compile(r"<title>([^<]+)</title>")
NS_PATTERN = re.compile(r"<ns>(\d+)</ns>")
TEXT_PATTERN = re.compile(r"<text[^>]*>(.+?)</text>", re.DOTALL)
REDIRECT_PATTERN = re.compile(r'<redirect\s+title="[^"]+"')


def scan_pages(file_obj, chunk_size: int = 1024 * 1024) -> Iterator[str]:
    """
    Scan for <page> boundaries and yield complete page XML.

    This is much faster than ET.iterparse() because:
    - No XML DOM building
    - No namespace handling
    - No validation
    - Simple string scanning

    Uses an incremental UTF-8 decoder to properly handle multi-byte sequences
    that may be split across chunk boundaries.
    """
    buffer = ""
    page_start_marker = "<page>"
    page_end_marker = "</page>"

    # Incremental decoder handles split multi-byte UTF-8 sequences correctly
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

    while True:
        chunk = file_obj.read(chunk_size)
        if not chunk:
            # Flush any remaining bytes in the decoder
            buffer += decoder.decode(b"", final=True)
            break

        buffer += decoder.decode(chunk)

        while True:
            start = buffer.find(page_start_marker)
            if start == -1:
                buffer = buffer[-len(page_start_marker) :]
                break

            end = buffer.find(page_end_marker, start)
            if end == -1:
                buffer = buffer[start:]
                break

            end += len(page_end_marker)
            page_xml = buffer[start:end]
            buffer = buffer[end:]

            yield page_xml


# =============================================================================
# Wikitext extraction patterns (imported from enwikt_patterns)
#
# English Wiktionary-specific patterns are isolated in enwikt_patterns.py.
# Some patterns are generated from schema/bindings/en-wikt.*.yaml config files.
# =============================================================================

from .enwikt_patterns import (
    # Section structure
    ENGLISH_SECTION,
    LANGUAGE_SECTION,
    POS_HEADER,
    DEFINITION_LINE,
    ETYMOLOGY_SECTION,
    ETYMOLOGY_HEADER,
    # Categories and labels
    CATEGORY,
    TLB_TEMPLATE,
    # Syllable extraction
    HYPHENATION_TEMPLATE,
    RHYMES_SYLLABLE,
    SYLLABLE_CATEGORY,
    IPA_TEMPLATE,
    # Special page handling
    SPECIAL_PAGE_PREFIXES,
    DICT_ONLY,
    # Template name lists (loaded from YAML config)
    MORPHOLOGY_TEMPLATE_NAMES,
    INFLECTION_TEMPLATE_NAMES,
    ALTFORM_TEMPLATE_NAMES,
)

# Note: Additional patterns available in enwikt_patterns for other modules:
# - CONTEXT_LABEL, HEAD_TEMPLATE, EN_POS_TEMPLATE (head/label parsing)
# - SUFFIX_TEMPLATE, PREFIX_TEMPLATE, etc. (morphology fast detection)
# - INFLECTION_PATTERNS (generated from en-wikt.flags.yaml)
# - ABBREVIATION_PATTERN (generated from en-wikt.flags.yaml)


# =============================================================================
# Extraction functions
# =============================================================================


def extract_english_section(text: str) -> Optional[str]:
    """
    Extract ONLY the ==English== section from a Wiktionary page.

    Returns the English section text, or None if no English section found.
    """
    english_match = ENGLISH_SECTION.search(text)
    if not english_match:
        return None

    english_start = english_match.end()

    next_section = None
    for match in LANGUAGE_SECTION.finditer(text, english_start):
        lang = match.group(1).strip()
        if lang.lower() != "english":
            next_section = match.start()
            break

    if next_section:
        return text[english_start:next_section]
    else:
        return text[english_start:]


def extract_categories(text: str) -> list[str]:
    """Extract English category suffixes from text."""
    categories = []
    for match in CATEGORY.finditer(text):
        categories.append(match.group(1))
    return categories


def extract_labels(text: str) -> list[str]:
    """Extract label tokens from {{lb|en|...}} templates using parser."""
    return parser_extract_labels(text)


def extract_spelling_labels(text: str) -> list[str]:
    """Extract spelling-related labels from {{tlb|en|...}} templates."""
    labels = []
    for match in TLB_TEMPLATE.finditer(text):
        for label in match.group(1).split("|"):
            label = label.strip().lower()
            if label:
                labels.append(label)
    return labels


def extract_hyphenation(text: str) -> list[str]:
    """Extract hyphenation parts from {{hyphenation|en|...}}."""
    match = HYPHENATION_TEMPLATE.search(text)
    if not match:
        return []

    content = match.group(1)
    # Handle alternatives (||) - use first alternative
    alternatives = content.split("||")
    first_alt = alternatives[0] if alternatives else content

    parts = []
    for part in first_alt.split("|"):
        part = part.strip()
        if part and "=" not in part:  # Skip parameters like lang=
            parts.append(part)

    return parts


def extract_rhymes_syllable_count(text: str) -> Optional[int]:
    """Extract syllable count from {{rhymes|en|...|s=N}}."""
    match = RHYMES_SYLLABLE.search(text)
    if match:
        return int(match.group(1))
    return None


def extract_syllable_category_count(text: str) -> Optional[int]:
    """Extract syllable count from Category:English N-syllable words."""
    match = SYLLABLE_CATEGORY.search(text)
    if match:
        return int(match.group(1))
    return None


def extract_ipa_transcription(text: str) -> Optional[str]:
    """Extract first IPA transcription from {{IPA|en|...}}."""
    match = IPA_TEMPLATE.search(text)
    if match:
        return match.group(1)
    return None


def extract_etymology_text(text: str) -> str:
    """Extract etymology section text.

    Handles two cases:
    1. Text contains ===Etymology=== header: extracts content after header up to next ===
    2. Text is already etymology block content (header consumed by find_etymology_blocks):
       extracts content up to first === header
    """
    # First, try to find etymology section with header
    match = ETYMOLOGY_SECTION.search(text)
    if match:
        return match.group(1).strip()

    # If no header found, this might be a block where we're already inside
    # the etymology content (header was consumed by find_etymology_blocks).
    # Extract up to first === header.
    next_header_match = re.search(r"\n===", text)
    if next_header_match:
        return text[: next_header_match.start()].strip()

    # No headers found, return all text (might be etymology-only content)
    return text.strip()


def extract_etymology_templates(etymology_text: str) -> list[Template]:
    """Extract morphology-related templates from etymology section using parser.

    Template names are loaded from schema/bindings/en-wikt.patterns.yaml.
    """
    return find_templates(etymology_text, *MORPHOLOGY_TEMPLATE_NAMES)


def extract_inflection_template(text: str) -> Optional[Template]:
    """Extract inflection template if present using parser.

    Template names are loaded from schema/bindings/en-wikt.flags.yaml (INFL.templates).
    Note: "form of" has special handling - param structure is {{form of|lang|description|lemma}}.
    """
    templates = find_templates(text, *INFLECTION_TEMPLATE_NAMES)
    if templates:
        # Return first matching template
        # Normalize name (remove "en-" prefix if present)
        t = templates[0]
        name = t.name.lower()
        if name.startswith("en-"):
            name = name[3:]
        # Filter to get positional params
        positional = [p for p in t.params if "=" not in p and p.strip()]
        # Skip language code if present
        if positional and positional[0].lower() == "en":
            positional = positional[1:]

        # Special handling for "form of" - lemma is param 3, not param 2
        # {{form of|en|Form|a#Article|a}} -> lemma is "a#Article" (index 1 after lang)
        if name == "form of" and len(positional) >= 2:
            lemma = positional[1]  # Skip description, get actual lemma
            # Strip anchor (e.g., "a#Article" -> "a")
            if "#" in lemma:
                lemma = lemma.split("#")[0]
            return Template(name=name, params=[lemma])
        elif positional:
            return Template(name=name, params=[positional[0]])
    return None


# Senseid pattern: {{senseid|en|value}}
SENSEID_PATTERN = re.compile(r"\{\{senseid\|en\|([^}|]+)", re.IGNORECASE)


def extract_senseid(text: str) -> Optional[str]:
    """Extract senseid value from {{senseid|en|...}} template in definition text.

    The senseid value can be:
    - A Wikidata QID (e.g., "Q617085")
    - A semantic identifier (e.g., "grammar", "music", "transitive")

    Returns the first senseid found, or None if no senseid template present.
    """
    match = SENSEID_PATTERN.search(text)
    if match:
        value = match.group(1).strip()
        # Clean up any trailing whitespace or wiki markup
        if value:
            return value
    return None


def extract_altform_template(text: str) -> Optional[Template]:
    """Extract alternative form template if present using parser.

    Detects templates like:
    - {{alt form|en|target}}
    - {{alt sp|en|target}}
    - {{alternative form of|en|target}}
    - {{alternative spelling of|en|target}}
    - {{standard spelling of|en|from=Commonwealth|target}}

    Template names are loaded from schema/bindings/en-wikt.flags.yaml (ALTH.templates).

    Returns Template with target word in params[0], and any from= values
    in params[1:] for spelling region detection. Returns None if not found.
    """
    templates = find_templates(text, *ALTFORM_TEMPLATE_NAMES)
    if templates:
        t = templates[0]
        name = t.name.lower()
        # Filter to get positional params (excluding named params with =)
        positional = [p for p in t.params if "=" not in p and p.strip()]
        # Extract from= params for spelling region (e.g., from=Commonwealth)
        from_values = []
        for p in t.params:
            if p.startswith("from=") or p.startswith("from2="):
                value = p.split("=", 1)[1].strip()
                from_values.append(value)
        # Skip language code if present
        if positional and positional[0].lower() == "en":
            positional = positional[1:]
        if positional:
            target = positional[0]
            # Strip anchor if present
            if "#" in target:
                target = target.split("#")[0]
            # Return target in params[0], from= values in rest
            return Template(name=name, params=[target] + from_values)
    return None


def extract_head_templates(text: str) -> list[Template]:
    """Extract head templates from text using parser."""
    # Find head templates and en-* templates
    head_names = ["head", "en-head", "head-lite"]
    en_pos_names = ["en-noun", "en-verb", "en-adj", "en-adv", "en-prop", "en-pron", "en-phrase", "en-prepphr"]

    all_names = head_names + en_pos_names
    return find_templates(text, *all_names)


def extract_phrase_type_header(text: str) -> Optional[str]:
    """Extract phrase type from section headers before POS normalization."""
    phrase_types = {
        "idiom",
        "proverb",
        "saying",
        "adage",
        "prepositional phrase",
        "adverbial phrase",
        "verb phrase",
        "verb phrase form",
        "noun phrase",
    }

    for match in POS_HEADER.finditer(text):
        header = match.group(1).lower().strip()
        header = " ".join(header.split())  # Normalize whitespace
        if header in phrase_types:
            return header

    return None


@dataclass
class PageResult:
    """Result of extracting a page."""

    title: str
    status: str  # 'ok', 'redirect', 'special', 'dict_only', 'non_english', 'no_content'
    text: Optional[str] = None


def extract_page(page_xml: str) -> PageResult:
    """
    Extract title and text from page XML.

    Returns PageResult with status indicating why page was skipped (if applicable).
    """
    # Extract title
    title_match = TITLE_PATTERN.search(page_xml)
    if not title_match:
        return PageResult(title="", status="no_content")

    title = title_match.group(1)

    # Check namespace - only process main namespace (ns=0)
    ns_match = NS_PATTERN.search(page_xml)
    if ns_match:
        namespace = int(ns_match.group(1))
        if namespace != 0:
            return PageResult(title=title, status="special")

    # Check for special pages by prefix
    if title.startswith(SPECIAL_PAGE_PREFIXES):
        return PageResult(title=title, status="special")

    # Filter translation subpages
    if "/translations" in title.lower():
        return PageResult(title=title, status="special")

    # Check for redirects
    if REDIRECT_PATTERN.search(page_xml):
        return PageResult(title=title, status="redirect")

    # Extract text
    text_match = TEXT_PATTERN.search(page_xml)
    if not text_match:
        return PageResult(title=title, status="no_content")

    text = text_match.group(1)

    # Check for English section
    if not ENGLISH_SECTION.search(text):
        return PageResult(title=title, status="non_english")

    # Check for dictionary-only terms
    if DICT_ONLY.search(text):
        return PageResult(title=title, status="dict_only")

    return PageResult(title=title, status="ok", text=text)


@dataclass
class PageLevelCache:
    """Cached page-level data that is truly page-wide (not per etymology)."""

    wc: int
    categories: list[str]  # Page-wide categories
    categories_lower: list[str]  # Pre-lowercased for efficient matching


@dataclass
class EtymologyBlockCache:
    """Cached data for a single etymology block (or the whole page if no etymologies)."""

    etymology_text: str
    etymology_templates: list[Template]
    hyphenation_parts: list[str]
    rhymes_syllable_count: Optional[int]
    syllable_category_count: Optional[int]
    ipa_transcription: Optional[str]
    phrase_type_header: Optional[str]
    spelling_labels: list[str]


@dataclass
class EtymologyBlock:
    """An etymology block with its boundaries and cache."""

    start: int  # Start position in English section
    end: int  # End position in English section
    cache: EtymologyBlockCache


def build_page_cache(title: str, english_text: str) -> PageLevelCache:
    """Build page-level cache from English section text."""
    categories = extract_categories(english_text)
    return PageLevelCache(
        wc=len(title.split()),
        categories=categories,
        categories_lower=[c.lower() for c in categories],
    )


def build_etymology_cache(
    block_text: str,
    preamble_cache: Optional["EtymologyBlockCache"] = None,
) -> EtymologyBlockCache:
    """Build etymology-scoped cache from a block of text.

    Args:
        block_text: The text of this etymology block
        preamble_cache: Optional cache from the preamble (content before first etymology).
            If provided, pronunciation data (hyphenation, rhymes, syllable count, IPA)
            from the preamble is used as fallback when not found in the block.
    """
    etymology_text = extract_etymology_text(block_text)

    # Extract pronunciation data from this block
    hyphenation = extract_hyphenation(block_text)
    rhymes_syllable = extract_rhymes_syllable_count(block_text)
    syllable_category = extract_syllable_category_count(block_text)
    ipa = extract_ipa_transcription(block_text)

    # Fall back to preamble pronunciation data if block has none
    if preamble_cache:
        if not hyphenation:
            hyphenation = preamble_cache.hyphenation_parts
        if rhymes_syllable is None:
            rhymes_syllable = preamble_cache.rhymes_syllable_count
        if syllable_category is None:
            syllable_category = preamble_cache.syllable_category_count
        if ipa is None:
            ipa = preamble_cache.ipa_transcription

    return EtymologyBlockCache(
        etymology_text=etymology_text,
        etymology_templates=extract_etymology_templates(etymology_text),
        hyphenation_parts=hyphenation,
        rhymes_syllable_count=rhymes_syllable,
        syllable_category_count=syllable_category,
        ipa_transcription=ipa,
        phrase_type_header=extract_phrase_type_header(block_text),
        spelling_labels=extract_spelling_labels(block_text),
    )


def find_etymology_blocks(english_text: str) -> list[EtymologyBlock]:
    """
    Find etymology blocks in the English section.

    Returns a list of EtymologyBlock objects, each with start/end positions.
    If no etymology headers found, returns a single block covering the whole section.

    Pronunciation inheritance: When pages have a Pronunciation section before the
    first Etymology header (a common pattern in Wiktionary), that pronunciation data
    is inherited by all etymology blocks as a fallback. This ensures words like
    "set", "cat", "hell" don't lose their syllable counts just because they have
    multiple etymologies.
    """
    etymology_matches = list(ETYMOLOGY_HEADER.finditer(english_text))

    if not etymology_matches:
        # No etymology headers - whole section is one block
        cache = build_etymology_cache(english_text)
        return [EtymologyBlock(start=0, end=len(english_text), cache=cache)]

    # Extract preamble (content before first etymology header)
    # This typically contains shared Pronunciation data
    preamble_text = english_text[: etymology_matches[0].start()]
    preamble_cache = build_etymology_cache(preamble_text) if preamble_text.strip() else None

    blocks = []
    for i, match in enumerate(etymology_matches):
        start = match.end()
        # Block extends to next etymology header or end of text
        if i + 1 < len(etymology_matches):
            end = etymology_matches[i + 1].start()
        else:
            end = len(english_text)

        block_text = english_text[start:end]
        cache = build_etymology_cache(block_text, preamble_cache=preamble_cache)
        blocks.append(EtymologyBlock(start=start, end=end, cache=cache))

    return blocks


def find_etymology_for_pos(pos_start: int, etymology_blocks: list[EtymologyBlock]) -> EtymologyBlockCache:
    """Find which etymology block a POS header belongs to."""
    for block in etymology_blocks:
        if block.start <= pos_start < block.end:
            return block.cache

    # Fallback to first block if not found (shouldn't happen)
    return etymology_blocks[0].cache if etymology_blocks else build_etymology_cache("")


def extract_evidence_from_section(
    title: str,
    pos_header: str,
    section_text: str,
    page_cache: PageLevelCache,
    etym_cache: EtymologyBlockCache,
    definition_marker_pattern: Optional[re.Pattern] = None,
    parse_definition_marker: Optional[callable] = None,
) -> Iterator[Evidence]:
    """
    Extract Evidence objects for each definition in a POS section.

    Args:
        title: Page title (the word)
        pos_header: The POS header text
        section_text: Text of this POS section
        page_cache: Pre-computed page-level data (categories, wc)
        etym_cache: Pre-computed etymology-scoped data (IPA, hyphenation, etymology, etc.)
        definition_marker_pattern: Compiled regex for matching definition lines (from config)
        parse_definition_marker: Function to parse prefix into (type, level) tuple

    Yields:
        Evidence objects, one per definition line
    """
    # Section-level data (parse once per section)
    head_templates = extract_head_templates(section_text)

    # Section-level inflection template (in definition area, not etymology)
    inflection_template = extract_inflection_template(section_text)

    # Section-level alternative form template
    altform_template = extract_altform_template(section_text)

    # Extract definition lines using config pattern or fallback to primary-only
    definition_entries: list[tuple[str, int, str]] = []  # (text, level, type)

    if definition_marker_pattern and parse_definition_marker:
        # Use config-driven definition extraction (captures #, ##, #*, #:, etc.)
        for match in definition_marker_pattern.finditer(section_text):
            prefix = match.group(1)
            text = match.group(2).strip()
            def_type, level = parse_definition_marker(prefix)
            definition_entries.append((text, level, def_type))
    else:
        # Fallback: primary definitions only (backwards compatibility)
        for match in DEFINITION_LINE.finditer(section_text):
            definition_entries.append((match.group(1), 1, "primary"))

    if not definition_entries:
        definition_entries = [("", 1, "primary")]  # Create at least one entry

    for def_text, def_level, def_type in definition_entries:
        # Definition-level labels
        labels = extract_labels(def_text)

        # Definition-level senseid
        senseid = extract_senseid(def_text)

        yield Evidence(
            title=title,
            wc=page_cache.wc,
            pos_header=pos_header,
            head_templates=head_templates,
            categories=page_cache.categories,
            categories_lower=page_cache.categories_lower,
            labels=labels,
            etymology_text=etym_cache.etymology_text,
            etymology_templates=etym_cache.etymology_templates,
            definition_text=def_text,
            definition_level=def_level,
            definition_type=def_type,
            hyphenation_parts=etym_cache.hyphenation_parts,
            rhymes_syllable_count=etym_cache.rhymes_syllable_count,
            syllable_category_count=etym_cache.syllable_category_count,
            ipa_transcription=etym_cache.ipa_transcription,
            inflection_template=inflection_template,
            altform_template=altform_template,
            phrase_type_header=etym_cache.phrase_type_header,
            spelling_labels=etym_cache.spelling_labels,
            senseid=senseid,
        )


@dataclass
class ExtractionResult:
    """Result of extracting evidence from a page, including metadata."""

    evidence: list[Evidence]
    unknown_headers: list[str]  # Headers not in allowlist or ignore list


def extract_evidence(
    title: str,
    text: str,
    is_ignored_header: callable,
    pos_headers: set[str] | None = None,
    definition_marker_pattern: Optional[re.Pattern] = None,
    parse_definition_marker: Optional[callable] = None,
) -> Iterator[Evidence]:
    """
    Extract Evidence objects from a Wiktionary page.

    Args:
        title: Page title
        text: Page wikitext
        is_ignored_header: Function(header: str) -> bool that checks if a header should be skipped.
            The header passed is already lowercased and whitespace-normalized.
        pos_headers: Allowlist of valid POS headers (lowercase). If None, accepts all non-ignored.
        definition_marker_pattern: Compiled regex for matching definition lines (from config)
        parse_definition_marker: Function to parse prefix into (type, level) tuple

    Yields:
        Evidence objects for each (POS, definition) pair
    """
    result = extract_evidence_with_unknowns(
        title, text, is_ignored_header, pos_headers,
        definition_marker_pattern, parse_definition_marker
    )
    yield from result.evidence


def extract_evidence_with_unknowns(
    title: str,
    text: str,
    is_ignored_header: callable,
    pos_headers: set[str] | None = None,
    definition_marker_pattern: Optional[re.Pattern] = None,
    parse_definition_marker: Optional[callable] = None,
) -> ExtractionResult:
    """
    Extract Evidence objects from a Wiktionary page, tracking unknown headers.

    Etymology scoping: Each POS section inherits etymology data from its
    containing etymology block. This prevents inflection/IPA/etymology from
    bleeding across different etymologies on multi-etymology pages.

    Args:
        title: Page title
        text: Page wikitext
        is_ignored_header: Function(header: str) -> bool that checks if a header should be skipped.
            The header passed is already lowercased and whitespace-normalized.
        pos_headers: Allowlist of valid POS headers (lowercase). If None, accepts all non-ignored.
        definition_marker_pattern: Compiled regex for matching definition lines (from config)
        parse_definition_marker: Function to parse prefix into (type, level) tuple

    Returns:
        ExtractionResult with evidence list and unknown headers
    """

    evidence_list = []
    unknown_headers = []

    # Extract English section only
    english_text = extract_english_section(text)
    if not english_text:
        return ExtractionResult(evidence=[], unknown_headers=[])

    # Build page-level cache ONCE (truly page-wide: categories, word count)
    page_cache = build_page_cache(title, english_text)

    # Build etymology blocks (each with its own IPA, hyphenation, etymology, etc.)
    etymology_blocks = find_etymology_blocks(english_text)

    # Find POS headers and their sections
    headers = []
    for match in POS_HEADER.finditer(english_text):
        header_text = match.group(1).strip()
        header_lower = header_text.lower()
        header_normalized = " ".join(header_lower.split())

        # Skip configured non-POS headers (etymology, pronunciation, etc.)
        if is_ignored_header(header_normalized):
            continue

        # Check if header is in allowlist (if provided)
        if pos_headers is not None:
            if header_normalized not in pos_headers:
                # Unknown header - track it but don't emit evidence
                unknown_headers.append(header_text)
                continue

        headers.append((match.start(), match.end(), header_text))

    if not headers:
        # No valid POS headers - don't create "unknown" evidence
        # (this is the new behavior per review: drop unknown headers)
        return ExtractionResult(evidence=[], unknown_headers=unknown_headers)

    # Process each POS section
    for i, (start, end, header_text) in enumerate(headers):
        # Section extends from end of header to start of next header (or end)
        section_start = end
        section_end = headers[i + 1][0] if i + 1 < len(headers) else len(english_text)
        section_text = english_text[section_start:section_end]

        # Find which etymology block this POS section belongs to
        etym_cache = find_etymology_for_pos(start, etymology_blocks)

        for ev in extract_evidence_from_section(
            title=title,
            pos_header=header_text,
            section_text=section_text,
            page_cache=page_cache,
            etym_cache=etym_cache,
            definition_marker_pattern=definition_marker_pattern,
            parse_definition_marker=parse_definition_marker,
        ):
            evidence_list.append(ev)

    return ExtractionResult(evidence=evidence_list, unknown_headers=unknown_headers)
