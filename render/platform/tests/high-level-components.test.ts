import assert from "node:assert/strict";
import { test } from "node:test";
import fixtures from "../fixtures/high-level-component-examples.json";
import {
  HIGH_LEVEL_COMPONENT_TYPES,
  VISUAL_RECIPE_VERSION,
  visualRecipePart,
} from "../lib/compact-components";
import { compileMiniDsl } from "../lib/mini-renderer";
import { defaultRegistry, renderTree } from "@genui-sdk/renderer";

const highLevelTypes = new Set<string>(HIGH_LEVEL_COMPONENT_TYPES);

for (const example of fixtures.examples) {
  test(`高阶组件示例：${example.name}`, () => {
    const result = compileMiniDsl(example.source, { size: example.size as "2x2" | "2x4" });
    assert.deepEqual(result.warnings, []);
    assert.ok(!result.jsonl.includes("_visualRecipe"));
    for (const node of result.graph.getAllNodes().values()) {
      assert.ok(defaultRegistry[node.type], `未注册基础组件 ${node.type}`);
      assert.ok(!highLevelTypes.has(node.type.replace(/^Extended\./, "")), `未展开 ${node.type}`);
    }
    assert.ok(renderTree(result.graph, defaultRegistry));
  });
}

test("预览样例覆盖共享 Runtime 的全部高阶组件", () => {
  const covered = new Set<string>();
  for (const example of fixtures.examples) {
    for (const line of example.source.split("\n")) {
      const row = JSON.parse(line) as unknown[];
      if (typeof row[1] === "string" && highLevelTypes.has(row[1])) covered.add(row[1]);
    }
  }
  assert.deepEqual([...covered].sort(), [...HIGH_LEVEL_COMPONENT_TYPES].sort());
});

test("浏览器展开直接使用 visual-recipes-v1 的关键几何", () => {
  assert.equal(VISUAL_RECIPE_VERSION, "visual-recipes-v1");
  assert.deepEqual(visualRecipePart("InfoBlock", "icon", "2x2").styles, {
    width: 20,
    height: 20,
    objectFit: "contain",
    flexShrink: 0,
  });
  assert.equal(visualRecipePart("ProgressCircleSingle", "ring", "2x4").styles.width, 44);
  assert.equal(visualRecipePart("TopTextBottomValue", "item", "2x4").styles.layoutWeight, 1);

  const dataDisplay = compileMiniDsl(fixtures.examples[0].source, { size: "2x2" }).graph;
  assert.equal(dataDisplay.getNode("action")?.type, "Extended.Button");
  assert.deepEqual(dataDisplay.getNode("action")?.props.styles, {
    width: "matchParent",
    height: 36,
    borderRadius: 30,
    padding: 0,
    flexShrink: 0,
    backgroundColor: "#331F4799",
    fontColor: "#FF1F4799",
    fontSize: 14,
    fontWeight: 500,
    textAlign: "center",
  });
  assert.equal(
    (dataDisplay.getNode("display_value")?.props.styles as Record<string, unknown>).fontSize,
    56,
  );

  const info = compileMiniDsl(fixtures.examples[1].source, { size: "2x2" }).graph;
  assert.equal((info.getNode("phone")?.props.styles as Record<string, unknown>).width, "matchParent");
  assert.equal((info.getNode("phone_icon")?.props.styles as Record<string, unknown>).width, 20);

  const event = compileMiniDsl(fixtures.examples[2].source, { size: "2x2" }).graph;
  assert.equal((event.getNode("event")?.props.styles as Record<string, unknown>).height, 50);
  assert.equal((event.getNode("event_rail_line")?.props.styles as Record<string, unknown>).height, 32);
  assert.equal(
    (event.getNode("event_time")?.props.styles as Record<string, unknown>).fontColor,
    "#998C4B1C",
  );

  const table = compileMiniDsl(fixtures.examples[3].source, { size: "2x2" }).graph;
  assert.equal((table.getNode("settings")?.props.styles as Record<string, unknown>).width, 36);
  assert.equal((table.getNode("settings_icon")?.props.styles as Record<string, unknown>).width, 20);

  const emphasized = compileMiniDsl(fixtures.examples[4].source, { size: "2x2" }).graph;
  assert.equal((emphasized.getNode("metric_value")?.props.styles as Record<string, unknown>).fontSize, 30);
  assert.deepEqual(
    (emphasized.getNode("metric_unit")?.props.styles as Record<string, unknown>).margin,
    { top: 14 },
  );

  const progressCircle = compileMiniDsl(fixtures.examples[5].source, { size: "2x2" }).graph;
  assert.equal(
    (progressCircle.getNode("circle")?.props.styles as Record<string, unknown>).width,
    72,
  );
  assert.equal(
    (progressCircle.getNode("circle_ring")?.props.styles as Record<string, unknown>).width,
    60,
  );
  assert.equal(
    (progressCircle.getNode("circle_external_text")?.props.styles as Record<string, unknown>)
      .fontSize,
    10,
  );

  const progress = compileMiniDsl(fixtures.examples[6].source, { size: "2x4" }).graph;
  assert.equal((progress.getNode("progress")?.props.styles as Record<string, unknown>).height, 50);
  assert.equal((progress.getNode("progress_bar")?.props.styles as Record<string, unknown>).height, 8);
  assert.equal((progress.getNode("progress_unit")?.props.styles as Record<string, unknown>).fontSize, 12);
  assert.equal((progress.getNode("details_item0")?.props.styles as Record<string, unknown>).layoutWeight, 1);
  assert.equal((progress.getNode("details_item0")?.props.styles as Record<string, unknown>).height, 48);

  const circle = compileMiniDsl(fixtures.examples[7].source, { size: "2x4" }).graph;
  assert.equal((circle.getNode("progress_ring")?.props.styles as Record<string, unknown>).width, 44);
  assert.equal((circle.getNode("progress")?.props.styles as Record<string, unknown>).height, 46);
  assert.equal(circle.getNode("progress_icon")?.type, "Extended.Image");
  assert.equal((circle.getNode("progress_icon")?.props.styles as Record<string, unknown>).width, 20);
  assert.equal(
    (circle.getNode("progress_icon")?.props.styles as Record<string, unknown>).fillColor,
    "#991F4799",
  );

  const cardButton = compileMiniDsl(fixtures.examples[8].source, { size: "2x4" }).graph;
  assert.equal((cardButton.getNode("calendar")?.props.styles as Record<string, unknown>).width, "matchParent");
  assert.equal((cardButton.getNode("focus_visual")?.props.styles as Record<string, unknown>).width, 20);

  const metrics = compileMiniDsl(fixtures.examples[9].source, { size: "2x4" }).graph;
  assert.equal((metrics.getNode("metrics_item0")?.props.styles as Record<string, unknown>).layoutWeight, 1);
  assert.equal((metrics.getNode("metrics_item0_unit")?.props.styles as Record<string, unknown>).fontSize, 12);

  const summary = compileMiniDsl(fixtures.examples[10].source, { size: "2x4" }).graph;
  assert.equal((summary.getNode("list")?.props.styles as Record<string, unknown>).height, 102);
});

test("高阶组件拒绝错误尺寸、未知 Props、children 和生成 ID 冲突", () => {
  const action = [{ call: "clickToIntent", args: { intentName: "Test" } }];
  assert.throws(
    () => compileMiniDsl(JSON.stringify([
      "root",
      "CircleButton",
      {
        icon: "resources/base/media/play_fill.svg",
        accessibility: { label: "播放" },
        actionInk: "#FF1F4799",
        actionSurface: "#331F4799",
        onClick: action,
      },
    ]), { size: "2x4" }),
    /2x2/,
  );
  assert.throws(
    () => compileMiniDsl('["root","EmphasizedData",{"value":1,"fontColor":"#FF000000","unknown":20}]'),
    /不接受 unknown/,
  );
  assert.throws(
    () => compileMiniDsl('["root","EmphasizedData",{"value":1,"fontColor":"#FF000000"},["child"]]\n["child","Text",{"content":"x"}]'),
    /不接受 children/,
  );
  assert.throws(
    () => compileMiniDsl('["root","Column",{},["metric"]]\n["metric","EmphasizedData",{"value":1,"fontColor":"#FF000000"}]\n["metric_value","Text",{"content":"冲突"}]'),
    /冲突/,
  );
});

test("TextBlock 接受 2–4 项并拒绝超出容量", () => {
  const item = (index: number) => ({ label: `指标${index}`, value: `${index}` });
  for (const count of [2, 3, 4]) {
    const source = JSON.stringify([
      "root",
      "TextBlock",
      {
        items: Array.from({ length: count }, (_, index) => item(index + 1)),
        fontColor: "#FF563D99",
        backgroundColor: "#99FFFFFF",
      },
    ]);
    const { graph } = compileMiniDsl(source, { size: "2x4" });
    assert.equal(graph.getNode("root")?.children.length, count);
    assert.ok(graph.getNode(`root_item${count - 1}`));
  }
  assert.throws(
    () => compileMiniDsl(JSON.stringify([
      "root",
      "TextBlock",
      {
        items: Array.from({ length: 5 }, (_, index) => item(index + 1)),
        fontColor: "#FF563D99",
        backgroundColor: "#99FFFFFF",
      },
    ]), { size: "2x4" }),
    /2–4 项/,
  );
});
