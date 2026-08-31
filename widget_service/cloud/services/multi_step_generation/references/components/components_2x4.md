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

#### 组件样式

| 样式属性 | 2×4 规格 |
|---|---|
| `width` | 占满 296vp 父模块；不提供自由 size Prop |
| `item-layout` | 两组及以上横排、`space-around`；每组宽度按内容自然决定，不拉伸或均分 |
| `label` | Body_S / 12px / Medium 500 / 18px / `font-primary` |
| `value` | Title_M / 24px / Bold 700 / 32px / `font-primary` |
| `unit` | Body_S / 12px / Regular 400 / 18px / `font-secondary` |
| `divider` | 相邻组之间使用 1 × 62vp 分割线；浅色黑色 20%，深色白色 20% |
| `overflow` | 三行均保持完整单行，不支持省略号；内容总宽度放不下时当前组件组合无效 |

#### 合法 JSX 示例与布局约束

- 只能放入当前尺寸 Card，用于 Type 1 单内容布局并在内容区底部对齐。
- 必须至少包含 2 个 item；只有 `value` 可绑定 `dataIds`，`label` 和 `unit` 始终保持静态。示例使用 3 项，但不表示只能使用 3 项。
- 外层模块提供完整 296vp 内容宽度，禁止通过 `style`、`className` 或额外 width Prop 改变规格。
- 每个 item 的 `label`、`value`、`unit` 都必须完整显示。不得依赖 flex 压缩、裁剪或省略号容纳过多／过长内容；浏览器检测到横向放不下时必须重新分组，或改用更适合密集信息的组件。

```jsx
<Card size="2x4" appearance="orange-gradient">
  <Stack basis={18} width="full">
    <SingleLineTitle title="我的健康数据" />
  </Stack>
  <Stack flex={1} minHeight={0} width="full" justify="end">
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

#### 组件样式

| 样式属性 | 2×4 规格 | 说明 |
|---|---|---|
| `width` | `100%` | 占满父容器分配的完整宽度 |
| `items-count` | ≥ 2 | 至少两组 |
| `item-width` | 等分剩余宽度，最小 64vp | 所有项使用相同弹性宽度并共同撑满父容器 |
| `item-height` | 默认 64vp；父槽较矮时跟随父槽收缩 | 推荐分配 48–64vp；不得低于内部两行文本可完整显示的高度 |
| `item-padding` | 左右各 8vp | 文本组合在背板内居中 |
| `item-radius` | 16vp | 背板圆角 |
| `distribution` | 等宽弹性布局，间距 8vp | 背板宽度按 `(父容器宽度 − 间距总和) ÷ 项数` 分配 |
| `copy-direction` | 纵向，间距 2vp | `label` 在上，`parameter` 在下，均左对齐 |
| `label` | Caption_L / 12px / Bold 700 / 18px | 浅色 Card 使用主题深色；深色渐变 Card 使用白色 |
| `parameter` | Caption_M / 10px / Medium 500 / 16px | 浅色 Card 使用主题深色；深色渐变 Card 使用白色 |
| `backplate-color` | 当前文字主题色 10% | 浅色 Card 使用主题深色 10%；深色渐变 Card 使用白色 10% |

#### 合法 JSX 示例与布局约束

- 只能放入当前尺寸 Card。
- 外层布局必须向 `TextBlock` 分配完整内容宽度；禁止通过 `style`、`className` 或额外宽度 Prop 改写它的内部分布。
- 每项等分父容器扣除 8vp 间距后的剩余宽度，且不得小于 64vp；必须控制项数和文本长度，不得依赖溢出、压缩或自然宽度改变分布。
- `TextBlock` 默认高 64vp；垂直空间不足时，外层固定高度槽可以在 48–64vp 范围内缩短组件。缩短的是整体背板高度，不改变两行文字的字号、行高和 2vp 内部间距。

```jsx
<Card size="2x4" appearance="blue-soft">
  <Stack basis={18} width="full">
    <SingleLineTitle title="手机电池" />
  </Stack>
  <Stack flex={1} minHeight={0} width="full" justify="end">
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

卡片按钮，由必选文本、可选 Icon 和按钮容器组成，仅用于 320 × 160vp（2×4）Card 中两个及以上 Action 的紧凑操作区。组件本身不声明固定宽高，而是占满父容器分配的半卡宽槽位或 2×2 操作网格槽位。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `text` | `string` | 必选；建议约 4 个汉字 | 无默认值 | 按钮内可见操作文本，同时构成按钮的可访问名称 |
| `icon` | `string` | 可选 | 不传时只显示文本 | 使用当前输入中与操作语义匹配的候选资源 `src`；组件内以 24 × 24vp 单色 Icon 显示 |
| `actionId` | `string` | 启用状态必选 | 不传时无动作绑定 | 原样引用输入 `actions[].id`；一个按钮只能引用一个动作，同一动作不得被其他按钮重复引用 |

`container`、`width`、`height` 和 `direction` 都不是 `CardButton` 的 JSX Props：容器尺寸由父布局负责，runtime 固定使用横向排列，生成模型不得显式控制方向。

```jsx
<CardButton
  text="播放音乐"
  icon="resources/base/media/music_fill.svg"
  actionId="media.play"
/>
```

```jsx
<CardButton
  text="查看详情"
  actionId="content.openDetails"
/>
```

#### 布局约束（非 CardButton Props）

- 只能用于当前尺寸 Card。
- 仅在同一语义组／操作区域包含两个及以上 Action 时使用；两个 Action 可放入 Type 15、Type 16 的半卡宽竖排操作列，三个或四个 Action 可组成 Type 9 的 2×2 操作网格。该区域只有一个 Action 时改用 `PillButton`。
- 竖排操作列优先使用 Type 15、Type 16；2×2 操作网格使用 Type 9。Type 13 的单个父区只有能容纳两个及以上上下竖排操作槽时才可使用。
- 组件使用 `width: 100%`、`height: 100%` 占满父槽。宽高由外层 `Stack` 或 `Grid` 按 Layout Pattern 分配，禁止给组件传固定尺寸。
- 每个父槽最多占一个半卡宽区域，通常为 144vp；禁止使用 296vp 整卡宽操作槽。
- 父槽必须满足“宽度 ≥ 高度”；不得把 CardButton 放入窄高槽位。
- 多个 `CardButton` 不得仅做一行左右并排；三个或四个 Action 可以组成两列、最多两行的 2×2 操作网格。
- `CardButton` 必须完整位于 48–64vp 高的父槽内；竖排或网格中的按钮槽应通过父 `Stack`／`Grid` 明确分配，不使用 `alignSelf`。
- runtime 固定使用横向排列：文本在左，Icon 在右。
- `CardButton` 不使用 `appearance="card"`、`variant` 或 `color`。它根据所在 Card 的明暗背景自动使用主题色或白色。

#### 组件样式

| 样式属性 | 值 | 说明 |
|---|---|---|
| `width` | `100%` | 继承并占满父 Layout Pattern 分配的模块宽度，不固定为示例值 |
| `height` | `100%` | 继承并占满父 Layout Pattern 分配的模块高度，不固定为示例值 |
| `min-height` | 48px | 组件最低高度；父槽分配高度低于 48px 时以 48px 为准 |
| `max-height` | 64px | 组件最大高度；父槽分配高度高于 64px 时以 64px 为准 |
| `padding` | 7px 12px | 文本距左边缘 12vp；Icon 距右边缘 12vp |
| `border-radius` | 16vp | 按钮容器圆角 |
| `background` | Light：背景主题色 10%；Dark：白色 20% | 根据所在 Card 的明暗背景自动切换 |
| `text-typography` | Body_M / 14px / Bold 700 / 20px | 必选文本字体规格 |
| `text-color` | Light：背景主题色 100%；Dark：白色 100% | 文本颜色 |
| `text-overflow` | 单行省略 | 文本不换行，超出可用宽度时显示省略号 |
| `icon-size` | 24 × 24vp | 可选 Icon 尺寸，颜色与文本一致 |
| `direction` | 横向 | 文本在左，Icon 在右；不包含纵向变体 |
| `text-icon-gap` | 最小 8vp | 文本与 Icon 的最小间距 |
| `content-alignment` | 垂直居中 | 文本和 Icon 在父槽内垂直居中 |
| `focus-visible` | 2px 蓝色外轮廓 | 键盘聚焦状态 |
