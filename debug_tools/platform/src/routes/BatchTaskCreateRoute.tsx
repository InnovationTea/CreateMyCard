import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  createBatchTask,
  getServiceConfigDefaults,
  listBatchDatasetSamples,
  listBatchDatasets,
  type BatchDataset,
  type BatchDatasetItem,
} from '../batchApi';
import { useWorkbench } from '../context';
import type { ServiceConfigDefaults } from '../batchApi';
import { ServiceConfigInput } from '../components/ServiceConfigInput';

export function BatchTaskCreateRoute() {
  const navigate = useNavigate();
  const { config } = useWorkbench();
  const [datasets, setDatasets] = useState<BatchDataset[]>([]);
  const [datasetId, setDatasetId] = useState('');
  const [samples, setSamples] = useState<BatchDatasetItem[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState('');
  const [name, setName] = useState('');
  const [backendMode, setBackendMode] = useState<'deployed' | 'managed'>('deployed');
  const [toolWsBaseUrl, setToolWsBaseUrl] = useState(config.toolWsBaseUrl);
  const [serviceConfig, setServiceConfig] = useState<Record<string, unknown>>({});
  const [defaults, setDefaults] = useState<ServiceConfigDefaults | null>(null);
  const [invalid, setInvalid] = useState<Record<string, boolean>>({});
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    Promise.all([listBatchDatasets(), getServiceConfigDefaults()])
      .then(([items, defaults]) => {
        setDatasets(items);
        if (items.length) setDatasetId(items[0].id);
        setDefaults(defaults);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
  }, []);

  useEffect(() => {
    if (!datasetId) return;
    listBatchDatasetSamples(datasetId)
      .then((items) => {
        setSamples(items);
        setSelected(new Set(items.filter((item) => item.valid).map((item) => item.id)));
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
  }, [datasetId]);

  const visibleSamples = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return samples;
    return samples.filter((item) => `${item.id} ${item.title} ${item.query}`.toLowerCase().includes(term));
  }, [samples, search]);

  const toggleSample = (id: string) => setSelected((current) => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  const submit = async () => {
    setSaving(true);
    setError('');
    try {
      if (backendMode === 'managed' && (!defaults || Object.values(invalid).some(Boolean))) throw new Error('请等待配置加载并修正无效参数');
      const created = await createBatchTask({
        name, datasetId, sampleIds: Array.from(selected), requestOverrides: {},
        backendMode, toolWsBaseUrl,
        serviceConfig: backendMode === 'managed' ? serviceConfig : {},
      });
      navigate(`/batch/tasks/${created.taskId}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
      setSaving(false);
    }
  };

  return (
    <div className="batch-create-page">
      <header className="batch-create-header">
        <div><button type="button" onClick={() => navigate('/batch')}>← 返回任务中心</button><h1>创建批量测试任务</h1><p>任务创建后自动加入执行队列；需要调整时可重新创建任务。</p></div>
        <button type="button" className="batch-create-submit" disabled={saving || !selected.size || !datasetId} onClick={submit}>{saving ? '正在创建并排队…' : '创建并执行'}</button>
      </header>
      {error && <div className="batch-error" role="alert">{error}</div>}
      <div className="batch-create-layout">
        <main className="batch-create-main">
          <section className="batch-form-section">
            <div className="batch-form-heading"><div><h2>基本信息</h2><p>选择一个数据集，并为任务保留可识别名称。</p></div></div>
            <div className="batch-form-grid three">
              <label><span>任务名称</span><input value={name} onChange={(event) => setName(event.target.value)} placeholder={`${datasetId || '数据集'} · 自动生成名称`} /></label>
              <label><span>数据集</span><select value={datasetId} onChange={(event) => setDatasetId(event.target.value)}>{datasets.map((item) => <option key={item.id} value={item.id}>{item.name}（{item.validSampleCount}/{item.sampleCount}）</option>)}</select></label>
            </div>
          </section>

          <section className="batch-form-section sample-picker-section">
            <div className="batch-form-heading"><div><h2>选择样本</h2><p>无效样本保留展示但不能选择。</p></div><span>{selected.size}/{samples.filter((item) => item.valid).length}</span></div>
            <div className="sample-picker-toolbar"><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索编号、标题或需求" /><button type="button" onClick={() => setSelected(new Set(samples.filter((item) => item.valid).map((item) => item.id)))}>全选</button><button type="button" onClick={() => setSelected(new Set())}>清空</button></div>
            <div className="sample-picker-list">{visibleSamples.map((item) => <label key={item.id} className={!item.valid ? 'invalid' : ''}><input type="checkbox" disabled={!item.valid} checked={selected.has(item.id)} onChange={() => toggleSample(item.id)} /><span><strong>{item.id} · {item.title}</strong><small>{item.size || '未知尺寸'} · {item.query || item.error}</small></span></label>)}</div>
          </section>

          <section className="batch-form-section">
            <div className="batch-form-heading"><div><h2>测试后端</h2><p>选择已部署服务，或调整会影响模型表现和性能的参数后启动本地微服务。</p></div></div>
            <div className="backend-mode-switch"><button type="button" className={backendMode === 'deployed' ? 'active' : ''} onClick={() => setBackendMode('deployed')}>已部署后端</button><button type="button" className={backendMode === 'managed' ? 'active' : ''} onClick={() => setBackendMode('managed')}>本地受管后端</button></div>
            {backendMode === 'deployed' ? <label className="wide-field"><span>WebSocket Base URL</span><input value={toolWsBaseUrl} onChange={(event) => setToolWsBaseUrl(event.target.value)} /></label> : <div className="managed-config-grid">{defaults?.fields.filter((field) => field.group === 'exposed' && field.editable && !field.sensitive).map((field) => <div className="managed-config-field" key={field.name}>
              <div className="managed-config-label"><strong>{field.displayName}</strong><small>{field.name in serviceConfig ? '本次临时覆盖' : field.source}</small></div>
              <ServiceConfigInput field={field} value={field.name in serviceConfig ? serviceConfig[field.name] : defaults.values[field.name]} onChange={(value) => setServiceConfig((current) => {
                const next = { ...current };
                if (JSON.stringify(value) === JSON.stringify(defaults.values[field.name])) delete next[field.name];
                else next[field.name] = value;
                return next;
              })} onValidity={(valid) => setInvalid((current) => ({ ...current, [field.name]: !valid }))} />
              {field.name in serviceConfig && <button type="button" onClick={() => { setInvalid((current) => ({ ...current, [field.name]: false })); setServiceConfig((current) => { const next = { ...current }; delete next[field.name]; return next; }); }}>取消临时覆盖</button>}
            </div>)}</div>}

            <p className="secret-note">本次参数只对该受管后端版本生效且优先级最高；端口自动分配，其余默认值来自连接配置和 debug_tool.yaml。</p>
          </section>
        </main>
        <aside className="batch-create-summary"><h2>任务摘要</h2><dl><div><dt>数据集</dt><dd>{datasetId || '未选择'}</dd></div><div><dt>样本</dt><dd>{selected.size} 个</dd></div><div><dt>后端</dt><dd>{backendMode === 'managed' ? '本地受管' : '已部署'}</dd></div></dl><p>创建后立即加入后台队列；执行完成后可进入任务选择插件进行后处理。</p></aside>
      </div>
    </div>
  );
}
