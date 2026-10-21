import type { ReactNode } from 'react';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import App from '../../../platform/src/App';

vi.mock('../../../platform/src/context', () => ({ WorkbenchProvider: ({ children }: { children: ReactNode }) => children }));
vi.mock('../../../platform/src/components/CallHistory', () => ({ default: () => null }));
vi.mock('../../../platform/src/components/SettingsPanel', () => ({ default: () => null }));
vi.mock('../../../platform/src/components/BackendStatusWidget', () => ({ BackendStatusWidget: () => null }));
vi.mock('../../../platform/src/routes/EndToEndRoute', () => ({ EndToEndRoute: () => null }));
vi.mock('../../../platform/src/routes/InterfaceRoute', () => ({ InterfaceRoute: () => null }));
vi.mock('../../../platform/src/routes/RendererRoute', () => ({ RendererRoute: () => null }));
vi.mock('../../../platform/src/routes/BatchRoute', () => ({ BatchRoute: () => null }));
vi.mock('../../../platform/src/routes/BatchTraceRoute', () => ({ BatchTraceRoute: () => null }));
vi.mock('../../../platform/src/routes/BatchGalleryCaptureRoute', () => ({ BatchGalleryCaptureRoute: () => null }));
vi.mock('../../../platform/src/routes/BatchTaskCreateRoute', () => ({ BatchTaskCreateRoute: () => null }));

describe('quality navigation', () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it.each(['main', 'batch'])('opens selection from the %s entry without POST or polling', async (entry) => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      const body = url === '/debug/batch/scheduler' ? { paused: false, queue: [] } : { items: [] };
      return { ok: true, json: async () => body } as Response;
    });
    render(<MemoryRouter initialEntries={['/batch']}><App /></MemoryRouter>);
    const mainNav = within(screen.getByRole('navigation', { name: '调试模块' }));
    const mainEntry = mainNav.getByRole('link', { name: /质量评分/ });
    const batchEntry = within(screen.getByRole('main')).getByRole('link', { name: '质量评分' });
    expect(mainEntry).toHaveAttribute('href', '/quality');
    expect(batchEntry).toHaveAttribute('href', '/quality');
    fireEvent.click(entry === 'main' ? mainEntry : batchEntry);
    expect(await screen.findByText('暂无已完成批次，请先到批跑中心完成运行。')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '运行评分' })).toBeDisabled();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/postprocess'))).toBe(false);
  });
});
