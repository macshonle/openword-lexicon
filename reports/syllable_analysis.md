# Syllable Data Analysis

## Overview

Analyzed 10,000 Wiktionary pages for syllable information.

## Availability

- **Pages with hyphenation templates**: 1,879 (18.79%)
- **Pages with IPA syllable markers**: 3,863 (38.63%)
- **Pages with either**: 4,148 (41.48%)

## Hyphenation Template Formats

- **pipe_separated**: 31 occurrences
- **with_alternatives**: 1 occurrences

## Syllable Count Distribution

- **1 syllables**: 7 words
- **2 syllables**: 15 words
- **3 syllables**: 5 words
- **4 syllables**: 1 words
- **5 syllables**: 1 words
- **6 syllables**: 1 words
- **8 syllables**: 1 words

## Hyphenation Examples

Sample words with hyphenation templates (showing raw, parsed, and syllable count):

- **dictionary**: `en|dic|tion|a|ry||dic|tion|ary` → `dic|tion|a|ry` (4 syllables)
- **thesaurus**: `en|the|saur|us` → `the|saur|us` (3 syllables)
- **encyclopedia**: `en|en|cy|clo|pe|di|a` → `en|cy|clo|pe|di|a` (6 syllables)
- **encyclopaedia**: `en|en|cy|clo|pae|dia` → `en|cy|clo|pae|dia` (5 syllables)
- **frei**: `pt|frei` → `frei` (1 syllables)
- **cat**: `gd|cat` → `cat` (1 syllables)
- **woordenboek**: `nl|woor|den|boek` → `woor|den|boek` (3 syllables)
- **gratis**: `en|grat|is` → `grat|is` (2 syllables)
- **gratis**: `da|gra|tis` → `gra|tis` (2 syllables)
- **gratis**: `nl|gra|tis` → `gra|tis` (2 syllables)
- **gratis**: `gl|gra|tis` → `gra|tis` (2 syllables)
- **gratis**: `ms|gra|tis` → `gra|tis` (2 syllables)
- **gratis**: `ro|gra|tis` → `gra|tis` (2 syllables)
- **gratuit**: `fr|gra|tuit` → `gra|tuit` (2 syllables)
- **gratuit**: `ro|gra|tu|it` → `gra|tu|it` (3 syllables)
- **livre**: `pt|li|vre` → `li|vre` (2 syllables)
- **book**: `li|book` → `book` (1 syllables)
- **pound**: `ro|pound` → `pound` (1 syllables)
- **pond**: `nl|pond` → `pond` (1 syllables)
- **pies**: `nl|pies` → `pies` (1 syllables)
- **nonsense**: `en|non|sense` → `non|sense` (2 syllables)
- **A**: `nb|A` → `A` (1 syllables)
- **elephant**: `en|ele|phant` → `ele|phant` (2 syllables)
- **Wiktionary:Entry layout**: `en|sym|bol` → `sym|bol` (2 syllables)
- **Wiktionary:Entry layout**: `en|sym|bol` → `sym|bol` (2 syllables)

## IPA Syllable Examples

Sample words with IPA syllable markers:

- **dictionary**: `en|/ˈdɪk.ʃə.nə.ɹi/|/ˈdɪk.ʃən.ɹi/|/ˈdɪkʃ.nə.ɹi/|a=RP`
- **dictionary**: `en|/ˈdɪk.ʃəˌnɛ.ɹi/`
- **dictionary**: `en|/ˈɖɪkʃ(ə)nəri/|a=Indic`
- **thesaurus**: `en|/θɪˈsɔːɹəs/`
- **encyclopedia**: `en|/ənˌsəɪ.kləˈpi.di.ə/|a=Canada`
- **encyclopedia**: `en|/ɪnˌsaɪ.kləˈpi(ː).dɪə/|a=UK`
- **encyclopedia**: `en|/ɪnˌsaɪ.kləˈpi(ː).di.ə/|a=US`
- **portmanteau**: `en|/pɔːtˈmæn.təʊ/|a=RP`
- **portmanteau**: `en|/pɔːɹtˈmæntoʊ/|/ˌpɔːɹtmænˈtoʊ/`
- **encyclopaedia**: `en|/ɪnˌsaɪ.kləˈpi(ː).di.ə/|/ɛn-/|a=UK,US,Canada`
- **cat**: `enm|/ˈkat(ə)/|aa=from {{m|ang|catte`
- **cat**: `gd|/ˈkʰaʰt̪/|/ˈkʰaht̪/|ref={{R:gd:Oftedal`
- **cat**: `gd|/ˈkʰɵht̪/|[kʏ̞ɸd̪̊]|ref={{R:gd:Grannd|pages=44-45`
- **woordenboek**: `nl|/ˈʋoːrdə(n)ˌbuk/|[ˈʋʊːrdə(n)ˌbuk]`
- **gratis**: `en|/ˈɡɹɑː.tɪs/|a=UK`
- **gratis**: `en|/ˈɡɹætɪs/|a=US`
- **gratis**: `af|/ˈχrɑːtəs/|[ˈχrɔːtəs]`
- **gratis**: `da|/ɡraːtis/|[ˈɡ̊ʁɑːd̥is]`
- **gratis**: `nl|/ˈɣraːtɪs/`
- **gratis**: `de|/ˈɡʁaːtɪs/`

## Extraction Strategy

### Recommended Approach

1. **Use hyphenation templates when available**
   - Extract `{{hyphenation|...}}` content
   - Count pipe-separated segments (excluding lang= parameters)
   - Store as explicit syllable count

2. **Only include explicit data**
   - Do NOT estimate syllable counts
   - Only store count when hyphenation template exists
   - Leave syllable field null/absent for words without explicit data

3. **Integration with scanner parser**
   - Add optional `syllables` field to JSONL output
   - Only populate when hyphenation template found
   - Format: `"syllables": 3` (integer count)

### Implementation

```python
# In wiktionary_scanner_parser.py
HYPHENATION_RE = re.compile(r'\{\{(?:hyphenation|hyph)\|([^}]+)\}\}', re.I)

def extract_syllable_count(text: str) -> Optional[int]:
    """Extract syllable count from hyphenation template."""
    match = HYPHENATION_RE.search(text)
    if not match:
        return None
    
    content = match.group(1)
    
    # Handle alternatives (||)
    alternatives = content.split('||')
    first_alt = alternatives[0]
    
    # Parse pipe-separated segments
    parts = first_alt.split('|')
    
    # Filter syllables (exclude lang codes, parameters, empty)
    syllables = []
    for i, part in enumerate(parts):
        part = part.strip()
        if not part or '=' in part:
            continue
        # Skip 2-3 letter lang codes at start (en, da, en-US)
        if i == 0 and len(part) <= 3 and part.isalpha():
            continue
        syllables.append(part)
    
    return len(syllables) if syllables else None
```

### Output Format

Enhanced JSONL with optional syllable field:

```json
{
  "word": "example",
  "pos": ["noun"],
  "labels": {...},
  "is_phrase": false,
  "syllables": 3,  // Only present when hyphenation template found
  "sources": ["wikt"]
}
```
