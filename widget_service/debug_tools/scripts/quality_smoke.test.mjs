// 使用真实 React 渲染器与截图入口；仅替换批跑 API 为确定性测试输入，不调用模型。
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { createServer } from 'vite';

const toolsRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const output = await fs.mkdtemp(path.join(os.tmpdir(), 'web-quality-smoke-'));
const cards = [
  { id: 'clean', source: '["root","Column",{"width":160,"height":160},["text"]]\n["text","Text",{"content":"正常文字","fontSize":14}]' },
  { id: 'clipped', source: '["root","Column",{"width":160,"height":160},["text"]]\n["text","Text",{"content":"文字应该完整显示而不是截断","width":30,"maxLines":1,"fontSize":14}]' },
  { id: 'invalid', source: 'this is not DSL' },
];
const samples = cards.map((x) => ({ id: x.id, query: '测试卡片', size: '2x2', status: 'success', finalAttempt: 0 }));
const summary = { runId: 'quality-smoke', samples, total: cards.length };
const server = await createServer({
  root: path.join(toolsRoot, 'platform'),
  configFile: path.join(toolsRoot, 'platform/vite.config.ts'),
  server: { host: '127.0.0.1', port: 0, open: false },
  plugins: [{ name: 'quality-test-inputs', configResolved(config) { config.server.proxy = {}; }, configureServer(vite) {
    vite.middlewares.use((req, res, next) => {
      let body;
      if (req.url === '/debug/batch/runs/quality-smoke') body = summary;
      const card = cards.find((x) => req.url === `/debug/batch/runs/quality-smoke/samples/${x.id}`);
      if (card) body = { summary: samples.find((x) => x.id === card.id), attempts: [{
        name: 'attempt_000', genui: card.source, blocks: { cardspec: { suggestSize: '2x2' } },
      }] };
      if (!body) { next(); return; }
      res.setHeader('Content-Type', 'application/json');
      res.end(JSON.stringify(body));
    });
  } }],
});
try {
  await server.listen();
  const port = server.httpServer.address().port;
  await new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [path.join(toolsRoot, 'scripts/capture_batch_gallery.mjs'),
      '--url', `http://127.0.0.1:${port}/debug/batch/runs/quality-smoke/gallery-capture`, '--output', output],
    { stdio: 'inherit', windowsHide: true });
    child.on('error', reject);
    child.on('exit', (code) => code === 0 ? resolve() : reject(new Error(`capture exit ${code}`)));
  });
  const capture = JSON.parse(await fs.readFile(path.join(output, 'capture.json'), 'utf8'));
  assert.equal(capture.items.length, 3);
  const clean = capture.items.find((x) => x.id === 'clean');
  const clipped = capture.items.find((x) => x.id === 'clipped');
  const invalid = capture.items.find((x) => x.id === 'invalid');
  assert.equal(clean.quality.findings.length, 0);
  assert(clipped.quality.findings.some((x) => x.rule_id === 'GEOMETRY.CLIP_TEXT'));
  assert.equal(invalid.quality.renderFailed, true);
  assert.match(clean.quality.sourceSha256, /^[a-f0-9]{64}$/);
  assert.match(clean.quality.imageSha256, /^[a-f0-9]{64}$/);
  for (const card of cards) {
    const dir = path.join(output, card.id, 'attempt_000');
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(path.join(dir, 'genui.jsonl'), card.source);
    await fs.writeFile(path.join(dir, 'blocks.json'), JSON.stringify({ cardspec: { suggestSize: '2x2' } }));
    await fs.writeFile(path.join(output, card.id, 'result.json'), JSON.stringify({ finalAttempt: 0 }));
  }
  await fs.writeFile(path.join(output, 'summary.json'), JSON.stringify(summary));
  console.log(`真实网页链路 3 张卡通过；证据目录：${output}`);
} finally {
  await server.close();
}
