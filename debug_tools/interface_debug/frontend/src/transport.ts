import type {
  InterfaceEvent,
  ToolFrame,
  ToolOperation,
  ToolStatus,
} from './types';

export interface ToolSocket {
  send(payload: unknown): void;
  close(): void;
}

export interface ToolSocketHandlers {
  onFrame: (frame: ToolFrame) => void;
  /** 只在 final/final_error 到达时触发；中间帧不会进入调用记录。 */
  onFinal?: (frame: ToolFrame, type: 'final' | 'final_error') => void;
  onIntermediate?: (frame: ToolFrame) => void;
  onStatus: (status: ToolStatus) => void;
  onEvent?: (event: InterfaceEvent) => void;
  /** 一次浏览器直连调用的总超时，默认 180 秒。 */
  timeoutMs?: number;
}

function websocketScheme(): string {
  if (typeof window !== 'undefined' && window.location.protocol === 'https:') {
    return 'wss:';
  }
  return 'ws:';
}

const ALLOWED_OPERATIONS: readonly ToolOperation[] = [
  'getWidgetCapabilityOverview',
  'getDataCapabilitySchemas',
  'generateWidgetCardCompactDsl',
];

/** 将配置中的相对路径、http(s) URL 或 ws(s) URL 统一成 WebSocket 地址。 */
export function buildToolSocketUrl(base: string | undefined, operation: ToolOperation): string {
  if (!ALLOWED_OPERATIONS.includes(operation)) throw new Error('不支持的工具操作');
  const configured = (base === undefined
    ? 'ws://127.0.0.1:8855/api/v1/ws/tools'
    : base).trim();
  if (!configured) throw new Error('工具地址不能为空');
  return validateWebSocketUrl(appendOperation(normalizeBaseWebSocketUrl(configured), operation));
}

/** 将相对路径、HTTP(S) 或 WS(S) 地址规范化为不含 operation 的 WS 地址。 */
export function normalizeBaseWebSocketUrl(value: string): string {
  const configured = value.trim();
  if (!configured) throw new Error('工具地址不能为空');
  if (configured.startsWith('//')) throw new Error('工具地址协议无效');
  if (/^[A-Za-z][A-Za-z0-9+.-]*:/.test(configured)
    && !/^(?:https?|wss?):\/\//i.test(configured)) {
    throw new Error('工具地址协议无效');
  }
  if (/^https?:\/\//i.test(configured)) {
    const parsed = new URL(configured);
    parsed.protocol = parsed.protocol === 'https:' ? 'wss:' : 'ws:';
    return validateWebSocketUrl(parsed.toString());
  }
  if (/^wss?:\/\//i.test(configured)) return validateWebSocketUrl(configured);
  const origin = typeof window === 'undefined'
    ? 'ws://127.0.0.1:8888'
    : `${websocketScheme()}//${window.location.host || '127.0.0.1:8888'}`;
  return validateWebSocketUrl(`${origin}${configured.startsWith('/') ? configured : `/${configured}`}`);
}

export function normalizeWebSocketUrl(value: string, operation?: ToolOperation): string {
  const base = normalizeBaseWebSocketUrl(value);
  if (!operation) return base;
  if (!ALLOWED_OPERATIONS.includes(operation)) throw new Error('不支持的工具操作');
  return appendOperation(base, operation);
}

function validateWebSocketUrl(value: string): string {
  const parsed = new URL(value);
  if (!['ws:', 'wss:'].includes(parsed.protocol) || !parsed.hostname) {
    throw new Error('工具地址必须使用 ws/wss 协议');
  }
  if (parsed.hash) throw new Error('工具地址不能包含 hash 片段');
  if (typeof window !== 'undefined' && window.location.protocol === 'https:' && parsed.protocol === 'ws:') {
    throw new Error('HTTPS 页面不能连接不安全的 ws 地址');
  }
  if (parsed.username || parsed.password || hasCredentialQuery(parsed)) throw new Error('工具地址不能包含认证信息');
  return value;
}

function hasCredentialQuery(parsed: URL): boolean {
  for (const key of parsed.searchParams.keys()) {
    const normalizedKey = key.toLowerCase().replace(/[^a-z0-9]/g, '');
    if (/(?:token|apikey|secret|password|authorization|auth)/.test(normalizedKey)) {
      return true;
    }
  }
  return false;
}

function appendOperation(base: string, operation: ToolOperation): string {
  const encodedOperation = encodeURIComponent(operation);
  if (/^wss?:\/\//i.test(base)) {
    const parsed = new URL(base);
    // Replace only the template token.  Decoding an entire query string would
    // turn an encoded `%26`/`%3D` in an unrelated value into separators.
    const rawPath = parsed.pathname.replace(/\/+$/, '');
    const decodedPath = decodeURIComponent(rawPath);
    const hasPathTemplate = /(?:\{operation\}|%7Boperation%7D)/i.test(rawPath);
    const hasSearchTemplate = /(?:\{operation\}|%7Boperation%7D)/i.test(parsed.search);
    if (hasPathTemplate || hasSearchTemplate) {
      parsed.pathname = rawPath
        .replace(/%7Boperation%7D/gi, encodedOperation)
        .replace(/\{operation\}/g, encodedOperation);
      parsed.search = parsed.search
        .replace(/%7Boperation%7D/gi, encodedOperation)
        .replace(/\{operation\}/g, encodedOperation);
      return parsed.toString();
    }
    if (decodedPath.endsWith(`/${operation}`)) {
      // Normalize an already-expanded operation path as well, so a base
      // ending in `/operation/` does not hit a strict route with a 404.
      parsed.pathname = rawPath || '/';
      return parsed.toString();
    }
    parsed.pathname = `${rawPath || ''}/${encodedOperation}`;
    return parsed.toString();
  }
  const hashIndex = base.indexOf('#');
  const hash = hashIndex >= 0 ? base.slice(hashIndex) : '';
  const withoutHash = hashIndex >= 0 ? base.slice(0, hashIndex) : base;
  const queryIndex = withoutHash.indexOf('?');
  const query = queryIndex >= 0 ? withoutHash.slice(queryIndex) : '';
  const path = queryIndex >= 0 ? withoutHash.slice(0, queryIndex) : withoutHash;
  const normalized = decodeURIComponent(path).replace(/%7Boperation%7D/gi, '{operation}').replace(/\/+$/, '');
  const nextPath = normalized.includes('{operation}')
    ? normalized.split('{operation}').join(encodedOperation)
    : normalized.endsWith(`/${operation}`)
      ? normalized
      : `${normalized}/${encodedOperation}`;
  return `${nextPath}${query}${hash}`;
}

function frameType(frame: ToolFrame): string {
  const candidates: string[] = [];
  const info = frame.reply?.streamInfo;
  if (typeof info?.streamType === 'string') candidates.push(info.streamType.toLowerCase());
  if (typeof frame.streamType === 'string') candidates.push(frame.streamType.toLowerCase());
  if (typeof frame.type === 'string') candidates.push(frame.type.toLowerCase());
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
  const explicitTerminal = candidates.some((value) => (
    ['error', 'failed', 'final_error', 'tool.error'].includes(value)
  ));
  const explicitFinal = candidates.includes('final');
  const explicitIntermediate = candidates.find((value) => (
    ['start', 'partial', 'command', 'streaming', 'pending'].includes(value)
  ));
  const statusTerminal = ['error', 'failed', 'final_error'].includes(status);
  const inferredError = hasOuterError || frame.ok === false || statusTerminal || hasErrorText;
  if (explicitTerminal || statusTerminal) return 'final_error';
  if (explicitFinal) return inferredError ? 'final_error' : 'final';
  // A partial/start marker is authoritative for this frame.  Error text on an
  // intermediate diagnostic must not end the connection before its final frame.
  if (explicitIntermediate && !hasOuterError && frame.ok !== false) return explicitIntermediate;
  if (inferredError) return 'final_error';
  return candidates[0] ?? 'unknown';
}

function createEvent(
  direction: InterfaceEvent['direction'],
  kind: string,
  operation: ToolOperation,
  payload: unknown,
): InterfaceEvent {
  return { direction, kind, operation, payload, timestamp: new Date().toISOString() };
}

/** 一次工具调用一个连接，保持服务端原始帧顺序和内容。 */
export function connectToolSocket(
  base: string | undefined,
  operation: ToolOperation,
  payload: unknown,
  handlers: ToolSocketHandlers,
): ToolSocket {
  let url = '';
  let socket: WebSocket | null = null;
  let closedByCaller = false;
  let settled = false;
  const timeoutMs = Number.isFinite(handlers.timeoutMs) && (handlers.timeoutMs ?? 0) > 0
    ? handlers.timeoutMs as number
    : 180_000;
  let timeout: ReturnType<typeof globalThis.setTimeout> | undefined;
  const emitStatus = (state: ToolStatus['state'], text: string) => {
    handlers.onStatus({ state, text });
    handlers.onEvent?.(createEvent('local', `status:${state}`, operation, text));
  };
  const emit = (direction: InterfaceEvent['direction'], kind: string, value: unknown) => {
    handlers.onEvent?.(createEvent(direction, kind, operation, value));
  };

  try {
    url = buildToolSocketUrl(base, operation);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    emitStatus('error', `地址无效：${message}`);
    return { send: () => undefined, close: () => undefined };
  }

  emitStatus('connecting', '正在连接…');
  try {
    socket = new WebSocket(url);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    emitStatus('error', `连接失败：${message}`);
    return { send: () => undefined, close: () => undefined };
  }
  timeout = globalThis.setTimeout(() => {
    if (settled || closedByCaller) return;
    settled = true;
    emitStatus('error', `调用超时（${Math.round(timeoutMs / 1000)} 秒）`);
    closedByCaller = true;
    if (socket && socket.readyState < WebSocket.CLOSING) socket.close(1000, 'timeout');
  }, timeoutMs);

  socket.onopen = () => {
    if (settled || closedByCaller) return;
    emitStatus('connected', '已连接');
    try {
      const serialized = JSON.stringify(payload);
      socket?.send(serialized);
      emit('send', 'request', payload);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      settled = true;
      closedByCaller = true;
      if (timeout !== undefined) globalThis.clearTimeout(timeout);
      emitStatus('error', `请求序列化失败：${message}`);
      if (socket && socket.readyState < WebSocket.CLOSING) socket.close(1000, 'serialization failed');
    }
  };
  socket.onmessage = (message) => {
    try {
      const value: unknown = JSON.parse(String(message.data));
      if (!value || typeof value !== 'object' || Array.isArray(value)) {
        throw new Error('响应不是 JSON 对象');
      }
      const frame = value as ToolFrame;
      const type = frameType(frame);
      if (type === 'final' || type === 'final_error') {
        if (settled) return;
        settled = true;
        if (timeout !== undefined) globalThis.clearTimeout(timeout);
        handlers.onFrame(frame);
        handlers.onFinal?.(frame, type);
        emit('receive', type, frame);
        if (socket && socket.readyState < WebSocket.CLOSING) {
          socket.close(1000, 'final received');
        }
        return;
      }
      handlers.onIntermediate?.(frame);
    } catch (error) {
      if (settled || closedByCaller) return;
      const detail = error instanceof Error ? error.message : String(error);
      settled = true;
      closedByCaller = true;
      if (timeout !== undefined) globalThis.clearTimeout(timeout);
      emitStatus('error', `响应解析失败：${detail}`);
      if (socket && socket.readyState < WebSocket.CLOSING) {
        socket.close(1000, 'invalid response');
      }
    }
  };
  socket.onerror = () => {
    if (closedByCaller || settled) return;
    settled = true;
    if (timeout !== undefined) globalThis.clearTimeout(timeout);
    emitStatus('error', 'WebSocket 连接错误');
  };
  socket.onclose = (event) => {
    if (timeout !== undefined) globalThis.clearTimeout(timeout);
    if (!settled && !closedByCaller) {
      settled = true;
      emitStatus('error', `连接已关闭（${event.code}）`);
    }
  };

  return {
    send(nextPayload: unknown) {
      if (!socket || socket.readyState !== WebSocket.OPEN) return;
      socket.send(JSON.stringify(nextPayload));
      emit('send', 'request', nextPayload);
    },
    close() {
      closedByCaller = true;
      settled = true;
      if (timeout !== undefined) globalThis.clearTimeout(timeout);
      if (socket && socket.readyState < WebSocket.CLOSING) socket.close(1000, 'client complete');
      socket = null;
    },
  };
}
