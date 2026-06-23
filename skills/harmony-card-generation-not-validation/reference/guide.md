# DSL 与卡片生成指南

## 必需消息形状

生成 JSONL，每行必须且只能有一个 JSON object：

```jsonl
{"version":"v0.9","createSurface":{"surfaceId":"sample-card","catalogId":"ohos.a2ui.extended.catalog"}}
{"version":"v0.9","updateComponents":{"surfaceId":"sample-card","components":[{"id":"root","component":"Column","children":["title"],"styles":{"width":160,"height":160,"borderRadius":22,"clip":true}},{"id":"title","component":"Text","content":{"path":"/title"},"styles":{"fontSize":16,"fontWeight":700}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"sample-card","path":"/","value":{"title":"Sample"}}}
```

规则：

- `version` 永远是 `"v0.9"`。
- `catalogId` 永远是 `"ohos.a2ui.extended.catalog"`。
- `createSurface` 不写 `theme`。
- `updateComponents` 必须在 `createSurface` 之后，同一 surface 只写一次完整组件树。
- 所有消息保持同一个 `surfaceId`。
- `updateDataModel` 优先使用 `path: "/"`。

## Root 尺寸

按精确卡片预算设计：

```json
{"id":"root","component":"Column","children":["primary"],"styles":{"width":160,"height":160,"borderRadius":22,"clip":true}}
```

```json
{"id":"root","component":"Row","children":["focal","details","status"],"styles":{"width":320,"height":160,"borderRadius":22,"clip":true}}
```

如果宿主运行时要求响应式宽度，`styles.width` 可以是 `"100%"`，但构图仍必须适配所选宽度预算：`2x2` 为 `160vp`，横版 `2x4` 为 `320vp`。不要使用 `$__widthBreakpoint`。

## 组件模型

使用扁平邻接表：

```json
{"id":"root","component":"Column","children":["title","cta"]}
{"id":"title","component":"Text","content":{"path":"/title"}}
```

不要内联 child component object：

```json
{"id":"root","component":"Column","children":[{"component":"Text","content":"Wrong"}]}
```

## Form 属性名

桌面卡片使用 extended catalog 下的 Form 子集。使用：

- `Text.content`，不要用 `Text.text`。
- `Image.src`，不要用 `Image.url`。
- `Button.label`，不要用 `Button.child`。
- `styles.backgroundColor`、`styles.borderRadius`、`styles.fontSize`，不要用 CSS kebab-case。
- `Row`/`Column` 的 `justifyContent`、`alignItems` 放在 `styles` 内。
- `Stack.alignContent`、`List.listDirection`、`List.scrollBar` 放在 `styles` 内。

## 卡片布局指导

- `2x2`：root `width: 160`，`height: 160`，root padding `10` 到 `12`，2 到 3 个主区域。
- `2x4`：root `width: 320`，`height: 160`，root padding `10` 到 `12`，2 到 4 个主区域横向排列。
- 使用约 `20` 到 `24` 的 `borderRadius` 和 `clip: true`。
- 除非使用有明确理由的模板循环，否则每个 row 限制为 2 或 3 个直接子节点。
- `Stack` 用于层叠光晕/图片/进度效果，`Column`/`Row` 用于信息布局。
- 使用 `itemMargin` 控制 Row/Column 子节点间距。
- 保持短受保护文本可读：时间、温度、数量、CTA、状态标签、电量百分比。
- 对受约束的标题值，优先使用 `maxLines: 1` 和 `minFontSize`。
- 不要在日期、星期、时间、状态、CTA、主指标、主标题或用户要求字段等关键信息上使用 `textOverflow: "ellipsis"`。通过减少 padding/gaps/字号、移动次要文本、拆行或选择 `2x4` 让关键文本放下。

## 数据模型规则

- 动态可见数据优先用原生 path 绑定：`{"path":"/meeting/time"}`。
- 只有结构性装饰值才保持字面量，例如空 spacer 文本。
- 表达式引用的数据应存在于 `updateDataModel.value`。
- `updateDataModel.path` 使用 `/` JSON Pointer。
- 动作参数尽量绑定到数据；点击、拨号、打开应用或详情页优先使用 event capability 中已声明的 `functionCall`：

```json
"onClick":[{"call":"openTrainingPlan","args":{"planId":{"path":"/plan/id"}}}]
```

## 表达式规则（兜底）

表达式是原生 path 绑定和 `formatString` 无法表达时的兜底方式，只在 Form 扩展组件中可用，并且只用于 `updateComponents` 的 value 位置：

```json
{"content":"{{ '剩余 ' + $__dataModel.countdown.days + ' 天' }}"}
```

桌面卡片中谨慎使用表达式。一句话生成时，优先在 `updateDataModel` 中预计算展示字符串，因为这样更容易评审和本地化。

不要在 `id`、`component`、对象 key、event `call` 或 event `as` 中使用表达式。不要在一个字符串中写多段表达式，例如 `"{{ a }} {{ b }}"`。

## 交互规则

- Form 只支持 `onClick`。
- 默认最多一个主动作。
- 当整个视觉区域可点击时，在 `Stack`、`Row` 或 `Column` 上使用 `onClick`。
- 当控件语义上应是带直接标签文本的按钮时，使用 `Button`，并把点击行为写在 `Button.onClick`。
- EventHandler 条目需要 `call`；`args`、`as` 和 `condition` 可选。
- `call` 优先引用 `reference/event-capability/` 中已声明的 `functionCall`；未声明时只能引用宿主 catalog 已声明的自定义函数，或明确声明为宿主假设。
- 不要使用 `Button.action` 或预定义扩展函数。

## 媒体规则

- 需要图标、图片或视觉锚点时，先按 [`asset-library.md`](asset-library.md) 语义匹配已声明素材；用户明确指定的本地/资源路径也可使用。
- `Image.src` 和 `styles.backgroundImage` 只使用用户提供或素材库声明的本地/资源路径。
- 静态素材可直接写 `Image.src`；如果素材由 DataModel 决定，绑定到 `/asset/...` 并把该值初始化为素材库中声明过的 `src`。
- 不要使用网络图片 URL、占位图片 URL、SVG、base64 SVG 或未声明资源路径。
- 如果没有语义匹配的真实资源，用 `linearGradient`、半透明块、文本字形、`Progress` 和 `Divider` 创造视觉丰富度。

## 输出质量清单

- [ ] 每行一个 JSON object。
- [ ] 所有消息使用同一个 `surfaceId`。
- [ ] 使用 extended catalog。
- [ ] `createSurface` 没有 `theme`。
- [ ] 只有一次 `updateComponents`。
- [ ] 存在 `root`，且所有 child 引用可解析。
- [ ] 只使用 Form 支持组件。
- [ ] 正确使用 `Text.content`、`Image.src`、`Button.label`。
- [ ] Root 适配 `160 x 160vp` 或横版 `320 x 160vp`。
- [ ] 表达式引用的数据在 DataModel 中有对应字段。
- [ ] 关键信息有明确完整显示宽度计划，不依赖 ellipsis/clip。
- [ ] 动作有真实 `onClick` EventHandler。
- [ ] 没有网络、占位媒体 URL 或未声明资源路径。
- [ ] 结构由规则构造，不是复制模板。
