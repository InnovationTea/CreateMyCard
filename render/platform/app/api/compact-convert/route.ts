import { NextResponse } from "next/server";

const DEFAULT_CONVERTER_URL = "http://127.0.0.1:8888/debug/renderer/convert";

function converterUrl(): string {
  return process.env.COMPACT_CONVERTER_URL?.trim() || DEFAULT_CONVERTER_URL;
}

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "请求必须是合法 JSON" }, { status: 400 });
  }

  try {
    const upstream = await fetch(converterUrl(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
      signal: AbortSignal.timeout(30_000),
    });
    const text = await upstream.text();
    return new Response(text, {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json" },
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    return NextResponse.json({
      detail: `无法连接 ${converterUrl()}：${detail}。请先启动 Debug Tools，或设置 COMPACT_CONVERTER_URL。`,
    }, { status: 503 });
  }
}
