/**
 * marisa.test.ts - Tests for MARISA trie (OWTRIE v7/v8)
 *
 * Tests verify:
 * 1. Building trie from word list
 * 2. Word membership (has)
 * 3. Word ID mapping (sequential IDs in BFS order)
 * 4. Prefix search (keysWithPrefix)
 * 5. Common prefix search (commonPrefixes)
 * 6. Unicode handling
 * 7. Serialization round-trip
 * 8. Path compression with recursive tails
 */

import { describe, test } from 'node:test';
import * as assert from 'node:assert';
import { MarisaTrie } from './marisa.js';

describe('MarisaTrie Construction', () => {
  test('empty word list', () => {
    const { trie } = MarisaTrie.build([]);
    assert.strictEqual(trie.wordCount, 0);
  });

  test('single word', () => {
    const { trie } = MarisaTrie.build(['hello']);
    assert.strictEqual(trie.wordCount, 1);
    assert.strictEqual(trie.has('hello'), true);
    assert.strictEqual(trie.has('hell'), false);
    assert.strictEqual(trie.has('hello!'), false);
  });

  test('multiple words with shared prefix', () => {
    const { trie } = MarisaTrie.build(['ant', 'ante', 'anti']);
    assert.strictEqual(trie.wordCount, 3);
    assert.strictEqual(trie.has('ant'), true);
    assert.strictEqual(trie.has('ante'), true);
    assert.strictEqual(trie.has('anti'), true);
    assert.strictEqual(trie.has('an'), false);
    assert.strictEqual(trie.has('antler'), false);
  });

  test('words with no shared prefix', () => {
    const { trie } = MarisaTrie.build(['apple', 'banana', 'cherry']);
    assert.strictEqual(trie.wordCount, 3);
    assert.strictEqual(trie.has('apple'), true);
    assert.strictEqual(trie.has('banana'), true);
    assert.strictEqual(trie.has('cherry'), true);
    assert.strictEqual(trie.has('apricot'), false);
  });

  test('single character words', () => {
    const { trie } = MarisaTrie.build(['a', 'b', 'c']);
    assert.strictEqual(trie.wordCount, 3);
    assert.strictEqual(trie.has('a'), true);
    assert.strictEqual(trie.has('b'), true);
    assert.strictEqual(trie.has('c'), true);
    assert.strictEqual(trie.has('d'), false);
  });

  test('all words are prefixes of each other', () => {
    const { trie } = MarisaTrie.build(['a', 'ab', 'abc', 'abcd', 'abcde']);
    assert.strictEqual(trie.wordCount, 5);
    for (const word of ['a', 'ab', 'abc', 'abcd', 'abcde']) {
      assert.strictEqual(trie.has(word), true, `should have ${word}`);
    }
    assert.strictEqual(trie.has('abcdef'), false);
    assert.strictEqual(trie.has(''), false);
  });
});

describe('MarisaTrie Word Lookup', () => {
  test('has returns true for existing words', () => {
    const { trie } = MarisaTrie.build(['cat', 'car', 'card', 'care', 'careful']);
    assert.strictEqual(trie.has('cat'), true);
    assert.strictEqual(trie.has('car'), true);
    assert.strictEqual(trie.has('card'), true);
    assert.strictEqual(trie.has('care'), true);
    assert.strictEqual(trie.has('careful'), true);
  });

  test('has returns false for non-existing words', () => {
    const { trie } = MarisaTrie.build(['cat', 'car', 'card', 'care', 'careful']);
    assert.strictEqual(trie.has('ca'), false); // prefix only
    assert.strictEqual(trie.has('cart'), false); // not in list
    assert.strictEqual(trie.has('dog'), false); // completely different
    assert.strictEqual(trie.has(''), false); // empty string
  });

  test('case sensitivity', () => {
    const { trie } = MarisaTrie.build(['Hello', 'HELLO', 'hello']);
    assert.strictEqual(trie.wordCount, 3);
    assert.strictEqual(trie.has('Hello'), true);
    assert.strictEqual(trie.has('HELLO'), true);
    assert.strictEqual(trie.has('hello'), true);
    assert.strictEqual(trie.has('hElLo'), false);
  });
});

describe('MarisaTrie Word IDs', () => {
  test('wordId returns sequential IDs', () => {
    const words = ['ant', 'ante', 'anti'];
    const { trie } = MarisaTrie.build(words);

    const id0 = trie.wordId('ant');
    const id1 = trie.wordId('ante');
    const id2 = trie.wordId('anti');

    const ids = [id0, id1, id2];
    assert.ok(ids.every((id) => id >= 0 && id < 3), 'IDs should be in range');
    assert.strictEqual(new Set(ids).size, 3, 'IDs should be unique');
  });

  test('wordId returns -1 for non-existing words', () => {
    const { trie } = MarisaTrie.build(['cat', 'car', 'card']);
    assert.strictEqual(trie.wordId('ca'), -1);
    assert.strictEqual(trie.wordId('dog'), -1);
    assert.strictEqual(trie.wordId(''), -1);
  });

  test('wordId consistency with has', () => {
    const words = ['apple', 'apply', 'banana', 'band', 'bandana'];
    const { trie } = MarisaTrie.build(words);

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
    const { trie } = MarisaTrie.build(words);

    const ids = words.map((w) => trie.wordId(w));
    ids.sort((a, b) => a - b);

    for (let i = 0; i < words.length; i++) {
      assert.ok(ids.includes(i), `ID ${i} should be present`);
    }
  });
});

describe('MarisaTrie Prefix Search', () => {
  test('keysWithPrefix returns matching words', () => {
    const { trie } = MarisaTrie.build(['cat', 'car', 'card', 'care', 'careful', 'dog']);

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
    const { trie } = MarisaTrie.build(words);

    const all = trie.keysWithPrefix('');
    assert.strictEqual(all.length, 3);
  });

  test('keysWithPrefix with non-matching prefix returns empty', () => {
    const { trie } = MarisaTrie.build(['apple', 'banana']);

    const result = trie.keysWithPrefix('xyz');
    assert.strictEqual(result.length, 0);
  });

  test('keysWithPrefix respects limit', () => {
    const words = Array.from({ length: 100 }, (_, i) => `word${i.toString().padStart(3, '0')}`);
    const { trie } = MarisaTrie.build(words);

    const limited = trie.keysWithPrefix('word', 10);
    assert.strictEqual(limited.length, 10);
  });

  test('keysWithPrefix with exact match', () => {
    const { trie } = MarisaTrie.build(['cat', 'cats', 'caterpillar']);

    const result = trie.keysWithPrefix('cat');
    assert.ok(result.includes('cat'));
    assert.ok(result.includes('cats'));
    assert.ok(result.includes('caterpillar'));
  });
});

describe('MarisaTrie Common Prefix Search', () => {
  test('commonPrefixes finds all prefix words', () => {
    const { trie } = MarisaTrie.build(['a', 'ab', 'abc', 'abcd', 'xyz']);

    const prefixes = trie.commonPrefixes('abcdef');
    const words = prefixes.map(([w]) => w);

    assert.ok(words.includes('a'));
    assert.ok(words.includes('ab'));
    assert.ok(words.includes('abc'));
    assert.ok(words.includes('abcd'));
    assert.strictEqual(words.includes('xyz'), false);
  });

  test('commonPrefixes returns empty for no matches', () => {
    const { trie } = MarisaTrie.build(['cat', 'dog']);

    const prefixes = trie.commonPrefixes('xyz');
    assert.strictEqual(prefixes.length, 0);
  });

  test('commonPrefixes with partial match', () => {
    const { trie } = MarisaTrie.build(['car', 'card', 'care']);

    const prefixes = trie.commonPrefixes('card');
    const words = prefixes.map(([w]) => w);

    assert.ok(words.includes('car'));
    assert.ok(words.includes('card'));
    assert.strictEqual(words.includes('care'), false);
  });

  test('commonPrefixes returns word IDs', () => {
    const { trie } = MarisaTrie.build(['a', 'ab', 'abc']);

    const prefixes = trie.commonPrefixes('abcd');

    for (const [word, wordId] of prefixes) {
      assert.strictEqual(trie.wordId(word), wordId, `wordId for ${word} should match`);
    }
  });
});

describe('MarisaTrie Unicode', () => {
  test('extended Latin characters', () => {
    const words = ['café', 'naïve', 'résumé', 'Zürich'];
    const { trie } = MarisaTrie.build(words);

    assert.strictEqual(trie.wordCount, 4);
    for (const word of words) {
      assert.strictEqual(trie.has(word), true, `should have ${word}`);
    }
  });

  test('characters that previously caused collisions', () => {
    const words = ['a', 'š']; // 'a' = 97, 'š' = U+0161 = 353
    const { trie } = MarisaTrie.build(words);

    assert.strictEqual(trie.has('a'), true);
    assert.strictEqual(trie.has('š'), true);
    assert.notStrictEqual(trie.wordId('a'), trie.wordId('š'));
  });

  test('emoji characters', () => {
    const words = ['hello', 'hello🎉', '🎉party'];
    const { trie } = MarisaTrie.build(words);

    assert.strictEqual(trie.wordCount, 3);
    for (const word of words) {
      assert.strictEqual(trie.has(word), true, `should have ${word}`);
    }
  });

  test('CJK characters', () => {
    const words = ['日本語', '中文', '한국어'];
    const { trie } = MarisaTrie.build(words);

    assert.strictEqual(trie.wordCount, 3);
    for (const word of words) {
      assert.strictEqual(trie.has(word), true, `should have ${word}`);
    }
  });
});

describe('MarisaTrie Serialization', () => {
  test('serialize and deserialize round-trip', () => {
    const words = ['apple', 'apply', 'banana', 'band', 'bandana'];
    const { trie: original } = MarisaTrie.build(words);

    const serialized = original.serialize();
    const restored = MarisaTrie.deserialize(serialized);

    assert.strictEqual(restored.wordCount, original.wordCount);
    assert.strictEqual(restored.nodeCount, original.nodeCount);

    for (const word of words) {
      assert.strictEqual(restored.has(word), true, `should have ${word}`);
      assert.strictEqual(restored.wordId(word), original.wordId(word), `wordId(${word}) should match`);
    }
  });

  test('serialized format has correct header', () => {
    const { trie } = MarisaTrie.build(['test']);
    const buffer = trie.serialize();

    const magic = new TextDecoder().decode(buffer.slice(0, 6));
    assert.strictEqual(magic, 'OWTRIE');

    const view = new DataView(buffer.buffer);
    const version = view.getUint16(6, true);
    assert.strictEqual(version, 7);
  });

  test('deserialize rejects invalid magic', () => {
    const buffer = new Uint8Array(30);
    buffer.set(new TextEncoder().encode('BADMGC'), 0);

    assert.throws(() => MarisaTrie.deserialize(buffer), /Invalid trie file/);
  });

  test('deserialize rejects wrong version', () => {
    const buffer = new Uint8Array(30);
    buffer.set(new TextEncoder().encode('OWTRIE'), 0);
    const view = new DataView(buffer.buffer);
    view.setUint16(6, 6, true); // version 6 (unsupported)

    assert.throws(() => MarisaTrie.deserialize(buffer), /Unsupported trie version/);
  });

  test('serialize with Unicode preserves words', () => {
    const words = ['café', 'naïve', '日本語', '🎉'];
    const { trie: original } = MarisaTrie.build(words);

    const serialized = original.serialize();
    const restored = MarisaTrie.deserialize(serialized);

    for (const word of words) {
      assert.strictEqual(restored.has(word), true, `should have ${word}`);
    }
  });
});

describe('MarisaTrie Statistics', () => {
  test('stats returns correct counts', () => {
    const words = ['a', 'ab', 'abc'];
    const { trie, stats } = MarisaTrie.build(words);

    assert.strictEqual(stats.wordCount, 3);
    assert.ok(stats.nodeCount > 0);
    assert.ok(stats.edgeCount > 0);
    assert.ok(stats.totalSize > 0);

    const stats2 = trie.stats();
    assert.deepStrictEqual(stats, stats2);
  });

  test('getStats returns expected format', () => {
    const { trie } = MarisaTrie.build(['test', 'testing', 'tested']);
    const stats = trie.getStats();

    assert.strictEqual(stats.wordCount, 3);
    assert.ok(stats.nodeCount > 0);
    assert.ok(stats.sizeBytes > 0);
    assert.ok(typeof stats.bytesPerWord === 'string');
  });
});

describe('MarisaTrie Path Compression', () => {
  test('builds with path compression', () => {
    const words = ['a', 'apple', 'banana'];
    const { trie } = MarisaTrie.build(words);

    assert.strictEqual(trie.wordCount, 3);
    for (const word of words) {
      assert.strictEqual(trie.has(word), true, `should have ${word}`);
    }
  });

  test('compresses single-child chains', () => {
    // "abc" should compress the "bc" part since "a" is a terminal
    const words = ['a', 'abc'];
    const { trie, stats } = MarisaTrie.build(words);

    assert.strictEqual(trie.wordCount, 2);
    assert.strictEqual(trie.has('a'), true);
    assert.strictEqual(trie.has('abc'), true);
    assert.strictEqual(trie.has('ab'), false);

    // With path compression, should have tail trie
    assert.ok(stats.tailBufferSize > 0, 'should have tail buffer (recursive trie)');
  });

  test('preserves terminals during compression', () => {
    // Important: don't compress through terminals
    const words = ['a', 'ab', 'abc'];
    const { trie } = MarisaTrie.build(words);

    assert.strictEqual(trie.wordCount, 3);
    for (const word of words) {
      assert.strictEqual(trie.has(word), true, `should have ${word}`);
    }
  });

  test('round-trip with path compression', () => {
    const words = ['apple', 'application', 'banana', 'bandana'];
    const { trie: original } = MarisaTrie.build(words);

    const serialized = original.serialize();
    const restored = MarisaTrie.deserialize(serialized);

    for (const word of words) {
      assert.strictEqual(restored.has(word), true, `should have ${word}`);
      assert.strictEqual(restored.wordId(word), original.wordId(word), `wordId(${word}) should match`);
    }
  });

  test('prefix search with compressed edges', () => {
    const words = ['apple', 'application', 'apply'];
    const { trie } = MarisaTrie.build(words);

    const results = trie.keysWithPrefix('app');
    assert.strictEqual(results.length, 3);
    assert.ok(results.includes('apple'));
    assert.ok(results.includes('application'));
    assert.ok(results.includes('apply'));
  });

  test('common prefixes with compressed edges', () => {
    const words = ['a', 'app', 'apple', 'application'];
    const { trie } = MarisaTrie.build(words);

    const prefixes = trie.commonPrefixes('application');
    const found = prefixes.map(([w]) => w);

    assert.ok(found.includes('a'));
    assert.ok(found.includes('app'));
    assert.ok(found.includes('application'));
    // 'apple' is NOT a prefix of 'application'
    assert.strictEqual(found.includes('apple'), false);
  });
});

describe('MarisaTrie Large Scale', () => {
  test('1000 words performance', () => {
    const words = Array.from({ length: 1000 }, (_, i) =>
      `word${i.toString().padStart(4, '0')}`
    );
    const { trie } = MarisaTrie.build(words);

    assert.strictEqual(trie.wordCount, 1000);

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
    const { trie } = MarisaTrie.build(words);

    assert.strictEqual(trie.wordCount, 20);
    for (const word of words) {
      assert.strictEqual(trie.has(word), true);
    }
  });

  test('1000 words with path compression', () => {
    const words = Array.from({ length: 1000 }, (_, i) =>
      `word${i.toString().padStart(4, '0')}`
    );
    const { trie } = MarisaTrie.build(words);

    assert.strictEqual(trie.wordCount, 1000);

    for (let i = 0; i < 100; i++) {
      const idx = Math.floor(Math.random() * 1000);
      const word = words[idx];
      assert.strictEqual(trie.has(word), true);
    }
  });
});

describe('MarisaTrie Recursive Tails', () => {
  test('builds with recursive tails', () => {
    const words = ['application', 'approbation', 'station', 'nation'];
    const { trie } = MarisaTrie.build(words);

    assert.strictEqual(trie.wordCount, 4);
    assert.ok(trie.tailTrie, 'should have tail trie');
  });

  test('recursive tails has() works correctly', () => {
    const words = ['apple', 'application', 'approbation', 'banana', 'bandana'];
    const { trie } = MarisaTrie.build(words);

    for (const word of words) {
      assert.strictEqual(trie.has(word), true, `should have ${word}`);
    }

    assert.strictEqual(trie.has('app'), false);
    assert.strictEqual(trie.has('applying'), false);
  });

  test('recursive tails wordId works correctly', () => {
    const words = ['apple', 'application', 'approbation'];
    const { trie } = MarisaTrie.build(words);

    for (let i = 0; i < words.length; i++) {
      const id = trie.wordId(words[i]);
      assert.ok(id >= 0, `wordId for ${words[i]} should be valid`);
    }

    assert.strictEqual(trie.wordId('notaword'), -1);
  });

  test('recursive tails round-trip serialization', () => {
    const words = ['application', 'approbation', 'station', 'nation', 'relation'];
    const { trie: original } = MarisaTrie.build(words);

    const serialized = original.serialize();
    const restored = MarisaTrie.deserialize(serialized);

    assert.ok(restored.tailTrie, 'restored should have tail trie');
    assert.strictEqual(restored.wordCount, original.wordCount);

    for (const word of words) {
      assert.strictEqual(restored.has(word), true, `restored should have ${word}`);
      assert.strictEqual(restored.wordId(word), original.wordId(word), `wordId should match for ${word}`);
    }
  });

  test('recursive tails prefix search', () => {
    const words = ['apple', 'application', 'approbation', 'apply'];
    const { trie } = MarisaTrie.build(words);

    const results = trie.keysWithPrefix('app');
    assert.strictEqual(results.length, 4);
    for (const word of words) {
      assert.ok(results.includes(word), `should include ${word}`);
    }
  });

  test('recursive tails common prefixes', () => {
    const words = ['a', 'app', 'apple', 'application'];
    const { trie } = MarisaTrie.build(words);

    const prefixes = trie.commonPrefixes('application');
    const found = prefixes.map(([w]) => w);

    assert.ok(found.includes('a'));
    assert.ok(found.includes('app'));
    assert.ok(found.includes('application'));
  });

  test('recursive tails getWord method', () => {
    const words = ['apple', 'apply', 'banana'];
    const { trie } = MarisaTrie.build(words);

    // getWord should return words by their ID
    const foundWords = new Set<string>();
    for (let i = 0; i < words.length; i++) {
      const word = trie.getWord(i);
      assert.ok(word !== null, `getWord(${i}) should not return null`);
      foundWords.add(word!);
    }

    // All original words should be found
    for (const word of words) {
      assert.ok(foundWords.has(word), `should find ${word} via getWord`);
    }

    // Out of range should return null
    assert.strictEqual(trie.getWord(-1), null);
    assert.strictEqual(trie.getWord(words.length), null);
  });
});
