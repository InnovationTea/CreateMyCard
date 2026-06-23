# Harmony 卡片生成参考索引

此文件只用于导航。只有在 `SKILL.md` 的参考路由不够明确、或当前任务横跨多个问题域时读取它；读取后只加载相关文件。

## 核心原则

卡片生成由 Form 协议和规则共同驱动：

- 协议依据收敛在 [`reference/protocol.md`](reference/protocol.md)。
- 生成时先读 [`reference/protocol.md`](reference/protocol.md) 取得 Form 硬约束。
- 不要选择或改造内置 DSL 模板。
- 除非用户明确提供已有 DSL 产物要求编辑，否则不要模仿历史输出或示例卡片。
- 从语义角色、尺寸预算和可泛化构造规则推导卡片。

## 职责地图

- [`reference/protocol.md`](reference/protocol.md)：协议硬约束。回答“能不能这样写”。
- [`reference/capability.md`](reference/capability.md)：能力边界和替代策略。回答“这个需求是不是卡片范围”。
- [`reference/card-composition-rules.md`](reference/card-composition-rules.md)：生成前和生成中的构图决策。回答“这张卡怎么组织信息”。
- [`reference/guide.md`](reference/guide.md)：JSONL 消息形状、root、属性命名和输出清单。回答“DSL 怎么落笔”。
- [`reference/component-catalog.md`](reference/component-catalog.md)：组件、属性、样式枚举和 Form 写法。回答“这个组件/样式怎么写”。
- [`reference/data-binding.md`](reference/data-binding.md)：DataModel、原生 `{path}` 绑定、表达式、模板循环、事件参数。回答“动态值怎么绑定”。
- [`reference/function.md`](reference/function.md)：`formatString` 字符串拼接函数。回答“静态文本和变量怎么拼成一个字符串”。
- [`reference/visual-interaction.md`](reference/visual-interaction.md)：CTA、点击、图片来源和媒体真实性。回答“交互和媒体是否真实可用”。
- [`reference/event-capability/click-event.md`](reference/event-capability/click-event.md)：点击事件能力清单。回答“这个 onClick 能调用什么、参数从哪里来”。
- [`reference/spacing-elevation.md`](reference/spacing-elevation.md)：间距、圆角、阴影、alpha 层级。回答“视觉尺度是否统一”。
- [`reference/expressiveness-toolkit.md`](reference/expressiveness-toolkit.md)：渐变、半透明块、字形、Progress、Divider、Stack。回答“无素材时如何增强表现力”。
- [`reference/design-review.md`](reference/design-review.md)：视觉、交互、数据语义评审。回答“质量是否像可交付卡片”。
- [`reference/final-review.md`](reference/final-review.md)：唯一最终评审入口。回答“能不能交付”。

## 按任务读取

- 新的一句话桌面卡片：
  [`reference/protocol.md`](reference/protocol.md),
  [`reference/capability.md`](reference/capability.md),
  [`reference/cardspec.md`](reference/cardspec.md),
  [`reference/card-composition-rules.md`](reference/card-composition-rules.md),
  然后 [`reference/guide.md`](reference/guide.md)。
- 组件或样式不确定：
  [`reference/component-catalog.md`](reference/component-catalog.md)。
- 数据绑定、表达式或重复项路径：
  [`reference/data-binding.md`](reference/data-binding.md)。
- 字符串拼接（静态文本 + DataModel 变量）：
  [`reference/function.md`](reference/function.md)。
- 动态数据能力、端侧刷新或持久化：
  先读 [`reference/cardspec.md`](reference/cardspec.md)，再按场景读取
  [`reference/data-capability/weather.md`](reference/data-capability/weather.md)
  或 [`reference/data-capability/calendar.md`](reference/data-capability/calendar.md)。
- 交互、图片、CTA 或点击行为：
  [`reference/visual-interaction.md`](reference/visual-interaction.md)。涉及点击函数、deeplink、拨号或 intent 时，继续读取
  [`reference/event-capability/click-event.md`](reference/event-capability/click-event.md)。
- 间距、圆角、阴影、视觉层次：
  [`reference/spacing-elevation.md`](reference/spacing-elevation.md)。
- 需要在 GenUI 约束内增强视觉表现：
  [`reference/expressiveness-toolkit.md`](reference/expressiveness-toolkit.md)。
- 最终评审：
  [`reference/final-review.md`](reference/final-review.md)。该文档会调用 [`reference/design-review.md`](reference/design-review.md)。
- 仅做视觉润色或卡片质量评审：
  [`reference/design-review.md`](reference/design-review.md)。

## 按触发读取

- 看到未知组件、样式位置、枚举值、Form 属性名：读 [`reference/component-catalog.md`](reference/component-catalog.md)。
- 看到 `{{ ... }}`、`{"path":"/..."}`、`updateDataModel`、模板循环、`onClick.args`、宿主动作 ID：读 [`reference/data-binding.md`](reference/data-binding.md)。
- 看到 `formatString`、`${...}` 插值，或需要把静态文本和变量拼成一个字符串：读 [`reference/function.md`](reference/function.md)。
- 看到 CTA、`Button`、可点击容器、图片、背景图、媒体路径：读 [`reference/visual-interaction.md`](reference/visual-interaction.md)；点击行为再读 [`reference/event-capability/click-event.md`](reference/event-capability/click-event.md)。
- 需要定 padding、`itemMargin`、圆角、阴影、半透明层：读 [`reference/spacing-elevation.md`](reference/spacing-elevation.md)。
- 没有真实素材但需要视觉锚点，或要使用渐变、字形、`Progress`、`Divider`、`Stack`：读 [`reference/expressiveness-toolkit.md`](reference/expressiveness-toolkit.md)。
- 判断视觉、交互、数据语义质量：读 [`reference/design-review.md`](reference/design-review.md)。
- 最终交付前：读 [`reference/final-review.md`](reference/final-review.md)，并由它调度最终评审。

## 内部依据

本 skill 目录内的 [`reference/protocol.md`](reference/protocol.md)、[`reference/component-catalog.md`](reference/component-catalog.md)、[`reference/data-binding.md`](reference/data-binding.md) 和 [`reference/function.md`](reference/function.md) 构成协议与 DSL 依据。

不要把示例产物作为卡片布局来源。卡片布局只从语义角色、尺寸预算和构图规则推导。

## 产物边界

不要创建临时文件、中间 DSL/CardSpec 文件或其他卡片产物。草稿、改进和评审都在当前上下文中完成，最终由模型直接输出 `genui` 与 `cardspec` 两个代码块。
