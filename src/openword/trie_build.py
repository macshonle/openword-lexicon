#!/usr/bin/env python3
"""
trie_build.py — Build compact MARISA trie from lexeme entries.

Usage:
  uv run python src/openword/trie_build.py \\
      --input LEXEMES.jsonl [--profile PROFILE]

Profiles:
  - full (default): All words from the lexicon
  - game: Pure a-z words only (no hyphens, apostrophes, accents, emojis)

Outputs:
  - data/build/{lang}.trie (full profile)
  - data/build/{lang}-game.trie (game profile)

The trie ordinal equals the line number in the lexeme file (0-indexed),
enabling O(1) metadata lookup by seeking directly to that line.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional, Callable
import sys

import marisa_trie

from openword.progress_display import ProgressDisplay


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# Profile filters - each returns True if word should be included
GAME_PATTERN = re.compile(r'^[a-z]+$')


def filter_game(word: str) -> bool:
    """Game profile: only pure lowercase a-z words."""
    return bool(GAME_PATTERN.match(word))


PROFILES = {
    'full': None,  # No filter - include all words
    'game': filter_game,
}


def build_trie_simple(
    input_path: Path,
    trie_path: Path,
    word_filter: Optional[Callable[[str], bool]] = None,
    profile_name: str = "full"
):
    """
    Build MARISA trie from lexeme file (new two-file pipeline).

    In the two-file pipeline, the lexeme JSONL file IS the metadata.
    Trie ordinal = line number in the lexeme file (0-indexed).
    No separate meta.json is needed.

    Args:
        input_path: Path to lexeme JSONL file
        trie_path: Output path for trie
        word_filter: Optional filter function (returns True to include word)
        profile_name: Name of profile for logging
    """
    logger.info(f"Building trie from {input_path.name} (profile: {profile_name})")

    words = []
    filtered_count = 0
    with ProgressDisplay(f"Loading words ({profile_name})", update_interval=1000) as progress:
        with open(input_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    word = entry['id']

                    # Apply filter if provided
                    if word_filter is None or word_filter(word):
                        words.append(word)
                    else:
                        filtered_count += 1

                    progress.update(Lines=line_num, Words=len(words), Filtered=filtered_count)
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Line {line_num}: {e}")
                    continue

    logger.info(f"  -> Loaded {len(words):,} words")
    if filtered_count > 0:
        logger.info(f"  -> Filtered out {filtered_count:,} words")

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
    parser.add_argument('--profile', choices=list(PROFILES.keys()), default='full',
                        help='Word filter profile (default: full)')
    args = parser.parse_args()

    data_root = Path(__file__).parent.parent.parent / "data"
    build_dir = data_root / "build"

    logger.info("Trie build (MARISA)")
    logger.info(f"  Input: {args.input}")
    logger.info(f"  Profile: {args.profile}")

    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)

    # Output path depends on profile
    if args.profile == 'full':
        trie_path = build_dir / f"{args.language}.trie"
    else:
        trie_path = build_dir / f"{args.language}-{args.profile}.trie"

    word_filter = PROFILES[args.profile]
    build_trie_simple(args.input, trie_path, word_filter, args.profile)

    logger.info("")
    logger.info("Trie build complete")


if __name__ == '__main__':
    main()
