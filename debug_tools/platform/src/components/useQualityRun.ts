import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getPostprocessExecution, startPostprocess } from '../batchApi';

// 选择页和历史看板共用同一显式提交/轮询流程。
export function useQualityRun(runId: string) {
  const navigate = useNavigate();
  const locked = useRef(false);
  const mounted = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [execution, setExecution] = useState<{ runId: string; executionId: string } | null>(null);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    if (!execution) return;
    const controller = new AbortController();
    let timer: number | undefined;
    const poll = async () => {
      try {
        const current = await getPostprocessExecution(execution.runId, execution.executionId, controller.signal);
        if (controller.signal.aborted) return;
        const plugin = current.plugins?.find((item) => item.id === 'quality-score');
        if (['completed', 'partial'].includes(current.status) && ['success', 'partial'].includes(plugin?.status ?? '')) {
          navigate(`/batch/runs/${encodeURIComponent(execution.runId)}/postprocess/`
            + `${encodeURIComponent(execution.executionId)}/plugins/quality-score`);
          setExecution(null); setBusy(false); locked.current = false;
        } else if (['queued', 'running'].includes(current.status)) {
          setStatus(current.status === 'queued' ? '评分排队中…' : '正在评分…');
          timer = window.setTimeout(poll, 1000);
        } else {
          throw new Error(current.error || plugin?.datasetResult?.summary || `评分执行未完成：${current.status}`);
        }
      } catch (reason) {
        if (controller.signal.aborted) return;
        setError(reason instanceof Error ? reason.message : String(reason));
        setStatus(''); setBusy(false); setExecution(null); locked.current = false;
      }
    };
    void poll();
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [execution, navigate]);

  const start = async (sampleIds: string[]) => {
    if (locked.current || !sampleIds.length) return;
    locked.current = true; setBusy(true); setError(''); setStatus('正在提交评分…');
    try {
      const next = await startPostprocess(runId, ['quality-score'], { 'quality-score': { sampleIds } }, true);
      if (mounted.current) setExecution({ runId, executionId: next.executionId });
    } catch (reason) {
      if (!mounted.current) return;
      setError(reason instanceof Error ? reason.message : String(reason));
      setStatus(''); setBusy(false); locked.current = false;
    }
  };

  return { start, busy, error, status };
}
