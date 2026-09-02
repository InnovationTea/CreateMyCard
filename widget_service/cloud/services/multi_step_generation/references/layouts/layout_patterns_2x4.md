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

标题是卡片的信息层，不是 Type 的固定属性。所有 2×4 Type 都允许按输入语义生成或省略标题；不得因为选择了 Type 12–17 就删除输入中需要表达的标题。Type 13 使用 `surface="backplate"` 时属于例外：标题必须进入其所描述的背板内部，不得作为 Card 顶部、背板外的全局标题悬在两个父区上方。

最简单的判断原则是：输入包含需要命名主题的数据类信息或日程类信息时，允许生成全局标题，例如天气、睡眠、设备状态、运动数据、会议或日程；标题内容必须来自用户意图或输入数据，不得为了填充版面虚构。没有明确主题、标题会重复正文，或加入标题后剩余区域无法容纳业务组件时，可以省略全局标题并保留必要的局部标题。

| 区域 | 必要性 | 尺寸 / 弹性 | 布局规则 |
|---|---|---|---|
| 标题区 | 按输入语义可选 | `flex0; height:auto`; 宽 296vp | 高度由标题组件自然撑开，不参与剩余空间分配；标题是否存在不限制 Type 选择 |
| 标题 Icon | 按标题组件选用 | 20 × 20vp | 锚定标题区右上角；标题区高度取文字组与 Icon 实际高度的较大值 |
| 标题后间距 | 存在全局标题时必选 | 4vp | 从标题区实际底部开始计算；无标题时不保留空间距 |
| 内容区 | 必选 | 按 Type 使用 `flex0` 或 `flex1` | 宽高必须由所属 Type 确定，不得照抄 HTML 参考图中的固定 `top` |
| 操作区 | 按真实 Action 可选 | `flex0`; 单个按钮最多占一个半卡宽父区 | 1 个 Action 使用 `PillButton`；2 个 Action 能分别进入左右信息父区时使用左右双 `PillButton`，集中在同一个纯操作列时必须使用上下竖排的 `CardButton`；3–4 个 Action 可使用 Type 9 的 2×2 `CardButton` 网格 |
| 主要区域间距 | 按 Type 必选 | 通常 8vp；Type 15–17 左右为 12vp | 区域不存在时不保留空槽或相邻间距 |

标题参考高度：

- `SingleLineTitle` 文本高 18vp；带 20vp Icon 时标题区通常为 20vp。
- `DoubleLineTitle` 含一行副信息时为 40vp；副信息为两行时继续自然增高。
- 全局标题存在时，其下方可用高度记为 `A = 136 − T − 4`，其中 `T` 为标题实际高度；无全局标题时 `A = 136`。
- HTML 中的 `top:24vp`、112vp 和 52vp 都是 `T = 20vp` 时的参考值，不得写成固定 JSX 定位值。

## 3. 布局选择逻辑

布局按以下顺序选择：

1. 读取信息处理阶段的垂域分组和 Action 语义关系；分组用于保持内容可识别，不作为牺牲按钮可读性的绝对位置约束。
2. 根据信息语义决定是否需要全局标题；标题选择独立于 Type，不得先按 Type 删除标题。
3. 根据语义组数量、组间关系和 Action 数量选择 Type，而不是只按组件总数凑槽位。
4. 检查各组信息是否仍可独立识别，以及业务组件最小尺寸是否能放入目标槽位。
5. 最后按 Action 数量、可读性和视觉均衡选择按钮。Action 应尽量靠近相关数据，但不得因此造成文字裁剪、重叠或过度拥挤；每个 action 仍必须与一个按钮一一对应。

Type 只约束顶层骨架、主要区域尺寸和区域间距，不锁死区域内部的业务组件组合。每个 Type 都允许在不改变顶层骨架和语义分组的前提下形成变体，例如替换业务组件、调整内部对齐、选择可选背板或按真实 action 增加内部操作区；变体仍必须满足当前 Type 的安全边界、组件最小尺寸、禁止项和数据／action 一一对应规则。若改动已经改变顶层区域数量、主要尺寸公式、操作区位置或语义归属，则应重新选择 Type，而不是继续沿用原 Type 名称。

### 3.1 语义分组与槽位分配

1. 2×4 场景先按垂域和大主题分组。跨垂域内容只有存在明确共同任务时才能放进同一张卡片，并且仍要保持各组可独立识别。
2. 直接服务某组的 Action 应优先靠近该组；当严格归组会导致按钮过窄、文字裁剪或布局失衡时，可将 Action 放入相邻的半卡操作槽，但按钮文本必须能独立说明操作。
3. 同组的数据、局部标题和辅助信息原则上应保持在同一连续父区域内；Action 可按可读性和视觉均衡放入对应或相邻操作槽。唯一允许的内容拆分是：单一垂域中已经形成“核心结论 + 属性明细”两个可独立识别的完整信息模块时，可以使用 Type 13 将核心值与状态放在一侧、同主题的多项属性明细放在另一侧。不得把彼此依赖的单个字段或同一组件应共同表达的内容随意拆到左右两区。
4. 布局阶段不得为了适配 Type 改变数据含义、丢失必需信息或虚构 Action；允许在保持信息可识别的前提下调整 Action 的视觉位置。
5. 无全局标题时仍可在各父内容区内部使用局部标题。跨垂域分组缺少其他清晰主语时，各父区都应保留可见的业务标题。

| 冻结后的语义结构 | 优先布局 | 分配规则 |
|---|---|---|
| 单一语义组 | Type 12、Type 14 或 Type 10 | 所有组件共同回答同一问题；Type 10 的四格必须同类别、同维度 |
| 单一语义组，包含明确的核心结论与多项属性明细 | Type 13 变体 | 左区完整表达核心值与状态，右区使用 `TableText` 等组件完整表达同主题明细；两个父区均使用 `surface="backplate"`，不得把单个字段随意拆分成独立区域 |
| 单一语义组，只有 1 个 Action | Type 17、Type 13 变体；主要组件必须占满 296vp 时可用 Type 12 纵向流变体 | 使用 `PillButton`，限制在 136vp 半卡宽按钮槽内；不得生成整卡宽按钮。若主要组件不能放入 140／144vp 半区，不得为了迁就 Type 17／13 压缩组件或删减数据 |
| 单一语义组，恰好 2 个同级 Action | Type 13 双 `PillButton` 变体，或 Type 15／16 | 两个 Action 能分别放入左右信息父区时使用左右双 `PillButton`；数据集中在一侧、另一侧作为纯操作列时，必须使用上下竖排的 `CardButton` |
| 单一语义组，3–4 个 Action 均服务该组或整卡共同任务 | Type 9 | 使用两列、最多两行的 `CardButton` 操作网格；三个 Action 时不生成第四个空按钮 |
| 两个同级语义组，没有独立 Action | Type 13；纵向关系更自然时可用 Type 12 | Type 13 左右父区分别承载一组；Type 12 上下内容区分别承载一组 |
| 卡片恰好有 2 个同级 Action，且可分别归入左右信息父区 | Type 13 双 `PillButton` 变体 | 左右各一个 `PillButton`；透明父区中为 136 × 36vp，背板父区中为 120 × 36vp；不得把两个 `PillButton` 纵向堆入同一个纯操作父区 |
| 卡片恰好有 2 个 Action，且数据集中在一侧、操作集中在另一侧 | Type 15 或 Type 16 | 纯操作列使用两个上下竖排的 `CardButton`；内容在左用 Type 15，内容在右用 Type 16 |
| 跨垂域且不存在共同任务对象 | 不合并生成 | 保留主问题，其他组报告为未满足或另行生成，不得仅因 2×4 空间较大而拼卡 |

例如“晨跑准备”同时包含睡眠／运动健康与耳机／音乐时，可以因共同任务对象合并为一张卡。健康数据和设备数据仍分别进入 Type 13 的左右父区；若恰好有“进入锻炼”和“打开歌单”两个同级 Action，可使用左右双 `PillButton`。Action 应尽量靠近相关数据，但完整可读与布局均衡优先于机械的父区归属。

### 3.2 2×4 按钮限制

- 2×4 可以使用 `PillButton` 和 `CardButton`，禁止使用 `CircleButton`。
- 只有 1 个 Action 时使用 `PillButton`，不得用 `CardButton` 近似替代。
- 恰好 2 个同级 Action 且两个 Action 能分别进入左右信息父区时，使用左右双 `PillButton`；左右各一个 144vp 父区。透明父区中按钮为 136 × 36vp；使用 `surface="backplate"` 时按钮固定为 120 × 36vp，并水平居中。
- 背板内的 `PillButton` 默认脱离普通 flex 流并锚定在背板底部：背板父 `Stack` 使用 `position="relative"`，单按钮槽使用 `<Stack position="absolute" left={12} bottom={6} width={120} height={36}>`。`bottom={6}` 与 runtime 当前背板 `padding:6px` 一致；按钮不参与上方内容的剩余高度分配，但上方内容的可见边界与按钮顶部之间仍必须保留至少 8vp，不得延伸到按钮下方。
- 当数据内容集中在一侧、两个 Action 集中在另一侧纯操作列时，必须选择 Type 15／16，并使用上下竖排的两个 `CardButton`。不得在同一个纯操作父区中纵向堆叠两个 `PillButton`，也不得把两个 `CardButton` 仅做一行左右并排。Type 13 Option F 的双 `PillButton` 只适用于同一背板内同时存在紧凑内容且两个 Action 都直接服务该内容的特殊子布局，不得替代 Type 15／16 的纯操作列。三个或四个 Action 可使用 Type 9 的 2×2 操作网格。
- 单个 `PillButton` 或 `CardButton` 都不得横跨 296vp 安全内容区。左右双 `PillButton` 是两个独立的半卡按钮，不是一个整卡宽按钮。
- Type 17 的单 Action 槽使用 `PillButton`；主要组件需要完整 296vp 宽度时，Type 12 纵向流变体可在底部半卡宽槽使用单 `PillButton`；Type 13 可使用单 `PillButton`、左右双 `PillButton` 或竖排 `CardButton`；Type 15、Type 16 用于紧凑竖排的双 `CardButton`；Type 9 用于三个或四个 `CardButton` 的 2×2 操作网格。
- 同一个 action 只能生成一个按钮，不得用 `PillButton` 与 `CardButton` 重复表达。
- 没有 action 时不得为了填充布局而虚构按钮。

### 3.3 模块数与 Type

下表只统计 Type 自身的内容槽和操作槽，不统计可选的全局标题；存在全局标题时，在表中数量上加 1。

| 内容／操作模块数 | Type |
|---:|---|
| 2 | Type 12、Type 13、Type 17 |
| 3 | Type 12 纵向流变体、Type 9、Type 15、Type 16 |
| 4 | Type 9、Type 10、Type 14 |

统计口径：

- 全局标题是独立可选模块，不改变 Type 名称。
- 每个独立内容槽和操作槽各计 1 个。
- Type 13 父内容区内部复用的子布局、背板和内部按钮不重复计入整卡顶层模块数。
- 模块数只用于初选 Type，最终仍需检查信息层级、标题高度和业务组件最小占位。

## 4. 内容骨架

下表中 `T` 表示标题实际高度；统一使用可用内容高度 `A`：有全局标题时 `A = 136 − T − 4`，无全局标题时 `A = 136`。所有公式单位均为 vp。

| Type | 骨架 | 顶层模块弹性 | 尺寸与闭合公式 | 适用场景 / 特殊规则 |
|---|---|---|---|---|
| Type 9 | 可选标题 + 2×2 CardButton 操作网格 | 标题存在时 `flex0`；操作网格 `flex0` | `144 + 8 + 144 = 296`；两行槽高均为 `(A − 8) ÷ 2`，且必须在 48–64vp 内 | 用于同一语义组或整卡共同任务的三个或四个 Action；三个 Action 时按顺序占用前三个槽，不创建空按钮 |
| Type 12 | 可选标题 + 纵向流式分区 | 同级内容默认使用 `flex1`；有明确真实高度的组件使用固定槽，至多一个剩余区域使用 `flex1` | 两个同级内容默认满足 `(A − 8) ÷ 2`；内容驱动变体满足 `固定高度之和 + 间距之和 + 弹性剩余 = A` | 两个同级内容默认上下等分；主要整宽组件、紧凑标题信息行和单个底部 Action 可按真实高度形成 2–3 段变体，但所有顶层内容仍沿纵向排列并完整占用所属 296vp 区域 |
| Type 13 | 左右独立父内容区；透明变体可有全局标题，背板变体只用背板内局部标题 | 两父区均 `flex0` | `144 + 8 + 144 = 296`；透明且有全局标题时父区各 144 × A；使用背板时不保留背板外标题槽，父区各 144 × 136；无按钮内容区为 120 × 112，背板内 `PillButton` 例外锚定在 `left={12} bottom={6}` | 两个信息组分别占一个父区；父区是否使用 `surface="backplate"` 必须按 7.2.1 的确定顺序判断，不得把透明父区作为默认答案；背板内部按 7.2.2 选择子布局。可放置单个 `PillButton`，也可在恰好两个同级 Action 时左右各放一个 `PillButton` |
| Type 17 | 可选标题 + 左内容 + 右下 PillButton | 标题存在时 `flex0`；两模块均 `flex0` | `140 + 12 + 144 = 296`；左右父区高 A；按钮自身固定 136 × 36 | 用于一个内容组只有一个 Action，且按钮服务左侧内容或整卡共同任务；`PillButton` 在右侧半卡宽父区底部对齐 |
| Type 15 | 可选标题 + 左内容 + 右侧双 CardButton | 标题存在时 `flex0`；三模块均 `flex0` | 横向 `140 + 12 + 144 = 296`；右侧每个按钮槽高 `(A − 8) ÷ 2` | 数据集中在左侧、两个 Action 集中在右侧纯操作列时使用；两个按钮服务左侧内容或整卡共同任务。不同信息父区各自拥有 Action 时改用 Type 13 左右双 `PillButton` |
| Type 16 | 可选标题 + 左侧双 CardButton + 右内容 | 标题存在时 `flex0`；三模块均 `flex0` | 横向 `144 + 12 + 140 = 296`；左侧每个按钮槽高 `(A − 8) ÷ 2` | Type 15 的左右镜像；数据集中在右侧、两个 Action 集中在左侧纯操作列时使用 |
| Type 14 | 可选标题 + 2×2 四宫格 | 标题存在时 `flex0`；四模块均 `flex0` | 横向 `144 + 8 + 144 = 296`；纵向每格高 `(A − 8) ÷ 2` | 四个内容区无标题时各 144 × 64；槽位自身不增加 Panel 外观，内容不得跨格 |
| Type 10 | 可选标题 + 同类信息 2×2 四宫格 | 标题存在时 `flex0`；四模块均 `flex0` | 每格 144 × 52；`144 + 8 + 144 = 296`，`52 + 8 + 52 = 112` | 四格必须表达同类别、同维度信息；槽位自身不增加 Panel 外观；存在标题时 `T > 20` 不兼容 |

## 5. 操作区

| Type | 按钮选择 | 槽位尺寸 | 排列方式 |
|---|---:|---|---|
| Type 12 纵向流变体 | 1 个 `PillButton` | 136 × 36vp，位于296vp宽底部区域内的半卡宽按钮槽 | 按钮槽在底部区域左对齐或右对齐；横向父 `Stack` 中使用 `flex={0} width={136} height={36}`，不得用 `basis={36}` 压缩宽度 |
| Type 13 | 1 个 Action 用单 `PillButton`；恰好 2 个同级 Action 优先用双 `PillButton` | 每个 `PillButton` 分别位于一个半卡父区内；透明标题变体父区为 144 × A，背板变体父区为 144 × 136；透明父区按钮为 136 × 36，背板父区按钮为 120 × 36 | 单按钮按子布局定位；双按钮左右各一个，不拉伸；背板父区使用 `position="relative"`，按钮槽固定为 `position="absolute" left={12} bottom={6}`，水平居中且不参与上方内容的 flex 分配 |
| Type 9 | 3–4 个 `CardButton` | 每个 144 × `(A − 8) ÷ 2`，高度必须在 48–64vp 内 | 两列、最多两行；三个 Action 时第四格不存在 |
| Type 15 | 2 个 `CardButton` | 每个 144 × `(A − 8) ÷ 2` | 右侧上下排列，间距 8 |
| Type 16 | 2 个 `CardButton` | 每个 144 × `(A − 8) ÷ 2` | 左侧上下排列，间距 8 |
| Type 17 | 1 个 `PillButton` | 按钮 136 × 36，位于 144vp 宽父区内 | 右下对齐 |

`PillButton` 默认使用 136 × 36vp；Type 13 背板内由 runtime 自动使用 120 × 36vp，并水平居中。尺寸变化由 `surface="backplate"` 的上下文样式完成，生成 JSX 不向按钮传尺寸 Prop；定位由外层 `Stack` 的公开 Props 表达。背板内单按钮槽固定使用 `position="absolute" left={12} bottom={6}`，不作为普通纵向 flex 子项。`CardButton` 由半卡宽竖排操作列或 Type 9 网格分配 48–64vp 高的子槽，并使用 `width:100%`、`height:100%` 填满该子槽。生成 JSX 不传入不存在的 `width`、`height`、`radius` 或 `position` Props。

当卡片包含两个信息组时，Action 应尽量靠近相关数据，但可读性、完整显示和视觉均衡的优先级更高。恰好两个同级 Action 且能分别进入左右信息父区时，可将两个 `PillButton` 分别放入左右半卡父区；按钮文本必须能独立表达操作，避免产生错误的业务归属。若两个 Action 最终集中在同一个不承载业务内容的半卡父区，该父区就是纯操作列，必须改用 Type 15／16 的两个纵向 `CardButton`。

## 6. 尺寸与实现规则

- 有全局标题时标题区使用自然高度，下方区域从标题实际底部 + 4vp 开始；Type 13 背板变体除外，该变体只使用背板内部局部标题。
- 无全局标题时直接使用完整的 296 × 136vp 安全内容区，不生成空标题槽。
- 基础等宽双列满足 `144 + 8 + 144 = 296`；144vp 子列满足 `68 + 8 + 68 = 144`。
- Type 15–17 使用非对称双列：`140 + 12 + 144 = 296` 或其镜像。
- `flex0` 表示模块不参与剩余空间分配；`flex1` 必须继续标明高度、宽度或宽高均自适应。
- 弹性纵向内容区使用 `flex={1} minHeight={0}`；固定区域使用明确的 `basis`、`width` 或 `height`。
- Type 9、Type 15、Type 16 的 `CardButton` 行高随 `A` 变化，必须位于 48–64vp 范围内，且槽位宽度不得小于高度。若标题增高导致按钮槽无法容纳 `CardButton`，应更换 Type、减少非核心内容或停止并报告。
- Type 10 的四个 144 × 52vp 模块固定不伸缩；标题实际高度超过 20vp 时必须更换 Type。
- Type 12 只有在两个同级内容都没有明确固定高度时才默认等分剩余高度。主要组件已有 runtime 高度、标题与 `Summary` 共享紧凑行，或底部存在单个 `PillButton` 时，可以按内容真实高度分配固定槽，并让一个剩余区域使用 `flex={1} minHeight={0}`；不得同时创建多个没有闭合依据的弹性区域。
- Type 13 的左右父区通常分别承载一个完整语义组，不得在同一父区混排两组信息。单一垂域的“核心结论 + 属性明细”变体中，左右父区分别承载一个可独立识别的完整信息模块：一侧为核心值与状态，另一侧为同主题属性明细。透明变体存在全局标题时父区高度为 A；只要使用背板，就取消背板外全局标题槽，父区使用完整 136vp 高度。无按钮时在 120 × 112vp 内组织局部标题和内容；存在背板内 `PillButton` 时按 `left={12} bottom={6}` 锚定按钮，并让上方内容在按钮顶部上方至少 8vp 结束。所有可见内容必须留在各自父区内，不得跨区、重叠或占用中间 8vp 间距；不能机械复制 2×2 的 136 × 136vp 固定骨架。
- Type 17 只生成一个右下 `PillButton`，不得保留第二个空按钮组件、占位模块或虚构 action。
- 整宽组件必须占满所属模块：整宽区为 296vp，普通等宽列为 144vp，非对称内容列为 140vp。包裹层使用 `width="full" minWidth={0}`。
- 标题增高或文本换行导致槽位小于业务组件最小尺寸时，应更换 Type、减少内容或停止并报告，不得依赖裁剪或溢出。
- 产品规格使用 vp；HTML 骨架预览可使用同数值 px 做 1:1 校核。

## 7. 标准 JSX 布局模板
共同规则：

- 根节点固定为 `<Card size="2x4" appearance="...">`；默认 `padding={12}` 得到 296 × 136vp 安全内容区。
- 模板禁止 `style`、`className`、spread Props 和硬编码颜色。
- 2×4 单 Action 使用 `PillButton`；两个 Action 分别进入左右信息父区时使用左右双 `PillButton`，集中在同一个纯操作列时必须使用 Type 15／16 的上下双 `CardButton`；三个或四个 Action 可使用 Type 9 的 2×2 `CardButton` 网格。每个按钮都必须限制在自己的半卡宽父区或半卡宽子槽内。
- 示例中的 `dataIds` 与 `actionId` 只说明绑定位置；实际生成必须替换为输入中真实存在的 ID。

以下各 Type 示例即使展示为无标题版本，也不表示该 Type 禁止标题。数据类或日程类信息存在明确主题时，通常在 `Card` 顶部增加自然高度标题区，并把原 Type 骨架放入剩余高度为 A 的主区域。Type 13 背板变体不使用这一通用写法：标题必须放入对应背板内部。对于原本使用 `direction="row"` 的 Type，`direction="row"` 应移动到主区域 `Stack`，不能继续写在 `Card` 上；主区域 `gap` 仍使用该 Type 规定的 8vp 或 12vp：

```jsx
<Card size="2x4" appearance="blue-soft">
  <Stack flex={0}>
    <SingleLineTitle title="今日日程" />
  </Stack>

  <Stack flex={1} minHeight={0} mt={4} width="full" direction="row" gap={8}>
    {/* 当前 Type 的内容／操作骨架 */}
  </Stack>
</Card>
```

加入标题后必须按 A 重新计算内容区、网格行和按钮槽高度；不能在原 136vp 骨架上方直接叠加标题。

### 7.1 Type 12：可选标题 + 纵向流式分区

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

上面的上下等分是两个同级内容都没有固定高度时的默认结构，不是 Type 12 的唯一合法高度关系。Type 12 的稳定特征是：顶层区域沿纵向排列，每个主要内容区占满所属的 296vp 宽度；区域高度可以由内容真实高度决定。标题与单行 `Summary` 可以共享顶部紧凑行，整宽组件按其 runtime 高度分配固定槽，单个 `PillButton` 使用 136 × 36vp 槽并在剩余底部区域左对齐或右对齐。无论采用默认等分还是内容驱动变体，都必须闭合 136vp，且不得通过压缩字号、裁剪内容或删除数据适配布局。

横向 `Stack` 内的按钮包装层不得使用 `basis={36}` 表示按钮高度，因为 `basis` 会占用横向主轴宽度并把 136vp 按钮压进 36vp 槽。应使用 `flex={0} width={136} height={36}` 固定按钮槽。

```jsx
<Card size="2x4" appearance="blue-soft">
  <Stack basis={20} height={20} width="full" direction="row" gap={8} align="center">
    <Stack basis={96} width={96} height={20}>
      <SingleLineTitle title="内容概览" />
    </Stack>
    <Stack flex={1} minWidth={0} height={20} align="flex-end" justify="center">
      <Summary content="辅助信息" />
    </Stack>
  </Stack>
  <Stack basis={64} width="full" mt={4}>
    <TextBlock
      items={[
        { label: "属性一", parameter: "内容一" },
        { label: "属性二", parameter: "内容二" },
        { label: "属性三", parameter: "内容三" },
      ]}
    />
  </Stack>
  <Stack flex={1} minHeight={0} width="full" direction="row" align="flex-end" justify="end">
    <Stack flex={0} width={136} height={36}>
      <PillButton label="查看详情" appearance="card" actionId="action.example" />
    </Stack>
  </Stack>
</Card>
```

此例的顶部标题与 `Summary` 共用 20vp；父 `Stack` 使用 `basis={64}`，因此 `TextBlock` 保持默认 64vp 高度；底部区域吸收剩余高度，并把 136 × 36vp 的 `PillButton` 贴在右下。只有内容预算不足时才把父槽改为 `basis={48}`，此时 `TextBlock` 自动收缩为 48vp；不得分配小于 48vp 的槽位。三项整宽数据仍共同占满 296vp，不因按钮存在而拆进半卡区域。

### 7.2 Type 13：可选标题 + 左右独立父内容区

```jsx
<Card size="2x4" appearance="neutral-soft" direction="row" gap={8}>
  <Stack surface="backplate" basis={144} width={144} height={136} gap={8} align="center">
    <Stack direction="row" basis={18} width={120} height={18} gap={8} align="center">
      <Stack flex={1} minWidth={0}>
        <SingleLineTitle title="27日 星期一" />
      </Stack>
      <Badge value={1} />
    </Stack>
    <Stack flex={1} width={120} minHeight={0} align="flex-start">
      <EventCard title="项目例会" time="10:00-14:00" location="练秋湖A1-3-41R" />
    </Stack>
  </Stack>

  <Stack surface="backplate" basis={144} width={144} height={136} position="relative">
    <Stack position="absolute" top={12} left={12} width={120} height={74} gap={8}>
      <Stack basis={18} width={120} height={18}>
        <SingleLineTitle title="健康数据" />
      </Stack>
      <Stack flex={1} width={120} minHeight={0} justify="center">
        <TableText items={[{ label: "今日步数", parameter: "6200步" }, { label: "昨晚睡眠", parameter: "82分" }]} />
      </Stack>
    </Stack>
    <Stack position="absolute" left={12} bottom={6} width={120} height={36}>
      <PillButton label="进入锻炼" icon="resources/base/media/figure_run.svg" appearance="card" actionId="event.open.health.sport" />
    </Stack>
  </Stack>
</Card>
```

Type 13 固定的是两个 144vp 宽父区和中间 8vp 间距。透明变体可以使用 Card 顶部全局标题，此时父区高 A；只要任一父区使用背板，就不再保留背板外标题槽，父区使用完整 136vp 高度，已有标题改为对应背板内的局部标题。左右父区不要求采用完全相同的内部结构，但各组数据或同一垂域下的两个完整信息模块应保持可独立识别。背板用于表达一个完整语义组或完整信息模块的共享边界，不能仅因版面空旷而作为装饰添加；透明变体也不是默认答案，只有满足 7.2.1 的完整自带容器条件时才能使用。没有按钮时，背板父区使用 120 × 112vp 内部安全区；存在 `PillButton` 时，按钮改为距背板左侧 12vp、底部 6vp 的绝对定位，按钮上方内容独立分配且必须在按钮顶部上方至少 8vp 结束。可用子布局见 7.2.2。只有一个 Action 时使用单 `PillButton`；恰好两个同级 Action 时优先左右各放一个 `PillButton`。Action 应尽量靠近相关数据，但不需为此把两个按钮挤入同一狭窄父区；没有 action 时同时删除按钮及其定位槽。

#### 7.2.1 Type 13 背板选择规则

`surface="backplate"` 只写在 Type 13 左右主区域中直接承载语义组的 144 × 136 父 `Stack` 上，不写在局部标题、数据或按钮的内层包装 `Stack` 上。背板选择不使用“看起来是否需要”的主观判断，必须依次执行以下规则，命中后停止：

1. 如果左右父区都完全由 `InfoBlock`、`CardButton` 等自带完整可见容器的组件组成，且父区内没有局部标题、`Summary`、`EmphasizedData`、`EventCard`、`TableText` 等裸内容，则左右父区都保持透明。
2. 如果只有一侧满足上述完整自带容器条件，另一侧由局部标题和一个或多个裸业务组件共同组成，则自带容器的一侧保持透明，组合内容的一侧必须使用 `surface="backplate"`。
3. 其余包含两个独立语义组，或采用单一垂域“核心结论 + 属性明细”变体的 Type 13，一律左右都使用 `surface="backplate"`。尤其当任一父区出现“局部标题 + 两个或以上裸业务组件”时，不得选择双透明变体。

这里的“裸业务组件”指自身不提供完整父区域背景和圆角边界、需要与同组其他内容共同组织的组件，包括 `Summary`、`EmphasizedData`、`EventCard`、`TableText`、`NumericRatioStack`、`ProgressLine2` 等。`PillButton` 虽然自身有按钮背景，但只表示 Action，不能据此把整个父区判定为自带完整容器。

标题归属是背板结构的硬约束：只要卡片中存在 `surface="backplate"`，所有 `SingleLineTitle`／`DoubleLineTitle` 都必须位于某个背板的子树中，通常作为该背板的第一个语义元素。不得生成“Card 顶部标题 + 下方一个或两个背板”的结构。如果原全局标题同时概括左右两组，应把它拆成来自真实语义的局部标题分别放入对应背板；无法形成真实局部标题时，只有左右父区同时满足第 1 条完整自带容器条件才能改用透明 Type 13，否则改选其他不需要局部标题的布局，不得虚构标题。

| 父区关系 | 背板选择 | 判断条件 | 典型场景 |
|---|---|---|---|
| 两个同级独立语义组 | 左右父区都使用 `surface="backplate"` | 两侧都未完全由自带可见容器的组件组成；局部标题与裸业务组件需要共同形成清晰的组边界 | 日程与天气；日程与健康数据；今日步数与本次训练 |
| 单一垂域的核心结论与属性明细 | 左右父区都使用 `surface="backplate"` | 左侧完整表达核心值与状态，右侧完整表达同主题的多项属性；两个模块均可独立识别，且不是为了凑双列而拆分单个字段 | 睡眠得分与状态 + 深睡、小睡、总时长明细 |
| 仅一侧完全由自带可见容器的组件组成 | 该侧透明，另一侧使用 `surface="backplate"` | 透明侧仅由 `InfoBlock`、`CardButton` 等完整可见块组成；另一侧需要把局部标题与 `EventCard`、`NumericRatioStack`、`TableText` 等组合为一个整体 | 运动与耳机数据；天气、电池与会面安排 |
| 两侧都完全由自带可见容器的组件组成 | 两侧父区都保持透明 | 两侧父区都只由 `InfoBlock`、`CardButton` 等完整可见块组成，且没有额外的局部标题或裸业务组件 | 左侧两个 `InfoBlock`，右侧两个 `CardButton` |

同级的两个裸内容组必须同时使用背板，避免无理由的一侧有背板、一侧透明。单侧背板只由“恰好一侧完全由自带可见容器组件组成”这一结构条件触发，不得因为主次关系、背景颜色或版面看起来已经分栏而自行省略另一侧背板。若父区中同时存在局部标题、数据和 Action，这些元素共同回答同一问题时，应放在同一个父背板内；不要仅因内部出现按钮就取消背板。

例如，左侧为 `SingleLineTitle + EventCard + Summary`，右侧为 `SingleLineTitle + Summary + EmphasizedData + Summary` 时，两侧都包含局部标题和多个裸业务组件，必须生成双背板；不得因为 `EventCard` 自身有时间线结构，或 Card 已使用渐变背景，就把任一父区判定为完整自带容器。

本节开头的“日程与健康数据”示例是双侧背板的标准结构。右侧父区同时包含局部标题、健康数据和 Action，因此这些元素由同一个背板组织；背板父区使用 `position="relative"`，按钮槽固定为 `position="absolute" left={12} bottom={6}`。`PillButton` 由 runtime 自动切换为 120 × 36vp，并在背板内水平居中，不得继续写成 `width={136}`。

单侧背板结构示例：左侧 `InfoBlock` 已分别形成完整可见块，右侧用父背板把局部标题和日程组合为一个语义组。

```jsx
<Card size="2x4" appearance="cloudy-gradient" direction="row" gap={8}>
  <Stack basis={144} width={144} height={136} gap={8}>
    <Stack basis={64} height={64}>
      <InfoBlock primaryText="31°" secondaryText="多云｜空气良" visual={{ type: "icon", icon: "icon_weather1.svg", color: "native" }} />
    </Stack>
    <Stack basis={64} height={64}>
      <InfoBlock primaryText={73} unit="%" secondaryText="手机电量" visual={{ type: "progressCircle", icon: "icon_charge.svg" }} />
    </Stack>
  </Stack>

  <Stack surface="backplate" basis={144} width={144} height={136} align="center" justify="center">
    <Stack width={120} height={112} gap={8}>
      <Stack basis={20} height={20}>
        <SingleLineTitle title="会面安排" />
      </Stack>
      <Stack flex={1} minHeight={0} align="flex-start">
        <EventCard title="客户现场沟通" time="10:30-12:30" location="客户创新中心" />
      </Stack>
    </Stack>
  </Stack>
</Card>
```

无需父背板时，左右内容已经分别由 `InfoBlock` 和 `CardButton` 提供组件级可见容器，父 `Stack` 保持透明，不再形成双重背板。

恰好两个同级 Action 时，可在 Type 13 的左右父区底部各放一个 `PillButton`：

```jsx
<Card size="2x4" appearance="purple-gradient" direction="row" gap={8}>
  <Stack surface="backplate" basis={144} width={144} height="full" minWidth={0} position="relative">
    <Stack position="absolute" top={12} left={12} width={120} height={74} minHeight={0}>
      {/* 左侧信息 */}
    </Stack>
    <Stack position="absolute" left={12} bottom={6} width={120} height={36}>
      <PillButton label="操作一" appearance="card" actionId="action.first" />
    </Stack>
  </Stack>

  <Stack surface="backplate" basis={144} width={144} height="full" minWidth={0} position="relative">
    <Stack position="absolute" top={12} left={12} width={120} height={74} minHeight={0}>
      {/* 右侧信息 */}
    </Stack>
    <Stack position="absolute" left={12} bottom={6} width={120} height={36}>
      <PillButton label="操作二" appearance="card" actionId="action.second" />
    </Stack>
  </Stack>
</Card>
```

#### 7.2.2 Type 13 背板内子布局 Options

Type 13 左右两个背板父区可分别、独立选择下列 Option。Option 只复用 2×2 规范中的模块关系，不是新的 2×4 顶层 Type，也不沿用 2×2 的 136 × 136vp 内容尺寸。左右两侧可以选择不同 Option，但每侧必须在自己的背板与安全内容区内完成布局。

##### 通用约束

- 每个背板父区固定为 `<Stack surface="backplate" basis={144} width={144} height={136}>`，圆角和裁剪由 runtime 提供，当前为 `border-radius:16px` 与 `overflow:hidden`。父区属于固定模块，不参与整卡剩余空间分配。
- 没有 `PillButton` 时，每个背板内必须建立一个水平、垂直居中的 `120 × 112vp` 内层 `Stack`，从而形成四边各 12vp 的有效安全边距。runtime 背板 CSS 自身不是 12vp padding，不得省略该内层容器后假定安全边距仍然成立。
- 存在 `PillButton` 时，背板父区必须增加 `position="relative"`。单按钮槽固定使用 `<Stack position="absolute" left={12} bottom={6} width={120} height={36}>`；按钮底部与背板底部的 6vp 距离等于 runtime 当前背板 padding。按钮不参与上方内容的 flex 高度计算，上方内容必须通过明确的 `top`、`left`、`width`、`height` 停止在按钮顶部上方至少 8vp，不得延伸到按钮后方。
- 无按钮时推荐公共外壳如下；`{/* Option 内容 */}` 只能使用本节定义的 120 × 112vp 骨架：

```jsx
<Stack surface="backplate" basis={144} width={144} height={136} align="center" justify="center">
  <Stack basis={112} width={120} height={112} minWidth={0}>
    {/* Option 内容 */}
  </Stack>
</Stack>
```

- 内层相邻主要模块的默认间距为 8vp。绝对定位的按钮不计入上方内容的 flex 分配，但内容与按钮可见边界仍必须保留 8vp。除相应 Option 明确允许缺省的模块外，不删除模块，也不保留空白占位。
- 标题槽宽 120vp，使用 `<Stack flex={0} width={120}>`，高度由标题组件自然撑开。以下公式中的 `T` 为标题组件实际高度；`SingleLineTitle` 带 20vp Icon 时参考 `T = 20vp`。
- 标记为固定的模块使用 `flex={0}` 或明确的 `basis`／`height`；参与剩余高度分配的内容模块使用 `flex={1} minHeight={0}`。`flex0`、`flex1` 只是尺寸关系说明，不是可以直接生成的 JSX Prop 名。
- 背板已由 runtime 继承 16px 圆角并裁剪内部背景；不得在子布局内使用原生元素、`style`、`className` 或硬编码背景模拟第二层 Panel，也不得产生越过圆角的直角背景。
- 左右 Option 相互独立，内部模块不得跨区排布、共享尺寸或共享对齐基准；子布局内部模块不重复计入 Type 13 的整卡顶层模块数。
- 公式所得空间若小于所选业务组件的真实最小宽高，则该 Option 与组件不兼容。必须更换组件组合、Option 或顶层布局；不得侵入 12vp 安全边距、压缩 8vp 规定间距、缩小按钮高度或依赖裁剪隐藏内容。

##### Option A：无标题单内容区

- 骨架：无标题 + 单内容区。
- 内容区固定为 120 × 112vp，使用 `flex={0}`，内容在区域内水平、垂直居中。

```jsx
<Stack basis={112} width={120} height={112} align="center" justify="center">
  {/* 单个核心内容模块 */}
</Stack>
```

##### Option B：标题 + 单内容区

- 标题区必选，宽 120vp，自然高度为 `T`。
- 内容区宽 120vp，使用 `flex={1} minHeight={0}`；标题与内容间距为 8vp。
- 内容区高度为 `112 − T − 8 = 104 − T`；当 `T = 20vp` 时，参考尺寸为 120 × 84vp。

```jsx
<Stack basis={112} width={120} height={112} gap={8}>
  <Stack flex={0} width={120}>{/* 局部标题 */}</Stack>
  <Stack flex={1} width={120} minHeight={0}>{/* 单个内容模块 */}</Stack>
</Stack>
```

##### Option C：标题 + 核心内容 + 明细内容

- 标题区必选，宽 120vp，自然高度为 `T`。
- 核心内容区和明细内容区均宽 120vp，均使用 `flex={1} minHeight={0}`，默认等分标题及两处 8vp 间距之外的剩余高度。
- 单个内容区高度为 `(112 − T − 8 − 8) ÷ 2 = (96 − T) ÷ 2`；当 `T = 20vp` 时，两区参考尺寸均为 120 × 38vp。

```jsx
<Stack basis={112} width={120} height={112} gap={8}>
  <Stack flex={0} width={120}>{/* 局部标题 */}</Stack>
  <Stack flex={1} width={120} minHeight={0}>{/* 核心内容 */}</Stack>
  <Stack flex={1} width={120} minHeight={0}>{/* 明细内容 */}</Stack>
</Stack>
```

##### Option D：标题 + 内容 + 可选 PillButton

- 标题区必选，宽 120vp，自然高度为 `T`；内容区宽 120vp，使用 `flex={1} minHeight={0}`。
- 显示按钮时，`PillButton` 固定为 120 × 36vp；圆角沿用 runtime 当前固定的 30px。按钮固定在 `left={12} bottom={6}`，上方标题与内容使用 `top={12} left={12} width={120} height={74}` 的独立区域。标题与内容间距为 8vp，内容区高度为 `74 − T − 8 = 66 − T`；当 `T = 20vp` 时，参考尺寸为 120 × 46vp。上方区域结束后到按钮顶部还保留 8vp。
- 按钮缺省时，同时删除按钮槽及其相邻的 8vp 间距。内容区高度为 `112 − T − 8 = 104 − T`；当 `T = 20vp` 时，参考尺寸为 120 × 84vp。
- 按钮槽必须写成 `position="absolute" left={12} bottom={6} width={120} height={36}`；背板上下文会使 `PillButton` 使用 runtime 的 120 × 36vp 规格，生成 JSX 不传尺寸或圆角 Prop。

```jsx
<Stack surface="backplate" basis={144} width={144} height={136} position="relative">
  <Stack position="absolute" top={12} left={12} width={120} height={74} gap={8}>
    <Stack flex={0} width={120}>{/* 局部标题 */}</Stack>
    <Stack flex={1} width={120} minHeight={0}>{/* 内容 */}</Stack>
  </Stack>
  <Stack position="absolute" left={12} bottom={6} width={120} height={36}>
    <PillButton label="操作" appearance="card" actionId="action.example" />
  </Stack>
</Stack>
```

##### Option E：双列内容 + 可选 PillButton

- 无标题。显示按钮时，上方 A、B 内容区均固定为 56 × 74vp，两列水平间距为 8vp。
- `PillButton` 固定为 120 × 36vp，圆角沿用 runtime 当前固定的 30px；双列内容区与按钮间距为 8vp。
- 横向满足 `56 + 8 + 56 = 120vp`；纵向满足 `12 + 74 + 8 + 36 + 6 = 136vp`。按钮固定在 `left={12} bottom={6}`，不参与双列内容区的 flex 分配。
- 按钮缺省时，同时删除按钮槽及其相邻的 8vp 间距，A、B 内容区均扩展为 56 × 112vp。

```jsx
<Stack surface="backplate" basis={144} width={144} height={136} position="relative">
  <Stack position="absolute" top={12} left={12} direction="row" width={120} height={74} gap={8}>
    <Stack basis={56} width={56} height={74}>{/* A */}</Stack>
    <Stack basis={56} width={56} height={74}>{/* B */}</Stack>
  </Stack>
  <Stack position="absolute" left={12} bottom={6} width={120} height={36}>
    <PillButton label="操作" appearance="card" actionId="action.example" />
  </Stack>
</Stack>
```

##### Option F：紧凑内容 + 两个纵向 PillButton

- 无标题。内容区固定为 120 × 30vp，仅适合单行文字、状态值或简单图标；内部组件最小高度超过 30vp 时不得使用该 Option。
- 两个 `PillButton` 均固定为 120 × 36vp，圆角沿用 runtime 当前固定的 30px。内容区与第一个按钮、两个按钮之间均使用 8vp 间距。
- 两按钮组成 120 × 80vp 的操作组并整体锚定在 `left={12} bottom={6}`；内容区固定在 `top={12} left={12}`。纵向满足 `12 + 30 + 8 + 36 + 8 + 36 + 6 = 136vp`。

```jsx
<Stack surface="backplate" basis={144} width={144} height={136} position="relative">
  <Stack position="absolute" top={12} left={12} width={120} height={30}>{/* 单行紧凑内容 */}</Stack>
  <Stack position="absolute" left={12} bottom={6} width={120} height={80} gap={8}>
    <Stack basis={36} width="full" height={36}>
      <PillButton label="操作一" appearance="card" actionId="action.first" />
    </Stack>
    <Stack basis={36} width="full" height={36}>
      <PillButton label="操作二" appearance="card" actionId="action.second" />
    </Stack>
  </Stack>
</Stack>
```

### 7.3 Type 17：必须标题 + 左内容 + 右下 PillButton

```jsx
<Card size="2x4" appearance="blue-soft" direction="row" gap={12}>
  <Stack basis={140} width={140} height="full" minWidth={0}>
    {/* 左内容区 */}
  </Stack>

  <Stack basis={144} width={144} height="full" justify="end">
    <Stack basis={36} width={136} height={36} align="center" justify="center">
      <PillButton
        label="立即处理"
        icon="clean_fill.svg"
        appearance="card"
        actionId="action.handle"
      />
    </Stack>
  </Stack>
</Card>
```

右侧上方留白只是剩余空间，不生成空按钮或虚构 action。该操作区域只有一个 Action，因此必须使用 `PillButton`。

### 7.4 Type 9：可选标题 + 2×2 CardButton 操作网格

```jsx
<Card size="2x4" appearance="orange-gradient">
  <Grid columns={2} rows="64px 64px" gap={8} width="full" height="full">
    <CardButton text="操作一" actionId="action.first" />
    <CardButton text="操作二" actionId="action.second" />
    <CardButton text="操作三" actionId="action.third" />
    <CardButton text="操作四" actionId="action.fourth" />
  </Grid>
</Card>
```

无标题时每格为 144 × 64vp。存在全局标题时必须根据实际 `A` 重新计算两行高度，并保证每行处于 48–64vp；无法满足时省略非必要标题、改用其他 Type 或停止并报告。只有三个 Action 时删除第四个 `CardButton`，不生成空按钮、占位组件或虚构 action。

### 7.5 Type 15：可选标题 + 左内容 + 右侧双 CardButton

```jsx
<Card size="2x4" appearance="cloudy-gradient" direction="row" gap={12}>
  <Stack basis={140} width={140} height="full" minWidth={0} gap={8}>
    <Stack basis={64} width="full" height={64}>
      <InfoBlock
        primaryText="7小时1分"
        secondaryText="良好"
        visual={{
          type: "icon",
          icon: "resources/base/media/moon_z_fill_1.svg",
        }}
        dataIds={{
          primaryText: "healthSport.nightSleepDurationText",
          secondaryText: "healthSport.sleepStatus",
        }}
      />
    </Stack>

    <Stack basis={64} width="full" height={64}>
      <InfoBlock
        primaryText={31}
        unit="°"
        secondaryText="多云"
        visual={{
          type: "icon",
          icon: "resources/base/media/icon_weather1.svg",
          color: "native",
        }}
        dataIds={{
          primaryText: "weather.current.feelsLikeC",
          secondaryText: "weather.current.condition",
        }}
      />
    </Stack>
  </Stack>

  <Stack basis={144} width={144} height="full" gap={8}>
    <Stack basis={64} width="full" height={64}>
      <CardButton
        text="进入锻炼"
        icon="resources/base/media/figure_run.svg"
        actionId="event.open.health.sport"
      />
    </Stack>

    <Stack basis={64} width="full" height={64}>
      <CardButton
        text="睡眠详情"
        icon="resources/base/media/moon_z_fill_1.svg"
        actionId="event.open.health.sleep"
      />
    </Stack>
  </Stack>
</Card>
```

本例中两个 `InfoBlock` 已占据左侧内容区，右侧不再承载业务数据而成为纯操作列，因此必须使用 Type 15 的两个纵向 `CardButton`。不得把右侧两个按钮改成纵向 `PillButton`。`event.open.health.sport` 的可见文本必须表达“进入锻炼”等真实操作语义，不得因为卡片同时展示天气而错误写成“看天气”。

### 7.6 Type 16：可选标题 + 左侧双 CardButton + 右内容

```jsx
<Card size="2x4" appearance="orange-gradient" direction="row" gap={12}>
  <Stack basis={144} width={144} height="full" gap={8}>
    <Stack basis={64} width="full" height={64}>
      <CardButton text="操作一" actionId="action.first" />
    </Stack>

    <Stack basis={64} width="full" height={64}>
      <CardButton text="操作二" actionId="action.second" />
    </Stack>
  </Stack>

  <Stack basis={140} width={140} height="full" minWidth={0}>
    {/* 右内容区 */}
  </Stack>
</Card>
```

### 7.7 Type 14：可选标题 + 四宫格

```jsx
<Card size="2x4" appearance="blue-soft">
  <Grid columns={2} rows="64px 64px" gap={8} width="full" height="full">
    <Stack>{/* A：144 × 64 */}</Stack>
    <Stack>{/* B：144 × 64 */}</Stack>
    <Stack>{/* C：144 × 64 */}</Stack>
    <Stack>{/* D：144 × 64 */}</Stack>
  </Grid>
</Card>
```

### 7.8 Type 10：可选标题 + 同类信息四宫格

```jsx
<Card size="2x4" appearance="orange-gradient">
  <Stack flex={0}>
    <SingleLineTitle title="同类信息" />
  </Stack>

  <Grid columns={2} rows="52px 52px" gap={8} width="full" mt={4}>
    <Stack>{/* A：144 × 52 */}</Stack>
    <Stack>{/* B：144 × 52 */}</Stack>
    <Stack>{/* C：144 × 52 */}</Stack>
    <Stack>{/* D：144 × 52 */}</Stack>
  </Grid>
</Card>
```

## 8. 常见错误

- 不要继续生成已经删除的 Type 2、Type 3、Type 4、Type 5、Type 6、Type 11。
- 不要在 2×4 中使用 `CircleButton`。只有一个 Action 时使用单 `PillButton`；两个 Action 分别进入左右信息父区时使用左右双 `PillButton`；两个 Action 集中在同一个纯操作列时必须使用 Type 15／16 的上下双 `CardButton`。
- 不要把标题高度固定为 20vp，也不要照抄 HTML 参考图中的 `top={24}`。
- 不要根据 Type 编号禁止全局标题。数据类或日程类信息存在明确主题时，Type 12–17 通常允许生成全局标题；标题必须来自真实意图／数据，并按 A 缩减其余区域。唯一例外是 Type 13 背板变体：标题必须进入对应背板，不能留在 Card 顶部。没有全局标题时，多组布局仍可在各内容父区内部使用属于本组的局部标题。
- 不要使用 Type 8 的上 1 下 2 按钮结构。Type 9 是允许的 2×2 `CardButton` 操作网格，只用于三个或四个真实 Action。
- Type 15、Type 16 的一个按钮槽只能放一个 `CardButton`。
- 不要在 Type 15／16 的纯操作列中纵向堆叠两个 `PillButton`。Type 13 Option F 的双 `PillButton` 仅限同一背板中同时存在紧凑业务内容、且两个 Action 都直接服务该内容的场景。
- 不要把 `CardButton` 放入宽度小于高度的槽位；存在标题时必须根据实际 A 检查按钮槽。
- 不要让 `PillButton` 或 `CardButton` 横跨 296vp 安全内容区；任何按钮都必须限制在左或右半卡宽父区内。
- 同一语义组／操作区域有且只有一个 Action 时，不要生成 `CardButton` 或整卡宽操作槽；通常使用 Type 17 或 Type 13 变体中的 `PillButton`。主要业务组件必须占满 296vp 时，可使用 Type 12 纵向流变体，将 `PillButton` 限制在底部136vp半卡宽槽内。
- 不要把不同垂域的数据混放在同一内容父区。Action 应尽量靠近相关数据，但可为了完整显示和视觉均衡放入相邻半卡操作槽；此时按钮文本必须能独立说明操作。
- Type 13 不得把左右父区误当成一个跨区画布。透明标题变体不得跨越 144 × A 父区边界；背板变体使用 144 × 136vp 父区，无按钮时使用 120 × 112vp 内部安全区，存在 `PillButton` 时使用底部 6vp 锚定规则。背板仍按 7.2.1 的共享语义组规则选择，不得无条件省略，也不得仅作装饰。存在局部标题或内部按钮时可以重新分配父区内部空间，但不得跨越父区边界或中间 8vp 间距。
- Type 15、Type 16 使用 12vp 左右间距，不要误用常规双列的 8vp。
- Type 17 只放一个右下 `PillButton`，不要保留空 `Stack` 模拟第二个按钮占位。
- Type 10 的四个模块固定为 144 × 52vp；标题超过兼容高度时必须更换 Type。
- 不要让整宽业务组件在 `align="flex-start"` 的父层中按内容宽度收缩。
- 不要通过 `style`、`className`、硬编码颜色或未知 Props 增加 runtime 未公开的 Panel 外观；Type 13 背板只使用公开的 `Stack surface="backplate"`。

## 9. Runtime 执行基线

- 所有 `CardButton` 统一使用当前 runtime 的固定 16px 圆角，只能出现在半卡宽父区内的上下竖排操作槽或 Type 9 的 2×2 操作网格中，不生成 `radius` 或 `style`。
- `PillButton` 在透明父区中使用 runtime 默认的 136 × 36vp；位于 Type 13 的 `surface="backplate"` 内时，runtime 自动把按钮切换为 120 × 36vp。背板父区使用 `position="relative"`，单按钮槽固定为 `position="absolute" left={12} bottom={6} width={120} height={36}`；Option F 中两个纵向按钮的 120 × 80vp 操作组同样固定在 `left={12} bottom={6}`，且只用于同一背板内同时存在紧凑内容的特殊子布局。纯操作列必须改用 Type 15／16 的 `CardButton`。背板内 `PillButton` 必须使用 `appearance="card"`，不得拉伸为整卡宽度。
- Type 13 使用合法的 `Card.appearance` 作为整卡背景；左右父区必须按 7.2.1 判断是否使用公开的 `Stack surface="backplate"`，不能把透明父区作为默认答案。父区内部允许组合标题、内容和符合数量规则的按钮，但不生成 runtime 未公开的 Panel appearance、圆角或裁剪 Props。
- Type 10、Type 14 的网格子项只作为透明布局槽；具体视觉由槽内业务组件自身负责，不为外层 `Stack` 增加背景或圆角。
