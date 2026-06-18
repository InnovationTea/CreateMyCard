# Harmony 卡片生成 V5 参考索引

此文件只用于导航。只有在 `SKILL.md` 的参考路由不够明确、或当前任务横跨多个问题域时读取它；读取后只加载相关文件。

## 核心原则

V5 由 Form 协议和规则共同驱动：

- 协议事实源是仓库根目录的 `harmonyos-a2ui-form-protocol.md`。
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
- [`reference/data-binding.md`](reference/data-binding.md)：DataModel、表达式、模板循环、事件参数。回答“动态值怎么绑定”。
- [`reference/visual-interaction.md`](reference/visual-interaction.md)：CTA、点击、图片来源和媒体真实性。回答“交互和媒体是否真实可用”。
- [`reference/spacing-elevation.md`](reference/spacing-elevation.md)：间距、圆角、阴影、alpha 层级。回答“视觉尺度是否统一”。
- [`reference/expressiveness-toolkit.md`](reference/expressiveness-toolkit.md)：渐变、半透明块、字形、Progress、Divider、Stack。回答“无素材时如何增强表现力”。
- [`reference/design-review.md`](reference/design-review.md)：脚本通过后的视觉、交互、数据语义评审。回答“质量是否像可交付卡片”。
- [`reference/review-validation.md`](reference/review-validation.md)：唯一最终验收入口。回答“能不能交付”。

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
- 动态数据能力、端侧刷新或持久化：
  先读 [`reference/cardspec.md`](reference/cardspec.md)，再按场景读取
  [`reference/data-capability/weather.md`](reference/data-capability/weather.md)
  或 [`reference/data-capability/calendar.md`](reference/data-capability/calendar.md)。
- 交互、图片、CTA 或点击行为：
  [`reference/visual-interaction.md`](reference/visual-interaction.md)。
- 间距、圆角、阴影、视觉层次：
  [`reference/spacing-elevation.md`](reference/spacing-elevation.md)。
- 需要在 GenUI 约束内增强视觉表现：
  [`reference/expressiveness-toolkit.md`](reference/expressiveness-toolkit.md)。
- 最终验收：
  [`reference/review-validation.md`](reference/review-validation.md)。该文档会按需调用 [`reference/design-review.md`](reference/design-review.md)。
- 仅做视觉润色或卡片质量评审：
  [`reference/design-review.md`](reference/design-review.md)。
- 校验器失败：
  先读 [`reference/review-validation.md`](reference/review-validation.md)，再读上面与问题直接相关的参考。

## 按触发读取

- 看到未知组件、样式位置、枚举值、Form 属性名：读 [`reference/component-catalog.md`](reference/component-catalog.md)。
- 看到 `{{ ... }}`、`updateDataModel`、模板循环、`onClick.args`、宿主动作 ID：读 [`reference/data-binding.md`](reference/data-binding.md)。
- 看到 CTA、`Button`、可点击容器、图片、背景图、媒体路径：读 [`reference/visual-interaction.md`](reference/visual-interaction.md)。
- 需要定 padding、`itemMargin`、圆角、阴影、半透明层：读 [`reference/spacing-elevation.md`](reference/spacing-elevation.md)。
- 没有真实素材但需要视觉锚点，或要使用渐变、字形、`Progress`、`Divider`、`Stack`：读 [`reference/expressiveness-toolkit.md`](reference/expressiveness-toolkit.md)。
- 脚本已通过但仍要判断视觉、交互、数据语义质量：读 [`reference/design-review.md`](reference/design-review.md)。
- 最终交付前：读 [`reference/review-validation.md`](reference/review-validation.md)，并由它调度最终评审。

## 来源依据

本 skill 基于本仓库中的 Form 协议裁剪文档：

- `harmonyos-a2ui-form-protocol.md`

不要把历史示例产物作为卡片布局来源。协议原文是权威依据；本 skill 的协议参考只是生成用摘要。

## 校验

内部校验可运行：

```bash
python scripts/validate_genui_card.py path/to/temp.dsl.jsonl
```

脚本接受 JSONL 消息，也接受 JSON 消息数组。最终响应仍应是 `genui` 代码块，不是文件路径。

同时校验 `cardspec` 代码块对应的 JSON：

```bash
python scripts/validate_cardspec.py path/to/temp.cardspec.json
```
