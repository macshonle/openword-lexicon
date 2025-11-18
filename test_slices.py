#!/usr/bin/env python3
"""
Test the scanner against all diagnostic slices.
Directly uses the parsing logic without Rich dependencies.
"""

import re
from pathlib import Path


# Copied patterns from wiktionary_scanner_parser.py
ENGLISH_SECTION = re.compile(r'==\s*English\s*==', re.IGNORECASE)
LANGUAGE_SECTION = re.compile(r'^==\s*([^=]+?)\s*==$', re.MULTILINE)
TITLE_PATTERN = re.compile(r'<title>([^<]+)</title>')
NS_PATTERN = re.compile(r'<ns>(\d+)</ns>')
TEXT_PATTERN = re.compile(r'<text[^>]*>(.+?)</text>', re.DOTALL)
REDIRECT_PATTERN = re.compile(r'<redirect\s+title="[^"]+"')
DICT_ONLY = re.compile(r'\{\{no entry\|en', re.IGNORECASE)

SPECIAL_PAGE_PREFIXES = (
    'Wiktionary:',
    'MediaWiki:',
    'Module:',
    'Thread:',
    'Appendix:',
    'Help:',
    'Template:',
    'Reconstruction:',
    'Unsupported titles/',
    'Category:',
)


def extract_page_content(page_xml: str):
    """
    Extract title and text from page XML using simple regex.
    Returns (title, text) or None if not found.
    Special pages (known prefixes) return ('SPECIAL_PAGE', title) even if redirects.
    Redirects return ('REDIRECT', title).
    Dictionary-only terms return ('DICT_ONLY', title, text).
    Non-English pages return ('NON_ENGLISH', title, languages) where languages is a list.
    """
    # Extract title
    title_match = TITLE_PATTERN.search(page_xml)
    if not title_match:
        return None
    title = title_match.group(1)

    # Check namespace FIRST - only process main namespace (ns=0)
    ns_match = NS_PATTERN.search(page_xml)
    if ns_match:
        namespace = int(ns_match.group(1))
        if namespace != 0:
            return ('SPECIAL_PAGE', title)

    # Check for special pages by title prefix (backup for entries without ns tag)
    if title.startswith(SPECIAL_PAGE_PREFIXES):
        return ('SPECIAL_PAGE', title)

    # Filter translation subpages
    if '/translations' in title or '/Translations' in title:
        return ('SPECIAL_PAGE', title)

    # Check for redirects AFTER special pages
    if REDIRECT_PATTERN.search(page_xml):
        return ('REDIRECT', title)

    # Extract text
    text_match = TEXT_PATTERN.search(page_xml)
    if not text_match:
        return None
    text = text_match.group(1)

    # Check for English section
    has_english = ENGLISH_SECTION.search(text)

    # Check for dictionary-only terms
    if has_english and DICT_ONLY.search(text):
        return ('DICT_ONLY', title, text)

    # If no English section, extract languages present
    if not has_english:
        languages = []
        for match in LANGUAGE_SECTION.finditer(text):
            lang = match.group(1).strip()
            if lang.lower() != 'english':
                languages.append(lang)
        return ('NON_ENGLISH', title, languages)

    return (title, text)


def test_slice(slice_path: Path):
    """Test a single slice file."""
    # Read the XML
    with open(slice_path, 'r', encoding='utf-8') as f:
        page_xml = f.read()

    # Extract title for reporting
    title_match = TITLE_PATTERN.search(page_xml)
    title = title_match.group(1) if title_match else "NO_TITLE"

    # Extract namespace
    ns_match = NS_PATTERN.search(page_xml)
    namespace = int(ns_match.group(1)) if ns_match else None

    # Test extract_page_content
    result = extract_page_content(page_xml)

    return {
        'file': slice_path.name,
        'title': title,
        'namespace': namespace,
        'result_type': result[0] if result else 'NONE',
        'result': result,
    }


def main():
    slices_dir = Path('data/diagnostic/wikt_slices')

    # Get all slice files
    slice_files = sorted(slices_dir.glob('*.xml'))

    print(f"Testing {len(slice_files)} slice files...")
    print()

    # Test each slice
    results = []
    for slice_path in slice_files:
        try:
            result = test_slice(slice_path)
            results.append(result)
        except Exception as e:
            results.append({
                'file': slice_path.name,
                'title': 'ERROR',
                'namespace': None,
                'result_type': 'EXCEPTION',
                'error': str(e),
            })

    # Categorize results
    passed = []
    filtered_namespace = []
    filtered_redirect = []
    filtered_dict_only = []
    filtered_non_english = []
    filtered_none = []
    exceptions = []

    for r in results:
        rt = r['result_type']
        if rt == 'SPECIAL_PAGE':
            filtered_namespace.append(r)
        elif rt == 'REDIRECT':
            filtered_redirect.append(r)
        elif rt == 'DICT_ONLY':
            filtered_dict_only.append(r)
        elif rt == 'NON_ENGLISH':
            filtered_non_english.append(r)
        elif rt == 'NONE':
            filtered_none.append(r)
        elif rt == 'EXCEPTION':
            exceptions.append(r)
        else:
            # Has title and text
            passed.append(r)

    # Print summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total files: {len(results)}")
    print(f"Passed (extracted): {len(passed)}")
    print(f"Filtered - Namespace: {len(filtered_namespace)}")
    print(f"Filtered - Redirect: {len(filtered_redirect)}")
    print(f"Filtered - Dict-only: {len(filtered_dict_only)}")
    print(f"Filtered - Non-English: {len(filtered_non_english)}")
    print(f"Filtered - None: {len(filtered_none)}")
    print(f"Exceptions: {len(exceptions)}")
    print()

    # Expected results based on ANALYSIS_REPORT.md
    expected_pass = 31
    expected_filter_ns = 6
    expected_filter_redirect = 1
    expected_filter_non_english = 26

    print("=" * 80)
    print("EXPECTED vs ACTUAL")
    print("=" * 80)
    print(f"Expected to pass: {expected_pass:2d}  | Actual: {len(passed):2d}  {'✓' if len(passed) == expected_pass else '✗ MISMATCH'}")
    print(f"Expected ns filter: {expected_filter_ns:2d}  | Actual: {len(filtered_namespace):2d}  {'✓' if len(filtered_namespace) == expected_filter_ns else '✗ MISMATCH'}")
    print(f"Expected redirect: {expected_filter_redirect:2d}  | Actual: {len(filtered_redirect):2d}  {'✓' if len(filtered_redirect) == expected_filter_redirect else '✗ MISMATCH'}")
    print(f"Expected non-EN: {expected_filter_non_english:2d}  | Actual: {len(filtered_non_english):2d}  {'✓' if len(filtered_non_english) == expected_filter_non_english else '✗ MISMATCH'}")
    print()

    # Print details
    print("=" * 80)
    print(f"PASSED (Should extract) - {len(passed)} files")
    print("=" * 80)
    for r in sorted(passed, key=lambda x: x['file']):
        print(f"✓ {r['file']:60s} | {r['title']}")
    print()

    print("=" * 80)
    print(f"FILTERED - NAMESPACE (Expected) - {len(filtered_namespace)} files")
    print("=" * 80)
    for r in sorted(filtered_namespace, key=lambda x: x['file']):
        print(f"• {r['file']:60s} | ns={r['namespace']} | {r['title']}")
    print()

    print("=" * 80)
    print(f"FILTERED - REDIRECT (Expected) - {len(filtered_redirect)} files")
    print("=" * 80)
    for r in sorted(filtered_redirect, key=lambda x: x['file']):
        print(f"• {r['file']:60s} | {r['title']}")
    print()

    print("=" * 80)
    print(f"FILTERED - NON-ENGLISH (Expected) - {len(filtered_non_english)} files")
    print("=" * 80)
    for r in sorted(filtered_non_english, key=lambda x: x['file']):
        languages = r['result'][2] if len(r['result']) > 2 else []
        lang_str = ', '.join(languages[:3])
        if len(languages) > 3:
            lang_str += f', ... ({len(languages)} total)'
        print(f"• {r['file']:60s} | {r['title']:20s} | {lang_str}")
    print()

    if filtered_dict_only:
        print("=" * 80)
        print(f"FILTERED - DICT-ONLY - {len(filtered_dict_only)} files")
        print("=" * 80)
        for r in sorted(filtered_dict_only, key=lambda x: x['file']):
            print(f"⚠ {r['file']:60s} | {r['title']}")
        print()

    if filtered_none:
        print("=" * 80)
        print(f"FILTERED - NONE (Needs investigation) - {len(filtered_none)} files")
        print("=" * 80)
        for r in sorted(filtered_none, key=lambda x: x['file']):
            print(f"⚠ {r['file']:60s} | {r['title']}")
        print()

    if exceptions:
        print("=" * 80)
        print(f"EXCEPTIONS (Bugs) - {len(exceptions)} files")
        print("=" * 80)
        for r in sorted(exceptions, key=lambda x: x['file']):
            print(f"✗ {r['file']:60s} | {r.get('error', 'Unknown error')}")
        print()


if __name__ == '__main__':
    main()
