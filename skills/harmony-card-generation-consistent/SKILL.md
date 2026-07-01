---
name: harmony-card-generation-consistent
description: "生成、修复、评审或解释 HarmonyOS A2UI Form 服务卡片的高一致性 skill。用于需要产出同一张卡片的 genui JSONL 和 cardspec JSON，并希望不同模型在同一需求下尽量稳定选择尺寸、信息取舍、path/formatString 绑定、模板骨架、Form 组件、事件、CardSpec 数据契约和最终校验口径的任务。"
---

# Harmony 卡片生成（一致版）

产出同一张 Form 卡片。交付必须同时满足：可解析、可渲染、信息不重复、关键文本不截断、布局不错位、颜色有来源、CardSpec 与 DSL 同步。

## 执行顺序

1. 先读 `reference/core-rules.md`，把 P0/L0/L1/L2 当硬门槛。
2. 只进入一个模式：新卡片、修复/评审、能力边界。新卡片再读 `reference/generation-workflow.md`；修复/评审再读 `reference/final-blockers.md`。
3. 新卡片先收敛到一个服务对象或主问题，再按角色槽位分配内容：`object`、`primary`、`support`、`metric/tile/status/badge`、`action`、`asset`。不要把所有事实硬压成固定支撑条数。
4. 未指定尺寸先尝试 `2x2`；只有受保护文本、热区、并列关系、关键媒体或布局预算具体失败时才升级 `2x4`。
5. 从零生成且能被稳定槽位承载时，读 `reference/template-routing.md`，最多选一个模板；模板只提供骨架和预算，内容、DataModel、素材、颜色、事件必须重做。
6. 需要专项时按 `reference.md` 渐进加载最小必要文件；先解决协议、绑定、尺寸和布局，再处理事件、CardSpec、颜色、素材和视觉增强。
7. 写 DSL 前先算 surface/root、内容区、padding/margin/itemMargin、热区、受保护文本、并排宽高和颜色来源。
8. 输出前确认协议、绑定、布局、颜色、事件、尺寸、模板槽位、信息职责、事实等价类和 CardSpec 对齐；只有用户要求校验既有文件或调试脚本时才运行 `scripts/validate_card.py`。

模式 1/2 的最终回答只给最终 DSL/CardSpec，不输出解释、校验日志、命令、比较过程或中间文件。

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

静态卡片也输出 `cardspec`，但不要虚构 `dataBindings`。动态卡片的 `cardspec.dataBindings` 必须来自已声明 data capability，且 UI 路径能由 `writeResultTo + outputSchema` 推导。

## 一致性约定

- 新卡片默认使用 `2x2 = 140 x 140`，root `padding: 12`、`borderRadius: 18`、`clip: true`；`2x4 = 300 x 140`，root `padding: 12`、`borderRadius: 22`、`clip: true`。
- 绑定优先级固定为：静态值或 `updateDataModel` 展示字段 -> `{"path":"/..."}` -> `formatString`。新卡片不要使用表达式；修复遗留 DSL 时也优先改写为 path/formatString，只有协议明确无法等价表达且用户要求保留行为时，才作为受限例外。
- 非模板生成时使用稳定语义 ID：`surface_card`、`root`、`header_row`、`title_text`、`primary_value`、`primary_caption`、`support_row`、`action_button` 等；模板生成时保留模板 ID 体系，但删除不用的可选槽位并同步清理引用。
- 不使用网络图、SVG、emoji、占位媒体、未声明资源路径、未声明事件能力、`Button.action`、非 `onClick` 事件或 Form 子集外组件。
- 可点击 UI 必须有真实 `onClick` EventHandler；如果动作能力不明，删除点击行为，把动作区降级为非误导支撑信息。
- 颜色规则读 `reference/design/color-token-system.md`；需要具体 hex 时再读 `reference/design/color-token-values.md`。DSL 输出 hex，不输出 token 名。
- 布局失败时按固定顺序降级：缩短弱文本 -> 删除可选角色槽位或 `shouldKeep` 字段 -> 降低到批准字号阶梯 -> 拆行/改 Column -> 放弃模板 -> 升级 `2x4` -> 能力边界说明。

## 专项参考

默认只读 `reference/core-rules.md`；新卡片再读 `reference/generation-workflow.md`。路由不清楚、修复已有 DSL、需要模板、动态数据、事件、颜色、素材或视觉增强时，再按 `reference.md` 读取对应专项文件；进入专项文件后先看顶部决策、阻断或使用规则，不一次性泛读无关参考。

运行本 skill 时不读取本 skill 包外的 UX 文档、旧样例、截图、网页或链接；需要的生成流程、布局字号、配色和验收规则已经折叠进 `reference/` 内部文件。

## 降级原则

低能力模型或高风险需求优先降低自由度：标准短需求先用 `reference/template-routing.md` 的模板 manifest 槽位模式；若不用模板，则少组件、少层级、少颜色、少动态路径、少 Stack。宁可输出简洁卡片，也不要输出语法不合规、文本显示不全、颜色无来源或明显错位的卡片。
