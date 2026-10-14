import assert from "node:assert/strict";
import { test } from "node:test";
import { PREVIEW_CARD_SIZE_PRESETS, previewDimensionsFor } from "../lib/card-size";

test("Renderer 的 2x2 与 2x4 使用标准预览尺寸", () => {
  assert.deepEqual(previewDimensionsFor("2x2"), { width: 150, height: 150 });
  assert.deepEqual(previewDimensionsFor("2x4"), { width: 300, height: 150 });
  assert.deepEqual(PREVIEW_CARD_SIZE_PRESETS, {
    "2x2": { width: 150, height: 150 },
    "2x4": { width: 300, height: 150 },
  });
});
