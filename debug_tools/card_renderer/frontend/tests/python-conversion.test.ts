import { afterEach, describe, expect, it, vi } from 'vitest';
import { parseInput } from '../src/parser';

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
    const document = await parseInput(JSON.stringify({ artifact: { genui: source } }), { cardSize: '2x2' });
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ source, size: '2x2' });
    expect(document.mode).toBe('Design Compact DSL');
  });

  it.each([genui, '{"root":{"type":"Extended.Text","props":{"content":"Graph"}}}'])(
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
