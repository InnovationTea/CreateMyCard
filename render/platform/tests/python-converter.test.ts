import assert from "node:assert/strict";
import { test } from "node:test";
import {
  compileCompactDslForPreview,
  compileCompactDslWithPython,
} from "../lib/python-converter";

const PYTHON_A2UI = [
  {
    version: "v0.9",
    createSurface: {
      surfaceId: "python-preview",
      catalogId: "ohos.a2ui.extended.catalog",
    },
  },
  {
    version: "v0.9",
    updateComponents: {
      surfaceId: "python-preview",
      root: "root",
      components: [{
        id: "root",
        component: "Extended.Button",
        child: "正式结果",
        onClick: [{ call: "openDetails", args: { id: "42" } }],
      }],
    },
  },
].map(row => JSON.stringify(row)).join("\n");

test("正式 Python 转换结果由平台 UIGraph 直接渲染", async () => {
  let requestBody: Record<string, unknown> | undefined;
  const result = await compileCompactDslWithPython(
    '["root","SingleLineTitle",{"title":"标题"}]',
    {
      size: "2x4",
      endpoint: "/test-convert",
      fetchImpl: async (input, init) => {
        assert.equal(input, "/test-convert");
        requestBody = JSON.parse(String(init?.body)) as Record<string, unknown>;
        return Response.json({ genui: PYTHON_A2UI, size: "2x4" });
      },
    },
  );
  assert.equal(requestBody?.size, "2x4");
  assert.equal(result.size, "2x4");
  assert.equal(result.count, 1);
  assert.equal(result.graph.getRoot()?.props.child, "正式结果");
  assert.deepEqual(result.graph.getRoot()?.props.action, [{
    functionCall: { call: "openDetails", args: { id: "42" } },
  }]);
  assert.equal(result.graph.getRoot()?.props.onClick, undefined);
  assert.equal(result.jsonl, PYTHON_A2UI);
});

test("正式转换错误不静默回退到 TypeScript", async () => {
  await assert.rejects(
    compileCompactDslWithPython('["root","Text",{}]', {
      size: "2x2",
      fetchImpl: async () => Response.json({ detail: "Text 不允许直接提交" }, { status: 422 }),
    }),
    /正式 Python 转换失败：Text 不允许直接提交（HTTP 422）/,
  );
});

test("页面预览在正式转换以 422 拒绝后使用宽松本地展开", async () => {
  const source = [
    '["root","Column",{},["battery"]]',
    '["battery","InfoBlock",{"primaryText":"{{ \'手机电量 \' + ${/data/battery} + \'%\' }}","secondaryText":"未充电","backgroundColor":"#99FFFFFF","visual":{"type":"progressCircle","icon":"resources/base/media/battery.svg"}}]',
    '["/data/battery",68]',
  ].join("\n");
  const result = await compileCompactDslForPreview(source, {
    size: "2x2",
    fetchImpl: async () => Response.json({
      detail: "battery: InfoBlock.primaryText 必须是 0–100 有限数值或完整数值百分比。",
    }, { status: 422 }),
  });

  assert.equal(result.graph.getNode("battery_visual_progress")?.props.value, 68);
  assert.match(result.warnings[0], /已切换为宽松预览/);
  assert.ok(result.warnings.some(message => message.includes("宽松预览已使用 68")));
});

test("无法连接正式转换器时给出可执行提示", async () => {
  await assert.rejects(
    compileCompactDslWithPython('["root","Text",{}]', {
      size: "2x2",
      fetchImpl: async () => { throw new TypeError("fetch failed"); },
    }),
    /请启动 Debug Tools，或显式切换到本地 TS/,
  );
});

test("拒绝缺少 genui 的伪成功响应", async () => {
  await assert.rejects(
    compileCompactDslWithPython('["root","Text",{}]', {
      size: "2x2",
      fetchImpl: async () => Response.json({ size: "2x2" }),
    }),
    /返回了无效结果/,
  );
});
