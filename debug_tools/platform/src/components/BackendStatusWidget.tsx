import { useCallback, useEffect, useState } from 'react';
import { getConnectionAvailability, startManagedService, type ConnectionAvailability } from '../batchApi';
import { useWorkbench } from '../context';

type ServiceStatus = {
  available?: boolean;
  detail: string;
};

const INITIAL_STATUS: ConnectionAvailability = {
  mainAgent: { available: false, detail: '等待检查' },
  deployedService: { available: false, detail: '等待检查' },
  managedService: { available: false, detail: '等待检查' },
};

export function stateClass(status: ServiceStatus, checking: boolean): string {
  if (checking || status.detail === '等待检查') return 'unknown';
  return status.available ? 'available' : 'unavailable';
}

export function useBackendAvailability() {
  const { config, updateConfig } = useWorkbench();
  const [status, setStatus] = useState<ConnectionAvailability>(INITIAL_STATUS);
  const [checking, setChecking] = useState(true);
  const [starting, setStarting] = useState(false);

  const refresh = useCallback(async () => {
    setChecking(true);
    try {
      setStatus(await getConnectionAvailability(config.toolWsBaseUrl));
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      setStatus({
        mainAgent: { available: false, detail },
        deployedService: { available: false, detail },
        managedService: { available: false, detail },
      });
    } finally {
      setChecking(false);
    }
  }, [config.toolWsBaseUrl]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, 20_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const startManaged = async () => {
    setStarting(true);
    try {
      const next = await startManagedService(config.managedServiceConfig);
      setStatus(next);
      const endpoint = next.managedService.endpoint;
      if (endpoint) updateConfig({ managedServiceWsUrl: endpoint });
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      setStatus((current) => ({
        ...current,
        managedService: { available: false, detail },
      }));
    } finally {
      setStarting(false);
      setChecking(false);
    }
  };

  return { checking, refresh, startManaged, starting, status };
}

export function SelectedMicroserviceStatus() {
  const { config } = useWorkbench();
  const { checking, status } = useBackendAvailability();
  const selected = config.microserviceMode === 'managed'
    ? status.managedService
    : status.deployedService;
  const label = config.microserviceMode === 'managed' ? '本地受管微服务' : '已部署微服务';
  const state = stateClass(selected, checking);
  const text = state === 'unknown' ? '检查中' : selected.available ? '可用' : '不可用';
  return <span className={`selected-service-status ${state}`} title={selected.detail}>
    <i aria-hidden="true" /><span>{label}</span><b>{text}</b>
  </span>;
}

export function BackendStatusWidget({ allowManagedStart = false }: { allowManagedStart?: boolean }) {
  const { checking, startManaged, starting, status } = useBackendAvailability();

  const items: Array<[string, ServiceStatus]> = [
    ['Main Agent', status.mainAgent],
    ['已部署微服务', status.deployedService],
    ['本地受管微服务', status.managedService],
  ];

  return (
    <aside className="backend-status-widget" aria-label="后端服务状态">
      <div className="backend-status-heading">
        <strong>后端服务</strong>
        <small>{checking ? '检查中' : '每 20 秒自动检查'}</small>
      </div>
      <div className="backend-status-items">
        {items.map(([label, item]) => {
          const state = stateClass(item, checking);
          const text = state === 'unknown' ? '检查中' : item.available ? '可用' : '不可用';
          return <div className={`backend-status-item ${state}`} key={label} title={item.detail}>
            <i aria-hidden="true" /><span>{label}</span><b>{text}</b>
          </div>;
        })}
      </div>
      {allowManagedStart && <button type="button" onClick={startManaged} disabled={starting}>
        {starting ? '正在启动…' : '启动本地受管微服务'}
      </button>}
    </aside>
  );
}
