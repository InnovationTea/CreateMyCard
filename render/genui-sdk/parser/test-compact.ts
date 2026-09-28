/**
 * Unit tests for compact tuple parsing (no LLM).
 * Run: npx tsx test-compact.ts
 */

import {
  isLikelyGraphCommand,
  parseCompactLine,
  parseCompactTupleLine,
} from "./src/compact-parse.ts";
import {
  CREATE_SURFACE_KEY,
  DELETE_SURFACE_KEY,
  UPDATE_DATA_MODEL_KEY,
} from "./src/protocol-v09.ts";

function assert(cond: boolean, msg: string) {
  if (!cond) {
    console.error("FAIL:", msg);
    process.exit(1);
  }
  console.log("ok:", msg);
}

const line1 =
  '{"root", "Card", {"title": "偏好设置", "gap": 12}, ["hint", "save-btn"]}';
const parsed1 = parseCompactTupleLine(line1);
assert(parsed1 !== null, "parses compact line with children");
assert(
  JSON.stringify(parsed1) ===
    JSON.stringify({
      root: {
        type: "Card",
        props: { title: "偏好设置", gap: 12 },
        children: ["hint", "save-btn"],
      },
    }),
  "normalized shape matches graph command",
);

const line2 = '{"hint", "Text", {"content": "保存后立即生效。"}}';
const parsed2 = parseCompactTupleLine(line2);
assert(parsed2 !== null, "parses line without children");
assert(
  (parsed2 as { hint: { children?: string[] } }).hint.children === undefined,
  "no children key when omitted",
);

assert(parseCompactTupleLine('{"a": {"type": "X"}}') === null, "classic JSON rejected by compact parser");

assert(isLikelyGraphCommand({ root: { type: "Card", props: {} } }), "classic graph command detected");

const fullwidthComma = '{"a"，"Text"，{"content": "全角逗号"}}';
const parsedFw = parseCompactTupleLine(fullwidthComma);
assert(parsedFw !== null && (parsedFw as { a: { type: string } }).a.type === "Text", "fullwidth commas between segments");

const propsOnly = '{"root", {"stroke": {"thickness": 1, "fill": "#FF0000"}}}';
const pProps = parseCompactLine(propsOnly);
assert(
  pProps !== null &&
    JSON.stringify(pProps) ===
      JSON.stringify({ root: { props: { stroke: { thickness: 1, fill: "#FF0000" } } } }),
  "props-only patch",
);

const childrenOnly = '{"root", ["a", "b"]}';
const pCh = parseCompactLine(childrenOnly);
assert(
  pCh !== null && JSON.stringify(pCh) === JSON.stringify({ root: { children: ["a", "b"] } }),
  "children-only patch",
);

assert(parseCompactLine === parseCompactTupleLine, "parseCompactTupleLine alias");

// Nested [] inside {} in props (regression: inner ] must not close outer children array)
const nestedArrayInProps =
  '{"root", "Card", {"items": [1, 2], "meta": {"k": 1}}, ["a", "b"]}';
const pNest = parseCompactLine(nestedArrayInProps);
assert(
  pNest !== null &&
    (pNest as { root: { props: { items: number[] } } }).root.props.items.length === 2 &&
    (pNest as { root: { children: string[] } }).root.children.join(",") === "a,b",
  "props object may contain nested arrays without breaking children [] span",
);

// Nested [] inside [] in children list (string elements only by schema; use id-like strings)
const nestedBracketsInChildren = '{"root", ["outer", ["inner"]]}';
assert(
  parseCompactLine(nestedBracketsInChildren) === null,
  "children array must be flat string ids — invalid if nested arrays",
);

const trailingComma =
  '{"root", "Card", {"title": "x",}, ["a",]}';
const pTc = parseCompactLine(trailingComma);
assert(
  pTc !== null &&
    (pTc as { root: { children: string[] } }).root.children.length === 1,
  "tolerates trailing commas in props/children JSON slices",
);

// No type: props + children in one line (any order)
const noTypeBoth =
  '{"room2", {"fill": "#FAF8F3", "gap": 12}, ["room2-info", "room2-book"]}';
const pBoth = parseCompactLine(noTypeBoth);
assert(
  pBoth !== null &&
    JSON.stringify(pBoth) ===
      JSON.stringify({
        room2: {
          props: { fill: "#FAF8F3", gap: 12 },
          children: ["room2-info", "room2-book"],
        },
      }),
  "incremental line with props and children without type",
);

const noTypeBothReversed =
  '{"room2", ["x", "y"], {"fill": "#fff"}}';
const pRev = parseCompactLine(noTypeBothReversed);
assert(
  pRev !== null &&
    (pRev as { room2: { props: { fill: string }; children: string[] } }).room2.children.join(
      ",",
    ) === "x,y" &&
    (pRev as { room2: { props: { fill: string } } }).room2.props.fill === "#fff",
  "props and children may appear in either order",
);

const typeOnly = '{"cta", "Button"}';
const pTypeOnly = parseCompactLine(typeOnly);
assert(
  pTypeOnly !== null &&
    JSON.stringify(pTypeOnly) === JSON.stringify({ cta: { type: "Button" } }),
  "type only (no props, no children)",
);

const idOnly = '{"solo"}';
const pId = parseCompactLine(idOnly);
assert(
  pId !== null && JSON.stringify(pId) === JSON.stringify({ solo: {} }),
  "id-only line",
);

// Minimal GenUI: deleteSurface, createSurface, updateDataModel, updateComponent
const del = parseCompactLine('{"~main"}') as Record<string, unknown>;
assert(
  del !== null && del[DELETE_SURFACE_KEY] && (del[DELETE_SURFACE_KEY] as { surfaceId: string }).surfaceId === "main",
  "deleteSurface ~",
);

const cs = parseCompactLine(
  '{"@s1", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor":"#0A59F7"}}',
) as Record<string, unknown>;
assert(
  cs !== null &&
    cs[CREATE_SURFACE_KEY] &&
    (cs[CREATE_SURFACE_KEY] as { surfaceId: string; theme: { primaryColor: string } }).surfaceId === "s1" &&
    (cs[CREATE_SURFACE_KEY] as { theme: { primaryColor: string } }).theme.primaryColor === "#0A59F7",
  "createSurface @ + catalog + theme",
);

const dm = parseCompactLine('{"s1", "/user/name", "Ada"}') as Record<string, unknown>;
assert(
  dm !== null &&
    dm[UPDATE_DATA_MODEL_KEY] &&
    (dm[UPDATE_DATA_MODEL_KEY] as { path: string; value: string }).path === "/user/name" &&
    (dm[UPDATE_DATA_MODEL_KEY] as { value: string }).value === "Ada",
  "updateDataModel path + value",
);

const u5 = parseCompactLine('{"s1", "n1", "Text", {"content":"x"}}') as { n1: { type: string } };
assert(u5 !== null && u5.n1 && u5.n1.type === "Text", "updateComponent 5-tuple");

// Implicit braceless theme + props (sloppy model output)
const csImplicit = parseCompactLine(
  '{"@s2", "https://xxx/specification/ohos/extended_catalog.json", "primaryColor":"#FF0A59F7"}',
) as Record<string, unknown>;
assert(
  csImplicit !== null &&
    csImplicit[CREATE_SURFACE_KEY] &&
    (csImplicit[CREATE_SURFACE_KEY] as { surfaceId: string; theme: { primaryColor: string } }).surfaceId ===
      "s2" &&
    (csImplicit[CREATE_SURFACE_KEY] as { theme: { primaryColor: string } }).theme.primaryColor === "#FF0A59F7",
  "createSurface @ + catalog + implicit theme object",
);

const rootImplicit = parseCompactLine(
  '{"demo_surf", "root", "Column", "space":12, "width":"matchParent", "constraintSize":"maxWidth":336, "children":["hero"]}',
) as { root: { type: string; props: Record<string, unknown>; children: string[] } };
assert(
  rootImplicit !== null &&
    rootImplicit.root &&
    rootImplicit.root.type === "Extended.Column" &&
    rootImplicit.root.props.space === 12 &&
    (rootImplicit.root.props.constraintSize as Record<string, unknown>).maxWidth === 336 &&
    rootImplicit.root.children.length === 1 &&
    rootImplicit.root.children[0] === "hero",
  "updateComponent with implicit props + nested implicit maxWidth",
);

console.log("\ncompact-parse tests passed ✅\n");
