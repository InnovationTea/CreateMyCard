import { describe, expect, it } from 'vitest';
import { SAMPLE_A2UI, SAMPLE_COMPACT, SAMPLE_DESIGN } from '../src/fixtures';
import { parseInput, resolveCardSize, resolveTemplate, sizeForCard } from '../src/parser';

describe('card renderer parser', () => {
  it.each([
    ['A2UI', SAMPLE_A2UI],
    ['Compact DSL', SAMPLE_COMPACT],
    ['Design Compact DSL', SAMPLE_DESIGN],
  ])('recognizes %s fixtures', (expectedMode, source) => {
    const document = parseInput(source);
    expect(document.mode).toBe(expectedMode);
    expect(document.components.size).toBeGreaterThan(0);
    expect(document.surface.width).toBeGreaterThan(0);
    expect(document.surface.height).toBeGreaterThan(0);
  });

  it('resolves data model template expressions', () => {
    expect(resolveTemplate('天气：{{weather.city}}', { weather: { city: '上海' } })).toBe('天气：上海');
  });

  it('infers stable 2x2 and 2x4 surfaces', () => {
    expect(sizeForCard('2x2')).toEqual({ width: 150, height: 150 });
    expect(sizeForCard('2x4')).toEqual({ width: 300, height: 150 });
  });

  it('resolves size from final CardSpec before query and sample fallback', () => {
    expect(resolveCardSize(
      { suggestSize: '2x4' },
      '请生成一个 2x2 卡片',
      '2x2',
    )).toBe('2x4');
    expect(resolveCardSize(null, '请生成一个 2×4 卡片')).toBe('2x4');
    expect(resolveCardSize(null, '做一个普通天气卡片', '2*4')).toBe('2x4');
    expect(resolveCardSize(null, '做一个普通天气卡片')).toBe('auto');
  });

  it('reads CardSpec size from artifact envelopes and JSON text', () => {
    expect(resolveCardSize({ cardspec: { suggestSize: '2x4' } }, '')).toBe('2x4');
    expect(resolveCardSize('{"cardSpec":{"suggestSize":"2x2"}}', '')).toBe('2x2');
  });

  it('accepts single-component A2UI updates and artifact envelopes', () => {
    const genui = [
      '{"version":"v0.9","createSurface":{"surfaceId":"card","width":180,"height":120}}',
      '{"version":"v0.9","updateComponents":{"surfaceId":"card","component":{"id":"root","component":"Extended.Text","content":{"path":"/title"}}}}',
      '{"version":"v0.9","updateDataModel":{"surfaceId":"card","path":"/title","value":"单条更新"}}',
    ].join('\n');
    const document = parseInput(JSON.stringify({ artifact: { genui } }));

    expect(document.mode).toBe('A2UI');
    expect(document.surface).toEqual({ width: 180, height: 120 });
    expect(document.graph.getRoot()?.type).toBe('Extended.Text');
    expect(document.graph.getDataModelValue('card', '/title')).toBe('单条更新');
  });

  it('keeps valid graph commands when another record is malformed', () => {
    const document = parseInput([
      '{"root":{"type":"Extended.Text","props":{"content":"可渲染"}}}',
      '{broken}',
    ].join('\n'));

    expect(document.graph.getRoot()?.id).toBe('root');
    expect(document.warnings).toHaveLength(1);
  });

  it('honors an explicit card size over input dimensions', () => {
    const document = parseInput(SAMPLE_A2UI, { cardSize: '2x4' });
    expect(document.surface).toEqual({ width: 300, height: 150 });
  });
});
