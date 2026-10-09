import assert from "node:assert/strict";
import { test } from "vitest";
import fixtures from "./fixtures/high-level-component-examples.json";
import {
  HIGH_LEVEL_COMPONENT_TYPES,
  VISUAL_RECIPE_VERSION,
  visualRecipePart,
} from "../src/runtime/compact-components";
import { compileMiniDsl } from "../src/runtime/mini-renderer";
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
  assert.ok(visualRecipePart("TopTextBottomValue", "item", "2x4").styles);

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
  });
  assert.equal(
    (dataDisplay.getNode("display_value")?.props.styles as Record<string, unknown>).fontSize,
    56,
  );
});

test("高阶组件拒绝错误尺寸、未知 Props、children 和生成 ID 冲突", () => {
  const action = [{ call: "clickToIntent", args: { intentName: "Test" } }];
  assert.throws(
    () => compileMiniDsl(JSON.stringify([
      "root",
      "PillButton",
      {
        label: "操作",
        actionInk: "#FF1F4799",
        actionSurface: "#331F4799",
        onClick: action,
      },
    ]), { size: "2x4" }),
    /2x2/,
  );
  assert.throws(
    () => compileMiniDsl('["root","EmphasizedData",{"value":1,"fontColor":"#FF000000","unknownProp":20}]'),
    /不接受 unknownProp/,
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
