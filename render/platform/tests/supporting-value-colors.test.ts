import assert from "node:assert/strict";
import { test } from "node:test";
import { compileMiniDsl } from "../lib/mini-renderer";

const values: Array<[unknown, boolean]> = [
  [{ path: "/data/custom/value" }, true],
  ["{{ '任意标签 ' + ${/data/custom/value} }}", true],
  ["{{ ('说明 ' + ${/data/custom/value}) + ' 单位' }}", true],
  ["{{ ${/data/custom/state} ? '状态甲' : '状态乙' }}", true],
  [0, true],
  ["数据 ${/data/custom/value} 示例", false],
  ["普通辅助说明", false],
  ["{{ '固定文字' }}", false],
];

const displayVariants = [
  { label: "标题", value: 42 },
  { label: "标题", value: "主区读数" },
  { icon: "resources/base/media/ic_weather_monochrome.svg", value: "主区读数" },
];

for (const color of ["#FFFFFFFF", "#FF000000", "#FF563D99"]) {
  for (const [variant, props] of displayVariants.entries()) {
    for (const [index, [value, emphasize]] of values.entries()) {
      test(`DataDisplay ${color} 模式${variant} 辅助值着色${index}`, () => {
        const build = (content: unknown) => compileMiniDsl(JSON.stringify([
          "root", "DataDisplay", { ...props, supportingText: content, fontColor: color },
        ]), { size: "2x2" }).graph;
        const graph = build(value);
        const baseline = build("普通辅助说明");
        const mainStyles = graph.getNode("root_value")?.props.styles as Record<string, unknown>;
        const supporting = graph.getNode("root_supporting");
        assert.ok(supporting);
        const styles = supporting.props.styles as Record<string, unknown>;
        const ink = String(mainStyles.fontColor);
        assert.equal(styles.fontColor, emphasize ? ink : `#99${ink.slice(3)}`);
        const label = graph.getNode("root_label");
        if (label) {
          assert.equal((label.props.styles as Record<string, unknown>).fontColor,
            `#99${ink.slice(3)}`);
        }
        assert.equal(graph.getAllNodes().size, baseline.getAllNodes().size);
        for (const [id, node] of graph.getAllNodes()) {
          const original = baseline.getNode(id);
          assert.ok(original);
          const current = structuredClone(node.props);
          if (id === "root_supporting") {
            current.content = original.props.content;
            (current.styles as Record<string, unknown>).fontColor =
              (original.props.styles as Record<string, unknown>).fontColor;
          }
          assert.deepEqual(current, original.props);
          assert.deepEqual(node.children, original.children);
        }
      });
    }
  }
}

for (const size of ["2x2", "2x4"] as const) {
  for (const kind of ["EmphasisText", "InfoBlock", "InfoBlock-unit"]) {
    for (const [index, [value, emphasize]] of values.entries()) {
      test(`${size} ${kind} 辅助值着色 ${index}`, () => {
        const type = kind === "InfoBlock-unit" ? "InfoBlock" : kind;
        const props: Record<string, unknown> = type === "EmphasisText"
          ? { mainText: "主读数", fontColor: "#FF563D99" }
          : { primaryText: "主读数", fontColor: "#FF563D99", backgroundColor: "#33000000",
            variant: size === "2x2" ? "stacked" : "slot" };
        if (kind === "InfoBlock-unit") props.unit = "单位";
        const build = (content: unknown) => compileMiniDsl(
          JSON.stringify(["root", type, { ...props, secondaryText: content }]), { size },
        ).graph;
        const graph = build(value);
        const baseline = build("普通辅助说明");
        const mainId = type === "EmphasisText" ? "root_main"
          : kind === "InfoBlock-unit" ? "root_primary_value" : "root_primary";
        const main = graph.getNode(mainId)?.props.styles as Record<string, unknown>;
        const secondary = graph.getNode("root_secondary");
        assert.ok(secondary);
        const secondaryStyles = secondary.props.styles as Record<string, unknown>;
        const ink = String(main.fontColor);
        assert.equal(secondaryStyles.fontColor, emphasize ? ink : `#99${ink.slice(3)}`);
        assert.equal(graph.getAllNodes().size, baseline.getAllNodes().size);
        for (const [id, node] of graph.getAllNodes()) {
          const original = baseline.getNode(id);
          assert.ok(original);
          const props = structuredClone(node.props);
          if (id === "root_secondary") {
            props.content = original.props.content;
            (props.styles as Record<string, unknown>).fontColor =
              (original.props.styles as Record<string, unknown>).fontColor;
          }
          assert.deepEqual(props, original.props);
          assert.deepEqual(node.children, original.children);
        }
      });
    }
  }
}
