#!/usr/bin/env python3
"""
Diagnostic script to extract raw wikitext for specific failing entries.
This helps debug why Rust isn't extracting certain features.
"""

import json
import sys
from pathlib import Path


def extract_wikitext_samples(jsonl_path, words, output_dir):
    """Extract raw wikitext for specific words to debug."""

    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    # Load target words
    target_words = set(words)
    found = {}

    with open(jsonl_path) as f:
        for line in f:
            entry = json.loads(line)
            word = entry['word']

            if word in target_words:
                found[word] = entry

                # Save entry to individual file for inspection
                with open(output_dir / f"{word.replace('/', '_')}.json", 'w') as out:
                    json.dump(entry, out, indent=2, ensure_ascii=False)

    # Report
    print(f"Found {len(found)}/{len(target_words)} target words")
    print()

    for word in words:
        if word in found:
            entry = found[word]
            print(f"{'='*60}")
            print(f"Word: {word}")
            print(f"{'='*60}")

            # Show what Python extracted
            if entry.get('morphology'):
                print(f"✓ Morphology: {entry['morphology']['type']}")
                print(f"  Template: {entry['morphology'].get('etymology_template', 'N/A')}")
            else:
                print("✗ Morphology: None")

            if entry.get('labels', {}).get('region'):
                print(f"✓ Regional: {entry['labels']['region']}")
            else:
                print("✗ Regional: None")

            if entry.get('syllables'):
                print(f"✓ Syllables: {entry['syllables']}")
            else:
                print("✗ Syllables: None")

            print()
        else:
            print(f"✗ Word not found: {word}")
            print()


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python extract_diagnostic_samples.py <output.jsonl> <output_dir> [word1] [word2] ...")
        sys.exit(1)

    jsonl_path = sys.argv[1]
    output_dir = sys.argv[2]
    words = sys.argv[3:] if len(sys.argv) > 3 else [
        # Morphology failures
        'dimorphemic', 'footfucker', 'immunochromatographical', 'inspectional', 'inviscid',
        # Regional failures
        'indaba', 'piss-easy', 'sectionman', 'throw-in', 'tulean',
        # Syllable failures
        'apical', 'dimorphemic', 'indaba'
    ]

    extract_wikitext_samples(jsonl_path, words, output_dir)
