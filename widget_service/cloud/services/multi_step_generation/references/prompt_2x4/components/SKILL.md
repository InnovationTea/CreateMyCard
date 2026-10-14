---
name: phone-widget-2x4-components
description: 根据信息语义选择单个组件，并填写该组件的 Props、绑定和容量。
---

# Design System

## 1. 组件总览

> 阅读约定：每个组件的“组件属性”就是生成代码时可使用的真实显示 Props；“空间占位”只记录与 runtime 对齐、且会影响布局容量判断的外部几何；字体、颜色、背景、圆角、描边、内部 Icon 尺寸与交互态等无需模型控制的组件内部样式不在生成文档中重复。“布局约束”记录组件与 `Card.layout`、`Region.slot/variant` 的组合方式。设计必选与 runtime 容错会在同一张属性表中分别说明。设计构成字段不一定是 JSX Props。每个组件允许绑定的数据字段和动作均在本文件对应组件章节内说明；所有 `icon` 和数组项中的 Icon 都必须逐字使用当前输入 `assetCandidates[].src` 中已有的模型侧值，并按候选项 `description` 选择语义匹配的资源。默认媒体资源只写 `icon_weather1.svg` 这样的文件名，由 runtime 和后续转换层补全 `resources/base/media/`；非默认目录资源保留输入给出的路径。示例路径不是内建资源，也不能在其他任务中直接复用；当前任务没有同名候选时不得使用示例资源。可选 Icon 没有候选时省略；Icon 必选的组件没有语义匹配候选时不要选用。

### 1.1 2×2、2×4 通用组件

本节列出两种 Card 尺寸都可使用的组件；本文件末尾继续列出当前任务尺寸的专属组件。

`SingleLineTitle`、`DoubleLineTitle`、`Badge`、`EmphasizedData`、`EmphasisText`、`SecondaryBody`、`DataDisplay`、`InfoBlock`、`TableText`、`ProgressLine2`、`ProgressCircleSingle`、`ProgressCircle`、`NumericRatio`、`NumericRatioStack`、`EventCard`、`H_BarChart`、`PillButton`

## 进度关系与辅助信息

1. 只有表达完成度、达成率、使用率、剩余占比或其他真实比例关系的百分比，才按进度处理。湿度、概率等普通百分比属性如果只是辅助事实，应作为辅助文本，不得仅因数值带 `%` 就选择进度组件。同一对象中的 `percent`、`current`、`total` 与可用量、剩余量或当前量共同构成一个进度关系，不拆成多个独立数据性质；`percent` 优先驱动进度，缺少时才使用 `current ÷ total × 100`。当真实比例只提供格式化百分比字符串（例如 `"68%"`、`"43.75%"`）时，该字段仍视为可驱动进度的 percent；字符串必须完整匹配“数字 + `%`”格式，不得从“剩余68%”“约68%”等混合文案中猜测数值。单个此类占比不得仅因输入类型为 string 退化为 `EmphasizedData`。手机电量、耳机仓电量等单个设备的剩余电量表示“当前余量状态”，不是朝目标推进的完成进度；默认使用 `ProgressCircleSingle`，当它与另一组“主文本 + 副文本 + 尾部视觉”的紧凑信息共同构成两个 64vp 信息块时，也可使用 `InfoBlock` 的 `visual.type="progressCircle"` 表达。即使输入同时提供 `current`、`total=100` 或格式化百分比，也不得仅为了突出数值改用 `ProgressLine2`。`total` 默认只用于计算或提供上下文，不直接显示。
2. 丰富信息中的非核心数字属性可以作为辅助文本组织，不因包含数字就单独提升为核心单值；多个次要字段统一使用“｜”分隔，不使用“·”。

## 单组件候选总表

### B2. 从信息语义选择具体组件

先判断信息承担的角色，再判断同类数据的数量，最后判断是否需要操作入口。下表中的“字段结构示例”描述输入信息的语义结构，不是可以直接复制到 JSX 的 Props；选定组件后，必须再按照本 Skill 中对应组件章节将字段映射为真实 JSX Props。

| 数据性质 / 信息形态 | 字段结构示例 | 选择组件 | 选择条件 | 不应选择的情况 |
|---|---|---|---|---|
| 单层标题 | `{title}` | `SingleLineTitle` | 只有一行纯文本标题 | 标题还需要表达连接状态、地点等第二层信息时不用；不向该组件添加 Icon |
| 标题 + 次要信息 | `{title, secondaryInfo}` | `DoubleLineTitle` | `title` 与 `secondaryInfo` 均有独立语义，例如设备名称 + 连接状态 | 不要把普通说明文字放进 `secondaryInfo`；严禁同时出现`SingleLineTitle`与`DoubleLineTitle` |
| 标题中的数量 | `{title, count: number \| formattedNumber}` | `Badge` | 未读数、总数、数量等与标题绑定的数值；字符串只用于 `99+` 等格式化数值 | 不用于状态、类别、普通标签或说明文字 |
| 纯单值 | `{label?, value, unit? / supportingText?}` | `DataDisplay` / `EmphasizedData` | 不包含目标、基准、等级、时间轴、分段或进度关系的数值事实。先以整张卡片为单位统计数据叙事：有且仅有一个完整数据叙事，结构为 `label + value + unit／supportingText`，且不存在标题、操作或其他并列数据事实时，选择 `DataDisplay` 并固定使用无标题的“核心居中”；丰富信息中与用户意图相关性最高的核心数值选择 `EmphasizedData`，由数值与单位构成，单位可由独立 `unit` 或完整格式化字符串承载；同一分区只允许一个核心信息 | 不得为了选择 `DataDisplay` 将天气状态、空气质量、最高温度、最低温度等并列事实拼成一条辅助信息；不得在同一分区并列或堆叠多个 `EmphasizedData`，也不得再用 `EmphasisText` 强调另一项核心信息；进度关系中的绝对值不重复映射为纯单值；区间档位、可比较数据或多维同等属性不用 |
| 核心文本 | `{mainText, secondaryText?}` | `EmphasisText` | 分区内与用户意图相关性最高的核心文本数据；`mainText` 只承载一个核心字段，紧密关联的第二字段放入 `secondaryText`；同一分区只允许一个核心信息 | 不得把多个业务字段用 `｜` 拼接到 `mainText`；没有真实且必要的第二字段时省略 `secondaryText`，不得虚构；不得在同一分区并列或堆叠多个 `EmphasisText`，也不得再用 `EmphasizedData` 强调另一项核心信息；纯数值与单位优先使用 `EmphasizedData` |
| 次要正文与补充说明 | `{items: [{label?, value}, ...]}` | `SecondaryBody` | 分区内核心信息之外的其余补充说明，由至少两个次要字段构成；必须与同一分区内的核心数据搭配使用，不会作为该分区唯一的业务信息独立存在。适合值本身能够清楚表达含义，或多个字段需要作为简短正文连续阅读的情况；继续按实际可用宽度自适应分组和换行 | 单个补充字段不用；若去掉逐项标签后会产生“良｜中等｜低”这类无法判断字段归属的裸值组合，应改用 `TableText` 保留标签；不得用多个单项 `SecondaryBody` 模拟纵向表格；不承载核心数值，不增加背板、图标或按钮 |
| 同一实体的多维同等属性或带标签明细 | `{items: [{label, value, unit?}, ...]}` | `TableText` / `TopTextBottomValue` / `TextBlock` | 两项及以上数据属于同一实体，每项都能形成“左侧短标识 + 右侧参数”，彼此确实同等且需要逐项识别时可使用；`TableText.label` 可绑定每行的动态标识。已经存在核心组件时，如果剩余明细的值必须依赖“空气质量、紫外线、感冒指数”等逐项标签才能准确理解，也应使用 `TableText` 保留标签。`TopTextBottomValue` 仅用于“上下双区”的 `details` Region，且仅表达恰好三组数值单位数据 | 不用于自然语言正文；不得把核心字段一起塞入 `TableText` 取消主次层级；不能仅因字段可写成“标签 + 参数”、存在按钮或空间紧张就把整卡全部判定为同级；只有一项时不用这些多项组件 |
| 核心数值 + 线性进度 | `{label?, percent?, current?, total?, displayValue?: {value, unit?, qualifier?}}` | `ProgressLine2` | 存在明确方向和参照终点，需要表达“当前完成到哪里、距离目标还差多少”时使用，例如步数／目标步数、任务完成量／总量、下载或安装进度；容量占用率只有在语义明确为“已使用／总容量”时才可使用 | 手机、耳机或其他单个设备的剩余电量不用；当前状态余量、普通百分比属性、不需要核心数值槽，或必须在 Track 下方同时显示左右标签时不用 |
| 多项同指标比较 | `{items: [{label, value, unit?}, ...]}` | `H_BarChart` | 至少两项同维度数据，每项有主体标签和同一指标值，单位相同或可统一，并且需要比较大小或排序；总表中的 `BarChart` 对应真实 JSX 组件 `H_BarChart` | 只有一项时不用；同一实体的跨单位、跨类型属性且各项同等时改按多维属性选择；不能统一为同一比较尺度时不用 |
| 1 个占比值 | `{label, percent, displayValue?, secondaryLabel?, icon}` | `ProgressCircleSingle` / `InfoBlock` | 默认使用 `ProgressCircleSingle` 表达单个对象的当前占比或余量状态；需要单环右侧的 Label、Value + Unit 和可选 Secondary Label 时必须使用它。当该占比可完整表达为“主文本 + 副文本 + 尾部进度环”，并且需与另一个 `InfoBlock` 组成两个连续的 64vp 紧凑信息块时，可改用 `InfoBlock visual={{ type: "progressCircle", ... }}` | 不用于同时比较多个同级占比值；存在明确目标终点且重点是完成差距时改用 `ProgressLine2`；只有一组紧凑信息或需要显示第三行状态时不用 `InfoBlock` |
| 三个占比值 | `{items: [{percent, icon}, {percent, icon}, {percent, icon}]}` | `NumericRatioStack` | 恰好三个同级占比值需要紧凑排列，分别以 Icon 区分对象；使用 `direction` 选择横排或纵排 | 一项或两项时不用；对象必须依赖文本 Label 才能区分时不用 |
| 日程、会议、时间序列事件 | `{events: [{title, time | (dtStart + dtEnd), date?, location?}]}` | `EventCard` | 一个 `EventCard.items` 最多放两条日程；每条的标题和时间必选，地点可选；两条按时间先后排列并由组件自适应分配间距，禁止拆成两个 `EventCard` | 不用于普通提醒或无时间信息的内容；当前无月份视图组件 |
| 没有明确操作 | `{action: null}` | 不创建按钮 | 卡片仅用于信息查看 | 不为了填充版面而增加无业务意义的按钮 |

### 多字段文本选择顺序

多字段文本按以下顺序选择：

1. 先判断字段之间是否存在核心与明细层级。普通的多字段信息卡默认必须根据用户目的、问题焦点和业务语义选出一个相关性最高的动态核心字段；除非用户明确要求列表、清单、逐项查看、对比或等权汇总，不得把全部字段直接声明为同级属性。
2. 存在核心值时，每个分区只选择一个 `EmphasizedData`、`EmphasisText` 或对应进度组件作为核心信息；不得在同一分区制造第二个核心信息。剩余两项及以上补充字段根据表达清晰度选择一个 `SecondaryBody` 或一个 `TableText`：值本身自描述、适合连续阅读时使用 `SecondaryBody`；值是“良、中等、低、是、否”等离开逐项标签就无法判断含义的状态或等级时，使用 `TableText` 保留标签。
3. 静态类别标题（例如“设备状态”“天气信息”“健康指数”）只负责说明卡片主题，不是动态核心信息，不能据此省略强调组件。
4. 只有用户明确表达列表、清单、逐项查看、对比或等权汇总，并且不存在可识别的核心字段时，才能将至少两项“静态标签 + 独立动态参数”作为同级属性交给 `TableText`；字段数量多、可写成键值对、布局空间紧张或存在按钮都不是同级证据。
5. `SecondaryBody` 必须与核心组件搭配，不独立存在；多个补充字段选择它时使用一个 `SecondaryBody` 的多个 item，不得拆成多个单项组件。不得把三个及以上不同语义字段压入 `EmphasisText.secondaryText` 的一个无标签字符串；需要逐项标签时改用 `TableText`。
6. 请求进度组件但输入缺少目标值、总量或比例时，可以报告进度要求无法满足，但仍须保持核心字段的视觉层级，不得将核心值降级为普通辅助正文。

## 2. 标题组件

### 2.1 SingleLineTitle

单行标题，用于卡片内容区左上角。

标题通常是根据 `userQuery` 概括的静态 UI 文案，此时只传 `title`。当地点名、设备名、事件名等输入业务字段直接承担标题角色时，才通过 `dataIds.title` 绑定其真实 ID。动态字段需要与固定标题文案组合时，使用 `titleTemplate`，其中必须且只能包含一个 `{value}`；`title` 仍填写当前完整预览文案。这样动态字段本身只在标题展示一次，不得为了补充后缀而在正文重复。

若地点名、设备名、事件名等动态事实已经由正文组件展示，静态标题必须改用不包含该动态值的类别概括，例如正文展示“厦门”时标题使用“天气定位”，不能再写“厦门天气”。反之，标题使用 `titleTemplate="{value}天气"` 并绑定地点字段时，正文不得再次展示该地点。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `title` | `string` | 必选 | 无默认值 | 单行标题，超出可用宽度时省略 |
| `titleTemplate` | `string` | 仅当 `dataIds.title` 存在时可选；必须且只能包含一个 `{value}` | 不传时直接显示绑定值 | 把绑定值嵌入固定标题文案，例如 `{value}天气`；不能与 `dataValueMaps.title` 同时使用 |
| `dataIds` | `{ title?: string }` | `title` 来自输入数据时必选 | 不传时无绑定 | 仅允许绑定 `title` |

```jsx
<SingleLineTitle title="手机使用时长" />

<SingleLineTitle
  title="长沙天气"
  titleTemplate="{value}天气"
  dataIds={{ title: "weather.location.prefectureName" }}
/>
```

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `width` | `fit-content`，上限 `100%` | 按标题文本自然宽度占位；超出父槽时收缩并省略 |
| `height` | 18vp | 固定单行占高；超宽时省略，不增加高度 |

### 2.2 DoubleLineTitle

标题和次要信息组成的双层标题。

`title` 与 `secondaryInfo` 分别按内容来源判断是否绑定，不能因为使用双行标题就默认两项都是动态数据。任一项来自 `userQuery` 的静态概括时不绑定；来自当前输入 `data[]` 的业务值时绑定该项的真实 ID。动态值需要固定前缀或后缀时，可分别使用 `titleTemplate`、`secondaryInfoTemplate`；模板必须且只能包含一个 `{value}`，对应的完整预览文案仍填写在原显示 Prop 中。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `title` | `string` | 必选 | 无默认值 | 主标题，最多一行 |
| `secondaryInfo` | `string` | 必选 | 无默认值 | 连接状态、地点等第二层信息，最多两行 |
| `titleTemplate` | `string` | 仅当 `dataIds.title` 存在时可选；必须且只能包含一个 `{value}` | 不传时直接显示绑定值 | 给动态主标题添加固定前缀或后缀；不能与 `dataValueMaps.title` 同时使用 |
| `secondaryInfoTemplate` | `string` | 仅当 `dataIds.secondaryInfo` 存在时可选；必须且只能包含一个 `{value}` | 不传时直接显示绑定值 | 给动态次信息添加固定前缀或后缀；不能与 `dataValueMaps.secondaryInfo` 同时使用 |
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

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `height` | 16px | 固定高度 |
| `width` | `max-content`，最大 100% | 宽度随数值自适应 |

## 3. 文本组件

## 文本组件的核心与明细层级

### 3.0 核心信息与同级属性的选择顺序

选择文本组件前，必须先按用户意图在每个语义分区内将展示事实分为“唯一核心”“补充说明”或“同级属性”，再选择组件：

- 如果存在一个与用户意图相关性明显最高的字段，该字段必须由 `EmphasisText`、`EmphasizedData`、`InfoBlock` 或其他能够表达核心信息的业务组件承载；不得为了结构简单或节省高度，把它降级为 `TableText.items[].parameter`。核心字段是纯文本时使用 `EmphasisText`，是数值与单位或完整格式化数值文本时使用 `EmphasizedData`；若只有一个补充字段且不满足 `SecondaryBody` 至少两项的合同，可选择语义匹配的 `InfoBlock` 或核心组件自身允许的解释槽。
- 核心信息之外的多个补充字段按可读性选择同分区内的一个 `SecondaryBody` 或一个 `TableText`。值本身自描述、适合作为简短正文连续阅读时使用 `SecondaryBody`，并保留此前规定的自适应换行规则；值是“良、中等、低、是、否”等离开逐项标签就无法判断含义的状态或等级时，使用 `TableText` 保留每项标签。空间不足时应更换可闭合的 Layout Pattern、使用规范允许的紧凑规格或选择能够无损承载相同事实的核心组件；不得仅为通过布局校验取消核心层级并把包括核心在内的全部事实压成 `TableText`。
- 普通多字段信息卡默认必须依据用户目的、问题焦点和业务语义选出一个相关性最高的动态核心字段。静态类别标题（例如“设备状态”“天气信息”“健康指数”）只说明卡片主题，不是核心业务事实，不能代替 `EmphasisText`、`EmphasizedData` 或其他核心组件。
- 只有用户明确要求列表、清单、逐项查看、对比或等权汇总，并且两个及以上字段在用户意图中确实同级时，才能使用 `TableText` 作为唯一业务组件。已经存在独立核心组件时，`TableText` 可以承载必须依赖逐项标签才能准确理解的补充明细。左侧 `label` 可以是静态标签，也可以是每行的动态短标识。不能仅因为字段可写成“标签 + 参数”、数量较多、空间紧张或存在按钮，就把包括核心在内的全部信息判定为同级。若核心信息已经由标题表达，该标题必须真实绑定并展示用户关注的动态核心字段；普通静态标题不满足这一条件。
- `EmphasisText.secondaryText` 只承载一个次文本字段，或少量组合后仍可立即理解的紧密关联字段。单个裸数值使用 `{value}` 模板补充语义；多 ID 次文本必须使用 `{0}`、`{1}`……索引模板逐项标注。不得把三个及以上不同语义的补充字段压入同一行；这种情况应保留核心组件，并将补充字段改用带逐项标签的 `TableText`。
- 同一语义分区最多只能有一个强调核心：`EmphasisText` 和 `EmphasizedData` 合并计数，任意组合总数超过一个均为错误；只有当前 Layout Pattern 明确划分的独立业务分区才分别计算。

### 3.1 EmphasizedData

文档中名称为“强调数值”。用于展示当前分区内与用户意图相关性最高的核心数值数据，由数值与单位共同构成；单位可以通过独立 `unit` 提供，也可以已经包含在输入的完整格式化字符串中。同一分区内只允许出现一个核心信息，不得并列或堆叠多个 `EmphasizedData`，也不得再用 `EmphasisText` 重复强调另一个核心信息。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `value` | `string \| number` | 展示当前分区唯一的核心数值；只有纯文本无数值时不使用此组件（如“正常电量”“户外跑步”） | `items` 存在时忽略 | 若绑定字段是完整格式化字符串，必须原样填写样例值，例如 `"2小时15分"`；组件会自动拆分，生成代码不得自行改写 |
| `unit` | `string` | 无单位数字或纯数字字符串可使用 | 不传时不显示 | 静态单位应显式填写；完整带单位字符串不追加单位；空字符串关闭额外单位 |
| `items` | `Array<{ key?, value, unit?, dataIds? }>` | 仅用于多个数值段共同构成同一个核心数值语义时；不得承载多个彼此独立的核心信息 | 存在时覆盖顶层 `value`、`unit` | 不用于手工拆分一个完整字符串；`"2小时15分"` 仍使用顶层 `value` 和一个原始 `dataId` |
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

`unit` 与主值保持同一行。`"充电中"`、`"已连接"` 等状态不是单位；存在多个补充字段时，将它们组织进与该核心数值同分区的 `SecondaryBody`。单个状态不得冒充单位，也不得为了展示它而创建独立存在的 `SecondaryBody`。

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

文档中名称为“强调文本”。用于展示当前分区内与用户意图相关性最高的核心文本数据。`mainText` 只承载一个核心字段；紧密关联的第二字段使用 `secondaryText`，不得把两个业务字段用 `｜` 拼接在 `mainText` 中。同一分区内只允许出现一个核心信息，不得并列或堆叠多个 `EmphasisText`，也不得再用 `EmphasizedData` 重复强调另一个核心信息。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `mainText` | `string` | 必选，只能表达一个核心字段 | 无默认值 | 主文本；不得用 `｜` 拼接其他业务字段 |
| `secondaryText` | `string` | 可选 | 不传时不创建次文本行 | 与核心主文本共同构成同一核心信息的第二个文本字段；没有真实且必要的第二字段时省略，不得虚构 |
| `secondaryTextTemplate` | `string` | 单个 ID 使用一个 `{value}`；有序数组依次使用 `{0}`、`{1}`……且各出现一次 | 不传时直接显示绑定值 | 为动态次文本补充静态语义标签；`secondaryText` 仍填写完整预览文案 |
| `dataIds` | `{ mainText?: string, secondaryText?: string \| string[] }` | 对应文本来自输入数据时必选 | 不传时无绑定 | `mainText` 只绑定一个 ID；仅 `secondaryText` 在多个短字段合并后仍表达同一次要语义时可使用有序数组 |
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

运动类型是核心文本、时长是关联补充时，必须分别使用 `mainText` 和 `secondaryText`：

```jsx
<EmphasisText
  mainText="户外跑步"
  secondaryText="时长 40分"
  secondaryTextTemplate="时长 {value}"
  dataIds={{
    mainText: "healthSport.exerciseTypeName",
    secondaryText: "healthSport.exerciseDurationText",
  }}
/>
```

`mainText` 不支持多 ID 数组。两个字段存在主次关系时分别放入 `mainText` 和 `secondaryText`；更多补充字段改用 `SecondaryBody` 或 `TableText`。单个次文本值脱离标签无法理解时，使用包含一个 `{value}` 的 `secondaryTextTemplate`。多个短字段合并后仍表达同一次要语义时，`dataIds.secondaryText` 使用有序数组，并必须用索引模板为每项保留语义。

```jsx
<EmphasisText mainText="多云" secondaryText="城市 上海市 ｜ 区域 青浦区" secondaryTextTemplate="城市 {0} ｜ 区域 {1}" dataIds={{"mainText":"weather.current.condition","secondaryText":["weather.location.prefectureName","weather.location.districtName"]}} />
```

数组中每个 ID 必须真实存在、不重复，且对应 string、integer 或 number 类型的短显示字段。数组不接受 Boolean，也不与 `dataValueMaps` 组合；Boolean 状态仍使用单 ID 和同名 `dataValueMaps`。只有一个数据源时必须使用字符串 ID，不要生成单元素数组。

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `width` | `max-content`，受父槽宽度约束 | 组件不主动占满父槽 |
| `height` | 仅主文本时 20vp；包含次文本时 38vp | 主文本 20vp；存在次文本时增加 2vp 间距和 16vp 次文本行 |

### 3.3 SecondaryBody

文档中名称为“次要文本”。用于组织当前分区内核心信息之外的其余补充说明，由多个次要字段构成；必须与同一分区内的 `EmphasisText`、`EmphasizedData` 或其他核心数据搭配使用，不会作为分区内唯一的业务信息独立存在。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `items` | `Array<{ key?, label?, value, dataIds? }>` | 必选，设计规范要求至少两项补充字段 | runtime 为兼容旧 JSX 仍可渲染一项；新生成不得使用 | 每行最多显示两项，第三项起进入下一行；`value` 原样使用输入提供的完整值，并通过项内 `dataIds.value` 独立绑定；`label` 保持静态；不支持 `unit` |
| `separator` | `string` | 仅 items 模式可选 | `" ｜ "` | 只分隔同一行内的两个字段；新一行开头不显示分隔符 |

`SecondaryBody` 只使用 `items`，不使用顶层 `body` 或顶层 `dataIds`。新生成至少提供两个补充字段，每项通过自己的 `dataIds.value` 独立绑定。纯数字、百分比、时间和孤立时语义不完整的等级值必须有静态 `label`；自描述状态可以省略。`items` 不设置固定数量上限，每个行组最多两项。runtime 以 14px 字号测量字段与分隔符的实际宽度：相邻两项放得下时合组，否则整项进入下一组；单个字段超宽时允许自身换行。超过两项、出现多个行组或单字段超宽时，整个组件统一使用 12px / 16px 行高，否则使用 14px / 19px 行高。相邻行组间距 2vp，行组开头不显示分隔符。内容更新或容器宽度变化后重新测量，仍需确保实际内容不超过卡片高度。

语义相近、需要成对理解的字段应相邻排列，并优先合并显示在同一行，例如“入睡时间 + 醒来时间”“开始时间 + 结束时间”“最高温 + 最低温”。这些字段仍分别保留为独立 item 并绑定各自的 `dataId`，不得为了合并显示而拼成一个动态字符串。

`items` 不支持 `unit`。`value` 必须原样使用输入提供的完整展示值，例如 `"29.0 ℃"`、`"40分"`、`"260 千卡"`；不得拆分、补写或根据 description 推断单位。若输入只提供不含单位的数字，组件只展示该数字。

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

### 3.5 DataDisplay

由文本标签、核心数值和单位／辅助信息组成的三行纵向文本组件，用于 2×2 或 2×4 的“核心居中”单模块布局。它适合倒计时、日期等需要以一个超大数值作为唯一视觉核心的场景，不用于同一分区并列展示多组数据。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `label` | `string` | 必选 | 无默认值 | 第一行文本标签 |
| `value` | `number \| string` | 必选 | 无默认值 | 第二行核心数值；保持输入值的真实内容，不附加静态单位 |
| `supportingText` | `string` | 必选 | 无默认值 | 第三行单位或辅助信息 |
| `dataIds` | `{ value?: string }` | `value` 来自输入数据时必选 | 不传时无绑定 | 只允许绑定核心数值 `value`；`label` 与 `supportingText` 始终是静态 UI 文案，不绑定数据 ID |

静态说明文字不需要绑定。下面示例中，`label` 和 `supportingText` 是静态 UI 文案，只有动态倒计时数值绑定数据：

```jsx
<Region slot="left" variant="compact-center">
  <DataDisplay
    label="马拉松还剩"
    value={7}
    supportingText="天"
    dataIds={{ value: "marathon.remainingDays" }}
  />
</Region>
```

即使 `label` 或 `supportingText` 的显示文案与输入数据内容相同，也不得为它们填写 `dataIds`。动态更新只作用于中间的核心 `value`，不会改变三行结构、样式或布局。

#### 空间占位

| Card 尺寸 | `width` | `height` | 说明 |
|---|---|---|---|
| `2x2` | `max-content`，最大 136vp | 114vp | 三行分别占 18vp、60vp、20vp，两处垂直间距各 8vp；在 136 × 136vp 安全内容区内居中 |
| `2x4` | `100%`，最大为父槽宽度 | 112vp | 三行分别占 18vp、64vp、20vp，两处垂直间距各 5vp；可闭合于 118 × 112vp 的 Sub-118-A，也可在 140 × 136vp 的 Sub-140-A 内居中 |

2×4 模式下，组件宽度随 Sub-118-A／Sub-140-A 的父槽变化；`label`、`value` 和 `supportingText` 均保持单行，超出当前宽度时省略，不通过缩小字号或增加组件高度解决。这里的自适应只表示“宽度跟随父槽、在 112–136vp 高度的核心居中槽内闭合”，不表示任意比例缩放，也不允许进入带标题、按钮或其他业务组件的子布局。

### 3.6 InfoBlock

高度固定为 64vp、宽度填满父槽的紧凑信息组件，由主文本、副文本和背板组成，并可按需增加右侧尾部视觉。存在明确的图形识别或 0–100 占比／进度语义时，尾部视觉在 Icon 与 ProgressCircle 中二选一；没有合适视觉或需要为文本保留完整宽度时可以省略 `visual`。

**先确认槽位再选择：**2×4 的 InfoBlock 是固定槽模块，不是普通内容组件；仅用于“左内容右侧双槽”的右侧固定槽或“四槽宫格”。所有 Sub-118／Sub-140 内容区均禁止使用，包裹 Stack/Grid 也不能改变这一限制；合法 Region.slot 见layouts Skill 的语义布局接口。普通内容区的主副文本优先考虑 EmphasisText，核心数值考虑 EmphasizedData，单设备余量考虑 ProgressCircleSingle（子布局用 size="compact"）；按组件合同保留全部信息和绑定，不机械替换 Props，也不为使用 InfoBlock 虚构其他固定槽模块。2×2“双信息块”用法不变。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `primaryText` | `string \| number` | 必选 | 无默认值 | 左侧第一行核心信息；数值和文本均可，单行省略 |
| `primaryTextTemplate` | `string` | 仅当 `dataIds.primaryText` 存在时可选；必须且只能包含一个 `{value}` | 不传时直接显示绑定值 | 为动态主值增加简短静态前后缀；`primaryText` 仍填写完整预览文案 |
| `secondaryText` | `string \| number` | 必选 | 无默认值 | 左侧第二行解释信息或次要信息，单行省略；可由一个数据字段提供，也可组合多个短字段 |
| `secondaryTextTemplate` | `string` | 单个 ID 使用一个 `{value}`；有序数组依次使用 `{0}`、`{1}`……且各出现一次 | 不传时直接显示绑定值 | 为动态副文本增加静态语义标签；`secondaryText` 仍填写完整预览文案 |
| `unit` | `string` | 可选，静态 UI 文案 | 不传时不显示 | 主文本为数值时与其同行显示；不允许绑定数据 ID |
| `visual` | `InfoBlockIconVisual \| InfoBlockProgressVisual` | 可选；提供时二选一 | 不传时不显示尾部视觉，文本区域使用剩余宽度 | 右侧 Icon 或 ProgressCircle；不得同时提供两种视觉 |
| `dataIds` | `{ primaryText?: string, secondaryText?: string \| string[] }` | 对应文本来自输入数据时分别绑定 | 不传时无绑定 | `primaryText` 绑定一个 ID；`secondaryText` 绑定一个 ID，或按显示顺序绑定两个及以上 ID；`unit` 与 `visual` 不绑定 |

两行内容都必须能独立理解。动态值需要静态语义时，使用对应的 `primaryTextTemplate` 或 `secondaryTextTemplate`，不要只把标签写进显示 Prop；值本身已能说明语义时无需模板。状态值作为 `primaryText` 时必须用 `primaryTextTemplate` 标明所属对象；多个同类状态合并到 `secondaryText` 时，必须用索引模板逐项标明所属对象，不得只拼接无法区分对象的状态值。省略 `visual` 时，组件只显示主、副文本，不生成空视觉占位。提供 `visual` 时只接受两种结构：`{ type: "icon", icon, color?: "native" }` 用于图形识别；`{ type: "progressCircle", icon }` 用于 0–100 占比／进度，圆环使用绑定的原始数值，不解析模板文案。两者的 `icon` 均必选且必须来自语义匹配的 `assetCandidates`；单色 Icon 与按钮一样自动跟随 Card appearance，浅色背景使用对应主题色，深色渐变背景使用白色。仅保留原生多色外观时写 `color: "native"`。

`secondaryText` 需要由多个短字段共同组成时，`dataIds.secondaryText` 使用有序数组，并保持每个字段独立响应更新。自描述字段不传模板时由转换层用固定的 ` ｜ ` 连接；需要逐项标签时，`secondaryTextTemplate` 按数组顺序使用 `{0}`、`{1}`……。数组至少包含两个真实、非重复的 string、integer 或 number 数据 ID；只有一个字段时仍使用字符串 ID。

```jsx
<InfoBlock
  primaryText="今日步数 6200"
  primaryTextTemplate="今日步数 {value}"
  unit="步"
  secondaryText="距离 4.60 公里"
  secondaryTextTemplate="距离 {value}"
  dataIds={{ primaryText: "healthSport.dailySteps", secondaryText: "healthSport.dailyDistanceText" }}
/>
```

```jsx
<InfoBlock
  primaryText="电量 68"
  primaryTextTemplate="电量 {value}"
  unit="%"
  secondaryText="未充电｜29.0 ℃"
  visual={{ type: "progressCircle", icon: "icon_charge.svg" }}
  dataIds={{ primaryText: "battery.remainingPercent", secondaryText: ["battery.chargingStatusDesc", "battery.temperatureText"] }}
/>
```

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

### 3.8 TableText

由至少两组“左侧文本标签 + 右侧文本／数值单位参数”组成的纵向表格文本组件，用于紧凑展示同一主题下的多项属性。每组占满父容器宽度，标签左对齐，参数右对齐。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `items` | `Array<{ key?, label, parameter, dataIds? }>` | 必选，至少 2 项 | 默认空数组；runtime 可渲染已有的短数组，但少于 2 项不符合新生成规范 | 多组纵向排列；每项必须同时提供 `label` 和 `parameter` |
| `items[].label` | `string` | 必选 | 无默认值 | 左侧短标识；可使用静态标签，也可绑定一个动态字段，例如星期、日期或设备名 |
| `items[].parameter` | `string \| number` | 必选 | 无默认值 | 右侧文本或数值单位参数；来自输入数据时必须绑定 |
| `items[].dataIds` | `{ label?: string, parameter?: string \| string[] }` | 对应字段来自输入数据时必选 | 不传时无绑定 | `label` 只绑定一个 ID；`parameter` 单字段传一个 ID，组合时传两个或更多有序 ID |
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

`label` 可以是静态业务标签，也可以绑定每行的动态短标识。多日天气记录同时提供完整日期和星期时，优先把星期及其 `dataId` 放入 `label`，完整日期作为可选信息；天气、温度范围和降雨概率等详情放入 `parameter`。其他重复记录也应将日期、设备名等可区分对象的短字段放入 `label`。`parameter` 的有序数组没有数量上限，但仍应避免把彼此无关的字段堆入右列；空间不足时应按用户问题重组信息或更换布局，不用省略号隐藏超长组合。

同一行参数需要跟随两个短数据源独立更新时，使用恰好包含两个 ID 的有序数组；转换后按数组顺序使用固定的紧凑连接符 `｜`。数组中的 ID 必须真实、不重复且为 string、integer 或 number，不接受 Boolean，也不能与 `dataValueMaps` 同时使用：

```jsx
<TableText
  items={[
    {
      label: "星期四",
      parameter: "多云｜25℃/32℃",
      dataIds: {
        label: "weather.daily.0.weekday",
        parameter: [
          "weather.daily.0.condition",
          "weather.daily.0.temperatureRangeText",
        ],
      },
    },
    {
      label: "星期五",
      parameter: "晴｜24℃/33℃",
      dataIds: {
        label: "weather.daily.1.weekday",
        parameter: [
          "weather.daily.1.condition",
          "weather.daily.1.temperatureRangeText",
        ],
      },
    },
  ]}
/>
```

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `width` | `100%` | 每组及整个组件占满父容器分配的宽度 |
| `height` | 两项时自然高度 34vp；三项及以上填满父槽 | 常规每项 16vp。恰好两项时组件不填满父槽，两行以固定 2vp 间距紧邻排列；三项及以上均分父槽剩余高度。在不超过 120vp 的窄槽内，三项及以上每项使用 24vp 紧凑双行规格 |
| `row-overflow` | Label 完整、Parameter 自适应 | 左侧短 Label 使用自然宽度且保持单行完整；常规宽度下右侧 Parameter 单行省略，窄槽三项及以上时允许最多两行，超过两行才省略 |

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

- 2×2 与 2×4 Card 均可使用；2×4 由 `Region.variant` 决定它占据的模块。
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
| `size` | `"compact"` | 仅在 2×4 Layout Pattern 的 Sub-118／Sub-140 子布局中、2x2 Layout Pattern 的紧凑内容双按钮 中必选；其他布局省略 | 省略时使用 52 × 52vp 默认圆环；`"compact"` 使用 44 × 44vp 圆环 | compact 规格与 `ProgressCircle size="sm"` 的圆环直径一致，并收紧右侧文本的纵向行盒 |
| `trackColor` | `string` | 仅实现层覆盖 | 使用组件默认值 | `appearance="card"` 时会被卡片模式覆盖 |
| `barColor` | `string` | 仅实现层覆盖 | 设计规范绿色 | `appearance="card"` 时会被卡片模式覆盖 |
| `dataIds` | `{ value?: string, displayValue?: string, label?: string, secondaryLabel?: string }` | 对应字段来自输入数据时必选 | 不传时无绑定 | `value` 必须绑定实际进度数据；其余可见文本按输入字段分别绑定 |

`ProgressCircleSingle` 与 `ProgressCircle` 的生成合同不同：`ProgressCircle` 使用唯一的 `externalText` 同时驱动圆环和外部百分比文本；`ProgressCircleSingle` 必须显式提供 `value` 驱动圆环，并允许用可选的 `displayValue` 显示另一项绝对值。不得因为 `ProgressCircle.value` 属于 runtime 兼容属性，就省略 `ProgressCircleSingle.value`。

`value` 优先绑定 number／integer 类型的原始百分比。当输入没有独立数值字段、只提供语义明确的完整格式化百分比字符串时，也可以直接绑定该字符串；runtime 会使用其中的数字驱动圆环，并原样显示百分比文本。该兼容方式只适用于完整百分比字符串，不接受普通文本或混合文案。

动态数值 `value` 省略 `displayValue` 时会直接显示实时数值和 `%`。当圆环百分比和可见百分比来自同一个数据 ID 时，只写 `value` 与 `dataIds.value`，禁止再把同一 ID 重复绑定到 `displayValue`；runtime 与后续转换层会将历史 JSX 中这种重复绑定归一化为 `value + %`。只有需要显示另一项独立数据，例如“已用 43.75%”的圆环旁显示“4.5GB 可用”，才同时提供并分别绑定 `value` 与 `displayValue`。

当组件位于 2×4 Layout Pattern 的 Sub-118 或 Sub-140 子布局和 2×2 Layout Pattern 的紧凑内容双按钮布局时，必须显式传入 `size="compact"`。compact 只改变圆环直径和右侧文本行盒，不改变字段语义、数据绑定、字体大小、字重、颜色、水平间距或中心 Icon 尺寸；除“紧凑内容双按钮”之外的 2×2 布局，以及不属于 Sub-118／Sub-140 子布局的 2×4 场景，继续省略 `size`，使用默认规格。

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

2×4 子布局和紧凑内容双按钮布局中的 compact 示例：

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
| `height-compact` | 两行 44vp；三行 46vp | `size="compact"` 仅用于 2×4 的 Sub-118／Sub-140 子布局和2x2 Layout Pattern 的紧凑内容双按钮布局；三行文本比 44vp 圆环高 2vp |

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

同时展示两个同级占比值时，使用 `wide-title-double-progress`，将两个 `ProgressCircle` 作为 Region 标题后的直属内容组件；程序负责横排、居中和等宽分配：

```jsx
<Region slot="main" variant="wide-title-double-progress">
  <SingleLineTitle title="设备电量" />
  <ProgressCircle
    ...
  />
  <ProgressCircle
    ...
  />
</Region>
```

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `width` | 至少 44vp | 由 44vp 圆环或更宽的外部数值文本决定 |
| `height` | 60vp | 44vp 圆环、2vp 间距、14vp 外部数值文本 |

> `density="compact-4"` 仅由 runtime 暂时兼容旧 JSX，新生成契约已禁止该属性；四值场景统一使用 `size="sm"`。

### 4.6 NumericRatio 与 NumericRatioStack

`NumericRatio` 是单项数值占比的内部单元。2×4 语义 JSX 仅在紧凑展示恰好三个同级占比值时使用一个 `NumericRatioStack`，不得直接输出多个 `NumericRatio` 或使用 `Stack/Grid` 包装。一项或两项不得使用 `NumericRatioStack`。不得在 `value` 中增加“耳机盒”“左耳”等纯文本 Label；对象语义必须由对应 Icon 表达。若 Icon 无法充分区分对象，应改选带文本 Label 槽的组件。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `icon` | `string` | 必选 | 无默认值 | 对象 Icon；使用当前输入中语义匹配的候选资源 `src` |
| `value` | `string \| number` | 必选 | 数字值截去小数部分并默认补 `%`，字符串原样显示 | 动态原始百分比使用数字，例如 `43.75` 可见为 `43%`；已有完整展示文本时可使用 `"43%"` |
| `unit` | `string` | 裸数字的新生成 JSX 显式填写 | 旧 JSX 数字值兼容默认 `%`，字符串默认空 | 静态单位；完整带单位字符串不重复追加；传空字符串关闭默认百分号 |
| `appearance` | `"card"` | 生成 Card 必选 | 默认 img 模式 | 启用卡片 Icon mask |
| `dataIds` | `{ value?: string }` | `value` 来自输入数据时必选 | 不传时无绑定 | 仅允许绑定 `value`；Icon 和静态单位不得绑定 |

`NumericRatioStack` 属性：

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `items` | `Array<{ key?, icon, value, unit?, dataIds? }>` | 必选，恰好 3 项 | 无默认内容 | 每项合同与 `NumericRatio` 相同；缺少第三项时改选其他组件，不得补造数据 |
| `direction` | `"row" \| "column"` | 必选 | `"column"` | 横排占满父槽宽度并按可用空间均匀分布各项；纵排使用 4vp 间距 |
| `appearance` | `"card"` | 必选 | 默认 img 模式 | 统一启用卡片 Icon mask |

```jsx
<NumericRatioStack
  direction="row"
  appearance="card"
  items={[
    { icon: "earphone_case.svg", value: 80, unit: "%", dataIds: { value: "earbuds.caseBatteryPercent" } },
    { icon: "left_ear.svg", value: 76, unit: "%", dataIds: { value: "earbuds.leftBatteryPercent" } },
    { icon: "right_ear.svg", value: 74, unit: "%", dataIds: { value: "earbuds.rightBatteryPercent" } },
  ]}
/>
```

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `height` | 16vp | 单个 `NumericRatio` 固定占高；横排共 16vp，纵排高度由项数和 4vp 项间距决定 |
| `width` | 横排为父槽宽度；纵排为 `max-content` | 横排根据父槽宽度自动压缩内部间距并均匀分布，三个百分比可在 118vp 内容槽内完整显示；纵排保持自然宽度 |

### 4.7 EventCard

时间线式日程组件，由圆圈、装饰线、日程标题、时间和可选地点组成。组件宽度由父布局槽位决定：2×2 中最大为 116vp；2×4 中取消该上限并使用父槽提供的完整可用宽度。

`EventCard` 是一个完整的日程组组件，通过 `items` 承载一条或两条日程；一张卡片最多只能生成一个 `EventCard`，不得把两条日程拆成两个独立的 `EventCard`。两条日程按时间先后排列：组件优先使用 8vp 条目间距；若两条日程的实际内容高度加 8vp 后超过父槽，则自动降为 4vp。间距只能是 8vp 或 4vp，不使用 `space-between` 把两条日程推到父槽上下两端。该间距由组件内部处理，模型不得在两条日程之间添加 `Stack`、固定 `gap`、空白占位或其他业务组件。

`EventCard.items[].title` 表示某一条具体事件的标题，例如“产品发布会”或“医院复查”；它不是整张卡片或内容区的标题，不能自动替代 `SingleLineTitle`。当所选 Layout Type 包含标题区时，必须在该标题区另外生成 `SingleLineTitle`，再把整个 `EventCard` 放入下方内容区。只有所选 Layout Type 明确允许无标题，并且省略后仍不会丢失卡片对象、时间范围或必要上下文时，才可以只显示 `EventCard`。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `items` | `Array<{ title: string, time: string, location?: string, dataIds?: { title?: string, time?: string \| [string, string], location?: string } }>` | 必选，长度只能为 1–2 | 无默认值 | 按时间先后排列的日程；每项的 `title`、`time` 必选，`location` 可选 |
| `density` | `"compact"` | 仅 2×4 多条日程且普通高度无法闭合时使用 | 不传时使用普通模式 | 紧凑模式标题固定一行，时间与地点合并到下一行，整体高度固定为 32vp |
| `items[].dataIds` | `{ title?: string, time?: string \| [string, string], location?: string }` | 对应字段来自输入数据时必选 | 不传时无绑定 | `title`、`location` 各绑定一个 ID；`time` 绑定一个时间 ID，或按 `[dtStartId, dtEndId]` 绑定开始与结束两个 ID，不要绑定 `entityId` |

每个 item 的 `title`、`location` 和只绑定一个 ID 的 `time` 若在 `userQuery` 中有明确的当前值，而同义数据字段的 `value` 只是不同的预览样例，item 中的显示值使用 `userQuery` 中的值，`dataIds` 仍绑定该字段原有 ID。`time` 绑定开始和结束两个 ID 时，仍按二者的样例值组合预览，不把一段查询文本猜测拆回两个字段。

```jsx
<EventCard
  items={[{
    title: "产品评审",
    time: "09:30 – 10:30",
    location: "A区会议室",
    dataIds: {
      title: "calendar.nextEvent.title",
      time: ["calendar.nextEvent.dtStart", "calendar.nextEvent.dtEnd"],
      location: "calendar.nextEvent.location",
    },
  }]}
/>
```

当开始时间和结束时间分别来自两个数据字段时，`time` 保留完整的预览文本，`dataIds.time` 必须按“开始、结束”的顺序传入二元数组。运行时数据更新后，两项会继续组合显示为 `开始时间 – 结束时间`；不得只绑定 `dtStart` 后把 `dtEnd` 静态写入 `time`。

只有开始时间、没有结束时间时，`dataIds.time` 仍使用单个字符串 ID；不要传单元素数组。没有地点数据时省略 `location` 及对应绑定，不生成空字符串或虚构地点：

```jsx
<EventCard
  items={[{
    title: "设计评审",
    time: "10:30",
    dataIds: {
      title: "calendar.nextEvent.title",
      time: "calendar.nextEvent.dtStart",
    },
  }]}
/>
```

2×4 中展示两条日程、普通模式总高度无法闭合时，在同一个 `EventCard` 上使用紧凑模式。它仍保留每条事件的标题、时间、地点和原始绑定；紧凑日程组优先放入 140vp 连续内容区，不放进 118vp 背板子槽，也不得为了缩小高度改用无法承载这些绑定的静态标签：

```jsx
<EventCard
  density="compact"
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
/>
```

EventCard 不提供业务 `width` Prop，也不根据绑定后的文本长度临时改变布局。父级布局负责按当前尺寸的 Layout Pattern 分配宽度：2×2 中组件在父槽位内使用 `width: 100%` 且最大不超过 116vp；2×4 中不设置最大宽度，应使用父槽提供的完整可用宽度，不得在右侧仍有可用空间时保留无意义空白并提前换行。

2×4 中优先让 `EventCard` 独占所选“标题单内容”子布局的内容槽，并使用完整可用宽度。辅助 `SecondaryBody` 不应作为同一横排兄弟挤压日程正文；确需保留时，应放入独立的纵向信息槽，并重新检查标题、时间和地点所需高度。

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `width` | `100%` | 占满父布局为它分配的槽位宽度 |
| `max-width` | 2×2 为 116vp；2×4 为 `none` | 2×4 使用父槽完整可用宽度，避免右侧有空间时标题仍提前换行 |
| `min-width` | `0` | 允许缩小到父槽位宽度，例如 2×2“标题锚点内容”的 88vp 左下区域 |
| `height` | 按内容自然撑高 | 单条普通模式 34–68vp、紧凑模式 32vp；两条日程作为一个整体按内容自然撑高，不占满父槽，由外层布局的 `justify` 决定整组的顶部、居中或底部对齐；条目间距优先为 8vp，父槽空间不足时为 4vp |
| `title-lines` | 1–2 行 | 标题换行会增加 18vp 高度；时间和地点各固定占 16vp |

## 5. 按钮组件

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

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `size` | 默认 136 × 36vp；2×4“左右双区”背板内 118 × 36vp | 背板内通过 runtime 上下文样式自动切换；不新增尺寸 Prop，也不拉伸为整卡宽度 |

# 2×4 专属组件

本文件只在当前任务 `Card.size="2x4"` 时加载。

## 1. 文本组件

### 3.7 TopTextBottomValue

仅用于 2×4“上下双区”布局的 `details` Region，并且必须作为该 Region 的直属组件。禁止放入“左右双区”“左内容右侧双槽”“四槽宫格”，也禁止用于任何 Sub-118／Sub-140 内容槽。每组按“文本标签 → 数值 → 单位”纵向排列，两组及以上横向 `space-around` 分布。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `items` | `Array<{ key?, label, value, unit, dataIds? }>` | 必选，至少 2 项 | 默认空数组；少于 2 项不符合生成规范 | 多组指标，顺序与输入语义一致 |
| `items[].label` | `string` | 必选，静态 UI 文案 | 无默认值 | 上方文本标签，不绑定数据 ID |
| `items[].value` | `string \| number` | 必选 | 无默认值 | 中间核心数值；来自输入时必须绑定 |
| `items[].unit` | `string` | 必选，静态 UI 文案 | 无默认值 | 下方单位，不绑定数据 ID |
| `items[].dataIds` | `{ value?: string }` | `value` 来自输入数据时必选 | 不传时无绑定 | 只允许绑定同一项的 `value` |

#### 空间占位

| 占位属性 | 2×4 规格 |
|---|---|
| `width` | 占满 296vp 父模块；不提供自由 size Prop |
| `height` | 68vp；三行分别占 18vp、32vp、18vp，无额外垂直间距 |
| `item-width` | 按内容自然决定；多个 item 横排且不拉伸或均分 |
| `overflow` | 三行均保持完整单行，不支持省略号；内容总宽度放不下时当前组件组合无效 |

### 3.9 TextBlock

仅用于 2×4 卡片的横向背板文本组。每项由静态文本标签和文本／数值单位参数组成，至少两项。组件占满父容器宽度；所有背板等分可用宽度，相邻项固定间距 8vp。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `items` | `Array<{ key?, label, parameter, dataIds? }>` | 必选，至少 2 项 | 默认空数组；少于 2 项不符合新生成规范 | 多组横向排列，顺序与输入语义一致 |
| `items[].label` | `string` | 必选，静态 UI 文案 | 无默认值 | 背板内上方文本标签，不绑定数据 ID |
| `items[].parameter` | `string \| number` | 必选 | 无默认值 | 背板内下方文本或数值单位参数；来自输入时必须绑定 |
| `items[].dataIds` | `{ parameter?: string }` | `parameter` 来自输入数据时必选 | 不传时无绑定 | 只允许绑定同一项的 `parameter`；不得包含 `label` 或其他 key |

#### 空间占位

| 占位属性 | 2×4 规格 | 说明 |
|---|---|---|
| `width` | `100%` | 占满父容器分配的完整宽度 |
| `item-width` | 等分剩余宽度，最小 64vp | 所有项使用相同弹性宽度并共同撑满父容器 |
| `height` | 自适应 48–64vp，默认 64vp | 跟随父级纵向槽在该范围内收缩；大于 64vp 时仍为 64vp，小于 48vp 时不再继续压缩 |
| `items-gap` | 8vp | item 宽度按 `(父容器宽度 − 间距总和) ÷ 项数` 计算 |
| `overflow` | 两行均单行省略 | 文本不换行，不增加组件高度 |

## 2. 按钮组件

### 5.3 CardButton

卡片按钮，由必选文本、可选资源 Icon（缺省时显示圆形占位 Icon）和按钮容器组成，仅用于 320 × 160vp（2×4）Card 中两个及以上 Action 的紧凑操作区。组件本身不声明固定宽高，而是占满父容器分配的半卡宽槽位或 2×2 操作网格槽位。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `text` | `string` | 必选；建议约 4 个汉字 | 无默认值 | 按钮内可见操作文本，同时构成按钮的可访问名称 |
| `icon` | `string` | 可选 | 不传时由 runtime 在尾部显示 24 × 24vp 圆形占位 Icon | 有语义匹配候选时逐字使用当前输入 `assetCandidates[].src`；没有匹配候选时省略该 Prop，不得虚构资源路径，占位 Icon 不需要也不允许通过 `icon` Prop 指定 |
| `actionId` | `string` | 启用状态必选 | 不传时无动作绑定 | 原样引用输入 `actions[].id`；一个按钮只能引用一个动作，同一动作不得被其他按钮重复引用 |

`container`、`width`、`height` 和 `direction` 都不是 `CardButton` 的 JSX Props：容器尺寸由父布局负责，runtime 固定使用横向排列，生成模型不得显式控制方向。

```jsx
<CardButton
  text="播放音乐"
  icon="music_fill.svg"
  actionId="media.play"
/>
```

```jsx
<CardButton
  text="查看详情"
  actionId="content.openDetails"
/>
```

上例没有可用资源 Icon，runtime 会自动在按钮右侧生成圆形占位 Icon；生成 JSX 保持省略 `icon`，不要填写不存在的资源名称。

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `width` | `100%` | 继承并占满父 Layout Pattern 分配的模块宽度，不固定为示例值 |
| `height` | 父槽高度，限制在 48–64vp | 组件占满父槽；低于 48vp 时仍按 48vp，高于 64vp 时仍按 64vp |
| `overflow` | 文本单行省略 | 文本不换行，不增加组件高度 |
