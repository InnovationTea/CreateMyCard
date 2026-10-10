import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QualityEvaluationRoute } from './QualityEvaluationRoute';

describe('QualityEvaluationRoute', () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it('renders current Markdown tables and code safely, labeling historical policy separately', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true, json: async () => ({
      markdown: '# 方案正文\n\n## 权重\n| 维度 | 权重 |\n| --- | --- |\n| 功能 | **50%** |\n\n1. 读取 `policy`\n2. 计算评分\n\n- 检查边界\n\n```json\n{"weight": 0.5}\n```\n<img src=x onerror=alert(1)>\n<script>alert(1)</script>',
      policy: { version: 'v2' }, policySha256: 'sha-current',
    }) } as Response);
    const { container } = render(<MemoryRouter><QualityEvaluationRoute /></MemoryRouter>);
    expect(await screen.findByRole('heading', { name: '方案正文' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '评估方案（当前版本）' })).toBeInTheDocument();
    expect(screen.getByText(/历史结果以对应评分看板的 policy 快照为准/)).toBeInTheDocument();
    expect(screen.getByText('sha-current')).toBeInTheDocument();
    expect(within(screen.getByRole('table')).getByRole('cell', { name: '50%' })).toBeInTheDocument();
    expect(container.querySelector('strong')).toHaveTextContent('50%');
    expect(screen.getByText('{"weight": 0.5}').tagName).toBe('CODE');
    expect(container.querySelector('script, img')).toBeNull();
    expect(screen.getByText('<script>alert(1)</script>')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith('/debug/batch/quality/evaluation', undefined);
  });

  it('shows a document load failure without inventing evaluation parameters', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: false, status: 500, json: async () => ({ detail: '方案读取失败' }) } as Response);
    render(<MemoryRouter><QualityEvaluationRoute /></MemoryRouter>);
    expect(await screen.findByRole('alert')).toHaveTextContent('方案读取失败');
    expect(screen.queryByText(/当前方案 SHA-256/)).not.toBeInTheDocument();
  });
});
