#!/usr/bin/env node
/**
 * build-trie.ts - Build compact binary trie from wordlist or JSONL
 *
 * Creates a DAWG (Directed Acyclic Word Graph) or LOUDS trie and serializes
 * it to a compact binary format optimized for browser consumption.
 *
 * Format versions:
 *   v2: DAWG with 16-bit absolute node IDs (ASCII only, max 65K nodes, 3 bytes/child)
 *   v4: DAWG with varint delta node IDs (full Unicode, unlimited nodes, ~2 bytes/child avg)
 *   v5: LOUDS trie with bitvectors + labels (full Unicode, word ID support, ~1.5 bytes/char)
 *   v6: MARISA trie with path compression (full Unicode, most compact, ~1 byte/char)
 *       v6.1: --links enables tail buffer for path compression
 *       v6.3: --links --recursive enables recursive tail trie (smaller but slower)
 *
 * The builder auto-selects the best format based on node count and content,
 * or you can force a specific version with --format=v2|v4|v5|v6
 *
 * Input formats:
 *   .txt     - Plain text wordlist (one word per line)
 *   .jsonl   - JSON Lines with "lemma" field (pipeline output format)
 *
 * Usage:
 *   pnpm build-trie [input] [output] [--format=v2|v4|v5|v6|auto]
 *
 * Examples:
 *   # Build from pipeline JSONL output
 *   pnpm build-trie ../../data/intermediate/en-wikt-v2-enriched.jsonl data/en.trie.bin
 *
 *   # Build from plain wordlist
 *   pnpm build-trie wordlist.txt data/en.trie.bin --format=v4
 *
 *   # Force LOUDS format for word ID support
 *   pnpm build-trie input.jsonl output.trie.bin --format=v5
 *
 *   # Build MARISA trie with path compression (most compact)
 *   pnpm build-trie input.jsonl output.trie.bin --format=v6 --links
 */

import * as fs from 'fs';
import * as path from 'path';
import {
  FormatVersion,
  UnicodeCompatibilityError,
  checkV2Compatibility,
  buildDAWG,
  LOUDSTrie,
  MarisaTrie,
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
  enableLinks: boolean;
  enableRecursive: boolean;
} {
  let inputPath = DEFAULT_INPUT;
  let outputPath = DEFAULT_OUTPUT;
  let format: FormatVersion = 'auto';
  let inputSet = false;
  let enableLinks = false;
  let enableRecursive = false;

  for (const arg of args) {
    if (arg.startsWith('--format=')) {
      const fmt = arg.slice(9);
      if (fmt === 'v2' || fmt === 'v4' || fmt === 'v5' || fmt === 'v6' || fmt === 'auto') {
        format = fmt;
      } else {
        console.error(`Invalid format: ${fmt}. Use v2, v4, v5, v6, or auto.`);
        process.exit(1);
      }
    } else if (arg === '--links') {
      enableLinks = true;
    } else if (arg === '--recursive') {
      enableRecursive = true;
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

  return { inputPath, outputPath, format, enableLinks, enableRecursive };
}

function printHelp(): void {
  console.log(`
build-trie - Build compact binary trie from wordlist or JSONL

Usage:
  pnpm build-trie [input] [output] [--format=v2|v4|v5|v6|auto] [--links] [--recursive]

Arguments:
  input     Input file (.txt wordlist or .jsonl pipeline output)
            Default: ${DEFAULT_INPUT}
  output    Output binary trie file
            Default: ${DEFAULT_OUTPUT}

Options:
  --format=<fmt>  Format version (v2, v4, v5, v6, or auto)
                  v2: ASCII only, max 65K nodes, smallest for ASCII
                  v4: Full Unicode, unlimited nodes, recommended for DAWG
                  v5: LOUDS trie with word ID mapping
                  v6: MARISA trie with path compression (most compact)
                  auto: Select based on content and size (default)
  --links         Enable path compression for v6 (tail buffer, v6.1)
  --recursive     Enable recursive tail trie for v6 (v6.3, smaller but slower)

Examples:
  # Build from pipeline output (default)
  pnpm build-trie

  # Build from custom JSONL
  pnpm build-trie ../../data/intermediate/en-wikt-v2-enriched.jsonl data/en.trie.bin

  # Force v4 format for Unicode support
  pnpm build-trie wordlist.txt output.trie.bin --format=v4

  # Build v6.1 MARISA trie with path compression
  pnpm build-trie input.jsonl output.trie.bin --format=v6 --links

  # Build v6.3 MARISA trie with recursive tails (most compact)
  pnpm build-trie input.jsonl output.trie.bin --format=v6 --links --recursive
`);
}

/**
 * Main entry point.
 */
async function main() {
  const { inputPath, outputPath, format, enableLinks, enableRecursive } = parseArgs(process.argv.slice(2));

  console.log('Building compact binary trie...');
  console.log(`Input: ${inputPath}`);
  console.log(`Output: ${outputPath}`);
  console.log(`Format: ${format}`);
  if (format === 'v6' && enableLinks) {
    console.log(`Path compression: enabled`);
    if (enableRecursive) {
      console.log(`Recursive tails: enabled (v6.3)`);
    }
  }
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

  // Check Unicode compatibility for informational purposes
  const unicodeCheck = checkV2Compatibility(words);
  if (!unicodeCheck.compatible) {
    console.log(`Note: Input contains ${unicodeCheck.invalidChars.length} non-ASCII character(s)`);
    if (format === 'v2') {
      console.log('  Characters:', unicodeCheck.invalidChars.slice(0, 5).join(', '));
      console.log('  Sample words:', unicodeCheck.sampleWords.slice(0, 3).join(', '));
    }
  }

  // Ensure output directory exists
  const outputDir = path.dirname(outputPath);
  if (outputDir && !fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const inputSize = fs.statSync(inputPath).size;

  try {
    let binary: Uint8Array;
    let version: number;
    let nodeCount: number;

    if (format === 'v6') {
      // Build MARISA trie (v6 format)
      console.log('Building MARISA trie...');
      const { trie, stats } = MarisaTrie.build(words, { enableLinks, enableRecursive });

      console.log(`MARISA trie has ${trie.nodeCount.toLocaleString()} nodes`);

      // Serialize to binary
      console.log('Serializing...');
      binary = trie.serialize();
      version = 6;
      nodeCount = trie.nodeCount;

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
        const tailLabel = enableRecursive ? 'Recursive trie' : 'Tail buffer';
        extra.push([tailLabel, `${stats.tailBufferSize.toLocaleString()} bytes`]);
      }

      printStats({
        version,
        inputSize,
        outputSize,
        ratio,
        bytesPerWord,
        nodeCount,
        extra,
      });
    } else if (format === 'v5') {
      // Build LOUDS trie (v5 format)
      console.log('Building LOUDS trie...');
      const trie = LOUDSTrie.build(words);

      console.log(`LOUDS trie has ${trie.nodeCount.toLocaleString()} nodes`);

      // Serialize to binary
      console.log('Serializing...');
      binary = trie.serialize();
      version = 5;
      nodeCount = trie.nodeCount;

      // Write output
      fs.writeFileSync(outputPath, binary);

      // Statistics
      const outputSize = binary.length;
      const ratio = ((outputSize / inputSize) * 100).toFixed(1);
      const bytesPerWord = (outputSize / words.length).toFixed(2);
      const stats = trie.stats();

      printStats({
        version,
        inputSize,
        outputSize,
        ratio,
        bytesPerWord,
        nodeCount,
        extra: [
          ['Edges', stats.edgeCount.toLocaleString()],
          ['LOUDS bits', `${stats.bitsSize.toLocaleString()} bytes`],
          ['Terminal bits', `${stats.terminalSize.toLocaleString()} bytes`],
          ['Labels', `${stats.labelsSize.toLocaleString()} bytes`],
        ],
      });
    } else {
      // Build DAWG (v2/v4 format)
      console.log('Building DAWG...');
      const result = buildDAWG(words, format);

      console.log(`DAWG has ${result.nodeCount.toLocaleString()} unique nodes`);

      // Write output
      fs.writeFileSync(outputPath, result.buffer);

      binary = result.buffer;
      version = result.version;
      nodeCount = result.nodeCount;

      // Statistics
      const outputSize = binary.length;
      const ratio = ((outputSize / inputSize) * 100).toFixed(1);
      const bytesPerWord = (outputSize / words.length).toFixed(2);

      printStats({
        version,
        inputSize,
        outputSize,
        ratio,
        bytesPerWord,
        nodeCount,
        extra: [],
      });
    }

    console.log(`\nWrote: ${outputPath}`);

  } catch (error) {
    if (error instanceof UnicodeCompatibilityError) {
      console.error();
      console.error(`Error: ${error.message}`);
      console.error();
      console.error('Tip: Use --format=v4, --format=v5, or --format=v6 for full Unicode support.');
      process.exit(1);
    }
    throw error;
  }
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
