# 2×2 专属组件

本文件只在当前任务 `Card.size="2x2"` 时加载。

## 1. 文本组件

### 3.5 DataDisplay

由文本标签、核心数值和单位／辅助信息组成的三行纵向文本组件，用于 Type 0 单模块居中布局。它适合倒计时、日期等需要以一个超大数值作为唯一视觉核心的场景，不用于同卡并列展示多组数据。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `label` | `string` | 必选 | 无默认值 | 第一行文本标签 |
| `value` | `number \| string` | 必选 | 无默认值 | 第二行核心数值；保持输入值的真实内容，不附加静态单位 |
| `supportingText` | `string` | 必选 | 无默认值 | 第三行单位或辅助信息 |
| `dataIds` | `{ value?: string }` | `value` 来自输入数据时必选 | 不传时无绑定 | 只允许绑定核心数值 `value`；`label` 与 `supportingText` 始终是静态 UI 文案，不绑定数据 ID |

静态说明文字不需要绑定。下面示例中，`label` 和 `supportingText` 是静态 UI 文案，只有动态倒计时数值绑定数据：

```jsx
<Card size="2x2" appearance="type0-gradient">
  <Stack width="full" height="full" align="center" justify="center">
    <DataDisplay
      label="马拉松还剩"
      value={7}
      supportingText="天"
      dataIds={{ value: "marathon.remainingDays" }}
    />
  </Stack>
</Card>
```

即使 `label` 或 `supportingText` 的显示文案与输入数据内容相同，也不得为它们填写 `dataIds`。动态更新只作用于中间的核心 `value`，不会改变三行结构、样式或布局。

#### 组件样式

| 样式属性 | 值 | 说明 |
|---|---|---|
| `label-typography` | Body_S / 12px / Medium 500 / 18px | 第一行文本标签字体规格 |
| `label-color` | `font-secondary` | 第一行文本标签字色 |
| `value-typography` | Display_L / 56px / Bold 700 / 60px | 第二行核心数值字体规格；0827 将行高由 64px 调整为 60px |
| `value-color` | `font-primary` | 第二行核心数值字色 |
| `supporting-typography` | Body_M / 14px / Regular 400 / 20px | 第三行单位／辅助信息字体规格 |
| `supporting-color` | `font-secondary` | 第三行单位／辅助信息字色 |
| `direction` | 纵向 | 固定顺序为 Label → Value → Supporting Text |
| `gap` | 8vp | Label 与 Value、Value 与 Supporting Text 的垂直间距；0827 由 2vp 调整为 8vp |
| `alignment` | 水平居中 | 三行文本及组件整体居中 |

#### 布局约束

- 固定用于 Type 0 单模块居中布局；规范示例为 160 × 160vp 的 `Card size="2x2"`。
- `Card` 四边安全边距为 12vp，内部可用模块为 136 × 136vp；`DataDisplay` 在该模块内水平、垂直居中。
- Type 0 必须使用 `Card appearance="type0-gradient"`。多椭圆深色渐变由 `Card` 创建，禁止在业务 JSX 中手工添加椭圆 DOM、`style`、`background` 或硬编码颜色。
- 不得在 Type 0 上额外添加标题、按钮或并列业务组件。

## 2. 按钮组件

### 5.2 CircleButton

只显示 Icon、不显示文本的圆形按钮。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `icon` | `string` | 必选 | 无默认值 | 使用当前输入中适合作为按钮功能的候选资源 `src` |
| `ariaLabel` | `string` | 生成 Card 必选 | runtime 不校验空字符串 | 按钮没有可见文本，必须提供明确的操作名称 |
| `variant` | `"emphasis" \| "normal"` | 可选；生成 Card 通常省略 | `"emphasis"` | 只在普通 catalog 模式下控制强调程度；Card 模式由 `Card.appearance` 统一配色 |
| `color` | `"primary" \| "secondary" \| "success" \| "discovery" \| "danger" \| "warning" \| "caution"` | 仅 runtime 兼容 catalog | `"primary"` | 新生成禁止传入；Card 内颜色由 `Card.appearance` 派生 |
| `appearance` | `"card"` | 生成 Card 必选 | 默认 catalog 模式 | 使用当前 Card 对应的背景和 Icon 颜色 |
| `disabled` | `boolean` | 可选 | `false` | 禁用状态 |
| `actionId` | `string` | 启用状态必选 | 不传时无动作绑定 | 原样引用输入 `actions[].id`；一个按钮只能引用一个动作 |

以下 `color` 值与 `PillButton` 相同，也仅供旧 catalog JSX 与 runtime 兼容：

- `primary`
- `secondary`
- `success`
- `discovery`
- `danger`
- `warning`
- `caution`

#### 布局约束（非 CircleButton Props）

`CircleButton` 仅用于 160 × 160vp（2×2）Card，自身只负责 36 × 36vp 圆形按钮的内容、颜色和交互状态，不负责在卡片内定位。必须由外层 `Stack` 放入安全内容区的右下操作槽：

```jsx
<Card size="2x2" appearance="blue-soft">
  <Stack width="full" height="full" position="relative">
    <Stack flex={1} minHeight={0}>
      <EmphasizedData
        value="26℃"
        dataIds={{ value: "weather.temperatureText" }}
      />
    </Stack>

    <Stack position="absolute" right={0} bottom={0} width={36} height={36}>
      <CircleButton
        icon="resources/base/media/phone_fill.svg"
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

#### 组件样式

| 样式属性 | 值 | 说明 |
|---|---|---|
| `size` | 36 × 36vp | 按钮固定尺寸 |
| `icon-size` | 20 × 20vp | 中心 Icon 固定尺寸 |
| `border-radius` | 50% | 圆形容器 |
| `label` | 不显示 | 组件只显示 Icon |
| `content-alignment` | 水平、垂直居中 | Icon 在按钮内的位置 |
| `placement` | 安全内容区右下操作槽 | 由外层 `Stack` 负责定位，按钮自身不设置 `right` 或 `bottom` |
| `card-edge-distance` | 右侧 12px、底部 12px | 由 Card 默认 12px padding 与安全内容区内的 `right={0}`、`bottom={0}`共同实现 |
| `variant-emphasis` | 与 `PillButton` 相同 | 仅描述普通 catalog 模式 |
| `variant-normal` | 与 `PillButton` 相同 | 仅描述普通 catalog 模式 |
| `hover` | catalog 模式主题色加深；Card 模式保持 `card-circle-bg` | 鼠标悬停状态 |
| `active` | catalog 模式主题色继续加深；Card 模式保持 `card-circle-bg` | 按压状态 |
| `focus-visible` | 2px 蓝色外轮廓 | 键盘聚焦状态 |
| `disabled` | 透明度 40% | 禁用点击与指针事件 |
| `accessible-name` | `aria-label` | 必须提供可访问名称 |
| `component-boundary` | 独立组件 | 不通过 `shape` 属性与 `PillButton` 切换 |
