/** Compact DSL expressions are parsed, never evaluated as JavaScript. */
type Token = { kind: "literal" | "path" | "operator" | "name" | "end"; text: string; value?: unknown };
type Evaluate = (get: (path: string) => unknown) => unknown;
export class ExpressionError extends Error {}

function tokenize(source: string): Token[] {
  if (source.length > 4096) throw new ExpressionError("表达式超过 4096 字符限制");
  const tokens: Token[] = [];
  let i = 0;
  while (i < source.length) {
    if (/\s/.test(source[i])) { i++; continue; }
    const rest = source.slice(i);
    if (rest.startsWith("${")) {
      const end = source.indexOf("}", i + 2);
      if (end < 0) throw new ExpressionError("数据路径未闭合");
      const path = source.slice(i + 2, end).trim();
      if (!path.startsWith("/")) throw new ExpressionError("表达式只支持绝对 JSON Pointer 路径");
      tokens.push({ kind: "path", text: path }); i = end + 1;
    } else if (source[i] === "'" || source[i] === '"') {
      const quote = source[i++];
      let value = "", closed = false;
      while (i < source.length) {
        const char = source[i++];
        if (char === quote) { closed = true; break; }
        if (char !== "\\") { value += char; continue; }
        const escaped = source[i++];
        const escapes: Record<string, string> = { n: "\n", r: "\r", t: "\t", b: "\b", f: "\f", "\\": "\\", "'": "'", '"': '"', "/": "/" };
        if (escaped === "u" && /^[0-9a-f]{4}$/i.test(source.slice(i, i + 4))) {
          value += String.fromCharCode(parseInt(source.slice(i, i + 4), 16)); i += 4;
        } else if (escaped in escapes) value += escapes[escaped];
        else throw new ExpressionError("字符串转义无效");
      }
      if (!closed) throw new ExpressionError("字符串未闭合");
      tokens.push({ kind: "literal", text: value, value });
    } else {
      const number = rest.match(/^(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?/);
      const name = rest.match(/^[a-zA-Z_][a-zA-Z_0-9]*/);
      const operator = rest.match(/^(?:===|!==|==|!=|>=|<=|&&|\|\||[+\-*/%><!?:(),])/);
      if (number) {
        const value = Number(number[0]);
        if (!Number.isFinite(value)) throw new ExpressionError("数值必须有限");
        tokens.push({ kind: "literal", text: number[0], value }); i += number[0].length;
      }
      else if (name) {
        const literals: Record<string, unknown> = { true: true, false: false, null: null };
        tokens.push(Object.hasOwn(literals, name[0]) ? { kind: "literal", text: name[0], value: literals[name[0]] } : { kind: "name", text: name[0] });
        i += name[0].length;
      } else if (operator) { tokens.push({ kind: "operator", text: operator[0] }); i += operator[0].length; }
      else throw new ExpressionError(`不支持的表达式字符：${source[i]}`);
    }
    if (tokens.length > 512) throw new ExpressionError("表达式过于复杂");
  }
  return [...tokens, { kind: "end", text: "" }];
}

const priority: Record<string, number> = { "||": 1, "&&": 2, "==": 3, "!=": 3, "===": 3, "!==": 3, ">": 4, "<": 4, ">=": 4, "<=": 4, "+": 5, "-": 5, "*": 6, "/": 6, "%": 6 };
function numeric(v: unknown): number {
  if (typeof v !== "number" || !Number.isFinite(v)) throw new ExpressionError("算术运算需要有限数值");
  return v;
}
function binary(op: string, a: unknown, b: unknown): unknown {
  if (op === "+" && (typeof a === "string" || typeof b === "string")) return String(a ?? "") + String(b ?? "");
  if (op === "==" || op === "===") return a === b;
  if (op === "!=" || op === "!==") return a !== b;
  if ([">", "<", ">=", "<="].includes(op)) {
    if (typeof a === "string" && typeof b === "string") return op === ">" ? a > b : op === "<" ? a < b : op === ">=" ? a >= b : a <= b;
    const left = numeric(a), right = numeric(b);
    return op === ">" ? left > right : op === "<" ? left < right : op === ">=" ? left >= right : left <= right;
  }
  const left = numeric(a), right = numeric(b);
  if ((op === "/" || op === "%") && right === 0) throw new ExpressionError("不能除以零");
  const result = op === "+" ? left + right : op === "-" ? left - right : op === "*" ? left * right : op === "/" ? left / right : left % right;
  return numeric(result);
}

export function parseExpression(source: string): { evaluate: Evaluate; paths: string[] } {
  const tokens = tokenize(source), paths = new Set<string>();
  let index = 0, depth = 0;
  const peek = () => tokens[index];
  const consume = (text: string) => {
    if (peek().text !== text) throw new ExpressionError(`表达式缺少 ${text}`);
    index++;
  };
  function atom(): Evaluate {
    const token = tokens[index++];
    if (token.kind === "literal") return () => token.value;
    if (token.kind === "path") { paths.add(token.text); return get => get(token.text) ?? ""; }
    if (token.text === "(" || token.text === "size") {
      if (token.text === "size") consume("(");
      const inner = expression(); consume(")");
      if (token.text === "(") return inner;
      return get => {
        const value = inner(get);
        if (typeof value === "string" || Array.isArray(value)) return value.length;
        if (value && typeof value === "object") return Object.keys(value).length;
        throw new ExpressionError("size() 需要字符串、数组或对象");
      };
    }
    if (["!", "+", "-"].includes(token.text)) {
      const inner = expression(7);
      return get => token.text === "!" ? !inner(get) : (token.text === "-" ? -1 : 1) * numeric(inner(get));
    }
    throw new ExpressionError(`不支持的表达式：${token.text || "意外结束"}`);
  }
  function expression(min = 0): Evaluate {
    if (++depth > 64) throw new ExpressionError("表达式嵌套过深");
    let left = atom();
    while (peek().kind === "operator" && (priority[peek().text] ?? -1) >= min) {
      const op = tokens[index++].text, previous = left, right = expression(priority[op] + 1);
      left = get => {
        const a = previous(get);
        if (op === "&&") return a ? right(get) : a;
        if (op === "||") return a ? a : right(get);
        return binary(op, a, right(get));
      };
    }
    if (min === 0 && peek().text === "?") {
      index++;
      const condition = left, yes = expression(); consume(":"); const no = expression();
      left = get => condition(get) ? yes(get) : no(get);
    }
    depth--;
    return left;
  }
  const evaluate = expression();
  if (peek().kind !== "end") throw new ExpressionError(`表达式包含多余内容：${peek().text}`);
  return { evaluate, paths: [...paths] };
}

export function evaluateExpression(source: string, get: (path: string) => unknown): unknown {
  return parseExpression(source).evaluate(get);
}
