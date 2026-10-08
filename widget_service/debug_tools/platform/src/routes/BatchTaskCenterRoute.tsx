import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  cancelBatchRun,
  deleteBatchTask,
  enqueueBatchTask,
  getBatchScheduler,
  listBatchTasks,
  resumeBatchScheduler,
  type BatchExecution,
  type BatchScheduler,
  type BatchTask,
} from '../batchApi';

const ACTIVE = new Set(['queued', 'preparing', 'running', 'stopping']);

function statusLabel(status: string): string {
  return ({
    queued: '排队中', preparing: '准备后端', running: '运行中', stopping: '停止中',
    completed: '已完成', cancelled: '已停止', failed: '失败', interrupted: '已中断',
  } as Record<string, string>)[status] ?? status;
}

function formatDate(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false });
}

function progressOf(run?: BatchExecution | null): number {
  if (!run?.total) return 0;
  const processed = (run.success ?? 0) + (run.degraded ?? 0) + (run.failed ?? 0);
  return Math.round((Math.min(processed, run.total) / run.total) * 100);
}

function processedOf(run?: BatchExecution | null): number {
  if (!run) return 0;
  return (run.success ?? 0) + (run.degraded ?? 0) + (run.failed ?? 0);
}

export function BatchTaskCenterRoute() {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<BatchTask[]>([]);
  const [scheduler, setScheduler] = useState<BatchScheduler>({ paused: false, queue: [] });
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [backendFilter, setBackendFilter] = useState('all');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');

  const refresh = useCallback(async () => {
    const [taskItems, schedulerState] = await Promise.all([
      listBatchTasks(), getBatchScheduler(),
    ]);
    setTasks(taskItems);
    setScheduler(schedulerState);
  }, []);

  useEffect(() => {
    refresh().catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
    const timer = window.setInterval(() => {
      refresh().catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const visibleTasks = useMemo(() => tasks.filter((task) => {
    const term = search.trim().toLowerCase();
    if (term && !`${task.name} ${task.datasetId}`.toLowerCase().includes(term)) return false;
    const status = task.latestRun?.status ?? 'idle';
    if (statusFilter !== 'all' && status !== statusFilter) return false;
    return backendFilter === 'all' || task.backendMode === backendFilter;
  }), [backendFilter, search, statusFilter, tasks]);

  const runAction = async (key: string, action: () => Promise<unknown>) => {
    setBusy(key);
    setError('');
    try {
      await action();
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy('');
    }
  };

  const deleteTask = (task: BatchTask) => {
    if (!window.confirm(`确认删除任务“${task.name}”吗？该任务的执行记录和本地文件也会被删除。`)) return;
    void runAction(`delete-${task.taskId}`, () => deleteBatchTask(task.taskId));
  };

  const active = scheduler.active;
  const completedCount = tasks.filter((task) => task.latestRun?.status === 'completed').length;
  const stoppedCount = tasks.filter((task) => ['cancelled', 'interrupted'].includes(task.latestRun?.status ?? '')).length;

  return (
    <div className="batch-center-page">
      <header className="batch-center-header">
        <div>
          <h1>批量测试任务</h1>
          <p>创建可重复运行的测试任务；执行完成后，可进入任务选择插件进行后处理。</p>
        </div>
        <Link className="batch-primary-link" to="/batch/new">创建任务</Link>
      </header>
      {error && <div className="batch-error" role="alert">{error}</div>}

      <section className="scheduler-strip" aria-label="调度运行状态">
        <div className="scheduler-summary">
          <strong><span className={`scheduler-dot ${active ? 'running' : scheduler.paused ? 'paused' : ''}`} />调度运行状态</strong>
          <span>{scheduler.paused ? '队列已暂停' : active ? '1 个任务运行中' : '当前空闲'}</span>
        </div>
        <div className="scheduler-metric"><small>排队中</small><b>{scheduler.queue.length}</b></div>
        <div className="scheduler-metric"><small>运行中</small><b>{active ? 1 : 0}</b></div>
        <div className="scheduler-metric"><small>已完成</small><b>{completedCount}</b></div>
        <div className="scheduler-metric"><small>已停止</small><b>{stoppedCount}</b></div>
        <div className="scheduler-queue-preview">
          <strong>任务队列</strong>
          {scheduler.paused && <button type="button" onClick={() => runAction('resume', resumeBatchScheduler)} disabled={busy === 'resume'}>恢复队列</button>}
          {!scheduler.queue.length && <span>暂无等待任务</span>}
          {scheduler.queue.slice(0, 2).map((item) => <span key={item.runId}>#{item.queuePosition} · {tasks.find((task) => task.taskId === item.taskId)?.name ?? item.taskId}</span>)}
        </div>
      </section>

      <section className="batch-task-table-shell">
        <div className="batch-task-toolbar">
          <h2>任务列表</h2>
          <div className="batch-task-filters">
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索任务名称或数据集" />
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="all">全部状态</option><option value="idle">未运行</option><option value="queued">排队中</option>
              <option value="running">运行中</option><option value="completed">已完成</option><option value="failed">失败</option>
            </select>
            <select value={backendFilter} onChange={(event) => setBackendFilter(event.target.value)}>
              <option value="all">全部后端</option><option value="managed">本地受管</option><option value="deployed">已部署</option>
            </select>
            <button type="button" className="batch-refresh" onClick={() => refresh()}>刷新</button>
          </div>
        </div>
        <div className="batch-task-table-scroll">
          <table className="batch-task-table">
            <thead><tr><th>任务名称</th><th>数据集</th><th>样本</th><th>后端模式</th><th>最新状态</th><th>进度 / 统计</th><th>插件</th><th>更新时间</th><th>操作</th></tr></thead>
            <tbody>{visibleTasks.map((task) => {
              const run = task.latestRun;
              const progress = progressOf(run);
              const processed = processedOf(run);
              const isActive = Boolean(run && ACTIVE.has(run.status));
              const executedPlugins = new Map<string, {
                executionId: string;
                name: string;
              }>();
              run?.postprocessExecutions?.forEach((execution) => {
                execution.plugins?.forEach((plugin) => {
                  if (!executedPlugins.has(plugin.id) && plugin.status && plugin.status !== 'queued') {
                    executedPlugins.set(plugin.id, {
                      executionId: execution.executionId,
                      name: plugin.name ?? plugin.id,
                    });
                  }
                });
              });
              return (
                <tr key={task.taskId} className={scheduler.active?.taskId === task.taskId ? 'is-active' : ''} onClick={() => navigate(`/batch/tasks/${task.taskId}`)}>
                  <td><strong>{task.name}</strong><small>{task.runCount} 次执行</small></td>
                  <td>{task.datasetId}</td><td>{task.sampleCount}</td>
                  <td><span className={`backend-tag ${task.backendMode}`}>{task.backendMode === 'managed' ? '本地受管' : '已部署'}</span></td>
                  <td><span className={`batch-run-status ${run?.status ?? 'idle'}`}>{statusLabel(run?.status ?? 'idle')}</span></td>
                  <td><div className="task-progress"><span><i style={{ width: `${progress}%` }} /></span><b>{progress}%</b></div><small>{run ? `${processed}/${run.total ?? task.sampleCount} · 成功 ${run.success ?? 0} · 失败 ${run.failed ?? 0}` : '尚未执行'}</small></td>
                  <td><div className="task-postprocess-actions" onClick={(event) => event.stopPropagation()}>
                    {!executedPlugins.size && <small>尚未执行插件</small>}
                    {Array.from(executedPlugins.entries()).map(([pluginId, plugin]) => <Link
                      key={pluginId}
                      to={`/batch/runs/${encodeURIComponent(run?.runId ?? '')}/postprocess/${encodeURIComponent(plugin.executionId)}/plugins/${encodeURIComponent(pluginId)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >{plugin.name}</Link>)}
                  </div></td>
                  <td>{formatDate(task.updatedAt)}</td>
                  <td><div className="task-row-actions" onClick={(event) => event.stopPropagation()}>
                    <button type="button" disabled={isActive || busy === task.taskId} onClick={() => runAction(task.taskId, () => enqueueBatchTask(task.taskId))}>再次执行</button>
                    {isActive && run && <button type="button" className="danger" onClick={() => runAction(run.runId, () => cancelBatchRun(run.runId))}>停止</button>}
                    <button type="button" className="danger" disabled={isActive || busy === `delete-${task.taskId}`} onClick={() => deleteTask(task)}>删除</button>
                  </div></td>
                </tr>
              );
            })}</tbody>
          </table>
          {!visibleTasks.length && <div className="batch-empty">暂无匹配任务，点击“创建任务”开始配置。</div>}
        </div>
      </section>

    </div>
  );
}
