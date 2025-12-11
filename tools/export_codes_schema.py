#!/usr/bin/env python3
"""
Export codes schema to JSON for downstream UI tools.

Reads schema/core/ files and produces a codes.json file containing:
- All POS codes (3-letter)
- All flag codes (4-letter)
- All tag codes (4-letter, grouped by tag set)
- All phrase type codes (4-letter)
- All morphology type codes (4-letter)
- All domain type codes (5-letter)

Output format is designed for UI consumption with short labels and descriptions.

Usage:
    python tools/export_codes_schema.py [output_path]

    If output_path not specified, writes to schema/codes.json
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.wiktionary_scanner_v2.schema import load_core_schema


def export_codes_schema(core_path: Path, output_path: Path) -> dict:
    """
    Export codes schema to a JSON-serializable dictionary.

    Returns dict with structure:
    {
        "pos": {
            "NOU": {"name": "Noun", "short": "noun", "description": "..."},
            ...
        },
        "flags": {
            "ABRV": {"name": "Abbreviation", "short": "abbr", "description": "..."},
            ...
        },
        "tags": {
            "REGS": {
                "name": "Register",
                "description": "...",
                "tags": {
                    "RINF": {"name": "informal", "short": "informal", "description": "..."},
                    ...
                }
            },
            ...
        },
        "phrase_types": {
            "IDIM": {"name": "Idiom", "short": "idiom", "description": "..."},
            ...
        },
        "morphology_types": {
            "SUFF": {"name": "Suffixed", "short": "suffix", "description": "..."},
            ...
        }
    }
    """
    core = load_core_schema(core_path)

    result = {
        "pos": {},
        "flags": {},
        "tags": {},
        "phrase_types": {},
        "morphology_types": {},
        "domain_types": {},
    }

    # POS codes
    for pos in core.pos_classes:
        result["pos"][pos.code] = {
            "name": pos.name,
            "short": pos.short_description or pos.name.lower(),
            "description": pos.description,
        }

    # Flag codes
    for flag in core.flags:
        result["flags"][flag.code] = {
            "name": flag.name,
            "short": flag.name.lower().replace("_", " "),
            "description": flag.description,
        }

    # Tag codes (grouped by tag set)
    for tag_set in core.tag_sets:
        tag_set_entry = {
            "name": tag_set.name,
            "description": tag_set.description,
            "tags": {},
        }
        for tag in tag_set.tags:
            tag_set_entry["tags"][tag.code] = {
                "name": tag.name,
                "short": tag.name.lower(),
                "description": tag.description,
            }
        result["tags"][tag_set.code] = tag_set_entry

    # Phrase type codes
    for pt in core.phrase_types:
        result["phrase_types"][pt.code] = {
            "name": pt.name,
            "short": pt.name.lower(),
            "description": pt.description,
        }

    # Morphology type codes
    for mt in core.morphology_types:
        result["morphology_types"][mt.code] = {
            "name": mt.name,
            "short": mt.name.lower(),
            "description": mt.description,
        }

    # Domain type codes
    for dt in core.domain_types:
        result["domain_types"][dt.code] = {
            "name": dt.name,
            "short": dt.name.lower(),
            "description": dt.description,
        }

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Export codes schema to JSON for UI consumption"
    )
    parser.add_argument(
        "output",
        nargs="?",
        default="schema/codes.json",
        help="Output path for codes.json (default: schema/codes.json)",
    )
    parser.add_argument(
        "--core",
        default="schema/core",
        help="Path to schema/core directory (default: schema/core)",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation (default: 2, use 0 for compact)",
    )

    args = parser.parse_args()

    core_path = Path(args.core)
    output_path = Path(args.output)

    if not core_path.exists():
        print(f"Error: Core schema path not found: {core_path}", file=sys.stderr)
        sys.exit(1)

    # Export schema
    codes = export_codes_schema(core_path, output_path)

    # Write output
    indent = args.indent if args.indent > 0 else None
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(codes, f, indent=indent, ensure_ascii=False)

    # Summary
    pos_count = len(codes["pos"])
    flag_count = len(codes["flags"])
    tag_count = sum(len(ts["tags"]) for ts in codes["tags"].values())
    tag_set_count = len(codes["tags"])
    pt_count = len(codes["phrase_types"])
    mt_count = len(codes["morphology_types"])
    dt_count = len(codes["domain_types"])

    print(f"Exported codes schema to {output_path}")
    print(f"  POS codes:        {pos_count}")
    print(f"  Flag codes:       {flag_count}")
    print(f"  Tag sets:         {tag_set_count} ({tag_count} tags)")
    print(f"  Phrase types:     {pt_count}")
    print(f"  Morphology types: {mt_count}")
    print(f"  Domain types:     {dt_count}")
    print(f"  Total codes:      {pos_count + flag_count + tag_count + pt_count + mt_count + dt_count}")


if __name__ == "__main__":
    main()
