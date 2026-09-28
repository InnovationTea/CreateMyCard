/**
 * UIGraph test
 *
 * Run:  npx tsx graph/test.ts            (mock only)
 *       npx tsx graph/test.ts --live     (mock + real LLM stream)
 */

import { config } from "dotenv";
import { resolve } from "node:path";
import { CREATE_SURFACE_CMD_KEY, UIGraph, UPDATE_DATA_MODEL_CMD_KEY, uitreeJson } from "@genui-sdk/graph";
import { JsonlStreamParser } from "@genui-sdk/parser";
import { streamGenUI } from "@genui-sdk/llm-client";

config({ path: resolve(__dirname, "../../.env") });
const apiKey = process.env.VITE_OPENROUTER_API_KEY ?? "";

// ── Helpers ──────────────────────────────────────────────────────────────────

function pass(msg: string) { console.log(`  ✅ ${msg}`); }
function fail(msg: string) { console.error(`  ❌ ${msg}`); process.exitCode = 1; }

function assert(condition: boolean, msg: string) {
  condition ? pass(msg) : fail(msg);
}

// ── Mock commands (Example 2 from output_format.ts) ──────────────────────────

const MOCK_COMMANDS: Array<Record<string, unknown>> = [
  {
    root: {
      type: "Card",
      props: { title: "生成式UI介绍", description: "一篇关于生成式UI的博客", justifyContent: "center" },
      children: ["post-title", "post-excerpt"],
    },
  },
  {
    "post-title": {
      type: "Text",
      props: { content: "如何构建现代化GenUI应用" },
    },
  },
  {
    "post-excerpt": {
      type: "Card",
      props: {
        title: "最新前端技术趋势",
        description: "在这篇文章中，我们将探讨最新的前端技术趋势...",
        justifyContent: "center",
      },
      children: ["trend1", "trend2"],
    },
  },
  {
    trend1: { type: "Text", props: { content: "趋势1：AI与GenUI的结合" } },
  },
  {
    trend2: { type: "Text", props: { content: "趋势2：GenUI的自动化设计" } },
  },
];

// ── Test 1: basic graph construction ─────────────────────────────────────────

function testMockBuild() {
  console.log("\n【测试 1】使用 mock 指令构建 UI 树\n");

  const graph = new UIGraph();
  for (const cmd of MOCK_COMMANDS) graph.applyCommand(cmd);

  // Node count
  assert(graph.size === 5, `共 5 个节点 (实际 ${graph.size})`);

  // Root
  const root = graph.getRoot();
  assert(root?.id === "root", `根节点 id = "root" (实际 ${root?.id})`);
  assert(root?.type === "Card", `根节点 type = "Card"`);
  assert(root?.parent === null, `根节点 parent = null`);
  assert(
    JSON.stringify(root?.children) === JSON.stringify(["post-title", "post-excerpt"]),
    `根节点 children = ["post-title", "post-excerpt"]`,
  );

  // Child parent links
  const postTitle = graph.getNode("post-title");
  assert(postTitle?.parent === "root", `post-title.parent = "root"`);
  assert(postTitle?.type === "Text", `post-title.type = "Text"`);

  const postExcerpt = graph.getNode("post-excerpt");
  assert(postExcerpt?.parent === "root", `post-excerpt.parent = "root"`);
  assert(postExcerpt?.type === "Card", `post-excerpt.type = "Card" (嵌套 Card)`);
  assert(
    JSON.stringify(postExcerpt?.children) === JSON.stringify(["trend1", "trend2"]),
    `post-excerpt.children = ["trend1", "trend2"]`,
  );

  const trend1 = graph.getNode("trend1");
  assert(trend1?.parent === "post-excerpt", `trend1.parent = "post-excerpt"`);

  const trend2 = graph.getNode("trend2");
  assert(trend2?.parent === "post-excerpt", `trend2.parent = "post-excerpt"`);

  // No pending children after all commands applied
  assert(
    graph.getPendingChildIds().length === 0,
    `无未完成子节点 (pending = ${graph.getPendingChildIds().length})`,
  );

  // uitreeJson output
  console.log("\n  uitreeJson 输出:\n");
  console.log(uitreeJson(graph, 2));
}

// ── Test 1b: v0.9 updateDataModel + active surface ───────────────────────────

function testUpdateDataModelCommands() {
  console.log("\n【测试 1b】__updateDataModel 与 createSurface 清理 data model\n");

  const graph = new UIGraph();
  graph.applyCommand({
    [UPDATE_DATA_MODEL_CMD_KEY]: { surfaceId: "main", path: "/title", value: "T0" },
  });
  assert(graph.getDataModelValue("main", "/title") === "T0", "path 写入 data model");
  assert(graph.getActiveSurfaceId() === null, "createSurface 前无 active surface");

  graph.applyCommand({ [CREATE_SURFACE_CMD_KEY]: { surfaceId: "main" } });
  assert(graph.getActiveSurfaceId() === "main", "createSurface 后 active surface");
  assert(graph.getDataModelValue("main", "/title") === undefined, "createSurface 清空 data model");

  graph.applyCommand({
    [UPDATE_DATA_MODEL_CMD_KEY]: { surfaceId: "main", path: "/title", value: "T1" },
  });
  assert(graph.getDataModelValue("main", "/title") === "T1", "createSurface 后可再次写入");

  graph.applyCommand({ root: { type: "Extended.Column", children: [] } });
  graph.applyCommand({ [CREATE_SURFACE_CMD_KEY]: { surfaceId: "other" } });
  assert(graph.getDataModelValue("main", "/title") === undefined, "再次 createSurface 清空全部 surface 数据");
}

/** v0.9 `updateDataModel` with `path: "/"` + whole object — bindings use `/key` (not `//key`). */
function testDataModelRootObjectPath() {
  console.log("\n【测试 1c】data model 根路径 `/` 下挂整对象，子路径 `/a`、`/a/b` 可解析\n");

  const graph = new UIGraph();
  graph.applyCommand({ [CREATE_SURFACE_CMD_KEY]: { surfaceId: "w" } });
  graph.applyCommand({
    [UPDATE_DATA_MODEL_CMD_KEY]: {
      surfaceId: "w",
      path: "/",
      value: {
        district: "萧山区",
        maxTemp: 26,
        nested: { x: 1 },
      },
    },
  });
  assert(graph.getDataModelValue("w", "/district") === "萧山区", "根对象 / → /district");
  assert(graph.getDataModelValue("w", "/maxTemp") === 26, "根对象 / → /maxTemp");
  assert(graph.getDataModelValue("w", "/nested/x") === 1, "根对象 / → /nested/x");
  assert(graph.getDataModelValue("w", "/missing") === undefined, "缺失键返回 undefined");

  graph.applyCommand({
    [UPDATE_DATA_MODEL_CMD_KEY]: { surfaceId: "w", path: "/a", value: "leaf" },
  });
  assert(graph.getDataModelValue("w", "/a") === "leaf", "与根并存时仍可按精确键命中 /a");
}

// ── Test 2: integration with parser ──────────────────────────────────────────

function testParserIntegration() {
  console.log("\n【测试 2】Parser + UIGraph 集成（字符级流式模拟）\n");

  const rawStream =
    '{"root":{"type":"Card","props":{"title":"天气预报","description":"实时天气信息和7天预报","justifyContent":"center"},"children":["weather-summary","weather-details"]}}\n' +
    '{"weather-summary":{"type":"Text","props":{"content":"今日天气：晴，气温 15°C - 25°C，东南风 2-3级。"}}}\n' +
    '{"weather-details":{"type":"Text","props":{"content":"未来三天预报：明天多云转晴，后天有小雨，大后天转晴。"}}}';

  const graph = new UIGraph();
  const parser = new JsonlStreamParser<Record<string, unknown>>({
    onMessage: (obj, _raw) => graph.applyCommand(obj),
    onParseError: (raw, err) => console.warn("parse error:", err, raw),
  });

  // Feed char-by-char (worst-case streaming scenario)
  for (const ch of rawStream) parser.push(ch);
  parser.end();

  assert(graph.size === 3, `共 3 个节点 (实际 ${graph.size})`);
  const root = graph.getRoot();
  assert(root?.id === "root", `根节点 id = "root"`);
  assert(graph.getNode("weather-summary")?.parent === "root", `weather-summary.parent = "root"`);
  assert(graph.getNode("weather-details")?.parent === "root", `weather-details.parent = "root"`);

  console.log("\n  uitreeJson 输出:\n");
  console.log(uitreeJson(graph, 2));
}

// ── Test 2a: extra `}` after a complete object (model slop) ─────────────────

function testParserExtraTrailingCloseBraces() {
  console.log("\n【测试 2a】顶层 JSON 后多余 `}`：并入同一段并仍能解析\n");

  const rawStream =
    '{"root":{"type":"Text","props":{"content":"hello"}}}}\n' +
    '{"a":{"type":"Text","props":{"content":"second"}}}\n' +
    '{"b", "Text", {"content":"compact"}}}}';

  const graph = new UIGraph();
  let parseErrors = 0;
  const parser = new JsonlStreamParser<Record<string, unknown>>({
    onMessage: (obj, _raw) => graph.applyCommand(obj),
    onParseError: () => {
      parseErrors++;
    },
  });

  for (const ch of rawStream) parser.push(ch);
  parser.end();

  assert(parseErrors === 0, "多余 `}` 不应导致解析失败");
  assert(graph.size === 3, `共 3 个节点 (实际 ${graph.size})`);
  assert(graph.getRoot()?.id === "root", "根节点 root");
  assert(graph.getNode("a")?.props.content === "second", "第二条经典 JSON");
  assert(graph.getNode("b")?.props.content === "compact", "compact 行多余 `}`");

  console.log("\n  uitreeJson 输出:\n");
  console.log(uitreeJson(graph, 2));
}

// ── Test 2a2: extra `}` before `]` inside JSON (…}}]… repair) ───────────────
//
// 仅当 `}}]` 对应「多写的一个对象闭合括号」时适用；`["a"}}]` 这类错误不在此模式内。

function testParserExtraBraceBeforeBracket() {
  console.log("\n【测试 2a2】数组闭合前多写 `}`（}}] → }] 且仅当修复后可 parse）\n");

  const valid =
    '{"svc":{"type":"Text","props":{"y":2},"children":[{"id":"a","type":"Text","props":{}}]}}';
  const bad =
    '{"svc":{"type":"Text","props":{"y":2},"children":[{"id":"a","type":"Text","props":{}}}]}}';

  const received: unknown[] = [];
  let parseErrors = 0;
  const parser = new JsonlStreamParser<Record<string, unknown>>({
    onMessage: (obj) => {
      received.push(obj);
    },
    onParseError: () => {
      parseErrors++;
    },
  });

  for (const ch of bad) parser.push(ch);
  parser.end();

  assert(parseErrors === 0, "`}}]` 修复后应解析成功");
  assert(received.length === 1, `应发出 1 条消息 (实际 ${received.length})`);
  assert(
    JSON.stringify(received[0]) === JSON.stringify(JSON.parse(valid)),
    "修复结果与合法 JSON 一致",
  );

  console.log("\n  解析结果:\n");
  console.log(JSON.stringify(received[0], null, 2));
}

// ── Test 2b: compact tuple format ───────────────────────────────────────────

function testCompactParserIntegration() {
  console.log("\n【测试 2b】Compact 元组格式 + Parser + UIGraph\n");

  const rawStream =
    '{"root", "Card", {"title": "天气预报", "justifyContent": "center"}, ["weather-summary", "weather-details"]}\n' +
    '{"weather-summary", "Text", {"content": "今日天气：晴。"}}\n' +
    '{"weather-details", "Text", {"content": "未来三天预报。"}}';

  const graph = new UIGraph();
  const parser = new JsonlStreamParser<Record<string, unknown>>({
    onMessage: (obj, _raw) => graph.applyCommand(obj),
    onParseError: (raw, err) => console.warn("parse error:", err, raw),
  });

  for (const ch of rawStream) parser.push(ch);
  parser.end();

  assert(graph.size === 3, `共 3 个节点 (实际 ${graph.size})`);
  const root = graph.getRoot();
  assert(root?.id === "root", `根节点 id = "root"`);
  assert(graph.getNode("weather-summary")?.parent === "root", `weather-summary.parent = "root"`);
  assert(graph.getNode("weather-details")?.parent === "root", `weather-details.parent = "root"`);

  console.log("\n  uitreeJson 输出:\n");
  console.log(uitreeJson(graph, 2));
}

// ── Test 2c: incremental props / children / fresh root ──────────────────────

function testIncrementalPatches() {
  console.log("\n【测试 2c】多轮增量：props / children / 新 root\n");

  const graph = new UIGraph();
  graph.applyCommand({
    root: {
      type: "Card",
      props: { title: "T0" },
      children: ["a", "b"],
    },
  });
  graph.applyCommand({ a: { type: "Text", props: { content: "A" } } });
  graph.applyCommand({ b: { type: "Text", props: { content: "B" } } });

  assert(graph.size === 3, `首轮 3 节点 (实际 ${graph.size})`);

  graph.applyCommand({ root: { props: { title: "T1" } } });
  assert(graph.getNode("root")?.props.title === "T1", "props 合并");
  assert(graph.size === 3, "props 合并不改变节点数");

  graph.applyCommand({ root: { children: ["a"] } });
  assert(graph.getNode("b") === null, "删除子节点 b 及其已从树移除");
  assert(graph.size === 2, `删除后 2 节点 (实际 ${graph.size})`);

  graph.applyCommand({
    root: {
      type: "Card",
      props: { title: "全新" },
      children: [],
    },
  });
  assert(graph.size === 1, `root 带 type 重建后仅 root (实际 ${graph.size})`);
  assert(graph.getRoot()?.props.title === "全新", "新 root 标题");

  console.log("\n  uitreeJson:\n");
  console.log(uitreeJson(graph, 2));
}

// ── Test 2d: compact incremental lines through JsonlStreamParser ─────────────

function testIncrementalCompactStream() {
  console.log("\n【测试 2d】流式解析 compact 增量行（props / children）\n");

  const rawStream =
    '{"root", "Card", {"title": "X"}, ["a"]}\n' +
    '{"a", "Text", {"content": "hi"}}\n' +
    '{"root", {"title": "patched"}}\n' +
    '{"root", []}';

  const graph = new UIGraph();
  const parser = new JsonlStreamParser<Record<string, unknown>>({
    onMessage: (obj, _raw) => graph.applyCommand(obj),
    onParseError: (raw, err) => console.warn("parse error:", err, raw),
  });

  for (const ch of rawStream) parser.push(ch);
  parser.end();

  assert(graph.size === 1, `children 置空后仅保留 root (实际 ${graph.size})`);
  assert(graph.getNode("a") === null, "子节点 a 已删除");
  assert(graph.getRoot()?.props.title === "patched", "root 标题已合并");
  assert(JSON.stringify(graph.getRoot()?.children) === "[]", "root.children 为空数组");

  console.log("\n  uitreeJson:\n");
  console.log(uitreeJson(graph, 2));
}

// ── Test 2e: full node without children key preserves existing children ─────

function testFullNodeOmittedChildrenPreserves() {
  console.log("\n【测试 2e】完整节点省略 children：保留已有子节点\n");

  const graph = new UIGraph();
  graph.applyCommand({
    sec: {
      type: "Card",
      props: { title: "S" },
      children: ["c1", "c2"],
    },
  });
  graph.applyCommand({ c1: { type: "Text", props: { content: "1" } } });
  graph.applyCommand({ c2: { type: "Text", props: { content: "2" } } });

  graph.applyCommand({
    sec: {
      type: "Card",
      props: { title: "Updated", description: "patched" },
    },
  });

  assert(graph.size === 3, `仍 3 节点 (实际 ${graph.size})`);
  assert(
    JSON.stringify(graph.getNode("sec")?.children) === JSON.stringify(["c1", "c2"]),
    "sec.children 未变",
  );
  assert(graph.getNode("c1") !== null, "c1 仍在图中");
  assert(graph.getNode("sec")?.props.title === "Updated", "props 已替换");
}

// ── Test 3: live LLM stream (optional, --live flag) ──────────────────────────

async function testLiveStream() {
  console.log("\n【测试 3】真实 LLM 流 + Parser + UIGraph\n");

  if (!apiKey) {
    fail("缺少 VITE_OPENROUTER_API_KEY — 请在仓库根目录 .env 中配置");
    return;
  }

  const userPrompt = process.argv[3] ?? "生成一个包含标题和两段正文的博客卡片";
  console.log(`  用户输入: "${userPrompt}"\n`);

  const graph = new UIGraph();
  let commandCount = 0;

  const parser = new JsonlStreamParser<Record<string, unknown>>({
    onMessage(obj, _raw) {
      commandCount++;
      const id = Object.keys(obj)[0];
      // Print on its own line — no raw token noise alongside it
      console.log(`  [${commandCount}] → ${id}`);
      graph.applyCommand(obj);
    },
    onParseError: (raw, err) => console.warn(`  ⚠ 解析错误: ${String(err)}`),
    onBraceMismatch: () => console.warn("  ⚠ 括号不匹配，跳过异常片段"),
  });

  // Feed stream to parser without printing raw tokens.
  // Raw tokens are printed inline via process.stdout.write which interleaves
  // with console.log output from onMessage, producing unreadable output.
  console.log("  正在请求模型...\n");
  try {
    for await (const token of streamGenUI(userPrompt, { apiKey })) {
      parser.push(token);
    }
    parser.end();
  } catch (err) {
    fail(`LLM 调用失败: ${err instanceof Error ? err.message : err}`);
    return;
  }

  const pending = parser.getPending().trim();
  if (pending) {
    console.warn(`\n  ⚠ 未完成片段 (${pending.length} 字符)，可能是模型在 JSON 外输出了额外文本`);
  }

  console.log();
  assert(graph.size > 0, `至少构建出 1 个节点 (实际 ${graph.size})`);
  assert(graph.getRoot() !== null, "根节点存在");

  const pendingIds = graph.getPendingChildIds();
  assert(
    pendingIds.length === 0,
    `无未完成子节点 (pending = ${pendingIds.join(", ") || "无"})`,
  );

  console.log("\n  uitreeJson 输出:\n");
  console.log(uitreeJson(graph, 2));
}

// ── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  const live = process.argv.includes("--live");

  testMockBuild();
  testUpdateDataModelCommands();
  testDataModelRootObjectPath();
  testParserIntegration();
  testParserExtraTrailingCloseBraces();
  testParserExtraBraceBeforeBracket();
  testCompactParserIntegration();
  testIncrementalPatches();
  testIncrementalCompactStream();
  testFullNodeOmittedChildrenPreserves();

  if (live) {
    await testLiveStream();
  } else {
    console.log('\n提示: 添加 --live 标志可进行真实 LLM 流测试，例如:');
    console.log('  npx tsx graph/test.ts --live "生成一个天气预报卡片"\n');
  }

  if (process.exitCode) {
    console.error("\n部分测试失败");
  } else {
    console.log("\n所有测试通过 ✅");
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
