import { useEffect, useMemo, useState } from 'react';
import { ArtifactPreview, type ArtifactRecord } from '@widget-debug/end-to-end';
import { CardRenderer, resolveCardSize } from '@widget-debug/card-renderer';
import { parseLegacyToolResponse, parsePythonRepr } from '@widget-debug/interface';
import { useWorkbench } from '../context';
import { DEFAULT_ASSET_BASE_URL } from '../config';

const COMPACT_DSL_OPERATION = 'generateWidgetCardCompactDsl';
const ARTIFACT_KINDS: Array<[string, string]> = [
  ['genui', 'GenUI DSL'],
  ['cardSpec', 'CardSpec'],
  ['taskSpec', 'TaskSpec'],
  ['effectiveCapabilities', '有效能力'],
  ['removedCapabilities', '移除能力'],
  ['generationPlan', '生成计划'],
  ['meta', 'Meta'],
  ['designToken', 'Design Token'],
];

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function artifactReference(value: unknown): string | undefined {
  if (typeof value === 'string') return value.trim() || undefined;
  const reference = recordValue(value);
  for (const key of ['artifactUrl', 'artifact_url', 'artifact_reference', 'artifactReference', 'url', 'path']) {
    const candidate = reference[key];
    if (typeof candidate === 'string' && candidate.trim()) return candidate.trim();
  }
  return undefined;
}

function artifactFromValue(value: unknown, runId?: string): ArtifactRecord | null {
  if (typeof value === 'string') {
    const parsed = parseLegacyToolResponse(value) ?? parsePythonRepr(value);
    if (parsed !== null && parsed !== value) return artifactFromValue(parsed, runId);
  }
  const root = recordValue(value);
  const nested = recordValue(root.data);
  const response = recordValue(root.response);
  const nestedData = recordValue(nested.data);
  const payload = { ...root, ...response, ...nested, ...nestedData };
  const artifactUrl = artifactReference(
    payload.artifactUrl
      ?? payload.artifact_url
      ?? payload.artifact_reference
      ?? payload.artifactReference,
  );
  const hasArtifact = payload.genui !== undefined
    || payload.cardSpec !== undefined
    || artifactUrl !== undefined
    || payload.taskSpec !== undefined;
  if (!hasArtifact) return null;
  return {
    ...payload,
    runId: typeof payload.runId === 'string' ? payload.runId : runId ?? 'renderer',
    artifactUrl,
    genui: typeof payload.genui === 'string' ? payload.genui : undefined,
  };
}

function renderableValue(value: unknown): string | undefined {
  if (typeof value === 'string') return value;
  const record = recordValue(value);
  const nestedResponse = recordValue(record.response);
  const nested = recordValue(record.data);
  const responseData = recordValue(nestedResponse.data);
  const payload = { ...record, ...nestedResponse, ...nested, ...responseData };
  if (typeof payload.genui === 'string') return payload.genui;
  if (typeof payload.dsl === 'string') return payload.dsl;
  if (typeof payload.compactDsl === 'string') return payload.compactDsl;
  if (payload.cardSpec !== undefined) return JSON.stringify(payload.cardSpec, null, 2);
  return undefined;
}

function finalFrameSource(frame: Record<string, unknown> | undefined): string | undefined {
  if (!frame) return undefined;
  const reply = recordValue(frame.reply);
  const streamInfo = recordValue(reply.streamInfo);
  const streamContent = typeof streamInfo.streamContent === 'string'
    ? streamInfo.streamContent
    : frame.streamContent;
  if (typeof streamContent === 'string' && streamContent.trim()) {
    const parsed = parseLegacyToolResponse(streamContent) ?? parsePythonRepr(streamContent);
    return renderableValue(parsed) ?? streamContent;
  }
  return renderableValue(frame) ?? renderableValue(frame.data)
    ?? (frame.data == null ? undefined : JSON.stringify(frame.data, null, 2));
}

function jsonText(value: unknown): string {
  if (typeof value === 'string') return value;
  try { return JSON.stringify(value, null, 2) ?? ''; } catch { return String(value); }
}

export function RendererRoute() {
  const { artifact, calls, selectedCallId, pushEvent, setArtifact } = useWorkbench();
  const selectedCall = calls.find((item) => item.id === selectedCallId);
  const [downloadedArtifact, setDownloadedArtifact] = useState<ArtifactRecord | null>(null);
  const [artifactKind, setArtifactKind] = useState('genui');
  const [artifactStatus, setArtifactStatus] = useState('');

  const responsePayload = selectedCall?.response;
  const responseData = responsePayload?.data;
  const responseDataRecord = recordValue(responseData);
  const finalStreamContent = selectedCall?.finalStreamContent;
  const parsedStream = useMemo(() => (
    finalStreamContent
      ? parseLegacyToolResponse(finalStreamContent) ?? parsePythonRepr(finalStreamContent)
      : undefined
  ), [finalStreamContent]);
  const parsedFrameStream = useMemo(() => {
    const frame = selectedCall?.finalFrame;
    const reply = recordValue(frame?.reply);
    const streamInfo = recordValue(reply.streamInfo);
    const content = typeof streamInfo.streamContent === 'string'
      ? streamInfo.streamContent
      : typeof frame?.streamContent === 'string' ? frame.streamContent : undefined;
    return content ? parseLegacyToolResponse(content) ?? parsePythonRepr(content) : undefined;
  }, [selectedCall?.finalFrame]);
  const inlineArtifact = useMemo(() => (
    selectedCall?.operation === COMPACT_DSL_OPERATION
      ? artifactFromValue(responsePayload, selectedCall.id)
        ?? artifactFromValue(responseData, selectedCall.id)
        ?? artifactFromValue(parsedStream, selectedCall.id)
        ?? artifactFromValue(parsedFrameStream, selectedCall.id)
        ?? artifactFromValue(selectedCall.finalFrame, selectedCall.id)
      : null
  ), [parsedFrameStream, parsedStream, responseData, responsePayload, selectedCall]);

  useEffect(() => {
    let active = true;
    setDownloadedArtifact(null);
    setArtifactStatus('');
    if (!selectedCall || selectedCall.operation !== COMPACT_DSL_OPERATION || selectedCall.status !== 'success') {
      return () => { active = false; };
    }
    const candidate = inlineArtifact;
    if (candidate?.genui || candidate?.cardSpec !== undefined) {
      setDownloadedArtifact(candidate);
      return () => { active = false; };
    }
    const artifactUrl = candidate?.artifactUrl ?? artifactReference(responseDataRecord.artifactUrl
      ?? responseDataRecord.artifact_url
      ?? responseDataRecord.artifact_reference
      ?? responseDataRecord.artifactReference);
    if (!artifactUrl) return () => { active = false; };
    const params = new URLSearchParams({ url: artifactUrl });
    if (typeof responseDataRecord.artifactDigest === 'string') params.set('digest', responseDataRecord.artifactDigest);
    setArtifactStatus('正在下载 artifact…');
    fetch(`/debug/artifact?${params.toString()}`)
      .then(async (response) => {
        const body = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `下载失败（${response.status}）`);
        return body as ArtifactRecord;
      })
      .then((loaded) => {
        if (!active) return;
        const normalized = { ...loaded, source: 'interface' as const, runId: selectedCall.id };
        setDownloadedArtifact(normalized);
        setArtifact({ ...normalized });
        setArtifactStatus('artifact 已下载');
      })
      .catch((error) => {
        if (active) setArtifactStatus(error instanceof Error ? error.message : String(error));
      });
    return () => { active = false; };
  }, [inlineArtifact, responseData, selectedCall, setArtifact]);

  const inlineArtifactUrl = inlineArtifact ? inlineArtifact.artifactUrl : undefined;
  const activeDownloadedArtifact = downloadedArtifact
    && (!selectedCall || downloadedArtifact.runId === selectedCall.id)
    ? downloadedArtifact
    : null;
  const selectedArtifact = activeDownloadedArtifact ?? inlineArtifact ?? (
    artifact && (!selectedCall || artifact.runId === selectedCall.id || artifact.artifactUrl === inlineArtifactUrl)
      ? artifact as ArtifactRecord
      : null
  );
  const responseSource = renderableValue(responsePayload)
    ?? renderableValue(responseData)
    ?? renderableValue(parsedStream)
    ?? finalFrameSource(selectedCall?.finalFrame);
  const selectedArtifactValue = selectedArtifact?.genui
    ?? (selectedArtifact?.cardSpec === undefined ? undefined : jsonText(selectedArtifact.cardSpec));
  const isCompactSelection = selectedCall?.operation === COMPACT_DSL_OPERATION;
  const selectedValue = isCompactSelection
    ? selectedArtifactValue
    : selectedArtifactValue
      ?? responseSource
      ?? (responseData == null
        ? (responsePayload == null ? selectedCall?.finalStreamContent : JSON.stringify(responsePayload, null, 2))
        : JSON.stringify(responseData, null, 2));
  const artifactValue = artifact?.genui
    ?? (artifact?.cardSpec == null ? undefined : JSON.stringify(artifact.cardSpec, null, 2))
    ?? (artifact?.raw == null ? undefined : JSON.stringify(artifact.raw, null, 2));
  const initialValue = selectedCall ? selectedValue : artifactValue;
  const activeArtifact = selectedArtifact ?? artifact;
  const activeArtifactRecord = recordValue(activeArtifact);
  const rendererCardSize = resolveCardSize(
    activeArtifact,
    activeArtifactRecord.taskSpec ?? selectedCall?.request ?? activeArtifactRecord.raw,
  );
  const artifactKey = selectedCall?.id ?? artifact?.runId ?? artifact?.artifactDigest ?? initialValue ?? 'empty';
  const availableKinds = useMemo(
    () => ARTIFACT_KINDS.filter(([kind]) => selectedArtifact?.[kind] !== undefined),
    [selectedArtifact],
  );
  useEffect(() => {
    if (availableKinds.length && !availableKinds.some(([kind]) => kind === artifactKind)) {
      setArtifactKind(availableKinds[0][0]);
    }
  }, [availableKinds, artifactKind]);

  return (
    <div className="renderer-route">
      <div className="renderer-route__canvas">
        <CardRenderer
          key={artifactKey}
          initialValue={selectedCall ? (initialValue ?? '') : initialValue}
          assetBaseUrl={DEFAULT_ASSET_BASE_URL}
          cardSize={rendererCardSize}
          onArtifact={(document) => {
            pushEvent({
              channel: 'renderer',
              direction: 'local',
              kind: 'artifact_rendered',
              payload: { format: document.mode, rows: document.rows, componentCount: document.components.size, dataPathCount: document.dataPathCount },
            });
          }}
        />
      </div>
      <aside className="renderer-route__inspector" aria-label="Artifact 检查器">
        <div className="renderer-route__inspector-heading">
          <div><span className="section-kicker">ARTIFACT</span><h2>Artifact 检查器</h2></div>
          {artifactStatus && <span className={artifactStatus.includes('失败') || artifactStatus.includes('错误') ? 'is-error' : ''}>{artifactStatus}</span>}
        </div>
        {selectedArtifact ? (
          <>
            <div className="renderer-route__artifact-actions">
              <span title={selectedArtifact.artifactUrl}>{selectedArtifact.artifactUrl || '当前接口返回'}</span>
              <button type="button" onClick={() => navigator.clipboard?.writeText(jsonText(selectedArtifact[artifactKind]))}>复制</button>
              <button type="button" onClick={() => {
                const url = URL.createObjectURL(new Blob([jsonText(selectedArtifact[artifactKind])], { type: 'application/json' }));
                const anchor = document.createElement('a'); anchor.href = url; anchor.download = `${artifactKind}.json`; anchor.click(); URL.revokeObjectURL(url);
              }}>下载</button>
            </div>
            <ArtifactPreview artifact={selectedArtifact} activeKind={artifactKind} onKindChange={setArtifactKind} />
          </>
        ) : (
          <div className="renderer-route__empty">点击左侧成功的 Compact DSL 调用后，这里会自动读取 artifact 并渲染。</div>
        )}
      </aside>
    </div>
  );
}
