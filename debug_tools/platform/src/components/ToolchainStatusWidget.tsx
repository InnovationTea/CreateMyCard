import { useEffect, useState } from 'react';
import { getDeviceEnvironment, type Check } from '../deviceApi';

const TOOL_NAMES = ['Node', 'HDC', 'Hvigor', 'JBR', 'SDK'];

export function ToolchainStatusWidget() {
  const [checks, setChecks] = useState<Check[]>([]);
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    const refresh = async () => {
      setChecking(true);
      try {
        const result = await getDeviceEnvironment();
        if (!active) return;
        setChecks(result.checks.filter((item) => TOOL_NAMES.includes(item.name)));
        setError('');
      } catch (reason) {
        if (!active) return;
        setChecks([]);
        setError(reason instanceof Error ? reason.message : String(reason));
      } finally {
        if (active) setChecking(false);
      }
    };
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, 20_000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  const items = checks.length > 0
    ? checks
    : TOOL_NAMES.map((name) => ({ name, ok: false, detail: error || '等待检查' }));

  return <aside className="backend-status-widget settings-toolchain-status" aria-label="本机工具链状态">
    <div className="backend-status-heading">
      <strong>本机工具链</strong>
      <small>{checking ? '检查中' : '每 20 秒自动检查'}</small>
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
  </aside>;
}

export default ToolchainStatusWidget;
