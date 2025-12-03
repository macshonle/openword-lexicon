# Changelog - Wordlist Spec Editor

## [1.2.0] - 2025-11-17

### Changed
- **Web-only interface**: Removed CLI/TUI builder in favor of web-based interface
  - Deleted `cli-builder.js` and `cli-builder-clack.js`
  - Deleted `package.json` (no Node.js dependencies needed)
  - Web interface allows users to see all options at once
  - Users prefer visual form over navigating CLI menus
- **Simplified documentation**: Updated all docs to reference web interface only
- **Streamlined Makefile**: Removed CLI/install targets, web-only

### Notes
- JSON specifications remain fully compatible
- YAML output support planned for future release
- Web interface works offline (no server required)

## [1.0.0] - 2025-11-13

### Initial Release
- Web-based builder interface
- JSON specification schema
- JavaScript decision engine (spec-builder.js)
- Python filter engine (owlex.py)
- Complete documentation
- Example specifications
- Makefile integration

---

## Upgrade Guide

### From v1.1.0 (CLI)

The CLI builder has been removed. Use the web interface instead:

```bash
make spec-editor-web
```

All existing JSON specifications remain compatible - no changes needed.

---

## Known Issues

### Frequency Sorting
The sorting logic is correct, but if you don't see expected results:
1. Ensure the distribution is built: `make build-core` or `make build-plus`
2. Use `--verbose` flag to see frequency tiers of first 5 entries
3. Check that your data has `frequency_tier` fields populated

### Label Filtering (Plus Only)
- Label filters require Plus distribution
- Coverage is low (~3-11% of entries have labels)
- Use `policy.family_friendly` instead of manual register labels for profanity filtering

---

## Migration from v1.0

No changes needed. All v1.0 specifications work with v1.1.
