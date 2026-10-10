import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { PostprocessDashboardRoute } from './PostprocessDashboardRoute';

function response(value: unknown): Response {
  return { ok: true, json: async () => value } as Response;
}

describe('PostprocessDashboardRoute', () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('loads overview, filters samples and opens the sample inspector', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: string) => {
      const url = String(input);
      if (url === '/debug/batch/runs/run_1') return response({
        runId: 'run_1', status: 'completed', postprocessExecutions: [{
          executionId: 'post_1', status: 'completed', plugins: [{ id: 'component-recall' }],
        }],
      });
      if (url.endsWith('/dashboard')) return response({
        schemaVersion: 'batch-postprocess-dashboard-v2',
        runId: 'run_1', executionId: 'post_1', status: 'success',
        plugin: { id: 'component-recall', name: '组件召回分析', version: '1.0.0', apiVersion: 'batch-postprocess-v2' },
        presentation: { defaultView: 'table', sampleFields: [
          { key: 'recallRate', label: '召回率', type: 'number', format: 'percent', sortable: true },
          { key: 'missingComponents', label: '缺失', type: 'string-list', filterable: true },
        ] },
        outputs: [], counts: { success: 1, failed: 1 }, totalSamples: 2,
        datasetResult: { status: 'partial', summary: '已评估 2/88 个样本', artifacts: [{
          key: 'overview', title: '召回率汇总', dataType: 'metrics', renderer: 'kpi',
          data: [{ label: '已评估样本', value: '16/88' }],
        }] },
        samples: [
          { sampleId: 'Q001', title: '天气', sequence: 1, status: 'success', summary: '完整', facts: { recallRate: 100, missingComponents: [] }, artifacts: [] },
          { sampleId: 'Q002', title: '日程', sequence: 2, status: 'failed', summary: '缺失', facts: { recallRate: 0, missingComponents: ['EventCard'] }, artifacts: [] },
        ],
      });
      if (url.includes('/samples?')) return response({
        total: 2, offset: 0, limit: 25, items: [
          { sampleId: 'Q001', title: '天气', sequence: 1, status: 'success', summary: '完整', facts: { recallRate: 100, missingComponents: [] }, artifacts: [] },
          { sampleId: 'Q002', title: '日程', sequence: 2, status: 'failed', summary: '缺失', facts: { recallRate: 0, missingComponents: ['EventCard'] }, artifacts: [] },
        ],
      });
      if (url.endsWith('/samples/Q001')) return response({ sampleId: 'Q001', status: 'success', summary: '召回 2/2', facts: { recallRate: 100 }, artifacts: [] });
      if (url.endsWith('/samples/Q002')) return response({ sampleId: 'Q002', status: 'failed', summary: '召回 0/2', facts: { recallRate: 0 }, artifacts: [] });
      throw new Error(`unexpected request: ${url}`);
    }));

    const { unmount } = render(<MemoryRouter initialEntries={[
      '/batch/runs/run_1/postprocess/post_1/plugins/component-recall',
    ]}><Routes><Route
      path="/batch/runs/:runId/postprocess/:executionId/plugins/:pluginId"
      element={<PostprocessDashboardRoute />}
    /></Routes></MemoryRouter>);

    expect(await screen.findByRole('heading', { name: '组件召回分析' })).toBeInTheDocument();
    expect(document.documentElement).toHaveClass('postprocess-dashboard-active');
    expect(document.body).toHaveClass('postprocess-dashboard-active');
    expect(screen.getByText('16/88')).toBeInTheDocument();
    fireEvent.click(await screen.findByText('Q002'));
    expect(await screen.findByText('召回 0/2')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('全部状态'), { target: { value: 'failed' } });
    await waitFor(() => expect(vi.mocked(fetch).mock.calls.some(([url]) => (
      String(url).includes('status=failed')
    ))).toBe(true));
    unmount();
    expect(document.documentElement).not.toHaveClass('postprocess-dashboard-active');
    expect(document.body).not.toHaveClass('postprocess-dashboard-active');
  });

  it('reruns only the quality dashboard subset and opens the new dashboard after completion', async () => {
    let finish!: (value: Response) => void;
    vi.stubGlobal('fetch', vi.fn(async (input: string, init?: RequestInit) => {
      if (init?.method === 'POST') return response({ executionId: 'new_score', status: 'queued' });
      if (input.endsWith('/postprocess/new_score')) return new Promise<Response>((resolve) => { finish = resolve; });
      if (input === '/debug/batch/runs/run_1') return response({ runId: 'run_1', status: 'completed', total: 88,
        postprocessExecutions: [{ executionId: 'old_score', plugins: [{ id: 'quality-score' }], status: 'partial' }],
      });
      if (input.endsWith('/dashboard')) return response({
        runId: 'run_1', executionId: 'old_score', status: 'partial', plugin: { id: 'quality-score', name: '质量评分' },
        presentation: { defaultView: 'table', sampleFields: [] }, samples: [], totalSamples: 2, sourceTotalSamples: 88,
        selection: { sampleIds: ['Q2', 'Q5'], count: 2 },
        datasetResult: { status: 'partial', artifacts: [{ key: 'policy', dataType: 'json', data: { version: 'historical-v1' } }] },
      });
      if (input.includes('/samples?')) return response({ items: [], total: 0 });
      throw new Error(`unexpected request: ${input}`);
    }));
    render(<MemoryRouter initialEntries={['/batch/runs/run_1/postprocess/old_score/plugins/quality-score']}><Routes>
      <Route path="/batch/runs/run_1/postprocess/new_score/plugins/quality-score" element={<h1>新评分结果</h1>} />
      <Route path="/batch/runs/:runId/postprocess/:executionId/plugins/:pluginId" element={<PostprocessDashboardRoute />} />
    </Routes></MemoryRouter>);
    await screen.findByRole('heading', { name: '质量评分' });
    expect(screen.getByText(/本次 2 \/ 来源 88/)).toBeInTheDocument();
    expect(screen.getByText(/historical-v1/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '选择批次' })).toHaveAttribute('href', '/quality?runId=run_1');
    expect(screen.getByRole('link', { name: '评估方案（当前版本）' })).toHaveAttribute('href', '/quality/evaluation');
    expect(screen.getByRole('link', { name: '批次对比' })).toHaveAttribute('href', '/quality/compare?leftRunId=run_1&leftExecutionId=old_score');
    expect(vi.mocked(fetch).mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: '↻ 再次运行' }));
    await waitFor(() => expect(finish).toBeDefined());
    const post = vi.mocked(fetch).mock.calls.find(([, init]) => init?.method === 'POST');
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ pluginIds: ['quality-score'], configs: { 'quality-score': { sampleIds: ['Q2', 'Q5'] } }, rerun: true });
    expect(screen.queryByText('新评分结果')).not.toBeInTheDocument();
    expect(screen.getByLabelText('历史执行')).toBeDisabled();
    finish(response({ status: 'partial', plugins: [{ id: 'quality-score', status: 'partial' }] }));
    expect(await screen.findByText('新评分结果')).toBeInTheDocument();
  });

  it('keeps generic plugin rerun behavior and does not attach quality links', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: string, init?: RequestInit) => {
      if (init?.method === 'POST') return response({ executionId: 'new_generic' });
      if (input === '/debug/batch/runs/run_1') return response({ runId: 'run_1', status: 'completed', postprocessExecutions: [] });
      if (input.endsWith('/dashboard')) return response({
        plugin: { id: 'component-recall', name: '组件召回分析' }, presentation: {}, samples: [], datasetResult: {}, totalSamples: 1,
      });
      if (input.includes('/samples?')) return response({ items: [], total: 0 });
      throw new Error(`unexpected request: ${input}`);
    }));
    render(<MemoryRouter initialEntries={['/batch/runs/run_1/postprocess/old/plugins/component-recall']}><Routes>
      <Route path="/batch/runs/run_1/postprocess/new_generic/plugins/component-recall" element={<h1>通用看板</h1>} />
      <Route path="/batch/runs/:runId/postprocess/:executionId/plugins/:pluginId" element={<PostprocessDashboardRoute />} />
    </Routes></MemoryRouter>);
    await screen.findByRole('heading', { name: '组件召回分析' });
    expect(screen.queryByRole('link', { name: '选择批次' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '↻ 再次运行' }));
    expect(await screen.findByText('通用看板')).toBeInTheDocument();
    const post = vi.mocked(fetch).mock.calls.find(([, init]) => init?.method === 'POST');
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ pluginIds: ['component-recall'], configs: {}, rerun: true });
  });
});
