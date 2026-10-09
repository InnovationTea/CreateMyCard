import React, {
  Component,
  useMemo,
  useState,
  type CSSProperties,
  type ReactNode,
} from 'react';
import {
  CREATE_SURFACE_CMD_KEY,
  UIGraph,
  UPDATE_DATA_MODEL_CMD_KEY,
  type UINode,
} from '@genui-sdk/graph';
import {
  defaultRegistry,
  renderTree,
  type InteractionHost,
} from '@genui-sdk/renderer';
import type { ComponentNode, RendererDocument } from './parser';

export interface CardPreviewProps {
  document: RendererDocument;
  assetBaseUrl?: string;
  onAction?: (action: unknown, component: ComponentNode) => void;
  className?: string;
}

export interface RenderNodeProps extends CardPreviewProps {
  id: string;
  depth?: number;
}

interface PreviewBoundaryProps {
  children: ReactNode;
}

interface PreviewBoundaryState {
  error: string;
}

class PreviewBoundary extends Component<PreviewBoundaryProps, PreviewBoundaryState> {
  state: PreviewBoundaryState = { error: '' };

  static getDerivedStateFromError(error: Error): PreviewBoundaryState {
    return { error: error.message };
  }

  render() {
    if (this.state.error) {
      return <div className="card-renderer__runtime-error" role="alert">
        渲染失败：{this.state.error}
      </div>;
    }
    return this.props.children;
  }
}

function joinAssetUrl(assetBaseUrl: string, path: string): string {
  const base = assetBaseUrl.endsWith('/') ? assetBaseUrl : `${assetBaseUrl}/`;
  const relative = path.replace(/^\/?resources\//, '').replace(/^\/+/, '');
  return `${base}${relative}`;
}

function rewriteAssetString(value: string, assetBaseUrl: string): string {
  if (/^\/?resources\//.test(value)) return joinAssetUrl(assetBaseUrl, value);
  return value.replace(
    /url\((['"]?)(\/?resources\/[^)'"\s]+)\1\)/g,
    (_match, quote: string, path: string) => (
      `url(${quote}${joinAssetUrl(assetBaseUrl, path)}${quote})`
    ),
  );
}

function rewriteAssets(value: unknown, assetBaseUrl: string): unknown {
  if (typeof value === 'string') return rewriteAssetString(value, assetBaseUrl);
  if (Array.isArray(value)) return value.map((item) => rewriteAssets(item, assetBaseUrl));
  if (!value || typeof value !== 'object') return value;
  const output: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(value)) {
    output[key] = rewriteAssets(item, assetBaseUrl);
  }
  return output;
}

function nodeCommand(node: UINode, assetBaseUrl: string): Record<string, unknown> {
  const definition: Record<string, unknown> = {
    type: node.type,
    props: rewriteAssets(node.props, assetBaseUrl),
  };
  if (node.dynamicChildrenTemplate) {
    definition.dynamicChildrenTemplate = { ...node.dynamicChildrenTemplate };
  } else {
    definition.children = [...node.children];
  }
  return { [node.id]: definition };
}

function cloneGraph(document: RendererDocument, assetBaseUrl: string, rootId: string): UIGraph {
  const graph = new UIGraph();
  const surfaceId = document.graph.getActiveSurfaceId() ?? 'debug-card-preview';
  graph.applyCommand({ [CREATE_SURFACE_CMD_KEY]: { surfaceId } });
  const sourceNodes = document.graph.getAllNodes();
  const visited = new Set<string>();

  const applyNode = (id: string): void => {
    if (visited.has(id)) return;
    const node = sourceNodes.get(id);
    if (!node) return;
    visited.add(id);
    graph.applyCommand(nodeCommand(node, assetBaseUrl));
    for (const childId of node.children) applyNode(childId);
    if (node.dynamicChildrenTemplate) applyNode(node.dynamicChildrenTemplate.componentId);
  };

  applyNode(rootId);
  for (const id of sourceNodes.keys()) applyNode(id);
  const dataModel = document.graph.getDataModelValue(surfaceId, '/');
  if (dataModel !== undefined) {
    graph.applyCommand({
      [UPDATE_DATA_MODEL_CMD_KEY]: { surfaceId, path: '/', value: dataModel },
    });
  }
  return graph;
}

function actionComponent(document: RendererDocument, componentId: string): ComponentNode {
  return document.components.get(componentId) ?? {
    id: componentId,
    type: 'Unknown',
    props: {},
    children: [],
  };
}

function RenderSurface({
  document,
  assetBaseUrl = '/resources/',
  onAction,
  rootId,
}: CardPreviewProps & { rootId: string }) {
  const [revision, setRevision] = useState(0);
  const graph = useMemo(
    () => cloneGraph(document, assetBaseUrl, rootId),
    [assetBaseUrl, document, rootId],
  );
  const interactionHost = useMemo<InteractionHost>(() => ({
    functionCall: ({ call, args, componentId }) => {
      onAction?.(
        { functionCall: { call, args } },
        actionComponent(document, componentId),
      );
    },
    submitForm: (event) => {
      onAction?.(
        { event },
        actionComponent(document, event.sourceComponentId),
      );
    },
  }), [document, onAction]);

  return <PreviewBoundary key={`${rootId}-${revision}`}>
    {renderTree(graph, defaultRegistry, {
      formId: null,
      interactionHost,
      onDataModelUserEdit: () => setRevision((value) => value + 1),
    })}
  </PreviewBoundary>;
}

export function RenderNode({ id, document, assetBaseUrl, onAction }: RenderNodeProps) {
  return <RenderSurface
    document={document}
    assetBaseUrl={assetBaseUrl}
    onAction={onAction}
    rootId={id}
  />;
}

export function CardPreview({
  document,
  assetBaseUrl = '/resources/',
  onAction,
  className = '',
}: CardPreviewProps) {
  const style: CSSProperties = {
    width: document.surface.width,
    height: document.surface.height,
  };
  return <div
    className={`card-renderer__surface ${className}`.trim()}
    style={style}
    data-renderer-engine="render"
    data-renderer-mode={document.mode}
    data-renderer-size={`${document.surface.width}x${document.surface.height}`}
  >
    <RenderSurface
      document={document}
      assetBaseUrl={assetBaseUrl}
      onAction={onAction}
      rootId={document.rootId}
    />
  </div>;
}

export function sizeValue(value: unknown): string | undefined {
  if (typeof value === 'number') return `${value}px`;
  return typeof value === 'string' ? value : undefined;
}

export function edgeValue(value: unknown): string | undefined {
  return sizeValue(value);
}

export function gradientValue(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

export { normalizeSchemaColor as colorValue } from '@genui-sdk/components';
