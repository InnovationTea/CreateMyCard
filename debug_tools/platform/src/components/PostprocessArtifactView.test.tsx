import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { PostprocessArtifact } from '../batchApi';
import { PostprocessArtifactView } from './PostprocessArtifactView';

describe('PostprocessArtifactView', () => {
  afterEach(() => vi.unstubAllGlobals());
  it.each([
    ['metrics', 'kpi', [{ label: '召回率', value: 87.5, unit: '%' }], '87.5'],
    ['records', 'table', [{ component: 'SingleLineTitle', matched: 3 }], 'SingleLineTitle'],
    ['records', 'bar', [{ range: '80–100%', count: 4 }], '80–100%'],
    ['records', 'line', [{ day: '一', count: 1 }, { day: '二', count: 2 }], '二'],
    ['records', 'pie', [{ state: '通过', count: 2 }], '通过'],
    ['matrix', 'heatmap', { rows: ['Card'], columns: ['命中'], cells: [[3]] }, 'Card'],
    ['issues', 'issues', [{ message: '组件缺失' }], '组件缺失'],
    ['json', 'tree', { nested: { value: 1 } }, 'nested'],
    ['text', undefined, '纯文本结果', '纯文本结果'],
    ['code', 'code', '["a", "SingleLineTitle"]', 'SingleLineTitle'],
    ['diff', 'diff', '- old\n+ new', '+ new'],
  ] as Array<[string, string | undefined, unknown, string]>) (
    'renders %s through the controlled registry',
    (dataType, renderer, data, expected) => {
      const { container } = render(<PostprocessArtifactView artifact={{
        key: `${dataType}-${renderer ?? 'default'}`,
        title: '测试产物',
        dataType,
        renderer,
        data,
      } as PostprocessArtifact} />);

      expect(container).toHaveTextContent(expected);
    },
  );

  it('renders images and restricted download links without executable markup', () => {
    const { rerender } = render(<PostprocessArtifactView artifact={{
      key: 'capture',
      title: '截图',
      dataType: 'image',
      url: '/capture.png',
      alt: '样本截图',
    }} />);
    expect(screen.getByRole('img', { name: '样本截图' })).toHaveAttribute('src', '/capture.png');

    rerender(<PostprocessArtifactView artifact={{
      key: 'download',
      title: '文件',
      dataType: 'file',
      url: '/artifact.txt',
    }} />);
    expect(screen.getByRole('link', { name: /下载文件/ })).toHaveAttribute('href', '/artifact.txt');
  });

  it('navigates validation images and keeps failed captures visible', () => {
    render(<PostprocessArtifactView artifact={{
      key: 'validation-renders',
      title: '逐次校验 DSL 浏览器渲染结果',
      dataType: 'image',
      renderer: 'gallery',
      data: [
        {
          label: '执行尝试 1 · 接口调用 1 · 校验评估 1',
          status: '校验失败',
          errorTypes: ['COMPACT_DSL_VALIDATION_FAILED'],
          url: '/validation-1.png',
          alt: '第一次校验',
        },
        {
          label: '执行尝试 1 · 接口调用 2 · 校验评估 1',
          status: '校验通过',
          errorTypes: [],
          error: 'DSL 无法解析',
        },
      ],
    }} />);

    expect(screen.getByRole('img', { name: '第一次校验' })).toHaveAttribute(
      'src',
      '/validation-1.png',
    );
    expect(screen.queryByText('DSL 无法解析')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '下一张图片' }));
    expect(screen.getByText('DSL 无法解析')).toBeInTheDocument();
    expect(screen.getByText(/接口调用 2 · 校验评估 1/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '显示缩略图' }));
    expect(screen.getByRole('button', { name: '查看第 1 张图片' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '查看第 1 张图片' }));
    expect(screen.getByRole('img', { name: '第一次校验' })).toBeInTheDocument();
  });

  it('renders DSL items when a finalized image is not available yet', async () => {
    render(<PostprocessArtifactView artifact={{
      key: 'validation-renders',
      title: '收尾中的 DSL',
      dataType: 'image',
      renderer: 'gallery',
      data: [{
        label: '校验评估 1',
        status: '校验失败',
        size: '2x2',
        dsl: [
          '{"version":"v0.9","createSurface":{"surfaceId":"preview"}}',
          '{"version":"v0.9","updateComponents":{"surfaceId":"preview","root":"root","components":[{"id":"root","component":"Text","content":"DSL 预览"}]}}',
        ].join('\n'),
      }],
    }} />);

    expect(await screen.findByText('DSL 预览')).toBeInTheDocument();
  });

  it('converts Compact gallery items through Python before showing them', async () => {
    const source = '["root","PillButton",{"label":"后处理"}]';
    const genui = [
      '{"version":"v0.9","createSurface":{"surfaceId":"preview"}}',
      '{"version":"v0.9","updateComponents":{"surfaceId":"preview","root":"root","components":[{"id":"root","component":"Text","content":"Python 画廊"}]}}',
    ].join('\n');
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ genui, size: '2x4' }) });
    vi.stubGlobal('fetch', fetchMock);
    render(<PostprocessArtifactView artifact={{
      key: 'gallery', title: '画廊', dataType: 'image', renderer: 'gallery',
      data: [{ label: 'Compact', dsl: source, size: '2x4', appVersion: '12.0.0.1' }],
    }} />);
    expect(await screen.findByText('Python 画廊')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock.mock.calls[0][0]).toBe('/debug/renderer/convert');
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ source, size: '2x4', appVersion: '12.0.0.1' });
  });
});
