// @vitest-environment jsdom

import React from 'react';
import '@testing-library/jest-dom/vitest';
import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ExtendedText } from '../../runtime/components/src/extended/ExtendedText';
import { fitCompleteText } from '../../runtime/components/src/extended/complete-text';
import { parseInput } from '../src/parser';
import { CardPreview } from '../src/render';

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

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

describe('完整字符裁剪', () => {
  const measure = (text: string) => Array.from(new Intl.Segmenter(undefined, { granularity: 'grapheme' })
    .segment(text)).length * 10;

  it.each([
    ['未连接充电器', 56, '未连接充电'],
    ['168次/分钟', 60, '168次/分'],
    ['中文', 20, '中文'],
    ['中文', 9, ''],
    ['中文', 0, ''],
    ['A👨‍👩‍👧‍👦B', 20, 'A👨‍👩‍👧‍👦'],
    ['A👍🏽B', 20, 'A👍🏽'],
    ['Ae\u0301B', 20, 'Ae\u0301'],
  ])('内容 %s 在宽度 %s 下仅保留完整前缀', (text, width, expected) => {
    expect(fitCompleteText(String(text), Number(width), measure)).toBe(expected);
  });

  it('按真实混合字符宽度选择前缀，不切开最后一个汉字', () => {
    const widths: Record<string, number> = { '1': 5, '6': 6, '8': 7, '次': 12, '/': 4, '分': 12, '钟': 12 };
    const mixedMeasure = (text: string) => Array.from(text).reduce((width, char) => width + widths[char]!, 0);
    expect(fitCompleteText('168次/分钟', 56, mixedMeasure)).toBe('168次/分');
  });

  it('自然宽度的小数舍入不会误删本来放得下的最后一个字符', () => {
    vi.spyOn(HTMLElement.prototype, 'getClientRects').mockReturnValue([{}] as unknown as DOMRectList);
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      return { width: (this.textContent?.length ?? 0) * 10 + 0.00004 } as DOMRect;
    });
    render(<ExtendedText content="完整" width={20} maxLines={1} />);
    expect(screen.getByLabelText('完整')).toHaveTextContent('完整');
  });

  it('自然宽度文字在父容器变宽后恢复原文', () => {
    let available = 25;
    let resized = () => {};
    vi.spyOn(HTMLElement.prototype, 'getClientRects').mockReturnValue([{}] as unknown as DOMRectList);
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      return { width: (this.textContent?.length ?? 0) * 10 } as DOMRect;
    });
    const originalComputedStyle = window.getComputedStyle.bind(window);
    vi.spyOn(window, 'getComputedStyle').mockImplementation(element => {
      const result = originalComputedStyle(element);
      const naturalWidth = parseFloat((element as HTMLElement).style.width) || (element.textContent?.length ?? 0) * 10;
      Object.defineProperty(result, 'width', { value: `${Math.min(available, naturalWidth)}px` });
      return result;
    });
    vi.stubGlobal('ResizeObserver', class {
      constructor(callback: () => void) { resized = callback; }
      observe() {}
      disconnect() {}
    });
    render(<div><ExtendedText content="完整原文" maxLines={1} /></div>);
    expect(screen.getByLabelText('完整原文')).toHaveTextContent('完整');
    available = 50;
    act(() => resized());
    expect(screen.getByLabelText('完整原文')).toHaveTextContent('完整原文');
    expect(screen.getByLabelText('完整原文').style.width).toBe('');
  });

  it('右对齐保留前缀，并随宽度、绑定内容和字体加载重新计算', async () => {
    let available = 25;
    let glyphWidth = 10;
    let resized = () => {};
    vi.spyOn(HTMLElement.prototype, 'getClientRects').mockReturnValue([{}] as unknown as DOMRectList);
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      return { width: this.tagName === 'SPAN' ? measure(this.textContent ?? '') * glyphWidth / 10 : available } as DOMRect;
    });
    const originalComputedStyle = window.getComputedStyle.bind(window);
    vi.spyOn(window, 'getComputedStyle').mockImplementation(element => {
      const result = originalComputedStyle(element);
      Object.defineProperty(result, 'width', { value: `${available}px` });
      return result;
    });
    vi.stubGlobal('ResizeObserver', class {
      constructor(callback: () => void) { resized = callback; }
      observe() {}
      disconnect() {}
    });
    const fonts = new EventTarget();
    Object.defineProperty(fonts, 'ready', { value: Promise.resolve(fonts) });
    Object.defineProperty(document, 'fonts', { configurable: true, value: fonts });
    try {
      const view = render(<ExtendedText content="未连接充电器" width={25} maxLines={1} textAlign="end" />);
      await act(async () => { await Promise.resolve(); });
      expect(screen.getByLabelText('未连接充电器')).toHaveTextContent('未连');
      expect(screen.getByLabelText('未连接充电器')).toHaveStyle({ 'text-align': 'end' });
      available = 60;
      act(() => resized());
      expect(screen.getByLabelText('未连接充电器')).toHaveTextContent('未连接充电器');
      view.rerender(<ExtendedText content="新的绑定内容" width={60} maxLines={1} />);
      await act(async () => { await Promise.resolve(); });
      expect(screen.getByLabelText('新的绑定内容')).toHaveTextContent('新的绑定内容');
      glyphWidth = 20;
      act(() => fonts.dispatchEvent(new Event('loadingdone')));
      expect(screen.getByLabelText('新的绑定内容')).toHaveTextContent('新的绑');
      expect(document.querySelector('span')).toBeNull();
    } finally {
      delete (document as unknown as { fonts?: FontFaceSet }).fonts;
    }
  });
});
