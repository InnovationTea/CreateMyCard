/**
 * UIGraph
 *
 * Incrementally builds a UI tree from a stream of parsed JSONL commands.
 *
 * Each command is a single-key object:
 * - **v0.9 createSurface** (from parser): `{ "__createSurface": { surfaceId } }` — clears the graph (new surface).
 * - **v0.9 deleteSurface** (minimal GenUI / A2UI): `{ "__deleteSurface": { surfaceId } }` — {@link UIGraph.resetAll} (clears tree + data model; clears active surface id).
 * - **v0.9 updateDataModel** (A2UI extended): `{ "__updateDataModel": { surfaceId, path?, value? } }` — stores a
 *   JSON Pointer-style key → value for that surface. {@link UIGraph.getDataModelValue} resolves bindings: exact
 *   key first, otherwise the longest stored prefix path then walks arrays/objects (RFC 6901 segment rules).
 * - **Full node**: `{ "<id>": { type, props?, children? } }` — creates or replaces a node.
 *   If `children` is **omitted**, an **existing** non-root node keeps its current child id list; a **new** node
 *   gets `[]`. If `children` is **present** (including `[]`), the list replaces the previous one and removed
 *   subtrees are deleted.
 * - **Props patch** (multi-turn): `{ "<id>": { props: { ... } } }` — merges into existing `props` (no `type`).
 * - **Children patch**: `{ "<id>": { children: [...] } }` — replaces child id list; removed subtrees are deleted (no `type`).
 *
 * **Fresh scene**: command for `id === "root"` that includes `type` clears the graph first, then builds anew.
 */

/** Allowed `componentId` repeats for paths that resolve to arrays (v0.9 `children` object — see parser). */
export type DynamicChildrenTemplate = {
  /** Data model pointer to an array value (RFC 6901 style, normalized with leading `/`). */
  path: string;
  /** Subtree root node id replicated for each element. */
  componentId: string;
};

export interface UINode {
  id: string;
  type: string;
  props: Record<string, unknown>;
  /** Child node IDs in declaration order. */
  children: string[];
  /** When set on List / Tabs / Navigation, `children` is empty and templates are rendered at {@link DynamicChildrenTemplate.path}. */
  dynamicChildrenTemplate?: DynamicChildrenTemplate | undefined;
  /** Parent node ID, or null for the root. */
  parent: string | null;
}

interface RawNodeDef {
  type?: string;
  props?: Record<string, unknown>;
  children?: string[];
  dynamicChildrenTemplate?: DynamicChildrenTemplate;
}

/** v0.9 `children: { path, componentId }` is only defined for these types. */
const DYNAMIC_TEMPLATE_COMPONENT_TYPES = new Set<string>([
  "Extended.List",
  "Extended.Tabs",
  "Extended.Navigation",
  "List",
  "Tabs",
  "Navigation",
]);

function normalizeDataModelPathSegmentPath(path: string): string {
  const p = path.trim();
  if (p.length === 0) return "/";
  return p.startsWith("/") ? p : `/${p}`;
}

function isDynamicChildrenTemplateValue(
  v: unknown,
): v is DynamicChildrenTemplate {
  if (typeof v !== "object" || v === null || Array.isArray(v)) return false;
  const o = v as Record<string, unknown>;
  return (
    typeof o.path === "string" &&
    o.path.trim().length > 0 &&
    typeof o.componentId === "string" &&
    String(o.componentId).length > 0
  );
}

/** Internal key emitted by v0.9 `createSurface` normalization (parser → graph). */
export const CREATE_SURFACE_CMD_KEY = "__createSurface";

/** Internal key emitted by v0.9 `updateDataModel` normalization (A2UI extended). */
export const UPDATE_DATA_MODEL_CMD_KEY = "__updateDataModel";

/** Internal key for minimal `deleteSurface` (`~surfaceId` tuple). */
export const DELETE_SURFACE_CMD_KEY = "__deleteSurface";

/** Decode one JSON Pointer path token (`~1` → `/`, `~0` → `~`). */
function decodeJsonPointerSegment(segment: string): string {
  return segment.replace(/~1/g, "/").replace(/~0/g, "~");
}

function traverseDataModelBySegments(root: unknown, segments: string[]): unknown {
  let cur: unknown = root;
  for (const raw of segments) {
    const seg = decodeJsonPointerSegment(raw);
    if (cur === null || cur === undefined) return undefined;
    if (Array.isArray(cur)) {
      if (!/^\d+$/.test(seg)) return undefined;
      const i = Number(seg);
      if (!Number.isInteger(i) || i < 0 || i >= cur.length) return undefined;
      cur = cur[i];
    } else if (typeof cur === "object") {
      if (!Object.prototype.hasOwnProperty.call(cur, seg)) return undefined;
      cur = (cur as Record<string, unknown>)[seg];
    } else {
      return undefined;
    }
  }
  return cur;
}

/** Copy-on-write JSON Pointer updates keep parent objects and leaf bindings in sync. */
function writeDataModelPath(current: unknown, path: string, value: unknown): unknown {
  if (path === "/" || path === "") return value;
  const segments = path.replace(/^\//, "").split("/").map(decodeJsonPointerSegment);
  function write(node: unknown, index: number): unknown {
    if (index === segments.length) return value;
    const key = segments[index];
    const container: Record<string, unknown> | unknown[] = Array.isArray(node) ? [...node]
      : node && typeof node === "object" ? { ...node }
      : /^\d+$/.test(key) ? [] : {};
    const previous = node && typeof node === "object" && Object.prototype.hasOwnProperty.call(node, key) ? (node as Record<string, unknown>)[key] : undefined;
    Object.defineProperty(container, key, { value: write(previous, index + 1), enumerable: true, configurable: true, writable: true });
    return container;
  }
  return write(current, 0);
}

/**
 * Longest map key `k` such that `queryPath` is exactly `k` or extends `k` at a JSON Pointer segment boundary.
 *
 * Non-root: `queryPath.startsWith(k + "/")` (e.g. `/card/title` under `/card`).
 * Root `k === "/"`: children are `/a`, `/b/c`, etc. — **not** `//a` (so we must not use `k + "/"` which becomes `"//"`).
 */
function longestDataModelPrefixKey(model: Map<string, unknown>, queryPath: string): string | null {
  let best: string | null = null;
  for (const k of model.keys()) {
    let isPrefix = false;
    if (queryPath === k) {
      isPrefix = true;
    } else if (k === "/") {
      isPrefix = queryPath.length > 1 && queryPath.startsWith("/");
    } else {
      isPrefix = queryPath.startsWith(`${k}/`);
    }
    if (isPrefix && (best === null || k.length > best.length)) best = k;
  }
  return best;
}

export class UIGraph {
  /** All nodes indexed by ID. */
  private readonly nodes = new Map<string, UINode>();

  /**
   * Per-surface data model: JSON Pointer-style path string → value (from `updateDataModel` lines).
   */
  private readonly dataModelBySurface = new Map<string, Map<string, unknown>>();

  /** Last `surfaceId` from a v0.9 `createSurface` command (for binding resolution when hosts use one surface). */
  private activeSurfaceId: string | null = null;

  /**
   * Populated when a parent command is processed ahead of its children.
   * Maps childId → parentId so that `parent` can be set when the child
   * command arrives.
   */
  private readonly pendingParents = new Map<string, string>();

  /** ID of the first node added — this is the root of the tree. */
  private rootId: string | null = null;

  /**
   * Apply one parsed JSONL command to the graph.
   *
   * @param cmd - A plain object with exactly one key: the node ID.
   */
  applyCommand(cmd: Record<string, unknown>): void {
    const entries = Object.entries(cmd);
    if (entries.length === 0) return;

    const [id, raw] = entries[0]!;

    if (id === CREATE_SURFACE_CMD_KEY && typeof raw === "object" && raw !== null && !Array.isArray(raw)) {
      const surfaceId = (raw as { surfaceId?: unknown }).surfaceId;
      if (typeof surfaceId === "string") {
        this.resetAll();
        this.activeSurfaceId = surfaceId;
      }
      return;
    }

    if (id === DELETE_SURFACE_CMD_KEY && typeof raw === "object" && raw !== null && !Array.isArray(raw)) {
      const surfaceId = (raw as { surfaceId?: unknown }).surfaceId;
      if (typeof surfaceId === "string") {
        this.resetAll();
      }
      return;
    }

    if (id === UPDATE_DATA_MODEL_CMD_KEY && typeof raw === "object" && raw !== null && !Array.isArray(raw)) {
      const surfaceId = (raw as { surfaceId?: unknown }).surfaceId;
      const path = (raw as { path?: unknown }).path;
      if (typeof surfaceId !== "string" || typeof path !== "string" || path.length === 0) {
        return;
      }
      const value = Object.prototype.hasOwnProperty.call(raw, "value")
        ? (raw as { value: unknown }).value
        : undefined;
      let m = this.dataModelBySurface.get(surfaceId);
      if (!m) {
        m = new Map<string, unknown>();
        this.dataModelBySurface.set(surfaceId, m);
      }
      const model = writeDataModelPath(m.get("/"), path, value);
      m.clear();
      m.set("/", model);
      return;
    }

    const def = raw as RawNodeDef;

    const hasType = typeof def.type === "string" && def.type.length > 0;
    const hasPropsKey =
      Object.prototype.hasOwnProperty.call(def, "props") &&
      def.props !== undefined &&
      typeof def.props === "object" &&
      def.props !== null &&
      !Array.isArray(def.props);
    const hasChildrenKey = Object.prototype.hasOwnProperty.call(def, "children");
    const childrenExplicit = hasChildrenKey && Array.isArray(def.children);
    const childrenList = childrenExplicit ? (def.children as string[]) : undefined;
    const hasDynamicChildrenKey = Object.prototype.hasOwnProperty.call(def, "dynamicChildrenTemplate");

    if (hasType) {
      this.applyFullNode(id, def, hasDynamicChildrenKey, childrenExplicit, childrenList);
      return;
    }

    // Incremental: no type
    const node = this.nodes.get(id);
    if (!node) return;

    if (hasPropsKey) {
      node.props = { ...node.props, ...(def.props as Record<string, unknown>) };
    }

    if (hasChildrenKey && childrenList !== undefined) {
      this.replaceChildren(id, node, childrenList as string[]);
    }

    if (hasDynamicChildrenKey && !(hasChildrenKey && childrenList !== undefined)) {
      const tpl = def.dynamicChildrenTemplate;
      if (
        tpl !== undefined &&
        isDynamicChildrenTemplateValue(tpl) &&
        DYNAMIC_TEMPLATE_COMPONENT_TYPES.has(node.type)
      ) {
        for (const oc of [...node.children]) {
          this.removeSubtree(oc);
        }
        node.children = [];
        node.dynamicChildrenTemplate = {
          path: normalizeDataModelPathSegmentPath(tpl.path),
          componentId: tpl.componentId,
        };
      }
    }
  }

  private applyFullNode(
    id: string,
    def: RawNodeDef,
    hasDynamicChildrenKey: boolean,
    childrenExplicit: boolean,
    childrenList: string[] | undefined,
  ): void {
    let children: string[];
    let dynamicChildrenTemplate: DynamicChildrenTemplate | undefined;
    let parent: string | null = null;

    const type = def.type!;
    const explicitTemplate =
      hasDynamicChildrenKey &&
      isDynamicChildrenTemplateValue(def.dynamicChildrenTemplate) &&
      DYNAMIC_TEMPLATE_COMPONENT_TYPES.has(type)
        ? {
            path: normalizeDataModelPathSegmentPath(def.dynamicChildrenTemplate!.path),
            componentId: def.dynamicChildrenTemplate!.componentId,
          }
        : undefined;

    if (id === "root") {
      // Fresh scene: clear tree + bound data, but keep v0.9 `activeSurfaceId` so A2UI bindings still resolve.
      this.resetGraphStructureAndDataModel();
      if (childrenExplicit && childrenList !== undefined) {
        children = [...childrenList];
        dynamicChildrenTemplate = undefined;
      } else if (explicitTemplate) {
        children = [];
        dynamicChildrenTemplate = explicitTemplate;
      } else {
        children = [];
        dynamicChildrenTemplate = undefined;
      }
    } else {
      const existing = this.nodes.get(id);
      if (existing) {
        parent = existing.parent;
        if (childrenExplicit && childrenList !== undefined) {
          children = [...childrenList];
          dynamicChildrenTemplate = undefined;
          for (const oc of existing.children) {
            if (!children.includes(oc)) {
              this.removeSubtree(oc);
            }
          }
        } else if (explicitTemplate) {
          for (const oc of existing.children) {
            this.removeSubtree(oc);
          }
          children = [];
          dynamicChildrenTemplate = explicitTemplate;
        } else {
          children = [...existing.children];
          dynamicChildrenTemplate = existing.dynamicChildrenTemplate;
        }
      } else {
        parent = this.pendingParents.get(id) ?? null;
        if (childrenExplicit && childrenList !== undefined) {
          children = [...childrenList];
          dynamicChildrenTemplate = undefined;
        } else if (explicitTemplate) {
          children = [];
          dynamicChildrenTemplate = explicitTemplate;
        } else {
          children = [];
          dynamicChildrenTemplate = undefined;
        }
      }
    }

    const node: UINode = {
      id,
      type,
      props:
        def.props !== undefined &&
        typeof def.props === "object" &&
        def.props !== null &&
        !Array.isArray(def.props)
          ? { ...(def.props as Record<string, unknown>) }
          : {},
      children,
      dynamicChildrenTemplate,
      parent,
    };

    this.nodes.set(id, node);
    this.pendingParents.delete(id);

    for (const childId of children) {
      this.pendingParents.set(childId, id);
      const ch = this.nodes.get(childId);
      if (ch) ch.parent = id;
    }

    if (this.rootId === null) {
      this.rootId = id;
    }
  }

  private replaceChildren(parentId: string, parent: UINode, newChildren: string[]): void {
    const old = [...parent.children];
    parent.children = [...newChildren];
    parent.dynamicChildrenTemplate = undefined;

    for (const oc of old) {
      if (!newChildren.includes(oc)) {
        this.removeSubtree(oc);
      }
    }

    for (const cid of newChildren) {
      this.pendingParents.set(cid, parentId);
      const ch = this.nodes.get(cid);
      if (ch) ch.parent = parentId;
    }
  }

  /** Removes a node and all descendants; cleans pendingParents. */
  removeSubtree(id: string): void {
    const node = this.nodes.get(id);
    if (!node) return;
    for (const childId of [...node.children]) {
      this.removeSubtree(childId);
    }
    this.nodes.delete(id);
    this.pendingParents.delete(id);
    if (this.rootId === id) {
      this.rootId = null;
    }
  }

  // ── Accessors ────────────────────────────────────────────────────────────

  getRoot(): UINode | null {
    return this.rootId ? (this.nodes.get(this.rootId) ?? null) : null;
  }

  getNode(id: string): UINode | null {
    return this.nodes.get(id) ?? null;
  }

  getAllNodes(): ReadonlyMap<string, UINode> {
    return this.nodes;
  }

  get size(): number {
    return this.nodes.size;
  }

  getPendingChildIds(): string[] {
    return Array.from(this.pendingParents.keys());
  }

  /** Surface id from the latest v0.9 `createSurface`, or null if none yet. */
  getActiveSurfaceId(): string | null {
    return this.activeSurfaceId;
  }

  /**
   * Returns the value for `path` on `surfaceId`, or `undefined` if missing.
   *
   * Lookup order:
   * 1. Exact key in the surface model map (legacy flat patches, e.g. `/card/title`).
   * 2. Otherwise the **longest** stored key `k` that prefixes `path` at a segment boundary (see
   *    {@link longestDataModelPrefixKey}), then walk the remainder as JSON Pointer segments through objects
   *    and numeric indices through arrays. For root `k === "/"`, the remainder is `path.slice(1)` (RFC 6901),
   *    not `path.slice(2)` — the latter would drop the first character of the first segment.
   */
  getDataModelValue(surfaceId: string, path: string): unknown {
    const m = this.dataModelBySurface.get(surfaceId);
    if (!m) return undefined;
    if (m.has(path)) return m.get(path);
    const prefix = longestDataModelPrefixKey(m, path);
    if (prefix === null) return undefined;
    const rest =
      prefix === "/" ? (path.length <= 1 ? "" : path.slice(1)) : path.slice(prefix.length + 1);
    const segments = rest.length === 0 ? [] : rest.split("/").filter((s) => s.length > 0);
    const base = m.get(prefix);
    return traverseDataModelBySegments(base, segments);
  }

  /**
   * Writes a value at `path` for `surfaceId` (same semantics as v0.9 `updateDataModel` in the stream).
   * Hosts (e.g. the renderer) use this for two-way `{"path":"…"}` bindings on inputs.
   */
  setDataModelValue(surfaceId: string, path: string, value: unknown): void {
    this.applyCommand({
      [UPDATE_DATA_MODEL_CMD_KEY]: { surfaceId, path, value },
    } as Record<string, unknown>);
  }

  /** Clears nodes, data model, and v0.9 active surface (used by `createSurface` after a new `resetAll`). */
  resetAll(): void {
    this.resetGraphStructureAndDataModel();
    this.activeSurfaceId = null;
  }

  /**
   * Clears the entire graph including data bindings context.
   * Prefer {@link resetAll} for new naming; behavior is identical.
   */
  reset(): void {
    this.resetAll();
  }

  /** Clears nodes, pending parents, root id, and per-surface data model; preserves {@link getActiveSurfaceId}. */
  private resetGraphStructureAndDataModel(): void {
    this.nodes.clear();
    this.pendingParents.clear();
    this.rootId = null;
    this.dataModelBySurface.clear();
  }
}

// ── Serialisation helper ─────────────────────────────────────────────────────

/** How to serialize `props` when building LLM context (token cost vs. fidelity). */
export type UITreePropsMode = "omit" | "truncate" | "full";

export interface UITreeJsonOptions {
  /** `JSON.stringify` space argument; `0` = single line. Default `0`. */
  indent?: number;
  /**
   * - `omit`: only `type` and `children` per node (default — minimal tokens).
   * - `truncate`: include `props` but shorten long strings (e.g. `content`, `label`).
   * - `full`: full `props` (legacy / debugging).
   */
  propsMode?: UITreePropsMode;
  /** Max string length in `props` when `propsMode` is `truncate`. Default `80`. */
  maxStringPropLen?: number;
}

function truncateJsonStrings(value: unknown, maxLen: number): unknown {
  if (typeof value === "string") {
    return value.length > maxLen ? `${value.slice(0, maxLen)}…` : value;
  }
  if (Array.isArray(value)) {
    return value.map((v) => truncateJsonStrings(v, maxLen));
  }
  if (value && typeof value === "object") {
    const o = value as Record<string, unknown>;
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(o)) {
      out[k] = truncateJsonStrings(v, maxLen);
    }
    return out;
  }
  return value;
}

function serializeNodeProps(
  props: Record<string, unknown>,
  mode: UITreePropsMode,
  maxLen: number,
): Record<string, unknown> | undefined {
  if (mode === "omit") return undefined;
  if (mode === "full") return Object.keys(props).length > 0 ? { ...props } : undefined;
  const t = truncateJsonStrings(props, maxLen) as Record<string, unknown>;
  return Object.keys(t).length > 0 ? t : undefined;
}

/**
 * Converts a UIGraph to a flat JSON object keyed by node ID.
 *
 * Each entry has `type` and `children` (child ids in order). `props` are included
 * only when `propsMode` is `truncate` or `full` (see {@link UITreeJsonOptions}).
 * The `parent` field is never emitted.
 *
 * @param optionsOrIndent - Pass a **number** for legacy behavior: that indent + **full** props.
 *   Omit or pass {@link UITreeJsonOptions} for compact defaults (`indent: 0`, `propsMode: "omit"`).
 */
export function uitreeJson(graph: UIGraph, optionsOrIndent?: UITreeJsonOptions | number): string {
  const opts: UITreeJsonOptions =
    typeof optionsOrIndent === "number"
      ? { indent: optionsOrIndent, propsMode: "full" }
      : { indent: 0, propsMode: "omit", maxStringPropLen: 80, ...optionsOrIndent };

  const indent = opts.indent ?? 0;
  const propsMode = opts.propsMode ?? "omit";
  const maxLen = opts.maxStringPropLen ?? 80;

  const out: Record<string, unknown> = {};

  const root = graph.getRoot();
  const ordered: UINode[] = root ? [root] : [];
  for (const node of graph.getAllNodes().values()) {
    if (node !== root) ordered.push(node);
  }

  for (const node of ordered) {
    const propsObj = serializeNodeProps(node.props, propsMode, maxLen);
    const entry: Record<string, unknown> = {
      type: node.type,
      children: node.children,
    };
    if (node.dynamicChildrenTemplate !== undefined) {
      entry.dynamicChildrenTemplate = node.dynamicChildrenTemplate;
    }
    if (propsObj !== undefined) {
      entry.props = propsObj;
    }
    out[node.id] = entry;
  }

  return JSON.stringify(out, null, indent === 0 ? undefined : indent);
}
