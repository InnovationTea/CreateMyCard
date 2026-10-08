import {
  isLikelyGraphCommand,
  parseCompactLine,
  stripTrailingCommasInJsonText,
} from "./compact-parse.js";
import { tryNormalizeV09Protocol } from "./protocol-v09.js";

/** v0.9 A2UI `deleteSurface`-only envelope: callers may treat as no-op (e.g. batch static render); skip without error. */
function shouldSilentlySkipV09DeleteSurfaceLine(value: unknown): boolean {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const o = value as Record<string, unknown>;
  if (o.version !== "v0.9") return false;
  const keys = Object.keys(o);
  if (keys.length !== 2 || !("deleteSurface" in o)) return false;
  const ds = o.deleteSurface;
  if (typeof ds !== "object" || ds === null || Array.isArray(ds)) return false;
  return typeof (ds as { surfaceId?: unknown }).surfaceId === "string";
}

/** Indices i (outside string literals) where `s.slice(i, i + 3) === "}}]"`. */
function collectDoubleCloseBeforeBracketIndices(s: string): number[] {
  const out: number[] = [];
  let inString = false;
  let escape = false;
  for (let i = 0; i + 2 < s.length; i++) {
    const c = s[i]!;
    if (inString) {
      if (escape) {
        escape = false;
        continue;
      }
      if (c === "\\") {
        escape = true;
        continue;
      }
      if (c === '"') {
        inString = false;
      }
      continue;
    }
    if (c === '"') {
      inString = true;
      continue;
    }
    if (c === "}" && s[i + 1] === "}" && s[i + 2] === "]") {
      out.push(i);
    }
  }
  return out;
}

function tryParseJsonLenient(s: string): unknown | undefined {
  try {
    return JSON.parse(s) as unknown;
  } catch {
    try {
      return JSON.parse(stripTrailingCommasInJsonText(s)) as unknown;
    } catch {
      return undefined;
    }
  }
}

/**
 * If the model emits an extra `}` before an array close (`…}}]…`), replace that
 * `}}]` with `}]` **only** when the result parses as JSON. Tries each match
 * outside strings, left to right (avoids breaking valid `…}}]` in correct JSON,
 * since that input would already have parsed).
 */
function tryRepairExtraCloseBeforeBracket(s: string): string | null {
  for (const i of collectDoubleCloseBeforeBracketIndices(s)) {
    const candidate = s.slice(0, i) + "}]" + s.slice(i + 3);
    if (tryParseJsonLenient(candidate) !== undefined) {
      return candidate;
    }
  }
  return null;
}

/**
 * JsonlStreamParser
 *
 * A character-level streaming parser that emits one complete JSON object at a
 * time by tracking brace depth.  Unlike a newline-based approach this handles:
 *
 *  - Multi-line or compact JSON with no trailing newline
 *  - `{` / `}` that appear inside string values (correctly ignored)
 *  - Escaped quotes (`\"`) inside strings
 *  - Leading junk / whitespace before the first `{`
 *  - Consecutive objects without any separator
 *  - Extra closing `}` immediately after a complete top-level object (model slop): those
 *    braces are kept in the emitted raw segment; {@link emitParsed} retries parse after
 *    stripping trailing `}` if needed.  If the stream chunk ends right after the brace
 *    that closes depth 0, emission waits for the next {@link push} or {@link end} so
 *    trailing `}` bytes in the following chunk are not split into a separate segment.
 *  - Extra `}` before `]` (`…}}]…` outside strings): {@link emitParsed} may replace with
 *    `}]` when the repaired text parses as JSON (model slop before array end).
 *
 * Each complete `{…}` segment is parsed as:
 *  - **v0.9 protocol** — `createSurface` / `updateComponents` / optional `updateDataModel` with `"version":"v0.9"`
 *    (normalized to graph commands, see `tryNormalizeV09Protocol`).
 *    Lines that are **only** `version` + `deleteSurface` are **silently skipped** (no `onMessage`, no error).
 *  - **Classic JSON** (single-key object: `{ "id": { "type", "props", "children"? } }`), or
 *  - **Compact tuple** — after `"id"`, any subset of `"type"`, `{ props }`, `[ children ]` (each at most once,
 *    any order), or **id-only** `{ "id" }`. Normalized for the graph (see `parseCompactLine`).
 *
 * The parser is callback-driven: pass `onMessage` to receive each parsed
 * object, and optionally `onParseError` / `onBraceMismatch` for error handling.
 *
 * Usage:
 *   const parser = new JsonlStreamParser({
 *     onMessage: (obj, rawSegment) => { console.log(obj, rawSegment); },
 *     onParseError: (raw, err) => console.warn("bad json", raw),
 *   });
 *
 *   for await (const token of streamGenUI(prompt)) {
 *     parser.push(token);
 *   }
 *   parser.end();
 */

export interface JsonlStreamParserOptions<T = unknown> {
  /**
   * Called with each fully-parsed graph command and the **raw** `{…}` segment
   * from the stream (trimmed), for logging / debugging.
   */
  onMessage: (value: T, rawSegment: string) => void;
  /** Called when a complete `{…}` segment fails JSON.parse. */
  onParseError?: (raw: string, error: unknown) => void;
  /** Called when a `}` would make depth negative (malformed stream). */
  onBraceMismatch?: () => void;
}

export class JsonlStreamParser<T = unknown> {
  private buffer = "";
  private depth = 0;
  private inString = false;
  private escape = false;
  private segmentStart = -1;
  /**
   * The next position in `buffer` to scan from.
   * Persisted across `push()` calls so we never re-scan already-processed
   * characters (re-scanning would corrupt `depth` / `inString` state).
   */
  private processingFrom = 0;
  /**
   * When the brace that closes the top-level object is the **last byte** of the
   * current buffer, we cannot yet run the greedy trailing-`}` extension (the next
   * chunk may be more `}`). Hold the segment until more input or {@link end}.
   */
  private awaitTrailingClose = false;
  private segmentEmitStart = -1;

  private readonly onMessage: (value: T, rawSegment: string) => void;
  private readonly onParseError?: (raw: string, error: unknown) => void;
  private readonly onBraceMismatch?: () => void;

  constructor(options: JsonlStreamParserOptions<T>) {
    this.onMessage = options.onMessage;
    this.onParseError = options.onParseError;
    this.onBraceMismatch = options.onBraceMismatch;
  }

  /** Feed an incoming chunk; complete top-level objects are emitted via `onMessage`. */
  push(chunk: string): void {
    if (this.awaitTrailingClose) {
      const j0 = this.buffer.length;
      this.buffer += chunk;
      let j = j0;
      while (j < this.buffer.length && this.buffer[j] === "}") {
        j++;
      }
      if (j < this.buffer.length) {
        const raw = this.buffer.slice(this.segmentEmitStart, j);
        this.buffer = this.buffer.slice(j);
        this.awaitTrailingClose = false;
        this.segmentEmitStart = -1;
        this.processingFrom = 0;
        this.emitParsed(raw);
        this.process();
        return;
      }
      this.processingFrom = this.buffer.length;
      return;
    }
    this.buffer += chunk;
    this.process();
  }

  /**
   * Signal end-of-stream.  Flushes a segment waiting on trailing `}` when the
   * stream ended right after a top-level close; otherwise incomplete objects
   * stay in the buffer (see `getPending()`).
   */
  end(): void {
    if (!this.awaitTrailingClose) {
      return;
    }
    const raw = this.buffer.slice(this.segmentEmitStart);
    this.buffer = "";
    this.awaitTrailingClose = false;
    this.segmentEmitStart = -1;
    this.processingFrom = 0;
    this.emitParsed(raw);
  }

  /** Returns any unconsumed tail (incomplete object or pre-`{` junk). */
  getPending(): string {
    return this.buffer;
  }

  /** Reset all state so the instance can be reused for a new stream. */
  reset(): void {
    this.buffer = "";
    this.depth = 0;
    this.inString = false;
    this.escape = false;
    this.segmentStart = -1;
    this.processingFrom = 0;
    this.awaitTrailingClose = false;
    this.segmentEmitStart = -1;
  }

  private process(): void {
    // Resume scanning from where we stopped last time — never re-scan
    // already-processed characters.
    let i = this.processingFrom;

    while (i < this.buffer.length) {
      const c = this.buffer[i]!;

      // ── Inside a string literal ───────────────────────────────────────────
      if (this.inString) {
        if (this.escape) {
          this.escape = false;
          i++;
          continue;
        }
        if (c === "\\") {
          this.escape = true;
          i++;
          continue;
        }
        if (c === '"') {
          this.inString = false;
        }
        i++;
        continue;
      }

      // ── Outside a string literal ──────────────────────────────────────────
      if (c === '"') {
        this.inString = true;
        i++;
        continue;
      }

      if (c === "{") {
        if (this.depth === 0) {
          this.segmentStart = i;
        }
        this.depth++;
        i++;
        continue;
      }

      if (c === "}") {
        this.depth--;
        i++;

        if (this.depth === 0 && this.segmentStart >= 0) {
          if (i === this.buffer.length) {
            this.awaitTrailingClose = true;
            this.segmentEmitStart = this.segmentStart;
            this.segmentStart = -1;
            this.processingFrom = i;
            break;
          }
          let end = i;
          while (end < this.buffer.length && this.buffer[end] === "}") {
            end++;
          }
          const raw = this.buffer.slice(this.segmentStart, end);
          this.buffer = this.buffer.slice(end);
          i = 0;
          this.segmentStart = -1;
          this.processingFrom = 0;
          this.emitParsed(raw);
          continue;
        }

        if (this.depth < 0) {
          this.depth = 0;
          this.segmentStart = -1;
          this.onBraceMismatch?.();
        }
        continue;
      }

      i++;
    }

    if (this.segmentStart === -1 && this.depth === 0 && !this.awaitTrailingClose) {
      this.buffer = "";
      this.processingFrom = 0;
    } else {
      this.processingFrom = i;
    }
  }

  private emitParsed(raw: string): void {
    const segmentForLog = raw.trim();
    let parseSlice = segmentForLog;

    // Retry: `}}]` → `}]` when repair parses; then strip trailing `}` (model slop).
    const maxTrimAttempts = segmentForLog.length * 2 + 32;
    for (let attempt = 0; attempt < maxTrimAttempts; attempt++) {
      const trimmed = parseSlice;

      // Compact tuple is NOT valid JSON (`{"id", "type", ...}`). Parse it first so we
      // never surface misleading `Expected ':' after property name` from JSON.parse.
      const compact = parseCompactLine(trimmed);
      if (compact) {
        this.onMessage(compact as T, segmentForLog);
        return;
      }

      let parsed: unknown = tryParseJsonLenient(trimmed);

      if (parsed !== undefined) {
        const v09 = tryNormalizeV09Protocol(parsed);
        if (v09 !== null) {
          if (Array.isArray(v09)) {
            for (const cmd of v09) {
              this.onMessage(cmd as T, segmentForLog);
            }
          } else {
            this.onMessage(v09 as T, segmentForLog);
          }
          return;
        }
        if (shouldSilentlySkipV09DeleteSurfaceLine(parsed)) {
          return;
        }
        if (isLikelyGraphCommand(parsed)) {
          this.onMessage(parsed as T, segmentForLog);
          return;
        }
        const err = new Error(
          `Unrecognized JSONL segment: not compact tuple and not single-key graph JSON. Snippet: ${trimmed.slice(0, 160)}${trimmed.length > 160 ? "…" : ""}`,
        );
        if (this.onParseError) {
          this.onParseError(segmentForLog, err);
        } else {
          throw err;
        }
        return;
      }

      const bracketRepaired = tryRepairExtraCloseBeforeBracket(trimmed);
      if (bracketRepaired !== null) {
        parseSlice = bracketRepaired;
        continue;
      }

      if (!trimmed.endsWith("}")) {
        break;
      }
      parseSlice = trimmed.slice(0, -1).trimEnd();
      if (parseSlice.length === 0) {
        break;
      }
    }

    const err = new Error(
      `Unrecognized JSONL segment: not compact tuple and not single-key graph JSON. Snippet: ${segmentForLog.slice(0, 160)}${segmentForLog.length > 160 ? "…" : ""}`,
    );
    if (this.onParseError) {
      this.onParseError(segmentForLog, err);
    } else {
      throw err;
    }
  }
}
