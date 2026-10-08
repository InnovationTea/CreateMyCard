export type BatchDataset = {
  id: string;
  name: string;
  sampleCount: number;
  validSampleCount: number;
  invalidSampleCount: number;
};

export type BatchDatasetItem = {
  id: string;
  fileName: string;
  title: string;
  query: string;
  size: string;
  valid: boolean;
  error: string;
};

export type BatchSampleSummary = {
  id: string;
  fileName: string;
  title: string;
  query: string;
  size: string;
  sequence: number;
  uid?: string;
  status: string;
  attemptCount: number;
  elapsedMs: number;
  errorCode: string;
  error: string;
  artifactAvailable: boolean;
  dslAvailable: boolean;
  traceStatus: string;
  traceRecordCount: number;
  traceSchemaVersion?: string;
  traceDurationMs?: number;
};

export type DeviceCaptureItem = {
  id: string;
  status: 'success' | 'failed' | 'skipped' | 'not_requested' | string;
  size?: string;
  error?: string;
  cardUrl?: string;
  fullUrl?: string;
};

export type DeviceCapture = {
  status: 'not_requested' | 'queued' | 'running' | 'ready' | 'partial' | 'failed' | 'interrupted';
  total?: number;
  completed?: number;
  succeeded?: number;
  failed?: number;
  skipped?: number;
  error?: string;
  items?: DeviceCaptureItem[];
};

export type DeviceCaptureConfig = {
  configured: boolean;
  available: boolean;
  reason: string;
  device?: string;
};

export type BatchRun = {
  runId: string;
  status: string;
  startedAt: string;
  finishedAt?: string;
  endpoint: string;
  concurrency: number;
  maxRetries: number;
  total: number;
  completed: number;
  success: number;
  degraded: number;
  failed: number;
  cancelled: number;
  averageElapsedMs: number;
  traceWarnings: number;
  samples: BatchSampleSummary[];
  taskId?: string;
  datasetId?: string;
  backendMode?: 'deployed' | 'managed';
  serviceStatus?: string;
  serviceLogPath?: string;
  error?: string;
  queuePosition?: number | null;
  interrupted?: boolean;
  gallery?: BatchGallery;
  deviceCapture?: DeviceCapture;
  postprocessExecutions?: PostprocessExecution[];
};

export type PostprocessArtifact = {
  key: string;
  title?: string;
  dataType: 'metrics' | 'records' | 'matrix' | 'image' | 'json' | 'text' | 'code'
    | 'diff' | 'issues' | 'file' | 'link' | string;
  renderer?: 'kpi' | 'table' | 'bar' | 'line' | 'pie' | 'heatmap' | 'gallery'
    | 'tree' | 'code' | 'diff' | 'issues' | 'download' | 'link' | string;
  data?: unknown;
  url?: string;
  path?: string;
  label?: string;
  language?: string;
  alt?: string;
  [key: string]: unknown;
};

export type PostprocessBlock = {
  type: string;
  title?: string;
  [key: string]: unknown;
};

export type PostprocessResult = {
  status: 'success' | 'partial' | 'failed' | 'skipped' | string;
  summary: string;
  facts?: Record<string, string | number | boolean | string[] | null>;
  artifacts?: PostprocessArtifact[];
  blocks?: PostprocessBlock[];
};

export type PostprocessSampleResult = PostprocessResult & { sampleId: string };

export type PostprocessPluginResult = {
  id: string;
  name?: string;
  apiVersion?: string;
  version?: string;
  config?: Record<string, unknown>;
  dependence?: string[];
  status?: string;
  sampleResults?: PostprocessSampleResult[];
  sampleCount?: number;
  counts?: Record<string, number>;
  datasetResult?: PostprocessResult;
};

export type PostprocessExecution = {
  schemaVersion: 'batch-postprocess-execution-v1' | 'batch-postprocess-execution-v2';
  executionId: string;
  runId: string;
  status: string;
  createdAt: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  plugins: PostprocessPluginResult[];
  error?: string;
};

export type PostprocessPlugin = {
  apiVersion: 'batch-postprocess-v1' | 'batch-postprocess-v2';
  id: string;
  name: string;
  version: string;
  description?: string;
  dependence?: string[];
  configSchema: Record<string, unknown>;
  outputs?: PostprocessOutputDefinition[];
  presentation?: PostprocessPresentation;
};

export type PostprocessOutputDefinition = {
  key: string;
  scope: 'sample' | 'dataset';
  title: string;
  dataType: string;
  renderer?: string;
  required?: boolean;
};

export type PostprocessSampleField = {
  key: string;
  label: string;
  type: 'string' | 'number' | 'boolean' | 'string-list';
  format?: string;
  filterable?: boolean;
  sortable?: boolean;
};

export type PostprocessPresentation = {
  defaultView: 'table' | 'gallery';
  sampleFields?: PostprocessSampleField[];
};

export type PostprocessDashboardSample = {
  sampleId: string;
  title: string;
  sequence: number;
  status: string;
  summary: string;
  facts: Record<string, string | number | boolean | string[] | null>;
  artifacts: PostprocessArtifact[];
};

export type PostprocessDashboard = {
  schemaVersion: 'batch-postprocess-dashboard-v2';
  legacy?: boolean;
  runId: string;
  executionId: string;
  plugin: { id: string; name: string; version: string; apiVersion: string };
  status: string;
  presentation: PostprocessPresentation;
  outputs: PostprocessOutputDefinition[];
  datasetResult: PostprocessResult;
  counts: Record<string, number>;
  totalSamples: number;
  samples: PostprocessDashboardSample[];
};

export type PostprocessSamplePage = {
  items: PostprocessDashboardSample[];
  total: number;
  offset: number;
  limit: number;
};

export type BatchGallery = {
  status: 'not_started' | 'generating' | 'ready' | 'failed';
  startedAt?: string | null;
  generatedAt?: string | null;
  url?: string;
  error?: string;
};

export type BatchExecution = Partial<BatchRun> & {
  runId: string;
  taskId: string;
  status: string;
  createdAt: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  queuePosition?: number | null;
  backendMode: 'deployed' | 'managed';
  serviceStatus: string;
  serviceLogPath?: string;
  error?: string;
};

export type BatchTask = {
  taskId: string;
  name: string;
  datasetId: string;
  sampleIds: string[];
  sampleCount: number;
  requestOverrides: Record<string, unknown>;
  concurrency: number;
  maxRetries: number;
  timeoutSeconds: number;
  backendMode: 'deployed' | 'managed';
  toolWsBaseUrl: string;
  serviceConfig: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
  runCount: number;
  latestRun?: BatchExecution | null;
  runs?: BatchExecution[];
};

export type BatchScheduler = {
  paused: boolean;
  activeRunId?: string | null;
  active?: BatchExecution | null;
  queue: BatchExecution[];
};

export type ServiceConfigDefaults = {
  values: Record<string, string | number | boolean>;
  sources: Record<string, string>;
};

export type ConnectionAvailability = {
  mainAgent: { available: boolean; detail: string };
  deployedService: { available: boolean; detail: string };
  managedService: { available: boolean; detail: string; endpoint?: string; logPath?: string };
};

export type CreateBatchTaskInput = {
  name: string;
  datasetId: string;
  sampleIds: string[];
  requestOverrides: Record<string, unknown>;
  backendMode: 'deployed' | 'managed';
  toolWsBaseUrl: string;
  serviceConfig: Record<string, unknown>;
};

export type BatchAttempt = {
  name: string;
  request?: Record<string, unknown>;
  response?: Record<string, unknown>;
  result?: Record<string, unknown>;
  blocks?: Record<string, unknown>;
  trace?: TraceView;
  genui?: string;
};

export type TraceArtifact = {
  id: string;
  name: string;
  role: 'input' | 'output' | 'diagnostic' | 'snapshot';
  mediaType: string;
  bytes: number;
  sha256: string;
  available: boolean;
  error?: string;
  label?: string;
  ownerNodeId?: string;
};

export type TraceNode = {
  id: string;
  parentId?: string | null;
  category: string;
  name: string;
  stage: string;
  status: string;
  recordType?: string;
  startOffsetMs: number;
  durationMs?: number | null;
  attempts: Record<string, number>;
  attributes: Record<string, unknown>;
  metrics: Record<string, unknown>;
  artifacts: TraceArtifact[];
  raw: Record<string, unknown>;
  operation?: string;
  kind?: 'group' | 'step' | 'model';
  title?: string;
  description?: string;
  events?: Array<Record<string, unknown>>;
  contentIndex?: TraceArtifact[];
};

export type TraceView = {
  viewVersion: string;
  uid: string;
  traceId: string;
  sourceSchemaVersion: string;
  status: 'complete' | 'partial' | 'missing' | 'invalid' | string;
  timingMode: 'exact';
  recordCount: number;
  summary: Record<string, unknown>;
  nodes: TraceNode[];
  warnings: string[];
  instrumentationVersion?: number;
  rawOnly?: boolean;
  rawRecords?: Array<Record<string, unknown>>;
};

export type BatchSampleDetail = {
  summary: BatchSampleSummary & { finalAttempt?: number };
  attempts: BatchAttempt[];
  deviceCapture?: DeviceCaptureItem;
};

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body && typeof body.detail === 'string' ? body.detail : `请求失败（${response.status}）`;
    throw new Error(detail);
  }
  return body as T;
}

export async function listBatchDatasets(): Promise<BatchDataset[]> {
  const body = await requestJson<{ items: BatchDataset[] }>('/debug/batch/datasets');
  return body.items;
}

export async function listBatchDatasetSamples(datasetId: string): Promise<BatchDatasetItem[]> {
  const body = await requestJson<{ items: BatchDatasetItem[] }>(
    `/debug/batch/datasets/${encodeURIComponent(datasetId)}/samples`,
  );
  return body.items;
}

export function getServiceConfigDefaults(): Promise<ServiceConfigDefaults> {
  return requestJson('/debug/batch/service-config/defaults');
}

export function getConnectionAvailability(toolWsBaseUrl: string): Promise<ConnectionAvailability> {
  return requestJson('/debug/batch/connections/status', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ toolWsBaseUrl }),
  });
}

export function startManagedService(
  serviceConfig: Record<string, string | number | boolean>,
): Promise<ConnectionAvailability> {
  return requestJson('/debug/batch/connections/managed/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ serviceConfig }),
  });
}

export function getDeviceCaptureConfig(): Promise<DeviceCaptureConfig> {
  return requestJson('/debug/batch/device-capture/config');
}

export async function listBatchTasks(): Promise<BatchTask[]> {
  const body = await requestJson<{ items: BatchTask[] }>('/debug/batch/tasks');
  return body.items;
}

export function getBatchTask(taskId: string): Promise<BatchTask> {
  return requestJson(`/debug/batch/tasks/${encodeURIComponent(taskId)}`);
}

export function createBatchTask(input: CreateBatchTaskInput): Promise<BatchTask> {
  return requestJson('/debug/batch/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
}

export function copyBatchTask(taskId: string): Promise<BatchTask> {
  return requestJson(`/debug/batch/tasks/${encodeURIComponent(taskId)}/copy`, { method: 'POST' });
}

export function deleteBatchTask(taskId: string): Promise<void> {
  return requestJson(`/debug/batch/tasks/${encodeURIComponent(taskId)}`, { method: 'DELETE' });
}

export function enqueueBatchTask(taskId: string): Promise<BatchExecution> {
  return requestJson(`/debug/batch/tasks/${encodeURIComponent(taskId)}/runs`, { method: 'POST' });
}

export function continueBatchRun(runId: string): Promise<BatchExecution> {
  return requestJson(`/debug/batch/runs/${encodeURIComponent(runId)}/continue`, { method: 'POST' });
}

export function getBatchScheduler(): Promise<BatchScheduler> {
  return requestJson('/debug/batch/scheduler');
}

export function resumeBatchScheduler(): Promise<BatchScheduler> {
  return requestJson('/debug/batch/scheduler/resume', { method: 'POST' });
}

export async function listBatchRuns(): Promise<BatchRun[]> {
  const body = await requestJson<{ items: BatchRun[] }>('/debug/batch/runs');
  return body.items;
}

export function getBatchRun(runId: string): Promise<BatchRun> {
  return requestJson(`/debug/batch/runs/${encodeURIComponent(runId)}`);
}

export function getBatchSample(runId: string, sampleId: string): Promise<BatchSampleDetail> {
  return requestJson(
    `/debug/batch/runs/${encodeURIComponent(runId)}/samples/${encodeURIComponent(sampleId)}`,
  );
}

export function cancelBatchRun(runId: string): Promise<BatchRun> {
  return requestJson(`/debug/batch/runs/${encodeURIComponent(runId)}/stop`, { method: 'POST' });
}

export async function listPostprocessPlugins(): Promise<PostprocessPlugin[]> {
  const body = await requestJson<{ items: PostprocessPlugin[] }>('/debug/batch/postprocess/plugins');
  return body.items;
}

export function startPostprocess(
  runId: string,
  pluginIds: string[],
  configs: Record<string, Record<string, unknown>> = {},
  rerun = false,
): Promise<PostprocessExecution> {
  return requestJson(`/debug/batch/runs/${encodeURIComponent(runId)}/postprocess`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pluginIds, configs, rerun }),
  });
}

export function getPostprocessDashboard(
  runId: string,
  executionId: string,
  pluginId: string,
): Promise<PostprocessDashboard> {
  return requestJson(
    `/debug/batch/runs/${encodeURIComponent(runId)}/postprocess/`
      + `${encodeURIComponent(executionId)}/plugins/${encodeURIComponent(pluginId)}/dashboard`,
  );
}

export function getPostprocessSamples(
  runId: string,
  executionId: string,
  pluginId: string,
  options: {
    offset?: number;
    limit?: number;
    q?: string;
    status?: string;
    sort?: string;
    order?: 'asc' | 'desc';
    factKey?: string;
    factValue?: string;
  } = {},
): Promise<PostprocessSamplePage> {
  const params = new URLSearchParams();
  Object.entries(options).forEach(([key, value]) => {
    if (value !== undefined && value !== '') params.set(key, String(value));
  });
  const suffix = params.size ? `?${params.toString()}` : '';
  return requestJson(
    `/debug/batch/runs/${encodeURIComponent(runId)}/postprocess/`
      + `${encodeURIComponent(executionId)}/plugins/${encodeURIComponent(pluginId)}/samples${suffix}`,
  );
}

export function getPostprocessSample(
  runId: string,
  executionId: string,
  pluginId: string,
  sampleId: string,
): Promise<PostprocessSampleResult> {
  return requestJson(
    `/debug/batch/runs/${encodeURIComponent(runId)}/postprocess/`
      + `${encodeURIComponent(executionId)}/plugins/${encodeURIComponent(pluginId)}/samples/`
      + encodeURIComponent(sampleId),
  );
}

export async function getBatchTraceArtifact(
  runId: string,
  sha256: string,
  expectedBytes: number,
  signal?: AbortSignal,
): Promise<{ content: string; mediaType: string }> {
  const response = await fetch(
    `/debug/batch/runs/${encodeURIComponent(runId)}/trace-artifacts/${encodeURIComponent(sha256)}`,
    { signal },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body && typeof body.detail === 'string'
      ? body.detail
      : `Trace 附件读取失败（${response.status}）`;
    throw new Error(detail);
  }
  const buffer = await response.arrayBuffer();
  if (buffer.byteLength !== expectedBytes) throw new Error('Trace 附件字节数不匹配');
  const digest = await crypto.subtle.digest('SHA-256', buffer);
  const actualDigest = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
  if (actualDigest !== sha256) throw new Error('Trace 附件 SHA-256 不匹配');
  return {
    content: new TextDecoder().decode(buffer),
    mediaType: response.headers.get('content-type') ?? 'text/plain',
  };
}

export function batchTraceArtifactUrl(runId: string, sha256: string): string {
  return `/debug/batch/runs/${encodeURIComponent(runId)}/trace-artifacts/${encodeURIComponent(sha256)}`;
}
