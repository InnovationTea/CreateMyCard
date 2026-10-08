import { resolvePathBindingsInValue } from "./resolve-path-bindings.js";
import { resolveEventContextValue } from "./resolve-event-context.js";
import type { EventContext, InteractionHost } from "./types.js";

function isRecord(x: unknown): x is Record<string, unknown> {
  return typeof x === "object" && x !== null && !Array.isArray(x);
}

function parseOpenUrlArgs(raw: unknown): { url: string } | null {
  if (!isRecord(raw)) return null;
  const u = raw.url;
  if (u === null || u === undefined) return null;
  const str = typeof u === "string" ? u : String(u);
  if (str.length === 0) return null;
  return { url: str };
}

/**
 * Runs a component-level **`action.functionCall`** (e.g. **`openUrl`**)
 * from **server → client** `updateComponents` (see `skills/a2ui/reference/protocol/extended-interactions.md`).
 *
 * When {@link EventContext.getDataModelLeaf} is set, `functionCall.args` is run through
 * {@link resolvePathBindingsInValue} for `{"path":"…"}` leaves.
 */
export async function runActionFunctionCall(
  action: unknown,
  host: InteractionHost,
  ctx: EventContext,
): Promise<void> {
  if (!isRecord(action)) return;
  const rawFc = action.functionCall;
  if (!isRecord(rawFc) || typeof rawFc.call !== "string") return;
  const call = rawFc.call;
  let args: unknown = rawFc.args;
  if (ctx.getDataModelLeaf) {
    args = resolvePathBindingsInValue(args, ctx.getDataModelLeaf);
  }
  if (call === "openUrl") {
    const parsed = parseOpenUrlArgs(args);
    if (parsed && host.openUrl) {
      await host.openUrl(parsed);
      return;
    }
  }
  await host.functionCall?.({ call, args, componentId: ctx.componentId });
}

/**
 * Handles any **`action.event`**: fully resolves `event.context`, then delivers the **client→server wire** payload.
 */
async function runActionEvent(
  event: Record<string, unknown>,
  host: InteractionHost,
  ctx: EventContext,
): Promise<void> {
  if (!host.submitForm) return;
  const name = event.name;
  if (typeof name !== "string" || name.length === 0) return;

  const rawContext = isRecord(event.context) ? event.context : {};

  const getDataModelLeaf = ctx.getDataModelLeaf ?? (() => "");
  const getSelectedGroupValue = ctx.getSelectedGroupValue ?? (() => "");

  const resolved = resolveEventContextValue(rawContext, {
    getDataModelLeaf: (path) => {
      const v = getDataModelLeaf(path);
      if (v === undefined || v === null) return "";
      return v;
    },
    getSelectedGroupValue,
  }) as Record<string, unknown>;

  const surfaceId =
    typeof ctx.surfaceId === "string" && ctx.surfaceId.length > 0 ? ctx.surfaceId : "default";

  await host.submitForm({
    name,
    surfaceId,
    sourceComponentId: ctx.componentId,
    timestamp: new Date().toISOString(),
    context: resolved,
  });
}

/**
 * Dispatches component **`action`**: prefers **`functionCall`** when present; otherwise runs **`event`**.
 */
export async function runActionDispatch(
  action: unknown,
  host: InteractionHost,
  ctx: EventContext,
): Promise<void> {
  if (Array.isArray(action)) {
    for (const item of action) await runActionDispatch(item, host, ctx);
    return;
  }
  if (!isRecord(action)) return;
  const fc = action.functionCall;
  if (isRecord(fc) && typeof fc.call === "string") {
    await runActionFunctionCall(action, host, ctx);
    return;
  }
  const ev = action.event;
  if (isRecord(ev)) {
    await runActionEvent(ev, host, ctx);
  }
}
