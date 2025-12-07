#!/usr/bin/env python3
"""
export_lemma_groups.py — Export lemma metadata from sense-level data.

Generates two complementary lemma files:
1. {lang}-lemmas.json.gz: Inflected word → base form mapping
   {"cats": "cat", "running": "run", "went": "go"}

2. {lang}-lemma-groups.json.gz: Base form → all inflected forms
   {"cat": ["cat", "cats"], "go": ["go", "goes", "went", "going", "gone"]}

These enable:
- Filtering to base forms only (exclude inflections)
- Grouping word families together (lemma + all inflected forms)
- Supporting irregular inflection (via Wiktionary templates)

Usage:
  uv run python src/openword/export_lemma_groups.py \\
      --senses SENSES.jsonl [--output-dir OUTPUT_DIR] [--gzip]

The script reads from the senses file (not lexemes) because lemma
information is stored at the sense level to handle cases where one
word has multiple lemmas (e.g., "left" as past tense of "leave" vs
"left" as a standalone adjective).
"""

import gzip
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set

from openword.progress_display import ProgressDisplay

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def extract_lemmas_from_senses(senses_path: Path) -> Dict[str, Set[str]]:
    """
    Extract lemma relationships from senses file.

    For each word that has a lemma field, record the mapping.
    A word can map to multiple lemmas if different senses have different lemmas.

    Returns:
        Dict mapping word -> set of lemmas for that word
    """
    word_lemmas: Dict[str, Set[str]] = defaultdict(set)

    with ProgressDisplay("Reading senses", update_interval=50000) as progress:
        with open(senses_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    word = entry.get('id')
                    lemma = entry.get('lemma')

                    # Only record if lemma exists and differs from word
                    if word and lemma and lemma != word:
                        word_lemmas[word].add(lemma)

                    if line_num % 50000 == 0:
                        progress.update(Senses=line_num, Words=len(word_lemmas))

                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Line {line_num}: {e}")
                    continue

    return word_lemmas


def get_primary_lemma(lemmas: Set[str]) -> str:
    """
    Select the primary lemma when a word has multiple.

    Strategy: Use the alphabetically first lemma for consistency.
    This ensures deterministic output across runs.

    Args:
        lemmas: Set of possible lemmas for a word

    Returns:
        The selected primary lemma
    """
    return min(lemmas)


def build_lemma_groups(word_lemmas: Dict[str, Set[str]]) -> Dict[str, List[str]]:
    """
    Build reverse index from lemma -> list of inflected forms.

    Each lemma maps to a list of words that have it as their lemma.
    The base form (lemma itself) is included first if it exists as a word.

    Args:
        word_lemmas: Mapping of word -> set of lemmas

    Returns:
        Dict mapping lemma -> sorted list of forms (base form first if present)
    """
    lemma_forms: Dict[str, Set[str]] = defaultdict(set)

    # Build reverse index: lemma -> words that inflect from it
    for word, lemmas in word_lemmas.items():
        for lemma in lemmas:
            lemma_forms[lemma].add(word)

    # Convert to sorted lists with base form first
    result = {}
    for lemma, forms in lemma_forms.items():
        forms_list = sorted(forms)

        # If the lemma itself is in the forms list, move it to front
        # (This happens when lemma exists as a standalone word)
        if lemma in forms_list:
            forms_list.remove(lemma)
            forms_list.insert(0, lemma)

        # Add lemma as first element if not already present
        # (The lemma is the base form, even if not in our inflected words list)
        if lemma not in forms_list:
            forms_list.insert(0, lemma)

        result[lemma] = forms_list

    return result


def write_json_output(data: dict, output_path: Path, use_gzip: bool = False) -> int:
    """
    Write dictionary to JSON file, optionally gzipped.

    Returns file size in bytes.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_bytes = json.dumps(data, separators=(',', ':'), ensure_ascii=False).encode('utf-8')

    if use_gzip:
        output_path = output_path.with_suffix('.json.gz')
        with gzip.open(output_path, 'wb', compresslevel=9) as f:
            f.write(json_bytes)
    else:
        with open(output_path, 'wb') as f:
            f.write(json_bytes)

    return output_path.stat().st_size


def export_lemma_metadata(
    senses_path: Path,
    output_dir: Path,
    language: str = 'en',
    use_gzip: bool = False
) -> tuple:
    """
    Export both lemma metadata files.

    Returns:
        Tuple of (lemmas_count, groups_count)
    """
    logger.info(f"Reading senses from: {senses_path}")

    # Extract word -> lemmas mapping from senses
    word_lemmas = extract_lemmas_from_senses(senses_path)
    logger.info(f"Found {len(word_lemmas):,} words with lemma data")

    # Build primary lemma mapping (word -> single lemma)
    # For words with multiple lemmas, select the primary one
    lemmas_map = {}
    for word, lemmas in word_lemmas.items():
        lemmas_map[word] = get_primary_lemma(lemmas)

    # Build lemma groups (lemma -> list of forms)
    lemma_groups = build_lemma_groups(word_lemmas)

    # Export lemmas.json (inflected -> lemma)
    lemmas_path = output_dir / f"{language}-lemmas.json"
    lemmas_size = write_json_output(lemmas_map, lemmas_path, use_gzip)
    if use_gzip:
        lemmas_path = lemmas_path.with_suffix('.json.gz')

    logger.info(f"Exported {lemmas_path.name}: {len(lemmas_map):,} entries ({lemmas_size / 1024:.1f} KB)")

    # Export lemma-groups.json (lemma -> [forms])
    groups_path = output_dir / f"{language}-lemma-groups.json"
    groups_size = write_json_output(lemma_groups, groups_path, use_gzip)
    if use_gzip:
        groups_path = groups_path.with_suffix('.json.gz')

    logger.info(f"Exported {groups_path.name}: {len(lemma_groups):,} groups ({groups_size / 1024:.1f} KB)")

    return len(lemmas_map), len(lemma_groups)


def main():
    """Main export pipeline."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Export lemma metadata from sense-level data'
    )
    parser.add_argument('--senses', type=Path, required=True,
                        help='Input senses JSONL file')
    parser.add_argument('--output-dir', type=Path,
                        help='Output directory (default: data/build)')
    parser.add_argument('--language', default='en',
                        help='Language code for output filenames (default: en)')
    parser.add_argument('--gzip', action='store_true',
                        help='Compress output with gzip')
    args = parser.parse_args()

    # Verify input exists
    if not args.senses.exists():
        logger.error(f"Senses file not found: {args.senses}")
        return 1

    # Determine output directory
    if args.output_dir:
        output_dir = args.output_dir
    else:
        data_root = Path(__file__).parent.parent.parent / "data"
        output_dir = data_root / "build"

    logger.info("Lemma metadata export")
    logger.info(f"  Senses: {args.senses}")
    logger.info(f"  Output: {output_dir}")
    logger.info(f"  Compression: {'gzip' if args.gzip else 'none'}")
    logger.info("")

    lemmas_count, groups_count = export_lemma_metadata(
        args.senses,
        output_dir,
        args.language,
        args.gzip
    )

    logger.info("")
    logger.info("=" * 60)
    logger.info("LEMMA EXPORT SUMMARY")
    logger.info("=" * 60)
    logger.info(f"  Lemma mappings: {lemmas_count:,}")
    logger.info(f"  Lemma groups: {groups_count:,}")
    logger.info("=" * 60)

    return 0


if __name__ == '__main__':
    sys.exit(main())
