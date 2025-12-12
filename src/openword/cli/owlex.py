#!/usr/bin/env python3
"""
OpenWord Lexicon Extended (owlex) - Command-line tool for filtering word lists.

This tool reads YAML/JSON specifications and generates filtered word lists.
Supports a simplified "filters-only" format where the spec body IS the filters.

Output modes:
  --output FILE     Plain text word list (one word per line)
  --enriched FILE   JSONL with aggregated sense data per word
  --jq EXPR         Apply jq expression to each enriched entry (requires jq)
"""

import json
import re
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from collections import defaultdict
import argparse
import logging

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def _load_pos_code_map() -> Dict[str, str]:
    """Load POS variant-to-code mapping from schema/pos.yaml.

    Returns a dict mapping user-friendly names (noun, verb, etc.) to
    their canonical 3-letter codes (NOU, VRB, etc.).

    Also maps codes to themselves for pass-through support.
    """
    # Find schema file relative to this module
    schema_paths = [
        Path(__file__).parent.parent.parent / "schema" / "pos.yaml",  # From src/openword/
        Path("schema/pos.yaml"),  # From project root
    ]

    schema_path = None
    for p in schema_paths:
        if p.exists():
            schema_path = p
            break

    if schema_path is None:
        raise FileNotFoundError(
            "POS schema not found. Expected at schema/pos.yaml relative to project root."
        )

    with open(schema_path) as f:
        schema = yaml.safe_load(f)

    pos_map = {}
    for pos_class in schema["pos_classes"]:
        code = pos_class["code"]
        # Map code to itself (pass-through)
        pos_map[code] = code
        pos_map[code.lower()] = code
        # Map all variants to code
        for variant in pos_class["variants"]:
            pos_map[variant.lower()] = code
    return pos_map


# Lazy-loaded POS code mapping
_POS_CODE_MAP: Optional[Dict[str, str]] = None


def _get_pos_code_map() -> Dict[str, str]:
    """Get the POS code mapping, loading it lazily."""
    global _POS_CODE_MAP
    if _POS_CODE_MAP is None:
        _POS_CODE_MAP = _load_pos_code_map()
    return _POS_CODE_MAP


def normalize_pos_to_code(pos: str) -> Optional[str]:
    """Convert a POS variant name to its canonical 3-letter code.

    Args:
        pos: User-friendly name (noun, verb) or code (NOU, VRB)

    Returns:
        The 3-letter code, or None if not recognized
    """
    pos_map = _get_pos_code_map()
    return pos_map.get(pos.lower())


# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# Lexeme Entry Schema
# =============================================================================
# This schema defines all valid fields in enriched lexeme entries.
# Used for validation and to auto-populate defaults for missing fields.

LEXEME_SCHEMA = {
    # Required fields
    'id': {'type': str, 'required': True},

    # Core metadata (always present after enrichment)
    'frequency_tier': {'type': str, 'default': 'Z'},
    'sources': {'type': list, 'default': []},
    'license_sources': {'type': dict, 'default': {}},
    'sense_count': {'type': int, 'default': 0},
    'sense_offset': {'type': int, 'default': 0},
    'sense_length': {'type': int, 'default': 0},
    'wc': {'type': int, 'default': 1},

    # Optional enrichment fields
    'nsyll': {'type': int, 'default': None},
    'concreteness': {'type': str, 'default': None},  # 'concrete', 'mixed', 'abstract'
    'concreteness_rating': {'type': float, 'default': None},
    'concreteness_sd': {'type': float, 'default': None},
    'spelling_region': {'type': str, 'default': None},  # 'us', 'gb', etc.
    'lexnames': {'type': list, 'default': None},  # WordNet semantic categories
    'morphology': {'type': dict, 'default': None},
    'phrase_type': {'type': str, 'default': None},
    'is_phrase': {'type': bool, 'default': False},
    'labels': {'type': dict, 'default': {}},
    'pos': {'type': list, 'default': []},

    # Lemma/inflection fields (from sense-level aggregation)
    'is_inflected': {'type': bool, 'default': False},
    'is_inflected_any': {'type': bool, 'default': False},

    # Proper noun fields - NOT YET IMPLEMENTED in data pipeline
    # These are defined here for documentation but will fail validation
    # until the enrichment pipeline populates them
    # 'has_common_usage': {'type': bool, 'default': False},
    # 'has_proper_usage': {'type': bool, 'default': False},
}

# Map filter options to the entry fields they require
# Format: {filter_category: {filter_option: [required_fields]}}
FILTER_FIELD_REQUIREMENTS = {
    'proper_noun': {
        'require_common_usage': ['has_common_usage'],
        'exclude_pure_proper_nouns': ['has_common_usage'],
        'allow_proper_usage': ['has_proper_usage'],
    },
    'frequency': {
        'min_tier': ['frequency_tier'],
        'max_tier': ['frequency_tier'],
        'tiers': ['frequency_tier'],
        'min_score': ['frequency_tier'],
        'max_score': ['frequency_tier'],
    },
    'syllables': {
        'min': ['nsyll'],
        'max': ['nsyll'],
        'exact': ['nsyll'],
        'require_syllables': ['nsyll'],
    },
    'concreteness': {
        'categories': ['concreteness'],
        'min_rating': ['concreteness_rating'],
        'max_rating': ['concreteness_rating'],
    },
    'character': {
        'min_length': ['id'],
        'max_length': ['id'],
        'exact_length': ['id'],
        'char_preset': ['id'],
        'allowed_chars': ['id'],
        'must_contain': ['id'],
        'must_not_contain': ['id'],
        'pattern': ['id'],
    },
    'phrase': {
        'min_words': ['wc'],
        'max_words': ['wc'],
        'is_phrase': ['wc'],
        'phrase_type': ['phrase_type'],
    },
    'sources': {
        'include': ['sources'],
        'exclude': ['sources'],
        'enrichment': ['sources'],
    },
    'region': {
        'include': ['spelling_region'],
        'exclude': ['spelling_region'],
        'allow_universal': ['spelling_region'],
    },
    'spelling_region': {
        'include': ['spelling_region'],
        'exclude': ['spelling_region'],
        'allow_universal': ['spelling_region'],
    },
    'labels': {
        'exclude_archaic': ['labels'],
        'exclude_obsolete': ['labels'],
        'exclude_slang': ['labels'],
        'exclude_offensive': ['labels'],
        'exclude_vulgar': ['labels'],
        'require_standard': ['labels'],
    },
    'temporal': {
        'exclude_archaic': ['labels'],
        'exclude_obsolete': ['labels'],
    },
    'lemma': {
        'base_forms_only': ['is_inflected', 'is_inflected_any'],
        'exclude_inflections': ['is_inflected', 'is_inflected_any'],
    },
    'pos': {
        'include': ['pos'],
        'exclude': ['pos'],
    },
}


def get_available_fields() -> Set[str]:
    """Return the set of field names available in the lexeme schema."""
    return set(LEXEME_SCHEMA.keys())


def validate_filter_fields(filters: Dict[str, Any], spec_path: Optional[Path] = None) -> List[str]:
    """
    Validate that filter options don't reference unavailable entry fields.

    Returns a list of error messages (empty if valid).
    """
    errors = []
    available = get_available_fields()

    for filter_category, filter_options in filters.items():
        if not isinstance(filter_options, dict):
            continue

        requirements = FILTER_FIELD_REQUIREMENTS.get(filter_category, {})

        for option_name, option_value in filter_options.items():
            if option_name not in requirements:
                # Unknown filter option - could warn but not error
                continue

            required_fields = requirements[option_name]
            for field in required_fields:
                if field not in available:
                    location = f" in {spec_path}" if spec_path else ""
                    errors.append(
                        f"Filter '{filter_category}.{option_name}' requires field '{field}' "
                        f"which is not available in the lexeme data{location}. "
                        f"This field may not be implemented yet in the data pipeline."
                    )

    return errors


class OwlexFilter:
    """Filter engine for word list specifications."""

    def __init__(self, spec_path: Path):
        """Initialize filter with a specification file."""
        self.spec_path = spec_path
        self.spec = self._load_spec()
        # Tier scores: A (most frequent) = 100, Z (rarest/unknown) = 0
        # Full tier progression: A-Z with scores from 100 down to 0
        self.tier_scores = {
            'A': 100, 'B': 96, 'C': 92, 'D': 88, 'E': 84, 'F': 80,
            'G': 76, 'H': 72, 'I': 68, 'J': 64, 'K': 60, 'L': 56,
            'M': 52, 'N': 48, 'O': 44, 'P': 40, 'Q': 36, 'R': 32,
            'S': 28, 'T': 24, 'U': 20, 'V': 16, 'W': 12, 'X': 8,
            'Y': 4, 'Z': 0
        }

    def _load_spec(self) -> Dict:
        """Load and validate specification.

        Supports:
        - JSON files (.json)
        - YAML files (.yaml, .yml) - requires PyYAML
        - Simplified "filters-only" format where the spec body IS the filters
        """
        suffix = self.spec_path.suffix.lower()

        try:
            with open(self.spec_path) as f:
                if suffix in ('.yaml', '.yml'):
                    if not HAS_YAML:
                        logger.error("YAML support requires PyYAML. Install with: pip install pyyaml")
                        sys.exit(1)
                    spec = yaml.safe_load(f)
                else:
                    spec = json.load(f)
        except (json.JSONDecodeError, yaml.YAMLError) as e:
            logger.error(f"Invalid specification: {e}")
            sys.exit(1)
        except FileNotFoundError:
            logger.error(f"Specification file not found: {self.spec_path}")
            sys.exit(1)

        if spec is None:
            logger.error("Specification is empty")
            sys.exit(1)

        # Detect and normalize spec format
        spec = self._normalize_spec_format(spec)

        # Validate that filters don't reference unavailable fields
        filters = spec.get('filters', {})
        validation_errors = validate_filter_fields(filters, self.spec_path)
        if validation_errors:
            for error in validation_errors:
                logger.error(error)
            sys.exit(1)

        return spec

    def _normalize_spec_format(self, spec: Dict) -> Dict:
        """Normalize various spec formats to internal format.

        Supports:
        1. Legacy format: {"version": "1.0", "distribution": "en", "filters": {...}}
        2. Web builder format: {"version": "1.0", "sources": [...], "filters": [...]}
        3. Simplified format: filters-only body
        4. Operation-first format: include/exclude at top level (recommended)

        Operation-first format example:
            include:
              pos: [noun]
            exclude:
              pos: [phrase]
              register: [vulgar]
            exclude-if-primary:
              pos: [proper noun]
        """
        # Word-level filter keys (properties of the word itself)
        word_filter_keys = {
            'character', 'phrase', 'frequency', 'syllables',
            'concreteness', 'proper_noun', 'lemma'
        }

        # Sense-level operation keys (operation-first format)
        operation_keys = {'include', 'exclude', 'include-if-primary', 'exclude-if-primary'}

        # Sense property keys (what operations apply to)
        sense_property_keys = {'pos', 'register', 'temporal', 'domain', 'region'}

        # Legacy category-first keys
        legacy_sense_keys = {'pos', 'labels', 'temporal', 'policy'}

        # Check for operation-first format
        is_operation_first = (
            'version' not in spec and
            'distribution' not in spec and
            'filters' not in spec and
            any(key in operation_keys for key in spec.keys())
        )

        if is_operation_first:
            return self._normalize_operation_first_format(spec, word_filter_keys, operation_keys, sense_property_keys)

        # Check if this is a simplified "filters-only" format (legacy category-first)
        all_filter_keys = word_filter_keys | legacy_sense_keys | {'sources', 'region'}

        is_simplified = (
            'version' not in spec and
            'distribution' not in spec and
            'filters' not in spec and
            any(key in all_filter_keys for key in spec.keys())
        )

        if is_simplified:
            # Simplified format: the spec body IS the filters
            # Extract sources filter if present, use rest as filters
            normalized = {
                'version': '2.0',
                'distribution': 'en',
                'filters': {}
            }

            for key, value in spec.items():
                if key == 'sources':
                    # Handle sources filter for licensing compliance
                    normalized['_sources_filter'] = value
                else:
                    normalized['filters'][key] = value

            return normalized

        # Legacy format with version
        if 'version' in spec:
            # Support both old format (distribution) and new format (sources array at root)
            if 'distribution' not in spec and 'sources' not in spec:
                # Default to 'en' distribution
                spec['distribution'] = 'en'

            # Normalize web builder format to internal format
            if 'sources' in spec and isinstance(spec['sources'], list) and 'distribution' not in spec:
                spec = self._normalize_new_format(spec)

            return spec

        # Unknown format - try to use as-is with defaults
        logger.warning("Unknown spec format, using defaults")
        return {
            'version': '1.0',
            'distribution': 'en',
            'filters': spec.get('filters', {})
        }

    def _normalize_operation_first_format(
        self,
        spec: Dict,
        word_filter_keys: set,
        operation_keys: set,
        sense_property_keys: set
    ) -> Dict:
        """Transform operation-first format to internal format.

        Operation-first format (input):
            include:
              pos: [noun]
            exclude:
              pos: [phrase]
              register: [vulgar]
            exclude-if-primary:
              pos: [proper noun]
            character:
              exact_length: 5
            phrase:
              max_words: 1

        Internal format (output):
            filters:
              pos:
                include: [noun]
                exclude: [phrase]
                exclude-if-primary: [proper noun]
              labels:
                register:
                  exclude: [vulgar]
              character:
                exact_length: 5
              phrase:
                max_words: 1
        """
        normalized = {
            'version': '2.0',
            'distribution': 'en',
            'filters': {}
        }

        filters = normalized['filters']

        # Process operation keys (include, exclude, etc.)
        for op_key in operation_keys:
            if op_key not in spec:
                continue

            op_content = spec[op_key]
            if not isinstance(op_content, dict):
                continue

            for prop_key, prop_values in op_content.items():
                # Handle sense-level properties
                if prop_key in sense_property_keys:
                    if prop_key == 'pos':
                        # POS goes directly under filters.pos
                        if 'pos' not in filters:
                            filters['pos'] = {}
                        filters['pos'][op_key] = prop_values
                    elif prop_key in {'register', 'temporal', 'domain', 'region'}:
                        # These go under filters.labels.{category}
                        if 'labels' not in filters:
                            filters['labels'] = {}
                        if prop_key not in filters['labels']:
                            filters['labels'][prop_key] = {}
                        filters['labels'][prop_key][op_key] = prop_values

        # Process word-level filter keys (character, phrase, frequency, etc.)
        for key in word_filter_keys:
            if key in spec:
                filters[key] = spec[key]

        # Handle sources filter specially (for licensing)
        if 'sources' in spec:
            if isinstance(spec['sources'], dict):
                normalized['_sources_filter'] = spec['sources']
            else:
                filters['sources'] = spec['sources']

        # Handle temporal at top level (shorthand for labels.temporal)
        if 'temporal' in spec and 'temporal' not in filters.get('labels', {}):
            # Check if it's an operation-style or direct style
            temporal_spec = spec['temporal']
            if isinstance(temporal_spec, dict):
                # Check if it has operation keys directly
                if any(k in operation_keys for k in temporal_spec.keys()):
                    if 'labels' not in filters:
                        filters['labels'] = {}
                    filters['labels']['temporal'] = temporal_spec
                else:
                    # It's a word-level filter config
                    filters['temporal'] = temporal_spec

        return normalized

    def _normalize_new_format(self, spec: Dict) -> Dict:
        """
        Convert web builder format to owlex internal format.

        New format:
          {
            "version": "1.0",
            "sources": ["wiktionary", "eowl"],
            "filters": [
              {"type": "character", "mode": "include", "config": {"minLength": 5}},
              {"type": "syllable", "mode": "include", "config": {"minSyllables": 1, "maxSyllables": 2}}
            ]
          }

        Old format:
          {
            "version": "1.0",
            "distribution": "en",
            "filters": {
              "character": {"min_length": 5},
              "syllables": {"min": 1, "max": 2}
            }
          }
        """
        normalized = spec.copy()

        # Set distribution to 'en' (English build)
        normalized['distribution'] = 'en'

        # Convert filter array to filter object
        if isinstance(spec.get('filters'), list):
            old_filters = {}

            for filter_item in spec['filters']:
                filter_type = filter_item['type']
                filter_mode = filter_item.get('mode', 'include')
                filter_config = filter_item.get('config', {})

                # Convert camelCase config keys to snake_case
                converted_config = self._convert_filter_config(filter_type, filter_config, filter_mode)

                # Merge with existing config for this filter type (in case of multiple filters of same type)
                if filter_type in old_filters:
                    old_filters[filter_type].update(converted_config)
                else:
                    old_filters[filter_type] = converted_config

            normalized['filters'] = old_filters

        return normalized

    def _convert_filter_config(self, filter_type: str, config: Dict, mode: str) -> Dict:
        """Convert camelCase config to snake_case and handle mode."""
        converted = {}

        # Map of camelCase to snake_case
        key_mappings = {
            'minLength': 'min_length',
            'maxLength': 'max_length',
            'minSyllables': 'min',
            'maxSyllables': 'max',
            'minTier': 'min_tier',
            'maxTier': 'max_tier',
            'singleWord': 'max_words',  # singleWord=true means max_words=1
            'multiWord': 'min_words',   # multiWord=true means min_words=2
            'requireSyllables': 'require_syllables',
            'preferBrysbaert': 'prefer_brysbaert',
            'charPreset': 'char_preset',
            'startsWith': 'starts_with',
            'excludeStartsWith': 'exclude_starts_with',
            'endsWith': 'ends_with',
            'excludeEndsWith': 'exclude_ends_with',
            'excludeContains': 'exclude_contains',
        }

        for old_key, value in config.items():
            new_key = key_mappings.get(old_key, old_key)

            # Handle special cases
            if old_key == 'singleWord' and value:
                converted['max_words'] = 1
            elif old_key == 'multiWord' and value:
                converted['min_words'] = 2
            elif old_key == 'exact' and filter_type == 'syllable':
                # exact syllables
                converted['exact'] = value
            else:
                converted[new_key] = value

        # Handle mode for filters that support include/exclude
        if filter_type in ['labels', 'pos', 'concreteness']:
            if mode == 'exclude' and config:
                # For exclude mode, wrap in exclude logic
                # This is a simplification - in practice we'd need to handle this more carefully
                pass

        return converted

    def get_input_file(self) -> Path:
        """Determine input JSONL file based on distribution."""
        dist = self.spec['distribution']

        # Try new lexemes-enriched file first (flat structure with language-prefixed files)
        candidates = [
            Path(f'data/intermediate/{dist}-lexemes-enriched.jsonl'),
            Path(f'data/intermediate/{dist}/entries_tiered.jsonl'),  # Legacy
            Path(f'data/intermediate/{dist}/{dist}_entries_enriched.jsonl'),  # Legacy
        ]

        for path in candidates:
            if path.exists():
                return path

        logger.error(f"No input file found for distribution '{dist}'")
        logger.error(f"Tried: {[str(p) for p in candidates]}")
        logger.error(f"\nPlease build the distribution first:")
        logger.error(f"  make build-{dist}")
        sys.exit(1)

    def filter_entry(self, entry: Dict) -> bool:
        """Check if an entry passes all filters."""
        filters = self.spec.get('filters', {})

        # Character filters
        if not self._check_character_filters(entry, filters.get('character', {})):
            return False

        # Phrase filters
        if not self._check_phrase_filters(entry, filters.get('phrase', {})):
            return False

        # Frequency filters
        if not self._check_frequency_filters(entry, filters.get('frequency', {})):
            return False

        # POS filters
        if not self._check_pos_filters(entry, filters.get('pos', {})):
            return False

        # Concreteness filters
        if not self._check_concreteness_filters(entry, filters.get('concreteness', {})):
            return False

        # Label filters
        if not self._check_label_filters(entry, filters.get('labels', {})):
            return False

        # Temporal filters (explicit, not via policy)
        if not self._check_temporal_filters(entry, filters.get('temporal', {})):
            return False

        # Policy filters (legacy - expanded to label filters)
        if not self._check_policy_filters(entry, filters.get('policy', {})):
            return False

        # Source filters (from filters section)
        if not self._check_source_filters(entry, filters.get('sources', {})):
            return False

        # Source filters (from simplified format's _sources_filter)
        sources_filter = self.spec.get('_sources_filter', {})
        if sources_filter:
            if not self._check_sources_licensing_filter(entry, sources_filter):
                return False

        # Spelling region filters
        if not self._check_spelling_region_filters(entry, filters.get('spelling_region', {})):
            return False

        # Region filters (simplified format - same as spelling_region)
        if not self._check_spelling_region_filters(entry, filters.get('region', {})):
            return False

        # Proper noun filters
        if not self._check_proper_noun_filters(entry, filters.get('proper_noun', {})):
            return False

        # Syllable filters
        if not self._check_syllable_filters(entry, filters.get('syllables', {})):
            return False

        # Lemma/inflection filters
        if not self._check_lemma_filters(entry, filters.get('lemma', {})):
            return False

        return True

    def _check_character_filters(self, entry: Dict, filters: Dict) -> bool:
        """Apply character-level filters."""
        word = entry['id']
        length = len(word)

        # Length constraints
        if 'exact_length' in filters:
            if length != filters['exact_length']:
                return False

        if 'min_length' in filters:
            if length < filters['min_length']:
                return False

        if 'max_length' in filters:
            if length > filters['max_length']:
                return False

        # Character preset validation
        if 'char_preset' in filters and filters['char_preset'] != 'any':
            preset = filters['char_preset']
            if preset == 'standard':
                # Only lowercase letters (a-z)
                if not all(c.islower() and c.isalpha() for c in word):
                    return False
            elif preset == 'contractions':
                # Lowercase letters and apostrophes
                if not all((c.islower() and c.isalpha()) or c == '\'' for c in word):
                    return False
            elif preset == 'alphanumeric':
                # Lowercase letters and digits
                if not all((c.islower() and c.isalpha()) or c.isdigit() for c in word):
                    return False
            elif preset == 'hyphenated':
                # Lowercase letters and hyphens
                if not all((c.islower() and c.isalpha()) or c == '-' for c in word):
                    return False
            elif preset == 'common-punct':
                # Lowercase letters, apostrophes, and hyphens
                if not all((c.islower() and c.isalpha()) or c in '\'-' for c in word):
                    return False

        # Regex pattern support
        if 'pattern' in filters:
            if not re.match(filters['pattern'], word):
                return False

        # Starts with (OR logic - match ANY)
        if 'starts_with' in filters:
            prefixes = filters['starts_with'] if isinstance(filters['starts_with'], list) else [filters['starts_with']]
            if not any(word.startswith(prefix) for prefix in prefixes):
                return False

        # Doesn't start with (exclude ALL)
        if 'exclude_starts_with' in filters:
            prefixes = filters['exclude_starts_with'] if isinstance(filters['exclude_starts_with'], list) else [filters['exclude_starts_with']]
            if any(word.startswith(prefix) for prefix in prefixes):
                return False

        # Ends with (OR logic - match ANY)
        if 'ends_with' in filters:
            suffixes = filters['ends_with'] if isinstance(filters['ends_with'], list) else [filters['ends_with']]
            if not any(word.endswith(suffix) for suffix in suffixes):
                return False

        # Doesn't end with (exclude ALL)
        if 'exclude_ends_with' in filters:
            suffixes = filters['exclude_ends_with'] if isinstance(filters['exclude_ends_with'], list) else [filters['exclude_ends_with']]
            if any(word.endswith(suffix) for suffix in suffixes):
                return False

        # Contains (AND logic - must have ALL)
        if 'contains' in filters:
            sequences = filters['contains'] if isinstance(filters['contains'], list) else [filters['contains']]
            if not all(seq in word for seq in sequences):
                return False

        # Doesn't contain (exclude any of these individual characters)
        if 'exclude_contains' in filters:
            excluded_chars = filters['exclude_contains']
            if any(char in word for char in excluded_chars):
                return False

        # Exclude pattern support
        if 'exclude_pattern' in filters:
            if re.match(filters['exclude_pattern'], word):
                return False

        return True

    def _check_phrase_filters(self, entry: Dict, filters: Dict) -> bool:
        """Apply phrase/word count filters."""
        word_count = entry.get('wc', len(entry['id'].split()))
        phrase_type = entry.get('phrase_type')

        if 'min_words' in filters:
            if word_count < filters['min_words']:
                return False

        if 'max_words' in filters:
            if word_count > filters['max_words']:
                return False

        # is_phrase filter: true means word_count > 1, false means word_count == 1
        if 'is_phrase' in filters:
            if filters['is_phrase'] and word_count == 1:
                return False
            if not filters['is_phrase'] and word_count > 1:
                return False

        # New phrase_type filter: filter by specific phrase type
        if 'phrase_type' in filters:
            if filters['phrase_type'] != phrase_type:
                return False

        return True

    def _check_frequency_filters(self, entry: Dict, filters: Dict) -> bool:
        """Apply frequency tier filters.

        Tier naming follows alphabetical convention:
        - A = most common/frequent
        - Z = rarest/unranked

        Filter semantics:
        - min_tier: Most common tier to include (e.g., "A" = include A and rarer)
        - max_tier: Least common tier to include (e.g., "I" = include I and more common)

        Example: min_tier=A, max_tier=I means "include tiers A through I"
        """
        tier = entry.get('frequency_tier', 'Z')  # Z = extremely rare/unranked
        tier_score = self.tier_scores.get(tier, 0)

        if 'tiers' in filters:
            if tier not in filters['tiers']:
                return False

        # min_tier: the MOST common tier to include
        # Words must be this tier OR less common (lower score is OK)
        if 'min_tier' in filters:
            min_tier_score = self.tier_scores.get(filters['min_tier'], 100)
            if tier_score > min_tier_score:
                return False

        # max_tier: the LEAST common tier to include
        # Words must be this tier OR more common (higher score is OK)
        if 'max_tier' in filters:
            max_tier_score = self.tier_scores.get(filters['max_tier'], 0)
            if tier_score < max_tier_score:
                return False

        if 'min_score' in filters:
            if tier_score < filters['min_score']:
                return False

        return True

    def _normalize_pos_list(self, pos_list: List[str]) -> set:
        """Normalize a list of POS values to 3-letter codes."""
        codes = set()
        for pos in pos_list:
            code = normalize_pos_to_code(pos)
            if code:
                codes.add(code)
            else:
                # If not recognized, try exact match (might be a code already)
                codes.add(pos.upper())
        return codes

    def _check_pos_filters(self, entry: Dict, filters: Dict) -> bool:
        """Apply POS filters.

        Supports both user-friendly names (noun, verb, adjective) and
        3-letter codes (NOU, VRB, ADJ). Filter values are normalized
        to codes before comparison.

        Filter variants:
        - include/exclude: check against ANY sense (current behavior)
        - include-if-primary/exclude-if-primary: check against PRIMARY sense only
        """
        pos_tags = set(entry.get('pos', []))
        primary_sense = entry.get('primary_sense', {})
        primary_pos = primary_sense.get('pos')

        if 'require_pos' in filters and filters['require_pos']:
            if not pos_tags:
                return False

        # include: Entry must have at least one matching POS (any sense)
        if 'include' in filters:
            if not pos_tags:
                return False
            include_codes = self._normalize_pos_list(filters['include'])
            if not any(pos in include_codes for pos in pos_tags):
                return False

        # exclude: Entry must not have any matching POS (any sense)
        if 'exclude' in filters:
            exclude_codes = self._normalize_pos_list(filters['exclude'])
            if any(pos in exclude_codes for pos in pos_tags):
                return False

        # include-if-primary: Primary sense must have one of these POS
        if 'include-if-primary' in filters:
            if not primary_pos:
                return False
            include_codes = self._normalize_pos_list(filters['include-if-primary'])
            if primary_pos not in include_codes:
                return False

        # exclude-if-primary: Primary sense must NOT have any of these POS
        if 'exclude-if-primary' in filters:
            if primary_pos:
                exclude_codes = self._normalize_pos_list(filters['exclude-if-primary'])
                if primary_pos in exclude_codes:
                    return False

        return True

    def _check_concreteness_filters(self, entry: Dict, filters: Dict) -> bool:
        """Apply concreteness filters."""
        concreteness = entry.get('concreteness')

        if 'require_concreteness' in filters and filters['require_concreteness']:
            if not concreteness:
                return False

        if 'values' in filters:
            if not concreteness:
                return False
            if concreteness not in filters['values']:
                return False

        return True

    def _check_label_filters(self, entry: Dict, filters: Dict) -> bool:
        """Apply label filters.

        Filter variants:
        - include/exclude: check against ANY sense (current behavior)
        - include-if-primary/exclude-if-primary: check against PRIMARY sense only
        """
        labels = entry.get('labels', {})
        primary_sense = entry.get('primary_sense', {})
        primary_labels = primary_sense.get('labels', {})

        for label_category in ['register', 'temporal', 'domain', 'region']:
            category_filters = filters.get(label_category, {})
            entry_labels = set(labels.get(label_category, []))
            primary_category_labels = set(primary_labels.get(label_category, []))

            # include: Entry must have at least one of the included labels (any sense)
            if 'include' in category_filters:
                include_set = set(category_filters['include'])
                if not (entry_labels & include_set):
                    return False

            # exclude: Entry must not have any of the excluded labels (any sense)
            if 'exclude' in category_filters:
                exclude_set = set(category_filters['exclude'])
                if entry_labels & exclude_set:
                    return False

            # include-if-primary: Primary sense must have one of these labels
            if 'include-if-primary' in category_filters:
                include_set = set(category_filters['include-if-primary'])
                if not (primary_category_labels & include_set):
                    return False

            # exclude-if-primary: Primary sense must NOT have any of these labels
            if 'exclude-if-primary' in category_filters:
                exclude_set = set(category_filters['exclude-if-primary'])
                if primary_category_labels & exclude_set:
                    return False

        return True

    def _check_policy_filters(self, entry: Dict, filters: Dict) -> bool:
        """Apply policy-level filters (expanded to label checks).

        Supports both v1 format (label names) and v2 format (codes).
        """
        labels = entry.get('labels', {})
        register_labels = set(labels.get('register', []))
        temporal_labels = set(labels.get('temporal', []))
        domain_labels = set(labels.get('domain', []))

        if filters.get('family_friendly', False):
            # Exclude vulgar, offensive, derogatory
            # V1 labels: vulgar, offensive, derogatory
            # V2 codes: RVLG, ROFF, RDEG
            v1_profane = {'vulgar', 'offensive', 'derogatory'}
            v2_profane = {'RVLG', 'ROFF', 'RDEG'}
            if register_labels & (v1_profane | v2_profane):
                return False

        if filters.get('modern_only', False):
            # Exclude archaic, obsolete, dated
            # V1 labels: archaic, obsolete, dated
            # V2 codes: TARC, TOBS, TDAT
            v1_outdated = {'archaic', 'obsolete', 'dated'}
            v2_outdated = {'TARC', 'TOBS', 'TDAT'}
            if temporal_labels & (v1_outdated | v2_outdated):
                return False

        if filters.get('no_jargon', False):
            # Exclude technical domains
            # V1 labels: medical, legal, technical, scientific
            # V2 codes: DMEDI, DLEGA, DTECH, DSCIE (if they exist)
            v1_jargon = {'medical', 'legal', 'technical', 'scientific'}
            v2_jargon = {'DMEDI', 'DLEGA', 'DTECH', 'DSCIE'}
            if domain_labels & (v1_jargon | v2_jargon):
                return False

        return True

    def _check_temporal_filters(self, entry: Dict, filters: Dict) -> bool:
        """Apply temporal filters (archaic, obsolete, dated, etc.).

        This is the explicit version - separate from policy.modern_only.

        Filter variants:
        - include/exclude: check against ANY sense (current behavior)
        - include-if-primary/exclude-if-primary: check against PRIMARY sense only

        Examples:
          temporal:
            exclude: [archaic, obsolete]
          temporal:
            include: [historical]  # Only historical words
          temporal:
            exclude-if-primary: [archaic]  # Only exclude if primary sense is archaic
        """
        if not filters:
            return True

        # Get temporal labels from entry (all senses)
        labels = entry.get('labels', {})
        temporal_labels = set(labels.get('temporal', []))

        # Get temporal labels from primary sense
        primary_sense = entry.get('primary_sense', {})
        primary_labels = primary_sense.get('labels', {})
        primary_temporal = set(primary_labels.get('temporal', []))

        # Include filter - must have at least one of these labels (any sense)
        if 'include' in filters:
            include_set = set(filters['include'])
            if not (temporal_labels & include_set):
                return False

        # Exclude filter - must NOT have any of these labels (any sense)
        if 'exclude' in filters:
            exclude_set = set(filters['exclude'])
            if temporal_labels & exclude_set:
                return False

        # include-if-primary: Primary sense must have one of these labels
        if 'include-if-primary' in filters:
            include_set = set(filters['include-if-primary'])
            if not (primary_temporal & include_set):
                return False

        # exclude-if-primary: Primary sense must NOT have any of these labels
        if 'exclude-if-primary' in filters:
            exclude_set = set(filters['exclude-if-primary'])
            if primary_temporal & exclude_set:
                return False

        return True

    def _check_sources_licensing_filter(self, entry: Dict, sources_filter: Dict) -> bool:
        """Apply sources filter for licensing compliance.

        The simplified format supports:
          sources:
            include: [wordnet, eowl]      # Word must exist in these sources
            enrichment: [frequency]        # Allow using data from these sources

        This enables generating word lists with specific license requirements.
        """
        if not sources_filter:
            return True

        entry_sources = set(entry.get('sources', []))

        # Include filter - word must exist in at least one of these sources
        if 'include' in sources_filter:
            include_set = set(sources_filter['include'])
            if not (entry_sources & include_set):
                return False

        # Note: 'enrichment' field is informational - it doesn't filter words,
        # it just indicates which enrichment data is acceptable to use.
        # The actual enrichment data is always in the entry; this field documents
        # which sources' data the user considers acceptable for their licensing.

        return True

    def _check_source_filters(self, entry: Dict, filters: Dict) -> bool:
        """Apply source filters."""
        sources = set(entry.get('sources', []))

        if 'include' in filters:
            # Entry must have at least one of the included sources
            include_set = set(filters['include'])
            if not (sources & include_set):
                return False

        if 'exclude' in filters:
            # Entry must not have any of the excluded sources
            exclude_set = set(filters['exclude'])
            if sources & exclude_set:
                return False

        return True

    def _check_spelling_region_filters(self, entry: Dict, filters: Dict) -> bool:
        """
        Apply spelling region filters.

        Use cases:
        - US game: include only en-US spellings or universal (no regional marker)
        - UK game: include only en-GB spellings or universal
        - Spellchecker: accept all spellings

        Filter options:
        - region: str - Only include words for this region (e.g., "en-US", "en-GB")
                       Words without spelling_region are considered universal
        - include_universal: bool - Include words without spelling_region (default: true)
        - exclude: list - Exclude words from these regions (e.g., ["en-US"])

        Examples:
        - {"region": "en-US"} - Only US spellings and universal words
        - {"region": "en-GB"} - Only British spellings and universal words
        - {"region": "en-US", "include_universal": false} - Only US spellings, no universal
        - {"exclude": ["en-US"]} - Exclude US spellings, keep everything else
        """
        spelling_region = entry.get('spelling_region')  # None = universal/unspecified
        include_universal = filters.get('include_universal', True)

        # If specific region required
        if 'region' in filters:
            target_region = filters['region']
            if spelling_region is None:
                # Universal word - include if include_universal is true
                return include_universal
            else:
                # Regional word - must match target region
                return spelling_region == target_region

        # Exclude specific regions
        if 'exclude' in filters:
            exclude_regions = set(filters['exclude'])
            if spelling_region and spelling_region in exclude_regions:
                return False

        return True

    def _check_proper_noun_filters(self, entry: Dict, filters: Dict) -> bool:
        """
        Apply proper noun filters.

        Filter options:
          - exclude_pure_proper_nouns: true/false (exclude words with no common usage)
          - require_common_usage: true/false (same as exclude_pure_proper_nouns)
          - allow_proper_usage: true/false (if false, exclude ANY proper noun usage)

        Examples:
          Scrabble (allow "bill", "candy", exclude "Aaron"):
            {"require_common_usage": true}

          Strict common words only (exclude "Bill", "Sun"):
            {"allow_proper_usage": false}
        """
        if not filters:
            return True

        # Check for common usage requirement (Scrabble-style filtering)
        if filters.get('exclude_pure_proper_nouns') or filters.get('require_common_usage'):
            # Must have common usage to pass
            if not entry.get('has_common_usage', False):
                return False

        # Check for strict no-proper-usage filtering
        if 'allow_proper_usage' in filters and not filters['allow_proper_usage']:
            # Must NOT have any proper usage
            if entry.get('has_proper_usage', False):
                return False

        return True

    def _check_syllable_filters(self, entry: Dict, filters: Dict) -> bool:
        """
        Apply syllable count filters.

        Filter options:
          - min: Minimum syllable count (inclusive)
          - max: Maximum syllable count (inclusive)
          - exact: Exact syllable count required
          - require_syllables: If true, exclude words without syllable data

        Syllable data comes from Wiktionary (hyphenation > rhymes > categories).
        Coverage is ~2-3% of entries (~30k words), but these are high-quality.

        Examples:
          Two-syllable words only:
            {"exact": 2, "require_syllables": true}

          Simple words (1-3 syllables):
            {"min": 1, "max": 3}

          Complex words (4+ syllables):
            {"min": 4}
        """
        if not filters:
            return True

        # Delegate to filters module for consistency
        from openword.filters import matches_syllables
        return matches_syllables(
            entry,
            min_syllables=filters.get('min'),
            max_syllables=filters.get('max'),
            exact_syllables=filters.get('exact'),
            require_syllables=filters.get('require_syllables', False)
        )

    def _check_lemma_filters(self, entry: Dict, filters: Dict) -> bool:
        """
        Apply lemma/inflection filters.

        NOTE: Full lemma filtering requires sense-level data. For comprehensive
        lemma-based filtering, use the two-file pipeline in filters.py:
            python -m openword.filters INPUT OUTPUT --senses SENSES --base-forms-only

        Filter options (lexeme-level approximation):
          - base_forms_only: Exclude words that are primarily inflections
                             (Approximated by checking if 'is_inflected_any' is set)
          - exclude_inflected: Same as base_forms_only

        Examples:
          Only base forms (no plurals, verb conjugations, etc.):
            {"base_forms_only": true}
        """
        if not filters:
            return True

        # Check for base forms only filter
        # Note: This is an approximation since lemma data is at sense level
        # For accurate filtering, use the two-file pipeline in filters.py
        if filters.get('base_forms_only') or filters.get('exclude_inflected'):
            # Check if any sense is marked as inflected
            # This field would need to be aggregated from senses during enrichment
            if entry.get('is_inflected_any', False):
                return False

            # Also check legacy single-value field
            if entry.get('is_inflected', False):
                return False

        return True

    def get_senses_file(self) -> Optional[Path]:
        """Determine senses JSONL file based on distribution."""
        dist = self.spec['distribution']

        # Try senses file in flat structure
        candidates = [
            Path(f'data/intermediate/{dist}-senses.jsonl'),
            Path(f'data/intermediate/{dist}/senses.jsonl'),  # Legacy
        ]

        for path in candidates:
            if path.exists():
                return path

        return None

    def _requires_senses_data(self) -> bool:
        """Check if any active filters require senses file data.

        Senses file contains POS, labels (register_tags, temporal_tags, etc.)
        which are NOT in the lexemes file.
        """
        filters = self.spec.get('filters', {})

        # POS filters need senses
        if filters.get('pos'):
            return True

        # Label filters need senses
        if filters.get('labels'):
            return True

        # Temporal filters need senses
        if filters.get('temporal'):
            return True

        # Policy filters expand to label checks
        policy = filters.get('policy', {})
        if policy.get('family_friendly') or policy.get('modern_only') or policy.get('no_jargon'):
            return True

        return False

    def _categorize_codes(self, codes: List[str]) -> Dict[str, List[str]]:
        """Categorize v2 codes into label categories.

        V2 codes use prefixes to indicate category:
        - R??? (4-letter): register codes (RVLG, ROFF, RINF, etc.)
        - T??? (4-letter): temporal codes (TARC, TOBS, TDAT, THIS)
        - D???? (5-letter): domain codes (DMEDI, DCOMP, etc.)
        - EN?? (4-letter): region codes (ENUS, ENGB, ENAU)

        Returns dict with keys: register, temporal, domain, region
        """
        result: Dict[str, List[str]] = {
            'register': [],
            'temporal': [],
            'domain': [],
            'region': [],
        }

        for code in codes:
            if len(code) == 4:
                if code.startswith('R'):
                    result['register'].append(code)
                elif code.startswith('T'):
                    result['temporal'].append(code)
                elif code.startswith('EN'):
                    result['region'].append(code)
            elif len(code) == 5 and code.startswith('D'):
                result['domain'].append(code)

        return result

    def _augment_entry_for_filtering(self, entry: Dict, senses: List[Dict]) -> Dict:
        """Augment a lexeme entry with aggregated senses data for filtering.

        This adds fields that exist in senses but not in lexemes:
        - pos: aggregated POS tags (from all senses)
        - labels: aggregated register/temporal/domain/region labels (from all senses)
        - primary_sense: data from first/primary sense only (for -if-primary filters)

        The primary sense is the first sense in document order from Wiktionary,
        which typically represents the most common/prominent meaning.

        Supports both v1 format (separate tag arrays) and v2 format (unified codes set).
        """
        # Start with a copy of the entry
        augmented = entry.copy()

        if not senses:
            return augmented

        # Aggregate POS from all senses
        pos_set = set()
        register_tags = set()
        temporal_tags = set()
        domain_tags = set()
        region_tags = set()

        for sense in senses:
            if sense.get('pos'):
                pos_set.add(sense['pos'])

            # Check for v2 format (codes set)
            codes = sense.get('codes', [])
            if codes:
                # V2 format: categorize codes into label categories
                categorized = self._categorize_codes(codes)
                register_tags.update(categorized['register'])
                temporal_tags.update(categorized['temporal'])
                domain_tags.update(categorized['domain'])
                region_tags.update(categorized['region'])
            else:
                # V1 format fallback: use separate tag arrays
                if sense.get('register_tags'):
                    register_tags.update(sense['register_tags'])
                if sense.get('temporal_tags'):
                    temporal_tags.update(sense['temporal_tags'])
                if sense.get('domain_tags'):
                    domain_tags.update(sense['domain_tags'])
                if sense.get('region_tags'):
                    region_tags.update(sense['region_tags'])

        # Add aggregated POS (from all senses)
        if pos_set:
            augmented['pos'] = sorted(pos_set)

        # Build labels structure matching filter expectations (from all senses)
        labels = {}
        if register_tags:
            labels['register'] = sorted(register_tags)
        if temporal_tags:
            labels['temporal'] = sorted(temporal_tags)
        if domain_tags:
            labels['domain'] = sorted(domain_tags)
        if region_tags:
            labels['region'] = sorted(region_tags)

        if labels:
            augmented['labels'] = labels

        # Extract primary sense data (first sense in document order)
        primary = senses[0]
        primary_sense = {}

        if primary.get('pos'):
            primary_sense['pos'] = primary['pos']

        # Build primary sense labels
        primary_labels = {}
        primary_codes = primary.get('codes', [])
        if primary_codes:
            # V2 format
            categorized = self._categorize_codes(primary_codes)
            if categorized['register']:
                primary_labels['register'] = categorized['register']
            if categorized['temporal']:
                primary_labels['temporal'] = categorized['temporal']
            if categorized['domain']:
                primary_labels['domain'] = categorized['domain']
            if categorized['region']:
                primary_labels['region'] = categorized['region']
        else:
            # V1 format fallback
            if primary.get('register_tags'):
                primary_labels['register'] = primary['register_tags']
            if primary.get('temporal_tags'):
                primary_labels['temporal'] = primary['temporal_tags']
            if primary.get('domain_tags'):
                primary_labels['domain'] = primary['domain_tags']
            if primary.get('region_tags'):
                primary_labels['region'] = primary['region_tags']

        if primary_labels:
            primary_sense['labels'] = primary_labels

        if primary_sense:
            augmented['primary_sense'] = primary_sense

        return augmented

    def load_senses_by_word(self, senses_path: Path) -> Dict[str, List[Dict]]:
        """Load senses from JSONL file and group by word."""
        senses_by_word: Dict[str, List[Dict]] = defaultdict(list)

        with open(senses_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    sense = json.loads(line)
                    word = sense.get('id')
                    if word:
                        senses_by_word[word].append(sense)
                except json.JSONDecodeError:
                    continue

        return dict(senses_by_word)

    def aggregate_entry_with_senses(self, entry: Dict, senses: List[Dict]) -> Dict:
        """Aggregate an entry with its senses for enriched output.

        Creates a combined view with:
        - Word-level data from lexeme entry
        - Aggregated POS array (unique values)
        - Aggregated lemmas array (unique values)
        - Full senses array with sense-level details
        """
        # Start with word-level data
        result = {
            'id': entry['id'],
            'frequency_tier': entry.get('frequency_tier', 'Z'),
            'sources': entry.get('sources', []),
        }

        # Add optional word-level fields if present
        if 'nsyll' in entry:
            result['nsyll'] = entry['nsyll']
        if 'concreteness' in entry:
            result['concreteness'] = entry['concreteness']

        # Aggregate POS from senses
        pos_set = set()
        lemmas_set = set()
        sense_data = []

        for sense in senses:
            if sense.get('pos'):
                pos_set.add(sense['pos'])

            lemma = sense.get('lemma', entry['id'])
            lemmas_set.add(lemma)

            # Build sense detail object
            sense_detail = {'pos': sense.get('pos')}
            if sense.get('lemma') and sense['lemma'] != entry['id']:
                sense_detail['lemma'] = sense['lemma']
            if sense.get('is_inflected'):
                sense_detail['is_inflected'] = True
            if sense.get('definition'):
                sense_detail['definition'] = sense['definition']

            sense_data.append(sense_detail)

        # Add aggregated arrays
        if pos_set:
            result['pos'] = sorted(pos_set)
        if lemmas_set and lemmas_set != {entry['id']}:
            result['lemmas'] = sorted(lemmas_set)

        # Include senses array if there's meaningful data
        if sense_data:
            result['senses'] = sense_data

        return result

    def calculate_score(self, entry: Dict) -> float:
        """Calculate score for an entry."""
        score = 0.0

        # Frequency score (base)
        tier = entry.get('frequency_tier', 'rare')
        score += self.tier_scores.get(tier, 0)

        # Concreteness bonus
        if entry.get('concreteness') == 'concrete':
            score += 20

        # Length penalty
        word_len = len(entry['id'])
        if word_len > 12:
            score -= 10
        if word_len > 15:
            score -= 10

        # Jargon penalty
        labels = entry.get('labels', {})
        domain_labels = set(labels.get('domain', []))
        if domain_labels & {'medical', 'legal', 'technical', 'scientific'}:
            score -= 30

        return score

    def format_output(self, entries: List[Dict], verbose: bool = False) -> str:
        """Format filtered entries according to output spec."""
        output_config = self.spec.get('output', {})
        output_format = output_config.get('format', 'text')
        include_metadata = output_config.get('include_metadata', False)
        metadata_fields = output_config.get('metadata_fields', [])
        limit = output_config.get('limit')
        sort_by = output_config.get('sort_by', 'alphabetical')

        if verbose and sort_by:
            logger.info(f"Sorting by: {sort_by}")

        # Sort entries
        if sort_by == 'alphabetical':
            entries = sorted(entries, key=lambda e: e['id'])
        elif sort_by == 'score':
            entries = sorted(entries, key=lambda e: self.calculate_score(e), reverse=True)
        elif sort_by == 'frequency':
            # Sort by frequency tier score (highest score = most frequent first)
            entries = sorted(entries, key=lambda e: self.tier_scores.get(e.get('frequency_tier', 'rare'), 0), reverse=True)
            if verbose and len(entries) > 0:
                # Show first few entries with their frequency tiers
                logger.info("First 5 entries after frequency sort:")
                for entry in entries[:5]:
                    tier = entry.get('frequency_tier', 'rare')
                    score = self.tier_scores.get(tier, 0)
                    logger.info(f"  {entry['id']:15} tier={tier:10} score={score}")
        elif sort_by == 'length':
            entries = sorted(entries, key=lambda e: len(e['id']))

        # Apply limit
        if limit:
            entries = entries[:limit]

        # Format output
        if output_format == 'text':
            if include_metadata and metadata_fields:
                lines = []
                for entry in entries:
                    fields = [str(entry.get(field, '')) for field in metadata_fields]
                    lines.append('\t'.join(fields))
                return '\n'.join(lines)
            else:
                return '\n'.join(entry['id'] for entry in entries)

        elif output_format == 'json':
            if include_metadata:
                return json.dumps(entries, indent=2, sort_keys=True)
            else:
                return json.dumps([entry['id'] for entry in entries], indent=2, sort_keys=True)

        elif output_format == 'jsonl':
            lines = []
            for entry in entries:
                if include_metadata:
                    lines.append(json.dumps(entry, sort_keys=True))
                else:
                    lines.append(json.dumps({'id': entry['id']}, sort_keys=True))
            return '\n'.join(lines)

        elif output_format == 'csv':
            if include_metadata and metadata_fields:
                lines = [','.join(metadata_fields)]
                for entry in entries:
                    fields = [str(entry.get(field, '')) for field in metadata_fields]
                    lines.append(','.join(f'"{f}"' for f in fields))
                return '\n'.join(lines)
            else:
                return '\n'.join(entry['id'] for entry in entries)

        elif output_format == 'tsv':
            if include_metadata and metadata_fields:
                lines = ['\t'.join(metadata_fields)]
                for entry in entries:
                    fields = [str(entry.get(field, '')) for field in metadata_fields]
                    lines.append('\t'.join(fields))
                return '\n'.join(lines)
            else:
                return '\n'.join(entry['id'] for entry in entries)

        return '\n'.join(entry['id'] for entry in entries)

    def run(
        self,
        output_path: Optional[Path] = None,
        enriched_path: Optional[Path] = None,
        jq_expr: Optional[str] = None,
        verbose: bool = False
    ) -> int:
        """Run the filter and generate output.

        Args:
            output_path: Path for plain text word list (one word per line)
            enriched_path: Path for enriched JSONL with aggregated sense data
            jq_expr: jq expression to apply to each enriched entry (requires jq)
            verbose: Enable verbose logging
        """
        input_file = self.get_input_file()

        if verbose:
            logger.info(f"Loading specification: {self.spec_path}")
            logger.info(f"Distribution: {self.spec['distribution']}")
            logger.info(f"Input file: {input_file}")

        # Check if senses data is needed for filtering or enriched output
        needs_senses_for_filtering = self._requires_senses_data()
        needs_senses = needs_senses_for_filtering or enriched_path

        # Load senses if needed
        senses_by_word: Dict[str, List[Dict]] = {}
        if needs_senses:
            senses_file = self.get_senses_file()
            if senses_file:
                if verbose:
                    reason = "filtering" if needs_senses_for_filtering else "enriched output"
                    logger.info(f"Loading senses for {reason}: {senses_file}")
                senses_by_word = self.load_senses_by_word(senses_file)
                if verbose:
                    logger.info(f"Loaded senses for {len(senses_by_word):,} words")
            else:
                if needs_senses_for_filtering:
                    logger.warning("Senses file not found - POS/label filters may not work correctly")
                else:
                    logger.warning("Senses file not found - enriched output will have limited data")

        # Read and filter entries
        filtered = []
        total = 0

        with open(input_file) as f:
            for line in f:
                total += 1
                try:
                    entry = json.loads(line)

                    # Augment entry with senses data if needed for filtering
                    if needs_senses_for_filtering:
                        word = entry.get('id', '')
                        senses = senses_by_word.get(word, [])
                        entry_for_filter = self._augment_entry_for_filtering(entry, senses)
                    else:
                        entry_for_filter = entry

                    if self.filter_entry(entry_for_filter):
                        # Store original entry (not augmented) for output
                        filtered.append(entry)
                except json.JSONDecodeError:
                    if verbose:
                        logger.warning(f"Skipping invalid JSON line: {line[:50]}...")

        if verbose:
            logger.info(f"Processed {total:,} entries")
            logger.info(f"Matched {len(filtered):,} entries ({len(filtered) / total * 100:.1f}%)")

            # Show warning if description doesn't match filters
            if self.spec.get('description'):
                desc = self.spec['description'].lower()
                filters = self.spec.get('filters', {})

                # Check for common mismatches
                if 'us' in desc or 'american' in desc:
                    if not filters.get('labels', {}).get('region', {}).get('exclude'):
                        logger.warning("Warning: Description mentions US/American but no region filter is set")
                        logger.warning("  -> Consider adding: filters.labels.region.exclude = ['en-GB']")

                if any(word in desc for word in ['vulgar', 'profan', 'family', 'clean']):
                    if not filters.get('policy', {}).get('family_friendly'):
                        if not filters.get('labels', {}).get('register', {}).get('exclude'):
                            logger.warning("Warning: Description mentions profanity/family-friendly but no filter is set")
                            logger.warning("  -> Consider adding: filters.policy.family_friendly = true")

        # Write enriched output if requested
        if enriched_path:
            enriched_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_enriched_output(filtered, senses_by_word, enriched_path, jq_expr, verbose)

        # Write plain text output if requested
        if output_path:
            output = self.format_output(filtered, verbose)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output + '\n')
            if verbose:
                logger.info(f"Output written to: {output_path}")

        # If neither output specified, write to stdout (legacy behavior)
        if not output_path and not enriched_path:
            output = self.format_output(filtered, verbose)
            print(output)

        return 0

    def _write_enriched_output(
        self,
        filtered: List[Dict],
        senses_by_word: Dict[str, List[Dict]],
        enriched_path: Path,
        jq_expr: Optional[str],
        verbose: bool
    ) -> None:
        """Write enriched JSONL output, optionally filtering through jq."""
        # Aggregate entries with senses
        enriched_entries = []
        for entry in filtered:
            word = entry['id']
            senses = senses_by_word.get(word, [])
            enriched = self.aggregate_entry_with_senses(entry, senses)
            enriched_entries.append(enriched)

        # If jq expression provided, pipe through jq
        if jq_expr:
            self._write_with_jq(enriched_entries, enriched_path, jq_expr, verbose)
        else:
            # Write directly
            with open(enriched_path, 'w', encoding='utf-8') as f:
                for entry in enriched_entries:
                    f.write(json.dumps(entry, sort_keys=True) + '\n')

        if verbose:
            logger.info(f"Enriched output written to: {enriched_path}")

    def _write_with_jq(
        self,
        entries: List[Dict],
        output_path: Path,
        jq_expr: str,
        verbose: bool
    ) -> None:
        """Write entries through jq filter."""
        # Check if jq is available
        if not shutil.which('jq'):
            logger.error("jq not found. Install jq or remove --jq flag.")
            logger.error("  macOS: brew install jq")
            logger.error("  Ubuntu: apt install jq")
            sys.exit(1)

        if verbose:
            logger.info(f"Applying jq filter: {jq_expr}")

        # Build JSONL input
        jsonl_input = '\n'.join(json.dumps(e) for e in entries)

        # Run jq with compact output (-c) for JSONL
        try:
            result = subprocess.run(
                ['jq', '-c', jq_expr],
                input=jsonl_input,
                capture_output=True,
                text=True,
                check=True
            )
            output_path.write_text(result.stdout)
        except subprocess.CalledProcessError as e:
            logger.error(f"jq error: {e.stderr}")
            sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Filter word lists using YAML/JSON specifications',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic: word list only (to stdout)
  owlex wordle.yaml

  # Save word list to file
  owlex wordle.yaml --output words.txt

  # With enriched sidecar JSONL
  owlex kids-nouns.yaml --output words.txt --enriched enriched.jsonl

  # Just enriched JSONL (no plain text)
  owlex kids-nouns.yaml --enriched enriched.jsonl

  # With inline jq projection
  owlex kids-nouns.yaml --enriched syllables.jsonl --jq '{word, syllables}'

  # Morphology lookup
  owlex kids-nouns.yaml --enriched morph.jsonl --jq '{word, pos}'
        """
    )

    parser.add_argument(
        'spec',
        type=Path,
        help='Path to YAML or JSON specification file'
    )

    parser.add_argument(
        '-o', '--output',
        type=Path,
        help='Plain text word list output file (one word per line)'
    )

    parser.add_argument(
        '-e', '--enriched',
        type=Path,
        help='Enriched JSONL output file with aggregated sense data'
    )

    parser.add_argument(
        '--jq',
        type=str,
        metavar='EXPR',
        help='jq expression to apply to each enriched entry (requires jq installed)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    # Validate --jq requires --enriched
    if args.jq and not args.enriched:
        parser.error("--jq requires --enriched output file")

    # Run filter
    filter_engine = OwlexFilter(args.spec)
    return filter_engine.run(
        output_path=args.output,
        enriched_path=args.enriched,
        jq_expr=args.jq,
        verbose=args.verbose
    )


if __name__ == '__main__':
    sys.exit(main())
