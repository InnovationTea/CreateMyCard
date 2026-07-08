# DSL 与卡片生成指南

## 必需消息形状

生成 JSONL，每行必须且只能有一个 JSON object：

```jsonl
{"version":"v0.9","createSurface":{"surfaceId":"sample-card","catalogId":"ohos.a2ui.extended.catalog","theme":{"primaryColor":"#4D5CFF"}}}
{"version":"v0.9","updateComponents":{"surfaceId":"sample-card","components":[{"id":"root","component":"Column","children":["title"],"styles":{"width":160,"height":160}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"sample-card","path":"/","value":{"title":"Sample"}}}
```

规则：

- `version` 永远是 `"v0.9"`。
- 先使用 `createSurface`，再使用 components 或 data。
- 使用 `catalogId: "ohos.a2ui.extended.catalog"`。
- 所有消息保持同一个 `surfaceId`。
- `updateDataModel` 优先使用 `path: "/"`。

## Root 尺寸

按精确卡片预算设计：

```json
{"id":"root","component":"Column","children":["primary"],"styles":{"width":160,"height":160,"borderRadius":22,"clip":true}}
```

```json
{"id":"root","component":"Row","children":["focal","details","action"],"styles":{"width":320,"height":160,"borderRadius":22,"clip":true}}
```

如果宿主运行时要求响应式宽度，`styles.width` 可以是 `"100%"`，但构图仍必须适配所选宽度预算：`2x2` 为 `160vp`，横版 `2x4` 为 `320vp`。

## 组件模型

使用扁平邻接表：

```json
{"id":"root","component":"Column","children":["title","action"]}
{"id":"title","component":"Text","content":{"path":"/title"}}
```

不要内联 child component object：

```json
{"id":"root","component":"Column","children":[{"component":"Text","content":"Wrong"}]}
```

## Extended-Catalog 属性名

桌面卡片使用 HarmonyOS extended catalog。使用：

- `Text.content`，不要用 `Text.text`。
- `Image.src`，不要用 `Image.url`。
- `Button.label`，不要用 `Button.child`。
- `styles.backgroundColor`、`styles.borderRadius`、`styles.fontSize`，不要用 CSS kebab-case。
- 可点击容器使用 `onClick: [{ "call": "...", "args": {...} }]`。
- 只有使用语义 `Button` 时才使用 `Button.action`；如果同时存在 `action` 和 `onClick`，`action` 优先。

## 卡片布局指导

- `2x2`：root `width: 160`，`height: 160`，root padding `10` 到 `12`，2 到 3 个主区域。
- `2x4`：root `width: 320`，`height: 160`，root padding `10` 到 `12`，2 到 4 个主区域横向排列。
- 使用约 `20` 到 `24` 的 `borderRadius` 和 `clip: true`。
- 除非使用有明确理由的重复项模式，否则每个 row 限制为 2 或 3 个直接子节点。
- `Stack` 用于层叠光晕/图片/进度效果，`Column`/`Row` 用于信息布局。
- 使用 `itemMargin` 控制 Row/Column 子节点间距。
- 保持短受保护文本可读：时间、温度、数量、CTA、状态标签、电量百分比。
- 对受约束的标题值，优先使用 `maxLines: 1` 和 `minFontSize`。
- 不要在日期、星期、时间、状态、CTA、主指标、主标题或用户要求字段等关键信息上使用 `textOverflow: "ellipsis"`。通过减少 padding/gaps/字号、移动次要文本、拆行或选择 `2x4` 让关键文本放下。

## 数据模型规则

- 用 `{ "path": "/..." }` 绑定动态可见数据。
- 只有结构性装饰值才保持字面量，例如空 spacer 文本。
- 可见组件使用的每个绝对路径都必须存在于 `updateDataModel.value`。
- 宿主动作参数尽量绑定到数据：

```json
"onClick":[{"call":"openTrainingPlan","args":{"planId":{"path":"/plan/id"}}}]
```

## 表达式规则

表达式只在 extended catalog 中可用，并且只用于 `updateComponents` 的标量值：

```json
{"content":"{{ '剩余 ' + $__dataModel.countdown.days + ' 天' }}"}
```

桌面卡片中谨慎使用表达式。一句话生成时，优先在 `updateDataModel` 中预计算展示字符串，因为这样更容易校验和本地化。

不要在 `id`、`component`、path 字符串或 event `call` 名称中使用表达式。

## 交互规则

- 默认最多一个主动作。
- 当整个视觉区域可点击时，在 `Stack`、`Row` 或 `Column` 上使用 `onClick`。
- 当控件语义上应是带直接标签文本的按钮时，使用 `Button`。
- EventHandler 条目需要 `call`；`args`、`as` 和 `condition` 可选。
- 内置 extension functions 包括 `setDataModel`、`setAttributes`、`navigate`、`scrollTo`、`break` 和 `sendToAssistant`。应用特定函数只有在宿主提供时才允许使用。

## 媒体规则

- 有可用资源时，使用本地资源或用户提供的 URL。
- 不要编造 `https://example.com` 或占位图片 URL。
- 如果没有真实媒体，用 `linearGradient`、半透明块、文本字形、`Progress` 和 `Divider` 创造视觉丰富度。

## 输出质量清单

- [ ] 每行一个 JSON object。
- [ ] 所有消息使用同一个 `surfaceId`。
- [ ] 使用 extended catalog。
- [ ] 存在 `root`，且所有 child 引用可解析。
- [ ] 正确使用 `Text.content`、`Image.src`、`Button.label`。
- [ ] Root 适配 `160 x 160vp` 或横版 `320 x 160vp`。
- [ ] 所有可见绑定路径都有数据。
- [ ] 文本紧凑，并且很可能适配所选卡片尺寸。
- [ ] 关键信息有明确完整显示宽度计划，不依赖 ellipsis/clip。
- [ ] 动作有真实 event/function handler。
- [ ] 没有占位远程媒体 URL。
- [ ] 结构由规则构造，不是复制模板。
