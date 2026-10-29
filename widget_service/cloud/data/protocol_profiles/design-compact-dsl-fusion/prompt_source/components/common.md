---
name: card-components
description: 共用单组件的语义、Props、容量和示例；尺寸差异和专属组件在尺寸文件，组合与槽位另有唯一来源。
---

# 组件合同

<!-- prompt:selection -->
## 1. 组件总表

| 类型 | 名称 | 内容结构 | 适用场景 | 容量与约束 |
|---|---|---|---|---|
| 标题 | `SingleLineTitle` | 单行标题 | 简短概括一个语义分区 | 每个分区最多一个；不用正文组件替代 |
| 标题 | `DoubleLineTitle` | 标题 + 次级信息 | 对象名还需同时表达状态或地点 | 两项必须紧密相关 |
| 标题附属 | `Badge` | 标题关联数量 | 标题旁显示同一集合的真实数量 | 只能与标题组成标题单元 |
| 核心信息 | `EmphasizedData` | 核心数值 + 可选单位 | 突出唯一量化主值 | 一个核心值；不吸收辅助信息 |
| 核心信息 | `EmphasisText` | 主文本 + 可选次文本 | 突出文本结论、类别或状态 | 两行必须属于同一核心语义 |
| 正文与补充 | `SecondaryBody` | 1–6 个正文、metadata 或短说明项 | 补充整卡已经存在的核心信息，可进入独立支撑区 | 整卡无核心时不用；同组多项放入一个实例并按单行／多行选择固定字号 |
| 紧凑信息 | `InfoBlock` | 主信息 + 辅助信息 + 可选图标或占比圆环 | 固定小槽中的完整主辅信息 | 每槽一个；不支持事件 |
| 多项属性 | `TableText` | 多行标签—值 | 同一主题的 2–3 项属性 | 两种尺寸共用；进入连续内容槽 |
| 占比 | `ProgressCircle` | 环心图标 + 环外读数 | 两个或四个同级对象的真实占比 | 每个实例表达一个 `0–100` 比例 |
| 比较 | `H_BarChart` | 2–3 组标签、值和横向柱 | 比较多个对象的同一指标 | 不比较不同量纲 |
| 环形进度 | `ProgressCircleSingle` | 单环 + 右侧读数组 | 单个真实比例及同对象说明 | 两种尺寸共用；规格由尺寸文件决定 |
| 占比摘要 | `NumericRatioStack` | 三组图标 + 数值 + 单位 | 三个同级对象的紧凑占比 | 必须恰好三项且图标可区分 |
| 日程 | `EventCard` | 时间线 + 一个或多个事件 | 两种尺寸的连续日程内容 | 默认同组合并一个实例；W-top-bottom可在primary/details有序分段，按实际总高验算容量 |
| 操作 | `PillButton` | 操作文案 + 可选图标 | 两种尺寸内容区内的直属操作 | 一个实例绑定一个真实动作 |
| 操作 | `CardButton` | 卡片背板 + 动作文案 + 视觉位 | 尺寸文件限定的固定动作槽 | 一个真实动作，不承载动态正文 |

符合专用语义、类型及容量时优先相应组件；不为用组件补造字段。单一核心与真实同级关系不能混淆。
2x2 无动作且整卡只有一个核心读数或1–8字短文本结论及其紧密支撑时，优先使用尺寸专属的
`S-center` + `DataDisplay`；不要仅放置一个 `EmphasizedData` 或 `EmphasisText`。一个明确核心附带地点、
备注、限定或短明细等从属信息时，使用普通核心组件与 `SecondaryBody`。恰好两个等权、各自能够独立
理解的短信息不是“核心 + 补充”，应各用一个 `InfoBlock`，再由尺寸布局承载，不把其中一项降为
`SecondaryBody`。
尺寸专属组件见对应尺寸总表。Text 不是生成候选。
<!-- /prompt:selection -->

<!-- prompt:catalog -->
# 2. 单组件细则

## 共同约束

只使用各组件属性表中的真实 Props。显示值支持表中声明的绑定；图标与样式保持静态。标有 fontSize 的文本组件必须显式写固定主字号，不能调小；内部次字号、字重、颜色和几何不用输出。
组件不能新增 children 或事件能力。外部槽位由语义布局提供，不输出兼容旧输入的宽高、权重、padding、圆角等参数。
图标来源和染色遵守 Core；尺寸差异、专属组件及槽位可用性见尺寸合同。

### 1. `SingleLineTitle`

#### 选择条件

用于简短的静态分区标题，或由一个字段直接承担的对象名、地点名、设备名。每个语义分区最多一个；
2x4 左右独立分区可分别使用。数值、状态、日期时间和动作不用作标题，也不用正文组件重造标题。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `title` | 显示值 | 静态 / Expression / PathBinding | 必填；非空单行标题 |
| `icon` | string | 仅静态 | 条件必选；按钮完成图标分配后，仍有与标题或卡片主题语义匹配且未被按钮使用的静态图标时默认填写；不可点击 |
| `fontSize` | number | 仅静态 | 新生成必填；固定 `12`，不允许修改 |

#### 槽位与容量

无 `icon` 时按 `12vp` 单行标题参与父布局高度计算；有 `icon` 时按 `20vp` 参与高度计算。
带图标变体使用端侧已兼容的 `20vp` 高 Row，标题文字以 `layoutWeight: 1` 占据剩余宽度，`20×20vp` 图标保持在右侧垂直居中；标题在剩余文字区单行省略，不能与图标重叠。标题图标分配遵守 Core 素材规则；有可用匹配候选时默认填写，不可点击，不承载动态状态。

#### 示例

```genui
["header","SingleLineTitle",{"title":"天气","icon":"resources/base/media/weather.png","fontSize":12}]
```

#### 注意事项

标题使用固定12fp；SVG图标自动配色，不输出 fillColor。

### 2. `DoubleLineTitle`

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

参考占高为主标题18vp＋4vp间距＋次信息18–36vp，不能忽略次行高度。
进入标题位置；主标题 `12fp/700`，次信息 `12fp/500`。它比 `SingleLineTitle` 占用更多高度，主体容量不足时改用
单行标题或更宽内容区。

#### 示例

```genui
["device_title","DoubleLineTitle",{"title":{"path":"/data/sensor/displayName"},"secondaryInfo":{"path":"/data/sensor/connectionStatus"},"fontSize":12}]
```


### 3. `Badge`

#### 选择条件

仅用于标题明确命名同一集合、且存在真实数量字段的“标题 + 数量”组合。状态、温度、时长、百分比和普通核心值
不使用；数量是唯一核心信息时使用内容组件。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `value` | 显示值 | 静态 / Expression / PathBinding | 必填；短数量或 `99+` |
| `backgroundColor` | `#AARRGGBB` | 仅静态 | 必填 |

#### 槽位与容量

不能单独进入标题位或内容位；必须紧跟标题组件，在2x4中共同放入Group.title-count。数量在整卡只表达一次。

#### 示例

```genui
["event_count","Badge",{"value":{"path":"/data/calendar/eventCount"},"backgroundColor":"#338C4B1C"}]
```

### 4. `EmphasizedData`

#### 选择条件

用于一个内容区中唯一需要突出的核心数值或单一测量读数。多个同级指标和普通文本结论不使用。
但在2x2无动作卡片中，若该数值是整卡唯一核心且只有单位、更新时间等紧密支撑，优先使用
`S-center` + `DataDisplay`；只有存在动作、独立补充事实或其它内容分区时，才保留 `EmphasizedData`，
并按需与 `SecondaryBody` 组合。
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

### 5. `EmphasisText`

#### 选择条件

用于一个分区最重要的文本结论、类别或状态。次文本只补充同一个核心语义；纯单一数值核心使用
`EmphasizedData`，事件、进度或比较保持专用组件。已经格式化的主读数与同一对象的一至两个短状态共同
构成一个完整摘要时，可以使用 `EmphasisText`：主读数进入 `mainText`，紧密关联的状态进入
`secondaryText`。这种组合以完整表达同一语义组为目的，不把互不相关的字段或仍需30fp强调的独立量化
主值降为次要文本。
但在2x2无动作卡片中，若1–8字短文本结论是整卡唯一核心且只有更新时间等紧密支撑，优先使用
`S-center` + `DataDisplay`；只有存在动作、独立补充事实或其它内容分区时，才保留 `EmphasisText`，
并按需与 `SecondaryBody` 组合。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `mainText` | 显示值 | 静态 / Expression / PathBinding | 必填；核心文本 |
| `secondaryText` | 显示值 / PathBinding[] | 静态 / Expression / PathBinding；多源时使用至少 2 个有序 PathBinding | 可选；同一语义的一条短补充；数组由转换器按顺序以 ` | ` 连接 |
| `fontSize` | number | 仅静态 | 新生成必填；主文本固定 `18`；次文本仍由 Recipe 固定为 `12` |

#### 槽位与容量

主文本使用18fp、`lineHeight: 1`，实际占18vp；可选次文本占16vp，两者间距2vp。

#### 示例

```genui
["connection","EmphasisText",{"mainText":{"path":"/data/earphone/connectionStatus"},"secondaryText":{"path":"/data/earphone/name"},"fontSize":18}]
```
例如当前温度、天气现象与空气质量共同组成同一时点的天气摘要时，温度文本作为主文本，天气现象和
空气质量共同组成次文本；所有动态字段仍会独立响应数据更新：

```genui
["weather","EmphasisText",{"mainText":{"path":"/data/weather/current/temperatureText"},"secondaryText":"{{ ${/data/weather/current/condition} + ' | 空气质量 ' + ${/data/weather/current/airQuality} }}","fontSize":18}]
```

不需要静态标签的多个紧密关联短字段，也可以使用至少两个有序 PathBinding 组成的数组，由转换器以
` | ` 连接。需要增加“空气质量”等静态标签时，如上例使用包含全部绑定的完整 Expression；
`mainText` 不接受数组，互不相关或需要逐项独立查看的多个字段改用 `SecondaryBody` 或 `TableText`。


### 6. `SecondaryBody`

#### 选择条件

只用于补充整卡已经存在的核心信息，例如辅助正文、普通时间、来源、更新时间或弱提示；可以位于独立
支撑区，但整卡不能只有 `SecondaryBody`、标题与按钮。标题、Badge、按钮、布局容器和其它 `SecondaryBody`
都不算核心组件。正文自身是主要结论时使用 `EmphasisText`，不能用 `SecondaryBody` 规避核心选型。
刷新元数据默认不展示；用户明确要求或时效决定业务结论时可放入辅助支撑区；仅为填补无动作稀疏卡片时，应把
刷新元数据合入该核心 `EmphasisText.secondaryText`，不得为了填空单独创建 `SecondaryBody`、第二分区或
`S-title-dual-content`。组件不区分 role，单项和多项均写入 `items`；同一对象或同一集合的
多个短字段按原顺序放入一个实例，不得按日期、对象索引或字段逐项拆成多个
单项 `SecondaryBody`，也不得为使用较小字号或规避容量校验而拆分。只有整卡无核心且用户明确要求逐项查看、
对比或等权汇总的标签—值表才使用 `TableText`；事件、比较和进度仍使用对应语义组件。
超过6项时优先删除重复、与需求无关或已接受Plan未要求的可选补充项，不为凑满6项补造内容。
已接受Plan要求的事实不得仅为满足项数删除；未经Drop授权时保留事实，改用能完整承载的合法组件组合。
允许6项不代表当前槽位能装下6项，仍按实际行数、完整值与间距验算容量。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `items` | Array | 数组结构仅静态 | 必填；1–6 项 |
| `items[].value` | 显示值 | 静态 / Expression / PathBinding | 必填；承载完整值和单位；追加单位或格式化使用完整 Expression |
| `items[].label` | string | 仅静态 | 可选；可独立识别的短字段名称优先写在这里，不拼进 value |
| `items[].maxLines` | number | 仅静态 | 可选；`1|2`，默认 1；两行时必须预留高度 |
| `columns` | number | 仅静态 | 可选；`1|2`，默认 2；1 表示每项独占一行 |
| `separator` | string | 仅静态 | 可选；同一行相邻项默认用 ` | ` 分隔，跨行不加分隔符 |
| `fontSize` | number | 仅静态 | 新生成必填；整组单行固定 `14`，多行固定 `12` |

#### 槽位与容量

按行布局选择规格：只有一行且每项 `maxLines:1` 时为 `14fp/400`、行高 `14vp`；
超过一行或任一项使用 `maxLines:2` 时，整组为 `12fp/400`、行高 `12vp`。
两项同行用 14；两项 `columns:1` 分行用 12，不能只按项目数判断。
每行最多两项，行间距固定 2；总高度为各行最大 `maxLines × 行高` 之和加行间距。
转换器按首帧完整文案与参考槽位宽度自动分行，整组转为多行时使用12fp/12vp，不裁切原值；
同行短项按自然占宽，不强制等分。没有已知文案或宽度时仍须显式声明单列/两行并预留容量。
文字放不下时使用单列或合法两行，并同步字号与高度预算；不裁切、删单位或手动缩字。
可独立识别的短字段名称优先放 `label`，动态值和单位放同项 `value`；裸值直接绑定，
不重复添加原值已含的名称或单位。标签保留自然宽度，值承接剩余宽度。
只有完整正文，或使用单列/合法两行后确实仍无法分开完整排版时，才把标签合入同项完整
Expression；保留原始绑定、标签和单位。不因能拼接 Expression 就省略短标签，也不为纯正文补造 label。
不输出 `role`，不覆盖内部字重、padding 或对齐。

```genui
["description","SecondaryBody",{"items":[{"value":{"path":"/data/weather/description"},"maxLines":2}],"fontSize":12}]
["updated","SecondaryBody",{"items":[{"label":"更新 ","value":{"path":"/data/weather/updatedAt"}}],"fontSize":14}]
["heart_detail","SecondaryBody",{"items":[{"label":"最低心率 ","value":"{{ ${/data/healthSport/exerciseHeartRateMin} + '次/分钟' }}","maxLines":2}],"fontSize":12}]
["sleep_detail","SecondaryBody",{"items":[{"label":"夜间睡眠 ","value":{"path":"/data/healthSport/nightSleepDurationText"}},{"label":"午睡 ","value":{"path":"/data/healthSport/napDurationText"}}],"separator":" | ","fontSize":14}]
```

以上仅展示组件属性写法；放入完整卡片时，整卡必须另有至少一个核心信息组件，但可位于其它语义分区。

### 7. `InfoBlock`

#### 选择条件

用于固定或有明确高度的小槽中属于同一对象或指标的一组“主信息 + 辅助信息”。尾部可显示语义图标，或由主信息驱动的
真实占比圆环，但不承载动作；
完整业务区、两个同级指标和无主辅关系的字段不放进同一个InfoBlock；本限制针对单个实例，
不排除合法双信息块组合中每块分别表达一个指标。指标名可作为secondaryText的静态说明，
不要求主次两行都绑定动态值；不为满足两行结构引入额外事实。

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

每个合法小槽只放一个 `InfoBlock`，两行文字保持单行。尺寸、variant 和文字区宽度由尺寸文件规定。
`secondaryText` 统一使用 12fp/500、16vp 行盒；该调整不改变 `unit` 的独立字号 Recipe。
`primaryText` 应完整可读；`secondaryText` 超出文字区时由 Recipe 在尾部显示省略号，并产生 warning，
不因此拒绝整张卡。省略只影响辅助文字的可见尾部，原始绑定与完整数据保持不变。

#### 尺寸示例

信息槽的普通、紧凑及图形示例见当前尺寸组件细则。

#### 注意事项

visual 不是装饰；`progressCircle` 只用于可验证的 `0–100` 主值。没有准确 visual 时不生成尾部空槽；
每行只承载一个动态业务值，不把第二个动态字段拼入 `primaryText`；同级对象需要区分时允许添加一个简短
静态对象标签，指标名需要帮助理解时允许添加一个简短静态标签。`visual.type:"progressCircle"` 的
`primaryText` 仍必须是原始有限数值或完整百分比，不得添加标签。外层和内部均不得写 `onClick`。
2x2 恰好两个同级 InfoBlock 时使用无独立标题的 `S-dual-info`，不额外生成 `SingleLineTitle`；
对象、日期和指标标签保留在各自块内。用户明确要求独立可见标题或动作时，不使用该双信息块组合。
`secondaryText` 仅作静态说明时，优先用它承载完整指标名及必要对象限定，`primaryText` 只放该读数，
独立单位用 `unit`；不要把已有说明重复拼进主行造成超宽。辅助行已有动态事实时不能覆盖它，
主行仍保留辨别对象所必需的简短标签；两行合起来必须完整可懂，不新增或删除事实。

### 8. `TableText`

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

### 9. `ProgressCircle`

#### 选择条件

用于两个或四个同级对象的真实 `0–100` 占比，每个对象必须有能准确区分它的环心图标。单个占比及
右侧说明使用 `ProgressCircleSingle`；无可靠范围、普通绝对量或没有准确图标时使用文本组件。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `externalText` | number / string / Expression / PathBinding | 静态 / Expression / PathBinding | 必填；`0–100` 数值、纯数值字符串、完整百分比字符串，或结果为 `0–100` 数值的完整 Expression；需要环外百分号时可让 Expression 以 `+ '%'` 或 `+ '％'` 结尾 |
| `icon` | string | 仅静态 | 必填；逐字使用当前素材候选路径 |
| `accessibility` | object | 仅静态 | 必填；包含非空 `label`，可选 `description` |
| `color` | `#AARRGGBB` | 仅静态 | 必填；完成轨道颜色 |
| `backgroundColor` | `#AARRGGBB` | 仅静态 | 必填；未完成轨道颜色 |
| `fillColor` | `#AARRGGBB` | 仅静态 | 使用默认可染色 SVG 时必填；位图不填写 |

#### 槽位与容量

组件内部固定为正圆进度环、`20×20vp` 环心图标和环外读数；合法数量、外框和槽位由尺寸文件规定。

#### 示例

```genui
["ratio","ProgressCircle",{"externalText":{"path":"/data/device/batteryPercent"},"icon":"resources/base/media/battery_leaf_fill.svg","accessibility":{"label":"设备电量百分比"},"fillColor":"#991F4799","color":"#FF1F4799","backgroundColor":"#331F4799"}]
```

#### 注意事项

`externalText` 同时驱动圆环和环外读数。Expression 以 `+ '%'` 或 `+ '％'` 结尾时，转换器确定性拆出前面的
数值表达式驱动圆环，并保留原表达式作为环外读数；其它 Expression 必须直接返回 `0–100` 数值，环外读数由
转换器追加 `%`。不传 `value`、`total`、`type`、`strokeWidth`、`size` 或 children。

### 10. `ProgressCircleSingle`

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

### 11. `H_BarChart`

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

#### 槽位与容量

两项至少71vp、三项至少98vp，必须进入完整连续内容区。

#### 示例

```genui
["energy_compare","H_BarChart",{"items":[{"label":"客厅","valueUnit":{"path":"/data/energy/livingText"},"percent":80},{"label":"书房","valueUnit":{"path":"/data/energy/studyText"},"percent":45}],"barColor":"#FF1F4799","trackColor":"#331F4799"}]
```


### 12. `NumericRatioStack`

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

#### 槽位与容量

column 三项高56vp；row 逐项检查完整读数宽度，不能截尾。

#### 示例

```genui
["storage_ratio","NumericRatioStack",{"direction":"column","items":[{"icon":"resources/base/media/externaldrive_fill.svg","value":{"path":"/data/storage/nodeA/usedPercent"},"unit":"%"},{"icon":"resources/base/media/earphone_case_16644.svg","value":{"path":"/data/storage/nodeB/usedPercent"},"unit":"%"},{"icon":"resources/base/media/l_circle_fill.svg","value":{"path":"/data/storage/nodeC/usedPercent"},"unit":"%"}],"fillColor":"#FF1F4799"}]
```


### 13. `EventCard`

#### 选择条件

用于一个或多个按时间排列、各自具有标题和时间的事件，可带地点。默认将同组多事件放在同一个
`EventCard`中并按时间排序。仅在 `W-top-bottom` 的primary和details表达同一有序事件集的前后分段时，
允许使用两个实例；不得重复事件或打乱顺序，且两段总高仍须通过父槽和整卡容量校验。普通时间属性不使用，
也不把事件拆成普通文本绕过容量。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `items` | Array | 数组结构仅静态 | 必填；至少一项；不设固定数量上限，按实际展开高度校验容量 |
| `items[].title` | 显示值 | 静态 / Expression / PathBinding | 必填；事件标题 |
| `items[].time` | 显示值 | 静态 / Expression / PathBinding | 必填；事件时间 |
| `items[].location` | 显示值 | 静态 / Expression / PathBinding | 可选；事件地点 |
| `density` | `compact` | 仅静态 | 可选；多项普通高度放不下时使用 |

#### 槽位与容量

普通单项无地点34vp、有地点50vp；普通多项间距8vp。
两种尺寸共用，进入尺寸文件允许的连续内容槽；除上述 `W-top-bottom` 有序分段外，一个组件承载全部同组事件，
所属动作放在独立操作组件中。
多项普通模式总高为各项实际高度之和加 `8vp × (items 数量 - 1)`；compact 将相邻项间距收紧为
`4vp`，总高为 `32vp × items 数量 + 4vp × (items 数量 - 1)`。数量放开不豁免父槽与整卡容量校验。

#### 示例

```genui
["content_area","EventCard",{"items":[{"title":{"path":"/data/calendar/events/0/title"},"time":{"path":"/data/calendar/events/0/dtStart"},"location":{"path":"/data/calendar/events/0/location"}},{"title":{"path":"/data/calendar/events/1/title"},"time":{"path":"/data/calendar/events/1/dtStart"}}],"density":"compact"}]
```

#### 注意事项

组件已包含时间线和文字列，不再手写时间线轨道或重复标题、时间内容。新生成统一使用 `items`。
  `items[].location` 只表达真实地点，不填写全天状态、发起人或其它备注；没有地点就省略。
  这些额外属性使用同区的 SecondaryBody，事件标题和时间仍留在同一个 EventCard 中。
compact 的时间与地点同行：时间取自然宽度，分隔符保持原间距，地点承接剩余宽度。
完整地点太长时改用普通有地点规格并重算总高，或选择更宽的合法内容区；不删地点或让时间占满整行。


### 14. `PillButton`

#### 选择条件

用于需要显示明确动作文字的内容区操作。只有当前事件候选提供匹配动作时使用；合法操作位由尺寸文件规定。

#### 组件属性

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `label` | string | 仅静态 | 必填；最多5个可见字符，使用简洁的“动作+必要目标”文案 |
| `onClick` | EventHandler[] | 事件参数按事件 schema | 必填；恰好一个当前事件候选中的 handler |
| `icon` | string | 仅静态 | 可选；逐字使用当前素材候选路径 |

#### 槽位与容量

固定高 `36vp`，宽度自动撑满当前合法动作槽。2x2 用于底部文字操作；2x4 用于完整内容区的
直属操作，不进入固定模块槽。背景色、文字与单色图标颜色取当前卡片语义色板，字号固定 `14fp/500`。

#### 示例

```genui
["cta","PillButton",{"label":"蓝牙设置","onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"bluetooth_entry"}}]}]
```

#### 注意事项

一个实例只绑定一个动作，同一动作只保留一个入口。不输出宽度、动作色、字号或字重；有 icon 时由 Recipe
生成图标与文字，不手写相同按钮皮肤；
超过5个字符时只缩短可见文案，例如“一键导航去公司”改为“导航去公司”；完整 `onClick`、参数和动作目标保持不变。5个字符内仍放不下时更换布局，不裁切、不缩小 Recipe，也不回退为基础 `Button`。
### 14. `CardButton`

只进入尺寸文件登记的固定动作槽，一个实例承载一个真实动作，不用按钮label替代动态正文。
左侧缺省单行文案，右侧为固定视觉位；有准确图标时使用候选素材。事件必须逐字复用当前候选。

| Prop | 类型 | 绑定能力 | 要求 |
|---|---|---|---|
| `label` | string | 仅静态 | 必填；最多5个可见字符，保留动作与必要目标 |
| `labelLines` | 1 / 2 | 仅静态 | 可选，缺省1；两行占高40，必须满足所属槽位容量 |
| `icon` | string | 仅静态 | 可选；逐字使用当前素材候选路径 |
| `fillColor` | — | — | 不输出；单色 SVG 由运行时按按钮前景色自动染色，位图保留原色 |
| `onClick` | EventHandler[] | 事件参数按事件 schema | 必填；恰好一个当前事件候选中的 handler |

背板与几何由Recipe和所属槽提供，不输出backgroundColor、宽高、padding或字号。
超过5个字符时只缩短可见文案，例如“一键导航去公司”改为“导航去公司”，完整事件保持不变；
5个字符内缺省单行仍超出文字区时由 Recipe 在尾部显示省略号并产生 warning，不因此拒绝整张卡。
需两行时先核对尺寸合同的实际槽高；
字号、槽位高度、图标、padding均不改变。两个字以内的短值不能作为任意长标签的容量依据。
两行仍不能容纳必要目标时，改选其它合法动作组件及父布局，保留动作与真实目标；不创建低阶可点击容器，不改内部规格，也不重复入口。

```genui
["settings","CardButton",{"label":"蓝牙设置","onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"bluetooth_entry"}}]}]
```

动态进度约束：以上数值字符串和百分比字符串仅指静态字面量；动态 PathBinding 必须指向 number/integer。有 numericSource 时使用其登记的数值路径，不将文本首帧解析为进度。
<!-- /prompt:catalog -->
