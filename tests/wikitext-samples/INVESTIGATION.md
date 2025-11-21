# Edge Case Investigation Results

## Summary

Investigation of edge cases revealed:
- **1 Python bug**: False positive for `is_abbreviation` on "acronym"
- **1 Rust bug**: Missing "colloquial" check for `is_informal`

## Case 1: `is_abbreviation` - "acronym" (Python False Positive)

### Observation
- Python: `is_abbreviation: True` ❌
- Rust: `is_abbreviation: False` ✅

### Investigation
Raw wikitext inspection shows "acronym" does NOT contain abbreviation templates:
- No `{{abbreviation of|en|...}}` template
- No `{{abbrev of|en|...}}` template
- No `{{initialism of|en|...}}` template
- No `Category:English...abbreviations` category

It only contains:
- `[[abbreviation]]` - wikilink in definition (line 33, 41)
- `{{l|en|abbreviation}}` - link template under Hypernyms (line 60)

### Conclusion
**Python has a false positive bug.** The ABBREVIATION_TEMPLATE regex should not match these patterns. Rust is correct.

### Recommendation
Investigate Python's `detect_abbreviation()` function. The pattern should only match `{{abbreviation of|en|...}}` style templates, not link templates or wikilinks. This may indicate a broader pattern matching issue in Python.

---

## Case 2: `is_informal` - Words with "colloquial" label (Rust Bug)

### Observation
Words: dialect, four, hell, poppycock, slushpile (and 1 more)
- Python: `is_informal: True` ✅
- Rust: `is_informal: False` ❌

All have `register: ["colloquial"]` in their labels.

### Investigation

**Python code** (tools/wiktionary_scanner_parser.py:1115-1123):
```python
def detect_informal_or_slang(labels: Dict) -> bool:
    register = labels.get('register', [])
    return 'informal' in register or 'slang' in register or 'colloquial' in register
```

**Rust code** (tools/wiktionary-rust/src/main.rs:726):
```rust
let is_informal = register.contains(&"informal".to_string()) || register.contains(&"slang".to_string());
```

**THE BUG**: Rust is missing the `|| register.contains(&"colloquial".to_string())` check.

### Example from raw wikitext
From `poppycock.xml`:
```wikitext
{{lb|en|colloquial}} [[nonsense|Nonsense]], [[foolish]] talk.
```

This gets extracted as `register: ["colloquial"]`, which Python correctly treats as informal, but Rust doesn't.

### Conclusion
**Rust has a bug.** The `is_informal` check needs to include "colloquial".

### Fix Required
```rust
let is_informal = register.contains(&"informal".to_string())
    || register.contains(&"slang".to_string())
    || register.contains(&"colloquial".to_string());
```

---

## Overall Parity Assessment

After investigating hotspot words:
- **Morphology extraction**: ✅ Fixed (was 100% broken, now working)
- **Regional labels**: ✅ Working (100% match in tests)
- **Syllables**: ✅ Working (100% match in tests)
- **Core fields**: ✅ Working (POS, labels, word_count all match)

**Remaining issues**:
1. Rust `is_informal` bug: Easy fix (add "colloquial" check)
2. Python `is_abbreviation` false positive: Needs investigation

**Test results**: 99.6% parity (1,793/1,800 field checks matched)

After fixing the Rust bug, expected parity: 99.9%+ (only Python false positive remaining)
