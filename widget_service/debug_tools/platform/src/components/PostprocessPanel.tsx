import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  listPostprocessPlugins,
  startPostprocess,
  type PostprocessExecution,
  type PostprocessPlugin,
  type PostprocessPluginResult,
} from '../batchApi';

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
  const [rerunningPluginId, setRerunningPluginId] = useState('');
  const [error, setError] = useState('');

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

  const waitingExecution = executions.find((item) => item.status === 'waiting');
  const active = executions.some((item) => ['queued', 'running'].includes(item.status));
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
  const newSelected = selected.filter((pluginId) => !historyByPlugin.has(pluginId));

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
    setRerunningPluginId(pluginId); setError('');
    try {
      await startPostprocess(runId, [pluginId], configs, true);
      await onStarted();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setRerunningPluginId('');
    }
  };

  return <>
    <button type="button" className="postprocess-launch" onClick={() => setOpen(true)}>
      后处理插件{active ? ' · 执行中' : historyByPlugin.size ? ` · ${historyByPlugin.size}` : ''}
    </button>
    {open && <div className="postprocess-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setOpen(false); }}>
      <section className="postprocess-dialog" role="dialog" aria-modal="true" aria-label="后处理插件">
        <header className="postprocess-dialog-header"><div><h2>后处理插件</h2><p>勾选插件后并行执行；依赖插件会自动加入，并在所需结果就绪后运行。</p></div><button type="button" aria-label="关闭后处理插件" onClick={() => setOpen(false)}>×</button></header>
        {error && <div className="batch-error" role="alert">{error}</div>}
        <div className="postprocess-unified-view">
          <section className="postprocess-plugin-grid" aria-label="可选后处理插件">
            {plugins.map((plugin) => {
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
                </span>
              </label>;
            })}
          </section>
          <footer className="postprocess-dialog-actions"><span>{newSelected.length ? `将并行执行 ${newSelected.length} 个新增插件` : selected.length ? '已选插件均已运行，可单独再次运行' : '尚未选择插件'}</span><button type="button" disabled={busy || active || !newSelected.length} onClick={run}>{busy ? '正在提交…' : active ? '后处理正在执行' : waitingExecution ? '更新自动执行配置' : runStatus === 'completed' ? '开始后处理' : '完成后自动执行'}</button></footer>
          <section className="postprocess-inline-results">
            <header><strong>执行结果</strong><small>展示每个已选插件的最新一次结果</small></header>
            {!selected.length && <div className="batch-empty">勾选插件后在这里查看执行结果</div>}
            {selected.map((pluginId) => {
              const plugin = pluginById.get(pluginId);
              const latest = (historyByPlugin.get(pluginId) ?? [])[0];
              return <article key={pluginId}><div><strong>{plugin?.name ?? pluginId}</strong>
                {!latest && <small>尚未执行</small>}
                {latest && <small>{latest.result.datasetResult?.summary ?? `${latest.result.sampleCount ?? 0} 个样本`} · {latest.execution.createdAt}</small>}
              </div>{latest && <><span className={`batch-status ${latest.result.status ?? latest.execution.status}`}>{executionStatusLabel(latest.result.status ?? latest.execution.status)}</span><div className="postprocess-result-actions"><button type="button" disabled={active || Boolean(rerunningPluginId)} onClick={() => rerun(pluginId)}>{rerunningPluginId === pluginId ? '提交中…' : '再次运行'}</button><Link
                to={`/batch/runs/${encodeURIComponent(runId)}/postprocess/${encodeURIComponent(latest.execution.executionId)}/plugins/${encodeURIComponent(pluginId)}`}
                target="_blank"
                rel="noopener noreferrer"
              >打开看板 ›</Link></div></>}</article>;
            })}
          </section>
        </div>
      </section>
    </div>}
  </>;
}
