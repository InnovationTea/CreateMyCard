import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DeviceRenderRoute } from './DeviceRenderRoute';

vi.mock('@widget-debug/card-renderer', () => ({
  CardRenderer: ({ initialValue }: { initialValue: string }) => <div data-testid="browser-card">{initialValue}</div>,
}));

describe('设备渲染', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal('WebSocket', vi.fn());
    fetchMock = vi.fn(async (url: string) => {
      let body: unknown = {};
      if (url.endsWith('/targets')) body = {
        targets: [{ id: 'device-a', name: '测试设备', serial: 'USB123', kind: 'unknown' }],
        emulators: [{ id: 'emulator-a', name: '测试虚拟机', ready: true, path: 'local' }],
      };
      if (url.endsWith('/environment')) body = { checks: [], status: [
        { id: 'toolchain', label: 'DevEco 工具链', ok: true, detail: 'tools' },
        { id: 'project', label: '渲染工程', ok: true, detail: 'project' },
      ] };
      if (url.endsWith('/convert')) body = { text: '[{"createSurface":{}}]' };
      return { ok: true, json: async () => body };
    });
    vi.stubGlobal('fetch', fetchMock);
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('requires an explicit target and preserves edited code', async () => {
    render(<DeviceRenderRoute />);
    await screen.findByText(/测试设备 · USB123/);
    expect(screen.queryByText('DevEco 工具链')).not.toBeInTheDocument();
    expect(screen.getByText('渲染工程')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Compact DSL 代码'), { target: { value: '{"test":1}' } });
    expect(screen.getByRole('button', { name: '编译并运行' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText('在线设备'), { target: { value: 'device-a' } });
    await waitFor(() => expect(screen.getByRole('button', { name: '编译并运行' })).toBeEnabled());
    expect(localStorage.getItem('ai-widget-device-editor:v1')).toContain('test');
  });

  it('shows normalized A2UI without deploying', async () => {
    render(<DeviceRenderRoute />);
    fireEvent.change(screen.getByLabelText('Compact DSL 代码'), { target: { value: '{}' } });
    await waitFor(() => expect(screen.getByText('已自动识别并转换')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('tab', { name: 'A2UI' }));
    expect(screen.getByLabelText('A2UI 代码')).toHaveValue('[{"createSurface":{}}]');
    expect(screen.getByTestId('browser-card')).toHaveTextContent('[{"createSurface":{}}]');
    fireEvent.click(screen.getByRole('tab', { name: 'Compact DSL' }));
    expect(screen.getByLabelText('Compact DSL 代码')).toHaveValue('{}');
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

  it('shows only selected previews and never subscribes to full-screen images', async () => {
    localStorage.setItem('ai-widget-device-run:v1', 'run-a');
    const original = fetchMock.getMockImplementation()!;
    fetchMock.mockImplementation(async (url: string) => {
      if (url.endsWith('/runs/run-a')) return { ok: true, json: async () => ({
        id: 'run-a', status: 'success', device: '测试设备', stage: '完成',
        cardImageUrl: '/card.png', fullImageUrl: '/full.png',
      }) };
      return original(url);
    });
    render(<DeviceRenderRoute />);
    const image = await screen.findByAltText('本次运行的卡片截图');
    const toolbar = screen.getByText('渲染预览').closest('.device-toolbar');
    expect(toolbar).toContainElement(screen.getByRole('checkbox', { name: '浏览器截图' }));
    expect(toolbar).toContainElement(screen.getByRole('checkbox', { name: '真机截图' }));
    expect(screen.queryByText('浏览器与设备部署使用同一转换结果')).not.toBeInTheDocument();
    expect(screen.getByRole('region', { name: '渲染预览' })).toContainElement(image);
    expect(image).toHaveAttribute('src', '/card.png');
    expect(screen.queryByAltText('本次运行的设备全屏截图')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('checkbox', { name: '真机截图' }));
    expect(screen.queryByAltText('本次运行的卡片截图')).not.toBeInTheDocument();
    expect(screen.getByTestId('browser-card')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('checkbox', { name: '浏览器截图' }));
    expect(screen.queryByTestId('browser-card')).not.toBeInTheDocument();
    expect(screen.getByText('勾选上方选项查看渲染结果')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('checkbox', { name: '真机截图' }));
    expect(screen.getByAltText('本次运行的卡片截图')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('在线设备'), { target: { value: 'device-a' } });
    expect(WebSocket).not.toHaveBeenCalled();
  });

  it('converts edited A2UI and preserves the Compact draft', async () => {
    render(<DeviceRenderRoute />);
    await screen.findByText(/测试设备 · USB123/);
    fireEvent.change(screen.getByLabelText('Compact DSL 代码'), { target: { value: 'compact draft' } });
    await waitFor(() => expect(screen.getByText('已自动识别并转换')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('tab', { name: 'A2UI' }));
    fireEvent.change(screen.getByLabelText('A2UI 代码'), { target: { value: 'edited a2ui' } });
    fireEvent.change(screen.getByLabelText('在线设备'), { target: { value: 'device-a' } });
    expect(screen.getByRole('button', { name: '编译并运行' })).toBeDisabled();
    await waitFor(() => expect(screen.getByRole('button', { name: '编译并运行' })).toBeEnabled());
    const requests = fetchMock.mock.calls.filter(([url]) => url.endsWith('/convert'));
    expect(JSON.parse(requests.at(-1)?.[1].body)).toMatchObject({ source: 'edited a2ui', format: 'a2ui' });
    fireEvent.click(screen.getByRole('tab', { name: 'Compact DSL' }));
    expect(screen.getByLabelText('Compact DSL 代码')).toHaveValue('compact draft');
  });

  it('restores legacy input in the A2UI tab with automatic detection', async () => {
    localStorage.setItem('ai-widget-device-editor:v1', JSON.stringify({ source: 'legacy input', size: '2x4' }));
    render(<DeviceRenderRoute />);
    expect(screen.getByRole('tab', { name: 'A2UI' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByLabelText('A2UI 代码')).toHaveValue('legacy input');
    expect(screen.getByLabelText('卡片尺寸')).toHaveValue('2x4');
    await waitFor(() => expect(screen.getByText('已自动识别并转换')).toBeInTheDocument());
    const requests = fetchMock.mock.calls.filter(([url]) => url.endsWith('/convert'));
    expect(JSON.parse(requests.at(-1)?.[1].body)).toMatchObject({ source: 'legacy input', format: 'auto' });
  });

  it('displays conversion failure and permits retry', async () => {
    fetchMock.mockImplementation(async (url: string) => ({
      ok: !url.endsWith('/convert'),
      json: async () => url.endsWith('/convert') ? { detail: '输入无效' }
        : url.endsWith('/targets') ? { targets: [], emulators: [] } : { checks: [], status: [] },
    }));
    render(<DeviceRenderRoute />);
    fireEvent.change(screen.getByLabelText('Compact DSL 代码'), { target: { value: 'bad' } });
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('输入无效'));
  });
});
