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

// Statistics from metadata_analysis_en.md
const STATS = {
    totalWords: 1298737,
    eowl: 128983,
    wiktionary: 1294779,
    wordnet: 90931,
    brysbaert: 39558,
    posAvailable: 0.988,      // 98.8%
    labelsAvailable: 0.113,   // 11.3%
    concretenessAvailable: 0.086,  // 8.6%
    regionalAvailable: 0.019  // 1.9%
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
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
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
        summary: summary || generateFilterSummary(filterType, config)
    };

    state.filters.push(filter);
    updateUI();
}

function removeFilter(filterId) {
    state.filters = state.filters.filter(f => f.id !== filterId);
    updateUI();
}

function generateFilterSummary(filterType, config) {
    const parts = [];

    switch (filterType) {
        case 'character':
            if (config.minLength || config.maxLength) {
                if (config.minLength && config.maxLength && config.minLength === config.maxLength) {
                    parts.push(`${config.minLength} letters`);
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
            if (config.multiWord) parts.push('Multi-word');
            if (config.singleWord) parts.push('Single word');
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
                parts.push(config.pos.join(', '));
            }
            break;

        case 'frequency':
            if (config.minTier && config.maxTier) {
                parts.push(`${config.minTier} to ${config.maxTier}`);
            } else if (config.minTier) {
                parts.push(`≥${config.minTier}`);
            } else if (config.maxTier) {
                parts.push(`≤${config.maxTier}`);
            }
            break;

        case 'region':
            if (config.regions && config.regions.length > 0) {
                parts.push(config.regions.join(', '));
            }
            break;

        case 'concreteness':
            if (config.concreteness && config.concreteness.length > 0) {
                parts.push(config.concreteness.join(', '));
            }
            if (config.preferBrysbaert) parts.push('(Brysbaert preferred)');
            break;

        case 'labels':
            if (config.labels && config.labels.length > 0) {
                parts.push(config.labels.join(', '));
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

function openFilterConfigPopup(filterType) {
    currentPopupFilterType = filterType;
    const filterDef = FILTER_TYPES[filterType];

    const popup = document.getElementById('popup-overlay');
    const title = document.getElementById('popup-title');
    const body = document.getElementById('popup-body');

    title.textContent = filterDef.title;
    body.innerHTML = generateFilterConfigHTML(filterDef);

    popup.classList.add('active');
}

function closeFilterConfigPopup() {
    const popup = document.getElementById('popup-overlay');
    popup.classList.remove('active');
    currentPopupFilterType = null;
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

    addFilter(currentPopupFilterType, mode, config);
    closeFilterConfigPopup();
}

function generateFilterConfigHTML(filterDef) {
    let html = '<div class="filter-config-form">';

    // Mode selection (include/exclude)
    html += `
        <div class="form-group">
            <label class="form-label">Filter Mode</label>
            <div class="radio-group">
                <label class="radio-label">
                    <input type="radio" name="filter-mode" value="include" checked>
                    <span class="mode-include">Must Include</span> - Only show words matching this filter
                </label>
                <label class="radio-label">
                    <input type="radio" name="filter-mode" value="exclude">
                    <span class="mode-exclude">Must Not Include</span> - Hide words matching this filter
                </label>
            </div>
        </div>
    `;

    // Configuration fields
    filterDef.configFields.forEach(field => {
        html += '<div class="form-group">';
        html += `<label class="form-label" for="filter-${field.name}">${field.label}</label>`;

        if (field.type === 'checkbox') {
            html += `
                <label class="checkbox-label">
                    <input type="checkbox" id="filter-${field.name}" ${field.defaultChecked ? 'checked' : ''}>
                    <span>${field.label}</span>
                </label>
            `;
        } else if (field.type === 'select') {
            html += `<select id="filter-${field.name}" class="form-select">`;
            html += '<option value="">Select...</option>';
            field.options.forEach(opt => {
                const value = typeof opt === 'string' ? opt : opt.value;
                const label = typeof opt === 'string' ? opt : opt.label;
                html += `<option value="${value}">${label}</option>`;
            });
            html += '</select>';
        } else if (field.type === 'multiselect') {
            html += `<select id="filter-${field.name}" class="form-select" multiple size="6">`;
            field.options.forEach(opt => {
                html += `<option value="${opt}">${opt}</option>`;
            });
            html += '</select>';
            html += '<p class="hint">Hold Ctrl/Cmd to select multiple</p>';
        } else if (field.type === 'number') {
            html += `<input type="number" id="filter-${field.name}" class="form-input"
                     placeholder="${field.placeholder || ''}"
                     min="${field.min || 0}">`;
        } else if (field.type === 'text') {
            html += `<input type="text" id="filter-${field.name}" class="form-input"
                     placeholder="${field.placeholder || ''}">`;
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

    // Calculate estimated word count
    let estimatedWords = 0;
    if (state.sources.eowl || state.sources.wiktionary) {
        if (state.sources.eowl && state.sources.wiktionary) {
            estimatedWords = STATS.totalWords;
        } else if (state.sources.wiktionary) {
            estimatedWords = STATS.wiktionary;
        } else if (state.sources.eowl) {
            estimatedWords = STATS.eowl;
        }
    }

    // Update stats
    document.getElementById('total-words').textContent = `~${estimatedWords.toLocaleString()}`;

    // POS availability
    const posAvailable = (state.sources.wiktionary || state.sources.wordnet);
    document.getElementById('pos-available').textContent = posAvailable
        ? `Yes (${(STATS.posAvailable * 100).toFixed(1)}%)`
        : 'No';

    // Labels availability
    const labelsAvailable = state.sources.wiktionary;
    document.getElementById('labels-available').textContent = labelsAvailable
        ? `Yes (${(STATS.labelsAvailable * 100).toFixed(1)}%)`
        : 'No';

    // Concreteness availability
    const concretenessAvailable = state.sources.wordnet || state.sources.brysbaert;
    document.getElementById('concreteness-available').textContent = concretenessAvailable
        ? `Yes (${(STATS.concretenessAvailable * 100).toFixed(1)}%)`
        : 'No';

    // Regional availability
    const regionalAvailable = state.sources.wiktionary;
    document.getElementById('regional-available').textContent = regionalAvailable
        ? `Yes (${(STATS.regionalAvailable * 100).toFixed(1)}%)`
        : 'No';
}

function updateLicenseInfo() {
    const licenseResult = document.getElementById('license-result');
    const licenseSources = document.getElementById('license-sources');

    // Determine license based on sources
    let license = 'CC BY 4.0';
    let licenseDesc = 'Attribution required';
    const sources = [];

    if (state.sources.wiktionary) {
        license = 'CC BY-SA 4.0';
        licenseDesc = 'Attribution + ShareAlike required';
        sources.push('Wiktionary (CC BY-SA 4.0)');
    }

    if (state.sources.eowl) {
        sources.push('EOWL (UKACD License)');
    }

    if (state.sources.wordnet) {
        sources.push('WordNet (WordNet License)');
    }

    if (state.sources.brysbaert) {
        sources.push('Brysbaert (Research Use)');
    }

    if (state.sources.frequency) {
        if (!state.sources.wiktionary) {
            license = 'CC BY-SA 4.0';
            licenseDesc = 'Attribution + ShareAlike required';
        }
        sources.push('Frequency Data (CC BY-SA 4.0)');
    }

    licenseResult.innerHTML = `<strong>${license}</strong><p class="license-description">${licenseDesc}</p>`;
    licenseSources.innerHTML = sources.map(s => `<li>${s}</li>`).join('');
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
                <div class="filter-header">
                    <span class="filter-icon">${filterDef.icon}</span>
                    <span class="filter-title">${filterDef.title}</span>
                    <span class="filter-mode ${modeClass}">${modeLabel}</span>
                    <button class="filter-remove" data-id="${filter.id}" title="Remove filter">×</button>
                </div>
                <div class="filter-summary">${filter.summary}</div>
            </div>
        `;
    }).join('');

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

    // Calculate estimated word count (same as source summary)
    let estimatedWords = 0;
    if (state.sources.eowl || state.sources.wiktionary) {
        if (state.sources.eowl && state.sources.wiktionary) {
            estimatedWords = STATS.totalWords;
        } else if (state.sources.wiktionary) {
            estimatedWords = STATS.wiktionary;
        } else if (state.sources.eowl) {
            estimatedWords = STATS.eowl;
        }
    }

    // Determine license
    let license = 'CC BY 4.0';
    if (state.sources.wiktionary || state.sources.frequency) {
        license = 'CC BY-SA 4.0';
    }

    document.getElementById('result-word-count').textContent = `~${estimatedWords.toLocaleString()}`;
    document.getElementById('result-license').textContent = license;
}
