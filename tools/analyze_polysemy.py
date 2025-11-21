#!/usr/bin/env python3
"""
Investigate how parsers handle polysemy (multiple meanings/entries).

This checks:
1. Multiple Etymology sections (creates separate entries)
2. Multiple POS under one Etymology (currently merged?)
3. Regional/context variants (currently merged into labels?)
"""

import json

def analyze_polysemy():
    # Load all entries and group by word
    word_entries = {}

    print("Loading Rust entries...")
    with open('/tmp/wikt-rust-full.jsonl') as f:
        for line in f:
            e = json.loads(line)
            word = e['word']
            if word not in word_entries:
                word_entries[word] = []
            word_entries[word].append(e)

    # Find words with multiple entries
    multi_entry_words = {word: entries for word, entries in word_entries.items() if len(entries) > 1}

    print(f"\nTotal unique words: {len(word_entries):,}")
    print(f"Words with multiple entries: {len(multi_entry_words):,} ({len(multi_entry_words)/len(word_entries)*100:.2f}%)")

    # Sample analysis
    print("\n" + "="*80)
    print("SAMPLE: Words with multiple entries")
    print("="*80)

    for word in sorted(multi_entry_words.keys())[:10]:
        entries = multi_entry_words[word]
        print(f"\n{word.upper()} ({len(entries)} entries):")
        for i, entry in enumerate(entries, 1):
            pos = ', '.join(entry.get('pos', []))
            labels = entry.get('labels', {})
            is_abbr = entry.get('is_abbreviation', False)
            is_vulgar = entry.get('is_vulgar', False)
            is_informal = entry.get('is_informal', False)
            is_regional = entry.get('is_regional', False)

            print(f"  Entry {i}:")
            print(f"    POS: {pos if pos else '(none)'}")
            if is_abbr:
                print(f"    is_abbreviation: True")
            if is_vulgar:
                print(f"    is_vulgar: True")
            if is_informal:
                print(f"    is_informal: True")
            if is_regional:
                print(f"    is_regional: True")
                print(f"    regions: {labels.get('region', [])}")
            if labels.get('register'):
                print(f"    register: {labels['register']}")

    # Analyze "taffy" specifically
    print("\n" + "="*80)
    print("SPECIFIC CASE: taffy (the 'taffy problem')")
    print("="*80)

    if 'taffy' in word_entries:
        for i, entry in enumerate(word_entries['taffy'], 1):
            print(f"\nEntry {i}:")
            print(json.dumps(entry, indent=2, sort_keys=True))
    else:
        print("'taffy' not found in dataset")

    # Check other interesting polysemous words
    print("\n" + "="*80)
    print("OTHER INTERESTING CASES")
    print("="*80)

    interesting = ['sat', 'sun', 'may', 'march', 'turkey', 'polish', 'bat', 'bank']
    for word in interesting:
        if word in multi_entry_words:
            entries = multi_entry_words[word]
            print(f"\n{word}: {len(entries)} entries")
            for i, e in enumerate(entries, 1):
                pos = ', '.join(e.get('pos', []))
                is_abbr = e.get('is_abbreviation')
                is_proper = e.get('is_proper_noun')
                print(f"  {i}. {pos} (abbr={is_abbr}, proper={is_proper})")

if __name__ == '__main__':
    analyze_polysemy()
