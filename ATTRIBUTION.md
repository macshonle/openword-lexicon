# ATTRIBUTION

This file lists **TASL** (Title, Author, Source, License) attributions for inputs used to build the Openword Lexicon datasets.

- **Code license:** Apache-2.0
- **Data licenses:**
  - **core:** CC0 1.0 (preferred) or CC BY 4.0 — choose one at release time and reflect it in `data/core/LICENSE`
  - **plus:** CC BY-SA 4.0 — required when including SA sources (e.g., Wiktionary, certain frequency lists)

The build produces two distributions. Keep this file in the repository and include it in all release archives. Regenerate as sources change.

---

## CORE INPUTS (PD/permissive only)

### ENABLE — Enhanced North American Benchmark LExicon
**Title:** ENABLE word list  
**Author:** Alan Beale; contributors (public domain release)  
**Source:** Public domain distribution mirrors (document in build manifest)  
**License:** Public Domain (CC0-compatible)  
**Notes:** A public-domain alternative to proprietary Scrabble lists; no restrictions on use.

### EOWL — English Open Word List (derived from UKACD)
**Title:** English Open Word List (EOWL)  
**Author:** Ken Loge; derived from UK Advanced Cryptics Dictionary (UKACD) by J. Ross Beresford; contributions by Alan Beale  
**Source:** EOWL distribution (document in build manifest)  
**License:** Unrestricted use with inclusion of the **UKACD notice** below  
**Required notice (verbatim):**
> The UK Advanced Cryptics Dictionary (UKACD) is © J Ross Beresford 1993–1999. Permission is granted to use this list for any purpose provided this notice is retained. No warranty is given.

### Optional PD sources (only if used)
**Title:** Moby word lists (various)  
**Author:** Grady Ward  
**Source:** Moby Project mirrors  
**License:** Public Domain  
**Notes:** Include only subsets confirmed PD; document exact files in the manifest.

---

## PLUS INPUTS (additional SA sources and enrichments)

### Wiktionary (English)
**Title:** Wiktionary (English) — pages-articles dump (specific date in manifest)  
**Author:** Wiktionary contributors  
**Source:** dumps.wikimedia.org (exact dump URL in manifest)  
**License:** CC BY-SA 4.0  
**Required attribution:** “This dataset includes material from Wiktionary (https://www.wiktionary.org/), available under the Creative Commons Attribution-ShareAlike License (CC BY-SA 4.0). See individual page histories for authorship.”

### WordNet (Princeton)
**Title:** Princeton WordNet (version noted in manifest)  
**Author:** Princeton University  
**Source:** wordnet.princeton.edu (exact package in manifest)  
**License:** WordNet license (free to use and redistribute with attribution)  
**Recommended citation:** “Miller, G. A. (1995). WordNet: A Lexical Database for English. *Communications of the ACM*, 38(11), 39–41.”  
**Trademark:** WordNet® is a registered trademark of Princeton University.

### Frequency data (choose one; document precisely in manifest)
- **OpenSubtitles word frequency (InvokeIT or equivalent)**  
  **License:** CC BY-SA 4.0  
  **Attribution:** Include project name, URL, and license link.
- **Wikipedia-derived frequency lists**  
  **License:** CC BY-SA 4.0  
  **Attribution:** “This dataset includes material derived from Wikipedia (https://www.wikipedia.org/), available under CC BY-SA 4.0.”
- **Other frequency sources**  
  **License:** Ensure compatibility; include exact TASL block here.

---

## GENERATED FILES AND PROVENANCE

- The build emits `data/LICENSE` for each distribution:
  - `data/core/LICENSE` → CC0 1.0 (or CC BY 4.0 if chosen)
  - `data/plus/LICENSE` → CC BY-SA 4.0
- The build emits `ATTRIBUTION.md` (this file) and a machine-readable `MANIFEST.json` listing:
  - Input files (paths/URLs), versions or dump dates
  - SHA-256 checksums
  - License identifiers for each input
- When distributing **plus** artifacts, ensure **ShareAlike**: downstream modifications must be licensed under **CC BY-SA 4.0** with proper attribution.

## HOW TO UPDATE THIS FILE

1. Add/remove input sources in the build.  
2. Update TASL entries here (or auto-generate from `SOURCE.json` files).  
3. Re-run the attribution generator during the release process.  
4. Verify that all downstream artifacts include this file and the appropriate `data/LICENSE`.
