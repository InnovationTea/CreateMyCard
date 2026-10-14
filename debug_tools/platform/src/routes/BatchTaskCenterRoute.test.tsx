import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { BatchTaskCenterRoute } from './BatchTaskCenterRoute';

function response(body: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => body } as Response;
}

describe('BatchTaskCenterRoute', () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it('shows the persisted queue and resumes it explicitly', async () => {
    let paused = true;
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === '/debug/batch/tasks') return response({ items: [{
        taskId: 'task_1', name: '天气回归', datasetId: 'request_dataset', sampleIds: ['Q001'],
        sampleCount: 1, requestOverrides: {}, concurrency: 4, maxRetries: 1,
        timeoutSeconds: 300, backendMode: 'managed', toolWsBaseUrl: 'ws://localhost',
        serviceConfig: {}, createdAt: '', updatedAt: '', runCount: 1,
        latestRun: { runId: 'run_1', taskId: 'task_1', status: 'queued', createdAt: '', backendMode: 'managed', serviceStatus: 'pending', queuePosition: 1 },
      }] });
      if (url === '/debug/batch/scheduler/resume' && init?.method === 'POST') {
        paused = false;
        return response({ paused, activeRunId: null, active: null, queue: [] });
      }
      if (url === '/debug/batch/scheduler') return response({
        paused, activeRunId: null, active: null,
        queue: paused ? [{ runId: 'run_1', taskId: 'task_1', status: 'queued', createdAt: '', backendMode: 'managed', serviceStatus: 'pending', queuePosition: 1 }] : [],
      });
      throw new Error(`unexpected fetch: ${url}`);
    });
    render(<MemoryRouter><BatchTaskCenterRoute /></MemoryRouter>);

    expect(await screen.findByText('天气回归')).toBeInTheDocument();
    expect(screen.getByText('队列已暂停')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '再次执行' })).toBeDisabled();
    expect(screen.queryByRole('button', { name: '复制' })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '恢复队列' }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      '/debug/batch/scheduler/resume', expect.objectContaining({ method: 'POST' }),
    ));
  });

  it('links every executed plugin to its latest dashboard', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url === '/debug/batch/tasks') return response({ items: [{
        taskId: 'task_1', name: '天气回归', datasetId: 'request_dataset', sampleIds: ['Q001'],
        sampleCount: 1, requestOverrides: {}, concurrency: 4, maxRetries: 1,
        timeoutSeconds: 300, backendMode: 'managed', toolWsBaseUrl: 'ws://localhost',
        serviceConfig: {}, createdAt: '', updatedAt: '', runCount: 1,
        latestRun: {
          runId: 'run_1', taskId: 'task_1', status: 'completed', createdAt: '',
          backendMode: 'managed', serviceStatus: 'managed_running', total: 1, completed: 1,
          postprocessExecutions: [{
            schemaVersion: 'batch-postprocess-execution-v2', executionId: 'exec_2',
            runId: 'run_1', status: 'completed', createdAt: '',
            plugins: [{
              id: 'component-recall', name: '组件召回分析', status: 'success',
              datasetResult: { status: 'success', summary: '完成' },
            }],
          }, {
            schemaVersion: 'batch-postprocess-execution-v2', executionId: 'exec_1',
            runId: 'run_1', status: 'completed', createdAt: '',
            plugins: [{
              id: 'browser-gallery', name: '浏览器渲染画廊', status: 'success',
              datasetResult: { status: 'success', summary: '完成' },
            }],
          }],
        },
      }] });
      if (url === '/debug/batch/scheduler') return response({
        paused: false, activeRunId: null, active: null, queue: [],
      });
      throw new Error(`unexpected fetch: ${url}`);
    });
    render(<MemoryRouter><BatchTaskCenterRoute /></MemoryRouter>);

    const pluginLink = await screen.findByRole('link', { name: '组件召回分析' });
    expect(pluginLink).toHaveAttribute(
      'href', '/batch/runs/run_1/postprocess/exec_2/plugins/component-recall',
    );
    expect(pluginLink).toHaveAttribute('target', '_blank');
    expect(pluginLink).toHaveAttribute('rel', 'noopener noreferrer');
    expect(screen.getByRole('link', { name: '浏览器渲染画廊' })).toHaveAttribute(
      'href', '/batch/runs/run_1/postprocess/exec_1/plugins/browser-gallery',
    );
    expect(screen.queryByRole('button', { name: '生成画廊' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '生成真机截图' })).not.toBeInTheDocument();
  });

  it('deletes a task and its local records after confirmation', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    let tasks = [{
      taskId: 'task_1', name: '天气回归', datasetId: 'request_dataset', sampleIds: ['Q001'],
      sampleCount: 1, requestOverrides: {}, concurrency: 4, maxRetries: 1,
      timeoutSeconds: 300, backendMode: 'managed' as const, toolWsBaseUrl: 'ws://localhost',
      serviceConfig: {}, createdAt: '', updatedAt: '', runCount: 0, latestRun: null,
    }];
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === '/debug/batch/tasks/task_1' && init?.method === 'DELETE') {
        tasks = [];
        return response({}, 204);
      }
      if (url === '/debug/batch/tasks') return response({ items: tasks });
      if (url === '/debug/batch/scheduler') {
        return response({ paused: false, activeRunId: null, active: null, queue: [] });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });
    render(<MemoryRouter><BatchTaskCenterRoute /></MemoryRouter>);

    await userEvent.click(await screen.findByRole('button', { name: '删除' }));

    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('执行记录和本地文件'));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      '/debug/batch/tasks/task_1', expect.objectContaining({ method: 'DELETE' }),
    ));
    await waitFor(() => expect(screen.queryByText('天气回归')).not.toBeInTheDocument());
    expect(screen.queryByText('历史执行记录（旧版）')).not.toBeInTheDocument();
  });

  it('excludes cancelled and unexecuted samples from stopped-task progress', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url === '/debug/batch/tasks') return response({ items: [{
        taskId: 'task_1', name: '中途停止', datasetId: 'request_dataset',
        sampleIds: ['Q001', 'Q002', 'Q003', 'Q004'], sampleCount: 4,
        requestOverrides: {}, concurrency: 4, maxRetries: 1, timeoutSeconds: 300,
        backendMode: 'managed', toolWsBaseUrl: 'ws://localhost', serviceConfig: {},
        createdAt: '', updatedAt: '', runCount: 1, latestRun: {
          runId: 'run_1', taskId: 'task_1', status: 'cancelled', createdAt: '',
          backendMode: 'managed', serviceStatus: 'managed_running', total: 4,
          completed: 4, success: 1, degraded: 0, failed: 1, cancelled: 2,
        },
      }] });
      if (url === '/debug/batch/scheduler') return response({
        paused: false, activeRunId: null, active: null, queue: [],
      });
      throw new Error(`unexpected fetch: ${url}`);
    });
    render(<MemoryRouter><BatchTaskCenterRoute /></MemoryRouter>);

    expect(await screen.findByText('50%')).toBeInTheDocument();
    expect(screen.getByText('2/4 · 成功 1 · 失败 1')).toBeInTheDocument();
  });
});
