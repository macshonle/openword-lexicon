#!/usr/bin/env python3
"""
Analyze WordNet for concrete vs abstract noun classification.

Uses NLTK's WordNet interface (same as the enrichment pipeline) to:
- Identify nouns with concrete/physical properties
- Analyze lexicographer files that indicate concreteness
- Extract categories suitable for kids' word lists (animals, objects, food, etc.)
- Sample words for each category

Output: reports/wordnet_concreteness.md
"""

import sys
import logging
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List, Set, Tuple

import nltk
from nltk.corpus import wordnet as wn


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# Lexicographer files that typically contain concrete nouns
CONCRETE_CATEGORIES = {
    'noun.animal': 'Animals',
    'noun.artifact': 'Man-made objects',
    'noun.body': 'Body parts',
    'noun.food': 'Food and drink',
    'noun.object': 'Natural objects',
    'noun.plant': 'Plants',
    'noun.substance': 'Substances and materials',
}

# Categories particularly good for kids
KIDS_CATEGORIES = {
    'noun.animal': 'Animals',
    'noun.artifact': 'Objects and toys',
    'noun.body': 'Body parts',
    'noun.food': 'Food',
    'noun.plant': 'Plants and flowers',
}

# Abstract/less suitable for kids
ABSTRACT_CATEGORIES = {
    'noun.act': 'Actions and activities (abstract)',
    'noun.attribute': 'Attributes and properties (abstract)',
    'noun.cognition': 'Cognitive concepts (abstract)',
    'noun.communication': 'Communication (abstract)',
    'noun.event': 'Events (abstract)',
    'noun.feeling': 'Feelings and emotions (abstract)',
    'noun.motive': 'Goals and motives (abstract)',
    'noun.phenomenon': 'Natural phenomena (abstract)',
    'noun.possession': 'Possession (abstract)',
    'noun.process': 'Processes (abstract)',
    'noun.quantity': 'Quantities (abstract)',
    'noun.relation': 'Relations (abstract)',
    'noun.shape': 'Shapes (abstract)',
    'noun.state': 'States (abstract)',
    'noun.time': 'Time (abstract)',
}


def ensure_wordnet_data():
    """Download WordNet data if not present."""
    try:
        # Check if WordNet is available
        wn.synsets('test')
        logger.info("✓ WordNet data found")
    except LookupError:
        logger.info("Downloading WordNet data...")
        nltk.download('wordnet', quiet=False)
        nltk.download('omw-1.4', quiet=False)  # Open Multilingual WordNet
        logger.info("✓ WordNet data downloaded")


def extract_wordnet_data() -> Dict[str, List[Tuple[object, List[str]]]]:
    """
    Extract synsets from WordNet via NLTK.

    Returns: dict mapping lexname -> [(synset, [lemma_names])]
    """
    synsets_by_category = defaultdict(list)

    logger.info("Extracting synsets from WordNet...")

    # Get all noun synsets
    all_synsets = list(wn.all_synsets(pos=wn.NOUN))
    logger.info(f"  Found {len(all_synsets):,} noun synsets")

    for synset in all_synsets:
        lexname = synset.lexname()

        # Extract lemmas (words) in this synset
        lemmas = [lemma.name().replace('_', ' ').lower() for lemma in synset.lemmas()]

        synsets_by_category[lexname].append((synset, lemmas))

    logger.info(f"  Organized into {len(synsets_by_category)} lexicographer files")

    return synsets_by_category


def extract_wordnet_data_OLD(archive_path: Path) -> Dict[str, List[Dict]]:
    """OLD VERSION: Extract synsets from WordNet archive - NO LONGER USED."""
    synsets_by_category = defaultdict(list)

    with tarfile.open(archive_path, 'r:gz') as tar:
        # First, explore the archive to find data files
        print("  Exploring archive structure...")

        all_members = tar.getmembers()
        print(f"  Total files in archive: {len(all_members)}")

        # Look for different file types
        xml_files = [m for m in all_members if m.name.endswith('.xml')]
        tsv_files = [m for m in all_members if m.name.endswith('.tsv')]
        txt_files = [m for m in all_members if m.name.endswith('.txt') and 'license' not in m.name.lower() and 'readme' not in m.name.lower()]

        print(f"  XML files: {len(xml_files)}")
        print(f"  TSV files: {len(tsv_files)}")
        print(f"  TXT files (non-doc): {len(txt_files)}")

        if xml_files:
            print(f"  XML files found:")
            for f in xml_files[:10]:
                print(f"    - {f.name}")

        if tsv_files:
            print(f"  TSV files found:")
            for f in tsv_files[:10]:
                print(f"    - {f.name}")

        if txt_files:
            print(f"  TXT files found:")
            for f in txt_files[:10]:
                print(f"    - {f.name}")

        # Try to find data files in common locations
        data_files = []
        for pattern in ['entries', 'synset', 'wordnet', 'data', 'dict']:
            matches = [m for m in all_members if pattern in m.name.lower() and (m.name.endswith('.xml') or m.name.endswith('.tsv') or m.name.endswith('.txt'))]
            if matches:
                print(f"  Files matching '{pattern}':")
                for m in matches[:5]:
                    print(f"    - {m.name}")
                data_files.extend(matches)

        if not data_files:
            print("  No obvious data files found. Showing directory structure:")
            dirs = set()
            for m in all_members[:100]:
                parts = m.name.split('/')
                if len(parts) > 1:
                    dirs.add(parts[0] + '/' + parts[1] if len(parts) > 1 else parts[0])
            for d in sorted(dirs)[:20]:
                print(f"    - {d}/")
            return synsets_by_category

        # Process XML files if found
        if xml_files:
            return extract_from_xml(tar, xml_files)

        # Process TSV files if found
        if tsv_files:
            return extract_from_tsv(tar, tsv_files)

    return synsets_by_category


def extract_from_xml(tar, xml_files: List) -> Dict[str, List[Dict]]:
    """Extract data from XML files."""
    synsets_by_category = defaultdict(list)

    for xml_file in xml_files:
        print(f"  Processing {xml_file.name}...")
        f = tar.extractfile(xml_file)
        if not f:
            continue

        try:
            tree = ET.parse(f)
            root = tree.getroot()

            print(f"    Root tag: {root.tag}")
            print(f"    Root attribs: {root.attrib}")

            # Try different namespace patterns
            namespaces = {
                'wn': 'http://globalwordnet.github.io/schemas/wn',
                'dc': 'http://purl.org/dc/terms/'
            }

            # Try to find synsets with and without namespace
            synsets = (
                root.findall('.//wn:Synset', namespaces) or
                root.findall('.//{http://globalwordnet.github.io/schemas/wn}Synset') or
                root.findall('.//Synset')
            )

            print(f"    Found {len(synsets)} synsets")

            for synset in synsets:
                synset_id = synset.get('id', '')

                # Try different attribute patterns for lexfile
                lexfile = (
                    synset.get('{http://purl.org/dc/terms/}subject') or
                    synset.get('subject') or
                    synset.get('lexfile') or
                    ''
                )

                if not lexfile:
                    # Try to extract from ID (format: ewn-dog-n)
                    if '-n' in synset_id:
                        lexfile = 'noun'
                    elif '-v' in synset_id:
                        lexfile = 'verb'
                    elif '-a' in synset_id:
                        lexfile = 'adjective'
                    elif '-r' in synset_id:
                        lexfile = 'adverb'
                    else:
                        continue

                # Extract lemmas (words) in this synset
                lemmas = []
                for lemma_elem in synset.findall('.//wn:Lemma', namespaces) or synset.findall('.//Lemma'):
                    written_form = lemma_elem.get('writtenForm', '')
                    if written_form:
                        lemmas.append(written_form.lower())

                # Extract definition
                definition = ''
                for def_elem in synset.findall('.//wn:Definition', namespaces) or synset.findall('.//Definition'):
                    definition = def_elem.text or ''
                    break

                if lemmas:
                    synsets_by_category[lexfile].append({
                        'id': synset_id,
                        'lemmas': lemmas,
                        'definition': definition
                    })

            print(f"    Extracted {sum(len(s['lemmas']) for s in synsets_by_category.values())} total lemmas")

        except ET.ParseError as e:
            print(f"  Warning: Error parsing {xml_file.name}: {e}")
            continue

    print(f"  Total categories found: {len(synsets_by_category)}")
    return synsets_by_category


def extract_from_tsv(tar, tsv_files: List) -> Dict[str, List[Dict]]:
    """Extract data from TSV files (WordNet TSV format)."""
    synsets_by_category = defaultdict(list)

    # WordNet TSV format typically has separate files for different data
    # Look for synsets, senses, and entries files

    for tsv_file in tsv_files:
        print(f"  Processing {tsv_file.name}...")
        f = tar.extractfile(tsv_file)
        if not f:
            continue

        try:
            lines = f.read().decode('utf-8').split('\n')
            print(f"    Lines in file: {len(lines)}")

            # Show first few lines to understand format
            if len(lines) > 0:
                print(f"    First line (header): {lines[0][:100]}")
            if len(lines) > 1:
                print(f"    Second line (sample): {lines[1][:100]}")

            # Try to parse as TSV
            # Common formats:
            # synset_id<tab>lemma<tab>definition<tab>...
            # or
            # lemma<tab>pos<tab>synset_id<tab>...

            header = lines[0].split('\t') if lines else []
            print(f"    Columns: {header[:10]}")

            # Parse based on file name
            if 'synset' in tsv_file.name.lower():
                # Synset file
                for line in lines[1:1000]:  # Sample first 1000
                    if not line.strip():
                        continue
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        synset_id = parts[0]
                        definition = parts[1] if len(parts) > 1 else ''

                        # Extract POS from synset ID
                        pos = 'noun'  # default
                        if '-v' in synset_id:
                            pos = 'verb'
                        elif '-a' in synset_id:
                            pos = 'adjective'
                        elif '-r' in synset_id:
                            pos = 'adverb'

                        synsets_by_category[pos].append({
                            'id': synset_id,
                            'lemmas': [],  # Need to join with sense/entry files
                            'definition': definition
                        })

            elif 'sense' in tsv_file.name.lower() or 'entry' in tsv_file.name.lower():
                # Sense/entry file - links lemmas to synsets
                for line in lines[1:1000]:  # Sample first 1000
                    if not line.strip():
                        continue
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        lemma = parts[0].lower()
                        synset_id = parts[1] if len(parts) > 1 else ''

                        # Store for later joining
                        # For now, just count
                        pass

        except Exception as e:
            print(f"  Warning: Error reading {tsv_file.name}: {e}")
            continue

    print(f"  Total categories found: {len(synsets_by_category)}")
    return synsets_by_category


def analyze_categories(synsets_by_category: Dict[str, List]) -> Dict:
    """Analyze category statistics and extract samples."""
    stats = {
        'total_synsets': sum(len(synsets) for synsets in synsets_by_category.values()),
        'total_categories': len(synsets_by_category),
        'concrete_stats': {},
        'abstract_stats': {},
        'kids_stats': {},
        'all_categories': {}
    }

    # Collect all words by category
    words_by_category = defaultdict(set)
    synset_definitions = defaultdict(list)

    for category, synsets_list in synsets_by_category.items():
        for synset, lemmas in synsets_list:
            for lemma in lemmas:
                words_by_category[category].add(lemma)

            # Store synset with definition for examples
            definition = synset.definition()
            synset_definitions[category].append({
                'lemmas': lemmas[:5],  # First 5 lemmas
                'definition': definition
            })

    # Analyze each category
    for category in sorted(synsets_by_category.keys()):
        synsets_list = synsets_by_category[category]
        words = words_by_category[category]

        category_info = {
            'name': category,
            'synset_count': len(synsets_list),
            'word_count': len(words),
            'sample_words': sorted(words)[:30],  # First 30 words alphabetically
            'sample_synsets': synset_definitions[category][:5]  # First 5 synsets with definitions
        }

        stats['all_categories'][category] = category_info

        # Categorize
        if category in CONCRETE_CATEGORIES:
            stats['concrete_stats'][category] = category_info
        if category in KIDS_CATEGORIES:
            stats['kids_stats'][category] = category_info
        if category in ABSTRACT_CATEGORIES:
            stats['abstract_stats'][category] = category_info

    return stats


def generate_report(stats: Dict, output_path: Path):
    """Generate markdown report."""
    lines = [
        "# WordNet Concreteness Analysis",
        "",
        "## Overview",
        "",
        f"- **Total synsets**: {stats['total_synsets']:,}",
        f"- **Total categories**: {stats['total_categories']}",
        f"- **Concrete categories found**: {len(stats['concrete_stats'])}",
        f"- **Kids-suitable categories found**: {len(stats['kids_stats'])}",
        f"- **Abstract categories found**: {len(stats['abstract_stats'])}",
        "",
        "## Data Extraction Status",
        ""
    ]

    if stats['total_synsets'] == 0:
        lines.extend([
            "⚠️ **No synsets extracted from WordNet.**",
            "",
            "This may indicate WordNet is not installed or NLTK is not configured.",
            "Run `nltk.download('wordnet')` to install.",
            ""
        ])
    elif stats['total_categories'] < 20:
        lines.extend([
            f"⚠️ **Only {stats['total_categories']} categories found.**",
            "",
            "Expected ~40+ lexicographer file categories.",
            "The extraction may be incomplete.",
            ""
        ])
    else:
        lines.extend([
            "✓ Successfully extracted WordNet data via NLTK.",
            "",
            f"WordNet contains {stats['total_synsets']:,} noun synsets organized into {stats['total_categories']} lexicographer files (categories).",
            ""
        ])

    lines.extend([
        "## Concrete Noun Categories",
        "",
        "These categories contain physical, tangible nouns suitable for kids' games:",
        ""
    ])

    # Table header
    lines.extend([
        "| Category | Description | Synsets | Unique Words |",
        "|----------|-------------|---------|--------------|"
    ])

    for category, label in CONCRETE_CATEGORIES.items():
        if category in stats['concrete_stats']:
            info = stats['concrete_stats'][category]
            lines.append(f"| `{category}` | {label} | {info['synset_count']:,} | {info['word_count']:,} |")

    lines.extend([
        "",
        "## Kids-Appropriate Categories",
        "",
        "Recommended categories for children's vocabulary:",
        ""
    ])

    for category, label in KIDS_CATEGORIES.items():
        if category in stats['kids_stats']:
            info = stats['kids_stats'][category]
            lines.extend([
                f"### {label} (`{category}`)",
                "",
                f"- **Synsets**: {info['synset_count']:,}",
                f"- **Unique words**: {info['word_count']:,}",
                "",
                "Sample words:",
                "```"
            ])
            lines.extend(info['sample_words'][:20])
            lines.extend([
                "```",
                "",
                "Sample synsets with definitions:",
                ""
            ])
            for synset in info['sample_synsets'][:3]:
                lemmas_str = ', '.join(synset['lemmas'][:5])
                lines.append(f"- **{lemmas_str}**: {synset['definition']}")
            lines.append("")

    lines.extend([
        "## Abstract Categories (Exclude from Kids' Lists)",
        "",
        "These categories contain abstract concepts less suitable for kids:",
        ""
    ])

    # Table header
    lines.extend([
        "| Category | Description | Synsets | Unique Words |",
        "|----------|-------------|---------|--------------|"
    ])

    for category, label in ABSTRACT_CATEGORIES.items():
        if category in stats['abstract_stats']:
            info = stats['abstract_stats'][category]
            lines.append(f"| `{category}` | {label} | {info['synset_count']:,} | {info['word_count']:,} |")

    lines.extend([
        "",
        "## All Categories",
        "",
        "Complete list of all noun categories in WordNet:",
        ""
    ])

    noun_categories = {k: v for k, v in stats['all_categories'].items() if k.startswith('noun.')}
    for category in sorted(noun_categories.keys()):
        info = noun_categories[category]
        lines.append(f"- `{category}`: {info['synset_count']:,} synsets, {info['word_count']:,} words")

    # Add total words in each broad category
    lines.extend([
        "",
        "## Category Statistics",
        "",
        "### Concrete Categories Total",
        ""
    ])

    total_concrete_synsets = sum(info['synset_count'] for info in stats['concrete_stats'].values())
    total_concrete_words = len(set(
        word
        for info in stats['concrete_stats'].values()
        for word in info['sample_words']
    ))

    lines.extend([
        f"- **Total synsets**: {total_concrete_synsets:,}",
        f"- **Estimated unique words**: {total_concrete_words:,}+ (sample only)",
        "",
        "### Abstract Categories Total",
        ""
    ])

    total_abstract_synsets = sum(info['synset_count'] for info in stats['abstract_stats'].values())
    total_abstract_words = len(set(
        word
        for info in stats['abstract_stats'].values()
        for word in info['sample_words']
    ))

    lines.extend([
        f"- **Total synsets**: {total_abstract_synsets:,}",
        f"- **Estimated unique words**: {total_abstract_words:,}+ (sample only)",
        ""
    ])

    lines.extend([
        "## Integration Strategy",
        "",
        "### Current Pipeline Integration",
        "",
        "The enrichment pipeline (`src/openword/wordnet_enrich.py`) already uses WordNet via NLTK to:",
        "",
        "1. **Classify nouns as concrete/abstract/mixed**",
        "   - Uses lexicographer file names (lexnames)",
        "   - Checks hypernym paths for physical_entity vs abstraction",
        "   - Stores result in `concreteness` field",
        "",
        "2. **Backfill POS tags**",
        "   - For entries missing POS data",
        "   - Uses WordNet synset lookups",
        "",
        "**Current enrichment coverage** (from capability audit):",
        "- ~34.5% of core distribution entries have concreteness data",
        "- 20,670 concrete nouns, 25,782 abstract, 25,408 mixed",
        "",
        "### For Kids' Concrete Nouns List",
        "",
        "**Recommended approach:**",
        "",
        "1. **Use existing pipeline enrichment**",
        "   - Filter entries with `concreteness == 'concrete'`",
        "   - No need to re-extract from WordNet",
        "",
        "2. **Optionally filter by lexname categories**",
        "   - Add `wordnet_lexname` field during enrichment",
        "   - Filter for kids-appropriate categories (animal, food, body, plant, artifact)",
        "",
        "3. **Apply additional filters**",
        "   - Word length: 3-10 characters",
        "   - Frequency: Top 10,000 most common",
        "   - Exclude vulgar/offensive",
        "   - Exclude archaic/obsolete",
        "",
        "### Enhanced Filtering Example",
        "",
        "```bash",
        "# Filter for concrete nouns suitable for kids",
        "jq -r 'select(",
        "  (.pos | contains([\"noun\"])) and",
        "  .concreteness == \"concrete\" and",
        "  .is_phrase == false and",
        "  (.word | test(\"^[a-z]+$\")) and",
        "  (.word | length >= 3 and length <= 10) and",
        "  (.frequency_tier | IN(\"top1k\", \"top10k\")) and",
        "  (.labels.register // [] | any(. == \"vulgar\" or . == \"offensive\") | not)",
        ") | .word' data/intermediate/core/core_entries_enriched.jsonl \\",
        "  | sort -u > kids-concrete-nouns.txt",
        "```",
        "",
        "### Future Enhancement: Add Lexname Field",
        "",
        "To enable filtering by WordNet category:",
        "",
        "```python",
        "# In wordnet_enrich.py, add to enrich_entry():",
        "if 'noun' in entry.get('pos', []):",
        "    synsets = wn.synsets(word, pos=wn.NOUN)",
        "    if synsets:",
        "        # Get most common lexname",
        "        lexnames = [s.lexname() for s in synsets]",
        "        entry['wordnet_lexname'] = Counter(lexnames).most_common(1)[0][0]",
        "```",
        "",
        "Then filter:",
        "```bash",
        "# Only animal words",
        "jq -r 'select(.wordnet_lexname == \"noun.animal\") | .word'",
        "",
        "# Only concrete categories",
        "jq -r 'select(.wordnet_lexname | IN(",
        "  \"noun.animal\", \"noun.artifact\", \"noun.body\",",
        "  \"noun.food\", \"noun.plant\", \"noun.object\", \"noun.substance\"",
        ")) | .word'",
        "```",
        ""
    ])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text('\n'.join(lines), encoding='utf-8')


def main():
    logger.info("=" * 60)
    logger.info("WordNet Concreteness Analysis")
    logger.info("=" * 60)

    # Ensure WordNet data is available
    ensure_wordnet_data()

    # Extract data from NLTK's WordNet
    synsets_by_category = extract_wordnet_data()

    if not synsets_by_category:
        logger.error("Failed to extract WordNet data")
        sys.exit(1)

    # Analyze categories
    stats = analyze_categories(synsets_by_category)
    logger.info(f"✓ Analyzed {stats['total_synsets']:,} synsets")
    logger.info(f"  Concrete categories: {len(stats['concrete_stats'])}")
    logger.info(f"  Kids categories: {len(stats['kids_stats'])}")
    logger.info(f"  Abstract categories: {len(stats['abstract_stats'])}")

    # Generate report
    output_path = Path("reports/wordnet_concreteness.md")
    generate_report(stats, output_path)
    logger.info(f"✓ Report saved: {output_path}")

    # Print summary
    logger.info("")
    logger.info("Summary of Kids-Appropriate Categories:")
    for category, label in KIDS_CATEGORIES.items():
        if category in stats['kids_stats']:
            info = stats['kids_stats'][category]
            logger.info(f"  {label:20s}: {info['word_count']:,} words")


if __name__ == '__main__':
    main()
