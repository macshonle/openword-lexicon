"""
English Wiktionary-specific patterns for v2 scanner.

This module isolates all English Wiktionary-specific regex patterns and
template matching logic. Patterns are generated from schema/bindings/en-wikt.*.yaml
config files at import time.

Required schema files:
- schema/bindings/en-wikt.flags.yaml (INFL templates, ABRV templates)
- schema/bindings/en-wikt.patterns.yaml (morphology templates, special page prefixes, etc.)

This separation allows:
- Clear visibility into what's language/source specific
- Easier maintenance when Wiktionary conventions change
- Potential reuse of schema/ approach for other language editions
"""

import re
import sys
from pathlib import Path
from typing import Optional

import yaml


# =============================================================================
# Schema file paths
# =============================================================================

def _get_schema_path() -> Path:
    """Get path to schema directory."""
    return Path(__file__).parent.parent.parent / "schema"


def _get_bindings_path() -> Path:
    """Get path to schema/bindings directory."""
    return _get_schema_path() / "bindings"


# =============================================================================
# Config loading with error handling
# =============================================================================

class SchemaError(Exception):
    """Raised when required schema files are missing or invalid."""
    pass


def _load_yaml(path: Path, description: str) -> dict:
    """Load YAML file with clear error message if missing."""
    if not path.exists():
        raise SchemaError(
            f"Required schema file not found: {path}\n"
            f"This file is needed for: {description}\n"
            f"Please ensure the schema directory is properly configured."
        )
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise SchemaError(f"Invalid YAML in {path}: {e}")


def _load_flags_config() -> dict:
    """Load en-wikt.flags.yaml config."""
    path = _get_bindings_path() / "en-wikt.flags.yaml"
    return _load_yaml(path, "inflection and abbreviation template patterns")


def _load_patterns_config() -> dict:
    """Load en-wikt.patterns.yaml config."""
    path = _get_bindings_path() / "en-wikt.patterns.yaml"
    return _load_yaml(path, "morphology templates, special page prefixes, and other patterns")


# =============================================================================
# Inflection patterns (from en-wikt.flags.yaml)
# =============================================================================

def build_inflection_patterns() -> list[tuple[str, re.Pattern]]:
    """
    Build inflection regex patterns from en-wikt.flags.yaml.

    Returns list of (template_name, compiled_regex) tuples.

    The YAML config specifies template names like "plural of", "past tense of".
    We generate regex patterns that match these templates with English lang code.
    """
    config = _load_flags_config()
    infl_config = config.get("flags", {}).get("INFL", {})
    templates = infl_config.get("templates", [])

    if not templates:
        raise SchemaError(
            "No INFL templates found in en-wikt.flags.yaml.\n"
            "Expected flags.INFL.templates to contain template names."
        )

    patterns = []
    for template_name in templates:
        # Handle "en-" prefix variants
        if template_name.startswith("en-"):
            # Match both with and without "en-" prefix
            base_name = template_name[3:]
            regex = re.compile(
                rf"\{{\{{(?:en-)?{re.escape(base_name)}\|en\|([^|}}]+)",
                re.IGNORECASE
            )
        else:
            regex = re.compile(
                rf"\{{\{{{re.escape(template_name)}\|en\|([^|}}]+)",
                re.IGNORECASE
            )
        patterns.append((template_name, regex))

    return patterns


# =============================================================================
# Abbreviation patterns (from en-wikt.flags.yaml)
# =============================================================================

def build_abbreviation_pattern() -> re.Pattern:
    """
    Build abbreviation regex pattern from en-wikt.flags.yaml.

    Returns compiled regex that matches any abbreviation template.
    """
    config = _load_flags_config()
    abrv_config = config.get("flags", {}).get("ABRV", {})
    templates = abrv_config.get("templates", [])

    if not templates:
        raise SchemaError(
            "No ABRV templates found in en-wikt.flags.yaml.\n"
            "Expected flags.ABRV.templates to contain template names."
        )

    # Build alternation pattern: (?:abbr of|abbrev of|...)
    escaped = [re.escape(t) for t in templates]
    alternation = "|".join(escaped)
    return re.compile(rf"\{{\{{(?:{alternation})\|en\|", re.IGNORECASE)


# =============================================================================
# Morphology patterns (from en-wikt.patterns.yaml)
# =============================================================================

def _load_morphology_templates() -> list[str]:
    """Load morphology template names from en-wikt.patterns.yaml."""
    config = _load_patterns_config()
    templates = config.get("morphology_templates", [])

    if not templates:
        raise SchemaError(
            "No morphology_templates found in en-wikt.patterns.yaml.\n"
            "Expected morphology_templates to contain template names."
        )

    return templates


def _build_morphology_patterns(template_names: list[str]) -> dict[str, re.Pattern]:
    """Build regex patterns for morphology templates."""
    patterns = {}
    for name in template_names:
        # Handle "af" as short form of "affix"
        if name == "af":
            patterns[name] = re.compile(rf"\{{\{{af(?:fix)?\|en\|([^}}]+)\}}\}}", re.IGNORECASE)
        else:
            patterns[name] = re.compile(rf"\{{\{{{re.escape(name)}\|en\|([^}}]+)\}}\}}", re.IGNORECASE)
    return patterns


# =============================================================================
# Special page prefixes (from en-wikt.patterns.yaml)
# =============================================================================

def _load_special_page_prefixes() -> tuple[str, ...]:
    """Load special page prefixes from en-wikt.patterns.yaml."""
    config = _load_patterns_config()
    prefixes = config.get("special_page_prefixes", [])

    if not prefixes:
        raise SchemaError(
            "No special_page_prefixes found in en-wikt.patterns.yaml.\n"
            "Expected special_page_prefixes to contain prefix strings."
        )

    return tuple(prefixes)


# =============================================================================
# Dict-only templates (from en-wikt.patterns.yaml)
# =============================================================================

def _load_dict_only_pattern() -> re.Pattern:
    """Build dict-only pattern from en-wikt.patterns.yaml."""
    config = _load_patterns_config()
    templates = config.get("dict_only_templates", [])

    if not templates:
        raise SchemaError(
            "No dict_only_templates found in en-wikt.patterns.yaml.\n"
            "Expected dict_only_templates to contain template names."
        )

    # Build alternation: {{no entry|en or {{other|en
    escaped = [re.escape(t) for t in templates]
    alternation = "|".join(escaped)
    return re.compile(rf"\{{\{{(?:{alternation})\|en", re.IGNORECASE)


# =============================================================================
# Head templates (from en-wikt.patterns.yaml)
# =============================================================================

def _build_head_patterns() -> tuple[re.Pattern, re.Pattern]:
    """Build head template patterns from en-wikt.patterns.yaml."""
    config = _load_patterns_config()
    head_config = config.get("head_templates", {})

    generic = head_config.get("generic", [])
    pos_specific = head_config.get("pos_specific", [])

    if not generic:
        raise SchemaError(
            "No head_templates.generic found in en-wikt.patterns.yaml."
        )

    # {{head|en|noun}} or {{en-head|noun}} or {{head-lite|en|noun}}
    generic_alt = "|".join(re.escape(t) for t in generic)
    head_pattern = re.compile(
        rf"\{{\{{({generic_alt})\|en\|([^}}]+)\}}\}}",
        re.IGNORECASE
    )

    # {{en-noun}}, {{en-verb}}, etc.
    if pos_specific:
        # Extract POS names from en-* templates
        pos_names = [t[3:] for t in pos_specific if t.startswith("en-")]
        pos_alt = "|".join(re.escape(p) for p in pos_names)
        en_pos_pattern = re.compile(rf"\{{\{{en-({pos_alt})\b", re.IGNORECASE)
    else:
        # Default pattern if not specified
        en_pos_pattern = re.compile(r"\{\{en-(noun|verb|adj|adv|prop|pron|phrase|prepphr)\b", re.IGNORECASE)

    return head_pattern, en_pos_pattern


# =============================================================================
# Context label templates (from en-wikt.patterns.yaml)
# =============================================================================

def _build_context_patterns() -> tuple[re.Pattern, re.Pattern]:
    """Build context label patterns from en-wikt.patterns.yaml."""
    config = _load_patterns_config()
    label_templates = config.get("context_label_templates", [])

    if not label_templates:
        raise SchemaError(
            "No context_label_templates found in en-wikt.patterns.yaml."
        )

    # Separate tlb (top-level label) from other context labels
    other_templates = [t for t in label_templates if t != "tlb"]

    # {{lb|en|...}} or {{label|en|...}} or {{context|en|...}}
    other_alt = "|".join(re.escape(t) for t in other_templates)
    context_pattern = re.compile(
        rf"\{{\{{(?:{other_alt})\|en\|([^}}]+)\}}\}}",
        re.IGNORECASE
    )

    # {{tlb|en|UK}}
    tlb_pattern = re.compile(r"\{\{tlb\|en\|([^}]+)\}\}", re.IGNORECASE)

    return context_pattern, tlb_pattern


# =============================================================================
# Syllable patterns (from en-wikt.patterns.yaml)
# =============================================================================

def _build_syllable_patterns() -> tuple[re.Pattern, re.Pattern, re.Pattern, re.Pattern]:
    """Build syllable extraction patterns from en-wikt.patterns.yaml."""
    config = _load_patterns_config()
    syllable_config = config.get("syllable_templates", {})

    # Hyphenation: {{hyphenation|en|...}} or {{hyph|en|...}}
    hyph_templates = syllable_config.get("hyphenation", [])
    if hyph_templates:
        hyph_alt = "|".join(re.escape(t) for t in hyph_templates)
        hyphenation_pattern = re.compile(
            rf"\{{\{{(?:{hyph_alt})\|en\|([^}}]+)\}}\}}",
            re.IGNORECASE
        )
    else:
        hyphenation_pattern = re.compile(r"\{\{(?:hyphenation|hyph)\|en\|([^}]+)\}\}", re.IGNORECASE)

    # Rhymes: {{rhymes|en|æt|s=1}}
    rhymes_template = syllable_config.get("rhymes", "rhymes")
    rhymes_pattern = re.compile(
        rf"\{{\{{{re.escape(rhymes_template)}\|en\|[^}}]*\|s=(\d+)",
        re.IGNORECASE
    )

    # IPA: {{IPA|en|/ˈhæpinəs/}}
    ipa_template = syllable_config.get("ipa", "IPA")
    ipa_pattern = re.compile(
        rf"\{{\{{{re.escape(ipa_template)}\|en\|([^}}]+)\}}\}}",
        re.IGNORECASE
    )

    # Syllable category: [[Category:English 3-syllable words]]
    syllable_category_pattern = re.compile(
        r"\[\[Category:English\s+(\d+)-syllable\s+words?\]\]",
        re.IGNORECASE
    )

    return hyphenation_pattern, rhymes_pattern, syllable_category_pattern, ipa_pattern


# =============================================================================
# Section structure patterns (structural, not from config)
#
# These patterns are structural to wikitext format and don't need externalization.
# =============================================================================

# ==English== language section header
ENGLISH_SECTION = re.compile(r"==\s*English\s*==", re.IGNORECASE)

# ==Language== any language section header (for finding section boundaries)
LANGUAGE_SECTION = re.compile(r"^==\s*([^=]+?)\s*==$", re.MULTILINE)

# ===Noun===, ===Etymology 1===, etc.
POS_HEADER = re.compile(r"^===+\s*(.+?)\s*===+\s*$", re.MULTILINE)

# ===Etymology=== or ===Etymology 1===
ETYMOLOGY_HEADER = re.compile(r"^===+\s*Etymology\s*(\d*)\s*===+\s*$", re.MULTILINE | re.IGNORECASE)

# Etymology section content extraction
ETYMOLOGY_SECTION = re.compile(
    r"===\s*Etymology\s*===\s*\n(.*?)(?=\n===|\Z)", re.DOTALL | re.IGNORECASE
)

# Definition lines: # definition text
DEFINITION_LINE = re.compile(r"^#\s+(.+)$", re.MULTILINE)

# [[Category:English nouns]] - extract category suffix after "English "
CATEGORY = re.compile(r"\[\[Category:English\s+([^\]]+)\]\]", re.IGNORECASE)


# =============================================================================
# English section extraction
# =============================================================================

def extract_english_section(text: str) -> Optional[str]:
    """
    Extract only the English section from a Wiktionary page.

    This is an optimization to avoid parsing non-English content which may
    contain templates that look similar but have different semantics.

    Returns the English section text, or None if no English section found.
    """
    # Find ==English== header
    match = ENGLISH_SECTION.search(text)
    if not match:
        return None

    start = match.end()

    # Find next language section (==SomeLanguage==) or end of text
    rest = text[start:]
    next_lang = LANGUAGE_SECTION.search(rest)

    if next_lang:
        return rest[:next_lang.start()]
    else:
        return rest


# =============================================================================
# Module initialization - build all patterns from config
# =============================================================================

def _initialize_all_patterns():
    """
    Initialize all patterns from config files at module import time.

    Raises SchemaError with clear message if required files are missing.
    """
    global INFLECTION_PATTERNS, ABBREVIATION_PATTERN
    global MORPHOLOGY_TEMPLATE_NAMES, MORPHOLOGY_PATTERNS
    global SUFFIX_TEMPLATE, PREFIX_TEMPLATE, AFFIX_TEMPLATE
    global COMPOUND_TEMPLATE, CONFIX_TEMPLATE, SURF_TEMPLATE
    global SPECIAL_PAGE_PREFIXES, DICT_ONLY
    global HEAD_TEMPLATE, EN_POS_TEMPLATE
    global CONTEXT_LABEL, TLB_TEMPLATE
    global HYPHENATION_TEMPLATE, RHYMES_SYLLABLE, SYLLABLE_CATEGORY, IPA_TEMPLATE

    try:
        # Inflection and abbreviation from en-wikt.flags.yaml
        INFLECTION_PATTERNS = build_inflection_patterns()
        ABBREVIATION_PATTERN = build_abbreviation_pattern()

        # Morphology from en-wikt.patterns.yaml
        MORPHOLOGY_TEMPLATE_NAMES = _load_morphology_templates()
        MORPHOLOGY_PATTERNS = _build_morphology_patterns(MORPHOLOGY_TEMPLATE_NAMES)

        # Create named pattern variables for backwards compatibility
        SUFFIX_TEMPLATE = MORPHOLOGY_PATTERNS.get("suffix", re.compile(r"$^"))  # never match
        PREFIX_TEMPLATE = MORPHOLOGY_PATTERNS.get("prefix", re.compile(r"$^"))
        AFFIX_TEMPLATE = MORPHOLOGY_PATTERNS.get("af", re.compile(r"$^"))
        COMPOUND_TEMPLATE = MORPHOLOGY_PATTERNS.get("compound", re.compile(r"$^"))
        CONFIX_TEMPLATE = MORPHOLOGY_PATTERNS.get("confix", re.compile(r"$^"))
        SURF_TEMPLATE = MORPHOLOGY_PATTERNS.get("surf", re.compile(r"$^"))

        # Special page prefixes and dict-only
        SPECIAL_PAGE_PREFIXES = _load_special_page_prefixes()
        DICT_ONLY = _load_dict_only_pattern()

        # Head templates
        HEAD_TEMPLATE, EN_POS_TEMPLATE = _build_head_patterns()

        # Context labels
        CONTEXT_LABEL, TLB_TEMPLATE = _build_context_patterns()

        # Syllable patterns
        HYPHENATION_TEMPLATE, RHYMES_SYLLABLE, SYLLABLE_CATEGORY, IPA_TEMPLATE = _build_syllable_patterns()

    except SchemaError as e:
        print(f"ERROR: Schema configuration error:\n{e}", file=sys.stderr)
        sys.exit(1)


# Declare module-level variables (will be populated by _initialize_all_patterns)
INFLECTION_PATTERNS: list[tuple[str, re.Pattern]] = []
ABBREVIATION_PATTERN: re.Pattern = re.compile(r"$^")  # placeholder
MORPHOLOGY_TEMPLATE_NAMES: list[str] = []
MORPHOLOGY_PATTERNS: dict[str, re.Pattern] = {}
SUFFIX_TEMPLATE: re.Pattern = re.compile(r"$^")
PREFIX_TEMPLATE: re.Pattern = re.compile(r"$^")
AFFIX_TEMPLATE: re.Pattern = re.compile(r"$^")
COMPOUND_TEMPLATE: re.Pattern = re.compile(r"$^")
CONFIX_TEMPLATE: re.Pattern = re.compile(r"$^")
SURF_TEMPLATE: re.Pattern = re.compile(r"$^")
SPECIAL_PAGE_PREFIXES: tuple[str, ...] = ()
DICT_ONLY: re.Pattern = re.compile(r"$^")
HEAD_TEMPLATE: re.Pattern = re.compile(r"$^")
EN_POS_TEMPLATE: re.Pattern = re.compile(r"$^")
CONTEXT_LABEL: re.Pattern = re.compile(r"$^")
TLB_TEMPLATE: re.Pattern = re.compile(r"$^")
HYPHENATION_TEMPLATE: re.Pattern = re.compile(r"$^")
RHYMES_SYLLABLE: re.Pattern = re.compile(r"$^")
SYLLABLE_CATEGORY: re.Pattern = re.compile(r"$^")
IPA_TEMPLATE: re.Pattern = re.compile(r"$^")

# Initialize on import
_initialize_all_patterns()
