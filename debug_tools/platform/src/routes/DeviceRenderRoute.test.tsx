import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DeviceRenderRoute } from './DeviceRenderRoute';

class FakeSocket {
  static instances: FakeSocket[] = [];
  binaryType = '';
  onmessage: ((event: { data: string }) => void) | null = null;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close = vi.fn();
  constructor(public url: URL) { FakeSocket.instances.push(this); }
}

describe('设备渲染', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  beforeEach(() => {
    localStorage.clear(); FakeSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeSocket);
    fetchMock = vi.fn(async (url: string) => {
      let body: unknown = {};
      if (url.endsWith('/targets')) body = {
        targets: [{ id: 'device-a', name: '测试设备', serial: 'USB123', kind: 'unknown' }],
        emulators: [{ id: 'emulator-a', name: '测试虚拟机', ready: true, path: 'local' }],
      };
      if (url.endsWith('/environment')) body = { checks: [], status: [] };
      if (url.endsWith('/convert')) body = { text: '[{"createSurface":{}}]' };
      return { ok: true, json: async () => body };
    });
    vi.stubGlobal('fetch', fetchMock);
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('requires an explicit target and preserves edited code', async () => {
    render(<DeviceRenderRoute />);
    await screen.findByText(/测试设备 · USB123/);
    fireEvent.change(screen.getByLabelText('A2UI 代码'), { target: { value: '{"test":1}' } });
    expect(screen.getByRole('button', { name: '编译并运行' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText('在线设备'), { target: { value: 'device-a' } });
    await waitFor(() => expect(screen.getByRole('button', { name: '编译并运行' })).toBeEnabled());
    expect(localStorage.getItem('ai-widget-device-editor:v1')).toContain('test');
  });

  it('shows normalized A2UI without deploying', async () => {
    render(<DeviceRenderRoute />);
    fireEvent.change(screen.getByLabelText('A2UI 代码'), { target: { value: '{}' } });
    await waitFor(() => expect(screen.getByText('已自动识别并转换')).toBeInTheDocument());
    expect(screen.getByText('实际写入工程的 A2UI')).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith('/runs'))).toBe(false);
  });

  it('starts a local emulator and selects its HDC target', async () => {
    let online = false;
    fetchMock.mockImplementation(async (url: string) => {
      let body: unknown = {};
      if (url.endsWith('/targets')) body = {
        targets: online ? [{
          id: 'emulator-target', name: '测试虚拟机', serial: '127.0.0.1:5555', kind: 'emulator',
        }] : [],
        emulators: [{ id: 'emulator-a', name: '测试虚拟机', ready: true, path: 'local' }],
      };
      if (url.endsWith('/environment')) body = { checks: [], status: [] };
      if (url.endsWith('/emulators/emulator-a/start')) body = {
        id: 'emulator-a', status: 'running', message: '正在启动本地模拟器',
      };
      if (url.endsWith('/operations/emulator-a')) {
        online = true;
        body = {
          id: 'emulator-a', status: 'success', message: '模拟器已连接 HDC，可以开始截图',
          targetId: 'emulator-target', serial: '127.0.0.1:5555',
        };
      }
      return { ok: true, json: async () => body };
    });
    render(<DeviceRenderRoute />);
    fireEvent.click(await screen.findByRole('button', { name: '启动 测试虚拟机' }));
    await waitFor(() => expect(screen.getByLabelText('在线设备')).toHaveValue('emulator-target'), {
      timeout: 2500,
    });
    expect(screen.getByText(/模拟器已连接 HDC，可以开始截图/)).toBeInTheDocument();
  });

  it('closes subscription when paused and when unmounted', async () => {
    const view = render(<DeviceRenderRoute />);
    await screen.findByText(/测试设备 · USB123/);
    fireEvent.change(screen.getByLabelText('在线设备'), { target: { value: 'device-a' } });
    expect(FakeSocket.instances).toHaveLength(1);
    const first = FakeSocket.instances[0];
    fireEvent.click(screen.getByRole('button', { name: '暂停' }));
    expect(first.close).toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '恢复' }));
    expect(FakeSocket.instances).toHaveLength(2);
    view.unmount();
    expect(FakeSocket.instances[1].close).toHaveBeenCalled();
  });

  it('displays conversion failure and permits retry', async () => {
    fetchMock.mockImplementation(async (url: string) => ({
      ok: !url.endsWith('/convert'),
      json: async () => url.endsWith('/convert') ? { detail: '输入无效' }
        : url.endsWith('/targets') ? { targets: [], emulators: [] } : { checks: [], status: [] },
    }));
    render(<DeviceRenderRoute />);
    fireEvent.change(screen.getByLabelText('A2UI 代码'), { target: { value: 'bad' } });
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('输入无效'));
  });
});
