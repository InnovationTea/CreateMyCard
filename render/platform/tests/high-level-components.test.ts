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
    width: 24,
    height: 24,
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
  assert.equal((info.getNode("phone_visual")?.props.styles as Record<string, unknown>).width, 24);

  const event = compileMiniDsl(fixtures.examples[2].source, { size: "2x2" }).graph;
  assert.equal((event.getNode("event")?.props.styles as Record<string, unknown>).height, 50);
  assert.equal((event.getNode("event")?.props.styles as Record<string, unknown>).flexShrink, 1);
  assert.equal((event.getNode("event_rail_line")?.props.styles as Record<string, unknown>).height, 32);
  assert.equal((event.getNode("event_title")?.props.styles as Record<string, unknown>).fontWeight, 700);
  assert.equal(
    (event.getNode("event_time")?.props.styles as Record<string, unknown>).fontColor,
    "#998C4B1C",
  );

  const table = compileMiniDsl(fixtures.examples[3].source, { size: "2x2" }).graph;
  assert.equal((table.getNode("settings")?.props.styles as Record<string, unknown>).width, 40);
  assert.equal((table.getNode("settings_icon")?.props.styles as Record<string, unknown>).width, 20);

  const emphasized = compileMiniDsl(fixtures.examples[4].source, { size: "2x2" }).graph;
  assert.equal((emphasized.getNode("metric_value")?.props.styles as Record<string, unknown>).fontSize, 30);
  assert.equal(
    (emphasized.getNode("metric")?.props.styles as Record<string, unknown>).alignItems,
    "baseline",
  );
  assert.equal(
    (emphasized.getNode("metric_unit")?.props.styles as Record<string, unknown>).margin,
    undefined,
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
  assert.equal((progress.getNode("progress")?.props.styles as Record<string, unknown>).itemMargin, 4);
  assert.equal((progress.getNode("progress_bar")?.props.styles as Record<string, unknown>).height, 8);
  assert.equal(
    (progress.getNode("progress_readout")?.props.styles as Record<string, unknown>).height,
    30,
  );
  assert.equal(
    (progress.getNode("progress_readout")?.props.styles as Record<string, unknown>).alignItems,
    "baseline",
  );
  const progressValue = progress.getNode("progress_value")?.props.styles as Record<string, unknown>;
  const progressUnit = progress.getNode("progress_unit")?.props.styles as Record<string, unknown>;
  assert.equal(progressValue.height, 30);
  assert.equal(progressValue.lineHeight, 1);
  assert.equal(progressUnit.fontSize, 12);
  assert.equal(progressUnit.height, 12);
  assert.equal(progressUnit.lineHeight, 1);
  assert.equal(progressUnit.margin, undefined);
  const detailStyles = progress.getNode("details_item0")?.props.styles as Record<string, unknown>;
  const detailConstraint = detailStyles.constraintSize as Record<string, unknown>;
  assert.equal(detailStyles.height, "matchParent");
  assert.equal(detailConstraint.minWidth, 64);

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
  assert.equal((cardButton.getNode("focus_visual")?.props.styles as Record<string, unknown>).width, 24);

  const metrics = compileMiniDsl(fixtures.examples[9].source, { size: "2x4" }).graph;
  assert.equal((metrics.getNode("metrics_item0")?.props.styles as Record<string, unknown>).layoutWeight, 1);
  assert.equal((metrics.getNode("metrics_item0_unit")?.props.styles as Record<string, unknown>).fontSize, 12);

  const summary = compileMiniDsl(fixtures.examples[10].source, { size: "2x4" }).graph;
  assert.equal((summary.getNode("list")?.props.styles as Record<string, unknown>).height, 102);

  const shared = compileMiniDsl(fixtures.examples[11].source, { size: "2x4" }).graph;
  assert.equal(
    (shared.getNode("ratio_item0_value_group")?.props.styles as Record<string, unknown>).itemMargin,
    0,
  );
});

test("EmphasizedData 在满宽根节点内左对齐并对齐数值与单位基线", () => {
  const root = visualRecipePart("EmphasizedData", "root", "2x2").styles;
  const unit = visualRecipePart("EmphasizedData", "unit", "2x2").styles;
  assert.equal(root.width, "matchParent");
  assert.equal(root.justifyContent, "start");
  assert.equal(root.alignItems, "baseline");
  const value = visualRecipePart("EmphasizedData", "value", "2x2").styles;
  assert.equal(value.height, 30);
  assert.equal(value.lineHeight, 1);
  assert.equal(unit.height, 12);
  assert.equal(unit.lineHeight, 1);
  assert.equal(root.padding, undefined);
  assert.equal(unit.margin, undefined);
});

test("带图标 PillButton 补偿文字行盒以实现视觉垂直居中", () => {
  const source = JSON.stringify([
    "action",
    "PillButton",
    {
      label: "每日歌单",
      icon: "resources/base/media/music_fill.svg",
      actionSurface: "#33563D99",
      actionInk: "#FF563D99",
      onClick: [{ call: "clickToDeeplink", args: { uri: "hwmusic://playlist" } }],
    },
  ]);
  const { graph } = compileMiniDsl(source, { size: "2x2" });
  const root = graph.getNode("action")?.props.styles as Record<string, unknown>;
  const icon = graph.getNode("action_icon")?.props.styles as Record<string, unknown>;
  const label = graph.getNode("action_text")?.props.styles as Record<string, unknown>;

  assert.equal(root.height, 36);
  assert.equal(root.alignItems, "center");
  assert.equal(icon.height, 20);
  assert.equal(label.height, 17);
});

test("2x4 纵向固定槽中的 InfoBlock 与 CardButton 保持等高", () => {
  const source = [
    '["root","Column",{"width":132,"height":126,"itemMargin":12},["status","settings"]]',
    '["status","InfoBlock",{"variant":"slot","primaryText":"连接状态","secondaryText":"连接正常","fontColor":"#FF1F4799","backgroundColor":"#99FFFFFF","width":"matchParent","layoutWeight":1}]',
    '["settings","CardButton",{"label":"设备设置","fontColor":"#FF1F4799","backgroundColor":"#99FFFFFF","onClick":[{"call":"openSettings","args":{}}],"width":"matchParent","layoutWeight":1}]',
  ].join("\n");
  const { graph } = compileMiniDsl(source, { size: "2x4" });

  for (const identifier of ["status", "settings"]) {
    const styles = graph.getNode(identifier)?.props.styles as Record<string, unknown>;
    assert.equal(styles.height, 57);
    assert.equal(styles.flexShrink, 0);
    assert.equal(styles.layoutWeight, undefined);
  }
  const primary = graph.getNode("status_primary")?.props.styles as Record<string, unknown>;
  const label = graph.getNode("settings_label")?.props.styles as Record<string, unknown>;
  assert.equal(primary.fontSize, 14);
  assert.equal(label.fontSize, 14);
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

test("SecondaryBody 继承显示值绑定、按角色限制行数并保留完整标签", () => {
  const source = [
    '["root","Column",{},["body","metadata","supporting"]]',
    '["body","SecondaryBody",{"role":"body","items":[{"value":{"path":"/description"},"maxLines":2}],"fontColor":"#FF1F4799"}]',
    '["metadata","SecondaryBody",{"role":"metadata","items":[{"value":"{{ \'更新 \' + ${/updatedAt} }}"}],"fontColor":"#FF1F4799"}]',
    '["supporting","SecondaryBody",{"role":"supporting","items":[{"label":"电流","value":"-151mA"},{"label":"电压","value":"4V"},{"label":"更新","value":"09:00"}],"fontColor":"#FF1F4799","width":132}]',
    '["/description","今天适宜户外活动，紫外线较弱"]',
    '["/updatedAt","10:30"]',
  ].join("\n");
  const { graph } = compileMiniDsl(source, { size: "2x2" });
  const body = graph.getNode("body_item0_value")?.props.styles as Record<string, unknown>;
  const metadata = graph.getNode("metadata_item0_value")?.props.styles as Record<string, unknown>;
  assert.equal(body.fontSize, 14);
  assert.equal(body.fontWeight, 400);
  assert.equal(body.height, 40);
  assert.equal(body.maxLines, 2);
  assert.equal(metadata.fontSize, 12);
  assert.equal(metadata.height, 18);
  const supportingLabel = graph.getNode("supporting_item0_label")?.props.styles as Record<string, unknown>;
  const supportingValue = graph.getNode("supporting_item0_value")?.props.styles as Record<string, unknown>;
  assert.equal(supportingLabel.flexShrink, 0);
  assert.equal(supportingValue.flexShrink, 1);

  assert.throws(
    () => compileMiniDsl(
      '["root","SecondaryBody",{"items":[{"value":"正文"}],"fontColor":"#FF1F4799"}]',
    ),
    /必须声明 role/,
  );
  assert.throws(
    () => compileMiniDsl(
      '["root","SecondaryBody",{"role":"metadata","items":[{"value":"更新时间","maxLines":2}],"fontColor":"#FF1F4799"}]',
    ),
    /只有 body SecondaryBody 支持两行/,
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
    const rootStyles = graph.getNode("root")?.props.styles as Record<string, unknown>;
    const itemStyles = graph.getNode(`root_item${count - 1}`)?.props.styles as Record<string, unknown>;
    const labelSlotStyles = graph.getNode("root_item0_label_slot")?.props.styles as Record<string, unknown>;
    const labelStyles = graph.getNode("root_item0_label")?.props.styles as Record<string, unknown>;
    const valueSlotStyles = graph.getNode("root_item0_value_slot")?.props.styles as Record<string, unknown>;
    const valueStyles = graph.getNode("root_item0_value")?.props.styles as Record<string, unknown>;
    assert.equal(graph.getNode("root")?.children.length, count);
    assert.equal(rootStyles.itemMargin, 8);
    assert.equal(rootStyles.height, "matchParent");
    assert.equal(rootStyles.justifyContent, "start");
    assert.equal(rootStyles.layoutWeight, 1);
    assert.deepEqual(rootStyles.constraintSize, {
      minHeight: 48,
    });
    assert.ok(graph.getNode(`root_item${count - 1}`));
    assert.equal(itemStyles.layoutWeight, 1);
    assert.deepEqual(graph.getNode("root_item0")?.children, [
      "root_item0_label_slot",
      "root_item0_value_slot",
    ]);
    assert.deepEqual(
      { height: labelSlotStyles.height, alignItems: labelSlotStyles.alignItems },
      { height: 18, alignItems: "center" },
    );
    assert.equal(labelStyles.height, undefined);
    assert.deepEqual(
      {
        fontSize: labelStyles.fontSize,
        fontWeight: labelStyles.fontWeight,
        textAlign: labelStyles.textAlign,
        textOverflow: labelStyles.textOverflow,
      },
      { fontSize: 12, fontWeight: 700, textAlign: "start", textOverflow: "ellipsis" },
    );
    assert.deepEqual(
      { height: valueSlotStyles.height, alignItems: valueSlotStyles.alignItems },
      { height: 16, alignItems: "center" },
    );
    assert.equal(valueStyles.height, undefined);
    assert.deepEqual(
      {
        fontSize: valueStyles.fontSize,
        fontWeight: valueStyles.fontWeight,
        textAlign: valueStyles.textAlign,
        textOverflow: valueStyles.textOverflow,
      },
      { fontSize: 10, fontWeight: 500, textAlign: "start", textOverflow: "ellipsis" },
    );
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
