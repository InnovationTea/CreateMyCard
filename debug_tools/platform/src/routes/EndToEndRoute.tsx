import { useWorkbench } from '../context';
import { EndToEndDebug } from '@widget-debug/end-to-end';
import { buildToolRequest, executeBrowserTool } from '../toolBridge';
import type { BrowserToolResult } from '@widget-debug/end-to-end';
import { selectedToolWsBaseUrl } from '../config';
import { SelectedMicroserviceStatus } from '../components/BackendStatusWidget';

function healthUrl(agentWsUrl: string): string {
  const configured = agentWsUrl.trim();
  if (!configured) return '';
  if (!/^(?:wss?|https?):\/\//i.test(configured)) {
    const path = configured.startsWith('/') ? configured : `/${configured}`;
    return /^\/debug\/(?:e2e|agent)\/ws\/?(?:[?#].*)?$/i.test(path)
      ? '/debug/health'
      : '';
  }
  try {
    const httpUrl = new URL(configured.replace(/^ws:/i, 'http:').replace(/^wss:/i, 'https:'));
    // A custom Agent URL does not imply that its host exposes our health
    // endpoint.  Keep the health indicator optional instead of probing an
    // unrelated origin and presenting a misleading failure.
    if (!/^\/debug\/(?:e2e|agent)\/ws\/?$/i.test(httpUrl.pathname)) return '';
    if (typeof window !== 'undefined' && httpUrl.origin !== window.location.origin) return '';
    httpUrl.pathname = '/debug/health';
    httpUrl.search = '';
    httpUrl.hash = '';
    return httpUrl.toString();
  } catch {
    return '';
  }
}

export function EndToEndRoute() {
  const { config, recordCall, updateCall, pushEvent, setArtifact } = useWorkbench();
  const agentSocket = config.agentWsUrl;
  const effectiveConfig = { ...config, toolWsBaseUrl: selectedToolWsBaseUrl(config) };
  return (
    <EndToEndDebug
      socketPath={agentSocket}
      healthPath={healthUrl(agentSocket)}
      config={effectiveConfig}
      microserviceStatus={<SelectedMicroserviceStatus />}
      executeTool={async (operation, request, meta) => {
        const typedOperation = operation as Parameters<typeof buildToolRequest>[1];
        const envelope = buildToolRequest(effectiveConfig, typedOperation, request, {
          sessionId: meta.conversationId,
          interactionId: meta.callId,
          utterance: meta.userText,
        });
        const startedAt = new Date().toISOString();
        const callId = recordCall({
          operation: typedOperation,
          source: 'e2e',
          status: 'pending',
          startedAt,
          request: envelope,
          callId: meta.callId,
          runId: meta.runId,
        });
        let result: BrowserToolResult;
        try {
          result = await executeBrowserTool(effectiveConfig, operation, request, meta, envelope);
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          updateCall(callId, {
            status: 'error',
            finishedAt: new Date().toISOString(),
            response: { operation, status: 'error', error: message },
            error: message,
          });
          return { ok: false, operation, error: message };
        }
        const finishedAt = new Date().toISOString();
        const error = result.error === undefined
          ? undefined
          : typeof result.error === 'string'
            ? result.error
            : JSON.stringify(result.error);
        updateCall(callId, {
          status: result.ok ? 'success' : 'error',
          finishedAt,
          finalFrame: result.finalFrame,
          finalStreamContent: result.finalStreamContent,
          response: result,
          error: result.ok ? undefined : error ?? '工具调用失败',
        });
        if (result.ok && result.data && typeof result.data === 'object' && !Array.isArray(result.data)) {
          const data = result.data as Record<string, unknown>;
          const nested = data.data && typeof data.data === 'object' && !Array.isArray(data.data)
            ? data.data as Record<string, unknown>
            : {};
          const payload = { ...data, ...nested };
          if (payload.genui !== undefined || payload.cardSpec !== undefined) {
            setArtifact({
              source: 'e2e',
              runId: meta.runId,
              genui: typeof payload.genui === 'string' ? payload.genui : undefined,
              cardSpec: payload.cardSpec,
              artifactUrl: typeof payload.artifactUrl === 'string' ? payload.artifactUrl : undefined,
              artifactDigest: typeof payload.artifactDigest === 'string' ? payload.artifactDigest : undefined,
              raw: result.data,
            });
          }
        }
        return result;
      }}
      onEvent={(event) => pushEvent({ channel: 'e2e', direction: event.direction, kind: event.kind, payload: event.payload })}
      onArtifact={(artifact) => setArtifact({ ...artifact, source: 'e2e' })}
    />
  );
}
