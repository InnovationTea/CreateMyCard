import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";
import { test } from "node:test";

const enabled = Boolean(process.env.THEME_PLAYWRIGHT_MODULE && process.env.THEME_BROWSER_EXECUTABLE);
const cli = resolve(__dirname, "../../node_modules/tsx/dist/cli.mjs");
const config = resolve(__dirname, "../../tsconfig.base.json");
const entry = resolve(__dirname, "measure-theme.tsx");

function text(id: string, content: any, styles = {}) {
  return { id, component: "Text", content, styles: {
    fontSize: 12, fontColor: "#FFFFFFFF", maxLines: 1, width: "matchParent", ...styles,
  } };
}

function measure(size: string, nodes: any[], schema = {}, data: any = { value: "23:15" }, rootStyles = {},
  viewport = { width: size === "2x4" ? 362 : 181, height: 181 }) {
  const source = [
    { version: "v0.9", createSurface: {
      surfaceId: "test", catalogId: "ohos.a2ui.extended.catalog.form",
    } },
    { version: "v0.9", updateComponents: { surfaceId: "test", root: "root", components: [
      { id: "root", component: "Column", children: [nodes[0].id], styles: {
        width: "matchParent", height: "matchParent", padding: 12, alignItems: "start", ...rootStyles,
      } }, ...nodes,
    ] } },
    { version: "v0.9", updateDataModel: { surfaceId: "test", path: "/", value: { data } } },
  ].map(row => JSON.stringify(row)).join("\n");
  const result = spawnSync(process.execPath, [cli, "--tsconfig", config, entry], {
    input: JSON.stringify({ source, size, viewport,
      dataModelSchema: { data: schema },
      dynamicTextReservation: { mode: "contract-or-estimated" }, buttonIds: ["button"]
        .filter(id => nodes.some(node => node.id === id)),
    }),
    encoding: "utf8", timeout: 45000,
  });
  assert.equal(result.status, 0, result.stderr || String(result.error));
  return JSON.parse(result.stdout);
}

function close(actual: number, expected: number) {
  assert.ok(Math.abs(actual - expected) < 0.03, `${actual} != ${expected}`);
}

test("diagnostics require an explicit viewport instead of guessing from card size", () => {
  const result = spawnSync(process.execPath, [cli, "--tsconfig", config, entry], {
    input: JSON.stringify({ size: "2x4" }), encoding: "utf8", timeout: 45000,
  });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /Explicit test viewport width and height are required/);
});

for (const [size, width, height, asset] of [
  ["2x2", 163, 197, "bg_ux_sleep_square.jpg"],
  ["2x4", 389, 181, "bg_ux_sport_center_wide.jpg"],
] as const) {
  test(`${size}: matchParent background fills a supplied nonstandard viewport`, { skip: !enabled }, () => {
    const evidence = measure(size, [{ id: "photo", component: "Image",
      src: `resources/base/media/${asset}`,
      styles: { width: "matchParent", height: "matchParent", objectFit: "fill" },
    }], {}, {}, { padding: 0 }, { width, height });
    assert.equal(evidence.basis, "explicit-test-viewport");
    assert.equal(evidence.deviceGeometryKnown, false);
    assert.deepEqual(evidence.viewport, { width, height });
    const photo = evidence.occupied.find((item: any) => item.id === "photo");
    assert.ok(photo);
    const imageRect = [photo.rect[0] + 2 / width, photo.rect[1] + 2 / height,
      photo.rect[2] - 4 / width, photo.rect[3] - 4 / height];
    [0, 0, 1, 1].forEach((value, index) => close(imageRect[index], value));
    assert.deepEqual(evidence.unsafe, []);
  });
}

function checkGrowth(evidence: any, id: string, anchor = "left") {
  const glyph = evidence.visible.find((item: any) => item.id === id).rect;
  const reservation = evidence.textReservations[id].reserved;
  const width = evidence.viewport.width;
  const extra = Math.max(6, glyph[2] * width * 0.15) / width;
  close(reservation[2] * width, (glyph[2] + extra) * width);
  const offset = anchor === "center" ? extra / 2 : anchor === "right" ? extra : 0;
  close(reservation[0] * width, (glyph[0] - offset) * width);
  close(reservation[1], glyph[1]);
  close(reservation[3], glyph[3]);
  assert.equal(evidence.textReservations[id].reason, "estimated-current-glyphs");
}

for (const size of ["2x2", "2x4"]) {
  test(`${size}: dynamic text uses glyph width, not matchParent slot`, { skip: !enabled }, () => {
    const evidence = measure(size, [text("value", "{{ ${/data/value} }}")]);
    checkGrowth(evidence, "value");
    assert.ok(evidence.textReservations.value.reserved[2] < evidence.textReservations.value.slot[2] / 2);
    assert.deepEqual(evidence.unsafe, []);
  });

  test(`${size}: long text has no 65 percent threshold`, { skip: !enabled }, () => {
    const evidence = measure(size, [text("value", "{{ ${/data/value} }}", { width: 100 })],
      {}, { value: "123456789012" });
    checkGrowth(evidence, "value");
    assert.ok(evidence.textReservations.value.reserved[2] > 65 / evidence.viewport.width);
    assert.ok(evidence.textReservations.value.reserved[2] < 100 / evidence.viewport.width);
  });

  test(`${size}: an inline value never expands left to its parent's label`, { skip: !enabled }, () => {
    const evidence = measure(size, [
      { id: "row", component: "Row", children: ["label", "value"], styles: {
        width: "matchParent", alignItems: "start", justifyContent: "start",
      } },
      text("label", "Sleep ", { width: "wrapContent" }),
      text("value", "{{ ${/data/value} }}", { width: "wrapContent", layoutWeight: 1 }),
    ]);
    checkGrowth(evidence, "value");
    assert.ok(evidence.textReservations.value.reserved[0] > 12 / evidence.viewport.width);
  });
}

for (const align of ["center", "end"]) {
  test(`dynamic ${align} text keeps its actual anchor`, { skip: !enabled }, () => {
    const evidence = measure("2x4", [text("value", "{{ ${/data/value} }}", { textAlign: align })]);
    checkGrowth(evidence, "value", align === "end" ? "right" : align);
    assert.deepEqual(evidence.unsafe, []);
  });
}

test("multiline dynamic content reserves each glyph line, not its row", { skip: !enabled }, () => {
  const evidence = measure("2x4", [text("value", "{{ ${/data/value} }}", {
    width: 80, maxLines: 3,
  })], {}, { value: "alpha beta gamma delta epsilon" });
  const boxes = evidence.visible.filter((item: any) => item.id === "value");
  const reserved = evidence.textReservations.value.reservedRects;
  assert.ok(boxes.length > 1);
  assert.equal(reserved.length, boxes.length);
  for (let index = 0; index < boxes.length; index++) {
    const width = boxes[index].rect[2] * evidence.viewport.width;
    close(reserved[index][2] * evidence.viewport.width, width + Math.max(6, width * 0.15));
  }
});

test("empty unknown dynamic content is unsafe, not blank and not a full slot", { skip: !enabled }, () => {
  const evidence = measure("2x4", [text("value", "{{ ${/data/value} }}")], {}, { value: "" });
  assert.ok(evidence.unsafe.includes("unmeasured-dynamic-text:value"));
  assert.deepEqual(evidence.textReservations.value.reservedRects, []);
  assert.equal(evidence.occupied.some((item: any) => item.id === "value"), false);
});

test("finite contracts use measured candidates without a slot fallback", { skip: !enabled }, () => {
  const evidence = measure("2x4", [text("value", "{{ ${/data/value} }}", { width: 20 })],
    { value: { type: "string", enum: ["x", "longer text"] } }, { value: "x" });
  const reservation = evidence.textReservations.value;
  assert.equal(reservation.reason, "finite-contract");
  assert.ok(reservation.reserved[2] > reservation.slot[2]);
  close(reservation.reserved[0], evidence.visible[0].rect[0]);
});

test("empty finite values still reserve the measured future candidates", { skip: !enabled }, () => {
  const evidence = measure("2x4", [text("value", "{{ ${/data/value} }}")],
    { value: { type: "string", enum: ["sleep", "awake"] } }, { value: "" });
  assert.equal(evidence.textReservations.value.reason, "finite-contract");
  assert.ok(evidence.textReservations.value.reserved[2] > 0);
  assert.deepEqual(evidence.unsafe, []);
});

test("automatic numbers reserve downstream units and icons without moving them", { skip: !enabled }, () => {
  const evidence = measure("2x4", [
    { id: "row", component: "Row", children: ["value", "unit", "icon"], styles: {
      width: "matchParent", justifyContent: "start", alignItems: "start",
    } },
    text("value", "{{ ${/data/value} }}", { width: "wrapContent" }),
    text("unit", "steps", { width: "wrapContent" }),
    { id: "icon", component: "Image", src: "resources/base/media/alarm_fill_1.svg",
      styles: { width: 20, height: 20, objectFit: "contain" } },
  ], {}, { value: "6200" });
  checkGrowth(evidence, "value");
  const growth = evidence.horizontalGrowth.value;
  assert.ok(growth > 0);
  const unit = evidence.visible.find((item: any) => item.id === "unit");
  const occupied = evidence.occupied.find((item: any) => item.id === "unit");
  close(occupied.rect[2], unit.rect[2] + 4 / evidence.viewport.width + growth);
  const icon = evidence.occupied.find((item: any) => item.id === "icon");
  close(icon.rect[2], 24 / evidence.viewport.width + growth);
});

test("whole buttons remain occupied, independent of their short labels", { skip: !enabled }, () => {
  const evidence = measure("2x4", [
    { id: "button", component: "Stack", children: ["label"], styles: {
      width: 120, height: 40, alignContent: "center", backgroundColor: "#33FFFFFF",
    } }, text("label", "Go", { width: "wrapContent" }),
  ]);
  assert.equal(evidence.buttonPolicy, "whole-button");
  const button = evidence.occupied.find((item: any) => item.kind === "button");
  close(button.rect[2] * evidence.viewport.width, 124);
  close(button.rect[3] * evidence.viewport.height, 44);
});
