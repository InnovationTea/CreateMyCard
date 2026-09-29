---
name: phone-widget-core-common
description: 规定两种尺寸共同使用的 JSX 输出、语义布局接口、数据与 Action 绑定、Boolean、单位和资源引用；不负责信息取舍或布局路由。
---

# 核心生成协议

## 1. 输出与生成边界

只输出工具要求的结构化参数。卡片 JSX 只使用已公开的 `Card`、`Region` 和业务组件；Prop 必须来自对应组件合同。

`Card` 是唯一根组件，`Region` 是业务组件的语义槽。模型只提交 `Card → Region → 业务组件`：

| 组件 | 可用 Prop | 规则 |
|---|---|---|
| `Card` | `size`、`appearance`、`layout`、可选 `aria-label` | `size` 与输入一致；`layout` 使用当前尺寸的枚举 |
| `Region` | `slot`、可选 `variant` | `slot` 属于当前布局；普通内容区按布局合同填写 `variant`，固定槽省略 |

不输出原生 HTML、未知 Prop、`style`、`className`、spread Props 或硬编码颜色。布局方向、间距、尺寸、定位、padding 和背板由 `Card.layout`、`Region.slot` 与 `Region.variant` 决定，不写入 JSX。

输入顶层 `size` 只用于布局路由，不是业务数据；生成的 `Card.size` 必须与输入一致。

## 2. 数据绑定

- 动态业务值写入组件真实显示 Prop，并用同名 `dataIds` 记录输入 `data[].id`。
- `dataIds` 的 key 必须是组件明确允许绑定的 Prop；ID 必须逐字引用当前任务内真实且唯一的值，不得缩写、改名或虚构。
- 默认一个显示 Prop 绑定一个 ID。只有组件合同明确允许时，才使用有序 ID 数组；具体可用 Prop 与组合语义由各组件定义。
- 多个字段不得手工拼成一个动态字符串。优先使用组件的多 item 能力、多个组件或合同允许的有序数组。
- `data[].value` 是预览值。若 `userQuery` 明确给出同一业务字段的当前值，单 ID 显示 Prop 使用查询值并继续绑定原 ID；多 ID Prop 不根据查询文本猜测各字段拆分值。
- 根据 `userQuery` 概括出的标题、区块标签、静态单位和按钮文案不绑定。输入字段直接承担标题、副标题或 `TableText` 行标识时，按对应组件合同绑定原 ID。
- 每个业务事实在整卡只有一个可见 owner。同一 ID 不得在两个可见位置重复绑定，也不得再用静态同义文案重复表达；进度图形与其配套的唯一数值文本可以共同表示同一进度。

## 3. Action 绑定

- `actionId` 逐字引用输入 `actions[].id`；一个控件最多绑定一个 Action，同一 `actionId` 在整卡最多使用一次。
- `actions[].description` 只用于选择动作并生成简短按钮文案，不作为标题、正文或按钮外说明。
- 只有输入提供真实 Action 时才创建操作组件；不得虚构、复制或删除必需 Action。

## 4. Boolean 与单位

- Boolean 优先绑定组件的 Boolean Prop，例如 `done` 或 `disabled`，并使用 JSX 表达式。
- 文本 Prop 不直接显示 `true`／`false`。确需显示双状态文案时，同一 Prop 同时提供 `dataIds` 与完整的 `dataValueMaps`：

```jsx
<EmphasisText
  mainText="已连接"
  dataIds={{ mainText: "device.connected" }}
  dataValueMaps={{ mainText: { true: "已连接", false: "未连接" } }}
/>
```

- `dataValueMaps` 只用于 Boolean 到可见文本的响应式映射，两种文案必须非空且不同；不能用于进度、布局或视觉属性。
- 有独立 `unit` Prop 的组件，可为输入明确支持的无单位数值补充静态单位。完整带单位字符串原样绑定，不拆分、不重复补单位。
- 静态标签、单位和分隔符只能解释动态值，不得改变数值、精度和业务语义；不得根据字段名猜测单位。

## 5. 资源与卡片颜色

- `icon`、`src` 和 `checkIcon` 必须逐字使用当前 `assetCandidates[].src`，并根据候选 `description` 选择。无匹配候选时省略可选 Icon；Icon 必选的组件不可选用。
- 不根据本地文件、示例或业务语义猜测资源名，不补路径或扩展名。
- 标题组件为纯文本。多个应用来源的信息不选择单个应用 Icon 代表整卡，也不堆叠多个应用 Icon。
- `Card.appearance` 负责卡片背景与语义调色板；业务组件不硬编码背景、字体、按钮或 Icon 颜色。

可用单色背景为 `solid-blue`、`solid-orange`、`solid-green`、`solid-cyan`、`solid-purple`。通用／天气／出行／办公／系统优先蓝色，日程优先橙色，电量／通话／运动健康优先绿色，耳机优先青色，睡眠／冥想优先紫色；无法确定时使用 `solid-blue`。其他背景以当前尺寸补充协议为准。

## 6. 提交前检查

1. 根组件、`size`、`layout`、`slot` 与 `variant` 合法。
2. 所有 Prop 都属于对应组件合同。
3. 所有动态值、数据 ID、Action ID、Boolean 映射和资源引用符合输入。
4. 无重复绑定、虚构字段、手工拼接动态字符串或几何布局 Prop。
