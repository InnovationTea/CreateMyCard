/**
 * 渲染器转换端点的唯一出口。
 *
 * 本地调试平台沿用同源 `/debug/renderer/convert`；站点版在入口上写入
 * `__WIDGET_CONVERT_ENDPOINT__`，把同一批调用改指到只读 Function 回放层，
 * 这样平台里所有卡片预览都不需要逐个传参。
 */

export const DEFAULT_CONVERSION_URL = '/debug/renderer/convert';

export function resolveConversionUrl(override?: string): string {
  if (override) return override;
  const scope = globalThis as { __WIDGET_CONVERT_ENDPOINT__?: string };
  const configured = scope.__WIDGET_CONVERT_ENDPOINT__;
  return typeof configured === 'string' && configured ? configured : DEFAULT_CONVERSION_URL;
}
