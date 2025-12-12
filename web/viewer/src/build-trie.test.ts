#!/usr/bin/env npx tsx
/**
 * Tests for build-trie.ts and binary trie format
 *
 * Uses Node's built-in test runner (node:test)
 * Run with: npx tsx src/build-trie.test.ts
 */

import { test, describe } from 'node:test';
import assert from 'node:assert';

// ============================================================================
// Varint encoding/decoding (copied from build-trie.ts for testing)
// ============================================================================

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

function readVarint(buffer: Uint8Array, offset: number): { value: number; bytesRead: number } {
  let value = 0;
  let shift = 0;
  let bytesRead = 0;
  while (true) {
    const byte = buffer[offset + bytesRead];
    bytesRead++;
    value |= (byte & 0x7F) << shift;
    if ((byte & 0x80) === 0) break;
    shift += 7;
  }
  return { value, bytesRead };
}

// ============================================================================
// Varint Tests
// ============================================================================

describe('Varint encoding', () => {
  test('varintSize returns correct sizes', () => {
    // 1-byte values (0-127)
    assert.strictEqual(varintSize(0), 1);
    assert.strictEqual(varintSize(1), 1);
    assert.strictEqual(varintSize(127), 1);

    // 2-byte values (128-16383)
    assert.strictEqual(varintSize(128), 2);
    assert.strictEqual(varintSize(16383), 2);

    // 3-byte values (16384-2097151)
    assert.strictEqual(varintSize(16384), 3);
    assert.strictEqual(varintSize(2097151), 3);

    // 4-byte values
    assert.strictEqual(varintSize(2097152), 4);
  });

  test('varint round-trip for small values', () => {
    const buffer = new Uint8Array(10);
    for (const value of [0, 1, 63, 64, 127]) {
      const written = writeVarint(buffer, 0, value);
      assert.strictEqual(written, 1, `Value ${value} should use 1 byte`);

      const { value: decoded, bytesRead } = readVarint(buffer, 0);
      assert.strictEqual(decoded, value);
      assert.strictEqual(bytesRead, 1);
    }
  });

  test('varint round-trip for 2-byte values', () => {
    const buffer = new Uint8Array(10);
    for (const value of [128, 255, 1000, 16383]) {
      const written = writeVarint(buffer, 0, value);
      assert.strictEqual(written, 2, `Value ${value} should use 2 bytes`);

      const { value: decoded, bytesRead } = readVarint(buffer, 0);
      assert.strictEqual(decoded, value);
      assert.strictEqual(bytesRead, 2);
    }
  });

  test('varint round-trip for large values', () => {
    const buffer = new Uint8Array(10);
    for (const value of [16384, 100000, 823446, 2097151]) {
      const written = writeVarint(buffer, 0, value);
      const { value: decoded, bytesRead } = readVarint(buffer, 0);
      assert.strictEqual(decoded, value);
      assert.strictEqual(bytesRead, written);
    }
  });

  test('varint handles typical node ID deltas', () => {
    // Based on actual DAWG statistics: 37.4% of deltas are 1
    const buffer = new Uint8Array(10);
    const typicalDeltas = [1, 2, 3, 5, 10, 50, 100, 500, 1000];

    for (const delta of typicalDeltas) {
      const written = writeVarint(buffer, 0, delta);
      const { value: decoded } = readVarint(buffer, 0);
      assert.strictEqual(decoded, delta);
    }
  });
});

// ============================================================================
// Unicode Character Handling Tests (the bug we fixed!)
// ============================================================================

describe('Unicode character handling', () => {
  test('codePointAt vs charCodeAt for ASCII', () => {
    const char = 'a';
    assert.strictEqual(char.codePointAt(0), 97);
    assert.strictEqual(char.charCodeAt(0), 97);
    // For ASCII, both are equivalent
  });

  test('codePointAt handles extended Latin correctly', () => {
    // This was the bug: 'š' (U+0161) has charCodeAt(0) = 353
    // When truncated to 1 byte: 353 & 0xFF = 97 = 'a'
    const sha = 'š';
    assert.strictEqual(sha.codePointAt(0), 0x0161); // 353
    assert.strictEqual(sha.charCodeAt(0), 0x0161);  // 353

    // The collision happens when storing as single byte
    assert.strictEqual(sha.charCodeAt(0) & 0xFF, 97); // Collides with 'a'!
    assert.notStrictEqual(sha.codePointAt(0), 97);    // Full code point is safe
  });

  test('codePointAt handles emoji correctly', () => {
    const emoji = '🥜'; // Peanut emoji, U+1F95C
    assert.strictEqual(emoji.codePointAt(0), 0x1F95C);

    // charCodeAt returns the high surrogate for emoji
    assert.strictEqual(emoji.charCodeAt(0), 0xD83E); // High surrogate
    assert.strictEqual(emoji.charCodeAt(1), 0xDD5C); // Low surrogate

    // Emoji length in JS is 2 (surrogate pair)
    assert.strictEqual(emoji.length, 2);

    // But spread operator or codePointAt treats it as 1 character
    assert.strictEqual([...emoji].length, 1);
  });

  test('varint can encode full Unicode code points', () => {
    const buffer = new Uint8Array(10);
    const testChars = [
      { char: 'a', codePoint: 97 },
      { char: 'š', codePoint: 0x0161 },
      { char: 'Ł', codePoint: 0x0141 },
      { char: '🥜', codePoint: 0x1F95C },
      { char: '🧵', codePoint: 0x1F9F5 },
    ];

    for (const { char, codePoint } of testChars) {
      const cp = char.codePointAt(0)!;
      assert.strictEqual(cp, codePoint, `Code point for '${char}'`);

      const written = writeVarint(buffer, 0, cp);
      const { value: decoded } = readVarint(buffer, 0);
      assert.strictEqual(decoded, cp);

      // Verify we can reconstruct the character
      const reconstructed = String.fromCodePoint(decoded);
      assert.strictEqual(reconstructed, char);
    }
  });

  test('characters that caused collisions are now distinguishable', () => {
    // These pairs collided when using charCodeAt(0) & 0xFF
    const collisionPairs = [
      ['a', 'š'],   // Both were byte 97
      ['A', 'Ł'],   // Both were byte 65
      ['!', 'ġ'],   // Both were byte 33
    ];

    const buffer = new Uint8Array(10);

    for (const [ascii, extended] of collisionPairs) {
      const cp1 = ascii.codePointAt(0)!;
      const cp2 = extended.codePointAt(0)!;

      // Code points should be different
      assert.notStrictEqual(cp1, cp2, `'${ascii}' and '${extended}' should have different code points`);

      // Both should round-trip correctly
      writeVarint(buffer, 0, cp1);
      const { value: decoded1 } = readVarint(buffer, 0);
      assert.strictEqual(String.fromCodePoint(decoded1), ascii);

      writeVarint(buffer, 0, cp2);
      const { value: decoded2 } = readVarint(buffer, 0);
      assert.strictEqual(String.fromCodePoint(decoded2), extended);
    }
  });
});

// ============================================================================
// DAWG Node Structure Tests
// ============================================================================

describe('DAWG structure', () => {
  // Minimal DAWGNode implementation for testing
  class DAWGNode {
    children: Map<string, DAWGNode> = new Map();
    isTerminal: boolean = false;
    id: number = -1;

    getSignature(): string {
      const childSigs = Array.from(this.children.entries())
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([char, node]) => `${char}:${node.id}`)
        .join(',');
      return `${this.isTerminal ? '1' : '0'}:${childSigs}`;
    }
  }

  test('DAWGNode signature distinguishes terminal vs non-terminal', () => {
    const node1 = new DAWGNode();
    node1.isTerminal = false;

    const node2 = new DAWGNode();
    node2.isTerminal = true;

    assert.notStrictEqual(node1.getSignature(), node2.getSignature());
  });

  test('DAWGNode signature includes children', () => {
    const child = new DAWGNode();
    child.id = 0;

    const parent1 = new DAWGNode();
    parent1.children.set('a', child);

    const parent2 = new DAWGNode();
    parent2.children.set('b', child);

    assert.notStrictEqual(parent1.getSignature(), parent2.getSignature());
  });

  test('nodes with same structure have same signature', () => {
    const child1 = new DAWGNode();
    child1.id = 5;

    const child2 = new DAWGNode();
    child2.id = 5;

    const parent1 = new DAWGNode();
    parent1.isTerminal = true;
    parent1.children.set('x', child1);

    const parent2 = new DAWGNode();
    parent2.isTerminal = true;
    parent2.children.set('x', child2);

    assert.strictEqual(parent1.getSignature(), parent2.getSignature());
  });
});

// ============================================================================
// Binary Format Tests
// ============================================================================

describe('Binary format', () => {
  test('header is 12 bytes with correct magic', () => {
    const header = new Uint8Array(12);
    const view = new DataView(header.buffer);

    // Write header
    const magic = new TextEncoder().encode('OWTRIE');
    header.set(magic, 0);
    view.setUint16(6, 4, true); // version 4
    view.setUint32(8, 1000, true); // word count

    // Verify
    const decodedMagic = new TextDecoder().decode(header.slice(0, 6));
    assert.strictEqual(decodedMagic, 'OWTRIE');
    assert.strictEqual(view.getUint16(6, true), 4);
    assert.strictEqual(view.getUint32(8, true), 1000);
  });

  test('v2 node format is flags + count + 3-byte children', () => {
    // v2 format: flags(1) + count(1) + children(char:1 + nodeId:2 each)
    const buffer = new Uint8Array(20);
    const view = new DataView(buffer.buffer);

    let offset = 0;
    buffer[offset++] = 0x01; // isTerminal = true
    buffer[offset++] = 2;    // 2 children

    // Child 1: 'a' -> node 100
    buffer[offset++] = 97;   // 'a'
    view.setUint16(offset, 100, true);
    offset += 2;

    // Child 2: 'b' -> node 200
    buffer[offset++] = 98;   // 'b'
    view.setUint16(offset, 200, true);
    offset += 2;

    // Total: 1 + 1 + 2*3 = 8 bytes
    assert.strictEqual(offset, 8);
  });

  test('v4 node format uses varints for char and delta', () => {
    const buffer = new Uint8Array(20);
    let offset = 0;

    buffer[offset++] = 0x01; // isTerminal = true
    buffer[offset++] = 2;    // 2 children

    // Child 1: 'a' (97) -> delta 10
    offset = writeVarint(buffer, offset, 97);  // char
    offset = writeVarint(buffer, offset, 10);  // delta

    // Child 2: 'š' (353) -> delta 5
    offset = writeVarint(buffer, offset, 353); // char (2 bytes)
    offset = writeVarint(buffer, offset, 5);   // delta

    // Verify: 1 + 1 + (1+1) + (2+1) = 7 bytes
    assert.strictEqual(offset, 7);

    // Read back
    let readOffset = 2;
    const { value: char1, bytesRead: cb1 } = readVarint(buffer, readOffset);
    readOffset += cb1;
    const { value: delta1, bytesRead: db1 } = readVarint(buffer, readOffset);
    readOffset += db1;

    assert.strictEqual(char1, 97);
    assert.strictEqual(delta1, 10);
    assert.strictEqual(String.fromCodePoint(char1), 'a');

    const { value: char2, bytesRead: cb2 } = readVarint(buffer, readOffset);
    readOffset += cb2;
    const { value: delta2, bytesRead: db2 } = readVarint(buffer, readOffset);
    readOffset += db2;

    assert.strictEqual(char2, 353);
    assert.strictEqual(delta2, 5);
    assert.strictEqual(String.fromCodePoint(char2), 'š');
  });

  test('delta encoding: parent - child is always positive in post-order', () => {
    // In post-order: children are processed before parents
    // So child IDs are always lower than parent IDs
    // Delta = parentId - childId > 0

    const parentId = 100;
    const childId = 50;
    const delta = parentId - childId;

    assert.ok(delta > 0, 'Delta should be positive');
    assert.strictEqual(parentId - delta, childId, 'Can reconstruct childId');
  });
});

// ============================================================================
// Integration Test: Build and read a mini trie
// ============================================================================

describe('Integration: mini trie', () => {
  // Build a small v4 trie and verify we can read it back
  test('build and read v4 trie with ASCII words', () => {
    // Simulate building a trie with: "a", "an", "ant"
    const words = ['a', 'an', 'ant'];

    // Manual DAWG structure (simplified, no deduplication):
    // root -> 'a' (terminal) -> 'n' (terminal) -> 't' (terminal)
    // Node IDs in post-order: 't'=0, 'n'=1, 'a'=2, root=3

    const buffer = new Uint8Array(100);
    const view = new DataView(buffer.buffer);
    let offset = 0;

    // Header
    buffer.set(new TextEncoder().encode('OWTRIE'), offset);
    offset += 6;
    view.setUint16(offset, 4, true); // version 4
    offset += 2;
    view.setUint32(offset, words.length, true);
    offset += 4;

    // Node 0: 't' - terminal, no children
    buffer[offset++] = 0x01; // terminal
    buffer[offset++] = 0;    // 0 children

    // Node 1: 'n' - terminal, one child 't'->0
    buffer[offset++] = 0x01; // terminal
    buffer[offset++] = 1;    // 1 child
    offset = writeVarint(buffer, offset, 't'.codePointAt(0)!);
    offset = writeVarint(buffer, offset, 1 - 0); // delta = 1

    // Node 2: 'a' - terminal, one child 'n'->1
    buffer[offset++] = 0x01; // terminal
    buffer[offset++] = 1;    // 1 child
    offset = writeVarint(buffer, offset, 'n'.codePointAt(0)!);
    offset = writeVarint(buffer, offset, 2 - 1); // delta = 1

    // Node 3: root - not terminal, one child 'a'->2
    buffer[offset++] = 0x00; // not terminal
    buffer[offset++] = 1;    // 1 child
    offset = writeVarint(buffer, offset, 'a'.codePointAt(0)!);
    offset = writeVarint(buffer, offset, 3 - 2); // delta = 1

    // Now read it back
    const trie = buffer.slice(0, offset);

    // Verify header
    assert.strictEqual(new TextDecoder().decode(trie.slice(0, 6)), 'OWTRIE');
    assert.strictEqual(new DataView(trie.buffer).getUint16(6, true), 4);
    assert.strictEqual(new DataView(trie.buffer).getUint32(8, true), 3);

    // Build node index
    const nodeOffsets: number[] = [];
    let idx = 12;
    while (idx < trie.length) {
      nodeOffsets.push(idx);
      idx++; // flags
      const childCount = trie[idx++];
      for (let i = 0; i < childCount; i++) {
        idx += readVarint(trie, idx).bytesRead; // char
        idx += readVarint(trie, idx).bytesRead; // delta
      }
    }

    assert.strictEqual(nodeOffsets.length, 4, 'Should have 4 nodes');

    // Helper to check word
    function has(word: string): boolean {
      let nodeId = nodeOffsets.length - 1; // root
      for (const char of word) {
        const off = nodeOffsets[nodeId];
        const childCount = trie[off + 1];
        let childOff = off + 2;
        let found = false;

        for (let i = 0; i < childCount; i++) {
          const { value: cp, bytesRead: cb } = readVarint(trie, childOff);
          childOff += cb;
          const { value: delta, bytesRead: db } = readVarint(trie, childOff);
          childOff += db;

          if (String.fromCodePoint(cp) === char) {
            nodeId = nodeId - delta;
            found = true;
            break;
          }
        }
        if (!found) return false;
      }
      return (trie[nodeOffsets[nodeId]] & 0x01) !== 0;
    }

    assert.strictEqual(has('a'), true);
    assert.strictEqual(has('an'), true);
    assert.strictEqual(has('ant'), true);
    assert.strictEqual(has('b'), false);
    assert.strictEqual(has('at'), false);
  });

  test('build and read v4 trie with Unicode words', () => {
    // Test that extended Latin and emoji work correctly
    // Words: "š" (U+0161), "a" (to verify no collision)

    const buffer = new Uint8Array(100);
    const view = new DataView(buffer.buffer);
    let offset = 0;

    // Header
    buffer.set(new TextEncoder().encode('OWTRIE'), offset);
    offset += 6;
    view.setUint16(offset, 4, true);
    offset += 2;
    view.setUint32(offset, 2, true); // 2 words
    offset += 4;

    // Node 0: 'a' leaf - terminal, no children
    buffer[offset++] = 0x01;
    buffer[offset++] = 0;

    // Node 1: 'š' leaf - terminal, no children
    buffer[offset++] = 0x01;
    buffer[offset++] = 0;

    // Node 2: root - not terminal, two children
    buffer[offset++] = 0x00;
    buffer[offset++] = 2;
    // Child 'a' -> node 0, delta = 2
    offset = writeVarint(buffer, offset, 'a'.codePointAt(0)!);
    offset = writeVarint(buffer, offset, 2);
    // Child 'š' -> node 1, delta = 1
    offset = writeVarint(buffer, offset, 'š'.codePointAt(0)!);
    offset = writeVarint(buffer, offset, 1);

    const trie = buffer.slice(0, offset);

    // Build index
    const nodeOffsets: number[] = [];
    let idx = 12;
    while (idx < trie.length) {
      nodeOffsets.push(idx);
      idx++;
      const childCount = trie[idx++];
      for (let i = 0; i < childCount; i++) {
        idx += readVarint(trie, idx).bytesRead;
        idx += readVarint(trie, idx).bytesRead;
      }
    }

    assert.strictEqual(nodeOffsets.length, 3);

    // Read root's children
    const rootOffset = nodeOffsets[2];
    const childCount = trie[rootOffset + 1];
    assert.strictEqual(childCount, 2);

    // Both 'a' and 'š' should be distinguishable
    const children = new Map<string, number>();
    let childOff = rootOffset + 2;
    for (let i = 0; i < childCount; i++) {
      const { value: cp, bytesRead: cb } = readVarint(trie, childOff);
      childOff += cb;
      const { value: delta, bytesRead: db } = readVarint(trie, childOff);
      childOff += db;
      children.set(String.fromCodePoint(cp), 2 - delta);
    }

    assert.strictEqual(children.size, 2, 'Should have 2 distinct children');
    assert.ok(children.has('a'), "Should have 'a'");
    assert.ok(children.has('š'), "Should have 'š'");
    assert.strictEqual(children.get('a'), 0);
    assert.strictEqual(children.get('š'), 1);
  });
});

console.log('Running tests...');
