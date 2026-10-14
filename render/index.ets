import { hilog } from '@kit.PerformanceAnalysisKit';
import { applyDesignStyles } from './design_handle';
import { preprocessMiniPayloadForFaultTolerance } from './fault_tolerance';

const A2_VERSION: string = 'v0.9';

const MAP_MINI_TO_A2UI_DOMAIN: number = 0xd001000;

const MAP_MINI_TO_A2UI_TAG: string = 'CompactHar';

/**

 * Per-component props written at the component root next to id / component,

 * not under `styles`. Extend this registry when adding new component-specific hoists.

 */

const COMPONENT_FLAT_PROPS: Record<string, string[]> = {
  'Text': ['content'],
  'Button': ['action', 'label', 'enabled'],
  'Row': ['space'],
  'Column': ['space'],
  'Radio': ['value', 'checked', 'group', 'indicatorType'],
  'TextInput': ['text', 'placeholder', 'enabled', 'maxLength', 'type'],
  'List': ['space'],
  'Image': ['src'],
  'Toggle': ['label', 'isOn', 'enabled'],
  'Progress': ['value', 'total'],
  'Checkbox': ['label', 'group', 'select'],
  'CheckboxGroup': ['group', 'selectAll'],
  'Web': ['url'],
  'Navigation': ['currentIndex', 'title'],
  'Tabs': ['barPosition', 'vertical', 'scrollable', 'tabIndex'],
  'TabContent': ['title', 'icon', 'selectedSrc', 'tabType'],
  'Select': ['options', 'selected', 'value']
};

// 组件属性重命名映射表（componentType → 原属性名 → 目标属性名）
// 采用两层 Record 结构，方便未来扩展
const COMPONENT_PROP_RENAME: Record<string, Record<string, string>> = {
  'Row': { 'space': 'itemMargin' },
  'Column': { 'space': 'itemMargin' }
};

/** 紧凑协议认可的组件类型名（与 `COMPONENT_FLAT_PROPS` 解耦，新增组件时需同步维护）。 */
const LEGAL_COMPACT_COMPONENT_TYPES: string[] = [
  'Text',
  'Button',
  'Row',
  'Column',
  'Radio',
  'TextInput',
  'List',
  'Image',
  'Toggle',
  'Progress',
  'Checkbox',
  'CheckboxGroup',
  'Web',
  'Navigation',
  'Tabs',
  'TabContent',
  'Select',
  'Stack',
  'Divider',
  'Grid'
];

/** 仅这些布局类组件的紧凑元组允许第 4 段为子节点 id 数组；其余类型若有第 4 段及以后一律忽略。 */
const COMPONENT_TYPES_WITH_TUPLE_CHILDREN: string[] =
  ['Row', 'Column', 'List', 'Stack', 'Grid', 'Navigation', 'Tabs'];

/** v0.9 允许 `children: { componentId, path }` 动态模板（非 string[]）。 */
const COMPONENT_TYPES_WITH_DYNAMIC_CHILDREN: string[] = ['List', 'Tabs', 'Navigation'];

function acceptsTupleChildren(componentType: string): boolean {
  const lower = componentType.toLowerCase();
  for (let i = 0; i < COMPONENT_TYPES_WITH_TUPLE_CHILDREN.length; i++) {
    if (COMPONENT_TYPES_WITH_TUPLE_CHILDREN[i].toLowerCase() === lower) {
      return true;
    }
  }
  return false;
}

function acceptsDynamicChildrenTemplate(componentType: string): boolean {
  const lower = componentType.toLowerCase();
  for (let i = 0; i < COMPONENT_TYPES_WITH_DYNAMIC_CHILDREN.length; i++) {
    if (COMPONENT_TYPES_WITH_DYNAMIC_CHILDREN[i].toLowerCase() === lower) {
      return true;
    }
  }
  return false;
}

function isDynamicChildrenTemplate(v: Object | string | number | boolean | string[] | null | undefined): boolean {
  if (typeof v !== 'object' || v === null || Array.isArray(v)) {
    return false;
  }
  const o = v as Record<string, Object | string | number | boolean | string[] | null>;
  return typeof o['componentId'] === 'string' &&
    (o['componentId'] as string).length > 0 &&
    typeof o['path'] === 'string' &&
    (o['path'] as string).length > 0;
}

function mapDynamicChildrenTemplate(raw: Record<string, Object | string | number | boolean | string[] | null>): Record<string, string> {
  const out: Record<string, string> = {};
  out['componentId'] = raw['componentId'] as string;
  out['path'] = raw['path'] as string;
  return out;
}

function isLegalCompactComponentType(componentType: string): boolean {
  const lower = componentType.toLowerCase();
  for (let i = 0; i < LEGAL_COMPACT_COMPONENT_TYPES.length; i++) {
    if (LEGAL_COMPACT_COMPONENT_TYPES[i].toLowerCase() === lower) {
      return true;
    }
  }
  return false;
}

function getRenamedPropKey(componentType: string, propKey: string): string {
  const compMap: Record<string, string> | undefined = COMPONENT_PROP_RENAME[componentType];
  if (compMap && compMap[propKey]) {
    return compMap[propKey];
  }
  return propKey; // 没有重命名规则时，原样返回
}

function isComponentFlatProp(componentType: string, propKey: string): boolean {
  const list: string[] | undefined = COMPONENT_FLAT_PROPS[componentType];

  if (list === undefined) {
    return false;
  }

  for (let i: number = 0; i < list.length; i++) {
    if (list[i] === propKey) {
      return true;
    }
  }

  return false;
}

/** Never hoist these from props; they are set by the tuple or the `styles` envelope. */

function isStructuralComponentKey(propKey: string): boolean {
  return propKey === 'id' || propKey === 'component' || propKey === 'styles' || propKey === 'children';
}

function shouldHoistPropToComponentRoot(componentType: string, propKey: string): boolean {
  if (isStructuralComponentKey(propKey)) {
    return false;
  }

  return isComponentFlatProp(componentType, propKey);
}

/** Compact-only props consumed during mapping; never hoisted or written to styles. */
function isCompactOnlyProp(componentType: string, propKey: string): boolean {
  return componentType.toLowerCase() === 'button' && propKey === 'url';
}

const PRIMARY_DATA_MODEL_PROP: Record<string, string> = {
  'Text': 'content',
  'TextInput': 'text',
  'Image': 'src'
};

const DATA_MODEL_STRING_BIND_PROPS: Record<string, string[]> = {
  'Text': ['content'],
  'Button': ['label'],
  'TextInput': ['text'],
  'Image': ['src'],
  'Radio': ['value'],
  'Toggle': ['label'],
  'Checkbox': ['label'],
  'Select': ['value'],
  'Web': ['url']
};

function isDataByPath(head: string): boolean {
  return head.length > 0 && head.charAt(0) === '/';
}

function isPathOnlyBinding(v: Object | string | number | boolean | string[] | null | undefined): boolean {
  if (typeof v !== 'object' || v === null || Array.isArray(v)) {
    return false;
  }
  const o = v as Record<string, Object | string | number | boolean | string[] | null>;
  const keys: string[] = Object.keys(o);
  return keys.length === 1 && typeof o['path'] === 'string';
}

function shouldBindStringPropToDataModel(componentType: string, propKey: string): boolean {
  const list: string[] | undefined = DATA_MODEL_STRING_BIND_PROPS[componentType];
  if (list === undefined) {
    return false;
  }
  for (let i: number = 0; i < list.length; i++) {
    if (list[i] === propKey) {
      return true;
    }
  }
  return false;
}

function inferDataModelBindPath(compId: string, componentType: string, propKey: string): string {
  const primary: string | undefined = PRIMARY_DATA_MODEL_PROP[componentType];
  if (primary !== undefined && propKey === primary) {
    return `/${compId}`;
  }
  return `/${compId}/${propKey}`;
}

function resolveHoistedPropValue(
  compId: string,
  componentType: string,
  propKey: string,
  raw: Object | string | number | boolean | string[] | null | undefined
): Object | string | number | boolean | string[] | null {
  if (!shouldBindStringPropToDataModel(componentType, propKey)) {
    return raw as Object | string | number | boolean | string[] | null;
  }
  if (isPathOnlyBinding(raw)) {
    return raw as Object;
  }
  if (typeof raw === 'string') {
    if (raw.startsWith('/')) {
      const pathBody: Record<string, string> = {};
      pathBody['path'] = raw;
      return pathBody as Object;
    }
    const pathBody: Record<string, string> = {};
    pathBody['path'] = inferDataModelBindPath(compId, componentType, propKey);
    return pathBody as Object;
  }
  return raw as Object | string | number | boolean | string[] | null;
}

interface JsonStringSlice {
  value: string;
  next: number;
}

interface JsonNumberSlice {
  value: number;
  next: number;
}

interface MinimalValueSlice {
  value: Object | null;
  next: number;
}

function skipWs(s: string, i: number): number {
  let j: number = i;

  while (j < s.length) {
    const c: string = s.charAt(j);
    if (c === ' ' || c === '\n' || c === '\r' || c === '\t') {
      j++;
    } else {
      break;
    }
  }

  return j;
}

/** Match `{` / `[` to corresponding `}` / `]`, respecting strings and escapes. */

function findMatchingBracket(s: string, openIndex: number, openCh: string, closeCh: string): number {
  let depth: number = 0;
  let inString: boolean = false;
  let escape: boolean = false;
  let i: number = openIndex;

  for (; i < s.length; i++) {
    const c: string = s.charAt(i);
    if (inString) {
      if (escape) {
        escape = false;
      } else if (c === '\\') {
        escape = true;
      } else if (c === '"') {
        inString = false;
      }
      continue;
    }

    if (c === '"') {
      inString = true;
      continue;
    }

    if (c === openCh) {
      depth++;
    } else if (c === closeCh) {
      depth--;
      if (depth === 0) {
        return i;
      }
    }
  }

  throw new Error('mapMiniToA2ui: unclosed bracket in minimal syntax');
}

function readJsonStringValue(s: string, startQuote: number): JsonStringSlice {
  if (s.charAt(startQuote) !== '"') {
    throw new Error('mapMiniToA2ui: expected string');
  }

  let i: number = startQuote + 1;
  let out: string = '';

  while (i < s.length) {
    const c: string = s.charAt(i);

    if (c === '"') {
      const done: JsonStringSlice = { value: out, next: i + 1 };
      return done;
    }

    if (c === '\\') {
      i++;

      if (i >= s.length) {
        throw new Error('mapMiniToA2ui: bad escape in string');
      }

      const e: string = s.charAt(i);

      if (e === '"' || e === '\\' || e === '/') {
        out += e;
      } else if (e === 'b') {
        out += '\b'
      } else if (e === 'f') {
        out += '\f';
      } else if (e === 'n') {
        out += '\n';
      } else if (e === 'r') {
        out += '\r';
      } else if (e === 't') {
        out += '\t';
      } else if (e === 'u') {
        if (i + 4 >= s.length) {
          throw new Error('mapMiniToA2ui: bad \\u escape');
        }

        const hex: string = s.substring(i + 1, i + 5);
        const code: number = parseInt(hex, 16);

        if (isNaN(code)) {
          throw new Error('mapMiniToA2ui: bad \\u escape');
        }

        out += String.fromCharCode(code);
        i += 4;
      } else {
        out += e;
      }

      i++;
      continue;
    }

    out += c;
    i++;
  }

  throw new Error('mapMiniToA2ui: unterminated string');
}

function readJsonNumberValue(s: string, i: number): JsonNumberSlice {
  let j: number = i;

  if (j < s.length && s.charAt(j) === '-') {
    j++;
  }

  if (j >= s.length) {
    throw new Error('mapMiniToA2ui: bad number');
  }

  if (s.charAt(j) === '0') {
    j++;
  } else {
    while (j < s.length && s.charAt(j) >= '0' && s.charAt(j) <= '9') {
      j++;
    }
  }

  if (j < s.length && s.charAt(j) === '.') {
    j++;
    while (j < s.length && s.charAt(j) >= '0' && s.charAt(j) <= '9') {
      j++;
    }
  }

  if (j < s.length && (s.charAt(j) === 'e' || s.charAt(j) === 'E')) {
    j++;
    if (j < s.length && (s.charAt(j) === '+' || s.charAt(j) === '-')) {
      j++;
    }
    while (j < s.length && s.charAt(j) >= '0' && s.charAt(j) <= '9') {
      j++;
    }
  }

  const txt: string = s.substring(i, j);
  const n: number = Number(txt);

  if (Number.isNaN(n)) {
    throw new Error('mapMiniToA2ui: bad number');
  }

  const done: JsonNumberSlice = { value: n, next: j };
  return done;
}

function isNumericContiguousKeys(rec: Record<string, Object>): boolean {
  const keys: string[] = Object.keys(rec);

  if (keys.length === 0) {
    return false;
  }

  for (let i = 0; i < keys.length; i++) {
    if (!/^\d+$/.test(keys[i])) {
      return false;
    }
  }

  const sorted: number[] = keys.map((k: string): number => parseInt(k, 10)).sort((a: number, b: number) => a - b);

  for (let i = 0; i < sorted.length; i++) {
    if (sorted[i] !== i) {
      return false;
    }
  }

  return true;
}

/** Root uses string keys "0","1",… for positional args (legacy JSON envelope). */

function objectRootToParts(raw: Record<string, Object>): Array<Object> {
  const keys: string[] = Object.keys(raw);
  const parts: Array<Object> = [];

  for (let i = 0; i < keys.length; i++) {
    parts.push(raw[String(i)] as Object);
  }

  return parts;
}

/** After `,` in an implicit `{...}`-less object, next token begins a tuple element (not another key). */

function peekStartsNextTupleElement(s: string, q: number): boolean {
  if (q >= s.length) {
    return false;
  }

  const c: string = s.charAt(q);

  if (c === '[' || c === '{') {
    return true;
  }

  if (c === '@') {
    return true;
  }

  if (c === '-' || (c >= '0' && c <= '9')) {
    return true;
  }

  const rest: string = s.substring(q);

  if (rest.startsWith('true') || rest.startsWith('false') || rest.startsWith('null')) {
    return true;
  }

  if (c === '"') {
    const r = readJsonStringValue(s, q);
    const j: number = skipWs(s, r.next);
    return s.charAt(j) !== ':';
  }

  return false;
}

/**

 * `"k": v, …` without wrapping `{ }` (e.g. theme or props); ends before tuple `,` + next element or at `}`.

 */

function parseImplicitJsonObjectAt(s: string, startQuote: number): MinimalValueSlice {
  const out: Record<string, Object | null> = {};

  let pos: number = startQuote;

  while (true) {
    if (s.charAt(pos) !== '"') {
      throw new Error('mapMiniToA2ui: expected " for key in implicit object');
    }

    const keySl: JsonStringSlice = readJsonStringValue(s, pos);
    let j: number = skipWs(s, keySl.next);

    if (s.charAt(j) !== ':') {
      throw new Error('mapMiniToA2ui: expected : after key in implicit object');
    }

    const valSl: MinimalValueSlice = parseMinimalValueAt(s, skipWs(s, j + 1));
    out[keySl.value] = valSl.value as Object;
    const p: number = skipWs(s, valSl.next);

    if (s.charAt(p) === '}') {
      const done: MinimalValueSlice = { value: out as Object, next: p };
      return done;
    }

    if (s.charAt(p) !== ',') {
      throw new Error('mapMiniToA2ui: expected , or } after value in implicit object');
    }

    const q: number = skipWs(s, p + 1);

    if (q >= s.length) {
      throw new Error('mapMiniToA2ui: unterminated implicit object');
    }

    if (s.charAt(q) === '}') {
      const done2: MinimalValueSlice = { value: out as Object, next: q };
      return done2;
    }

    if (peekStartsNextTupleElement(s, q)) {
      const tupleSep: MinimalValueSlice = { value: out as Object, next: p };
      return tupleSep;
    }

    pos = q;
  }
}

/** `{ "k": v, … }` when JSON.parse fails (e.g. nested value uses implicit `"a":"b"` without inner `{ }). */

function parseBraceKeyValueObjectAt(s: string, openBraceIndex: number): MinimalValueSlice {
  if (s.charAt(openBraceIndex) !== '{') {
    throw new Error('mapMiniToA2ui: expected { for key-value object');
  }

  const end: number = findMatchingBracket(s, openBraceIndex, '{', '}');
  let pos: number = skipWs(s, openBraceIndex + 1);
  const out: Record<string, Object | null> = {};

  if (pos <= end && s.charAt(pos) === '}') {
    const emptyKv: MinimalValueSlice = { value: out as Object, next: end + 1 };
    return emptyKv;
  }

  while (true) {
    if (s.charAt(pos) !== '"') {
      throw new Error('mapMiniToA2ui: expected " for key in object');
    }

    const keySl: JsonStringSlice = readJsonStringValue(s, pos);
    let j: number = skipWs(s, keySl.next);

    if (s.charAt(j) !== ':') {
      throw new Error('mapMiniToA2ui: expected : after key in object');
    }

    const valSl: MinimalValueSlice = parseMinimalValueAt(s, skipWs(s, j + 1));
    out[keySl.value] = valSl.value as Object;
    pos = skipWs(s, valSl.next);

    if (pos > end) {
      throw new Error('mapMiniToA2ui: malformed brace object');
    }

    if (s.charAt(pos) === '}') {
      if (pos !== end) {
        throw new Error('mapMiniToA2ui: brace object closed at wrong }');
      }
      const done: MinimalValueSlice = { value: out as Object, next: end + 1 };
      return done;
    }

    if (s.charAt(pos) !== ',') {
      throw new Error('mapMiniToA2ui: expected , or } in object');
    }

    pos = skipWs(s, pos + 1);
  }
}

/**

 * Parses one minimal value starting at position `pos`. Used for tuples and primitives.

 */

function parseMinimalValueAt(s: string, pos: number): MinimalValueSlice {
  let i: number = skipWs(s, pos);
  const c0: string = s.charAt(i);

  if (c0 === '"') {
    const r: JsonStringSlice = readJsonStringValue(s, i);
    const j: number = skipWs(s, r.next);

    if (j < s.length && s.charAt(j) === ':') {
      return parseImplicitJsonObjectAt(s, i);
    }

    const outStr: MinimalValueSlice = { value: r.value as Object, next: r.next };
    return outStr;
  }

  if (c0 === '-') {
    const r = readJsonNumberValue(s, i);
    const out: MinimalValueSlice = { value: r.value as Object, next: r.next };
    return out;
  }

  if (c0 >= '0' && c0 <= '9') {
    const r = readJsonNumberValue(s, i);
    const out: MinimalValueSlice = { value: r.value as Object, next: r.next };
    return out;
  }

  const rest: string = s.substring(i);

  if (rest.startsWith('true')) {
    const out: MinimalValueSlice = { value: true as Object, next: i + 4 };
    return out;
  }

  if (rest.startsWith('false')) {
    const out: MinimalValueSlice = { value: false as Object, next: i + 5 };
    return out;
  }

  if (rest.startsWith('null')) {
    const out: MinimalValueSlice = { value: null, next: i + 4 };
    return out;
  }

  if (c0 === '[') {
    const end: number = findMatchingBracket(s, i, '[', ']');
    const sub: string = s.substring(i, end + 1);
    const arr: Object = JSON.parse(sub) as Object;
    const out: MinimalValueSlice = { value: arr, next: end + 1 };
    return out;
  }

  if (c0 === '{') {
    const end: number = findMatchingBracket(s, i, '{', '}');
    const sub: string = s.substring(i, end + 1);

    try {
      const parsed: Object = JSON.parse(sub) as Object;
      if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
        const out: MinimalValueSlice = { value: parsed as Object, next: end + 1 };
        return out;
      }

    } catch (_e) {
      // invalid strict JSON: may be comma-tuple or key-value with omitted inner {}
    }

    const innerFirst: number = skipWs(s, i + 1);

    if (innerFirst < s.length && s.charAt(innerFirst) === '"') {
      const rk: JsonStringSlice = readJsonStringValue(s, innerFirst);
      const afterKey: number = skipWs(s, rk.next);

      if (afterKey < s.length && s.charAt(afterKey) === ':') {
        return parseBraceKeyValueObjectAt(s, i);
      }
    }

    return parseBraceTupleContents(s, i);
  }

  throw new Error('mapMiniToA2ui: unexpected token in minimal syntax');
}

/** Comma-separated tuple `{ a, b, c }`; `openBraceIndex` points at `{`. */

function parseBraceTupleContents(s: string, openBraceIndex: number): MinimalValueSlice {
  if (s.charAt(openBraceIndex) !== '{') {
    throw new Error('mapMiniToA2ui: expected { for tuple');
  }

  const parts: Array<Object | null> = [];
  let i: number = skipWs(s, openBraceIndex + 1);

  if (s.charAt(i) === '}') {
    const empty: MinimalValueSlice = { value: parts as Object, next: i + 1 };
    return empty;
  }

  while (true) {
    const r = parseMinimalValueAt(s, i);
    parts.push(r.value);
    i = skipWs(s, r.next);
    if (s.charAt(i) === '}') {
      const done: MinimalValueSlice = { value: parts as Object, next: i + 1 };
      return done;
    }
    if (s.charAt(i) !== ',') {
      throw new Error('mapMiniToA2ui: expected , or } in tuple');
    }
    i = skipWs(s, i + 1);
  }
}

/**

 * Tuple form returns `Array<Object>` packaged as Object to satisfy ArkTS typed return;

 * caller normalizes via `normalizeTupleParts`.

 */

function normalizeTupleParts(v: Object | null): Array<Object> {
  if (v === null) {
    throw new Error('mapMiniToA2ui: invalid tuple value');
  }

  return v as Array<Object>;
}

function parseUiParts(mini: string): Array<Object> {
  const s: string = mini.trim();

  if (s.length === 0) {
    throw new Error('mapMiniToA2ui: empty payload');
  }

  const c0: string = s.charAt(0);

  if (c0 === '{') {
    const endBrace: number = findMatchingBracket(s, 0, '{', '}');

    if (endBrace + 1 !== s.length && skipWs(s, endBrace + 1) !== s.length) {
      throw new Error('mapMiniToA2ui: trailing characters after root }');
    }

    const sub: string = s.substring(0, endBrace + 1);
    let jsonOk: boolean = false;
    let parsedRoot: Object | null = null;

    try {
      parsedRoot = JSON.parse(sub) as Object;
      jsonOk = true;
    } catch (_e) {
      jsonOk = false;
    }

    if (jsonOk && typeof parsedRoot === 'object' && parsedRoot !== null && !Array.isArray(parsedRoot)) {
      const rec = parsedRoot as Record<string, Object>;

      if (Object.keys(rec).length > 0) {
        if (isNumericContiguousKeys(rec)) {
          return objectRootToParts(rec);
        }

        throw new Error('mapMiniToA2ui: root `{...}` must be comma-tuple (non-JSON body) or JSON with keys "0","1",...');
      }

      // `{}` ambiguous: parsed as JSON empty — use tuple parser so `{ }` can mean empty tuple parts
    }

    const r = parseBraceTupleContents(s, 0);
    const tail: number = skipWs(s, r.next);

    if (tail !== s.length) {
      throw new Error('mapMiniToA2ui: trailing characters after root }');
    }

    return normalizeTupleParts(r.value);
  }

  if (c0 === '[') {
    const raw: Object = JSON.parse(s) as Object;

    if (!Array.isArray(raw)) {
      throw new Error('mapMiniToA2ui: expected JSON array');
    }

    return raw as Array<Object>;
  }

  const raw2: Object | string = JSON.parse(s) as Object | string;

  if (raw2 === null) {
    throw new Error('mapMiniToA2ui: invalid payload');
  }

  if (Array.isArray(raw2)) {
    return raw2 as Array<Object>;
  }

  if (typeof raw2 === 'string') {
    return [raw2 as Object];
  }

  if (typeof raw2 === 'object') {
    const rec = raw2 as Record<string, Object>;
    if (isNumericContiguousKeys(rec)) {
      return objectRootToParts(rec);
    }
    throw new Error('mapMiniToA2ui: JSON object root must use keys 0,1,... or use { } minimal tuple');
  }

  throw new Error('mapMiniToA2ui: unsupported root payload');
}

function asString(v: Object | string | number | boolean | null | undefined): string {
  if (typeof v === 'string') {
    return v;
  }

  throw new Error('mapMiniToA2ui: expected string');
}

function isPlainObject(v: Object | string | number | boolean | null | undefined): boolean {
  if (typeof v !== 'object' || v === null) {
    return false;
  }

  return !Array.isArray(v);
}

function createOpenUrlButtonAction(url: string): Object {
  const argsBody: Record<string, string> = {};
  argsBody['url'] = url;
  const functionCallBody: Record<string, Object | string> = {};
  functionCallBody['call'] = 'openUrl';
  functionCallBody['args'] = argsBody as Object;
  const actionBody: Record<string, Object> = {};
  actionBody['functionCall'] = functionCallBody as Object;
  return actionBody as Object;
}

function mapCreateSurface(parts: Array<Object>): Record<string, Object> {
  if (parts.length < 2) {
    throw new Error('mapMiniToA2ui: surface requires catalogId');
  }

  const catalogId: string = asString(parts[1]);
  const body: Record<string, Object | string | boolean> = {};
  body['surfaceId'] = 'ui_surface';
  body['catalogId'] = catalogId;
  let idx: number = 2;

  if (idx < parts.length && isPlainObject(parts[idx])) {
    body['theme'] = parts[idx] as Object;
    idx++;
  }

  if (idx < parts.length && typeof parts[idx] === 'boolean') {
    body['send_DataModel'] = parts[idx] as boolean;
  }

  return {
    'version': A2_VERSION,
    'createSurface': body
  };
}

function mapUpdateDataModel(parts: Array<Object>): Record<string, Object> {
  if (parts.length < 1) {
    throw new Error('mapMiniToA2ui: data requires path');
  }
  const path: string = asString(parts[0]);
  const payload: Record<string, Object | string | number | boolean | string[] | null> = {};
  payload['surfaceId'] = 'ui_surface';
  payload['path'] = path;

  if (parts.length > 1) {
    payload['value'] = parts[1] as Object | string | number | boolean | string[] | null;
  }

  return {
    'version': A2_VERSION,
    'updateDataModel': payload
  };
}

function mapUpdateComponents(parts: Array<Object>): Record<string, Object> {
  if (parts.length < 2) {
    throw new Error('mapMiniToA2ui: component needs id and type');
  }

  const compId: string = asString(parts[0]);
  const compType: string = asString(parts[1]);
  const emptyProps: Record<string, Object | string | number | boolean | string[] | null> = {};
  let propsRaw: Object | string | number | boolean | null | undefined =
    parts.length >= 3 ? parts[2] : emptyProps as Object;

  if (propsRaw === undefined || propsRaw === null) {
    propsRaw = emptyProps as Object;
  }

  if (!isPlainObject(propsRaw)) {
    throw new Error('mapMiniToA2ui: props must be object');
  }

  let resolvedCompType: string = compType;
  if (!isLegalCompactComponentType(compType) && parts.length >= 4) {
    resolvedCompType = 'Column';
  }

  const props = propsRaw as Record<string, Object | string | number | boolean | string[] | null>;
  const styleProps: Record<string, Object | string | number | boolean | string[] | null> = {};
  const keys: string[] = Object.keys(props);

  for (let i = 0; i < keys.length; i++) {
    const k: string = keys[i];

    if (shouldHoistPropToComponentRoot(resolvedCompType, k)) {
      continue;
    }

    if (isCompactOnlyProp(resolvedCompType, k)) {
      continue;
    }

    if (k === 'styles') {
      // 最外层带 styles 时，平铺其内容到最终 styles
      const sv: Object | string | number | boolean | string[] | null | undefined = props[k];
      if (sv && isPlainObject(sv)) {
        const so = sv as Record<string, Object | string | number | boolean | string[] | null>;
        const sks: string[] = Object.keys(so);
        for (let ii = 0; ii < sks.length; ii++) {
          styleProps[sks[ii]] = so[sks[ii]];
        }
      }
      continue;
    }

    styleProps[k] = props[k];
  }

  const single: Record<string, Object | string | number | boolean | string[] | null> = {};
  single['id'] = compId;
  single['component'] = resolvedCompType;

  for (let j = 0; j < keys.length; j++) {
    const k2: string = keys[j];

    if (shouldHoistPropToComponentRoot(resolvedCompType, k2)) {
      const finalKey: string = getRenamedPropKey(resolvedCompType, k2);
      single[finalKey] = resolveHoistedPropValue(compId, resolvedCompType, k2, props[k2]);
    }
  }

  if (resolvedCompType.toLowerCase() === 'button') {
    const urlVal = props['url'];
    if (typeof urlVal === 'string' && urlVal.trim().length > 0) {
      single['action'] = createOpenUrlButtonAction(urlVal.trim());
    }
  }

  single['styles'] = applyDesignStyles(resolvedCompType, styleProps) as Object;

  if (parts.length >= 4 && acceptsTupleChildren(resolvedCompType)) {
    const ch: Object = parts[3] as Object;

    if (Array.isArray(ch)) {
      single['children'] = ch as string[];
    } else if (acceptsDynamicChildrenTemplate(resolvedCompType) && isPlainObject(ch) && isDynamicChildrenTemplate(ch)) {
      single['children'] = mapDynamicChildrenTemplate(ch as Record<string, Object | string | number | boolean | string[] | null>) as Object;
    } else {
      throw new Error('mapMiniToA2ui: children must be string[] or { componentId, path } template');
    }
  }

  const components: Array<Record<string, Object | string | number | boolean | string[] | null>> = [single];
  const updateComponentsBody: Record<string, string | Array<Record<string, Object | string | number | boolean | string[] | null>>> = {};
  updateComponentsBody['surfaceId'] = 'ui_surface';
  updateComponentsBody['components'] = components;

  return {
    'version': A2_VERSION,
    'updateComponents': updateComponentsBody
  };
}

export function mapMiniToA2ui(mini: string, first: boolean = false): string[] {
  hilog.info(MAP_MINI_TO_A2UI_DOMAIN, MAP_MINI_TO_A2UI_TAG, 'mapMiniToA2ui: input: %{public}s', mini);
  let miniForError: string = mini;
  let parts: Array<Object>;

  try {
    parts = parseUiParts(mini);
  } catch (_e) {
    miniForError = preprocessMiniPayloadForFaultTolerance(mini);
    try {
      parts = parseUiParts(miniForError);
    } catch (e2) {
      const msg: string = (e2 as Error).message;
      hilog.error(MAP_MINI_TO_A2UI_DOMAIN, MAP_MINI_TO_A2UI_TAG, 'mapMiniToA2ui: failed: %{public}s', msg);
      return ['转换失败\n输入:\n' + miniForError + '\n错误:\n' + msg];
    }
  }

  try {
    if (parts.length === 0) {
      throw new Error('mapMiniToA2ui: empty tuple');
    }

    const head: string = asString(parts[0]);
    const isDataSegment: boolean = isDataByPath(head);

    let effectiveParts: Array<Object> = parts;
    if (first && !isDataSegment) {
      effectiveParts = parts.slice();
      effectiveParts[0] = 'root' as Object;
    }

    let normalOut: string;
    if (isDataSegment) {
      normalOut = JSON.stringify(mapUpdateDataModel(parts));
    } else {
      normalOut = JSON.stringify(mapUpdateComponents(effectiveParts));
    }

    if (first) {
      const theme: Record<string, string> = { 'primaryColor': '#FF0A59F7' };
      const surfaceParts: Array<Object> = ['surface', 'ohos.a2ui.extended.catalog', theme as Object];
      const surfOut = JSON.stringify(mapCreateSurface(surfaceParts));
      hilog.info(MAP_MINI_TO_A2UI_DOMAIN, MAP_MINI_TO_A2UI_TAG, 'mapMiniToA2ui: output: %{public}s', surfOut + ' | ' + normalOut);
      return [surfOut, normalOut];
    }

    hilog.info(MAP_MINI_TO_A2UI_DOMAIN, MAP_MINI_TO_A2UI_TAG, 'mapMiniToA2ui: output: %{public}s', normalOut);
    return [normalOut];
  } catch (e) {
    const msg: string = (e as Error).message;
    hilog.error(MAP_MINI_TO_A2UI_DOMAIN, MAP_MINI_TO_A2UI_TAG, 'mapMiniToA2ui: failed: %{public}s', msg);
    return ['转换失败\n输入:\n' + miniForError + '\n错误:\n' + msg];
  }
}
