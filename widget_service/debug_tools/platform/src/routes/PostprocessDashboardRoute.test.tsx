import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { PostprocessDashboardRoute } from './PostprocessDashboardRoute';

function response(value: unknown): Response {
  return { ok: true, json: async () => value } as Response;
}

describe('PostprocessDashboardRoute', () => {
  afterEach(() => vi.unstubAllGlobals());

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
});
