import { cleanup, render, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ValidationFailureCaptureRoute } from './ValidationFailureCaptureRoute';

function response(body: unknown, status = 200): Response {
  return { ok: status < 400, status, json: async () => body } as Response;
}

describe('ValidationFailureCaptureRoute', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    delete document.documentElement.dataset.galleryCapture;
  });

  it('renders validation input DSL and reports invalid DSL without hiding the sample', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, options) => {
      if (String(input) === '/debug/renderer/convert') {
        const body = JSON.parse(String(options?.body));
        if (body.source.endsWith('{')) return response({ detail: 'DSL 括号未闭合' }, 422);
        return response({ size: '2x2', genui: [
          '{"version":"v0.9","createSurface":{"surfaceId":"preview"}}',
          '{"version":"v0.9","updateComponents":{"surfaceId":"preview","root":"root","components":[{"id":"root","component":"Text","content":"会议"}]}}',
        ].join('\n') });
      }
      return response({
      items: [
        {
          id: 'Q001',
          title: '多轮校验',
          query: '展示会议',
          size: '2x2',
          sequence: 1,
          finalStatus: 'success',
          interfaceRetryCount: 1,
          validationFailureCount: 1,
          repairAttemptCount: 1,
          validations: [
            {
              captureId: 'Q001-e1-i1-v1',
              executionAttempt: 1,
              interfaceAttempt: 1,
              validationAttempt: 1,
              status: 'failed',
              errorTypes: ['COMPACT_DSL_VALIDATION_FAILED'],
              dsl: '["root","Text",{"content":"会议"}]',
            },
            {
              captureId: 'Q001-e1-i2-v1',
              executionAttempt: 1,
              interfaceAttempt: 2,
              validationAttempt: 1,
              status: 'success',
              errorTypes: [],
              dsl: '["root","Text",{',
            },
          ],
        },
      ],
      });
    });

    const { container } = render(
      <MemoryRouter initialEntries={['/batch/runs/run_001/validation-failure-capture']}>
        <Routes>
          <Route
            path="/batch/runs/:runId/validation-failure-capture"
            element={<ValidationFailureCaptureRoute />}
          />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(container.querySelectorAll('.gallery-capture-item')).toHaveLength(2);
    });
    expect(
      container.querySelector('[data-sample-id="Q001-e1-i1-v1"] .gallery-capture-card'),
    ).toBeTruthy();
    expect(fetchMock.mock.calls.filter(([url]) => String(url) === '/debug/renderer/convert')).toHaveLength(2);
    expect(
      container.querySelector('[data-sample-id="Q001-e1-i2-v1"] .gallery-capture-placeholder'),
    ).toBeTruthy();
    await waitFor(() => {
      expect(document.documentElement.dataset.galleryCapture).toBe('ready');
    });
  });
});
