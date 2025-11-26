#!/usr/bin/env python3
"""
Generate synthetic Wiktionary XML data for benchmarking Rust scanner optimizations.

This script creates XML files that mimic the structure of real Wiktionary dumps
but with controlled sizes for performance testing.
"""

import argparse
import bz2
import random
import sys
from pathlib import Path

# Sample word templates for generating diverse entries
WORD_BASES = [
    "happy", "run", "think", "beautiful", "computer", "science", "music", "water",
    "earth", "sky", "book", "write", "speak", "listen", "dream", "hope", "love",
    "friend", "family", "work", "play", "learn", "teach", "build", "create",
    "discover", "explore", "imagine", "wonder", "believe", "understand", "know",
    "feel", "touch", "see", "hear", "taste", "smell", "walk", "jump", "swim",
    "fly", "dance", "sing", "draw", "paint", "cook", "clean", "organize", "plan"
]

POS_TYPES = [
    ("Noun", "en-noun", "noun"),
    ("Verb", "en-verb", "verb"),
    ("Adjective", "en-adj", "adjective"),
    ("Adverb", "en-adv", "adverb"),
    ("Proper noun", "en-prop", "proper noun"),
]

REGISTER_LABELS = ["informal", "colloquial", "slang", "formal", "literary"]
REGION_LABELS = ["US", "UK", "Australia", "Canada", "Ireland"]
DOMAIN_LABELS = ["computing", "mathematics", "medicine", "biology", "law", "sports"]
TEMPORAL_LABELS = ["archaic", "obsolete", "dated", "historical", "rare"]

ETYMOLOGY_TEMPLATES = [
    "{{suffix|en|{base}|ness}}",
    "{{prefix|en|un|{base}}}",
    "{{compound|en|{base}|work}}",
    "{{affix|en|{base}|-tion}}",
    "From {{inh|en|enm|{base}}}",
]

DEFINITIONS = [
    "The act of {verb}ing something.",
    "A person who {verb}s.",
    "Relating to or characterized by {adj}.",
    "The quality of being {adj}.",
    "An instance of {verb}ing.",
    "A type of {noun}.",
    "One who is {adj}.",
    "The state of {verb}ing.",
    "A place where {noun}s are found.",
    "Something used for {verb}ing.",
]


def generate_word_variant(base: str, idx: int) -> str:
    """Generate a unique word variant."""
    suffixes = ["ness", "ity", "tion", "ment", "er", "or", "ing", "ly", "able", "ful"]
    prefixes = ["un", "re", "pre", "dis", "over", "under", "mis", "out", "non", "anti"]

    variant_type = idx % 5
    if variant_type == 0:
        return f"{base}{suffixes[idx % len(suffixes)]}"
    elif variant_type == 1:
        return f"{prefixes[idx % len(prefixes)]}{base}"
    elif variant_type == 2:
        return f"{base}{idx}"
    elif variant_type == 3:
        return f"{base}_{suffixes[idx % len(suffixes)]}"
    else:
        return f"{base}{suffixes[idx % len(suffixes)]}{idx}"


def generate_definition_with_labels(idx: int) -> str:
    """Generate a definition line with optional labels."""
    labels = []

    if random.random() < 0.3:
        labels.append(random.choice(REGISTER_LABELS))
    if random.random() < 0.2:
        labels.append(random.choice(REGION_LABELS))
    if random.random() < 0.2:
        labels.append(random.choice(DOMAIN_LABELS))
    if random.random() < 0.1:
        labels.append(random.choice(TEMPORAL_LABELS))

    definition = random.choice(DEFINITIONS).format(
        verb=random.choice(WORD_BASES),
        adj=random.choice(WORD_BASES),
        noun=random.choice(WORD_BASES)
    )

    if labels:
        label_str = "|".join(labels)
        return f"# {{{{lb|en|{label_str}}}}} {definition}"
    return f"# {definition}"


def generate_english_section(word: str, num_senses: int = 3) -> str:
    """Generate the English section of a Wiktionary entry."""
    pos_type = random.choice(POS_TYPES)
    pos_header, pos_template, pos_name = pos_type

    # Etymology
    etymology = random.choice(ETYMOLOGY_TEMPLATES).format(base=word[:4])

    # Hyphenation (for syllable detection)
    syllables = "-".join([word[i:i+3] for i in range(0, min(len(word), 9), 3)])

    # Generate definitions
    definitions = "\n".join(generate_definition_with_labels(i) for i in range(num_senses))

    section = f"""==English==

===Etymology===
{etymology}

===Pronunciation===
* {{{{IPA|en|/ˈwɜːd/}}}}
* {{{{hyphenation|en|{syllables}}}}}

==={pos_header}===
{{{{{pos_template}}}}}

{definitions}

====Derived terms====
* {{{{l|en|{word}er}}}}
* {{{{l|en|{word}ing}}}}

[[Category:English {pos_name}s]]
"""
    return section


def generate_page(title: str, page_id: int, num_senses: int = 3) -> str:
    """Generate a complete Wiktionary page XML."""
    english_section = generate_english_section(title, num_senses)

    # Sometimes add other language sections (to test English extraction)
    other_sections = ""
    if random.random() < 0.3:
        other_sections = f"""

==French==

===Noun===
{{{{fr-noun|m}}}}

# French definition
"""

    return f"""  <page>
    <title>{title}</title>
    <ns>0</ns>
    <id>{page_id}</id>
    <revision>
      <id>{page_id * 100}</id>
      <timestamp>2025-01-01T00:00:00Z</timestamp>
      <contributor>
        <username>TestBot</username>
        <id>1</id>
      </contributor>
      <model>wikitext</model>
      <format>text/x-wiki</format>
      <text bytes="{len(english_section)}" xml:space="preserve">{english_section}{other_sections}</text>
    </revision>
  </page>
"""


def generate_redirect_page(title: str, target: str, page_id: int) -> str:
    """Generate a redirect page (to test redirect filtering)."""
    return f"""  <page>
    <title>{title}</title>
    <ns>0</ns>
    <id>{page_id}</id>
    <redirect title="{target}" />
    <revision>
      <id>{page_id * 100}</id>
      <text bytes="20" xml:space="preserve">#REDIRECT [[{target}]]</text>
    </revision>
  </page>
"""


def generate_special_page(title: str, page_id: int) -> str:
    """Generate a special/non-English page (to test filtering)."""
    return f"""  <page>
    <title>{title}</title>
    <ns>10</ns>
    <id>{page_id}</id>
    <revision>
      <id>{page_id * 100}</id>
      <text bytes="100" xml:space="preserve">Template content here</text>
    </revision>
  </page>
"""


def generate_non_english_page(title: str, page_id: int) -> str:
    """Generate a page without English section."""
    return f"""  <page>
    <title>{title}</title>
    <ns>0</ns>
    <id>{page_id}</id>
    <revision>
      <id>{page_id * 100}</id>
      <text bytes="200" xml:space="preserve">==French==

===Noun===
{{{{fr-noun|m}}}}

# French only word
</text>
    </revision>
  </page>
"""


def generate_xml_dump(
    output_path: Path,
    num_pages: int,
    compress: bool = True,
    avg_senses: int = 3
) -> None:
    """Generate a complete XML dump file."""

    header = """<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/">
  <siteinfo>
    <sitename>Wiktionary</sitename>
    <dbname>enwiktionary</dbname>
    <base>https://en.wiktionary.org/wiki/Main_Page</base>
  </siteinfo>
"""
    footer = "</mediawiki>\n"

    # Calculate page distribution
    # 70% English pages, 10% redirects, 10% special, 10% non-English
    english_pages = int(num_pages * 0.70)
    redirect_pages = int(num_pages * 0.10)
    special_pages = int(num_pages * 0.10)
    non_english_pages = num_pages - english_pages - redirect_pages - special_pages

    print(f"Generating {num_pages} pages:")
    print(f"  - {english_pages} English pages")
    print(f"  - {redirect_pages} redirects")
    print(f"  - {special_pages} special pages")
    print(f"  - {non_english_pages} non-English pages")

    page_id = 0

    def write_output(f):
        nonlocal page_id
        f.write(header.encode('utf-8'))

        # Generate English pages
        for i in range(english_pages):
            base_word = WORD_BASES[i % len(WORD_BASES)]
            word = generate_word_variant(base_word, i)
            num_senses = max(1, int(random.gauss(avg_senses, 1)))
            page = generate_page(word, page_id, num_senses)
            f.write(page.encode('utf-8'))
            page_id += 1

            if page_id % 10000 == 0:
                print(f"  Generated {page_id} pages...")

        # Generate redirects
        for i in range(redirect_pages):
            title = f"redirect_{i}"
            target = WORD_BASES[i % len(WORD_BASES)]
            page = generate_redirect_page(title, target, page_id)
            f.write(page.encode('utf-8'))
            page_id += 1

        # Generate special pages
        for i in range(special_pages):
            title = f"Template:test_{i}"
            page = generate_special_page(title, page_id)
            f.write(page.encode('utf-8'))
            page_id += 1

        # Generate non-English pages
        for i in range(non_english_pages):
            title = f"mot_{i}"  # French-style
            page = generate_non_english_page(title, page_id)
            f.write(page.encode('utf-8'))
            page_id += 1

        f.write(footer.encode('utf-8'))

    if compress:
        with bz2.open(output_path, 'wb', compresslevel=9) as f:
            write_output(f)
    else:
        with open(output_path, 'wb') as f:
            write_output(f)

    print(f"\nGenerated {output_path}")
    file_size = output_path.stat().st_size
    if file_size > 1024 * 1024:
        print(f"File size: {file_size / (1024*1024):.2f} MB")
    else:
        print(f"File size: {file_size / 1024:.2f} KB")


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic Wiktionary XML for benchmarking"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("synthetic_wiktionary.xml.bz2"),
        help="Output file path (default: synthetic_wiktionary.xml.bz2)"
    )
    parser.add_argument(
        "-n", "--num-pages",
        type=int,
        default=100000,
        help="Number of pages to generate (default: 100000)"
    )
    parser.add_argument(
        "--no-compress",
        action="store_true",
        help="Don't compress output (generate plain XML)"
    )
    parser.add_argument(
        "--avg-senses",
        type=int,
        default=3,
        help="Average number of senses per word (default: 3)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)"
    )

    # Preset sizes for convenience
    parser.add_argument(
        "--small",
        action="store_true",
        help="Generate small test file (10K pages)"
    )
    parser.add_argument(
        "--medium",
        action="store_true",
        help="Generate medium test file (100K pages)"
    )
    parser.add_argument(
        "--large",
        action="store_true",
        help="Generate large test file (500K pages)"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Generate full-scale test file (1M pages, similar to real dump)"
    )

    args = parser.parse_args()

    random.seed(args.seed)

    # Handle presets
    if args.small:
        args.num_pages = 10000
        args.output = Path("synthetic_small.xml.bz2")
    elif args.medium:
        args.num_pages = 100000
        args.output = Path("synthetic_medium.xml.bz2")
    elif args.large:
        args.num_pages = 500000
        args.output = Path("synthetic_large.xml.bz2")
    elif args.full:
        args.num_pages = 1000000
        args.output = Path("synthetic_full.xml.bz2")

    compress = not args.no_compress
    if not compress and args.output.suffix == ".bz2":
        args.output = args.output.with_suffix("")

    generate_xml_dump(
        args.output,
        args.num_pages,
        compress=compress,
        avg_senses=args.avg_senses
    )


if __name__ == "__main__":
    main()
