import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { CardRenderer, resolveCardSize } from '@widget-debug/card-renderer';
import {
  cancelBatchRun,
  continueBatchRun,
  enqueueBatchTask,
  getBatchRun,
  getBatchSample,
  getBatchTask,
  type BatchAttempt,
  type BatchRun,
  type BatchSampleDetail,
  type BatchTask,
} from '../batchApi';
import { DEFAULT_ASSET_BASE_URL } from '../config';
import { PostprocessPanel } from '../components/PostprocessPanel';
import { serviceConfigLabel } from '../serviceConfig';

const ACTIVE_STATUSES = new Set(['queued', 'preparing', 'running', 'stopping']);
const ACTIVE_CAPTURE_STATUSES = new Set(['queued', 'running']);
const STOPPED_STATUSES = new Set(['cancelled', 'interrupted']);

function jsonText(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}

function statusLabel(status: string): string {
  return ({
    idle: '未运行', queued: '排队中', preparing: '准备后端', running: '运行中',
    stopping: '停止中', completed: '已完成', success: '成功', degraded: '降级',
    failed: '失败', unsupported: '不支持', cancelled: '已停止', interrupted: '已中断',
  } as Record<string, string>)[status] ?? status;
}

function serviceStatusLabel(status?: string): string {
  if (!status) return '未连接';
  return ({
    pending: '等待启动', starting: '正在启动受管后端', managed_running: '受管后端已就绪',
    external: '使用已部署后端', failed: '后端启动失败',
  } as Record<string, string>)[status] ?? status;
}

function deviceCaptureStatusLabel(status?: string): string {
  return ({
    not_requested: '未生成', queued: '等待截图', running: '正在截图', ready: '已完成',
    partial: '部分完成', failed: '截图失败', interrupted: '已中断',
  } as Record<string, string>)[status ?? 'not_requested'] ?? String(status);
}

function finalAttempt(detail: BatchSampleDetail | null): BatchAttempt | null {
  if (!detail?.attempts.length) return null;
  const index = detail.summary.finalAttempt;
  if (typeof index === 'number') {
    return detail.attempts.find((item) => item.name === `attempt_${String(index).padStart(3, '0')}`)
      ?? detail.attempts.at(-1) ?? null;
  }
  return detail.attempts.at(-1) ?? null;
}

export function BatchRoute() {
  const { taskId, runId: legacyRunId } = useParams();
  const navigate = useNavigate();
  const [task, setTask] = useState<BatchTask | null>(null);
  const [run, setRun] = useState<BatchRun | null>(null);
  const [selectedSampleId, setSelectedSampleId] = useState('');
  const [detail, setDetail] = useState<BatchSampleDetail | null>(null);
  const [detailTab, setDetailTab] = useState('preview');
  const [statusFilter, setStatusFilter] = useState('all');
  const [traceFilter, setTraceFilter] = useState('all');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [showCustomParams, setShowCustomParams] = useState(false);
  const [previewZoom, setPreviewZoom] = useState(220);

  const refresh = useCallback(async () => {
    if (taskId) {
      const nextTask = await getBatchTask(taskId);
      setTask(nextTask);
      const latestRun = nextTask.runs?.[0];
      const preferredRunId = latestRun && ACTIVE_STATUSES.has(latestRun.status)
        ? latestRun.runId
        : run?.runId && nextTask.runs?.some((item) => item.runId === run.runId)
          ? run.runId
          : latestRun?.runId;
      if (preferredRunId) setRun(await getBatchRun(preferredRunId)); else setRun(null);
    } else if (legacyRunId) {
      setRun(await getBatchRun(legacyRunId));
    }
  }, [legacyRunId, run?.runId, taskId]);

  useEffect(() => {
    refresh().catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
  }, [taskId, legacyRunId]);

  useEffect(() => {
    if (!run || (!ACTIVE_STATUSES.has(run.status)
      && run.gallery?.status !== 'generating'
      && !ACTIVE_CAPTURE_STATUSES.has(run.deviceCapture?.status ?? '')
      && !run.postprocessExecutions?.some((item) => ['queued', 'running'].includes(item.status)))) return;
    const timer = window.setInterval(() => {
      Promise.all([getBatchRun(run.runId), taskId ? getBatchTask(taskId) : Promise.resolve(null)])
        .then(([nextRun, nextTask]) => { setRun(nextRun); if (nextTask) setTask(nextTask); })
        .catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
    }, 750);
    return () => window.clearInterval(timer);
  }, [run?.deviceCapture?.status, run?.gallery?.status, run?.postprocessExecutions, run?.runId, run?.status, taskId]);

  useEffect(() => {
    if (!run || !selectedSampleId) { setDetail(null); return; }
    const sample = run.samples?.find((item) => item.id === selectedSampleId);
    if (!sample || ACTIVE_STATUSES.has(sample.status) || sample.status === 'queued') return;
    getBatchSample(run.runId, selectedSampleId)
      .then(setDetail)
      .catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
  }, [run, selectedSampleId]);

  const visibleSamples = useMemo(() => (run?.samples ?? []).filter((sample) => {
    if (statusFilter !== 'all' && sample.status !== statusFilter) return false;
    if (traceFilter === 'warning' && !['missing', 'partial', 'invalid'].includes(sample.traceStatus)) return false;
    if (traceFilter === 'available' && sample.traceStatus !== 'complete') return false;
    return true;
  }), [run, statusFilter, traceFilter]);

  const activeAttempt = finalAttempt(detail);
  const activeCardSize = resolveCardSize(
    activeAttempt?.blocks,
    detail?.summary.query,
    detail?.summary.size,
  );
  const total = run?.total ?? task?.sampleCount ?? 0;
  const completed = run?.completed ?? 0;
  const progress = total ? Math.round((completed / total) * 100) : 0;
  const currentStatus = run?.status ?? 'idle';
  const gallery = run?.gallery ?? { status: 'not_started' as const };
  const deviceCapture = run?.deviceCapture ?? { status: 'not_requested' as const };
  const perform = async (action: () => Promise<unknown>) => {
    setBusy(true); setError('');
    try { await action(); await refresh(); } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  };

  return (
    <div className="batch-page batch-detail-page">
      <header className="batch-heading">
        <div>
          <button type="button" className="batch-back" onClick={() => navigate('/batch')}>← 返回任务中心</button>
          <h1>{task?.name ?? '历史批量测试'}</h1>
          <p>{task ? `${task.datasetId} · ${task.sampleCount} 个样本 · ${task.backendMode === 'managed' ? '本地受管后端' : '已部署后端'}` : run?.runId}</p>
        </div>
        <div className="batch-heading-side">
          <div className="batch-heading-actions">
            {task && <button type="button" className="batch-start" disabled={busy || Boolean(run && ACTIVE_STATUSES.has(run.status))} onClick={() => perform(() => enqueueBatchTask(task.taskId))}>重新执行</button>}
            {run && STOPPED_STATUSES.has(run.status) && <button type="button" className="batch-start" disabled={busy} onClick={() => perform(() => continueBatchRun(run.runId))}>继续执行</button>}
            {run && ACTIVE_STATUSES.has(run.status) && <button type="button" className="batch-cancel" disabled={busy} onClick={() => perform(() => cancelBatchRun(run.runId))}>停止</button>}
            {run && <PostprocessPanel runId={run.runId} runStatus={run.status} selectedSampleId={selectedSampleId} executions={run.postprocessExecutions ?? []} onStarted={refresh} />}
            {task && <button type="button" onClick={() => setShowCustomParams((visible) => !visible)}>
              {showCustomParams ? '收起自定义参数' : '查看自定义参数'}
            </button>}
          </div>
          {task && <div className="batch-run-switcher"><label>执行记录<select value={run?.runId ?? ''} onChange={(event) => { const nextId = event.target.value; if (!nextId) { setRun(null); return; } getBatchRun(nextId).then(setRun).catch((reason) => setError(String(reason))); setSelectedSampleId(''); }}><option value="">尚无执行</option>{task.runs?.map((item) => <option key={item.runId} value={item.runId}>{item.runId} · {statusLabel(item.status)}</option>)}</select></label><span>并发 {task.concurrency} · 重试 {task.maxRetries} · 超时 {task.timeoutSeconds}s</span></div>}
        </div>
      </header>
      {error && <div className="batch-error" role="alert">{error}</div>}
      {task && showCustomParams && <section className="batch-custom-params" aria-label="任务自定义参数">
        <strong>自定义参数</strong>
        <div className="batch-custom-param-groups">
          <section>
            <h2>测试后端</h2>
            <dl>
              <div><dt>微服务来源</dt><dd>{task.backendMode === 'managed' ? '本地受管微服务' : '已部署微服务'}</dd></div>
              {task.backendMode === 'deployed'
                ? <div><dt>微服务 URL</dt><dd>{task.toolWsBaseUrl}</dd></div>
                : null}
            </dl>
            {task.backendMode === 'managed' && <dl>{Object.entries(task.serviceConfig).map(([key, value]) => (
              <div key={key}><dt>{serviceConfigLabel(key)}</dt><dd>{String(value)}</dd></div>
            ))}</dl>}
          </section>
          <section>
            <h2>公共请求字段覆盖</h2>
            {Object.keys(task.requestOverrides).length
              ? <pre>{jsonText(task.requestOverrides)}</pre>
              : <p>未覆盖公共请求字段。</p>}
          </section>
        </div>
      </section>}
      {gallery.status === 'failed' && gallery.error && (
        <div className="batch-gallery-error" role="alert">画廊生成失败：{gallery.error}</div>
      )}
      {deviceCapture.status !== 'not_requested' && (
        <section className={`device-capture-state ${deviceCapture.status}`} aria-live="polite">
          <div><small>真机截图</small><strong>{deviceCaptureStatusLabel(deviceCapture.status)}</strong></div>
          <div><small>处理进度</small><strong>{deviceCapture.completed ?? 0}/{deviceCapture.total ?? 0}</strong></div>
          <div><small>成功 / 失败 / 跳过</small><strong>{deviceCapture.succeeded ?? 0} / {deviceCapture.failed ?? 0} / {deviceCapture.skipped ?? 0}</strong></div>
          {deviceCapture.error && <p>{deviceCapture.error}</p>}
        </section>
      )}
      {task && currentStatus !== 'completed' && (
        <section className={`batch-current-state ${currentStatus}`} aria-live="polite">
          <div>
            <small>当前任务状态</small>
            <strong>{statusLabel(currentStatus)}</strong>
          </div>
          <div>
            <small>后端状态</small>
            <strong>{serviceStatusLabel(run?.serviceStatus)}</strong>
          </div>
          <div>
            <small>任务进度</small>
            <strong>{completed}/{total}（{progress}%）</strong>
          </div>
          {run?.queuePosition ? <div><small>队列位置</small><strong>第 {run.queuePosition} 位</strong></div> : null}
        </section>
      )}
      {run?.error && (
        <section className="batch-run-error" role="alert">
          <strong>{run.serviceStatus === 'failed' ? '受管后端启动失败' : '任务执行失败'}</strong>
          <p>{run.error}</p>
          {run.serviceLogPath && <p className="batch-log-path">服务日志：{run.serviceLogPath}</p>}
        </section>
      )}
      <main className="batch-results">
        <section className="batch-summary">
          <div className="batch-progress"><span style={{ width: `${progress}%` }} /></div>
          <div className="batch-metrics"><span><b>{completed}/{total}</b>已完成 / 总样本</span><span><b>{run?.success ?? 0}</b>成功</span><span><b>{run?.degraded ?? 0}</b>降级</span><span><b>{run?.failed ?? 0}</b>失败</span><span><b>{run?.averageElapsedMs ?? 0}ms</b>平均耗时</span><span><b>{run?.traceWarnings ?? 0}</b>Trace 告警</span></div>
          <div className="batch-run-meta"><span>{run ? run.runId : '任务尚无执行记录'}</span><span>{run ? serviceStatusLabel(run.serviceStatus) : task?.toolWsBaseUrl}</span></div>
        </section>
        <section className="batch-workspace">
          <div className="batch-table-panel"><div className="batch-table-toolbar"><strong>样本结果</strong><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">全部状态</option><option value="success">成功</option><option value="degraded">降级</option><option value="failed">失败</option><option value="unsupported">不支持</option></select><select value={traceFilter} onChange={(event) => setTraceFilter(event.target.value)}><option value="all">全部 Trace</option><option value="available">Trace 正常</option><option value="warning">Trace 告警</option></select></div>
            <div className="batch-table-scroll"><table><thead><tr><th>样本</th><th>状态</th><th>耗时</th><th>尝试</th><th>Trace</th></tr></thead><tbody>{visibleSamples.map((sample) => <tr key={sample.id} className={selectedSampleId === sample.id ? 'is-selected' : ''} onClick={() => setSelectedSampleId(sample.id)}><td><strong>{sample.id}</strong><small>{sample.title}</small></td><td><span className={`batch-status ${sample.status}`}>{statusLabel(sample.status)}</span>{sample.errorCode && <small>{sample.errorCode}</small>}</td><td>{sample.elapsedMs ? `${sample.elapsedMs}ms` : '—'}</td><td>{sample.attemptCount}</td><td><span className={`batch-trace ${sample.traceStatus}`}>{sample.traceStatus}</span><small>{sample.traceRecordCount} 条</small></td></tr>)}</tbody></table>{!visibleSamples.length && <div className="batch-empty">{run ? '暂无匹配结果' : '尚无执行结果'}</div>}</div>
          </div>
          <div className="batch-detail-panel"><div className="batch-detail-tabs">{['preview', 'request', 'response', 'artifact'].map((tab) => <button type="button" key={tab} className={detailTab === tab ? 'is-active' : ''} onClick={() => setDetailTab(tab)}>{({ preview: '预览', request: '请求', response: '响应', artifact: '产物' } as Record<string, string>)[tab]}</button>)}{run && detail && <Link className="batch-trace-button" to={`/batch/runs/${encodeURIComponent(run.runId)}/samples/${encodeURIComponent(detail.summary.id)}/trace`} target="_blank" rel="noopener noreferrer">Trace</Link>}</div>
            <div className="batch-detail-body">{!detail && <div className="batch-empty">选择已完成的样本查看详情</div>}{detail && detailTab === 'preview' && <div className={`batch-render-comparison ${detail.deviceCapture?.cardUrl ? 'has-device' : ''}`}><section>{activeAttempt?.genui ? <CardRenderer key={`${run?.runId}-${selectedSampleId}`} initialValue={activeAttempt.genui} assetBaseUrl={DEFAULT_ASSET_BASE_URL} cardSize={activeCardSize} previewOnly zoom={previewZoom} onZoomChange={setPreviewZoom} /> : <div className="batch-empty">该样本没有可预览的 GenUI</div>}</section>{detail.deviceCapture?.cardUrl && <section><strong>真机渲染</strong><div className="device-capture-preview"><img src={detail.deviceCapture.cardUrl} alt={`${detail.summary.title ?? detail.summary.id} 真机渲染截图`} /><a href={detail.deviceCapture.fullUrl} target="_blank" rel="noopener noreferrer">查看全屏原图 ↗</a></div></section>}{!detail.deviceCapture?.cardUrl && detail.deviceCapture?.status !== 'not_requested' && <section><strong>真机渲染</strong><div className="batch-empty">{detail.deviceCapture?.error || '真机截图尚不可用'}</div></section>}</div>}{detail && detailTab === 'request' && <pre>{jsonText(activeAttempt?.request)}</pre>}{detail && detailTab === 'response' && <pre>{jsonText(activeAttempt?.response)}</pre>}{detail && detailTab === 'artifact' && <pre>{jsonText(activeAttempt?.blocks)}</pre>}</div>
          </div>
        </section>
      </main>
    </div>
  );
}
