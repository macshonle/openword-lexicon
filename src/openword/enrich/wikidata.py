#!/usr/bin/env python3
"""
Wikidata Q-code enrichment for senseid values.

Queries Wikidata SPARQL endpoint for short descriptions of Q identifiers
found in Wiktionary senseid fields. Results are cached in a checked-in
mapping file since Wikidata descriptions are very stable.

Usage:
    # Extract Q codes from enriched output
    uv run python -m openword.enrich.wikidata extract \
        data/intermediate/en-wikt-v2-enriched.jsonl \
        reference/wikidata/senseid-qids.txt

    # Fetch missing descriptions from Wikidata
    uv run python -m openword.enrich.wikidata fetch \
        reference/wikidata/senseid-qids.txt \
        reference/wikidata/wikidata-descriptions.json

    # Show statistics
    uv run python -m openword.enrich.wikidata stats \
        reference/wikidata/senseid-qids.txt \
        reference/wikidata/wikidata-descriptions.json
"""

import argparse
import json
import logging
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Wikidata SPARQL endpoint
WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"

# Batch size for SPARQL queries (Wikidata recommends keeping queries reasonable)
DEFAULT_BATCH_SIZE = 500

# Delay between requests to be nice to Wikidata servers
REQUEST_DELAY_SECONDS = 1.0

# User agent for requests (Wikidata requires a descriptive user agent)
USER_AGENT = "OpenWordLexicon/0.2 (https://github.com/openword-lexicon; contact@example.com)"


def extract_qids_from_jsonl(input_path: Path) -> Set[str]:
    """
    Extract unique Q identifiers from senseid fields in JSONL.

    Args:
        input_path: Path to enriched JSONL file

    Returns:
        Set of Q identifiers (e.g., {"Q12345", "Q67890"})
    """
    qid_pattern = re.compile(r'^Q\d+$')
    qids: Set[str] = set()

    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                senseid = entry.get('senseid')
                if senseid and qid_pattern.match(senseid):
                    qids.add(senseid)
            except json.JSONDecodeError:
                continue

    return qids


def load_qid_list(path: Path) -> Set[str]:
    """Load Q identifiers from a text file (one per line)."""
    qids: Set[str] = set()
    if not path.exists():
        return qids

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            qid = line.strip()
            if qid and qid.startswith('Q'):
                qids.add(qid)

    return qids


def save_qid_list(qids: Set[str], path: Path) -> None:
    """Save Q identifiers to a text file (sorted, one per line)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        for qid in sorted(qids, key=lambda x: int(x[1:])):
            f.write(f"{qid}\n")


@dataclass
class WikidataEntry:
    """A Wikidata item with label and description."""
    label: str
    description: str

    def to_dict(self) -> dict:
        return {"label": self.label, "description": self.description}

    @classmethod
    def from_dict(cls, d: dict) -> "WikidataEntry":
        return cls(label=d.get("label", ""), description=d.get("description", ""))


def load_wikidata_cache(path: Path) -> Dict[str, WikidataEntry]:
    """Load cached Q-code to WikidataEntry mapping."""
    if not path.exists():
        return {}

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return {qid: WikidataEntry.from_dict(entry) for qid, entry in data.items()}


def save_wikidata_cache(entries: Dict[str, WikidataEntry], path: Path) -> None:
    """Save Q-code to WikidataEntry mapping (sorted by Q number)."""
    path.parent.mkdir(parents=True, exist_ok=True)

    # Sort by numeric Q value for stable output
    sorted_items = sorted(entries.items(), key=lambda x: int(x[0][1:]))
    sorted_dict = {qid: entry.to_dict() for qid, entry in sorted_items}

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(sorted_dict, f, indent=2, ensure_ascii=False)
        f.write('\n')


# Legacy wrappers for backward compatibility
def load_descriptions(path: Path) -> Dict[str, str]:
    """Load cached Q-code to description mapping (legacy format)."""
    entries = load_wikidata_cache(path)
    return {qid: e.description for qid, e in entries.items()}


def save_descriptions(descriptions: Dict[str, str], path: Path) -> None:
    """Save Q-code to description mapping (legacy format)."""
    entries = {qid: WikidataEntry(label="", description=desc)
               for qid, desc in descriptions.items()}
    save_wikidata_cache(entries, path)


def fetch_wikidata_batch(qids: List[str], language: str = "en") -> Dict[str, WikidataEntry]:
    """
    Fetch labels and descriptions for a batch of Q identifiers from Wikidata.

    Args:
        qids: List of Q identifiers to query
        language: Language code for labels/descriptions (default: en)

    Returns:
        Dict mapping Q identifier to WikidataEntry
    """
    if not qids:
        return {}

    # Build VALUES clause for SPARQL
    values = " ".join(f"wd:{qid}" for qid in qids)

    # SPARQL query to get labels and descriptions
    query = f"""
    SELECT ?item ?itemLabel ?itemDescription WHERE {{
      VALUES ?item {{ {values} }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{language},en". }}
    }}
    """

    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": USER_AGENT,
    }

    try:
        # Use POST to avoid URL length limits with large VALUES clauses
        response = requests.post(
            WIKIDATA_SPARQL_URL,
            data={"query": query},
            headers=headers,
            timeout=60,
        )
        response.raise_for_status()

        results = response.json()
        entries: Dict[str, WikidataEntry] = {}

        for binding in results.get("results", {}).get("bindings", []):
            # Extract Q identifier from URI
            item_uri = binding.get("item", {}).get("value", "")
            qid = item_uri.split("/")[-1] if item_uri else None

            if not qid:
                continue

            # Get label (may be QID itself if no label found)
            label = binding.get("itemLabel", {}).get("value", "")
            # If label equals QID, it means no real label was found
            if label == qid:
                label = ""

            # Get description
            description = binding.get("itemDescription", {}).get("value", "")

            entries[qid] = WikidataEntry(label=label, description=description)

        return entries

    except requests.RequestException as e:
        logger.error(f"SPARQL request failed: {e}")
        return {}


def fetch_all_wikidata(
    qids: Set[str],
    existing: Dict[str, WikidataEntry],
    batch_size: int = DEFAULT_BATCH_SIZE,
    language: str = "en",
) -> Dict[str, WikidataEntry]:
    """
    Fetch labels and descriptions for all Q identifiers not already cached.

    Args:
        qids: Set of Q identifiers to fetch
        existing: Already-cached entries (will not be re-fetched)
        batch_size: Number of Q codes per SPARQL request
        language: Language code for labels/descriptions

    Returns:
        Updated entries dict (existing + newly fetched)
    """
    # Find Q codes we need to fetch
    missing = qids - set(existing.keys())

    if not missing:
        logger.info("All Q codes already have cached entries")
        return existing

    logger.info(f"Fetching Wikidata for {len(missing):,} Q codes")
    logger.info(f"  Already cached: {len(existing):,}")
    logger.info(f"  Batch size: {batch_size}")

    # Convert to sorted list for deterministic batching
    missing_list = sorted(missing, key=lambda x: int(x[1:]))

    # Create batches
    batches = [
        missing_list[i:i + batch_size]
        for i in range(0, len(missing_list), batch_size)
    ]

    # Copy existing entries
    all_entries = dict(existing)
    fetched_count = 0
    failed_count = 0

    for i, batch in enumerate(batches, 1):
        logger.info(f"  Batch {i}/{len(batches)}: {len(batch)} Q codes...")

        batch_entries = fetch_wikidata_batch(batch, language)

        for qid in batch:
            if qid in batch_entries:
                all_entries[qid] = batch_entries[qid]
                fetched_count += 1
            else:
                # Mark as failed (empty entry) so we don't retry
                all_entries[qid] = WikidataEntry(label="", description="")
                failed_count += 1

        # Be nice to Wikidata servers
        if i < len(batches):
            time.sleep(REQUEST_DELAY_SECONDS)

    logger.info(f"  Fetched: {fetched_count:,}")
    logger.info(f"  Failed: {failed_count:,}")

    return all_entries


# =============================================================================
# CLI Commands
# =============================================================================

def cmd_extract(args):
    """Extract Q codes from enriched JSONL."""
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        sys.exit(1)

    logger.info(f"Extracting Q codes from {input_path}")
    qids = extract_qids_from_jsonl(input_path)

    logger.info(f"  Found {len(qids):,} unique Q codes")

    save_qid_list(qids, output_path)
    logger.info(f"  -> {output_path}")


def cmd_fetch(args):
    """Fetch labels and descriptions from Wikidata for Q codes not already cached."""
    qids_path = Path(args.qids)
    cache_path = Path(args.cache)

    if not qids_path.exists():
        logger.error(f"Q codes file not found: {qids_path}")
        sys.exit(1)

    # Load Q codes to fetch
    qids = load_qid_list(qids_path)
    logger.info(f"Loaded {len(qids):,} Q codes from {qids_path}")

    # Load existing cache
    existing = load_wikidata_cache(cache_path)
    logger.info(f"Loaded {len(existing):,} cached entries from {cache_path}")

    # Fetch missing entries
    all_entries = fetch_all_wikidata(
        qids,
        existing,
        batch_size=args.batch_size,
        language=args.language,
    )

    # Save updated cache
    save_wikidata_cache(all_entries, cache_path)
    logger.info(f"  -> {cache_path}")

    # Summary
    with_label = sum(1 for e in all_entries.values() if e.label)
    with_desc = sum(1 for e in all_entries.values() if e.description)
    empty = sum(1 for e in all_entries.values() if not e.label and not e.description)
    logger.info(f"Summary:")
    logger.info(f"  With label: {with_label:,}")
    logger.info(f"  With description: {with_desc:,}")
    logger.info(f"  Empty (no data): {empty:,}")


def cmd_stats(args):
    """Show statistics about Q codes and cached entries."""
    qids_path = Path(args.qids)
    cache_path = Path(args.cache)

    qids = load_qid_list(qids_path) if qids_path.exists() else set()
    cache = load_wikidata_cache(cache_path) if cache_path.exists() else {}

    print(f"Q codes file: {qids_path}")
    print(f"  Total Q codes: {len(qids):,}")
    print()
    print(f"Cache file: {cache_path}")
    print(f"  Cached entries: {len(cache):,}")

    with_label = sum(1 for e in cache.values() if e.label)
    with_desc = sum(1 for e in cache.values() if e.description)
    empty = sum(1 for e in cache.values() if not e.label and not e.description)
    print(f"  With label: {with_label:,}")
    print(f"  With description: {with_desc:,}")
    print(f"  Empty (no data): {empty:,}")
    print()

    # Coverage
    cached_qids = set(cache.keys())
    covered = qids & cached_qids
    missing = qids - cached_qids

    print(f"Coverage:")
    print(f"  Covered: {len(covered):,} ({100*len(covered)/len(qids):.1f}%)" if qids else "  No Q codes")
    print(f"  Missing: {len(missing):,}")

    if missing and args.verbose:
        print(f"\nMissing Q codes (first 20):")
        for qid in sorted(missing, key=lambda x: int(x[1:]))[:20]:
            print(f"  {qid}")


def cmd_sample(args):
    """Show sample entries from the cache."""
    cache_path = Path(args.cache)

    if not cache_path.exists():
        logger.error(f"Cache file not found: {cache_path}")
        sys.exit(1)

    cache = load_wikidata_cache(cache_path)

    # Show sample with labels and descriptions
    count = 0
    for qid, entry in cache.items():
        if entry.label or entry.description:
            label_part = f'"{entry.label}"' if entry.label else "(no label)"
            desc_part = entry.description if entry.description else "(no description)"
            print(f"{qid}: {label_part} - {desc_part}")
            count += 1
            if count >= args.limit:
                break


def main():
    parser = argparse.ArgumentParser(
        description="Wikidata Q-code description enrichment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # extract command
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract Q codes from enriched JSONL"
    )
    extract_parser.add_argument("input", help="Input JSONL file")
    extract_parser.add_argument("output", help="Output Q codes file (one per line)")

    # fetch command
    fetch_parser = subparsers.add_parser(
        "fetch",
        help="Fetch descriptions from Wikidata"
    )
    fetch_parser.add_argument("qids", help="Q codes file (one per line)")
    fetch_parser.add_argument("cache", help="Description cache file (JSON)")
    fetch_parser.add_argument(
        "--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
        help=f"Q codes per SPARQL request (default: {DEFAULT_BATCH_SIZE})"
    )
    fetch_parser.add_argument(
        "--language", default="en",
        help="Language code for descriptions (default: en)"
    )

    # stats command
    stats_parser = subparsers.add_parser(
        "stats",
        help="Show statistics about Q codes and cache"
    )
    stats_parser.add_argument("qids", help="Q codes file")
    stats_parser.add_argument("cache", help="Description cache file")
    stats_parser.add_argument("-v", "--verbose", action="store_true")

    # sample command
    sample_parser = subparsers.add_parser(
        "sample",
        help="Show sample descriptions from cache"
    )
    sample_parser.add_argument("cache", help="Description cache file")
    sample_parser.add_argument(
        "-n", "--limit", type=int, default=20,
        help="Number of samples to show (default: 20)"
    )

    args = parser.parse_args()

    if args.command == "extract":
        cmd_extract(args)
    elif args.command == "fetch":
        cmd_fetch(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "sample":
        cmd_sample(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
