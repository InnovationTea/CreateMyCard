import type { DebugConfig } from './types';

export const DEBUG_CONFIG_VERSION = 1;
export const DEBUG_CONFIG_STORAGE_KEY = `ai-widget-debug-config:v${DEBUG_CONFIG_VERSION}`;
const LEGACY_DEBUG_CONFIG_STORAGE_KEY = 'ai-widget-debug-config';
export const CONFIG_STORAGE_KEY = DEBUG_CONFIG_STORAGE_KEY;
export const DEFAULT_TOOL_WS_BASE_URL = 'ws://127.0.0.1:8855/api/v1/ws/tools';
export const DEFAULT_AGENT_WS_URL = '/debug/e2e/ws';
export const DEFAULT_ASSET_BASE_URL = '/resources/';
export const DEFAULT_MANAGED_SERVICE_CONFIG: Record<string, string | number | boolean> = {
  enableA2uiModelMock: true,
  designCompactModelBackend: 'openai',
  openaiMasterClient: 'deepseek_official_http',
  openaiFallbackClient: 'llmclient',
  deepseekOfficialHttpModel: 'deepseek-flash',
  deepseekOfficialHttpTemperature: 0.7,
  deepseekOfficialHttpTopP: 0.9,
  deepseekOfficialHttpMaxTokens: 8192,
  deepseekOfficialHttpEnableThinking: false,
  enableModelFailureRetry: false,
  modelFailureMaxRetryAttempts: 1,
  fallbackModelFailureMaxRetryAttempts: 1,
  enableOpenaiFallback: true,
  enableValidationFailureRetry: false,
  validationFailureMaxRepairAttempts: 1,
  enableCompactDslInterfaceRetry: false,
  compactDslInterfaceRetryCount: 1,
};

type EndpointConfig = {
  agentWsUrl: string;
  toolWsBaseUrl: string;
};

/** 供仍未迁移到 Context 的独立模块读取的只读兼容快照。 */
export const endpointConfig: EndpointConfig = {
  agentWsUrl: DEFAULT_AGENT_WS_URL,
  toolWsBaseUrl: DEFAULT_TOOL_WS_BASE_URL,
};

export const defaultDebugConfig: DebugConfig = {
  agentWsUrl: DEFAULT_AGENT_WS_URL,
  toolWsBaseUrl: DEFAULT_TOOL_WS_BASE_URL,
  microserviceMode: 'deployed',
  managedServiceWsUrl: '',
  bundleName: 'com.omega_w_0823.hmservice',
  protocolVersion: '1.0',
  userId: 'debug-user',
  deviceId: 'debug-device',
  phoneType: 'ALN-AL00',
  appVersion: '11.9.9.342',
  romVersion: 'ALN-AL00 7.0.0.100',
  locale: 'zh-CN',
  countryCode: 'CN',
  deviceFormation: 'phone',
  deviceType: 0,
  sysVer: 'HarmonyOS',
  paginationLimit: 5,
  paginationStart: '',
  managedServiceConfig: { ...DEFAULT_MANAGED_SERVICE_CONFIG },
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value));
}

function stringValue(value: unknown, fallback: string): string {
  return typeof value === 'string' ? value.trim() : fallback;
}

function numberValue(value: unknown, fallback: number): number {
  if (typeof value !== 'number' && typeof value !== 'string') return fallback;
  if (typeof value === 'string' && !value.trim()) return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

/**
 * 将旧版 requestDefaults/endpoints 结构迁移成当前规范字段。
 * 动态 sessionId、interactionId 和 time 即使存在也会被忽略，不进入配置。
 */
export function normalizeDebugConfig(value: unknown): DebugConfig {
  const stored = isRecord(value) ? value : {};
  const source = isRecord(stored.config) ? stored.config : stored;
  const legacy = isRecord(source.requestDefaults) ? source.requestDefaults : {};
  const legacyEndpoints = isRecord(source.endpoints) ? source.endpoints : {};
  const pickString = (key: keyof DebugConfig, legacyKey?: string): string => (
    stringValue(source[key], stringValue(legacy[legacyKey ?? key], String(defaultDebugConfig[key] ?? '')))
  );
  const pickEndpoint = (key: 'agentWsUrl' | 'toolWsBaseUrl', ...legacyKeys: string[]): string => {
    const normalizeLegacyEndpoint = (value: string): string => {
      const trimmed = value.trim();
      // The old platform proxy lived at /debug/tools.  Keeping that path in a
      // migrated browser config would route calls to the deprecation endpoint,
      // so move the exact legacy default to the direct microservice base.
      if (key === 'toolWsBaseUrl' && /^\/debug\/tools\/?$/i.test(trimmed)) {
        return defaultDebugConfig.toolWsBaseUrl;
      }
      return trimmed;
    };
    if (typeof source[key] === 'string') {
      return normalizeLegacyEndpoint(source[key]);
    }
    for (const legacyKey of legacyKeys) {
      const valueFromEndpoints = legacyEndpoints[legacyKey];
      if (typeof valueFromEndpoints === 'string' && valueFromEndpoints.trim()) {
        return normalizeLegacyEndpoint(valueFromEndpoints);
      }
      const valueFromRoot = source[legacyKey];
      if (typeof valueFromRoot === 'string' && valueFromRoot.trim()) {
        return normalizeLegacyEndpoint(valueFromRoot);
      }
    }
    return defaultDebugConfig[key];
  };
  // Some early builds nested the canonical names under `endpoints`, while
  // others used the older `toolsBaseUrl`/`e2eSocketPath` aliases.  Read both
  // shapes so a refresh never silently switches a user's custom endpoint
  // back to localhost.
  const toolWsBaseUrl = pickEndpoint(
    'toolWsBaseUrl',
    'toolWsBaseUrl',
    'toolsBaseUrl',
    'toolsSocketPath',
  );
  const agentWsUrl = pickEndpoint('agentWsUrl', 'agentWsUrl', 'e2eSocketPath');
  const deviceType = Math.max(0, Math.floor(numberValue(source.deviceType, numberValue(legacy.deviceType, defaultDebugConfig.deviceType))));
  const paginationLimit = Math.max(1, Math.floor(numberValue(source.paginationLimit, defaultDebugConfig.paginationLimit)));
  const storedServiceConfig = isRecord(source.managedServiceConfig)
    ? source.managedServiceConfig
    : {};
  const managedServiceConfig = { ...DEFAULT_MANAGED_SERVICE_CONFIG };
  Object.entries(storedServiceConfig).forEach(([key, value]) => {
    if (key in managedServiceConfig
      && (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean')) {
      managedServiceConfig[key] = value;
    }
  });
  return {
    agentWsUrl,
    toolWsBaseUrl,
    microserviceMode: source.microserviceMode === 'managed' ? 'managed' : 'deployed',
    managedServiceWsUrl: pickString('managedServiceWsUrl'),
    bundleName: pickString('bundleName'),
    protocolVersion: stringValue(
      source.protocolVersion,
      stringValue(
        typeof source.version === 'string' ? source.version : undefined,
        pickString('protocolVersion', 'version'),
      ),
    ),
    userId: pickString('userId'),
    deviceId: pickString('deviceId'),
    phoneType: pickString('phoneType'),
    appVersion: pickString('appVersion', 'prdVer'),
    romVersion: pickString('romVersion'),
    locale: pickString('locale'),
    countryCode: pickString('countryCode'),
    deviceFormation: pickString('deviceFormation'),
    deviceType,
    sysVer: pickString('sysVer'),
    paginationLimit,
    paginationStart: pickString('paginationStart'),
    managedServiceConfig,
  };
}

export function cloneDebugConfig(config: DebugConfig): DebugConfig {
  return { ...config, managedServiceConfig: { ...config.managedServiceConfig } };
}

/** URL 中的 userinfo 或常见 query 凭据永远不写入本地持久化配置。 */
export function endpointHasCredentials(value: string): boolean {
  const normalized = value.trim();
  if (!normalized) return false;
  try {
    const parsed = /^(?:https?|wss?):\/\//i.test(normalized)
      ? new URL(normalized)
      : new URL(normalized, 'http://127.0.0.1');
    if (parsed.username || parsed.password) return true;
    // WebSocket/HTTP fragments are never sent to the server and are often
    // used accidentally for bearer material; reject them before persistence.
    if (parsed.hash) return true;
    for (const key of parsed.searchParams.keys()) {
      const normalizedKey = key.toLowerCase().replace(/[^a-z0-9]/g, '');
      if (/(?:token|apikey|secret|password|authorization|auth)/.test(normalizedKey)) {
        return true;
      }
    }
    return false;
  } catch {
    return false;
  }
}

function persistedConfig(config: DebugConfig): DebugConfig {
  const normalized = normalizeDebugConfig(config);
  return {
    ...normalized,
    // Keep the current in-memory value available for an immediate validation
    // message, while ensuring a reload can never recover URL credentials.
    agentWsUrl: endpointHasCredentials(normalized.agentWsUrl)
      ? defaultDebugConfig.agentWsUrl
      : normalized.agentWsUrl,
    toolWsBaseUrl: endpointHasCredentials(normalized.toolWsBaseUrl)
      ? defaultDebugConfig.toolWsBaseUrl
      : normalized.toolWsBaseUrl,
  };
}

export function loadDebugConfig(): DebugConfig {
  if (typeof localStorage === 'undefined') return cloneDebugConfig(defaultDebugConfig);
  try {
    const currentRaw = localStorage.getItem(DEBUG_CONFIG_STORAGE_KEY);
    const legacyRaw = currentRaw ? null : localStorage.getItem(LEGACY_DEBUG_CONFIG_STORAGE_KEY);
    const raw = currentRaw ?? legacyRaw;
    if (!raw) return cloneDebugConfig(defaultDebugConfig);
    const config = persistedConfig(normalizeDebugConfig(JSON.parse(raw)));
    // Rewrite the active key after every load so a legacy entry or a manually
    // edited URL containing credentials/hash fragments cannot remain in browser
    // storage after it has been read once.
    const serialized = JSON.stringify({ version: DEBUG_CONFIG_VERSION, config });
    if (currentRaw !== serialized || legacyRaw) {
      try {
        localStorage.setItem(DEBUG_CONFIG_STORAGE_KEY, serialized);
        if (legacyRaw) localStorage.removeItem(LEGACY_DEBUG_CONFIG_STORAGE_KEY);
      } catch {
        // A full or read-only storage must not discard the valid in-memory
        // configuration; it simply cannot complete the migration rewrite.
      }
    }
    return config;
  } catch {
    return cloneDebugConfig(defaultDebugConfig);
  }
}

export function saveDebugConfig(config: DebugConfig): void {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(DEBUG_CONFIG_STORAGE_KEY, JSON.stringify({
      version: DEBUG_CONFIG_VERSION,
      config: persistedConfig(config),
    }));
  } catch {
    // 隐私模式或配额不足时仍保留当前 React 会话中的配置。
  }
}

export function clearSavedDebugConfig(): void {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.removeItem(DEBUG_CONFIG_STORAGE_KEY);
    localStorage.removeItem(LEGACY_DEBUG_CONFIG_STORAGE_KEY);
  } catch { /* ignore storage errors */ }
}

export function applyDebugConfig(config: DebugConfig): void {
  endpointConfig.agentWsUrl = config.agentWsUrl;
  endpointConfig.toolWsBaseUrl = selectedToolWsBaseUrl(config);
}

export function selectedToolWsBaseUrl(config: DebugConfig): string {
  return config.microserviceMode === 'managed'
    ? config.managedServiceWsUrl
    : config.toolWsBaseUrl;
}

function ensureScheme(value: string, kind: 'http' | 'ws'): URL {
  const normalized = value.trim();
  if (!normalized) throw new Error('地址不能为空');
  if (normalized.startsWith('//')) throw new Error('地址协议无效');
  if (/^[A-Za-z][A-Za-z0-9+.-]*:/.test(normalized)
    && !/^(?:https?|wss?):\/\//i.test(normalized)) {
    throw new Error('地址协议无效');
  }
  const isHttp = /^https?:\/\//i.test(normalized);
  const isWebSocket = /^wss?:\/\//i.test(normalized);
  let url: URL;
  if (kind === 'ws' && isHttp) {
    url = new URL(normalized.replace(/^http:/i, 'ws:').replace(/^https:/i, 'wss:'));
  } else if (kind === 'http' && isWebSocket) {
    url = new URL(normalized.replace(/^ws:/i, 'http:').replace(/^wss:/i, 'https:'));
  } else if (isHttp || isWebSocket) {
    url = new URL(normalized);
  } else if (typeof window === 'undefined') {
    url = new URL(`${kind === 'ws' ? 'ws' : 'http'}://127.0.0.1:8888/${normalized.replace(/^\/+/, '')}`);
  } else {
    const scheme = kind === 'ws'
      ? window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      : window.location.protocol === 'https:' ? 'https:' : 'http:';
    const host = window.location.host || '127.0.0.1:8888';
    url = new URL(`${scheme}//${host}/${normalized.replace(/^\/+/, '')}`);
  }
  if (url.username || url.password) throw new Error('地址不能包含认证信息');
  return url;
}

function rejectMixedContent(url: URL): void {
  if (url.hash) throw new Error('地址不能包含 hash 片段');
  if (typeof window !== 'undefined' && window.location.protocol === 'https:' && url.protocol === 'ws:') {
    throw new Error('HTTPS 页面不能连接不安全的 ws 地址');
  }
}

export function websocketUrl(path: string): string {
  const url = ensureScheme(path, 'ws');
  if (!['ws:', 'wss:'].includes(url.protocol) || !url.hostname) throw new Error('地址必须使用 ws/wss 协议');
  rejectMixedContent(url);
  return url.toString();
}

export function httpUrl(path: string): string {
  const url = ensureScheme(path, 'http');
  if (!['http:', 'https:'].includes(url.protocol) || !url.hostname) throw new Error('地址必须使用 http/https 协议');
  if (url.hash) throw new Error('地址不能包含 hash 片段');
  if (typeof window !== 'undefined' && window.location.protocol === 'https:' && url.protocol === 'http:') {
    throw new Error('HTTPS 页面不能连接不安全的 http 地址');
  }
  return url.toString();
}
