export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

export interface DebugEvent {
  type: string;
  sequence?: number;
  sessionId?: string;
  runId?: string;
  timestamp?: string;
  data?: Record<string, unknown>;
  error?: string;
}

export interface ContextValues {
  uid: string;
  odid: string;
  deviceId: string;
  phoneType: string;
  appVersion: string;
  romVersion: string;
  locale: string;
  countryCode: string;
  deviceFormation?: string;
  deviceType?: number;
  sysVer?: string;
  paginationLimit?: number;
  paginationStart?: string;
}

/** 平台共享配置的结构化子集。保持子包可独立构建，不反向依赖平台。 */
export interface SharedDebugConfig {
  agentWsUrl?: string;
  toolWsBaseUrl?: string;
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

export interface BrowserToolResult {
  ok: boolean;
  operation: string;
  requestId?: string;
  status?: string;
  errorCode?: string;
  error?: unknown;
  data?: unknown;
  finalFrame?: Record<string, unknown>;
  finalStreamContent?: string;
  [key: string]: unknown;
}

export interface SkillProfile {
  id: string;
  name?: string;
  displayName?: string;
  description?: string;
}

export interface QuickPrompt {
  label: string;
  prompt: string;
}

export interface ArtifactRecord {
  runId: string;
  timestamp?: string;
  artifactUrl?: string;
  artifactDigest?: string;
  genui?: string;
  cardSpec?: unknown;
  taskSpec?: unknown;
  effectiveCapabilities?: unknown;
  removedCapabilities?: unknown;
  generationPlan?: unknown;
  meta?: unknown;
  designToken?: unknown;
  [key: string]: unknown;
}

export type TimelineStatus = 'running' | 'success' | 'error' | 'result-error';

export interface TimelineMeta {
  callId?: string;
  toolName?: string;
  resourceId?: string;
  functionName?: string;
  step?: string;
  statusLabel?: string;
  flow?: 'request' | 'result' | 'execution-error' | 'business-error' | 'user' | 'assistant';
}

export interface TimelineEntry {
  id: string;
  type: string;
  title: string;
  detail?: string;
  timestamp?: string;
  tone: 'neutral' | 'success' | 'warning' | 'error' | 'info';
  status?: TimelineStatus;
  meta?: TimelineMeta;
}
