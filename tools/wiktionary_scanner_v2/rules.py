"""
Rule engine for v2 scanner.

This module converts Evidence objects to Entry objects using BindingConfig
lookups. It's the bridge between raw Wiktionary signals and normalized codes.

Architecture:
    Evidence (raw signals) + BindingConfig (lookups) → Entry (normalized codes)
"""

import re
import unicodedata as ud
from dataclasses import dataclass, field
from typing import Optional

from .cdaload import BindingConfig
from .evidence import Evidence, Template


# =============================================================================
# Entry dataclass (v2 output format)
# =============================================================================


@dataclass
class Morphology:
    """Structured morphology for v2 Entry."""

    type: str  # 4-letter code: SIMP, COMP, PREF, SUFF, AFFX, CIRC
    components: list[str] = field(default_factory=list)
    base: Optional[str] = None
    prefixes: list[str] = field(default_factory=list)
    suffixes: list[str] = field(default_factory=list)


@dataclass
class Entry:
    """
    v2 Entry format - compact and code-based.

    All boolean flags, tags, and phrase types are collapsed into `codes` set.
    """

    id: str  # Page title
    pos: str  # 3-letter POS code
    wc: int  # Word count
    codes: set[str] = field(default_factory=set)  # 4-letter feature codes
    lemma: Optional[str] = None  # Base form (if inflected)
    nsyll: Optional[int] = None  # Syllable count
    morphology: Optional[Morphology] = None


# =============================================================================
# Helper functions
# =============================================================================

# IPA vowels for syllable counting
IPA_VOWELS = set("iɪeɛæaɑɒɔoʊuʌəɜɝɐᵻᵿɚ")
IPA_OFFGLIDES = set("ɪʊəɐ")
IPA_SYLLABIC_MARKER = "\u0329"


def count_syllables_from_ipa(ipa: str) -> Optional[int]:
    """
    Count syllables from IPA transcription.

    Counts vowel nuclei (monophthongs and diphthongs) plus syllabic consonants.
    """
    # Extract transcription from slashes or brackets
    match = re.search(r"[/\[]([^/\[\]]+)[/\]]", ipa)
    if not match:
        return None

    transcription = match.group(1)
    count = 0
    chars = list(transcription)
    i = 0

    while i < len(chars):
        ch = chars[i]

        # Check for syllabic consonant
        if i + 1 < len(chars) and chars[i + 1] == IPA_SYLLABIC_MARKER:
            count += 1
            i += 2
            continue

        # Check for vowel
        if ch in IPA_VOWELS:
            count += 1
            i += 1

            # Skip diphthong off-glides and modifiers
            vowel_skipped = False
            while i < len(chars):
                next_ch = chars[i]
                if next_ch in ("ː", "ˑ", "\u0303", "\u032F", "\u0361", "̯"):
                    i += 1
                elif not vowel_skipped and next_ch in IPA_OFFGLIDES:
                    vowel_skipped = True
                    i += 1
                else:
                    break
            continue

        i += 1

    return count if count > 0 and count <= 15 else None


def is_englishlike(token: str) -> bool:
    """
    Returns True if token looks like an English-language word or phrase.

    Uses Latin letters (ASCII or Latin diacritics in range 0x00C0-0x024F).
    """
    t = ud.normalize("NFC", token)

    # Reject non-ASCII whitespace except ordinary space
    if any(ch != " " and ch.isspace() for ch in t):
        return False

    if t.strip() == "":
        return False

    ALLOWED_PUNCT = {"'", "'", "'", "-", "–", ".", "/"}
    FORBIDDEN = set("&;<>")

    saw_latin_letter = False

    for ch in t:
        if ch == " ":
            continue

        if ch in FORBIDDEN:
            return False

        if ch.isascii():
            if ch.isalpha():
                saw_latin_letter = True
        else:
            if ch.isalpha():
                cp = ord(ch)
                if 0x00C0 <= cp <= 0x024F:
                    saw_latin_letter = True
                else:
                    return False
            elif ch in ALLOWED_PUNCT:
                pass
            else:
                cp = ord(ch)
                if 0x0300 <= cp <= 0x036F:
                    return False
                if cp > 0xFFFF or (0x1F000 <= cp <= 0x1FFFF):
                    return False

    return saw_latin_letter


def clean_lemma(raw: str) -> str:
    """Clean wiki markup from extracted lemma."""
    # Remove wikilinks: [[word]] -> word, [[link|display]] -> link
    result = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", raw)
    result = result.replace("]]", "").replace("[[", "")

    # Remove templates
    result = re.sub(r"\{\{[^}]+\}\}", "", result)

    # Truncate at section anchor
    if "#" in result:
        result = result.split("#")[0]

    # Strip namespace prefixes
    result = result.lstrip(":")
    if ":" in result:
        result = result.rsplit(":", 1)[-1]

    return result.strip().lower()


# =============================================================================
# Rule functions
# =============================================================================


def determine_pos(evidence: Evidence, config: BindingConfig) -> str:
    """
    Determine POS code from evidence using config lookups.

    Priority order:
    1. Section header
    2. Head template POS value
    3. en-* template name
    4. Category suffix
    5. Default: UNK (unknown)
    """
    # 1. Try section header
    header_lower = evidence.pos_header.lower().strip()
    header_normalized = " ".join(header_lower.split())
    if header_normalized in config.header_to_pos:
        return config.header_to_pos[header_normalized]

    # 2. Try head template POS values
    for template in evidence.head_templates:
        if template.name.lower() in ("head", "en-head", "head-lite") and template.params:
            pos_value = template.params[0].lower().strip()
            if pos_value in config.head_pos_to_pos:
                return config.head_pos_to_pos[pos_value]

    # 3. Try en-* template name (e.g., en-noun -> NOU)
    for template in evidence.head_templates:
        name = template.name.lower()
        if name.startswith("en-"):
            suffix = name[3:]  # Remove "en-" prefix
            if suffix in config.en_template_to_pos:
                return config.en_template_to_pos[suffix]

    # 4. Try category suffix
    for category in evidence.categories:
        cat_lower = category.lower()
        if cat_lower in config.category_suffix_to_pos:
            return config.category_suffix_to_pos[cat_lower]

    # 5. Default to unknown
    return "UNK"


def compute_flags(evidence: Evidence, config: BindingConfig) -> set[str]:
    """
    Compute flag codes from evidence.

    Flags: ABRV (abbreviation), INFL (inflected), PHRZ (phrase)
    """
    flags = set()

    # Check for abbreviation templates
    abbreviation_templates = {
        "abbreviation of",
        "abbrev of",
        "abbr of",
        "initialism of",
        "acronym of",
    }

    # Check head templates for abbreviation
    for template in evidence.head_templates:
        if template.name.lower() in abbreviation_templates:
            if "ABRV" in config.flag_schema:
                flags.add("ABRV")

    # Check definition text for abbreviation templates
    def_lower = evidence.definition_text.lower()
    for abbr_template in abbreviation_templates:
        if f"{{{{{abbr_template}|en|" in def_lower:
            if "ABRV" in config.flag_schema:
                flags.add("ABRV")
            break

    # Check categories for abbreviation
    abbr_categories = {"abbreviations", "initialisms", "acronyms"}
    for category in evidence.categories:
        if category.lower() in abbr_categories:
            if "ABRV" in config.flag_schema:
                flags.add("ABRV")

    # Check for inflection
    if evidence.inflection_template is not None:
        if "INFL" in config.flag_schema:
            flags.add("INFL")

    # Check categories for inflection
    inflection_categories = {
        "verb forms",
        "noun forms",
        "adjective forms",
        "adverb forms",
        "plurals",
    }
    for category in evidence.categories:
        if category.lower() in inflection_categories:
            if "INFL" in config.flag_schema:
                flags.add("INFL")

    # Check for phrase
    if evidence.wc > 1:
        if "PHRZ" in config.flag_schema:
            flags.add("PHRZ")

    return flags


def compute_tags(evidence: Evidence, config: BindingConfig) -> set[str]:
    """
    Compute tag codes from evidence labels and categories.
    """
    tags = set()

    # Map labels to tags
    for label in evidence.labels:
        label_lower = label.lower()
        if label_lower in config.label_to_tag:
            tags.add(config.label_to_tag[label_lower])

    # Map category substrings to tags
    for category in evidence.categories:
        cat_lower = category.lower()
        for substring, code in config.category_substring_to_tag.items():
            if substring in cat_lower:
                tags.add(code)

    return tags


def compute_phrase_type(evidence: Evidence, config: BindingConfig) -> Optional[str]:
    """
    Compute phrase type code if applicable.
    """
    # Only apply to multi-word entries
    if evidence.wc <= 1:
        return None

    # 1. Check phrase type header (highest priority)
    if evidence.phrase_type_header:
        header_lower = evidence.phrase_type_header.lower()
        if header_lower in config.header_to_phrase_type:
            return config.header_to_phrase_type[header_lower]
        # Handle synonyms
        if header_lower in ("saying", "adage"):
            if "proverb" in config.header_to_phrase_type:
                return config.header_to_phrase_type["proverb"]

    # 2. Check head template for phrase type
    for template in evidence.head_templates:
        if template.name.lower() in ("head", "en-head") and template.params:
            pos_value = template.params[0].lower().strip()
            if pos_value in config.header_to_phrase_type:
                return config.header_to_phrase_type[pos_value]

    # 3. Check specific templates
    for template in evidence.head_templates:
        if template.name.lower() in config.template_to_phrase_type:
            return config.template_to_phrase_type[template.name.lower()]

    # 4. Check category suffix
    for category in evidence.categories:
        cat_lower = category.lower()
        if cat_lower in config.category_suffix_to_phrase_type:
            return config.category_suffix_to_phrase_type[cat_lower]

    return None


def compute_morphology(evidence: Evidence, config: BindingConfig) -> Optional[Morphology]:
    """
    Compute morphology structure from etymology templates.
    """
    if not evidence.etymology_templates:
        return None

    template = evidence.etymology_templates[0]  # Use first template
    template_name = template.name.lower()
    params = template.params

    # Clean parameters
    cleaned = []
    # Known language codes to skip
    lang_codes = {"en", "da", "de", "es", "fr", "it", "pt", "nl", "sv", "la", "grc", "ang"}
    skip_first_lang = True  # First param is often language code

    for p in params:
        p = p.strip()
        if not p or "=" in p:
            continue
        # Skip language code prefixes (e.g., "grc:word")
        if re.match(r"^[a-z]{2,4}:", p, re.IGNORECASE):
            continue
        # Skip standalone language codes (usually first param)
        if skip_first_lang and p.lower() in lang_codes:
            skip_first_lang = False
            continue
        skip_first_lang = False
        cleaned.append(p)

    if len(cleaned) < 2:
        return None

    # Classify morphemes by hyphen patterns
    prefixes = [c for c in cleaned if c.endswith("-") and not c.startswith("-")]
    suffixes = [c for c in cleaned if c.startswith("-") and not c.endswith("-")]
    interfixes = [c for c in cleaned if c.startswith("-") and c.endswith("-")]
    bases = [c for c in cleaned if not c.startswith("-") and not c.endswith("-")]

    # Determine morphology type
    if template_name == "compound":
        morph_type = "COMP"
        base = None  # Compounds have no single base
    elif template_name == "confix":
        morph_type = "CIRC"  # Circumfix
        base = bases[0] if bases else None
    elif prefixes and suffixes:
        morph_type = "AFFX"  # Affixed
        base = bases[0] if bases else None
    elif prefixes:
        morph_type = "PREF"  # Prefixed
        base = bases[0] if bases else None
    elif suffixes:
        morph_type = "SUFF"  # Suffixed
        base = bases[0] if bases else None
    else:
        morph_type = "SIMP"  # Simple
        base = None

    # Validate type code exists
    if morph_type not in config.morphology_type_schema:
        return None

    return Morphology(
        type=morph_type,
        components=cleaned,
        base=base,
        prefixes=prefixes if prefixes else [],
        suffixes=suffixes if suffixes else [],
    )


def compute_syllable_count(evidence: Evidence) -> Optional[int]:
    """
    Compute syllable count from multiple evidence sources.

    Priority: IPA > hyphenation > categories > rhymes
    """
    # 1. IPA (most reliable)
    if evidence.ipa_transcription:
        count = count_syllables_from_ipa(evidence.ipa_transcription)
        if count is not None:
            return count

    # 2. Hyphenation
    if evidence.hyphenation_parts:
        parts = evidence.hyphenation_parts
        # Single part > 3 chars is unreliable
        if len(parts) == 1 and len(parts[0]) > 3:
            pass
        elif parts:
            return len(parts)

    # 3. Category count
    if evidence.syllable_category_count is not None:
        return evidence.syllable_category_count

    # 4. Rhymes (has data quality issues)
    if evidence.rhymes_syllable_count is not None:
        return evidence.rhymes_syllable_count

    return None


def extract_lemma(evidence: Evidence) -> Optional[str]:
    """
    Extract lemma from inflection template.
    """
    if evidence.inflection_template is None:
        return None

    if not evidence.inflection_template.params:
        return None

    raw_lemma = evidence.inflection_template.params[0]
    lemma = clean_lemma(raw_lemma)

    if lemma and is_englishlike(lemma):
        return lemma

    return None


def apply_rules(evidence: Evidence, config: BindingConfig) -> Optional[Entry]:
    """
    Convert Evidence to Entry using BindingConfig.

    Returns None if the entry should be filtered out.
    """
    # Filter non-English-like titles
    if not is_englishlike(evidence.title):
        return None

    # Determine POS
    pos = determine_pos(evidence, config)

    # Compute codes
    codes = set()

    # Add flags
    codes.update(compute_flags(evidence, config))

    # Add tags
    codes.update(compute_tags(evidence, config))

    # Add phrase type
    phrase_type = compute_phrase_type(evidence, config)
    if phrase_type:
        codes.add(phrase_type)

    # Compute morphology
    morphology = compute_morphology(evidence, config)
    if morphology:
        codes.add(morphology.type)

    # Compute syllable count
    nsyll = compute_syllable_count(evidence)

    # Extract lemma
    lemma = extract_lemma(evidence)

    return Entry(
        id=evidence.title,
        pos=pos,
        wc=evidence.wc,
        codes=codes,
        lemma=lemma,
        nsyll=nsyll,
        morphology=morphology,
    )


def entry_to_dict(entry: Entry) -> dict:
    """
    Convert Entry to dictionary for JSON output.

    Field order:
    1. id, pos, wc (core identifiers)
    2. codes (if not empty)
    3. lemma (if present)
    4. nsyll (if present)
    5. morphology (if present)
    """
    result = {
        "id": entry.id,
        "pos": entry.pos,
        "wc": entry.wc,
    }

    if entry.codes:
        result["codes"] = sorted(entry.codes)

    if entry.lemma:
        result["lemma"] = entry.lemma

    if entry.nsyll is not None:
        result["nsyll"] = entry.nsyll

    if entry.morphology:
        morph_dict = {
            "type": entry.morphology.type,
            "components": entry.morphology.components,
        }
        if entry.morphology.base:
            morph_dict["base"] = entry.morphology.base
        if entry.morphology.prefixes:
            morph_dict["prefixes"] = entry.morphology.prefixes
        if entry.morphology.suffixes:
            morph_dict["suffixes"] = entry.morphology.suffixes
        result["morphology"] = morph_dict

    return result
