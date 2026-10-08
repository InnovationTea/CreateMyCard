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
import { SERVICE_CONFIG_GROUPS, serviceConfigLabel } from '../serviceConfig';

const REQUEST_FIELDS = [
  ['protocolVersion', '协议版本'], ['bundleName', 'Bundle Name'], ['deviceId', 'Device ID'],
  ['phoneType', 'Phone Type'], ['appVersion', 'App Version'], ['romVersion', 'ROM Version'],
  ['locale', 'Locale'], ['countryCode', 'Country Code'], ['deviceFormation', 'Device Formation'],
  ['deviceType', 'Device Type'], ['sysVer', 'System Version'],
] as const;

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
  const [serviceConfig, setServiceConfig] = useState<Record<string, string | number | boolean>>(
    { ...config.managedServiceConfig },
  );
  const [serviceSources, setServiceSources] = useState<Record<string, string>>({});
  const [enabledOverrides, setEnabledOverrides] = useState<Set<string>>(new Set());
  const [overrideValues, setOverrideValues] = useState<Record<string, string | number>>(() => {
    const values: Record<string, string | number> = {};
    REQUEST_FIELDS.forEach(([key]) => { values[key] = config[key]; });
    return values;
  });
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    Promise.all([listBatchDatasets(), getServiceConfigDefaults()])
      .then(([items, defaults]) => {
        setDatasets(items);
        if (items.length) setDatasetId(items[0].id);
        setServiceConfig((current) => ({ ...defaults.values, ...current }));
        setServiceSources(defaults.sources);
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

  const toggleOverride = (key: string) => setEnabledOverrides((current) => {
    const next = new Set(current);
    if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  });

  const submit = async () => {
    setSaving(true);
    setError('');
    try {
      const requestOverrides: Record<string, unknown> = {};
      enabledOverrides.forEach((key) => { requestOverrides[key] = overrideValues[key]; });
      const created = await createBatchTask({
        name, datasetId, sampleIds: Array.from(selected), requestOverrides,
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
            <div className="batch-form-heading"><div><h2>公共请求字段覆盖</h2><p>默认保留样本原值；勾选后才会覆盖所有选中样本。系统生成的 UID 与会话字段不可覆盖。</p></div><button type="button" onClick={() => setEnabledOverrides(new Set(REQUEST_FIELDS.map(([key]) => key)))}>使用工作台配置</button></div>
            <div className="override-grid">{REQUEST_FIELDS.map(([key, label]) => <label key={key} className={enabledOverrides.has(key) ? 'enabled' : ''}><input type="checkbox" checked={enabledOverrides.has(key)} onChange={() => toggleOverride(key)} /><span>{label}</span><input disabled={!enabledOverrides.has(key)} type={typeof overrideValues[key] === 'number' ? 'number' : 'text'} value={overrideValues[key] ?? ''} onChange={(event) => setOverrideValues((current) => ({ ...current, [key]: typeof current[key] === 'number' ? Number(event.target.value) : event.target.value }))} /></label>)}</div>
          </section>

          <section className="batch-form-section">
            <div className="batch-form-heading"><div><h2>测试后端</h2><p>选择已部署服务，或调整会影响模型表现和性能的参数后启动本地微服务。</p></div></div>
            <div className="backend-mode-switch"><button type="button" className={backendMode === 'deployed' ? 'active' : ''} onClick={() => setBackendMode('deployed')}>已部署后端</button><button type="button" className={backendMode === 'managed' ? 'active' : ''} onClick={() => setBackendMode('managed')}>本地受管后端</button></div>
            {backendMode === 'deployed' ? <label className="wide-field"><span>WebSocket Base URL</span><input value={toolWsBaseUrl} onChange={(event) => setToolWsBaseUrl(event.target.value)} /></label> : <div className="service-config-groups">{SERVICE_CONFIG_GROUPS.map((group) => <fieldset key={group.title}><legend>{group.title}</legend>{group.keys.map((key) => { const value = serviceConfig[key]; return <label key={key}><span>{serviceConfigLabel(key)}<small>{serviceSources[key] ?? '连接配置'}</small></span>{typeof value === 'boolean' ? <input type="checkbox" checked={value} onChange={(event) => setServiceConfig((current) => ({ ...current, [key]: event.target.checked }))} /> : <input type={typeof value === 'number' ? 'number' : 'text'} value={value ?? ''} onChange={(event) => setServiceConfig((current) => ({ ...current, [key]: typeof value === 'number' ? Number(event.target.value) : event.target.value }))} />}</label>; })}</fieldset>)}</div>}
            <p className="secret-note">端口由系统自动分配；并发、超时、Trace 与产物设置复用 debug_agent.yaml。API Key、Access Key 和 Secret 仅由后端进程继承 `.env`。</p>
          </section>
        </main>
        <aside className="batch-create-summary"><h2>任务摘要</h2><dl><div><dt>数据集</dt><dd>{datasetId || '未选择'}</dd></div><div><dt>样本</dt><dd>{selected.size} 个</dd></div><div><dt>后端</dt><dd>{backendMode === 'managed' ? '本地受管' : '已部署'}</dd></div><div><dt>字段覆盖</dt><dd>{enabledOverrides.size} 项</dd></div></dl><p>创建后立即加入后台队列；执行完成后可进入任务选择插件进行后处理。</p></aside>
      </div>
    </div>
  );
}
