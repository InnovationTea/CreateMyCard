// @vitest-environment jsdom

import React from 'react';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { parseInput } from '../src/parser';
import { CardPreview } from '../src/render';

afterEach(cleanup);

async function renderText(content: string, styles: Record<string, unknown>) {
  const document = await parseInput([
    { version: 'v0.9', createSurface: { surfaceId: 'text-preview', width: 150, height: 150 } },
    { version: 'v0.9', updateComponents: {
      surfaceId: 'text-preview', root: 'root', components: [
        { id: 'root', component: 'Row', children: ['value'], styles: { width: 126 } },
        { id: 'value', component: 'Text', content, styles },
      ],
    } },
  ].map(row => JSON.stringify(row)).join('\n'));
  render(<CardPreview document={document} />);
  return screen.getByText(content);
}

describe('Web 文字行数与裁剪', () => {
  it.each([
    { content: '未连接充电器', width: 56, height: 16, fontSize: 10 },
    { content: '168次/分钟', width: 56, height: 18, fontSize: 12 },
    { content: '更新于 2026-08-06 09:00', width: 126, height: 18, fontSize: 12 },
  ])('单行长字段 $content 保留布局高度并禁止换行', async ({ content, width, height, fontSize }) => {
    const text = await renderText(content, { width, height, fontSize, maxLines: 1, textOverflow: 'clip' });

    expect(text).toHaveStyle({
      width: `${width}px`, height: `${height}px`, 'font-size': `${fontSize}px`,
      'white-space': 'nowrap', overflow: 'hidden', 'text-overflow': 'clip',
    });
    expect(text.style.display).not.toBe('-webkit-box');
    expect(text).toHaveTextContent(content);
  });

  it.each([
    { mode: 'ellipsis', cssOverflow: 'ellipsis' },
    { mode: 'none', cssOverflow: 'clip' },
  ])('单行仍保留 $mode 的超宽处理语义', async ({ mode, cssOverflow }) => {
    const text = await renderText('很长的单行内容', { width: 56, height: 18, maxLines: 1, textOverflow: mode });

    expect(text).toHaveStyle({ 'white-space': 'nowrap', overflow: 'hidden', 'text-overflow': cssOverflow });
    expect(text.style.display).not.toBe('-webkit-box');
  });

  it.each([2, 3])('maxLines=%s 保留多行截断', async maxLines => {
    const text = await renderText('允许多行显示的文字内容', { width: 56, height: 40, maxLines });

    expect(text).toHaveStyle({ display: '-webkit-box', 'white-space': 'normal', overflow: 'hidden', height: '40px' });
    expect(text.style.getPropertyValue('-webkit-line-clamp')).toBe(String(maxLines));
  });

  it('未声明 maxLines 时保留自然换行', async () => {
    const text = await renderText('可以自然换行的内容', { width: 56 });

    expect(text.style.whiteSpace).not.toBe('nowrap');
    expect(text.style.display).not.toBe('-webkit-box');
    expect(text.style.overflowWrap).toBe('anywhere');
  });
});
