#!/usr/bin/env python3
"""
Extract raw wikitext from Wiktionary XML dump for specific words.

This tool scans through the .xml.bz2 file and extracts the complete
<page>...</page> XML for specified words, writing each to a separate file.

Case Sensitivity:
    Words are matched case-sensitively. "sat", "Sat", and "SAT" are three
    different targets that will extract different Wiktionary pages.

Filename Encoding:
    Filenames use punycode for Unicode and left-aligned octal for case patterns
    to ensure unique filenames on case-insensitive filesystems (macOS APFS):
        sat         -> sat.xml
        Sat         -> sat_4.xml       (binary: 100 = octal 4)
        SAT         -> sat_7.xml       (binary: 111 = octal 7)
        March       -> march_4.xml     (10000, trailing zeros stripped)
        MARCH       -> march_76.xml    (11111 -> 111 110 = octal 76)
        Afghanistan -> afghanistan_4.xml  (first letter uppercase)
        tiếng       -> xn--ting-hv5a.xml  (punycode for Vietnamese)
        водка       -> xn--80adgys.xml    (punycode for Cyrillic)

Usage:
    python tools/extract_wikitext.py INPUT.xml.bz2 OUTPUT_DIR WORD1 [WORD2 ...]
    python tools/extract_wikitext.py INPUT.xml.bz2 OUTPUT_DIR --words-file WORDLIST.txt
    python tools/extract_wikitext.py INPUT.xml.bz2 OUTPUT_DIR --words-file WORDLIST.txt --update

Options:
    --update    Skip words that already have .xml files in OUTPUT_DIR

Examples:
    # Update mode: only extract missing words
    uv run python tools/extract_wikitext.py data/raw/en/enwiktionary-latest-pages-articles.xml.bz2 \
        reference/wiktionary/samples --words-file reference/wiktionary/hotspot-words.txt --update

    # Extract from hotspot list
    uv run python tools/extract_wikitext.py data/raw/en/enwiktionary-latest-pages-articles.xml.bz2 \
        reference/wiktionary/samples --words-file reference/wiktionary/hotspot-words.txt
"""

import bz2
import re
import sys
from pathlib import Path


def word_to_filename(word: str) -> str:
    """Encode a word to a filesystem-safe filename (without extension).

    Uses punycode for Unicode characters and octal for case pattern.
    This ensures unique filenames on case-insensitive filesystems.

    Case pattern encoding:
        - Build binary string left-to-right: 1=upper, 0=lower
        - Pad on RIGHT to multiple of 3 bits, convert to octal
        - Strip trailing zeros (word length is known from decoding)
        - Use underscore delimiter (never appears in punycode)

    Examples:
        sat         -> sat
        Sat         -> sat_4       (binary: 100 = octal 4)
        SAT         -> sat_7       (binary: 111 = octal 7)
        March       -> march_4     (binary: 10000, only leading digit needed)
        MARCH       -> march_76    (binary: 11111 -> 111 110 = octal 76)
        Afghanistan -> afghanistan_4  (first letter uppercase = 4)
        tiếng       -> xn--ting-hv5a
        Tiếng       -> xn--ting-hv5a_4
    """
    # Build binary string left-to-right (1=upper, 0=lower)
    case_binary = "".join("1" if c.isupper() else "0" for c in word)
    has_upper = "1" in case_binary

    # Convert to lowercase and encode as punycode
    lower_word = word.lower()
    try:
        # Punycode encode (handles Unicode)
        encoded = lower_word.encode("idna").decode("ascii")
    except (UnicodeError, UnicodeDecodeError):
        # Fallback for edge cases that IDNA can't handle
        encoded = lower_word.encode("punycode").decode("ascii")
        if encoded != lower_word:
            encoded = "xn--" + encoded

    # Add case suffix if needed (underscore delimiter, strip trailing zeros)
    if has_upper:
        # Pad on RIGHT to multiple of 3 for clean octal conversion
        while len(case_binary) % 3 != 0:
            case_binary += "0"
        case_octal = oct(int(case_binary, 2))[2:].rstrip("0") or "0"
        return f"{encoded}_{case_octal}"
    return encoded


def filename_to_word(filename: str) -> str:
    """Decode a filename back to the original word.

    Inverse of word_to_filename().

    Case pattern decoding:
        - Parse octal number, convert to binary
        - Pad LEFT to multiple of 3 (for proper octal grouping)
        - Pad RIGHT with zeros to match word length
        - Apply: 1=upper, 0=lower
    """
    # Remove .xml extension if present
    if filename.endswith(".xml"):
        filename = filename[:-4]

    # Check for case suffix (underscore followed by octal digits)
    parts = filename.rsplit("_", 1)
    if len(parts) == 2 and all(c in "01234567" for c in parts[1]):
        encoded = parts[0]
        case_octal = parts[1]
    else:
        encoded = filename
        case_octal = None

    # Decode punycode
    try:
        word = encoded.encode("ascii").decode("idna")
    except (UnicodeError, UnicodeDecodeError):
        # Fallback for edge cases
        if encoded.startswith("xn--"):
            word = encoded[4:].encode("ascii").decode("punycode")
        else:
            word = encoded

    # Apply case pattern (left-aligned, trailing zeros stripped)
    if case_octal:
        # Convert octal to binary
        case_bits = int(case_octal, 8)
        case_binary = bin(case_bits)[2:]
        # Pad left to multiple of 3 (proper octal grouping)
        while len(case_binary) % 3 != 0:
            case_binary = "0" + case_binary
        # Pad right with zeros to match word length
        while len(case_binary) < len(word):
            case_binary += "0"

        # Apply case pattern
        chars = list(word)
        for i in range(len(chars)):
            if i < len(case_binary) and case_binary[i] == "1":
                chars[i] = chars[i].upper()
        word = "".join(chars)

    return word


def load_words_from_file(filepath):
    """Load words from a text file, one per line, ignoring comments."""
    words = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith("#"):
                words.append(line)
    return words


def filter_existing_words(target_words, output_dir):
    """Filter out words that already have .xml files in output_dir.

    Uses encoded filenames to handle case-insensitive filesystems.
    """
    output_dir = Path(output_dir)
    existing = []
    missing = []

    # Get actual filenames in directory
    if output_dir.exists():
        existing_files = {f.name for f in output_dir.iterdir() if f.is_file()}
    else:
        existing_files = set()

    for word in target_words:
        filename = f"{word_to_filename(word)}.xml"
        if filename in existing_files:
            existing.append(word)
        else:
            missing.append(word)

    return missing, existing


def scan_and_extract(xml_path, output_dir, target_words, update_mode=False):
    """Scan XML dump and extract pages for target words."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # In update mode, skip words that already have files
    if update_mode:
        missing_words, existing_words = filter_existing_words(target_words, output_dir)
        if existing_words:
            print(f"Update mode: Skipping {len(existing_words)} existing words:")
            for word in sorted(existing_words):
                print(f"  ✓ {word_to_filename(word)}.xml (already exists)")
            print()
        target_words = missing_words
        if not target_words:
            print("All words already extracted. Nothing to do.")
            return set()

    # Convert to set for fast lookup (case-sensitive matching)
    target_set = set(target_words)
    found_words = set()

    print(f"Scanning: {xml_path}")
    print(f"Output directory: {output_dir}")
    print(f"Looking for {len(target_words)} words...")
    print()

    # Patterns for extraction
    title_pattern = re.compile(r"<title>([^<]+)</title>")
    page_start = "<page>"
    page_end = "</page>"

    buffer = ""
    pages_scanned = 0
    pages_extracted = 0

    # Open bz2 file
    with bz2.open(xml_path, "rt", encoding="utf-8") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), ""):
            buffer += chunk

            # Extract complete pages
            while True:
                start = buffer.find(page_start)
                if start == -1:
                    # Keep last bit in case it's a partial tag
                    buffer = buffer[-len(page_start):]
                    break

                end = buffer.find(page_end, start)
                if end == -1:
                    # Incomplete page, keep from start
                    buffer = buffer[start:]
                    break

                # Extract complete page
                end += len(page_end)
                page_xml = buffer[start:end]
                buffer = buffer[end:]

                pages_scanned += 1
                if pages_scanned % 100000 == 0:
                    print(f"Scanned {pages_scanned:,} pages, extracted {pages_extracted}...")

                # Check if this is a target word (case-sensitive matching)
                title_match = title_pattern.search(page_xml)
                if title_match:
                    title = title_match.group(1)

                    if title in target_set and title not in found_words:
                        # Extract and save with encoded filename
                        encoded_name = word_to_filename(title)
                        output_file = output_dir / f"{encoded_name}.xml"
                        with open(output_file, "w", encoding="utf-8") as out:
                            out.write(page_xml)

                        found_words.add(title)
                        pages_extracted += 1
                        print(f"✓ Extracted: {title} -> {output_file.name}")

                        # Stop if we've found all target words
                        if len(found_words) == len(target_set):
                            print()
                            print(f"All {len(target_set)} target words found!")
                            return found_words

    print()
    print(f"Scan complete. Scanned {pages_scanned:,} pages.")
    print(f"Extracted {pages_extracted} of {len(target_words)} target words.")

    # Report missing words
    missing = target_set - found_words
    if missing:
        print()
        print(f"⚠️  Missing words ({len(missing)}):")
        for word in sorted(missing):
            print(f"  - {word}")

    return found_words


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    xml_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not xml_path.exists():
        print(f"Error: Input file not found: {xml_path}")
        sys.exit(1)

    # Parse flags and words from arguments
    args = sys.argv[3:]
    update_mode = False
    target_words = []

    # Check for --update flag
    if "--update" in args:
        update_mode = True
        args = [a for a in args if a != "--update"]

    # Parse words from arguments or file
    if len(args) > 0 and args[0] == "--words-file":
        if len(args) < 2:
            print("Error: --words-file requires a filename argument")
            sys.exit(1)
        words_file = Path(args[1])
        if not words_file.exists():
            print(f"Error: Words file not found: {words_file}")
            sys.exit(1)
        target_words = load_words_from_file(words_file)
        print(f"Loaded {len(target_words)} words from {words_file}")
    else:
        target_words = args

    if not target_words:
        print("Error: No words specified")
        sys.exit(1)

    scan_and_extract(xml_path, output_dir, target_words, update_mode=update_mode)


if __name__ == "__main__":
    main()
