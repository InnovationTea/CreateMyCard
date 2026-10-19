import { afterEach, describe, expect, it } from 'vitest';
import template from '../../postprocess_plugins/gallery/templates/report.html?raw';

function setup() {
  const mean = (value: number) => ({ sum: value, count: 1, mean: value });
  const cases = [
    { id: 'Q001', title: '天气', query: '<script>window.injected=1</script>', size: '2x4', status: 'success',
      captureStatus: 'success', image: 'data:image/png;base64,aGVsbG8=', warnings: [],
      compact: 'Compact', a2ui: 'A2UI', analysis: {}, statistics: {
        requestCount: 1, effectiveCount: 2, paddedCount: 1,
        pass1: { hits: 1, count: 1 }, pass2: { hits: 1, count: 1 },
        elapsedMs: mean(100), interfaceRetries: mean(0),
        usage: { assets: { count: 1, used: 1, items: [{ id: 'asset.sun', count: 1 }] } },
      } },
    { id: 'Q002', title: '失败', query: '无截图', size: '2x2', status: 'failed',
      captureStatus: 'failed', image: '', error: '渲染失败', warnings: ['警告'],
      compact: '', a2ui: '', analysis: {}, statistics: {
        requestCount: 1, effectiveCount: 1, paddedCount: 0,
        pass1: { hits: 0, count: 1 }, pass2: { hits: 0, count: 1 },
        elapsedMs: mean(300), interfaceRetries: mean(1),
        usage: { assets: { count: 1, used: 0, items: [] } },
      } },
  ];
  const payload = JSON.stringify({ runId: 'run', cases }).replaceAll('<', '\\u003c');
  const html = template.replaceAll('{{TITLE}}', '画廊').replaceAll('{{CREATED}}', 'date').replace('{{DATA}}', payload);
  document.documentElement.innerHTML = html;
  const scripts = document.querySelectorAll('script');
  const script = scripts.item(scripts.length - 1);
  // 执行受控模板中的脚本；用户文本只进入 JSON 数据。
  new Function('document', script.textContent ?? '')(document);
}

function select(id: string, value: string) {
  const control = document.getElementById(id) as HTMLSelectElement;
  control.value = value;
  control.dispatchEvent(new Event('change'));
}

afterEach(() => { document.documentElement.innerHTML = ''; });

describe('offline gallery document', () => {
  it('renders escaped products, status placeholders, and known metric denominators', () => {
    setup();
    expect(document.querySelectorAll('.case')).toHaveLength(2);
    expect(document.querySelector('.query')?.textContent).toContain('<script>');
    expect(document.querySelector('.case script')).toBeNull();
    expect(document.getElementById('metrics')?.textContent).toContain('50.0%');
    expect(document.getElementById('coverage')?.textContent).toContain('实际请求 2 · 补齐 1');
    expect(document.querySelector('.render-error')?.textContent).toBe('渲染失败');
    expect(document.getElementById('analysis-details')?.textContent).toContain('asset.sun');
  });

  it('filters and recomputes metrics and handles empty results', () => {
    setup();
    select('size', '2x4');
    expect(document.querySelectorAll('.case')).toHaveLength(1);
    expect(document.getElementById('metrics')?.textContent).toContain('100.0%');
    select('capture', 'missing');
    expect(document.querySelector('.empty')?.textContent).toContain('没有符合');
    expect(document.getElementById('metrics')?.textContent).toContain('未知');
    document.getElementById('reset')?.click();
    expect(document.querySelectorAll('.case')).toHaveLength(2);
    const search = document.getElementById('search') as HTMLInputElement;
    search.value = '无截图'; search.dispatchEvent(new Event('input'));
    expect(document.querySelectorAll('.case')).toHaveLength(1);
    expect(document.querySelector('.case-id')?.textContent).toBe('Q002');
  });

  it('sorts, switches layout, and preserves selected columns and filters', () => {
    setup();
    select('sort', 'latency');
    expect(document.querySelector('.case-id')?.textContent).toBe('Q002');
    select('columns', '3');
    document.getElementById('layout')?.click();
    expect(document.getElementById('cases')?.classList.contains('compact')).toBe(true);
    expect(document.getElementById('cases')?.dataset.columns).toBe('3');
    expect(document.getElementById('layout')?.getAttribute('aria-pressed')).toBe('true');
    select('warning', 'yes');
    expect(document.querySelectorAll('.case')).toHaveLength(1);
    expect(document.querySelector('.case-id')?.textContent).toBe('Q002');
    document.getElementById('layout')?.click();
    expect(document.getElementById('cases')?.classList.contains('compact')).toBe(false);
    expect(document.getElementById('cases')?.dataset.columns).toBe('3');
  });
});
