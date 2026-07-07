# Harmony 卡片生成参考索引

只有当 `SKILL.md` 路由不明确时读取本文档。默认加载 `SKILL.md` + `reference/core-rules.md`；新卡片加载 `reference/generation-workflow.md`；修复已有 DSL 时，按失败类型逐个加载最小必要文件。

## 加载规则

- 先解决协议、绑定、尺寸和布局，再处理事件、CardSpec、色彩、素材、主显示组突出度、支撑组归拢和表面层级。
- 从自然语言生成新卡片时，先读取 [`reference/generation-workflow.md`](reference/generation-workflow.md) 建立意图字段组、内容分级、尺寸适配、场景字段组、布局原型和配色前置决策。
- 从零生成完成内容分级后，只要候选尺寸可能由模板承载，且入选内容能归入单一对象/主问题的角色槽位，读取 [`reference/template-routing.md`](reference/template-routing.md) 与 `assets/templates/index.json` 判断候选。模板不匹配、槽位过长、动作能力不明、素材缺失、无同尺寸模板或预算不成立时，回到非模板流程。
- DSL 中将要出现的组件字段、绑定、事件、CardSpec、颜色或素材，必须能在已读文件中找到权威来源；找不到就按下方专项路由补读，不要从旧样例或记忆推断。
- 白屏、不渲染或 JSONL 解析失败时，先查协议消息闭环和 root shell，再查组件字段归属，最后查绑定路径闭环。
- 长文档先看顶部决策、阻断或使用规则；manifest、token 表、素材表只在需要具体值时查。
- 不要为了比较风格同时读取多个设计文件；只按当前失败类型读取对应专项文件。
- 不要读取本 skill 包外的历史样例、截图、旧模板或其它本地文件作为生成依据。

## 文件职责边界

- `core-rules.md`：默认硬门槛，覆盖协议、绑定、尺寸、布局、内容重复和交付前基础校验。
- `generation-workflow.md`：新卡片 UX 规划，覆盖意图字段组、内容分级、尺寸适配、场景字段组、布局原型和配色前置决策，并提供内部术语最小定义。
- `protocol/protocol.md`：协议裁决，覆盖三行 JSONL、surface/root、禁用能力、事件语法和路径表达边界；不维护组件逐项字段表。
- `protocol/component-catalog.md`：组件字段权威来源，覆盖允许组件、顶层语义字段、组件特有属性、通用样式和枚举。
- `protocol/data-binding.md`：绑定权威来源，覆盖 `updateDataModel`、`path`、`formatString`、模板循环相对路径和事件参数取值。
- `design/layout-system.md`：几何落地，覆盖安全区、宽高预算、字号阶梯、图标区、进度几何、按钮热区和重叠防线。
- `design/color-token-system.md`：颜色合法性，覆盖 token、多彩色、场景色族、深浅色、渐变 stop、前景/背景配对和按钮材质。
- `design/color-token-values.md`：token、`ohos_id_color_*` 和多彩色到 light/dark hex 的值表；只在需要最终色值时读取。
- `design/design-heuristics.md`：构图和表面补强，覆盖主显示组突出度、支撑组归拢、表面层级和可用表面技法；不重复生成流程、字号预算或色值表。
- `template-routing.md`：模板是否使用、如何选、如何删槽位和何时回退。

## 模式路由

- 新卡片：先读 [`reference/core-rules.md`](reference/core-rules.md) 和 [`reference/generation-workflow.md`](reference/generation-workflow.md)，再按是否模板化读取 [`reference/template-routing.md`](reference/template-routing.md)，最后只读取当前阻塞点需要的专项文件。
- 修复/评审：先读 [`reference/core-rules.md`](reference/core-rules.md)，再按 validator 或人工发现的失败类型读取专项文件。
- 能力边界：读 [`reference/design/layout-system.md`](reference/design/layout-system.md) 判断是否能降级为 `2x2` 或 `2x4`；不能承载时说明边界，不输出伪 DSL。

## 专项路由

- 白屏、不渲染、三行 JSONL 顺序、`surfaceId`、root shell 或禁用能力：[`reference/protocol/protocol.md`](reference/protocol/protocol.md)；组件字段归属、属性或样式枚举：[`reference/protocol/component-catalog.md`](reference/protocol/component-catalog.md)。
- 自然语言需求拆解、内容取舍、尺寸适配、场景字段组、布局原型、进度可视化选择：[`reference/generation-workflow.md`](reference/generation-workflow.md)。
- DataModel、`path`、绑定路径漏初始化、`formatString` 字符串拼接、模板循环、事件参数：[`reference/protocol/data-binding.md`](reference/protocol/data-binding.md)。
- CardSpec、动态数据能力：[`reference/capability/cardspec.md`](reference/capability/cardspec.md)，再按场景逐个选择必要的 [`reference/capability/data-capability/`](reference/capability/data-capability/) 文件。
- 点击、拨号、跳转和动作参数：[`reference/capability/event-capability/click-event.md`](reference/capability/event-capability/click-event.md)。
- 布局预算、按钮对齐、底部贴底、重叠、留白：[`reference/design/layout-system.md`](reference/design/layout-system.md)。
- 合规模板选型、槽位映射和回退规则：[`reference/template-routing.md`](reference/template-routing.md)。
- 颜色合法性、场景色、渐变 stop、token 来源：[`reference/design/color-token-system.md`](reference/design/color-token-system.md)；需要具体 hex 时再读 [`reference/design/color-token-values.md`](reference/design/color-token-values.md)。
- 图片、图标、背景图、素材路径，或入选内容存在可由素材承担的识别、状态、动作、主媒体、视觉锚点职责：[`reference/design/asset-library.md`](reference/design/asset-library.md)。不要仅因用户未提供素材就跳过素材库。
- P0/L0/L1 已成立，但主显示组不突出、支撑组散落、表面层级缺失，或用户明确要求调整构图/表面：[`reference/design/design-heuristics.md`](reference/design/design-heuristics.md)。
- 人工复核、修复已有 DSL 或 validator 不可用：先用 [`reference/core-rules.md`](reference/core-rules.md) 的 P0/L0/L1/L2 与人工阻断补充，再按具体失败点读取专项文件。

## 一致性优先级

1. 用户显式需求。
2. Form 协议、组件、绑定、事件和 CardSpec 合法性。
3. 尺寸预算、受保护文本完整显示和可点击热区。
4. 信息职责互斥和事实不重复。
5. 模板槽位、主显示组、支撑组和表面层级。

当 2-5 与 1 冲突时，只做最小受限例外；协议合法性不放宽。
