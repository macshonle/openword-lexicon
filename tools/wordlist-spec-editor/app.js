/**
 * OpenWord Lexicon - Advanced Word List Builder
 * Interactive web application for building custom word lists
 */

// ============================================================================
// STATE MANAGEMENT
// ============================================================================

const state = {
    sources: {
        eowl: true,
        wiktionary: true,
        wordnet: true,
        brysbaert: false,  // Unchecked by default
        frequency: true
    },
    filters: [],  // Array of filter objects
    nextFilterId: 1,
    pendingQuickFilter: {
        wordType: 'any',
        syllableData: 'any'
    }
};

// Build statistics - loaded from build-statistics.json
let BUILD_STATS = null;

// Default fallback statistics (will be replaced by actual data)
const DEFAULT_STATS = {
    totalWords: 1303681,
    eowl: 129037,
    wiktionary: 1294779,
    wordnet: 90931,
    brysbaert: 39558,
    posAvailable: 0.984,
    labelsAvailable: 0.112,
    concretenessAvailable: 0.086,
    regionalAvailable: 0.019
};

// ============================================================================
// CHARACTER PRESETS
// ============================================================================

const CHAR_PRESETS = {
    'standard': {
        label: 'Standard letters (a-z)',
        allowedChars: 'a-z',
        description: 'lowercase letters only'
    },
    'contractions': {
        label: 'Letters + apostrophes (a-z\')',
        allowedChars: 'a-z\'',
        description: 'lowercase letters and apostrophes'
    },
    'alphanumeric': {
        label: 'Letters + numbers (a-z0-9)',
        allowedChars: 'a-z0-9',
        description: 'lowercase letters and digits'
    },
    'hyphenated': {
        label: 'Letters + hyphens (a-z-)',
        allowedChars: 'a-z-',
        description: 'lowercase letters and hyphens'
    },
    'common-punct': {
        label: 'Letters + common punctuation (a-z\'-)',
        allowedChars: 'a-z\'-',
        description: 'lowercase letters, apostrophes, and hyphens'
    },
    'any': {
        label: 'Any characters',
        allowedChars: '',
        description: 'no character restrictions'
    }
};

// ============================================================================
// FILTER DEFINITIONS
// ============================================================================

const FILTER_TYPES = {
    character: {
        title: 'Character Filter',
        icon: '🔤',
        requires: [],
        configFields: [
            { type: 'preset-select', name: 'charPreset', label: 'Allowed Characters', defaultValue: 'standard' },
            { type: 'length-row', names: ['minLength', 'maxLength'], labels: ['Min Length', 'Max Length'], min: 1 },
            { type: 'text', name: 'startsWith', label: 'Starts With', placeholder: 'e.g., un,pre,re (comma-separated, matches any)', hint: 'Comma-separated prefixes - matches words starting with ANY of these' },
            { type: 'text', name: 'excludeStartsWith', label: 'Doesn\'t Start With', placeholder: 'e.g., x,z (comma-separated)', hint: 'Comma-separated prefixes to exclude' },
            { type: 'text', name: 'endsWith', label: 'Ends With', placeholder: 'e.g., ing,ed,s (comma-separated, matches any)', hint: 'Comma-separated suffixes - matches words ending with ANY of these' },
            { type: 'text', name: 'excludeEndsWith', label: 'Doesn\'t End With', placeholder: 'e.g., ly,ness (comma-separated)', hint: 'Comma-separated suffixes to exclude' },
            { type: 'text', name: 'contains', label: 'Contains', placeholder: 'e.g., tion,ing (comma-separated, must have all)', hint: 'Comma-separated sequences - word must contain ALL of these' },
            { type: 'text', name: 'excludeContains', label: 'Doesn\'t Contain', placeholder: 'e.g., \',- (individual characters)', hint: 'Individual characters to exclude' }
        ]
    },
    phrase: {
        title: 'Phrase Filter',
        icon: '💬',
        requires: [],
        configFields: [
            { type: 'checkbox', name: 'multiWord', label: 'Multi-word phrases only', defaultChecked: true },
            { type: 'checkbox', name: 'singleWord', label: 'Single words only', defaultChecked: false },
            { type: 'length-row', names: ['minWords', 'maxWords'], labels: ['Min Words', 'Max Words'], min: 1 }
        ]
    },
    pos: {
        title: 'Part of Speech Filter',
        icon: '📝',
        requires: ['wiktionary', 'wordnet'],
        configFields: [
            { type: 'multiselect', name: 'pos', label: 'Select Parts of Speech', options: [
                'noun', 'verb', 'adjective', 'adverb', 'pronoun',
                'preposition', 'conjunction', 'interjection', 'determiner',
                'particle', 'numeral', 'article', 'postposition'
            ]}
        ]
    },
    frequency: {
        title: 'Frequency Filter',
        icon: '📊',
        requires: ['frequency'],
        configFields: [
            { type: 'select', name: 'minTier', label: 'Minimum Frequency (most common)', options: [
                { value: 'A', label: 'A - Most common (rank 1)' },
                { value: 'B', label: 'B - Very common (rank 2-3)' },
                { value: 'C', label: 'C - Common (rank 4-5)' },
                { value: 'D', label: 'D - Frequent (rank 6-10)' },
                { value: 'E', label: 'E - Regular (rank 11-17)' },
                { value: 'F', label: 'F - Standard (rank 18-31)' },
                { value: 'G', label: 'G - Moderate (rank 32-56)' },
                { value: 'H', label: 'H - Less frequent (rank 57-100)' },
                { value: 'T', label: 'T - Top 75k' },
                { value: 'Z', label: 'Z - Any (unranked)' }
            ]},
            { type: 'select', name: 'maxTier', label: 'Maximum Frequency (least common)', options: [
                { value: 'A', label: 'A - Most common only' },
                { value: 'C', label: 'C - Common' },
                { value: 'E', label: 'E - Regular' },
                { value: 'H', label: 'H - Less frequent' },
                { value: 'T', label: 'T - Top 75k' },
                { value: 'Z', label: 'Z - Any (unranked)' }
            ]}
        ]
    },
    region: {
        title: 'Regional Filter',
        icon: '🌍',
        requires: ['wiktionary'],
        configFields: [
            { type: 'multiselect', name: 'regions', label: 'Select Regions', options: [
                'en-GB', 'en-US', 'en-AU', 'en-CA', 'en-NZ', 'en-ZA', 'en-IE', 'en-IN'
            ]}
        ]
    },
    concreteness: {
        title: 'Concreteness Filter',
        icon: '🎨',
        requires: ['wordnet', 'brysbaert'],
        configFields: [
            { type: 'multiselect', name: 'concreteness', label: 'Select Concreteness Levels', options: [
                'concrete', 'mixed', 'abstract'
            ]},
            { type: 'checkbox', name: 'preferBrysbaert', label: 'Prefer Brysbaert ratings over WordNet', defaultChecked: true }
        ]
    },
    labels: {
        title: 'Labels Filter',
        icon: '🏷️',
        requires: ['wiktionary'],
        configFields: [
            { type: 'multiselect', name: 'labels', label: 'Select Labels', options: [
                'vulgar', 'offensive', 'slang', 'informal', 'formal',
                'archaic', 'obsolete', 'dated', 'rare',
                'colloquial', 'dialectal', 'technical', 'literary',
                'humorous', 'derogatory', 'euphemistic'
            ]}
        ]
    },
    syllable: {
        title: 'Syllable Filter',
        icon: '🔢',
        requires: ['wiktionary'],
        configFields: [
            { type: 'length-row', names: ['minSyllables', 'maxSyllables'], labels: ['Min Syllables', 'Max Syllables'], min: 1 },
            { type: 'number', name: 'exact', label: 'Exact Syllables', min: 1, placeholder: 'e.g., 2 (overrides min/max)' },
            { type: 'checkbox', name: 'requireSyllables', label: 'Require syllable data (exclude words without syllable info)', defaultChecked: false }
        ]
    }
};

// ============================================================================
// DEMO PRESETS
// ============================================================================

const DEMOS = {
    wordle: {
        name: 'Wordle Words',
        sources: { eowl: true, wiktionary: true, wordnet: true, brysbaert: false, frequency: true },
        filters: [
            {
                type: 'character',
                mode: 'include',
                config: { minLength: 5, maxLength: 5, charPreset: 'standard', excludeContains: '\'-' },
                summary: '5 letters, lowercase letters only, no contractions'
            },
            {
                type: 'frequency',
                mode: 'include',
                config: { minTier: 'A', maxTier: 'H' },
                summary: 'Common words (A-H)'
            },
            {
                type: 'phrase',
                mode: 'include',
                config: { singleWord: true },
                summary: 'Single words only'
            }
        ]
    },
    'kids-nouns': {
        name: 'Kids Game (Concrete Nouns)',
        sources: { eowl: true, wiktionary: true, wordnet: true, brysbaert: true, frequency: true },
        filters: [
            {
                type: 'pos',
                mode: 'include',
                config: { pos: ['noun'] },
                summary: 'Nouns only'
            },
            {
                type: 'concreteness',
                mode: 'include',
                config: { concreteness: ['concrete'], preferBrysbaert: true },
                summary: 'Concrete words'
            },
            {
                type: 'character',
                mode: 'include',
                config: { minLength: 3, maxLength: 10 },
                summary: '3-10 letters'
            },
            {
                type: 'frequency',
                mode: 'include',
                config: { minTier: 'A', maxTier: 'G' },
                summary: 'Common words (A-G)'
            },
            {
                type: 'labels',
                mode: 'exclude',
                config: { labels: ['vulgar', 'offensive', 'slang'] },
                summary: 'No vulgar/offensive/slang'
            }
        ]
    },
    scrabble: {
        name: 'Scrabble Words',
        sources: { eowl: true, wiktionary: true, wordnet: true, brysbaert: false, frequency: false },
        filters: [
            {
                type: 'phrase',
                mode: 'include',
                config: { singleWord: true },
                summary: 'Single words only'
            },
            {
                type: 'character',
                mode: 'include',
                config: { minLength: 2, maxLength: 15, charPreset: 'standard' },
                summary: '2-15 letters, standard letters only'
            }
        ]
    },
    profanity: {
        name: 'Profanity Blocklist',
        sources: { eowl: false, wiktionary: true, wordnet: false, brysbaert: false, frequency: false },
        filters: [
            {
                type: 'labels',
                mode: 'include',
                config: { labels: ['vulgar', 'offensive'] },
                summary: 'Vulgar or offensive words'
            }
        ]
    },
    'british-common': {
        name: 'British English Common Words',
        sources: { eowl: true, wiktionary: true, wordnet: false, brysbaert: false, frequency: true },
        filters: [
            {
                type: 'region',
                mode: 'include',
                config: { regions: ['en-GB'] },
                summary: 'British English'
            },
            {
                type: 'frequency',
                mode: 'include',
                config: { minTier: 'A', maxTier: 'E' },
                summary: 'Common words (A-E)'
            }
        ]
    },
    'childrens-reading': {
        name: "Children's Reading",
        sources: { eowl: true, wiktionary: true, wordnet: true, brysbaert: true, frequency: true },
        filters: [
            {
                type: 'syllable',
                mode: 'include',
                config: { minSyllables: 1, maxSyllables: 2 },
                summary: '1-2 syllables'
            },
            {
                type: 'character',
                mode: 'include',
                config: { minLength: 3, maxLength: 8 },
                summary: '3-8 letters'
            },
            {
                type: 'frequency',
                mode: 'include',
                config: { minTier: 'A', maxTier: 'F' },
                summary: 'Common words (A-F)'
            },
            {
                type: 'phrase',
                mode: 'include',
                config: { singleWord: true },
                summary: 'Single words only'
            },
            {
                type: 'labels',
                mode: 'exclude',
                config: { labels: ['vulgar', 'offensive', 'slang'] },
                summary: 'No vulgar/offensive/slang'
            }
        ]
    },
    'prefix-game': {
        name: 'Prefix Game',
        sources: { eowl: true, wiktionary: true, wordnet: true, brysbaert: false, frequency: true },
        filters: [
            {
                type: 'character',
                mode: 'include',
                config: {
                    startsWith: ['un', 're', 'pre', 'dis', 'mis', 'over'],
                    minLength: 4,
                    charPreset: 'standard'
                },
                summary: 'Starts with "un", "re", "pre", "dis", "mis", or "over", 4+ letters, standard letters only'
            },
            {
                type: 'frequency',
                mode: 'include',
                config: { minTier: 'A', maxTier: 'G' },
                summary: 'Common words (A-G)'
            },
            {
                type: 'phrase',
                mode: 'include',
                config: { singleWord: true },
                summary: 'Single words only'
            }
        ]
    },
    'no-special-chars': {
        name: 'No Special Characters',
        sources: { eowl: true, wiktionary: true, wordnet: true, brysbaert: false, frequency: true },
        filters: [
            {
                type: 'character',
                mode: 'include',
                config: {
                    charPreset: 'standard',
                    minLength: 3,
                    maxLength: 12
                },
                summary: '3-12 letters, lowercase only (no apostrophes, hyphens, etc.)'
            },
            {
                type: 'frequency',
                mode: 'include',
                config: { minTier: 'A', maxTier: 'H' },
                summary: 'Common words (A-H)'
            },
            {
                type: 'phrase',
                mode: 'include',
                config: { singleWord: true },
                summary: 'Single words only'
            }
        ]
    }
};

// ============================================================================
// STATISTICS LOADING
// ============================================================================

async function loadBuildStatistics() {
    try {
        const response = await fetch('build-statistics.json');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        BUILD_STATS = await response.json();
        console.log('Build statistics loaded:', BUILD_STATS);

        // Update source counts in UI
        updateSourceCounts();
    } catch (error) {
        console.warn('Failed to load build-statistics.json, using defaults:', error);
        BUILD_STATS = null;
    }
}

function updateSourceCounts() {
    if (!BUILD_STATS || !BUILD_STATS.sources) return;

    // Update individual source counts
    const sourceMapping = {
        'eowl': 'eowl',
        'wiktionary': 'wikt'
    };

    for (const [uiSource, dataSource] of Object.entries(sourceMapping)) {
        const count = BUILD_STATS.sources[dataSource];
        if (count !== undefined) {
            const element = document.getElementById(`source-count-${uiSource}`);
            if (element) {
                element.textContent = `${count.toLocaleString()} words`;
            }
        }
    }
}

function getStats() {
    return BUILD_STATS || DEFAULT_STATS;
}

/**
 * Estimate word count for a union of selected sources.
 *
 * BACKGROUND: source_combinations partition the lexicon into DISJOINT sets based on
 * which sources contributed to each word. Think of it like a Venn diagram where each
 * region is labeled with which circles it's in:
 *   - "wikt": 1,095,480 = words ONLY in Wiktionary (not in eowl)
 *   - "eowl": 3,252 = words ONLY in EOWL (not in wikt)
 *   - "eowl,wikt": 32,126 = words in BOTH eowl AND wikt
 *
 * WHY WE CAN'T JUST USE TOTALS: When a user selects sources, they want a UNION
 * (all words from ANY selected source). We can't precompute all possible unions
 * because with N sources there are 2^N possibilities. Instead, we compute unions
 * on-the-fly using the intersection principle:
 *
 * INTERSECTION PRINCIPLE: Include a combination if ANY of its sources are selected.
 *   User selects ["eowl"]:
 *     - "wikt" ✗ (no overlap with {eowl})
 *     - "eowl" ✓ (eowl ∈ {eowl})
 *     - "eowl,wikt" ✓ (eowl ∈ {eowl})  ← words from EOWL that are also in wikt
 *   Total: 3,252 + 32,126 = ~35,378 words (placeholder numbers)
 *
 *   User selects ["wikt", "eowl"]:
 *     - "wikt" ✓ (wikt ∈ {wikt, eowl})
 *     - "eowl" ✓ (eowl ∈ {wikt, eowl})
 *     - "eowl,wikt" ✓ (both sources in {wikt, eowl})
 *   Total: 1,095,480 + 3,252 + 32,126 = 1,130,858 words
 *
 * WHY ADDITION WORKS: Since combinations are disjoint (no word appears in multiple
 * combinations), summing them gives the exact union count.
 */
function estimateWordCount(selectedSources) {
    // If we have detailed statistics, use them for accurate estimates
    if (BUILD_STATS && BUILD_STATS.source_combinations) {
        // Union operation: sum all disjoint combinations that have any overlap with selection
        let totalWords = 0;
        for (const [combo, data] of Object.entries(BUILD_STATS.source_combinations)) {
            const comboSources = combo.split(',');

            // Include this combination if ANY of its sources are in the selected sources
            const hasOverlap = comboSources.some(s => selectedSources.includes(s));
            if (hasOverlap) {
                const count = data.count;
                totalWords += count;
            }
        }

        return totalWords;
    }

    // Fallback to simple estimates (less accurate, doesn't handle unions properly)
    const stats = getStats();
    if (selectedSources.includes('wiktionary')) {
        return stats.wiktionary;
    } else if (selectedSources.includes('eowl')) {
        return stats.eowl;
    } else if (selectedSources.includes('enable')) {
        return stats.enable || 172823;
    }

    return 0;
}

/**
 * Compute metadata coverage for a union of selected sources.
 *
 * Similar to word count estimation, we sum metadata counts from all disjoint
 * source combinations that are subsets of the selection. This gives accurate
 * coverage statistics for the union.
 *
 * @param {string[]} selectedSources - Array of selected source IDs
 * @returns {Object} Metadata coverage with counts and percentages
 */
function computeMetadataCoverage(selectedSources) {
    if (!BUILD_STATS || !BUILD_STATS.metadata_by_combination) {
        // Fallback to global stats
        return BUILD_STATS ? BUILD_STATS.metadata_coverage : null;
    }

    // Accumulate counts across all relevant combinations
    const totals = {
        total_words: 0,
        with_pos: 0,
        with_any_labels: 0,
        with_register: 0,
        with_domain: 0,
        with_region: 0,
        with_temporal: 0,
        with_concreteness: 0,
        with_frequency: 0,
        multi_word: 0,
        nouns: 0,
        nouns_with_concrete: 0,
    };

    // Sum counts from all matching combinations (disjoint union)
    for (const [combo, metadata] of Object.entries(BUILD_STATS.metadata_by_combination)) {
        const comboSources = combo.split(',');
        const hasOverlap = comboSources.some(s => selectedSources.includes(s));

        if (hasOverlap) {
            totals.total_words += metadata.total;
            totals.with_pos += metadata.pos_tags.count;
            totals.with_any_labels += metadata.any_labels.count;
            totals.with_register += metadata.register_labels.count;
            totals.with_domain += metadata.domain_labels.count;
            totals.with_region += metadata.region_labels.count;
            totals.with_temporal += metadata.temporal_labels.count;
            totals.with_concreteness += metadata.concreteness.count;
            totals.with_frequency += metadata.frequency_tier.count;
            totals.multi_word += metadata.multi_word_phrases.count;
            totals.nouns += metadata.concreteness_nouns.total_nouns;
            totals.nouns_with_concrete += metadata.concreteness_nouns.count;
        }
    }

    // Compute percentages
    const total = totals.total_words;
    return {
        pos_tags: {
            count: totals.with_pos,
            percentage: total > 0 ? Math.round(100 * totals.with_pos / total * 10) / 10 : 0
        },
        any_labels: {
            count: totals.with_any_labels,
            percentage: total > 0 ? Math.round(100 * totals.with_any_labels / total * 10) / 10 : 0
        },
        register_labels: {
            count: totals.with_register,
            percentage: total > 0 ? Math.round(100 * totals.with_register / total * 10) / 10 : 0
        },
        domain_labels: {
            count: totals.with_domain,
            percentage: total > 0 ? Math.round(100 * totals.with_domain / total * 10) / 10 : 0
        },
        region_labels: {
            count: totals.with_region,
            percentage: total > 0 ? Math.round(100 * totals.with_region / total * 10) / 10 : 0
        },
        temporal_labels: {
            count: totals.with_temporal,
            percentage: total > 0 ? Math.round(100 * totals.with_temporal / total * 10) / 10 : 0
        },
        concreteness: {
            count: totals.with_concreteness,
            percentage: total > 0 ? Math.round(100 * totals.with_concreteness / total * 10) / 10 : 0
        },
        concreteness_nouns: {
            count: totals.nouns_with_concrete,
            total_nouns: totals.nouns,
            percentage: totals.nouns > 0 ? Math.round(100 * totals.nouns_with_concrete / totals.nouns * 10) / 10 : 0
        },
        frequency_tier: {
            count: totals.with_frequency,
            percentage: total > 0 ? Math.round(100 * totals.with_frequency / total * 10) / 10 : 0
        },
        multi_word_phrases: {
            count: totals.multi_word,
            percentage: total > 0 ? Math.round(100 * totals.multi_word / total * 10) / 10 : 0
        }
    };
}

/**
 * Determine the resulting license for a combination of selected sources.
 * Uses the source_combinations data (which includes licenses) to find the most
 * restrictive license that applies.
 *
 * @param {string[]} selectedSources - Array of selected source IDs
 * @returns {Object} License information {id, description, sources}
 */
function computeLicense(selectedSources) {
    if (!BUILD_STATS || !BUILD_STATS.source_combinations) {
        // Fallback to hardcoded logic
        return computeLicenseFallback(selectedSources);
    }

    // Normalize source names (map UI names to data names)
    const sourceMap = {
        'wiktionary': 'wikt',
        'eowl': 'eowl',
        'wordnet': 'wordnet',
        'brysbaert': 'brysbaert',
        'frequency': 'frequency'
    };
    const normalizedSources = selectedSources.map(s => sourceMap[s] || s);

    // Find all licenses that will be included in the union
    const allLicenses = new Set();
    for (const [combo, data] of Object.entries(BUILD_STATS.source_combinations)) {
        const comboSources = combo.split(',');
        // Include this combination if ANY of its sources are selected
        const hasOverlap = comboSources.some(s => normalizedSources.includes(s));
        if (hasOverlap && data.licenses) {
            // Add all licenses from this combination
            data.licenses.split(',').forEach(lic => allLicenses.add(lic));
        }
    }

    // Determine the most restrictive license
    // Priority: CC-BY-SA-4.0 > WordNet > UKACD
    let license = '';
    let licenseDesc = '';
    const sources = [];

    if (allLicenses.has('CC-BY-SA-4.0')) {
        license = 'CC BY-SA 4.0';
        licenseDesc = 'Attribution + ShareAlike required';
    } else if (allLicenses.has('WordNet')) {
        license = 'WordNet License';
        licenseDesc = 'WordNet License terms apply';
    } else if (allLicenses.has('UKACD')) {
        license = 'UKACD License';
        licenseDesc = 'UKACD License terms apply';
    }

    // Build source list
    if (selectedSources.includes('wiktionary')) sources.push('Wiktionary (CC BY-SA 4.0)');
    if (selectedSources.includes('eowl')) sources.push('EOWL (UKACD License)');
    if (selectedSources.includes('wordnet')) sources.push('WordNet (WordNet License)');
    if (selectedSources.includes('brysbaert')) sources.push('Brysbaert (Research Use)');
    if (selectedSources.includes('frequency')) sources.push('Frequency Data (CC BY-SA 4.0)');

    return { license, licenseDesc, sources };
}

function computeLicenseFallback(selectedSources) {
    // License hierarchy (most restrictive first)
    // CC BY-SA 4.0 is most restrictive (requires attribution + share-alike)
    let license = 'CC BY 4.0';
    let licenseDesc = 'Attribution required';
    const sources = [];

    if (selectedSources.includes('wiktionary')) {
        license = 'CC BY-SA 4.0';
        licenseDesc = 'Attribution + ShareAlike required';
        sources.push('Wiktionary (CC BY-SA 4.0)');
    }

    if (selectedSources.includes('eowl')) {
        sources.push('EOWL (UKACD License)');
    }

    if (selectedSources.includes('wordnet')) {
        sources.push('WordNet (WordNet License)');
    }

    if (selectedSources.includes('brysbaert')) {
        sources.push('Brysbaert (Research Use)');
    }

    if (selectedSources.includes('frequency')) {
        if (!selectedSources.includes('wiktionary')) {
            license = 'CC BY-SA 4.0';
            licenseDesc = 'Attribution + ShareAlike required';
        }
        sources.push('Frequency Data (CC BY-SA 4.0)');
    }

    return { license, licenseDesc, sources };
}

// ============================================================================
// QUICK FILTERS (Builder Mode)
// ============================================================================

function initializeQuickFilters() {
    // Handle quick filter button clicks
    document.querySelectorAll('.quick-filter-buttons').forEach(buttonGroup => {
        const filterType = buttonGroup.dataset.filterType;

        buttonGroup.querySelectorAll('.quick-filter-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                // Deactivate siblings
                buttonGroup.querySelectorAll('.quick-filter-btn').forEach(b => b.classList.remove('active'));
                // Activate clicked button
                btn.classList.add('active');

                // Update pending state instead of applying immediately
                updateQuickFilterSelection(filterType, btn.dataset.value);
            });
        });
    });

    // Handle "Add Filter" button
    const addBtn = document.getElementById('quick-filter-add');
    if (addBtn) {
        addBtn.addEventListener('click', applyPendingQuickFilter);
    }
}

function updateQuickFilterSelection(filterType, value) {
    // Map filter types to state keys
    const stateKeyMap = {
        'word-type': 'wordType',
        'syllable-data': 'syllableData'
    };

    const stateKey = stateKeyMap[filterType];
    if (stateKey) {
        state.pendingQuickFilter[stateKey] = value;
    }

    updateQuickFilterPreview();
}

function updateQuickFilterPreview() {
    const preview = document.getElementById('quick-filter-preview');
    const description = document.getElementById('quick-filter-description');
    const warning = document.getElementById('quick-filter-warning');
    const warningText = document.getElementById('quick-filter-warning-text');
    const addBtn = document.getElementById('quick-filter-add');

    // Compute what filter would be created
    const filterToAdd = computeQuickFilter(state.pendingQuickFilter);

    // If no filter (all "any"), hide preview
    if (!filterToAdd) {
        preview.style.display = 'none';
        return;
    }

    // Show preview
    preview.style.display = 'block';
    description.textContent = filterToAdd.summary;

    // Validate filter
    const validation = validateFilter(filterToAdd);

    if (validation.warning) {
        warning.style.display = 'block';
        warningText.textContent = validation.warning;
        addBtn.disabled = validation.blocking;
    } else {
        warning.style.display = 'none';
        addBtn.disabled = false;
    }
}

function computeQuickFilter(pending) {
    const filters = [];

    // Word Type filter
    if (pending.wordType !== 'any') {
        if (pending.wordType === 'single') {
            filters.push({
                type: 'phrase',
                mode: 'include',
                config: { singleWord: true },
                summary: 'Single words only'
            });
        } else if (pending.wordType === 'phrases') {
            filters.push({
                type: 'phrase',
                mode: 'include',
                config: { multiWord: true },
                summary: 'Phrases only'
            });
        }
    }

    // Syllable Data filter
    if (pending.syllableData !== 'any') {
        if (pending.syllableData === 'required') {
            filters.push({
                type: 'syllable',
                mode: 'include',
                config: { requireSyllables: true },
                summary: 'Syllable data required'
            });
        }
    }

    // If no non-"any" selections, return null
    if (filters.length === 0) {
        return null;
    }

    // If only one filter, return it directly
    if (filters.length === 1) {
        return filters[0];
    }

    // If multiple filters, create a composite description
    return {
        type: 'composite',
        filters: filters,
        summary: filters.map(f => f.summary).join(' + ')
    };
}

function validateFilter(filterToAdd) {
    // Check for redundancy and conflicts with existing filters
    for (const existing of state.filters) {
        if (filtersEquivalent(existing, filterToAdd)) {
            return {
                warning: 'This filter (or an equivalent one) already exists',
                blocking: true
            };
        }

        if (filtersConflict(existing, filterToAdd)) {
            return {
                warning: 'This contradicts an existing filter',
                blocking: true
            };
        }
    }

    return { warning: null, blocking: false };
}

function filtersEquivalent(filter1, filter2) {
    // Handle composite filters
    if (filter1.type === 'composite' && filter2.type === 'composite') {
        // Check if they have the same set of sub-filters
        if (filter1.filters.length !== filter2.filters.length) {
            return false;
        }
        // Simple check: same summaries
        return filter1.summary === filter2.summary;
    }

    // Handle composite vs non-composite
    if (filter1.type === 'composite' || filter2.type === 'composite') {
        return false;
    }

    // Same type and mode
    if (filter1.type !== filter2.type || filter1.mode !== filter2.mode) {
        return false;
    }

    // Check config equivalence (simple JSON comparison)
    return JSON.stringify(filter1.config) === JSON.stringify(filter2.config);
}

function filtersConflict(filter1, filter2) {
    // Check for contradictory filters
    // Example: singleWord=true conflicts with multiWord=true

    // Handle composite filters
    if (filter1.type === 'composite') {
        return filter1.filters.some(f => filtersConflict(f, filter2));
    }
    if (filter2.type === 'composite') {
        return filter2.filters.some(f => filtersConflict(filter1, f));
    }

    // Phrase filters: singleWord conflicts with multiWord
    if (filter1.type === 'phrase' && filter2.type === 'phrase') {
        const single1 = filter1.config.singleWord;
        const single2 = filter2.config.singleWord;
        const multi1 = filter1.config.multiWord;
        const multi2 = filter2.config.multiWord;

        if (single1 && multi2) return true;
        if (multi1 && single2) return true;
    }

    return false;
}

function applyPendingQuickFilter() {
    const filterToAdd = computeQuickFilter(state.pendingQuickFilter);

    if (!filterToAdd) {
        return;
    }

    // Handle composite filters by adding each sub-filter
    if (filterToAdd.type === 'composite') {
        filterToAdd.filters.forEach(f => {
            const filter = {
                id: state.nextFilterId++,
                type: f.type,
                mode: f.mode,
                config: f.config,
                summary: f.summary
            };
            state.filters.push(filter);
        });
    } else {
        const filter = {
            id: state.nextFilterId++,
            type: filterToAdd.type,
            mode: filterToAdd.mode,
            config: filterToAdd.config,
            summary: filterToAdd.summary
        };
        state.filters.push(filter);
    }

    // Reset pending quick filter to "any"
    state.pendingQuickFilter = {
        wordType: 'any',
        syllableData: 'any'
    };

    // Reset UI buttons
    document.querySelectorAll('.quick-filter-btn').forEach(btn => {
        if (btn.dataset.value === 'any') {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    // Hide preview
    document.getElementById('quick-filter-preview').style.display = 'none';

    updateUI();
}

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', async () => {
    // Load build statistics
    await loadBuildStatistics();

    initializeSourceCheckboxes();
    initializeFilterButtons();
    initializeQuickFilters();
    initializeDemoSelector();
    initializeExportButtons();
    initializeResizeHandle();
    updateUI();
});

// ============================================================================
// PANEL RESIZING
// ============================================================================

function initializeResizeHandle() {
    const resizeHandle = document.getElementById('resize-handle');
    const leftPanel = document.querySelector('.left-panel');
    const mainContent = document.querySelector('.main-content');

    let isResizing = false;
    let startX = 0;
    let startWidth = 0;

    resizeHandle.addEventListener('mousedown', (e) => {
        isResizing = true;
        startX = e.clientX;
        startWidth = leftPanel.offsetWidth;

        resizeHandle.classList.add('resizing');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';

        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;

        const deltaX = e.clientX - startX;
        const newWidth = startWidth + deltaX;

        // Get min and max constraints
        const minWidth = parseFloat(getComputedStyle(leftPanel).minWidth);
        const maxWidth = mainContent.offsetWidth * 0.75; // Max 75% of total width

        // Apply constraints
        if (newWidth >= minWidth && newWidth <= maxWidth) {
            leftPanel.style.width = newWidth + 'px';
        }
    });

    document.addEventListener('mouseup', () => {
        if (isResizing) {
            isResizing = false;
            resizeHandle.classList.remove('resizing');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        }
    });
}

// ============================================================================
// SOURCE SELECTION
// ============================================================================

function initializeSourceCheckboxes() {
    Object.keys(state.sources).forEach(sourceId => {
        const checkbox = document.getElementById(`source-${sourceId}`);
        if (checkbox) {
            checkbox.checked = state.sources[sourceId];
            checkbox.addEventListener('change', (e) => {
                state.sources[sourceId] = e.target.checked;
                updateUI();
            });
        }
    });
}

function getActiveSources() {
    return Object.keys(state.sources).filter(s => state.sources[s]);
}

function hasRequiredSources(requires) {
    if (!requires || requires.length === 0) return true;
    return requires.some(sourceId => state.sources[sourceId]);
}

// ============================================================================
// FILTER MANAGEMENT
// ============================================================================

function initializeFilterButtons() {
    document.querySelectorAll('.add-filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const filterType = btn.dataset.filter;
            const requires = btn.dataset.requires ? btn.dataset.requires.split(',') : [];

            if (!hasRequiredSources(requires)) {
                const sourceNames = requires.map(s => s.charAt(0).toUpperCase() + s.slice(1)).join(', ');
                alert(`This filter requires at least one of these sources: ${sourceNames}`);
                return;
            }

            openFilterConfigPopup(filterType);
        });
    });
}

function addFilter(filterType, mode, config, summary) {
    const filter = {
        id: state.nextFilterId++,
        type: filterType,
        mode: mode || 'include',  // 'include' or 'exclude'
        config: config || {},
        summary: summary || generateFilterSummary(filterType, config, mode || 'include')
    };

    state.filters.push(filter);
    updateUI();
}

function removeFilter(filterId) {
    state.filters = state.filters.filter(f => f.id !== filterId);
    updateUI();
}

function generateFilterSummary(filterType, config, mode = 'include') {
    const parts = [];

    switch (filterType) {
        case 'character':
            // Length constraints
            if (config.minLength || config.maxLength) {
                if (config.minLength && config.maxLength && config.minLength === config.maxLength) {
                    parts.push(config.minLength === 1 ? '1 letter' : `${config.minLength} letters`);
                } else if (config.minLength && config.maxLength) {
                    parts.push(`${config.minLength}-${config.maxLength} letters`);
                } else if (config.minLength) {
                    parts.push(`≥${config.minLength} letters`);
                } else if (config.maxLength) {
                    parts.push(`≤${config.maxLength} letters`);
                }
            }

            // Character preset
            if (config.charPreset && config.charPreset !== 'any') {
                const preset = CHAR_PRESETS[config.charPreset];
                if (preset) {
                    parts.push(preset.description);
                }
            }

            // Starts with (OR logic)
            if (config.startsWith && config.startsWith.length > 0) {
                const list = Array.isArray(config.startsWith) ? config.startsWith : [config.startsWith];
                if (list.length === 1) {
                    parts.push(`starts with "${list[0]}"`);
                } else {
                    parts.push(`starts with ${list.map(s => `"${s}"`).join(' or ')}`);
                }
            }

            // Doesn't start with
            if (config.excludeStartsWith && config.excludeStartsWith.length > 0) {
                const list = Array.isArray(config.excludeStartsWith) ? config.excludeStartsWith : [config.excludeStartsWith];
                if (list.length === 1) {
                    parts.push(`doesn't start with "${list[0]}"`);
                } else {
                    parts.push(`doesn't start with ${list.map(s => `"${s}"`).join(', ')}`);
                }
            }

            // Ends with (OR logic)
            if (config.endsWith && config.endsWith.length > 0) {
                const list = Array.isArray(config.endsWith) ? config.endsWith : [config.endsWith];
                if (list.length === 1) {
                    parts.push(`ends with "${list[0]}"`);
                } else {
                    parts.push(`ends with ${list.map(s => `"${s}"`).join(' or ')}`);
                }
            }

            // Doesn't end with
            if (config.excludeEndsWith && config.excludeEndsWith.length > 0) {
                const list = Array.isArray(config.excludeEndsWith) ? config.excludeEndsWith : [config.excludeEndsWith];
                if (list.length === 1) {
                    parts.push(`doesn't end with "${list[0]}"`);
                } else {
                    parts.push(`doesn't end with ${list.map(s => `"${s}"`).join(', ')}`);
                }
            }

            // Contains (AND logic)
            if (config.contains && config.contains.length > 0) {
                const list = Array.isArray(config.contains) ? config.contains : [config.contains];
                if (list.length === 1) {
                    parts.push(`contains "${list[0]}"`);
                } else {
                    parts.push(`contains ${list.map(s => `"${s}"`).join(' and ')}`);
                }
            }

            // Doesn't contain
            if (config.excludeContains) {
                parts.push(`no ${config.excludeContains.split('').map(c => `"${c}"`).join(', ')}`);
            }

            // Legacy pattern support (for backwards compatibility)
            if (config.pattern && !config.charPreset) {
                parts.push(`pattern: ${config.pattern}`);
            }
            break;

        case 'phrase':
            if (config.multiWord && !config.singleWord) {
                parts.push('Multi-word phrases only');
            } else if (config.singleWord && !config.multiWord) {
                parts.push('Single words only');
            } else if (config.singleWord && config.multiWord) {
                parts.push('All word counts');
            }
            if (config.minWords || config.maxWords) {
                if (config.minWords && config.maxWords) {
                    parts.push(`${config.minWords}-${config.maxWords} words`);
                } else if (config.minWords) {
                    parts.push(`≥${config.minWords} words`);
                } else if (config.maxWords) {
                    parts.push(`≤${config.maxWords} words`);
                }
            }
            break;

        case 'pos':
            if (config.pos && config.pos.length > 0) {
                if (config.pos.length === 1) {
                    // Capitalize and pluralize for single selection
                    const pos = config.pos[0];
                    const friendly = {
                        'noun': 'Nouns only',
                        'verb': 'Verbs only',
                        'adjective': 'Adjectives only',
                        'adverb': 'Adverbs only',
                        'pronoun': 'Pronouns only',
                        'preposition': 'Prepositions only',
                        'conjunction': 'Conjunctions only',
                        'interjection': 'Interjections only',
                        'determiner': 'Determiners only',
                        'particle': 'Particles only',
                        'numeral': 'Numerals only',
                        'article': 'Articles only',
                        'postposition': 'Postpositions only'
                    };
                    parts.push(friendly[pos] || pos);
                } else {
                    // For multiple, just capitalize each
                    const capitalized = config.pos.map(p => p.charAt(0).toUpperCase() + p.slice(1));
                    parts.push(capitalized.join(', '));
                }
            }
            break;

        case 'frequency':
            if (config.minTier && config.maxTier) {
                // Friendly range descriptions
                const rangeDesc = `Common words (${config.minTier}-${config.maxTier})`;
                parts.push(rangeDesc);
            } else if (config.minTier) {
                parts.push(`≥${config.minTier}`);
            } else if (config.maxTier) {
                parts.push(`≤${config.maxTier}`);
            }
            break;

        case 'region':
            if (config.regions && config.regions.length > 0) {
                if (config.regions.length === 1 && config.regions[0] === 'en-GB') {
                    parts.push('British English');
                } else if (config.regions.length === 1 && config.regions[0] === 'en-US') {
                    parts.push('American English');
                } else {
                    parts.push(config.regions.join(', '));
                }
            }
            break;

        case 'concreteness':
            if (config.concreteness && config.concreteness.length > 0) {
                if (config.concreteness.length === 1 && config.concreteness[0] === 'concrete') {
                    parts.push('Concrete words');
                } else if (config.concreteness.length === 1 && config.concreteness[0] === 'abstract') {
                    parts.push('Abstract words');
                } else {
                    // Capitalize each
                    const capitalized = config.concreteness.map(c => c.charAt(0).toUpperCase() + c.slice(1));
                    parts.push(capitalized.join(', '));
                }
            }
            // Don't show Brysbaert preference in summary - it's a technical detail
            break;

        case 'labels':
            if (config.labels && config.labels.length > 0) {
                if (mode === 'exclude') {
                    // For exclude mode, add "No" prefix
                    parts.push('No ' + config.labels.join('/'));
                } else {
                    // For include mode, just list them or make it friendly
                    if (config.labels.length === 1) {
                        const label = config.labels[0];
                        parts.push(label.charAt(0).toUpperCase() + label.slice(1) + ' words');
                    } else {
                        parts.push(config.labels.join(', '));
                    }
                }
            }
            break;

        case 'syllable':
            if (config.exact) {
                parts.push(config.exact === 1 ? '1 syllable' : `${config.exact} syllables`);
            } else if (config.minSyllables && config.maxSyllables) {
                if (config.minSyllables === config.maxSyllables) {
                    parts.push(config.minSyllables === 1 ? '1 syllable' : `${config.minSyllables} syllables`);
                } else {
                    parts.push(`${config.minSyllables}-${config.maxSyllables} syllables`);
                }
            } else if (config.minSyllables) {
                parts.push(`≥${config.minSyllables} syllables`);
            } else if (config.maxSyllables) {
                parts.push(`≤${config.maxSyllables} syllables`);
            }
            break;
    }

    return parts.length > 0 ? parts.join(', ') : 'No configuration';
}

// ============================================================================
// DEMO PRESETS
// ============================================================================

function initializeDemoSelector() {
    const demoSelect = document.getElementById('demo-select');
    demoSelect.addEventListener('change', (e) => {
        if (e.target.value) {
            loadDemo(e.target.value);
            e.target.value = '';  // Reset selection
        }
    });
}

function loadDemo(demoId) {
    const demo = DEMOS[demoId];
    if (!demo) return;

    // Load sources
    Object.keys(state.sources).forEach(sourceId => {
        state.sources[sourceId] = demo.sources[sourceId] || false;
        const checkbox = document.getElementById(`source-${sourceId}`);
        if (checkbox) checkbox.checked = state.sources[sourceId];
    });

    // Load filters
    state.filters = [];
    state.nextFilterId = 1;
    demo.filters.forEach(filter => {
        addFilter(filter.type, filter.mode, filter.config, filter.summary);
    });

    updateUI();
}

// ============================================================================
// POPUP MANAGEMENT
// ============================================================================

let currentPopupFilterType = null;
let currentPopupFilterId = null;  // null = adding new, number = editing existing

function openFilterConfigPopup(filterType, existingFilter = null) {
    currentPopupFilterType = filterType;
    currentPopupFilterId = existingFilter ? existingFilter.id : null;
    const filterDef = FILTER_TYPES[filterType];

    const popup = document.getElementById('popup-overlay');
    const title = document.getElementById('popup-title');
    const body = document.getElementById('popup-body');

    title.textContent = existingFilter
        ? `Edit ${filterDef.title}`
        : filterDef.title;
    body.innerHTML = generateFilterConfigHTML(filterDef, existingFilter);

    popup.classList.add('active');
}

function closeFilterConfigPopup() {
    const popup = document.getElementById('popup-overlay');
    popup.classList.remove('active');
    currentPopupFilterType = null;
    currentPopupFilterId = null;
}

function applyFilterConfig() {
    const filterDef = FILTER_TYPES[currentPopupFilterType];
    const config = {};

    filterDef.configFields.forEach(field => {
        // Handle preset-select
        if (field.type === 'preset-select') {
            const input = document.getElementById(`filter-${field.name}`);
            if (input && input.value) {
                config[field.name] = input.value;
            }
            return;
        }

        // Handle length-row (split row fields)
        if (field.type === 'length-row') {
            field.names.forEach(name => {
                const input = document.getElementById(`filter-${name}`);
                if (input && input.value) {
                    config[name] = parseInt(input.value);
                }
            });
            return;
        }

        const input = document.getElementById(`filter-${field.name}`);
        if (!input) return;

        if (field.type === 'checkbox') {
            config[field.name] = input.checked;
        } else if (field.type === 'multiselect') {
            const selected = Array.from(input.selectedOptions).map(opt => opt.value);
            config[field.name] = selected;
        } else if (field.type === 'number') {
            if (input.value) config[field.name] = parseInt(input.value);
        } else if (field.type === 'text') {
            // Parse comma-separated values for certain fields
            if (input.value) {
                const value = input.value.trim();
                // Fields that should be parsed as comma-separated lists
                if (['startsWith', 'excludeStartsWith', 'endsWith', 'excludeEndsWith', 'contains'].includes(field.name)) {
                    // Split by comma, trim whitespace, filter empty strings
                    config[field.name] = value.split(',').map(s => s.trim()).filter(s => s.length > 0);
                } else {
                    // Other text fields remain as strings
                    config[field.name] = value;
                }
            }
        } else {
            if (input.value) config[field.name] = input.value;
        }
    });

    // Get mode (include/exclude)
    const modeRadio = document.querySelector('input[name="filter-mode"]:checked');
    const mode = modeRadio ? modeRadio.value : 'include';

    if (currentPopupFilterId !== null) {
        // Editing existing filter
        const filter = state.filters.find(f => f.id === currentPopupFilterId);
        if (filter) {
            filter.mode = mode;
            filter.config = config;
            filter.summary = generateFilterSummary(currentPopupFilterType, config, mode);
        }
    } else {
        // Adding new filter
        addFilter(currentPopupFilterType, mode, config);
    }

    closeFilterConfigPopup();
    updateUI();
}

function generateFilterConfigHTML(filterDef, existingFilter = null) {
    let html = '<div class="filter-config-form">';

    const mode = existingFilter ? existingFilter.mode : 'include';
    const config = existingFilter ? existingFilter.config : {};

    // Mode selection (include/exclude)
    html += `
        <div class="form-group">
            <label class="form-label">Filter Mode</label>
            <div class="radio-group">
                <label class="radio-label">
                    <input type="radio" name="filter-mode" value="include" ${mode === 'include' ? 'checked' : ''}>
                    <span class="mode-include">Must Include</span> - Only show words matching this filter
                </label>
                <label class="radio-label">
                    <input type="radio" name="filter-mode" value="exclude" ${mode === 'exclude' ? 'checked' : ''}>
                    <span class="mode-exclude">Must Not Include</span> - Hide words matching this filter
                </label>
            </div>
        </div>
    `;

    // Configuration fields
    filterDef.configFields.forEach(field => {
        // Special handling for preset-select
        if (field.type === 'preset-select') {
            html += '<div class="form-group">';
            html += `<label class="form-label" for="filter-${field.name}">${field.label}</label>`;
            const fieldValue = config[field.name] || field.defaultValue || 'standard';
            html += `<select id="filter-${field.name}" class="form-select">`;
            Object.keys(CHAR_PRESETS).forEach(presetKey => {
                const preset = CHAR_PRESETS[presetKey];
                const selected = fieldValue === presetKey ? 'selected' : '';
                html += `<option value="${presetKey}" ${selected}>${preset.label}</option>`;
            });
            html += '</select>';
            html += '<p class="hint">Choose a character preset or select "Any" for no restrictions</p>';
            html += '</div>';
            return;
        }

        // Special handling for length-row (split row for min/max length)
        if (field.type === 'length-row') {
            html += '<div class="form-group">';
            html += '<label class="form-label">Word Length</label>';
            html += '<div class="form-row-split">';
            field.names.forEach((name, index) => {
                const value = config[name] !== undefined ? config[name] : '';
                html += '<div class="form-col">';
                html += `<label class="form-sublabel">${field.labels[index]}:</label>`;
                html += `<input type="number" id="filter-${name}" class="form-input"
                         placeholder="${index === 0 ? '1' : '15'}"
                         min="${field.min || 0}"
                         value="${value}">`;
                html += '</div>';
            });
            html += '</div>';
            html += '</div>';
            return;
        }

        html += '<div class="form-group">';
        html += `<label class="form-label" for="filter-${field.name}">${field.label}</label>`;

        const fieldValue = config[field.name];

        if (field.type === 'checkbox') {
            const checked = fieldValue !== undefined ? fieldValue : (field.defaultChecked || false);
            html += `
                <label class="checkbox-label">
                    <input type="checkbox" id="filter-${field.name}" ${checked ? 'checked' : ''}>
                    <span>${field.label}</span>
                </label>
            `;
        } else if (field.type === 'select') {
            html += `<select id="filter-${field.name}" class="form-select">`;
            html += '<option value="">Select...</option>';
            field.options.forEach(opt => {
                const value = typeof opt === 'string' ? opt : opt.value;
                const label = typeof opt === 'string' ? opt : opt.label;
                const selected = fieldValue === value ? 'selected' : '';
                html += `<option value="${value}" ${selected}>${label}</option>`;
            });
            html += '</select>';
        } else if (field.type === 'multiselect') {
            html += `<select id="filter-${field.name}" class="form-select" multiple size="6">`;
            const selectedValues = fieldValue || [];
            field.options.forEach(opt => {
                const selected = selectedValues.includes(opt) ? 'selected' : '';
                html += `<option value="${opt}" ${selected}>${opt}</option>`;
            });
            html += '</select>';
            html += '<p class="hint">Hold Ctrl/Cmd to select multiple</p>';
        } else if (field.type === 'number') {
            const value = fieldValue !== undefined ? fieldValue : '';
            html += `<input type="number" id="filter-${field.name}" class="form-input"
                     placeholder="${field.placeholder || ''}"
                     min="${field.min || 0}"
                     value="${value}">`;
        } else if (field.type === 'text') {
            const value = fieldValue !== undefined ? fieldValue : '';
            html += `<input type="text" id="filter-${field.name}" class="form-input"
                     placeholder="${field.placeholder || ''}"
                     value="${value}">`;
        }

        // Add hint text if present
        if (field.hint) {
            html += `<p class="hint">${field.hint}</p>`;
        }

        html += '</div>';
    });

    html += '</div>';
    return html;
}

// Popup event listeners
document.getElementById('popup-close').addEventListener('click', closeFilterConfigPopup);
document.getElementById('popup-cancel').addEventListener('click', closeFilterConfigPopup);
document.getElementById('popup-apply').addEventListener('click', applyFilterConfig);

document.getElementById('popup-overlay').addEventListener('click', (e) => {
    if (e.target.id === 'popup-overlay') {
        closeFilterConfigPopup();
    }
});

// ============================================================================
// EXPORT & SPEC GENERATION
// ============================================================================

function initializeExportButtons() {
    document.getElementById('btn-view-spec').addEventListener('click', showSpecPopup);
    document.getElementById('btn-download-spec').addEventListener('click', downloadSpec);
    document.getElementById('btn-copy-spec').addEventListener('click', copySpec);
    document.getElementById('spec-popup-close').addEventListener('click', closeSpecPopup);
    document.getElementById('spec-popup-close-btn').addEventListener('click', closeSpecPopup);

    document.getElementById('spec-popup').addEventListener('click', (e) => {
        if (e.target.id === 'spec-popup') {
            closeSpecPopup();
        }
    });
}

/**
 * Generate simplified YAML spec (filters-only format).
 * This is the primary export format for owlex.
 */
function generateYAMLSpec() {
    const lines = ['# Word list specification'];
    lines.push('# Generated by OpenWord Lexicon Word List Builder');
    lines.push('');

    // Sources filter (for licensing compliance)
    const activeSources = getActiveSources();
    const sourceMapping = {
        'wiktionary': 'wikt',
        'eowl': 'eowl',
        'wordnet': 'wordnet',
        'brysbaert': 'brysbaert'
    };
    const dataSources = activeSources
        .filter(s => s !== 'frequency')  // frequency is enrichment, not primary source
        .map(s => sourceMapping[s] || s);

    if (dataSources.length > 0 && dataSources.length < 4) {
        lines.push('sources:');
        lines.push(`  include: [${dataSources.join(', ')}]`);
        if (activeSources.includes('frequency')) {
            lines.push('  enrichment: [frequency]');
        }
        lines.push('');
    }

    // Group filters by type
    const filtersByType = {};
    state.filters.forEach(f => {
        if (!filtersByType[f.type]) {
            filtersByType[f.type] = [];
        }
        filtersByType[f.type].push(f);
    });

    // Generate YAML for each filter type
    for (const [type, filters] of Object.entries(filtersByType)) {
        const yamlBlock = convertFilterToYAML(type, filters);
        if (yamlBlock) {
            lines.push(yamlBlock);
            lines.push('');
        }
    }

    return lines.join('\n');
}

/**
 * Convert filters of a given type to YAML format.
 */
function convertFilterToYAML(type, filters) {
    const lines = [];

    switch (type) {
        case 'character': {
            lines.push('character:');
            const f = filters[0];  // Usually only one character filter
            if (f.config.minLength && f.config.maxLength && f.config.minLength === f.config.maxLength) {
                lines.push(`  exact_length: ${f.config.minLength}`);
            } else {
                if (f.config.minLength) lines.push(`  min_length: ${f.config.minLength}`);
                if (f.config.maxLength) lines.push(`  max_length: ${f.config.maxLength}`);
            }
            if (f.config.charPreset === 'standard') {
                lines.push('  pattern: "^[a-z]+$"');
            }
            if (f.config.startsWith && f.config.startsWith.length > 0) {
                lines.push(`  starts_with: [${f.config.startsWith.join(', ')}]`);
            }
            if (f.config.endsWith && f.config.endsWith.length > 0) {
                lines.push(`  ends_with: [${f.config.endsWith.join(', ')}]`);
            }
            break;
        }
        case 'phrase': {
            lines.push('phrase:');
            const f = filters[0];
            if (f.config.singleWord) {
                lines.push('  max_words: 1');
            } else if (f.config.multiWord) {
                lines.push('  min_words: 2');
            }
            break;
        }
        case 'frequency': {
            lines.push('frequency:');
            const f = filters[0];
            if (f.config.minTier) lines.push(`  min_tier: ${f.config.minTier}`);
            if (f.config.maxTier) lines.push(`  max_tier: ${f.config.maxTier}`);
            break;
        }
        case 'pos': {
            lines.push('pos:');
            const f = filters[0];
            if (f.config.pos && f.config.pos.length > 0) {
                lines.push(`  include: [${f.config.pos.join(', ')}]`);
            }
            break;
        }
        case 'concreteness': {
            lines.push('concreteness:');
            const f = filters[0];
            if (f.config.concreteness && f.config.concreteness.length > 0) {
                lines.push(`  values: [${f.config.concreteness.join(', ')}]`);
            }
            break;
        }
        case 'labels': {
            // Separate temporal labels from register labels
            const temporalLabels = ['archaic', 'obsolete', 'dated'];

            // Collect all labels from all filters
            const includeFilters = filters.filter(f => f.mode === 'include');
            const excludeFilters = filters.filter(f => f.mode === 'exclude');

            const includeLabels = includeFilters.flatMap(f => f.config.labels || []);
            const excludeLabels = excludeFilters.flatMap(f => f.config.labels || []);

            // Split into register and temporal
            const includeRegister = includeLabels.filter(l => !temporalLabels.includes(l));
            const excludeRegister = excludeLabels.filter(l => !temporalLabels.includes(l));
            const includeTemporal = includeLabels.filter(l => temporalLabels.includes(l));
            const excludeTemporal = excludeLabels.filter(l => temporalLabels.includes(l));

            // Output register labels
            if (includeRegister.length > 0 || excludeRegister.length > 0) {
                lines.push('labels:');
                lines.push('  register:');
                if (includeRegister.length > 0) {
                    lines.push(`    include: [${includeRegister.join(', ')}]`);
                }
                if (excludeRegister.length > 0) {
                    lines.push(`    exclude: [${excludeRegister.join(', ')}]`);
                }
            }

            // Output temporal labels separately
            if (includeTemporal.length > 0 || excludeTemporal.length > 0) {
                // Add blank line if we also had register labels
                if (lines.length > 0 && lines[lines.length - 1] !== '') {
                    lines.push('');
                }
                lines.push('temporal:');
                if (includeTemporal.length > 0) {
                    lines.push(`  include: [${includeTemporal.join(', ')}]`);
                }
                if (excludeTemporal.length > 0) {
                    lines.push(`  exclude: [${excludeTemporal.join(', ')}]`);
                }
            }
            break;
        }
        case 'region': {
            lines.push('region:');
            const f = filters[0];
            if (f.config.regions && f.config.regions.length > 0) {
                if (f.mode === 'include') {
                    lines.push(`  include: [${f.config.regions.join(', ')}]`);
                } else {
                    lines.push(`  exclude: [${f.config.regions.join(', ')}]`);
                }
            }
            break;
        }
        case 'syllable': {
            lines.push('syllables:');
            const f = filters[0];
            if (f.config.exact) {
                lines.push(`  exact: ${f.config.exact}`);
            } else {
                if (f.config.minSyllables) lines.push(`  min: ${f.config.minSyllables}`);
                if (f.config.maxSyllables) lines.push(`  max: ${f.config.maxSyllables}`);
            }
            if (f.config.requireSyllables) {
                lines.push('  require_syllables: true');
            }
            break;
        }
    }

    return lines.length > 1 ? lines.join('\n') : null;
}

/**
 * Generate JSON spec (legacy format for backwards compatibility).
 */
function generateJSONSpec() {
    const spec = {
        version: '1.0',
        sources: getActiveSources(),
        filters: state.filters.map(f => ({
            type: f.type,
            mode: f.mode,
            config: f.config
        }))
    };

    return JSON.stringify(spec, null, 2);
}

function showSpecPopup() {
    const yaml = generateYAMLSpec();
    document.getElementById('spec-output').textContent = yaml;
    document.getElementById('spec-popup').classList.add('active');
}

function closeSpecPopup() {
    document.getElementById('spec-popup').classList.remove('active');
}

function copySpec() {
    const yaml = generateYAMLSpec();
    navigator.clipboard.writeText(yaml).then(() => {
        const btn = document.getElementById('btn-copy-spec');
        const originalText = btn.textContent;
        btn.textContent = 'Copied!';
        setTimeout(() => {
            btn.textContent = originalText;
        }, 2000);
    });
}

function downloadSpec() {
    const yaml = generateYAMLSpec();
    const blob = new Blob([yaml], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'wordlist-spec.yaml';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// ============================================================================
// UI UPDATES
// ============================================================================

function updateUI() {
    updateSourceSummary();
    updateFilterButtons();
    updateQuickFilters();
    updateFiltersList();
    updateResultsSummary();
}

function updateSourceSummary() {
    const activeSources = getActiveSources();

    // Map UI source names to data source names
    const sourceMapping = {
        'wiktionary': 'wikt',
        'eowl': 'eowl',
        'wordnet': 'wordnet',
        'brysbaert': 'brysbaert',
        'frequency': 'frequency'
    };

    // Convert UI source names to data source names
    const dataSources = activeSources.map(s => sourceMapping[s] || s);

    // Get primary sources only (for word count)
    // Note: 'enable' is validation-only, not a primary source
    const primarySources = dataSources.filter(s => ['wikt', 'eowl'].includes(s));

    // Calculate estimated word count
    const estimatedWords = estimateWordCount(primarySources);
    document.getElementById('total-words').textContent = estimatedWords > 0
        ? `~${estimatedWords.toLocaleString()}`
        : '0';

    // Compute real-time metadata coverage for ALL selected sources (including enrichment)
    const metadata = computeMetadataCoverage(dataSources);

    // Display word counts for each metadata type
    if (metadata) {
        document.getElementById('pos-available').textContent = metadata.pos_tags.count.toLocaleString();
        document.getElementById('labels-available').textContent = metadata.any_labels.count.toLocaleString();
        document.getElementById('concreteness-available').textContent = metadata.concreteness.count.toLocaleString();
        document.getElementById('regional-available').textContent = metadata.region_labels.count.toLocaleString();
    } else {
        // Fallback when no metadata available
        document.getElementById('pos-available').textContent = '0';
        document.getElementById('labels-available').textContent = '0';
        document.getElementById('concreteness-available').textContent = '0';
        document.getElementById('regional-available').textContent = '0';
    }
}

function updateFilterButtons() {
    document.querySelectorAll('.add-filter-btn').forEach(btn => {
        const requires = btn.dataset.requires ? btn.dataset.requires.split(',') : [];
        const isAvailable = hasRequiredSources(requires);
        btn.disabled = !isAvailable;
    });
}

function updateQuickFilters() {
    // Update availability based on selected sources
    document.querySelectorAll('.quick-filter-item[data-requires]').forEach(item => {
        const requires = item.dataset.requires.split(',');
        const isAvailable = hasRequiredSources(requires);

        if (isAvailable) {
            item.classList.add('available');
        } else {
            item.classList.remove('available');
        }
    });
}

function updateFiltersList() {
    const filtersList = document.getElementById('filters-list');
    const emptyState = document.getElementById('filters-empty');
    const filterCount = document.getElementById('filter-count');

    filterCount.textContent = `(${state.filters.length})`;

    if (state.filters.length === 0) {
        emptyState.style.display = 'block';
        filtersList.innerHTML = '';
        return;
    }

    emptyState.style.display = 'none';

    filtersList.innerHTML = state.filters.map(filter => {
        const filterDef = FILTER_TYPES[filter.type];
        const modeClass = filter.mode === 'include' ? 'mode-include' : 'mode-exclude';
        const modeLabel = filter.mode === 'include' ? 'Must Include' : 'Must Not Include';

        return `
            <div class="filter-item ${modeClass}">
                <div class="filter-main">
                    <div class="filter-info">
                        <span class="filter-icon">${filterDef.icon}</span>
                        <span class="filter-title">${filterDef.title}</span>
                        <span class="filter-mode ${modeClass}">${modeLabel}</span>
                    </div>
                    <div class="filter-actions">
                        <button class="filter-edit" data-id="${filter.id}" title="Edit filter">Edit</button>
                        <button class="filter-remove" data-id="${filter.id}" title="Remove filter">×</button>
                    </div>
                </div>
                <div class="filter-summary">${filter.summary}</div>
            </div>
        `;
    }).join('');

    // Attach edit handlers
    filtersList.querySelectorAll('.filter-edit').forEach(btn => {
        btn.addEventListener('click', () => {
            const filterId = parseInt(btn.dataset.id);
            const filter = state.filters.find(f => f.id === filterId);
            if (filter) {
                openFilterConfigPopup(filter.type, filter);
            }
        });
    });

    // Attach remove handlers
    filtersList.querySelectorAll('.filter-remove').forEach(btn => {
        btn.addEventListener('click', () => {
            const filterId = parseInt(btn.dataset.id);
            removeFilter(filterId);
        });
    });
}

function updateResultsSummary() {
    const activeSources = getActiveSources();

    // Determine license using centralized function
    const licenseInfo = computeLicense(activeSources);

    // Create clean source names list
    const sourceNames = {
        'wiktionary': 'Wiktionary',
        'eowl': 'EOWL',
        'wordnet': 'WordNet',
        'brysbaert': 'Brysbaert',
        'frequency': 'Frequency Data'
    };
    const sourcesList = activeSources.map(s => sourceNames[s] || s).join(', ');

    document.getElementById('result-license').textContent = licenseInfo.license;
    document.getElementById('result-sources').textContent = sourcesList || 'None selected';
}
