# Syllable Count Issue - Root Cause Analysis

## Problem
The syllable count in the metadata is incorrect for many words because the hyphenation template parsing logic incorrectly filters out valid syllable segments.

## Root Cause
In `tools/wiktionary_scanner_parser.py` at line 355, the language code filter is too aggressive:

```python
if i == 0 and len(part) <= 5 and ('-' in part or (len(part) <= 3 and part.isalpha())):
    continue
```

This filter assumes that:
- Any 2-3 letter alphabetic string at position 0 is a language code
- Any string up to 5 chars with a hyphen at position 0 is a language code (like "en-US")

## Issues This Causes

### Issue 1: Templates without language codes
When Wiktionary uses templates like `{{hyphenation|art}}` without an explicit language code:
- The word "art" is at position 0
- It's 3 letters and all alphabetic
- It gets filtered out as if it were a language code
- Result: Returns `None` instead of 1 syllable

### Issue 2: Unseparated syllables in templates
When Wiktionary has templates like `{{hyphenation|arad}}` instead of `{{hyphenation|a|rad}}`:
- "arad" is 4 letters (exceeds the 3-char filter)
- It passes through as a single syllable
- Result: Counts as 1 syllable instead of 2

### Issue 3: Multi-word phrases
When templates contain full phrases like `{{hyphenation|by right}}`:
- "by right" is treated as a single unseparated segment
- Result: Counts as 1 syllable instead of 2

## Solution Options

### Option 1: Stricter Language Code Whitelist (Recommended)
Instead of heuristics, maintain a whitelist of known language codes:

```python
KNOWN_LANG_CODES = {
    'en', 'da', 'de', 'es', 'fr', 'it', 'pt', 'nl', 'sv', 'no',
    'en-US', 'en-GB', 'en-AU', 'en-CA', 'en-NZ', 'en-ZA', 'en-IE', 'en-IN'
}

# Skip only if it's an actual known language code at position 0
if i == 0 and part in KNOWN_LANG_CODES:
    continue
```

This approach:
- ✓ Doesn't filter out valid single-syllable words like "art", "god"
- ✓ Still filters out actual language codes
- ✓ Simple and maintainable
- ✗ Requires maintaining the whitelist
- ✗ Doesn't fix Issue 2 (unseparated syllables in Wiktionary data)

### Option 2: Smarter Heuristic
Only filter if there are additional segments after position 0:

```python
# Only skip lang code if there are more parts after it
if i == 0 and len(parts) > 1 and len(part) <= 5 and ('-' in part or (len(part) <= 3 and part.isalpha())):
    continue
```

This approach:
- ✓ Fixes templates without language codes (single part is not filtered)
- ✓ Still filters out language codes when proper syllables follow
- ✗ Might incorrectly count some two-letter language codes if they're the only content
- ✗ Doesn't fix Issue 2 (unseparated syllables in Wiktionary data)

### Option 3: Context-Aware Detection (Most Robust)
Check if the potential lang code is also the page title:

```python
# This requires passing the word being processed to the function
# Skip only if it looks like a lang code AND is not the word itself
if i == 0 and len(parts) > 1 and len(part) <= 5 and ('-' in part or (len(part) <= 3 and part.isalpha())):
    if part.lower() != word.lower():  # Not the word itself
        continue
```

This requires modifying the function signature to accept the word being processed.

## Recommendation

**Implement Option 2** as it provides the best balance:
- Fixes the immediate issue with templates lacking language codes
- Minimal code change
- Low risk of breaking existing correct behavior

Then, for the data quality issue (Issue 2 - unseparated syllables in Wiktionary), we should:
1. Document that syllable counts depend on Wiktionary data quality
2. Consider alternative sources for syllable data (e.g., CMU Pronouncing Dictionary)
3. Add validation/warnings for suspicious syllable counts during ingestion

## Testing

The fix should be tested with:
```python
# Should all return correct results after fix:
{{hyphenation|art}}           # Should return 1 (currently returns None)
{{hyphenation|god}}           # Should return 1 (currently returns None)
{{hyphenation|en|art}}        # Should return 1 (works correctly)
{{hyphenation|en|a|rad}}      # Should return 2 (works correctly)
{{hyphenation|arad}}          # Should return 1 (Wiktionary data issue, not parser bug)
```
