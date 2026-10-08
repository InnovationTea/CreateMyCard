import { UIGraph } from "@genui-sdk/graph";
import { tryNormalizeV09Protocol } from "@genui-sdk/parser";
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
  ..."Card Row Column Text Image Button ActionUnit CardHeader TimelineUnit Input TextInput Radio Checkbox CheckboxGroup Select Toggle Progress Divider Grid GridRow List Stack Tabs TabContent Web Navigation".split(" "),
  ...HIGH_LEVEL_COMPONENT_TYPES,
]);

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
      } catch (error) {
        const reason = error instanceof Error ? error.message : String(error);
        const snippet = text.slice(start, i + 1).slice(0, 120);
        throw new Error(
          `第 ${line} 行：JSON 格式错误，请检查引号、逗号和括号（${reason}）：${snippet}`,
        );
      }
      start = -1;
    }
  }
  if (start >= 0) throw new Error(`第 ${text.slice(0, start).split("\n").length} 行：字符串或括号未闭合。`);
  return rows;
}

export function compileMiniDsl(source: string, options: { size?: CardSize } = {}) {
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
    if (typeof type !== "string" || !TYPES.has(type.replace(/^Extended\./, ""))) fail(`不支持的组件类型：${String(type)}`);
    if (!record(props)) fail("组件属性必须是对象。");
    if (!Array.isArray(children) || !children.every(c => typeof c === "string")) fail("子节点必须是 ID 数组。");
    if (nodes.has(key)) fail(`组件 ID 重复：${key}`);
    nodes.set(key, { type: (type as string).replace(/^Extended\./, ""), props: props as RecordValue, children: children as string[] });
  }
  if (!nodes.size) throw new Error("DSL 中没有组件。");
  const sourceCount = nodes.size;
  const size = options.size ?? ([...nodes.values()].some(n => typeof n.props.width === "number" && n.props.width >= 240) ? "2x4" : "2x2");
  nodes = expandCompactComponents(nodes, size);
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
  const warnings = new Set<string>();
  for (const id of ordered) {
    const node = nodes.get(id)!;
    const { styles: nested, onClick, action, ...flat } = node.props;
    const props: RecordValue = { ...(record(nested) ? nested : {}), ...flat };
    const type = node.type === "Input" ? "TextInput" : node.type;
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
    } catch (error) { throw new Error(`组件 ${id}：${error instanceof Error ? error.message : String(error)}`); }
  }
  return { graph, jsonl: messages.map(m => JSON.stringify(m)).join("\n"), warnings: [...warnings], count: sourceCount, expandedCount: nodes.size, size };
}
