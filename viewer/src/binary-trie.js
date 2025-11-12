/**
 * binary-trie.js - Browser-side binary trie loader
 *
 * Efficiently loads and navigates the compact binary DAWG format.
 */

export class BinaryTrie {
  constructor() {
    this.buffer = null;
    this.view = null;
    this.wordCount = 0;
    this.nodeOffsets = []; // Map node ID to byte offset
    this.words = []; // Cache of all words (lazy loaded)
  }

  /**
   * Load binary trie from ArrayBuffer
   */
  async load(arrayBuffer) {
    this.buffer = new Uint8Array(arrayBuffer);
    this.view = new DataView(arrayBuffer);

    // Parse header
    const magic = new TextDecoder().decode(this.buffer.slice(0, 6));
    if (magic !== 'OWTRIE') {
      throw new Error('Invalid trie file: bad magic number');
    }

    const version = this.view.getUint16(6, true);
    if (version !== 1) {
      throw new Error(`Unsupported trie version: ${version}`);
    }

    this.wordCount = this.view.getUint32(8, true);

    // Build node offset index
    this._buildNodeIndex();

    console.log(`Loaded binary trie: ${this.wordCount.toLocaleString()} words, ${this.nodeOffsets.length} nodes`);
  }

  /**
   * Build index mapping node ID to byte offset
   */
  _buildNodeIndex() {
    let offset = 12; // After header
    let nodeId = 0;

    while (offset < this.buffer.length) {
      this.nodeOffsets[nodeId++] = offset;

      const flagsByte = this.buffer[offset++];
      const childCount = flagsByte & 0x7F;

      // Skip children (char + offset = 3 bytes each)
      offset += childCount * 3;
    }
  }

  /**
   * Get node info at given offset
   */
  _getNode(offset) {
    const flagsByte = this.buffer[offset];
    const isTerminal = (flagsByte & 0x80) !== 0;
    const childCount = flagsByte & 0x7F;

    const children = new Map();
    let childOffset = offset + 1;

    for (let i = 0; i < childCount; i++) {
      const char = String.fromCharCode(this.buffer[childOffset]);
      const nodeId = this.view.getUint16(childOffset + 1, true);
      children.set(char, nodeId);
      childOffset += 3;
    }

    return { isTerminal, children };
  }

  /**
   * Check if word exists in trie
   */
  has(word) {
    let nodeId = 0; // Start at root

    for (const char of word) {
      const offset = this.nodeOffsets[nodeId];
      const node = this._getNode(offset);

      if (!node.children.has(char)) {
        return false;
      }

      nodeId = node.children.get(char);
    }

    const offset = this.nodeOffsets[nodeId];
    const node = this._getNode(offset);
    return node.isTerminal;
  }

  /**
   * Find longest valid prefix of text
   */
  findLongestValidPrefix(text) {
    let nodeId = 0;
    let validPrefix = '';

    for (let i = 0; i < text.length; i++) {
      const char = text[i];
      const offset = this.nodeOffsets[nodeId];
      const node = this._getNode(offset);

      if (!node.children.has(char)) {
        break;
      }

      nodeId = node.children.get(char);
      validPrefix += char;
    }

    return validPrefix;
  }

  /**
   * Get next possible characters after a prefix
   */
  getNextChars(prefix) {
    let nodeId = 0;

    // Navigate to prefix
    for (const char of prefix) {
      const offset = this.nodeOffsets[nodeId];
      const node = this._getNode(offset);

      if (!node.children.has(char)) {
        return [];
      }

      nodeId = node.children.get(char);
    }

    // Get children of current node
    const offset = this.nodeOffsets[nodeId];
    const node = this._getNode(offset);

    return Array.from(node.children.keys()).sort();
  }

  /**
   * Check if prefix exists (may or may not be a complete word)
   */
  hasPrefix(prefix) {
    let nodeId = 0;

    for (const char of prefix) {
      const offset = this.nodeOffsets[nodeId];
      const node = this._getNode(offset);

      if (!node.children.has(char)) {
        return false;
      }

      nodeId = node.children.get(char);
    }

    return true;
  }

  /**
   * Get all words with given prefix
   */
  keysWithPrefix(prefix) {
    let nodeId = 0;

    // Navigate to prefix
    for (const char of prefix) {
      const offset = this.nodeOffsets[nodeId];
      const node = this._getNode(offset);

      if (!node.children.has(char)) {
        return [];
      }

      nodeId = node.children.get(char);
    }

    // Collect all words from this node
    const words = [];
    this._collectWords(nodeId, prefix, words);
    return words;
  }

  /**
   * Recursively collect all words from a node
   */
  _collectWords(nodeId, prefix, results, limit = 1000) {
    if (results.length >= limit) return;

    const offset = this.nodeOffsets[nodeId];
    const node = this._getNode(offset);

    if (node.isTerminal) {
      results.push(prefix);
    }

    for (const [char, childId] of node.children) {
      this._collectWords(childId, prefix + char, results, limit);
    }
  }

  /**
   * Get all words (lazy loaded)
   */
  getAllWords() {
    if (this.words.length === 0) {
      this._collectWords(0, '', this.words, this.wordCount);
    }
    return this.words;
  }

  /**
   * Get random word
   */
  getRandomWord() {
    const allWords = this.getAllWords();
    return allWords[Math.floor(Math.random() * allWords.length)];
  }

  /**
   * Find predecessor word (previous in lexicographic order)
   */
  getPredecessor(text) {
    const allWords = this.getAllWords();

    // Binary search for insertion point
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

    // right is now the index of largest word < text
    return right >= 0 ? allWords[right] : null;
  }

  /**
   * Find successor word (next in lexicographic order)
   */
  getSuccessor(text) {
    const allWords = this.getAllWords();

    // Binary search for insertion point
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

    // left is now the index of smallest word > text
    return left < allWords.length ? allWords[left] : null;
  }

  /**
   * Get trie statistics
   */
  getStats() {
    return {
      wordCount: this.wordCount,
      nodeCount: this.nodeOffsets.length,
      sizeBytes: this.buffer.length,
      bytesPerWord: (this.buffer.length / this.wordCount).toFixed(2)
    };
  }
}
