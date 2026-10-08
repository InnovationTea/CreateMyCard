import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  getBatchRun,
  getPostprocessDashboard,
  getPostprocessSample,
  getPostprocessSamples,
  startPostprocess,
  type BatchRun,
  type PostprocessArtifact,
  type PostprocessDashboard,
  type PostprocessDashboardSample,
  type PostprocessSampleResult,
} from '../batchApi';
import { PostprocessArtifactView } from '../components/PostprocessArtifactView';

const PAGE_SIZE = 25;

function factText(value: unknown, format?: string): string {
  if (Array.isArray(value)) return value.length ? value.join('、') : '—';
  if (value === null || value === undefined || value === '') return '—';
  if (format === 'percent' && typeof value === 'number') return `${value.toFixed(1)}%`;
  return String(value);
}

function sampleTone(sample: PostprocessDashboardSample): string {
  const verdict = sample.facts.verdict;
  if (verdict === 'full') return 'success';
  if (verdict === 'missing' || verdict === 'no-output') return 'danger';
  return sample.status;
}

export function PostprocessDashboardRoute() {
  const { runId = '', executionId = '', pluginId = '' } = useParams();
  const navigate = useNavigate();
  const [run, setRun] = useState<BatchRun | null>(null);
  const [dashboard, setDashboard] = useState<PostprocessDashboard | null>(null);
  const [samples, setSamples] = useState<PostprocessDashboardSample[]>([]);
  const [total, setTotal] = useState(0);
  const [selectedId, setSelectedId] = useState('');
  const [sample, setSample] = useState<PostprocessSampleResult | null>(null);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [factValue, setFactValue] = useState('');
  const [sort, setSort] = useState('sequence');
  const [order, setOrder] = useState<'asc' | 'desc'>('asc');
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const loadDashboard = useCallback(async () => {
    const [nextRun, nextDashboard] = await Promise.all([
      getBatchRun(runId),
      getPostprocessDashboard(runId, executionId, pluginId),
    ]);
    setRun(nextRun);
    setDashboard(nextDashboard);
  }, [executionId, pluginId, runId]);

  const missingComponents = useMemo(() => Array.from(new Set(
    (dashboard?.samples ?? []).flatMap((item) => {
      const value = item.facts.missingComponents;
      return Array.isArray(value) ? value.map(String) : [];
    }),
  )).sort(), [dashboard]);

  const sampleFields = dashboard?.presentation.sampleFields ?? [];
  const selectedIndex = samples.findIndex((item) => item.sampleId === selectedId);
  const backPath = run?.taskId ? `/batch/tasks/${encodeURIComponent(run.taskId)}`
    : `/batch/legacy/${encodeURIComponent(runId)}`;
  const datasetArtifacts = dashboard?.datasetResult.artifacts ?? [];

  useEffect(() => {
    document.documentElement.classList.add('postprocess-dashboard-active');
    document.body.classList.add('postprocess-dashboard-active');
    return () => {
      document.documentElement.classList.remove('postprocess-dashboard-active');
      document.body.classList.remove('postprocess-dashboard-active');
    };
  }, []);

  useEffect(() => {
    loadDashboard().catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
  }, [loadDashboard]);

  useEffect(() => {
    if (!dashboard) return;
    const timer = window.setTimeout(() => {
      getPostprocessSamples(runId, executionId, pluginId, {
        offset, limit: PAGE_SIZE, q: query, status, sort, order,
        factKey: factValue ? 'missingComponents' : '', factValue,
      }).then((page) => {
        setSamples(page.items); setTotal(page.total);
        if (!selectedId || !page.items.some((item) => item.sampleId === selectedId)) {
          setSelectedId(page.items[0]?.sampleId ?? '');
        }
      }).catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
    }, 150);
    return () => window.clearTimeout(timer);
  }, [dashboard, executionId, factValue, offset, order, pluginId, query, runId, selectedId, sort, status]);

  useEffect(() => {
    if (!selectedId) { setSample(null); return; }
    getPostprocessSample(runId, executionId, pluginId, selectedId)
      .then(setSample)
      .catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
  }, [executionId, pluginId, runId, selectedId]);

  const changeExecution = (nextExecutionId: string) => {
    navigate(`/batch/runs/${encodeURIComponent(runId)}/postprocess/`
      + `${encodeURIComponent(nextExecutionId)}/plugins/${encodeURIComponent(pluginId)}`);
  };

  const rerun = async () => {
    setBusy(true); setError('');
    try {
      const execution = await startPostprocess(runId, [pluginId], {}, true);
      navigate(`/batch/runs/${encodeURIComponent(runId)}/postprocess/`
        + `${encodeURIComponent(execution.executionId)}/plugins/${encodeURIComponent(pluginId)}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  };

  if (!dashboard) return <main className="postprocess-dashboard-page"><div className="batch-empty">
    {error || '正在加载后处理看板…'}
  </div></main>;

  return <main className="postprocess-dashboard-page">
    <header className="postprocess-dashboard-header">
      <div>
        <Link to={backPath}>← 返回批量测试结果</Link>
        <h1>{dashboard.plugin.name}</h1>
        <p>后处理插件 · 当前结果 {dashboard.status}</p>
      </div>
      <div className="postprocess-dashboard-actions">
        <label>历史执行<select value={executionId} onChange={(event) => changeExecution(event.target.value)}>
          {(run?.postprocessExecutions ?? []).filter((item) => (
            item.plugins?.some((plugin) => plugin.id === pluginId)
          )).map((item) => <option key={item.executionId} value={item.executionId}>
            {item.createdAt} · {item.status}
          </option>)}
        </select></label>
        <button type="button" disabled={busy || run?.status !== 'completed'} onClick={rerun}>
          {busy ? '正在提交…' : '↻ 再次运行'}
        </button>
      </div>
    </header>
    {error && <div className="batch-error" role="alert">{error}</div>}
    <section className="postprocess-overview">
      {datasetArtifacts.map((artifact) => <PostprocessArtifactView key={artifact.key} artifact={artifact} />)}
      {!datasetArtifacts.length && <div className="postprocess-empty">该插件没有数据集层产物</div>}
    </section>
    <section className="postprocess-dashboard-workspace">
      <div className="postprocess-sample-browser">
        <div className="postprocess-toolbar">
          <label className="postprocess-search"><span aria-hidden="true">⌕</span><input
            aria-label="搜索样本" placeholder="搜索样本" value={query}
            onChange={(event) => { setQuery(event.target.value); setOffset(0); }}
          /></label>
          <select aria-label="全部状态" value={status} onChange={(event) => { setStatus(event.target.value); setOffset(0); }}>
            <option value="">全部状态</option><option value="success">成功</option>
            <option value="partial">部分完成</option><option value="failed">失败</option>
            <option value="skipped">未标注</option>
          </select>
          {missingComponents.length > 0 && <select aria-label="期望组件" value={factValue} onChange={(event) => { setFactValue(event.target.value); setOffset(0); }}>
            <option value="">期望组件</option>{missingComponents.map((value) => <option key={value}>{value}</option>)}
          </select>}
          <select aria-label="排序字段" value={sort} onChange={(event) => { setSort(event.target.value); setOffset(0); }}>
            <option value="sequence">样本顺序</option>
            {sampleFields.filter((field) => field.sortable).map((field) => (
              <option key={field.key} value={`fact:${field.key}`}>{field.label}</option>
            ))}
          </select>
          <button type="button" className="postprocess-order" onClick={() => setOrder((value) => value === 'asc' ? 'desc' : 'asc')}>
            {order === 'asc' ? '↑ 升序' : '↓ 降序'}
          </button>
        </div>
        <div className="postprocess-sample-table-scroll"><table className="postprocess-sample-table">
          <thead><tr><th>样本</th>{sampleFields.map((field) => <th key={field.key}>{field.label}</th>)}<th /></tr></thead>
          <tbody>{samples.map((item) => <tr key={item.sampleId} className={selectedId === item.sampleId ? 'is-selected' : ''} onClick={() => setSelectedId(item.sampleId)}>
            <td><b>{item.sampleId}</b><span>{item.title}</span></td>
            {sampleFields.map((field) => <td key={field.key} className={field.key === 'recallRate' ? sampleTone(item) : ''}>
              {factText(item.facts[field.key], field.format)}
            </td>)}
            <td aria-hidden="true">›</td>
          </tr>)}</tbody>
        </table>{!samples.length && <div className="postprocess-empty">暂无匹配样本</div>}</div>
        <footer className="postprocess-pagination">
          <span>共 {total} 条记录</span><div>
            <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>‹</button>
            <b>{Math.floor(offset / PAGE_SIZE) + 1}</b>
            <button type="button" disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>›</button>
          </div>
        </footer>
      </div>
      <aside className="postprocess-sample-inspector">
        {!sample && <div className="postprocess-empty">选择样本查看详情</div>}
        {sample && <>
          <header><div><h2>{selectedId} · {samples.find((item) => item.sampleId === selectedId)?.title}</h2>
            <p>{sample.summary}</p></div><div className="postprocess-inspector-nav">
              <button type="button" disabled={selectedIndex <= 0} onClick={() => setSelectedId(samples[selectedIndex - 1].sampleId)}>‹ 上一个</button>
              <button type="button" disabled={selectedIndex < 0 || selectedIndex >= samples.length - 1} onClick={() => setSelectedId(samples[selectedIndex + 1].sampleId)}>下一个 ›</button>
            </div></header>
          {typeof sample.facts?.recallRate === 'number' && <div className={`postprocess-recall-score ${Number(sample.facts.recallRate) === 100 ? 'success' : 'danger'}`}>
            召回率 <b>{Number(sample.facts.recallRate).toFixed(1)}%</b>
          </div>}
          <div className="postprocess-inspector-artifacts">
            {(sample.artifacts ?? []).map((artifact: PostprocessArtifact) => (
              <PostprocessArtifactView key={artifact.key} artifact={artifact} />
            ))}
            {!(sample.artifacts ?? []).length && <div className="postprocess-empty">该样本没有可展示产物</div>}
          </div>
        </>}
      </aside>
    </section>
  </main>;
}
