#!/usr/bin/env python3
"""
Normalize Wiktionary scanner output into two flat tables:
- en-lexeme.jsonl: Word-level properties (one row per unique word)
- en-aggregate-senses.jsonl: Sense-level properties (deduplicated by projection)

The scanner outputs one entry per sense (definition line). This script:
1. Groups entries by word
2. Extracts word-level properties into lexeme entries
3. Deduplicates senses by projection (pos, tags, flags)
4. Writes both files with offset/length linking
"""

import json
import argparse
from pathlib import Path
from typing import Iterator, Dict, List, Any, Tuple
from collections import defaultdict


def read_jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    """Read JSONL file line by line."""
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: Path, entries: Iterator[Dict[str, Any]]) -> int:
    """Write entries to JSONL file, return count."""
    count = 0
    with open(path, 'w', encoding='utf-8') as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False, separators=(',', ':')) + '\n')
            count += 1
    return count


def sense_projection(sense: Dict[str, Any]) -> Tuple:
    """
    Create a hashable projection of sense-level properties for deduplication.
    Two senses with the same projection are considered duplicates.
    """
    return (
        sense.get('pos', 'unknown'),
        tuple(sorted(sense.get('register_tags', []))),
        tuple(sorted(sense.get('region_tags', []))),
        tuple(sorted(sense.get('domain_tags', []))),
        tuple(sorted(sense.get('temporal_tags', []))),
        sense.get('is_abbreviation', False),
        sense.get('is_inflected', False),
        sense.get('is_proper_noun', False),
    )


def aggregate_word_senses(
    word: str,
    senses: List[Dict[str, Any]],
    current_sense_offset: int
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Aggregate all senses for a word into:
    - lexeme entry (word-level properties)
    - deduplicated sense entries

    Returns (lexeme_entry, sense_entries)
    """
    # Extract word-level properties (take first non-null)
    syllables = next((s.get('syllables') for s in senses if s.get('syllables') is not None), None)
    morphology = next((s.get('morphology') for s in senses if s.get('morphology')), None)
    word_count = senses[0].get('word_count', 1)
    phrase_type = next((s.get('phrase_type') for s in senses if s.get('phrase_type')), None)
    is_phrase = senses[0].get('is_phrase', False)
    spelling_region = next((s.get('spelling_region') for s in senses if s.get('spelling_region')), None)

    # Deduplicate senses by projection
    seen_projections = set()
    unique_senses = []

    for sense in senses:
        proj = sense_projection(sense)

        if proj not in seen_projections:
            seen_projections.add(proj)

            # Create sense entry with only sense-level fields
            sense_entry = {
                'word': word,
                'pos': sense.get('pos', 'unknown'),
            }

            # Add tag arrays only if non-empty
            for tag_field in ['register_tags', 'region_tags', 'domain_tags', 'temporal_tags']:
                tags = sense.get(tag_field, [])
                if tags:
                    sense_entry[tag_field] = sorted(tags)

            # Add boolean flags only if True
            if sense.get('is_abbreviation', False):
                sense_entry['is_abbreviation'] = True
            if sense.get('is_inflected', False):
                sense_entry['is_inflected'] = True
            if sense.get('is_proper_noun', False):
                sense_entry['is_proper_noun'] = True

            unique_senses.append(sense_entry)

    # Create lexeme entry
    lexeme = {
        'word': word,
        'word_count': word_count,
        'sense_count': len(senses),  # Original sense count before deduplication
        'sense_offset': current_sense_offset,
        'sense_length': len(unique_senses),
    }

    # Add optional fields only if present
    if syllables is not None:
        lexeme['syllables'] = syllables
    if is_phrase:
        lexeme['is_phrase'] = True
    if phrase_type:
        lexeme['phrase_type'] = phrase_type
    if morphology:
        lexeme['morphology'] = morphology
    if spelling_region:
        lexeme['spelling_region'] = spelling_region

    return lexeme, unique_senses


def normalize_wiktionary(
    input_path: Path,
    lexeme_path: Path,
    senses_path: Path,
    verbose: bool = False
) -> Tuple[int, int, int]:
    """
    Transform sorted Wiktionary output into normalized lexeme + senses tables.

    Reads: wikt-sorted.jsonl (one line per sense, sorted by word)
    Outputs:
        - en-lexeme.jsonl (one line per unique word)
        - en-aggregate-senses.jsonl (deduplicated senses)

    Returns: (lexeme_count, sense_count, original_sense_count)
    """
    lexeme_entries = []
    all_sense_entries = []

    current_word = None
    current_senses = []
    current_sense_offset = 0

    original_sense_count = 0

    for entry in read_jsonl(input_path):
        word = entry.get('word', '')
        original_sense_count += 1

        if word != current_word:
            if current_word is not None:
                # Finalize previous word
                lexeme, senses = aggregate_word_senses(
                    current_word,
                    current_senses,
                    current_sense_offset
                )
                lexeme_entries.append(lexeme)
                all_sense_entries.extend(senses)
                current_sense_offset += len(senses)

            current_word = word
            current_senses = []

        current_senses.append(entry)

    # Handle last word
    if current_word is not None and current_senses:
        lexeme, senses = aggregate_word_senses(
            current_word,
            current_senses,
            current_sense_offset
        )
        lexeme_entries.append(lexeme)
        all_sense_entries.extend(senses)

    # Write output files
    lexeme_count = write_jsonl(lexeme_path, iter(lexeme_entries))
    sense_count = write_jsonl(senses_path, iter(all_sense_entries))

    if verbose:
        print(f"Lexemes written: {lexeme_count}")
        print(f"Senses written: {sense_count}")
        print(f"Original senses: {original_sense_count}")
        print(f"Deduplication ratio: {original_sense_count / max(sense_count, 1):.2f}x")
        print(f"Avg senses/word: {sense_count / max(lexeme_count, 1):.2f}")

    return lexeme_count, sense_count, original_sense_count


def main():
    parser = argparse.ArgumentParser(
        description='Normalize Wiktionary scanner output into lexeme + senses tables'
    )
    parser.add_argument(
        '--input',
        type=Path,
        default=Path('data/intermediate/en/wikt-sorted.jsonl'),
        help='Input sorted JSONL file from scanner'
    )
    parser.add_argument(
        '--lexeme-output',
        type=Path,
        default=Path('data/intermediate/en/en-lexeme.jsonl'),
        help='Output lexeme JSONL file'
    )
    parser.add_argument(
        '--senses-output',
        type=Path,
        default=Path('data/intermediate/en/en-aggregate-senses.jsonl'),
        help='Output senses JSONL file'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Print statistics'
    )

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}")
        return 1

    # Ensure output directory exists
    args.lexeme_output.parent.mkdir(parents=True, exist_ok=True)
    args.senses_output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Input: {args.input}")
    print(f"Lexeme output: {args.lexeme_output}")
    print(f"Senses output: {args.senses_output}")
    print()

    lexeme_count, sense_count, original_count = normalize_wiktionary(
        args.input,
        args.lexeme_output,
        args.senses_output,
        verbose=args.verbose
    )

    print()
    print("=" * 60)
    print(f"Lexemes: {lexeme_count:,}")
    print(f"Aggregate senses: {sense_count:,}")
    print(f"Original senses: {original_count:,}")
    print(f"Compression: {original_count / max(sense_count, 1):.2f}x")
    print("=" * 60)

    return 0


if __name__ == '__main__':
    exit(main())
