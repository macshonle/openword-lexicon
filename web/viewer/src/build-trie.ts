#!/usr/bin/env node
/**
 * build-trie.ts - Build compact binary trie from wordlist or JSONL
 *
 * Creates a MARISA trie and serializes it to a compact binary format
 * optimized for browser consumption.
 *
 * Format versions:
 *   v7: MARISA trie with recursive tail trie (uncompressed)
 *   v8: MARISA trie with recursive tail trie + brotli compression
 *
 * Input formats:
 *   .txt     - Plain text wordlist (one word per line)
 *   .jsonl   - JSON Lines with "lemma" field (pipeline output format)
 *
 * Usage:
 *   pnpm build-trie [input] [output] [--format=v7|v8|auto] [--brotli]
 *
 * Examples:
 *   # Build from pipeline JSONL output
 *   pnpm build-trie ../../data/intermediate/en-wikt-v2-enriched.jsonl data/en.trie.bin
 *
 *   # Build from plain wordlist
 *   pnpm build-trie wordlist.txt data/en.trie.bin
 *
 *   # Build v8 (brotli compressed) format
 *   pnpm build-trie input.jsonl output.trie.bin --brotli
 */

import * as fs from 'fs';
import * as path from 'path';
import {
  FormatVersion,
  MarisaTrie,
  initBrotliNode,
} from './trie/index.js';

// Default paths relative to web/viewer/
const DEFAULT_INPUT = '../../data/intermediate/en-wikt-v2-enriched.jsonl';
const DEFAULT_OUTPUT = 'data/en.trie.bin';

/**
 * Load words from a file, detecting format by extension.
 */
function loadWords(inputPath: string): string[] {
  const ext = path.extname(inputPath).toLowerCase();
  const content = fs.readFileSync(inputPath, 'utf-8');

  if (ext === '.jsonl') {
    // JSONL format: extract "lemma" field from each line
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
        // Skip invalid JSON lines
      }
    }

    return words;
  } else {
    // Plain text: one word per line
    return content.trim().split('\n').filter(w => w.trim().length > 0).map(w => w.trim());
  }
}

/**
 * Parse command line arguments.
 */
function parseArgs(args: string[]): {
  inputPath: string;
  outputPath: string;
  format: FormatVersion;
  enableBrotli: boolean;
} {
  let inputPath = DEFAULT_INPUT;
  let outputPath = DEFAULT_OUTPUT;
  let format: FormatVersion = 'auto';
  let inputSet = false;
  let enableBrotli = false;

  for (const arg of args) {
    if (arg.startsWith('--format=')) {
      const fmt = arg.slice(9);
      if (fmt === 'v7' || fmt === 'v8' || fmt === 'auto') {
        format = fmt;
        if (fmt === 'v8') {
          enableBrotli = true;
        }
      } else {
        console.error(`Invalid format: ${fmt}. Use v7, v8, or auto.`);
        process.exit(1);
      }
    } else if (arg === '--brotli') {
      enableBrotli = true;
    } else if (arg === '--help' || arg === '-h') {
      printHelp();
      process.exit(0);
    } else if (!arg.startsWith('--')) {
      if (!inputSet) {
        inputPath = arg;
        inputSet = true;
      } else {
        outputPath = arg;
      }
    }
  }

  return { inputPath, outputPath, format, enableBrotli };
}

function printHelp(): void {
  console.log(`
build-trie - Build compact binary trie from wordlist or JSONL

Usage:
  pnpm build-trie [input] [output] [--format=v7|v8|auto] [--brotli]

Arguments:
  input     Input file (.txt wordlist or .jsonl pipeline output)
            Default: ${DEFAULT_INPUT}
  output    Output binary trie file
            Default: ${DEFAULT_OUTPUT}

Options:
  --format=<fmt>  Format version (v7, v8, or auto)
                  v7: Uncompressed (best runtime efficiency)
                  v8: Brotli-compressed (best compression)
                  auto: Same as v7 (default)
  --brotli        Enable brotli compression (same as --format=v8)

Examples:
  # Build from pipeline output (default)
  pnpm build-trie

  # Build from custom JSONL
  pnpm build-trie ../../data/intermediate/en-wikt-v2-enriched.jsonl data/en.trie.bin

  # Build v8 (brotli compressed) for smallest download size
  pnpm build-trie input.jsonl output.trie.bin --brotli
`);
}

/**
 * Main entry point.
 */
async function main() {
  const { inputPath, outputPath, format, enableBrotli } = parseArgs(process.argv.slice(2));

  // Initialize brotli support if needed
  if (enableBrotli) {
    await initBrotliNode();
  }

  const actualFormat = enableBrotli ? 'v8' : (format === 'v8' ? 'v8' : 'v7');

  console.log('Building compact binary trie...');
  console.log(`Input: ${inputPath}`);
  console.log(`Output: ${outputPath}`);
  console.log(`Format: ${actualFormat}${enableBrotli ? ' (brotli compressed)' : ''}`);
  console.log();

  // Check input file exists
  if (!fs.existsSync(inputPath)) {
    console.error(`Error: Input file not found: ${inputPath}`);
    console.error();
    console.error('Make sure you have run the pipeline to generate the input file.');
    console.error('Run: make enrich');
    process.exit(1);
  }

  // Load words
  console.log('Loading words...');
  const words = loadWords(inputPath);
  console.log(`Loaded ${words.length.toLocaleString()} words`);

  if (words.length === 0) {
    console.error('Error: No words found in input file');
    process.exit(1);
  }

  // Ensure output directory exists
  const outputDir = path.dirname(outputPath);
  if (outputDir && !fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const inputSize = fs.statSync(inputPath).size;

  // Build MARISA trie
  console.log('Building MARISA trie...');
  const { trie, stats } = MarisaTrie.build(words, { enableBrotli });

  console.log(`MARISA trie has ${trie.nodeCount.toLocaleString()} nodes`);

  // Serialize to binary
  console.log('Serializing...');
  const binary = trie.serialize();
  const version = enableBrotli ? 8 : 7;

  // Write output
  fs.writeFileSync(outputPath, binary);

  // Statistics
  const outputSize = binary.length;
  const ratio = ((outputSize / inputSize) * 100).toFixed(1);
  const bytesPerWord = (outputSize / words.length).toFixed(2);

  const extra: [string, string][] = [
    ['Edges', stats.edgeCount.toLocaleString()],
    ['LOUDS bits', `${stats.bitsSize.toLocaleString()} bytes`],
    ['Terminal bits', `${stats.terminalSize.toLocaleString()} bytes`],
    ['Labels', `${stats.labelsSize.toLocaleString()} bytes`],
  ];

  if (stats.linkFlagsSize > 0) {
    extra.push(['Link flags', `${stats.linkFlagsSize.toLocaleString()} bytes`]);
  }
  if (stats.tailBufferSize > 0) {
    extra.push(['Recursive trie', `${stats.tailBufferSize.toLocaleString()} bytes`]);
  }

  printStats({
    version,
    inputSize,
    outputSize,
    ratio,
    bytesPerWord,
    nodeCount: trie.nodeCount,
    extra,
  });

  console.log(`\nWrote: ${outputPath}`);
}

function printStats(opts: {
  version: number;
  inputSize: number;
  outputSize: number;
  ratio: string;
  bytesPerWord: string;
  nodeCount: number;
  extra: [string, string][];
}): void {
  console.log();
  console.log('='.repeat(50));
  console.log('Statistics:');
  console.log('='.repeat(50));
  console.log(`Format version:  v${opts.version}`);
  console.log(`Input size:      ${opts.inputSize.toLocaleString()} bytes (${(opts.inputSize / 1024 / 1024).toFixed(1)} MB)`);
  console.log(`Output size:     ${opts.outputSize.toLocaleString()} bytes (${(opts.outputSize / 1024).toFixed(1)} KB)`);
  console.log(`Compression:     ${opts.ratio}% of original`);
  console.log(`Bytes/word:      ${opts.bytesPerWord}`);
  console.log(`Nodes:           ${opts.nodeCount.toLocaleString()}`);
  for (const [label, value] of opts.extra) {
    console.log(`${label}:`.padEnd(17) + value);
  }
  console.log('='.repeat(50));
}

main().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
