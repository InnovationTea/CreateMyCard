---
name: phone-widget-2x4-core
description: 生成 2×2 或 2×4 卡片时使用的 JSX 协议、绑定规则与布局原语合同。
---

# Core Generation Contract

本文件规定生成声明式卡片 JSX 时必须遵守的核心协议和 `Card + Region` 语义布局接口边界。Runner 会按输入 `size` 加载当前尺寸的 `components`、`component-combinations`、`layouts` 与 `composition` Skill。生成侧可用资源只来自当前输入的 `assetCandidates`。

文档中的规则分为两层：

- **runtime 能力**：组件实现实际能够接收或容错的属性。
- **生成侧约束**：模型生成卡片时允许使用的能力。生成侧约束可以比 runtime 更严格。

当两者不同时，以生成侧约束为准。

动态数据必须保留真实显示 Prop，并仅用 `dataIds` 记录输入中的数据 `id`。`dataIds` 不得用于 `Card`、`Stack`、`Grid` 或视觉与布局属性。

`data[].value` 是动态字段的预览样例，不会覆盖 `userQuery` 明确给出的同义当前事实。单 ID 绑定冲突时，可见 Prop 使用 `userQuery` 中的具体值，但仍必须绑定原数据 `id`，以便后续实时数据继续更新同一显示 Prop。多 ID 组合字段不从查询文本反向猜测各字段值。

`dataIds` 只能逐字引用当前输入 `data[].id` 中真实存在的值。通常一个显示 Prop 对应一个 ID；`EventCard.items[].time` 可按 `[dtStartId, dtEndId]` 绑定开始与结束两个 ID，`EmphasisText.mainText` 只允许一个 ID，仅 `secondaryText` 可按组件文档使用有序数组，并必须用 `secondaryTextTemplate` 为各值保留语义标签。根据 `userQuery` 概括出的卡片标题、区块标签、静态单位和按钮文案属于静态 UI 文案，不需要绑定；只有输入 `data[]` 明确提供了对应字段时，标题或副标题才绑定。不得按业务域猜测或虚构 `calendar.cardTitle`、`memory.cardTitle` 等 ID。

## 2. 布局原语真实 API

2×4 的模型提交只使用 `Card.layout + Region.slot/variant`，具体接口见layouts Skill。模型不得输出 `Stack` 或 `Grid`；下述布局原语仅说明程序展开后的 runtime 合同，不属于 2×4 语义 JSX 的生成接口。2×2 提交规则不变。

### 2.1 通用数值语义

- JSX 数值必须使用表达式，例如 `gap={8}`、`height={36}`；`Card.size` 是语义枚举，使用字符串 `size="2x2"` 或 `size="2x4"`。
- 不要把 px 数值写成字符串，例如不要写 `gap="8"` 或 `height="36"`。
- enum 和特殊关键字使用字符串，例如 `direction="row"`、`width="full"`。
- 对布局尺寸 Props 传入数字时，React 会按 CSS px 使用；项目中 vp 与 px 使用相同数值进行 1:1 预览。
- `width="full"`、`height="full"` 会解析为 `100%`。

### 2.2 Card

`Card` 是每张生成卡片唯一允许的根组件。下表列出普通 runtime API；2×4 模型提交只使用语义接口的 size、appearance、layout、可选 flow 和 aria-label，不填写下表中的几何属性。2×2 仍使用普通 Card/Stack/Grid。

| Prop | JSX 类型 | runtime 默认值 | 生成侧规则 |
|---|---|---|---|
| `children` | `ReactNode` | — | 卡片内容，只放生成安全组件 |
| `size` | `"2x2" \| "2x4"` | `"2x2"` | 生成侧必选；必须与输入任务顶层 `size` 完全一致 |
| `appearance` | Card appearance enum | 无 | 生成卡片必选，合法值见第 3 节 |
| `background` | CSS background string | 根据 appearance 或 surface | runtime 支持，但生成代码禁止使用 |
| `padding` | `number \| string` | `12` | 通常省略；安全边距固定使用默认 12 |
| `direction` | `"column" \| "row"` | `"column"` | 2×2 生成侧必选；2×4 由语义骨架生成 |
| `gap` | `number` | `0` | 数字表示 px；常用 0、2、4、8 |
| `align` | CSS `align-items` 值 | 未设置 | 推荐 `"stretch"`、`"flex-start"`、`"center"`、`"flex-end"` |
| `justify` | `"flex-start" \| "center" \| "flex-end" \| "space-between"` | 未设置 | 使用标准 CSS Flex 对齐值 |

尺寸映射：

| 输入任务 `size` | `Card.size` | Card 尺寸 | 默认 padding | 安全内容区 | 布局规范 |
|---|---|---:|---:|---:|---|
| `"2x2"` | `"2x2"` | 160 × 160vp | 12vp | 136 × 136vp | `2×2 layouts` Skill |
| `"2x4"` | `"2x4"` | 320 × 160vp | 12vp | 296 × 136vp | `2×4 layouts` Skill |

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

### 2.3 程序内部布局原语

`Stack` 与 `Grid` 只由语义布局程序生成，用于实现 `Region.variant` 的尺寸、方向、弹性、间距和对齐。2×4 模型输出不得包含这两个标签；浏览器 findings 中出现的 `Stack/Grid` 也是展开结果，不得复制回语义 JSX。需要改变几何结构时更换 `Card.layout` 或 `Region.variant`；多个同级占比值使用 `NumericRatioStack`。

### 2.5 合法布局示例

以下示例中的绑定仅在当前输入存在完全相同的 `data[].id`／`actions[].id` 时成立。静态标题来自 `userQuery` 的语义概括，因此不绑定；不得照抄或类推出示例 ID。

以下仅展示 main Region；完整卡片仍须按 layouts Skill 填满其余固定槽。

标题、内容与底部操作区：

```jsx
<Region slot="main" variant="wide-title-content-action">
  <SingleLineTitle title="内存清理" />
  <ProgressCircleSingle
      size="compact"
      value={43.75}
      icon="externaldrive_fill.svg"
      displayValue="4.5GB"
      label="剩余内存"
      ariaLabel="内存已用43.75%，可用4.5GB"
      appearance="card"
      dataIds={{
        value: "memory.usedPercent",
        displayValue: "memory.availableText",
      }}
    />
  <PillButton label="一键清理" appearance="card" actionId="memory.cleanNow" />
</Region>
```

两个同级占比：

```jsx
<Region slot="main" variant="wide-title-double-progress">
  <SingleLineTitle title="设备电量" />
  <ProgressCircle size="sm"
      icon="phone_fill.svg"
      externalText="68%"
      ariaLabel="手机电量68%"
      appearance="card"
      dataIds={{ externalText: "device.phoneBatteryText" }}
    />
  <ProgressCircle size="sm"
      icon="kidswatch_fill.svg"
      externalText="52%"
      ariaLabel="手表电量52%"
      appearance="card"
      dataIds={{ externalText: "device.watchBatteryText" }}
    />
</Region>
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

当前正式生成 API 的 Card 背景映射如下。单色背景支持 `2x2` 与 `2x4`；融球背景只支持 `2x2`：

| `Card.appearance` | 对应设计背景 | 字体模式 | 支持尺寸 |
|---|---|---|---|
| `"solid-blue"` | `#E5EDFE` | 单色 | `2x2`、`2x4` |
| `"solid-orange"` | `#FFF3E6` | 单色 | `2x2`、`2x4` |
| `"solid-green"` | `#F0FFE6` | 单色 | `2x2`、`2x4` |
| `"solid-cyan"` | `#E6FDFF` | 单色 | `2x2`、`2x4` |
| `"solid-purple"` | `#EDE6FF` | 单色 | `2x2`、`2x4` |
| `"orb-orange"` | 橘色融球 | 暗色 | 仅 `2x2` |
| `"orb-blue"` | 蓝色融球 | 暗色 | 仅 `2x2` |
| `"orb-purple"` | 紫色融球 | 暗色 | 仅 `2x2` |
| `"orb-green"` | 绿色融球 | 暗色 | 仅 `2x2` |

`"neutral-soft"`、`"blue-soft"`、`"pink-soft"`、`"yellow-soft"`、`"green-soft"`、`"cyan-soft"`、`"sunny-gradient"`、`"cloudy-gradient"`、`"slate-gradient"`、`"orange-gradient"`、`"purple-gradient"`、`"type0-gradient"` 仅在 runtime 中保留用于兼容历史 JSX，不属于新版设计源的正式背景，不允许新生成。历史 `2x4` JSX 若传入融球或深色渐变别名，runtime 会降级到同色系单色背景。

### 3.1 `Card.appearance` 选择规则

先根据业务所属应用或明确的场景语义选择 `Card.appearance`，不要仅根据视觉偏好、Icon 颜色或内容中偶然出现的颜色词选择背景。

| 业务语义／适用应用 | `Card.appearance` | 选择说明 |
|---|---|---|
| 通用场景；多个意图或垂域；信息或组件数超过 3 个 | `"solid-blue"` | 使用适用于系统信息和通用信息展示的蓝色背景 |
| 天气、出行导航、办公效率、系统信息 | `"solid-blue"`；`2x2` 可选 `"orb-blue"` | `2x4` 必须使用单色背景 |
| 日程、日历 | `"solid-orange"` | 单色背景 |
| 电量、通话、运动健康 | `"solid-green"`；`2x2` 运动场景可选 `"orb-orange"` | `2x4` 必须使用单色背景 |
| 耳机 | `"solid-cyan"` | 单色背景 |
| 睡眠、冥想、晚安 | `"solid-purple"`；`2x2` 可选 `"orb-purple"` | `2x4` 必须使用单色背景 |
| 充电 | `"solid-green"`；`2x2` 可选 `"orb-green"` | `2x4` 必须使用单色背景 |
| `2x2` 的运动、赛事、倒计时、卡路里、热量 | `"orb-orange"` | 融球仅限 `2x2` |

选择顺序固定为：

1. 先检查 Card 尺寸；`2x4` 只能从五种 `solid-*` 单色背景中选择，不得选择 `orb-*`。
2. 输入明确属于表中的应用或场景时，使用该行指定的单色背景。
3. 只有 `2x2` 才能根据表中明确列出的意图改选对应融球背景。
4. 无法由以上规则确定时，不得根据相近颜色自行推断；应使用 `"solid-blue"` 通用背景。

### 3.2 融球背景的尺寸限制

`"orb-orange"`、`"orb-blue"`、`"orb-purple"`、`"orb-green"` 使用融球背景。JSX runtime 按视觉规范叠加椭圆色块和背景模糊，不用单一线性渐变或图片替代。融球主题只允许用于 `Card.size="2x2"`；`2x4` 必须选择单色背景。背景只由 `Card.appearance` 创建，业务 JSX 不得自行添加椭圆 DOM、`background` Prop 或硬编码样式。

下面的椭圆参数由 runtime 统一实现，业务 JSX 不需要额外创建背景层：

| Card 尺寸 | 右下椭圆 | 左下椭圆 | 上方椭圆 | 背板 |
|---|---|---|---|---|
| `2x2` · 160×160vp | 100×100vp @ 96/80 | 160×160vp @ -40/70 | 210×210vp @ -25/-90 | 160×160vp，白色 5%，模糊 50vp |

融球圆角由 `2x2` Card 规格提供，背景层不再自带圆角约束。

## 4. Icon 使用范围与资源文件名

生成代码中的任何 `icon`、`src` 或 `checkIcon` 都必须逐字使用当前输入 `assetCandidates[].src` 中已有的模型侧值，并根据同一候选项的 `description` 判断语义是否适合当前位置。Runner 会把默认媒体目录 `resources/base/media/` 下的普通资源转换成 `icon_weather1.svg` 这样的文件名后再送给模型；生成 JSX 直接复制该文件名，不得重新补目录。候选列表为空时不得输出资源属性，也不得根据语义猜测文件名。

| Icon 类型 | 允许位置 | 使用方式 |
|---|---|---|
| 应用或天气 Icon | `InfoBlock` 等支持 Icon 的业务组件内部 | 通过对应业务组件的 Icon Prop 传入；不得放入标题组件 |
| 通用功能 Icon | ProgressCircle、NumericRatio、按钮等组件内部 | 通过对应业务组件的 `icon` 传入 |
| 任意 Icon | 标题区右上角 | 禁止；`SingleLineTitle` 与 `DoubleLineTitle` 均为纯文本标题 |

资源引用规则：

- 将模型输入中的候选 `src` 视为不透明字符串并逐字复制。默认媒体资源通常只有文件名；不得补 `resources/base/media/`、补扩展名或改写名称。非默认目录资源若仍包含路径，则保留输入给出的路径，不得自行截短。
- JSX Runtime 和后续协议处理层会把不含 `/` 的普通文件名统一解析为 `resources/base/media/<文件名>`；该补全不会改变组件布局和视觉样式。
- 文档和 runtime 中是否存在同名本地文件，不构成生成侧可使用该资源的依据。
- 应用 Icon 和天气 Icon 的尺寸、裁切方式由实际承载它们的业务组件决定，不再使用标题区 20 × 20vp 规格。
- 只有信息明确来自单一应用时才展示该应用 Icon；信息来自多个应用时，不得选择其中任一应用 Icon 作为代表，也不得并列展示多个应用 Icon。
- 只能使用当前输入 `assetCandidates` 中列出的资源 `src`，不得根据语义虚构文件名。
- `CircleButton` 必须提供 `ariaLabel`。

## 5. 设计规则与 JSX 责任归属

设计规范中的“位置、间距、允许区域”不自动等于业务组件 Props。生成 JSX 时按以下责任划分：

| 规则类型 | JSX 责任方 | 示例 |
|---|---|---|
| 组件内部尺寸、字体、颜色和内部间距 | 业务组件自身 | `PillButton` 自身负责 136 × 36px、圆角 30px；`CircleButton` 自身负责 36 × 36px 和 20 × 20px Icon 居中 |
| 标题与 Badge 的间距 | 语义布局程序 | Badge 必须作为 Region 标题后的直属节点，由程序生成 8px 横向标题行；模型不得使用 Stack/Grid 包裹标题与 Badge，也不得把 Badge 放入内容 Stack/Grid |
| 卡片中的顶部、主内容、底部操作区 | 语义布局程序 | `Region.variant` 决定标题、内容与操作槽；程序展开为底层 `Stack/Grid` |
| 右下角绝对定位 | 2×2 布局原语 | 仅 2×2 的 CircleButton 布局使用相对／绝对定位 Stack；2×4 语义 JSX 不输出该结构 |
| 背景、字体和按钮／Icon 调色板 | `Card.appearance` | 业务组件使用 `appearance="card"` 消费 Card 颜色 |

不要把设计构成字段直接写成未知 Props。例如 `container`、`position` 不是 `PillButton` 或 `CircleButton` 的 JSX Props；`percent`、`current`、`total` 是业务字段，也必须先映射为具体进度组件的真实 Props。

## 数据、动作与单位绑定

### 数据与动作引用共同约定

- `dataIds` 只记录可见显示 Prop 对应的输入 `data[].id`，不参与样式或布局计算。`data[].value` 是预览样例；若 `userQuery` 明确给出同一业务字段的当前具体值，单 ID 绑定的显示 Prop 使用 `userQuery` 中的值并继续绑定原 `dataId`；否则使用样例值。不得用 ID 字符串替代显示内容。
- `dataIds` 的 key 必须是对应组件属性表明确允许绑定的 Prop。通常每个 value 原样引用一个输入中真实存在且当前任务内唯一的 `id`；`EventCard.items[].dataIds.time` 可按 `[dtStartId, dtEndId]` 顺序引用两个 ID，`EmphasisText.dataIds.secondaryText`、`InfoBlock.dataIds.secondaryText` 与 `TableText.items[].dataIds.parameter` 可使用包含两个或更多 ID 的有序数组。`EmphasisText.dataIds.mainText` 与 `TableText.items[].dataIds.label` 只允许一个 ID。不得缩写、改名或虚构 ID。
- 根据 `userQuery` 概括出的卡片标题、区块标签、静态单位和按钮文案是静态 UI 文案，不绑定。标题或副标题只有在当前输入 `data[]` 明确提供对应字段时才绑定；不得按业务域构造 `*.cardTitle`、`*.subtitle` 等不存在的 ID。
- `dataIds` 引用的数据类型必须与目标 Prop 的用途兼容。最终渲染为可见文本的 Prop 可绑定 string、integer 或 number，数字由文本组件直接显示；参与进度计算的 Prop 通常只能绑定 integer 或 number，`ProgressCircle.externalText` 可额外接受纯数字字符串或数字百分比字符串并在组件内部转换。Boolean 优先绑定 `done` 等 boolean Prop。确实需要把 Boolean 显示成双状态文案且输入没有描述性字符串时，必须同时为同一 Prop 提供完整的 `dataValueMaps`，其中 `true`／`false` 都是非空且不同的字符串；禁止只按当前样例值静态翻译。
- `dataValueMaps` 只做 Boolean 到可见文本的响应式映射，不代替 `dataIds`，也不能用于进度值、布局或视觉属性。其 key 必须同时存在于同一对象的 `dataIds`；数组项需要映射时，将 `dataValueMaps` 与该项的 `dataIds` 写在同一个 item 内。
- 布尔值使用表达式，例如 `disabled={true}`，不能写成字符串 `disabled="true"`。
- Boolean 可直接用于 `disabled`、`done` 等 boolean Prop。文本 Prop 不接受裸 Boolean；只有同时通过同名 `dataIds` 和完整 `dataValueMaps={{ prop: { true: "…", false: "…" } }}` 声明双状态文案时，才允许把 Boolean 响应式显示为文本。
- 所有来自输入 `data` 的可见业务值都必须绑定；通常一个显示 Prop 只绑定一个数据 ID。只有组件属性表明确声明数组形式时，才能让同一显示 Prop 绑定多个 ID。`Card`、`Stack`、`Grid`、Icon、appearance、尺寸、位置和颜色等视觉属性不得绑定。
- 每个原子业务事实在整张卡片中必须只有一个可见 owner，标题也计入 owner。一个 ID 已绑定到可见文本 Prop 或作为有序 ID 数组成员进入某段文本后，不得再绑定到另一段可见文本；也不得通过静态标题、标签或同义改写重复表达同一事实。同一数值可以同时驱动进度图形和该图形配套的唯一数值文本。若 `SecondaryBody`、`TableText` 等组件的最少条目数会迫使事实重复，应改选合同匹配的组件，不能复制数据凑数。
- 多个输入字段不得在 JSX 中手工拼成一个动态字符串。应使用组件的多 item 模式、拆成多个组件，或使用合同明确允许的有序 ID 数组；`EventCard.items[].time` 用 ` – ` 组合开始／结束时间，`EmphasisText.secondaryText` 与 `InfoBlock.secondaryText` 可用 ` ｜ ` 组合多个紧密关联的短字段，其中 `EmphasisText` 的多 ID 次文本必须通过 `secondaryTextTemplate` 为各值保留语义标签；`TableText.items[].parameter` 使用紧凑连接符 `｜`；`EmphasisText.mainText` 不允许拼接多个业务字段。添加或删除绑定不得改变其余 Props、组件树和槽位尺寸。
- 静态 `label`、`unit` 和 `separator` 可以说明动态值，但必须遵守对应组件合同，不得改变数值和业务语义。有单位槽的组件可为独立数字或纯数字字符串声明静态单位，保留原值及精度；完整带单位字符串必须保留完整，不得自行拆分或补写单位。
- 格式化字符串只能绑定到接受字符串的显示 Prop；`EmphasizedData` 会自动拆分完整字符串，生成代码仍原样填写 `value="25 分钟"`。`ProgressCircle` 只绑定 `externalText`，由组件内部解析其中的数字驱动圆环；其他进度组件仍按各自属性表绑定实际进度值。`ProgressCircleSingle.value` 在没有独立数值字段时允许绑定完整的格式化百分比字符串。
- `actionId` 只能原样引用输入 `actions[].id`。模型输入中的 `actions[].description` 是映射后的推荐按钮术语，不是上游原始动作描述或业务数据；只能用于选择动作，并可作为绑定该动作的按钮内简短 `label`／`text`／`ariaLabel`。禁止把该术语或改写后的操作说明放入标题、正文、摘要、数据项或按钮外的任何可见内容；按钮已经表达操作后，不得再生成“点击／点开／打开／查看／进入……”等引导文案重复说明该操作。一个控件最多引用一个动作，同一 `actionId` 在一张卡片中最多使用一次。

### 1.2 动态数据与显式单位

- 原始数据及其类型不变。有独立 `unit` 槽的组件（EmphasizedData、InfoBlock、NumericRatio、ProgressLine2 / ProgressLine2WithData），绑定无单位数字时，最终 JSX 使用原始数值加显式静态 `unit`，例如 `value={80} unit="%" dataIds={{value:"earphone.batteryLevel"}}`。
- 纯数字字符串如 `"80.00"` 也可配合显式单位，但必须保留字符串及其精度，不能擅自改为数字 `80`。完整带单位文本如 `"80%"`、`"4.60 公里"`、`"7小时1分"` 原样绑定，不再添加静态单位，也不拆成写死的业务数据。
- 单位依据当前输入的明确说明填写，不能根据字段名称猜测。显式 `unit=""` 关闭对裸数字的额外单位，独立 `dataIds.unit` 必须保留。单位冲突不得冒充单位换算。
- 没有单位槽的普通文本属性继续使用绑定层兼容格式化；不得给 SecondaryBody.items 等不支持单位属性的结构添加 `unit`。进度计算参数始终保留原值，百分比组件既有的取整与默认百分比语义不变。
- 动态完整文本仍由组件按原有设计拆为数字和小单位，生成代码不能把当前样例中的数字或单位拆成写死的业务数据。

## 输入事实与字段表绑定

9. 优先选择可直接展示的描述性字符串。原始 boolean 优先用于组件自身的 boolean 状态 Prop；没有描述性字符串但该状态对用户确有价值时，可通过完整 `dataValueMaps` 声明 `true`／`false` 两种文案。不得直接显示 `true`／`false`，也不得只根据当前样例值写死一个状态；不重要的状态仍应省略。
10. `userQuery` 中明确给出的当前事件名、对象名、地点、时间或状态优先于同义单一数据字段的预览样例值。当两者冲突时，字段表保留 `userQuery` 中的具体值，并继续记录该动态字段原有的 `dataId`；预览样例只用于 `userQuery` 没有给出对应具体值的情况。同一显示 Prop 绑定多个 ID 时，不根据查询文本猜测各字段的拆分值。
- 对最终展示的动态字段保留输入 `data` 中的原始数据 `id`。选定真实 JSX Prop 后，按当前尺寸的 `components` Skill 记录 `dataIds`／`actionId`。
操作组件只在输入提供真实 Action 时创建。模型输入中的 `actions[].description` 是映射后的推荐按钮术语，不是上游原始动作描述或可展示的业务字段；只能用于对应按钮内部的短文案。禁止将该术语或改写内容作为标题、正文、摘要、数据项或其他按钮外文案展示。独立按钮计为一个布局模块，按钮内部的文本和 Icon 不重复计数；同一个 `actionId` 在一张卡片中最多使用一次，不得同时用 `PillButton`、`CircleButton` 或 `CardButton` 重复表达同一操作。

## 2x4 生成补充约束

### 3.4 数据绑定与禁止项

- 示例中的 `dataIds` 与 `actionId` 只说明绑定位置；实际生成必须替换为输入中真实存在的 ID。
- 需要 Card 语义配色的业务组件传入 `appearance="card"`。
- 模板禁止原生元素、`style`、`className`、spread Props、未知 Props 和硬编码颜色。
- 不得使用硬编码背景模拟 runtime 未公开的 Panel；“左右双区”背板由程序根据 Region.variant 生成，模型不手写 `Stack surface="backplate"`。
