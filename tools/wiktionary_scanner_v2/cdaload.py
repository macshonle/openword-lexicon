"""
CDA (Configuration-Driven Architecture) loader for v2 scanner.

This module loads schema/core/ and schema/bindings/ YAML files and builds
indexed lookup tables for efficient rule application. The "CDA" name is
intentionally distinctive to prompt readers to investigate this architectural
pattern.

The BindingConfig object provides:
- Core schema definitions (POS, flags, tags, phrase types, morphology types)
- Indexed mappings from Wiktionary signals → codes
- Validation of code shapes and global uniqueness
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Pattern

from .schema import (
    CoreSchema,
    Bindings,
    PosClass,
    Flag,
    Tag,
    PhraseType,
    MorphologyType,
    MorphologyTemplate,
    load_core_schema,
    load_bindings,
)


@dataclass
class BindingConfig:
    """
    Complete configuration for the v2 scanner.

    Combines core schema definitions with indexed binding lookups.
    All lookup tables use lowercase keys for case-insensitive matching.
    """

    # === Core schemas (code → metadata) ===
    pos_schema: dict[str, PosClass] = field(default_factory=dict)
    flag_schema: dict[str, Flag] = field(default_factory=dict)
    tag_schema: dict[str, dict[str, Tag]] = field(default_factory=dict)
    phrase_type_schema: dict[str, PhraseType] = field(default_factory=dict)
    morphology_type_schema: dict[str, MorphologyType] = field(default_factory=dict)

    # === POS bindings (en-wikt.pos.yaml) ===
    header_to_pos: dict[str, str] = field(default_factory=dict)
    head_pos_to_pos: dict[str, str] = field(default_factory=dict)
    en_template_to_pos: dict[str, str] = field(default_factory=dict)
    category_suffix_to_pos: dict[str, str] = field(default_factory=dict)

    # === Flag bindings (en-wikt.flags.yaml) ===
    template_to_flag: dict[str, str] = field(default_factory=dict)
    category_suffix_to_flag: dict[str, str] = field(default_factory=dict)

    # === Tag bindings (en-wikt.tag_sets.yaml) ===
    label_to_tag: dict[str, str] = field(default_factory=dict)
    category_substring_to_tag: dict[str, str] = field(default_factory=dict)

    # === Phrase type bindings (en-wikt.phrase_types.yaml) ===
    header_to_phrase_type: dict[str, str] = field(default_factory=dict)
    template_to_phrase_type: dict[str, str] = field(default_factory=dict)
    category_suffix_to_phrase_type: dict[str, str] = field(default_factory=dict)

    # === Morphology bindings (en-wikt.morphology.yaml) ===
    morphology_templates: list[MorphologyTemplate] = field(default_factory=list)
    morphology_type_to_code: dict[str, str] = field(default_factory=dict)

    # === Section roles (en-wikt.section_roles.yaml) ===
    ignore_headers: set[str] = field(default_factory=set)  # Literal headers (no patterns)
    ignore_header_patterns: list[Pattern[str]] = field(default_factory=list)  # Compiled %d patterns
    label_qualifiers: set[str] = field(default_factory=set)  # Noise words to strip from labels
    label_normalizations: dict[str, str] = field(default_factory=dict)
    definition_markers: dict[str, str] = field(default_factory=dict)  # type → prefix (e.g., "primary" → "#")
    definition_marker_pattern: Pattern[str] | None = None  # Compiled regex for matching definition lines

    # === Derived allowlists (computed from bindings) ===
    # pos_headers = headers that map to a POS or phrase type (the "allowlist")
    pos_headers: set[str] = field(default_factory=set)

    def is_ignored_header(self, header: str) -> bool:
        """
        Check if a header should be ignored (is a metadata section).

        Args:
            header: Header text, already lowercased and whitespace-normalized

        Returns:
            True if the header should be skipped
        """
        # Fast path: check literal headers first
        if header in self.ignore_headers:
            return True
        # Slow path: check patterns
        for pattern in self.ignore_header_patterns:
            if pattern.fullmatch(header):
                return True
        return False

    def parse_definition_marker(self, prefix: str) -> tuple[str, int]:
        """
        Parse a definition marker prefix into (type, level).

        Args:
            prefix: The matched prefix (e.g., "#", "##", "#*")

        Returns:
            (definition_type, definition_level) tuple
        """
        # Find matching type from definition_markers
        for def_type, marker_prefix in self.definition_markers.items():
            if prefix == marker_prefix:
                # Determine level from hash count
                level = prefix.count("#")
                if level == 0:
                    level = 1  # Fallback for non-hash markers
                return (def_type, level)

        # Fallback: primary level 1
        return ("primary", 1)

    def summary(self) -> str:
        """Return a human-readable summary of the loaded configuration."""
        ignore_count = len(self.ignore_headers) + len(self.ignore_header_patterns)
        pattern_note = f" ({len(self.ignore_header_patterns)} patterns)" if self.ignore_header_patterns else ""
        return (
            f"Core schema:\n"
            f"  - {len(self.pos_schema)} POS codes\n"
            f"  - {len(self.flag_schema)} flag codes\n"
            f"  - {sum(len(tags) for tags in self.tag_schema.values())} tag codes "
            f"in {len(self.tag_schema)} sets\n"
            f"  - {len(self.phrase_type_schema)} phrase type codes\n"
            f"  - {len(self.morphology_type_schema)} morphology type codes\n"
            f"\n"
            f"Bindings:\n"
            f"  - {len(self.header_to_pos)} POS header mappings\n"
            f"  - {len(self.template_to_flag)} flag template mappings\n"
            f"  - {len(self.label_to_tag)} label → tag mappings\n"
            f"  - {len(self.morphology_templates)} morphology templates\n"
            f"  - {len(self.pos_headers)} POS/phrase header allowlist entries\n"
            f"  - {ignore_count} ignored section headers{pattern_note}"
        )


class CodeValidationError(ValueError):
    """Raised when code validation fails."""

    pass


def validate_code_shape(code: str, expected_length: int, context: str) -> None:
    """
    Validate that a code has the expected shape.

    Args:
        code: The code to validate
        expected_length: Expected number of characters (3 for POS, 4 for others)
        context: Description for error messages

    Raises:
        CodeValidationError: If code doesn't match expected shape
    """
    if len(code) != expected_length:
        raise CodeValidationError(
            f"{context}: code '{code}' should be {expected_length} characters, "
            f"got {len(code)}"
        )
    if not code.isupper():
        raise CodeValidationError(
            f"{context}: code '{code}' should be uppercase"
        )
    if not code.isalpha():
        raise CodeValidationError(
            f"{context}: code '{code}' should contain only letters"
        )


def validate_code_uniqueness(config: BindingConfig) -> None:
    """
    Validate that all 4-letter codes are globally unique.

    All flags, tags, phrase types, and morphology types share a single
    namespace and must not collide.

    Args:
        config: The BindingConfig to validate

    Raises:
        CodeValidationError: If duplicate codes are found
    """
    seen: dict[str, str] = {}  # code → source

    # Collect all 4-letter codes
    for code in config.flag_schema:
        if code in seen:
            raise CodeValidationError(
                f"Duplicate code '{code}': defined in both {seen[code]} and flags"
            )
        seen[code] = "flags"

    for tag_set_code, tags in config.tag_schema.items():
        for tag_code in tags:
            if tag_code in seen:
                raise CodeValidationError(
                    f"Duplicate code '{tag_code}': defined in both {seen[tag_code]} "
                    f"and tag_set {tag_set_code}"
                )
            seen[tag_code] = f"tag_set:{tag_set_code}"

    for code in config.phrase_type_schema:
        if code in seen:
            raise CodeValidationError(
                f"Duplicate code '{code}': defined in both {seen[code]} and phrase_types"
            )
        seen[code] = "phrase_types"

    for code in config.morphology_type_schema:
        if code in seen:
            raise CodeValidationError(
                f"Duplicate code '{code}': defined in both {seen[code]} and morphology_types"
            )
        seen[code] = "morphology_types"


def load_binding_config(core_path: Path, bindings_path: Path) -> BindingConfig:
    """
    Load and index all schema and binding files into a BindingConfig.

    This is the main entry point for the CDA loader. It:
    1. Loads core schema definitions
    2. Loads language-specific bindings
    3. Builds indexed lookup tables
    4. Validates code shapes and uniqueness

    Args:
        core_path: Path to schema/core/ directory
        bindings_path: Path to schema/bindings/ directory

    Returns:
        BindingConfig with all lookups populated

    Raises:
        FileNotFoundError: If required files are missing
        CodeValidationError: If code validation fails
    """
    # Load raw schema and bindings
    core = load_core_schema(core_path)
    bindings = load_bindings(bindings_path)

    config = BindingConfig()

    # === Index core schema ===

    for pos in core.pos_classes:
        validate_code_shape(pos.code, 3, f"POS class '{pos.name}'")
        config.pos_schema[pos.code] = pos

    for flag in core.flags:
        validate_code_shape(flag.code, 4, f"Flag '{flag.name}'")
        config.flag_schema[flag.code] = flag

    for tag_set in core.tag_sets:
        config.tag_schema[tag_set.code] = {}
        for tag in tag_set.tags:
            validate_code_shape(tag.code, 4, f"Tag '{tag.name}' in {tag_set.code}")
            config.tag_schema[tag_set.code][tag.code] = tag

    for pt in core.phrase_types:
        validate_code_shape(pt.code, 4, f"Phrase type '{pt.name}'")
        config.phrase_type_schema[pt.code] = pt

    for mt in core.morphology_types:
        validate_code_shape(mt.code, 4, f"Morphology type '{mt.name}'")
        config.morphology_type_schema[mt.code] = mt

    # === Index POS bindings ===

    for pos_binding in bindings.pos_bindings:
        code = pos_binding.code
        if code not in config.pos_schema:
            raise CodeValidationError(
                f"POS binding references unknown code '{code}'"
            )
        for header in pos_binding.header_variants:
            config.header_to_pos[header.lower()] = code
        for head_pos in pos_binding.head_pos_values:
            config.head_pos_to_pos[head_pos.lower()] = code
        for template in pos_binding.en_templates:
            config.en_template_to_pos[template.lower()] = code
        for suffix in pos_binding.category_suffixes:
            config.category_suffix_to_pos[suffix.lower()] = code

    # === Index flag bindings ===

    for flag_binding in bindings.flag_bindings:
        code = flag_binding.code
        if code not in config.flag_schema:
            raise CodeValidationError(
                f"Flag binding references unknown code '{code}'"
            )
        for template in flag_binding.templates:
            config.template_to_flag[template.lower()] = code
        for suffix in flag_binding.category_suffixes:
            config.category_suffix_to_flag[suffix.lower()] = code

    # === Index tag bindings ===

    for tag_set_binding in bindings.tag_set_bindings:
        for tag_binding in tag_set_binding.tags:
            code = tag_binding.code
            # Validate tag exists in core (check all tag sets)
            found = False
            for tag_set_code, tags in config.tag_schema.items():
                if code in tags:
                    found = True
                    break
            if not found:
                raise CodeValidationError(
                    f"Tag binding references unknown code '{code}'"
                )
            for label in tag_binding.from_labels:
                config.label_to_tag[label.lower()] = code
            for substring in tag_binding.from_category_substrings:
                config.category_substring_to_tag[substring.lower()] = code

    # === Index phrase type bindings ===

    for pt_binding in bindings.phrase_type_bindings:
        code = pt_binding.code
        if code not in config.phrase_type_schema:
            raise CodeValidationError(
                f"Phrase type binding references unknown code '{code}'"
            )
        for header in pt_binding.headers:
            config.header_to_phrase_type[header.lower()] = code
        for template in pt_binding.templates:
            config.template_to_phrase_type[template.lower()] = code
        for suffix in pt_binding.category_suffixes:
            config.category_suffix_to_phrase_type[suffix.lower()] = code

    # === Index morphology bindings ===

    config.morphology_templates = bindings.morphology.templates
    for type_str, code in bindings.morphology.type_mappings.items():
        if code not in config.morphology_type_schema:
            raise CodeValidationError(
                f"Morphology type mapping references unknown code '{code}'"
            )
        config.morphology_type_to_code[type_str.lower()] = code

    # === Index section roles ===

    # Separate literal headers from patterns (%d)
    # Pattern format: %d matches one or more digits
    for h in bindings.section_roles.ignore_headers:
        h_lower = h.lower()
        if "%d" in h_lower:
            # Convert %d to regex pattern (matches one or more digits)
            # First escape any regex special chars, then replace %d with \d+
            # Note: % is not a regex special char, so we replace the literal "%d"
            pattern_str = re.escape(h_lower).replace("%d", r"\d+")
            config.ignore_header_patterns.append(re.compile(f"^{pattern_str}$"))
        else:
            config.ignore_headers.add(h_lower)

    config.label_qualifiers = {q.lower() for q in bindings.section_roles.label_qualifiers}

    config.label_normalizations = {
        k.lower(): v.lower() for k, v in bindings.section_roles.label_normalizations.items()
    }

    # Load definition markers and build compiled regex pattern
    # The YAML maps type → prefix (e.g., "primary" → "#", "secondary" → "##")
    config.definition_markers = bindings.section_roles.definition_markers.copy()
    if config.definition_markers:
        # Build regex pattern that matches all marker types
        # Sort prefixes by length (longest first) so ## matches before #
        prefixes_by_type = [(t, p) for t, p in config.definition_markers.items()]
        prefixes_by_type.sort(key=lambda x: -len(x[1]))  # Longest prefix first

        # Build pattern: ^(###|##|#\*|#:|#)\s*(.*)$
        # Each prefix is escaped and captured, followed by optional space and content
        escaped_prefixes = [re.escape(p) for _, p in prefixes_by_type]
        pattern_str = f"^({'|'.join(escaped_prefixes)})\\s*(.*)$"
        config.definition_marker_pattern = re.compile(pattern_str, re.MULTILINE)

    # === Build derived allowlists ===

    # pos_headers = union of all POS header variants and phrase type headers
    # This is the "allowlist" - headers that should be treated as POS sections
    config.pos_headers = set(config.header_to_pos.keys()) | set(config.header_to_phrase_type.keys())

    # === Validate global uniqueness ===

    validate_code_uniqueness(config)

    return config
