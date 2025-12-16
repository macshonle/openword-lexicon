/**
 * dawg.ts - DAWG (Directed Acyclic Word Graph) builder and serializer
 *
 * Builds a minimized DAWG from a word list and serializes to OWTRIE v2/v4 format.
 * Works in both Node.js and browser environments.
 */

import { varintSize, writeVarint } from './varint.js';
import {
  OWTRIE_MAGIC,
  FormatVersion,
  V2_MAX_NODES,
  validateV2Compatibility,
} from './formats.js';

/**
 * DAWG node for building phase.
 */
export class DAWGNode {
  children: Map<string, DAWGNode> = new Map();
  isTerminal: boolean = false;
  id: number = -1;

  /**
   * Get signature for node deduplication.
   * Nodes with identical signatures can be merged.
   */
  getSignature(): string {
    const childSigs = Array.from(this.children.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([char, node]) => `${char}:${node.id}`)
      .join(',');
    return `${this.isTerminal ? '1' : '0'}:${childSigs}`;
  }
}

/**
 * DAWG builder that creates a minimized DAWG from words.
 */
export class DAWGBuilder {
  root: DAWGNode = new DAWGNode();
  private nodeRegistry: Map<string, DAWGNode> = new Map();
  private nextId: number = 0;

  /**
   * Add a word to the DAWG.
   */
  addWord(word: string): void {
    let node = this.root;
    for (const char of word) {
      if (!node.children.has(char)) {
        node.children.set(char, new DAWGNode());
      }
      node = node.children.get(char)!;
    }
    node.isTerminal = true;
  }

  /**
   * Add multiple words to the DAWG.
   */
  addWords(words: Iterable<string>): void {
    for (const word of words) {
      this.addWord(word.trim());
    }
  }

  /**
   * Minimize the DAWG by sharing common suffixes.
   * @returns Array of unique nodes sorted by ID
   */
  minimize(): DAWGNode[] {
    const nodes: DAWGNode[] = [];
    const visited = new Set<DAWGNode>();

    // Assign IDs in post-order (children before parents)
    const assignIds = (node: DAWGNode): void => {
      if (visited.has(node)) return;
      visited.add(node);

      for (const child of node.children.values()) {
        assignIds(child);
      }

      // Check if we've seen this node structure before
      const sig = node.getSignature();
      const existing = this.nodeRegistry.get(sig);

      if (existing) {
        // Reuse existing node
        node.id = existing.id;
      } else {
        // New unique node
        node.id = this.nextId++;
        nodes.push(node);
        this.nodeRegistry.set(sig, node);
      }
    };

    assignIds(this.root);

    // Re-sort nodes by ID for compact storage
    return nodes.sort((a, b) => a.id - b.id);
  }
}

/**
 * Calculate size for v4 format (varint deltas, varint chars).
 */
function calculateV4Size(nodes: DAWGNode[]): number {
  let size = 12; // Header

  for (const node of nodes) {
    size += 2; // flags + child_count

    const sortedChildren = Array.from(node.children.entries())
      .sort(([a], [b]) => a.localeCompare(b));

    for (const [char, childNode] of sortedChildren) {
      const codePoint = char.codePointAt(0)!;
      size += varintSize(codePoint);
      const delta = node.id - childNode.id;
      size += varintSize(delta);
    }
  }

  return size;
}

/**
 * Serialize DAWG to v2 format (16-bit absolute IDs, ASCII only).
 *
 * @throws Error if node count exceeds 65535
 */
function serializeV2(nodes: DAWGNode[], wordCount: number): Uint8Array {
  if (nodes.length > V2_MAX_NODES) {
    throw new Error(`v2 format cannot support ${nodes.length} nodes (max ${V2_MAX_NODES})`);
  }

  let size = 12; // Header
  for (const node of nodes) {
    size += 2 + node.children.size * 3; // flags + count + (char + 2-byte ID) per child
  }

  const buffer = new Uint8Array(size);
  const view = new DataView(buffer.buffer);
  let offset = 0;

  // Header
  buffer.set(new TextEncoder().encode(OWTRIE_MAGIC), offset);
  offset += 6;
  view.setUint16(offset, 2, true);
  offset += 2;
  view.setUint32(offset, wordCount, true);
  offset += 4;

  // Nodes
  for (const node of nodes) {
    const childCount = node.children.size;
    if (childCount > 255) throw new Error(`Node has too many children: ${childCount}`);

    buffer[offset++] = node.isTerminal ? 0x01 : 0x00;
    buffer[offset++] = childCount;

    const sortedChildren = Array.from(node.children.entries())
      .sort(([a], [b]) => a.localeCompare(b));

    for (const [char, childNode] of sortedChildren) {
      // v2 uses single-byte characters (validated earlier)
      buffer[offset++] = char.charCodeAt(0);
      view.setUint16(offset, childNode.id, true);
      offset += 2;
    }
  }

  return buffer;
}

/**
 * Serialize DAWG to v4 format (varint delta IDs, full Unicode).
 */
function serializeV4(nodes: DAWGNode[], wordCount: number): Uint8Array {
  const size = calculateV4Size(nodes);
  const buffer = new Uint8Array(size);
  const view = new DataView(buffer.buffer);
  let offset = 0;

  // Header
  buffer.set(new TextEncoder().encode(OWTRIE_MAGIC), offset);
  offset += 6;
  view.setUint16(offset, 4, true);
  offset += 2;
  view.setUint32(offset, wordCount, true);
  offset += 4;

  // Nodes
  for (const node of nodes) {
    const childCount = node.children.size;
    if (childCount > 255) throw new Error(`Node has too many children: ${childCount}`);

    buffer[offset++] = node.isTerminal ? 0x01 : 0x00;
    buffer[offset++] = childCount;

    const sortedChildren = Array.from(node.children.entries())
      .sort(([a], [b]) => a.localeCompare(b));

    for (const [char, childNode] of sortedChildren) {
      // Full Unicode code point
      const codePoint = char.codePointAt(0)!;
      offset = writeVarint(buffer, offset, codePoint);
      // Delta encoding: parent ID - child ID (always positive in post-order)
      const delta = node.id - childNode.id;
      offset = writeVarint(buffer, offset, delta);
    }
  }

  return buffer;
}

/**
 * Build result with metadata.
 */
export interface DAWGBuildResult {
  buffer: Uint8Array;
  version: number;
  wordCount: number;
  nodeCount: number;
}

/**
 * Build and serialize a DAWG from words.
 *
 * @param words Array of words to include
 * @param format Format version to use ('v2', 'v4', or 'auto')
 * @returns Serialized DAWG with metadata
 * @throws UnicodeCompatibilityError if v2 is requested but words contain non-ASCII
 */
export function buildDAWG(words: string[], format: FormatVersion = 'auto'): DAWGBuildResult {
  // Build and minimize
  const builder = new DAWGBuilder();
  builder.addWords(words);
  const nodes = builder.minimize();
  const nodeCount = nodes.length;

  // Select format
  let selectedFormat = format;
  if (format === 'auto') {
    selectedFormat = nodeCount <= V2_MAX_NODES ? 'v2' : 'v4';
  }

  // Validate format choice
  if (selectedFormat === 'v2') {
    if (nodeCount > V2_MAX_NODES) {
      console.warn(`Warning: v2 format cannot support ${nodeCount} nodes (max ${V2_MAX_NODES}). Switching to v4.`);
      selectedFormat = 'v4';
    } else {
      // Validate Unicode compatibility for v2
      validateV2Compatibility(words);
    }
  }

  // Serialize
  let buffer: Uint8Array;
  let version: number;

  if (selectedFormat === 'v2') {
    buffer = serializeV2(nodes, words.length);
    version = 2;
  } else {
    buffer = serializeV4(nodes, words.length);
    version = 4;
  }

  return { buffer, version, wordCount: words.length, nodeCount };
}

/**
 * Calculate statistics for a node list.
 */
export function calculateDAWGStats(nodes: DAWGNode[]): {
  nodeCount: number;
  edgeCount: number;
  avgChildren: number;
} {
  let edgeCount = 0;
  for (const node of nodes) {
    edgeCount += node.children.size;
  }

  return {
    nodeCount: nodes.length,
    edgeCount,
    avgChildren: nodes.length > 0 ? edgeCount / nodes.length : 0,
  };
}
