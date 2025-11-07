#!/usr/bin/env python3
"""
policy.py — Apply policy filters to create curated views.

Reads:
  - data/intermediate/{core,plus}/entries_merged.jsonl
  - docs/policy_overrides.yaml (optional)

Outputs:
  - data/filtered/{core,plus}/family_friendly.jsonl

Policy: family-friendly
  Excludes entries with these labels:
    - register: vulgar, offensive, derogatory

  Overrides can be specified in policy_overrides.yaml to allow/block specific words.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Set, Optional

import orjson


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# Exclusion criteria for family-friendly policy
FAMILY_FRIENDLY_EXCLUDE_REGISTER = {'vulgar', 'offensive', 'derogatory'}


def load_policy_overrides(overrides_file: Path) -> Dict[str, Set[str]]:
    """
    Load policy overrides from YAML file.

    Format:
      family_friendly:
        allow:
          - word1
          - word2
        block:
          - word3

    Returns: {'allow': {...}, 'block': {...}}
    """
    overrides = {'allow': set(), 'block': set()}

    if not overrides_file.exists():
        logger.info(f"No policy overrides file found at {overrides_file}")
        return overrides

    try:
        import yaml
        with open(overrides_file, 'r') as f:
            data = yaml.safe_load(f)

        if data and 'family_friendly' in data:
            ff = data['family_friendly']
            if 'allow' in ff:
                overrides['allow'] = set(ff['allow'])
            if 'block' in ff:
                overrides['block'] = set(ff['block'])

        logger.info(f"Loaded policy overrides: {len(overrides['allow'])} allowed, {len(overrides['block'])} blocked")
    except ImportError:
        logger.warning("PyYAML not installed, skipping overrides")
    except Exception as e:
        logger.warning(f"Error loading overrides: {e}")

    return overrides


def is_family_friendly(entry: dict, overrides: Dict[str, Set[str]]) -> bool:
    """
    Check if an entry passes the family-friendly policy.

    Returns: True if entry should be included, False to exclude
    """
    word = entry['word']

    # Check explicit overrides first
    if word in overrides['block']:
        return False
    if word in overrides['allow']:
        return True

    # Check register labels
    labels = entry.get('labels', {})
    register = set(labels.get('register', []))

    # Exclude if any problematic register labels
    if register & FAMILY_FRIENDLY_EXCLUDE_REGISTER:
        return False

    return True


def apply_policy(input_path: Path, output_path: Path,
                 policy_func, overrides: Dict[str, Set[str]]):
    """Apply policy filter to entries."""
    if not input_path.exists():
        logger.warning(f"Input file not found: {input_path}")
        return

    logger.info(f"Applying family-friendly policy to {input_path.name}")

    included = []
    excluded_count = 0

    with open(input_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if line_num % 10000 == 0:
                logger.info(f"  Processed {line_num:,} entries...")

            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)

                if policy_func(entry, overrides):
                    included.append(entry)
                else:
                    excluded_count += 1

            except json.JSONDecodeError as e:
                logger.warning(f"Line {line_num}: JSON decode error: {e}")
                continue

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'wb') as f:
        for entry in included:
            line = orjson.dumps(entry) + b'\n'
            f.write(line)

    logger.info(f"  ✓ Included: {len(included):,} entries")
    logger.info(f"  ✗ Excluded: {excluded_count:,} entries")
    logger.info(f"  → {output_path}")


def generate_smoke_test(filtered_path: Path, output_path: Path, limit: int = 5):
    """Generate a simple text file with N filtered words for smoke testing."""
    if not filtered_path.exists():
        logger.warning(f"Filtered file not found: {filtered_path}")
        return

    logger.info(f"Generating smoke test file: {output_path}")

    words = []
    with open(filtered_path, 'r', encoding='utf-8') as f:
        for line in f:
            if len(words) >= limit:
                break
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                words.append(entry['word'])
            except:
                continue

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        for word in words:
            f.write(f"{word}\n")

    logger.info(f"  ✓ Smoke test: {len(words)} words → {output_path}")


def main():
    """Main policy filtering pipeline."""
    data_root = Path(__file__).parent.parent.parent / "data"
    docs_root = Path(__file__).parent.parent.parent / "docs"

    intermediate_dir = data_root / "intermediate"
    filtered_dir = data_root / "filtered"

    overrides_file = docs_root / "policy_overrides.yaml"

    logger.info("=" * 60)
    logger.info("PHASE 10: Policy layer (family-friendly)")
    logger.info("=" * 60)

    # Load overrides
    overrides = load_policy_overrides(overrides_file)

    # Apply to core distribution
    core_input = intermediate_dir / "core" / "entries_merged.jsonl"
    core_output = filtered_dir / "core" / "family_friendly.jsonl"

    if core_input.exists():
        apply_policy(core_input, core_output, is_family_friendly, overrides)

        # Generate smoke test
        smoke_output = filtered_dir / "core" / "family_friendly_5.txt"
        generate_smoke_test(core_output, smoke_output, limit=5)

    # Apply to plus distribution
    plus_input = intermediate_dir / "plus" / "entries_merged.jsonl"
    plus_output = filtered_dir / "plus" / "family_friendly.jsonl"

    if plus_input.exists():
        apply_policy(plus_input, plus_output, is_family_friendly, overrides)

        # Generate smoke test
        smoke_output = filtered_dir / "plus" / "family_friendly_5.txt"
        generate_smoke_test(plus_output, smoke_output, limit=5)

    logger.info("")
    logger.info("✓ Policy filtering complete")


if __name__ == '__main__':
    main()
