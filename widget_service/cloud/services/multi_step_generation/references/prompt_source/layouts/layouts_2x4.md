---
name: phone-widget-layouts-2x4
description: 规定 2×4 父布局、内容区 variant、固定槽、容量、模板与检查；Card 和 Region 的通用接口见 core。
---

# 2×4 布局选择

布局只使用 `Card.layout` 和直属 `Region` 表达。固定宽高、间距、方向、对齐和弹性分配由语义布局名称确定，不写入 JSX。

## 1. 布局总表

### 1.1 父布局总表

| 类型 | 名称 | 内容结构 | 适用场景 | 容量与约束 |
|---|---|---|---|---|
| 父布局 | `top-bottom` | 标题 + 主体 + 同级明细 | 单一信息分区中的核心结论与并列属性 | 无 Action；明细为一个 `TextBlock` 或 `TopTextBottomValue` |
| 父布局 | `split-panels` | 左右两个内容区 | 两个可独立阅读的信息分区 | 每侧使用一个内容区变体；每侧至多 1 个直属 Action；至多一侧使用指定宽变体 |
| 父布局 | `main-right-double` | 主内容区 + 右侧两个固定模块 | 一个主要内容区，外加恰好两个紧凑信息或操作模块 | 右侧必须填满；只允许双操作、双信息、上信息下操作 |
| 父布局 | `four-blocks` | 四个同级固定模块 | 恰好四组层级相近、能够独立阅读的信息或操作 | 每槽一个 `InfoBlock` 或 `CardButton`；不得留空或补造内容 |

### 1.2 内容区变体总表

内容区只使用以下三个闭集。表中的“标题”“紧凑内容”和“宽内容”均逐字引用这些集合，不包含其他组件：

| 类型 | 名称 | 内容结构 | 适用场景 | 容量与约束 |
|---|---|---|---|---|
| 组件集合 | 标题单元 | 单个 `SingleLineTitle`／`DoubleLineTitle`，或“标题与数量”组件组合 | 带标题的内容区变体 | 每个标题位恰好 1 个标题单元 |
| 组件集合 | 紧凑内容 | `EmphasisText`、`EmphasizedData`、`EventCard`、`H_BarChart`、`NumericRatioStack`、`ProgressCircleSingle`、`ProgressLine2`、`SecondaryBody`、`TableText` | 所有 `compact-*` 通用内容位 | 每个内容位恰好 1 个；连续内容只允许一条短事件、两项短表格或双项短柱图，并且必须在当前变体中完整闭合；不包含 `TextBlock`、`InfoBlock`、`ProgressCircle` |
| 组件集合 | 宽内容 | 与紧凑内容使用相同组件类型，但允许其较高容量形态 | `wide-center`、`wide-title-content*`、`wide-title-primary-secondary*` 的通用内容位 | 每个内容位恰好 1 个；可承载 1–2 条事件、2–3 项柱图或更多短表格项；仍不包含 `TextBlock`、`InfoBlock`、`ProgressCircle` |
| 专用内容 | 核心居中 | `DataDisplay` | 仅 `compact-center` 或 `wide-center` | 作为唯一内容组件；不追加标题、明细或 Action |

| 类型 | 名称 | 内容结构 | 适用场景 | 容量与约束 |
|---|---|---|---|---|
| 紧凑变体 | `compact-center` | 紧凑内容 | 无标题也能理解的单一核心信息 | 子节点依次为：1 个紧凑内容；无 Action |
| 紧凑变体 | `compact-title-content` | 标题 + 紧凑内容 | 需要标题说明的单一内容 | 子节点依次为：标题、紧凑内容；无 Action |
| 紧凑变体 | `compact-title-primary-secondary` | 标题 + 紧凑内容 + 紧凑内容 | 同一分区的一项核心信息与一项补充 | 子节点依次为：标题、核心、明细；无 Action |
| 紧凑变体 | `compact-title-content-action` | 标题 + 紧凑内容 + 操作 | 一个内容模块及其直属 Action | 子节点依次为：标题、紧凑内容、`PillButton` |
| 宽变体 | `wide-center` | 宽内容 | 主内容区中的无标题核心信息 | 子节点为 1 个宽内容；无 Action |
| 宽变体 | `wide-title-content` | 标题 + 宽内容 | 主内容区中的单一主题内容 | 子节点依次为：标题、宽内容；无 Action |
| 宽变体 | `wide-title-content-action` | 标题 + 宽内容 + 操作 | 主内容区中的内容及直属 Action | 子节点依次为：标题、宽内容、`PillButton` |
| 宽变体 | `wide-title-double-progress` | 标题 + 双占比 + 可选操作 | 两个同级占比，可有共同 Action | 子节点依次为：标题、`ProgressCircle`、`ProgressCircle`；可追加 1 个 `PillButton` |
| 宽变体 | `wide-title-primary-secondary-action` | 标题 + 宽内容 + 宽内容 + 操作 | 核心、明细和直属 Action 都必须展示 | 子节点依次为：标题、核心、明细、`PillButton` |
| 宽变体 | `wide-title-primary-secondary` | 标题 + 宽内容 + 宽内容 | 同一分区的核心信息与相关明细 | 子节点依次为：标题、核心、明细；无 Action |
| 宽变体 | `wide-quad-progress` | 四占比网格 | 四个同级对象的占比 | 子节点恰好为 4 个 `ProgressCircle`；无标题、无 Action |

标题单元通常是一个标题组件；使用“标题与数量”时，JSX 中依次写标题组件和 `Badge`，两者共同占用一个横向标题单元。布局只规定该组合可占用标题位；是否应使用它由组件组合的触发条件决定。

## 2. 选择规则

### 2.1 选择父布局

同时考虑信息分区、必要 Action、候选组件及其占位类型：

1. 有必要 Action 时排除 `top-bottom`。
2. 两个内容分区都值得独立阅读时，优先 `split-panels`；不要仅按输入字段顺序机械切成左右两边。
3. 一个主要内容区之外还有恰好两个真实固定模块时，使用 `main-right-double`。只有一个固定模块时不能选择它。
4. 恰好四个层级相近且都适合 `InfoBlock`／`CardButton` 时，使用 `four-blocks`。
5. 没有 Action，且一个核心组件加一组整宽并列明细能够完整表达时，使用 `top-bottom`。
6. 多个布局都可行时，依次比较：必要信息与全部 Action 是否完整；相关信息是否邻近、最终分区是否清楚；组件是否属于允许集合且容量充足；主次是否明确、同级模块是否对齐；是否存在不必要的空槽、嵌套、压缩或零散组件。

不得为了满足布局数量而重复信息、虚构字段、虚构 Action 或创建无效标题。

### 2.2 选择内容区变体

先确定业务组件属于“紧凑内容”“宽内容”还是专用组件，再按一个信息分区最终需要的标题、内容组件数和直属 Action 数选择。不能先按名称选变体，再把不属于其组件集合的组件塞入内容位：

- 单内容无标题：`compact-center`／`wide-center`。
- 标题 + 单内容：`compact-title-content`／`wide-title-content`。
- 标题 + 单内容 + Action：`compact-title-content-action`／`wide-title-content-action`。
- 标题 + 核心 + 明细：`compact-title-primary-secondary`／`wide-title-primary-secondary`。
- 标题 + 核心 + 明细 + Action：仅 `wide-title-primary-secondary-action`。
- 双占比和四占比分别使用对应专用宽变体，不拆成通用零散组件；双 `InfoBlock` 只进入 `main-right-double` 的右侧两个固定槽。

`split-panels` 默认两侧使用紧凑变体。只有 `wide-title-double-progress`、`wide-quad-progress` 可以在其中一侧使用；两侧不能同时使用宽变体。任何一侧都不得使用 `InfoBlock`。

## 3. 父布局

### 3.1 `top-bottom`

#### 布局描述

将一个信息分区组织为标题、主体和同级明细。适合突出一个结论，并用一组高密度明细补充。

#### 槽位

| 槽位 | 内容角色 | 允许内容 |
|---|---|---|
| `title` | 整卡标题 | 一个标题单元 |
| `primary` | 主要内容 | 一个能够独立表达核心信息的组件 |
| `details` | 并列明细 | 一个 `TextBlock` 或 `TopTextBottomValue` |

#### 模板

```jsx
<Card size="2x4" appearance="solid-blue" layout="top-bottom">
  <Region slot="title">{/* 标题 */}</Region>
  <Region slot="primary">{/* 一个主体组件 */}</Region>
  <Region slot="details">{/* TextBlock 或 TopTextBottomValue */}</Region>
</Card>
```

#### 注意事项

- 输入存在任何 Action 时不能使用。
- `details` 是同级明细组，不放第二个主结论。
- 主体和明细信息较多时，先使用合适的高密度组件；仍无法完整承载则更换父布局。

### 3.2 `split-panels`

#### 布局描述

用于两个完整信息分区，或同一主题中可以独立阅读的核心区与属性区。

#### 槽位

| 槽位 | 内容角色 | 允许内容 |
|---|---|---|
| `left` | 左内容区 | 一个紧凑变体，或允许的一个宽变体 |
| `right` | 右内容区 | 一个紧凑变体，或允许的一个宽变体 |

#### 模板

```jsx
<Card size="2x4" appearance="solid-cyan" layout="split-panels">
  <Region slot="left" variant="compact-title-content">
    {/* 标题、主体 */}
  </Region>
  <Region slot="right" variant="compact-title-content-action">
    {/* 标题、主体、直属 PillButton */}
  </Region>
</Card>
```

#### 注意事项

- 每侧的信息和直属 Action 留在本侧。
- 不按 `data[]`／`actions[]` 的原始顺序分区；先按语义关系重组。
- 只有指定专用宽变体可使用无背板侧；该视觉差异由语义布局处理。

### 3.3 `main-right-double`

#### 布局描述

左侧承载主要内容，右侧提供两个固定模块槽。右侧模块可以共同服务左侧，也可以表达相关但不适合塞入主内容区的信息。

#### 槽位

| 槽位 | 内容角色 | 允许内容 |
|---|---|---|
| `main` | 主要内容区 | 一个宽变体 |
| `side-top` | 右上固定槽 | `CardButton`，或 `InfoBlock` |
| `side-bottom` | 右下固定槽 | `CardButton`；或在上槽为 `InfoBlock` 时使用 `InfoBlock` |

#### 模板

```jsx
<Card size="2x4" appearance="solid-purple" layout="main-right-double">
  <Region slot="main" variant="wide-title-content">
    {/* 标题、主体 */}
  </Region>
  <Region slot="side-top">{/* CardButton，或 InfoBlock */}</Region>
  <Region slot="side-bottom">{/* CardButton，或与上槽配对的 InfoBlock */}</Region>
</Card>
```

#### 注意事项

- 右侧只允许：双 `CardButton`、双 `InfoBlock`、上 `InfoBlock` + 下 `CardButton`。
- 两个槽都必须有真实内容；不得用重复信息或虚构按钮填充。
- 单独一个固定模块不能选择该布局。
- 右侧不使用 `PillButton`。

### 3.4 `four-blocks`

#### 布局描述

用于恰好四个同级固定模块。每个模块应能独立阅读，四者的视觉层级应接近。

#### 槽位

| 槽位 | 内容角色 | 允许内容 |
|---|---|---|
| `top-left` | 左上模块 | 一个 `InfoBlock` 或 `CardButton` |
| `top-right` | 右上模块 | 一个 `InfoBlock` 或 `CardButton` |
| `bottom-left` | 左下模块 | 一个 `InfoBlock` 或 `CardButton` |
| `bottom-right` | 右下模块 | 一个 `InfoBlock` 或 `CardButton` |

#### 模板

```jsx
<Card size="2x4" appearance="solid-blue" layout="four-blocks">
  <Region slot="top-left">{/* InfoBlock 或 CardButton */}</Region>
  <Region slot="top-right">{/* InfoBlock 或 CardButton */}</Region>
  <Region slot="bottom-left">{/* InfoBlock 或 CardButton */}</Region>
  <Region slot="bottom-right">{/* InfoBlock 或 CardButton */}</Region>
</Card>
```

#### 注意事项

- 四个槽必须全部有效。
- 混用信息与操作时，同类模块必须放在同一列并按上到下排列；同一列不得混用两种组件。
- 三个模块不得补造第四个；改选其他父布局。

## 4. 紧凑内容区变体

以下变体只用于 `split-panels`。

### 4.1 `compact-center`

#### 选择条件

单一核心组件无需标题即可理解，且没有 Action。

#### 槽位结构

一个紧凑内容组件。

#### 模板

```jsx
<Region slot="left" variant="compact-center">
  {/* 一个核心组件 */}
</Region>
```

#### 注意事项

核心组件必须无需额外上下文即可理解，并且属于“紧凑内容”集合。

### 4.2 `compact-title-content`

#### 选择条件

一个紧凑主体需要标题补足对象或语境，且没有 Action。

#### 槽位结构

一个标题和一个主体组件。

#### 模板

```jsx
<Region slot="left" variant="compact-title-content">
  <SingleLineTitle title="分区标题" />
  {/* 一个主体组件 */}
</Region>
```

#### 注意事项

主体必须属于“紧凑内容”集合并能完整显示。一条短事件可使用普通 `EventCard`；两项短 `TableText` 或双项短 `H_BarChart` 也可使用。`TextBlock`、`InfoBlock` 和 `ProgressCircle` 均不适用。

### 4.3 `compact-title-primary-secondary`

#### 选择条件

同一信息分区中存在一项核心信息和一项短明细，且没有 Action。

#### 槽位结构

一个标题、一个核心组件和一个短明细组件。

#### 模板

```jsx
<Region slot="left" variant="compact-title-primary-secondary">
  <SingleLineTitle title="分区标题" />
  {/* 一个核心组件 */}
  {/* 一个短明细组件 */}
</Region>
```

#### 注意事项

两个内容组件都必须属于“紧凑内容”集合、属于同一信息分区并具有明确主次；不要放两个都需要较大高度的组件。

### 4.4 `compact-title-content-action`

#### 选择条件

一个紧凑主体具有一个直属 Action。

#### 槽位结构

一个标题、一个主体组件和一个 `PillButton`。

#### 模板

```jsx
<Region slot="right" variant="compact-title-content-action">
  <SingleLineTitle title="分区标题" />
  {/* 一个紧凑主体组件 */}
  <PillButton label="操作" appearance="card" actionId="输入中的真实 Action ID" />
</Region>
```

#### 注意事项

Action 必须直属本分区。主体必须属于“紧凑内容”集合；长文本或多行高密度组件不适用。

## 5. 宽内容区变体

宽变体主要用于 `main-right-double.main`。其中两个专用变体也允许作为 `split-panels` 的一侧。

### 5.1 `wide-center`

#### 选择条件

主内容区只有一个无需标题即可理解的核心组件。

#### 槽位结构

一个宽内容组件。

#### 模板

```jsx
<Region slot="main" variant="wide-center">
  {/* 一个核心组件 */}
</Region>
```

#### 注意事项

主体必须属于“宽内容”集合；不追加标题、明细或 Action。

### 5.2 `wide-title-content`

#### 选择条件

主内容区中的一个主体需要标题补足对象或语境。

#### 槽位结构

一个标题和一个宽主体组件。

#### 模板

```jsx
<Region slot="main" variant="wide-title-content">
  <SingleLineTitle title="分区标题" />
  {/* 一个主体组件 */}
</Region>
```

#### 注意事项

主体必须属于“宽内容”集合；没有直属 Action 时使用。

### 5.3 `wide-title-content-action`

#### 选择条件

主内容区中的一个主体具有一个直属 Action。

#### 槽位结构

一个标题、一个主体组件和一个 `PillButton`。

#### 模板

```jsx
<Region slot="main" variant="wide-title-content-action">
  <SingleLineTitle title="分区标题" />
  {/* 一个主体组件 */}
  <PillButton label="操作" appearance="card" actionId="输入中的真实 Action ID" />
</Region>
```

#### 注意事项

主体必须属于“宽内容”集合；Action 必须作用于该主体。

### 5.4 `wide-title-double-progress`

#### 选择条件

恰好两个同级对象使用同一种占比尺度，可有一个共同 Action。

#### 槽位结构

一个标题、两个 `ProgressCircle` 和可选的一个 `PillButton`。

#### 模板

```jsx
<Region slot="main" variant="wide-title-double-progress">
  <SingleLineTitle title="分区标题" />
  <ProgressCircle /* 第一个占比 */ />
  <ProgressCircle /* 第二个占比 */ />
  {/* 有共同 Action 时可追加一个 PillButton；否则省略 */}
</Region>
```

#### 注意事项

必须恰好两个同级占比。该变体可以作为 `split-panels` 的唯一宽侧。

### 5.5 `wide-title-primary-secondary-action`

#### 选择条件

同一分区的核心、短明细和一个直属 Action 都需要展示。

#### 槽位结构

一个标题、一个核心组件、一个短明细组件和一个 `PillButton`。

#### 模板

```jsx
<Region slot="main" variant="wide-title-primary-secondary-action">
  <SingleLineTitle title="分区标题" />
  {/* 一个核心组件 */}
  {/* 一个短明细组件 */}
  <PillButton label="操作" appearance="card" actionId="输入中的真实 Action ID" />
</Region>
```

#### 注意事项

核心和明细都必须属于“宽内容”集合且足够紧凑。任一组件需要多行连续高度时，改用其他父布局或减少经信息分析确认可省略的内容。

### 5.6 `wide-title-primary-secondary`

#### 选择条件

同一分区存在一项核心信息和一项相关明细，且没有 Action。

#### 槽位结构

一个标题、一个核心组件和一个明细组件。

#### 模板

```jsx
<Region slot="main" variant="wide-title-primary-secondary">
  <SingleLineTitle title="分区标题" />
  {/* 一个核心组件 */}
  {/* 一个明细组件 */}
</Region>
```

#### 注意事项

两个内容组件都必须属于“宽内容”集合，并具有明确主次。

### 5.7 `wide-quad-progress`

#### 选择条件

恰好四个同级对象使用同一种占比尺度，且不需要标题或 Action。

#### 槽位结构

四个 `ProgressCircle`。

#### 模板

```jsx
<Region slot="main" variant="wide-quad-progress">
  <ProgressCircle /* 占比 1 */ />
  <ProgressCircle /* 占比 2 */ />
  <ProgressCircle /* 占比 3 */ />
  <ProgressCircle /* 占比 4 */ />
</Region>
```

#### 注意事项

只包含四个同级占比，无标题、无 Action。可以作为 `split-panels` 的唯一宽侧。

## 6. 布局检查

- `Card.layout`、`Region.slot` 和 `Region.variant` 均逐字来自对应表格或模板，没有推断、缩写、拼接或扩展名称。
- `Card.layout` 与直属 `Region.slot` 集合完全一致，没有缺槽、重复槽或额外槽。
- 内容区 `variant` 与标题数、内容组件数和直属 Action 数一致。
- 必要 Action 均进入合法操作位，没有因布局选择而遗漏。
- 固定双槽和四槽均填入真实内容，没有重复信息、虚构字段或虚构 Action。
- 组件与槽位的兼容关系符合编排规范中的槽位兼容矩阵。
- JSX 中没有 `Stack`、`Grid` 或任何几何布局 Prop。
