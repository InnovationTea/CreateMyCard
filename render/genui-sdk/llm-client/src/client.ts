import { buildGenUIUserMessage, buildPrompt, type StyleId } from "@genui-sdk/prompt";

/**
 * User message describing a form submit / button action for the next GenUI turn
 * (use with {@link streamGenUI}; pair with {@link LLMClientOptions.currentTreeJson} for patches).
 */
export function buildFormActionUserMessage(
  action: string,
  formValues: Record<string, string>,
): string {
  const json = JSON.stringify(formValues, null, 0);
  return (
    `The user submitted a form action (button click with structured fields).\n` +
    `- **action** (host form / button submit id): ${action}\n` +
    `  Treat this as the user’s **intent for this turn**, not a decorative label.\n` +
    `- **field values** (use as source of truth for the next UI):\n\`\`\`json\n${json}\n\`\`\`\n` +
    `**Instructions:**\n` +
    `- Fulfill the intent implied by **action** using the JSON values (e.g. show a plan, result, or next step).\n` +
    `- Prefer replacing or adding the **main content** (new Card/Text blocks, or a new \`root\` scene if needed) so the user sees **outcomes**, not another confirmation-only screen.\n` +
    `- Apply compact JSONL patches as in the output format; merge or replace nodes so the flow **advances**.`
  );
}

/**
 * Same intent as {@link buildFormActionUserMessage}, wrapped with the current UI tree
 * so the model can emit incremental patches.
 */
export function buildFormActionGenUIMessage(
  action: string,
  formValues: Record<string, string>,
  treeJson: string,
): string {
  return buildGenUIUserMessage(buildFormActionUserMessage(action, formValues), treeJson);
}

/** Client→server payload for `action.event` (same fields as `ActionEventMessage` in `@genui-sdk/interactions`). */
export type ActionEventWire = {
  name: string;
  surfaceId: string;
  sourceComponentId: string;
  timestamp: string;
  context: Record<string, unknown>;
};

/**
 * User message for a resolved **`action.event`** (client→server wire shape per extended-interactions).
 */
export function buildSubmitFormUserMessage(msg: ActionEventWire): string {
  const wire = {
    name: msg.name,
    surfaceId: msg.surfaceId,
    sourceComponentId: msg.sourceComponentId,
    timestamp: msg.timestamp,
    context: msg.context,
  };
  const json = JSON.stringify(wire, null, 0);
  return (
    `The user sent a **client→server action event** (shape: \`name\`, \`surfaceId\`, \`sourceComponentId\`, \`timestamp\`, \`context\`).\n` +
    `- **context** was **resolved at click time** — \`{"path":"…"}\`, \`getSelectedValues\` + radio \`group\`, nested structures.\n` +
    `- **Message** (source of truth for this turn):\n\`\`\`json\n${json}\n\`\`\`\n` +
    `**Instructions:**\n` +
    `- Use field entries in \`context\` and metadata above as the user’s intent and data for this turn.\n` +
    `- Prefer replacing or adding the **main content** so the user sees outcomes, not only a confirmation screen.\n` +
    `- Apply compact JSONL patches as in the output format; merge or replace nodes so the flow **advances**.`
  );
}

export function buildSubmitFormGenUIMessage(msg: ActionEventWire, treeJson: string): string {
  return buildGenUIUserMessage(buildSubmitFormUserMessage(msg), treeJson);
}

const OPENROUTER_DIRECT_URL =
  "https://openrouter.ai/api/v1/chat/completions";

/**
 * Browser (Next platform): `/openrouter-api/...` → streaming proxy Route Handler (see `platform/app/openrouter-api/.../route.ts`).
 * Node / tests: no `import.meta.env` from Vite → direct HTTPS URL.
 * Set `VITE_OPENROUTER_DIRECT=true` to force direct URL (localhost-only; cross-origin will CORS-fail).
 * Set `VITE_OPENROUTER_API_BASE=https://example.com` to use a custom gateway (path `/api/v1/chat/completions` is appended).
 * Use `VITE_OPENROUTER_API_KEY` as the Bearer unless your gateway documents otherwise.
 */
function openRouterChatCompletionsUrl(): string {
  const env = (import.meta as unknown as { env?: Record<string, unknown> }).env;
  if (!env) return OPENROUTER_DIRECT_URL;
  const direct = env.VITE_OPENROUTER_DIRECT;
  if (direct === true || direct === "true" || direct === "1") {
    return OPENROUTER_DIRECT_URL;
  }
  const base = typeof env.VITE_OPENROUTER_API_BASE === "string" ? env.VITE_OPENROUTER_API_BASE.trim() : "";
  if (base.length > 0) {
    return `${base.replace(/\/$/, "")}/api/v1/chat/completions`;
  }
  if (env.DEV === true || env.PROD === true) {
    return "/openrouter-api/api/v1/chat/completions";
  }
  return OPENROUTER_DIRECT_URL;
}

const DEFAULT_MODEL = "z-ai/glm-5";

export interface LLMClientOptions {
  /**
   * OpenRouter API key.  Required — pass it explicitly so this module stays
   * browser-compatible (no dotenv / process.env dependency).
   */
  apiKey: string;
  model?: string;
  /** Style guide id (see `@genui-sdk/prompt` `src/styles/*.md` filenames without `.md`). */
  styleId?: StyleId;
  /**
   * When set (multi-turn), the user message includes this JSON so the model can emit
   * incremental patches. Use compact `uitreeJson(graph)` from `@genui-sdk/graph` (structure summary by default).
   */
  currentTreeJson?: string | null;
  /**
   * Called once on the first non-empty `delta` from SSE (after `JSON.parse`, before redacted-thinking filter).
   * This is the closest client-side measure to “model first token” (provider may batch multiple tokens per chunk).
   */
  onFirstRawDelta?: (elapsedMs: number) => void;
  /**
   * Called once when the first text chunk is yielded (after SSE parse and redacted-thinking filter).
   * Elapsed ms is measured from immediately before `fetch` to that first chunk — “first consumable text” for
   * the parser; content held back inside reasoning tags does not count.
   */
  onFirstToken?: (elapsedMs: number) => void;
  /**
   * Called at most once per request when the stream includes OpenAI-style `usage.prompt_tokens`
   * (OpenRouter typically sends this on the final SSE chunk).
   */
  onPromptTokens?: (promptTokens: number) => void;
}

/**
 * Strips `<think>…</think>` blocks from a streaming token sequence.
 *
 * Reasoning models (e.g. DeepSeek-R1, QwQ) emit their chain-of-thought inside
 * `<think>` tags before the actual answer.  If those tokens reach the parser
 * they may be mistaken for valid JSON commands.  This filter buffers potential
 * tag edges so tags split across chunk boundaries are handled correctly.
 */
class ThinkFilter {
  private inThink = false;
  private buf = "";

  feed(chunk: string): string {
    this.buf += chunk;
    return this.drain();
  }

  private drain(): string {
    let output = "";

    while (this.buf.length > 0) {
      if (!this.inThink) {
        const tagIdx = this.buf.indexOf("<think>");
        if (tagIdx === -1) {
          const lt = this.buf.lastIndexOf("<");
          if (lt !== -1 && "<think>".startsWith(this.buf.slice(lt))) {
            output += this.buf.slice(0, lt);
            this.buf = this.buf.slice(lt);
            break;
          }
          output += this.buf;
          this.buf = "";
          break;
        }
        output += this.buf.slice(0, tagIdx);
        this.buf = this.buf.slice(tagIdx + "<think>".length);
        this.inThink = true;
      } else {
        const endIdx = this.buf.indexOf("</think>");
        if (endIdx === -1) {
          const lt = this.buf.lastIndexOf("<");
          if (lt !== -1 && "</think>".startsWith(this.buf.slice(lt))) {
            this.buf = this.buf.slice(lt);
            break;
          }
          this.buf = "";
          break;
        }
        this.buf = this.buf.slice(endIdx + "</think>".length);
        this.inThink = false;
      }
    }

    return output;
  }
}

type StreamUsage = {
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
};

/** Parse one OpenAI-compatible chat completion SSE `data:` payload. */
function parseStreamChunk(data: string): { text: string; usage?: StreamUsage } {
  try {
    const json = JSON.parse(data) as {
      choices?: Array<{
        delta?: { content?: unknown };
        message?: { content?: unknown };
      }>;
      usage?: StreamUsage;
    };
    const usage = json.usage;

    const ch0 = json.choices?.[0];
    if (!ch0) {
      return { text: "", usage };
    }

    const delta = ch0.delta?.content;
    let text = "";
    if (typeof delta === "string") {
      text = delta;
    } else if (Array.isArray(delta)) {
      text = delta
        .map((p) => (typeof p === "string" ? p : String((p as { text?: unknown }).text ?? "")))
        .join("");
    } else {
      const msg = ch0.message?.content;
      if (typeof msg === "string") text = msg;
    }

    return { text, usage };
  } catch {
    // Incomplete JSON chunk — skip
    return { text: "" };
  }
}

/**
 * Streams GenUI JSONL output from the model token-by-token.
 *
 * @yields Each text chunk (token) as it arrives from the model.
 */
export async function* streamGenUI(
  userPrompt: string,
  options: LLMClientOptions,
): AsyncGenerator<string> {
  const apiKey = options.apiKey.trim();
  if (!apiKey) throw new Error("Missing apiKey — pass it in LLMClientOptions");

  const model = (options.model ?? DEFAULT_MODEL).trim();
  const systemPrompt = buildPrompt(options.styleId);
  const treeJson = options.currentTreeJson?.trim();
  const userContent =
    treeJson && treeJson.length > 0
      ? buildGenUIUserMessage(userPrompt, treeJson)
      : userPrompt;
  const thinkFilter = new ThinkFilter();

  const ttftStart = performance.now();
  let firstRawDeltaReported = false;
  const maybeReportFirstRawDelta = () => {
    if (firstRawDeltaReported) return;
    firstRawDeltaReported = true;
    options.onFirstRawDelta?.(performance.now() - ttftStart);
  };

  let firstTokenReported = false;
  const maybeReportFirstToken = () => {
    if (firstTokenReported) return;
    firstTokenReported = true;
    options.onFirstToken?.(performance.now() - ttftStart);
  };

  let promptTokensReported = false;
  const maybeReportPromptTokens = (usage?: StreamUsage) => {
    if (promptTokensReported) return;
    const n = usage?.prompt_tokens;
    if (typeof n === "number" && Number.isFinite(n) && n >= 0) {
      promptTokensReported = true;
      options.onPromptTokens?.(n);
    }
  };

  const response = await fetch(openRouterChatCompletionsUrl(), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
      "X-Title": "GenUI SDK",
    },
    body: JSON.stringify({
      model,
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: userContent },
      ],
      stream: true,
      temperature: 1,
      max_tokens: 65535,
      // OpenRouter: disable extended reasoning (OpenAI-style effort level).
      reasoning: { effort: "none" },
    }),
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`OpenRouter ${response.status}: ${errText.slice(0, 400)}`);
  }
  if (!response.body) throw new Error("No response body from OpenRouter");

  const decoder = new TextDecoder();
  let sseBuffer = "";

  // Use a reader loop for broader runtime compatibility (e.g. engines where
  // ReadableStream isn't exposed as an async iterable).
  const reader = response.body.getReader();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    if (!value) continue;

    sseBuffer += decoder.decode(value, { stream: true });
    const lines = sseBuffer.split("\n");
    sseBuffer = lines.pop() ?? "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data:")) continue;
      const data = trimmed.slice(5).trim();
      if (data === "[DONE]") continue;

      const { text: raw, usage } = parseStreamChunk(data);
      maybeReportPromptTokens(usage);
      if (raw) {
        maybeReportFirstRawDelta();
        const text = thinkFilter.feed(raw);
        if (text) {
          maybeReportFirstToken();
          yield text;
        }
      }
    }
  }

  // Flush any remaining SSE data
  if (sseBuffer.trim()) {
    for (const line of sseBuffer.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data:")) continue;
      const data = trimmed.slice(5).trim();
      if (data === "[DONE]") continue;
      const { text: raw, usage } = parseStreamChunk(data);
      maybeReportPromptTokens(usage);
      if (raw) {
        maybeReportFirstRawDelta();
        const text = thinkFilter.feed(raw);
        if (text) {
          maybeReportFirstToken();
          yield text;
        }
      }
    }
  }
}
