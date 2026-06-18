---
name: harmony-card-generation-v5
description: "根据 harmonyos-a2ui-form-protocol 生成 HarmonyOS A2UI Form 服务卡片完整结果：一个 genui 代码块中的 DSL JSONL + 一个 cardspec 代码块中的 CardSpec JSON。使用 extended catalog 下的 Form 子集、10 个 Form 支持组件、onClick 行为链、表达式/DataModel、2x2 或横版 2x4 卡片构造规则，以及端侧 dataBindings/refreshPlan 契约。适用于创建、优化、校验或输出 HarmonyOS/A2UI/Form/服务卡片/widget 卡片/DSL/JSONL/CardSpec 组合结果，目标场景为 160x160vp 或 320x160vp。"
---

# Harmony 卡片生成 V5

## 这个 Skill 做什么

- 根据一句话生成 HarmonyOS A2UI Form 服务卡片完整结果。
- 每个卡片结果都包含同一张卡片的 `genui` DSL JSONL 代码块与 `cardspec` JSON 代码块；CardSpec 是 V5 结果的一部分，不是额外外挂。
- 使用可泛化的构图规则构造卡片：
  - `2x2`：`160 x 160vp`
  - `2x4`：`320 x 160vp` 横版
- 遵循自包含工作流：模式识别、按需读取参考、先说明布局理由再写 JSON、显式改进、优先落盘迭代、脚本校验和最终验收。
- 使用 `harmonyos-a2ui-form-protocol.md` 的 Form 裁剪协议。协议冲突时，以该协议为准。

## 执行边界

- 默认不要联网。使用本地 `harmonyos-a2ui-form-protocol.md` 和本 skill 自带参考。
- 除非用户明确提供已有 DSL 文件用于优化，否则不要主动读取、复制、改造或模仿历史卡片模板、示例卡片、旧产物、截图或已生成 JSON。
- 不要把“选择模板”作为生成步骤。布局决策只来自可泛化的构造规则。
- 除非用户明确改变任务，否则不要把桌面卡片扩展成页面、文章、长列表或仪表盘。
- 不要发明组件、样式键或预定义函数。只有在用户/宿主提供或明确声明为宿主自定义函数假设时，才允许使用应用特定函数。
- CardSpec 是 V5 卡片结果的一部分，负责端侧数据能力、刷新和持久化契约；不要把旧项目中的旧 catalog、旧组件清单或旧 DSL 示例合并进 V5 DSL 规则。

## 协议优先级

按以下顺序解决冲突：

1. 仓库根目录的 `harmonyos-a2ui-form-protocol.md`
2. [`reference/protocol.md`](reference/protocol.md)
3. [`reference/component-catalog.md`](reference/component-catalog.md) 和 [`reference/data-binding.md`](reference/data-binding.md)
4. 设计、构图和评审文档

设计文档只负责卡片质量，不得放宽 Form 协议约束。

## 第一原则：用户需求优先

- 把用户的显式需求作为最高优先级。
- 当显式用户需求与默认卡片规则冲突时，满足用户需求并记录这个受限例外。
- 其他无关的校验和设计检查仍然生效。不要因为一个例外绕过整个工作流。
- 从用户场景选择视觉语言，不要从示例或历史输出继承。

## 场景识别

生成前，先对用户的一句话分类：

- `status glance`：当前状态、指标、天气、电量、健康、进度或告警。
- `time/reminder`：会议、课程、约会、倒计时、行程、截止日期、提醒。
- `action card`：一个明确的下一步动作，例如呼叫、打开、专注、提醒、导航、切换。
- `device/product`：资源图片、电量、模式、播放、连接状态。
- `information summary`：把地点、人物、事件、概念或实体压缩成紧凑卡片。
- `unsupported/page-like`：多个章节、长说明、复杂表单、表格、完整页面。

对于信息摘要类请求，保持输出像卡片：

- 结构：标题 -> 1 到 3 个核心属性 -> 简短摘要 -> 可选标签/动作。
- 正文 <= 2 行短文本。
- 默认不要使用动态列表模式。
- 不要使用全宽 16:9 hero 图。
- 只有当用户明确要求丰富细节时，才升级为页面。

## 尺寸选择

写 DSL 前必须且只能选择一个尺寸：

### `2x2` / `160 x 160vp`

默认尺寸。用于一个主要结论和一个辅助上下文：

- 状态速览、简单提醒、天气+下个事件、设备状态、单个进度指标、一个动作。
- 主区域：<= 3。
- 适合无需滚动、无需阅读段落即可一眼理解的答案。

### `2x4` / `320 x 160vp`

仅当场景确实需要横向宽度时使用：

- 左右关系、两个紧凑面板、更宽的受保护文本、更丰富的设备/产品状态、媒体加状态、详情加动作。
- 主区域：<= 4。
- 默认不滚动。如果卡片需要滚动，它很可能已经接近页面。

如果压缩后两个尺寸都装不下请求，使用模式 3。

## 模式选择

必须进入且只进入一个模式：

### 模式 1：一句话桌面卡片

默认模式。用户用自然语言要求生成新卡片，且没有提供现有 DSL。

交付物：

1. 一个 `genui` 代码块，内容是 A2UI JSONL 消息流。
2. 一个 `cardspec` 代码块，内容是 CardSpec JSON 对象。

### 模式 2：已有 DSL 优化 / 评审

当用户提供已有 GenUI/CardSpec 内容，或要求修复/评审某个组合结果时使用。

交付物：

1. 修复后的 `genui` 代码块
2. 修复后的 `cardspec` 代码块
3. 校验器结果
4. 简短的问题/修复摘要

### 模式 3：能力边界 / 升级说明

当请求超出紧凑桌面卡片范围时使用。

交付物：

1. 清楚说明不支持的部分
2. 给出最接近的受支持 2x2 或 2x4 卡片替代方案
3. 只有在用户接受更窄范围时，才继续询问或执行

## 参考路由

先确定模式，再按下面路由读取。不要只看资源列表；资源列表只是索引。

### 默认必读

- 新卡片：[`reference/protocol.md`](reference/protocol.md)、[`reference/capability.md`](reference/capability.md)、[`reference/cardspec.md`](reference/cardspec.md)、[`reference/card-composition-rules.md`](reference/card-composition-rules.md)、[`reference/guide.md`](reference/guide.md)。
- 已有 DSL/CardSpec 修复或评审：[`reference/protocol.md`](reference/protocol.md)、[`reference/review-validation.md`](reference/review-validation.md)、[`reference/component-catalog.md`](reference/component-catalog.md)、[`reference/data-binding.md`](reference/data-binding.md)、[`reference/cardspec.md`](reference/cardspec.md)。
- 能力边界分流：[`reference/protocol.md`](reference/protocol.md)、[`reference/capability.md`](reference/capability.md)、[`reference/card-composition-rules.md`](reference/card-composition-rules.md)。
- 最终验收：只从 [`reference/review-validation.md`](reference/review-validation.md) 进入；该文档会按需调用 [`reference/design-review.md`](reference/design-review.md)。

### 条件触发

- 组件、属性、样式枚举、`children` 形状不确定：读取 [`reference/component-catalog.md`](reference/component-catalog.md)。
- 出现 `updateDataModel`、表达式、模板循环、事件参数或宿主动作 ID：读取 [`reference/data-binding.md`](reference/data-binding.md)。
- 出现 CTA、可点击区域、`Button`、`onClick`、图片来源或媒体真实性问题：读取 [`reference/visual-interaction.md`](reference/visual-interaction.md)。
- 需要确定 padding、`itemMargin`、圆角、阴影、半透明块或视觉层级尺度：读取 [`reference/spacing-elevation.md`](reference/spacing-elevation.md)。
- 没有真实本地图片但需要视觉锚点，或需要渐变、字形、`Progress`、`Divider`、`Stack` 增强表现力：读取 [`reference/expressiveness-toolkit.md`](reference/expressiveness-toolkit.md)。
- 出现动态数据能力、端侧刷新或持久化：先读 [`reference/cardspec.md`](reference/cardspec.md)，再按场景读取 [`reference/data-capability/weather.md`](reference/data-capability/weather.md) 或 [`reference/data-capability/calendar.md`](reference/data-capability/calendar.md)。
- 只做视觉润色或卡片质量评审：读取 [`reference/design-review.md`](reference/design-review.md)；最终交付前仍回到 [`reference/review-validation.md`](reference/review-validation.md)。
- 不确定该读哪个文件：先读 [`reference.md`](reference.md)，再只读它指向的相关文件。

## 输出格式

最终交付只有一个组合结果，由两个代码块组成：

```genui
{"version":"v0.9","createSurface":{...}}
{"version":"v0.9","updateComponents":{...}}
{"version":"v0.9","updateDataModel":{...}}
```

```cardspec
{
  "suggestSize": "2x4",
  "dataBindings": []
}
```

规则：

- 直接输出 `genui` 块和 `cardspec` 块；前后不要加解释、标题、路径或总结。
- `genui` 块只输出 A2UI JSONL，每行是一条完整 JSON 消息。
- `cardspec` 块只输出一个完整 JSON 对象。
- `genui` 和 `cardspec` 是同一个 V5 卡片结果的两个部分，不要把 CardSpec 当外挂、附件或另一个项目产物。
- 静态卡片也输出 `cardspec`；可以只包含 `suggestSize`，不要虚构 `dataBindings`。
- 动态卡片必须在 `cardspec.dataBindings` 中声明端侧能力调用。

默认 `genui` JSONL 顺序：

1. `createSurface`
2. `updateComponents`
3. `updateDataModel`

`updateComponents` 必须在 `createSurface` 之后，同一 surface 只发送一次完整 `updateComponents`。

## 工作流

1. 读取用户请求并判断场景/模式。
2. 按 [`reference/capability.md`](reference/capability.md) 确认请求是否在能力范围内。不在范围内则使用模式 3。
3. 按 [`reference/card-composition-rules.md`](reference/card-composition-rules.md) 选择 `2x2` 或 `2x4`。
4. 从请求中推导语义角色：identity、primary answer、metric、context、progress/trend、media、action。
5. 按“参考路由”读取该模式和触发条件所需的参考。
6. 写 JSON 前必须明确说明布局理由，覆盖：
   - 选择的尺寸以及原因
   - 语义角色和主区域
   - 视觉焦点
   - 信息节奏
   - 关键横向关系
   - 必须完整显示的关键信息
   - 每个拥挤 Row 的组件内部宽度预算
   - 交互和 DataModel 形状
   - CardSpec 的 `suggestSize`、静态/动态形态、能力选择、参数、`writeResultTo` 和刷新计划
7. 正式输出前至少做一次显式改进：
   - 指出第一个内部版本缺少什么
   - 改进层级、紧凑度、场景视觉特征，或关键信息完整显示的安全性
8. 生成 `genui` 与 `cardspec` 两个代码块草稿。
9. 用临时文件或内存方式校验 `genui` JSONL 和 `cardspec` JSON。
10. 直接修复校验错误，并重复校验直到通过。
11. 脚本通过后，按 [`reference/review-validation.md`](reference/review-validation.md) 做最终验收；该文档会在需要时调用 [`reference/design-review.md`](reference/design-review.md) 做视觉、交互、数据语义和受保护文本评审。
12. 如果最终验收修改了内容，重新运行相关校验。
13. 只有在校验通过且最终验收完成后交付两个代码块。

## 不可妥协项

- 协议合法性不能由设计文档放宽。具体组件、事件、媒体、表达式和 catalog 约束以 [`reference/protocol.md`](reference/protocol.md)、[`reference/component-catalog.md`](reference/component-catalog.md)、[`reference/data-binding.md`](reference/data-binding.md) 为准。
- 卡片形态不能放宽成页面。具体尺寸、区域数量、受保护文本和构图规则以 [`reference/card-composition-rules.md`](reference/card-composition-rules.md) 为准。
- 生成必须由规则驱动。不要选择、复制或改造内置模板。
- 每条消息使用 `version: "v0.9"`。
- 使用 `catalogId: "ohos.a2ui.extended.catalog"`。
- `createSurface` 不支持 `theme` 字段。
- 同一 surface 只允许一次完整 `updateComponents`，不要流式或增量追加组件树。
- 最终响应只输出 `genui` 与 `cardspec` 两个代码块；不要输出文件路径、标题、总结或额外解释。
- 使用 extended 属性名：`Text.content`、`Image.src`、`Button.label`。
- 不要使用仅标准 catalog 的 `Text.text`、`Image.url`、`Button.child` 或 CSS kebab-case 样式键。
- 只使用 Form 组件子集：`Text`、`Image`、`Divider`、`Progress`、`Button`、`Checkbox`、`Row`、`Column`、`List`、`Stack`。
- 不使用 `TextInput`、`Toggle`、`Radio`、`CheckboxGroup`、`Select`、`NavContainer`、`Tabs`、`TabContent`、`Web`、`Grid`、`If` 或 A2UI 原生组件。
- 使用扁平 `components` 邻接表和 `id` 引用。不要在 `children` 中内联组件。
- 包含 `root` 组件，并保证所有引用可解析。
- 目标卡片尺寸为 `2x2 = 160 x 160vp` 和横版 `2x4 = 320 x 160vp`。如果宿主要求 `width: "100%"`，仍然按所选宽度预算设计：`2x2` 为 `160vp`，`2x4` 为 `320vp`。
- 卡片不是页面：`2x2` 主区域 <= 3，`2x4` 主区域 <= 4；不要长文案、大表格或长动态列表。
- 正式输出前，必须有布局理由和至少一次改进。
- 可点击 UI 必须有真实 `onClick` EventHandler 数组。Form 不使用 `Button.action`。
- Form 只支持通用事件 `onClick`；不要使用 `onAppear`、`onChange`、`onSelect`、`onReachStart` 或 `onReachEnd`。
- 不使用预定义扩展函数。EventHandler 的 `call` 只能引用宿主 catalog 已声明的自定义函数，或明确声明为宿主假设。
- 不要编造远程媒体 URL。`Image.src` 和 `styles.backgroundImage` 只使用本地/资源路径；不支持网络图片或 SVG。
- 组件属性绑定默认使用完整表达式，如 `"{{ $__dataModel.meeting.title }}"`；`updateDataModel.path` 和模板 `children.path` 使用 `/` JSON Pointer。
- 不使用 `$__widthBreakpoint` 或 `$__colorMode`。
- 协议模板循环只能用于 `Row`、`Column`、`List` 的 `children: { componentId, path }`。
- 横向 `Row` 默认直接子节点 <= 3。需要更多时拆分、堆叠或使用竖向分组。
- 时间、CTA、状态、温度、电量百分比、价格和短中文短语等受保护内容不能被挤压成碎片。
- 关键信息默认必须完整显示：日期、星期、时间、CTA、状态、主指标/数值、主标题/名称、倒计时、价格/数量，以及用户要求显示的字段。不要依赖 `textOverflow: "ellipsis"`、`clip` 或 marquee 隐藏缺失信息。
- `textOverflow: "ellipsis"` 只能用于明确可压缩的次要文本，例如可选地点、副标题或建议文案。如果关键值放不下，先减少 padding、itemMargin、装饰性分隔线、固定列和字体大小；再拆行、选择横版 `2x4`，或使用模式 3。
- 每个包含两个或更多受保护文本值的 Row，在写 JSON 前都要做宽度预算：可用宽度 = 父级宽度 - 父级水平 padding - row gaps - 固定分隔线/图标 - 固定文本列。如果接近放不下，先简化该行再生成 DSL。
- 当有 2 个以上标签时，标签组和主 CTA 不应共用一个拥挤行；放到 `Column` 内的不同行。
- 任何手动/设计修改后，都要重新运行校验器。
- CardSpec 的 `suggestSize` 必须与 DSL 选择的尺寸一致。
- CardSpec 的 `dataBindings[].writeResultTo` 必须位于 `/data` 下，且 UI 绑定路径必须能由 `writeResultTo + outputSchema` 推导。
- CardSpec 优先使用旧 cardspec 项目的简洁契约：`suggestSize`、`dataBindings[].capabilityId`、`arguments`、`writeResultTo`；只有端侧明确需要时才加入 `bindingId`、`capabilityVersion` 或 `refreshPlan`。
- 不虚构 CardSpec 能力、参数、权限、端侧函数或刷新策略；未声明能力只能降级为静态卡片或说明需要补充 capability manifest。

## 资源

- 子文档索引：[`reference.md`](reference.md)
- Form 协议摘要：[`reference/protocol.md`](reference/protocol.md)
- 能力范围：[`reference/capability.md`](reference/capability.md)
- 可泛化卡片构造规则：[`reference/card-composition-rules.md`](reference/card-composition-rules.md)
- DSL 指南：[`reference/guide.md`](reference/guide.md)
- 组件目录：[`reference/component-catalog.md`](reference/component-catalog.md)
- 数据绑定：[`reference/data-binding.md`](reference/data-binding.md)
- CardSpec 契约：[`reference/cardspec.md`](reference/cardspec.md)
- 数据能力：[`reference/data-capability/weather.md`](reference/data-capability/weather.md), [`reference/data-capability/calendar.md`](reference/data-capability/calendar.md)
- 视觉和交互：[`reference/visual-interaction.md`](reference/visual-interaction.md)
- 间距和层级：[`reference/spacing-elevation.md`](reference/spacing-elevation.md)
- 表现力工具箱：[`reference/expressiveness-toolkit.md`](reference/expressiveness-toolkit.md)
- 设计评审：[`reference/design-review.md`](reference/design-review.md)
- 最终验收：[`reference/review-validation.md`](reference/review-validation.md)
- 校验脚本：[`scripts/validate_genui_card.py`](scripts/validate_genui_card.py)
- CardSpec 校验脚本：[`scripts/validate_cardspec.py`](scripts/validate_cardspec.py)
