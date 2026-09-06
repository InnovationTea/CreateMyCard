# 2×4 卡片布局规范

## 1. 画布约束

| 项目 | 规格 |
|---|---:|
| 卡片尺寸 | 320 × 160vp |
| 圆角 | 20vp |
| 四边安全边距 | 12vp |
| 安全内容区 | 296 × 136vp |

所有可见内容必须限制在 296 × 136vp 安全内容区内，不得侵入 12vp 安全边距。

## 2. 基础框架

当前保留的 2×4 顶层 Type 只有 Type 12、Type 13、Type 14、Type 15、Type 15-R 和 Type 17，全部固定无公共标题并直接使用完整的 296 × 136vp 安全内容区。Type 13 需要标题时，只能在对应 118 × 112vp 父内容安全区的参考子布局内部使用局部标题；Type 15、Type 15-R、Type 17 的标题只能属于 140 × 136vp 内容区内部的适配子布局。Type 12、Type 14 不设置任何标题区。

局部标题必须来自用户意图或输入数据，不得为了填充版面虚构；标题会重复正文或剩余区域无法容纳业务组件时，应更换无标题子布局或更换顶层 Type。

| 区域 | 必要性 | 尺寸 / 弹性 | 布局规则 |
|---|---|---|---|
| 公共标题区 | 禁止 | 不生成 | 当前保留的所有 2×4 顶层 Type 均无公共标题，不保留标题空槽或标题后间距 |
| 子布局局部标题 | 按所选子布局必选 | `flex0; height:auto` | Type 13 子布局标题宽 118vp，相邻纵向模块间距 6vp；Type 15、Type 15-R、Type 17 的适配子布局标题宽 140vp，相邻主要模块间距 8vp |
| 内容区 | 必选 | 按 Type 使用 `flex0` 或 `flex1` | 宽高必须由所属 Type 确定，不得照抄 HTML 参考图中的固定 `top` |
| 操作区 | 按真实 Action 可选 | `flex0`; 单个按钮最多占一个半卡宽父区 | 1 个 Action 通常使用 `PillButton`，Type 17 可使用右下 144 × 64vp `CardButton` 槽；2 个 Action 能分别进入左右信息父区时使用左右双 `PillButton`，集中在同一个纯操作列时使用 Type 15／Type 15-R；3 个 Action 当前没有可用布局；4 个有效 CardButton 可使用 Type 14 四宫格 |
| 主要区域间距 | 按 Type 必选 | 通常 8vp；Type 15、Type 15-R、Type 17 左右为 12vp | 区域不存在时不保留空槽或相邻间距 |

局部标题参考高度：

- `SingleLineTitle` 是纯文本标题，高度固定为 18vp。
- `SingleLineTitle` 不支持标题 Icon；不得为参考图中的图标占位增加标题高度。
- `DoubleLineTitle` 含一行副信息时为 `18 + 4 + 18 = 40vp`；副信息为两行时继续自然增高。
- 局部标题高度记为 `T`。Type 13 子布局和 140vp 适配子布局必须分别按自身的 6vp、8vp 间距公式计算剩余空间。
- HTML 中的固定坐标和尺寸仅供视觉参考，不得写成 JSX 定位值；应按局部标题实际高度、区域间距和所属子布局的可用空间计算。

## 3. 布局选择逻辑

布局按以下顺序选择：

1. 读取信息处理阶段的垂域分组和 Action 语义关系；分组用于保持内容可识别，不作为牺牲按钮可读性的绝对位置约束。
2. 不生成整卡公共标题；根据信息语义判断是否需要局部标题，并检查候选 Type 是否提供对应的内部标题子布局。
3. 根据语义组数量、组间关系和 Action 数量选择 Type，而不是只按组件总数凑槽位。
4. 检查各组信息是否仍可独立识别，以及业务组件最小尺寸是否能放入目标槽位。
5. 最后按 Action 数量、可读性和视觉均衡选择按钮。Action 应尽量靠近相关数据，但不得因此造成文字裁剪、重叠或过度拥挤；每个 action 仍必须与一个按钮一一对应。

Type 约束顶层骨架、主要区域尺寸、区域间距和固定槽位类型。允许的内部变化必须由对应 Type 明确声明；例如 Type 14、Type 15、Type 15-R、Type 17 的固定槽只能填入 `CardButton` 或 `InfoBlock`，存在 Action 时必须使用 `CardButton`；Type 15、Type 15-R、Type 17 的 140 × 136vp 内容区只能使用规定的六种适配子布局。若改动已经改变顶层区域数量、主要尺寸公式、固定槽位置或语义归属，则应重新选择 Type，而不是继续沿用原 Type 名称。

### 3.1 语义分组与槽位分配

1. 2×4 场景先按垂域和大主题分组。跨垂域内容只有存在明确共同任务时才能放进同一张卡片，并且仍要保持各组可独立识别。
2. 直接服务某组的 Action 应优先靠近该组；当严格归组会导致按钮过窄、文字裁剪或布局失衡时，可将 Action 放入相邻的半卡操作槽，但按钮文本必须能独立说明操作。
3. 同组的数据、局部标题和辅助信息原则上应保持在同一连续父区域内；Action 可按可读性和视觉均衡放入对应或相邻操作槽。唯一允许的内容拆分是：单一垂域中已经形成“核心结论 + 属性明细”两个可独立识别的完整信息模块时，可以使用 Type 13 将核心值与状态放在一侧、同主题的多项属性明细放在另一侧。不得把彼此依赖的单个字段或同一组件应共同表达的内容随意拆到左右两区。
4. 布局阶段不得为了适配 Type 改变数据含义、丢失必需信息或虚构 Action；允许在保持信息可识别的前提下调整 Action 的视觉位置。
5. 顶层无公共标题时，仍可按所选子布局在父内容区内部使用局部标题。跨垂域分组缺少其他清晰主语时，各父区都应保留可见的业务标题。

| 冻结后的语义结构 | 优先布局 | 分配规则 |
|---|---|---|
| 单一语义组 | Type 12 | 两个上下内容区共同回答同一问题；不得追加公共标题或第三个顶层模块 |
| 单一语义组，恰好需要四个 CardButton／InfoBlock 固定槽 | Type 14 | 四槽必须全部有效并一一填满；Action 必须使用 `CardButton`，非操作信息可使用 `InfoBlock`；混用时同类组件进入同一列并按上→下排列 |
| 单一语义组，包含明确的核心结论与多项属性明细 | Type 13 变体 | 左区完整表达核心值与状态，右区使用 `TableText` 等组件完整表达同主题明细；两个父区均使用 `surface="backplate"`，不得把单个字段随意拆分成独立区域 |
| 单一语义组，只有 1 个 Action | Type 17 或 Type 13 变体 | Type 17 可在右下 144 × 64vp 固定槽中使用 `CardButton`，左侧保留 140 × 136vp 内容区；Type 13 使用含单个 `PillButton` 的 Type 10-A 参考子布局。不得生成整卡宽按钮 |
| 单一语义组，恰好 2 个同级 Action | Type 13 双 `PillButton` 变体，或 Type 15／Type 15-R | 两个 Action 能分别放入左右信息父区时可使用左右双 `PillButton`；内容集中在一侧时，可在另一侧的两个 144 × 64vp 固定槽中分别使用 CardButton |
| 单一语义组，恰好 3 个 Action 均服务该组或整卡共同任务 | 当前无可用 2×4 布局 | 停止并报告，不得删减、合并、虚构 Action 或用空槽伪装 Type 14 |
| 单一语义组，恰好 4 个 Action 均服务该组或整卡共同任务 | Type 14 | 四个 Action 分别使用一个 CardButton；四槽全部填满，并遵守同类组件按列纵排规则 |
| 两个同级语义组，没有独立 Action | Type 13；纵向关系更自然时可用 Type 12 | Type 13 左右父区分别承载一组；Type 12 上下内容区分别承载一组 |
| 卡片恰好有 2 个同级 Action，且可分别归入左右信息父区 | Type 13 双 `PillButton` 变体 | 左右父区分别使用含单个按钮的参考子布局，各放一个 118 × 36vp `PillButton` |
| 卡片恰好有 2 个 Action，且数据集中在一侧、操作集中在另一侧 | Type 15 或 Type 15-R | 两个 Action 固定槽分别使用 `CardButton`；内容在左用 Type 15，内容在右用 Type 15-R。只有非操作型槽位才可使用 `InfoBlock` |
| 跨垂域且不存在共同任务对象 | 不合并生成 | 保留主问题，其他组报告为未满足或另行生成，不得仅因 2×4 空间较大而拼卡 |

例如“晨跑准备”同时包含睡眠／运动健康与耳机／音乐时，可以因共同任务对象合并为一张卡。健康数据和设备数据仍分别进入 Type 13 的左右父区；若恰好有“进入锻炼”和“打开歌单”两个同级 Action，可使用左右双 `PillButton`。Action 应尽量靠近相关数据，但完整可读与布局均衡优先于机械的父区归属。

### 3.2 2×4 按钮限制

- 2×4 可以使用 `PillButton` 和 `CardButton`，禁止使用 `CircleButton`。
- 只有 1 个 Action 时通常使用 `PillButton`；Type 17 是固定结构例外，可在右下 144 × 64vp 槽中使用 `CardButton`，不得替换为其他按钮类型。
- 恰好 2 个同级 Action 且两个 Action 能分别进入左右信息父区时，左右父区分别使用含单个按钮的 Type 10-A 参考子布局，各放一个 118 × 36vp `PillButton`。
- Type 13 的 `PillButton` 位于 118 × 112vp 内部安全区的普通布局流中，固定为 118 × 36vp、圆角 18vp；不得使用绝对定位或底部 6vp 锚定规则。
- Type 15／Type 15-R 的两个固定侧槽均为 144 × 64vp，可各自独立使用 `CardButton` 或 `InfoBlock`；存在 Action 的槽必须使用 `CardButton`，只有非操作型槽位才可使用 `InfoBlock`。Type 13 的 Type 15 参考子布局只适用于同一父内容区内同时存在 118 × 28vp 紧凑内容，且两个 Action 都直接服务该内容的场景。三个 Action 当前没有可用的 2×4 布局；四个有效 Action 可分别使用一个 `CardButton` 填满 Type 14 四槽。
- Type 14 的四个 144 × 64vp 固定槽必须全部由有效的 `CardButton` 或 `InfoBlock` 一一填满，不得留空、占位、隐藏或合并。存在 Action 的槽必须使用 `CardButton`。左列为 A、C，右列为 B、D；混用两种组件时，同类组件必须在同一列按上→下排列，同一列不得混排不同类型；四槽同型时，两列分别纵向排列。
- 单个 `PillButton` 或 `CardButton` 都不得横跨 296vp 安全内容区。左右双 `PillButton` 是两个独立的半卡按钮，不是一个整卡宽按钮。
- Type 17 的右下固定槽允许使用 `CardButton` 或 `InfoBlock`，尺寸为 144 × 64vp；存在 Action 时必须使用 `CardButton`，不得使用其他按钮类型（包括 `PillButton`）。Type 13 可通过 Type 10-A、Type 12、Type 15 参考子布局使用规定数量的 `PillButton`；Type 15、Type 15-R 使用上下两个 144 × 64vp CardButton／InfoBlock 固定槽。顶层 Type 12 不包含操作槽。
- 同一个 action 只能生成一个按钮，不得用 `PillButton` 与 `CardButton` 重复表达。
- 没有 action 时不得为了填充布局而虚构按钮。

### 3.3 模块数与 Type

下表只统计 Type 自身的顶层内容槽和操作槽。当前保留的所有 2×4 顶层 Type 均无公共标题，子布局内部标题和内部按钮不增加顶层模块数。

| 内容／操作模块数 | Type |
|---:|---|
| 2 | Type 12、Type 13、Type 17 |
| 3 | Type 15、Type 15-R |
| 4 | Type 14 |

统计口径：

- Type 12、Type 13、Type 14、Type 15、Type 15-R、Type 17 均不生成公共标题模块。
- 每个独立内容槽和操作槽各计 1 个。
- Type 13 父内容区内部复用的子布局、背板和内部按钮不重复计入整卡顶层模块数。
- 模块数只用于初选 Type，最终仍需检查信息层级、标题高度和业务组件最小占位。

## 4. 内容骨架

所有顶层 Type 直接使用 296 × 136vp 安全内容区。下表及后续子布局公式中的 `T` 只表示子布局内部标题的实际高度，所有公式单位均为 vp。

| Type | 骨架 | 顶层模块弹性 | 尺寸与闭合公式 | 适用场景 / 特殊规则 |
|---|---|---|---|---|
| Type 12 | 无标题 + 上下二分 | 上下两个内容区均为 `flex1`、高度自适应 | 两区均宽 296vp；间距 8vp；参考高度均为 `(136 − 8) ÷ 2 = 64vp` | 固定承载两个上下排列的内容区；不设置标题区、操作槽或第三个顶层模块 |
| Type 13 | 无公共标题 + 左右均分双背板父内容区 | 两父区均 `flex0` | `142 + 12 + 142 = 296`；父区各 142 × 136；四边内缩 12vp 后，内部安全区各为 118 × 112 | 两个父区都使用背板并分别选择 Type 0、1、2、10-A、12、15 参考子布局之一；左右内部布局相互独立，不得跨区 |
| Type 17 | 无公共标题 + 左内容 + 右下 CardButton／InfoBlock | 两模块均为 `flex0` | 左内容区 140 × 136；右下槽 144 × 64；横向满足 `140 + 12 + 144 = 296` | 基于 Type 15 删除右上槽位；右下槽允许使用 `CardButton` 或 `InfoBlock`，存在 Action 时必须使用 `CardButton`；删除区域不保留占位；左内容区使用六种 140vp 适配子布局之一 |
| Type 15 | 无公共标题 + 左内容 + 右侧双 CardButton／InfoBlock | 三模块均为 `flex0` | 左内容区 140 × 136；右侧两槽均为 144 × 64、上下间距 8；横向 `140 + 12 + 144 = 296` | 两槽可各自使用 `CardButton` 或 `InfoBlock`，但存在 Action 时必须使用 `CardButton`；左内容区使用六种 140vp 适配子布局之一 |
| Type 15-R | 无公共标题 + 左侧双 CardButton／InfoBlock + 右内容 | 三模块均为 `flex0` | 左侧两槽均为 144 × 64、上下间距 8；右内容区 140 × 136；横向 `144 + 12 + 140 = 296` | Type 15 的镜像；存在 Action 时必须使用 `CardButton`；右内容区使用相同的六种适配子布局 |
| Type 14 | 无标题 + CardButton／InfoBlock 2×2 四宫格 | 四个固定槽均为 `flex0` | 每槽 144 × 64、圆角 16；横向 `144 + 8 + 144 = 296`；纵向 `64 + 8 + 64 = 136` | 四槽必须一一填满；存在 Action 时必须使用 `CardButton`；不得留空、隐藏、占位或合并；混用时同类组件按列纵排 |

## 5. 操作区

| Type | 按钮选择 | 槽位尺寸 | 排列方式 |
|---|---:|---|---|
| Type 13 | Type 10-A、Type 12 各含 1 个必选 `PillButton`；Type 15 含 2 个必选 `PillButton` | 每个按钮固定为 118 × 36vp | 按所选参考子布局进入普通纵向流；相邻纵向模块间距为 6vp，不使用绝对定位 |
| Type 14 | 四个固定槽分别使用 `CardButton` 或 `InfoBlock`；Action 必须使用 `CardButton` | 每槽 144 × 64vp、圆角 16vp | 2×2 排列，横向、纵向间距均为 8vp；四槽必填，混用时同类组件按列纵排 |
| Type 15 | 右侧两个固定槽可分别使用 `CardButton` 或 `InfoBlock`；Action 必须使用 `CardButton` | 每槽 144 × 64vp、圆角 16vp | 上下排列，间距 8vp |
| Type 15-R | 左侧两个固定槽可分别使用 `CardButton` 或 `InfoBlock`；Action 必须使用 `CardButton` | 每槽 144 × 64vp、圆角 16vp | 上下排列，间距 8vp |
| Type 17 | 右下槽有 Action 时必须使用 `CardButton`；无 Action 时可使用非操作型 `InfoBlock` | 固定槽位 144 × 64vp、圆角 16vp | 锚定安全内容区右下角；右上不保留占位 |

Type 13 参考子布局中的 `PillButton` 固定为 118 × 36vp、圆角 18vp；Type 15、Type 15-R、Type 17 的 140vp 适配子布局中保持 runtime 默认的 136 × 36vp 并左对齐，不拉伸到 144vp。Type 14、Type 15、Type 15-R 的 CardButton／`InfoBlock` 父槽，以及 Type 17 的 `CardButton`／`InfoBlock` 父槽，均固定为 144 × 64vp、圆角 16vp，不使用 48–64vp 动态槽高。生成 JSX 不向业务组件传入不存在的 `width`、`height`、`radius` 或 `position` Props。

当卡片包含两个信息组时，Action 应尽量靠近相关数据，但可读性、完整显示和视觉均衡的优先级更高。恰好两个同级 Action 且能分别进入左右信息父区时，可将两个 `PillButton` 分别放入左右半卡父区。若内容集中在一侧，另一侧需要两个固定槽，则使用 Type 15 或 Type 15-R；存在 Action 的槽必须使用 `CardButton`，非操作型槽可使用 `InfoBlock`，不得虚构 Action 或数据。

## 6. 尺寸与实现规则

- Type 12、Type 13、Type 14、Type 15、Type 15-R、Type 17 均固定无公共标题，直接使用完整的 296 × 136vp 安全内容区，不生成空标题槽或公共标题后间距。
- 基础等宽双列满足 `144 + 8 + 144 = 296`；144vp 子列满足 `68 + 8 + 68 = 144`。
- Type 15、Type 15-R、Type 17 使用非对称双列：`140 + 12 + 144 = 296` 或其镜像。
- `flex0` 表示模块不参与剩余空间分配；`flex1` 必须继续标明高度、宽度或宽高均自适应。
- 弹性纵向内容区使用 `flex={1} minHeight={0}`；固定区域使用明确的 `basis`、`width` 或 `height`。
- Type 15、Type 15-R 的 `CardButton`／`InfoBlock` 槽固定为 144 × 64vp，圆角为 16vp；存在 Action 的槽必须使用 `CardButton`。两布局均不设置公共标题，槽位尺寸不得动态变化。
- Type 14 固定无标题，四个 `CardButton`／`InfoBlock` 槽均为 144 × 64vp、圆角 16vp、`flex0`；存在 Action 的槽必须使用 `CardButton`。横向和纵向间距均为 8vp，四槽必须一一填满；混用时同类组件必须在同一列按上→下排列，四槽同型时两列分别纵向排列。
- Type 15 的左内容区和 Type 15-R 的右内容区均固定为 140 × 136vp，并与 Type 17 共用 Type 0、Type 1、Type 10-A、Type 12、Type 15、Type 10-B 六种适配子布局。满宽内容模块使用 140vp，内部 `PillButton` 保持 136 × 36vp 并左对齐。
- Type 12 固定使用上下两个 `flex={1} minHeight={0}` 内容区，宽度均为 296vp，中间间距为 8vp；参考高度均为 64vp。不得增加标题区、操作槽、第三个顶层模块或固定高度变体。
- Type 13 的左右父区分别承载一个完整语义组或一个可独立识别的完整信息模块，不得在同一父区混排两组信息。两个父区固定为 142 × 136vp，间距 12vp，并都使用背板；每个父区四边内缩 12vp，内部安全区为 118 × 112vp。父区内部必须选择六种参考子布局之一，相邻纵向主要模块统一使用 6vp 间距。所有内容必须留在所属父区内，不得跨区、重叠或占用中间 12vp 间距。
- Type 17 只保留一个右下 144 × 64vp `CardButton`／`InfoBlock` 槽位，圆角为 16vp；存在 Action 时必须使用 `CardButton`，不得使用其他按钮类型（包括 `PillButton`）。不得保留右上空槽、占位模块或虚构 Action。左内容区固定为 140 × 136vp，并使用 Type 0、Type 1、Type 10-A、Type 12、Type 15、Type 10-B 的 140vp 适配子布局之一。
- 整宽组件必须占满所属模块：整宽区为 296vp，普通等宽列为 144vp，非对称内容列为 140vp。包裹层使用 `width="full" minWidth={0}`。
- 标题增高或文本换行导致槽位小于业务组件最小尺寸时，应更换 Type、减少内容或停止并报告，不得依赖裁剪或溢出。
- 产品规格使用 vp；HTML 骨架预览可使用同数值 px 做 1:1 校核。

## 7. 标准 JSX 布局模板
共同规则：

- 根节点固定为 `<Card size="2x4" appearance="...">`；默认 `padding={12}` 得到 296 × 136vp 安全内容区。
- 模板禁止 `style`、`className`、spread Props 和硬编码颜色。
- 2×4 单 Action 通常使用 `PillButton`，Type 17 的右下固定槽是例外，有 Action 时必须使用 `CardButton`；两个 Action 分别进入左右信息父区时可使用左右双 `PillButton`，集中在同一侧固定槽列时使用 Type 15／Type 15-R 的两个 CardButton 槽。三个 Action 当前没有可用的 2×4 布局；四个有效 Action 可使用 Type 14 的四个 CardButton 槽。每个按钮都必须限制在自己的半卡宽父区或半卡宽子槽内。
- 示例中的 `dataIds` 与 `actionId` 只说明绑定位置；实际生成必须替换为输入中真实存在的 ID。

以下所有顶层 Type 示例均固定无公共标题，不得在 `Card` 顶部追加 `SingleLineTitle`、`DoubleLineTitle`、空标题槽或标题后间距。需要标题时，只能选择 Type 13 中允许标题的参考子布局，或 Type 15、Type 15-R、Type 17 中允许标题的 140vp 适配子布局。

### 7.1 Type 12：上下二分（无标题）

```jsx
<Card size="2x4" appearance="purple-gradient" gap={8}>
  <Stack flex={1} minHeight={0} width="full">
    {/* 上内容区：参考尺寸 296 × 64 */}
  </Stack>

  <Stack flex={1} minHeight={0} width="full">
    {/* 下内容区：参考尺寸 296 × 64 */}
  </Stack>
</Card>
```

Type 12 固定由上下两个内容区组成，不设置标题区或操作槽。两个内容区宽度均为 296vp，均使用 `flex={1} minHeight={0}`，中间间距固定为 8vp。父容器在 136vp 可用高度内等分剩余空间，参考尺寸均为 `296 × 64vp`，满足 `64 + 8 + 64 = 136vp`。不得增加第三个顶层模块、改用固定高度分配或在任一内容区外追加按钮。

### 7.2 Type 13：左右均分双内容区（无公共标题）

```jsx
<Card size="2x4" appearance="neutral-soft" direction="row" gap={12}>
  <Stack surface="backplate" basis={142} width={142} height={136} align="center" justify="center">
    <Stack basis={112} width={118} height={112} gap={6}>
      <Stack flex={0} width={118}>
        <SingleLineTitle title="日程" />
      </Stack>
      <Stack flex={1} width={118} minHeight={0} align="flex-start">
        <EventCard title="项目例会" time="10:00-14:00" location="练秋湖A1-3-41R" />
      </Stack>
    </Stack>
  </Stack>

  <Stack surface="backplate" basis={142} width={142} height={136} align="center" justify="center">
    <Stack basis={112} width={118} height={112} gap={6}>
      <Stack flex={0} width={118}>
        <SingleLineTitle title="健康数据" />
      </Stack>
      <Stack flex={1} width={118} minHeight={0}>
        <Summary content="今日 6200 步" />
      </Stack>
      <Stack flex={0} width={118} height={36}>
        <PillButton label="进入锻炼" icon="figure_run.svg" appearance="card" actionId="event.open.health.sport" />
      </Stack>
    </Stack>
  </Stack>
</Card>
```

Type 13 固定为无公共标题的左右均分双内容区。左右父内容区均为 `flex0`、142 × 136vp，水平间距为 12vp，满足 `142 + 12 + 142 = 296vp`。两个父区都使用 `surface="backplate"`，圆角为 16vp，并裁剪内部背景。每个父区四边内缩 12vp，形成 118 × 112vp 内部安全区。左右可分别选用不同参考子布局，但内部模块不得跨区、共享尺寸或占用中间间距。

#### 7.2.1 Type 13 通用规则

- Type 13 整卡不设置公共标题；需要标题时，在对应父内容区内部使用局部标题。
- 左右父内容区固定为 142 × 136vp，均使用 `surface="backplate"`；不得生成透明父区或单侧背板变体。
- `surface="backplate"` 只写在左右顶层父 `Stack` 上，不写在局部标题、内容或按钮包装层上。
- 父内容区背板在 Light Mode 使用当前卡片背景对应的主题深色、透明度 5%；Dark Mode 使用白色、透明度 10%。该颜色规则只属于左右父内容区，不扩散到子布局内部模块。
- 每个父区四边保留 12vp 安全边距，内部布局区固定为 118 × 112vp。
- 父区圆角为 16vp，并使用裁剪保证背板背景不越过圆角。
- 左右父区可分别选择不同参考子布局，内部模块不重复计入整卡顶层模块数。
- 子布局中的标题、内容与 `PillButton` 等相邻纵向主要模块统一使用 6vp 间距；横向间距按相应子布局定义。
- 标题宽 118vp、`flex0`、`height:auto`；公式中的 `T` 为标题实际高度，v5 骨架以 `T = 20vp` 为参考态。
- `PillButton` 固定为 118 × 36vp、圆角 18vp，并作为 `flex0` 模块参与普通布局流，不使用绝对定位。
- 计算结果小于组件最小尺寸时，必须更换子布局或顶层布局，不得压缩安全边距或规定间距。

#### 7.2.2 Type 13 父内容区参考子布局

Type 13 左右两个背板父区可分别选择下列六种参考子布局。子布局只复用对应 2×2 Type 的模块关系，不是新的 2×4 顶层 Type，也不沿用 2×2 的 136 × 136vp 尺寸。

##### 通用约束

- 每个背板父区固定为 `<Stack surface="backplate" basis={142} width={142} height={136}>`，圆角和裁剪由 runtime 提供。父区属于固定模块，不参与整卡剩余空间分配。
- 每个背板内必须建立水平、垂直居中的 118 × 112vp 内层 `Stack`，形成四边各 12vp 的安全边距。
- 所有子布局，包括含 `PillButton` 的子布局，都在 118 × 112vp 内部安全区中使用普通布局流。
- 推荐公共外壳如下：

```jsx
<Stack surface="backplate" basis={142} width={142} height={136} align="center" justify="center">
  <Stack basis={112} width={118} height={112} minWidth={0}>
    {/* 参考子布局内容 */}
  </Stack>
</Stack>
```

- 内层相邻纵向主要模块统一使用 6vp 间距；横向间距按对应子布局定义。
- 标题槽宽 118vp，使用 `<Stack flex={0} width={118}>`，高度由标题组件自然撑开。以下公式中的 `T` 为标题实际高度，参考态为 `T = 20vp`。
- 标记为固定的模块使用 `flex={0}` 或明确的 `basis`／`height`；参与剩余高度分配的内容模块使用 `flex={1} minHeight={0}`。`flex0`、`flex1` 只是尺寸关系说明，不是可以直接生成的 JSX Prop 名。
- 背板已由 runtime 继承 16px 圆角并裁剪内部背景；不得在子布局内使用原生元素、`style`、`className` 或硬编码背景模拟第二层 Panel，也不得产生越过圆角的直角背景。
- `surface="backplate"` 必须由 runtime 映射为规定的主题背板：Light Mode 为当前卡片背景对应的主题深色 5%，Dark Mode 为白色 10%；子布局组件继续遵循各自的颜色规范。
- 左右子布局相互独立，内部模块不得跨区排布、共享尺寸或共享对齐基准；子布局内部模块不重复计入 Type 13 的整卡顶层模块数。
- 公式所得空间若小于所选业务组件的真实最小宽高，则该子布局与组件不兼容。必须更换组件组合、参考子布局或顶层布局；不得侵入 12vp 安全边距、压缩 6vp 规定间距、缩小按钮高度或依赖裁剪隐藏内容。

##### Type 0 参考子布局：无标题单内容区

- 骨架：无标题 + 单内容区。
- 内容区固定为 118 × 112vp，使用 `flex={0}`，内容在区域内水平、垂直居中；仅允许放置 Design System 中归类为 Data Display 的组件。

```jsx
<Stack basis={112} width={118} height={112} align="center" justify="center">
  {/* 单个核心内容模块 */}
</Stack>
```

##### Type 1 参考子布局：标题 + 单内容区

- 标题区必选，宽 118vp，自然高度为 `T`。
- 内容区宽 118vp，使用 `flex={1} minHeight={0}`；标题与内容间距为 6vp，内容左对齐且底端对齐。
- 内容区高度为 `112 − T − 6 = 106 − T`；当 `T = 20vp` 时，参考尺寸为 118 × 86vp。

```jsx
<Stack basis={112} width={118} height={112} gap={6}>
  <Stack flex={0} width={118}>{/* 局部标题 */}</Stack>
  <Stack flex={1} width={118} minHeight={0} align="flex-start" justify="flex-end">{/* 单个内容模块 */}</Stack>
</Stack>
```

##### Type 2 参考子布局：标题 + 核心内容 + 明细内容

- 标题区必选，宽 118vp，自然高度为 `T`。
- 核心内容区和明细内容区均宽 118vp，均使用 `flex={1} minHeight={0}`，默认等分标题及两处 6vp 间距之外的剩余高度。
- 单个内容区高度为 `(112 − T − 6 − 6) ÷ 2 = (100 − T) ÷ 2`；当 `T = 20vp` 时，两区参考尺寸均为 118 × 40vp。核心区左对齐且顶端对齐，明细区左对齐且底端对齐。

```jsx
<Stack basis={112} width={118} height={112} gap={6}>
  <Stack flex={0} width={118}>{/* 局部标题 */}</Stack>
  <Stack flex={1} width={118} minHeight={0} align="flex-start" justify="flex-start">{/* 核心内容 */}</Stack>
  <Stack flex={1} width={118} minHeight={0} align="flex-start" justify="flex-end">{/* 明细内容 */}</Stack>
</Stack>
```

##### Type 10-A 参考子布局：标题 + 内容 + PillButton

- 标题区必选，宽 118vp，自然高度为 `T`；内容区宽 118vp，使用 `flex={1} minHeight={0}`。
- `PillButton` 必选、不得缺省，固定为 118 × 36vp、圆角 18vp，并作为 `flex0` 模块进入普通纵向流。
- 标题、内容区和按钮之间均为 6vp；内容区高度为 `112 − T − 6 − 6 − 36 = 64 − T`。当 `T = 20vp` 时，参考尺寸为 118 × 44vp。

```jsx
<Stack basis={112} width={118} height={112} gap={6}>
  <Stack flex={0} width={118}>{/* 局部标题 */}</Stack>
  <Stack flex={1} width={118} minHeight={0}>{/* 内容 */}</Stack>
  <Stack flex={0} width={118} height={36}>
    <PillButton label="操作" appearance="card" actionId="action.example" />
  </Stack>
</Stack>
```

##### Type 12 参考子布局：双列内容 + PillButton

- 无标题。上方 A、B 内容区均固定为 55 × 70vp，两列水平间距为 8vp。
- `PillButton` 必选、不得缺省，固定为 118 × 36vp、圆角 18vp；双列内容区与按钮间距为 6vp。
- 横向满足 `55 + 8 + 55 = 118vp`；纵向满足 `70 + 6 + 36 = 112vp`。

```jsx
<Stack basis={112} width={118} height={112} gap={6}>
  <Stack direction="row" basis={70} width={118} height={70} gap={8}>
    <Stack basis={55} width={55} height={70}>{/* A */}</Stack>
    <Stack basis={55} width={55} height={70}>{/* B */}</Stack>
  </Stack>
  <Stack flex={0} width={118} height={36}>
    <PillButton label="操作" appearance="card" actionId="action.example" />
  </Stack>
</Stack>
```

##### Type 15 参考子布局：紧凑内容 + 两个纵向 PillButton

- 无标题。内容区固定为 118 × 28vp，仅适合单行文字、状态值或简单图标；内部组件最小高度超过 28vp 时不得使用该参考子布局。
- 两个 `PillButton` 均为必选，固定为 118 × 36vp、圆角 18vp。内容区与第一个按钮、两个按钮之间均使用 6vp 间距。
- 纵向满足 `28 + 6 + 36 + 6 + 36 = 112vp`。

```jsx
<Stack basis={112} width={118} height={112} gap={6}>
  <Stack flex={0} width={118} height={28}>{/* 单行紧凑内容 */}</Stack>
  <Stack flex={0} width={118} height={36}>
    <PillButton label="操作一" appearance="card" actionId="action.first" />
  </Stack>
  <Stack flex={0} width={118} height={36}>
    <PillButton label="操作二" appearance="card" actionId="action.second" />
  </Stack>
</Stack>
```

### 7.3 Type 17：左内容 + 右下 CardButton／InfoBlock（无标题）

```jsx
<Card size="2x4" appearance="blue-soft" direction="row" gap={12}>
  <Stack basis={140} width={140} height="full" minWidth={0}>
    {/* 左内容区：选择 7.3.1 中的一种共用 140vp 适配子布局 */}
  </Stack>

  <Stack basis={144} width={144} height="full" justify="end">
    <Stack basis={64} width={144} height={64}>
      <CardButton
        text="查看详情"
        actionId="content.openDetails"
      />
    </Stack>
  </Stack>
</Card>
```

Type 17 基于 Type 15 删除右上槽位。左内容区固定为 140 × 136vp，右下 `CardButton`／`InfoBlock` 槽固定为 144 × 64vp、圆角 16vp，左右间距为 12vp，满足 `140 + 12 + 144 = 296vp`。右下槽锚定安全内容区右下角；存在 Action 时必须放置一个 `CardButton`，不得使用其他按钮类型（包括 `PillButton`）；无 Action 时可放置一个非操作型 `InfoBlock`。删除的右上槽位不保留占位模块。两个顶层模块均为 `flex0`，内容不得跨区。

#### 7.3.1 Type 15、Type 15-R、Type 17 共用内容区适配子布局

以下六种骨架由对应 2×2 Type 适配而来，适用于 Type 15 的左内容区、Type 15-R 的右内容区和 Type 17 的左内容区，统一使用完整的 140 × 136vp。满宽内容模块扩展至 140vp；`PillButton` 保持 136 × 36vp 并左对齐，右侧留 4vp。子布局中的内部标题不是整卡公共标题。

##### Type 0 · 140vp 适配版

- 无标题单内容区，固定为 140 × 136vp，内容水平、垂直居中。
- 仅允许放置 Design System 中归类为 Data Display 的组件。

```jsx
<Stack width={140} height={136} align="center" justify="center">
  {/* Data Display 组件 */}
</Stack>
```

##### Type 1 · 140vp 适配版

- 标题宽 140vp、`flex0`、`height:auto`；内容区 `flex1`、高度自适应，并左对齐、底端对齐。
- 标题与内容间距为 8vp；内容区高度为 `136 − T − 8 = 128 − T`。参考 `T = 20vp` 时，内容区高 108vp。

```jsx
<Stack width={140} height={136} gap={8}>
  <Stack flex={0} width={140}>{/* 内部标题 */}</Stack>
  <Stack flex={1} width={140} minHeight={0} align="flex-start" justify="flex-end">{/* 内容 */}</Stack>
</Stack>
```

##### Type 10-A · 140vp 适配版

- 标题、内容区和 `PillButton` 均为必选，相邻模块间距为 8vp。
- `PillButton` 固定为 136 × 36vp 并左对齐；内容区高度为 `136 − T − 8 − 8 − 36 = 84 − T`。参考 `T = 20vp` 时，内容区高 64vp。

```jsx
<Stack width={140} height={136} gap={8}>
  <Stack flex={0} width={140}>{/* 内部标题 */}</Stack>
  <Stack flex={1} width={140} minHeight={0}>{/* 内容 */}</Stack>
  <Stack flex={0} width={136} height={36}>
    <PillButton label="操作" appearance="card" actionId="action.example" />
  </Stack>
</Stack>
```

##### Type 12 · 140vp 适配版

- 无标题；上方双列内容区为两个 66 × 92vp 固定模块，横向间距为 8vp。
- `PillButton` 必选，固定为 136 × 36vp 并左对齐；内容行与按钮间距为 8vp。
- 横向满足 `66 + 8 + 66 = 140vp`；纵向满足 `92 + 8 + 36 = 136vp`。

```jsx
<Stack width={140} height={136} gap={8}>
  <Stack direction="row" basis={92} width={140} height={92} gap={8}>
    <Stack basis={66} width={66} height={92}>{/* A */}</Stack>
    <Stack basis={66} width={66} height={92}>{/* B */}</Stack>
  </Stack>
  <Stack flex={0} width={136} height={36}>
    <PillButton label="操作" appearance="card" actionId="action.example" />
  </Stack>
</Stack>
```

##### Type 15 · 140vp 适配版

- 无标题；内容区固定为 140 × 48vp，两个 `PillButton` 均为必选并固定为 136 × 36vp。
- 内容区与第一个按钮、两个按钮之间均为 8vp；满足 `48 + 8 + 36 + 8 + 36 = 136vp`。

```jsx
<Stack width={140} height={136} gap={8}>
  <Stack flex={0} width={140} height={48}>{/* 内容 */}</Stack>
  <Stack flex={0} width={136} height={36}>
    <PillButton label="操作一" appearance="card" actionId="action.first" />
  </Stack>
  <Stack flex={0} width={136} height={36}>
    <PillButton label="操作二" appearance="card" actionId="action.second" />
  </Stack>
</Stack>
```

##### Type 10-B · 140vp 适配版

- 标题、Hero、次要信息和 `PillButton` 均为必选；标题、内容组、按钮之间为 8vp，Hero 与次要信息之间为 2vp。
- Hero 与次要信息均按内容自然撑高，不强制等高；`PillButton` 固定为 136 × 36vp 并左对齐。

```jsx
<Stack width={140} height={136} gap={8}>
  <Stack flex={0} width={140}>{/* 内部标题 */}</Stack>
  <Stack flex={1} width={140} minHeight={0} gap={2}>
    <Stack width={140}>{/* Hero：按内容自然撑高 */}</Stack>
    <Stack width={140}>{/* 次要信息：按内容自然撑高 */}</Stack>
  </Stack>
  <Stack flex={0} width={136} height={36}>
    <PillButton label="操作" appearance="card" actionId="action.example" />
  </Stack>
</Stack>
```

### 7.4 Type 15：左内容 + 右侧双 CardButton／InfoBlock（无标题）

```jsx
<Card size="2x4" appearance="cloudy-gradient" direction="row" gap={12}>
  <Stack basis={140} width={140} height={136} minWidth={0}>
    {/* 选择 7.3.1 中的一种共用 140vp 适配子布局 */}
  </Stack>

  <Stack basis={144} width={144} height={136} gap={8}>
    <Stack basis={64} width={144} height={64}>
      <CardButton text="操作一" actionId="action.first" />
    </Stack>
    <Stack basis={64} width={144} height={64}>
      <CardButton text="操作二" actionId="action.second" />
    </Stack>
  </Stack>
</Card>
```

Type 15 固定由左侧 140 × 136vp 内容区和右侧两个 144 × 64vp `CardButton`／`InfoBlock` 槽组成。右侧两槽上下间距为 8vp，满足 `64 + 8 + 64 = 136vp`；左右间距为 12vp，满足 `140 + 12 + 144 = 296vp`。两个固定槽可分别独立使用 `CardButton` 或 `InfoBlock`，但存在 Action 的槽必须使用 `CardButton`；不得改变槽位数量、尺寸、间距或位置。左内容区必须使用 7.3.1 中的六种共用适配子布局之一。

### 7.5 Type 15-R：左侧双 CardButton／InfoBlock + 右内容（无标题）

```jsx
<Card size="2x4" appearance="orange-gradient" direction="row" gap={12}>
  <Stack basis={144} width={144} height={136} gap={8}>
    <Stack basis={64} width={144} height={64}>
      <CardButton text="操作一" actionId="action.first" />
    </Stack>
    <Stack basis={64} width={144} height={64}>
      <CardButton text="操作二" actionId="action.second" />
    </Stack>
  </Stack>

  <Stack basis={140} width={140} height={136} minWidth={0}>
    {/* 选择 7.3.1 中的一种共用 140vp 适配子布局 */}
  </Stack>
</Card>
```

Type 15-R 是 Type 15 的镜像。左侧两个固定槽均为 144 × 64vp，上下间距为 8vp；右内容区为 140 × 136vp；左右间距为 12vp，满足 `144 + 12 + 140 = 296vp`。两个固定槽可分别独立使用 `CardButton` 或 `InfoBlock`，但存在 Action 的槽必须使用 `CardButton`；右内容区与 Type 15、Type 17 共用 7.3.1 中的六种适配子布局。

### 7.6 Type 14：CardButton／InfoBlock 四宫格（无标题）

```jsx
<Card size="2x4" appearance="blue-soft">
  <Grid columns={2} rows="64px 64px" gap={8} width="full" height="full">
    <Stack width={144} height={64}>
      <CardButton text="操作一" actionId="action.first" />
    </Stack>
    <Stack width={144} height={64}>{/* B：InfoBlock */}</Stack>
    <Stack width={144} height={64}>
      <CardButton text="操作二" actionId="action.second" />
    </Stack>
    <Stack width={144} height={64}>{/* D：InfoBlock */}</Stack>
  </Grid>
</Card>
```

Type 14 固定无标题，由四个 `flex0` 的 `CardButton`／`InfoBlock` 固定槽组成。每槽为 144 × 64vp、圆角 16vp；横向和纵向间距均为 8vp，满足 `144 + 8 + 144 = 296vp` 与 `64 + 8 + 64 = 136vp`，完整铺满安全内容区。

四个槽位必须全部由有效的 `CardButton` 或 `InfoBlock` 一一填满，存在 Action 的槽必须使用 `CardButton`。不得留空、占位、隐藏或合并，内容不得跨格或占用间距。左列为 A、C，右列为 B、D；同类组件必须占用同一列并按上→下排列，不得横向并排在同一行。`CardButton` 与 `InfoBlock` 同时出现时，同一列不得混排不同类型；四槽全部使用同一组件类型时，两列分别按上→下排列。

## 8. 常见错误

- 2×4 顶层布局只允许 Type 12、Type 13、Type 14、Type 15、Type 15-R、Type 17。Type 0、Type 1、Type 2、Type 10-A、Type 10-B 等名称只可按本文规定作为内部参考／适配子布局使用，不得生成同名 2×4 顶层 Type。
- 不要在 2×4 中使用 `CircleButton`。只有一个 Action 时通常使用单 `PillButton`；Type 17 是例外，其右下 144 × 64vp 槽有 Action 时必须使用 `CardButton`。两个 Action 分别进入左右信息父区时可使用左右双 `PillButton`；集中在同一侧固定槽列时使用 Type 15／Type 15-R 的两个 CardButton 槽。
- 不要把标题高度固定为 20vp，也不要照抄 HTML 参考图中的 `top={24}`。
- 不要为任何保留的 2×4 顶层 Type 生成公共标题、空标题槽或公共标题后间距。Type 13 的标题只能作为局部标题进入对应父内容区；Type 15、Type 15-R、Type 17 的标题只能属于 140 × 136vp 内容区内部的适配子布局；Type 12、Type 14 不设置标题区。
- 不要使用 Type 8 的上 1 下 2 按钮结构。三个 Action 当前没有可用的 2×4 布局，应停止并报告；四个有效 Action 可分别使用一个 CardButton 填满 Type 14 四槽。
- Type 14 必须完整保留四个 144 × 64vp、圆角 16vp 的 `CardButton`／`InfoBlock` 固定槽，存在 Action 的槽必须使用 `CardButton`。不得留空、隐藏、占位、合并或改成动态高度。混用两种组件时，同类组件必须进入同一列并按上→下排列，同一列不得混排不同类型；四槽同型时，两列分别纵向排列。
- Type 15、Type 15-R 的每个 144 × 64vp 固定槽只能放一个 `CardButton` 或 `InfoBlock`，存在 Action 的槽必须使用 `CardButton`；不得合并槽位、跨槽排布或改变槽位尺寸。
- 不要在 Type 15／Type 15-R 的固定侧槽列中纵向堆叠两个 `PillButton`。Type 13 的 Type 15 参考子布局仅限同一父内容区中同时存在 118 × 28vp 紧凑业务内容、且两个 Action 都直接服务该内容的场景。
- `CardButton` 只能填入对应的 144 × 64vp 固定 CardButton 槽，不得自行改变父槽尺寸或跨槽排布。
- 不要让 `PillButton` 或 `CardButton` 横跨 296vp 安全内容区；任何按钮都必须限制在左或右半卡宽父区内。
- 同一语义组／操作区域有且只有一个 Action 时，不要生成整卡宽操作槽；通常使用 Type 13 变体中的 `PillButton`，或使用 Type 17 右下 144 × 64vp 槽中的 `CardButton`。顶层 Type 12 不包含 Action，不得向其上下二分骨架追加按钮。
- 不要把不同垂域的数据混放在同一内容父区。Action 应尽量靠近相关数据，但可为了完整显示和视觉均衡放入相邻半卡操作槽；此时按钮文本必须能独立说明操作。
- Type 13 不得把左右父区误当成一个跨区画布。左右父区固定为 142 × 136vp，均使用背板，中间间距为 12vp；每个父区内部安全区为 118 × 112vp。子布局中的纵向主要模块间距为 6vp，`PillButton` 不得使用绝对定位。内容不得跨越父区边界或占用中间间距。
- Type 15、Type 15-R 使用 12vp 左右间距，固定侧槽之间使用 8vp 纵向间距；不要混用这两个间距。
- Type 17 只保留一个右下 144 × 64vp `CardButton`／`InfoBlock` 槽；存在 Action 时必须使用 `CardButton`。不要生成右上空槽或用 `Stack` 模拟占位。
- 不要让整宽业务组件在 `align="flex-start"` 的父层中按内容宽度收缩。
- 不要通过 `style`、`className`、硬编码颜色或未知 Props 增加 runtime 未公开的 Panel 外观；Type 13 背板只使用公开的 `Stack surface="backplate"`。

## 9. Runtime 执行基线

- 所有 `CardButton` 统一使用当前 runtime 的固定 16px 圆角，只能出现在半卡宽父区内的上下竖排操作槽中，不生成 `radius` 或 `style`。
- Type 13 参考子布局中的 `PillButton` 固定为 118 × 36vp、圆角 18vp，作为 `flex0` 模块进入普通布局流。Type 10-A、Type 12、Type 15 参考子布局中的按钮均为必选，不得缺省；需要侧边固定槽列时使用 Type 15／Type 15-R。背板内 `PillButton` 使用 `appearance="card"`，不得拉伸为整卡宽度。
- Type 13 使用合法的 `Card.appearance` 作为整卡背景；左右父区都必须使用公开的 `Stack surface="backplate"`，不得生成透明或单侧背板变体。父区内部只使用六种参考子布局，不生成 runtime 未公开的 Panel appearance、圆角或裁剪 Props。
- Type 13 的 `surface="backplate"` 在 Light Mode 映射为当前卡片背景对应的主题深色 5%，在 Dark Mode 映射为白色 10%；子布局内部模块不得继承或重复生成该背板颜色。
- Type 17 的右下 `CardButton`／`InfoBlock` 使用固定的 144 × 64vp 父槽和 16vp 圆角，锚定安全内容区右下角；存在 Action 时组件必须为 `CardButton`，不得使用其他按钮类型（包括 `PillButton`）。左内容区的满宽模块使用 140vp，内部 `PillButton` 保持 136 × 36vp 并左对齐。
- Type 15、Type 15-R 的两个 `CardButton`／`InfoBlock` 父槽均固定为 144 × 64vp、圆角 16vp、纵向间距 8vp；存在 Action 的槽必须承载 `CardButton`。内容区固定为 140 × 136vp，并与 Type 17 共用六种 140vp 适配子布局。
- Type 14 的父槽固定为 144 × 64vp、圆角边界 16vp，只允许承载一个 `CardButton` 或 `InfoBlock`；存在 Action 的槽必须承载 `CardButton`。视觉由槽内组件负责，不生成额外 Panel 外观。
