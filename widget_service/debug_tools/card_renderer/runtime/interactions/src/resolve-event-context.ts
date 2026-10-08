/**
 * Resolves `action.event.context` at trigger time: `{"path":"…"}`, `getSelectedValues`, nested objects/arrays.
 * See `skills/a2ui/reference/protocol/extended-interactions.md`.
 */
import { isPathOnlyBinding, resolvePathBindingsInValue } from "./resolve-path-bindings.js";

function isRecord(x: unknown): x is Record<string, unknown> {
  return typeof x === "object" && x !== null && !Array.isArray(x);
}

export function isGetSelectedValuesBinding(
  v: unknown,
): v is { call: "getSelectedValues"; args: { groupID: string } } {
  if (!isRecord(v)) return false;
  if (v.call !== "getSelectedValues") return false;
  const args = v.args;
  if (!isRecord(args)) return false;
  return typeof args.groupID === "string" && args.groupID.length > 0;
}

export type EventContextResolvers = {
  getDataModelLeaf: (path: string) => unknown;
  /** Current selected value for the radio group (same `group` / `groupID` on `Extended.Radio`). */
  getSelectedGroupValue: (groupID: string) => string;
};

/**
 * Recursively resolves every value in a JSON-like structure (object keys, array items).
 */
export function resolveEventContextValue(value: unknown, r: EventContextResolvers): unknown {
  if (typeof value === "string") return resolvePathBindingsInValue(value, r.getDataModelLeaf);
  if (isPathOnlyBinding(value)) {
    const got = r.getDataModelLeaf(value.path);
    if (got === undefined || got === null) return "";
    return got;
  }
  if (isGetSelectedValuesBinding(value)) {
    return r.getSelectedGroupValue(value.args.groupID);
  }
  if (Array.isArray(value)) {
    return value.map((v) => resolveEventContextValue(v, r));
  }
  if (isRecord(value)) {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value)) {
      out[k] = resolveEventContextValue(v, r);
    }
    return out;
  }
  return value;
}
