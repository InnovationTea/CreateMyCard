# Harmony 卡片生成参考索引

只有当 `SKILL.md` 路由不明确时读取本文档。默认加载 `SKILL.md` + `reference/core-rules.md`；新卡片加载 `reference/generation-workflow.md`；修复已有 DSL 时，按失败类型逐个加载最小必要文件。

## 加载规则

- 先解决协议、绑定、尺寸和布局，再处理事件、CardSpec、色彩、素材和视觉增强。
- 从自然语言生成新卡片时，先读取 [`reference/generation-workflow.md`](reference/generation-workflow.md) 建立意图字段组、内容分级、尺寸适配、场景字段组、布局原型和配色前置决策。
- 从零生成且布局可由模板稳定承载时，读取 [`reference/template-routing.md`](reference/template-routing.md)。模板不匹配、槽位过长、动作能力不明、素材缺失或预算不成立时，回到非模板流程。
- 长文档先看顶部决策、阻断或使用规则；manifest、token 表、素材表只在需要具体值时查。
- 不要为了泛化设计分析读取多个详细设计文件；先解决当前阻塞点，再判断是否需要下一个文件。
- 不要读取本 skill 包外的历史样例、截图、旧模板或其它本地文件作为生成依据。

## 文件职责边界

- `core-rules.md`：默认硬门槛，覆盖协议、绑定、尺寸、布局、内容重复和交付前基础校验。
- `generation-workflow.md`：新卡片 UX 规划，覆盖意图字段组、内容分级、尺寸适配、场景字段组、布局原型和配色前置决策，并提供内部术语最小定义。
- `design/layout-system.md`：几何落地，覆盖安全区、宽高预算、字号阶梯、图标区、进度几何、按钮热区和重叠防线。
- `design/color-token-system.md`：颜色合法性，覆盖 token、多彩色、场景色族、深浅色、渐变 stop、前景/背景配对和按钮材质。
- `design/color-token-values.md`：token、`ohos_id_color_*` 和多彩色到 light/dark hex 的值表；只在需要最终色值时读取。
- `design/design-heuristics.md`：视觉润色，覆盖 composition、surface strategy 和表现技法；不重复生成流程、字号预算或色值表。
- `template-routing.md`：模板是否使用、如何选、如何删槽位和何时回退。
- `final-blockers.md`：人工复核和 validator 覆盖不到的最终阻断。

## 模式路由

- 新卡片：先读 [`reference/core-rules.md`](reference/core-rules.md) 和 [`reference/generation-workflow.md`](reference/generation-workflow.md)，再按是否模板化读取 [`reference/template-routing.md`](reference/template-routing.md)，最后只读取当前阻塞点需要的专项文件。
- 修复/评审：先读 [`reference/core-rules.md`](reference/core-rules.md) 和 [`reference/final-blockers.md`](reference/final-blockers.md)，再按 validator 或人工发现的失败类型读取专项文件。
- 能力边界：读 [`reference/design/layout-system.md`](reference/design/layout-system.md) 判断是否能降级为 `2x2` 或 `2x4`；不能承载时说明边界，不输出伪 DSL。

## 专项路由

- 组件是否可用、属性或样式枚举：[`reference/protocol/component-catalog.md`](reference/protocol/component-catalog.md)；协议冲突兜底：[`reference/protocol/protocol.md`](reference/protocol/protocol.md)。
- 自然语言需求拆解、内容取舍、尺寸适配、场景字段组、布局原型、进度可视化选择：[`reference/generation-workflow.md`](reference/generation-workflow.md)。
- DataModel、`path`、表达式遗留改写、模板循环、事件参数：[`reference/protocol/data-binding.md`](reference/protocol/data-binding.md)；字符串拼接：[`reference/protocol/function.md`](reference/protocol/function.md)。
- CardSpec、动态数据能力：[`reference/capability/cardspec.md`](reference/capability/cardspec.md)，再按场景逐个选择必要的 [`reference/capability/data-capability/`](reference/capability/data-capability/) 文件。
- 点击、拨号、跳转和动作参数：[`reference/capability/event-capability/click-event.md`](reference/capability/event-capability/click-event.md)。
- 布局预算、按钮对齐、底部贴底、重叠、留白：[`reference/design/layout-system.md`](reference/design/layout-system.md)。
- 合规模板选型、槽位映射和回退规则：[`reference/template-routing.md`](reference/template-routing.md)。
- 颜色合法性、场景色、渐变 stop、token 来源：[`reference/design/color-token-system.md`](reference/design/color-token-system.md)；需要具体 hex 时再读 [`reference/design/color-token-values.md`](reference/design/color-token-values.md)。
- 图片、图标、背景图、素材路径：[`reference/design/asset-library.md`](reference/design/asset-library.md)。
- 无 P0/L0/L1 问题但视觉质量弱：[`reference/design/design-heuristics.md`](reference/design/design-heuristics.md)。
- 人工复核、修复已有 DSL 或 validator 不可用：[`reference/final-blockers.md`](reference/final-blockers.md)。

## 一致性优先级

1. 用户显式需求。
2. Form 协议、组件、绑定、事件和 CardSpec 合法性。
3. 尺寸预算、受保护文本完整显示和可点击热区。
4. 信息职责互斥和事实不重复。
5. 模板槽位和视觉表现。

当 2-5 与 1 冲突时，只做最小受限例外；协议合法性不放宽。
