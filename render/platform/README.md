# 独立卡片渲染器

`render/platform` 用于粘贴 Compact DSL、检查正式 A2UI 和对照组件视觉。卡片运行时直接使用仓库根目录
`render/genui-sdk`；Compact DSL 默认通过 Debug Tools 的正式 Python 转换接口处理，不再把本地
TypeScript 编译器作为视觉验收依据。

## 启动

先从仓库根目录启动正式转换接口：

```bash
uv run debug_tools --mode frontend --host 127.0.0.1 --port 8888
```

再启动独立渲染器：

```bash
cd render/platform
npm run dev
```

打开 <http://127.0.0.1:3000/>。页面默认选择“正式优先”：合法 DSL 使用正式 Python 转换结果；仅当正式
转换器以 422 拒绝组件合同时，页面自动改用本地宽松预览，并明确显示警告。宽松预览只用于查看被拒绝
DSL 的大致视觉，不改变云侧校验、正式转换器或生成结果；JSON 语法和组件树等无法恢复的错误仍会阻断。
“本地 TS”保留严格模式，只用于离线开发和差异排查。

如果转换接口不在默认的 `127.0.0.1:8888`，启动平台前指定完整地址：

```bash
COMPACT_CONVERTER_URL=http://127.0.0.1:8890/debug/renderer/convert npm run dev
```

## 验证

```bash
npm test
npm run build
```

Debug Tools 还会在自身测试前执行 Renderer Runtime 同步门禁，确保其 Web Runtime 与这里使用的
`render/genui-sdk` 一致；同步方法见 `debug_tools/card_renderer/runtime/SOURCE.md`。
