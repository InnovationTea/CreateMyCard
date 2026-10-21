import { afterEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { parseInput, resolveAppVersion } from '../../../card_renderer/frontend/src/parser';

const genui = [
  { version: 'v0.9', createSurface: { surfaceId: 'python' } },
  { version: 'v0.9', updateComponents: {
    surfaceId: 'python', root: 'root', components: [
      { id: 'root', component: 'Text', content: { path: '/battery' } },
    ],
  } },
  { version: 'v0.9', updateDataModel: { surfaceId: 'python', path: '/battery', value: 68 } },
].map(row => JSON.stringify(row)).join('\n');

afterEach(() => vi.unstubAllGlobals());

describe('Python 是 Compact 预览的唯一转换器', () => {
  it('设备页的双城市天气消息数组与原始 JSONL 使用相同渲染数据', async () => {
    const source = readFileSync(new URL('../../fixtures/card_renderer/a2ui-weather-cities.jsonl', import.meta.url), 'utf8');
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    const original = await parseInput(source);
    const device = await parseInput(JSON.stringify(source.trim().split('\n').map(row => JSON.parse(row))));
    expect(device.mode).toBe('A2UI');
    expect(device.components).toEqual(original.components);
    expect(device.data).toEqual(original.data);
    expect(device.jsonl).toBe(original.jsonl);
    expect(device.surface).toEqual(original.surface);
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it.each(['PillButton', 'CircleButton', 'ProgressCircle', 'FuturePythonComponent'])(
    '%s 原样交给 Python，不在浏览器展开或限制类型', async (component) => {
      const source = JSON.stringify(['root', component, { label: '电量' }]);
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true, json: async () => ({ genui, size: '2x4' }),
      });
      vi.stubGlobal('fetch', fetchMock);
      const signal = new AbortController().signal;
      const document = await parseInput(source, {
        cardSize: 'auto', conversionUrl: '/custom/convert', signal,
      });
      expect(fetchMock).toHaveBeenCalledOnce();
      expect(fetchMock.mock.calls[0][0]).toBe('/custom/convert');
      const request = fetchMock.mock.calls[0][1];
      expect(JSON.parse(request.body)).toEqual({ source, size: 'auto' });
      expect(request.signal).toBe(signal);
      expect(document.surface).toEqual({ width: 300, height: 150 });
      expect(document.components.get('root')?.type).toBe('Text');
      expect(document.graph.getDataModelValue('python', '/battery')).toBe(68);
      expect(document.jsonl).toBe(genui);
    },
  );

  it('从 artifact 外壳解包 Design Compact 输入并传递指定尺寸', async () => {
    const source = '["root","Column",{"design":"fusion-ball-battery-teal"}]';
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ genui, size: '2x2' }),
    });
    vi.stubGlobal('fetch', fetchMock);
    const document = await parseInput(JSON.stringify({ artifact: {
      genui: source, taskSpec: { appVersion: '12.0.0.1' },
    } }), { cardSize: '2x2', appVersion: '11.0.0.0' });
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ source, size: '2x2', appVersion: '12.0.0.1' });
    expect(document.mode).toBe('Design Compact DSL');
  });

  it.each([
    genui,
    JSON.stringify(genui.split('\n').map(row => JSON.parse(row))),
    JSON.stringify({ artifact: { genui: genui.split('\n').map(row => JSON.parse(row)) } }),
    '{"root":{"type":"Extended.Text","props":{"content":"Graph"}}}',
  ])(
    '已有 A2UI 或 Graph 不调用转换接口', async (source) => {
      const fetchMock = vi.fn();
      vi.stubGlobal('fetch', fetchMock);
      const document = await parseInput(source);
      expect(document.graph.getRoot()).toBeTruthy();
      expect(fetchMock).not.toHaveBeenCalled();
    },
  );

  it('服务端拒绝时显示原因，禁止浏览器回退', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, json: async () => ({ detail: '组件合同不合法' }) });
    vi.stubGlobal('fetch', fetchMock);
    await expect(parseInput('["root","Text",{"content":"原输入"}]')).rejects.toThrow('组件合同不合法');
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it('后端不可用时失败，不在浏览器生成替代结果', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('连接失败')));
    await expect(parseInput('["root","Text",{"content":"原输入"}]')).rejects.toThrow('连接失败');
  });

  it.each([
    { genui, size: '3x3' },
    { genui: '["root","Text",{"content":"不是 A2UI"}]', size: '2x2' },
  ])('拒绝错误尺寸或非 A2UI 返回，避免递归转换', async (result) => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => result });
    vi.stubGlobal('fetch', fetchMock);
    await expect(parseInput('["root","Text",{"content":"原输入"}]')).rejects.toThrow('Python 转换服务');
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it('取消后即使请求返回也不解析结果', async () => {
    const controller = new AbortController();
    controller.abort();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ genui, size: '2x2' }) }));
    await expect(parseInput('["root","Text",{}]', { signal: controller.signal })).rejects.toThrow();
  });
});

describe('原始客户端版本', () => {
  it.each([
    [{ taskspec: '{"appVersion":"12.0.0.1"}' }, '12.0.0.1'],
    [{ request: { deviceInfo: { prdVer: '11.9.0.1' } } }, '11.9.0.1'],
    [{ taskSpec: { appVersion: 'invalid' }, request: { deviceInfo: { prdVer: '12.0.0.1' } } }, 'invalid'],
    [{ taskSpec: { appVersion: '' }, appVersion: '12.0.0.1' }, ''],
    [{ version: 'v0.9' }, undefined],
    [{ deviceInfo: { prdVer: '12.0.0.1' }, artifact: { taskSpec: { appVersion: '11.0.0.0' } } }, '11.0.0.0'],
  ])('从 %j 取版本，不伪造或升级原版本', (source, version) => {
    expect(resolveAppVersion(source)).toBe(version);
  });
  it('裸 DSL 传递显式版本', async () => {
    const source = '["root","Text",{"content":"会议"}]';
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ genui, size: '2x2' }) });
    vi.stubGlobal('fetch', fetchMock);
    await parseInput(source, { appVersion: '12.0.0.1' });
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ source, size: 'auto', appVersion: '12.0.0.1' });
  });
});
