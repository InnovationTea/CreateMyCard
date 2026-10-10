import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { BatchTraceRoute } from './BatchTraceRoute';

function renderPage() {
  render(<MemoryRouter initialEntries={['/batch/runs/run_001/samples/Q001/trace']}>
    <Routes><Route path="/batch/runs/:runId/samples/:sampleId/trace" element={<BatchTraceRoute />} /></Routes>
  </MemoryRouter>);
}

describe('BatchTraceRoute', () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it('loads a sample directly from its URL and refreshes independently', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, json: async () => ({ summary: { id: 'Q001', title: '天气' }, attempts: [] }),
    } as Response);
    renderPage();
    expect(await screen.findByText('该样本没有可用 Trace')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Q001 · Trace 链路' })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith('/debug/batch/runs/run_001/samples/Q001', undefined);
    await userEvent.click(screen.getByRole('button', { name: '刷新' }));
    expect(await screen.findByText('该样本没有可用 Trace')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('shows a local load failure and allows retry', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new Error('样本不存在'))
      .mockResolvedValue({ ok: true, json: async () => ({ summary: { id: 'Q001' }, attempts: [] }) } as Response);
    renderPage();
    expect(await screen.findByRole('alert')).toHaveTextContent('样本不存在');
    await userEvent.click(screen.getByRole('button', { name: '刷新' }));
    expect(await screen.findByText('该样本没有可用 Trace')).toBeInTheDocument();
  });
});
