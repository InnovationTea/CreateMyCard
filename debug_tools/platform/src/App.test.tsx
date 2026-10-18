import type { ReactNode } from 'react';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import App from './App';

vi.mock('./context', () => ({
  WorkbenchProvider: ({ children }: { children: ReactNode }) => children,
  // 期望对比页会读会话调用记录；这里给一个空历史，具体提取逻辑另有单测。
  useWorkbench: () => ({ calls: [], events: [], artifact: null }),
}));
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

describe('expect module navigation', () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  function mockRuns() {
    return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      const body = url === '/debug/batch/scheduler' ? { paused: false, queue: [] } : { items: [] };
      return { ok: true, json: async () => body } as Response;
    });
  }

  it('is its own top-level module, separate from quality scoring', async () => {
    mockRuns();
    render(<MemoryRouter initialEntries={['/expect']}><App /></MemoryRouter>);
    const mainNav = within(screen.getByRole('navigation', { name: '调试模块' }));
    expect(mainNav.getByRole('link', { name: /期望对比/ })).toHaveAttribute('href', '/expect');
    expect(mainNav.queryByRole('link', { name: /期望画廊/ })).toBeNull();
    expect(mainNav.getByRole('link', { name: /质量评分/ })).toHaveAttribute('href', '/quality');
    expect(await screen.findByRole('heading', { name: '期望对比' })).toBeInTheDocument();
    cleanup();
    // 质量评分页不再把期望对比当作子页面。
    mockRuns();
    render(<MemoryRouter initialEntries={['/quality']}><App /></MemoryRouter>);
    const qualityNav = within(await screen.findByRole('navigation', { name: '质量工具' }));
    expect(qualityNav.queryByRole('link', { name: /期望|预期/ })).toBeNull();
    expect(qualityNav.getByRole('link', { name: '导入 DSL＋图片' })).toHaveAttribute('href', '/quality/import');
  });

  it('redirects the legacy quality URL into the expect module keeping the query', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      const body = url === '/debug/batch/runs' ? { items: [
        { runId: 'imp', name: '期望批次', status: 'completed', sourceType: 'external-quality' },
        { runId: 'run1', name: '实际批跑', status: 'completed' },
      ] } : { items: [] };
      return { ok: true, json: async () => body } as Response;
    });
    render(<MemoryRouter initialEntries={['/quality/expect?importRunId=imp&runId=run1']}><App /></MemoryRouter>);
    expect(await screen.findByRole('heading', { name: '期望对比' })).toBeInTheDocument();
    // 期望侧不再挑批次：旧地址带过来的参数被忽略，进页面只用已导入的期望池。
    expect(screen.queryByLabelText('期望批次（导入）')).toBeNull();
    expect(await screen.findByText(/已导入 0 条 · 1 个批次/)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => String(url).startsWith('/debug/expect/compare'))).toBe(false);
  });
});

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
