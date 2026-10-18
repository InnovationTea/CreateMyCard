import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { CardRenderer } from '@widget-debug/card-renderer';
import {
  deleteExpectRun, deleteExpectSample, getExpectGallery,
  updateExpectRunCategory, updateExpectSample,
  type ExpectGallery, type ExpectGalleryItem,
} from '../batchApi';
import { DEFAULT_ASSET_BASE_URL } from '../config';

const SIZE_SOURCE_LABEL: Record<string, string> = {
  declared: '声明', derived: '判定', fallback: '缺省', unknown: '未确定',
};

function cardSize(size: string): 'auto' | '2x2' | '2x4' {
  if (size === '2x2' || size === '2x4') return size;
  return 'auto';
}

/** 筛选词可一次输入多个，以空格分隔；同时匹配原始 token 与中文标签。 */
function matches(search: string, tokens?: string[], labels?: Record<string, string>) {
  const needles = search.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (!needles.length) return true;
  const haystack = [
    ...(tokens ?? []),
    ...Object.keys(labels ?? {}),
    ...Object.values(labels ?? {}),
  ].map((item) => item.toLowerCase());
  return needles.every((needle) => haystack.some((item) => item.includes(needle)));
}

function LabelRow({ kind, tokens, labels }: {
  kind: string; tokens?: string[]; labels?: Record<string, string>;
}) {
  const items = (tokens?.length ? tokens : Object.keys(labels ?? {}))
    .map((token) => [token, labels?.[token] ?? token]);
  return <div className="expect-line"><span className="expect-key">{kind}</span>
    {items.length
      ? <div className="expect-chips">{items.map(([token, label]) => (
        <span key={token} className="expect-chip is-hit"
          title={label === token ? token : `${label} · ${token}`}>{label}</span>
      ))}</div>
      : <span className="expect-empty">未声明</span>}
  </div>;
}

/** 分类下拉里的「新建」哨兵值；选中后由父组件弹输入框。 */
export const NEW_CATEGORY = '__new__';

function GalleryCard({ item, busy, categories, onDelete, onCategory }: {
  item: ExpectGalleryItem;
  busy: boolean;
  categories: string[];
  onDelete: (item: ExpectGalleryItem) => void;
  onCategory: (item: ExpectGalleryItem, next: string) => void;
}) {
  const [showDsl, setShowDsl] = useState(false);
  const [renderDsl, setRenderDsl] = useState(!item.imageUrl);
  const sizeLabel = item.size || '未确定';
  const sizeSource = item.sizeSource
    ? `（${SIZE_SOURCE_LABEL[item.sizeSource] ?? item.sizeSource}）` : '';
  return <article className="quality-card expect-gallery-card">
    <header className="expect-gallery-card-head">
      <div className="expect-card-title">
        <strong>{item.title}</strong>
        {/* 分类就地改：下拉里既有分类，也可以选「＋新建分类…」加自定义分类。 */}
        <label className="expect-gallery-category">分类
          {/* 无障碍名带上样本号：卡片多了以后，光靠「分类」区分不出是哪一张。 */}
          <select aria-label={`图片分类 ${item.sampleId}`}
            value={item.category || ''} disabled={busy}
            onChange={(event) => onCategory(item, event.target.value)}>
            <option value="">未分类</option>
            {categories.map((name) => <option key={name} value={name}>{name}</option>)}
            {item.category && !categories.includes(item.category)
              && <option value={item.category}>{item.category}</option>}
            <option value={NEW_CATEGORY}>＋新建分类…</option>
          </select></label>
      </div>
      <small>{item.sampleId} · {sizeLabel}{sizeSource}</small>
    </header>
    <p className="expect-line"><span className="expect-key">Query</span>
      <span className="expect-value" title={item.query}>{item.query || '—'}</span></p>
    <div className="expect-gallery-preview">
      {renderDsl || !item.imageUrl
        ? <CardRenderer key={`${item.runId}-${item.sampleId}`} initialValue={item.genui}
          assetBaseUrl={DEFAULT_ASSET_BASE_URL} cardSize={cardSize(item.size)}
          previewOnly zoom={110} />
        : <a href={item.imageUrl} target="_blank" rel="noreferrer">
          <img src={item.imageUrl} alt={`${item.sampleId} 上传截图`} />
        </a>}
    </div>
    {item.imageUrl && <label className="expect-toggle">
      <input type="checkbox" checked={renderDsl}
        onChange={(event) => setRenderDsl(event.target.checked)} />
      显示 DSL 渲染（默认上传截图）
    </label>}
    <div className="expect-side-tokens">
      <LabelRow kind="数据" tokens={item.fingerprint?.data} labels={item.labels?.data} />
      <LabelRow kind="动作" tokens={item.fingerprint?.actions} labels={item.labels?.actions} />
      <LabelRow kind="图标" tokens={item.fingerprint?.icons} labels={item.labels?.icons} />
    </div>
    <div className="expect-gallery-actions">
      <button type="button" onClick={() => setShowDsl((value) => !value)}>
        {showDsl ? '收起 DSL' : '查看 DSL'}
      </button>
        {/* 就地修改这一条：保存后不会产生同 ID 的第二条，也不牵动同批其它样本。 */}
        <Link className="expect-gallery-edit"
          to={`/expect/import?runId=${encodeURIComponent(item.runId)}`
            + `&sampleId=${encodeURIComponent(item.sampleId)}`}>编辑</Link>
      <button type="button" className="is-danger" disabled={busy}
        onClick={() => onDelete(item)}>删除样本</button>
    </div>
    {showDsl && <pre className="expect-gallery-dsl">{item.genui}</pre>}
  </article>;
}

export function ExpectGalleryRoute() {
  const [gallery, setGallery] = useState<ExpectGallery | null>(null);
  const [category, setCategory] = useState('');
  const [dataSearch, setDataSearch] = useState('');
  const [actionSearch, setActionSearch] = useState('');
  const [iconSearch, setIconSearch] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  async function load() {
    setError('');
    try {
      setGallery(await getExpectGallery());
    } catch (reason) {
      setError(String(reason));
    }
  }
  useEffect(() => {
    let cancelled = false;
    getExpectGallery()
      .then((value) => { if (!cancelled) setGallery(value); })
      .catch((reason) => { if (!cancelled) setError(String(reason)); });
    return () => { cancelled = true; };
  }, []);
  const filtered = useMemo(() => {
    return (gallery?.items ?? []).filter((item) => {
      if (category && item.category !== category) return false;
      return matches(dataSearch, item.fingerprint?.data, item.labels?.data)
        && matches(actionSearch, item.fingerprint?.actions, item.labels?.actions)
        && matches(iconSearch, item.fingerprint?.icons, item.labels?.icons);
    });
  }, [gallery, category, dataSearch, actionSearch, iconSearch]);
  const groups = useMemo(() => {
    const map = new Map<string, { batchName: string; items: ExpectGalleryItem[] }>();
    for (const item of filtered) {
      const group = map.get(item.runId) ?? { batchName: item.runName, items: [] };
      group.items.push(item);
      map.set(item.runId, group);
    }
    return [...map.entries()];
  }, [filtered]);
  async function removeSample(item: ExpectGalleryItem) {
    if (!window.confirm(`删除期望样本「${item.sampleId}」？此操作不可撤销。`)) return;
    setBusy(`${item.runId}/${item.sampleId}`);
    try {
      await deleteExpectSample(item.runId, item.sampleId);
      await load();
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy('');
    }
  }
  /** 只改分类：后端是局部更新，Query／DSL／期望项与截图都不受影响。 */
  async function changeCategory(item: ExpectGalleryItem, next: string) {
    let value: string | null = next || null;
    if (next === NEW_CATEGORY) {
      const typed = window.prompt('新建分类名称（最多 40 个字符）', '');
      if (typed === null) return;
      const name = typed.trim();
      if (!name) return;
      if (name.length > 40) { setError('分类名不能超过 40 个字符'); return; }
      value = name;
    }
    setBusy(`${item.runId}/${item.sampleId}`);
    try {
      await updateExpectSample(item.runId, item.sampleId, { category: value });
      await load();
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy('');
    }
  }
  /** 整批改分类：跟单张一样支持「＋新建分类…」，只是作用范围是整批。 */
  async function changeBatchCategory(runId: string, name: string, next: string) {
    let value: string | null = next || null;
    if (next === NEW_CATEGORY) {
      const typed = window.prompt(`「${name}」整批新建分类名称（最多 40 个字符）`, '');
      if (typed === null) return;
      const typedName = typed.trim();
      if (!typedName) return;
      if (typedName.length > 40) { setError('分类名不能超过 40 个字符'); return; }
      value = typedName;
    }
    setBusy(`run:${runId}`);
    try {
      await updateExpectRunCategory(runId, value);
      await load();
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy('');
    }
  }
  async function removeBatch(runId: string, name: string) {
    if (!window.confirm(`删除整个期望批次「${name}」及其全部样本？此操作不可撤销。`)) return;
    setBusy(`run:${runId}`);
    try {
      await deleteExpectRun(runId);
      await load();
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy('');
    }
  }
  const total = gallery?.total ?? 0;
  return <div className="quality-page expect-gallery">
    <header className="batch-center-header">
      <div><h1>期望数据画廊</h1>
        <p>集中查看导入的期望卡片：输入数据、动作或图标检索，展开 DSL，删除单个样本或整个批次。
          新增数据从「导入添加」进入，导入后自动回到这里。</p></div>
      <nav className="quality-links" aria-label="期望数据画廊工具">
        <Link to="/expect/gallery/import">导入添加</Link>
        <Link to="/expect">期望对比</Link>
      </nav>
    </header>
    <div className="quality-card expect-gallery-filters">
      <label className="quality-field">数据分类
        <select value={category} onChange={(event) => setCategory(event.target.value)}>
          <option value="">全部</option>
          {(gallery?.categories ?? []).map((item) => (
            <option key={item} value={item}>{item}</option>
          ))}
        </select></label>
      <label className="quality-field">数据
        <input value={dataSearch} placeholder="路径或中文名，空格分隔多项"
          onChange={(event) => setDataSearch(event.target.value)} /></label>
      <label className="quality-field">动作
        <input value={actionSearch} placeholder="handler 或中文名，空格分隔多项"
          onChange={(event) => setActionSearch(event.target.value)} /></label>
      <label className="quality-field">图标
        <input value={iconSearch} placeholder="资源文件名，空格分隔多项"
          onChange={(event) => setIconSearch(event.target.value)} /></label>
      <button type="button" onClick={() => { void load(); }} disabled={Boolean(busy)}>
        刷新
      </button>
      <button type="button" disabled={Boolean(busy)}
        onClick={() => {
          setCategory(''); setDataSearch(''); setActionSearch(''); setIconSearch('');
        }}>
        清空筛选
      </button>
      <span className="expect-filter-count">
        {filtered.length}/{total} 条
      </span>
    </div>
    {error && <div className="batch-error" role="alert">{error}</div>}
    {gallery?.warnings.map((warning, index) => (
      <p className="quality-warning" key={index}>{warning}</p>
    ))}
    {!gallery
      ? <div className="quality-card batch-empty">正在读取期望数据…</div>
      : !total
        ? <div className="quality-card batch-empty">
          还没有导入的期望数据。<Link to="/expect/gallery/import">导入添加</Link>
        </div>
        : !groups.length
          ? <div className="quality-card batch-empty">没有符合筛选条件的期望样本</div>
          : groups.map(([runId, group]) => {
            const meta = gallery.batches.find((item) => item.runId === runId);
            return <section className="expect-gallery-batch" key={runId}>
              <header className="expect-gallery-batch-head">
                <div>
                  <h2>{group.batchName}</h2>
                  <small>{runId}{meta?.category ? ` · ${meta.category}` : ''}
                    {' · '}{group.items.length} 条</small>
                </div>
                <div className="expect-gallery-batch-actions">
                  {/* 整批改分类：界面里这批图片的分类一次改掉，含自定义分类。 */}
                  <label className="expect-gallery-category">整批分类
                    <select aria-label={`整批分类 ${runId}`}
                      value={meta?.category ?? ''} disabled={Boolean(busy)}
                      onChange={(event) => {
                        void changeBatchCategory(runId, group.batchName, event.target.value);
                      }}>
                      <option value="">未分类</option>
                      {(gallery?.categories ?? []).map((name) => (
                        <option key={name} value={name}>{name}</option>))}
                      <option value={NEW_CATEGORY}>＋新建分类…</option>
                    </select></label>
                  <button type="button" className="is-danger"
                    disabled={Boolean(busy)}
                    onClick={() => { void removeBatch(runId, group.batchName); }}>
                    {busy === `run:${runId}` ? '正在删除…' : '删除批次'}
                  </button>
                </div>
              </header>
              <div className="expect-gallery-grid">
                {group.items.map((item) => <GalleryCard key={`${item.runId}/${item.sampleId}`}
                  item={item} busy={Boolean(busy)}
                  categories={gallery?.categories ?? []}
                  onDelete={(value) => { void removeSample(value); }}
                  onCategory={(value, next) => { void changeCategory(value, next); }} />)}
              </div>
            </section>;
          })}
  </div>;
}
