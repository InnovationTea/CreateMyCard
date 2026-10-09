/**
 * 三个微服务共用的浏览器请求包络构造器。
 *
 * 这个文件不依赖 React，平台壳、接口调试器和端到端工具桥可以使用完全
 * 相同的字段映射；会话 ID、交互 ID 和设备时间始终在调用时生成。
 */

export interface ToolEnvelopeConfig {
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

export interface ToolEnvelopeCorrelation {
  sessionId?: string;
  interactionId?: string;
  utterance?: string;
}

/**
 * These keys belong to the transport envelope, not to a microservice's
 * business payload.  Dropping them here prevents an old form/clipboard JSON
 * value from overriding the shared configuration on the wire.
 */
const ENVELOPE_FIELDS = [
  'bundleName',
  'contentBundleName',
  'uid',
  'odid',
  'userId',
  'deviceId',
  'phoneType',
  'appVersion',
  'prdVer',
  'romVersion',
  'locale',
  'countryCode',
  'deviceFormation',
  'deviceType',
  'sysVer',
  'time',
  'deviceInfo',
  'pagination',
  'paginationLimit',
  'paginationStart',
  'limit',
  'start',
  'session',
  'sessionId',
  'interactionId',
  'requestId',
  'streamingTextId',
  'callId',
  'runId',
  'userAuth',
  'utterance',
  'version',
  'protocolVersion',
] as const;

function createClientId(prefix: string): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function deviceTime(): string {
  return new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 17);
}

export function buildToolEnvelope(
  config: ToolEnvelopeConfig | undefined,
  business: Record<string, unknown>,
  correlation: ToolEnvelopeCorrelation = {},
): Record<string, unknown> {
  const deviceId = config?.deviceId ?? 'debug-device';
  const userId = config?.userId ?? 'debug-user';
  const content = { ...business };
  ENVELOPE_FIELDS.forEach((key) => delete content[key]);
  const sessionId = correlation.sessionId || createClientId('session');
  const interactionId = correlation.interactionId || createClientId('interaction');
  const utterance = correlation.utterance
    ?? (typeof business.userQuery === 'string' ? business.userQuery : '');
  const rawDeviceType = Number(config?.deviceType);
  const deviceType = Number.isFinite(rawDeviceType) && rawDeviceType >= 0
    ? Math.floor(rawDeviceType)
    : 0;
  const rawPaginationLimit = Number(config?.paginationLimit);
  const paginationLimit = Number.isFinite(rawPaginationLimit) && rawPaginationLimit > 0
    ? Math.floor(rawPaginationLimit)
    : 5;
  return {
    content: { ...content, uid: userId, odid: deviceId },
    deviceInfo: {
      countryCode: config?.countryCode ?? 'CN',
      deviceFormation: config?.deviceFormation ?? 'phone',
      deviceType,
      locale: config?.locale ?? 'zh-CN',
      phoneType: config?.phoneType ?? 'ALN-AL00',
      prdVer: config?.appVersion ?? '11.9.9.342',
      sysVer: config?.sysVer ?? 'HarmonyOS',
      romVersion: config?.romVersion ?? 'ALN-AL00 7.0.0.100',
      deviceId,
      time: deviceTime(),
    },
    pagination: {
      limit: paginationLimit,
      start: config?.paginationStart ?? '',
    },
    session: { sessionId, interactionId, isNew: false },
    userAuth: { user: { userId } },
    utterance: { original: utterance, type: 'text' },
    version: config?.protocolVersion ?? '1.0',
    bundleName: config?.bundleName ?? 'com.omega_w_0823.hmservice',
  };
}
