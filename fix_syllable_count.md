# Syllable Count Issue - Root Cause Analysis & Comprehensive Fix

## Problem
The syllable count in the metadata is incorrect for many words due to multiple issues in the hyphenation template parsing logic.

## Root Causes

### Issue 1: Overly Aggressive Language Code Filtering
The original heuristic-based filter was too broad:
```python
if i == 0 and len(part) <= 5 and ('-' in part or (len(part) <= 3 and part.isalpha())):
    continue
```

This incorrectly filtered:
- Valid words like "art", "god" (3 letters, treated as lang codes)
- Words matching language codes like "en", "da" (when they ARE the word being processed)

### Issue 2: Unreliable Data Not Rejected
Templates with unseparated syllables were accepted:
- `{{hyphenation|arad}}` → counted as 1 (should be None - data quality issue)
- `{{hyphenation|portia}}` → counted as 1 (should be None - missing pipes)

### Issue 3: No Fallback Signal
Category labels (e.g., `[[Category:English 3-syllable words]]`) were ignored, even though they provide a useful fallback when hyphenation templates are missing.

### Issue 4: General Principle Violation
The code was making assumptions (guessing) when data was unreliable or missing, rather than leaving fields unspecified.

## Comprehensive Solution (Implemented)

### ✓ Option 1: Whitelist of Known Language Codes
```python
KNOWN_LANG_CODES = {
    'en', 'da', 'de', 'es', 'fr', 'it', 'pt', 'nl', 'sv', 'no', 'fi',
    'en-US', 'en-GB', 'en-AU', 'en-CA', 'en-NZ', 'en-ZA', 'en-IE', 'en-IN',
    # ... (40+ language codes)
}
```

Benefits:
- ✓ Precise filtering - only actual language codes are filtered
- ✓ No false positives from short words
- ✓ Maintainable and explicit

### ✓ Option 3: Context-Aware Detection
```python
if i == 0:
    # Check if it's a known language code (not the word itself)
    if part in KNOWN_LANG_CODES and part.lower() != word.lower():
        continue
```

Benefits:
- ✓ Handles words that match language codes (e.g., word "en" itself)
- ✓ Prevents filtering the actual word being processed

### ✓ Unreliable Data Rejection
```python
# If there's only one part and it's unseparated (>3 chars), it's likely
# incomplete data (e.g., {{hyphenation|arad}} should be {{hyphenation|a|rad}})
if len(parts) == 1 and len(part) > 3:
    return None  # Indicate unreliable data
```

Benefits:
- ✓ Rejects templates with unseparated syllables (data quality issues)
- ✓ Only trusts single-part templates for very short words (1-3 chars)
- ✓ Returns None instead of guessing

### ✓ Category Labels as Fallback Signal
```python
def extract_syllable_count_from_categories(text: str) -> Optional[int]:
    """Extract from [[Category:English N-syllable words]]"""
    match = SYLLABLE_CATEGORY.search(text)
    if match:
        return int(match.group(1))
    return None
```

Benefits:
- ✓ Uses deprecated category labels when available
- ✓ Provides coverage for words without hyphenation templates
- ✓ Hyphenation template still preferred (more reliable)

### ✓ No-Guess Principle
```python
# Only include syllable count if reliably determined
# Leave unspecified (None) if data is missing or unreliable
if syllable_count is not None:
    entry['syllables'] = syllable_count
```

Benefits:
- ✓ Never makes assumptions about missing data
- ✓ Downstream processes can make context-appropriate decisions
- ✓ Explicit about what we know vs. what we don't know

## Test Results

All 21 test cases pass:

**Hyphenation Templates:**
- ✓ `{{hyphenation|art}}` → 1 (was: None)
- ✓ `{{hyphenation|en|art}}` → 1 (still works)
- ✓ `{{hyphenation|en|dic|tion|a|ry}}` → 4 (still works)

**Context-Aware:**
- ✓ Word "en" with `{{hyphenation|en}}` → 1 (not filtered)
- ✓ Word "da" with `{{hyphenation|da}}` → 1 (not filtered)

**Unreliable Data Rejection:**
- ✓ `{{hyphenation|arad}}` → None (unreliable, should be a|rad)
- ✓ `{{hyphenation|portia}}` → None (unreliable, missing pipes)
- ✓ `{{hyphenation|by right}}` → None (unseparated phrase)

**Reliable Short Words:**
- ✓ `{{hyphenation|god}}` → 1 (3 chars, reliable)
- ✓ `{{hyphenation|by}}` → 1 (2 chars, reliable)

**Category Fallback:**
- ✓ `[[Category:English 3-syllable words]]` → 3
- ✓ Works when hyphenation template is missing

**No Guessing:**
- ✓ No hyphenation, no category → None (not guessed)
- ✓ Empty template → None (not guessed)

## Files Modified

1. **tools/wiktionary_scanner_parser.py**
   - Added `KNOWN_LANG_CODES` whitelist
   - Added `SYLLABLE_CATEGORY` regex pattern
   - Renamed and improved `extract_syllable_count()` → `extract_syllable_count_from_hyphenation()`
   - Added `extract_syllable_count_from_categories()`
   - Updated `parse_entry()` to use both sources with proper fallback
   - Implements no-guess principle

2. **fix_syllable_count.md** (this file)
   - Complete analysis and documentation

## Recommendations for Downstream Use

When filtering words by syllable count:

**For inclusion (e.g., "must have X syllables"):**
```python
# Only include words with confirmed syllable count
if entry.get('syllables') == desired_count:
    include(word)
```

**For exclusion (e.g., "exclude words with >5 syllables"):**
```python
# Option A: Conservative (exclude unknowns)
if entry.get('syllables', 999) > 5:
    exclude(word)

# Option B: Permissive (include unknowns)
syllables = entry.get('syllables')
if syllables is not None and syllables > 5:
    exclude(word)
```

The appropriate choice depends on your use case. The important point is that we provide **accurate information about what we know**, not guesses about what we don't know.
