---
name: harmony-card-generation-path-first
description: "生成、修复、评审或解释 HarmonyOS A2UI Form 服务卡片输出的 path 优先旧版 skill。用于需要保留原始数据绑定优先级（优先使用 A2UI 原生 {path}/formatString，表达式兜底）并产出同一张卡片的 genui JSONL 和 cardspec JSON，严格保证 DSL/CardSpec 语法正确、Form 组件/绑定/事件/数据契约合法、2x2 或 2x4 尺寸内渲染美观且上线可用的任务。"
---

# Harmony 卡片生成（Path 优先版）

产出同一张 Form 卡片。交付必须同时满足：可解析、可渲染、信息不重复、文本不截断、布局不错位、颜色有来源。

## 执行顺序

1. 默认先读 `reference/core-rules.md`；它不足以解决当前阻塞点时，按“专项参考”逐个加载最小必要文件，解决一个阻塞点后再判断是否需要下一个。
2. 先定取舍：一个主答案、最多 2 条支撑事实、最多 1 个主动作；每个可见组件只承载一个信息职责，同一事实不要换单位、别名、同义标签、聚合/拆分或派生文案重复展示。
3. 写 DSL 前先算硬预算：surface/root 尺寸一致，root shell 完整，内容区、padding、margin、itemMargin、按钮热区、受保护文本、Text+Button 并排宽高、颜色来源都能推导。
4. 起草后做模型内置校验：先过协议、绑定、布局、颜色、事件和尺寸，再查信息职责和事实等价类。不要为了校验新建、输出或保留草稿文件。
5. 只有用户明确要求校验既有文件、修复本地草稿或调试脚本时，才运行 `scripts/validate_card.py`。

最终回答只给最终 DSL/CardSpec，不输出解释、校验日志、命令或中间文件。

## 输出形态

只输出两个代码块，顺序固定：

```genui
{"version":"v0.9","createSurface":{...}}
{"version":"v0.9","updateComponents":{"surfaceId":"...","root":"...","components":[...]}}
{"version":"v0.9","updateDataModel":{...}}
```

```cardspec
{
  "suggestSize": "2x2"
}
```

静态卡片也输出 `cardspec`，但不要虚构 `dataBindings`。

## 专项参考

按当前阻塞点逐个读取最小必要文件；进入专项文件后先看顶部决策、阻断或使用规则，再查 schema、表格和示例。不要一次性泛读无关参考。

- 组件/样式枚举：`reference/protocol/component-catalog.md`；协议冲突兜底：`reference/protocol/protocol.md`。
- DataModel、路径、模板、事件参数：`reference/protocol/data-binding.md`；`formatString`：`reference/protocol/function.md`。
- 点击、拨号、跳转、动作区：`reference/capability/event-capability/click-event.md`。
- CardSpec、动态数据能力：`reference/capability/cardspec.md`；涉及数据能力时，按场景逐个读取对应 data-capability 文件。
- 布局承载、按钮对齐、底部贴底、重叠、留白：`reference/design/layout-system.md`。
- 颜色、深浅色、渐变 stop、token 来源：`reference/design/color-token-system.md`。
- 图片、图标、背景图、素材路径：`reference/design/asset-library.md`。
- 无 L0/L1 问题但视觉弱：`reference/design/design-heuristics.md`。
- 最终人工复核：`reference/final-blockers.md`；路由仍不清楚：`reference.md`。

## 降级原则

低能力模型或高风险需求优先降级自由度：少组件、少层级、少颜色、少动态路径、少 Stack。宁可输出简洁卡片，也不要输出语法不合规、文本显示不全、颜色无来源或明显错位的卡片。
