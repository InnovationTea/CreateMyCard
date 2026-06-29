# Harmony 卡片生成参考索引

只有当 `SKILL.md` 路由不明确时读取本文档。默认先加载 `SKILL.md` + `reference/core-rules.md`；修复已有 DSL 时，按失败类型逐个加载最小必要文件。

## 加载规则

- 先解决协议、绑定、尺寸和布局，再处理色彩、素材和视觉增强。
- 长文档先看顶部决策、阻断或使用规则；manifest、token 表、素材表只在需要具体值时查。
- 不要为泛化设计分析读取多个详细设计文件；先解决当前阻塞点，再判断是否需要下一个文件。

## 路由

- 组件是否可用、属性或样式枚举：[`reference/protocol/component-catalog.md`](reference/protocol/component-catalog.md)；协议冲突兜底：[`reference/protocol/protocol.md`](reference/protocol/protocol.md)。
- DataModel、`path`、表达式、模板、事件参数：[`reference/protocol/data-binding.md`](reference/protocol/data-binding.md)；字符串拼接：[`reference/protocol/function.md`](reference/protocol/function.md)。
- CardSpec、动态数据能力：[`reference/capability/cardspec.md`](reference/capability/cardspec.md)，再按场景逐个选择必要的 [`reference/capability/data-capability/`](reference/capability/data-capability/) 文件。
- 点击、拨号、跳转和动作参数：[`reference/capability/event-capability/click-event.md`](reference/capability/event-capability/click-event.md)。
- 布局预算、按钮对齐、底部贴底、重叠、留白：[`reference/design/layout-system.md`](reference/design/layout-system.md)。
- 颜色、深浅色、渐变 stop、token 来源：[`reference/design/color-token-system.md`](reference/design/color-token-system.md)。
- 图片、图标、背景图、素材路径：[`reference/design/asset-library.md`](reference/design/asset-library.md)。
- 无 L0/L1 问题但视觉质量弱：[`reference/design/design-heuristics.md`](reference/design/design-heuristics.md)。
- 人工复核或 validator 不可用：[`reference/final-blockers.md`](reference/final-blockers.md)。
