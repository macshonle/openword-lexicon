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
import inspect_metadata
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

    # 6. Metadata exploration - core
    print("🏷️  Exploring metadata (core)...")
    try:
        report_path = inspect_metadata.generate_report('core')
        reports_generated.append(report_path)
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    print()

    # 7. Metadata exploration - plus
    print("🏷️  Exploring metadata (plus)...")
    try:
        report_path = inspect_metadata.generate_report('plus')
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
    print(f"✓ Generated {len(reports_generated)} reports")
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
    index += "### Raw Data\n"
    index += "- [Raw Data Inspection](raw_data_inspection.md) - Samples from downloaded datasets\n\n"
    index += "### Pipeline Analysis\n"
    index += "- [Pipeline Inspection (Core)](pipeline_inspection_core.md) - Core distribution pipeline stages\n"
    index += "- [Pipeline Inspection (Plus)](pipeline_inspection_plus.md) - Plus distribution pipeline stages\n\n"
    index += "### Trie Analysis\n"
    index += "- [Trie Inspection (Core)](trie_inspection_core.md) - Core trie structure and tests\n"
    index += "- [Trie Inspection (Plus)](trie_inspection_plus.md) - Plus trie structure and tests\n\n"
    index += "### Metadata Exploration\n"
    index += "- [Metadata Exploration (Core)](metadata_exploration_core.md) - Core metadata analysis\n"
    index += "- [Metadata Exploration (Plus)](metadata_exploration_plus.md) - Plus metadata analysis\n\n"
    index += "### Distribution Comparison\n"
    index += "- [Distribution Comparison](distribution_comparison.md) - Core vs Plus analysis\n\n"
    index += "---\n\n"
    index += "**Generation:** Run `make reports` or `uv run python tools/generate_reports.py`\n"

    output_path = Path('reports/README.md')
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(index)

    print(f"✓ Index written to {output_path}")


if __name__ == '__main__':
    generate_all_reports()
    generate_index()
