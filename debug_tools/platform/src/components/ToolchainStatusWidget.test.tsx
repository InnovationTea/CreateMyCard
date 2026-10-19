import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import * as deviceApi from '../deviceApi';
import { ToolchainStatusWidget } from './ToolchainStatusWidget';

describe('连接配置环境状态', () => {
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); });

  it('shares one environment request, polls every ten seconds and stops after leaving', async () => {
    vi.useFakeTimers();
    const request = vi.spyOn(deviceApi, 'getDeviceEnvironment').mockResolvedValue({
      checks: [{ name: 'Node', ok: true, detail: 'node-path' }],
      status: [
        { id: 'toolchain', label: 'DevEco 工具链', ok: true, detail: 'tools' },
        { id: 'project', label: '渲染工程', ok: true, detail: 'project-path' },
      ],
    });
    const view = render(<ToolchainStatusWidget />);
    await act(async () => {});
    expect(request).toHaveBeenCalledTimes(1);
    expect(screen.queryByText('DevEco 工具链')).not.toBeInTheDocument();
    expect(screen.getByText('渲染工程').closest('.backend-status-item')).toHaveClass('available');
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    expect(request).toHaveBeenCalledTimes(2);
    view.unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    expect(request).toHaveBeenCalledTimes(2);
    expect(request.mock.calls[0][0]?.aborted).toBe(true);
  });
});
