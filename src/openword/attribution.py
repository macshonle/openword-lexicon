#!/usr/bin/env python3
"""
attribution.py — Generate ATTRIBUTION.md and LICENSE files.

Reads:
  - data/raw/*/*.SOURCE.json

Outputs:
  - ATTRIBUTION.md (consolidated attribution per TASL)
  - data/core/LICENSE (CC0 or CC BY 4.0)
  - data/plus/LICENSE (CC BY-SA 4.0)

License matrix:
  - CORE: ENABLE (PD), EOWL (permissive) -> CC BY 4.0
  - PLUS: + Wiktionary (CC BY-SA) + WordNet + Frequency -> CC BY-SA 4.0
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import orjson


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_source_metadata(data_root: Path) -> List[Dict]:
    """Load all SOURCE.json files."""
    sources = []
    source_files = list(data_root.glob("*/*/*.SOURCE.json")) + \
                   list(data_root.glob("*/*.SOURCE.json"))

    logger.info(f"Found {len(source_files)} SOURCE.json files")

    for source_file in source_files:
        try:
            with open(source_file, 'r') as f:
                data = json.load(f)
                sources.append(data)
        except Exception as e:
            logger.warning(f"Error reading {source_file}: {e}")

    return sources


def generate_attribution_md(sources: List[Dict], output_path: Path):
    """Generate ATTRIBUTION.md with consolidated attribution."""
    logger.info(f"Generating {output_path}")

    # Sort sources by name
    sources = sorted(sources, key=lambda s: s.get('name', ''))

    content = []
    content.append("# Openword Lexicon — Attribution\n")
    content.append(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
    content.append("\n---\n\n")

    content.append("## Overview\n\n")
    content.append("This lexicon is built from multiple open sources. ")
    content.append("Each source has its own license and attribution requirements, ")
    content.append("which are detailed below.\n\n")

    content.append("## Distribution Licenses\n\n")
    content.append("- **Core Distribution**: CC BY 4.0 (most permissive sources only)\n")
    content.append("- **Plus Distribution**: CC BY-SA 4.0 (includes additional CC BY-SA sources)\n\n")

    content.append("---\n\n")

    content.append("## Source Attributions\n\n")

    for source in sources:
        name = source.get('name', 'Unknown')
        title = source.get('title', name)
        author = source.get('author', 'Unknown')
        url = source.get('url', 'N/A')
        license_name = source.get('license', 'Unknown')
        license_url = source.get('license_url', '')
        attribution = source.get('attribution', '')

        content.append(f"### {name}\n\n")
        content.append(f"**Title:** {title}\n\n")
        content.append(f"**Author/Contributors:** {author}\n\n")
        content.append(f"**Source URL:** {url}\n\n")

        if license_url:
            content.append(f"**License:** [{license_name}]({license_url})\n\n")
        else:
            content.append(f"**License:** {license_name}\n\n")

        if attribution:
            content.append(f"**Attribution Statement:**\n\n")
            content.append(f"> {attribution}\n\n")

        # Additional notes
        notes = source.get('notes', '')
        if notes:
            content.append(f"**Notes:** {notes}\n\n")

        # Download metadata
        downloaded = source.get('downloaded_at', '')
        if downloaded:
            content.append(f"*Downloaded: {downloaded}*\n\n")

        sha256 = source.get('sha256', '')
        if sha256:
            content.append(f"*SHA256: `{sha256}`*\n\n")

        content.append("---\n\n")

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(''.join(content))

    logger.info(f"Written: {output_path}")


def generate_core_license(output_path: Path):
    """Generate LICENSE file for core distribution (CC BY 4.0)."""
    logger.info(f"Generating {output_path}")

    content = """Creative Commons Attribution 4.0 International Public License

By exercising the Licensed Rights (defined below), You accept and agree to be
bound by the terms and conditions of this Creative Commons Attribution 4.0
International Public License ("Public License"). To the extent this Public
License may be interpreted as a contract, You are granted the Licensed Rights
in consideration of Your acceptance of these terms and conditions, and the
Licensor grants You such rights in consideration of benefits the Licensor
receives from making the Licensed Material available under these terms and
conditions.

Section 1 – Definitions.

a. Adapted Material means material subject to Copyright and Similar Rights that
   is derived from or based upon the Licensed Material and in which the Licensed
   Material is translated, altered, arranged, transformed, or otherwise modified
   in a manner requiring permission under the Copyright and Similar Rights held
   by the Licensor.

b. Adapter's License means the license You apply to Your Copyright and Similar
   Rights in Your contributions to Adapted Material in accordance with the terms
   and conditions of this Public License.

c. Copyright and Similar Rights means copyright and/or similar rights closely
   related to copyright including, without limitation, performance, broadcast,
   sound recording, and Sui Generis Database Rights, without regard to how the
   rights are labeled or categorized.

d. Licensed Material means the artistic or literary work, database, or other
   material to which the Licensor applied this Public License.

e. Licensed Rights means the rights granted to You subject to the terms and
   conditions of this Public License, which are limited to all Copyright and
   Similar Rights that apply to Your use of the Licensed Material and that the
   Licensor has authority to license.

f. Licensor means the individual(s) or entity(ies) granting rights under this
   Public License.

g. Share means to provide material to the public by any means or process that
   requires permission under the Licensed Rights, such as reproduction, public
   display, public performance, distribution, dissemination, communication, or
   importation, and to make material available to the public including in ways
   that members of the public may access the material from a place and at a time
   individually chosen by them.

h. You means the individual or entity exercising the Licensed Rights under this
   Public License. Your has a corresponding meaning.

For the full license text, see:
https://creativecommons.org/licenses/by/4.0/legalcode

---

ATTRIBUTION REQUIREMENT:

When using this work, you must provide attribution as follows:

  "Openword Lexicon Core Distribution" by [contributors]
  Licensed under CC BY 4.0
  https://creativecommons.org/licenses/by/4.0/

For detailed source attributions, see ATTRIBUTION.md
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    logger.info(f"Written: {output_path}")


def generate_plus_license(output_path: Path):
    """Generate LICENSE file for plus distribution (CC BY-SA 4.0)."""
    logger.info(f"Generating {output_path}")

    content = """Creative Commons Attribution-ShareAlike 4.0 International Public License

By exercising the Licensed Rights (defined below), You accept and agree to be
bound by the terms and conditions of this Creative Commons Attribution-ShareAlike
4.0 International Public License ("Public License"). To the extent this Public
License may be interpreted as a contract, You are granted the Licensed Rights
in consideration of Your acceptance of these terms and conditions, and the
Licensor grants You such rights in consideration of benefits the Licensor
receives from making the Licensed Material available under these terms and
conditions.

Section 1 – Definitions.

a. Adapted Material means material subject to Copyright and Similar Rights that
   is derived from or based upon the Licensed Material and in which the Licensed
   Material is translated, altered, arranged, transformed, or otherwise modified
   in a manner requiring permission under the Copyright and Similar Rights held
   by the Licensor.

b. Adapter's License means the license You apply to Your Copyright and Similar
   Rights in Your contributions to Adapted Material in accordance with the terms
   and conditions of this Public License.

c. BY-SA Compatible License means a license listed at
   creativecommons.org/compatiblelicenses, approved by Creative Commons as
   essentially the equivalent of this Public License.

d. Copyright and Similar Rights means copyright and/or similar rights closely
   related to copyright including, without limitation, performance, broadcast,
   sound recording, and Sui Generis Database Rights, without regard to how the
   rights are labeled or categorized.

e. Licensed Material means the artistic or literary work, database, or other
   material to which the Licensor applied this Public License.

f. Licensed Rights means the rights granted to You subject to the terms and
   conditions of this Public License, which are limited to all Copyright and
   Similar Rights that apply to Your use of the Licensed Material and that the
   Licensor has authority to license.

g. Licensor means the individual(s) or entity(ies) granting rights under this
   Public License.

h. Share means to provide material to the public by any means or process that
   requires permission under the Licensed Rights, such as reproduction, public
   display, public performance, distribution, dissemination, communication, or
   importation, and to make material available to the public including in ways
   that members of the public may access the material from a place and at a time
   individually chosen by them.

i. ShareAlike means that any Adapted Material must be licensed under the same,
   a similar, or a BY-SA Compatible License.

j. You means the individual or entity exercising the Licensed Rights under this
   Public License. Your has a corresponding meaning.

For the full license text, see:
https://creativecommons.org/licenses/by-sa/4.0/legalcode

---

ATTRIBUTION AND SHAREALIKE REQUIREMENTS:

When using this work, you must:

1. Provide attribution:
   "Openword Lexicon Plus Distribution" by [contributors]
   Licensed under CC BY-SA 4.0
   https://creativecommons.org/licenses/by-sa/4.0/

2. License derivative works under CC BY-SA 4.0 or a compatible license

For detailed source attributions, see ATTRIBUTION.md
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    logger.info(f"Written: {output_path}")


def main():
    """Main attribution generation pipeline."""
    project_root = Path(__file__).parent.parent.parent
    data_root = project_root / "data"

    logger.info("Attribution and licensing")

    # Load source metadata
    sources = load_source_metadata(data_root / "raw")

    # Generate ATTRIBUTION.md
    attribution_path = project_root / "ATTRIBUTION.md"
    generate_attribution_md(sources, attribution_path)

    # Generate LICENSE files
    core_license_path = data_root / "core" / "LICENSE"
    generate_core_license(core_license_path)

    plus_license_path = data_root / "plus" / "LICENSE"
    generate_plus_license(plus_license_path)

    logger.info("")
    logger.info("Attribution and licensing complete")
    logger.info(f"  ATTRIBUTION.md: {len(sources)} sources documented")
    logger.info(f"  Core license: CC BY 4.0")
    logger.info(f"  Plus license: CC BY-SA 4.0")


if __name__ == '__main__':
    main()
