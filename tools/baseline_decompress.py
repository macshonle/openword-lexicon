#!/usr/bin/env python3
"""
baseline_decompress.py - Baseline decompression benchmark

Decompresses a bz2 file and counts page markers without any XML parsing.
This establishes a baseline for how long raw decompression takes vs
decompression + XML parsing.

Usage:
    python baseline_decompress.py INPUT.xml.bz2
"""

import bz2
import sys
import time
from pathlib import Path


def baseline_decompress(filepath: Path):
    """
    Decompress file and count page markers.

    Counts:
    - "<page" (any occurrence)
    - "\n<page" (page at start of line)
    """

    print(f"Baseline decompression test: {filepath}")
    print()

    file_size_mb = filepath.stat().st_size / (1024 * 1024)
    print(f"Compressed file size: {file_size_mb:.1f} MB")
    print()

    # Open raw file
    print("Opening compressed file...")
    with open(filepath, 'rb') as f:
        decompressor = bz2.BZ2Decompressor()

        # Counters
        total_compressed = 0
        total_decompressed = 0
        page_count = 0
        newline_page_count = 0
        last_progress = 0
        start_time = time.time()

        # For tracking newlines
        last_char_was_newline = True  # Assume start of file

        # Read and decompress in chunks
        chunk_size = 256 * 1024  # 256 KB chunks

        print("Decompressing and counting page markers...")
        print()

        while True:
            # Read compressed chunk
            compressed_chunk = f.read(chunk_size)
            if not compressed_chunk:
                break

            total_compressed += len(compressed_chunk)

            # Decompress
            try:
                decompressed_chunk = decompressor.decompress(compressed_chunk)
            except EOFError:
                # End of compressed data
                break

            total_decompressed += len(decompressed_chunk)

            # Convert to string for counting
            try:
                text = decompressed_chunk.decode('utf-8')
            except UnicodeDecodeError:
                # Skip non-UTF8 chunks
                text = decompressed_chunk.decode('utf-8', errors='ignore')

            # Count "<page" occurrences
            page_count += text.count('<page')

            # Count "\n<page" occurrences (page at start of line)
            newline_page_count += text.count('\n<page')

            # Also check if first char of this chunk is '<page' and last char of previous was '\n'
            if last_char_was_newline and text.startswith('<page'):
                newline_page_count += 1

            # Track if last char was newline
            if text:
                last_char_was_newline = text[-1] == '\n'

            # Progress every 50 MB decompressed
            if total_decompressed - last_progress >= 50 * 1024 * 1024:
                elapsed = time.time() - start_time
                rate_mb = (total_decompressed / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                elapsed_min = int(elapsed / 60)
                elapsed_sec = int(elapsed % 60)

                print(f"  Decompressing: {total_decompressed / (1024*1024):.0f} MB "
                      f"({rate_mb:.1f} MB/s, {elapsed_min}m {elapsed_sec}s elapsed) "
                      f"[{page_count:,} <page markers found]",
                      end='\r', flush=True)

                last_progress = total_decompressed

            # Check if done
            if decompressor.eof:
                break

    # Final stats
    elapsed = time.time() - start_time
    elapsed_min = int(elapsed / 60)
    elapsed_sec = int(elapsed % 60)

    print()  # New line after progress
    print()
    print("=" * 60)
    print("BASELINE DECOMPRESSION COMPLETE")
    print("=" * 60)
    print()
    print(f"Compressed size:     {total_compressed / (1024*1024):.1f} MB")
    print(f"Decompressed size:   {total_decompressed / (1024*1024):.1f} MB")
    print(f"Compression ratio:   {total_decompressed / total_compressed:.2f}x")
    print(f"Decompression time:  {elapsed_min}m {elapsed_sec}s")
    print(f"Decompression rate:  {(total_decompressed / (1024*1024)) / elapsed:.1f} MB/s")
    print()
    print(f"Page markers found:")
    print(f"  '<page' anywhere:        {page_count:,}")
    print(f"  '\\n<page' (line start):  {newline_page_count:,}")
    print()
    print("=" * 60)
    print()
    print("Interpretation:")
    print(f"  • Raw decompression took {elapsed_min}m {elapsed_sec}s")
    print(f"  • Found ~{page_count:,} page elements")
    print(f"  • If full parsing takes longer, the difference is XML overhead")
    print(f"  • If full parsing takes similar time, decompression is the bottleneck")
    print()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Baseline decompression benchmark (no XML parsing)'
    )

    parser.add_argument(
        'input',
        type=Path,
        help='Input bz2 file'
    )

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    baseline_decompress(args.input)


if __name__ == '__main__':
    main()
