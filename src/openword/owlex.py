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
        self.tier_scores = {
            'top10': 100,
            'top100': 95,
            'top300': 90,
            'top500': 85,
            'top1k': 80,
            'top3k': 70,
            'top10k': 60,
            'top25k': 40,
            'top50k': 20,
            'rare': 5
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
        if 'distribution' not in spec:
            logger.error("Specification missing 'distribution' field")
            sys.exit(1)

        return spec

    def get_input_file(self) -> Path:
        """Determine input JSONL file based on distribution."""
        dist = self.spec['distribution']

        # Try enriched file first, fall back to merged
        candidates = [
            Path(f'data/intermediate/{dist}/{dist}_entries_enriched.jsonl'),
            Path(f'data/intermediate/{dist}/entries_merged.jsonl'),
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

        return True

    def _check_character_filters(self, entry: Dict, filters: Dict) -> bool:
        """Apply character-level filters."""
        word = entry['word']
        length = len(word)

        if 'exact_length' in filters:
            if length != filters['exact_length']:
                return False

        if 'min_length' in filters:
            if length < filters['min_length']:
                return False

        if 'max_length' in filters:
            if length > filters['max_length']:
                return False

        if 'pattern' in filters:
            if not re.match(filters['pattern'], word):
                return False

        if 'starts_with' in filters:
            if not word.startswith(filters['starts_with']):
                return False

        if 'ends_with' in filters:
            if not word.endswith(filters['ends_with']):
                return False

        if 'contains' in filters:
            if filters['contains'] not in word:
                return False

        if 'exclude_pattern' in filters:
            if re.match(filters['exclude_pattern'], word):
                return False

        return True

    def _check_phrase_filters(self, entry: Dict, filters: Dict) -> bool:
        """Apply phrase/word count filters."""
        word = entry['word']
        word_count = len(word.split())
        is_phrase = entry.get('is_phrase', False)

        if 'min_words' in filters:
            if word_count < filters['min_words']:
                return False

        if 'max_words' in filters:
            if word_count > filters['max_words']:
                return False

        if 'is_phrase' in filters:
            if filters['is_phrase'] != is_phrase:
                return False

        return True

    def _check_frequency_filters(self, entry: Dict, filters: Dict) -> bool:
        """Apply frequency tier filters."""
        tier = entry.get('frequency_tier', 'rare')

        if 'tiers' in filters:
            if tier not in filters['tiers']:
                return False

        if 'min_tier' in filters:
            # More restrictive tier (higher in list) is minimum
            min_score = self.tier_scores.get(filters['min_tier'], 0)
            if self.tier_scores.get(tier, 0) < min_score:
                return False

        if 'max_tier' in filters:
            # Less restrictive tier (lower in list) is maximum
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
  owlex filter wordlist-spec.json

  # Save to file
  owlex filter wordlist-spec.json --output kids-words.txt

  # Verbose output
  owlex filter wordlist-spec.json --verbose

  # Create specification interactively
  node tools/wordlist-builder/cli-builder.js

  # Use web interface
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
