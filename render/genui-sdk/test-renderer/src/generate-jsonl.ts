/**
 * generate-jsonl.ts
 *
 * Reads output/component-schema.json (produced by extract-schema.ts),
 * classifies components into containers (hasChildren) and leaves, then
 * generates per-container-type test JSONL files.
 *
 * For each container type C:
 *   - One JSONL file wrapping all test cases in a root Column
 *   - Each test case nests a different container type inside C
 *   - Leaf children count is controlled by --min-leaves / --max-leaves
 *
 * Structural constraints respected:
 *   - Extended.Tabs children must be Extended.TabContent (leaf)
 *   - Extended.Grid children must be Extended.GridRow
 *   - Extended.GridRow only appears inside Extended.Grid (not tested as outer)
 *
 * Output: output/test-<ComponentName>.jsonl   (one per testable container)
 *
 * Run:  npx tsx src/generate-jsonl.ts
 *       npx tsx src/generate-jsonl.ts --seed 42
 *       npx tsx src/generate-jsonl.ts --seed 42 --min-leaves 1 --max-leaves 5
 */

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";

// Re-use the types from extract-schema (they're also in the JSON, but TS helps)
import type { GenRule, PropDef, ComponentDef, SchemaOutput } from "./extract-schema";

// ── Seeded PRNG (xoshiro128**) for reproducibility ──────────────────────────

function makeRng(seed: number) {
  let s0 = seed | 0 || 1;
  let s1 = (seed * 1597334677) | 0 || 2;
  let s2 = (seed * 3812015801) | 0 || 3;
  let s3 = (seed * 2868466484) | 0 || 4;
  function next(): number {
    const result = Math.imul(s1 * 5, 7) >>> 0;
    const t = s1 << 9;
    s2 ^= s0;
    s3 ^= s1;
    s1 ^= s2;
    s0 ^= s3;
    s2 ^= t;
    s3 = (s3 << 11) | (s3 >>> 21);
    return (result >>> 0) / 4294967296;
  }
  return {
    /** Random float in [0, 1) */
    random: next,
    /** Random int in [min, max] inclusive */
    int(min: number, max: number): number {
      return Math.floor(next() * (max - min + 1)) + min;
    },
    /** Random float in [min, max] */
    float(min: number, max: number): number {
      return next() * (max - min) + min;
    },
    /** Pick one element */
    pick<T>(arr: readonly T[]): T {
      return arr[Math.floor(next() * arr.length)]!;
    },
    /** true with the given probability */
    chance(p: number): boolean {
      return next() < p;
    },
  };
}

type Rng = ReturnType<typeof makeRng>;

// ── Random string generators ────────────────────────────────────────────────

const LOREM = [
  "天气晴朗", "今日推荐", "数据概览", "操作成功", "加载中",
  "确认提交", "取消", "返回", "查看详情", "更多选项",
  "搜索结果", "系统通知", "版本更新", "设置", "帮助",
  "Trending", "Dashboard", "Submit", "Cancel", "Refresh",
  "Analytics", "Overview", "Settings", "Profile", "Explore",
];

const BUTTON_LABELS = [
  "提交", "确认", "取消", "保存", "删除", "刷新", "登录", "注册",
  "Submit", "Confirm", "Cancel", "Save", "Delete", "Refresh", "Login",
];

const CARD_TITLES = [
  "系统信息", "用户中心", "数据面板", "订单详情", "消息通知",
  "System Info", "User Center", "Dashboard", "Order Detail", "Notifications",
];

const IMAGE_URLS = [
  "https://picsum.photos/200/300",
  "https://picsum.photos/300/200",
  "https://picsum.photos/150/150",
  "https://picsum.photos/400/300",
  "https://picsum.photos/300/300",
];

const WEB_URLS = [
  "https://example.com",
  "https://developer.mozilla.org",
  "https://vuejs.org",
  "https://github.com/",
];

const FONT_FAMILIES = ["sans-serif", "serif", "monospace", "Arial", "Helvetica"];

const GRID_TEMPLATES = ["1fr 1fr", "1fr 1fr 1fr", "1fr 2fr", "2fr 1fr 1fr", "1fr 1fr 1fr 1fr"];

function randomString(rng: Rng, hint: string): string {
  switch (hint) {
    case "sentence":
      return rng.pick(LOREM) + "·" + rng.pick(LOREM);
    case "buttonLabel":
      return rng.pick(BUTTON_LABELS);
    case "cardTitle":
      return rng.pick(CARD_TITLES);
    case "cardDescription":
      return rng.pick(LOREM) + "，" + rng.pick(LOREM);
    case "imageUrl":
      return rng.pick(IMAGE_URLS);
    case "webUrl":
      return rng.pick(WEB_URLS);
    case "iconUrl":
      return rng.pick(IMAGE_URLS);
    case "fontFamily":
      return rng.pick(FONT_FAMILIES);
    case "gridTemplate":
      return rng.pick(GRID_TEMPLATES);
    case "placeholder":
      return "请输入…";
    case "inputText":
      return rng.pick(LOREM);
    case "radioValue":
      return `option-${rng.int(1, 10)}`;
    case "radioGroup":
    case "checkboxGroup":
      return `group-${rng.int(1, 5)}`;
    case "tabTitle":
      return rng.pick(["首页", "推荐", "消息", "我的", "Tab " + rng.int(1, 8)]);
    case "selectValue":
      return rng.pick(["选项A", "选项B", "选项C", "Option X", "Option Y"]);
    case "navTitle":
      return rng.pick(["导航", "Navigation", "首页", "详情页"]);
    case "text":
    default:
      return rng.pick(LOREM);
  }
}

function randomColor(rng: Rng): string {
  const r = rng.int(0, 255).toString(16).padStart(2, "0");
  const g = rng.int(0, 255).toString(16).padStart(2, "0");
  const b = rng.int(0, 255).toString(16).padStart(2, "0");
  // ~50% chance to use #RRGGBB, ~50% to use 0xAARRGGBB (matching the schema's dual format)
  if (rng.chance(0.5)) {
    return `#${r}${g}${b}`.toUpperCase();
  }
  const a = rng.int(128, 255).toString(16).padStart(2, "0");
  return `0x${a}${r}${g}${b}`.toUpperCase();
}

// ── Value generation from GenRule ────────────────────────────────────────────

function generateValue(rng: Rng, rule: GenRule): unknown {
  switch (rule.type) {
    case "enum":
      return rng.pick(rule.values ?? []);

    case "number":
      return rng.int(rule.min ?? 0, rule.max ?? 100);

    case "float": {
      const v = rng.float(rule.min ?? 0, rule.max ?? 1);
      return Math.round(v * 100) / 100;
    }

    case "string":
      return randomString(rng, rule.hint ?? "text");

    case "boolean":
      return rng.chance(0.5);

    case "color":
      return randomColor(rng);

    case "object": {
      if (!rule.fields) return {};
      const obj: Record<string, unknown> = {};
      for (const [k, subRule] of Object.entries(rule.fields)) {
        // Include ~70% of sub-fields to add variety
        if (rng.chance(0.7)) {
          obj[k] = generateValue(rng, subRule);
        }
      }
      return obj;
    }

    case "array":
      // Special handling: for selectOptions we generate a small array
      if (rule.hint === "selectOptions") {
        const count = rng.int(2, 5);
        return Array.from({ length: count }, (_, i) => ({
          value: `opt-${i + 1}`,
          icon: rng.chance(0.3) ? rng.pick(IMAGE_URLS) : undefined,
        })).map((o) => {
          const clean: Record<string, unknown> = { value: o.value };
          if (o.icon) clean.icon = o.icon;
          return clean;
        });
      }
      // childIds — handled externally
      return [];

    case "oneOf":
      if (rule.options && rule.options.length > 0) {
        return generateValue(rng, rng.pick(rule.options));
      }
      return null;

    case "numberOrFillContainer":
      return rng.chance(0.4)
        ? "matchParent"
        : rng.int(rule.min ?? 10, rule.max ?? 400);

    case "numberOrString":
      return rng.int(rule.min ?? 1, rule.max ?? 6);

    case "numberOrEdges":
      if (rng.chance(0.5)) {
        // uniform number
        return rng.int(rule.min ?? 0, rule.max ?? 32);
      } else {
        // per-edge object
        if (!rule.fields) return rng.int(rule.min ?? 0, rule.max ?? 32);
        const obj: Record<string, unknown> = {};
        for (const [k, subRule] of Object.entries(rule.fields)) {
          obj[k] = generateValue(rng, subRule);
        }
        return obj;
      }

    case "numberOrCorners":
      if (rng.chance(0.5)) {
        return rng.int(rule.min ?? 0, rule.max ?? 24);
      } else {
        if (!rule.fields) return rng.int(rule.min ?? 0, rule.max ?? 24);
        const obj: Record<string, unknown> = {};
        for (const [k, subRule] of Object.entries(rule.fields)) {
          obj[k] = generateValue(rng, subRule);
        }
        return obj;
      }

    case "shadowObject": {
      if (!rule.fields) return {};
      const obj: Record<string, unknown> = {};
      // radius is required
      if (rule.fields.radius) {
        obj.radius = generateValue(rng, rule.fields.radius);
      }
      // others are optional
      for (const [k, subRule] of Object.entries(rule.fields)) {
        if (k === "radius") continue;
        if (rng.chance(0.5)) {
          obj[k] = generateValue(rng, subRule);
        }
      }
      return obj;
    }

    default:
      return null;
  }
}

// ── Generate props + styles for a component ──────────────────────────────────

function generateProps(
  rng: Rng,
  componentDef: ComponentDef,
  commonStyles: Record<string, PropDef>,
  /** Probability [0,1] that each optional prop is included */
  propInclusion: number,
  /** Probability [0,1] that each optional style is included */
  styleInclusion: number,
  /** Probability [0,1] that a common style is included */
  commonStyleInclusion: number,
): Record<string, unknown> {
  const props: Record<string, unknown> = {};

  // Component-specific props
  for (const [key, def] of Object.entries(componentDef.props)) {
    if (key === "childrenIf" || key === "childrenElse") continue; // skip child arrays
    if (def.required || rng.chance(propInclusion)) {
      props[key] = generateValue(rng, def.rule);
    }
  }

  // Styles (component-specific + common)
  const styles: Record<string, unknown> = {};

  for (const [key, def] of Object.entries(componentDef.styles)) {
    if (rng.chance(styleInclusion)) {
      styles[key] = generateValue(rng, def.rule);
    }
  }

  for (const [key, def] of Object.entries(commonStyles)) {
    if (rng.chance(commonStyleInclusion)) {
      styles[key] = generateValue(rng, def.rule);
    }
  }

  if (Object.keys(styles).length > 0) {
    props.styles = styles;
  }

  return props;
}

// ── Tree node & serialisation ────────────────────────────────────────────────

interface TreeNode {
  id: string;
  type: string;
  props: Record<string, unknown>;
  childIds: string[];
}

/**
 * Serialize one node into the compact tuple format:
 *   {"<id>", "<type>", {props}, ["child", ...]}
 */
function nodeToCompactLine(node: TreeNode): string {
  const parts: string[] = [JSON.stringify(node.id), JSON.stringify(node.type)];

  const propsObj = { ...node.props };
  delete propsObj.component;
  delete propsObj.id;

  if (Object.keys(propsObj).length > 0) {
    parts.push(JSON.stringify(propsObj));
  }

  if (node.childIds.length > 0) {
    if (Object.keys(propsObj).length === 0) {
      parts.push("{}");
    }
    parts.push(JSON.stringify(node.childIds));
  }

  return `{${parts.join(", ")}}`;
}

// ── Component classification ────────────────────────────────────────────────

/** Sub-component types that only make sense inside a specific parent. */
const SUB_COMPONENT_TYPES = new Set(["Extended.GridRow"]);

/** Container types that require specific child types. */
const STRUCTURAL_CHILDREN: Record<string, string> = {
  "Extended.Tabs": "Extended.TabContent",
  "Extended.Grid": "Extended.GridRow",
};

interface Classification {
  /** All components with hasChildren === true */
  containers: string[];
  /** All components with hasChildren === false */
  leaves: string[];
  /** Containers suitable as outer test targets (excludes sub-components like GridRow) */
  testableContainers: string[];
  componentMap: Map<string, ComponentDef>;
}

function classifyComponents(schema: SchemaOutput): Classification {
  const componentMap = new Map<string, ComponentDef>();
  const containers: string[] = [];
  const leaves: string[] = [];

  for (const c of schema.components) {
    componentMap.set(c.name, c);
    if (c.hasChildren) {
      containers.push(c.name);
    } else {
      leaves.push(c.name);
    }
  }

  const testableContainers = containers.filter((c) => !SUB_COMPONENT_TYPES.has(c));

  return { containers, leaves, testableContainers, componentMap };
}

// ── ID generator ────────────────────────────────────────────────────────────

class IdGen {
  private counter = 0;
  nextId(prefix: string): string {
    return `${prefix}-${++this.counter}`;
  }
}

// ── Test case metadata ──────────────────────────────────────────────────────

interface TestCaseInfo {
  level: "L0" | "L1";
  label: string;
  outerContainer: string;
  nestedContainer: string | null;
  componentsUsed: string[];
}

// ── Leaf generation helpers ─────────────────────────────────────────────────

function generateRandomLeaves(
  rng: Rng,
  leaves: string[],
  componentMap: Map<string, ComponentDef>,
  commonStyles: Record<string, PropDef>,
  count: number,
  idGen: IdGen,
): TreeNode[] {
  const nodes: TreeNode[] = [];
  for (let i = 0; i < count; i++) {
    const leafType = rng.pick(leaves);
    const leafDef = componentMap.get(leafType)!;
    const short = leafType.replace("Extended.", "").toLowerCase();
    const id = idGen.nextId(short);
    const props = generateProps(rng, leafDef, commonStyles, 0.6, 0.3, 0.05);
    nodes.push({ id, type: leafType, props, childIds: [] });
  }
  return nodes;
}

// ── Populated container (respects structural constraints) ───────────────────

/**
 * Generate a container node filled with appropriate children.
 * - Tabs → TabContent children
 * - Grid → GridRow → leaves
 * - Others → random leaves
 */
function generatePopulatedContainer(
  containerType: string,
  rng: Rng,
  cl: Classification,
  commonStyles: Record<string, PropDef>,
  leafCount: number,
  idGen: IdGen,
): TreeNode[] {
  const { leaves, componentMap } = cl;
  const containerDef = componentMap.get(containerType)!;
  const short = containerType.replace("Extended.", "").toLowerCase();
  const containerId = idGen.nextId(short);
  const containerProps = generateProps(rng, containerDef, commonStyles, 0.5, 0.25, 0.05);
  const containerNode: TreeNode = {
    id: containerId,
    type: containerType,
    props: containerProps,
    childIds: [],
  };
  const allNodes: TreeNode[] = [containerNode];

  if (containerType === "Extended.Tabs") {
    // TabContent is a leaf — just generate TabContent children
    const tcDef = componentMap.get("Extended.TabContent");
    if (tcDef) {
      const count = Math.max(2, leafCount);
      for (let i = 0; i < count; i++) {
        const tcId = idGen.nextId("tabcontent");
        const tcProps = generateProps(rng, tcDef, commonStyles, 0.7, 0.3, 0.05);
        allNodes.push({ id: tcId, type: "Extended.TabContent", props: tcProps, childIds: [] });
        containerNode.childIds.push(tcId);
      }
    }
  } else if (containerType === "Extended.Grid") {
    // Grid → GridRow → leaves
    const grDef = componentMap.get("Extended.GridRow");
    if (grDef) {
      const grId = idGen.nextId("gridrow");
      const grProps = generateProps(rng, grDef, commonStyles, 0.3, 0.15, 0.02);
      const grNode: TreeNode = { id: grId, type: "Extended.GridRow", props: grProps, childIds: [] };
      allNodes.push(grNode);
      containerNode.childIds.push(grId);
      const leafNodes = generateRandomLeaves(rng, leaves, componentMap, commonStyles, leafCount, idGen);
      for (const ln of leafNodes) {
        grNode.childIds.push(ln.id);
        allNodes.push(ln);
      }
    }
  } else {
    // Regular container → random leaves
    const leafNodes = generateRandomLeaves(rng, leaves, componentMap, commonStyles, leafCount, idGen);
    for (const ln of leafNodes) {
      containerNode.childIds.push(ln.id);
      allNodes.push(ln);
    }
  }

  return allNodes;
}

// ── Single L0 test case: container with leaves only (no nested container) ───

function generateL0TestCase(
  containerType: string,
  rng: Rng,
  cl: Classification,
  commonStyles: Record<string, PropDef>,
  minLeaves: number,
  maxLeaves: number,
  idGen: IdGen,
): { nodes: TreeNode[]; info: TestCaseInfo } {
  const { leaves, componentMap } = cl;
  const allNodes: TreeNode[] = [];

  const containerDef = componentMap.get(containerType)!;
  const outerShort = containerType.replace("Extended.", "").toLowerCase();
  const outerId = idGen.nextId(outerShort);
  const containerProps = generateProps(rng, containerDef, commonStyles, 0.5, 0.25, 0.05);
  const containerNode: TreeNode = { id: outerId, type: containerType, props: containerProps, childIds: [] };
  allNodes.push(containerNode);

  // Determine where children attach (respect Grid structural constraint)
  let childTarget = containerNode;
  if (containerType === "Extended.Grid") {
    const grDef = componentMap.get("Extended.GridRow");
    if (grDef) {
      const grId = idGen.nextId("gridrow");
      const grProps = generateProps(rng, grDef, commonStyles, 0.3, 0.15, 0.02);
      const grNode: TreeNode = { id: grId, type: "Extended.GridRow", props: grProps, childIds: [] };
      allNodes.push(grNode);
      containerNode.childIds.push(grId);
      childTarget = grNode;
    }
  }

  if (containerType === "Extended.Tabs") {
    // Tabs → TabContent only
    const tcDef = componentMap.get("Extended.TabContent");
    if (tcDef) {
      const count = rng.int(Math.max(2, minLeaves), Math.max(2, maxLeaves));
      for (let i = 0; i < count; i++) {
        const tcId = idGen.nextId("tabcontent");
        const tcProps = generateProps(rng, tcDef, commonStyles, 0.7, 0.3, 0.05);
        allNodes.push({ id: tcId, type: "Extended.TabContent", props: tcProps, childIds: [] });
        containerNode.childIds.push(tcId);
      }
    }
  } else {
    const leafCount = rng.int(minLeaves, maxLeaves);
    const leafNodes = generateRandomLeaves(rng, leaves, componentMap, commonStyles, leafCount, idGen);
    for (const ln of leafNodes) {
      childTarget.childIds.push(ln.id);
      allNodes.push(ln);
    }
  }

  const shortOuter = containerType.replace("Extended.", "");
  const componentsUsed = collectComponentTypes(allNodes);

  return {
    nodes: allNodes,
    info: {
      level: "L0",
      label: `L0: ${shortOuter} (leaves only)`,
      outerContainer: containerType,
      nestedContainer: null,
      componentsUsed,
    },
  };
}

// ── Single L1 test case: outer container nesting an inner container ────────────

function generateL1TestCase(
  outerType: string,
  nestedType: string,
  rng: Rng,
  cl: Classification,
  commonStyles: Record<string, PropDef>,
  minLeaves: number,
  maxLeaves: number,
  idGen: IdGen,
): { nodes: TreeNode[]; info: TestCaseInfo } {
  const { leaves, componentMap } = cl;
  const allNodes: TreeNode[] = [];

  // Outer container
  const outerDef = componentMap.get(outerType)!;
  const outerShort = outerType.replace("Extended.", "").toLowerCase();
  const outerId = idGen.nextId(outerShort);
  const outerProps = generateProps(rng, outerDef, commonStyles, 0.5, 0.25, 0.05);
  const outerNode: TreeNode = { id: outerId, type: outerType, props: outerProps, childIds: [] };
  allNodes.push(outerNode);

  // Determine where children attach (respect Grid structural constraint)
  let childTarget = outerNode;
  if (outerType === "Extended.Grid") {
    const grDef = componentMap.get("Extended.GridRow");
    if (grDef) {
      const grId = idGen.nextId("gridrow");
      const grProps = generateProps(rng, grDef, commonStyles, 0.3, 0.15, 0.02);
      const grNode: TreeNode = { id: grId, type: "Extended.GridRow", props: grProps, childIds: [] };
      allNodes.push(grNode);
      outerNode.childIds.push(grId);
      childTarget = grNode;
    }
  }

  // Leaves before nested container
  const leavesBefore = rng.int(0, Math.max(1, Math.floor(maxLeaves / 2)));
  const beforeNodes = generateRandomLeaves(rng, leaves, componentMap, commonStyles, leavesBefore, idGen);
  for (const ln of beforeNodes) {
    childTarget.childIds.push(ln.id);
    allNodes.push(ln);
  }

  // Nested container (populated with its own children)
  const nestedLeafCount = rng.int(minLeaves, maxLeaves);
  const nestedNodes = generatePopulatedContainer(nestedType, rng, cl, commonStyles, nestedLeafCount, idGen);
  childTarget.childIds.push(nestedNodes[0]!.id);
  allNodes.push(...nestedNodes);

  // Leaves after nested container
  const leavesAfter = rng.int(0, Math.max(1, Math.floor(maxLeaves / 2)));
  const afterNodes = generateRandomLeaves(rng, leaves, componentMap, commonStyles, leavesAfter, idGen);
  for (const ln of afterNodes) {
    childTarget.childIds.push(ln.id);
    allNodes.push(ln);
  }

  const shortOuter = outerType.replace("Extended.", "");
  const shortNested = nestedType.replace("Extended.", "");
  const componentsUsed = collectComponentTypes(allNodes);

  return {
    nodes: allNodes,
    info: {
      level: "L1",
      label: `L1: ${shortOuter} ▸ ${shortNested}`,
      outerContainer: outerType,
      nestedContainer: nestedType,
      componentsUsed,
    },
  };
}

// ── Helper: collect unique component types from a node list ─────────────────

function collectComponentTypes(nodes: TreeNode[]): string[] {
  return [...new Set(nodes.map((n) => n.type))].sort();
}

// ── Full test file for one container type ───────────────────────────────────

function generateContainerTestFile(
  containerType: string,
  rng: Rng,
  schema: SchemaOutput,
  cl: Classification,
  minLeaves: number,
  maxLeaves: number,
  l0Count: number,
): { nodes: TreeNode[]; testCases: TestCaseInfo[] } {
  const idGen = new IdGen();
  const { testableContainers } = cl;
  const allNodes: TreeNode[] = [];
  const testCases: TestCaseInfo[] = [];

  // Root Column wrapper
  const rootNode: TreeNode = {
    id: "root",
    type: "Extended.Column",
    props: { space: 16, styles: { width: "matchParent" } },
    childIds: [],
  };
  allNodes.push(rootNode);

  // File title
  const titleId = idGen.nextId("title");
  allNodes.push({
    id: titleId,
    type: "Extended.Text",
    props: {
      content: `Container Tests: ${containerType}`,
      styles: { fontSize: 22, fontWeight: "700", fontColor: "#0f172a" },
    },
    childIds: [],
  });
  rootNode.childIds.push(titleId);

  const shortOuter = containerType.replace("Extended.", "");

  // ── L0: container with leaves only (repeated l0Count times) ─────────────
  for (let li = 0; li < l0Count; li++) {
    const l0LabelId = idGen.nextId("label");
    allNodes.push({
      id: l0LabelId,
      type: "Extended.Text",
      props: {
        content: `L0 #${li + 1}: ${shortOuter} (leaves only)`,
        styles: { fontSize: 14, fontWeight: "500", fontColor: "#64748b" },
      },
      childIds: [],
    });
    rootNode.childIds.push(l0LabelId);

    const l0 = generateL0TestCase(containerType, rng, cl, schema.commonStyles, minLeaves, maxLeaves, idGen);
    rootNode.childIds.push(l0.nodes[0]!.id);
    allNodes.push(...l0.nodes);
    l0.info.label = `L0 #${li + 1}: ${shortOuter} (leaves only)`;
    testCases.push(l0.info);
  }

  // ── L1: container nesting each testable container type ──────────────────
  if (containerType === "Extended.Tabs") {
    // Tabs can only hold TabContent (leaf), so no meaningful L1
  } else {
    for (const nestedType of testableContainers) {
      const shortNested = nestedType.replace("Extended.", "");

      // Section label
      const labelId = idGen.nextId("label");
      allNodes.push({
        id: labelId,
        type: "Extended.Text",
        props: {
          content: `L1: ${shortOuter} ▸ ${shortNested}`,
          styles: { fontSize: 14, fontWeight: "500", fontColor: "#64748b" },
        },
        childIds: [],
      });
      rootNode.childIds.push(labelId);

      // Test case
      const l1 = generateL1TestCase(
        containerType,
        nestedType,
        rng,
        cl,
        schema.commonStyles,
        minLeaves,
        maxLeaves,
        idGen,
      );
      rootNode.childIds.push(l1.nodes[0]!.id);
      allNodes.push(...l1.nodes);
      testCases.push(l1.info);
    }
  }

  return { nodes: allNodes, testCases };
}

// ── CLI ──────────────────────────────────────────────────────────────────────

function parseCliArg(args: string[], flag: string, fallback: number): number {
  const idx = args.indexOf(flag);
  return idx >= 0 ? parseInt(args[idx + 1] ?? String(fallback), 10) : fallback;
}

function main() {
  const args = process.argv.slice(2);
  const seed = parseCliArg(args, "--seed", Date.now());
  const minLeaves = parseCliArg(args, "--min-leaves", 1);
  const maxLeaves = parseCliArg(args, "--max-leaves", 3);
  const l0Count = parseCliArg(args, "--l0-count", 5);

  console.log(`  🎲 Seed: ${seed}  Leaves per container: ${minLeaves}–${maxLeaves}  L0 cases per container: ${l0Count}\n`);

  const outDir = resolve(__dirname, "../output");
  mkdirSync(outDir, { recursive: true });

  // Load schema
  const schemaPath = resolve(outDir, "component-schema.json");
  let schema: SchemaOutput;
  try {
    schema = JSON.parse(readFileSync(schemaPath, "utf-8")) as SchemaOutput;
  } catch {
    console.error("  ❌ component-schema.json not found. Run extract-schema.ts first.");
    process.exit(1);
  }

  // Classify
  const cl = classifyComponents(schema);
  console.log(`  📦 Containers (${cl.containers.length}): ${cl.containers.map((c) => c.replace("Extended.", "")).join(", ")}`);
  console.log(`  🍃 Leaves     (${cl.leaves.length}): ${cl.leaves.map((c) => c.replace("Extended.", "")).join(", ")}`);
  console.log(`  🧪 Testable   (${cl.testableContainers.length}): ${cl.testableContainers.map((c) => c.replace("Extended.", "")).join(", ")}\n`);

  // Generate one file per testable container
  const manifest: Array<{
    container: string;
    file: string;
    nodes: number;
    l0Cases: number;
    l1Cases: number;
    testCases: TestCaseInfo[];
  }> = [];

  for (const containerType of cl.testableContainers) {
    const rng = makeRng(seed);
    const { nodes, testCases } = generateContainerTestFile(containerType, rng, schema, cl, minLeaves, maxLeaves, l0Count);

    const safeName = containerType.replace("Extended.", "");
    const fileName = `test-${safeName}.jsonl`;
    const filePath = resolve(outDir, fileName);

    const lines = nodes.map(nodeToCompactLine);
    writeFileSync(filePath, lines.join("\n") + "\n", "utf-8");

    const l0Cases = testCases.filter((tc) => tc.level === "L0").length;
    const l1Cases = testCases.filter((tc) => tc.level === "L1").length;
    manifest.push({ container: containerType, file: fileName, nodes: nodes.length, l0Cases, l1Cases, testCases });

    console.log(`  ✅ ${fileName.padEnd(24)} ${String(nodes.length).padStart(4)} nodes, L0: ${l0Cases}, L1: ${l1Cases}`);
  }

  // Write manifest
  const manifestPath = resolve(outDir, "test-manifest.json");
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), "utf-8");
  console.log(`\n  📋 Wrote ${manifestPath}`);

  // Summary
  const totalNodes = manifest.reduce((s, m) => s + m.nodes, 0);
  const totalL0 = manifest.reduce((s, m) => s + m.l0Cases, 0);
  const totalL1 = manifest.reduce((s, m) => s + m.l1Cases, 0);
  console.log(`\n  📊 Total: ${manifest.length} files, ${totalNodes} nodes, L0: ${totalL0}, L1: ${totalL1} (${totalL0 + totalL1} test cases)`);

  // Print first few lines of first file as sample
  const sampleFile = manifest[0];
  if (sampleFile) {
    const samplePath = resolve(outDir, sampleFile.file);
    const sampleLines = readFileSync(samplePath, "utf-8").split("\n").filter(Boolean);
    console.log(`\n  📄 Sample (${sampleFile.file}), first 5 lines:\n`);
    for (const line of sampleLines.slice(0, 5)) {
      console.log(`    ${line}`);
    }
    if (sampleLines.length > 5) {
      console.log(`    … (${sampleLines.length - 5} more)`);
    }
  }
}

main();
