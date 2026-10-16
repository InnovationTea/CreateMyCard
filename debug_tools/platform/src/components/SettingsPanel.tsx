import { useEffect, useState } from 'react';
import { getServiceConfigDefaults, saveServiceConfigDefaults, type ServiceConfigDefaults } from '../batchApi';
import { useWorkbench } from '../context';
import { endpointHasCredentials, websocketUrl } from '../config';
import { ServiceConfigInput } from './ServiceConfigInput';
import { BackendStatusWidget } from './BackendStatusWidget';
import { ToolchainStatusWidget } from './ToolchainStatusWidget';

export function SettingsPanel() {
  const { config, updateConfig } = useWorkbench();
  const [draft, setDraft] = useState(config);
  const [defaults, setDefaults] = useState<ServiceConfigDefaults | null>(null);
  const [changes, setChanges] = useState<Record<string, unknown>>({});
  const [invalid, setInvalid] = useState<Record<string, boolean>>({});
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => { setDraft(config); }, [config]);
  useEffect(() => {
    let active = true;
    setBusy(true);
    getServiceConfigDefaults().then((result) => {
      if (!active) return;
      setDefaults(result);
      setChanges({});
      setInvalid({});
      setError('');
    }).catch((reason) => { if (active) setError(String(reason)); })
      .finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [reloadKey]);

  const save = async () => {
    setSaved(false);
    setError('');
    setBusy(true);
    try {
      if (draft.microserviceMode === 'deployed') {
        if (!draft.toolWsBaseUrl.trim()) throw new Error('微服务地址不能为空');
        if (endpointHasCredentials(draft.toolWsBaseUrl)) throw new Error('地址不能包含认证信息或 hash');
        websocketUrl(draft.toolWsBaseUrl);
      } else {
        if (!defaults) throw new Error('配置尚未加载');
        if (Object.values(invalid).some(Boolean)) throw new Error('请先修正无效配置');
        const result = await saveServiceConfigDefaults(defaults.version, changes);
        setDefaults(result);
        setChanges({});
      }
      updateConfig({ ...draft, managedServiceConfig: {} });
      setSaved(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  };

  const update = (name: string, value: unknown) => {
    setSaved(false);
    setChanges((current) => {
      const next = { ...current };
      if (JSON.stringify(value) === JSON.stringify(defaults?.values[name])) delete next[name];
      else next[name] = value;
      return next;
    });
  };

  return <section className="settings-page" aria-label="调试配置">
    <div className="settings-heading">
      <div><span className="section-kicker">CONFIGURATION</span><h1>连接与请求配置</h1><p>受管微服务默认参数保存在服务器 debug_tool.yaml，连接偏好保存在当前浏览器。</p></div>
      <div className="settings-actions">
        <button type="button" className="settings-reset" disabled={busy} onClick={() => { setDraft(config); setSaved(false); setReloadKey((key) => key + 1); }}>重新加载已保存配置</button>
        <button type="button" className="settings-save" disabled={busy || Object.values(invalid).some(Boolean)} onClick={save}>{busy ? '处理中…' : '保存配置'}</button>
        {saved && <span role="status">已保存；受管参数在下次启动或任务执行时生效</span>}
        {error && <span className="settings-validation-error" role="alert">{error}</span>}
      </div>
    </div>
    <div className="settings-scroll">
      {defaults?.localConfigExists === false && <section className="settings-card" aria-label="首次使用配置说明">
        <div className="settings-card-heading"><h2>使用前请创建本机配置</h2></div>
        <p role="alert">未找到本机 debug_tool.yaml，平台已使用默认配置启动；设备渲染和截图暂不可用，模型调用仍需有效配置。</p>
        <p>将 <code>debug_tools/debug_tool.yaml.example</code> 复制为 <code>debug_tools/debug_tool.yaml</code>，按模板注释填写本机路径和模型配置后重启。已有配置请勿覆盖。</p>
        <p>实际配置仅保存在本机，不提交 Git；示例中的空凭据和路径需要按实际环境填写。</p>
      </section>}
      <BackendStatusWidget allowManagedStart refreshIntervalMs={10_000} className="settings-toolchain-status" />
      <ToolchainStatusWidget />
      <section className="settings-card">
        <div className="settings-card-heading"><h2>微服务连接</h2><span>选择当前调试使用的微服务来源</span></div>
        <div className="microservice-mode-picker" role="radiogroup" aria-label="调试微服务来源">
          {(['deployed', 'managed'] as const).map((mode) => <label key={mode} className={draft.microserviceMode === mode ? 'selected' : ''}>
            <input type="radio" name="microservice-mode" checked={draft.microserviceMode === mode} onChange={() => { setSaved(false); setDraft({ ...draft, microserviceMode: mode }); }} />
            <span><strong>{mode === 'managed' ? '使用本地受管微服务' : '使用已部署微服务'}</strong></span>
          </label>)}
        </div>
        {draft.microserviceMode === 'deployed' && <div className="settings-grid"><label><span>微服务 WebSocket Base</span><input value={draft.toolWsBaseUrl} onChange={(event) => { setSaved(false); setDraft({ ...draft, toolWsBaseUrl: event.target.value }); }} /></label></div>}
      </section>
      {draft.microserviceMode === 'managed' && (['exposed', 'defaults'] as const).map((group) => <section className="settings-card" key={group}>
        <div className="settings-card-heading"><h2>{group === 'exposed' ? '批跑可临时调整的默认参数' : '其余受管微服务默认参数'}</h2><span>{group === 'exposed' ? '由 widget_backend.exposed 定义' : '批跑每次开始执行时使用当前默认值'}</span></div>
        <fieldset disabled={busy} className="managed-config-grid">{defaults?.fields.filter((field) => field.group === group).map((field) => <div className="managed-config-field" key={`${reloadKey}-${field.name}`}>
          <div className="managed-config-label"><strong title={field.displayName}>{field.displayName}</strong><small title={`${field.source}${field.name in changes ? ' · 待保存至 debug_tool.yaml' : ''}`}>{field.source}{field.name in changes ? ' · 待保存' : ''}</small></div>
          <ServiceConfigInput field={field} value={field.name in changes ? changes[field.name] : defaults.values[field.name]} onChange={(value) => update(field.name, value)} onValidity={(valid) => setInvalid((current) => ({ ...current, [field.name]: !valid }))} />
        </div>)}</fieldset>
      </section>)}
    </div>
  </section>;
}

export default SettingsPanel;
