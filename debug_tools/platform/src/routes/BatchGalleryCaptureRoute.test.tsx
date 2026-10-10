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

  it.each(['A2UI', 'Compact DSL'])('uses final CardSpec size for %s gallery screenshots', async (mode) => {
    const genui = [
      '{"version":"v0.9","createSurface":{"surfaceId":"surface_card"}}',
      '{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Text","content":"宽卡"}]}}',
    ].join('\n');
    const source = mode === 'Compact DSL' ? '["root","Text",{"content":"宽卡"}]' : genui;
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, options) => {
      const url = String(input);
      if (url === '/debug/renderer/convert') {
        expect(JSON.parse(String(options?.body))).toEqual({ source, size: '2x4' });
        return response({ genui, size: '2x4' });
      }
      if (url === '/debug/batch/runs/run_001') return response({
        runId: 'run_001', status: 'completed', samples: [{
          id: 'Q001', query: '请做一个 2x2 卡片', size: '2x2', status: 'success',
        }],
      });
      if (url.endsWith('/samples/Q001')) return response({
        summary: { id: 'Q001', finalAttempt: 0 },
        attempts: [{
          name: 'attempt_000',
          genui: source,
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
    expect(fetchMock.mock.calls.filter(([url]) => String(url) === '/debug/renderer/convert'))
      .toHaveLength(mode === 'Compact DSL' ? 1 : 0);
    await waitFor(() => {
      expect(document.documentElement.dataset.galleryCapture).toBe('ready');
    });
  });
});
