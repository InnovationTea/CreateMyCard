import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  listPostprocessPlugins,
  startPostprocess,
  type PostprocessExecution,
  type PostprocessPlugin,
  type PostprocessPluginResult,
} from '../batchApi';
import { deviceRequest, type Emulator, type Operation, type Target } from '../deviceApi';

function executionStatusLabel(status: string): string {
  return ({
    waiting: '等待任务完成', queued: '排队中', running: '执行中',
    completed: '已完成', success: '成功', partial: '部分完成', failed: '失败',
    skipped: '已跳过', interrupted: '已中断',
    replaced: '已被新配置替换',
  } as Record<string, string>)[status] ?? status;
}

export function PostprocessPanel({ runId, runStatus, selectedSampleId, executions, onStarted }: {
  runId: string;
  runStatus: string;
  selectedSampleId: string;
  executions: PostprocessExecution[];
  onStarted: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [plugins, setPlugins] = useState<PostprocessPlugin[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [configs, setConfigs] = useState<Record<string, Record<string, unknown>>>({});
  const [busy, setBusy] = useState(false);
  const [rerunningPluginIds, setRerunningPluginIds] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [deviceTargets, setDeviceTargets] = useState<Target[]>([]);
  const [deviceEmulators, setDeviceEmulators] = useState<Emulator[]>([]);
  const [deviceOperation, setDeviceOperation] = useState<Operation | null>(null);

  const refreshDeviceTargets = async (preferredTargetId = '') => {
    const value = await deviceRequest<{ targets: Target[]; emulators: Emulator[] }>('/targets');
    setDeviceTargets(value.targets);
    setDeviceEmulators(value.emulators);
    if (preferredTargetId && value.targets.some((target) => target.id === preferredTargetId)) {
      setConfigs((current) => ({
        ...current,
        'device-capture': { ...current['device-capture'], targetId: preferredTargetId },
      }));
    }
  };

  useEffect(() => {
    listPostprocessPlugins().then((items) => {
      setPlugins(items);
      const defaults: Record<string, Record<string, unknown>> = {};
      items.forEach((item) => {
        const properties = item.configSchema.properties as Record<string, Record<string, unknown>> | undefined;
        defaults[item.id] = {};
        Object.entries(properties ?? {}).forEach(([name, schema]) => {
          if (schema.default !== undefined) defaults[item.id][name] = schema.default;
        });
      });
      setConfigs(defaults);
    }).catch((reason) => setError(String(reason)));
  }, []);
  useEffect(() => {
    if (!open) return;
    refreshDeviceTargets().catch(() => {
      setDeviceTargets([]);
      setDeviceEmulators([]);
    });
  }, [open]);
  useEffect(() => {
    if (!open || !deviceOperation || deviceOperation.status !== 'running') return;
    let stopped = false;
    let timer = 0;
    const poll = async () => {
      try {
        const value = await deviceRequest<Operation>(`/operations/${deviceOperation.id}`);
        if (stopped) return;
        setDeviceOperation(value);
        if (value.status === 'running') {
          timer = window.setTimeout(poll, 800);
        } else if (value.status === 'success') {
          await refreshDeviceTargets(value.targetId ?? '');
        } else {
          setError(value.message);
        }
      } catch (reason) {
        if (!stopped) setError(reason instanceof Error ? reason.message : String(reason));
      }
    };
    timer = window.setTimeout(poll, 800);
    return () => { stopped = true; window.clearTimeout(timer); };
  }, [open, deviceOperation?.id, deviceOperation?.status]);

  const waitingExecution = executions.find((item) => item.status === 'waiting');
  const active = executions.some((item) => ['queued', 'running'].includes(item.status));
  const activePluginIds = useMemo(() => {
    const ids = new Set<string>();
    executions.forEach((execution) => {
      if (!['queued', 'running'].includes(execution.status)) return;
      execution.plugins.forEach((plugin) => {
        if (!plugin.status || ['queued', 'running'].includes(plugin.status)) ids.add(plugin.id);
      });
    });
    return ids;
  }, [executions]);
  const activeCount = executions.reduce((count, execution) => count + (
    ['queued', 'running'].includes(execution.status) ? execution.plugins.length : 0
  ), 0);
  const pluginById = useMemo(() => new Map(plugins.map((plugin) => [plugin.id, plugin])), [plugins]);
  const historyByPlugin = useMemo(() => {
    const histories = new Map<string, Array<{
      execution: PostprocessExecution;
      result: PostprocessPluginResult;
    }>>();
    executions.forEach((execution) => {
      execution.plugins?.forEach((result) => {
        if (!result.status || result.status === 'queued') return;
        const history = histories.get(result.id) ?? [];
        history.push({ execution, result });
        histories.set(result.id, history);
      });
    });
    return histories;
  }, [executions]);
  const latestByPlugin = useMemo(() => {
    const latest = new Map<string, {
      execution: PostprocessExecution;
      result: PostprocessPluginResult;
    }>();
    executions.forEach((execution) => {
      execution.plugins?.forEach((result) => {
        if (!latest.has(result.id)) latest.set(result.id, { execution, result });
      });
    });
    return latest;
  }, [executions]);
  const displayedPluginIds = Array.from(latestByPlugin.keys());
  const newSelected = selected.filter((pluginId) => pluginId !== 'quality-score'
    && !historyByPlugin.has(pluginId) && !activePluginIds.has(pluginId));

  useEffect(() => {
    if (!waitingExecution) return;
    setSelected(waitingExecution.plugins.map((plugin) => plugin.id));
    setConfigs((current) => {
      const next = { ...current };
      waitingExecution.plugins.forEach((plugin) => {
        next[plugin.id] = plugin.config ?? {};
      });
      return next;
    });
  }, [waitingExecution?.executionId]);

  const dependenciesOf = (pluginId: string): string[] => {
    const result: string[] = [];
    const visiting = new Set<string>();
    const visit = (currentId: string) => {
      if (visiting.has(currentId)) return;
      visiting.add(currentId);
      (pluginById.get(currentId)?.dependence ?? []).forEach((dependencyId) => {
        if (result.includes(dependencyId)) return;
        visit(dependencyId);
        result.push(dependencyId);
      });
      visiting.delete(currentId);
    };
    visit(pluginId);
    return result;
  };

  const togglePlugin = (pluginId: string) => setSelected((current) => {
    if (!current.includes(pluginId)) {
      const next = [...current];
      [...dependenciesOf(pluginId), pluginId].forEach((id) => {
        if (!next.includes(id)) next.push(id);
      });
      return next;
    }
    const removed = new Set([pluginId]);
    let changed = true;
    while (changed) {
      changed = false;
      plugins.forEach((plugin) => {
        const blocked = plugin.dependence?.some((dependencyId) => removed.has(dependencyId));
        if (current.includes(plugin.id) && blocked && !removed.has(plugin.id)) {
          removed.add(plugin.id);
          changed = true;
        }
      });
    }
    return current.filter((id) => !removed.has(id));
  });

  const run = async () => {
    setBusy(true); setError('');
    try {
      await startPostprocess(runId, newSelected, configs);
      await onStarted();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  };

  const rerun = async (pluginId: string) => {
    if (activePluginIds.has(pluginId) || rerunningPluginIds.includes(pluginId)) return;
    setRerunningPluginIds((current) => [...current, pluginId]); setError('');
    try {
      await startPostprocess(runId, [pluginId], configs, true);
      await onStarted();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setRerunningPluginIds((current) => current.filter((id) => id !== pluginId));
    }
  };

  const startEmulator = async (emulatorId: string) => {
    setError('');
    try {
      const value = await deviceRequest<Operation>(`/emulators/${emulatorId}/start`, {});
      setDeviceOperation(value);
      if (value.status === 'success') await refreshDeviceTargets(value.targetId ?? '');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  };

  return <>
    <button type="button" className="postprocess-launch" onClick={() => setOpen(true)}>
      后处理插件{active ? ` · ${activeCount} 个执行中` : historyByPlugin.size ? ` · ${historyByPlugin.size}` : ''}
    </button>
    {open && <div className="postprocess-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setOpen(false); }}>
      <section className="postprocess-dialog" role="dialog" aria-modal="true" aria-label="后处理插件">
        <header className="postprocess-dialog-header"><div><h2>后处理插件</h2><p>可继续提交或重跑其他插件；独立任务并行执行，依赖或结果读写冲突时等待。</p></div><button type="button" aria-label="关闭后处理插件" onClick={() => setOpen(false)}>×</button></header>
        {error && <div className="batch-error" role="alert">{error}</div>}
        <div className="postprocess-unified-view">
          <section className="postprocess-plugin-grid" aria-label="可选后处理插件">
            {plugins.map((plugin) => {
              if (plugin.id === 'quality-score') return <Link key={plugin.id} className="postprocess-plugin-card"
                to={`/quality?runId=${encodeURIComponent(runId)}`}>
                <span><b>{plugin.name}</b><small>选择已完成批次和样本，确认后手动运行评分 ›</small></span>
              </Link>;
              const checked = selected.includes(plugin.id);
              const dependencies = plugin.dependence ?? [];
              return <label key={plugin.id} className={checked ? 'postprocess-plugin-card is-selected' : 'postprocess-plugin-card'}>
                <input
                  type="checkbox"
                  aria-label={plugin.name}
                  checked={checked}
                  onChange={() => togglePlugin(plugin.id)}
                />
                <span><b>{plugin.name}</b><small>{plugin.description ?? plugin.id}</small>
                  {dependencies.length > 0 && <em>依赖：{dependencies.map((id) => pluginById.get(id)?.name ?? id).join(' → ')}</em>}
                  {plugin.id === 'device-capture' && checked && <span className="postprocess-device-profile">
                    {deviceTargets.length ? <select aria-label="真机截图在线设备"
                      value={String(configs[plugin.id]?.targetId ?? '')}
                      onClick={(event) => event.stopPropagation()}
                      onChange={(event) => {
                        event.stopPropagation();
                        setConfigs((current) => ({
                          ...current,
                          [plugin.id]: { ...current[plugin.id], targetId: event.target.value },
                        }));
                      }}>
                      <option value="">请选择在线设备</option>
                      {deviceTargets.map((target) => <option key={target.id} value={target.id}>
                        {target.name} · {target.kind}
                      </option>)}
                    </select> : <small>当前没有在线设备</small>}
                    {deviceEmulators.map((emulator) => <button type="button" key={emulator.id}
                      disabled={!emulator.ready || deviceOperation?.status === 'running'}
                      onClick={(event) => { event.stopPropagation(); void startEmulator(emulator.id); }}>
                      启动本地模拟器 · {emulator.name}
                    </button>)}
                    {deviceOperation && <small>{deviceOperation.message}</small>}
                    {!deviceTargets.length && <Link to="/device-render"
                      onClick={(event) => event.stopPropagation()}>打开设备渲染 ›</Link>}
                  </span>}
                </span>
              </label>;
            })}
          </section>
          <footer className="postprocess-dialog-actions"><span>{newSelected.length ? active ? `将按依赖执行 ${newSelected.length} 个新增插件` : `将并行执行 ${newSelected.length} 个新增插件` : selected.length ? '已选插件均已提交或已运行，可单独再次运行' : '尚未选择插件'}</span><button type="button" disabled={busy || !newSelected.length || (newSelected.includes('device-capture') && !configs['device-capture']?.targetId)} onClick={run}>{busy ? '正在提交…' : waitingExecution ? '更新自动执行配置' : runStatus === 'completed' ? active ? '继续运行后处理' : '开始后处理' : '完成后自动执行'}</button></footer>
          <section className="postprocess-inline-results">
            <header><strong>执行结果</strong><small>自动展示运行中插件与每个插件的最新一次结果</small></header>
            {!displayedPluginIds.length && <div className="batch-empty">尚无后处理执行记录</div>}
            {displayedPluginIds.map((pluginId) => {
              const plugin = pluginById.get(pluginId);
              const latest = latestByPlugin.get(pluginId);
              const progress = latest?.result.progress;
              const isActiveResult = activePluginIds.has(pluginId);
              const canOpenDashboard = latest?.execution.status !== 'waiting';
              return <article key={pluginId}><div><strong>{plugin?.name ?? pluginId}</strong>
                {!latest && <small>尚未执行</small>}
                {latest && <small>{progress?.message
                  ?? latest.result.datasetResult?.summary
                  ?? `${latest.result.sampleCount ?? 0} 个样本`} · {latest.execution.createdAt}</small>}
                {progress && <div className="postprocess-inline-progress"><i style={{ width: `${progress.total
                  ? Math.round(progress.completed * 100 / progress.total) : 0}%` }} /></div>}
                {latest?.result.error && <em className="postprocess-result-error">{latest.result.error}</em>}
              </div>{latest && <><span className={`batch-status ${latest.result.status ?? latest.execution.status}`}>{executionStatusLabel(latest.result.status ?? latest.execution.status)}</span><div className="postprocess-result-actions">{pluginId !== 'quality-score' && !isActiveResult && <button type="button" disabled={rerunningPluginIds.includes(pluginId)} onClick={() => rerun(pluginId)}>{rerunningPluginIds.includes(pluginId) ? '提交中…' : '再次运行'}</button>}{canOpenDashboard && <Link
                to={`/batch/runs/${encodeURIComponent(runId)}/postprocess/${encodeURIComponent(latest.execution.executionId)}/plugins/${encodeURIComponent(pluginId)}`}
                target="_blank"
                rel="noopener noreferrer"
              >打开看板 ›</Link>}</div></>}</article>;
            })}
          </section>
        </div>
      </section>
    </div>}
  </>;
}
