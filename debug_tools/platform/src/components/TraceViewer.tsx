import { CSSProperties, useEffect, useMemo, useRef, useState } from 'react';
import { BatchAttempt, TraceArtifact, TraceNode, TraceView } from '../batchApi';
import { TraceContent } from './TraceContent';

const PHASES = new Set(['prepare', 'plan', 'dsl', 'validation', 'repair', 'artifact', 'response']);
const FAILURE = new Set(['failed', 'error', 'timeout', 'invalid', 'cancelled']);
const STATUS: Record<string, string> = {
  success: '成功', failed: '失败', error: '错误', timeout: '超时', cancelled: '已取消',
  degraded: '降级', recovered: '已恢复', unsupported: '不支持', skipped: '已跳过',
  complete: '完整', partial: '部分', missing: '缺失', invalid: '无效',
};
type Tab = 'overview' | 'input' | 'output' | 'diagnostic' | 'raw';
const TABS: Array<{ id: Tab; label: string }> = [
  { id: 'overview', label: '概览' }, { id: 'input', label: '输入' }, { id: 'output', label: '输出' },
  { id: 'diagnostic', label: '诊断' }, { id: 'raw', label: '原始记录' },
];
const ms = (value: unknown) => typeof value === 'number' && Number.isFinite(value)
  ? value >= 1000 ? `${(value / 1000).toFixed(2)} s` : `${value.toFixed(2)} ms` : '—';

function ancestry(node: TraceNode, map: Map<string, TraceNode>): TraceNode[] {
  const result: TraceNode[] = [];
  const seen = new Set<string>([node.id]);
  let parent = node.parentId ? map.get(node.parentId) : undefined;
  while (parent && !seen.has(parent.id)) {
    result.unshift(parent);
    seen.add(parent.id);
    parent = parent.parentId ? map.get(parent.parentId) : undefined;
  }
  return result;
}

function order(nodes: TraceNode[]): Array<{ node: TraceNode; depth: number }> {
  const map = new Map(nodes.map((node) => [node.id, node]));
  const children = new Map<string, TraceNode[]>();
  nodes.forEach((node) => {
    const parent = node.parentId && map.has(node.parentId) ? node.parentId : '';
    children.set(parent, [...(children.get(parent) ?? []), node]);
  });
  const rows: Array<{ node: TraceNode; depth: number }> = [];
  const visited = new Set<string>();
  const visit = (node: TraceNode, depth: number) => {
    if (visited.has(node.id)) return;
    visited.add(node.id);
    rows.push({ node, depth });
    (children.get(node.id) ?? []).sort((a, b) => a.startOffsetMs - b.startOffsetMs).forEach((child) => visit(child, depth + 1));
  };
  (children.get('') ?? []).sort((a, b) => a.startOffsetMs - b.startOffsetMs).forEach((node) => visit(node, 0));
  nodes.filter((node) => !visited.has(node.id)).forEach((node) => visit(node, 0));
  return rows;
}

function contents(node: TraceNode, tab: Tab): TraceArtifact[] {
  const refs = node.kind === 'group' ? node.contentIndex ?? node.artifacts : node.artifacts;
  const roles = tab === 'input' ? ['input'] : tab === 'output' ? ['output', 'snapshot'] : ['diagnostic'];
  return refs.filter((ref) => roles.includes(ref.role));
}

function Inspector({ node, runId, map, fullWidth, onFullWidth, onSelect }: {
  node: TraceNode | null; runId: string; map: Map<string, TraceNode>;
  fullWidth: boolean; onFullWidth: () => void; onSelect: (id: string) => void;
}) {
  const [tab, setTab] = useState<Tab>('overview');
  useEffect(() => {
    if (!node || node.kind === 'group') { setTab('overview'); return; }
    const first = (['input', 'output', 'diagnostic'] as Tab[]).find((id) => contents(node, id).length > 0);
    setTab(first ?? 'overview');
  }, [node?.id]);
  if (!node) return <div className="batch-empty">选择阶段或步骤查看详情</div>;
  const refs = contents(node, tab);
  const ownRefs = node.contentIndex ?? node.artifacts;
  return <section className="trace-inspector" aria-label="节点详情">
    <header className="trace-inspector-heading">
      <div className="trace-breadcrumb">{[...ancestry(node, map), node].map((parent) => (
        <button key={parent.id} onClick={() => onSelect(parent.id)}>{parent.title || parent.name}</button>
      ))}</div>
      <h2>{node.title || node.name}</h2>
      <p>{STATUS[node.status] || node.status} · {ms(node.durationMs)} {node.description}</p>
      <button className="trace-expand-content" onClick={onFullWidth}>{fullWidth ? '恢复左右布局' : '正文全宽查看'}</button>
    </header>
    <nav aria-label="节点内容">
      {TABS.map(({ id, label }) => {
        const count = ['input', 'output', 'diagnostic'].includes(id) ? contents(node, id).length : undefined;
        return <button key={id} className={tab === id ? 'is-active' : ''} disabled={count === 0}
          title={count === 0 ? `该节点没有${label}内容` : label} onClick={() => setTab(id)}>
          {label}{count !== undefined ? ` (${count})` : ''}
        </button>;
      })}
    </nav>
    {tab === 'overview' && <div className="trace-overview">
      <dl className="trace-node-overview">
        <div><dt>业务阶段 / 操作</dt><dd>{node.title}<small>{node.operation}</small></dd></div>
        <div><dt>执行区间</dt><dd>{ms(node.startOffsetMs)} → {ms(node.startOffsetMs + (node.durationMs ?? 0))}</dd></div>
        <div><dt>执行结果</dt><dd>{STATUS[node.status] || node.status} {node.description}</dd></div>
        <div><dt>指标</dt><dd><pre>{JSON.stringify(node.metrics, null, 2)}</pre></dd></div>
        <div><dt>属性</dt><dd><pre>{JSON.stringify(node.attributes, null, 2)}</pre></dd></div>
      </dl>
      <div className="trace-content-directory"><h3>内容目录 · {ownRefs.length}</h3>
        {!ownRefs.length && <p>该区间仅记录执行状态和指标，没有独立内容。</p>}
        {ownRefs.map((ref) => <button key={ref.id} onClick={() => {
          if (ref.ownerNodeId && ref.ownerNodeId !== node.id) onSelect(ref.ownerNodeId);
          else setTab(ref.role === 'snapshot' ? 'output' : ref.role);
        }}><strong>{ref.label || ref.name}</strong>
          <span>来源：{map.get(ref.ownerNodeId ?? '')?.title || node.title} · {ref.bytes.toLocaleString()} B</span>
          {!ref.available && <span className="trace-local-error">{ref.error}</span>}
        </button>)}
      </div>
    </div>}
    {tab === 'raw' && <pre className="trace-raw">{JSON.stringify({ span: node.raw, events: node.events }, null, 2)}</pre>}
    {['input', 'output', 'diagnostic'].includes(tab) && <div className="trace-artifacts">
      {refs.map((ref, index) => <TraceContent key={`${runId}:${ref.id}`} artifact={ref} runId={runId}
        source={map.get(ref.ownerNodeId ?? '')?.title || node.title || node.name} autoLoad={index === 0} />)}
    </div>}
  </section>;
}

export function TraceViewer({ runId, attempts }: { runId: string; attempts: BatchAttempt[] }) {
  const traced = attempts.filter((attempt) => attempt.trace);
  const [attemptName, setAttemptName] = useState(traced.at(-1)?.name ?? '');
  const [search, setSearch] = useState('');
  const [failedOnly, setFailedOnly] = useState(false);
  const [technical, setTechnical] = useState(false);
  const [category, setCategory] = useState('all');
  const [attemptTag, setAttemptTag] = useState('all');
  const [selectedId, setSelectedId] = useState('');
  const [collapsed, setCollapsed] = useState(new Set<string>());
  const [zoomId, setZoomId] = useState('');
  const [split, setSplit] = useState(55);
  const [fullWidth, setFullWidth] = useState(false);
  const main = useRef<HTMLDivElement>(null);
  const view = traced.find((attempt) => attempt.name === attemptName)?.trace;
  const map = useMemo(() => new Map((view?.nodes ?? []).map((node) => [node.id, node])), [view]);
  const ordered = useMemo(() => order(view?.nodes ?? []), [view]);
  const parents = new Set((view?.nodes ?? []).map((node) => node.parentId));
  const phaseNodes = (view?.nodes ?? []).filter((node) => PHASES.has(node.operation ?? ''));
  const attemptOptions = Array.from(new Set((view?.nodes ?? []).flatMap((node) => (
    Object.entries(node.attempts).map(([key, value]) => `${key}:${value}`)
  ))));
  useEffect(() => { setAttemptName(traced.at(-1)?.name ?? ''); }, [attempts]);
  useEffect(() => {
    setCollapsed(new Set((view?.nodes ?? []).filter((node) => (
      node.kind === 'model' || (node.kind === 'group' && !PHASES.has(node.operation ?? '') && node.operation !== 'request' && node.operation !== 'interface.attempt')
    )).map((node) => node.id)));
    setSelectedId(phaseNodes[0]?.id ?? view?.nodes.find((node) => !node.parentId)?.id ?? '');
    setZoomId('');
    setSearch('');
    setFailedOnly(false);
    setCategory('all');
    setAttemptTag('all');
    setFullWidth(false);
  }, [view?.traceId, attemptName]);
  const filtering = !!search.trim() || failedOnly || category !== 'all' || attemptTag !== 'all';
  const matching = new Set<string>();
  ordered.forEach(({ node }) => {
    if (search.trim() && !`${node.title} ${node.name} ${node.description}`.toLowerCase().includes(search.trim().toLowerCase())) return;
    if (failedOnly && !FAILURE.has(node.status)) return;
    if (category !== 'all' && ![node, ...ancestry(node, map)].some((item) => item.operation === category)) return;
    if (attemptTag !== 'all' && !Object.entries(node.attempts).some(([key, value]) => `${key}:${value}` === attemptTag)) return;
    matching.add(node.id);
    ancestry(node, map).forEach((parent) => matching.add(parent.id));
  });
  const visible = ordered.filter(({ node }) => (
    matching.has(node.id) && (filtering || !ancestry(node, map).some((parent) => collapsed.has(parent.id)))
  ));
  const selected = map.get(selectedId) ?? visible[0]?.node ?? null;
  const zoom = map.get(zoomId);
  const rangeStart = zoom?.startOffsetMs ?? 0;
  const rangeEnd = zoom ? zoom.startOffsetMs + (zoom.durationMs ?? 0) : Math.max(
    Number(view?.summary.totalDurationMs) || 0,
    ...(view?.nodes ?? []).map((node) => node.startOffsetMs + (node.durationMs ?? 0)), 1,
  );
  const duration = Math.max(rangeEnd - rangeStart, 0.001);
  const selectedAncestors = new Set(selected ? ancestry(selected, map).map((node) => node.id) : []);
  const select = (id: string) => {
    setSelectedId(id);
    const node = map.get(id);
    if (node) setCollapsed((old) => {
      const next = new Set(old);
      ancestry(node, map).forEach((parent) => next.delete(parent.id));
      return next;
    });
  };

  if (!traced.length) return <div className="batch-empty">该样本没有可用 Trace</div>;
  if (!view) return <div className="batch-empty">所选 attempt 没有 Trace</div>;
  const rawOnly = view.rawOnly || view.viewVersion !== 'trace-view-v2' || view.instrumentationVersion !== 2;
  return <div className="trace-viewer trace-semantic">
    <header className="trace-summary">
      <div className="trace-warning-banner">Trace 包含完整请求、提示词与模型输出，仅用于本地调试。</div>
      <div className="trace-summary-row">
        <select aria-label="批跑 attempt" value={attemptName} onChange={(event) => setAttemptName(event.target.value)}>
          {traced.map((attempt) => <option key={attempt.name}>{attempt.name}</option>)}
        </select>
        <span className={`trace-state ${view.status}`}>{STATUS[view.status] || view.status}</span>
        <span><b>{STATUS[String(view.summary.status)] || view.summary.status as string || '—'}</b>生成结果</span>
        <span><b>{ms(view.summary.totalDurationMs)}</b>全链路耗时</span>
        <span><b>{String(view.summary.modelPhysicalCalls ?? '—')}</b>物理模型调用</span>
        <span><b>{String(view.summary.retryCount ?? '—')}</b>重试</span>
        <span><b>{String(view.summary.totalTokens ?? '—')}</b>Token</span>
        <span><b>{ms(view.summary.firstTokenMs)}</b>首 Token</span>
      </div>
      {view.warnings.length > 0 && <p role="status">{view.warnings.join('；')}</p>}
    </header>
    {rawOnly ? <div className="trace-legacy"><p>旧埋点仅提供原始查看，请重新批跑使用阶段视图。</p>
      <pre>{JSON.stringify(view.rawRecords ?? view.nodes.map((node) => node.raw), null, 2)}</pre></div>
      : <>
        <div className="trace-filters">
          <input aria-label="搜索 Trace 节点" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索中文阶段、步骤或错误" />
          <select aria-label="分类" value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="all">全部阶段</option>
            {Array.from(new Map(phaseNodes.map((node) => [node.operation, node.title])).entries()).map(([id, title]) => <option key={id} value={id}>{title}</option>)}
          </select>
          <select aria-label="节点 attempt" value={attemptTag} onChange={(event) => setAttemptTag(event.target.value)}>
            <option value="all">全部尝试</option>{attemptOptions.map((tag) => <option key={tag}>{tag}</option>)}
          </select>
          <label><input type="checkbox" checked={failedOnly} onChange={(event) => setFailedOnly(event.target.checked)} />仅失败</label>
          <button onClick={() => {
            setTechnical(!technical);
            setCollapsed(technical ? new Set((view.nodes).filter((node) => node.kind === 'model').map((node) => node.id)) : new Set());
          }}>{technical ? '阶段视图' : '完整技术轨迹'}</button>
        </div>
        <div className="trace-timeline-toolbar">
          <span>浅色范围＝父区间　实心条＝执行步骤　◆＝极短步骤　●＝事件</span>
          <button disabled={!selected || !selected.durationMs} onClick={() => setZoomId(selected?.id ?? '')}>缩放到所选区间</button>
          <button disabled={!zoomId} onClick={() => setZoomId('')}>恢复全请求时间轴</button>
        </div>
        <div ref={main} className={`trace-main${fullWidth ? ' trace-main-full' : ''}`} style={{ '--trace-split': `${split}%` } as CSSProperties}>
          <div className="trace-waterfall" aria-label="阶段树与时间轴">
            <div className="trace-scale"><span>{ms(rangeStart)}</span><span>{ms(rangeStart + duration / 2)}</span><span>{ms(rangeEnd)}</span></div>
            {!visible.length && <div className="batch-empty">没有匹配的节点</div>}
            {visible.map(({ node, depth }) => {
              const ancestors = ancestry(node, map);
              const phase = [...ancestors, node].find((item) => PHASES.has(item.operation ?? ''))?.operation ?? 'prepare';
              const left = Math.max(0, (node.startOffsetMs - rangeStart) / duration * 100);
              const end = Math.min(100, (node.startOffsetMs + (node.durationMs ?? 0) - rangeStart) / duration * 100);
              const width = Math.max(0, end - left);
              const inRange = node.startOffsetMs <= rangeEnd && node.startOffsetMs + (node.durationMs ?? 0) >= rangeStart;
              const relation = selectedAncestors.has(node.id) || node.parentId === selected?.id;
              const allRefs = node.contentIndex ?? node.artifacts;
              return <div key={node.id} className={`trace-tree-row phase-${phase}${node.id === selected?.id ? ' is-selected' : ''}${relation ? ' is-related' : ''}${FAILURE.has(node.status) ? ' is-failed' : ''}`}>
                <div className="trace-tree-label" style={{ '--depth': depth } as CSSProperties}>
                  <span className="trace-tree-guide" aria-hidden="true" />
                  {parents.has(node.id) ? <button className="trace-toggle" aria-label={`${collapsed.has(node.id) ? '展开' : '折叠'} ${node.title}`} aria-expanded={!collapsed.has(node.id)} onClick={() => setCollapsed((old) => {
                    const next = new Set(old); if (next.has(node.id)) next.delete(node.id); else next.add(node.id); return next;
                  })}>{collapsed.has(node.id) ? '▸' : '▾'}</button> : <span className="trace-toggle-space" />}
                  <button className="trace-select-node" onClick={() => select(node.id)} title={`${node.title} · ${node.name}`}>
                    <strong>{FAILURE.has(node.status) ? '⚠ ' : ''}{node.title || node.name}</strong>
                    <small>{STATUS[node.status] || node.status} · {ms(node.durationMs)} · {allRefs.length} 项内容</small>
                    {technical && <code>{node.name}</code>}
                  </button>
                </div>
                <button className="trace-time-track" onClick={() => select(node.id)} aria-label={`选择 ${node.title} 时间区间`}>
                  {inRange && <span className={`trace-time-bar ${node.kind === 'group' ? 'is-group' : ''}${width < 0.4 ? 'is-point' : ''}`} style={{ left: `${Math.min(left, 100)}%`, width: `${width}%` }} title={`${ms(node.startOffsetMs)} · ${ms(node.durationMs)}`} />}
                  {technical && node.events?.map((event, index) => {
                    const offset = Number(event.startOffsetMs);
                    if (offset < rangeStart || offset > rangeEnd) return null;
                    return <i className="trace-event-point" key={String(event.eventId ?? index)} style={{ left: `${(offset - rangeStart) / duration * 100}%` }} title={`${event.event} · ${ms(offset)}`} />;
                  })}
                </button>
              </div>;
            })}
          </div>
          <div className="trace-splitter" role="separator" aria-label="调整阶段树宽度" aria-orientation="vertical" aria-valuenow={split} tabIndex={0}
            onKeyDown={(event) => { if (event.key === 'ArrowLeft') setSplit((n) => Math.max(30, n - 2)); if (event.key === 'ArrowRight') setSplit((n) => Math.min(75, n + 2)); }}
            onPointerDown={(event) => event.currentTarget.setPointerCapture(event.pointerId)}
            onPointerMove={(event) => { if (!event.currentTarget.hasPointerCapture(event.pointerId) || !main.current) return;
              const bounds = main.current.getBoundingClientRect(); setSplit(Math.max(30, Math.min(75, (event.clientX - bounds.left) / bounds.width * 100))); }}
            onPointerUp={(event) => event.currentTarget.releasePointerCapture(event.pointerId)} />
          <Inspector node={selected} runId={runId} map={map} fullWidth={fullWidth} onFullWidth={() => setFullWidth(!fullWidth)} onSelect={select} />
        </div>
      </>}
  </div>;
}
