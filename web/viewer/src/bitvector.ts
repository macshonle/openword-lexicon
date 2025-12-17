/**
 * bitvector.ts - Succinct bitvector with O(1) rank and O(log n) select
 *
 * Implementation based on:
 * - Jacobson, G. (1989) "Space-efficient Static Trees and Graphs" - FOCS 1989
 * - Clark, D. (1996) PhD thesis - practical rank/select structures
 * - Hanov, S. "Succinct Data Structures" - stevehanov.ca/blog/?id=120
 *
 * This module provides a BitVector class optimized for succinct data structures
 * like LOUDS tries. It supports:
 * - O(1) rank queries via precomputed directory
 * - O(log n) select queries via binary search on rank
 */

/**
 * Block size for rank directory (bits per block).
 * Smaller blocks = faster rank but more space overhead.
 * 32 bits aligns with Uint32Array word boundaries.
 */
const BLOCK_SIZE = 32;

/**
 * Superblock size for two-level rank directory.
 * Each superblock contains multiple blocks.
 * 256 bits = 8 blocks of 32 bits each.
 */
const SUPERBLOCK_SIZE = 256;
const BLOCKS_PER_SUPERBLOCK = SUPERBLOCK_SIZE / BLOCK_SIZE;

/**
 * BitVector with O(1) rank and O(log n) select support.
 *
 * The bitvector stores bits in a Uint32Array and maintains a directory
 * structure for fast rank queries. The directory uses a two-level scheme:
 * - Superblock directory: cumulative 1-bit count at superblock boundaries
 * - Block directory: cumulative 1-bit count within each superblock
 */
export class BitVector {
  /** Raw bit storage, 32 bits per element */
  private words: Uint32Array;

  /** Number of valid bits (may be less than words.length * 32) */
  private _length: number;

  /** Total count of 1-bits */
  private _popcount: number = 0;

  /** Superblock directory: cumulative rank at superblock boundaries */
  private superblocks: Uint32Array;

  /** Block directory: cumulative rank within each superblock (relative) */
  private blocks: Uint8Array;

  /** Whether the directory has been built */
  private directoryBuilt: boolean = false;

  /**
   * Create a new BitVector with the given capacity.
   * @param length Number of bits to allocate
   */
  constructor(length: number) {
    this._length = length;
    const wordCount = Math.ceil(length / BLOCK_SIZE);
    this.words = new Uint32Array(wordCount);

    // Allocate directory structures
    const superblockCount = Math.ceil(length / SUPERBLOCK_SIZE);
    this.superblocks = new Uint32Array(superblockCount);

    const blockCount = Math.ceil(length / BLOCK_SIZE);
    this.blocks = new Uint8Array(blockCount);
  }

  /** Number of bits in the bitvector */
  get length(): number {
    return this._length;
  }

  /** Total count of 1-bits (available after build()) */
  get popcount(): number {
    return this._popcount;
  }

  /**
   * Set a bit to 1.
   * @param i Bit position (0-indexed)
   */
  set(i: number): void {
    if (i < 0 || i >= this._length) {
      throw new RangeError(`Bit index ${i} out of range [0, ${this._length})`);
    }
    const wordIndex = Math.floor(i / BLOCK_SIZE);
    const bitIndex = i % BLOCK_SIZE;
    this.words[wordIndex] |= (1 << bitIndex);
    this.directoryBuilt = false;
  }

  /**
   * Clear a bit to 0.
   * @param i Bit position (0-indexed)
   */
  clear(i: number): void {
    if (i < 0 || i >= this._length) {
      throw new RangeError(`Bit index ${i} out of range [0, ${this._length})`);
    }
    const wordIndex = Math.floor(i / BLOCK_SIZE);
    const bitIndex = i % BLOCK_SIZE;
    this.words[wordIndex] &= ~(1 << bitIndex);
    this.directoryBuilt = false;
  }

  /**
   * Get the value of a bit.
   * @param i Bit position (0-indexed)
   * @returns true if bit is 1, false if 0
   */
  get(i: number): boolean {
    if (i < 0 || i >= this._length) {
      throw new RangeError(`Bit index ${i} out of range [0, ${this._length})`);
    }
    const wordIndex = Math.floor(i / BLOCK_SIZE);
    const bitIndex = i % BLOCK_SIZE;
    return (this.words[wordIndex] & (1 << bitIndex)) !== 0;
  }

  /**
   * Build the rank directory. Must be called before rank/select queries.
   * This freezes the bitvector - further modifications require rebuilding.
   */
  build(): void {
    let cumulativeRank = 0;
    let superblockIndex = 0;
    let blockInSuperblock = 0;

    for (let wordIndex = 0; wordIndex < this.words.length; wordIndex++) {
      // At superblock boundary, record cumulative rank
      if (blockInSuperblock === 0) {
        this.superblocks[superblockIndex] = cumulativeRank;
      }

      // Record relative rank within superblock
      this.blocks[wordIndex] = cumulativeRank - this.superblocks[superblockIndex];

      // Count 1-bits in this word
      cumulativeRank += this.popcountWord(this.words[wordIndex]);

      // Advance to next block
      blockInSuperblock++;
      if (blockInSuperblock >= BLOCKS_PER_SUPERBLOCK) {
        blockInSuperblock = 0;
        superblockIndex++;
      }
    }

    this._popcount = cumulativeRank;
    this.directoryBuilt = true;
  }

  /**
   * Count 1-bits in positions [0, i] (inclusive).
   * @param i Bit position (0-indexed)
   * @returns Number of 1-bits from position 0 to i
   */
  rank1(i: number): number {
    if (!this.directoryBuilt) {
      throw new Error('Directory not built. Call build() first.');
    }
    if (i < 0) {
      return 0;
    }
    if (i >= this._length) {
      return this._popcount;
    }

    const wordIndex = Math.floor(i / BLOCK_SIZE);
    const bitIndex = i % BLOCK_SIZE;
    const superblockIndex = Math.floor(wordIndex / BLOCKS_PER_SUPERBLOCK);

    // Cumulative rank from superblock + block directories
    let rank = this.superblocks[superblockIndex] + this.blocks[wordIndex];

    // Add popcount of bits [0, bitIndex] in the current word
    // Note: (1 << 32) wraps to 1 in JavaScript, so handle bitIndex=31 specially
    const mask = bitIndex === 31 ? 0xFFFFFFFF : (1 << (bitIndex + 1)) - 1;
    rank += this.popcountWord((this.words[wordIndex] & mask) >>> 0);

    return rank;
  }

  /**
   * Count 0-bits in positions [0, i] (inclusive).
   * @param i Bit position (0-indexed)
   * @returns Number of 0-bits from position 0 to i
   */
  rank0(i: number): number {
    if (i < 0) {
      return 0;
    }
    if (i >= this._length) {
      return this._length - this._popcount;
    }
    return (i + 1) - this.rank1(i);
  }

  /**
   * Find the position of the j-th 1-bit.
   * @param j Which 1-bit to find (1-indexed: 1 = first, 2 = second, etc.)
   * @returns Bit position, or -1 if not found
   */
  select1(j: number): number {
    if (!this.directoryBuilt) {
      throw new Error('Directory not built. Call build() first.');
    }
    if (j < 1 || j > this._popcount) {
      return -1;
    }

    // Binary search for the superblock containing the j-th 1-bit
    let lo = 0;
    let hi = this.superblocks.length - 1;

    while (lo < hi) {
      const mid = Math.floor((lo + hi + 1) / 2);
      if (this.superblocks[mid] < j) {
        lo = mid;
      } else {
        hi = mid - 1;
      }
    }

    const superblockIndex = lo;
    let remaining = j - this.superblocks[superblockIndex];

    // Linear search through blocks in this superblock
    const blockStart = superblockIndex * BLOCKS_PER_SUPERBLOCK;
    const blockEnd = Math.min(blockStart + BLOCKS_PER_SUPERBLOCK, this.words.length);

    for (let wordIndex = blockStart; wordIndex < blockEnd; wordIndex++) {
      const wordPopcount = this.popcountWord(this.words[wordIndex]);
      if (remaining <= wordPopcount) {
        // The j-th 1-bit is in this word
        return this.selectInWord(this.words[wordIndex], remaining) + wordIndex * BLOCK_SIZE;
      }
      remaining -= wordPopcount;
    }

    return -1; // Should not reach here if j is valid
  }

  /**
   * Find the position of the j-th 0-bit.
   * @param j Which 0-bit to find (1-indexed: 1 = first, 2 = second, etc.)
   * @returns Bit position, or -1 if not found
   */
  select0(j: number): number {
    if (!this.directoryBuilt) {
      throw new Error('Directory not built. Call build() first.');
    }
    const totalZeros = this._length - this._popcount;
    if (j < 1 || j > totalZeros) {
      return -1;
    }

    // Binary search on rank0 values
    let lo = 0;
    let hi = this._length - 1;

    while (lo < hi) {
      const mid = Math.floor((lo + hi) / 2);
      if (this.rank0(mid) < j) {
        lo = mid + 1;
      } else {
        hi = mid;
      }
    }

    return lo;
  }

  /**
   * Count 1-bits in a 32-bit word using the Hamming weight algorithm.
   */
  private popcountWord(word: number): number {
    // Parallel bit count (Brian Kernighan's algorithm is simpler but slower)
    word = word - ((word >>> 1) & 0x55555555);
    word = (word & 0x33333333) + ((word >>> 2) & 0x33333333);
    word = (word + (word >>> 4)) & 0x0f0f0f0f;
    word = word + (word >>> 8);
    word = word + (word >>> 16);
    return word & 0x3f;
  }

  /**
   * Find the position of the j-th 1-bit within a 32-bit word.
   * @param word The 32-bit word to search
   * @param j Which 1-bit to find (1-indexed)
   * @returns Bit position within the word (0-31)
   */
  private selectInWord(word: number, j: number): number {
    // Linear scan - simple but correct
    for (let i = 0; i < BLOCK_SIZE; i++) {
      if ((word & (1 << i)) !== 0) {
        j--;
        if (j === 0) {
          return i;
        }
      }
    }
    return -1; // Should not reach here
  }

  /**
   * Create a BitVector from a string of '0' and '1' characters.
   * Useful for testing.
   * @param bits String like "10110"
   */
  static fromBitString(bits: string): BitVector {
    const bv = new BitVector(bits.length);
    for (let i = 0; i < bits.length; i++) {
      if (bits[i] === '1') {
        bv.set(i);
      }
    }
    bv.build();
    return bv;
  }

  /**
   * Convert to a string of '0' and '1' characters.
   * Useful for testing and debugging.
   */
  toBitString(): string {
    let s = '';
    for (let i = 0; i < this._length; i++) {
      s += this.get(i) ? '1' : '0';
    }
    return s;
  }

  /**
   * Serialize the bitvector to a Uint8Array for storage.
   * Format: [length (4 bytes)] [words] [superblocks] [blocks]
   */
  serialize(): Uint8Array {
    if (!this.directoryBuilt) {
      throw new Error('Directory not built. Call build() first.');
    }

    const headerSize = 4; // length as uint32
    const wordsBytes = this.words.length * 4;
    const superblocksBytes = this.superblocks.length * 4;
    const blocksBytes = this.blocks.length;

    const buffer = new Uint8Array(headerSize + wordsBytes + superblocksBytes + blocksBytes);
    const view = new DataView(buffer.buffer);

    let offset = 0;

    // Header: length
    view.setUint32(offset, this._length, true);
    offset += 4;

    // Words
    for (let i = 0; i < this.words.length; i++) {
      view.setUint32(offset, this.words[i], true);
      offset += 4;
    }

    // Superblocks
    for (let i = 0; i < this.superblocks.length; i++) {
      view.setUint32(offset, this.superblocks[i], true);
      offset += 4;
    }

    // Blocks
    buffer.set(this.blocks, offset);

    return buffer;
  }

  /**
   * Get detailed size breakdown of serialized bitvector.
   */
  sizeBreakdown(): {
    headerBytes: number;
    rawBitsBytes: number;
    superblockBytes: number;
    blockBytes: number;
    totalBytes: number;
    directoryOverhead: number; // percentage
  } {
    const headerBytes = 4;
    const rawBitsBytes = this.words.length * 4;
    const superblockBytes = this.superblocks.length * 4;
    const blockBytes = this.blocks.length;
    const totalBytes = headerBytes + rawBitsBytes + superblockBytes + blockBytes;
    const directoryBytes = superblockBytes + blockBytes;
    const directoryOverhead = totalBytes > 0 ? (directoryBytes / totalBytes) * 100 : 0;

    return {
      headerBytes,
      rawBitsBytes,
      superblockBytes,
      blockBytes,
      totalBytes,
      directoryOverhead,
    };
  }

  /**
   * Deserialize a bitvector from a Uint8Array.
   */
  static deserialize(buffer: Uint8Array): BitVector {
    const view = new DataView(buffer.buffer, buffer.byteOffset, buffer.byteLength);
    let offset = 0;

    // Header: length
    const length = view.getUint32(offset, true);
    offset += 4;

    const bv = new BitVector(length);

    // Words
    for (let i = 0; i < bv.words.length; i++) {
      bv.words[i] = view.getUint32(offset, true);
      offset += 4;
    }

    // Superblocks
    for (let i = 0; i < bv.superblocks.length; i++) {
      bv.superblocks[i] = view.getUint32(offset, true);
      offset += 4;
    }

    // Blocks
    bv.blocks.set(buffer.slice(offset, offset + bv.blocks.length));

    // Compute popcount from superblocks
    if (bv.superblocks.length > 0) {
      const lastSuperblock = bv.superblocks.length - 1;
      const lastBlockStart = lastSuperblock * BLOCKS_PER_SUPERBLOCK;
      let popcount = bv.superblocks[lastSuperblock];
      for (let i = lastBlockStart; i < bv.words.length; i++) {
        popcount += bv.popcountWord(bv.words[i]);
      }
      bv._popcount = popcount;
    }

    bv.directoryBuilt = true;
    return bv;
  }
}
