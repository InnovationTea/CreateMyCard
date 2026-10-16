import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PostprocessPanel } from './PostprocessPanel';

function response(value: unknown): Response {
  return { ok: true, json: async () => value } as Response;
}

describe('PostprocessPanel', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
      if (url === '/debug/batch/postprocess/plugins') return response({ items: [
        { apiVersion: 'batch-postprocess-v2', id: 'browser-gallery', name: '浏览器渲染画廊', version: '2.0.0', configSchema: { type: 'object' } },
        { apiVersion: 'batch-postprocess-v2', id: 'device-gallery', name: '真机截图画廊', version: '2.0.0', dependence: ['browser-gallery'], configSchema: { type: 'object' } },
      ] });
      if (url === '/debug/device/targets') return response({ targets: [{
        id: 'device_one', name: 'Pura Test', serial: 'USB123', kind: 'physical',
      }], emulators: [] });
      if (url.endsWith('/postprocess') && init?.method === 'POST') return response({ executionId: 'exec_1', status: 'queued' });
      throw new Error(`unexpected request: ${url}`);
    }));
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('opens on demand and submits selected plugins for parallel execution', async () => {
    const onStarted = vi.fn(async () => undefined);
    render(<PostprocessPanel
      runId="run_1"
      runStatus="completed"
      selectedSampleId="Q001"
      executions={[]}
      onStarted={onStarted}
    />);

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '后处理插件' }));
    expect(screen.getByRole('dialog', { name: '后处理插件' })).toBeInTheDocument();

    fireEvent.click(await screen.findByRole('checkbox', { name: '真机截图画廊' }));
    expect(screen.getByRole('checkbox', { name: '浏览器渲染画廊' })).toBeChecked();
    fireEvent.change(screen.getByLabelText('真机截图在线设备'), { target: { value: 'device_one' } });
    fireEvent.click(screen.getByRole('button', { name: '开始后处理' }));

    await waitFor(() => expect(onStarted).toHaveBeenCalled());
    const request = vi.mocked(fetch).mock.calls.find(([url, init]) => (
      String(url).endsWith('/postprocess') && init?.method === 'POST'
    ));
    const body = JSON.parse(String(request?.[1]?.body));
    expect(body.pluginIds).toEqual(['browser-gallery', 'device-gallery']);
    expect(body.rerun).toBe(false);
  });

  it('allows scheduling plugins before the batch run completes', async () => {
    const onStarted = vi.fn(async () => undefined);
    render(<PostprocessPanel
      runId="run_1"
      runStatus="running"
      selectedSampleId=""
      executions={[]}
      onStarted={onStarted}
    />);

    fireEvent.click(screen.getByRole('button', { name: '后处理插件' }));
    fireEvent.click(await screen.findByRole('checkbox', { name: '浏览器渲染画廊' }));
    fireEvent.click(screen.getByRole('button', { name: '完成后自动执行' }));

    await waitFor(() => expect(onStarted).toHaveBeenCalled());
    expect(fetch).toHaveBeenCalledWith(
      '/debug/batch/runs/run_1/postprocess',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('starts and selects a local emulator for device capture', async () => {
    let online = false;
    vi.mocked(fetch).mockImplementation(async (input: string | URL | Request) => {
      const url = String(input);
      if (url === '/debug/batch/postprocess/plugins') return response({ items: [{
        apiVersion: 'batch-postprocess-v2', id: 'device-gallery', name: '真机截图画廊',
        version: '2.0.0', configSchema: { type: 'object' },
      }] });
      if (url === '/debug/device/targets') return response({
        targets: online ? [{
          id: 'emulator-target', name: 'Pura X', serial: '127.0.0.1:5555', kind: 'emulator',
        }] : [],
        emulators: [{ id: 'emulator-a', name: 'Pura X', path: 'local', ready: true }],
      });
      if (url === '/debug/device/emulators/emulator-a/start') return response({
        id: 'emulator-a', status: 'running', message: '正在启动本地模拟器',
      });
      if (url === '/debug/device/operations/emulator-a') {
        online = true;
        return response({
          id: 'emulator-a', status: 'success', message: '模拟器已连接 HDC，可以开始截图',
          targetId: 'emulator-target', serial: '127.0.0.1:5555',
        });
      }
      throw new Error(`unexpected request: ${url}`);
    });
    render(<MemoryRouter><PostprocessPanel runId="run_1" runStatus="completed"
      selectedSampleId="Q001" executions={[]} onStarted={vi.fn()} /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: '后处理插件' }));
    fireEvent.click(await screen.findByRole('checkbox', { name: '真机截图画廊' }));
    fireEvent.click(screen.getByRole('button', { name: '启动本地模拟器 · Pura X' }));
    await waitFor(() => expect(screen.getByLabelText('真机截图在线设备'))
      .toHaveValue('emulator-target'), { timeout: 2500 });
    expect(screen.getByText('模拟器已连接 HDC，可以开始截图')).toBeInTheDocument();
  });

  it('allows updating the waiting plugin configuration before completion', async () => {
    const onStarted = vi.fn(async () => undefined);
    render(<MemoryRouter><PostprocessPanel
        runId="run_1"
        runStatus="running"
        selectedSampleId=""
        executions={[{
          schemaVersion: 'batch-postprocess-execution-v2',
          executionId: 'exec_waiting',
          runId: 'run_1',
          status: 'waiting',
          createdAt: '2026-10-07T00:00:00Z',
          plugins: [{ id: 'browser-gallery', name: '浏览器渲染画廊', config: {} }],
        }]}
        onStarted={onStarted}
      /></MemoryRouter>);

    fireEvent.click(screen.getByRole('button', { name: /后处理插件/ }));
    const gallery = await screen.findByRole('checkbox', { name: '浏览器渲染画廊' });
    expect(gallery).toBeChecked();
    fireEvent.click(screen.getByRole('checkbox', { name: '真机截图画廊' }));
    fireEvent.change(screen.getByLabelText('真机截图在线设备'), { target: { value: 'device_one' } });
    fireEvent.click(screen.getByRole('button', { name: '更新自动执行配置' }));

    await waitFor(() => expect(onStarted).toHaveBeenCalled());
    expect(screen.queryByRole('link', { name: '打开看板 ›' })).not.toBeInTheDocument();
    const request = vi.mocked(fetch).mock.calls.find(([url, init]) => (
      String(url).endsWith('/postprocess') && init?.method === 'POST'
    ));
    const body = JSON.parse(String(request?.[1]?.body));
    expect(body.pluginIds).toEqual(['browser-gallery', 'device-gallery']);
  });

  it('submits only new plugins and reruns completed plugins explicitly', async () => {
    const onStarted = vi.fn(async () => undefined);
    render(<MemoryRouter><PostprocessPanel
      runId="run_1"
      runStatus="completed"
      selectedSampleId="Q001"
      executions={[{
        schemaVersion: 'batch-postprocess-execution-v2',
        executionId: 'exec_old',
        runId: 'run_1',
        status: 'completed',
        createdAt: '2026-10-08T00:00:00Z',
        plugins: [{
          id: 'browser-gallery', name: '浏览器渲染画廊', status: 'success', sampleCount: 1,
          datasetResult: { status: 'success', summary: '已生成' },
        }],
      }]}
      onStarted={onStarted}
    /></MemoryRouter>);

    fireEvent.click(screen.getByRole('button', { name: /后处理插件/ }));
    fireEvent.click(await screen.findByRole('checkbox', { name: '真机截图画廊' }));
    fireEvent.change(screen.getByLabelText('真机截图在线设备'), { target: { value: 'device_one' } });
    expect(screen.getByText('将并行执行 1 个新增插件')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '开始后处理' }));
    await waitFor(() => expect(onStarted).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: '再次运行' }));
    await waitFor(() => expect(onStarted).toHaveBeenCalledTimes(2));
    const requests = vi.mocked(fetch).mock.calls.filter(([url, init]) => (
      String(url).endsWith('/postprocess') && init?.method === 'POST'
    ));
    expect(JSON.parse(String(requests[0]?.[1]?.body))).toMatchObject({
      pluginIds: ['device-gallery'], rerun: false,
    });
    expect(JSON.parse(String(requests[1]?.[1]?.body))).toMatchObject({
      pluginIds: ['browser-gallery'], rerun: true,
    });
  });

  it('routes quality scoring through sample selection without submitting it as a generic plugin', async () => {
    vi.mocked(fetch).mockResolvedValue(response({ items: [{
      apiVersion: 'batch-postprocess-v2', id: 'quality-score', name: '质量评分', version: '1',
      configSchema: { type: 'object' }, dependence: ['browser-gallery'],
    }] }));
    render(<MemoryRouter><PostprocessPanel runId="run_1" runStatus="completed"
      selectedSampleId="Q001" executions={[]} onStarted={vi.fn()} /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: '后处理插件' }));
    expect(await screen.findByRole('link', { name: /质量评分/ })).toHaveAttribute('href', '/quality?runId=run_1');
    expect(screen.queryByRole('checkbox', { name: '质量评分' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '开始后处理' })).toBeDisabled();
    expect(vi.mocked(fetch).mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);
  });

  it('shows running progress and exposes the partial dashboard without selecting plugins', async () => {
    render(<MemoryRouter><PostprocessPanel
      runId="run_1"
      runStatus="completed"
      selectedSampleId="Q001"
      executions={[{
        schemaVersion: 'batch-postprocess-execution-v2',
        executionId: 'exec_running',
        runId: 'run_1',
        status: 'running',
        createdAt: '2026-10-10T00:00:00Z',
        plugins: [{
          id: 'browser-gallery',
          name: '浏览器渲染画廊',
          status: 'running',
          sampleCount: 8,
          progress: {
            phase: 'finalize', completed: 3, total: 8, message: '正在补齐截图 3/8',
          },
          datasetResult: { status: 'success', summary: '基础结果可查看' },
        }],
      }]}
      onStarted={vi.fn(async () => undefined)}
    /></MemoryRouter>);

    expect(screen.getByRole('button', { name: '后处理插件 · 1 个执行中' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '后处理插件 · 1 个执行中' }));
    expect(await screen.findByText(/正在补齐截图 3\/8/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '打开看板 ›' })).toHaveAttribute(
      'href',
      '/batch/runs/run_1/postprocess/exec_running/plugins/browser-gallery',
    );
    expect(screen.queryByRole('button', { name: '再次运行' })).not.toBeInTheDocument();
  });
});
