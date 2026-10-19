import { useEffect, useState } from 'react';
import { getDeviceEnvironment, type Check, type EnvironmentStatus } from '../deviceApi';

const TOOL_NAMES = ['Node', 'HDC', 'Hvigor', 'JBR', 'SDK'];

export function ToolchainStatusWidget() {
  const [checks, setChecks] = useState<Check[]>([]);
  const [deviceStatus, setDeviceStatus] = useState<EnvironmentStatus[]>([]);
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    let pending = false;
    const controller = new AbortController();
    const refresh = async () => {
      if (pending) return;
      pending = true;
      setChecking(true);
      try {
        const result = await getDeviceEnvironment(controller.signal);
        if (!active) return;
        setChecks(result.checks.filter((item) => TOOL_NAMES.includes(item.name)));
        setDeviceStatus(result.status.filter((item) => item.id !== 'toolchain'));
        setError('');
      } catch (reason) {
        if (!active) return;
        setChecks([]);
        setDeviceStatus([]);
        setError(reason instanceof Error ? reason.message : String(reason));
      } finally {
        pending = false;
        if (active) setChecking(false);
      }
    };
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, 10_000);
    return () => {
      active = false;
      controller.abort();
      window.clearInterval(timer);
    };
  }, []);

  const items = checks.length > 0
    ? checks
    : TOOL_NAMES.map((name) => ({ name, ok: false, detail: error || '等待检查' }));

  return <><aside className="backend-status-widget settings-toolchain-status" aria-label="本机工具链状态">
    <div className="backend-status-heading">
      <strong>本机工具链</strong>
      <small>{checking ? '检查中' : '每 10 秒自动检查'}</small>
    </div>
    <div className="backend-status-items">
      {items.map((item) => {
        const state = checking ? 'unknown' : item.ok ? 'available' : 'unavailable';
        const text = checking ? '检查中' : item.ok ? '可用' : '不可用';
        return <div className={`backend-status-item ${state}`} key={item.name} title={item.detail}>
          <i aria-hidden="true" /><span>{item.name}</span><b>{text}</b>
        </div>;
      })}
    </div>
  </aside>
  <aside className="backend-status-widget settings-toolchain-status" aria-label="设备环境状态">
    <div className="backend-status-heading"><strong>设备环境</strong>
      <small>{checking ? '检查中' : '每 10 秒自动检查'}</small></div>
    <div className="backend-status-items">
      {(deviceStatus.length ? deviceStatus : [{ id: 'environment', label: '设备环境', ok: false, detail: error || '等待检查' }]).map((item) => {
        const state = checking ? 'unknown' : item.ok ? 'available' : 'unavailable';
        return <div className={`backend-status-item ${state}`} key={item.id} title={item.detail}>
          <i aria-hidden="true" /><span>{item.label}</span><b>{checking ? '检查中' : item.ok ? '可用' : '不可用'}</b>
        </div>;
      })}
    </div>
  </aside></>;
}

export default ToolchainStatusWidget;
