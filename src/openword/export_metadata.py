#!/usr/bin/env python3
"""
export_metadata.py — Export modular metadata layers from enriched lexemes.

Creates separate, downloadable metadata files that can be loaded on-demand
by applications. Each module is a JSON file mapping words to specific metadata.

Usage:
  uv run python src/openword/export_metadata.py \\
      --input LEXEMES.jsonl --modules frequency,concreteness [--gzip]

Available modules:
  - frequency: Frequency tier codes (A-Z)
  - concreteness: Brysbaert concreteness ratings (1.0-5.0)
  - syllables: Syllable counts
  - sources: Source attributions (wikt, eowl, wordnet)

Outputs:
  - data/build/{lang}-{module}.json (or .json.gz with --gzip)
"""

import gzip
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

from openword.progress_display import ProgressDisplay

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def extract_frequency(entry: Dict[str, Any]) -> Optional[str]:
    """Extract frequency tier code (A-Z)."""
    return entry.get('frequency_tier')


def extract_concreteness(entry: Dict[str, Any]) -> Optional[float]:
    """Extract concreteness rating (1.0-5.0)."""
    return entry.get('concreteness')


def extract_syllables(entry: Dict[str, Any]) -> Optional[int]:
    """Extract syllable count."""
    return entry.get('nsyll')


def extract_sources(entry: Dict[str, Any]) -> Optional[List[str]]:
    """Extract source attributions."""
    sources = entry.get('sources')
    return sources if sources else None


# Module definitions: name -> (extractor function, description)
MODULES = {
    'frequency': (extract_frequency, 'Frequency tier codes (A-Z)'),
    'concreteness': (extract_concreteness, 'Brysbaert concreteness ratings'),
    'syllables': (extract_syllables, 'Syllable counts'),
    'sources': (extract_sources, 'Source attributions'),
}


def export_module(
    input_path: Path,
    output_path: Path,
    extractor: Callable[[Dict[str, Any]], Any],
    module_name: str,
    use_gzip: bool = False
) -> int:
    """
    Export a single metadata module.

    Args:
        input_path: Path to enriched lexemes JSONL
        output_path: Output path for module JSON
        extractor: Function to extract module value from entry
        module_name: Name of module for logging
        use_gzip: Whether to gzip compress the output

    Returns:
        Number of entries with non-null values
    """
    logger.info(f"Exporting module: {module_name}")

    data = {}
    null_count = 0

    with ProgressDisplay(f"Processing {module_name}", update_interval=10000) as progress:
        with open(input_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    word = entry['id']
                    value = extractor(entry)

                    if value is not None:
                        data[word] = value
                    else:
                        null_count += 1

                    progress.update(Lines=line_num, Exported=len(data), Skipped=null_count)
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Line {line_num}: {e}")
                    continue

    # Write compact JSON (optionally gzipped)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_bytes = json.dumps(data, separators=(',', ':'), ensure_ascii=False).encode('utf-8')

    if use_gzip:
        output_path = output_path.with_suffix('.json.gz')
        with gzip.open(output_path, 'wb', compresslevel=9) as f:
            f.write(json_bytes)
    else:
        with open(output_path, 'wb') as f:
            f.write(json_bytes)

    size_kb = output_path.stat().st_size / 1024
    logger.info(f"  -> {output_path.name}: {len(data):,} entries ({size_kb:.1f} KB)")

    return len(data)


def main():
    """Main export pipeline."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Export modular metadata layers from enriched lexemes'
    )
    parser.add_argument('--input', type=Path, required=True,
                        help='Input enriched lexemes JSONL file')
    parser.add_argument('--language', default='en',
                        help='Language code for output filenames (default: en)')
    parser.add_argument('--modules', default='all',
                        help='Comma-separated list of modules to export (default: all)')
    parser.add_argument('--gzip', action='store_true',
                        help='Compress output with gzip (creates .json.gz files)')
    parser.add_argument('--list-modules', action='store_true',
                        help='List available modules and exit')
    args = parser.parse_args()

    # List modules if requested
    if args.list_modules:
        print("Available metadata modules:")
        for name, (_, desc) in MODULES.items():
            print(f"  {name}: {desc}")
        return 0

    # Determine which modules to export
    if args.modules == 'all':
        modules_to_export = list(MODULES.keys())
    else:
        modules_to_export = [m.strip() for m in args.modules.split(',')]
        for m in modules_to_export:
            if m not in MODULES:
                logger.error(f"Unknown module: {m}")
                logger.error(f"Available: {', '.join(MODULES.keys())}")
                return 1

    # Verify input exists
    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        return 1

    # Determine output directory
    data_root = Path(__file__).parent.parent.parent / "data"
    build_dir = data_root / "build"

    logger.info("Metadata export")
    logger.info(f"  Input: {args.input}")
    logger.info(f"  Modules: {', '.join(modules_to_export)}")
    logger.info(f"  Compression: {'gzip' if args.gzip else 'none'}")
    logger.info("")

    # Export each module
    results = {}
    output_paths = {}
    for module_name in modules_to_export:
        extractor, _ = MODULES[module_name]
        output_path = build_dir / f"{args.language}-{module_name}.json"
        count = export_module(args.input, output_path, extractor, module_name, args.gzip)
        results[module_name] = count
        # Track actual output path (may have .gz suffix)
        if args.gzip:
            output_paths[module_name] = output_path.with_suffix('.json.gz')
        else:
            output_paths[module_name] = output_path

    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("EXPORT SUMMARY")
    logger.info("=" * 60)
    for module_name, count in results.items():
        output_path = output_paths[module_name]
        size_kb = output_path.stat().st_size / 1024
        logger.info(f"  {module_name}: {count:,} entries ({size_kb:.1f} KB)")
    logger.info("=" * 60)

    return 0


if __name__ == '__main__':
    sys.exit(main())
