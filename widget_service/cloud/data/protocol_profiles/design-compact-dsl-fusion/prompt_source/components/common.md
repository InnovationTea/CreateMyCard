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
| 正文与补充 | `SecondaryBody` | 1–4 个正文、metadata 或短说明项 | 补充同区已经存在的核心信息 | 不得独立存在；同组多项放入一个实例并按单行／多行选择固定字号 |
| 核心信息 | `DataDisplay` | 标签 + 主值 + 支撑文本 | 2x2 完整单焦点 | 三项各一行；不吸收动作、第二指标或独立补充 |
| 紧凑信息 | `InfoBlock` | 主信息 + 辅助信息 + 可选图标或占比圆环 | 固定小槽中的完整主辅信息 | 每槽一个；不支持事件 |
| 多项属性 | `TableText` | 多行标签—值 | 同一主题的 2–3 项属性 | 两种尺寸共用；进入连续内容槽 |
| 摘要列表 | `SummaryList` | 2–3 条同级摘要 | 2x4 短列表 | 每项固定单行显示 |
| 占比 | `ProgressCircle` | 环心图标 + 环外读数 | 两个或四个同级对象的真实占比 | 每个实例表达一个 `0–100` 比例 |
| 线性进度 | `ProgressLine2` | 可见读数 + 线性进度 | 当前值相对明确总量 | 当前只用于 2x4 连续内容区 |
| 比较 | `H_BarChart` | 2–3 组标签、值和横向柱 | 比较多个对象的同一指标 | 不比较不同量纲 |
| 环形进度 | `ProgressCircleSingle` | 单环 + 右侧读数组 | 单个真实比例及同对象说明 | 两种尺寸共用；规格由尺寸文件决定 |
| 占比摘要 | `NumericRatioStack` | 三组图标 + 数值 + 单位 | 三个同级对象的紧凑占比 | 必须恰好三项且图标可区分 |
| 日程 | `EventCard` | 时间线 + 一个或多个事件 | 两种尺寸的连续日程内容 | 全部事件按时间排序并放在同一实例，按实际总高验算容量 |
| 操作 | `PillButton` | 操作文案 + 可选图标 | 两种尺寸内容区内的直属操作 | 一个实例绑定一个真实动作 |
| 操作 | `CircleButton` | 纯图标操作 | 2x2 右下锚点操作 | 2x2 专属；合同见 `components/2x2.md` |
| 等权指标 | `TopTextBottomValue` | 三组标签—数值—单位 | 2x4 三个同级指标 | 2x4 专属；合同见 `components/2x4.md` |
| 明细信息 | `TextBlock` | 2–4 组标签—值背板 | 2x4 同级详情 | 2x4 专属；合同见 `components/2x4.md` |
| 操作 | `CardButton` | 文案 + 可选图标 | 2x4 固定动作槽 | 2x4 专属；合同见 `components/2x4.md` |

### 1.1 关键选择边界

1. 每个语义分区最多使用一个 `SingleLineTitle`；2x4 左右独立分区可分别使用。标题加次信息使用 `DoubleLineTitle`，标题关联真实数量才使用 `Badge`；标题不用正文组件代替。
2. 先按信息语义和字段关系保留可行组件，再结合尺寸文件的槽位与容量确定最终组件；不为使用组件补造字段。
3. 有唯一核心值时使用一个强调或进度组件；没有真实主次时保持并列，不把普通数字强行放大为核心。
4. 完整单焦点使用 `DataDisplay`；核心加独立补充使用一个核心组件与一个 `SecondaryBody`，同一对象或同一集合的 2–4 个短补充字段合并到该实例的 `items`，不拆成多个单项实例。`SecondaryBody` 只能辅助同一语义分区内的核心信息组件，不能成为分区内唯一的信息组件；标题、按钮、布局容器和其它 `SecondaryBody` 都不满足搭配条件。只有无核心且用户明确要求逐项查看、对比或等权汇总时才使用 `TableText`。2x4 横向详情选择 `TextBlock` 或 `TopTextBottomValue`。
5. 单占比使用 `ProgressCircleSingle`；两个或四个同级占比使用多个 `ProgressCircle`；三个图标可区分的同级占比使用 `NumericRatioStack`；明确目标差距使用 `ProgressLine2`；2–3 个对象同指标比较使用 `H_BarChart`。
6. 一个或多个按时间排列的事件使用一个 `EventCard`；普通时间属性使用 `SecondaryBody`。同一事实只展示一次，事件数量不设固定上限但必须通过实际容量预算。
7. 动作按槽位选择 `PillButton`、`CircleButton` 或 `CardButton`，只能绑定当前事件候选，不伪造操作。
8. 模型只输出总表及尺寸文件登记的语义组件；`Text` 仅由转换器展开为 A2UI 基础节点。
9. 每个组件只使用自身属性表声明的 Props 与绑定能力；选型、容量和槽位以对应组件合同为准。
<!-- /prompt:selection -->

<!-- prompt:catalog -->
# 2. Compact DSL 组件合同

只允许三种基础布局组件：`Row`、`Column`、`Stack`。

除基础布局组件外，只允许：`SingleLineTitle`、`DoubleLineTitle`、`Badge`、
`EmphasizedData`、`EmphasisText`、`SecondaryBody`、`DataDisplay`、`InfoBlock`、`TableText`、`SummaryList`、
`ProgressCircle`、`ProgressLine2`、`H_BarChart`、`ProgressCircleSingle`、`NumericRatioStack`、
`EventCard`、`PillButton`，以及尺寸文件登记的 `CircleButton`、`TopTextBottomValue`、`TextBlock`、`CardButton`。

## 2.1 组件共同规则

- 组件行的语义字段和样式字段直接写在第三项 `props`，不用的字段省略，不嵌套 `styles`。
- 只有 `Row`、`Column`、`Stack` 在第 4 项声明非空 `children`；其它组件均只输出一行且不带 children。
- 布局组件只能使用各自章节列出的字段。使用视觉 Recipe 的组件只能使用自身属性表，
  并可额外使用 `width`、`height`、`layoutWeight`、`flexShrink`、`margin` 调整组件根的外部布局。
- `PillButton` 不使用上述 `width` 例外；其宽度固定由所在动作槽和 Recipe 撑满。
- 视觉 Recipe 组件不接受 `padding`、圆角、内部间距或对齐覆盖；本文件标有 `fontSize` 的文本组件在新生成时
  必须显式写出固定主字号，帮助布局预算，但该值必须等于 Recipe，不是可调样式。内部次级字号、结构和样式仍由转换器确定。
- 组件不声明文字颜色；转换器根据 root 背景解析主色、辅助色等语义色板角色，并按组件 Recipe 注入。
  自定义背景同样由运行时选择具有足够对比度的文字角色，不在组件 Props 中重复指定颜色。
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
`justifyContent` 使用 `spaceAround|spaceBetween|spaceEvenly` 时，`itemMargin` 仍是必须保留的最小间距；
两者可以同时设置，但只能把扣除最小间距后的非负剩余空间交给分布式对齐。
同一行不同字号的文字采用`Row alignItems="bottom"`底部对齐，2x2与2x4都遵守；语义组件内部由转换器统一执行，
不手写Text或覆盖组件内部padding。数值与真实单位保留各自固定字号并紧邻，不把单位居中悬在大字旁。

### 3.2 `Column`

用于纵向排列有先后层级的子组件。第 4 项 `children` 必填；`itemMargin` 可选数字 vp，`space` 是兼容别名。
`justifyContent` 与 Row 相同，`alignItems` 只取 `start|center|end`，可使用与 Row 相同的布局与表面字段。
子组件高度、padding 与最小间距之和必须不超过父高；`layoutWeight` 和 `flexShrink` 不抵消真实最小高度。
`justifyContent` 使用分布式对齐时同样先扣除 `itemMargin`，不能依赖它消除负剩余空间。

### 3.3 `Stack`

只用于背景与前景、图标底板等真实叠放。第 4 项 `children` 必填；`alignContent` 只取
`topStart|top|topEnd|start|center|end|bottomStart|bottom|bottomEnd`。可使用与 Row 相同的布局与表面字段，
但不使用 `itemMargin`、`justifyContent` 或 `alignItems`。进度组件已包含内部结构，不再手写内部 Stack。

## 4. 文本与信息组件

本节组件使用视觉 Recipe，只能使用自身属性表和 2.1 允许的外部布局字段。

### 4.1 `SingleLineTitle`

#### 选择条件

用于简短的静态分区标题，或由一个字段直接承担的对象名、地点名、设备名。每个语义分区最多一个；
2x4 左右独立分区可分别使用。数值、状态、日期时间和动作不用作标题，也不用正文组件重造标题。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `title` | 显示值 | 静态 / Expression / PathBinding | 必填；非空单行标题 |
| `icon` | string | 仅静态 | 条件必选；按钮完成图标分配后，仍有与标题或卡片主题语义匹配且未被按钮使用的静态图标时默认填写；不可点击 |
| `fillColor` | color | 仅静态 | 仅兼容历史 SVG 输入，新生成不填；运行时固定覆盖为当前色板 `graphicPrimary`；位图图标不得填写 |
| `fontSize` | number | 仅静态 | 新生成必填；固定 `12`，不允许修改 |

#### 槽位与容量

无 `icon` 时占高 `12vp`，与内部 `12fp/400` 单行文字一致，不额外保留上下 padding；有 `icon` 时占高 `20vp`，
图标固定右对齐为 `20×20vp`，标题在剩余宽度内单行省略。图标用于补充标题或卡片主题语义；
先为 `PillButton` 和 `CircleButton` 分配动作图标，再从按钮未使用的候选中为标题选择语义匹配图标；
按钮与标题不得复用同一素材，但可以使用不同素材。
进入卡级或分区标题位置；
2x4 左右分区各自预算成立时可各放一个，具体宽度和合法位置由尺寸布局文件规定。

#### 示例

```genui
["header","SingleLineTitle",{"title":"天气","icon":"resources/base/media/weather.png","fontSize":12}]
```

#### 注意事项

标题固定左对齐 `12fp/400`；有图标时文字与右侧图标共同构成标题区。动作按钮分配后仍有语义匹配且未使用的静态素材时默认填写 `icon`；
SVG 标题图标由运行时使用 100% 不透明的主图形色，不由模型选择透明度；
`fontSize:12` 只声明固定主字号，不覆盖 Recipe。

### 4.2 `DoubleLineTitle`

#### 选择条件

用于标题区域中紧密相关的“对象名称 + 状态／地点”。只有一层标题时使用 `SingleLineTitle`，不能把两个独立主题
塞入一个双层标题。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `title` | 显示值 | 静态 / Expression / PathBinding | 必填；最多一行 |
| `secondaryInfo` | 显示值 | 静态 / Expression / PathBinding | 必填；最多两行 |
| `fontSize` | number | 仅静态 | 新生成必填；主标题和次信息均固定 `12` |

#### 槽位与容量

进入标题位置；主标题 `12fp/700`，次信息 `12fp/500`。它比 `SingleLineTitle` 占用更多高度，主体容量不足时改用
单行标题或更宽内容区。

```genui
["device_title","DoubleLineTitle",{"title":{"path":"/data/sensor/displayName"},"secondaryInfo":{"path":"/data/sensor/connectionStatus"},"fontSize":12}]
```

### 4.3 `Badge`

#### 选择条件

仅用于标题明确命名同一集合、且存在真实数量字段的“标题 + 数量”组合。状态、温度、时长、百分比和普通核心值
不使用；数量是唯一核心信息时使用内容组件。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `value` | 显示值 | 静态 / Expression / PathBinding | 必填；短数量或 `99+` |
| `backgroundColor` | `#AARRGGBB` | 仅静态 | 必填 |

#### 槽位与容量

不能单独进入标题位或内容位；必须紧跟标题组件，共同放入标题 Row。数量在整卡只表达一次。

```genui
["event_count","Badge",{"value":{"path":"/data/calendar/eventCount"},"backgroundColor":"#338C4B1C"}]
```

### 4.4 `EmphasizedData`

#### 选择条件

用于一个内容区中唯一需要突出的核心数值或单一测量读数。多个同级指标和普通文本结论不使用。
普通状态、名称、日期等明确非量化内容使用文本组件；数字字符串、单一带单位测量读数和合法绑定、
Expression 仍按原合同使用，不根据字段类型为 string 就改写或截取内容。
完整多段时长（如“7小时1分”）包含多个数量与单位，属于文本读数：作为主信息使用
`EmphasisText.mainText` 的固定18fp规格，作为辅助信息使用原正文角色，不把整串放入30fp的value。
保留完整原绑定，不截取样例数字、不伪造分段字段、不重复或删除单位。纯数字主值规格不变。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `value` | 显示值 | 静态 / Expression / PathBinding | 必填；一个核心值 |
| `unit` | string | 静态 / Expression / string PathBinding | 可选；只绑定或填写单位文本 |
| `fontSize` | number | 仅静态 | 新生成必填；核心值固定 `30`；单位仍由 Recipe 固定为 `12` |

#### 槽位与容量

只承载一个核心值；合法槽位和宽度由当前尺寸文件规定，不吸收标题、辅助信息或第二指标。

#### 示例

```genui
["reading","EmphasizedData",{"value":{"path":"/data/healthSport/sleepScore"},"unit":"分","fontSize":30}]
```

#### 注意事项

值已包含单位时不再传 `unit`；不把多个同级值拼进一个 `value`。

### 4.5 `EmphasisText`

#### 选择条件

用于一个分区最重要的文本结论、类别或状态。次文本只补充同一个核心语义；数值核心使用
`EmphasizedData`，事件、进度或比较保持专用组件。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `mainText` | 显示值 | 静态 / Expression / PathBinding | 必填；核心文本 |
| `secondaryText` | 显示值 / PathBinding[] | 静态 / Expression / PathBinding；多源时使用至少 2 个有序 PathBinding | 可选；同一语义的一条短补充；数组由转换器按顺序以 ` | ` 连接 |
| `fontSize` | number | 仅静态 | 新生成必填；主文本固定 `18`；次文本仍由 Recipe 固定为 `12` |

```genui
["connection","EmphasisText",{"mainText":{"path":"/data/earphone/connectionStatus"},"secondaryText":{"path":"/data/earphone/name"},"fontSize":18}]
```
多个紧密关联的短字段共同组成次文本时，直接按显示顺序绑定；每个字段仍会独立响应数据更新：

```genui
["weather","EmphasisText",{"mainText":{"path":"/data/weather/current/condition"},"secondaryText":[{"path":"/data/weather/location/prefectureName"},{"path":"/data/weather/location/districtName"}],"fontSize":18}]
```

上述 `secondaryText` 展开为 `城市值 | 区域值`。需要为各值增加静态标签时，改用包含全部绑定的完整
Expression；`mainText` 不接受数组，互不相关或需要逐项标签的多个字段改用 `SecondaryBody` 或 `TableText`。


### 4.6 `SecondaryBody`

#### 选择条件

只用于补充同一分区已经存在的核心信息，例如辅助正文、普通时间、来源、更新时间或弱提示；不得独立作为
该分区的唯一信息组件。标题、Badge、按钮、布局容器和其它 `SecondaryBody` 都不算核心组件。正文自身是主要
结论时使用 `EmphasisText`，不能用 `SecondaryBody` 规避核心选型。组件不区分 role，单项和多项均写入
`items`；同一对象或同一集合的多个短字段按原顺序放入一个实例，不得按日期、对象索引或字段逐项拆成多个
单项 `SecondaryBody`，也不得为使用较小字号或规避容量校验而拆分。只有无核心且用户明确要求逐项查看、
对比或等权汇总的标签—值表才使用 `TableText`；事件、比较和进度仍使用对应语义组件。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `items` | Array | 数组结构仅静态 | 必填；1–4 项 |
| `items[].value` | 显示值 | 静态 / Expression / PathBinding | 必填；保留完整值和单位 |
| `items[].label` | string | 仅静态 | 可选；短标签 |
| `items[].maxLines` | number | 仅静态 | 可选；`1|2`，默认 1；两行时必须预留高度 |
| `columns` | number | 仅静态 | 可选；`1|2`，默认 2；1 表示每项独占一行 |
| `separator` | string | 仅静态 | 可选；同一行相邻项默认用 ` | ` 分隔，跨行不加分隔符 |
| `fontSize` | number | 仅静态 | 新生成必填；整组单行固定 `14`，多行固定 `12` |

#### 槽位与容量

按行布局选择规格：只有一行且每项 `maxLines:1` 时为 `14fp/400`、行高 `19vp`；
超过一行或任一项使用 `maxLines:2` 时，整组为 `12fp/400`、行高 `16vp`。
两项同行用 14；两项 `columns:1` 分行用 12，不能只按项目数判断。
每行最多两项，行间距固定 2；总高度为各行最大 `maxLines × 行高` 之和加行间距。
文字放不下时使用单列或合法两行，并同步字号与高度预算；不裁切、删单位或手动缩字。
标签保留自然宽度，值承接剩余宽度；长标签可与值合并到同项完整 Expression，保留原始绑定。
不输出 `role`，不覆盖内部字重、padding 或对齐。

```genui
["description","SecondaryBody",{"items":[{"value":{"path":"/data/weather/description"},"maxLines":2}],"fontSize":12}]
["updated","SecondaryBody",{"items":[{"value":"{{ '更新 ' + ${/data/weather/updatedAt} }}"}],"fontSize":14}]
["sleep_detail","SecondaryBody",{"items":[{"label":"夜间睡眠 ","value":{"path":"/data/healthSport/nightSleepDurationText"}},{"label":"午睡 ","value":{"path":"/data/healthSport/napDurationText"}}],"separator":" | ","fontSize":14}]
```

以上仅展示组件属性写法；放入完整卡片时，每个实例都必须与同一语义分区内的核心信息组件搭配。

### 4.7 `DataDisplay`

#### 选择条件

用于 2x2 无动作的完整单焦点：一个短标签、一个唯一核心读数或短文本结论，以及一条单位、更新时间等
紧密支撑。地点、备注、另一指标等能够独立回答问题的字段属于独立补充，此时改用核心组件加
`SecondaryBody`，不使用 `DataDisplay`。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `label` | string | 仅静态 | 必填；非空短文本 |
| `value` | 显示值 | 静态 / Expression / PathBinding | 必填；唯一核心读数或短文本结论 |
| `supportingText` | 显示值 | 静态 / Expression / PathBinding | 必填；单位、更新时间或短说明 |
| `fontSize` | number | 仅静态 | 新生成必填；数值核心固定 `56`，短文本结论固定 `18`；标签和支撑文本仍由 Recipe 固定为 `12/14` |

#### 槽位与容量

合同在本文件定义，当前只进入 2x2 `S-center` 的唯一内容区；具体几何由 `components/2x2.md` 规定。

#### 示例

```genui
["display","DataDisplay",{"label":"运动会倒计时","value":{"path":"/data/countdown/countdownDays"},"supportingText":"天","fontSize":56}]
```

#### 注意事项

值已包含完整单位时改用其他合适组件，不重复单位。

### 4.8 `InfoBlock`

#### 选择条件

用于固定或有明确高度的小槽中属于同一对象或指标的一组“主信息 + 辅助信息”。尾部可显示语义图标，或由主信息驱动的
真实占比圆环，但不承载动作；
完整业务区、两个同级指标和无主辅关系的字段不使用。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `primaryText` | 显示值 | 静态 / Expression / PathBinding | 必填 |
| `secondaryText` | 显示值 | 静态 / Expression / PathBinding | 必填；与主信息属于同一对象或指标 |
| `unit` | string | 仅静态 | 可选；主信息未包含单位时使用 |
| `backgroundColor` | `#AARRGGBB` | 仅静态 | 必填 |
| `variant` | string | 仅静态 | 按尺寸文件填写；2x2 可省略，2x4 必填 |
| `visual` | object | 仅静态 | 可选；`{type:"icon",icon,color?:"native"}` 或 `{type:"progressCircle",icon}` |
| `fillColor` | `#AARRGGBB` | 仅静态 | 可选；用于可染色 visual 图标 |

#### 槽位与容量

每个合法小槽只放一个 `InfoBlock`，两行文字必须保持单行。尺寸、variant 和文字区宽度由尺寸文件规定；
必要值放不下时先取消可选图标，仍不成立则改用其它组件组合。

#### 示例

无尾部视觉时，只输出同一对象的一组主辅信息。2x2 可省略 `variant`：

```genui
["weather","InfoBlock",{"primaryText":{"path":"/data/weather/current/temperatureText"},"secondaryText":{"path":"/data/weather/current/condition"},"backgroundColor":"#CCFFFFFF"}]
```

2x2 保留卡级标题并展示两个同级子对象时，可在 `S-title-dual-content` 的两个 `126×50vp` 槽中各放一个
无 visual 的紧凑 `InfoBlock`。短静态对象标签可以和一个动态值组成完整 Expression，用来区分同级对象：

```genui
["tomorrow","InfoBlock",{"variant":"stacked","width":"matchParent","height":50,"primaryText":"{{ '明天 ' + ${/data/weather/daily/1/condition} }}","secondaryText":"{{ '空气质量 ' + ${/data/weather/daily/1/airQuality} }}","backgroundColor":"#CCFFFFFF"}]
```

有准确语义图标时使用 `visual.type:"icon"`。Compact DSL 直接绑定真实路径，不使用 `dataIds` 或
`primaryTextTemplate`；需要静态标签时改用只包含一个动态绑定的完整 Expression：

```genui
["sleep","InfoBlock",{"variant":"slot","primaryText":{"path":"/data/healthSport/sleepScore"},"unit":"分","secondaryText":"{{ '状态 ' + ${/data/healthSport/sleepStatus} }}","visual":{"type":"icon","icon":"resources/base/media/moon_z_fill_1.svg"},"fillColor":"#991F4799","backgroundColor":"#99FFFFFF"}]
```

主信息是可验证的 `0–100` 数值时，才可使用 `visual.type:"progressCircle"`。原始数值绑定和单位必须分开：

```genui
["battery","InfoBlock",{"variant":"slot","primaryText":{"path":"/data/phoneBattery/batterySOC"},"unit":"%","secondaryText":{"path":"/data/phoneBattery/chargingStatusDesc"},"visual":{"type":"progressCircle","icon":"resources/base/media/battery_leaf_fill.svg"},"fillColor":"#991F4799","backgroundColor":"#99FFFFFF"}]
```

#### 注意事项

visual 不是装饰；`progressCircle` 只用于可验证的 `0–100` 主值。没有准确 visual 时不生成尾部空槽；
每行只承载一个动态业务值，不把第二个动态字段拼入 `primaryText`；同级对象需要区分时允许添加一个简短
静态对象标签，指标名需要帮助理解时允许添加一个简短静态标签。`visual.type:"progressCircle"` 的
`primaryText` 仍必须是原始有限数值或完整百分比，不得添加标签。外层和内部均不得写 `onClick`。

### 4.9 `TableText`

#### 选择条件

用于用户明确要求逐项查看、列表、清单、对比或等权汇总，且同一主题下不存在可识别核心信息的
2–3 项同级“标签—值”。字段数量多或可写成键值对不能单独作为选用依据；单项信息、核心加补充、
事件时间线和比例关系不使用。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `items` | Array | 数组结构仅静态 | 必填；2–3 项，每项只含 `label`、`value` |
| `items[].label` | 显示值 | 静态 / Expression / PathBinding | 必填；非空标签 |
| `items[].value` | 显示值 | 静态 / Expression / PathBinding | 必填；真实可见值 |
| `fontSize` | number | 仅静态 | 新生成必填；两项固定 `12`，三项固定 `10` |

#### 槽位与容量

两种尺寸共用。两行最小高度 `38vp`（18×2+2），三行 `52vp`（16×3+2×2）；只进入能完整容纳所有行的连续内容槽。
标签使用自然宽度，值占扣除标签和8vp间距后的剩余宽度；不是左右各占一半。两列均为单行，
长标签或完整值仍容不下时，改用 SecondaryBody 单列/两行并重算正文预算，不能截去单位或末尾文字。

#### 示例

```genui
["metrics","TableText",{"items":[{"label":"紫外线","value":{"path":"/data/weatherHealth/ultravioletLevel"}},{"label":"空气质量","value":{"path":"/data/weatherHealth/airQualityLevel"}}],"fontSize":12}]
```

#### 注意事项

每项只表达一个事实；不把同一个值同时作为核心读数和表格项。

### 4.10 `SummaryList`

#### 选择条件

用于 2–3 条同级、可单行完整显示的短摘要。长正文、标签—值或存在主次关系的内容不使用。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `items` | 显示值数组 | 数组结构仅静态；每项可静态 / Expression / PathBinding | 必填；2–3 条显示值 |
| `backgroundColor` | `#AARRGGBB` | 仅静态 | 必填 |

#### 槽位与容量

合同在本文件定义，当前只进入 2x4 `W-top-bottom` 的列表明细槽；每项固定为一个单行背板。

#### 示例

```genui
["list","SummaryList",{"items":[{"path":"/data/calendar/events/0/title"},{"path":"/data/calendar/events/1/title"},{"path":"/data/calendar/events/2/title"}],"backgroundColor":"#99FFFFFF"}]
```

#### 注意事项

条目不嵌套标签、图标或按钮；超出三条时按信息优先级取舍或改选布局，不使用动态数组模板。

## 5. 进度与占比组件

进度组件默认不生成。只有字段描述明确表示占比、完成度、使用率、电量等比例语义，并且范围可验证时才允许；
温度、日期、时间、时长、倒计时、状态、名称和普通数值不使用。完整数值百分比字符串可直接作为比例输入，
但不从包含其它正文的字符串中截取数字或猜测范围。

### 5.1 `ProgressCircle`

#### 选择条件

用于两个或四个同级对象的真实 `0–100` 占比，每个对象必须有能准确区分它的环心图标。单个占比及
右侧说明使用 `ProgressCircleSingle`；无可靠范围、普通绝对量或没有准确图标时使用文本组件。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `externalText` | number / string / Expression / PathBinding | 静态 / Expression / PathBinding | 必填；`0–100` 数值、纯数值字符串、完整百分比字符串，或结果为 `0–100` 数值的完整 Expression；需要环外百分号时可让 Expression 以 `+ '%'` 或 `+ '％'` 结尾 |
| `icon` | string | 仅静态 | 必填；逐字使用当前素材候选路径 |
| `accessibility` | object | 仅静态 | 必填；包含非空 `label`，可选 `description` |
| `width`、`height` | number | 仅静态 | 必填；按当前槽位填写正数 vp |
| `color` | `#AARRGGBB` | 仅静态 | 必填；完成轨道颜色 |
| `backgroundColor` | `#AARRGGBB` | 仅静态 | 必填；未完成轨道颜色 |
| `fillColor` | `#AARRGGBB` | 仅静态 | 使用默认可染色 SVG 时必填；原色 SVG 或 PNG 不填写 |

#### 槽位与容量

组件内部固定为正圆进度环、`20×20vp` 环心图标和环外读数；合法数量、外框和槽位由尺寸文件规定。

#### 示例

```genui
["ratio","ProgressCircle",{"externalText":{"path":"/data/device/batteryPercent"},"icon":"resources/base/media/battery_leaf_fill.svg","accessibility":{"label":"设备电量百分比"},"width":52,"height":68,"fillColor":"#991F4799","color":"#FF1F4799","backgroundColor":"#331F4799"}]
```

#### 注意事项

`externalText` 同时驱动圆环和环外读数。Expression 以 `+ '%'` 或 `+ '％'` 结尾时，转换器确定性拆出前面的
数值表达式驱动圆环，并保留原表达式作为环外读数；其它 Expression 必须直接返回 `0–100` 数值，环外读数由
转换器追加 `%`。不传 `value`、`total`、`type`、`strokeWidth`、`size` 或 children。

### 5.2 `ProgressLine2`

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
| `color`、`backgroundColor` | `#AARRGGBB` | 仅静态 | 必填 |

#### 槽位与容量

合同在本文件定义，当前只进入 2x4 组件文件允许的连续内容槽。

#### 示例

```genui
["score","ProgressLine2",{"value":{"path":"/data/healthSport/sleepScore"},"total":100,"displayValue":{"path":"/data/healthSport/sleepScore"},"unit":"分","color":"#FF563D99","backgroundColor":"#33563D99"}]
```

#### 注意事项

`value`、`total` 和 `displayValue` 必须属于同一进度关系；`value` 只接受纯数值或完整百分比字符串，
不能从包含标签、单位说明或其它正文的字符串中截取数字。

### 5.3 `ProgressCircleSingle`

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
| `color`、`backgroundColor` | `#AARRGGBB` | 仅静态 | 必填 |

#### 槽位与容量

两种尺寸共用。2x2 使用普通规格，2x4 使用 compact 规格；合法槽位与高度预算由尺寸文件规定。

#### 示例

```genui
["main","ProgressCircleSingle",{"value":{"path":"/data/phoneBattery/batterySOC"},"total":100,"icon":"resources/base/media/battery_leaf_fill.svg","displayValue":{"path":"/data/phoneBattery/batterySOCText"},"label":"手机电量","secondaryLabel":{"path":"/data/phoneBattery/chargingStatusDesc"},"color":"#FF1F4799","backgroundColor":"#331F4799"}]
```

#### 注意事项

`value`、`displayValue` 与 `secondaryLabel` 必须属于同一对象；图标只标识对象，不代替可见读数。

### 5.4 `H_BarChart`

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
| `barColor`、`trackColor` | `#AARRGGBB` | 仅静态 | 必填 |

```genui
["energy_compare","H_BarChart",{"items":[{"label":"客厅","valueUnit":{"path":"/data/energy/livingText"},"percent":80},{"label":"书房","valueUnit":{"path":"/data/energy/studyText"},"percent":45}],"barColor":"#FF1F4799","trackColor":"#331F4799"}]
```

### 5.5 `NumericRatioStack`

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
| `fillColor` | `#AARRGGBB` | 仅静态 | 必填 |

```genui
["storage_ratio","NumericRatioStack",{"direction":"column","items":[{"icon":"resources/base/media/externaldrive_fill.svg","value":{"path":"/data/storage/nodeA/usedPercent"},"unit":"%"},{"icon":"resources/base/media/earphone_case_16644.svg","value":{"path":"/data/storage/nodeB/usedPercent"},"unit":"%"},{"icon":"resources/base/media/l_circle_fill.svg","value":{"path":"/data/storage/nodeC/usedPercent"},"unit":"%"}],"fillColor":"#FF1F4799"}]
```

## 6. 日程组件

### 6.1 `EventCard`

#### 选择条件

用于一个或多个按时间排列、各自具有标题和时间的事件，可带地点。一张卡最多生成一个 `EventCard`；多项必须
放在同一个实例中并按时间排序。普通时间属性不使用，也不把事件拆成普通文本绕过容量。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `items` | Array | 数组结构仅静态 | 必填；至少一项；不设固定数量上限，按实际展开高度校验容量 |
| `items[].title` | 显示值 | 静态 / Expression / PathBinding | 必填；事件标题 |
| `items[].time` | 显示值 | 静态 / Expression / PathBinding | 必填；事件时间 |
| `items[].location` | 显示值 | 静态 / Expression / PathBinding | 可选；事件地点 |
| `density` | `compact` | 仅静态 | 可选；多项普通高度放不下时使用 |

#### 槽位与容量

两种尺寸共用，进入尺寸文件允许的连续内容槽；一个组件承载全部同组事件，所属动作放在独立操作组件中。
多项普通模式总高为各项实际高度之和加 `8vp × (items 数量 - 1)`；compact 将相邻项间距收紧为
`4vp`，总高为 `32vp × items 数量 + 4vp × (items 数量 - 1)`。数量放开不豁免父槽与整卡容量校验。

#### 示例

```genui
["content_area","EventCard",{"items":[{"title":{"path":"/data/calendar/events/0/title"},"time":{"path":"/data/calendar/events/0/dtStart"},"location":{"path":"/data/calendar/events/0/location"}},{"title":{"path":"/data/calendar/events/1/title"},"time":{"path":"/data/calendar/events/1/dtStart"}}],"density":"compact"}]
```

#### 注意事项

组件已包含时间线和文字列，不再手写时间线轨道或重复标题、时间内容。兼容旧的单事件
`title/time/location` 输入，但新生成统一使用 `items`。
  `items[].location` 只表达真实地点，不填写全天状态、发起人或其它备注；没有地点就省略。
  这些额外属性使用同区的 SecondaryBody，事件标题和时间仍留在同一个 EventCard 中。
compact 的时间与地点同行：时间取自然宽度，分隔符保持原间距，地点承接剩余宽度。
完整地点太长时改用普通有地点规格并重算总高，或选择更宽的合法内容区；不删地点或让时间占满整行。

## 7. 操作组件

### 7.1 `PillButton`

#### 选择条件

用于需要显示明确动作文字的内容区操作。只有当前事件候选提供匹配动作时使用；合法操作位由尺寸文件规定。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `label` | string | 仅静态 | 必填；非空动作文字 |
| `onClick` | EventHandler[] | 事件参数按事件 schema | 必填；恰好一个当前事件候选中的 handler |
| `icon` | string | 仅静态 | 可选；逐字使用当前素材候选路径 |

#### 槽位与容量

固定高 `36vp`、圆角 `30vp`，宽度自动撑满当前合法动作槽。2x2 用于底部文字操作；2x4 用于完整内容区的
直属操作，不进入固定模块槽。背景色、文字与单色图标颜色取当前卡片语义色板，字号固定 `14fp/500`。

#### 示例

```genui
["cta","PillButton",{"label":"蓝牙设置","onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"bluetooth_entry"}}]}]
```

#### 注意事项

一个实例只绑定一个动作，同一动作只保留一个入口。不输出宽度、动作色、字号或字重；有 icon 时由 Recipe
生成图标与文字，不手写相同按钮皮肤；
完整标签放不下时更换布局，不裁切、不缩小 Recipe，也不回退为基础 `Button`。

## 8. 选择检查

- 组件内容结构与真实信息关系一致，没有为了使用组件而合并无关字段或补造信息。
- 每个组件只使用自身属性表中的 Props；视觉 Recipe 组件只额外使用允许的外部布局字段。
- 组件进入当前尺寸文件允许的槽位，项目数、文字长度、固定高度和 `InfoBlock.variant` 均符合容量。
- 进度组件绑定真实数值字段或完整数值百分比字符串，并具有可验证的比例、总量或范围。
- 同一事实和同一动作没有在多个组件中重复表达。
- 内容超出固定容量时更换组件或布局，不通过覆盖内部样式、裁切或隐藏必要信息交付。
<!-- /prompt:catalog -->
