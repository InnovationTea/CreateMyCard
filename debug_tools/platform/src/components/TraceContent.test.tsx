import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import * as api from '../batchApi';
import { TraceArtifact } from '../batchApi';
import { TraceContent } from './TraceContent';

const artifact = (digest: string, bytes = 10): TraceArtifact => ({
  id: digest, sha256: digest, name: 'output', role: 'output', mediaType: 'text/plain', bytes, available: true,
});

describe('TraceContent loading lifecycle', () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it('handles empty content as loaded and retains download controls', async () => {
    vi.spyOn(api, 'getBatchTraceArtifact').mockResolvedValue({ content: '', mediaType: 'text/plain' });
    render(<TraceContent artifact={artifact('empty', 0)} runId="empty-run" source="模型调用" autoLoad />);
    expect(await screen.findByText('内容已加载：空文本（0 字节）')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '下载' })).toBeInTheDocument();
  });

  it('leaves large content lazy and retries a local failure', async () => {
    const load = vi.spyOn(api, 'getBatchTraceArtifact').mockRejectedValueOnce(new Error('SHA-256 不匹配'))
      .mockResolvedValue({ content: '完整大文本', mediaType: 'text/plain' });
    render(<TraceContent artifact={artifact('large', 300000)} runId="large-run" source="模型调用" autoLoad />);
    expect(load).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: '加载完整内容' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('SHA-256 不匹配');
    await userEvent.click(screen.getByRole('button', { name: '重试加载' }));
    expect(await screen.findByText('完整大文本')).toBeInTheDocument();
  });

  it('aborts stale requests when the node content changes', async () => {
    let resolveFirst: (value: { content: string; mediaType: string }) => void = () => {};
    const load = vi.spyOn(api, 'getBatchTraceArtifact').mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve; }))
      .mockResolvedValue({ content: '新节点内容', mediaType: 'text/plain' });
    const page = render(<TraceContent artifact={artifact('old')} runId="race-run" source="旧节点" autoLoad />);
    await waitFor(() => expect(load).toHaveBeenCalledTimes(1));
    const signal = load.mock.calls[0][3];
    page.rerender(<TraceContent artifact={artifact('new')} runId="race-run" source="新节点" autoLoad />);
    expect(await screen.findByText('新节点内容')).toBeInTheDocument();
    resolveFirst({ content: '旧节点内容', mediaType: 'text/plain' });
    await waitFor(() => expect(signal?.aborted).toBe(true));
    expect(screen.queryByText('旧节点内容')).not.toBeInTheDocument();
  });
});
