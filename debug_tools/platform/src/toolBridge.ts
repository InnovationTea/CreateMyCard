import type { BrowserToolResult } from '@widget-debug/end-to-end';
import {
  buildToolSocketUrl,
  buildToolEnvelope,
  finalResponseMetadataError,
  frameRequestIds,
  hasErrorCode,
  isToolResponseRecord,
  optionalStringField,
  parseLegacyToolResponse,
  parsePythonRepr,
  unwrapToolResponseRecord,
} from '@widget-debug/interface';
import type { DebugConfig, ToolOperation } from './types';

const ALLOWED_OPERATIONS: readonly ToolOperation[] = [
  'getWidgetCapabilityOverview',
  'getDataCapabilitySchemas',
  'generateWidgetCardCompactDsl',
];

export const DEFAULT_TOOL_WS_BASE_URL = 'ws://127.0.0.1:8855/api/v1/ws/tools';

/** 接口调试和 Agent 工具调用共用的请求包络。 */
export function buildToolRequest(
  config: DebugConfig,
  operation: ToolOperation,
  business: Record<string, unknown>,
  correlation: { sessionId?: string; interactionId?: string; utterance?: string } = {},
): Record<string, unknown> {
  void operation;
  return buildToolEnvelope(config, business, correlation);
}

function frameType(frame: Record<string, unknown>): string {
  const candidates: string[] = [];
  const reply = frame.reply;
  if (reply && typeof reply === 'object' && !Array.isArray(reply)) {
    const info = (reply as Record<string, unknown>).streamInfo;
    if (info && typeof info === 'object' && !Array.isArray(info)) {
      const type = (info as Record<string, unknown>).streamType;
      if (typeof type === 'string') candidates.push(type.toLowerCase());
    }
  }
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
  if (explicitIntermediate && !hasOuterError && frame.ok !== false) return explicitIntermediate;
  if (inferredError) return 'final_error';
  return candidates[0] ?? 'unknown';
}

function frameContent(frame: Record<string, unknown>): string | undefined {
  const reply = frame.reply;
  const info = reply && typeof reply === 'object' && !Array.isArray(reply)
    ? (reply as Record<string, unknown>).streamInfo
    : undefined;
  if (info && typeof info === 'object' && !Array.isArray(info)) {
    const value = (info as Record<string, unknown>).streamContent;
    if (value !== undefined && value !== null) return String(value);
  }
  const value = frame.streamContent;
  return value === undefined || value === null ? undefined : String(value);
}

/** 将配置中的地址解析为某个白名单 operation 的 WebSocket 地址。 */
export function normalizeToolWebSocketUrl(base: string, operation: ToolOperation): string {
  if (!ALLOWED_OPERATIONS.includes(operation)) throw new Error('不支持的工具操作');
  return buildToolSocketUrl(base, operation);
}

function parseResult(content: string | undefined, frame: Record<string, unknown>): Record<string, unknown> {
  if (!content) {
    return frame.data !== undefined ? { data: frame.data } : {};
  }
  const legacy = parseLegacyToolResponse(content);
  if (legacy) return legacy;
  const value = parsePythonRepr(content);
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const record = value as Record<string, unknown>;
    return isToolResponseRecord(record)
      ? unwrapToolResponseRecord(record)
      : { data: record };
  }
  return { data: value ?? frame.data ?? content };
}

/** 浏览器直连微服务，只消费一个 final/final_error 帧。 */
export async function executeBrowserTool(
  config: DebugConfig,
  operation: string,
  business: Record<string, unknown>,
  meta: { callId: string; runId?: string; turnId?: string; conversationId?: string; userText?: string; signal?: AbortSignal },
  requestOverride?: Record<string, unknown>,
): Promise<BrowserToolResult> {
  if (!ALLOWED_OPERATIONS.includes(operation as ToolOperation)) {
    return { ok: false, operation, errorCode: 'UNSUPPORTED_OPERATION', error: `不支持的工具：${operation}` };
  }
  const typedOperation = operation as ToolOperation;
  const request = requestOverride ?? buildToolRequest(config, typedOperation, business, {
    sessionId: meta.conversationId,
    interactionId: meta.callId,
    utterance: meta.userText,
  });
  if (meta.signal?.aborted) {
    return { ok: false, operation, error: '工具调用已取消', cancelled: true };
  }
  if (typeof WebSocket === 'undefined') return { ok: false, operation, error: '当前环境不支持 WebSocket' };
  let socket: WebSocket | null = null;
  return new Promise((resolve) => {
    let settled = false;
    const abort = () => finish({ ok: false, operation, error: '工具调用已取消', cancelled: true });
    const timer = globalThis.setTimeout(() => finish({ ok: false, operation, error: '工具调用超时' }), 180000);
    const finish = (result: BrowserToolResult) => {
      if (settled) return;
      settled = true;
      globalThis.clearTimeout(timer);
      meta.signal?.removeEventListener('abort', abort);
      try {
        if (socket && socket.readyState < WebSocket.CLOSING) socket.close(1000, 'final received');
      } catch {
        // The socket may already be closing when cancellation races with final.
      }
      resolve(result);
    };
    meta.signal?.addEventListener('abort', abort, { once: true });
    if (meta.signal?.aborted) {
      abort();
      return;
    }
    try {
      // An omitted base uses the transport module's documented localhost
      // default; an explicitly empty configured value must stay an error so
      // the settings page cannot silently route traffic somewhere else.
      socket = new WebSocket(normalizeToolWebSocketUrl(config.toolWsBaseUrl, typedOperation));
    } catch (error) {
      finish({ ok: false, operation, error: error instanceof Error ? error.message : String(error) });
      return;
    }
    socket.onopen = () => {
      if (settled) return;
      try { socket?.send(JSON.stringify(request)); } catch (error) {
        finish({ ok: false, operation, error: error instanceof Error ? error.message : String(error) });
      }
    };
    socket.onmessage = (event) => {
      try {
        const frame = JSON.parse(String(event.data)) as Record<string, unknown>;
        const type = frameType(frame);
        if (type !== 'final' && type !== 'final_error') return;
        const content = frameContent(frame);
        const parsed = parseResult(content, frame);
        const expectedRequestId = request.session && typeof request.session === 'object'
          ? `${String((request.session as Record<string, unknown>).sessionId ?? '')}&${String((request.session as Record<string, unknown>).interactionId ?? '')}`
          : '';
        const responseRequestMeta = optionalStringField(parsed, 'requestId');
        const responseOperationMeta = optionalStringField(parsed, 'operation');
        const frameOperationMeta = optionalStringField(frame, 'operation');
        const frameRequestMeta = frameRequestIds(frame);
        const responseRequestId = responseRequestMeta.value ?? '';
        const responseOperation = responseOperationMeta.value ?? frameOperationMeta.value ?? '';
        const outerErrorCode = frame.errorCode;
        const outerError = outerErrorCode !== undefined
          && outerErrorCode !== ''
          && outerErrorCode !== '0'
          && outerErrorCode !== 0
          ? String(outerErrorCode)
          : '';
        const validationError = responseRequestMeta.error
          ?? responseOperationMeta.error
          ?? frameOperationMeta.error
          ?? frameRequestMeta.error
          ?? (responseRequestId && responseRequestId !== expectedRequestId
            ? `requestId 不匹配（期望 ${expectedRequestId}，收到 ${responseRequestId}）`
            : frameRequestMeta.values.some((value) => value !== expectedRequestId)
              ? `streamingTextId/requestId 不匹配（期望 ${expectedRequestId}，收到 ${frameRequestMeta.values.join(', ')}）`
              : responseOperation && responseOperation !== operation
                ? `operation 不匹配（期望 ${operation}，收到 ${responseOperation}）`
                : outerError
                  ? `服务外层错误：${outerError}`
                  : '');
        const metadataError = finalResponseMetadataError(
          parsed,
          frame,
          operation,
          expectedRequestId,
        );
        const normalizedStatus = typeof parsed.status === 'string' ? parsed.status.toLowerCase() : '';
        const normalizedStreamType = typeof parsed.streamType === 'string'
          ? parsed.streamType.toLowerCase()
          : '';
        const normalizedType = typeof parsed.type === 'string' ? parsed.type.toLowerCase() : '';
        const parsedErrorCode = parsed.errorCode === undefined || parsed.errorCode === null
          ? outerError
          : String(parsed.errorCode);
        const failed = type === 'final_error'
          || Boolean(validationError || metadataError)
          || ['failed', 'error', 'final_error'].includes(normalizedStatus)
          || ['final_error'].includes(normalizedStreamType)
          || normalizedType === 'final_error'
          || hasErrorCode(parsedErrorCode)
          || parsed.ok === false;
        finish({
          ok: !failed,
          operation,
          requestId: responseRequestId || undefined,
          status: typeof parsed.status === 'string' ? parsed.status : type,
          errorCode: parsedErrorCode || undefined,
          error: validationError || metadataError || parsed.error || (type === 'final_error'
            ? (typeof frame.error === 'string' && frame.error.trim()
              ? frame.error
              : typeof frame.errorMessage === 'string' && frame.errorMessage.trim()
                ? frame.errorMessage
                : content?.trim())
              || (hasErrorCode(parsedErrorCode) ? `服务返回错误码：${parsedErrorCode}` : '服务返回 final_error')
            : hasErrorCode(parsedErrorCode)
              ? `服务返回错误码：${parsedErrorCode}`
              : undefined),
          data: parsed.data,
          finalFrame: frame,
          finalStreamContent: content,
        });
      } catch (error) {
        finish({ ok: false, operation, error: error instanceof Error ? error.message : String(error) });
      }
    };
    socket.onerror = () => finish({ ok: false, operation, error: '工具 WebSocket 连接失败' });
    socket.onclose = (event) => {
      if (!settled) finish({ ok: false, operation, error: `工具连接已关闭（${event.code}）` });
    };
  });
}
