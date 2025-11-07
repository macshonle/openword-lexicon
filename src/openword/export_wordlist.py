#!/usr/bin/env python3
"""
export_wordlist.py — Export trie to plain text for JavaScript consumption.

Reads:
  - data/build/core/core.trie

Outputs:
  - data/build/core/wordlist.txt (one word per line)
"""

import logging
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

    logger.info(f"✓ Exported to {output_path}")


def main():
    project_root = Path(__file__).parent.parent.parent

    # Export core trie
    core_trie = project_root / "data" / "build" / "core" / "core.trie"
    core_output = project_root / "data" / "build" / "core" / "wordlist.txt"

    if core_trie.exists():
        export_trie_to_wordlist(core_trie, core_output)

    # Export plus trie
    plus_trie = project_root / "data" / "build" / "plus" / "plus.trie"
    plus_output = project_root / "data" / "build" / "plus" / "wordlist.txt"

    if plus_trie.exists():
        export_trie_to_wordlist(plus_trie, plus_output)


if __name__ == '__main__':
    main()
