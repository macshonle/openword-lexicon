#!/bin/bash
# Verification script for OEWN 2024 migration
# Tests WordNet integration, modern vocabulary, and accent handling

set -e

echo "========================================"
echo "OEWN 2024 Migration Verification"
echo "========================================"
echo

echo "1. WordNet word source output"
echo "----------------------------------------"
wc -l data/intermediate/en/wordnet_entries.jsonl
echo

echo "2. WordNet words in final lexicon"
echo "----------------------------------------"
uv run python -c "
import orjson
with open('data/build/en/unified_lexicon.jsonl', 'rb') as f:
    entries = [orjson.loads(line) for line in f]
    wordnet_sourced = [e for e in entries if 'wordnet' in e.get('sources', [])]
    print(f'Total entries: {len(entries):,}')
    print(f'WordNet-sourced: {len(wordnet_sourced):,}')
    print(f'Percentage: {100*len(wordnet_sourced)/len(entries):.1f}%')
"
echo

echo "3. Modern vocabulary test"
echo "----------------------------------------"
uv run python -c "
import orjson
with open('data/build/en/unified_lexicon.jsonl', 'rb') as f:
    entries = {orjson.loads(line)['word']: orjson.loads(line) for line in f}
    test_words = ['selfie', 'cryptocurrency', 'hashtag', 'emoji', 'blog']
    for word in test_words:
        if word in entries:
            sources = entries[word].get('sources', [])
            pos = entries[word].get('pos', 'none')
            print(f'✓ {word}: {pos}, sources: {sources}')
        else:
            print(f'✗ {word}: NOT FOUND')
"
echo

echo "4. Accent normalization test"
echo "----------------------------------------"
uv run python -c "
import orjson
with open('data/build/en/unified_lexicon.jsonl', 'rb') as f:
    entries = {orjson.loads(line)['word']: orjson.loads(line) for line in f}
    test_words = ['café', 'naïve', 'résumé']
    for word in test_words:
        if word in entries:
            print(f'✓ {word}: found')
        else:
            print(f'✗ {word}: NOT FOUND')
"
echo

echo "5. Accent normalization unit tests"
echo "----------------------------------------"
uv run pytest tests/test_accent_normalization.py -v
echo

echo "6. Build statistics summary"
echo "----------------------------------------"
uv run python -c "
import orjson
from collections import Counter

with open('data/build/en/unified_lexicon.jsonl', 'rb') as f:
    entries = [orjson.loads(line) for line in f]

# Count by source
source_counts = Counter()
for e in entries:
    for source in e.get('sources', []):
        source_counts[source] += 1

# Count POS coverage
with_pos = sum(1 for e in entries if e.get('pos'))
with_concreteness = sum(1 for e in entries if e.get('concreteness') is not None)

print('=== Build Statistics ===')
print(f'Total words: {len(entries):,}')
print(f'\nWords by source:')
for source, count in source_counts.most_common():
    print(f'  {source}: {count:,}')
print(f'\nEnrichment coverage:')
print(f'  POS tags: {with_pos:,} ({100*with_pos/len(entries):.1f}%)')
print(f'  Concreteness: {with_concreteness:,} ({100*with_concreteness/len(entries):.1f}%)')
"

echo
echo "========================================"
echo "Verification Complete!"
echo "========================================"
