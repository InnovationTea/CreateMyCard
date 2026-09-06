# 2×2 卡片布局规范

## 1. 画布约束

| 项目 | 规格 |
|---|---:|
| 卡片尺寸 | 160 × 160vp |
| 圆角 | 20vp |
| 四边安全边距 | 12vp |
| 安全内容区 | 136 × 136vp |

所有可见内容必须限制在 136 × 136vp 安全内容区内，不得侵入 12vp 安全边距。

### 1.1 基础框架

2×2 布局分为“有标题”和“无标题”两类，不假设每张卡都有固定高度的标题槽。

| 区域 | 必要性 | 尺寸 / 弹性 | 布局规则 |
|---|---|---|---|
| 标题区 | 按 Type 必选 | `flex0; height:auto` | 宽度占满 136vp；高度由标题组件实际撑开，不参与剩余空间分配 |
| 内容区 | 必选 | 通常为 `flex1` | 必须继续说明是高度自适应、宽度自适应或宽高均自适应 |
| PillButton 区 | 所属 Type 必选 | `flex0`; 136 × 36vp | 只能用于 2×2 的底部整宽操作槽；Type 10-A、Type 10-B、Type 12 使用一个，Type 10-C、Type 15 使用两个；runtime 圆角固定为 30vp |
| CircleButton 区 | 所属 Type 必选 | `flex0`; 操作槽 40 × 40vp | 槽内居中放置 runtime 的 36 × 36vp `CircleButton`；Icon 20 × 20vp，不显示文字，由外层布局锚定安全内容区右下角 |
| 标题与下方内容间距 | 有标题布局必选 | 8vp | 从标题区实际底部开始计算 |
| 其他主要区域间距 | 按 Type 必选 | 8vp | 用于同级内容区、内容组与按钮、次要信息与 CircleButton；可选区域不存在时同时移除其占位和相邻间距 |
| 紧密关联的主次信息间距 | Type 10-B | 2vp | 只用于同一内容组内 Hero 与次要信息 |

## 2. 布局选择逻辑

布局由三部分组合：

`Base Pattern + Placement + Button Type`

- `Base Pattern`：单内容、上下二分、纵向三段、主次分层、局部双列或 2×2 网格。
- `Placement`：`flow` 顺序流式，或 `anchor` 固定边缘关系。
- `Button Type`：`none`、`PillButton` 或 `CircleButton`。

先根据信息层级选择基础骨架，再决定流式或锚点落位，最后选择操作区。局部双列和网格只能嵌套在所属内容区内，不能与整卡 Type 混为同一层级。

### 2.1 Type 选择总表

| 信息层级 / 关系 | 标题 | Placement | Action | Type | 选择条件 / 特殊规则 |
|---|---|---|---|---|---|
| 单层：一个 Data Display 内容 | 无 | `flow` | 无 | Type 0 | 仅允许 Design System 中归类为 Data Display 的组件，并在安全内容区内水平、垂直居中 |
| 单层：一个主体内容 | 必选 | `flow` | 无 | Type 1 | 内容从标题实际底部 + 8vp 开始并填满剩余高度，左对齐且底端对齐 |
| 同级：上下两个 `InfoBlock` | 无 | `flow` | 无 | Type 3 | 两个必选 `InfoBlock` 使用 136 × 64vp 固定槽位，不得替换、合并或缺省 |
| 主次：核心内容 + 独立明细 | 必选 | `flow` | 无 | Type 2 | 两区默认等分剩余高度；核心区左上对齐，明细区左下对齐 |
| 同级：四个可独立识别的内容 | 无 | `flow` | 无 | Type 6 | 内容区内部使用 2×2 四宫格，不放置操作按钮 |
| 单层：一个主体内容 | 必选 | `flow` | 1 个 `PillButton` | Type 10-A | 使用底部整宽按钮；没有 Action 时改用 Type 1 |
| 主次：Hero 主要信息 + 紧密关联的次要信息 | 必选 | `flow` | 1 个 `PillButton` | Type 10-B | Hero 与次要信息按内容自然撑高、不等分；底部按钮必选 |
| 同级：两个对象横向并列 | 无 | `flow` | 1 个 `PillButton` | Type 12 | 两个 64 × 92vp 内容区横向并列，按钮位于底部且必选 |
| 单层：一个连续正文区域 | 必选 | `anchor` | 1 个 `CircleButton` | Type 14 | 正文固定使用左侧 88vp 宽度，Action 锚定右下角 |
| 主次：Hero 主要信息 + 左下次要信息 | 必选 | `anchor` | 1 个 `CircleButton` | Type 11-A | 次要信息可向上扩展，但必须与 Hero 保持至少 8vp |
| 单层：一个紧凑内容 | 无 | `flow` | 2 个 `PillButton` | Type 15 | 内容区固定为 136 × 48vp，两个整宽 Action 均必选 |
| 单层：一个紧凑内容 | 必选 | `flow` | 2 个 `PillButton` | Type 10-C | 标题和两个 Action 均必选；必须先确认剩余内容高度足够 |

### 2.2 根据 Action 确认操作区

- 先按真实内容高度检查底部空间。标题和必需内容完整呈现后，若仍可闭合出内容与按钮之间的 `8vp` 间距及 `136 × 36vp` 底部操作槽，必须优先选择带可见操作文本的 `PillButton`，并改用 Type 10-A、Type 10-B 或其他提供底部整宽操作槽的兼容 Type。
- 不得仅因 action 提供 Icon，或为了沿用 Type 14，而把本可放入底部的 `PillButton` 降级为 `CircleButton`。
- 只有底部 `136 × 36vp` 操作槽确实无法与必需内容共同容纳、右下 `40 × 40vp` 操作槽可以安全避让正文，并且操作仅靠 Icon 也能明确表达时，才使用 `CircleButton`；完整操作名称写入 `ariaLabel`。
- 有两个 action 时全部使用 PillButton，使用 Type 10-C 或 Type 15，上下排列，禁止 `CircleButton` 加 `PillButton`。

## 3. 布局实现与JSX写法

以下公式中的 `T` 表示标题区实际高度，所有公式单位均为 vp。

标题参考高度：

- `SingleLineTitle` 纯文本标题高度为 18vp。
- `DoubleLineTitle` 含一行副信息时为 `18 + 4 + 18 = 40vp`；副信息为两行时继续自然增高。
- 参考高度只用于容量判断。JSX 必须使用自然高度，不得把参考高度写成固定 `top` 或固定标题槽高度。

本节只表达槽位和几何关系。业务组件可以替换，但不得改变所属 Type 的区域数量、间距和弹性。核心 API 见 [`../core.md`](../core.md)，组件 Props 与绑定规则见 [`../components/components_common.md`](../components/components_common.md) 和 [`../components/components_2x2.md`](../components/components_2x2.md)。

通用规则：

- 根节点固定为 `<Card size="2x2">`；默认 `padding={12}` 得到 136 × 136vp 安全内容区。
- 标题区统一使用 `flex0; height:auto`；下方内容从标题区实际底部 + 8vp 开始。
- `flex0` 表示模块不参与剩余空间分配；`flex1` 表示至少一个方向使用剩余空间。
- 每个 `flex1` 模块必须继续标明自适应方向；JSX 通常使用 `flex={1} minHeight={0}`。
- 等分公式：`单块尺寸 = (可分配尺寸 − gap 总和) ÷ 区块数`。
- 独立主要区域之间使用 8vp；只有 Type 10-B 内容组内部的 Hero 与次要信息使用 2vp。
- 可选区域不存在时，必须同时移除其槽位和相邻间距，不生成空 `Stack` 占位。
- 标题增高时先压缩弹性内容区。如果剩余空间小于业务组件最小占位，应更换 Type、减少内容或停止并报告，不得依赖裁剪或溢出。
- 整宽组件必须占满所属模块宽度；包裹层使用 `width="full" minWidth={0}`，不得因父层对齐方式而按内容收缩。
- 产品尺寸使用 vp；HTML 骨架预览可使用同数值 px 做 1:1 校核。
- 2×2 只允许 `PillButton` 和 `CircleButton`。
- 同一 action 只能生成一个按钮，禁止同时用 `PillButton` 和 `CircleButton` 表示同一个 action。
- 按钮颜色、背板和交互状态遵循 Design System；本文件只规定按钮槽位与其他模块的几何关系。圆角属于组件视觉规范，不生成未知的 `radius` Prop。
- 需要 Card 语义配色的业务组件传入 `appearance="card"`。
- 模板禁止 `style`、`className`、spread Props 和硬编码颜色。
- 示例中的 `dataIds` 与 `actionId` 只说明绑定位置；实际生成必须换成输入中真实存在的 ID。

### 3.1 Type 0：无标题单模块居中

尺寸与闭合：136 × 136vp。
操作区：无；不保留操作槽及其相邻间距。
内容对齐：仅允许放置 Design System 中归类为 Data Display 的组件，组件在模块内水平、垂直居中；不得混入标题、按钮或其他类型组件。

```jsx
<Card size="2x2" appearance="type0-gradient">
  <Stack width="full" height="full" align="center" justify="center">
    {/* 单一 Data Display 组件 */}
  </Stack>
</Card>
```

### 3.2 Type 1：标题 + 单内容

尺寸与闭合：内容高 `136 − T − 8`。
操作区：无；不保留操作槽及其相邻间距。
内容对齐：内容区左对齐且底端对齐。

```jsx
<Card size="2x2" appearance="blue-soft" gap={8}>
  <Stack flex={0}>
    <SingleLineTitle title="今日天气" />
  </Stack>

  <Stack flex={1} minHeight={0} align="flex-start" justify="end">
    {/* 单主体内容 */}
  </Stack>
</Card>
```

### 3.3 Type 3：无标题上下双 InfoBlock

尺寸与闭合：`64 + 8 + 64 = 136`；每区 136 × 64vp。
操作区：无；不保留操作槽及其相邻间距。
内容限制：两个槽位均为必选的 `InfoBlock` 固定槽位，只允许放置 `InfoBlock`，不得替换为其他组件、合并或缺省。

```jsx
<Card size="2x2" appearance="purple-gradient" gap={8}>
  <Stack basis={64} height={64}>
    {/* 上方 InfoBlock */}
  </Stack>

  <Stack basis={64} height={64}>
    {/* 下方 InfoBlock */}
  </Stack>
</Card>
```

### 3.4 Type 2：标题 + 等分核心 / 明细

尺寸与闭合：单区高 `(136 − T − 8 − 8) ÷ 2`。
操作区：无；不保留操作槽及其相邻间距。
内容对齐：核心区左对齐且顶端对齐；明细区左对齐且底端对齐。

```jsx
<Card size="2x2" appearance="green-soft" gap={8}>
  <Stack flex={0}>
    <SingleLineTitle title="今日状态" />
  </Stack>

  <Stack flex={1} minHeight={0} gap={8}>
    <Stack flex={1} minHeight={0} align="flex-start" justify="start">
      {/* 核心内容 */}
    </Stack>

    <Stack flex={1} minHeight={0} align="flex-start" justify="end">
      {/* 独立明细 */}
    </Stack>
  </Stack>
</Card>
```

### 3.5 Type 6：无标题四宫格

尺寸与闭合：`(136 − 8) ÷ 2 = 64`；每格 64 × 64vp，行列间距均为 8vp。
操作区：无；不保留操作槽及其相邻间距。

```jsx
<Card size="2x2" appearance="orange-gradient">
  <Grid columns={2} rows="64px 64px" gap={8} width="full" height="full">
    <Stack align="center" justify="center">{/* A */}</Stack>
    <Stack align="center" justify="center">{/* B */}</Stack>
    <Stack align="center" justify="center">{/* C */}</Stack>
    <Stack align="center" justify="center">{/* D */}</Stack>
  </Grid>
</Card>
```

### 3.6 Type 10-A：标题 + 单内容 + PillButton

尺寸与闭合：内容高 `136 − T − 8 − 8 − 36`。
操作区：必选底部整宽 `PillButton`，槽位为 136 × 36vp，runtime 圆角为 30vp；文字必选，20vp Icon 可选。没有 Action 时改用 Type 1。

```jsx
<Card size="2x2" appearance="green-soft" gap={8}>
  <Stack flex={0}>
    <SingleLineTitle title="内存优化" />
  </Stack>

  <Stack flex={1} minHeight={0} width="full" minWidth={0} align="flex-start">
    <ProgressLine2
      currentValue={43.75}
      totalValue={100}
      value="4.5"
      unit="GB可用"
      mode="light"
      dataIds={{
        currentValue: "memory.usedPercent",
        value: "memory.availableGB"
      }}
    />
  </Stack>

  <Stack basis={36} height={36} width="full">
    <PillButton
      label="一键清理"
      appearance="card"
      actionId="memory.cleanNow"
    />
  </Stack>
</Card>
```

### 3.7 Type 10-B：标题 + Hero + 次要信息 + PillButton

尺寸与闭合：标题与内容组间距为 8vp；Hero 与次要信息间距为 2vp；内容组与按钮间距为 8vp。
操作区：必选底部整宽 `PillButton`，槽位为 136 × 36vp，runtime 圆角为 30vp；文字必选，20vp Icon 可选。

```jsx
<Card size="2x2" appearance="blue-soft" gap={8}>
  <Stack flex={0}>
    <SingleLineTitle title="今日概览" />
  </Stack>

  <Stack flex={1} minHeight={0} width="full" gap={2} justify="start">
    <Stack flex={0} width="full">
      {/* Hero 主要信息 */}
    </Stack>

    <Stack flex={0} width="full">
      {/* 次要信息 */}
    </Stack>
  </Stack>

  <Stack basis={36} height={36} width="full">
    <PillButton
      label="查看详情"
      appearance="card"
      actionId="detail.open"
    />
  </Stack>
</Card>
```

### 3.8 Type 12：无标题双列 + PillButton

尺寸与闭合：完整态双列各 64 × 92vp，`64 + 8 + 64 = 136`，`92 + 8 + 36 = 136`。
操作区：必选底部整宽 `PillButton`，槽位为 136 × 36vp，runtime 圆角为 30vp；文字必选，20vp Icon 可选。

```jsx
<Card size="2x2" appearance="blue-soft" gap={8}>
  <Stack direction="row" basis={92} height={92} width="full" gap={8}>
    <Stack basis={64} width={64} height="full">
      {/* 同级对象 A */}
    </Stack>

    <Stack basis={64} width={64} height="full">
      {/* 同级对象 B */}
    </Stack>
  </Stack>

  <Stack basis={36} height={36} width="full">
    <PillButton
      label="查看详情"
      appearance="card"
      actionId="detail.open"
    />
  </Stack>
</Card>
```

### 3.9 Type 14：标题 + 正文 + 右下 CircleButton

尺寸与闭合：标题下方正文画布高 `136 − T − 8`；正文宽 88vp；底部横向满足 `88 + 8 + 40 = 136`；Action 为 40 × 40vp。
操作区：必选 40 × 40vp 操作槽，槽内居中放置 runtime 的 36 × 36vp `CircleButton`；操作槽锚定安全内容区右下角，20vp Icon 必选，不显示文字，`ariaLabel` 必选。

Type 14 是分层锚点布局：
- `CircleButton` 自身不负责定位；`right={0}`、`bottom={0}` 属于外层 `Stack`。
- 正文从标题区实际底部 + 8vp 开始，固定占用左侧 88vp，并在剩余高度内自适应。
- Action 固定锚定安全内容区右下角；正文与 Action 保持 8vp 水平间距，不得依赖覆盖、裁剪或隐藏必需文字避让按钮。

```jsx
<Card size="2x2" appearance="blue-soft" gap={8}>
  <Stack flex={0}>
    <SingleLineTitle title="需求评审会" />
  </Stack>

  <Stack flex={1} minHeight={0} width="full" minWidth={0} position="relative">
    <Stack position="absolute" left={0} top={0} bottom={0} width={88} minWidth={0}>
      {/* 正文 */}
    </Stack>

    <Stack position="absolute" right={0} bottom={0} width={40} height={40} align="center" justify="center">
      <CircleButton
        icon="phone_fill.svg"
        ariaLabel="快捷操作"
        appearance="card"
        actionId="action.quick"
      />
    </Stack>
  </Stack>
</Card>
```

### 3.10 Type 11-A：标题 + Hero + 左下次要信息 + 右下 CircleButton

尺寸与闭合：标题下方高 `136 − T − 8`；底部 `88 + 8 + 40 = 136`。
操作区：必选 40 × 40vp 操作槽，槽内居中放置 runtime 的 36 × 36vp `CircleButton`；操作槽锚定安全内容区右下角，20vp Icon 必选，不显示文字，`ariaLabel` 必选。
内容对齐：Hero 从标题区实际底部 + 8vp 开始；次要信息左对齐并锚定左下角，内容增高时只能向上扩展，且与 Hero 保持至少 8vp。

```jsx
<Card size="2x2" appearance="blue-soft" gap={8}>
  <Stack flex={0}>
    <SingleLineTitle title="设备状态" />
  </Stack>

  <Stack flex={1} minHeight={0} width="full" minWidth={0} gap={8}>
    <Stack flex={1} minHeight={0} width="full" minWidth={0}>
      {/* Hero */}
    </Stack>

    <Stack direction="row" width="full" minWidth={0} minHeight={40} gap={8} align="flex-end">
      <Stack width={88} minWidth={0} align="flex-start" justify="end">
        {/* Summary / SecondaryBody 等次要信息 */}
      </Stack>

      <Stack width={40} height={40} align="center" justify="center">
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

### 3.11 Type 15：无标题内容 + 两个 PillButton

尺寸与闭合：`48 + 8 + 36 + 8 + 36 = 136`。
操作区：两个必选 `PillButton` 在底部上下排列，每个槽位为 136 × 36vp，垂直间距为 8vp。

```jsx
<Card size="2x2" appearance="neutral-soft" gap={8}>
  <Stack basis={48} height={48} width="full">
    {/* 内容区 */}
  </Stack>

  <Stack basis={36} height={36} width="full">
    <PillButton
      label="主要操作"
      appearance="card"
      actionId="action.primary"
    />
  </Stack>

  <Stack basis={36} height={36} width="full">
    <PillButton
      label="次要操作"
      appearance="card"
      actionId="action.secondary"
    />
  </Stack>
</Card>
```

### 3.12 Type 10-C：标题 + 内容 + 两个 PillButton

尺寸与闭合：内容高 `136 − T − 8 − 8 − 36 − 8 − 36 = 40 − T`。
操作区：两个必选 `PillButton` 在底部上下排列，每个槽位为 136 × 36vp，垂直间距为 8vp。

```jsx
<Card size="2x2" appearance="blue-soft" gap={8}>
  <Stack flex={0}>
    <SingleLineTitle title="设备控制" />
  </Stack>

  <Stack flex={1} minHeight={0} width="full">
    {/* 紧凑内容区 */}
  </Stack>

  <Stack basis={36} height={36} width="full">
    <PillButton label="操作一" appearance="card" actionId="action.first" />
  </Stack>

  <Stack basis={36} height={36} width="full">
    <PillButton label="操作二" appearance="card" actionId="action.second" />
  </Stack>
</Card>
```

该 Type 的内容空间非常有限。必须先按标题实际高度计算剩余高度；无法容纳业务组件时停止并报告，不得强行裁剪。

## 4. 常见错误

- 不要把 `position`、`right`、`bottom` 传给 `CircleButton`；定位属于外层 `Stack`。
- `CircleButton` 没有可用 Icon 或 action 需要显示文字时，改用带底部 `PillButton` 的 Type，不得将 `PillButton` 塞进右下圆形操作槽。
- 安全内容区内使用 `right={0}`、`bottom={0}`；`Card` 已提供 12vp padding，不要重复写 12。圆形操作槽固定为 40 × 40vp。
- 不要同时用父级 `gap` 和空白 `Stack` 表示同一段间距。
- 不要让整宽组件在 `align="flex-start"` 的父容器内按内容宽度收缩。
- Type 10-C 和带 `DoubleLineTitle` 的布局必须先计算剩余高度；不足以容纳业务组件时不得生成。
