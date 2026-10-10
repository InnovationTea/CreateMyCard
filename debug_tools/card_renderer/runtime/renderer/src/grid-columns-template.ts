/**
 * Safe interpolation for **Extended.Grid** `columnsTemplate` only.
 * Supports `{{ ... }}` blocks that reference `$__WindowBreakpoint` with `==`, `||`,
 * parentheses, nested `?:`, and single-quoted string literals (no escapes).
 */

export const GRID_WINDOW_BREAKPOINT_TOKEN = "$__WindowBreakpoint";

type Tok =
  | { k: "bp" }
  | { k: "str"; v: string }
  | { k: "op"; v: "==" | "||" | "?" | ":" | "(" | ")" };

function tokenize(input: string): Tok[] | null {
  let i = 0;
  const out: Tok[] = [];
  const n = input.length;
  const BP = GRID_WINDOW_BREAKPOINT_TOKEN;
  while (i < n) {
    const c = input[i]!;
    if (c === " " || c === "\t" || c === "\n" || c === "\r") {
      i++;
      continue;
    }
    if (input.startsWith(BP, i)) {
      out.push({ k: "bp" });
      i += BP.length;
      continue;
    }
    if (c === "(") {
      out.push({ k: "op", v: "(" });
      i++;
      continue;
    }
    if (c === ")") {
      out.push({ k: "op", v: ")" });
      i++;
      continue;
    }
    if (c === "?") {
      out.push({ k: "op", v: "?" });
      i++;
      continue;
    }
    if (c === ":") {
      out.push({ k: "op", v: ":" });
      i++;
      continue;
    }
    if (c === "=" && input[i + 1] === "=") {
      out.push({ k: "op", v: "==" });
      i += 2;
      continue;
    }
    if (c === "|" && input[i + 1] === "|") {
      out.push({ k: "op", v: "||" });
      i += 2;
      continue;
    }
    if (c === "'") {
      i++;
      const start = i;
      while (i < n && input[i] !== "'") i++;
      if (i >= n) return null;
      out.push({ k: "str", v: input.slice(start, i) });
      i++;
      continue;
    }
    return null;
  }
  return out;
}

class MustacheParser {
  private pos = 0;

  constructor(
    private readonly toks: Tok[],
    private readonly bp: string,
  ) {}

  private peek(): Tok | undefined {
    return this.toks[this.pos];
  }

  private eatStr(): string {
    const t = this.peek();
    if (!t || t.k !== "str") throw new SyntaxError("expected string");
    this.pos++;
    return t.v;
  }

  /** String result: either a quoted literal or `cond ? a : b` (nested). */
  parseValue(): string {
    const t = this.peek();
    if (t?.k === "str") {
      return this.eatStr();
    }
    const cond = this.parseOrBool();
    const q = this.peek();
    if (!q || q.k !== "op" || q.v !== "?") throw new SyntaxError("expected ?");
    this.pos++;
    const yes = this.parseValue();
    const c = this.peek();
    if (!c || c.k !== "op" || c.v !== ":") throw new SyntaxError("expected :");
    this.pos++;
    const no = this.parseValue();
    return cond ? yes : no;
  }

  parseOrBool(): boolean {
    let v = this.parseEqBool();
    while (this.pos < this.toks.length) {
      const t = this.peek();
      if (t?.k === "op" && t.v === "||") {
        this.pos++;
        v = v || this.parseEqBool();
      } else {
        break;
      }
    }
    return v;
  }

  parseEqBool(): boolean {
    const t = this.peek();
    if (t?.k === "op" && t.v === "(") {
      this.pos++;
      const inner = this.parseOrBool();
      const c = this.peek();
      if (!c || c.k !== "op" || c.v !== ")") throw new SyntaxError("expected )");
      this.pos++;
      return inner;
    }
    if (t?.k !== "bp") throw new SyntaxError("expected breakpoint or ( )");
    this.pos++;
    const eq = this.peek();
    if (!eq || eq.k !== "op" || eq.v !== "==") throw new SyntaxError("expected ==");
    this.pos++;
    const s = this.eatStr();
    return this.bp === s;
  }

  atEnd(): boolean {
    return this.pos >= this.toks.length;
  }
}

function parseOneMustache(inner: string, windowBreakpoint: string): string | null {
  const toks = tokenize(inner);
  if (toks === null) return null;
  const p = new MustacheParser(toks, windowBreakpoint);
  try {
    const v = p.parseValue();
    if (!p.atEnd()) return null;
    return v;
  } catch {
    return null;
  }
}

/**
 * Replace each `{{ ... }}` segment that references {@link GRID_WINDOW_BREAKPOINT_TOKEN}.
 * Other segments and strings are left unchanged. Failed parses keep the original `{{ … }}` text.
 */
export function interpolateGridColumnsTemplate(template: string, windowBreakpoint: string): string {
  const bp = String(windowBreakpoint);
  const token = GRID_WINDOW_BREAKPOINT_TOKEN;
  return template.replace(/\{\{([\s\S]*?)\}\}/g, (full, inner: string) => {
    if (typeof inner !== "string" || !inner.includes(token)) {
      return full;
    }
    const got = parseOneMustache(inner.trim(), bp);
    return got !== null ? got : full;
  });
}
