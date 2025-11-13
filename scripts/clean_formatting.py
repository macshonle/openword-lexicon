#!/usr/bin/env python3
"""
Remove PHASE numbering and Unicode formatting from Python modules.
Replace with simple UNIX-style output.
"""

import re
from pathlib import Path

def clean_file(filepath):
    """Remove PHASE references and Unicode formatting."""
    with open(filepath, 'r') as f:
        content = f.read()

    original = content

    # Remove PHASE N: prefix from log messages
    # e.g., "PHASE 5: Core word list ingestion" -> "Core word list ingestion"
    content = re.sub(
        r'logger\.info\("PHASE \d+: ([^"]+)"\)',
        r'logger.info("\1")',
        content
    )

    # Remove separator lines with equals signs
    # e.g., logger.info("=" * 60)
    content = re.sub(
        r'\s*logger\.info\("=+"\s*\*\s*\d+\)\s*\n',
        '',
        content
    )

    # Replace Unicode checkmarks and symbols with simple text
    replacements = {
        '✓': '',  # Remove checkmark
        '✗': '',  # Remove X mark
        '→': '->',  # Arrow to ASCII
        '⚠': 'Warning:',  # Warning symbol to text
    }

    for unicode_char, replacement in replacements.items():
        # Replace in logger messages
        content = content.replace(unicode_char, replacement)

    # Clean up double spaces from removed checkmarks
    content = re.sub(r'  +', ' ', content)

    # Clean up lines that now start with extra space
    content = re.sub(r'\n +logger\.info\("  ', '\nlogger.info("', content)

    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        return True
    return False

def main():
    """Process all Python files."""
    src_dir = Path('src/openword')
    tools_dir = Path('tools')

    changed_files = []

    # Process source files
    for pyfile in src_dir.glob('*.py'):
        if clean_file(pyfile):
            changed_files.append(pyfile)
            print(f"Cleaned: {pyfile}")

    # Process tool files
    for pyfile in tools_dir.glob('*.py'):
        if clean_file(pyfile):
            changed_files.append(pyfile)
            print(f"Cleaned: {pyfile}")

    print(f"\nCleaned {len(changed_files)} files")
    for f in changed_files:
        print(f"  {f}")

if __name__ == '__main__':
    main()
