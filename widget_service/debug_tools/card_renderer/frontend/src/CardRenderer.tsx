import React, { useEffect, useMemo, useState } from 'react';
import { CardPreview } from './render';
import { CardSize, ComponentNode, parseInput, RendererDocument } from './parser';
import { SAMPLE_COMPACT } from './fixtures';
import './styles.css';

export interface CardRendererProps {
  /** JSONL/JSON/compact DSL source supplied by the host; manual edits remain local. */
  initialValue?: string;
  /** Base URL used for relative image resources. Defaults to same-origin /resources/. */
  assetBaseUrl?: string;
  /** Host-resolved card size, usually from the final CardSpec or request query. */
  cardSize?: CardSize;
  /** Called after a successful parse, allowing the platform to publish the artifact. */
  onArtifact?: (document: RendererDocument) => void;
  /** Receives resolved local actions; the renderer never performs external navigation. */
  onAction?: (action: unknown, component: ComponentNode) => void;
  /** Hides source editing controls while keeping automatic rendering and preview controls. */
  previewOnly?: boolean;
  /** Controlled preview zoom percentage. */
  zoom?: number;
  /** Called when the preview zoom changes. */
  onZoomChange?: (zoom: number) => void;
  className?: string;
}

const DEFAULT_SOURCE = SAMPLE_COMPACT;

function sourceValue(value: string | undefined): string {
  return typeof value === 'string' ? value : DEFAULT_SOURCE;
}

export function CardRenderer({ initialValue, assetBaseUrl = '/resources/', cardSize: hostCardSize = 'auto', onArtifact, onAction, previewOnly = false, zoom: controlledZoom, onZoomChange, className = '' }: CardRendererProps) {
  const [source, setSource] = useState(() => sourceValue(initialValue));
  const [cardSize, setCardSize] = useState<CardSize>(hostCardSize);
  const [internalZoom, setInternalZoom] = useState(220);
  const [autoRender, setAutoRender] = useState(true);
  const [document, setDocument] = useState<RendererDocument | null>(null);
  const [containerWidth, setContainerWidth] = useState(150);
  const [containerHeight, setContainerHeight] = useState(150);
  const [error, setError] = useState('');
  const [interaction, setInteraction] = useState('');
  const zoom = controlledZoom ?? internalZoom;

  const changeZoom = (nextZoom: number) => {
    if (controlledZoom === undefined) setInternalZoom(nextZoom);
    onZoomChange?.(nextZoom);
  };

  useEffect(() => {
    if (initialValue === undefined) return;
    setSource(initialValue);
    // A selected shared call may keep the same component identity while its
    // final frame arrives. Clear the previous preview so manual-render mode
    // cannot display an unrelated call's document.
    setDocument(null);
    setError('');
    setInteraction('');
  }, [initialValue]);

  useEffect(() => {
    setCardSize(hostCardSize);
  }, [hostCardSize]);

  const render = (nextSource = source) => {
    const text = nextSource.trim();
    if (!text) {
      setDocument(null);
      setError('');
      return;
    }
    try {
      const parsed = parseInput(text, { cardSize });
      setDocument(parsed);
      setContainerWidth(parsed.surface.width);
      setContainerHeight(parsed.surface.height);
      setError('');
      onArtifact?.(parsed);
    } catch (reason) {
      setDocument(null);
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  };

  useEffect(() => {
    if (!autoRender) return;
    const timer = window.setTimeout(() => render(), 250);
    return () => window.clearTimeout(timer);
  }, [source, cardSize, autoRender]);

  const status = useMemo(() => {
    if (error) return error;
    if (!document) return source.trim() ? '未渲染' : '请输入 JSONL 或 DSL';
    const warningText = document.warnings.length > 0
      ? `，${document.warnings.length} 条警告`
      : '';
    return `已渲染 ${document.components.size} 个组件，DataModel ${document.dataPathCount} 个路径${warningText}。`;
  }, [document, error, source]);

  const previewDocument = useMemo(() => document ? {
    ...document,
    surface: { width: containerWidth, height: containerHeight },
  } : null, [containerHeight, containerWidth, document]);

  return <section className={`card-renderer${previewOnly ? ' card-renderer--preview-only' : ''} ${className}`.trim()} aria-label="卡片生成结果渲染器">
    {!previewOnly && <div className="card-renderer__editor">
      <div className="card-renderer__toolbar">
        <button type="button" className="is-primary" onClick={() => render()}>渲染</button>
        <button type="button" onClick={() => { setSource(''); render(''); }}>清空</button>
        <label className="card-renderer__control">画布<select value={cardSize} onChange={(event) => setCardSize(event.target.value as CardSize)}><option value="auto">自动</option><option value="2x2">2×2 · 150×150</option><option value="2x4">2×4 · 300×150</option></select></label>
        <label className="card-renderer__check"><input type="checkbox" checked={autoRender} onChange={(event) => setAutoRender(event.target.checked)} />自动渲染</label>
      </div>
      <textarea value={source} onChange={(event) => setSource(event.target.value)} spellCheck={false} aria-label="DSL 输入" />
      <div className={`card-renderer__status${error ? ' is-error' : ''}`} role={error ? 'alert' : 'status'}>{status}</div>
    </div>}
    <div className="card-renderer__preview">
      <div className="card-renderer__preview-toolbar">
        <span>{previewDocument ? `${previewDocument.mode} · ${containerWidth} × ${containerHeight}` : '预览'}</span>
        <div className="card-renderer__preview-controls">
          <label>容器宽度<input type="number" min="1" step="1" value={containerWidth} disabled={!document} onChange={(event) => setContainerWidth(Math.max(1, Number(event.target.value)))} /></label>
          <label>容器高度<input type="number" min="1" step="1" value={containerHeight} disabled={!document} onChange={(event) => setContainerHeight(Math.max(1, Number(event.target.value)))} /></label>
          <label>缩放<input type="range" min="50" max="360" value={zoom} onChange={(event) => changeZoom(Number(event.target.value))} /><span>{zoom}%</span></label>
        </div>
      </div>
      <div className="card-renderer__stage"><div className="card-renderer__matte" style={{ transform: `scale(${zoom / 100})` }}>{previewDocument ? <CardPreview document={previewDocument} assetBaseUrl={assetBaseUrl} onAction={(action, component) => {
        setInteraction(JSON.stringify({ action, componentId: component.id }, null, 2));
        onAction?.(action, component);
      }} /> : <div className="card-renderer__empty">暂无卡片</div>}</div></div>
      {interaction && <div className="card-renderer__interaction" role="status"><div><strong>点击事件</strong><button type="button" onClick={() => setInteraction('')}>清除</button></div><pre>{interaction}</pre><p>仅展示解析后的事件参数，不执行外部跳转。</p></div>}
    </div>
  </section>;
}

export default CardRenderer;
