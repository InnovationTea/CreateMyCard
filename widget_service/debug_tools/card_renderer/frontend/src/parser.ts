/**
 * Parser and data-binding helpers for the local card renderer.
 *
 * The accepted input intentionally mirrors docs/index.html: JSONL A2UI rows,
 * compact DSL rows, and design-compact rows.  The module has no DOM imports so
 * it can also be used by the platform to inspect an artifact before rendering.
 */

import { UIGraph } from '@genui-sdk/graph';
import { JsonlStreamParser } from '@genui-sdk/parser';
import { compileMiniDsl } from './runtime/mini-renderer';

export const COMPONENT_TYPES = new Set([
  'Row',
  'Column',
  'List',
  'Stack',
  'Grid',
  'Text',
  'Image',
  'Divider',
  'Progress',
  'Button',
  'Checkbox',
  'Card',
]);

export type CardSize = 'auto' | '2x2' | '2x4';

export interface SurfaceSize {
  width: number;
  height: number;
}

export interface ComponentNode {
  id: string;
  type: string;
  props: Record<string, unknown>;
  children: string[];
}

export interface RendererDocument {
  mode: 'A2UI' | 'Compact DSL' | 'Design Compact DSL';
  surface: SurfaceSize;
  rootId: string;
  components: Map<string, ComponentNode>;
  data: Record<string, unknown>;
  dataPathCount: number;
  rows: unknown[];
  graph: UIGraph;
  warnings: string[];
  jsonl: string;
}

export interface ParseOptions {
  cardSize?: CardSize;
}

export const COLOR_TOKENS: Record<string, string> = {
  font_primary: '#E5000000',
  font_secondary: '#99000000',
  font_tertiary: '#66000000',
  font_emphasize: '#FF0A59F7',
  font_on_primary: '#FFFFFFFF',
  warning: '#FFE84026',
  alert: '#FFED6F21',
  confirm: '#FF64BB5C',
  icon_primary: '#E5000000',
  icon_secondary: '#99000000',
  icon_tertiary: '#66000000',
  icon_emphasize: '#FF0A59F7',
  icon_on_primary: '#FFFFFFFF',
  icon_on_tertiary: '#66FFFFFF',
  background_primary: '#FFFFFFFF',
  background_emphasize: '#FF0A59F7',
  comp_background_list_card: '#FFFFFFFF',
  comp_background_emphasize: '#FF0A59F7',
  comp_background_tertiary: '#0C000000',
  comp_background_secondary: '#19000000',
  comp_background_primary_contrary: '#FFFFFFFF',
  comp_divider: '#33000000',
  container40: '#66000000',
  primary50: '#7F000000',
  multi_color_01: '#FF564AF7',
  multi_color_02: '#FF46B1E3',
  multi_color_03: '#FF61CFBE',
  multi_color_04: '#FF64BB5C',
  multi_color_05: '#FFA5D61D',
  multi_color_06: '#FFAC49F5',
  multi_color_07: '#FFE64566',
  multi_color_08: '#FFE84026',
  multi_color_09: '#FFED6F21',
  multi_color_10: '#FFF9A01E',
  multi_color_11: '#FFF7CE00',
  multi_color_aux_01: '#FF8981F7',
  multi_color_aux_02: '#FF86C5E3',
  multi_color_aux_03: '#FF92D6CC',
  multi_color_aux_04: '#FF92C48D',
  multi_color_aux_05: '#FFBDDB69',
  multi_color_aux_06: '#FFC386F0',
  multi_color_aux_07: '#FFE67C92',
  multi_color_aux_08: '#FFE87361',
  multi_color_aux_09: '#FFED955F',
  multi_color_aux_10: '#FFF9BC64',
  multi_color_aux_11: '#FFF5DC62',
  mask_primary: '#CC000000',
  mask_secondary: '#99000000',
  mask_tertiary: '#66000000',
  mask_fourth: '#33000000',
  mask_fifth: '#19000000',
  mask_sixth: '#0C000000',
};

export const DESIGN_TOKENS: Record<string, Record<string, Record<string, unknown>>> = {
  Text: {
    'display-l': { fontSize: 56, fontWeight: 300 },
    'display-m': { fontSize: 48, fontWeight: 300 },
    'display-s': { fontSize: 36, fontWeight: 700 },
    'title-l': { fontSize: 30, fontWeight: 700 },
    'title-m': { fontSize: 24, fontWeight: 700 },
    'title-s': { fontSize: 20, fontWeight: 700 },
    'subtitle-l': { fontSize: 18, fontWeight: 500 },
    'subtitle-m': { fontSize: 16, fontWeight: 500 },
    'subtitle-s': { fontSize: 14, fontWeight: 500 },
    'body-l': { fontSize: 16, fontWeight: 500 },
    'body-m': { fontSize: 14, fontWeight: 400 },
    'body-s': { fontSize: 12, fontWeight: 400 },
    'caption-l': { fontSize: 12, fontWeight: 500 },
    'caption-m': { fontSize: 10, fontWeight: 500 },
  },
  Button: {
    capsule: {
      width: 'matchParent',
      height: 36,
      borderRadius: 20,
      padding: { left: 8, top: 0, right: 8, bottom: 0 },
      backgroundColor: 'comp_background_tertiary',
      fontColor: 'font_emphasize',
      fontSize: 14,
      fontWeight: 500,
      maxLines: 1,
      flexShrink: 0,
    },
    'icon-round': {
      width: 36,
      height: 36,
      borderRadius: 18,
      padding: 0,
      backgroundColor: 'comp_background_tertiary',
      flexShrink: 0,
    },
  },
  Progress: {
    ring: {
      type: 'ring',
      width: 44,
      height: 44,
      strokeWidth: 6,
      backgroundColor: 'comp_background_secondary',
      color: 'font_emphasize',
    },
    'linear-bar': {
      type: 'linear',
      width: 'matchParent',
      height: 8,
      borderRadius: 4,
      backgroundColor: 'comp_background_secondary',
    },
    'segmented-bar': {
      type: 'linear',
      width: 'matchParent',
      height: 8,
      borderRadius: 4,
      backgroundColor: 'comp_background_secondary',
    },
    'threshold-bar': {
      type: 'linear',
      width: 'matchParent',
      height: 20,
      borderRadius: 10,
      backgroundColor: '#6B7F91',
      color: '#C8F000',
    },
  },
  Divider: {
    line: { strokeWidth: 1, vertical: false, color: 'comp_divider' },
    bar: { strokeWidth: 8, vertical: false, color: 'comp_background_tertiary' },
  },
  Checkbox: {
    default: {
      width: 20,
      height: 20,
      borderRadius: 10,
      selectedColor: 'comp_background_emphasize',
      unSelectedColor: 'icon_tertiary',
      shape: 'circle',
    },
  },
};

type UnknownRecord = Record<string, unknown>;

function isRecord(value: unknown): value is UnknownRecord {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value));
}

/** Parse concatenated JSON values and JSONL without relying on line breaks. */
export function collectJsonSegments(text: string): string[] {
  const segments: string[] = [];
  let start = -1;
  const stack: string[] = [];
  let inString = false;
  let escaped = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (start < 0) {
      if (char === '{' || char === '[') {
        start = index;
        stack.push(char);
      }
      continue;
    }

    if (inString) {
      if (escaped) escaped = false;
      else if (char === '\\') escaped = true;
      else if (char === '"') inString = false;
      continue;
    }

    if (char === '"') inString = true;
    else if (char === '{' || char === '[') stack.push(char);
    else if (char === '}' || char === ']') {
      stack.pop();
      if (stack.length === 0) {
        segments.push(text.slice(start, index + 1));
        start = -1;
      }
    }
  }
  return segments;
}

function safeJsonParse(value: string): unknown {
  try {
    return JSON.parse(value) as unknown;
  } catch {
    return null;
  }
}

function isComponentRow(row: unknown): row is unknown[] {
  return Array.isArray(row)
    && row.length >= 3
    && typeof row[0] === 'string'
    && COMPONENT_TYPES.has(normalizeType(row[1]));
}

function isPathRow(row: unknown): row is [string, unknown] {
  return Array.isArray(row)
    && row.length === 2
    && typeof row[0] === 'string'
    && row[0].startsWith('/');
}

function isA2uiRow(value: unknown): value is UnknownRecord {
  if (!isRecord(value) || typeof value.version !== 'string') return false;
  return isRecord(value.createSurface)
    || isRecord(value.updateComponents)
    || isRecord(value.updateDataModel);
}

/**
 * Unwrap artifact envelopes while retaining rows such as suggestSize. This is
 * deliberately conservative: only known artifact fields are traversed.
 */
function collectRows(value: unknown, output: unknown[], depth = 0): void {
  if (depth > 12 || value == null) return;
  if (typeof value === 'string') {
    const nestedText = value.trim();
    if (!nestedText.startsWith('{') && !nestedText.startsWith('[')) return;
    const nestedValues = parseRows(nestedText);
    for (const nested of nestedValues) output.push(nested);
    return;
  }
  if (isComponentRow(value) || isPathRow(value) || isA2uiRow(value)) {
    output.push(value);
    return;
  }
  if (Array.isArray(value)) {
    for (const item of value) collectRows(item, output, depth + 1);
    return;
  }
  if (!isRecord(value)) return;

  if (value.suggestSize === '2x2' || value.suggestSize === '2x4') output.push(value);

  const knownKeys = ['genui', 'dsl', 'compactDsl', 'compact_dsl', 'artifact', 'cardSpec', 'card_spec'];
  let traversed = false;
  for (const key of knownKeys) {
    if (key in value) {
      traversed = true;
      collectRows(value[key], output, depth + 1);
    }
  }
  if (!traversed && (Array.isArray(value.components) || Array.isArray(value.rows))) {
    collectRows(value.components ?? value.rows, output, depth + 1);
  }
}

function parseRows(text: string): unknown[] {
  const values: unknown[] = [];
  const trimmed = text.trim();
  if (trimmed) {
    const whole = safeJsonParse(trimmed);
    if (whole !== null) values.push(whole);
  }
  if (values.length === 0) {
    for (const segment of collectJsonSegments(text)) {
      const parsed = safeJsonParse(segment);
      if (parsed !== null) values.push(parsed);
    }
  }
  const rows: unknown[] = [];
  for (const value of values) collectRows(value, rows);
  return rows;
}

export function parseInput(text: string, options: ParseOptions = {}): RendererDocument {
  const rows = parseRows(text);
  const compactRows = rows.filter((row): row is unknown[] => Array.isArray(row));
  if (compactRows.length > 0) {
    return compileCompactDocument(
      unwrapRenderableSource(text),
      compactRows,
      rows,
      options,
    );
  }
  const a2uiRows = rows.filter(isA2uiRow);
  const source = a2uiRows.length > 0
    ? a2uiRows.map((row) => JSON.stringify(row)).join('\n')
    : unwrapRenderableSource(text);
  return compileGraphDocument(source, rows, options);
}

function compileCompactDocument(
  source: string,
  compactRows: unknown[][],
  allRows: unknown[],
  options: ParseOptions,
): RendererDocument {
  const selectedSize = options.cardSize === '2x2' || options.cardSize === '2x4'
    ? options.cardSize
    : undefined;
  const result = compileMiniDsl(source, { size: selectedSize });
  const mode = compactRows.some((row) => isRecord(row[2]) && typeof row[2].design === 'string')
    ? 'Design Compact DSL'
    : 'Compact DSL';
  return documentFromGraph({
    graph: result.graph,
    jsonl: result.jsonl,
    mode,
    options,
    rows: allRows,
    suggestedSize: result.size,
    warnings: result.warnings,
  });
}

function compileGraphDocument(
  source: string,
  rows: unknown[],
  options: ParseOptions,
): RendererDocument {
  const graph = new UIGraph();
  const warnings: string[] = [];
  const commands: Record<string, unknown>[] = [];
  const parser = new JsonlStreamParser<Record<string, unknown>>({
    onMessage: (command) => {
      commands.push(command);
      graph.applyCommand(command);
    },
    onParseError: (_raw, error) => {
      warnings.push(error instanceof Error ? error.message : String(error));
    },
    onBraceMismatch: () => warnings.push('输入包含不匹配的右花括号。'),
  });
  parser.push(source);
  parser.end();
  if (parser.getPending().trim()) warnings.push('输入末尾包含未完成的 JSON。');
  if (!graph.getRoot()) {
    const detail = warnings[0] ? `：${warnings[0]}` : '';
    throw new Error(`没有识别到可渲染的 A2UI 或 Graph JSONL${detail}`);
  }
  return documentFromGraph({
    graph,
    jsonl: commands.map((command) => JSON.stringify(command)).join('\n'),
    mode: 'A2UI',
    options,
    rows: rows.length > 0 ? rows : commands,
    warnings,
  });
}

interface DocumentFromGraphOptions {
  graph: UIGraph;
  jsonl: string;
  mode: RendererDocument['mode'];
  options: ParseOptions;
  rows: unknown[];
  warnings: string[];
  suggestedSize?: '2x2' | '2x4';
}

function documentFromGraph(input: DocumentFromGraphOptions): RendererDocument {
  const components = new Map<string, ComponentNode>();
  for (const [id, node] of input.graph.getAllNodes()) {
    components.set(id, {
      id,
      type: normalizeType(node.type).replace(/^Extended\./, ''),
      props: { ...node.props },
      children: [...node.children],
    });
  }
  const activeSurfaceId = input.graph.getActiveSurfaceId();
  const model = activeSurfaceId
    ? input.graph.getDataModelValue(activeSurfaceId, '/')
    : undefined;
  const data = isRecord(model) ? model : {};
  const root = input.graph.getRoot();
  const selected = sizeForCard(input.options.cardSize);
  const suggested = sizeForCard(input.suggestedSize ?? findSuggestSize(input.rows));
  const declared = findDeclaredSurface(input.rows);
  const inferred = inferSurface(root ? components.get(root.id) : undefined);
  return {
    mode: input.mode,
    surface: {
      width: selected?.width ?? declared.width ?? suggested?.width ?? inferred.width,
      height: selected?.height ?? declared.height ?? suggested?.height ?? inferred.height,
    },
    rootId: root?.id ?? 'root',
    components,
    data,
    dataPathCount: countLeafPaths(data),
    rows: input.rows,
    graph: input.graph,
    warnings: input.warnings,
    jsonl: input.jsonl,
  };
}

function findDeclaredSurface(rows: unknown[]): { width: number | null; height: number | null } {
  for (const row of rows) {
    if (!isRecord(row) || !isRecord(row.createSurface)) continue;
    return {
      width: numberOr(row.createSurface.width, null),
      height: numberOr(row.createSurface.height, null),
    };
  }
  return { width: null, height: null };
}

function unwrapRenderableSource(text: string): string {
  const trimmed = text.trim().replace(
    /^```(?:jsonl?|genui|a2ui)?\s*\n([\s\S]*?)\n```$/i,
    '$1',
  );
  const parsed = safeJsonParse(trimmed);
  return unwrapRenderableValue(parsed) ?? trimmed;
}

function unwrapRenderableValue(value: unknown, depth = 0): string | null {
  if (depth > 12 || value == null) return null;
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return JSON.stringify(value);
  if (!isRecord(value)) return null;
  for (const key of ['genui', 'dsl', 'compactDsl', 'compact_dsl', 'artifact']) {
    if (!(key in value)) continue;
    const nested = unwrapRenderableValue(value[key], depth + 1);
    if (nested !== null) return nested;
  }
  return JSON.stringify(value);
}

function parseA2ui(rows: UnknownRecord[], allRows: unknown[], options: ParseOptions): RendererDocument {
  const data: Record<string, unknown> = {};
  const components = new Map<string, ComponentNode>();
  const surface: { width: number | null; height: number | null } = { width: null, height: null };
  let rootId = 'root';

  for (const row of rows) {
    const createSurface = row.createSurface;
    if (isRecord(createSurface)) {
      surface.width = numberOr(createSurface.width, surface.width);
      surface.height = numberOr(createSurface.height, surface.height);
    }
    const dataModel = row.updateDataModel;
    if (isRecord(dataModel)) setPath(data, dataModel.path ?? '/', dataModel.value);

    const updateComponents = row.updateComponents;
    if (!isRecord(updateComponents)) continue;
    if (typeof updateComponents.root === 'string') rootId = updateComponents.root;
    const items = Array.isArray(updateComponents.components) ? updateComponents.components : [];
    for (const rawItem of items) {
      if (!isRecord(rawItem) || typeof rawItem.id !== 'string') continue;
      const props: Record<string, unknown> = {};
      for (const [key, value] of Object.entries(rawItem)) {
        if (!['id', 'component', 'children', 'styles', 'itemMargin'].includes(key)) props[key] = value;
      }
      if (isRecord(rawItem.styles)) Object.assign(props, rawItem.styles);
      if (rawItem.itemMargin != null && props.space == null) props.space = rawItem.itemMargin;
      components.set(rawItem.id, {
        id: rawItem.id,
        type: normalizeType(rawItem.component),
        props,
        children: Array.isArray(rawItem.children)
          ? rawItem.children.filter((item): item is string => typeof item === 'string')
          : [],
      });
    }
  }

  const root = components.get(rootId);
  const inferred = inferSurfaceFromChildren(root, components);
  const selected = sizeForCard(options.cardSize);
  const suggested = sizeForCard(findSuggestSize(allRows));
  const resolvedSurface: SurfaceSize = {
    width: selected?.width ?? numberOr(surface.width, suggested?.width ?? inferred.width ?? 160),
    height: selected?.height ?? numberOr(surface.height, suggested?.height ?? inferred.height ?? 160),
  };
  return {
    mode: 'A2UI',
    surface: resolvedSurface,
    rootId,
    components,
    data,
    dataPathCount: countLeafPaths(data),
    rows: allRows,
    graph: new UIGraph(),
    warnings: [],
    jsonl: rows.map((row) => JSON.stringify(row)).join('\n'),
  };
}

function parseCompact(rows: unknown[][], options: ParseOptions): RendererDocument {
  const data: Record<string, unknown> = {};
  const components = new Map<string, ComponentNode>();
  let rootId = 'root';

  for (const row of rows) {
    if (isComponentRow(row)) {
      const id = String(row[0]);
      const type = normalizeType(row[1]);
      const props = normalizeDesignProps(type, isRecord(row[2]) ? { ...row[2] } : {});
      const nestedStyles = isRecord(props.styles) ? props.styles : null;
      if (nestedStyles) {
        delete props.styles;
        Object.assign(props, nestedStyles);
      }
      components.set(id, {
        id,
        type,
        props,
        children: Array.isArray(row[3])
          ? row[3].filter((item): item is string => typeof item === 'string')
          : [],
      });
      if (components.size === 1 || id === 'root') rootId = id;
    } else if (isPathRow(row)) {
      setPath(data, row[0], row[1]);
    }
  }
  const root = components.get(rootId) ?? components.values().next().value;
  const inferred = inferSurface(root);
  const selected = sizeForCard(options.cardSize);
  return {
    mode: hasDesignToken(components) ? 'Design Compact DSL' : 'Compact DSL',
    surface: selected ?? inferred,
    rootId: root?.id ?? rootId,
    components,
    data,
    dataPathCount: countLeafPaths(data),
    rows,
    graph: new UIGraph(),
    warnings: [],
    jsonl: rows.map((row) => JSON.stringify(row)).join('\n'),
  };
}

function normalizeDesignProps(type: string, props: Record<string, unknown>): Record<string, unknown> {
  const design = props.design;
  if (typeof design !== 'string') return props;
  const token = DESIGN_TOKENS[type]?.[design];
  props.__design = design;
  delete props.design;
  return token ? { ...token, ...props } : props;
}

function hasDesignToken(components: Map<string, ComponentNode>): boolean {
  for (const component of components.values()) if (component.props.__design != null) return true;
  return false;
}

function inferSurface(root: ComponentNode | undefined): SurfaceSize {
  if (!root) return { width: 160, height: 160 };
  const props = root.props;
  const constraint = isRecord(props.constraintSize) ? props.constraintSize : {};
  const width = numberOr(constraint.maxWidth ?? constraint.minWidth ?? props.width, props.height === 140 ? 140 : 160);
  const height = numberOr(constraint.maxHeight ?? constraint.minHeight ?? props.height, 160);
  return { width, height };
}

function inferSurfaceFromChildren(
  root: ComponentNode | undefined,
  components: Map<string, ComponentNode>,
): { width: number | null; height: number | null } {
  if (!root) return { width: null, height: null };
  const props = root.props;
  const rootWidth = numberOr(props.width, null);
  const rootHeight = numberOr(props.height, null);
  if (rootWidth != null && rootHeight != null) return { width: rootWidth, height: rootHeight };
  if (numberOr(props.borderRadius, null) === 22) return { width: 320, height: 160 };
  const children = root.children.map((id) => components.get(id)).filter(
    (child): child is ComponentNode => Boolean(child),
  );
  if (children.length === 0) return { width: null, height: null };
  const sizes = children.map((child) => ({
    width: numberOr(child.props.width, null),
    height: numberOr(child.props.height, null),
  }));
  if (sizes.some((size) => size.width == null || size.height == null)) return { width: null, height: null };
  const gap = numberOr(props.space ?? props.itemMargin, 0);
  const padding = edgeNumbers(props.padding);
  if (root.type === 'Row') {
    return {
      width: sizes.reduce((total, size) => total + (size.width ?? 0), 0)
        + gap * Math.max(0, sizes.length - 1) + padding.left + padding.right,
      height: Math.max(...sizes.map((size) => size.height ?? 0)) + padding.top + padding.bottom,
    };
  }
  if (['Column', 'List', 'Card'].includes(root.type)) {
    return {
      width: Math.max(...sizes.map((size) => size.width ?? 0)) + padding.left + padding.right,
      height: sizes.reduce((total, size) => total + (size.height ?? 0), 0)
        + gap * Math.max(0, sizes.length - 1) + padding.top + padding.bottom,
    };
  }
  return { width: null, height: null };
}

function findSuggestSize(rows: unknown[]): CardSize | '' {
  for (const row of rows) {
    if (!isRecord(row)) continue;
    const candidates = [row.suggestSize, row.cardSpec && isRecord(row.cardSpec) ? row.cardSpec.suggestSize : undefined,
      row.artifact && isRecord(row.artifact) && isRecord(row.artifact.cardSpec)
        ? row.artifact.cardSpec.suggestSize : undefined];
    const match = candidates.find((value): value is CardSize => value === '2x2' || value === '2x4');
    if (match) return match;
  }
  return '';
}

function normalizedCardSize(value: unknown): Exclude<CardSize, 'auto'> | null {
  if (typeof value !== 'string') return null;
  const normalized = value.trim().toLowerCase().replace(/[×＊*]/g, 'x');
  if (normalized === '2x2' || normalized === '2x4') return normalized;
  return null;
}

function cardSizeFromSpec(value: unknown, depth = 0): Exclude<CardSize, 'auto'> | null {
  if (depth > 8 || value == null) return null;
  if (typeof value === 'string') {
    const parsed = safeJsonParse(value);
    return parsed === null ? null : cardSizeFromSpec(parsed, depth + 1);
  }
  if (!isRecord(value)) return null;
  const direct = normalizedCardSize(value.suggestSize) ?? normalizedCardSize(value.size);
  if (direct) return direct;
  for (const key of ['cardSpec', 'card_spec', 'cardspec', 'artifact', 'data', 'response']) {
    if (!(key in value)) continue;
    const nested = cardSizeFromSpec(value[key], depth + 1);
    if (nested) return nested;
  }
  return null;
}

function cardSizeFromQuery(value: unknown, depth = 0): Exclude<CardSize, 'auto'> | null {
  if (depth > 8 || value == null) return null;
  if (typeof value === 'string') {
    const match = value.match(/(?:^|[^0-9])2\s*(?:x|×|＊|\*|乘)\s*([24])(?:[^0-9]|$)/i);
    return match ? normalizedCardSize(`2x${match[1]}`) : null;
  }
  if (!isRecord(value)) return null;
  for (const key of ['userQuery', 'query', 'original', 'utterance', 'content', 'taskSpec']) {
    if (!(key in value)) continue;
    const nested = cardSizeFromQuery(value[key], depth + 1);
    if (nested) return nested;
  }
  return null;
}

export function resolveCardSize(
  cardSpec: unknown,
  query: unknown,
  fallback?: unknown,
): CardSize {
  return cardSizeFromSpec(cardSpec)
    ?? cardSizeFromQuery(query)
    ?? normalizedCardSize(fallback)
    ?? 'auto';
}

export function sizeForCard(value: unknown): SurfaceSize | null {
  const normalized = normalizedCardSize(value);
  if (normalized === '2x2') return { width: 150, height: 150 };
  if (normalized === '2x4') return { width: 300, height: 150 };
  return null;
}

export function normalizeType(value: unknown): string {
  const type = String(value ?? '');
  return type === 'Container' ? 'Column' : type;
}

export function numberOr<T>(value: unknown, fallback: T): number | T {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && /^\d+(\.\d+)?$/.test(value)) return Number(value);
  return fallback;
}

export function stringify(value: unknown): string {
  if (value == null) return '';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value);
  try {
    return JSON.stringify(value) ?? '';
  } catch {
    return '';
  }
}

export function getPath(data: unknown, path: unknown): unknown {
  if (!path || path === '/') return data;
  const normalized = String(path)
    .trim()
    .replace(/^\$\{?/, '')
    .replace(/\}?$/, '')
    .replace(/^\$\.?/, '')
    .replace(/\[(\d+)\]/g, '.$1');
  const parts = normalized.split(normalized.includes('/') ? '/' : '.').filter(Boolean);
  let node: unknown = data;
  for (const part of parts) {
    if (node == null || (typeof node !== 'object' && typeof node !== 'function')) return '';
    node = (node as UnknownRecord)[part];
  }
  return node == null ? '' : node;
}

export function setPath(data: Record<string, unknown>, path: unknown, value: unknown): void {
  if (!path || path === '/') {
    if (isRecord(value)) Object.assign(data, value);
    return;
  }
  const parts = String(path).split('/').filter(Boolean);
  let node: UnknownRecord | unknown[] = data;
  for (let index = 0; index < parts.length; index += 1) {
    const part = parts[index];
    const last = index === parts.length - 1;
    if (last) {
      if (Array.isArray(node)) node[Number(part)] = value;
      else node[part] = value;
      return;
    }
    const nextIsArray = /^\d+$/.test(parts[index + 1]);
    if (Array.isArray(node)) {
      const arrayIndex = Number(part);
      if (node[arrayIndex] == null || typeof node[arrayIndex] !== 'object') node[arrayIndex] = nextIsArray ? [] : {};
      node = node[arrayIndex] as UnknownRecord | unknown[];
    } else {
      if (node[part] == null || typeof node[part] !== 'object') node[part] = nextIsArray ? [] : {};
      node = node[part] as UnknownRecord | unknown[];
    }
  }
}

export function countLeafPaths(value: unknown): number {
  if (value == null || typeof value !== 'object') return 1;
  if (Array.isArray(value)) return value.reduce((count, item) => count + countLeafPaths(item), 0);
  return Object.values(value).reduce((count, item) => count + countLeafPaths(item), 0);
}

export function resolveTemplate(value: string, data: unknown): string {
  const fullExpression = value.match(/^\{\{\s*([\s\S]*?)\s*\}\}$/);
  if (fullExpression) {
    const expression = fullExpression[1];
    const countdown = expression.match(
      /^\$\{([^}]+)\}\s*==\s*0\s*\?\s*'([^']*)'\s*:\s*\(\s*\$\{([^}]+)\}\s*>\s*0\s*\?\s*\$\{([^}]+)\}\s*\+\s*'([^']*)'\s*:\s*'([^']*)'\s*\)$/,
    );
    if (countdown && countdown[1] === countdown[3] && countdown[1] === countdown[4]) {
      const numeric = Number(getPath(data, countdown[1].trim()));
      if (numeric === 0) return countdown[2];
      return numeric > 0 ? `${numeric}${countdown[5]}` : countdown[6];
    }
    const booleanChoice = expression.match(/^\$\{([^}]+)\}\s*\?\s*'([^']*)'\s*:\s*'([^']*)'$/);
    if (booleanChoice) return getPath(data, booleanChoice[1].trim()) ? booleanChoice[2] : booleanChoice[3];
    const concatenated = resolveConcatenation(expression, data);
    if (concatenated != null) return concatenated;
  }
  return value
    .replace(/\{\{\s*\$\{([^}]+)\}\s*(?:\+\s*(['"])(.*?)\2)?\s*\}\}/g,
      (_match, path: string, _quote: string, suffix: string) => `${stringify(getPath(data, path.trim()))}${suffix ?? ''}`)
    .replace(/\{\{\s*([A-Za-z0-9_$./[\]-]+)\s*\}\}/g,
      (_match, path: string) => stringify(getPath(data, path.trim())));
}

function resolveConcatenation(expression: string, data: unknown): string | null {
  let index = 0;
  const values: string[] = [];
  while (index < expression.length) {
    index = skipWhitespace(expression, index);
    const operand = readExpressionOperand(expression, index, data);
    if (!operand) return null;
    values.push(operand.value);
    index = skipWhitespace(expression, operand.nextIndex);
    if (index === expression.length) return values.join('');
    if (expression[index] !== '+') return null;
    index += 1;
  }
  return null;
}

function readExpressionOperand(expression: string, index: number, data: unknown): { value: string; nextIndex: number } | null {
  if (expression.startsWith('${', index)) {
    const end = expression.indexOf('}', index + 2);
    if (end < 0) return null;
    const path = expression.slice(index + 2, end).trim();
    return path ? { value: stringify(getPath(data, path)), nextIndex: end + 1 } : null;
  }
  const quote = expression[index];
  if (quote !== "'" && quote !== '"') return null;
  let value = '';
  for (let cursor = index + 1; cursor < expression.length; cursor += 1) {
    const character = expression[cursor];
    if (character === quote) return { value, nextIndex: cursor + 1 };
    if (character !== '\\') {
      value += character;
      continue;
    }
    cursor += 1;
    if (cursor >= expression.length) return null;
    value += ({ n: '\n', r: '\r', t: '\t' } as Record<string, string>)[expression[cursor]] ?? expression[cursor];
  }
  return null;
}

function skipWhitespace(value: string, index: number): number {
  let cursor = index;
  while (cursor < value.length && /\s/.test(value[cursor])) cursor += 1;
  return cursor;
}

export function resolveValue(value: unknown, data: unknown): unknown {
  if (isRecord(value) && typeof value.path === 'string') return getPath(data, value.path);
  if (Array.isArray(value)) return value.map((item) => resolveValue(item, data));
  if (isRecord(value)) {
    if (value.call === 'formatString') {
      const args = isRecord(value.args) ? value.args : {};
      const format = String(args.format ?? value.format ?? '{}');
      const values = Array.isArray(args.values) ? args.values : [];
      let index = 0;
      return format.replace(/\{\}/g, () => stringify(resolveValue(values[index++], data)));
    }
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, resolveValue(item, data)]));
  }
  return typeof value === 'string' ? resolveTemplate(value, data) : value;
}

export function resolveProps(props: Record<string, unknown>, data: unknown): Record<string, unknown> {
  return Object.fromEntries(Object.entries(props).map(([key, value]) => [key, key === '__design' ? value : resolveValue(value, data)]));
}

export function normalizeA2uiColor(value: string): string {
  if (!/^#[0-9a-fA-F]{8}$/.test(value)) return value;
  const alpha = Number.parseInt(value.slice(1, 3), 16) / 255;
  const red = Number.parseInt(value.slice(3, 5), 16);
  const green = Number.parseInt(value.slice(5, 7), 16);
  const blue = Number.parseInt(value.slice(7, 9), 16);
  return `rgba(${red}, ${green}, ${blue}, ${alpha.toFixed(3)})`;
}

export function colorValue(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  return normalizeA2uiColor(COLOR_TOKENS[value] ?? value);
}

export function edgeNumbers(value: unknown): { top: number; right: number; bottom: number; left: number } {
  const uniform = numberOr(value, null);
  if (typeof uniform === 'number') return { top: uniform, right: uniform, bottom: uniform, left: uniform };
  if (!isRecord(value)) return { top: 0, right: 0, bottom: 0, left: 0 };
  return {
    top: numberOr(value.top, 0),
    right: numberOr(value.right, 0),
    bottom: numberOr(value.bottom, 0),
    left: numberOr(value.left, 0),
  };
}
