import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { WorkbenchProvider } from '../context';
import { SettingsPanel } from './SettingsPanel';

describe('SettingsPanel', () => {
  afterEach(() => {
    cleanup();
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('defaults to deployed service and allows selecting managed service', async () => {
    render(<WorkbenchProvider><SettingsPanel /></WorkbenchProvider>);
    expect(screen.queryByText('分页参数')).not.toBeInTheDocument();
    const deployed = screen.getByRole('radio', { name: /使用已部署微服务/ });
    const managed = screen.getByRole('radio', { name: /使用本地受管微服务/ });
    expect(deployed).toBeChecked();
    expect(screen.queryByText('Main Agent WebSocket')).not.toBeInTheDocument();
    expect(screen.getByText('微服务 WebSocket Base')).toBeInTheDocument();
    expect(screen.queryByText('可选微服务参数')).not.toBeInTheDocument();
    await userEvent.click(managed);
    expect(managed).toBeChecked();
    expect(screen.queryByText('微服务 WebSocket Base')).not.toBeInTheDocument();
    expect(screen.getByText('可选微服务参数')).toBeInTheDocument();
  });
});
