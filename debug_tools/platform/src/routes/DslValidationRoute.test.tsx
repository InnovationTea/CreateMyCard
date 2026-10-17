import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { DslValidationRoute } from './DslValidationRoute';

vi.mock('@widget-debug/card-renderer', () => ({
  CardRenderer: ({ initialValue }: { initialValue: string }) => {
    if (initialValue === 'crashing preview') throw new Error('非法表达式');
    return <div data-testid="preview">{initialValue}</div>;
  },
}));

const SOURCE = '["root","Column",{},["text"]]\n["text","Text",{"content":"bad"}]';
const RESULT = {
  valid: false, complete: true, status: 'failed', stages: [], inputNotes: [], sources: { original: SOURCE, genui: 'first\nsecond' }, size: '2x2', genui: 'converted preview', previewError: null, warnings: ['局部检查'],
  diagnostics: [{ code: 'TEST', message: '内容有误', sourceLine: 2, componentId: 'text', propertyPath: '/content', fixHint: '修改内容' }],
};
function response(body: unknown) { return { ok: true, json: async () => body }; }
function enterSource() {
  render(<DslValidationRoute />);
  fireEvent.change(screen.getByRole('textbox', { name: '待校验 DSL' }), { target: { value: SOURCE } });
}

describe('DSL validation workbench', () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('isolates renderer crashes and recovers after editing and checking again', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(response({ ...RESULT, genui: 'crashing preview' }))
      .mockResolvedValueOnce(response(RESULT)));
    enterSource();
    fireEvent.click(screen.getByRole('button', { name: '校验并预览' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('预览绘制失败：非法表达式');
    expect(screen.getByText('内容有误')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '原始 DSL · 第 2 行' }));
    expect(screen.getByLabelText('待校验 DSL')).toHaveFocus();
    fireEvent.change(screen.getByLabelText('待校验 DSL'), { target: { value: SOURCE + '\n' } });
    fireEvent.click(screen.getByRole('button', { name: '校验并预览' }));
    expect(await screen.findByTestId('preview')).toHaveTextContent('converted preview');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('validates exact source, displays errors and preview, and selects the source line', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(RESULT));
    vi.stubGlobal('fetch', fetchMock);
    enterSource();
    fireEvent.click(screen.getByRole('button', { name: '校验并预览' }));
    expect(await screen.findByText('内容有误')).toBeInTheDocument();
    expect(screen.getByText('修改建议：修改内容')).toBeInTheDocument();
    expect(screen.getByTestId('preview')).toHaveTextContent('converted preview');
    expect(screen.getByText('校验未通过。预览仅供排查，不代表可发布。')).toBeInTheDocument();
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.source).toBe(SOURCE);
    fireEvent.click(screen.getByRole('button', { name: '原始 DSL · 第 2 行' }));
    const editor = screen.getByRole('textbox', { name: '待校验 DSL' }) as HTMLTextAreaElement;
    expect(editor).toHaveFocus();
    expect(editor.value.slice(editor.selectionStart, editor.selectionEnd)).toBe(SOURCE.split('\n')[1]);
    fireEvent.change(editor, { target: { value: 'new source' } });
    expect(screen.queryByText('内容有误')).not.toBeInTheDocument();
    expect(screen.queryByTestId('preview')).not.toBeInTheDocument();
  });

  it('aborts pending checks and ignores late responses after an edit', async () => {
    let finish!: (value: unknown) => void;
    const fetchMock = vi.fn().mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    vi.stubGlobal('fetch', fetchMock);
    enterSource();
    fireEvent.click(screen.getByRole('button', { name: '校验并预览' }));
    fireEvent.change(screen.getByRole('textbox', { name: '待校验 DSL' }), { target: { value: 'changed' } });
    expect(fetchMock.mock.calls[0][1].signal.aborted).toBe(true);
    finish(response(RESULT));
    await waitFor(() => expect(screen.getByRole('button', { name: '校验并预览' })).toBeEnabled());
    expect(screen.queryByText('内容有误')).not.toBeInTheDocument();
  });

  it('submits the exact context without size or version overrides', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ ...RESULT, valid: true, status: 'passed', diagnostics: [] }));
    vi.stubGlobal('fetch', fetchMock);
    enterSource();
    const context = { artifact: { taskSpec: { appVersion: '11.7.7.331' } }, enableArtifactValidation: true };
    fireEvent.change(screen.getByLabelText('校验上下文'), { target: { value: JSON.stringify(context) } });
    fireEvent.keyDown(screen.getByLabelText('待校验 DSL'), { key: 'Enter', ctrlKey: true });
    expect(await screen.findByText('产物校验通过')).toBeInTheDocument();
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ source: SOURCE, context });
  });

  it('distinguishes a layout pass from final delivery validation', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({
      ...RESULT, valid: true, status: 'passed', validationScope: 'layout', diagnostics: [],
    })));
    enterSource();
    fireEvent.click(screen.getByRole('button', { name: '校验并预览' }));
    expect(await screen.findByText('布局校验通过，最终交付尚未校验')).toBeInTheDocument();
    expect(screen.getByText('布局预览：尚未选择主题或填色，不代表最终交付效果。')).toBeInTheDocument();
    expect(screen.queryByText('产物校验通过')).not.toBeInTheDocument();
  });

  it.each([
    ['genui', '标准 A2UI'],
    ['layoutInput', '去色后校验输入'],
  ])('switches to the actual %s source for diagnostics', async (kind, label) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ ...RESULT,
      sources: { ...RESULT.sources, [kind]: 'first\nsecond' },
      diagnostics: [{ code: 'TEST', message: '转换后的组件有误', sourceKind: kind, sourceLine: 2 }],
    })));
    enterSource();
    fireEvent.click(screen.getByRole('button', { name: '校验并预览' }));
    fireEvent.click(await screen.findByRole('button', { name: `${label} · 第 2 行` }));
    const editor = screen.getByLabelText('源码查看') as HTMLTextAreaElement;
    expect(editor.readOnly).toBe(true);
    expect(editor.value.slice(editor.selectionStart, editor.selectionEnd)).toBe('second');
    fireEvent.change(screen.getByLabelText('查看源码'), { target: { value: 'original' } });
    expect(screen.getByLabelText('待校验 DSL')).toHaveValue(SOURCE);
  });

  it.each(['skipped', 'context_required'])('never calls %s a complete pass', async (status) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ ...RESULT,
      valid: false, complete: false, status, genui: null,
    })));
    enterSource();
    fireEvent.click(screen.getByRole('button', { name: '校验并预览' }));
    expect(await screen.findByText(status === 'skipped' ? '产物校验已跳过，未完成完整校验' : '上下文不完整，无法回放')).toBeInTheDocument();
    expect(screen.queryByText('产物校验通过')).not.toBeInTheDocument();
  });

  it('rejects invalid context locally', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    enterSource();
    fireEvent.change(screen.getByLabelText('校验上下文'), { target: { value: '[]' } });
    fireEvent.click(screen.getByRole('button', { name: '校验并预览' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('校验上下文必须是 JSON 对象');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('shows conversion failures and unlocated errors without inventing a preview', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({
      ...RESULT, genui: null, previewError: '解析失败', diagnostics: [{ message: '无法解析' }],
    })));
    enterSource();
    fireEvent.click(screen.getByRole('button', { name: '校验并预览' }));
    expect(await screen.findByText('原始 DSL · 无可靠行号')).toBeInTheDocument();
    expect(screen.getByText('无法渲染：解析失败')).toBeInTheDocument();
    expect(screen.queryByTestId('preview')).not.toBeInTheDocument();
  });

  it('reports backend failures and allows retry', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503, json: async () => ({ detail: '服务不可用' }) }));
    enterSource();
    fireEvent.click(screen.getByRole('button', { name: '校验并预览' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('503');
    expect(screen.getByRole('button', { name: '校验并预览' })).toBeEnabled();
  });

  it('disables empty input and loads and clears the example', () => {
    render(<DslValidationRoute />);
    expect(screen.getByRole('button', { name: '校验并预览' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '载入完整示例' }));
    expect((screen.getByLabelText('待校验 DSL') as HTMLTextAreaElement).value).toContain('你好，卡片');
    fireEvent.click(screen.getByRole('button', { name: '清空' }));
    expect(screen.getByLabelText('待校验 DSL')).toHaveValue('');
  });
});
