import { FormEvent, KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
// Keep the envelope implementation dependency-free so this standalone package
// also builds before npm has created workspace symlinks.
import { buildToolEnvelope } from '../../../interface_debug/frontend/src/envelope';
import { buildToolSocketUrl } from '../../../interface_debug/frontend/src/transport';
import {
  frameRequestIds,
  finalResponseMetadataError,
  hasErrorCode,
  isToolResponseRecord,
  optionalStringField,
  parseLegacyToolResponse,
  parsePythonRepr,
  unwrapToolResponseRecord,
} from '../../../interface_debug/frontend/src/parser';
import type {
  ArtifactRecord,
  DebugEvent,
  QuickPrompt,
  SkillProfile,
  TimelineEntry,
  BrowserToolResult,
  SharedDebugConfig,
} from './types';
import type { ToolOperation } from '../../../interface_debug/frontend/src/types';

export interface EndToEndEvent {
  direction: 'send' | 'receive' | 'local';
  kind: string;
  payload?: unknown;
}

export interface EndToEndDebugProps {
  socketPath?: string;
  healthPath?: string;
  config?: SharedDebugConfig;
  /** 浏览器侧执行三个白名单微服务接口的桥接器。 */
  executeTool?: (
    operation: string,
    request: Record<string, unknown>,
    meta: { callId: string; runId?: string; turnId?: string; conversationId?: string; userText?: string; signal?: AbortSignal },
  ) => Promise<BrowserToolResult>;
  onEvent?: (event: EndToEndEvent) => void;
  onArtifact?: (artifact: ArtifactRecord) => void;
  microserviceStatus?: ReactNode;
}

type Message = { role: 'user' | 'assistant'; content: string; runId?: string; timestamp?: string };
type Health = Record<string, unknown> & {
  status?: string;
  model?: string;
  upstreamStatus?: string;
  upstreamReachable?: boolean;
};

const DEFAULT_QUICK_PROMPTS: QuickPrompt[] = [
  { label: '天气卡片', prompt: '帮我做一个今天的天气卡片，显示上海市天气' },
  { label: '待办清单', prompt: '创建一个待办清单卡片' },
  { label: '日程安排', prompt: '创建一个日程安排卡片，突出显示今天的重要事项' },
];

const MAX_AGENT_TIMELINE = 500;
const MAX_AGENT_MESSAGES = 200;
const AGENT_PROTOCOL_VERSION = '1.0';
const ALLOWED_TOOL_OPERATIONS = new Set([
  'getWidgetCapabilityOverview',
  'getDataCapabilitySchemas',
  'generateWidgetCardCompactDsl',
]);

function objectValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function textValue(value: unknown, fallback = ''): string {
  if (typeof value === 'string') return value;
  if (value === null || value === undefined) return fallback;
  return String(value);
}

function jsonText(value: unknown): string {
  if (typeof value === 'string') return value;
  try { return JSON.stringify(value ?? {}, null, 2); } catch { return String(value); }
}

function parseArguments(value: unknown): Record<string, unknown> {
  if (typeof value !== 'string') return objectValue(value);
  try { return objectValue(JSON.parse(value.trim())); } catch { return {}; }
}

function prettyArguments(value: unknown): string {
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) return '{}';
    try { return jsonText(JSON.parse(trimmed)); } catch { return value; }
  }
  return jsonText(value);
}

function browserResultTimelineEntry(
  result: BrowserToolResult,
  operation: string,
  callId?: string,
): Omit<TimelineEntry, 'id'> {
  const status = textValue(result.status).toLocaleLowerCase();
  const failed = result.ok === false || ['failed', 'error', 'final_error'].includes(status);
  const executionError = result.ok === false && !status;
  return {
    type: 'tool.result',
    title: `工具返回 · ${operation || '未知工具'}`,
    detail: jsonText(result),
    timestamp: new Date().toISOString(),
    tone: failed ? 'error' : 'success',
    status: executionError ? 'error' : failed ? 'result-error' : 'success',
    meta: {
      callId,
      functionName: operation || undefined,
      statusLabel: executionError ? '执行错误' : failed ? '结果错误' : '执行成功',
      flow: executionError ? 'execution-error' : failed ? 'business-error' : 'result',
    },
  };
}

function formatTime(value?: string): string {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleTimeString('zh-CN', {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

function icon(name: string) {
  const paths: Record<string, string> = {
    spark: 'M12 2l1.7 6.3L20 10l-6.3 1.7L12 18l-1.7-6.3L4 10l6.3-1.7L12 2z',
    user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm-7 8a7 7 0 0 1 14 0',
    agent: 'M12 3 14 8l5 2-5 2-2 5-2-5-5-2 5-2 2-5z',
    send: 'M3 11.8 21 3l-8.8 18-1.7-7.5L3 11.8z',
    refresh: 'M20 11a8 8 0 0 0-14.9-4L3 10h6M4 13a8 8 0 0 0 14.9 4L21 14h-6',
    settings: 'M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7zm0-6v2m0 15v2m9.5-9.5h-2M4.5 12h-2m16.2-6.2-1.4 1.4M6.7 17.3l-1.4 1.4m13.4 0-1.4-1.4M6.7 6.7 5.3 5.3',
    copy: 'M8 8h10v12H8zM6 16H4V4h10v2',
    download: 'M12 3v12m0 0 4-4m-4 4-4-4M4 20h16',
  };
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d={paths[name] ?? paths.spark} /></svg>;
}

function timelineGlyph(entry: TimelineEntry) {
  if (entry.type === 'run_started' || entry.meta?.flow === 'user') return icon('user');
  if (entry.type === 'assistant_message' || entry.meta?.flow === 'assistant') return icon('agent');
  if (entry.meta?.flow === 'request') return '→';
  if (entry.meta?.flow === 'execution-error') return '×';
  if (entry.meta?.flow === 'result' || entry.meta?.flow === 'business-error') return '←';
  if (entry.status === 'running') return '…';
  if (entry.status === 'success') return '✓';
  if (entry.status) return '!';
  return '·';
}

function resolveSocketUrl(path: string): string {
  const configured = path.trim();
  if (!configured) throw new Error('Agent WebSocket 地址不能为空');
  if (configured.startsWith('//')) throw new Error('Agent 地址协议无效');
  if (/^wss?:\/\//i.test(configured)) {
    const parsed = new URL(configured);
    if (!parsed.hostname) throw new Error('Agent 地址缺少主机名');
    if (parsed.hash) throw new Error('Agent 地址不能包含 hash 片段');
    if (hasCredentialQuery(parsed) || parsed.username || parsed.password) throw new Error('Agent 地址不能包含认证信息');
    if (typeof window !== 'undefined' && window.location.protocol === 'https:' && /^ws:/i.test(configured)) {
      throw new Error('HTTPS 页面不能连接不安全的 ws 地址');
    }
    return parsed.toString();
  }
  if (/^https?:\/\//i.test(configured)) {
    const converted = configured.replace(/^http:/i, 'ws:').replace(/^https:/i, 'wss:');
    const parsed = new URL(converted);
    if (!parsed.hostname) throw new Error('Agent 地址缺少主机名');
    if (parsed.hash) throw new Error('Agent 地址不能包含 hash 片段');
    if (hasCredentialQuery(parsed) || parsed.username || parsed.password) throw new Error('Agent 地址不能包含认证信息');
    if (typeof window !== 'undefined' && window.location.protocol === 'https:' && /^ws:/i.test(converted)) {
      throw new Error('HTTPS 页面不能连接不安全的 ws 地址');
    }
    return parsed.toString();
  }
  if (/^[A-Za-z][A-Za-z0-9+.-]*:/.test(configured)) throw new Error('Agent 地址协议无效');
  const scheme = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss' : 'ws';
  const host = typeof window === 'undefined'
    ? '127.0.0.1:8888'
    : window.location.host || '127.0.0.1:8888';
  const normalized = configured.startsWith('/') ? configured : `/${configured}`;
  const parsed = new URL(`${scheme}://${host}${normalized}`);
  if (!parsed.hostname) throw new Error('Agent 地址缺少主机名');
  if (parsed.hash) throw new Error('Agent 地址不能包含 hash 片段');
  if (hasCredentialQuery(parsed)) throw new Error('Agent 地址不能包含认证信息');
  return parsed.toString();
}

function hasCredentialQuery(url: URL): boolean {
  for (const key of url.searchParams.keys()) {
    const normalizedKey = key.toLowerCase().replace(/[^a-z0-9]/g, '');
    if (/(?:token|apikey|secret|password|authorization|auth)/.test(normalizedKey)) {
      return true;
    }
  }
  return false;
}

function createTurnId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `turn-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function agentContext(config?: SharedDebugConfig): Record<string, unknown> {
  return {
    uid: config?.userId ?? 'debug-user',
    odid: config?.deviceId ?? 'debug-device',
    deviceId: config?.deviceId ?? 'debug-device',
    phoneType: config?.phoneType ?? 'ALN-AL00',
    appVersion: config?.appVersion ?? '11.7.7.332',
    romVersion: config?.romVersion ?? 'ALN-AL00 7.0.0.100',
    locale: config?.locale ?? 'zh-CN',
    countryCode: config?.countryCode ?? 'CN',
    deviceFormation: config?.deviceFormation ?? 'phone',
    deviceType: config?.deviceType ?? 0,
    sysVer: config?.sysVer ?? 'HarmonyOS',
    paginationLimit: config?.paginationLimit ?? 5,
    paginationStart: config?.paginationStart ?? '',
  };
}

function toolFrameType(frame: Record<string, unknown>): string {
  const candidates: string[] = [];
  const reply = frame.reply;
  if (reply && typeof reply === 'object' && !Array.isArray(reply)) {
    const info = (reply as Record<string, unknown>).streamInfo;
    if (info && typeof info === 'object' && !Array.isArray(info)) {
      const streamType = (info as Record<string, unknown>).streamType;
      if (typeof streamType === 'string') candidates.push(streamType.toLowerCase());
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

function toolFrameContent(frame: Record<string, unknown>): string | undefined {
  const reply = frame.reply;
  if (reply && typeof reply === 'object' && !Array.isArray(reply)) {
    const info = (reply as Record<string, unknown>).streamInfo;
    if (info && typeof info === 'object' && !Array.isArray(info)) {
      const content = (info as Record<string, unknown>).streamContent;
      return typeof content === 'string' ? content : content == null ? undefined : String(content);
    }
  }
  const content = frame.streamContent;
  return typeof content === 'string' ? content : content == null ? undefined : String(content);
}

function toolSocketUrl(base: string | undefined, operation: string): string {
  if (!ALLOWED_TOOL_OPERATIONS.has(operation)) throw new Error(`不支持的工具：${operation}`);
  return buildToolSocketUrl(base, operation as ToolOperation);
}

function parseFinalContent(value: string | undefined): Record<string, unknown> {
  if (!value?.trim()) return {};
  const source = value.trim();
  const legacy = parseLegacyToolResponse(source);
  if (legacy) return legacy;
  const parsed = parsePythonRepr(source);
  if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
    const record = parsed as Record<string, unknown>;
    return isToolResponseRecord(record) ? unwrapToolResponseRecord(record) : { data: record };
  }
  return { data: parsed ?? value };
}

async function executeDirectTool(
  base: string | undefined,
  operation: string,
  request: Record<string, unknown>,
  config?: SharedDebugConfig,
  correlation: { sessionId?: string; interactionId?: string; userText?: string } = {},
  signal?: AbortSignal,
): Promise<BrowserToolResult> {
  if (signal?.aborted) return { ok: false, operation, error: '工具调用已取消', cancelled: true };
  if (typeof WebSocket === 'undefined') {
    return { ok: false, operation, error: '当前环境不支持 WebSocket' };
  }
  let url: string;
  try {
    url = toolSocketUrl(base, operation);
  } catch (error) {
    return { ok: false, operation, error: error instanceof Error ? error.message : String(error) };
  }
  const business = { ...request };
  delete business.bundleName;
  delete business.uid;
  delete business.odid;
  const payload = buildToolEnvelope(config, business, {
    sessionId: correlation.sessionId,
    interactionId: correlation.interactionId,
    utterance: correlation.userText
      ?? (typeof request.userQuery === 'string' ? request.userQuery : ''),
  });
  return new Promise((resolve) => {
    let settled = false;
    let socket: WebSocket | null = null;
    let timer: ReturnType<typeof globalThis.setTimeout> | undefined;
    const abort = () => finish({ ok: false, operation, error: '工具调用已取消', cancelled: true });
    const finish = (result: BrowserToolResult) => {
      if (settled) return;
      settled = true;
      if (timer !== undefined) globalThis.clearTimeout(timer);
      signal?.removeEventListener('abort', abort);
      try {
        if (socket && socket.readyState < WebSocket.CLOSING) socket.close(1000, 'final received');
      } catch {
        // The browser may reject close() while a connection is being torn down.
      }
      resolve(result);
    };
    signal?.addEventListener('abort', abort, { once: true });
    timer = globalThis.setTimeout(() => finish({ ok: false, operation, error: '工具调用超时' }), 180000);
    try {
      socket = new WebSocket(url);
    } catch (error) {
      finish({ ok: false, operation, error: error instanceof Error ? error.message : String(error) });
      return;
    }
    socket.onopen = () => {
      if (settled) return;
      try { socket?.send(JSON.stringify(payload)); } catch (error) {
        finish({ ok: false, operation, error: error instanceof Error ? error.message : String(error) });
      }
    };
    socket.onmessage = (message) => {
      try {
        const frame = JSON.parse(String(message.data)) as Record<string, unknown>;
        const type = toolFrameType(frame);
        if (type !== 'final' && type !== 'final_error') return;
        if (settled) return;
        const content = toolFrameContent(frame);
        const response = parseFinalContent(content);
        const session = payload.session as Record<string, unknown>;
        const expectedRequestId = `${String(session.sessionId ?? '')}&${String(session.interactionId ?? '')}`;
        const responseRequestMeta = optionalStringField(response, 'requestId');
        const responseOperationMeta = optionalStringField(response, 'operation');
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
          response,
          frame,
          operation,
          expectedRequestId,
        );
        const responseStatus = typeof response.status === 'string' ? response.status.toLowerCase() : '';
        const responseStreamType = typeof response.streamType === 'string' ? response.streamType.toLowerCase() : '';
        const responseType = typeof response.type === 'string' ? response.type.toLowerCase() : '';
        const responseErrorCode = response.errorCode === undefined || response.errorCode === null
          ? outerError
          : String(response.errorCode);
        const failed = type === 'final_error' || Boolean(validationError || metadataError)
          || responseStatus === 'failed' || responseStatus === 'error'
          || responseStatus === 'final_error' || responseStreamType === 'final_error'
          || responseType === 'final_error' || hasErrorCode(responseErrorCode)
          || response.ok === false;
        finish({
          ok: !failed,
          operation,
          requestId: responseRequestId || undefined,
          status: typeof response.status === 'string' ? response.status : type,
          errorCode: responseErrorCode || undefined,
          error: validationError || metadataError || response.error || (type === 'final_error'
            ? (typeof frame.error === 'string' && frame.error.trim()
              ? frame.error
              : typeof frame.errorMessage === 'string' && frame.errorMessage.trim()
                ? frame.errorMessage
                : content?.trim())
              || (hasErrorCode(responseErrorCode) ? `服务返回错误码：${responseErrorCode}` : '服务返回 final_error')
            : hasErrorCode(responseErrorCode)
              ? `服务返回错误码：${responseErrorCode}`
              : undefined),
          data: response.data ?? frame.data,
          finalFrame: frame,
          finalStreamContent: content,
        });
      } catch (error) {
        finish({ ok: false, operation, error: error instanceof Error ? error.message : String(error) });
      }
    };
    socket.onerror = () => {
      finish({ ok: false, operation, error: '工具 WebSocket 连接失败' });
    };
    socket.onclose = (event) => {
      if (!settled) {
        finish({ ok: false, operation, error: `工具连接已关闭（${event.code}）` });
      }
    };
  });
}

export default function App({
  socketPath = '/debug/e2e/ws',
  healthPath = '/debug/health',
  config,
  executeTool,
  onEvent,
  onArtifact,
  microserviceStatus,
}: EndToEndDebugProps = {}) {
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(true);
  const [connectionError, setConnectionError] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [profile, setProfile] = useState('');
  const [profiles, setProfiles] = useState<SkillProfile[]>([]);
  const [quickPrompts, setQuickPrompts] = useState<QuickPrompt[]>(DEFAULT_QUICK_PROMPTS);
  const [skillName, setSkillName] = useState('等待 Skill 信息');
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [running, setRunning] = useState(false);
  const [runStatus, setRunStatus] = useState('准备就绪');
  const [health, setHealth] = useState<Health | null>(null);
  const [mobileTab, setMobileTab] = useState<'chat' | 'timeline'>('chat');
  const [contextOpen, setContextOpen] = useState(false);
  const [timelineSearch, setTimelineSearch] = useState('');
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const socketRef = useRef<WebSocket | null>(null);
  const runStartedAt = useRef(0);
  const timelineCounter = useRef(0);
  const handledToolCallsRef = useRef<Set<string>>(new Set());
  const activeToolControllersRef = useRef<Map<string, AbortController>>(new Map());
  const activeTurnIdRef = useRef('');
  const onEventRef = useRef(onEvent);
  const onArtifactRef = useRef(onArtifact);
  const configRef = useRef(config);
  const executeToolRef = useRef(executeTool);
  const lastUserTextRef = useRef('');

  useEffect(() => {
    onEventRef.current = onEvent;
    onArtifactRef.current = onArtifact;
    configRef.current = config;
    executeToolRef.current = executeTool;
  }, [config, executeTool, onArtifact, onEvent]);

  const cancelActiveToolCalls = useCallback(() => {
    activeToolControllersRef.current.forEach((controller) => controller.abort());
    activeToolControllersRef.current.clear();
  }, []);

  const addTimeline = useCallback((entry: Omit<TimelineEntry, 'id'>, id?: string) => {
    setTimeline((items) => {
      const nextEntry = { ...entry, id: id ?? `event-${Date.now()}-${timelineCounter.current++}` };
      const existingIndex = items.findIndex((item) => item.id === nextEntry.id);
      if (existingIndex >= 0) {
        const replaced = [...items];
        replaced[existingIndex] = { ...replaced[existingIndex], ...nextEntry };
        return replaced;
      }
      return [...items, nextEntry].slice(-MAX_AGENT_TIMELINE);
    });
  }, []);

  const processEvent = useCallback((event: DebugEvent) => {
    onEventRef.current?.({ direction: 'receive', kind: event.type, payload: event });
    const data = objectValue(event.data);
    const envelope = { ...event as unknown as Record<string, unknown>, ...data };
    const timestamp = event.timestamp ?? new Date().toISOString();
    if (event.sessionId) setSessionId(event.sessionId);
    if (event.type === 'conversation.ready') {
      const conversationId = textValue(envelope.conversationId || envelope.sessionId);
      if (conversationId) setSessionId(conversationId);
      setProfile(textValue(envelope.skillProfile));
      setSkillName(textValue(envelope.skillName, 'Main Agent Debug'));
      if (Array.isArray(envelope.skillProfiles)) {
        setProfiles(envelope.skillProfiles as SkillProfile[]);
      }
      if (Array.isArray(envelope.quickPrompts)) {
        const configured = envelope.quickPrompts.filter((item): item is QuickPrompt => (
          !!item && typeof item === 'object'
          && typeof (item as QuickPrompt).label === 'string'
          && typeof (item as QuickPrompt).prompt === 'string'
          && (item as QuickPrompt).label.trim().length > 0
          && (item as QuickPrompt).prompt.trim().length > 0
        ));
        if (configured.length) setQuickPrompts(configured);
      }
      if (envelope.resumed === false) {
        cancelActiveToolCalls();
        setMessages([]);
        setTimeline([]);
        setExpanded(new Set());
        handledToolCallsRef.current.clear();
      }
      setConnecting(false);
      setConnectionError('');
      setConnected(true);
      setRunStatus('会话已就绪');
      addTimeline({ type: event.type, title: 'Agent 会话已就绪', detail: conversationId, timestamp, tone: 'success' });
      return;
    }
    if (event.type === 'turn.status') {
      const statusValue = textValue(envelope.status, '运行中');
      const turnId = textValue(envelope.turnId || envelope.runId);
      if (turnId) activeTurnIdRef.current = turnId;
      setRunning(!['completed', 'failed', 'cancelled'].includes(statusValue));
      setRunStatus(statusValue);
      if (statusValue === 'waiting_tool') return;
      const query = textValue(envelope.query);
      if (query) {
        setMessages((items) => [...items, {
          role: 'user' as const,
          content: query,
          runId: textValue(envelope.turnId),
          timestamp,
        }].slice(-MAX_AGENT_MESSAGES));
        addTimeline({
          type: event.type,
          title: '用户输入',
          detail: query,
          timestamp,
          tone: 'info',
          meta: { flow: 'user' },
        });
      }
      addTimeline({ type: event.type, title: `回合状态 · ${statusValue}`, detail: textValue(envelope.turnId), timestamp, tone: 'info' });
      return;
    }
    if (event.type === 'assistant.message') {
      const content = textValue(envelope.content);
      setMessages((items) => [...items, { role: 'assistant' as const, content, runId: textValue(envelope.turnId), timestamp }].slice(-MAX_AGENT_MESSAGES));
      addTimeline({ type: event.type, title: 'Agent 回复', detail: content, timestamp, tone: 'info', meta: { flow: 'assistant' } });
      return;
    }
    if (event.type === 'tool.trace') {
      return;
    }
    if (event.type === 'tool.call') {
      const callId = textValue(envelope.callId || envelope.id);
      const turnId = textValue(envelope.turnId || envelope.runId);
      const conversationId = textValue(envelope.conversationId || envelope.sessionId);
      const functionName = textValue(envelope.functionName || envelope.name || envelope.toolName);
      const rawArguments = envelope.arguments;
      const parsedArguments = parseArguments(rawArguments);
      const operation = functionName === 'invoke'
        ? textValue(parsedArguments.functionName || parsedArguments.operation || envelope.operation)
        : textValue(envelope.operation || functionName);
      if (!callId || !turnId) {
        addTimeline({
          type: event.type,
          title: '浏览器工具协议错误',
          detail: 'tool.call 缺少 turnId 或 callId，未连接微服务。',
          timestamp,
          tone: 'error',
          status: 'error',
        });
        return;
      }
      const toolCallKey = callId && turnId ? `${turnId}:${callId}` : '';
      if (toolCallKey) {
        if (handledToolCallsRef.current.has(toolCallKey)) return;
        handledToolCallsRef.current.add(toolCallKey);
        if (handledToolCallsRef.current.size > 256) {
          const oldest = handledToolCallsRef.current.values().next().value;
          if (typeof oldest === 'string') handledToolCallsRef.current.delete(oldest);
        }
      }
      const timelineCallId = callId ? `${turnId}:${callId}` : undefined;
      const title = operation ? `浏览器工具 · ${operation}` : `浏览器工具 · ${functionName || '未知工具'}`;
      addTimeline({
        type: event.type,
        title,
        detail: `参数:\n${prettyArguments(rawArguments)}`,
        timestamp,
        tone: 'warning',
        status: 'running',
        meta: { callId, functionName: operation || functionName, statusLabel: '浏览器执行中', flow: 'request' },
      }, timelineCallId);
      let controller: AbortController | undefined;
      void (async () => {
        const allowed = new Set(['getWidgetCapabilityOverview', 'getDataCapabilitySchemas', 'generateWidgetCardCompactDsl']);
        if (!allowed.has(operation)) {
          const result: BrowserToolResult = { ok: false, operation, errorCode: 'UNSUPPORTED_OPERATION', error: `不允许的工具：${operation}` };
          send({
            type: 'tool.result',
            protocolVersion: AGENT_PROTOCOL_VERSION,
            conversationId,
            sessionId: conversationId,
            turnId,
            runId: turnId,
            callId,
            operation,
            result,
          });
          setTimeline((items) => items.map((item) => item.id === timelineCallId ? {
            ...item,
            status: 'error',
            tone: 'error',
            meta: { ...item.meta, statusLabel: '执行失败' },
          } : item));
          addTimeline(browserResultTimelineEntry(result, operation, callId), `${timelineCallId}-result`);
          return;
        }
        const request = functionName === 'invoke' && parsedArguments.arguments
          && typeof parsedArguments.arguments === 'object'
          && !Array.isArray(parsedArguments.arguments)
          ? parsedArguments.arguments as Record<string, unknown>
          : parsedArguments;
        const activeController = new AbortController();
        controller = activeController;
        const activeKey = toolCallKey;
        if (activeKey) activeToolControllersRef.current.set(activeKey, activeController);
        const result = executeToolRef.current
          ? await executeToolRef.current(operation, request, {
            callId,
            turnId,
            runId: turnId,
            conversationId,
            userText: lastUserTextRef.current,
            signal: activeController.signal,
          })
          : await executeDirectTool(
            configRef.current?.toolWsBaseUrl,
            operation,
            request,
            configRef.current,
            {
              sessionId: conversationId,
              interactionId: callId,
              userText: lastUserTextRef.current,
            },
            activeController.signal,
          );
        if (activeController.signal.aborted) return;
        send({
          type: 'tool.result',
          protocolVersion: AGENT_PROTOCOL_VERSION,
          conversationId,
          sessionId: conversationId,
          turnId,
          runId: turnId,
          callId,
          operation,
          result,
        });
        setTimeline((items) => items.map((item) => item.id === timelineCallId ? {
          ...item,
          status: result.ok ? 'success' : 'error',
          tone: result.ok ? 'success' : 'error',
          meta: { ...item.meta, statusLabel: result.ok ? '执行成功' : '执行失败' },
        } : item));
        addTimeline(browserResultTimelineEntry(result, operation, callId), `${timelineCallId}-result`);
        if (toolCallKey) activeToolControllersRef.current.delete(toolCallKey);
      })().catch((error) => {
        if (toolCallKey) activeToolControllersRef.current.delete(toolCallKey);
        if (controller?.signal.aborted) return;
        if (error && typeof error === 'object' && 'name' in error && error.name === 'AbortError') return;
        if (!callId || !turnId) return;
        const result: BrowserToolResult = { ok: false, operation, error: error instanceof Error ? error.message : String(error) };
        send({
          type: 'tool.result',
          protocolVersion: AGENT_PROTOCOL_VERSION,
          conversationId,
          sessionId: conversationId,
          turnId,
          runId: turnId,
          callId,
          operation,
          result,
        });
        setTimeline((items) => items.map((item) => item.id === timelineCallId ? { ...item, status: 'error', tone: 'error', meta: { ...item.meta, statusLabel: '执行失败' } } : item));
        addTimeline(browserResultTimelineEntry(result, operation, callId), `${timelineCallId}-result`);
      });
      return;
    }
    if (event.type === 'tool.cancel') {
      const callId = textValue(envelope.callId);
      const turnId = textValue(envelope.turnId || envelope.runId);
      const key = callId && turnId ? `${turnId}:${callId}` : '';
      activeToolControllersRef.current.get(key)?.abort();
      if (key) activeToolControllersRef.current.delete(key);
      addTimeline({ type: event.type, title: '浏览器工具已取消', detail: key, timestamp, tone: 'error', status: 'error' }, key || undefined);
      return;
    }
    if (event.type === 'tool.result.rejected') {
      const callId = textValue(envelope.callId);
      const turnId = textValue(envelope.turnId || envelope.runId);
      const key = callId && turnId ? `${turnId}:${callId}` : '';
      const message = textValue(envelope.message || envelope.code, 'Agent 拒绝了工具结果');
      setTimeline((items) => items.map((item) => item.id === key ? {
        ...item,
        status: 'error',
        tone: 'error',
        detail: `${item.detail}\n结果拒绝：${message}`,
        meta: { ...item.meta, statusLabel: '结果被拒绝' },
      } : item.id === `${key}-result` ? {
        ...item,
        status: 'error',
        tone: 'error',
        detail: `${item.detail || ''}\n结果拒绝：${message}`,
        meta: { ...item.meta, statusLabel: '结果被拒绝', flow: 'execution-error' },
      } : item));
      addTimeline({
        type: event.type,
        title: '工具结果被拒绝',
        detail: `${key}\n${message}`,
        timestamp,
        tone: 'error',
        status: 'error',
      });
      return;
    }
    if (event.type === 'turn.completed') {
      const statusValue = textValue(envelope.status, 'completed');
      setRunning(false);
      activeTurnIdRef.current = '';
      setRunStatus(statusValue === 'completed' ? '运行完成' : statusValue === 'cancelled' ? '已取消' : '运行失败');
      addTimeline({ type: event.type, title: `回合${statusValue}`, detail: textValue(envelope.turnId), timestamp, tone: statusValue === 'completed' ? 'success' : 'error' });
      return;
    }
    if (event.type === 'error') {
      const message = textValue(envelope.message || envelope.error, 'Agent 返回错误');
      setConnectionError(message);
      const protocolError = [
        'UNSUPPORTED_PROTOCOL_VERSION',
        'PROTOCOL_INVALID',
        'BUNDLE_MISMATCH',
        'INVALID_CONTEXT',
        'STALE_SESSION',
      ].includes(textValue(envelope.code));
      if (protocolError) {
        setConnected(false);
        setConnecting(false);
      }
      setRunning(false);
      setRunStatus('运行失败');
      addTimeline({ type: event.type, title: 'Agent 错误', detail: message, timestamp, tone: 'error' });
      return;
    }
    if (event.type === 'session_started') {
      setConnected(true);
      setConnecting(false);
      setProfile(textValue(data.skillProfile));
      setProfiles(Array.isArray(data.skillProfiles) ? data.skillProfiles as SkillProfile[] : []);
      setSkillName(textValue(data.skillName, 'Main Agent Debug'));
      if (Array.isArray(data.quickPrompts)) {
        const configured = data.quickPrompts.filter((item): item is QuickPrompt => (
          !!item && typeof item === 'object'
          && typeof (item as QuickPrompt).label === 'string'
          && typeof (item as QuickPrompt).prompt === 'string'
          && (item as QuickPrompt).label.trim().length > 0
          && (item as QuickPrompt).prompt.trim().length > 0
        ));
        setQuickPrompts(configured.length ? configured : DEFAULT_QUICK_PROMPTS);
      }
      // 固定设备参数由平台共享配置提供；Agent 返回的上下文仅作为内部诊断信息。
      addTimeline({ type: event.type, title: '会话已建立', detail: textValue(data.skillProfile), timestamp, tone: 'success' });
      return;
    }
    if (event.type === 'session_reset') {
      setProfile(textValue(data.skillProfile));
      setProfiles(Array.isArray(data.skillProfiles) ? data.skillProfiles as SkillProfile[] : []);
      if (typeof data.skillName === 'string') setSkillName(data.skillName);
      if (Array.isArray(data.quickPrompts)) {
        const configured = data.quickPrompts.filter((item): item is QuickPrompt => (
          !!item && typeof item === 'object'
          && typeof (item as QuickPrompt).label === 'string'
          && typeof (item as QuickPrompt).prompt === 'string'
          && (item as QuickPrompt).label.trim().length > 0
          && (item as QuickPrompt).prompt.trim().length > 0
        ));
        setQuickPrompts(configured.length ? configured : DEFAULT_QUICK_PROMPTS);
      }
      setMessages([]); setTimeline([]); setExpanded(new Set());
      cancelActiveToolCalls();
      activeTurnIdRef.current = '';
      handledToolCallsRef.current.clear();
      setRunStatus('会话已重置'); setRunning(false); return;
    }
    if (event.type === 'run_started') {
      runStartedAt.current = Date.now(); setRunning(true); setRunStatus('正在运行');
      setMessages((items) => [...items, { role: 'user' as const, content: textValue(data.query), runId: event.runId, timestamp }].slice(-MAX_AGENT_MESSAGES));
      addTimeline({ type: event.type, title: '用户输入', detail: textValue(data.query), timestamp, tone: 'info', meta: { flow: 'user' } }); return;
    }
    if (event.type === 'assistant_message') {
      const content = textValue(data.content);
      setMessages((items) => [...items, { role: 'assistant' as const, content, runId: event.runId, timestamp }].slice(-MAX_AGENT_MESSAGES));
      addTimeline({ type: event.type, title: 'Agent 回复', detail: content, timestamp, tone: 'info', meta: { flow: 'assistant' } });
      return;
    }
    if (event.type === 'tool_call') {
      const args = parseArguments(data.arguments);
      const name = textValue(data.name, '未知工具');
      const functionName = textValue(data.functionName || args.functionName);
      const resourceId = textValue(data.resourceId || args.resourceId);
      const callId = textValue(data.callId) || undefined;
      // 旧版后端会把浏览器微服务请求适配成 underscore 事件。只要它是
      // invoke 白名单调用，就转换成同一条标准执行路径，避免旧入口一直
      // 等待 tool.result 而浏览器只显示一条静态时间线。
      const legacyOperation = name === 'invoke'
        ? textValue(args.functionName || args.operation || functionName)
        : '';
      if (legacyOperation && ALLOWED_TOOL_OPERATIONS.has(legacyOperation) && callId && event.runId) {
        processEvent({
          ...event,
          type: 'tool.call',
          data: {
            ...data,
            conversationId: event.sessionId,
            sessionId: event.sessionId,
            turnId: event.runId,
            runId: event.runId,
            callId,
            name: 'invoke',
            functionName: 'invoke',
            operation: legacyOperation,
            arguments: args,
          },
        });
        return;
      }
      const title = name === 'invoke' && functionName ? `工具请求 · ${name} · ${functionName}` : name === 'load_skill' && resourceId ? `工具请求 · ${name} · ${resourceId}` : `工具请求 · ${name}`;
      addTimeline({ type: event.type, title, detail: `参数:\n${prettyArguments(data.arguments)}`, timestamp, tone: 'warning', status: 'running', meta: { callId, toolName: name, resourceId, functionName, step: textValue(data.step), statusLabel: '运行中', flow: 'request' } }, callId);
      return;
    }
    if (event.type === 'tool_result') {
      const result = objectValue(data.result);
      const callId = textValue(data.callId); const name = textValue(data.functionName || data.name, '未知工具');
      if (callId) {
        setTimeline((items) => items.map((item) => item.id === callId ? {
          ...item,
          status: result.ok === false ? 'error' : 'success',
          tone: result.ok === false ? 'error' : 'success',
          meta: { ...item.meta, statusLabel: result.ok === false ? '执行失败' : '执行成功' },
        } : item));
      }
      const resultEntry = browserResultTimelineEntry(result as BrowserToolResult, name, callId || undefined);
      addTimeline(
        {
          ...resultEntry,
          type: event.type,
          meta: { ...resultEntry.meta, toolName: textValue(data.name), step: textValue(data.step) },
        },
        callId ? `${callId}-result` : undefined,
      );
      return;
    }
    if (event.type === 'upstream_frame') return;
    if (event.type === 'diagnostic') {
      const diagnosticMessage = textValue(data.message, event.error || jsonText(data));
      addTimeline({ type: event.type, title: textValue(data.kind, '诊断'), detail: diagnosticMessage, timestamp, tone: 'error' });
      if (event.error) setConnectionError(event.error);
      return;
    }
    if (event.type === 'artifact_preview') {
      const artifact: ArtifactRecord = {
        ...data,
        runId: event.runId ?? textValue(data.runId, 'renderer'),
        timestamp,
      };
      onArtifactRef.current?.(artifact);
      addTimeline({ type: event.type, title: 'Artifact 已转入卡片渲染', detail: event.runId ?? '', timestamp, tone: 'success' }); return;
    }
    if (event.type === 'run_completed' || event.type === 'run_failed' || event.type === 'run_cancelled') {
      setRunning(false); const failed = event.type === 'run_failed'; const cancelled = event.type === 'run_cancelled'; const status = failed ? '运行失败' : cancelled ? '已取消' : `完成 · ${Math.max(0, Date.now() - runStartedAt.current)} ms`; setRunStatus(status); addTimeline({ type: event.type, title: status, detail: jsonText(data), timestamp, tone: failed ? 'error' : 'success' });
    }
  }, [addTimeline, cancelActiveToolCalls]);

  const connect = useCallback(() => {
    cancelActiveToolCalls();
    socketRef.current?.close();
    handledToolCallsRef.current.clear();
    setConnecting(true);
    let socket: WebSocket;
    let resolvedUrl: string;
    try {
      resolvedUrl = resolveSocketUrl(socketPath);
      socket = new WebSocket(resolvedUrl);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setConnected(false);
      setConnecting(false);
      setConnectionError(`Agent 地址无效：${message}`);
      onEventRef.current?.({ direction: 'local', kind: 'connection_error', payload: { path: socketPath, error: message } });
      return;
    }
    socketRef.current = socket;
    const isCurrentSocket = () => socketRef.current === socket;
    socket.onopen = () => {
      if (!isCurrentSocket()) return;
      setConnected(false); setConnecting(true); setConnectionError('');
      onEventRef.current?.({ direction: 'local', kind: 'connected', payload: { path: socketPath } });
      // 标准 Agent 桥接协议先打开会话；兼容旧后端时该帧会被诊断事件吸收，后续
      // turn.start 仍由同一个入口处理。
      socket.send(JSON.stringify({
        type: 'conversation.open',
        protocolVersion: AGENT_PROTOCOL_VERSION,
        context: agentContext(configRef.current),
        bundleName: configRef.current?.bundleName,
      }));
    };
    socket.onclose = () => {
      if (!isCurrentSocket()) return;
      cancelActiveToolCalls();
      setConnected(false); setConnecting(false);
      onEventRef.current?.({ direction: 'local', kind: 'closed', payload: { path: socketPath } });
    };
    socket.onerror = () => {
      if (!isCurrentSocket()) return;
      setConnected(false); setConnecting(false); setConnectionError('无法连接到调试服务，请确认后端已启动。');
      onEventRef.current?.({ direction: 'local', kind: 'connection_error', payload: { path: socketPath } });
    };
    socket.onmessage = (message) => {
      if (!isCurrentSocket()) return;
      try {
        const event = JSON.parse(message.data) as DebugEvent;
        if (typeof event.type === 'string') processEvent(event);
      } catch {
        setConnectionError('收到无法解析的服务事件。');
      }
    };
  }, [cancelActiveToolCalls, processEvent, socketPath]);

  const refreshHealth = useCallback(() => {
    if (!healthPath.trim()) {
      setHealth({ status: 'unavailable' });
      return;
    }
    fetch(healthPath)
      .then((response) => response.json())
      .then((value) => setHealth(objectValue(value) as Health))
      .catch(() => setHealth({ status: 'unavailable' }));
  }, [healthPath]);
  useEffect(() => {
    connect();
    refreshHealth();
    return () => {
      cancelActiveToolCalls();
      socketRef.current?.close();
    };
  }, [cancelActiveToolCalls, connect, refreshHealth]);
  const send = (payload: Record<string, unknown>) => { if (socketRef.current?.readyState === WebSocket.OPEN) { onEventRef.current?.({ direction: 'send', kind: String(payload.type ?? 'message'), payload }); socketRef.current.send(JSON.stringify(payload)); } };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = input.trim();
    if (!value || running) return;
    const turnId = createTurnId();
    activeTurnIdRef.current = turnId;
    send({
      type: 'turn.start',
      protocolVersion: AGENT_PROTOCOL_VERSION,
      conversationId: sessionId || undefined,
      turnId,
      text: value,
      content: value,
    });
    lastUserTextRef.current = value;
    setInput('');
    setMobileTab('chat');
  };
  const keyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); submit(event); } };
  const filteredTimeline = useMemo(() => { const query = timelineSearch.trim().toLocaleLowerCase(); if (!query) return timeline; return timeline.filter((entry) => [entry.title, entry.detail, entry.type, entry.status, entry.meta?.statusLabel, entry.meta?.toolName, entry.meta?.resourceId, entry.meta?.functionName, entry.meta?.callId].filter(Boolean).join(' ').toLocaleLowerCase().includes(query)); }, [timeline, timelineSearch]);

  return <div className="e2e-debug app-shell">
    {connectionError && <p className="connection-error" role="alert">{connectionError}</p>}
    <div className="mobile-tabs"><button className={mobileTab === 'chat' ? 'active' : ''} onClick={() => setMobileTab('chat')}>对话</button><button className={mobileTab === 'timeline' ? 'active' : ''} onClick={() => setMobileTab('timeline')}>轨迹 <em>{timeline.length}</em></button></div>
    <main className="workspace">
      <aside className={`context-panel ${contextOpen ? 'open' : ''}`}>
        <div className="panel-heading"><div><span className="eyebrow">AGENT SESSION</span><h2>运行状态</h2></div><button className="collapse-button" onClick={() => setContextOpen(false)} aria-label="关闭状态">×</button></div>
        <div className="skill-card"><div className="skill-icon">{icon('spark')}</div><div><strong>{skillName}</strong><small>{profile || '标准 Agent 协议'}</small></div><span className={`check ${connected ? '' : 'offline'}`}>{connected ? '✓' : '·'}</span></div>
        <div className="compact-context"><span>会话</span><b>{sessionId ? sessionId.slice(0, 10) : '等待连接'}</b></div>
        <div className="health-card"><div><span className="group-label">Agent 状态</span><strong className={connected ? 'text-success' : ''}>{connecting ? '连接中…' : connected ? '已连接' : '未连接'}</strong><small className="health-detail">工具服务由浏览器直连</small></div><button className="icon-button small" onClick={refreshHealth} title="刷新 Agent 状态">{icon('refresh')}</button></div>
        {microserviceStatus && <div className="health-card microservice-health-card"><div><span className="group-label">当前微服务</span>{microserviceStatus}</div></div>}
        <button className="secondary-button context-reset" onClick={() => send({ type: 'conversation.reset', protocolVersion: AGENT_PROTOCOL_VERSION, conversationId: sessionId || undefined })}>新建会话</button>
      </aside>
      <section className={`chat-panel ${mobileTab === 'chat' ? 'mobile-visible' : ''}`}><div className="chat-heading"><div><span className="eyebrow">CONVERSATION</span><h1>创建一张卡片</h1></div><button className="context-toggle" onClick={() => setContextOpen(true)}>{icon('settings')} 状态</button></div><div className="message-list">{messages.length === 0 ? <div className="empty-chat"><div className="empty-icon">{icon('spark')}</div><h3>从一个想法开始</h3><p>描述你想创建的桌面卡片，Agent 会处理能力裁决、生成与校验。</p><div className="suggestions">{quickPrompts.map((item) => <button key={`${item.label}-${item.prompt}`} onClick={() => setInput(item.prompt)}>{item.label}</button>)}</div></div> : messages.map((message, index) => <div className={`message-row ${message.role}`} key={`${message.runId || 'm'}-${index}`}><div className="message-avatar">{message.role === 'assistant' ? icon('spark') : '用户'}</div><div className="message-bubble"><div className="message-meta">{message.role === 'assistant' ? 'Main Agent' : '用户'}<span>{message.runId ? message.runId.slice(0, 8) : ''}</span><time>{formatTime(message.timestamp)}</time></div><div className="message-content">{message.content}</div></div></div>)}</div><div className="composer-wrap"><div className="run-state"><span className={`state-dot ${running ? 'running' : runStatus === '运行失败' ? 'failed' : 'ready'}`} />{runStatus}{running && <button onClick={() => send({ type: 'turn.cancel', protocolVersion: AGENT_PROTOCOL_VERSION, conversationId: sessionId || undefined, turnId: activeTurnIdRef.current || undefined })}>取消运行</button>}</div><form className="composer" onSubmit={submit}><textarea value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={keyDown} placeholder="描述你想创建的卡片" rows={1} /><button className="send-button" disabled={!connected || running || !input.trim()} aria-label="发送">{icon('send')}</button></form><small className="composer-hint">Enter 发送 · Shift + Enter 换行</small></div></section>
      <aside className={`inspector-panel ${mobileTab !== 'chat' ? 'mobile-visible' : ''}`}><section className={`timeline-section ${mobileTab === 'timeline' ? 'mobile-visible' : ''}`}><div className="section-heading"><div><span className="eyebrow">ACTIVITY</span><h2>运行轨迹</h2></div><span className="counter">{filteredTimeline.length}/{timeline.length}</span></div><label className="timeline-search"><span className="sr-only">搜索运行轨迹</span><input value={timelineSearch} onChange={(event) => setTimelineSearch(event.target.value)} placeholder="搜索工具、resourceId、状态…" /></label><div className="timeline-list">{filteredTimeline.length === 0 ? <div className="small-empty">{timeline.length ? '没有匹配的运行轨迹' : '等待运行事件'}</div> : filteredTimeline.map((entry) => { const isExpanded = expanded.has(entry.id); const statusLabel = entry.meta?.statusLabel; const functionName = entry.meta?.functionName || ''; return <article className={`timeline-item ${isExpanded ? 'is-expanded' : ''}`} key={entry.id}><button className="timeline-item__header" type="button" aria-expanded={isExpanded} onClick={() => setExpanded((current) => { const next = new Set(current); next.has(entry.id) ? next.delete(entry.id) : next.add(entry.id); return next; })}><span className={`timeline-icon ${entry.tone}`}>{timelineGlyph(entry)}</span><span className="timeline-item__title"><strong>{entry.title}</strong>{functionName && <span className="timeline-inline-value" title={functionName}>{functionName}</span>}{statusLabel && <span className={`timeline-status ${entry.status || ''}`}>{statusLabel}</span>}</span><span className="timeline-item__chevron">{isExpanded ? '⌃' : '⌄'}</span></button><div className="timeline-item__body">{entry.meta && <div className="timeline-meta">{entry.meta.resourceId && <span>resourceId <b>{entry.meta.resourceId}</b></span>}{entry.meta.functionName && <span>functionName <b>{entry.meta.functionName}</b></span>}{entry.meta.callId && <span>callId <b>{entry.meta.callId.slice(0, 8)}</b></span>}{entry.meta.step && <span>step <b>{entry.meta.step}</b></span>}</div>}{entry.detail && <pre>{entry.detail}</pre>}<time>{formatTime(entry.timestamp)}</time></div></article>; })}</div></section></aside>
    </main>
  </div>;
}
