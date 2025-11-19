#!/usr/bin/env python3
"""
Analyze syllable information implementation and sources.

This script examines:
1. Current syllable extraction implementation
2. Conflicts between different syllable sources (hyphenation, rhymes, categories)
3. Coverage and utility for filtering
4. Recommendations for word list generation
"""

import re
import json
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from collections import defaultdict

# Same regex patterns as wiktionary_scanner_parser.py
HYPHENATION_TEMPLATE = re.compile(r'\{\{(?:hyphenation|hyph)\|en\|([^}]+)\}\}', re.IGNORECASE)
RHYMES_SYLLABLE = re.compile(r'\{\{rhymes\|en\|[^}]*\|s=(\d+)', re.IGNORECASE)
SYLLABLE_CATEGORY = re.compile(r'\[\[Category:English\s+(\d+)-syllable\s+words?\]\]', re.IGNORECASE)
TITLE_PATTERN = re.compile(r'<title>([^<]+)</title>')

KNOWN_LANG_CODES = {
    'en', 'da', 'de', 'es', 'fr', 'it', 'pt', 'nl', 'sv', 'no', 'fi',
    'pl', 'cs', 'sk', 'hu', 'ro', 'bg', 'ru', 'uk', 'el', 'tr', 'ar',
    'he', 'hi', 'bn', 'pa', 'ta', 'te', 'mr', 'gu', 'kn', 'ml', 'si',
    'th', 'vi', 'zh', 'ja', 'ko', 'id', 'ms', 'tl', 'fa', 'ur',
    'en-US', 'en-GB', 'en-AU', 'en-CA', 'en-NZ', 'en-ZA', 'en-IE', 'en-IN',
    'la', 'sa', 'grc', 'ang', 'enm', 'fro', 'non',
}


def extract_syllable_count_from_hyphenation(text: str, word: str) -> Optional[int]:
    """Extract syllable count from hyphenation template."""
    match = HYPHENATION_TEMPLATE.search(text)
    if not match:
        return None

    content = match.group(1)
    alternatives = content.split('||')
    first_alt = alternatives[0] if alternatives else content
    parts = first_alt.split('|')

    syllables = []
    for i, part in enumerate(parts):
        part = part.strip()
        if not part or '=' in part:
            continue

        if i == 0:
            if part in KNOWN_LANG_CODES and part.lower() != word.lower():
                continue
            if len(parts) == 1 and len(part) > 3:
                return None

        syllables.append(part)

    return len(syllables) if syllables else None


def extract_syllable_count_from_rhymes(text: str) -> Optional[int]:
    """Extract syllable count from rhymes template."""
    match = RHYMES_SYLLABLE.search(text)
    if match:
        return int(match.group(1))
    return None


def extract_syllable_count_from_categories(text: str) -> Optional[int]:
    """Extract syllable count from category labels."""
    match = SYLLABLE_CATEGORY.search(text)
    if match:
        return int(match.group(1))
    return None


def find_all_hyphenation_templates(text: str) -> List[str]:
    """Find all hyphenation templates in text."""
    return HYPHENATION_TEMPLATE.findall(text)


def find_all_rhyme_templates(text: str) -> List[str]:
    """Find all rhyme templates with syllable counts."""
    return re.findall(r'\{\{rhymes\|en\|[^}]*\|s=(\d+)[^}]*\}\}', text, re.IGNORECASE)


def find_all_category_templates(text: str) -> List[str]:
    """Find all syllable category labels."""
    return re.findall(r'\[\[Category:English\s+(\d+)-syllable\s+words?\]\]', text, re.IGNORECASE)


def analyze_slice(slice_path: Path) -> Dict:
    """Analyze a single Wiktionary slice for syllable information."""
    with open(slice_path, 'r', encoding='utf-8') as f:
        text = f.read()

    # Extract title
    title_match = TITLE_PATTERN.search(text)
    word = title_match.group(1) if title_match else "unknown"

    # Extract from all sources
    hyph_count = extract_syllable_count_from_hyphenation(text, word)
    rhyme_count = extract_syllable_count_from_rhymes(text)
    cat_count = extract_syllable_count_from_categories(text)

    # Find all instances
    all_hyph = find_all_hyphenation_templates(text)
    all_rhyme = find_all_rhyme_templates(text)
    all_cat = find_all_category_templates(text)

    return {
        'word': word,
        'file': slice_path.name,
        'hyphenation_count': hyph_count,
        'rhyme_count': rhyme_count,
        'category_count': cat_count,
        'all_hyphenation': all_hyph,
        'all_rhyme': all_rhyme,
        'all_category': all_cat,
        'has_conflict': (
            hyph_count is not None and rhyme_count is not None and hyph_count != rhyme_count
        ) or (
            hyph_count is not None and cat_count is not None and hyph_count != cat_count
        ) or (
            rhyme_count is not None and cat_count is not None and rhyme_count != cat_count
        ),
    }


def main():
    """Main analysis function."""
    print("# Syllable Information Implementation Review")
    print()
    print("**Analysis Date:** 2025-11-19")
    print()

    # Analyze diagnostic slices
    slices_dir = Path("data/diagnostic/wikt_slices")

    if not slices_dir.exists():
        print(f"⚠️  Warning: {slices_dir} not found")
        print()

    # Analyze both syllable-specific slices AND baseline slices (which have good examples)
    syllable_slices = list(slices_dir.glob("*syllable*.xml"))
    baseline_slices = list(slices_dir.glob("*baseline*.xml"))
    all_slices = syllable_slices + baseline_slices

    print(f"## Diagnostic Slice Analysis")
    print()
    print(f"Found {len(syllable_slices)} syllable-tagged slices and {len(baseline_slices)} baseline slices")
    print(f"Analyzing {len(all_slices)} total slices for syllable extraction...")
    print()

    results = []
    for slice_path in sorted(all_slices):
        result = analyze_slice(slice_path)
        results.append(result)

    # Filter to only show results that have at least one source
    results_with_data = [r for r in results if
                         r['hyphenation_count'] is not None or
                         r['rhyme_count'] is not None or
                         r['category_count'] is not None]

    print(f"**Found syllable data in {len(results_with_data)}/{len(results)} slices**")
    print()

    # Display results (only those with data)
    for result in results_with_data:
        print(f"### {result['word']} (`{result['file']}`)")
        print()

        print(f"**Syllable Sources:**")
        print()

        if result['hyphenation_count'] is not None:
            print(f"- **Hyphenation:** {result['hyphenation_count']} syllables")
            if result['all_hyphenation']:
                for template in result['all_hyphenation'][:3]:  # Show first 3
                    print(f"  - `{{{{hyphenation|en|{template}}}}}`")
        else:
            print(f"- **Hyphenation:** Not found or unreliable")
        print()

        if result['rhyme_count'] is not None:
            print(f"- **Rhymes:** {result['rhyme_count']} syllables")
            if result['all_rhyme']:
                for template in result['all_rhyme'][:3]:
                    print(f"  - Found s={template}")
        else:
            print(f"- **Rhymes:** Not found")
        print()

        if result['category_count'] is not None:
            print(f"- **Category:** {result['category_count']} syllables")
            if result['all_category']:
                for cat in result['all_category'][:3]:
                    print(f"  - Category: English {cat}-syllable words")
        else:
            print(f"- **Category:** Not found")
        print()

        if result['has_conflict']:
            print(f"⚠️  **CONFLICT DETECTED:**")
            print(f"  - Hyphenation: {result['hyphenation_count']}")
            print(f"  - Rhymes: {result['rhyme_count']}")
            print(f"  - Category: {result['category_count']}")
            print()
        else:
            print(f"✅ **No conflicts** between sources")
            print()

        print("---")
        print()

    # Summary statistics
    conflicts = sum(1 for r in results_with_data if r['has_conflict'])
    has_hyph = sum(1 for r in results_with_data if r['hyphenation_count'] is not None)
    has_rhyme = sum(1 for r in results_with_data if r['rhyme_count'] is not None)
    has_cat = sum(1 for r in results_with_data if r['category_count'] is not None)
    total = len(results_with_data)

    print("## Source Coverage Summary")
    print()
    print(f"**Total slices analyzed:** {len(results)}")
    print(f"**Slices with syllable data:** {total}")
    print()
    print(f"| Source | Coverage | Percentage |")
    print(f"|--------|----------|------------|")
    print(f"| Hyphenation | {has_hyph}/{total} | {100*has_hyph/total if total else 0:.0f}% |")
    print(f"| Rhymes | {has_rhyme}/{total} | {100*has_rhyme/total if total else 0:.0f}% |")
    print(f"| Category | {has_cat}/{total} | {100*has_cat/total if total else 0:.0f}% |")
    print()
    print(f"**Conflicts detected:** {conflicts}/{total}")
    print()

    # Implementation status
    print("## Implementation Status")
    print()
    print("### ✅ COMPLETED")
    print()
    print("1. **Extraction Pipeline**")
    print("   - Three source extractors implemented:")
    print("     - Hyphenation template (priority 1)")
    print("     - Rhymes template (priority 2)")
    print("     - Category labels (priority 3)")
    print("   - Smart filtering to avoid false positives")
    print("   - Language code whitelist for accuracy")
    print()
    print("2. **Data Flow**")
    print("   - Syllable counts stored as integer field")
    print("   - Preserved through ingestion (`wikt_ingest.py`)")
    print("   - Preserved through merging (`merge_all.py`)")
    print("   - Only set when reliable (never guessed)")
    print()
    print("3. **Analysis & Reporting**")
    print("   - Comprehensive syllable statistics in `analyze_metadata.py`")
    print("   - Distribution tables, averages, samples")
    print("   - Coverage percentage tracking")
    print()

    print("### ❌ NOT YET IMPLEMENTED")
    print()
    print("1. **Wordlist Filtering**")
    print("   - Schema defines filters but not implemented:")
    print("     - `min_syllables`: Include words with ≥ N syllables")
    print("     - `max_syllables`: Include words with ≤ N syllables")
    print("     - `exact_syllables`: Include words with exactly N syllables")
    print("     - `require_syllables`: Exclude words without syllable data")
    print("   - Location: `docs/schema/wordlist_spec.schema.json` (lines 296-320)")
    print("   - Needs implementation in: `src/openword/export_wordlist.py`")
    print()
    print("2. **Filter Application**")
    print("   - No code in `src/openword/filters.py` for syllable filtering")
    print("   - No integration in wordlist export pipeline")
    print()

    print("## Priority Handling & Conflict Resolution")
    print()
    print("The implementation uses a **waterfall priority system** with no conflict checking:")
    print()
    print("```python")
    print("# Priority 1: Hyphenation template")
    print("if hyphenation_count is not None:")
    print("    syllable_count = hyphenation_count")
    print("# Priority 2: Rhymes template")
    print("elif rhymes_count is not None:")
    print("    syllable_count = rhymes_count")
    print("# Priority 3: Category labels")
    print("elif category_count is not None:")
    print("    syllable_count = category_count")
    print("```")
    print()
    print("**Implication:** If hyphenation exists, other sources are never checked or compared.")
    print()
    print("This means:")
    print("- ✅ **No conflicts in output** (only one source used per word)")
    print("- ✅ **Prioritizes most reliable source** (hyphenation)")
    print("- ⚠️  **Cannot detect Wiktionary data inconsistencies** (if sources disagree)")
    print()

    print("## Recommendations")
    print()
    print("### 1. **Implementation Priority: Enable Filtering** 🔴 HIGH")
    print()
    print("**What:** Implement syllable filtering in wordlist export")
    print()
    print("**Why:** The extraction and storage are complete. Filtering is the only missing piece for the use case described (children's word game with 2-syllable concrete nouns).")
    print()
    print("**How:**")
    print("```python")
    print("# In src/openword/filters.py")
    print("def filter_by_syllables(entries, spec):")
    print("    syllable_spec = spec.get('syllables', {})")
    print("    if not syllable_spec:")
    print("        return entries")
    print("    ")
    print("    min_syl = syllable_spec.get('min')")
    print("    max_syl = syllable_spec.get('max')")
    print("    exact_syl = syllable_spec.get('exact')")
    print("    require = syllable_spec.get('require_syllables', False)")
    print("    ")
    print("    filtered = []")
    print("    for entry in entries:")
    print("        syl = entry.get('syllables')")
    print("        ")
    print("        # Require syllable data if specified")
    print("        if require and syl is None:")
    print("            continue")
    print("        ")
    print("        # Skip if no data and filters specified")
    print("        if syl is None and (min_syl or max_syl or exact_syl):")
    print("            continue")
    print("        ")
    print("        # Apply filters")
    print("        if exact_syl and syl != exact_syl:")
    print("            continue")
    print("        if min_syl and syl < min_syl:")
    print("            continue")
    print("        if max_syl and syl > max_syl:")
    print("            continue")
    print("        ")
    print("        filtered.append(entry)")
    print("    ")
    print("    return filtered")
    print("```")
    print()
    print("**Impact:**")
    print("- Enables the children's word game use case immediately")
    print("- Allows filtering like: 'exact: 2, require_syllables: true' → only 2-syllable words with data")
    print("- Works with existing ~30k words with syllable data (2% coverage from report)")
    print()

    print("### 2. **Data Quality: Add Conflict Detection** 🟡 MEDIUM")
    print()
    print("**What:** Optionally log when sources disagree (hyphenation vs rhymes vs category)")
    print()
    print("**Why:** Helps identify Wiktionary data quality issues for potential upstream fixes")
    print()
    print("**How:**")
    print("```python")
    print("# In wiktionary_scanner_parser.py, around line 1202")
    print("# Check all sources and log conflicts")
    print("if hyph_count and rhyme_count and hyph_count != rhyme_count:")
    print("    logger.warning(f'Syllable conflict in {word}: hyph={hyph_count} rhyme={rhyme_count}')")
    print("```")
    print()
    print("**Impact:**")
    print("- No change to output (still uses priority system)")
    print("- Visibility into data quality issues")
    print("- Potential for contributing fixes back to Wiktionary")
    print()

    print("### 3. **Coverage Improvement: Consider IPA Parsing** 🟢 LOW")
    print()
    print("**What:** Extract syllable counts from IPA pronunciation (e.g., `/ˈdɪk.ʃə.nɛ.ɹi/` → 4 syllables)")
    print()
    print("**Why:** Could increase coverage from 2% to potentially 40-60%")
    print()
    print("**Caution:** IPA syllable counting is complex:")
    print("- Syllabic consonants (e.g., /l̩/, /n̩/)")
    print("- Diphthongs vs two vowels")
    print("- Language-specific rules")
    print("- Would violate current 'never guess' principle")
    print()
    print("**Recommendation:** NOT recommended unless:")
    print("1. Manual validation on 1000+ entries shows >95% accuracy")
    print("2. Flagged separately from Wiktionary-sourced counts")
    print("3. Users can filter by 'reliable_syllables_only'")
    print()

    print("### 4. **Source Priority Validation** 🟢 LOW")
    print()
    print("**What:** Verify hyphenation is indeed more reliable than rhymes/categories")
    print()
    print("**Why:** Current priority assumes hyphenation is best, but no empirical validation")
    print()
    print("**How:**")
    print("1. Process full Wiktionary dump")
    print("2. Track all three sources for words that have multiple")
    print("3. Manually validate sample of 100 conflicts")
    print("4. Adjust priority if needed")
    print()

    print("## Answer to User Questions")
    print()
    print("### Q1: Can syllable info be used at list generation time to filter words?")
    print()
    print("**Current Status:** ❌ NO - Schema defined but not implemented")
    print()
    print("**After Implementation:** ✅ YES - Would take ~30 minutes to implement filtering")
    print()
    print("**Coverage:** ~30k words (2% of entries) have syllable data from Wiktionary")
    print()
    print("**Example Use Case:**")
    print("```json")
    print("{")
    print('  "pos": ["noun"],')
    print('  "syllables": {"exact": 2, "require_syllables": true},')
    print('  "register": {"exclude": ["slang", "vulgar"]},')
    print('  "concrete": true,')
    print('  "frequency_tier": {"max": "N"}')
    print("}")
    print("```")
    print()
    print("This would produce hundreds of words like: 'table', 'window', 'pencil', 'rabbit'")
    print()

    print("### Q2: Do hyphenation vs rhyme (or other sources) conflict or disagree?")
    print()
    print(f"**Based on diagnostic slices:** {conflicts}/{len(results)} conflicts detected")
    print()
    print("**Current Implementation:** Conflicts are invisible due to priority waterfall")
    print()
    print("- Hyphenation always wins if present")
    print("- Other sources only used as fallback")
    print("- No logging or tracking of disagreements")
    print()
    print("**Recommendation:**")
    print("- Keep priority system (don't break ties)")
    print("- Add optional conflict logging for data quality monitoring")
    print("- This helps identify issues to potentially fix upstream in Wiktionary")
    print()

    print("### Q3: What is the most utility we can get from what source of truth?")
    print()
    print("**Source of Truth: Wiktionary hyphenation templates**")
    print()
    print("**Strengths:**")
    print("- Human-curated and reviewed")
    print("- Explicit syllable boundaries (not just counts)")
    print("- High accuracy when present")
    print("- Already extracted and stored")
    print()
    print("**Limitations:**")
    print("- Only 2% coverage (30k/1.3M entries)")
    print("- Wiktionary editors prioritize common words")
    print("- Rare/technical words often lack data")
    print()
    print("**Maximum Utility Strategy:**")
    print()
    print("1. **Accept sparse coverage** ✅")
    print("   - For use cases like children's games, 30k words is MORE than enough")
    print("   - Quality over quantity for syllable-filtered lists")
    print()
    print("2. **Implement filtering NOW** 🔴")
    print("   - Unlock the value of existing 30k syllable-tagged words")
    print("   - Enable 'require_syllables: true' for quality-controlled lists")
    print()
    print("3. **Never guess syllables in extraction** ✅ (already done)")
    print("   - Maintain 'reliable data only' principle")
    print("   - Let downstream applications add heuristics if needed")
    print()
    print("4. **Consider multiple fallbacks** 🟡")
    print("   - Current: hyphenation → rhymes → categories (good!)")
    print("   - Potential future: Add IPA parsing with 'confidence_level' field")
    print()

    print("## Summary")
    print()
    print("**Status:** 🟡 80% Complete")
    print()
    print("- ✅ Extraction: Excellent (3 sources, smart filtering)")
    print("- ✅ Storage: Complete (preserved through pipeline)")
    print("- ✅ Analysis: Complete (comprehensive reporting)")
    print("- ❌ Filtering: Not implemented (blocking use case)")
    print()
    print("**Critical Path:** Implement syllable filtering in `export_wordlist.py`")
    print()
    print("**Time Estimate:** ~30-60 minutes for filtering implementation + tests")
    print()
    print("**Value:** Unlocks immediate use for word games, educational apps, poetry tools, etc.")
    print()


if __name__ == "__main__":
    main()
