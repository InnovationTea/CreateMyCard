import assert from "node:assert/strict";
import { test } from "vitest";
import { compileMiniDsl, SURFACE_ID } from "../src/runtime/mini-renderer";
import { EXAMPLE_DSL } from "./fixtures/example-dsl";
import { resolvePathBindingsInValue, runActionDispatch } from "@genui-sdk/interactions";

test("user countdown DSL preserves literals and resolves explicit data paths", () => {
  const { graph, warnings, count, jsonl } = compileMiniDsl(EXAMPLE_DSL);
  assert.equal(count, 10);
  assert.deepEqual(warnings, []);
  const leaf = (path: string) => graph.getDataModelValue(SURFACE_ID, path);
  assert.equal(resolvePathBindingsInValue(graph.getNode("title_text")!.props.content, leaf), "产品发布会");
  assert.equal(resolvePathBindingsInValue(graph.getNode("value_num")!.props.content, leaf), 18);
  assert.equal(graph.getNode("value_unit")!.props.content, "天");
  assert.equal(graph.getNode("action")!.props.label, "查看详情");
  assert.equal(graph.getNode("action")!.type, "Extended.Button");
  assert.ok(jsonl.includes('"updateDataModel"'));
});

test("intent arguments resolve at click time after data updates", async () => {
  const { graph } = compileMiniDsl(EXAMPLE_DSL);
  const calls: unknown[] = [];
  graph.setDataModelValue(SURFACE_ID, "/data/calendar/events/0/entityId", "event-002");
  const action = graph.getNode("action")!.props.action;
  await runActionDispatch(action, { functionCall: call => { calls.push(call); } }, {
    componentId: "action", surfaceId: SURFACE_ID, getDataModelLeaf: path => graph.getDataModelValue(SURFACE_ID, path),
  });
  assert.deepEqual(calls, [{ call: "clickToIntent", args: { intentName: "ViewCalendarEvent", params: { entityId: "event-002" } }, componentId: "action" }]);
});

test("data can precede components; nested array and escaped JSON pointer bindings work", () => {
  const source = '["/",{"data":{"events":[{"title":"数组标题"}],"a/b":0}}]\n["root","Text",{"content":{"path":"/data/events/0/title"}}]';
  const { graph } = compileMiniDsl(source);
  assert.equal(graph.getDataModelValue(SURFACE_ID, "/data/events/0/title"), "数组标题");
  assert.equal(graph.getDataModelValue(SURFACE_ID, "/data/a~1b"), 0);
});

test("bindings preserve falsy values, recursively resolve templates and safely handle missing paths", () => {
  const data: Record<string, unknown> = { "/zero": 0, "/false": false, "/name": "发布会" };
  const leaf = (path: string) => data[path];
  assert.deepEqual(resolvePathBindingsInValue([{ path: "/zero" }, { path: "/false" }, { path: "/missing" }], leaf), [0, false, ""]);
  assert.equal(resolvePathBindingsInValue('活动：{{ ${/name} + "！" }}', leaf), "活动：发布会！");
  assert.throws(() => resolvePathBindingsInValue('{{ alert(1) }}', leaf), /不支持/);
});

test("multiline tuples, JSON tuple arrays and fenced input compile", () => {
  const row = ["root", "Text", { content: "literal" }];
  for (const source of [JSON.stringify(row, null, 2), JSON.stringify([row]), '```jsonl\n' + JSON.stringify(row) + '\n```']) {
    assert.equal(compileMiniDsl(source).graph.getRoot()!.props.content, "literal");
  }
});

test("invalid JSON, unsupported components and broken/cyclic trees report errors", () => {
  for (const source of ['["root",', '["root","NoSuchComponent",{}]', '["root","Column",{},["missing"]]', '["root","Column",{},["a"]]\n["a","Column",{},["root"]]', '["root","Text",{}]\n["root","Text",{}]']) assert.throws(() => compileMiniDsl(source));
  assert.deepEqual(compileMiniDsl('["root","Text",{"content":{"path":"/absent"}}]').warnings, ["未找到数据：/absent"]);
});
