/**
 * bitvector.test.ts - Comprehensive tests for BitVector with rank/select
 *
 * Tests are organized by risk level and functionality:
 * 1. Basic operations (set, get, length)
 * 2. Rank operations (highest risk - foundational for LOUDS)
 * 3. Select operations (high risk - used for tree navigation)
 * 4. Edge cases (boundaries, empty vectors, all 0s/1s)
 * 5. Serialization round-trip
 * 6. Large-scale stress tests
 */

import { describe, test } from 'node:test';
import * as assert from 'node:assert';
import { BitVector } from './bitvector.js';

describe('BitVector Basic Operations', () => {
  test('constructor creates bitvector with correct length', () => {
    const bv = new BitVector(100);
    assert.strictEqual(bv.length, 100);
  });

  test('all bits are initially 0', () => {
    const bv = new BitVector(64);
    for (let i = 0; i < 64; i++) {
      assert.strictEqual(bv.get(i), false, `bit ${i} should be 0`);
    }
  });

  test('set and get single bit', () => {
    const bv = new BitVector(100);
    bv.set(42);
    assert.strictEqual(bv.get(42), true);
    assert.strictEqual(bv.get(41), false);
    assert.strictEqual(bv.get(43), false);
  });

  test('set multiple bits', () => {
    const bv = new BitVector(100);
    bv.set(0);
    bv.set(31);
    bv.set(32);
    bv.set(99);

    assert.strictEqual(bv.get(0), true);
    assert.strictEqual(bv.get(31), true);
    assert.strictEqual(bv.get(32), true);
    assert.strictEqual(bv.get(99), true);
    assert.strictEqual(bv.get(1), false);
    assert.strictEqual(bv.get(50), false);
  });

  test('clear bit', () => {
    const bv = new BitVector(100);
    bv.set(42);
    assert.strictEqual(bv.get(42), true);
    bv.clear(42);
    assert.strictEqual(bv.get(42), false);
  });

  test('set out of range throws RangeError', () => {
    const bv = new BitVector(100);
    assert.throws(() => bv.set(100), RangeError);
    assert.throws(() => bv.set(-1), RangeError);
  });

  test('get out of range throws RangeError', () => {
    const bv = new BitVector(100);
    assert.throws(() => bv.get(100), RangeError);
    assert.throws(() => bv.get(-1), RangeError);
  });

  test('fromBitString creates correct bitvector', () => {
    const bv = BitVector.fromBitString('10110');
    assert.strictEqual(bv.length, 5);
    assert.strictEqual(bv.get(0), true);
    assert.strictEqual(bv.get(1), false);
    assert.strictEqual(bv.get(2), true);
    assert.strictEqual(bv.get(3), true);
    assert.strictEqual(bv.get(4), false);
  });

  test('toBitString returns correct string', () => {
    const bv = new BitVector(8);
    bv.set(0);
    bv.set(2);
    bv.set(5);
    assert.strictEqual(bv.toBitString(), '10100100');
  });

  test('fromBitString and toBitString round-trip', () => {
    const original = '1011001010110010101100101011001010110010101100101';
    const bv = BitVector.fromBitString(original);
    assert.strictEqual(bv.toBitString(), original);
  });
});

describe('BitVector Rank Operations', () => {
  test('rank1 requires build() to be called first', () => {
    const bv = new BitVector(10);
    bv.set(5);
    assert.throws(() => bv.rank1(5), /Directory not built/);
  });

  test('popcount after build', () => {
    const bv = BitVector.fromBitString('10110');
    assert.strictEqual(bv.popcount, 3);
  });

  test('rank1 on simple bitvector', () => {
    // Bits: 1 0 1 1 0
    // Pos:  0 1 2 3 4
    const bv = BitVector.fromBitString('10110');

    assert.strictEqual(bv.rank1(0), 1, 'rank1(0)');
    assert.strictEqual(bv.rank1(1), 1, 'rank1(1)');
    assert.strictEqual(bv.rank1(2), 2, 'rank1(2)');
    assert.strictEqual(bv.rank1(3), 3, 'rank1(3)');
    assert.strictEqual(bv.rank1(4), 3, 'rank1(4)');
  });

  test('rank0 on simple bitvector', () => {
    // Bits: 1 0 1 1 0
    // Pos:  0 1 2 3 4
    const bv = BitVector.fromBitString('10110');

    assert.strictEqual(bv.rank0(0), 0, 'rank0(0)');
    assert.strictEqual(bv.rank0(1), 1, 'rank0(1)');
    assert.strictEqual(bv.rank0(2), 1, 'rank0(2)');
    assert.strictEqual(bv.rank0(3), 1, 'rank0(3)');
    assert.strictEqual(bv.rank0(4), 2, 'rank0(4)');
  });

  test('rank1 with negative index returns 0', () => {
    const bv = BitVector.fromBitString('10110');
    assert.strictEqual(bv.rank1(-1), 0);
    assert.strictEqual(bv.rank1(-100), 0);
  });

  test('rank1 beyond length returns popcount', () => {
    const bv = BitVector.fromBitString('10110');
    assert.strictEqual(bv.rank1(5), 3);
    assert.strictEqual(bv.rank1(100), 3);
  });

  test('rank0 beyond length returns total zeros', () => {
    const bv = BitVector.fromBitString('10110');
    assert.strictEqual(bv.rank0(5), 2);
    assert.strictEqual(bv.rank0(100), 2);
  });

  test('rank1 across word boundary (32 bits)', () => {
    // Create a bitvector spanning multiple 32-bit words
    const bits = '1'.repeat(16) + '0'.repeat(16) + '1'.repeat(16) + '0'.repeat(16);
    const bv = BitVector.fromBitString(bits);

    assert.strictEqual(bv.rank1(15), 16, 'rank1(15) - end of first 16 ones');
    assert.strictEqual(bv.rank1(31), 16, 'rank1(31) - end of first word');
    assert.strictEqual(bv.rank1(32), 17, 'rank1(32) - start of second word');
    assert.strictEqual(bv.rank1(47), 32, 'rank1(47) - end of third group');
    assert.strictEqual(bv.rank1(63), 32, 'rank1(63) - end of second word');
  });

  test('rank1 identity: rank1(i) + rank0(i) = i + 1', () => {
    const bv = BitVector.fromBitString('10110100101101001011010010110100');
    for (let i = 0; i < bv.length; i++) {
      assert.strictEqual(
        bv.rank1(i) + bv.rank0(i),
        i + 1,
        `rank1(${i}) + rank0(${i}) should equal ${i + 1}`
      );
    }
  });

  test('rank1 is monotonically non-decreasing', () => {
    const bv = BitVector.fromBitString('10110100101101001011010010110100');
    let prev = 0;
    for (let i = 0; i < bv.length; i++) {
      const curr = bv.rank1(i);
      assert.ok(curr >= prev, `rank1(${i}) = ${curr} should be >= rank1(${i - 1}) = ${prev}`);
      prev = curr;
    }
  });
});

describe('BitVector Select Operations', () => {
  test('select1 requires build() to be called first', () => {
    const bv = new BitVector(10);
    bv.set(5);
    assert.throws(() => bv.select1(1), /Directory not built/);
  });

  test('select1 on simple bitvector', () => {
    // Bits: 1 0 1 1 0
    // Pos:  0 1 2 3 4
    // 1st 1-bit at position 0
    // 2nd 1-bit at position 2
    // 3rd 1-bit at position 3
    const bv = BitVector.fromBitString('10110');

    assert.strictEqual(bv.select1(1), 0, 'select1(1) - first 1-bit');
    assert.strictEqual(bv.select1(2), 2, 'select1(2) - second 1-bit');
    assert.strictEqual(bv.select1(3), 3, 'select1(3) - third 1-bit');
  });

  test('select0 on simple bitvector', () => {
    // Bits: 1 0 1 1 0
    // Pos:  0 1 2 3 4
    // 1st 0-bit at position 1
    // 2nd 0-bit at position 4
    const bv = BitVector.fromBitString('10110');

    assert.strictEqual(bv.select0(1), 1, 'select0(1) - first 0-bit');
    assert.strictEqual(bv.select0(2), 4, 'select0(2) - second 0-bit');
  });

  test('select1 returns -1 for j < 1', () => {
    const bv = BitVector.fromBitString('10110');
    assert.strictEqual(bv.select1(0), -1);
    assert.strictEqual(bv.select1(-1), -1);
  });

  test('select1 returns -1 for j > popcount', () => {
    const bv = BitVector.fromBitString('10110');
    assert.strictEqual(bv.select1(4), -1);
    assert.strictEqual(bv.select1(100), -1);
  });

  test('select0 returns -1 for j < 1', () => {
    const bv = BitVector.fromBitString('10110');
    assert.strictEqual(bv.select0(0), -1);
    assert.strictEqual(bv.select0(-1), -1);
  });

  test('select0 returns -1 for j > total zeros', () => {
    const bv = BitVector.fromBitString('10110');
    assert.strictEqual(bv.select0(3), -1);
    assert.strictEqual(bv.select0(100), -1);
  });

  test('select1 across word boundary', () => {
    // 16 ones, 16 zeros, 16 ones
    const bits = '1'.repeat(16) + '0'.repeat(16) + '1'.repeat(16);
    const bv = BitVector.fromBitString(bits);

    assert.strictEqual(bv.select1(16), 15, 'select1(16) - last of first 16 ones');
    assert.strictEqual(bv.select1(17), 32, 'select1(17) - first of second group');
    assert.strictEqual(bv.select1(32), 47, 'select1(32) - last 1-bit');
  });

  test('select0 across word boundary', () => {
    // 16 ones, 16 zeros, 16 ones
    const bits = '1'.repeat(16) + '0'.repeat(16) + '1'.repeat(16);
    const bv = BitVector.fromBitString(bits);

    assert.strictEqual(bv.select0(1), 16, 'select0(1) - first 0-bit');
    assert.strictEqual(bv.select0(16), 31, 'select0(16) - last 0-bit');
  });

  test('rank1 and select1 are inverses: rank1(select1(j)) = j', () => {
    const bv = BitVector.fromBitString('10110100101101001011010010110100');
    for (let j = 1; j <= bv.popcount; j++) {
      const pos = bv.select1(j);
      const rank = bv.rank1(pos);
      assert.strictEqual(rank, j, `rank1(select1(${j})) should equal ${j}, got ${rank}`);
    }
  });

  test('rank0 and select0 are inverses: rank0(select0(j)) = j', () => {
    const bv = BitVector.fromBitString('10110100101101001011010010110100');
    const totalZeros = bv.length - bv.popcount;
    for (let j = 1; j <= totalZeros; j++) {
      const pos = bv.select0(j);
      const rank = bv.rank0(pos);
      assert.strictEqual(rank, j, `rank0(select0(${j})) should equal ${j}, got ${rank}`);
    }
  });
});

describe('BitVector Edge Cases', () => {
  test('bitvector of all zeros', () => {
    const bv = new BitVector(64);
    bv.build();

    assert.strictEqual(bv.popcount, 0);
    assert.strictEqual(bv.rank1(0), 0);
    assert.strictEqual(bv.rank1(63), 0);
    assert.strictEqual(bv.rank0(63), 64);
    assert.strictEqual(bv.select1(1), -1);
    assert.strictEqual(bv.select0(1), 0);
    assert.strictEqual(bv.select0(64), 63);
  });

  test('bitvector of all ones', () => {
    const bv = new BitVector(64);
    for (let i = 0; i < 64; i++) bv.set(i);
    bv.build();

    assert.strictEqual(bv.popcount, 64);
    assert.strictEqual(bv.rank1(0), 1);
    assert.strictEqual(bv.rank1(63), 64);
    assert.strictEqual(bv.rank0(63), 0);
    assert.strictEqual(bv.select1(1), 0);
    assert.strictEqual(bv.select1(64), 63);
    assert.strictEqual(bv.select0(1), -1);
  });

  test('single bit set at position 0', () => {
    const bv = BitVector.fromBitString('10000');
    assert.strictEqual(bv.rank1(0), 1);
    assert.strictEqual(bv.select1(1), 0);
  });

  test('single bit set at last position', () => {
    const bv = BitVector.fromBitString('00001');
    assert.strictEqual(bv.rank1(4), 1);
    assert.strictEqual(bv.select1(1), 4);
  });

  test('alternating bits', () => {
    const bv = BitVector.fromBitString('10101010');

    assert.strictEqual(bv.popcount, 4);
    assert.strictEqual(bv.rank1(0), 1);
    assert.strictEqual(bv.rank1(1), 1);
    assert.strictEqual(bv.rank1(2), 2);
    assert.strictEqual(bv.rank1(7), 4);

    assert.strictEqual(bv.select1(1), 0);
    assert.strictEqual(bv.select1(2), 2);
    assert.strictEqual(bv.select1(4), 6);

    assert.strictEqual(bv.select0(1), 1);
    assert.strictEqual(bv.select0(2), 3);
    assert.strictEqual(bv.select0(4), 7);
  });

  test('length not multiple of 32', () => {
    // 37 bits - crosses word boundary with partial last word
    const bv = new BitVector(37);
    bv.set(0);
    bv.set(31);
    bv.set(32);
    bv.set(36);
    bv.build();

    assert.strictEqual(bv.length, 37);
    assert.strictEqual(bv.popcount, 4);
    assert.strictEqual(bv.rank1(36), 4);
    assert.strictEqual(bv.select1(4), 36);
  });

  test('length of 1', () => {
    const bv0 = BitVector.fromBitString('0');
    assert.strictEqual(bv0.popcount, 0);
    assert.strictEqual(bv0.rank1(0), 0);
    assert.strictEqual(bv0.rank0(0), 1);

    const bv1 = BitVector.fromBitString('1');
    assert.strictEqual(bv1.popcount, 1);
    assert.strictEqual(bv1.rank1(0), 1);
    assert.strictEqual(bv1.rank0(0), 0);
  });
});

describe('BitVector Serialization', () => {
  test('serialize and deserialize round-trip', () => {
    const original = BitVector.fromBitString('10110100101101001011010010110100');
    const serialized = original.serialize();
    const restored = BitVector.deserialize(serialized);

    assert.strictEqual(restored.length, original.length);
    assert.strictEqual(restored.popcount, original.popcount);
    assert.strictEqual(restored.toBitString(), original.toBitString());
  });

  test('deserialize preserves rank/select functionality', () => {
    const original = BitVector.fromBitString('10110100101101001011010010110100');
    const serialized = original.serialize();
    const restored = BitVector.deserialize(serialized);

    for (let i = 0; i < original.length; i++) {
      assert.strictEqual(restored.rank1(i), original.rank1(i), `rank1(${i})`);
    }
    for (let j = 1; j <= original.popcount; j++) {
      assert.strictEqual(restored.select1(j), original.select1(j), `select1(${j})`);
    }
  });

  test('serialize requires build() to be called first', () => {
    const bv = new BitVector(10);
    bv.set(5);
    assert.throws(() => bv.serialize(), /Directory not built/);
  });

  test('round-trip with large bitvector crossing superblock boundary', () => {
    // 300 bits - crosses the 256-bit superblock boundary
    const bv = new BitVector(300);
    for (let i = 0; i < 300; i += 3) bv.set(i);
    bv.build();

    const serialized = bv.serialize();
    const restored = BitVector.deserialize(serialized);

    assert.strictEqual(restored.toBitString(), bv.toBitString());
    assert.strictEqual(restored.popcount, bv.popcount);

    // Verify rank/select work across superblock boundary
    assert.strictEqual(restored.rank1(255), bv.rank1(255));
    assert.strictEqual(restored.rank1(256), bv.rank1(256));
    assert.strictEqual(restored.rank1(299), bv.rank1(299));
  });
});

describe('BitVector Large Scale', () => {
  test('1 million bits with random pattern', () => {
    const SIZE = 1_000_000;
    const bv = new BitVector(SIZE);

    // Set bits using a deterministic pseudo-random pattern
    // Simple PRNG using xorshift to avoid JavaScript number issues
    let x = 12345;
    for (let i = 0; i < SIZE; i++) {
      // xorshift32
      x ^= x << 13;
      x ^= x >>> 17;
      x ^= x << 5;
      x = x >>> 0; // Ensure unsigned 32-bit
      if ((x & 1) === 0) bv.set(i);
    }
    bv.build();

    // Verify popcount is reasonable (should be around 50%)
    assert.ok(bv.popcount > 400_000, `popcount ${bv.popcount} should be > 400K`);
    assert.ok(bv.popcount < 600_000, `popcount ${bv.popcount} should be < 600K`);

    // Verify rank/select consistency at sample points
    const samplePoints = [0, 1, 100, 1000, 10000, 100000, 500000, 999999];
    for (const i of samplePoints) {
      // rank1(i) + rank0(i) = i + 1
      assert.strictEqual(bv.rank1(i) + bv.rank0(i), i + 1, `identity at ${i}`);
    }

    // Verify select1/rank1 inverse at sample points
    const sampleRanks = [1, 10, 100, 1000, 10000, bv.popcount];
    for (const j of sampleRanks) {
      const pos = bv.select1(j);
      assert.ok(pos >= 0 && pos < SIZE, `select1(${j}) = ${pos} should be in range`);
      assert.strictEqual(bv.rank1(pos), j, `rank1(select1(${j})) should equal ${j}`);
    }
  });

  test('performance: 10M bits rank query', () => {
    const SIZE = 10_000_000;
    const bv = new BitVector(SIZE);

    // Set every other bit
    for (let i = 0; i < SIZE; i += 2) bv.set(i);
    bv.build();

    // Time 1000 random rank queries
    const start = performance.now();
    let sum = 0;
    for (let i = 0; i < 1000; i++) {
      const pos = Math.floor(Math.random() * SIZE);
      sum += bv.rank1(pos);
    }
    const elapsed = performance.now() - start;

    // Should complete quickly (< 100ms for 1000 queries)
    assert.ok(elapsed < 100, `1000 rank queries took ${elapsed}ms, expected < 100ms`);
    assert.ok(sum > 0, 'sanity check: sum should be positive');
  });
});
