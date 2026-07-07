# A2UI Form 协议精简摘要

本文是 `harmony-card-dsl-validator` 的默认协议参考。完整原文保存在 [`harmonyos-a2ui-form-protocol-full.md`](harmonyos-a2ui-form-protocol-full.md)，仅在本摘要不足以裁决时读取。

## 1. Form 裁剪范围

Form 是 HarmonyOS A2UI 扩展协议的严格子集：

- 只使用扩展组件，不支持 A2UI 原生组件。
- `createSurface.catalogId` 必须是 `"ohos.a2ui.extended.catalog"`。
- 不支持 `theme`。
- 不支持多端响应式断点变量 `$__widthBreakpoint`、`$__colorMode`。
- 支持自定义组件和自定义函数，但必须由宿主 catalog 明确注册；未声明时按高风险或阻塞处理。

Form 默认支持 10 个组件：

| 类型 | 组件 |
| --- | --- |
| 展示 | `Text`、`Image`、`Divider`、`Progress` |
| 交互 | `Button`、`Checkbox` |
| 布局 | `Row`、`Column`、`List`、`Stack` |

默认排除：

`TextInput`、`Toggle`、`Radio`、`CheckboxGroup`、`Select`、`NavContainer`、`Tabs`、`TabContent`、`Web`、`Grid`、`If`

## 2. 消息流

常见卡片结果使用 JSONL，每行一个 message object：

1. `createSurface`
2. `updateComponents`
3. `updateDataModel`

关键规则：

- 每条消息 `version` 为 `"v0.9"`。
- `updateComponents` 必须在 `createSurface` 之后。
- `updateComponents` 与 `updateDataModel` 的相对顺序协议上无硬约束，但卡片生成结果推荐先组件后数据。
- Form 不支持增量/流式构建，同一 surface 仅接受一次完整 `updateComponents`。
- 后续数据变化通过多次 `updateDataModel` 完成。
- 不同 surface 的消息独立；同一卡片结果内 `surfaceId` 应一致。

`createSurface`：

```json
{
  "version": "v0.9",
  "createSurface": {
    "surfaceId": "main",
    "catalogId": "ohos.a2ui.extended.catalog"
  }
}
```

`updateComponents`：

```json
{
  "version": "v0.9",
  "updateComponents": {
    "surfaceId": "main",
    "components": [
      {"id": "root", "component": "Column", "children": ["title"]},
      {"id": "title", "component": "Text", "content": "Hello"}
    ]
  }
}
```

`updateDataModel`：

```json
{
  "version": "v0.9",
  "updateDataModel": {
    "surfaceId": "main",
    "path": "/",
    "value": {"title": "Hello"}
  }
}
```

`updateDataModel.path` 使用 JSON Pointer。路径不存在时，运行时可自动创建中间路径。

## 3. 组件与属性速查

### Text

- 必需属性：`content`
- 常见样式：`fontSize`、`fontWeight`、`fontColor`、`maxLines`、`minFontSize`、`textOverflow`、`textAlign`、`wordBreak`
- 常见错误：写成 `text`

### Image

- 必需属性：`src`
- 常见样式：`width`、`height`、`objectFit`、`aspectRatio`
- `src` 和 `styles.backgroundImage` 只使用本地/资源路径；不要使用网络 URL、占位图 URL、SVG、`data:image/svg+xml`
- 常见错误：写成 `url`

### Divider

- 样式：`strokeWidth`、`vertical`、`color`

### Progress

- 属性：`value`、`total`
- `total` 必需
- 样式：`type` 可为 `linear`、`ring`、`eclipse`、`scaleRing`、`capsule`；`color`

### Button

- 必需/关键属性：`label`
- 点击写在 `onClick` EventHandler 数组中
- 不使用 `Button.action`、`Button.child`

### Checkbox

- 常用属性：`label`、`value`、`group`、`select`
- 样式：`selectedColor`、`unSelectedColor`、`shape`、`mark`
- Form 不支持 `onChange`，交互仍用 `onClick`

### Row / Column

- `children`：字符串数组，或模板对象 `{ "path": "...", "componentId": "...", "itemVar"?: "...", "indexVar"?: "..." }`
- `itemMargin`：子项间距
- `Row.wrap`：`noWrap|wrap`
- 对齐样式放在 `styles`：
  - `Row.styles.justifyContent`
  - `Row.styles.alignItems`
  - `Column.styles.justifyContent`
  - `Column.styles.alignItems`

### List

- `children`：字符串数组或模板对象
- `space`：列表项间距
- 样式：`listDirection`、`scrollBar`、`nestedScroll`

### Stack

- `children`：字符串数组
- 不支持模板对象
- 样式：`alignContent`

## 4. 通用样式

常用通用样式：

- 尺寸：`width`、`height`、`constraintSize`
- 盒模型：`margin`、`padding`
- 背景：`backgroundColor`、`backgroundImage`、`backgroundImageSizeWithStyle`、`linearGradient`
- 边框：`borderRadius`、`borderWidth`、`borderColor`
- 布局：`layoutWeight`、`flexShrink`
- 视觉：`shadow`、`visibility`、`clip`

样式键使用 camelCase，不使用 CSS kebab-case，例如写 `fontSize`，不要写 `font-size`。

## 5. children 与模板

普通 children：

```json
{"id": "root", "component": "Column", "children": ["title", "body"]}
```

模板 children：

```json
{
  "id": "list",
  "component": "List",
  "children": {
    "path": "/items",
    "componentId": "itemTpl",
    "itemVar": "item",
    "indexVar": "index"
  }
}
```

规则：

- 只有 `Row`、`Column`、`List` 支持模板 children。
- `Stack` 不支持模板 children。
- `children` 不应内联组件 object；组件应放在扁平 `components` 数组中，用 id 引用。
- 完整协议允许 `itemVar`、`indexVar`。变量名不带 `$`，匹配 `^[a-zA-Z_][a-zA-Z0-9_]*$`。
- 当前 `$harmony-card-generation` 生成 skill 更严格，默认只使用 `{componentId,path}`；校验时要区分“协议允许”和“生成 skill 偏离”。

## 6. DataModel 绑定

原生 path 绑定：

```json
{"content": {"path": "/meeting/title"}}
```

规则：

- JSON Pointer 使用 `/` 分隔，例如 `/meeting/title`。
- 不要把点路径写进 JSON Pointer，例如 `/meeting.title`。
- 模板内可使用相对路径，例如 `{"path": "title"}`。
- path 绑定值本身不是表达式，不要写 `{"path": "{{ ... }}"}`。

字符串拼接可用 `formatString`：

```json
{
  "content": {
    "call": "formatString",
    "args": {"value": "${/weather/temp}° ${/weather/status}"}
  }
}
```

`formatString` 只做简单拼接；复杂日期、货币、条件文案建议预计算到 DataModel。

## 7. 表达式与变量

完整 A2UI Form 协议支持表达式：

```json
{"content": "{{ $__dataModel.user.name + ' 您好' }}"}
```

表达式规则：

- 必须以 `{{` 开始，以 `}}` 结束。
- 一个字符串中只能有一个完整表达式；不要写 `"{{ $a }} {{ $b }}"`。
- 不支持嵌套表达式。
- 表达式总长度不超过 2048 字符。
- 括号嵌套深度不超过 20 层。
- 表达式只用于 JSON value，不用于 key。
- `id`、`component`、EventHandler `call`、EventHandler `as` 不支持表达式。
- 内置函数仅支持 `size()`。
- 字符串字面量使用单引号；布尔值使用小写 `true`、`false`。

变量：

- DataModel：`$__dataModel.user.name`
- JSON Pointer 引用：`${/user/name}`，可作为 `$__dataModel.user.name` 的补充
- 模板默认变量：`$item`、`$index`
- 模板自定义变量：`itemVar: "product"` 后用 `$product`
- 行为链变量：EventHandler `as: "result"` 后用 `$result`
- 事件上下文：`$context.componentId`、`$context.eventData`

校验策略：

- A2UI Form 协议层允许表达式。
- 当前 `$harmony-card-generation` 默认禁用表达式。若校验生成 skill 产物，表达式应作为偏离约束提示，但不要误判为协议不支持。
- `$__widthBreakpoint`、`$__colorMode` 在 Form 中排除，应判为错误。

## 8. 事件与行为链

Form 只支持通用事件 `onClick`。

不支持：

`onAppear`、`onChange`、`onSelect`、`onReachStart`、`onReachEnd`

EventHandler：

```json
{
  "onClick": [
    {
      "call": "openDetail",
      "args": {"id": "{{ $__dataModel.item.id }}"},
      "as": "result",
      "condition": "{{ $__dataModel.enabled }}"
    }
  ]
}
```

规则：

- 事件值必须是 EventHandler 数组。
- 每个 handler 必须有 `call`。
- `call` 是函数名，不支持表达式。
- `args` 可为静态值、表达式或嵌套对象。
- `condition` 是表达式字符串；无 `condition` 时默认执行。
- `as` 不带 `$`，后续用 `$result` 引用。
- 自定义函数必须由宿主 catalog 声明。若未声明，按高风险或阻塞提示。

## 9. 校验与生成 skill 的差异点

本校验 skill 按两层标准判断：

1. A2UI Form 协议：完整落地允许表达式、`condition`、`as`、`itemVar`、`indexVar`、自定义函数/组件。
2. `$harmony-card-generation` 生成 skill：为了稳定生成，默认禁用表达式，模板更收敛，点击和数据能力只使用已声明 manifest。

因此输出诊断时要明确区分：

- “协议错误”：运行时或协议层不可接受。
- “生成 skill 偏离”：协议可能允许，但不符合当前生成 skill 的收敛规则。
- “落地风险”：需要宿主 manifest、资源、函数或能力补充。
