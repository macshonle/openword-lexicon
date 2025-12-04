/**
 * Wordlist Viewer - Interactive Trie Explorer
 *
 * Unified viewer that loads either:
 * 1. Pre-built binary DAWG (fast, recommended)
 * 2. Plain text wordlist (slower, builds trie in browser)
 */

// ============================================================================
// Binary Trie - Loads pre-built compact DAWG format
// ============================================================================

class BinaryTrie {
    constructor() {
        this.buffer = null;
        this.view = null;
        this.wordCount = 0;
        this.version = 0;
        this.nodeOffsets = [];
        this.rootId = 0;  // Root is last node (post-order IDs)
        this.words = [];
    }

    async load(arrayBuffer) {
        this.buffer = new Uint8Array(arrayBuffer);
        this.view = new DataView(arrayBuffer);

        // Parse header
        const magic = new TextDecoder().decode(this.buffer.slice(0, 6));
        if (magic !== 'OWTRIE') {
            throw new Error('Invalid trie file: bad magic number');
        }

        this.version = this.view.getUint16(6, true);
        if (this.version !== 2 && this.version !== 4) {
            throw new Error(`Unsupported trie version: ${this.version}. Only v2 and v4 are supported.`);
        }

        this.wordCount = this.view.getUint32(8, true);
        this._buildNodeIndex();

        // Root is the last node (post-order ID assignment puts root last)
        this.rootId = this.nodeOffsets.length - 1;

        console.log(`Loaded binary trie v${this.version}: ${this.wordCount.toLocaleString()} words, ${this.nodeOffsets.length} nodes, root=${this.rootId}`);
    }

    // Read unsigned varint, returns { value, bytesRead }
    _readVarint(offset) {
        let value = 0;
        let shift = 0;
        let bytesRead = 0;

        while (true) {
            const byte = this.buffer[offset + bytesRead];
            bytesRead++;
            value |= (byte & 0x7F) << shift;
            if ((byte & 0x80) === 0) break;
            shift += 7;
        }

        return { value, bytesRead };
    }

    _buildNodeIndex() {
        let offset = 12;
        let nodeId = 0;

        while (offset < this.buffer.length) {
            this.nodeOffsets[nodeId++] = offset;

            // Both v2 and v4 use: flags byte + child count byte
            offset++; // skip flags byte
            const childCount = this.buffer[offset++];

            if (this.version === 2) {
                // v2: char (1 byte) + node_id (2 bytes) = 3 bytes per child
                offset += childCount * 3;
            } else {
                // v4: varint char + varint delta per child
                for (let i = 0; i < childCount; i++) {
                    const { bytesRead: charBytes } = this._readVarint(offset);
                    offset += charBytes;
                    const { bytesRead: deltaBytes } = this._readVarint(offset);
                    offset += deltaBytes;
                }
            }
        }
    }

    _getNode(offset, nodeId = null) {
        // Both v2 and v4 use: flags byte (bit 0 = terminal) + child count byte
        const isTerminal = (this.buffer[offset] & 0x01) !== 0;
        const childCount = this.buffer[offset + 1];
        let childOffset = offset + 2;

        const children = new Map();
        for (let i = 0; i < childCount; i++) {
            let char, childNodeId;

            if (this.version === 4) {
                // v4: varint char + varint delta
                const { value: codePoint, bytesRead: charBytes } = this._readVarint(childOffset);
                char = String.fromCodePoint(codePoint);
                childOffset += charBytes;
                const { value: delta, bytesRead: deltaBytes } = this._readVarint(childOffset);
                childNodeId = nodeId - delta;
                childOffset += deltaBytes;
            } else {
                // v2: 1-byte char + 2-byte absolute node ID
                char = String.fromCharCode(this.buffer[childOffset]);
                childNodeId = this.view.getUint16(childOffset + 1, true);
                childOffset += 3;
            }
            children.set(char, childNodeId);
        }

        return { isTerminal, children };
    }

    has(word) {
        let nodeId = this.rootId;
        for (const char of word) {
            const offset = this.nodeOffsets[nodeId];
            const node = this._getNode(offset, nodeId);
            if (!node.children.has(char)) {
                return false;
            }
            nodeId = node.children.get(char);
        }
        const offset = this.nodeOffsets[nodeId];
        const node = this._getNode(offset, nodeId);
        return node.isTerminal;
    }

    isValidPrefix(prefix) {
        let nodeId = this.rootId;
        for (const char of prefix) {
            const offset = this.nodeOffsets[nodeId];
            const node = this._getNode(offset, nodeId);
            if (!node.children.has(char)) {
                return false;
            }
            nodeId = node.children.get(char);
        }
        return true;
    }

    findLongestValidPrefix(text) {
        let nodeId = this.rootId;
        let validPrefix = '';

        for (let i = 0; i < text.length; i++) {
            const char = text[i];
            const offset = this.nodeOffsets[nodeId];
            const node = this._getNode(offset, nodeId);

            if (!node.children.has(char)) {
                break;
            }

            nodeId = node.children.get(char);
            validPrefix += char;
        }

        return validPrefix;
    }

    getNextLetters(prefix) {
        let nodeId = this.rootId;
        for (const char of prefix) {
            const offset = this.nodeOffsets[nodeId];
            const node = this._getNode(offset, nodeId);
            if (!node.children.has(char)) {
                return [];
            }
            nodeId = node.children.get(char);
        }

        const offset = this.nodeOffsets[nodeId];
        const node = this._getNode(offset, nodeId);
        return Array.from(node.children.keys()).sort();
    }

    _collectWords(nodeId, prefix, results, limit = Infinity) {
        if (results.length >= limit) return;

        const offset = this.nodeOffsets[nodeId];
        const node = this._getNode(offset, nodeId);

        if (node.isTerminal) {
            results.push(prefix);
        }

        for (const [char, childId] of node.children) {
            this._collectWords(childId, prefix + char, results, limit);
        }
    }

    getAllWords() {
        if (this.words.length === 0) {
            this._collectWords(this.rootId, '', this.words, this.wordCount);
        }
        return this.words;
    }

    getRandomWords(count) {
        const allWords = this.getAllWords();
        const selected = [];
        for (let i = 0; i < count && i < allWords.length; i++) {
            const randomIdx = Math.floor(Math.random() * allWords.length);
            selected.push(allWords[randomIdx]);
        }
        return selected;
    }

    getPredecessor(text) {
        const allWords = this.getAllWords();
        let left = 0;
        let right = allWords.length - 1;

        while (left <= right) {
            const mid = Math.floor((left + right) / 2);
            if (allWords[mid] < text) {
                left = mid + 1;
            } else {
                right = mid - 1;
            }
        }

        return right >= 0 ? allWords[right] : null;
    }

    getSuccessor(text) {
        const allWords = this.getAllWords();
        let left = 0;
        let right = allWords.length - 1;

        while (left <= right) {
            const mid = Math.floor((left + right) / 2);
            if (allWords[mid] <= text) {
                left = mid + 1;
            } else {
                right = mid - 1;
            }
        }

        return left < allWords.length ? allWords[left] : null;
    }

    getStats() {
        return {
            wordCount: this.wordCount,
            nodeCount: this.nodeOffsets.length,
            sizeBytes: this.buffer.length,
            bytesPerWord: (this.buffer.length / this.wordCount).toFixed(2)
        };
    }
}

// ============================================================================
// Dynamic Trie - Built from plain text wordlist
// ============================================================================

class TrieNode {
    constructor() {
        this.children = new Map();
        this.isWord = false;
    }
}

class DynamicTrie {
    constructor() {
        this.root = new TrieNode();
        this.words = [];
    }

    insert(word) {
        let node = this.root;
        for (const char of word) {
            if (!node.children.has(char)) {
                node.children.set(char, new TrieNode());
            }
            node = node.children.get(char);
        }
        node.isWord = true;
        this.words.push(word);
    }

    _search(prefix) {
        let node = this.root;
        for (const char of prefix) {
            if (!node.children.has(char)) {
                return null;
            }
            node = node.children.get(char);
        }
        return node;
    }

    has(word) {
        const node = this._search(word);
        return node !== null && node.isWord;
    }

    isValidPrefix(prefix) {
        return this._search(prefix) !== null;
    }

    findLongestValidPrefix(text) {
        let validPrefix = '';
        let node = this.root;

        for (let i = 0; i < text.length; i++) {
            const char = text[i];
            if (!node.children.has(char)) {
                break;
            }
            node = node.children.get(char);
            validPrefix += char;
        }

        return validPrefix;
    }

    getNextLetters(prefix) {
        const node = this._search(prefix);
        if (!node) return [];
        return Array.from(node.children.keys()).sort();
    }

    getAllWords() {
        return this.words;
    }

    getRandomWords(count) {
        const selected = [];
        const totalWords = this.words.length;
        for (let i = 0; i < count && i < totalWords; i++) {
            const randomIdx = Math.floor(Math.random() * totalWords);
            selected.push(this.words[randomIdx]);
        }
        return selected;
    }

    getPredecessor(word) {
        const sortedWords = [...this.words].sort();
        const idx = sortedWords.findIndex(w => w >= word);
        return idx > 0 ? sortedWords[idx - 1] : null;
    }

    getSuccessor(word) {
        const sortedWords = [...this.words].sort();
        const idx = sortedWords.findIndex(w => w > word);
        return idx !== -1 ? sortedWords[idx] : null;
    }

    getStats() {
        // Estimate size by counting nodes
        let nodeCount = 0;
        const countNodes = (node) => {
            nodeCount++;
            for (const child of node.children.values()) {
                countNodes(child);
            }
        };
        countNodes(this.root);

        return {
            wordCount: this.words.length,
            nodeCount: nodeCount,
            sizeBytes: null,
            bytesPerWord: null
        };
    }
}

// ============================================================================
// Application State and UI
// ============================================================================

let trie = null;
let loadMode = null;
let isLoading = true;

// DOM elements
const statusEl = document.getElementById('status');
const userInput = document.getElementById('userInput');
const displaySection = document.getElementById('displaySection');
const typedDisplay = document.getElementById('typedDisplay');
const randomWordsEl = document.getElementById('randomWords');
const refreshBtn = document.getElementById('refreshBtn');
const totalWordsEl = document.getElementById('totalWords');
const nodeCountEl = document.getElementById('nodeCount');
const currentStateEl = document.getElementById('currentState');
const loadModeEl = document.getElementById('loadMode');

// Update status display
function setStatus(message, className = '') {
    statusEl.textContent = message;
    statusEl.className = 'status ' + className;
}

// Load binary trie from pre-built file
async function loadBinaryTrie() {
    setStatus('Downloading binary trie...', 'loading');

    const response = await fetch('/data/en.trie.bin');
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const arrayBuffer = await response.arrayBuffer();

    setStatus('Parsing binary trie...', 'loading');
    const binaryTrie = new BinaryTrie();
    await binaryTrie.load(arrayBuffer);

    return binaryTrie;
}

// Load plain text wordlist and build trie dynamically
async function loadDynamicTrie() {
    setStatus('Downloading wordlist...', 'loading');

    const response = await fetch('/data/build/en-wordlist.txt');
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const text = await response.text();
    const words = text.trim().split('\n');

    setStatus(`Building trie from ${words.length.toLocaleString()} words...`, 'loading');

    const dynamicTrie = new DynamicTrie();
    let count = 0;

    for (const word of words) {
        if (word.trim()) {
            dynamicTrie.insert(word.trim());
            count++;
            if (count % 10000 === 0) {
                setStatus(`Building trie: ${count.toLocaleString()} / ${words.length.toLocaleString()}...`, 'loading');
                await new Promise(resolve => setTimeout(resolve, 0));
            }
        }
    }

    return dynamicTrie;
}

// Main initialization - try binary first, fallback to dynamic
async function initialize() {
    try {
        // First try binary trie (fast)
        trie = await loadBinaryTrie();
        loadMode = 'binary';
    } catch (binaryError) {
        console.warn('Binary trie not available:', binaryError.message);
        console.log('Falling back to dynamic trie...');

        try {
            // Fall back to dynamic trie (slower)
            trie = await loadDynamicTrie();
            loadMode = 'dynamic';
        } catch (dynamicError) {
            setStatus(`Error: ${dynamicError.message}`, 'error');
            console.error('Failed to load any trie:', dynamicError);
            return;
        }
    }

    // Success - enable UI
    isLoading = false;
    const stats = trie.getStats();

    let statusMsg = `Ready! Loaded ${stats.wordCount.toLocaleString()} words`;
    if (stats.bytesPerWord) {
        statusMsg += ` (${(stats.sizeBytes / 1024).toFixed(1)} KB)`;
    }
    setStatus(statusMsg, 'ready');

    // Update stats display
    totalWordsEl.textContent = stats.wordCount.toLocaleString();
    nodeCountEl.textContent = stats.nodeCount.toLocaleString();
    currentStateEl.textContent = '-';

    // Show load mode
    if (loadMode === 'binary') {
        loadModeEl.innerHTML = `<strong>Mode:</strong> Binary DAWG (instant load)`;
    } else {
        loadModeEl.innerHTML = `<strong>Mode:</strong> Dynamic trie (built from wordlist)`;
    }

    // Enable input
    userInput.disabled = false;
    refreshBtn.disabled = false;
    userInput.focus();

    // Show initial random words
    showRandomWords();
}

// Update display based on user input
function updateDisplay(text) {
    // Clear previous feedback sections
    const oldNext = document.querySelector('.next-letters');
    const oldNeighbors = document.querySelector('.neighbors');
    if (oldNext) oldNext.remove();
    if (oldNeighbors) oldNeighbors.remove();

    if (!text) {
        typedDisplay.innerHTML = '<span style="color: #999;">Start typing to explore...</span>';
        currentStateEl.textContent = '-';
        return;
    }

    const validPrefix = trie.findLongestValidPrefix(text);
    const invalidSuffix = text.substring(validPrefix.length);

    let html = '';

    if (validPrefix) {
        html += `<span class="valid-prefix">${validPrefix}</span>`;
    }

    if (invalidSuffix) {
        html += `<span class="invalid-suffix">${invalidSuffix}</span>`;
    }

    // Check if it's a complete word
    if (trie.has(text)) {
        html += '<span class="annotation">complete word</span>';
        currentStateEl.textContent = 'Complete';
    } else if (trie.isValidPrefix(text)) {
        currentStateEl.textContent = 'Prefix';
    } else {
        currentStateEl.textContent = 'Invalid';
    }

    typedDisplay.innerHTML = html;

    // Show next possible letters for valid prefix
    if (trie.isValidPrefix(text)) {
        const nextLetters = trie.getNextLetters(text);
        if (nextLetters.length > 0) {
            const nextSection = document.createElement('div');
            nextSection.className = 'next-letters';
            nextSection.innerHTML = `
                <h3>Next possible letters:</h3>
                <div class="letters-list">
                    ${nextLetters.map(l => `<span class="letter-badge">${l}</span>`).join('')}
                </div>
            `;
            displaySection.appendChild(nextSection);
        }
    }

    // Show neighbors for invalid suffix
    if (invalidSuffix) {
        const predecessor = trie.getPredecessor(text);
        const successor = trie.getSuccessor(text);

        if (predecessor || successor) {
            const neighborsSection = document.createElement('div');
            neighborsSection.className = 'neighbors';
            let neighborHtml = '<h3>Nearby words in dictionary:</h3>';

            if (predecessor) {
                neighborHtml += `<div class="neighbor">&larr; Before: <strong>${predecessor}</strong></div>`;
            }
            if (successor) {
                neighborHtml += `<div class="neighbor">&rarr; After: <strong>${successor}</strong></div>`;
            }

            neighborsSection.innerHTML = neighborHtml;
            displaySection.appendChild(neighborsSection);
        }
    }
}

// Show random words
function showRandomWords() {
    const words = trie.getRandomWords(10);
    randomWordsEl.innerHTML = words.map(word =>
        `<div class="word-item" data-word="${word}">${word}</div>`
    ).join('');
}

// Select a word from random list
function selectWord(word) {
    userInput.value = word;
    updateDisplay(word);
}

// Event listeners
userInput.addEventListener('input', (e) => {
    if (isLoading) return;
    updateDisplay(e.target.value.toLowerCase());
});

refreshBtn.addEventListener('click', () => {
    if (!isLoading) {
        showRandomWords();
    }
});

randomWordsEl.addEventListener('click', (e) => {
    const wordItem = e.target.closest('.word-item');
    if (wordItem && !isLoading) {
        selectWord(wordItem.dataset.word);
    }
});

// Start loading
initialize();
