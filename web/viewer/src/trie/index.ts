/**
 * trie/index.ts - OWTRIE trie building and serialization
 *
 * This module provides tools for building compact binary tries from word lists.
 * All exports work in both Node.js and browser environments.
 *
 * Format versions:
 *   v7: MARISA trie with recursive tail trie (uncompressed)
 *   v8: MARISA trie with recursive tail trie + brotli compression
 *
 * Usage (Node.js):
 *   import { MarisaTrie, initBrotliNode } from './trie/index.js';
 *   await initBrotliNode();
 *   const { trie } = MarisaTrie.build(words, { enableBrotli: true });
 *   fs.writeFileSync('output.trie.bin', trie.serialize());
 *
 * Usage (Browser):
 *   import { MarisaTrie, initBrotli } from './trie/index.js';
 *   await initBrotli();
 *   const trie = MarisaTrie.deserialize(buffer);
 *   console.log(trie.has('word'));
 */

// Varint encoding utilities
export { varintSize, writeVarint, readVarint } from './varint.js';

// Format constants and validation
export {
  OWTRIE_MAGIC,
  HEADER_SIZE,
  FLAG_RECURSIVE,
  FLAG_BROTLI,
  detectVersion,
  readHeader,
} from './formats.js';
export type { FormatVersion } from './formats.js';

// MARISA trie (v7/v8)
export { MarisaTrie, initBrotli, initBrotliNode, isBrotliReady } from './marisa.js';
export type { MarisaConfig, MarisaStats, MarisaDetailedStats, MarisaMemoryStats, MarisaBuildResult } from './marisa.js';

// Re-export BitVector for advanced usage
export { BitVector } from '../bitvector.js';
