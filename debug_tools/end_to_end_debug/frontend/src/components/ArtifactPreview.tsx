import React, { CSSProperties, useMemo } from 'react';

export interface ArtifactPreviewProps {
  artifact: Record<string, unknown> | null;
  activeKind: string;
  onKindChange: (kind: string) => void;
}

type ComponentNode = {
  id?: string;
  component?: string;
  children?: unknown;
  [key: string]: unknown;
};

const COMPONENT_KINDS = [
  'genui',
  'cardSpec',
  'taskSpec',
  'effectiveCapabilities',
  'removedCapabilities',
  'generationPlan',
  'meta',
  'designToken',
  'design_token',
];

function parseGenui(value: unknown): ComponentNode[] {
  if (typeof value !== 'string') {
    if (Array.isArray(value)) return value.filter(isNode);
    if (value && typeof value === 'object') {
      const object = value as Record<string, unknown>;
      if (Array.isArray(object.components)) return object.components.filter(isNode);
      if (Array.isArray(object.nodes)) return object.nodes.filter(isNode);
      return isNode(object) ? [object] : [];
    }
    return [];
  }
  const text = value.trim();
  if (!text) return [];
  try {
    const parsed: unknown = JSON.parse(text);
    return parseGenui(parsed);
  } catch {
    const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    const nodes: ComponentNode[] = [];
    for (const line of lines) {
      try {
        const parsed: unknown = JSON.parse(line);
        if (isNode(parsed)) nodes.push(parsed);
      } catch {
        // Keep malformed lines out of the visual preview; source remains available below.
      }
    }
    return nodes;
  }
}

function isNode(value: unknown): value is ComponentNode {
  return Boolean(value && typeof value === 'object' && 'component' in value);
}

function valueToText(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return JSON.stringify(value) ?? '';
}

function childNodes(node: ComponentNode, byId: Map<string, ComponentNode>): ComponentNode[] {
  const children = node.children;
  if (!Array.isArray(children)) {
    if (children && typeof children === 'object') {
      const child = children as Record<string, unknown>;
      const id = typeof child.componentId === 'string' ? child.componentId : '';
      const resolved = id ? byId.get(id) : undefined;
      return resolved ? [resolved] : [];
    }
    return [];
  }
  return children
    .map((child) => {
      if (typeof child === 'string') return byId.get(child);
      return isNode(child) ? child : undefined;
    })
    .filter((child): child is ComponentNode => Boolean(child));
}

function layoutStyle(node: ComponentNode): CSSProperties {
  const component = String(node.component || '');
  const style: CSSProperties = {
    minWidth: 0,
    boxSizing: 'border-box',
  };
  if (component === 'Row') {
    style.display = 'flex';
    style.flexDirection = 'row';
    style.alignItems = 'center';
    style.gap = 8;
  } else if (component === 'Column') {
    style.display = 'flex';
    style.flexDirection = 'column';
    style.gap = 8;
  } else if (component === 'Stack') {
    style.display = 'grid';
    style.gridTemplateAreas = '"stack"';
    style.alignItems = 'stretch';
  }
  const padding = node.padding;
  if (typeof padding === 'number' || typeof padding === 'string') style.padding = padding;
  const width = node.width;
  if (typeof width === 'number' || typeof width === 'string') style.width = width;
  return style;
}

function RenderNode({ node, byId, depth = 0 }: { node: ComponentNode; byId: Map<string, ComponentNode>; depth?: number }) {
  if (depth > 24) return <div className="artifact-preview__unknown">嵌套层级过深</div>;
  const component = String(node.component || 'Unknown');
  const children = childNodes(node, byId);
  const content = node.content ?? node.text ?? node.label;
  const style = layoutStyle(node);
  const renderChildren = () => children.map((child, index) => (
    <RenderNode key={String(child.id || index)} node={child} byId={byId} depth={depth + 1} />
  ));

  switch (component) {
    case 'Text':
      return <div style={{ ...style, color: '#172033', fontSize: 14, lineHeight: 1.45 }}>{valueToText(content)}</div>;
    case 'Column':
    case 'Row':
      return <div style={style}>{renderChildren()}</div>;
    case 'Stack':
      return <div style={{ ...style, position: 'relative' }}>{children.map((child, index) => (
        <div key={String(child.id || index)} style={{ gridArea: 'stack' }}><RenderNode node={child} byId={byId} depth={depth + 1} /></div>
      ))}</div>;
    case 'Image': {
      const source = node.src ?? node.url ?? node.source ?? node.image;
      return <div style={{ ...style, overflow: 'hidden', borderRadius: 10, background: '#edf1f8' }}>
        {typeof source === 'string' && source ? <img src={source} alt={valueToText(node.alt || '卡片图片')} style={{ display: 'block', maxWidth: '100%', width: '100%', objectFit: 'cover' }} /> : <div className="artifact-preview__placeholder">图片素材</div>}
      </div>;
    }
    case 'Button':
      return <button type="button" style={{ ...style, border: 0, borderRadius: 9, padding: '8px 14px', color: '#fff', background: '#4659d8', fontWeight: 600 }}>{valueToText(content || '按钮')}</button>;
    case 'Progress': {
      const value = Number(node.value ?? 0);
      const total = Math.max(1, Number(node.total ?? 100));
      const percentage = Math.max(0, Math.min(100, (value / total) * 100));
      return <div style={{ ...style, display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ height: 7, flex: 1, borderRadius: 5, background: '#e4e9f2', overflow: 'hidden' }}><div style={{ height: '100%', width: `${percentage}%`, background: '#3aa984', borderRadius: 5 }} /></div>
        <span style={{ color: '#667085', fontSize: 12 }}>{Math.round(percentage)}%</span>
      </div>;
    }
    case 'Checkbox': {
      const checked = Boolean(node.checked ?? node.selected ?? node.value);
      return <div style={{ ...style, display: 'flex', alignItems: 'center', gap: 8, color: '#344054', fontSize: 13 }}>
        <span aria-hidden="true" style={{ width: 16, height: 16, display: 'inline-grid', placeItems: 'center', borderRadius: 4, border: `1px solid ${checked ? '#4659d8' : '#b8c1d1'}`, background: checked ? '#4659d8' : '#fff', color: '#fff', fontSize: 11 }}>{checked ? '✓' : ''}</span>
        {valueToText(node.label || content)}
      </div>;
    }
    case 'Divider':
      return <div role="separator" style={{ ...style, height: 1, width: '100%', background: '#e6eaf0', margin: '3px 0' }} />;
    default:
      return <div className="artifact-preview__unknown"><strong>{component}</strong><span>暂不支持视觉预览，可切换代码查看</span></div>;
  }
}

function JsonView({ value }: { value: unknown }) {
  const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  return <pre className="artifact-preview__code">{text || '暂无内容'}</pre>;
}

export function ArtifactPreview({ artifact, activeKind, onKindChange }: ArtifactPreviewProps) {
  const kindValue = artifact?.[activeKind];
  const nodes = useMemo(() => parseGenui(artifact?.genui), [artifact?.genui]);
  const byId = useMemo(() => new Map(nodes.filter((node) => typeof node.id === 'string').map<[string, ComponentNode]>((node) => [node.id as string, node])), [nodes]);
  const roots = useMemo(() => {
    if (!nodes.length) return [];
    const referenced = new Set(nodes.flatMap((node) => childNodes(node, byId).map((child) => child.id)).filter(Boolean));
    return nodes.filter((node) => !node.id || !referenced.has(node.id));
  }, [nodes, byId]);
  const isGenui = activeKind === 'genui';

  return <section className="artifact-preview" aria-label="Artifact 预览">
    <div className="artifact-preview__tabs" role="tablist">
      {COMPONENT_KINDS.filter((kind) => artifact?.[kind] !== undefined).map((kind) => (
        <button key={kind} type="button" role="tab" aria-selected={activeKind === kind} className={activeKind === kind ? 'is-active' : ''} onClick={() => onKindChange(kind)}>{kind}</button>
      ))}
    </div>
    <div className="artifact-preview__body">
      {isGenui && roots.length ? <div className="artifact-preview__canvas">{roots.map((node, index) => <RenderNode key={String(node.id || index)} node={node} byId={byId} />)}</div> : null}
      {!isGenui || !roots.length ? <JsonView value={kindValue} /> : <details className="artifact-preview__source"><summary>查看 GenUI 源码</summary><JsonView value={kindValue} /></details>}
    </div>
  </section>;
}

export default ArtifactPreview;
