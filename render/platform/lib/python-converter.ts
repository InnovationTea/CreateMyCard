import { compileA2uiJsonl, compileMiniDsl } from "./mini-renderer";
import type { CardSize } from "./compact-components";

export type PreviewConverter = "python" | "typescript";

export class PythonConversionError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail: string,
  ) {
    super(message);
    this.name = "PythonConversionError";
  }
}

type FetchLike = typeof fetch;

type PythonConversionResponse = {
  genui: string;
  size: CardSize;
};

function isPythonConversionResponse(value: unknown): value is PythonConversionResponse {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const response = value as Record<string, unknown>;
  return typeof response.genui === "string"
    && (response.size === "2x2" || response.size === "2x4");
}

function conversionErrorDetail(value: unknown): string {
  if (!value || typeof value !== "object" || Array.isArray(value)) return "转换服务返回了未知错误";
  const detail = (value as Record<string, unknown>).detail;
  return typeof detail === "string" && detail.trim() ? detail : "转换服务返回了未知错误";
}

export async function compileCompactDslWithPython(
  source: string,
  options: {
    size: CardSize;
    appVersion?: string;
    endpoint?: string;
    signal?: AbortSignal;
    fetchImpl?: FetchLike;
  },
) {
  const fetchImpl = options.fetchImpl ?? fetch;
  let response: Response;
  try {
    response = await fetchImpl(options.endpoint ?? "/api/compact-convert", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source,
        size: options.size,
        appVersion: options.appVersion,
      }),
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    const detail = error instanceof Error ? error.message : String(error);
    throw new Error(`无法连接正式 Python 转换器：${detail}。请启动 Debug Tools，或显式切换到本地 TS。`);
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new Error(`正式 Python 转换器返回了非 JSON 响应（HTTP ${response.status}）。`);
  }
  if (!response.ok) {
    const detail = conversionErrorDetail(payload);
    throw new PythonConversionError(
      `正式 Python 转换失败：${detail}（HTTP ${response.status}）。`,
      response.status,
      detail,
    );
  }
  if (!isPythonConversionResponse(payload)) {
    throw new Error("正式 Python 转换器返回了无效结果。");
  }
  return compileA2uiJsonl(payload.genui, { size: payload.size });
}

export async function compileCompactDslForPreview(
  source: string,
  options: Parameters<typeof compileCompactDslWithPython>[1],
) {
  try {
    return await compileCompactDslWithPython(source, options);
  } catch (error) {
    if (!(error instanceof PythonConversionError) || error.status !== 422) throw error;
    const result = compileMiniDsl(source, { size: options.size, previewMode: true });
    result.warnings.unshift(`正式 Python 转换器拒绝该 DSL：${error.detail} 已切换为宽松预览。`);
    return result;
  }
}
