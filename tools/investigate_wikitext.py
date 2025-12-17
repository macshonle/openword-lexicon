#!/usr/bin/env python3
"""
Systematic investigation tool for wikitext samples.

This tool examines raw wikitext to understand patterns and identify
where parsers might diverge from expected behavior.

Usage:
    python tools/investigate_wikitext.py reference/wiktionary/samples/WORD.xml
    python tools/investigate_wikitext.py reference/wiktionary/samples/*.xml > investigation_report.txt
"""

import re
import sys
from pathlib import Path
from typing import Dict, List


def extract_text(xml_path: Path) -> str:
    """Extract the <text> content from XML."""
    with open(xml_path, encoding="utf-8") as f:
        content = f.read()

    match = re.search(r"<text[^>]*>(.+?)</text>", content, re.DOTALL)
    if match:
        return match.group(1)
    return ""


def extract_english_section(text: str) -> str:
    """Extract just the ==English== section."""
    match = re.search(r"==\s*English\s*==", text, re.IGNORECASE)
    if not match:
        return ""

    start = match.end()

    # Find next language section
    next_match = re.search(r"^==\s*([^=]+?)\s*==$", text[start:], re.MULTILINE)
    if next_match:
        return text[start:start + next_match.start()]
    return text[start:]


def analyze_labels(text: str) -> Dict[str, List[str]]:
    """Analyze label templates in text."""
    labels = {
        "context_labels": [],
        "categories": [],
    }

    # Find {{lb|en|...}} templates
    for match in re.finditer(r"\{\{(?:lb|label|context)\|en\|([^}]+)\}\}", text, re.IGNORECASE):
        content = match.group(1)
        labels["context_labels"].extend([label.strip() for label in content.split("|")])

    # Find categories
    for match in re.finditer(r"\[\[Category:English\s+([^\]]+)\]\]", text, re.IGNORECASE):
        labels["categories"].append(match.group(1))

    return labels


def analyze_templates(text: str) -> Dict[str, List[str]]:
    """Find all templates and their types."""
    templates = {
        "abbreviation": [],
        "inflection": [],
        "morphology": [],
        "other": [],
    }

    # Abbreviation templates
    for match in re.finditer(r"\{\{(abbreviation of|abbrev of|abbr of|initialism of)\|en\|[^}]+\}\}", text, re.IGNORECASE):
        templates["abbreviation"].append(match.group(0))

    # Inflection templates
    for match in re.finditer(r"\{\{(plural of|past tense of|past participle of|present participle of|inflection of)\|en\|[^}]+\}\}", text, re.IGNORECASE):
        templates["inflection"].append(match.group(0))

    # Morphology templates
    for match in re.finditer(r"\{\{(suffix|prefix|affix|compound|surf|confix)\|en\|[^}]+\}\}", text, re.IGNORECASE):
        templates["morphology"].append(match.group(0))

    # Other notable templates
    for pattern in [r"\{\{en-[a-z]+", r"\{\{head\|en"]:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            # Get full template
            start = match.start()
            depth = 0
            end = start
            for i, char in enumerate(text[start:], start):
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            templates["other"].append(text[start:end])

    return templates


def investigate_word(xml_path: Path) -> Dict:
    """Perform full investigation of a word's wikitext."""
    word = xml_path.stem

    print("=" * 80)
    print(f"INVESTIGATING: {word}")
    print("=" * 80)
    print()

    # Extract content
    full_text = extract_text(xml_path)
    english_text = extract_english_section(full_text)

    if not english_text:
        print("⚠️  NO ENGLISH SECTION FOUND")
        print()
        # Check if there are other languages
        other_langs = re.findall(r"^==\s*([^=]+?)\s*==$", full_text, re.MULTILINE)
        if other_langs:
            print(f"Other languages present: {', '.join(other_langs)}")
        print()
        return {"word": word, "has_english": False}

    print(f"English section length: {len(english_text)} characters")
    print()

    # Analyze labels
    labels = analyze_labels(english_text)

    print("CONTEXT LABELS (from {{lb|en|...}} templates):")
    if labels["context_labels"]:
        for label in sorted(set(labels["context_labels"])):
            print(f"  - {label}")
    else:
        print("  (none)")
    print()

    print("CATEGORIES:")
    if labels["categories"]:
        for cat in labels["categories"][:10]:  # Show first 10
            print(f"  - {cat}")
        if len(labels["categories"]) > 10:
            print(f"  ... and {len(labels['categories']) - 10} more")
    else:
        print("  (none)")
    print()

    # Analyze templates
    templates = analyze_templates(english_text)

    print("ABBREVIATION TEMPLATES:")
    if templates["abbreviation"]:
        for tmpl in templates["abbreviation"]:
            print(f"  - {tmpl}")
    else:
        print("  (none)")
    print()

    print("INFLECTION TEMPLATES:")
    if templates["inflection"]:
        for tmpl in templates["inflection"][:5]:  # Show first 5
            print(f"  - {tmpl}")
        if len(templates["inflection"]) > 5:
            print(f"  ... and {len(templates['inflection']) - 5} more")
    else:
        print("  (none)")
    print()

    print("MORPHOLOGY TEMPLATES:")
    if templates["morphology"]:
        for tmpl in templates["morphology"]:
            print(f"  - {tmpl}")
    else:
        print("  (none)")
    print()

    # Check etymology sections
    etym_matches = list(re.finditer(r"===+\s*Etymology\s*\d*\s*===+", english_text, re.IGNORECASE))
    print(f"ETYMOLOGY SECTIONS: {len(etym_matches)}")
    if etym_matches:
        for i, match in enumerate(etym_matches, 1):
            section_name = match.group(0).strip()
            print(f"  {i}. {section_name}")
    print()

    # Character set analysis
    print("CHARACTER SET ANALYSIS:")
    has_latin = any("a" <= c.lower() <= "z" for c in word)
    has_non_ascii = any(ord(c) > 127 for c in word)
    has_extended_latin = any(0x00C0 <= ord(c) <= 0x024F for c in word if ord(c) > 127)
    print(f"  Has Latin letters: {has_latin}")
    print(f"  Has non-ASCII: {has_non_ascii}")
    if has_non_ascii:
        print(f"  Has extended Latin (À-ɏ): {has_extended_latin}")
        # Show actual characters
        non_ascii_chars = set(c for c in word if ord(c) > 127)
        print(f"  Non-ASCII characters: {', '.join(sorted(non_ascii_chars))}")
    print()

    return {
        "word": word,
        "has_english": True,
        "labels": labels,
        "templates": templates,
        "etym_count": len(etym_matches),
    }


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    xml_paths = [Path(arg) for arg in sys.argv[1:]]

    for xml_path in xml_paths:
        if not xml_path.exists():
            print(f"Error: File not found: {xml_path}")
            continue

        investigate_word(xml_path)
        print()


if __name__ == "__main__":
    main()
