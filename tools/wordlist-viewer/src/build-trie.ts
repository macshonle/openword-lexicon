#!/usr/bin/env node
/**
 * build-trie.ts - Build compact binary trie from wordlist
 *
 * Creates a DAWG (Directed Acyclic Word Graph) and serializes it to a
 * compact binary format optimized for browser consumption.
 *
 * Format versions:
 *   v2: 16-bit absolute node IDs (max 65K nodes, 3 bytes/child)
 *   v4: varint delta node IDs (unlimited nodes, ~2 bytes/child avg)
 *
 * The builder auto-selects the best format based on node count,
 * or you can force a specific version with --format=v2|v4
 */

import * as fs from 'fs';
import * as path from 'path';

// DAWG node for building
class DAWGNode {
  children: Map<string, DAWGNode> = new Map();
  isTerminal: boolean = false;
  id: number = -1;

  // For DAWG construction - signature for deduplication
  getSignature(): string {
    const childSigs = Array.from(this.children.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([char, node]) => `${char}:${node.id}`)
      .join(',');
    return `${this.isTerminal ? '1' : '0'}:${childSigs}`;
  }
}

class DAWGBuilder {
  root: DAWGNode = new DAWGNode();
  private nodeRegistry: Map<string, DAWGNode> = new Map();
  private nextId: number = 0;

  // Add a word to the DAWG
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

  // Minimize the DAWG by sharing common suffixes
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

// Varint encoding helpers
function varintSize(value: number): number {
  if (value < 0x80) return 1;
  if (value < 0x4000) return 2;
  if (value < 0x200000) return 3;
  if (value < 0x10000000) return 4;
  return 5;
}

function writeVarint(buffer: Uint8Array, offset: number, value: number): number {
  while (value >= 0x80) {
    buffer[offset++] = (value & 0x7F) | 0x80;
    value >>>= 7;
  }
  buffer[offset++] = value;
  return offset;
}

// Calculate size for v4 format (varint deltas, varint chars)
function calculateV4Size(nodes: DAWGNode[]): number {
  let size = 12; // Header

  for (let i = 0; i < nodes.length; i++) {
    const node = nodes[i];
    size += 2; // flags + child_count

    const sortedChildren = Array.from(node.children.entries())
      .sort(([a], [b]) => a.localeCompare(b));

    for (const [char, childNode] of sortedChildren) {
      // Use codePointAt to get full Unicode code point (handles emoji, extended Latin)
      const codePoint = char.codePointAt(0)!;
      size += varintSize(codePoint);
      // Delta = currentNodeId - childNodeId (always positive in post-order)
      const delta = node.id - childNode.id;
      size += varintSize(delta);
    }
  }

  return size;
}

// Serialize DAWG to v2 format (16-bit absolute IDs)
function serializeV2(nodes: DAWGNode[], wordCount: number): Uint8Array {
  let size = 12; // Header
  for (const node of nodes) {
    size += 2 + node.children.size * 3; // flags + count + (char + 2-byte ID) per child
  }

  const buffer = new Uint8Array(size);
  const view = new DataView(buffer.buffer);
  let offset = 0;

  // Header
  buffer.set(new TextEncoder().encode('OWTRIE'), offset);
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
      buffer[offset++] = char.charCodeAt(0);
      view.setUint16(offset, childNode.id, true);
      offset += 2;
    }
  }

  return buffer;
}

// Serialize DAWG to v4 format (varint delta IDs)
function serializeV4(nodes: DAWGNode[], wordCount: number): Uint8Array {
  const size = calculateV4Size(nodes);
  const buffer = new Uint8Array(size);
  const view = new DataView(buffer.buffer);
  let offset = 0;

  // Header
  buffer.set(new TextEncoder().encode('OWTRIE'), offset);
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
      // Use codePointAt to get full Unicode code point (handles emoji, extended Latin)
      const codePoint = char.codePointAt(0)!;
      offset = writeVarint(buffer, offset, codePoint);
      // Delta encoding: parent ID - child ID (always positive in post-order)
      const delta = node.id - childNode.id;
      offset = writeVarint(buffer, offset, delta);
    }
  }

  return buffer;
}

type FormatVersion = 'v2' | 'v4' | 'auto';

// Select best format and serialize
function serializeDAWG(nodes: DAWGNode[], wordCount: number, format: FormatVersion = 'auto'): { buffer: Uint8Array; version: number } {
  const nodeCount = nodes.length;

  // Auto-select format based on node count
  let selectedFormat = format;
  if (format === 'auto') {
    selectedFormat = nodeCount <= 65535 ? 'v2' : 'v4';
  }

  // Validate format choice
  if (selectedFormat === 'v2' && nodeCount > 65535) {
    console.warn(`Warning: v2 format cannot support ${nodeCount} nodes (max 65535). Switching to v4.`);
    selectedFormat = 'v4';
  }

  if (selectedFormat === 'v2') {
    return { buffer: serializeV2(nodes, wordCount), version: 2 };
  } else {
    return { buffer: serializeV4(nodes, wordCount), version: 4 };
  }
}

// Parse command line arguments
function parseArgs(args: string[]): { inputPath: string; outputPath: string; format: FormatVersion } {
  let inputPath = '../data/build/core/wordlist.txt';
  let outputPath = 'data/core.trie.bin';
  let format: FormatVersion = 'auto';

  for (const arg of args) {
    if (arg.startsWith('--format=')) {
      const fmt = arg.slice(9);
      if (fmt === 'v2' || fmt === 'v4' || fmt === 'auto') {
        format = fmt;
      } else {
        console.error(`Invalid format: ${fmt}. Use v2, v4, or auto.`);
        process.exit(1);
      }
    } else if (!arg.startsWith('--')) {
      if (inputPath === '../data/build/core/wordlist.txt') {
        inputPath = arg;
      } else {
        outputPath = arg;
      }
    }
  }

  return { inputPath, outputPath, format };
}

// Main execution
async function main() {
  const { inputPath, outputPath, format } = parseArgs(process.argv.slice(2));

  console.log('Building compact binary trie...');
  console.log(`Input: ${inputPath}`);
  console.log(`Output: ${outputPath}`);
  console.log(`Format: ${format}`);
  console.log();

  // Read wordlist
  const wordlistText = fs.readFileSync(inputPath, 'utf-8');
  const words = wordlistText.trim().split('\n').filter(w => w.length > 0);

  console.log(`Loaded ${words.length.toLocaleString()} words`);

  // Build DAWG
  console.log('Building DAWG...');
  const builder = new DAWGBuilder();

  for (const word of words) {
    builder.addWord(word.trim());
  }

  // Minimize (deduplicate nodes with same suffixes)
  console.log('Minimizing...');
  const nodes = builder.minimize();

  console.log(`DAWG has ${nodes.length.toLocaleString()} unique nodes`);

  // Serialize to binary
  console.log('Serializing...');
  const { buffer: binary, version } = serializeDAWG(nodes, words.length, format);

  // Ensure output directory exists
  const outputDir = path.dirname(outputPath);
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  // Write output
  fs.writeFileSync(outputPath, binary);

  // Statistics
  const inputSize = Buffer.byteLength(wordlistText, 'utf-8');
  const outputSize = binary.length;
  const ratio = ((outputSize / inputSize) * 100).toFixed(1);
  const bytesPerWord = (outputSize / words.length).toFixed(2);

  console.log();
  console.log('='.repeat(50));
  console.log('Statistics:');
  console.log('='.repeat(50));
  console.log(`Format version:  v${version}`);
  console.log(`Input size:      ${inputSize.toLocaleString()} bytes (${(inputSize / 1024).toFixed(1)} KB)`);
  console.log(`Output size:     ${outputSize.toLocaleString()} bytes (${(outputSize / 1024).toFixed(1)} KB)`);
  console.log(`Compression:     ${ratio}% of original`);
  console.log(`Bytes/word:      ${bytesPerWord}`);
  console.log(`Unique nodes:    ${nodes.length.toLocaleString()}`);
  console.log(`Avg children:    ${(nodes.reduce((sum, n) => sum + n.children.size, 0) / nodes.length).toFixed(2)}`);
  console.log('='.repeat(50));
}

main().catch(console.error);
