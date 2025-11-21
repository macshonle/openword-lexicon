#!/usr/bin/env python3
"""
Test is_derogatory detection with taffy example.
"""

import subprocess
import tempfile
import json
import os

# Test XML with taffy entries
test_xml = """<mediawiki>
<page>
<title>taffy</title>
<ns>0</ns>
<text>
==English==

===Etymology 1===
Uncertain origin.

====Noun====
{{en-noun}}

# {{lb|en|US|informal}} A type of chewy [[candy]].

===Etymology 2===
From {{m|en|Taffy}}, a Welsh name.

====Noun====
{{en-noun}}

# {{lb|en|UK|derogatory|ethnic slur}} A [[Welsh]] person.

[[Category:English ethnic slurs]]
</text>
</page>
</mediawiki>"""

# Write test XML
with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
    f.write(test_xml)
    test_xml_path = f.name

# Run Rust parser
rust_out = tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False)
rust_out.close()

print("Running Rust parser on taffy test case...")
result = subprocess.run([
    'tools/wiktionary-rust/target/release/wiktionary-rust',
    test_xml_path,
    rust_out.name
], capture_output=True, text=True)

if result.returncode != 0:
    print(f"Error running Rust parser: {result.stderr}")
    os.unlink(test_xml_path)
    os.unlink(rust_out.name)
    exit(1)

# Analyze results
print("\n" + "="*80)
print("TAFFY ENTRIES - is_derogatory TEST")
print("="*80)

entries = []
with open(rust_out.name) as f:
    for line in f:
        entries.append(json.loads(line))

print(f"\nFound {len(entries)} entries for 'taffy'\n")

for i, entry in enumerate(entries, 1):
    print(f"Entry {i}:")
    print(f"  word: {entry['word']}")
    print(f"  pos: {', '.join(entry.get('pos', []))}")
    print(f"  is_derogatory: {entry.get('is_derogatory')}")
    print(f"  is_informal: {entry.get('is_informal')}")
    print(f"  is_regional: {entry.get('is_regional')}")
    if entry.get('labels'):
        if 'register' in entry['labels']:
            print(f"  register: {entry['labels']['register']}")
        if 'region' in entry['labels']:
            print(f"  region: {entry['labels']['region']}")
    print()

# Cleanup
os.unlink(test_xml_path)
os.unlink(rust_out.name)

# Verify results
print("="*80)
print("VERIFICATION")
print("="*80)

has_derogatory = any(e.get('is_derogatory') for e in entries)
has_non_derogatory = any(not e.get('is_derogatory') for e in entries)

if has_derogatory and has_non_derogatory:
    print("✓ SUCCESS: Found both derogatory and non-derogatory entries")
    print("✓ The 'taffy problem' is now trackable with is_derogatory flag")
    print("✓ Downstream consumers can filter by this flag")
else:
    print("✗ ISSUE: Expected both derogatory and non-derogatory entries")
    if has_derogatory:
        print("  - Found derogatory entries")
    if has_non_derogatory:
        print("  - Found non-derogatory entries")
