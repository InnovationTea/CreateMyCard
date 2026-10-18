import { useEffect, useState } from 'react';
import { useWorkbench } from '../context';
import { endpointHasCredentials, websocketUrl } from '../config';
import { SERVICE_CONFIG_GROUPS, serviceConfigLabel } from '../serviceConfig';
import type { DebugConfig } from '../types';

type TextFieldProps = {
  label: string;
  value: string | number;
  onChange: (value: string) => void;
  help?: string;
  type?: 'text' | 'number';
};

function TextField({ label, value, onChange, help, type = 'text' }: TextFieldProps) {
  return (
    <label className="settings-field">
      <span>{label}</span>
      <input type={type} value={value} onChange={(event) => onChange(event.target.value)} />
      {help && <small>{help}</small>}
    </label>
  );
}

export function SettingsPanel() {
  const { config, updateConfig, resetConfig } = useWorkbench();
  const [draft, setDraft] = useState<DebugConfig>(config);
  const [saved, setSaved] = useState(false);
  const [validationError, setValidationError] = useState('');

  useEffect(() => {
    setDraft(config);
  }, [config]);

  const setValue = <K extends keyof DebugConfig>(key: K, value: DebugConfig[K]) => {
    setDraft((current) => ({ ...current, [key]: value }));
  };

  const save = () => {
    const usesDeployedService = draft.microserviceMode === 'deployed';
    if (usesDeployedService && !draft.toolWsBaseUrl.trim()) {
      setValidationError('微服务地址不能为空。');
      setSaved(false);
      return;
    }
    if (usesDeployedService && endpointHasCredentials(draft.toolWsBaseUrl)) {
      setValidationError('地址不能包含认证信息或 hash；认证信息不会保存。');
      setSaved(false);
      return;
    }
    try {
      // 在保存时就校验协议、相对路径和 HTTPS 混合内容，避免把一个只会在
      // 发起调用时才失败的地址写入共享配置。
      if (usesDeployedService) websocketUrl(draft.toolWsBaseUrl);
    } catch (error) {
      setValidationError(`地址无效：${error instanceof Error ? error.message : String(error)}`);
      setSaved(false);
      return;
    }
    updateConfig(draft);
    setValidationError('');
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1800);
  };

  const reset = () => {
    resetConfig();
    setValidationError('');
    setSaved(false);
  };

  return (
    <section className="settings-page" aria-label="调试配置">
      <div className="settings-heading">
        <div>
          <span className="section-kicker">CONFIGURATION</span>
          <h1>连接与请求配置</h1>
          <p>所有工作区共用以下微服务连接和固定请求参数。配置保存在当前浏览器。</p>
        </div>
        <div className="settings-actions">
          <button type="button" className="settings-reset" onClick={reset}>恢复默认</button>
          <button type="button" className="settings-save" onClick={save}>保存配置</button>
          {saved && <span className="settings-saved" role="status">已保存</span>}
          {validationError && <span className="settings-validation-error" role="alert">{validationError}</span>}
        </div>
      </div>

      <div className="settings-scroll">
        <section className="settings-card">
          <div className="settings-card-heading"><h2>微服务连接</h2><span>选择当前调试使用的微服务来源</span></div>
          <div className="microservice-mode-picker" role="radiogroup" aria-label="调试微服务来源">
            <label className={draft.microserviceMode === 'deployed' ? 'selected' : ''}>
              <input type="radio" name="microservice-mode" checked={draft.microserviceMode === 'deployed'} onChange={() => setValue('microserviceMode', 'deployed')} />
              <span><strong>使用已部署微服务</strong><small>默认选项，使用下方配置的 WebSocket 地址</small></span>
            </label>
            <label className={draft.microserviceMode === 'managed' ? 'selected' : ''}>
              <input type="radio" name="microservice-mode" checked={draft.microserviceMode === 'managed'} onChange={() => setValue('microserviceMode', 'managed')} />
              <span><strong>使用本地受管微服务</strong><small>需先启动，地址由调试平台自动维护</small></span>
            </label>
          </div>
          {draft.microserviceMode === 'deployed' ? <div className="settings-grid">
            <TextField label="微服务 WebSocket Base" value={draft.toolWsBaseUrl} onChange={(value) => setValue('toolWsBaseUrl', value)} help="调用方会在末尾追加三个 operation" />
          </div> : <>
            <div className="settings-subheading"><strong>可选微服务参数</strong><span>批量测试默认继承这些参数</span></div>
            <div className="service-config-groups">{SERVICE_CONFIG_GROUPS.map((group) => <fieldset key={group.title}>
            <legend>{group.title}</legend>
            {group.keys.map((key) => {
              const value = draft.managedServiceConfig[key];
              const update = (next: string | number | boolean) => setValue('managedServiceConfig', {
                ...draft.managedServiceConfig,
                [key]: next,
              });
              return <label key={key}><span>{serviceConfigLabel(key)}</span>{typeof value === 'boolean'
                ? <input type="checkbox" checked={value} onChange={(event) => update(event.target.checked)} />
                : <input type={typeof value === 'number' ? 'number' : 'text'} value={value ?? ''} onChange={(event) => update(typeof value === 'number' ? Number(event.target.value) : event.target.value)} />}</label>;
            })}
            </fieldset>)}</div>
            <p className="secret-note">端口自动分配；密钥只由服务端环境继承，不保存到浏览器。</p>
          </>}
        </section>

        <section className="settings-card">
          <div className="settings-card-heading"><h2>公共请求参数</h2><span>三接口和 Agent 共用</span></div>
          <div className="settings-grid">
            <TextField label="微服务协议版本" value={draft.protocolVersion} onChange={(value) => setValue('protocolVersion', value)} help="仅用于微服务请求包络；Agent 桥接协议固定为 1.0" />
            <TextField label="Bundle Name" value={draft.bundleName} onChange={(value) => setValue('bundleName', value)} />
            <TextField label="User ID" value={draft.userId} onChange={(value) => setValue('userId', value)} />
            <TextField label="Device ID" value={draft.deviceId} onChange={(value) => setValue('deviceId', value)} />
            <TextField label="Phone Type" value={draft.phoneType} onChange={(value) => setValue('phoneType', value)} />
            <TextField label="App Version" value={draft.appVersion} onChange={(value) => setValue('appVersion', value)} />
            <TextField label="ROM Version" value={draft.romVersion} onChange={(value) => setValue('romVersion', value)} />
            <TextField label="Locale" value={draft.locale} onChange={(value) => setValue('locale', value)} />
            <TextField label="Country Code" value={draft.countryCode} onChange={(value) => setValue('countryCode', value)} />
            <TextField label="Device Formation" value={draft.deviceFormation} onChange={(value) => setValue('deviceFormation', value)} />
            <TextField label="Device Type" type="number" value={draft.deviceType} onChange={(value) => setValue('deviceType', Number(value) || 0)} />
            <TextField label="System Version" value={draft.sysVer} onChange={(value) => setValue('sysVer', value)} />
          </div>
        </section>

      </div>
    </section>
  );
}

export default SettingsPanel;
