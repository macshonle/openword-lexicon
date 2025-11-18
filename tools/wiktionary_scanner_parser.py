#!/usr/bin/env python3
"""
wiktionary_scanner_parser.py - Lightweight scanner-based Wiktionary parser

Uses simple string scanning to find <page> boundaries instead of full XML
parsing. Much faster than ET.iterparse() for predictable MediaWiki format.

No XML validation, no DOM building, no namespace overhead - just fast
extraction of the data we need.

Usage:
    python wiktionary_scanner_parser.py INPUT.xml.bz2 OUTPUT.jsonl [--limit N]
"""

import bz2
import json
import re
import sys
import time
import unicodedata as ud
from pathlib import Path
from typing import Dict, List, Set, Optional
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box


class BZ2StreamReader:
    """Streaming BZ2 decompressor with progress feedback."""

    def __init__(self, filepath: Path, chunk_size: int = 256 * 1024, metrics: Optional[Dict] = None):
        self.filepath = filepath
        self.chunk_size = chunk_size
        self.file = open(filepath, 'rb')
        self.decompressor = bz2.BZ2Decompressor()
        self.buffer = b''
        self.total_compressed = 0
        self.total_decompressed = 0
        self.last_progress = 0
        self.start_time = time.time()
        self.metrics = metrics  # Optional metrics dict to update

    def read(self, size: int = -1) -> bytes:
        """Read decompressed data."""
        if size == -1:
            while not self.decompressor.eof:
                self._decompress_chunk()
            result = self.buffer
            self.buffer = b''
            return result

        while len(self.buffer) < size and not self.decompressor.eof:
            self._decompress_chunk()

        result = self.buffer[:size]
        self.buffer = self.buffer[size:]
        return result

    def _decompress_chunk(self):
        """Decompress one chunk and update progress."""
        if self.decompressor.eof:
            return

        compressed = self.file.read(self.chunk_size)
        if not compressed:
            return

        self.total_compressed += len(compressed)
        decompressed = self.decompressor.decompress(compressed)
        self.buffer += decompressed
        self.total_decompressed += len(decompressed)

        # Update metrics if provided
        if self.metrics is not None:
            elapsed = time.time() - self.start_time
            rate_mb = (self.total_decompressed / (1024 * 1024)) / elapsed if elapsed > 0 else 0
            self.metrics["Decomp MB"] = int(self.total_decompressed / (1024 * 1024))
            self.metrics["Decomp Rate"] = rate_mb

    def close(self):
        self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


# Regex patterns for extraction
ENGLISH_SECTION = re.compile(r'==\s*English\s*==', re.IGNORECASE)
LANGUAGE_SECTION = re.compile(r'^==\s*([^=]+?)\s*==$', re.MULTILINE)
POS_HEADER = re.compile(r'^===+\s*(.+?)\s*===+\s*$', re.MULTILINE)  # Already flexible with \s*
# Fallback: extract POS from {{head|en|POS}} templates when section headers missing
HEAD_TEMPLATE = re.compile(r'\{\{(?:head|en-head|head-lite)\|en\|([^}|]+)', re.IGNORECASE)
# Extract POS from {{en-POS}} templates (e.g., {{en-noun}}, {{en-verb}}, {{en-prop}})
EN_POS_TEMPLATE = re.compile(r'\{\{en-(noun|verb|adj|adv|prop|pron)\b', re.IGNORECASE)
# Check for abbreviation templates
ABBREVIATION_TEMPLATE = re.compile(r'\{\{(?:abbreviation of|abbrev of|abbr of|initialism of)\|en\|', re.IGNORECASE)
# Definition-generating templates that indicate English content (even without POS headers)
# These are quaternary validation signals for entries that have definitions but no POS headers
DEFINITION_TEMPLATES = re.compile(r'\{\{(?:' +
    r'abbr of|abbreviation of|abbrev of|initialism of|acronym of|' +
    r'alternative form of|alt form|alt sp|' +
    r'plural of|' +
    r'past tense of|past participle of|' +
    r'present participle of|' +
    r'en-(?:noun|verb|adj|adv|past of)' +
    r')\|en\|', re.IGNORECASE)
# Special template patterns for specific POS types
PREP_PHRASE_TEMPLATE = re.compile(r'\{\{en-prepphr\b', re.IGNORECASE)
CONTEXT_LABEL = re.compile(r'\{\{(?:lb|label|context)\|en\|([^}]+)\}\}', re.IGNORECASE)
CATEGORY = re.compile(r'\[\[Category:English\s+([^\]]+)\]\]', re.IGNORECASE)
DICT_ONLY = re.compile(r'\{\{no entry\|en', re.IGNORECASE)  # Matches both {{no entry|en}} and {{no entry|en|...}}
# Extract hyphenation data for syllable counts (English-specific via |en| param)
HYPHENATION_TEMPLATE = re.compile(r'\{\{(?:hyphenation|hyph)\|en\|([^}]+)\}\}', re.IGNORECASE)
# Extract syllable count from rhymes template: {{rhymes|en|...|s=N}}
RHYMES_SYLLABLE = re.compile(r'\{\{rhymes\|en\|[^}]*\|s=(\d+)', re.IGNORECASE)
# Extract syllable count from category labels (e.g., "Category:English 3-syllable words")
SYLLABLE_CATEGORY = re.compile(r'\[\[Category:English\s+(\d+)-syllable\s+words?\]\]', re.IGNORECASE)

# Etymology section extraction (for morphology analysis)
ETYMOLOGY_SECTION = re.compile(r'===+\s*Etymology\s*\d*\s*===+\s*\n(.+?)(?=\n===|\Z)', re.DOTALL | re.IGNORECASE)
# Morphology templates for derivation tracking
SUFFIX_TEMPLATE = re.compile(r'\{\{suffix\|en\|([^}|]+)\|([^}|]+)(?:\|([^}|]+))?\}\}', re.IGNORECASE)
PREFIX_TEMPLATE = re.compile(r'\{\{prefix\|en\|([^}|]+)\|([^}|]+)(?:\|([^}|]+))?\}\}', re.IGNORECASE)
AFFIX_TEMPLATE = re.compile(r'\{\{affix\|en\|([^}]+)\}\}', re.IGNORECASE)
COMPOUND_TEMPLATE = re.compile(r'\{\{compound\|en\|([^}]+)\}\}', re.IGNORECASE)
# Surface form template (alternative to affix template)
SURF_TEMPLATE = re.compile(r'\{\{surf\|en\|([^}]+)\}\}', re.IGNORECASE)
# Confix template (prefix + base + suffix together)
CONFIX_TEMPLATE = re.compile(r'\{\{confix\|en\|([^}|]+)\|([^}|]+)\|([^}|]+)(?:\|([^}|]+))?\}\}', re.IGNORECASE)

# Known language codes for hyphenation templates
# This whitelist prevents false positives when filtering language codes from syllable segments
KNOWN_LANG_CODES = {
    # Major languages
    'en', 'da', 'de', 'es', 'fr', 'it', 'pt', 'nl', 'sv', 'no', 'fi',
    'pl', 'cs', 'sk', 'hu', 'ro', 'bg', 'ru', 'uk', 'el', 'tr', 'ar',
    'he', 'hi', 'bn', 'pa', 'ta', 'te', 'mr', 'gu', 'kn', 'ml', 'si',
    'th', 'vi', 'zh', 'ja', 'ko', 'id', 'ms', 'tl', 'fa', 'ur',
    # English variants
    'en-US', 'en-GB', 'en-AU', 'en-CA', 'en-NZ', 'en-ZA', 'en-IE', 'en-IN',
    # Other common codes
    'la', 'sa', 'grc', 'ang', 'enm', 'fro', 'non',
}

# Simple extraction patterns (no full XML parsing)
TITLE_PATTERN = re.compile(r'<title>([^<]+)</title>')
NS_PATTERN = re.compile(r'<ns>(\d+)</ns>')
TEXT_PATTERN = re.compile(r'<text[^>]*>(.+?)</text>', re.DOTALL)
REDIRECT_PATTERN = re.compile(r'<redirect\s+title="[^"]+"')

# Known special page prefixes (build this list as we discover them)
SPECIAL_PAGE_PREFIXES = (
    'Wiktionary:',
    'MediaWiki:',       # MediaWiki system messages
    'Module:',          # Lua modules
    'Thread:',          # Discussion threads (e.g., Thread:User talk:)
    'Appendix:',
    'Help:',
    'Template:',
    'Reconstruction:',  # Proto-language reconstructions
    'Unsupported titles/',  # Special namespace for unsupported page titles
    'Category:',        # Category pages (metadata, not words)
)

# Regional label patterns
REGION_LABELS = {
    'british': 'en-GB',
    'uk': 'en-GB',
    'us': 'en-US',
    'american': 'en-US',
    'canadian': 'en-CA',
    'australia': 'en-AU',
    'australian': 'en-AU',
    'new zealand': 'en-NZ',
    'ireland': 'en-IE',
    'irish': 'en-IE',
    'south africa': 'en-ZA',
    'india': 'en-IN',
    'indian': 'en-IN',
}

# POS mapping
POS_MAP = {
    'noun': 'noun',
    'proper noun': 'noun',
    'proper name': 'noun',             # Alternative form of proper noun
    'propernoun': 'noun',              # Proper noun without space (typo in some entries)
    'verb': 'verb',
    'verb form': 'verb',               # Verb inflections
    'participle': 'verb',              # Participles treated as verb forms
    'adjective': 'adjective',
    'adverb': 'adverb',
    'pronoun': 'pronoun',
    'preposition': 'preposition',
    'conjunction': 'conjunction',
    'interjection': 'interjection',
    'determiner': 'determiner',
    'article': 'article',              # Articles (a, an, the, yͤ, t3h)
    'particle': 'particle',
    'auxiliary': 'auxiliary',
    'contraction': 'verb',
    'prefix': 'affix',
    'suffix': 'affix',
    'infix': 'affix',                  # Infixes like -bloody- (inserted inside words)
    'circumfix': 'affix',              # Circumfixes like en- -en (surround the root)
    'interfix': 'affix',               # Interfixes like -s- (connect morphemes)
    'phrase': 'phrase',                # Multi-word expressions
    'prepositional phrase': 'phrase',  # Prepositional phrases (e.g., "at least", "on hold")
    'adverbial phrase': 'phrase',      # Adverbial phrases (e.g., "on all fours")
    'verb phrase': 'phrase',           # Verb phrases (multi-word verb expressions)
    'verb phrase form': 'phrase',      # Inflected verb phrases
    'idiom': 'phrase',                 # Idiomatic expressions (e.g., "maximum attack")
    'proverb': 'phrase',               # Proverbs treated as phrases
    'numeral': 'numeral',              # Numbers (thirteen, centillion, etc.)
    'symbol': 'symbol',                # Symbols (chemical elements, abbreviations, etc.)
    'symbols': 'symbol',               # Plural form (from {{head-lite|en|symbols}})
    'letter': 'letter',                # Letters (ſ, þ, Þ, etc. - archaic/special Latin letters)
    'multiple parts of speech': 'multiple',  # Entries with multiple POS (stenoscript)
}

# Label classifications
REGISTER_LABELS = {
    'informal', 'colloquial', 'slang', 'vulgar', 'offensive',
    'derogatory', 'formal', 'euphemistic', 'humorous', 'literary'
}

TEMPORAL_LABELS = {
    'archaic', 'obsolete', 'dated', 'historical', 'rare'
}

DOMAIN_LABELS = {
    'computing', 'mathematics', 'medicine', 'biology', 'chemistry',
    'physics', 'law', 'military', 'nautical', 'aviation', 'sports'
}


def extract_english_section(text: str) -> Optional[str]:
    """
    Extract ONLY the ==English== section from a Wiktionary page.

    This prevents contamination from other language sections (French, Translingual, etc.)
    which could have different POS headers, templates, and categories.

    Returns the English section text, or None if no English section found.
    """
    # Find the start of the English section
    english_match = ENGLISH_SECTION.search(text)
    if not english_match:
        return None

    english_start = english_match.end()

    # Find the start of the next language section (or end of text)
    # Language sections are marked with == (level 2 headers)
    next_section = None
    for match in LANGUAGE_SECTION.finditer(text, english_start):
        lang = match.group(1).strip()
        if lang.lower() != 'english':
            next_section = match.start()
            break

    # Extract English section only
    if next_section:
        return text[english_start:next_section]
    else:
        return text[english_start:]


def extract_pos_tags(text: str) -> List[str]:
    """Extract POS tags from section headers and {{head}} templates."""
    pos_tags = []

    # Primary: Extract from section headers (===Noun===, etc.)
    for match in POS_HEADER.finditer(text):
        header = match.group(1).lower().strip()
        # Normalize whitespace (handle "Proper  noun" with double spaces)
        header = ' '.join(header.split())
        if header in POS_MAP:
            pos_tags.append(POS_MAP[header])

    # Fallback: If no section headers found, try {{head|en|POS}} templates
    if not pos_tags:
        for match in HEAD_TEMPLATE.finditer(text):
            pos = match.group(1).lower().strip()
            if pos in POS_MAP:
                pos_tags.append(POS_MAP[pos])
            # Handle special cases
            elif pos == 'phrase':
                pos_tags.append('phrase')
            elif pos == 'proverb':
                pos_tags.append('phrase')
            elif pos == 'numeral':
                pos_tags.append('numeral')

    # Additional fallback: Check for {{en-POS}} templates (e.g., {{en-noun}})
    if not pos_tags:
        for match in EN_POS_TEMPLATE.finditer(text):
            pos = match.group(1).lower()
            # Map abbreviated forms
            pos_mapping = {
                'noun': 'noun',
                'verb': 'verb',
                'adj': 'adjective',
                'adv': 'adverb',
                'prop': 'noun',  # {{en-prop}} is for proper nouns
                'pron': 'pronoun',
            }
            if pos in pos_mapping:
                pos_tags.append(pos_mapping[pos])

    # Additional fallback: Check for prepositional phrase template or category
    if not pos_tags:
        if PREP_PHRASE_TEMPLATE.search(text):
            pos_tags.append('phrase')
        elif 'Category:English prepositional phrases' in text:
            pos_tags.append('phrase')

    # Final fallback: Check for stenoscript abbreviations (no POS headers)
    # These have {{abbreviation of|en|...}} and Category:English Stenoscript abbreviations
    if not pos_tags:
        if ABBREVIATION_TEMPLATE.search(text) or 'Category:English Stenoscript abbreviations' in text:
            pos_tags.append('symbol')

    return sorted(set(pos_tags))


def extract_labels(text: str) -> Dict[str, List[str]]:
    """Extract context labels from templates and categorize them."""
    labels = {
        'register': set(),
        'temporal': set(),
        'domain': set(),
        'region': set(),
        'categories': set(),  # NEW: Track all categories (including prefixes/suffixes)
    }

    # Extract from {{lb|en|...}} templates
    for match in CONTEXT_LABEL.finditer(text):
        label_text = match.group(1)
        for label in label_text.split('|'):
            label = label.strip().lower()

            if label in REGISTER_LABELS:
                labels['register'].add(label)
            elif label in TEMPORAL_LABELS:
                labels['temporal'].add(label)
            elif label in DOMAIN_LABELS:
                labels['domain'].add(label)
            elif label in REGION_LABELS:
                labels['region'].add(REGION_LABELS[label])

    # Extract from categories
    for match in CATEGORY.finditer(text):
        cat = match.group(1)  # Keep original case for categories
        cat_lower = cat.lower()

        # Store the category itself
        labels['categories'].add(cat)

        if 'informal' in cat_lower or 'colloquial' in cat_lower:
            labels['register'].add('informal')
        if 'slang' in cat_lower:
            labels['register'].add('slang')
        if 'vulgar' in cat_lower:
            labels['register'].add('vulgar')
        if 'offensive' in cat_lower or 'derogatory' in cat_lower:
            labels['register'].add('offensive')
        if 'obsolete' in cat_lower:
            labels['temporal'].add('obsolete')
        if 'archaic' in cat_lower:
            labels['temporal'].add('archaic')

        for region_key, region_code in REGION_LABELS.items():
            if region_key in cat_lower:
                labels['region'].add(region_code)
                break

    return {k: sorted(v) for k, v in labels.items() if v}


def extract_syllable_count_from_hyphenation(text: str, word: str) -> Optional[int]:
    """
    Extract syllable count from {{hyphenation|...}} template.

    Uses multiple strategies to avoid false positives:
    1. Whitelist of known language codes (KNOWN_LANG_CODES)
    2. Context-aware detection (don't filter if it matches the word being processed)
    3. Only count properly separated syllable segments

    Args:
        text: The Wiktionary page text
        word: The word being processed (for context-aware filtering)

    Returns:
        Number of syllables if reliably determined, None otherwise

    Handles complex formats:
    - Language codes: {{hyphenation|en|dic|tion|a|ry}} -> 4 syllables
    - Alternatives: {{hyphenation|en|dic|tion|a|ry||dic|tion|ary}} -> 4 (uses first)
    - Parameters: {{hyphenation|en|lang=en-US|dic|tion|a|ry}} -> 4
    - Without lang code: {{hyphenation|art}} -> 1 syllable

    Returns None for unreliable cases:
    - {{hyphenation|arad}} -> None (unseparated, data quality issue)
    - {{hyphenation|}} -> None (empty)
    """
    match = HYPHENATION_TEMPLATE.search(text)
    if not match:
        return None

    content = match.group(1)

    # Handle alternatives (||) - use first alternative
    alternatives = content.split('||')
    first_alt = alternatives[0] if alternatives else content

    # Parse pipe-separated segments
    parts = first_alt.split('|')

    # Filter syllables (exclude lang codes, parameters, empty)
    syllables = []
    for i, part in enumerate(parts):
        part = part.strip()

        # Skip empty
        if not part:
            continue

        # Skip parameter assignments (lang=, caption=, etc.)
        if '=' in part:
            continue

        # Skip known language codes at position 0
        # Use whitelist for reliability + context-awareness
        if i == 0:
            # Check if it's a known language code (not the word itself)
            if part in KNOWN_LANG_CODES and part.lower() != word.lower():
                continue

            # If there's only one part and it's unseparated (>3 chars), it's likely
            # incomplete data (e.g., {{hyphenation|arad}} should be {{hyphenation|a|rad}})
            # We only trust single-part templates for very short words (1-3 chars)
            # Return None to indicate unreliable data for longer unseparated words
            if len(parts) == 1 and len(part) > 3:
                return None

        syllables.append(part)

    # Return syllable count if we found any syllables
    return len(syllables) if syllables else None


def extract_syllable_count_from_rhymes(text: str) -> Optional[int]:
    """
    Extract syllable count from {{rhymes|en|...|s=N}} template.

    The rhymes template often includes a syllable count parameter.
    Example: {{rhymes|en|eɪθs|s=1}} indicates 1 syllable.

    Returns syllable count if found, None otherwise.
    """
    match = RHYMES_SYLLABLE.search(text)
    if match:
        return int(match.group(1))
    return None


def extract_syllable_count_from_categories(text: str) -> Optional[int]:
    """
    Extract syllable count from category labels as a fallback signal.

    Example: [[Category:English 3-syllable words]] -> 3

    Note: These categories are deprecated in Wiktionary but can still provide
    a useful signal when hyphenation templates are missing.

    Args:
        text: The Wiktionary page text

    Returns:
        Number of syllables from category label, or None if not found
    """
    match = SYLLABLE_CATEGORY.search(text)
    if match:
        return int(match.group(1))
    return None


def extract_morphology(text: str) -> Optional[Dict]:
    """
    Extract morphological structure from Wiktionary etymology sections.

    Parses etymology templates to identify derivation relationships and compound structures.
    Handles suffix, prefix, affix, compound, surf, and confix templates.

    Templates parsed:
    - {{suffix|en|happy|ness}} -> happiness = happy + -ness
    - {{prefix|en|un|happy}} -> unhappy = un- + happy
    - {{affix|en|un-|break|-able}} -> unbreakable = un- + break + -able
    - {{compound|en|bar|tender}} -> bartender = bar + tender
    - {{surf|en|dict|ion|ary}} -> dictionary = dict + ion + ary (surface form)
    - {{confix|en|en-|light|ment}} -> enlightenment = en- + light + -ment

    Args:
        text: The English section of Wiktionary page text

    Returns:
        Dictionary with morphology structure, or None if no etymology data found.
        Structure:
        {
            'type': 'suffixed' | 'prefixed' | 'affixed' | 'compound' | 'circumfixed',
            'base': str (base word, optional for compounds),
            'components': [str] (all morphological parts in order),
            'prefixes': [str] (prefix morphemes with trailing hyphen),
            'suffixes': [str] (suffix morphemes with leading hyphen),
            'is_compound': bool,
            'etymology_template': str (raw template for reference)
        }
    """
    # Try to find etymology section
    etym_match = ETYMOLOGY_SECTION.search(text)
    if not etym_match:
        return None

    etymology_text = etym_match.group(1)

    # Try each template type in priority order

    # 1. Check for suffix template: {{suffix|en|base|suffix}}
    suffix_match = SUFFIX_TEMPLATE.search(etymology_text)
    if suffix_match:
        base = suffix_match.group(1).strip()
        suffix = suffix_match.group(2).strip()

        # Normalize suffix format (add leading hyphen if missing)
        if not suffix.startswith('-'):
            suffix = f'-{suffix}'

        return {
            'type': 'suffixed',
            'base': base,
            'components': [base, suffix],
            'prefixes': [],
            'suffixes': [suffix],
            'is_compound': False,
            'etymology_template': suffix_match.group(0)
        }

    # 2. Check for prefix template: {{prefix|en|prefix|base}}
    prefix_match = PREFIX_TEMPLATE.search(etymology_text)
    if prefix_match:
        prefix = prefix_match.group(1).strip()
        base = prefix_match.group(2).strip()

        # Normalize prefix format (add trailing hyphen if missing)
        if not prefix.endswith('-'):
            prefix = f'{prefix}-'

        return {
            'type': 'prefixed',
            'base': base,
            'components': [prefix, base],
            'prefixes': [prefix],
            'suffixes': [],
            'is_compound': False,
            'etymology_template': prefix_match.group(0)
        }

    # 3. Check for confix template: {{confix|en|prefix|base|suffix}}
    confix_match = CONFIX_TEMPLATE.search(etymology_text)
    if confix_match:
        prefix = confix_match.group(1).strip()
        base = confix_match.group(2).strip()
        suffix = confix_match.group(3).strip()

        # Normalize affix formats
        if not prefix.endswith('-'):
            prefix = f'{prefix}-'
        if not suffix.startswith('-'):
            suffix = f'-{suffix}'

        return {
            'type': 'circumfixed',
            'base': base,
            'components': [prefix, base, suffix],
            'prefixes': [prefix],
            'suffixes': [suffix],
            'is_compound': False,
            'etymology_template': confix_match.group(0)
        }

    # 4. Check for compound template: {{compound|en|word1|word2|...}}
    compound_match = COMPOUND_TEMPLATE.search(etymology_text)
    if compound_match:
        # Split on | and get all components after 'en'
        parts = [p.strip() for p in compound_match.group(1).split('|')]
        # Filter out alt=, t=, gloss= parameters
        components = [p for p in parts if not ('=' in p)]

        if len(components) >= 2:
            return {
                'type': 'compound',
                'components': components,
                'prefixes': [],
                'suffixes': [],
                'is_compound': True,
                'etymology_template': compound_match.group(0)
            }

    # 5. Check for affix template: {{affix|en|part1|part2|...}}
    affix_match = AFFIX_TEMPLATE.search(etymology_text)
    if affix_match:
        # Split on | and parse components
        parts = [p.strip() for p in affix_match.group(1).split('|')]
        # Filter out parameters with = (like alt=, t=, etc.)
        components = [p for p in parts if not ('=' in p)]

        if len(components) >= 2:
            # Analyze components to determine type
            prefixes = []
            suffixes = []
            base = None

            for comp in components:
                if comp.endswith('-') and not comp.startswith('-'):
                    # Prefix (has trailing hyphen, no leading hyphen)
                    prefixes.append(comp)
                elif comp.startswith('-') and not comp.endswith('-'):
                    # Suffix (has leading hyphen, no trailing hyphen)
                    suffixes.append(comp)
                elif comp.startswith('-') and comp.endswith('-'):
                    # Interfix or special case (both hyphens)
                    # For now, treat as base
                    if base is None:
                        base = comp
                else:
                    # No hyphens - this is the base
                    if base is None:
                        base = comp

            # Determine morphology type
            if prefixes and suffixes:
                morph_type = 'affixed'
            elif prefixes:
                morph_type = 'prefixed'
            elif suffixes:
                morph_type = 'suffixed'
            else:
                # All components are bases (compound)
                morph_type = 'compound'

            result = {
                'type': morph_type,
                'components': components,
                'prefixes': prefixes,
                'suffixes': suffixes,
                'is_compound': (morph_type == 'compound'),
                'etymology_template': affix_match.group(0)
            }

            # Add base if identified
            if base:
                result['base'] = base

            return result

    # 6. Check for surf template: {{surf|en|part1|part2|...}}
    surf_match = SURF_TEMPLATE.search(etymology_text)
    if surf_match:
        # Similar to affix template but more lenient
        parts = [p.strip() for p in surf_match.group(1).split('|')]
        components = [p for p in parts if not ('=' in p)]

        if len(components) >= 2:
            # Analyze components similar to affix
            prefixes = [c for c in components if c.endswith('-') and not c.startswith('-')]
            suffixes = [c for c in components if c.startswith('-') and not c.endswith('-')]
            bases = [c for c in components if not c.startswith('-') and not c.endswith('-')]

            # Determine type
            if prefixes and suffixes:
                morph_type = 'affixed'
                base = bases[0] if bases else None
            elif prefixes:
                morph_type = 'prefixed'
                base = bases[0] if bases else None
            elif suffixes:
                morph_type = 'suffixed'
                base = bases[0] if bases else None
            else:
                morph_type = 'compound'
                base = None

            result = {
                'type': morph_type,
                'components': components,
                'prefixes': prefixes,
                'suffixes': suffixes,
                'is_compound': (morph_type == 'compound'),
                'etymology_template': surf_match.group(0)
            }

            if base:
                result['base'] = base

            return result

    return None


def extract_page_content(page_xml: str) -> Optional[tuple]:
    """
    Extract title and text from page XML using simple regex.
    Returns (title, text) or None if not found.
    Special pages (known prefixes) return ('SPECIAL_PAGE', title) even if redirects.
    Redirects return ('REDIRECT', title).
    Dictionary-only terms return ('DICT_ONLY', title, text).
    Non-English pages return ('NON_ENGLISH', title, languages) where languages is a list.
    """
    # Extract title
    title_match = TITLE_PATTERN.search(page_xml)
    if not title_match:
        return None
    title = title_match.group(1)

    # Check namespace FIRST - only process main namespace (ns=0)
    # This is the authoritative way to filter special pages
    # ns=0: Main (dictionary entries)
    # ns=14: Category
    # ns=100: Appendix
    # ns=118: Reconstruction
    # All other namespaces should be filtered out
    ns_match = NS_PATTERN.search(page_xml)
    if ns_match:
        namespace = int(ns_match.group(1))
        if namespace != 0:
            return ('SPECIAL_PAGE', title)

    # Check for special pages by title prefix (backup for entries without ns tag)
    # Special page redirects count as special pages, not redirects
    if title.startswith(SPECIAL_PAGE_PREFIXES):
        return ('SPECIAL_PAGE', title)

    # Filter translation subpages (e.g., "an/translations", "the/translations")
    # These are meta-pages that contain only translation data, not word definitions
    if '/translations' in title or '/Translations' in title:
        return ('SPECIAL_PAGE', title)

    # Check for redirects AFTER special pages
    # This catches regular redirects like "grain of salt" -> "with a grain of salt"
    if REDIRECT_PATTERN.search(page_xml):
        return ('REDIRECT', title)

    # Extract text
    text_match = TEXT_PATTERN.search(page_xml)
    if not text_match:
        return None
    text = text_match.group(1)

    # Check for English section
    has_english = ENGLISH_SECTION.search(text)

    # Check for dictionary-only terms ({{no entry|en|...)
    if has_english and DICT_ONLY.search(text):
        return ('DICT_ONLY', title, text)

    # If no English section, extract languages present
    if not has_english:
        languages = []
        for match in LANGUAGE_SECTION.finditer(text):
            lang = match.group(1).strip()
            if lang.lower() != 'english':
                languages.append(lang)
        return ('NON_ENGLISH', title, languages)

    return (title, text)


def is_englishlike(token: str) -> bool:
    """
    Returns True if `token` looks like an English-language word or phrase:
    - Uses Latin letters (with optional combining diacritics)
    - May include ASCII spaces between parts
    - May include hyphen (U+002D), en dash (U+2013),
      straight apostrophe (U+0027), left single quote (U+2018),
      right single quote (U+2019), period (U+002E),
      and slash (U+002F)
    - Rejects any string of only spaces, any non-ASCII whitespace,
      and any obvious HTML-entity-like token (&, ;, <, >)
    """

    t = ud.normalize("NFC", token)

    # Reject non-ASCII whitespace except ordinary space U+0020
    if any(ch != ' ' and ud.category(ch).startswith('Z') for ch in t):
        return False

    # Reject strings that are empty or only spaces
    if t.strip(' ') == '':
        return False

    ALLOWED_PUNCT = {"'", "’", "‘", "-", "–", ".", "/"}
    FORBIDDEN = set("&;<>")

    saw_latin_letter = False
    prev_base_is_latin = False  # for validating combining marks

    for ch in t:
        if ch == ' ':
            prev_base_is_latin = False
            continue

        if ch in FORBIDDEN:
            return False

        cat = ud.category(ch)

        if cat.startswith('M'):
            # combining mark must follow a Latin base
            if not prev_base_is_latin:
                return False
            continue

        if cat.startswith('L'):
            # require Latin letters
            if "LATIN" not in ud.name(ch, ""):
                return False
            saw_latin_letter = True
            prev_base_is_latin = True
            continue

        if cat.startswith('N'):
            # allow numbers
            prev_base_is_latin = False
            continue

        if ch in ALLOWED_PUNCT:
            prev_base_is_latin = False
            continue

        # anything else disallowed
        return False

    return saw_latin_letter


def extract_phrase_type(text: str) -> Optional[str]:
    """
    Extract specific phrase type before POS normalization.

    Returns the specific type (idiom, proverb, etc.) or None if not a phrase.
    This preserves granularity lost during POS_MAP normalization.

    Distinction criteria:
    - **Word**: word_count == 1 (handled elsewhere)
    - **Idiom**: Non-literal figurative expression ("kick the bucket")
    - **Proverb**: Complete sentence with advice/wisdom ("a stitch in time saves nine")
    - **Phrase**: Generic multi-word without specific type
    - **Prepositional phrase**: Starts with preposition ("at least", "on hold")
    - **Adverbial phrase**: Functions as adverb ("all of a sudden")
    - **Verb phrase**: Multi-word verb expression ("give up", "take over")

    Detection methods:
    1. Section headers: ===Idiom===, ===Proverb===, etc.
    2. Templates: {{head|en|idiom}}, {{en-prepphr}}
    3. Categories: [[Category:English idioms]], etc.
    """
    # Check section headers for specific phrase types
    for match in POS_HEADER.finditer(text):
        header = match.group(1).lower().strip()
        header = ' '.join(header.split())  # Normalize whitespace

        # Exact matches for phrase types
        if header in ['idiom', 'proverb', 'prepositional phrase', 'adverbial phrase',
                      'verb phrase', 'verb phrase form', 'noun phrase']:
            return header

        # Additional phrase type variations
        if header in ['saying', 'adage']:
            return 'proverb'  # Sayings/adages are proverb-like

    # Check {{head}} templates
    for match in HEAD_TEMPLATE.finditer(text):
        pos = match.group(1).lower().strip()
        if pos in ['idiom', 'proverb', 'prepositional phrase', 'adverbial phrase',
                   'verb phrase', 'noun phrase', 'saying', 'adage']:
            return 'proverb' if pos in ['saying', 'adage'] else pos

    # Check for phrase-specific templates
    if PREP_PHRASE_TEMPLATE.search(text):
        return 'prepositional phrase'

    # Check categories (more comprehensive)
    category_patterns = {
        'Category:English idioms': 'idiom',
        'Category:English proverbs': 'proverb',
        'Category:English prepositional phrases': 'prepositional phrase',
        'Category:English adverbial phrases': 'adverbial phrase',
        'Category:English verb phrases': 'verb phrase',
        'Category:English noun phrases': 'noun phrase',
        'Category:English sayings': 'proverb',
    }

    for pattern, phrase_type in category_patterns.items():
        if pattern in text:
            return phrase_type

    return None


def detect_abbreviation(text: str, pos_tags: List[str]) -> bool:
    """
    Detect if entry is an abbreviation.

    Detection methods:
    1. Templates: {{abbr of|en|...}}, {{abbreviation of|en|...}}, {{initialism of|en|...}}
    2. Categories: Category:English abbreviations, Category:English initialisms
    3. POS: symbol (often abbreviations)

    Examples: USA, Dr., etc., crp (stenoscript)
    """
    # Check templates
    if ABBREVIATION_TEMPLATE.search(text):
        return True

    # Check categories
    if 'Category:English abbreviations' in text:
        return True
    if 'Category:English initialisms' in text:
        return True
    if 'Category:English acronyms' in text:
        return True
    if 'Category:English Stenoscript abbreviations' in text:
        return True

    # Symbol POS is often used for abbreviations
    if 'symbol' in pos_tags:
        return True

    return False


def detect_proper_noun(text: str, pos_tags: List[str]) -> bool:
    """
    Detect if entry is a proper noun (name, place, etc.).

    Detection methods:
    1. POS: proper noun mapped to 'noun' in POS_MAP
    2. Section header: ===Proper noun===
    3. Templates: {{en-proper noun}}, {{en-prop}}

    Examples: London, Shakespeare, Microsoft
    """
    # Check for proper noun section header
    for match in POS_HEADER.finditer(text):
        header = match.group(1).lower().strip()
        header = ' '.join(header.split())
        if header in ['proper noun', 'proper name', 'propernoun']:
            return True

    # Check for proper noun templates
    if re.search(r'\{\{en-(?:proper noun|prop)\b', text, re.IGNORECASE):
        return True

    return False


def detect_vulgar_or_offensive(labels: Dict) -> bool:
    """
    Detect if entry is vulgar or offensive.

    Uses label data already extracted.
    Examples: profanity, slurs, offensive terms
    """
    register = labels.get('register', [])
    return 'vulgar' in register or 'offensive' in register


def detect_archaic_or_obsolete(labels: Dict) -> bool:
    """
    Detect if entry is archaic or obsolete.

    Uses label data already extracted.
    Examples: thou, whence, forsooth
    """
    temporal = labels.get('temporal', [])
    return 'archaic' in temporal or 'obsolete' in temporal


def detect_rare(labels: Dict) -> bool:
    """
    Detect if entry is marked as rare.

    Uses label data already extracted.
    """
    temporal = labels.get('temporal', [])
    return 'rare' in temporal


def detect_informal_or_slang(labels: Dict) -> bool:
    """
    Detect if entry is informal or slang.

    Uses label data already extracted.
    Examples: gonna, wanna, ain't
    """
    register = labels.get('register', [])
    return 'informal' in register or 'slang' in register or 'colloquial' in register


def detect_technical(labels: Dict) -> bool:
    """
    Detect if entry is technical/domain-specific jargon.

    Uses domain labels already extracted.
    Examples: mitochondria (biology), tort (law), algorithm (computing)

    Useful for: Filtering out specialized terminology for general-purpose
    dictionaries vs keeping it for domain-specific applications.
    """
    domain = labels.get('domain', [])
    # Technical if it has ANY domain label (medical, legal, computing, etc.)
    return len(domain) > 0


def detect_regional(labels: Dict) -> bool:
    """
    Detect if entry is region-specific (dialectal).

    Uses region labels already extracted.
    Examples: lift (British), elevator (American), arvo (Australian)

    Useful for: Dictionary localization and dialect-aware applications.
    """
    region = labels.get('region', [])
    return len(region) > 0


def detect_inflected_form(text: str, pos_tags: List[str]) -> bool:
    """
    Detect if entry is an inflected form rather than a base word.

    Detection methods:
    1. Templates: {{plural of|en|...}}, {{past tense of|en|...}}, etc.
    2. POS categories indicating forms: "verb forms", "noun forms", etc.

    Examples: cats (plural of cat), ran (past tense of run), better (comparative of good)

    Useful for: Base-word-only dictionaries, lemmatization, reducing redundancy.
    """
    # Check for inflection templates
    inflection_patterns = [
        r'\{\{plural of\|en\|',
        r'\{\{past tense of\|en\|',
        r'\{\{past participle of\|en\|',
        r'\{\{present participle of\|en\|',
        r'\{\{comparative of\|en\|',
        r'\{\{superlative of\|en\|',
        r'\{\{inflection of\|en\|',
    ]

    for pattern in inflection_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    # Check for form categories
    form_categories = [
        'Category:English verb forms',
        'Category:English noun forms',
        'Category:English adjective forms',
        'Category:English adverb forms',
        'Category:English plurals',
    ]

    for category in form_categories:
        if category in text:
            return True

    return False


def detect_dated(labels: Dict) -> bool:
    """
    Detect if entry is dated (understood but not commonly used).

    Different from archaic - dated words are still understood but old-fashioned.
    Examples: wireless (for radio), icebox (for refrigerator)

    Useful for: More granular temporal filtering than archaic/obsolete.
    """
    temporal = labels.get('temporal', [])
    return 'dated' in temporal


def has_english_categories(text: str) -> bool:
    """
    Check if the text contains English POS categories.

    This validates that a page is actually an English entry, not just a page
    with an English section. Filters out foreign words like 'łódź' that may
    have an English section but no English POS categories.

    Returns True if any English POS categories are found.
    """
    # Common English POS categories
    english_pos_patterns = [
        'Category:English nouns',
        'Category:English verbs',
        'Category:English adjectives',
        'Category:English adverbs',
        'Category:English pronouns',
        'Category:English prepositions',
        'Category:English conjunctions',
        'Category:English interjections',
        'Category:English determiners',
        'Category:English articles',
        'Category:English proper nouns',
        'Category:English idioms',
        'Category:English phrases',
        'Category:English proverbs',
        'Category:English prepositional phrases',
        'Category:English verb forms',
        'Category:English noun forms',
        'Category:English adjective forms',
        'Category:English adverb forms',
        'Category:English contractions',
        'Category:English abbreviations',
    ]

    text_lower = text.lower()
    return any(pattern.lower() in text_lower for pattern in english_pos_patterns)


def parse_entry(title: str, text: str) -> Optional[Dict]:
    """
    Parse a single Wiktionary page.

    Critical: Extracts ONLY the ==English== section before parsing to prevent
    contamination from other language sections (French, Translingual, etc.).

    Uses multiple signals to validate English entries:
    1. Primary: Successful POS extraction (strongest signal)
    2. Secondary: English categories present
    3. Tertiary: English templates ({{en-noun}}, etc.)
    4. Quaternary: Definition-generating templates ({{abbr of|en|...}}, etc.)

    Philosophy: When information is present (POS, labels, etc.), include the entry.
    Only reject if we have NO English signals at all.

    Examples handled:
    - "crp": Has {{abbr of|en|corporate}} but no POS header → included via signal 4
    - Entries with only categories → included via signal 2
    - Entries with en-templates → included via signal 3
    """
    word = title.lower().strip()

    # CRITICAL: Extract ONLY the ==English== section
    # This prevents contamination from other language sections
    english_text = extract_english_section(text)
    if not english_text:
        return None  # No English section found

    # Try to extract POS tags - this is the STRONGEST signal that it's English
    pos_tags = extract_pos_tags(english_text)

    # Check for English categories as a secondary signal
    has_categories = has_english_categories(english_text)

    # Check for English-specific templates as tertiary signal
    has_en_templates = bool(re.search(r'\{\{en-(?:noun|verb|adj|adv)', english_text))

    # Check for definition-generating templates (quaternary signal)
    # Catches entries like "crp" that have {{abbr of|en|...}} but no POS headers
    has_definition_templates = bool(DEFINITION_TEMPLATES.search(english_text))

    # Decision logic: Keep if ANY strong English signal is present
    if not pos_tags and not has_categories and not has_en_templates and not has_definition_templates:
        # No English signals at all - reject
        return None

    # If we have categories/templates but no POS, this might be a minimal entry
    # Keep it but it will have empty POS list
    if not pos_tags and (has_categories or has_en_templates or has_definition_templates):
        # Valid English entry with categories/templates but no extractable POS
        # This can happen with some stub entries, abbreviations, or special formats
        pos_tags = []  # Empty but valid

    labels = extract_labels(english_text)

    # Calculate word count (always track, even for single words)
    word_count = len(word.split())

    # Extract specific phrase type for multi-word entries
    phrase_type = extract_phrase_type(english_text) if word_count > 1 else None

    # Extract syllable count from multiple sources, trying in priority order
    # Only set syllable count when we have reliable data - never guess
    syllable_count = None

    # Priority 1: Hyphenation template (most reliable when properly formatted)
    hyph_count = extract_syllable_count_from_hyphenation(english_text, word)
    if hyph_count is not None:
        syllable_count = hyph_count
    else:
        # Priority 2: Rhymes template (often has syllable count)
        rhymes_count = extract_syllable_count_from_rhymes(english_text)
        if rhymes_count is not None:
            syllable_count = rhymes_count
        else:
            # Priority 3: Category labels (deprecated but sometimes available)
            cat_count = extract_syllable_count_from_categories(english_text)
            if cat_count is not None:
                syllable_count = cat_count

    # Extract morphology from etymology section
    morphology = extract_morphology(english_text)

    # Detect boolean properties for filtering
    is_phrase = word_count > 1
    is_abbreviation = detect_abbreviation(english_text, pos_tags)
    is_proper_noun = detect_proper_noun(english_text, pos_tags)
    is_vulgar = detect_vulgar_or_offensive(labels)
    is_archaic = detect_archaic_or_obsolete(labels)
    is_rare = detect_rare(labels)
    is_informal = detect_informal_or_slang(labels)
    is_technical = detect_technical(labels)
    is_regional = detect_regional(labels)
    is_inflected = detect_inflected_form(english_text, pos_tags)
    is_dated = detect_dated(labels)

    entry = {
        'word': word,
        'pos': pos_tags,
        'labels': labels,
        'word_count': word_count,
        'is_phrase': is_phrase,
        'is_abbreviation': is_abbreviation,
        'is_proper_noun': is_proper_noun,
        'is_vulgar': is_vulgar,
        'is_archaic': is_archaic,
        'is_rare': is_rare,
        'is_informal': is_informal,
        'is_technical': is_technical,
        'is_regional': is_regional,
        'is_inflected': is_inflected,
        'is_dated': is_dated,
        'sources': ['wikt'],
    }

    # Add phrase type for multi-word entries
    if phrase_type:
        entry['phrase_type'] = phrase_type

    # Only include syllable count if reliably determined
    # Leave unspecified (None) if data is missing or unreliable
    if syllable_count is not None:
        entry['syllables'] = syllable_count

    # Add morphology if etymology data was successfully extracted
    if morphology is not None:
        entry['morphology'] = morphology

    return entry


# Layout for status display (label, value) pairs
PAIRS_LAYOUT = [
    # each row contains up to three (label, key) pairs
    [("Processed", "Processed"), ("Written", "Written"), ("Special", "Special")],
    [("Redirects", "Redirects"), ("Dict-only", "Dict-only"), ("Non-EN", "Non-EN")],
    [("Non-Latin", "Non-Latin"), ("Skipped", "Skipped"), ("Rate", "Rate")],
    [("Decomp MB", "Decomp MB"), ("Decomp Rate", "Decomp Rate"), ("Elapsed", "Elapsed")],
]


def fmt(name: str, value) -> str:
    """Format metric value based on field name."""
    if name == "Rate":
        return f"{int(value):>10,} pg/s"
    elif name == "Decomp Rate":
        return f"{value:>10.1f} MB/s"
    elif name == "Elapsed":
        # value is seconds, format as mm:ss or hh:mm:ss
        mins = int(value // 60)
        secs = int(value % 60)
        if mins >= 60:
            hours = mins // 60
            mins = mins % 60
            return f"{hours:>6}h {mins:02}m"
        return f"{mins:>9}m {secs:02}s"
    return f"{value:>10,}"


def make_form(metrics: dict) -> Panel:
    """Create a Rich panel with grid layout for live progress display."""
    grid = Table.grid(padding=(0, 4))
    # six columns: label,value x3
    grid.add_column(justify="left",  no_wrap=True)  # L1
    grid.add_column(justify="right", no_wrap=True)  # V1
    grid.add_column(justify="left",  no_wrap=True)  # L2
    grid.add_column(justify="right", no_wrap=True)  # V2
    grid.add_column(justify="left",  no_wrap=True)  # L3
    grid.add_column(justify="right", no_wrap=True)  # V3

    for row in PAIRS_LAYOUT:
        cells = []
        for label, key in row:
            if label is None:
                cells += ["", ""]
            else:
                cells += [Text(f"{label}:", style="bold grey50"), Text(fmt(label, metrics[key]), style="bright_cyan")]
        grid.add_row(*cells)

    return Panel(grid, title="Status", box=box.SIMPLE, border_style="bright_black")


def scan_pages(file_obj, chunk_size: int = 1024 * 1024):
    """
    Scan for <page> boundaries and yield complete page XML.

    This is much faster than ET.iterparse() because:
    - No XML DOM building
    - No namespace handling
    - No validation
    - Simple string scanning
    """
    buffer = ""
    page_start_marker = "<page>"
    page_end_marker = "</page>"

    while True:
        # Read chunk
        chunk = file_obj.read(chunk_size)
        if not chunk:
            break

        # Decode to string
        try:
            buffer += chunk.decode('utf-8')
        except UnicodeDecodeError:
            buffer += chunk.decode('utf-8', errors='ignore')

        # Find complete pages in buffer
        while True:
            start = buffer.find(page_start_marker)
            if start == -1:
                # No page start found, keep last bit in case it's partial
                buffer = buffer[-len(page_start_marker):]
                break

            end = buffer.find(page_end_marker, start)
            if end == -1:
                # Page incomplete, keep from start
                buffer = buffer[start:]
                break

            # Extract complete page (include closing tag)
            end += len(page_end_marker)
            page_xml = buffer[start:end]
            buffer = buffer[end:]

            yield page_xml


def parse_wiktionary_dump(xml_path: Path, output_path: Path, limit: int = None, diagnostic_file: Optional[Path] = None):
    """Parse Wiktionary XML dump using lightweight scanning."""

    print(f"Parsing: {xml_path}")
    print(f"Output: {output_path}")
    print(f"Method: Lightweight scanner (no full XML parsing)")
    if limit:
        print(f"Limit: {limit:,} entries")
    if diagnostic_file:
        print(f"Diagnostic mode: Will stop after 100 skips and write report to {diagnostic_file}")
    print()

    # Prepare skip log file (always write, regardless of diagnostic mode)
    skip_log_path = output_path.parent / "wikt_skipped_pages.jsonl"
    skip_log = open(skip_log_path, 'w', encoding='utf-8')

    # Prepare metrics dictionary for Live display
    metrics = {
        "Processed": 0,
        "Written": 0,
        "Special": 0,
        "Redirects": 0,
        "Dict-only": 0,
        "Non-EN": 0,
        "Non-Latin": 0,
        "Skipped": 0,
        "Rate": 0,
        "Decomp MB": 0,
        "Decomp Rate": 0.0,
        "Elapsed": 0.0
    }

    if str(xml_path).endswith('.bz2'):
        file_obj = BZ2StreamReader(xml_path, chunk_size=256 * 1024, metrics=metrics)
    else:
        file_obj = open(xml_path, 'rb')

    entries_processed = 0
    entries_written = 0
    entries_skipped = 0
    special_pages_found = 0
    redirects_found = 0
    dict_only_found = 0  # Track dictionary-only terms
    non_english_found = 0  # Track non-English pages
    non_englishlike_found = 0  # Non-Latin scripts (Greek, Cyrillic, Arabic, Braille, etc.)
    first_page_seen = False

    # Track languages encountered in non-English pages
    language_counts = {}

    # Diagnostic tracking (special pages, redirects, dict-only, non-English, non-Englishlike not included)
    skip_reasons = {
        'no_content_extracted': [],  # extract_page_content returned None
        'parse_entry_none': [],      # parse_entry returned None
        'parse_entry_exception': []  # parse_entry threw exception
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    diagnostic_mode = diagnostic_file is not None

    with file_obj as f, open(output_path, 'w', encoding='utf-8') as out:
        # Use Rich Live display for progress
        with Live(make_form(metrics), refresh_per_second=10) as live:
            # Scan for pages (much faster than XML parsing)
            for page_xml in scan_pages(f, chunk_size=1024 * 1024):
                entries_processed += 1
                metrics["Processed"] = entries_processed

                if not first_page_seen:
                    first_page_seen = True
                    # No need to finish progress - it's in the Live display now

                # Extract title and text using simple regex
                result = extract_page_content(page_xml)
                if not result:
                    entries_skipped += 1
                    metrics["Skipped"] = entries_skipped

                    # Log to skip file
                    title_match = TITLE_PATTERN.search(page_xml)
                    title = title_match.group(1) if title_match else "NO_TITLE"
                    skip_log.write(json.dumps({
                        'reason': 'no_content_extracted',
                        'title': title,
                        'page_xml': page_xml
                    }, ensure_ascii=False) + '\n')
                    skip_log.flush()

                    if diagnostic_mode:
                        skip_reasons['no_content_extracted'].append({
                            'title': title,
                            'page_preview': page_xml[:500]
                        })

                    # Check diagnostic stop condition
                    if diagnostic_mode and entries_skipped >= 100:
                        break
                    continue

                # Handle special pages (known prefixes - expected, no diagnostic needed)
                if result[0] == 'SPECIAL_PAGE':
                    special_pages_found += 1
                    metrics["Special"] = special_pages_found
                    continue

                # Handle redirects (expected, tracked separately)
                if result[0] == 'REDIRECT':
                    redirects_found += 1
                    metrics["Redirects"] = redirects_found
                    continue

                # Handle dictionary-only terms ({{no entry|en|...)
                if result[0] == 'DICT_ONLY':
                    dict_only_found += 1
                    metrics["Dict-only"] = dict_only_found
                    continue

                # Handle non-English pages (track languages)
                if result[0] == 'NON_ENGLISH':
                    non_english_found += 1
                    metrics["Non-EN"] = non_english_found
                    _, title, languages = result
                    for lang in languages:
                        language_counts[lang] = language_counts.get(lang, 0) + 1
                    continue

                title, text = result

                # Check if word uses English-like character set (Latin script)
                # This filters out Greek, Cyrillic, Arabic, Braille, CJK, etc.
                if not is_englishlike(title):
                    non_englishlike_found += 1
                    metrics["Non-Latin"] = non_englishlike_found
                    continue

                # Parse entry
                try:
                    entry = parse_entry(title, text)
                    if entry:
                        out.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + '\n')
                        entries_written += 1
                        metrics["Written"] = entries_written
                    else:
                        entries_skipped += 1
                        metrics["Skipped"] = entries_skipped

                        # Log to skip file
                        skip_log.write(json.dumps({
                            'reason': 'parse_entry_none',
                            'title': title,
                            'text': text
                        }, ensure_ascii=False) + '\n')
                        skip_log.flush()

                        if diagnostic_mode:
                            skip_reasons['parse_entry_none'].append({
                                'title': title,
                                'text_preview': text[:500] if len(text) > 500 else text
                            })

                        # Check diagnostic stop condition
                        if diagnostic_mode and entries_skipped >= 100:
                            break
                except Exception as e:
                    entries_skipped += 1
                    metrics["Skipped"] = entries_skipped

                    # Log to skip file
                    skip_log.write(json.dumps({
                        'reason': 'parse_entry_exception',
                        'title': title,
                        'exception': str(e),
                        'text': text
                    }, ensure_ascii=False) + '\n')
                    skip_log.flush()

                    if diagnostic_mode:
                        skip_reasons['parse_entry_exception'].append({
                            'title': title,
                            'exception': str(e),
                            'text_preview': text[:500] if len(text) > 500 else text
                        })

                    # Check diagnostic stop condition
                    if diagnostic_mode and entries_skipped >= 100:
                        break

                # Update rate and refresh Live display
                if entries_processed % 1000 == 0:
                    elapsed = time.time() - start_time
                    rate = entries_processed / elapsed if elapsed > 0 else 0
                    metrics["Rate"] = rate
                    metrics["Elapsed"] = elapsed
                    live.update(make_form(metrics))
                    if entries_processed % 5000 == 0:
                        out.flush()

                if limit and entries_written >= limit:
                    print(f"\nReached limit of {limit:,} entries")
                    break

    # Close skip log file
    skip_log.close()

    elapsed = time.time() - start_time
    elapsed_min = int(elapsed / 60)
    elapsed_sec = int(elapsed % 60)

    # Summary to stdout
    print()
    print("=" * 60)
    print(f"Total processed: {entries_processed:,}")
    print(f"Total written: {entries_written:,}")
    print(f"Special pages: {special_pages_found:,}")
    print(f"Redirects: {redirects_found:,}")
    print(f"Dictionary-only terms: {dict_only_found:,}")
    print(f"Non-English pages: {non_english_found:,}")
    print(f"Non-Latin scripts: {non_englishlike_found:,}")
    print(f"Total skipped: {entries_skipped:,}")
    print(f"Success rate: {entries_written/entries_processed*100:.1f}%")
    print(f"Time: {elapsed_min}m {elapsed_sec}s")
    print(f"Rate: {entries_processed / elapsed:.0f} pages/sec")
    print("=" * 60)

    # Report skip log location
    if entries_skipped > 0:
        print(f"\nSkipped pages logged to: {skip_log_path}")
        print(f"Review with: cat {skip_log_path} | jq .")

    # Write diagnostic information to file if in diagnostic mode
    if diagnostic_mode:
        diagnostic_file.parent.mkdir(parents=True, exist_ok=True)
        with open(diagnostic_file, 'w', encoding='utf-8') as diag:
            # Helper function to write to file
            def write(text=""):
                diag.write(text + "\n")

            # Write aggregate results at the top
            write("=" * 60)
            write("AGGREGATE RESULTS")
            write("=" * 60)
            write()
            write(f"Total processed: {entries_processed:,}")
            write(f"Total written: {entries_written:,}")
            write(f"Special pages: {special_pages_found:,}")
            write(f"Redirects: {redirects_found:,}")
            write(f"Dictionary-only terms: {dict_only_found:,}")
            write(f"Non-English pages: {non_english_found:,}")
            write(f"Non-Latin scripts: {non_englishlike_found:,}")
            write(f"Total skipped: {entries_skipped:,}")
            write(f"Success rate: {entries_written/entries_processed*100:.1f}%")
            write(f"Time: {elapsed_min}m {elapsed_sec}s")
            write(f"Rate: {entries_processed / elapsed:.0f} pages/sec")
            write("=" * 60)
            write()
            write()

            write("=" * 60)
            write("DIAGNOSTIC REPORT: Skip Reasons Breakdown")
            write("=" * 60)
            write()

            # Count skip reasons
            total_no_content = len(skip_reasons['no_content_extracted'])
            total_parse_none = len(skip_reasons['parse_entry_none'])
            total_exceptions = len(skip_reasons['parse_entry_exception'])

            write(f"Skip reason counts (showing first 10 and last 10 samples):")
            write(f"  1. No content extracted (no title/text or not English): {total_no_content} samples")
            write(f"  2. parse_entry returned None (validation failed): {total_parse_none} samples")
            write(f"  3. parse_entry threw exception: {total_exceptions} samples")
            write()
            write(f"Note: Special pages ({', '.join(SPECIAL_PAGE_PREFIXES)}), redirects,")
            write(f"      dictionary-only terms, non-English pages, and non-Latin scripts are")
            write(f"      counted separately, not included in diagnostic samples.")
            write()

            # Language statistics for non-English pages
            if language_counts:
                write("-" * 60)
                write("NON-ENGLISH PAGE STATISTICS")
                write("-" * 60)
                write()
                write(f"Total non-English pages: {non_english_found:,}")
                write()
                write("Top 20 languages by page count:")
                sorted_langs = sorted(language_counts.items(), key=lambda x: x[1], reverse=True)
                for i, (lang, count) in enumerate(sorted_langs[:20], 1):
                    write(f"  {i:2}. {lang:20} {count:6,} pages")
                write()
                if len(sorted_langs) > 20:
                    write(f"  ... and {len(sorted_langs) - 20} more languages")
                write()
                write(f"Total unique languages: {len(language_counts):,}")
                write()

            # Print samples for each category (first 10 and last 10)
            def write_samples(category_name, samples, has_exception=False):
                """Helper to write first 10 and last 10 samples."""
                if not samples:
                    return

                write("-" * 60)
                write(f"SAMPLES: {category_name}")
                write("-" * 60)

                # Show first 10
                first_samples = samples[:10]
                for i, sample in enumerate(first_samples, 1):
                    write(f"\n{i}. Title: {sample['title']}")
                    if has_exception:
                        write(f"   Exception: {sample['exception']}")
                    if 'page_preview' in sample:
                        write(f"   Page preview (first 500 chars):")
                        write(f"   {sample['page_preview'][:500]}")
                    elif 'text_preview' in sample:
                        write(f"   Text preview (first 500 chars):")
                        write(f"   {sample['text_preview'][:500]}")
                    write()

                # Show last 10 if we have more than 10 samples
                if len(samples) > 10:
                    if len(samples) > 20:
                        write(f"... ({len(samples) - 20} samples omitted) ...")
                        write()

                    last_samples = samples[-10:]
                    start_idx = len(samples) - 10 + 1
                    for i, sample in enumerate(last_samples, start_idx):
                        write(f"\n{i}. Title: {sample['title']}")
                        if has_exception:
                            write(f"   Exception: {sample['exception']}")
                        if 'page_preview' in sample:
                            write(f"   Page preview (first 500 chars):")
                            write(f"   {sample['page_preview'][:500]}")
                        elif 'text_preview' in sample:
                            write(f"   Text preview (first 500 chars):")
                            write(f"   {sample['text_preview'][:500]}")
                        write()

            write_samples("No content extracted", skip_reasons['no_content_extracted'])
            write_samples("parse_entry returned None", skip_reasons['parse_entry_none'])
            write_samples("parse_entry threw exception", skip_reasons['parse_entry_exception'], has_exception=True)

            write("=" * 60)
            write("GOAL: Reach fixed point (no samples in any category)")
            write("=" * 60)
            write()
            write("Action items based on samples:")
            write()
            write("1. 'no_content_extracted' samples:")
            write("   - Look for unknown special page prefixes (add to SPECIAL_PAGE_PREFIXES)")
            write("   - Check for pages with ':' that aren't English words (e.g., 'talk:', 'user:')")
            write("   - Identify any regex pattern issues")
            write()
            write("2. 'parse_entry_none' samples:")
            write("   - Check if missing POS tags for valid entries")
            write("   - Check for character validation issues")
            write("   - Identify entries that should be extracted")
            write()
            write("3. 'parse_entry_exception' samples:")
            write("   - Fix code bugs causing exceptions")
            write("   - Add error handling for edge cases")
            write()
            write("Fixed point achieved when all sample lists are empty!")
            write("=" * 60)

        print(f"\nDiagnostic report written to: {diagnostic_file}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Fast scanner-based Wiktionary XML parser (no full XML parsing)'
    )

    parser.add_argument(
        'input',
        type=Path,
        help='Input XML file (.xml or .xml.bz2)'
    )

    parser.add_argument(
        'output',
        type=Path,
        help='Output JSONL file'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit number of entries to extract (for testing)'
    )

    parser.add_argument(
        '--diagnostic',
        type=Path,
        default=None,
        metavar='FILE',
        help='Diagnostic mode: stop after 100 skips and write report to FILE'
    )

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)

    parse_wiktionary_dump(args.input, args.output, args.limit, args.diagnostic)


if __name__ == '__main__':
    main()
