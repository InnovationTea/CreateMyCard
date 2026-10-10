import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { buildDefaultArguments, buildOutputFieldPaths, buildSelectedSubset, extractArtifact, findFinalFrame, finalResponseMetadataError, frameRequestIds, getAtPath, hasErrorCode, isToolResponseRecord, optionalStringField, parseLegacyToolResponse, parsePythonRepr, streamContent, streamType, unwrapToolResponseRecord } from './parser';
import { connectToolSocket, type ToolSocket } from './transport';
import { buildToolEnvelope } from './envelope';
import type {
  FieldConfig,
  InterfaceArtifact,
  InterfaceDebuggerProps,
  Selection,
  ToolFrame,
  ToolFrameRecord,
  ToolOperation,
  InterfaceDebugConfig,
  SharedToolCallRecord,
  SharedToolCallResult,
} from './types';
import { TOOL_OPERATIONS } from './types';
import './styles.css';

const OPERATION_LABELS: Record<ToolOperation, string> = {
  getWidgetCapabilityOverview: '能力概览',
  getDataCapabilitySchemas: '数据 Schema',
  generateWidgetCardCompactDsl: '生成 Compact DSL',
};

function createClientId(prefix: string): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

const BUSINESS_FIELDS: Record<ToolOperation, FieldConfig[]> = {
  getWidgetCapabilityOverview: [
  ],
  getDataCapabilitySchemas: [
    { id: 'dataCapabilityIds', label: 'Data Capability IDs', type: 'text', required: true, placeholder: 'ViewWeather,GetCalendarEvents' },
  ],
  generateWidgetCardCompactDsl: [
    { id: 'userQuery', label: 'User Query', type: 'text', required: true, placeholder: '帮我做通勤卡片，包含天气' },
    { id: 'title', label: 'Title', type: 'text', required: true, placeholder: '通勤日常' },
    { id: 'description', label: 'Description', type: 'text', required: true, placeholder: '天气速览' },
    { id: 'size', label: 'Size', type: 'select', default: '2x2', options: ['2x2', '2x4'] },
    { id: 'sourceArtifactUrl', label: 'Source Artifact URL', type: 'text', placeholder: '编辑模式可填写' },
    { id: 'candidateAssetIds', label: 'Candidate Asset IDs', type: 'text', placeholder: 'asset.drop_1,asset.clock_fill' },
    { id: 'candidateDataBindings', label: 'Candidate Data Bindings', type: 'textarea', placeholder: '{"capabilityId":"ViewWeather"}' },
    { id: 'candidateEventCandidates', label: 'Candidate Event Candidates', type: 'textarea', placeholder: '[{"capabilityId":"event.open"}]' },
    { id: 'allowDegradation', label: 'Allow Degradation', type: 'checkbox', default: true },
  ],
};

type BusinessValues = Record<string, string>;

function businessDefaults(operation: ToolOperation): BusinessValues {
  const values: BusinessValues = {};
  BUSINESS_FIELDS[operation].forEach((field) => { values[field.id] = String(field.default ?? ''); });
  return values;
}

function businessValuesFromRequest(operation: ToolOperation, request: Record<string, unknown>): BusinessValues {
  const values = businessDefaults(operation);
  const rawContent = request.content;
  let parsedContent: unknown = rawContent;
  if (typeof rawContent === 'string') {
    try { parsedContent = JSON.parse(rawContent) as unknown; } catch { parsedContent = rawContent; }
  }
  const content = parsedContent && typeof parsedContent === 'object' && !Array.isArray(parsedContent)
    ? parsedContent as Record<string, unknown>
    : request;
  const options = content.options && typeof content.options === 'object' && !Array.isArray(content.options)
    ? content.options as Record<string, unknown>
    : request.options && typeof request.options === 'object' && !Array.isArray(request.options)
      ? request.options as Record<string, unknown>
      : {};
  BUSINESS_FIELDS[operation].forEach((field) => {
    const raw = field.id === 'allowDegradation' ? options[field.id] : content[field.id];
    if (raw === undefined || raw === null) return;
    if (field.id === 'allowDegradation') {
      values[field.id] = raw === true || raw === 'true' ? 'true' : 'false';
      return;
    }
    if (field.id === 'dataCapabilityIds' || field.id === 'candidateAssetIds') {
      values[field.id] = Array.isArray(raw) ? raw.map(String).join(',') : String(raw);
      return;
    }
    values[field.id] = typeof raw === 'string' ? raw : jsonText(raw);
  });
  return values;
}

function jsonText(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function buildEnvelope(operation: ToolOperation, business: unknown, config?: InterfaceDebugConfig): Record<string, unknown> {
  void operation;
  const content = business && typeof business === 'object' && !Array.isArray(business)
    ? { ...(business as Record<string, unknown>) }
    : {};
  return buildToolEnvelope(config, content, {
    utterance: typeof content.userQuery === 'string' ? content.userQuery : '',
  });
}

function defaultBusiness(operation: ToolOperation, raw: string, formValues: BusinessValues): unknown {
  if (raw.trim()) {
    try {
      return JSON.parse(raw);
    } catch {
      return { userQuery: raw };
    }
  }
  const missing = BUSINESS_FIELDS[operation].find((field) => field.required && !(formValues[field.id] ?? '').trim());
  if (missing) throw new Error(`${missing.label} 为必填项`);
  const result: Record<string, unknown> = {};
  BUSINESS_FIELDS[operation].forEach((field) => {
    const value = (formValues[field.id] ?? '').trim();
    if (!value) return;
    if (field.type === 'textarea') {
      try { result[field.id] = JSON.parse(value) as unknown; } catch { result[field.id] = value; }
    } else if (field.id === 'allowDegradation') {
      result.options = { allowDegradation: value === 'true' };
    } else if (field.id === 'dataCapabilityIds' || field.id === 'candidateAssetIds') {
      result[field.id] = value.split(',').map((item) => item.trim()).filter(Boolean);
    } else {
      result[field.id] = value;
    }
  });
  if (operation === 'getWidgetCapabilityOverview') return result;
  if (operation === 'getDataCapabilitySchemas') return { dataCapabilityIds: [], ...result };
  return {
    userQuery: '创建一个天气卡片',
    title: '天气',
    description: '本地调试卡片',
    size: '2x2',
    ...result,
  };
}

function displayFrame(frame: ToolFrameRecord): string {
  return `${frame.type.toUpperCase()}\n${jsonText(frame.data)}`;
}

function Tree({ value, path, selected, onToggle, arrayLimits, onArrayLimit }: {
  value: unknown;
  path: string;
  selected: Set<string>;
  onToggle: (path: string, value: unknown) => void;
  arrayLimits: Record<string, number>;
  onArrayLimit: (path: string, value: number) => void;
}) {
  if (value === null || typeof value !== 'object') {
    return <label className="tree-leaf"><input type="checkbox" checked={selected.has(path)} onChange={() => onToggle(path, value)} /> <code>{path || '/'}</code><span>{String(value)}</span></label>;
  }
  const entries = Array.isArray(value)
    ? value.slice(0, arrayLimits[path] ?? 20).map((item, index) => [String(index), item] as const)
    : Object.entries(value as Record<string, unknown>);
  return <div className="tree-node">{Array.isArray(value) && value.length > 20 && <label className="array-limit">展开数组项 <input type="number" min={1} max={100} value={arrayLimits[path] ?? 20} onChange={(event) => onArrayLimit(path, Math.min(100, Math.max(1, Number(event.target.value) || 1)))} /></label>}{entries.map(([key, child]) => {
    const childPath = path ? `${path}.${key}` : key;
    return <details open key={childPath}><summary><span>{key}</span></summary><Tree value={child} path={childPath} selected={selected} onToggle={onToggle} arrayLimits={arrayLimits} onArrayLimit={onArrayLimit} /></details>;
  })}</div>;
}

export function InterfaceDebugger({
  transportBase,
  socketBasePath,
  config,
  selectedCall,
  onCallStart,
  onCallFinish,
  onCallFail,
  onEvent,
  onArtifact,
  microserviceStatus,
  className = '',
}: InterfaceDebuggerProps) {
  const [operation, setOperation] = useState<ToolOperation>(TOOL_OPERATIONS[0]);
  const [businessText, setBusinessText] = useState('');
  const [businessValues, setBusinessValues] = useState<BusinessValues>(() => businessDefaults(TOOL_OPERATIONS[0]));
  const [frames, setFrames] = useState<ToolFrameRecord[]>([]);
  const [activeHistory, setActiveHistory] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<'parsed' | 'build' | 'raw'>('parsed');
  const [requestPreview, setRequestPreview] = useState<Record<string, unknown> | null>(null);
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(new Set());
  const [builtJson, setBuiltJson] = useState('');
  const [status, setStatus] = useState('就绪');
  const [search, setSearch] = useState('');
  const [arrayLimits, setArrayLimits] = useState<Record<string, number>>({});
  const socketRef = useRef<ToolSocket | null>(null);
  const startedAtRef = useRef(0);
  const nextHistoryIdRef = useRef(1);
  const sharedCallIdRef = useRef<string | undefined>();
  const onCallFailRef = useRef(onCallFail);

  useEffect(() => {
    onCallFailRef.current = onCallFail;
  }, [onCallFail]);

  useEffect(() => () => {
    socketRef.current?.close();
    if (sharedCallIdRef.current) {
      onCallFailRef.current?.(sharedCallIdRef.current, '接口调试模块已关闭');
      sharedCallIdRef.current = undefined;
    }
  }, []);

  const parsedResult = useMemo(() => {
    const final = findFinalFrame(frames.map((frame) => frame.data));
    if (!final) return null;
    const content = streamContent(final);
    if (content.trim()) {
      const parsed = parsePythonRepr(content);
      return parsed ?? (streamType(final) === 'final_error' ? { error: content } : null);
    }
    if (final.data !== undefined) return final.data;
    if (streamType(final) === 'final_error') {
      const error = final.error ?? final.errorMessage ?? final.errorCode ?? 'final_error';
      return { error };
    }
    return null;
  }, [frames]);

  useEffect(() => {
    if (!selectedCall) {
      setFrames([]);
      setBusinessText('');
      setRequestPreview(null);
      setActiveHistory(null);
      setSelectedPaths(new Set());
      setArrayLimits({});
      setBuiltJson('');
      return;
    }
    const selectedOperation = TOOL_OPERATIONS.includes(selectedCall.operation as ToolOperation)
      ? selectedCall.operation as ToolOperation
      : operation;
    if (selectedOperation !== operation) setOperation(selectedOperation);
    const request = selectedCall.request && typeof selectedCall.request === 'object'
      ? selectedCall.request as Record<string, unknown>
      : {};
    setRequestPreview(request);
    const finalFrame = selectedCall.finalFrame && typeof selectedCall.finalFrame === 'object'
      ? selectedCall.finalFrame as ToolFrame
      : undefined;
    setFrames([]);
    if (finalFrame) {
      setFrames([{
        id: selectedCall.id,
        type: streamType(finalFrame) as ToolFrameRecord['type'],
        timestamp: new Date().toISOString(),
        data: finalFrame,
      }]);
    } else if (selectedCall.finalStreamContent !== undefined) {
      setFrames([{
        id: selectedCall.id,
        type: selectedCall.status === 'error' ? 'final_error' : 'final',
        timestamp: selectedCall.finishedAt ?? new Date().toISOString(),
        data: {
          reply: {
            streamInfo: {
              streamType: selectedCall.status === 'error' ? 'final_error' : 'final',
              streamContent: selectedCall.finalStreamContent,
            },
          },
        },
      }]);
    } else if (selectedCall.response || selectedCall.error) {
      const syntheticType = selectedCall.status === 'error' ? 'final_error' : 'final';
      const syntheticContent = selectedCall.response ?? { error: selectedCall.error };
      setFrames([{
        id: selectedCall.id,
        type: syntheticType,
        timestamp: selectedCall.finishedAt ?? new Date().toISOString(),
        data: {
          reply: {
            streamInfo: {
              streamType: syntheticType,
              streamContent: jsonText(syntheticContent),
            },
          },
        },
      }]);
    }
    // Shared history stores the complete envelope.  Rehydrate the known
    // business fields into the primary form so selecting a call is immediately
    // editable; the advanced JSON editor remains an explicit escape hatch.
    setBusinessValues(businessValuesFromRequest(selectedOperation, request));
    setBusinessText('');
    setActiveHistory(null);
    setSelectedPaths(new Set());
    setArrayLimits({});
    setBuiltJson('');
    setActiveTab('parsed');
  }, [selectedCall]);

  const filteredResult = useMemo(() => {
    if (!search.trim() || parsedResult == null) return parsedResult;
    const needle = search.toLowerCase();
    const filter = (value: unknown): unknown => {
      if (value == null || typeof value !== 'object') return String(value).toLowerCase().includes(needle) ? value : undefined;
      if (Array.isArray(value)) return value.map(filter).filter((item) => item !== undefined);
      const result: Record<string, unknown> = {};
      Object.entries(value).forEach(([key, child]) => {
        const filtered = filter(child);
        if (key.toLowerCase().includes(needle) || filtered !== undefined) result[key] = filtered ?? child;
      });
      return Object.keys(result).length ? result : undefined;
    };
    return filter(parsedResult);
  }, [parsedResult, search]);

  const send = () => {
    let business: unknown;
    try {
      business = defaultBusiness(operation, businessText, businessValues);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
      return;
    }
    const envelope = buildEnvelope(operation, business, config);
    const nextFrames: ToolFrameRecord[] = [];
    setFrames(nextFrames);
    setRequestPreview(envelope);
    setSelectedPaths(new Set());
    setBuiltJson('');
    setArrayLimits({});
    setActiveTab('parsed');
    setStatus('连接中…');
    startedAtRef.current = performance.now();
    if (sharedCallIdRef.current) {
      onCallFail?.(sharedCallIdRef.current, '调用被新的请求取消');
      sharedCallIdRef.current = undefined;
    }
    socketRef.current?.close();
    const sharedCallId = onCallStart?.({ operation, request: envelope });
    sharedCallIdRef.current = sharedCallId;
    let finalHandled = false;
    const socket = connectToolSocket(transportBase ?? socketBasePath, operation, envelope, {
      onFrame: (frame) => {
        if (finalHandled) return;
        finalHandled = true;
        const record: ToolFrameRecord = { id: createClientId('frame'), type: streamType(frame) as ToolFrameRecord['type'], timestamp: new Date().toISOString(), data: frame };
        nextFrames.push(record);
        setFrames([...nextFrames]);
        const kind = streamType(frame);
        const stream = streamContent(frame);
        const parsedValue = parsePythonRepr(stream);
        const parsed = parsedValue
          ?? (!stream && frame.data !== undefined ? frame.data : undefined)
          ?? (kind === 'final_error' && stream ? { error: stream } : null);
        const legacyResponse = parseLegacyToolResponse(stream);
        const parsedRecord = parsed && typeof parsed === 'object' && !Array.isArray(parsed)
          ? parsed as Record<string, unknown>
          : null;
        const response = legacyResponse ?? (parsedRecord && isToolResponseRecord(parsedRecord)
          ? unwrapToolResponseRecord(parsedRecord) as SharedToolCallResult
          : { status: kind, data: parsed, error: kind === 'final_error' ? stream : undefined });
        const expectedRequestId = `${String((envelope.session as Record<string, unknown>).sessionId ?? '')}&${String((envelope.session as Record<string, unknown>).interactionId ?? '')}`;
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
          response as Record<string, unknown>,
          frame,
          operation,
          expectedRequestId,
        );
        const responseStatus = typeof response.status === 'string' ? response.status.toLowerCase() : '';
        const responseStreamType = typeof response.streamType === 'string'
          ? response.streamType.toLowerCase()
          : '';
        const responseType = typeof response.type === 'string' ? response.type.toLowerCase() : '';
        const responseErrorCode = response.errorCode === undefined || response.errorCode === null
          ? outerError
          : String(response.errorCode);
        const failed = kind === 'final_error' || Boolean(validationError || metadataError)
          || ['failed', 'error', 'final_error'].includes(responseStatus)
          || responseStreamType === 'final_error'
          || responseType === 'final_error'
          || hasErrorCode(responseErrorCode)
          || response.ok === false;
        const normalizedResponse: SharedToolCallResult = {
          ...response,
          operation,
          status: failed ? 'error' : 'success',
          errorCode: responseErrorCode || undefined,
          error: validationError || metadataError || response.error || (kind === 'final_error'
            ? (typeof frame.error === 'string' && frame.error.trim()
              ? frame.error
              : typeof frame.errorMessage === 'string' && frame.errorMessage.trim()
                ? frame.errorMessage
                : stream.trim())
              || (hasErrorCode(responseErrorCode) ? `服务返回错误码：${responseErrorCode}` : '服务返回 final_error')
            : hasErrorCode(responseErrorCode)
              ? `服务返回错误码：${responseErrorCode}`
              : undefined),
        };
        setStatus(failed ? '调用失败' : `已完成 · ${Math.max(0, Math.round(performance.now() - startedAtRef.current))} ms`);
        const artifact = extractArtifact(parsed, operation, record.id) as InterfaceArtifact;
        if (!failed) onArtifact?.(artifact);
        const id = nextHistoryIdRef.current++;
        setActiveHistory(id);
        onCallFinish?.(sharedCallId, {
          ...normalizedResponse,
          finalFrame: frame,
          finalStreamContent: stream,
        });
        if (sharedCallIdRef.current === sharedCallId) sharedCallIdRef.current = undefined;
        window.setTimeout(() => socket.close(), 50);
      },
      onStatus: (next) => {
        setStatus(next.text);
        if (next.state === 'error') {
          onCallFail?.(sharedCallId, next.text);
          if (sharedCallIdRef.current === sharedCallId) sharedCallIdRef.current = undefined;
        }
      },
      onEvent,
    });
    socketRef.current = socket;
  };

  const toggleSelection = (path: string, value: unknown) => {
    setSelectedPaths((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path); else next.add(path);
      if (parsedResult && path) {
        const selections: Selection[] = [...next].map((item) => ({ historyId: activeHistory ?? 0, operation, path: item, key: item.split('.').pop() ?? item, value: getAtPath(parsedResult, item) }));
        setBuiltJson(jsonText(buildSelectedSubset(parsedResult, selections)));
      }
      return next;
    });
  };

  const buildQuick = (kind: 'selected' | 'data' | 'assets' | 'events' | 'bindings') => {
    if (!parsedResult) return;
    const selections: Selection[] = [...selectedPaths].map((path) => ({
      historyId: activeHistory ?? 0,
      operation,
      path,
      key: path.split('.').pop() ?? path,
      value: getAtPath(parsedResult, path),
    }));
    const source = parsedResult && typeof parsedResult === 'object' && !Array.isArray(parsedResult)
      ? parsedResult as Record<string, unknown>
      : {};
    const selectedItems = (name: string): Record<string, unknown>[] => {
      const collection = source[name];
      if (!Array.isArray(collection)) return [];
      const indexes = new Set<number>();
      selections.forEach((item) => {
        const parts = item.path.split('.');
        if (parts[0] !== name) return;
        if (/^\d+$/.test(parts[1] ?? '')) indexes.add(Number(parts[1]));
      });
      return [...indexes].map((index) => collection[index]).filter((item): item is Record<string, unknown> => !!item && typeof item === 'object' && !Array.isArray(item));
    };
    let result: unknown;
    if (kind === 'selected') result = buildSelectedSubset(parsedResult, selections);
    else if (kind === 'data') result = { dataCapabilityIds: selectedItems('dataCapabilities').map((item) => item.id).filter(Boolean) };
    else if (kind === 'assets') result = { candidateAssetIds: selectedItems('assetCandidates').map((item) => item.id).filter(Boolean) };
    else if (kind === 'events') result = { candidateEventCandidates: selectedItems('eventCapabilities').map((item) => ({ capabilityId: item.id ?? '', action: item.actionTemplate ?? item.action ?? { call: '', args: {} } })) };
    else result = { candidateDataBindings: selectedItems('dataCapabilities').map((item) => ({
      capabilityId: item.id ?? '',
      arguments: buildDefaultArguments(item.inputSchema as Parameters<typeof buildDefaultArguments>[0], true),
      writeResultTo: item.defaultWriteResultTo ?? '',
      candidateOutputFields: buildOutputFieldPaths(item.outputSchema as Parameters<typeof buildOutputFieldPaths>[0]),
    })) };
    setBuiltJson(jsonText(result));
    setActiveTab('build');
  };

  const handleSubmitShortcut = (event: KeyboardEvent<HTMLElement>) => {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault();
      send();
    }
  };

  return <section className={`interface-debugger ${className}`.trim()} aria-label="接口调试">
    <div className="interface-toolbar"><strong>微服务接口</strong>{status}<span className="interface-toolbar-service">{microserviceStatus}</span></div>
    <div className="operation-tabs" role="tablist">{TOOL_OPERATIONS.map((item) => <button type="button" role="tab" aria-selected={operation === item} className={operation === item ? 'active' : ''} onClick={() => { setOperation(item); setBusinessValues(businessDefaults(item)); setBusinessText(''); setRequestPreview(null); setActiveHistory(null); setFrames([]); setSelectedPaths(new Set()); setBuiltJson(''); }} key={item}>{OPERATION_LABELS[item]}</button>)}</div>
    <div className="interface-grid">
      <div className="interface-panel request-panel" onKeyDown={handleSubmitShortcut}>
        <div className="panel-heading"><h3>请求</h3><button type="button" onClick={() => { setBusinessText(''); setRequestPreview(null); }}>清空业务参数</button></div>
        <p className="shared-config-note">会话、交互 ID 和设备时间会在发送时自动生成。</p>
        {requestPreview && <details className="request-envelope-preview">
          <summary>完整请求包络（只读）</summary>
          <pre>{jsonText(requestPreview)}</pre>
        </details>}
        <div className="business-form"><div className="business-form-heading"><strong>接口参数</strong><button type="button" onClick={() => { setBusinessValues(businessDefaults(operation)); setBusinessText(''); setRequestPreview(null); }}>恢复示例</button></div>{BUSINESS_FIELDS[operation].map((field) => <label className={`business-field${field.type === 'checkbox' ? ' checkbox-field' : ''}`} key={field.id}>{field.label}{field.required && <span className="required-mark">*</span>}{field.type === 'textarea' ? <textarea value={businessValues[field.id] ?? ''} onChange={(event) => setBusinessValues((current) => ({ ...current, [field.id]: event.target.value }))} placeholder={field.placeholder} spellCheck={false} rows={3} /> : field.type === 'select' ? <select value={businessValues[field.id] ?? String(field.default ?? '')} onChange={(event) => setBusinessValues((current) => ({ ...current, [field.id]: event.target.value }))}>{(field.options ?? []).map((option) => <option value={option} key={option}>{option}</option>)}</select> : field.type === 'checkbox' ? <input type="checkbox" checked={businessValues[field.id] === 'true'} onChange={(event) => setBusinessValues((current) => ({ ...current, [field.id]: String(event.target.checked) }))} /> : <input value={businessValues[field.id] ?? ''} onChange={(event) => setBusinessValues((current) => ({ ...current, [field.id]: event.target.value }))} placeholder={field.placeholder} />}</label>)}</div><label className="business-field advanced-field">高级 JSON（可选）<textarea value={businessText} onChange={(event) => setBusinessText(event.target.value)} placeholder="填写后将覆盖上面的接口参数" spellCheck={false} rows={4} /></label>
        <button type="button" className="primary-action" onClick={send}>发送请求 <span>Ctrl + Enter</span></button>
      </div>
      <div className="interface-panel response-panel">
        <div className="panel-heading"><h3>响应</h3><button type="button" onClick={() => setFrames([])}>清空</button></div>
        <div className="response-tabs">{(['parsed', 'raw', 'build'] as const).map((tab) => <button type="button" className={activeTab === tab ? 'active' : ''} onClick={() => setActiveTab(tab)} key={tab}>{tab === 'parsed' ? '最终结果' : tab === 'raw' ? '原始 final' : '构建 JSON'}</button>)}</div>
        {activeTab === 'parsed' && <div className="parsed-panel"><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索字段或值…" />{filteredResult == null ? <div className="empty-response">暂无可解析的 final / final_error 帧。</div> : <Tree value={filteredResult} path="" selected={selectedPaths} onToggle={toggleSelection} arrayLimits={arrayLimits} onArrayLimit={(path, value) => setArrayLimits((current) => ({ ...current, [path]: value }))} />}</div>}
        {activeTab === 'raw' && <div className="frame-list">{frames.length === 0 ? <div className="empty-response">暂无 final / final_error 帧。</div> : frames.map((frame) => <pre className={`frame ${frame.type}`} key={frame.id}>{displayFrame(frame)}</pre>)}</div>}
        {activeTab === 'build' && <div className="build-panel"><p>已选择 {selectedPaths.size} 个字段。</p><div className="quick-build-actions">{(['selected', 'data', 'bindings', 'assets', 'events'] as const).map((kind) => <button type="button" key={kind} disabled={selectedPaths.size === 0} onClick={() => buildQuick(kind)}>{kind === 'selected' ? '选中内容' : kind === 'data' ? 'dataCapabilityIds' : kind === 'bindings' ? 'candidateDataBindings' : kind === 'assets' ? 'candidateAssetIds' : 'candidateEventCandidates'}</button>)}</div><textarea value={builtJson} onChange={(event) => setBuiltJson(event.target.value)} spellCheck={false} placeholder="从解析树选择字段，或手动编辑 JSON。" /><div className="build-actions"><button type="button" onClick={() => navigator.clipboard?.writeText(builtJson)}>复制 JSON</button><button type="button" className="primary-action" onClick={() => { setBusinessText(builtJson); setBusinessValues(businessDefaults(operation)); setActiveTab('parsed'); }}>应用到请求</button></div></div>}
      </div>
    </div>
  </section>;
}

export default InterfaceDebugger;
