import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { BatchSampleDetail, getBatchSample } from '../batchApi';
import { TraceViewer } from '../components/TraceViewer';

export function BatchTraceRoute() {
  const { runId = '', sampleId = '' } = useParams();
  const [detail, setDetail] = useState<BatchSampleDetail | null>(null);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let active = true;
    setDetail(null);
    setError('');
    getBatchSample(runId, sampleId)
      .then((result) => { if (active) setDetail(result); })
      .catch((reason) => {
        if (active) setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => { active = false; };
  }, [runId, sampleId, reload]);

  useEffect(() => {
    const previousTitle = document.title;
    document.title = `${sampleId} · Trace 链路`;
    return () => { document.title = previousTitle; };
  }, [sampleId]);

  return (
    <main className="trace-page">
      <header className="trace-page-header">
        <div>
          <h1>{sampleId} · Trace 链路</h1>
          <p>{detail?.summary.title || '单样本链路分析'} · {runId}</p>
        </div>
        <div className="trace-page-actions">
          <button type="button" onClick={() => setReload((value) => value + 1)}>刷新</button>
          <a href="/debug/batch">批量测试</a>
        </div>
      </header>
      {error ? <div className="trace-page-message" role="alert">{error}</div>
        : detail ? <TraceViewer runId={runId} attempts={detail.attempts} />
          : <div className="trace-page-message" role="status">正在加载 Trace…</div>}
    </main>
  );
}
