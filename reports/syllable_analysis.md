# Syllable Data Analysis

## Overview

Analyzed 10,000 Wiktionary pages for syllable information.

## Availability

- **Pages with hyphenation templates**: 1,879 (18.79%)
- **Pages with IPA syllable markers**: 3,863 (38.63%)
- **Pages with either**: 4,148 (41.48%)

## Hyphenation Template Formats

- **pipe_separated**: 20 occurrences

## Hyphenation Examples

Sample words with hyphenation templates:

- **dictionary**: `en|dic|tion|a|ry||dic|tion|ary` (8 syllables)
- **thesaurus**: `en|the|saur|us` (4 syllables)
- **encyclopedia**: `en|en|cy|clo|pe|di|a` (7 syllables)
- **encyclopaedia**: `en|en|cy|clo|pae|dia` (6 syllables)
- **frei**: `pt|frei` (2 syllables)
- **cat**: `gd|cat` (2 syllables)
- **woordenboek**: `nl|woor|den|boek` (4 syllables)
- **gratis**: `en|grat|is` (3 syllables)
- **gratis**: `da|gra|tis` (3 syllables)
- **gratis**: `nl|gra|tis` (3 syllables)
- **gratis**: `gl|gra|tis` (3 syllables)
- **gratis**: `ms|gra|tis` (3 syllables)
- **gratis**: `ro|gra|tis` (3 syllables)
- **gratuit**: `fr|gra|tuit` (3 syllables)
- **gratuit**: `ro|gra|tu|it` (4 syllables)
- **livre**: `pt|li|vre` (3 syllables)
- **book**: `li|book` (2 syllables)
- **pound**: `ro|pound` (2 syllables)
- **pond**: `nl|pond` (2 syllables)
- **pies**: `nl|pies` (2 syllables)

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
    
    # Parse hyphenation content
    content = match.group(1)
    parts = content.split('|')
    
    # Count syllables (exclude parameters like lang=en)
    syllables = [p for p in parts if p.strip() and '=' not in p]
    
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
