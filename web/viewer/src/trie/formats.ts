/**
 * formats.ts - OWTRIE format constants and validation
 *
 * Defines the binary format specifications for OWTRIE tries.
 * Works in both Node.js and browser environments.
 */

/** Magic bytes identifying OWTRIE format files */
export const OWTRIE_MAGIC = 'OWTRIE';

/** Header size in bytes (magic + version + word count) */
export const HEADER_SIZE = 12;

/** Extended header size for v5 (includes node count) */
export const HEADER_SIZE_V5 = 16;

/** Extended header size for v6 MARISA format */
export const HEADER_SIZE_V6 = 24;

/**
 * Supported format versions.
 *
 * v2: DAWG with 16-bit absolute node IDs
 *     - Max 65,535 nodes
 *     - 3 bytes per child (1 char + 2 node ID)
 *     - ASCII only (code points 0-255)
 *
 * v4: DAWG with varint delta node IDs
 *     - Unlimited nodes
 *     - ~2-3 bytes per child average
 *     - Full Unicode support
 *
 * v5: LOUDS trie with bitvectors
 *     - Unlimited nodes
 *     - ~1.5-2 bytes per character
 *     - Full Unicode support
 *     - Word ID mapping via terminal ranking
 *
 * v6: MARISA trie with link flags and tail buffer
 *     - LOUDS + terminal + link bitvectors
 *     - Tail buffer for path compression
 *     - Tail suffix sharing for deduplication
 *     - Optional recursive trie over tails
 *     - Full Unicode support
 */
export type FormatVersion = 'v2' | 'v4' | 'v5' | 'v6' | 'auto';

/**
 * v6 format flags (bit positions in header).
 */
export const V6_FLAG_HAS_LINKS = 0x01;      // Link flags bitvector present
export const V6_FLAG_HAS_TAILS = 0x02;      // Tail buffer present
export const V6_FLAG_BINARY_TAILS = 0x04;   // Length-prefixed tails (vs null-terminated)
export const V6_FLAG_RECURSIVE = 0x08;      // Tails stored in recursive trie

/** Maximum code point supported by v2 format (single byte) */
export const V2_MAX_CODE_POINT = 255;

/** Maximum nodes supported by v2 format (16-bit IDs) */
export const V2_MAX_NODES = 65535;

/**
 * Error thrown when input contains characters incompatible with the requested format.
 */
export class UnicodeCompatibilityError extends Error {
  constructor(
    public readonly format: FormatVersion,
    public readonly invalidChars: string[],
    public readonly sampleWords: string[]
  ) {
    const charList = invalidChars.slice(0, 5).map(c => `'${c}' (U+${c.codePointAt(0)!.toString(16).toUpperCase().padStart(4, '0')})`).join(', ');
    const wordList = sampleWords.slice(0, 3).map(w => `"${w}"`).join(', ');
    super(
      `Format ${format} requires ASCII characters (code points 0-255), but input contains: ${charList}. ` +
      `Found in words: ${wordList}. Use --format=v4 or --format=v5 for full Unicode support.`
    );
    this.name = 'UnicodeCompatibilityError';
  }
}

/**
 * Validate that all words are compatible with the v2 format (ASCII only).
 *
 * @param words Array of words to validate
 * @throws UnicodeCompatibilityError if any word contains non-ASCII characters
 */
export function validateV2Compatibility(words: string[]): void {
  const invalidChars = new Set<string>();
  const sampleWords: string[] = [];

  for (const word of words) {
    for (const char of word) {
      const codePoint = char.codePointAt(0)!;
      if (codePoint > V2_MAX_CODE_POINT) {
        invalidChars.add(char);
        if (sampleWords.length < 10 && !sampleWords.includes(word)) {
          sampleWords.push(word);
        }
      }
    }
  }

  if (invalidChars.size > 0) {
    throw new UnicodeCompatibilityError('v2', Array.from(invalidChars), sampleWords);
  }
}

/**
 * Check if a word list is compatible with v2 format without throwing.
 *
 * @param words Array of words to check
 * @returns Object with compatibility info
 */
export function checkV2Compatibility(words: string[]): {
  compatible: boolean;
  invalidChars: string[];
  sampleWords: string[];
} {
  const invalidChars = new Set<string>();
  const sampleWords: string[] = [];

  for (const word of words) {
    for (const char of word) {
      const codePoint = char.codePointAt(0)!;
      if (codePoint > V2_MAX_CODE_POINT) {
        invalidChars.add(char);
        if (sampleWords.length < 10 && !sampleWords.includes(word)) {
          sampleWords.push(word);
        }
      }
    }
  }

  return {
    compatible: invalidChars.size === 0,
    invalidChars: Array.from(invalidChars),
    sampleWords,
  };
}

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
  nodeCount?: number;
  flags?: number;
  tailBufferSize?: number;
} {
  const version = detectVersion(buffer);
  if (version === null) {
    throw new Error('Invalid trie file: bad magic number');
  }

  const view = new DataView(buffer.buffer, buffer.byteOffset, buffer.byteLength);
  const wordCount = view.getUint32(8, true);

  if (version === 6) {
    const nodeCount = view.getUint32(12, true);
    const flags = view.getUint32(16, true);
    const tailBufferSize = view.getUint32(20, true);
    return { version, wordCount, nodeCount, flags, tailBufferSize };
  }

  if (version === 5) {
    const nodeCount = view.getUint32(12, true);
    return { version, wordCount, nodeCount };
  }

  return { version, wordCount };
}
