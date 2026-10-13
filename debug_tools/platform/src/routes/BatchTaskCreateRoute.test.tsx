import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { WorkbenchProvider } from '../context';
import { BatchTaskCreateRoute } from './BatchTaskCreateRoute';

function response(body: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => body } as Response;
}

describe('BatchTaskCreateRoute', () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it('creates a task with its first queued execution and opens the detail page', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === '/debug/batch/datasets') return response({ items: [{ id: 'request_dataset', name: 'request_dataset', sampleCount: 2, validSampleCount: 1, invalidSampleCount: 1 }] });
      if (url === '/debug/batch/service-config/defaults') return response({ values: { enableA2uiModelMock: true, openaiMasterClient: 'llmclient' }, sources: { enableA2uiModelMock: 'debug_agent.yaml', openaiMasterClient: 'debug_agent.yaml' } });
      if (url.endsWith('/datasets/request_dataset/samples')) return response({ items: [
        { id: 'Q001', fileName: 'Q001.json', title: '天气', query: '天气卡片', size: '2x2', valid: true, error: '' },
        { id: 'Q002', fileName: 'Q002.json', title: '损坏', query: '', size: '', valid: false, error: 'invalid' },
      ] });
      if (url === '/debug/batch/tasks' && init?.method === 'POST') return response({
        taskId: 'task_new',
        latestRun: { runId: 'run_new', taskId: 'task_new', status: 'queued', queuePosition: 2 },
        runCount: 1,
      }, 201);
      throw new Error(`unexpected fetch: ${url}`);
    });
    render(<WorkbenchProvider><MemoryRouter initialEntries={['/batch/new']}><Routes>
      <Route path="/batch/new" element={<BatchTaskCreateRoute />} />
      <Route path="/batch/tasks/:taskId" element={<div>任务已自动加入队列</div>} />
    </Routes></MemoryRouter></WorkbenchProvider>);

    expect(await screen.findByText('Q001 · 天气')).toBeInTheDocument();
    expect(screen.getByText('Q002 · 损坏')).toBeInTheDocument();
    expect(screen.getByText(/创建后立即加入后台队列/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '创建并执行' }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      '/debug/batch/tasks', expect.objectContaining({ method: 'POST' }),
    ));
    const createCall = fetchMock.mock.calls.find(([url, init]) => String(url) === '/debug/batch/tasks' && init?.method === 'POST');
    const body = JSON.parse(String(createCall?.[1]?.body));
    expect(body.datasetId).toBe('request_dataset');
    expect(body.sampleIds).toEqual(['Q001']);
    expect(body.requestOverrides).toEqual({});
    expect(body).not.toHaveProperty('concurrency');
    expect(body).not.toHaveProperty('maxRetries');
    expect(body).not.toHaveProperty('timeoutSeconds');
    expect(body).not.toHaveProperty('enableDeviceCapture');
    expect(screen.queryByText('样本并发数')).not.toBeInTheDocument();
    expect(screen.queryByText('单次调用超时（秒）')).not.toBeInTheDocument();
    expect(screen.queryByRole('checkbox', { name: /生成真机截图/ })).not.toBeInTheDocument();
    expect(await screen.findByText('任务已自动加入队列')).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/runs'))).toBe(false);
  });

});
