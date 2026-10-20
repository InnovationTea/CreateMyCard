/**
 * 从本次会话的调用历史里取出端到端／接口调试拿到的真实输出。
 *
 * debug_tools 已经把「入参给模型 → 取回 md／DSL → 渲染」这条链路跑通，结果只存在浏览器
 * sessionStorage 的调用记录里，后端并不落盘。期望对比页需要把这些真实输出交给后端的
 * 同一套指纹与尺寸判定逻辑，所以这里只负责按与卡片渲染页相同的口径把 genui DSL 与
 * query 从记录里挖出来，不做任何匹配计算。
 */

import { parseLegacyToolResponse, parsePythonRepr } from '@widget-debug/interface';
import type { ToolCallRecord } from './types';

export type SessionArtifact = {
  id: string;
  title: string;
  query: string;
  genui: string;
  size: string;
  status: string;
  at: string;
};

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function parsedText(value: string): Record<string, unknown> {
  return record(parseLegacyToolResponse(value) ?? parsePythonRepr(value));
}

/** 展平 response／finalFrame／streamContent 里可能的多层 data，取最完整的业务负载。 */
function payloadOf(call: ToolCallRecord): Record<string, unknown> {
  const response = record(call.response);
  const frame = record(call.finalFrame);
  const reply = record(frame.reply);
  const streamInfo = record(reply.streamInfo);
  const stream = typeof call.finalStreamContent === 'string' && call.finalStreamContent.trim()
    ? parsedText(call.finalStreamContent)
    : typeof streamInfo.streamContent === 'string'
      ? parsedText(streamInfo.streamContent)
      : {};
  return {
    ...response,
    ...record(response.data),
    ...record(record(response.data).data),
    ...frame,
    ...record(frame.data),
    ...reply,
    ...stream,
  };
}

function genuiOf(payload: Record<string, unknown>): string {
  for (const key of ['genui', 'dsl', 'compactDsl']) {
    const value = payload[key];
    if (typeof value === 'string' && value.trim()) return value;
  }
  return '';
}

function queryOf(call: ToolCallRecord, payload: Record<string, unknown>): string {
  const request = record(call.request);
  const content = record(request.content);
  const utterance = record(request.utterance);
  const candidates = [
    utterance.original, content.userQuery, request.userQuery,
    payload.userQuery, content.query, request.query,
  ];
  for (const candidate of candidates) {
    if (typeof candidate === 'string' && candidate.trim()) return candidate.trim();
  }
  return '';
}

function sizeOf(payload: Record<string, unknown>): string {
  const spec = record(payload.cardSpec);
  const size = spec.suggestSize ?? payload.size;
  return typeof size === 'string' ? size.trim() : '';
}

/** 只返回确实带 DSL 的成功调用；失败或没有 genui 的记录不参与对比。 */
export function sessionArtifacts(calls: ToolCallRecord[]): SessionArtifact[] {
  return calls.flatMap((call) => {
    if (call.status !== 'success') return [];
    const payload = payloadOf(call);
    const genui = genuiOf(payload);
    if (!genui) return [];
    const source = call.source === 'e2e' ? '端到端' : '接口调试';
    return [{
      id: call.id,
      title: `${source} · ${call.operation || '生成调用'}`,
      query: queryOf(call, payload),
      genui,
      size: sizeOf(payload),
      status: call.status,
      at: call.finishedAt ?? call.completedAt ?? call.startedAt ?? '',
    }];
  });
}
