# 视觉和交互指导

## 默认视觉方向

除非用户要求极简/朴素输出，默认应当：

- 精致
- 有层次
- 紧凑
- 贴合场景
- 在 GenUI extended Catalog 限制内具有视觉表现力

不要默认使用最少组件。使用所选尺寸预算和语义角色建立清晰层级。

## 真实交互

可点击区域必须是真实的：

- 当整个区域可点击时，在 `Stack`、`Row` 或 `Column` 上使用 `onClick`。
- 当语义上是按钮时，使用带 `label` 和 `action` 的 `Button`。
- 不要画没有事件的假按钮。
- 对应用特定动作，使用有意义的宿主函数名，例如 `enterFocusMode`、`openTrainingPlan`、`makePhoneCall`，并从 DataModel 绑定所需 ID。

示例：

```json
{"id":"focusAction","component":"Stack","children":["focusLabel"],"onClick":[{"call":"enterFocusMode","args":{"meetingId":{"path":"/meeting/id"}}}]}
```

## 按钮安全

- `Button.label` 必须是可见文本。
- 如果使用 `Button.action`，不要同时依赖 `onClick`；`action` 优先。
- 如果动作只是宿主占位，最终回复中说明。
- CTA 文本是受保护内容：保持一行，不要强行放进狭窄固定宽度。

## 图片来源

- 优先使用用户提供的本地资源或 URL。
- 不要编造 URL。
- 如果没有可靠图片，使用渐变、`Stack`、半透明块、文本字形、`Divider` 或 `Progress`。

## URL 真实性

`updateDataModel` 中的任何 URL 都应真实且可加载。`example.com`、`placeholder.com` 和 `picsum.photos` 等占位域名不能用于最终卡片输出。

## 反模式

避免：

- 在 extended 卡片中使用 standard-catalog 属性名。
- 把没有事件的样式化文本伪装成按钮。
- 一张紧凑卡片中有太多小卡片块。
- 只有竖向文本堆叠，没有视觉焦点。
- 标签组和 CTA 按钮挤在同一行互相争抢。
- 从示例产物复用颜色或结构，而不是服务当前场景。
- 图片背景遮住核心文本。
- 本应来自 DataModel 的宿主动作 args 被硬编码。
