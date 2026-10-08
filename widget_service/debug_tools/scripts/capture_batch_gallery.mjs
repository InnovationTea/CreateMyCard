#!/usr/bin/env node

import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { chromium } from 'playwright-core';

function parseArgs(argv) {
  const result = {};
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (key !== '--url' && key !== '--output') throw new Error(`未知参数：${key}`);
    const value = argv[index + 1];
    if (!value || value.startsWith('--')) throw new Error(`${key} 缺少参数值`);
    result[key.slice(2)] = value;
    index += 1;
  }
  if (!result.url || !result.output) throw new Error('必须指定 --url 和 --output');
  return result;
}

async function existingPath(candidate) {
  if (!candidate) return null;
  try {
    const stat = await fs.stat(candidate);
    return stat.isFile() ? candidate : null;
  } catch {
    return null;
  }
}

async function browserExecutable() {
  const configured = await existingPath(process.env.WIDGET_DEBUG_GALLERY_BROWSER_EXECUTABLE);
  if (configured) return configured;
  const candidates = process.platform === 'win32'
    ? [
      'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
      'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
      'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    ]
    : process.platform === 'darwin'
      ? [
        '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      ]
      : ['/usr/bin/microsoft-edge', '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser'];
  for (const candidate of candidates) {
    const found = await existingPath(candidate);
    if (found) return found;
  }
  throw new Error(
    '未找到 Edge/Chrome/Chromium。可通过 WIDGET_DEBUG_GALLERY_BROWSER_EXECUTABLE 指定浏览器路径。',
  );
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  await fs.mkdir(args.output, { recursive: true });
  const browser = await chromium.launch({
    executablePath: await browserExecutable(),
    headless: true,
  });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
    const consoleErrors = [];
    page.on('console', (message) => {
      if (message.type() === 'error') consoleErrors.push(message.text());
    });
    await page.goto(args.url, { waitUntil: 'domcontentloaded', timeout: 120_000 });
    await page.waitForSelector('html[data-gallery-capture="ready"]', { timeout: 600_000 });
    const items = page.locator('.gallery-capture-item');
    const count = await items.count();
    const captured = [];
    for (let index = 0; index < count; index += 1) {
      const item = items.nth(index);
      const id = await item.getAttribute('data-sample-id');
      const size = await item.getAttribute('data-card-size');
      const error = await item.getAttribute('data-capture-error');
      const card = item.locator('.gallery-capture-card');
      if (await card.count()) {
        const runtimeError = card.locator('.card-renderer__runtime-error');
        if (await runtimeError.count()) {
          captured.push({
            id,
            file: '',
            size,
            error: (await runtimeError.textContent())?.trim() || '卡片渲染失败',
          });
          continue;
        }
        const file = `${String(index + 1).padStart(4, '0')}.png`;
        await card.screenshot({ path: path.join(args.output, file), animations: 'disabled', scale: 'css' });
        captured.push({ id, file, size, error: '' });
      } else {
        captured.push({ id, file: '', size, error: error || '该样本没有可渲染的 GenUI' });
      }
    }
    await fs.writeFile(
      path.join(args.output, 'capture.json'),
      `${JSON.stringify({ items: captured, consoleErrors }, null, 2)}\n`,
      'utf8',
    );
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  process.stderr.write(`画廊截图失败：${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
