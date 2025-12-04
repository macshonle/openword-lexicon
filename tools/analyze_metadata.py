#!/usr/bin/env python3
"""
analyze_metadata.py - Comprehensive metadata analysis and pipeline insights

Consolidates and enhances:
- inspect_metadata.py (general metadata exploration)
- analyze_game_metadata.py (game-specific filtering analysis)
- report_label_statistics_built.py (label coverage analysis)

Adds:
- Sense-based format analysis and recommendations
- Label data loss diagnosis
- Comprehensive filtering recommendations
"""

import json
import random
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, Any, List, Tuple


def load_metadata(meta_path: Path) -> Dict[str, Any]:
    """Load metadata from JSONL lexeme file or legacy JSON array."""
    if not meta_path.exists():
        return {}

    metadata = {}

    # JSONL format (current pipeline)
    if meta_path.suffix == '.jsonl':
        with open(meta_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    entry = json.loads(line)
                    metadata[entry['word']] = entry
    else:
        # Legacy JSON array format
        with open(meta_path, 'r', encoding='utf-8') as f:
            metadata_list = json.load(f)
        metadata = {entry['word']: entry for entry in metadata_list}

    return metadata


def load_senses(senses_path: Path) -> Dict[str, Dict[str, Any]]:
    """Load senses file and aggregate sense-level data per word.

    The senses file contains one entry per sense with:
    - pos (string, including 'proper' for proper nouns)
    - register_tags, domain_tags, region_tags, temporal_tags (arrays)
    - is_abbreviation, is_inflected (booleans)

    Returns a dict with aggregated data per word:
    {
        'word': {
            'pos': ['noun', 'verb'],  # List of unique POS
            'labels': {
                'register': ['informal', 'slang'],
                'domain': ['medicine', 'law'],
                'region': ['UK', 'US'],
                'temporal': ['archaic', 'dated'],
            }
        }
    }
    """
    if not senses_path.exists():
        return {}

    word_senses: Dict[str, Dict[str, Any]] = {}

    with open(senses_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            entry = json.loads(line)
            word = entry.get('word', '')

            if word not in word_senses:
                word_senses[word] = {
                    'pos': set(),
                    'labels': {
                        'register': set(),
                        'domain': set(),
                        'region': set(),
                        'temporal': set(),
                    }
                }

            # Collect POS
            pos = entry.get('pos')
            if pos:
                word_senses[word]['pos'].add(pos)

            # Collect tags
            for tag_field, label_key in [
                ('register_tags', 'register'),
                ('domain_tags', 'domain'),
                ('region_tags', 'region'),
                ('temporal_tags', 'temporal'),
            ]:
                tags = entry.get(tag_field, [])
                word_senses[word]['labels'][label_key].update(tags)

    # Convert sets to sorted lists
    for word, data in word_senses.items():
        data['pos'] = sorted(data['pos'])
        for label_key in data['labels']:
            data['labels'][label_key] = sorted(data['labels'][label_key])

    return word_senses


def merge_lexemes_and_senses(
    lexemes: Dict[str, Any],
    senses: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """Merge lexeme entries with aggregated sense data."""
    for word, lexeme in lexemes.items():
        if word in senses:
            sense_data = senses[word]
            lexeme['pos'] = sense_data['pos']
            lexeme['labels'] = sense_data['labels']
        else:
            # Word has no senses (secondary source only)
            lexeme['pos'] = []
            lexeme['labels'] = {}

    return lexemes


def analyze_frequency_tiers(metadata: Dict[str, Any]) -> Tuple[str, Dict]:
    """Analyze frequency tier distribution."""
    tier_counts = Counter()

    for word, meta in metadata.items():
        tier = meta.get('frequency_tier')
        tier_counts[tier] += 1

    report = "## Frequency Tier Distribution\n\n"
    report += "| Tier | Count | Percentage (of Ranked) |\n"
    report += "|------|------:|-----------------------:|\n"

    total = sum(tier_counts.values())
    # Calculate total of ranked entries (excluding Z tier)
    ranked_total = sum(count for tier, count in tier_counts.items() if tier != 'Z' and tier is not None)

    # Sort by tier number (None at end)
    sorted_tiers = sorted([t for t in tier_counts.keys() if t is not None])
    if None in tier_counts:
        sorted_tiers.append(None)

    for tier in sorted_tiers:
        count = tier_counts[tier]
        # For Z tier, show N/A for percentage; for others, calculate % of ranked entries
        if tier == 'Z':
            pct_display = "N/A"
        else:
            pct = (count / ranked_total * 100) if ranked_total > 0 else 0
            pct_display = f"{pct:.1f}%"
        tier_display = tier if tier is not None else 'N/A'
        report += f"| {tier_display} | {count:,} | {pct_display} |\n"

    report += f"\n*Ranked entries: {ranked_total:,} | Unranked (Z): {tier_counts.get('Z', 0):,}*\n\n"

    # Sample words from each tier - show ALL tiers, enumerate when count < 10
    report += "### Sample Words by Tier\n\n"

    for tier in sorted_tiers:  # Show ALL tiers
        tier_words = [w for w, m in metadata.items() if m.get('frequency_tier') == tier]
        tier_display = tier if tier is not None else 'N/A'

        if not tier_words:
            # Explicitly report null cases
            report += f"**Tier {tier_display}:** *(no words)*  \n"
        elif len(tier_words) < 10:
            # Enumerate all words when count < 10
            sorted_words = sorted(tier_words)
            report += f"**Tier {tier_display}:** ({len(tier_words)} words) {', '.join(f'`{w}`' for w in sorted_words)}  \n"
        else:
            # Sample 5 words for larger sets
            sample = random.sample(tier_words, 5)
            report += f"**Tier {tier_display}:** ({len(tier_words):,} words) {', '.join(f'`{w}`' for w in sample)}  \n"

    report += "\n"

    stats = {
        'tier_counts': tier_counts,
        'total': total
    }

    return report, stats


def analyze_sources(metadata: Dict[str, Any]) -> str:
    """Analyze source distribution."""
    source_counts = Counter()
    source_combos = Counter()

    for word, meta in metadata.items():
        sources = meta.get('sources', [])
        for source in sources:
            source_counts[source] += 1

        # Track source combinations
        combo = tuple(sorted(sources))
        source_combos[combo] += 1

    report = "## Source Distribution\n\n"
    report += "### Individual Sources\n\n"
    report += "| Source | Words |\n"
    report += "|--------|------:|\n"

    for source, count in source_counts.most_common():
        report += f"| {source} | {count:,} |\n"

    report += "\n### Source Combinations\n\n"
    report += "| Sources | Words |\n"
    report += "|---------|------:|\n"

    for combo, count in source_combos.most_common(10):
        combo_str = ', '.join(combo) if combo else 'None'
        report += f"| {combo_str} | {count:,} |\n"

    report += "\n"
    return report


def analyze_labels(metadata: Dict[str, Any]) -> Tuple[str, Dict]:
    """Analyze label distribution."""
    pos_counts = Counter()
    register_counts = Counter()
    domain_counts = Counter()
    region_counts = Counter()
    temporal_counts = Counter()

    entries_with_labels = 0
    entries_with_pos = 0
    entries_with_register = 0
    entries_with_domain = 0
    entries_with_region = 0
    entries_with_temporal = 0

    for word, meta in metadata.items():
        labels = meta.get('labels', {})

        if labels:
            entries_with_labels += 1

        # POS is stored in the top-level 'pos' field, not in 'labels'
        pos_list = meta.get('pos', [])
        if pos_list:
            entries_with_pos += 1
            for pos in pos_list:
                pos_counts[pos] += 1

        # Register labels
        register_list = labels.get('register', [])
        if register_list:
            entries_with_register += 1
            for reg in register_list:
                register_counts[reg] += 1

        # Domain labels
        domain_list = labels.get('domain', [])
        if domain_list:
            entries_with_domain += 1
            for dom in domain_list:
                domain_counts[dom] += 1

        # Region labels
        region_list = labels.get('region', [])
        if region_list:
            entries_with_region += 1
            for reg in region_list:
                region_counts[reg] += 1

        # Temporal labels
        temporal_list = labels.get('temporal', [])
        if temporal_list:
            entries_with_temporal += 1
            for tmp in temporal_list:
                temporal_counts[tmp] += 1

    total = len(metadata)

    report = "## Label Coverage Analysis\n\n"
    report += f"**Metadata coverage summary:**\n\n"
    report += "| Metadata Type | Entries | Percentage |\n"
    report += "|--------------|--------:|-----------:|\n"
    report += f"| POS tags | {entries_with_pos:,} | {entries_with_pos/total*100:.1f}% |\n"
    report += f"| Any labels | {entries_with_labels:,} | {entries_with_labels/total*100:.1f}% |\n"
    report += f"| Register labels | {entries_with_register:,} | {entries_with_register/total*100:.1f}% |\n"
    report += f"| Domain labels | {entries_with_domain:,} | {entries_with_domain/total*100:.1f}% |\n"
    report += f"| Region labels | {entries_with_region:,} | {entries_with_region/total*100:.1f}% |\n"
    report += f"| Temporal labels | {entries_with_temporal:,} | {entries_with_temporal/total*100:.1f}% |\n"
    report += "\n"
    report += "*Note: POS tags are stored separately from labels in the metadata.*\n\n"

    if pos_counts:
        report += "### Part of Speech Tags\n\n"
        report += "| POS | Count |\n"
        report += "|-----|------:|\n"
        for pos, count in pos_counts.most_common(15):
            report += f"| {pos} | {count:,} |\n"

        # Check for expected but missing POS tags
        all_expected_pos = {'noun', 'verb', 'adjective', 'adverb', 'pronoun', 'preposition',
                           'conjunction', 'interjection', 'determiner', 'particle', 'auxiliary'}
        missing_pos = all_expected_pos - set(pos_counts.keys())

        if missing_pos:
            report += f"\n⚠️  **Missing POS tags:** {', '.join(sorted(missing_pos))}  \n"
            report += "*These POS tags are defined in the schema but have zero occurrences in the data.*\n"

        report += "\n"

    if register_counts:
        report += "### Register Labels\n\n"
        report += "| Register | Count |\n"
        report += "|----------|------:|\n"
        for reg, count in register_counts.most_common(15):
            report += f"| {reg} | {count:,} |\n"
        report += "\n"

    if domain_counts:
        report += "### Domain Labels\n\n"
        report += "| Domain | Count |\n"
        report += "|--------|------:|\n"
        for dom, count in domain_counts.most_common(20):
            report += f"| {dom} | {count:,} |\n"
        report += "\n"

    if region_counts:
        report += "### Region Labels\n\n"
        report += "| Region | Count |\n"
        report += "|--------|------:|\n"
        for reg, count in region_counts.most_common():
            report += f"| {reg} | {count:,} |\n"
        report += "\n"

    if temporal_counts:
        report += "### Temporal Labels\n\n"
        report += "| Temporal | Count |\n"
        report += "|----------|------:|\n"
        for tmp, count in temporal_counts.most_common():
            report += f"| {tmp} | {count:,} |\n"
        report += "\n"

    stats = {
        'entries_with_labels': entries_with_labels,
        'pos_counts': pos_counts,
        'register_counts': register_counts,
        'domain_counts': domain_counts,
        'region_counts': region_counts,
        'temporal_counts': temporal_counts,
    }

    return report, stats


def analyze_game_metadata(metadata: Dict[str, Any]) -> Tuple[str, Dict]:
    """Analyze metadata for game-specific filtering."""
    total = len(metadata)

    # Count field coverage
    has_pos = sum(1 for e in metadata.values() if e.get('pos'))
    has_concreteness = sum(1 for e in metadata.values() if e.get('concreteness'))
    has_frequency = sum(1 for e in metadata.values() if e.get('frequency_tier'))
    has_labels = sum(1 for e in metadata.values() if e.get('labels'))
    has_gloss = sum(1 for e in metadata.values() if e.get('gloss'))
    has_syllables = sum(1 for e in metadata.values() if e.get('syllables'))

    # Count nouns
    nouns = [e for e in metadata.values() if 'noun' in e.get('pos', [])]
    concrete_nouns = [e for e in nouns if e.get('concreteness') == 'concrete']
    abstract_nouns = [e for e in nouns if e.get('concreteness') == 'abstract']
    mixed_nouns = [e for e in nouns if e.get('concreteness') == 'mixed']
    nouns_no_concrete = [e for e in nouns if not e.get('concreteness')]

    # Frequency distribution of nouns
    noun_freq = Counter()
    for noun in nouns:
        tier = noun.get('frequency_tier', 'rare')
        noun_freq[tier] += 1

    # Concreteness distribution
    concrete_dist = Counter()
    for entry in metadata.values():
        if 'noun' in entry.get('pos', []):
            concrete_dist[entry.get('concreteness', 'unknown')] += 1

    report = "## Game-Specific Metadata Analysis\n\n"
    report += "This section analyzes metadata coverage for word game filtering needs.\n\n"
    report += "### Field Coverage\n\n"
    report += f"**Total entries:** {total:,}\n\n"

    report += "| Field | Coverage | Percentage |\n"
    report += "|-------|------:|----------:|\n"

    fields = [
        ('POS tags', has_pos),
        ('Concreteness', has_concreteness),
        ('Frequency tier', has_frequency),
        ('Labels', has_labels),
        ('Syllables', has_syllables),
        ('Gloss', has_gloss),
    ]

    for field_name, count in fields:
        pct = count / total * 100 if total > 0 else 0
        report += f"| {field_name} | {count:,} | {pct:.1f}% |\n"

    report += "\n### Noun Analysis\n\n"
    report += f"**Total nouns:** {len(nouns):,}\n"
    report += f"**Concrete nouns:** {len(concrete_nouns):,}\n"
    report += f"**Abstract nouns:** {len(abstract_nouns):,}\n"
    report += f"**Mixed nouns:** {len(mixed_nouns):,}\n"
    report += f"**Nouns without concreteness data:** {len(nouns_no_concrete):,}\n\n"

    if len(nouns_no_concrete) > 0:
        pct_missing = len(nouns_no_concrete) / len(nouns) * 100 if len(nouns) > 0 else 0
        report += f"⚠️  **{pct_missing:.1f}%** of nouns lack concreteness metadata!\n\n"

    #Syllable analysis
    if has_syllables > 0:
        syllable_dist = Counter()
        for entry in metadata.values():
            syll_count = entry.get('syllables')
            if syll_count is not None:
                syllable_dist[syll_count] += 1

        report += "\n### Syllable Analysis\n\n"
        report += f"**Words with syllable data:** {has_syllables:,} ({has_syllables/total*100:.1f}%)\n\n"

        if syllable_dist:
            report += "#### Syllable Distribution\n\n"
            report += "| Syllables | Count | Percentage |\n"
            report += "|-----------|------:|-----------:|\n"

            for syll_count in sorted(syllable_dist.keys())[:15]:  # Top 15
                count = syllable_dist[syll_count]
                pct = count / has_syllables * 100
                report += f"| {syll_count} | {count:,} | {pct:.1f}% |\n"

            # Summary stats
            total_syllables = sum(k * v for k, v in syllable_dist.items())
            avg_syllables = total_syllables / has_syllables if has_syllables > 0 else 0
            max_syllables = max(syllable_dist.keys()) if syllable_dist else 0

            report += f"\n**Average syllables:** {avg_syllables:.2f}  \n"
            report += f"**Max syllables:** {max_syllables}  \n"

            # Sample words by syllable count
            report += "\n#### Sample Words by Syllable Count\n\n"
            report += "*(Excludes proverbs and long phrases with >5 words)*\n\n"
            for syll_count in [1, 2, 3, 4, 5]:
                if syll_count in syllable_dist:
                    # Filter out proverbs and long phrases from samples
                    words_with_syll = [
                        w for w, e in metadata.items()
                        if e.get('syllables') == syll_count
                        and e.get('phrase_type') != 'proverb'
                        and e.get('word_count', 1) <= 5
                    ]
                    count = len(words_with_syll)

                    if count < 10:
                        # Enumerate all when < 10, with annotations
                        words_with_meta = [(w, metadata[w]) for w in words_with_syll]
                        words_with_meta.sort(key=lambda x: x[0])
                        formatted = []
                        for w, meta in words_with_meta:
                            phrase_type = meta.get('phrase_type')
                            word_count = meta.get('word_count', 1)
                            if phrase_type or word_count > 1:
                                annotations = []
                                if phrase_type:
                                    annotations.append(phrase_type)
                                if word_count > 1:
                                    annotations.append(f"{word_count} words")
                                formatted.append(f"`{w}` ({', '.join(annotations)})")
                            else:
                                formatted.append(f"`{w}`")
                        report += f"**{syll_count} syllable{'s' if syll_count > 1 else ''}:** ({count} words) {', '.join(formatted)}  \n"
                    else:
                        # Sample 5 for larger sets
                        sample = random.sample(words_with_syll, min(5, len(words_with_syll)))
                        formatted = []
                        for w in sample:
                            meta = metadata[w]
                            phrase_type = meta.get('phrase_type')
                            word_count = meta.get('word_count', 1)
                            if phrase_type or word_count > 1:
                                annotations = []
                                if phrase_type:
                                    annotations.append(phrase_type)
                                if word_count > 1:
                                    annotations.append(f"{word_count} words")
                                formatted.append(f"`{w}` ({', '.join(annotations)})")
                            else:
                                formatted.append(f"`{w}`")
                        report += f"**{syll_count} syllable{'s' if syll_count > 1 else ''}:** {', '.join(formatted)}  \n"

            # Complete enumeration for rare syllable counts (< 10 words)
            rare_syllable_counts = [k for k, v in syllable_dist.items() if v < 10 and k > 5]
            if rare_syllable_counts:
                report += "\n#### Complete Enumeration for Rare Syllable Counts\n\n"
                for syll_count in sorted(rare_syllable_counts):
                    words_with_syll_data = [(w, metadata[w]) for w in metadata.keys()
                                           if metadata[w].get('syllables') == syll_count]
                    words_with_syll_data.sort(key=lambda x: x[0])  # Sort by word

                    count = len(words_with_syll_data)

                    # Format each word with metadata annotations
                    formatted_words = []
                    for word, meta in words_with_syll_data:
                        phrase_type = meta.get('phrase_type')
                        word_count = meta.get('word_count')

                        if phrase_type or (word_count and word_count > 3):
                            # Annotate special cases
                            annotations = []
                            if phrase_type:
                                annotations.append(phrase_type)
                            if word_count and word_count > 3:
                                annotations.append(f"{word_count} words")
                            formatted_words.append(f"`{word}` ({', '.join(annotations)})")
                        else:
                            formatted_words.append(f"`{word}`")

                    report += f"**{syll_count} syllables:** ({count} word{'s' if count > 1 else ''}) {', '.join(formatted_words)}  \n"

            report += "\n"

    # Concreteness distribution
    report += "### Concreteness Distribution\n\n"
    report += "| Type | Count |\n"
    report += "|------|------:|\n"
    for concrete_type, count in concrete_dist.most_common():
        report += f"| {concrete_type} | {count:,} |\n"
    report += "\n"

    # Frequency distribution (using letter-based tiers A-L/Y/Z)
    report += "#### Frequency Distribution by Tier (Nouns Only)\n\n"
    report += "| Tier | Count | Percentage |\n"
    report += "|------|------:|-----------:|\n"

    # Get all tiers present in noun data
    all_tiers = sorted(set(noun_freq.keys()))
    total_nouns_with_tier = sum(noun_freq.values())

    for tier in all_tiers:
        count = noun_freq[tier]
        pct = (count / total_nouns_with_tier * 100) if total_nouns_with_tier > 0 else 0
        tier_display = tier if tier is not None else 'N/A'
        report += f"| {tier_display} | {count:,} | {pct:.1f}% |\n"

    # Show total
    report += f"\n**Total nouns with frequency tier:** {total_nouns_with_tier:,}  \n"
    if len(nouns) > total_nouns_with_tier:
        missing = len(nouns) - total_nouns_with_tier
        report += f"**Nouns without frequency tier:** {missing:,}  \n"
    report += "\n"

    stats = {
        'total_nouns': len(nouns),
        'concrete_nouns': len(concrete_nouns),
        'abstract_nouns': len(abstract_nouns),
        'mixed_nouns': len(mixed_nouns),
        'nouns_no_concrete': len(nouns_no_concrete),
        'has_labels': has_labels,
    }

    return report, stats


def analyze_sense_based_format(metadata: Dict[str, Any]) -> str:
    """Analyze and propose sense-based intermediate format."""

    # Find words with multiple POS tags as candidates for sense splitting
    multi_pos_words = []
    for word, meta in metadata.items():
        pos_list = meta.get('pos', [])
        if len(pos_list) > 1:
            multi_pos_words.append((word, pos_list, meta))

    # Find examples with regional variants
    regional_variants = defaultdict(list)
    for word, meta in metadata.items():
        labels = meta.get('labels', {})
        regions = labels.get('region', [])
        if regions:
            regional_variants[word].append((regions, meta))

    report = "## Sense-Based Format Analysis\n\n"
    report += "### Current Limitations\n\n"
    report += "The current format merges all senses of a word into a single entry:\n\n"
    report += "**Issues:**\n"
    report += "- Words with multiple POS (e.g., 'crow' as noun and verb) lose sense-specific metadata\n"
    report += "- Regional variants (e.g., 'colour' vs 'color') are not linked\n"
    report += "- Sense-specific labels (e.g., offensive meaning vs. neutral meaning) are conflated\n"
    report += "- Downstream filtering cannot distinguish between word senses\n\n"

    report += f"**Statistics:**\n"
    report += f"- **{len(multi_pos_words):,}** words have multiple POS tags (potential for sense splitting)\n"
    report += f"- **{len(regional_variants):,}** words have regional labels\n\n"

    report += "### Proposed Sense-Based Format\n\n"
    report += "Each sense of a word becomes its own entry with a sense ID:\n\n"
    report += "```\n"
    report += "word    sense_id    metadata_fields\n"
    report += "crow    crow.n.1    pos:noun|sem:animal|sem:bird|domain:zoology|concrete:yes|freq:top3k\n"
    report += "crow    crow.n.2    pos:noun|sem:person|register:derogatory|register:offensive|temporal:historical\n"
    report += "crow    crow.v.1    pos:verb|sem:sound|sem:vocalize|concrete:no|freq:top10k\n"
    report += "mummy   mummy.n.1   pos:noun|sem:artifact|sem:corpse|domain:archaeology|concrete:yes\n"
    report += "mummy   mummy.n.2   pos:noun|sem:person|sem:parent|register:informal|region:en-GB|freq:top5k\n"
    report += "colour  colour.n.1  pos:noun|sem:attribute|sem:visual|region:en-GB|freq:top1k|variant:color\n"
    report += "color   color.n.1   pos:noun|sem:attribute|sem:visual|region:en-US|freq:top1k|variant:colour\n"
    report += "```\n\n"

    report += "### Benefits\n\n"
    report += "1. **Precise filtering:** Filter out offensive senses while keeping neutral ones\n"
    report += "2. **Regional handling:** Link variant spellings, choose preferred region\n"
    report += "3. **Semantic richness:** Add semantic tags (animal, person, sound, etc.)\n"
    report += "4. **Game optimization:** Include only common senses, exclude rare technical senses\n"
    report += "5. **Frequency per sense:** Different senses may have different frequencies\n\n"

    report += "### Implementation Path\n\n"
    report += "1. **Extract sense-level data from Wiktionary**\n"
    report += "   - Current scanner merges all senses - needs modification\n"
    report += "   - Parse each sense separately with its own labels, glosses, etc.\n\n"

    report += "2. **Generate sense IDs**\n"
    report += "   - Format: `{word}.{pos_abbrev}.{sense_num}`\n"
    report += "   - Example: `crow.n.1`, `crow.v.1`\n"
    report += "   - Handle multi-word phrases with URL encoding if needed\n\n"

    report += "3. **Add semantic tags**\n"
    report += "   - Extract from Wiktionary glosses using NLP\n"
    report += "   - Use WordNet hypernyms (animal, person, object, etc.)\n"
    report += "   - Manual curation for high-frequency words\n\n"

    report += "4. **Link variants**\n"
    report += "   - Track US/UK spelling pairs\n"
    report += "   - Include `variant:` field pointing to alternate spellings\n\n"

    report += "5. **Downstream processing**\n"
    report += "   - Filters can target specific senses\n"
    report += "   - Final word lists can collapse senses or keep them separate\n"
    report += "   - Enables sophisticated game-specific word selection\n\n"

    report += "### Example Filtering Queries\n\n"
    report += "```bash\n"
    report += "# Get only concrete nouns (any sense)\n"
    report += "grep '|concrete:yes' senses.txt | cut -f1 | sort -u\n\n"

    report += "# Get common words excluding offensive senses\n"
    report += "grep '|freq:top' senses.txt | grep -v '|register:offensive' | cut -f1 | sort -u\n\n"

    report += "# Get US-preferred spellings\n"
    report += "grep '|region:en-US' senses.txt | cut -f1 | sort -u\n\n"

    report += "# Get animal words\n"
    report += "grep '|sem:animal' senses.txt | cut -f1 | sort -u\n"
    report += "```\n\n"

    report += "### Sample Multi-POS Words\n\n"
    report += "Examples of words that would benefit from sense splitting:\n\n"

    # Show 10 interesting examples
    for word, pos_list, meta in multi_pos_words[:10]:
        pos_str = ', '.join(pos_list)
        report += f"- **{word}**: {pos_str}\n"

    report += "\n"

    return report


def generate_filtering_recommendations(label_stats: Dict, game_stats: Dict) -> str:
    """Generate comprehensive filtering recommendations."""

    report = "## Filtering Recommendations\n\n"

    # Check label coverage
    label_coverage = label_stats['entries_with_labels']
    has_labels = label_coverage > 100  # Arbitrary threshold

    if not has_labels:
        report += "### ⚠️ CRITICAL: Label Data Loss Detected\n\n"
        report += f"Only {label_coverage:,} entries have labels in the final distribution.\n"
        report += "This indicates a pipeline issue where labels are being dropped during build.\n\n"
        report += "**Action required:**\n"
        report += "1. Investigate build pipeline for label preservation\n"
        report += "2. Check intermediate files to identify where labels are lost\n"
        report += "3. Fix label extraction and/or merging logic\n\n"

    # Concreteness filtering
    nouns_no_concrete = game_stats['nouns_no_concrete']
    if nouns_no_concrete > 1000:
        report += "### 1. Improve Concreteness Detection\n\n"
        report += f"{nouns_no_concrete:,} nouns lack concreteness data. Options:\n\n"
        report += "- **Heuristic-based:** Infer from word endings, domains, etc.\n"
        report += "- **ML-based:** Train classifier on known concrete/abstract words\n"
        report += "- **External data:** Import from concreteness databases\n"
        report += "- **Manual annotation:** Crowdsource or hire annotators\n\n"

    # Domain filtering
    if has_labels:
        report += "### 2. Domain-Based Filtering\n\n"
        report += "Use domain labels to exclude:\n"
        report += "- Adult content (sexuality, drugs, violence)\n"
        report += "- Jargon (technical, specialized)\n"
        report += "- Age-inappropriate (weapons, alcohol)\n\n"
    else:
        report += "### 2. Domain-Based Filtering\n\n"
        report += "⚠️ Domain labels not available - fix pipeline first\n\n"

    # Frequency filtering
    report += "### 3. Frequency-Based Ranking\n\n"
    report += "Prioritize common words (top10k tier) that people actually use:\n"
    report += "- **Kids' games:** top1k to top10k\n"
    report += "- **General games:** top100 to top100k\n"
    report += "- **Expert games:** Include rare words\n\n"

    # Regional filtering
    if has_labels:
        report += "### 4. Regional Filtering\n\n"
        report += "Use region labels to:\n"
        report += "- Standardize on US English for US-market games\n"
        report += "- Include both US/UK variants with preference marking\n"
        report += "- Exclude region-specific slang if needed\n\n"

    # Manual review
    report += "### 5. Manual Review Process\n\n"
    report += "Even with good filters, manual review is essential:\n"
    report += "- Review top 500-1000 candidates\n"
    report += "- Create whitelist of verified words\n"
    report += "- Create blacklist of inappropriate words\n"
    report += "- Use lists to train better filters\n\n"

    return report


def sample_entries_by_source(metadata: Dict[str, Any]) -> str:
    """Sample entries from different source combinations."""
    # Group entries by source combinations
    source_combinations = defaultdict(list)

    for word, meta in metadata.items():
        sources = tuple(sorted(meta.get('sources', [])))
        source_combinations[sources].append((word, meta))

    report = "## Sample Entries by Source\n\n"
    report += "Representative samples from different source combinations:\n\n"

    # Sort by count (most common first)
    sorted_combos = sorted(source_combinations.items(), key=lambda x: len(x[1]), reverse=True)

    # Show samples from top source combinations
    for sources, entries in sorted_combos[:8]:  # Top 8 combinations
        sources_str = ', '.join(sources) if sources else 'None'
        count = len(entries)

        report += f"### {sources_str} ({count:,} entries)\n\n"

        # Sample 3 entries
        sample_entries = random.sample(entries, min(3, len(entries)))

        for word, meta in sample_entries:
            report += f"**`{word}`**\n"
            report += "```json\n"
            report += json.dumps(meta, indent=2, ensure_ascii=False, sort_keys=True)
            report += "\n```\n\n"

        report += "\n"

    return report


def sample_rich_entries(metadata: Dict[str, Any]) -> str:
    """Sample entries with rich metadata."""
    # Find entries with lots of metadata
    rich_entries = []

    for word, meta in metadata.items():
        score = 0
        score += len(meta.get('sources', []))
        score += len(meta.get('labels', {}).get('pos', []))
        score += len(meta.get('labels', {}).get('domain', []))
        score += 1 if meta.get('frequency_tier') else 0
        score += 1 if meta.get('gloss') else 0

        if score >= 5:  # Threshold for "rich"
            rich_entries.append((word, meta, score))

    # Sort by richness score
    rich_entries.sort(key=lambda x: x[2], reverse=True)

    report = "## Sample Rich Entries\n\n"
    report += "These entries have extensive metadata (multiple sources, labels, glosses, etc.)\n\n"

    for word, meta, score in rich_entries[:10]:
        report += f"### `{word}` (richness: {score})\n\n"
        report += "```json\n"
        report += json.dumps(meta, indent=2, ensure_ascii=False, sort_keys=True)
        report += "\n```\n\n"

    return report


def _is_contraction_fragment(word: str) -> bool:
    """Check if word is a contraction fragment (not a standalone word).

    Matches the logic from frequency_tiers.py.
    """
    return word.startswith("'") or word.endswith("'")


def analyze_unmatched_frequency_entries(metadata: Dict[str, Any], language: str = 'en') -> str:
    """Analyze frequency entries that don't result in tier assignments.

    This helps explain discrepancies like tier A having 18 words instead of 20,
    because some high-frequency entries (like `'t` from `don't`) are contraction
    fragments that are skipped during tier assignment.

    An entry is "unmatched" if:
    1. It's a contraction fragment (filtered out by frequency_tiers.py), OR
    2. It doesn't match any lexeme in the dataset
    """
    import unicodedata

    # Load frequency data
    freq_file = Path(f'data/raw/{language}/{language}_50k.txt')
    if not freq_file.exists():
        return ""

    # Build set of normalized lexeme words
    lexeme_words = set()
    for word in metadata.keys():
        normalized = unicodedata.normalize('NFKC', word.lower())
        lexeme_words.add(normalized)

    # Find unmatched frequency entries
    unmatched = []

    with open(freq_file, 'r', encoding='utf-8') as f:
        for rank, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            parts = line.split()
            if not parts:
                continue

            word = parts[0]
            freq = int(parts[1]) if len(parts) > 1 else 0
            normalized = unicodedata.normalize('NFKC', word.lower())

            # Check if this entry is skipped during tier assignment
            is_contraction = _is_contraction_fragment(normalized)
            is_missing_lexeme = normalized not in lexeme_words

            if is_contraction or is_missing_lexeme:
                reason = "contraction" if is_contraction else "no lexeme"
                unmatched.append((rank, word, freq, reason))

            # Stop after checking enough to get 100 unmatched
            if len(unmatched) >= 100:
                break

    if not unmatched:
        return ""

    report = "## Unmatched Frequency Entries\n\n"
    report += "These entries appear in the frequency data but do not result in tier assignments.\n"
    report += "This explains discrepancies like tier A having 18 words instead of 20.\n\n"
    report += "Entries are excluded from tier assignment when:\n"
    report += "- **Contraction fragments:** `'t` (from `don't`), `'s` (from `it's`), `'ll`, `'re`, etc.\n"
    report += "- **No matching lexeme:** The word doesn't exist in the lexicon\n\n"

    report += "### First 100 Excluded Entries (by frequency rank)\n\n"
    report += "| Rank | Word | Frequency Count | Reason |\n"
    report += "|-----:|------|----------------:|--------|\n"

    for rank, word, freq, reason in unmatched:
        # Escape pipe characters in words for markdown table
        word_escaped = word.replace('|', '\\|')
        report += f"| {rank} | `{word_escaped}` | {freq:,} | {reason} |\n"

    report += "\n"

    return report


def generate_report(language: str = 'en'):
    """Generate comprehensive metadata analysis report for a language."""
    # Try new lexemes-enriched format first (flat structure with language-prefixed files)
    meta_path = Path(f'data/intermediate/{language}-lexemes-enriched.jsonl')
    if not meta_path.exists():
        meta_path = Path(f'data/build/{language}.meta.json')

    # Load senses file for POS and label data (two-file format)
    senses_path = Path(f'data/intermediate/{language}-senses.jsonl')

    # Load metadata first to set reproducible seed based on data
    metadata = load_metadata(meta_path)

    # Load and merge senses data for POS and labels
    if senses_path.exists():
        senses = load_senses(senses_path)
        metadata = merge_lexemes_and_senses(metadata, senses)
        print(f"Merged {len(senses):,} senses entries")

    # Set seed based on metadata size for reproducibility that changes with data
    # This makes sampling reproducible but updates when data significantly changes
    if metadata:
        random.seed(len(metadata))
    else:
        random.seed(42)  # Fallback for empty metadata

    report = f"# Comprehensive Metadata Analysis Report ({language.upper()})\n\n"
    report += f"Generated by `tools/analyze_metadata.py`\n\n"
    report += "This consolidated report analyzes metadata coverage, quality, and filtering capabilities.\n\n"
    report += "**Consolidates:**\n"
    report += "- General metadata exploration (formerly `inspect_metadata.py`)\n"
    report += "- Game-specific filtering analysis (formerly `analyze_game_metadata.py`)\n"
    report += "- Label coverage analysis (formerly `report_label_statistics_built.py`)\n\n"
    report += "---\n\n"

    if not metadata:
        report += f"## Error\n\nMetadata not found at `{meta_path}`\n"
        report += f"Run `make build-{language}` first.\n"
    else:
        report += f"**Total entries:** {len(metadata):,}\n\n"
        report += "---\n\n"

        # Frequency analysis
        freq_report, freq_stats = analyze_frequency_tiers(metadata)
        report += freq_report

        # Unmatched frequency entries (explains tier discrepancies)
        unmatched_report = analyze_unmatched_frequency_entries(metadata, language)
        if unmatched_report:
            report += unmatched_report

        report += "---\n\n"

        # Source distribution
        report += analyze_sources(metadata)
        report += "---\n\n"

        # Label analysis
        label_report, label_stats = analyze_labels(metadata)
        report += label_report
        report += "---\n\n"

        # Game metadata analysis
        game_report, game_stats = analyze_game_metadata(metadata)
        report += game_report
        report += "---\n\n"

        # Sense-based format analysis
        report += analyze_sense_based_format(metadata)
        report += "---\n\n"

        # Filtering recommendations
        report += generate_filtering_recommendations(label_stats, game_stats)
        report += "---\n\n"

        # Representative samples by source
        report += sample_entries_by_source(metadata)
        report += "---\n\n"

        # Sample rich entries
        report += sample_rich_entries(metadata)

    # Write report
    output_path = Path(f'reports/metadata_analysis_{language}.md')
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"Comprehensive metadata analysis report ({language}) written to {output_path}")
    return output_path


if __name__ == '__main__':
    import sys

    language = sys.argv[1] if len(sys.argv) > 1 else 'en'

    print(f"Generating report for language: {language}")
    generate_report(language)
