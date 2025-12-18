#!/usr/bin/env node
/**
 * build-test-tries.ts - Build test trie files for browser testing
 *
 * Creates v7 (uncompressed) and v8 (brotli) trie files for browser tests.
 * These files are used to test brotli-wasm decompression and memory usage.
 *
 * Usage:
 *   pnpm exec tsx src/build-test-tries.ts [--full]
 *
 * Options:
 *   --full    Build with full Wiktionary dataset (~1.3M words)
 *             Default: Wordle dataset (~3K words)
 */

import * as fs from 'fs';
import * as path from 'path';
import { execSync } from 'child_process';
import { MarisaTrie, initBrotliNode } from './trie/index.js';

const PROJECT_ROOT = path.resolve(import.meta.dirname, '..', '..', '..');
const OUTPUT_DIR = path.join(PROJECT_ROOT, 'web', 'viewer', 'test-data');

/**
 * Load words using owlex.
 */
function loadWords(specFile: string): string[] {
  const specPath = path.join(PROJECT_ROOT, specFile);
  const result = execSync(`uv run owlex "${specPath}"`, {
    cwd: PROJECT_ROOT,
    encoding: 'utf-8',
    maxBuffer: 100 * 1024 * 1024,
  });
  return [...new Set(result.trim().split('\n').filter(w => w.length > 0))].sort();
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

interface BuildConfig {
  name: string;
  specFile: string;
  prefix: string;
}

async function buildDataset(config: BuildConfig) {
  console.log(`\n${'='.repeat(60)}`);
  console.log(`Building ${config.name} dataset`);
  console.log('='.repeat(60));

  console.log(`Loading words from ${config.specFile}...`);
  const words = loadWords(config.specFile);
  console.log(`  Loaded ${words.length.toLocaleString()} words\n`);

  const results: Array<{
    version: string;
    filename: string;
    downloadSize: number;
    decompressedSize: number;
    runtimeMemory: number;
    buildTime: number;
  }> = [];

  // v7 (uncompressed baseline)
  console.log('Building v7 (uncompressed)...');
  let start = performance.now();
  const { trie: trie7 } = MarisaTrie.build(words, {});
  let buildTime = performance.now() - start;
  const buffer7 = trie7.serialize();
  const path7 = path.join(OUTPUT_DIR, `${config.prefix}-v7.trie.bin`);
  fs.writeFileSync(path7, buffer7);
  const mem7 = trie7.memoryStats(buffer7.length);
  console.log(`  Saved: ${path7} (${formatSize(buffer7.length)}) in ${(buildTime / 1000).toFixed(1)}s`);
  results.push({
    version: 'v7',
    filename: `${config.prefix}-v7.trie.bin`,
    downloadSize: mem7.downloadSize,
    decompressedSize: mem7.decompressedSize,
    runtimeMemory: mem7.runtimeMemory,
    buildTime,
  });

  // v8 (brotli compressed, quality 11)
  console.log('Building v8 (brotli)...');
  start = performance.now();
  const { trie: trie8 } = MarisaTrie.build(words, {
    enableBrotli: true,
  });
  buildTime = performance.now() - start;
  const buffer8 = trie8.serialize();
  const path8 = path.join(OUTPUT_DIR, `${config.prefix}-v8.trie.bin`);
  fs.writeFileSync(path8, buffer8);
  const mem8 = trie8.memoryStats(buffer8.length);
  console.log(`  Saved: ${path8} (${formatSize(buffer8.length)}) in ${(buildTime / 1000).toFixed(1)}s`);
  results.push({
    version: 'v8',
    filename: `${config.prefix}-v8.trie.bin`,
    downloadSize: mem8.downloadSize,
    decompressedSize: mem8.decompressedSize,
    runtimeMemory: mem8.runtimeMemory,
    buildTime,
  });

  // Print summary
  console.log('\nMemory Statistics:');
  console.log('-'.repeat(70));
  console.log(`${'Format'.padEnd(10)} ${'Download'.padEnd(12)} ${'Decompress'.padEnd(12)} ${'Runtime'.padEnd(12)} ${'Build Time'}`);
  console.log('-'.repeat(70));
  for (const r of results) {
    console.log(
      `${r.version.padEnd(10)} ` +
      `${formatSize(r.downloadSize).padEnd(12)} ` +
      `${formatSize(r.decompressedSize).padEnd(12)} ` +
      `${formatSize(r.runtimeMemory).padEnd(12)} ` +
      `${(r.buildTime / 1000).toFixed(1)}s`
    );
  }

  // Save word list for verification (sample for large datasets)
  const wordListPath = path.join(OUTPUT_DIR, `${config.prefix}-words.json`);
  if (words.length > 10000) {
    // Save just first 1000 and last 1000 for verification
    const sample = [...words.slice(0, 1000), ...words.slice(-1000)];
    fs.writeFileSync(wordListPath, JSON.stringify({ total: words.length, sample }));
    console.log(`\nWord sample saved: ${wordListPath} (${sample.length} of ${words.length})`);
  } else {
    fs.writeFileSync(wordListPath, JSON.stringify(words));
    console.log(`\nWord list saved: ${wordListPath}`);
  }

  return { words: words.length, results };
}

async function main() {
  const args = process.argv.slice(2);
  const buildFull = args.includes('--full');

  // Initialize brotli support
  await initBrotliNode();

  // Ensure output directory exists
  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  console.log('Building test tries for browser testing...');

  // Always build Wordle (small, for quick tests)
  await buildDataset({
    name: 'Wordle 5-letter',
    specFile: 'examples/wordlist-specs/wordle.yaml',
    prefix: 'wordle',
  });

  // Optionally build full Wiktionary
  if (buildFull) {
    await buildDataset({
      name: 'Full Wiktionary',
      specFile: 'examples/wordlist-specs/full.yaml',
      prefix: 'full',
    });
  }

  console.log('\n' + '='.repeat(60));
  console.log('Done! Test files ready for browser testing.');
  console.log('='.repeat(60));

  if (!buildFull) {
    console.log('\nTip: Use --full to also build with full Wiktionary dataset');
  }
}

main().catch(console.error);
