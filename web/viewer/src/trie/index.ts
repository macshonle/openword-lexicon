/**
 * trie/index.ts - OWTRIE trie building and serialization
 *
 * This module provides tools for building compact binary tries from word lists.
 * All exports work in both Node.js and browser environments.
 *
 * Format versions:
 *   v2: DAWG with 16-bit node IDs (ASCII only, max 65K nodes)
 *   v4: DAWG with varint node IDs (full Unicode, unlimited nodes)
 *   v5: LOUDS trie with bitvectors (full Unicode, word ID mapping)
 *
 * Usage (Node.js):
 *   import { buildDAWG, LOUDSTrie } from './trie/index.js';
 *   const result = buildDAWG(words, 'v4');
 *   fs.writeFileSync('output.trie.bin', result.buffer);
 *
 * Usage (Browser):
 *   import { buildDAWG } from './trie/index.js';
 *   const result = buildDAWG(words, 'auto');
 *   // result.buffer is ready to use
 */

// Varint encoding utilities
export { varintSize, writeVarint, readVarint } from './varint.js';

// Format constants and validation
export {
  OWTRIE_MAGIC,
  HEADER_SIZE,
  HEADER_SIZE_V5,
  V2_MAX_CODE_POINT,
  V2_MAX_NODES,
  UnicodeCompatibilityError,
  validateV2Compatibility,
  checkV2Compatibility,
  detectVersion,
  readHeader,
} from './formats.js';
export type { FormatVersion } from './formats.js';

// DAWG builder and serializer
export {
  DAWGNode,
  DAWGBuilder,
  buildDAWG,
  calculateDAWGStats,
} from './dawg.js';
export type { DAWGBuildResult } from './dawg.js';

// Re-export LOUDS trie from existing module
export { LOUDSTrie } from '../louds-trie.js';

// Re-export BitVector for advanced usage
export { BitVector } from '../bitvector.js';
