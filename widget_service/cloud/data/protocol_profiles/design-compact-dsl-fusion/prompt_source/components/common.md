# 共享组件合同（维护源）

> 维护说明不发给模型；仅 `prompt` 标记内正文参与构建。

## 边界与阅读顺序

组件总表与选择边界 → Compact DSL 共同规则 → 布局与基础内容组件 → 共享语义组件 → 选择检查。
组件行格式、root、画布、色板和一级布局分别以 `core.md`、`layouts/common.md` 和尺寸布局文件为准。

## 基础布局组件总表（维护导航，不发模型）

| 名称 | 布局职责 | 容量与约束 |
|---|---|---|
| `Row` | 横向排列子组件 | 子组件与横向预算必须成立 |
| `Column` | 纵向排列子组件 | 子组件与纵向预算必须成立 |
| `Stack` | 叠放子组件 | 只用于背景与前景、图标底板等真实叠放 |

只有基础布局组件通过组件行第 4 项声明 `children`。它们只负责排列和承载，不替代信息、进度、标题或操作组件。

## 片段索引

| 片段 | 用途 |
|---|---|
| `selection` | Plan 与 DSL 共用的组件总表和选择边界 |
| `catalog` | DSL 生成使用的完整 Compact DSL 组件合同 |

片段由 manifest 编排；修改正文后验证并重启服务，无需生成中间文件。

<!-- prompt:selection -->
## 1. 组件总表

| 类型 | 名称 | 内容结构 | 适用场景 | 容量与约束 |
|---|---|---|---|---|
| 标题 | `SingleLineTitle` | 单行标题 | 简短概括一个语义分区 | 每个分区最多一个；不用正文组件替代 |
| 标题 | `DoubleLineTitle` | 标题 + 次级信息 | 对象名还需同时表达状态或地点 | 两项必须紧密相关 |
| 标题附属 | `Badge` | 标题关联数量 | 标题旁显示同一集合的真实数量 | 只能与标题组成标题单元 |
| 核心信息 | `EmphasizedData` | 核心数值 + 可选单位 | 突出唯一量化主值 | 一个核心值；不吸收辅助信息 |
| 核心信息 | `EmphasisText` | 主文本 + 可选次文本 | 突出文本结论、类别或状态 | 两行必须属于同一核心语义 |
| 正文与补充 | `SecondaryBody` | 1–4 个正文、metadata 或短说明项 | 普通正文、时间、弱提示和同区补充信息 | 用 `role` 决定语义与行数，不开放任意文字样式 |
| 核心信息 | `DataDisplay` | 标签 + 主值 + 支撑文本 | 2x2 单一量化焦点 | 三项各一行；不吸收动作或第二指标 |
| 紧凑信息 | `InfoBlock` | 主信息 + 辅助信息 + 可选图标或占比圆环 | 固定小槽中的完整主辅信息 | 每槽一个；不支持事件 |
| 多项属性 | `TableText` | 多行标签—值 | 同一主题的 2–3 项属性 | 两种尺寸共用；进入连续内容槽 |
| 摘要列表 | `SummaryList` | 2–3 条同级摘要 | 2x4 短列表 | 每项固定单行显示 |
| 占比 | `ProgressCircle` | 环心图标 + 环外读数 | 两个或四个同级对象的真实占比 | 每个实例表达一个 `0–100` 比例 |
| 线性进度 | `ProgressLine2` | 可见读数 + 线性进度 | 当前值相对明确总量 | 当前只用于 2x4 连续内容区 |
| 比较 | `H_BarChart` | 2–3 组标签、值和横向柱 | 比较多个对象的同一指标 | 不比较不同量纲 |
| 环形进度 | `ProgressCircleSingle` | 单环 + 右侧读数组 | 单个真实比例及同对象说明 | 两种尺寸共用；规格由尺寸文件决定 |
| 占比摘要 | `NumericRatioStack` | 三组图标 + 数值 + 单位 | 三个同级对象的紧凑占比 | 必须恰好三项且图标可区分 |
| 日程 | `EventCard` | 时间线 + 1–2 个事件 | 两种尺寸的连续日程内容 | 两项按时间排序并放在同一实例 |
| 操作 | `PillButton` | 操作文案 + 可选图标 | 两种尺寸内容区内的直属操作 | 一个实例绑定一个真实动作 |
| 操作 | `CircleButton` | 纯图标操作 | 2x2 右下锚点操作 | 2x2 专属；合同见 `components/2x2.md` |
| 等权指标 | `TopTextBottomValue` | 三组标签—数值—单位 | 2x4 三个同级指标 | 2x4 专属；合同见 `components/2x4.md` |
| 明细信息 | `TextBlock` | 2–4 组标签—值背板 | 2x4 同级详情 | 2x4 专属；合同见 `components/2x4.md` |
| 操作 | `CardButton` | 文案 + 可选图标 | 2x4 固定动作槽 | 2x4 专属；合同见 `components/2x4.md` |

### 1.1 关键选择边界

1. 每个语义分区最多使用一个 `SingleLineTitle`；2x4 左右独立分区可分别使用。标题加次信息使用 `DoubleLineTitle`，标题关联真实数量才使用 `Badge`；标题不用正文组件代替。
2. 先按信息语义和字段关系保留可行组件，再结合尺寸文件的槽位与容量确定最终组件；不为使用组件补造字段。
3. 有唯一核心值时使用一个强调或进度组件；没有真实主次时保持并列，不把普通数字强行放大为核心。
4. 文本核心结论使用 `EmphasisText`，短补充项使用 `SecondaryBody`；稳定标签—值使用 `TableText`。2x4 横向详情选择 `TextBlock` 或 `TopTextBottomValue`。
5. 单占比使用 `ProgressCircleSingle`；两个或四个同级占比使用多个 `ProgressCircle`；三个图标可区分的同级占比使用 `NumericRatioStack`；明确目标差距使用 `ProgressLine2`；2–3 个对象同指标比较使用 `H_BarChart`。
6. 一至两个按时间排列的事件使用一个 `EventCard`；普通时间属性使用 `SecondaryBody role="metadata"`。同一事实只展示一次。
7. 动作按槽位选择 `PillButton`、`CircleButton` 或 `CardButton`，只能绑定当前事件候选，不伪造操作。
<!-- /prompt:selection -->

<!-- prompt:catalog -->
# 2. Compact DSL 组件合同

只允许三种基础布局组件：`Row`、`Column`、`Stack`。

除基础布局组件外，只允许：`SingleLineTitle`、`DoubleLineTitle`、`Badge`、
`EmphasizedData`、`EmphasisText`、`SecondaryBody`、`DataDisplay`、`InfoBlock`、`TableText`、`SummaryList`、
`ProgressCircle`、`ProgressLine2`、`H_BarChart`、`ProgressCircleSingle`、`NumericRatioStack`、
`EventCard`、`PillButton`，以及尺寸文件登记的 `CircleButton`、`TopTextBottomValue`、`TextBlock`、`CardButton`。

禁止输出 `Button`、`Progress`、`List`、`TextInput`、`Toggle`、`Radio`、`Select`、`NavContainer`、
`Tabs`、`TabContent`、`Web`、`Grid`、`If`。禁止所有组件的 `theme`、`onAppear`、`onChange`、
`onSelect`、`onReachStart`、`onReachEnd`。
`Text` 只由转换器在展开语义组件时生成，模型不得直接输出。

## 2.1 组件共同规则

- 组件行的语义字段和样式字段直接写在第三项 `props`，不用的字段省略，不嵌套 `styles`。
- 只有 `Row`、`Column`、`Stack` 在第 4 项声明非空 `children`；其它组件均只输出一行且不带 children。
- 布局组件只能使用各自章节列出的字段。使用视觉 Recipe 的组件只能使用自身属性表，
  并可额外使用 `width`、`height`、`layoutWeight`、`flexShrink`、`margin` 调整组件根的外部布局。
- 视觉 Recipe 组件不接受 `padding`、圆角、字号、内部间距或对齐覆盖；内部结构、子节点 ID 和样式由转换器确定。
- 显示值按属性表使用静态值、完整 Expression 或 PathBinding；颜色和布局样式必须是静态合法值。
- `onClick` 只用于当前组件合同明确支持事件、且存在匹配事件候选的情况；一个入口只绑定一个真实动作。
- 动态布局样式、动态 children 和数组模板均不支持；不能从格式化字符串中猜测或截取数值。
- root 的尺寸、背景和布局规则见 `core.md` 与 `layouts/common.md`，不由组件合同重复定义。

## 3. 布局组件

### 3.1 `Row`

用于横向排列同级子组件。第 4 项 `children` 必填；`itemMargin` 可选数字 vp，`space` 是兼容别名。
`justifyContent` 只取 `start|center|end|spaceAround|spaceBetween|spaceEvenly`，`alignItems` 只取
`top|center|bottom`。可使用 `width`、`height`、`constraintSize`、`aspectRatio`、`margin`、`padding`、
`borderRadius`、`borderWidth`、`borderColor`、`backgroundColor`、`backgroundImage`、
`backgroundImageSizeWithStyle`、`linearGradient`、`shadow`、`layoutWeight`、`flexShrink`、`visibility`、`clip`。
子组件宽度、padding 与最小间距之和必须不超过父宽；分布式对齐不能修复负剩余空间。

### 3.2 `Column`

用于纵向排列有先后层级的子组件。第 4 项 `children` 必填；`itemMargin` 可选数字 vp，`space` 是兼容别名。
`justifyContent` 与 Row 相同，`alignItems` 只取 `start|center|end`，可使用与 Row 相同的布局与表面字段。
子组件高度、padding 与最小间距之和必须不超过父高；`layoutWeight` 和 `flexShrink` 不抵消真实最小高度。

### 3.3 `Stack`

只用于背景与前景、图标底板等真实叠放。第 4 项 `children` 必填；`alignContent` 只取
`topStart|top|topEnd|start|center|end|bottomStart|bottom|bottomEnd`。可使用与 Row 相同的布局与表面字段，
但不使用 `itemMargin`、`justifyContent` 或 `alignItems`。进度组件已包含内部结构，不再手写内部 Stack。

## 4. 显示内容共同规则

- 先按对象与信息关系合组，再选择能够完整承载该组的组件。Plan 首选满足自身语义、绑定、事件和容量合同
  时落实；不匹配才改用其它合法语义组件或组合。不将匹配的信息组无理由拆为逐字段单文字组件。
- 外部区域、背板和文字承载宽度随所属区域分配；固定标题、文字行高、图标、圆环和按钮高度不缩放。
  原有 padding 和组内间距保持原值；内容自然高度与自适应正文承载区分开，不拉大文字之间间距。

- 模型不直接生成 `Text`。标题、核心数字、核心文本、普通正文、metadata、主辅信息、事件和操作分别使用
  对应语义组件；转换器再将这些组件确定性展开为 A2UI 基础文字节点。
- 每个组件的属性表分别声明绑定能力；未声明可绑定的 Prop 只能使用静态值。`显示值`支持非空静态字符串、
  完整 Expression 或 PathBinding；直接 PathBinding 只绑定 string/number/integer，boolean 必须先用 Expression
  映射为用户可读文案。动态数据必须绑定真实路径，不能把 `sampleValue` 写成静态文字。
- 普通正文、普通时间、来源、更新时间、弱提示或没有更强语义结构的剩余单段内容使用
  `SecondaryBody`；一个文本结论或状态需要成为主焦点时使用 `EmphasisText`；量化主值使用
  `EmphasizedData` 或对应进度组件。
- 用户明确的标题、状态、日期、时间、主指标、价格、数量、联系人称呼和 CTA 必须完整显示；前后缀、负号、
  百分号和单位也是显示值的一部分。格式化值已含单位时完整绑定原值，不重复追加或拆分；原始数值需要单位时
  使用组件合同中的 `unit` 或完整 Expression，只展示一次准确单位。
- 选择组件前按字段语义允许的较长合法值完成压力检查；单行内容保留约 20% 宽度余量。放不下时按顺序缩短
  弱标签、删除可选字段、使用合同允许的两行模式、改选容量更大的槽位或简化布局，不依赖裁切、省略号、
  超小字号、负间距或遮罩。
- 同一事实只展示一次；不增加重复同义后缀，不用空内容制造间距，也不用多个语义组件重造已经完整匹配的结构。

## 5. 文本与信息组件

本节组件使用视觉 Recipe，只能使用自身属性表和 2.1 允许的外部布局字段。

### 5.1 `SingleLineTitle`

#### 选择条件

用于简短的静态分区标题，或由一个字段直接承担的对象名、地点名、设备名。每个语义分区最多一个；
2x4 左右独立分区可分别使用。数值、状态、日期时间和动作不用作标题，也不用正文组件重造标题。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `title` | 显示值 | 静态 / Expression / PathBinding | 必填；非空单行标题 |
| `fontColor` | `#AARRGGBB` | 仅静态 | 必填 |

#### 槽位与容量

固定高 `20vp`，进入卡级或分区标题位置。2x4 左右分区各自预算成立时可各放一个；具体宽度和合法位置由
尺寸布局文件规定。

#### 示例

```genui
["header","SingleLineTitle",{"title":"天气","fontColor":"#FF1F4799"}]
```

#### 注意事项

标题固定左对齐 `12fp/400`，只承载标题文字；不覆盖内部 padding、字号或字重。

### 5.2 `DoubleLineTitle`

#### 选择条件

用于标题区域中紧密相关的“对象名称 + 状态／地点”。只有一层标题时使用 `SingleLineTitle`，不能把两个独立主题
塞入一个双层标题。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `title` | 显示值 | 静态 / Expression / PathBinding | 必填；最多一行 |
| `secondaryInfo` | 显示值 | 静态 / Expression / PathBinding | 必填；最多两行 |
| `fontColor` | `#AARRGGBB` | 仅静态 | 必填 |

#### 槽位与容量

进入标题位置；主标题 `12fp/700`，次信息 `12fp/500`。它比 `SingleLineTitle` 占用更多高度，主体容量不足时改用
单行标题或更宽内容区。

```genui
["device_title","DoubleLineTitle",{"title":{"path":"/data/sensor/displayName"},"secondaryInfo":{"path":"/data/sensor/connectionStatus"},"fontColor":"#FF1F4799"}]
```

### 5.3 `Badge`

#### 选择条件

仅用于标题明确命名同一集合、且存在真实数量字段的“标题 + 数量”组合。状态、温度、时长、百分比和普通核心值
不使用；数量是唯一核心信息时使用内容组件。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `value` | 显示值 | 静态 / Expression / PathBinding | 必填；短数量或 `99+` |
| `fontColor` | `#AARRGGBB` | 仅静态 | 必填 |
| `backgroundColor` | `#AARRGGBB` | 仅静态 | 必填 |

#### 槽位与容量

不能单独进入标题位或内容位；必须紧跟标题组件，共同放入标题 Row。数量在整卡只表达一次。

```genui
["event_count","Badge",{"value":{"path":"/data/calendar/eventCount"},"fontColor":"#FF8C4B1C","backgroundColor":"#338C4B1C"}]
```

### 5.4 `EmphasizedData`

#### 选择条件

用于一个内容区中唯一需要突出的核心数值或完整格式化数值。多个同级指标和普通文本结论不使用。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `value` | 显示值 | 静态 / Expression / PathBinding | 必填；一个核心值 |
| `unit` | string | 静态 / Expression / string PathBinding | 可选；只绑定或填写单位文本 |
| `fontColor` | `#AARRGGBB` | 仅静态 | 必填 |

#### 槽位与容量

只承载一个核心值；合法槽位和宽度由当前尺寸文件规定，不吸收标题、辅助信息或第二指标。

#### 示例

```genui
["reading","EmphasizedData",{"value":{"path":"/data/healthSport/sleepScore"},"unit":"分","fontColor":"#FF563D99"}]
```

#### 注意事项

值已包含单位时不再传 `unit`；不把多个同级值拼进一个 `value`。

### 5.5 `EmphasisText`

#### 选择条件

用于一个分区最重要的文本结论、类别或状态。次文本只补充同一个核心语义；数值核心使用
`EmphasizedData`，事件、进度或比较保持专用组件。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `mainText` | 显示值 | 静态 / Expression / PathBinding | 必填；核心文本 |
| `secondaryText` | 显示值 | 静态 / Expression / PathBinding | 可选；同一语义的一条短补充 |
| `fontColor` | `#AARRGGBB` | 仅静态 | 必填 |

```genui
["connection","EmphasisText",{"mainText":{"path":"/data/earphone/connectionStatus"},"secondaryText":{"path":"/data/earphone/name"},"fontColor":"#FF1F4799"}]
```

### 5.6 `SecondaryBody`

#### 选择条件

用于普通正文、普通时间、来源、更新时间、弱提示，或补充同一分区的核心信息。单项通过 `role` 表达正文或
metadata；多个短字段使用 supporting。稳定标签—值表使用 `TableText`；事件、比较和进度不使用它代替。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `items` | Array | 数组结构仅静态 | 必填；1–4 项 |
| `items[].value` | 显示值 | 静态 / Expression / PathBinding | 必填；真实可见内容 |
| `items[].label` | string | 仅静态 | 可选；短标签 |
| `items[].maxLines` | number | 仅静态 | 可选；只取 `1|2` |
| `role` | string | 仅静态 | 单项必填；`body|metadata|supporting`；多项新生成也应显式填写 |
| `separator` | string | 仅静态 | 可选；默认 ` ｜ ` |
| `fontColor` | `#AARRGGBB` | 仅静态 | 必填 |

`role:"body"` 恰好一项，不写 label，`maxLines` 可为 `1|2`；`role:"metadata"` 恰好一项且只能单行；
`role:"supporting"` 支持 1–4 项，每项只能单行，每行最多两项，超过两项自动分为两行。为兼容旧 DSL，
2–4 项省略 role 时按 supporting 处理；新生成必须显式填写 role。完整显示值保留原样，不拆单位，也不开放
字号、字重、padding 或内部对齐等任意样式属性。

```genui
["description","SecondaryBody",{"role":"body","items":[{"value":{"path":"/data/weather/description"},"maxLines":2}],"fontColor":"#FF1F4799"}]
["updated","SecondaryBody",{"role":"metadata","items":[{"value":"{{ '更新 ' + ${/data/weather/updatedAt} }}"}],"fontColor":"#FF1F4799"}]
["sleep_detail","SecondaryBody",{"role":"supporting","items":[{"label":"夜间睡眠 ","value":{"path":"/data/healthSport/nightSleepDurationText"}},{"label":"午睡 ","value":{"path":"/data/healthSport/napDurationText"}}],"fontColor":"#FF563D99"}]
```

### 5.7 `DataDisplay`

#### 选择条件

用于 2x2 中一个短标签、一个唯一核心数值和一条短支撑文本。存在动作、第二指标或独立说明时不使用。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `label` | string | 仅静态 | 必填；非空短文本 |
| `value` | 显示值 | 静态 / Expression / PathBinding | 必填；唯一核心值 |
| `supportingText` | string | 仅静态 | 必填；单位或短说明 |
| `fontColor` | `#AARRGGBB` | 仅静态 | 必填 |

#### 槽位与容量

合同在本文件定义，当前只进入 2x2 `S-center` 的唯一内容区；具体几何由 `components/2x2.md` 规定。

#### 示例

```genui
["display","DataDisplay",{"label":"运动会倒计时","value":{"path":"/data/countdown/countdownDays"},"supportingText":"天","fontColor":"#FFFFFFFF"}]
```

#### 注意事项

值已包含完整单位时改用其他合适组件，不重复单位。

### 5.8 `InfoBlock`

#### 选择条件

用于固定小槽中属于同一对象或指标的一组“主信息 + 辅助信息”。尾部可显示语义图标，或由主信息驱动的
真实占比圆环，但不承载动作；
完整业务区、两个同级指标和无主辅关系的字段不使用。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `primaryText` | 显示值 | 静态 / Expression / PathBinding | 必填 |
| `secondaryText` | 显示值 | 静态 / Expression / PathBinding | 必填；与主信息属于同一对象或指标 |
| `unit` | string | 仅静态 | 可选；主信息未包含单位时使用 |
| `fontColor` | `#AARRGGBB` | 仅静态 | 必填 |
| `backgroundColor` | `#AARRGGBB` | 仅静态 | 必填 |
| `variant` | string | 仅静态 | 按尺寸文件填写；2x2 可省略，2x4 必填 |
| `visual` | object | 仅静态 | 可选；`{type:"icon",icon,color?:"native"}` 或 `{type:"progressCircle",icon}` |
| `fillColor` | `#AARRGGBB` | 仅静态 | 可选；用于可染色 visual 图标 |

#### 槽位与容量

每个合法固定槽只放一个 `InfoBlock`，两行文字必须保持单行。尺寸、variant 和文字区宽度由尺寸文件规定；
必要值放不下时先取消可选图标，仍不成立则改用其它组件组合。

#### 示例

```genui
["battery","InfoBlock",{"variant":"slot","primaryText":{"path":"/data/phoneBattery/batterySOC"},"unit":"%","secondaryText":{"path":"/data/phoneBattery/chargingStatusDesc"},"visual":{"type":"progressCircle","icon":"resources/base/media/battery_leaf_fill.svg"},"fontColor":"#FF1F4799","backgroundColor":"#99FFFFFF"}]
```

#### 注意事项

visual 不是装饰；`progressCircle` 只用于可验证的 `0–100` 主值。没有准确 visual 时不生成尾部空槽；
外层和内部均不得写 `onClick`。

### 5.9 `TableText`

#### 选择条件

用于同一主题下 2–3 项同级“标签—值”。单项信息、唯一核心值、事件时间线和比例关系不使用。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `items` | Array | 数组结构仅静态 | 必填；2–3 项，每项只含 `label`、`value` |
| `items[].label` | 显示值 | 静态 / Expression / PathBinding | 必填；非空标签 |
| `items[].value` | 显示值 | 静态 / Expression / PathBinding | 必填；真实可见值 |
| `fontColor` | `#AARRGGBB` | 仅静态 | 必填 |

#### 槽位与容量

两种尺寸共用。两行最小高度 `34vp`，三行 `52vp`；只进入尺寸文件允许且能完整容纳所有行的连续内容槽。

#### 示例

```genui
["metrics","TableText",{"items":[{"label":"紫外线","value":{"path":"/data/weatherHealth/ultravioletLevel"}},{"label":"空气质量","value":{"path":"/data/weatherHealth/airQualityLevel"}}],"fontColor":"#FF1F4799"}]
```

#### 注意事项

每项只表达一个事实；不把同一个值同时作为核心读数和表格项。

### 5.10 `SummaryList`

#### 选择条件

用于 2–3 条同级、可单行完整显示的短摘要。长正文、标签—值或存在主次关系的内容不使用。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `items` | 显示值数组 | 数组结构仅静态；每项可静态 / Expression / PathBinding | 必填；2–3 条显示值 |
| `fontColor` | `#AARRGGBB` | 仅静态 | 必填 |
| `backgroundColor` | `#AARRGGBB` | 仅静态 | 必填 |

#### 槽位与容量

合同在本文件定义，当前只进入 2x4 `W-top-bottom` 的列表明细槽；每项固定为一个单行背板。

#### 示例

```genui
["list","SummaryList",{"items":[{"path":"/data/calendar/events/0/title"},{"path":"/data/calendar/events/1/title"},{"path":"/data/calendar/events/2/title"}],"fontColor":"#FF8C4B1C","backgroundColor":"#99FFFFFF"}]
```

#### 注意事项

条目不嵌套标签、图标或按钮；超出三条时按信息优先级取舍或改选布局，不使用动态数组模板。

## 6. 进度与占比组件

进度组件默认不生成。只有字段描述明确表示占比、完成度、使用率、电量等比例语义，并且范围可验证时才允许；
温度、日期、时间、时长、倒计时、状态、名称和普通数值不使用。完整数值百分比字符串可直接作为比例输入，
但不从包含其它正文的字符串中截取数字或猜测范围。

### 6.1 `ProgressCircle`

#### 选择条件

用于两个或四个同级对象的真实 `0–100` 占比，每个对象必须有能准确区分它的环心图标。单个占比及
右侧说明使用 `ProgressCircleSingle`；无可靠范围、普通绝对量或没有准确图标时使用文本组件。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `externalText` | number / string / PathBinding | 静态 / PathBinding；不接受 Expression | 必填；`0–100` 数值、纯数值字符串或完整百分比字符串；绑定字段样例也须满足该格式 |
| `icon` | string | 仅静态 | 必填；逐字使用当前素材候选路径 |
| `accessibility` | object | 仅静态 | 必填；包含非空 `label`，可选 `description` |
| `width`、`height` | number | 仅静态 | 必填；按当前槽位填写正数 vp |
| `fontColor` | `#AARRGGBB` | 仅静态 | 必填；环外读数颜色 |
| `color` | `#AARRGGBB` | 仅静态 | 必填；完成轨道颜色 |
| `backgroundColor` | `#AARRGGBB` | 仅静态 | 必填；未完成轨道颜色 |
| `fillColor` | `#AARRGGBB` | 仅静态 | 可选；单色环心图标颜色 |

#### 槽位与容量

组件内部固定为正圆进度环、`20×20vp` 环心图标和环外读数；合法数量、外框和槽位由尺寸文件规定。

#### 示例

```genui
["ratio","ProgressCircle",{"externalText":{"path":"/data/device/batteryPercent"},"icon":"resources/base/media/battery_leaf_fill.svg","accessibility":{"label":"设备电量百分比"},"width":52,"height":68,"fontColor":"#FF1F4799","fillColor":"#991F4799","color":"#FF1F4799","backgroundColor":"#331F4799"}]
```

#### 注意事项

`externalText` 同时驱动圆环和环外读数；不传 `value`、`total`、`type`、`strokeWidth`、`size` 或 children。

### 6.2 `ProgressLine2`

#### 选择条件

用于当前数值相对明确总量的真实线性进度，并同时展示可见读数。没有真实分母、总量或比例关系时不使用；
仅因为内容含 `%` 不自动成为进度。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `value` | number / string / PathBinding | 静态 / PathBinding；不接受 Expression | 必填；数值、纯数值字符串或完整百分比字符串；百分比字符串按 `total` 等比换算 |
| `total` | number | 仅静态 | 必填；正数 |
| `displayValue` | 显示值 | 静态 / Expression / PathBinding | 必填；与 `value/total` 表达同一事实 |
| `unit` | string | 静态 / Expression / string PathBinding | 可选；读数未包含单位时填写 |
| `fontColor`、`color`、`backgroundColor` | `#AARRGGBB` | 仅静态 | 必填 |

#### 槽位与容量

合同在本文件定义，当前只进入 2x4 组件文件允许的连续内容槽。

#### 示例

```genui
["score","ProgressLine2",{"value":{"path":"/data/healthSport/sleepScore"},"total":100,"displayValue":{"path":"/data/healthSport/sleepScore"},"unit":"分","fontColor":"#FF563D99","color":"#FF563D99","backgroundColor":"#33563D99"}]
```

#### 注意事项

`value`、`total` 和 `displayValue` 必须属于同一进度关系；`value` 只接受纯数值或完整百分比字符串，
不能从包含标签、单位说明或其它正文的字符串中截取数字。

### 6.3 `ProgressCircleSingle`

#### 选择条件

用于一个具有真实比例范围的环形主指标，环心显示对象图标，右侧显示标签、读数和可选状态。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `value` | number / string / PathBinding | 静态 / PathBinding；不接受 Expression | 必填；数值、纯数值字符串或完整百分比字符串；百分比字符串按 `total` 等比换算 |
| `total` | number | 仅静态 | 必填；正数 |
| `icon` | string | 仅静态 | 必填；逐字使用当前素材候选路径 |
| `displayValue` | 显示值 | 静态 / Expression / PathBinding | 必填；与环形进度表达同一数值 |
| `label` | 显示值 | 静态 / Expression / PathBinding | 必填；非空说明 |
| `secondaryLabel` | 显示值 | 静态 / Expression / PathBinding | 可选；同一对象的一条状态说明 |
| `fontColor`、`color`、`backgroundColor` | `#AARRGGBB` | 仅静态 | 必填 |

#### 槽位与容量

两种尺寸共用。2x2 使用普通规格，2x4 使用 compact 规格；合法槽位与高度预算由尺寸文件规定。

#### 示例

```genui
["main","ProgressCircleSingle",{"value":{"path":"/data/phoneBattery/batterySOC"},"total":100,"icon":"resources/base/media/battery_leaf_fill.svg","displayValue":{"path":"/data/phoneBattery/batterySOCText"},"label":"手机电量","secondaryLabel":{"path":"/data/phoneBattery/chargingStatusDesc"},"fontColor":"#FF1F4799","color":"#FF1F4799","backgroundColor":"#331F4799"}]
```

#### 注意事项

`value`、`displayValue` 与 `secondaryLabel` 必须属于同一对象；图标只标识对象，不代替可见读数。

### 6.4 `H_BarChart`

#### 选择条件

用于比较 2–3 个对象的同一指标，尤其是需要看出大小、排序或差异时。单个值、不同量纲或没有可靠换算尺度
的数据不使用，也不退化成缺少比较视觉的普通文本。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `items` | Array | 数组结构仅静态 | 必填；2–3 项，每项只含 `label`、`valueUnit`、`percent` |
| `items[].label` | string | 仅静态 | 必填；对象标签 |
| `items[].valueUnit` | 显示值 | 静态 / Expression / PathBinding | 必填；真实可见值 |
| `items[].percent` | number | 仅静态 | 必填；`0–100`，按同一尺度决定柱长 |
| `fontColor`、`barColor`、`trackColor` | `#AARRGGBB` | 仅静态 | 必填 |

```genui
["energy_compare","H_BarChart",{"items":[{"label":"客厅","valueUnit":{"path":"/data/energy/livingText"},"percent":80},{"label":"书房","valueUnit":{"path":"/data/energy/studyText"},"percent":45}],"fontColor":"#FF1F4799","barColor":"#FF1F4799","trackColor":"#331F4799"}]
```

### 6.5 `NumericRatioStack`

#### 选择条件

用于恰好三个同级对象的紧凑占比或带单位数值，三个对象必须各有准确图标。对象名称不能塞进 `value`；
没有可靠图标或项数不是三时使用其它组件。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `items` | Array | 数组结构仅静态 | 必填；恰好三项 |
| `items[].icon` | string | 仅静态 | 必填；逐字使用当前素材候选路径 |
| `items[].value` | 显示值 | 静态 / Expression / PathBinding | 必填；真实可见数值 |
| `items[].unit` | string | 仅静态 | 可选；完整值已含单位时不得重复 |
| `direction` | `row` / `column` | 仅静态 | 可选；默认 `column` |
| `fontColor`、`fillColor` | `#AARRGGBB` | 仅静态 | 必填 |

```genui
["storage_ratio","NumericRatioStack",{"direction":"column","items":[{"icon":"resources/base/media/externaldrive_fill.svg","value":{"path":"/data/storage/nodeA/usedPercent"},"unit":"%"},{"icon":"resources/base/media/earphone_case_16644.svg","value":{"path":"/data/storage/nodeB/usedPercent"},"unit":"%"},{"icon":"resources/base/media/l_circle_fill.svg","value":{"path":"/data/storage/nodeC/usedPercent"},"unit":"%"}],"fontColor":"#FF1F4799","fillColor":"#FF1F4799"}]
```

## 7. 日程组件

### 7.1 `EventCard`

#### 选择条件

用于 1–2 个按时间排列、各自具有标题和时间的事件，可带地点。一张卡最多生成一个 `EventCard`；两项必须
放在同一个实例中并按时间排序。普通时间属性不使用，也不把事件拆成普通文本绕过容量。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `items` | Array | 数组结构仅静态 | 必填；1–2 项 |
| `items[].title` | 显示值 | 静态 / Expression / PathBinding | 必填；事件标题 |
| `items[].time` | 显示值 | 静态 / Expression / PathBinding | 必填；事件时间 |
| `items[].location` | 显示值 | 静态 / Expression / PathBinding | 可选；事件地点 |
| `density` | `compact` | 仅静态 | 可选；两项普通高度放不下时使用 |
| `fontColor` | `#AARRGGBB` | 仅静态 | 必填 |

#### 槽位与容量

两种尺寸共用，进入尺寸文件允许的连续内容槽；一个组件承载 1–2 个事件，所属动作放在独立操作组件中。

#### 示例

```genui
["content_area","EventCard",{"items":[{"title":{"path":"/data/calendar/events/0/title"},"time":{"path":"/data/calendar/events/0/dtStart"},"location":{"path":"/data/calendar/events/0/location"}},{"title":{"path":"/data/calendar/events/1/title"},"time":{"path":"/data/calendar/events/1/dtStart"}}],"density":"compact","fontColor":"#FF8C4B1C"}]
```

#### 注意事项

组件已包含时间线和文字列，不再手写时间线轨道或重复标题、时间内容。兼容旧的单事件
`title/time/location` 输入，但新生成统一使用 `items`。

## 8. 操作组件

### 8.1 `PillButton`

#### 选择条件

用于需要显示明确动作文字的内容区操作。只有当前事件候选提供匹配动作时使用；合法操作位由尺寸文件规定。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `label` | string | 仅静态 | 必填；非空动作文字 |
| `onClick` | EventHandler[] | 事件参数按事件 schema | 必填；恰好一个当前事件候选中的 handler |
| `actionSurface` | `#AARRGGBB` | 仅静态 | 必填；按钮背景色 |
| `actionInk` | `#AARRGGBB` | 仅静态 | 必填；文字与单色图标颜色 |
| `icon` | string | 仅静态 | 可选；逐字使用当前素材候选路径 |
| `fontSize` | number | 仅静态 | 可选；只允许 `14` |
| `fontWeight` | number | 仅静态 | 可选；只允许 `400` 或 `500` |
| `width` | number / `matchParent` | 仅静态 | 可选；按尺寸文件合法槽位填写 |

#### 槽位与容量

固定高 `36vp`、圆角 `30vp`。2x2 用于底部文字操作；2x4 用于完整内容区的直属操作，不进入固定模块槽。

#### 示例

```genui
["cta","PillButton",{"label":"蓝牙设置","actionSurface":"#331F4799","actionInk":"#FF1F4799","fontSize":14,"fontWeight":400,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"bluetooth_entry"}}]}]
```

#### 注意事项

一个实例只绑定一个动作，同一动作只保留一个入口。有 icon 时由 Recipe 生成图标与文字，不手写相同按钮皮肤；
完整标签放不下时更换布局，不裁切、不缩小 Recipe，也不回退为基础 `Button`。

## 9. 选择检查

- 组件内容结构与真实信息关系一致，没有为了使用组件而合并无关字段或补造信息。
- 每个组件只使用自身属性表中的 Props；视觉 Recipe 组件只额外使用允许的外部布局字段。
- 组件进入当前尺寸文件允许的槽位，项目数、文字长度、固定高度和 `InfoBlock.variant` 均符合容量。
- 进度组件绑定真实数值字段或完整数值百分比字符串，并具有可验证的比例、总量或范围。
- 同一事实和同一动作没有在多个组件中重复表达。
- 内容超出固定容量时更换组件或布局，不通过覆盖内部样式、裁切或隐藏必要信息交付。
<!-- /prompt:catalog -->
