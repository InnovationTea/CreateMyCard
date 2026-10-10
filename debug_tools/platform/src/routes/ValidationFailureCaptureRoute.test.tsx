import { cleanup, render, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ValidationFailureCaptureRoute } from './ValidationFailureCaptureRoute';

function response(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as Response;
}

describe('ValidationFailureCaptureRoute', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    delete document.documentElement.dataset.galleryCapture;
  });

  it('renders validation input DSL and reports invalid DSL without hiding the sample', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(response({
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
    }));

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
    expect(
      container.querySelector('[data-sample-id="Q001-e1-i2-v1"] .gallery-capture-placeholder'),
    ).toBeTruthy();
    await waitFor(() => {
      expect(document.documentElement.dataset.galleryCapture).toBe('ready');
    });
  });
});
