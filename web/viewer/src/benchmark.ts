#!/usr/bin/env node
/**
 * benchmark.ts - Benchmark OWTRIE format comparisons
 *
 * Compares build time, binary size, and lookup performance for v7/v8 formats.
 * Uses owlex (OpenWord Lexicon Extended) to generate word lists from YAML specs.
 *
 * Usage:
 *   pnpm benchmark [options] [input]
 *
 * Options:
 *   --all          Run all predefined datasets (Wordle, word-only, full)
 *   --wordle       Run only Wordle 5-letter words (~3K words)
 *   --word-only    Run only word-only entries (~1.2M words)
 *   --full         Run only full Wiktionary (~1.3M words, default)
 *   --json         Output results as JSON (for comparison with Python benchmark)
 *   --breakdown    Show detailed size breakdown
 *   --validate     Perform round-trip validation (build → serialize → deserialize → enumerate)
 *
 * Examples:
 *   # Benchmark all three datasets
 *   pnpm benchmark --all
 *
 *   # Benchmark only Wordle words
 *   pnpm benchmark --wordle
 *
 *   # Benchmark with custom wordlist
 *   pnpm benchmark wordlist.txt
 */

import * as fs from 'fs';
import * as path from 'path';
import { execSync } from 'child_process';
import { MarisaTrie, initBrotliNode } from './trie/index.js';
import type { MarisaDetailedStats, MarisaMemoryStats } from './trie/index.js';

const PROJECT_ROOT = path.resolve(import.meta.dirname, '..', '..', '..');

interface DatasetConfig {
  name: string;
  description: string;
  specFile: string;
}

// Datasets use owlex spec files for filtering
const DATASETS: Record<string, DatasetConfig> = {
  wordle: {
    name: 'Wordle 5-letter',
    description: '5-letter common words (no vulgar/offensive)',
    specFile: 'examples/wordlist-specs/wordle.yaml',
  },
  'word-only': {
    name: 'Word-only',
    description: 'All words (no phrases, proper nouns, idioms)',
    specFile: 'examples/wordlist-specs/word-only.yaml',
  },
  full: {
    name: 'Full Wiktionary',
    description: 'All entries (includes phrases)',
    specFile: 'examples/wordlist-specs/full.yaml',
  },
};

interface RoundTripResult {
  passed: boolean;
  originalCount: number;
  roundTripCount: number;
  missingWords: string[];
  extraWords: string[];
}

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
  detailedStats?: MarisaDetailedStats;
  memoryStats?: MarisaMemoryStats;
  roundTrip?: RoundTripResult;
}

interface DatasetResults {
  dataset: DatasetConfig;
  words: string[];
  results: BenchResult[];
}

/**
 * Load words using owlex with a spec file.
 * Returns unique, sorted words.
 */
function loadWordsFromSpec(specFile: string, quiet: boolean = false): string[] {
  const specPath = path.join(PROJECT_ROOT, specFile);
  if (!fs.existsSync(specPath)) {
    throw new Error(`Spec file not found: ${specPath}`);
  }

  if (!quiet) console.log(`  Running owlex ${specFile}...`);
  const output = execSync(`uv run owlex "${specPath}"`, {
    cwd: PROJECT_ROOT,
    encoding: 'utf-8',
    maxBuffer: 100 * 1024 * 1024,  // 100MB buffer for large outputs
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  // Deduplicate and sort
  const words = output.trim().split('\n').filter(w => w.length > 0);
  const unique = [...new Set(words)].sort();
  return unique;
}

/**
 * Load words from a plain text file.
 */
function loadWordsFromFile(filePath: string): string[] {
  const content = fs.readFileSync(filePath, 'utf-8');
  const words = content.trim().split('\n').filter(w => w.trim().length > 0).map(w => w.trim());
  return [...new Set(words)].sort();
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
 * Perform round-trip validation: build → serialize → deserialize → enumerate → compare.
 */
function validateRoundTrip(
  originalWords: string[],
  serialize: () => Uint8Array,
  deserialize: (buffer: Uint8Array) => { getWord: (id: number) => string | null; wordCount: number },
): RoundTripResult {
  // Serialize and deserialize
  const buffer = serialize();
  const trie = deserialize(buffer);

  // Enumerate all words from the deserialized trie
  const roundTripWords: string[] = [];
  for (let i = 0; i < trie.wordCount; i++) {
    const word = trie.getWord(i);
    if (word !== null) {
      roundTripWords.push(word);
    }
  }

  // Sort for comparison
  const sortedOriginal = [...originalWords].sort();
  const sortedRoundTrip = [...roundTripWords].sort();

  // Find differences
  const originalSet = new Set(sortedOriginal);
  const roundTripSet = new Set(sortedRoundTrip);

  const missingWords = sortedOriginal.filter(w => !roundTripSet.has(w)).slice(0, 10);
  const extraWords = sortedRoundTrip.filter(w => !originalSet.has(w)).slice(0, 10);

  const passed = sortedOriginal.length === sortedRoundTrip.length &&
    missingWords.length === 0 && extraWords.length === 0;

  return {
    passed,
    originalCount: sortedOriginal.length,
    roundTripCount: sortedRoundTrip.length,
    missingWords,
    extraWords,
  };
}

/**
 * Run benchmarks for a format.
 */
function benchmark(
  name: string,
  version: number,
  words: string[],
  buildFn: () => {
    nodeCount: number;
    serialize: () => Uint8Array;
    has: (w: string) => boolean;
    keysWithPrefix: (p: string, l: number) => string[];
    detailedStats?: () => MarisaDetailedStats;
    memoryStats?: (serializedSize?: number) => MarisaMemoryStats;
    getWord?: (id: number) => string | null;
    wordCount?: number;
  },
  options?: {
    validateRoundTrip?: boolean;
    deserialize?: (buffer: Uint8Array) => { getWord: (id: number) => string | null; wordCount: number };
  }
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

  // Detailed stats (for MARISA tries)
  const detailedStats = trie.detailedStats?.();

  // Memory stats (for MARISA tries)
  const memoryStats = trie.memoryStats?.(binarySize);

  // Round-trip validation
  let roundTrip: RoundTripResult | undefined;
  if (options?.validateRoundTrip && options.deserialize) {
    roundTrip = validateRoundTrip(words, trie.serialize, options.deserialize);
  }

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
    detailedStats,
    memoryStats,
    roundTrip,
  };
}

interface BenchmarkOptions {
  quiet?: boolean;
  validateRoundTrip?: boolean;
}

/**
 * Run all format benchmarks for a word list.
 */
function runBenchmarks(words: string[], options: BenchmarkOptions = {}): BenchResult[] {
  const { quiet = false, validateRoundTrip: doValidation = false } = options;
  const results: BenchResult[] = [];
  const log = (msg: string) => { if (!quiet) process.stdout.write(msg); };
  const logln = (msg: string) => { if (!quiet) console.log(msg); };

  // v7 MARISA (recursive tail trie, uncompressed)
  log('    v7 MARISA (uncompressed)...');
  results.push(benchmark('v7', 7, words, () => {
    const { trie } = MarisaTrie.build(words, {});
    return {
      nodeCount: trie.nodeCount,
      serialize: () => trie.serialize(),
      has: (w) => trie.has(w),
      keysWithPrefix: (p, l) => trie.keysWithPrefix(p, l),
      detailedStats: () => trie.detailedStats(),
      memoryStats: (sz) => trie.memoryStats(sz),
      getWord: (id) => trie.getWord(id),
      wordCount: trie.wordCount,
    };
  }, {
    validateRoundTrip: doValidation,
    deserialize: (buf) => MarisaTrie.deserialize(buf),
  }));
  logln(' done');

  // v8 MARISA (brotli compression)
  log('    v8 MARISA (brotli)...');
  results.push(benchmark('v8', 8, words, () => {
    const { trie } = MarisaTrie.build(words, { enableBrotli: true });
    return {
      nodeCount: trie.nodeCount,
      serialize: () => trie.serialize(),
      has: (w) => trie.has(w),
      keysWithPrefix: (p, l) => trie.keysWithPrefix(p, l),
      detailedStats: () => trie.detailedStats(),
      memoryStats: (sz) => trie.memoryStats(sz),
      getWord: (id) => trie.getWord(id),
      wordCount: trie.wordCount,
    };
  }, {
    validateRoundTrip: doValidation,
    deserialize: (buf) => MarisaTrie.deserialize(buf),
  }));
  logln(' done');

  return results;
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
function printResults(dataset: DatasetConfig, results: BenchResult[]): void {
  console.log('\n' + '='.repeat(100));
  console.log(`BENCHMARK: ${dataset.name}`);
  console.log(`${dataset.description}`);
  console.log('='.repeat(100));
  console.log(`Words: ${fmt(results[0].wordCount)}`);
  console.log();

  // Header
  console.log(
    'Format'.padEnd(14) +
    'Nodes'.padEnd(14) +
    'Size'.padEnd(12) +
    'B/word'.padEnd(10) +
    'Build'.padEnd(12) +
    'Lookup'.padEnd(12) +
    'Prefix'
  );
  console.log('-'.repeat(100));

  // Data rows
  for (const r of results) {
    const lookupStr = isNaN(r.lookupAvgUs) ? 'N/A' : `${r.lookupAvgUs.toFixed(2)}µs`;
    const prefixStr = isNaN(r.prefixAvgUs) ? 'N/A' : `${r.prefixAvgUs.toFixed(1)}µs`;
    console.log(
      r.format.padEnd(14) +
      fmt(r.nodeCount).padEnd(14) +
      fmtBytes(r.binarySize).padEnd(12) +
      r.bytesPerWord.toFixed(2).padEnd(10) +
      `${r.buildTimeMs.toFixed(0)}ms`.padEnd(12) +
      lookupStr.padEnd(12) +
      prefixStr
    );
  }

  console.log('-'.repeat(100));

  // Size comparison vs v7
  const baseline = results.find(r => r.format === 'v7');
  if (baseline) {
    console.log('Size vs v7 (uncompressed):');
    for (const r of results) {
      if (r.format === 'v7') continue;
      const ratio = r.binarySize / baseline.binarySize;
      const pctChange = ((ratio - 1) * 100);
      const sign = pctChange >= 0 ? '+' : '';
      const arrow = pctChange < 0 ? '↓' : (pctChange > 0 ? '↑' : '=');
      console.log(`  ${r.format.padEnd(12)} ${sign}${pctChange.toFixed(1)}% ${arrow}`);
    }
  }

  // Memory stats for brotli format (v8)
  const brotliFormats = results.filter(r => r.memoryStats && r.format === 'v8');
  if (brotliFormats.length > 0) {
    console.log('\nMemory Usage (v8 brotli format):');
    console.log(
      'Format'.padEnd(14) +
      'Download'.padEnd(12) +
      'Decompressed'.padEnd(14) +
      'Runtime'.padEnd(12) +
      'bits/word (dl)'.padEnd(16) +
      'bits/word (rt)'
    );
    console.log('-'.repeat(80));
    for (const r of brotliFormats) {
      if (!r.memoryStats) continue;
      const m = r.memoryStats;
      console.log(
        r.format.padEnd(14) +
        fmtBytes(m.downloadSize).padEnd(12) +
        fmtBytes(m.decompressedSize).padEnd(14) +
        fmtBytes(m.runtimeMemory).padEnd(12) +
        m.bitsPerWord.download.toFixed(2).padEnd(16) +
        m.bitsPerWord.runtime.toFixed(2)
      );
    }
  }
}

/**
 * Print summary comparison across all datasets.
 */
function printSummary(allResults: DatasetResults[]): void {
  console.log('\n');
  console.log('='.repeat(100));
  console.log('SUMMARY: File Size Comparison Across Datasets');
  console.log('='.repeat(100));
  console.log();

  // Header
  const formats = ['v7', 'v8'];
  console.log('Dataset'.padEnd(20) + 'Words'.padEnd(12) + formats.map(f => f.padEnd(14)).join(''));
  console.log('-'.repeat(100));

  for (const dr of allResults) {
    let row = dr.dataset.name.padEnd(20);
    row += fmt(dr.words.length).padEnd(12);
    for (const formatName of formats) {
      const r = dr.results.find(r => r.format === formatName);
      if (r) {
        row += fmtBytes(r.binarySize).padEnd(14);
      } else {
        row += 'N/A'.padEnd(14);
      }
    }
    console.log(row);
  }

  console.log('-'.repeat(100));

  // Bytes per word comparison
  console.log('\nBytes per word:');
  console.log('Dataset'.padEnd(20) + 'Words'.padEnd(12) + formats.map(f => f.padEnd(14)).join(''));
  console.log('-'.repeat(100));

  for (const dr of allResults) {
    let row = dr.dataset.name.padEnd(20);
    row += fmt(dr.words.length).padEnd(12);
    for (const formatName of formats) {
      const r = dr.results.find(r => r.format === formatName);
      if (r) {
        row += `${r.bytesPerWord.toFixed(2)} B`.padEnd(14);
      } else {
        row += 'N/A'.padEnd(14);
      }
    }
    console.log(row);
  }

  console.log('='.repeat(100));
}

/**
 * Output results as JSON for comparison with Python benchmark.
 */
function outputJson(allResults: DatasetResults[]): void {
  const output = allResults.map(dr => ({
    dataset: {
      name: dr.dataset.name,
      description: dr.dataset.description,
      spec_file: dr.dataset.specFile,
    },
    results: dr.results.map(r => ({
      format: r.format,
      implementation: 'typescript',
      word_count: r.wordCount,
      node_count: r.nodeCount,
      binary_size: r.binarySize,
      bytes_per_word: r.bytesPerWord,
      build_time_ms: r.buildTimeMs,
      lookup_avg_us: isNaN(r.lookupAvgUs) ? null : r.lookupAvgUs,
      prefix_avg_us: isNaN(r.prefixAvgUs) ? null : r.prefixAvgUs,
    })),
  }));
  console.log(JSON.stringify(output, null, 2));
}

/**
 * Print round-trip validation results.
 */
function printValidation(dataset: DatasetConfig, results: BenchResult[]): void {
  console.log('\n' + '='.repeat(100));
  console.log(`ROUND-TRIP VALIDATION: ${dataset.name}`);
  console.log('='.repeat(100));

  let allPassed = true;
  for (const r of results) {
    if (!r.roundTrip) continue;

    const status = r.roundTrip.passed ? '✓ PASS' : '✗ FAIL';
    console.log(`\n${r.format}: ${status}`);

    if (!r.roundTrip.passed) {
      allPassed = false;
      console.log(`  Original:   ${r.roundTrip.originalCount.toLocaleString()} words`);
      console.log(`  Round-trip: ${r.roundTrip.roundTripCount.toLocaleString()} words`);
      if (r.roundTrip.missingWords.length > 0) {
        console.log(`  Missing (first ${r.roundTrip.missingWords.length}): ${r.roundTrip.missingWords.join(', ')}`);
      }
      if (r.roundTrip.extraWords.length > 0) {
        console.log(`  Extra (first ${r.roundTrip.extraWords.length}): ${r.roundTrip.extraWords.join(', ')}`);
      }
    }
  }

  console.log('\n' + '-'.repeat(100));
  console.log(allPassed ? 'All formats passed round-trip validation ✓' : 'Some formats FAILED validation ✗');
  console.log('='.repeat(100));
}

/**
 * Print detailed size breakdown.
 */
function printBreakdown(dataset: DatasetConfig, results: BenchResult[]): void {
  console.log('\n' + '='.repeat(100));
  console.log(`SIZE BREAKDOWN: ${dataset.name}`);
  console.log('='.repeat(100));

  for (const r of results) {
    if (!r.detailedStats) continue;
    const s = r.detailedStats;

    console.log(`\n${r.format} (${fmtBytes(r.binarySize)} total, ${r.bytesPerWord.toFixed(2)} B/word)`);
    console.log('-'.repeat(80));

    const row = (label: string, bytes: number, pct: number, extra?: string) => {
      const pctStr = `${pct.toFixed(1)}%`.padStart(6);
      const bytesStr = fmtBytes(bytes).padStart(10);
      const extraStr = extra ? `  ${extra}` : '';
      console.log(`  ${label.padEnd(20)} ${bytesStr} ${pctStr}${extraStr}`);
    };

    row('Header', s.headerBytes, s.breakdown.header);
    row('LOUDS bitvector', s.louds.totalBytes, s.breakdown.louds,
      `[raw: ${fmtBytes(s.louds.rawBitsBytes)}, dir: ${fmtBytes(s.louds.directoryBytes)} (${s.louds.directoryOverhead.toFixed(0)}% overhead)]`);
    row('Terminal bits', s.terminal.totalBytes, s.breakdown.terminal,
      `[raw: ${fmtBytes(s.terminal.rawBitsBytes)}, dir: ${fmtBytes(s.terminal.directoryBytes)} (${s.terminal.directoryOverhead.toFixed(0)}% overhead)]`);

    if (s.linkFlags) {
      row('Link flags', s.linkFlags.totalBytes, s.breakdown.linkFlags,
        `[raw: ${fmtBytes(s.linkFlags.rawBitsBytes)}, dir: ${fmtBytes(s.linkFlags.directoryBytes)} (${s.linkFlags.directoryOverhead.toFixed(0)}% overhead)]`);
    }

    row('Labels', s.labels.totalBytes, s.breakdown.labels,
      `[${s.edgeCount.toLocaleString()} edges, ${s.labels.avgBitsPerLabel.toFixed(1)} bits/label avg]`);

    if (s.tails) {
      const tailType = s.tails.isRecursive ? 'recursive trie' : 'flat buffer';
      row('Tails', s.tails.totalBytes, s.breakdown.tails, `[${tailType}]`);
    }

    console.log('-'.repeat(80));

    // Show directory overhead summary
    const totalDirBytes = s.louds.directoryBytes + s.terminal.directoryBytes +
      (s.linkFlags?.directoryBytes ?? 0);
    const totalRawBitsBytes = s.louds.rawBitsBytes + s.terminal.rawBitsBytes +
      (s.linkFlags?.rawBitsBytes ?? 0);
    const dirOverheadPct = totalRawBitsBytes > 0
      ? (totalDirBytes / (totalRawBitsBytes + totalDirBytes)) * 100
      : 0;
    console.log(`  Total bitvector directory overhead: ${fmtBytes(totalDirBytes)} (${dirOverheadPct.toFixed(1)}% of bitvectors)`);
  }

  console.log('\n' + '='.repeat(100));
}

async function main() {
  // Initialize brotli support (needed for v8 compression)
  await initBrotliNode();

  const args = process.argv.slice(2);

  // Parse flags
  const runAll = args.includes('--all');
  const runWordle = args.includes('--wordle');
  const runWordOnly = args.includes('--word-only');
  const runFull = args.includes('--full');
  const jsonOutput = args.includes('--json');
  const showBreakdown = args.includes('--breakdown');
  const doValidation = args.includes('--validate');

  // Find custom input path (non-flag argument)
  const customInput = args.find(a => !a.startsWith('--'));

  if (!jsonOutput) {
    console.log('OWTRIE Format Benchmark');
    console.log('=======================\n');
  }

  const allResults: DatasetResults[] = [];

  // If custom input file is provided, use that directly
  if (customInput) {
    if (!fs.existsSync(customInput)) {
      console.error(`Error: Input file not found: ${customInput}`);
      process.exit(1);
    }

    if (!jsonOutput) console.log(`Loading custom wordlist: ${customInput}...`);
    const words = loadWordsFromFile(customInput);
    if (!jsonOutput) console.log(`  Loaded ${fmt(words.length)} unique words`);

    const dataset: DatasetConfig = {
      name: path.basename(customInput),
      description: 'Custom wordlist',
      specFile: customInput,
    };

    if (!jsonOutput) console.log('  Running benchmarks:');
    const results = runBenchmarks(words, {
      quiet: jsonOutput,
      validateRoundTrip: doValidation,
    });
    if (!jsonOutput) printResults(dataset, results);
    if (showBreakdown && !jsonOutput) printBreakdown(dataset, results);
    if (doValidation && !jsonOutput) printValidation(dataset, results);
    allResults.push({ dataset, words, results });

  } else {
    // Use owlex spec files for predefined datasets
    let datasetsToRun: string[];
    if (runAll) {
      datasetsToRun = ['wordle', 'word-only', 'full'];
    } else if (runWordle || runWordOnly || runFull) {
      datasetsToRun = [];
      if (runWordle) datasetsToRun.push('wordle');
      if (runWordOnly) datasetsToRun.push('word-only');
      if (runFull) datasetsToRun.push('full');
    } else {
      // Default to full
      datasetsToRun = ['full'];
    }

    for (const datasetKey of datasetsToRun) {
      const dataset = DATASETS[datasetKey];
      if (!jsonOutput) console.log(`\nLoading ${dataset.name} dataset...`);

      try {
        const words = loadWordsFromSpec(dataset.specFile, jsonOutput);
        if (!jsonOutput) console.log(`  Loaded ${fmt(words.length)} unique words`);

        if (words.length === 0) {
          console.error(`  Error: No words found for ${dataset.name}`);
          continue;
        }

        if (!jsonOutput) console.log('  Running benchmarks:');
        const results = runBenchmarks(words, {
          quiet: jsonOutput,
          validateRoundTrip: doValidation,
        });
        if (!jsonOutput) printResults(dataset, results);
        if (showBreakdown && !jsonOutput) printBreakdown(dataset, results);
        if (doValidation && !jsonOutput) printValidation(dataset, results);

        allResults.push({ dataset, words, results });
      } catch (err) {
        console.error(`  Error loading ${dataset.name}: ${err}`);
        continue;
      }
    }
  }

  // Output results
  if (jsonOutput) {
    outputJson(allResults);
  } else {
    // Print summary if multiple datasets
    if (allResults.length > 1) {
      printSummary(allResults);
    }

    // Notes
    console.log('\nNotes:');
    console.log('  - v7: Uncompressed (best runtime efficiency, no decompression needed)');
    console.log('  - v8: Brotli-compressed payload (best compression, slower load)');
  }
}

main().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
