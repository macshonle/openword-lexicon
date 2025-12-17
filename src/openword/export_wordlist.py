#!/usr/bin/env python3
"""
export_wordlist.py — Export trie to plain text for JavaScript consumption.

Reads:
  - data/build/{lang}.trie

Outputs:
  - data/build/{lang}-wordlist.txt (one word per line)
"""

import argparse
import logging
import os
from pathlib import Path

import marisa_trie


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def export_trie_to_wordlist(trie_path: Path, output_path: Path):
    """Export MARISA trie to plain text wordlist."""
    logger.info(f"Loading trie from {trie_path}")

    trie = marisa_trie.Trie()
    trie.load(str(trie_path))

    logger.info(f"Exporting {len(trie):,} words to {output_path}")

    with open(output_path, 'w', encoding='utf-8') as f:
        for word in trie:
            f.write(f"{word}\n")

    logger.info(f"Exported to {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Export trie to plain text wordlist')
    parser.add_argument('--lang', default=os.environ.get('LEXICON_LANG', 'en'),
                        help='Language code (default: en or $LEXICON_LANG)')
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent.parent
    lang = args.lang

    # Export language-specific trie (flat structure with language-prefixed files)
    build_dir = project_root / "data" / "build"
    lang_trie = build_dir / f"{lang}.trie"
    lang_output = build_dir / f"{lang}-wordlist.txt"

    if lang_trie.exists():
        export_trie_to_wordlist(lang_trie, lang_output)
    else:
        logger.error(f"Trie not found: {lang_trie}")
        logger.info("Run 'make build-en' first to generate the trie.")


if __name__ == '__main__':
    main()
