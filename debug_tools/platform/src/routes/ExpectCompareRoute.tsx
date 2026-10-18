import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { CardRenderer } from '@widget-debug/card-renderer';
import {
  compareExpectLive, compareExpectRun, listBatchRuns,
  type BatchRun, type ExpectComparison, type ExpectPair, type ExpectSampleSide,
} from '../batchApi';
import { DEFAULT_ASSET_BASE_URL } from '../config';
import { useWorkbench } from '../context';
import { sessionArtifacts } from '../sessionArtifacts';
import { clearCompareConfig, loadCompareConfig, saveCompareConfig } from '../compareState';

const TIER_LABEL: Record<string, string> = {
  matched: '已匹配',
  none: '未匹配',
  'no-fingerprint': '无筛选需求（按尺寸对齐）',
  'no-actual': '没有对应的实际输出',
};

/** 层级含义逐条摆出来，避免只看颜色猜结论。 */
const TIER_MEANING: Array<{ id: string; text: string }> = [
  { id: 'matched', text: '启用维度里的期望需求项全部命中（尺寸不参与判定）' },
  { id: 'none', text: '至少一个期望需求项在实际指纹里找不到' },
  { id: 'no-fingerprint', text: '期望侧没有需求项，只能按尺寸对齐' },
  { id: 'no-actual', text: '没有同名样本、无相同 Query，且「分类＋数据＋动作」强绑定不成立，因此不拿无关卡片硬凑' },
];

const SIZE_SOURCE_LABEL: Record<string, string> = {
  declared: '声明', derived: '判定', fallback: '缺省', unknown: '未确定',
};

const DIMENSIONS = [
  { id: 'data', label: '数据' },
  { id: 'actions', label: '动作' },
  { id: 'icons', label: '图标' },
] as const;

/** 这两档才算匹配上：内容全命中且尺寸一致，或期望侧本来就没有需求项。 */
const MATCHED_TIERS = new Set(['matched', 'no-fingerprint']);

type DimensionId = (typeof DIMENSIONS)[number]['id'];

/** 按实际样本分组的视图：右一张实际卡片，左侧列出所有匹配到它的期望卡片。 */
type ActualGroup = {
  key: string;
  actual: ExpectSampleSide | null;
  pairs: ExpectPair[];
};

function cardSize(size: string): 'auto' | '2x2' | '2x4' {
  if (size === '2x2' || size === '2x4') return size;
  return 'auto';
}

function requirementItems(side: ExpectSampleSide, kind: DimensionId): string[] {
  const explicit = side.explicit?.[kind] ?? [];
  if (kind === 'icons') {
    return explicit.length ? explicit : side.fingerprint.icons ?? [];
  }
  return explicit.length ? explicit : side.fingerprint[kind];
}

function labelOf(side: ExpectSampleSide, token: string): string {
  return side.labels?.data?.[token]
    ?? side.labels?.actions?.[token]
    ?? side.labels?.icons?.[token]
    ?? token;
}

/** 明细表里 token 可能属于任一维度，展示时把三份标签合起来查。 */
function allLabels(side: ExpectSampleSide): Record<string, string> {
  return {
    ...side.labels?.data, ...side.labels?.actions, ...side.labels?.icons,
  };
}

/** 批次统一显示「批次名 · runId」，没名字时只显示 ID。 */
function runLabel(item: BatchRun): string {
  const name = item.name ? `${item.name} · ` : '';
  return `${name}${item.runId}`;
}

/** 实际来源下拉里要区分批跑运行与导入的实际输出批次，否则两个批次摆一起看不出选的是哪个。 */
function actualRunLabel(item: BatchRun): string {
  return `${isImported(item) ? '[导入实际] ' : '[批跑] '}${runLabel(item)}`;
}

/** 导入批次按用途分侧：期望进左侧池子，实际输出进右侧来源；普通批跑运行都在右侧。 */
const isImported = (item: BatchRun) => item.sourceType === 'external-quality';
const isImportedExpect = (item: BatchRun) => isImported(item) && item.purpose !== 'actual';
const isImportedActual = (item: BatchRun) => isImported(item) && item.purpose === 'actual';

/** 运行时间可能是 ISO 也可能是本地 `2026/10/18 11:19:28`，按数值比较避免字符串格式差异。 */
function runTime(item: BatchRun): number {
  const raw = item.finishedAt ?? item.startedAt ?? '';
  const parsed = Date.parse(raw.replace(/\//g, '-'));
  return Number.isNaN(parsed) ? 0 : parsed;
}

function TokenChips({ items, labels, missing, flagClass = 'is-missing' }:
  {
    items: string[]; labels?: Record<string, string>;
    missing: Set<string>; flagClass?: string;
  }) {
  if (!items.length) return <span className="expect-empty">未声明</span>;
  return <div className="expect-chips">{items.map((item) => (
    <span key={item} className={`expect-chip ${missing.has(item) ? flagClass : 'is-hit'}`}
      title={labels?.[item] ? `${labels[item]} · ${item}` : item}>
      {/* 中文名只帮读，具体字段名必须一起露出，否则对不上入参和 DSL。 */}
      {labels?.[item] && <strong className="expect-chip-label">{labels[item]}</strong>}
      <code className="expect-chip-raw">{item}</code>
    </span>
  ))}</div>;
}

/** 分组布局较窄，默认按容器宽度缩放，避免预览被裁切出滚动条。 */
const PAIR_ZOOM = 130;

/** 卡片预览下方统一给出 Query、尺寸、数据、动作与图标，左右两侧同口径可读。 */
function SideCard({ side, expected = false, badge, missingData, missingActions, missingIcons,
  extraData, extraActions, extraIcons }:
  {
    side: ExpectSampleSide; expected?: boolean; badge?: ReactNode;
    missingData: Set<string>; missingActions: Set<string>; missingIcons: Set<string>;
    extraData: Set<string>; extraActions: Set<string>; extraIcons: Set<string>;
  }) {
  const [showImage, setShowImage] = useState(false);
  const [zoom, setZoom] = useState(PAIR_ZOOM);
  const dataItems = expected ? requirementItems(side, 'data') : side.fingerprint.data;
  const actionItems = expected ? requirementItems(side, 'actions') : side.fingerprint.actions;
  const iconItems = requirementItems(side, 'icons');
  const derived = side.sizeDerived && side.sizeDerived !== side.size ? `判定 ${side.sizeDerived}` : '';
  return <section className="expect-card">
    <header>
      <div className="expect-card-title">
        {/* 两侧身份写在卡片最前面，避免看预览时分不清哪边是期望、哪边是真实输出。 */}
        <span className={`expect-role ${expected ? 'is-expected' : 'is-actual'}`}>
          {expected ? '期望输出' : '真实输出'}
        </span>
        <strong>{side.title}</strong>
        {badge}
      </div>
      <small>{side.sampleId}{side.attempt ? ` · ${side.attempt}` : ''}
        {side.category ? ` · ${side.category}` : ''}</small>
    </header>
    <p className="expect-line"><span className="expect-key">Query</span>
      <span className="expect-value" title={side.query}>{side.query || '—'}</span></p>
    <p className="expect-line"><span className="expect-key">尺寸</span>
      <span className="expect-value">{side.size || '未确定'}
        {side.sizeSource ? `（${SIZE_SOURCE_LABEL[side.sizeSource] ?? side.sizeSource}）` : ''}
        {derived ? ` · ${derived}` : ''}</span></p>
    {/* 两侧导入时带的截图都只作参考图：默认渲染 DSL，勾上才看当时那张图。 */}
    {side.imageUrl && <label className="expect-toggle">
      <input type="checkbox" checked={showImage}
        onChange={(event) => setShowImage(event.target.checked)} />
      {expected ? '显示上传截图' : '显示导入截图'}
    </label>}
    {showImage && side.imageUrl
      ? <a href={side.imageUrl} target="_blank" rel="noreferrer">
        <img src={side.imageUrl} alt={`${side.sampleId} 上传截图`} /></a>
      : side.genui
        ? <CardRenderer key={`${side.sampleId}-${side.attempt}`} initialValue={side.genui}
          assetBaseUrl={DEFAULT_ASSET_BASE_URL} cardSize={cardSize(side.size)} previewOnly
          zoom={zoom} onZoomChange={setZoom} />
        : <div className="batch-empty">没有可渲染的 GenUI</div>}
    <div className="expect-side-tokens">
      <div className="expect-line"><span className="expect-key">数据</span>
        <TokenChips items={dataItems} labels={side.labels?.data}
          missing={expected ? missingData : extraData}
          flagClass={expected ? 'is-missing' : 'is-extra'} /></div>
      <div className="expect-line"><span className="expect-key">动作</span>
        <TokenChips items={actionItems} labels={side.labels?.actions}
          missing={expected ? missingActions : extraActions}
          flagClass={expected ? 'is-missing' : 'is-extra'} /></div>
      <div className="expect-line"><span className="expect-key">图标</span>
        <TokenChips items={iconItems} labels={side.labels?.icons}
          missing={expected ? missingIcons : extraIcons}
          flagClass={expected ? 'is-missing' : 'is-extra'} /></div>
    </div>
  </section>;
}

/** 期望卡片附带的筛选结论：尺寸门槛与缺失的需求项，不再计算覆盖率或综合分。 */
function MatchDetail({ pair }: { pair: ExpectPair }) {
  const match = pair.match;
  const missingData = match?.missingData ?? [];
  const missingActions = match?.missingActions ?? [];
  const missingIcons = match?.missingIcons ?? [];
  const missing = [...missingData, ...missingActions, ...missingIcons];
  const extras = [
    ...(pair.diff?.data.extra ?? []),
    ...(pair.diff?.actions.extra ?? []),
    ...(pair.diff?.icons?.extra ?? []),
  ];
  const extraSide = pair.actual ?? pair.expected;
  return <div className="expect-entry-match">
    <p>
      <span className="expect-key">筛选结果</span>
      {' 数据 '}<strong>{missingData.length ? `缺 ${missingData.length}` : '通过'}</strong>
      {' · 动作 '}<strong>{missingActions.length ? `缺 ${missingActions.length}` : '通过'}</strong>
      {' · 图标 '}<strong>{missingIcons.length ? `缺 ${missingIcons.length}` : '通过'}</strong>
    </p>
    {missing.length > 0 && <p className="quality-warning">
      真实输出缺少需求项：{missing.map((token) => labelOf(pair.expected, token)).join('，')}
    </p>}
    {extras.length > 0 && <p className="expect-extra">
      真实输出多出：{extras.map((token) => labelOf(extraSide, token)).join('，')}
    </p>}
  </div>;
}

/**
 * 一个真实输出样本一组。默认折叠成一行摘要：留在卡片区的都是已匹配的配对，
 * 铺满屏幕没有信息量；点开才铺左右对比，需要看渲染时再展开。
 */
function GroupView({ group, expanded, onToggle }:
  { group: ActualGroup; expanded: boolean; onToggle: () => void }) {
  const actual = group.actual;
  const actualExtras = useMemo(() => ({
    data: new Set(group.pairs.flatMap((pair) => pair.diff?.data.extra ?? [])),
    actions: new Set(group.pairs.flatMap((pair) => pair.diff?.actions.extra ?? [])),
    icons: new Set(group.pairs.flatMap((pair) => pair.diff?.icons?.extra ?? [])),
  }), [group.pairs]);
  const none = new Set<string>();
  return <section className="quality-card expect-group">
    <header className="expect-group-head">
      <div>
        <h2>{actual ? `真实输出 · ${actual.title}` : '没有可配对的真实输出'}</h2>
        {actual && <p className="expect-line"><span className="expect-key">Query</span>
          <span className="expect-value">{actual.query || '—'}</span>
          <span className="expect-key">尺寸</span>
          <span className="expect-value">{actual.size || '未确定'}</span></p>}
      </div>
      <span className="expect-group-count">{group.pairs.length
        ? `${group.pairs.length} 个已匹配期望`
        : '没有已匹配的期望'}</span>
      <button type="button" className="expect-group-toggle" aria-expanded={expanded}
        onClick={onToggle}>{expanded ? '收起对比' : '展开对比'}</button>
    </header>
    {expanded && <div className="expect-group-grid">
      <div className="expect-group-expected">
        {group.pairs.length
          ? group.pairs.map((pair) => <article className="expect-entry" key={pair.expected.sampleId}>
            <MatchDetail pair={pair} />
            <SideCard key={`${pair.expected.sampleId}-${pair.expected.attempt}`}
              side={pair.expected} expected
              badge={<span className={`expect-tier is-${pair.tier}`}>
                {TIER_LABEL[pair.tier] ?? pair.tier}
              </span>}
              missingData={new Set(pair.match?.missingData ?? [])}
              missingActions={new Set(pair.match?.missingActions ?? [])}
              missingIcons={new Set(pair.match?.missingIcons ?? [])}
              extraData={none} extraActions={none} extraIcons={none} />
          </article>)
          : <div className="batch-empty expect-group-empty">
            {actual ? '没有已匹配的期望（未匹配的在明细表里）' : '本次没有可配对的真实输出'}
          </div>}
      </div>
      <div className="expect-group-actual">
        {actual
          ? <SideCard key={actual.sampleId} side={actual}
            missingData={none} missingActions={none} missingIcons={none}
            extraData={actualExtras.data} extraActions={actualExtras.actions}
            extraIcons={actualExtras.icons} />
          : <div className="batch-empty expect-none">没有真实输出</div>}
      </div>
    </div>}
  </section>;
}

/**
 * 明细表里的结论：缺了哪些需求项、真实输出多出哪些；没有对应真实输出的直接写明。
 */
function PairVerdict({ pair }: { pair: ExpectPair }) {
  if (!pair.actual) {
    return <span className="expect-empty">没有可比的真实输出</span>;
  }
  const missing = [
    ...(pair.match?.missingData ?? []), ...(pair.match?.missingActions ?? []),
    ...(pair.match?.missingIcons ?? []),
  ];
  const extra = [
    ...(pair.diff?.data.extra ?? []), ...(pair.diff?.actions.extra ?? []),
    ...(pair.diff?.icons?.extra ?? []),
  ];
  return <div className="expect-verdict">
    <div className="expect-line"><span className="expect-key">缺项</span>
      {missing.length
        ? <TokenChips items={missing} labels={allLabels(pair.expected)}
          missing={new Set(missing)} />
        : <span className="expect-empty">需求项全部命中</span>}</div>
    {extra.length > 0 && <div className="expect-line"><span className="expect-key">多出</span>
      <TokenChips items={extra} labels={allLabels(pair.actual)} missing={new Set()} /></div>}
  </div>;
}

export function ExpectCompareRoute() {
  const { calls } = useWorkbench();
  // 上次的选择从持久配置恢复：跳去画廊再回来、切模块或刷新都不用重选。
  const restored = useRef(loadCompareConfig());
  const [runs, setRuns] = useState<BatchRun[]>([]);
  const [actualSource, setActualSource] = useState<'session' | 'batch'>(
    restored.current?.actualSource ?? 'session',
  );
  const [actualRunId, setActualRunId] = useState(restored.current?.actualRunId ?? '');
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(restored.current?.sessionIds ?? []),
  );
  const [dimensions, setDimensions] = useState<Set<DimensionId>>(() => {
    const saved = (restored.current?.dimensions ?? []) as DimensionId[];
    const valid = saved.filter((id) => DIMENSIONS.some((item) => item.id === id));
    return new Set(valid.length ? valid : DIMENSIONS.map((item) => item.id));
  });
  /** 展开的组：默认全折叠，避免几十组卡片一次铺满。 */
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [tier, setTier] = useState(restored.current?.tier ?? 'all');
  const [category, setCategory] = useState(restored.current?.category ?? 'all');
  const [search, setSearch] = useState(restored.current?.search ?? '');
  const [comparison, setComparison] = useState<ExpectComparison | null>(null);
  /** 记忆位：跑出过结果才为 true；「清除记忆」立即置 false，避免被保存 effect 写回。 */
  const [hasResult, setHasResult] = useState(Boolean(restored.current?.hasResult));
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let cancelled = false;
    listBatchRuns()
      .then((items) => { if (!cancelled) setRuns(items); })
      .catch((reason) => { if (!cancelled) setError(String(reason)); });
    return () => { cancelled = true; };
  }, []);
  const expectedRuns = runs.filter(isImportedExpect);
  const expectedTotal = expectedRuns.reduce((total, item) => total + (item.total || 0), 0);
  // 实际侧按完成时间倒序，自动选中与下拉列表都先给最新的一批；
  // 批跑运行与导入的实际输出批次是同一套规则的两个来源，可以并列选择。
  const actualRuns = runs
    .filter((item) => !isImportedExpect(item))
    .sort((left, right) => runTime(right) - runTime(left));
  const importedActualTotal = runs.filter(isImportedActual)
    .reduce((total, item) => total + (item.total || 0), 0);
/** 导入的实际输出批次默认排在批跑运行前：把外部结果导进来就是要用它比。 */
function pickDefaultActualRun(runs: BatchRun[]): string {
  const imported = runs.find(isImportedActual);
  return (imported ?? runs[0])?.runId ?? '';
}

  const artifacts = useMemo(() => sessionArtifacts(calls), [calls]);
  const picked = artifacts.filter((item) => selected.has(item.id));
  // 会话记录只存在本浏览器里，默认来源不能让它一直空着；只在首次加载后自动切一次，之后尊重用户选择。
  // 没有会话记录时优先用最新导入的实际输出批次：导进来就是要用它比，批跑运行作为回退。
  const switchedRef = useRef(false);
  /** 本次进入页面是否已经跑过对比（手动或自动），保证不会重复请求。 */
  const autoRanRef = useRef(false);
  useEffect(() => {
    if (restored.current || switchedRef.current || !runs.length) return;
    switchedRef.current = true;
    if (!artifacts.length && actualRuns.length) {
      setActualSource('batch');
      setActualRunId((current) => current || pickDefaultActualRun(actualRuns));
    }
  }, [runs, artifacts, actualRuns]);
  function toggle(id: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }
  function toggleDimension(id: DimensionId) {
    setDimensions((current) => {
      if (current.has(id) && current.size === 1) return current;
      const next = new Set(current);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }
  async function submit() {
    autoRanRef.current = true;
    setError(''); setBusy(true); setComparison(null);
    try {
      setComparison(actualSource === 'batch'
        ? await compareExpectRun(actualRunId, { dimensions: [...dimensions] })
        : await compareExpectLive(
          null,
          picked.map((item) => ({
            id: item.id, query: item.query, genui: item.genui,
            title: item.title, size: item.size || undefined,
          })),
          { dimensions: [...dimensions] },
        ));
      setTier('all'); setCategory('all'); setSearch('');
      setHasResult(true);
    }
    catch (reason) { setError(String(reason)); }
    finally { setBusy(false); }
  }
  const actualRunMissing = actualSource === 'batch' && Boolean(actualRunId)
    && runs.length > 0 && !actualRuns.some((item) => item.runId === actualRunId);
  useEffect(() => {
    saveCompareConfig({
      actualSource, actualRunId, sessionIds: [...selected], dimensions: [...dimensions],
      tier, category, search, hasResult,
    });
  }, [actualSource, actualRunId, selected, dimensions, tier, category, search, hasResult]);
  // 上次跑出过结果时自动按同一套配置重跑：回到页面就是同一份对比，且口径一定是最新的后端数据。
  useEffect(() => {
    if (!hasResult || autoRanRef.current) return;
    if (!dimensions.size) return;
    if (actualSource === 'batch') {
      if (!runs.length || !actualRunId || actualRunMissing) return;
    } else if (!picked.length) return;
    autoRanRef.current = true;
    void submit();
  }, [actualSource, actualRunId, actualRunMissing, dimensions, picked.length, runs.length,
    hasResult]);
  const groups = useMemo<ActualGroup[]>(() => {
    if (!comparison) return [];
    const grouped = new Map<string, ActualGroup>();
    for (const pair of comparison.pairs) {
      // 只有真正匹配上的期望才归到实际卡片名下；未匹配的另起一区，不占实际卡片的左侧。
      if (!MATCHED_TIERS.has(pair.tier)) continue;
      const key = pair.actual ? `actual:${pair.actual.sampleId}` : 'no-actual';
      const group = grouped.get(key) ?? { key, actual: pair.actual, pairs: [] };
      group.pairs.push(pair);
      grouped.set(key, group);
    }
    for (const actual of comparison.unmatchedActual) {
      const key = `actual:${actual.sampleId}`;
      if (!grouped.has(key)) grouped.set(key, { key, actual, pairs: [] });
    }
    return [...grouped.values()];
  }, [comparison]);
  const keepPair = useCallback((pair: ExpectPair) => {
    if (tier !== 'all' && pair.tier !== tier) return false;
    if (category !== 'all') {
      const value = pair.expected.category || '';
      if (category === '__none__' ? value !== '' : value !== category) return false;
    }
    const query = search.trim().toLowerCase();
    if (!query) return true;
    return [
      pair.expected.sampleId, pair.expected.title, pair.expected.query,
      pair.actual?.sampleId ?? '', pair.actual?.title ?? '', pair.actual?.query ?? '',
    ].join(' ').toLowerCase().includes(query);
  }, [tier, category, search]);
  const filteredGroups = useMemo(() => {
    const query = search.trim().toLowerCase();
    return groups.map((group) => ({
      ...group,
      pairs: group.pairs.filter(keepPair),
    })).filter((group) => {
      if (group.pairs.length) return true;
      const untouched = !tier || tier === 'all';
      return untouched && category === 'all' && !query.trim() && group.actual !== null;
    });
  }, [groups, keepPair, tier, category, search]);
  /** 明细表按同一组筛选条件展示配对结论；未匹配的期望不再渲染卡片。 */
  const filteredPairs = useMemo(
    () => (comparison?.pairs ?? []).filter(keepPair), [comparison, keepPair],
  );
  const unusedActuals = useMemo(
    () => (comparison?.unmatchedActual ?? []).filter((actual) =>
      !search.trim() || [actual.sampleId, actual.title, actual.query]
        .join(' ').toLowerCase().includes(search.trim().toLowerCase())),
    [comparison, search],
  );
  const ready = dimensions.size > 0
    && (actualSource === 'session' ? picked.length > 0 : Boolean(actualRunId));
  const options = comparison?.options;
  const enabled = options?.dimensions ?? [...dimensions];
  const enabledText = enabled.map((id) => {
    const item = DIMENSIONS.find((entry) => entry.id === id);
    return item ? item.label : id;
  }).join(' / ');
  return <div className="quality-page expect-page">
    <header className="batch-center-header">
      <div><h1>期望对比</h1>
        <p>工具跑出来的结果 vs 已导入的期望输出；未匹配的在明细表里看缺项。</p></div>
      <nav className="quality-links" aria-label="期望对比工具">
        <Link to="/expect/import">导入期望输出</Link>
        <Link to="/expect/actual-import">导入实际输出</Link>
        <Link to="/expect/gallery">期望数据画廊</Link>
      </nav>
    </header>
    <section className="quality-card expect-method" aria-label="比对方法">
      <p className="expect-summary-meta">判定口径：启用维度内期望需求项必须被实际指纹全部包含；
        尺寸不进指纹、不参与判定；只在同一条用例内配对。</p>
      <details className="expect-method-details">
        <summary>展开完整口径</summary>
        <h3>期望需求项与实际指纹怎么取</h3>
        <ol className="expect-method-steps">
          <li><strong>取期望需求项</strong>：导入页显式填写的期望数据／期望动作／期望图标优先，
            其次是 CardSpec 指纹，最后回退到导入 DSL 的自动提取；上传截图只作参考图，不参与筛选。</li>
          <li><strong>取实际指纹</strong>：每条真实输出（会话记录、批跑样本或导入的实际输出批次）走同一套提取口径，
            得到数据路径、动作函数（`call:标识`）与图标素材名三份清单。</li>
          <li><strong>按启用维度筛选</strong>：期望侧每一项都要能在实际指纹里找到——数据按路径层级包含、
            动作按同一函数下的标识、图标按素材文件名；缺任意一项即「未匹配」。</li>
          <li><strong>配对与展示</strong>：只在同一条用例内配对——同名样本、相同 Query，或「数据分类＋数据＋动作」强绑定全部成立；ID 只是标识（可留空按内容哈希生成），不作配对依据。
            候选里挑缺失最少的，
            所以多个期望可以落在同一张实际卡片上；结果只给匹配上的配对铺卡片，供需差看明细表。</li>
        </ol>
        <ul className="expect-method-legend">
          {TIER_MEANING.map((item) => <li key={item.id}>
            <span className={`expect-tier is-${item.id}`}>{TIER_LABEL[item.id]}</span>
            <span>{item.text}</span>
          </li>)}
        </ul>
      </details>
    </section>
    <form className="quality-card" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
      {/* 期望侧不挑批次：导入进来多少就比多少，按样本 ID 去重后与工具跑出来的结果配对。 */}
      <div className="quality-card expect-expected-pool">
        <p><span className="expect-key">期望输出</span>
          <span className="expect-value">{expectedRuns.length
            ? `已导入 ${expectedTotal} 条 · ${expectedRuns.length} 个批次（按样本 ID 去重，新批次优先）`
            : '还没有导入'}</span></p>
        {expectedRuns.length
          ? <span className="expect-empty" title={expectedRuns.map((item) => runLabel(item)).join('；')}>
            悬停看批次名</span>
          : <p className="quality-warning">还没有导入期望输出：先去「导入期望输出」上传 DSL（截图与 Query 可选）。</p>}
        {importedActualTotal > 0 && <p className="expect-summary-meta">
          已导入实际输出 {importedActualTotal} 条，可在下方「真实输出来源」里选到
        </p>}
      </div>
      <p className="expect-summary-meta">选择会被记住（跳走再回来自动恢复并重跑）。
        {actualRunMissing && '上次的真实输出批次已不存在，请重新选择来源。'}
        <button type="button" className="expect-forget" onClick={() => {
          clearCompareConfig();
          setActualSource('session'); setActualRunId(''); setSelected(new Set());
          setDimensions(new Set(DIMENSIONS.map((item) => item.id)));
          setTier('all'); setCategory('all'); setSearch(''); setComparison(null);
          setHasResult(false);
        }}>清除记忆</button></p>
      <fieldset className="expect-dimensions">
        <legend>筛选维度</legend>
        {DIMENSIONS.map((item) => <label key={item.id} className="expect-dimension">
          <input type="checkbox" aria-label={item.label}
            checked={dimensions.has(item.id)} onChange={() => toggleDimension(item.id)}
            disabled={dimensions.size === 1 && dimensions.has(item.id)} />
          <span>{item.label}</span>
        </label>)}
        <p className="expect-dimension-note">启用维度内期望项必须全部命中；尺寸不参与判定。</p>
      </fieldset>
      <div className="expect-live">
        <fieldset className="expect-dimensions">
          <legend>真实输出来源</legend>
          <label className="expect-dimension">
            <input type="radio" name="actual-source" checked={actualSource === 'session'}
              onChange={() => setActualSource('session')} />
            <span>本次会话的真实输出</span>
          </label>
          <label className="expect-dimension">
            <input type="radio" name="actual-source" checked={actualSource === 'batch'}
              onChange={() => setActualSource('batch')} />
            <span>已落盘的批跑运行／导入的实际输出</span>
          </label>
          <p className="expect-dimension-note">三种来源同一套规则；会话记录只存在当前浏览器，
            没有时默认切到已落盘的批次。外部产出的结果先用「导入实际输出」按批次导进来。</p>
        </fieldset>
      </div>
      {actualSource === 'batch' && <div className="quality-summary">
        <label className="quality-field">真实输出来源批次
          <select value={actualRunId} onChange={(event) => setActualRunId(event.target.value)}>
            <option value="">请选择批跑运行或导入的实际输出批次</option>
            {actualRuns.map((item) => <option key={item.runId} value={item.runId}>
              {actualRunLabel(item)}</option>)}
          </select></label>
        {!actualRuns.length && <p className="quality-warning">
          还没有可比的实际输出：去「批量测试」跑一次，或先「导入实际输出」。</p>}
      </div>}
      {actualSource === 'session' && <div className="expect-live">
        <div className="expect-live-head">
          <strong>本次会话的真实输出（{picked.length}/{artifacts.length}）</strong>
          <button type="button" onClick={() => setSelected(new Set(artifacts.map((item) => item.id)))}>
            全选
          </button>
          <button type="button" onClick={() => setSelected(new Set())}>清空</button>
        </div>
        {!artifacts.length
          ? <p className="quality-warning">会话里还没有带 DSL 的成功调用：先在左侧「端到端调试」或
            「接口调试」跑一张卡片，或把来源切到批跑运行。</p>
          : <div className="expect-live-list">{artifacts.map((item) => (
            <label key={item.id} className="expect-live-item">
              <input type="checkbox" checked={selected.has(item.id)}
                onChange={() => toggle(item.id)} />
              <span><strong>{item.title}</strong>
                <small>记录 {item.id} · {item.query || '（记录里没有 query）'}
                  {' · '}{item.size || '尺寸待判定'}{' · '}{item.at}</small></span>
            </label>
          ))}</div>}
      </div>}
      {expectedRuns.length > 0 && !ready && <p className="quality-warning">
        还不能比对，还差：{[
          actualSource === 'session'
            ? (picked.length ? '' : '勾选至少一条真实输出')
            : (actualRunId ? '' : '选择实际批跑运行'),
        ].filter(Boolean).join('；')}。
      </p>}
      <button className="batch-create-submit" disabled={busy || !ready}>
        {busy ? '正在匹配…' : '自动匹配并对比'}
      </button>
    </form>
    {error && <div className="batch-error" role="alert">{error}</div>}
    {comparison && <>
      <div className="quality-card"><h2>匹配汇总</h2>
        <p>期望输出来源：{comparison.importName || '已导入的期望输出'} ·
          真实输出来源：{comparison.runName || '本次会话调试记录'} ·
          期望 {comparison.summary.expected} 条 · 实际 {comparison.summary.actual} 条 ·
          已匹配 {comparison.summary.matched} ·
          未匹配 {comparison.summary.none}</p>
        <p className="expect-summary-meta">筛选维度：{enabledText} · 按实际样本分组，
          共 {groups.length} 组</p>
        {comparison.warnings.map((warning, index) => (
          <p className="quality-warning" key={index}>{warning}</p>
        ))}
        {/* 先把"哪条期望配到了哪条实际、结论是什么"列成一张表，再往下看逐条明细。 */}
        <details className="expect-pair-overview" open>
          <summary>配对明细表（{comparison.pairs.length} 对，含未匹配）</summary>
          <div className="quality-table-scroll"><table className="quality-table">
            <thead><tr>
              <th>期望输出样本</th><th>匹配到的真实输出样本</th><th>层级</th><th>结论明细</th>
              <th>尺寸（期望／实际，不影响判定）</th>
            </tr></thead>
            <tbody>
              {filteredPairs.map((pair) => <tr key={`pair:${pair.expected.sampleId}`}>
                <td>{pair.expected.sampleId} · {pair.expected.title}</td>
                <td>{pair.actual
                  ? `${pair.actual.sampleId} · ${pair.actual.title}`
                  : '没有同名样本、无相同 Query，分类＋数据＋动作也未强绑定'}</td>
                <td><span className={`expect-tier is-${pair.tier}`}>
                  {TIER_LABEL[pair.tier] ?? pair.tier}</span></td>
                <td><PairVerdict pair={pair} /></td>
                <td>{`${pair.expected.size || '未确定'} ／ ${pair.actual?.size || '未确定'}`}</td>
              </tr>)}
              {unusedActuals.map((actual) => <tr key={`unused:${actual.sampleId}`}>
                <td>—</td>
                <td>{actual.sampleId} · {actual.title}</td>
                <td><span className="expect-tier is-none">没有期望匹配到它</span></td>
                <td>—</td>
                <td>—</td>
              </tr>)}
            </tbody>
          </table></div>
        </details>
      </div>
      <div className="quality-card expect-filters">
        <label className="quality-field">匹配层级
          <select value={tier} onChange={(event) => setTier(event.target.value)}>
            <option value="all">全部</option>
            {Object.entries(TIER_LABEL).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select></label>
        <label className="quality-field">数据分类
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="all">全部</option>
            {(comparison.categories ?? []).map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
            <option value="__none__">未分类</option>
          </select></label>
        <label className="quality-field">筛选 Query
          <input value={search} placeholder="输入期望或实际的 Query"
            onChange={(event) => setSearch(event.target.value)} /></label>
        <span className="expect-filter-count">显示 {filteredPairs.length} 对配对 · {unusedActuals.length} 条未配对的实际输出</span>
        <button type="button" onClick={() => setExpandedGroups(
          new Set(filteredGroups.map((group) => group.key)))}>全部展开</button>
        <button type="button" onClick={() => setExpandedGroups(new Set())}>全部收起</button>
      </div>
      {filteredGroups.length
        ? filteredGroups.map((group) => <GroupView key={group.key} group={group}
          expanded={expandedGroups.has(group.key)}
          onToggle={() => setExpandedGroups((current) => {
            const next = new Set(current);
            if (next.has(group.key)) next.delete(group.key); else next.add(group.key);
            return next;
          })} />)
        : <div className="quality-card batch-empty">没有符合筛选条件的已匹配配对</div>}
    </>}
  </div>;
}
