"""
Schema loading for v2 scanner.

Loads and validates YAML schema files from schema/core/ and schema/bindings/.

This module defines dataclasses for both:
- Core schema (language-neutral definitions)
- Bindings (language-specific mappings from Wiktionary to core codes)
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


# =============================================================================
# Core schema dataclasses
# =============================================================================


@dataclass
class PosClass:
    """A part-of-speech class definition from core/pos.yaml."""

    code: str  # 3-letter code (e.g., "NOU", "VRB")
    name: str
    description: str
    short_description: str


@dataclass
class Flag:
    """A boolean flag definition from core/flags.yaml."""

    code: str  # 4-letter code (e.g., "ABRV", "INFL")
    name: str
    description: str
    examples: list[str] = field(default_factory=list)


@dataclass
class Tag:
    """A single tag within a tag set."""

    code: str  # 4-letter code (e.g., "RINF", "TARC")
    name: str
    description: str


@dataclass
class TagSet:
    """A group of related tags from core/tag_sets.yaml."""

    code: str  # 4-letter code (e.g., "REGS", "TEMP")
    name: str
    description: str
    tags: list[Tag] = field(default_factory=list)


@dataclass
class PhraseType:
    """A phrase type definition from core/phrase_types.yaml."""

    code: str  # 4-letter code (e.g., "IDIM", "PRVB")
    name: str
    description: str
    examples: list[str] = field(default_factory=list)


@dataclass
class MorphologyType:
    """A morphology type definition from core/morphology.yaml."""

    code: str  # 4-letter code (e.g., "SIMP", "COMP", "PREF")
    name: str
    description: str


@dataclass
class CoreSchema:
    """Complete core schema loaded from schema/core/."""

    pos_classes: list[PosClass]
    flags: list[Flag]
    tag_sets: list[TagSet]
    phrase_types: list[PhraseType]
    morphology_types: list[MorphologyType]

    def summary(self) -> str:
        """Return a human-readable summary of the loaded schema."""
        total_tags = sum(len(ts.tags) for ts in self.tag_sets)
        return (
            f"  - {len(self.pos_classes)} POS classes\n"
            f"  - {len(self.flags)} flags\n"
            f"  - {len(self.tag_sets)} tag sets ({total_tags} tags total)\n"
            f"  - {len(self.phrase_types)} phrase types\n"
            f"  - {len(self.morphology_types)} morphology types"
        )


# =============================================================================
# Binding dataclasses
# =============================================================================


@dataclass
class PosBinding:
    """POS binding from en-wikt.pos.yaml."""

    code: str  # 3-letter POS code
    header_variants: list[str] = field(default_factory=list)
    head_pos_values: list[str] = field(default_factory=list)
    en_templates: list[str] = field(default_factory=list)
    category_suffixes: list[str] = field(default_factory=list)


@dataclass
class FlagBinding:
    """Flag binding from en-wikt.flags.yaml."""

    code: str  # 4-letter flag code
    name: str
    description: str
    templates: list[str] = field(default_factory=list)
    category_suffixes: list[str] = field(default_factory=list)
    pos_hints: list[str] = field(default_factory=list)


@dataclass
class TagBinding:
    """Tag binding within a tag set from en-wikt.tag_sets.yaml."""

    code: str  # 4-letter tag code
    description: str
    from_labels: list[str] = field(default_factory=list)
    from_category_substrings: list[str] = field(default_factory=list)


@dataclass
class TagSetBinding:
    """Tag set binding from en-wikt.tag_sets.yaml."""

    code: str  # Tag set code (e.g., "REGS", "TEMP")
    tags: list[TagBinding] = field(default_factory=list)


@dataclass
class PhraseTypeBinding:
    """Phrase type binding from en-wikt.phrase_types.yaml."""

    code: str  # 4-letter phrase type code
    name: str
    description: str
    headers: list[str] = field(default_factory=list)
    head_pos_values: list[str] = field(default_factory=list)
    templates: list[str] = field(default_factory=list)
    category_suffixes: list[str] = field(default_factory=list)


@dataclass
class MorphologyTemplate:
    """Morphology template binding from en-wikt.morphology.yaml."""

    name: str
    aliases: list[str] = field(default_factory=list)
    language_param: str = "en"
    roles: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class MorphologyBindings:
    """Morphology bindings from en-wikt.morphology.yaml."""

    type_mappings: dict[str, str] = field(default_factory=dict)  # "compound" → "COMP"
    templates: list[MorphologyTemplate] = field(default_factory=list)


@dataclass
class SectionRoles:
    """Section role definitions from en-wikt.section_roles.yaml."""

    ignore_headers: list[str] = field(default_factory=list)
    label_qualifiers: list[str] = field(default_factory=list)
    label_normalizations: dict[str, str] = field(default_factory=dict)
    definition_markers: dict[str, str] = field(default_factory=dict)


@dataclass
class Bindings:
    """Language-specific bindings loaded from schema/bindings/."""

    pos_bindings: list[PosBinding] = field(default_factory=list)
    flag_bindings: list[FlagBinding] = field(default_factory=list)
    tag_set_bindings: list[TagSetBinding] = field(default_factory=list)
    phrase_type_bindings: list[PhraseTypeBinding] = field(default_factory=list)
    morphology: MorphologyBindings = field(default_factory=MorphologyBindings)
    section_roles: SectionRoles = field(default_factory=SectionRoles)

    def summary(self) -> str:
        """Return a human-readable summary of the loaded bindings."""
        total_tags = sum(len(tsb.tags) for tsb in self.tag_set_bindings)
        return (
            f"  - {len(self.pos_bindings)} POS bindings\n"
            f"  - {len(self.flag_bindings)} flag bindings\n"
            f"  - {len(self.tag_set_bindings)} tag set bindings ({total_tags} tags)\n"
            f"  - {len(self.phrase_type_bindings)} phrase type bindings\n"
            f"  - {len(self.morphology.templates)} morphology templates"
        )


# =============================================================================
# Loading functions
# =============================================================================

CORE_FILES = [
    "pos.yaml",
    "flags.yaml",
    "tag_sets.yaml",
    "phrase_types.yaml",
    "morphology.yaml",
]


def load_core_schema(path: Path) -> CoreSchema:
    """
    Load and validate the core schema from a directory.

    Args:
        path: Path to schema/core/ directory

    Returns:
        CoreSchema with all loaded definitions

    Raises:
        FileNotFoundError: If required files are missing
        ValueError: If schema validation fails
    """
    if not path.is_dir():
        raise FileNotFoundError(f"Core schema directory not found: {path}")

    # Check all required files exist
    missing = [f for f in CORE_FILES if not (path / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing required schema files in {path}: {', '.join(missing)}"
        )

    # Load pos.yaml
    with open(path / "pos.yaml") as f:
        pos_data = yaml.safe_load(f)
    pos_classes = [
        PosClass(
            code=p["code"],
            name=p["name"],
            description=p["description"],
            short_description=p["short_description"],
        )
        for p in pos_data.get("pos_classes", [])
    ]

    # Load flags.yaml
    with open(path / "flags.yaml") as f:
        flags_data = yaml.safe_load(f)
    flags = [
        Flag(
            code=fl["code"],
            name=fl["name"],
            description=fl["description"].strip(),
            examples=fl.get("examples", []),
        )
        for fl in flags_data.get("flags", [])
    ]

    # Load tag_sets.yaml
    with open(path / "tag_sets.yaml") as f:
        tag_sets_data = yaml.safe_load(f)
    tag_sets = []
    for ts in tag_sets_data.get("tag_sets", []):
        tags = [
            Tag(
                code=t["code"],
                name=t["name"],
                description=t["description"],
            )
            for t in ts.get("tags", [])
        ]
        tag_sets.append(
            TagSet(
                code=ts["code"],
                name=ts["name"],
                description=ts["description"],
                tags=tags,
            )
        )

    # Load phrase_types.yaml
    with open(path / "phrase_types.yaml") as f:
        phrase_types_data = yaml.safe_load(f)
    phrase_types = [
        PhraseType(
            code=pt["code"],
            name=pt["name"],
            description=pt["description"].strip(),
            examples=pt.get("examples", []),
        )
        for pt in phrase_types_data.get("phrase_types", [])
    ]

    # Load morphology.yaml
    with open(path / "morphology.yaml") as f:
        morph_data = yaml.safe_load(f)
    morphology_types = [
        MorphologyType(
            code=mt["code"],
            name=mt["name"],
            description=mt["description"].strip(),
        )
        for mt in morph_data.get("morphology_types", [])
    ]

    return CoreSchema(
        pos_classes=pos_classes,
        flags=flags,
        tag_sets=tag_sets,
        phrase_types=phrase_types,
        morphology_types=morphology_types,
    )


def load_bindings(path: Path) -> Bindings:
    """
    Load binding files from a directory.

    Args:
        path: Path to schema/bindings/ directory

    Returns:
        Bindings with all parsed binding structures

    Raises:
        FileNotFoundError: If directory doesn't exist
    """
    if not path.is_dir():
        raise FileNotFoundError(f"Bindings directory not found: {path}")

    bindings = Bindings()

    # Load POS bindings (en-wikt.pos.yaml)
    pos_file = path / "en-wikt.pos.yaml"
    if pos_file.exists():
        with open(pos_file) as f:
            pos_data = yaml.safe_load(f)
        for code, binding in pos_data.get("pos_bindings", {}).items():
            bindings.pos_bindings.append(
                PosBinding(
                    code=code,
                    header_variants=binding.get("header_variants", []),
                    head_pos_values=binding.get("head_pos_values", []),
                    en_templates=binding.get("en_templates", []),
                    category_suffixes=binding.get("category_suffixes", []),
                )
            )

    # Load flag bindings (en-wikt.flags.yaml)
    flags_file = path / "en-wikt.flags.yaml"
    if flags_file.exists():
        with open(flags_file) as f:
            flags_data = yaml.safe_load(f)
        for code, binding in flags_data.get("flags", {}).items():
            bindings.flag_bindings.append(
                FlagBinding(
                    code=code,
                    name=binding.get("name", ""),
                    description=binding.get("description", ""),
                    templates=binding.get("templates", []),
                    category_suffixes=binding.get("category_suffixes", []),
                    pos_hints=binding.get("pos_hints", []),
                )
            )

    # Load tag set bindings (en-wikt.tag_sets.yaml)
    tags_file = path / "en-wikt.tag_sets.yaml"
    if tags_file.exists():
        with open(tags_file) as f:
            tags_data = yaml.safe_load(f)
        for set_code, set_binding in tags_data.get("tag_set_bindings", {}).items():
            tag_bindings = []
            for tag in set_binding.get("tags", []):
                tag_bindings.append(
                    TagBinding(
                        code=tag["code"],
                        description=tag.get("description", ""),
                        from_labels=tag.get("from_labels", []),
                        from_category_substrings=tag.get("from_category_substrings", []),
                    )
                )
            bindings.tag_set_bindings.append(
                TagSetBinding(code=set_code, tags=tag_bindings)
            )

    # Load phrase type bindings (en-wikt.phrase_types.yaml)
    phrase_file = path / "en-wikt.phrase_types.yaml"
    if phrase_file.exists():
        with open(phrase_file) as f:
            phrase_data = yaml.safe_load(f)
        for code, binding in phrase_data.get("phrase_type_bindings", {}).items():
            bindings.phrase_type_bindings.append(
                PhraseTypeBinding(
                    code=code,
                    name=binding.get("name", ""),
                    description=binding.get("description", ""),
                    headers=binding.get("headers", []),
                    head_pos_values=binding.get("head_pos_values", []),
                    templates=binding.get("templates", []),
                    category_suffixes=binding.get("category_suffixes", []),
                )
            )

    # Load morphology bindings (en-wikt.morphology.yaml)
    morph_file = path / "en-wikt.morphology.yaml"
    if morph_file.exists():
        with open(morph_file) as f:
            morph_data = yaml.safe_load(f)
        bindings.morphology = MorphologyBindings(
            type_mappings=morph_data.get("type_mappings", {}),
            templates=[
                MorphologyTemplate(
                    name=t["name"],
                    aliases=t.get("aliases", []),
                    language_param=t.get("language_param", "en"),
                    roles=t.get("roles", []),
                    notes=t.get("notes", ""),
                )
                for t in morph_data.get("templates", [])
            ],
        )

    # Load section roles (en-wikt.section_roles.yaml)
    roles_file = path / "en-wikt.section_roles.yaml"
    if roles_file.exists():
        with open(roles_file) as f:
            roles_data = yaml.safe_load(f)
        bindings.section_roles = SectionRoles(
            ignore_headers=roles_data.get("ignore_headers", []),
            label_qualifiers=roles_data.get("label_qualifiers", []),
            label_normalizations=roles_data.get("label_normalizations", {}),
            definition_markers=roles_data.get("definition_markers", {}),
        )

    return bindings
