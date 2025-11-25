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

import analyze_metadata


def generate_all_reports(language: str = 'en'):
    """Generate all inspection reports for a language."""
    print("=" * 60)
    print(f"Generating Openword Lexicon Inspection Reports ({language.upper()})")
    print("=" * 60)
    print()

    reports_generated = []

    # 1. Comprehensive metadata analysis
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
    index += "## Pipeline Architecture\n\n"
    index += "**Two-File Format (2025):**\n"
    index += "- Normalized format with separate lexeme and senses files\n"
    index += "- Word-level properties in `en-lexeme-enriched.jsonl`\n"
    index += "- Sense-level properties in `en-aggregate-senses.jsonl`\n"
    index += "- Language-based organization (English currently)\n"
    index += "- Safe defaults philosophy for missing metadata\n"
    index += "- Runtime filtering support (child-safe, region-specific, profanity, etc.)\n\n"
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
