import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const repositoryRoot = resolve(__dirname, '../../../..');
const tsxCli = resolve(repositoryRoot, 'render/genui-sdk/node_modules/tsx/dist/cli.mjs');
const renderScript = resolve(
  repositoryRoot,
  'debug_tools/card_renderer/runtime/scripts/render-a2ui-static.ts',
);
const renderedFixtures = new Map<string, string>();

function renderFixture(runtime: 'debug' | 'platform', fixture: string): string {
  const cacheKey = `${runtime}:${fixture}`;
  const cached = renderedFixtures.get(cacheKey);
  if (cached !== undefined) return cached;
  const fixturePath = resolve(
    repositoryRoot,
    'debug_tools/card_renderer/fixtures',
    fixture,
  );
  const tsconfig = runtime === 'platform'
    ? resolve(repositoryRoot, 'debug_tools/card_renderer/runtime/scripts/tsconfig.platform-parity.json')
    : resolve(repositoryRoot, 'debug_tools/card_renderer/runtime/scripts/tsconfig.debug-parity.json');
  const markup = execFileSync(
    process.execPath,
    [tsxCli, '--tsconfig', tsconfig, renderScript, runtime, fixturePath],
    {
      encoding: 'utf8',
      env: { ...process.env, NODE_ENV: 'production' },
    },
  ).trim();
  renderedFixtures.set(cacheKey, markup);
  return markup;
}

describe('Debug Tools 与 render/platform 的 Renderer Runtime 一致性', () => {
  it.each([
    'a2ui.jsonl',
    'a2ui-visual-parity.jsonl',
  ])('%s 在隔离的两套包解析环境中产生相同 DOM', (fixture) => {
    expect(renderFixture('debug', fixture)).toBe(renderFixture('platform', fixture));
  });

  it('圆环关键视觉几何保持与 render/platform 一致', () => {
    const markup = renderFixture('debug', 'a2ui-visual-parity.jsonl');
    expect(markup).toContain('r="18"');
    expect(markup).toContain('stroke-width="6"');
    expect(markup).toContain('width:44px;height:44px');
  });
});
