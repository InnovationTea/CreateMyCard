import { useEffect, useState } from 'react';
import { TraceArtifact, batchTraceArtifactUrl, getBatchTraceArtifact } from '../batchApi';

type LoadedContent = { content: string; mediaType: string };
const cache = new Map<string, LoadedContent>();
const AUTO_LOAD_LIMIT = 256 * 1024;

function ContentBody({ value, name }: { value: LoadedContent; name: string }) {
  if (value.content === '') return <p className="trace-empty-content">内容已加载：空文本（0 字节）</p>;
  let formatted = value.content;
  if (value.mediaType.includes('json')) {
    try {
      const parsed = JSON.parse(value.content);
      if (Array.isArray(parsed) && name.includes('messages')) {
        return <div className="trace-messages">{parsed.map((message, index) => (
          <article key={index}><strong>{String(message.role ?? 'message')}</strong>
            <pre>{typeof message.content === 'string' ? message.content : JSON.stringify(message.content, null, 2)}</pre>
          </article>
        ))}</div>;
      }
      formatted = JSON.stringify(parsed, null, 2);
    } catch { /* 非法 JSON 仍展示原始完整文本。 */ }
  }
  return <pre>{formatted}</pre>;
}

export function TraceContent({ artifact, runId, source, autoLoad = false }: {
  artifact: TraceArtifact; runId: string; source: string; autoLoad?: boolean;
}) {
  const [state, setState] = useState<'idle' | 'loading' | 'loaded' | 'error'>('idle');
  const [value, setValue] = useState<LoadedContent | null>(null);
  const [error, setError] = useState('');
  const [request, setRequest] = useState(0);
  const [copyError, setCopyError] = useState('');
  const key = `${runId}:${artifact.sha256}`;

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setValue(null);
    setError('');
    setCopyError('');
    const cached = cache.get(key);
    if (cached && new TextEncoder().encode(cached.content).byteLength === artifact.bytes) {
      setValue(cached);
      setState('loaded');
    } else if (artifact.available && (request > 0 || (autoLoad && artifact.bytes <= AUTO_LOAD_LIMIT))) {
      setState('loading');
      getBatchTraceArtifact(runId, artifact.sha256, artifact.bytes, controller.signal)
        .then((loaded) => {
          if (!active) return;
          cache.set(key, loaded);
          setValue(loaded);
          setState('loaded');
        })
        .catch((reason) => {
          if (!active) return;
          setError(reason instanceof Error ? reason.message : String(reason));
          setState('error');
        });
    } else {
      setState('idle');
    }
    return () => { active = false; controller.abort(); };
  }, [key, request, artifact.bytes, artifact.available, autoLoad]);

  return <article className="trace-artifact">
    <header><strong>{artifact.label || artifact.name}</strong>
      <small>来源：{source} · {artifact.mediaType} · {artifact.bytes.toLocaleString()} B</small></header>
    {!artifact.available && <p role="alert" className="trace-local-error">{artifact.error || '附件不可用'}</p>}
    {artifact.available && state === 'idle' && <button onClick={() => setRequest((n) => n + 1)}>加载完整内容</button>}
    {state === 'loading' && <p role="status">正在加载并校验内容…</p>}
    {state === 'error' && <div role="alert" className="trace-local-error">{error}
      <button onClick={() => setRequest((n) => n + 1)}>重试加载</button></div>}
    {state === 'loaded' && value && <>
      <div className="trace-artifact-actions">
        <button onClick={() => navigator.clipboard.writeText(value.content).catch(() => setCopyError('复制失败，请手动选择文本'))}>复制</button>
        <a href={batchTraceArtifactUrl(runId, artifact.sha256)} download={artifact.name}>下载</a>
        <span>已通过大小与 SHA-256 校验</span>
      </div>
      {copyError && <p role="alert">{copyError}</p>}
      <ContentBody value={value} name={artifact.name} />
    </>}
  </article>;
}
