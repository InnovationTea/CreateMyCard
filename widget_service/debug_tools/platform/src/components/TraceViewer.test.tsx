import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import * as api from '../batchApi';
import { TraceArtifact, TraceNode, TraceView } from '../batchApi';
import { TraceViewer } from './TraceViewer';

function trace(status = 'complete'): TraceView {
  const artifact: TraceArtifact = {
    id: 'model:output', ownerNodeId: 'model', label: '模型原文', name: 'initial_assistant_raw',
    role: 'output', mediaType: 'application/json', bytes: 11, sha256: 'a'.repeat(64), available: true,
  };
  const node = (id: string, title: string, parentId: string | null, kind: TraceNode['kind']): TraceNode => ({
    id, title, operation: id, parentId, kind, name: `${id}.completed`, category: 'model',
    stage: id, status: 'success', startOffsetMs: id === 'model' ? 5 : 0,
    durationMs: id === 'model' ? 8 : 20, attempts: {}, attributes: {}, metrics: {},
    artifacts: [], events: [], raw: { event: `${id}.completed` },
  });
  const root = node('request', '请求全链路', null, 'group');
  const phase = node('dsl', '生成 DSL', 'request', 'group');
  const model = node('model', '模型调用 · 第 1 次', 'dsl', 'model');
  model.status = 'failed';
  model.artifacts = [artifact];
  phase.contentIndex = [artifact];
  const queue = node('queue', '等待模型执行配额', 'model', 'step');
  queue.events = [{ eventId: 'e1', startOffsetMs: 6, event: 'queue.acquired' }];
  return {
    viewVersion: 'trace-view-v2', instrumentationVersion: 2, uid: 'batch-1234abcd-00001-000',
    traceId: 'trace-id', sourceSchemaVersion: 'generation-trace-v2', status, timingMode: 'exact',
    recordCount: 5, summary: { totalDurationMs: 20, modelPhysicalCalls: 1, retryCount: 0, totalTokens: 42 },
    warnings: [], nodes: [root, phase, model, queue],
  };
}

function show(view = trace()) {
  render(<TraceViewer runId="run" attempts={[{ name: 'attempt_000', trace: view }]} />);
}

describe('TraceViewer semantic flow', () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it('shows Chinese stages, collapsed model children and a content directory with sources', async () => {
    show();
    expect(screen.getByRole('button', { name: /生成 DSL 成功/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /等待模型执行配额 成功/ })).not.toBeInTheDocument();
    expect(screen.getByText('内容目录 · 1')).toBeInTheDocument();
    expect(screen.getByText(/来源：模型调用 · 第 1 次/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '展开 模型调用 · 第 1 次' }));
    expect(screen.getByRole('button', { name: /等待模型执行配额 成功/ })).toBeInTheDocument();
  });

  it('loads the first real content automatically and disables empty tabs', async () => {
    const load = vi.spyOn(api, 'getBatchTraceArtifact').mockResolvedValue({ content: '{"ok":true}', mediaType: 'application/json' });
    show();
    await userEvent.click(screen.getByRole('button', { name: /模型调用 · 第 1 次 失败/ }));
    expect(await screen.findByText(/"ok": true/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '输入 (0)' })).toBeDisabled();
    expect(load).toHaveBeenCalledWith('run', 'a'.repeat(64), 11, expect.any(AbortSignal));
  });

  it('preserves ancestors when filtering and highlights selected relations', async () => {
    show();
    await userEvent.type(screen.getByLabelText('搜索 Trace 节点'), '执行配额');
    expect(screen.getByRole('button', { name: /请求全链路 成功/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /生成 DSL 成功/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /等待模型执行配额 成功/ }));
    expect(screen.getByRole('button', { name: /生成 DSL 成功/ }).closest('.trace-tree-row')).toHaveClass('is-related');
  });

  it('zooms the time axis, opens technical events and expands the inspector', async () => {
    show();
    await userEvent.click(screen.getByRole('button', { name: '缩放到所选区间' }));
    expect(screen.getByRole('button', { name: '恢复全请求时间轴' })).toBeEnabled();
    await userEvent.click(screen.getByRole('button', { name: '完整技术轨迹' }));
    expect(document.querySelector('[title="queue.acquired · 6.00 ms"]')).not.toBeNull();
    await userEvent.click(screen.getByRole('button', { name: '正文全宽查看' }));
    expect(document.querySelector('.trace-main-full')).not.toBeNull();
  });

  it('changes batch attempts and resets selection and zoom', async () => {
    const second = trace(); second.traceId = 'second'; second.nodes[1].title = '第二轮 DSL';
    render(<TraceViewer runId="run" attempts={[{ name: 'attempt_000', trace: trace() }, { name: 'attempt_001', trace: second }]} />);
    expect(screen.getByRole('heading', { name: '第二轮 DSL' })).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText('批跑 attempt'), 'attempt_000');
    expect(screen.getByRole('heading', { name: '生成 DSL' })).toBeInTheDocument();
  });

  it.each(['complete', 'partial', 'missing', 'invalid'])('renders %s integrity separately', (status) => {
    show(trace(status));
    expect(screen.getByText({ complete: '完整', partial: '部分', missing: '缺失', invalid: '无效' }[status]!)).toBeInTheDocument();
  });

  it('restricts older views to explicitly labelled raw records', () => {
    const old = trace(); old.viewVersion = 'trace-view-v1';
    show(old);
    expect(screen.getByText(/旧埋点仅提供原始查看/)).toBeInTheDocument();
    expect(screen.queryByLabelText('搜索 Trace 节点')).not.toBeInTheDocument();
  });
});
