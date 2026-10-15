import { useEffect, useState } from 'react';
import { CardRenderer } from '@widget-debug/card-renderer';
import {
  DeviceApiError, deviceRequest, terminal,
  type Check, type DeviceRun, type Emulator, type EnvironmentStatus, type Operation, type Target,
} from '../deviceApi';
import { DEFAULT_ASSET_BASE_URL } from '../config';
import './device-render.css';

const STORAGE = 'ai-widget-device-editor:v1';
const LAST_RUN = 'ai-widget-device-run:v1';
type Editor = { source: string; size: '2x2' | '2x4' };

function restore(): Editor {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE) ?? '{}');
    return {
      source: typeof value.source === 'string' ? value.source : '',
      size: value.size === '2x4' ? '2x4' : '2x2',
    };
  } catch {
    return { source: '', size: '2x2' };
  }
}

export function DeviceRenderRoute() {
  const [editor, setEditor] = useState(restore);
  const [targets, setTargets] = useState<Target[]>([]);
  const [emulators, setEmulators] = useState<Emulator[]>([]);
  const [checks, setChecks] = useState<Check[]>([]);
  const [statusItems, setStatusItems] = useState<EnvironmentStatus[]>([]);
  const [selected, setSelected] = useState('');
  const [converted, setConverted] = useState('');
  const [convertMessage, setConvertMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [operation, setOperation] = useState<Operation | null>(null);
  const [run, setRun] = useState<DeviceRun | null>(null);
  const [logs, setLogs] = useState('');
  const [paused, setPaused] = useState(false);
  const [screenImage, setScreenImage] = useState('');
  const [screenStatus, setScreenStatus] = useState('请选择设备');
  const [connection, setConnection] = useState(0);
  const [runVersion, setRunVersion] = useState(0);

  async function refresh(preferredTargetId = '') {
    const [devices, environment] = await Promise.all([
      deviceRequest<{ targets: Target[]; emulators: Emulator[] }>('/targets'),
      deviceRequest<{ checks: Check[]; status: EnvironmentStatus[] }>('/environment'),
    ]);
    setTargets(devices.targets);
    setEmulators(devices.emulators);
    setChecks(environment.checks);
    setStatusItems(environment.status);
    setSelected((current) => {
      if (devices.targets.some((target) => target.id === current)) return current;
      return devices.targets.some((target) => target.id === preferredTargetId) ? preferredTargetId : '';
    });
  }

  async function action(callback: () => Promise<void>) {
    setBusy(true); setError('');
    try { await callback(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }

  useEffect(() => { void action(refresh); }, []);
  useEffect(() => { localStorage.setItem(STORAGE, JSON.stringify(editor)); }, [editor]);

  useEffect(() => {
    if (!operation || operation.status !== 'running') return;
    let stopped = false;
    let timer = 0;
    const poll = async () => {
      try {
        const value = await deviceRequest<Operation>(`/operations/${operation.id}`);
        if (stopped) return;
        setOperation(value);
        if (value.status === 'running') {
          timer = window.setTimeout(poll, 800);
        } else if (value.status === 'success') {
          await refresh(value.targetId ?? '');
        } else {
          setError(value.message);
        }
      } catch (reason) {
        if (!stopped) setError(reason instanceof Error ? reason.message : String(reason));
      }
    };
    timer = window.setTimeout(poll, 800);
    return () => { stopped = true; window.clearTimeout(timer); };
  }, [operation?.id, operation?.status]);

  useEffect(() => {
    if (!editor.source.trim()) { setConverted(''); setConvertMessage(''); return; }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      deviceRequest<{ text: string }>('/convert', {
        source: editor.source, format: 'auto', size: editor.size,
      }, { signal: controller.signal }).then((value) => {
        setConverted(value.text); setConvertMessage('已自动识别并转换'); setError('');
      }).catch((reason) => {
        if (reason?.name !== 'AbortError') {
          setConverted('');
          setConvertMessage('');
          setError(reason instanceof Error ? reason.message : String(reason));
        }
      });
    }, 400);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [editor]);

  useEffect(() => {
    if (!selected || paused) { setScreenStatus(selected ? '屏幕已暂停' : '请选择设备'); return; }
    const url = new URL(`/debug/device/targets/${encodeURIComponent(selected)}/screen`, window.location.href);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(url);
    socket.binaryType = 'blob';
    socket.onopen = () => setScreenStatus('设备屏幕已连接');
    socket.onmessage = (event) => {
      if (typeof event.data === 'string') {
        const value = JSON.parse(event.data);
        setScreenStatus(value.status === 'error' ? value.message : '设备屏幕实时画面');
        return;
      }
      const next = URL.createObjectURL(event.data);
      setScreenImage((current) => { if (current) URL.revokeObjectURL(current); return next; });
    };
    socket.onerror = () => setScreenStatus('屏幕连接失败');
    socket.onclose = () => setScreenStatus('屏幕连接已断开');
    return () => socket.close();
  }, [selected, paused, connection]);

  useEffect(() => () => { if (screenImage) URL.revokeObjectURL(screenImage); }, [screenImage]);

  useEffect(() => {
    const id = run?.id ?? localStorage.getItem(LAST_RUN);
    if (!id) return;
    let stopped = false;
    const poll = async () => {
      try {
        const value = await deviceRequest<DeviceRun>(`/runs/${id}`);
        if (stopped) return;
        setRun(value);
        const output = await deviceRequest<{ text: string }>(`/runs/${id}/logs?offset=0`);
        setLogs(output.text);
        if (!terminal.has(value.status)) window.setTimeout(poll, 900);
      } catch (reason) {
        if (reason instanceof DeviceApiError && reason.status === 404) localStorage.removeItem(LAST_RUN);
      }
    };
    void poll();
    return () => { stopped = true; };
  }, [run?.id, runVersion]);

  async function deploy() {
    if (!selected || !converted) return;
    const value = await deviceRequest<DeviceRun>('/runs', {
      targetId: selected, source: converted, format: 'a2ui', size: editor.size,
    });
    localStorage.setItem(LAST_RUN, value.id);
    setRun(value); setRunVersion((current) => current + 1);
  }

  async function startEmulator(id: string) {
    const value = await deviceRequest<Operation>(`/emulators/${id}/start`, {});
    setOperation(value);
    if (value.status === 'success') await refresh(value.targetId ?? '');
  }

  return <div className="device-workspace">
    <header className="device-header"><div><h2>设备渲染</h2><p>内置 A2UI_Render、动态推送与自动裁切</p></div>
      <button disabled={busy} onClick={() => void action(refresh)}>刷新设备与环境</button></header>
    {error && <div className="device-error" role="alert">{error}</div>}
    <aside className="device-status-widget" aria-label="设备环境状态"><div className="backend-status-items">{statusItems.map((item) => <div key={item.id}
      className={`backend-status-item ${item.ok ? 'available' : 'unavailable'}`}><i aria-hidden="true" /><span>{item.label}</span>
      <b>{item.ok ? '可用' : '不可用'}</b></div>)}</div>
      <details><summary>查看检查明细</summary>{checks.map((check) => <div key={check.name}>
        <strong>{check.ok ? '✓' : '！'} {check.name}</strong> · {check.detail}</div>)}</details></aside>
    <section className="device-profile-bar"><label>在线设备 <select aria-label="在线设备" value={selected}
      onChange={(event) => setSelected(event.target.value)}><option value="">请选择在线设备</option>
      {targets.map((target) => <option key={target.id} value={target.id}>
        {target.name} · {target.serial} · {target.kind}</option>)}</select></label>
      {emulators.map((emulator) => <button key={emulator.id} disabled={!emulator.ready || busy}
        onClick={() => void action(() => startEmulator(emulator.id))}>启动 {emulator.name}</button>)}
      {operation && <span>{operation.message}{operation.serial ? ` · ${operation.serial}` : ''}</span>}</section>
    <div className="device-columns">
      <section className="device-editor"><div className="device-toolbar"><strong>输入与部署</strong>
        <select aria-label="卡片尺寸" value={editor.size} onChange={(event) => setEditor((value) => ({
          ...value, size: event.target.value as '2x2' | '2x4',
        }))}><option value="2x2">2x2</option><option value="2x4">2x4</option></select></div>
        <textarea aria-label="A2UI 代码" value={editor.source} onChange={(event) => setEditor((value) => ({
          ...value, source: event.target.value,
        }))} placeholder="粘贴 A2UI JSON/JSONL 或 Compact DSL" />
        <div className="device-actions"><span>{convertMessage}</span><button disabled={!selected || !converted || busy}
          onClick={() => void action(deploy)}>编译并运行</button></div>
        <details><summary>实际写入工程的 A2UI</summary><pre>{converted}</pre></details></section>
      <section className="device-browser-preview"><div className="device-toolbar"><strong>浏览器预览</strong>
        <small>与设备部署使用同一转换结果</small></div><CardRenderer key={`${editor.size}:${converted}`}
          initialValue={converted} assetBaseUrl={DEFAULT_ASSET_BASE_URL} cardSize={editor.size}
          previewOnly zoom={160} /></section>
      <section className="device-preview"><div className="device-toolbar"><strong>{screenStatus}</strong><div>
        <button disabled={!selected} onClick={() => setPaused(!paused)}>{paused ? '恢复' : '暂停'}</button>
        <button disabled={!selected} onClick={() => setConnection((value) => value + 1)}>重新连接</button></div></div>
        <div className="device-screen">{screenImage ? <img src={screenImage} alt="设备当前屏幕" />
          : <p>选择在线设备后显示全屏画面</p>}</div></section>
    </div>
    {run && <section className="device-task"><div className="device-toolbar"><strong>
      任务 · {run.device} · {run.stage}</strong>{!terminal.has(run.status) && <button onClick={() => void action(async () => {
        setRun(await deviceRequest<DeviceRun>(`/runs/${run.id}/cancel`, {}));
      })}>取消任务</button>}</div>
      {run.error && <p role="alert">{run.error}</p>}
      {run.cropPx && <p>App 自动裁切：{run.cropPx.left}, {run.cropPx.top} · {run.cropPx.width} × {run.cropPx.height}px</p>}
      {run.warnings?.map((warning) => <p key={warning}>警告：{warning}</p>)}
      {run.cardImageUrl && <div className="device-result-images"><figure><img src={run.cardImageUrl}
        alt="本次运行的卡片截图" /><figcaption>卡片截图</figcaption></figure>
        {run.fullImageUrl && <figure><img src={run.fullImageUrl} alt="本次运行的设备全屏截图" />
          <figcaption>全屏原图</figcaption></figure>}</div>}
      {logs && <details><summary>运行日志</summary><pre>{logs}</pre></details>}</section>}
  </div>;
}
