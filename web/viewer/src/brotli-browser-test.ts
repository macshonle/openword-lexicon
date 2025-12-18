#!/usr/bin/env node
/**
 * brotli-browser-test.ts - Headless browser test for brotli-wasm
 *
 * Tests brotli decompression in a real browser environment and measures memory usage.
 *
 * Usage:
 *   pnpm exec tsx src/brotli-browser-test.ts
 */

import { chromium, Browser, Page } from 'playwright';
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

interface TestResult {
  wasmInitTime: number;
  v7FetchTime: number;
  v7DeserializeTime: number;
  v7DownloadSize: number;
  v8FetchTime: number;
  v8DeserializeTime: number;
  v8DownloadSize: number;
  memoryBefore?: number;
  memoryAfterV7?: number;
  memoryAfterV8?: number;
  errors: string[];
}

async function runBrotliTest(page: Page): Promise<TestResult> {
  const result: TestResult = {
    wasmInitTime: 0,
    v7FetchTime: 0,
    v7DeserializeTime: 0,
    v7DownloadSize: 0,
    v8FetchTime: 0,
    v8DeserializeTime: 0,
    v8DownloadSize: 0,
    errors: [],
  };

  // Navigate to test page
  await page.goto('http://localhost:8083/web/viewer/brotli-test.html');
  await page.waitForLoadState('networkidle');

  // Capture console logs
  page.on('console', msg => {
    if (msg.type() === 'error') {
      result.errors.push(msg.text());
    }
  });

  // Step 1: Initialize brotli-wasm
  console.log('  Initializing brotli-wasm...');
  await page.click('#btn-init');

  // Wait for initialization to complete
  await page.waitForFunction(() => {
    const status = document.getElementById('brotli-status');
    return status?.textContent === 'Ready' || status?.textContent?.includes('Failed');
  }, { timeout: 30000 });

  const wasmStatus = await page.textContent('#brotli-status');
  if (wasmStatus?.includes('Failed')) {
    result.errors.push(`WASM init failed: ${wasmStatus}`);
    return result;
  }

  const wasmInitTime = await page.textContent('#wasm-init-time');
  result.wasmInitTime = parseFloat(wasmInitTime?.replace(' ms', '') || '0');
  console.log(`    WASM init: ${result.wasmInitTime.toFixed(1)} ms`);

  // Step 2: Load v7 (baseline, no brotli)
  console.log('  Loading v7 trie (no brotli)...');
  await page.click('#btn-load-v7');
  await page.waitForFunction(() => {
    const el = document.getElementById('v7-words');
    return el?.textContent !== '-';
  }, { timeout: 30000 });

  result.v7FetchTime = parseFloat((await page.textContent('#v7-fetch'))?.replace(' ms', '') || '0');
  result.v7DeserializeTime = parseFloat((await page.textContent('#v7-deserialize'))?.replace(' ms', '') || '0');
  result.v7DownloadSize = parseByteSize(await page.textContent('#v7-download') || '0');
  console.log(`    Fetch: ${result.v7FetchTime.toFixed(1)} ms, Deserialize: ${result.v7DeserializeTime.toFixed(1)} ms`);

  // Get memory after v7
  result.memoryAfterV7 = await page.evaluate(() => {
    return (performance as any).memory?.usedJSHeapSize || null;
  });

  // Step 3: Load v8 (brotli compressed)
  console.log('  Loading v8 trie (brotli)...');
  await page.click('#btn-load-v8');

  // Wait for either success (words populated) or error (download shows "Error")
  await page.waitForFunction(() => {
    const wordsEl = document.getElementById('v8-words');
    const downloadEl = document.getElementById('v8-download');
    return wordsEl?.textContent !== '-' || downloadEl?.textContent === 'Error';
  }, { timeout: 30000 });

  // Check for error
  const v8Download = await page.textContent('#v8-download');
  if (v8Download === 'Error') {
    // Capture log for debugging
    const logs = await page.evaluate(() => {
      const logEl = document.getElementById('log');
      return logEl?.textContent || '';
    });
    console.log('  Browser log:', logs.substring(logs.length - 500));
    result.errors.push('v8 load failed - check browser console');
    return result;
  }

  result.v8FetchTime = parseFloat((await page.textContent('#v8-fetch'))?.replace(' ms', '') || '0');
  result.v8DeserializeTime = parseFloat((await page.textContent('#v8-deserialize'))?.replace(' ms', '') || '0');
  result.v8DownloadSize = parseByteSize(await page.textContent('#v8-download') || '0');
  console.log(`    Fetch: ${result.v8FetchTime.toFixed(1)} ms, Deserialize: ${result.v8DeserializeTime.toFixed(1)} ms`);

  // Get memory after v8
  result.memoryAfterV8 = await page.evaluate(() => {
    return (performance as any).memory?.usedJSHeapSize || null;
  });

  return result;
}

function parseByteSize(str: string): number {
  const match = str.match(/([\d.]+)\s*(KB|MB|B)/i);
  if (!match) return 0;
  const value = parseFloat(match[1]);
  const unit = match[2].toUpperCase();
  if (unit === 'MB') return value * 1024 * 1024;
  if (unit === 'KB') return value * 1024;
  return value;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
  return (bytes / 1024 / 1024).toFixed(2) + ' MB';
}

async function main() {
  console.log('OWTRIE Brotli/WASM Browser Test');
  console.log('================================\n');

  let server: Server | null = null;
  let browser: Browser | null = null;

  try {
    // Start server
    server = await createStaticServer(8083);
    console.log('Server started on port 8083\n');

    // Launch browser
    browser = await chromium.launch({
      headless: true,
      args: ['--enable-precise-memory-info'],
    });
    const context = await browser.newContext();
    const page = await context.newPage();

    console.log('Running browser tests...\n');
    const result = await runBrotliTest(page);

    // Print results
    console.log('\n' + '='.repeat(60));
    console.log('RESULTS');
    console.log('='.repeat(60) + '\n');

    console.log('Initialization:');
    console.log(`  brotli-wasm load time: ${result.wasmInitTime.toFixed(1)} ms\n`);

    console.log('v7 (baseline, no brotli):');
    console.log(`  Download size:    ${formatBytes(result.v7DownloadSize)}`);
    console.log(`  Fetch time:       ${result.v7FetchTime.toFixed(1)} ms`);
    console.log(`  Deserialize time: ${result.v7DeserializeTime.toFixed(1)} ms\n`);

    console.log('v8 (brotli compressed):');
    console.log(`  Download size:    ${formatBytes(result.v8DownloadSize)}`);
    console.log(`  Fetch time:       ${result.v8FetchTime.toFixed(1)} ms`);
    console.log(`  Deserialize time: ${result.v8DeserializeTime.toFixed(1)} ms`);
    console.log(`  (includes brotli decompression)\n`);

    const downloadSavings = ((result.v7DownloadSize - result.v8DownloadSize) / result.v7DownloadSize * 100);
    console.log('Comparison:');
    console.log(`  Download savings: ${downloadSavings.toFixed(1)}% (${formatBytes(result.v7DownloadSize)} -> ${formatBytes(result.v8DownloadSize)})`);

    if (result.memoryAfterV7 && result.memoryAfterV8) {
      console.log(`  Memory after v7: ${formatBytes(result.memoryAfterV7)}`);
      console.log(`  Memory after v8: ${formatBytes(result.memoryAfterV8)}`);
    }

    if (result.errors.length > 0) {
      console.log('\nErrors:');
      for (const err of result.errors) {
        console.log(`  - ${err}`);
      }
      process.exit(1);
    }

    console.log('\n' + '='.repeat(60));
    console.log('PASS: All browser tests completed successfully');
    console.log('='.repeat(60));

  } catch (error) {
    console.error('Test error:', error);
    process.exit(1);
  } finally {
    if (browser) await browser.close();
    if (server) server.close();
  }
}

main();
