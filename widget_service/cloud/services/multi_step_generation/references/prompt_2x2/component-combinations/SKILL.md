---
name: phone-widget-2x2-component-combinations
description: 当多个业务组件需要共同表达一组信息或操作时选择并实现合法组合。
---

# 多组件组合

## 组合候选总表

| 组合信息形态 | 字段结构示例 | 组合 | 选择条件 | 不应选择的情况 |
| :--- | :--- | :--- | :--- | :--- |
| 2 个占比值 | `{items: [{percent, icon}, {percent, icon}]}` | `ProgressCircle` × 2 | 两个同级对象并列，每项显示圆环、Icon 和取整后的 External Text；2×2 卡片使用“标题双列内容可选按钮”，必须生成固定单行标题，两个 59vp 固定宽度列在剩余高度内自适应；有 Action 时增加底部 `PillButton`，无 Action 时不保留按钮槽 | 1 个值改用 `ProgressCircleSingle`；3 个值改用三个独立的 `NumericRatio`；每个占比对象还带有独立副文本时，优先判断是否应聚合为 `InfoBlock × 2`；逐项纯文本 Label 必须可见时不用 |
| 3 个占比值 | `{items: [{percent, icon}, {percent, icon}, {percent, icon}]}` | `NumericRatio` × 3 | 每项分别使用一个 `NumericRatio`，显示 Icon 和取整后的百分比且不使用 Bar；根据布局分配的可用宽高，通过外层标准 `Stack` 横向或纵向排列三个组件；对象语义由 Icon 或模块标题承载 | 不用于 1、2 或 4 个占比值；不得增加额外的组合组件；逐项纯文本 Label 必须可见时不用 |
| 4 个占比值 | `{items: [{percent, icon}, {percent, icon}, {percent, icon}, {percent, icon}]}` | `ProgressCircle` × 4 | 四个同级对象使用紧凑圆环，每项显示取整后的百分比并可独立识别；2×2 卡片使用“内容四宫格” | 不通过多个 `NumericRatio` 表达四项数据；逐项纯文本 Label 必须可见时不用 |
| 两组紧凑主副文本 | `{groups: [{primaryText, secondaryText, unit?, visual?}, {primaryText, secondaryText, unit?, visual?}]}` | `InfoBlock` × 2 | 完成基础性质识别后再判定：同一张卡片中有且仅有两组可独立理解的信息，每组都具有一个主文本和一个副文本槽位；有明确图形识别或占比语义时可增加 Icon 或 ProgressCircle 尾部视觉，没有合适视觉或文本需要完整宽度时省略 `visual`。单设备剩余电量可作为其中一组；主值为孤立数字时使用 `primaryTextTemplate="电量 {value}"` 补充短语义，静态 `unit="%"`，并设置 `visual.type="progressCircle"`。命中后两组分别映射一个 `InfoBlock`，2×2 使用无独立标题的“双信息块”，2×4 仅可进入 132 × 57vp 固定槽，不得放入普通内容区 | 只有一组、三组及以上或任一组缺少主、副文本槽位时不用；不得为满足旧视觉结构虚构 Icon；普通百分比仅作为副文本事实时不得据此启用 ProgressCircle；聚合后不得再重复实例化内部来源组件 |
| 2×2 操作 | `{cardSize: "2x2", action: {label?, icon?, ariaLabel?}}` | `PillButton` / `CircleButton` | 先检查标题和必需内容完整呈现后，底部是否仍能留出 `8vp` 间距和 `126 × 36vp` 操作槽；能留出时优先使用带明确操作文本的 `PillButton`，Icon 可选。只有无法容纳该底部槽、但右下 `40 × 40vp` 操作槽可安全避让内容，且操作仅靠 Icon 也能明确表达时，才使用 `CircleButton`，并将完整操作名称写入 `ariaLabel` | 不得仅因 action 提供 Icon 就选择 `CircleButton`；`CircleButton` 不得用于 2×4；不得补造缺失的操作语义或 Icon |
| 2×4 单 Action 组 | `{cardSize: "2x4", actions: [oneAction]}` | `PillButton` / `CardButton` | 优先在所属子布局内使用 `PillButton`；子布局无法安全容纳时，使用“左内容右侧双槽”的右下固定槽和 `CardButton`。操作文本必选，按钮不得横跨整卡 | 不得因按钮类型改变 Action 语义；缺少操作文本时停止并报告；不得使用 `CircleButton` |
| 2×4 多 Action 组 | `{cardSize: "2x4", actions: [actionA, actionB, ...]}` | `CardButton` | 同一语义组／操作区域有两个及以上 Action 时使用；两个 Action 可进入“左内容右侧双槽”的右侧固定槽列，四个 Action 可使用“四槽宫格”；三个 Action 只有在另有一个真实同级 `InfoBlock` 时才能共同组成“四槽宫格” | 禁止只做一行左右并排或生成整卡宽按钮；缺少操作文本时停止并报告；同一个 Action 只能表达一次 |

## 标题与数量

#### 布局约束（非 Badge Props）

`Badge` 必须与它所修饰的标题处于同一个横向标题组，间距固定为 8px。`Badge` 不是标题组件的 prop，间距也不由 Badge 自身生成。

当一个总数用于概括下方的日程、消息或列表内容时，总数属于标题语义，必须通过标题旁的 `Badge` 表达，不再为同一个总数额外生成 `EmphasizedData`。例如“未来 7 天日程总数 + 最近一件日程”使用以下结构；`calendar.eventCount` 只绑定到 `Badge.value`，最近事件的标题和时间继续分别绑定到 `EventCard`：

```jsx
<Stack flex={0} direction="row" gap={8} align="center" width="full">
  <SingleLineTitle title="未来7天日程" />
  <Badge
    value={1}
    color="pink"
    dataIds={{ value: "calendar.eventCount" }}
  />
</Stack>

<Stack direction="column" flex={1} width="full" gap={2} justify="flex-start">
  <Stack direction="column" flex={0} width="full">
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
  </Stack>

  <Stack direction="column" flex={0} width="full">
    <SecondaryBody
      items={[
        {
          value: "周例会",
          dataIds: { value: "calendar.events.0.description" },
        },
      ]}
    />
  </Stack>
</Stack>
```

## 并列强调文本

#### 不同子分区中 EmphasisText 的横向组合

`EmphasisText` 自身保持“主文本在上、可选次文本在下”的纵向结构。同一分区只能放置一个 `EmphasisText`；只有 Layout Pattern 已经把父区域明确拆成两个独立子分区时，两个子分区才可各放一个。两个子分区横向排列且自然宽度加 8vp 间距不超过父槽时，父 `Stack` 必须显式写 `direction="row"`，并使用 `justify="space-between"` 分配剩余横向空间；每个包装 `Stack` 分别代表一个子分区：

```jsx
<Stack direction="row" width={120} gap={8} align="center" justify="space-between">
  <Stack direction="column" flex={0} width={56}>
    <EmphasisText
      mainText="6200"
      secondaryText="今日步数"
      dataIds={{ mainText: "healthSport.dailySteps" }}
    />
  </Stack>
  <Stack direction="column" flex={0} width={56}>
    <EmphasisText
      mainText="良好"
      secondaryText="昨晚睡眠"
      dataIds={{ mainText: "healthSport.sleepStatus" }}
    />
  </Stack>
</Stack>
```

## 双信息块

#### 合法 JSX 示例与布局约束

- `InfoBlock` 宽度使用父槽的完整可用宽度；2×2“双信息块”中固定为 134 × 63vp，2×4 固定槽中为 132 × 57vp。不得向 `InfoBlock` 传入 `width` Prop 覆盖父槽尺寸。
- 在 2×2 卡片中，`InfoBlock × 2` 使用“双信息块”：`Card` 设置 `padding={8} gap={8}`，每个 `InfoBlock` 分别放入一个 `<Stack direction="column" flex={0} width="full" height={63}>`。

```jsx
<Card direction="column" size="2x2" appearance="orb-purple" padding={8} gap={8}>
  <Stack direction="column" flex={0} width="full" height={63}>
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
  </Stack>
  <Stack direction="column" flex={0} width="full" height={63}>
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
  </Stack>
</Card>
```

```jsx
<Card direction="column" size="2x2" appearance="solid-blue" padding={8} gap={8}>
  <Stack direction="column" flex={0} width="full" height={63}>
    <InfoBlock
      primaryText="成都 29℃"
      primaryTextTemplate="成都 {value}"
      secondaryText="多云"
      visual={{
        type: "icon",
        icon: "local_fill.svg"
      }}
      dataIds={{
        primaryText: "weather1.current.temperatureC",
        secondaryText: "weather1.current.condition"
      }} />
  </Stack>
  <Stack direction="column" flex={0} width="full" height={63}>
    <InfoBlock
      primaryText="上海 29℃"
      primaryTextTemplate="上海 {value}"
      secondaryText="多云"
      visual={{
        type: "icon",
        icon: "local_fill.svg"
      }}
      dataIds={{
        primaryText: "weather2.current.temperatureC",
        secondaryText: "weather2.current.condition"
      }} />
  </Stack>
</Card>
```

ProgressCircle 分支仍使用同一槽位结构。`unit` 和静态说明不绑定；输入提供的主、副文本分别通过同名 `dataIds` 绑定：

```jsx
<Stack direction="column" flex={0} width="full" height={63}>
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
</Stack>
```

## 多占比圆环

#### 布局约束（非 ProgressCircle Props）

同时展示多个占比值时，每个 `ProgressCircle` 放入当前尺寸 Layout Pattern 分配的独立槽位并水平、垂直居中。数量、网格结构和操作区由当前尺寸的布局文档决定；组件章节不重复声明另一尺寸的布局。

## 三项占比

#### 合法 JSX 与布局约束

三个占比值纵向排列时，外层 `Stack` 显式使用 `direction="column"` 和 `gap={4}`：

```jsx
<Stack direction="column" gap={4} align="flex-start">
  <NumericRatio
    icon="earphone_case_16644.svg"
    value={80}
    unit="%"
    appearance="card"
    dataIds={{ value: "earbuds.caseBatteryPercent" }}
  />
  <NumericRatio
    icon="l_circle_fill.svg"
    value={76}
    unit="%"
    appearance="card"
    dataIds={{ value: "earbuds.leftBatteryPercent" }}
  />
  <NumericRatio
    icon="r_circle_fill.svg"
    value={74}
    unit="%"
    appearance="card"
    dataIds={{ value: "earbuds.rightBatteryPercent" }}
  />
</Stack>
```

三个占比值横向排列时，外层 `Stack` 显式使用 `direction="row"`；只有父槽宽度能够容纳三个组件的自然宽度与两处间距时才使用该方式：

```jsx
<Stack direction="row" width="full" gap={8} align="center" justify="space-between">
  <NumericRatio
    icon="earphone_case_16644.svg"
    value={80}
    unit="%"
    appearance="card"
    dataIds={{ value: "earbuds.caseBatteryPercent" }}
  />
  <NumericRatio
    icon="l_circle_fill.svg"
    value={76}
    unit="%"
    appearance="card"
    dataIds={{ value: "earbuds.leftBatteryPercent" }}
  />
  <NumericRatio
    icon="r_circle_fill.svg"
    value={74}
    unit="%"
    appearance="card"
    dataIds={{ value: "earbuds.rightBatteryPercent" }}
  />
</Stack>
```

## 内容与按钮对齐

### 通用布局约束（适用于 2×2 与 2×4）

- `PillButton` 及当前尺寸允许的专用操作按钮用作卡片操作入口时，按钮槽或同组按钮容器必须与其所属内容区的底部对齐；存在多个按钮时，整个按钮组贴底排列。各尺寸专用按钮的规则见对应尺寸的组件文档。
- 横向 `Stack` 中只有按钮需要贴底时，将按钮放进与内容区等高的包装 `Stack`，由该包装层使用 `justify="flex-end"`；同一行所有直接子项都需要底部对齐时，父 `Stack` 使用 `align="flex-end"`。
- 纵向 `Stack` 中使用 `justify="flex-end"` 将按钮槽或按钮组推到所属内容区底部。
- 不得使用 `align="center"`、`justify="center"` 或等量上下留白使按钮悬空；按钮上方可以保留自适应剩余空间，按钮下方不得保留非规范间距。

#### 布局约束（非 PillButton Props）

- 2×2 中由对应 Layout Pattern 提供 126 × 36vp 操作槽，圆角 30vp。
- 2×4“左右双区”内容区使用 116 × 36vp；“左内容右侧双槽／左侧双槽右内容”内容区使用 132 × 36vp 并撑满父容器宽度，圆角 18vp。
- 2×4 的单 Action 优先进入所属子布局的 `PillButton`；子布局无法安全容纳时，改用固定槽中的 `CardButton`。按钮不得横跨 276vp 安全内容区。
- 如果卡片其他组件已经使用相同 Icon，按钮内省略重复 Icon，只保留文本标签。

2×4 的 132vp 内容区“标题内容单按钮”示例：

```jsx
<Stack direction="column" width={132} height={126} gap={0}>
  <Stack direction="column" flex={0} width={132} mb={6}>{/* 局部标题 */}</Stack>
  <Stack direction="column" flex={1} width={132} mb={8}>{/* 与 Action 对应的主内容 */}</Stack>
  <Stack direction="column" flex={0} width={132} height={36}>
    <PillButton
      label="一键清理"
      appearance="card"
      actionId="memory.cleanNow"
    />
  </Stack>
</Stack>
```

## 2×2 锚点操作组合

#### 布局约束

`CircleButton` 仅用于 150 × 150vp（2×2）Card，自身只负责 36 × 36vp 圆形按钮的内容、颜色和交互状态，不负责在卡片内定位。必须由外层 `Stack` 放入安全内容区的右下操作槽：

```jsx
<Card direction="column" size="2x2" appearance="solid-blue">
  <Stack direction="column" width="full" height="full" position="relative">
    <Stack direction="column" flex={1}>
      <EmphasizedData
        value="26℃"
        dataIds={{ value: "weather.temperatureText" }}
      />
    </Stack>

    <Stack direction="column" position="absolute" right={0} bottom={0} width={36} height={36}>
      <CircleButton
        icon="phone_fill.svg"
        ariaLabel="拨打电话"
        appearance="card"
        actionId="contact.callPrimary"
      />
    </Stack>
  </Stack>
</Card>
```

定位规则：

- 最近的父容器必须设置 `position="relative"`。
- 按钮槽使用 `position="absolute"`、`right={0}`、`bottom={0}`、`width={36}`、`height={36}`。
- Card 默认 12vp padding，因此安全内容区内的 `right={0}`、`bottom={0}` 已等价于距离卡片外边缘右、下各 12vp。
- 不要再写 `right={12}`、`bottom={12}`，否则会在安全边距基础上重复内缩。
- 不要把 `position`、`right`、`bottom` 传给 `CircleButton`；这些不是它的业务 Props。
