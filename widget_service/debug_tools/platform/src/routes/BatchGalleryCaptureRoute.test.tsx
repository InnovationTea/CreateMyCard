import { cleanup, render, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { BatchGalleryCaptureRoute } from './BatchGalleryCaptureRoute';

function response(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as Response;
}

describe('BatchGalleryCaptureRoute', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    delete document.documentElement.dataset.galleryCapture;
  });

  it('uses final CardSpec size for gallery screenshots', async () => {
    const genui = [
      '{"version":"v0.9","createSurface":{"surfaceId":"surface_card"}}',
      '{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Text","content":"宽卡"}]}}',
    ].join('\n');
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url === '/debug/batch/runs/run_001') return response({
        runId: 'run_001', status: 'completed', samples: [{
          id: 'Q001', query: '请做一个 2x2 卡片', size: '2x2', status: 'success',
        }],
      });
      if (url.endsWith('/samples/Q001')) return response({
        summary: { id: 'Q001', finalAttempt: 0 },
        attempts: [{
          name: 'attempt_000',
          genui,
          blocks: { cardspec: { suggestSize: '2x4' } },
        }],
      });
      throw new Error(`unexpected fetch: ${url}`);
    });

    const { container } = render(
      <MemoryRouter initialEntries={['/batch/runs/run_001/gallery-capture']}>
        <Routes>
          <Route
            path="/batch/runs/:runId/gallery-capture"
            element={<BatchGalleryCaptureRoute />}
          />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(container.querySelector('[data-renderer-size="300x150"]')).toBeTruthy();
    });
    expect(container.querySelector('[data-card-size="2x4"]')).toBeTruthy();
    await waitFor(() => {
      expect(document.documentElement.dataset.galleryCapture).toBe('ready');
    });
  });
});
