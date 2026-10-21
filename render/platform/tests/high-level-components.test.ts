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
    48,
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
  const summaryRoot = summary.getNode("list")?.props.styles as Record<string, unknown>;
  const summaryConstraint = summaryRoot.constraintSize as Record<string, unknown>;
  assert.equal(summaryRoot.height, "matchParent");
  assert.equal(summaryRoot.justifyContent, "end");
  assert.equal(summaryConstraint.minHeight, 102);
  assert.equal(
    (summary.getNode("list_item0")?.props.styles as Record<string, unknown>).backgroundColor,
    "#99FFFFFF",
  );

  const shared = compileMiniDsl(fixtures.examples[11].source, { size: "2x4" }).graph;
  assert.equal(
    (shared.getNode("ratio_item0_value_group")?.props.styles as Record<string, unknown>).itemMargin,
    0,
  );
});

test("ProgressCircle 将百分号 Expression 拆成数值驱动和可见读数", () => {
  const source = [
    '["root","Column",{},["circle"]]',
    JSON.stringify([
      "circle",
      "ProgressCircle",
      {
        externalText: "{{ ${/data/battery/percent} + '%' }}",
        icon: "resources/base/media/battery.svg",
        accessibility: { label: "手机电量百分比" },
        width: 72,
        height: 76,
        color: "#FF1F4799",
        backgroundColor: "#331F4799",
      },
    ]),
    '["/data/battery/percent",68]',
  ].join("\n");
  const graph = compileMiniDsl(source, { size: "2x4" }).graph;

  assert.equal(graph.getNode("circle_ring")?.props.value, "{{ ${/data/battery/percent} }}");
  assert.equal(
    graph.getNode("circle_external_text")?.props.content,
    "{{ ${/data/battery/percent} + '%' }}",
  );
});

test("宽松预览允许 InfoBlock 用带标签的百分比表达式驱动圆环", () => {
  const source = [
    '["root","Column",{},["battery"]]',
    '["battery","InfoBlock",{"primaryText":"{{ \'手机电量 \' + ${/data/battery} + \'%\' }}","secondaryText":"未充电","backgroundColor":"#99FFFFFF","visual":{"type":"progressCircle","icon":"resources/base/media/battery.svg"}}]',
    '["/data/battery",68]',
  ].join("\n");
  const result = compileMiniDsl(source, { size: "2x2", previewMode: true });

  assert.equal(result.graph.getNode("battery_visual_progress")?.props.value, 68);
  assert.ok(result.warnings.some(message => message.includes("宽松预览已使用 68")));
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

test("EventCard 允许三项并按全部相邻间距计算总高", () => {
  const source = [
    '["root","Column",{},["events"]]',
    '["events","EventCard",{"items":[{"title":"晨会","time":"09:00"},{"title":"评审","time":"14:00"},{"title":"复盘","time":"17:00"}],"density":"compact","fontColor":"#FF1F4799"}]',
  ].join("\n");
  const graph = compileMiniDsl(source, { size: "2x4" }).graph;

  assert.deepEqual(graph.getNode("events")?.children, [
    "events_item0",
    "events_item1",
    "events_item2",
  ]);
  const styles = graph.getNode("events")?.props.styles as Record<string, unknown>;
  assert.equal(styles.height, 104);
  assert.equal(styles.itemMargin, 4);
});

test("EmphasisText 使用与 claw-widget 一致的行盒与文本间距", () => {
  const root = visualRecipePart("EmphasisText", "root", "2x2").styles;
  const main = visualRecipePart("EmphasisText", "main", "2x2").styles;
  const secondary = visualRecipePart("EmphasisText", "secondary", "2x2").styles;
  assert.equal(root.itemMargin, 2);
  assert.equal(Number(main.fontSize) * Number(main.lineHeight), main.height);
  assert.equal(Number(secondary.fontSize) * Number(secondary.lineHeight), secondary.height);
});

test("EmphasisText 次文本将多个有序绑定编译为响应式分隔表达式", () => {
  const source = [
    '["root","Column",{},["weather"]]',
    '["weather","EmphasisText",{"mainText":{"path":"/data/weather/condition"},'
      + '"secondaryText":[{"path":"/data/weather/city"},{"path":"/data/weather/district"}]}]',
    '["/data/weather/condition","多云"]',
    '["/data/weather/city","上海市"]',
    '["/data/weather/district","青浦区"]',
  ].join("\n");
  const { graph } = compileMiniDsl(source, { size: "2x2" });

  assert.equal(
    graph.getNode("weather_secondary")?.props.content,
    "{{ ${/data/weather/city} + ' | ' + ${/data/weather/district} }}",
  );
});

test("带图标 PillButton 补偿文字行盒以实现视觉垂直居中", () => {
  const source = JSON.stringify([
    "action",
    "PillButton",
    {
      label: "每日歌单",
      icon: "resources/base/media/music_fill.svg",
      onClick: [{ call: "clickToDeeplink", args: { uri: "hwmusic://playlist" } }],
    },
  ]);
  const { graph } = compileMiniDsl(source, { size: "2x2" });
  const root = graph.getNode("action")?.props.styles as Record<string, unknown>;
  const icon = graph.getNode("action_icon")?.props.styles as Record<string, unknown>;
  const label = graph.getNode("action_text")?.props.styles as Record<string, unknown>;

  assert.equal(root.height, 36);
  assert.equal(root.alignItems, "center");
  assert.equal(root.backgroundColor, "#331F4799");
  assert.equal(icon.height, 20);
  assert.equal(icon.fillColor, "#FF1F4799");
  assert.equal(label.height, 17);
  assert.equal(label.fontColor, "#FF1F4799");
});

test("2x4 纵向固定槽中的 InfoBlock 与 CardButton 保持等高", () => {
  const source = [
    '["root","Column",{"width":132,"height":126,"itemMargin":12},["status","settings"]]',
    '["status","InfoBlock",{"variant":"slot","primaryText":"连接状态","secondaryText":"连接正常","fontColor":"#FF1F4799","backgroundColor":"#99FFFFFF","width":"matchParent","layoutWeight":1}]',
    '["settings","CardButton",{"label":"设备设置","fontColor":"#FF1F4799","onClick":[{"call":"openSettings","args":{}}],"width":"matchParent","layoutWeight":1}]',
  ].join("\n");
  const { graph } = compileMiniDsl(source, { size: "2x4" });

  for (const identifier of ["status", "settings"]) {
    const styles = graph.getNode(identifier)?.props.styles as Record<string, unknown>;
    assert.equal(styles.height, 57);
    assert.equal(styles.flexShrink, 0);
    assert.equal(styles.layoutWeight, undefined);
  }
  const primary = graph.getNode("status_primary")?.props.styles as Record<string, unknown>;
  const action = graph.getNode("settings")?.props.styles as Record<string, unknown>;
  const label = graph.getNode("settings_label")?.props.styles as Record<string, unknown>;
  assert.equal(primary.fontSize, 14);
  assert.equal(action.backgroundColor, "#99FFFFFF");
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

test("文本语义组件只接受与 Recipe 一致的固定 fontSize 声明", () => {
  const cases: Array<{ type: string; props: Record<string, unknown>; fontSize: number }> = [
    { type: "SingleLineTitle", props: { title: "天气" }, fontSize: 12 },
    {
      type: "DoubleLineTitle",
      props: { title: "传感器", secondaryInfo: "在线" },
      fontSize: 12,
    },
    { type: "EmphasizedData", props: { value: 82, unit: "分" }, fontSize: 30 },
    {
      type: "EmphasisText",
      props: { mainText: "已连接", secondaryText: "耳机" },
      fontSize: 18,
    },
    {
      type: "SecondaryBody",
      props: { role: "body", items: [{ value: "正文" }] },
      fontSize: 14,
    },
    {
      type: "SecondaryBody",
      props: { items: [{ value: "10:30", maxLines: 2 }] },
      fontSize: 12,
    },
    {
      type: "DataDisplay",
      props: { label: "倒计时", value: 3, supportingText: "天" },
      fontSize: 48,
    },
    {
      type: "TableText",
      props: { items: [{ label: "湿度", value: "48%" }, { label: "风力", value: "2级" }] },
      fontSize: 12,
    },
    {
      type: "TableText",
      props: {
        items: [
          { label: "湿度", value: "48%" },
          { label: "风力", value: "2级" },
          { label: "气压", value: "1012hPa" },
        ],
      },
      fontSize: 10,
    },
  ];
  for (const item of cases) {
    const source = JSON.stringify([
      "content",
      item.type,
      { ...item.props, fontSize: item.fontSize },
    ]);
    const result = compileMiniDsl(source, { size: "2x2" });
    const legacy = JSON.stringify(["content", item.type, item.props]);
    assert.equal(result.jsonl, compileMiniDsl(legacy, { size: "2x2" }).jsonl);
    const invalid = JSON.stringify([
      "content",
      item.type,
      { ...item.props, fontSize: item.fontSize + 1 },
    ]);
    assert.throws(
      () => compileMiniDsl(invalid, { size: "2x2" }),
      /fontSize.*固定 Recipe 值/,
    );
  }
});

test("DataDisplay 文本模式展开居中图标、24fp 双行结论和动态支撑文本", () => {
  const source = [
    ["root", "Layout", {
      layout: "S-center",
      linearGradient: {
        direction: "RightBottom",
        colors: [["#FFCBDDFE", 0], ["#FFF1F6FE", 1]],
      },
    }, ["display"]],
    ["display", "DataDisplay", {
      icon: "resources/base/media/ic_weatherWarning.svg",
      value: { path: "/data/weather/current/alertLevel" },
      supportingText: { path: "/data/weather/updatedAtText" },
      fontSize: 24,
    }],
    ["/data/weather/current/alertLevel", "蓝色预警"],
    ["/data/weather/updatedAtText", "2026-9-19 更新"],
  ].map(row => JSON.stringify(row)).join("\n");
  const graph = compileMiniDsl(source, { size: "2x2", previewMode: true }).graph;
  const display = graph.getNode("display");
  const value = graph.getNode("display_value");

  assert.deepEqual(
    display?.children,
    ["display_icon", "display_value_area", "display_supporting"],
  );
  assert.equal(graph.getNode("display_icon")?.type, "Extended.Image");
  const valueArea = graph.getNode("display_value_area");
  const valueAreaStyles = valueArea?.props.styles as Record<string, unknown>;
  assert.deepEqual(valueArea?.children, ["display_value"]);
  assert.equal(valueAreaStyles.height, 60);
  assert.equal(valueAreaStyles.justifyContent, "center");
  assert.equal((value?.props.styles as Record<string, unknown>).fontSize, 24);
  assert.equal((value?.props.styles as Record<string, unknown>).lineHeight, 1.25);
  assert.equal((value?.props.styles as Record<string, unknown>).maxLines, 2);
  assert.equal((value?.props.styles as Record<string, unknown>).height, undefined);
  const supportingStyles = graph.getNode("display_supporting")?.props.styles as Record<string, unknown>;
  assert.deepEqual(supportingStyles.margin, { top: 8, right: 0, bottom: 0, left: 0 });
  assert.equal(supportingStyles.flexShrink, 0);
});

test("SecondaryBody 保留绑定、按行布局切换字号并忽略历史角色", () => {
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
  assert.equal(body.fontSize, 12);
  assert.equal(body.fontWeight, 400);
  assert.equal(body.height, 32);
  assert.equal(body.maxLines, 2);
  assert.equal(metadata.fontSize, 14);
  assert.equal(metadata.height, 19);
  const supportingLabel = graph.getNode("supporting_item0_label")?.props.styles as Record<string, unknown>;
  const supportingValue = graph.getNode("supporting_item0_value")?.props.styles as Record<string, unknown>;
  assert.equal(supportingLabel.flexShrink, 0);
  assert.equal(supportingValue.flexShrink, 1);

  const single = compileMiniDsl(
    '["root","SecondaryBody",{"items":[{"value":"正文"}]}]',
  );
  const singleStyles = single.graph.getNode("root_item0_value")?.props.styles as Record<string, unknown>;
  assert.equal(singleStyles.fontSize, 14);
  assert.equal(singleStyles.height, 19);
  const multilineMetadata = compileMiniDsl(
    '["root","SecondaryBody",{"role":"metadata","items":[{"value":"更新时间","maxLines":2}]}]',
  );
  const multilineStyles = multilineMetadata.graph.getNode("root_item0_value")?.props
    .styles as Record<string, unknown>;
  assert.equal(multilineStyles.height, 32);
  assert.equal(multilineStyles.maxLines, 2);
});

for (const color of ["#FFFFFFFF", "#FF000000", "#FF1F4799", "#FF8C4B1C"]) {
  for (const size of ["2x2", "2x4"] as const) {
    test(`SecondaryBody 标签弱化、值强调：${color}/${size}`, () => {
      const source = [
        ["root", "Column", {}, ["details", "note"]],
        ["details", "SecondaryBody", {
          fontColor: color, columns: 1,
          items: [{ label: "天气 ", value: { path: "/condition" } }],
        }],
        ["note", "SecondaryBody", { fontColor: color, items: [{ value: "辅助说明" }] }],
        ["/condition", "多云"],
      ].map(row => JSON.stringify(row)).join("\n");
      const result = compileMiniDsl(source, { size });
      const nodes = result.graph.getAllNodes();
      const label = nodes.get("details_item0_label")?.props.styles as Record<string, unknown>;
      const value = nodes.get("details_item0_value")?.props.styles as Record<string, unknown>;
      const note = nodes.get("note_item0_value")?.props.styles as Record<string, unknown>;
      assert.equal(label.fontColor, `#99${color.slice(3)}`);
      assert.equal(value.fontColor, color);
      assert.equal(note.fontColor, `#99${color.slice(3)}`);
    });
  }
}

const pairedTextParts: Record<string, [string, string]> = {
  SecondaryBody: ["_item0_label", "_item0_value"],
  TableText: ["_row0_label", "_row0_value"],
  TextBlock: ["_item0_label", "_item0_value"],
  H_BarChart: ["_item0_label", "_item0_value"],
  ProgressCircleSingle: ["_label", "_display"],
  DataDisplay: ["_label", "_value"],
  TopTextBottomValue: ["_item0_label", "_item0_value"],
};

for (const [type, [labelSuffix, valueSuffix]] of Object.entries(pairedTextParts)) {
  test(`所有标签值组件使用统一强调层级：${type}`, () => {
    const example = fixtures.examples.find(item => item.source.split("\n")
      .some(line => (JSON.parse(line) as unknown[])[1] === type));
    assert.ok(example, `缺少组件用例：${type}`);
    const component = example.source.split("\n").map(line => JSON.parse(line) as unknown[])
      .find(row => row[1] === type);
    assert.ok(component);
    const result = compileMiniDsl(example.source, { size: example.size as "2x2" | "2x4" });
    const label = result.graph.getNode(`${component[0]}${labelSuffix}`)?.props
      .styles as Record<string, unknown>;
    const value = result.graph.getNode(`${component[0]}${valueSuffix}`)?.props
      .styles as Record<string, unknown>;
    assert.equal(typeof value.fontColor, "string");
    assert.equal(label.fontColor, `#99${String(value.fontColor).slice(3)}`);
    assert.ok(String(value.fontColor).startsWith("#FF"));
  });
}

test("SecondaryBody 支持 1–6 项，保留全部绑定并拒绝超过上限", () => {
  for (const size of ["2x2", "2x4"] as const) {
    for (const columns of [1, 2]) {
      for (const count of [1, 4, 5, 6]) {
        const items = Array.from({ length: count }, (_, index) => ({
          label: `项${index} `, value: { path: `/data/detail${index}` },
        }));
        const dataRows = items.map((item, index) => JSON.stringify([item.value.path, `${index}项`]));
        const source = [
          JSON.stringify(["root", "Column", { width: "matchParent" }, ["details"]]),
          JSON.stringify(["details", "SecondaryBody", {
            items, columns, fontSize: count === 1 ? 14 : 12,
          }]),
          ...dataRows,
        ].join("\n");
        const graph = compileMiniDsl(source, { size }).graph;
        for (const [index, item] of items.entries()) {
          const props = graph.getNode(`details_item${index}_value`)?.props;
          assert.deepEqual(props?.content, item.value);
          const styles = props?.styles as Record<string, unknown>;
          assert.equal(styles.fontSize, count === 1 ? 14 : 12);
          assert.equal(styles.height, count === 1 ? 19 : 16);
        }
      }
    }
  }
  for (const count of [0, 7]) {
    const items = Array.from({ length: count }, () => ({ value: "补充" }));
    assert.throws(() => compileMiniDsl(JSON.stringify(["root", "SecondaryBody", { items }])),
      new RegExp(`SecondaryBody.items 需要 1–6 项，实际 ${count} 项`));
  }
});

test("SecondaryBody 按完整日期与星期自动分行，宽槽保留自然占宽和分隔空格", () => {
  const source = [
    '["root","Column",{"width":"matchParent","padding":12},["meta"]]',
    '["meta","SecondaryBody",{"width":"matchParent","fontSize":14,"items":[{"value":{"path":"/date"}},{"value":"{{ ${/weekday} }}"}]}]',
    '["/date","2026-08-06"]',
    '["/weekday","星期四"]',
  ].join("\n");
  const small = compileMiniDsl(source, { size: "2x2" }).graph;
  assert.deepEqual(small.getNode("meta")?.children, ["meta_row0", "meta_row1"]);
  const smallValue = small.getNode("meta_item0_value")?.props;
  assert.deepEqual(smallValue?.content, { path: "/date" });
  assert.equal((smallValue?.styles as Record<string, unknown>).fontSize, 12);
  assert.equal((smallValue?.styles as Record<string, unknown>).height, 16);
  assert.equal(small.getNode("meta_row0_separator"), null);
  const wide = compileMiniDsl(source, { size: "2x4" }).graph;
  assert.deepEqual(wide.getNode("meta")?.children, ["meta_row0"]);
  assert.equal(wide.getNode("meta_row0_separator")?.props.content, " | ");
  const first = wide.getNode("meta_item0")?.props.styles as Record<string, unknown>;
  const second = wide.getNode("meta_item1")?.props.styles as Record<string, unknown>;
  assert.ok(Number(first.width) > Number(second.width));
});

test("SecondaryBody 长单项声明两行，未知绑定保持原布局", () => {
  for (const [value, font, lines] of [["完整的长补充信息需要自动换行", 12, 2], [{ path: "/unknown" }, 14, 1]]) {
    const source = JSON.stringify(["root", "SecondaryBody", {
      width: 126, fontSize: 14, items: [{ value }],
    }]);
    const graph = compileMiniDsl(source).graph;
    const styles = graph.getNode("root_item0_value")?.props.styles as Record<string, unknown>;
    assert.equal(styles.fontSize, font);
    assert.equal(styles.maxLines, lines);
  }
  const labeled = compileMiniDsl([
    '["root","SecondaryBody",{"width":126,"fontSize":14,"items":[{"label":"更新时间 ","value":{"path":"/updated"}}]}]',
    '["/updated","2026-08-06 09:00"]',
  ].join("\n")).graph;
  assert.equal(labeled.getNode("root_item0_value")?.props.content, "{{ '更新时间 ' + ${/updated} }}");
  assert.equal(labeled.getNode("root_item0_label"), null);
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
    assert.equal(rootStyles.alignItems, "top");
    assert.equal(rootStyles.justifyContent, "start");
    assert.equal(rootStyles.layoutWeight, 1);
    assert.deepEqual(rootStyles.constraintSize, {
      minHeight: 48,
    });
    assert.ok(graph.getNode(`root_item${count - 1}`));
    assert.equal(itemStyles.layoutWeight, 1);
    assert.equal(itemStyles.height, "matchParent");
    assert.equal(itemStyles.backgroundColor, "#99FFFFFF");
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
      },
    ]), { size: "2x4" }),
    /2–4 项/,
  );
  assert.throws(
    () => compileMiniDsl(JSON.stringify([
      "root",
      "TextBlock",
      {
        items: [item(1), item(2)],
        fontColor: "#FF563D99",
        backgroundColor: "#99FFFFFF",
      },
    ]), { size: "2x4" }),
    /不接受 backgroundColor/,
  );
});
