#!/usr/bin/env node
/**
 * build-trie.ts - Build compact binary trie from wordlist
 *
 * Creates a DAWG (Directed Acyclic Word Graph) and serializes it to a
 * compact binary format optimized for browser consumption.
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

// Serialize DAWG to binary format
function serializeDAWG(nodes: DAWGNode[], wordCount: number): Uint8Array {
  // Calculate size needed
  let size = 12; // Header: magic(6) + version(2) + wordCount(4)

  for (const node of nodes) {
    size += 2; // flags(1) + child_count(1) - supports up to 255 children
    size += node.children.size * 3; // Each child: char(1) + offset(2)
  }

  const buffer = new Uint8Array(size);
  const view = new DataView(buffer.buffer);
  let offset = 0;

  // Write header
  const magic = new TextEncoder().encode('OWTRIE');
  buffer.set(magic, offset);
  offset += 6;

  view.setUint16(offset, 2, true); // Version 2: extended child count, little-endian
  offset += 2;

  view.setUint32(offset, wordCount, true);
  offset += 4;

  // Write nodes
  for (const node of nodes) {
    const childCount = node.children.size;

    if (childCount > 255) {
      throw new Error(`Node has too many children: ${childCount}`);
    }

    // Version 2 format: separate bytes for flags and child count
    // Byte 1: flags (bit 0: is_terminal)
    // Byte 2: child_count (0-255)
    const flagsByte = node.isTerminal ? 0x01 : 0x00;
    buffer[offset++] = flagsByte;
    buffer[offset++] = childCount;

    // Write children (sorted by character for consistency)
    const sortedChildren = Array.from(node.children.entries())
      .sort(([a], [b]) => a.localeCompare(b));

    for (const [char, childNode] of sortedChildren) {
      // Character code (ASCII/UTF-8)
      buffer[offset++] = char.charCodeAt(0);

      // Child node offset (2 bytes, little-endian)
      view.setUint16(offset, childNode.id, true);
      offset += 2;
    }
  }

  return buffer;
}

// Main execution
async function main() {
  const args = process.argv.slice(2);
  const inputPath = args[0] || '../data/build/core/wordlist.txt';
  const outputPath = args[1] || 'data/core.trie.bin';

  console.log('Building compact binary trie...');
  console.log(`Input: ${inputPath}`);
  console.log(`Output: ${outputPath}`);
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
  const binary = serializeDAWG(nodes, words.length);

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
  console.log(`Input size:      ${inputSize.toLocaleString()} bytes (${(inputSize / 1024).toFixed(1)} KB)`);
  console.log(`Output size:     ${outputSize.toLocaleString()} bytes (${(outputSize / 1024).toFixed(1)} KB)`);
  console.log(`Compression:     ${ratio}% of original`);
  console.log(`Bytes/word:      ${bytesPerWord}`);
  console.log(`Unique nodes:    ${nodes.length.toLocaleString()}`);
  console.log(`Avg children:    ${(nodes.reduce((sum, n) => sum + n.children.size, 0) / nodes.length).toFixed(2)}`);
  console.log('='.repeat(50));
}

main().catch(console.error);
