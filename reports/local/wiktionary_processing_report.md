# Wiktionary Processing Report

**Generated:** 2025-11-16 18:14:52 UTC
**Language:** en
**Processing time:** 14m 25s

---

## Summary

| Metric | Value |
|--------|------:|
| **Total entries extracted** | 1326842 |
| **Entries with syllable data** | 29964 |
| **Entries with labels** | 1326842 |
| **Syllable coverage** | 2% |
| **Label coverage** | 100% |

---

## Files Generated

### Input
- **Wiktionary dump:** `/Users/mshonle/Projects/openword-lexicon/data/raw/en/enwiktionary-latest-pages-articles.xml.bz2`
  - Size: 1.4G
  - Download time: See processing.log

### Output
- **Processed JSONL:** `/Users/mshonle/Projects/openword-lexicon/data/intermediate/en/wikt.jsonl`
  - Size: 128M
  - Entries: 1326842
  - Format: One JSON object per line

---

## Quality Checks

### Syllable Data
✅ **PASS** - Syllable data found (29964 entries, 2% coverage)

Expected coverage: 30-50% based on Wiktionary's hyphenation template usage.

### Label Data
✅ **PASS** - Label data found (1326842 entries, 100% coverage)

### Entry Count
✅ **PASS** - Entry count looks reasonable (1326842 entries)

Expected: 500k-800k English words/phrases from Wiktionary.

---

## Sample Entries

First 10 entries from the output file:

```json
{"word": "dictionary", "pos": ["noun", "verb"], "labels": {"temporal": ["rare"], "domain": ["computing"]}, "is_phrase": false, "sources": ["wikt"], "syllables": 4}
{"word": "free", "pos": ["adjective", "adverb", "noun", "verb"], "labels": {"register": ["informal"], "temporal": ["dated", "obsolete"], "domain": ["military"], "region": ["en-GB"]}, "is_phrase": false, "sources": ["wikt"]}
{"word": "thesaurus", "pos": ["noun"], "labels": {"temporal": ["archaic"]}, "is_phrase": false, "sources": ["wikt"], "syllables": 3}
{"word": "encyclopedia", "pos": ["noun"], "labels": {"temporal": ["dated"]}, "is_phrase": false, "sources": ["wikt"], "syllables": 6}
{"word": "portmanteau", "pos": ["adjective", "noun", "verb"], "labels": {"temporal": ["archaic", "dated"], "region": ["en-AU"]}, "is_phrase": false, "sources": ["wikt"]}
{"word": "encyclopaedia", "pos": ["noun"], "labels": {}, "is_phrase": false, "sources": ["wikt"], "syllables": 5}
{"word": "cat", "pos": ["adjective", "noun", "symbol", "verb"], "labels": {"register": ["colloquial", "derogatory", "offensive", "slang", "vulgar"], "temporal": ["archaic", "dated", "historical", "obsolete", "rare"], "domain": ["computing", "military", "nautical"], "region": ["en-IE", "en-US"]}, "is_phrase": false, "sources": ["wikt"], "syllables": 1}
{"word": "gratis", "pos": ["adjective", "adverb", "noun", "verb"], "labels": {}, "is_phrase": false, "sources": ["wikt"], "syllables": 2}
{"word": "word", "pos": ["interjection", "noun", "verb"], "labels": {"register": ["slang"], "temporal": ["archaic", "obsolete", "rare"], "domain": ["computing"]}, "is_phrase": false, "sources": ["wikt"]}
{"word": "livre", "pos": ["adjective", "noun", "verb"], "labels": {"temporal": ["historical", "obsolete"]}, "is_phrase": false, "sources": ["wikt"], "syllables": 2}
```

---

## POS Tag Distribution

Top 20 most common POS tags:

```
961893 noun
228750 verb
189687 adjective
29301 adverb
8835 phrase
5371 interjection
3573 affix
3417 symbol
2351 pronoun
1512 preposition
1193 numeral
 938 conjunction
 923 determiner
 509 particle
 267 letter
 210 article
   6 multiple
```

---

## Next Steps

### If processing succeeded:

1. **Copy the processed file to your remote environment:**
   ```bash
   # On your local machine, compress the file for transfer:
   gzip -c "/Users/mshonle/Projects/openword-lexicon/data/intermediate/en/wikt.jsonl" > wikt.jsonl.gz

   # Transfer to remote (adjust path as needed):
   scp wikt.jsonl.gz remote:/path/to/openword-lexicon/data/intermediate/en/

   # On remote, decompress:
   gunzip -c wikt.jsonl.gz > data/intermediate/en/wikt.jsonl
   ```

2. **Or, if using the same filesystem, the file is already in place!**
   Just continue with the build:
   ```bash
   make build-en
   ```

3. **Expected improvements after rebuild:**
   - Syllable coverage: 0% → 30-50% (~60k-100k words)
   - Label coverage: 0% → 60-80% (register, domain, region tags)
   - Total words: 208k → 800k-1.2M (ENABLE+EOWL+Wiktionary)
   - Multi-word phrases: many more compound terms and idioms

### If processing failed:

Check the log file for errors:
```bash
cat "/Users/mshonle/Projects/openword-lexicon/reports/local/processing.log"
```

Common issues:
- Corrupted download: Re-download with `rm /Users/mshonle/Projects/openword-lexicon/data/raw/en/enwiktionary-latest-pages-articles.xml.bz2` and run again
- Parser errors: Check Python version (requires 3.11+)
- Out of memory: Processing requires ~4-8GB RAM
- Disk space: Ensure ~10GB free space

---

## File Locations

All files are in the project directory structure:

```
data/
├── raw/en/
│   └── enwiktionary-latest-pages-articles.xml.bz2  (1.4G)
└── intermediate/en/
    └── wikt.jsonl  (128M, 1326842 entries)

reports/local/
├── wiktionary_processing_report.md  (this file)
└── processing.log  (detailed processing output)
```

---

## Integration Status

After copying this file to your build environment:

- [ ] Run `uv run python src/openword/wikt_ingest.py`
- [ ] Run `uv run python src/openword/merge_all.py`
- [ ] Run `uv run python src/openword/wordnet_enrich.py --unified`
- [ ] Run `uv run python src/openword/brysbaert_enrich.py --unified`
- [ ] Run `uv run python src/openword/frequency_tiers.py --unified`
- [ ] Run `uv run python src/openword/trie_build.py --unified`
- [ ] Run `uv run python tools/analyze_metadata.py en`
- [ ] Verify syllable coverage in report: `grep "Syllables" reports/metadata_analysis_en.md`

