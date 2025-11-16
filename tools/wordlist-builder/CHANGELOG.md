# Changelog - Word List Builder

## [1.1.0] - 2025-11-13

### Added
- **Enhanced TUI version** using `@clack/prompts` for better UX
  - Arrow key navigation
  - Multi-select for filters
  - Beautiful color-coded interface
  - Progress indicators and spinners
  - Automatic fallback to basic CLI if not installed
- **Package.json** for optional @clack/prompts dependency
- **Verbose output** in owlex filter engine
  - Shows sorting method being used
  - Displays first 5 entries with frequency tiers when sorting by frequency
  - Warns when description doesn't match actual filters

### Fixed
- **Preset listing**: Now shows available presets BEFORE asking if user wants one
- **Label configuration**: Now loops through all label categories (register, temporal, domain, region)
  - Users can configure multiple label types in one session
  - Better prompts explaining each category
- **Policy filters**: Enhanced prompts explaining what each policy does
  - Makes profanity filtering more discoverable
  - Shows confirmation when filters are applied
- **Frequency sorting**: Added debugging output to verify correct sorting
  - Displays frequency tiers and scores in verbose mode
  - Helps diagnose data issues

### Improved
- **Better UX**: All filter categories now have clearer descriptions
- **Error messages**: More helpful warnings when description doesn't match filters
  - Warns if description mentions "US" but no region filter set
  - Warns if description mentions "profanity" but no family-friendly filter set
- **Documentation**: Updated to mention both CLI versions

## [1.0.0] - 2025-11-13

### Initial Release
- Basic CLI builder with readline
- Web-based builder interface
- JSON specification schema
- JavaScript decision engine (spec-builder.js)
- Python filter engine (owlex.py)
- Complete documentation
- Example specifications
- Makefile integration

---

## Upgrade Guide

### To Enhanced TUI Version

```bash
cd tools/wordlist-builder
npm install
cd ../..
make wordlist-builder-cli
```

The enhanced version will automatically be used if @clack/prompts is installed.

### Breaking Changes

None. All specifications remain compatible.

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
