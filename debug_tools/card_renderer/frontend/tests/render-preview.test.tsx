// @vitest-environment jsdom

import React from 'react';
import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { CardRenderer } from '../src/CardRenderer';
import { CardPreview } from '../src/render';
import { parseInput } from '../src/parser';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const CONVERTED_A2UI = [
  '{"version":"v0.9","createSurface":{"surfaceId":"surface_card","catalogId":"ohos.a2ui.extended.catalog.form"}}',
  '{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[' +
    '{"id":"root","component":"Column","children":["text"]},' +
    '{"id":"text","component":"Text","content":"Python 转换结果"}]}}',
  '{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{}}}',
].join('\n');

describe('Render 内核预览', () => {
  it('调用 Python 转换并用返回尺寸渲染 A2UI，更新编辑器', async () => {
    const source = '["root","Text",{"content":"原始 DSL"}]';
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ genui: CONVERTED_A2UI, size: '2x4' }),
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<CardRenderer initialValue={source} conversionUrl="/debug/renderer/convert" />);
    fireEvent.click(screen.getByRole('button', { name: 'Python 转换并渲染' }));

    await waitFor(() => expect(screen.getByText('Python 转换结果')).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe('/debug/renderer/convert');
    expect(JSON.parse(options.body)).toEqual({ source, size: 'auto' });
    expect(screen.getByRole('textbox', { name: 'DSL 输入' })).toHaveValue(CONVERTED_A2UI);
    expect(screen.getByRole('combobox', { name: '画布' })).toHaveValue('2x4');
    expect(screen.getByText(/A2UI · 300 × 150/)).toBeInTheDocument();
  });

  it('转换失败显示服务端原因并保留原始 DSL', async () => {
    const source = '["root","Text",{"content":"保留输入"}]';
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ detail: 'PillButton requires label' }),
    }));
    render(<CardRenderer initialValue={source} conversionUrl="/debug/renderer/convert" />);
    fireEvent.click(screen.getByRole('button', { name: 'Python 转换并渲染' }));

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('PillButton requires label'));
    expect(screen.getByRole('textbox', { name: 'DSL 输入' })).toHaveValue(source);
  });

  it('转换途中编辑输入，取消旧请求且迟到结果不覆盖新内容', async () => {
    let resolveResponse!: (value: unknown) => void;
    const fetchMock = vi.fn().mockImplementation(() => new Promise(resolve => {
      resolveResponse = resolve;
    }));
    vi.stubGlobal('fetch', fetchMock);
    render(<CardRenderer initialValue='["root","Text",{"content":"旧内容"}]' conversionUrl="/debug/renderer/convert" />);
    fireEvent.click(screen.getByRole('button', { name: 'Python 转换并渲染' }));
    const [, options] = fetchMock.mock.calls[0];
    const nextSource = '["root","Text",{"content":"新内容"}]';
    fireEvent.change(screen.getByRole('textbox', { name: 'DSL 输入' }), { target: { value: nextSource } });
    expect(options.signal.aborted).toBe(true);
    resolveResponse({ ok: true, json: async () => ({ genui: CONVERTED_A2UI, size: '2x2' }) });

    await waitFor(() => expect(screen.getByText('新内容')).toBeInTheDocument());
    expect(screen.getByRole('textbox', { name: 'DSL 输入' })).toHaveValue(nextSource);
    expect(screen.queryByText('Python 转换结果')).not.toBeInTheDocument();
  });

  it('使用 renderTree 绘制并安全回传点击动作', async () => {
    const source = [
      '["root","Column",{"onClick":[{"call":"clickToDeeplink","args":{"uri":"demo://card"}}]},["text"]]',
      '["text","Text",{"content":"打开详情"}]',
    ].join('\n');
    const document = parseInput(source);
    const onAction = vi.fn();

    const { container } = render(<CardPreview document={document} onAction={onAction} />);

    expect(container.querySelector('[data-renderer-engine="render"]')).toBeTruthy();
    fireEvent.click(container.querySelector('[data-node-id="root"]') as HTMLElement);
    await waitFor(() => expect(onAction).toHaveBeenCalledOnce());
    expect(onAction.mock.calls[0][0]).toEqual({
      functionCall: { call: 'clickToDeeplink', args: { uri: 'demo://card' } },
    });
    expect(onAction.mock.calls[0][1].id).toBe('root');
  });

  it('按 assetBaseUrl 重写本地素材路径', () => {
    const document = parseInput(
      '["root","Image",{"src":"resources/base/media/sun_max.svg","width":20,"height":20}]',
    );
    const { container } = render(
      <CardPreview document={document} assetBaseUrl="/custom-assets/" />,
    );

    expect(container.querySelector('img')).toHaveAttribute(
      'src',
      '/custom-assets/base/media/sun_max.svg',
    );
  });

  it('TextInput 写回 DataModel 后局部刷新绑定文本', async () => {
    const source = [
      '{"version":"v0.9","createSurface":{"surfaceId":"form"}}',
      '{"version":"v0.9","updateComponents":{"surfaceId":"form","root":"root","components":[' +
        '{"id":"root","component":"Column","children":["input","echo"]},' +
        '{"id":"input","component":"Extended.TextInput","text":{"path":"/name"}},' +
        '{"id":"echo","component":"Text","content":{"path":"/name"}}]}}',
      '{"version":"v0.9","updateDataModel":{"surfaceId":"form","path":"/name","value":"初始值"}}',
    ].join('\n');
    const document = parseInput(source);

    render(<CardPreview document={document} />);
    const input = screen.getByRole('textbox');
    expect(input).toHaveValue('初始值');
    fireEvent.change(input, { target: { value: '已编辑' } });

    await waitFor(() => expect(screen.getByText('已编辑')).toBeInTheDocument());
    expect(input).toHaveValue('已编辑');
  });

  it('保留 CardRenderer 编辑器与自动渲染状态', async () => {
    render(<CardRenderer initialValue='["root","Text",{"content":"迁移完成"}]' />);

    expect(screen.getByRole('textbox', { name: 'DSL 输入' })).toHaveValue(
      '["root","Text",{"content":"迁移完成"}]',
    );
    await waitFor(() => expect(screen.getByText(/已渲染 1 个组件/)).toBeInTheDocument());
    expect(screen.getByText('迁移完成')).toBeInTheDocument();
  });

  it('supports preview-only rendering with host-controlled zoom', async () => {
    const onZoomChange = vi.fn();
    const { container, rerender } = render(
      <CardRenderer
        initialValue='["root","Text",{"content":"精简预览"}]'
        previewOnly
        zoom={175}
        onZoomChange={onZoomChange}
      />,
    );

    await waitFor(() => expect(screen.getByText('精简预览')).toBeInTheDocument());
    expect(screen.queryByRole('textbox', { name: 'DSL 输入' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '渲染' })).not.toBeInTheDocument();
    expect(screen.getByRole('slider', { name: /^缩放/ })).toHaveValue('175');

    fireEvent.change(screen.getByRole('slider', { name: /^缩放/ }), { target: { value: '190' } });
    expect(onZoomChange).toHaveBeenCalledWith(190);

    rerender(<CardRenderer initialValue='["root","Text",{"content":"另一条样本"}]' previewOnly zoom={190} onZoomChange={onZoomChange} />);
    await waitFor(() => expect(screen.getByText('另一条样本')).toBeInTheDocument());
    expect(screen.getByRole('slider', { name: /^缩放/ })).toHaveValue('190');
    expect(container.querySelector('.card-renderer--preview-only')).toBeTruthy();
  });

  it('使用宿主从 CardSpec 或 query 解析出的卡片尺寸', async () => {
    const { container } = render(
      <CardRenderer
        initialValue='["root","Text",{"content":"宽卡"}]'
        cardSize="2x4"
      />,
    );

    await waitFor(() => expect(screen.getByText(/300 × 150/)).toBeInTheDocument());
    expect(container.querySelector('[data-renderer-size="300x150"]')).toBeTruthy();
    expect(screen.getByRole('combobox', { name: /画布/ })).toHaveValue('2x4');
  });

  it('允许用户调整卡片容器宽高且不显示示例入口', async () => {
    const { container } = render(
      <CardRenderer initialValue='["root","Text",{"content":"自定义尺寸"}]' />,
    );

    await waitFor(() => expect(screen.getByText(/150 × 150/)).toBeInTheDocument());
    expect(screen.queryByText('打开 JSONL')).not.toBeInTheDocument();
    expect(screen.queryByText('A2UI 示例')).not.toBeInTheDocument();
    expect(screen.queryByText('极简示例')).not.toBeInTheDocument();
    expect(screen.queryByText('Design 示例')).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole('spinbutton', { name: '容器宽度' }), {
      target: { value: '240' },
    });
    fireEvent.change(screen.getByRole('spinbutton', { name: '容器高度' }), {
      target: { value: '180' },
    });

    expect(screen.getByText(/240 × 180/)).toBeInTheDocument();
    expect(container.querySelector('[data-renderer-size="240x180"]')).toBeTruthy();
  });
});
