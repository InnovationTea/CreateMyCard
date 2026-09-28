import {
    isLikelyGraphCommand,
    parseCompactLine,
  } from "./compact-parse.js";

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
   *
   * Each complete `{…}` segment is parsed as:
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
      this.buffer += chunk;
      this.process();
    }

    /**
     * Signal end-of-stream.  Incomplete objects are left in the buffer and
     * can be inspected via `getPending()`.
     */
    end(): void {
      // Intentionally a no-op: partial data is never force-emitted.
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
            const raw = this.buffer.slice(this.segmentStart, i);
            this.buffer = this.buffer.slice(i);
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

      if (this.segmentStart === -1 && this.depth === 0) {
        this.buffer = "";
        this.processingFrom = 0;
      } else {
        this.processingFrom = i;
      }
    }

    private emitParsed(raw: string): void {
      const trimmed = raw.trim();

      // Compact tuple is NOT valid JSON (`{"id", "type", ...}`). Parse it first so we
      // never surface misleading `Expected ':' after property name` from JSON.parse.
      const compact = parseCompactLine(trimmed);
      if (compact) {
        this.onMessage(compact as T, trimmed);
        return;
      }

      try {
        const value = JSON.parse(trimmed) as unknown;
        if (isLikelyGraphCommand(value)) {
          this.onMessage(value as T, trimmed);
          return;
        }
      } catch {
        // fall through
      }

      const err = new Error(
        `Unrecognized JSONL segment: not compact tuple and not single-key graph JSON. Snippet: ${trimmed.slice(0, 160)}${trimmed.length > 160 ? "…" : ""}`,
      );
      if (this.onParseError) {
        this.onParseError(trimmed, err);
      } else {
        throw err;
      }
    }
  }
