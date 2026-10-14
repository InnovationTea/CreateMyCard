---
name: phone-widget-2x4-component-combinations
description: 当多个业务组件需要共同表达一组信息或操作时选择并实现合法组合。
---

# 多组件组合

## 组合候选总表

| 组合信息形态 | 字段结构示例 | 组合 | 选择条件 | 不应选择的情况 |
| :--- | :--- | :--- | :--- | :--- |
| 2 个占比值 | `{items: [{percent, icon}, {percent, icon}]}` | `ProgressCircle` × 2 | 2×4 使用 `wide-title-double-progress`，两个 `ProgressCircle` 作为 Region 直属节点 | 不得用 `NumericRatioStack`；每个占比对象还带有独立副文本时，优先判断是否应聚合为 `InfoBlock × 2`；逐项纯文本 Label 必须可见时不用 |
| 3 个紧凑占比值 | `{items: [{percent, icon}, {percent, icon}, {percent, icon}]}` | `NumericRatioStack` | 恰好三个同级占比值；每项显示 Icon 和取整后的百分比且不使用 Bar；通过 `direction="row" | "column"` 选择横排或纵排 | 一项或两项时不用；不得改为多个独立 `NumericRatio` 或用 `Stack/Grid` 包装 |
| 4 个占比值 | `{items: [{percent, icon}, {percent, icon}, {percent, icon}, {percent, icon}]}` | `ProgressCircle` × 4 | 四个同级对象使用紧凑圆环，每项显示取整后的百分比并可独立识别；2×2 卡片使用“内容四宫格” | 不通过多个 `NumericRatio` 表达四项数据；逐项纯文本 Label 必须可见时不用 |
| 单设备余量 + 状态 + 1 个 Action | `{percent, status, action}` | `ProgressCircleSingle` + `PillButton` | 占比与一条完整状态属于同一设备时，Info Plan 为两项事实都优先填写 `ProgressCircleSingle`；组件用 `value` 与 `secondaryLabel` 合并表达，Action 独立放在同一 Region 的末尾。2×4 紧凑区域使用 `size="compact"` 和带单 Action 的 variant | 不把 Action 写入 `ProgressCircleSingle`；不再为状态创建第二个业务组件；多个独立状态字段不能自行拼成一个 `secondaryLabel` |
| 两组紧凑主副文本 | `{groups: [{primaryText, secondaryText, unit?, visual?}, {primaryText, secondaryText, unit?, visual?}]}` | `InfoBlock` × 2 | 完成基础性质识别后再判定：同一张卡片中有且仅有两组可独立理解的信息，每组都具有一个主文本和一个副文本槽位；有明确图形识别或占比语义时可增加 Icon 或 ProgressCircle 尾部视觉，没有合适视觉或文本需要完整宽度时省略 `visual`。单设备剩余电量可作为其中一组；主值为孤立数字时使用 `primaryTextTemplate="电量 {value}"` 补充短语义，静态 `unit="%"`，并设置 `visual.type="progressCircle"`。总表中的 `InfoTile` 对应真实 JSX 组件 `InfoBlock`；命中后两组分别映射一个 `InfoBlock`，2×2 使用无独立标题的“双信息块”，2×4 仅在布局提供合法的 144 × 64vp 固定槽时选择，不得放入普通内容 Region；具体槽位见语义布局接口 | 只有一组、三组及以上或任一组缺少主、副文本槽位时不用；不得为满足旧视觉结构虚构 Icon；普通百分比仅作为副文本事实时不得据此启用 ProgressCircle；聚合后不得再重复实例化内部来源组件 |
| 2×2 操作 | `{cardSize: "2x2", action: {label?, icon?, ariaLabel?}}` | `PillButton` / `CircleButton` | 先检查标题和必需内容完整呈现后，底部是否仍能留出 `8vp` 间距和 `136 × 36vp` 操作槽；能留出时优先使用带明确操作文本的 `PillButton`，Icon 可选。只有无法容纳该底部槽、但右下 `36 × 36vp` 槽可安全避让内容，且操作仅靠 Icon 也能明确表达时，才使用 `CircleButton`，并将完整操作名称写入 `ariaLabel` | 不得仅因 action 提供 Icon 就选择 `CircleButton`；`CircleButton` 不得用于 2×4；不得补造缺失的操作语义或 Icon |
| 2×4 单 Action 组 | `{cardSize: "2x4", actions: [oneAction]}` | `PillButton` / `CardButton` | 优先在所属子布局内使用 `PillButton`；子布局无法安全容纳时，使用“左内容右侧双槽”的右下固定槽和 `CardButton`。操作文本必选，按钮不得横跨整卡 | 不得因按钮类型改变 Action 语义；缺少操作文本时停止并报告；不得使用 `CircleButton` |
| 2×4 多 Action 组 | `{cardSize: "2x4", actions: [actionA, actionB, ...]}` | `CardButton` | 同一语义组／操作区域有两个及以上 Action 时使用；两个 Action 可进入“左内容右侧双槽”的右侧固定槽列，四个 Action 可使用“四槽宫格”；三个 Action 只有在另有一个真实同级 `InfoBlock` 时才能共同组成“四槽宫格” | 禁止只做一行左右并排或生成整卡宽按钮；缺少操作文本时停止并报告；同一个 Action 只能表达一次 |

## 标题与数量

Badge 紧跟 Region 内的标题，程序将二者组成间距 8px 的横向标题行，不用 Stack 包裹标题。总数只绑定 Badge，不再重复生成 EmphasizedData。

```jsx
<Region slot="main" variant="wide-title-primary-secondary">
  <SingleLineTitle title="未来7天日程" />
  <Badge value={1} color="pink" dataIds={{ value: "calendar.eventCount" }} />
  <EventCard
      items={[{
        title: "项目例会",
        time: "14:00",
        dataIds: {
          title: "calendar.events.0.title",
          time: "calendar.events.0.dtStart",
        },
      }]}
    />
  <SecondaryBody
      items={[
        {
          value: "周例会",
          dataIds: { value: "calendar.events.0.description" },
        },
      ]}
    />
</Region>
```

## 并列强调文本

每个语义分区最多一个 EmphasisText 或 EmphasizedData。两个独立业务组需要各自强调时，分别放入左右 Region；不得用容器制造额外语义分区。

```jsx
<Card size="2x4" appearance="solid-blue" layout="split-panels">
  <Region slot="left" variant="compact-title-content">
    <SingleLineTitle title="今日步数" />
    <EmphasisText mainText="6200步" dataIds={{ mainText: "healthSport.dailySteps" }} />
  </Region>
  <Region slot="right" variant="compact-title-content">
    <SingleLineTitle title="昨晚睡眠" />
    <EmphasisText mainText="良好" dataIds={{ mainText: "healthSport.sleepStatus" }} />
  </Region>
</Card>
```

## 双信息块

InfoBlock 只进入 144 × 64vp 固定 Region，不包裹 Stack，不传 width。下面是 main-right-double 的右侧双槽片段，完整卡片还须有真实 main 内容；没有第三个业务区域时应更换布局或组件，不补造模块。

```jsx
<Region slot="side-top">
  <InfoBlock
      primaryText="昨夜7小时1分"
      primaryTextTemplate="昨夜{value}"
      secondaryText="午睡0分"
      secondaryTextTemplate="午睡{value}"
      visual={{
        type: "icon",
        icon: "moon_z_fill_1.svg",
      }}
      dataIds={{
        primaryText: "healthSport.nightSleepDurationText",
        secondaryText: "healthSport.totalNapDurationText",
      }}
    />
</Region>
<Region slot="side-bottom">
  <InfoBlock
      primaryText="昨夜82分"
      primaryTextTemplate="昨夜{value}"
      secondaryText="睡眠｜科学睡眠"
      secondaryTextTemplate="睡眠｜{value}"
      visual={{
        type: "icon",
        icon: "moon_z_fill_1.svg",
      }}
      dataIds={{
        primaryText: "healthSport.sleepScore",
        secondaryText: "healthSport.sleepTypeDesc",
      }}
    />
</Region>
```

ProgressCircle 分支使用相同固定槽；unit 和静态说明不绑定：

```jsx
<Region slot="side-top">
  <InfoBlock
    primaryText="电量 68"
    primaryTextTemplate="电量 {value}"
    unit="%"
    secondaryText="未充电｜29.0 ℃"
    visual={{
      type: "progressCircle",
      icon: "icon_charge.svg",
    }}
    dataIds={{
      primaryText: "battery.remainingPercent",
      secondaryText: ["battery.chargingStatusDesc", "battery.temperatureText"],
    }}
  />
</Region>
```

## 多占比圆环

#### 布局约束（非 ProgressCircle Props）

同时展示多个占比值时，每个 `ProgressCircle` 放入当前尺寸 Layout Pattern 分配的独立槽位并水平、垂直居中。数量、网格结构和操作区由当前尺寸的布局文档决定；组件章节不重复声明另一尺寸的布局。

## 三项紧凑占比

#### 合法 JSX 与布局约束

恰好三个占比值纵向排列时使用 `NumericRatioStack direction="column"`：

```jsx
<NumericRatioStack
  direction="column"
  appearance="card"
  items={[
    { icon: "earphone_case_16644.svg", value: 80, unit: "%", dataIds: { value: "earbuds.caseBatteryPercent" } },
    { icon: "l_circle_fill.svg", value: 76, unit: "%", dataIds: { value: "earbuds.leftBatteryPercent" } },
    { icon: "r_circle_fill.svg", value: 74, unit: "%", dataIds: { value: "earbuds.rightBatteryPercent" } },
  ]}
/>
```

恰好三个占比值横向排列时使用 `direction="row"`；组件按父槽可用宽度自适应分配三项：

```jsx
<NumericRatioStack
  direction="row"
  appearance="card"
  items={[
    { icon: "earphone_case_16644.svg", value: 80, unit: "%", dataIds: { value: "earbuds.caseBatteryPercent" } },
    { icon: "l_circle_fill.svg", value: 76, unit: "%", dataIds: { value: "earbuds.leftBatteryPercent" } },
    { icon: "r_circle_fill.svg", value: 74, unit: "%", dataIds: { value: "earbuds.rightBatteryPercent" } },
  ]}
/>
```

## 内容与按钮对齐

### 操作槽对齐

- `PillButton` 及当前尺寸允许的专用操作按钮用作卡片操作入口时，按钮槽或同组按钮容器必须与其所属内容区的底部对齐；存在多个按钮时，整个按钮组贴底排列。各尺寸专用按钮的规则见对应尺寸的组件文档。
- 2×4 按钮由 Region 的操作槽贴底排列，不手写外层 Stack 或修改程序生成的对齐。
- 不得使用 `align="center"`、`justify="center"` 或等量上下留白使按钮悬空；按钮上方可以保留自适应剩余空间，按钮下方不得保留非规范间距。

#### 布局约束（非 PillButton Props）

- runtime 默认几何规格为 136 × 36vp、圆角 30vp；组件自身不设置定位。2×4“左右双区”的 `surface="backplate"` 内使用 118 × 36vp、圆角 18vp，作为普通布局流模块；其他尺寸的旧背板上下文保持 120 × 36vp。
- 2×2 中由对应 Layout Pattern 提供 136 × 36vp 操作槽。
- 2×4 的单 Action 优先进入所属子布局的 `PillButton`；子布局无法安全容纳时，改用“左内容右侧双槽”的右下固定槽和 `CardButton`。按钮不得横跨 296vp 安全内容区。
- 2×4“左右双区”的 Sub-118 按钮槽为 118 × 36vp，进入居中的 118 × 112vp 内部安全区，使用普通布局流及 6vp 纵向间距，不使用绝对定位。“左内容右侧双槽”的 Sub-140 内容区内部 `PillButton` 保持 136 × 36vp 并左对齐；不得向组件传入未知尺寸 Props。
- 如果卡片其他组件已经使用相同 Icon，按钮内省略重复 Icon，只保留文本标签。

2×4 Sub-140“标题内容单按钮”示例：

```jsx
<Region slot="main" variant="wide-title-content-action">
  <SingleLineTitle title="存储空间" />
  {/* 与 Action 对应的主内容组件或自然高度内容组 */}
  <PillButton label="一键清理" appearance="card" actionId="memory.cleanNow" />
</Region>
```

## 2×4 整宽数值明细组合

下方仅展示 details 槽；完整 top-bottom 卡片还必须提供 title 和 primary，父级结构见 layouts Skill。

#### 合法 JSX 示例与布局约束

- 只能放入当前尺寸 Card，用于“上下双区”的整宽明细区，并由布局按真实内容高度分配空间。
- 必须至少包含 3 个 item；只有 `value` 可绑定 `dataIds`，`label` 和 `unit` 始终保持静态。
- 外层模块提供完整 296vp 内容宽度，禁止通过 `style`、`className` 或额外 width Prop 改变规格。
- 每个 item 的 `label`、`value`、`unit` 都必须完整显示。不得依赖 flex 压缩、裁剪或省略号容纳过多／过长内容；浏览器检测到横向放不下时必须重新分组，或改用更适合密集信息的组件。

```jsx
<Region slot="details">
    <TopTextBottomValue
      items={[
        {
          label: "睡眠得分",
          value: 80,
          unit: "分",
          dataIds: { value: "health.sleepScore" },
        },
        {
          label: "消耗热量",
          value: 92,
          unit: "千卡",
          dataIds: { value: "health.calories" },
        },
        {
          label: "今日步数",
          value: 2031,
          unit: "步",
          dataIds: { value: "health.steps" },
        },
      ]}
    />
</Region>
```

## 2×4 整宽文本块组合

下方仅展示 details 槽；title 与 primary 按实际业务填写，不能省略或补造内容。

#### 合法 JSX 示例与布局约束

- 只能放入当前尺寸 Card。
- 外层布局必须向 `TextBlock` 分配完整内容宽度；禁止通过 `style`、`className` 或额外宽度 Prop 改写它的内部分布。
- 每项等分父容器扣除 8vp 间距后的剩余宽度，且不得小于 64vp；必须控制项数和文本长度，不得依赖溢出、压缩或自然宽度改变分布。
- `TextBlock` 默认高 64vp，并在父级纵向槽分配 48–64vp 时自动跟随收缩。
- TextBlock 直接放入 `top-bottom` 的 details Region；需要 48vp 明细槽时选择 `Card.flow="footer"`，程序生成可收缩的包装层，不手写固定高度 Stack。

```jsx
<Region slot="details">
  <TextBlock
    items={[
      { label: "空气质量", parameter: "良", dataIds: { parameter: "weather.airQuality" } },
      { label: "紫外线", parameter: "中等", dataIds: { parameter: "weather.uvIndex" } },
      { label: "感冒指数", parameter: "低", dataIds: { parameter: "weather.coldLevel" } },
    ]}
  />
</Region>
```

```jsx
<Region slot="details">
    <TextBlock
      items={[
        {
          label: "状态",
          parameter: "未充电",
          dataIds: { parameter: "battery.statusText" },
        },
        {
          label: "电量等级",
          parameter: "正常",
          dataIds: { parameter: "battery.levelText" },
        },
        {
          label: "电池温度",
          parameter: "29℃",
          dataIds: { parameter: "battery.temperatureText" },
        },
        {
          label: "充电器连接",
          parameter: "未连接",
          dataIds: { parameter: "battery.chargerStatusText" },
        },
      ]}
    />
</Region>
```
