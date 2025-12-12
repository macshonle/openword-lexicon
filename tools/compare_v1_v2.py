#!/usr/bin/env python3
"""
Compare v1 and v2 Wiktionary scanner outputs to measure parity.

V1 format uses flat tag arrays:
  - register_tags: ["slang", "informal"]
  - temporal_tags: ["archaic", "obsolete"]
  - region_tags: ["UK", "US"]
  - domain_tags: ["medicine", "computing"]

V2 format uses unified codes set:
  - codes: ["RSLG", "RINF", "TARC", "TOBS", "ENGB", "ENUS", "DMEDI", "DCOMP"]

This tool maps v1 fields to v2 codes and compares entries.

Usage:
    python tools/compare_v1_v2.py V1_OUTPUT.jsonl V2_OUTPUT.jsonl [--sample N]
"""

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Optional, Any


# V1 label → V2 code mappings
# These must match the schema/bindings definitions

REGISTER_MAP = {
    "informal": "RINF",
    "colloquial": "RINF",
    "slang": "RSLG",
    "vulgar": "RVLG",
    "offensive": "ROFF",
    "derogatory": "RDEG",
    "formal": "RFRM",
    "euphemistic": "REUP",
    "humorous": "RHUM",
    "literary": "RLIT",
    "childish": "RCHD",
    "nonstandard": "RNST",
    "AAVE": "RAAV",
}

TEMPORAL_MAP = {
    "archaic": "TARC",
    "obsolete": "TOBS",
    "dated": "TDAT",
    "historical": "THIS",
    "rare": "TRAR",
}

REGION_MAP = {
    "UK": "ENGB",
    "British": "ENGB",
    "US": "ENUS",
    "American": "ENUS",
    "Canada": "ENCA",
    "Canadian": "ENCA",
    "Australia": "ENAU",
    "Australian": "ENAU",
    "New Zealand": "ENNZ",
    "Ireland": "ENIE",
    "Irish": "ENIE",
    "South Africa": "ENZA",
    "Scotland": "ENSC",
    "Scottish": "ENSC",
    "India": "ENIN",
    "Indian": "ENIN",
}

# Domain mappings (abbreviated - extend as needed)
DOMAIN_MAP = {
    "medicine": "DMEDI",
    "medical": "DMEDI",
    "computing": "DCOMP",
    "law": "DLAWW",
    "legal": "DLAWW",
    "military": "DMILL",
    "nautical": "DNAUT",
    "aviation": "DAVIA",
    "mathematics": "DMATH",
    "math": "DMATH",
    "physics": "DPHYS",
    "chemistry": "DCHEM",
    "biology": "DBIOL",
    "zoology": "DZOOL",
    "botany": "DBOTN",
    "anatomy": "DANAT",
    "music": "DMUSC",
    "sports": "DSPRT",
    "finance": "DFINN",
    "linguistics": "DLING",
    "philosophy": "DPHIL",
    "religion": "DRELI",
}

MORPHOLOGY_TYPE_MAP = {
    "simple": "SIMP",
    "compound": "COMP",
    "prefixed": "PREF",
    "suffixed": "SUFF",
    "affixed": "AFFX",
    "circumfixed": "CIRC",
}


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Load JSONL file into list of entries."""
    entries = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def v1_to_codes(entry: Dict[str, Any]) -> Set[str]:
    """Convert v1 entry tags to v2 code set."""
    codes = set()

    # Register tags
    for tag in entry.get("register_tags", []):
        if tag in REGISTER_MAP:
            codes.add(REGISTER_MAP[tag])

    # Temporal tags
    for tag in entry.get("temporal_tags", []):
        if tag in TEMPORAL_MAP:
            codes.add(TEMPORAL_MAP[tag])

    # Region tags
    for tag in entry.get("region_tags", []):
        if tag in REGION_MAP:
            codes.add(REGION_MAP[tag])

    # Domain tags
    for tag in entry.get("domain_tags", []):
        if tag.lower() in DOMAIN_MAP:
            codes.add(DOMAIN_MAP[tag.lower()])

    # Boolean flags
    if entry.get("is_abbreviation"):
        codes.add("ABRV")
    if entry.get("is_inflected"):
        codes.add("INFL")

    # Morphology type
    morph = entry.get("morphology")
    if morph and "type" in morph:
        morph_type = morph["type"]
        if morph_type in MORPHOLOGY_TYPE_MAP:
            codes.add(MORPHOLOGY_TYPE_MAP[morph_type])

    return codes


def group_by_word(entries: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group entries by word ID."""
    groups = defaultdict(list)
    for entry in entries:
        groups[entry["id"]].append(entry)
    return dict(groups)


def compare_entry_sets(
    v1_entries: List[Dict[str, Any]],
    v2_entries: List[Dict[str, Any]],
    word: str
) -> Dict[str, Any]:
    """Compare v1 and v2 entries for a single word."""
    result = {
        "word": word,
        "v1_count": len(v1_entries),
        "v2_count": len(v2_entries),
        "differences": [],
    }

    # Collect unique (pos, codes) pairs from each
    v1_signatures = set()
    v2_signatures = set()

    for e in v1_entries:
        pos = e.get("pos", "UNK")
        codes = frozenset(v1_to_codes(e))
        v1_signatures.add((pos, codes))

    for e in v2_entries:
        pos = e.get("pos", "UNK")
        codes = frozenset(e.get("codes", []))
        v2_signatures.add((pos, codes))

    # Find differences
    v1_only = v1_signatures - v2_signatures
    v2_only = v2_signatures - v1_signatures

    if v1_only:
        result["differences"].append({
            "type": "v1_only",
            "signatures": [{"pos": pos, "codes": sorted(codes)} for pos, codes in v1_only]
        })

    if v2_only:
        result["differences"].append({
            "type": "v2_only",
            "signatures": [{"pos": pos, "codes": sorted(codes)} for pos, codes in v2_only]
        })

    # Compare common fields
    v1_pos_set = {e.get("pos") for e in v1_entries}
    v2_pos_set = {e.get("pos") for e in v2_entries}

    if v1_pos_set != v2_pos_set:
        result["differences"].append({
            "type": "pos_mismatch",
            "v1_pos": sorted(v1_pos_set),
            "v2_pos": sorted(v2_pos_set),
        })

    # Check syllable counts
    v1_nsyll = {e.get("nsyll") for e in v1_entries if e.get("nsyll")}
    v2_nsyll = {e.get("nsyll") for e in v2_entries if e.get("nsyll")}

    if v1_nsyll != v2_nsyll:
        result["differences"].append({
            "type": "nsyll_mismatch",
            "v1_nsyll": sorted(v1_nsyll) if v1_nsyll else None,
            "v2_nsyll": sorted(v2_nsyll) if v2_nsyll else None,
        })

    return result


def print_report(
    v1_by_word: Dict[str, List[Dict[str, Any]]],
    v2_by_word: Dict[str, List[Dict[str, Any]]],
    sample_size: Optional[int] = None
):
    """Print comparison report."""
    print("=" * 80)
    print("V1 vs V2 WIKTIONARY SCANNER COMPARISON")
    print("=" * 80)
    print()

    v1_words = set(v1_by_word.keys())
    v2_words = set(v2_by_word.keys())
    common_words = v1_words & v2_words
    v1_only_words = v1_words - v2_words
    v2_only_words = v2_words - v1_words

    print(f"V1 unique words: {len(v1_words):,}")
    print(f"V2 unique words: {len(v2_words):,}")
    print(f"Common words: {len(common_words):,}")
    print(f"V1-only words: {len(v1_only_words):,}")
    print(f"V2-only words: {len(v2_only_words):,}")
    print()

    # Compare common words
    words_to_compare = sorted(common_words)
    if sample_size and len(words_to_compare) > sample_size:
        import random
        words_to_compare = random.sample(words_to_compare, sample_size)
        print(f"Sampling {sample_size} words for detailed comparison")
        print()

    words_with_differences = []
    pos_mismatches = 0
    code_mismatches = 0
    nsyll_mismatches = 0

    for word in words_to_compare:
        result = compare_entry_sets(v1_by_word[word], v2_by_word[word], word)

        if result["differences"]:
            words_with_differences.append(result)
            for diff in result["differences"]:
                if diff["type"] == "pos_mismatch":
                    pos_mismatches += 1
                elif diff["type"] in ("v1_only", "v2_only"):
                    code_mismatches += 1
                elif diff["type"] == "nsyll_mismatch":
                    nsyll_mismatches += 1

    print("-" * 80)
    print("SUMMARY")
    print("-" * 80)
    print(f"Words compared: {len(words_to_compare)}")
    print(f"Words with differences: {len(words_with_differences)}")
    print(f"  - POS mismatches: {pos_mismatches}")
    print(f"  - Code mismatches: {code_mismatches}")
    print(f"  - Syllable mismatches: {nsyll_mismatches}")
    print()

    if len(words_with_differences) > 0:
        parity_pct = (1 - len(words_with_differences) / len(words_to_compare)) * 100
        print(f"Parity: {parity_pct:.1f}%")
        print()

    # Show sample differences
    if words_with_differences:
        print("-" * 80)
        print("SAMPLE DIFFERENCES (first 10)")
        print("-" * 80)

        for result in words_with_differences[:10]:
            print(f"\n{result['word']} (v1: {result['v1_count']} entries, v2: {result['v2_count']} entries)")
            for diff in result["differences"]:
                if diff["type"] == "v1_only":
                    print(f"  V1 only: {diff['signatures']}")
                elif diff["type"] == "v2_only":
                    print(f"  V2 only: {diff['signatures']}")
                elif diff["type"] == "pos_mismatch":
                    print(f"  POS: v1={diff['v1_pos']} vs v2={diff['v2_pos']}")
                elif diff["type"] == "nsyll_mismatch":
                    print(f"  Syllables: v1={diff['v1_nsyll']} vs v2={diff['v2_nsyll']}")

    # Show words only in v1 or v2
    if v1_only_words:
        print()
        print("-" * 80)
        print(f"WORDS ONLY IN V1 ({len(v1_only_words)} total, showing first 20)")
        print("-" * 80)
        for word in sorted(v1_only_words)[:20]:
            print(f"  {word}")

    if v2_only_words:
        print()
        print("-" * 80)
        print(f"WORDS ONLY IN V2 ({len(v2_only_words)} total, showing first 20)")
        print("-" * 80)
        for word in sorted(v2_only_words)[:20]:
            print(f"  {word}")

    print()
    print("=" * 80)


def main():
    if len(sys.argv) < 3:
        print("Usage: python compare_v1_v2.py V1_OUTPUT.jsonl V2_OUTPUT.jsonl [--sample N]")
        print()
        print("Compare v1 and v2 scanner outputs to measure parity.")
        sys.exit(1)

    v1_path = Path(sys.argv[1])
    v2_path = Path(sys.argv[2])

    sample_size = None
    if "--sample" in sys.argv:
        idx = sys.argv.index("--sample")
        if idx + 1 < len(sys.argv):
            sample_size = int(sys.argv[idx + 1])

    if not v1_path.exists():
        print(f"Error: V1 output not found: {v1_path}")
        sys.exit(1)

    if not v2_path.exists():
        print(f"Error: V2 output not found: {v2_path}")
        sys.exit(1)

    print(f"Loading V1: {v1_path}")
    v1_entries = load_jsonl(v1_path)

    print(f"Loading V2: {v2_path}")
    v2_entries = load_jsonl(v2_path)

    print(f"V1 entries: {len(v1_entries):,}")
    print(f"V2 entries: {len(v2_entries):,}")
    print()

    v1_by_word = group_by_word(v1_entries)
    v2_by_word = group_by_word(v2_entries)

    print_report(v1_by_word, v2_by_word, sample_size)


if __name__ == "__main__":
    main()
