#!/usr/bin/env node

/**
 * 把任意一组 Compact DSL 文件渲染成真实截图。
 *
 * 走的是调试平台自己的「卡片渲染」页（POST /debug/renderer/convert + 浏览器绘制），
 * 与批跑画廊截图用的是同一套渲染运行时，只是输入来自本地 .jsonl 文件而不是批跑产物。
 *
 *   node debug_tools/scripts/capture_dsl_preview.mjs \
 *     --manifest debug_tools/Datasets/<批次>/import/render-manifest.json \
 *     --base-url http://127.0.0.1:8888 --output debug_tools/Datasets/<批次>/renders
 *
 * manifest 形如 [{"id":"Q001","size":"2x2","file":"../dsl/Q001.jsonl"}]，file 相对 manifest 所在目录。
 */

import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { chromium } from 'playwright-core';

function parseArgs(argv) {
  const result = { 'base-url': 'http://127.0.0.1:8888', scale: '2' };
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (!['--manifest', '--output', '--base-url'].includes(key)) {
      throw new Error(`未知参数：${key}`);
    }
    const value = argv[index + 1];
    if (!value || value.startsWith('--')) throw new Error(`${key} 缺少参数值`);
    result[key.slice(2)] = value;
    index += 1;
  }
  if (!result.manifest || !result.output) throw new Error('必须指定 --manifest 和 --output');
  return result;
}

async function existingFile(candidate) {
  if (!candidate) return null;
  try {
    return (await fs.stat(candidate)).isFile() ? candidate : null;
  } catch {
    return null;
  }
}

async function browserExecutable() {
  const configured = await existingFile(process.env.WIDGET_DEBUG_GALLERY_BROWSER_EXECUTABLE);
  if (configured) return configured;
  const candidates = [
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    '/usr/bin/microsoft-edge',
    '/usr/bin/chromium',
  ];
  for (const candidate of candidates) {
    const found = await existingFile(candidate);
    if (found) return found;
  }
  throw new Error('未找到 Edge/Chrome/Chromium，可用 WIDGET_DEBUG_GALLERY_BROWSER_EXECUTABLE 指定。');
}

/** 等图片与字体就位，否则截图会出现占位框。 */
async function settle(page) {
  await page.evaluate(async () => {
    if (document.fonts) await document.fonts.ready;
    const waits = Array.from(document.images).map((image) => {
      if (image.complete) return Promise.resolve();
      return new Promise((resolve) => {
        image.addEventListener('load', () => resolve(), { once: true });
        image.addEventListener('error', () => resolve(), { once: true });
      });
    });
    await Promise.all(waits);
  });
  await page.evaluate(() => new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
  }));
}

/** 截图前把编辑区收起、把卡片的所有祖先改为不裁切，避免窄栏滚动导致卡片被切。 */
async function isolateCard(page) {
  await page.evaluate(() => {
    const hidden = ['.card-renderer__editor', '.card-renderer__toolbar', '.card-renderer__status',
      '.card-renderer__preview-toolbar', '.history-mobile-toggle'];
    for (const selector of hidden) {
      document.querySelectorAll(selector).forEach((element) => {
        element.style.visibility = 'hidden';
      });
    }
    let node = document.querySelector('.card-renderer__surface');
    while (node) {
      node.style.overflow = 'visible';
      node = node.parentElement;
    }
    document.documentElement.style.overflow = 'visible';
    document.body.style.overflow = 'visible';
  });
  const surface = page.locator('.card-renderer__surface').first();
  await surface.scrollIntoViewIfNeeded();
  await page.waitForTimeout(250);
  return surface;
}

async function renderOne(page, baseUrl, item) {
  await page.goto(`${baseUrl}/debug/renderer`, { waitUntil: 'domcontentloaded', timeout: 120_000 });
  const editor = page.locator('textarea').first();
  await editor.waitFor({ state: 'visible', timeout: 60_000 });
  await editor.fill(item.dsl);
  await page.locator('select').first().selectOption(item.size);
  const status = page.locator('.card-renderer__status').first();
  await page.getByRole('button', { name: 'Python 转换并渲染' }).first().click();
  // 该按钮会把编辑器内容换成完整 A2UI，以此确认转换已经跑完。
  await page.waitForFunction(
    () => (document.querySelector('textarea')?.value || '').includes('createSurface'),
    null,
    { timeout: 120_000 },
  );
  const runtimeError = page.locator('.card-renderer__runtime-error');
  if (await runtimeError.count()) {
    return { error: (await runtimeError.first().textContent())?.trim() || '卡片渲染失败' };
  }
  const surface = page.locator('.card-renderer__surface').first();
  await surface.waitFor({ state: 'visible', timeout: 120_000 });
  await settle(page);
  const text = (await status.count()) ? (await status.first().textContent()) || '' : '';
  if (/错误|失败/.test(text)) return { error: text.trim() };
  const isolated = await isolateCard(page);
  const box = await isolated.boundingBox();
  return { error: '', box, surface: isolated };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const manifestDir = path.dirname(path.resolve(args.manifest));
  const entries = JSON.parse(await fs.readFile(args.manifest, 'utf8'));
  await fs.mkdir(args.output, { recursive: true });
  const browser = await chromium.launch({
    executablePath: await browserExecutable(),
    headless: true,
  });
  const items = [];
  try {
    const page = await browser.newPage({
      viewport: { width: 1280, height: 900 },
      deviceScaleFactor: Number(args.scale) || 2,
    });
    for (const entry of entries) {
      const target = path.resolve(manifestDir, entry.file);
      const record = { id: entry.id, size: entry.size, file: `${entry.id}.png`, error: '' };
      try {
        const item = await renderOne(page, args['base-url'], {
          ...entry,
          dsl: await fs.readFile(target, 'utf8'),
        });
        record.error = item.error;
        if (!item.error) {
          // 用显式 clip 而不是元素截图：卡片所在窄栏可横向滚动，元素截图会连带拍到相邻面板。
          await page.screenshot({
            path: path.join(args.output, record.file),
            clip: {
              x: item.box.x,
              y: item.box.y,
              width: item.box.width,
              height: item.box.height,
            },
            scale: 'device',
          });
          record.width = Math.round(item.box?.width ?? 0);
          record.height = Math.round(item.box?.height ?? 0);
        }
      } catch (reason) {
        record.error = reason instanceof Error ? reason.message : String(reason);
      }
      items.push(record);
      console.error(`${record.id} ${record.size} → ${record.error ? `失败：${record.error}`
        : `${record.width}×${record.height}px ${record.file}`}`);
    }
  } finally {
    await browser.close();
  }
  await fs.writeFile(
    path.join(args.output, 'capture.json'),
    `${JSON.stringify({ items }, null, 2)}\n`,
    'utf8',
  );
  if (items.some((item) => item.error)) process.exitCode = 1;
}

main().catch((error) => {
  process.stderr.write(`渲染截图失败：${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
