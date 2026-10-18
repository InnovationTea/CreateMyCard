# 2×2 专属组件

本文件只在当前任务 `Card.size="2x2"` 时加载。

## 1. 按钮组件

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

#### 空间占位

| 占位属性 | 值 | 说明 |
|---|---|---|
| `size` | 36 × 36vp | 按钮固定尺寸 |
| `layout` | 由 36 × 36vp 外层槽定位 | 组件自身不设置 `right` 或 `bottom` |
