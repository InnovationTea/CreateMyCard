// 离线画廊浏览器冒烟：node check_postprocess_gallery.mjs <HTML> <输出目录> [浏览器路径]
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { chromium } from 'playwright-core';

const [input, output, executablePath = process.env.WIDGET_DEBUG_GALLERY_BROWSER_EXECUTABLE] = process.argv.slice(2);
if (!input || !output || !executablePath) throw new Error('需要 HTML、输出目录及浏览器路径');
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ executablePath, headless: true });
const errors = [];
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => assert(!/^https?:/.test(request.url()), '离线画廊不能请求网络资源'));
  await page.goto(pathToFileURL(path.resolve(input)).href);
  const total = await page.locator('.case').count();
  assert(total > 0, '至少需要一个预览样本');
  await page.screenshot({ path: path.join(output, 'gallery-desktop.png'), fullPage: true });
  await page.selectOption('#columns', '3');
  await page.selectOption('#sort', 'latency');
  await page.click('#layout');
  assert.equal(await page.locator('#layout').getAttribute('aria-pressed'), 'true');
  assert.equal(await page.locator('.case-body').first().isVisible(), false);
  assert.equal(await page.locator('#cases').getAttribute('data-columns'), '3');
  await page.screenshot({ path: path.join(output, 'gallery-compact.png'), fullPage: true });
  await page.fill('#search', '不存在的样本-EMPTY');
  assert.equal(await page.locator('.case').count(), 0);
  assert.equal(await page.locator('.empty').count(), 1);
  await page.click('#reset');
  assert.equal(await page.locator('.case').count(), total);
  const image = page.locator('[data-zoom]').first();
  if (await image.count()) {
    await image.click();
    assert(await page.locator('#zoom').isVisible());
    await page.click('#close');
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.click('#layout');
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  assert.equal(overflow, false, '窄屏不能产生页面水平滚动');
  await page.screenshot({ path: path.join(output, 'gallery-mobile.png'), fullPage: true });
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ samples: total, errors, checks: 11, output }));
} finally {
  await browser.close();
}
