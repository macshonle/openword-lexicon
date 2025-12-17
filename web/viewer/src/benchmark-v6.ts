#!/usr/bin/env node
/**
 * benchmark-v6.ts - Benchmark OWTRIE format comparisons
 *
 * Compares build time, binary size, and lookup performance across formats.
 *
 * Usage:
 *   pnpm benchmark [input]
 *
 * Examples:
 *   # Benchmark with default input (pipeline JSONL)
 *   pnpm benchmark
 *
 *   # Benchmark with custom wordlist
 *   pnpm benchmark wordlist.txt
 */

import * as fs from 'fs';
import * as path from 'path';
import { buildDAWG, LOUDSTrie, MarisaTrie } from './trie/index.js';

const DEFAULT_INPUT = '../../data/intermediate/en-wikt-v2-enriched.jsonl';

interface BenchResult {
  format: string;
  version: number;
  wordCount: number;
  nodeCount: number;
  binarySize: number;
  bytesPerWord: number;
  buildTimeMs: number;
  lookupAvgUs: number;
  prefixAvgUs: number;
}

/**
 * Load words from a file.
 */
function loadWords(inputPath: string): string[] {
  const ext = path.extname(inputPath).toLowerCase();
  const content = fs.readFileSync(inputPath, 'utf-8');

  if (ext === '.jsonl') {
    const words: string[] = [];
    const lines = content.trim().split('\n');
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const obj = JSON.parse(line);
        if (obj.lemma && typeof obj.lemma === 'string') {
          const word = obj.lemma.trim();
          if (word.length > 0) {
            words.push(word);
          }
        }
      } catch {
        // Skip invalid JSON
      }
    }
    return words;
  } else {
    return content.trim().split('\n').filter(w => w.trim().length > 0).map(w => w.trim());
  }
}

/**
 * Benchmark lookup performance.
 */
function benchmarkLookups(
  lookupFn: (word: string) => boolean,
  words: string[],
  iterations: number = 1000
): number {
  // Sample words for lookup
  const sampleSize = Math.min(iterations, words.length);
  const sampleWords: string[] = [];
  for (let i = 0; i < sampleSize; i++) {
    sampleWords.push(words[Math.floor(Math.random() * words.length)]);
  }

  // Add some non-words
  const nonWords = sampleWords.map(w => w + 'xyz');

  const allWords = [...sampleWords, ...nonWords];

  const start = performance.now();
  for (const word of allWords) {
    lookupFn(word);
  }
  const elapsed = performance.now() - start;

  return (elapsed * 1000) / allWords.length; // microseconds per lookup
}

/**
 * Benchmark prefix search performance.
 */
function benchmarkPrefixSearch(
  prefixFn: (prefix: string, limit: number) => string[],
  words: string[],
  iterations: number = 100
): number {
  // Generate prefix samples (2-4 characters)
  const prefixes: string[] = [];
  for (let i = 0; i < iterations; i++) {
    const word = words[Math.floor(Math.random() * words.length)];
    const prefixLen = Math.min(word.length, 2 + Math.floor(Math.random() * 3));
    prefixes.push(word.slice(0, prefixLen));
  }

  const start = performance.now();
  for (const prefix of prefixes) {
    prefixFn(prefix, 10);
  }
  const elapsed = performance.now() - start;

  return (elapsed * 1000) / prefixes.length; // microseconds per search
}

/**
 * Run benchmarks for a format.
 */
function benchmark(
  name: string,
  version: number,
  words: string[],
  buildFn: () => { nodeCount: number; serialize: () => Uint8Array; has: (w: string) => boolean; keysWithPrefix: (p: string, l: number) => string[] }
): BenchResult {
  // Build
  const buildStart = performance.now();
  const trie = buildFn();
  const buildTimeMs = performance.now() - buildStart;

  // Size
  const binary = trie.serialize();
  const binarySize = binary.length;
  const bytesPerWord = binarySize / words.length;

  // Lookups
  const lookupAvgUs = benchmarkLookups(w => trie.has(w), words);

  // Prefix search
  const prefixAvgUs = benchmarkPrefixSearch((p, l) => trie.keysWithPrefix(p, l), words);

  return {
    format: name,
    version,
    wordCount: words.length,
    nodeCount: trie.nodeCount,
    binarySize,
    bytesPerWord,
    buildTimeMs,
    lookupAvgUs,
    prefixAvgUs,
  };
}

/**
 * Format a number with commas.
 */
function fmt(n: number): string {
  return n.toLocaleString();
}

/**
 * Format bytes as human-readable.
 */
function fmtBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

/**
 * Print benchmark results as a table.
 */
function printResults(results: BenchResult[], inputSize: number): void {
  console.log('\n' + '='.repeat(90));
  console.log('BENCHMARK RESULTS');
  console.log('='.repeat(90));
  console.log(`Input: ${fmt(results[0].wordCount)} words (${fmtBytes(inputSize)})`);
  console.log();

  // Header
  console.log(
    'Format'.padEnd(12) +
    'Version'.padEnd(10) +
    'Nodes'.padEnd(12) +
    'Size'.padEnd(12) +
    'B/word'.padEnd(10) +
    'Build'.padEnd(12) +
    'Lookup'.padEnd(12) +
    'Prefix'
  );
  console.log('-'.repeat(90));

  // Data rows
  for (const r of results) {
    console.log(
      r.format.padEnd(12) +
      `v${r.version}`.padEnd(10) +
      fmt(r.nodeCount).padEnd(12) +
      fmtBytes(r.binarySize).padEnd(12) +
      r.bytesPerWord.toFixed(2).padEnd(10) +
      `${r.buildTimeMs.toFixed(0)}ms`.padEnd(12) +
      `${r.lookupAvgUs.toFixed(2)}µs`.padEnd(12) +
      `${r.prefixAvgUs.toFixed(1)}µs`
    );
  }

  console.log('='.repeat(90));

  // Size comparison
  const baseline = results.find(r => r.format === 'v5 LOUDS');
  if (baseline) {
    console.log('\nSize comparison (vs v5 LOUDS baseline):');
    for (const r of results) {
      const ratio = r.binarySize / baseline.binarySize;
      const savings = ((1 - ratio) * 100).toFixed(1);
      const sign = ratio <= 1 ? '' : '+';
      console.log(`  ${r.format.padEnd(12)} ${sign}${savings}%`);
    }
  }
}

async function main() {
  const inputPath = process.argv[2] || DEFAULT_INPUT;

  console.log('OWTRIE Format Benchmark');
  console.log('=======================\n');

  if (!fs.existsSync(inputPath)) {
    console.error(`Error: Input file not found: ${inputPath}`);
    console.error('\nRun "make enrich" to generate the input file.');
    process.exit(1);
  }

  console.log(`Loading words from: ${inputPath}`);
  const words = loadWords(inputPath);
  console.log(`Loaded ${fmt(words.length)} words\n`);

  if (words.length === 0) {
    console.error('Error: No words found in input');
    process.exit(1);
  }

  const inputSize = fs.statSync(inputPath).size;
  const results: BenchResult[] = [];

  // Check if we can use v4 (may fail on large datasets due to node limit)
  console.log('Running benchmarks...\n');

  // v4 DAWG
  try {
    console.log('  v4 DAWG...');
    const r = benchmark('v4 DAWG', 4, words, () => {
      const result = buildDAWG(words, 'v4');
      return {
        nodeCount: result.nodeCount,
        serialize: () => result.buffer,
        has: () => { throw new Error('v4 has() requires loading'); },
        keysWithPrefix: () => { throw new Error('v4 prefix search not implemented'); },
      };
    });
    // v4 doesn't support runtime lookups from buffer, so skip lookup benchmarks
    r.lookupAvgUs = NaN;
    r.prefixAvgUs = NaN;
    results.push(r);
  } catch (e) {
    console.log('  v4 DAWG: skipped (too many nodes or other error)');
  }

  // v5 LOUDS
  console.log('  v5 LOUDS...');
  results.push(benchmark('v5 LOUDS', 5, words, () => {
    const trie = LOUDSTrie.build(words);
    return {
      nodeCount: trie.nodeCount,
      serialize: () => trie.serialize(),
      has: (w) => trie.has(w),
      keysWithPrefix: (p, l) => trie.keysWithPrefix(p, l),
    };
  }));

  // v6.0 MARISA (no links)
  console.log('  v6.0 MARISA (baseline)...');
  results.push(benchmark('v6.0 MARISA', 6, words, () => {
    const { trie } = MarisaTrie.build(words);
    return {
      nodeCount: trie.nodeCount,
      serialize: () => trie.serialize(),
      has: (w) => trie.has(w),
      keysWithPrefix: (p, l) => trie.keysWithPrefix(p, l),
    };
  }));

  // v6.1 MARISA (with path compression)
  console.log('  v6.1 MARISA (path compression)...');
  results.push(benchmark('v6.1 MARISA', 6, words, () => {
    const { trie } = MarisaTrie.build(words, { enableLinks: true });
    return {
      nodeCount: trie.nodeCount,
      serialize: () => trie.serialize(),
      has: (w) => trie.has(w),
      keysWithPrefix: (p, l) => trie.keysWithPrefix(p, l),
    };
  }));

  // v6.3 MARISA (recursive tail trie)
  console.log('  v6.3 MARISA (recursive tails)...');
  results.push(benchmark('v6.3 MARISA', 6, words, () => {
    const { trie } = MarisaTrie.build(words, { enableLinks: true, enableRecursive: true });
    return {
      nodeCount: trie.nodeCount,
      serialize: () => trie.serialize(),
      has: (w) => trie.has(w),
      keysWithPrefix: (p, l) => trie.keysWithPrefix(p, l),
    };
  }));

  printResults(results, inputSize);

  // Summary
  console.log('\nNotes:');
  console.log('  - v4 DAWG: No runtime lookup support (build-only format)');
  console.log('  - v5 LOUDS: Baseline format with word ID mapping');
  console.log('  - v6.0 MARISA: Same as v5 with v6 header (baseline for MARISA features)');
  console.log('  - v6.1 MARISA: Path compression (single-child chains collapsed into tails)');
  console.log('  - v6.3 MARISA: Recursive trie over tails (prefix sharing within tails)');
}

main().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
