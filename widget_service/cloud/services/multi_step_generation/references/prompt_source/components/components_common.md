---
name: phone-widget-components-common
description: 规定两种尺寸共用单组件的选择条件、真实 Props、绑定能力、容量和单组件示例；不负责组件组合或父布局路由。
---

# 组件选择

先按信息语义和字段结构保留可行的组件候选，再结合组件组合与布局槽位确定最终组件，不提前锁定唯一选择。一个组件只承担其定义的内容结构；不要为了使用某个组件而补造字段。

以下示例中的数据 ID、文案与资源名只说明写法。实际生成时必须改为当前输入中的真实值；示例资源只有在当前 `assetCandidates[].src` 存在同名候选时才能使用。

每个组件的“组件属性”表是该组件可生成的完整 API。只能使用表中列出的 Prop，不能借用其他组件的 Prop，也不能根据含义补造属性；“可绑定字段”只表示 `dataIds` 中允许出现的 key。当前组件的合法 Prop 无法完整表达所需信息时，改选其他组件或组件组合。

## 1. 组件总表

| 类型 | 名称 | 内容结构 | 适用场景 | 容量与约束 |
|---|---|---|---|---|
| 标题 | `SingleLineTitle` | 单层标题 | 简短概括一个内容区 | 1 个短标题；单行标题位 |
| 标题 | `DoubleLineTitle` | 标题 + 次级信息 | 对象名称还需同时表达状态或地点 | 2 个相关文本；双层标题位 |
| 标题附属 | `Badge` | 标题关联数量 | 在标题旁呈现该标题所概括内容的总数、数量或未读数 | 1 个短数值；只能进入“标题与数量”组合 |
| 核心信息 | `EmphasizedData` | 核心数值 + 可选单位 | 突出数值或完整格式化数值 | 1 个核心数值语义；视觉权重高 |
| 核心信息 | `EmphasisText` | 主文本 + 可选次文本 | 突出文本结论或状态 | 1–2 个相关文本；视觉权重高 |
| 补充信息 | `SecondaryBody` | 多个短说明项 | 补充核心信息的状态或说明 | 至少 2 个短字段；与核心组件组合 |
| 紧凑信息 | `InfoBlock` | 主信息 + 辅助信息 + 可选尾部视觉 | 在固定槽内表达一组完整信息 | 1 组主辅信息；固定信息槽 |
| 多项属性 | `TableText` | 多行标签—参数 | 紧凑呈现同一主题的多项属性 | 至少 2 项；纵向高密度排列 |
| 进度 | `ProgressLine2` | 核心数值 + 线性进度 | 表达当前值相对明确目标或总量的进度 | 1 组进度关系；连续内容区 |
| 比较 | `H_BarChart` | 多行标签—数值—柱条 | 比较多个对象的同一指标 | 2–3 个同维度值；连续内容区 |
| 占比 | `ProgressCircleSingle` | 单环 + 右侧文本 | 表达单个对象的占比或余量状态 | 1 个占比，可带标签、展示值和状态 |
| 占比 | `ProgressCircle` | 小圆环 + 外部数值 | 表达两个或四个同级对象的真实占比或有界进度 | 每个实例 1 个 0–100 比例；使用 2 或 4 个实例；不表达天数、数量或时间 |
| 占比 | `NumericRatioStack` | 3 组 Icon + 数值 | 表达三个同级对象的占比 | 恰好 3 项；作为一个高密度组件使用 |
| 日程 | `EventCard` | 时间线事件项 | 表达按时间排列的日程或会议 | 1–2 个事件；占用连续内容区 |
| 操作 | `PillButton` | 操作文案 + 可选 Icon | 内容区内的单个 Action | 1 个 Action；进入内容区变体的操作位 |

### 1.1 关键选择边界

1. **标题**：信息分区缺少清晰对象或主题时保留标题；业务组件已经完整表达对象且布局允许无标题时可以省略。一个标题槽使用一个标题单元：单独的 `SingleLineTitle`／`DoubleLineTitle`，或“标题与数量”组件组合。
2. **核心与明细**：存在明确核心时，用一个强调、进度或事件组件表达核心，其余相关字段用一个多字段组件补充；没有真实主次时保持并列，不把某个普通数字强行放大为核心。
3. **多项属性**：纵向紧凑的标签—参数使用 `TableText`；需要比较同一量纲的大小时使用 `H_BarChart`。尺寸专属的高密度组件只按当前尺寸文件选择。
4. **比例与普通百分比**：完成度、达成率、使用率、剩余占比等真实比例可使用进度或占比组件。湿度、降雨概率等普通百分比若只是属性，应作为带标签的文本，不因含 `%` 就生成圆环或进度条。同一比例关系中的 `percent`、`current`、`total` 与可用量／剩余量共同描述一个事实，不拆成多个重复组件；缺少真实比例、目标或总量时改用文本组件，不猜测进度。
5. **单个占比**：单个设备电量、容量余量等当前状态通常用 `ProgressCircleSingle`；只有它与另一组完整主辅信息共同形成“双信息块”时，才改用带进度尾部视觉的 `InfoBlock`。明确存在目标终点、重点是完成差距时使用 `ProgressLine2`。
6. **占比数量**：两个同级占比用 `ProgressCircle` × 2，三个用一个 `NumericRatioStack`，四个用 `ProgressCircle` × 4。对象无法由 Icon 清楚区分时，改用带文字标签的组件。
7. **时间信息**：时间决定事件成立或排序时使用 `EventCard`；普通时间属性使用文本组件。同一事件数据只表达一次。

## 2. 标题组件

### 2.1 `SingleLineTitle`

#### 选择条件

用于简短的静态分区标题，或由一个输入字段直接承担的对象名、地点名、设备名。标题只占一行；长标题会省略。

#### 组件属性

| Prop | 类型 | 要求 | 可绑定字段 |
|---|---|---|---|
| `title` | `string` | 必选 | `dataIds.title` |
| `titleTemplate` | `string` | 仅绑定动态标题且需要静态前后缀时可选；必须且只能包含一个 `{value}` | 与 `dataIds.title` 配对 |
| `dataIds` | `{ title?: string }` | `title` 来自 `data[]` 时填写 | 仅 `title` |

#### 槽位与容量

进入标题位置，显示一个短标题。与内容的空间分配由 `Region.variant` 处理。

#### 示例

```jsx
<SingleLineTitle title="书房空气" dataIds={{ title: "air.device.roomName" }} />
```

#### 注意事项

根据 `userQuery` 概括的标题是静态 UI 文案，不绑定不存在的标题 ID。动态值需要固定前后缀时使用 `titleTemplate`，不要在正文再次展示同一事实。

### 2.2 `DoubleLineTitle`

#### 选择条件

用于“对象名称 + 状态／地点”等两个紧密相关、且都需要出现在标题区域的文本。只有一层标题时改用 `SingleLineTitle`。

#### 组件属性

| Prop | 类型 | 要求 | 可绑定字段 |
|---|---|---|---|
| `title` | `string` | 必选，最多一行 | `dataIds.title` |
| `secondaryInfo` | `string` | 必选，最多两行 | `dataIds.secondaryInfo` |
| `titleTemplate` | `string` | 动态标题需要静态前后缀时可选；包含一个 `{value}` | 与 `dataIds.title` 配对 |
| `secondaryInfoTemplate` | `string` | 动态次信息需要静态前后缀时可选；包含一个 `{value}` | 与 `dataIds.secondaryInfo` 配对 |
| `dataIds` | `{ title?: string, secondaryInfo?: string }` | 对应内容来自 `data[]` 时填写 | 同名 Prop |
| `dataValueMaps` | `{ title?: { true: string, false: string }, secondaryInfo?: { true: string, false: string } }` | 对应绑定值为 Boolean 文案时填写 | 与同名 `dataIds` 配对 |

#### 槽位与容量

进入标题位置，表达标题和一至两行次级信息。它比单行标题占用更多内容容量；主体较多时改用 `SingleLineTitle` 或更宽的内容区。

#### 示例

```jsx
<DoubleLineTitle
  title="阳台传感器"
  secondaryInfo="已连接"
  dataIds={{ title: "sensor.displayName", secondaryInfo: "sensor.connected" }}
  dataValueMaps={{ secondaryInfo: { true: "已连接", false: "未连接" } }}
/>
```

#### 注意事项

两项分别判断是否绑定；不能因为使用双层标题而给静态文案虚构 ID。

### 2.3 `Badge`

#### 选择条件

仅当 `userQuery` 要求展示某个集合的数量、输入 `data[]` 有对应的真实数量字段，且当前标题明确命名同一集合时，才考虑 `Badge`。例如“未来7天日程”的日程总数。`Badge` 是可选的标题附属标记，不是所有数量字段的默认组件；如果数量本身是卡片的唯一核心信息，应使用能清楚表达主值的内容组件。

#### 组件属性

| Prop | 类型 | 要求 | 可绑定字段 |
|---|---|---|---|
| `value` | `string \| number` | 必选；字符串只用于 `99+` 等格式化数量 | `dataIds.value` |
| `color` | `"blue" \| "orange" \| "green" \| "red" \| "purple" \| "cyan" \| "pink"` | 可选；通常省略 | 不绑定 |
| `dataIds` | `{ value?: string }` | `value` 来自 `data[]` 时填写 | 仅 `value` |

#### 槽位与容量

`Badge` 不能单独进入标题位或内容位，只能紧跟一个标题组件，按“标题与数量”组合作为一个标题单元进入带标题的槽位。必须绑定上述真实数量字段，不根据可见列表项数推测总数；数量保持简短，并且在整张卡片中只表达一次。

#### 示例

```jsx
<Badge
  value={1}
  color="pink"
  dataIds={{ value: "calendar.eventCount" }}
/>
```

#### 注意事项

状态、类别、温度、时长、百分比和普通核心数值都不是标题数量，不使用 `Badge`。命中“标题与数量”组合后，同一个数量不得再进入 `EmphasizedData`、`EmphasisText`、`TableText` 或其他正文组件。

## 3. 文本与信息组件

### 3.1 `EmphasizedData`

#### 选择条件

用于一个分区中最需要突出的数值、时长、温度等核心数据。纯文本结论使用 `EmphasisText`。只有满足“标题与数量”的成立条件时才考虑 `Badge`；真实进度、占比、同量纲比较或事件信息分别保留其专用组件候选，不因文本组件更容易排版就提前退化为大号数值。

#### 组件属性

| Prop | 类型 | 要求 | 可绑定字段 |
|---|---|---|---|
| `value` | `string \| number` | 与 `items` 二选一 | `dataIds.value` |
| `unit` | `string` | 独立数字需要静态单位时填写 | `dataIds.unit` 仅在输入确有独立单位字段时使用 |
| `items` | `Array<{ key?, value, unit?, dataIds? }>` | 多个数值段共同构成一个核心语义时使用 | 每项 `value`／`unit` |
| `dataIds` | `{ value?: string, unit?: string }` | 对应值来自 `data[]` 时填写 | 同名 Prop |

#### 槽位与容量

属于单核心内容。适合一个突出数值；完整值过长时选择普通文本组件或更宽内容区，不能依靠裁剪。

#### 示例

```jsx
<EmphasizedData value={1250} unit="毫升" dataIds={{ value: "hydration.today.amount" }} />
```

完整格式化字符串：

```jsx
<EmphasizedData value="1小时45分" dataIds={{ value: "focus.today.durationText" }} />
```

#### 注意事项

输入值已经包含单位时原样放入 `value`，不拆分、不再填写 `unit`。一个分区只选择一个核心强调组件。

### 3.2 `EmphasisText`

#### 选择条件

用于一个分区中最重要的文本结论、类别或状态。`secondaryText` 只补充同一个核心语义，不承载另一个独立主题。日程事件、标题数量、真实进度或同量纲比较已经匹配专用组件时，不改用 `EmphasisText` 拆散其结构。

#### 组件属性

| Prop | 类型 | 要求 | 可绑定字段 |
|---|---|---|---|
| `mainText` | `string` | 必选 | `dataIds.mainText` |
| `secondaryText` | `string` | 可选 | `dataIds.secondaryText` |
| `secondaryTextTemplate` | `string` | `secondaryText` 绑定多个 ID 时必选；按 ID 顺序各使用一次 `{0}`、`{1}`……并补足必要标签 | 与 `dataIds.secondaryText` 配对 |
| `dataIds` | `{ mainText?: string, secondaryText?: string \| string[] }` | 对应值来自 `data[]` 时填写 | `mainText` 只绑定一个 ID；`secondaryText` 数组至少 2 个 ID |
| `dataValueMaps` | `{ mainText?: { true: string, false: string }, secondaryText?: { true: string, false: string } }` | 单 ID Boolean 显示文案时填写 | 与同名 `dataIds` 配对 |

#### 槽位与容量

属于单核心内容，可表达主文本和一条短补充。两条文字都较长时不进入紧凑内容区。

#### 示例

```jsx
<EmphasisText
  mainText="已连接"
  secondaryText="FreeBuds Pro 3"
  dataIds={{
    mainText: "earphone.isConnected",
    secondaryText: "earphone.earphoneName",
  }}
  dataValueMaps={{
    mainText: { true: "已连接", false: "未连接" },
  }}
/>
```

多个短字段共同组成一个显示 Prop：

```jsx
<EmphasisText
  mainText="多云"
  secondaryText="城市上海市 ｜ 区域青浦区"
  secondaryTextTemplate="城市{0} ｜ 区域{1}"
  dataIds={{
    mainText: "weather.current.condition",
    secondaryText: ["weather.location.prefectureName", "weather.location.districtName"],
  }}
/>
```

#### 注意事项

`mainText` 不允许数组绑定。`secondaryText` 的数组绑定按顺序用索引模板组合，不接受 Boolean，也不能与 `dataValueMaps` 同时用于同一 Prop；模板不能重复输入值已有的单位。

### 3.3 `SecondaryBody`

#### 选择条件

用于补充同一分区中的核心信息。至少包含两个短字段，不能作为分区内唯一的业务组件。能够稳定形成多项标签—参数的同级属性时使用 `TableText`；事件、比较、进度等结构不使用 `SecondaryBody` 代替专用组件。

#### 组件属性

| Prop | 类型 | 要求 | 可绑定字段 |
|---|---|---|---|
| `items` | `Array<{ key?, label?, value, dataIds? }>` | 必选，至少 2 项 | 每项 `dataIds.value` |
| `separator` | `string` | 可选，默认 ` ｜ ` | 不绑定 |

#### 槽位与容量

属于短明细组件。每行最多两项，项目较多会增加占用；具体槽位和容量由当前尺寸文件规定。

#### 示例

```jsx
<SecondaryBody
  items={[
    {
      label: "夜间睡眠",
      value: "7小时1分",
      dataIds: { value: "healthSport.nightSleepDurationText" },
    },
    {
      label: "午睡",
      value: "0分",
      dataIds: { value: "healthSport.totalNapDurationText" },
    },
  ]}
/>
```

#### 注意事项

裸数字、百分比和孤立等级需要静态 `label`。`items` 不支持 `unit`；完整展示值保持原样。

### 3.4 `DataDisplay`

#### 选择条件

由文本标签、核心数值和单位／辅助信息组成的三行纵向文本组件，用于“核心居中”单模块布局。它适合倒计时、日期等需要以一个超大数值作为唯一视觉核心的场景，不用于同一分区并列展示多组数据。

#### 组件属性

| Prop | 类型 | 要求 | 可绑定字段 |
|---|---|---|---|
| `label` | `string` | 必选；第一行静态标签 | 无 |
| `value` | `number \| string` | 必选；保持输入值，不附加静态单位 | `value` |
| `supportingText` | `string` | 必选；第三行静态单位或说明 | 无 |
| `dataIds` | `{ value?: string }` | `value` 来自输入时必选 | 仅 `value` |

#### 槽位与容量

组件宽度由当前核心居中槽决定；`label`、`value` 与 `supportingText` 均保持单行。具体最大宽度、高度和内部行距以当前布局规范为准；自适应不表示任意缩放，也不允许进入带标题、按钮或其他业务组件的骨架。

#### 示例

```jsx
<DataDisplay
  label="距离开始"
  value={3}
  supportingText="天"
  dataIds={{ value: "countdown.remainingDays" }}
/>
```

#### 注意事项

`label` 和 `supportingText` 是静态说明，只绑定中间的动态 `value`。即使说明文案与输入内容相同，也不得为它们填写 `dataIds`。

### 3.5 `InfoBlock`

#### 选择条件

用于固定信息槽中的一组完整主辅信息。尾部可显示对象 Icon 或由 `primaryText` 驱动的占比圆环。只有信息天然形成“主信息 + 辅助信息”且当前尺寸提供固定槽或双信息块组合时选择，不把任意两个字段压成 `InfoBlock`。

#### 组件属性

| Prop | 类型 | 要求 | 可绑定字段 |
|---|---|---|---|
| `primaryText` | `string \| number` | 必选，单行 | `dataIds.primaryText` |
| `primaryTextTemplate` | `string` | 单 ID 主文本需要静态语义时可选；包含一个 `{value}` | 与 `dataIds.primaryText` 配对 |
| `secondaryText` | `string \| number` | 必选，单行；解释主值或提供同一对象的一项相关信息 | 可选的单个 `dataIds.secondaryText` |
| `secondaryTextTemplate` | `string` | 次文本绑定一个 ID 且需要静态标签时使用一个 `{value}` | 与 `dataIds.secondaryText` 配对 |
| `unit` | `string` | 可选，静态 | 不绑定 |
| `visual` | `{ type: "icon", icon, color?: "native" } \| { type: "progressCircle", icon }` | 可选，二选一 | 不绑定 |
| `dataIds` | `{ primaryText?: string, secondaryText?: string }` | 主、次文本各最多绑定一个 ID；静态次文本不绑定 | 同名 Prop |
| `dataValueMaps` | `{ primaryText?: { true: string, false: string }, secondaryText?: { true: string, false: string } }` | Boolean 显示文案时填写 | 与同名 `dataIds` 配对 |

#### 槽位与容量

属于固定模块。每个固定槽放一个 `InfoBlock`；具体合法槽位由当前尺寸文件和 Layouts 定义。不要向组件传宽高。

`InfoBlock` 是低信息密度的固定模块：主文本只表达一个业务值，最多绑定一个 ID；次文本或者是不绑定的静态说明，或者绑定同一对象的一项相关信息，最多一个 ID。不得在任一文本中拼接多个动态字段，也不得靠静态文案重复展示其他输入业务值。主文本不把对象名、指标名和已有单位一起塞进 `primaryTextTemplate`。例如主文本为 `29.0 ℃` 时，静态次文本可写“电池温度”。两行都应在固定槽内完整可读；承载不了的字段应使用其他组件或调整布局，不能继续压进此槽。

#### 示例

假设当前资源候选中存在 `moon_z_fill_1.svg`，且这是睡眠卡中的信息槽：

```jsx
<InfoBlock
  primaryText={82}
  unit="分"
  secondaryText="状态良好"
  secondaryTextTemplate="状态 {value}"
  visual={{ type: "icon", icon: "moon_z_fill_1.svg" }}
  dataIds={{
    primaryText: "healthSport.sleepScore",
    secondaryText: "healthSport.sleepStatus",
  }}
/>
```

#### 注意事项

`visual` 不是必填装饰。只有存在语义匹配资源时才使用；占比视觉只用于 0–100 的 `primaryText`。Icon 不能以裁切主辅文本为代价；文本仍放不下时可以省略 Icon，但不要省略承载进度语义的圆环。动态值需要标签时使用 Template，而不是把标签静态焊死在显示 Prop 中；Template 只补充必要标签，不重复数据已有的单位或同一组件的 `unit`。

### 3.6 `TableText`

#### 选择条件

用于同一主题下至少两项“标签—参数”的纵向同级属性。参数右对齐，适合紧凑列举；单项信息不要使用。时间决定事件成立时使用 `EventCard`，满足“标题与数量”条件时才考虑 `Badge`，用户重点是比较同一指标大小时使用 `H_BarChart`，不得把这些结构统一降级为键值表。

#### 组件属性

| Prop | 类型 | 要求 | 可绑定字段 |
|---|---|---|---|
| `items` | `Array<{ key?, label, parameter, dataIds?, dataValueMaps? }>` | 必选，至少 2 项 | 每项 `label`／`parameter` 可独立绑定 |
| `items[].label` | `string` | 必选；说明性标签保持静态，输入字段直接提供行标识时使用其值 | `items[].dataIds.label`，单个 ID |
| `items[].parameter` | `string \| number` | 必选 | `items[].dataIds.parameter`，可为至少 2 个 ID 的数组 |
| `items[].dataValueMaps` | `{ parameter?: { true: string, false: string } }` | 单 ID Boolean 显示文案时填写 | 与同项绑定配对 |

#### 槽位与容量

属于纵向高密度内容，项目越多占用越高。具体槽位和可用项数由当前尺寸文件规定。

#### 示例

```jsx
<TableText
  items={[
    {
      label: "连接方式",
      parameter: "蓝牙",
      dataIds: { parameter: "sensor.connectionType" },
    },
    {
      label: "协议版本",
      parameter: "5.3",
      dataIds: { parameter: "sensor.protocolVersion" },
    },
    {
      label: "工作模式",
      parameter: "低功耗",
      dataIds: { parameter: "sensor.operationMode" },
    },
  ]}
/>
```

#### 注意事项

说明性标签是静态文案；日期、设备名等来自输入的行标识则填写同一项的 `dataIds.label`，并保留对应的 `dataIds.parameter`。不同记录即使预览值相同，也要各自绑定原始 ID，不能把一个样例标签写死给所有行。需要横向同级属性时，按当前尺寸的专属组件合同选择相应明细组件。

## 4. 进度、比较与占比组件

### 4.1 `ProgressLine2`

#### 选择条件

用于一个当前值相对明确目标或总量的连续进度。没有明确分母或比例关系时不使用；命中真实进度关系后，不只用 `EmphasizedData` 或 `TableText` 展示当前值而丢失当前—目标关系。

#### 组件属性

| Prop | 类型 | 要求 | 可绑定字段 |
|---|---|---|---|
| `currentValue` | `number` | 必选，初始当前值 | 不绑定 |
| `totalValue` | `number` | 必选且大于 0 | 不绑定 |
| `value` | `string \| number` | 与 `items` 二选一；省略时显示推导百分比 | `dataIds.value` |
| `unit` | `string` | 可选 | `dataIds.unit` 仅在输入确有独立单位字段时使用 |
| `items` | `Array<{ key?, value, unit?, dataIds? }>` | 多个数值段共同构成同一展示值时使用 | 每项 `value`／`unit` |
| `mode` | `"light" \| "dark"` | 必选；与 Card 背景明暗一致 | 不绑定 |
| `dataIds` | `{ value?: string, unit?: string }` | 对应显示值来自 `data[]` 时填写 | 不绑定 `currentValue`、`totalValue` |

#### 槽位与容量

属于单进度内容，进入普通内容槽。需要同时展示较多明细时与短补充组件组合或改用整宽布局。

#### 示例

```jsx
<ProgressLine2
  currentValue={6}
  totalValue={10}
  value={6}
  unit="章已读"
  mode="light"
  dataIds={{ value: "reading.book.completedChapters" }}
/>
```

#### 注意事项

`currentValue` 和 `totalValue` 决定初始进度，但动态绑定只写可见的 `value`／`unit`。`mode` 与当前 Card 背景明暗一致：单色浅背景使用 `light`，深色背景使用 `dark`。

### 4.2 `H_BarChart`

#### 选择条件

用于比较 2–3 个对象的同一指标，尤其是用户目标要求看出对象间大小、排序或差异时。单个值或不同量纲的数据不能使用；命中比较关系后，不退化成缺少比较视觉的多个普通文本。

#### 组件属性

| Prop | 类型 | 要求 | 可绑定字段 |
|---|---|---|---|
| `items` | `Array<{ key?, label, valueUnit, percent, dataIds? }>` | 必选，2–3 项 | 每项 `valueUnit` |
| `items[].label` | `string` | 必选，静态 | 不绑定 |
| `items[].valueUnit` | `string` | 必选，可见值 | `items[].dataIds.valueUnit` |
| `items[].percent` | `number` | 必选，0–100；决定柱长 | 不绑定 |
| `mode` | `"light" \| "dark"` | 必选；与 Card 背景明暗一致 | 不绑定 |

#### 槽位与容量

属于连续比较内容，2–3 项共同构成一个内容模块；具体槽位与容量由当前尺寸文件规定。

#### 示例

```jsx
<H_BarChart
  mode="light"
  items={[
    { label: "客厅", valueUnit: "3.2千瓦时", percent: 80, dataIds: { valueUnit: "energy.room.livingText" } },
    { label: "书房", valueUnit: "1.8千瓦时", percent: 45, dataIds: { valueUnit: "energy.room.studyText" } },
  ]}
/>
```

#### 注意事项

`percent` 是按同一尺度换算的初始柱长，`valueUnit` 保留输入的真实展示值；不要把不同单位强行比较。

### 4.3 `ProgressCircleSingle`

#### 选择条件

用于一个对象的单一占比，并在圆环右侧显示标签、占比或独立绝对值。手机电量、设备电量、容量余量等单对象当前占比默认保留该组件候选。具体尺寸是否要求紧凑规格由当前尺寸文件规定。

#### 组件属性

| Prop | 类型 | 要求 | 可绑定字段 |
|---|---|---|---|
| `value` | `number \| string` | 必选；0–100 数字或完整百分比字符串 | `dataIds.value` |
| `icon` | `string` | 必选，来自当前资源候选 | 不绑定 |
| `displayValue` | `string` | 可选；只在与圆环值为不同字段时使用 | `dataIds.displayValue` |
| `label` | `string` | 必选 | `dataIds.label` |
| `secondaryLabel` | `string` | 可选 | `dataIds.secondaryLabel` |
| `ariaLabel` | `string` | 必选，完整描述 | 不绑定 |
| `appearance` | `"card"` | 必选 | 不绑定 |
| `size` | `"compact"` | 当前尺寸文件要求紧凑规格时填写 | 不绑定 |
| `dataIds` | `{ value?: string, displayValue?: string, label?: string, secondaryLabel?: string }` | 对应值来自 `data[]` 时填写 | 同名 Prop |

#### 槽位与容量

属于单核心占比内容。标签和补充状态保持简短；是否使用 `size="compact"` 由当前尺寸的容量规则决定。

#### 示例

假设当前资源候选中存在 `battery_leaf_fill.svg`：

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

输入提供耳机总电量整数时，同一个组件可以直接绑定该百分比：

```jsx
<ProgressCircleSingle
  value={82}
  icon="earphone_fill.svg"
  label="耳机电量"
  ariaLabel="耳机电量82%"
  appearance="card"
  dataIds={{ value: "earphone.batteryLevel" }}
/>
```

#### 注意事项

当可见百分比由 `value` 自动生成时，不要把同一 ID 再绑定到 `displayValue`。`displayValue` 只用于另一个独立展示字段。圆环、`label`、`displayValue` 和 `secondaryLabel` 共同构成一个组件，不再把这些内容重复生成为其他文本组件或布局模块。

### 4.4 `ProgressCircle`

#### 选择条件

只用于两个或四个同级对象的真实占比、百分比或明确的 0–100 有界进度。数值必须表示部分相对整体、当前相对目标或完成程度；即使样例值落在 0–100，天数、次数、总数、事件数量、时间、温度、距离、金额等绝对量也不能使用 `ProgressCircle`。单个占比使用 `ProgressCircleSingle`，三个同级占比使用 `NumericRatioStack`。

#### 组件属性

| Prop | 类型 | 要求 | 可绑定字段 |
|---|---|---|---|
| `icon` | `string` | 必选，来自当前资源候选 | 不绑定 |
| `externalText` | `string \| number` | 必选；0–100 数字或完整百分比字符串，且业务含义必须是占比或有界进度 | `dataIds.externalText` |
| `size` | `"sm"` | 必选 | 不绑定 |
| `ariaLabel` | `string` | 必选 | 不绑定 |
| `appearance` | `"card"` | 必选 | 不绑定 |
| `dataIds` | `{ externalText?: string }` | 值来自 `data[]` 时填写 | 仅 `externalText` |

#### 槽位与容量

不能单独自由排版。两个或四个实例必须进入当前尺寸明确提供的对应占比组合槽；具体 `Region.variant` 由当前尺寸文件规定。

#### 示例

假设当前资源候选中存在 `zone_a_fill.svg`：

```jsx
<ProgressCircle
  icon="zone_a_fill.svg"
  externalText={74}
  size="sm"
  ariaLabel="A区灌溉进度74%"
  appearance="card"
  dataIds={{ externalText: "irrigation.zoneA.percent" }}
/>
```

#### 注意事项

`externalText` 同时驱动圆环和外部数值，不再生成 `value`。组件必须按 2 个或 4 个实例成组使用。不要为了使用双环或四环布局，把两个无共同比例尺度的普通数字并列为 `ProgressCircle`；这类绝对值改用 `EmphasizedData`、`EmphasisText`、`InfoBlock` 或其他语义匹配的文本组件。

### 4.5 `NumericRatioStack`

#### 选择条件

只用于三个同级对象的占比，每个对象能够由 Icon 明确区分。需要文字标签解释对象时改用其他组件。

#### 组件属性

| Prop | 类型 | 要求 | 可绑定字段 |
|---|---|---|---|
| `appearance` | `"card"` | 必选 | 不绑定 |
| `direction` | `"row" \| "column"` | 必选；按当前槽位支持的排列方向填写 | 不绑定 |
| `items` | `Array<{ icon, value, unit?, dataIds? }>` | 必选，恰好 3 项 | 每项 `dataIds.value` |
| `items[].icon` | `string` | 必选，来自当前资源候选 | 不绑定 |
| `items[].value` | `string \| number` | 必选 | 同项 `dataIds.value` |
| `items[].unit` | `string` | 数字值可写 `%`；完整字符串不重复单位 | 不绑定 |

#### 槽位与容量

整体作为一个高密度内容组件进入单内容槽，不拆成三个 JSX 组件。

#### 示例

假设当前资源候选中存在三个对应 Icon：

```jsx
<NumericRatioStack
  direction="column"
  appearance="card"
  items={[
    { icon: "storage_node_a.svg", value: 82, unit: "%", dataIds: { value: "storage.nodeA.usedPercent" } },
    { icon: "storage_node_b.svg", value: 61, unit: "%", dataIds: { value: "storage.nodeB.usedPercent" } },
    { icon: "storage_node_c.svg", value: 34, unit: "%", dataIds: { value: "storage.nodeC.usedPercent" } }
  ]}
/>
```

#### 注意事项

`value` 中只放数值，不加入对象名称；对象必须由 Icon 足够清楚地区分。必须恰好三项。

## 5. 日程组件

### 5.1 `EventCard`

#### 选择条件

用于 1–2 条按时间排列的事件。一张卡片最多生成一个 `EventCard`；两条事件必须放在同一个 `EventCard` 中，并按时间先后排序。输入同时具有事件标题与时间时优先使用 `EventCard`，不因普通文本更容易填槽就拆成 `EmphasisText` 或 `SecondaryBody`。两条事件普通高度放不下时，可在同一个组件上使用 `density="compact"`。不得生成超过两项的 `EventCard.items`，也不得仅为绕过容量把事件结构改写成普通文本组件。

#### 组件属性

| Prop | 类型 | 要求 | 可绑定字段 |
|---|---|---|---|
| `items` | `Array<{ title, time, location?, dataIds? }>` | 必选，1–2 项 | 每项 `title`、`time`、`location` |
| `items[].title` | `string` | 必选 | `items[].dataIds.title` |
| `items[].time` | `string` | 必选 | `items[].dataIds.time`，可为 `[startId, endId]` |
| `items[].location` | `string` | 可选 | `items[].dataIds.location` |
| `density` | `"compact"` | 两条事件普通高度放不下时使用 | 不绑定 |

#### 槽位与容量

属于连续内容，一个组件可承载 1–2 条事件。具体槽位、事件数与密度限制由当前尺寸文件规定。

#### 示例

```jsx
<EventCard
  items={[
    {
      title: "用户卡片需求评审会",
      time: "09:00",
      location: "练秋湖C5会议室",
      dataIds: {
        title: "calendar.events.0.title",
        time: "calendar.events.0.dtStart",
        location: "calendar.events.0.eventLocation",
      },
    },
    {
      title: "版本复盘会",
      time: "15:00",
      dataIds: {
        title: "calendar.events.1.title",
        time: "calendar.events.1.dtStart",
      },
    },
  ]}
  density="compact"
/>
```

#### 注意事项

事件标题不是分区标题。`time` 的二元数组固定按开始、结束顺序；只有一个时间时使用字符串 ID。

## 6. 操作组件

### 6.1 `PillButton`

#### 选择条件

用于内容区内部的一个直属 Action；不用于固定模块槽。

#### 组件属性

| Prop | 类型 | 要求 | 可绑定字段 |
|---|---|---|---|
| `label` | `string` | 必选 | 不绑定 |
| `icon` | `string` | 可选，来自当前资源候选 | 不绑定 |
| `appearance` | `"card"` | 必选 | 不绑定 |
| `disabled` | `boolean` | 可选 | 不绑定 |
| `actionId` | `string` | 启用状态必选 | 原样引用一个 `actions[].id` |

#### 槽位与容量

表达内容区中的一个直属 Action。具体合法槽位由当前尺寸文件规定。

#### 示例

```jsx
<PillButton
  label="进入锻炼"
  icon="figure_run.svg"
  appearance="card"
  actionId="event.open.health.sport"
/>
```

#### 注意事项

一个按钮只绑定一个 Action。Icon 与卡内其他组件重复或没有语义匹配候选时省略。

## 7. 选择检查

- 每个组件只使用自身“组件属性”表中逐字存在的 Prop 和枚举值。
- 组件的内容结构与真实信息一一对应，没有用单值组件承载多个独立主题。
- 同级多值优先使用匹配数量和关系的高密度组件，没有拆成重复的零散文本。
- 占比、进度和比较组件都有真实的比例或同量纲关系。
- 每个组件的必选 Prop、数据绑定和 Action 绑定完整，未使用表中不存在的 Prop。
- 组件的内容长度、项目数和占位类型符合候选 `Region.variant`。
