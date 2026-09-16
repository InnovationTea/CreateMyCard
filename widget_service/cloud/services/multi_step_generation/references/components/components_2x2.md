# 2×2 专属组件

本文件只在当前任务 `Card.size="2x2"` 时加载。

## 1. 文本组件

### 3.5 DataDisplay

由文本标签、核心数值和单位／辅助信息组成的三行纵向文本组件，用于“核心居中”单模块布局。它适合倒计时、日期等需要以一个超大数值作为唯一视觉核心的场景，不用于同卡并列展示多组数据。

#### 组件属性

| 属性名 | JSX 类型 | 设计约束 | runtime 默认 / 容错 | 说明 |
|---|---|---|---|---|
| `label` | `string` | 必选 | 无默认值 | 第一行文本标签 |
| `value` | `number \| string` | 必选 | 无默认值 | 第二行核心数值；保持输入值的真实内容，不附加静态单位 |
| `supportingText` | `string` | 必选 | 无默认值 | 第三行单位或辅助信息 |
| `dataIds` | `{ value?: string }` | `value` 来自输入数据时必选 | 不传时无绑定 | 只允许绑定核心数值 `value`；`label` 与 `supportingText` 始终是静态 UI 文案，不绑定数据 ID |

静态说明文字不需要绑定。下面示例中，`label` 和 `supportingText` 是静态 UI 文案，只有动态倒计时数值绑定数据：

```jsx
<Card direction="column" size="2x2" appearance="orb-orange">
  <Stack direction="column" width="full" height="full" align="center" justify="center">
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

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `width` | `max-content`，最大 136vp | 在 136 × 136vp 安全内容区内水平居中 |
| `height` | 114vp | 三行分别占 18vp、60vp、20vp，两处垂直间距各 8vp |

#### 布局约束

- 固定用于“核心居中”单模块布局；规范示例为 160 × 160vp 的 `Card size="2x2"`。
- `Card` 四边安全边距为 12vp，内部可用模块为 136 × 136vp；`DataDisplay` 在该模块内水平、垂直居中。
- 背景选择遵循 `references/core.md` 的 `Card.appearance` 规则；上述倒计时示例使用 `orb-orange`。融球背景由 `Card` 按视觉规范创建，使用椭圆色块与背景模糊，禁止在业务 JSX 中手工添加椭圆 DOM、`style`、`background` 或硬编码颜色。
- 不得在“核心居中”上额外添加标题、按钮或并列业务组件。

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

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `size` | 36 × 36vp | 按钮固定尺寸 |
| `layout` | 由 36 × 36vp 外层槽定位 | 组件自身不设置 `right` 或 `bottom` |
