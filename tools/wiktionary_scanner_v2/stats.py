"""Statistics collection for the v2 Wiktionary scanner.

Collects empirical data during scanning to help answer questions about:
- Domain tag frequencies
- Senseid template values and their Wikidata QIDs
- Label frequencies (what labels are actually used)
- Template frequencies
- Category frequencies
- POS distribution
- Flag distribution
- Unknown headers and templates

The statistics are written to a separate JSON file from the main output,
providing insight into the actual content of the Wiktionary dump.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional
import json
import re


@dataclass
class ScannerStats:
    """Accumulator for scanner statistics."""

    # Entry counts
    total_pages: int = 0
    total_entries: int = 0
    filtered_entries: int = 0

    # POS distribution
    pos_counts: Counter = field(default_factory=Counter)

    # Flag distribution
    flag_counts: Counter = field(default_factory=Counter)

    # Tag distribution (from labels)
    tag_counts: Counter = field(default_factory=Counter)

    # Label frequencies (raw labels from {{lb|en|...}})
    label_counts: Counter = field(default_factory=Counter)

    # Labels that didn't map to any tag
    unmapped_labels: Counter = field(default_factory=Counter)

    # Domain labels specifically (subset of labels for domain-specific vocabulary)
    domain_label_counts: Counter = field(default_factory=Counter)

    # Senseid values (from {{senseid|en|...}} templates)
    senseid_counts: Counter = field(default_factory=Counter)

    # Senseid QIDs specifically (Q-prefixed Wikidata IDs)
    senseid_qid_counts: Counter = field(default_factory=Counter)

    # Category frequencies (English categories)
    category_counts: Counter = field(default_factory=Counter)

    # Template frequencies (all templates found)
    template_counts: Counter = field(default_factory=Counter)

    # Morphology template frequencies
    morphology_template_counts: Counter = field(default_factory=Counter)

    # Inflection template frequencies
    inflection_template_counts: Counter = field(default_factory=Counter)

    # Alternative form template frequencies
    altform_template_counts: Counter = field(default_factory=Counter)

    # Unknown headers (not in allowlist or ignore list)
    unknown_header_counts: Counter = field(default_factory=Counter)

    # Etymology sources (from {{inh}}, {{bor}}, {{der}} templates)
    etymology_source_counts: Counter = field(default_factory=Counter)

    # Words with syllable counts
    words_with_nsyll: int = 0
    words_without_nsyll: int = 0

    # Words with lemmas
    words_with_lemma: int = 0

    # Words with morphology
    words_with_morphology: int = 0

    # Regional spelling distribution
    spelling_region_counts: Counter = field(default_factory=Counter)

    # Definition depth distribution
    definition_depth_counts: Counter = field(default_factory=Counter)

    # Definition type distribution
    definition_type_counts: Counter = field(default_factory=Counter)

    def record_page(self) -> None:
        """Record that a page was processed."""
        self.total_pages += 1

    def record_entry(
        self,
        pos: str,
        flags: set[str],
        tags: set[str],
        labels: list[str],
        categories: list[str],
        has_nsyll: bool,
        has_lemma: bool,
        has_morphology: bool,
        def_level: int,
        def_type: str,
        spelling_region: Optional[str],
    ) -> None:
        """Record statistics for a single entry."""
        self.total_entries += 1

        # POS
        self.pos_counts[pos] += 1

        # Flags
        for flag in flags:
            self.flag_counts[flag] += 1

        # Tags
        for tag in tags:
            self.tag_counts[tag] += 1

        # Labels
        for label in labels:
            self.label_counts[label] += 1

        # Categories
        for cat in categories:
            self.category_counts[cat] += 1

        # Syllable coverage
        if has_nsyll:
            self.words_with_nsyll += 1
        else:
            self.words_without_nsyll += 1

        # Lemma coverage
        if has_lemma:
            self.words_with_lemma += 1

        # Morphology coverage
        if has_morphology:
            self.words_with_morphology += 1

        # Definition depth
        self.definition_depth_counts[def_level] += 1
        self.definition_type_counts[def_type] += 1

        # Spelling region
        if spelling_region:
            self.spelling_region_counts[spelling_region] += 1

    def record_filtered_entry(self) -> None:
        """Record that an entry was filtered out."""
        self.filtered_entries += 1

    def record_template(self, template_name: str) -> None:
        """Record a template usage."""
        self.template_counts[template_name.lower()] += 1

    def record_inflection_template(self, template_name: str) -> None:
        """Record an inflection template."""
        self.inflection_template_counts[template_name.lower()] += 1

    def record_altform_template(self, template_name: str) -> None:
        """Record an alternative form template."""
        self.altform_template_counts[template_name.lower()] += 1

    def record_morphology_template(self, template_name: str) -> None:
        """Record a morphology template."""
        self.morphology_template_counts[template_name.lower()] += 1

    def record_unmapped_label(self, label: str) -> None:
        """Record a label that didn't map to any tag."""
        self.unmapped_labels[label.lower()] += 1

    def record_domain_label(self, label: str) -> None:
        """Record a domain-specific label."""
        self.domain_label_counts[label.lower()] += 1

    def record_senseid(self, senseid_value: str) -> None:
        """Record a senseid template value."""
        self.senseid_counts[senseid_value] += 1
        # Check if it's a Wikidata QID
        if senseid_value.startswith("Q") and senseid_value[1:].isdigit():
            self.senseid_qid_counts[senseid_value] += 1

    def record_unknown_header(self, header: str) -> None:
        """Record an unknown header."""
        self.unknown_header_counts[header.lower()] += 1

    def record_etymology_source(self, lang_code: str) -> None:
        """Record an etymology source language."""
        self.etymology_source_counts[lang_code.lower()] += 1

    def to_dict(self) -> dict:
        """Convert stats to a dictionary for JSON serialization."""
        return {
            "summary": {
                "total_pages": self.total_pages,
                "total_entries": self.total_entries,
                "filtered_entries": self.filtered_entries,
                "syllable_coverage": {
                    "with_nsyll": self.words_with_nsyll,
                    "without_nsyll": self.words_without_nsyll,
                    "coverage_pct": round(
                        100 * self.words_with_nsyll / max(1, self.total_entries), 2
                    ),
                },
                "lemma_count": self.words_with_lemma,
                "morphology_count": self.words_with_morphology,
            },
            "pos_distribution": dict(self.pos_counts.most_common()),
            "flag_distribution": dict(self.flag_counts.most_common()),
            "tag_distribution": dict(self.tag_counts.most_common()),
            "label_frequencies": {
                "total_unique": len(self.label_counts),
                "top_100": dict(self.label_counts.most_common(100)),
            },
            "unmapped_labels": {
                "total_unique": len(self.unmapped_labels),
                "top_100": dict(self.unmapped_labels.most_common(100)),
            },
            "domain_labels": {
                "total_unique": len(self.domain_label_counts),
                "all": dict(self.domain_label_counts.most_common()),
            },
            "senseid": {
                "total_unique": len(self.senseid_counts),
                "total_qids": len(self.senseid_qid_counts),
                "top_100_values": dict(self.senseid_counts.most_common(100)),
                "top_100_qids": dict(self.senseid_qid_counts.most_common(100)),
            },
            "categories": {
                "total_unique": len(self.category_counts),
                "top_100": dict(self.category_counts.most_common(100)),
            },
            "templates": {
                "total_unique": len(self.template_counts),
                "top_100": dict(self.template_counts.most_common(100)),
            },
            "morphology_templates": dict(self.morphology_template_counts.most_common()),
            "inflection_templates": dict(self.inflection_template_counts.most_common()),
            "altform_templates": dict(self.altform_template_counts.most_common()),
            "unknown_headers": {
                "total_unique": len(self.unknown_header_counts),
                "top_50": dict(self.unknown_header_counts.most_common(50)),
            },
            "etymology_sources": {
                "total_unique": len(self.etymology_source_counts),
                "top_50": dict(self.etymology_source_counts.most_common(50)),
            },
            "spelling_regions": dict(self.spelling_region_counts.most_common()),
            "definition_depth": dict(sorted(self.definition_depth_counts.items())),
            "definition_types": dict(self.definition_type_counts.most_common()),
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert stats to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def write_to_file(self, path: str) -> None:
        """Write stats to a JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())


# Regex patterns for extracting additional statistics
SENSEID_PATTERN = re.compile(r"\{\{senseid\|en\|([^}|]+)", re.IGNORECASE)
ETYMOLOGY_INHERIT_PATTERN = re.compile(r"\{\{(?:inh|inherited)\|en\|([a-z-]+)\|", re.IGNORECASE)
ETYMOLOGY_BORROW_PATTERN = re.compile(r"\{\{(?:bor|borrowed)\|en\|([a-z-]+)\|", re.IGNORECASE)
ETYMOLOGY_DERIVE_PATTERN = re.compile(r"\{\{(?:der|derived)\|en\|([a-z-]+)\|", re.IGNORECASE)


def extract_senseids(text: str) -> list[str]:
    """Extract senseid values from text."""
    return SENSEID_PATTERN.findall(text)


def extract_etymology_sources(text: str) -> list[str]:
    """Extract etymology source languages from text."""
    sources = []
    sources.extend(ETYMOLOGY_INHERIT_PATTERN.findall(text))
    sources.extend(ETYMOLOGY_BORROW_PATTERN.findall(text))
    sources.extend(ETYMOLOGY_DERIVE_PATTERN.findall(text))
    return sources


# Known domain labels for tracking domain-specific vocabulary
# This set should align with schema/bindings/en-wikt.domain_types.yaml
DOMAIN_LABELS = {
    # Sciences (DMATH, DPHYS, DASTL, DGEOL, DCHEM)
    "mathematics", "math", "maths", "set theory", "logic", "algebra",
    "geometry", "calculus", "number theory",
    "physics", "astronomy", "astrophysics", "celestial mechanics", "cosmology",
    "geology", "mineralogy", "petrology", "paleontology", "geomorphology",
    "chemistry",
    # Life Sciences (DBIOL, DANAT, DZOOL, DBOTN, DORGC, DBCHM)
    "biology", "anatomy", "anatomical",
    "zoology", "mammalogy", "ornithology", "herpetology", "ichthyology", "entomology",
    "botany", "mycology", "phycology",
    "organic chemistry", "organic compound",
    "biochemistry", "enzyme", "protein",
    # Medicine (DMEDI)
    "medicine", "medical",
    # Technology (DCOMP)
    "computing", "internet", "programming",
    # Professional domains (DLAWW, DMILL, DNAUT, DAVIA, DFINN, DTRAN, DWEAP)
    "law", "legal",
    "military",
    "nautical",
    "aviation",
    "finance", "banking", "economics", "stock market", "accounting", "business",
    "rail", "railways", "automotive", "shipping", "transport", "transportation",
    "weapons", "firearms", "artillery", "ballistics", "archery",
    # Humanities (DLING, DPHIL, DRELI)
    "linguistics", "grammar", "phonetics", "phonology", "morphology",
    "syntax", "semantics", "pragmatics", "lexicography",
    "philosophy", "ethics", "metaphysics", "epistemology",
    "religion", "theology", "christianity", "islam", "judaism",
    "buddhism", "hinduism", "biblical",
    # Culture & Leisure (DSPRT, DGAMB, DMUSC, DGAST, DFASH, DARCR)
    "sports", "sport", "baseball", "cricket", "soccer", "football",
    "basketball", "tennis", "golf",
    "poker", "card games", "board games", "dice", "gambling", "chess", "backgammon",
    "music", "musical",
    "cooking", "cuisine", "culinary", "beverages", "brewing", "winemaking", "distilling",
    "clothing", "fashion", "textiles", "sewing", "tailoring",
    "architecture", "construction", "building",
}


def is_domain_label(label: str) -> bool:
    """Check if a label is a domain-specific label."""
    return label.lower() in DOMAIN_LABELS
