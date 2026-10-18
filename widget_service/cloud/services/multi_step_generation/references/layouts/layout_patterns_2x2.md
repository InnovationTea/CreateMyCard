# 2×2 卡片布局规范

## 1. 画布约束

| 项目 | 规格 |
|---|---:|
| 卡片尺寸 | 150 × 150vp |
| 圆角 | 20vp |
| 四边安全边距 | 12vp |
| 安全内容区 | 126 × 126vp |

所有可见内容必须限制在 126 × 126vp 安全内容区内，不得侵入 12vp 安全边距。

### 1.1 基础框架

2×2 布局分为“有标题”和“无标题”两类，不假设每张卡都有固定高度的标题槽。

| 区域 | 必要性 | 尺寸 / 弹性 | 布局规则 |
|---|---|---|---|
| 标题区 | 按布局必选 | `flex0; height:auto` | 宽度占满 126vp；高度由标题组件实际撑开，不参与剩余空间分配 |
| 内容区 | 必选 | 通常为 `flex1` | 必须继续说明是高度自适应、宽度自适应或宽高均自适应 |
| PillButton 区 | 按布局必选或可选 | `flex0`; 126 × 36vp | 只能用于 2×2 的底部整宽操作槽；“标题内容单按钮”“标题主次内容单按钮”必选一个，“标题双列内容可选按钮”可选一个，“紧凑内容双按钮”必选两个；runtime 圆角固定为 30vp |
| CircleButton 区 | 所属布局必选 | `flex0`; 操作槽 40 × 40vp | 槽内居中放置 runtime 的 36 × 36vp `CircleButton`；Icon 20 × 20vp，不显示文字，由外层布局锚定安全内容区右下角 |
| 标题与下方内容间距 | 有标题布局必选 | 6vp | 从标题区实际底部开始计算；“标题单内容”“标题双内容”“标题内容单按钮”“标题主次内容单按钮”“标题锚点内容”“标题双列内容可选按钮”统一使用此值 |
| 其他主要区域间距 | 按布局必选 | 8vp | 用于同级内容区、内容组与按钮、次要信息与 CircleButton；可选区域不存在时同时移除其占位和相邻间距 |
| 紧密关联的主次信息间距 | 标题主次内容单按钮 | 2vp | 只用于同一内容组内 Hero 与次要信息 |

## 2. 布局选择逻辑

布局由三部分组合：

`Base Pattern + Placement + Action Component`

- `Base Pattern`：单内容、上下二分、纵向三段、主次分层、局部双列或 2×2 网格。
- `Placement`：`flow` 顺序流式，或 `anchor` 固定边缘关系。
- `Action Component`：`none`、`PillButton` 或 `CircleButton`。

先根据信息层级选择基础骨架，再决定流式或锚点落位，最后选择操作区。局部双列和网格只能嵌套在所属内容区内，不能与整卡布局混为同一层级。

### 2.1 布局选择总表

| 信息层级 / 关系 | 标题 | Placement | Action | 布局 | 选择条件 / 特殊规则 |
|---|---|---|---|---|---|
| 单层：一个 Data Display 内容 | 无 | `flow` | 无 | 核心居中 | 仅允许 Design System 中归类为 Data Display 的组件，并在安全内容区内水平、垂直居中 |
| 单层：一个主体内容 | 必选 | `flow` | 无 | 标题单内容 | 内容从标题实际底部 + 6vp 开始并填满剩余高度，左对齐且底端对齐 |
| 同级：上下两个 `InfoBlock` | 无 | `flow` | 无 | 双信息块 | 卡片改用 8vp 安全边距；两个必选 `InfoBlock` 使用 134 × 63vp 固定槽位，不得替换、合并或缺省 |
| 主次：核心内容 + 独立明细 | 必选 | `flow` | 无 | 标题双内容 | 两区默认等分剩余高度；核心区左上对齐，明细区左下对齐 |
| 同级：四个可独立识别的内容 | 无 | `flow` | 无 | 内容四宫格 | 内容区内部使用 2×2 四宫格，不放置操作按钮 |
| 单层：一个主体内容 | 必选 | `flow` | 1 个 `PillButton` | 标题内容单按钮 | 使用底部整宽按钮；没有 Action 时改用“标题单内容” |
| 主次：Hero 主要信息 + 紧密关联的次要信息 | 必选 | `flow` | 1 个 `PillButton` | 标题主次内容单按钮 | Hero 与次要信息按内容自然撑高、不等分；底部按钮必选 |
| 同级：两个占比对象横向并列 | 必选 | `flow` | 可选 1 个 `PillButton` | 标题双列内容可选按钮 | 单行标题下放两个 59vp 固定宽度 `ProgressCircle size="sm"` 内容列；底部按钮随 Action 可选 |
| 主次：Hero 主要信息 + 左下次要信息 | 必选 | `anchor` | 1 个 `CircleButton` | 标题锚点内容 | 次要信息可向上扩展，但必须与 Hero 保持至少 8vp |
| 单层：一个紧凑内容 | 无 | `flow` | 2 个 `PillButton` | 紧凑内容双按钮 | 内容区固定为 126 × 38vp，两个整宽 Action 均必选 |

### 2.2 根据 Action 确认操作区

- 先按真实内容高度检查底部空间。标题和必需内容完整呈现后，若仍可闭合出内容与按钮之间的 `8vp` 间距及 `126 × 36vp` 底部操作槽，必须优先选择带可见操作文本的 `PillButton`，并改用“标题内容单按钮”“标题主次内容单按钮”或其他提供底部整宽操作槽的兼容布局。
- 只有底部 `126 × 36vp` 操作槽确实无法与必需内容共同容纳、右下 `40 × 40vp` 操作槽可以安全避让正文，并且操作仅靠 Icon 也能明确表达时，才使用 `CircleButton`；完整操作名称写入 `ariaLabel`。
- 有两个 action 时全部使用 PillButton，使用“紧凑内容双按钮”，上下排列，禁止 `CircleButton` 加 `PillButton`。

## 3. 布局实现与JSX写法

以下公式中的 `T` 表示标题区实际高度，所有公式单位均为 vp。

标题参考高度：

- `SingleLineTitle` 的 title 行高为 16vp。
- `DoubleLineTitle` 的标题行按 16vp 计算；副信息按组件自身行盒自然撑高。
- 参考高度只用于容量判断。JSX 必须使用自然高度，不得把参考高度写成固定 `top` 或固定标题槽高度。

本节只表达槽位和几何关系。业务组件可以替换，但不得改变所属布局的区域数量、间距和弹性。核心 API 见 [`../core.md`](../core.md)，组件 Props 与绑定规则见 [`../components/components_common.md`](../components/components_common.md) 和 [`../components/components_2x2.md`](../components/components_2x2.md)。

通用规则：

- 根节点固定为 `<Card direction="column" size="2x2">`；默认 `padding={12}` 得到 126 × 126vp 安全内容区。
- 标题区统一使用 `flex0; height:auto`；所有带标题布局的下方第一个内容区都从标题区实际底部 + 6vp 开始。
- `flex0` 表示模块不参与剩余空间分配；`flex1` 表示至少一个方向使用剩余空间。
- 每个 `flex1` 模块必须继续标明自适应方向；JSX 使用 `flex={1}`，runtime 自动提供纵向收缩所需的 `minHeight:0`。
- 等分公式：`单块尺寸 = (可分配尺寸 − gap 总和) ÷ 区块数`。
- 独立主要区域之间使用 8vp；只有“标题主次内容单按钮”的内容组内部 Hero 与次要信息使用 2vp。
- “标题内容单按钮”和“标题主次内容单按钮”的内容区必须从标题下方的可用区域左上角开始排布；内容区外层 `Stack` 必须显式设置 `align="flex-start"` 与 `justify="flex-start"`。禁止使用 `align="center"`、`justify="center"`、`justify="flex-end"` 或 `justify="space-between"` 改变内容起点；剩余高度保留在内容下方。
- 可选区域不存在时，必须同时移除其槽位和相邻间距，不生成空 `Stack` 占位。
- 标题增高时先压缩弹性内容区。如果剩余空间小于业务组件最小占位，应更换布局、减少内容或停止并报告，不得依赖裁剪或溢出。
- 整宽组件必须占满所属模块宽度；包裹层使用 `width="full"`，不得因父层对齐方式而按内容收缩。
- 普通内容区只允许纵向组织业务组件，禁止在一个内容区内使用 `direction="row"` 的 `Stack` 横向并排两个或更多业务组件。标题区不属于内容区，不参与这项横向校验；标题与至多一个 `Badge` 仍按组件文档组成合法横向标题组。需要表达两个业务组件时，必须改为文档已有的纵向主次／双内容结构。内容区仅有两个明确例外：“标题双列内容可选按钮”按规定横向放置两个 59vp `ProgressCircle` 内容列；“标题锚点内容”按规定使用左下次要信息区与右下 `CircleButton` 的 `78 + 8 + 40vp` 横向底部行。不得仿照这两个例外并排其他组件。
- 产品尺寸使用 vp；HTML 骨架预览可使用同数值 px 做 1:1 校核。
- 2×2 只允许 `PillButton` 和 `CircleButton`。
- 同一 action 只能生成一个按钮，禁止同时用 `PillButton` 和 `CircleButton` 表示同一个 action。
- 按钮颜色、背板和交互状态遵循 Design System；本文件只规定按钮槽位与其他模块的几何关系。圆角属于组件视觉规范，不生成未知的 `radius` Prop。
- 需要 Card 语义配色的业务组件传入 `appearance="card"`。
- 模板禁止 `style`、`className`、spread Props 和硬编码颜色。
- 示例中的 `dataIds` 与 `actionId` 只说明绑定位置；实际生成必须换成输入中真实存在的 ID。

### 3.1 核心居中

尺寸与闭合：126 × 126vp。
操作区：无；不保留操作槽及其相邻间距。
内容对齐：仅允许放置 Design System 中归类为 Data Display 的组件，组件在模块内水平、垂直居中；不得混入标题、按钮或其他类型组件。

```jsx
<Card direction="column" size="2x2" appearance="orb-orange">
  <Stack direction="column" width="full" height="full" align="center" justify="center">
    {/* 单一 Data Display 组件 */}
  </Stack>
</Card>
```

### 3.2 标题单内容

尺寸与闭合：内容高 `126 − T − 6`。
操作区：无；不保留操作槽及其相邻间距。
内容对齐：内容区左对齐且底端对齐，显示使用`align="flex-start" justify="flex-end"`。

```jsx
<Card direction="column" size="2x2" appearance="solid-blue" gap={6}>
  <Stack direction="column" flex={0}>
    <SingleLineTitle title="今日天气" />
  </Stack>

  <Stack direction="column" flex={1} align="flex-start" justify="flex-end">
    {/* 单主体内容 */}
  </Stack>
</Card>
```

### 3.3 双信息块

尺寸与闭合：该布局单独使用 8vp 卡片安全边距，内容区为 134 × 134vp；`63 + 8 + 63 = 134`，每区 134 × 63vp。
操作区：无；不保留操作槽及其相邻间距。
内容限制：两个槽位均为必选的 `InfoBlock` 固定槽位，只允许放置 `InfoBlock`，不得替换为其他组件、合并或缺省。

```jsx
<Card direction="column" size="2x2" appearance="orb-purple" padding={8} gap={8}>
  <Stack direction="column" flex={0} width="full" height={63}>
    {/* 上方 InfoBlock */}
  </Stack>

  <Stack direction="column" flex={0} width="full" height={63}>
    {/* 下方 InfoBlock */}
  </Stack>
</Card>
```

### 3.4 标题双内容

尺寸与闭合：每个内容区高 `(126 − T − 6 − 8) ÷ 2`。
操作区：无；不保留操作槽及其相邻间距。
内容对齐：核心区左对齐且顶端对齐；明细区左对齐且底端对齐。

```jsx
<Card direction="column" size="2x2" appearance="solid-green" gap={6}>
  <Stack direction="column" flex={0}>
    <SingleLineTitle title="今日状态" />
  </Stack>

  <Stack direction="column" flex={1} gap={8}>
    <Stack direction="column" flex={1} align="flex-start" justify="flex-start">
      {/* 核心内容 */}
    </Stack>

    <Stack direction="column" flex={1} align="flex-start" justify="flex-end">
      {/* 独立明细 */}
    </Stack>
  </Stack>
</Card>
```

### 3.5 内容四宫格

尺寸与闭合：`(126 − 8) ÷ 2 = 59`；每格 59 × 59vp，行列间距均为 8vp。
操作区：无；不保留操作槽及其相邻间距。

```jsx
<Card direction="column" size="2x2" appearance="orb-orange">
  <Grid columns={2} rows="59px 59px" gap={8} width="full" height="full">
    <Stack direction="column" align="center" justify="center">{/* A */}</Stack>
    <Stack direction="column" align="center" justify="center">{/* B */}</Stack>
    <Stack direction="column" align="center" justify="center">{/* C */}</Stack>
    <Stack direction="column" align="center" justify="center">{/* D */}</Stack>
  </Grid>
</Card>
```

### 3.6 标题内容单按钮

尺寸与闭合：内容区高 `126 − T − 6 − 8 − 36`。
操作区：必选底部整宽 `PillButton`，槽位为 126 × 36vp，runtime 圆角为 30vp；文字必选，20vp Icon 可选。没有 Action 时改用“标题单内容”。
内容对齐：内容区左对齐且顶端对齐，必须显式使用 `align="flex-start"`、`justify="flex-start"`；不得纵向居中或贴底。
实现方式：`Card gap={6}` 只表达标题与下方操作主体的间距；操作主体内部用 `gap={8}` 分隔内容区和按钮槽。标题、内容区均不再使用 `mb` 重复表达这两段间距。

```jsx
<Card direction="column" size="2x2" appearance="solid-green" gap={6}>
  <Stack direction="column" flex={0}>
    <SingleLineTitle title="内存优化" />
  </Stack>

  <Stack direction="column" flex={1} width="full" gap={8}>
    <Stack direction="column" flex={1} width="full" align="flex-start" justify="flex-start">
      <ProgressLine2
        currentValue={43.75}
        totalValue={100}
        value="4.5"
        unit="GB可用"
        mode="light"
        dataIds={{
          value: "memory.availableGB"
        }}
      />
    </Stack>

    <Stack direction="column" flex={0} height={36} width="full">
      <PillButton
        label="一键清理"
        appearance="card"
        actionId="memory.cleanNow"
      />
    </Stack>
  </Stack>
</Card>
```

### 3.7 标题主次内容单按钮

尺寸与闭合：标题与内容组间距为 6vp；Hero 与次要信息间距为 2vp；内容组与按钮间距为 8vp。
操作区：必选底部整宽 `PillButton`，槽位为 126 × 36vp，runtime 圆角为 30vp；文字必选，20vp Icon 可选。
内容对齐：内容组必须显式使用 `align="flex-start"`、`justify="flex-start"`，Hero 从内容区左上角开始，次要信息紧随其后；不得使用 `center`、`flex-end` 或 `space-between` 分配剩余高度。只有一个业务内容组件时，它仍然顶端对齐，并应重新检查是否更适合“标题内容单按钮”。
实现方式：`Card gap={6}` 只表达标题与下方操作主体的间距；操作主体内部用 `gap={8}` 分隔主次内容组和按钮槽，主次内容组内部继续使用 `gap={2}`。标题和内容组均不使用 `mb`。

```jsx
<Card direction="column" size="2x2" appearance="solid-blue" gap={6}>
  <Stack direction="column" flex={0}>
    <SingleLineTitle title="今日概览" />
  </Stack>

  <Stack direction="column" flex={1} width="full" gap={8}>
    <Stack direction="column" flex={1} width="full" gap={2} align="flex-start" justify="flex-start">
      <Stack direction="column" flex={0} width="full">
        {/* Hero 主要信息 */}
      </Stack>

      <Stack direction="column" flex={0} width="full">
        {/* 次要信息 */}
      </Stack>
    </Stack>

    <Stack direction="column" flex={0} height={36} width="full">
      <PillButton
        label="查看详情"
        appearance="card"
        actionId="detail.open"
      />
    </Stack>
  </Stack>
</Card>
```

### 3.8 标题双列内容可选按钮

标题区：必选一个自然高度的 `SingleLineTitle`；标题至内容间距固定为 6vp，不使用 `DoubleLineTitle`。
内容区：必选左右两个固定宽度、自适应高度的内容列，列宽均为 59vp、列间距为 8vp，满足 `59 + 8 + 59 = 126`。每列必须且只能承载一个 `ProgressCircle size="sm"`，不允许跨列。
操作区：有 Action 时在底部放一个整宽 `PillButton`，槽位固定为 126 × 36vp，内容行至按钮间距为 8vp；无 Action 时同时移除按钮槽及这段 8vp 间距。
尺寸与闭合：无按钮时内容行高度为 `126 − T − 6`；有按钮时内容行高度为 `126 − T − 6 − 8 − 36`。标题增高只压缩内容行，标题、按钮和固定间距不压缩。

```jsx
<Card direction="column" size="2x2" appearance="solid-blue" gap={0}>
  <Stack direction="column" flex={0} width="full" mb={6}>
    <SingleLineTitle title="设备状态" />
  </Stack>

  <Stack direction="row" flex={1} width="full" gap={8} mb={8}>
    <Stack direction="column" flex={0} width={59} height="full">
      <ProgressCircle size="sm" value={80} label="左耳" />
    </Stack>

    <Stack direction="column" flex={0} width={59} height="full">
      <ProgressCircle size="sm" value={75} label="右耳" />
    </Stack>
  </Stack>

  <Stack direction="column" flex={0} height={36} width="full">
    <PillButton
      label="查看详情"
      appearance="card"
      actionId="detail.open"
    />
  </Stack>
</Card>
```

无 Action 变体删除最后一个按钮 `Stack`，并同时删除内容行的 `mb={8}`。

### 3.9 标题锚点内容

尺寸与闭合：标题下方可用高度 `126 − T − 6`；底部闭合校验为 `78 + 8 + 40 = 126`。
操作区：必选 40 × 40vp 操作槽，槽内居中放置 runtime 的 36 × 36vp `CircleButton`；操作槽锚定安全内容区右下角，必选 20vp Icon ，不显示文字，`ariaLabel` 必选。
内容对齐：Hero 从标题区实际底部 + 6vp 开始；次要信息左对齐并锚定左下角，内容增高时只能向上扩展，且与 Hero 保持至少 8vp，右侧与操作区保持 8vp。

```jsx
<Card direction="column" size="2x2" appearance="solid-blue" gap={6}>
  <Stack direction="column" flex={0}>
    <SingleLineTitle title="设备状态" />
  </Stack>

  <Stack direction="column" flex={1} width="full" gap={8}>
    <Stack direction="column" flex={1} width="full">
      {/* Hero */}
    </Stack>

    <Stack direction="row" width="full" minHeight={40} gap={8} align="flex-end">
      <Stack direction="column" width={78} align="flex-start" justify="flex-end">
        {/* SecondaryBody 等次要信息 */}
      </Stack>

      <Stack direction="column" width={40} height={40} align="center" justify="center">
        <CircleButton
          icon="phone_fill.svg"
          ariaLabel="快捷操作"
          appearance="card"
          actionId="action.quick"
        />
      </Stack>
    </Stack>
  </Stack>
</Card>
```

### 3.10 紧凑内容双按钮

尺寸与闭合：内容区为 126 × 38vp，显式使用 `align="flex-start"`、`justify="flex-start"`。内容区使用 `ProgressCircleSingle` 时，必须显式传入 `size="compact"`。
操作区：两个必选 `PillButton` 在底部上下排列，每个槽位为 126 × 36vp，垂直间距为 8vp。

```jsx
<Card direction="column" size="2x2" appearance="solid-blue" gap={8}>
  <Stack direction="column" flex={1} width="full" align="flex-start" justify="flex-start">
    {/* 使用 ProgressCircleSingle 时必须写 size="compact" */}
  </Stack>

  <Stack direction="column" flex={0} height={36} width="full">
    <PillButton label="操作一" appearance="card" actionId="action.first" />
  </Stack>

  <Stack direction="column" flex={0} height={36} width="full">
    <PillButton label="操作二" appearance="card" actionId="action.second" />
  </Stack>
</Card>
```


## 4. 常见错误

- 不要把 `position`、`right`、`bottom` 传给 `CircleButton`；定位属于外层 `Stack`。
- `CircleButton` 没有可用 Icon 或 action 需要显示文字时，改用带底部 `PillButton` 的布局，不得将 `PillButton` 塞进右下圆形操作槽。
- 安全内容区内使用 `right={0}`、`bottom={0}`；`Card` 已提供 12vp padding，不要重复写 12。圆形操作槽固定为 40 × 40vp。
- 不要同时用父级 `gap` 和空白 `Stack` 表示同一段间距。
- 不要让整宽组件在 `align="flex-start"` 的父容器内按内容宽度收缩。
- 带 `DoubleLineTitle` 的布局必须先计算剩余高度；不足以容纳业务组件时不得生成。
