import { parseExpression } from "@genui-sdk/interactions";

const LIMIT = 256;
type Scalar = string | number | boolean | null;

function fieldAt(schema: any, pointer: string): any {
  if (!pointer.startsWith("/")) return undefined;
  let field = schema;
  for (const key of pointer.slice(1).split("/")) {
    const name = key.replace(/~1/g, "/").replace(/~0/g, "~");
    field = field?.properties?.[name] ?? field?.[name];
  }
  return field;
}

function domain(field: any): Scalar[] | undefined {
  if (!field || typeof field !== "object") return undefined;
  let values: unknown[] | undefined;
  if (Array.isArray(field.enum)) values = field.enum;
  else if (field.type === "boolean") values = [false, true];
  else if (field.type === "integer" && Number.isSafeInteger(field.minimum) && Number.isSafeInteger(field.maximum)) {
    const count = field.maximum - field.minimum + 1;
    if (count > 0 && count < LIMIT) values = Array.from({ length: count }, (_, i) => field.minimum + i);
  }
  if (!values?.length || values.length >= LIMIT) return undefined;
  if (!values.every(v => v === null || typeof v === "boolean" ||
    (typeof v === "string" && v.length <= 4096) || (typeof v === "number" && Number.isFinite(v)))) return undefined;
  return [...new Set([...values, null])] as Scalar[];
}

// Enumerate contracts, never preview samples. Evaluation uses the existing safe DSL parser.
export function textBound(content: any, schema: any): { dynamic: boolean; candidates?: string[]; reason: string } {
  const path = typeof content?.path === "string" ? content.path : undefined;
  const expression = typeof content === "string" && content.trim().startsWith("{{") && content.trim().endsWith("}}");
  if (!path && !expression) return { dynamic: false, reason: "static-glyphs" };
  try {
    const parsed = path ? { paths: [path], evaluate: (get: (key: string) => unknown) => get(path) ?? "" }
      : parseExpression(content.trim().slice(2, -2));
    const domains = parsed.paths.map(key => domain(fieldAt(schema, key)));
    if (domains.some(value => !value)) return { dynamic: true, reason: "unbounded-field" };
    let combinations: Record<string, Scalar>[] = [{}];
    for (let i = 0; i < parsed.paths.length; i++) {
      if (combinations.length * domains[i]!.length > LIMIT) return { dynamic: true, reason: "combination-budget" };
      combinations = combinations.flatMap(row => domains[i]!.map(value => ({ ...row, [parsed.paths[i]]: value })));
    }
    const candidates = combinations.map(row => parsed.evaluate(key => row[key]));
    if (candidates.some(v => v !== null && !["string", "number", "boolean", "undefined"].includes(typeof v))) {
      return { dynamic: true, reason: "non-scalar-output" };
    }
    const strings = [...new Set(candidates.map(v => String(v ?? "")))];
    if (strings.some(v => v.length > 4096 || /[\r\n\t]/.test(v))) return { dynamic: true, reason: "multiline-or-long-output" };
    return { dynamic: true, candidates: strings, reason: "finite-contract" };
  } catch {
    return { dynamic: true, reason: "unsupported-expression" };
  }
}
