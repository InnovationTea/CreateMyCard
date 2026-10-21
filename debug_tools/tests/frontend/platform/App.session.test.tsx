import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import App from '../../../platform/src/App';
import { executeBrowserTool } from '../../../platform/src/toolBridge';
import type { BrowserToolResult } from '@widget-debug/end-to-end';

vi.mock('../../../platform/src/components/BackendStatusWidget', () => ({
  BackendStatusWidget: () => null,
  SelectedMicroserviceStatus: () => null,
}));
vi.mock('../../../platform/src/components/SettingsPanel', () => ({ default: () => <h1>连接配置页面</h1> }));
vi.mock('../../../platform/src/routes/InterfaceRoute', () => ({ InterfaceRoute: () => <h1>接口调试页面</h1> }));
vi.mock('../../../platform/src/routes/RendererRoute', () => ({ RendererRoute: () => <h1>卡片渲染页面</h1> }));
vi.mock('../../../platform/src/routes/BatchTaskCenterRoute', () => ({ BatchTaskCenterRoute: () => <h1>批量测试页面</h1> }));
vi.mock('../../../platform/src/routes/QualityRoute', () => ({ QualityRoute: () => <h1>质量评分页面</h1> }));
vi.mock('../../../platform/src/toolBridge', async (importOriginal) => ({
  ...await importOriginal<typeof import('../../../platform/src/toolBridge')>(),
  executeBrowserTool: vi.fn(),
}));

class AgentSocket {
  static OPEN = 1;
  static instances: AgentSocket[] = [];
  readyState = 0;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  send = vi.fn((_payload: string) => {});
  close = vi.fn(() => { this.readyState = 3; });

  constructor(readonly url: string) {
    AgentSocket.instances.push(this);
  }

  emit(event: Record<string, unknown>) {
    act(() => { this.onmessage?.({ data: JSON.stringify(event) }); });
  }
}

function navigate(label: string) {
  const navigation = within(screen.getByRole('navigation', { name: '调试模块' }));
  fireEvent.click(navigation.getByRole('link', { name: new RegExp(label) }));
}

function openSession() {
  const socket = AgentSocket.instances.at(-1);
  if (!socket) throw new Error('未建立 Agent 连接');
  act(() => {
    socket.readyState = AgentSocket.OPEN;
    socket.onopen?.();
  });
  socket.emit({ type: 'conversation.ready', conversationId: 'session-keep', resumed: false });
  return socket;
}

function toolCall(socket: AgentSocket, callId: string) {
  socket.emit({
    type: 'tool.call',
    conversationId: 'session-keep',
    turnId: 'turn-keep',
    callId,
    functionName: 'getWidgetCapabilityOverview',
    arguments: {},
  });
  const call = vi.mocked(executeBrowserTool).mock.calls.at(-1);
  if (!call?.[3]?.signal) throw new Error('未开始浏览器工具调用');
  return call[3].signal;
}

describe('端到端会话在工作台导航期间保留', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    AgentSocket.instances = [];
    vi.stubGlobal('WebSocket', AgentSocket);
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ status: 'ok' }) })));
    vi.mocked(executeBrowserTool).mockReset();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('首次进入才创建连接，重复进入不重新连接', () => {
    render(<MemoryRouter initialEntries={['/settings']}><App /></MemoryRouter>);
    expect(AgentSocket.instances).toHaveLength(0);
    navigate('端到端调试');
    const socket = openSession();
    navigate('连接配置');
    navigate('端到端调试');
    expect(AgentSocket.instances).toHaveLength(1);
    expect(socket.close).not.toHaveBeenCalled();
  });

  it.each(['接口调试', '卡片渲染', '批量测试', '质量评分', '连接配置'])(
    '切换到%s后保留消息、轨迹、草稿和原会话',
    (destination) => {
      render(<MemoryRouter initialEntries={['/end-to-end/']}><App /></MemoryRouter>);
      const socket = openSession();
      socket.emit({ type: 'assistant.message', turnId: 'turn-keep', content: '天气卡片已生成' });
      const composer = screen.getByPlaceholderText('描述你想创建的卡片');
      fireEvent.change(composer, { target: { value: '把背景改为蓝色' } });
      navigate(destination);
      expect(screen.queryByRole('heading', { name: '创建一张卡片' })).not.toBeInTheDocument();
      expect(screen.getByRole('heading', { name: `${destination}页面` })).toBeVisible();
      expect(socket.close).not.toHaveBeenCalled();

      navigate('端到端调试');
      expect(screen.getByText('天气卡片已生成', { selector: '.message-content' })).toBeVisible();
      expect(screen.getByText('Agent 回复', { selector: 'strong' })).toBeVisible();
      expect(screen.getByPlaceholderText('描述你想创建的卡片')).toHaveValue('把背景改为蓝色');
      expect(AgentSocket.instances).toHaveLength(1);
      fireEvent.click(screen.getByRole('button', { name: '发送' }));
      const sent = JSON.parse(socket.send.mock.calls.at(-1)?.[0] ?? '{}');
      expect(sent).toMatchObject({
        type: 'turn.start', conversationId: 'session-keep', text: '把背景改为蓝色',
      });
    },
  );

  it('隐藏期间工具继续执行并回传，返回后显示新结果；新建会话仍可清空', async () => {
    let resolveTool!: (result: BrowserToolResult) => void;
    vi.mocked(executeBrowserTool).mockImplementation(() => new Promise((resolve) => { resolveTool = resolve; }));
    render(<MemoryRouter initialEntries={['/end-to-end']}><App /></MemoryRouter>);
    const socket = openSession();
    const signal = toolCall(socket, 'call-keep');
    navigate('卡片渲染');
    expect(signal.aborted).toBe(false);
    await act(async () => {
      resolveTool({ ok: true, operation: 'getWidgetCapabilityOverview', data: {} });
    });
    expect(socket.send.mock.calls.map(([payload]) => JSON.parse(payload))).toContainEqual(
      expect.objectContaining({ type: 'tool.result', conversationId: 'session-keep', callId: 'call-keep' }),
    );
    socket.emit({ type: 'assistant.message', turnId: 'turn-keep', content: '切换期间生成完成' });
    socket.emit({ type: 'turn.completed', turnId: 'turn-keep', status: 'success' });
    navigate('端到端调试');
    expect(screen.getByText('切换期间生成完成', { selector: '.message-content' })).toBeVisible();
    expect(AgentSocket.instances).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: '新建会话' }));
    expect(JSON.parse(socket.send.mock.calls.at(-1)?.[0] ?? '{}')).toMatchObject({
      type: 'conversation.reset', conversationId: 'session-keep',
    });
    socket.emit({ type: 'conversation.ready', conversationId: 'new-session', resumed: false });
    expect(screen.queryByText('切换期间生成完成', { selector: '.message-content' })).not.toBeInTheDocument();
    expect(screen.getByText('从一个想法开始')).toBeVisible();
  });

  it('离开整个工作台时仍会关闭连接并取消工具调用', () => {
    vi.mocked(executeBrowserTool).mockImplementation(() => new Promise(() => {}));
    const view = render(<MemoryRouter initialEntries={['/end-to-end']}><App /></MemoryRouter>);
    const socket = openSession();
    const signal = toolCall(socket, 'call-unmount');
    navigate('连接配置');
    view.unmount();
    expect(signal.aborted).toBe(true);
    expect(socket.close).toHaveBeenCalledTimes(1);
  });
});
