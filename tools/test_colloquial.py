#!/usr/bin/env python3
"""Quick test: verify colloquial detection in both parsers"""

import json
import subprocess
import tempfile
from pathlib import Path

# Create a minimal test XML with a word that has {{lb|en|colloquial}}
test_xml = """<mediawiki>
<page>
<title>testword</title>
<ns>0</ns>
<text>
==English==

===Noun===
{{en-noun}}

# {{lb|en|colloquial}} A test word.

[[Category:English nouns]]
</text>
</page>
</mediawiki>"""

# Write test XML
with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
    f.write(test_xml)
    test_xml_path = f.name

# Run Python parser
python_out = tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False)
python_out.close()

print("Running Python parser...")
subprocess.run([
    'python', 'tools/wiktionary_scanner_parser.py',
    test_xml_path,
    python_out.name
], check=True, capture_output=True)

# Run Rust parser
rust_out = tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False)
rust_out.close()

print("Running Rust parser...")
subprocess.run([
    'tools/wiktionary-rust/target/release/wiktionary-rust',
    test_xml_path,
    rust_out.name
], check=True, capture_output=True)

# Compare results
print("\nPython output:")
with open(python_out.name) as f:
    py_entry = json.loads(f.read())
    print(f"  is_informal: {py_entry.get('is_informal')}")
    print(f"  labels: {py_entry.get('labels')}")

print("\nRust output:")
with open(rust_out.name) as f:
    rust_entry = json.loads(f.read())
    print(f"  is_informal: {rust_entry.get('is_informal')}")
    print(f"  labels: {rust_entry.get('labels')}")

# Cleanup
Path(test_xml_path).unlink()
Path(python_out.name).unlink()
Path(rust_out.name).unlink()

print("\n" + "=" * 50)
if py_entry.get('is_informal') == rust_entry.get('is_informal'):
    print("✓ PASS: Both parsers agree on is_informal")
else:
    print("✗ FAIL: Parsers disagree on is_informal")
    print(f"  Python: {py_entry.get('is_informal')}")
    print(f"  Rust:   {rust_entry.get('is_informal')}")
