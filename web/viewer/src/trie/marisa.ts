/**
 * marisa.ts - MARISA trie implementation (OWTRIE v7/v8)
 *
 * A TypeScript implementation of the MARISA trie data structure.
 * This module provides a compact, static trie with:
 * - LOUDS bitvector encoding for tree structure
 * - Terminal bitvector for end-of-word markers
 * - Link flags bitvector for path-compressed edges
 * - Recursive trie over tail strings for compression
 * - Optional brotli compression for best download size (v8)
 *
 * Format versions:
 * - v7: Recursive tail trie (best runtime efficiency, no decompression needed)
 * - v8: Brotli-compressed payload (best compression, works in browser and Node.js)
 *
 * Works in both Node.js and browser environments.
 */

import { BitVector } from '../bitvector.js';
import { varintSize, writeVarint, readVarint } from './varint.js';
import type { BrotliWasmType } from 'brotli-wasm';
import {
  OWTRIE_MAGIC,
  HEADER_SIZE,
  FLAG_RECURSIVE,
  FLAG_BROTLI,
} from './formats.js';

// ============================================================================
// Brotli Provider - handles compression/decompression in Node.js and browser
// ============================================================================

/**
 * Detect if we're running in Node.js (has process.versions.node)
 */
const isNode = typeof process !== 'undefined' && process.versions?.node != null;

/**
 * Cached brotli-wasm module (loaded lazily)
 */
let brotliWasm: BrotliWasmType | null = null;
let brotliWasmPromise: Promise<BrotliWasmType> | null = null;

/**
 * Node.js zlib module (loaded lazily in Node.js only)
 */
let nodeZlib: typeof import('zlib') | null = null;

/**
 * Initialize brotli-wasm module. Must be called before using brotli decompression
 * in browsers. Works in Node.js too (uses WASM instead of native zlib).
 *
 * @returns Promise that resolves when brotli-wasm is ready
 */
export async function initBrotli(): Promise<void> {
  if (brotliWasm) return;
  if (!brotliWasmPromise) {
    brotliWasmPromise = import('brotli-wasm').then(mod => mod.default);
  }
  brotliWasm = await brotliWasmPromise;
}

/**
 * Initialize Node.js native zlib for brotli compression/decompression.
 * This is required before using brotli compression (build-time) in Node.js.
 * For decompression, either this or initBrotli() can be used.
 *
 * @returns Promise that resolves when zlib is ready
 * @throws Error if not running in Node.js
 */
export async function initBrotliNode(): Promise<void> {
  await loadNodeZlib();
}

/**
 * Check if brotli is initialized and ready for use.
 */
export function isBrotliReady(): boolean {
  return brotliWasm !== null || (isNode && nodeZlib !== null);
}

/**
 * Load Node.js zlib module (async, ESM-compatible).
 */
async function loadNodeZlib(): Promise<typeof import('zlib')> {
  if (nodeZlib) return nodeZlib;
  if (!isNode) {
    throw new Error('zlib is only available in Node.js');
  }
  // Dynamic import works in ESM
  nodeZlib = await import('zlib');
  return nodeZlib;
}

/**
 * Compress data with brotli (Node.js only - used for building tries).
 * This is synchronous but requires initBrotliNode() to be called first.
 * @throws Error if called in browser environment or zlib not loaded
 */
function brotliCompress(data: Uint8Array, quality: number): Uint8Array {
  if (!isNode) {
    throw new Error('Brotli compression is only available in Node.js (build-time operation)');
  }

  if (!nodeZlib) {
    throw new Error('Node.js zlib not loaded. Call initBrotliNode() first.');
  }

  const compressed = nodeZlib.brotliCompressSync(data, {
    params: { [nodeZlib.constants.BROTLI_PARAM_QUALITY]: quality }
  });
  return new Uint8Array(compressed);
}

/**
 * Decompress brotli data (works in both Node.js and browser).
 * In browser, initBrotli() must be called first.
 * In Node.js, initBrotliNode() or initBrotli() must be called first.
 * @throws Error if brotli is not initialized
 */
function brotliDecompress(data: Uint8Array): Uint8Array {
  // Try brotli-wasm first (works in both environments)
  if (brotliWasm) {
    return brotliWasm.decompress(data);
  }

  // Fall back to Node.js zlib if available
  if (isNode && nodeZlib) {
    const decompressed = nodeZlib.brotliDecompressSync(data);
    return new Uint8Array(decompressed);
  }

  throw new Error('Brotli not initialized. Call initBrotli() or initBrotliNode() first.');
}

// ============================================================================
// MARISA Trie Configuration and Types
// ============================================================================

/**
 * Configuration for MARISA trie building.
 */
export interface MarisaConfig {
  /** Minimum tail length to compress (default: 2) */
  minTailLength?: number;
  /** Enable brotli compression of payload (v8 format) */
  enableBrotli?: boolean;
  /** Brotli quality level (0-11, default: 11). Lower = faster but larger. */
  brotliQuality?: number;
  /**
   * Maximum recursion depth for tail tries (default: 1).
   * - 0: No tail compression (flat labels only)
   * - 1: Primary trie has recursive tail trie (current default)
   * - 2+: Tail trie also has its own recursive tail trie, and so on
   * Higher values may improve compression for datasets with long keys,
   * but increase build time and slightly slow lookups.
   */
  maxRecursionDepth?: number;
  /** Internal: current recursion depth (0 = primary trie) */
  _recursionDepth?: number;
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
 * Detailed size breakdown for analysis.
 */
export interface MarisaDetailedStats extends MarisaStats {
  headerBytes: number;
  louds: {
    totalBytes: number;
    rawBitsBytes: number;
    directoryBytes: number;
    directoryOverhead: number; // percentage
    lengthPrefixBytes: number;
  };
  terminal: {
    totalBytes: number;
    rawBitsBytes: number;
    directoryBytes: number;
    directoryOverhead: number;
    lengthPrefixBytes: number;
  };
  linkFlags: {
    totalBytes: number;
    rawBitsBytes: number;
    directoryBytes: number;
    directoryOverhead: number;
    lengthPrefixBytes: number;
  } | null;
  labels: {
    totalBytes: number;
    countPrefixBytes: number;
    dataBytes: number;
    avgBitsPerLabel: number;
  };
  tails: {
    totalBytes: number;
    sizePrefixBytes: number;
    dataBytes: number;
    isRecursive: boolean;
  } | null;
  // Summary percentages
  breakdown: {
    header: number;
    louds: number;
    terminal: number;
    linkFlags: number;
    labels: number;
    tails: number;
  };
}

/**
 * Memory usage statistics for a MARISA trie.
 */
export interface MarisaMemoryStats {
  /** Size of the compressed/serialized trie (download size) */
  downloadSize: number;
  /** Size of the decompressed trie data in memory */
  decompressedSize: number;
  /** Estimated total runtime memory including JS object overhead */
  runtimeMemory: number;
  /** Breakdown of runtime memory by component */
  components: {
    bits: number;        // LOUDS bitvector
    terminal: number;    // Terminal bitvector
    linkFlags: number;   // Link flags bitvector
    labels: number;      // Labels array
    tailTrie: number;    // Recursive tail trie
    jsOverhead: number;  // Estimated JS object/class overhead
  };
  /** Bits per word for different metrics */
  bitsPerWord: {
    download: number;
    decompressed: number;
    runtime: number;
  };
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
 * MARISA trie with LOUDS encoding and path compression.
 *
 * The trie stores:
 * - LOUDS bitvector for tree structure
 * - Terminal bitvector marking end-of-word nodes
 * - Link flags bitvector marking edges with tail references
 * - Labels array with Unicode code points (or tail IDs for linked edges)
 * - Recursive trie over tail strings
 *
 * Word IDs are assigned in BFS traversal order of terminal nodes.
 * ID = rank1(terminal, nodeId) - 1 (0-indexed)
 */
export class MarisaTrie {
  /** LOUDS bitvector encoding tree structure */
  readonly bits: BitVector;

  /** Terminal bitvector marking end-of-word nodes */
  readonly terminal: BitVector;

  /** Link flags bitvector marking edges with tail references */
  readonly linkFlags: BitVector;

  /** Labels for each edge (code points or tail IDs for linked edges) */
  readonly labels: Uint32Array;

  /** Recursive trie over tail strings */
  readonly tailTrie: MarisaTrie | null;

  /** Number of nodes (including super-root) */
  readonly nodeCount: number;

  /** Number of words stored */
  readonly wordCount: number;

  /** Format flags */
  readonly flags: number;

  /** Brotli quality level (0-11, default: 11) */
  readonly brotliQuality: number;

  constructor(
    bits: BitVector,
    terminal: BitVector,
    linkFlags: BitVector,
    labels: Uint32Array,
    nodeCount: number,
    wordCount: number,
    flags: number = 0,
    tailTrie: MarisaTrie | null = null,
    brotliQuality: number = 11
  ) {
    this.bits = bits;
    this.terminal = terminal;
    this.linkFlags = linkFlags;
    this.labels = labels;
    this.nodeCount = nodeCount;
    this.wordCount = wordCount;
    this.flags = flags;
    this.tailTrie = tailTrie;
    this.brotliQuality = brotliQuality;
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
    const minTailLength = config.minTailLength ?? 2;
    const enableBrotli = config.enableBrotli ?? false;
    const brotliQuality = config.brotliQuality ?? 11;
    const maxRecursionDepth = config.maxRecursionDepth ?? 1;
    const currentDepth = config._recursionDepth ?? 0;

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

    // Phase 2: Path compression with recursive tail trie (skip if at max depth)
    const tailOffsets = new Map<TrieNode, number>(); // node -> tail ID in recursive trie
    const tailStrings = new Map<TrieNode, string>(); // node -> tail string
    let recursiveTailTrie: MarisaTrie | null = null;

    if (currentDepth < maxRecursionDepth) {
      // First pass: collect all compressible chains
      const pendingTails: Array<{ chain: number[]; endNode: TrieNode; parentNode: TrieNode; firstCode: number }> = [];

      const collectChains = (node: TrieNode): void => {
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
            const [nextCode, nextChild] = current.children.entries().next().value!;
            chain.push(nextCode);
            current = nextChild;
          }

          if (chain.length >= minTailLength) {
            pendingTails.push({ chain, endNode: current, parentNode: node, firstCode: code });
            // CRITICAL: Recurse from end of chain, not from child
            // This skips intermediate nodes that are part of this chain
            collectChains(current);
          } else {
            // Chain too short - recurse from original child
            collectChains(child);
          }
        }
      };

      collectChains(root);

      // Sort tails lexicographically so tail trie word IDs are predictable
      pendingTails.sort((a, b) => {
        const aStr = a.chain.map(c => String.fromCodePoint(c)).join('');
        const bStr = b.chain.map(c => String.fromCodePoint(c)).join('');
        return aStr.localeCompare(bStr);
      });

      // Collect unique tail strings, build recursive trie
      const uniqueTails = new Set<string>();
      for (const { chain, endNode, parentNode, firstCode } of pendingTails) {
        const tailString = chain.map(c => String.fromCodePoint(c)).join('');
        uniqueTails.add(tailString);
        tailStrings.set(endNode, tailString);
        // Update trie structure
        parentNode.children.set(firstCode, endNode);
      }

      // Build recursive trie over unique tails (pass depth to allow further recursion)
      if (uniqueTails.size > 0) {
        const sortedTails = Array.from(uniqueTails).sort();
        const { trie: innerTrie } = MarisaTrie.build(sortedTails, {
          enableBrotli: false,
          maxRecursionDepth,
          _recursionDepth: currentDepth + 1,
        });
        recursiveTailTrie = innerTrie;

        // Assign tail IDs based on word IDs in the recursive trie
        for (const { endNode } of pendingTails) {
          const tailString = tailStrings.get(endNode)!;
          const tailId = recursiveTailTrie.wordId(tailString);
          if (tailId === -1) {
            throw new Error(`Internal error: tail "${tailString}" not found in recursive trie`);
          }
          tailOffsets.set(endNode, tailId);
        }
      }
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
    const linkFlags = new BitVector(edgeCount);
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

        if (tailOffsets.has(child)) {
          // This edge has a tail - store tail ID in labels
          linkFlags.set(labelPos);
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
    linkFlags.build();

    // Compute flags: always recursive, optionally brotli
    let flags = FLAG_RECURSIVE;
    if (enableBrotli) {
      flags |= FLAG_BROTLI;
    }

    // Word count is the actual number of unique words (terminal nodes),
    // not input words.length which may contain duplicates
    const actualWordCount = terminal.popcount;

    const trie = new MarisaTrie(
      bits,
      terminal,
      linkFlags,
      labels,
      nodeCount + 1,
      actualWordCount,
      flags,
      recursiveTailTrie,
      brotliQuality
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
   * Read a tail from the recursive tail trie by word ID.
   *
   * @param tailId Word ID in the recursive tail trie
   * @returns Array of code points
   */
  private readTail(tailId: number): number[] {
    if (!this.tailTrie) return [];
    const tailString = this.tailTrie.getWord(tailId);
    if (!tailString) return [];
    return [...tailString].map(c => c.codePointAt(0)!);
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

    // Check each edge - labels are either code points (non-linked) or tail IDs (linked)
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
    let remainingTail = ''; // Characters from tail after prefix ends

    while (consumedChars < codes.length) {
      const [childId, labelIdx] = this.findChildByCode(nodeId, codes[consumedChars]);
      if (childId === -1) return [];

      if (this.linkFlags && this.linkFlags.get(labelIdx)) {
        const tail = this.readTail(this.labels[labelIdx]);

        // Check partial match within tail
        let j = 0;
        for (; j < tail.length && consumedChars < codes.length; j++) {
          if (codes[consumedChars] !== tail[j]) {
            return []; // Prefix doesn't match
          }
          consumedChars++;
        }

        // If we've consumed all prefix chars but there's more tail,
        // remember the remaining tail characters
        if (consumedChars >= codes.length && j < tail.length) {
          remainingTail = tail.slice(j).map(c => String.fromCodePoint(c)).join('');
        }
      } else {
        consumedChars++;
      }

      nodeId = childId;
    }

    // DFS to collect words
    // Start with prefix + any remaining tail characters from the last edge
    const results: string[] = [];
    const startWord = prefix + remainingTail;
    const stack: Array<[number, string]> = [[nodeId, startWord]];

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
   * Get the parent node of a given node in the LOUDS tree.
   * @param nodeId Node to find parent of (must be > 1)
   * @returns Parent node ID
   */
  private getParent(nodeId: number): number {
    if (nodeId <= 1) return 0;
    const bitPos = this.bits.select1(nodeId);
    return this.bits.rank0(bitPos);
  }

  /**
   * Get the word at a given ID (reverse lookup from terminal rank).
   * This allows retrieving words by their BFS terminal order ID.
   *
   * @param id Word ID (0-indexed)
   * @returns The word at that ID, or null if ID is out of range
   */
  getWord(id: number): string | null {
    if (id < 0 || id >= this.wordCount) return null;

    // Find the terminal node with this ID
    const nodeId = this.terminal.select1(id + 1);
    if (nodeId === -1) return null;

    // Walk from node to root, collecting labels
    const codes: number[] = [];
    let current = nodeId;

    while (current > 1) {
      // Label index for edge leading to current node
      const labelIdx = current - 2; // Nodes 2+ have labels 0, 1, 2, ...

      if (this.linkFlags && this.linkFlags.get(labelIdx)) {
        // This edge has a tail - prepend all tail codes
        const tail = this.readTail(this.labels[labelIdx]);
        codes.unshift(...tail);
      } else {
        codes.unshift(this.labels[labelIdx]);
      }

      current = this.getParent(current);
    }

    return codes.map(c => String.fromCodePoint(c)).join('');
  }

  /**
   * Serialize the trie to binary format (v7 or v8).
   */
  serialize(): Uint8Array {
    const bitsBytes = this.bits.serialize();
    const terminalBytes = this.terminal.serialize();
    const linkFlagsBytes = this.linkFlags.serialize();

    // Calculate labels size (varint encoded)
    let labelsSize = 4; // length prefix
    for (let i = 0; i < this.labels.length; i++) {
      labelsSize += varintSize(this.labels[i]);
    }

    // Serialize recursive tail trie
    const tailBytes = this.tailTrie ? this.tailTrie.serialize() : null;
    const tailStorageSize = tailBytes ? tailBytes.length : 0;

    const totalSize = HEADER_SIZE +
      4 + bitsBytes.length +
      4 + terminalBytes.length +
      4 + linkFlagsBytes.length +
      labelsSize +
      (tailStorageSize > 0 ? 4 + tailStorageSize : 0);

    const buffer = new Uint8Array(totalSize);
    const view = new DataView(buffer.buffer);
    let offset = 0;

    // Header (24 bytes)
    // Version: 7 = uncompressed, 8 = brotli compressed
    const version = (this.flags & FLAG_BROTLI) ? 8 : 7;
    buffer.set(new TextEncoder().encode(OWTRIE_MAGIC), offset);
    offset += 6;
    view.setUint16(offset, version, true);
    offset += 2;
    view.setUint32(offset, this.wordCount, true);
    offset += 4;
    view.setUint32(offset, this.nodeCount, true);
    offset += 4;
    view.setUint32(offset, this.flags, true);
    offset += 4;
    view.setUint32(offset, tailStorageSize, true);
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

    // Link flags bitvector
    view.setUint32(offset, linkFlagsBytes.length, true);
    offset += 4;
    buffer.set(linkFlagsBytes, offset);
    offset += linkFlagsBytes.length;

    // Labels (varint encoded)
    view.setUint32(offset, this.labels.length, true);
    offset += 4;
    for (let i = 0; i < this.labels.length; i++) {
      offset = writeVarint(buffer, offset, this.labels[i]);
    }

    // Tail trie
    if (tailBytes && tailStorageSize > 0) {
      view.setUint32(offset, tailStorageSize, true);
      offset += 4;
      buffer.set(tailBytes, offset);
      offset += tailStorageSize;
    }

    const uncompressed = buffer.slice(0, offset);

    // Apply brotli compression if enabled (v8)
    if (this.flags & FLAG_BROTLI) {
      return this.compressWithBrotli(uncompressed);
    }

    return uncompressed;
  }

  /**
   * Compress the serialized buffer with brotli (Node.js only - build time).
   * Header is preserved uncompressed, payload is compressed.
   */
  private compressWithBrotli(uncompressed: Uint8Array): Uint8Array {
    const header = uncompressed.slice(0, HEADER_SIZE);
    const payload = uncompressed.slice(HEADER_SIZE);

    const compressed = brotliCompress(payload, this.brotliQuality);

    // Result: header + 4-byte compressed length + compressed payload
    const result = new Uint8Array(HEADER_SIZE + 4 + compressed.length);
    result.set(header, 0);
    const view = new DataView(result.buffer);
    view.setUint32(HEADER_SIZE, compressed.length, true);
    result.set(compressed, HEADER_SIZE + 4);

    return result;
  }

  /**
   * Decompress brotli-compressed payload (works in Node.js and browser).
   * In browser, initBrotli() must have been called first.
   */
  private static decompressBrotli(buffer: Uint8Array): Uint8Array {
    const header = buffer.slice(0, HEADER_SIZE);
    const view = new DataView(buffer.buffer, buffer.byteOffset, buffer.byteLength);
    const compressedLength = view.getUint32(HEADER_SIZE, true);
    const compressedPayload = buffer.slice(HEADER_SIZE + 4, HEADER_SIZE + 4 + compressedLength);

    const decompressed = brotliDecompress(compressedPayload);

    // Reconstruct: header + decompressed payload
    const result = new Uint8Array(HEADER_SIZE + decompressed.length);
    result.set(header, 0);
    result.set(decompressed, HEADER_SIZE);

    return result;
  }

  /**
   * Deserialize a trie from binary format (v7 or v8).
   */
  static deserialize(buffer: Uint8Array): MarisaTrie {
    // First, check version to see if brotli decompression is needed
    const peekView = new DataView(buffer.buffer, buffer.byteOffset, buffer.byteLength);
    const peekVersion = peekView.getUint16(6, true); // version at offset 6

    // Decompress if v8 (brotli compressed)
    if (peekVersion === 8) {
      buffer = this.decompressBrotli(buffer);
    }

    const view = new DataView(buffer.buffer, buffer.byteOffset, buffer.byteLength);
    let offset = 0;

    // Header
    const magic = new TextDecoder().decode(buffer.slice(offset, offset + 6));
    if (magic !== OWTRIE_MAGIC) {
      throw new Error("Invalid trie file: bad magic number");
    }
    offset += 6;

    const version = view.getUint16(offset, true);
    if (version !== 7 && version !== 8) {
      throw new Error(`Unsupported trie version: ${version}. Expected v7 or v8.`);
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

    // Link flags bitvector
    const linkFlagsLength = view.getUint32(offset, true);
    offset += 4;
    const linkFlags = BitVector.deserialize(buffer.slice(offset, offset + linkFlagsLength));
    offset += linkFlagsLength;

    // Labels (varint encoded)
    const labelsCount = view.getUint32(offset, true);
    offset += 4;
    const labels = new Uint32Array(labelsCount);
    for (let i = 0; i < labelsCount; i++) {
      const { value, bytesRead } = readVarint(buffer, offset);
      labels[i] = value;
      offset += bytesRead;
    }

    // Recursive tail trie
    let tailTrie: MarisaTrie | null = null;
    if (tailBufferSize > 0) {
      const storedTailSize = view.getUint32(offset, true);
      offset += 4;
      const tailTrieBytes = buffer.slice(offset, offset + storedTailSize);
      tailTrie = MarisaTrie.deserialize(tailTrieBytes);
      offset += storedTailSize;
    }

    return new MarisaTrie(
      bits,
      terminal,
      linkFlags,
      labels,
      nodeCount,
      wordCount,
      flags,
      tailTrie
    );
  }

  /**
   * Get statistics about the trie.
   */
  stats(): MarisaStats {
    const bitsBytes = this.bits.serialize();
    const terminalBytes = this.terminal.serialize();
    const linkFlagsBytes = this.linkFlags.serialize();

    let labelsSize = 4;
    for (let i = 0; i < this.labels.length; i++) {
      labelsSize += varintSize(this.labels[i]);
    }

    // Tail storage size: serialized recursive trie
    const tailBufferSize = this.tailTrie ? this.tailTrie.serialize().length : 0;

    const totalSize = HEADER_SIZE +
      4 + bitsBytes.length +
      4 + terminalBytes.length +
      4 + linkFlagsBytes.length +
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

  /**
   * Get detailed size breakdown for analysis.
   */
  detailedStats(): MarisaDetailedStats {
    const baseStats = this.stats();

    // Bitvector breakdowns
    const loudsBreakdown = this.bits.sizeBreakdown();
    const terminalBreakdown = this.terminal.sizeBreakdown();
    const linkFlagsBreakdown = this.linkFlags.sizeBreakdown();

    // Calculate labels data size (varint encoded, without count prefix)
    let labelsDataSize = 0;
    for (let i = 0; i < this.labels.length; i++) {
      labelsDataSize += varintSize(this.labels[i]);
    }
    const avgBitsPerLabel = this.labels.length > 0
      ? (labelsDataSize * 8) / this.labels.length
      : 0;

    // Tail storage (always recursive in v7/v8)
    let tailDataSize = 0;
    const isRecursive = !!(this.flags & FLAG_RECURSIVE);
    if (this.tailTrie) {
      tailDataSize = this.tailTrie.serialize().length;
    }

    // Calculate component totals (including length prefixes)
    const headerBytes = HEADER_SIZE;
    const loudsTotalBytes = 4 + loudsBreakdown.totalBytes;
    const terminalTotalBytes = 4 + terminalBreakdown.totalBytes;
    const linkFlagsTotalBytes = linkFlagsBreakdown ? 4 + linkFlagsBreakdown.totalBytes : 0;
    const labelsTotalBytes = 4 + labelsDataSize;
    const tailsTotalBytes = tailDataSize > 0 ? 4 + tailDataSize : 0;

    const totalSize = headerBytes + loudsTotalBytes + terminalTotalBytes +
      linkFlagsTotalBytes + labelsTotalBytes + tailsTotalBytes;

    // Calculate percentages
    const pct = (n: number) => totalSize > 0 ? (n / totalSize) * 100 : 0;

    return {
      ...baseStats,
      totalSize,
      headerBytes,
      louds: {
        totalBytes: loudsTotalBytes,
        rawBitsBytes: loudsBreakdown.rawBitsBytes,
        directoryBytes: loudsBreakdown.superblockBytes + loudsBreakdown.blockBytes,
        directoryOverhead: loudsBreakdown.directoryOverhead,
        lengthPrefixBytes: 4,
      },
      terminal: {
        totalBytes: terminalTotalBytes,
        rawBitsBytes: terminalBreakdown.rawBitsBytes,
        directoryBytes: terminalBreakdown.superblockBytes + terminalBreakdown.blockBytes,
        directoryOverhead: terminalBreakdown.directoryOverhead,
        lengthPrefixBytes: 4,
      },
      linkFlags: linkFlagsBreakdown ? {
        totalBytes: linkFlagsTotalBytes,
        rawBitsBytes: linkFlagsBreakdown.rawBitsBytes,
        directoryBytes: linkFlagsBreakdown.superblockBytes + linkFlagsBreakdown.blockBytes,
        directoryOverhead: linkFlagsBreakdown.directoryOverhead,
        lengthPrefixBytes: 4,
      } : null,
      labels: {
        totalBytes: labelsTotalBytes,
        countPrefixBytes: 4,
        dataBytes: labelsDataSize,
        avgBitsPerLabel,
      },
      tails: tailDataSize > 0 ? {
        totalBytes: tailsTotalBytes,
        sizePrefixBytes: 4,
        dataBytes: tailDataSize,
        isRecursive,
      } : null,
      breakdown: {
        header: pct(headerBytes),
        louds: pct(loudsTotalBytes),
        terminal: pct(terminalTotalBytes),
        linkFlags: pct(linkFlagsTotalBytes),
        labels: pct(labelsTotalBytes),
        tails: pct(tailsTotalBytes),
      },
    };
  }

  /**
   * Get memory usage statistics including download, decompressed, and runtime sizes.
   * @param serializedSize Optional pre-computed serialized size (avoids re-serialization)
   */
  memoryStats(serializedSize?: number): MarisaMemoryStats {
    // Calculate serialized (download) size
    const downloadSize = serializedSize ?? this.serialize().length;

    // Calculate decompressed size (size without brotli compression)
    const detailed = this.detailedStats();
    const decompressedSize = detailed.totalSize;

    // Calculate runtime memory for each component
    // TypedArray memory = length * bytes_per_element + ~64 bytes overhead per array

    // BitVector stores: bits (Uint32Array) + directory arrays
    const bitsMemory = this.estimateBitVectorMemory(this.bits);
    const terminalMemory = this.estimateBitVectorMemory(this.terminal);
    const linkFlagsMemory = this.linkFlags ? this.estimateBitVectorMemory(this.linkFlags) : 0;

    // Labels array: Uint32Array
    const labelsMemory = this.labels.length * 4 + 64;

    // Recursive tail trie: recurse
    const tailTrieMemory = this.tailTrie ? this.tailTrie.memoryStats().runtimeMemory : 0;

    // JS object overhead: class instance, properties, Map/Set structures
    // Estimate ~500 bytes for the class instance and its scalar properties
    const jsOverhead = 500;

    const runtimeMemory = bitsMemory + terminalMemory + linkFlagsMemory +
      labelsMemory + tailTrieMemory + jsOverhead;

    const wordCount = this.wordCount;

    return {
      downloadSize,
      decompressedSize,
      runtimeMemory,
      components: {
        bits: bitsMemory,
        terminal: terminalMemory,
        linkFlags: linkFlagsMemory,
        labels: labelsMemory,
        tailTrie: tailTrieMemory,
        jsOverhead,
      },
      bitsPerWord: {
        download: wordCount > 0 ? (downloadSize * 8) / wordCount : 0,
        decompressed: wordCount > 0 ? (decompressedSize * 8) / wordCount : 0,
        runtime: wordCount > 0 ? (runtimeMemory * 8) / wordCount : 0,
      },
    };
  }

  /**
   * Estimate memory usage of a BitVector including its directory structures.
   */
  private estimateBitVectorMemory(bv: BitVector): number {
    const breakdown = bv.sizeBreakdown();
    // Uint32Array for bits, plus directory arrays, plus object overhead
    return breakdown.totalBytes + 64 * 3; // 3 arrays typically
  }
}
