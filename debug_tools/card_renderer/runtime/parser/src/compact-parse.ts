/**
 * Compact line format (token-saving JSONL), parsed by a small state machine.
 *
 * **Legacy mini tuple** (after first `"<id>"`, type / props / children in any order, each at most once):
 * - `{ id: { type, props?, children? } }` or patch lines.
 *
 * **Implicit brace tuple** (`mini-tuple-to-graph.ts`): comma-separated values in `{ … }` where
 * theme/props may omit inner `{ }` (`"k":v`), for sloppy model output — tried first.
 *
 * **Minimal GenUI** (see `skills/compact`):
 * - `createSurface` — `{"@<surfaceId>", "<catalogId>", { theme? }, sendDataModel? }`
 * - `updateDataModel` — `{"<surfaceId>", "/path", <json value> }` (value optional for delete)
 * - `deleteSurface` — `{"~<surfaceId>"}` (single string segment)
 * - `updateComponent` — `{"<surfaceId>", "<componentId>", "<Type>", { props }?, [ children ]? }`
 *
 * `parseCompactLine` returns **UIGraph** single-key command objects, including
 * `{ __createSurface }`, `{ __updateDataModel }`, `{ __deleteSurface }` (see `genui-sdk/graph`)
 * and `{ [componentId]: { type, props, children? } }`.
 */

import {
  CREATE_SURFACE_KEY,
  DELETE_SURFACE_KEY,
  UPDATE_DATA_MODEL_KEY,
} from "./protocol-v09.js";
import { tryParseMiniTupleBraceLineToGraphCommand } from "./mini-tuple-to-graph.js";

/** Remove trailing commas before `}` or `]` — models often emit invalid strict JSON. */
export function stripTrailingCommasInJsonText(s: string): string {
  let out = s.trim();
  let prev = "";
  while (out !== prev) {
    prev = out;
    out = out.replace(/,(\s*[}\]])/g, "$1");
  }
  return out;
}

function tryParseJsonValue(slice: string): unknown {
  const t = slice.trim();
  try {
    return JSON.parse(t);
  } catch {
    return JSON.parse(stripTrailingCommasInJsonText(t));
  }
}

export function skipWs(s: string, start: number): number {
  let i = start;
  while (i < s.length && /\s/.test(s[i]!)) i++;
  return i;
}

export function isComma(s: string, i: number): boolean {
  const c = s[i];
  return c === "," || c === "\uFF0C";
}

/** Parse a JSON string literal starting at `"`; returns value and index after closing `"`. */
export function parseJsonStringLiteral(
  s: string,
  start: number,
): { value: string; end: number } | null {
  if (s[start] !== '"') return null;
  let i = start + 1;
  let escape = false;
  for (; i < s.length; i++) {
    const c = s[i]!;
    if (escape) {
      escape = false;
      continue;
    }
    if (c === "\\") {
      escape = true;
      continue;
    }
    if (c === '"') {
      try {
        const value = JSON.parse(s.slice(start, i + 1)) as string;
        return { value, end: i + 1 };
      } catch {
        return null;
      }
    }
  }
  return null;
}

const JSON_BRACKET_PAIR: Record<string, string> = {
  "{": "}",
  "[": "]",
};

/**
 * From `start` at an opening `open` bracket, return the index *after* the matching closing `close`.
 * String-aware: `{`/`[`/`}`/`]` inside JSON strings do not affect the stack.
 */
export function findBalancedBracketEnd(
  s: string,
  start: number,
  open: string,
  close: string,
): number {
  if (s[start] !== open) return -1;
  if (JSON_BRACKET_PAIR[open] !== close) return -1;

  const stack: string[] = [open];
  let inString = false;
  let escape = false;

  for (let i = start + 1; i < s.length; i++) {
    const c = s[i]!;
    if (inString) {
      if (escape) {
        escape = false;
        continue;
      }
      if (c === "\\") {
        escape = true;
        continue;
      }
      if (c === '"') inString = false;
      continue;
    }
    if (c === '"') {
      inString = true;
      continue;
    }

    if (c === "{" || c === "[") {
      stack.push(c);
      continue;
    }
    if (c === "}" || c === "]") {
      const top = stack[stack.length - 1];
      if (top === undefined) return -1;
      const expected = JSON_BRACKET_PAIR[top];
      if (c !== expected) return -1;
      stack.pop();
      if (stack.length === 0) return i + 1;
    }
  }
  return -1;
}

/** True when JSON.parse produced a single-key object whose value is a non-array object (graph command). */
export function isLikelyGraphCommand(value: unknown): boolean {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const keys = Object.keys(value);
  if (keys.length !== 1) return false;
  const inner = (value as Record<string, unknown>)[keys[0]!];
  return typeof inner === "object" && inner !== null && !Array.isArray(inner);
}

/** One JSON value for minimal `updateDataModel` (number, true/false/null, string, object, array). */
function parseOneJsonValue(s: string, start: number): { value: unknown; end: number } | null {
  const i0 = skipWs(s, start);
  if (i0 >= s.length) return null;
  if (s[i0] === '"') {
    const p = parseJsonStringLiteral(s, i0);
    return p ? { value: p.value, end: p.end } : null;
  }
  if (s[i0] === "{") {
    const end = findBalancedBracketEnd(s, i0, "{", "}");
    if (end < 0) return null;
    try {
      return { value: tryParseJsonValue(s.slice(i0, end)), end };
    } catch {
      return null;
    }
  }
  if (s[i0] === "[") {
    const end = findBalancedBracketEnd(s, i0, "[", "]");
    if (end < 0) return null;
    try {
      return { value: tryParseJsonValue(s.slice(i0, end)), end };
    } catch {
      return null;
    }
  }
  if (s.slice(i0, i0 + 4) === "true" && (i0 + 4 >= s.length || /[,\s}]/.test(s[i0 + 4]!)))
    return { value: true, end: i0 + 4 };
  if (s.slice(i0, i0 + 5) === "false" && (i0 + 5 >= s.length || /[,\s}]/.test(s[i0 + 5]!)))
    return { value: false, end: i0 + 5 };
  if (s.slice(i0, i0 + 4) === "null" && (i0 + 4 >= s.length || /[,\s}]/.test(s[i0 + 4]!)))
    return { value: null, end: i0 + 4 };
  const m = s.slice(i0).match(/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/);
  if (m && m[0].length > 0) {
    const end = i0 + m[0].length;
    if (m[0] === "-" || m[0] === "-.") return null;
    return { value: JSON.parse(m[0]) as number, end };
  }
  return null;
}

const DEFAULT_CATALOG = "https://xxx/specification/ohos/extended_catalog.json";

/**
 * Minimal GenUI: createSurface, deleteSurface, updateDataModel, or updateComponent (5+ tuple only).
 * Returns `null` so callers can fall back to legacy mini tuple.
 */
function tryParseMinimalGenUILine(s: string): Record<string, unknown> | null {
  if (s.length < 2 || s[0] !== "{" || s[s.length - 1] !== "}") return null;

  let i = 1;
  i = skipWs(s, i);
  const p0 = parseJsonStringLiteral(s, i);
  if (!p0) return null;
  const s0 = p0.value;
  i = skipWs(s, p0.end);

  if (s[i] === "}") {
    if (s0.length > 0 && s0[0] === "~") {
      return { [DELETE_SURFACE_KEY]: { surfaceId: s0.slice(1) } };
    }
    return null;
  }
  if (!isComma(s, i)) return null;
  i++;
  i = skipWs(s, i);

  // __createSurface: first is @surfaceId, then theme object only OR catalog + optional rest
  if (s0.length > 0 && s0[0] === "@") {
    const surfaceId = s0.slice(1);
    if (surfaceId.length === 0) return null;

    if (s[i] === "{") {
      const e = findBalancedBracketEnd(s, i, "{", "}");
      if (e < 0) return null;
      const theme = tryParseJsonValue(s.slice(i, e)) as Record<string, unknown>;
      if (typeof theme !== "object" || theme === null || Array.isArray(theme)) return null;
      i = skipWs(s, e);
      if (s[i] === "}") {
        return { [CREATE_SURFACE_KEY]: { surfaceId, catalogId: DEFAULT_CATALOG, theme } };
      }
      if (!isComma(s, i)) return null;
      i++;
      i = skipWs(s, i);
      const pBool = parseJsonStringLiteral(s, i);
      if (pBool) {
        if (pBool.value !== "true" && pBool.value !== "false") return null;
        i = skipWs(s, pBool.end);
        if (s[i] !== "}") return null;
        return {
          [CREATE_SURFACE_KEY]: {
            surfaceId,
            catalogId: DEFAULT_CATALOG,
            theme,
            sendDataModel: pBool.value === "true",
          },
        };
      }
      const jv = parseOneJsonValue(s, i);
      if (!jv || typeof jv.value !== "boolean") return null;
      i = skipWs(s, jv.end);
      if (s[i] !== "}") return null;
      return {
        [CREATE_SURFACE_KEY]: {
          surfaceId,
          catalogId: DEFAULT_CATALOG,
          theme,
          sendDataModel: jv.value,
        },
      };
    }

    const p1 = parseJsonStringLiteral(s, i);
    if (!p1) return null;
    i = skipWs(s, p1.end);
    const out: { surfaceId: string; catalogId: string; theme?: object; sendDataModel?: boolean } = {
      surfaceId,
      catalogId: p1.value,
    };
    if (s[i] === "}") {
      return { [CREATE_SURFACE_KEY]: out };
    }
    if (!isComma(s, i)) return null;
    i++;
    i = skipWs(s, i);
    if (s[i] === "{") {
      const e = findBalancedBracketEnd(s, i, "{", "}");
      if (e < 0) return null;
      const theme = tryParseJsonValue(s.slice(i, e)) as Record<string, unknown>;
      if (typeof theme !== "object" || theme === null || Array.isArray(theme)) return null;
      out.theme = theme;
      i = skipWs(s, e);
    } else {
      return null;
    }
    if (s[i] === "}") {
      return { [CREATE_SURFACE_KEY]: out };
    }
    if (!isComma(s, i)) return null;
    i++;
    i = skipWs(s, i);
    const pBool2 = parseJsonStringLiteral(s, i);
    if (pBool2 && (pBool2.value === "true" || pBool2.value === "false")) {
      out.sendDataModel = pBool2.value === "true";
      i = skipWs(s, pBool2.end);
    } else {
      const jv = parseOneJsonValue(s, i);
      if (jv && typeof jv.value === "boolean") {
        out.sendDataModel = jv.value;
        i = jv.end;
        i = skipWs(s, i);
      } else {
        return null;
      }
    }
    if (s[i] !== "}") return null;
    return { [CREATE_SURFACE_KEY]: out };
  }

  // Need second string for all remaining minimal forms
  const p1 = parseJsonStringLiteral(s, i);
  if (!p1) return null;
  const s1 = p1.value;
  i = skipWs(s, p1.end);

  // __updateDataModel: path second segment
  if (s1.length > 0 && s1[0] === "/") {
    const payload: { surfaceId: string; path: string; value?: unknown } = { surfaceId: s0, path: s1 };
    if (s[i] === "}") {
      return { [UPDATE_DATA_MODEL_KEY]: payload };
    }
    if (!isComma(s, i)) return null;
    i++;
    const jv = parseOneJsonValue(s, i);
    if (!jv) return null;
    payload.value = jv.value;
    i = skipWs(s, jv.end);
    if (s[i] !== "}") return null;
    return { [UPDATE_DATA_MODEL_KEY]: payload };
  }

  if (s[i] === "}") {
    // exactly two strings — not a minimal 5-tuple
    return null;
  }
  if (!isComma(s, i)) return null;
  i++;
  i = skipWs(s, i);
  const p2 = parseJsonStringLiteral(s, i);
  if (!p2) return null;
  const s2 = p2.value;
  i = skipWs(s, p2.end);

  if (s[i] === "}") {
    // three strings only, no props/children
    return null;
  }
  if (!isComma(s, i)) return null;
  i++;
  i = skipWs(s, i);

  let props: Record<string, unknown> = {};
  let children: string[] | undefined;

  if (s[i] === "{") {
    const e = findBalancedBracketEnd(s, i, "{", "}");
    if (e < 0) return null;
    const po = tryParseJsonValue(s.slice(i, e)) as unknown;
    if (typeof po !== "object" || po === null || Array.isArray(po)) return null;
    props = po as Record<string, unknown>;
    i = skipWs(s, e);
  } else if (s[i] === "[") {
    // three strings then children, no explicit props
    const e = findBalancedBracketEnd(s, i, "[", "]");
    if (e < 0) return null;
    const arr = tryParseJsonValue(s.slice(i, e));
    if (!Array.isArray(arr) || !arr.every((x) => typeof x === "string")) return null;
    children = arr as string[];
    i = skipWs(s, e);
  } else {
    return null;
  }

  if (s[i] === "}") {
    const node: Record<string, unknown> = { type: s2, props, ...(children !== undefined && { children }) };
    return { [p1.value]: node };
  }
  if (children !== undefined) return null;
  if (!isComma(s, i)) return null;
  i++;
  i = skipWs(s, i);
  if (s[i] !== "[") return null;
  const e2 = findBalancedBracketEnd(s, i, "[", "]");
  if (e2 < 0) return null;
  const arr2 = tryParseJsonValue(s.slice(i, e2));
  if (!Array.isArray(arr2) || !arr2.every((x) => typeof x === "string")) return null;
  children = arr2 as string[];
  i = skipWs(s, e2);
  if (s[i] !== "}") return null;
  return {
    [p1.value]: {
      type: s2,
      props,
      children: children!,
    },
  };
}

/**
 * Legacy compact: first segment is always node id; any order of type / props / children after.
 */
function parseCompactLineLegacy(s: string): Record<string, unknown> | null {
  if (s.length < 2 || s[0] !== "{" || s[s.length - 1] !== "}") return null;

  let i = 1;
  i = skipWs(s, i);
  const idPart = parseJsonStringLiteral(s, i);
  if (!idPart) return null;
  const id = idPart.value;
  i = skipWs(s, idPart.end);

  if (s[i] === "}") {
    return { [id]: {} };
  }
  if (!isComma(s, i)) return null;
  i++;
  i = skipWs(s, i);

  let typeStr: string | undefined;
  let props: Record<string, unknown> | undefined;
  let children: string[] | undefined;

  while (true) {
    i = skipWs(s, i);
    if (s[i] === "}") break;

    const ch = s[i];
    if (ch === '"') {
      const strPart = parseJsonStringLiteral(s, i);
      if (!strPart) return null;
      if (typeStr !== undefined) return null;
      typeStr = strPart.value;
      i = strPart.end;
    } else if (ch === "{") {
      if (props !== undefined) return null;
      const end = findBalancedBracketEnd(s, i, "{", "}");
      if (end < 0) return null;
      try {
        const parsed = tryParseJsonValue(s.slice(i, end)) as unknown;
        if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) return null;
        props = parsed as Record<string, unknown>;
      } catch {
        return null;
      }
      i = end;
    } else if (ch === "[") {
      if (children !== undefined) return null;
      const end = findBalancedBracketEnd(s, i, "[", "]");
      if (end < 0) return null;
      let arr: unknown;
      try {
        arr = tryParseJsonValue(s.slice(i, end));
      } catch {
        return null;
      }
      if (!Array.isArray(arr)) return null;
      if (!arr.every((x) => typeof x === "string")) return null;
      children = arr as string[];
      i = end;
    } else {
      return null;
    }

    i = skipWs(s, i);
    if (s[i] === "}") break;
    if (!isComma(s, i)) return null;
    i++;
  }

  i = skipWs(s, i);
  if (s[i] !== "}") return null;

  if (typeStr !== undefined) {
    const node: Record<string, unknown> = { type: typeStr };
    if (props !== undefined) node.props = props;
    if (children !== undefined) node.children = children;
    return { [id]: node };
  }

  const patch: Record<string, unknown> = {};
  if (props !== undefined) patch.props = props;
  if (children !== undefined) patch.children = children;
  return { [id]: patch };
}

/**
 * Parse one compact line into a graph command object, or null if not valid compact format.
 * Tries **minimal GenUI**, then **implicit brace tuple** (sloppy comma-tuple / braceless props/theme), then legacy **mini** tuple.
 */
export function parseCompactLine(raw: string): Record<string, unknown> | null {
  const t = raw.trim();
  return (
    tryParseMinimalGenUILine(t) ??
    tryParseMiniTupleBraceLineToGraphCommand(t) ??
    parseCompactLineLegacy(t)
  );
}

/** @deprecated Use {@link parseCompactLine} */
export const parseCompactTupleLine = parseCompactLine;
