# Core Generation Contract

本文件规定生成声明式卡片 JSX 时必须遵守的核心协议，以及 `Card`、`Stack`、`Grid` 三个布局原语的真实 API。Runner 会按输入 `size` 加载 [`components_common.md`](./components/components_common.md) 与对应的 [`components_2x2.md`](./components/components_2x2.md) 或 [`components_2x4.md`](./components/components_2x4.md)。布局几何规范根据输入 `size` 分别见 [`layout_patterns_2x2.md`](./layouts/layout_patterns_2x2.md) 与 [`layout_patterns_2x4.md`](./layouts/layout_patterns_2x4.md)。生成侧可用资源只来自当前输入的 `assetCandidates`。

文档中的规则分为两层：

- **runtime 能力**：组件实现实际能够接收或容错的属性。
- **生成侧约束**：模型生成卡片时允许使用的能力。生成侧约束可以比 runtime 更严格。

当两者不同时，以生成侧约束为准。

动态数据必须保留真实显示 Prop，并仅用 `dataIds` 记录输入中的数据 `id`。`dataIds` 不得用于 `Card`、`Stack`、`Grid` 或视觉与布局属性。

`dataIds` 只能逐字引用当前输入 `data[].id` 中真实存在的值。通常一个显示 Prop 对应一个 ID；`EventCard.time` 是唯一例外，可按 `[dtStartId, dtEndId]` 绑定开始与结束两个 ID，具体写法见当前尺寸加载的组件文档。根据 `userQuery` 概括出的卡片标题、区块标签、静态单位和按钮文案属于静态 UI 文案，不需要绑定；只有输入 `data[]` 明确提供了对应业务字段时，标题或副标题才绑定。不得按业务域猜测或虚构 `calendar.cardTitle`、`memory.cardTitle` 等 ID。

## 2. 布局原语真实 API

### 2.1 通用数值语义

- JSX 数值必须使用表达式，例如 `gap={8}`、`basis={12}`；`Card.size` 是语义枚举，使用字符串 `size="2x2"` 或 `size="2x4"`。
- 不要把 px 数值写成字符串，例如不要写 `gap="8"` 或 `basis="12"`。
- enum 和特殊关键字使用字符串，例如 `direction="row"`、`width="full"`。
- 对布局尺寸 Props 传入数字时，React 会按 CSS px 使用；项目中 vp 与 px 使用相同数值进行 1:1 预览。
- `width="full"`、`height="full"` 会解析为 `100%`。

### 2.2 Card

`Card` 是每张生成卡片唯一允许的根组件。

| Prop | JSX 类型 | runtime 默认值 | 生成侧规则 |
|---|---|---|---|
| `children` | `ReactNode` | — | 卡片内容，只放生成安全组件 |
| `size` | `"2x2" \| "2x4"` | `"2x2"` | 生成侧必选；必须与输入任务顶层 `size` 完全一致 |
| `appearance` | Card appearance enum | 无 | 生成卡片必选，合法值见第 3 节 |
| `background` | CSS background string | 根据 appearance 或 surface | runtime 支持，但生成代码禁止使用 |
| `padding` | `number \| string` | `12` | 通常省略；安全边距固定使用默认 12 |
| `direction` | `"column" \| "row"` | `"column"` | 只使用这两个值 |
| `gap` | `number` | `0` | 数字表示 px；常用 0、2、4、8 |
| `align` | CSS `align-items` 值 | 未设置 | 推荐 `"stretch"`、`"flex-start"`、`"center"`、`"flex-end"` |
| `justify` | `"start" \| "center" \| "end" \| "between"` | 未设置 | runtime 映射为对应 flex 对齐方式 |

尺寸映射：

| 输入任务 `size` | JSX | Card 尺寸 | 默认 padding | 安全内容区 | 布局规范 |
|---|---|---:|---:|---:|---|
| `"2x2"` | `<Card size="2x2">` | 160 × 160vp | 12vp | 136 × 136vp | [`layout_patterns_2x2.md`](./layouts/layout_patterns_2x2.md) |
| `"2x4"` | `<Card size="2x4">` | 320 × 160vp | 12vp | 296 × 136vp | [`layout_patterns_2x4.md`](./layouts/layout_patterns_2x4.md) |

输入与生成链路：

- 原始任务顶层的 `size` 是布局路由字段，不是业务数据绑定字段。
- `jsx_runner/data_processing.py` 在 raw task 转换为 `userQuery/size/actions/data/icons` 时原样保留 `size`，不将它过滤或放入 `data`。
- Runner 将处理后的 `size` 传给模型，并只加载对应尺寸的布局文档。
- 生成的 `Card.size` 必须与任务 `size` 相同；不允许将 `"2x4"` 任务降级为 `"2x2"`，反之亦然。

行为说明：

- runtime 将 `"2x2"` 解析为 160 × 160px，将 `"2x4"` 解析为 320 × 160px。
- 为兼容旧 catalog 和历史预览，runtime 仍可容错数字 `size`，并将其解析为等宽高方形；新的生成 JSX 禁止使用该兼容路径。
- 合法 `appearance` 会启用 20px 圆角、卡片调色板和生成卡专属组件样式。
- 没有合法 `appearance` 时会使用 catalog／普通容器样式，不符合生成卡要求。
- `className`、`style` 和原生 DOM 透传属于 runtime 能力，生成代码禁止使用。

### 2.3 Stack

`Stack` 是 Flex 布局原语，用于纵向流、横向分组、固定槽位、弹性内容区和锚点定位。

| Prop | JSX 类型 | runtime 默认值 | 生成侧语义 |
|---|---|---|---|
| `children` | `ReactNode` | — | 子组件 |
| `direction` | `"column" \| "row"` | `"column"` | 纵向或横向排列 |
| `gap` | `number` | `0` | 子项间距，数字表示 px |
| `align` | CSS `align-items` 值 | `"stretch"` | 推荐 `"stretch"`、`"flex-start"`、`"center"`、`"flex-end"` |
| `justify` | `"start" \| "center" \| "end" \| "between"` | `"start"` | 主轴对齐；`between` 映射为 `space-between` |
| `wrap` | `boolean` | `false` | 浏览器 runtime 兼容能力；不属于正式生成合同，生成卡禁止使用 |
| `flex` | `0 \| 1` | 未设置 | `1` 填充剩余空间；`0` 使用内容自然尺寸 |
| `basis` | `number \| string` | 未设置 | 固定槽位尺寸；数字转为 px，并优先于 `flex` |
| `width` | `number \| string \| "full"` | 未设置 | `"full"` 表示 `100%` |
| `minWidth` | `number \| string` | `0` | 通常省略，防止 Flex 子项内容撑宽 |
| `height` | `number \| string \| "full"` | 未设置 | `"full"` 表示 `100%` |
| `minHeight` | `number \| string` | 未设置 | 弹性内容区通常显式传 `minHeight={0}` |
| `mt` / `mb` / `ml` / `mr` | `number \| string` | 未设置 | 四方向外边距；优先使用 `gap`，必要时再使用 |
| `position` | `"relative" \| "absolute"` | 未设置 | 建立定位上下文或锚点子项 |
| `top` / `right` / `bottom` / `left` | `number \| string` | 未设置 | 只与定位 Stack 配合；数字表示 px |
| `alignSelf` | CSS `align-self` 值 | 未设置 | 浏览器 runtime 兼容能力；不属于正式生成合同，生成卡禁止使用 |
| `surface` | `"backplate"` | 未设置 | 为 2×4 Type 13 的任一父内容区启用可选受控背板：白色 10% 背景、8px 圆角和 6px 内边距 |

关键规则：

- `basis` 优先于 `flex`。例如 `basis={12}` 会生成固定 12px 标题槽，而不是弹性区。
- 弹性内容区使用 `flex={1} minHeight={0}`，避免内容把卡片撑出安全区。
- 右下角操作使用父级 `position="relative"`，子级 `position="absolute" right={0} bottom={0}`。
- 只有需要边缘锚定的子项使用 `position="absolute"`；其余正文保持正常流式布局，不要改成手工 `top` 坐标。
- 生成卡不得使用 `wrap` 或 `alignSelf`；需要换行时使用允许自然换行的文本组件，需要局部对齐时通过父 Stack 的 `align`／`justify` 或正式布局槽表达。
- Card 已提供 12px padding，因此安全内容区中的 `right={0}`、`bottom={0}` 已对应卡片外边缘的 12px 安全距离。
- `surface="backplate"` 仅用于布局规范明确要求背板的内容区域；颜色、圆角和内边距由 runtime 固定提供，禁止使用 `style` 重新实现。
- `className`、`style` 和原生 DOM 透传属于 runtime 能力，生成代码禁止使用。

### 2.4 Grid

`Grid` 用于两个同级对象的双列布局和四个同级对象的 2 × 2 网格。

| Prop | JSX 类型 | runtime 默认值 | 生成侧语义 |
|---|---|---|---|
| `children` | `ReactNode` | — | 网格子组件 |
| `columns` | `positive integer \| string` | `2` | 数字生成等宽列；生成代码优先使用正整数 |
| `rows` | CSS grid-template-rows string | 未设置 | 必须写完整尺寸字符串，例如 `"54px 54px"`；数字不是行数 |
| `gap` | `number` | `0` | 同时设置行列间距 |
| `rowGap` | `number` | 继承 `gap` | 单独覆盖行间距 |
| `columnGap` | `number` | 继承 `gap` | 单独覆盖列间距 |
| `flex` | `0 \| 1` | 未设置 | 与 Stack 相同，`1` 填充剩余空间 |
| `basis` | `number \| string` | 未设置 | 与 Stack 相同，优先于 `flex` |
| `width` | `number \| string \| "full"` | 未设置 | `"full"` 表示 `100%` |
| `minWidth` | `number \| string` | `0` | 通常省略 |
| `height` | `number \| string \| "full"` | 未设置 | `"full"` 表示 `100%` |
| `minHeight` | `number \| string` | 未设置 | 必要时传 `0` 防止内容溢出 |
| `align` | CSS `align-items` 值 | 未设置 | 控制单元格内容在块轴的对齐 |
| `justify` | CSS `justify-items` 值 | 未设置 | 推荐 `"start"`、`"center"`、`"end"`、`"stretch"`；这里不使用 `"between"` |
| `mt` / `mb` | `number \| string` | 未设置 | 网格上下外边距 |

`columns` 与 `rows` 的区别：

```jsx
<Grid columns={2} rows="54px 54px" gap={8}>
  ...
</Grid>
```

- `columns={2}` 表示两列，并由 runtime 转为 `repeat(2, minmax(0, 1fr))`。
- `rows="54px 54px"` 是完整 CSS 行模板，表示两行，每行 54px。
- 不要写 `columns="2"`，它会被当作原始 CSS 模板字符串。
- 不要写 `rows={2}`，它不表示“两行”。

### 2.5 合法布局示例

以下示例中的绑定仅在当前输入存在完全相同的 `data[].id`／`actions[].id` 时成立。静态标题来自 `userQuery` 的语义概括，因此不绑定；不得照抄或类推出示例 ID。

流式标题、弹性内容区和底部操作区：

```jsx
<Card size="2x2" appearance="green-soft">
  <Stack flex={0}>
    <SingleLineTitle title="内存清理" />
  </Stack>

  <Stack flex={1} minHeight={0} width="full" minWidth={0} mt={2} align="flex-start" justify="center">
    <ProgressCircleSingle
      value={43.75}
      icon="resources/base/media/externaldrive_fill.svg"
      displayValue="4.5GB"
      label="剩余内存"
      ariaLabel="内存已用43.75%，可用4.5GB"
      appearance="card"
      dataIds={{
        value: "memory.usedPercent",
        displayValue: "memory.availableText",
      }}
    />
  </Stack>

  <Stack basis={36} height={36} width="full" mt={8}>
    <PillButton
      label="一键清理"
      appearance="card"
      actionId="memory.cleanNow"
    />
  </Stack>
</Card>
```

双列内容区：

```jsx
<Grid columns={2} gap={8} flex={1} align="center">
  <Stack align="center">
    <ProgressCircle
      icon="resources/base/media/phone_fill.svg"
      externalText="68%"
      ariaLabel="手机电量68%"
      appearance="card"
      dataIds={{ externalText: "device.phoneBatteryText" }}
    />
  </Stack>
  <Stack align="center">
    <ProgressCircle
      icon="resources/base/media/kidswatch_fill.svg"
      externalText="52%"
      ariaLabel="手表电量52%"
      appearance="card"
      dataIds={{ externalText: "device.watchBatteryText" }}
    />
  </Stack>
</Grid>
```

## 3. Card 模式与颜色责任

卡片背景分为通用／浅色渐变和深色渐变两类。背景类型同时决定字体、按钮背板和组件 Icon 的颜色；生成代码不得在业务组件中逐项硬编码这些颜色。

| 卡片背景 | 字体模式 | `PillButton` | `CircleButton` |
|---|---|---|---|
| 通用背景／浅色渐变 | 亮色字体：主文本黑色 100%，次文本黑色 60% | 背板使用顶部渐变色 10%；文本和 Icon 使用顶部渐变色 | 背板使用顶部渐变色 100%；Icon 使用白色 100% |
| 深色渐变 | 暗色字体：主文本白色 100%，次文本白色 60% | 白色背板；文本和 Icon 使用背景顶部渐变色 | 白色背板；Icon 使用应用功能主题色 |

颜色责任固定为：

- 外层 `Card.appearance` 选择卡片背景和整张卡片的语义调色板。
- 业务组件在生成卡片中只传 `appearance="card"`，消费外层 Card 提供的颜色。
- `PillButton.variant`、`PillButton.color`、`CircleButton.variant`、`CircleButton.color` 只用于普通 catalog 模式；Card 模式下不用于改写卡片配色。
- `trackColor`、`barColor` 属于实现层覆盖属性，生成代码通常不填写。
- 不在 JSX 中使用 `style`、`className`、硬编码色值或渐变绕过 Card 调色板。

`appearance="card"` 不是可脱离 Card 独立使用的主题。以下组件在生成卡片时，必须位于带合法 `appearance` 的 `<Card>` 内，并同时在组件自身传入 `appearance="card"`：

- `PillButton`
- `CircleButton`
- `ProgressCircleSingle`
- `ProgressCircle`
- `NumericRatio`
- `NumericRatioStack`

当前正式生成 API 的 Card 背景映射如下：

| `Card.appearance` | 对应设计背景 | 字体模式 |
|---|---|---|
| `"blue-soft"` | 通用／蓝色浅色渐变 | 亮色 |
| `"pink-soft"` | `#E64566` 红色浅色渐变 | 亮色 |
| `"yellow-soft"` | `#F7CE00` 黄色浅色渐变 | 亮色 |
| `"green-soft"` | `#64BB5C` 绿色浅色渐变 | 亮色 |
| `"cyan-soft"` | `#46B1E3` 蓝青色浅色渐变 | 亮色 |
| `"sunny-gradient"` | 晴天蓝色深色渐变 | 暗色 |
| `"cloudy-gradient"` | 多云多椭圆深色渐变 | 暗色 |
| `"slate-gradient"` | 雨天多椭圆深色渐变 | 暗色 |
| `"orange-gradient"` | 运动健康深色渐变 | 暗色 |
| `"purple-gradient"` | 睡眠深色渐变 | 暗色 |
| `"type0-gradient"` | Type 0 专属多椭圆深色背景 | 暗色 |

`"neutral-soft"` 仅在 runtime 中保留用于兼容历史 JSX，不属于新版设计源的正式背景，不允许新生成。

### 3.1 `Card.appearance` 选择规则

先根据业务所属应用或明确的场景语义选择 `Card.appearance`，不要仅根据视觉偏好、Icon 颜色或内容中偶然出现的颜色词选择背景。

| 业务语义／适用应用 | `Card.appearance` | 选择说明 |
|---|---|---|
| 通用场景；应用 Icon 颜色复杂、无法确定单一主色；WeMeeting、电子邮件、信息、云空间、钱包、浏览器、音乐、图库 | `"blue-soft"` | 对应设计规范中的通用背景或蓝色浅色渐变 |
| 阅读、日历 | `"pink-soft"` | 对应 `#E64566` 红色浅色渐变；runtime 的枚举名称为 `pink-soft` |
| 备忘录、文件管理 | `"yellow-soft"` | 对应 `#F7CE00` 黄色浅色渐变 |
| 电话 | `"green-soft"` | 对应 `#64BB5C` 绿色浅色渐变 |
| 地图 | `"cyan-soft"` | 对应 `#46B1E3` 蓝青色浅色渐变 |
| 天气且天气状态为晴天 | `"sunny-gradient"` | 晴天专属蓝色深色渐变 |
| 天气且天气状态为多云 | `"cloudy-gradient"` | 多云专属多椭圆深色背景 |
| 天气且天气状态为雨天 | `"slate-gradient"` | 对应雨天深色渐变；不能用于晴天 |
| 睡眠监督／睡眠 | `"purple-gradient"` | 对应睡眠深色渐变 |
| 运动健康 | `"orange-gradient"` | 对应运动健康深色渐变 |
| Type 0 布局 | `"type0-gradient"` | 仅允许 Type 0 使用；禁止用于 Type 1–12 及其他布局 |

选择顺序固定为：

1. 输入明确属于表中的应用或场景时，使用该行指定的 `Card.appearance`。
2. 输入没有专属映射，但符合“通用场景”或“应用 Icon 颜色复杂、无法确定单一主色”时，使用 `"blue-soft"`。
3. 天气场景必须继续判断晴天、多云或雨天，不能仅凭“天气”选择同一种背景。
4. 无法由以上规则确定时，不得根据相近颜色自行推断；应报告缺少对应的背景映射。

### 3.2 多椭圆背景的尺寸适配

`"cloudy-gradient"`、`"slate-gradient"`、`"type0-gradient"` 使用多椭圆背景层，而不是单一线性渐变。背景层只由 `Card.appearance` 创建，业务 JSX 不得自行添加椭圆 DOM、`background` Prop 或硬编码样式。

| Card 尺寸 | 右下椭圆 | 左下椭圆 | 上方椭圆 | 背板 |
|---|---|---|---|---|
| `2x2` · 160×160vp | 100×100vp @ 96/80 | 160×160vp @ -40/70 | 210×210vp @ -25/-90 | 160×160vp，白色 5%，模糊 50vp |
| `2x4` · 320×160vp | 220×100vp @ 180/80 | 280×160vp @ -60/70 | 420×210vp @ -50/-90 | 320×160vp，白色 5%，模糊 50vp |

两种 Card 的圆角均由 Card 规格提供，背景层不再自带 160×160vp 或 24px 圆角约束。

## 4. Icon 使用范围与资源路径

生成代码中的任何 `icon`、`src` 或 `checkIcon` 都必须逐字使用当前输入 `assetCandidates[].src` 中已有的值，并根据同一候选项的 `description` 判断语义是否适合当前位置。候选列表为空时不得输出资源属性；不得缩写路径或根据语义猜测文件名。

| Icon 类型 | 允许位置 | 使用方式 |
|---|---|---|
| 应用 Icon | 单一应用来源时的标题区右上角 | 通过 `SingleLineTitle.icon` 或 `DoubleLineTitle.icon` 传入，通常配合 `iconFit="cover"`；信息来自多个应用时不展示应用 Icon |
| 天气 Icon | 标题区右上角 | 通过标题组件的 `icon` 传入，通常使用默认 `iconFit="contain"` |
| 通用功能 Icon | ProgressCircle、NumericRatio、按钮等组件内部 | 通过对应业务组件的 `icon` 传入 |
| 通用功能 Icon | 标题区右上角 | 禁止；不得用来替代应用来源或天气状态 Icon |

资源引用规则：

- 将候选 `src` 视为不透明字符串，逐字复制当前任务中选中的完整值；不得补扩展名、补目录、删减路径段或截成文件名。
- 文档和 runtime 中是否存在同名本地文件，不构成生成侧可使用该资源的依据。
- 应用 Icon 和天气 Icon 均为 20 × 20vp、圆角 4vp；应用 Icon 通常使用 `cover`，天气 Icon 通常使用 `contain`。
- 只有信息明确来自单一应用时才展示该应用 Icon；信息来自多个应用时，不得选择其中任一应用 Icon 作为标题 Icon，也不得并列展示多个应用 Icon。
- 只能使用当前输入 `assetCandidates` 中列出的资源 `src`，不得根据语义虚构文件名。
- 有业务语义的标题 Icon 必须提供 `iconAlt`；`CircleButton` 必须提供 `ariaLabel`。

## 5. 设计规则与 JSX 责任归属

设计规范中的“位置、间距、允许区域”不自动等于业务组件 Props。生成 JSX 时按以下责任划分：

| 规则类型 | JSX 责任方 | 示例 |
|---|---|---|
| 组件内部尺寸、字体、颜色和内部间距 | 业务组件自身 | `PillButton` 自身负责 136 × 36px、圆角 30px；`CircleButton` 自身负责 36 × 36px 和 20 × 20px Icon 居中 |
| 组件之间的间距 | 外层 `Stack` 或 `Grid` | Badge 与标题间距 8px 使用 `Stack gap={8}` |
| 卡片中的顶部、主内容、底部操作区 | 外层 `Card`、`Stack`、`Grid` | PillButton 放入固定 36px 高的底部操作槽；外层布局不覆盖按钮的 136px 宽度或 30px 圆角 |
| 右下角绝对定位 | 具有 `position="relative"` 的父 `Stack` 和绝对定位子 `Stack` | CircleButton 使用 `right={0}`、`bottom={0}` 的 36 × 36px 槽位 |
| 背景、字体和按钮／Icon 调色板 | `Card.appearance` | 业务组件使用 `appearance="card"` 消费 Card 颜色 |

不要把设计构成字段直接写成未知 Props。例如 `container`、`position` 不是 `PillButton` 或 `CircleButton` 的 JSX Props；`percent`、`current`、`total` 是业务字段，也必须先映射为具体进度组件的真实 Props。
