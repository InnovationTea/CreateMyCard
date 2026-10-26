import assert from "node:assert/strict";
import { test } from "node:test";
import { compileMiniDsl } from "../lib/mini-renderer";

const values: Array<[unknown, boolean]> = [
  [{ path: "/data/custom/value" }, true],
  ["{{ '任意标签 ' + ${/data/custom/value} }}", true],
  ["{{ ('说明 ' + ${/data/custom/value}) + ' 单位' }}", true],
  ["{{ ${/data/custom/state} ? '状态甲' : '状态乙' }}", true],
  [0, true],
  ["普通辅助说明", false],
  ["{{ '固定文字' }}", false],
];

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
