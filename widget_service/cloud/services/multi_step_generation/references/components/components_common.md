# Design System

## 1. 组件总览

> 阅读约定：每个组件的“组件属性”就是生成代码时可使用的真实显示 Props；“组件样式”记录设计师给出的视觉规范；“布局约束”记录组件与 `Card`、`Stack`、`Grid` 的组合方式。设计必选与 runtime 容错会在同一张属性表中分别说明。设计构成字段不一定是 JSX Props。每个组件允许绑定的数据字段和动作均在本文件对应组件章节内说明；所有 `icon` 和数组项中的 Icon 都必须逐字使用当前输入 `assetCandidates[].src` 中已有的值，并按候选项 `description` 选择语义匹配的资源。凡示例出现完整资源路径，均以“当前任务的 `assetCandidates` 已包含完全相同的 `src` 和匹配的 `description`”为局部前提；示例路径不是内建资源，也不能在其他任务中直接复用。可选 Icon 没有候选时省略；Icon 必选的组件没有语义匹配候选时不要选用。

### 数据与动作引用共同约定

- `dataIds` 只记录可见显示 Prop 对应的输入 `data[].id`，不参与样式或布局计算。已绑定的显示 Prop 可以保留输入样例值、按组件合同调整显示格式或省略；不得用 ID 字符串替代显示内容。
- `dataIds` 的 key 必须是对应组件属性表明确允许绑定的 Prop。通常每个 value 原样引用一个输入中真实存在且当前任务内唯一的 `id`；唯一例外是 `EventCard.dataIds.time` 可按 `[dtStartId, dtEndId]` 顺序引用两个 ID。不得缩写、改名或虚构 ID。
- 根据 `userQuery` 概括出的卡片标题、区块标签、静态单位和按钮文案是静态 UI 文案，不绑定。标题或副标题只有在当前输入 `data[]` 明确提供对应字段时才绑定；不得按业务域构造 `*.cardTitle`、`*.subtitle` 等不存在的 ID。
- `dataIds` 引用的数据类型必须与目标 Prop 的用途兼容。最终渲染为可见文本的 Prop 可绑定 string、integer 或 number，数字由文本组件直接显示；参与进度计算的 Prop 通常只能绑定 integer 或 number，`ProgressCircle.externalText` 可额外接受纯数字字符串或数字百分比字符串并在组件内部转换。Boolean 优先绑定 `done` 等 boolean Prop。确实需要把 Boolean 显示成双状态文案且输入没有描述性字符串时，必须同时为同一 Prop 提供完整的 `dataValueMaps`，其中 `true`／`false` 都是非空且不同的字符串；禁止只按当前样例值静态翻译。
- `dataValueMaps` 只做 Boolean 到可见文本的响应式映射，不代替 `dataIds`，也不能用于进度值、布局或视觉属性。其 key 必须同时存在于同一对象的 `dataIds`；数组项需要映射时，将 `dataValueMaps` 与该项的 `dataIds` 写在同一个 item 内。
- 布尔值使用表达式，例如 `disabled={true}`，不能写成字符串 `disabled="true"`。
- Boolean 可直接用于 `disabled`、`done` 等 boolean Prop。文本 Prop 不接受裸 Boolean；只有同时通过同名 `dataIds` 和完整 `dataValueMaps={{ prop: { true: "…", false: "…" } }}` 声明双状态文案时，才允许把 Boolean 响应式显示为文本。
- 所有来自输入 `data` 的可见业务值都必须绑定；通常一个显示 Prop 只绑定一个数据 ID，只有 `EventCard.time` 可按组件合同同时绑定开始与结束两个 ID。`Card`、`Stack`、`Grid`、Icon、appearance、尺寸、位置和颜色等视觉属性不得绑定。
- 多个输入字段不得在 JSX 中手工拼成一个动态字符串。应使用组件的多 item 模式分别绑定，或拆成多个组件；`EventCard.time` 的开始／结束时间必须使用规定的二元 ID 数组，不得手工拼接。添加或删除绑定不得改变其余 Props、组件树和槽位尺寸。
- 静态 `label`、`unit` 和 `separator` 可以说明动态值，但必须遵守对应组件合同，不得改变数值和业务语义。只有输入 `data[].type` 为 `integer`／`number` 且 `value` 确实是数字时，才可补充静态单位；输入为 `string` 时必须原样保留完整字符串，不得自行拆分或补写单位。
- 格式化字符串只能绑定到接受字符串的显示 Prop；`EmphasizedData` 会自动拆分完整字符串，生成代码仍原样填写 `value="25 分钟"`。`ProgressCircle` 只绑定 `externalText`，由组件内部解析其中的数字驱动圆环；其他进度组件仍按各自属性表绑定实际进度值。`ProgressCircleSingle.value` 在没有独立数值字段时允许绑定完整的格式化百分比字符串。
- `actionId` 只能原样引用输入 `actions[].id`。`actions[].description` 仅用于选择动作，不输出为 JSX Prop；一个控件最多引用一个动作，同一 `actionId` 在一张卡片中最多使用一次。

### 1.1 2×2、2×4 通用组件

本文件只包含两种 Card 尺寸都可使用的组件。Runner 会根据当前任务的 `Card.size`，继续拼接对应尺寸的专属组件文档。

`SingleLineTitle`、`DoubleLineTitle`、`Badge`、`EmphasizedData`、`EmphasisText`、`SecondaryBody`、`Summary`、`InfoBlock`、`TableText`、`ProgressLine2`、`ProgressCircleSingle`、`ProgressCircle`、`NumericRatio`、`NumericRatioStack`、`EventCard`、`H_BarChart`、`PillButton`

## 2. 标题组件

### 2.1 SingleLineTitle

单行标题，用于卡片内容区左上角。

标题通常是根据 `userQuery` 概括的静态 UI 文案，此时只传 `title`。当地点名、设备名、事件名等输入业务字段直接承担标题角色时，才通过 `dataIds.title` 绑定其真实 ID。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `title` | `string` | 必选 | 无默认值 | 单行标题，超出可用宽度时省略 |
| `icon` | `string` | 可选；仅允许天气 Icon 或应用 Icon | 不传时不显示 | 使用当前输入中语义匹配的天气 Icon 或应用 Icon `src`；睡眠、电话、提醒、定位、充电等通用功能 Icon 禁止放入标题区 |
| `iconAlt` | `string` | 有语义的 Icon 必须提供 | 默认空字符串，按装饰图处理 | 描述 Icon 表达的对象或天气含义 |
| `iconFit` | `"contain" \| "cover"` | 可选 | `"contain"` | 天气 Icon 通常使用 `contain`；应用 Icon 通常使用 `cover` |
| `invertIcon` | `boolean` | 可选 | `false` | 仅在深色背景且单色 Icon 对比度不足时使用 |
| `dataIds` | `{ title?: string }` | `title` 来自输入数据时必选 | 不传时无绑定 | 仅允许绑定 `title`；Icon 与视觉属性不得绑定 |

```jsx
<SingleLineTitle title="手机使用时长" />
```

```jsx
<SingleLineTitle
  title="上海今日天气"
  icon="resources/base/media/icon_weather1.svg"
  iconAlt="天气"
/>
```

#### 组件样式

| 样式属性 | 值 | 说明 |
|---|---|---|
| `typography` | Body_S / 12px / Regular 400 / 18px | 单行标题字体规格；末尾的 18px 为字体行高 |
| `layout-height` | 18px；带 Icon 时整体为 20px | 无 Icon 时按文字行高占位；带 20px Icon 时组件整体取较大高度 |
| `color` | `font-secondary` | 标题字色 |
| `text-align` | `left` | 文本左对齐 |
| `line-clamp` | `1` | 只显示一行 |
| `text-overflow` | `ellipsis` | 超出可用宽度时显示省略号 |
| `icon-size` | 20 × 20vp | 可选的标题区右侧 Icon |
| `icon-gap` | 4vp | 文本与 Icon 的水平间距 |
| `placement` | 内容区左上角 | 组件在卡片内的位置 |
| `next-component-gap` | 2px | 与下方组件的垂直间距 |
| `safe-area-inline` | 12vp | 卡片左右安全边距 |

### 2.2 DoubleLineTitle

标题和次要信息组成的双层标题。

`title` 与 `secondaryInfo` 分别按内容来源判断是否绑定，不能因为使用双行标题就默认两项都是动态数据。任一项来自 `userQuery` 的静态概括时不绑定；来自当前输入 `data[]` 的业务值时绑定该项的真实 ID。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `title` | `string` | 必选 | 无默认值 | 主标题，最多一行 |
| `secondaryInfo` | `string` | 必选 | 无默认值 | 连接状态、地点等第二层信息，最多两行 |
| `icon` | `string` | 可选；仅允许天气 Icon 或应用 Icon | 不传时不显示 | 使用当前输入中语义匹配的天气 Icon 或应用 Icon `src`；睡眠、电话、提醒、定位、充电等通用功能 Icon 禁止放入标题区 |
| `iconAlt` | `string` | 有语义的 Icon 必须提供 | 默认空字符串 | Icon 的可访问文本 |
| `iconFit` | `"contain" \| "cover"` | 可选 | `"contain"` | 应用 Icon 推荐 `cover` |
| `invertIcon` | `boolean` | 可选 | `false` | 深色背景下的单色 Icon 可按需反色 |
| `dataIds` | `{ title?: string, secondaryInfo?: string }` | 对应显示字段来自输入数据时必选 | 不传时无绑定 | `title` 与 `secondaryInfo` 分别绑定各自的数据 ID |
| `dataValueMaps` | `{ title?: { true: string, false: string }, secondaryInfo?: { true: string, false: string } }` | 对应绑定源为 Boolean 且需要显示文案时必选 | 不传时不转换 | 必须与同名 `dataIds` 配对；优先使用输入已有的描述性字符串字段 |

```jsx
<DoubleLineTitle
  title="FreeBuds Pro 3"
  secondaryInfo="已连接"
  dataIds={{
    title: "device.name",
    secondaryInfo: "device.isConnected",
  }}
  dataValueMaps={{
    secondaryInfo: {
      true: "已连接",
      false: "未连接",
    },
  }}
/>
```

#### 组件样式

| 样式属性 | 值 | 说明 |
|---|---|---|
| `title-typography` | Body_S / 12px / Bold 700 / 18px | 主标题字体规格 |
| `title-color` | `font-primary` | 主标题字色 |
| `secondary-typography` | Body_S / 12px / Medium 500 / 18px | 次要信息字体规格 |
| `secondary-color` | `font-secondary` | 次要信息字色 |
| `title-line-clamp` | `1` | 主标题最多一行 |
| `secondary-line-clamp` | `2` | 次要信息最多两行 |
| `text-overflow` | `ellipsis` | 主标题和次要信息超出时显示省略号 |
| `content-gap` | 4vp | 主标题与次要信息的垂直间距 |
| `two-line-secondary` | 最多 2 行 | 次要信息允许两行；组件实际占位高度由文本行数与所在布局槽共同决定 |
| `icon-size` | 20 × 20vp | 可选的标题区右侧 Icon |
| `icon-gap` | 4vp | 文本与 Icon 的水平间距 |
| `alignment` | 左对齐 | 主标题、次要信息整体左对齐 |
| `placement` | 内容区左上角 | 组件在卡片内的位置 |
| `safe-area-inline` | 12vp | 卡片左右安全边距 |

> 字体行高不是布局槽高度。`SingleLineTitle` 的文字行高为 18px，无 Icon 时占高 18px，带 20px Icon 时组件整体占高 20px；`DoubleLineTitle` 的主标题与次要信息行高均为 18px。组件与下方内容的间距由对应 Layout Pattern 决定。

### 2.3 Badge

圆矩形数值胶囊，只用于呈现标题中的数量、总数或未读数。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `value` | `number \| string` | 必选 | 无默认值 | 标题中的数值；字符串仅用于 `99+` 等格式化数值 |
| `color` | `"blue" \| "orange" \| "green" \| "red" \| "purple" \| "cyan" \| "pink"` | 可选 | `"blue"` | 只使用设计规范列出的主题色；runtime 额外支持的颜色不自动进入生成规范 |
| `dataIds` | `{ value?: string }` | `value` 来自输入数据时必选 | 不传时无绑定 | 仅允许绑定 `value`；颜色保持静态 |

`color` 可选值：

- `blue`
- `orange`
- `green`
- `red`
- `purple`
- `cyan`
- `pink`

```jsx
<Badge
  value="99+"
  color="red"
  dataIds={{ value: "mail.unreadCountText" }}
/>
```

#### 布局约束（非 Badge Props）

`Badge` 必须与它所修饰的标题处于同一个横向标题组，间距固定为 8px。`Badge` 不是标题组件的 prop，间距也不由 Badge 自身生成。

```jsx
<Stack direction="row" gap={8} align="center">
  <SingleLineTitle
    title="未读邮件"
    dataIds={{ title: "mail.sectionTitle" }}
  />
  <Badge
    value="99+"
    color="red"
    dataIds={{ value: "mail.unreadCountText" }}
  />
</Stack>
```

不要生成 `badge={<Badge />}` 等不存在的标题 Props，也不要把 Badge 单独放入正文或状态区域。

#### 组件样式

| 样式属性 | 值 | 说明 |
|---|---|---|
| `height` | 16px | 固定高度 |
| `width` | `auto` | 宽度随数值自适应 |
| `border-radius` | 8px | 圆矩形胶囊 |
| `padding-inline` | 6px | 左右内边距 |
| `typography` | Caption_M / 10px / Medium 500 | 数值字体规格 |
| `alignment` | 水平、垂直居中 | 数值在容器内的位置 |
| `background-color` | 主题色浅色版本 | 默认使用蓝色浅色背景 |
| `color` | 主题色实色版本 | 数值文字颜色 |
| `title-gap` | 8px | 与左侧标题的水平间距 |
| `usage` | 仅标题数值 | 不用于状态、类别、说明文字或普通标签 |

## 3. 文本组件

### 3.1 EmphasizedData

统一的核心数值组件，用于时长、日期、温度、容量等数据。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `value` | `string \| number` | 单组数据时必选，不用于纯文本如"正常电量"、"户外跑步" | `items` 存在时忽略 | 若绑定字段是完整格式化字符串，必须原样填写样例值，例如 `"2小时15分"`；组件会自动拆分，生成代码不得自行改写 |
| `unit` | `string` | 仅 `integer`／`number` 输入可使用 | 不传时不显示 | 只有绑定字段的真实输入值是无单位数字时才可填写；`string` 输入无论内容如何都不得再填写 `unit` |
| `items` | `Array<{ key?, value, unit?, dataIds? }>` | 多个独立数据字段时使用 | 存在时覆盖顶层 `value`、`unit` | 不用于手工拆分一个完整字符串；`"2小时15分"` 仍使用顶层 `value` 和一个原始 `dataId` |
| `dataIds` | `{ value?: string, unit?: string }` | 对应属性来自输入数据时必选 | 不传时无绑定 | 只填写输入中真实存在的原始数据 ID，不得构造额外数据 ID |

#### 数值与单位拆分规则

- 判断只依据当前输入的真实 `type` 和 `value`，不得根据字段名或 description 猜测、提取单位。
- 输入 `type` 为 `integer`／`number` 且 `value` 是独立数字时，才使用 `value + unit`。
- 输入 `type` 为 `string` 时，将完整样例原样放入 `value`，只绑定原始 `dataId`；即使字符串看起来像 `"320千卡"`、`"25分钟"`，也不要填写 `unit`，不要手工拆成多个 `items`。
- 组件会把可完整识别的字符串自动分段。例如 `"2小时15分"` 显示为大号 `2`、小号“小时”、大号 `15`、小号“分”；无法识别时只显示完整原文，绝不同时显示原文和额外单位。
- 摄氏温度是特例：`"29.0 ℃"`／`"29.0℃"` 显示为大号 `29.0°`，删除其中的 `C`、保留 `°`，且不生成独立单位；`"26°"` 仍作为完整大号值显示。

完整格式化时长只绑定原始字段：

```jsx
<EmphasizedData
  value="2小时15分"
  dataIds={{ value: "sleep.deepSleepDurationText" }}
/>
```

```jsx
<EmphasizedData
  value="29.0 ℃"
  dataIds={{ value: "weather.temperatureText" }}
/>
```

以下两种输入必须区别处理。

输入是数字：

```json
{ "id": "health.caloriesBurned", "type": "number", "value": 320 }
```

```jsx
<EmphasizedData value={320} unit="千卡" dataIds={{ value: "health.caloriesBurned" }} />
```

输入是完整字符串：

```json
{ "id": "health.caloriesBurnedText", "type": "string", "value": "320千卡" }
```

```jsx
<EmphasizedData value="320千卡" dataIds={{ value: "health.caloriesBurnedText" }} />
```

`unit` 与主值保持同一行。`"充电中"`、`"已连接"` 等状态不是单位，应使用独立的 `Summary` 或 `SecondaryBody`。

#### 组件样式

| 样式属性 | 值 | 说明 |
|---|---|---|
| `value-typography` | Display_S / 38px / Bold 700 / 38px | 核心数值使用紧凑 `line-height: 1`；数值与单位共同收敛在 38vp 行盒内，不因不同字体的 baseline 扩大组件可见高度 |
| `value-color` | `font-primary` | 核心数值字色 |
| `unit-typography` | Caption_L / 12px / Regular 400 / 18px | 单位字体规格 |
| `unit-color` | `font-secondary` | 单位字色 |
| `align-items` | `flex-end` | 数值与单位按行盒底部对齐；`ProgressLine2` 在自身固定 47vp 数值槽中继续使用 baseline 对齐 |
| `gap` | 2px | 数值与单位、单位与下一组数值之间的水平间距 |
| `temperature-format` | `26°` | 数值和 `°` 作为整体采用 38px Bold 样式 |
| `description-slot` | 无 | 数值和可选单位就是全部信息 |

### 3.2 EmphasisText

文档中名称为“强调文本”，由主文本和次文本组成。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `mainText` | `string` | 必选 | 无默认值 | 主文本 |
| `secondaryText` | `string` | 必选 | 无默认值 | 关联对象、设备名称或补充说明；正式 runtime 合同要求提供 |
| `dataIds` | `{ mainText?: string, secondaryText?: string }` | 对应文本来自输入数据时必选 | 不传时无绑定 | 两个显示 Prop 分别绑定各自的数据 ID |
| `dataValueMaps` | `{ mainText?: { true: string, false: string }, secondaryText?: { true: string, false: string } }` | 对应绑定源为 Boolean 且需要显示文本时必选 | 不传时不转换 | 必须与同名 `dataIds` 配对；`true` 和 `false` 必须是不同的非空文本 |

```jsx
<EmphasisText
  mainText="已连接"
  secondaryText="FreeBuds Pro 3"
  dataIds={{
    mainText: "earphone.isConnected",
    secondaryText: "earphone.earphoneName",
  }}
  dataValueMaps={{
    mainText: {
      true: "已连接",
      false: "未连接",
    },
  }}
/>
```

#### 组件样式

| 样式属性 | 值 | 说明 |
|---|---|---|
| `main-typography` | Title_S / 20px / Bold 700 / 27px | 主文本字体规格 |
| `main-color` | `font-primary` | 主文本字色 |
| `secondary-typography` | Body_S / 12px / Regular 400 / 16px | 次文本字体规格 |
| `secondary-color` | `font-secondary` | 次文本字色 |
| `flex-direction` | `column` | 主文本在上，次文本在下 |
| `gap` | 0vp | 两行之间的垂直间距 |
| `alignment` | 左对齐 | 整体在模块内左对齐 |

### 3.3 SecondaryBody

文档中名称为“次要文本”，用于卡片里的辅助正文信息。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `body` | `string` | 单个完整字段时必选 | `items` 存在时不使用 | 辅助正文；通过顶层 `dataIds.body` 最多绑定一个动态字段 |
| `items` | `Array<{ key?, label?, value, dataIds? }>` | 原始值需要静态标签，或多字段组合时必选 | `body` 存在时不使用 | 至少一项；`value` 原样使用输入提供的完整值，并通过项内 `dataIds.value` 独立绑定；`label` 保持静态；不支持 `unit` |
| `separator` | `string` | 仅 items 模式可选 | `" ｜ "` | 多个 item 之间的静态分隔符；父容器宽度不足时允许随内容换行 |
| `dataIds` | `{ body?: string }` | 顶层 `body` 来自输入数据时必选 | 不传时无绑定 | 只用于单字段模式；items 模式在每项内部绑定 `value` |

`body` 与 `items` 互斥，必须且只能选择一种模式。单个完整字段使用 `body`；需要静态标签或多个独立动态字段时使用 `items`。纯数字、百分比、时间和孤立时语义不完整的等级值必须有静态 `label`；自描述状态可以省略。`items` 不设置固定数量上限，父容器宽度不足时由 runtime 自动换行；仍需确保换行后的整体内容不超过卡片高度。

`items` 不支持 `unit`。`value` 必须原样使用输入提供的完整展示值，例如 `"29.0 ℃"`、`"40分"`、`"260 千卡"`；不得拆分、补写或根据 description 推断单位。若输入只提供不含单位的数字，组件只展示该数字。

```jsx
<SecondaryBody items={[{ label: "用时", value: "40分", dataIds: { value: "healthSport.exerciseDurationText" } }]} />
```

```jsx
<SecondaryBody
  body="多云"
  dataIds={{ body: "weather.condition" }}
/>
```

```jsx
<SecondaryBody
  items={[
    {
      value: "晴",
      dataIds: { value: "weather.condition" },
    },
    {
      label: "空气",
      value: "优",
      dataIds: { value: "weather.airQualityLevel" },
    },
  ]}
/>
```

```jsx
<SecondaryBody
  items={[
    {
      label: "已用",
      value: "43%",
      dataIds: { value: "memory.usedPercentText" },
    },
    {
      label: "剩余",
      value: "4.5GB",
      dataIds: { value: "memory.availableText" },
    },
  ]}
/>
```

#### 组件样式

| 样式属性 | 值 | 说明 |
|---|---|---|
| `typography` | Body_M / 14px / Regular 400 / 19px | 正文字体规格 |
| `color` | `font-primary` | 正文字色 |
| `text-align` | `left` | 文本左对齐 |
| `component-gap` | 2px | 与上方或下方组件的垂直间距 |
| `field-separator` | `｜` | 多个字段不使用 `·` 分隔 |
| `items-layout` | 水平分段、自动换行 | 内部片段继承 `SecondaryBody` 原有字号、行高和字色；父容器宽度不足时按可用宽度换行 |
| `line-count` | 1 行或多行 | `body` 与 `items` 模式都默认允许换行；不需要额外传入 `wrap` |
| `placement` | 卡片左下角区域 | 常用位置 |
| `content-processing` | 结构化精简 | 去除重复标签和冗余修饰 |

结构化精简可以删除静态冗余，也可以按组件合同调整动态样例值的显示结构和格式，但不得改变数值或业务语义。动态标签和值必须分段表达，并继续绑定原始 `dataId`：

- 输入值为 `"优"` 时，使用 items 模式的静态 `label="空气"` 和动态 `value="优"`，不得把动态值改成 `"空气优"`。
- 输入值为数字 `86` 时，使用 `EmphasizedData value={86} unit="分"`，不得把动态值改成字符串 `"86分"`。
- 入睡时间、起床时间或最高温、最低温来自不同数据字段时，分别绑定到独立组件或同一组件的独立 item；只有输入本身提供完整展示字段时，才能原样绑定到一个 `body` Prop。
- 裸数字、百分比和“优／正常／高”等孤立状态通常需要静态语义 Label；温度文本（如 `29°C`）和时刻文本（如 `07:30`）自身已带明确类型信息，不强制重复添加“温度”“时间”等 Label。

### 3.4 Summary

用于紧凑的次要信息和辅助说明，包括数据来源、更新时间、结果说明，以及“体感27℃ ｜ 湿度68%”一类需要独立绑定的并列指标。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `content` | `string` | 单个完整字段时必选 | `items` 存在时不使用 | 紧凑辅助信息；通过顶层 `dataIds.content` 最多绑定一个动态字段 |
| `items` | `Array<{ key?, label?, value, dataIds? }>` | 原始值需要静态标签，或多字段组合时必选 | `content` 存在时不使用 | 至少一项；`value` 原样使用输入提供的完整值，并通过项内 `dataIds.value` 独立绑定；`label` 保持静态；不支持 `unit` |
| `separator` | `string` | 仅 items 模式可选 | `" ｜ "` | 多个 item 之间的静态分隔符；父容器宽度不足时允许随内容换行 |
| `dataIds` | `{ content?: string }` | 顶层 `content` 来自输入数据时必选 | 不传时无绑定 | 只用于单字段模式；items 模式在每项内部绑定 `value` |

`content` 与 `items` 互斥，必须且只能选择一种模式。单个完整字段使用 `content`；需要静态标签或多个独立动态字段时使用 `items`。纯数字、百分比、时间和孤立时语义不完整的等级值必须有静态 `label`；自描述状态可以省略。`items` 不设置固定数量上限，父容器宽度不足时由 runtime 自动换行；仍需确保换行后的整体内容不超过卡片高度。

`items` 不支持 `unit`。每个 item 的 `value` 都必须原样使用对应输入字段的完整值，不得拆分、补写或推断单位；若输入值不含单位，就只展示原始值。

```jsx
<Summary items={[{ label: "消耗", value: "260 千卡", dataIds: { value: "healthSport.exerciseCalorieText" } }, { label: "最高心率", value: 168, dataIds: { value: "healthSport.exerciseHeartRateMax" } }]} />
```

```jsx
<Summary
  content="数据更新于刚刚"
  dataIds={{ content: "weather.updatedAtText" }}
/>
```

完整辅助文本作为一个输入字段整体变化时，直接绑定 `content`，不要在 JSX 中拆分或拼接年月等片段：

```jsx
<Summary
  content="2026年10月"
  dataIds={{ content: "calendar.monthText" }}
/>
```

```jsx
<Summary
  items={[
    {
      label: "体感",
      value: 31,
      dataIds: { value: "weather.current.feelsLikeC" },
    },
    {
      label: "湿度",
      value: 68,
      dataIds: { value: "weather.current.humidityPercent" },
    },
  ]}
/>
```

> runtime 函数暂时继续接收旧 JSX 使用的 `density`、`wrap`，但它们不属于正式组件合同，也不会出现在新生成 Props 中。当前默认根据父容器宽度自动换行，不需要设置 `wrap`。

#### 组件样式

| 样式属性 | 值 | 说明 |
|---|---|---|
| `typography` | Caption_M / 10px / Regular 400 / 14px | 辅助说明字体规格 |
| `line-height` | 14px | 与 runtime `.summary-text` 的生成卡样式一致 |
| `color` | `font-secondary` | 文本字色 |
| `field-separator` | `｜` | 并列的辅助数据使用全角竖线分隔 |
| `items-layout` | 水平分段、自动换行 | 内部片段继承 `Summary` 原有字号、行高和字色；父容器宽度不足时按可用宽度换行 |
| `line-count` | 1 行或多行 | `content` 与 `items` 模式都默认允许换行；仍应优先精简内容以控制卡片高度 |
| `presentation` | 纯文本 | 单字段或多片段都不增加背板、Icon 或其他可见容器 |
| `background` | 无 | 无背板 |
| `decoration` | 无 | 无按钮、无装饰图形 |

### 3.6 InfoBlock

固定为 136 × 64vp 的紧凑信息组件，由主文本、副文本、背板和右侧尾部视觉组成。尾部视觉必须在 Icon 与 ProgressCircle 中二选一；选择取决于输入数据是需要图形识别，还是需要表达 0–100 的占比／进度。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `primaryText` | `string \| number` | 必选 | 无默认值 | 左侧第一行核心信息；数值和文本均可，单行省略 |
| `secondaryText` | `string \| number` | 必选 | 无默认值 | 左侧第二行解释信息或次要信息，单行省略 |
| `unit` | `string` | 可选，静态 UI 文案 | 不传时不显示 | 主文本为数值时与其同行显示；不允许绑定数据 ID |
| `visual` | `InfoBlockIconVisual \| InfoBlockProgressVisual` | 必选，二选一 | 非法或缺失时 runtime 不显示尾部视觉，但不符合生成规范 | 右侧 Icon 或 ProgressCircle；不得同时提供两种视觉 |
| `dataIds` | `{ primaryText?: string, secondaryText?: string }` | 对应文本来自输入数据时分别绑定 | 不传时无绑定 | 只允许绑定 `primaryText`、`secondaryText`；`unit` 与 `visual` 不绑定 |

`visual` 只接受两种结构：`{ type: "icon", icon, color?: "native" }` 用于图形识别；`{ type: "progressCircle", icon }` 用于 0–100 占比／进度，圆环直接解析并限制 `primaryText`。两者的 `icon` 均必选且必须来自语义匹配的 `assetCandidates`；单色 Icon 默认显示为白色，仅保留原生多色外观时写 `color: "native"`。

#### 组件样式

| 样式属性 | 值 | 说明 |
|---|---|---|
| `size` | 136 × 64vp | 固定宽高，不随父容器拉伸 |
| `padding-inline` | 8vp | 内容距背板左右安全距离 |
| `border-radius` | 16vp | 背板圆角 |
| `background` | 白色 / 20% | 0827 深色卡片上的半透明背板 |
| `content-gap` | 4vp | 左侧文本组与右侧视觉的最小间距 |
| `primary-typography` | Subtitle_S / 14px / Bold 700 / 20px | 主文本；`font-primary` |
| `unit-typography` | Caption_M / 10px / Medium 500 / 16px | 单位；`font-secondary`；与主文本间距 2vp |
| `secondary-typography` | Caption_L / 12px / Medium 500 / 18px | 副文本；`font-secondary` |
| `text-row-gap` | 0vp | 主、副文本上下紧邻 |
| `text-overflow` | 单行省略 | 主文本值和副文本超宽时显示省略号 |
| `icon-size` | 24 × 24vp | Icon 分支的尾部视觉 |
| `progress-size` | 44 × 44vp | ProgressCircle 分支的圆环 |
| `progress-stroke` | 6vp | Track：白色 / 10%；Bar：白色 / 100% |
| `progress-inner-icon` | 20 × 20vp | 白色 / 90%，圆环内居中 |

#### 合法 JSX 示例与布局约束

- `InfoBlock` 自身始终保持 136 × 64vp；宽高由组件固定，外层 `Stack` 或 `Grid` 只负责按当前尺寸的 Layout Pattern 分配位置和数量。
- 在 2×2 卡片中，`InfoBlock × 2` 使用无标题的 Type 3：`Card` 设置 `gap={8}`，每个 `InfoBlock` 分别放入一个 `<Stack basis={64} height={64}>`。

```jsx
<Card size="2x2" appearance="purple-gradient" gap={8}>
  <Stack basis={64} height={64}>
    <InfoBlock
      primaryText="昨夜7小时1分"
      secondaryText="午睡0分"
      visual={{
        type: "icon",
        icon: "moon_z_fill_1.svg",
      }}
      dataIds={{
        primaryText: "healthSport.nightSleepDurationText",
        secondaryText: "healthSport.totalNapDurationText",
      }}
    />
  </Stack>
  <Stack basis={64} height={64}>
    <InfoBlock
      primaryText="昨夜82分"
      secondaryText="睡眠｜科学睡眠"
      visual={{
        type: "icon",
        icon: "moon_z_fill_1.svg",
      }}
      dataIds={{
        primaryText: "healthSport.sleepScore",
        secondaryText: "healthSport.sleepTypeDesc",
      }}
    />
  </Stack>
</Card>
```

ProgressCircle 分支仍使用同一槽位结构。`unit` 和静态说明不绑定；输入提供的主、副文本分别通过同名 `dataIds` 绑定：

```jsx
<Stack basis={64} height={64}>
  <InfoBlock
    primaryText={68}
    unit="%"
    secondaryText="剩余电量"
    visual={{
      type: "progressCircle",
      icon: "icon_charge.svg",
    }}
    dataIds={{ primaryText: "battery.remainingPercent" }}
  />
</Stack>
```

### 3.8 TableText

由至少两组“左侧文本标签 + 右侧文本／数值单位参数”组成的纵向表格文本组件，用于紧凑展示同一主题下的多项属性。每组占满父容器宽度，标签左对齐，参数右对齐。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `items` | `Array<{ key?, label, parameter, dataIds? }>` | 必选，至少 2 项 | 默认空数组；runtime 可渲染已有的短数组，但少于 2 项不符合新生成规范 | 多组纵向排列；每项必须同时提供 `label` 和 `parameter` |
| `items[].label` | `string` | 必选，静态 UI 文案 | 无默认值 | 左侧文本标签，不允许绑定数据 ID |
| `items[].parameter` | `string \| number` | 必选 | 无默认值 | 右侧文本或数值单位参数；来自输入数据时必须绑定 |
| `items[].dataIds` | `{ parameter?: string }` | `parameter` 来自输入数据时必选 | 不传时无绑定 | 只允许绑定 `parameter`；不得包含 `label` 或其他 key |

```jsx
<TableText
  items={[
    {
      label: "运动时长",
      parameter: "1小时40分钟",
      dataIds: { parameter: "workout.durationText" },
    },
    {
      label: "消耗热量",
      parameter: "260千卡",
      dataIds: { parameter: "workout.caloriesText" },
    },
    {
      label: "平均心率",
      parameter: "135次/分钟",
      dataIds: { parameter: "workout.averageHeartRateText" },
    },
  ]}
/>
```

`label` 用于解释右侧参数的业务含义，始终由生成代码静态提供。即使输入数据中存在相同文本，也不得生成 `dataIds.label`。只有 `parameter` 会在转换后关联动态数据路径；增加绑定不会改变组件 DOM、样式或布局。

#### 组件样式

| 样式属性 | 值 | 说明 |
|---|---|---|
| `width` | `100%` | 每组及整个组件占满父容器分配的宽度 |
| `items-count` | ≥ 2 | 至少包含两组文本 |
| `direction` | 纵向 | 多组自上而下排列 |
| `row-gap` | 2vp | 相邻两组之间的垂直间距 |
| `column-gap` | 8vp | 同组标签与参数之间的最小水平间距 |
| `alignment` | 标签左对齐；参数右对齐；两者底部对齐 | 单组内部对齐规则 |
| `label-typography` | Caption_M / 10px / Medium 500 / 16px | 左侧标签字体规格 |
| `label-color` | `font-secondary` | 左侧标签字色 |
| `parameter-typography` | Caption_M / 10px / Medium 500 / 16px | 右侧参数字体规格 |
| `parameter-color` | `font-primary` | 右侧参数字色 |
| `parameter-max-width` | 70% | 参数最长占组件宽度的 70% |
| `overflow` | 单行省略 | 标签或参数超出各自可用宽度时显示省略号 |

#### 布局约束

- 0827 规范示例用于 2×2 Card 的 Type 1 布局，外层布局负责将组件放入内容区并分配宽度。
- `TableText` 不提供业务 `width`、位置或对齐 Props；不得通过 `style`、`className` 改写内部行结构。
- 少于两组时不得选择 `TableText`；应改用与单项信息语义匹配的文本组件。

## 4. 图表与数据组件

### 4.1 公共字段模型

进度组件的业务输入可能包含以下语义字段：

> 本节字段属于设计输入／业务数据模型，不是可以直接传给所有进度组件的 JSX Props。必须按照具体组件的属性表和字段映射，将它们转换为 `currentValue`、`totalValue`、`value`、`externalText`、`displayValue`、`leftLabel`、`rightLabel` 等真实 Props。

| 字段 | 类型 | 必选 | 说明 |
|---|---|---:|---|
| `percent` | `number` | 是或推导 | 占比值，直接驱动 Progress Bar |
| `percentText` | `string` | 是或推导 | `percent` 的整数百分比显示值；按 `Math.trunc(clamp(percent, 0, 100)) + "%"` 生成，Bar 仍使用原始 `percent` 精度 |
| `current` | `number` | 否 | 当前值，与 `total` 成对使用 |
| `total` | `number` | 否 | 总值；没有 `percent` 时通过 `current / total × 100` 推导占比 |
| `displayValue` | `{ value, unit?, qualifier? }` | 否 | 可用量、剩余量或当前量等绝对值 |
| `label` | `string` | 否 | 数值的语义标签 |

字段映射原则：

- `ProgressLine2`、`ProgressCircleSingle` 等组件的 Bar 由各自数值 Prop 驱动；`ProgressCircle` 是例外，只接收 `externalText`，并在内部从该值派生 0–100 的数值
- `H_BarChart.items[].percent` 驱动每条 Bar 的宽度，`items[].valueUnit` 显示格式化后的数值与单位；每项只有 `valueUnit` 允许通过 `dataIds.valueUnit` 绑定数据 ID
- 组件同时接收进度值与展示值时，可见文本使用 `percentText`，Bar 保留原始 `percent` 精度；`ProgressCircle` 只有一个 `externalText` 数据源，因此文本与 Bar 都以其中解析出的数字为准
- 没有 `percent` 时，可以由 `current / total` 推导
- 除 `ProgressCircle` 外，每个进度组件必须按具体属性表提供进度数值，或同时提供 `current` 和 `total`；使用推导方式时 `total` 必须大于 0
- 最终驱动 Bar 的占比值必须限制在 0–100 之间
- `displayValue` 用于显示绝对值，例如 `4.5 GB 可用`
- 只有占比值时，显示槽必须直接呈现百分比

错误与正确调用对比。下面的正确调用以 `*-soft` 浅色 Card 为背景，因此使用 `mode="light"` 并省略 `barColor`：

```jsx
<ProgressLine2
  currentValue={60}
  totalValue={100}
  value={60}
  unit="%"
  mode="light"
  dataIds={{
    currentValue: "task.progressPercent",
    value: "task.progressPercent",
  }}
/>
```

不要生成 `<ProgressLine2 percent={60} label="已完成" />`；`percent` 和 `label` 需要先映射，不能直接作为未知 Props 传入。`label` 由所在模块标题承载。

### 4.2 ProgressLine2

由 `EmphasizedData` 和线性 Bar 组成的自适应宽度进度组件。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `currentValue` | `number` | 必选 | `0` | 当前值或 percent |
| `totalValue` | `number` | 必选且必须大于 0 | `100` | 总值；百分比场景使用 100 |
| `value` | `string \| number` | 与 `items` 二选一；也可省略以显示推导百分比 | 省略时显示截去小数部分的百分比 | `EmphasizedData` 的核心数值；例如 43.75% 可见文本为 `43%` |
| `unit` | `string` | 可选 | 不传时不显示 | `EmphasizedData` 的短单位或短限定词；不得承载状态或重复 `value` 已包含的单位 |
| `items` | `Array<{ key?, value, unit?, dataIds? }>` | 多组数值时使用 | 存在时覆盖顶层 `value`、`unit` | 数组结构与 `EmphasizedData.items` 相同；每项分别绑定自己的值和单位 |
| `mode` | `"light" \| "dark"` | 生成卡片必选 | `"light"` | 表示 ProgressLine2 所在背景的明暗：`light` 为黑色 10% Track + Blue 400 Bar，`dark` 为白色 40% Track + 白色 Bar |
| `barColor` | `string` | 仅实现层覆盖 | 由 `mode` 决定：`light` 为 Blue 400，`dark` 为白色 | 只用于设计规范明确要求的特殊覆盖；新生成不得用它自由改变 Bar 色，也不得填写硬编码颜色 |
| `dataIds` | `{ currentValue?: string, totalValue?: string, value?: string, unit?: string }` | 对应字段来自输入数据时必选 | 不传时无绑定 | Bar 数值必须绑定；顶层显示值／单位分别绑定，items 模式改用项内 `dataIds` |

设计字段 `percent` 映射为 `currentValue={percent} totalValue={100}`；`displayValue` 拆分为 `value` 和可选 `unit`。`mode` 直接表示组件所在 Card 背景的明暗，与 `H_BarChart` 的命名一致；正常生成不需要传 `barColor`：

| Card 背景 | 必须使用的配置 | Track 颜色 | Bar 颜色 |
|---|---|---|---|
| `*-soft` 浅色背景 | `mode="light"`；省略 `barColor` | 黑色 10% | Blue 400 · 100% |
| `*-gradient` 深色背景 | `mode="dark"`；省略 `barColor` | 白色 40% | 白色 100% |

不要通过 `barColor` 为普通生成场景选择近似色。浅色与深色背景的标准 Bar 色均由 `mode` 自动确定；只有设计规范明确给出特殊 Bar 色时，才允许把 `barColor` 作为实现层覆盖。

```jsx
<ProgressLine2
  currentValue={5860}
  totalValue={10000}
  value="5860"
  unit="步"
  mode="dark"
  dataIds={{
    currentValue: "activity.steps",
    totalValue: "activity.stepGoal",
    value: "activity.steps",
  }}
/>
```

当 `totalValue` 也来自动态数据，或可见百分比需要独立格式化时，必须显式提供并绑定 `value` 或 `items`；“动态 `currentValue` + 静态 `totalValue={100}`”可以省略可见值。

> 以下三个未包裹 `<Card>` 的独立示例均以 `*-soft` 浅色背景为前提，因此使用 `mode="light"` 并省略 `barColor`。如果放入 `*-gradient` 深色 Card，只需改为 `mode="dark"`。

```jsx
<ProgressLine2
  currentValue={43.75}
  totalValue={100}
  value={4.5}
  unit="GB可用"
  mode="light"
  dataIds={{
    currentValue: "memory.usedPercent",
    value: "memory.availableGB",
  }}
/>
```

单组绝对值继续使用顶层 `value` 和 `unit`：

```jsx
<ProgressLine2
  currentValue={37}
  totalValue={90}
  value={37}
  unit="天剩余"
  mode="light"
  dataIds={{
    currentValue: "subscription.remainingDays",
    totalValue: "subscription.totalDays",
    value: "subscription.remainingDays",
  }}
/>
```

多个数值使用 `items`，每个动态值分别绑定；单位保持静态并沿用 `EmphasizedData` 的视觉规格：

```jsx
<ProgressLine2
  currentValue={345}
  totalValue={480}
  items={[
    {
      value: 5,
      unit: "小时",
      dataIds: { value: "battery.remainingHours" },
    },
    {
      value: 45,
      unit: "分钟",
      dataIds: { value: "battery.remainingMinutes" },
    },
  ]}
  mode="light"
  dataIds={{
    currentValue: "battery.remainingMinutesTotal",
    totalValue: "battery.estimatedDurationMinutes",
  }}
/>
```

#### 组件样式

| 样式属性 | 值 | 说明 |
|---|---|---|
| `flex-direction` | `column` | 按 `EmphasizedData + Track/Bar` 纵向排列 |
| `width` | `100%` | 撑满所在模块 |
| `min-width` | `0` | 避免处于 flex 内容区时按内容收缩 |
| `emphasized-data-min-height` | 47px | 固定 ProgressLine2 内数值区域的最小高度 |
| `emphasized-data-transform` | `translateY(3.5px)` | 去除数字行盒底部约 3.5px 的视觉留白 |
| `value-line-height` | 47px | ProgressLine2 内 `EmphasizedData` 数值行高 |
| `vertical-gap` | 8vp | `EmphasizedData` 与 Bar 的垂直间距 |
| `glyph-to-bar-gap` | 8vp | 数字字形底部到 Bar 顶部的目标视觉间距 |
| `track-height` | 8vp | Track 固定高度 |
| `bar-height` | 8vp | Bar 固定高度 |
| `bar-width` | `clamp(percent ?? current / total × 100, 0, 100)%` | Bar 宽度计算公式 |
| `track-color-mode-light` | 黑色 10% | `mode="light"` 时的 Track 颜色，用于 `*-soft` 浅色 Card |
| `track-color-mode-dark` | 白色 40% | `mode="dark"` 时的 Track 颜色，用于 `*-gradient` 深色 Card |
| `bar-color-soft-card` | Blue 400 · 100% | `*-soft` 浅色 Card 使用 `mode="light"` 时的默认 Bar 颜色 |
| `bar-color-gradient-card` | 白色 100% | `*-gradient` 深色 Card 使用 `mode="dark"` 时的默认 Bar 颜色 |

字段映射：

- Bar ← `percent`
- 有 `displayValue` 时：`EmphasizedData.value` ← `displayValue.value`
- 有 `displayValue` 时：`EmphasizedData.unit` ← `unit + qualifier`
- 无 `displayValue` 时：`EmphasizedData` 显示截去小数部分的 `percent`，例如 43.75% 显示为 `43%`
- 无 `displayValue` 时，`label` 由所在模块标题承载

### 4.3 H_BarChart

文本标签、数值单位、Track 与 Bar 组成的横向柱状图组件。仅用于比较至少两条同维度数据，不支持单条数据；每条 Bar 的宽度由 `percent` 决定。组件始终撑满父布局分配的宽度，不写死 Card 宽度，因此可用于 2×2 和 2×4 Card。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `items` | `Array<{ key?, label, valueUnit, percent, dataIds? }>` | 必选且至少 2 项 | 默认空数组；少于 2 项时 runtime 不渲染 | 多条可比较的柱状数据；数组顺序就是从上到下的显示顺序 |
| `mode` | `"light" \| "dark"` | 生成 Card 必选 | `"light"` | 表示 H_BarChart 所在背景的明暗，决定文本、Track 和 Bar 配色 |

每个 `items` 项的结构：

| 字段 | JSX 类型 | 设计约束 | 说明 |
|---|---|---|---|
| `key` | `string \| number` | 可选 | React 列表稳定标识；没有时使用数组顺序 |
| `label` | `string` | 必选、静态 | 左侧文本标签；单行省略，不绑定数据 ID |
| `valueUnit` | `string` | 必选、动态 | 右侧数值单位，例如 `"60%"`；这是每项唯一允许绑定数据 ID 的属性 |
| `percent` | `number` | 必选，范围 0–100 | 驱动 Bar 宽度；runtime 会将非法值回退为 0，并将结果限制在 0–100；不绑定数据 ID |
| `dataIds` | `{ valueUnit?: string }` | `valueUnit` 来自输入数据时必选 | 只允许包含 `valueUnit`；不得绑定 `label` 或 `percent` |

`mode` 直接表示所在 Card 背景的明暗：

| Card 背景 | H_BarChart 配置 | 文本 | Track | Bar |
|---|---|---|---|---|
| `*-soft` 浅色背景 | `mode="light"` | 背景主题深色 · 60% | 背景主题深色 · 20% | 背景主题深色 · 100% |
| `*-gradient` 深色背景 | `mode="dark"` | 白色 · 50% | 白色 · 20% | 白色 · 100% |

> `ProgressLine2` 与 `H_BarChart` 的 `mode` 含义一致：浅色背景使用 `light`，深色背景使用 `dark`。

#### 合法 JSX 示例

外层布局负责为 H_BarChart 分配当前尺寸的布局槽位，组件自身不固定所在区域：

```jsx
<H_BarChart
  mode="light"
  items={[
    {
      label: "手机剩余电量",
      valueUnit: "68%",
      percent: 68,
      dataIds: { valueUnit: "battery.remainingPercentText" },
    },
    {
      label: "手表剩余电量",
      valueUnit: "52%",
      percent: 52,
      dataIds: { valueUnit: "battery.watchPercentText" },
    },
  ]}
/>
```

#### 组件样式

| 样式属性 | 值 | 说明 |
|---|---|---|
| `width` | 100% | 撑满父布局分配的模块宽度；适配 2×2 与 2×4 Card |
| `items-count` | ≥ 2 | 仅支持多条数据，按数组顺序纵向排列；少于 2 项不渲染 |
| `items-gap` | 11vp | 相邻数据组的纵向间距 |
| `meta-track-gap` | 4vp | 文本行与 Track 的纵向间距 |
| `meta-gap` | 8vp | 标签与数值单位之间的最小水平间距 |
| `label/value-typography` | Body_M / 14px / Bold 700 / 20px | 标签左对齐并单行省略；数值单位右对齐且不换行 |
| `track-size` | 父容器宽度 × 6vp | Track 占满组件宽度 |
| `track-radius` | 32px | Track 胶囊圆角 |
| `bar-size` | `clamp(percent, 0, 100)% × 6vp` | Bar 宽度表达百分比，高度与 Track 一致 |
| `bar-radius` | 2vp | Bar 圆角 |

布局约束：

- 2×2 与 2×4 Card 均可使用；外层 `Stack`、`Grid` 或 Layout Pattern 决定它占据的模块。
- 只在存在至少两条同维度、可比较的数据时使用；单条数据必须改用与其语义匹配的其他数据组件。
- `H_BarChart` 是整宽组件，父槽必须提供明确宽度；不要通过 `style`、`className` 或组件业务 Props 改写宽度。
- 数据绑定只更新可见的 `valueUnit`；`label` 和 `percent` 是生成时确定的静态配置。

### 4.4 ProgressCircleSingle

单个占比值使用的圆环组件，由圆环和右侧文本组组成。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `value` | `number \| string` | 必选；数字范围 0–100，字符串必须是完整格式化百分比 | 无效值会回退为 0；有效值会限制到 0–100 | 驱动圆环 Bar，对应设计字段 `percent`；字符串只接受 `"68%"`、`"43.75%"` 等“数字 + `%`”格式 |
| `icon` | `string` | 必选 | 无默认值 | 圆环中心功能 Icon；使用当前输入中语义匹配的候选资源 `src` |
| `displayValue` | `string` | 可选 | 数字 `value` 显示截去小数部分的 `${value}%`；格式化百分比字符串 `value` 原样显示 | 绝对值或格式化百分比 |
| `label` | `string` | 必选 | 无默认值 | 右侧文本组顶部的语义标签 |
| `secondaryLabel` | `string` | 可选 | 不传时使用两行文本组 | 存在时自动切换为 Label + Value + Secondary Label 三行规格，不使用 `lines` prop |
| `ariaLabel` | `string` | 生成 Card 必选 | 省略时回退为 `label + 最终显示值` | 完整描述占比、绝对值和状态 |
| `appearance` | `"card"` | 生成 Card 必选 | 默认普通 catalog 模式 | 对 2×2 与 2×4 Card 均启用卡片专属 Icon、精度和颜色处理 |
| `trackColor` | `string` | 仅实现层覆盖 | 使用组件默认值 | `appearance="card"` 时会被卡片模式覆盖 |
| `barColor` | `string` | 仅实现层覆盖 | 设计规范绿色 | `appearance="card"` 时会被卡片模式覆盖 |
| `dataIds` | `{ value?: string, displayValue?: string, label?: string, secondaryLabel?: string }` | 对应字段来自输入数据时必选 | 不传时无绑定 | `value` 必须绑定实际进度数据；其余可见文本按输入字段分别绑定 |

`value` 优先绑定 number／integer 类型的原始百分比。当输入没有独立数值字段、只提供语义明确的完整格式化百分比字符串时，也可以直接绑定该字符串；runtime 会使用其中的数字驱动圆环，并原样显示百分比文本。该兼容方式只适用于完整百分比字符串，不接受普通文本或混合文案。

动态数值 `value` 省略 `displayValue` 时会直接显示实时数值和 `%`；需要独立格式化、截断或显示另一项数值时，应提供并绑定 `displayValue`。

```jsx
<ProgressCircleSingle
  value="68%"
  icon="resources/base/media/battery_leaf_fill.svg"
  label="剩余电量"
  secondaryLabel="充电中"
  ariaLabel="剩余电量68%，充电中"
  appearance="card"
  dataIds={{
    value: "phoneBattery.batterySOCText",
    secondaryLabel: "phoneBattery.chargingStatusDesc",
  }}
/>
```

```jsx
<ProgressCircleSingle
  value={43.75}
  icon="resources/base/media/externaldrive_fill.svg"
  displayValue="4.5GB"
  label="剩余内存"
  secondaryLabel="已用 43.75%"
  ariaLabel="内存已用43.75%，可用4.5GB"
  appearance="card"
  dataIds={{
    value: "memory.usedPercent",
    displayValue: "memory.availableText",
    label: "memory.availableLabel",
    secondaryLabel: "memory.usedPercentText",
  }}
/>
```

三行模式用于同时显示百分比和一条完整状态说明。`secondaryLabel` 仍是单个显示 Prop；只有输入提供完整组合文本时，才能把“充电中 ｜ 正常电量”整体绑定给它：

```jsx
<ProgressCircleSingle
  value={68}
  icon="resources/base/media/battery_leaf_fill.svg"
  displayValue="68%"
  label="剩余电量"
  secondaryLabel="充电中 ｜ 正常电量"
  ariaLabel="剩余电量68%，充电中，正常电量"
  appearance="card"
  dataIds={{
    value: "phoneBattery.batterySOCPercent",
    displayValue: "phoneBattery.batterySOCText",
    secondaryLabel: "phoneBattery.statusSummaryText",
  }}
/>
```

如果“充电状态”和“电量等级”是两个独立输入字段，不能在 JSX 中把它们拼成一个 `secondaryLabel`；应只展示其中一个已有字段，或等待输入侧提供完整组合文本。

#### 组件样式

| 样式属性 | 值 | 说明 |
|---|---|---|
| `size` | 52 × 52vp | 圆环固定尺寸 |
| `stroke-width` | 6vp | Track 与 Bar 统一线宽 |
| `track-color-light` | 黑色 10% | Light 模式 Track 颜色 |
| `track-color-dark` | 白色 10% | Dark 模式 Track 颜色 |
| `bar-color-light` | `#64BB5C` | 亮色 Card 中的 Bar 颜色 |
| `bar-color-dark` | 白色 100% | 暗色 Card 中的 Bar 颜色 |
| `bar-origin` | 12 点方向 | Bar 起始位置 |
| `bar-direction` | 顺时针 | Bar 增长方向 |
| `stroke-linecap` | `round` | Bar 使用圆角端盖 |
| `icon-size` | 20 × 20vp | 圆环中心 Icon 尺寸 |
| `icon-color-light` | 黑色 60% | 亮色 Card 中的圆环中心 Icon 颜色 |
| `icon-color-dark` | 白色 60% | 暗色 Card 中的圆环中心 Icon 颜色 |
| `layout` | 圆环在左，文本组在右 | 组件内部布局 |
| `content-gap` | 8vp | 圆环与文本组的水平间距 |
| `alignment` | 垂直居中、模块内左对齐 | 组合整体对齐方式 |

右侧文本组：

| 规格 | 样式属性 | 值 | 说明 |
|---|---|---|---|
| 两行 | `label-typography` | Body_M / 14px / Bold 700 / 20px | 顶部 Label 字体规格 |
| 两行 | `label-color` | `font-primary` | 顶部 Label 字色 |
| 两行 | `value-typography` | Body_S / 12px / Medium 500 / 18px | 底部 Value + Unit 字体规格 |
| 两行 | `value-color` | `font-secondary` | 底部 Value + Unit 字色 |
| 两行 | `line-gap` | 0vp | Label 与 Value 的垂直间距 |
| 三行 | `label-typography` | Body_M / 14px / Bold 700 / 20px | 顶部 Label 字体规格 |
| 三行 | `detail-typography` | Caption_M / 10px / Regular 400 / 16px | Value 与 Secondary Label 字体规格 |
| 三行 | `detail-color` | `font-secondary` | Value 与 Secondary Label 字色 |
| 三行 | `line-gap` | 0vp | Label、Value、Secondary Label 三行之间无额外间距 |
| 全部 | `order` | Label 在上，Value 在下；可选 Secondary Label 最下 | 右侧文本的固定语义顺序 |

### 4.5 ProgressCircle

同时展示两个或四个占比值时使用的圆环组件，包含圆环外部数值。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `icon` | `string` | 必选 | 无默认值 | 圆环中心功能 Icon；使用当前输入中语义匹配的候选资源 `src` |
| `externalText` | `string \| number` | 生成 Card 必选；必须是纯数字或数字百分比 | 原样显示；内部去掉 `%`／`％` 后转为 0–100 数值并驱动圆环 | 直接使用输入提供的完整值，例如 `68`、`"68"` 或 `"68%"`；不要另外编写或绑定 `value` |
| `size` | `"sm" \| "md"` | 按规格选择 | `"sm"` | 两值卡片通常使用 `sm` |
| `ariaLabel` | `string` | 生成 Card 必选 | 省略时回退为最终显示的 `externalText` | 描述对象和百分比 |
| `appearance` | `"card"` | 生成 Card 必选 | 默认普通 catalog 模式 | 对 2×2 与 2×4 Card 均启用卡片 Icon mask 与精度规则 |
| `trackColor` | `string` | 由明暗模式决定 | 黑色 10% | 不作为自由视觉属性使用 |
| `barColor` | `string` | 设计规范固定绿色 | 使用组件默认值 | 不作为自由视觉属性使用 |
| `dataIds` | `{ externalText?: string }` | `externalText` 来自输入数据时必选 | 不传时无绑定 | 只绑定一次原始比例字段；不得添加 `dataIds.value`。integer、number 与 string 类型的比例字段都绑定到 `externalText` |

`externalText` 是生成 Card 时唯一的比例数据源。组件内部会确定性地将 `68`、`"68"`、`"68%"` 或 `"68％"` 解析为数值 `68` 来驱动圆环；外部文本仍原样显示输入值。模型不得为同一业务比例寻找或构造第二个 `value` dataId。

```jsx
<ProgressCircle
  icon="resources/base/media/battery_leaf_fill.svg"
  externalText="68%"
  size="sm"
  ariaLabel="手机电量68%"
  appearance="card"
  dataIds={{ externalText: "phone.batteryPercentText" }}
/>
```

#### 布局约束（非 ProgressCircle Props）

同时展示多个占比值时，每个 `ProgressCircle` 放入当前尺寸 Layout Pattern 分配的独立槽位并水平、垂直居中。数量、网格结构和操作区由当前尺寸的布局文档决定；组件章节不重复声明另一尺寸的布局。

#### 组件样式

| 样式属性 | 值 | 说明 |
|---|---|---|
| `size-sm` | 44 × 44px | `sm` 圆环尺寸 |
| `stroke-width-sm` | 6px | `sm` Track 与 Bar 统一线宽 |
| `icon-size-sm` | 20px | `sm` 中心 Icon 尺寸 |
| `size-md` | 96 × 96px | `md` 圆环尺寸 |
| `stroke-width-md` | 6px | `md` Track 与 Bar 统一线宽 |
| `icon-size-md` | 20px | `md` 中心 Icon 尺寸 |
| `track-color-light` | 黑色 10% | Light 模式 Track 颜色 |
| `track-color-dark` | 白色 10% | Dark 模式 Track 颜色 |
| `bar-color-light` | `#64BB5C` | 亮色 Card 中的 Bar 颜色 |
| `bar-color-dark` | 白色 100% | 暗色 Card 中的 Bar 颜色 |
| `bar-origin` | 12 点方向 | Bar 起始位置 |
| `bar-direction` | 顺时针 | Bar 增长方向 |
| `stroke-linecap` | `round` | Bar 使用圆角端盖 |
| `external-text-typography` | Caption_M / 10px / Medium 500 / 14px | External Text 字体规格 |
| `external-text-placement` | 圆环下方 | External Text 位置 |
| `external-text-gap` | 2vp | External Text 与圆环的垂直间距 |
| `external-text-alignment` | 水平居中 | External Text 与圆环的对齐方式 |

布局规则：

| 样式属性 | 值 | 说明 |
|---|---|---|
| `layout-2-values` | Type 12 双列 | 同时展示两个占比值 |
| `layout-4-values` | Type 6 四宫格 | 同时展示四个占比值 |
| `module-alignment` | 水平居中、垂直居中 | 组件在所在模块中的位置 |
| `external-text-content` | `Math.trunc(percent) + "%"` | 可见占比文本截去小数部分，不替换为 `displayValue`；Bar 仍保留原始精度 |

> `density="compact-4"` 仅由 runtime 暂时兼容旧 JSX，新生成契约已禁止该属性；四值场景统一使用 `size="sm"`。

### 4.6 NumericRatio 与 NumericRatioStack

文档中名称为“数值占比”，只用于同时展示三个占比值。

#### 组件属性

| 组件 | 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|---|
| `NumericRatio` | `icon` | `string` | 必选 | 无默认值 | 对象 Icon；使用当前输入中语义匹配的候选资源 `src` |
| `NumericRatio` | `value` | `string \| number` | 必选 | 数字值截去小数部分并默认补 `%`，字符串原样显示 | 动态原始百分比使用数字，例如 `43.75` 可见为 `43%`；已有完整展示文本时可使用 `"43%"` |
| `NumericRatio` | `unit` | `string` | 可选 | 数字值默认 `%`，字符串默认空 | 静态单位；传空字符串可关闭数字值的默认百分号 |
| `NumericRatio` | `appearance` | `"card"` | 生成 Card 必选 | 默认 img 模式 | 启用卡片 Icon mask |
| `NumericRatio` | `dataIds` | `{ value?: string }` | `value` 来自输入数据时必选 | 不传时无绑定 | 仅允许绑定 `value`；Icon 和静态单位不得绑定 |
| `NumericRatioStack` | `items` | `Array<{ key?, icon, value, unit?, dataIds? }>` | 必选，设计规范固定三项 | runtime 接受任意长度 | 每项必须包含当前输入中语义匹配的候选资源 `src` 和数值 `value`，并通过 `dataIds.value` 独立绑定；对象语义由 Icon 承载 |
| `NumericRatioStack` | `appearance` | `"card"` | 生成 Card 必选 | 默认普通模式 | 自动传递给每个 `NumericRatio` |

#### 合法 JSX 与布局约束

`NumericRatioStack` 只用于恰好 3 个占比值，组件内部已经负责三项纵向排列和 4vp 间距。下面示例中的 `Stack` 负责把整个组件放在主内容区左侧并与模块底端对齐；这些布局属性不是 `NumericRatioStack` Props：

```jsx
<Stack flex={1} minHeight={0} align="flex-start" justify="end">
  <NumericRatioStack
    appearance="card"
    items={[
      {
        icon: "resources/base/media/earphone_case_16644.svg",
        value: 80,
        dataIds: { value: "earbuds.caseBatteryPercent" },
      },
      {
        icon: "resources/base/media/l_circle_fill.svg",
        value: 76,
        dataIds: { value: "earbuds.leftBatteryPercent" },
      },
      {
        icon: "resources/base/media/r_circle_fill.svg",
        value: 74,
        dataIds: { value: "earbuds.rightBatteryPercent" },
      },
    ]}
  />
</Stack>
```

不得在 `value` 中增加“耳机盒”“左耳”等纯文本 Label；对象语义必须由对应 Icon 表达。若 Icon 无法充分区分对象，应改选带文本 Label 槽的组件，而不是扩展 `NumericRatio` 的内容结构。

#### 组件样式

| 样式属性 | 值 | 说明 |
|---|---|---|
| `icon-container-size` | 16 × 16vp | Icon 占位框尺寸 |
| `icon-size` | 12 × 12vp | Icon 内部图形尺寸 |
| `icon-color` | `card-secondary` | 浅色 Card 为黑色 60%，深色 Card 为白色 60% |
| `value-typography` | Caption_M / 10px / Regular 400 / 16px | 数值字体规格 |
| `value-color` | `card-secondary` | 浅色 Card 为黑色 60%，深色 Card 为白色 60% |
| `item-layout` | Icon 在左，`percent` 在右 | 单项内部布局 |
| `icon-value-gap` | 4vp | Icon 与数值的水平间距 |
| `stack-layout` | 三项纵向排列 | 三个占比值的布局方式 |
| `stack-gap` | 4vp | 三项之间的垂直间距 |
| `module-alignment` | 左对齐、底端对齐 | 整体在模块中的位置 |
| `bar` | 无 | 组件不包含 Bar |
| `label-slot` | 无 | 组件内不包含名称、标签或其他纯文本；对象语义由 Icon 承载 |
| `value-content` | `Math.trunc(percent) + "%"` | 数字输入显示截去小数部分的百分比；字符串输入原样保留 |

### 4.7 EventCard

时间线式日程组件，由圆圈、装饰线、日程标题、时间和可选地点组成。组件宽度由父布局槽位决定：2×2 中最大为 116vp；2×4 中取消该上限并使用父槽提供的完整可用宽度。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `title` | `string` | 必选 | 无默认值 | 日程标题，最多两行 |
| `time` | `string` | 必选 | 无默认值 | 时间或时间范围 |
| `location` | `string` | 可选 | 不传时不渲染地点 | 地点或会议室 |
| `dataIds` | `{ title?: string, time?: string \| [string, string], location?: string }` | 对应字段来自输入数据时必选 | 不传时无绑定 | `title`、`location` 各绑定一个 ID；`time` 绑定一个时间 ID，或按 `[dtStartId, dtEndId]` 绑定开始与结束两个 ID，不要绑定`entityId` |

```jsx
<EventCard
  title="产品评审"
  time="09:30 – 10:30"
  location="A区会议室"
  dataIds={{
    title: "calendar.nextEvent.title",
    time: [
      "calendar.nextEvent.dtStart",
      "calendar.nextEvent.dtEnd",
    ],
    location: "calendar.nextEvent.location",
  }}
/>
```

当开始时间和结束时间分别来自两个数据字段时，`time` 保留完整的预览文本，`dataIds.time` 必须按“开始、结束”的顺序传入二元数组。运行时数据更新后，两项会继续组合显示为 `开始时间 – 结束时间`；不得只绑定 `dtStart` 后把 `dtEnd` 静态写入 `time`。

只有开始时间、没有结束时间时，`dataIds.time` 仍使用单个字符串 ID；不要传单元素数组。没有地点数据时省略 `location` 及对应绑定，不生成空字符串或虚构地点：

```jsx
<EventCard
  title="设计评审"
  time="10:30"
  dataIds={{
    title: "calendar.nextEvent.title",
    time: "calendar.nextEvent.dtStart",
  }}
/>
```

EventCard 不提供业务 `width` Prop，也不根据绑定后的文本长度临时改变布局。父级布局负责按当前尺寸的 Layout Pattern 分配宽度：2×2 中组件在父槽位内使用 `width: 100%` 且最大不超过 116vp；2×4 中不设置最大宽度，应使用父槽提供的完整可用宽度，不得在右侧仍有可用空间时保留无意义空白并提前换行。

2×4 中优先让 `EventCard` 独占所在横向内容槽，按 Type 1 的内容区方式使用完整可用宽度。辅助 `Summary` 不应作为同一横排兄弟挤压日程正文；确需保留时，应放入独立的纵向信息槽，并重新检查标题、时间和地点所需高度。

#### 组件样式

| 样式属性 | 值 | 说明 |
|---|---|---|
| `width` | `100%` | 占满父布局为它分配的槽位宽度 |
| `max-width` | 2×2 为 116vp；2×4 为 `none` | 2×4 使用父槽完整可用宽度，避免右侧有空间时标题仍提前换行 |
| `min-width` | `0` | 允许缩小到父槽位宽度，例如 Type 11-A 的 92vp 左下区域 |
| `grid-template-columns` | `8vp minmax(0, 1fr)` | 左侧时间轴固定 8vp，文本区使用剩余宽度，不再固定为 101vp |
| `dot-size` | 8 × 8vp | 左侧圆圈尺寸 |
| `dot-stroke-width` | 1.5vp | 圆圈描边粗细 |
| `dot-color` | `#ff2f23` | 圆圈颜色 |
| `line-width` | 1px | 装饰线宽度 |
| `line-color` | `#d8d8d8` | 装饰线颜色 |
| `dot-line-gap` | 5px | 装饰线起点与圆圈的间距 |
| `rail-content-gap` | 7px | 圆圈/装饰线与文本区的水平间距 |
| `title-typography` | 14px / Medium 500 / 18px | 标题字体规格 |
| `title-color` | `var(--card-primary)` | 跟随 Card 主题；浅色 Card 为黑色 100%，深色 Card 为白色 100% |
| `title-line-clamp` | `2` | 标题最多显示两行 |
| `title-overflow` | `ellipsis` | 标题超出时显示省略号 |
| `time-typography` | 12px / Regular 400 / 16px | 时间字体规格；固定行高参与组件自然高度计算，不得被父级压缩为 0 |
| `time-color` | `var(--card-secondary)` | 跟随 Card 主题；浅色 Card 为黑色 60%，深色 Card 为白色 60% |
| `location-typography` | 12px / Regular 400 / 16px | 地点字体规格；固定行高参与组件自然高度计算，不得被父级压缩为 0 |
| `location-color` | `var(--card-secondary)` | 跟随 Card 主题；浅色 Card 为黑色 60%，深色 Card 为白色 60% |
| `title-body-gap` | 4vp | 标题与正文的垂直间距 |
| `time-location-gap` | 0px | 时间与地点的垂直间距 |
| `line-end-alignment` | 实际显示文本底端 | 装饰线底部对齐位置 |

## 5. 按钮组件

### 通用布局约束（适用于 2×2 与 2×4）

- `PillButton` 及当前尺寸允许的专用操作按钮用作卡片操作入口时，按钮槽或同组按钮容器必须与其所属内容区的底部对齐；存在多个按钮时，整个按钮组贴底排列。各尺寸专用按钮的规则见对应尺寸的组件文档。
- 横向 `Stack` 中只有按钮需要贴底时，将按钮放进与内容区等高的包装 `Stack`，由该包装层使用 `justify="end"`；同一行所有直接子项都需要底部对齐时，父 `Stack` 使用 `align="flex-end"`。
- 纵向 `Stack` 中使用 `justify="end"` 将按钮槽或按钮组推到所属内容区底部。
- 不得使用 `align="center"`、`justify="center"` 或等量上下留白使按钮悬空；按钮上方可以保留自适应剩余空间，按钮下方不得保留非规范间距。

### 5.1 PillButton

胶囊按钮，由必选文本、可选 Icon 和按钮容器组成，可用于 2×2 与 2×4 Card。2×2 中放入 Layout Pattern 明确提供的主要操作槽；2×4 中用于某个语义组／操作区域恰好一个 Action 的情况，并限制在半卡宽父区内。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `label` | `string` | 必选 | 无默认值 | 按钮文本，控制在 4 个汉字以内 |
| `icon` | `string` | 可选 | 不传时只显示文本 | 使用当前输入中适合作为按钮功能的候选资源 `src`；若与卡内其他组件重复则省略 |
| `variant` | `"emphasis" \| "normal"` | 可选；生成 Card 通常省略 | `"emphasis"` | 只在普通 catalog 模式下控制强调程度；Card 模式由 `Card.appearance` 统一配色 |
| `color` | `"primary" \| "secondary" \| "success" \| "discovery" \| "danger" \| "warning" \| "caution"` | 仅 runtime 兼容 catalog | `"primary"` | 新生成禁止传入；Card 内颜色由 `Card.appearance` 派生 |
| `appearance` | `"card"` | 生成 Card 必选 | 默认 catalog 模式 | 使用当前 Card 对应的卡片调色板 |
| `disabled` | `boolean` | 可选 | `false` | 禁用状态 |
| `actionId` | `string` | 启用状态必选 | 不传时无动作绑定 | 原样引用输入 `actions[].id`；一个按钮只能引用一个动作 |

以下 `color` 值仅供旧 catalog JSX 与 runtime 兼容，新生成代码不得使用：`primary`、`secondary`、`success`、`discovery`、`danger`、`warning`、`caution`。

```jsx
<PillButton
  label="一键清理"
  icon="resources/base/media/icon_clear.svg"
  appearance="card"
  actionId="memory.cleanNow"
/>
```

#### 布局约束（非 PillButton Props）

- runtime 几何规格固定为 136 × 36vp、圆角 30vp；组件自身不设置定位。
- 2×2 中由对应 Layout Pattern 提供 136 × 36vp 操作槽。
- 2×4 中某个语义组／操作区域只有一个 Action 时使用 `PillButton`，外层必须把它放入该语义组所属的左或右半卡区域；按钮不得横跨 296vp 安全内容区。
- 2×4 半卡父区通常宽 144vp，`PillButton` 保持自身 136vp 固定宽度，由父区负责左对齐、右对齐或居中；不得通过未知 Prop 或样式把按钮拉伸到 144vp 或 296vp。
- 如果卡片其他组件已经使用相同 Icon，按钮内省略重复 Icon，只保留文本标签。

2×4 单 Action 示例：

```jsx
<Card size="2x4" appearance="green-soft" direction="row" gap={8}>
  <Stack basis={144} width={144} height="full" minWidth={0}>
    {/* 与 Action 对应的主内容 */}
  </Stack>

  <Stack basis={144} width={144} height="full" justify="end" align="center">
    <Stack basis={36} width={136} height={36}>
      <PillButton
        label="一键清理"
        appearance="card"
        actionId="memory.cleanNow"
      />
    </Stack>
  </Stack>
</Card>
```

#### 组件样式

| 样式属性 | 值 | 说明 |
|---|---|---|
| `size` | 136 × 36vp | runtime 固定尺寸；2×4 中也不拉伸为整卡宽度 |
| `padding-inline-catalog` | 12px | 普通 catalog 模式的水平内边距 |
| `padding-card` | 0 | `appearance="card"` 时由固定容器负责内容布局 |
| `border-radius` | 30vp | runtime 固定圆角 |
| `label-typography` | 14px / Medium 500 / 19px | 按钮文本字体规格 |
| `icon-size` | 20 × 20px | 可选 Icon 尺寸 |
| `icon-label-gap` | 8vp | Icon 与文本的水平间距 |
| `content-alignment` | 水平、垂直居中 | Icon 和文本作为整体居中 |
| `layout-responsibility` | 参与正常布局流 | 组件本身不定义定位；操作区由布局规范负责 |
| `variant-emphasis` | 实色背景、通常使用白字 | 仅描述普通 catalog 模式 |
| `variant-normal` | 浅色背景、对应主题色文字 | 仅描述普通 catalog 模式 |
| `hover` | catalog 模式主题色加深；Card 模式保持 `card-action-bg` | 鼠标悬停状态 |
| `active` | catalog 模式主题色继续加深；Card 模式保持 `card-action-bg` | 按压状态 |
| `focus-visible` | 2px 蓝色外轮廓 | 键盘聚焦状态 |
| `disabled` | 透明度 40% | 禁用点击与指针事件 |
| `duplicate-icon-rule` | 省略 Icon | 卡片其他组件已使用同一 Icon 时只保留文本 |
