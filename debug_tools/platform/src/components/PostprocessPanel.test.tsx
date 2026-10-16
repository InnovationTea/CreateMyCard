import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { PostprocessExecution } from '../batchApi';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PostprocessPanel } from './PostprocessPanel';

function response(value: unknown): Response {
  return { ok: true, json: async () => value } as Response;
}

function execution(status: string, plugins: PostprocessExecution['plugins']): PostprocessExecution {
  return {
    schemaVersion: 'batch-postprocess-execution-v2', executionId: `exec_${status}`,
    runId: 'run_1', status, createdAt: '2026-10-17T00:00:00Z', plugins,
  };
}

function resultRow(name: string) {
  const row = screen.getByText(name, { selector: '.postprocess-inline-results strong' }).closest('article');
  if (!row) throw new Error(`Missing result row: ${name}`);
  return within(row);
}

describe('PostprocessPanel', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
      if (url === '/debug/batch/postprocess/plugins') return response({ items: [
        { apiVersion: 'batch-postprocess-v2', id: 'browser-gallery', name: '浏览器渲染画廊', version: '2.0.0', configSchema: { type: 'object' } },
        { apiVersion: 'batch-postprocess-v2', id: 'device-capture', name: '真机截图', version: '2.0.0', dependence: ['browser-gallery'], configSchema: { type: 'object' } },
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

    fireEvent.click(await screen.findByRole('checkbox', { name: '真机截图' }));
    expect(screen.getByRole('checkbox', { name: '浏览器渲染画廊' })).toBeChecked();
    fireEvent.change(screen.getByLabelText('真机截图在线设备'), { target: { value: 'device_one' } });
    fireEvent.click(screen.getByRole('button', { name: '开始后处理' }));

    await waitFor(() => expect(onStarted).toHaveBeenCalled());
    const request = vi.mocked(fetch).mock.calls.find(([url, init]) => (
      String(url).endsWith('/postprocess') && init?.method === 'POST'
    ));
    const body = JSON.parse(String(request?.[1]?.body));
    expect(body.pluginIds).toEqual(['browser-gallery', 'device-capture']);
    expect(body.rerun).toBe(false);
  });

  it('selecting a device gallery adds capture and analysis and submits the device config', async () => {
    const onStarted = vi.fn(async () => undefined);
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === '/debug/batch/postprocess/plugins') return response({ items: [
        { id: 'data-analysis', name: '数据分析', configSchema: { type: 'object' } },
        { id: 'device-capture', name: '真机截图', configSchema: { type: 'object' } },
        { id: 'device-gallery', name: '真机截图画廊', configSchema: { type: 'object' },
          dependence: ['device-capture', 'data-analysis'] },
      ] });
      if (url === '/debug/device/targets') return response({ targets: [
        { id: 'device_one', name: '设备', kind: 'physical' },
      ], emulators: [] });
      if (init?.method === 'POST') return response({ executionId: 'exec', status: 'queued' });
      throw new Error(url);
    });
    render(<MemoryRouter><PostprocessPanel runId="run_1" runStatus="completed"
      selectedSampleId="" executions={[]} onStarted={onStarted} /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: '后处理插件' }));
    fireEvent.click(await screen.findByRole('checkbox', { name: '真机截图画廊' }));
    expect(screen.getByRole('checkbox', { name: '真机截图' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: '数据分析' })).toBeChecked();
    expect(screen.getByRole('button', { name: '开始后处理' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText('真机截图在线设备'), { target: { value: 'device_one' } });
    fireEvent.click(screen.getByRole('button', { name: '开始后处理' }));
    await waitFor(() => expect(onStarted).toHaveBeenCalled());
    const request = vi.mocked(fetch).mock.calls.find(([, init]) => init?.method === 'POST');
    const body = JSON.parse(String(request?.[1]?.body));
    expect(body.pluginIds).toEqual(['device-capture', 'data-analysis', 'device-gallery']);
    expect(body.configs['device-capture']).toEqual({ targetId: 'device_one' });
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

  it('keeps capture delay in local YAML instead of exposing a browser setting', async () => {
    const onStarted = vi.fn(async () => undefined);
    render(<MemoryRouter><PostprocessPanel runId="run_1" runStatus="completed"
      selectedSampleId="" executions={[]} onStarted={onStarted} /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: '后处理插件' }));
    fireEvent.click(await screen.findByRole('checkbox', { name: '真机截图' }));
    fireEvent.change(screen.getByLabelText('真机截图在线设备'), { target: { value: 'device_one' } });
    expect(screen.queryByRole('spinbutton', { name: '截图前等待（秒）' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '开始后处理' }));
    await waitFor(() => expect(onStarted).toHaveBeenCalled());
    const request = vi.mocked(fetch).mock.calls.find(([, init]) => init?.method === 'POST');
    expect(JSON.parse(String(request?.[1]?.body)).configs['device-capture']).toEqual({
      targetId: 'device_one',
    });
  });

  it('starts and selects a local emulator for device capture', async () => {
    let online = false;
    vi.mocked(fetch).mockImplementation(async (input: string | URL | Request) => {
      const url = String(input);
      if (url === '/debug/batch/postprocess/plugins') return response({ items: [{
        apiVersion: 'batch-postprocess-v2', id: 'device-capture', name: '真机截图',
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
    fireEvent.click(await screen.findByRole('checkbox', { name: '真机截图' }));
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
    fireEvent.click(screen.getByRole('checkbox', { name: '真机截图' }));
    fireEvent.change(screen.getByLabelText('真机截图在线设备'), { target: { value: 'device_one' } });
    fireEvent.click(screen.getByRole('button', { name: '更新自动执行配置' }));

    await waitFor(() => expect(onStarted).toHaveBeenCalled());
    expect(screen.queryByRole('link', { name: '打开看板 ›' })).not.toBeInTheDocument();
    const request = vi.mocked(fetch).mock.calls.find(([url, init]) => (
      String(url).endsWith('/postprocess') && init?.method === 'POST'
    ));
    const body = JSON.parse(String(request?.[1]?.body));
    expect(body.pluginIds).toEqual(['browser-gallery', 'device-capture']);
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
    fireEvent.click(await screen.findByRole('checkbox', { name: '真机截图' }));
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
      pluginIds: ['device-capture'], rerun: false,
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

  it('allows retrying another plugin while one runs and a completed sibling while its execution runs', async () => {
    const onStarted = vi.fn(async () => undefined);
    const plugins = [
      { id: 'browser-gallery', name: '浏览器渲染画廊', status: 'success' },
      { id: 'device-capture', name: '真机截图', status: 'success' },
    ];
    const props = { runId: 'run_1', runStatus: 'completed', selectedSampleId: '', onStarted };
    const view = render(<MemoryRouter><PostprocessPanel {...props}
      executions={[execution('completed', plugins)]} /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: /后处理插件/ }));
    await screen.findByRole('checkbox', { name: '浏览器渲染画廊' });
    fireEvent.click(resultRow('浏览器渲染画廊').getByRole('button', { name: '再次运行' }));
    await waitFor(() => expect(onStarted).toHaveBeenCalledTimes(1));
    view.rerender(<MemoryRouter><PostprocessPanel {...props} executions={[
      execution('completed', plugins),
      execution('running', [{ ...plugins[0], status: 'running' }, plugins[1]]),
    ]} /></MemoryRouter>);
    expect(resultRow('浏览器渲染画廊').queryByRole('button', { name: '再次运行' })).not.toBeInTheDocument();
    const otherRetry = resultRow('真机截图').getByRole('button', { name: '再次运行' });
    expect(otherRetry).toBeEnabled();
    fireEvent.click(otherRetry);
    await waitFor(() => expect(onStarted).toHaveBeenCalledTimes(2));
    const requests = vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === 'POST');
    expect(JSON.parse(String(requests[1]?.[1]?.body))).toMatchObject({
      pluginIds: ['device-capture'], rerun: true,
    });
  });

  it('tracks pending retry submissions independently for each plugin', async () => {
    let finishFirst: ((value: Response) => void) | undefined;
    const originalFetch = vi.mocked(fetch).getMockImplementation();
    vi.mocked(fetch).mockImplementation((input, init) => {
      if (init?.method === 'POST' && JSON.parse(String(init.body)).pluginIds.includes('browser-gallery')) {
        return new Promise<Response>((resolve) => { finishFirst = resolve; });
      }
      if (!originalFetch) throw new Error('Missing fetch fixture');
      return originalFetch(input, init);
    });
    const onStarted = vi.fn(async () => undefined);
    render(<MemoryRouter><PostprocessPanel runId="run_1" runStatus="completed"
      selectedSampleId="" onStarted={onStarted} executions={[execution('completed', [
        { id: 'browser-gallery', status: 'success' }, { id: 'device-capture', status: 'success' },
      ])]} /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: /后处理插件/ }));
    await screen.findByRole('checkbox', { name: '浏览器渲染画廊' });
    fireEvent.click(resultRow('浏览器渲染画廊').getByRole('button', { name: '再次运行' }));
    expect(resultRow('浏览器渲染画廊').getByRole('button', { name: '提交中…' })).toBeDisabled();
    fireEvent.click(resultRow('真机截图').getByRole('button', { name: '再次运行' }));
    await waitFor(() => expect(onStarted).toHaveBeenCalledTimes(1));
    expect(resultRow('浏览器渲染画廊').getByRole('button', { name: '提交中…' })).toBeDisabled();
    expect(resultRow('真机截图').getByRole('button', { name: '再次运行' })).toBeEnabled();
    if (!finishFirst) throw new Error('First retry was not submitted');
    finishFirst(response({ executionId: 'exec_first', status: 'queued' }));
    await waitFor(() => expect(onStarted).toHaveBeenCalledTimes(2));
  });

  it('queues new selected plugins while excluding already queued plugins', async () => {
    const onStarted = vi.fn(async () => undefined);
    render(<MemoryRouter><PostprocessPanel runId="run_1" runStatus="completed"
      selectedSampleId="" onStarted={onStarted} executions={[execution('queued', [
        { id: 'browser-gallery', status: 'queued' },
      ])]} /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: /后处理插件/ }));
    const queued = await screen.findByRole('checkbox', { name: '浏览器渲染画廊' });
    expect(queued).toBeEnabled();
    fireEvent.click(queued);
    expect(screen.getByRole('button', { name: '继续运行后处理' })).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox', { name: '真机截图' }));
    fireEvent.change(screen.getByLabelText('真机截图在线设备'), { target: { value: 'device_one' } });
    expect(screen.getByText('将按依赖执行 1 个新增插件')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '继续运行后处理' }));
    await waitFor(() => expect(onStarted).toHaveBeenCalledTimes(1));
    const request = vi.mocked(fetch).mock.calls.find(([, init]) => init?.method === 'POST');
    expect(JSON.parse(String(request?.[1]?.body))).toMatchObject({
      pluginIds: ['device-capture'], rerun: false,
    });
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
