import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { PostprocessArtifact } from '../batchApi';
import { PostprocessArtifactView } from './PostprocessArtifactView';

describe('PostprocessArtifactView', () => {
  it.each([
    ['metrics', 'kpi', [{ label: '召回率', value: 87.5, unit: '%' }], '87.5'],
    ['records', 'table', [{ component: 'CardHeader', matched: 3 }], 'CardHeader'],
    ['records', 'bar', [{ range: '80–100%', count: 4 }], '80–100%'],
    ['records', 'line', [{ day: '一', count: 1 }, { day: '二', count: 2 }], '二'],
    ['records', 'pie', [{ state: '通过', count: 2 }], '通过'],
    ['matrix', 'heatmap', { rows: ['Card'], columns: ['命中'], cells: [[3]] }, 'Card'],
    ['issues', 'issues', [{ message: '组件缺失' }], '组件缺失'],
    ['json', 'tree', { nested: { value: 1 } }, 'nested'],
    ['text', undefined, '纯文本结果', '纯文本结果'],
    ['code', 'code', '["a", "CardHeader"]', 'CardHeader'],
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
});
