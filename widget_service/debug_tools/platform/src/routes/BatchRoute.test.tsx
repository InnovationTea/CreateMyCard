import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { WorkbenchProvider } from '../context';
import { BatchRoute } from './BatchRoute';

function response(body: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => body } as Response;
}

const run = {
  runId: 'run_001', taskId: 'task_1', status: 'completed', total: 1, completed: 1,
  success: 1, degraded: 0, failed: 0, cancelled: 0, averageElapsedMs: 10,
  traceWarnings: 0, endpoint: 'ws://127.0.0.1:8855/api/v1/ws/tools', concurrency: 4,
  maxRetries: 1, startedAt: '2026-10-03T00:00:00Z', samples: [{
    id: 'Q001', fileName: 'Q001.json', title: '天气', query: '天气卡片', size: '2x2',
    sequence: 1, status: 'success', traceStatus: 'complete', traceRecordCount: 2,
    attemptCount: 1, elapsedMs: 10, errorCode: '', error: '', artifactAvailable: true,
    dslAvailable: true,
  }],
};

function renderDetail() {
  return render(
    <WorkbenchProvider>
      <MemoryRouter initialEntries={['/batch/tasks/task_1']}>
        <Routes><Route path="/batch/tasks/:taskId" element={<BatchRoute />} /></Routes>
      </MemoryRouter>
    </WorkbenchProvider>,
  );
}

describe('BatchRoute', () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it('loads task history and opens sample Trace in a new tab', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url === '/debug/batch/tasks/task_1') return response({
        taskId: 'task_1', name: '天气回归', datasetId: 'request_dataset', sampleIds: ['Q001'],
        sampleCount: 1, requestOverrides: {}, concurrency: 4, maxRetries: 1,
        timeoutSeconds: 300, backendMode: 'deployed', toolWsBaseUrl: 'ws://localhost',
        serviceConfig: {}, createdAt: '', updatedAt: '', runCount: 1,
        runs: [{ runId: 'run_001', taskId: 'task_1', status: 'completed', createdAt: '', backendMode: 'deployed', serviceStatus: 'external' }],
      });
      if (url === '/debug/batch/runs/run_001') return response(run);
      if (url.endsWith('/samples/Q001')) return response({ summary: { id: 'Q001' }, attempts: [] });
      throw new Error(`unexpected fetch: ${url}`);
    });
    renderDetail();

    await userEvent.click(await screen.findByText('Q001'));
    const link = await screen.findByRole('link', { name: 'Trace' });
    expect(link).toHaveAttribute('href', '/batch/runs/run_001/samples/Q001/trace');
    expect(link).toHaveAttribute('target', '_blank');
    expect(screen.getByText('天气回归')).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: '执行记录' }).closest('header'))
      .toHaveClass('batch-heading');
    expect(document.querySelector('.batch-current-state.completed')).toBeNull();
  });

  it('renders a sample with the final CardSpec size instead of the 2x2 default', async () => {
    const genui = [
      '{"version":"v0.9","createSurface":{"surfaceId":"surface_card"}}',
      '{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Text","content":"宽卡"}]}}',
    ].join('\n');
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url === '/debug/batch/tasks/task_1') return response({
        taskId: 'task_1', name: '尺寸回归', datasetId: 'request_dataset', sampleIds: ['Q001'],
        sampleCount: 1, requestOverrides: {}, concurrency: 4, maxRetries: 1,
        timeoutSeconds: 300, backendMode: 'deployed', toolWsBaseUrl: 'ws://localhost',
        serviceConfig: {}, createdAt: '', updatedAt: '', runCount: 1,
        runs: [{ runId: 'run_001', taskId: 'task_1', status: 'completed', createdAt: '', backendMode: 'deployed', serviceStatus: 'external' }],
      });
      if (url === '/debug/batch/runs/run_001') return response(run);
      if (url.endsWith('/samples/Q001')) return response({
        summary: { id: 'Q001', query: '请做一个 2x2 卡片', size: '2x2', finalAttempt: 0 },
        attempts: [{ name: 'attempt_000', genui, blocks: { cardspec: { suggestSize: '2x4' } } }],
        deviceCapture: {
          id: 'Q001', status: 'success',
          cardUrl: '/debug/batch/runs/run_001/device-captures/Q001/card',
          fullUrl: '/debug/batch/runs/run_001/device-captures/Q001/full',
        },
      });
      throw new Error(`unexpected fetch: ${url}`);
    });
    renderDetail();

    await userEvent.click(await screen.findByText('Q001'));
    expect(await screen.findByText(/300 × 150/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '渲染' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '清空' })).not.toBeInTheDocument();
    expect(screen.queryByText('自动渲染')).not.toBeInTheDocument();
    expect(screen.queryByText('Web 渲染')).not.toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Q001 真机渲染截图' })).toHaveAttribute(
      'src', '/debug/batch/runs/run_001/device-captures/Q001/card',
    );
  });

  it('enqueues a reusable task from the detail page', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === '/debug/batch/tasks/task_1' && !init?.method) return response({
        taskId: 'task_1', name: '天气回归', datasetId: 'request_dataset', sampleIds: ['Q001'],
        sampleCount: 1, requestOverrides: {}, concurrency: 4, maxRetries: 1,
        timeoutSeconds: 300, backendMode: 'deployed', toolWsBaseUrl: 'ws://localhost',
        serviceConfig: {}, createdAt: '', updatedAt: '', runCount: 0, runs: [],
      });
      if (url === '/debug/batch/tasks/task_1/runs' && init?.method === 'POST') return response({
        runId: 'run_002', taskId: 'task_1', status: 'queued', createdAt: '',
        backendMode: 'deployed', serviceStatus: 'pending',
      }, 202);
      throw new Error(`unexpected fetch: ${url}`);
    });
    renderDetail();
    await userEvent.click(await screen.findByRole('button', { name: '重新执行' }));

    expect(fetchMock).toHaveBeenCalledWith(
      '/debug/batch/tasks/task_1/runs',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('shows and hides the task custom parameters without offering copy', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url === '/debug/batch/tasks/task_1') return response({
        taskId: 'task_1', name: '参数回归', datasetId: 'request_dataset', sampleIds: ['Q001'],
        sampleCount: 1, requestOverrides: { size: '2x4', dataCapabilityIds: ['weather'] },
        concurrency: 4, maxRetries: 1, timeoutSeconds: 300, backendMode: 'deployed',
        toolWsBaseUrl: 'ws://service.example/tools', serviceConfig: {}, createdAt: '', updatedAt: '',
        runCount: 0, runs: [],
      });
      throw new Error(`unexpected fetch: ${url}`);
    });
    renderDetail();

    const showButton = await screen.findByRole('button', { name: '查看自定义参数' });
    expect(screen.queryByRole('button', { name: '复制任务' })).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: '任务自定义参数' })).not.toBeInTheDocument();

    await userEvent.click(showButton);
    const panel = screen.getByRole('region', { name: '任务自定义参数' });
    expect(panel).toHaveTextContent('测试后端');
    expect(panel).toHaveTextContent('已部署微服务');
    expect(panel).toHaveTextContent('ws://service.example/tools');
    expect(panel).toHaveTextContent('公共请求字段覆盖');
    expect(panel).toHaveTextContent('"size": "2x4"');
    expect(panel).toHaveTextContent('"weather"');

    await userEvent.click(screen.getByRole('button', { name: '收起自定义参数' }));
    expect(screen.queryByRole('region', { name: '任务自定义参数' })).not.toBeInTheDocument();
  });

  it('shows task, service, progress and managed startup errors prominently', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url === '/debug/batch/tasks/task_1') return response({
        taskId: 'task_1', name: '受管后端回归', datasetId: 'request_dataset',
        sampleIds: ['Q001', 'Q002', 'Q003'], sampleCount: 3, requestOverrides: {},
        concurrency: 4, maxRetries: 1, timeoutSeconds: 300, backendMode: 'managed',
        toolWsBaseUrl: 'ws://127.0.0.1:8855/api/v1/ws/tools', serviceConfig: {},
        createdAt: '', updatedAt: '', runCount: 1, runs: [{
          runId: 'run_failed', taskId: 'task_1', status: 'failed', createdAt: '',
          backendMode: 'managed', serviceStatus: 'failed', total: 3, completed: 0,
        }],
      });
      if (url === '/debug/batch/runs/run_failed') return response({
        runId: 'run_failed', taskId: 'task_1', status: 'failed', createdAt: '',
        backendMode: 'managed', serviceStatus: 'failed', total: 3, completed: 0,
        success: 0, degraded: 0, failed: 0, cancelled: 0, averageElapsedMs: 0,
        traceWarnings: 0, samples: [], endpoint: '', concurrency: 4, maxRetries: 1,
        startedAt: '', error: 'RuntimeError: 无法访问 /health',
        serviceLogPath: 'D:/logs/service.log',
      });
      throw new Error(`unexpected fetch: ${url}`);
    });
    renderDetail();

    expect((await screen.findAllByText('后端启动失败')).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('0/3（0%）')).toBeInTheDocument();
    expect(screen.getByText('受管后端启动失败')).toBeInTheDocument();
    expect(screen.getByText('RuntimeError: 无法访问 /health')).toBeInTheDocument();
    expect(screen.getByText(/D:\/logs\/service\.log/)).toBeInTheDocument();
  });

  it('offers restart and continue actions for a stopped run', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === '/debug/batch/tasks/task_1') return response({
        taskId: 'task_1', name: '已停止任务', datasetId: 'request_dataset',
        sampleIds: ['Q001'], sampleCount: 1, requestOverrides: {}, concurrency: 4,
        maxRetries: 1, timeoutSeconds: 300, backendMode: 'deployed',
        toolWsBaseUrl: 'ws://localhost', serviceConfig: {}, createdAt: '', updatedAt: '',
        runCount: 1, runs: [{
          runId: 'run_stopped', taskId: 'task_1', status: 'cancelled', createdAt: '',
          backendMode: 'deployed', serviceStatus: 'external',
        }],
      });
      if (url === '/debug/batch/runs/run_stopped' && !init?.method) return response({
        ...run, runId: 'run_stopped', status: 'cancelled', completed: 1, cancelled: 1,
        success: 0, samples: [{ ...run.samples[0], status: 'cancelled', attemptCount: 1 }],
      });
      if (url === '/debug/batch/runs/run_stopped/continue' && init?.method === 'POST') {
        return response({ runId: 'run_stopped', status: 'queued' }, 202);
      }
      throw new Error(`unexpected fetch: ${url}`);
    });
    renderDetail();

    expect(await screen.findByRole('button', { name: '重新执行' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '继续执行' }));
    expect(fetchMock).toHaveBeenCalledWith(
      '/debug/batch/runs/run_stopped/continue', expect.objectContaining({ method: 'POST' }),
    );
  });

  it('keeps postprocessing actions in the task center', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url === '/debug/batch/tasks/task_1') return response({
        taskId: 'task_1', name: '天气回归', datasetId: 'request_dataset', sampleIds: ['Q001'],
        sampleCount: 1, requestOverrides: {}, concurrency: 4, maxRetries: 1,
        timeoutSeconds: 300, backendMode: 'deployed', toolWsBaseUrl: 'ws://localhost',
        serviceConfig: {}, createdAt: '', updatedAt: '', runCount: 1,
        runs: [{ runId: 'run_001', taskId: 'task_1', status: 'completed', createdAt: '', backendMode: 'deployed', serviceStatus: 'external' }],
      });
      if (url === '/debug/batch/runs/run_001') return response({
        ...run,
        gallery: { status: 'failed', error: '未找到 Edge' },
      });
      throw new Error(`unexpected fetch: ${url}`);
    });
    renderDetail();

    expect(await screen.findByText('画廊生成失败：未找到 Edge')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '生成画廊' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '生成真机截图' })).not.toBeInTheDocument();
  });
});
