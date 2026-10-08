/**
 * Brace `{ … }` comma tuples with **implicit** `"key":value` segments (no inner `{ }`),
 * for model outputs that omit object braces. Dispatches to v0.9 then
 * {@link tryNormalizeV09Protocol} → graph commands.
 */

import {
  CREATE_SURFACE_KEY,
  DELETE_SURFACE_KEY,
  tryNormalizeV09Protocol,
} from "./protocol-v09.js";

const V09 = "v0.9";

function stripTrailingCommasInJsonText(s: string): string {
  let out = s.trim();
  let prev = "";
  while (out !== prev) {
    prev = out;
    out = out.replace(/,(\s*[}\]])/g, "$1");
  }
  return out;
}

function skipWs(s: string, i: number): number {
  let j = i;
  while (j < s.length) {
    const c = s[j]!;
    if (c === " " || c === "\n" || c === "\r" || c === "\t") j++;
    else break;
  }
  return j;
}

function isComma(s: string, i: number): boolean {
  const c = s[i];
  return c === "," || c === "\uFF0C";
}

function findMatchingBracket(s: string, openIndex: number, openCh: string, closeCh: string): number {
  let depth = 0;
  let inString = false;
  let escape = false;
  for (let i = openIndex; i < s.length; i++) {
    const c = s[i]!;
    if (inString) {
      if (escape) escape = false;
      else if (c === "\\") escape = true;
      else if (c === '"') inString = false;
      continue;
    }
    if (c === '"') {
      inString = true;
      continue;
    }
    if (c === openCh) depth++;
    else if (c === closeCh) {
      depth--;
      if (depth === 0) return i;
    }
  }
  throw new Error("mini-tuple: unclosed bracket");
}

function readJsonStringValue(s: string, startQuote: number): { value: string; next: number } {
  if (s.charAt(startQuote) !== '"') throw new Error("mini-tuple: expected string");
  let i = startQuote + 1;
  let out = "";
  while (i < s.length) {
    const c = s.charAt(i);
    if (c === '"') {
      return { value: out, next: i + 1 };
    }
    if (c === "\\") {
      i++;
      if (i >= s.length) throw new Error("mini-tuple: bad escape");
      const e = s.charAt(i);
      if (e === '"' || e === "\\" || e === "/") out += e;
      else if (e === "b") out += "\b";
      else if (e === "f") out += "\f";
      else if (e === "n") out += "\n";
      else if (e === "r") out += "\r";
      else if (e === "t") out += "\t";
      else if (e === "u") {
        if (i + 4 >= s.length) throw new Error("mini-tuple: bad \\u");
        const hex = s.substring(i + 1, i + 5);
        const code = parseInt(hex, 16);
        if (Number.isNaN(code)) throw new Error("mini-tuple: bad \\u");
        out += String.fromCharCode(code);
        i += 4;
      } else out += e;
      i++;
      continue;
    }
    out += c;
    i++;
  }
  throw new Error("mini-tuple: unterminated string");
}

function readJsonNumberValue(s: string, i: number): { value: number; next: number } {
  let j = i;
  if (j < s.length && s.charAt(j) === "-") j++;
  if (j >= s.length) throw new Error("mini-tuple: bad number");
  if (s.charAt(j) === "0") j++;
  else while (j < s.length && s.charAt(j) >= "0" && s.charAt(j) <= "9") j++;
  if (j < s.length && s.charAt(j) === ".") {
    j++;
    while (j < s.length && s.charAt(j) >= "0" && s.charAt(j) <= "9") j++;
  }
  if (j < s.length && (s.charAt(j) === "e" || s.charAt(j) === "E")) {
    j++;
    if (j < s.length && (s.charAt(j) === "+" || s.charAt(j) === "-")) j++;
    while (j < s.length && s.charAt(j) >= "0" && s.charAt(j) <= "9") j++;
  }
  const txt = s.substring(i, j);
  const n = Number(txt);
  if (Number.isNaN(n)) throw new Error("mini-tuple: bad number");
  return { value: n, next: j };
}

function peekStartsNextTupleElement(s: string, q: number): boolean {
  if (q >= s.length) return false;
  const c = s.charAt(q);
  if (c === "[" || c === "{") return true;
  if (c === "@") return true;
  if (c === "-" || (c >= "0" && c <= "9")) return true;
  const rest = s.substring(q);
  if (rest.startsWith("true") && (q + 4 >= s.length || /[,\s}]/.test(s.charAt(q + 4)!)))
    return true;
  if (rest.startsWith("false") && (q + 5 >= s.length || /[,\s}]/.test(s.charAt(q + 5)!)))
    return true;
  if (rest.startsWith("null") && (q + 4 >= s.length || /[,\s}]/.test(s.charAt(q + 4)!)))
    return true;
  if (c === '"') {
    const r = readJsonStringValue(s, q);
    const j = skipWs(s, r.next);
    return s.charAt(j) !== ":";
  }
  return false;
}

function peekJsonKeyAt(s: string, q: number): string | null {
  if (s.charAt(q) !== '"') return null;
  try {
    return readJsonStringValue(s, q).value;
  } catch {
    return null;
  }
}

function parseImplicitJsonObjectAt(
  s: string,
  startQuote: number,
  nested: boolean,
): { value: Record<string, unknown>; next: number } {
  const out: Record<string, unknown> = {};
  let pos = startQuote;
  while (true) {
    if (s.charAt(pos) !== '"') throw new Error('mini-tuple: expected " for implicit key');
    const keySl = readJsonStringValue(s, pos);
    let j = skipWs(s, keySl.next);
    if (s.charAt(j) !== ":") throw new Error("mini-tuple: expected : after implicit key");
    const valSl = parseMinimalValueAt(s, skipWs(s, j + 1), "implicitValue");
    out[keySl.value] = valSl.value;
    const p = skipWs(s, valSl.next);
    if (s.charAt(p) === "}") {
      return { value: out, next: p };
    }
    if (!isComma(s, p)) throw new Error("mini-tuple: expected , or } in implicit object");
    const q = skipWs(s, p + 1);
    if (q >= s.length) throw new Error("mini-tuple: unterminated implicit object");
    if (s.charAt(q) === "}") {
      return { value: out, next: q };
    }
    if (nested && peekJsonKeyAt(s, q) === "children") {
      return { value: out, next: p };
    }
    if (peekStartsNextTupleElement(s, q)) {
      return { value: out, next: p };
    }
    pos = q;
  }
}

function parseBraceKeyValueObjectAt(s: string, openBraceIndex: number): { value: Record<string, unknown>; next: number } {
  if (s.charAt(openBraceIndex) !== "{") throw new Error("mini-tuple: expected {");
  const end = findMatchingBracket(s, openBraceIndex, "{", "}");
  let pos = skipWs(s, openBraceIndex + 1);
  const out: Record<string, unknown> = {};
  if (pos <= end && s.charAt(pos) === "}") {
    return { value: out, next: end + 1 };
  }
  while (true) {
    if (s.charAt(pos) !== '"') throw new Error('mini-tuple: expected " for key in brace object');
    const keySl = readJsonStringValue(s, pos);
    let j = skipWs(s, keySl.next);
    if (s.charAt(j) !== ":") throw new Error("mini-tuple: expected : after key");
    const valSl = parseMinimalValueAt(s, skipWs(s, j + 1), "implicitValue");
    out[keySl.value] = valSl.value;
    pos = skipWs(s, valSl.next);
    if (pos > end) throw new Error("mini-tuple: malformed brace object");
    if (s.charAt(pos) === "}") {
      if (pos !== end) throw new Error("mini-tuple: brace object closed at wrong }");
      return { value: out, next: end + 1 };
    }
    if (!isComma(s, pos)) throw new Error("mini-tuple: expected , or } in brace object");
    pos = skipWs(s, pos + 1);
  }
}

type ImplicitLeafContext = "tuple" | "implicitValue";

function parseMinimalValueAt(
  s: string,
  pos: number,
  implicitLeaf: ImplicitLeafContext = "tuple",
): { value: unknown; next: number } {
  let i = skipWs(s, pos);
  const c0 = s.charAt(i);
  if (c0 === '"') {
    const r = readJsonStringValue(s, i);
    const j = skipWs(s, r.next);
    if (j < s.length && s.charAt(j) === ":") {
      const nested = implicitLeaf === "implicitValue";
      return parseImplicitJsonObjectAt(s, i, nested);
    }
    return { value: r.value, next: r.next };
  }
  if (c0 === "-") {
    const r = readJsonNumberValue(s, i);
    return { value: r.value, next: r.next };
  }
  if (c0 >= "0" && c0 <= "9") {
    const r = readJsonNumberValue(s, i);
    return { value: r.value, next: r.next };
  }
  const rest = s.substring(i);
  if (rest.startsWith("true") && (i + 4 >= s.length || /[,\s}\]]/.test(s.charAt(i + 4)!))) {
    return { value: true, next: i + 4 };
  }
  if (rest.startsWith("false") && (i + 5 >= s.length || /[,\s}\]]/.test(s.charAt(i + 5)!))) {
    return { value: false, next: i + 5 };
  }
  if (rest.startsWith("null") && (i + 4 >= s.length || /[,\s}\]]/.test(s.charAt(i + 4)!))) {
    return { value: null, next: i + 4 };
  }
  if (c0 === "[") {
    const end = findMatchingBracket(s, i, "[", "]");
    const sub = s.substring(i, end + 1);
    return { value: JSON.parse(stripTrailingCommasInJsonText(sub)) as unknown, next: end + 1 };
  }
  if (c0 === "{") {
    const end = findMatchingBracket(s, i, "{", "}");
    const sub = s.substring(i, end + 1);
    try {
      const parsed = JSON.parse(stripTrailingCommasInJsonText(sub));
      if (typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)) {
        return { value: parsed as Record<string, unknown>, next: end + 1 };
      }
    } catch {
      /* tuple or brace-KV */
    }
    const innerFirst = skipWs(s, i + 1);
    if (innerFirst < s.length && s.charAt(innerFirst) === '"') {
      const rk = readJsonStringValue(s, innerFirst);
      const afterKey = skipWs(s, rk.next);
      if (afterKey < s.length && s.charAt(afterKey) === ":") {
        return parseBraceKeyValueObjectAt(s, i);
      }
    }
    return parseBraceTupleContents(s, i);
  }
  throw new Error("mini-tuple: unexpected token");
}

function parseBraceTupleContents(s: string, openBraceIndex: number): { value: unknown[]; next: number } {
  if (s.charAt(openBraceIndex) !== "{") throw new Error("mini-tuple: expected {");
  const parts: unknown[] = [];
  let i = skipWs(s, openBraceIndex + 1);
  if (s.charAt(i) === "}") {
    return { value: parts, next: i + 1 };
  }
  while (true) {
    const r = parseMinimalValueAt(s, i);
    parts.push(r.value);
    i = skipWs(s, r.next);
    if (s.charAt(i) === "}") {
      return { value: parts, next: i + 1 };
    }
    if (!isComma(s, i)) throw new Error("mini-tuple: expected , or } in tuple");
    i = skipWs(s, i + 1);
  }
}

function isNumericContiguousKeys(rec: Record<string, unknown>): boolean {
  const keys = Object.keys(rec);
  if (keys.length === 0) return false;
  for (const k of keys) {
    if (!/^\d+$/.test(k)) return false;
  }
  const sorted = keys.map((k) => parseInt(k, 10)).sort((a, b) => a - b);
  for (let i = 0; i < sorted.length; i++) {
    if (sorted[i] !== i) return false;
  }
  return true;
}

function objectRootToParts(raw: Record<string, unknown>): unknown[] {
  return Object.keys(raw)
    .sort((a, b) => parseInt(a, 10) - parseInt(b, 10))
    .map((k) => raw[k] ?? null);
}

function parseUiParts(mini: string): unknown[] {
  const s = mini.trim();
  if (s.length === 0) throw new Error("mini-tuple: empty");
  const c0 = s.charAt(0);
  if (c0 === "{") {
    const endBrace = findMatchingBracket(s, 0, "{", "}");
    if (skipWs(s, endBrace + 1) !== s.length) throw new Error("mini-tuple: trailing chars after root }");
    const sub = s.substring(0, endBrace + 1);
    let parsedEnvelope: Record<string, unknown> | undefined;
    try {
      const p = JSON.parse(stripTrailingCommasInJsonText(sub)) as unknown;
      if (typeof p === "object" && p !== null && !Array.isArray(p)) {
        parsedEnvelope = p as Record<string, unknown>;
      }
    } catch {
      parsedEnvelope = undefined;
    }
    if (parsedEnvelope !== undefined && Object.keys(parsedEnvelope).length > 0) {
      if (!isNumericContiguousKeys(parsedEnvelope)) {
        throw new Error("mini-tuple: not a comma-tuple (strict JSON object)");
      }
      return objectRootToParts(parsedEnvelope);
    }
    const r = parseBraceTupleContents(s, 0);
    if (skipWs(s, r.next) !== s.length) throw new Error("mini-tuple: trailing chars after root }");
    return r.value;
  }
  if (c0 === "[") {
    const raw = JSON.parse(stripTrailingCommasInJsonText(s));
    if (!Array.isArray(raw)) throw new Error("mini-tuple: expected array");
    return raw as unknown[];
  }
  const raw2 = JSON.parse(stripTrailingCommasInJsonText(s)) as unknown;
  if (raw2 === null) throw new Error("mini-tuple: invalid");
  if (Array.isArray(raw2)) return raw2 as unknown[];
  if (typeof raw2 === "string") return [raw2];
  if (typeof raw2 === "object") {
    const rec = raw2 as Record<string, unknown>;
    if (isNumericContiguousKeys(rec)) return objectRootToParts(rec);
    throw new Error("mini-tuple: JSON object root must use keys 0,1,… or brace tuple");
  }
  throw new Error("mini-tuple: unsupported root");
}

function asString(v: unknown): string {
  if (typeof v === "string") return v;
  throw new Error("mini-tuple: expected string");
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function shallowMergeProps(dest: Record<string, unknown>, src: Record<string, unknown>): void {
  for (const k of Object.keys(src)) dest[k] = src[k];
}

/** Short mini component names → registry `Extended.*`. */
export function mapMiniShortTypeToExtended(compType: string): string | null {
  const map: Record<string, string> = {
    Card: "Extended.Card",
    Row: "Extended.Row",
    Column: "Extended.Column",
    Text: "Extended.Text",
    Image: "Extended.Image",
    Button: "Extended.Button",
    Radio: "Extended.Radio",
    Select: "Extended.Select",
    Checkbox: "Extended.Checkbox",
    Input: "Extended.TextInput",
  };
  if (compType.startsWith("Extended.")) return compType;
  return map[compType] ?? null;
}

function mapDeleteSurface(first: string): Record<string, unknown> {
  const sid = first.startsWith("~") ? first.slice(1) : first;
  return { version: V09, deleteSurface: { surfaceId: sid } };
}

function mapCreateSurface(parts: unknown[]): Record<string, unknown> {
  const first = asString(parts[0]);
  if (first.charAt(0) !== "@") throw new Error("mini-tuple: createSurface expects @");
  if (parts.length < 2) throw new Error("mini-tuple: createSurface missing catalogId");
  const surfaceId = first.slice(1);
  const catalogId = asString(parts[1]);
  const body: Record<string, unknown> = { surfaceId, catalogId };
  let idx = 2;
  if (idx < parts.length && isPlainObject(parts[idx])) {
    body.theme = parts[idx];
    idx++;
  }
  if (idx < parts.length && typeof parts[idx] === "boolean") {
    body.sendDataModel = parts[idx];
  }
  return { version: V09, createSurface: body };
}

function mapUpdateDataModel(parts: unknown[]): Record<string, unknown> {
  const surfaceId = asString(parts[0]);
  const path = asString(parts[1]);
  const payload: Record<string, unknown> = { surfaceId, path };
  if (parts.length > 2) payload.value = parts[2];
  return { version: V09, updateDataModel: payload };
}

function mapUpdateComponents(parts: unknown[]): Record<string, unknown> {
  if (parts.length < 4) throw new Error("mini-tuple: updateComponents needs surfaceId, id, type, props");
  const surfaceId = asString(parts[0]);
  const compId = asString(parts[1]);
  const compTypeRaw = asString(parts[2]);
  const extended = mapMiniShortTypeToExtended(compTypeRaw);
  if (!extended) throw new Error(`mini-tuple: unknown component type: ${compTypeRaw}`);
  const propsRaw = parts[3];
  if (!isPlainObject(propsRaw)) throw new Error("mini-tuple: props must be object");
  const single: Record<string, unknown> = {};
  shallowMergeProps(single, propsRaw);
  single.id = compId;
  single.component = extended;
  if (parts.length >= 5) {
    const ch = parts[4];
    if (!Array.isArray(ch) || !ch.every((x) => typeof x === "string")) {
      throw new Error("mini-tuple: children must be string[]");
    }
    single.children = ch;
  }
  return {
    version: V09,
    updateComponents: {
      surfaceId,
      components: [single],
    },
  };
}

function miniTuplePartsToV09(parts: unknown[]): Record<string, unknown> {
  if (parts.length === 0) throw new Error("mini-tuple: empty tuple");
  const first = asString(parts[0]);
  const head = first.charAt(0);
  if (head === "~") {
    return mapDeleteSurface(first);
  }
  if (head === "@") {
    return mapCreateSurface(parts);
  }
  if (parts.length >= 2) {
    const second = asString(parts[1]);
    if (second.charAt(0) === "/") {
      return mapUpdateDataModel(parts);
    }
  }
  return mapUpdateComponents(parts);
}

function tupleV09ToGraphCommand(v09: Record<string, unknown>): Record<string, unknown> | null {
  if (v09.version !== V09) return null;
  const ks = Object.keys(v09).filter((k) => k !== "version");
  if (ks.length !== 1) return null;

  if (v09.createSurface !== undefined && typeof v09.createSurface === "object" && v09.createSurface !== null) {
    const inner = v09.createSurface as Record<string, unknown>;
    if (typeof inner.surfaceId !== "string") return null;
    return { [CREATE_SURFACE_KEY]: inner };
  }
  if (
    v09.deleteSurface !== undefined &&
    typeof v09.deleteSurface === "object" &&
    v09.deleteSurface !== null
  ) {
    const inner = v09.deleteSurface as Record<string, unknown>;
    if (typeof inner.surfaceId !== "string") return null;
    return { [DELETE_SURFACE_KEY]: inner };
  }
  const n = tryNormalizeV09Protocol(v09);
  if (n === null) return null;
  if (Array.isArray(n)) return n.length > 0 ? (n[0] as Record<string, unknown>) : null;
  return n as Record<string, unknown>;
}

/**
 * Parse one implicit-tuple minimal line into a **single** graph command, or `null` if not this format.
 */
export function tryParseMiniTupleBraceLineToGraphCommand(line: string): Record<string, unknown> | null {
  const t = line.trim();
  if (t.length < 2 || t[0] !== "{" || t[t.length - 1] !== "}") return null;
  let parts: unknown[];
  try {
    parts = parseUiParts(t);
  } catch {
    return null;
  }
  let v09: Record<string, unknown>;
  try {
    v09 = miniTuplePartsToV09(parts);
  } catch {
    return null;
  }
  return tupleV09ToGraphCommand(v09);
}
