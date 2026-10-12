import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { getBatchRun, listBatchRuns, type BatchRun } from '../batchApi';
import { useQualityRun } from '../components/useQualityRun';

export function QualityRoute() {
  const [params, setParams] = useSearchParams();
  const runId = params.get('runId') ?? '';
  const [runs, setRuns] = useState<BatchRun[]>([]);
  const [run, setRun] = useState<BatchRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [mode, setMode] = useState('all');
  const [count, setCount] = useState('1');
  const [ids, setIds] = useState('');
  const [checked, setChecked] = useState<string[]>([]);
  const [confirmed, setConfirmed] = useState<string[] | null>(null);
  const scoring = useQualityRun(runId);

  useEffect(() => {
    let cancelled = false;
    listBatchRuns().then((items) => {
      if (!cancelled) setRuns(items.filter((item) => item.status === 'completed'));
    }).catch((reason) => { if (!cancelled) setError(String(reason)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setRun(null); setConfirmed(null); setMode('all'); setChecked([]); setIds('');
    if (runId) {
      setError('');
      getBatchRun(runId).then((item) => {
        if (cancelled) return;
        if (item.status !== 'completed') throw new Error('只能选择已完成的批次');
        setRun(item);
      }).catch((reason) => { if (!cancelled) setError(String(reason)); });
    }
    return () => { cancelled = true; };
  }, [runId]);

  const samples = run?.runId === runId ? run.samples : [];
  const requestedIds = mode === 'ids' ? ids.trim().split(/[\s,，;；]+/).filter(Boolean) : checked;
  const selectedIds = mode === 'all' ? samples.map((sample) => sample.id)
    : mode === 'count' ? samples.slice(0, Number(count)).map((sample) => sample.id)
      : samples.filter((sample) => requestedIds.includes(sample.id)).map((sample) => sample.id);
  let selectionError = '';
  if (mode === 'count' && (!Number.isInteger(Number(count)) || Number(count) < 1 || Number(count) > samples.length)) {
    selectionError = `前 N 条需为 1 至 ${samples.length} 的整数`;
  } else if (mode === 'ids' && new Set(requestedIds).size !== requestedIds.length) {
    selectionError = '指定 ID 不能重复';
  } else if (mode === 'ids' && requestedIds.some((id) => !samples.some((sample) => sample.id === id))) {
    selectionError = `未知样本 ID：${requestedIds.filter((id) => !samples.some((sample) => sample.id === id)).join('、')}`;
  } else if (!selectedIds.length) {
    selectionError = '请至少选择一个样本';
  }
  const gallery = run?.postprocessExecutions?.find((item) => (
    item.plugins?.some((plugin) => plugin.id === 'browser-gallery' && plugin.status !== 'queued')
  ));
  const galleryPath = gallery
    ? `/batch/runs/${encodeURIComponent(runId)}/postprocess/${encodeURIComponent(gallery.executionId)}/plugins/browser-gallery`
    : run?.taskId ? `/batch/tasks/${encodeURIComponent(run.taskId)}` : `/batch/legacy/${encodeURIComponent(runId)}`;

  return <div className="quality-page">
    <header className="batch-center-header">
      <div><h1>质量评分</h1><p>选择已完成批次和样本，确认后手动运行 Web 质量评分。</p></div>
      <nav className="quality-links" aria-label="质量工具"><Link to="/quality/evaluation">评估方案</Link><Link to="/quality/compare">批次对比</Link></nav>
    </header>
    {(error || scoring.error) && <div className="batch-error" role="alert">{error || scoring.error}</div>}
    <fieldset className="quality-card" disabled={scoring.busy} onChange={() => setConfirmed(null)}>
      <legend>1. 选择批次与样本</legend>
      <label className="quality-field">已完成批次<select value={runId} onChange={(event) => setParams(event.target.value ? { runId: event.target.value } : {})}>
        <option value="">请选择批次</option>
        {runs.map((item) => <option key={item.runId} value={item.runId}>
          {item.name ? `${item.name} · ` : ''}{item.runId} · {item.total} 个样本 · {item.finishedAt || item.startedAt}
        </option>)}
      </select></label>
      {loading && <p role="status">正在加载批次…</p>}
      {!loading && !runs.length && !error && <p>暂无已完成批次，请先到批跑中心完成运行。</p>}
      {runId && !run && !error && <p role="status">正在加载样本…</p>}
      {run && <>
        <div className="quality-controls">
          <label className="quality-field">样本范围<select value={mode} onChange={(event) => setMode(event.target.value)}>
            <option value="all">全部样本</option><option value="count">前 N 条</option>
            <option value="ids">指定 ID</option><option value="checkbox">逐项勾选</option>
          </select></label>
          {mode === 'count' && <label className="quality-field">前 N 条<input type="number" min="1" max={samples.length} step="1" value={count} onChange={(event) => setCount(event.target.value)} /></label>}
          {mode === 'ids' && <label className="quality-field">样本 ID<textarea placeholder="用逗号或空白分隔" value={ids} onChange={(event) => setIds(event.target.value)} /></label>}
          <p>已选择 {selectedIds.length} / {samples.length} 个样本</p>
        </div>
        <div className="quality-table-scroll"><table className="quality-table">
          <thead><tr><th>选择</th><th>样本 ID</th><th>query</th><th>size</th><th>status</th></tr></thead>
          <tbody>{samples.map((sample) => <tr key={sample.id}>
            <td><input type="checkbox" aria-label={`选择样本 ${sample.id}`} checked={selectedIds.includes(sample.id)} onChange={(event) => {
              setChecked(event.target.checked ? [...selectedIds, sample.id] : selectedIds.filter((id) => id !== sample.id));
              setMode('checkbox');
            }} /></td><td>{sample.id}</td><td>{sample.query}</td><td>{sample.size || '—'}</td><td>{sample.status}</td>
          </tr>)}</tbody>
        </table></div>
        {selectionError && <p className="quality-warning" role="alert">{selectionError}</p>}
        <button type="button" className="batch-create-submit" disabled={Boolean(selectionError)} onClick={() => setConfirmed([...selectedIds])}>确认导入样本</button>
      </>}
    </fieldset>
    <section className="quality-card" aria-label="运行评分">
      <h2>2. 运行评分</h2>
      <p>{confirmed ? `已确认 ${confirmed.length} 个样本；修改批次或范围后需重新确认。` : '先确认导入样本，再点击运行评分。'}</p>
      <p className="quality-warning">将复用已有画廊依赖。旧证据可能导致待评，请先显式再次运行画廊，再运行评分。100 分不代表训练验收通过。</p>
      {run && <p><Link to={galleryPath}>前往画廊／后处理</Link></p>}
      <button type="button" className="batch-create-submit" disabled={!confirmed || Boolean(selectionError) || scoring.busy} onClick={() => { if (confirmed) void scoring.start(confirmed); }}>
        {scoring.busy ? scoring.status : '运行评分'}
      </button>
      {scoring.busy && <p role="status">{scoring.status} 完成后自动打开原评分看板。</p>}
    </section>
  </div>;
}
