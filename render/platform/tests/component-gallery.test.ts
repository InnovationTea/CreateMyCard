import assert from "node:assert/strict";
import { test } from "node:test";
import { defaultRegistry, renderTree } from "@genui-sdk/renderer";
import { HIGH_LEVEL_COMPONENT_TYPES } from "../lib/compact-components";
import { compileMiniDsl } from "../lib/mini-renderer";
import {
  COMPONENT_GALLERY,
  FUSION_COMPONENT_NAMES,
} from "../src/component-gallery-data";

const expectedFusionComponents = [
  "Row",
  "Column",
  "Stack",
  "Text",
  "Image",
  "Divider",
  "SingleLineTitle",
  "DoubleLineTitle",
  "Badge",
  "EmphasizedData",
  "EmphasisText",
  "SecondaryBody",
  "ProgressCircle",
  "InfoBlock",
  "TableText",
  "H_BarChart",
  "NumericRatioStack",
  "DataDisplay",
  "EventCard",
  "PillButton",
  "CircleButton",
  "ProgressLine2",
  "TextBlock",
  "CardButton",
  "ProgressCircleSingle",
  "TopTextBottomValue",
  "SummaryList",
];

test("组件总览覆盖 Fusion Prompt 的完整组件清单", () => {
  assert.deepEqual([...FUSION_COMPONENT_NAMES], expectedFusionComponents);
  assert.deepEqual(
    COMPONENT_GALLERY.map(component => component.name),
    expectedFusionComponents,
  );
  assert.equal(new Set(COMPONENT_GALLERY.map(component => component.id)).size, COMPONENT_GALLERY.length);
});

test("组件总览遵循最新的共享与尺寸专属边界", () => {
  const namesForCategory = (
    category: (typeof COMPONENT_GALLERY)[number]["category"],
  ) => COMPONENT_GALLERY
    .filter(component => component.category === category)
    .map(component => component.name);
  assert.deepEqual(
    namesForCategory("基础结构"),
    ["Row", "Column", "Stack", "Text", "Image", "Divider"],
  );
  assert.deepEqual(
    namesForCategory("共享组件"),
    [
      "SingleLineTitle",
      "DoubleLineTitle",
      "Badge",
      "EmphasizedData",
      "EmphasisText",
      "SecondaryBody",
      "ProgressCircle",
      "InfoBlock",
      "TableText",
      "H_BarChart",
      "NumericRatioStack",
      "DataDisplay",
      "EventCard",
      "PillButton",
      "ProgressLine2",
      "ProgressCircleSingle",
      "SummaryList",
    ],
  );
  assert.deepEqual(
    namesForCategory("2×2 组件"),
    ["CircleButton"],
  );
  assert.deepEqual(
    namesForCategory("2×4 组件"),
    ["TextBlock", "CardButton", "TopTextBottomValue"],
  );
});

test("共享合同与实际可用尺寸分别表达", () => {
  const sizesByName = new Map(
    COMPONENT_GALLERY.map(component => [component.name, component.sizes]),
  );
  assert.deepEqual(sizesByName.get("TableText"), ["2x2", "2x4"]);
  assert.deepEqual(sizesByName.get("EventCard"), ["2x2", "2x4"]);
  assert.deepEqual(sizesByName.get("ProgressCircleSingle"), ["2x2", "2x4"]);
  assert.deepEqual(sizesByName.get("DataDisplay"), ["2x2"]);
  assert.deepEqual(sizesByName.get("ProgressLine2"), ["2x4"]);
  assert.deepEqual(sizesByName.get("SummaryList"), ["2x4"]);
});

for (const component of COMPONENT_GALLERY) {
  test(`组件总览可渲染：${component.name}`, () => {
    const result = compileMiniDsl(component.source, { size: component.size });
    assert.deepEqual(result.warnings, []);
    assert.equal(result.size, component.size);
    assert.ok(result.expandedCount >= result.count);
    assert.ok(renderTree(result.graph, defaultRegistry));
  });
}

test("组件总览覆盖 Renderer 支持的全部高阶组件", () => {
  const covered = new Set<string>();
  for (const component of COMPONENT_GALLERY) {
    for (const line of component.source.split("\n")) {
      const row = JSON.parse(line) as unknown[];
      if (typeof row[1] === "string") covered.add(row[1]);
    }
  }
  assert.deepEqual(
    [...HIGH_LEVEL_COMPONENT_TYPES].filter(type => !covered.has(type)),
    [],
  );
});
