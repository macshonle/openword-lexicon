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
import analyze_metadata


def generate_all_reports(language: str = 'en'):
    """Generate all inspection reports for a language."""
    print("=" * 60)
    print(f"Generating Openword Lexicon Inspection Reports ({language.upper()})")
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

    # 2. Comprehensive metadata analysis
    print(f"🏷️  Analyzing metadata ({language})...")
    try:
        report_path = analyze_metadata.generate_report(language)
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


def generate_index(language: str = 'en'):
    """Generate an index.md file linking to all reports."""
    index = "# Openword Lexicon - Inspection Reports\n\n"
    index += "This directory contains automated inspection reports for the Openword Lexicon project.\n\n"
    index += "## Available Reports\n\n"
    index += "### Raw Data Analysis\n"
    index += "- [Raw Data Inspection](raw_data_inspection.md) - Samples from downloaded datasets\n\n"
    index += "### Comprehensive Metadata Analysis\n"
    index += f"- [Metadata Analysis ({language.upper()})](metadata_analysis_{language}.md) - Comprehensive metadata, labels, and filtering analysis\n\n"
    index += "**Note:** This consolidated report includes:\n"
    index += "- Frequency tier distribution\n"
    index += "- Source distribution (ENABLE, EOWL, Wiktionary)\n"
    index += "- Label coverage (register, domain, region, temporal)\n"
    index += "- Game-specific filtering analysis (concreteness, POS tags, syllables)\n"
    index += "- Sense-based format recommendations\n"
    index += "- Filtering recommendations and data quality insights\n"
    index += "- Representative samples from all data sources\n\n"
    index += "---\n\n"
    index += "## Recent Improvements\n\n"
    index += "**Unified Build (2025):**\n"
    index += "- Unified build integrating all sources (ENABLE, EOWL, Wiktionary, WordNet)\n"
    index += "- Per-word license tracking via `license_sources` field\n"
    index += "- Language-based organization (English-only currently)\n"
    index += "- Safe defaults philosophy for missing metadata\n"
    index += "- Runtime filtering support (child-safe, region-specific, profanity, etc.)\n"
    index += "- Fixed syllable data loss pipeline issue\n"
    index += "- Added missing POS tag detection\n"
    index += "- Enhanced analysis with source-specific sampling\n\n"
    index += "---\n\n"
    index += f"**Generation:** Run `make report-{language}` or `uv run python tools/generate_reports.py`\n"

    output_path = Path('reports/README.md')
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(index)

    print(f"Index written to {output_path}")


if __name__ == '__main__':
    # Get language from command line or default to 'en'
    language = sys.argv[1] if len(sys.argv) > 1 else 'en'

    generate_all_reports(language)
    generate_index(language)
