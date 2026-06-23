# 最终评审

## 目的

首版草稿形成 `genui` 与 `cardspec` 两个代码块后，使用本文档作为唯一最终评审入口。本文档负责编排设计评审、协议一致性评审、受保护文本评审、CardSpec 对齐评审和最终阻塞项。整个评审在当前上下文中完成，不创建临时文件、中间文件或其他卡片产物。

## 职责边界

- 协议一致性：按 [`protocol.md`](protocol.md)、[`component-catalog.md`](component-catalog.md) 和 [`data-binding.md`](data-binding.md) 评审。
- CardSpec 对齐：按 [`cardspec.md`](cardspec.md) 评审。
- 视觉、交互、数据语义质量：按 [`design-review.md`](design-review.md) 评审。
- 受保护文本和最终阻塞项：按本文档评审。

## 端到端流程

1. 读取当前上下文中的 `genui` 和 `cardspec` 草稿；不要写入文件，也不要从记忆重新起草。
2. 读取 [`design-review.md`](design-review.md)，评审视觉、交互和数据语义。
3. 按本文档评审协议一致性、受保护内容换行、CardSpec 对齐和最终阻塞项。
4. 直接修复当前上下文中的草稿。
5. 如果任何评审修改了内容，重新检查受影响的评审项。
6. 所有阻塞项解决后，由模型在最终回复中直接输出结果。

## 协议阻塞项

以下任一项失败都不能交付：

- 输出不是 JSONL，或每行不止一个 object。
- `version` 不是 `"v0.9"`。
- `createSurface.catalogId` 不是 `ohos.a2ui.extended.catalog`。
- `createSurface` 包含 `theme`。
- 同一 surface 有多次 `updateComponents`。
- `surfaceId` 不一致。
- component ID 重复或 child 引用不可解析。
- 使用 Form 10 个支持组件之外的组件。
- 使用 `Text.text`、`Image.url`、`Button.child`、`Button.action` 或 CSS kebab-case 样式键。
- 使用 `onClick` 之外的事件。
- `onClick.call` 没有来自 event capability 或明确宿主声明。
- 事件 `args` 使用了未在对应 `parameters` 中声明的参数，或跳转目标不在 `supportedTargets` 中。
- 事件参数路径无法从 DataModel 推导，或本应来自 data capability 输出却无法从 `writeResultTo + outputSchema` 推导。
- 使用 `$__widthBreakpoint`、`$__colorMode`、网络图片 URL、SVG 或占位媒体 URL。
- 使用未由用户提供、未在 [`asset-library.md`](asset-library.md) 声明、编造相似路径或与当前场景语义不匹配的资源路径。

## 卡片阻塞项

以下任一项失败都需要修改或转入能力边界说明：

- 未明确选择 `2x2` 或 `2x4`。
- `2x2` 主区域超过 3 个，或 `2x4` 主区域超过 4 个。
- 主要信息需要滚动、长列表、表格、段落或页面导航才能理解。
- 卡片由示例/模板改造而来，而不是由语义角色和构图规则生成。
- 正式输出前没有布局理由或没有至少一次显式改进。
- 可点击视觉区域没有 `onClick` EventHandler。

## CardSpec 阻塞项

以下任一项失败都不能交付：

- 缺少 `cardspec` 代码块，或 `cardspec` 不是一个 JSON object。
- `suggestSize` 与 DSL 尺寸选择不一致。
- 静态卡片虚构 `dataBindings` 或 `refreshPlan`。
- 动态卡片缺少 `dataBindings`。
- `capabilityId`、`capabilityVersion` 或 `arguments` 没有来自已声明能力。
- `writeResultTo` 不在 `/data` 下。
- DSL 中 UI 绑定路径无法从 CardSpec 的 `writeResultTo` 和能力 `outputSchema` 推导；静态卡片则必须能从初始 DataModel 推导。
- `refreshPlan` 引用不存在的 `bindingId`。
- CardSpec 包含 event capability、`functionCall`、`supportedTargets` 或点击事件清单内容。事件能力只进入 DSL `onClick`。

## 受保护内容换行评审

对每个横向布局：

1. 列出该行中的受保护内容：日期、星期、CTA、时间、状态、百分比、价格、短标签、主数字、主标题和用户要求字段。
2. 检查它是否位于狭窄固定宽容器中。
3. 检查它是否使用 `textOverflow: "ellipsis"`、`clip` 或 marquee。对受保护内容来说，这是阻塞问题。
4. 检查弱文本是否会先于受保护内容压缩。
5. 按此顺序修复：
   - 加宽受保护列
   - 缩短或移动弱文本
   - 减少 padding、`itemMargin`、分隔线宽度和装饰性固定列
   - 在层级内降低字号
   - 把该行拆成 `Column`
   - 选择 `2x4`，或在受保护文本仍无法完整显示时升级说明

不要接受受保护短短语逐字换行。不要接受受保护文本显示为 `...`。

## 用户需求优先例外

如果用户明确要求有风险的布局或看起来不受支持的细节：

- 使用尽可能小的受限例外。
- 保持协议约束生效。
- 在内部评审中记录这个例外；最终回复仍只输出规定的代码块。
