# 2×4 专属组件

本文件只在当前任务 `Card.size="2x4"` 时加载。

## 1. 文本组件

### 3.7 TopTextBottomValue

仅用于 2×4 卡片的多组指标组件。每组按“文本标签 → 数值 → 单位”纵向排列，两组及以上横向 `space-around` 分布。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `items` | `Array<{ key?, label, value, unit, dataIds? }>` | 必选，至少 2 项 | 默认空数组；少于 2 项不符合生成规范 | 多组指标，顺序与输入语义一致 |
| `items[].label` | `string` | 必选，静态 UI 文案 | 无默认值 | 上方文本标签，不绑定数据 ID |
| `items[].value` | `string \| number` | 必选 | 无默认值 | 中间核心数值；来自输入时必须绑定 |
| `items[].unit` | `string` | 必选，静态 UI 文案 | 无默认值 | 下方单位，不绑定数据 ID |
| `items[].dataIds` | `{ value?: string }` | `value` 来自输入数据时必选 | 不传时无绑定 | 只允许绑定同一项的 `value` |

#### 空间占位

| 占位属性 | 2×4 规格 |
|---|---|
| `width` | 占满 296vp 父模块；不提供自由 size Prop |
| `height` | 68vp；三行分别占 18vp、32vp、18vp，无额外垂直间距 |
| `item-width` | 按内容自然决定；多个 item 横排且不拉伸或均分 |
| `overflow` | 三行均保持完整单行，不支持省略号；内容总宽度放不下时当前组件组合无效 |

#### 合法 JSX 示例与布局约束

- 只能放入当前尺寸 Card，用于“上下双区”的整宽明细区，并由布局按真实内容高度分配空间。
- 必须至少包含 3 个 item；只有 `value` 可绑定 `dataIds`，`label` 和 `unit` 始终保持静态。
- 外层模块提供完整 296vp 内容宽度，禁止通过 `style`、`className` 或额外 width Prop 改变规格。
- 每个 item 的 `label`、`value`、`unit` 都必须完整显示。不得依赖 flex 压缩、裁剪或省略号容纳过多／过长内容；浏览器检测到横向放不下时必须重新分组，或改用更适合密集信息的组件。

```jsx
<Card direction="column" size="2x4" appearance="solid-green">
  <Stack direction="column" flex={0} width="full" height={18}>
    <SingleLineTitle title="我的健康数据" />
  </Stack>
  <Stack direction="column" flex={1} width="full" justify="flex-end">
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
  </Stack>
</Card>
```

### 3.9 TextBlock

仅用于 2×4 卡片的横向背板文本组。每项由静态文本标签和文本／数值单位参数组成，至少两项。组件占满父容器宽度；所有背板等分可用宽度，相邻项固定间距 8vp。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `items` | `Array<{ key?, label, parameter, dataIds? }>` | 必选，至少 2 项 | 默认空数组；少于 2 项不符合新生成规范 | 多组横向排列，顺序与输入语义一致 |
| `items[].label` | `string` | 必选，静态 UI 文案 | 无默认值 | 背板内上方文本标签，不绑定数据 ID |
| `items[].parameter` | `string \| number` | 必选 | 无默认值 | 背板内下方文本或数值单位参数；来自输入时必须绑定 |
| `items[].dataIds` | `{ parameter?: string }` | `parameter` 来自输入数据时必选 | 不传时无绑定 | 只允许绑定同一项的 `parameter`；不得包含 `label` 或其他 key |

#### 空间占位

| 占位属性 | 2×4 规格 | 说明 |
|---|---|---|
| `width` | `100%` | 占满父容器分配的完整宽度 |
| `item-width` | 等分剩余宽度，最小 64vp | 所有项使用相同弹性宽度并共同撑满父容器 |
| `height` | 自适应 48–64vp，默认 64vp | 跟随父级纵向槽在该范围内收缩；大于 64vp 时仍为 64vp，小于 48vp 时不再继续压缩 |
| `items-gap` | 8vp | item 宽度按 `(父容器宽度 − 间距总和) ÷ 项数` 计算 |
| `overflow` | 两行均单行省略 | 文本不换行，不增加组件高度 |

#### 合法 JSX 示例与布局约束

- 只能放入当前尺寸 Card。
- 外层布局必须向 `TextBlock` 分配完整内容宽度；禁止通过 `style`、`className` 或额外宽度 Prop 改写它的内部分布。
- 每项等分父容器扣除 8vp 间距后的剩余宽度，且不得小于 64vp；必须控制项数和文本长度，不得依赖溢出、压缩或自然宽度改变分布。
- `TextBlock` 默认高 64vp，并在父级纵向槽分配 48–64vp 时自动跟随收缩。
- 需要紧凑高度时，`TextBlock` 必须是外层纵向 `Stack` 的直接子组件；外层使用 `flex={0} height={48}` 分配 48vp 主轴空间。runtime 只对直接包裹 `TextBlock` 的 Stack 启用纵向收缩，不影响其他 Stack。不得给 `TextBlock` 分配小于 48vp 的槽位。

```jsx
<Stack direction="column" flex={0} width="full" height={48} mt={4}>
  <TextBlock
    items={[
      { label: "空气质量", parameter: "良", dataIds: { parameter: "weather.airQuality" } },
      { label: "紫外线", parameter: "中等", dataIds: { parameter: "weather.uvIndex" } },
      { label: "感冒指数", parameter: "低", dataIds: { parameter: "weather.coldLevel" } },
    ]}
  />
</Stack>
```

```jsx
<Card direction="column" size="2x4" appearance="solid-blue">
  <Stack direction="column" flex={0} width="full" height={18}>
    <SingleLineTitle title="手机电池" />
  </Stack>
  <Stack direction="column" flex={1} width="full" justify="flex-end">
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
  </Stack>
</Card>
```

## 2. 按钮组件

### 5.3 CardButton

卡片按钮，由必选文本、可选资源 Icon（缺省时显示圆形占位 Icon）和按钮容器组成，仅用于 320 × 160vp（2×4）Card 中两个及以上 Action 的紧凑操作区。组件本身不声明固定宽高，而是占满父容器分配的半卡宽槽位或 2×2 操作网格槽位。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `text` | `string` | 必选；建议约 4 个汉字 | 无默认值 | 按钮内可见操作文本，同时构成按钮的可访问名称 |
| `icon` | `string` | 可选 | 不传时由 runtime 在尾部显示 24 × 24vp 圆形占位 Icon | 有语义匹配候选时逐字使用当前输入 `assetCandidates[].src`；没有匹配候选时省略该 Prop，不得虚构资源路径，占位 Icon 不需要也不允许通过 `icon` Prop 指定 |
| `actionId` | `string` | 启用状态必选 | 不传时无动作绑定 | 原样引用输入 `actions[].id`；一个按钮只能引用一个动作，同一动作不得被其他按钮重复引用 |

`container`、`width`、`height` 和 `direction` 都不是 `CardButton` 的 JSX Props：容器尺寸由父布局负责，runtime 固定使用横向排列，生成模型不得显式控制方向。

```jsx
<CardButton
  text="播放音乐"
  icon="music_fill.svg"
  actionId="media.play"
/>
```

```jsx
<CardButton
  text="查看详情"
  actionId="content.openDetails"
/>
```

上例没有可用资源 Icon，runtime 会自动在按钮右侧生成圆形占位 Icon；生成 JSX 保持省略 `icon`，不要填写不存在的资源名称。

#### 布局约束（非 CardButton Props）

- 只能用于当前尺寸 Card。
- 用于“左内容右侧双槽”和“四槽宫格”的固定 Action 槽；单个右下 Action 仍使用 `CardButton`。
- 竖排固定槽列使用“左内容右侧双槽”；“四槽宫格”的四槽必须填满，允许与 `InfoBlock` 分列混用。“左右双区”子布局中的按钮使用 `PillButton`，不使用 `CardButton`。
- 组件使用 `width: 100%`、`height: 100%` 占满父槽。宽高由外层 `Stack` 或 `Grid` 按 Layout Pattern 分配，禁止给组件传固定尺寸。
- 每个父槽最多占一个半卡宽区域，通常为 144vp；禁止使用 296vp 整卡宽操作槽。
- 父槽必须满足“宽度 ≥ 高度”；不得把 CardButton 放入窄高槽位。
- 多个 `CardButton` 不得仅做一行左右并排；“四槽宫格”为完整的两列两行结构，同类组件按列纵排，不生成三槽网格。
- `CardButton` 必须完整位于 144 × 64vp 的固定父槽内；竖排或网格中的按钮槽应通过父 `Stack`／`Grid` 明确分配，不使用 `alignSelf`。
- runtime 固定使用横向排列：文本在左，资源 Icon 或圆形占位 Icon 在右；尾部视觉槽始终保留。
- `CardButton` 不使用 `appearance="card"`、`variant` 或 `color`。它根据所在 Card 的明暗背景自动使用主题色或白色。

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `width` | `100%` | 继承并占满父 Layout Pattern 分配的模块宽度，不固定为示例值 |
| `height` | 父槽高度，限制在 48–64vp | 组件占满父槽；低于 48vp 时仍按 48vp，高于 64vp 时仍按 64vp |
| `overflow` | 文本单行省略 | 文本不换行，不增加组件高度 |
