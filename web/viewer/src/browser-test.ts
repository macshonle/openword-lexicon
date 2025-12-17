#!/usr/bin/env node
/**
 * browser-test.ts - Headless browser test runner for OWTRIE
 *
 * Runs the browser-based tests in test.html using Playwright in headless mode.
 * This allows automated testing without opening a browser window.
 *
 * Usage:
 *   pnpm browser-test           # Test default v6.1 trie
 *   pnpm browser-test --v63     # Test v6.3 recursive trie
 *   pnpm browser-test --all     # Test both v6.1 and v6.3
 */

import { chromium, Browser, Page } from 'playwright';
import { createServer, Server, IncomingMessage, ServerResponse } from 'http';
import { readFile, stat } from 'fs/promises';
import { join, extname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const PROJECT_ROOT = join(__dirname, '..', '..', '..');

// MIME types for static file serving
const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html',
  '.js': 'application/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.bin': 'application/octet-stream',
  '.trie': 'application/octet-stream',
};

interface TestResult {
  passed: number;
  failed: number;
  skipped: number;
  format: string;
  details: string;
}

/**
 * Create a simple HTTP server for serving test files.
 */
function createStaticServer(port: number): Promise<Server> {
  return new Promise((resolve, reject) => {
    const server = createServer(async (req: IncomingMessage, res: ServerResponse) => {
      // Strip query string from URL before resolving file path
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
        res.end('Not found');
      }
    });

    server.on('error', reject);
    server.listen(port, () => resolve(server));
  });
}

/**
 * Run tests in headless browser and extract results.
 */
async function runTests(page: Page, testV63: boolean): Promise<TestResult> {
  const url = testV63
    ? 'http://localhost:8081/web/viewer/test.html?trie=v63'
    : 'http://localhost:8081/web/viewer/test.html';

  // Navigate to test page
  await page.goto(url);

  // Wait for tests to complete (look for summary element)
  await page.waitForSelector('.summary', { timeout: 120000 });

  // Extract results from the page
  const result = await page.evaluate(() => {
    const summaryEl = document.querySelector('.summary');
    const formatInfoEl = document.querySelector('.format-info');
    const textResultsEl = document.querySelector('#textResults') as HTMLTextAreaElement;

    const summaryText = summaryEl?.textContent || '';
    const match = summaryText.match(/(\d+) passed, (\d+) failed, (\d+) skipped/);

    return {
      passed: match ? parseInt(match[1], 10) : 0,
      failed: match ? parseInt(match[2], 10) : 0,
      skipped: match ? parseInt(match[3], 10) : 0,
      format: formatInfoEl?.textContent || 'unknown',
      details: textResultsEl?.value || '',
    };
  });

  return result;
}

/**
 * Print test results to console.
 */
function printResults(result: TestResult, label: string): void {
  console.log();
  console.log('='.repeat(60));
  console.log(`${label}`);
  console.log('='.repeat(60));
  console.log(result.format);
  console.log();

  if (result.failed > 0) {
    // Print details for failures
    const lines = result.details.split('\n');
    for (const line of lines) {
      if (line.includes('[FAIL]')) {
        console.log(`  ❌ ${line.replace('[FAIL] ', '')}`);
      }
    }
    console.log();
  }

  const status = result.failed === 0 ? '✅ PASS' : '❌ FAIL';
  console.log(`${status}: ${result.passed} passed, ${result.failed} failed, ${result.skipped} skipped`);
}

async function main() {
  const args = process.argv.slice(2);
  const testV63Only = args.includes('--v63');
  const testAll = args.includes('--all');
  const testV61 = !testV63Only || testAll;
  const testV63 = testV63Only || testAll;

  console.log('Starting headless browser tests...');

  // Start HTTP server
  let server: Server | null = null;
  let browser: Browser | null = null;

  try {
    server = await createStaticServer(8081);
    console.log('Server started on port 8081');

    // Launch headless browser
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const page = await context.newPage();

    // Capture console logs from the page
    page.on('console', msg => {
      if (msg.type() === 'error') {
        console.error(`[Browser Error] ${msg.text()}`);
      }
    });

    let totalPassed = 0;
    let totalFailed = 0;

    // Test v6.1
    if (testV61) {
      console.log('\nRunning v6.1 tests...');
      const v61Result = await runTests(page, false);
      printResults(v61Result, 'v6.1 (path compression)');
      totalPassed += v61Result.passed;
      totalFailed += v61Result.failed;
    }

    // Test v6.3
    if (testV63) {
      console.log('\nRunning v6.3 tests...');
      const v63Result = await runTests(page, true);
      printResults(v63Result, 'v6.3 (recursive tails)');
      totalPassed += v63Result.passed;
      totalFailed += v63Result.failed;
    }

    // Overall summary
    if (testAll) {
      console.log();
      console.log('='.repeat(60));
      console.log('OVERALL SUMMARY');
      console.log('='.repeat(60));
      console.log(`Total: ${totalPassed} passed, ${totalFailed} failed`);
    }

    // Exit with appropriate code
    process.exit(totalFailed > 0 ? 1 : 0);

  } catch (error) {
    console.error('Test error:', error);
    process.exit(1);
  } finally {
    if (browser) await browser.close();
    if (server) server.close();
  }
}

main();
