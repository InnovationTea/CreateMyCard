/**
 * 站点版（只读快照）与本地全功能版共用的构建开关。
 *
 * 站点版由 `npm run build:site` 通过 `.env.site` 打开 VITE_SITE_MODE：
 * 接口改走 app Function 回放、路由只保留可浏览模块、写操作在请求层直接拒绝。
 * 本地 `npm run dev` 与 `npm run build` 不带这个变量，行为完全不变。
 */

export const SITE_MODE = import.meta.env.VITE_SITE_MODE === '1';
export const FUNCTION_BASE = '/functions/v1/app';
export const READONLY_HINT = '站点版是只读快照，该操作需要在本地调试平台执行。';

/** 站点上所有 /debug 接口都由 app Function 回放；其它地址原样放行。 */
export function siteApiUrl(url: string): string {
  if (!SITE_MODE || !url.startsWith('/debug/')) return url;
  return `${FUNCTION_BASE}${url}`;
}

/** 站点版把渲染器的转换端点也指向 Function，供 card_renderer 包读取。 */
export function publishRendererEndpoint(): void {
  if (!SITE_MODE) return;
  const scope = globalThis as { __WIDGET_CONVERT_ENDPOINT__?: string };
  scope.__WIDGET_CONVERT_ENDPOINT__ = siteApiUrl('/debug/renderer/convert');
}
