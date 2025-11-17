# Diagnostic Data

This directory contains diagnostic samples extracted from source data for analysis.

## Wiktionary XML Slices (`wikt_slices/`)

Contains ~1KB samples of XML from the Wiktionary dump, strategically selected to represent different entry types and edge cases.

### Slicing Strategy

The slices are extracted by `tools/wiktionary_xml_slicer.py` using this strategy:

1. **Baseline samples (first 10 entries)**: Capture typical format
2. **Statistical samples (every 10,000th entry)**: Spread across the dump
3. **Characteristic samples**: Entries with specific features:
   - `pos_no_cat`: Has POS tags but no categories (edge case for filtering)
   - `cat_no_pos`: Has categories but no POS tags (another edge case)
   - `multiword`: Multi-word phrases and idioms
   - `syllable`: Entries with syllable/hyphenation data
   - `labels`: Entries with context labels (register, domain, etc.)
4. **Position-based samples**: Random samples from different file positions

### File Naming Convention

Files are named: `{OFFSET_HEX}_{LENGTH_DEC}_{REASON}_{TITLE}.xml`

- `OFFSET_HEX`: Byte offset in source file (hexadecimal)
- `LENGTH_DEC`: Slice length in bytes (decimal)
- `REASON`: Why this slice was extracted (e.g., `baseline`, `pos_no_cat`)
- `TITLE`: First 30 chars of entry title (sanitized)

### Usage

Extract new slices:
```bash
make extract-slices
```

This will:
1. Read from `data/raw/en/enwiktionary-latest-pages-articles.xml.bz2`
2. Extract ~50 slices totaling ~50KB
3. Write to `data/diagnostic/wikt_slices/`
4. Create `_metadata.json` with run statistics

### Purpose

These slices enable:
- **Deep format analysis** without loading the full 5GB+ dump
- **Regression testing** to catch parser changes that affect specific entry types
- **Edge case documentation** showing problematic entries
- **Debugging** of filtering logic and category detection
- **Version control** of representative samples for historical comparison

### Metadata File

`_metadata.json` contains:
- Number of slices written
- Total entries scanned
- Types of samples captured
- Source file path

This helps track what was captured in each slicing run.
