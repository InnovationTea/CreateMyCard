---
name: phone-widget-2x2-layouts
description: 为当前尺寸选择和实现父布局、子布局、槽位、尺寸与对齐。
---

# 2×2 卡片布局规范

模型只提交 `Card.layout + Region.slot/variant`，程序在编译和浏览器校验前确定性展开为真实布局。以下尺寸只用于容量判断，不写入 JSX。

## 1. 画布约束

| 项目 | 规格 |
|---|---:|
| 卡片尺寸 | 150 × 150vp |
| 四边安全边距 | 12vp |
| 安全内容区 | 126 × 126vp |

所有可见内容必须限制在安全内容区内。标题、内容、按钮、对齐、间距与固定槽都由语义布局程序负责；模型不得输出 `Stack`、`Grid` 或几何 Props。

## 2. 顶层布局接口

| Card.layout | Region.slot | 用途 |
|---|---|---|
| `single` | `main`，必选并填写 variant | 除双信息块外的单区布局 |
| `double-blocks` | `top`、`bottom`，均必选且不填写 variant | 上下两个固定 `InfoBlock` |

`single` 只允许一个 `main` Region；`double-blocks` 必须同时提交两个固定槽，不得留空、合并或增加第三个 Region。

## 3. 单区 Variant 总表

| Region.variant | 对应布局 | 直属子元素顺序 | Action |
|---|---|---|---|
| `wide-center` | 核心居中 | 一个 Data Display 组件 | 无 |
| `wide-title-content` | 标题单内容 | 标题、一个主体内容 | 无 |
| `wide-title-primary-secondary` | 标题双内容 | 标题、核心内容、明细内容 | 无 |
| `wide-quad-content` | 内容四宫格 | 四个同级占比内容 | 无 |
| `wide-title-content-action` | 标题内容单按钮 | 标题、一个主体内容、`PillButton` | 1 |
| `wide-title-primary-secondary-action` | 标题主次内容单按钮 | 标题、核心内容、紧密关联的次要内容、`PillButton` | 1 |
| `wide-two-column-action` | 标题双列内容可选按钮 | `SingleLineTitle`、两个 `ProgressCircle`、可选 `PillButton` | 0–1 |
| `wide-title-anchor-action` | 标题锚点内容 | 标题、主要内容、左下次要内容、`CircleButton` | 1 |
| `wide-content-two-actions` | 紧凑内容双按钮 | 一个紧凑内容、两个 `PillButton` | 2 |

标题后间距、内容间距、底部按钮槽、双列、四宫格和右下锚点都由程序生成。一个业务组件无论包含多少字段或 `items` 都只算一个内容组件。需要改变内容模块数时必须更换 variant，不得使用容器把多个组件伪装成一个内容槽。

## 4. 各布局容量与模板

### 4.1 核心居中

仅允许一个无需标题即可独立理解的 Data Display 组件；不得混入标题、按钮或第二个业务组件。

```jsx
<Card size="2x2" appearance="orb-orange" layout="single">
  <Region slot="main" variant="wide-center">
    {/* 单一 Data Display 组件 */}
  </Region>
</Card>
```

### 4.2 标题单内容

标题必选。主体在标题下方使用剩余区域，左对齐、底端对齐。标题增高时先压缩内容槽；内容最小占位无法闭合时更换组件或布局。

```jsx
<Card size="2x2" appearance="solid-blue" layout="single">
  <Region slot="main" variant="wide-title-content">
    <SingleLineTitle title="今日天气" />
    {/* 单主体内容 */}
  </Region>
</Card>
```

### 4.3 双信息块

`top`、`bottom` 均为必选的 `InfoBlock` 固定槽。此布局单独使用 8vp 卡片安全边距，两个槽均为 134 × 63vp，槽间距为 8vp。每槽只允许一个 `InfoBlock`，不得替换为其他组件、包裹容器、合并或缺省。

```jsx
<Card size="2x2" appearance="orb-purple" layout="double-blocks">
  <Region slot="top">{/* InfoBlock */}</Region>
  <Region slot="bottom">{/* InfoBlock */}</Region>
</Card>
```

### 4.4 标题双内容

标题后依次提交核心内容和独立明细。程序让核心内容从上方开始、明细沉底；两者不是两个强调核心。

```jsx
<Card size="2x2" appearance="solid-green" layout="single">
  <Region slot="main" variant="wide-title-primary-secondary">
    <SingleLineTitle title="今日状态" />
    {/* 核心内容 */}
    {/* 独立明细 */}
  </Region>
</Card>
```

### 4.5 内容四宫格

无标题、无 Action。必须提交四个同级占比内容；每个内容独占一个单元格并居中。不得用四个零散文本组件填充。

```jsx
<Card size="2x2" appearance="orb-orange" layout="single">
  <Region slot="main" variant="wide-quad-content">
    {/* A */}
    {/* B */}
    {/* C */}
    {/* D */}
  </Region>
</Card>
```

### 4.6 标题内容单按钮

标题、一个主体内容和一个 `PillButton` 均必选。内容从标题下方左上开始，按钮固定在底部；没有 Action 时改用 `wide-title-content`。

```jsx
<Card size="2x2" appearance="solid-green" layout="single">
  <Region slot="main" variant="wide-title-content-action">
    <SingleLineTitle title="内存优化" />
    <ProgressLine2
      currentValue={43.75}
      totalValue={100}
      value="4.5"
      unit="GB可用"
      mode="light"
      dataIds={{ value: "memory.availableGB" }}
    />
    <PillButton label="一键清理" appearance="card" actionId="memory.cleanNow" />
  </Region>
</Card>
```

### 4.7 标题主次内容单按钮

标题、核心内容、紧密关联的次要内容和一个 `PillButton` 均必选。主次内容连续排列，按钮固定在底部；只有一个业务内容时改用 `wide-title-content-action`。

```jsx
<Card size="2x2" appearance="solid-blue" layout="single">
  <Region slot="main" variant="wide-title-primary-secondary-action">
    <SingleLineTitle title="今日概览" />
    {/* Hero 主要信息 */}
    {/* 紧密关联的次要信息 */}
    <PillButton label="查看详情" appearance="card" actionId="detail.open" />
  </Region>
</Card>
```

### 4.8 标题双列内容可选按钮

标题必须是 `SingleLineTitle`。两个内容必须且只能是 `ProgressCircle size="sm"`，分别表达两个同级占比对象；按钮可选，存在时必须是最后一个 `PillButton`。不得放入文本、图表、`ProgressCircleSingle` 或其他业务组件。

```jsx
<Card size="2x2" appearance="solid-blue" layout="single">
  <Region slot="main" variant="wide-two-column-action">
    <SingleLineTitle title="设备电量" />
    <ProgressCircle icon="phone_fill.svg" externalText={68} size="sm" ariaLabel="手机电量68%" appearance="card" />
    <ProgressCircle icon="watch_fill.svg" externalText={52} size="sm" ariaLabel="手表电量52%" appearance="card" />
    <PillButton label="设备管理" appearance="card" actionId="device.manage" />
  </Region>
</Card>
```

### 4.9 标题锚点内容

标题、主要内容、左下次要内容和一个 `CircleButton` 均必选。程序将次要内容放在左下区域，将按钮放入右下固定锚点；只有操作仅靠 Icon 即可明确表达，并且完整名称已写入 `ariaLabel` 时使用。

```jsx
<Card size="2x2" appearance="solid-blue" layout="single">
  <Region slot="main" variant="wide-title-anchor-action">
    <SingleLineTitle title="天气" />
    {/* 主要内容 */}
    {/* 左下次要内容 */}
    <CircleButton
      icon="phone_fill.svg"
      ariaLabel="拨打电话"
      appearance="card"
      actionId="contact.callPrimary"
    />
  </Region>
</Card>
```

### 4.10 紧凑内容双按钮

无标题。一个紧凑内容后必须依次提交两个 `PillButton`；两个 Action 均不可缺省。内容不能在固定容量内闭合时不得选择该 variant。

```jsx
<Card size="2x2" appearance="solid-green" layout="single">
  <Region slot="main" variant="wide-content-two-actions">
    <EmphasizedData
      value="68%"
      dataIds={{ value: "battery.remainingPercentText" }}
    />
    <PillButton label="开启省电" appearance="card" actionId="battery.powerSaving" />
    <PillButton label="电池设置" appearance="card" actionId="battery.settings" />
  </Region>
</Card>
```

## 5. 提交边界与容量检查

- 标题可接一个 `Badge`；程序将二者组成标题行，模型不用容器包裹。
- 每个内容组件必须是 Region 的直属子元素。不得输出 `Stack`、`Grid`，也不得用容器改变槽位数量。
- 三个紧凑占比使用一个 `NumericRatioStack` 作为单个内容组件；不得输出三个 `NumericRatio` 再自行排列。
- 可选区域不存在时直接省略对应业务组件，程序不会保留空槽。
- 超出容量时先选择合同允许的紧凑组件、组件原生 `items` 或其他合法 variant；不得手改宽高、间距、flex 或定位，也不得裁剪、重复或删除必需信息。
- 动态显示与 Action 使用输入中的真实 ID；需要卡片配色的业务组件传 `appearance="card"`。
