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

标题是卡片的信息层，不是 Type 的固定属性。所有 2×4 Type 都允许按输入语义生成或省略全局标题；不得因为选择了 Type 12–17 就删除输入中需要表达的标题。

最简单的判断原则是：输入包含需要命名主题的数据类信息或日程类信息时，允许生成全局标题，例如天气、睡眠、设备状态、运动数据、会议或日程；标题内容必须来自用户意图或输入数据，不得为了填充版面虚构。没有明确主题、标题会重复正文，或加入标题后剩余区域无法容纳业务组件时，可以省略全局标题并保留必要的局部标题。

| 区域 | 必要性 | 尺寸 / 弹性 | 布局规则 |
|---|---|---|---|
| 标题区 | 按输入语义可选 | `flex0; height:auto`; 宽 296vp | 高度由标题组件自然撑开，不参与剩余空间分配；标题是否存在不限制 Type 选择 |
| 标题 Icon | 按标题组件选用 | 20 × 20vp | 锚定标题区右上角；标题区高度取文字组与 Icon 实际高度的较大值 |
| 标题后间距 | 存在全局标题时必选 | 4vp | 从标题区实际底部开始计算；无标题时不保留空间距 |
| 内容区 | 必选 | 按 Type 使用 `flex0` 或 `flex1` | 宽高必须由所属 Type 确定，不得照抄 HTML 参考图中的固定 `top` |
| 操作区 | 按真实 Action 可选 | `flex0`; 单个按钮最多占一个半卡宽父区 | 1 个 Action 使用 `PillButton`；恰好 2 个同级 Action 优先左右各一个 `PillButton`，需要紧凑操作列时使用上下竖排的 `CardButton`；3–4 个 Action 可使用 Type 9 的 2×2 `CardButton` 网格 |
| 主要区域间距 | 按 Type 必选 | 通常 8vp；Type 15–17 左右为 12vp | 区域不存在时不保留空槽或相邻间距 |

标题参考高度：

- `SingleLineTitle` 文本高 18vp；带 20vp Icon 时标题区通常为 20vp。
- `DoubleLineTitle` 含一行副信息时约为 41vp；副信息为两行时继续自然增高。
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
3. 同组的数据、局部标题和辅助信息应保持在同一连续父区域内；Action 可按可读性和视觉均衡放入对应或相邻操作槽。
4. 布局阶段不得为了适配 Type 改变数据含义、丢失必需信息或虚构 Action；允许在保持信息可识别的前提下调整 Action 的视觉位置。
5. 无全局标题时仍可在各父内容区内部使用局部标题。跨垂域分组缺少其他清晰主语时，各父区都应保留可见的业务标题。

| 冻结后的语义结构 | 优先布局 | 分配规则 |
|---|---|---|
| 单一语义组 | Type 1、Type 12、Type 14 或 Type 10 | 所有组件共同回答同一问题；Type 10 的四格必须同类别、同维度 |
| 单一语义组，只有 1 个 Action | Type 17 或 Type 13 变体 | 使用 `PillButton`，放入左或右半卡宽父区；不得生成整卡宽按钮 |
| 单一语义组，恰好 2 个同级 Action | Type 13 双 `PillButton` 变体；需要紧凑操作列时使用 Type 15／16 | 优先左右各一个 `PillButton`；只有明确需要操作列时才改用上下竖排的 `CardButton` |
| 单一语义组，3–4 个 Action 均服务该组或整卡共同任务 | Type 9 | 使用两列、最多两行的 `CardButton` 操作网格；三个 Action 时不生成第四个空按钮 |
| 两个同级语义组，没有独立 Action | Type 13；纵向关系更自然时可用 Type 12 | Type 13 左右父区分别承载一组；Type 12 上下内容区分别承载一组 |
| 卡片恰好有 2 个同级 Action | Type 13 双 `PillButton` 变体 | 左右各一个 136 × 36vp `PillButton`；优先靠近相关数据，但不要因严格归组把两个按钮挤入同一狭窄父区 |
| 跨垂域且不存在共同任务对象 | 不合并生成 | 保留主问题，其他组报告为未满足或另行生成，不得仅因 2×4 空间较大而拼卡 |

例如“晨跑准备”同时包含睡眠／运动健康与耳机／音乐时，可以因共同任务对象合并为一张卡。健康数据和设备数据仍分别进入 Type 13 的左右父区；若恰好有“进入锻炼”和“打开歌单”两个同级 Action，可使用左右双 `PillButton`。Action 应尽量靠近相关数据，但完整可读与布局均衡优先于机械的父区归属。

### 3.2 2×4 按钮限制

- 2×4 可以使用 `PillButton` 和 `CardButton`，禁止使用 `CircleButton`。
- 只有 1 个 Action 时使用 `PillButton`，不得用 `CardButton` 近似替代。
- 恰好 2 个同级 Action 时，优先使用左右双 `PillButton`；左右各一个 144vp 父区，每个按钮保持 136 × 36vp。
- 只有明确需要紧凑操作列时，2 个 Action 才改用上下竖排的 `CardButton`；不得把两个 `CardButton` 仅做一行左右并排。三个或四个 Action 可使用 Type 9 的 2×2 操作网格。
- 单个 `PillButton` 或 `CardButton` 都不得横跨 296vp 安全内容区。左右双 `PillButton` 是两个独立的半卡按钮，不是一个整卡宽按钮。
- Type 17 的单 Action 槽使用 `PillButton`；Type 13 可使用单 `PillButton`、左右双 `PillButton` 或竖排 `CardButton`；Type 15、Type 16 用于紧凑竖排的双 `CardButton`；Type 9 用于三个或四个 `CardButton` 的 2×2 操作网格。
- 同一个 action 只能生成一个按钮，不得用 `PillButton` 与 `CardButton` 重复表达。
- 没有 action 时不得为了填充布局而虚构按钮。

### 3.3 模块数与 Type

下表只统计 Type 自身的内容槽和操作槽，不统计可选的全局标题；存在全局标题时，在表中数量上加 1。

| 内容／操作模块数 | Type |
|---:|---|
| 1 | Type 1 |
| 2 | Type 12、Type 13、Type 17 |
| 3 | Type 9、Type 15、Type 16 |
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
| Type 1 | 可选标题 + 单内容 | 标题存在时 `flex0`；主内容 `flex1`、高度自适应 | 内容为 296 × A | 只用于无 Action 的整宽主内容；有一个 Action 时改用 Type 17 或 Type 13 变体，将 `PillButton` 限制在半卡宽父区 |
| Type 9 | 可选标题 + 2×2 CardButton 操作网格 | 标题存在时 `flex0`；操作网格 `flex0` | `144 + 8 + 144 = 296`；两行槽高均为 `(A − 8) ÷ 2`，且必须在 48–64vp 内 | 用于同一语义组或整卡共同任务的三个或四个 Action；三个 Action 时按顺序占用前三个槽，不创建空按钮 |
| Type 12 | 可选标题 + 上下二分 | 标题存在时 `flex0`；两区均 `flex1`、高度自适应 | 单区高 `(A − 8) ÷ 2`；无标题时为 296 × 64 | 两个同级内容区可分别承载一个语义组；组内字段不得跨越上下区域 |
| Type 13 | 可选标题 + 左右独立父内容区 | 标题存在时 `flex0`；两父区均 `flex0` | `144 + 8 + 144 = 296`；父区各 144 × A；无标题纯内容变体的推荐内部安全区为 120 × 112 | 两个信息组分别占一个父区；任一父区可选 `surface="backplate"`。可放置单个 `PillButton`，也可在恰好两个同级 Action 时左右各放一个 `PillButton` |
| Type 17 | 可选标题 + 左内容 + 右下 PillButton | 标题存在时 `flex0`；两模块均 `flex0` | `140 + 12 + 144 = 296`；左右父区高 A；按钮自身固定 136 × 36 | 用于一个内容组只有一个 Action，且按钮服务左侧内容或整卡共同任务；`PillButton` 在右侧半卡宽父区底部对齐 |
| Type 15 | 可选标题 + 左内容 + 右侧双 CardButton | 标题存在时 `flex0`；三模块均 `flex0` | 横向 `140 + 12 + 144 = 296`；右侧每个按钮槽高 `(A − 8) ÷ 2` | 两个按钮都必须服务左侧内容或整卡共同任务；不同组各自拥有 Action 时改用 Type 13 |
| Type 16 | 可选标题 + 左侧双 CardButton + 右内容 | 标题存在时 `flex0`；三模块均 `flex0` | 横向 `144 + 12 + 140 = 296`；左侧每个按钮槽高 `(A − 8) ÷ 2` | Type 15 的左右镜像；两个按钮都必须服务右侧内容或整卡共同任务 |
| Type 14 | 可选标题 + 2×2 四宫格 | 标题存在时 `flex0`；四模块均 `flex0` | 横向 `144 + 8 + 144 = 296`；纵向每格高 `(A − 8) ÷ 2` | 四个内容区无标题时各 144 × 64；槽位自身不增加 Panel 外观，内容不得跨格 |
| Type 10 | 可选标题 + 同类信息 2×2 四宫格 | 标题存在时 `flex0`；四模块均 `flex0` | 每格 144 × 52；`144 + 8 + 144 = 296`，`52 + 8 + 52 = 112` | 四格必须表达同类别、同维度信息；槽位自身不增加 Panel 外观；存在标题时 `T > 20` 不兼容 |

## 5. 操作区

| Type | 按钮选择 | 槽位尺寸 | 排列方式 |
|---|---:|---|---|
| Type 13 | 1 个 Action 用单 `PillButton`；恰好 2 个同级 Action 优先用双 `PillButton` | 每个 `PillButton` 分别位于一个 144 × A 半卡父区内 | 单按钮按子布局定位；双按钮左右各一个，不拉伸 |
| Type 9 | 3–4 个 `CardButton` | 每个 144 × `(A − 8) ÷ 2`，高度必须在 48–64vp 内 | 两列、最多两行；三个 Action 时第四格不存在 |
| Type 15 | 2 个 `CardButton` | 每个 144 × `(A − 8) ÷ 2` | 右侧上下排列，间距 8 |
| Type 16 | 2 个 `CardButton` | 每个 144 × `(A − 8) ÷ 2` | 左侧上下排列，间距 8 |
| Type 17 | 1 个 `PillButton` | 按钮 136 × 36，位于 144vp 宽父区内 | 右下对齐 |

`PillButton` 使用 runtime 固定的 136 × 36vp，不拉伸；`CardButton` 由半卡宽竖排操作列或 Type 9 网格分配 48–64vp 高的子槽，并使用 `width:100%`、`height:100%` 填满该子槽。生成 JSX 不传入不存在的 `width`、`height`、`radius` 或 `position` Props。

当卡片包含两个信息组时，Action 应尽量靠近相关数据，但可读性、完整显示和视觉均衡的优先级更高。恰好两个同级 Action 时，可将两个 `PillButton` 分别放入左右半卡父区；按钮文本必须能独立表达操作，避免产生错误的业务归属。

## 6. 尺寸与实现规则

- 有全局标题时标题区使用自然高度，下方区域从标题实际底部 + 4vp 开始；此规则适用于所有 Type。
- 无全局标题时直接使用完整的 296 × 136vp 安全内容区，不生成空标题槽。
- 基础等宽双列满足 `144 + 8 + 144 = 296`；144vp 子列满足 `68 + 8 + 68 = 144`。
- Type 15–17 使用非对称双列：`140 + 12 + 144 = 296` 或其镜像。
- `flex0` 表示模块不参与剩余空间分配；`flex1` 必须继续标明高度、宽度或宽高均自适应。
- 弹性纵向内容区使用 `flex={1} minHeight={0}`；固定区域使用明确的 `basis`、`width` 或 `height`。
- Type 9、Type 15、Type 16 的 `CardButton` 行高随 `A` 变化，必须位于 48–64vp 范围内，且槽位宽度不得小于高度。若标题增高导致按钮槽无法容纳 `CardButton`，应更换 Type、减少非核心内容或停止并报告。
- Type 10 的四个 144 × 52vp 模块固定不伸缩；标题实际高度超过 20vp 时必须更换 Type。
- Type 12 两个内容区默认等分剩余高度，不得写成一个固定、一个弹性。
- Type 13 的左右父区分别承载一个完整语义组，不得在同一父区混排两组信息。无全局标题的纯内容变体推荐在每个父区四边预留 12vp，并在 120 × 112vp 内组织子布局；存在全局标题时父区高度改为 A，内部安全高度同步缩减。需要局部标题、背板或内部操作区时，父区可以重新分配标题、内容和操作槽，但所有可见内容必须留在各自 144 × A 父区内，不得跨区、重叠或占用中间 8vp 间距；不能机械复制 2×2 的 136 × 136vp 固定骨架。
- Type 17 只生成一个右下 `PillButton`，不得保留第二个空按钮组件、占位模块或虚构 action。
- 整宽组件必须占满所属模块：整宽区为 296vp，普通等宽列为 144vp，非对称内容列为 140vp。包裹层使用 `width="full" minWidth={0}`。
- 标题增高或文本换行导致槽位小于业务组件最小尺寸时，应更换 Type、减少内容或停止并报告，不得依赖裁剪或溢出。
- 产品规格使用 vp；HTML 骨架预览可使用同数值 px 做 1:1 校核。

## 7. 标准 JSX 布局模板
共同规则：

- 根节点固定为 `<Card size="2x4" appearance="...">`；默认 `padding={12}` 得到 296 × 136vp 安全内容区。
- 模板禁止 `style`、`className`、spread Props 和硬编码颜色。
- 2×4 单 Action 使用 `PillButton`；恰好两个同级 Action 时优先左右双 `PillButton`，只有需要紧凑操作列时才使用上下竖排的 `CardButton`；三个或四个 Action 可使用 Type 9 的 2×2 `CardButton` 网格。每个按钮都必须限制在自己的半卡宽父区或半卡宽子槽内。
- 示例中的 `dataIds` 与 `actionId` 只说明绑定位置；实际生成必须替换为输入中真实存在的 ID。

以下各 Type 示例即使展示为无标题版本，也不表示该 Type 禁止标题。数据类或日程类信息存在明确主题时，在 `Card` 顶部增加自然高度标题区，并把原 Type 骨架放入剩余高度为 A 的主区域。对于原本使用 `direction="row"` 的 Type，`direction="row"` 应移动到主区域 `Stack`，不能继续写在 `Card` 上；主区域 `gap` 仍使用该 Type 规定的 8vp 或 12vp：

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

### 7.1 Type 1：标题 + 单内容

```jsx
<Card size="2x4" appearance="blue-soft">
  <Stack flex={0}>
    <SingleLineTitle title="今日数据" />
  </Stack>

  <Stack flex={1} minHeight={0} mt={4} width="full" minWidth={0} gap={4} align="flex-start" justify="end">
    {/* 单内容区；整宽组件必须撑满 296vp */}
  </Stack>
</Card>
```

Type 1 不放置按钮。整卡只有一个 Action 时改用 Type 17 或 Type 13 变体，并把 `PillButton` 放入半卡宽父区；不得在 Type 1 底部增加横跨 296vp 的整宽操作槽。

### 7.2 Type 12：可选标题 + 上下二分

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

### 7.3 Type 13：可选标题 + 左右独立父内容区

```jsx
<Card size="2x4" appearance="neutral-soft" direction="row" gap={8}>
  <Stack surface="backplate" basis={144} width={144} height="full" align="center" justify="center">
    <Stack width={120} height={112} minWidth={0} gap={8}>
      <Stack basis={18} width="full" height={18}>
        <SingleLineTitle title="健康状态" />
      </Stack>
      <Stack flex={1} minHeight={0} width="full">
        {/* 健康数据与辅助信息 */}
      </Stack>
    </Stack>
  </Stack>

  <Stack basis={144} width={144} height="full" align="center">
    <Stack width={136} height="full" minWidth={0} gap={8}>
      <Stack basis={18} width="full" height={18}>
        <SingleLineTitle title="设备状态" />
      </Stack>
      <Stack flex={1} minHeight={0} width="full">
        {/* 设备数据与辅助信息 */}
      </Stack>
      <Stack basis={36} width={136} height={36}>
        <PillButton label="设备设置" appearance="card" actionId="action.openDevice" />
      </Stack>
    </Stack>
  </Stack>
</Card>
```

Type 13 固定的是两个 144vp 宽父区和中间 8vp 间距；无全局标题时父区高 136vp，存在全局标题时父区高 A。左右父区不要求采用完全相同的内部结构，但各组数据和局部标题应保持可独立识别。`surface="backplate"` 可按父区独立选择；无标题纯内容父区推荐使用 120 × 112vp 内部安全区，存在全局标题或复合内容时按实际父区高度重新分配局部标题、内容和操作槽。只有一个 Action 时使用单 `PillButton`；恰好两个同级 Action 时优先左右各放一个 `PillButton`。Action 应尽量靠近相关数据，但不需为此把两个按钮挤入同一狭窄父区；没有 action 时同时删除按钮及其相邻间距。

恰好两个同级 Action 时，可在 Type 13 的左右父区底部各放一个 `PillButton`：

```jsx
<Card size="2x4" appearance="purple-gradient" direction="row" gap={8}>
  <Stack basis={144} width={144} height="full" minWidth={0} justify="between" align="center">
    <Stack flex={1} minHeight={0} width="full">
      {/* 左侧信息 */}
    </Stack>
    <Stack basis={36} width={136} height={36}>
      <PillButton label="操作一" appearance="card" actionId="action.first" />
    </Stack>
  </Stack>

  <Stack basis={144} width={144} height="full" minWidth={0} justify="between" align="center">
    <Stack flex={1} minHeight={0} width="full">
      {/* 右侧信息 */}
    </Stack>
    <Stack basis={36} width={136} height={36}>
      <PillButton label="操作二" appearance="card" actionId="action.second" />
    </Stack>
  </Stack>
</Card>
```

### 7.4 Type 17：可选标题 + 左内容 + 右下 PillButton

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

### 7.5 Type 9：可选标题 + 2×2 CardButton 操作网格

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

### 7.6 Type 15：可选标题 + 左内容 + 右侧双 CardButton

```jsx
<Card size="2x4" appearance="orange-gradient" direction="row" gap={12}>
  <Stack basis={140} width={140} height="full" minWidth={0}>
    {/* 左内容区 */}
  </Stack>

  <Stack basis={144} width={144} height="full" gap={8}>
    <Stack basis={64} width="full" height={64}>
      <CardButton text="操作一" actionId="action.first" />
    </Stack>

    <Stack basis={64} width="full" height={64}>
      <CardButton text="操作二" actionId="action.second" />
    </Stack>
  </Stack>
</Card>
```

### 7.7 Type 16：可选标题 + 左侧双 CardButton + 右内容

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

### 7.8 Type 14：可选标题 + 四宫格

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

### 7.9 Type 10：可选标题 + 同类信息四宫格

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
- 不要在 2×4 中使用 `CircleButton`。只有一个 Action 时使用单 `PillButton`；恰好两个同级 Action 时优先左右双 `PillButton`；需要紧凑操作列时才使用上下竖排的 `CardButton`。
- 不要把标题高度固定为 20vp，也不要照抄 HTML 参考图中的 `top={24}`。
- 不要根据 Type 编号禁止全局标题。数据类或日程类信息存在明确主题时，Type 12–17 也允许生成全局标题；标题必须来自真实意图／数据，并按 A 缩减其余区域。没有全局标题时，多组布局仍可在各内容父区内部使用属于本组的局部标题。
- 不要使用 Type 8 的上 1 下 2 按钮结构。Type 9 是允许的 2×2 `CardButton` 操作网格，只用于三个或四个真实 Action。
- Type 15、Type 16 的一个按钮槽只能放一个 `CardButton`。
- 不要把 `CardButton` 放入宽度小于高度的槽位；存在标题时必须根据实际 A 检查按钮槽。
- 不要让 `PillButton` 或 `CardButton` 横跨 296vp 安全内容区；任何按钮都必须限制在左或右半卡宽父区内。
- 同一语义组／操作区域有且只有一个 Action 时，不要生成 `CardButton`，也不要在 Type 1 底部增加整宽操作槽；改用 Type 17 或 Type 13 变体中的 `PillButton`。
- 不要把不同垂域的数据混放在同一内容父区。Action 应尽量靠近相关数据，但可为了完整显示和视觉均衡放入相邻半卡操作槽；此时按钮文本必须能独立说明操作。
- Type 13 不得把左右父区误当成一个跨区画布。无全局标题的纯内容变体推荐使用 120 × 112vp；存在标题、背板或内部 CardButton 时可以重新分配父区内部空间，但不得跨越 144 × A 父区边界或中间 8vp 间距。
- Type 15、Type 16 使用 12vp 左右间距，不要误用常规双列的 8vp。
- Type 17 只放一个右下 `PillButton`，不要保留空 `Stack` 模拟第二个按钮占位。
- Type 10 的四个模块固定为 144 × 52vp；标题超过兼容高度时必须更换 Type。
- 不要让整宽业务组件在 `align="flex-start"` 的父层中按内容宽度收缩。
- 不要通过 `style`、`className`、硬编码颜色或未知 Props 增加 runtime 未公开的 Panel 外观；Type 13 背板只使用公开的 `Stack surface="backplate"`。

## 9. Runtime 执行基线

- 所有 `CardButton` 统一使用当前 runtime 的固定 16px 圆角，只能出现在半卡宽父区内的上下竖排操作槽或 Type 9 的 2×2 操作网格中，不生成 `radius` 或 `style`。
- `PillButton` 使用 runtime 固定的 136 × 36vp 和 `appearance="card"`，在 2×4 中不得被拉伸为整卡宽度。
- Type 13 使用合法的 `Card.appearance` 作为整卡背景；左右父区可按需使用公开的 `Stack surface="backplate"`，也可保持透明。父区内部允许组合标题、内容和符合数量规则的按钮，但不生成 runtime 未公开的 Panel appearance、圆角或裁剪 Props。
- Type 10、Type 14 的网格子项只作为透明布局槽；具体视觉由槽内业务组件自身负责，不为外层 `Stack` 增加背景或圆角。
