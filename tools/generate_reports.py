#!/usr/bin/env python3
"""
generate_reports.py - Generate all inspection reports

Master script that runs all inspection tools and generates a complete
set of reports for the project.
"""
import sys
from pathlib import Path

# Add tools directory to path
sys.path.insert(0, str(Path(__file__).parent))

import inspect_raw
import inspect_pipeline
import inspect_trie
import analyze_metadata
import compare_distributions


def generate_all_reports():
    """Generate all inspection reports."""
    print("=" * 60)
    print("Generating Openword Lexicon Inspection Reports")
    print("=" * 60)
    print()

    reports_generated = []

    # 1. Raw data inspection
    print("📊 Inspecting raw datasets...")
    try:
        report_path = inspect_raw.generate_report()
        reports_generated.append(report_path)
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    print()

    # 2. Pipeline inspection - core
    print("🔄 Inspecting pipeline (core)...")
    try:
        report_path = inspect_pipeline.generate_report('core')
        reports_generated.append(report_path)
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    print()

    # 3. Pipeline inspection - plus
    print("🔄 Inspecting pipeline (plus)...")
    try:
        report_path = inspect_pipeline.generate_report('plus')
        reports_generated.append(report_path)
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    print()

    # 4. Trie inspection - core
    print("🌲 Inspecting trie (core)...")
    try:
        report_path = inspect_trie.generate_report('core')
        reports_generated.append(report_path)
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    print()

    # 5. Trie inspection - plus
    print("🌲 Inspecting trie (plus)...")
    try:
        report_path = inspect_trie.generate_report('plus')
        reports_generated.append(report_path)
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    print()

    # 6. Comprehensive metadata analysis - core
    print("🏷️  Analyzing metadata (core)...")
    try:
        report_path = analyze_metadata.generate_report('core')
        reports_generated.append(report_path)
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    print()

    # 7. Comprehensive metadata analysis - plus
    print("🏷️  Analyzing metadata (plus)...")
    try:
        report_path = analyze_metadata.generate_report('plus')
        reports_generated.append(report_path)
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    print()

    # 8. Distribution comparison
    print("⚖️  Comparing distributions...")
    try:
        report_path = compare_distributions.generate_report()
        reports_generated.append(report_path)
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    print()

    # Summary
    print("=" * 60)
    print(f"Generated {len(reports_generated)} reports")
    print("=" * 60)
    print()
    print("Reports available in reports/:")
    for report in reports_generated:
        print(f"  - {report}")
    print()


def generate_index():
    """Generate an index.md file linking to all reports."""
    index = "# Openword Lexicon - Inspection Reports\n\n"
    index += "This directory contains automated inspection reports for the Openword Lexicon project.\n\n"
    index += "## Available Reports\n\n"
    index += "### Raw Data Analysis\n"
    index += "- [Raw Data Inspection](raw_data_inspection.md) - Samples from downloaded datasets\n\n"
    index += "### Pipeline Analysis\n"
    index += "- [Pipeline Inspection (Core)](pipeline_inspection_core.md) - Core distribution pipeline stages\n"
    index += "- [Pipeline Inspection (Plus)](pipeline_inspection_plus.md) - Plus distribution pipeline stages\n\n"
    index += "### Trie Analysis\n"
    index += "- [Trie Inspection (Core)](trie_inspection_core.md) - Core trie structure and tests\n"
    index += "- [Trie Inspection (Plus)](trie_inspection_plus.md) - Plus trie structure and tests\n\n"
    index += "### Comprehensive Metadata Analysis\n"
    index += "- [Metadata Analysis (Core)](metadata_analysis_core.md) - Comprehensive metadata, labels, and filtering analysis\n"
    index += "- [Metadata Analysis (Plus)](metadata_analysis_plus.md) - Comprehensive metadata, labels, and filtering analysis\n\n"
    index += "**Note:** These consolidated reports include:\n"
    index += "- Frequency tier distribution\n"
    index += "- Source distribution (ENABLE, EOWL, Wiktionary)\n"
    index += "- Label coverage (register, domain, region, temporal)\n"
    index += "- Game-specific filtering analysis (concreteness, POS tags)\n"
    index += "- Sense-based format recommendations\n"
    index += "- Filtering recommendations and data quality insights\n\n"
    index += "### Distribution Comparison\n"
    index += "- [Distribution Comparison](distribution_comparison.md) - Core vs Plus analysis\n\n"
    index += "---\n\n"
    index += "## Recent Improvements\n\n"
    index += "**Report Consolidation (2025):**\n"
    index += "- Merged metadata exploration, game analysis, and label statistics into comprehensive metadata reports\n"
    index += "- Fixed label data loss pipeline issue - labels now preserved from Wiktionary extraction\n"
    index += "- Added syllable extraction to Wiktionary scanner parser (handles complex hyphenation formats)\n"
    index += "- Removed obsolete exploratory reports (frequency analysis, WordNet concreteness)\n"
    index += "- Added sense-based intermediate format analysis and recommendations\n\n"
    index += "---\n\n"
    index += "**Generation:** Run `make reports` or `uv run python tools/generate_reports.py`\n"

    output_path = Path('reports/README.md')
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(index)

    print(f"Index written to {output_path}")


if __name__ == '__main__':
    generate_all_reports()
    generate_index()
