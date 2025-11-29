#!/usr/bin/env python3
"""
OpenWord Lexicon Extended (owlex) - Command-line tool for filtering word lists.

This tool reads JSON specifications created by the interactive builder and
generates filtered word lists based on the specified criteria.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
import argparse
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class OwlexFilter:
    """Filter engine for word list specifications."""

    def __init__(self, spec_path: Path):
        """Initialize filter with a specification file."""
        self.spec_path = spec_path
        self.spec = self._load_spec()
        # Tier scores: A (most frequent) = 100, Z (rarest/unknown) = 0
        # 12 main tiers (A-L) + Y (rare) + Z (unknown)
        # Scale: A=100, B=92, C=84, ..., L=12, Y=4, Z=0 (~8 points per tier)
        self.tier_scores = {
            'A': 100, 'B': 92, 'C': 84, 'D': 76, 'E': 68, 'F': 60,
            'G': 52, 'H': 44, 'I': 36, 'J': 28, 'K': 20, 'L': 12,
            'Y': 4, 'Z': 0
        }

    def _load_spec(self) -> Dict:
        """Load and validate specification."""
        try:
            with open(self.spec_path) as f:
                spec = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in specification: {e}")
            sys.exit(1)
        except FileNotFoundError:
            logger.error(f"Specification file not found: {self.spec_path}")
            sys.exit(1)

        # Validate required fields
        if 'version' not in spec:
            logger.error("Specification missing 'version' field")
            sys.exit(1)

        # Support both old format (distribution) and new format (sources)
        if 'distribution' not in spec and 'sources' not in spec:
            logger.error("Specification missing 'distribution' or 'sources' field")
            sys.exit(1)

        # Normalize new format to old format for backward compatibility
        if 'sources' in spec and 'distribution' not in spec:
            spec = self._normalize_new_format(spec)

        return spec

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

        # Policy filters (expanded to label filters)
        if not self._check_policy_filters(entry, filters.get('policy', {})):
            return False

        # Source filters
        if not self._check_source_filters(entry, filters.get('sources', {})):
            return False

        # Spelling region filters
        if not self._check_spelling_region_filters(entry, filters.get('spelling_region', {})):
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
        word = entry['word']
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
        word_count = entry.get('word_count', len(entry['word'].split()))
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
        """Apply frequency tier filters."""
        tier = entry.get('frequency_tier', 'Z')  # Z = extremely rare/unranked

        if 'tiers' in filters:
            if tier not in filters['tiers']:
                return False

        if 'min_tier' in filters:
            # More frequent tier (higher score) is minimum
            min_score = self.tier_scores.get(filters['min_tier'], 0)
            if self.tier_scores.get(tier, 0) < min_score:
                return False

        if 'max_tier' in filters:
            # Less frequent tier (lower score) is maximum
            max_score = self.tier_scores.get(filters['max_tier'], 100)
            if self.tier_scores.get(tier, 0) > max_score:
                return False

        if 'min_score' in filters:
            score = self.tier_scores.get(tier, 0)
            if score < filters['min_score']:
                return False

        return True

    def _check_pos_filters(self, entry: Dict, filters: Dict) -> bool:
        """Apply POS filters."""
        pos_tags = set(entry.get('pos', []))

        if 'require_pos' in filters and filters['require_pos']:
            if not pos_tags:
                return False

        if 'include' in filters:
            # Entry must have at least one of the included POS tags
            if not pos_tags:
                return False
            if not any(pos in pos_tags for pos in filters['include']):
                return False

        if 'exclude' in filters:
            # Entry must not have any of the excluded POS tags
            if any(pos in pos_tags for pos in filters['exclude']):
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
        """Apply label filters."""
        labels = entry.get('labels', {})

        for label_category in ['register', 'temporal', 'domain', 'region']:
            category_filters = filters.get(label_category, {})
            entry_labels = set(labels.get(label_category, []))

            if 'include' in category_filters:
                # Entry must have at least one of the included labels
                include_set = set(category_filters['include'])
                if not (entry_labels & include_set):
                    return False

            if 'exclude' in category_filters:
                # Entry must not have any of the excluded labels
                exclude_set = set(category_filters['exclude'])
                if entry_labels & exclude_set:
                    return False

        return True

    def _check_policy_filters(self, entry: Dict, filters: Dict) -> bool:
        """Apply policy-level filters (expanded to label checks)."""
        labels = entry.get('labels', {})
        register_labels = set(labels.get('register', []))
        temporal_labels = set(labels.get('temporal', []))
        domain_labels = set(labels.get('domain', []))

        if filters.get('family_friendly', False):
            # Exclude vulgar, offensive, derogatory
            if register_labels & {'vulgar', 'offensive', 'derogatory'}:
                return False

        if filters.get('modern_only', False):
            # Exclude archaic, obsolete, dated
            if temporal_labels & {'archaic', 'obsolete', 'dated'}:
                return False

        if filters.get('no_jargon', False):
            # Exclude technical domains
            if domain_labels & {'medical', 'legal', 'technical', 'scientific'}:
                return False

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
        word_len = len(entry['word'])
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
            entries = sorted(entries, key=lambda e: e['word'])
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
                    logger.info(f"  {entry['word']:15} tier={tier:10} score={score}")
        elif sort_by == 'length':
            entries = sorted(entries, key=lambda e: len(e['word']))

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
                return '\n'.join(entry['word'] for entry in entries)

        elif output_format == 'json':
            if include_metadata:
                return json.dumps(entries, indent=2, sort_keys=True)
            else:
                return json.dumps([entry['word'] for entry in entries], indent=2, sort_keys=True)

        elif output_format == 'jsonl':
            lines = []
            for entry in entries:
                if include_metadata:
                    lines.append(json.dumps(entry, sort_keys=True))
                else:
                    lines.append(json.dumps({'word': entry['word']}, sort_keys=True))
            return '\n'.join(lines)

        elif output_format == 'csv':
            if include_metadata and metadata_fields:
                lines = [','.join(metadata_fields)]
                for entry in entries:
                    fields = [str(entry.get(field, '')) for field in metadata_fields]
                    lines.append(','.join(f'"{f}"' for f in fields))
                return '\n'.join(lines)
            else:
                return '\n'.join(entry['word'] for entry in entries)

        elif output_format == 'tsv':
            if include_metadata and metadata_fields:
                lines = ['\t'.join(metadata_fields)]
                for entry in entries:
                    fields = [str(entry.get(field, '')) for field in metadata_fields]
                    lines.append('\t'.join(fields))
                return '\n'.join(lines)
            else:
                return '\n'.join(entry['word'] for entry in entries)

        return '\n'.join(entry['word'] for entry in entries)

    def run(self, output_path: Optional[Path] = None, verbose: bool = False) -> int:
        """Run the filter and generate output."""
        input_file = self.get_input_file()

        if verbose:
            logger.info(f"Loading specification: {self.spec_path}")
            logger.info(f"Distribution: {self.spec['distribution']}")
            logger.info(f"Input file: {input_file}")

        # Read and filter entries
        filtered = []
        total = 0

        with open(input_file) as f:
            for line in f:
                total += 1
                try:
                    entry = json.loads(line)
                    if self.filter_entry(entry):
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

        # Format output
        output = self.format_output(filtered, verbose)

        # Write output
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output + '\n')
            if verbose:
                logger.info(f"Output written to: {output_path}")
        else:
            print(output)

        return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Filter word lists using JSON specifications',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate filtered word list
  owlex wordlist-spec.json

  # Save to file
  owlex wordlist-spec.json --output kids-words.txt

  # Verbose output
  owlex wordlist-spec.json --verbose

  # Create specification with web interface
  open tools/wordlist-builder/web-builder.html
        """
    )

    parser.add_argument(
        'spec',
        type=Path,
        help='Path to JSON specification file'
    )

    parser.add_argument(
        '-o', '--output',
        type=Path,
        help='Output file path (default: stdout)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    args = parser.parse_args()

    # Run filter
    filter_engine = OwlexFilter(args.spec)
    return filter_engine.run(args.output, args.verbose)


if __name__ == '__main__':
    sys.exit(main())
