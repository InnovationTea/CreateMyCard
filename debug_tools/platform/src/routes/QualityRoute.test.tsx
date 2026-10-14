import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QualityRoute } from './QualityRoute';

const samples = [
  { id: 'Q1', query: '天气卡片', size: '2x2', status: 'success' },
  { id: 'Q2', query: '日程卡片', size: '2x4', status: 'failed' },
  { id: 'Q3', query: '运动卡片', size: '2x2', status: 'degraded' },
];
const run = { runId: 'run_1', name: null, status: 'completed', total: 3, samples };
const execution = { executionId: 'score_1', status: 'completed', plugins: [{ id: 'quality-score', status: 'success' }] };

function response(body: unknown, status = 200): Response {
  return { ok: status < 400, status, json: async () => body } as Response;
}

function mockApi() {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input);
    if (url === '/debug/batch/runs') return response({ items: [run,
      { ...run, runId: 'run_2', name: '另一个已完成批次' }, { ...run, runId: 'unfinished', status: 'running' },
    ] });
    if (url === '/debug/batch/runs/run_1') return response(run);
    if (url === '/debug/batch/runs/run_2') return response({ ...run, runId: 'run_2' });
    if (url.endsWith('/postprocess') && init?.method === 'POST') return response({ ...execution, status: 'queued' });
    if (url.endsWith('/postprocess/score_1')) return response(execution);
    throw new Error(`unexpected request: ${url}`);
  });
}

function open(path = '/quality?runId=run_1') {
  return render(<MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/quality" element={<QualityRoute />} />
    <Route path="/batch/runs/:runId/postprocess/:executionId/plugins/quality-score" element={<h1>原评分看板</h1>} />
  </Routes></MemoryRouter>);
}

function posts() { return vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === 'POST'); }

describe('QualityRoute', () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.useRealTimers(); });

  it('only imports completed historical runs and never starts or polls on entry/confirmation', async () => {
    mockApi(); open('/quality');
    expect(await screen.findByRole('option', { name: /另一个已完成批次/ })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: /unfinished/ })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('已完成批次'), { target: { value: 'run_1' } });
    expect(await screen.findByText('天气卡片')).toBeInTheDocument();
    expect(screen.getByText('2x4')).toBeInTheDocument();
    expect(screen.getByText('failed')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '运行评分' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '确认导入样本' }));
    expect(screen.getByRole('button', { name: '运行评分' })).toBeEnabled();
    expect(posts()).toHaveLength(0);
    expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).includes('/postprocess'))).toBe(false);
  });

  it.each([
    ['all', ['Q1', 'Q2', 'Q3']], ['count', ['Q1', 'Q2']],
    ['ids', ['Q1', 'Q3']], ['checkbox', ['Q1', 'Q3']],
  ])('submits the %s selection only on explicit run, retaining original sample order', async (mode, ids) => {
    mockApi(); open();
    await screen.findByText('天气卡片');
    if (mode === 'checkbox') fireEvent.click(screen.getByLabelText('选择样本 Q2'));
    else fireEvent.change(screen.getByLabelText('样本范围'), { target: { value: mode } });
    if (mode === 'count') fireEvent.change(screen.getByLabelText('前 N 条'), { target: { value: '2' } });
    if (mode === 'ids') fireEvent.change(screen.getByLabelText('样本 ID'), { target: { value: 'Q3，Q1' } });
    fireEvent.click(screen.getByRole('button', { name: '确认导入样本' }));
    expect(posts()).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: '运行评分' }));
    expect(await screen.findByRole('heading', { name: '原评分看板' })).toBeInTheDocument();
    expect(posts()).toHaveLength(1);
    expect(JSON.parse(String(posts()[0][1]?.body))).toEqual({
      pluginIds: ['quality-score'], configs: { 'quality-score': { sampleIds: ids } }, rerun: true,
    });
  });

  it('revokes confirmation when mode, count, IDs, checkboxes or batch changes', async () => {
    mockApi(); open(); await screen.findByText('天气卡片');
    const confirm = () => fireEvent.click(screen.getByRole('button', { name: '确认导入样本' }));
    const disabled = () => expect(screen.getByRole('button', { name: '运行评分' })).toBeDisabled();
    confirm(); fireEvent.change(screen.getByLabelText('样本范围'), { target: { value: 'count' } }); disabled();
    confirm(); fireEvent.change(screen.getByLabelText('前 N 条'), { target: { value: '2' } }); disabled();
    confirm(); fireEvent.click(screen.getByLabelText('选择样本 Q3')); disabled();
    fireEvent.change(screen.getByLabelText('样本范围'), { target: { value: 'ids' } });
    fireEvent.change(screen.getByLabelText('样本 ID'), { target: { value: 'Q1' } }); confirm();
    fireEvent.change(screen.getByLabelText('样本 ID'), { target: { value: 'Q2' } }); disabled();
    confirm(); fireEvent.change(screen.getByLabelText('已完成批次'), { target: { value: 'run_2' } });
    await screen.findByText('天气卡片'); disabled(); expect(posts()).toHaveLength(0);
  });

  it('rejects empty, duplicate, unknown IDs and invalid counts before confirming', async () => {
    mockApi(); open(); await screen.findByText('天气卡片');
    fireEvent.change(screen.getByLabelText('样本范围'), { target: { value: 'ids' } });
    for (const value of ['', 'Q1 Q1', 'UNKNOWN']) {
      fireEvent.change(screen.getByLabelText('样本 ID'), { target: { value } });
      expect(screen.getByRole('button', { name: '确认导入样本' })).toBeDisabled();
    }
    fireEvent.change(screen.getByLabelText('样本范围'), { target: { value: 'count' } });
    for (const value of ['0', '-1', '1.5', '4']) {
      fireEvent.change(screen.getByLabelText('前 N 条'), { target: { value } });
      expect(screen.getByRole('button', { name: '确认导入样本' })).toBeDisabled();
    }
    expect(posts()).toHaveLength(0);
  });

  it('blocks double clicks and waits for terminal execution before navigating', async () => {
    const fetchMock = mockApi(); open(); await screen.findByText('天气卡片');
    vi.useFakeTimers();
    let polls = 0;
    fetchMock.mockImplementation(async (input, init) => {
      if (init?.method === 'POST') return response({ ...execution, status: 'queued' });
      polls++;
      return response({ ...execution, status: polls === 1 ? 'running' : 'partial' });
    });
    fireEvent.click(screen.getByRole('button', { name: '确认导入样本' }));
    await act(async () => {
      const button = screen.getByRole('button', { name: '运行评分' });
      fireEvent.click(button); fireEvent.click(button);
    });
    expect(posts()).toHaveLength(1);
    expect(screen.getByRole('button', { name: '正在评分…' })).toBeDisabled();
    expect(screen.getByLabelText('已完成批次')).toBeDisabled();
    expect(screen.queryByText('原评分看板')).not.toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(screen.getByText('原评分看板')).toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(polls).toBe(2);
  });

  it.each(['submit', 'failed', 'plugin', 'missing', 'network'])('shows %s errors without navigating or automatically retrying', async (failure) => {
    const fetchMock = mockApi(); open(); await screen.findByText('天气卡片');
    fetchMock.mockImplementation(async (_, init) => {
      if (init?.method === 'POST') return failure === 'submit' ? response({ detail: '提交失败' }, 409) : response(execution);
      if (failure === 'network') throw new Error('状态读取失败');
      return response({ ...execution, status: ['plugin', 'missing'].includes(failure) ? 'partial' : 'failed', error: '评分执行失败',
        plugins: failure === 'missing' ? [] : [{ id: 'quality-score', status: 'failed', datasetResult: { summary: '评分失败' } }],
      });
    });
    fireEvent.click(screen.getByRole('button', { name: '确认导入样本' }));
    fireEvent.click(screen.getByRole('button', { name: '运行评分' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/失败/);
    expect(screen.queryByText('原评分看板')).not.toBeInTheDocument();
    expect(posts()).toHaveLength(1);
  });

  it('ignores a late sample response from the previously selected batch', async () => {
    const fetchMock = mockApi();
    const original = fetchMock.getMockImplementation()!;
    let resolveOld!: (value: Response) => void;
    fetchMock.mockImplementation((input, init) => String(input) === '/debug/batch/runs/run_1'
      ? new Promise((resolve) => { resolveOld = resolve; }) : original(input, init));
    open();
    await screen.findByRole('option', { name: /另一个已完成批次/ });
    fireEvent.change(screen.getByLabelText('已完成批次'), { target: { value: 'run_2' } });
    await screen.findByText('天气卡片');
    await act(async () => { resolveOld(response({ ...run, samples: [{ ...samples[0], query: '旧响应' }] })); });
    expect(screen.queryByText('旧响应')).not.toBeInTheDocument();
    expect(within(screen.getByRole('table')).getAllByRole('checkbox')).toHaveLength(3);
    expect(posts()).toHaveLength(0);
  });
});
