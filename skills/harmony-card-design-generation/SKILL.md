---
name: harmony-card-design-generation
description: "使用分层卡片设计系统生成 HarmonyOS A2UI Form 服务卡片。用于用户显式调用本 Skill，并要求主 Agent 按自然语言 query 依次提取卡片特征、选择 2x2/2x4 固定布局、分配兼容模块、选择受控元素尺寸和填充内容，再通过确定性装配生成三行 genui JSONL 与 cardspec JSON；支持已声明的数据能力、点击事件和本地素材，但不调用 harmony-card-generation-online 或 harmony-card-generation-offline。"
---

# Harmony 卡片分层设计生成

按“特征 -> 布局 -> 模块 -> 元素 -> 内容”的顺序生成内部 `design-plan-v1`，再调用脚本确定性装配 DSL 与 CardSpec。不要调用或读取其它卡片生成 Skill，不要直接手写最终 DSL。

## 执行流程

1. 读取 `references/generation-contract.md`，把 query 收敛为唯一服务对象、唯一主问题和 Feature Profile。为每个内容项分配稳定 ID、角色及 `mustKeep/shouldKeep`。
2. 读取 `references/routing-and-style.md`。运行 `python scripts/query_design_system.py --layouts --size <2x2|2x4>`，按主模块数量和信息关系选择一个布局。
3. 对布局的每个 region 运行 `python scripts/query_design_system.py --compatible-modules <layout-id> <region-id>`。只选择返回的精确 footprint 模块。
4. 对每个模块运行 `python scripts/query_design_system.py --module <module-id> --variant <variant-id>`，为所有实际节点选择 `allowedTokens` 中的 element token，并把 Feature Profile 内容映射到模块槽位。
5. 需要动态数据时读取 `references/capability/cardspec.md` 和数据能力索引，再只读取命中的 1-2 个能力文件。`2x2` 最多一个数据能力，`2x4` 最多两个。
6. 需要点击时读取 `references/capability/event-capability/click-event.md`；需要素材时读取 `references/design/asset-library.md`；需要颜色语义时读取 `references/design/color-token-system.md`。未声明能力必须静态降级。
7. 按 `references/template-contract.md` 写内部 Design Plan JSON。Design Plan 不向用户展示，也不得包含布局、模块或 element token 未声明的组件、宽高、字号或样式。
8. 运行 `python scripts/assemble_card.py <design-plan.json> --genui-out <genui.jsonl> --cardspec-out <cardspec.json>`。装配失败时只修改 Design Plan。
9. 运行 `python scripts/validate_card.py --dsl <genui.jsonl> --cardspec <cardspec.json> --design-plan <design-plan.json> --strict`。首次失败时按诊断修改 Design Plan 并重新装配一次；第二次仍失败则不输出产物。
10. 最终先给一句面向用户的布局、视觉风格和必要降级说明，再输出一个 `genui` 代码块和一个 `cardspec` 代码块。不要暴露布局 ID、模块 ID、element token、能力 ID、Design Plan 或校验日志。

## 选择门槛

- Feature Profile 必须只有一个服务对象和一个主问题。
- 未指定尺寸先尝试 `2x2`；受保护文本、并列关系、关键媒体或动作热区无法成立时使用 `2x4`。
- `2x2` 最多三个顶层模块，`2x4` 最多四个。
- 模块 role 必须在 region 允许列表中，variant footprint 必须与 region 宽高完全相等。
- 每个实际元素节点必须选择模块声明的 token；不得在 Design Plan 中直接写组件类型或尺寸。
- 所有 `mustKeep` 内容恰好映射一次；删除 `shouldKeep` 时在 `degradations` 中记录内容 ID 和原因。
- 动作数、数据能力数、素材和文本预算必须同时满足 Feature Profile、布局和模块槽位约束。

无合法组合时，依次删除 `shouldKeep`、选择同尺寸更简单布局、尝试 `2x4`。仍不成立时说明需要简化需求，不调用其它 Skill，也不退回自由生成。

## 不可妥协项

- `genui` 恰好三行：`createSurface`、`updateComponents`、`updateDataModel`。
- `version` 为 `v0.9`，`catalogId` 为 `ohos.a2ui.extended.catalog.form`。
- `createSurface.width/height` 与 root `styles.width/height` 为 `matchParent`。
- CardSpec 只包含静态短标题、静态短描述、`suggestSize` 和有效 `dataBindings`。
- 点击事件只写 DSL `onClick`；不写入 CardSpec。
- 不使用网络图、内联/base64 图、emoji、未声明素材、未声明事件、`theme`、`Button.action` 或 Form 子集外组件。
- 不直接编辑装配后的 DSL，不跨模块复制节点，不伪造动态能力。

## 按需参考

- Design Plan、布局、模块和元素契约：`references/template-contract.md`
- 消息、组件与表达式：`references/protocol/protocol.md`、`references/protocol/component-catalog.md`、`references/protocol/data-binding.md`
- 布局、构图和色彩：`references/design/layout-system.md`、`references/design/design-heuristics.md`、`references/design/color-token-system.md`
- 方案维护说明：`方案设计.md`，只在维护本 Skill 时读取。

## 输出形态

```genui
{"version":"v0.9","createSurface":{...}}
{"version":"v0.9","updateComponents":{...}}
{"version":"v0.9","updateDataModel":{...}}
```

```cardspec
{"title":"状态卡片","description":"状态概览","suggestSize":"2x2"}
```
