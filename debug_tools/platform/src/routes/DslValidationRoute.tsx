import { Component, type ReactNode, useEffect, useRef, useState } from 'react';
import { CardRenderer } from '@widget-debug/card-renderer';
import './dslValidation.css';
import example from '../../../card_renderer/validation-example.json';

interface Diagnostic {
  message: string;
  legacyMessage?: string;
  code?: string;
  validationClass?: string;
  category?: string;
  sourceLine?: number;
  sourceColumn?: number;
  componentId?: string;
  propertyPath?: string;
  fixHint?: string;
  expected?: unknown;
  actual?: unknown;
  sourceKind?: string;
  stage?: string;
  severity?: string;
}

interface ValidationResult {
  valid: boolean;
  complete: boolean;
  validationScope?: 'layout' | 'artifact';
  status: string;
  stages: { name: string; status: string; reason?: string }[];
  sources: Record<string, string>;
  inputNotes: Diagnostic[];
  size: '2x2' | '2x4';
  diagnostics: Diagnostic[];
  warnings: string[];
  genui: string | null;
  previewError: string | null;
}

const SOURCE_LABELS: Record<string, string> = {
  original: '原始 DSL', layoutInput: '去色后校验输入', processed: '处理后 DSL', genui: '标准 A2UI',
  cardspec: '卡片定义', context: '回放上下文',
};
const STAGE_LABELS: Record<string, string> = {
  passed: '通过', failed: '失败', skipped: '跳过', blocked: '缺少上下文',
};

class PreviewBoundary extends Component<{ children: ReactNode }, { error: string | null }> {
  state: { error: string | null } = { error: null };

  static getDerivedStateFromError(error: unknown) {
    return { error: error instanceof Error ? error.message : String(error) };
  }

  render() {
    return this.state.error !== null
      ? <p role="alert" className="dsl-validation__error">预览绘制失败：{this.state.error}。请根据校验结果修改源码。</p>
      : this.props.children;
  }
}

function readContext(text: string): Record<string, unknown> | null {
  if (!text.trim()) return null;
  const value: unknown = JSON.parse(text);
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('校验上下文必须是 JSON 对象。');
  }
  return value as Record<string, unknown>;
}

export function DslValidationRoute() {
  const [source, setSource] = useState('');
  const [context, setContext] = useState('');
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [selectedLine, setSelectedLine] = useState<number | null>(null);
  const [showPreview, setShowPreview] = useState(true);
  const [zoom, setZoom] = useState(100);
  const [sourceKind, setSourceKind] = useState('original');
  const [location, setLocation] = useState<{ kind: string; line: number } | null>(null);
  const requestRef = useRef<AbortController | null>(null);
  const editorRef = useRef<HTMLTextAreaElement>(null);
  const linesRef = useRef<HTMLDivElement>(null);
  const visibleSource = sourceKind === 'original' ? source : result?.sources[sourceKind] ?? '';
  const lines = visibleSource.split('\n');

  useEffect(() => {
    if (!location || sourceKind !== location.kind) return;
    const editor = editorRef.current;
    const sourceLines = visibleSource.split('\n');
    const line = location.line;
    if (!editor || line < 1 || line > sourceLines.length) return;
    let start = 0;
    for (let index = 0; index < line - 1; index += 1) start += sourceLines[index].length + 1;
    editor.focus();
    editor.setSelectionRange(start, start + sourceLines[line - 1].length);
    editor.scrollTop = Math.max(0, (line - 3) * 22);
    if (linesRef.current) linesRef.current.scrollTop = editor.scrollTop;
    setSelectedLine(line);
  }, [location, sourceKind, visibleSource]);

  useEffect(() => () => requestRef.current?.abort(), []);

  const invalidate = () => {
    requestRef.current?.abort();
    requestRef.current = null;
    setBusy(false);
    setResult(null);
    setError('');
    setSelectedLine(null);
    setSourceKind('original');
    setLocation(null);
  };

  const validate = async () => {
    invalidate();
    const controller = new AbortController();
    requestRef.current = controller;
    setBusy(true);
    try {
      const response = await fetch('/debug/renderer/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source, context: readContext(context),
        }),
        signal: controller.signal,
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        const detail = body?.detail;
        throw new Error(`校验请求失败（${response.status}）：${
          typeof detail === 'string' ? detail : JSON.stringify(detail ?? '请确认 Python 调试后端已启动')
        }`);
      }
      const nextResult = await response.json() as ValidationResult;
      if (requestRef.current === controller) setResult(nextResult);
    } catch (reason) {
      if (requestRef.current === controller) {
        setError(reason instanceof Error ? reason.message : String(reason));
      }
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null;
        setBusy(false);
      }
    }
  };

  const locate = (kind: string, line: number) => {
    setSourceKind(kind);
    setLocation({ kind, line });
  };

  return <section className="dsl-validation" aria-label="DSL 校验工作区">
    <header className="dsl-validation__heading">
      <div><h1>线上校验回放</h1><p>粘贴 Compact DSL 和当次执行上下文，复现单轮线上校验。模型来源回放到布局评估，主题与最终交付校验单独标明。</p></div>
      <button type="button" onClick={() => {
        invalidate(); setSource(example.source); setContext(JSON.stringify(example.context, null, 2));
      }}>载入完整示例</button>
    </header>
    <div className="dsl-validation__workspace">
      <section className="dsl-validation__source" aria-label="DSL 源码">
        <div className="dsl-validation__toolbar">
          <button className="dsl-validation__primary" type="button" disabled={busy || !source.trim()}
            onClick={() => { void validate(); }}>{busy ? '正在校验…' : '校验并预览'}</button>
          <button type="button" onClick={() => { invalidate(); setSource(''); }}>清空</button>
          <label>查看源码<select value={sourceKind} onChange={(event) => {
            setSourceKind(event.target.value); setSelectedLine(null); setLocation(null);
          }}>{Object.entries(SOURCE_LABELS).map(([kind, label]) =>
            <option key={kind} value={kind} disabled={kind !== 'original' && !result?.sources[kind]}>{label}</option>
          )}</select></label>
        </div>
        <div className="dsl-validation__editor">
          <div className="dsl-validation__lines" ref={linesRef} aria-hidden="true">
            {lines.map((_, index) => <div key={index} className={selectedLine === index + 1 ? 'is-selected' : ''}>
              {index + 1}
            </div>)}
          </div>
          <textarea aria-label={sourceKind === 'original' ? '待校验 DSL' : '源码查看'}
            ref={editorRef} value={visibleSource} readOnly={sourceKind !== 'original'} wrap="off" spellCheck={false}
            placeholder="在这里粘贴 DSL，每行一条 JSON 数组…"
            onChange={(event) => { invalidate(); setSource(event.target.value); }}
            onScroll={(event) => { if (linesRef.current) linesRef.current.scrollTop = event.currentTarget.scrollTop; }}
            onKeyDown={(event) => {
              if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && source.trim() && !busy) {
                event.preventDefault(); void validate();
              }
            }} />
        </div>
        <div className="dsl-validation__source-status">{lines.length} 行 · Ctrl / ⌘ + Enter 校验
          {selectedLine !== null && ` · 已选中第 ${selectedLine} 行`}</div>
        <details className="dsl-validation__context" open>
          <summary>必填：当次执行上下文</summary>
          <p>提供当前候选产物、生成计划、来源、校验及修复阶段配置与素材映射；编辑使用本轮最终绑定，无需旧产物。可先载入完整示例查看格式。</p>
          <textarea aria-label="校验上下文" value={context} spellCheck={false}
            placeholder={'{"artifact": {...}, "sourceKind": "model", "compactPlan": {...}, ...}'}
            onChange={(event) => { invalidate(); setContext(event.target.value); }} />
        </details>
      </section>
      <section className="dsl-validation__results" aria-label="校验结果">
        <div className="dsl-validation__report">
          <h2>检查结果</h2>
          {error && <p role="alert" className="dsl-validation__error">{error}</p>}
          {!result && !error && <p role="status">{busy ? '正在调用本地校验器…' : '粘贴 DSL 后点击“校验并预览”。修改输入后需重新校验。'}</p>}
          {result && <>
            <p role="status" className={result.valid && result.complete ? 'dsl-validation__success' : 'dsl-validation__error'}>
              {result.valid && result.complete
                ? result.validationScope === 'layout' ? '布局校验通过，最终交付尚未校验' : '产物校验通过'
                : result.status === 'context_required' ? '上下文不完整，无法回放'
                  : result.status === 'skipped' ? '产物校验已跳过，未完成完整校验' : '本轮校验未通过'}
            </p>
            <ol className="dsl-validation__stages">{result.stages.map((stage, index) => <li key={index}>
              <strong>{STAGE_LABELS[stage.status] ?? stage.status}</strong> · {stage.name}
              {stage.reason && <p>{stage.reason}</p>}
            </li>)}</ol>
            {result.warnings.map((warning, index) => <p className="dsl-validation__notice" key={index}>{warning}</p>)}
            <ol className="dsl-validation__issues">
              {[...result.diagnostics, ...result.inputNotes].map((item, index) => {
                const kind = item.sourceKind ?? 'original';
                const diagnosticLines = (result.sources[kind] ?? '').split('\n');
                const canLocate = item.sourceLine && item.sourceLine <= diagnosticLines.length;
                return <li key={index}>
                <div className="dsl-validation__issue-heading">
                  <strong>{item.code ?? 'DSL 解析 / 转换问题'}</strong>
                  {canLocate
                    ? <button type="button" onClick={() => locate(kind, item.sourceLine!)}>{SOURCE_LABELS[kind]} · 第 {item.sourceLine} 行
                      {item.sourceColumn ? ` · 第 ${item.sourceColumn} 列` : ''}</button>
                    : <span>{SOURCE_LABELS[kind]} · 无可靠行号</span>}
                </div>
                <p>{item.stage} · {item.severity === 'warning' ? '提示（不阻断）' : '错误'}</p>
                <p>{item.message}</p>
                {item.legacyMessage && item.legacyMessage !== item.message &&
                  <p>校验器详情：{item.legacyMessage}</p>}
                {(item.componentId || item.propertyPath) && <p>组件：{item.componentId ?? '—'} · 属性：{item.propertyPath ?? '—'}</p>}
                {canLocate && <pre>{diagnosticLines[item.sourceLine! - 1]}</pre>}
                {item.fixHint && <p className="dsl-validation__hint">修改建议：{item.fixHint}</p>}
                {(item.actual !== undefined || item.expected !== undefined) && <details>
                  <summary>查看实际值与约束</summary><pre>{JSON.stringify({ actual: item.actual, expected: item.expected }, null, 2)}</pre>
                </details>}
              </li>; })}
            </ol>
          </>}
        </div>
        <div className="dsl-validation__preview-heading"><h2>渲染预览</h2>
          <label><input type="checkbox" checked={showPreview} onChange={(event) => setShowPreview(event.target.checked)} />显示预览</label>
        </div>
        {showPreview && <div className="dsl-validation__preview">
          {result?.genui ? <>
            {result.validationScope === 'layout' &&
              <p className="dsl-validation__notice">布局预览：尚未选择主题或填色，不代表最终交付效果。</p>}
            {!result.valid && <p className="dsl-validation__notice">校验未通过。预览仅供排查，不代表可发布。</p>}
            <PreviewBoundary key={result.genui}>
              <CardRenderer previewOnly initialValue={result.genui} cardSize={result.size}
                zoom={zoom} onZoomChange={setZoom} />
            </PreviewBoundary>
          </> : <p>{result?.previewError ? `无法渲染：${result.previewError}` : '校验后在这里展示可转换的卡片。'}</p>}
        </div>}
      </section>
    </div>
  </section>;
}
