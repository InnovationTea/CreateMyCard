export type DebugModule = 'end-to-end' | 'interface' | 'renderer' | 'batch';

/** 正式微服务接口名称。平台层重复声明一份，避免业务子包反向依赖平台。 */
export type ToolOperation =
  | 'getWidgetCapabilityOverview'
  | 'getDataCapabilitySchemas'
  | 'generateWidgetCardCompactDsl';

export const TOOL_OPERATIONS: readonly ToolOperation[] = [
  'getWidgetCapabilityOverview',
  'getDataCapabilitySchemas',
  'generateWidgetCardCompactDsl',
] as const;

export type ToolCallSource = 'interface' | 'e2e';
export type ToolCallStatus = 'pending' | 'success' | 'error';

/** 微服务最终帧的宽松结构；平台保留服务返回的原始字段。 */
export type ToolFrame = {
  reply?: {
    streamInfo?: {
      streamType?: string;
      streamContent?: string;
      streamingTextId?: string;
      [key: string]: unknown;
    };
    [key: string]: unknown;
  };
  [key: string]: unknown;
};

export type ToolCallResponse = {
  requestId?: string;
  operation?: ToolOperation | string;
  status?: string;
  errorCode?: string;
  error?: unknown;
  data?: unknown;
  [key: string]: unknown;
};

/**
 * 共享的微服务调用历史。
 *
 * 中间 WebSocket 帧不应进入这个模型；调用方只在 final/final_error 到达后
 * 写入 response/rawResponse。这样历史可以在三个工作区之间安全复用。
 */
export type ToolCallRecord = {
  id: string;
  operation: ToolOperation;
  source: ToolCallSource;
  status: ToolCallStatus;
  startedAt: string;
  finishedAt?: string;
  /** 兼容旧调用方；新代码使用 finishedAt。 */
  completedAt?: string;
  durationMs?: number;
  request: Record<string, unknown>;
  finalFrame?: ToolFrame;
  finalStreamContent?: string;
  response?: ToolCallResponse;
  rawResponse?: unknown;
  error?: string;
  runId?: string;
  callId?: string;
};

export type ToolCallInput = Omit<ToolCallRecord, 'id'> & { id?: string };
export type ToolCallPatch = Partial<Omit<ToolCallRecord, 'id' | 'operation' | 'source'>>;

export type DebugConfig = {
  /** 自定义 Main Agent WebSocket 地址（可为相对路径或完整 ws(s) URL）。 */
  agentWsUrl: string;
  /** 三个微服务 WebSocket 的 base 地址，调用方按 operation 追加路径。 */
  toolWsBaseUrl: string;
  /** 端到端和接口调试使用的微服务来源，默认连接已部署服务。 */
  microserviceMode: 'deployed' | 'managed';
  /** 当前调试平台启动的本地受管微服务地址。 */
  managedServiceWsUrl: string;
  protocolVersion: string;
  bundleName: string;
  userId: string;
  deviceId: string;
  phoneType: string;
  appVersion: string;
  romVersion: string;
  locale: string;
  countryCode: string;
  deviceFormation: string;
  deviceType: number;
  sysVer: string;
  paginationLimit: number;
  paginationStart: string;
  /** 本地受管微服务的默认启动参数；批量任务可在创建时继承。 */
  managedServiceConfig: Record<string, string | number | boolean>;
};

export type DebugEvent = {
  id: string;
  channel: 'e2e' | 'tools' | 'renderer' | 'system';
  direction: 'send' | 'receive' | 'local';
  kind: string;
  timestamp: string;
  durationMs?: number;
  operation?: ToolOperation | string;
  callId?: string;
  runId?: string;
  payload?: unknown;
};

export type CardArtifact = {
  source: 'e2e' | 'interface' | 'import';
  runId?: string;
  artifactUrl?: string;
  artifactDigest?: string;
  genui?: string;
  cardSpec?: unknown;
  raw?: unknown;
};

export type WorkbenchContextValue = {
  events: DebugEvent[];
  pushEvent: (event: Omit<DebugEvent, 'id' | 'timestamp'> & { timestamp?: string }) => void;
  calls: ToolCallRecord[];
  selectedCallId: string | null;
  selectedCall: ToolCallRecord | null;
  recordCall: (call: ToolCallInput) => string;
  updateCall: (id: string, patch: ToolCallPatch) => void;
  beginCall: (call: Omit<ToolCallInput, 'status'> & { status?: 'pending' }) => string;
  finishCall: (id: string, patch: ToolCallPatch) => void;
  failCall: (id: string, error: string, patch?: ToolCallPatch) => void;
  selectCall: (id: string | null) => void;
  clearCalls: () => void;
  config: DebugConfig;
  updateConfig: (patch: Partial<DebugConfig>) => void;
  resetConfig: () => void;
  artifact: CardArtifact | null;
  setArtifact: (artifact: CardArtifact | null) => void;
};
