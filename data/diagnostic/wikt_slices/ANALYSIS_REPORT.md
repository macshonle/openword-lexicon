# Wiktionary XML Slice Analysis Report

**Date:** 2025-11-17
**Total Files Analyzed:** 64
**Purpose:** Identify patterns, edge cases, and potential parser issues in XML slices

---

## Executive Summary

The diagnostic slices contain a diverse mix of entries designed to test various filtering and parsing scenarios:
- **6 files** from non-main namespaces (Wiktionary, Appendix, Rhymes) - **should be filtered**
- **1 redirect page** - **should be filtered**
- **31 files** with English sections - **should be extracted**
- **26 files** without English sections - **should be filtered**
- **14 files** with non-Latin script titles

---

## Category 1: Non-Main Namespace Pages (SHOULD BE FILTERED)

These pages exist in Wiktionary meta-namespaces and should be filtered by `<ns>` tag checking.

### Files with `<ns>4</ns>` (Wiktionary namespace):
| File | Title | Expected Behavior |
|------|-------|-------------------|
| `00002861_3630_baseline_Wiktionary_GNU_Free_Documentat.xml` | Wiktionary:GNU Free Documentation License | **FILTER** - Meta page |
| `00000d59_3856_baseline_Wiktionary_Welcome__newcomers.xml` | Wiktionary:Welcome, newcomers | **FILTER** - Meta page |
| `00007c47_3835_baseline_Wiktionary_What_Wiktionary_is_.xml` | Wiktionary:What Wiktionary is not | **FILTER** - Meta page |
| `00003692_3656_baseline_Wiktionary_Text_of_the_GNU_Fre.xml` | Wiktionary:Text of the GNU Free Documentation License | **FILTER** - Meta page |
| `0001f6d9_2065_baseline_Wiktionary_Language_considerat.xml` | Wiktionary:Language considerations | **FILTER** - Meta page |

**Key Observations:**
- All contain `<ns>4</ns>` tag
- No language sections (no `==English==`, etc.)
- Content is about Wiktionary policies, licenses, etc.
- Should be trivially filtered by namespace check

### Files with `<ns>100</ns>` (Appendix namespace):
| File | Title | Expected Behavior |
|------|-------|-------------------|
| `00088b4b_4073_multiword_Appendix_English_pronunciation.xml` | Appendix:English pronunciation | **FILTER** - Appendix page |

**Key Observations:**
- Contains `<ns>100</ns>` tag
- Has technical reference content about pronunciation
- Should be filtered by namespace check

---

## Category 2: Redirect Pages (SHOULD BE FILTERED)

### Files with `<redirect>` tag:
| File | Title | Redirects To | Namespace |
|------|-------|--------------|-----------|
| `15d93a33_770_cat_no_pos_Rhymes_English_eəri.xml` | Rhymes:English/eəri | Rhymes:English/ɛəɹi | `<ns>106</ns>` |

**Key Observations:**
- Contains `<redirect title="Rhymes:English/ɛəɹi" />` tag
- Also in Rhymes namespace (106)
- Should be filtered by redirect detection AND namespace check

---

## Category 3: Valid English Entries (SHOULD EXTRACT)

These are main namespace (`<ns>0</ns>`) entries with English sections and proper POS headers.

### 3A. Single-Word English Entries (31 files)

| File | Title | POS Headers | Templates | Categories | Notes |
|------|-------|-------------|-----------|------------|-------|
| `0001d422_4047_baseline_thesaurus.xml` | thesaurus | ===Noun=== | {{en-noun}} | ✓ | Classic dictionary word |
| `00011b5f_3951_baseline_free.xml` | free | ===Adjective===, ===Adverb===, ===Verb=== | {{en-adj}}, {{en-adv}} | ✓ | Multiple POS |
| `0000acdc_3933_baseline_dictionary.xml` | dictionary | ===Noun=== | {{en-noun}} | ✓ | Classic dictionary word |
| `000289c0_4112_syllable_cat.xml` | cat | ===Noun===, ===Verb=== | {{en-noun}}, {{mul-symbol}} | ✓ | Also has ==Translingual== |
| `000251a3_4096_labels_portmanteau.xml` | portmanteau | ===Noun=== | {{en-noun}} | ✓ | Etymology sections |
| `0001feec_3970_baseline_encyclopedia.xml` | encyclopedia | ===Noun=== | {{en-noun}} | ✓ | Alternative forms |
| `0005e0ad_4111_syllable_pies.xml` | pies | ===Noun===, ===Verb=== | {{head\|en\|noun form}} | ✓ | Plural/verb form |
| `0003265e_4099_pos_no_cat_gratis.xml` | gratis | ===Adjective===, ===Adverb=== | {{en-adj}}, {{en-adv}} | ✗ NO English categories | **EDGE CASE** |
| `0344e45a_3939_position_1_cattle.xml` | cattle | ===Noun=== | {{en-noun}} | ✓ | English is position 1 |
| `000986cb_4075_labels_elephant.xml` | elephant | ===Noun=== | {{en-noun}} | ✓ | Rich content |
| `080c9b2b_2296_periodic_29919_ejector.xml` | ejector | ===Noun=== | {{en-noun}} | ✓ | Also ==Latin==, ==Romanian== |
| `064d06ee_4080_position_3_nuance.xml` | nuance | ===Noun=== | {{en-noun}} | ✓ | English is position 3 |
| `0ee7bcc0_2644_periodic_49865_imagery.xml` | imagery | ===Noun=== | {{en-noun}} | ✓ | Also ==Middle English== |
| `0b643a9e_1976_position_3_dissimilarity.xml` | dissimilarity | ===Noun=== | {{en-noun}} | ✓ | |
| `0b0a1120_2324_cat_no_pos_-phobic.xml` | -phobic | ===Suffix=== | {{en-suffix}} | ✓ | Prefix/suffix entry |
| `11125693_2897_position_5_householder.xml` | householder | ===Noun=== | {{en-noun}} | ✓ | |
| `1897080f_1135_periodic_99730_biomimetic.xml` | biomimetic | ===Adjective=== | {{head\|en\|adjective}} | ✓ | |
| `16f90943_1673_periodic_89757_firebrick.xml` | firebrick | ===Noun=== | {{en-noun}} | ✓ | |
| `16611a28_1529_position_9_FMS.xml` | FMS | ===Noun===, ===Proper noun=== | {{en-noun}}, {{en-proper noun}} | ✓ | Abbreviation |
| `1e41ba4d_2791_periodic_139622_fuming.xml` | fuming | ===Verb===, ===Adjective===, ===Noun=== | {{head\|en\|verb form}}, {{en-adj}} | ✓ | Multiple POS |
| `1cc917d0_844_periodic_129649_accurses.xml` | accurses | ===Verb=== | {{head\|en\|verb form}} | ✓ | Verb form |
| `1bbcb577_1323_position_9_owler.xml` | owler | ===Noun=== | {{en-noun}} | ✓ | Two etymologies |
| `1b711f6f_4004_periodic_119676_posology.xml` | posology | ===Noun=== | {{en-noun}} | ✓ | |
| `222b8a4e_1733_periodic_169541_garce.xml` | garce | ===Noun=== | {{en-noun}} | ✓ | Also ==French== |
| `243d612d_1627_periodic_189487_Newby.xml` | Newby | ===Proper noun=== | {{en-proper noun}} | ✓ | Capitalized proper noun |

### 3B. Multi-Word English Entries (6 files)

| File | Title | POS Headers | Templates | Categories | Notes |
|------|-------|-------------|-----------|------------|-------|
| `000598a4_3931_multiword_rain_cats_and_dogs.xml` | rain cats and dogs | ===Verb=== | {{en-verb}} | ✓ | Idiom with spaces |
| `1443c3bb_2559_position_8_small_potatoes.xml` | small potatoes | ===Noun=== | {{en-noun}} | ✓ | Idiomatic phrase |
| `13a63d57_1109_periodic_69811_key_server.xml` | key server | ===Noun=== | {{en-noun}} | ✓ | Two-word compound |
| `1a018ca9_1598_periodic_109703_field_emission.xml` | field emission | ===Noun=== | {{en-noun}} | ✓ | Technical term |

**Key Observations:**
- All have `<ns>0</ns>`
- All have `==English==` section
- All have POS headers (===Noun===, ===Verb===, etc.)
- Most have English-specific templates ({{en-noun}}, {{en-verb}}, etc.)
- Most have English categories
- English section can appear in various positions (1st, 3rd, 5th, 8th, 9th, 10th)
- **EDGE CASE:** `gratis` has English section but NO English categories in the visible text

---

## Category 4: Non-English Only Entries (SHOULD BE FILTERED)

These are main namespace entries (`<ns>0</ns>`) but contain NO English sections.

### 4A. Non-English Latin Script Entries (16 files)

| File | Title | Languages Present | Notes |
|------|-------|-------------------|-------|
| `00031fbe_1680_pos_no_cat_woordenboek.xml` | woordenboek | ==Dutch== only | Dutch word for "dictionary" |
| `0bec14c8_3991_periodic_39892_nej.xml` | nej | ==Danish==, ==Hungarian==, ==Maltese==, ==Slovak==, ==Swedish==, ==White Hmong== | No English |
| `12335f7c_1186_position_6_esperimento.xml` | esperimento | ==Italian== only | |
| `1193b790_1415_periodic_59838_gudura.xml` | gudura | ==Romanian==, ==Serbo-Croatian== | |
| `0adcbbe9_1196_position_5_mjúkr.xml` | mjúkr | ==Old Norse== only | |
| `156b8301_1193_periodic_79784_Atelier.xml` | Atelier | ==German==, ==Luxembourgish== | Capitalized |
| `15379bfb_3525_position_6_hurma.xml` | hurma | ==Finnish==, ==Latvian==, ==Polish==, ==Serbo-Croatian==, ==Turkish== | Multiple languages |
| `139b4ab7_1046_position_7_zutano.xml` | zutano | ==Spanish== only | |
| `1926b3ea_1656_position_10_gedwola.xml` | gedwola | ==Old English== only | |
| `1a313e9f_1331_position_8_emperatriz.xml` | emperatriz | ==Spanish== only | |
| `234925d6_836_periodic_179514_gilim.xml` | gilim | ==Australian Kriol==, ==Sumerian== | Romanization |
| `260d40d6_821_periodic_219406_conllevando.xml` | conllevando | ==Spanish== only | Verb form |
| `24f78900_878_periodic_199460_agitamos.xml` | agitamos | ==Portuguese==, ==Spanish== | Verb form |
| `25829c5a_737_periodic_209433_aventajases.xml` | aventajases | ==Spanish== only | Verb form |
| `2820a818_853_periodic_259298_exilié.xml` | exilié | ==Asturian==, ==Spanish== | Verb form with accent |
| `279670e4_773_periodic_249325_flagelase.xml` | flagelase | ==Spanish== only | Verb form |
| `2717c96f_775_periodic_239352_encuerabais.xml` | encuerabais | ==Spanish== only | Verb form |
| `26919652_746_periodic_229379_desilusionaríamos.xml` | desilusionaríamos | ==Spanish== only | Long verb form with accent |

### 4B. Non-Latin Script Entries (10 files)

#### Chinese Characters (Han script):
| File | Title | Languages Present | Notes |
|------|-------|-------------------|-------|
| `05b3e280_925_position_2_溃.xml` | 溃 | ==Translingual==, ==Chinese== | Simplified Chinese |
| `05189b43_2116_position_1_弇.xml` | 弇 | ==Translingual==, ==Chinese==, ==Japanese==, ==Korean==, ==Vietnamese== | CJK unified |
| `04c818a1_1319_periodic_9973_墌.xml` | 墌 | ==Translingual==, ==Chinese==, ==Japanese== | |
| `07347336_1111_position_4_醟.xml` | 醟 | ==Translingual==, ==Chinese== | |
| `06504911_995_periodic_19946_緿.xml` | 緿 | ==Translingual==, ==Chinese== | |
| `0605c162_1060_position_2_癵.xml` | 癵 | ==Translingual==, ==Chinese== | |
| `20f4ff55_1068_periodic_159568_生活照.xml` | 生活照 | ==Chinese== only | Multi-character |
| `1fc7257c_1234_periodic_149595_徳用.xml` | 徳用 | ==Japanese== only | Multi-character |

#### Japanese Scripts:
| File | Title | Languages Present | Notes |
|------|-------|-------------------|-------|
| `198d6e49_1950_position_7_こちら.xml` | こちら | ==Japanese== only | Hiragana |
| `10d2ee16_920_position_4_為る.xml` | 為る | ==Japanese== only | Kanji + hiragana |

#### Cyrillic Script:
| File | Title | Languages Present | Notes |
|------|-------|-------------------|-------|
| `1fd3a938_980_position_10_фокстерьер.xml` | фокстерьер | ==Russian== only | Cyrillic |

**Key Observations:**
- All have `<ns>0</ns>`
- **NONE** have `==English==` section
- Should be filtered by absence of English language header
- Non-Latin scripts provide additional filtering challenges
- Some entries have ==Translingual== sections (CJK characters)
- Many Spanish verb forms (conjugated forms)

---

## Pattern Analysis & Edge Cases

### Pattern 1: Namespace Filtering
**What it tests:** Entries in non-main namespaces
- **Count:** 6 files (5 Wiktionary, 1 Appendix)
- **Expected behavior:** Filter based on `<ns>` tag value ≠ 0
- **Parser assumption:** Must check `<ns>` tag before processing content
- **Potential issue:** If parser doesn't check namespace early, may waste time processing meta pages

### Pattern 2: Redirect Detection
**What it tests:** Pages that redirect to other pages
- **Count:** 1 file
- **Expected behavior:** Filter based on `<redirect>` tag presence
- **Parser assumption:** Must check for `<redirect>` tag
- **Potential issue:** Parser might process content that doesn't exist

### Pattern 3: Language Section Detection
**What it tests:** Presence of `==English==` header
- **Count:** 31 with English, 26 without
- **Expected behavior:** Only extract entries with `==English==` section
- **Parser assumption:** Searches for exact pattern `==English==`
- **Potential issues:**
  - Case sensitivity
  - Whitespace variations
  - Position in file (English can be 1st, 3rd, 5th, 8th, 9th, or 10th language)

### Pattern 4: POS Header Detection
**What it tests:** Presence of POS headers like `===Noun===`, `===Verb===`, etc.
- **Expected behavior:** Extract entries with valid POS headers
- **Common POS headers found:**
  - ===Noun===
  - ===Verb===
  - ===Adjective===
  - ===Adverb===
  - ===Suffix===
  - ===Proper noun===
- **Potential issues:**
  - Level-3 headers (===) vs level-4 headers (====)
  - Custom POS like "===Etymology 1===" might be confused with POS

### Pattern 5: Template Usage
**What it tests:** Wiktionary-specific templates
- **Common templates:**
  - {{en-noun}}, {{en-verb}}, {{en-adj}}, {{en-adv}}
  - {{head|en|noun form}}, {{head|en|verb form}}
  - {{en-proper noun}}
- **Potential issues:** Parser might rely on templates, but not all entries use them consistently

### Pattern 6: Category Detection
**What it tests:** English category tags
- **Pattern:** `[[Category:English <type>]]`
- **EDGE CASE:** File `0003265e_4099_pos_no_cat_gratis.xml` has English section but NO visible English categories
- **Potential issue:** If parser requires categories for validation, it might miss valid entries

### Pattern 7: Multi-word Entries
**What it tests:** Entry titles with spaces
- **Count:** 4 files
- **Examples:** "rain cats and dogs", "small potatoes", "key server", "field emission"
- **Expected behavior:** Should be processed like single-word entries
- **Potential issue:** Parser might have special handling for spaces in titles

### Pattern 8: Non-Latin Scripts
**What it tests:** Unicode handling and script detection
- **Count:** 10 files (Chinese, Japanese, Cyrillic)
- **Expected behavior:** Filter if no English section
- **Potential issues:**
  - Unicode normalization
  - Regex patterns assuming ASCII/Latin
  - Character encoding issues

### Pattern 9: Multiple Language Sections
**What it tests:** Entries with many languages
- **Example:** `cat` has ==Translingual==, ==English==, and many others
- **Expected behavior:** Extract only English section
- **Potential issue:** Parser must correctly isolate English section boundaries

### Pattern 10: Position Variation
**What it tests:** English section at different positions
- **Positions found:** 1st, 3rd, 5th, 8th, 9th, 10th language section
- **Expected behavior:** Find English regardless of position
- **Potential issue:** Parser might assume English is always first

---

## Critical Edge Cases for Parser Testing

### 1. **`gratis` - Has English but NO English Categories**
- **File:** `0003265e_4099_pos_no_cat_gratis.xml`
- **Issue:** If parser validates via category tags, this entry might be incorrectly filtered
- **What to check:** Parser should NOT require English categories for valid extraction

### 2. **Entries with English in Non-First Position**
- **Examples:** `nuance` (position 3), `householder` (position 5), `small potatoes` (position 8)
- **Issue:** Parser must scan entire file, not stop at first language section
- **What to check:** Parser correctly finds `==English==` anywhere in file

### 3. **Multi-Word Titles**
- **Examples:** "rain cats and dogs", "key server"
- **Issue:** Title parsing, space handling
- **What to check:** Parser correctly handles spaces in `<title>` tags

### 4. **Entries with Multiple Etymologies**
- **Examples:** `free`, `owler`
- **Issue:** Structure is ===Etymology 1===, ====Adjective====, ===Etymology 2===, ====Verb====
- **What to check:** Parser handles nested POS headers under etymology sections

### 5. **Verb/Noun Forms (Inflections)**
- **Examples:** `pies`, `accurses`, `fuming`
- **Issue:** Use different templates like `{{head|en|verb form}}` instead of `{{en-verb}}`
- **What to check:** Parser recognizes inflected forms as valid entries

### 6. **Prefix/Suffix Entries**
- **Example:** `-phobic`
- **Issue:** Title starts with hyphen
- **What to check:** Parser handles non-alphabetic first characters

### 7. **Abbreviations**
- **Example:** `FMS`
- **Issue:** All caps, multiple POS (Noun + Proper noun)
- **What to check:** Parser handles case variations

### 8. **Capitalized Entries (Proper Nouns)**
- **Examples:** `Newby`, `Atelier`
- **Issue:** Capitalization might affect filtering
- **What to check:** Parser doesn't filter based on capitalization alone

---

## Recommendations for Parser Validation

### High Priority Checks:
1. **Namespace filtering is working** - Verify all 6 non-main namespace files are filtered
2. **Redirect filtering is working** - Verify redirect page is filtered
3. **English detection is accurate** - Verify all 31 English entries are extracted
4. **Non-English filtering is complete** - Verify all 26 non-English entries are filtered
5. **Position independence** - Verify English sections found at any position

### Medium Priority Checks:
6. **POS header detection** - Verify various POS types are recognized
7. **Multi-word title handling** - Verify 4 multi-word entries process correctly
8. **Etymology section handling** - Verify nested POS under etymology sections
9. **Template variations** - Verify both {{en-noun}} and {{head|en|noun}} work

### Low Priority Checks:
10. **Non-Latin script handling** - Verify clean rejection of 10 non-Latin entries
11. **Special characters in titles** - Verify `-phobic` and similar entries
12. **Case handling** - Verify `FMS` and `Newby` entries

---

## Summary Statistics

| Category | Count | Should Pass? |
|----------|-------|--------------|
| Namespace ≠ 0 | 6 | ❌ Filter |
| Redirects | 1 | ❌ Filter |
| Has ==English== (single word) | 25 | ✅ Extract |
| Has ==English== (multi-word) | 6 | ✅ Extract |
| No ==English== (Latin script) | 16 | ❌ Filter |
| No ==English== (non-Latin script) | 10 | ❌ Filter |
| **TOTAL** | **64** | **31 Pass, 33 Filter** |

---

## Files Requiring Special Attention

### Should PASS (Extract):
All 31 files with ==English== sections should be successfully extracted, including:
- `0003265e_4099_pos_no_cat_gratis.xml` (no categories)
- `064d06ee_4080_position_3_nuance.xml` (English at position 3)
- `11125693_2897_position_5_householder.xml` (English at position 5)
- `1443c3bb_2559_position_8_small_potatoes.xml` (English at position 8, multi-word)
- All multi-word entries (4 files)

### Should FILTER:
All 33 files without ==English== or in wrong namespaces should be filtered, including:
- All 6 namespace ≠ 0 files
- 1 redirect file
- All 26 files without ==English==

---

## Conclusion

This diagnostic set provides comprehensive coverage of:
- ✅ Different namespaces (main, Wiktionary, Appendix, Rhymes)
- ✅ Redirect pages
- ✅ English entries with various POS types
- ✅ Multi-language entries with English in different positions
- ✅ Non-English only entries
- ✅ Non-Latin script entries
- ✅ Multi-word entries
- ✅ Special characters and capitalization
- ✅ Edge case: Entry with English but no categories

The parser should be tested against all 64 files to ensure:
1. All 6 non-main namespace files are filtered
2. 1 redirect is filtered
3. All 31 files with ==English== are extracted successfully
4. All 26 files without ==English== are filtered

Any deviation from this expected behavior indicates a bug in the scanning logic.
