# 卡片信息处理

### A1. 定义问题与主次

1. 根据 intent 和真实使用场景，写出用户看卡时要回答的问题。
2. 每个信息组只回答一个问题；数据平铺时按语义归入对应信息组。
3. 按以下顺序确定主次：
   - 真汇总关系：总计、总数、完成率等汇总为主，构成它的明细为次。
   - 意图焦点：没有真汇总时，以 intent 点名内容为主，点名顺序就是优先级。
   - 结构兜底：intent 模糊时，概括优先于明细。
   - 行动或告警特例：卡片目标是促成操作时，行动焦点可高于汇总。
4. 只允许一个主问题。不要把“相关”误判为“汇总”。

### A2. 归组、核查与取舍

1. 把每条候选数据归入一个问题；无法服务任何问题的内容标记为丢弃。
2. 核查算术、单位、时间范围、百分比、总分关系和语义一致性。
4. 只用卡面现有数据即可推导且无独立决策价值的字段可以丢弃；有摘要或行动价值的内容保留并说明原因。
5. 补齐被选字段不可缺少的单位、主语、基准期和时间范围；不得补造输入不支持的事实。
6. 只有表达完成度、达成率、使用率、剩余占比或其他真实比例关系的百分比，才按进度处理。湿度、概率等普通百分比属性如果只是辅助事实，应作为辅助文本，不得仅因数值带 `%` 就选择进度组件。同一对象中的 `percent`、`current`、`total` 与可用量、剩余量或当前量共同构成一个进度关系，不拆成多个独立数据性质；`percent` 优先驱动进度，缺少时才使用 `current ÷ total × 100`。当真实比例只提供格式化百分比字符串（例如 `"68%"`、`"43.75%"`）时，该字段仍视为可驱动进度的 percent；字符串必须完整匹配“数字 + `%`”格式，不得从“剩余68%”“约68%”等混合文案中猜测数值。单个此类占比不得仅因输入类型为 string 退化为 `EmphasizedData`。手机电量、耳机仓电量等单个设备的剩余电量表示“当前余量状态”，不是朝目标推进的完成进度；默认使用 `ProgressCircleSingle`，当它与另一组“主文本 + 副文本 + 尾部视觉”的紧凑信息共同构成两个 64vp 信息块时，也可使用 `InfoBlock` 的 `visual.type="progressCircle"` 表达。即使输入同时提供 `current`、`total=100` 或格式化百分比，也不得仅为了突出数值改用 `ProgressLine2`。`total` 默认只用于计算或提供上下文，不直接显示。
7. 区分普通清单与日程事件：条目顺序不表达时间关系时按清单处理；时间是事件成立或排序的核心条件时按日程处理，同一条数据不得重复映射。
8. 丰富信息中的非核心数字属性可以作为辅助文本组织，不因包含数字就单独提升为核心单值；多个次要字段统一使用“｜”分隔，不使用“·”。
9. 优先选择可直接展示的描述性字符串。原始 boolean 优先用于组件自身的 boolean 状态 Prop；没有描述性字符串但该状态对用户确有价值时，可通过完整 `dataValueMaps` 声明 `true`／`false` 两种文案。不得直接显示 `true`／`false`，也不得只根据当前样例值写死一个状态；不重要的状态仍应省略。
10. `userQuery` 中明确给出的当前事件名、对象名、地点、时间或状态优先于同义单一数据字段的预览样例值。当两者冲突时，字段表保留 `userQuery` 中的具体值，并继续记录该动态字段原有的 `dataId`；预览样例只用于 `userQuery` 没有给出对应具体值的情况。同一显示 Prop 绑定多个 ID 时，不根据查询文本猜测各字段的拆分值。

### A3. 输出并冻结字段表

字段表至少包含：

| 序 | 问题 | 字段类型 | 字段内容 | 层级 | 来源/处理 |
|---:|---|---|---|---|---|
| 0 | 标题 | 值 | … | 主 | intent |
| 1 | 主问题 | 标签/值 | … | 主 | data |
| 2 | 次问题 | 标签/值 | … | 次 | data |
| 3 | 无关问题 | 标签/值 | … | 与意图无关 | data（丢弃） |

- 默认保留标题。只有用户明确允许无标题，且省略不会丢失对象、时间范围或必要上下文时，才采用无标题策略。
- 标签和值应保持语义配对，不得拆分到不同问题中。
- “与意图无关”的字段只在字段表中记录并标记为丢弃，不进入组件选择、布局、数据绑定或最终卡片。
- 对最终展示的动态字段保留输入 `data` 中的原始数据 `id`。选定真实 JSX Prop 后，按 [`components_common.md`](./components/components_common.md) 与当前尺寸加载的专属组件文档记录 `dataIds`／`actionId`。
- 在表后记录主次依据、纠错、丢弃、取舍和未映射项。
- 冻结后，HOW 不得重新选择字段、改变主次或把次问题提升为主问题。

### B1. 组件候选原则

1. 逐项读取字段表，保留所有符合条件的组件候选；不得凭经验提前锁定一个组件。
2. 一个问题包含多个性质时，先分别映射，再组合为同一个语义组。
3. 数据性质不等于唯一视觉组件。空间不适配时，只能在同一性质允许的候选中切换。
4. 次要或辅助信息优先考虑紧凑组件或尺寸变体；换组件不得改变字段内容、数据性质和信息层级。
5. 当前候选均不适配时，先更换 Layout Pattern；仍不适配则停止并报告，不得拼假组件、删字段或跨区域移动信息。
6. 总表明确限定组件与 Layout Pattern 的组合时，必须同时满足组件语义、卡片 `size` 和布局槽位，不得只根据组件外观选型。
7. 要求占满模块宽度的组件，其组件包装层必须显式占满可用宽度并允许收缩；不得依赖内容宽度决定 Track 或背板宽度。

### B2. 从信息语义选择具体组件

先判断信息承担的角色，再判断同类数据的数量，最后判断是否需要操作入口。下表中的“字段结构示例”描述输入信息的语义结构，不是可以直接复制到 JSX 的 Props；选定组件后，必须再按照当前尺寸加载的组件文档将字段映射为真实 JSX Props。

| 数据性质 / 信息形态 | 字段结构示例 | 选择组件 | 选择条件 | 不应选择的情况 |
|---|---|---|---|---|
| 单层标题 | `{title}` | `SingleLineTitle` | 只有一行纯文本标题 | 标题还需要表达连接状态、地点等第二层信息时不用；不向该组件添加 Icon |
| 标题 + 次要信息 | `{title, secondaryInfo}` | `DoubleLineTitle` | `title` 与 `secondaryInfo` 均有独立语义，例如设备名称 + 连接状态 | 不要把普通说明文字放进 `secondaryInfo`；不向该组件添加 Icon |
| 标题中的数量 | `{title, count: number \| formattedNumber}` | `Badge` | 未读数、总数、数量等与标题绑定的数值；字符串只用于 `99+` 等格式化数值 | 不用于状态、类别、普通标签或说明文字 |
| 纯单值 | `{label?, value, unit? / supportingText?}` | `DataDisplay` / `EmphasizedData` | 不包含目标、基准、等级、时间轴、分段或进度关系的数值事实。先以整张卡片为单位统计数据叙事：有且仅有一个完整数据叙事，结构为 `label + value + unit／supportingText`，且不存在标题、操作或其他并列数据事实时，选择 `DataDisplay` 并固定使用无标题的 Type 0；丰富信息中的主要数值，或只有数值与可选单位时，选择 `EmphasizedData` | 不得为了选择 `DataDisplay` 将天气状态、空气质量、最高温度、最低温度等并列事实拼成一条辅助信息；进度关系中的绝对值不重复映射为纯单值；区间档位、可比较数据或多维同等属性不用 |
| 重点短语 + 次级短语 | `{mainText, secondaryText}` | `EmphasisText` | 主文本和次文本共同表达一个重点状态，例如“86分 / 良好” | 只有一个文本时不用；纯数值与单位优先使用 `EmphasizedData` |
| 辅助正文 | `{body}` | `SecondaryBody` | 需要按自然语言连续阅读的正文级说明、描述或结论，通常与核心数据属于同一信息组；单个完整字段使用 `body`，少量字段只有在合并后仍是一句自然语言时才使用 `items` | 两项及以上能够稳定拆成“静态标签 + 独立动态参数”的并列属性不得使用，应选择 `TableText`；不得用多个单项 `SecondaryBody` 模拟纵向表格；紧凑元信息、来源、更新时间优先使用 `Summary` |
| 紧凑辅助信息 | `{content}` | `Summary` | 元信息、结果说明、体感、湿度、时间范围等紧凑辅助内容；可以承载丰富信息中的非核心数字属性；多个次要字段使用“｜”分隔，作为并列动态指标 | 不承载核心数值，不增加背板、图标或按钮 |
| 同一实体的多维同等属性 | `{items: [{label, value, unit?}, ...]}` | `TableText` / `TopTextBottomValue` / `TextBlock` | 两项及以上数据属于同一实体，每项都能形成“静态标签 + 独立动态参数”，彼此同等且需要逐项识别。含文本或空间紧凑时优先选择 `TableText`；全为数值单位且宽度充足时可选择 `TopTextBottomValue` 或 `TextBlock`。`TopTextBottomValue` 仅用于恰好三组数值单位数据 | 不用于自然语言正文；存在核心值与明细层级时，核心值单独使用对应核心组件，其余两项及以上明细使用 `TableText`；多项数据属于同一指标并需要比较大小或排序时不用；只有一项时不用这些多项组件 |
| 核心数值 + 线性进度 | `{label?, percent?, current?, total?, displayValue?: {value, unit?, qualifier?}}` | `ProgressLine2` | 存在明确方向和参照终点，需要表达“当前完成到哪里、距离目标还差多少”时使用，例如步数／目标步数、任务完成量／总量、下载或安装进度；容量占用率只有在语义明确为“已使用／总容量”时才可使用 | 手机、耳机或其他单个设备的剩余电量不用；当前状态余量、普通百分比属性、不需要核心数值槽，或必须在 Track 下方同时显示左右标签时不用 |
| 多项同指标比较 | `{items: [{label, value, unit?}, ...]}` | `H_BarChart` | 至少两项同维度数据，每项有主体标签和同一指标值，单位相同或可统一，并且需要比较大小或排序；总表中的 `BarChart` 对应真实 JSX 组件 `H_BarChart` | 只有一项时不用；同一实体的跨单位、跨类型属性且各项同等时改按多维属性选择；不能统一为同一比较尺度时不用 |
| 1 个占比值 | `{label, percent, displayValue?, secondaryLabel?, icon}` | `ProgressCircleSingle` / `InfoBlock` | 默认使用 `ProgressCircleSingle` 表达单个对象的当前占比或余量状态；需要单环右侧的 Label、Value + Unit 和可选 Secondary Label 时必须使用它。当该占比可完整表达为“主文本 + 副文本 + 尾部进度环”，并且需与另一个 `InfoBlock` 组成两个连续的 64vp 紧凑信息块时，可改用 `InfoBlock visual={{ type: "progressCircle", ... }}` | 不用于同时比较多个同级占比值；存在明确目标终点且重点是完成差距时改用 `ProgressLine2`；只有一组紧凑信息或需要显示第三行状态时不用 `InfoBlock` |
| 2 个占比值 | `{items: [{percent, icon}, {percent, icon}]}` | `ProgressCircle` × 2 | 两个同级对象并列，每项显示圆环、Icon 和取整后的 External Text；2×2 卡片使用 Type 12 | 1 个值改用 `ProgressCircleSingle`；3 个值改用 `NumericRatioStack`；逐项纯文本 Label 必须可见时不用 |
| 3 个占比值 | `{items: [{percent, icon}, {percent, icon}, {percent, icon}]}` | `NumericRatioStack` | 三个 Icon + 取整后的百分比纵向排列，无 Bar；对象语义由 Icon 或模块标题承载 | 不用于 1、2 或 4 个占比值；逐项纯文本 Label 必须可见时不用 |
| 4 个占比值 | `{items: [{percent, icon}, {percent, icon}, {percent, icon}, {percent, icon}]}` | `ProgressCircle` × 4 | 四个同级对象使用紧凑圆环，每项显示取整后的百分比并可独立识别；2×2 卡片使用 Type 6 | 不通过 `NumericRatioStack` 表达四项数据；逐项纯文本 Label 必须可见时不用 |
| 两组紧凑主副文本 | `{groups: [{primaryText, secondaryText, unit?, visual?}, {primaryText, secondaryText, unit?, visual?}]}` | `InfoBlock` × 2 | 完成基础性质识别后再判定：同一张卡片中有且仅有两组可独立理解的信息，每组都具有一个主文本和一个副文本槽位；有明确图形识别或占比语义时可增加 Icon 或 ProgressCircle 尾部视觉，没有合适视觉或文本需要完整宽度时省略 `visual`。单设备剩余电量可作为其中一组，使用 `primaryText={percent}`、静态 `unit="%"` 和 `visual.type="progressCircle"`。总表中的 `InfoTile` 对应真实 JSX 组件 `InfoBlock`；命中后两组分别映射一个 `InfoBlock`，2×2 使用无独立标题的 Type 3，2×4 可将它们放入同一内容列，并将 Action 保留在独立操作区 | 只有一组、三组及以上或任一组缺少主、副文本槽位时不用；不得为满足旧视觉结构虚构 Icon；普通百分比仅作为副文本事实时不得据此启用 ProgressCircle；聚合后不得再重复实例化内部来源组件 |
| 日程、会议、时间序列事件 | `{events: [{title, time | (dtStart + dtEnd), date?, location?}]}` | `EventCard` | 每条事件的标题和时间必选；只有开始时间时绑定单个时间 ID，开始与结束分字段时共同组成一个时间范围；日期和地点可选；多条事件按时间先后排列 | 不用于普通提醒或无时间信息的内容；当前无月份视图组件 |
| 2×2 操作 | `{cardSize: "2x2", action: {label?, icon?, ariaLabel?}}` | `PillButton` / `CircleButton` | 先检查标题和必需内容完整呈现后，底部是否仍能留出 `8vp` 间距和 `136 × 36vp` 操作槽；能留出时优先使用带明确操作文本的 `PillButton`，Icon 可选。只有无法容纳该底部槽、但右下 `36 × 36vp` 槽可安全避让内容，且操作仅靠 Icon 也能明确表达时，才使用 `CircleButton`，并将完整操作名称写入 `ariaLabel` | 不得仅因 action 提供 Icon 就选择 `CircleButton`；`CircleButton` 不得用于 2×4；不得补造缺失的操作语义或 Icon |
| 2×4 单 Action 组 | `{cardSize: "2x4", actions: [oneAction]}` | `PillButton` | 同一语义组／操作区域恰好一个 Action 时使用；操作文本必选、Icon 可选；放入该组所属的半卡宽父区，不得横跨整卡 | 不得使用 `CardButton` 近似替代；缺少操作文本时停止并报告；不得使用 `CircleButton` |
| 2×4 多 Action 组 | `{cardSize: "2x4", actions: [actionA, actionB, ...]}` | `CardButton` | 同一语义组／操作区域有两个及以上 Action 时使用；两个 Action 可在半卡宽操作父区上下竖排，三个或四个 Action 可组成 Type 9 的 2×2 操作网格 | 禁止只做一行左右并排或生成整卡宽按钮；缺少操作文本时停止并报告；同一个 Action 只能表达一次 |
| 没有明确操作 | `{action: null}` | 不创建按钮 | 卡片仅用于信息查看 | 不为了填充版面而增加无业务意义的按钮 |

多字段文本按以下顺序选择：

1. 先判断字段之间是否存在核心与明细层级。
2. 存在核心值时，核心值使用 `EmphasizedData`、`EmphasisText` 或对应进度组件；剩余两项及以上明细使用 `TableText`。
3. 不存在主次且至少两项均可拆成“静态标签 + 独立动态参数”时，优先使用 `TableText`，不得使用多个 `SecondaryBody` 分行模拟。
4. 只有内容需要作为完整句子连续阅读时，才使用 `SecondaryBody`。
5. 请求进度组件但输入缺少目标值、总量或比例时，可以报告进度要求无法满足，但仍须保持核心字段的视觉层级，不得将核心值降级为普通辅助正文。

`ProgressCircleSingle`、`InfoBlock` 的进度环分支与 `ProgressLine2` 按以下顺序区分：

1. 先判断是否为单个设备的电量、剩余容量或其他当前余量状态；是则同时保留 `ProgressCircleSingle` 和 `InfoBlock` 进度环分支两个候选，不在此处提前锁定。
2. 需要独立的 Label、可见占比和可选第三行状态，或没有第二个可配对的紧凑信息块时，选择 `ProgressCircleSingle`。
3. 当卡片恰好有两组可独立理解的紧凑信息，两组都具备主文本、副文本，并可各自完整放入 136 × 64vp 槽位时，选择两个 `InfoBlock`；尾部视觉按数据语义可选，不得为了凑结构虚构 Icon，设备电量所在组可使用 `visual.type="progressCircle"`。卡片另有独立 Action 不影响此配对，Action 继续放入对应操作区。
4. 否则判断数据是否具有明确方向和终点，并且用户关心“当前完成到哪里、距离目标还差多少”；是则选择 `ProgressLine2`。
5. “手机电量 68%”单独展示时使用 `ProgressCircleSingle`；它与“当前温度 31℃／多云”组成两个紧凑信息块时，可使用两个 `InfoBlock`；“今日 5860／10000 步”“任务完成 7／10”“下载 68／100”表示目标或过程进度，使用 `ProgressLine2`。
6. “已用存储 43%”只有在卡片问题明确关注已用量相对于总容量的占用关系时才使用 `ProgressLine2`；若表达的是单个对象当前还剩多少，则按上述组合条件在 `ProgressCircleSingle` 与 `InfoBlock` 之间选择。

`ProgressCircleSingle` 右侧的 Label、Value、Unit 和 Secondary Label 属于单环内部文本组，不再分别实例化 `EmphasizedData`、`SecondaryBody` 或 `Summary`，也不重复计算为新的布局模块。

操作组件只在输入提供真实 Action 时创建。独立按钮计为一个布局模块，按钮内部的文本和 Icon 不重复计数；同一个 `actionId` 在一张卡片中最多使用一次，不得同时用 `PillButton`、`CircleButton` 或 `CardButton` 重复表达同一操作。
