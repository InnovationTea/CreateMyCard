import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { WorkbenchProvider } from '../context';
import { BackendStatusWidget } from './BackendStatusWidget';

function response(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as Response;
}

describe('BackendStatusWidget', () => {
  afterEach(() => {
    cleanup();
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('uses text and traffic-light colors, polls every 20 seconds and starts managed service', async () => {
    const intervalSpy = vi.spyOn(window, 'setInterval');
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith('/connections/status')) return response({
        mainAgent: { available: true, detail: 'agent ok' },
        deployedService: { available: false, detail: 'offline' },
        managedService: { available: false, detail: '尚未启动' },
      });
      if (url.endsWith('/connections/managed/start')) return response({
        mainAgent: { available: true, detail: 'agent ok' },
        deployedService: { available: false, detail: 'offline' },
        managedService: { available: true, detail: 'health ok' },
      });
      throw new Error(`unexpected fetch: ${url}`);
    });

    render(<WorkbenchProvider><BackendStatusWidget allowManagedStart /></WorkbenchProvider>);
    expect(screen.getAllByText('检查中')).toHaveLength(4);
    expect(intervalSpy).toHaveBeenCalledWith(expect.any(Function), 20_000);

    await waitFor(() => expect(screen.getByText('每 20 秒自动检查')).toBeInTheDocument());
    expect(screen.getByText('Main Agent').closest('.backend-status-item')).toHaveClass('available');
    expect(screen.getByText('已部署微服务').closest('.backend-status-item')).toHaveClass('unavailable');

    await userEvent.click(screen.getByRole('button', { name: '启动本地受管微服务' }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      '/debug/batch/connections/managed/start', expect.objectContaining({ method: 'POST' }),
    ));
    expect(screen.getByText('本地受管微服务').closest('.backend-status-item')).toHaveClass('available');
  });
});
