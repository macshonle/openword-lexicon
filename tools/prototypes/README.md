# Wiktionary Parser Prototypes

Experimental alternative to wiktextract for faster, simpler Wiktionary processing.

## Problem

Current pipeline uses `wiktextract` with Lua evaluation:
- ⏱️  Very slow (hours)
- ⚠️  Thousands of UTF-8 errors
- 🐘 Heavy dependencies
- ❌ Filters out contractions
- 🔧 Overkill for our needs

## Solution

Simple XML parser with regex patterns:
- ⚡ 10-100x faster
- ✅ No Lua errors
- 🪶 Lightweight
- ✅ Can include contractions
- 🎯 Exactly what we need

## Files

### `wiktionary_simple_parser.py`

Fast XML parser that extracts:
- Words/phrases (page titles)
- POS tags (section headers)
- Labels ({{lb}} templates + categories)
- Multi-word detection

**Usage:**
```bash
# Parse full dump
python wiktionary_simple_parser.py \
  enwiktionary-latest-pages-articles.xml.bz2 \
  wikt_simple.jsonl

# Test on first 1000 entries
python wiktionary_simple_parser.py \
  enwiktionary-latest-pages-articles.xml.bz2 \
  wikt_simple_test.jsonl \
  --limit 1000
```

**Output format:**
```json
{
  "word": "example",
  "pos": ["noun", "verb"],
  "labels": {
    "register": ["informal"],
    "temporal": ["archaic"]
  },
  "is_phrase": false,
  "sources": ["wikt"]
}
```

### `compare_wikt_extractions.py`

Validates simple parser against wiktextract output.

**Usage:**
```bash
python compare_wikt_extractions.py \
  data/intermediate/plus/wikt.jsonl \
  data/intermediate/plus/wikt_simple.jsonl
```

**Shows:**
- Word coverage percentage
- Metadata match rates
- Examples of differences
- Quality assessment

## Testing Workflow

1. **Get Wiktionary dump:**
   ```bash
   make fetch-plus
   ```

2. **Run both parsers:**
   ```bash
   # Old way (slow, with Lua)
   make fetch-post-process-plus

   # New way (fast, no Lua) - test first 10k
   python tools/prototypes/wiktionary_simple_parser.py \
     data/raw/plus/enwiktionary-latest-pages-articles.xml.bz2 \
     data/intermediate/plus/wikt_simple.jsonl \
     --limit 10000
   ```

3. **Compare outputs:**
   ```bash
   python tools/prototypes/compare_wikt_extractions.py \
     data/intermediate/plus/wikt.jsonl \
     data/intermediate/plus/wikt_simple.jsonl
   ```

4. **Evaluate:**
   - If coverage >95% → consider switching
   - If coverage <95% → improve regex patterns
   - Check speed improvement
   - Check error rates

## Performance Expectations

Based on similar parsers:

| Metric | wiktextract | Simple Parser | Improvement |
|--------|-------------|---------------|-------------|
| Time | ~2 hours | ~5 minutes | 24x |
| Memory | ~2 GB | ~200 MB | 10x |
| Errors | Thousands | Rare | 100x |
| Coverage | 100%* | 95%+ | -5% |

*Of complex data we don't use

## Implementation Path

### Phase 1: Prototype (Done)
- ✅ Basic XML parser
- ✅ Regex patterns for labels
- ✅ Comparison tool

### Phase 2: Validation
- Run on full dump
- Measure coverage
- Identify gaps
- Refine patterns

### Phase 3: Integration
- Add to Makefile
- Update documentation
- Make it default

### Phase 4: Optimization (Optional)
- Rewrite in Rust/Go if needed
- Parallel processing
- Streaming output

## Key Regex Patterns

```python
# POS headers
r'^===+\s*(.+?)\s*===+\s*$'
# Matches: ===Noun===, ====Proper noun====

# Context labels
r'\{\{(?:lb|label|context)\|en\|([^}]+)\}\}'
# Matches: {{lb|en|informal}}, {{label|en|obsolete|computing}}

# Categories
r'\[\[Category:English\s+([^\]]+)\]\]'
# Matches: [[Category:English informal terms]]
```

## Extending

To add support for:

**New labels:**
```python
REGISTER_LABELS.add('new_label')
```

**New POS tags:**
```python
POS_MAP['new pos'] = 'mapped_pos'
```

**Custom extraction:**
```python
def extract_custom_field(text: str):
    pattern = r'...'
    return re.findall(pattern, text)
```

## Contractions Bonus

Simple parser can include contractions:

```python
def is_contraction(word: str) -> bool:
    return "'" in word

# No special filtering - just include them!
```

Unlike wiktextract which filters "non-lemma" forms, we can keep everything we want.

## References

- See `docs/WIKTIONARY_ALTERNATIVES.md` for full analysis
- See `reports/wiktionary_analysis.md` for current extraction stats
- MediaWiki XML: https://www.mediawiki.org/wiki/Help:Export
- Wiktionary templates: https://en.wiktionary.org/wiki/Category:Form-of templates

## Decision Criteria

**Use simple parser if:**
- ✅ Coverage >95%
- ✅ Speed >10x improvement
- ✅ Error rate <1%
- ✅ Can include contractions

**Keep wiktextract if:**
- ❌ Significant data loss
- ❌ Complex templates critical
- ❌ Marginal performance gain

**Current recommendation:** Test on full dump and measure!
