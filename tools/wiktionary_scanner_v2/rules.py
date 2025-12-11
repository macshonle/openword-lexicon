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
    definition_level: int = 1  # 1 for #, 2 for ##, 3 for ###
    definition_type: str = "primary"  # primary, secondary, tertiary, quote, synonym, usage
    senseid: Optional[str] = None  # Wikidata QID or semantic identifier from {{senseid|en|...}}


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

    # 4. Try category suffix (use pre-lowercased categories)
    for cat_lower in evidence.categories_lower:
        if cat_lower in config.category_suffix_to_pos:
            return config.category_suffix_to_pos[cat_lower]

    # 5. Default to unknown
    return "UNK"


def compute_flags(evidence: Evidence, config: BindingConfig) -> set[str]:
    """
    Compute flag codes from evidence using binding tables.

    Uses config.template_to_flag and config.category_suffix_to_flag for
    binding-driven matching, with fallback heuristics for edge cases.
    """
    flags = set()

    # 1. Check head templates against binding table
    for template in evidence.head_templates:
        template_lower = template.name.lower()
        if template_lower in config.template_to_flag:
            flags.add(config.template_to_flag[template_lower])

    # 2. Check inflection template against binding table (no fallback - use config)
    if evidence.inflection_template:
        template_lower = evidence.inflection_template.name.lower()
        if template_lower in config.template_to_flag:
            flags.add(config.template_to_flag[template_lower])

    # 2b. Check alternative form template against binding table
    if evidence.altform_template:
        template_lower = evidence.altform_template.name.lower()
        if template_lower in config.template_to_flag:
            flags.add(config.template_to_flag[template_lower])

    # 3. Check categories against binding table (use pre-lowercased)
    for cat_lower in evidence.categories_lower:
        if cat_lower in config.category_suffix_to_flag:
            flags.add(config.category_suffix_to_flag[cat_lower])

    # 4. Check definition text for template patterns (e.g., {{abbr of|en|...}})
    # This catches cases where templates appear in definitions but not head_templates
    def_lower = evidence.definition_text.lower()
    for template_name, flag_code in config.template_to_flag.items():
        if f"{{{{{template_name}|en|" in def_lower or f"{{{{{template_name}|en}}}}" in def_lower:
            flags.add(flag_code)

    # 5. Phrase heuristic: multi-word entries get PHRZ flag
    if evidence.wc > 1:
        if "PHRZ" in config.flag_schema:
            flags.add("PHRZ")

    return flags


def compute_tags(evidence: Evidence, config: BindingConfig) -> set[str]:
    """
    Compute tag codes from evidence labels, spelling labels, and categories.

    Uses config.label_qualifiers to strip noise words before lookup.
    Uses config.label_normalizations to canonicalize labels before lookup.
    Also extracts spelling region from {{standard spelling of|en|from=...|target}}
    """
    tags = set()

    def strip_qualifiers(label: str) -> str:
        """Strip leading qualifier words from a label."""
        words = label.split()
        while words and words[0] in config.label_qualifiers:
            words.pop(0)
        return " ".join(words)

    def normalize_and_lookup(label: str) -> str | None:
        """Strip qualifiers, normalize a label and look it up in the tag table."""
        label_lower = label.lower()
        # Strip leading qualifiers (e.g., "usu. derogatory" -> "derogatory")
        stripped = strip_qualifiers(label_lower)
        if not stripped:
            return None
        # Apply normalizations (e.g., "u.s." -> "us", "british" -> "uk")
        normalized = config.label_normalizations.get(stripped, stripped)
        return config.label_to_tag.get(normalized)

    # Map labels from {{lb|en|...}} to tags
    for label in evidence.labels:
        tag = normalize_and_lookup(label)
        if tag:
            tags.add(tag)

    # Map spelling labels from {{tlb|en|...}} to tags (for regional variants)
    for label in evidence.spelling_labels:
        tag = normalize_and_lookup(label)
        if tag:
            tags.add(tag)

    # Extract spelling region from altform template from= params
    # e.g., {{standard spelling of|en|from=Commonwealth|from2=Ireland|color}}
    # params[0] = "color", params[1:] = ["Commonwealth", "Ireland"]
    # Mapping is loaded from schema/bindings/en-wikt.flags.yaml (ALTH.from_param_to_spelling)
    if evidence.altform_template and len(evidence.altform_template.params) > 1:
        for from_value in evidence.altform_template.params[1:]:
            from_lower = from_value.lower().strip()
            spelling_label = config.from_param_to_spelling.get(from_lower)
            if spelling_label:
                tag = config.label_to_tag.get(spelling_label)
                if tag:
                    tags.add(tag)

    # Map category substrings to tags (use pre-lowercased)
    for cat_lower in evidence.categories_lower:
        for substring, code in config.category_substring_to_tag.items():
            if substring in cat_lower:
                tags.add(code)

    return tags


def compute_phrase_type(evidence: Evidence, config: BindingConfig) -> Optional[str]:
    """
    Compute phrase type code if applicable using binding tables.

    Priority: phrase_type_header > pos_header > head template POS > template name > category
    All mappings are driven by config bindings (no hardcoded synonyms).
    """
    # Only apply to multi-word entries
    if evidence.wc <= 1:
        return None

    # 1. Check phrase type header from evidence (highest priority)
    if evidence.phrase_type_header:
        header_lower = evidence.phrase_type_header.lower()
        if header_lower in config.header_to_phrase_type:
            return config.header_to_phrase_type[header_lower]

    # 2. Check POS header against phrase type headers (idiom, proverb, etc.)
    if evidence.pos_header:
        header_lower = evidence.pos_header.lower()
        if header_lower in config.header_to_phrase_type:
            return config.header_to_phrase_type[header_lower]

    # 3. Check head template POS value (e.g., {{head|en|idiom}})
    for template in evidence.head_templates:
        if template.name.lower() in ("head", "en-head") and template.params:
            # Get positional params (skip named params with =)
            pos_params = [p for p in template.params if "=" not in p and p.strip()]
            # Skip language code if present
            for pos_value in pos_params:
                if pos_value.lower() == "en":
                    continue
                if pos_value.lower() in config.header_to_phrase_type:
                    return config.header_to_phrase_type[pos_value.lower()]
                break  # Only check first non-en param

    # 4. Check specific phrase templates (e.g., {{en-prepphr}})
    for template in evidence.head_templates:
        template_lower = template.name.lower()
        if template_lower in config.template_to_phrase_type:
            return config.template_to_phrase_type[template_lower]

    # 5. Check category suffix (use pre-lowercased)
    for cat_lower in evidence.categories_lower:
        if cat_lower in config.category_suffix_to_phrase_type:
            return config.category_suffix_to_phrase_type[cat_lower]

    return None


def _find_morphology_template_binding(
    template_name: str,
    template_params: list[str],
    config: BindingConfig,
) -> Optional[tuple[str, list[str], str]]:
    """
    Find matching morphology template binding by name/alias and language.

    Checks that the template's first param matches the expected language_param
    from the binding config. This prevents matching non-English etymology
    templates on mixed-language pages.

    Args:
        template_name: Name of the template (e.g., "suffix")
        template_params: List of template parameters
        config: BindingConfig with morphology templates

    Returns:
        (canonical_name, roles, language_param) if found, None otherwise
    """
    template_lower = template_name.lower()

    # Extract first positional param (likely the language code)
    first_param = None
    for p in template_params:
        p = p.strip()
        if p and "=" not in p:
            first_param = p.lower()
            break

    for mt in config.morphology_templates:
        # Check name or alias match
        name_match = template_lower == mt.name.lower()
        alias_match = any(template_lower == alias.lower() for alias in mt.aliases)

        if name_match or alias_match:
            # Check language param matches expected value
            if first_param == mt.language_param.lower():
                return (mt.name, mt.roles, mt.language_param)

    return None


def compute_morphology(evidence: Evidence, config: BindingConfig) -> Optional[Morphology]:
    """
    Compute morphology structure from etymology templates using binding config.

    Iterates over all etymology templates until finding one that matches a
    binding with the correct language. Uses config.morphology_templates to
    match templates and derive roles, then maps type through
    config.morphology_type_to_code.
    """
    if not evidence.etymology_templates:
        return None

    # Try each etymology template until we find a matching binding
    template = None
    binding = None

    for t in evidence.etymology_templates:
        binding = _find_morphology_template_binding(t.name, t.params, config)
        if binding:
            template = t
            break

    if template is None or binding is None:
        # No matching binding found - config must define the template
        return None

    template_name = template.name.lower()
    params = template.params
    canonical_name, roles, _ = binding

    # Extract components (skip language codes and named params)
    cleaned = []
    lang_codes = {"en", "da", "de", "es", "fr", "it", "pt", "nl", "sv", "la", "grc", "ang"}
    skip_first_lang = True

    for p in params:
        p = p.strip()
        if not p or "=" in p:
            continue
        if re.match(r"^[a-z]{2,4}:", p, re.IGNORECASE):
            continue
        if skip_first_lang and p.lower() in lang_codes:
            skip_first_lang = False
            continue
        skip_first_lang = False
        cleaned.append(p)

    if len(cleaned) < 2:
        return None

    # Initialize structured data
    prefixes = []
    suffixes = []
    bases = []
    components = []

    # Use roles from binding to classify components
    for i, component in enumerate(cleaned):
        role = roles[i] if i < len(roles) else "component"

        if role == "prefix":
            # Normalize: ensure trailing hyphen
            if not component.endswith("-"):
                component = component + "-"
            prefixes.append(component)
        elif role == "suffix":
            # Normalize: ensure leading hyphen
            if not component.startswith("-"):
                component = "-" + component
            suffixes.append(component)
        elif role == "base":
            bases.append(component)
        else:
            # Generic component - classify by hyphen pattern
            if component.endswith("-") and not component.startswith("-"):
                prefixes.append(component)
            elif component.startswith("-") and not component.endswith("-"):
                suffixes.append(component)
            elif not component.startswith("-") and not component.endswith("-"):
                bases.append(component)

        components.append(component)

    # Determine type based on canonical template name and derived structure
    if canonical_name == "compound":
        morph_type_str = "compound"
    elif canonical_name == "confix":
        morph_type_str = "circumfixed"
    elif prefixes and suffixes:
        morph_type_str = "affixed"
    elif prefixes:
        morph_type_str = "prefixed"
    elif suffixes:
        morph_type_str = "suffixed"
    else:
        morph_type_str = "simple"

    # Map type string to 4-letter code via config (no hardcoded fallback)
    morph_type = config.morphology_type_to_code.get(morph_type_str)
    if not morph_type or morph_type not in config.morphology_type_schema:
        return None

    return Morphology(
        type=morph_type,
        components=components,
        base=bases[0] if bases else None,
        prefixes=prefixes,
        suffixes=suffixes,
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
    Extract lemma from inflection template or alternative form template.

    For inflected forms (e.g., "cats" -> "cat"), returns the base form.
    For alternative forms (e.g., "colour" -> "color"), returns the canonical form.
    """
    # Try inflection template first
    if evidence.inflection_template and evidence.inflection_template.params:
        raw_lemma = evidence.inflection_template.params[0]
        lemma = clean_lemma(raw_lemma)
        if lemma and is_englishlike(lemma):
            return lemma

    # Try alternative form template
    if evidence.altform_template and evidence.altform_template.params:
        raw_lemma = evidence.altform_template.params[0]
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
        definition_level=evidence.definition_level,
        definition_type=evidence.definition_type,
        senseid=evidence.senseid,
    )


def entry_to_dict(entry: Entry) -> dict:
    """
    Convert Entry to dictionary for JSON output.

    Field order:
    1. id, pos, wc (core identifiers)
    2. nsyll (if present)
    3. codes (if not empty)
    4. lemma (if present)
    5. morphology (if present)
    6. def_level, def_type (if not primary level 1)
    """
    result = {
        "id": entry.id,
        "pos": entry.pos,
        "wc": entry.wc,
    }

    if entry.nsyll is not None:
        result["nsyll"] = entry.nsyll

    if entry.codes:
        result["codes"] = sorted(entry.codes)

    if entry.lemma:
        result["lemma"] = entry.lemma

    if entry.morphology:
        morph_dict = {
            "components": entry.morphology.components,
        }
        if entry.morphology.base:
            morph_dict["base"] = entry.morphology.base
        if entry.morphology.prefixes:
            morph_dict["prefixes"] = entry.morphology.prefixes
        if entry.morphology.suffixes:
            morph_dict["suffixes"] = entry.morphology.suffixes
        result["morphology"] = morph_dict

    # Include definition level/type only for non-primary entries
    if entry.definition_level != 1 or entry.definition_type != "primary":
        result["def_level"] = entry.definition_level
        result["def_type"] = entry.definition_type

    # Include senseid if present
    if entry.senseid:
        result["senseid"] = entry.senseid

    return result
