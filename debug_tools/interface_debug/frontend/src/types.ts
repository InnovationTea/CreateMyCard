import type { ReactNode } from 'react';

/** WebSocket 工具接口名称。保持与服务端路由和来源调试器一致。 */
export type ToolOperation =
  | 'getWidgetCapabilityOverview'
  | 'getDataCapabilitySchemas'
  | 'generateWidgetCardCompactDsl';

export const TOOL_OPERATIONS: readonly ToolOperation[] = [
  'getWidgetCapabilityOverview',
  'getDataCapabilitySchemas',
  'generateWidgetCardCompactDsl',
] as const;

export type StreamType = 'start' | 'partial' | 'final' | 'final_error' | 'command' | 'unknown';

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = Record<string, unknown>;

export interface ToolStreamInfo {
  streamType?: string;
  streamContent?: string;
  [key: string]: unknown;
}

/** 原样保留服务端工具帧，避免调试器丢失协议字段。 */
export interface ToolFrame {
  reply?: {
    streamInfo?: ToolStreamInfo;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface ToolFrameRecord {
  id: string;
  type: StreamType;
  timestamp: string;
  data: ToolFrame;
}

export interface CommonEnvelopeState {
  sessionId: string;
  interactionId: string;
  userId: string;
  bundleName: string;
  version: string;
  utterance: string;
  countryCode: string;
  deviceFormation: string;
  deviceType: number;
  locale: string;
  phoneType: string;
  prdVer: string;
  sysVer: string;
  romVersion: string;
  time: string;
}

export interface InterfaceArtifact {
  runId: string;
  operation: ToolOperation;
  raw: unknown;
  genui?: string;
  cardSpec?: unknown;
  artifactUrl?: string;
  artifactDigest?: string;
}

export interface HistoryEntry {
  id: number;
  timestamp: string;
  operation: ToolOperation;
  request: JsonObject;
  frames: ToolFrameRecord[];
  parsedResult: unknown;
  rawStreamContent: string;
  sourceHistoryId?: number;
}

export interface Selection {
  historyId: number;
  operation: ToolOperation;
  path: string;
  key: string;
  value: unknown;
}

export interface InterfaceEvent {
  direction: 'send' | 'receive' | 'local';
  kind: string;
  operation?: ToolOperation;
  payload?: unknown;
  timestamp?: string;
}

export interface InterfaceDebuggerProps {
  /** Full ws URL or a path such as `/debug/tools`; operation is appended automatically. */
  transportBase?: string;
  /** Backwards-compatible alias used by the first platform shell. */
  socketBasePath?: string;
  config?: InterfaceDebugConfig;
  selectedCall?: SharedToolCallRecord | null;
  onCallStart?: (input: { operation: ToolOperation; request: JsonObject; runId?: string; callId?: string }) => string | undefined;
  onCallFinish?: (id: string | undefined, result: SharedToolCallResult) => void;
  onCallFail?: (id: string | undefined, error: string) => void;
  onEvent?: (event: InterfaceEvent) => void;
  onArtifact?: (artifact: InterfaceArtifact) => void;
  className?: string;
  microserviceStatus?: ReactNode;
}

/** 平台配置的结构化子集，允许接口子包单独运行。 */
export interface InterfaceDebugConfig {
  bundleName?: string;
  protocolVersion?: string;
  userId?: string;
  deviceId?: string;
  phoneType?: string;
  appVersion?: string;
  romVersion?: string;
  locale?: string;
  countryCode?: string;
  deviceFormation?: string;
  deviceType?: number;
  sysVer?: string;
  paginationLimit?: number;
  paginationStart?: string;
}

export interface SharedToolCallRecord {
  id: string;
  operation: string;
  status?: 'pending' | 'success' | 'error' | string;
  finishedAt?: string;
  request?: unknown;
  finalFrame?: unknown;
  finalStreamContent?: string;
  response?: SharedToolCallResult;
  error?: string;
}

export interface SharedToolCallResult {
  requestId?: string;
  operation?: string;
  status?: string;
  errorCode?: string;
  error?: unknown;
  data?: unknown;
  finalFrame?: ToolFrame;
  finalStreamContent?: string;
  [key: string]: unknown;
}

export interface ToolStatus {
  state: 'ready' | 'connecting' | 'connected' | 'closed' | 'error';
  text: string;
}

export interface ToolOperationConfig {
  label: string;
  fields: FieldConfig[];
}

export type FieldType = 'text' | 'textarea' | 'select' | 'checkbox';

export interface FieldConfig {
  id: string;
  label: string;
  type: FieldType;
  required?: boolean;
  placeholder?: string;
  help?: string;
  default?: string | boolean;
  options?: string[];
}
