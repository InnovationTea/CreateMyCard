# 2×2 卡片布局规范

本文档是 2×2 卡片布局的生成依据。设计参数以 `human/layout_patterns_0828.html` 为准；JSX 只使用 Design Runtime 公开的 `Card`、`Stack`、`Grid` 与业务组件 Props。

## 1. 画布约束

| 项目 | 规格 |
|---|---:|
| 卡片尺寸 | 160 × 160vp |
| 圆角 | 20vp |
| 四边安全边距 | 12vp |
| 安全内容区 | 136 × 136vp |

所有可见内容必须限制在 136 × 136vp 安全内容区内，不得侵入 12vp 安全边距。

横向紧凑信息还必须满足：

- 每项保留可理解的语义标签，例如“手机电量 68%”，不能只显示“68%”。
- `Summary` 的 `content` 与 `items` 模式会根据父容器宽度自然换行；布局必须为实际换行高度预留空间，避免与相邻内容或操作区重叠。

## 2. 基础框架

2×2 布局分为“有标题”和“无标题”两类，不假设每张卡都有固定高度的标题槽。

| 区域 | 必要性 | 尺寸 / 弹性 | 布局规则 |
|---|---|---|---|
| 标题区 | 按 Type 必选 | `flex0; height:auto` | 宽度占满 136vp；高度由标题组件实际撑开，不参与剩余空间分配 |
| 标题 Icon | 按标题组件选用 | 20 × 20vp | 锚定标题区右上角；标题区高度取文字组与 Icon 实际高度的较大值 |
| 内容区 | 必选 | 通常为 `flex1` | 必须继续说明是高度自适应、宽度自适应或宽高均自适应 |
| PillButton 区 | 按 Type 必选 / 可选 | `flex0`; 136 × 36vp | 只能用于 2×2 的底部整宽操作槽；默认设计圆角 18vp，Type 10-C 为 40vp |
| CircleButton 区 | 按 Type 必选 | `flex0`; 36 × 36vp | Icon 20 × 20vp，不显示文字，由外层布局锚定安全内容区右下角 |
| 标题与下方内容间距 | 有标题布局必选 | 8vp | 从标题区实际底部开始计算 |
| 其他主要区域间距 | 按 Type 必选 | 8vp | 用于同级内容区、内容组与按钮、次要信息与 CircleButton；可选区域不存在时同时移除其占位和相邻间距 |
| 紧密关联的主次信息间距 | Type 10-B | 2vp | 只用于同一内容组内 Hero 与次要信息 |

标题参考高度：

- `SingleLineTitle` 文本高 18vp；带 20vp Icon 时标题区通常为 20vp。
- `DoubleLineTitle` 含一行副信息时约为 `19 + 4 + 18 = 41vp`；副信息为两行时继续自然增高。
- 参考高度只用于容量判断。JSX 必须使用自然高度，不得把参考高度写成固定 `top` 或固定标题槽高度。
- Type 0、Type 3、Type 6、Type 12、Type 15 为无标题布局。

## 3. 布局选择逻辑

布局由三部分组合：

`Base Pattern + Placement + Button Type`

- `Base Pattern`：单内容、上下二分、纵向三段、主次分层、局部双列或 2×2 网格。
- `Placement`：`flow` 顺序流式，或 `anchor` 固定边缘关系。
- `Button Type`：`none`、`PillButton` 或 `CircleButton`。

先根据信息层级选择基础骨架，再决定流式或锚点落位，最后选择操作区。局部双列和网格只能嵌套在所属内容区内，不能与整卡 Type 混为同一层级。

### 3.1 2×2 按钮限制

- 2×2 只允许 `PillButton` 和 `CircleButton`
- 有文字的整宽操作使用 `PillButton`
- 只有 Icon 且语义可由 `ariaLabel` 完整说明的右下快捷操作使用 `CircleButton`
- 同一 action 只能生成一个按钮，禁止同时用 `PillButton` 和 `CircleButton` 表示同一个 action
- 有两个 action 时全部使用 PillButton，使用 Type 10-C 或 Type 15，上下排列，禁止 `CircleButton` 加 `PillButton`

### 3.2 模块数与 Type

| 完整态顶层模块数 | Type |
|---:|---|
| 1 | Type 0 |
| 2 | Type 1、Type 3 |
| 3 | Type 2、Type 10-A、Type 12、Type 14、Type 15 |
| 4 | Type 6、Type 10-B、Type 10-C、Type 11-A |

统计口径：

- 有标题布局的标题区计 1 个顶层模块；无标题布局不计标题模块。
- 每个独立内容槽和操作槽各计 1 个。内容槽内部的业务组件不改变整卡 Type 的模块数。
- 带可选按钮的 Type 按完整态计数；按钮缺省时 Type 身份不变，可见模块数减 1。

## 4. 内容骨架

下表中 `T` 表示标题区实际高度，所有公式单位均为 vp。

| Type | 骨架 | 顶层模块弹性 | 尺寸与闭合公式 | 适用场景 / 特殊规则 |
|---|---|---|---|---|
| Type 0 | 无标题 + 单模块 | 单模块 `flex0` | 136 × 136 | 单内容、单图表、单功能；内容水平和垂直居中 |
| Type 1 | 标题 + 单内容 | 标题 `flex0`；内容 `flex1`、高度自适应 | 内容高 `136 − T − 8` | 内容从标题实际底部 + 8vp 开始，填满剩余高度 |
| Type 3 | 无标题 + 上下二分 | 上下区均 `flex0` | `64 + 8 + 64 = 136`；每区 136 × 64 | 双图表信息、双功能操作；实际骨架是纵向上下二分 |
| Type 2 | 标题 + 核心 + 明细 | 标题 `flex0`；两内容区均 `flex1`、高度自适应 | 单区高 `(136 − T − 8 − 8) ÷ 2` | 标题、核心、明细相邻间距均为 8vp；两个内容区默认等分剩余高度 |
| Type 10-A | 标题 + 单内容 + 可选 PillButton | 内容 `flex1`；按钮 `flex0` | 有按钮：内容高 `136 − T − 8 − 8 − 36`；无按钮：`136 − T − 8` | 按钮缺省时同时移除按钮槽及其相邻 8vp |
| Type 12 | 无标题 + 上方双列 + 可选 PillButton | 双列与按钮均 `flex0` | 完整态：双列各 64 × 92，`64 + 8 + 64 = 136`，`92 + 8 + 36 = 136` | 两个同级对象与一个整宽操作；无按钮时双列内容可占满 136vp 高度 |
| Type 14 | 标题 + 正文 + 右下 CircleButton | 正文 `flex1`；Action `flex0` | 正文宽 92；Action 36 × 36；`92 + 8 + 36 = 136`；正文高 `136 − T − 8` | `Layer + Anchor`；Action 锚定安全内容区右下角 |
| Type 15 | 无标题内容 + 两个 PillButton | 三个模块均 `flex0` | `48 + 8 + 36 + 8 + 36 = 136` | 内容区 136 × 48；两个整宽 Action 均必选 |
| Type 10-B | 标题 + Hero + 次要信息 + 可选 PillButton | 内容组 `flex1`；Hero/次要信息自然高度；按钮 `flex0` | 标题与内容组 8；Hero 与次要信息 2；内容组与按钮 8 | Hero 与次要信息按内容自然撑高，不等分、不写死高度 |
| Type 10-C | 标题 + 内容 + 两个 PillButton | 内容 `flex1`；两个 Action `flex0` | 内容高 `136 − T − 8 − 8 − 36 − 8 − 36 = 40 − T` | 相邻顶层区域均为 8vp；两个 Action 均必选 |
| Type 11-A | 标题 + Hero + 左下次要信息 + 右下 CircleButton | Hero `flex1`；次要信息宽度固定、高度自然；Action `flex0` | 标题下方高 `136 − T − 8`；底部 `92 + 8 + 36 = 136` | 次要信息可向上扩展，但必须与 Hero 保持至少 8vp |
| Type 6 | 无标题 + 2×2 四宫格 | 四模块均 `flex0` | `(136 − 8) ÷ 2 = 64`；每格 64 × 64，行列间距均为 8 | 四个同级且可独立识别的内容或操作 |

## 5. 操作区

| 类型 | 尺寸 | 位置 | 内容要求 | 适用 Type |
|---|---:|---|---|---|
| PillButton | 136 × 36vp；设计默认圆角 18vp | 底部整宽操作槽 | 文字必选，20vp Icon 可选 | Type 10-A、Type 10-B、Type 12 |
| 双 PillButton | 每个 136 × 36vp | 底部上下排列 | 两个 Action 均必选，垂直间距 8vp | Type 10-C、Type 15 |
| CircleButton | 36 × 36vp 圆形槽 | 安全内容区右下角 | 20vp Icon 必选，不显示文字，`ariaLabel` 必选 | Type 14、Type 11-A |
| None | — | — | 不保留操作槽及其相邻间距 | Type 0、Type 1、Type 2、Type 3、Type 6 |

按钮颜色、背板和交互状态遵循 Design System；本文件只规定按钮槽位与其他模块的几何关系。圆角属于组件视觉规范，不生成未知的 `radius` Prop。

## 6. 尺寸与实现规则

- 标题区统一使用 `flex0; height:auto`；下方内容从标题区实际底部 + 8vp 开始。
- `flex0` 表示模块不参与剩余空间分配；`flex1` 表示至少一个方向使用剩余空间。
- 每个 `flex1` 模块必须继续标明自适应方向；JSX 通常使用 `flex={1} minHeight={0}`。
- 等分公式：`单块尺寸 = (可分配尺寸 − gap 总和) ÷ 区块数`。
- 独立主要区域之间使用 8vp；只有 Type 10-B 内容组内部的 Hero 与次要信息使用 2vp。
- 可选区域不存在时，必须同时移除其槽位和相邻间距，不生成空 `Stack` 占位。
- 标题增高时先压缩弹性内容区。如果剩余空间小于业务组件最小占位，应更换 Type、减少内容或停止并报告，不得依赖裁剪或溢出。
- 整宽组件必须占满所属模块宽度；包裹层使用 `width="full" minWidth={0}`，不得因父层对齐方式而按内容收缩。
- 产品尺寸使用 vp；HTML 骨架预览可使用同数值 px 做 1:1 校核。

## 7. 标准 JSX 布局模板

本节只表达槽位和几何关系。业务组件可以替换，但不得改变所属 Type 的区域数量、间距和弹性。核心 API 见 [`../core.md`](../core.md)，组件 Props 与绑定规则见 [`../components/components_common.md`](../components/components_common.md) 和 [`../components/components_2x2.md`](../components/components_2x2.md)。

共同规则：

- 根节点固定为 `<Card size="2x2">`；默认 `padding={12}` 得到 136 × 136vp 安全内容区。
- 标题槽使用自然高度，不使用 `basis={12}` 或其他固定标题高度。
- 有标题 Type 必须显式保留 8vp 标题后间距。
- 主内容区通常使用 `flex={1} minHeight={0}`。
- 需要 Card 语义配色的业务组件传入 `appearance="card"`。
- 模板禁止 `style`、`className`、spread Props 和硬编码颜色。
- 示例中的 `dataIds` 与 `actionId` 只说明绑定位置；实际生成必须换成输入中真实存在的 ID。

### 7.1 Type 0：无标题单模块居中

```jsx
<Card size="2x2" appearance="blue-soft">
  <Stack width="full" height="full" align="center" justify="center">
    {/* 单一核心组件 */}
  </Stack>
</Card>
```

### 7.2 Type 1：标题 + 单内容

```jsx
<Card size="2x2" appearance="blue-soft" gap={8}>
  <Stack flex={0}>
    <SingleLineTitle title="今日天气" />
  </Stack>

  <Stack flex={1} minHeight={0} align="flex-start" justify="start">
    {/* 单主体内容 */}
  </Stack>
</Card>
```

### 7.3 Type 3：无标题上下二分

```jsx
<Card size="2x2" appearance="purple-gradient" gap={8}>
  <Stack basis={64} height={64}>
    {/* 上区域 */}
  </Stack>

  <Stack basis={64} height={64}>
    {/* 下区域 */}
  </Stack>
</Card>
```

### 7.4 Type 2：标题 + 等分核心 / 明细

```jsx
<Card size="2x2" appearance="green-soft" gap={8}>
  <Stack flex={0}>
    <SingleLineTitle title="今日状态" />
  </Stack>

  <Stack flex={1} minHeight={0} gap={8}>
    <Stack flex={1} minHeight={0}>
      {/* 核心内容 */}
    </Stack>

    <Stack flex={1} minHeight={0}>
      {/* 独立明细 */}
    </Stack>
  </Stack>
</Card>
```

### 7.5 Type 10-A：标题 + 单内容 + 可选 PillButton

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

按钮缺省时必须同时移除最后一个 `Stack` 及其相邻 gap。

### 7.6 Type 12：无标题双列 + 可选 PillButton

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

### 7.7 Type 14：标题 + 正文 + 右下 CircleButton

```jsx
<Card size="2x2" appearance="slate-gradient" gap={8}>
  <Stack flex={0}>
    <SingleLineTitle title="叫车出行" />
  </Stack>

  <Stack flex={1} minHeight={0} width="full" position="relative">
    <Stack position="absolute" left={0} top={0} bottom={0} width={92} minWidth={0}>
      {/* 正文 */}
    </Stack>

    <Stack position="absolute" right={0} bottom={0} width={36} height={36} align="center" justify="center">
      <CircleButton
        icon="phone_fill.svg"
        ariaLabel="拨打电话"
        appearance="card"
        actionId="phone.call"
      />
    </Stack>
  </Stack>
</Card>
```

`CircleButton` 自身不负责定位；`right={0}`、`bottom={0}` 属于外层 `Stack`。

### 7.8 Type 15：无标题内容 + 两个 PillButton

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

### 7.9 Type 10-B：标题 + Hero + 次要信息 + 可选 PillButton

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

### 7.10 Type 10-C：标题 + 内容 + 两个 PillButton

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

### 7.11 Type 11-A：标题 + Hero + 左下次要信息 + 右下 CircleButton

```jsx
<Card size="2x2" appearance="blue-soft" gap={8}>
  <Stack flex={0}>
    <SingleLineTitle title="设备状态" />
  </Stack>

  <Stack flex={1} minHeight={0} width="full" minWidth={0} gap={8}>
    <Stack flex={1} minHeight={0} width="full" minWidth={0}>
      {/* Hero */}
    </Stack>

    <Stack direction="row" width="full" minWidth={0} minHeight={36} gap={8} align="flex-end">
      <Stack width={92} minWidth={0}>
        {/* Summary / SecondaryBody 等次要信息 */}
      </Stack>

      <Stack width={36} height={36} align="center" justify="center">
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

### 7.12 Type 6：无标题四宫格

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

## 8. 常见错误

- 不要固定标题槽高度；标题必须按实际内容自然撑高。
- 不要在标题与下方内容之间继续使用旧版 2vp；0828 规范统一为 8vp。
- 不要把 `CardButton` 放入 2×2；2×2 只允许 `PillButton` 和 `CircleButton`。
- 不要把 `position`、`right`、`bottom` 传给 `CircleButton`；定位属于外层 `Stack`。
- Type 14 和 Type 11-A 的操作槽暂按当前 runtime 使用 36 × 36vp，正文 / 次要信息宽度为 92vp，满足 `92 + 8 + 36 = 136`。
- `CircleButton` 没有可用 Icon 或 action 需要显示文字时，改用带底部 `PillButton` 的 Type，不得将 `PillButton` 塞进右下圆形操作槽。
- 安全内容区内使用 `right={0}`、`bottom={0}`；`Card` 已提供 12vp padding，不要重复写 12。
- 不要同时用父级 `gap` 和空白 `Stack` 表示同一段间距。
- 不要让整宽组件在 `align="flex-start"` 的父容器内按内容宽度收缩。
- Type 10-C 和带 `DoubleLineTitle` 的布局必须先计算剩余高度；不足以容纳业务组件时不得生成。

## 9. 临时实现差异

0828 设计稿将 `CircleButton` 定义为 40 × 40vp；当前 runtime 的按钮自身为 36 × 36px。为了保证文档示例可以直接由当前 runtime 复现，本文件暂时统一使用 36 × 36vp，并将相邻内容区设为 92vp。后续 runtime 升级为 40 × 40px 时，应同步恢复为 `88 + 8 + 40 = 136vp`。
