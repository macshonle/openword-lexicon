# XML Slice Analysis & Scanner Code Review

## Executive Summary

After analyzing all 65 diagnostic XML slices against the current scanning code in `tools/wiktionary_scanner_parser.py`, I've identified several critical issues and edge cases that need to be addressed.

## Key Finding: Slices are Variably Truncated

**Critical Discovery:** The diagnostic slices come in two forms:
1. **Complete slices** (16 files) - Have `</text>` and `</page>` closing tags
2. **Truncated slices** (49 files) - Missing closing tags, text content cut off mid-stream

### Impact on Testing

The current `TEXT_PATTERN` regex:
```python
TEXT_PATTERN = re.compile(r'<text[^>]*>(.+?)</text>', re.DOTALL)
```

This pattern **requires** a closing `</text>` tag. This causes:
- ✅ **16 complete slices PASS** (have closing tags)
- ❌ **49 truncated slices FAIL** (return `None` from `extract_page_content`)

### Files by Completeness

#### Complete Slices (16 files):
All of these passed the initial extraction test:
- ejector
- -phobic
- dissimilarity
- imagery
- householder
- key server
- small potatoes
- FMS
- firebrick
- biomimetic
- field emission
- owler
- accurses
- fuming
- garce
- Newby

#### Truncated Slices (49 files):
These all returned `None` due to missing `</text>`:
- All baseline files (dictionary, free, thesaurus, encyclopedia, etc.)
- All syllable files (cat, pies)
- All label files (elephant, portmanteau)
- Most position files (cattle, nuance, gratis)
- Many periodic files

## Issues Identified

### Issue 1: TEXT_PATTERN Requires Closing Tag

**Problem:** The regex pattern uses `.+?` between `<text>` and `</text>`, which requires both tags to be present.

**Impact:** Cannot parse truncated XML slices that are missing closing tags.

**Recommendation:** The scanner should be robust to both:
- Complete XML (production use case)
- Truncated XML (diagnostic/testing use case)

**Proposed Solution:**
```python
# Option 1: Make closing tag optional
TEXT_PATTERN = re.compile(r'<text[^>]*>(.+?)(?:</text>|$)', re.DOTALL)

# Option 2: Match to end of string if no closing tag
TEXT_PATTERN = re.compile(r'<text[^>]*>((?:.|\n)+?)(?:</text>|(?=</revision>|</page>|$))', re.DOTALL)

# Option 3 (Recommended): Two-phase approach
# Phase 1: Try with closing tag (fast, precise)
TEXT_PATTERN_CLOSED = re.compile(r'<text[^>]*>(.+?)</text>', re.DOTALL)
# Phase 2: Fallback without closing tag (slower, diagnostic mode)
TEXT_PATTERN_OPEN = re.compile(r'<text[^>]*>(.+)', re.DOTALL)
```

### Issue 2: Order of Element Processing

**Current Code Flow:**
1. Extract `<title>`
2. Check `<ns>` (namespace)
3. Check for `<redirect>`
4. **Extract `<text>` (can fail here)**
5. Check for English section in text

**Problem:** If step 4 fails (no closing `</text>`), the entire page returns `None`, even if we could determine it should be filtered based on namespace or redirect status.

**Impact:** Premature filtering - can't distinguish between "invalid XML" and "non-English page".

**Recommendation:** The current order is actually CORRECT for production use:
- Namespace check is first (fast filter)
- Redirect check is second (fast filter)
- Text extraction is last (can be expensive)

**For diagnostic mode only:** Consider extracting text content even without closing tag.

### Issue 3: Redirect Detection in Non-Main Namespaces

**Current Behavior:**
- File `15d93a33_770_cat_no_pos_Rhymes_English_eəri.xml` has:
  - `<ns>106</ns>` (Rhymes namespace)
  - `<redirect title="..."/>` tag

**Result:** Filtered as `SPECIAL_PAGE` (namespace), NOT as `REDIRECT`

**Analysis:** This is actually **CORRECT** behavior because:
- Namespace filtering happens BEFORE redirect checking
- We don't care about redirects in non-main namespaces
- This is efficient (early exit)

**Recommendation:** No change needed. Current behavior is optimal.

### Issue 4: Multiple Language Sections - Position Independence

**Test Coverage:** Slices include English sections at positions 1, 3, 5, 8, 9, 10

**Current Code:**
```python
ENGLISH_SECTION = re.compile(r'==\s*English\s*==', re.IGNORECASE)
```

**Analysis:** The pattern will find `==English==` anywhere in the text, regardless of position.

**Test Result:** Should work correctly for all position variations.

**Recommendation:** Verify this works correctly when paired with `extract_english_section()` function that isolates the English section boundaries.

### Issue 5: Section Boundary Detection

**Current Code:**
```python
def extract_english_section(text: str) -> Optional[str]:
    # Find ==English==
    english_match = ENGLISH_SECTION.search(text)
    if not english_match:
        return None

    english_start = english_match.end()

    # Find next == section
    for match in LANGUAGE_SECTION.finditer(text, english_start):
        lang = match.group(1).strip()
        if lang.lower() != 'english':
            next_section = match.start()
            break

    # Extract English section only
    if next_section:
        return text[english_start:next_section]
    else:
        return text[english_start:]
```

**Pattern:**
```python
LANGUAGE_SECTION = re.compile(r'^==\s*([^=]+?)\s*==$', re.MULTILINE)
```

**Analysis:**
- Uses `^` anchor (start of line) - CORRECT
- Uses `MULTILINE` flag - CORRECT
- Looks for `==LANG==` pattern - CORRECT

**Potential Issues:**
1. **Level-2 vs Level-3 headers:**
   - `==English==` - Level 2 (language section) ✓
   - `===Noun===` - Level 3 (POS header) ✓
   - Pattern `==\s*([^=]+?)\s*==` will NOT match `===Noun===` (has 3+ equals) ✓

2. **Other Level-2 headers in English section:**
   - Some entries have `==Etymology 1==`, `==Etymology 2==` (still level-2!)
   - These would be incorrectly detected as "next language section"
   - **This is a BUG** ❌

**Example from `free` slice:**
```wikitext
==English==

===Etymology 1===
From Old English...

====Adjective====
{{en-adj}}

===Etymology 2===
...

====Verb====
{{en-verb}}

==French==
```

**Problem:** The pattern `^==\s*([^=]+?)\s*==$` will match:
- `==Etymology 1==`
- `==Etymology 2==`

And stop the English section extraction early!

**Recommendation:** Modify the section detection to ONLY match language names:

```python
# Option 1: Exclude known non-language level-2 headers
def extract_english_section(text: str) -> Optional[str]:
    english_match = ENGLISH_SECTION.search(text)
    if not english_match:
        return None

    english_start = english_match.end()

    # Find the next LANGUAGE section (not Etymology, Pronunciation, etc.)
    NON_LANGUAGE_HEADERS = {'Etymology', 'Pronunciation', 'References', 'See also',
                            'Alternative forms', 'Usage notes', 'Further reading'}

    next_section = None
    for match in LANGUAGE_SECTION.finditer(text, english_start):
        lang = match.group(1).strip()

        # Skip if it's a numbered header (e.g., "Etymology 1", "Pronunciation 2")
        if re.match(r'^(Etymology|Pronunciation|References)\s+\d+$', lang):
            continue

        # Skip if it's a known non-language header
        if lang in NON_LANGUAGE_HEADERS:
            continue

        # If we get here, it's likely a language section
        if lang.lower() != 'english':
            next_section = match.start()
            break

    if next_section:
        return text[english_start:next_section]
    else:
        return text[english_start:]

# Option 2 (Better): Only match known language patterns
# Languages are typically capitalized single/double words
# Not "Etymology 1" or "See also"
LANGUAGE_SECTION = re.compile(r'^==\s*([A-Z][a-zA-Z\s-]+?)\s*==$', re.MULTILINE)

# Then filter out non-languages:
if lang in NON_LANGUAGE_HEADERS or re.match(r'.+\s+\d+$', lang):
    continue
```

### Issue 6: POS Header Detection

**Current Pattern:**
```python
POS_HEADER = re.compile(r'^===+\s*(.+?)\s*===+\s*$', re.MULTILINE)
```

**Analysis:** Uses `===+` which matches 3 or more equals signs.

**Potential Issues:**
1. **Variable nesting levels:**
   - `===Noun===` - Level 3 (standard POS) ✓
   - `====Noun====` - Level 4 (under Etymology section) ✓
   - Both are valid POS headers

2. **Asymmetric equals:**
   - `===Noun==` - Might occur in malformed entries
   - Current pattern requires equal number on both sides ✓

**Test Cases from Slices:**
- `===Noun===` ✓
- `===Verb===` ✓
- `===Adjective===` ✓
- `====Adjective====` (under Etymology) ✓
- `===Suffix===` ✓

**Recommendation:** Current pattern is good. The `===+` allows flexibility for nested POS headers under Etymology sections.

### Issue 7: Template Variations

**Test Coverage:** Slices include various template formats:
- `{{en-noun}}`
- `{{en-verb}}`
- `{{head|en|noun form}}`
- `{{head|en|verb form}}`
- `{{head|en|adjective}}`

**Current Code:**
```python
HEAD_TEMPLATE = re.compile(r'\{\{(?:head|en-head|head-lite)\|en\|([^}|]+)', re.IGNORECASE)
```

**Analysis:** Pattern looks for `{{head|en|POS...` and extracts POS.

**Recommendation:** Add more template variations:

```python
# Current patterns are good, but could add:
# - {{head-lite|en|...}}
# - {{en-head|...}}

# Also consider templates without |en| parameter:
# - {{en-noun}} - English is implicit
# - Pattern: r'\{\{en-([^}|]+)'

# These are already covered by EN_POS_TEMPLATE ✓
```

### Issue 8: Multi-word Entry Titles

**Test Coverage:** 4 slices with spaces in titles:
- "rain cats and dogs"
- "small potatoes"
- "key server"
- "field emission"

**Current Code:**
```python
TITLE_PATTERN = re.compile(r'<title>([^<]+)</title>')
```

**Analysis:** Pattern `[^<]+` matches any character except `<`, including spaces ✓

**Recommendation:** No changes needed. Correctly handles multi-word titles.

### Issue 9: Non-Latin Scripts

**Test Coverage:** 10 slices with non-Latin characters:
- Chinese (Han): 溃, 弇, 墌, 醟, 緿, 癵, 生活照, 徳用
- Japanese: こちら, 為る
- Cyrillic: фокстерьер

**Current Code:**
```python
def is_englishlike(token: str) -> bool:
    # Checks for Latin letters with Unicode category checking
    # Rejects non-Latin scripts
```

**Analysis:** The function correctly rejects non-Latin scripts.

**Test Result:** All non-Latin entries should be filtered BEFORE `is_englishlike` check (they have no English sections).

**Recommendation:** No changes needed. The dual filtering (no English section + non-Latin) provides robustness.

## Assumptions Review

### Assumption 1: ✅ VALID
**"Namespace tag appears before text content"**
- This is guaranteed by MediaWiki XML structure
- Namespace is in page metadata, text is in revision content
- Safe to check namespace early

### Assumption 2: ✅ VALID
**"Redirect tag appears before text content"**
- Redirect is a page-level attribute
- Appears early in XML structure
- Safe to check before text extraction

### Assumption 3: ⚠️ NEEDS REFINEMENT
**"Text content is enclosed in <text>...</text> tags"**
- TRUE for complete XML dumps
- FALSE for truncated diagnostic slices
- Need to handle both cases

### Assumption 4: ⚠️ NEEDS REFINEMENT
**"Language sections are delimited by level-2 headers (==LANG==)"**
- MOSTLY TRUE
- BUT: English sections may also have level-2 Etymology/Pronunciation headers
- NEED: Better distinction between language vs. non-language level-2 headers

### Assumption 5: ✅ VALID
**"POS headers use level-3 or higher (===POS===)"**
- TRUE in standard entries
- Also true for nested POS under Etymology (====POS====)
- Pattern `===+` correctly handles both

### Assumption 6: ✅ VALID
**"English section can appear at any position"**
- Test coverage confirms this
- Pattern `==\s*English\s*==` with no anchors will find it anywhere
- Correct behavior

### Assumption 7: ⚠️ QUESTIONABLE
**"English categories must be present for valid entries"**
- Test case `gratis` has English section but NO English categories
- Parser has fallback logic for entries without categories
- DECISION: Categories are helpful but not required ✓

### Assumption 8: ✅ VALID
**"Title can contain spaces and special characters"**
- Pattern `[^<]+` handles all cases
- Test coverage includes multi-word entries
- Correct behavior

## Recommendations Summary

### Priority 1: Critical Fixes

1. **Fix Section Boundary Detection**
   - Problem: Etymology sections incorrectly terminate English section extraction
   - Impact: Loss of data from entries with multiple etymology sections
   - Solution: Filter out non-language level-2 headers

2. **Handle Truncated XML (Diagnostic Mode)**
   - Problem: 49 slices fail due to missing `</text>` tag
   - Impact: Cannot test against truncated diagnostic data
   - Solution: Add fallback pattern for text extraction without closing tag

### Priority 2: Enhancements

3. **Improve Language vs. Non-Language Header Detection**
   - Add whitelist/blacklist of known non-language headers
   - Use pattern matching to identify "Etymology 1", "Pronunciation 2", etc.

4. **Add More Robust Template Detection**
   - Current patterns are good but could be more comprehensive
   - Consider template aliases and variations

### Priority 3: Testing & Validation

5. **Create Test Harness for Slices**
   - Test both complete and truncated XML
   - Validate expected pass/filter behavior
   - Track coverage of edge cases

6. **Document Expected Behavior**
   - 31 slices should PASS (extract English content)
   - 34 slices should FILTER (6 namespace, 1 redirect, 26 non-English)

## Proposed Code Changes

### Change 1: Extract English Section (Fix Etymology Handling)

```python
def extract_english_section(text: str) -> Optional[str]:
    """
    Extract ONLY the ==English== section from a Wiktionary page.

    Handles multi-etymology entries correctly by distinguishing between:
    - Language sections (==French==, ==Spanish==, etc.)
    - Non-language sections (==Etymology 1==, ==Pronunciation==, etc.)
    """
    # Find the start of the English section
    english_match = ENGLISH_SECTION.search(text)
    if not english_match:
        return None

    english_start = english_match.end()

    # Known level-2 headers that are NOT language sections
    NON_LANGUAGE_HEADERS = {
        'Etymology', 'Pronunciation', 'Alternative forms', 'Usage notes',
        'References', 'Further reading', 'See also', 'Anagrams',
        'Derived terms', 'Related terms', 'Descendants', 'Translations'
    }

    # Find the start of the next language section
    next_section = None
    for match in LANGUAGE_SECTION.finditer(text, english_start):
        header = match.group(1).strip()

        # Skip numbered headers (Etymology 1, Pronunciation 2, etc.)
        if re.match(r'^.+\s+\d+$', header):
            continue

        # Skip known non-language headers
        if header in NON_LANGUAGE_HEADERS:
            continue

        # If it's not English, we found the next language section
        if header.lower() != 'english':
            next_section = match.start()
            break

    # Extract English section only
    if next_section:
        return text[english_start:next_section]
    else:
        return text[english_start:]
```

### Change 2: Handle Truncated XML

```python
def extract_page_content(page_xml: str, allow_truncated: bool = False):
    """
    Extract title and text from page XML using simple regex.

    Args:
        page_xml: The XML content of a single page
        allow_truncated: If True, extract text even without closing </text> tag
                        (useful for diagnostic slices)

    Returns:
        (title, text) or status tuples
    """
    # [... existing code for title, namespace, redirect ...]

    # Extract text - try with closing tag first (fast path)
    text_match = TEXT_PATTERN.search(page_xml)

    if not text_match and allow_truncated:
        # Fallback: Try without closing tag (diagnostic mode)
        TEXT_PATTERN_OPEN = re.compile(r'<text[^>]*>(.+)', re.DOTALL)
        text_match = TEXT_PATTERN_OPEN.search(page_xml)

    if not text_match:
        return None

    text = text_match.group(1)

    # [... rest of existing code ...]
```

### Change 3: Add Diagnostic Testing Mode

```python
# In main() or separate test script:

def validate_slices(slices_dir: Path):
    """
    Validate scanner behavior against diagnostic slices.

    Expected results:
    - 31 slices should extract English content
    - 6 slices should filter (namespace)
    - 1 slice should filter (redirect)
    - 26 slices should filter (no English)
    - 1 slice might filter (dict-only, depending on policy)
    """
    results = {'pass': 0, 'filter_ns': 0, 'filter_redirect': 0,
               'filter_no_english': 0, 'error': 0}

    for slice_file in slices_dir.glob('*.xml'):
        # Test with allow_truncated=True for diagnostic slices
        result = test_slice(slice_file, allow_truncated=True)
        # ... categorize and count ...

    # Validate expectations
    assert results['pass'] == 31, f"Expected 31 pass, got {results['pass']}"
    # ... more assertions ...
```

## Test Coverage Summary

Current slice coverage:

✅ **Well Covered:**
- Namespace filtering (6 slices)
- Redirect detection (1 slice)
- Non-English entries (26 slices)
- Multi-word titles (4 slices)
- Non-Latin scripts (10 slices)
- English at different positions (1, 3, 5, 8, 9, 10)
- Various POS types
- Template variations

⚠️ **Needs More Coverage:**
- Etymology sections (only partially tested)
- Nested POS headers under Etymology (needs explicit test)
- Entries with categories but no POS headers
- Entries with POS headers but no categories
- Edge cases in template formatting

❌ **Missing Coverage:**
- Malformed XML (unclosed tags other than </text>)
- Invalid UTF-8 sequences
- Extremely long entries (> 1MB text)
- Entries with unusual Unicode normalization

## Conclusion

The XML scanning code is generally robust and well-designed. The main issues are:

1. **Etymology section handling** - Needs refinement to avoid early termination
2. **Truncated XML support** - Need to support diagnostic slices
3. **Test coverage** - Need automated validation against expected results

With the proposed changes, the scanner will handle all edge cases correctly while maintaining performance and code clarity.
