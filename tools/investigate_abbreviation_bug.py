#!/usr/bin/env python3
"""
Investigate Python's is_abbreviation false positives.

Checks what pattern Python is matching that causes false positives
on days of the week, "acronym", and "i".
"""

import re
from pathlib import Path

# Check Python's implementation
print("Python's ABBREVIATION_TEMPLATE pattern:")
with open('tools/wiktionary_scanner_parser.py') as f:
    for i, line in enumerate(f, 1):
        if 'ABBREVIATION_TEMPLATE' in line and '=' in line and 'compile' in line:
            print(f"  Line {i}: {line.strip()}")

print("\nChecking wikitext samples for false positives:")
print("=" * 80)

false_positives = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'acronym', 'i']

for word in false_positives:
    xml_file = Path(f'tests/wikitext-samples/{word}.xml')
    if not xml_file.exists():
        print(f"\n{word}: No wikitext sample available")
        continue

    with open(xml_file, encoding='utf-8') as f:
        content = f.read()

    # Extract English section
    match = re.search(r'==\s*English\s*==(.+?)(?:^==\s*[^=]|\Z)', content, re.IGNORECASE | re.DOTALL | re.MULTILINE)
    if not match:
        print(f"\n{word}: No English section")
        continue

    english = match.group(1)

    print(f"\n{word.upper()}:")
    print("-" * 80)

    # Check for actual abbreviation templates
    abbr_templates = re.findall(r'\{\{(?:abbreviation of|abbrev of|abbr of|initialism of)\|en\|[^}]+\}\}', english, re.IGNORECASE)
    if abbr_templates:
        print(f"  ✗ HAS abbreviation templates: {len(abbr_templates)}")
        for tmpl in abbr_templates[:3]:
            print(f"    - {tmpl}")
    else:
        print(f"  ✓ NO abbreviation templates")

    # Check for references TO abbreviations
    abbr_refs = re.findall(r'.*abbreviation.*', english, re.IGNORECASE)
    if abbr_refs:
        print(f"  ! References to abbreviations: {len(abbr_refs)}")
        for ref in abbr_refs[:3]:
            print(f"    - {ref.strip()[:100]}")

    # Check for {{abbr}} or {{a}} templates
    other_abbr = re.findall(r'\{\{(?:abbr?|a)\|[^}]*\}\}', english, re.IGNORECASE)
    if other_abbr:
        print(f"  ! Other abbr-related templates: {len(other_abbr)}")
        for tmpl in other_abbr[:3]:
            print(f"    - {tmpl}")
