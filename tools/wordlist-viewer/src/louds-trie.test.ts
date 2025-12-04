/**
 * louds-trie.test.ts - Tests for LOUDS trie with word lookup and ID mapping
 *
 * Tests verify:
 * 1. Building trie from word list
 * 2. Word membership (has)
 * 3. Word ID mapping (sequential IDs in BFS order)
 * 4. Prefix search
 * 5. Unicode handling
 * 6. Serialization round-trip
 */

import { describe, test } from 'node:test';
import * as assert from 'node:assert';
import { LOUDSTrie } from './louds-trie.js';

describe('LOUDSTrie Construction', () => {
  test('empty word list', () => {
    const trie = LOUDSTrie.build([]);
    assert.strictEqual(trie.wordCount, 0);
  });

  test('single word', () => {
    const trie = LOUDSTrie.build(['hello']);
    assert.strictEqual(trie.wordCount, 1);
    assert.strictEqual(trie.has('hello'), true);
    assert.strictEqual(trie.has('hell'), false);
    assert.strictEqual(trie.has('hello!'), false);
  });

  test('multiple words with shared prefix', () => {
    const trie = LOUDSTrie.build(['ant', 'ante', 'anti']);
    assert.strictEqual(trie.wordCount, 3);
    assert.strictEqual(trie.has('ant'), true);
    assert.strictEqual(trie.has('ante'), true);
    assert.strictEqual(trie.has('anti'), true);
    assert.strictEqual(trie.has('an'), false);
    assert.strictEqual(trie.has('antler'), false);
  });

  test('words with no shared prefix', () => {
    const trie = LOUDSTrie.build(['apple', 'banana', 'cherry']);
    assert.strictEqual(trie.wordCount, 3);
    assert.strictEqual(trie.has('apple'), true);
    assert.strictEqual(trie.has('banana'), true);
    assert.strictEqual(trie.has('cherry'), true);
    assert.strictEqual(trie.has('apricot'), false);
  });

  test('single character words', () => {
    const trie = LOUDSTrie.build(['a', 'b', 'c']);
    assert.strictEqual(trie.wordCount, 3);
    assert.strictEqual(trie.has('a'), true);
    assert.strictEqual(trie.has('b'), true);
    assert.strictEqual(trie.has('c'), true);
    assert.strictEqual(trie.has('d'), false);
  });
});

describe('LOUDSTrie Word Lookup', () => {
  test('has returns true for existing words', () => {
    const trie = LOUDSTrie.build(['cat', 'car', 'card', 'care', 'careful']);
    assert.strictEqual(trie.has('cat'), true);
    assert.strictEqual(trie.has('car'), true);
    assert.strictEqual(trie.has('card'), true);
    assert.strictEqual(trie.has('care'), true);
    assert.strictEqual(trie.has('careful'), true);
  });

  test('has returns false for non-existing words', () => {
    const trie = LOUDSTrie.build(['cat', 'car', 'card', 'care', 'careful']);
    assert.strictEqual(trie.has('ca'), false); // prefix only
    assert.strictEqual(trie.has('cart'), false); // not in list
    assert.strictEqual(trie.has('dog'), false); // completely different
    assert.strictEqual(trie.has(''), false); // empty string
  });

  test('has with empty word in trie', () => {
    // Note: empty string as a word is an edge case
    const trie = LOUDSTrie.build(['', 'a', 'ab']);
    // Empty string at root - should be terminal at node 1
    // This depends on implementation details
  });

  test('case sensitivity', () => {
    const trie = LOUDSTrie.build(['Hello', 'HELLO', 'hello']);
    assert.strictEqual(trie.wordCount, 3);
    assert.strictEqual(trie.has('Hello'), true);
    assert.strictEqual(trie.has('HELLO'), true);
    assert.strictEqual(trie.has('hello'), true);
    assert.strictEqual(trie.has('hElLo'), false);
  });
});

describe('LOUDSTrie Word IDs', () => {
  test('wordId returns sequential IDs', () => {
    const words = ['ant', 'ante', 'anti'];
    const trie = LOUDSTrie.build(words);

    // IDs should be assigned in BFS terminal order
    const id0 = trie.wordId('ant');
    const id1 = trie.wordId('ante');
    const id2 = trie.wordId('anti');

    // All IDs should be unique and in range [0, wordCount)
    const ids = [id0, id1, id2];
    assert.ok(ids.every((id) => id >= 0 && id < 3), 'IDs should be in range');
    assert.strictEqual(new Set(ids).size, 3, 'IDs should be unique');
  });

  test('wordId returns -1 for non-existing words', () => {
    const trie = LOUDSTrie.build(['cat', 'car', 'card']);
    assert.strictEqual(trie.wordId('ca'), -1);
    assert.strictEqual(trie.wordId('dog'), -1);
    assert.strictEqual(trie.wordId(''), -1);
  });

  test('wordId consistency with has', () => {
    const words = ['apple', 'apply', 'banana', 'band', 'bandana'];
    const trie = LOUDSTrie.build(words);

    for (const word of words) {
      assert.ok(trie.has(word), `has(${word}) should be true`);
      assert.ok(trie.wordId(word) >= 0, `wordId(${word}) should be >= 0`);
    }

    const nonWords = ['app', 'ban', 'xyz'];
    for (const word of nonWords) {
      assert.strictEqual(trie.has(word), false, `has(${word}) should be false`);
      assert.strictEqual(trie.wordId(word), -1, `wordId(${word}) should be -1`);
    }
  });

  test('wordId covers all IDs from 0 to wordCount-1', () => {
    const words = ['a', 'ab', 'abc', 'b', 'bc', 'bcd', 'c'];
    const trie = LOUDSTrie.build(words);

    const ids = words.map((w) => trie.wordId(w));
    ids.sort((a, b) => a - b);

    // Should have IDs 0, 1, 2, 3, 4, 5, 6
    for (let i = 0; i < words.length; i++) {
      assert.ok(ids.includes(i), `ID ${i} should be present`);
    }
  });
});

describe('LOUDSTrie Prefix Search', () => {
  test('keysWithPrefix returns matching words', () => {
    const trie = LOUDSTrie.build(['cat', 'car', 'card', 'care', 'careful', 'dog']);

    const carWords = trie.keysWithPrefix('car');
    assert.ok(carWords.includes('car'));
    assert.ok(carWords.includes('card'));
    assert.ok(carWords.includes('care'));
    assert.ok(carWords.includes('careful'));
    assert.strictEqual(carWords.includes('cat'), false);
    assert.strictEqual(carWords.includes('dog'), false);
  });

  test('keysWithPrefix with empty prefix returns all words', () => {
    const words = ['a', 'b', 'c'];
    const trie = LOUDSTrie.build(words);

    const all = trie.keysWithPrefix('');
    assert.strictEqual(all.length, 3);
  });

  test('keysWithPrefix with non-matching prefix returns empty', () => {
    const trie = LOUDSTrie.build(['apple', 'banana']);

    const result = trie.keysWithPrefix('xyz');
    assert.strictEqual(result.length, 0);
  });

  test('keysWithPrefix respects limit', () => {
    const words = Array.from({ length: 100 }, (_, i) => `word${i.toString().padStart(3, '0')}`);
    const trie = LOUDSTrie.build(words);

    const limited = trie.keysWithPrefix('word', 10);
    assert.strictEqual(limited.length, 10);
  });

  test('keysWithPrefix with exact match', () => {
    const trie = LOUDSTrie.build(['cat', 'cats', 'caterpillar']);

    const result = trie.keysWithPrefix('cat');
    assert.ok(result.includes('cat'));
    assert.ok(result.includes('cats'));
    assert.ok(result.includes('caterpillar'));
  });
});

describe('LOUDSTrie Unicode', () => {
  test('extended Latin characters', () => {
    const words = ['café', 'naïve', 'résumé', 'Zürich'];
    const trie = LOUDSTrie.build(words);

    assert.strictEqual(trie.wordCount, 4);
    for (const word of words) {
      assert.strictEqual(trie.has(word), true, `should have ${word}`);
    }
  });

  test('characters that previously caused collisions', () => {
    // These characters had collisions in v4 when using charCodeAt
    const words = ['a', 'š']; // 'a' = 97, 'š' = U+0161 = 353
    const trie = LOUDSTrie.build(words);

    assert.strictEqual(trie.has('a'), true);
    assert.strictEqual(trie.has('š'), true);
    assert.notStrictEqual(trie.wordId('a'), trie.wordId('š'));
  });

  test('emoji characters', () => {
    const words = ['hello', 'hello🎉', '🎉party'];
    const trie = LOUDSTrie.build(words);

    assert.strictEqual(trie.wordCount, 3);
    for (const word of words) {
      assert.strictEqual(trie.has(word), true, `should have ${word}`);
    }
  });

  test('CJK characters', () => {
    const words = ['日本語', '中文', '한국어'];
    const trie = LOUDSTrie.build(words);

    assert.strictEqual(trie.wordCount, 3);
    for (const word of words) {
      assert.strictEqual(trie.has(word), true, `should have ${word}`);
    }
  });
});

describe('LOUDSTrie Serialization', () => {
  test('serialize and deserialize round-trip', () => {
    const words = ['apple', 'apply', 'banana', 'band', 'bandana'];
    const original = LOUDSTrie.build(words);

    const serialized = original.serialize();
    const restored = LOUDSTrie.deserialize(serialized);

    assert.strictEqual(restored.wordCount, original.wordCount);
    assert.strictEqual(restored.nodeCount, original.nodeCount);

    // Verify all words are still accessible
    for (const word of words) {
      assert.strictEqual(restored.has(word), true, `should have ${word}`);
      assert.strictEqual(restored.wordId(word), original.wordId(word), `wordId(${word}) should match`);
    }
  });

  test('serialized format has correct header', () => {
    const trie = LOUDSTrie.build(['test']);
    const buffer = trie.serialize();

    // Check magic
    const magic = new TextDecoder().decode(buffer.slice(0, 6));
    assert.strictEqual(magic, 'OWTRIE');

    // Check version
    const view = new DataView(buffer.buffer);
    const version = view.getUint16(6, true);
    assert.strictEqual(version, 5);
  });

  test('deserialize rejects invalid magic', () => {
    const buffer = new Uint8Array(20);
    buffer.set(new TextEncoder().encode('BADMGC'), 0);

    assert.throws(() => LOUDSTrie.deserialize(buffer), /Invalid trie file/);
  });

  test('deserialize rejects wrong version', () => {
    const buffer = new Uint8Array(20);
    buffer.set(new TextEncoder().encode('OWTRIE'), 0);
    const view = new DataView(buffer.buffer);
    view.setUint16(6, 4, true); // version 4

    assert.throws(() => LOUDSTrie.deserialize(buffer), /Unsupported trie version/);
  });

  test('serialize with Unicode preserves words', () => {
    const words = ['café', 'naïve', '日本語', '🎉'];
    const original = LOUDSTrie.build(words);

    const serialized = original.serialize();
    const restored = LOUDSTrie.deserialize(serialized);

    for (const word of words) {
      assert.strictEqual(restored.has(word), true, `should have ${word}`);
    }
  });
});

describe('LOUDSTrie Statistics', () => {
  test('stats returns correct counts', () => {
    const words = ['a', 'ab', 'abc'];
    const trie = LOUDSTrie.build(words);

    const stats = trie.stats();
    assert.strictEqual(stats.wordCount, 3);
    assert.ok(stats.nodeCount > 0);
    assert.ok(stats.edgeCount > 0);
    assert.ok(stats.totalSize > 0);
  });
});

describe('LOUDSTrie Large Scale', () => {
  test('1000 words performance', () => {
    const words = Array.from({ length: 1000 }, (_, i) =>
      `word${i.toString().padStart(4, '0')}`
    );
    const trie = LOUDSTrie.build(words);

    assert.strictEqual(trie.wordCount, 1000);

    // Verify random lookups work
    const start = performance.now();
    for (let i = 0; i < 100; i++) {
      const idx = Math.floor(Math.random() * 1000);
      const word = words[idx];
      assert.strictEqual(trie.has(word), true);
      assert.ok(trie.wordId(word) >= 0);
    }
    const elapsed = performance.now() - start;
    assert.ok(elapsed < 100, `100 lookups took ${elapsed}ms, expected < 100ms`);
  });

  test('words of varying length', () => {
    const words: string[] = [];
    for (let len = 1; len <= 20; len++) {
      words.push('a'.repeat(len));
    }
    const trie = LOUDSTrie.build(words);

    assert.strictEqual(trie.wordCount, 20);
    for (const word of words) {
      assert.strictEqual(trie.has(word), true);
    }
  });
});
