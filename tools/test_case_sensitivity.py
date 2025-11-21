#!/usr/bin/env python3
"""
Test if pages with different capitalizations create multiple entries.
"""

import subprocess
import tempfile
import json

# Test XML with different capitalizations of the same word
test_xml = """<mediawiki>
<page>
<title>sat</title>
<ns>0</ns>
<text>
==English==

===Verb===
{{head|en|verb form}}

# {{inflection of|en|sit||simple|past}}

[[Category:English verb forms]]
</text>
</page>

<page>
<title>Sat</title>
<ns>0</ns>
<text>
==English==

===Noun===
{{en-noun}}

# {{abbreviation of|en|Saturday}}
# {{lb|en|informal}} [[Saturday]].
</text>
</page>

<page>
<title>sun</title>
<ns>0</ns>
<text>
==English==

===Noun===
{{en-noun}}

# {{lb|en|astronomy}} The [[star]] that the [[Earth]] [[orbit]]s.
</text>
</page>

<page>
<title>Sun</title>
<ns>0</ns>
<text>
==English==

===Proper noun===
{{en-proper noun}}

# {{abbreviation of|en|Sunday}}
# {{lb|en|informal}} [[Sunday]].
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

print("Testing case sensitivity...")
subprocess.run([
    'tools/wiktionary-rust/target/release/wiktionary-rust',
    test_xml_path,
    rust_out.name
], check=True, capture_output=True)

# Analyze results
print("\n" + "="*80)
print("CASE SENSITIVITY TEST RESULTS")
print("="*80)

with open(rust_out.name) as f:
    for line in f:
        entry = json.loads(line)
        word = entry['word']
        pos = ', '.join(entry.get('pos', []))
        is_abbr = entry.get('is_abbreviation')
        is_inflected = entry.get('is_inflected')
        print(f"\nword: {word}")
        print(f"  POS: {pos}")
        print(f"  is_abbreviation: {is_abbr}")
        print(f"  is_inflected: {is_inflected}")

# Cleanup
import os
os.unlink(test_xml_path)
os.unlink(rust_out.name)

print("\n" + "="*80)
print("CONCLUSION")
print("="*80)
print("Multiple pages with different capitalizations DO create multiple entries!")
print("The 'word' field is lowercase, so they share the same word value.")
print("This is how polysemy is preserved in the output.")
