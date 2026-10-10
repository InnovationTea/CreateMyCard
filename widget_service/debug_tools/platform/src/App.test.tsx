import type { ReactNode } from 'react';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import App from './App';

vi.mock('./context', () => ({ WorkbenchProvider: ({ children }: { children: ReactNode }) => children }));
vi.mock('./components/CallHistory', () => ({ default: () => null }));
vi.mock('./components/SettingsPanel', () => ({ default: () => null }));
vi.mock('./components/BackendStatusWidget', () => ({ BackendStatusWidget: () => null }));
vi.mock('./routes/EndToEndRoute', () => ({ EndToEndRoute: () => null }));
vi.mock('./routes/InterfaceRoute', () => ({ InterfaceRoute: () => null }));
vi.mock('./routes/RendererRoute', () => ({ RendererRoute: () => null }));
vi.mock('./routes/BatchRoute', () => ({ BatchRoute: () => null }));
vi.mock('./routes/BatchTraceRoute', () => ({ BatchTraceRoute: () => null }));
vi.mock('./routes/BatchGalleryCaptureRoute', () => ({ BatchGalleryCaptureRoute: () => null }));
vi.mock('./routes/BatchTaskCreateRoute', () => ({ BatchTaskCreateRoute: () => null }));

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
