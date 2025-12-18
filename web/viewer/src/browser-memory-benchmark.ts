#!/usr/bin/env node
/**
 * browser-memory-benchmark.ts - Comprehensive browser memory benchmark
 *
 * Tests each trie format in isolation with fresh browser contexts to get
 * accurate memory measurements. Measures memory at multiple stages:
 * - Before trie load
 * - After trie load
 * - After running prefix queries
 *
 * Usage:
 *   pnpm exec tsx src/browser-memory-benchmark.ts [--full]
 */

import { chromium, Browser, BrowserContext, Page } from 'playwright';
import { createServer, Server, IncomingMessage, ServerResponse } from 'http';
import { readFile, stat } from 'fs/promises';
import { join, extname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const PROJECT_ROOT = join(__dirname, '..', '..', '..');

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html',
  '.js': 'application/javascript',
  '.mjs': 'application/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.bin': 'application/octet-stream',
  '.wasm': 'application/wasm',
};

function createStaticServer(port: number): Promise<Server> {
  return new Promise((resolve, reject) => {
    const server = createServer(async (req: IncomingMessage, res: ServerResponse) => {
      const urlPath = (req.url || '/').split('?')[0];
      let filePath = join(PROJECT_ROOT, urlPath);

      try {
        const stats = await stat(filePath);
        if (stats.isDirectory()) {
          filePath = join(filePath, 'index.html');
        }

        const content = await readFile(filePath);
        const ext = extname(filePath);
        const mimeType = MIME_TYPES[ext] || 'application/octet-stream';

        res.writeHead(200, {
          'Content-Type': mimeType,
          'Access-Control-Allow-Origin': '*',
          'Cache-Control': 'no-cache',
        });
        res.end(content);
      } catch {
        res.writeHead(404);
        res.end('Not found: ' + urlPath);
      }
    });

    server.on('error', reject);
    server.listen(port, () => resolve(server));
  });
}

interface FormatResult {
  format: string;
  downloadSize: number;
  fetchTime: number;
  deserializeTime: number;
  wordCount: number;
  nodeCount: number;
  memoryBefore: number | null;
  memoryAfterLoad: number | null;
  memoryAfterQueries: number | null;
  queryCount: number;
  queryTime: number;
  avgQueryTime: number;
  errors: string[];
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
  return (bytes / 1024 / 1024).toFixed(2) + ' MB';
}

/**
 * Run benchmark for a single format in a fresh browser context.
 */
async function benchmarkFormat(
  browser: Browser,
  baseUrl: string,
  dataset: string,
  format: string,
  queryCount: number
): Promise<FormatResult> {
  const result: FormatResult = {
    format,
    downloadSize: 0,
    fetchTime: 0,
    deserializeTime: 0,
    wordCount: 0,
    nodeCount: 0,
    memoryBefore: null,
    memoryAfterLoad: null,
    memoryAfterQueries: null,
    queryCount: 0,
    queryTime: 0,
    avgQueryTime: 0,
    errors: [],
  };

  // Create fresh context for isolation
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    // Navigate to benchmark page with parameters
    const url = `${baseUrl}/web/viewer/memory-benchmark.html?dataset=${dataset}&format=${format}&queries=${queryCount}`;
    await page.goto(url);

    // Wait for benchmark to complete
    await page.waitForFunction(
      () => (window as any).benchmarkComplete === true,
      { timeout: 300000 } // 5 minutes for large datasets
    );

    // Extract results
    const pageResult = await page.evaluate(() => (window as any).benchmarkResult);

    if (pageResult.error) {
      result.errors.push(pageResult.error);
    } else {
      result.downloadSize = pageResult.downloadSize;
      result.fetchTime = pageResult.fetchTime;
      result.deserializeTime = pageResult.deserializeTime;
      result.wordCount = pageResult.wordCount;
      result.nodeCount = pageResult.nodeCount;
      result.memoryBefore = pageResult.memoryBefore;
      result.memoryAfterLoad = pageResult.memoryAfterLoad;
      result.memoryAfterQueries = pageResult.memoryAfterQueries;
      result.queryCount = pageResult.queryCount;
      result.queryTime = pageResult.queryTime;
      result.avgQueryTime = pageResult.avgQueryTime;
    }
  } catch (error) {
    result.errors.push(`Benchmark error: ${error}`);
  } finally {
    await context.close();
  }

  return result;
}

async function main() {
  const args = process.argv.slice(2);
  const useFull = args.includes('--full');
  const dataset = useFull ? 'full' : 'wordle';
  const queryCount = useFull ? 5000 : 1000;

  console.log('Browser Memory Benchmark');
  console.log('========================\n');
  console.log(`Dataset: ${dataset}`);
  console.log(`Prefix queries: ${queryCount.toLocaleString()}\n`);

  let server: Server | null = null;
  let browser: Browser | null = null;

  try {
    // Start server
    server = await createStaticServer(8084);
    console.log('Server started on port 8084\n');

    // Launch browser with memory measurement enabled
    browser = await chromium.launch({
      headless: true,
      args: [
        '--enable-precise-memory-info',
        '--js-flags=--expose-gc',
      ],
    });

    const formats = ['v7', 'v8'];
    const results: FormatResult[] = [];

    for (const format of formats) {
      console.log(`Testing ${format}...`);
      const result = await benchmarkFormat(browser, 'http://localhost:8084', dataset, format, queryCount);
      results.push(result);

      if (result.errors.length > 0) {
        console.log(`  ERROR: ${result.errors.join(', ')}`);
      } else {
        console.log(`  Download: ${formatBytes(result.downloadSize)}, Load: ${result.deserializeTime.toFixed(1)}ms`);
        console.log(`  Queries: ${result.queryCount} in ${result.queryTime.toFixed(1)}ms (${result.avgQueryTime.toFixed(3)}ms avg)`);
        if (result.memoryAfterLoad !== null && result.memoryBefore !== null) {
          const loadDelta = result.memoryAfterLoad - result.memoryBefore;
          console.log(`  Memory delta (load): ${formatBytes(loadDelta)}`);
        }
        if (result.memoryAfterQueries !== null && result.memoryAfterLoad !== null) {
          const queryDelta = result.memoryAfterQueries - result.memoryAfterLoad;
          console.log(`  Memory delta (queries): ${formatBytes(queryDelta)}`);
        }
      }
      console.log();
    }

    // Print summary table
    console.log('=' .repeat(100));
    console.log('SUMMARY');
    console.log('='.repeat(100));
    console.log();

    // Size comparison
    console.log('File Size Comparison:');
    console.log('-'.repeat(60));
    console.log(`${'Format'.padEnd(10)} ${'Download'.padEnd(12)} ${'vs v7'}`);
    console.log('-'.repeat(60));
    const baseline = results.find(r => r.format === 'v7');
    for (const r of results) {
      const vsBaseline = baseline && baseline.downloadSize > 0
        ? ((r.downloadSize / baseline.downloadSize - 1) * 100).toFixed(1) + '%'
        : '-';
      console.log(`${r.format.padEnd(10)} ${formatBytes(r.downloadSize).padEnd(12)} ${vsBaseline}`);
    }

    // Memory comparison
    console.log('\nMemory Usage (Chrome heap):');
    console.log('-'.repeat(80));
    console.log(`${'Format'.padEnd(10)} ${'Before'.padEnd(12)} ${'After Load'.padEnd(14)} ${'After Queries'.padEnd(14)} ${'Load Delta'.padEnd(12)}`);
    console.log('-'.repeat(80));
    for (const r of results) {
      const before = r.memoryBefore !== null ? formatBytes(r.memoryBefore) : 'N/A';
      const afterLoad = r.memoryAfterLoad !== null ? formatBytes(r.memoryAfterLoad) : 'N/A';
      const afterQueries = r.memoryAfterQueries !== null ? formatBytes(r.memoryAfterQueries) : 'N/A';
      const loadDelta = r.memoryAfterLoad !== null && r.memoryBefore !== null
        ? formatBytes(r.memoryAfterLoad - r.memoryBefore)
        : 'N/A';
      console.log(`${r.format.padEnd(10)} ${before.padEnd(12)} ${afterLoad.padEnd(14)} ${afterQueries.padEnd(14)} ${loadDelta.padEnd(12)}`);
    }

    // Performance comparison
    console.log('\nQuery Performance:');
    console.log('-'.repeat(60));
    console.log(`${'Format'.padEnd(10)} ${'Queries'.padEnd(10)} ${'Total Time'.padEnd(14)} ${'Avg Time'}`);
    console.log('-'.repeat(60));
    for (const r of results) {
      console.log(`${r.format.padEnd(10)} ${r.queryCount.toString().padEnd(10)} ${(r.queryTime.toFixed(1) + 'ms').padEnd(14)} ${r.avgQueryTime.toFixed(3)}ms`);
    }

    // Check for errors
    const hasErrors = results.some(r => r.errors.length > 0);
    console.log('\n' + '='.repeat(100));
    console.log(hasErrors ? 'COMPLETED WITH ERRORS' : 'BENCHMARK COMPLETE');
    console.log('='.repeat(100));

  } catch (error) {
    console.error('Fatal error:', error);
    process.exit(1);
  } finally {
    if (browser) await browser.close();
    if (server) server.close();
  }
}

main();
