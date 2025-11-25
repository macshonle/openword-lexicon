#!/usr/bin/env python3
"""
trie_build.py — Build compact MARISA trie from lexeme entries.

Usage:
  uv run python src/openword/trie_build.py \\
      --input data/intermediate/en/en-lexeme-enriched.jsonl

Outputs:
  - data/build/{lang}/{lang}.trie (MARISA trie)

The trie ordinal equals the line number in the lexeme file (0-indexed),
enabling O(1) metadata lookup by seeking directly to that line.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict
import sys

import marisa_trie
import orjson

from openword.progress_display import ProgressDisplay


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def build_trie_simple(input_path: Path, trie_path: Path):
    """
    Build MARISA trie from lexeme file (new two-file pipeline).

    In the two-file pipeline, the lexeme JSONL file IS the metadata.
    Trie ordinal = line number in the lexeme file (0-indexed).
    No separate meta.json is needed.
    """
    logger.info(f"Building trie from {input_path.name}")

    words = []
    with ProgressDisplay(f"Loading words from {input_path.name}", update_interval=1000) as progress:
        with open(input_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    words.append(entry['word'])
                    progress.update(Lines=line_num, Words=len(words))
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Line {line_num}: {e}")
                    continue

    logger.info(f"  -> Loaded {len(words):,} words")

    # Build trie
    logger.info("  Building MARISA trie...")
    trie = marisa_trie.Trie(words)

    # Save trie
    trie_path.parent.mkdir(parents=True, exist_ok=True)
    trie.save(str(trie_path))

    trie_size_kb = trie_path.stat().st_size / 1024
    logger.info(f"  Trie saved: {trie_path} ({trie_size_kb:.1f} KB)")
    logger.info(f"  Word count: {len(trie):,}")


def main():
    """Main trie build pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description='Build MARISA trie from lexeme entries')
    parser.add_argument('--input', type=Path, required=True,
                        help='Input JSONL file (lexeme entries)')
    parser.add_argument('--language', default='en',
                        help='Language code for output path (default: en)')
    args = parser.parse_args()

    data_root = Path(__file__).parent.parent.parent / "data"
    build_dir = data_root / "build"

    logger.info("Trie build (MARISA)")
    logger.info(f"  Input: {args.input}")

    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)

    # Output to language build dir
    lang_dir_build = build_dir / args.language
    trie_path = lang_dir_build / f"{args.language}.trie"

    build_trie_simple(args.input, trie_path)

    logger.info("")
    logger.info("Trie build complete")


if __name__ == '__main__':
    main()
