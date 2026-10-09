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
| 标题 | `CardHeader` | 单行标题 + 可选主题图标 | 整卡唯一的稳定主题标题 | 每卡最多一个；不能用 Text 替代 |
| 文本 | `Text` | 单段文本或读数 | 重点文字、正文、标签、状态和补充说明 | 不作为 CardHeader 或分区标题的替代物 |
| 核心信息 | `EmphasizedData` | 核心数值 + 可选单位 | 突出唯一量化主值 | 一个核心值；不吸收辅助信息 |
| 核心信息 | `DataDisplay` | 标签 + 主值 + 支撑文本 | 2x2 单一量化焦点 | 三项各一行；不吸收动作或第二指标 |
| 紧凑信息 | `InfoBlock` | 主信息 + 辅助信息 + 可选图标 | 固定小槽中的完整主辅信息 | 每槽一个；不支持事件 |
| 多项属性 | `TableText` | 多行标签—值 | 同一主题的 2–3 项属性 | 两种尺寸共用；进入连续内容槽 |
| 摘要列表 | `SummaryList` | 2–3 条同级摘要 | 2x4 短列表 | 每项固定单行显示 |
| 分隔 | `Divider` | 水平或竖直分隔线 | 确有分组关系的内容之间 | 不作为装饰填空 |
| 占比 | `ProgressCircle` | 环心图标 + 环外读数 | 两个或四个同级对象的真实占比 | 每个实例表达一个 `0–100` 比例 |
| 线性进度 | `ProgressLine2` | 可见读数 + 线性进度 | 当前值相对明确总量 | 当前只用于 2x4 连续内容区 |
| 环形进度 | `ProgressCircleSingle` | 单环 + 右侧读数组 | 单个真实比例及同对象说明 | 两种尺寸共用；规格由尺寸文件决定 |
| 日程 | `EventCard` | 时间线 + 标题 + 时间 + 可选地点 | 两种尺寸的单事件连续内容 | 内容必须来自同一事件 |
| 操作 | `PillButton` | 操作文案 + 可选图标 | 两种尺寸内容区内的直属操作 | 一个实例绑定一个真实动作 |
| 操作 | `CircleButton` | 纯图标操作 | 2x2 右下锚点操作 | 2x2 专属；合同见 `components/2x2.md` |
| 等权指标 | `TopTextBottomValue` | 三组标签—数值—单位 | 2x4 三个同级指标 | 2x4 专属；合同见 `components/2x4.md` |
| 明细信息 | `TextBlock` | 2–4 组标签—值背板 | 2x4 同级详情 | 2x4 专属；合同见 `components/2x4.md` |
| 操作 | `CardButton` | 文案 + 可选图标 | 2x4 固定动作槽 | 2x4 专属；合同见 `components/2x4.md` |
| 视觉 | `Image` | 单个本地素材 | 存在语义准确且状态安全的素材 | 只使用当前素材候选 |

### 1.1 关键选择边界

1. 每张卡最多一个 `CardHeader`；标题必须使用 `CardHeader`，`Text` 只承载正文、标签、状态、读数和补充说明。
2. 先按信息语义和字段关系保留可行组件，再结合尺寸文件的槽位与容量确定最终组件；不为使用组件补造字段。
3. 有唯一核心值时使用一个强调或进度组件；没有真实主次时保持并列，不把普通数字强行放大为核心。
4. 纵向标签—值使用 `TableText`；2x4 横向同级详情按专属组件合同选择 `TextBlock` 或 `TopTextBottomValue`。
5. 单个真实占比及同对象说明使用 `ProgressCircleSingle`；两个或四个同级占比使用多个 `ProgressCircle`；明确目标差距使用 `ProgressLine2`。
6. 时间决定事项成立时使用 `EventCard`；普通时间属性使用 `Text`。同一事实只展示一次。
7. 动作按槽位选择 `PillButton`、`CircleButton` 或 `CardButton`，只能绑定当前事件候选，不伪造操作。
<!-- /prompt:selection -->

<!-- prompt:catalog -->
# 2. Compact DSL 组件合同

只允许三种基础布局组件：`Row`、`Column`、`Stack`。

除基础布局组件外，只允许：`Text`、`Image`、`Divider`、`CardHeader`、`EmphasizedData`、`DataDisplay`、
`InfoBlock`、`TableText`、`SummaryList`、`ProgressCircle`、`ProgressLine2`、`ProgressCircleSingle`、
`EventCard`、`PillButton`，以及尺寸文件登记的 `CircleButton`、`TopTextBottomValue`、`TextBlock`、`CardButton`。

禁止输出 `Button`、`Progress`、`List`、`TextInput`、`Toggle`、`Radio`、`Select`、`NavContainer`、
`Tabs`、`TabContent`、`Web`、`Grid`、`If`。禁止所有组件的 `theme`、`onAppear`、`onChange`、
`onSelect`、`onReachStart`、`onReachEnd`。

## 2.1 组件共同规则

- 组件行的语义字段和样式字段直接写在第三项 `props`，不用的字段省略，不嵌套 `styles`。
- 只有 `Row`、`Column`、`Stack` 在第 4 项声明非空 `children`；其它组件均只输出一行且不带 children。
- `Text`、`Image` 与布局组件只能使用各自章节列出的字段。使用视觉 Recipe 的组件只能使用自身属性表，
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

## 4. 基础内容组件

### 4.1 `Text`

#### 选择条件

用于单段重点文字、正文、标签、状态、读数或补充说明，不用于整卡标题或分区标题。标题只能使用本卡唯一的
`CardHeader`。内容不符合固定语义组件时直接使用；已经完整匹配
`EmphasizedData`、`InfoBlock`、`TableText` 或 `EventCard` 时不再用多个 Text 重造其结构。

#### 组件属性

| Prop | 类型 | 要求 |
|---|---|---|
| `content` | 显示值 | 必填；非空静态值、完整 Expression 或 PathBinding |
| `fontSize` | number | 必填；使用批准字号档位 |
| `fontWeight` | number | 可选；`100–900`，按 100 递增 |
| `fontColor` | `#AARRGGBB` | 必填 |
| `maxLines` | number | 可选；正整数 |
| `minFontSize`、`maxFontSize` | number | 可选；必须同时设置 |
| `textAlign` | string | 可选；`start|center|end|justify` |

可额外使用 3.1 中的布局与表面字段。一个 Text 只承载一段连续内容，不用空 Text 绘制圆点、占位或留白。
生成阶段不输出 `textOverflow`，也不依赖裁切、省略号或字体缩放掩盖压力文本放不下的问题。

#### 字号、字重与文本压力

`Text.fontSize` 只允许 `12`、`14`、`16`、`18`、`20`、`24`、`30`、`32`、`38`，按以下语义选择：

- 需要突出量化主值时，数字及其紧邻单位必须位于所属业务主内容区第一行，必要对象名可以在主值上方或同一行，
  其他支撑文字放在数字下方。CardHeader 和会议日期上下文不计入主内容行；倒计时不构成顶层位置例外：
  有目标名称时按带标题正式布局对齐，无标题且数值自身可理解时才可使用 `S-center`。`ProgressCircle`
  视为所属业务主内容第一项；固定分区布局在各自区域内分别执行。
- `12fp`：标题区、小标题、支撑信息、弱提示、短 metadata、主标签、单位；辅助文字统一使用 `12fp/400`，
  不得降为 `10fp`。
- `14fp`：内容标题、状态、正文、CTA。
- `16fp`：主焦点文字默认档；`18fp`：普通主焦点文字放大档。2x2 稀疏单业务卡中，短且自解释的唯一
  核心状态或结果可以使用 `20fp/24fp`，但必须是全宽单行、显式 `maxLines:1`、通过压力预算且父容器
  无横向 padding；对象名、日期、时间、来源、更新时间和普通说明仍最大 `18fp`。
- `20fp`、`24fp`：紧凑纯数字；`30fp`：主焦点纯数字默认档；`32fp`、`38fp`：内容少且空间充足时
  的数字放大档，数字最大 `38fp`，不保留 `S-center` 大数字例外。
- 未拆分的数字与单位字符串默认 `16fp`、最大 `18fp`；满足下方“格式化主读数例外”时才允许
  `20fp/24fp`，但作为量化主值时仍必须放在所属业务主内容区第一行；拆分后纯数字最大 `38fp`，单位
  使用 `12–16fp`。`S-content-dual-action` 双按钮骨架空间有限，主信息统一使用 `14fp/700`，禁止另起大数字行。
- 上述上限同时适用于 2x2、2x4，包括 `minFontSize/maxFontSize`；上限不是默认值，空间不足时缩小。
  同级并列内容统一字号，CardHeader 固定 `12fp`，按钮固定 `14fp`。

**格式化主读数例外（与转换前校验一致）**：适用于明确描述为温度、时长或百分比的主读数，不限于单一
data 根；名称、日期、时间、状态不适用。内容可以是直接 PathBinding，也可以是只引用一个字段并追加真实
单位的简单 Expression，不得拼接名称、状态或说明。Text 必须单行、无 padding/margin、显式高度至少为字号
的 `1.4` 倍，并与实际主内容槽同宽：2x2 使用 `126vp`，2x4 全宽使用 `276vp`，`W-split-panels`
父区内部使用 `116vp`，`W-content-side-slots` 内容区使用 `132vp`；父级 Column/Row 必须同宽且无 padding。
只允许 `20fp` 或 `24fp`；各槽默认使用 `20fp`，只有按最长合法值加 20% 余量完成压力预算后才可使用
`24fp`。`W-four-slots`、固定小槽与环中心不使用该例外；不能通过增大 Text 声明宽度突破父级预算。

**短核心状态例外（与转换前校验一致）**：只适用于 2x2 稀疏单业务卡的唯一第一焦点，例如简短天气现象、
设备状态或结果词；不得用于对象名、标题、日期、时间、来源、更新时间或普通说明。Text 只能使用 `20fp`
或 `24fp`，必须全宽单行、`maxLines:1`、无 padding/margin，父级为同宽且无 padding 的 Column 或单子节点
Row，并按最长合法值加 20% 余量检查。核心状态超过一行或不能自解释时退回 `16fp/18fp`，并通过自然分行
建立层级；不得用 `30fp/38fp` 放大文字。

字号按批准档位直写，不做档位折算映射；同一卡片最多使用三档字号。同级内容必须使用同一字号、字重、尺寸
和对齐方式；同一组并列指标不能因为某项文本较长就单独降字号或改变垂直位置。某一项放不下时，应统一降低
该组字号、统一调整槽位、缩短弱标签或改用更合适的骨架。

同一 Row 中包含不同字号 Text 时，Row 使用 `alignItems:"bottom"`；每个较小 Text 的 `padding.bottom` 使用
`min(8, ceil((最大字号 - 自身字号) / 4))`，最多补偿 `8vp`。数字与单位 Row 固定使用 `itemMargin:2`，
数字和单位都按内容自适应宽度，不写会拉开两者的固定宽度。

字重按角色选择：主值使用 `700–800`；内容标题使用 `500`，仅当它是唯一强调时升至 `700`；支撑信息使用
`400–500`。同一卡片只保留一个最强字重，不把所有文字加粗。2x4 的卡级标题、区域标签、说明、状态、日期、
时间及其他辅助内容统一使用 `400`，普通主内容标题最多 `500`；`700–800` 只用于真正的主焦点数字、环内
主值、大号核心状态或并列主指标。

受保护文本包括用户明确标题、状态、日期、时间、主指标、价格、数量、联系人称呼和 CTA：

- 卡片级标题或标题行文案默认最多 8 个字符。只有在标题更长确有必要，且按实际字号、完整文案和可用槽位
  完成压力检查后，能够保证完整显示、不影响阅读，也不挤压主信息、图标或动作时才允许超过 8 个字符；
  业务内容中的日程标题、设备名称、列表项标题等不按卡片级标题计数，仍按各自槽位执行完整文本压力检查。
- 必须完整显示。格式化动态字段的前缀、后缀和单位是主值的一部分；例如 `18%` 的 `%`、`-6°C` 的负号
  与 `°C` 都受保护，不得只保证数字主体可见。动态数值的单位是否已包含、合法拼接和拆分结构统一按 4.2.1 执行。
- 温度单位优先统一写作 `°C`。数值型摄氏温度按 4.2.1 由包含 `°C` 的紧邻后置 Text 或完整 Expression
  补充，不得使用单独的 `°`、圆点、实心圆或其它近似符号冒充温度单位；若 TaskSpec 提供的格式化字符串
  已经包含单位，则完整绑定原值，不重复追加或擅自改写。
- 不得用 `ellipsis`、`clip`、超小字号、负间距或遮罩掩盖布局失败。
- 放不下时按顺序处理：缩短弱标签 → 删除可选字段 → 改为两行并增加高度 → 降到批准字号 → 简化布局。
- 不截断用户明确要求的 CTA；按钮宽度需覆盖文字宽度和左右至少 `8vp` 内边距。

动态文本宽度按以下保守规则静默估算：

1. 先构造布局压力字符串：优先取字段语义允许的较长合法值，其次取完整 `sampleValue`；表达式拼接的静态
   前后缀也必须计入。
2. 每个中文字符约 `1.0 × fontSize`，每个英文或数字约 `0.65 × fontSize`，`%`、`°C`、货币符号等宽
   单位约 `0.8 × fontSize`，空格和窄标点约 `0.4 × fontSize`，其余符号至少按 `0.6 × fontSize`。
3. 单行文本必须满足 `Text.width - horizontalPadding >= estimatedWidth × 1.2`；粗体、主指标、百分比、
   温度、金额和时间不得取消这 20% 余量。
4. Row 中多个文本并排时，先分别完成压力检查，再验证
   `sum(child width) + itemMargin + padding <= parent width`；不能把父容器刚好算平当成文本一定放得下。
5. 空间不足时优先把次要状态移到主值下方、扩大主值槽位或降低到批准字号；纵向仍有空间时优先分行，
   不要把多个独立事实继续压进一个 Row。不要从已经格式化且自带单位的动态字符串中剥离单位另造静态 Text；
   原始 number/integer 字段需要按描述补充静态单位时，允许按 4.2.1 拆分数值与包含单位的自然后置文案。
6. 不给动态字段追加重复或可由其自身表达的同义后缀。例如天气现象已显示“小雨”时，不再拼接“· 降雨”；
   按钮已写“导航回家”时，不再增加“点击”或“立即”。静态拼接只有在增加独立信息维度时才保留。

### 4.2 `Image`

#### 选择条件

只使用当前 `assetCandidates` 中语义准确且状态安全的本地素材；没有合适素材时省略并重新分配布局。

#### 组件属性

| Prop | 类型 | 要求 |
|---|---|---|
| `src` | string / 绑定 | 必填；静态路径或只能解析为候选原始路径的绑定 |
| `width`、`height` | number | 必填；正数 vp |
| `objectFit` | string | 必填；优先 `contain`，主媒体确需裁切时使用 `cover` |
| `fillColor` | `#AARRGGBB` | 可选；只用于允许染色的 SVG |

可额外使用 3.1 中除排版字段外的布局与表面字段。SVG 默认可染色并显式设置 `fillColor`；描述明确要求
不可染色、保留原色、多色、渐变或品牌色时省略。PNG 等位图不写 `fillColor`。

### 4.3 `Divider`

只用于真实分隔、时间线或强调线，不作为装饰填空。使用 `strokeWidth`、`vertical`、`color` 和必要的
`width`、`height`，可额外使用必要的外部布局字段。

## 5. 文本与信息组件

本节组件使用视觉 Recipe，只能使用自身属性表和 2.1 允许的外部布局字段。

### 5.1 `CardHeader`

#### 选择条件

用于整张卡唯一的稳定业务、对象、事项或分组主题。每卡最多一个；数值、状态、日期时间和动作不用作标题，
也不再用 Text 制作另一个卡级或分区标题。

#### 组件属性

| Prop | 类型 | 要求 |
|---|---|---|
| `title` | 显示值 | 必填；非空静态值、完整 Expression 或 PathBinding |
| `fontColor` | `#AARRGGBB` | 必填 |
| `icon` | string | 可选；逐字使用当前素材候选路径 |
| `fillColor` | `#AARRGGBB` | 可选；只与可染色 `icon` 同时使用 |

#### 槽位与容量

固定高 `20vp`，每张卡最多一个。它可以位于卡级标题槽，或在无卡级标题时位于一个具体内容分区的首行；
两种位置不能同时出现。具体宽度和合法位置由尺寸布局文件规定。

#### 示例

```genui
["header","CardHeader",{"title":"天气","fontColor":"#FF1F4799","icon":"resources/base/media/sun_max.svg","fillColor":"#FF1F4799"}]
```

#### 注意事项

标题固定左对齐 `12fp/400`，图标固定 `20×20vp`；不传图标时不保留空槽。不覆盖内部 padding、字号或字重。

### 5.2 `EmphasizedData`

#### 选择条件

用于一个内容区中唯一需要突出的核心数值或完整格式化数值。多个同级指标和普通文本结论不使用。

#### 组件属性

| Prop | 类型 | 要求 |
|---|---|---|
| `value` | 显示值 | 必填；静态值、Expression 或 PathBinding |
| `unit` | string | 可选；仅用于静态单位 |
| `fontColor` | `#AARRGGBB` | 必填 |

#### 槽位与容量

只承载一个核心值；合法槽位和宽度由当前尺寸文件规定，不吸收标题、辅助信息或第二指标。

#### 示例

```genui
["reading","EmphasizedData",{"value":{"path":"/data/healthSport/sleepScore"},"unit":"分","fontColor":"#FF563D99"}]
```

#### 注意事项

值已包含单位时不再传 `unit`；不把多个同级值拼进一个 `value`。

### 5.3 `DataDisplay`

#### 选择条件

用于 2x2 中一个短标签、一个唯一核心数值和一条短支撑文本。存在动作、第二指标或独立说明时不使用。

#### 组件属性

| Prop | 类型 | 要求 |
|---|---|---|
| `label` | string | 必填；静态非空短文本 |
| `value` | 显示值 | 必填；唯一核心值 |
| `supportingText` | string | 必填；静态单位或短说明 |
| `fontColor` | `#AARRGGBB` | 必填 |

#### 槽位与容量

合同在本文件定义，当前只进入 2x2 `S-center` 的唯一内容区；具体几何由 `components/2x2.md` 规定。

#### 示例

```genui
["display","DataDisplay",{"label":"运动会倒计时","value":{"path":"/data/countdown/countdownDays"},"supportingText":"天","fontColor":"#FFFFFFFF"}]
```

#### 注意事项

值已包含完整单位时改用其他合适组件，不重复单位。

### 5.4 `InfoBlock`

#### 选择条件

用于固定小槽中属于同一对象或指标的一组“主信息 + 辅助信息”。可附加语义匹配图标，但不承载动作；
完整业务区、两个同级指标和无主辅关系的字段不使用。

#### 组件属性

| Prop | 类型 | 要求 |
|---|---|---|
| `primaryText` | 显示值 | 必填 |
| `secondaryText` | 显示值 | 必填；与主信息属于同一对象或指标 |
| `fontColor` | `#AARRGGBB` | 必填 |
| `backgroundColor` | `#AARRGGBB` | 必填 |
| `variant` | string | 按尺寸文件填写；2x2 可省略，2x4 必填 |
| `icon` | string | 可选；逐字使用当前素材候选路径 |
| `fillColor` | `#AARRGGBB` | 可选；只与可染色 `icon` 同时使用 |

#### 槽位与容量

每个合法固定槽只放一个 `InfoBlock`，两行文字必须保持单行。尺寸、variant 和文字区宽度由尺寸文件规定；
必要值放不下时先取消可选图标，仍不成立则改用其它组件组合。

#### 示例

```genui
["battery","InfoBlock",{"variant":"small","primaryText":"{{ ${/data/phoneBattery/batterySOC} + '%' }}","secondaryText":{"path":"/data/phoneBattery/chargingStatusDesc"},"fontColor":"#FF1F4799","backgroundColor":"#99FFFFFF"}]
```

#### 注意事项

无图标时不生成图标节点或空槽；`fillColor` 不能脱离 `icon`。外层和内部均不得写 `onClick`。

### 5.5 `TableText`

#### 选择条件

用于同一主题下 2–3 项同级“标签—值”。单项信息、唯一核心值、事件时间线和比例关系不使用。

#### 组件属性

| Prop | 类型 | 要求 |
|---|---|---|
| `items` | Array | 必填；2–3 项，每项只含 `label`、`value` |
| `items[].label` | string | 必填；静态非空标签 |
| `items[].value` | 显示值 | 必填；静态值、Expression 或 PathBinding |
| `fontColor` | `#AARRGGBB` | 必填 |

#### 槽位与容量

两种尺寸共用。两行最小高度 `34vp`，三行 `52vp`；只进入尺寸文件允许且能完整容纳所有行的连续内容槽。

#### 示例

```genui
["metrics","TableText",{"items":[{"label":"紫外线","value":{"path":"/data/weatherHealth/ultravioletLevel"}},{"label":"空气质量","value":{"path":"/data/weatherHealth/airQualityLevel"}}],"fontColor":"#FF1F4799"}]
```

#### 注意事项

每项只表达一个事实；不把同一个值同时作为核心读数和表格项。

### 5.6 `SummaryList`

#### 选择条件

用于 2–3 条同级、可单行完整显示的短摘要。长正文、标签—值或存在主次关系的内容不使用。

#### 组件属性

| Prop | 类型 | 要求 |
|---|---|---|
| `items` | Array | 必填；2–3 条显示值 |
| `fontColor` | `#AARRGGBB` | 必填 |
| `backgroundColor` | `#AARRGGBB` | 必填 |

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
温度、日期、时间、时长、倒计时、状态、名称和普通数值不使用，也不从字符串中猜测范围。

### 6.1 `ProgressCircle`

#### 选择条件

用于两个或四个同级对象的真实 `0–100` 占比，每个对象必须有能准确区分它的环心图标。单个占比及
右侧说明使用 `ProgressCircleSingle`；无可靠范围、普通绝对量或没有准确图标时使用文本组件。

#### 组件属性

| Prop | 类型 | 要求 |
|---|---|---|
| `externalText` | number / string / PathBinding | 必填；静态 `0–100` 数值或百分比字符串；动态绑定必须引用 number/integer |
| `icon` | string | 必填；逐字使用当前素材候选路径 |
| `accessibility` | object | 必填；包含静态非空 `label`，可选 `description` |
| `width`、`height` | number | 必填；按当前槽位填写正数 vp |
| `fontColor` | `#AARRGGBB` | 必填；环外读数颜色 |
| `color` | `#AARRGGBB` | 必填；完成轨道颜色 |
| `backgroundColor` | `#AARRGGBB` | 必填；未完成轨道颜色 |
| `fillColor` | `#AARRGGBB` | 可选；单色环心图标颜色 |

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

| Prop | 类型 | 要求 |
|---|---|---|
| `value` | number 绑定 | 必填；绑定 number/integer 字段 |
| `total` | number | 必填；静态正数 |
| `displayValue` | 显示值 | 必填；与 `value/total` 表达同一事实 |
| `unit` | string | 可选；读数未包含单位时填写 |
| `fontColor`、`color`、`backgroundColor` | `#AARRGGBB` | 必填 |

#### 槽位与容量

合同在本文件定义，当前只进入 2x4 组件文件允许的连续内容槽。

#### 示例

```genui
["score","ProgressLine2",{"value":{"path":"/data/healthSport/sleepScore"},"total":100,"displayValue":{"path":"/data/healthSport/sleepScore"},"unit":"分","fontColor":"#FF563D99","color":"#FF563D99","backgroundColor":"#33563D99"}]
```

#### 注意事项

`value`、`total` 和 `displayValue` 必须属于同一进度关系；格式化字符串不能绑定给 `value`。

### 6.3 `ProgressCircleSingle`

#### 选择条件

用于一个具有真实比例范围的环形主指标，环心显示对象图标，右侧显示标签、读数和可选状态。

#### 组件属性

| Prop | 类型 | 要求 |
|---|---|---|
| `value` | number 绑定 | 必填；绑定 number/integer 字段 |
| `total` | number | 必填；静态正数 |
| `icon` | string | 必填；逐字使用当前素材候选路径 |
| `displayValue` | 显示值 | 必填；与环形进度表达同一数值 |
| `label` | string | 必填；静态非空说明 |
| `secondaryLabel` | 显示值 | 可选；同一对象的一条状态说明 |
| `fontColor`、`color`、`backgroundColor` | `#AARRGGBB` | 必填 |

#### 槽位与容量

两种尺寸共用。2x2 使用普通规格，2x4 使用 compact 规格；合法槽位与高度预算由尺寸文件规定。

#### 示例

```genui
["main","ProgressCircleSingle",{"value":{"path":"/data/phoneBattery/batterySOC"},"total":100,"icon":"resources/base/media/battery_leaf_fill.svg","displayValue":{"path":"/data/phoneBattery/batterySOCText"},"label":"手机电量","secondaryLabel":{"path":"/data/phoneBattery/chargingStatusDesc"},"fontColor":"#FF1F4799","color":"#FF1F4799","backgroundColor":"#331F4799"}]
```

#### 注意事项

`value`、`displayValue` 与 `secondaryLabel` 必须属于同一对象；图标只标识对象，不代替可见读数。

## 7. 日程组件

### 7.1 `EventCard`

#### 选择条件

用于一个具有标题和时间的事件，可带地点。普通时间属性不使用；多个事件不拆成多个文本绕过容量。

#### 组件属性

| Prop | 类型 | 要求 |
|---|---|---|
| `title` | 显示值 | 必填；事件标题 |
| `time` | 显示值 | 必填；同一事件的时间 |
| `location` | 显示值 | 可选；同一事件的地点 |
| `fontColor` | `#AARRGGBB` | 必填 |

#### 槽位与容量

两种尺寸共用，进入尺寸文件允许的连续内容槽，当前合同承载一个事件；所属动作放在独立操作组件中。

#### 示例

```genui
["content_area","EventCard",{"title":{"path":"/data/calendar/events/0/title"},"time":{"path":"/data/calendar/events/0/dtStart"},"fontColor":"#FF8C4B1C"}]
```

#### 注意事项

组件已包含时间线和文字列，不再手写轨道 Divider 或重复标题、时间 Text。

## 8. 操作组件

### 8.1 `PillButton`

#### 选择条件

用于需要显示明确动作文字的内容区操作。只有当前事件候选提供匹配动作时使用；合法操作位由尺寸文件规定。

#### 组件属性

| Prop | 类型 | 要求 |
|---|---|---|
| `label` | string | 必填；静态非空动作文字 |
| `onClick` | EventHandler[] | 必填；恰好一个当前事件候选中的 handler |
| `actionSurface` | `#AARRGGBB` | 必填；按钮背景色 |
| `actionInk` | `#AARRGGBB` | 必填；文字与单色图标颜色 |
| `icon` | string | 可选；逐字使用当前素材候选路径 |
| `fontSize` | number | 可选；只允许 `14` |
| `fontWeight` | number | 可选；只允许 `400` 或 `500` |
| `width` | number / `matchParent` | 可选；按尺寸文件合法槽位填写 |

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
- 进度组件绑定真实 number/integer 字段，并具有可验证的比例、总量或范围。
- 同一事实和同一动作没有在多个组件中重复表达。
- 内容超出固定容量时更换组件或布局，不通过覆盖内部样式、裁切或隐藏必要信息交付。
<!-- /prompt:catalog -->
