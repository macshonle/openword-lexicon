# Planned: CLI Implementation (`owlex` command)

**Status:** Planned for future release
**Priority:** Medium

## Overview

The `owlex` CLI will provide command-line access to the Openword Lexicon for searching, filtering, and exporting word lists.

## Planned Usage

```bash
# Search for words matching pattern
owlex search --pattern '^cas.*' --len 6-8

# Filter by attributes
owlex search --pos noun --tier top10k --family-friendly

# Get word info
owlex info castle

# Export filtered list
owlex export --pos noun --tier top1k --format txt > nouns_top1k.txt
```

## Implementation Notes

- Entry point: `src/openword/cli/__init__.py`
- Use Click for argument parsing
- Support JSON, CSV, and plain text output formats
- Enable flexible filtering by all metadata fields

## Dependencies

- Additional CLI dependencies may be needed (e.g., tabulate for table formatting)
- Consider integrating with existing filter_words.py functionality

## See Also

- [Current Python API](../USAGE.md#python-api) - Available now
- Python API provides full functionality; CLI is a convenience wrapper
