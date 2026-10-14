import assert from 'node:assert/strict';
import { chromium } from 'playwright-core';
import { collectWebQuality } from './web_quality.mjs';

const browser = await chromium.launch({
  executablePath: process.env.WIDGET_DEBUG_GALLERY_BROWSER_EXECUTABLE,
  channel: process.env.WIDGET_DEBUG_GALLERY_BROWSER_EXECUTABLE ? undefined : 'msedge',
  headless: true,
});
try {
  const page = await browser.newPage();
  async function measure(body) {
    await page.setContent(`<div class="card-renderer__surface" style="position:relative;width:160px;height:160px;overflow:hidden;font:14px Arial">${body}</div>`);
    return page.locator('.card-renderer__surface').evaluate(collectWebQuality);
  }
  const clean = await measure('<p data-node-id="title">正常文字</p>');
  assert.equal(clean.findings.length, 0);
  const clipped = await measure('<p data-node-id="t" style="width:20px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">Long long long text</p>');
  assert(clipped.findings.some((x) => x.rule_id === 'GEOMETRY.CLIP_TEXT'));
  const clamp = await measure('<p data-node-id="t" style="width:30px;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:1;overflow:hidden">Long text more more more</p>');
  assert(clamp.findings.some((x) => x.rule_id === 'GEOMETRY.CLIP_TEXT'));
  const nested = await measure('<div data-node-id="button"><span data-node-id="label">Label</span></div>');
  assert.equal(nested.findings.length, 0);
  const overlap = await measure('<p data-node-id="a" style="position:absolute;top:0">AAAA</p><p data-node-id="b" style="position:absolute;top:0">BBBB</p>');
  assert(overlap.findings.some((x) => x.rule_id === 'GEOMETRY.OVERLAP_TEXT' && x.evidence_type === '待确认'));
  const offscreen = await measure('<p data-node-id="a" style="position:absolute;top:150px">AAAA</p>');
  assert(offscreen.findings.some((x) => x.rule_id === 'GEOMETRY.CLIP_TEXT'));
  const hidden = await measure('<p data-node-id="a" style="display:none">AAAA</p>');
  assert.equal(hidden.findings.length, 0);
  assert.equal(hidden.complete, false);
  const scroll = await measure('<div style="height:20px;overflow:auto"><p data-node-id="a">AAAA<br>BBBB</p></div>');
  assert.equal(scroll.findings.length, 0);
  assert(scroll.excludedScrollable > 0);
  const missing = await measure('<span data-node-id="icon" role="img" aria-label="素材未找到：test.svg">?</span>');
  assert(missing.findings.some((x) => x.rule_id === 'ASSET.WEB_LOAD_FAILED'));
  console.log('9 个真实浏览器检测场景通过');
} finally {
  await browser.close();
}
