# Frequency Data Analysis

## Overview

- **Total words**: 50,000
- **Total frequency count**: 725,119,374
- **Source**: FrequencyWords (OpenSubtitles 2018)

## Frequency Tiers (10-tier system)

Tiers based on linguistic breakpoints and educational use cases:

| Tier | Rank Range | Word Count | Description | Use Case |
|------|------------|------------|-------------|----------|
| top10 | 1-10 | 10 | Ultra-common function words | Essential particles |
| top100 | 11-100 | 90 | Core vocabulary | Basic communication |
| top300 | 101-300 | 200 | Early reader / sight words | Children's books (K-1) |
| top500 | 301-500 | 200 | Simple vocabulary | Elementary (Grade 2-3) |
| top1k | 501-1,000 | 500 | High-frequency everyday | Early elementary complete |
| top3k | 1,001-3,000 | 2,000 | Conversational fluency | ~95% comprehension |
| top10k | 3,001-10,000 | 7,000 | Educated vocabulary | General literacy |
| top25k | 10,001-25,000 | 15,000 | Extended vocabulary | Advanced learners |
| top50k | 25,001-50,000 | 25,000 | Rare/technical/variants | Specialized domains |
| rare | >50,000 | ∞ | Very rare/specialized | Not in dataset |

## Coverage Statistics (from OpenSubtitles 2018)

- **Top 10**: 23.24% of all word occurrences
- **Top 100**: 35.74% additional coverage (58.98% cumulative)
- **Top 1,000**: 24.84% additional coverage (83.82% cumulative)
- **Top 3,000**: ~95% comprehension threshold (key linguistic breakpoint)
- **Top 10,000**: 12.70% additional coverage
- **Top 50,000**: 3.47% additional coverage

## Interpretation

- **top10**: Ultra-common function words (the, of, and, to, etc.)
- **top100**: Core vocabulary for basic communication
- **top300**: Sight words for early readers (Grades K-1)
- **top500**: Simple children's book vocabulary (Grades 2-3)
- **top1k**: High-frequency everyday words
- **top3k**: Conversational fluency (~95% coverage) - critical threshold
- **top10k**: Standard educated vocabulary
- **top25k**: Extended vocabulary with specialized terms
- **top50k**: Rare words, technical terms, and variants
- **rare**: Everything else (not in top 50k frequency dataset)

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
- **Early readers (K-1)**: top300, top500
- **Elementary (2-5)**: top1k, top3k
- **Middle school**: top10k
- Combine with concrete noun categories from Wiktionary/WordNet
- Filter out vulgar words even if high frequency

For game word lists:
- **Simple games**: top1k, top3k (conversational fluency)
- **Standard games**: top10k (educated vocabulary)
- **Advanced games**: top25k, top50k (variety and challenge)
- Exclude archaic/obsolete even if they appear in frequency data

For language learning:
- **Beginner**: top300, top500, top1k
- **Intermediate**: top3k (95% comprehension threshold)
- **Advanced**: top10k, top25k
- Progressive difficulty based on tier

## Integration Strategy

1. Parse en_50k.txt into frequency tiers (10 tiers based on linguistic breakpoints)
2. During word list export, join on word
3. Apply tier-based filters using tier names or score ranges
4. Combine with existing POS, label, and category filters
5. Sort by frequency score for optimal learning/game order
