import { useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useWorkbench } from '../context';
import type { ToolCallRecord } from '../types';

const OPERATION_LABELS: Record<string, string> = {
  getWidgetCapabilityOverview: '能力概览',
  getDataCapabilitySchemas: '数据 Schema',
  generateWidgetCardCompactDsl: '生成 Compact DSL',
};

function operationLabel(operation: string): string {
  return OPERATION_LABELS[operation] ?? operation;
}

function payloadText(value: unknown): string {
  if (typeof value === 'string') return value;
  if (value === undefined) return '—';
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function payloadSummary(value: unknown, fallback = '—'): string {
  const text = typeof value === 'string' ? value : value === undefined ? '' : payloadText(value);
  const compact = text.replace(/\s+/g, ' ').trim();
  if (!compact) return fallback;
  return compact.length > 92 ? `${compact.slice(0, 89)}…` : compact;
}

function errorValue(value: unknown): string | undefined {
  if (value === undefined || value === null) return undefined;
  if (typeof value === 'string') return value.trim() || undefined;
  return payloadText(value);
}

function errorCodeValue(value: unknown): string | undefined {
  if (value === undefined || value === null) return undefined;
  const normalized = String(value).trim();
  return normalized && normalized !== '0' ? normalized : undefined;
}

function timeText(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function statusText(status: ToolCallRecord['status']): string {
  if (status === 'pending') return '进行中';
  if (status === 'success') return '成功';
  return '失败';
}

function responseText(call: ToolCallRecord): string {
  // 优先展示服务返回的数据本身。完整包络仍保存在共享记录中，但直接
  // 展示包络会让历史过于嘈杂，也会遮住渲染模块真正需要的最终返回值。
  const responseError = errorValue(call.response?.error);
  const responseErrorCode = errorCodeValue(call.response?.errorCode);
  const finalFrame = call.finalFrame;
  const frameError = errorValue(finalFrame?.error ?? finalFrame?.errorMessage);
  const frameErrorCode = errorCodeValue(finalFrame?.errorCode);
  const streamInfo = finalFrame?.reply?.streamInfo;
  const streamError = streamInfo && typeof streamInfo.streamContent === 'string'
    && (streamInfo.streamType === 'final_error' || streamInfo.streamType === 'error')
    ? errorValue(streamInfo.streamContent)
    : undefined;
  if (call.status === 'error') {
    if (call.error) return call.error;
    if (responseError) return responseError;
    if (responseErrorCode) return `错误码 ${responseErrorCode}`;
    if (frameError) return frameError;
    if (frameErrorCode) return `错误码 ${frameErrorCode}`;
    if (streamError) return streamError;
  }
  if (call.response?.data !== undefined) return payloadText(call.response.data);
  if (call.finalStreamContent !== undefined) return call.finalStreamContent || '（空 final 内容）';
  if (call.finalFrame !== undefined) return payloadText(call.finalFrame);
  if (call.response !== undefined) return payloadText(call.response);
  return call.status === 'pending' ? '等待 final 帧…' : '未返回 final 内容';
}

export function CallHistory() {
  const { calls, selectedCallId, selectCall, clearCalls } = useWorkbench();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const visibleCalls = useMemo(() => calls.slice(-100).reverse(), [calls]);

  const choose = (call: ToolCallRecord) => {
    selectCall(call.id);
    setMobileOpen(false);
    if (call.operation === 'generateWidgetCardCompactDsl' && call.status === 'success'
      && location.pathname !== '/renderer') {
      navigate('/renderer');
    }
  };

  return (
    <section className={`call-history${mobileOpen ? ' is-mobile-open' : ''}`} aria-label="接口调用历史">
      <div className="history-heading">
        <div>
          <span className="section-kicker">CALL HISTORY</span>
          <h2>接口调用历史</h2>
        </div>
        <div className="history-heading-actions">
          <span className="history-count">{calls.length}</span>
          <button type="button" className="history-mobile-toggle" onClick={() => setMobileOpen((open) => !open)} aria-expanded={mobileOpen}>
            {mobileOpen ? '收起' : '展开'}
          </button>
          {calls.length > 0 && <button type="button" className="history-clear" onClick={clearCalls}>清空</button>}
        </div>
      </div>
      <div className="history-list">
        {visibleCalls.length === 0 ? (
          <p className="empty-row">完成一次接口调用后显示 request / final。</p>
        ) : visibleCalls.map((call) => {
          const isSelected = selectedCallId === call.id;
          return (
            <article className={`history-item${isSelected ? ' is-selected' : ''}`} key={call.id}>
              <button type="button" className="history-item-header" onClick={() => choose(call)} aria-pressed={isSelected}>
                <span className={`history-status ${call.status}`} aria-hidden="true" />
                <span className="history-item-main">
                  <strong>{operationLabel(call.operation)}</strong>
                  <small>{call.source === 'e2e' ? '端到端' : '接口调试'} · {timeText(call.startedAt)}{call.durationMs != null ? ` · ${call.durationMs} ms` : ''}</small>
                  <span className="history-summary" title={payloadSummary(call.request)}>
                    <b>入</b> {payloadSummary(call.request)}
                  </span>
                  <span className="history-summary" title={responseText(call)}>
                    <b>回</b> {payloadSummary(responseText(call), call.status === 'pending' ? '等待 final 帧…' : '未返回 final 内容')}
                  </span>
                </span>
                <span className="history-item-state">{statusText(call.status)}</span>
              </button>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export default CallHistory;
