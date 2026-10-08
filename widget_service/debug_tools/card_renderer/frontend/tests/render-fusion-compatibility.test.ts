import assert from "node:assert/strict";
import fs from "node:fs";
import { fileURLToPath } from "node:url";
import { test } from "vitest";
import fixtures from "./fixtures/fusion-examples.json";
import { compileMiniDsl, SURFACE_ID } from "../src/runtime/mini-renderer";
import { FUSION_PALETTES } from "../src/runtime/compact-components";
import { resolvePathBindingsInValue, evaluateExpression, runActionDispatch } from "@genui-sdk/interactions";
import { defaultRegistry, renderTree } from "@genui-sdk/renderer";
import { mergeCommonStyles } from "@genui-sdk/components";

const RESOURCE_ROOT = fileURLToPath(
  new URL('../../../../../render/platform/public/resources/', import.meta.url),
);

for (const example of fixtures.examples) {
  test(`分支原始示例：${example.name}`, async () => {
    const { graph, warnings } = compileMiniDsl(example.source, { size: example.size as "2x2" | "2x4" });
    assert.deepEqual(warnings, []);
    const leaf = (p: string) => graph.getDataModelValue(SURFACE_ID, p);
    for (const node of graph.getAllNodes().values()) {
      assert.ok(defaultRegistry[node.type], `未注册组件 ${node.type}`);
      assert.ok(!["ActionUnit", "CardHeader", "TimelineUnit"].some(t => node.type.endsWith(t)));
      const resolved = resolvePathBindingsInValue(node.props, leaf) as Record<string, unknown>;
      if (node.type === "Extended.Text") {
        assert.ok(resolved.content !== undefined && resolved.content !== "", `${node.id} 未解析`);
        assert.ok(!String(resolved.content).includes("{{"));
      }
      if (node.type === "Extended.Image") {
        assert.equal(typeof resolved.src, "string");
        const relative = String(resolved.src).replace(/^\/?resources\//, '');
        assert.ok(fs.existsSync(`${RESOURCE_ROOT}${relative}`), `素材缺失 ${resolved.src}`);
      }
      if (node.props.action) {
        const calls: unknown[] = [];
        await runActionDispatch(node.props.action, { functionCall: args => { calls.push(args); } }, { componentId: node.id, surfaceId: SURFACE_ID, getDataModelLeaf: leaf });
        assert.equal(calls.length, 1);
        assert.ok(!JSON.stringify(calls).includes("{{"));
      }
    }
    assert.ok(renderTree(graph, defaultRegistry));
  });
}

test("表达式支持多字段拼接、数值运算、比较、逻辑和三元，保留 boolean/number", () => {
  const values: Record<string, unknown> = { "/a": 40, "/b": 60, "/connected": false };
  const get = (p: string) => values[p];
  assert.equal(evaluateExpression("'L ' + ${/a} + '% | R ' + ${/b} + '%'", get), "L 40% | R 60%");
  assert.equal(evaluateExpression("(${/a} + ${/b}) / 2", get), 50);
  assert.equal(evaluateExpression("${/a} >= 40 && !${/connected}", get), true);
  assert.equal(evaluateExpression("${/connected} ? '已连接' : '未连接'", get), "未连接");
  assert.equal(resolvePathBindingsInValue("{{ ${/connected} }}", get), false);
  assert.equal(evaluateExpression("false ? 1 / 0 : 12", get), 12);
  assert.equal(evaluateExpression("true || 1 / 0", get), true);
  assert.equal(evaluateExpression("-2 * 3 + 10 % 4", get), -4);
});

test("表达式拒绝执行代码、属性访问、未知函数、非有限值与过深嵌套", () => {
  for (const expr of ["alert(1)", "globalThis", "${/a}.constructor", "eval('1')", "1 / 0", "size(42)", "1e999", "(".repeat(100) + "1" + ")".repeat(100)]) {
    assert.throws(() => evaluateExpression(expr, () => 1), expr);
  }
});

test("dataModel 叶子写入可读取父数组，父级替换不留下旧叶子", () => {
  const { graph } = compileMiniDsl('["root","Text",{"content":"列表"}]\n["/items/0/title","A"]\n["/items/1/title","B"]');
  const get = (p: string) => graph.getDataModelValue(SURFACE_ID, p);
  assert.equal(evaluateExpression("size(${/items})", get), 2);
  graph.setDataModelValue(SURFACE_ID, "/items", [{ title: "C" }]);
  assert.equal(get("/items/0/title"), "C");
  assert.equal(get("/items/1/title"), undefined);
  graph.setDataModelValue(SURFACE_ID, "/items/0/title", "D");
  assert.deepEqual(get("/items"), [{ title: "D" }]);
  graph.setDataModelValue(SURFACE_ID, "/a~1b/~0x", 5);
  assert.equal(get("/a~1b/~0x"), 5);
  assert.equal(get("/constructor"), undefined);
});

test("CardHeader 展开固定几何且阻止生成 ID 冲突", () => {
  const source = '["root","Column",{},["header"]]\n["header","CardHeader",{"title":"天气","fontColor":"#FF000000","icon":"resources/base/media/sun_max.svg"}]';
  const { graph } = compileMiniDsl(source, { size: "2x4" });
  assert.equal((graph.getNode("header")!.props.styles as Record<string, unknown>).width, "matchParent");
  assert.equal(graph.getNode("header_title")!.type, "Extended.Text");
  assert.throws(() => compileMiniDsl(source + '\n["header_title","Text",{"content":"冲突"}]'), /冲突/);
  assert.throws(
    () => compileMiniDsl(source.replace('"fontColor"', '"unknownProp":12,"fontColor"')),
    /CardHeader/,
  );
});

test("TimelineUnit 与 icon-round 展开为可渲染基础组件", () => {
  const timeline = '["root","Column",{},["line"]]\n["line","TimelineUnit",{"color":"#FF99661F","lineColor":"#1A99661F"}]';
  const graph = compileMiniDsl(timeline).graph;
  assert.equal((graph.getNode("line")!.props.styles as Record<string, unknown>).height, 48);
  assert.equal(graph.getNode("line_dot")!.type, "Extended.Divider");
  assert.throws(() => compileMiniDsl(timeline, { size: "2x4" }), /2x2/);
  const round = compileMiniDsl('["root","ActionUnit",{"state":"icon-round","icon":"resources/base/media/play_fill.svg","actionSurface":"#331F4799","actionInk":"#FF1F4799","accessibility":{"label":"播放"},"onClick":[{"call":"clickToIntent","args":{"intentName":"Music"}}]}]');
  assert.equal(round.graph.getNode("root_icon")!.type, "Extended.Image");
  assert.equal((round.graph.getRoot()!.props.styles as Record<string, unknown>).width, 30);
});

test("五套融球背景保留规定配色、百分比几何和玻璃层", () => {
  for (const [design, colors] of Object.entries(FUSION_PALETTES)) {
    const { graph } = compileMiniDsl(JSON.stringify(["root", "Column", { design }, ["text"]]) + '\n["text","Text",{"content":"融球"}]');
    assert.equal(graph.getRoot()!.type, "Extended.Stack");
    assert.equal((graph.getNode("fusionBallLarge")!.props.styles as Record<string, unknown>).backgroundColor, colors[0]);
    assert.ok(graph.getNode("__genui_render_component__root"));
    assert.deepEqual((graph.getNode("fusionBallGlassLayer")!.props.styles as Record<string, unknown>).backdropBlur, { radius: 210 });
  }
});

test("通用样式解析 ARGB 渐变、百分比、宽高比和阴影", () => {
  const style = mergeCommonStyles({ width: "125%", aspectRatio: 2, shadow: "outerDefaultXS", linearGradient: { direction: "RightBottom", colors: [["#FFCBDDFE", 0], ["#FFF1F6FE", 1]] } });
  assert.equal(style.width, "125%");
  assert.equal(style.aspectRatio, 2);
  assert.match(String(style.backgroundImage), /to bottom right, rgba\(203,221,254,1\) 0%/);
  assert.ok(style.boxShadow);
});

test("Progress 拒绝百分比字符串、负数和超范围值", () => {
  for (const value of ["68%", -1, 101]) assert.throws(() => compileMiniDsl(JSON.stringify(["root", "Progress", { type: "ring", value, total: 100 }])), /Progress/);
});

test("圆角裁剪覆盖模糊合成层，融球预览保留色彩变化且不改写 A2UI", () => {
  const style = mergeCommonStyles({ clip: true, borderRadius: 20 });
  assert.equal(style.clipPath, "inset(0 round 20px)");
  assert.equal(style.isolation, "isolate");
  const { graph } = compileMiniDsl('["root","Column",{"design":"fusion-ball-sport-orange"}]');
  const tree = renderTree(graph, defaultRegistry) as any;
  const find = (node: any): any => {
    if (node?.props?.["data-node-id"] === "fusionBallGlassLayer") return node;
    return (Array.isArray(node?.props?.children) ? node.props.children : [node?.props?.children]).filter(Boolean).map(find).find(Boolean);
  };
  assert.deepEqual(find(tree).props.backdropBlur, { radius: 24 });
  assert.deepEqual((graph.getNode("fusionBallGlassLayer")!.props.styles as any).backdropBlur, { radius: 210 });
});

test("容器点击可键盘触发，嵌套动作停止冒泡且参数实时解析", async () => {
  const { graph } = compileMiniDsl('["root","Column",{"onClick":[{"call":"clickToDeeplink","args":{"uri":"{{ \'hww://weather?city=\' + ${/city} }}"}}]},["text"]]\n["text","Text",{"content":"天气"}]\n["/city","101"]');
  const calls: unknown[] = [];
  const tree = renderTree(graph, defaultRegistry, { interactionHost: { functionCall: value => { calls.push(value); } } }) as { props: Record<string, any> };
  assert.equal(tree.props.role, "button");
  assert.equal(tree.props.tabIndex, 0);
  let stopped = false;
  graph.setDataModelValue(SURFACE_ID, "/city", "102");
  tree.props.onClick({ stopPropagation() { stopped = true; }, clientX: 0, clientY: 0 });
  await Promise.resolve();
  assert.equal(stopped, true);
  assert.deepEqual(calls, [{ call: "clickToDeeplink", args: { uri: "hww://weather?city=102" }, componentId: "root" }]);
});
