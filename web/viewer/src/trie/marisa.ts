/**
 * marisa.ts - MARISA trie implementation (OWTRIE v6)
 *
 * A TypeScript implementation of the MARISA trie data structure.
 * This module provides a compact, static trie with:
 * - LOUDS bitvector encoding for tree structure
 * - Terminal bitvector for end-of-word markers
 * - Link flags bitvector for path-compressed edges (v6.1+)
 * - Tail buffer for compressed suffixes (v6.1+)
 * - Optional recursive trie over tails (v6.3+)
 *
 * Implementation versions:
 * - v6.0: LOUDS baseline (equivalent to v5, establishes comparison point)
 * - v6.1: Link flags + tail buffer for path compression
 * - v6.2: Tail suffix sharing for deduplication
 * - v6.3: Recursive tail trie for large tail sets
 *
 * Works in both Node.js and browser environments.
 */

import { BitVector } from '../bitvector.js';
import { varintSize, writeVarint, readVarint } from './varint.js';
import {
  OWTRIE_MAGIC,
  HEADER_SIZE_V6,
  V6_FLAG_HAS_LINKS,
  V6_FLAG_HAS_TAILS,
  V6_FLAG_BINARY_TAILS,
} from './formats.js';

/**
 * Configuration for MARISA trie building.
 */
export interface MarisaConfig {
  /** Enable path compression with tail buffer (v6.1+) */
  enableLinks?: boolean;
  /** Use length-prefixed tails instead of null-terminated */
  binaryTails?: boolean;
  /** Minimum tail length to compress (default: 2) */
  minTailLength?: number;
}

/**
 * Statistics about a MARISA trie.
 */
export interface MarisaStats {
  wordCount: number;
  nodeCount: number;
  edgeCount: number;
  bitsSize: number;
  terminalSize: number;
  linkFlagsSize: number;
  labelsSize: number;
  tailBufferSize: number;
  totalSize: number;
  compressionRatio?: number;
}

/**
 * Internal trie node for building phase.
 */
class TrieNode {
  children: Map<number, TrieNode> = new Map(); // code point -> child
  isTerminal: boolean = false;
  /** For path compression: stores the full edge label if this is a compressed edge */
  edgeLabel: number[] | null = null;
}

/**
 * Result of building a MARISA trie.
 */
export interface MarisaBuildResult {
  trie: MarisaTrie;
  stats: MarisaStats;
}

/**
 * MARISA trie with LOUDS encoding and optional path compression.
 *
 * The trie stores:
 * - LOUDS bitvector for tree structure
 * - Terminal bitvector marking end-of-word nodes
 * - Link flags bitvector marking edges with tail references (v6.1+)
 * - Labels array with Unicode code points (or tail offsets for linked edges)
 * - Tail buffer with compressed suffixes (v6.1+)
 *
 * Word IDs are assigned in BFS traversal order of terminal nodes.
 * ID = rank1(terminal, nodeId) - 1 (0-indexed)
 */
export class MarisaTrie {
  /** LOUDS bitvector encoding tree structure */
  readonly bits: BitVector;

  /** Terminal bitvector marking end-of-word nodes */
  readonly terminal: BitVector;

  /** Link flags bitvector marking edges with tail references (null for v6.0) */
  readonly linkFlags: BitVector | null;

  /** Labels for each edge (code points or tail offsets) */
  readonly labels: Uint32Array;

  /** Tail buffer for path-compressed edges (null for v6.0) */
  readonly tailBuffer: Uint8Array | null;

  /** Tail end markers for null-terminated tails */
  readonly tailEnds: BitVector | null;

  /** Number of nodes (including super-root) */
  readonly nodeCount: number;

  /** Number of words stored */
  readonly wordCount: number;

  /** Format flags */
  readonly flags: number;

  constructor(
    bits: BitVector,
    terminal: BitVector,
    linkFlags: BitVector | null,
    labels: Uint32Array,
    tailBuffer: Uint8Array | null,
    tailEnds: BitVector | null,
    nodeCount: number,
    wordCount: number,
    flags: number = 0
  ) {
    this.bits = bits;
    this.terminal = terminal;
    this.linkFlags = linkFlags;
    this.labels = labels;
    this.tailBuffer = tailBuffer;
    this.tailEnds = tailEnds;
    this.nodeCount = nodeCount;
    this.wordCount = wordCount;
    this.flags = flags;
  }

  /**
   * Build a MARISA trie from an array of words.
   * Words should be pre-sorted for consistent ordering.
   *
   * @param words Array of words to store
   * @param config Optional configuration for path compression
   * @returns A new MarisaTrie with build statistics
   */
  static build(words: string[], config: MarisaConfig = {}): MarisaBuildResult {
    const enableLinks = config.enableLinks ?? false;
    const minTailLength = config.minTailLength ?? 2;

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

    // Phase 2: Path compression (if enabled)
    let tailBuffer: number[] = [];
    const tailOffsets = new Map<TrieNode, number>(); // node -> tail buffer offset

    if (enableLinks) {
      // Compress single-child chains into tail labels
      const compressNode = (node: TrieNode): void => {
        // Sort children for deterministic order
        const sortedCodes = Array.from(node.children.keys()).sort((a, b) => a - b);

        for (const code of sortedCodes) {
          const child = node.children.get(code)!;

          // Check if this is a compressible chain
          const chain: number[] = [code];
          let current = child;

          while (
            current.children.size === 1 &&
            !current.isTerminal &&
            chain.length < 255 // Limit chain length
          ) {
            const [nextCode, nextChild] = current.children.entries().next().value;
            chain.push(nextCode);
            current = nextChild;
          }

          if (chain.length >= minTailLength) {
            // Store tail in buffer
            const tailOffset = tailBuffer.length;
            tailOffsets.set(child, tailOffset);

            // Store tail as UTF-8 encoded bytes with null terminator
            const tailString = chain.map(c => String.fromCodePoint(c)).join('');
            const encoded = new TextEncoder().encode(tailString);
            tailBuffer.push(...encoded, 0); // null-terminated

            // Mark the edge with the tail
            child.edgeLabel = chain;

            // Replace child's children with the end of the chain
            node.children.set(code, current);
          }

          // Recursively process children
          compressNode(node.children.get(code)!);
        }
      };

      compressNode(root);
    }

    // Phase 3: Count nodes via BFS
    let nodeCount = 0;
    let edgeCount = 0;
    const countQueue: TrieNode[] = [root];
    for (let qi = 0; qi < countQueue.length; qi++) {
      const node = countQueue[qi];
      nodeCount++;
      edgeCount += node.children.size;
      const sortedCodes = Array.from(node.children.keys()).sort((a, b) => a - b);
      for (const code of sortedCodes) {
        countQueue.push(node.children.get(code)!);
      }
    }

    // Phase 4: Allocate structures
    const bitCount = 2 * nodeCount + 1;
    const bits = new BitVector(bitCount);
    const terminal = new BitVector(nodeCount + 1);
    const linkFlags = enableLinks ? new BitVector(edgeCount) : null;
    const labels = new Uint32Array(edgeCount);

    // Phase 5: BFS traversal to build LOUDS
    let bitPos = 0;
    let labelPos = 0;

    // Super-root: "10" (one child = actual root)
    bits.set(bitPos++); // 1
    bitPos++; // 0 (implicit)

    const nodeIds = new Map<TrieNode, number>();
    nodeIds.set(root, 1);

    const queue: TrieNode[] = [root];
    let nextNodeId = 2;

    for (let qi = 0; qi < queue.length; qi++) {
      const node = queue[qi];
      const currentNodeId = nodeIds.get(node)!;

      if (node.isTerminal) {
        terminal.set(currentNodeId);
      }

      const sortedCodes = Array.from(node.children.keys()).sort((a, b) => a - b);

      for (const code of sortedCodes) {
        bits.set(bitPos++);

        const child = node.children.get(code)!;

        if (enableLinks && tailOffsets.has(child)) {
          // This edge has a tail - store offset in labels
          linkFlags!.set(labelPos);
          labels[labelPos] = tailOffsets.get(child)!;
        } else {
          // Normal edge - store code point
          labels[labelPos] = code;
        }
        labelPos++;

        nodeIds.set(child, nextNodeId++);
        queue.push(child);
      }
      bitPos++; // 0 to terminate
    }

    bits.build();
    terminal.build();
    if (linkFlags) linkFlags.build();

    // Build tail buffer as Uint8Array
    const tailBufferArray = enableLinks && tailBuffer.length > 0
      ? new Uint8Array(tailBuffer)
      : null;

    // Compute flags
    let flags = 0;
    if (enableLinks) {
      flags |= V6_FLAG_HAS_LINKS;
      if (tailBufferArray) flags |= V6_FLAG_HAS_TAILS;
    }

    const trie = new MarisaTrie(
      bits,
      terminal,
      linkFlags,
      labels,
      tailBufferArray,
      null, // tailEnds not implemented yet
      nodeCount + 1,
      words.length,
      flags
    );

    const stats = trie.stats();

    return { trie, stats };
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
   */
  private firstLabelIndex(nodeId: number): number {
    if (nodeId === 0) return -1;
    const start = this.bits.select0(nodeId) + 1;
    return this.bits.rank1(start - 1) - 1;
  }

  /**
   * Read a tail from the tail buffer at the given offset.
   * Returns an array of code points.
   */
  private readTail(offset: number): number[] {
    if (!this.tailBuffer) return [];

    const codes: number[] = [];
    let pos = offset;

    // Read UTF-8 bytes until null terminator
    while (pos < this.tailBuffer.length && this.tailBuffer[pos] !== 0) {
      const byte = this.tailBuffer[pos];

      if (byte < 0x80) {
        // ASCII
        codes.push(byte);
        pos++;
      } else if ((byte & 0xe0) === 0xc0) {
        // 2-byte sequence
        const cp = ((byte & 0x1f) << 6) | (this.tailBuffer[pos + 1] & 0x3f);
        codes.push(cp);
        pos += 2;
      } else if ((byte & 0xf0) === 0xe0) {
        // 3-byte sequence
        const cp = ((byte & 0x0f) << 12) |
                   ((this.tailBuffer[pos + 1] & 0x3f) << 6) |
                   (this.tailBuffer[pos + 2] & 0x3f);
        codes.push(cp);
        pos += 3;
      } else if ((byte & 0xf8) === 0xf0) {
        // 4-byte sequence
        const cp = ((byte & 0x07) << 18) |
                   ((this.tailBuffer[pos + 1] & 0x3f) << 12) |
                   ((this.tailBuffer[pos + 2] & 0x3f) << 6) |
                   (this.tailBuffer[pos + 3] & 0x3f);
        codes.push(cp);
        pos += 4;
      } else {
        // Invalid UTF-8, skip byte
        pos++;
      }
    }

    return codes;
  }

  /**
   * Find a child node by character code point.
   *
   * @param nodeId Current node
   * @param code Code point to find
   * @returns [childNodeId, labelIndex] or [-1, -1] if not found
   */
  private findChildByCode(nodeId: number, code: number): [number, number] {
    const count = this.childCount(nodeId);
    if (count === 0) return [-1, -1];

    const labelStart = this.firstLabelIndex(nodeId);
    const firstChildId = this.bits.rank1(this.bits.select0(nodeId) + 1);

    // For v6.0 without links, or edges without links, binary search by code point
    if (!this.linkFlags) {
      let lo = 0;
      let hi = count - 1;
      while (lo <= hi) {
        const mid = Math.floor((lo + hi) / 2);
        const midLabel = this.labels[labelStart + mid];
        if (midLabel === code) {
          return [firstChildId + mid, labelStart + mid];
        } else if (midLabel < code) {
          lo = mid + 1;
        } else {
          hi = mid - 1;
        }
      }
      return [-1, -1];
    }

    // With link flags, we need to check each edge
    // Labels are either code points (non-linked) or tail offsets (linked)
    for (let i = 0; i < count; i++) {
      const labelIdx = labelStart + i;

      if (this.linkFlags.get(labelIdx)) {
        // Linked edge - read tail and check first code point
        const tail = this.readTail(this.labels[labelIdx]);
        if (tail.length > 0 && tail[0] === code) {
          return [firstChildId + i, labelIdx];
        }
      } else {
        // Normal edge - direct code point comparison
        if (this.labels[labelIdx] === code) {
          return [firstChildId + i, labelIdx];
        }
      }
    }

    return [-1, -1];
  }

  /**
   * Check if a word exists in the trie.
   *
   * @param word Word to look up
   * @returns true if word exists
   */
  has(word: string): boolean {
    let nodeId = 1;
    const codes = [...word].map(c => c.codePointAt(0)!);
    let i = 0;

    while (i < codes.length) {
      const [childId, labelIdx] = this.findChildByCode(nodeId, codes[i]);
      if (childId === -1) return false;

      // Check if this is a linked edge with a tail
      if (this.linkFlags && this.linkFlags.get(labelIdx)) {
        const tail = this.readTail(this.labels[labelIdx]);

        // Verify the rest of the tail matches
        for (let j = 0; j < tail.length; j++) {
          if (i + j >= codes.length || codes[i + j] !== tail[j]) {
            return false;
          }
        }
        i += tail.length;
      } else {
        i++;
      }

      nodeId = childId;
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
    const codes = [...word].map(c => c.codePointAt(0)!);
    let i = 0;

    while (i < codes.length) {
      const [childId, labelIdx] = this.findChildByCode(nodeId, codes[i]);
      if (childId === -1) return -1;

      if (this.linkFlags && this.linkFlags.get(labelIdx)) {
        const tail = this.readTail(this.labels[labelIdx]);
        for (let j = 0; j < tail.length; j++) {
          if (i + j >= codes.length || codes[i + j] !== tail[j]) {
            return -1;
          }
        }
        i += tail.length;
      } else {
        i++;
      }

      nodeId = childId;
    }

    if (!this.terminal.get(nodeId)) return -1;
    return this.terminal.rank1(nodeId) - 1;
  }

  /**
   * Get all children of a node with their labels.
   */
  getChildren(nodeId: number): Array<[string, number, number]> {
    const count = this.childCount(nodeId);
    if (count === 0) return [];

    const labelStart = this.firstLabelIndex(nodeId);
    const firstChildId = this.bits.rank1(this.bits.select0(nodeId) + 1);

    const result: Array<[string, number, number]> = [];
    for (let i = 0; i < count; i++) {
      const labelIdx = labelStart + i;
      let label: string;

      if (this.linkFlags && this.linkFlags.get(labelIdx)) {
        const tail = this.readTail(this.labels[labelIdx]);
        label = tail.map(c => String.fromCodePoint(c)).join('');
      } else {
        label = String.fromCodePoint(this.labels[labelIdx]);
      }

      result.push([label, firstChildId + i, labelIdx]);
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
    let consumedChars = 0;
    const codes = [...prefix].map(c => c.codePointAt(0)!);

    while (consumedChars < codes.length) {
      const [childId, labelIdx] = this.findChildByCode(nodeId, codes[consumedChars]);
      if (childId === -1) return [];

      if (this.linkFlags && this.linkFlags.get(labelIdx)) {
        const tail = this.readTail(this.labels[labelIdx]);

        // Check partial match within tail
        for (let j = 0; j < tail.length && consumedChars < codes.length; j++) {
          if (codes[consumedChars] !== tail[j]) {
            return []; // Prefix doesn't match
          }
          consumedChars++;
        }

        // If we've consumed all prefix chars but there's more tail,
        // we need to include the remaining tail in results
        if (consumedChars >= codes.length && consumedChars - (codes.length - 1) < tail.length) {
          // Prefix ends mid-tail - still valid, continue from this child
        }
      } else {
        consumedChars++;
      }

      nodeId = childId;
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
   * Find all keys that are prefixes of the given string.
   * (Common prefix search)
   *
   * @param text String to search for prefix matches
   * @returns Array of [word, wordId] pairs in order of increasing length
   */
  commonPrefixes(text: string): Array<[string, number]> {
    const results: Array<[string, number]> = [];
    let nodeId = 1;
    let currentWord = '';
    const codes = [...text].map(c => c.codePointAt(0)!);
    let i = 0;

    while (i < codes.length) {
      const [childId, labelIdx] = this.findChildByCode(nodeId, codes[i]);
      if (childId === -1) break;

      if (this.linkFlags && this.linkFlags.get(labelIdx)) {
        const tail = this.readTail(this.labels[labelIdx]);

        // Check each position in the tail for terminals
        for (let j = 0; j < tail.length; j++) {
          if (i + j >= codes.length || codes[i + j] !== tail[j]) {
            return results; // Mismatch
          }
          currentWord += String.fromCodePoint(tail[j]);
        }
        i += tail.length;
      } else {
        currentWord += String.fromCodePoint(codes[i]);
        i++;
      }

      nodeId = childId;

      if (this.terminal.get(nodeId)) {
        const wordId = this.terminal.rank1(nodeId) - 1;
        results.push([currentWord, wordId]);
      }
    }

    return results;
  }

  /**
   * Serialize the trie to binary format (v6).
   */
  serialize(): Uint8Array {
    const bitsBytes = this.bits.serialize();
    const terminalBytes = this.terminal.serialize();
    const linkFlagsBytes = this.linkFlags ? this.linkFlags.serialize() : new Uint8Array(0);

    // Calculate labels size (varint encoded)
    let labelsSize = 4; // length prefix
    for (let i = 0; i < this.labels.length; i++) {
      labelsSize += varintSize(this.labels[i]);
    }

    const tailBufferSize = this.tailBuffer ? this.tailBuffer.length : 0;

    const totalSize = HEADER_SIZE_V6 +
      4 + bitsBytes.length +
      4 + terminalBytes.length +
      (this.linkFlags ? 4 + linkFlagsBytes.length : 0) +
      labelsSize +
      (tailBufferSize > 0 ? 4 + tailBufferSize : 0);

    const buffer = new Uint8Array(totalSize);
    const view = new DataView(buffer.buffer);
    let offset = 0;

    // Header (24 bytes)
    buffer.set(new TextEncoder().encode(OWTRIE_MAGIC), offset);
    offset += 6;
    view.setUint16(offset, 6, true); // version 6
    offset += 2;
    view.setUint32(offset, this.wordCount, true);
    offset += 4;
    view.setUint32(offset, this.nodeCount, true);
    offset += 4;
    view.setUint32(offset, this.flags, true);
    offset += 4;
    view.setUint32(offset, tailBufferSize, true);
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

    // Link flags bitvector (if present)
    if (this.flags & V6_FLAG_HAS_LINKS) {
      view.setUint32(offset, linkFlagsBytes.length, true);
      offset += 4;
      buffer.set(linkFlagsBytes, offset);
      offset += linkFlagsBytes.length;
    }

    // Labels
    view.setUint32(offset, this.labels.length, true);
    offset += 4;
    for (let i = 0; i < this.labels.length; i++) {
      offset = writeVarint(buffer, offset, this.labels[i]);
    }

    // Tail buffer (if present)
    if (this.flags & V6_FLAG_HAS_TAILS && this.tailBuffer) {
      view.setUint32(offset, tailBufferSize, true);
      offset += 4;
      buffer.set(this.tailBuffer, offset);
      offset += tailBufferSize;
    }

    return buffer.slice(0, offset);
  }

  /**
   * Deserialize a trie from binary format (v6).
   */
  static deserialize(buffer: Uint8Array): MarisaTrie {
    const view = new DataView(buffer.buffer, buffer.byteOffset, buffer.byteLength);
    let offset = 0;

    // Header
    const magic = new TextDecoder().decode(buffer.slice(offset, offset + 6));
    if (magic !== OWTRIE_MAGIC) {
      throw new Error('Invalid trie file: bad magic number');
    }
    offset += 6;

    const version = view.getUint16(offset, true);
    if (version !== 6) {
      throw new Error(`Unsupported trie version: ${version}. Expected v6.`);
    }
    offset += 2;

    const wordCount = view.getUint32(offset, true);
    offset += 4;
    const nodeCount = view.getUint32(offset, true);
    offset += 4;
    const flags = view.getUint32(offset, true);
    offset += 4;
    const tailBufferSize = view.getUint32(offset, true);
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

    // Link flags bitvector (if present)
    let linkFlags: BitVector | null = null;
    if (flags & V6_FLAG_HAS_LINKS) {
      const linkFlagsLength = view.getUint32(offset, true);
      offset += 4;
      linkFlags = BitVector.deserialize(buffer.slice(offset, offset + linkFlagsLength));
      offset += linkFlagsLength;
    }

    // Labels
    const labelsCount = view.getUint32(offset, true);
    offset += 4;
    const labels = new Uint32Array(labelsCount);
    for (let i = 0; i < labelsCount; i++) {
      const { value, bytesRead } = readVarint(buffer, offset);
      labels[i] = value;
      offset += bytesRead;
    }

    // Tail buffer (if present)
    let tailBuffer: Uint8Array | null = null;
    if (flags & V6_FLAG_HAS_TAILS && tailBufferSize > 0) {
      const storedTailSize = view.getUint32(offset, true);
      offset += 4;
      tailBuffer = buffer.slice(offset, offset + storedTailSize);
      offset += storedTailSize;
    }

    return new MarisaTrie(
      bits,
      terminal,
      linkFlags,
      labels,
      tailBuffer,
      null,
      nodeCount,
      wordCount,
      flags
    );
  }

  /**
   * Get statistics about the trie.
   */
  stats(): MarisaStats {
    const bitsBytes = this.bits.serialize();
    const terminalBytes = this.terminal.serialize();
    const linkFlagsBytes = this.linkFlags ? this.linkFlags.serialize() : new Uint8Array(0);

    let labelsSize = 4;
    for (let i = 0; i < this.labels.length; i++) {
      labelsSize += varintSize(this.labels[i]);
    }

    const tailBufferSize = this.tailBuffer ? this.tailBuffer.length : 0;

    const totalSize = HEADER_SIZE_V6 +
      4 + bitsBytes.length +
      4 + terminalBytes.length +
      (this.linkFlags ? 4 + linkFlagsBytes.length : 0) +
      labelsSize +
      (tailBufferSize > 0 ? 4 + tailBufferSize : 0);

    return {
      wordCount: this.wordCount,
      nodeCount: this.nodeCount,
      edgeCount: this.labels.length,
      bitsSize: bitsBytes.length,
      terminalSize: terminalBytes.length,
      linkFlagsSize: linkFlagsBytes.length,
      labelsSize,
      tailBufferSize,
      totalSize,
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
