# Design System

## 1. 组件总览

> 阅读约定：每个组件的“组件属性”就是生成代码时可使用的真实显示 Props；“空间占位”只记录与 runtime 对齐、且会影响布局容量判断的外部几何；字体、颜色、背景、圆角、描边、内部 Icon 尺寸与交互态等无需模型控制的组件内部样式不在生成文档中重复。“布局约束”记录组件与 `Card`、`Stack`、`Grid` 的组合方式。设计必选与 runtime 容错会在同一张属性表中分别说明。设计构成字段不一定是 JSX Props。每个组件允许绑定的数据字段和动作均在本文件对应组件章节内说明；所有 `icon` 和数组项中的 Icon 都必须逐字使用当前输入 `assetCandidates[].src` 中已有的模型侧值，并按候选项 `description` 选择语义匹配的资源。默认媒体资源只写 `icon_weather1.svg` 这样的文件名，由 runtime 和后续转换层补全 `resources/base/media/`；非默认目录资源保留输入给出的路径。示例路径不是内建资源，也不能在其他任务中直接复用；当前任务没有同名候选时不得使用示例资源。可选 Icon 没有候选时省略；Icon 必选的组件没有语义匹配候选时不要选用。

### 数据与动作引用共同约定

- `dataIds` 只记录可见显示 Prop 对应的输入 `data[].id`，不参与样式或布局计算。`data[].value` 是预览样例；若 `userQuery` 明确给出同一业务字段的当前具体值，单 ID 绑定的显示 Prop 使用 `userQuery` 中的值并继续绑定原 `dataId`；否则使用样例值。不得用 ID 字符串替代显示内容。
- `dataIds` 的 key 必须是对应组件属性表明确允许绑定的 Prop。通常每个 value 原样引用一个输入中真实存在且当前任务内唯一的 `id`；`EventCard.dataIds.time` 可按 `[dtStartId, dtEndId]` 顺序引用两个 ID，`EmphasisText.dataIds.mainText`、`EmphasisText.dataIds.secondaryText`、`InfoBlock.dataIds.secondaryText` 和 `TableText.items[].dataIds.parameter` 可使用包含两个或更多 ID 的有序数组。不得缩写、改名或虚构 ID。
- 根据 `userQuery` 概括出的卡片标题、区块标签、静态单位和按钮文案是静态 UI 文案，不绑定。标题或副标题只有在当前输入 `data[]` 明确提供对应字段时才绑定；不得按业务域构造 `*.cardTitle`、`*.subtitle` 等不存在的 ID。
- `dataIds` 引用的数据类型必须与目标 Prop 的用途兼容。最终渲染为可见文本的 Prop 可绑定 string、integer 或 number，数字由文本组件直接显示；参与进度计算的 Prop 通常只能绑定 integer 或 number，`ProgressCircle.externalText` 可额外接受纯数字字符串或数字百分比字符串并在组件内部转换。Boolean 优先绑定 `done` 等 boolean Prop。确实需要把 Boolean 显示成双状态文案且输入没有描述性字符串时，必须同时为同一 Prop 提供完整的 `dataValueMaps`，其中 `true`／`false` 都是非空且不同的字符串；禁止只按当前样例值静态翻译。
- `dataValueMaps` 只做 Boolean 到可见文本的响应式映射，不代替 `dataIds`，也不能用于进度值、布局或视觉属性。其 key 必须同时存在于同一对象的 `dataIds`；数组项需要映射时，将 `dataValueMaps` 与该项的 `dataIds` 写在同一个 item 内。
- 布尔值使用表达式，例如 `disabled={true}`，不能写成字符串 `disabled="true"`。
- Boolean 可直接用于 `disabled`、`done` 等 boolean Prop。文本 Prop 不接受裸 Boolean；只有同时通过同名 `dataIds` 和完整 `dataValueMaps={{ prop: { true: "…", false: "…" } }}` 声明双状态文案时，才允许把 Boolean 响应式显示为文本。
- 所有来自输入 `data` 的可见业务值都必须绑定；通常一个显示 Prop 只绑定一个数据 ID。只有组件属性表明确声明数组形式时，才能让同一显示 Prop 绑定多个 ID。`Card`、`Stack`、`Grid`、Icon、appearance、尺寸、位置和颜色等视觉属性不得绑定。
- 多个输入字段不得在 JSX 中手工拼成一个动态字符串。应使用组件的多 item 模式、拆成多个组件，或使用合同明确允许的有序 ID 数组；`EventCard.time` 用 ` – ` 组合开始／结束时间，`EmphasisText.mainText`、`EmphasisText.secondaryText` 、`InfoBlock.secondaryText` 和 `TableText.items[].parameter` 用 ` ｜ ` 组合多个短字段。添加或删除绑定不得改变其余 Props、组件树和槽位尺寸。
- 静态 `label`、`unit` 和 `separator` 可以说明动态值，但必须遵守对应组件合同，不得改变数值和业务语义。有单位槽的组件可为独立数字或纯数字字符串声明静态单位，保留原值及精度；完整带单位字符串必须保留完整，不得自行拆分或补写单位。
- 格式化字符串只能绑定到接受字符串的显示 Prop；`EmphasizedData` 会自动拆分完整字符串，生成代码仍原样填写 `value="25 分钟"`。`ProgressCircle` 只绑定 `externalText`，由组件内部解析其中的数字驱动圆环；其他进度组件仍按各自属性表绑定实际进度值。`ProgressCircleSingle.value` 在没有独立数值字段时允许绑定完整的格式化百分比字符串。
- `actionId` 只能原样引用输入 `actions[].id`。模型输入中的 `actions[].description` 是映射后的推荐按钮术语，不是上游原始动作描述或业务数据；只能用于选择动作，并可作为绑定该动作的按钮内简短 `label`／`text`／`ariaLabel`。禁止把该术语或改写后的操作说明放入标题、正文、摘要、数据项或按钮外的任何可见内容；按钮已经表达操作后，不得再生成“点击／点开／打开／查看／进入……”等引导文案重复说明该操作。一个控件最多引用一个动作，同一 `actionId` 在一张卡片中最多使用一次。

### 1.1 2×2、2×4 通用组件

本文件只包含两种 Card 尺寸都可使用的组件。Runner 会根据当前任务的 `Card.size`，继续拼接对应尺寸的专属组件文档。

`SingleLineTitle`、`DoubleLineTitle`、`Badge`、`EmphasizedData`、`EmphasisText`、`SecondaryBody`、`InfoBlock`、`TableText`、`ProgressLine2`、`ProgressCircleSingle`、`ProgressCircle`、`NumericRatio`、`EventCard`、`H_BarChart`、`PillButton`

### 1.2 动态数据与显式单位

- 原始数据及其类型不变。有独立 `unit` 槽的组件（EmphasizedData、InfoBlock、NumericRatio、ProgressLine2 / ProgressLine2WithData），绑定无单位数字时，最终 JSX 使用原始数值加显式静态 `unit`，例如 `value={80} unit="%" dataIds={{value:"earphone.batteryLevel"}}`。
- 纯数字字符串如 `"80.00"` 也可配合显式单位，但必须保留字符串及其精度，不能擅自改为数字 `80`。完整带单位文本如 `"80%"`、`"4.60 公里"`、`"7小时1分"` 原样绑定，不再添加静态单位，也不拆成写死的业务数据。
- 单位依据当前输入的明确说明填写，不能根据字段名称猜测。显式 `unit=""` 关闭对裸数字的额外单位，独立 `dataIds.unit` 必须保留。单位冲突不得冒充单位换算。
- 没有单位槽的普通文本属性继续使用绑定层兼容格式化；不得给 SecondaryBody.items 等不支持单位属性的结构添加 `unit`。进度计算参数始终保留原值，百分比组件既有的取整与默认百分比语义不变。
- 动态完整文本仍由组件按原有设计拆为数字和小单位，生成代码不能把当前样例中的数字或单位拆成写死的业务数据。

## 2. 标题组件

### 2.1 SingleLineTitle

单行标题，用于卡片内容区左上角。

标题通常是根据 `userQuery` 概括的静态 UI 文案，此时只传 `title`。当地点名、设备名、事件名等输入业务字段直接承担标题角色时，才通过 `dataIds.title` 绑定其真实 ID。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `title` | `string` | 必选 | 无默认值 | 单行标题，超出可用宽度时省略 |
| `dataIds` | `{ title?: string }` | `title` 来自输入数据时必选 | 不传时无绑定 | 仅允许绑定 `title` |

```jsx
<SingleLineTitle title="手机使用时长" />
```

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `width` | `fit-content`，上限 `100%` | 按标题文本自然宽度占位；超出父槽时收缩并省略 |
| `height` | 18vp | 固定单行占高；超宽时省略，不增加高度 |

### 2.2 DoubleLineTitle

标题和次要信息组成的双层标题。

`title` 与 `secondaryInfo` 分别按内容来源判断是否绑定，不能因为使用双行标题就默认两项都是动态数据。任一项来自 `userQuery` 的静态概括时不绑定；来自当前输入 `data[]` 的业务值时绑定该项的真实 ID。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `title` | `string` | 必选 | 无默认值 | 主标题，最多一行 |
| `secondaryInfo` | `string` | 必选 | 无默认值 | 连接状态、地点等第二层信息，最多两行 |
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

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `width` | `100%` | 占满父槽可用宽度 |
| `height` | 40vp 或 58vp | 主标题 18vp、间距 4vp；次要信息一行时总高 40vp，两行时总高 58vp |
| `line-count` | 主标题 1 行；次要信息 1–2 行 | 超宽时省略；不得按单行标题的 18vp 预算分配槽位 |

> 组件与下方内容的间距由对应 Layout Pattern 决定，不计入标题自身占高。

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

#### 布局约束（非 Badge Props）

`Badge` 必须与它所修饰的标题处于同一个横向标题组，间距固定为 8px。`Badge` 不是标题组件的 prop，间距也不由 Badge 自身生成。

当一个总数用于概括下方的日程、消息或列表内容时，总数属于标题语义，必须通过标题旁的 `Badge` 表达，不再为同一个总数额外生成 `EmphasizedData`。例如“未来 7 天日程总数 + 最近一件日程”使用以下结构；`calendar.eventCount` 只绑定到 `Badge.value`，最近事件的标题和时间继续分别绑定到 `EventCard`：

```jsx
<Stack flex={0} direction="row" gap={8} align="center" width="full">
  <SingleLineTitle title="未来7天日程" />
  <Badge
    value={1}
    color="pink"
    dataIds={{ value: "calendar.eventCount" }}
  />
</Stack>

<Stack direction="column" flex={1} width="full" gap={2} justify="flex-start">
  <Stack direction="column" flex={0} width="full">
    <EventCard
      title="项目例会"
      time="14:00"
      dataIds={{
        title: "calendar.events.0.title",
        time: "calendar.events.0.dtStart",
      }}
    />
  </Stack>

  <Stack direction="column" flex={0} width="full">
    <SecondaryBody
      items={[
        {
          value: "周例会",
          dataIds: { value: "calendar.events.0.description" },
        },
      ]}
    />
  </Stack>
</Stack>
```

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `height` | 16px | 固定高度 |
| `width` | `max-content`，最大 100% | 宽度随数值自适应 |

## 3. 文本组件

### 3.1 EmphasizedData

统一的核心数值组件，用于时长、日期、温度、容量等数据。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `value` | `string \| number` | 展示单组数据，只有纯文本无数值时不使用此组件(如"正常电量"、"户外跑步") | `items` 存在时忽略 | 若绑定字段是完整格式化字符串，必须原样填写样例值，例如 `"2小时15分"`；组件会自动拆分，生成代码不得自行改写 |
| `unit` | `string` | 无单位数字或纯数字字符串可使用 | 不传时不显示 | 静态单位应显式填写；完整带单位字符串不追加单位；空字符串关闭额外单位 |
| `items` | `Array<{ key?, value, unit?, dataIds? }>` | 多个独立数据字段时使用 | 存在时覆盖顶层 `value`、`unit` | 不用于手工拆分一个完整字符串；`"2小时15分"` 仍使用顶层 `value` 和一个原始 `dataId` |
| `dataIds` | `{ value?: string, unit?: string }` | 对应属性来自输入数据时必选 | 不传时无绑定 | 只填写输入中真实存在的原始数据 ID，不得构造额外数据 ID |

#### 数值与单位拆分规则

- 判断只依据当前输入的真实 `type` 和 `value`，不得根据字段名或 description 猜测、提取单位。
- 输入为独立数字或纯数字字符串时，使用原始 `value + unit`；保留 `"80.00"` 等字符串精度。
- 输入为完整带单位字符串时，将完整样例原样放入 `value`，只绑定原始 `dataId`；如 `"320千卡"`、`"25分钟"`，不要填写 `unit`，不要手工拆成多个 `items`。
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

`unit` 与主值保持同一行。`"充电中"`、`"已连接"` 等状态不是单位，应使用独立的 `SecondaryBody`。

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `width` | `max-content`，受父槽宽度约束 | 单组或多组数值均横向排列，不主动占满父槽 |
| `value-typography` | Display_S / 38px / Bold 700 / 38px | 核心数值使用紧凑 `line-height: 1`；单行数字行盒为 38vp，单位换行时组件按内容向下扩展，不强行裁切或压缩为 38vp |
| `value-color` | `font-primary` | 核心数值字色 |
| `unit-typography` | Caption_L / 12px / Regular 400 / 18px | 单位字体规格 |
| `unit-color` | `font-secondary` | 单位字色 |
| `align-items` | `baseline` | 数值与单位的第一行文字基线对齐，而非行盒底部对齐；`ProgressLine2` 保留其紧凑单位行盒及既有基线对齐 |
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
| `dataIds` | `{ mainText?: string \| string[], secondaryText?: string \| string[] }` | 对应文本来自输入数据时必选 | 不传时无绑定 | 单字段传一个 ID；同一显示 Prop 由多个短字段组成时，传包含两个或更多 ID 的有序数组 |
| `dataValueMaps` | `{ mainText?: { true: string, false: string }, secondaryText?: { true: string, false: string } }` | 单 ID 绑定源为 Boolean 且需要显示文本时必选 | 不传时不转换 | 必须与同名的单个 `dataIds` 配对；多 ID 数组不支持 Boolean 映射 |

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

同一行文本需要跟随多个数据源独立更新时，对应 `dataIds` 可使用有序数组。JSX 预览由 `mainText` 和 `secondaryText` 中的完整样例文本保持原有视觉；后续转换层按数组顺序用固定的 ` ｜ ` 连接各数据路径。不得用 ID 替代可见文本。

```jsx
<EmphasisText mainText="多云" secondaryText="上海市 ｜ 青浦区" dataIds={{"mainText":"weather.current.condition","secondaryText":["weather.location.prefectureName","weather.location.districtName"]}} />
```

数组中每个 ID 必须真实存在、不重复，且对应 string、integer 或 number 类型的短显示字段。数组不接受 Boolean，也不与 `dataValueMaps` 组合；Boolean 状态仍使用单 ID 和同名 `dataValueMaps`。只有一个数据源时必须使用字符串 ID，不要生成单元素数组。

#### 同级 EmphasisText 的横向组合

`EmphasisText` 自身始终保持“主文本在上、次文本在下”的纵向结构；多个 `EmphasisText` 之间的排列由外层 `Stack` 决定。恰好有两个同级短数据／状态，并且两者自然宽度加 8vp 间距不超过 120vp 时，优先横向排列，避免纵排占用双倍高度。父 `Stack` 必须显式写 `direction="row"`，并使用 `justify="space-between"` 分配剩余横向空间；`minWidth={0}` 由 runtime 默认提供，无需生成：

```jsx
<Stack direction="row" width={120} gap={8} align="center" justify="space-between">
  <EmphasisText
    mainText="6200"
    secondaryText="今日步数"
    dataIds={{ mainText: "healthSport.dailySteps" }}
  />
  <EmphasisText
    mainText="良好"
    secondaryText="昨晚睡眠"
    dataIds={{ mainText: "healthSport.sleepStatus" }}
  />
</Stack>
```

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `width` | `max-content`，受父槽宽度约束 | 组件不主动占满父槽 |
| `height` | 38vp | 主文本 20vp、主次文本间距 2vp、次文本 16vp |

#### 浏览器重叠时的紧凑替换规则

当浏览器校验通过 `browser-semantic-overlap` 明确确认 `EmphasizedData` 与相邻业务组件重叠时，必须先复核该字段的业务语义。若内容属于短文本、状态或完整格式化字符串，并且能够从现有用户需求或字段语义提供真实的 `secondaryText`，优先尝试改用 `EmphasisText`，随后重新执行语义与浏览器布局校验。

替换时必须完整保留可见内容和动态绑定：原 `value` 迁移到 `mainText`，原 `dataIds.value` 迁移到 `dataIds.mainText`；不得拆分格式化字符串、删除数据、把动态值改为静态文本或虚构 `secondaryText`。纯数值与单位、进度关系，以及根据组件选择规则应使用 `EventCard` 的日程事件，不得仅为解决重叠而替换。

```jsx
<EmphasisText
  mainText="15分钟"
  secondaryText="距离开始"
  dataIds={{ mainText: "countdown.remainingText" }}
/>
```

### 3.3 SecondaryBody

文档中名称为“次要文本”，用于卡片里的辅助正文信息。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `items` | `Array<{ key?, label?, value, dataIds? }>` | 必选，至少一项 | 无默认值 | 单个字段也使用只含一个 item 的数组；每行最多显示两项，第三项起进入下一行；`value` 原样使用输入提供的完整值，并通过项内 `dataIds.value` 独立绑定；`label` 保持静态；不支持 `unit` |
| `separator` | `string` | 仅 items 模式可选 | `" ｜ "` | 只分隔同一行内的两个字段；新一行开头不显示分隔符 |

`SecondaryBody` 只使用 `items`，不使用顶层 `body` 或顶层 `dataIds`。单个完整字段也必须写成一个 item，并通过该 item 的 `dataIds.value` 绑定。纯数字、百分比、时间和孤立时语义不完整的等级值必须有静态 `label`；自描述状态可以省略。`items` 不设置固定数量上限，每个行组最多两项。runtime 以 14px 字号测量字段与分隔符的实际宽度：相邻两项放得下时合组，否则整项进入下一组；单个字段超宽时允许自身换行。超过两项、出现多个行组或单字段超宽时，整个组件统一使用 12px / 16px 行高，否则使用 14px / 19px 行高。相邻行组间距 2vp，行组开头不显示分隔符。内容更新或容器宽度变化后重新测量，仍需确保实际内容不超过卡片高度。

语义相近、需要成对理解的字段应相邻排列，并优先合并显示在同一行，例如“入睡时间 + 醒来时间”“开始时间 + 结束时间”“最高温 + 最低温”。这些字段仍分别保留为独立 item 并绑定各自的 `dataId`，不得为了合并显示而拼成一个动态字符串。

`items` 不支持 `unit`。`value` 必须原样使用输入提供的完整展示值，例如 `"29.0 ℃"`、`"40分"`、`"260 千卡"`；不得拆分、补写或根据 description 推断单位。若输入只提供不含单位的数字，组件只展示该数字。

```jsx
<SecondaryBody
  items={[
    {
      label: "用时",
      value: "40分",
      dataIds: { value: "healthSport.exerciseDurationText" },
    },
  ]}
/>
```

```jsx
<SecondaryBody
  items={[
    {
      value: "多云",
      dataIds: { value: "weather.condition" },
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

三个字段会按“两项 + 一项”换行，第二行前不显示分隔符：

```jsx
<SecondaryBody
  items={[
    {
      label: "入睡",
      value: "23:15",
      dataIds: { value: "healthSport.sleepStartTime" },
    },
    {
      label: "醒来",
      value: "07:30",
      dataIds: { value: "healthSport.sleepEndTime" },
    },
    {
      label: "总时长",
      value: "7小时1分",
      dataIds: { value: "healthSport.nightSleepDurationText" },
    },
  ]}
/>
```

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `width` | `100%`，最大为父槽宽度 | 分段内容按父槽宽度换行 |
| `height` | 单行 19vp；多行按 `16vp × 实际行数 + 2vp × 行组间数` | 字段完整性优先；分组与字号按实际可用宽度自适应 |

结构化精简可以删除静态冗余，也可以按组件合同调整动态样例值的显示结构和格式，但不得改变数值或业务语义。动态标签和值必须分段表达，并继续绑定原始 `dataId`：

- 输入值为 `"优"` 时，使用 items 模式的静态 `label="空气"` 和动态 `value="优"`，不得把动态值改成 `"空气优"`。
- 输入值为数字 `86` 时，使用 `EmphasizedData value={86} unit="分"`，不得把动态值改成字符串 `"86分"`。
- 入睡时间、起床时间或最高温、最低温来自不同数据字段时，分别绑定到独立组件或同一组件的独立 item；只有输入本身提供完整展示字段时，才能原样绑定到一个 `body` Prop。
- 裸数字、百分比和“优／正常／高”等孤立状态通常需要静态语义 Label；温度文本（如 `29°C`）和时刻文本（如 `07:30`）自身已带明确类型信息，不强制重复添加“温度”“时间”等 Label。

### 3.6 InfoBlock

高度固定为 64vp、宽度填满父槽的紧凑信息组件，由主文本、副文本和背板组成，并可按需增加右侧尾部视觉。存在明确的图形识别或 0–100 占比／进度语义时，尾部视觉在 Icon 与 ProgressCircle 中二选一；没有合适视觉或需要为文本保留完整宽度时可以省略 `visual`。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `primaryText` | `string \| number` | 必选 | 无默认值 | 左侧第一行核心信息；数值和文本均可，单行省略 |
| `secondaryText` | `string \| number` | 必选 | 无默认值 | 左侧第二行解释信息或次要信息，单行省略；可由一个数据字段提供，也可组合多个短字段 |
| `unit` | `string` | 可选，静态 UI 文案 | 不传时不显示 | 主文本为数值时与其同行显示；不允许绑定数据 ID |
| `visual` | `InfoBlockIconVisual \| InfoBlockProgressVisual` | 可选；提供时二选一 | 不传时不显示尾部视觉，文本区域使用剩余宽度 | 右侧 Icon 或 ProgressCircle；不得同时提供两种视觉 |
| `dataIds` | `{ primaryText?: string, secondaryText?: string \| string[] }` | 对应文本来自输入数据时分别绑定 | 不传时无绑定 | `primaryText` 绑定一个 ID；`secondaryText` 绑定一个 ID，或按显示顺序绑定两个及以上 ID；`unit` 与 `visual` 不绑定 |

省略 `visual` 时，组件只显示主、副文本，不生成空视觉占位。提供 `visual` 时只接受两种结构：`{ type: "icon", icon, color?: "native" }` 用于图形识别；`{ type: "progressCircle", icon }` 用于 0–100 占比／进度，圆环直接解析并限制 `primaryText`。两者的 `icon` 均必选且必须来自语义匹配的 `assetCandidates`；单色 Icon 与按钮一样自动跟随 Card appearance，浅色背景使用对应主题色，深色渐变背景使用白色。仅保留原生多色外观时写 `color: "native"`。

`secondaryText` 需要由多个短字段共同组成时，`dataIds.secondaryText` 使用有序数组，转换层会用固定的 ` ｜ ` 连接各数据路径，并保持每个字段独立响应更新。数组至少包含两个真实、非重复的 string、integer 或 number 数据 ID；只有一个字段时仍使用字符串 ID。

```jsx
<InfoBlock
  primaryText="多云"
  secondaryText="上海市 ｜ 青浦区"
  dataIds={{
    primaryText: "weather.current.condition",
    secondaryText: [
      "weather.location.prefectureName",
      "weather.location.districtName",
    ],
  }}
/>
```

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `size` | 父槽宽度 × 64vp | 宽度填满 Layout Pattern 分配的父槽，高度固定为 64vp；2×2“双信息块”中为 136 × 64vp，2×4 固定槽中为 144 × 64vp |
| `overflow` | 单行省略 | 主文本和副文本超宽时不换行，不增加组件高度 |

#### 合法 JSX 示例与布局约束

- `InfoBlock` 高度始终保持 64vp，宽度使用父槽的完整可用宽度；外层 `Stack` 或 `Grid` 必须按当前尺寸的 Layout Pattern 提供明确槽宽。2×2“双信息块”的 136vp 槽中组件宽为 136vp；2×4“四槽宫格”与“左内容右侧双槽”的固定槽中组件宽为 144vp。不得向 `InfoBlock` 传入 `width` Prop 覆盖父槽尺寸。
- 在 2×2 卡片中，`InfoBlock × 2` 使用“双信息块”：`Card` 设置 `gap={8}`，每个 `InfoBlock` 分别放入一个 `<Stack direction="column" flex={0} height={64}>`。

```jsx
<Card direction="column" size="2x2" appearance="orb-purple" gap={8}>
  <Stack direction="column" flex={0} height={64}>
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
  <Stack direction="column" flex={0} height={64}>
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

```jsx
<Card direction="column" size="2x2" appearance="solid-blue" gap={8}>
  <Stack direction="column" flex={0} height={64}>
    <InfoBlock
      primaryText="成都 29℃"
      secondaryText="多云"
      visual={{
        type: "icon",
        icon: "local_fill.svg"
      }}
      dataIds={{
        primaryText: "weather1.current.temperatureC",
        secondaryText: "weather1.current.condition"
      }} />
  </Stack>
  <Stack direction="column" flex={0} height={64}>
    <InfoBlock
      primaryText="上海 29℃"
      secondaryText="多云"
      visual={{
        type: "icon",
        icon: "local_fill.svg"
      }}
      dataIds={{
        primaryText: "weather2.current.temperatureC",
        secondaryText: "weather2.current.condition"
      }} />
  </Stack>
</Card>
```

ProgressCircle 分支仍使用同一槽位结构。`unit` 和静态说明不绑定；输入提供的主、副文本分别通过同名 `dataIds` 绑定：

```jsx
<Stack direction="column" flex={0} height={64}>
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
| `items[].dataIds` | `{ parameter?: string \| string[] }` | `parameter` 来自输入数据时必选 | 不传时无绑定 | 单字段传一个 ID；同一参数需要组合两个或更多短字段时传有序 ID 数组；只允许绑定 `parameter` |
| `items[].dataValueMaps` | `{ parameter?: { true: string, false: string } }` | 单 ID 绑定源为 Boolean 且需要显示文本时必选 | 不传时不转换 | 必须与同一 item 的单个 `dataIds.parameter` 配对；多 ID 数组不支持 Boolean 映射 |

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

同一行参数需要跟随多个短数据源独立更新时，使用有序 ID 数组；转换后按数组顺序使用固定的 ` ｜ ` 连接。数组至少包含两个真实、不重复的 string、integer 或 number 数据 ID，不接受 Boolean，也不能与 `dataValueMaps` 同时使用：

```jsx
<TableText
  items={[
    {
      label: "时间地点",
      parameter: "09:00 ｜ C5会议室",
      dataIds: {
        parameter: [
          "calendar.events.0.dtStart",
          "calendar.events.0.eventLocation",
        ],
      },
    },
    {
      label: "提醒",
      parameter: "已开启",
      dataIds: { parameter: "calendar.reminder.enabled" },
      dataValueMaps: {
        parameter: {
          true: "已开启",
          false: "未开启",
        },
      },
    },
  ]}
/>
```

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `width` | `100%` | 每组及整个组件占满父容器分配的宽度 |
| `height` | 填满父槽；内容自然高度为 `16 × N + 2 × (N − 1)vp` | `N` 为 items 数量；每项固定 16vp。两项时顶部排列、间距 2vp；三项及以上时均分父槽剩余高度，相邻项间距最小 2vp。父槽不足时报告溢出，不压缩行高 |
| `row-overflow` | 单行省略 | 每项不换行，不增加单项高度 |

#### 布局约束

- 0827 规范示例用于 2×2 Card 的“标题单内容”，外层布局负责将组件放入内容区并分配宽度。
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
  value="60%"
  mode="light"
  dataIds={{
    value: "task.progressPercentText",
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
| `mode` | `"light" \| "dark"` | 生成卡片必选 | `"light"` | 浅色 solid／soft 背景使用 light：主题深色 20% Track + 100% Bar；深色 orb／gradient 背景使用 dark：白色 20% Track + 白色 Bar |
| `barColor` | `string` | 仅实现层覆盖 | 浅色主题深色；深色白色 | 只用于设计规范明确要求的特殊覆盖；新生成不得用它自由改变 Bar 色，也不得填写硬编码颜色 |
| `dataIds` | `{ value?: string, unit?: string }` | 可见值来自输入数据时绑定 `value`；生成代码不得绑定 `currentValue`／`totalValue` | 不传时无绑定 | `value`／`unit` 的绑定规则与 `EmphasizedData` 相同；items 模式改用项内 `dataIds` |

`currentValue` 和 `totalValue` 只使用数值字面量计算 Bar 的初始比例，不放入 `dataIds`。没有传 `unit` 时，也不要生成 `dataIds.unit`。

```jsx
<ProgressLine2
  currentValue={43.75}
  totalValue={100}
  value={4.5}
  unit="GB可用"
  mode="light"
  dataIds={{
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
/>
```

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `width` | `100%` | 撑满所在模块 |
| `min-width` | `0` | 避免处于 flex 内容区时按内容收缩 |
| `height` | 56vp | 数值区 38vp、纵向间距 6vp、进度条 8vp、底部留白 4vp |

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

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `width` | 100% | 撑满父布局分配的模块宽度；适配 2×2 与 2×4 Card |
| `height` | `30 × N + 11 × (N − 1)vp` | `N` 为 items 数量；每项占高 30vp，相邻项间距 11vp |
| `row-overflow` | 单行省略 | 每项标签和值不换行，不增加单项高度 |

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
| `value` | `number \| string` | 生成 Card 必选；数字范围 0–100，字符串必须是完整格式化百分比 | 无效值会回退为 0；有效值会限制到 0–100 | 模型必须显式传入的圆环进度数据源，对应设计字段 `percent`；它不是可省略的内部属性。字符串只接受 `"68%"`、`"43.75%"` 等“数字 + `%`”格式 |
| `icon` | `string` | 必选 | 无默认值 | 圆环中心功能 Icon；使用当前输入中语义匹配的候选资源 `src` |
| `displayValue` | `string` | 可选；仅当可见值与圆环百分比来自不同字段时使用 | 省略时由 `value` 自动生成百分比文本；传入时原样显示 | 独立的绝对展示值或已格式化展示字段，例如圆环表达已用比例、右侧显示 `"4.5GB"` |
| `label` | `string` | 必选 | 无默认值 | 右侧文本组顶部的语义标签 |
| `secondaryLabel` | `string` | 可选 | 不传时使用两行文本组 | 存在时自动切换为 Label + Value + Secondary Label 三行规格，不使用 `lines` prop |
| `ariaLabel` | `string` | 生成 Card 必选 | 省略时回退为 `label + 最终显示值` | 完整描述占比、绝对值和状态 |
| `appearance` | `"card"` | 生成 Card 必选 | 默认普通 catalog 模式 | 对 2×2 与 2×4 Card 均启用卡片专属 Icon、精度和颜色处理 |
| `size` | `"compact"` | 仅在 2×4 Layout Pattern 的 Sub-118／Sub-140 子布局中必选；其他布局省略 | 省略时使用 52 × 52vp 默认圆环；`"compact"` 使用 44 × 44vp 圆环 | compact 规格与 `ProgressCircle size="sm"` 的圆环直径一致，并收紧右侧文本的纵向行盒 |
| `trackColor` | `string` | 仅实现层覆盖 | 使用组件默认值 | `appearance="card"` 时会被卡片模式覆盖 |
| `barColor` | `string` | 仅实现层覆盖 | 设计规范绿色 | `appearance="card"` 时会被卡片模式覆盖 |
| `dataIds` | `{ value?: string, displayValue?: string, label?: string, secondaryLabel?: string }` | 对应字段来自输入数据时必选 | 不传时无绑定 | `value` 必须绑定实际进度数据；其余可见文本按输入字段分别绑定 |

`ProgressCircleSingle` 与 `ProgressCircle` 的生成合同不同：`ProgressCircle` 使用唯一的 `externalText` 同时驱动圆环和外部百分比文本；`ProgressCircleSingle` 必须显式提供 `value` 驱动圆环，并允许用可选的 `displayValue` 显示另一项绝对值。不得因为 `ProgressCircle.value` 属于 runtime 兼容属性，就省略 `ProgressCircleSingle.value`。

`value` 优先绑定 number／integer 类型的原始百分比。当输入没有独立数值字段、只提供语义明确的完整格式化百分比字符串时，也可以直接绑定该字符串；runtime 会使用其中的数字驱动圆环，并原样显示百分比文本。该兼容方式只适用于完整百分比字符串，不接受普通文本或混合文案。

动态数值 `value` 省略 `displayValue` 时会直接显示实时数值和 `%`。当圆环百分比和可见百分比来自同一个数据 ID 时，只写 `value` 与 `dataIds.value`，禁止再把同一 ID 重复绑定到 `displayValue`；runtime 与后续转换层会将历史 JSX 中这种重复绑定归一化为 `value + %`。只有需要显示另一项独立数据，例如“已用 43.75%”的圆环旁显示“4.5GB 可用”，才同时提供并分别绑定 `value` 与 `displayValue`。

当组件位于 2×4 Layout Pattern 的 Sub-118 或 Sub-140 子布局时，必须显式传入 `size="compact"`。compact 只改变圆环直径和右侧文本行盒，不改变字段语义、数据绑定、字体大小、字重、颜色、水平间距或中心 Icon 尺寸；2×2 和不属于子布局的场景继续省略 `size`，使用默认规格。

```jsx
<ProgressCircleSingle
  value="68%"
  icon="battery_leaf_fill.svg"
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

2×4 子布局中的 compact 示例：

```jsx
<ProgressCircleSingle
  value="68%"
  icon="battery_leaf_fill.svg"
  label="剩余电量"
  secondaryLabel="充电中"
  ariaLabel="剩余电量68%，充电中"
  appearance="card"
  size="compact"
  dataIds={{
    value: "phoneBattery.batterySOCText",
    secondaryLabel: "phoneBattery.chargingStatusDesc",
  }}
/>
```

```jsx
<ProgressCircleSingle
  value={43.75}
  icon="externaldrive_fill.svg"
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
  icon="battery_leaf_fill.svg"
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

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `width` | `max-content` | 自然宽度为圆环、8vp 间距与右侧文本组宽度之和；不会自动撑满父槽 |
| `height-default` | 52vp | 省略 `size` 时，无论两行或三行文本均至少由 52vp 圆环决定高度 |
| `height-compact` | 两行 44vp；三行 46vp | `size="compact"` 仅用于 2×4 的 Sub-118／Sub-140 子布局；三行文本比 44vp 圆环高 2vp |

### 4.5 ProgressCircle

同时展示两个或四个占比值时使用的圆环组件，包含圆环外部数值。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `icon` | `string` | 必选 | 无默认值 | 圆环中心功能 Icon；使用当前输入中语义匹配的候选资源 `src` |
| `externalText` | `string \| number` | 生成 Card 必选；必须是纯数字或数字百分比 | 裸数字自动显示为 `${Math.trunc(value)}%`；已有 `%`／`％` 时不重复追加；内部解析为 0–100 数值并驱动圆环 | 直接使用输入提供的真实值，例如 `68`、`"68"` 或 `"68%"`；不要为了补单位改写绑定样例，也不要另外编写或绑定 `value` |
| `size` | `"sm"` | 固定使用 `sm` | `"sm"` | 生成代码只使用 44 × 44vp 小号圆环 |
| `ariaLabel` | `string` | 生成 Card 必选 | 省略时回退为最终显示的 `externalText` | 描述对象和百分比 |
| `appearance` | `"card"` | 生成 Card 必选 | 默认普通 catalog 模式 | 对 2×2 与 2×4 Card 均启用卡片 Icon mask 与精度规则 |
| `trackColor` | `string` | 由明暗模式决定 | 黑色 10% | 不作为自由视觉属性使用 |
| `barColor` | `string` | 设计规范固定绿色 | 使用组件默认值 | 不作为自由视觉属性使用 |
| `dataIds` | `{ externalText?: string }` | `externalText` 来自输入数据时必选 | 不传时无绑定 | 只绑定一次原始比例字段；不得添加 `dataIds.value`。integer、number 与 string 类型的比例字段都绑定到 `externalText` |

`externalText` 是生成 Card 时唯一的比例数据源。组件内部会确定性地将 `68`、`"68"`、`"68%"` 或 `"68％"` 解析为数值 `68` 来驱动圆环；当绑定源是 integer／number 或不带单位的纯数字字符串时，可见文本自动追加静态 `%`，已经包含 `%`／`％` 的字符串不会重复追加。模型必须保留输入提供的真实样例值，不得为了显示单位把 `68` 改写成 `"68%"`，也不得为同一业务比例寻找或构造第二个 `value` dataId。

```jsx
<ProgressCircle
  icon="battery_leaf_fill.svg"
  externalText={68}
  size="sm"
  ariaLabel="手机电量68%"
  appearance="card"
  dataIds={{ externalText: "phone.batteryPercent" }}
/>
```

同时展示两个同级占比值时，两个 `ProgressCircle` 必须放入占满完整可用宽度的横向父 `Stack`。父容器使用 `direction="row"` 横排、`align="center"` 控制垂直居中，并使用 `justify="space-between"` 分配剩余横向空间：

```jsx
<Stack direction="row" width={120} gap={8} align="center" justify="space-between">
  <ProgressCircle
    ...
  />
  <ProgressCircle
    ...
  />
</Stack>
```

#### 布局约束（非 ProgressCircle Props）

同时展示多个占比值时，每个 `ProgressCircle` 放入当前尺寸 Layout Pattern 分配的独立槽位并水平、垂直居中。数量、网格结构和操作区由当前尺寸的布局文档决定；组件章节不重复声明另一尺寸的布局。

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `width` | 至少 44vp | 由 44vp 圆环或更宽的外部数值文本决定 |
| `height` | 60vp | 44vp 圆环、2vp 间距、14vp 外部数值文本 |

> `density="compact-4"` 仅由 runtime 暂时兼容旧 JSX，新生成契约已禁止该属性；四值场景统一使用 `size="sm"`。

### 4.6 NumericRatio

文档中名称为“数值占比”。同时展示三个占比值时，分别使用三个 `NumericRatio`，并通过外层标准 `Stack` 决定横向或纵向排列；不使用额外的组合组件；不要拆分到两个`Stack`中使用。不得在 `value` 中增加“耳机盒”“左耳”等纯文本 Label；对象语义必须由对应 Icon 表达。若 Icon 无法充分区分对象，应改选带文本 Label 槽的组件，而不是扩展 `NumericRatio` 的内容结构。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `icon` | `string` | 必选 | 无默认值 | 对象 Icon；使用当前输入中语义匹配的候选资源 `src` |
| `value` | `string \| number` | 必选 | 数字值截去小数部分并默认补 `%`，字符串原样显示 | 动态原始百分比使用数字，例如 `43.75` 可见为 `43%`；已有完整展示文本时可使用 `"43%"` |
| `unit` | `string` | 裸数字的新生成 JSX 显式填写 | 旧 JSX 数字值兼容默认 `%`，字符串默认空 | 静态单位；完整带单位字符串不重复追加；传空字符串关闭默认百分号 |
| `appearance` | `"card"` | 生成 Card 必选 | 默认 img 模式 | 启用卡片 Icon mask |
| `dataIds` | `{ value?: string }` | `value` 来自输入数据时必选 | 不传时无绑定 | 仅允许绑定 `value`；Icon 和静态单位不得绑定 |

#### 合法 JSX 与布局约束

三个占比值纵向排列时，外层 `Stack` 显式使用 `direction="column"` 和 `gap={4}`：

```jsx
<Stack direction="column" gap={4} align="flex-start">
  <NumericRatio
    icon="earphone_case_16644.svg"
    value={80}
    unit="%"
    appearance="card"
    dataIds={{ value: "earbuds.caseBatteryPercent" }}
  />
  <NumericRatio
    icon="l_circle_fill.svg"
    value={76}
    unit="%"
    appearance="card"
    dataIds={{ value: "earbuds.leftBatteryPercent" }}
  />
  <NumericRatio
    icon="r_circle_fill.svg"
    value={74}
    unit="%"
    appearance="card"
    dataIds={{ value: "earbuds.rightBatteryPercent" }}
  />
</Stack>
```

三个占比值横向排列时，外层 `Stack` 显式使用 `direction="row"`；只有父槽宽度能够容纳三个组件的自然宽度与两处间距时才使用该方式：

```jsx
<Stack direction="row" width="full" gap={8} align="center" justify="space-between">
  <NumericRatio
    icon="earphone_case_16644.svg"
    value={80}
    unit="%"
    appearance="card"
    dataIds={{ value: "earbuds.caseBatteryPercent" }}
  />
  <NumericRatio
    icon="l_circle_fill.svg"
    value={76}
    unit="%"
    appearance="card"
    dataIds={{ value: "earbuds.leftBatteryPercent" }}
  />
  <NumericRatio
    icon="r_circle_fill.svg"
    value={74}
    unit="%"
    appearance="card"
    dataIds={{ value: "earbuds.rightBatteryPercent" }}
  />
</Stack>
```

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `height` | 16vp | 单项固定占高；三个组件纵排并使用 4vp 间距时共占 56vp |
| `width` | `max-content` | Icon、4vp 间距和数值共同决定自然宽度；横排时由外层 `Stack` 判断并分配可用宽度 |

### 4.7 EventCard

时间线式日程组件，由圆圈、装饰线、日程标题、时间和可选地点组成。组件宽度由父布局槽位决定：2×2 中最大为 116vp；2×4 中取消该上限并使用父槽提供的完整可用宽度。

`EventCard.title` 表示某一条具体事件的标题，例如“产品发布会”或“医院复查”；它不是整张卡片或内容区的标题，不能自动替代 `SingleLineTitle`。当所选 Layout Type 包含标题区时，必须在该标题区另外生成 `SingleLineTitle`，再把具体事件放入下方内容区。只有所选 Layout Type 明确允许无标题，并且省略后仍不会丢失卡片对象、时间范围或必要上下文时，才可以只显示 `EventCard`。多条日程需要保留全局标题时，应选择能够容纳标题和多条事件内容区的布局，不得为了使用无标题布局删除标题或任一事件。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `title` | `string` | 必选 | 无默认值 | 从用户query中提取日程标题，最多两行 |
| `time` | `string` | 必选 | 无默认值 | 时间或时间范围 |
| `location` | `string` | 可选 | 不传时不渲染地点 | 地点或会议室 |
| `density` | `"compact"` | 仅 2×4 多条日程且普通高度无法闭合时使用 | 不传时使用普通模式 | 紧凑模式标题固定一行，时间与地点合并到下一行，整体高度固定为 32vp |
| `dataIds` | `{ title?: string, time?: string \| [string, string], location?: string }` | 对应字段来自输入数据时必选 | 不传时无绑定 | `title`、`location` 各绑定一个 ID；`time` 绑定一个时间 ID，或按 `[dtStartId, dtEndId]` 绑定开始与结束两个 ID，不要绑定`entityId` |

`EventCard` 的 `title`、`location` 和只绑定一个 ID 的 `time` 若在 `userQuery` 中有明确的当前值，而同义数据字段的 `value` 只是不同的预览样例，JSX 显示 Prop 使用 `userQuery` 中的值，`dataIds` 仍绑定该字段原有 ID。例如查询明确说“产品发布会”，而 `calendar.events.0.title.value` 是“项目例会”时，应写 `title="产品发布会"` 并继续绑定 `calendar.events.0.title`。后续实时数据仍通过该 ID 对应的动态数据源更新。`time` 绑定开始和结束两个 ID 时，仍按二者的样例值组合预览，不把一段查询文本猜测拆回两个字段。

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

2×4 中需要连续展示多条日程、普通 `EventCard` 的总高度无法闭合时，使用紧凑模式。它仍保留每条事件的标题、时间、地点和原始绑定；多条紧凑事件优先放入 140vp 连续内容区，不放进 118vp 背板子槽，也不得为了缩小高度改用无法承载这些绑定的静态标签：

```jsx
<EventCard
  density="compact"
  title="用户卡片需求评审会"
  time="09:00"
  location="练秋湖C5会议室"
  dataIds={{
    title: "calendar.events.0.title",
    time: "calendar.events.0.dtStart",
    location: "calendar.events.0.eventLocation",
  }}
/>
```

EventCard 不提供业务 `width` Prop，也不根据绑定后的文本长度临时改变布局。父级布局负责按当前尺寸的 Layout Pattern 分配宽度：2×2 中组件在父槽位内使用 `width: 100%` 且最大不超过 116vp；2×4 中不设置最大宽度，应使用父槽提供的完整可用宽度，不得在右侧仍有可用空间时保留无意义空白并提前换行。

2×4 中优先让 `EventCard` 独占所选“标题单内容”子布局的内容槽，并使用完整可用宽度。辅助 `SecondaryBody` 不应作为同一横排兄弟挤压日程正文；确需保留时，应放入独立的纵向信息槽，并重新检查标题、时间和地点所需高度。

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `width` | `100%` | 占满父布局为它分配的槽位宽度 |
| `max-width` | 2×2 为 116vp；2×4 为 `none` | 2×4 使用父槽完整可用宽度，避免右侧有空间时标题仍提前换行 |
| `min-width` | `0` | 允许缩小到父槽位宽度，例如 2×2“标题正文角标按钮”的 92vp 左下区域 |
| `height` | 普通模式 34–68vp；紧凑模式 32vp | 普通模式标题一行且无地点为 34vp、有地点为 50vp；标题两行时分别为 52vp 或 68vp；紧凑模式固定为标题 16vp + 间距 2vp + 时间地点 14vp，时间与地点在同一行显示 |
| `title-lines` | 1–2 行 | 标题换行会增加 18vp 高度；时间和地点各固定占 16vp |

## 5. 按钮组件

### 通用布局约束（适用于 2×2 与 2×4）

- `PillButton` 及当前尺寸允许的专用操作按钮用作卡片操作入口时，按钮槽或同组按钮容器必须与其所属内容区的底部对齐；存在多个按钮时，整个按钮组贴底排列。各尺寸专用按钮的规则见对应尺寸的组件文档。
- 横向 `Stack` 中只有按钮需要贴底时，将按钮放进与内容区等高的包装 `Stack`，由该包装层使用 `justify="flex-end"`；同一行所有直接子项都需要底部对齐时，父 `Stack` 使用 `align="flex-end"`。
- 纵向 `Stack` 中使用 `justify="flex-end"` 将按钮槽或按钮组推到所属内容区底部。
- 不得使用 `align="center"`、`justify="center"` 或等量上下留白使按钮悬空；按钮上方可以保留自适应剩余空间，按钮下方不得保留非规范间距。

### 5.1 PillButton

胶囊按钮，由必选文本、可选 Icon 和按钮容器组成，可用于 2×2 与 2×4 Card。2×2 中放入 Layout Pattern 明确提供的主要操作槽；2×4 中用于某个语义组／操作区域恰好一个 Action 的情况，并限制在半卡宽父区内。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `label` | `string` | 必选 | 无默认值 | 按钮文本，清晰传达action意图 |
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
  icon="icon_clear.svg"
  appearance="card"
  actionId="memory.cleanNow"
/>
```

#### 布局约束（非 PillButton Props）

- runtime 默认几何规格为 136 × 36vp、圆角 30vp；组件自身不设置定位。2×4“左右双区”的 `surface="backplate"` 内使用 118 × 36vp、圆角 18vp，作为普通布局流模块；其他尺寸的旧背板上下文保持 120 × 36vp。
- 2×2 中由对应 Layout Pattern 提供 136 × 36vp 操作槽。
- 2×4 的单 Action 优先进入所属子布局的 `PillButton`；子布局无法安全容纳时，改用“左内容右侧双槽”的右下固定槽和 `CardButton`。按钮不得横跨 296vp 安全内容区。
- 2×4“左右双区”的 Sub-118 按钮槽为 118 × 36vp，进入居中的 118 × 112vp 内部安全区，使用普通布局流及 6vp 纵向间距，不使用绝对定位。“左内容右侧双槽”的 Sub-140 内容区内部 `PillButton` 保持 136 × 36vp 并左对齐；不得向组件传入未知尺寸 Props。
- 如果卡片其他组件已经使用相同 Icon，按钮内省略重复 Icon，只保留文本标签。

2×4 Sub-140“标题内容单按钮”示例：

```jsx
<Stack direction="column" width={140} height={136} gap={8}>
  <Stack direction="column" flex={0} width={140}>{/* 局部标题 */}</Stack>
  <Stack direction="column" flex={1} width={140}>{/* 与 Action 对应的主内容 */}</Stack>
  <Stack direction="column" flex={0} width={136} height={36}>
    <PillButton
      label="一键清理"
      appearance="card"
      actionId="memory.cleanNow"
    />
  </Stack>
</Stack>
```

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `size` | 默认 136 × 36vp；2×4“左右双区”背板内 118 × 36vp | 背板内通过 runtime 上下文样式自动切换；不新增尺寸 Prop，也不拉伸为整卡宽度 |
