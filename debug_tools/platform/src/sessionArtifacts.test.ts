import { describe, expect, it } from 'vitest';
import { sessionArtifacts } from './sessionArtifacts';
import type { ToolCallRecord } from './types';

const DSL = '{"version":"v0.9","updateComponents":{"surfaceId":"s","root":"root","components":[]}}';

function call(patch: Partial<ToolCallRecord>): ToolCallRecord {
  return {
    id: 'call-1', operation: 'generateWidgetCardCompactDsl', source: 'e2e',
    status: 'success', startedAt: '2026-10-17T08:00:00.000Z', ...patch,
  } as ToolCallRecord;
}

describe('sessionArtifacts', () => {
  it('reads the DSL, the query and the suggested size out of a successful call', () => {
    const items = sessionArtifacts([call({
      request: { utterance: { original: '做个天气卡片' } },
      response: { operation: 'x', status: 'success', data: { genui: DSL, cardSpec: { suggestSize: '2x4' } } },
    })]);
    expect(items).toEqual([{
      id: 'call-1', title: '端到端 · generateWidgetCardCompactDsl', query: '做个天气卡片',
      genui: DSL, size: '2x4', status: 'success', at: '2026-10-17T08:00:00.000Z',
    }]);
  });

  it('falls back to the streamed final content and the request envelope', () => {
    const items = sessionArtifacts([call({
      source: 'interface',
      request: { content: { userQuery: '电量卡片' } },
      finalStreamContent: `{'genui': '${DSL.replace(/'/g, "\\'")}'}`,
    })]);
    expect(items).toHaveLength(1);
    expect(items[0].query).toBe('电量卡片');
    expect(items[0].genui).toContain('updateComponents');
    expect(items[0].title).toBe('接口调试 · generateWidgetCardCompactDsl');
  });

  it('skips failed calls and calls that carry no DSL', () => {
    const items = sessionArtifacts([
      call({ id: 'bad', status: 'error', response: { operation: 'x', status: 'error', data: { genui: DSL } } }),
      call({ id: 'empty', response: { operation: 'x', status: 'success', data: { cardSpec: {} } } }),
      call({ id: 'ok', response: { operation: 'x', status: 'success', data: { genui: DSL } } }),
    ]);
    expect(items.map((item) => item.id)).toEqual(['ok']);
  });
});
