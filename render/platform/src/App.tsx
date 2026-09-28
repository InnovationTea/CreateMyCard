"use client";
import { Component, useMemo, useState, type ReactNode } from "react";
import { defaultRegistry, renderTree } from "@genui-sdk/renderer";
import { compileMiniDsl } from "@/lib/mini-renderer";
import { EXAMPLE_DSL } from "./example-dsl";
import fusionExamples from "../fixtures/fusion-examples.json";

class PreviewBoundary extends Component<{ children: ReactNode }, { error: string }> {
  state = { error: "" };
  static getDerivedStateFromError(error: Error) { return { error: error.message }; }
  render() { return this.state.error ? <p className="error" role="alert">渲染失败：{this.state.error}</p> : this.props.children; }
}
export function App() {
  const [draft, setDraft] = useState(EXAMPLE_DSL);
  const [source, setSource] = useState(EXAMPLE_DSL);
  const [width, setWidth] = useState(160);
  const [height, setHeight] = useState(160);
  const [event, setEvent] = useState("");
  const [revision, setRevision] = useState(0);
  const [tab, setTab] = useState<"preview" | "a2ui">("preview");
  const [example, setExample] = useState("original");
  const result = useMemo(() => {
    try { return { value: compileMiniDsl(source, { size: width >= 250 ? "2x4" : "2x2" }), error: "" }; }
    catch (e) { return { value: null, error: e instanceof Error ? e.message : String(e) }; }
  }, [source, width]);
  function apply() { setSource(draft); setEvent(""); setRevision(r => r + 1); }
  function loadExample(value: string) {
    const selected = fusionExamples.examples[Number(value)];
    const dsl = value === "original" ? EXAMPLE_DSL : selected.source;
    setExample(value); setDraft(dsl); setSource(dsl); setEvent(""); setRevision(r => r + 1);
    setWidth(value === "original" ? 160 : selected.width);
    setHeight(value === "original" ? 160 : selected.height);
  }
  return <main className="renderer-app">
    <header className="app-header">
      <div><span className="brand-mark">[ ]</span><h1>DSL 渲染器</h1><span className="header-description">粘贴协议，即刻预览</span></div>
      <span className="local-badge"><i />本地渲染 · 无需 API Key</span>
    </header>
    <div className="workspace">
      <section className="editor-panel" aria-label="DSL 编辑器">
        <div className="panel-heading"><div><h2>极简 DSL</h2><p>组件元组与数据元组，每条一行。</p></div>
          <button onClick={() => loadExample(example)}>重载示例</button>
        </div>
        <label className="example-picker">示例<select aria-label="示例选择" value={example} onChange={e => loadExample(e.target.value)}>
          <option value="original">发布会倒计时 · 原始示例</option>
          {(["2x2", "2x4"] as const).map(size => <optgroup key={size} label={`${size} · ${size === "2x2" ? "150 × 150" : "300 × 150"}`}>
            {fusionExamples.examples.map((e, index) => e.size === size && <option key={index} value={index}>{e.name}</option>)}
          </optgroup>)}
        </select></label>
        {example !== "original" && fusionExamples.examples[Number(example)]?.note && <p className="example-note">{fusionExamples.examples[Number(example)].note}</p>}
        <textarea aria-label="极简 DSL 输入" spellCheck={false} value={draft} onChange={e => setDraft(e.target.value)}
          onKeyDown={e => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); apply(); } }} />
        <footer className="editor-footer"><span>{draft.split("\n").length} 行 · Ctrl / ⌘ + Enter 渲染</span><button className="primary" onClick={apply}>渲染预览 ↗</button></footer>
      </section>
      <section className="preview-panel" aria-label="渲染结果">
        <div className="preview-toolbar">
          <div className="tabs" role="tablist" aria-label="结果视图">
            <button role="tab" aria-selected={tab === "preview"} onClick={() => setTab("preview")}>预览</button>
            <button role="tab" aria-selected={tab === "a2ui"} onClick={() => setTab("a2ui")}>A2UI</button>
          </div>
          <div className="dimensions"><label>宽<input aria-label="预览宽度" type="number" min={80} max={1200} value={width} onChange={e => setWidth(Math.max(80, Math.min(1200, Number(e.target.value) || 80)))} /></label><span>×</span><label>高<input aria-label="预览高度" type="number" min={80} max={1200} value={height} onChange={e => setHeight(Math.max(80, Math.min(1200, Number(e.target.value) || 80)))} /></label></div>
        </div>
        {result.error ? <div className="empty-state error" role="alert">{result.error}</div> : result.value && <>
          {tab === "preview" ? <div className="preview-stage"><div className="preview-group">
            <div className="card-viewport" style={{ width, height }} data-testid="card-preview">
              <PreviewBoundary key={source + revision}>
                {renderTree(result.value.graph, defaultRegistry, { formId: null, onDataModelUserEdit: () => setRevision(r => r + 1), interactionHost: {
                  functionCall: action => { setEvent(JSON.stringify(action, null, 2)); },
                  submitForm: action => { setEvent(JSON.stringify(action, null, 2)); },
                } })}
              </PreviewBoundary>
            </div><span className="canvas-caption">{width} × {height} px</span>
          </div></div> : <pre className="a2ui-output" aria-label="A2UI 输出">{result.value.jsonl}</pre>}
          <div className="preview-status" role="status"><span className="status-dot" />已渲染 {result.value.count} 个组件{draft !== source && <span> · 输入已修改，点击渲染更新</span>}</div>
          {result.value.warnings.length > 0 && <div className="warnings">{result.value.warnings.map(w => <p key={w}>{w}</p>)}</div>}
        </>}
        {event && <div className="event-panel"><div><strong>点击事件</strong><button onClick={() => setEvent("")}>清除</button></div><pre>{event}</pre><p>仅展示解析后的事件参数，不执行外部跳转。</p></div>}
      </section>
    </div>
  </main>;
}
