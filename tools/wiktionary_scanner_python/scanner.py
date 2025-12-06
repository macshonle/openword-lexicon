#!/usr/bin/env python3
"""
scanner.py - Lightweight scanner-based Wiktionary parser

Part of tools/wiktionary_scanner_python/ - the Python reference implementation
of the Wiktionary scanner. A Rust implementation is available at
tools/wiktionary-scanner-rust/ which is significantly faster (typically 5-10x).
Both produce identical output.

Production builds use the Rust version via `make build-wiktionary-json`.
This Python version serves as a readable reference and for testing/development.

Uses simple string scanning to find <page> boundaries instead of full XML
parsing. Much faster than ET.iterparse() for predictable MediaWiki format.

No XML validation, no DOM building, no namespace overhead - just fast
extraction of the data we need.

Usage:
    python -m wiktionary_scanner_python.scanner INPUT.xml.bz2 OUTPUT.jsonl [--limit N]
"""

import bz2
import json
import logging
import re
import sys
import time
import unicodedata as ud
from pathlib import Path

import yaml
from dataclasses import dataclass
from typing import Any, Dict, List, Set, Optional, Tuple
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Wikitext Parser Data Structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Wikilink:
    """Represents a parsed wikilink: [[target#anchor|display]]"""
    target: str
    anchor: Optional[str] = None
    display: Optional[str] = None

    def text(self) -> str:
        """Return display text if present, otherwise target."""
        return self.display if self.display is not None else self.target


@dataclass
class Template:
    """Represents a parsed template: {{name|param1|param2|...}}"""
    name: str
    params: List[str]


# ─────────────────────────────────────────────────────────────────────────────
# Wikitext Recursive Descent Parser
# ─────────────────────────────────────────────────────────────────────────────

class WikitextParser:
    """
    Recursive descent parser for Wiktionary template parameters.

    Uses the call stack for nesting - no explicit depth counters.
    Each parse method returns structured data; callers decide what to do with it.

    Grammar:
        params          ::= param ("|" param)*
        param           ::= element*
        element         ::= template | wikilink | char
        template        ::= "{{" template_body "}}"
        template_body   ::= (template | wikilink | template_char)*
        wikilink        ::= "[[" target ("#" anchor)? ("|" display)? "]]"
        target          ::= target_char+
        anchor          ::= anchor_char+
        display         ::= display_char+
    """

    def __init__(self, text: str):
        self.text = text
        self.pos = 0

    def peek(self, n: int = 1) -> str:
        """Look ahead n characters without consuming."""
        return self.text[self.pos:self.pos + n]

    def consume(self, n: int = 1) -> str:
        """Consume and return n characters."""
        result = self.text[self.pos:self.pos + n]
        self.pos += n
        return result

    def at_end(self) -> bool:
        """Check if we've reached end of input."""
        return self.pos >= len(self.text)

    # ─────────────────────────────────────────────────────────────
    # Top-level entry point: params ::= param ("|" param)*
    # ─────────────────────────────────────────────────────────────
    def parse_params(self) -> List[str]:
        """Parse template parameters separated by |."""
        params = []
        while not self.at_end():
            param = self.parse_param()
            params.append(param)
            if self.peek() == "|":
                self.consume()
            else:
                break
        return params

    # ─────────────────────────────────────────────────────────────
    # param ::= element*  (terminated by | or end)
    # ─────────────────────────────────────────────────────────────
    def parse_param(self) -> str:
        """Parse elements until | or end of input."""
        result = ""
        while not self.at_end() and self.peek() != "|":
            if self.peek(2) == "[[":
                wikilink = self.parse_wikilink()
                result += wikilink.text()  # Extract display or target
            elif self.peek(2) == "{{":
                template = self.parse_template()
                # For morphology params, nested templates are metadata - discard
                _ = template
            else:
                result += self.consume()
        return result.strip()

    # ─────────────────────────────────────────────────────────────
    # wikilink ::= "[[" target ("#" anchor)? ("|" display)? "]]"
    # ─────────────────────────────────────────────────────────────
    def parse_wikilink(self) -> Wikilink:
        """Parse [[target#anchor|display]] -> Wikilink object."""
        self.consume(2)  # consume "[["

        target = self.parse_target()
        anchor = None
        display = None

        # Optional: "#" anchor
        if self.peek() == "#":
            self.consume()
            anchor = self.parse_anchor()

        # Optional: "|" display
        if self.peek() == "|":
            self.consume()
            display = self.parse_display()

        # Consume "]]"
        if self.peek(2) == "]]":
            self.consume(2)

        return Wikilink(target=target, anchor=anchor, display=display)

    def parse_target(self) -> str:
        """target ::= target_char+  where target_char = [^#|\\]]"""
        result = ""
        while not self.at_end() and self.peek() not in "#|]":
            result += self.consume()
        return result

    def parse_anchor(self) -> str:
        """anchor ::= anchor_char+  where anchor_char = [^|\\]]"""
        result = ""
        while not self.at_end() and self.peek() not in "|]":
            result += self.consume()
        return result

    def parse_display(self) -> str:
        """display ::= display_char+  where display_char = [^\\]]"""
        result = ""
        while not self.at_end() and self.peek() != "]":
            result += self.consume()
        return result

    # ─────────────────────────────────────────────────────────────
    # template ::= "{{" params "}}"
    # (reuses param parsing - templates have same structure!)
    # ─────────────────────────────────────────────────────────────
    def parse_template(self) -> Template:
        """
        Parse {{name|param1|param2|...}} -> Template object.
        RECURSIVELY handles nested templates via parse_template_param_inner().
        """
        self.consume(2)  # consume "{{"

        # Parse template contents as params (recursive!)
        params = self.parse_template_params_inner()

        if self.peek(2) == "}}":
            self.consume(2)

        # First param is template name, rest are params
        name = params[0] if params else ""
        return Template(name=name, params=params[1:])

    def parse_template_params_inner(self) -> List[str]:
        """Parse params inside a template (terminated by }})."""
        params = []
        while not self.at_end() and self.peek(2) != "}}":
            param = self.parse_template_param_inner()
            params.append(param)
            if self.peek() == "|":
                self.consume()
            else:
                break
        return params

    def parse_template_param_inner(self) -> str:
        """Parse a single param inside a template (terminated by | or }})."""
        result = ""
        while not self.at_end() and self.peek() != "|" and self.peek(2) != "}}":
            if self.peek(2) == "[[":
                wikilink = self.parse_wikilink()
                result += wikilink.text()
            elif self.peek(2) == "{{":
                template = self.parse_template()  # RECURSIVE!
                # Nested templates produce no text for our purposes
                _ = template
            else:
                result += self.consume()
        return result.strip()


def parse_template_params(content: str) -> List[str]:
    """
    Parse template parameters with proper bracket handling.

    This is the main entry point for parsing template content.
    Handles nested [[wikilinks]] and {{templates}} correctly.

    Args:
        content: The inner content of a template (without outer {{ }})

    Returns:
        List of parsed parameter strings with wikilink display text extracted
    """
    parser = WikitextParser(content)
    return parser.parse_params()


# ─────────────────────────────────────────────────────────────────────────────
# Head Template POS Extraction - Proper parsing for {{head|en|POS|...}}
# ─────────────────────────────────────────────────────────────────────────────

# Regex to find head templates and capture their FULL content (greedy but balanced)
# This matches {{head|en|...}}, {{en-head|en|...}}, {{head-lite|en|...}}
# We capture everything after the template name up to the closing }}
# Note: This is a two-phase approach:
#   1. Find potential head templates with a simple regex
#   2. Use WikitextParser to properly extract parameters
HEAD_TEMPLATE_FINDER = re.compile(
    r'\{\{(head|en-head|head-lite)\|en\|',
    re.IGNORECASE
)


def extract_head_template_content(text: str, start_pos: int) -> Optional[str]:
    """
    Extract the full content of a template starting at start_pos.

    Uses bracket counting to handle nested templates correctly.

    Args:
        text: Full text to search in
        start_pos: Position right after '{{head|en|' (where content begins)

    Returns:
        Template content (without {{ and }}) or None if malformed
    """
    depth = 1  # We're inside one {{ already
    pos = start_pos
    content_start = start_pos

    while pos < len(text) and depth > 0:
        if text[pos:pos + 2] == '{{':
            depth += 1
            pos += 2
        elif text[pos:pos + 2] == '}}':
            depth -= 1
            if depth == 0:
                return text[content_start:pos]
            pos += 2
        else:
            pos += 1

    # Unclosed template - return what we have
    return text[content_start:pos] if pos > content_start else None


def extract_pos_from_head_template(template_content: str) -> Optional[str]:
    """
    Extract the POS from head template content using proper parsing.

    The POS is the first positional parameter (no '=' in it).
    Named parameters like 'head=...', 'sort=...' are skipped.

    Args:
        template_content: Content after '{{head|en|' and before '}}'

    Returns:
        The POS string (lowercase) or None if not found

    Examples:
        >>> extract_pos_from_head_template("noun form|head=kris kringles")
        'noun form'
        >>> extract_pos_from_head_template("head=[[word]]|noun")
        'noun'
        >>> extract_pos_from_head_template("proper noun|head=[[United States]]")
        'proper noun'
    """
    # Parse using WikitextParser for proper bracket handling
    params = parse_template_params(template_content)

    # Find first positional parameter (no '=' in it)
    for param in params:
        if '=' not in param and param.strip():
            return param.strip().lower()

    return None


def find_head_template_pos_values(text: str) -> List[str]:
    """
    Find all POS values from {{head|en|...}} templates in text.

    Uses proper parsing to correctly handle:
    - Named parameters like head=...
    - Nested templates
    - Wikilinks in parameters

    Args:
        text: Wikitext to search

    Returns:
        List of POS values found (lowercase, deduplicated by order)

    Examples:
        >>> find_head_template_pos_values("{{head|en|noun form|head=cats}}")
        ['noun form']
        >>> find_head_template_pos_values("{{head|en|head=[[word]]|verb}}")
        ['verb']
    """
    pos_values = []
    seen = set()

    for match in HEAD_TEMPLATE_FINDER.finditer(text):
        # Position right after '{{head|en|'
        content_start = match.end()

        # Extract full template content with bracket balancing
        content = extract_head_template_content(text, content_start)
        if not content:
            continue

        # Parse to get POS
        pos = extract_pos_from_head_template(content)
        if pos and pos not in seen:
            seen.add(pos)
            pos_values.append(pos)

    return pos_values


class BZ2StreamReader:
    """Streaming BZ2 decompressor with progress feedback."""

    def __init__(self, filepath: Path, chunk_size: int = 256 * 1024, metrics: Optional[Dict] = None):
        self.filepath = filepath
        self.chunk_size = chunk_size
        self.file = open(filepath, 'rb')
        self.decompressor = bz2.BZ2Decompressor()
        self.buffer = b''
        self.total_compressed = 0
        self.total_decompressed = 0
        self.last_progress = 0
        self.start_time = time.time()
        self.metrics = metrics  # Optional metrics dict to update

    def read(self, size: int = -1) -> bytes:
        """Read decompressed data."""
        if size == -1:
            while not self.decompressor.eof:
                self._decompress_chunk()
            result = self.buffer
            self.buffer = b''
            return result

        while len(self.buffer) < size and not self.decompressor.eof:
            self._decompress_chunk()

        result = self.buffer[:size]
        self.buffer = self.buffer[size:]
        return result

    def _decompress_chunk(self):
        """Decompress one chunk and update progress."""
        if self.decompressor.eof:
            return

        compressed = self.file.read(self.chunk_size)
        if not compressed:
            return

        self.total_compressed += len(compressed)
        decompressed = self.decompressor.decompress(compressed)
        self.buffer += decompressed
        self.total_decompressed += len(decompressed)

        # Update metrics if provided
        if self.metrics is not None:
            elapsed = time.time() - self.start_time
            rate_mb = (self.total_decompressed / (1024 * 1024)) / elapsed if elapsed > 0 else 0
            self.metrics["Decomp MB"] = int(self.total_decompressed / (1024 * 1024))
            self.metrics["Decomp Rate"] = rate_mb

    def close(self):
        self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


# Regex patterns for extraction
ENGLISH_SECTION = re.compile(r'==\s*English\s*==', re.IGNORECASE)
LANGUAGE_SECTION = re.compile(r'^==\s*([^=]+?)\s*==$', re.MULTILINE)
POS_HEADER = re.compile(r'^===+\s*(.+?)\s*===+\s*$', re.MULTILINE)  # Already flexible with \s*
# NOTE: POS extraction from {{head|en|POS}} templates now uses proper bracket-aware
# parsing via find_head_template_pos_values() - see HEAD_TEMPLATE_FINDER and helpers
# Extract POS from {{en-POS}} templates (e.g., {{en-noun}}, {{en-verb}}, {{en-prop}})
EN_POS_TEMPLATE = re.compile(r'\{\{en-(noun|verb|adj|adv|prop|pron)\b', re.IGNORECASE)
# Check for abbreviation templates
ABBREVIATION_TEMPLATE = re.compile(r'\{\{(?:abbreviation of|abbrev of|abbr of|initialism of)\|en\|', re.IGNORECASE)
# Definition-generating templates that indicate English content (even without POS headers)
# These are quaternary validation signals for entries that have definitions but no POS headers
DEFINITION_TEMPLATES = re.compile(r'\{\{(?:' +
    r'abbr of|abbreviation of|abbrev of|initialism of|acronym of|' +
    r'alternative form of|alt form|alt sp|' +
    r'plural of|' +
    r'past tense of|past participle of|' +
    r'present participle of|' +
    r'en-(?:noun|verb|adj|adv|past of)' +
    r')\|en\|', re.IGNORECASE)
# Special template patterns for specific POS types
PREP_PHRASE_TEMPLATE = re.compile(r'\{\{en-prepphr\b', re.IGNORECASE)
CONTEXT_LABEL = re.compile(r'\{\{(?:lb|label|context)\|en\|([^}]+)\}\}', re.IGNORECASE)
CATEGORY = re.compile(r'\[\[Category:English\s+([^\]]+)\]\]', re.IGNORECASE)
DICT_ONLY = re.compile(r'\{\{no entry\|en', re.IGNORECASE)  # Matches both {{no entry|en}} and {{no entry|en|...}}
# Extract hyphenation data for syllable counts (English-specific via |en| param)
HYPHENATION_TEMPLATE = re.compile(r'\{\{(?:hyphenation|hyph)\|en\|([^}]+)\}\}', re.IGNORECASE)
# Extract syllable count from rhymes template: {{rhymes|en|...|s=N}}
RHYMES_SYLLABLE = re.compile(r'\{\{rhymes\|en\|[^}]*\|s=(\d+)', re.IGNORECASE)
# Extract syllable count from category labels (e.g., "Category:English 3-syllable words")
SYLLABLE_CATEGORY = re.compile(r'\[\[Category:English\s+(\d+)-syllable\s+words?\]\]', re.IGNORECASE)
# IPA extraction pattern - matches {{IPA|en|/transcription/}} or {{IPA|en|[transcription]}}
IPA_TEMPLATE = re.compile(r'\{\{IPA\|en\|([^}]+)\}\}', re.IGNORECASE)
# Extract transcription from slashes or brackets
IPA_TRANSCRIPTION = re.compile(r'[/\[]([^/\[\]]+)[/\]]')

# Etymology section extraction (for morphology analysis)
ETYMOLOGY_SECTION = re.compile(r'===+\s*Etymology\s*\d*\s*===+\s*\n(.+?)(?=\n===|\Z)', re.DOTALL | re.IGNORECASE)

# Inflection templates for lemma extraction
# These templates indicate the word is a grammatical inflection of a base word (lemma)
# Format: {{template name|en|lemma|optional params...}}
INFLECTION_TEMPLATES = [
    # Noun inflections
    ('plural of', re.compile(r'\{\{plural of\|en\|([^|}]+)', re.IGNORECASE)),

    # Verb inflections
    ('past tense of', re.compile(r'\{\{past tense of\|en\|([^|}]+)', re.IGNORECASE)),
    ('past participle of', re.compile(r'\{\{past participle of\|en\|([^|}]+)', re.IGNORECASE)),
    ('present participle of', re.compile(r'\{\{present participle of\|en\|([^|}]+)', re.IGNORECASE)),
    ('third-person singular of', re.compile(r'\{\{(?:en-third-person singular of|third-person singular of)\|en\|([^|}]+)', re.IGNORECASE)),

    # Adjective/adverb inflections
    ('comparative of', re.compile(r'\{\{comparative of\|en\|([^|}]+)', re.IGNORECASE)),
    ('superlative of', re.compile(r'\{\{superlative of\|en\|([^|}]+)', re.IGNORECASE)),

    # Generic inflection template (handles various forms)
    ('inflection of', re.compile(r'\{\{inflection of\|en\|([^|}]+)', re.IGNORECASE)),
]
# Morphology templates for derivation tracking
SUFFIX_TEMPLATE = re.compile(r'\{\{suffix\|en\|([^}|]+)\|([^}|]+)(?:\|([^}|]+))?\}\}', re.IGNORECASE)
PREFIX_TEMPLATE = re.compile(r'\{\{prefix\|en\|([^}|]+)\|([^}|]+)(?:\|([^}|]+))?\}\}', re.IGNORECASE)
# Matches both {{affix|en|...}} and {{af|en|...}} (common shorthand)
AFFIX_TEMPLATE = re.compile(r'\{\{af(?:fix)?\|en\|([^}]+)\}\}', re.IGNORECASE)
COMPOUND_TEMPLATE = re.compile(r'\{\{compound\|en\|([^}]+)\}\}', re.IGNORECASE)
# Surface form template (alternative to affix template)
SURF_TEMPLATE = re.compile(r'\{\{surf\|en\|([^}]+)\}\}', re.IGNORECASE)
# Confix template (prefix + base + suffix together)
CONFIX_TEMPLATE = re.compile(r'\{\{confix\|en\|([^}|]+)\|([^}|]+)\|([^}|]+)(?:\|([^}|]+))?\}\}', re.IGNORECASE)

# Template parameter cleaning patterns (for morphology extraction)
LANG_CODE_PREFIX = re.compile(r'^[a-z]{2,4}:', re.IGNORECASE)  # Language codes like grc:, la:, ang:
WIKILINK_PATTERN = re.compile(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]')  # [[word]] or [[word|display]]
HTML_ENTITY_PATTERN = re.compile(r'<[^>]+>')  # <tag>, <id:...>, etc.


def strip_wikilinks(s: str) -> str:
    """Strip wikilink markup from a string: [[word]] -> word, [[word|display]] -> word."""
    if '[[' in s or ']]' in s:
        result = WIKILINK_PATTERN.sub(r'\1', s)
        return result.replace(']]', '')
    return s


PARAM_KEY_PATTERN = re.compile(r'^(t|gloss|pos|alt|id|lit|tr|ts|sc|nocap|nocat|notext)\d*=', re.IGNORECASE)  # Common parameter keys

# Known language codes for hyphenation templates
# This whitelist prevents false positives when filtering language codes from syllable segments
KNOWN_LANG_CODES = {
    # Major languages
    'en', 'da', 'de', 'es', 'fr', 'it', 'pt', 'nl', 'sv', 'no', 'fi',
    'pl', 'cs', 'sk', 'hu', 'ro', 'bg', 'ru', 'uk', 'el', 'tr', 'ar',
    'he', 'hi', 'bn', 'pa', 'ta', 'te', 'mr', 'gu', 'kn', 'ml', 'si',
    'th', 'vi', 'zh', 'ja', 'ko', 'id', 'ms', 'tl', 'fa', 'ur',
    # English variants
    'en-US', 'en-GB', 'en-AU', 'en-CA', 'en-NZ', 'en-ZA', 'en-IE', 'en-IN',
    # Other common codes
    'la', 'sa', 'grc', 'ang', 'enm', 'fro', 'non',
}

# Simple extraction patterns (no full XML parsing)
TITLE_PATTERN = re.compile(r'<title>([^<]+)</title>')
NS_PATTERN = re.compile(r'<ns>(\d+)</ns>')
TEXT_PATTERN = re.compile(r'<text[^>]*>(.+?)</text>', re.DOTALL)
REDIRECT_PATTERN = re.compile(r'<redirect\s+title="[^"]+"')

# Schema loading - all configuration is externalized to schema/ directory
# Both Python and Rust scanners share these YAML files as single source of truth

def _find_schema_file(filename: str) -> Path:
    """Find a schema file in the schema/ directory."""
    candidates = [
        Path(__file__).parent.parent.parent / "schema" / filename,  # From tools/wiktionary_scanner_python/
        Path("schema") / filename,  # From project root
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        f"Could not find schema/{filename}. Searched: {[str(p) for p in candidates]}"
    )


def _load_pos_map() -> Dict[str, str]:
    """Load POS mapping from schema/pos.yaml."""
    schema_path = _find_schema_file("pos.yaml")
    with open(schema_path) as f:
        schema = yaml.safe_load(f)

    pos_map = {}
    for pos_class in schema["pos_classes"]:
        code = pos_class["code"]
        for variant in pos_class["variants"]:
            pos_map[variant] = code
    return pos_map


def _load_labels() -> Dict[str, Any]:
    """Load label classifications from schema/labels.yaml."""
    labels_path = _find_schema_file("labels.yaml")
    with open(labels_path) as f:
        return yaml.safe_load(f)


# Load configuration at module import time
POS_MAP = _load_pos_map()
_LABELS = _load_labels()

# Extract label sets from loaded configuration
REGISTER_LABELS: Set[str] = set(_LABELS["register_labels"])
TEMPORAL_LABELS: Set[str] = set(_LABELS["temporal_labels"])
DOMAIN_LABELS: Set[str] = set(_LABELS["domain_labels"])
REGION_LABELS: Dict[str, str] = _LABELS["region_labels"]
SPELLING_LABELS: Dict[str, str] = _LABELS["spelling_labels"]
SPECIAL_PAGE_PREFIXES: Tuple[str, ...] = tuple(_LABELS["special_page_prefixes"])


def extract_english_section(text: str) -> Optional[str]:
    """
    Extract ONLY the ==English== section from a Wiktionary page.

    This prevents contamination from other language sections (French, Translingual, etc.)
    which could have different POS headers, templates, and categories.

    Returns the English section text, or None if no English section found.
    """
    # Find the start of the English section
    english_match = ENGLISH_SECTION.search(text)
    if not english_match:
        return None

    english_start = english_match.end()

    # Find the start of the next language section (or end of text)
    # Language sections are marked with == (level 2 headers)
    next_section = None
    for match in LANGUAGE_SECTION.finditer(text, english_start):
        lang = match.group(1).strip()
        if lang.lower() != 'english':
            next_section = match.start()
            break

    # Extract English section only
    if next_section:
        return text[english_start:next_section]
    else:
        return text[english_start:]


def extract_pos_tags(text: str) -> List[str]:
    """Extract POS tags from section headers and {{head}} templates."""
    pos_tags = []

    # Primary: Extract from section headers (===Noun===, etc.)
    for match in POS_HEADER.finditer(text):
        header = match.group(1).lower().strip()
        # Normalize whitespace (handle "Proper  noun" with double spaces)
        header = ' '.join(header.split())
        if header in POS_MAP:
            pos_tags.append(POS_MAP[header])

    # Fallback: If no section headers found, try {{head|en|POS}} templates
    # Uses proper bracket-aware parsing to handle named params, nested templates, etc.
    if not pos_tags:
        for pos in find_head_template_pos_values(text):
            if pos in POS_MAP:
                pos_tags.append(POS_MAP[pos])
            # Handle special cases
            elif pos == 'phrase':
                pos_tags.append('phrase')
            elif pos == 'proverb':
                pos_tags.append('phrase')
            elif pos == 'numeral':
                pos_tags.append('numeral')

    # Additional fallback: Check for {{en-POS}} templates (e.g., {{en-noun}})
    if not pos_tags:
        for match in EN_POS_TEMPLATE.finditer(text):
            pos = match.group(1).lower()
            # Map abbreviated forms
            pos_mapping = {
                'noun': 'noun',
                'verb': 'verb',
                'adj': 'adjective',
                'adv': 'adverb',
                'prop': 'proper',  # {{en-prop}} is for proper nouns
                'pron': 'pronoun',
            }
            if pos in pos_mapping:
                pos_tags.append(pos_mapping[pos])

    # Additional fallback: Check for prepositional phrase template or category
    if not pos_tags:
        if PREP_PHRASE_TEMPLATE.search(text):
            pos_tags.append('phrase')
        elif 'Category:English prepositional phrases' in text:
            pos_tags.append('phrase')

    # Final fallback: Check for stenoscript abbreviations (no POS headers)
    # These have {{abbreviation of|en|...}} and Category:English Stenoscript abbreviations
    if not pos_tags:
        if ABBREVIATION_TEMPLATE.search(text) or 'Category:English Stenoscript abbreviations' in text:
            pos_tags.append('symbol')

    return sorted(set(pos_tags))


# Definition line pattern - lines starting with # (but not ## which are sub-definitions)
DEFINITION_LINE = re.compile(r'^#\s+(.+)$', re.MULTILINE)


class PosSection:
    """Represents a POS section with its definitions."""
    def __init__(self, pos: str, definitions: List[str]):
        self.pos = pos
        self.definitions = definitions


def parse_pos_sections(english_text: str) -> List[PosSection]:
    """
    Parse POS sections and their definitions from English text.
    Returns list of PosSection, each containing pos and definitions.
    """
    sections = []

    # Find all POS headers and their positions
    headers = []
    for match in POS_HEADER.finditer(english_text):
        header_text = match.group(1).lower().strip()
        header_normalized = ' '.join(header_text.split())

        # Map to normalized POS (proper nouns get pos='proper')
        if header_normalized in POS_MAP:
            mapped_pos = POS_MAP[header_normalized]
            headers.append((match.start(), mapped_pos))

    # For each POS header, extract definitions until next header
    for i, (start_pos, pos) in enumerate(headers):
        section_start = start_pos
        section_end = headers[i + 1][0] if i + 1 < len(headers) else len(english_text)

        section_text = english_text[section_start:section_end]

        # Extract definition lines (lines starting with single #)
        definitions = [m.group(1) for m in DEFINITION_LINE.finditer(section_text)]

        if definitions:
            sections.append(PosSection(pos, definitions))

    return sections


def extract_labels_from_line(line: str) -> tuple:
    """
    Extract label tags from a single definition line.
    Returns (register_tags, region_tags, domain_tags, temporal_tags) as sorted lists.
    """
    register_tags = set()
    region_tags = set()
    domain_tags = set()
    temporal_tags = set()

    # Extract from context labels in this line
    for match in CONTEXT_LABEL.finditer(line):
        for label in match.group(1).split('|'):
            label = label.strip().lower()

            if label in REGISTER_LABELS:
                register_tags.add(label)
            elif label in TEMPORAL_LABELS:
                temporal_tags.add(label)
            elif label in DOMAIN_LABELS:
                domain_tags.add(label)
            elif label in REGION_LABELS:
                region_tags.add(REGION_LABELS[label])

    return (
        sorted(register_tags),
        sorted(region_tags),
        sorted(domain_tags),
        sorted(temporal_tags),
    )


def extract_labels(text: str) -> Dict[str, List[str]]:
    """Extract context labels from templates and categorize them."""
    labels = {
        'register': set(),
        'temporal': set(),
        'domain': set(),
        'region': set(),
        'categories': set(),  # NEW: Track all categories (including prefixes/suffixes)
    }

    # Extract from {{lb|en|...}} templates
    for match in CONTEXT_LABEL.finditer(text):
        label_text = match.group(1)
        for label in label_text.split('|'):
            label = label.strip().lower()

            if label in REGISTER_LABELS:
                labels['register'].add(label)
            elif label in TEMPORAL_LABELS:
                labels['temporal'].add(label)
            elif label in DOMAIN_LABELS:
                labels['domain'].add(label)
            elif label in REGION_LABELS:
                labels['region'].add(REGION_LABELS[label])

    # Extract from categories
    for match in CATEGORY.finditer(text):
        cat = match.group(1)  # Keep original case for categories
        cat_lower = cat.lower()

        # Store the category itself
        labels['categories'].add(cat)

        if 'informal' in cat_lower or 'colloquial' in cat_lower:
            labels['register'].add('informal')
        if 'slang' in cat_lower:
            labels['register'].add('slang')
        if 'vulgar' in cat_lower:
            labels['register'].add('vulgar')
        if 'offensive' in cat_lower or 'derogatory' in cat_lower:
            labels['register'].add('offensive')
        if 'childish' in cat_lower or 'baby talk' in cat_lower or 'infantile' in cat_lower:
            labels['register'].add('childish')
        if 'obsolete' in cat_lower:
            labels['temporal'].add('obsolete')
        if 'archaic' in cat_lower:
            labels['temporal'].add('archaic')

        for region_key, region_code in REGION_LABELS.items():
            if region_key in cat_lower:
                labels['region'].add(region_code)
                break

    return {k: sorted(v) for k, v in labels.items() if v}


def extract_syllable_count_from_hyphenation(text: str, word: str) -> Optional[int]:
    """
    Extract syllable count from {{hyphenation|en|...}} template.

    The regex pattern already requires |en| so the captured content contains
    only syllable segments (no need to filter language codes).

    Args:
        text: The Wiktionary page text
        word: The word being processed (unused but kept for API compatibility)

    Returns:
        Number of syllables if reliably determined, None otherwise

    Handles complex formats:
    - Basic: {{hyphenation|en|dic|tion|a|ry}} -> 4 syllables
    - Alternatives: {{hyphenation|en|dic|tion|a|ry||dic|tion|ary}} -> 4 (uses first)
    - Parameters: {{hyphenation|en|lang=en-US|dic|tion|a|ry}} -> 4 (filters params)
    - First syllable matches lang code: {{hyphenation|en|en|cy|clo|pe|di|a}} -> 6 syllables

    Returns None for unreliable cases:
    - {{hyphenation|en|encyclopedia}} -> None (single unseparated part > 3 chars)
    - {{hyphenation|en|}} -> None (empty)

    Examples:
    - "encyclopedia" with {{hyphenation|en|en|cy|clo|pe|di|a}} -> 6 (en-cy-clo-pe-di-a)
    - "dictionary" with {{hyphenation|en|dic|tion|a|ry}} -> 4 (dic-tion-a-ry)
    - "cat" with {{hyphenation|en|cat}} -> None (single part > 3 chars, likely incomplete)
    - "it" with {{hyphenation|en|it}} -> 1 (short word, acceptable)
    """
    match = HYPHENATION_TEMPLATE.search(text)
    if not match:
        return None

    content = match.group(1)

    # Handle alternatives (||) - use first alternative
    alternatives = content.split('||')
    first_alt = alternatives[0] if alternatives else content

    # Parse pipe-separated segments
    parts = first_alt.split('|')

    # Filter syllables (exclude parameters and empty parts only)
    # NOTE: No language code filtering needed - the regex already consumed |en|
    syllables = []
    for part in parts:
        part = part.strip()

        # Skip empty parts
        if not part:
            continue

        # Skip parameter assignments (lang=, caption=, etc.)
        if '=' in part:
            continue

        syllables.append(part)

    # Safety check: Single-part templates with long unseparated text are likely
    # incomplete data (e.g., {{hyphenation|en|encyclopedia}} instead of proper separation)
    # We only trust single-part templates for very short words (1-3 chars)
    if len(syllables) == 1 and len(syllables[0]) > 3:
        return None

    # Return syllable count if we found any syllables
    return len(syllables) if syllables else None


def extract_syllable_count_from_rhymes(text: str) -> Optional[int]:
    """
    Extract syllable count from {{rhymes|en|...|s=N}} template.

    The rhymes template often includes a syllable count parameter.
    Example: {{rhymes|en|eɪθs|s=1}} indicates 1 syllable.

    Returns syllable count if found, None otherwise.
    """
    match = RHYMES_SYLLABLE.search(text)
    if match:
        return int(match.group(1))
    return None


def extract_syllable_count_from_categories(text: str) -> Optional[int]:
    """
    Extract syllable count from category labels as a fallback signal.

    Example: [[Category:English 3-syllable words]] -> 3

    Note: These categories are deprecated in Wiktionary but can still provide
    a useful signal when hyphenation templates are missing.

    Args:
        text: The Wiktionary page text

    Returns:
        Number of syllables from category label, or None if not found
    """
    match = SYLLABLE_CATEGORY.search(text)
    if match:
        return int(match.group(1))
    return None


def count_syllables_from_ipa(ipa: str) -> int:
    """
    Count syllables from IPA transcription.

    Counts vowel nuclei (monophthongs and diphthongs) plus syllabic consonants.
    Handles diphthongs by only skipping high/central vowels as off-glides.

    Args:
        ipa: IPA transcription string (without surrounding slashes/brackets)

    Returns:
        Number of syllables counted
    """
    # IPA vowels (monophthongs) - includes common English vowels and variants
    vowels = set('iɪeɛæaɑɒɔoʊuʌəɜɝɐᵻᵿɚ')

    # Syllabic consonant marker (combining character U+0329)
    syllabic_marker = '\u0329'

    # Off-glide vowels (second element of diphthongs)
    offglides = set('ɪʊəɐ')

    count = 0
    chars = list(ipa)
    i = 0

    while i < len(chars):
        ch = chars[i]

        # Check for syllabic consonant (consonant followed by syllabic marker)
        if i + 1 < len(chars) and chars[i + 1] == syllabic_marker:
            count += 1
            i += 2  # Skip consonant and marker
            continue

        # Check for vowel
        if ch in vowels:
            count += 1
            i += 1

            # Skip diphthong off-glides and modifiers
            vowel_skipped = False
            while i < len(chars):
                next_ch = chars[i]
                if next_ch in ('ː', 'ˑ', '\u0303', '\u032F', '\u0361', '̯'):
                    # Length markers and diacritics
                    i += 1
                elif not vowel_skipped and next_ch in offglides:
                    # Skip off-glide vowels (second element of diphthongs)
                    vowel_skipped = True
                    i += 1
                else:
                    break
            continue

        i += 1

    return count


def extract_syllable_count_from_ipa(text: str) -> Optional[int]:
    """
    Extract syllable count from IPA transcription.

    Parses {{IPA|en|/transcription/}} templates and counts syllables
    based on vowel nuclei and syllabic consonants.

    Args:
        text: The Wiktionary page text

    Returns:
        Number of syllables if IPA found and valid, None otherwise
    """
    # Find IPA template
    match = IPA_TEMPLATE.search(text)
    if not match:
        return None

    template_content = match.group(1)

    # Extract the first transcription (between / / or [ ])
    transcription_match = IPA_TRANSCRIPTION.search(template_content)
    if not transcription_match:
        return None

    ipa = transcription_match.group(1)

    # Count syllables
    count = count_syllables_from_ipa(ipa)

    # Return None for implausible counts (0 or very high)
    if count == 0 or count > 15:
        return None

    return count


def clean_template_components(parts: List[str]) -> List[str]:
    """
    Clean template parameters to extract only morphological components.

    Filters out template metadata like gloss=, pos=, t=, alt=, language codes (grc:),
    HTML entities (<...>), and other non-morpheme content.

    Note: Wikilink handling ([[...]]) is now done by the WikitextParser during parsing,
    so this function only handles post-parsing cleanup.

    Args:
        parts: Component parts from template parsing (wikilinks already extracted)

    Returns:
        List of clean morphological components only

    Examples:
        >>> clean_template_components(['lexico-', 'pos1=prefix meaning...', '-graphy'])
        ['lexico-', '-graphy']

        >>> clean_template_components(['grc:πλαγκτός', 'drifter', '-on'])
        ['drifter', '-on']  # Excludes non-English roots

        >>> clean_template_components(['bi-', 'gloss1=two', '-illion'])
        ['bi-', '-illion']
    """
    cleaned = []

    for part in parts:
        part = part.strip()

        # Skip empty
        if not part:
            continue

        # Skip key=value parameters (t=, gloss=, pos=, alt=, id=, etc.)
        if '=' in part:
            continue

        # Skip language code prefixes (grc:, la:, ang:, etc.)
        # These indicate non-English etymological roots
        if LANG_CODE_PREFIX.match(part):
            continue

        # Decode HTML entities (&lt; -> <, &gt; -> >, &amp; -> &)
        if '&lt;' in part or '&gt;' in part or '&amp;' in part:
            part = part.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')

        # Remove HTML/XML tags and template parameters like <id:...>, <t:...>, etc.
        if '<' in part or '>' in part:
            part = HTML_ENTITY_PATTERN.sub('', part)
            # If nothing left after removing HTML, skip
            if not part:
                continue

        # Skip if it's clearly a parameter assignment we missed
        if PARAM_KEY_PATTERN.match(part):
            continue

        # Skip isolated punctuation or brackets
        if part in ['-', '|', ']]', '[[', '<', '>']:
            continue

        # Valid component - add to cleaned list
        cleaned.append(part)

    return cleaned


def classify_morphology(components: List[str], etymology_template: str) -> Dict:
    """
    Classify morphology components and build a unified Morphology result.

    Classification is purely based on hyphen patterns:
    - Ends with '-' (but doesn't start with '-'): prefix
    - Starts with '-' (but doesn't end with '-'): suffix
    - Starts and ends with '-': interfix
    - No hyphens: base word

    Args:
        components: List of cleaned morphological components
        etymology_template: Raw template string for reference

    Returns:
        Dictionary with unified morphology structure
    """
    # Classify components by hyphen pattern
    prefixes = [c for c in components if c.endswith('-') and not c.startswith('-')]
    suffixes = [c for c in components if c.startswith('-') and not c.endswith('-')]
    interfixes = [c for c in components if c.startswith('-') and c.endswith('-')]
    bases = [c for c in components if not c.startswith('-') and not c.endswith('-')]

    # Determine morphology type based on what we found
    if prefixes and suffixes:
        morph_type = 'affixed'
    elif prefixes:
        morph_type = 'prefixed'
    elif suffixes:
        morph_type = 'suffixed'
    elif len(bases) >= 2:
        morph_type = 'compound'
    else:
        morph_type = 'simple'

    # Determine base word
    # For derivations: first base word is the root
    # For compounds: no single base (all parts are equal constituents)
    is_compound = morph_type == 'compound'
    base = bases[0] if bases and not is_compound else None

    # Build result
    result = {
        'type': morph_type,
        'components': components,
        'prefixes': prefixes,
        'suffixes': suffixes,
        'is_compound': is_compound,
        'etymology_template': etymology_template
    }

    # Add optional fields only if present
    if base:
        result['base'] = base
    if interfixes:
        result['interfixes'] = interfixes

    return result


def extract_morphology_components(etymology_text: str) -> Optional[Tuple[List[str], str]]:
    """
    Extract normalized morphology components from any etymology template.

    Tries each template type in priority order and normalizes to a common
    component format where affixes are marked with hyphens.

    Templates handled (in priority order):
    1. {{suffix|en|base|suffix}} - Fixed positional args
    2. {{prefix|en|prefix|base}} - Fixed positional args
    3. {{confix|en|prefix|base|suffix}} - Fixed positional args
    4. {{compound|en|...}} - Variable args
    5. {{affix|en|...}} or {{af|en|...}} - Variable args
    6. {{surf|en|...}} - Variable args

    Args:
        etymology_text: The etymology section text to search

    Returns:
        Tuple of (components, raw_template) or None if no template found.
        Components are normalized with hyphens indicating affix type.
    """
    # 1. Try suffix template: {{suffix|en|base|suffix}}
    match = SUFFIX_TEMPLATE.search(etymology_text)
    if match:
        base = strip_wikilinks(match.group(1).strip())
        suffix = strip_wikilinks(match.group(2).strip())
        # Normalize: add leading hyphen if missing
        if not suffix.startswith('-'):
            suffix = f'-{suffix}'
        return [base, suffix], match.group(0)

    # 2. Try prefix template: {{prefix|en|prefix|base}}
    match = PREFIX_TEMPLATE.search(etymology_text)
    if match:
        prefix = strip_wikilinks(match.group(1).strip())
        base = strip_wikilinks(match.group(2).strip())
        # Normalize: add trailing hyphen if missing
        if not prefix.endswith('-'):
            prefix = f'{prefix}-'
        return [prefix, base], match.group(0)

    # 3. Try confix template: {{confix|en|prefix|base|suffix}}
    match = CONFIX_TEMPLATE.search(etymology_text)
    if match:
        prefix = strip_wikilinks(match.group(1).strip())
        base = strip_wikilinks(match.group(2).strip())
        suffix = strip_wikilinks(match.group(3).strip())
        # Normalize affix hyphens
        if not prefix.endswith('-'):
            prefix = f'{prefix}-'
        if not suffix.startswith('-'):
            suffix = f'-{suffix}'
        return [prefix, base, suffix], match.group(0)

    # 4-6. Try variable-arg templates: compound, affix, surf
    # These use parse_template_params for bracket-aware parsing
    for template_re in [COMPOUND_TEMPLATE, AFFIX_TEMPLATE, SURF_TEMPLATE]:
        match = template_re.search(etymology_text)
        if match:
            parts = parse_template_params(match.group(1))
            components = clean_template_components(parts)
            if len(components) >= 2:
                return components, match.group(0)

    return None


def extract_morphology(text: str) -> Optional[Dict]:
    """
    Extract morphological structure from Wiktionary etymology sections.

    This is the main entry point for morphology extraction. It uses a unified
    approach that:
    1. Extracts and normalizes components from any morphology template
    2. Classifies the morphology type based on hyphen patterns

    Templates parsed:
    - {{suffix|en|happy|ness}} -> happiness = happy + -ness
    - {{prefix|en|un|happy}} -> unhappy = un- + happy
    - {{affix|en|un-|break|-able}} -> unbreakable = un- + break + -able
    - {{compound|en|bar|tender}} -> bartender = bar + tender
    - {{surf|en|dict|ion|ary}} -> dictionary = dict + ion + ary (surface form)
    - {{confix|en|en-|light|ment}} -> enlightenment = en- + light + -ment

    Args:
        text: The English section of Wiktionary page text

    Returns:
        Dictionary with morphology structure, or None if no etymology data found.
        Structure:
        {
            'type': 'suffixed' | 'prefixed' | 'affixed' | 'compound' | 'circumfixed' | 'simple',
            'base': str (base word, optional - None for compounds),
            'components': [str] (all morphological parts in order),
            'prefixes': [str] (prefix morphemes with trailing hyphen),
            'suffixes': [str] (suffix morphemes with leading hyphen),
            'interfixes': [str] (interfix morphemes with leading and trailing hyphen, optional),
            'is_compound': bool,
            'etymology_template': str (raw template for reference)
        }
    """
    # Find etymology section
    etym_match = ETYMOLOGY_SECTION.search(text)
    if not etym_match:
        return None

    etymology_text = etym_match.group(1)

    # Extract and normalize components from any template type
    result = extract_morphology_components(etymology_text)
    if result is None:
        return None

    components, template_str = result

    # Special case: confix template should be classified as 'circumfixed'
    # We detect this by checking if the template is confix
    if 'confix' in template_str.lower():
        # Build circumfixed result directly
        prefix = components[0]
        base = components[1]
        suffix = components[2] if len(components) > 2 else None

        result_dict = {
            'type': 'circumfixed',
            'base': base,
            'components': components,
            'prefixes': [prefix],
            'suffixes': [suffix] if suffix else [],
            'is_compound': False,
            'etymology_template': template_str
        }
        return result_dict

    # Classify morphology based on component hyphen patterns
    return classify_morphology(components, template_str)


def extract_page_content(page_xml: str) -> Optional[tuple]:
    """
    Extract title and text from page XML using simple regex.
    Returns (title, text) or None if not found.
    Special pages (known prefixes) return ('SPECIAL_PAGE', title) even if redirects.
    Redirects return ('REDIRECT', title).
    Dictionary-only terms return ('DICT_ONLY', title, text).
    Non-English pages return ('NON_ENGLISH', title, languages) where languages is a list.
    """
    # Extract title
    title_match = TITLE_PATTERN.search(page_xml)
    if not title_match:
        return None
    title = title_match.group(1)

    # Check namespace FIRST - only process main namespace (ns=0)
    # This is the authoritative way to filter special pages
    # ns=0: Main (dictionary entries)
    # ns=14: Category
    # ns=100: Appendix
    # ns=118: Reconstruction
    # All other namespaces should be filtered out
    ns_match = NS_PATTERN.search(page_xml)
    if ns_match:
        namespace = int(ns_match.group(1))
        if namespace != 0:
            return ('SPECIAL_PAGE', title)

    # Check for special pages by title prefix (backup for entries without ns tag)
    # Special page redirects count as special pages, not redirects
    if title.startswith(SPECIAL_PAGE_PREFIXES):
        return ('SPECIAL_PAGE', title)

    # Filter translation subpages (e.g., "an/translations", "the/translations")
    # These are meta-pages that contain only translation data, not word definitions
    if '/translations' in title or '/Translations' in title:
        return ('SPECIAL_PAGE', title)

    # Check for redirects AFTER special pages
    # This catches regular redirects like "grain of salt" -> "with a grain of salt"
    if REDIRECT_PATTERN.search(page_xml):
        return ('REDIRECT', title)

    # Extract text
    text_match = TEXT_PATTERN.search(page_xml)
    if not text_match:
        return None
    text = text_match.group(1)

    # Check for English section
    has_english = ENGLISH_SECTION.search(text)

    # Check for dictionary-only terms ({{no entry|en|...)
    if has_english and DICT_ONLY.search(text):
        return ('DICT_ONLY', title, text)

    # If no English section, extract languages present
    if not has_english:
        languages = []
        for match in LANGUAGE_SECTION.finditer(text):
            lang = match.group(1).strip()
            if lang.lower() != 'english':
                languages.append(lang)
        return ('NON_ENGLISH', title, languages)

    return (title, text)


def is_englishlike(token: str) -> bool:
    """
    Returns True if `token` looks like an English-language word or phrase:
    - Uses Latin letters (ASCII or Latin diacritics in range 0x00C0-0x024F)
    - May include ASCII spaces between parts
    - May include hyphen (U+002D), en dash (U+2013),
      straight apostrophe (U+0027), left single quote (U+2018),
      right single quote (U+2019), period (U+002E),
      and slash (U+002F)
    - Rejects any string of only spaces, any non-ASCII whitespace,
      and any obvious HTML-entity-like token (&, ;, <, >)

    Note: Uses same Latin range as Rust scanner (0x00C0-0x024F) for parity.
    This covers Latin-1 Supplement, Latin Extended-A, and Latin Extended-B.
    """

    t = ud.normalize("NFC", token)

    # Reject non-ASCII whitespace except ordinary space U+0020
    if any(ch != ' ' and ch.isspace() for ch in t):
        return False

    # Reject strings that are empty or only spaces
    if t.strip() == '':
        return False

    ALLOWED_PUNCT = {"'", "'", "'", "-", "–", ".", "/"}
    FORBIDDEN = set("&;<>")

    saw_latin_letter = False

    for ch in t:
        if ch == ' ':
            continue

        if ch in FORBIDDEN:
            return False

        if ch.isascii():
            if ch.isalpha():
                saw_latin_letter = True
        else:
            # Non-ASCII character - check if it's in Latin diacritics range
            if ch.isalpha():
                cp = ord(ch)
                # Accept Latin diacritics (À-ɏ range) matching Rust scanner
                if 0x00C0 <= cp <= 0x024F:
                    saw_latin_letter = True
                else:
                    return False
            elif ch in ALLOWED_PUNCT:
                pass  # Allow punctuation
            else:
                # Reject combining diacritical marks (U+0300-U+036F) and emojis
                # to match Rust scanner behavior
                cp = ord(ch)
                if 0x0300 <= cp <= 0x036F:
                    # Combining Diacritical Marks - reject (Rust treats these
                    # as alphabetic via Unicode Alphabetic property, then rejects
                    # them for being outside Latin range)
                    return False
                if cp > 0xFFFF or (0x1F000 <= cp <= 0x1FFFF):
                    # Emojis and supplementary characters - reject
                    return False
                # Other non-alphabetic non-punctuation chars pass through

    return saw_latin_letter


def extract_phrase_type(text: str) -> Optional[str]:
    """
    Extract specific phrase type before POS normalization.

    Returns the specific type (idiom, proverb, etc.) or None if not a phrase.
    This preserves granularity lost during POS_MAP normalization.

    Distinction criteria:
    - **Word**: word_count == 1 (handled elsewhere)
    - **Idiom**: Non-literal figurative expression ("kick the bucket")
    - **Proverb**: Complete sentence with advice/wisdom ("a stitch in time saves nine")
    - **Phrase**: Generic multi-word without specific type
    - **Prepositional phrase**: Starts with preposition ("at least", "on hold")
    - **Adverbial phrase**: Functions as adverb ("all of a sudden")
    - **Verb phrase**: Multi-word verb expression ("give up", "take over")

    Detection methods:
    1. Section headers: ===Idiom===, ===Proverb===, etc.
    2. Templates: {{head|en|idiom}}, {{en-prepphr}}
    3. Categories: [[Category:English idioms]], etc.
    """
    # Check section headers for specific phrase types
    for match in POS_HEADER.finditer(text):
        header = match.group(1).lower().strip()
        header = ' '.join(header.split())  # Normalize whitespace

        # Exact matches for phrase types
        if header in ['idiom', 'proverb', 'prepositional phrase', 'adverbial phrase',
                      'verb phrase', 'verb phrase form', 'noun phrase']:
            return header

        # Additional phrase type variations
        if header in ['saying', 'adage']:
            return 'proverb'  # Sayings/adages are proverb-like

    # Check {{head}} templates using proper bracket-aware parsing
    for pos in find_head_template_pos_values(text):
        if pos in ['idiom', 'proverb', 'prepositional phrase', 'adverbial phrase',
                   'verb phrase', 'noun phrase', 'saying', 'adage']:
            return 'proverb' if pos in ['saying', 'adage'] else pos

    # Check for phrase-specific templates
    if PREP_PHRASE_TEMPLATE.search(text):
        return 'prepositional phrase'

    # Check categories (more comprehensive)
    category_patterns = {
        'Category:English idioms': 'idiom',
        'Category:English proverbs': 'proverb',
        'Category:English prepositional phrases': 'prepositional phrase',
        'Category:English adverbial phrases': 'adverbial phrase',
        'Category:English verb phrases': 'verb phrase',
        'Category:English noun phrases': 'noun phrase',
        'Category:English sayings': 'proverb',
    }

    for pattern, phrase_type in category_patterns.items():
        if pattern in text:
            return phrase_type

    return None


def detect_abbreviation(text: str, pos_tags: List[str]) -> bool:
    """
    Detect if entry is an abbreviation.

    Detection methods:
    1. Templates: {{abbr of|en|...}}, {{abbreviation of|en|...}}, {{initialism of|en|...}}
    2. Categories: [[Category:English abbreviations]], etc. (actual membership)
    3. POS: symbol (often abbreviations)

    Note: We check for '[[Category:' (without colon prefix) to avoid false positives
    from category links like '[[:Category:English acronyms|...]]' which are just
    links to the category page, not actual membership. The word "acronym" was
    incorrectly flagged before this fix because it links to the acronyms category.

    Examples: USA, Dr., etc., crp (stenoscript)
    """
    # Check templates
    if ABBREVIATION_TEMPLATE.search(text):
        return True

    # Check categories - use [[Category: prefix to distinguish from [[:Category: links
    # [[Category:X]] = membership in category X
    # [[:Category:X]] = link to category X (not membership)
    if '[[Category:English abbreviations' in text:
        return True
    if '[[Category:English initialisms' in text:
        return True
    if '[[Category:English acronyms' in text:
        return True
    if '[[Category:English Stenoscript abbreviations' in text:
        return True

    # Symbol POS is often used for abbreviations
    if 'symbol' in pos_tags:
        return True

    return False


def detect_proper_noun(text: str, pos_tags: List[str]) -> bool:
    """
    Detect if entry is a proper noun (name, place, etc.).

    Detection methods:
    1. POS: proper noun mapped to 'noun' in POS_MAP
    2. Section header: ===Proper noun===
    3. Templates: {{en-proper noun}}, {{en-prop}}

    Examples: London, Shakespeare, Microsoft
    """
    # Check for proper noun section header
    for match in POS_HEADER.finditer(text):
        header = match.group(1).lower().strip()
        header = ' '.join(header.split())
        if header in ['proper noun', 'proper name', 'propernoun']:
            return True

    # Check for proper noun templates
    if re.search(r'\{\{en-(?:proper noun|prop)\b', text, re.IGNORECASE):
        return True

    return False


def detect_vulgar_or_offensive(labels: Dict) -> bool:
    """
    Detect if entry is vulgar or offensive.

    Uses label data already extracted.
    Examples: profanity, slurs, offensive terms
    """
    register = labels.get('register', [])
    return 'vulgar' in register or 'offensive' in register


def detect_archaic_or_obsolete(labels: Dict) -> bool:
    """
    Detect if entry is archaic or obsolete.

    Uses label data already extracted.
    Examples: thou, whence, forsooth
    """
    temporal = labels.get('temporal', [])
    return 'archaic' in temporal or 'obsolete' in temporal


def detect_rare(labels: Dict) -> bool:
    """
    Detect if entry is marked as rare.

    Uses label data already extracted.
    """
    temporal = labels.get('temporal', [])
    return 'rare' in temporal


def detect_informal_or_slang(labels: Dict) -> bool:
    """
    Detect if entry is informal or slang.

    Uses label data already extracted.
    Examples: gonna, wanna, ain't
    """
    register = labels.get('register', [])
    return 'informal' in register or 'slang' in register or 'colloquial' in register


def detect_technical(labels: Dict) -> bool:
    """
    Detect if entry is technical/domain-specific jargon.

    Uses domain labels already extracted.
    Examples: mitochondria (biology), tort (law), algorithm (computing)

    Useful for: Filtering out specialized terminology for general-purpose
    dictionaries vs keeping it for domain-specific applications.
    """
    domain = labels.get('domain', [])
    # Technical if it has ANY domain label (medical, legal, computing, etc.)
    return len(domain) > 0


def detect_regional(labels: Dict) -> bool:
    """
    Detect if entry is region-specific (dialectal).

    Uses region labels already extracted.
    Examples: lift (British), elevator (American), arvo (Australian)

    Useful for: Dictionary localization and dialect-aware applications.
    """
    region = labels.get('region', [])
    return len(region) > 0


def detect_inflected_form(text: str, pos_tags: List[str]) -> bool:
    """
    Detect if entry is an inflected form rather than a base word.

    Detection methods:
    1. Templates: {{plural of|en|...}}, {{past tense of|en|...}}, etc.
    2. POS categories indicating forms: "verb forms", "noun forms", etc.

    Examples: cats (plural of cat), ran (past tense of run), better (comparative of good)

    Useful for: Base-word-only dictionaries, lemmatization, reducing redundancy.
    """
    # Check for inflection templates
    inflection_patterns = [
        r'\{\{plural of\|en\|',
        r'\{\{past tense of\|en\|',
        r'\{\{past participle of\|en\|',
        r'\{\{present participle of\|en\|',
        r'\{\{comparative of\|en\|',
        r'\{\{superlative of\|en\|',
        r'\{\{inflection of\|en\|',
    ]

    for pattern in inflection_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    # Check for form categories
    form_categories = [
        'Category:English verb forms',
        'Category:English noun forms',
        'Category:English adjective forms',
        'Category:English adverb forms',
        'Category:English plurals',
    ]

    for category in form_categories:
        if category in text:
            return True

    return False


def clean_lemma(raw: str) -> str:
    """
    Clean wiki markup from extracted lemma.

    Removes section anchors (#...), wiki links ([[...]]), and templates ({{...}}).
    This handles malformed Wiktionary template content that leaks into lemma values.

    Args:
        raw: Raw lemma string potentially containing wiki markup

    Returns:
        Cleaned lemma string

    Examples:
        "after#noun" → "after"
        "[[rhodologist]]" → "rhodologist"
        "[[:en:word]]" → "word"
        "germanic {{italic" → "germanic"
        "read -> [[#etymology 1" → "read"
    """
    result = raw

    # Remove section anchors (e.g., "after#noun" -> "after")
    if '#' in result:
        result = result.split('#')[0]

    # Remove wiki link syntax: [[target]] or [[target|display]] or [[:en:target]]
    while '[[' in result:
        start = result.find('[[')
        end = result.find(']]', start)
        if end != -1:
            link_content = result[start + 2:end]
            # Handle [[target|display]] - extract target
            if '|' in link_content:
                cleaned = link_content.split('|')[0]
            else:
                cleaned = link_content
            # Handle [[:en:word]] - strip leading colon and namespace
            cleaned = cleaned.lstrip(':')
            if ':' in cleaned:
                cleaned = cleaned.rsplit(':', 1)[-1]
            result = result[:start] + cleaned + result[end + 2:]
        else:
            # Malformed (no closing ]]) - remove from [[ to end
            result = result[:start]
    result = result.replace(']]', '')

    # Remove template syntax {{...}}
    while '{{' in result:
        start = result.find('{{')
        end = result.find('}}', start)
        if end != -1:
            result = result[:start] + result[end + 2:]
        else:
            # Malformed (no closing }}) - remove from {{ to end
            result = result[:start]
    result = result.replace('}}', '')
    result = result.replace('//', '')

    return result.strip()


def extract_lemma(text: str) -> Optional[str]:
    """
    Extract lemma (base form) from inflection templates.

    Searches for templates like {{plural of|en|cat}} and extracts "cat" as the lemma.
    Returns the first matching lemma found, or None if no inflection template found.

    Args:
        text: The English section of Wiktionary page text

    Returns:
        The lemma (base form) string, or None if not an inflected form

    Examples:
        "{{plural of|en|cat}}" → "cat"
        "{{past tense of|en|run}}" → "run"
        "{{inflection of|en|go||past|part}}" → "go"
    """
    for template_name, pattern in INFLECTION_TEMPLATES:
        match = pattern.search(text)
        if match:
            raw_lemma = match.group(1).strip()
            lemma = clean_lemma(raw_lemma).lower()
            # Validate the lemma is reasonable (non-empty and English-like)
            if lemma and is_englishlike(lemma):
                return lemma
    return None


def detect_dated(labels: Dict) -> bool:
    """
    Detect if entry is dated (understood but not commonly used).

    Different from archaic - dated words are still understood but old-fashioned.
    Examples: wireless (for radio), icebox (for refrigerator)

    Useful for: More granular temporal filtering than archaic/obsolete.
    """
    temporal = labels.get('temporal', [])
    return 'dated' in temporal


def detect_derogatory(labels: Dict) -> bool:
    """
    Detect if entry is derogatory (disparaging or offensive in certain contexts).

    Different from vulgar - derogatory terms may be offensive due to context
    rather than profanity. Especially important for ethnic slurs, demeaning terms.
    Examples: taffy (UK derogatory term for Welsh), various ethnic slurs

    Useful for: Content filtering, especially for educational or public-facing
    applications where context-dependent offensive terms need separate handling.
    """
    register = labels.get('register', [])
    return 'derogatory' in register


def has_english_categories(text: str) -> bool:
    """
    Check if the text contains English POS categories.

    This validates that a page is actually an English entry, not just a page
    with an English section. Filters out foreign words like 'łódź' that may
    have an English section but no English POS categories.

    Returns True if any English POS categories are found.
    """
    # Common English POS categories
    english_pos_patterns = [
        'Category:English nouns',
        'Category:English verbs',
        'Category:English adjectives',
        'Category:English adverbs',
        'Category:English pronouns',
        'Category:English prepositions',
        'Category:English conjunctions',
        'Category:English interjections',
        'Category:English determiners',
        'Category:English articles',
        'Category:English proper nouns',
        'Category:English idioms',
        'Category:English phrases',
        'Category:English proverbs',
        'Category:English prepositional phrases',
        'Category:English verb forms',
        'Category:English noun forms',
        'Category:English adjective forms',
        'Category:English adverb forms',
        'Category:English contractions',
        'Category:English abbreviations',
    ]

    text_lower = text.lower()
    return any(pattern.lower() in text_lower for pattern in english_pos_patterns)


# Pattern to extract {{tlb|en|...}} or {{lb|en|...}} from text
TLB_TEMPLATE = re.compile(r'\{\{(?:tlb|lb)\|en\|([^}]+)\}\}', re.IGNORECASE)

# SPELLING_LABELS is loaded from schema/labels.yaml at module initialization


def extract_spelling_region(text: str) -> Optional[str]:
    """
    Extract regional spelling variant from the page text.
    Returns region code like "en-US" or "en-GB" if found.

    Searches through {{tlb|en|...}} and {{lb|en|...}} templates,
    checking each label within the template for spelling variants.
    """
    for match in TLB_TEMPLATE.finditer(text):
        # Get all labels in this template
        for label in match.group(1).split('|'):
            label = label.strip().lower()
            # Check if this is a spelling variant label
            if label in SPELLING_LABELS:
                return SPELLING_LABELS[label]
    return None


def build_ordered_entry(
    word: str,
    pos: str,
    word_count: int,
    is_abbreviation: bool,
    is_inflected: bool,
    is_phrase: bool,
    syllables: Optional[int] = None,
    phrase_type: Optional[str] = None,
    lemma: Optional[str] = None,
    domain_tags: Optional[List[str]] = None,
    region_tags: Optional[List[str]] = None,
    register_tags: Optional[List[str]] = None,
    temporal_tags: Optional[List[str]] = None,
    spelling_region: Optional[str] = None,
    morphology: Optional[Dict] = None,
) -> Dict:
    """
    Build an entry dict with normalized field order for consistent JSON output.

    Field order:
    1. word, pos, word_count (core identifiers)
    2. is_abbreviation, is_inflected, is_phrase (if true - false is default, omitted)
    3. syllables (if present)
    4. phrase_type (if present)
    5. lemma (if present)
    6. domain_tags, region_tags, register_tags, temporal_tags (if present)
    7. spelling_region (if present)
    8. morphology (if present)
    """
    entry = {}

    # Core fields (always present)
    entry['word'] = word
    entry['pos'] = pos
    entry['word_count'] = word_count

    # Boolean predicates (omit when false - false is the default)
    if is_abbreviation:
        entry['is_abbreviation'] = True
    if is_inflected:
        entry['is_inflected'] = True
    if is_phrase:
        entry['is_phrase'] = True

    # Optional fields in specified order
    if syllables is not None:
        entry['syllables'] = syllables
    if phrase_type is not None:
        entry['phrase_type'] = phrase_type
    if lemma is not None:
        entry['lemma'] = lemma

    # Tag arrays
    if domain_tags:
        entry['domain_tags'] = domain_tags
    if region_tags:
        entry['region_tags'] = region_tags
    if register_tags:
        entry['register_tags'] = register_tags
    if temporal_tags:
        entry['temporal_tags'] = temporal_tags

    # Remaining optional fields
    if spelling_region is not None:
        entry['spelling_region'] = spelling_region
    if morphology is not None:
        entry['morphology'] = morphology

    return entry


def parse_entry(title: str, text: str) -> List[Dict]:
    """
    Parse a single Wiktionary page and return multiple entries (one per sense).

    Critical: Extracts ONLY the ==English== section before parsing to prevent
    contamination from other language sections (French, Translingual, etc.).

    Returns a list of Entry dicts, one for each (POS, definition) pair.
    Each entry has: word, pos (string, 'proper' for proper nouns), register_tags,
    region_tags, domain_tags, temporal_tags, spelling_region, word_count, is_phrase,
    is_abbreviation, is_inflected, lemma, phrase_type, syllables, morphology.
    """
    # Preserve original case - downstream consumers can filter by case pattern as needed
    word = title.strip()

    # CRITICAL: Extract ONLY the ==English== section
    # This prevents contamination from other language sections
    english_text = extract_english_section(text)
    if not english_text:
        return []  # No English section found

    # Extract word-level data (shared across all senses)
    word_count = len(word.split())
    phrase_type = extract_phrase_type(english_text) if word_count > 1 else None

    # Extract syllable count from multiple sources
    # Priority order: rhymes (explicit) > IPA (parsed) > categories > hyphenation (least reliable)
    rhymes_count = extract_syllable_count_from_rhymes(english_text)
    ipa_count = extract_syllable_count_from_ipa(english_text)
    cat_count = extract_syllable_count_from_categories(english_text)
    hyph_count = extract_syllable_count_from_hyphenation(english_text, word)

    syllable_count = None
    if rhymes_count is not None:
        syllable_count = rhymes_count
    elif ipa_count is not None:
        syllable_count = ipa_count
    elif cat_count is not None:
        syllable_count = cat_count
    elif hyph_count is not None:
        syllable_count = hyph_count

    # Extract morphology from etymology section
    morphology = extract_morphology(english_text)

    # Detect word-level properties
    is_abbreviation = detect_abbreviation(english_text, [])

    # Extract lemma from inflection templates
    lemma = extract_lemma(english_text)

    # Mark as inflected if we found a lemma OR if category indicates inflection
    is_inflected = lemma is not None or detect_inflected_form(english_text, [])

    # Extract regional spelling variant
    spelling_region = extract_spelling_region(english_text)

    # Word-level data shared across all senses
    word_data = {
        'word': word,
        'word_count': word_count,
        'is_phrase': word_count > 1,
        'is_abbreviation': is_abbreviation,
        'is_inflected': is_inflected,
    }

    # Add optional word-level fields
    if lemma:
        word_data['lemma'] = lemma
    if phrase_type:
        word_data['phrase_type'] = phrase_type
    if syllable_count is not None:
        word_data['syllables'] = syllable_count
    if morphology:
        word_data['morphology'] = morphology
    if spelling_region:
        word_data['spelling_region'] = spelling_region

    # Parse POS sections and their definitions
    pos_sections = parse_pos_sections(english_text)

    # If no POS sections found, try to create a single entry with unknown POS
    if not pos_sections:
        # Check for English categories or templates as validation
        has_categories = has_english_categories(english_text)
        has_en_templates = bool(re.search(r'\{\{en-(?:noun|verb|adj|adv)', english_text))
        has_definition_templates = bool(DEFINITION_TEMPLATES.search(english_text))

        if has_categories or has_en_templates or has_definition_templates:
            # Create a single entry with unknown POS using ordered builder
            entry = build_ordered_entry(
                word=word,
                pos='unknown',
                word_count=word_data['word_count'],
                is_abbreviation=word_data['is_abbreviation'],
                is_inflected=word_data['is_inflected'],
                is_phrase=word_data['is_phrase'],
                syllables=word_data.get('syllables'),
                phrase_type=word_data.get('phrase_type'),
                lemma=word_data.get('lemma'),
                spelling_region=word_data.get('spelling_region'),
                morphology=word_data.get('morphology'),
            )
            return [entry]
        return []

    # Create one entry per definition
    entries = []

    for section in pos_sections:
        for def_line in section.definitions:
            register_tags, region_tags, domain_tags, temporal_tags = extract_labels_from_line(def_line)

            # Use ordered builder for consistent field order
            entry = build_ordered_entry(
                word=word,
                pos=section.pos,
                word_count=word_data['word_count'],
                is_abbreviation=word_data['is_abbreviation'],
                is_inflected=word_data['is_inflected'],
                is_phrase=word_data['is_phrase'],
                syllables=word_data.get('syllables'),
                phrase_type=word_data.get('phrase_type'),
                lemma=word_data.get('lemma'),
                domain_tags=domain_tags if domain_tags else None,
                region_tags=region_tags if region_tags else None,
                register_tags=register_tags if register_tags else None,
                temporal_tags=temporal_tags if temporal_tags else None,
                spelling_region=word_data.get('spelling_region'),
                morphology=word_data.get('morphology'),
            )

            entries.append(entry)

    return entries


# Layout for status display (label, value) pairs
PAIRS_LAYOUT = [
    # each row contains up to three (label, key) pairs
    [("Processed", "Processed"), ("Words", "Words"), ("Senses", "Senses")],
    [("Special", "Special"), ("Redirects", "Redirects"), ("Dict-only", "Dict-only")],
    [("Non-EN", "Non-EN"), ("Non-Latin", "Non-Latin"), ("Skipped", "Skipped")],
    [("Rate", "Rate"), ("Decomp MB", "Decomp MB"), ("Elapsed", "Elapsed")],
]


def fmt(name: str, value) -> str:
    """Format metric value based on field name."""
    if name == "Rate":
        return f"{int(value):>10,} pg/s"
    elif name == "Decomp Rate":
        return f"{value:>10.1f} MB/s"
    elif name == "Elapsed":
        # value is seconds, format as mm:ss or hh:mm:ss
        mins = int(value // 60)
        secs = int(value % 60)
        if mins >= 60:
            hours = mins // 60
            mins = mins % 60
            return f"{hours:>6}h {mins:02}m"
        return f"{mins:>9}m {secs:02}s"
    return f"{value:>10,}"


def make_form(metrics: dict) -> Panel:
    """Create a Rich panel with grid layout for live progress display."""
    grid = Table.grid(padding=(0, 4))
    # six columns: label,value x3
    grid.add_column(justify="left",  no_wrap=True)  # L1
    grid.add_column(justify="right", no_wrap=True)  # V1
    grid.add_column(justify="left",  no_wrap=True)  # L2
    grid.add_column(justify="right", no_wrap=True)  # V2
    grid.add_column(justify="left",  no_wrap=True)  # L3
    grid.add_column(justify="right", no_wrap=True)  # V3

    for row in PAIRS_LAYOUT:
        cells = []
        for label, key in row:
            if label is None:
                cells += ["", ""]
            else:
                cells += [Text(f"{label}:", style="bold grey50"), Text(fmt(label, metrics[key]), style="bright_cyan")]
        grid.add_row(*cells)

    return Panel(grid, title="Status", box=box.SIMPLE, border_style="bright_black")


def scan_pages(file_obj, chunk_size: int = 1024 * 1024):
    """
    Scan for <page> boundaries and yield complete page XML.

    This is much faster than ET.iterparse() because:
    - No XML DOM building
    - No namespace handling
    - No validation
    - Simple string scanning
    """
    buffer = ""
    page_start_marker = "<page>"
    page_end_marker = "</page>"

    while True:
        # Read chunk
        chunk = file_obj.read(chunk_size)
        if not chunk:
            break

        # Decode to string
        try:
            buffer += chunk.decode('utf-8')
        except UnicodeDecodeError:
            buffer += chunk.decode('utf-8', errors='ignore')

        # Find complete pages in buffer
        while True:
            start = buffer.find(page_start_marker)
            if start == -1:
                # No page start found, keep last bit in case it's partial
                buffer = buffer[-len(page_start_marker):]
                break

            end = buffer.find(page_end_marker, start)
            if end == -1:
                # Page incomplete, keep from start
                buffer = buffer[start:]
                break

            # Extract complete page (include closing tag)
            end += len(page_end_marker)
            page_xml = buffer[start:end]
            buffer = buffer[end:]

            yield page_xml


def parse_wiktionary_dump(xml_path: Path, output_path: Path, limit: int = None, diagnostic_file: Optional[Path] = None):
    """Parse Wiktionary XML dump using lightweight scanning."""

    print(f"Parsing: {xml_path}")
    print(f"Output: {output_path}")
    print(f"Method: Lightweight scanner (no full XML parsing)")
    if limit:
        print(f"Limit: {limit:,} entries")
    if diagnostic_file:
        print(f"Diagnostic mode: Will stop after 100 skips and write report to {diagnostic_file}")
    print()

    # Prepare skip log file (always write, regardless of diagnostic mode)
    skip_log_path = output_path.parent / "wikt_skipped_pages.jsonl"
    skip_log = open(skip_log_path, 'w', encoding='utf-8')

    # Prepare metrics dictionary for Live display
    metrics = {
        "Processed": 0,
        "Words": 0,
        "Senses": 0,
        "Special": 0,
        "Redirects": 0,
        "Dict-only": 0,
        "Non-EN": 0,
        "Non-Latin": 0,
        "Skipped": 0,
        "Rate": 0,
        "Decomp MB": 0,
        "Decomp Rate": 0.0,
        "Elapsed": 0.0
    }

    if str(xml_path).endswith('.bz2'):
        file_obj = BZ2StreamReader(xml_path, chunk_size=256 * 1024, metrics=metrics)
    else:
        file_obj = open(xml_path, 'rb')

    entries_processed = 0
    words_written = 0
    senses_written = 0
    entries_skipped = 0
    special_pages_found = 0
    redirects_found = 0
    dict_only_found = 0  # Track dictionary-only terms
    non_english_found = 0  # Track non-English pages
    non_englishlike_found = 0  # Non-Latin scripts (Greek, Cyrillic, Arabic, Braille, etc.)
    first_page_seen = False

    # Track languages encountered in non-English pages
    language_counts = {}

    # Diagnostic tracking (special pages, redirects, dict-only, non-English, non-Englishlike not included)
    skip_reasons = {
        'no_content_extracted': [],  # extract_page_content returned None
        'parse_entry_none': [],      # parse_entry returned None
        'parse_entry_exception': []  # parse_entry threw exception
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    diagnostic_mode = diagnostic_file is not None

    with file_obj as f, open(output_path, 'w', encoding='utf-8') as out:
        # Use Rich Live display for progress
        with Live(make_form(metrics), refresh_per_second=10) as live:
            # Scan for pages (much faster than XML parsing)
            for page_xml in scan_pages(f, chunk_size=1024 * 1024):
                entries_processed += 1
                metrics["Processed"] = entries_processed

                if not first_page_seen:
                    first_page_seen = True
                    # No need to finish progress - it's in the Live display now

                # Extract title and text using simple regex
                result = extract_page_content(page_xml)
                if not result:
                    entries_skipped += 1
                    metrics["Skipped"] = entries_skipped

                    # Log to skip file
                    title_match = TITLE_PATTERN.search(page_xml)
                    title = title_match.group(1) if title_match else "NO_TITLE"
                    skip_log.write(json.dumps({
                        'reason': 'no_content_extracted',
                        'title': title,
                        'page_xml': page_xml
                    }, ensure_ascii=False) + '\n')
                    skip_log.flush()

                    if diagnostic_mode:
                        skip_reasons['no_content_extracted'].append({
                            'title': title,
                            'page_preview': page_xml[:500]
                        })

                    # Check diagnostic stop condition
                    if diagnostic_mode and entries_skipped >= 100:
                        break
                    continue

                # Handle special pages (known prefixes - expected, no diagnostic needed)
                if result[0] == 'SPECIAL_PAGE':
                    special_pages_found += 1
                    metrics["Special"] = special_pages_found
                    continue

                # Handle redirects (expected, tracked separately)
                if result[0] == 'REDIRECT':
                    redirects_found += 1
                    metrics["Redirects"] = redirects_found
                    continue

                # Handle dictionary-only terms ({{no entry|en|...)
                if result[0] == 'DICT_ONLY':
                    dict_only_found += 1
                    metrics["Dict-only"] = dict_only_found
                    continue

                # Handle non-English pages (track languages)
                if result[0] == 'NON_ENGLISH':
                    non_english_found += 1
                    metrics["Non-EN"] = non_english_found
                    _, title, languages = result
                    for lang in languages:
                        language_counts[lang] = language_counts.get(lang, 0) + 1
                    continue

                title, text = result

                # Check if word uses English-like character set (Latin script)
                # This filters out Greek, Cyrillic, Arabic, Braille, CJK, etc.
                if not is_englishlike(title):
                    non_englishlike_found += 1
                    metrics["Non-Latin"] = non_englishlike_found
                    continue

                # Parse entry (returns list of entries, one per sense)
                try:
                    entries_list = parse_entry(title, text)
                    if entries_list:
                        # Track as one word written, multiple senses
                        words_written += 1
                        metrics["Words"] = words_written
                        limit_reached = False
                        for entry in entries_list:
                            out.write(json.dumps(entry, ensure_ascii=False) + '\n')
                            senses_written += 1
                            metrics["Senses"] = senses_written
                            # Check limit after each sense (matches Rust scanner precision)
                            if limit and senses_written >= limit:
                                print(f"\nReached limit of {limit:,} senses")
                                limit_reached = True
                                break
                        if limit_reached:
                            break
                    else:
                        entries_skipped += 1
                        metrics["Skipped"] = entries_skipped

                        # Log to skip file
                        skip_log.write(json.dumps({
                            'reason': 'parse_entry_none',
                            'title': title,
                            'text': text
                        }, ensure_ascii=False) + '\n')
                        skip_log.flush()

                        if diagnostic_mode:
                            skip_reasons['parse_entry_none'].append({
                                'title': title,
                                'text_preview': text[:500] if len(text) > 500 else text
                            })

                        # Check diagnostic stop condition
                        if diagnostic_mode and entries_skipped >= 100:
                            break
                except Exception as e:
                    entries_skipped += 1
                    metrics["Skipped"] = entries_skipped

                    # Log to skip file
                    skip_log.write(json.dumps({
                        'reason': 'parse_entry_exception',
                        'title': title,
                        'exception': str(e),
                        'text': text
                    }, ensure_ascii=False) + '\n')
                    skip_log.flush()

                    if diagnostic_mode:
                        skip_reasons['parse_entry_exception'].append({
                            'title': title,
                            'exception': str(e),
                            'text_preview': text[:500] if len(text) > 500 else text
                        })

                    # Check diagnostic stop condition
                    if diagnostic_mode and entries_skipped >= 100:
                        break

                # Update rate and refresh Live display
                if entries_processed % 1000 == 0:
                    elapsed = time.time() - start_time
                    rate = entries_processed / elapsed if elapsed > 0 else 0
                    metrics["Rate"] = rate
                    metrics["Elapsed"] = elapsed
                    live.update(make_form(metrics))
                    if entries_processed % 5000 == 0:
                        out.flush()

    # Close skip log file
    skip_log.close()

    elapsed = time.time() - start_time
    elapsed_min = int(elapsed / 60)
    elapsed_sec = int(elapsed % 60)

    # Summary to stdout (matches Rust scanner output format)
    print()
    print("=" * 60)
    print(f"Pages processed: {entries_processed:,}")
    print(f"Words written: {words_written:,}")
    print(f"Senses written: {senses_written:,}")
    print(f"Avg senses/word: {senses_written / max(words_written, 1):.2f}")
    print(f"Special pages: {special_pages_found:,}")
    print(f"Redirects: {redirects_found:,}")
    print(f"Dictionary-only terms: {dict_only_found:,}")
    print(f"Non-English pages: {non_english_found:,}")
    print(f"Non-Latin scripts: {non_englishlike_found:,}")
    print(f"Skipped: {entries_skipped:,}")
    print(f"Time: {elapsed_min}m {elapsed_sec}s")
    print(f"Rate: {entries_processed / elapsed:.0f} pages/sec")
    print("=" * 60)

    # Report skip log location
    if entries_skipped > 0:
        print(f"\nSkipped pages logged to: {skip_log_path}")
        print(f"Review with: cat {skip_log_path} | jq .")

    # Write diagnostic information to file if in diagnostic mode
    if diagnostic_mode:
        diagnostic_file.parent.mkdir(parents=True, exist_ok=True)
        with open(diagnostic_file, 'w', encoding='utf-8') as diag:
            # Helper function to write to file
            def write(text=""):
                diag.write(text + "\n")

            # Write aggregate results at the top
            write("=" * 60)
            write("AGGREGATE RESULTS")
            write("=" * 60)
            write()
            write(f"Pages processed: {entries_processed:,}")
            write(f"Words written: {words_written:,}")
            write(f"Senses written: {senses_written:,}")
            write(f"Avg senses/word: {senses_written / max(words_written, 1):.2f}")
            write(f"Special pages: {special_pages_found:,}")
            write(f"Redirects: {redirects_found:,}")
            write(f"Dictionary-only terms: {dict_only_found:,}")
            write(f"Non-English pages: {non_english_found:,}")
            write(f"Non-Latin scripts: {non_englishlike_found:,}")
            write(f"Skipped: {entries_skipped:,}")
            write(f"Time: {elapsed_min}m {elapsed_sec}s")
            write(f"Rate: {entries_processed / elapsed:.0f} pages/sec")
            write("=" * 60)
            write()
            write()

            write("=" * 60)
            write("DIAGNOSTIC REPORT: Skip Reasons Breakdown")
            write("=" * 60)
            write()

            # Count skip reasons
            total_no_content = len(skip_reasons['no_content_extracted'])
            total_parse_none = len(skip_reasons['parse_entry_none'])
            total_exceptions = len(skip_reasons['parse_entry_exception'])

            write(f"Skip reason counts (showing first 10 and last 10 samples):")
            write(f"  1. No content extracted (no title/text or not English): {total_no_content} samples")
            write(f"  2. parse_entry returned None (validation failed): {total_parse_none} samples")
            write(f"  3. parse_entry threw exception: {total_exceptions} samples")
            write()
            write(f"Note: Special pages ({', '.join(SPECIAL_PAGE_PREFIXES)}), redirects,")
            write(f"      dictionary-only terms, non-English pages, and non-Latin scripts are")
            write(f"      counted separately, not included in diagnostic samples.")
            write()

            # Language statistics for non-English pages
            if language_counts:
                write("-" * 60)
                write("NON-ENGLISH PAGE STATISTICS")
                write("-" * 60)
                write()
                write(f"Total non-English pages: {non_english_found:,}")
                write()
                write("Top 20 languages by page count:")
                sorted_langs = sorted(language_counts.items(), key=lambda x: x[1], reverse=True)
                for i, (lang, count) in enumerate(sorted_langs[:20], 1):
                    write(f"  {i:2}. {lang:20} {count:6,} pages")
                write()
                if len(sorted_langs) > 20:
                    write(f"  ... and {len(sorted_langs) - 20} more languages")
                write()
                write(f"Total unique languages: {len(language_counts):,}")
                write()

            # Print samples for each category (first 10 and last 10)
            def write_samples(category_name, samples, has_exception=False):
                """Helper to write first 10 and last 10 samples."""
                if not samples:
                    return

                write("-" * 60)
                write(f"SAMPLES: {category_name}")
                write("-" * 60)

                # Show first 10
                first_samples = samples[:10]
                for i, sample in enumerate(first_samples, 1):
                    write(f"\n{i}. Title: {sample['title']}")
                    if has_exception:
                        write(f"   Exception: {sample['exception']}")
                    if 'page_preview' in sample:
                        write(f"   Page preview (first 500 chars):")
                        write(f"   {sample['page_preview'][:500]}")
                    elif 'text_preview' in sample:
                        write(f"   Text preview (first 500 chars):")
                        write(f"   {sample['text_preview'][:500]}")
                    write()

                # Show last 10 if we have more than 10 samples
                if len(samples) > 10:
                    if len(samples) > 20:
                        write(f"... ({len(samples) - 20} samples omitted) ...")
                        write()

                    last_samples = samples[-10:]
                    start_idx = len(samples) - 10 + 1
                    for i, sample in enumerate(last_samples, start_idx):
                        write(f"\n{i}. Title: {sample['title']}")
                        if has_exception:
                            write(f"   Exception: {sample['exception']}")
                        if 'page_preview' in sample:
                            write(f"   Page preview (first 500 chars):")
                            write(f"   {sample['page_preview'][:500]}")
                        elif 'text_preview' in sample:
                            write(f"   Text preview (first 500 chars):")
                            write(f"   {sample['text_preview'][:500]}")
                        write()

            write_samples("No content extracted", skip_reasons['no_content_extracted'])
            write_samples("parse_entry returned None", skip_reasons['parse_entry_none'])
            write_samples("parse_entry threw exception", skip_reasons['parse_entry_exception'], has_exception=True)

            write("=" * 60)
            write("GOAL: Reach fixed point (no samples in any category)")
            write("=" * 60)
            write()
            write("Action items based on samples:")
            write()
            write("1. 'no_content_extracted' samples:")
            write("   - Look for unknown special page prefixes (add to SPECIAL_PAGE_PREFIXES)")
            write("   - Check for pages with ':' that aren't English words (e.g., 'talk:', 'user:')")
            write("   - Identify any regex pattern issues")
            write()
            write("2. 'parse_entry_none' samples:")
            write("   - Check if missing POS tags for valid entries")
            write("   - Check for character validation issues")
            write("   - Identify entries that should be extracted")
            write()
            write("3. 'parse_entry_exception' samples:")
            write("   - Fix code bugs causing exceptions")
            write("   - Add error handling for edge cases")
            write()
            write("Fixed point achieved when all sample lists are empty!")
            write("=" * 60)

        print(f"\nDiagnostic report written to: {diagnostic_file}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Fast scanner-based Wiktionary XML parser (no full XML parsing)'
    )

    parser.add_argument(
        'input',
        type=Path,
        help='Input XML file (.xml or .xml.bz2)'
    )

    parser.add_argument(
        'output',
        type=Path,
        help='Output JSONL file'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit number of entries to extract (for testing)'
    )

    parser.add_argument(
        '--diagnostic',
        type=Path,
        default=None,
        metavar='FILE',
        help='Diagnostic mode: stop after 100 skips and write report to FILE'
    )

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)

    parse_wiktionary_dump(args.input, args.output, args.limit, args.diagnostic)


if __name__ == '__main__':
    main()
