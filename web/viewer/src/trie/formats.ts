/**
 * formats.ts - OWTRIE format constants and validation
 *
 * Defines the binary format specifications for OWTRIE tries.
 * Works in both Node.js and browser environments.
 *
 * Supported versions:
 *   v7: MARISA trie with recursive tail trie (uncompressed)
 *   v8: MARISA trie with recursive tail trie + brotli compression
 */

/** Magic bytes identifying OWTRIE format files */
export const OWTRIE_MAGIC = "OWTRIE";

/** Header size in bytes (magic + version + word count + node count + flags + tail buffer size) */
export const HEADER_SIZE = 24;

/**
 * Supported format versions.
 *
 * v7: MARISA trie with recursive tail trie
 *     - LOUDS + terminal + link bitvectors
 *     - Recursive trie over tail strings
 *     - Full Unicode support
 *     - Word ID mapping and reverse lookup
 *
 * v8: MARISA trie with brotli compression
 *     - Same as v7, but payload is brotli-compressed
 *     - ~33% smaller download size
 *     - Requires brotli-wasm for decompression
 */
export type FormatVersion = "v7" | "v8" | "auto";

/**
 * Format flags (bit positions in header).
 * Note: RECURSIVE is always set in v7/v8 but kept for format identification.
 */
export const FLAG_RECURSIVE = 0x08; // Tails stored in recursive trie
export const FLAG_BROTLI = 0x20; // Entire payload is brotli-compressed

/**
 * Detect the format version from a binary buffer.
 *
 * @param buffer Binary trie data
 * @returns Format version number, or null if invalid
 */
export function detectVersion(buffer: Uint8Array): number | null {
  if (buffer.length < HEADER_SIZE) {
    return null;
  }

  const magic = new TextDecoder().decode(buffer.slice(0, 6));
  if (magic !== OWTRIE_MAGIC) {
    return null;
  }

  const view = new DataView(buffer.buffer, buffer.byteOffset, buffer.byteLength);
  return view.getUint16(6, true);
}

/**
 * Read the header from a binary trie buffer.
 *
 * @param buffer Binary trie data
 * @returns Header information
 */
export function readHeader(buffer: Uint8Array): {
  version: number;
  wordCount: number;
  nodeCount: number;
  flags: number;
  tailBufferSize: number;
} {
  const version = detectVersion(buffer);
  if (version === null) {
    throw new Error("Invalid trie file: bad magic number");
  }

  if (version !== 7 && version !== 8) {
    throw new Error(
      `Unsupported trie version: ${version}. Expected v7 or v8.`
    );
  }

  const view = new DataView(buffer.buffer, buffer.byteOffset, buffer.byteLength);
  const wordCount = view.getUint32(8, true);
  const nodeCount = view.getUint32(12, true);
  const flags = view.getUint32(16, true);
  const tailBufferSize = view.getUint32(20, true);

  return { version, wordCount, nodeCount, flags, tailBufferSize };
}
