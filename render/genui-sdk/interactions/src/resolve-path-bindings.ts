import { evaluateExpression } from "./expression.js";

/**
 * A2UI `{"path":"..."}` data-binding (v0.9 `updateDataModel`).
 * Used for component props, `action.functionCall.args`, and `action.event.context` (e.g. `submit_form`) at click time.
 */
export function isPathOnlyBinding(v: unknown): v is { path: string } {
  if (typeof v !== "object" || v === null || Array.isArray(v)) return false;
  const o = v as Record<string, unknown>;
  const keys = Object.keys(o);
  return keys.length === 1 && keys[0] === "path" && typeof o.path === "string";
}

/**
 * Resolves path leaves with `getLeaf` (e.g. `graph.getDataModelValue(surfaceId, path)`).
 * `undefined` / `null` from `getLeaf` become `""` (match reference renderer for props).
 */
export function resolvePathBindingsInValue(
  value: unknown,
  getLeaf: (path: string) => unknown,
): unknown {
  if (typeof value === "string") {
    const full = value.match(/^\{\{\s*([\s\S]*?)\s*\}\}$/);
    if (full) return evaluateExpression(full[1], getLeaf);
    // Match the reference web renderer without evaluating JavaScript expressions.
    return value.replace(/\{\{\s*\$\{([^}]+)\}\s*(?:\+\s*(['"])(.*?)\2)?\s*\}\}/g,
      (_match, path: string, _quote: string, suffix: string) => {
        const resolved = getLeaf(path.trim());
        return `${resolved == null ? "" : typeof resolved === "object" ? JSON.stringify(resolved) : String(resolved)}${suffix ?? ""}`;
      });
  }
  if (isPathOnlyBinding(value)) {
    const got = getLeaf(value.path);
    if (got === undefined || got === null) return "";
    return got;
  }
  if (Array.isArray(value)) {
    return value.map((v) => resolvePathBindingsInValue(v, getLeaf));
  }
  if (value && typeof value === "object") {
    const o = value as Record<string, unknown>;
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(o)) {
      out[k] = resolvePathBindingsInValue(v, getLeaf);
    }
    return out;
  }
  return value;
}
