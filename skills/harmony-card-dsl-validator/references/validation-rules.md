# HarmonyOS A2UI Form DSL 校验规则

本文档是日常校验主规则。协议细节优先查 [`form-protocol-summary.md`](form-protocol-summary.md)。只有摘要不足以裁决时，才查 [`harmonyos-a2ui-form-protocol-full.md`](harmonyos-a2ui-form-protocol-full.md)。

## 输入解析

- ```genui``` 代码块视为 DSL JSONL。
- ```cardspec``` 或包含 `suggestSize` 的 JSON 代码块视为 CardSpec。
- 无代码块时，每个非空行按一条 JSON object 解析。
- 若用户只给局部组件树，说明无法完整判断 surface、CardSpec 和 root，但仍检查局部语法。

## 协议硬约束

- 每条消息必须是 object，且 `version` 为 `"v0.9"`。
- Form 卡片必须创建 `createSurface.surfaceId` 和 `createSurface.catalogId`。
- `catalogId` 必须为 `"ohos.a2ui.extended.catalog"`。
- `createSurface` 不支持 `theme`。
- `updateComponents` 必须在 `createSurface` 之后。
- 同一 surface 的 Form 卡片只接受一次完整 `updateComponents`；后续通过 `updateDataModel` 更新数据。
- `surfaceId` 必须一致。

## 组件范围

默认支持 10 个扩展组件：

`Text`、`Image`、`Divider`、`Progress`、`Button`、`Checkbox`、`Row`、`Column`、`List`、`Stack`

默认不支持：

`TextInput`、`Toggle`、`Radio`、`CheckboxGroup`、`Select`、`NavContainer`、`Tabs`、`TabContent`、`Web`、`Grid`、`If`

自定义组件只有在用户或宿主明确说明 catalog 已注册时才可接受；否则标为阻塞或高风险。

## 属性和常见错名

| 组件 | 正确属性 | 常见错误 |
| --- | --- | --- |
| `Text` | `content` | `text` |
| `Image` | `src` | `url`、网络 URL、SVG |
| `Progress` | `total`，通常还有 `value` | 缺少 `total` |
| `Button` | `label`，点击用 `onClick` | `child`、`action` |
| `Row`/`Column`/`List` | `children` 为字符串数组或模板对象 | children 内联组件 object |
| `Stack` | `children` 为字符串数组 | 模板 children |

布局对齐类属性放在 `styles` 中：

- `Row.styles.justifyContent`、`Row.styles.alignItems`
- `Column.styles.justifyContent`、`Column.styles.alignItems`
- `Stack.styles.alignContent`
- `List.styles.listDirection`、`List.styles.scrollBar`、`List.styles.nestedScroll`

不要使用 CSS kebab-case 样式键，例如 `font-size`、`background-color`。

## 组件树

- `components` 是数组。
- 每个组件有唯一 `id` 和合法 `component`。
- 完整卡片必须有 `root`。
- `children` 字符串引用必须能在 `components[].id` 中找到。
- `children` 不能内联组件对象。
- 模板模式只允许用于 `Row`、`Column`、`List`：

```json
{
  "children": {
    "path": "/items",
    "componentId": "itemTpl",
    "itemVar": "item",
    "indexVar": "index"
  }
}
```

完整协议允许 `itemVar`、`indexVar`；当前生成 skill 更严格，只要求 `{componentId,path}`。校验时按用户意图区分“协议错误”和“生成 skill 偏离”。

## DataModel 和绑定

推荐原生绑定：

```json
{"content": {"path": "/meeting/title"}}
```

规则：

- `path` 使用 JSON Pointer。绝对路径以 `/` 开头。
- 不要把点路径写成 JSON Pointer，例如 `/meeting.title`。
- 模板内部可使用相对路径，例如 `{"path": "title"}`。
- `formatString` 可用于静态文本拼接：

```json
{"content": {"call": "formatString", "args": {"value": "${/weather/temp}°"}}}
```

## 表达式

完整协议允许表达式：

```json
{"content": "{{ $__dataModel.user.name + ' 您好' }}"}
```

检查点：

- 表达式必须以 `{{` 开始、以 `}}` 结束。
- 一个字符串中不要出现多个独立表达式，例如 `"{{ $a }} {{ $b }}"`。
- 不允许嵌套表达式。
- 表达式总长度不超过 2048 字符，括号嵌套不超过 20 层。
- 表达式只用于 JSON value，不用于 key。
- `id`、`component`、EventHandler `call`、EventHandler `as` 不支持表达式。
- Form 排除 `$__widthBreakpoint` 和 `$__colorMode`。
- 表达式内置函数仅支持 `size()`。
- 字符串字面量使用单引号；布尔值为小写 `true`/`false`。

当前生成 skill 默认禁用表达式。若校验其输出，表达式不是 A2UI 协议错误，但应提示“偏离生成 skill 约束”。

更多表达式运算符、变量作用域和模板变量规则见 [`form-protocol-summary.md`](form-protocol-summary.md)。

## 事件和函数

- Form 只支持通用事件 `onClick`。
- 不支持 `onAppear`、`onChange`、`onSelect`、`onReachStart`、`onReachEnd`。
- 事件值必须是非空 EventHandler 数组。
- 每个 handler 必须有 `call`。
- `call` 是函数名，不能是表达式。
- `args` 可为静态值、表达式、原生绑定对象或嵌套对象。
- `condition` 是表达式字符串；完整协议允许，但生成 skill 默认不鼓励。
- `as` 不带 `$`，后续表达式中用 `$变量名` 引用。
- 若点击能力来自 manifest，参数必须符合 manifest；若是宿主自定义函数，应说明这是宿主假设。

## CardSpec

- `suggestSize` 必须是 `"2x2"` 或 `"2x4"`。
- `suggestSize` 应与 DSL root 尺寸一致：`160x160` 对应 `2x2`，`320x160` 对应 `2x4`。
- 静态卡片可只包含 `suggestSize`。
- 动态卡片必须有 `dataBindings`。
- `dataBindings[].capabilityId` 必须来自已声明 data capability。
- `arguments` 只能使用该 capability 的 `inputSchema.properties`。
- `writeResultTo` 必须位于 `/data` 下。
- 多个 `writeResultTo` 不得相同、互为父子或互相覆盖。
- CardSpec 不包含点击事件、`functionCall`、`supportedTargets` 或组件 catalog。

当前 CreateMyCard 生成 skill 已声明的数据能力只有：

- `weather.overview.get`
- `calendar.events.search`

若用户请求待办、联系人、设备状态、音乐、运动等动态能力但没有 manifest，不能编造 CardSpec；应提示需要补充 data capability manifest 或改为静态降级。

## 媒体与资源

- `Image.src` 和 `styles.backgroundImage` 只接受本地/资源路径。
- 不接受 `http://`、`https://`、`example.com`、`placeholder.com`、`picsum.photos` 等网络或占位图。
- 不接受 SVG 或 `data:image/svg+xml`。
- 若路径未由用户提供、未在素材库声明，标为高风险或阻塞。

## 布局和美观评审

- `2x2`：`160 x 160vp`，主区域 <= 3，适合一个主答案和一个辅助上下文。
- `2x4`：`320 x 160vp`，主区域 <= 4，适合左右关系、双面板、详情加动作。
- 如果内容需要长列表、表格、段落、复杂表单或滚动才能理解，应判断为页面需求。
- 日期、星期、时间、倒计时、温度、电量、百分比、价格、状态、CTA、主标题、用户明确要求字段是受保护内容，不应依赖 `ellipsis`、`clip` 或 marquee。
- 有明确主焦点：大数字、状态、进度、时间、事件标题或真实图片。
- 可点击视觉区域必须有真实 `onClick`。

## 输出诊断建议

每条问题尽量包含严重度、位置、错误现象、协议依据和修改建议。

示例：

```text
- [P0] 组件 `title`：使用了 `Text.text`。Form extended Text 必须使用 `content`；改为 `"content": "今日天气"`。
- [P1] CardSpec `/dataBindings/0/capabilityId`：`todo.items.search` 未在当前 data-capability 中声明。请补充 capability manifest，或将待办区降级为静态 DataModel。
- [P2] 组件 `eventRow`：时间和 CTA 共用窄 Row，CTA 是受保护文本，建议将 CTA 移到底部 pill。
```
