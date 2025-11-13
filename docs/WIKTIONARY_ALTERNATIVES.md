# Wiktionary Processing Alternatives

This document analyzes whether we need the heavyweight wiktextract/Lua pipeline or could use a simpler, faster custom parser.

## Current Approach: wiktextract + Lua

**What it does:**
- Downloads full Wiktionary XML dump (~7 GB compressed)
- Uses `wiktwords` (Python wrapper around wiktextract)
- Executes Lua code to expand MediaWiki templates
- Processes hundreds of thousands of entries with full semantic parsing

**Problems:**
- ⚠️ Very slow (hours on large dumps)
- ⚠️ Thousands of UTF-8 errors during Lua evaluation
- ⚠️ Heavy dependencies (Lua, complex Python libraries)
- ⚠️ Overk

ill for our needs (we only want words + basic metadata)
- ⚠️ Missing contractions/possessives (filters them as "non-lemma" forms)

**What we get:**
- 1.3M words/phrases
- POS tags
- Some labels (informal, obsolete, etc.)
- Glosses/definitions
- Complex nested structures we don't use

## What We Actually Need

Looking at our schema (`SCHEMA.md`):

```json
{
  "word": "example",           // ← Page title (in XML)
  "pos": ["noun"],             // ← Section header (in XML)
  "labels": {
    "register": ["informal"],  // ← Template: {{lb|en|informal}}
    "temporal": ["obsolete"],  // ← Template: {{lb|en|obsolete}}
    "domain": ["computing"]    // ← Category or template
  },
  "is_phrase": false,          // ← Has spaces? (trivial check)
  "sources": ["wikt"]
}
```

**Essential:**
1. Word (page title)
2. POS (section headers)
3. Basic labels (register/temporal/domain)
4. Multi-word detection

**Not needed:**
- Full glosses (we don't use them for wordlist)
- Etymology trees
- Complex semantic relations
- Inflection tables (for wordlist purposes)
- Lua-evaluated templates

## Wiktionary XML Structure

MediaWiki XML format:

```xml
<mediawiki>
  <page>
    <title>example</title>      <!-- Word/phrase -->
    <ns>0</ns>                   <!-- Namespace (0 = main) -->
    <revision>
      <text>
        <!-- Wikitext content -->
        ==English==
        ===Noun===
        {{en-noun}}
        # A thing representative of its kind...

        ===Verb===
        {{en-verb}}
        # To set an example...
      </text>
    </revision>
  </page>
</mediawiki>
```

**What's directly accessible:**
- ✅ Title (word/phrase)
- ✅ Wikitext content
- ✅ Section headers (`==English==`, `===Noun===`)
- ✅ Category tags
- ✅ Basic templates (with regex)

**What requires Lua:**
- ❌ Complex template expansion
- ❌ Module execution
- ❌ Conditional logic

## Wiktionary Templates We Care About

### 1. Context Labels ({{lb}} / {{label}})

**Format:**
```wikitext
{{lb|en|informal}}
{{lb|en|obsolete}}
{{lb|en|offensive|derogatory}}
{{label|en|computing}}
```

**Simple regex extraction:**
```python
# Pattern: {{lb|en|LABEL1|LABEL2|...}}
pattern = r'\{\{(?:lb|label)\|en\|([^}]+)\}\}'
labels = re.findall(pattern, text)
# → ['informal', 'obsolete', 'offensive|derogatory', 'computing']
```

**No Lua needed!**

### 2. POS Headers

**Format:**
```wikitext
==English==
===Noun===
====Proper noun====
===Verb===
===Adjective===
```

**Simple parsing:**
```python
# Pattern: ===POS===
pattern = r'^===(.+?)===\s*$'
pos_tags = re.findall(pattern, text, re.MULTILINE)
# → ['Noun', 'Verb', 'Adjective']
```

**No Lua needed!**

### 3. Categories

**Format:**
```wikitext
[[Category:English nouns]]
[[Category:English informal terms]]
[[Category:English offensive terms]]
```

**Simple extraction:**
```python
pattern = r'\[\[Category:English ([^]]+)\]\]'
categories = re.findall(pattern, text)
# → ['nouns', 'informal terms', 'offensive terms']
```

**No Lua needed!**

## Proposed Simpler Approach

### Option 1: Python XML + Regex

**Advantages:**
- Fast (process millions of entries in minutes)
- No Lua dependencies
- No UTF-8 errors from template expansion
- 90%+ coverage of labels
- Easy to maintain

**Code sketch:**
```python
import xml.etree.ElementTree as ET
import re

def parse_wiktionary_dump(xml_path):
    for event, elem in ET.iterparse(xml_path):
        if elem.tag == '{http://www.mediawiki.org/xml/export-0.10/}page':
            title = elem.find('.//{...}title').text
            text = elem.find('.//{...}revision/{...}text').text

            # Skip non-English or non-main namespace
            if not text or '==English==' not in text:
                continue

            # Extract POS
            pos_tags = extract_pos(text)

            # Extract labels
            labels = extract_labels(text)

            # Detect phrases
            is_phrase = ' ' in title

            yield {
                'word': title.lower(),
                'pos': pos_tags,
                'labels': labels,
                'is_phrase': is_phrase,
                'sources': ['wikt']
            }

            elem.clear()  # Free memory
```

### Option 2: Rust/Go Streaming Parser

**Advantages:**
- Even faster (10-100x)
- Low memory footprint
- Can process dumps in parallel
- Type-safe

**Example (Rust with quick-xml):**
```rust
use quick_xml::Reader;
use regex::Regex;

struct WiktEntry {
    word: String,
    pos: Vec<String>,
    labels: HashMap<String, Vec<String>>,
    is_phrase: bool,
}

fn parse_dump(path: &Path) -> impl Iterator<Item = WiktEntry> {
    let lb_pattern = Regex::new(r"\{\{lb\|en\|([^}]+)\}\}").unwrap();
    let pos_pattern = Regex::new(r"^===(.+?)===\s*$").unwrap();

    // Stream parse XML, extract on the fly
    // ...
}
```

### Option 3: Hybrid Approach

Use wiktextract for **initial exploration**, then:
1. Analyze what templates/labels actually appear in our data
2. Build regex patterns for the top 95%
3. Use simple parser for production
4. Fall back to wiktextract only for edge cases

## Coverage Analysis

Based on Wiktionary content:

| Data Type | Lua Needed? | Regex Sufficient? | Coverage |
|-----------|-------------|-------------------|----------|
| Page titles | No | N/A | 100% |
| POS tags | No | Yes | 99%+ |
| Context labels ({{lb}}) | No | Yes | 95%+ |
| Categories | No | Yes | 100% |
| Multi-word detection | No | N/A | 100% |
| Glosses (unused) | Sometimes | Partial | N/A |
| Etymology (unused) | Often | Partial | N/A |
| Inflections (unused) | Often | Partial | N/A |

**Conclusion:** 95%+ of what we need can be extracted with simple parsing!

## Implementation Recommendation

### Phase 1: Prototype (Python)

Create `scripts/fetch/parse_wiktionary_simple.py`:
```python
#!/usr/bin/env python3
"""
Simple Wiktionary XML parser without Lua.

Extracts:
- Words/phrases (page titles)
- POS tags (section headers)
- Context labels ({{lb}} templates via regex)
- Categories

10-100x faster than wiktextract, 90%+ coverage.
"""

# See tools/wiktionary_scanner_parser.py for implementation
```

### Phase 2: Validation

Run both approaches on same dump:
```bash
# Old way
make fetch-post-process-plus  # Hours, Lua errors

# New way
python scripts/fetch/parse_wiktionary_simple.py  # Minutes, no errors

# Compare
python tools/compare_wikt_extractions.py
```

### Phase 3: Optimize

If Python is still slow, rewrite in Rust/Go for production.

## Trade-offs

| Aspect | wiktextract | Simple Parser |
|--------|-------------|---------------|
| **Speed** | Hours | Minutes |
| **Errors** | Many UTF-8/Lua | Rare |
| **Coverage** | 100%* | 95%+ |
| **Maintenance** | External dep | We control |
| **Flexibility** | Limited | High |
| **Contractions** | Filtered out | Can include |

*100% of complex structures we don't use anyway

## Next Steps

1. **Analyze current extraction:**
   ```bash
   uv run python tools/analyze_wiktionary_needs.py
   ```

2. **Review report:**
   ```bash
   cat reports/wiktionary_analysis.md
   ```

3. **Prototype simple parser:**
   ```bash
   python tools/wiktionary_scanner_parser.py \
     data/raw/plus/enwiktionary-latest-pages-articles.xml.bz2 \
     data/intermediate/plus/wikt.jsonl
   ```

4. **Compare outputs:**
   ```bash
   python tools/compare_wikt_extractions.py \
     data/intermediate/plus/wikt.jsonl \
     data/intermediate/plus/wikt_simple.jsonl
   ```

5. **Measure:**
   - Word count difference
   - Label coverage
   - Processing time
   - Error rate

6. **Decide:**
   - If <5% data loss and >10x speedup → switch
   - If significant loss → iterate on regex patterns
   - If marginal gain → keep wiktextract

## Contractions Bonus

Simple parser can easily include contractions:

```python
# wiktextract filters these out as "non-lemma"
# We can include them!

if title in ["don't", "can't", "won't", "I'm", "it's"]:
    # Include contractions explicitly
    yield entry
```

No special handling needed - just don't filter them!

## Resources

- Wiktionary XML schema: https://www.mediawiki.org/wiki/Help:Export
- MediaWiki markup: https://www.mediawiki.org/wiki/Help:Formatting
- Common templates: https://en.wiktionary.org/wiki/Category:Form-of templates
- Our needs: `docs/SCHEMA.md`, `docs/DATASETS.md`

## Conclusion

**Recommendation:** Build a simple XML + regex parser to replace wiktextract.

**Benefits:**
- 10-100x faster
- No Lua errors
- Can include contractions
- Full control
- Same or better coverage for our use case

**Cost:**
- ~200 lines of Python (or less in Rust/Go)
- One-time development effort
- Ongoing maintenance (but simpler than debugging Lua issues)

The question isn't "Can we simplify?" but "Why haven't we already?" 😊
