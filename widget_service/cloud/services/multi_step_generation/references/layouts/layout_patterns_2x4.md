# 2×4 卡片布局规范

## 1. 画布与布局层级

### 1.1 画布约束

| 项目 | 规格 |
|---|---:|
| 卡片尺寸 | 320 × 160vp |
| 圆角 | 20vp |
| 四边安全边距 | 12vp |
| 安全内容区 | 296 × 136vp |

所有可见内容必须限制在 296 × 136vp 安全内容区内，不得侵入 12vp 安全边距。

### 1.2 三层布局模型

2×4 布局分为三个层级：

1. **整卡安全内容区**：`Card` 默认 `padding={12}` 后得到 296 × 136vp。
2. **顶层布局区域**：“上下双区”“左右双区”“左内容右侧双槽”“四槽宫格”定义整卡的区域数量、主要尺寸、间距和固定槽位置。
3. **父内容区内部子布局**：“左右双区”默认在 118 × 112vp 内部安全区使用 Sub-118 子布局；其中一侧使用 Sub-140-D、Sub-140-E 或 Sub-140-H 时，该侧不使用背板，直接在 142 × 136vp 父区内居中放置 140 × 136vp Sub-140 子布局。“左内容右侧双槽”的 140 × 136vp 左内容区使用 Sub-140 子布局。

Sub 子布局只复用对应 2×2 布局的模块关系，不是新的 2×4 顶层布局。子布局内部模块不重复计入整卡顶层模块数，也不得跨越所属父内容区。

### 1.3 顶层区域与标题作用域

“上下双区”使用一个 296 × 20vp 整卡标题槽；其余顶层布局无公共标题，直接使用完整的 296 × 136vp 安全内容区。

| 区域 | 必要性 | 尺寸 / 弹性 | 布局规则 |
|---|---|---|---|
| 公共标题区 | 仅“上下双区”必选 | 296 × 20vp | 其他顶层布局不生成公共标题槽 |
| 子布局局部标题 | 按所选子布局必选 | `flex0; height:auto` | Sub-118 系列标题宽 118vp，相邻纵向模块间距 6vp；Sub-140 系列标题宽 140vp，相邻主要模块间距 8vp |
| 内容区 | 必选 | 按布局使用 `flex0` 或 `flex1` | 宽高必须由所属布局确定，不得照抄 HTML 参考图中的固定 `top` |
| 操作区 | 按真实 Action 可选 | `flex0`; 单个按钮最多占一个半卡宽父区 | 根据 Action 数量、归属和所选布局使用 `PillButton` 或 `CardButton` |
| 主要区域间距 | 按布局必选 | “上下双区”标题后 4vp、两个内容区之间 8vp；左右顶层区域之间 12vp；固定槽之间 8vp | 区域不存在时不保留空槽或相邻间距 |

“左右双区”需要标题时，只能在对应的 118 × 112vp 父内容安全区内部使用局部标题；“左内容右侧双槽”的标题只能属于 140 × 136vp 左内容区内部的 Sub-140 子布局。“上下双区”使用整卡标题，“四槽宫格”不设置标题区。

- 局部标题必须来自用户意图或输入数据，不得为了填充版面虚构。标题会重复正文或剩余区域无法容纳业务组件时，应更换无标题子布局或更换顶层布局。
- `SingleLineTitle` 是纯文本标题，高度固定为 18vp。
- `SingleLineTitle` 不支持标题 Icon；不得为参考图中的图标占位增加标题高度。
- `DoubleLineTitle` 含一行副信息时为 `18 + 4 + 18 = 40vp`；副信息为两行时继续自然增高。
- “上下双区”的整卡标题槽固定为 20vp；局部标题高度记为 `T`，Sub-118 和 Sub-140 子布局必须分别按自身的 6vp、8vp 间距公式计算剩余空间。
- HTML 中的固定坐标和尺寸仅供视觉参考，不得写成 JSX 定位值；应按局部标题实际高度、区域间距和所属子布局的可用空间计算。

## 2. 如何选择布局

布局按以下顺序选择：

1. 读取信息处理阶段的垂域分组和 Action 语义关系，保持各组内容可独立识别。
2. 判断信息适合上下、左右、非对称固定槽还是四宫格，先选择顶层布局家族。
3. 根据语义组数量、组间关系和 Action 数量确定顶层布局，不按组件总数机械凑槽位。
4. 根据信息关系、局部标题和 Action 选择父内容区内部子布局。
5. 检查各组信息是否完整、业务组件最小尺寸是否能放入目标槽位，以及 Action 是否一一对应。

布局名称约束顶层骨架、主要区域尺寸、区域间距和固定槽位类型。允许的内部变化必须由对应布局明确声明。若改动已经改变顶层区域数量、主要尺寸公式、固定槽位置或语义归属，应重新选择布局。

### 2.1 先完成语义分组

1. 2×4 场景先按业务对象和任务主题分组，再把数据与直接服务该对象的 Action 归入同组。Action 不是独立语义组，不得在分组前按按钮数量单独抽离。跨垂域内容只有存在明确共同任务时才能放进同一张卡片，并且仍要保持各组可独立识别。
2. 直接服务某组的 Action 应优先与该组内容进入同一父区；当同组内容无法安全容纳按钮时，可将 Action 放入相邻的固定操作槽，但其语义归属不变，按钮文本必须能独立说明操作，也不得因此把另一个业务组的数据并入当前内容区。
3. 同组的数据、局部标题和辅助信息原则上应保持在同一连续父区域内；Action 可按可读性和视觉均衡放入对应或相邻操作槽。唯一允许的内容拆分是：单一垂域中已经形成“核心结论 + 属性明细”两个可独立识别的完整信息模块时，可以使用“左右双区”将核心值与状态放在一侧、同主题的多项属性明细放在另一侧。不得把彼此依赖的单个字段或同一组件应共同表达的内容随意拆到左右两区。
4. 布局阶段不得为了适配布局改变数据含义、丢失必需信息或虚构 Action；允许在保持信息可识别的前提下调整 Action 的视觉位置。只要 `userQuery` 明确要求操作且输入 `actions` 非空，每个 Action 都必须进入合法按钮槽位，“上下双区”立即排除，不得把 Action 写入 `unmetRequirements`。
5. 顶层无公共标题时，仍可按所选子布局在父内容区内部使用局部标题。跨垂域分组缺少其他清晰主语时，各父区都应保留可见的业务标题。

完成归组后再判断顶层区域：两个独立业务组各自包含数据和一个 Action，且两组都能压缩为合法的 Sub-118-D 时，使用“左右双区”，不得把两个 Action 抽到同一按钮列。最终需要三个可见区域时，即一个完整内容区加两个可独立识别的紧凑信息／操作槽，可以尝试“左内容右侧双槽”；右侧两个槽必须各自完整，不得承载本应与不同业务组数据成组的两个 Action。

例如会议与耳机共同服务当前参会任务时，应先形成“日程信息 + 加入会议 Action”和“耳机连接状态／耳机仓电量 + 蓝牙设置 Action”两个完整业务组；若两组都能各用一个内容组件表达，则选择“左右双区”，左右分别使用 Sub-118-D。不得改成左侧混放日程与耳机数据、右侧集中放两个 `CardButton`。

### 2.2 选择顶层布局家族

| 顶层信息关系 | 布局家族 | 候选布局 |
|---|---|---|
| 单一主要信息分区中，主体内容与同级属性明细形成上下关系 | 整宽纵向流 | 上下双区 |
| 两个完整信息模块左右分区，或同一主题的“核心结论 + 属性明细”；每组可各带一个同组 Action | 双背板分区 | 左右双区 |
| 最终形成“一个完整内容区 + 右侧一个或两个独立紧凑信息／操作槽”，通常是三个可见区域 | 非对称内容与固定槽 | 左内容右侧双槽 |
| 恰好四个有效的固定 `CardButton`／`InfoBlock` 模块 | 固定四宫格 | 四槽宫格 |

顶层模块数只用于初选：“上下双区”为一个标题区和两个内容区；“左右双区”为两个父内容区；“左内容右侧双槽”为一个左内容区和右侧一个或两个有效固定槽；“四槽宫格”为四个固定槽。父区内部的标题、文本、Icon、进度视觉和业务组件不重复计数。最终仍须检查信息层级、标题高度和业务组件最小占位。

### 2.3 顶层布局选择总表

| 语义结构 / Action 关系 | 顶层布局 | 顶层分配规则 |
|---|---|---|
| 单一主要信息分区，主体内容与同级属性明细形成上下关系，并且输入 `actions` 为空 | 上下双区 | 先确认用户没有要求任何操作，再放 296 × 20vp 整卡标题、主体内容和一组 `TextBlock` 或 `TopTextBottomValue` 明细；不支持 Action，输入存在 Action 时禁止选择 |
| 单一语义组，包含明确的核心结论与多项属性明细 | 左右双区 | 左区完整表达核心值与状态，右区表达同主题明细；默认两个父区均使用 `surface="backplate"` |
| 两个同级语义组，没有独立 Action | 左右双区 | 左右各承载一个可独立阅读的完整信息分区 |
| 单一语义组，只有 1 个 Action | 左内容右侧双槽或左右双区 | 左内容无法安全容纳 `PillButton` 时，在右下固定槽使用 `CardButton`；左右双区可在所属父区使用 Sub-118-D；不得生成整卡宽按钮 |
| 两个独立业务组各有 1 个直属 Action | 左右双区双 `PillButton` 变体 | 左右父区分别完整承载本组数据和 Action，并使用 Sub-118-D；不得把两组数据合进左侧后把 Action 统一移到右侧 |
| 2 个 Action 均服务同一个左侧内容组或整卡共同任务，没有第二个独立数据组 | 左内容右侧双槽 | 左侧完整表达数据，右侧两个固定槽分别使用 `CardButton` |
| 一个完整内容区之外还需要两个独立紧凑信息／操作模块 | 左内容右侧双槽 | 左侧使用一个 Sub-140；右侧两个模块各占一个 144 × 64vp 固定槽，形成三个可见区域 |
| 恰好 3 个 Action | 四槽宫格有条件支持 | 只有另有一个真实、同级的 `InfoBlock` 时，才能组成三个 `CardButton` + 一个 `InfoBlock`；否则停止并报告 |
| 恰好 4 个 Action，均服务同组或整卡共同任务 | 四槽宫格 | 四个 Action 分别使用一个 `CardButton`，四槽全部填满 |
| 单一语义组，恰好需要四个固定信息／操作模块 | 四槽宫格 | 四槽必须全部有效；Action 使用 `CardButton`，非操作信息可使用 `InfoBlock`；混用时同类组件按列纵排 |
| 跨垂域且不存在共同任务对象 | 不合并生成 | 保留主问题，其他组报告为未满足或另行生成，不得仅因 2×4 空间较大而拼卡 |

### 2.4 根据 Action 确认操作槽

- 2×4 可以使用 `PillButton` 和 `CardButton`，禁止使用 `CircleButton`。
- 按钮类型由布局槽位决定，不由 Action 数量直接决定：子布局中的操作使用 `PillButton`，固定操作槽使用 `CardButton`。
- 只有 1 个 Action 时优先使用所属子布局中的 `PillButton`；内容子布局无法安全容纳时，使用“左内容右侧双槽”的右下 144 × 64vp 固定槽和 `CardButton`。
- 有两个 Action 时先检查语义归属：分别服务两个独立业务组，且两侧都能安全使用 Sub-118-D 时，使用“左右双区”和两个 118 × 36vp `PillButton`；两个 Action 均服务同一个内容组或整卡共同任务时，使用“左内容右侧双槽”的两个 144 × 64vp `CardButton`。不得仅因 Action 数量为两个就把不同业务组的按钮统一移到右侧。
- 三个 Action 不能单独凑成布局；只有另有一个真实、同级的 `InfoBlock` 并共同满足“四槽宫格”条件时，才允许使用三个 `CardButton` + 一个 `InfoBlock`。四个有效 Action 可分别使用一个 `CardButton` 填满“四槽宫格”。
- 单个 `PillButton` 或 `CardButton` 都不得横跨 296vp 安全内容区。左右双 `PillButton` 是两个独立的半卡按钮，不是一个整卡宽按钮。
- 同一个 action 只能生成一个按钮，不得用 `PillButton` 与 `CardButton` 重复表达。
- 没有 action 时不得为了填充布局而虚构按钮。

### 2.5 选择父内容区内部子布局

子布局必须在该父内容区的业务组件选择完成后确定，按“内容组件数 → 是否有局部标题 → 是否有 Action”查表：

- 内容组件数按最终 JSX 中属于该父内容区的 Design System 业务组件实例计数。只负责尺寸、对齐或分组的 `Stack` 不计数，局部标题和按钮分别按“标题”“Action”判断，不计入内容组件数。
- 一个业务组件无论包含多少显示字段、内部元素、`items` 或文本行，都只算一个内容组件。例如同时显示数值、标签和状态的一个 `ProgressCircleSingle` 仍是一个内容；同一内容包装层中的 `EmphasisText` 与 `SecondaryBody` 是两个独立内容组件。
- 先确定组件，再确定子布局。若生成 JSX 时合并、拆分或替换了业务组件，必须按最终组件数重新选择并同步提交 `decision.subPattern`，不得沿用计划阶段已经失效的名称。
- 必选 Action 的子布局与无 Action 子布局互斥。存在按钮时必须选择表中明确支持按钮的子布局；无 Action 时不得选择必选按钮的子布局。只有明确标为“可选按钮”的子布局可同时覆盖有、无 Action 两种状态，按钮缺省时必须连同其相邻间距一起删除。按钮是独立操作模块，不得把按钮计作第二个内容组件。

“左右双区”的左右背板父区各自在 118 × 112vp 内部安全区中选择一种 Sub-118 子布局：

| 参考子布局 | 内容组件数 | 信息关系 | 局部标题 | Action |
|---|---:|---|---|---|
| Sub-118-A · 核心居中 | 1 | 单个 Data Display 内容 | 无 | 无 |
| Sub-118-B · 标题单内容 | 1 | 单个主体内容 | 必选 | 无 |
| Sub-118-C · 标题双内容 | 2 | 上核心组件 + 下明细组件 | 必选 | 无 |
| Sub-118-D · 标题内容单按钮 | 1 | 单个主体内容 | 必选 | 1 个 `PillButton` |

Sub-118 没有“标题 + 两个内容组件 + 按钮”的骨架。遇到该组合时，应改用能完整容纳它的 Sub-140 与顶层布局，或在不丢失信息和绑定的前提下用一个语义兼容组件合并内容；不得选 Sub-118-C 后追加按钮，也不得选 Sub-118-D 后塞入两个内容组件。

“左内容右侧双槽”的 140 × 136vp 左内容区选择一种 Sub-140 子布局；其中 Sub-140-D、Sub-140-E、Sub-140-H 还可作为“左右双区”的无背板半区：

| 适配子布局 | 内容组件数 | 信息关系 | 局部标题 | Action |
|---|---:|---|---|---|
| Sub-140-A · 核心居中 | 1 | 单个 Data Display 内容 | 无 | 无 |
| Sub-140-B · 标题单内容 | 1 | 单个主体内容 | 必选 | 无 |
| Sub-140-C · 标题内容单按钮 | 1 | 单个主体内容 | 必选 | 1 个 `PillButton` |
| Sub-140-D · 标题双列内容可选按钮 | 2 | 两个同级占比 | 必选 | 可选 1 个 `PillButton` |
| Sub-140-E · 上下双信息块 | 2 | 两个同级紧凑信息块 | 无 | 无 |
| Sub-140-F · 标题主次内容单按钮 | 2 | Hero + 紧密关联的次要信息 | 必选 | 1 个 `PillButton` |
| Sub-140-G · 标题双内容 | 2 | 上核心组件 + 下明细组件 | 必选 | 无 |
| Sub-140-H · 内容四宫格 | 4 | 四个同级占比 | 无 | 无 |

Sub 名称只表示父内容区内部布局，不是 2×4 顶层布局，也不沿用 2×2 的 136 × 136vp 尺寸。

顶层结构不得混用：“左右双区”只能使用两个 142vp 父区和 12vp 间距；“左内容右侧双槽”只能使用左 140vp 内容区、12vp 间距和右 144vp 固定槽列；“上下双区”只能使用 296vp 整宽标题和上下内容区；“四槽宫格”只能使用四个 144 × 64vp 固定槽。不得拼接不同顶层布局的区域。

## 3. 通用实现规则

### 3.1 Stack、Grid 与尺寸语义

- 根节点固定使用 `size="2x4"` 与合法 `appearance`，并显式声明 `direction`：“上下双区”使用 `"column"`，其余横向顶层骨架使用 `"row"`；默认 `padding={12}` 得到 296 × 136vp 安全内容区。
- `flex0` 表示模块不参与剩余空间分配；在 JSX 中使用 `flex={0}`，并按父容器主轴用 `width` 或 `height` 表达固定区域。
- `flex1` 表示模块至少在一个方向使用剩余空间，必须继续标明自适应方向；JSX 使用 `flex={1}`，runtime 自动提供纵向收缩所需的 `minHeight:0`。
- 整宽组件必须占满所属模块：整宽区为 296vp，普通等宽列为 144vp，非对称内容列为 140vp。包裹层使用 `width="full"`，不得因父层对齐方式按内容收缩。
- 基础等宽双列满足 `144 + 8 + 144 = 296`；144vp 子列满足 `68 + 8 + 68 = 144`。
- “左内容右侧双槽”使用 `140 + 12 + 144 = 296`。
- 产品规格使用 vp；HTML 骨架预览可使用同数值 px 做 1:1 校核。

### 3.2 标题与内容对齐

- 只有“上下双区”生成整卡标题；其他顶层布局不生成公共标题。局部标题使用 `flex={0}`，宽度由所属子布局决定，高度由标题组件自然撑开。
- 标题下方空间从标题实际底部开始计算；Sub-118 的相邻纵向主要模块使用 6vp，Sub-140 使用 8vp。
- 标题增高或文本换行导致槽位小于业务组件最小尺寸时，更换更紧凑的组件或布局。
- 需要左对齐、底端对齐或居中时，由业务组件外层 `Stack` 表达，不向业务组件传入未知的布局 Props。
- 任一 Sub-118／Sub-140 子布局使用 `ProgressCircleSingle` 时，必须传入 `size="compact"`：圆环为 44 × 44vp，右侧各行行盒相对默认规格减少 2px。不得在子布局中使用省略 `size` 的 52 × 52vp 默认规格。

### 3.3 按钮与固定槽

- 普通 2×4 `PillButton` 沿用 runtime 的 136 × 36vp、圆角 30vp；Sub-118 中固定为 118 × 36vp、圆角 18vp；Sub-140 中固定为 136 × 36vp 并左对齐，右侧留 4vp。
- Sub-118 的 `PillButton` 作为 `flex0` 模块进入普通纵向流，不使用绝对定位或底部锚定。
- “四槽宫格”和“左内容右侧双槽”的 `CardButton`／`InfoBlock` 父槽均为 144 × 64vp、圆角 16vp，不使用 48–64vp 动态槽高。
- 所有 `CardButton` 使用当前 runtime 的固定 16px 圆角，只能进入本文规定的半卡宽固定槽，不生成 `radius` 或 `style`。
- 生成 JSX 不向业务组件传入不存在的 `width`、`height`、`radius` 或 `position` Props；尺寸和位置由外层槽位负责。

### 3.4 数据绑定与禁止项

- 示例中的 `dataIds` 与 `actionId` 只说明绑定位置；实际生成必须替换为输入中真实存在的 ID。
- 需要 Card 语义配色的业务组件传入 `appearance="card"`。
- 模板禁止原生元素、`style`、`className`、spread Props、未知 Props 和硬编码颜色。
- 不得使用硬编码背景模拟 runtime 未公开的 Panel；“左右双区”背板只使用公开的 `Stack surface="backplate"`。

## 4. 布局实现与JSX写法

### 4.1 上下双区

仅当输入 `actions` 为空、`userQuery` 没有要求按钮或操作时使用。输入存在任何 Action 时，不得选择该布局，也不得先选择该布局再把 Action 标记为未满足需求。

骨架：整卡标题区 + 上主体内容区 + 下明细内容区。
标题区固定为 296 × 20vp，标题区与内容父区之间为 4vp。标题下方建立占据剩余 112vp 高度的内容父区，按“主体内容 → 同级属性明细”的语义顺序排列。下明细区只能使用一组 `TextBlock` 或 `TopTextBottomValue`：`TextBlock` 通常展示 2–4 项两行明细，`TopTextBottomValue` 用于至少 3 项“标签 → 数值 → 单位”三行指标。

两个内容模块不默认等高，应根据内容关系选择以下高度策略。内容父区必须满足 `主体实际高度 + 8vp + 明细实际高度 ≤ 112vp`；当两个组件的默认高度之和超出 112vp 时，必须由支持高度自适应的内容槽承接剩余高度，不得让两个内容槽同时使用无明确高度的 `flex={0}`，也不得把组件压缩到低于其最小高度。

上下双区的内容统一左对齐。内容父区和两个内容槽均使用 `align="flex-start"`；不得使用 `align="center"` 将 `EmphasisText`、`EmphasizedData` 等主体组件放到区域中间，也不得使用 `justify="center"` 制造无语义的垂直居中。

| 内容关系 | 高度策略 | 内容父区对齐 |
|---|---|---|
| 主体与明细需要紧密连续阅读 | 主体使用自然高度，明细槽承接剩余高度 | `justify="flex-start"`、`gap={8}` |
| 主体在上，明细作为底部结论 | 主体槽承接剩余高度，明细使用自然高度 | `justify="space-between"`、`gap={8}` |
| 两块同类型、同重要性且都支持高度拉伸 | 等分扣除间距后的剩余高度 | 两个模块均使用 `flex={1}` |

紧密连续阅读：
```jsx
<Stack direction="column" flex={1} minHeight={0} width="full" gap={8} align="flex-start" justify="flex-start">
  <Stack direction="column" flex={0} width="full" align="flex-start" justify="flex-start">{/* 自然高度的主体内容组件 */}</Stack>
  <Stack direction="column" flex={1} minHeight={0} width="full" align="flex-start" justify="flex-start">{/* 一组可在合法高度内适配的 TextBlock 或 TopTextBottomValue */}</Stack>
</Stack>
```

明细作为底部结论：
```jsx
<Stack direction="column" flex={1} minHeight={0} width="full" gap={8} align="flex-start" justify="space-between">
  <Stack direction="column" flex={1} minHeight={0} width="full" align="flex-start" justify="flex-start">{/* 主体内容组件 */}</Stack>
  <Stack direction="column" flex={0} width="full" align="flex-start" justify="flex-start">{/* 自然高度的一组 TextBlock 或 TopTextBottomValue */}</Stack>
</Stack>
```

两个同类型模块等分：
```jsx
<Stack direction="column" flex={1} minHeight={0} width="full" gap={8} align="flex-start">
  <Stack direction="column" flex={1} minHeight={0} width="full" align="flex-start" justify="flex-start">{/* 主体内容组件 */}</Stack>
  <Stack direction="column" flex={1} minHeight={0} width="full" align="flex-start" justify="flex-start">{/* 一组 TextBlock 或 TopTextBottomValue */}</Stack>
</Stack>
```

标题区必选，不得省略、移入主体内容区或改为局部标题。`TextBlock` 高度可在 48–64vp 内适配；`TopTextBottomValue` 固定占用 68vp，因此仅在主体内容自然高度加 8vp 间距后仍能装入 112vp 内容父区时使用，且不得进入等分后不足 68vp 的槽位。下明细区不得混入 `SecondaryBody`、进度组件、按钮或其他类型的业务组件；不得增加第四个顶层区域、追加按钮或依赖裁剪隐藏溢出。

### 4.2 左右双区

骨架：无公共标题 + 左右两个均分父内容区，默认两侧使用背板。
尺寸与闭合：左右父区均为 `flex0`、142 × 136vp，水平间距为 12vp，满足 `142 + 12 + 142 = 296vp`。普通背板父区四边内缩 12vp，形成 118 × 112vp 内部安全区并使用 Sub-118 子布局。

当且仅当一侧使用 Sub-140-D、Sub-140-E 或 Sub-140-H 时，该侧允许省略 `surface="backplate"`，并在 142 × 136vp 父区内水平居中放置 140 × 136vp Sub-140 子布局；另一侧仍使用普通背板和 Sub-118 子布局。不得同时取消两侧背板。

```jsx
<Card size="2x4" appearance="solid-white" direction="row" gap={12}>
  <Stack direction="column" surface="backplate" flex={0} width={142} height={136} align="center" justify="center">
    <Stack direction="column" flex={0} width={118} height={112} gap={6}>
      <Stack direction="column" flex={0} width={118}>
        <SingleLineTitle title="日程" />
      </Stack>
      <Stack direction="column" flex={1} width={118} align="flex-start">
        <EventCard title="项目例会" time="10:00-14:00" location="练秋湖A1-3-41R" />
      </Stack>
    </Stack>
  </Stack>

  <Stack direction="column" surface="backplate" flex={0} width={142} height={136} align="center" justify="center">
    <Stack direction="column" flex={0} width={118} height={112} gap={6}>
      <Stack direction="column" flex={0} width={118}>
        <SingleLineTitle title="健康数据" />
      </Stack>
      <Stack direction="column" flex={1} width={118}>
        <SecondaryBody items={[{ value: "今日 6200 步" }]} />
      </Stack>
      <Stack direction="column" flex={0} width={118} height={36}>
        <PillButton label="进入锻炼" icon="figure_run.svg" appearance="card" actionId="event.open.health.sport" />
      </Stack>
    </Stack>
  </Stack>
</Card>
```

单侧 Sub-140 无背板变体：

```jsx
<Card size="2x4" appearance="solid-blue" direction="row" gap={12}>
  <Stack direction="column" flex={0} width={142} height={136} align="center" justify="center">
    <Stack direction="column" flex={0} width={140} height={136}>
      {/* Sub-140-D、Sub-140-E 或 Sub-140-H */}
    </Stack>
  </Stack>
  <Stack direction="column" surface="backplate" flex={0} width={142} height={136} align="center" justify="center">
    <Stack direction="column" flex={0} width={118} height={112}>
      {/* 一个 Sub-118 子布局 */}
    </Stack>
  </Stack>
</Card>
```

#### 4.2.1 左右双区通用规则

- 整卡不设置公共标题；需要标题时，在对应父内容区内部使用局部标题。
- 整卡背景使用合法的 `Card.appearance`；父内容区背板由 `surface="backplate"` 在该主题上派生。
- 普通模式下，左右父区都必须使用 `surface="backplate"`，圆角为 16vp，并裁剪内部背景。只有承载 Sub-140-D、Sub-140-E 或 Sub-140-H 的一侧可以省略背板；不得用于其他子布局，也不得同时取消两侧背板。
- `surface="backplate"` 只写在普通背板父 `Stack` 上，不写在局部标题、内容或按钮包装层上。
- 背板颜色沿用当前 runtime：Light Mode 使用白色、透明度 40%；Dark Mode 使用白色、透明度 10%。该颜色规则只属于父内容区，不扩散到子布局内部模块；在主题深色 5% 的具体色值映射明确前不自行替换。
- 普通背板父区内部必须建立水平、垂直居中的 118 × 112vp 内层 `Stack`，形成四边各 12vp 的安全边距。
- 左右父区可以分别选择不同参考子布局，但内部模块不得跨区、共享尺寸、共享对齐基准或占用中间 12vp 间距。
- 标题宽 118vp、`flex0`、`height:auto`；公式中的 `T` 为标题实际高度。`SingleLineTitle` 的参考态为 `T = 18vp`，`DoubleLineTitle` 按实际 40vp 或自然换行高度计算。
- 相邻纵向主要模块统一使用 6vp 间距；横向间距按对应子布局定义。
- `PillButton` 固定为 118 × 36vp、圆角 18vp，作为 `flex0` 模块进入普通布局流，不使用绝对定位。
- 不得在子布局中使用原生元素、`style`、`className` 或硬编码背景模拟第二层 Panel，也不得产生越过背板圆角的直角背景。

推荐公共外壳：

```jsx
<Stack direction="column" surface="backplate" flex={0} width={142} height={136} align="center" justify="center">
  <Stack direction="column" flex={0} width={118} height={112}>
    {/* 参考子布局内容 */}
  </Stack>
</Stack>
```

#### 4.2.2 Sub-118 父内容区子布局

##### Sub-118-A：核心居中

内容区固定为 118 × 112vp，内容水平、垂直居中；仅允许放置 Design System 中归类为 Data Display 的组件。

```jsx
<Stack direction="column" flex={0} width={118} height={112} align="center" justify="center">
  {/* 单个核心内容模块 */}
</Stack>
```

##### Sub-118-B：标题单内容

标题区必选，宽 118vp，自然高度为 `T`。内容区宽 118vp，使用 `flex={1}`；标题与内容间距为 6vp，内容左对齐且底端对齐。

内容区高度为 `112 − T − 6 = 106 − T`；当 `T = 18vp` 时，参考尺寸为 118 × 88vp。

```jsx
<Stack direction="column" flex={0} width={118} height={112} gap={6}>
  <Stack direction="column" flex={0} width={118}>{/* 局部标题 */}</Stack>
  <Stack direction="column" flex={1} width={118} align="flex-start" justify="flex-end">{/* 单个内容模块 */}</Stack>
</Stack>
```

##### Sub-118-C：标题双内容

标题区必选，宽 118vp，自然高度为 `T`。标题下方必须放置两个彼此独立的业务 JSX 组件实例：上内容用于核心信息，下内容用于独立明细或结论；例如上方使用 `EmphasisText`、下方使用 `EmphasizedData`。一个组件内部的两个字段、两个 `items` 或两行文本不算“双内容”。

标题下方的内容父区占满剩余高度。上内容槽使用 `flex={1}` 吸收剩余空间，组件在槽内左上对齐；下内容槽使用 `flex={0}` 和组件自然高度，由上内容槽把它推至内容父区底部。两个内容槽间距固定为 6vp，不等分高度，也不使用 `justify="space-between"` 或两个 `flex={0}` 模块模拟贴底。两个组件均不得被压缩到低于自身最小高度。

```jsx
<Stack direction="column" flex={0} width={118} height={112} gap={6}>
  <Stack direction="column" flex={0} width={118}>{/* 局部标题 */}</Stack>
  <Stack direction="column" flex={1} minHeight={0} width={118} gap={6}>
    <Stack direction="column" flex={1} minHeight={0} width={118} align="flex-start" justify="flex-start">
      {/* 上内容：一个核心业务 JSX 组件 */}
    </Stack>
    <Stack direction="column" flex={0} width={118} align="flex-start">
      {/* 下内容：另一个独立的业务 JSX 组件 */}
    </Stack>
  </Stack>
</Stack>
```

##### Sub-118-D：标题内容单按钮

标题区必选，宽 118vp，自然高度为 `T`；内容区宽 118vp，使用 `flex={1}`。`PillButton` 必选、不得缺省，固定为 118 × 36vp、圆角 18vp，并作为 `flex0` 模块进入普通纵向流。

标题、内容区和按钮之间均为 6vp；内容区高度为 `112 − T − 6 − 6 − 36 = 64 − T`。当 `T = 18vp` 时，参考尺寸为 118 × 46vp。

该 46vp 内容区允许放置 `ProgressCircleSingle size="compact"`：两行模式整体高 44vp，三行模式整体高 46vp。不得放置省略 `size` 的 52vp 默认规格。

```jsx
<Stack direction="column" flex={0} width={118} height={112} gap={6}>
  <Stack direction="column" flex={0} width={118}>{/* 局部标题 */}</Stack>
  <Stack direction="column" flex={1} width={118}>{/* 内容(flex1)；ProgressCircleSingle 必须使用 size="compact" */}</Stack>
  <Stack direction="column" flex={0} width={118} height={36}>
    <PillButton label="操作" appearance="card" actionId="action.example" />
  </Stack>
</Stack>
```

### 4.3 非对称内容与固定槽

“左内容右侧双槽”由左侧 140 × 136vp 完整内容区和右侧一个或两个 144 × 64vp 固定槽组成。左内容区使用 Sub-140 子布局；右侧只允许本文明确列出的 `CardButton`／`InfoBlock` 组合，不提供镜像布局。

#### 4.3.1 共用的 Sub-140 内容区子布局

以下八种骨架适用于“左内容右侧双槽”的左内容区。满宽内容模块使用 140vp；`PillButton` 保持 136 × 36vp 并左对齐，右侧留 4vp。内部标题不是整卡公共标题。Sub-140-D、Sub-140-E、Sub-140-H 还可作为“左右双区”的无背板半区。Sub-140-G、Sub-140-H 分别复用 2×2“标题双内容”“内容四宫格”的模块关系，但按 140 × 136vp 内容区重新计算宽度，不得照搬 2×2 的 136vp 横向尺寸。

##### Sub-140-A：核心居中

无标题单内容区，固定为 140 × 136vp，内容水平、垂直居中；仅允许放置 Design System 中归类为 Data Display 的组件。

```jsx
<Stack direction="column" width={140} height={136} align="center" justify="center">
  {/* Data Display 组件 */}
</Stack>
```

##### Sub-140-B：标题单内容

标题宽 140vp、`flex0`、`height:auto`；内容区 `flex1`、高度自适应，并左对齐、底端对齐。标题与内容间距为 8vp；内容区高度为 `136 − T − 8 = 128 − T`。参考 `T = 18vp` 时，内容区高 110vp。

```jsx
<Stack direction="column" width={140} height={136} gap={8}>
  <Stack direction="column" flex={0} width={140}>{/* 内部标题 */}</Stack>
  <Stack direction="column" flex={1} width={140} align="flex-start" justify="flex-end">{/* 内容 */}</Stack>
</Stack>
```

##### Sub-140-C：标题内容单按钮

标题、内容区和 `PillButton` 均为必选，相邻模块间距为 8vp。`PillButton` 固定为 136 × 36vp 并左对齐；内容区高度为 `136 − T − 8 − 8 − 36 = 84 − T`。参考 `T = 18vp` 时，内容区高 66vp。

```jsx
<Stack direction="column" width={140} height={136} gap={8}>
  <Stack direction="column" flex={0} width={140}>{/* 内部标题 */}</Stack>
  <Stack direction="column" flex={1} width={140}>{/* 内容(flex1) */}</Stack>
  <Stack direction="column" flex={0} width={136} height={36}>
    <PillButton label="操作" appearance="card" actionId="action.example" />
  </Stack>
</Stack>
```

##### Sub-140-D：标题双列内容可选按钮

标题必选，宽 140vp、自然高度为 `T`；双列内容区使用 `flex={1}`，内部必须放置两个同级的 `ProgressCircle size="sm"`，两列等分扣除 8vp 横向间距后的宽度。`PillButton` 可选；存在时固定为 136 × 36vp 并左对齐，内容行与按钮间距为 8vp；缺省时同时删除按钮模块及其相邻间距。

显示按钮时，双列内容区高度为 `136 − T − 8 − 8 − 36 = 84 − T`；当 `T = 18vp` 时，两列参考槽位均为 66 × 66vp，纵向满足 `18 + 8 + 66 + 8 + 36 = 136vp`。按钮缺省时，双列内容区高度为 `136 − T − 8 = 128 − T`；当 `T = 18vp` 时，两列参考槽位均为 66 × 110vp。两种状态都使用同一 `flex={1}` 内容骨架，不固定写死内容区高度。

```jsx
<Stack direction="column" width={140} height={136} gap={8}>
  <Stack direction="column" flex={0} width={140}>{/* 内部标题 */}</Stack>
  <Stack direction="row" flex={1} width={140} gap={8}>
    <Stack direction="column" flex={1} align="center" justify="center">{/* <ProgressCircle size="sm" /> */}</Stack>
    <Stack direction="column" flex={1} align="center" justify="center">{/* <ProgressCircle size="sm" /> */}</Stack>
  </Stack>
  <Stack direction="column" flex={0} width={136} height={36}>
    <PillButton label="操作" appearance="card" actionId="action.example" />
  </Stack>
</Stack>
```

上例为有 Action 状态；没有 Action 时删除最后一个按钮 `Stack`，不得保留空按钮槽或额外的 8vp 间距。

##### Sub-140-E：上下双信息块

无标题、无 Action，上下排列两个同级 `InfoBlock`。两个槽位均为 136 × 64vp 并水平居中，垂直间距为 8vp，满足 `64 + 8 + 64 = 136vp`。

```jsx
<Stack direction="column" width={140} height={136} gap={8} align="center">
  <Stack direction="column" flex={0} width={136} height={64}>
    {/* <InfoBlock /> */}
  </Stack>
  <Stack direction="column" flex={0} width={136} height={64}>
    {/* <InfoBlock /> */}
  </Stack>
</Stack>
```

##### Sub-140-F：标题主次内容单按钮

标题、Hero、次要信息和 `PillButton` 均为必选；标题、内容组、按钮之间为 8vp，Hero 与次要信息之间为 2vp。Hero 与次要信息均按内容自然撑高，不强制等高；`PillButton` 固定为 136 × 36vp 并左对齐。

```jsx
<Stack direction="column" width={140} height={136} gap={8}>
  <Stack direction="column" flex={0} width={140}>{/* 内部标题 */}</Stack>
  <Stack direction="column" flex={1} width={140} gap={2}>
    <Stack direction="column" width={140}>{/* Hero：按内容自然撑高 */}</Stack>
    <Stack direction="column" width={140}>{/* 次要信息：按内容自然撑高 */}</Stack>
  </Stack>
  <Stack direction="column" flex={0} width={136} height={36}>
    <PillButton label="操作" appearance="card" actionId="action.example" />
  </Stack>
</Stack>
```

##### Sub-140-G：标题双内容

标题、上内容和下内容均为必选。标题宽 140vp、`flex={0}`、自然高度为 `T`。上下内容必须分别承载一个彼此独立的业务 JSX 组件实例，例如上方使用 `EmphasisText`、下方使用 `EmphasizedData`；一个组件内部的多个字段、`items` 或文本行不算“双内容”。

标题下方的内容父区使用 `flex={1}`。上内容槽使用 `flex={1}` 吸收剩余高度，组件在槽内左上对齐；下内容槽使用 `flex={0}` 和组件自然高度，因此稳定落在内容父区底部。标题与内容父区、上下内容槽之间的间距均为 8vp。不得把上下内容等分，也不得让两个内容槽都使用 `flex={0}` 后停留在顶部。

```jsx
<Stack direction="column" width={140} height={136} gap={8}>
  <Stack direction="column" flex={0} width={140}>{/* 内部标题 */}</Stack>
  <Stack direction="column" flex={1} minHeight={0} width={140} gap={8}>
    <Stack direction="column" flex={1} minHeight={0} width={140} align="flex-start" justify="flex-start">
      {/* 上内容：一个核心业务 JSX 组件 */}
    </Stack>
    <Stack direction="column" flex={0} width={140} align="flex-start">
      {/* 下内容：另一个独立的业务 JSX 组件 */}
    </Stack>
  </Stack>
</Stack>
```

##### Sub-140-H：内容四宫格

无标题、无 Action，固定为 140 × 136vp。四个槽位必须分别承载一个 `ProgressCircle size="sm"`，表达四个同级占比，不得留空、替换、合并或跨格。横向满足 `66 + 8 + 66 = 140vp`，纵向满足 `64 + 8 + 64 = 136vp`，因此每格为 66 × 64vp，行列间距均为 8vp。

```jsx
<Grid columns={2} rows="64px 64px" gap={8} width={140} height={136}>
  <Stack direction="column" width={66} height={64} align="center" justify="center">{/* <ProgressCircle size="sm" /> */}</Stack>
  <Stack direction="column" width={66} height={64} align="center" justify="center">{/* <ProgressCircle size="sm" /> */}</Stack>
  <Stack direction="column" width={66} height={64} align="center" justify="center">{/* <ProgressCircle size="sm" /> */}</Stack>
  <Stack direction="column" width={66} height={64} align="center" justify="center">{/* <ProgressCircle size="sm" /> */}</Stack>
</Grid>
```

#### 4.3.2 左内容右侧双槽

尺寸与闭合：左内容区为 140 × 136vp；右侧每个有效槽均为 144 × 64vp。两个槽同时存在时上下间距为 8vp，满足 `64 + 8 + 64 = 136vp`；左右间距为 12vp，满足 `140 + 12 + 144 = 296vp`。

右侧固定槽只允许以下四种组合：

| 右侧组合 | 槽位规则 |
|---|---|
| 1 个 `CardButton` | 只生成右下槽，不生成右上空槽或占位 |
| 2 个 `CardButton` | 上、下槽各放一个 |
| 2 个 `InfoBlock` | 上、下槽各放一个 |
| 1 个 `InfoBlock` + 1 个 `CardButton` | `InfoBlock` 固定在上槽，`CardButton` 固定在下槽 |

存在 Action 的槽必须使用 `CardButton`。禁止只放一个 `InfoBlock`，也不得交换混合组合的上下顺序。右侧包含任何 `InfoBlock` 时，Card 必须使用 `*-gradient` 深色主题；右侧只有 `CardButton` 时可根据场景使用浅色或深色主题。

两个右侧槽：

```jsx
<Card size="2x4" appearance="solid-green" direction="row" gap={12}>
  <Stack direction="column" flex={0} width={140} height={136}>
    {/* 选择 4.3.1 中的一种 Sub-140 子布局 */}
  </Stack>
  <Stack direction="column" flex={0} width={144} height={136} gap={8}>
    <Stack direction="column" flex={0} width={144} height={64}>
      {/* <InfoBlock /> */}
    </Stack>
    <Stack direction="column" flex={0} width={144} height={64}>
      {/* <CardButton /> */}
    </Stack>
  </Stack>
</Card>
```

单个右下 `CardButton`：

```jsx
<Card size="2x4" appearance="solid-blue" direction="row" gap={12}>
  <Stack direction="column" flex={0} width={140} height={136}>
    {/* 选择 4.3.1 中的一种 Sub-140 子布局 */}
  </Stack>
  <Stack direction="column" flex={0} width={144} height={136} justify="flex-end">
    <Stack direction="column" flex={0} width={144} height={64}>
      {/* <CardButton /> */}
    </Stack>
  </Stack>
</Card>
```

左内容区固定在左侧，不提供镜像布局。每个有效固定槽只放一个业务组件；不得合并槽位、跨槽排布、改变槽位尺寸或在右侧槽列使用 `PillButton`。多条日程与一个次要状态、一个 Action 同时出现时，左侧连续内容区可纵向排列 `density="compact"` 的 `EventCard`，右上使用 `InfoBlock`，右下使用 `CardButton`；不得删除日程标题、时间、地点或绑定。

### 4.4 四槽宫格

骨架：无标题 + 四个固定的 `CardButton`／`InfoBlock` 槽。
尺寸与闭合：每槽为 144 × 64vp、圆角 16vp；横向和纵向间距均为 8vp，满足 `144 + 8 + 144 = 296vp` 与 `64 + 8 + 64 = 136vp`。
操作区：四槽必须全部由有效的 `CardButton` 或 `InfoBlock` 一一填满；存在 Action 的槽必须使用 `CardButton`。不得留空、占位、隐藏、合并或改成动态高度。四槽中包含任何 `InfoBlock` 时，Card 必须使用 `*-gradient` 深色主题。
排列规则：左列为 A、C，右列为 B、D。混用两种组件时，同类组件必须占用同一列并按上→下排列，同一列不得混排不同类型；四槽全部使用同一组件类型时，两列分别按上→下排列。
视觉规则：每个槽位只承载一个 `CardButton` 或 `InfoBlock`，视觉由槽内组件负责，不生成额外 Panel 外观。

```jsx
<Card direction="row" size="2x4" appearance="solid-purple" gap={8}>
  <Stack direction="column" flex={0} width={144} height={136} gap={8}>
    <Stack direction="column" flex={0} width={144} height={64}>
      {/* <CardButton /> 或 <InfoBlock /> */}
    </Stack>
    <Stack direction="column" flex={0} width={144} height={64}>
      {/* <CardButton /> 或 <InfoBlock /> */}
    </Stack>
  </Stack>
  <Stack direction="column" flex={0} width={144} height={136} gap={8}>
    <Stack direction="column" flex={0} width={144} height={64}>
      {/* <CardButton /> 或 <InfoBlock /> */}
    </Stack>
    <Stack direction="column" flex={0} width={144} height={64}>
      {/* <CardButton /> 或 <InfoBlock /> */}
    </Stack>
  </Stack>
</Card>
```

## 5. 常见错误

### 5.1 选择阶段错误

- 2×4 顶层布局只允许“上下双区”“左右双区”“左内容右侧双槽”“四槽宫格”；内部只允许本文定义的 Sub-118 与 Sub-140 子布局。
- 不要生成上 1 下 2 的三按钮结构。三个 Action 不能单独凑成布局；只有另有一个真实、同级的 `InfoBlock` 并共同满足“四槽宫格”条件时，才允许生成三个 `CardButton` + 一个 `InfoBlock`。
- 不要把不同垂域的数据混放在同一内容父区。Action 可为了完整显示和视觉均衡进入相邻半卡操作槽，但按钮文本必须能独立说明操作。

### 5.2 顶层与子布局错误

- “上下双区”必须生成 296 × 20vp 整卡标题槽；“左右双区”的标题只能进入对应父内容区；“左内容右侧双槽”的局部标题只能进入 140 × 136vp 左内容区；“四槽宫格”不设置标题区。
- 除“上下双区”的整卡标题槽外，不要把局部标题高度固定为 20vp，也不要照抄 HTML 参考图中的 `top={24}`。
- “上下双区”不包含 Action，只能用于输入 `actions` 为空的任务；输入存在 Action 时必须更换为能提供合法按钮槽位的其他顶层布局。下明细区使用一组 `TextBlock` 或 `TopTextBottomValue`，不得追加按钮或混入其他下区组件。两个内容模块应按内容关系使用自然高度、上下分离或等分策略，不得机械固定为等高。
- “左右双区”不得把左右父区误当成一个跨区画布。普通父区使用背板，内部安全区为 118 × 112vp，纵向主要模块间距为 6vp；只有承载 Sub-140-D、Sub-140-E 或 Sub-140-H 的一侧可以取消背板并使用 140 × 136vp 子布局。中间间距始终为 12vp。

### 5.3 Action 与按钮错误

- 不要在 2×4 中使用 `CircleButton`。按钮类型由布局槽位决定：子布局操作槽使用 `PillButton`，固定操作槽使用 `CardButton`。
- 不要让 `PillButton` 或 `CardButton` 横跨 296vp 安全内容区；任何按钮都必须限制在左或右半卡宽父区内。
- 不要在“左内容右侧双槽”的右侧固定槽列中纵向堆叠 `PillButton`。
- `CardButton` 只能填入对应的 144 × 64vp 固定槽，不得自行改变父槽尺寸或跨槽排布。

### 5.4 固定槽、尺寸与间距错误

- “四槽宫格”必须完整保留四个 144 × 64vp 固定槽；不得留空、隐藏、占位、合并或改成动态高度。混用时同类组件必须进入同一列并按上→下排列。
- “左内容右侧双槽”的右侧只允许：单个右下 `CardButton`、两个 `CardButton`、两个 `InfoBlock`、上 `InfoBlock` + 下 `CardButton`。禁止单个 `InfoBlock`、交换混合组件顺序或使用其他组合。
- 该布局使用 12vp 左右间距；两个固定槽同时存在时使用 8vp 纵向间距，不要混用这两个间距。
- 单个 `CardButton` 只生成右下 144 × 64vp 固定槽；不要生成右上空槽或使用 `Stack` 模拟占位。
- 不要让整宽业务组件在 `align="flex-start"` 的父层中按内容宽度收缩。

### 5.5 背板与 Runtime 错误

- “左右双区”默认两侧都使用 `surface="backplate"`。只有承载 Sub-140-D、Sub-140-E 或 Sub-140-H 的一侧可以省略背板，另一侧仍须保留背板；不得把该例外用于其他子布局或同时取消两侧背板。
- `surface="backplate"` 只属于父内容区；子布局内部模块不得继承或重复生成背板颜色。
- 不要通过 `style`、`className`、硬编码颜色或未知 Props 增加 runtime 未公开的 Panel 外观。
- `CardButton`、`InfoBlock`、`PillButton` 的尺寸由外层槽位和 runtime 负责，不得向业务组件传入未知的尺寸、圆角或定位 Props。
