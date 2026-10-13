import { Buffer } from "node:buffer";

export const runtime = "nodejs";

/**
 * Same-origin image proxy (former Vite `imgProxyPlugin`):
 * `/img-proxy/${encodeURIComponent(fullUrl)}` so the browser sends no Referer.
 */
export async function GET(
  _request: Request,
  context: { params: Promise<{ encoded: string[] }> },
) {
  const { encoded } = await context.params;
  const joined = encoded?.join("/") ?? "";
  let targetUrl: string;
  try {
    targetUrl = decodeURIComponent(joined);
    new URL(targetUrl);
  } catch {
    return new Response("Bad Request: invalid proxy URL", { status: 400 });
  }

  try {
    const upstream = await fetch(targetUrl, {
      headers: { referer: "" },
      redirect: "follow",
    });
    const buf = Buffer.from(await upstream.arrayBuffer());
    const headers = new Headers();
    headers.set(
      "content-type",
      upstream.headers.get("content-type") ?? "application/octet-stream",
    );
    headers.set(
      "cache-control",
      upstream.headers.get("cache-control") ?? "public, max-age=86400",
    );
    headers.set("access-control-allow-origin", "*");
    return new Response(buf, { status: upstream.status, headers });
  } catch {
    return new Response("Bad Gateway: upstream fetch failed", { status: 502 });
  }
}
