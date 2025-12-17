/**
 * huffman.ts - Huffman encoding for trie labels
 *
 * Provides frequency-based bit encoding for Unicode code points.
 * Uses canonical Huffman codes for compact table representation.
 *
 * The key insight is that trie labels have non-uniform frequency distribution:
 * - Common letters (e, t, a, o, i, n, s, r) are very frequent
 * - Rare Unicode characters appear infrequently
 *
 * Canonical Huffman encoding assigns shorter bit codes to frequent symbols,
 * and the code table itself can be represented compactly by just storing
 * the number of symbols at each code length.
 */

/**
 * Node in the Huffman tree during construction.
 */
interface HuffmanNode {
  symbol?: number;  // Code point (leaf nodes only)
  freq: number;
  left?: HuffmanNode;
  right?: HuffmanNode;
}

/**
 * Entry in the canonical Huffman code table.
 */
interface CodeEntry {
  symbol: number;
  bitLength: number;
  code: number;
}

/**
 * Huffman encoder/decoder for Unicode code points.
 */
export class HuffmanCodec {
  /** Map from symbol to {code, bitLength} */
  private encodeTable: Map<number, { code: number; bitLength: number }>;

  /** Decoding tree: nested arrays representing binary tree */
  private decodeTree: unknown;

  /** Symbols sorted by code length, then by symbol value (for canonical encoding) */
  private canonicalSymbols: number[];

  /** Number of symbols at each bit length (index 0 unused, lengths 1..maxLength) */
  private lengthCounts: number[];

  /** Maximum bit length in the code */
  private maxBitLength: number;

  private constructor() {
    this.encodeTable = new Map();
    this.decodeTree = null;
    this.canonicalSymbols = [];
    this.lengthCounts = [];
    this.maxBitLength = 0;
  }

  /**
   * Build a Huffman codec from symbol frequencies.
   * @param frequencies Map from symbol (code point) to count
   */
  static build(frequencies: Map<number, number>): HuffmanCodec {
    const codec = new HuffmanCodec();

    if (frequencies.size === 0) {
      return codec;
    }

    // Handle single-symbol case
    if (frequencies.size === 1) {
      const symbol = frequencies.keys().next().value!;
      codec.encodeTable.set(symbol, { code: 0, bitLength: 1 });
      codec.decodeTree = [symbol, symbol];
      codec.canonicalSymbols = [symbol];
      codec.lengthCounts = [0, 1];
      codec.maxBitLength = 1;
      return codec;
    }

    // Build Huffman tree using a priority queue (min-heap)
    const nodes: HuffmanNode[] = [];
    for (const [symbol, freq] of frequencies) {
      nodes.push({ symbol, freq });
    }

    // Sort by frequency ascending (simple heap simulation)
    nodes.sort((a, b) => a.freq - b.freq);

    while (nodes.length > 1) {
      // Take two nodes with smallest frequencies
      const left = nodes.shift()!;
      const right = nodes.shift()!;

      // Create parent node
      const parent: HuffmanNode = {
        freq: left.freq + right.freq,
        left,
        right,
      };

      // Insert parent in sorted order
      let inserted = false;
      for (let i = 0; i < nodes.length; i++) {
        if (parent.freq <= nodes[i].freq) {
          nodes.splice(i, 0, parent);
          inserted = true;
          break;
        }
      }
      if (!inserted) {
        nodes.push(parent);
      }
    }

    const root = nodes[0];

    // Assign bit lengths by traversing tree
    const bitLengths: Map<number, number> = new Map();
    const assignLengths = (node: HuffmanNode, depth: number) => {
      if (node.symbol !== undefined) {
        bitLengths.set(node.symbol, depth);
      } else {
        if (node.left) assignLengths(node.left, depth + 1);
        if (node.right) assignLengths(node.right, depth + 1);
      }
    };
    assignLengths(root, 0);

    // For most practical cases (< 1000 unique symbols), the Huffman tree depth
    // is bounded and we don't need to limit code lengths. The theoretical max
    // for n symbols is n-1 bits, but with typical frequency distributions,
    // it's much less (around log2(n) for balanced, maybe 2x that for skewed).
    //
    // We skip code length limiting for simplicity - it was causing bugs.
    // If we ever need it, implement proper package-merge algorithm.

    // Build canonical Huffman codes
    codec.buildCanonicalCodes(bitLengths);

    return codec;
  }

  /**
   * Limit code lengths to a maximum value while maintaining Kraft inequality.
   * Uses a simple but correct algorithm: calculate valid length distribution.
   */
  private limitCodeLengths(bitLengths: Map<number, number>, maxLength: number): void {
    // Count symbols at each length
    const lengthCounts: number[] = new Array(32).fill(0);
    let maxActualLength = 0;
    for (const [, length] of bitLengths) {
      lengthCounts[length]++;
      maxActualLength = Math.max(maxActualLength, length);
    }

    if (maxActualLength <= maxLength) {
      return; // No limiting needed
    }

    // Use a simpler approach: redistribute symbols to fit within maxLength
    // while satisfying Kraft inequality: sum of 2^(-len) <= 1

    const numSymbols = bitLengths.size;

    // Calculate optimal lengths for numSymbols symbols with maxLength limit
    // Use "package-merge" style distribution
    const newLengthCounts: number[] = new Array(maxLength + 1).fill(0);

    // For n symbols with max length L, distribute as evenly as possible
    // Start by filling from the shortest feasible length
    let remaining = numSymbols;
    let kraft = 0;

    // Fill levels from shortest to maxLength
    for (let len = 1; len <= maxLength && remaining > 0; len++) {
      // How many symbols can fit at this length given remaining Kraft budget?
      const availableKraft = 1.0 - kraft;
      const maxAtLevel = Math.floor(availableKraft * (1 << len));
      const actualAtLevel = Math.min(maxAtLevel, remaining);

      if (len === maxLength) {
        // Put all remaining at maxLength
        newLengthCounts[len] = remaining;
        remaining = 0;
      } else if (actualAtLevel > 0 && len >= Math.ceil(Math.log2(numSymbols))) {
        // Only start assigning once we have enough levels to fit everything
        // Prefer longer codes for better compression (more frequent = shorter)
        // Skip short levels, let everything go to longer levels
      }
    }

    // Simple fallback: just use maxLength for everything if the fancy algorithm fails
    // This is suboptimal but correct
    if (remaining > 0 || newLengthCounts.reduce((a, b) => a + b, 0) !== numSymbols) {
      // Use a simple valid distribution
      // For n symbols with max length L, we need to find a valid distribution
      // The simplest valid one: put everything at maxLength if it fits
      if (numSymbols <= (1 << maxLength)) {
        newLengthCounts.fill(0);
        newLengthCounts[maxLength] = numSymbols;
      } else {
        // Need to distribute across multiple lengths
        // Work backwards from maxLength
        let toAssign = numSymbols;
        for (let len = maxLength; len >= 1 && toAssign > 0; len--) {
          const maxAtLevel = 1 << len;
          const atLevel = Math.min(maxAtLevel, toAssign);
          newLengthCounts[len] = atLevel;
          toAssign -= atLevel;
        }
      }
    }

    // Sort symbols by frequency (ascending) to assign shorter codes to more frequent
    const sortedByFreq = [...bitLengths.entries()].sort((a, b) => a[1] - b[1]);

    // Assign new lengths: shortest codes to highest-frequency symbols
    // Since we sorted by original length (which correlates with frequency in Huffman),
    // we can just assign in reverse order
    let idx = 0;
    for (let len = 1; len <= maxLength; len++) {
      for (let i = 0; i < newLengthCounts[len]; i++) {
        if (idx < sortedByFreq.length) {
          bitLengths.set(sortedByFreq[idx][0], len);
          idx++;
        }
      }
    }

    // Verify Kraft inequality
    let kraftSum = 0;
    for (const [, len] of bitLengths) {
      kraftSum += 1 / (1 << len);
    }
    if (kraftSum > 1.001) {
      // Fallback: uniform distribution at maxLength
      for (const [symbol] of bitLengths) {
        bitLengths.set(symbol, maxLength);
      }
    }
  }

  /**
   * Build canonical Huffman codes from bit lengths.
   * Canonical codes are determined solely by bit lengths and symbol order.
   */
  private buildCanonicalCodes(bitLengths: Map<number, number>): void {
    // Find max bit length
    this.maxBitLength = 0;
    for (const [, length] of bitLengths) {
      this.maxBitLength = Math.max(this.maxBitLength, length);
    }

    // Count symbols at each length
    this.lengthCounts = new Array(this.maxBitLength + 1).fill(0);
    for (const [, length] of bitLengths) {
      this.lengthCounts[length]++;
    }

    // Sort symbols by (length, symbol value)
    const entries: Array<{ symbol: number; bitLength: number }> = [];
    for (const [symbol, bitLength] of bitLengths) {
      entries.push({ symbol, bitLength });
    }
    entries.sort((a, b) => {
      if (a.bitLength !== b.bitLength) return a.bitLength - b.bitLength;
      return a.symbol - b.symbol;
    });

    this.canonicalSymbols = entries.map(e => e.symbol);

    // Assign canonical codes using the standard algorithm:
    // - Start with code 0 at the first bit length
    // - For each subsequent symbol at the same length, increment by 1
    // - When moving to a longer length, shift left first, then increment if needed
    let code = 0;
    let prevLength = entries.length > 0 ? entries[0].bitLength : 0;

    for (const { symbol, bitLength } of entries) {
      if (bitLength > prevLength) {
        // Moving to longer codes: shift left by the difference
        code <<= (bitLength - prevLength);
        prevLength = bitLength;
      }

      this.encodeTable.set(symbol, { code, bitLength });
      code++; // Increment for next symbol at this (or any) length
    }

    // Build decode tree
    this.buildDecodeTree();
  }

  /**
   * Build decode tree for efficient bit-by-bit decoding.
   * Tree is represented as nested arrays: [leftChild, rightChild]
   * Leaf nodes are the symbol values (numbers).
   */
  private buildDecodeTree(): void {
    const root: unknown[] = [];

    for (const [symbol, { code, bitLength }] of this.encodeTable) {
      let node = root;

      // Navigate/create path through tree
      for (let i = bitLength - 1; i > 0; i--) {
        const bit = (code >> i) & 1;
        if (node[bit] === undefined) {
          node[bit] = [];
        } else if (!Array.isArray(node[bit])) {
          // This shouldn't happen with valid Huffman codes (prefix-free property)
          throw new Error(`Invalid Huffman tree: node at bit ${i} is already a leaf`);
        }
        node = node[bit] as unknown[];
      }

      // Set leaf
      const lastBit = code & 1;
      if (node[lastBit] !== undefined) {
        throw new Error(`Duplicate Huffman code for symbol ${symbol}`);
      }
      node[lastBit] = symbol;
    }

    this.decodeTree = root;
  }

  /**
   * Encode a single symbol, writing bits to output.
   */
  encode(symbol: number, writer: BitWriter): void {
    const entry = this.encodeTable.get(symbol);
    if (!entry) {
      throw new Error(`Symbol not in Huffman table: ${symbol}`);
    }
    writer.writeBits(entry.code, entry.bitLength);
  }

  /**
   * Decode a single symbol by reading bits from input.
   */
  decode(reader: BitReader): number {
    let node = this.decodeTree as unknown[];

    while (Array.isArray(node)) {
      const bit = reader.readBit();
      node = node[bit] as unknown[];
    }

    return node as unknown as number;
  }

  /**
   * Get the bit length for a symbol.
   */
  getBitLength(symbol: number): number {
    const entry = this.encodeTable.get(symbol);
    return entry?.bitLength ?? 0;
  }

  /**
   * Calculate total bits needed to encode a sequence of symbols.
   */
  calculateEncodedBits(symbols: number[]): number {
    let total = 0;
    for (const symbol of symbols) {
      total += this.getBitLength(symbol);
    }
    return total;
  }

  /**
   * Serialize the Huffman table.
   * Format:
   *   - uint8: maxBitLength
   *   - uint8[maxBitLength]: lengthCounts[1..maxBitLength]
   *   - varint[]: symbols in canonical order
   */
  serialize(): Uint8Array {
    const parts: Uint8Array[] = [];

    // Max bit length (1 byte)
    parts.push(new Uint8Array([this.maxBitLength]));

    // Length counts (maxBitLength bytes)
    if (this.maxBitLength > 0) {
      const counts = new Uint8Array(this.maxBitLength);
      for (let i = 1; i <= this.maxBitLength; i++) {
        counts[i - 1] = this.lengthCounts[i];
      }
      parts.push(counts);
    }

    // Symbols in canonical order (varint encoded)
    const symbolBytes: number[] = [];
    for (const symbol of this.canonicalSymbols) {
      // Varint encode
      let s = symbol;
      while (s >= 0x80) {
        symbolBytes.push((s & 0x7F) | 0x80);
        s >>>= 7;
      }
      symbolBytes.push(s);
    }
    parts.push(new Uint8Array(symbolBytes));

    // Concatenate all parts
    const totalLength = parts.reduce((sum, p) => sum + p.length, 0);
    const result = new Uint8Array(totalLength);
    let offset = 0;
    for (const part of parts) {
      result.set(part, offset);
      offset += part.length;
    }

    return result;
  }

  /**
   * Deserialize a Huffman table.
   */
  static deserialize(data: Uint8Array, offset: number = 0): { codec: HuffmanCodec; bytesRead: number } {
    const codec = new HuffmanCodec();
    let pos = offset;

    // Max bit length
    codec.maxBitLength = data[pos++];

    if (codec.maxBitLength === 0) {
      return { codec, bytesRead: pos - offset };
    }

    // Length counts
    codec.lengthCounts = new Array(codec.maxBitLength + 1).fill(0);
    let totalSymbols = 0;
    for (let i = 1; i <= codec.maxBitLength; i++) {
      codec.lengthCounts[i] = data[pos++];
      totalSymbols += codec.lengthCounts[i];
    }

    // Symbols (varint decoded)
    codec.canonicalSymbols = [];
    for (let i = 0; i < totalSymbols; i++) {
      let symbol = 0;
      let shift = 0;
      while (true) {
        const byte = data[pos++];
        symbol |= (byte & 0x7F) << shift;
        if ((byte & 0x80) === 0) break;
        shift += 7;
      }
      codec.canonicalSymbols.push(symbol);
    }

    // Rebuild encode table and decode tree from canonical form
    const bitLengths: Map<number, number> = new Map();
    let symbolIdx = 0;
    for (let length = 1; length <= codec.maxBitLength; length++) {
      for (let j = 0; j < codec.lengthCounts[length]; j++) {
        bitLengths.set(codec.canonicalSymbols[symbolIdx++], length);
      }
    }
    codec.buildCanonicalCodes(bitLengths);

    return { codec, bytesRead: pos - offset };
  }

  /**
   * Get encoding statistics.
   */
  getStats(): { symbolCount: number; maxBitLength: number; avgBitLength: number } {
    let totalBits = 0;
    let totalSymbols = 0;

    for (const [, { bitLength }] of this.encodeTable) {
      totalBits += bitLength;
      totalSymbols++;
    }

    return {
      symbolCount: totalSymbols,
      maxBitLength: this.maxBitLength,
      avgBitLength: totalSymbols > 0 ? totalBits / totalSymbols : 0,
    };
  }
}

/**
 * Bit writer for building bit-packed streams.
 */
export class BitWriter {
  private buffer: number[] = [];
  private currentByte: number = 0;
  private bitPosition: number = 0;

  /**
   * Write bits to the stream.
   * @param value The bits to write (right-aligned)
   * @param numBits Number of bits to write
   */
  writeBits(value: number, numBits: number): void {
    for (let i = numBits - 1; i >= 0; i--) {
      const bit = (value >> i) & 1;
      this.currentByte = (this.currentByte << 1) | bit;
      this.bitPosition++;

      if (this.bitPosition === 8) {
        this.buffer.push(this.currentByte);
        this.currentByte = 0;
        this.bitPosition = 0;
      }
    }
  }

  /**
   * Finalize the stream and return bytes.
   * Pads the final byte with zeros if needed.
   */
  toBytes(): Uint8Array {
    // Flush remaining bits (padded with zeros)
    if (this.bitPosition > 0) {
      this.currentByte <<= (8 - this.bitPosition);
      this.buffer.push(this.currentByte);
    }
    return new Uint8Array(this.buffer);
  }

  /**
   * Get current bit count.
   */
  get bitCount(): number {
    return this.buffer.length * 8 + this.bitPosition;
  }
}

/**
 * Bit reader for decoding bit-packed streams.
 */
export class BitReader {
  private data: Uint8Array;
  private bytePos: number;
  private bitPos: number;

  constructor(data: Uint8Array, byteOffset: number = 0) {
    this.data = data;
    this.bytePos = byteOffset;
    this.bitPos = 0;
  }

  /**
   * Read a single bit.
   */
  readBit(): number {
    if (this.bytePos >= this.data.length) {
      throw new Error('BitReader: end of data');
    }

    const bit = (this.data[this.bytePos] >> (7 - this.bitPos)) & 1;
    this.bitPos++;

    if (this.bitPos === 8) {
      this.bitPos = 0;
      this.bytePos++;
    }

    return bit;
  }

  /**
   * Read multiple bits.
   */
  readBits(numBits: number): number {
    let value = 0;
    for (let i = 0; i < numBits; i++) {
      value = (value << 1) | this.readBit();
    }
    return value;
  }

  /**
   * Get current byte position (for tracking progress).
   */
  get currentBytePosition(): number {
    return this.bytePos;
  }
}

/**
 * Analyze label frequencies and return potential savings.
 */
export function analyzeLabels(labels: number[]): {
  frequencies: Map<number, number>;
  currentBits: number;
  huffmanBits: number;
  savingsPercent: number;
} {
  // Count frequencies
  const frequencies: Map<number, number> = new Map();
  for (const label of labels) {
    frequencies.set(label, (frequencies.get(label) ?? 0) + 1);
  }

  // Current encoding: varint (assume average 2 bytes = 16 bits for Unicode)
  // More accurate: count actual varint sizes
  let currentBits = 0;
  for (const label of labels) {
    // Varint size: 7 bits per byte, continuation bit
    if (label < 0x80) currentBits += 8;
    else if (label < 0x4000) currentBits += 16;
    else if (label < 0x200000) currentBits += 24;
    else currentBits += 32;
  }

  // Huffman encoding
  const codec = HuffmanCodec.build(frequencies);
  const huffmanBits = codec.calculateEncodedBits(labels);

  const savingsPercent = currentBits > 0
    ? ((currentBits - huffmanBits) / currentBits) * 100
    : 0;

  return {
    frequencies,
    currentBits,
    huffmanBits,
    savingsPercent,
  };
}
