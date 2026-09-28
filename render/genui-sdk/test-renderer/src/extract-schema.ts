/**
 * extract-schema.ts
 *
 * Dynamically reads and parses prompt/src/prompt-assets/ui_schema.ts,
 * extracts every component definition (name, props, styles) and the
 * Common Styles section, infers generation rules for each field, and
 * writes the result to output/component-schema.json.
 *
 * Run:  npx tsx src/extract-schema.ts
 */

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";

// ── Output types ─────────────────────────────────────────────────────────────

export interface GenRule {
  type:
    | "enum"
    | "number"
    | "float"
    | "string"
    | "boolean"
    | "color"
    | "object"
    | "array"
    | "oneOf"
    | "numberOrFillContainer"
    | "numberOrString"
    | "numberOrEdges"
    | "numberOrCorners"
    | "shadowObject";
  values?: (string | number | boolean)[];
  min?: number;
  max?: number;
  hint?: string;
  fields?: Record<string, GenRule>;
  options?: GenRule[];
}

export interface PropDef {
  rule: GenRule;
  required?: boolean;
}

export interface ComponentDef {
  name: string;
  hasChildren: boolean;
  props: Record<string, PropDef>;
  styles: Record<string, PropDef>;
}

export interface SchemaOutput {
  components: ComponentDef[];
  commonStyles: Record<string, PropDef>;
}

// ── Brace-balanced helpers ───────────────────────────────────────────────────

/**
 * Starting from `start` (an opening `{` or `[`), return the index *after*
 * the matching closing brace/bracket.  Respects double-quoted strings.
 */
function findBalancedEnd(text: string, start: number): number {
  const open = text[start];
  const close = open === "{" ? "}" : open === "[" ? "]" : undefined;
  if (!close) return -1;
  let depth = 0;
  let inStr = false;
  let esc = false;
  for (let i = start; i < text.length; i++) {
    const c = text[i];
    if (inStr) {
      if (esc) { esc = false; continue; }
      if (c === "\\") { esc = true; continue; }
      if (c === '"') inStr = false;
      continue;
    }
    if (c === '"') { inStr = true; continue; }
    if (c === open) depth++;
    if (c === close) { depth--; if (depth === 0) return i + 1; }
  }
  return -1;
}

/** Return { content (without outer braces), end } or null. */
function extractBracedBlock(text: string, searchFrom: number): { content: string; end: number } | null {
  const idx = text.indexOf("{", searchFrom);
  if (idx < 0) return null;
  const end = findBalancedEnd(text, idx);
  if (end < 0) return null;
  return { content: text.slice(idx + 1, end - 1), end };
}

// ── Field-line splitter ──────────────────────────────────────────────────────

interface FieldLine {
  key: string;
  optional: boolean;
  typeExpr: string;
}

/**
 * Given the inner text of a `{ ... }` block (one level), split it into
 * individual `key: typeExpr` entries, correctly handling nested `{}`/`[]`
 * and `|` continuation lines.
 */
function splitFields(blockContent: string): FieldLine[] {
  const results: FieldLine[] = [];
  let pos = 0;
  const text = blockContent;

  while (pos < text.length) {
    // skip whitespace & commas
    while (pos < text.length && /[\s,]/.test(text[pos]!)) pos++;
    if (pos >= text.length) break;

    // Match:  key?: ...  or  "key": ...  or  key: ...
    const lineMatch = text.slice(pos).match(/^"?([a-zA-Z_$][\w$]*)"?\s*(\?)?\s*:\s*/);
    if (!lineMatch) {
      // skip to next line
      const nl = text.indexOf("\n", pos);
      pos = nl < 0 ? text.length : nl + 1;
      continue;
    }

    const key = lineMatch[1]!;
    const optional = lineMatch[2] === "?";
    pos += lineMatch[0].length;

    // Collect the type expression — may span brace blocks or | continuations
    let typeExpr = "";

    while (pos < text.length) {
      const ch = text[pos]!;

      if (ch === "{" || ch === "[") {
        const end = findBalancedEnd(text, pos);
        if (end < 0) { pos = text.length; break; }
        typeExpr += text.slice(pos, end);
        pos = end;
        continue;
      }

      if (ch === ",") { pos++; break; }

      if (ch === "\n") {
        // peek: if next non-space char is `|`, it's a continuation
        let peek = pos + 1;
        while (peek < text.length && text[peek] === " ") peek++;
        if (peek < text.length && text[peek] === "|") {
          typeExpr += " ";
          pos = peek;
          continue;
        }
        pos++;
        break;
      }

      typeExpr += ch;
      pos++;
    }

    typeExpr = typeExpr.trim();
    if (typeExpr.length > 0) {
      results.push({ key, optional, typeExpr });
    }
  }
  return results;
}

// ── Type expression → GenRule ────────────────────────────────────────────────

function typeExprToRule(expr: string, key: string): GenRule {
  const e = expr.trim();

  // ── enum of literals separated by `|` ──
  if (e.includes("|") && !e.startsWith("{") && !e.startsWith("[") && !e.includes("{\n")) {
    // Check this isn't a union with an object branch
    if (!e.includes("{")) {
      const parts = e.split("|").map(s => s.trim()).filter(Boolean);
      const values: (string | number | boolean)[] = [];
      for (const p of parts) {
        if (p.startsWith('"') && p.endsWith('"')) values.push(p.slice(1, -1));
        else if (/^-?\d+(\.\d+)?$/.test(p)) values.push(Number(p));
        else if (p === "true") values.push(true);
        else if (p === "false") values.push(false);
        else values.push(p);
      }
      if (values.every(v => typeof v === "string" || typeof v === "number" || typeof v === "boolean")) {
        return { type: "enum", values };
      }
    }
  }

  if (e === "boolean") return { type: "boolean" };
  if (e === "number") return inferNumberRule(key);
  if (e === "string") return inferStringRule(key);
  if (e === "string[]") return { type: "array", hint: "childIds" };

  // object literal { ... }
  if (e.startsWith("{") && !e.endsWith("[]")) {
    const inner = e.slice(1, e.lastIndexOf("}")).trim();
    if (inner.length === 0) return { type: "object", fields: {} };
    const fields = splitFields(inner);
    const fieldRules: Record<string, GenRule> = {};
    for (const f of fields) {
      fieldRules[f.key] = typeExprToRule(f.typeExpr, f.key);
    }
    return { type: "object", fields: fieldRules };
  }

  // array of objects { ... }[]
  if (e.endsWith("[]") && e.includes("{")) {
    const objPart = e.slice(0, e.lastIndexOf("[]")).trim();
    if (objPart.startsWith("{")) {
      const inner = objPart.slice(1, objPart.lastIndexOf("}")).trim();
      const fields = splitFields(inner);
      const fieldRules: Record<string, GenRule> = {};
      for (const f of fields) {
        fieldRules[f.key] = typeExprToRule(f.typeExpr, f.key);
      }
      return { type: "array", hint: "objectArray", fields: fieldRules };
    }
  }

  // specific literal string like "Extended.Text"
  if (e.startsWith('"') && e.endsWith('"')) {
    return { type: "enum", values: [e.slice(1, -1)] };
  }

  // fallback
  return { type: "string", hint: key };
}

/** Infer a sensible number rule from the field name. */
function inferNumberRule(key: string): GenRule {
  const k = key.toLowerCase();
  if (k.includes("fontsize") || k === "size" || k === "iconsize") return { type: "number", min: 10, max: 36 };
  if (k.includes("maxfontsize")) return { type: "number", min: 12, max: 48 };
  if (k.includes("maxlines") || k === "maxlines") return { type: "number", min: 1, max: 10 };
  if (k.includes("maxlength")) return { type: "number", min: 1, max: 500 };
  if (k === "space" || k === "gap") return { type: "number", min: 0, max: 24 };
  if (k.includes("gap")) return { type: "number", min: 0, max: 20 };
  if (k.includes("width") || k.includes("height")) return { type: "number", min: 10, max: 400 };
  if (k.includes("strokewidth")) return { type: "number", min: 1, max: 6 };
  if (k.includes("radius")) return { type: "number", min: 0, max: 30 };
  if (k === "startmargin" || k === "endmargin") return { type: "number", min: 0, max: 32 };
  if (k === "offsetx" || k === "offsety" || k === "dx" || k === "dy") return { type: "number", min: -20, max: 20 };
  if (k.includes("index") || k === "tableindex" || k === "currentindex" || k === "selected")
    return { type: "number", min: 0, max: 5 };
  if (k === "value") return { type: "number", min: 0, max: 100 };
  if (k === "total") return { type: "number", min: 1, max: 100 };
  if (k.includes("aspectr")) return { type: "float", min: 0.3, max: 3 };
  if (k.includes("fontscale") || k.includes("minfontscale") || k.includes("maxfontscale"))
    return { type: "float", min: 0.5, max: 2 };
  if (k === "flexshrink") return { type: "number", min: 0, max: 3 };
  if (k === "layoutweight") return { type: "number", min: 0, max: 5 };
  return { type: "number", min: 0, max: 100 };
}

/** Infer a sensible string rule from the field name. */
function inferStringRule(key: string): GenRule {
  const k = key.toLowerCase();
  if (k.includes("color") || k === "fill") return { type: "color" };
  if (k.includes("image") || k.includes("src") || k === "icon" || k === "selectedsrc")
    return { type: "string", hint: "imageUrl" };
  if (k === "url") return { type: "string", hint: "webUrl" };
  if (k === "content") return { type: "string", hint: "sentence" };
  if (k === "label") return { type: "string", hint: "buttonLabel" };
  if (k === "title") return { type: "string", hint: "cardTitle" };
  if (k === "description") return { type: "string", hint: "cardDescription" };
  if (k === "placeholder") return { type: "string", hint: "placeholder" };
  if (k === "text") return { type: "string", hint: "inputText" };
  if (k === "value") return { type: "string", hint: "selectValue" };
  if (k === "group") return { type: "string", hint: "group" };
  if (k === "family") return { type: "string", hint: "fontFamily" };
  if (k.includes("template")) return { type: "string", hint: "gridTemplate" };
  return { type: "string", hint: key };
}

// ── Component block extraction ───────────────────────────────────────────────

function extractComponentBlocks(schemaText: string): Array<{ name: string; propsBlock: string }> {
  const results: Array<{ name: string; propsBlock: string }> = [];

  // Each component starts with **Extended.XXX**
  const headerRe = /\*\*(Extended\.\w+)\*\*/g;
  const headers: Array<{ name: string; index: number }> = [];
  let m: RegExpExecArray | null;
  while ((m = headerRe.exec(schemaText)) !== null) {
    headers.push({ name: m[1]!, index: m.index });
  }

  for (let i = 0; i < headers.length; i++) {
    const start = headers[i]!.index;
    const end = i + 1 < headers.length ? headers[i + 1]!.index : schemaText.length;
    const block = schemaText.slice(start, end);

    const propsIdx = block.indexOf("Props:");
    if (propsIdx < 0) continue;

    const braced = extractBracedBlock(block, propsIdx);
    if (!braced) continue;

    results.push({ name: headers[i]!.name, propsBlock: braced.content });
  }

  return results;
}

/** Parse a single component's Props: { ... } block into a ComponentDef. */
function parseComponentBlock(raw: { name: string; propsBlock: string }): ComponentDef {
  const fields = splitFields(raw.propsBlock);

  const props: Record<string, PropDef> = {};
  const styles: Record<string, PropDef> = {};
  let hasChildren = false;

  for (const f of fields) {
    // Skip meta fields
    if (f.key === "id") continue;
    if (f.key === "component") continue;

    // children → marks hasChildren
    if (f.key === "children") {
      hasChildren = true;
      continue;
    }

    // childrenIf / childrenElse are treated as regular props (Extended.If)
    if (f.key === "childrenIf" || f.key === "childrenElse") {
      props[f.key] = { rule: { type: "array", hint: "childIds" }, required: false };
      continue;
    }

    // styles block → parse recursively into the styles map
    if (f.key === "styles") {
      if (f.typeExpr.startsWith("{")) {
        const inner = f.typeExpr.slice(1, f.typeExpr.lastIndexOf("}")).trim();
        if (inner.length > 0) {
          const styleFields = splitFields(inner);
          for (const sf of styleFields) {
            styles[sf.key] = { rule: typeExprToRule(sf.typeExpr, sf.key), required: false };
          }
        }
      }
      continue;
    }

    // Regular prop
    props[f.key] = {
      rule: typeExprToRule(f.typeExpr, f.key),
      required: !f.optional,
    };
  }

  return { name: raw.name, hasChildren, props, styles };
}

// ── Common Styles parser ─────────────────────────────────────────────────────

function parseCommonStyles(schemaText: string): Record<string, PropDef> {
  const marker = "## Common Styles";
  const idx = schemaText.indexOf(marker);
  if (idx < 0) return {};

  const section = schemaText.slice(idx + marker.length).trim();
  const result: Record<string, PropDef> = {};

  // Each entry starts at column 0 with  `word: ...`
  const entryRe = /^([a-zA-Z_$][\w$]*)\s*:\s*/gm;
  const entries: Array<{ key: string; index: number; matchEnd: number }> = [];
  let em: RegExpExecArray | null;
  while ((em = entryRe.exec(section)) !== null) {
    const key = em[1]!;
    const afterColon = section.slice(em.index + em[0].length).trimStart();
    // A real style definition starts with: `"`, `{`, `[`, a digit, or a type
    // keyword (number, boolean, string).  Commentary lines like `eg: 字符串`
    // or `offsetY: 可选，数值` start with Chinese prose and are skipped.
    const isTypeExpr =
      /^["{\[\d]/.test(afterColon) ||
      /^(number|boolean|string)\b/.test(afterColon);
    if (!isTypeExpr) continue;
    entries.push({ key, index: em.index, matchEnd: em.index + em[0].length });
  }

  for (let i = 0; i < entries.length; i++) {
    const entry = entries[i]!;
    const nextStart = i + 1 < entries.length
      ? entries[i + 1]!.index
      : section.length;
    let rawExpr = section.slice(entry.matchEnd, nextStart).trim();

    // Keep only up to first line that starts with `eg:` or `- `
    const lines = rawExpr.split("\n");
    const cleanLines: string[] = [];
    for (const ln of lines) {
      const stripped = ln.trim();
      if (stripped.startsWith("eg:") || stripped.startsWith("- ")) break;
      cleanLines.push(ln);
    }
    rawExpr = cleanLines.join("\n").trim();
    // Strip inline // comments
    rawExpr = rawExpr.replace(/\/\/.*$/gm, "").trim();

    result[entry.key] = { rule: parseCommonStyleExpr(rawExpr, entry.key) };
  }

  return result;
}

function parseCommonStyleExpr(expr: string, key: string): GenRule {
  const e = expr.trim();

  // Union: number | { edges }  (margin, padding, borderRadius)
  if (/^number\s*\|/.test(e) && e.includes("{")) {
    const objStart = e.indexOf("{");
    const objEnd = findBalancedEnd(e, objStart);
    const objStr = objEnd > 0 ? e.slice(objStart, objEnd) : "{}";
    const inner = objStr.slice(1, -1).trim();
    const fields = splitFields(inner);
    const fieldRules: Record<string, GenRule> = {};
    for (const f of fields) fieldRules[f.key] = typeExprToRule(f.typeExpr, f.key);

    const k = key.toLowerCase();
    if (k === "borderradius") return { type: "numberOrCorners", min: 0, max: 24, fields: fieldRules };
    if (k === "margin" || k === "padding") return { type: "numberOrEdges", min: 0, max: 32, fields: fieldRules };
    return { type: "numberOrString", min: 1, max: 6, hint: key };
  }

  // number | string  (borderWidth)
  if (/^number\s*\|\s*string$/.test(e)) {
    return { type: "numberOrString", min: 1, max: 6, hint: key };
  }

  // "matchParent"  literal for width/height
  if (e.includes('"matchParent"')) {
    return { type: "numberOrFillContainer", min: 10, max: 400, values: ["matchParent"] };
  }

  // enum | { object }  union  (backgroundImageSizeWithStyle)
  if (e.includes("|") && e.includes("{")) {
    const objStart = e.indexOf("{");
    const objEnd = findBalancedEnd(e, objStart);
    const enumPart = e.slice(0, e.lastIndexOf("|", objStart)).trim();
    const objStr = objEnd > 0 ? e.slice(objStart, objEnd) : "{}";
    const enumRule = typeExprToRule(enumPart, key);
    const objRule = typeExprToRule(objStr, key);
    return { type: "oneOf", options: [enumRule, objRule] };
  }

  // plain enum with |
  if (e.includes("|") && !e.includes("{")) {
    return typeExprToRule(e, key);
  }

  // Object block (shadow, constraintSize)
  if (e.startsWith("{")) {
    if (key === "shadow") {
      const inner = e.slice(1, e.lastIndexOf("}")).trim();
      const fields = splitFields(inner);
      const fieldRules: Record<string, GenRule> = {};
      for (const f of fields) fieldRules[f.key] = typeExprToRule(f.typeExpr, f.key);
      return { type: "shadowObject", fields: fieldRules };
    }
    return typeExprToRule(e, key);
  }

  if (e === "boolean") return { type: "boolean" };
  if (e === "number") return inferNumberRule(key);
  if (e === "string") return inferStringRule(key);

  return { type: "string", hint: key };
}

// ── Main ─────────────────────────────────────────────────────────────────────

function main() {
  const outDir = resolve(__dirname, "../output");
  mkdirSync(outDir, { recursive: true });

  const schemaPath = resolve(__dirname, "../../prompt/src/prompt-assets/ui_schema.ts");
  const src = readFileSync(schemaPath, "utf-8");
  console.log(`  Read ui_schema.ts (${src.length} chars)`);

  // Extract the template literal content between backticks
  const tplMatch = src.match(/\x60([\s\S]*)\x60/);
  if (!tplMatch) {
    console.error("  Could not find template literal in ui_schema.ts");
    process.exit(1);
  }
  const schemaText = tplMatch[1]!;

  // ── Parse components from the AVAILABLE COMPONENTS section ────────────
  const rawBlocks = extractComponentBlocks(schemaText);
  console.log(`  Found ${rawBlocks.length} component blocks in schema text`);

  const components: ComponentDef[] = rawBlocks.map(parseComponentBlock);

  // ── Parse common styles ──────────────────────────────────────────────
  const commonStyles = parseCommonStyles(schemaText);
  console.log(`  Found ${Object.keys(commonStyles).length} common styles in schema text`);

  // ── Write output ─────────────────────────────────────────────────────
  const output: SchemaOutput = { components, commonStyles };
  const outPath = resolve(outDir, "component-schema.json");
  writeFileSync(outPath, JSON.stringify(output, null, 2), "utf-8");
  console.log(`\n  Wrote ${outPath}`);
  console.log(`     ${components.length} components, ${Object.keys(commonStyles).length} common styles`);

  // Print summary
  console.log("\n  Component summary:");
  for (const c of components) {
    const pKeys = Object.keys(c.props);
    const sKeys = Object.keys(c.styles);
    console.log(
      `    ${c.name.padEnd(28)} props: ${String(pKeys.length).padStart(2)}  styles: ${String(sKeys.length).padStart(2)}  children: ${c.hasChildren ? "yes" : "no "}  propKeys: [${pKeys.join(", ")}]`,
    );
  }
  console.log("\n  Common styles:");
  for (const [k, v] of Object.entries(commonStyles)) {
    console.log(`    ${k.padEnd(32)} rule.type: ${v.rule.type}`);
  }
}

main();
