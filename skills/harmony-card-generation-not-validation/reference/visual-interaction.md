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
- 当语义上是按钮时，使用带 `label` 和 `onClick` 的 `Button`。
- 不要画没有事件的假按钮。
- 对应用特定动作，优先使用 [`event-capability/click-event.md`](event-capability/click-event.md) 声明的 `functionCall`，并从 DataModel 或模板变量绑定所需 ID。只有用户或宿主明确提供其它自定义函数时，才使用宿主假设函数名。

示例：

```json
{"id":"calendarItem","component":"Row","children":["eventTime","eventTitle"],"onClick":[{"call":"clickToIntent","args":{"intentName":"ViewCalendarEvent","params":{"entityId":{"path":"entityId"}}}}]}
```

事件能力规则：

- `clickToCallPhone` 必须提供 `phonenumber`。
- `clickToDeeplink` 只能使用 event-capability 中 `supportedTargets` 的合法 `bundleName`、`abilityName`、`uri` 组合。
- `clickToIntent` 的日历详情跳转使用 `intentName: "ViewCalendarEvent"`，并绑定 `params.entityId`。

## 按钮安全

- `Button.label` 必须是可见文本。
- Form 不使用 `Button.action`；按钮点击写在 `Button.onClick`。
- 如果动作只是宿主占位，最终回复中说明。
- CTA 文本是受保护内容：保持一行，不要强行放进狭窄固定宽度。

## 图片来源

- 优先使用用户提供的本地/资源路径。
- 不要编造网络 URL。
- 如果没有可靠图片，使用渐变、`Stack`、半透明块、文本字形、`Divider` 或 `Progress`。

## 媒体真实性

`Image.src` 和 `styles.backgroundImage` 不支持网络 URL。`example.com`、`placeholder.com` 和 `picsum.photos` 等占位域名不能用于最终卡片输出。

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
