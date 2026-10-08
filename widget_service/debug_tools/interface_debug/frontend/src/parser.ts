import type { JsonObject, Selection, ToolFrame } from './types';

const ARRAY_ITEM_COUNT_MIN = 1;
const ARRAY_ITEM_COUNT_MAX = 100;
const OUTPUT_FIELD_PATH_LIMIT = 5000;

export function streamType(frame: ToolFrame): string {
  const values: string[] = [];
  const nested = frame.reply?.streamInfo?.streamType;
  if (typeof nested === 'string') values.push(nested.toLowerCase());
  if (typeof frame.streamType === 'string') values.push(frame.streamType.toLowerCase());
  if (typeof frame.type === 'string') values.push(frame.type.toLowerCase());
  const errorCode = frame.errorCode;
  const hasOuterError = errorCode !== undefined
    && errorCode !== null
    && String(errorCode).trim() !== ''
    && String(errorCode) !== '0';
  const status = typeof frame.status === 'string' ? frame.status.toLowerCase() : '';
  const hasErrorText = [frame.error, frame.errorMessage].some((value) => {
    if (typeof value === 'string') return value.trim().length > 0;
    if (Array.isArray(value)) return value.length > 0;
    return Boolean(value && typeof value === 'object' && Object.keys(value).length > 0);
  });
  const explicitTerminal = values.some((value) => (
    ['error', 'failed', 'final_error', 'tool.error'].includes(value)
  ));
  const explicitFinal = values.includes('final');
  const explicitIntermediate = values.find((value) => (
    ['start', 'partial', 'command', 'streaming', 'pending'].includes(value)
  ));
  const statusTerminal = ['error', 'failed', 'final_error'].includes(status);
  const inferredError = hasOuterError || frame.ok === false || statusTerminal || hasErrorText;
  if (explicitTerminal || statusTerminal) return 'final_error';
  if (explicitFinal) return inferredError ? 'final_error' : 'final';
  // An explicitly non-terminal stream marker wins over incidental error text
  // on a partial frame; only an explicit terminal marker may complete a call.
  if (explicitIntermediate && !hasOuterError && frame.ok !== false) return explicitIntermediate;
  if (inferredError) return 'final_error';
  return values[0] ?? 'unknown';
}

export function streamContent(frame: ToolFrame): string {
  const value = frame.reply?.streamInfo?.streamContent;
  if (typeof value === 'string') return value;
  return typeof frame.streamContent === 'string' ? frame.streamContent : '';
}

/**
 * 读取协议元数据中的可选字符串。
 *
 * 字段缺失表示服务没有返回该元数据，可以继续使用其它关联信息；但字段
 * 一旦出现就必须是字符串，避免把数字/null 静默当成“没有 requestId”。
 */
export function optionalStringField(
  value: unknown,
  field: string,
): { present: boolean; value?: string; error?: string } {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return { present: false };
  }
  const record = value as Record<string, unknown>;
  if (!Object.prototype.hasOwnProperty.call(record, field)) {
    return { present: false };
  }
  if (typeof record[field] !== 'string') {
    return { present: true, error: `${field} 必须是字符串` };
  }
  return { present: true, value: record[field] as string };
}

/** 非空且非 0 的业务错误码应统一视为失败。 */
export function hasErrorCode(value: unknown): boolean {
  if (value === undefined || value === null) return false;
  if (typeof value === 'number') return Number.isFinite(value) && value !== 0;
  if (typeof value === 'string') {
    const normalized = value.trim();
    return normalized !== '' && normalized !== '0';
  }
  return true;
}

/** 收集最终帧可能携带的所有流关联 ID，并拒绝非字符串值。 */
export function frameRequestIds(
  frame: ToolFrame,
): { values: string[]; error?: string } {
  const values: string[] = [];
  const containers: unknown[] = [frame];
  const reply = frame.reply;
  if (reply && typeof reply === 'object' && !Array.isArray(reply)) {
    containers.push(reply);
    const streamInfo = reply.streamInfo;
    if (streamInfo && typeof streamInfo === 'object' && !Array.isArray(streamInfo)) {
      containers.push(streamInfo);
    }
  }
  for (const container of containers) {
    for (const field of ['requestId', 'streamingTextId']) {
      const result = optionalStringField(container, field);
      if (result.error) return { values, error: result.error };
      if (result.value) values.push(result.value);
    }
  }
  return { values };
}

/**
 * 校验浏览器回传的 final 结果关联信息。
 *
 * Agent 后端对成功结果要求 operation 和 requestId/streamingTextId；失败结果
 * 可以只携带 ok=false、错误码或 final_error。把这条规则放在共享解析模块，
 * 接口调试和端到端直连不会出现“浏览器显示成功、Agent 随后拒绝”的分叉。
 */
export function finalResponseMetadataError(
  response: Record<string, unknown>,
  frame: ToolFrame,
  expectedOperation: string,
  expectedRequestId: string,
): string | undefined {
  const containers: Record<string, unknown>[] = [response, frame];
  const addNested = (value: unknown) => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return;
    const record = value as Record<string, unknown>;
    containers.push(record);
    for (const key of ['response', 'finalFrame', 'reply']) {
      const nested = record[key];
      if (nested && typeof nested === 'object' && !Array.isArray(nested)) {
        containers.push(nested as Record<string, unknown>);
        if (key === 'reply') {
          const streamInfo = (nested as Record<string, unknown>).streamInfo;
          if (streamInfo && typeof streamInfo === 'object' && !Array.isArray(streamInfo)) {
            containers.push(streamInfo as Record<string, unknown>);
          }
        }
      }
    }
  };
  // Only inspect one level of known protocol containers; business data may
  // legitimately contain fields named operation or requestId.
  addNested(response.response);
  addNested(response.finalFrame);
  addNested(frame.reply);

  const operationValues: string[] = [];
  const requestIds: string[] = [];
  for (const container of containers) {
    for (const key of ['operation', 'functionName']) {
      const field = optionalStringField(container, key);
      if (field.error) return field.error;
      if (field.value?.trim() && !(key === 'functionName' && field.value.trim() === 'invoke')) {
        operationValues.push(field.value.trim());
      }
    }
    for (const key of ['requestId', 'streamingTextId']) {
      const field = optionalStringField(container, key);
      if (field.error) return field.error;
      if (field.value?.trim()) requestIds.push(field.value.trim());
    }
  }
  const frameIds = frameRequestIds(frame);
  if (frameIds.error) return frameIds.error;
  requestIds.push(...frameIds.values);

  for (const value of operationValues) {
    if (value !== expectedOperation) {
      return `operation 不匹配（期望 ${expectedOperation}，收到 ${value}）`;
    }
  }
  if (expectedRequestId && requestIds.some((value) => value !== expectedRequestId)) {
    return `streamingTextId/requestId 不匹配（期望 ${expectedRequestId}，收到 ${requestIds.join(', ')})`;
  }

  const statuses = containers.flatMap((container) => (
    ['status', 'invokeStatus', 'streamType', 'type']
      .map((key) => container[key])
      .filter((value): value is string => typeof value === 'string')
      .map((value) => value.trim().toLowerCase())
  ));
  const errorCode = response.errorCode ?? frame.errorCode;
  const hasErrorText = [response.error, frame.error, frame.errorMessage].some((value) => {
    if (typeof value === 'string') return value.trim().length > 0;
    if (Array.isArray(value)) return value.length > 0;
    if (value && typeof value === 'object') return Object.keys(value).length > 0;
    return Boolean(value);
  });
  const isFailure = streamType(frame) === 'final_error'
    || response.ok === false
    || statuses.some((value) => ['failed', 'error', 'final_error'].includes(value))
    || hasErrorCode(errorCode)
    || hasErrorCode(response.errorCode) || hasErrorCode(frame.errorCode)
    || hasErrorText;
  if (!isFailure && operationValues.length === 0) return 'tool.result 缺少 operation';
  if (!isFailure && expectedRequestId && requestIds.length === 0) {
    return 'tool.result 缺少 requestId 或 streamingTextId';
  }
  return undefined;
}

/**
 * 解析服务端旧协议中可能出现的 JSON、Python repr 和 `data={...}` 包装。
 * 不执行 eval，所有输入都经过字符扫描后交给 JSON.parse。
 */
export function parsePythonRepr(value: unknown): unknown | null {
  if (typeof value !== 'string') return value ?? null;
  const source = value.trim();
  if (!source) return null;
  const direct = parseJson(source);
  if (direct !== null) return direct;
  const fenced = extractFencedJson(source);
  if (fenced) {
    const parsedFence = parseJson(fenced);
    if (parsedFence !== null) return parsedFence;
  }
  const jsonLines = source.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (jsonLines.length > 1) {
    const parsedLines = jsonLines.map(parseJson);
    if (parsedLines.every((line) => line !== null)) return parsedLines;
  }
  const model = parsePythonModel(source);
  if (model) return Object.keys(model).length === 1 && 'data' in model ? model.data : model;
  const dataObject = extractDataObject(source);
  if (dataObject) {
    const parsedData = convertPythonRepr(dataObject);
    if (parsedData !== null) return parsedData;
  }
  return convertPythonRepr(source);
}

/**
 * 解析微服务 final 帧中历史 Pydantic 消息的包络字段。
 *
 * `parsePythonRepr` 保持“只取 data 业务对象”的兼容语义，接口桥接还需要
 * requestId、operation、status 和 errorCode 做关联校验，因此单独暴露这个
 * 不执行代码的元数据解析器。
 */
export function parseLegacyToolResponse(value: unknown): Record<string, unknown> | null {
  if (typeof value !== 'string') return null;
  const marker = value.indexOf('type=');
  if (marker < 0) return null;
  const source = value.slice(marker);
  const dataMarker = source.indexOf(' data=');
  if (dataMarker < 0) return null;
  const header = source.slice(0, dataMarker);
  const dataAndTail = source.slice(dataMarker + ' data='.length);
  const statusMarker = dataAndTail.lastIndexOf(' status=');
  if (statusMarker < 0) return null;
  const dataText = dataAndTail.slice(0, statusMarker);
  const statusAndTail = dataAndTail.slice(statusMarker + ' status='.length);
  const errorCodeMarker = statusAndTail.indexOf(' errorCode=');
  if (errorCodeMarker < 0) return null;
  const statusText = statusAndTail.slice(0, errorCodeMarker);
  const errorAndTail = statusAndTail.slice(errorCodeMarker + ' errorCode='.length);
  const errorMarker = errorAndTail.indexOf(' error=');
  if (errorMarker < 0) return null;
  const errorCodeText = errorAndTail.slice(0, errorMarker);
  const errorText = errorAndTail.slice(errorMarker + ' error='.length);
  const headerFields = header.match(/^type=(.+) tool=(.+) operation=(.+) requestId=(.+)$/);
  if (!headerFields) return null;
  const type = parsePythonRepr(headerFields[1]);
  const tool = parsePythonRepr(headerFields[2]);
  const operation = parsePythonRepr(headerFields[3]);
  const requestId = parsePythonRepr(headerFields[4]);
  const data = parsePythonRepr(dataText);
  const status = parsePythonRepr(statusText);
  const errorCode = parsePythonRepr(errorCodeText);
  const error = parsePythonRepr(errorText);
  if (type === null || tool === null || operation === null || status === null || errorCode === null) {
    return null;
  }
  return { type, tool, operation, requestId, data, status, errorCode, error };
}

/** 判断一个对象是否明显是微服务响应包络，而不是业务 data 本身。 */
export function isToolResponseRecord(value: Record<string, unknown>): boolean {
  const strongKeys = [
    'requestId',
    'operation',
    'errorCode',
    'response',
    'invokeStatus',
    'streamType',
    'finalFrame',
    'ok',
  ];
  if (strongKeys.some((key) => key in value)) return true;
  if (
    typeof value.type === 'string'
    && ['final', 'final_error', 'tool.result', 'tool_result', 'response', 'error'].includes(
      value.type.toLowerCase(),
    )
    && ['status', 'requestId', 'operation', 'errorCode', 'data', 'reply', 'streamType', 'finalFrame']
      .some((key) => key in value)
  ) return true;
  return 'data' in value && 'status' in value;
}

/** 展开浏览器/Agent 可能使用的 response 包装，同时保留原始字段。 */
export function unwrapToolResponseRecord(value: Record<string, unknown>): Record<string, unknown> {
  const nested = value.response;
  if (!nested || typeof nested !== 'object' || Array.isArray(nested)) return value;
  const response = nested as Record<string, unknown>;
  return {
    ...value,
    data: value.data ?? response.data,
    status: value.status ?? response.status,
    errorCode: value.errorCode ?? response.errorCode,
    error: value.error ?? response.error,
    operation: value.operation ?? response.operation,
    requestId: value.requestId ?? response.requestId,
  };
}

function parseJson(source: string): unknown | null {
  try {
    return JSON.parse(source) as unknown;
  } catch {
    return null;
  }
}

function extractFencedJson(source: string): string | null {
  const match = source.match(/```(?:json|jsonl|javascript)?\s*([\s\S]*?)```/i);
  return match?.[1]?.trim() || null;
}

function extractDataObject(source: string): string | null {
  const marker = source.indexOf('data=');
  if (marker < 0) return null;
  const start = source.slice(marker + 'data='.length).trimStart();
  if (!start.startsWith('{') && !start.startsWith('[')) return null;
  const end = balancedEnd(start);
  return end < 0 ? null : start.slice(0, end + 1);
}

function balancedEnd(source: string): number {
  const stack: string[] = [];
  let quote = '';
  for (let index = 0; index < source.length; index += 1) {
    const character = source[index];
    if (quote) {
      if (character === '\\') index += 1;
      else if (character === quote) quote = '';
      continue;
    }
    if (character === '"' || character === "'") {
      quote = character;
      continue;
    }
    if (character === '{' || character === '[') stack.push(character);
    if (character === '}' || character === ']') {
      const expected = character === '}' ? '{' : '[';
      if (stack.pop() !== expected) return -1;
      if (stack.length === 0) return index;
    }
  }
  return -1;
}

function convertPythonRepr(source: string): unknown | null {
  let output = '';
  let quote = '';
  for (let index = 0; index < source.length; index += 1) {
    const character = source[index];
    if (!quote) {
      if (character === '"' || character === "'") {
        quote = character;
        output += '"';
      } else if (source.startsWith('True', index) && isTokenBoundary(source, index, 4)) {
        output += 'true';
        index += 3;
      } else if (source.startsWith('False', index) && isTokenBoundary(source, index, 5)) {
        output += 'false';
        index += 4;
      } else if (source.startsWith('None', index) && isTokenBoundary(source, index, 4)) {
        output += 'null';
        index += 3;
      } else if (character === '(') {
        // Pydantic ValidationError uses tuples for ``loc``.  Convert tuple
        // delimiters to JSON arrays without evaluating the response text.
        output += '[';
      } else if (character === ')') {
        let trailingIndex = output.length - 1;
        while (trailingIndex >= 0 && /\s/.test(output[trailingIndex])) trailingIndex -= 1;
        if (output[trailingIndex] === ',') {
          output = output.slice(0, trailingIndex) + output.slice(trailingIndex + 1);
        }
        output += ']';
      } else {
        output += character;
      }
      continue;
    }
    if (character === '\\' && index + 1 < source.length) {
      const next = source[index + 1];
      const escaped = next === "'" ? "'" : next === '"' ? '\\"' : next;
      output += `\\${escaped}`;
      index += 1;
    } else if (character === quote) {
      quote = '';
      output += '"';
    } else if (character === '"') {
      output += '\\"';
    } else {
      output += character;
    }
  }
  return parseJson(output);
}

function isTokenBoundary(source: string, start: number, length: number): boolean {
  const before = source[start - 1];
  const after = source[start + length];
  return !before || !/[A-Za-z0-9_]/.test(before)
    ? !after || !/[A-Za-z0-9_]/.test(after)
    : false;
}

export function normalizeArrayItemCount(value: unknown): number {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return ARRAY_ITEM_COUNT_MIN;
  return Math.min(ARRAY_ITEM_COUNT_MAX, Math.max(ARRAY_ITEM_COUNT_MIN, Math.floor(numeric)));
}

export interface SchemaNode {
  type?: string;
  description?: string;
  sampleValue?: unknown;
  properties?: Record<string, SchemaNode>;
  items?: SchemaNode;
  required?: string[];
  [key: string]: unknown;
}

export function buildSchemaPlaceholder(schema: SchemaNode, includeOptional = false): unknown {
  if (schema.type === 'string') return '请输入';
  if (schema.type === 'integer' || schema.type === 'number') return 0;
  if (schema.type === 'boolean') return false;
  if (schema.type === 'array') return [];
  if (schema.type === 'object' || schema.properties) return buildDefaultArguments(schema, includeOptional);
  return null;
}

export function buildDefaultArguments(schema: SchemaNode | null | undefined, includeOptional = false): JsonObject {
  if (!schema?.properties) return {};
  const result: JsonObject = {};
  const required = new Set(schema.required ?? []);
  Object.entries(schema.properties).forEach(([key, child]) => {
    if (child.sampleValue !== undefined) result[key] = clone(child.sampleValue);
    else if (required.has(key) || includeOptional) result[key] = buildSchemaPlaceholder(child, includeOptional);
  });
  return result;
}

export function buildOutputFieldPaths(
  schema: SchemaNode | null | undefined,
  arrayItemCount: (schemaPath: string) => number = () => ARRAY_ITEM_COUNT_MIN,
): string[] {
  const output: string[] = [];
  collectOutputPaths(schema, '', '', output, arrayItemCount);
  return output;
}

function collectOutputPaths(
  schema: SchemaNode | null | undefined,
  outputPath: string,
  schemaPath: string,
  output: string[],
  arrayItemCount: (schemaPath: string) => number,
): void {
  if (!schema) return;
  if (schema.type === 'array' && schema.items) {
    const count = normalizeArrayItemCount(arrayItemCount(schemaPath));
    for (let index = 0; index < count; index += 1) {
      collectOutputPaths(
        schema.items,
        `${outputPath}/${index}`,
        joinSchemaPath(schemaPath, 'items'),
        output,
        arrayItemCount,
      );
    }
    return;
  }
  const properties = schema.properties;
  if (properties && Object.keys(properties).length > 0) {
    Object.entries(properties).forEach(([key, child]) => {
      collectOutputPaths(
        child,
        `${outputPath}/${escapeJsonPointerSegment(key)}`,
        joinSchemaPath(schemaPath, `properties.${key}`),
        output,
        arrayItemCount,
      );
    });
    return;
  }
  const composite = schema.type === 'object' || schema.type === 'array';
  if (outputPath && !composite) {
    if (output.length >= OUTPUT_FIELD_PATH_LIMIT) {
      throw new RangeError(`输出字段展开超过 ${OUTPUT_FIELD_PATH_LIMIT} 条，请减少数组项数量。`);
    }
    output.push(outputPath);
  }
}

function joinSchemaPath(path: string, segment: string): string {
  return path ? `${path}.${segment}` : segment;
}

function escapeJsonPointerSegment(value: string): string {
  return value.replace(/~/g, '~0').replace(/\//g, '~1');
}

export function getAtPath(source: unknown, path: string): unknown {
  if (!path) return source;
  return path.split('.').reduce<unknown>((value, segment) => {
    if (value && typeof value === 'object') {
      if (Array.isArray(value) && /^\d+$/.test(segment)) return value[Number(segment)];
      return (value as Record<string, unknown>)[segment];
    }
    return undefined;
  }, source);
}

export function buildSelectedSubset(source: unknown, selections: Selection[]): unknown {
  if (selections.length === 0) return {};
  const result: unknown = Array.isArray(source) ? [] : {};
  const uniquePaths = [...new Set(selections.map((item) => item.path))];
  uniquePaths.sort((left, right) => left.split('.').length - right.split('.').length);
  uniquePaths.forEach((path) => {
    const value = getAtPath(source, path);
    if (value === undefined) return;
    setPath(result, path, clone(value));
  });
  return result;
}

function setPath(target: unknown, path: string, value: unknown): void {
  const parts = path.split('.').filter(Boolean);
  if (parts.length === 0 || !target || typeof target !== 'object') return;
  let cursor = target as Record<string, unknown> | unknown[];
  parts.forEach((part, index) => {
    const finalPart = index === parts.length - 1;
    const nextIsArray = !finalPart && /^\d+$/.test(parts[index + 1]);
    if (Array.isArray(cursor)) {
      const position = Number(part);
      while (cursor.length <= position) cursor.push(undefined);
      if (finalPart) cursor[position] = value;
      else {
        const current = cursor[position];
        if (!current || typeof current !== 'object') cursor[position] = nextIsArray ? [] : {};
        cursor = cursor[position] as Record<string, unknown> | unknown[];
      }
    } else if (finalPart) {
      cursor[part] = value;
    } else {
      const current = cursor[part];
      if (!current || typeof current !== 'object') cursor[part] = nextIsArray ? [] : {};
      cursor = cursor[part] as Record<string, unknown> | unknown[];
    }
  });
}

export function clone<T>(value: T): T {
  if (value === undefined) return value;
  try {
    return JSON.parse(JSON.stringify(value)) as T;
  } catch {
    return value;
  }
}

export function findFinalFrame(frames: ToolFrame[]): ToolFrame | undefined {
  return [...frames].reverse().find((frame) => {
    const type = streamType(frame);
    return type === 'final' || type === 'final_error';
  });
}

/** 解析 Pydantic/BaseModel 的 `Model(field='value', ...)` 字符串表示。 */
function parsePythonModel(source: string): Record<string, unknown> | null {
  const match = source.match(/^[A-Za-z_][A-Za-z0-9_.]*\(([\s\S]*)\)$/);
  if (!match) return null;
  const fields = splitTopLevel(match[1], ',');
  const output: Record<string, unknown> = {};
  let parsedField = false;
  for (const field of fields) {
    const separator = topLevelIndexOf(field, '=');
    if (separator < 1) continue;
    const key = field.slice(0, separator).trim();
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key)) continue;
    const parsed = parsePythonRepr(field.slice(separator + 1));
    if (parsed === null) continue;
    output[key] = parsed;
    parsedField = true;
  }
  return parsedField ? output : null;
}

function splitTopLevel(source: string, separator: string): string[] {
  const values: string[] = [];
  let start = 0;
  let quote = '';
  let escaped = false;
  const stack: string[] = [];
  for (let index = 0; index < source.length; index += 1) {
    const character = source[index];
    if (quote) {
      if (escaped) escaped = false;
      else if (character === '\\') escaped = true;
      else if (character === quote) quote = '';
      continue;
    }
    if (character === '"' || character === "'") {
      quote = character;
      continue;
    }
    if ('([{'.includes(character)) stack.push(character);
    else if (')]}'.includes(character)) stack.pop();
    else if (character === separator && stack.length === 0) {
      values.push(source.slice(start, index).trim());
      start = index + 1;
    }
  }
  const tail = source.slice(start).trim();
  if (tail) values.push(tail);
  return values;
}

function topLevelIndexOf(source: string, target: string): number {
  let quote = '';
  let escaped = false;
  const stack: string[] = [];
  for (let index = 0; index < source.length; index += 1) {
    const character = source[index];
    if (quote) {
      if (escaped) escaped = false;
      else if (character === '\\') escaped = true;
      else if (character === quote) quote = '';
      continue;
    }
    if (character === '"' || character === "'") {
      quote = character;
      continue;
    }
    if ('([{'.includes(character)) stack.push(character);
    else if (')]}'.includes(character)) stack.pop();
    else if (character === target && stack.length === 0) return index;
  }
  return -1;
}

export function extractArtifact(parsed: unknown, operation: Selection['operation'], runId: string) {
  const record = parsed && typeof parsed === 'object' && !Array.isArray(parsed)
    ? parsed as Record<string, unknown>
    : {};
  const nested = record.data && typeof record.data === 'object' && !Array.isArray(record.data)
    ? record.data as Record<string, unknown>
    : {};
  const payload = { ...record, ...nested };
  const genuiValue = payload.genui ?? payload.dsl ?? payload.source ?? payload.compactDsl;
  const rawArtifactReference = payload.artifactUrl
    ?? payload.artifact_url
    ?? payload.artifact_reference
    ?? payload.artifactReference;
  const artifactUrl = typeof rawArtifactReference === 'string'
    ? rawArtifactReference
    : rawArtifactReference && typeof rawArtifactReference === 'object' && !Array.isArray(rawArtifactReference)
      ? typeof (rawArtifactReference as Record<string, unknown>).url === 'string'
        ? (rawArtifactReference as Record<string, unknown>).url as string
        : typeof (rawArtifactReference as Record<string, unknown>).artifactUrl === 'string'
          ? (rawArtifactReference as Record<string, unknown>).artifactUrl as string
          : undefined
      : undefined;
  const artifactDigest = typeof payload.artifactDigest === 'string' ? payload.artifactDigest : undefined;
  return {
    runId,
    operation,
    // The legacy stream envelope wraps the usable artifact in `data`. Keep
    // that payload as raw input so the renderer can inspect known artifact
    // keys without fetching an arbitrary URL from the browser.
    raw: Object.keys(nested).length > 0 ? nested : parsed,
    genui: typeof genuiValue === 'string' ? genuiValue : undefined,
    cardSpec: payload.cardSpec,
    artifactUrl,
    artifactDigest,
  };
}
