# Wikitext Samples

This directory contains raw wikitext XML extracted from the Wiktionary dump
for specific "hotspot" words used in testing and validation.

## Purpose

These samples allow us to:
- Inspect the actual raw wikitext for words that show parsing differences
- Debug edge cases by examining the source data
- Verify that parser behavior matches the actual wikitext structure
- Track changes in wikitext format over time (when samples are regenerated)

## Hotspot Words

The list of hotspot words is maintained in `tests/hotspot-words.txt`.
These words are selected because they:
- Appear in tests or documentation examples
- Show edge cases or parsing differences
- Represent common patterns worth validating

## Generating Samples

To extract wikitext for all hotspot words:

```bash
uv run python tools/extract_wikitext.py \
    data/raw/en/enwiktionary-latest-pages-articles.xml.bz2 \
    tests/wikitext-samples \
    --words-file tests/hotspot-words.txt
```

To extract specific words:

```bash
uv run python tools/extract_wikitext.py \
    data/raw/en/enwiktionary-latest-pages-articles.xml.bz2 \
    tests/wikitext-samples \
    acronym dialect four
```

## File Format

Each extracted sample is saved as `{word}.xml` and contains the complete
`<page>...</page>` XML block from the Wiktionary dump, including:
- Page metadata (title, namespace, revision info)
- Raw wikitext markup in the `<text>` tag
- All language sections, templates, and categories

## Usage in Investigation

When investigating parsing differences:

1. Look at the raw XML: `cat tests/wikitext-samples/acronym.xml`
2. Check what templates are present: `grep -o '{{[^}]*}}' tests/wikitext-samples/acronym.xml`
3. Find specific patterns: `grep -i 'abbreviation' tests/wikitext-samples/acronym.xml`
4. Compare against parser output to understand extraction behavior

## Source Control

These samples are committed to source control to:
- Enable investigation without requiring the full Wiktionary dump
- Document historical parsing edge cases
- Facilitate debugging across different machines
- Track wikitext format evolution
