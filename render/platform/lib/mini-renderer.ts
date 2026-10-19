import { UIGraph } from "@genui-sdk/graph";
import { JsonlStreamParser, tryNormalizeV09Protocol } from "@genui-sdk/parser";
import { adaptCloudEventProps } from "@genui-sdk/renderer";
import { applyDesignStyles } from "./design-handle";
import { parseExpression, resolvePathBindingsInValue } from "@genui-sdk/interactions";
import {
  HIGH_LEVEL_COMPONENT_TYPES,
  expandCompactComponents,
  type MiniNode,
  type CardSize,
} from "./compact-components";

export const SURFACE_ID = "dsl-preview";
type RecordValue = Record<string, unknown>;
const record = (v: unknown): v is RecordValue => typeof v === "object" && v !== null && !Array.isArray(v);
const TYPES = new Set([
  ..."Card Row Column Text Image SingleLineTitle TimelineUnit Input TextInput Radio CheckboxGroup Select Toggle Divider Grid GridRow Stack Tabs TabContent Web Navigation".split(" "),
  ...HIGH_LEVEL_COMPONENT_TYPES,
]);
const SEMANTIC_LAYOUT_TYPES = new Set(["Layout", "Region", "Group"]);

function generatedPreviewId(nodes: Map<string, MiniNode>, base: string): string {
  let candidate = base;
  while (nodes.has(candidate)) candidate += "_";
  return candidate;
}

function stripSemanticProps(props: RecordValue): RecordValue {
  const result = { ...props };
  delete result.layout;
  delete result.variant;
  delete result.orientation;
  return result;
}

/**
 * Error previews must remain renderable even when the formal semantic-layout
 * contract rejects the source. This is deliberately approximate: the Python
 * converter remains the only authority for publishable geometry.
 */
function expandSemanticLayoutsForPreview(
  input: Map<string, MiniNode>,
  size: CardSize,
  warn: (message: string) => void,
): Map<string, MiniNode> {
  if (![...input.values()].some(node => SEMANTIC_LAYOUT_TYPES.has(node.type))) return input;
  const output = new Map<string, MiniNode>();
  for (const [id, node] of input) {
    output.set(id, {
      type: node.type,
      props: { ...node.props },
      children: [...node.children],
    });
  }

  for (const [id, original] of input) {
    if (original.type === "Region") {
      output.set(id, {
        type: "Column",
        props: {
          width: "matchParent",
          height: "matchParent",
          layoutWeight: 1,
          padding: size === "2x4" ? 8 : 0,
          itemMargin: 4,
          alignItems: "start",
          justifyContent: "start",
          ...stripSemanticProps(original.props),
        },
        children: [...original.children],
      });
      continue;
    }
    if (original.type === "Group") {
      const variant = original.props.variant;
      const horizontal = variant === "peer-pair" || variant === "title-count";
      output.set(id, {
        type: horizontal ? "Row" : "Column",
        props: {
          width: "matchParent",
          itemMargin: horizontal ? 8 : 2,
          alignItems: "start",
          justifyContent: "start",
          ...stripSemanticProps(original.props),
        },
        children: [...original.children],
      });
      continue;
    }
    if (original.type !== "Layout") continue;

    const layout = original.props.layout;
    const visualProps = stripSemanticProps(original.props);
    const rootProps: RecordValue = {
      width: "matchParent",
      height: "matchParent",
      padding: 12,
      borderRadius: 20,
      clip: true,
      itemMargin: size === "2x4" ? 12 : 6,
      alignItems: "start",
      justifyContent: "start",
      ...visualProps,
    };
    let type = "Column";
    let children = [...original.children];

    if (layout === "W-split-panels") {
      type = "Row";
      rootProps.alignItems = "center";
    } else if (layout === "W-content-side-slots") {
      type = "Row";
      rootProps.alignItems = "center";
      if (children.length >= 3) {
        const [content, upper, lower, ...remaining] = children;
        const slotsId = generatedPreviewId(output, `${id}__preview_slots`);
        output.set(slotsId, {
          type: "Column",
          props: {
            width: "matchParent",
            height: "matchParent",
            layoutWeight: 1,
            itemMargin: 12,
            alignItems: "start",
            justifyContent: "start",
          },
          children: [upper, lower],
        });
        children = original.props.orientation === "content-right"
          ? [slotsId, content, ...remaining]
          : [content, slotsId, ...remaining];
      }
    } else if (layout === "W-four-slots" || layout === "S-quad-content") {
      const rows: string[] = [];
      for (let index = 0; index < children.length; index += 2) {
        const rowId = generatedPreviewId(output, `${id}__preview_row${index / 2}`);
        output.set(rowId, {
          type: "Row",
          props: {
            width: "matchParent",
            layoutWeight: 1,
            itemMargin: size === "2x4" ? 12 : 8,
            alignItems: "start",
            justifyContent: "start",
          },
          children: children.slice(index, index + 2),
        });
        rows.push(rowId);
      }
      children = rows;
    } else if (layout === "W-top-bottom" && children.length >= 2) {
      const title = children.length >= 3 ? children[0] : undefined;
      const bodyChildren = children.slice(-2);
      const bodyId = generatedPreviewId(output, `${id}__preview_body`);
      output.set(bodyId, {
        type: "Column",
        props: {
          width: "matchParent",
          layoutWeight: 1,
          itemMargin: 8,
          alignItems: "start",
          justifyContent: "start",
        },
        children: bodyChildren,
      });
      children = title ? [title, bodyId] : [bodyId];
      rootProps.itemMargin = 6;
    } else if (typeof layout !== "string" || !layout.startsWith("S-")) {
      warn(`宽松预览无法识别语义布局 ${String(layout)}，已按纵向容器展示。`);
    }

    output.set(id, { type, props: rootProps, children });
  }

  warn(
    "宽松预览已将 Layout / Region / Group 近似展开为基础布局；"
      + "该画面只用于定位错误，不代表正式 A2UI 或可发布结果。",
  );
  return output;
}

export function compileA2uiJsonl(source: string, options: { size?: CardSize } = {}) {
  const graph = new UIGraph();
  const warnings: string[] = [];
  const parser = new JsonlStreamParser<RecordValue>({
    onMessage: command => graph.applyCommand(command),
    onParseError: (_raw, error) => {
      warnings.push(error instanceof Error ? error.message : String(error));
    },
    onBraceMismatch: () => warnings.push("A2UI 包含不匹配的右花括号。"),
  });
  parser.push(source);
  parser.end();
  if (parser.getPending().trim()) warnings.push("A2UI 末尾包含未完成的 JSON。");
  for (const node of graph.getAllNodes().values()) {
    node.props = adaptCloudEventProps(node.props);
  }
  if (!graph.getRoot()) {
    const detail = warnings[0] ? `：${warnings[0]}` : "";
    throw new Error(`正式 Python 转换器没有返回可渲染的 A2UI${detail}`);
  }
  const count = graph.getAllNodes().size;
  return {
    graph,
    jsonl: source.trim(),
    warnings,
    count,
    expandedCount: count,
    size: options.size ?? "2x2",
  };
}

/** Balanced JSON tuples: supports JSONL, multiline tuples, and a JSON array of tuples. */
function parseTuples(source: string): unknown[][] {
  const text = source.trim().replace(/^```(?:jsonl?|genui|a2ui)?\s*\n([\s\S]*?)\n```$/i, "$1");
  if (!text) throw new Error("请粘贴极简 DSL。");
  const rows: unknown[][] = [];
  let start = -1, depth = 0, quoted = false, escaped = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (start < 0) {
      if (/\s/.test(c)) continue;
      if (c !== "[") throw new Error(`第 ${text.slice(0, i).split("\n").length} 行：需要以 [ 开始的 JSON 元组。`);
      start = i;
    }
    if (quoted) {
      if (escaped) escaped = false;
      else if (c === "\\") escaped = true;
      else if (c === '"') quoted = false;
      continue;
    }
    if (c === '"') quoted = true;
    else if (c === "[" || c === "{") depth++;
    else if (c === "]" || c === "}") depth--;
    if (depth === 0) {
      const line = text.slice(0, start).split("\n").length;
      try {
        const value: unknown[] = JSON.parse(text.slice(start, i + 1));
        if (value.length && value.every(Array.isArray)) rows.push(...value as unknown[][]);
        else rows.push(value);
      } catch { throw new Error(`第 ${line} 行：JSON 格式错误，请检查引号、逗号和括号。`); }
      start = -1;
    }
  }
  if (start >= 0) throw new Error(`第 ${text.slice(0, start).split("\n").length} 行：字符串或括号未闭合。`);
  return rows;
}

function pointerTokens(path: string): string[] {
  if (!path.startsWith("/")) throw new Error(`数据路径不是 JSON Pointer：${path}`);
  if (path === "/") return [];
  return path.slice(1).split("/").map(token => token.replaceAll("~1", "/").replaceAll("~0", "~"));
}

function setPointer(root: RecordValue, path: string, value: unknown): void {
  const tokens = pointerTokens(path);
  if (!tokens.length) {
    if (!record(value)) throw new Error("根数据路径只能写入对象。");
    Object.assign(root, cloneValue(value));
    return;
  }
  let current: RecordValue | unknown[] = root;
  tokens.forEach((token, index) => {
    const last = index === tokens.length - 1;
    if (Array.isArray(current)) {
      if (!/^\d+$/.test(token)) throw new Error(`数组数据路径索引无效：${path}`);
      const itemIndex = Number(token);
      if (last) {
        current[itemIndex] = cloneValue(value);
        return;
      }
      if (!record(current[itemIndex]) && !Array.isArray(current[itemIndex])) {
        current[itemIndex] = /^\d+$/.test(tokens[index + 1]) ? [] : {};
      }
      current = current[itemIndex] as RecordValue | unknown[];
      return;
    }
    if (last) {
      current[token] = cloneValue(value);
      return;
    }
    if (!record(current[token]) && !Array.isArray(current[token])) {
      current[token] = /^\d+$/.test(tokens[index + 1]) ? [] : {};
    }
    current = current[token] as RecordValue | unknown[];
  });
}

function readPointer(root: RecordValue, path: string): unknown {
  let current: unknown = root;
  for (const token of pointerTokens(path)) {
    if (Array.isArray(current) && /^\d+$/.test(token)) current = current[Number(token)];
    else if (record(current)) current = current[token];
    else return undefined;
  }
  return current;
}

function cloneValue<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

export function compileMiniDsl(
  source: string,
  options: { size?: CardSize; previewMode?: boolean } = {},
) {
  const rows = parseTuples(source);
  let nodes = new Map<string, MiniNode>();
  const data: unknown[][] = [];
  for (const [index, row] of rows.entries()) {
    const [id, type, props = {}, children = []] = row;
    const fail = (reason: string): never => { throw new Error(`第 ${index + 1} 条：${reason}`); };
    if (typeof id !== "string" || !id) fail("组件 ID 或数据路径不能为空。");
    const key = id as string;
    if (key.startsWith("/")) {
      if (row.length !== 2) fail("数据格式应为 [路径, 值]。");
      data.push(row);
      continue;
    }
    if (row.length < 2 || row.length > 4) fail("组件格式应为 [ID, 类型, 属性, 子节点列表]。");
    const normalizedType = typeof type === "string" ? type.replace(/^Extended\./, "") : "";
    const previewSemanticType = options.previewMode && SEMANTIC_LAYOUT_TYPES.has(normalizedType);
    if (!normalizedType || (!TYPES.has(normalizedType) && !previewSemanticType)) {
      fail(`不支持的组件类型：${String(type)}`);
    }
    if (!record(props)) fail("组件属性必须是对象。");
    if (!Array.isArray(children) || !children.every(c => typeof c === "string")) fail("子节点必须是 ID 数组。");
    if (nodes.has(key)) fail(`组件 ID 重复：${key}`);
    nodes.set(key, {
      type: normalizedType,
      props: props as RecordValue,
      children: children as string[],
    });
  }
  if (!nodes.size) throw new Error("DSL 中没有组件。");
  const sourceCount = nodes.size;
  const size = options.size ?? ([...nodes.values()].some(n => typeof n.props.width === "number" && n.props.width >= 240) ? "2x4" : "2x2");
  const initialData: RecordValue = {};
  const warnings = new Set<string>();
  for (const [path, value] of data) setPointer(initialData, String(path), value);
  if (options.previewMode) {
    nodes = expandSemanticLayoutsForPreview(nodes, size, message => warnings.add(message));
  }
  const derivedData: unknown[][] = [];
  nodes = expandCompactComponents(nodes, size, {
    get: path => readPointer(initialData, path),
    setDerived: (path, value) => {
      setPointer(initialData, path, value);
      derivedData.push([path, value]);
    },
    previewMode: options.previewMode,
    warn: message => warnings.add(message),
  });
  const parents = new Map<string, string>();
  for (const [id, node] of nodes) for (const child of node.children) {
    if (!nodes.has(child)) throw new Error(`组件 ${id} 引用了不存在的子节点 ${child}。`);
    if (parents.has(child)) throw new Error(`组件 ${child} 被重复引用。`);
    parents.set(child, id);
  }
  const roots = [...nodes.keys()].filter(id => !parents.has(id));
  if (roots.length !== 1) throw new Error("需要且只能有一个根节点，请检查子节点引用或循环引用。");
  const ordered: string[] = [], visiting = new Set<string>();
  function visit(id: string) {
    if (visiting.has(id)) throw new Error(`组件 ${id} 存在循环引用。`);
    visiting.add(id); ordered.push(id);
    for (const child of nodes.get(id)!.children) visit(child);
    visiting.delete(id);
  }
  visit(roots[0]);
  if (ordered.length !== nodes.size) throw new Error("存在未连接到根节点的循环引用。");
  const messages: RecordValue[] = [{ version: "v0.9", createSurface: { surfaceId: SURFACE_ID, catalogId: "ohos.a2ui.extended.catalog" } }];
  for (const id of ordered) {
    const node = nodes.get(id)!;
    const { styles: nested, onClick, action, ...flat } = node.props;
    const props: RecordValue = { ...(record(nested) ? nested : {}), ...flat };
    const type = node.type === "Input" ? "TextInput" : node.type;
    if (type === "Progress" && props.type === "ring") {
      const width = props.width;
      const height = props.height;
      const validWidth = typeof width === "number" && Number.isFinite(width) && width > 0;
      const validHeight = typeof height === "number" && Number.isFinite(height) && height > 0;
      if (!validWidth || !validHeight) {
        const message = `组件 ${id}：ring Progress 的 width/height 必须是正数。`;
        if (!options.previewMode) throw new Error(message);
        warnings.add(message);
      }
      if (width !== height) {
        const message = `组件 ${id}：ring Progress 的 width/height 必须相等。`;
        if (!options.previewMode) throw new Error(message);
        warnings.add(message);
      }
      if (props.strokeWidth !== undefined && props.strokeWidth !== 6) {
        const message = `组件 ${id}：ring Progress.strokeWidth 必须是 6。`;
        if (!options.previewMode) throw new Error(message);
        warnings.add(message);
      }
      if ("trackColor" in props) {
        const message = `组件 ${id}：ring Progress 使用 backgroundColor，不使用 trackColor。`;
        if (!options.previewMode) throw new Error(message);
        warnings.add(message);
      }
      if ("icon" in props || "externalText" in props) {
        const message = `组件 ${id}：环心图标和环外读数必须使用 Stack/Column 组合。`;
        if (!options.previewMode) throw new Error(message);
        warnings.add(message);
      }
    }
    const { content, label, text, src, value, total, enabled, select, accessibility, ...styleProps } = props;
    // Explicit compact styles are authoritative. Apply legacy presets only when requested.
    const styles = styleProps.design ? applyDesignStyles(type, styleProps) : styleProps;
    const component: RecordValue = { id, component: `Extended.${type}`, styles, ...(node.children.length ? { children: node.children } : {}) };
    for (const [k, v] of Object.entries({ content, label, text, src, value, total, enabled, select, accessibility })) if (v !== undefined) component[k] = v;
    if (onClick !== undefined) {
      if (!Array.isArray(onClick) || !onClick.every(a => record(a) && typeof a.call === "string")) throw new Error(`组件 ${id} 的 onClick 应为 call/args 数组。`);
      component.action = onClick.map(a => ({ functionCall: a }));
    } else if (action !== undefined) component.action = action;
    messages.push({ version: "v0.9", updateComponents: { surfaceId: SURFACE_ID, component } });
  }
  // Apply data after the root: UIGraph resets its data model when a fresh root is installed.
  for (const [path, value] of data) messages.push({ version: "v0.9", updateDataModel: { surfaceId: SURFACE_ID, path, value } });
  for (const [path, value] of derivedData) messages.push({ version: "v0.9", updateDataModel: { surfaceId: SURFACE_ID, path, value } });
  const graph = new UIGraph();
  for (const message of messages) {
    const normalized = tryNormalizeV09Protocol(message);
    if (!normalized) throw new Error("A2UI 转换失败。");
    for (const command of Array.isArray(normalized) ? normalized : [normalized]) graph.applyCommand(command);
  }
  function checkBindings(value: unknown): void {
    if (record(value) && typeof value.path === "string" && Object.keys(value).length === 1) {
      if (graph.getDataModelValue(SURFACE_ID, value.path) === undefined) warnings.add(`未找到数据：${value.path}`);
    } else if (typeof value === "string" && value.startsWith("{{") && value.endsWith("}}")) {
      const parsed = parseExpression(value.slice(2, -2));
      for (const path of parsed.paths) if (graph.getDataModelValue(SURFACE_ID, path) === undefined) warnings.add(`未找到数据：${path}`);
      parsed.evaluate(path => graph.getDataModelValue(SURFACE_ID, path));
    } else if (Array.isArray(value)) value.forEach(checkBindings);
    else if (record(value)) Object.values(value).forEach(checkBindings);
  }
  for (const [id, node] of nodes) {
    try {
      checkBindings(node.props);
      const resolved = resolvePathBindingsInValue(node.props, path => graph.getDataModelValue(SURFACE_ID, path)) as RecordValue;
      if (node.type === "Progress") {
        const total = resolved.total ?? 100;
        if (typeof resolved.value !== "number" || !Number.isFinite(resolved.value) || typeof total !== "number" || !Number.isFinite(total) || total <= 0 || resolved.value < 0 || resolved.value > total) throw new Error("Progress.value 必须是 0 到 total 之间的有限数值，不能使用百分比字符串。");
      }
      if (resolved.enabled !== undefined && typeof resolved.enabled !== "boolean") throw new Error("enabled 必须解析为 boolean。");
    } catch (error) {
      const message = `组件 ${id}：${error instanceof Error ? error.message : String(error)}`;
      if (!options.previewMode) throw new Error(message);
      warnings.add(message);
    }
  }
  return { graph, jsonl: messages.map(m => JSON.stringify(m)).join("\n"), warnings: [...warnings], count: sourceCount, expandedCount: nodes.size, size };
}
