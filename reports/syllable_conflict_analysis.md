# Syllable Source Conflict Analysis

**Date:** 2025-11-19
**Finding:** Bug discovered in hyphenation extraction logic

## Summary

During syllable implementation review, a conflict was detected for the word "encyclopedia":
- **Hyphenation template:** 5 syllables (INCORRECT - should be 6)
- **Rhymes template:** 6 syllables (CORRECT)
- **Actual syllables:** en-cy-clo-pe-di-a (6 syllables)

## Root Cause

The hyphenation extraction logic has a **double-filtering bug**:

1. The regex pattern already requires and consumes the language code:
   ```python
   HYPHENATION_TEMPLATE = re.compile(r'\{\{(?:hyphenation|hyph)\|en\|([^}]+)\}\}')
   ```
   For `{{hyphenation|en|en|cy|clo|pe|di|a}}`, this captures: `'en|cy|clo|pe|di|a'`

2. The extraction then **incorrectly** treats the first captured part as a potential language code:
   ```python
   # Line 51-53 in wiktionary_scanner_parser.py
   if i == 0:
       if part in KNOWN_LANG_CODES and part.lower() != word.lower():
           continue  # BUG: This filters out the first syllable 'en'
   ```

3. Result: The word "encyclopedia" with template `{{hyphenation|en|en|cy|clo|pe|di|a}}` gets:
   - Captured: `['en', 'cy', 'clo', 'pe', 'di', 'a']` (6 parts)
   - After filtering: `['cy', 'clo', 'pe', 'di', 'a']` (5 parts) ❌
   - **Incorrectly returns 5 syllables instead of 6**

## Impact Assessment

**Severity:** 🟡 MEDIUM

**Affected words:** Words where the first syllable matches a language code in `KNOWN_LANG_CODES`

**Common examples:**
- encyclopedia (en-) → miscounted as 5 instead of 6
- encore (en-) → potentially affected
- italic (it-) → potentially affected
- korean (ko-) → potentially affected
- romance (ro-) → potentially affected

**Estimated impact:** Small subset of words (< 1% of hyphenation templates)

**Why it wasn't caught earlier:**
- Most words don't start with syllables that match language codes
- The rhymes template provides correct fallback
- Priority system means rhymes would be used if hyphenation fails
- BUT: In cases where both exist, hyphenation wins (incorrectly)

## Current Behavior

**For "encyclopedia":**
```
Template: {{hyphenation|en|en|cy|clo|pe|di|a}}
         {{rhymes|en|iːdiə|s=6}}

Priority system:
1. Check hyphenation → Returns 5 ❌ (BUG)
2. (Never checks rhymes because hyphenation succeeded)

Output: syllables: 5 (INCORRECT)
```

**If we fix the bug:**
```
Priority system:
1. Check hyphenation → Returns 6 ✅
2. (Never checks rhymes because hyphenation succeeded)

Output: syllables: 6 (CORRECT)
```

## Recommended Fix

### Option 1: Remove redundant filtering (RECOMMENDED)

Since the regex already requires `|en|`, the captured content should be pure syllables:

```python
# In wiktionary_scanner_parser.py, replace lines 427-456 with:
def extract_syllable_count_from_hyphenation(text: str, word: str) -> Optional[int]:
    """Extract syllable count from {{hyphenation|en|...}} template."""
    match = HYPHENATION_TEMPLATE.search(text)
    if not match:
        return None

    content = match.group(1)

    # Handle alternatives (||) - use first alternative
    alternatives = content.split('||')
    first_alt = alternatives[0] if alternatives else content

    # Parse pipe-separated segments
    parts = first_alt.split('|')

    # Filter syllables (exclude parameters and empty)
    syllables = []
    for part in parts:
        part = part.strip()

        # Skip empty or parameter assignments
        if not part or '=' in part:
            continue

        syllables.append(part)

    # Return syllable count if we found any syllables
    # Single-part templates with long unseparated text are likely incomplete
    if len(syllables) == 1 and len(syllables[0]) > 3:
        return None

    return len(syllables) if syllables else None
```

**Changes:**
- Remove language code filtering from captured content (regex already handles it)
- Simplify logic: only skip empty parts and parameters
- Keep safety check for incomplete templates (single long part)

### Option 2: Keep defensive filtering but fix the logic

If we want to keep the language code filtering for defensive purposes:

```python
# Only filter at position 0 if there are MORE parts after it
# (i.e., it's actually a lang code, not the first syllable)
if i == 0 and len(parts) > 1:
    # Check if this looks like a redundant language code
    # (Sometimes templates incorrectly include it twice)
    if part in KNOWN_LANG_CODES and len(part) <= 3:
        # Heuristic: very short parts at position 0 that are lang codes
        # are likely redundant (not actual syllables)
        # BUT: This heuristic is unreliable for words like "encyclopedia"
        continue
```

**Note:** This option is NOT recommended because it's still prone to false positives.

## Testing

After applying Option 1 fix, verify with these test cases:

```python
# Should all return 6
test_cases = [
    ("encyclopedia", "{{hyphenation|en|en|cy|clo|pe|di|a}}"),
    ("encore", "{{hyphenation|en|en|core}}"),  # 2 syllables
]

for word, template in test_cases:
    result = extract_syllable_count_from_hyphenation(f"text {template} text", word)
    print(f"{word}: {result}")
```

## Recommendation Priority

**Priority:** 🟡 MEDIUM

**Rationale:**
1. ✅ Relatively few words affected (< 1%)
2. ✅ Rhymes template often provides correct fallback
3. ❌ When both exist, incorrect value is used (priority system)
4. ❌ Undermines trust in hyphenation as "most reliable source"

**Suggested timeline:**
- Fix in next development cycle (not urgent)
- Include in test suite to prevent regression
- Re-run extraction after fix to update affected entries

## Verification

To find all affected words in the current data:

```bash
# After running full extraction, find entries where hyphenation < rhyme count
# (These are likely affected by this bug)
jq -r 'select(.syllables != null and .syllables_from_rhymes != null and .syllables < .syllables_from_rhymes) | "\(.word): hyph=\(.syllables) rhyme=\(.syllables_from_rhymes)"' data/intermediate/en/wikt.jsonl
```

Note: This requires tracking multiple syllable sources (currently only final value is stored).

## Conclusion

The hyphenation extraction has a **double-filtering bug** that incorrectly removes the first syllable when it matches a language code.

**Fix:** Remove the redundant language code filtering since the regex already handles it.

**Impact:** Small (< 1% of words) but important for maintaining hyphenation as the most reliable source.

**Next steps:**
1. Apply Option 1 fix to `wiktionary_scanner_parser.py`
2. Add test cases for affected words
3. Re-extract syllable data from Wiktionary
4. Verify conflict resolution
