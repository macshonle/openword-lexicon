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
    nextFilterId: 1
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
// FILTER DEFINITIONS
// ============================================================================

const FILTER_TYPES = {
    character: {
        title: 'Character Filter',
        icon: '🔤',
        requires: [],
        configFields: [
            { type: 'number', name: 'minLength', label: 'Minimum Length', min: 1, placeholder: 'e.g., 1' },
            { type: 'number', name: 'maxLength', label: 'Maximum Length', min: 1, placeholder: 'e.g., 15' },
            { type: 'text', name: 'pattern', label: 'Pattern (regex)', placeholder: 'e.g., ^[a-z]+$ (lowercase only)' },
            { type: 'text', name: 'startsWith', label: 'Starts With', placeholder: 'e.g., un' },
            { type: 'text', name: 'endsWith', label: 'Ends With', placeholder: 'e.g., ing' },
            { type: 'text', name: 'contains', label: 'Contains', placeholder: 'e.g., tion' }
        ]
    },
    phrase: {
        title: 'Phrase Filter',
        icon: '💬',
        requires: [],
        configFields: [
            { type: 'checkbox', name: 'multiWord', label: 'Multi-word phrases only', defaultChecked: true },
            { type: 'checkbox', name: 'singleWord', label: 'Single words only', defaultChecked: false },
            { type: 'number', name: 'minWords', label: 'Minimum Words', min: 1, placeholder: 'e.g., 2' },
            { type: 'number', name: 'maxWords', label: 'Maximum Words', min: 1, placeholder: 'e.g., 5' }
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
                config: { minLength: 5, maxLength: 5 },
                summary: '5 letters exactly'
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
                config: { minLength: 2, maxLength: 15 },
                summary: '2-15 letters'
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
 * on-the-fly using the subset principle:
 *
 * SUBSET PRINCIPLE: Include a combination if ALL its sources are selected.
 *   User selects ["wikt", "eowl"]:
 *     - "wikt" ✓ (wikt ⊆ {wikt, eowl})
 *     - "eowl" ✓ (eowl ⊆ {wikt, eowl})
 *     - "eowl,wikt" ✓ (both ⊆ {wikt, eowl})
 *     - "enable,eowl,wikt" ✗ (enable ∉ {wikt, eowl})
 *   Total: 1,095,480 + 3,252 + 32,126 = 1,130,858 words
 *
 * WHY ADDITION WORKS: Since combinations are disjoint (no word appears in multiple
 * combinations), summing them gives the exact union count.
 */
function estimateWordCount(selectedSources) {
    // If we have detailed statistics, use them for accurate estimates
    if (BUILD_STATS && BUILD_STATS.source_combinations) {
        // Union operation: sum all disjoint combinations that are subsets of selection
        let totalWords = 0;
        for (const [combo, count] of Object.entries(BUILD_STATS.source_combinations)) {
            const comboSources = combo.split(',');

            // Include this combination if it's a subset of selected sources
            const isSubset = comboSources.every(s => selectedSources.includes(s));
            if (isSubset) {
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
        const isSubset = comboSources.every(s => selectedSources.includes(s));

        if (isSubset) {
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
 * Uses the license_combinations data to find the most restrictive license.
 *
 * @param {string[]} selectedSources - Array of selected source IDs
 * @returns {Object} License information {id, description, sources}
 */
function computeLicense(selectedSources) {
    if (!BUILD_STATS || !BUILD_STATS.license_combinations) {
        // Fallback to hardcoded logic
        return computeLicenseFallback(selectedSources);
    }

    // Find all license combinations that match our source selection
    let matchedLicense = null;
    let maxCoverage = 0;

    for (const [licenses, count] of Object.entries(BUILD_STATS.license_combinations)) {
        // This is a heuristic: we look for the license combination that appears
        // most frequently with our selected sources. In practice, we should find
        // the combination that exactly matches our source selection.
        // For now, we'll use a simpler approach based on source requirements.
    }

    // Simplified: determine license based on most restrictive source
    return computeLicenseFallback(selectedSources);
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
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', async () => {
    // Load build statistics
    await loadBuildStatistics();

    initializeSourceCheckboxes();
    initializeFilterButtons();
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
            if (config.minLength || config.maxLength) {
                if (config.minLength && config.maxLength && config.minLength === config.maxLength) {
                    parts.push(config.minLength === 5 ? '5 letters exactly' : `${config.minLength} letters`);
                } else if (config.minLength && config.maxLength) {
                    parts.push(`${config.minLength}-${config.maxLength} letters`);
                } else if (config.minLength) {
                    parts.push(`≥${config.minLength} letters`);
                } else if (config.maxLength) {
                    parts.push(`≤${config.maxLength} letters`);
                }
            }
            if (config.pattern) parts.push(`pattern: ${config.pattern}`);
            if (config.startsWith) parts.push(`starts with "${config.startsWith}"`);
            if (config.endsWith) parts.push(`ends with "${config.endsWith}"`);
            if (config.contains) parts.push(`contains "${config.contains}"`);
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
        const input = document.getElementById(`filter-${field.name}`);

        if (field.type === 'checkbox') {
            config[field.name] = input.checked;
        } else if (field.type === 'multiselect') {
            const selected = Array.from(input.selectedOptions).map(opt => opt.value);
            config[field.name] = selected;
        } else if (field.type === 'number') {
            if (input.value) config[field.name] = parseInt(input.value);
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
// EXPORT & JSON GENERATION
// ============================================================================

function initializeExportButtons() {
    document.getElementById('btn-view-spec').addEventListener('click', showJSONPopup);
    document.getElementById('btn-download-spec').addEventListener('click', downloadJSON);
    document.getElementById('btn-copy-json').addEventListener('click', copyJSON);
    document.getElementById('json-popup-close').addEventListener('click', closeJSONPopup);
    document.getElementById('json-popup-close-btn').addEventListener('click', closeJSONPopup);

    document.getElementById('json-popup').addEventListener('click', (e) => {
        if (e.target.id === 'json-popup') {
            closeJSONPopup();
        }
    });
}

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

function showJSONPopup() {
    const json = generateJSONSpec();
    document.getElementById('json-output').textContent = json;
    document.getElementById('json-popup').classList.add('active');
}

function closeJSONPopup() {
    document.getElementById('json-popup').classList.remove('active');
}

function copyJSON() {
    const json = generateJSONSpec();
    navigator.clipboard.writeText(json).then(() => {
        const btn = document.getElementById('btn-copy-json');
        const originalText = btn.textContent;
        btn.textContent = 'Copied!';
        setTimeout(() => {
            btn.textContent = originalText;
        }, 2000);
    });
}

function downloadJSON() {
    const json = generateJSONSpec();
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'wordlist-spec.json';
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
    updateLicenseInfo();
    updateFilterButtons();
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

    // POS availability - depends on wiktionary or wordnet
    const posAvailable = state.sources.wiktionary || state.sources.wordnet;
    document.getElementById('pos-available').textContent = posAvailable && metadata
        ? `Yes (${metadata.pos_tags.percentage}%)`
        : posAvailable ? 'Yes' : 'No';

    // Labels availability - depends on wiktionary
    const labelsAvailable = state.sources.wiktionary;
    document.getElementById('labels-available').textContent = labelsAvailable && metadata
        ? `Yes (${metadata.any_labels.percentage}%)`
        : labelsAvailable ? 'Yes' : 'No';

    // Concreteness availability - depends on wordnet or brysbaert
    const concretenessAvailable = state.sources.wordnet || state.sources.brysbaert;
    document.getElementById('concreteness-available').textContent = concretenessAvailable && metadata
        ? `Yes (${metadata.concreteness.percentage}%)`
        : concretenessAvailable ? 'Yes' : 'No';

    // Regional availability - depends on wiktionary
    const regionalAvailable = state.sources.wiktionary;
    document.getElementById('regional-available').textContent = regionalAvailable && metadata
        ? `Yes (${metadata.region_labels.percentage}%)`
        : regionalAvailable ? 'Yes' : 'No';
}

function updateLicenseInfo() {
    const licenseResult = document.getElementById('license-result');
    const licenseSources = document.getElementById('license-sources');

    // Compute license using centralized function
    const activeSources = getActiveSources();
    const licenseInfo = computeLicense(activeSources);

    licenseResult.innerHTML = `<strong>${licenseInfo.license}</strong><p class="license-description">${licenseInfo.licenseDesc}</p>`;
    licenseSources.innerHTML = licenseInfo.sources.map(s => `<li>${s}</li>`).join('');
}

function updateFilterButtons() {
    document.querySelectorAll('.add-filter-btn').forEach(btn => {
        const requires = btn.dataset.requires ? btn.dataset.requires.split(',') : [];
        const isAvailable = hasRequiredSources(requires);
        btn.disabled = !isAvailable;
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

    // Map UI source names to data source names
    const sourceMapping = {
        'wiktionary': 'wikt',
        'eowl': 'eowl',
        'wordnet': 'wordnet',
        'brysbaert': 'brysbaert',
        'frequency': 'frequency'
    };

    // Get primary sources only (for word count)
    const dataSources = activeSources.map(s => sourceMapping[s] || s);
    // Note: 'enable' is validation-only, not a primary source
    const primarySources = dataSources.filter(s => ['wikt', 'eowl'].includes(s));

    // Calculate estimated word count using centralized function
    const estimatedWords = estimateWordCount(primarySources);

    // Determine license using centralized function
    const licenseInfo = computeLicense(activeSources);

    document.getElementById('result-word-count').textContent = estimatedWords > 0
        ? `~${estimatedWords.toLocaleString()}`
        : '0';
    document.getElementById('result-license').textContent = licenseInfo.license;
}
