---
name: phone-widget-layouts-2x2
description: 规定 2×2 父布局、Region variant、固定槽、容量与语义 JSX 模板；通用布局语义见 layouts_common.md。
---

# 2×2 卡片布局规范

以下尺寸只用于容量判断，不写入 JSX。

| 项目 | 规格 |
|---|---:|
| 卡片尺寸 | 150 × 150vp |
| 四边安全边距 | 12vp |
| 安全内容区 | 126 × 126vp |

## 1. 父布局

| `Card.layout` | Region | 用途 |
|---|---|---|
| `single` | `main`，必选并填写 variant | 除双信息块外的单区布局 |
| `double-blocks` | `top`、`bottom`，均必选且不填 variant | 上下两个固定 `InfoBlock` |

`single` 只允许一个 `main`；`double-blocks` 必须填满两个固定槽，不得留空、合并或增加第三个 Region。

## 2. `single` Variant 总表

| `Region.variant` | 内容骨架 | 直属子元素顺序 | Action |
|---|---|---|---:|
| `wide-center` | 核心居中 | 一个 Data Display 组件 | 0 |
| `wide-title-content` | 标题单内容 | 标题、一个主体内容 | 0 |
| `wide-title-primary-secondary` | 标题双内容 | 标题、核心、明细 | 0 |
| `wide-quad-content` | 内容四宫格 | 四个同级占比内容 | 0 |
| `wide-title-content-action` | 标题内容单按钮 | 标题、主体、`PillButton` | 1 |
| `wide-title-primary-secondary-action` | 标题主次内容单按钮 | 标题、核心、明细、`PillButton` | 1 |
| `wide-two-column-action` | 标题双列占比 | `SingleLineTitle`、两个 `ProgressCircle`、可选 `PillButton` | 0–1 |
| `wide-title-anchor-action` | 标题锚点内容 | 标题、主要内容、左下次要内容、`CircleButton` | 1 |
| `wide-content-two-actions` | 紧凑内容双按钮 | 一个紧凑内容、两个 `PillButton` | 2 |

## 3. 容量与限定

### 核心居中

只允许一个无需标题即可独立理解的 Data Display 组件，不得混入标题、按钮或第二个内容。

```jsx
<Card size="2x2" appearance="orb-orange" layout="single">
  <Region slot="main" variant="wide-center">
    {/* 单一 Data Display 组件 */}
  </Region>
</Card>
```

### 标题单内容／标题双内容

标题必选。单内容使用标题后的剩余区域；双内容按核心、明细顺序提交，程序让核心靠上、明细沉底。标题增高后内容最小占位无法闭合时更换组件或 variant。

```jsx
<Card size="2x2" appearance="solid-green" layout="single">
  <Region slot="main" variant="wide-title-primary-secondary">
    <SingleLineTitle title="今日状态" />
    {/* 核心内容 */}
    {/* 独立明细 */}
  </Region>
</Card>
```

### 双信息块

`top`、`bottom` 均为必选 `InfoBlock` 固定槽。该布局使用 8vp 外边距，两个槽均为 134 × 63vp，槽间距 8vp；每槽只能放一个 `InfoBlock`。

```jsx
<Card size="2x2" appearance="orb-purple" layout="double-blocks">
  <Region slot="top">{/* InfoBlock */}</Region>
  <Region slot="bottom">{/* InfoBlock */}</Region>
</Card>
```

### 内容四宫格

无标题、无 Action，必须提交四个同级占比内容并分别居中；不得用四个零散文本组件填充。

### 带 `PillButton` 的 Variant

- `wide-title-content-action`：标题、一个主体和一个底部按钮均必选。
- `wide-title-primary-secondary-action`：标题、核心、紧密关联的明细和一个底部按钮均必选。核心与明细合计只有约 56vp 的安全高度；大号数值加多行明细、强调文本加三项明细通常放不下，应改用更紧凑的内容组件或其他能保留 Action 的布局。
- `wide-content-two-actions`：无标题，一个高度不超过 38vp 的紧凑内容后依次提交两个按钮；两个 Action 均不可缺省。`ProgressCircleSingle` 即使使用紧凑规格也放不下，不选用。
- 没有 Action 时不得选必选按钮 variant；只有一个业务内容时不得选主次内容 variant。

### 标题双列占比

标题必须是 `SingleLineTitle`。两个内容必须且只能是 `ProgressCircle size="sm"`；可选按钮存在时必须是最后一个 `PillButton`。不得放入文本、图表或 `ProgressCircleSingle`。

### 标题锚点内容

标题、主要内容、左下次要内容和一个 `CircleButton` 均必选。只有操作仅靠 Icon 即可明确表达，且完整名称已写入 `ariaLabel` 时使用。

```jsx
<Card size="2x2" appearance="solid-blue" layout="single">
  <Region slot="main" variant="wide-title-anchor-action">
    <SingleLineTitle title="天气" />
    {/* 主要内容 */}
    {/* 左下次要内容 */}
    <CircleButton icon="phone_fill.svg" ariaLabel="拨打电话" appearance="card" actionId="contact.callPrimary" />
  </Region>
</Card>
```

## 4. 提交检查

- 标题可接一个 `Badge`，程序自动形成标题行，不用容器包裹。
- 三个紧凑占比使用一个 `NumericRatioStack`，不得输出三个 `NumericRatio` 自行排列。
- 所有业务组件是 Region 直属子元素；不输出 `Stack`、`Grid` 或几何 Props。
- 动态显示与 Action 使用当前输入真实 ID；需要卡片配色的业务组件传 `appearance="card"`。
