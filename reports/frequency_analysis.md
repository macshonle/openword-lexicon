# Frequency Data Analysis

## Overview

- **Total words**: 50,000
- **Total frequency count**: 725,119,374
- **Source**: FrequencyWords (OpenSubtitles 2018)

## Proposed Frequency Tiers

Tiers based on orders of magnitude:

| Tier | Rank Range | Word Count | Frequency Sum | Coverage % | Freq Range |
|------|------------|------------|---------------|------------|------------|
| Top 10 | 10 | 10 | 168,548,023 | 23.24% | 9,628,970 - 28,787,591 |
| 11 to 100 | 100 | 90 | 259,168,174 | 35.74% | 1,166,914 - 8,915,110 |
| 101 to 1000 | 1,000 | 900 | 180,108,690 | 24.84% | 54,085 - 1,153,915 |
| 1001 to 10000 | 10,000 | 9,000 | 92,124,841 | 12.70% | 2,510 - 54,026 |
| 10001 to 50000 | 50,000 | 40,000 | 25,169,646 | 3.47% | 159 - 2,510 |

## Interpretation

- **Top 10**: Ultra-common function words (the, of, and, to, etc.)
- **Top 100**: Core vocabulary for basic communication
- **Top 1,000**: Common everyday words
- **Top 10,000**: Standard educated vocabulary
- **Top 50,000**: Extensive vocabulary including technical terms
- **Rare**: Everything else (not in top 50k)

## Sample Words by Tier

### Top 10

Sample words:
```
you
i
the
to
a
's
it
and
that
't
```

### 11 to 100

Sample words:
```
of
is
in
what
we
me
this
he
for
my
...
then
had
or
been
our
gonna
tell
really
man
some
```

### 101 to 1000

Sample words:
```
say
hey
could
'd
didn
by
need
something
has
too
...
i-i
position
lieutenant
realize
lt
especially
machine
walking
art
pleasure
```

### 1001 to 10000

Sample words:
```
bloody
college
french
involved
cry
became
lived
impossible
obviously
neither
...
commence
plains
debra
readers
neglected
tavern
worthwhile
morale
cleaners
caviar
```

### 10001 to 50000

Sample words:
```
welcoming
kimberly
evaluation
f.
occurs
rituals
morton
disguised
precision
cube
...
jordans
unicycle
aaru
mati
pericardial
rolli
hyeon-to
redline
pho
buddy-buddy
```

## Usage in Filtering

For kids' word lists:
- Focus on **Top 1,000** to **Top 10,000** tiers
- Combine with concrete noun categories from Wiktionary/WordNet
- Filter out vulgar words even if high frequency

For game word lists:
- Include **Top 10,000** for common words
- Optionally extend to **Top 50,000** for variety
- Exclude archaic/obsolete even if they appear in frequency data

## Integration Strategy

1. Parse en_50k.txt into frequency tiers (1-5 + rare)
2. During word list export, join on word
3. Apply tier-based filters (e.g., `frequency_tier <= 4` for kids)
4. Combine with existing POS, label, and category filters
