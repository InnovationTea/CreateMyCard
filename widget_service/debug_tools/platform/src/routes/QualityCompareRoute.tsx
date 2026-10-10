import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  getQualityComparison, listBatchRuns, type BatchRun, type QualityComparison,
  type QualityComparisonSide, type QualityComparisonSummary, type QualityIssueDiff,
} from '../batchApi';

const ALIGNMENT: Record<string, string> = {
  matched: '已匹配', 'right-only': '仅右侧有样本（左侧缺失）', 'left-only': '仅左侧有样本（右侧缺失）',
  'context-missing': '缺少 query / size 快照', 'context-mismatch': 'query / size 不一致',
  'policy-mismatch': '评分口径不一致', 'evidence-mismatch': '证据口径不一致', 'pending-score': '待评',
};

function numberText(value: number | null, suffix = '') {
  return value === null ? '—' : `${value.toFixed(1)}${suffix}`;
}

function deltaText(value: number | null) {
  return value === null ? '不可比' : `${value > 0 ? '+' : ''}${value.toFixed(1)}`;
}

function IssueTable({ title, rows, comparable }: { title: string; rows: QualityIssueDiff[]; comparable: boolean }) {
  return <section><h3>{title}</h3>{rows.length ? <table className="quality-table">
    <thead><tr><th>问题 code</th><th>左侧卡数</th><th>右侧卡数</th><th>差值（右−左）</th></tr></thead>
    <tbody>{rows.map((row) => <tr key={row.code}><td>{row.code}</td><td>{row.left}</td><td>{row.right}</td><td>{comparable ? deltaText(row.delta) : '不可比'}</td></tr>)}</tbody>
  </table> : <p>无记录</p>}</section>;
}

function Summary({ title, value }: { title: string; value: QualityComparisonSummary }) {
  return <section className="quality-card"><h2>{title}</h2>
    <Link to={`/batch/runs/${encodeURIComponent(value.runId)}/postprocess/${encodeURIComponent(value.executionId)}/plugins/quality-score`}>
      {value.runId} · {value.executionId}
    </Link>
    <p>本次样本 {value.total} · 已评分 {value.scored} · 待评 {value.total - value.scored}</p>
    <p>通过 {value.passCount} · 通过率 {numberText(value.passRate, '%')} · 均分 {numberText(value.meanScore)}</p>
  </section>;
}

function Side({ value }: { value: QualityComparisonSide | null }) {
  if (!value) return <span>缺失</span>;
  return <div>
    <strong>{value.score === null ? '待评' : `得分 ${numberText(value.score)} · 下界 ${numberText(value.scoreLow)}`}</strong>
    <p>{value.verdict}</p><p>{value.query || 'query 快照缺失'}</p><small>{value.size || 'size 快照缺失'}</small>
  </div>;
}

export function QualityCompareRoute() {
  const [params, setParams] = useSearchParams();
  const [leftRunId, setLeftRunId] = useState(params.get('leftRunId') ?? '');
  const [rightRunId, setRightRunId] = useState(params.get('rightRunId') ?? '');
  const [leftExecutionId, setLeftExecutionId] = useState(params.get('leftExecutionId') ?? '');
  const [rightExecutionId, setRightExecutionId] = useState(params.get('rightExecutionId') ?? '');
  const [runs, setRuns] = useState<BatchRun[]>([]);
  const [comparison, setComparison] = useState<QualityComparison | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const request = useRef(0);
  const left = params.get('leftRunId') ?? '';
  const right = params.get('rightRunId') ?? '';
  const leftExecution = params.get('leftExecutionId') ?? '';
  const rightExecution = params.get('rightExecutionId') ?? '';

  useEffect(() => {
    let cancelled = false;
    listBatchRuns().then((items) => { if (!cancelled) setRuns(items.filter((item) => item.status === 'completed')); })
      .catch((reason) => { if (!cancelled) setError(String(reason)); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    setLeftRunId(left); setRightRunId(right); setLeftExecutionId(leftExecution); setRightExecutionId(rightExecution);
    const current = ++request.current;
    setComparison(null); setError(''); setBusy(Boolean(left && right));
    if (left && right) getQualityComparison({ leftRunId: left, rightRunId: right, leftExecutionId: leftExecution, rightExecutionId: rightExecution })
      .then((value) => { if (request.current === current) setComparison(value); })
      .catch((reason) => { if (request.current === current) setError(String(reason)); })
      .finally(() => { if (request.current === current) setBusy(false); });
    return () => { request.current++; };
  }, [left, right, leftExecution, rightExecution, revision]);

  return <div className="quality-page">
    <header className="batch-center-header"><div><h1>批次评分对比</h1><p>默认读取两边最新已落盘终态评分；缺少结果时不会自动补跑。差值为右侧减左侧，得分差为正表示右侧更好。</p></div>
      <nav className="quality-links"><Link to="/quality">选择批次</Link><Link to="/quality/evaluation">评估方案</Link></nav></header>
    <form className="quality-card" onSubmit={(event) => {
      event.preventDefault();
      setRevision((value) => value + 1);
      setParams({ leftRunId, rightRunId, ...(leftExecutionId.trim() ? { leftExecutionId: leftExecutionId.trim() } : {}), ...(rightExecutionId.trim() ? { rightExecutionId: rightExecutionId.trim() } : {}) });
    }} onChange={() => { request.current++; setComparison(null); setBusy(false); setError(''); }}>
      <div className="quality-controls">
        <label className="quality-field">左侧批次<select required value={leftRunId} onChange={(event) => { setLeftRunId(event.target.value); setLeftExecutionId(''); }}>
          <option value="">请选择批次</option>{runs.map((item) => <option value={item.runId} key={item.runId}>{item.name ? `${item.name} · ` : ''}{item.runId}</option>)}
        </select></label>
        <label className="quality-field">左侧执行（可选）<input value={leftExecutionId} placeholder="默认最新终态评分" onChange={(event) => setLeftExecutionId(event.target.value)} /></label>
        <label className="quality-field">右侧批次<select required value={rightRunId} onChange={(event) => { setRightRunId(event.target.value); setRightExecutionId(''); }}>
          <option value="">请选择批次</option>{runs.map((item) => <option value={item.runId} key={item.runId}>{item.name ? `${item.name} · ` : ''}{item.runId}</option>)}
        </select></label>
        <label className="quality-field">右侧执行（可选）<input value={rightExecutionId} placeholder="默认最新终态评分" onChange={(event) => setRightExecutionId(event.target.value)} /></label>
      </div>
      <button className="batch-create-submit" disabled={!leftRunId || !rightRunId || busy}>{busy ? '正在读取…' : '加载对比'}</button>
    </form>
    {error && <div className="batch-error" role="alert">{error}</div>}
    {busy && <p role="status">正在加载对比…</p>}
    {comparison && <>
      <div className="quality-summary"><Summary title="左侧结果" value={comparison.left} /><Summary title="右侧结果" value={comparison.right} /></div>
      <section className="quality-card"><h2>{comparison.comparable ? '总体可比' : '总体不可直接比较'}</h2>
        <p>通过率差：{comparison.comparable && comparison.passRateDelta !== null ? `${deltaText(comparison.passRateDelta)} 个百分点` : '不可比'}</p>
        <p>{comparison.passDefinition}</p>
        {comparison.warnings.map((warning, index) => <p className="quality-warning" key={index}>{warning}</p>)}
      </section>
      <section className="quality-card"><h2>逐样本对比</h2><div className="quality-table-scroll"><table className="quality-table">
        <thead><tr><th>样本 ID / 对齐状态</th><th>左侧</th><th>右侧</th><th>得分差</th><th>问题差异</th></tr></thead>
        <tbody>{comparison.rows.map((row) => <tr key={row.sampleId}>
          <td><b>{row.sampleId}</b><p>{ALIGNMENT[row.alignment] ?? row.alignment}</p></td>
          <td><Side value={row.left} /></td><td><Side value={row.right} /></td>
          <td>{deltaText(row.scoreDelta)}</td><td>{row.issueDiff.length ? <details><summary>查看 {row.issueDiff.length} 项</summary>
            <IssueTable title="每卡去重问题" rows={row.issueDiff} comparable={row.alignment === 'matched'} />
          </details> : '无问题记录'}</td>
        </tr>)}</tbody>
      </table></div></section>
      <section className="quality-card"><h2>问题分布（每卡每 code 去重）</h2>
        <IssueTable title="确认问题" rows={comparison.confirmedIssueDistribution ?? []} comparable={comparison.comparable} />
        <IssueTable title="疑似／待确认问题" rows={comparison.pendingIssueDistribution ?? []} comparable={comparison.comparable} />
        <details><summary>全部问题分布</summary><IssueTable title="全部问题" rows={comparison.issueDistribution} comparable={comparison.comparable} /></details>
      </section>
    </>}
  </div>;
}
