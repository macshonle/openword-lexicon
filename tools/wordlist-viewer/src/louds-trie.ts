/**
 * louds-trie.ts - LOUDS-encoded trie for word storage and lookup
 *
 * Implementation based on:
 * - Jacobson, G. (1989) "Space-efficient Static Trees and Graphs" - FOCS 1989
 * - Delpratt, O., Rahman, N., Raman, R. (2006) "Engineering the LOUDS
 *   Succinct Tree Representation" - WEA 2006
 * - Hanov, S. "Succinct Data Structures" - stevehanov.ca/blog/?id=120
 *
 * This module provides a complete LOUDS trie implementation that:
 * - Stores a set of words compactly using LOUDS encoding
 * - Supports O(m) membership queries where m is word length
 * - Maps each word to a sequential ID (0-indexed) via terminal ranking
 * - Supports prefix queries to find all words with a given prefix
 */

import { BitVector } from './bitvector.js';

// Varint encoding helpers (same as build-trie.ts)
function varintSize(value: number): number {
  if (value < 0x80) return 1;
  if (value < 0x4000) return 2;
  if (value < 0x200000) return 3;
  if (value < 0x10000000) return 4;
  return 5;
}

function writeVarint(buffer: Uint8Array, offset: number, value: number): number {
  while (value >= 0x80) {
    buffer[offset++] = (value & 0x7f) | 0x80;
    value >>>= 7;
  }
  buffer[offset++] = value;
  return offset;
}

function readVarint(buffer: Uint8Array, offset: number): { value: number; bytesRead: number } {
  let value = 0;
  let shift = 0;
  let bytesRead = 0;
  while (true) {
    const byte = buffer[offset + bytesRead];
    bytesRead++;
    value |= (byte & 0x7f) << shift;
    if ((byte & 0x80) === 0) break;
    shift += 7;
  }
  return { value, bytesRead };
}

/**
 * Trie node for building phase (not LOUDS encoded yet).
 */
class TrieNode {
  children: Map<number, TrieNode> = new Map(); // char code point -> child
  isTerminal: boolean = false;
}

/**
 * LOUDS-encoded trie with word lookup and ID mapping.
 *
 * The trie stores:
 * - LOUDS bitvector for tree structure
 * - Terminal bitvector marking end-of-word nodes
 * - Labels array with Unicode code points for each edge
 *
 * Word IDs are assigned in BFS traversal order of terminal nodes.
 * ID = rank1(terminal, nodeId) - 1 (0-indexed)
 */
export class LOUDSTrie {
  /** LOUDS bitvector encoding tree structure */
  readonly bits: BitVector;

  /** Terminal bitvector marking end-of-word nodes */
  readonly terminal: BitVector;

  /** Labels for each edge (Unicode code points) */
  readonly labels: Uint32Array;

  /** Number of nodes (including super-root) */
  readonly nodeCount: number;

  /** Number of words stored */
  readonly wordCount: number;

  constructor(
    bits: BitVector,
    terminal: BitVector,
    labels: Uint32Array,
    nodeCount: number,
    wordCount: number
  ) {
    this.bits = bits;
    this.terminal = terminal;
    this.labels = labels;
    this.nodeCount = nodeCount;
    this.wordCount = wordCount;
  }

  /**
   * Build a LOUDS trie from an array of words.
   * Words should be pre-sorted for consistent ordering.
   *
   * @param words Array of words to store
   * @returns A new LOUDSTrie
   */
  static build(words: string[]): LOUDSTrie {
    // Phase 1: Build standard trie
    const root = new TrieNode();
    for (const word of words) {
      let node = root;
      for (const char of word) {
        const code = char.codePointAt(0)!;
        if (!node.children.has(code)) {
          node.children.set(code, new TrieNode());
        }
        node = node.children.get(code)!;
      }
      node.isTerminal = true;
    }

    // Phase 2: Count nodes via BFS
    // Note: Use index-based iteration instead of shift() for O(n) vs O(n²)
    let nodeCount = 0;
    let edgeCount = 0;
    const countQueue: TrieNode[] = [root];
    for (let qi = 0; qi < countQueue.length; qi++) {
      const node = countQueue[qi];
      nodeCount++;
      edgeCount += node.children.size;
      // Sort children by code point for consistent order
      const sortedCodes = Array.from(node.children.keys()).sort((a, b) => a - b);
      for (const code of sortedCodes) {
        countQueue.push(node.children.get(code)!);
      }
    }

    // Phase 3: Allocate structures
    // LOUDS bits: 2n + 1 for n nodes
    const bitCount = 2 * nodeCount + 1;
    const bits = new BitVector(bitCount);
    const terminal = new BitVector(nodeCount + 1); // +1 for super-root
    const labels = new Uint32Array(edgeCount);

    // Phase 4: BFS traversal to build LOUDS
    let bitPos = 0;
    let labelPos = 0;
    let nodeId = 0;

    // Super-root: "10" (one child = actual root)
    bits.set(bitPos++); // 1
    bitPos++; // 0 (implicit)
    nodeId++; // super-root is node 0

    // Map from TrieNode to nodeId for terminal marking
    const nodeIds = new Map<TrieNode, number>();
    nodeIds.set(root, 1); // root is node 1

    // Note: Use index-based iteration instead of shift() for O(n) vs O(n²)
    const queue: TrieNode[] = [root];
    let nextNodeId = 2; // Next node to assign

    for (let qi = 0; qi < queue.length; qi++) {
      const node = queue[qi];
      const currentNodeId = nodeIds.get(node)!;

      // Mark terminal
      if (node.isTerminal) {
        terminal.set(currentNodeId);
      }

      // Sort children by code point for consistent order
      const sortedCodes = Array.from(node.children.keys()).sort((a, b) => a - b);

      // Output degree in unary: k ones followed by zero
      for (const code of sortedCodes) {
        bits.set(bitPos++); // 1 for each child
        labels[labelPos++] = code;

        const child = node.children.get(code)!;
        nodeIds.set(child, nextNodeId++);
        queue.push(child);
      }
      bitPos++; // 0 to terminate
    }

    bits.build();
    terminal.build();

    return new LOUDSTrie(bits, terminal, labels, nodeCount + 1, words.length);
  }

  /**
   * Get the number of children of a node.
   */
  private childCount(nodeId: number): number {
    const start = nodeId === 0 ? 0 : this.bits.select0(nodeId) + 1;
    const end = this.bits.select0(nodeId + 1);
    return end - start;
  }

  /**
   * Get the label index for the first child of a node.
   * Labels are stored in edge order, so we need to count edges before this node.
   * Note: super-root's edge to root has no label, so we subtract 1.
   */
  private firstLabelIndex(nodeId: number): number {
    if (nodeId === 0) return -1; // super-root has no labels
    const start = this.bits.select0(nodeId) + 1;
    // Subtract 1 because super-root's edge (the first 1-bit) has no label
    return this.bits.rank1(start - 1) - 1;
  }

  /**
   * Find a child node by character.
   *
   * @param nodeId Current node
   * @param char Character to find
   * @returns Child node ID, or -1 if not found
   */
  findChild(nodeId: number, char: string): number {
    const code = char.codePointAt(0)!;
    const count = this.childCount(nodeId);
    if (count === 0) return -1;

    const labelStart = this.firstLabelIndex(nodeId);
    const firstChildId = this.bits.rank1(this.bits.select0(nodeId) + 1);

    // Binary search through sorted children
    let lo = 0;
    let hi = count - 1;
    while (lo <= hi) {
      const mid = Math.floor((lo + hi) / 2);
      const midLabel = this.labels[labelStart + mid];
      if (midLabel === code) {
        return firstChildId + mid;
      } else if (midLabel < code) {
        lo = mid + 1;
      } else {
        hi = mid - 1;
      }
    }

    return -1;
  }

  /**
   * Check if a word exists in the trie.
   *
   * @param word Word to look up
   * @returns true if word exists
   */
  has(word: string): boolean {
    let nodeId = 1; // Start at root (node 1, after super-root)

    for (const char of word) {
      nodeId = this.findChild(nodeId, char);
      if (nodeId === -1) return false;
    }

    return this.terminal.get(nodeId);
  }

  /**
   * Get the ID of a word (0-indexed, in BFS terminal order).
   *
   * @param word Word to look up
   * @returns Word ID, or -1 if not found
   */
  wordId(word: string): number {
    let nodeId = 1;

    for (const char of word) {
      nodeId = this.findChild(nodeId, char);
      if (nodeId === -1) return -1;
    }

    if (!this.terminal.get(nodeId)) return -1;

    // ID = rank of this terminal among all terminals (0-indexed)
    return this.terminal.rank1(nodeId) - 1;
  }

  /**
   * Get all children of a node with their labels.
   *
   * @param nodeId Node to get children of
   * @returns Array of [label, childNodeId] pairs
   */
  getChildren(nodeId: number): Array<[string, number]> {
    const count = this.childCount(nodeId);
    if (count === 0) return [];

    const labelStart = this.firstLabelIndex(nodeId);
    const firstChildId = this.bits.rank1(this.bits.select0(nodeId) + 1);

    const result: Array<[string, number]> = [];
    for (let i = 0; i < count; i++) {
      const label = String.fromCodePoint(this.labels[labelStart + i]);
      result.push([label, firstChildId + i]);
    }
    return result;
  }

  /**
   * Get words with a given prefix.
   *
   * @param prefix Prefix to search for
   * @param limit Maximum number of words to return
   * @returns Array of words with the prefix
   */
  keysWithPrefix(prefix: string, limit: number = 100): string[] {
    // Navigate to prefix node
    let nodeId = 1;
    for (const char of prefix) {
      nodeId = this.findChild(nodeId, char);
      if (nodeId === -1) return [];
    }

    // DFS to collect words
    const results: string[] = [];
    const stack: Array<[number, string]> = [[nodeId, prefix]];

    while (stack.length > 0 && results.length < limit) {
      const [node, word] = stack.pop()!;

      if (this.terminal.get(node)) {
        results.push(word);
      }

      // Add children in reverse order so smallest comes out first
      const children = this.getChildren(node);
      for (let i = children.length - 1; i >= 0; i--) {
        const [label, childId] = children[i];
        stack.push([childId, word + label]);
      }
    }

    return results;
  }

  /**
   * Serialize the trie to binary format (v5).
   *
   * Format:
   * - Header (16 bytes):
   *   - Magic: "OWTRIE" (6 bytes)
   *   - Version: uint16 = 5 (2 bytes)
   *   - Word count: uint32 (4 bytes)
   *   - Node count: uint32 (4 bytes)
   * - LOUDS bitvector (serialized BitVector)
   * - Terminal bitvector (serialized BitVector)
   * - Labels (varint encoded code points)
   */
  serialize(): Uint8Array {
    const bitsBytes = this.bits.serialize();
    const terminalBytes = this.terminal.serialize();

    // Calculate labels size (varint encoded)
    let labelsSize = 4; // length prefix
    for (let i = 0; i < this.labels.length; i++) {
      labelsSize += varintSize(this.labels[i]);
    }

    const headerSize = 16;
    const totalSize = headerSize + 4 + bitsBytes.length + 4 + terminalBytes.length + labelsSize;

    const buffer = new Uint8Array(totalSize);
    const view = new DataView(buffer.buffer);
    let offset = 0;

    // Header
    buffer.set(new TextEncoder().encode('OWTRIE'), offset);
    offset += 6;
    view.setUint16(offset, 5, true); // version 5
    offset += 2;
    view.setUint32(offset, this.wordCount, true);
    offset += 4;
    view.setUint32(offset, this.nodeCount, true);
    offset += 4;

    // LOUDS bitvector
    view.setUint32(offset, bitsBytes.length, true);
    offset += 4;
    buffer.set(bitsBytes, offset);
    offset += bitsBytes.length;

    // Terminal bitvector
    view.setUint32(offset, terminalBytes.length, true);
    offset += 4;
    buffer.set(terminalBytes, offset);
    offset += terminalBytes.length;

    // Labels
    view.setUint32(offset, this.labels.length, true);
    offset += 4;
    for (let i = 0; i < this.labels.length; i++) {
      offset = writeVarint(buffer, offset, this.labels[i]);
    }

    return buffer.slice(0, offset);
  }

  /**
   * Deserialize a trie from binary format (v5).
   */
  static deserialize(buffer: Uint8Array): LOUDSTrie {
    const view = new DataView(buffer.buffer, buffer.byteOffset, buffer.byteLength);
    let offset = 0;

    // Header
    const magic = new TextDecoder().decode(buffer.slice(offset, offset + 6));
    if (magic !== 'OWTRIE') {
      throw new Error('Invalid trie file: bad magic number');
    }
    offset += 6;

    const version = view.getUint16(offset, true);
    if (version !== 5) {
      throw new Error(`Unsupported trie version: ${version}. Expected v5.`);
    }
    offset += 2;

    const wordCount = view.getUint32(offset, true);
    offset += 4;
    const nodeCount = view.getUint32(offset, true);
    offset += 4;

    // LOUDS bitvector
    const bitsLength = view.getUint32(offset, true);
    offset += 4;
    const bits = BitVector.deserialize(buffer.slice(offset, offset + bitsLength));
    offset += bitsLength;

    // Terminal bitvector
    const terminalLength = view.getUint32(offset, true);
    offset += 4;
    const terminal = BitVector.deserialize(buffer.slice(offset, offset + terminalLength));
    offset += terminalLength;

    // Labels
    const labelsCount = view.getUint32(offset, true);
    offset += 4;
    const labels = new Uint32Array(labelsCount);
    for (let i = 0; i < labelsCount; i++) {
      const { value, bytesRead } = readVarint(buffer, offset);
      labels[i] = value;
      offset += bytesRead;
    }

    return new LOUDSTrie(bits, terminal, labels, nodeCount, wordCount);
  }

  /**
   * Get statistics about the trie.
   */
  stats(): {
    wordCount: number;
    nodeCount: number;
    edgeCount: number;
    bitsSize: number;
    terminalSize: number;
    labelsSize: number;
    totalSize: number;
  } {
    const bitsBytes = this.bits.serialize();
    const terminalBytes = this.terminal.serialize();
    let labelsSize = 4;
    for (let i = 0; i < this.labels.length; i++) {
      labelsSize += varintSize(this.labels[i]);
    }

    return {
      wordCount: this.wordCount,
      nodeCount: this.nodeCount,
      edgeCount: this.labels.length,
      bitsSize: bitsBytes.length,
      terminalSize: terminalBytes.length,
      labelsSize,
      totalSize: 16 + 4 + bitsBytes.length + 4 + terminalBytes.length + labelsSize,
    };
  }

  /**
   * Get statistics in the format expected by app.js.
   */
  getStats(): {
    wordCount: number;
    nodeCount: number;
    sizeBytes: number;
    bytesPerWord: string;
  } {
    const s = this.stats();
    return {
      wordCount: s.wordCount,
      nodeCount: s.nodeCount,
      sizeBytes: s.totalSize,
      bytesPerWord: (s.totalSize / s.wordCount).toFixed(2),
    };
  }
}
