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
2. **顶层 Type 区域**：Type 12、Type 13、Type 14、Type 15、Type 15-R、Type 17 定义整卡的区域数量、主要尺寸、间距和固定槽位置。
3. **父内容区内部子布局**：Type 13 的 118 × 112vp 内部安全区，以及 Type 15、Type 15-R、Type 17 的 140 × 136vp 内容区，需要继续选择本文规定的参考／适配子布局，再放入业务组件。

内部参考／适配子布局只复用对应 2×2 Type 的模块关系，不是新的 2×4 顶层 Type。子布局内部模块不重复计入整卡顶层模块数，也不得跨越所属父内容区。

### 1.3 顶层区域与标题作用域

当前保留的所有 2×4 顶层 Type 均无公共标题，直接使用完整的 296 × 136vp 安全内容区，不生成公共标题槽、空标题槽或公共标题后的间距。

| 区域 | 必要性 | 尺寸 / 弹性 | 布局规则 |
|---|---|---|---|
| 公共标题区 | 禁止 | 不生成 | 所有保留的 2×4 顶层 Type 均无公共标题 |
| 子布局局部标题 | 按所选子布局必选 | `flex0; height:auto` | Type 13 子布局标题宽 118vp，相邻纵向模块间距 6vp；Type 15、Type 15-R、Type 17 的适配子布局标题宽 140vp，相邻主要模块间距 8vp |
| 内容区 | 必选 | 按 Type 使用 `flex0` 或 `flex1` | 宽高必须由所属 Type 确定，不得照抄 HTML 参考图中的固定 `top` |
| 操作区 | 按真实 Action 可选 | `flex0`; 单个按钮最多占一个半卡宽父区 | 根据 Action 数量、归属和所选 Type 使用 `PillButton` 或 `CardButton` |
| 主要区域间距 | 按 Type 必选 | 通常 8vp；Type 15、Type 15-R、Type 17 左右为 12vp | 区域不存在时不保留空槽或相邻间距 |

Type 13 需要标题时，只能在对应的 118 × 112vp 父内容安全区内部使用局部标题；Type 15、Type 15-R、Type 17 的标题只能属于 140 × 136vp 内容区内部的适配子布局。Type 12、Type 14 不设置标题区。

- 局部标题必须来自用户意图或输入数据，不得为了填充版面虚构。标题会重复正文或剩余区域无法容纳业务组件时，应更换无标题子布局或更换顶层 Type。
- `SingleLineTitle` 是纯文本标题，高度固定为 18vp。
- `SingleLineTitle` 不支持标题 Icon；不得为参考图中的图标占位增加标题高度。
- `DoubleLineTitle` 含一行副信息时为 `18 + 4 + 18 = 40vp`；副信息为两行时继续自然增高。
- 局部标题高度记为 `T`。Type 13 子布局和 140vp 适配子布局必须分别按自身的 6vp、8vp 间距公式计算剩余空间。
- HTML 中的固定坐标和尺寸仅供视觉参考，不得写成 JSX 定位值；应按局部标题实际高度、区域间距和所属子布局的可用空间计算。

## 2. 如何选择布局

布局按以下顺序选择：

1. 读取信息处理阶段的垂域分组和 Action 语义关系，保持各组内容可独立识别。
2. 判断信息适合上下、左右、非对称固定槽还是四宫格，先选择顶层布局家族。
3. 根据语义组数量、组间关系和 Action 数量确定顶层 Type，不按组件总数机械凑槽位。
4. 根据信息关系、局部标题和 Action 选择父内容区内部子布局。
5. 检查各组信息是否完整、业务组件最小尺寸是否能放入目标槽位，以及 Action 是否一一对应。

Type 约束顶层骨架、主要区域尺寸、区域间距和固定槽位类型。允许的内部变化必须由对应 Type 明确声明。若改动已经改变顶层区域数量、主要尺寸公式、固定槽位置或语义归属，应重新选择 Type，而不是继续沿用原 Type 名称。

### 2.1 先完成语义分组

1. 2×4 场景先按垂域和大主题分组。跨垂域内容只有存在明确共同任务时才能放进同一张卡片，并且仍要保持各组可独立识别。
2. 直接服务某组的 Action 应优先靠近该组；当严格归组会导致按钮过窄、文字裁剪或布局失衡时，可将 Action 放入相邻的半卡操作槽，但按钮文本必须能独立说明操作。
3. 同组的数据、局部标题和辅助信息原则上应保持在同一连续父区域内；Action 可按可读性和视觉均衡放入对应或相邻操作槽。唯一允许的内容拆分是：单一垂域中已经形成“核心结论 + 属性明细”两个可独立识别的完整信息模块时，可以使用 Type 13 将核心值与状态放在一侧、同主题的多项属性明细放在另一侧。不得把彼此依赖的单个字段或同一组件应共同表达的内容随意拆到左右两区。
4. 布局阶段不得为了适配 Type 改变数据含义、丢失必需信息或虚构 Action；允许在保持信息可识别的前提下调整 Action 的视觉位置。
5. 顶层无公共标题时，仍可按所选子布局在父内容区内部使用局部标题。跨垂域分组缺少其他清晰主语时，各父区都应保留可见的业务标题。

例如“晨跑准备”同时包含睡眠／运动健康与耳机／音乐时，可以因共同任务对象合并为一张卡。健康数据和设备数据仍分别进入 Type 13 的左右父区；若恰好有“进入锻炼”和“打开歌单”两个同级 Action，可使用左右双 `PillButton`。Action 应尽量靠近相关数据，但完整可读与布局均衡优先于机械的父区归属。

### 2.2 选择顶层布局家族

| 顶层信息关系 | 布局家族 | 候选 Type |
|---|---|---|
| 两个内容区纵向排列 | 整宽纵向流 | Type 12 |
| 两个完整信息模块左右分区，或同一主题的“核心结论 + 属性明细” | 双背板分区 | Type 13 |
| 一侧为完整内容，另一侧为一个或两个固定 `CardButton`／`InfoBlock` 槽 | 非对称内容与固定槽 | Type 17、Type 15、Type 15-R |
| 恰好四个有效的固定 `CardButton`／`InfoBlock` 模块 | 固定四宫格 | Type 14 |

顶层模块数只用于初选：Type 12、Type 13、Type 17 为两个顶层内容／操作模块；Type 15、Type 15-R 为三个；Type 14 为四个。每个独立内容槽和操作槽各计一个，Type 13 父区内部的标题、子布局、背板和按钮不重复计数。最终仍须检查信息层级、标题高度和业务组件最小占位。

### 2.3 顶层 Type 选择总表

| 语义结构 / Action 关系 | 顶层 Type | 顶层分配规则 |
|---|---|---|
| 单一语义组，两个上下内容区共同回答同一问题 | Type 12 | 两个 296vp 整宽内容区上下排列；不得追加公共标题、操作槽或第三个顶层模块 |
| 单一语义组，包含明确的核心结论与多项属性明细 | Type 13 | 左区完整表达核心值与状态，右区使用 `TableText` 等组件表达同主题明细；两个父区均使用 `surface="backplate"` |
| 两个同级语义组，没有独立 Action | Type 13；纵向关系更自然时可用 Type 12 | Type 13 左右各承载一组；Type 12 上下各承载一组 |
| 单一语义组，只有 1 个 Action | Type 17 或 Type 13 | Type 17 在右下固定槽使用 `CardButton`；Type 13 使用含单个 `PillButton` 的 Type 10-A 参考子布局；不得生成整卡宽按钮 |
| 恰好 2 个同级 Action，可分别归入左右信息父区 | Type 13 双 `PillButton` 变体 | 左右父区分别使用含单个按钮的参考子布局，各放一个 118 × 36vp `PillButton` |
| 恰好 2 个 Action，数据集中在一侧、操作集中在另一侧 | Type 15 或 Type 15-R | 两个固定槽分别使用 `CardButton`；内容在左用 Type 15，内容在右用 Type 15-R |
| 恰好 3 个 Action，均服务同组或整卡共同任务 | 当前无可用布局 | 停止并报告，不得删减、合并、虚构 Action 或用空槽伪装 Type 14 |
| 恰好 4 个 Action，均服务同组或整卡共同任务 | Type 14 | 四个 Action 分别使用一个 `CardButton`，四槽全部填满 |
| 单一语义组，恰好需要四个固定信息／操作模块 | Type 14 | 四槽必须全部有效；Action 使用 `CardButton`，非操作信息可使用 `InfoBlock`；混用时同类组件按列纵排 |
| 跨垂域且不存在共同任务对象 | 不合并生成 | 保留主问题，其他组报告为未满足或另行生成，不得仅因 2×4 空间较大而拼卡 |

### 2.4 根据 Action 确认操作槽

- 2×4 可以使用 `PillButton` 和 `CardButton`，禁止使用 `CircleButton`。
- 只有 1 个 Action 时通常使用 `PillButton`；Type 17 是固定结构例外，可在右下 144 × 64vp 槽中使用 `CardButton`，不得替换为其他按钮类型。
- 恰好 2 个同级 Action 且两个 Action 能分别进入左右信息父区时，左右父区分别使用含单个按钮的 Type 10-A 参考子布局，各放一个 118 × 36vp `PillButton`。
- 两个 Action 集中在同一侧时，使用 Type 15／Type 15-R 的两个 144 × 64vp 固定槽；存在 Action 的槽必须使用 `CardButton`，只有非操作型槽位才可使用 `InfoBlock`。
- Type 13 的 Type 15 参考子布局只适用于同一父内容区内同时存在 118 × 28vp 紧凑内容，且两个 Action 都直接服务该内容的场景。
- 三个 Action 当前没有可用的 2×4 布局；四个有效 Action 可分别使用一个 `CardButton` 填满 Type 14 四槽。
- 单个 `PillButton` 或 `CardButton` 都不得横跨 296vp 安全内容区。左右双 `PillButton` 是两个独立的半卡按钮，不是一个整卡宽按钮。
- 同一个 action 只能生成一个按钮，不得用 `PillButton` 与 `CardButton` 重复表达。
- 没有 action 时不得为了填充布局而虚构按钮。

### 2.5 选择父内容区内部子布局

Type 13 的左右背板父区各自在 118 × 112vp 内部安全区中选择一种参考子布局：

| 参考子布局 | 信息关系 | 局部标题 | Action |
|---|---|---|---|
| Type 0 参考子布局 | 单个 Data Display 内容 | 无 | 无 |
| Type 1 参考子布局 | 单个主体内容 | 必选 | 无 |
| Type 2 参考子布局 | 核心内容 + 独立明细 | 必选 | 无 |
| Type 10-A 参考子布局 | 单个主体内容 | 必选 | 1 个 `PillButton` |
| Type 12 参考子布局 | 两个横向并列内容 | 无 | 1 个 `PillButton` |
| Type 15 参考子布局 | 单行紧凑内容 | 无 | 2 个 `PillButton` |

Type 15、Type 15-R、Type 17 的 140 × 136vp 内容区选择一种共用适配子布局：

| 适配子布局 | 信息关系 | 局部标题 | Action |
|---|---|---|---|
| Type 0 · 140vp 适配版 | 单个 Data Display 内容 | 无 | 无 |
| Type 1 · 140vp 适配版 | 单个主体内容 | 必选 | 无 |
| Type 10-A · 140vp 适配版 | 单个主体内容 | 必选 | 1 个 `PillButton` |
| Type 12 · 140vp 适配版 | 两个横向并列内容 | 无 | 1 个 `PillButton` |
| Type 15 · 140vp 适配版 | 单个紧凑内容 | 无 | 2 个 `PillButton` |
| Type 10-B · 140vp 适配版 | Hero + 紧密关联的次要信息 | 必选 | 1 个 `PillButton` |

子布局名称只表示复用对应的模块关系，不新增同名 2×4 顶层 Type，也不沿用 2×2 的 136 × 136vp 尺寸。

## 3. 通用实现规则

### 3.1 Stack、Grid 与尺寸语义

- 根节点固定为 `<Card size="2x4" appearance="...">`；默认 `padding={12}` 得到 296 × 136vp 安全内容区。
- `flex0` 表示模块不参与剩余空间分配；在 JSX 中使用 `flex={0}` 或明确的 `basis`、`width`、`height` 表达固定区域。
- `flex1` 表示模块至少在一个方向使用剩余空间，必须继续标明自适应方向；弹性纵向内容区通常使用 `flex={1} minHeight={0}`。
- 整宽组件必须占满所属模块：整宽区为 296vp，普通等宽列为 144vp，非对称内容列为 140vp。包裹层使用 `width="full" minWidth={0}`，不得因父层对齐方式按内容收缩。
- 基础等宽双列满足 `144 + 8 + 144 = 296`；144vp 子列满足 `68 + 8 + 68 = 144`。
- Type 15、Type 15-R、Type 17 使用非对称双列：`140 + 12 + 144 = 296` 或其镜像。
- 产品规格使用 vp；HTML 骨架预览可使用同数值 px 做 1:1 校核。

### 3.2 标题与内容对齐

- 顶层不生成公共标题；局部标题使用 `flex={0}`，宽度由所属子布局决定，高度由标题组件自然撑开。
- 标题下方空间从标题实际底部开始计算；Type 13 的相邻纵向主要模块使用 6vp，140vp 适配子布局使用 8vp。
- 标题增高或文本换行导致槽位小于业务组件最小尺寸时，按照 2.6 的容量规则处理。
- 需要左对齐、底端对齐或居中时，由业务组件外层 `Stack` 表达，不向业务组件传入未知的布局 Props。

### 3.3 按钮与固定槽

- 普通 2×4 `PillButton` 沿用 runtime 的 136 × 36vp、圆角 30vp；Type 13 参考子布局中固定为 118 × 36vp、圆角 18vp；140vp 适配子布局中固定为 136 × 36vp 并左对齐，右侧留 4vp。
- Type 13 的 `PillButton` 作为 `flex0` 模块进入普通纵向流，不使用绝对定位或底部锚定。
- Type 14、Type 15、Type 15-R 的 `CardButton`／`InfoBlock` 父槽，以及 Type 17 的右下固定槽，均为 144 × 64vp、圆角 16vp，不使用 48–64vp 动态槽高。
- 所有 `CardButton` 使用当前 runtime 的固定 16px 圆角，只能进入本文规定的半卡宽固定槽，不生成 `radius` 或 `style`。
- 生成 JSX 不向业务组件传入不存在的 `width`、`height`、`radius` 或 `position` Props；尺寸和位置由外层槽位负责。

### 3.4 数据绑定与禁止项

- 示例中的 `dataIds` 与 `actionId` 只说明绑定位置；实际生成必须替换为输入中真实存在的 ID。
- 需要 Card 语义配色的业务组件传入 `appearance="card"`。
- 模板禁止原生元素、`style`、`className`、spread Props、未知 Props 和硬编码颜色。
- 不得使用硬编码背景模拟 runtime 未公开的 Panel；Type 13 背板只使用公开的 `Stack surface="backplate"`。

## 4. 布局实现与JSX写法

### 4.1 整宽纵向流：Type 12

骨架：无标题 + 上下两个整宽内容区。
尺寸与闭合：两个内容区宽度均为 296vp，均使用 `flex={1} minHeight={0}`，中间间距为 8vp；参考高度均为 `(136 − 8) ÷ 2 = 64vp`，满足 `64 + 8 + 64 = 136vp`。

操作区：无，不得向任一内容区外追加按钮。

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

Type 12 不设置标题区或操作槽，不得增加第三个顶层模块、改用固定高度分配或追加按钮。

### 4.2 双背板分区：Type 13

骨架：无公共标题 + 左右两个均分背板父内容区。
尺寸与闭合：左右父区均为 `flex0`、142 × 136vp，水平间距为 12vp，满足 `142 + 12 + 142 = 296vp`。每个父区四边内缩 12vp，形成 118 × 112vp 内部安全区。

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

#### 4.2.1 Type 13 通用规则

- 整卡不设置公共标题；需要标题时，在对应父内容区内部使用局部标题。
- 整卡背景使用合法的 `Card.appearance`；父内容区背板由 `surface="backplate"` 在该主题上派生。
- 左右父区都必须使用 `surface="backplate"`，圆角为 16vp，并裁剪内部背景；不得生成透明父区或单侧背板变体。
- `surface="backplate"` 只写在左右顶层父 `Stack` 上，不写在局部标题、内容或按钮包装层上。
- 背板颜色沿用当前 runtime：Light Mode 使用白色、透明度 40%；Dark Mode 使用白色、透明度 10%。该颜色规则只属于父内容区，不扩散到子布局内部模块；在主题深色 5% 的具体色值映射明确前不自行替换。
- 每个父区内部必须建立水平、垂直居中的 118 × 112vp 内层 `Stack`，形成四边各 12vp 的安全边距。
- 左右父区可以分别选择不同参考子布局，但内部模块不得跨区、共享尺寸、共享对齐基准或占用中间 12vp 间距。
- 标题宽 118vp、`flex0`、`height:auto`；公式中的 `T` 为标题实际高度。`SingleLineTitle` 的参考态为 `T = 18vp`，`DoubleLineTitle` 按实际 40vp 或自然换行高度计算。
- 相邻纵向主要模块统一使用 6vp 间距；横向间距按对应子布局定义。
- `PillButton` 固定为 118 × 36vp、圆角 18vp，作为 `flex0` 模块进入普通布局流，不使用绝对定位。
- 不得在子布局中使用原生元素、`style`、`className` 或硬编码背景模拟第二层 Panel，也不得产生越过背板圆角的直角背景。

推荐公共外壳：

```jsx
<Stack surface="backplate" basis={142} width={142} height={136} align="center" justify="center">
  <Stack basis={112} width={118} height={112} minWidth={0}>
    {/* 参考子布局内容 */}
  </Stack>
</Stack>
```

#### 4.2.2 Type 13 父内容区参考子布局

##### Type 0 参考子布局：无标题单内容区

内容区固定为 118 × 112vp，内容水平、垂直居中；仅允许放置 Design System 中归类为 Data Display 的组件。

```jsx
<Stack basis={112} width={118} height={112} align="center" justify="center">
  {/* 单个核心内容模块 */}
</Stack>
```

##### Type 1 参考子布局：标题 + 单内容区

标题区必选，宽 118vp，自然高度为 `T`。内容区宽 118vp，使用 `flex={1} minHeight={0}`；标题与内容间距为 6vp，内容左对齐且底端对齐。

内容区高度为 `112 − T − 6 = 106 − T`；当 `T = 18vp` 时，参考尺寸为 118 × 88vp。

```jsx
<Stack basis={112} width={118} height={112} gap={6}>
  <Stack flex={0} width={118}>{/* 局部标题 */}</Stack>
  <Stack flex={1} width={118} minHeight={0} align="flex-start" justify="flex-end">{/* 单个内容模块 */}</Stack>
</Stack>
```

##### Type 2 参考子布局：标题 + 核心内容 + 明细内容

标题区必选，宽 118vp，自然高度为 `T`。核心内容区和明细内容区均宽 118vp，均使用 `flex={1} minHeight={0}`，默认等分标题及两处 6vp 间距之外的剩余高度。

单个内容区高度为 `(112 − T − 6 − 6) ÷ 2 = (100 − T) ÷ 2`；当 `T = 18vp` 时，两区参考尺寸均为 118 × 41vp。核心区左对齐且顶端对齐，明细区左对齐且底端对齐。

```jsx
<Stack basis={112} width={118} height={112} gap={6}>
  <Stack flex={0} width={118}>{/* 局部标题 */}</Stack>
  <Stack flex={1} width={118} minHeight={0} align="flex-start" justify="flex-start">{/* 核心内容 */}</Stack>
  <Stack flex={1} width={118} minHeight={0} align="flex-start" justify="flex-end">{/* 明细内容 */}</Stack>
</Stack>
```

##### Type 10-A 参考子布局：标题 + 内容 + PillButton

标题区必选，宽 118vp，自然高度为 `T`；内容区宽 118vp，使用 `flex={1} minHeight={0}`。`PillButton` 必选、不得缺省，固定为 118 × 36vp、圆角 18vp，并作为 `flex0` 模块进入普通纵向流。

标题、内容区和按钮之间均为 6vp；内容区高度为 `112 − T − 6 − 6 − 36 = 64 − T`。当 `T = 18vp` 时，参考尺寸为 118 × 46vp。

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

无标题。上方 A、B 内容区均固定为 55 × 70vp，两列水平间距为 8vp。`PillButton` 必选、不得缺省，固定为 118 × 36vp、圆角 18vp；双列内容区与按钮间距为 6vp。

横向满足 `55 + 8 + 55 = 118vp`；纵向满足 `70 + 6 + 36 = 112vp`。

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

无标题。内容区固定为 118 × 28vp，仅适合单行文字、状态值或简单图标；内部组件最小高度超过 28vp 时不得使用该参考子布局。两个 `PillButton` 均为必选，固定为 118 × 36vp、圆角 18vp。

内容区与第一个按钮、两个按钮之间均使用 6vp 间距，满足 `28 + 6 + 36 + 6 + 36 = 112vp`。

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

### 4.3 非对称内容与固定槽：Type 17、Type 15、Type 15-R

这三个 Type 共用一个 140 × 136vp 内容区和同一套内容区适配子布局。Type 17 具有一个右下固定槽；Type 15、Type 15-R 具有位于内容区对侧的两个固定槽。

#### 4.3.1 共用的 140vp 内容区适配子布局

以下六种骨架由对应 2×2 Type 适配而来，适用于 Type 15 的左内容区、Type 15-R 的右内容区和 Type 17 的左内容区。满宽内容模块使用 140vp；`PillButton` 保持 136 × 36vp 并左对齐，右侧留 4vp。内部标题不是整卡公共标题。

##### Type 0 · 140vp 适配版

无标题单内容区，固定为 140 × 136vp，内容水平、垂直居中；仅允许放置 Design System 中归类为 Data Display 的组件。

```jsx
<Stack width={140} height={136} align="center" justify="center">
  {/* Data Display 组件 */}
</Stack>
```

##### Type 1 · 140vp 适配版

标题宽 140vp、`flex0`、`height:auto`；内容区 `flex1`、高度自适应，并左对齐、底端对齐。标题与内容间距为 8vp；内容区高度为 `136 − T − 8 = 128 − T`。参考 `T = 18vp` 时，内容区高 110vp。

```jsx
<Stack width={140} height={136} gap={8}>
  <Stack flex={0} width={140}>{/* 内部标题 */}</Stack>
  <Stack flex={1} width={140} minHeight={0} align="flex-start" justify="flex-end">{/* 内容 */}</Stack>
</Stack>
```

##### Type 10-A · 140vp 适配版

标题、内容区和 `PillButton` 均为必选，相邻模块间距为 8vp。`PillButton` 固定为 136 × 36vp 并左对齐；内容区高度为 `136 − T − 8 − 8 − 36 = 84 − T`。参考 `T = 18vp` 时，内容区高 66vp。

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

无标题；上方双列内容区为两个 66 × 92vp 固定模块，横向间距为 8vp。`PillButton` 必选，固定为 136 × 36vp 并左对齐；内容行与按钮间距为 8vp。

横向满足 `66 + 8 + 66 = 140vp`；纵向满足 `92 + 8 + 36 = 136vp`。

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

无标题；内容区固定为 140 × 48vp，两个 `PillButton` 均为必选并固定为 136 × 36vp。内容区与第一个按钮、两个按钮之间均为 8vp，满足 `48 + 8 + 36 + 8 + 36 = 136vp`。

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

标题、Hero、次要信息和 `PillButton` 均为必选；标题、内容组、按钮之间为 8vp，Hero 与次要信息之间为 2vp。Hero 与次要信息均按内容自然撑高，不强制等高；`PillButton` 固定为 136 × 36vp 并左对齐。

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

#### 4.3.2 Type 17：左内容 + 右下 CardButton／InfoBlock

尺寸与闭合：左内容区为 140 × 136vp，右下固定槽为 144 × 64vp，左右间距为 12vp，满足 `140 + 12 + 144 = 296vp`。
操作区：右下槽锚定安全内容区右下角；存在 Action 时必须放置一个 `CardButton`，不得使用其他按钮类型；无 Action 时可放置一个非操作型 `InfoBlock`。删除的右上槽不保留占位。

```jsx
<Card size="2x4" appearance="blue-soft" direction="row" gap={12}>
  <Stack basis={140} width={140} height="full" minWidth={0}>
    {/* 左内容区：选择 4.3.1 中的一种共用 140vp 适配子布局 */}
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

Type 17 基于 Type 15 删除右上槽位。两个顶层模块均为 `flex0`，内容不得跨区，也不得生成右上空槽、占位模块或虚构 Action。

#### 4.3.3 Type 15：左内容 + 右侧双 CardButton／InfoBlock

尺寸与闭合：左内容区为 140 × 136vp；右侧两槽均为 144 × 64vp，上下间距为 8vp，满足 `64 + 8 + 64 = 136vp`；左右间距为 12vp，满足 `140 + 12 + 144 = 296vp`。
操作区：两个固定槽可分别使用 `CardButton` 或 `InfoBlock`，但存在 Action 的槽必须使用 `CardButton`；不得改变槽位数量、尺寸、间距或位置。

```jsx
<Card size="2x4" appearance="cloudy-gradient" direction="row" gap={12}>
  <Stack basis={140} width={140} height={136} minWidth={0}>
    {/* 选择 4.3.1 中的一种共用 140vp 适配子布局 */}
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

#### 4.3.4 Type 15-R：左侧双 CardButton／InfoBlock + 右内容

Type 15-R 是 Type 15 的镜像。左侧两个固定槽均为 144 × 64vp，上下间距为 8vp；右内容区为 140 × 136vp；左右间距为 12vp，满足 `144 + 12 + 140 = 296vp`。
操作区：两个固定槽可分别使用 `CardButton` 或 `InfoBlock`，但存在 Action 的槽必须使用 `CardButton`；右内容区与 Type 15、Type 17 共用 4.3.1 中的六种适配子布局。

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
    {/* 选择 4.3.1 中的一种共用 140vp 适配子布局 */}
  </Stack>
</Card>
```

### 4.4 固定四宫格：Type 14

骨架：无标题 + 四个固定的 `CardButton`／`InfoBlock` 槽。
尺寸与闭合：每槽为 144 × 64vp、圆角 16vp；横向和纵向间距均为 8vp，满足 `144 + 8 + 144 = 296vp` 与 `64 + 8 + 64 = 136vp`。
操作区：四槽必须全部由有效的 `CardButton` 或 `InfoBlock` 一一填满；存在 Action 的槽必须使用 `CardButton`。不得留空、占位、隐藏、合并或改成动态高度。
排列规则：左列为 A、C，右列为 B、D。混用两种组件时，同类组件必须占用同一列并按上→下排列，同一列不得混排不同类型；四槽全部使用同一组件类型时，两列分别按上→下排列。
视觉规则：每个槽位只承载一个 `CardButton` 或 `InfoBlock`，视觉由槽内组件负责，不生成额外 Panel 外观。

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

## 5. 常见错误

### 5.1 选择阶段错误

- 2×4 顶层布局只允许 Type 12、Type 13、Type 14、Type 15、Type 15-R、Type 17。Type 0、Type 1、Type 2、Type 10-A、Type 10-B 等名称只可按本文规定作为内部参考／适配子布局使用。
- 不要使用 Type 8 的上 1 下 2 按钮结构。三个 Action 当前没有可用的 2×4 布局，应停止并报告；四个有效 Action 可分别使用一个 `CardButton` 填满 Type 14 四槽。
- 不要把不同垂域的数据混放在同一内容父区。Action 可为了完整显示和视觉均衡进入相邻半卡操作槽，但按钮文本必须能独立说明操作。

### 5.2 顶层与子布局错误

- 不要为任何保留的顶层 Type 生成公共标题、空标题槽或公共标题后间距。Type 13 的标题只能进入对应背板父区；Type 15、Type 15-R、Type 17 的标题只能进入 140 × 136vp 内容区；Type 12、Type 14 不设置标题区。
- 不要把标题高度固定为 20vp，也不要照抄 HTML 参考图中的 `top={24}`。
- 顶层 Type 12 不包含 Action，不得向其上下二分骨架追加按钮。
- Type 13 不得把左右父区误当成一个跨区画布。两个父区均使用背板，中间间距为 12vp；每个父区内部安全区为 118 × 112vp，纵向主要模块间距为 6vp。

### 5.3 Action 与按钮错误

- 不要在 2×4 中使用 `CircleButton`。只有一个 Action 时通常使用单 `PillButton`；Type 17 是固定的 `CardButton` 例外。
- 不要让 `PillButton` 或 `CardButton` 横跨 296vp 安全内容区；任何按钮都必须限制在左或右半卡宽父区内。
- 不要在 Type 15／Type 15-R 的固定侧槽列中纵向堆叠两个 `PillButton`。Type 13 的 Type 15 参考子布局仅限同一父区中存在 118 × 28vp 紧凑内容，且两个 Action 都直接服务该内容的场景。
- `CardButton` 只能填入对应的 144 × 64vp 固定槽，不得自行改变父槽尺寸或跨槽排布。

### 5.4 固定槽、尺寸与间距错误

- Type 14 必须完整保留四个 144 × 64vp 固定槽；不得留空、隐藏、占位、合并或改成动态高度。混用时同类组件必须进入同一列并按上→下排列。
- Type 15、Type 15-R 的每个 144 × 64vp 固定槽只能放一个 `CardButton` 或 `InfoBlock`；不得合并槽位、跨槽排布或改变槽位尺寸。
- Type 15、Type 15-R 使用 12vp 左右间距，固定侧槽之间使用 8vp 纵向间距；不要混用这两个间距。
- Type 17 只保留一个右下 144 × 64vp 固定槽；不要生成右上空槽或使用 `Stack` 模拟占位。
- 不要让整宽业务组件在 `align="flex-start"` 的父层中按内容宽度收缩。

### 5.5 背板与 Runtime 错误

- Type 13 左右父区都必须使用 `surface="backplate"`，不得生成透明或单侧背板变体。
- `surface="backplate"` 只属于父内容区；子布局内部模块不得继承或重复生成背板颜色。
- 不要通过 `style`、`className`、硬编码颜色或未知 Props 增加 runtime 未公开的 Panel 外观。
- `CardButton`、`InfoBlock`、`PillButton` 的尺寸由外层槽位和 runtime 负责，不得向业务组件传入未知的尺寸、圆角或定位 Props。
