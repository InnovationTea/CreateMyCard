/**
 * v0.9 JSONL protocol: `createSurface`, `updateComponents`, and optional `updateDataModel`
 * (see skills/a2ui/reference/protocol/extended-updateDataModel.md).
 *
 * This repo historically used **one component per JSON object**:
 *   `{ "version":"v0.9", "updateComponents": { "surfaceId": "...", "component": { ... } } }`
 *
 * Some producers emit **batch updates**:
 *   `{ "version":"v0.9", "updateComponents": { "surfaceId": "...", "components": [ { ... }, ... ] } }`
 *
 * Both are accepted and normalized to classic UIGraph single-key commands.
 */

const V09 = "v0.9";

const DYNAMIC_CHILDREN_TEMPLATE_COMPONENTS = new Set<string>([
  "Extended.List",
  "Extended.Tabs",
  "Extended.Navigation",
  "List",
  "Tabs",
  "Navigation",
]);

export const CREATE_SURFACE_KEY = "__createSurface";

/** Normalized graph command key for v0.9 `updateDataModel` (A2UI extended; not used by mini protocol). */
export const UPDATE_DATA_MODEL_KEY = "__updateDataModel";

/** Minimal GenUI / A2UI `deleteSurface` → graph clears the active surface tree. */
export const DELETE_SURFACE_KEY = "__deleteSurface";

export function isV09CreateSurfaceCommand(
  cmd: Record<string, unknown>,
): cmd is { [CREATE_SURFACE_KEY]: { surfaceId: string } } {
  const inner = cmd[CREATE_SURFACE_KEY];
  return (
    Object.keys(cmd).length === 1 &&
    typeof inner === "object" &&
    inner !== null &&
    !Array.isArray(inner) &&
    typeof (inner as { surfaceId?: unknown }).surfaceId === "string"
  );
}

/**
 * If `value` is a v0.9 protocol message, returns one (or many) UIGraph command(s).
 * - `createSurface` → `{ __createSurface: { surfaceId } }` (graph resets surface)
 * - `updateComponents` → `{ [id]: { type, props, children? } }` (single or batch)
 * - `updateDataModel` → `{ __updateDataModel: { surfaceId, path?, value? } }`
 */
export function tryNormalizeV09Protocol(
  value: unknown,
): Record<string, unknown> | Record<string, unknown>[] | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  const o = value as Record<string, unknown>;
  if (o.version !== V09) return null;

  const nKinds =
    (o.createSurface !== undefined ? 1 : 0) +
    (o.updateComponents !== undefined ? 1 : 0) +
    (o.updateDataModel !== undefined ? 1 : 0);
  if (nKinds > 1) return null;

  if (o.createSurface !== undefined) {
    if (typeof o.createSurface !== "object" || o.createSurface === null || Array.isArray(o.createSurface)) {
      return null;
    }
    const cs = o.createSurface as { surfaceId?: unknown };
    if (typeof cs.surfaceId !== "string") return null;
    return { [CREATE_SURFACE_KEY]: { surfaceId: cs.surfaceId } };
  }

  if (o.updateComponents !== undefined) {
    if (typeof o.updateComponents !== "object" || o.updateComponents === null || Array.isArray(o.updateComponents)) {
      return null;
    }
    const uc = o.updateComponents as {
      surfaceId?: unknown;
      component?: unknown;
      components?: unknown;
    };
    if (typeof uc.surfaceId !== "string") return null;

    const normalizeOne = (comp: unknown): Record<string, unknown> | null => {
      if (typeof comp !== "object" || comp === null || Array.isArray(comp)) return null;
      const c = comp as Record<string, unknown>;
      const nodeId = c.id;
      const compName = c.component;
      if (typeof nodeId !== "string" || typeof compName !== "string") return null;

      const props: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(c)) {
        if (k === "id" || k === "component" || k === "children") continue;
        props[k] = v;
      }

      const node: Record<string, unknown> = {
        type: compName,
        props,
      };
      const staticChildrenOk = Array.isArray(c.children) && c.children.every((x) => typeof x === "string");
      const templObj =
        typeof c.children === "object" &&
        c.children !== null &&
        !Array.isArray(c.children)
          ? (c.children as Record<string, unknown>)
          : null;
      const templPathsOk =
        templObj !== null &&
        typeof templObj.path === "string" &&
        templObj.path.length > 0 &&
        typeof templObj.componentId === "string" &&
        String(templObj.componentId).length > 0;

      if (staticChildrenOk) {
        node.children = c.children as string[];
      } else if (templPathsOk && templObj !== null && DYNAMIC_CHILDREN_TEMPLATE_COMPONENTS.has(compName)) {
        node.dynamicChildrenTemplate = {
          path: templObj.path as string,
          componentId: templObj.componentId as string,
        };
      }

      return { [nodeId]: node };
    };

    // Single component (legacy / streaming friendly)
    if (uc.component !== undefined) {
      return normalizeOne(uc.component);
    }

    // Batch components (producer convenience)
    if (Array.isArray(uc.components)) {
      const out: Record<string, unknown>[] = [];
      for (const comp of uc.components) {
        const cmd = normalizeOne(comp);
        if (cmd === null) return null;
        out.push(cmd);
      }
      return out;
    }

    return null;
  }

  if (o.updateDataModel !== undefined) {
    const topKeys = Object.keys(o).filter((k) => k !== "version");
    if (topKeys.length !== 1 || topKeys[0] !== "updateDataModel") return null;
    if (typeof o.updateDataModel !== "object" || o.updateDataModel === null || Array.isArray(o.updateDataModel)) {
      return null;
    }
    const dm = o.updateDataModel as { surfaceId?: unknown; path?: unknown; value?: unknown };
    if (typeof dm.surfaceId !== "string") return null;
    if (dm.path !== undefined && typeof dm.path !== "string") return null;
    const payload: { surfaceId: string; path?: string; value?: unknown } = { surfaceId: dm.surfaceId };
    if (typeof dm.path === "string") payload.path = dm.path;
    if (Object.prototype.hasOwnProperty.call(dm, "value")) payload.value = dm.value;
    return { [UPDATE_DATA_MODEL_KEY]: payload };
  }

  return null;
}
