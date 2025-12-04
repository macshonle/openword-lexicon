/**
 * Wordlist Viewer - Interactive Trie Explorer
 *
 * Unified viewer that loads either:
 * 1. Pre-built binary DAWG v2/v4 (fast, recommended)
 * 2. Pre-built LOUDS trie v5 (fast, with word IDs)
 * 3. Plain text wordlist (slower, builds trie in browser)
 */

// ============================================================================
// BitVector - Succinct bitvector with O(1) rank and O(log n) select
// Used by LOUDS trie (v5 format)
// ============================================================================

const BLOCK_SIZE = 32;
const SUPERBLOCK_SIZE = 256;
const BLOCKS_PER_SUPERBLOCK = SUPERBLOCK_SIZE / BLOCK_SIZE;

class BitVector {
    constructor(length) {
        this._length = length;
        const wordCount = Math.ceil(length / BLOCK_SIZE);
        this.words = new Uint32Array(wordCount);
        this.superblocks = new Uint32Array(Math.ceil(length / SUPERBLOCK_SIZE));
        this.blocks = new Uint8Array(wordCount);
        this._popcount = 0;
    }

    get length() { return this._length; }
    get popcount() { return this._popcount; }

    get(i) {
        const wordIndex = Math.floor(i / BLOCK_SIZE);
        const bitIndex = i % BLOCK_SIZE;
        return (this.words[wordIndex] & (1 << bitIndex)) !== 0;
    }

    _popcountWord(word) {
        word = word - ((word >>> 1) & 0x55555555);
        word = (word & 0x33333333) + ((word >>> 2) & 0x33333333);
        word = (word + (word >>> 4)) & 0x0f0f0f0f;
        word = word + (word >>> 8);
        word = word + (word >>> 16);
        return word & 0x3f;
    }

    rank1(i) {
        if (i < 0) return 0;
        if (i >= this._length) return this._popcount;

        const wordIndex = Math.floor(i / BLOCK_SIZE);
        const bitIndex = i % BLOCK_SIZE;
        const superblockIndex = Math.floor(wordIndex / BLOCKS_PER_SUPERBLOCK);

        let rank = this.superblocks[superblockIndex] + this.blocks[wordIndex];
        const mask = bitIndex === 31 ? 0xFFFFFFFF : (1 << (bitIndex + 1)) - 1;
        rank += this._popcountWord((this.words[wordIndex] & mask) >>> 0);

        return rank;
    }

    rank0(i) {
        if (i < 0) return 0;
        if (i >= this._length) return this._length - this._popcount;
        return (i + 1) - this.rank1(i);
    }

    select0(j) {
        if (j < 1 || j > this._length - this._popcount) return -1;
        let lo = 0, hi = this._length - 1;
        while (lo < hi) {
            const mid = Math.floor((lo + hi) / 2);
            if (this.rank0(mid) < j) lo = mid + 1;
            else hi = mid;
        }
        return lo;
    }

    select1(j) {
        if (j < 1 || j > this._popcount) return -1;
        let lo = 0, hi = this.superblocks.length - 1;
        while (lo < hi) {
            const mid = Math.floor((lo + hi + 1) / 2);
            if (this.superblocks[mid] < j) lo = mid;
            else hi = mid - 1;
        }
        const superblockIndex = lo;
        let remaining = j - this.superblocks[superblockIndex];
        const blockStart = superblockIndex * BLOCKS_PER_SUPERBLOCK;
        const blockEnd = Math.min(blockStart + BLOCKS_PER_SUPERBLOCK, this.words.length);
        for (let wordIndex = blockStart; wordIndex < blockEnd; wordIndex++) {
            const wordPopcount = this._popcountWord(this.words[wordIndex]);
            if (remaining <= wordPopcount) {
                for (let i = 0; i < BLOCK_SIZE; i++) {
                    if ((this.words[wordIndex] & (1 << i)) !== 0) {
                        remaining--;
                        if (remaining === 0) return wordIndex * BLOCK_SIZE + i;
                    }
                }
            }
            remaining -= wordPopcount;
        }
        return -1;
    }

    static deserialize(buffer, offset) {
        const view = new DataView(buffer.buffer, buffer.byteOffset + offset, buffer.byteLength - offset);
        let pos = 0;
        const length = view.getUint32(pos, true); pos += 4;
        const bv = new BitVector(length);
        for (let i = 0; i < bv.words.length; i++) {
            bv.words[i] = view.getUint32(pos, true); pos += 4;
        }
        for (let i = 0; i < bv.superblocks.length; i++) {
            bv.superblocks[i] = view.getUint32(pos, true); pos += 4;
        }
        for (let i = 0; i < bv.blocks.length; i++) {
            bv.blocks[i] = buffer[offset + pos + i];
        }
        pos += bv.blocks.length;
        // Compute popcount
        if (bv.superblocks.length > 0) {
            const lastSb = bv.superblocks.length - 1;
            const lastBlockStart = lastSb * BLOCKS_PER_SUPERBLOCK;
            let popcount = bv.superblocks[lastSb];
            for (let i = lastBlockStart; i < bv.words.length; i++) {
                popcount += bv._popcountWord(bv.words[i]);
            }
            bv._popcount = popcount;
        }
        return { bv, bytesRead: pos };
    }
}

// ============================================================================
// LOUDS Binary Trie - Loads LOUDS format (v5)
// ============================================================================

class LOUDSBinaryTrie {
    constructor() {
        this.bits = null;
        this.terminal = null;
        this.labels = null;
        this.wordCount = 0;
        this.nodeCount = 0;
        this.words = [];
    }

    _readVarint(buffer, offset) {
        let value = 0, shift = 0, bytesRead = 0;
        while (true) {
            const byte = buffer[offset + bytesRead];
            bytesRead++;
            value |= (byte & 0x7f) << shift;
            if ((byte & 0x80) === 0) break;
            shift += 7;
        }
        return { value, bytesRead };
    }

    async load(arrayBuffer) {
        const buffer = new Uint8Array(arrayBuffer);
        const view = new DataView(arrayBuffer);
        let offset = 0;

        // Header
        const magic = new TextDecoder().decode(buffer.slice(0, 6));
        if (magic !== 'OWTRIE') throw new Error('Invalid trie file: bad magic number');
        offset += 6;

        const version = view.getUint16(offset, true); offset += 2;
        if (version !== 5) throw new Error(`Expected v5, got v${version}`);

        this.wordCount = view.getUint32(offset, true); offset += 4;
        this.nodeCount = view.getUint32(offset, true); offset += 4;

        // LOUDS bitvector
        const bitsLength = view.getUint32(offset, true); offset += 4;
        const { bv: bits, bytesRead: bitsRead } = BitVector.deserialize(buffer.slice(offset), 0);
        this.bits = bits;
        offset += bitsLength;

        // Terminal bitvector
        const terminalLength = view.getUint32(offset, true); offset += 4;
        const { bv: terminal } = BitVector.deserialize(buffer.slice(offset), 0);
        this.terminal = terminal;
        offset += terminalLength;

        // Labels
        const labelsCount = view.getUint32(offset, true); offset += 4;
        this.labels = new Uint32Array(labelsCount);
        for (let i = 0; i < labelsCount; i++) {
            const { value, bytesRead } = this._readVarint(buffer, offset);
            this.labels[i] = value;
            offset += bytesRead;
        }

        console.log(`Loaded LOUDS trie v5: ${this.wordCount.toLocaleString()} words, ${this.nodeCount} nodes`);
    }

    _childCount(nodeId) {
        const start = nodeId === 0 ? 0 : this.bits.select0(nodeId) + 1;
        const end = this.bits.select0(nodeId + 1);
        return end - start;
    }

    _firstLabelIndex(nodeId) {
        if (nodeId === 0) return -1;
        const start = this.bits.select0(nodeId) + 1;
        return this.bits.rank1(start - 1) - 1;
    }

    _findChild(nodeId, char) {
        const code = char.codePointAt(0);
        const count = this._childCount(nodeId);
        if (count === 0) return -1;

        const labelStart = this._firstLabelIndex(nodeId);
        const firstChildId = this.bits.rank1(this.bits.select0(nodeId) + 1);

        // Binary search through sorted children
        let lo = 0, hi = count - 1;
        while (lo <= hi) {
            const mid = Math.floor((lo + hi) / 2);
            const midLabel = this.labels[labelStart + mid];
            if (midLabel === code) return firstChildId + mid;
            else if (midLabel < code) lo = mid + 1;
            else hi = mid - 1;
        }
        return -1;
    }

    _getChildren(nodeId) {
        const count = this._childCount(nodeId);
        if (count === 0) return [];
        const labelStart = this._firstLabelIndex(nodeId);
        const firstChildId = this.bits.rank1(this.bits.select0(nodeId) + 1);
        const result = [];
        for (let i = 0; i < count; i++) {
            const label = String.fromCodePoint(this.labels[labelStart + i]);
            result.push([label, firstChildId + i]);
        }
        return result;
    }

    has(word) {
        let nodeId = 1; // Root is node 1
        for (const char of word) {
            nodeId = this._findChild(nodeId, char);
            if (nodeId === -1) return false;
        }
        return this.terminal.get(nodeId);
    }

    wordId(word) {
        let nodeId = 1;
        for (const char of word) {
            nodeId = this._findChild(nodeId, char);
            if (nodeId === -1) return -1;
        }
        if (!this.terminal.get(nodeId)) return -1;
        return this.terminal.rank1(nodeId) - 1;
    }

    isValidPrefix(prefix) {
        let nodeId = 1;
        for (const char of prefix) {
            nodeId = this._findChild(nodeId, char);
            if (nodeId === -1) return false;
        }
        return true;
    }

    findLongestValidPrefix(text) {
        let nodeId = 1;
        let validPrefix = '';
        for (let i = 0; i < text.length; i++) {
            const char = text[i];
            const nextNode = this._findChild(nodeId, char);
            if (nextNode === -1) break;
            nodeId = nextNode;
            validPrefix += char;
        }
        return validPrefix;
    }

    getNextLetters(prefix) {
        let nodeId = 1;
        for (const char of prefix) {
            nodeId = this._findChild(nodeId, char);
            if (nodeId === -1) return [];
        }
        return this._getChildren(nodeId).map(([label]) => label).sort();
    }

    _collectWords(nodeId, prefix, results, limit) {
        if (results.length >= limit) return;
        if (this.terminal.get(nodeId)) results.push(prefix);
        for (const [label, childId] of this._getChildren(nodeId)) {
            this._collectWords(childId, prefix + label, results, limit);
        }
    }

    getAllWords() {
        if (this.words.length === 0) {
            this._collectWords(1, '', this.words, this.wordCount);
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
        let left = 0, right = allWords.length - 1;
        while (left <= right) {
            const mid = Math.floor((left + right) / 2);
            if (allWords[mid] < text) left = mid + 1;
            else right = mid - 1;
        }
        return right >= 0 ? allWords[right] : null;
    }

    getSuccessor(text) {
        const allWords = this.getAllWords();
        let left = 0, right = allWords.length - 1;
        while (left <= right) {
            const mid = Math.floor((left + right) / 2);
            if (allWords[mid] <= text) left = mid + 1;
            else right = mid - 1;
        }
        return left < allWords.length ? allWords[left] : null;
    }

    keysWithPrefix(prefix, limit = 100) {
        let nodeId = 1;
        for (const char of prefix) {
            nodeId = this._findChild(nodeId, char);
            if (nodeId === -1) return [];
        }
        const results = [];
        this._collectWords(nodeId, prefix, results, limit);
        return results;
    }

    getStats() {
        return {
            wordCount: this.wordCount,
            nodeCount: this.nodeCount,
            sizeBytes: null,
            bytesPerWord: null
        };
    }
}

// ============================================================================
// Binary Trie - Loads pre-built compact DAWG format (v2/v4)
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

    // Check version to select appropriate loader
    const view = new DataView(arrayBuffer);
    const version = view.getUint16(6, true);

    setStatus('Parsing binary trie...', 'loading');

    let trie;
    if (version === 5) {
        // LOUDS trie (v5)
        trie = new LOUDSBinaryTrie();
    } else {
        // DAWG (v2/v4)
        trie = new BinaryTrie();
    }
    await trie.load(arrayBuffer);

    return trie;
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
