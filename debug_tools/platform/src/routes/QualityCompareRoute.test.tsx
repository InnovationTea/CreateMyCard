import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QualityCompareRoute } from './QualityCompareRoute';
import type { QualityComparison } from '../batchApi';

const side = { score: 90, scoreLow: 80, verdict: '含待确认问题', query: '天气', size: '2x2', issues: {} };
const summary = { runId: 'left', executionId: 'e1', total: 2, scored: 2, passCount: 1, passRate: 50, meanScore: 90 };
const comparison: QualityComparison = {
  left: summary, right: { ...summary, runId: 'right', executionId: 'e2', passCount: 2, passRate: 100 },
  comparable: true, warnings: [], passRateDelta: 50, passDefinition: '待评不计通过，仅 Web 范围。',
  rows: [{ sampleId: 'Q1', alignment: 'matched', left: side, right: { ...side, score: 100 }, scoreDelta: 10,
    issueDiff: [{ code: 'text.clipped', left: 1, right: 0, delta: -1 }],
  }],
  issueDistribution: [{ code: 'text.clipped', left: 1, right: 0, delta: -1 }],
  confirmedIssueDistribution: [{ code: 'text.clipped', left: 1, right: 0, delta: -1 }],
  pendingIssueDistribution: [{ code: 'layout.overlap', left: 0, right: 1, delta: 1 }],
};
function response(body: unknown, status = 200): Response {
  return { ok: status < 400, status, json: async () => body } as Response;
}
function mockApi(value = comparison, status = 200) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input);
    if (url === '/debug/batch/runs') return response({ items: [
      { runId: 'left', name: null, status: 'completed' }, { runId: 'right', name: '新版', status: 'completed' },
    ] });
    if (url.startsWith('/debug/batch/quality/compare?')) return response(status === 200 ? value : { detail: '尚无已完成评分结果' }, status);
    throw new Error(`unexpected request: ${url}`);
  });
}
function open(path = '/quality/compare') {
  render(<MemoryRouter initialEntries={[path]}><QualityCompareRoute /></MemoryRouter>);
}

describe('QualityCompareRoute', () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it('loads chosen batches read-only and separates confirmed/suspected issues', async () => {
    const fetchMock = mockApi(); open();
    await within(screen.getByLabelText('右侧批次')).findByRole('option', { name: '新版 · right' });
    expect(fetchMock.mock.calls).toHaveLength(1);
    fireEvent.change(screen.getByLabelText('左侧批次'), { target: { value: 'left' } });
    fireEvent.change(screen.getByLabelText('右侧批次'), { target: { value: 'right' } });
    expect(fetchMock.mock.calls).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: '加载对比' }));
    expect(await screen.findByText('通过率差：+50.0 个百分点')).toBeInTheDocument();
    expect(screen.getByText('待评不计通过，仅 Web 范围。')).toBeInTheDocument();
    expect(screen.getByText('+10.0')).toBeInTheDocument();
    const confirmed = screen.getByRole('heading', { name: '确认问题' }).parentElement!;
    const pending = screen.getByRole('heading', { name: '疑似／待确认问题' }).parentElement!;
    expect(within(confirmed).getByText('text.clipped')).toBeInTheDocument();
    expect(within(pending).getByText('layout.overlap')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'left · e1' })).toHaveAttribute('href', '/batch/runs/left/postprocess/e1/plugins/quality-score');
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);
  });

  it('loads explicit historical executions from the URL and supports reloading unchanged inputs', async () => {
    const fetchMock = mockApi();
    open('/quality/compare?leftRunId=left&rightRunId=right&leftExecutionId=old%2F1&rightExecutionId=old%2B2');
    await screen.findByText('总体可比');
    const url = new URL(String(fetchMock.mock.calls.find(([input]) => String(input).includes('/compare?'))![0]), 'http://localhost');
    expect(url.searchParams.get('leftExecutionId')).toBe('old/1');
    expect(url.searchParams.get('rightExecutionId')).toBe('old+2');
    fireEvent.click(screen.getByRole('button', { name: '加载对比' }));
    await waitFor(() => expect(fetchMock.mock.calls.filter(([input]) => String(input).includes('/compare?'))).toHaveLength(2));
    await screen.findByText('总体可比');
  });

  it('shows missing/pending/mismatch rows without invented deltas, preserving comparable matched rows', async () => {
    mockApi({ ...comparison, comparable: false, passRateDelta: null, warnings: ['所选样本集合不同'],
      rows: [...comparison.rows,
        { sampleId: 'Q2', alignment: 'right-only', left: null, right: side, scoreDelta: null, issueDiff: [] },
        { sampleId: 'Q3', alignment: 'left-only', left: side, right: null, scoreDelta: null, issueDiff: [] },
        ...['context-missing', 'context-mismatch', 'policy-mismatch', 'evidence-mismatch', 'pending-score'].map((alignment) => ({
          sampleId: alignment, alignment, left: side, right: { ...side, score: null, scoreLow: null }, scoreDelta: null, issueDiff: [],
        })),
      ],
    });
    open('/quality/compare?leftRunId=left&rightRunId=right');
    await screen.findByText('总体不可直接比较');
    expect(screen.getByText('通过率差：不可比')).toBeInTheDocument();
    expect(screen.getByText('所选样本集合不同')).toBeInTheDocument();
    expect(screen.getByText('+10.0')).toBeInTheDocument();
    const missing = screen.getByText('Q2').closest('tr')!;
    expect(within(missing).getByText('缺失')).toBeInTheDocument();
    expect(within(missing).getByText('不可比')).toBeInTheDocument();
    for (const label of ['query / size 不一致', '评分口径不一致', '证据口径不一致']) {
      const row = screen.getByText(label).closest('tr')!;
      expect(within(row).getByText('不可比')).toBeInTheDocument();
      expect(within(row).getByText('待评')).toBeInTheDocument();
      expect(within(row).queryByText('0.0')).not.toBeInTheDocument();
    }
  });

  it('clears stale comparisons when inputs change and does not auto-reload', async () => {
    const fetchMock = mockApi(); open('/quality/compare?leftRunId=left&rightRunId=right');
    await screen.findByText('总体可比');
    fireEvent.change(screen.getByLabelText('左侧执行（可选）'), { target: { value: 'different' } });
    expect(screen.queryByText('总体可比')).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([input]) => String(input).includes('/compare?'))).toHaveLength(1);
  });

  it('shows 409 missing results as an error and never starts scoring', async () => {
    const fetchMock = mockApi(comparison, 409); open('/quality/compare?leftRunId=left&rightRunId=right');
    expect(await screen.findByRole('alert')).toHaveTextContent('尚无已完成评分结果');
    expect(screen.queryByText('总体可比')).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);
  });
});
