// 浏览器输入/展示回归：API 使用明确测试夹具；不生成业务数据，不运行生产模型。
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';
import { createServer } from 'vite';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const output = await fs.mkdtemp(path.join(os.tmpdir(), 'quality-input-ui-'));
const server = await createServer({
  root: path.join(root, 'platform'), configFile: path.join(root, 'platform/vite.config.ts'),
  server: { host: '127.0.0.1', port: 0, open: false },
});
let browser;
try {
  await server.listen();
  browser = await chromium.launch({
    executablePath: process.env.WIDGET_DEBUG_GALLERY_BROWSER_EXECUTABLE,
    channel: process.env.WIDGET_DEBUG_GALLERY_BROWSER_EXECUTABLE ? undefined : 'msedge', headless: true,
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1080 } });
  await page.setContent('<div style="width:280px;height:160px;background:#dceeff;border-radius:24px;padding:24px;font:24px sans-serif">天气测试卡片<br>测试输入，非业务样本</div>');
  const picture = await page.locator('div').screenshot();
  const origin = `http://127.0.0.1:${server.httpServer.address().port}`;
  const sample = { id: 'Q001', query: '显示天气', size: '2x2', status: 'imported' };
  const run = (id) => ({ runId: id, name: id, status: 'completed', sourceType: 'external-quality',
    startedAt: '2026-10-14T00:00:00Z', total: 1, samples: [sample], postprocessExecutions: [] });
  const summary = (id) => ({ runId: id, executionId: 'e1', total: 1, scored: 1, passCount: 0, passRate: 0, meanScore: 85 });
  const side = (id) => ({ sampleId: 'Q001', query: sample.query, size: sample.size,
    score: 85, scoreLow: 70, verdict: '测试夹具', issues: {}, imageUrl: `/debug/batch/runs/${id}/picture.png` });
  const posts = [];
  await page.route('**/debug/batch/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    let body;
    if (url.pathname.endsWith('/picture.png')) {
      await route.fulfill({ contentType: 'image/png', body: picture }); return;
    }
    if (request.method() === 'POST') {
      posts.push(url.pathname);
      assert.equal(url.pathname, '/debug/batch/quality/import');
      const data = request.postDataJSON();
      assert.equal(data.samples[0].query, sample.query);
      assert.equal(data.samples[0].dsl, '\ufeff[]\r\n');
      assert.deepEqual(Buffer.from(data.samples[0].imageBase64, 'base64'), picture);
      body = run('imported');
    } else if (url.pathname === '/debug/batch/runs') body = { items: [run('before'), run('after'), run('imported')] };
    else if (url.pathname.startsWith('/debug/batch/runs/')) body = run(url.pathname.split('/').at(-1));
    else if (url.pathname === '/debug/batch/quality/compare') body = {
      left: summary('before'), right: summary('after'), comparable: true, warnings: [], passRateDelta: 0,
      passDefinition: '测试批次无问题样本比例', issueDistribution: [],
      rows: [{ sampleId: '单条对比', alignment: 'matched', left: side('before'), right: side('after'),
        scoreDelta: 0, scoreLowDelta: 0, issueDiff: [] }],
    };
    else throw new Error(`未声明测试请求 ${url.pathname}`);
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.goto(`${origin}/debug/quality/import`);
  await page.getByRole('heading', { name: '导入已有卡片' }).waitFor();
  assert.equal(posts.length, 0);
  await page.getByLabel('Query', { exact: true }).fill(sample.query);
  await page.getByLabel('DSL 文件', { exact: true }).setInputFiles({ name: 'Q001.jsonl', mimeType: 'application/json', buffer: Buffer.from('\ufeff[]\r\n') });
  await page.getByLabel('截图文件', { exact: true }).setInputFiles({ name: 'Q001.png', mimeType: 'image/png', buffer: picture });
  await page.getByRole('button', { name: '导入并选择评分样本' }).click();
  await page.waitForURL('**/debug/quality?runId=imported');
  await page.getByRole('cell', { name: 'Q001', exact: true }).waitFor();
  assert.equal(posts.length, 1);
  await page.goto(`${origin}/debug/quality/compare?leftRunId=before&rightRunId=after&leftSampleId=Q001&rightSampleId=Q001`);
  await page.getByRole('heading', { name: '单条优化前后对比', exact: true }).waitFor();
  await page.waitForFunction(() => [...document.querySelectorAll('.quality-summary img')].filter((img) => img.complete && img.naturalWidth > 0).length === 2);
  const boxes = await page.locator('.quality-summary img').evaluateAll((images) => images.map((img) => ({ x: img.getBoundingClientRect().x, width: img.getBoundingClientRect().width })));
  assert(boxes[0].x + boxes[0].width <= boxes[1].x);
  assert.deepEqual(posts, ['/debug/batch/quality/import']);
  const panel = page.getByRole('heading', { name: '单条优化前后对比', exact: true }).locator('..');
  await panel.screenshot({ path: path.join(output, 'single-compare.png') });
  console.log(`浏览器单条上传、无自动评分、两侧图片加载与并列布局通过；测试截图：${output}`);
} finally {
  await browser?.close();
  await server.close();
}
