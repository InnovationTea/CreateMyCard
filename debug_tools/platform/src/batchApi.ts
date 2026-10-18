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
  sourceType?: string;
  /** 导入批次用途：``expect`` 期望基线（缺省），``actual`` 外部真实输出。批跑运行没有该字段。 */
  purpose?: string;
  name?: string | null;
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
  progress?: PostprocessProgress;
  error?: string;
};

export type PostprocessProgress = {
  phase: 'dependencies' | 'samples' | 'dataset' | 'finalize' | 'done' | string;
  completed: number;
  total: number;
  message: string;
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
  deferred?: boolean;
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
  sourceTotalSamples?: number;
  selection?: { sampleIds: string[]; count?: number };
  samples: PostprocessDashboardSample[];
  progress?: PostprocessProgress;
  error?: string;
};

export type QualityEvaluation = {
  markdown: string;
  policy: Record<string, unknown>;
  policySha256: string;
};

export type QualityIssueDiff = { code: string; left: number; right: number; delta: number };
export type QualityComparisonSide = {
  sampleId?: string;
  imageUrl?: string | null;
  evidenceVersion?: string;
  gaps?: string[];
  score: number | null;
  scoreLow: number | null;
  verdict: string;
  query: string;
  size: string;
  issues: Record<string, number>;
};
export type QualityComparisonSummary = {
  runId: string;
  executionId: string;
  total: number;
  scored: number;
  passCount: number;
  passRate: number | null;
  meanScore: number | null;
};
export type QualityComparison = {
  left: QualityComparisonSummary;
  right: QualityComparisonSummary;
  comparable: boolean;
  warnings: string[];
  passRateDelta: number | null;
  rows: Array<{
    sampleId: string;
    alignment: string;
    left: QualityComparisonSide | null;
    right: QualityComparisonSide | null;
    scoreDelta: number | null;
    scoreLowDelta?: number | null;
    issueDiff: QualityIssueDiff[];
  }>;
  issueDistribution: QualityIssueDiff[];
  confirmedIssueDistribution?: QualityIssueDiff[];
  pendingIssueDistribution?: QualityIssueDiff[];
  passDefinition: string;
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

export type ValidationFailureItem = {
  id: string;
  title: string;
  query: string;
  size: string;
  sequence: number;
  finalStatus: string;
  interfaceRetryCount: number;
  validationFailureCount: number;
  repairAttemptCount: number;
  validations: Array<{
    captureId: string;
    executionAttempt: number;
    interfaceAttempt: number;
    validationAttempt: number;
    status: string;
    errorTypes: string[];
    dsl: string;
    appVersion?: string | null;
  }>;
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

export function getQualityEvaluation(): Promise<QualityEvaluation> {
  return requestJson('/debug/batch/quality/evaluation');
}

export function getQualityComparison(options: {
  leftRunId: string;
  rightRunId: string;
  leftExecutionId?: string;
  rightExecutionId?: string;
  leftSampleId?: string;
  rightSampleId?: string;
}): Promise<QualityComparison> {
  const params = new URLSearchParams();
  Object.entries(options).forEach(([key, value]) => { if (value) params.set(key, value); });
  return requestJson(`/debug/batch/quality/compare?${params}`);
}

/** 导入用途：期望基线（对比左侧）或外部真实输出（对比右侧）。 */
export type ExpectPurpose = 'expect' | 'actual';

export type ExpectImportSample = {
  id: string;
  /** 可以不填：留空时期望对比只按样本 ID 配对。 */
  query?: string;
  size?: string;
  dsl: string;
  /** 参考截图，可留空；不参与指纹与筛选。 */
  imageBase64?: string;
  cardSpec?: Record<string, unknown>; expectedIntents?: string[];
  expectedData?: string[]; expectedActions?: string[]; expectedIcons?: string[];
  category?: string;
  sourceSha256?: string; imageSha256?: string;
};

/** 导入页可选 token：中文标签与匹配时比较的原始值一起给出。 */
export type ExpectOption = { value: string; label: string };
export type ExpectOptions = {
  data: ExpectOption[]; actions: ExpectOption[]; icons: ExpectOption[];
};

export function getExpectOptions(): Promise<ExpectOptions> {
  return requestJson('/debug/expect/options');
}

/** 该侧已有样本 ID 的轻量索引（不带 DSL／截图）：导入页据此在提交前提示 ID 冲突。 */
export type ExpectSampleId = { id: string; runId: string; runName: string };

export function getExpectSampleIds(purpose: ExpectPurpose)
  : Promise<{ items: ExpectSampleId[] }> {
  return requestJson(`/debug/expect/sample-ids?purpose=${encodeURIComponent(purpose)}`);
}

/** 导入批次；``purpose`` 决定它进期望池还是当实际来源，产出的批次同时供质量评分使用。 */
export function importExpectBatch(input: {
  name: string; imageSource: string; category?: string; samples: ExpectImportSample[];
  purpose?: ExpectPurpose;
}): Promise<BatchRun> {
  return requestJson('/debug/expect/import', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input),
  });
}

export function getBatchSample(runId: string, sampleId: string): Promise<BatchSampleDetail> {
  return requestJson(
    `/debug/batch/runs/${encodeURIComponent(runId)}/samples/${encodeURIComponent(sampleId)}`,
  );
}

export type ExpectFingerprint = {
  data: string[]; actions: string[]; icons?: string[];
};

/** ``/debug/expect/detect`` 的返回：内容格式、自动提取的指纹与判定尺寸。 */
export type ExpectDetection = {
  kind: 'cardspec' | 'dsl' | 'empty' | 'unknown' | string;
  fingerprint: ExpectFingerprint;
  size?: string;
  note?: string;
};

/** 只用于展示的中文标签：键是原始 token，值是中文名。 */
export type ExpectLabels = {
  data?: Record<string, string>;
  actions?: Record<string, string>;
  icons?: Record<string, string>;
};

export type ExpectSampleSide = {
  sampleId: string; title: string; query: string; size: string;
  attempt: string; genui: string; fingerprint: ExpectFingerprint;
  status?: string;
  sizeSource?: string; sizeDerived?: string;
  explicit?: { data: string[]; actions: string[]; icons?: string[] };
  labels?: ExpectLabels;
  category?: string;
  imageUrl?: string | null;
};

export type ExpectMatch = {
  tier: string;
  missingData: string[]; missingActions: string[]; missingIcons?: string[];
};

export type ExpectDiff = {
  data: { missing: string[]; extra: string[] };
  actions: { missing: string[]; extra: string[] };
  icons?: { missing: string[]; extra: string[] };
};

export type ExpectPair = {
  expected: ExpectSampleSide;
  actual: ExpectSampleSide | null;
  match: ExpectMatch | null;
  diff: ExpectDiff | null;
  tier: string;
};

export type ExpectComparison = {
  importRunId: string; importName: string; runId: string; runName: string;
  /** 实际侧来源：``session`` 为本次会话的调试记录，``batch`` 为已落盘的批跑运行。 */
  actualSource?: string;
  summary: {
    expected: number; actual: number; matched: number; none: number;
  };
  options?: { dimensions: string[] };
  categories?: string[];
  pairs: ExpectPair[];
  unmatchedActual: ExpectSampleSide[];
  warnings: string[];
};

/** 实际侧不跑批时提交的一条真实输出：端到端／接口调试拿到的 query 与 genui DSL。 */
export type ExpectLiveActual = {
  id: string; query: string; genui: string; title?: string; size?: string;
};

export type ExpectMatchOptions = {
  dimensions?: string[];
  actualName?: string;
};

export function compareExpectLive(
  importRunId: string | null, actuals: ExpectLiveActual[], options: ExpectMatchOptions = {},
): Promise<ExpectComparison> {
  return requestJson('/debug/expect/compare-live', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    // 期望侧不再挑批次：不传 importRunId 表示用全部已导入的期望输出。
    body: JSON.stringify({ actuals, ...options, ...(importRunId ? { importRunId } : {}) }),
  });
}

/** 实际侧改用已落盘的批跑运行：直接读该批跑每个样本的最终 GenUI 参与配对。 */
export function compareExpectRun(
  runId: string, options: ExpectMatchOptions = {}, importRunId?: string | null,
): Promise<ExpectComparison> {
  const params = new URLSearchParams({ runId });
  if (importRunId) params.set('importRunId', importRunId);
  if (options.dimensions?.length) params.set('dimensions', options.dimensions.join(','));
  return requestJson(`/debug/expect/compare?${params.toString()}`);
}

/** 期望数据画廊里的一条样本；genui 用于展开查看原始 DSL。 */
export type ExpectGalleryItem = {
  runId: string; runName: string; sampleId: string; title: string;
  query: string; size: string; sizeSource?: string; category: string;
  attempt?: string; genui: string; imageUrl?: string | null;
  /** 导入时显式填写的期望项；编辑回填时用它，而不是自动指纹。 */
  explicit?: { data?: string[]; actions?: string[]; icons?: string[] };
  fingerprint: ExpectFingerprint;
  labels?: ExpectLabels;
};

/**
 * 编辑保存用的载荷：不带 id（身份由路径决定），不带 imageBase64 表示保留原截图。
 * 只改传了的字段（后端局部更新），因此画廊里只改分类不会动 Query／DSL／期望项；
 * category 传 null 表示清回「未分类」。
 */
export type ExpectSampleUpdate = {
  query?: string; size?: string; dsl?: string; imageBase64?: string;
  cardSpec?: Record<string, unknown>;
  expectedIntents?: string[]; expectedData?: string[];
  expectedActions?: string[]; expectedIcons?: string[];
  category?: string | null;
};

export function getExpectSample(
  runId: string, sampleId: string,
): Promise<ExpectGalleryItem> {
  return requestJson(
    `/debug/expect/runs/${encodeURIComponent(runId)}/samples/${encodeURIComponent(sampleId)}`,
  );
}

/** 整批改数据分类：一次改掉这批所有图片的分类，不动 DSL、截图与期望项。 */
export function updateExpectRunCategory(
  runId: string, category: string | null,
): Promise<{ runId: string; category: string; sampleCount: number }> {
  return requestJson(
    `/debug/expect/runs/${encodeURIComponent(runId)}/category`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category }),
    },
  );
}

/** 就地更新一条导入样本：批次与同批其它样本都不动，因此不会出现同 ID 两条。 */
export function updateExpectSample(
  runId: string, sampleId: string, sample: ExpectSampleUpdate,
): Promise<ExpectGalleryItem> {
  return requestJson(
    `/debug/expect/runs/${encodeURIComponent(runId)}/samples/${encodeURIComponent(sampleId)}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(sample),
    },
  );
}

export type ExpectGalleryBatch = {
  runId: string; name: string; category: string;
  sampleCount: number; startedAt: string;
};

export type ExpectGallery = {
  items: ExpectGalleryItem[];
  categories: string[];
  batches: ExpectGalleryBatch[];
  total: number;
  warnings: string[];
};

export function getExpectGallery(filters: { category?: string; q?: string } = {}) {
  const params = new URLSearchParams();
  if (filters.category) params.set('category', filters.category);
  if (filters.q) params.set('q', filters.q);
  const suffix = params.toString();
  return requestJson<ExpectGallery>(`/debug/expect/samples${suffix ? `?${suffix}` : ''}`);
}

export function deleteExpectSample(runId: string, sampleId: string) {
  return requestJson<{ deleted: string; runId: string; sampleId: string }>(
    `/debug/expect/runs/${encodeURIComponent(runId)}/samples/${encodeURIComponent(sampleId)}`,
    { method: 'DELETE' },
  );
}

export function deleteExpectRun(runId: string) {
  return requestJson<{ deleted: string; runId: string }>(
    `/debug/expect/runs/${encodeURIComponent(runId)}`,
    { method: 'DELETE' },
  );
}

/**
 * 导入页识别一份内容文件是 CardSpec 还是 genui DSL，并取回自动提取的数据／动作／图标。
 * 判定与提取都用后端比对时的同一套口径，页面不需要再维护第二套规则。
 */
export function detectExpectPayload(text: string): Promise<ExpectDetection> {
  return requestJson('/debug/expect/detect', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
}

export async function getValidationFailures(runId: string): Promise<ValidationFailureItem[]> {
  const body = await requestJson<{ items: ValidationFailureItem[] }>(
    `/debug/batch/runs/${encodeURIComponent(runId)}/validation-failures`,
  );
  return body.items;
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

export function getPostprocessExecution(
  runId: string, executionId: string, signal?: AbortSignal,
): Promise<PostprocessExecution> {
  return requestJson(
    `/debug/batch/runs/${encodeURIComponent(runId)}/postprocess/${encodeURIComponent(executionId)}`,
    { signal },
  );
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
