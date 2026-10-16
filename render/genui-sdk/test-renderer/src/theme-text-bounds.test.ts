import assert from "node:assert/strict";
import { test } from "node:test";
import { textBound } from "./theme-text-bounds";

test("static text is not an unbounded dynamic slot", () => {
  assert.equal(textBound("weather", {}).dynamic, false);
});

test("enum contracts include missing data", () => {
  const bound = textBound({ path: "/data/state" }, { data: { state: { enum: ["sun", "cloudy"] } } });
  assert.deepEqual(bound.candidates, ["sun", "cloudy", ""]);
});

test("preview samples do not constrain future text", () => {
  const bound = textBound({ path: "/data/state" }, { data: { state: { type: "string", sampleValue: "sun" } } });
  assert.equal(bound.reason, "unbounded-field");
  assert.equal(bound.candidates, undefined);
});

test("integer ranges enumerate all values", () => {
  const bound = textBound({ path: "/data/days" }, { data: { days: { type: "integer", minimum: 0, maximum: 3 } } });
  assert.deepEqual(bound.candidates, ["0", "1", "2", "3", ""]);
});

test("large integer ranges fall back to a slot", () => {
  const bound = textBound({ path: "/data/days" }, { data: { days: { type: "integer", minimum: 0, maximum: 10000 } } });
  assert.equal(bound.reason, "unbounded-field");
});

test("boolean expressions use the production parser", () => {
  const bound = textBound("{{ ${/data/ready} ? 'ready' : 'waiting' }}", { data: { ready: { type: "boolean" } } });
  assert.deepEqual(new Set(bound.candidates), new Set(["ready", "waiting"]));
});

test("multiline outputs are not treated as single-line bounds", () => {
  const bound = textBound({ path: "/data/state" }, { data: { state: { enum: ["a\nb"] } } });
  assert.equal(bound.reason, "multiline-or-long-output");
});

test("JSON schema properties and escaped pointers are supported", () => {
  const bound = textBound({ path: "/data/a~1b" }, { properties: { data: { properties: { "a/b": { enum: ["ok"] } } } } });
  assert.deepEqual(bound.candidates, ["ok", ""]);
});
