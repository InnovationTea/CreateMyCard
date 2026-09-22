---
name: phone-widget-2x4-layouts
description: 为当前尺寸选择和实现父布局、子布局、槽位、尺寸与对齐。
---

# 2×4 布局容量与语义提交

先按 composition Skill 选择业务分区与布局，再按本接口填槽；尺寸用于容量判断，外壳由程序确定性展开。

## 1. 画布与布局层级

### 1.1 画布约束

| 项目 | 规格 |
|---|---:|
| 卡片尺寸 | 320 × 160vp |
| 圆角 | 20vp |
| 四边安全边距 | 12vp |
| 安全内容区 | 296 × 136vp |

所有可见内容必须限制在 296 × 136vp 安全内容区内，不得侵入 12vp 安全边距。

### 1.2 三层布局模型

2×4 布局分为三个层级：

1. **整卡安全内容区**：程序使用默认安全边距后得到 296 × 136vp。
2. **顶层布局区域**：“上下双区”“左右双区”“左内容右侧双槽”“四槽宫格”定义整卡的区域数量、主要尺寸、间距和固定槽位置。
3. **父内容区内部子布局**：“左右双区”默认在 118 × 112vp 内部安全区使用 Sub-118 子布局；其中一侧使用 Sub-140-D 或 Sub-140-H 时，该侧不使用背板，直接在 142 × 136vp 父区内居中放置 140 × 136vp Sub-140 子布局。“左内容右侧双槽”的 140 × 136vp 左内容区使用 Sub-140 子布局。

Sub 子布局只复用对应 2×2 布局的模块关系，不是新的 2×4 顶层布局。子布局内部模块不重复计入整卡顶层模块数，也不得跨越所属父内容区。

### 1.3 顶层区域与标题作用域

“上下双区”使用一个 296 × 20vp 整卡标题槽；其余顶层布局无公共标题，直接使用完整的 296 × 136vp 安全内容区。

| 区域 | 必要性 | 尺寸 / 弹性 | 布局规则 |
|---|---|---|---|
| 公共标题区 | 仅“上下双区”必选 | 296 × 20vp | 其他顶层布局不生成公共标题槽 |
| 子布局局部标题 | 按所选子布局必选 | 自然高度 | Sub-118 系列标题宽 118vp，相邻纵向模块间距 6vp；Sub-140 系列标题宽 140vp，相邻主要模块间距 8vp |
| 内容区 | 必选 | 由所选骨架分配剩余空间 | 宽高必须由所属布局确定，不得照抄 HTML 参考图中的固定 `top` |
| 操作区 | 按真实 Action 可选 | 固定槽；单个按钮最多占一个半卡宽父区 | 根据 Action 数量、归属和所选布局使用 `PillButton` 或 `CardButton` |
| 主要区域间距 | 按布局必选 | “上下双区”标题后 4vp、两个内容区之间 8vp；左右顶层区域之间 12vp；固定槽之间 8vp | 区域不存在时不保留空槽或相邻间距 |

“左右双区”需要标题时，只能在对应的 118 × 112vp 父内容安全区内部使用局部标题；“左内容右侧双槽”的标题只能属于 140 × 136vp 左内容区内部的 Sub-140 子布局。“上下双区”使用整卡标题，“四槽宫格”不设置标题区。

- 局部标题必须来自用户意图或输入数据，不得为了填充版面虚构。标题会重复正文或剩余区域无法容纳业务组件时，应更换无标题子布局或更换顶层布局。
- `SingleLineTitle` 是纯文本标题，高度固定为 18vp。
- `DoubleLineTitle` 含一行副信息时为 `18 + 4 + 18 = 40vp`；副信息为两行时继续自然增高。
- “上下双区”的整卡标题槽固定为 20vp；局部标题高度记为 `T`，Sub-118 和 Sub-140 子布局必须分别按自身的 6vp、8vp 间距公式计算剩余空间。

## 3. 提交边界与容量检查

- 模型选择 `Card.layout`、`Region.slot/variant`，不手写方向、固定宽高、背板、安全边距、按钮位置或 flex，也不在 Region 内输出 `Stack/Grid`。语法与标识映射见本 Skill 下方的语义布局提交接口。
- 表中的尺寸用于选组件和检查容量，不是要求模型把这些尺寸再次写进 JSX。标题自然高度记为 `T`；标题增高、文本换行时，内容可用高度相应减少。
- 内容必须完整显示，不能只检查外壳能否闭合。组件的最小宽高、换行和紧凑能力以组件文档为准；超出槽位时调整组件表达或在允许的阶段更换布局，不靠裁剪、删必需信息或移动 Action 到不相关业务区过检。
- 任一 Sub-118／Sub-140 使用 `ProgressCircleSingle` 时必须传入 `size="compact"`：圆环 44 × 44vp，两行整体高 44vp、三行高 46vp；不得使用默认 52vp 规格。
- 同一语义区域的 `EmphasisText` 与 `EmphasizedData` 合计最多一个。双内容表达核心与辅助，不表示允许两个强调核心。
- 动态显示与 Action 使用输入中的真实 ID；组件需要卡片配色时传 `appearance="card"`。禁止原生元素、style、className、spread、未知 Props 和硬编码颜色，不给业务组件补造 width、height、radius 或 position。2×4 主题使用 core 规定的合法 `solid-*`，不使用旧 `*-gradient` 名称。

## 4. 布局容量与对齐效果

以下对齐、间距和按钮固定槽均由程序保证。模型按业务关系选择相应骨架，并检查内容能否装入。

### 4.1 上下双区

仅用于没有 Action 的一个语义组：整卡标题 → 主体 → 同级属性明细。标题槽 296 × 20vp，标题后间距 4vp，下方内容父区 296 × 112vp。内容统一左对齐、从上方开始，不将核心数值居中。

下明细区只放一组 `TextBlock` 或 `TopTextBottomValue`；前者通常为 2–4 项两行明细，高度可在 48–64vp 内适配；后者仅在本布局的 `details` Region 合法，用于至少 3 项三行指标，固定高 68vp。`TopTextBottomValue` 禁止进入任何其他顶层布局或 Sub-118／Sub-140 内容槽。不能追加其他明细组件、按钮或第四个区域。

按阅读关系选择 `Card.flow`：

| flow | 内容关系与程序分配 | 容量检查 |
|---|---|---|
| `continuous` | 主体自然高度，明细承接剩余高度，连续阅读 | 主体实际高度 + 8vp + 明细最小高度 ≤ 112vp |
| `footer`（默认） | 主体承接剩余高度，明细固定槽贴底 | TextBlock 槽 48vp，主体剩 56vp；TopTextBottomValue 槽 68vp，主体剩 36vp |
| `equal` | 两个内容槽等分扣除间距后的高度 | 每槽 52vp；仅组件均支持时使用，不能放入高 68vp 的 TopTextBottomValue |

不得把组件压缩到低于最小高度。所有 flow 的两个内容槽间距均为 8vp。

```jsx
<Card size="2x4" appearance="solid-green" layout="top-bottom" flow="footer">
  <Region slot="title">{/* 整卡标题及可选 Badge */}</Region>
  <Region slot="primary">{/* 一个核心内容组件或同组内容组合 */}</Region>
  <Region slot="details">{/* 一组 TextBlock 或 TopTextBottomValue */}</Region>
</Card>
```

### 4.2 左右双区

两个父区各为 142 × 136vp，中间 12vp，满足 `142 + 12 + 142 = 296vp`；无公共标题。普通父区自动生成背板，内缩 12vp 后为 118 × 112vp，使用 Sub-118。背板颜色和圆角由 runtime 管理，不在内部重复生成背景。

仅一侧采用 Sub-140-D 或 Sub-140-H 时，程序取消该侧背板，并在父区内居中放置 140 × 136vp 子布局；另一侧仍使用 Sub-118 背板。其他 wide 变体不能进入本布局，也不能同时取消两侧背板。

左右分别按本组数据、标题与直属 Action 选择 variant。内容不得跨区、占用中间间距，任何一侧都禁止 `InfoBlock`。

#### 4.2.1 左右双区通用规则

普通 Sub-118 标题自然高度为 `T`，主要模块间距 6vp。按钮为 118 × 36vp，由内容槽吸收剩余高度后稳定贴底；没有 Action 时使用无按钮 variant，不生成空按钮槽。

#### 4.2.2 Sub-118 父内容区子布局

##### Sub-118-A：核心居中

一个无需标题即可理解的 Data Display 内容，无 Action；可用 118 × 112vp，水平、垂直居中。

##### Sub-118-B：标题单内容

标题 + 一个主体，无 Action。主体左对齐、底端对齐；可用高度为 `112 − T − 6`，单行标题时为 88vp。

##### Sub-118-C：标题双内容

标题 + 核心 + 辅助，无 Action。核心左上对齐，其槽吸收剩余高度；辅助使用自然高度沉底，两内容之间为 6vp，不等分。两个独立内容槽的最小高度之和不得超过 `112 − T − 12`，单行标题时为 82vp。例如核心使用 EmphasizedData，辅助使用 SecondaryBody；一个组件内部多个字段不算双内容。

##### Sub-118-D：标题内容单按钮

标题 + 一个内容 + 本组 PillButton。内容左上对齐并承接剩余高度，按钮贴底；标题、内容和按钮之间各 6vp。内容可用高度为 `112 − T − 12 − 36`，单行标题时只有 46vp。

应选择能在 118 × 46vp 完整显示的组件；例如 ProgressCircleSingle 必须使用 compact。普通组件即使只超出几 vp，也可能侵入按钮间距；切换紧凑模式后仍需检查横向文本是否完整。

### 4.3 非对称内容与固定槽

左内容区 140 × 136vp，使用 Sub-140，禁止 InfoBlock；右侧固定双槽规则见 4.3.2。不提供镜像布局。

#### 4.3.1 共用的 Sub-140 内容区子布局

标题自然高度为 `T`，主要模块间距 8vp。按钮为 136 × 36vp、左对齐，右侧留 4vp。以下七种子布局均可用于左内容区；只有 D、H 可用于左右双区的唯一无背板侧。

##### Sub-140-A：核心居中

一个无需标题即可理解的 Data Display 内容，无 Action；可用 140 × 136vp，水平、垂直居中。

##### Sub-140-B：标题单内容

标题 + 一个主体，无 Action。主体左对齐、底端对齐；可用高度 `136 − T − 8`，单行标题时为 110vp。

##### Sub-140-C：标题内容单按钮

标题 + 一个内容 + 本组 PillButton。内容左上对齐并承接剩余高度，按钮贴底；内容可用高度 `136 − T − 16 − 36`，单行标题时为 66vp。

##### Sub-140-D：标题双列内容可选按钮

标题 + 两个同级 `ProgressCircle size="sm"` + 可选共同 PillButton。两个内容列等宽、居中，横向间距 8vp，每列宽 66vp。单行标题时，有按钮为 66 × 66vp，无按钮为 66 × 110vp；标题增高时高度相应减少。省略按钮时不保留空槽及其间距。

##### Sub-140-F：标题主次内容单按钮

标题 + 核心 + 紧密关联辅助 + 本组 PillButton。主辅均自然高度、左上连续排列，中间 2vp；内容组承接剩余空间，按钮贴底。主辅高度加 2vp 不得超过 `136 − T − 16 − 36`，单行标题时为 66vp。

##### Sub-140-G：标题双内容

标题 + 核心 + 辅助，无 Action。核心左上对齐，其槽吸收剩余高度；辅助自然高度沉底，两内容之间为 8vp，不等分。主辅最小高度之和不得超过 `136 − T − 16`，单行标题时为 102vp。例如 EmphasisText + SecondaryBody，而不是两个强调核心组件。

##### Sub-140-H：内容四宫格

四个同级 `ProgressCircle size="sm"`，无标题、无 Action。每格 66 × 64vp，行列间距 8vp，组件在格内居中；不得留空、替换、合并或跨格。

#### 4.3.2 左内容右侧双槽

左 140 × 136vp 内容区 + 12vp 间距 + 右 144 × 136vp 固定槽列。右侧上下槽各 144 × 64vp，中间 8vp；必须由两个真实模块填满：

| 上槽 | 下槽 |
|---|---|
| CardButton | CardButton |
| InfoBlock | InfoBlock |
| InfoBlock | CardButton |

右侧不用 PillButton；不得交换混合组合的上下顺序、只放一个模块、创建空槽或虚构内容。每个槽只放一个业务组件，不合并、跨槽或改变槽高。

两条日程 + 一个次要状态 + 一个 Action 的情形，左侧可用一个 `EventCard density="compact"`，将两条日程都写入 items；组件条目间距优先 8vp，无法闭合时由组件降为 4vp。右上 InfoBlock、右下 CardButton；不得拆成两个 EventCard 或丢失事件标题、时间、地点及绑定。仍须检查长地点是否完整可见。

```jsx
<Card size="2x4" appearance="solid-green" layout="main-right-double">
  <Region slot="main" variant="wide-title-content">
    {/* 局部标题，然后一个完整业务内容；实际 variant 按左区关系选择 */}
  </Region>
  <Region slot="side-top">{/* InfoBlock 或 CardButton，遵循组合表 */}</Region>
  <Region slot="side-bottom">{/* InfoBlock 或 CardButton，遵循组合表 */}</Region>
</Card>
```

### 4.4 四槽宫格

四个 144 × 64vp 固定槽，行列间距 8vp，无标题区。每槽一个真实 InfoBlock 或 CardButton；不得留空、占位、隐藏、合并、改为动态高度或生成额外 Panel。

内容天然适合多个同级 InfoBlock 且能组成四个有效模块时优先使用本布局，不改用左右双区，也不把 InfoBlock 放入左内容右侧双槽的左区。InfoBlock 与 CardButton 可按业务关系分配到任意固定槽，不要求同一列使用相同组件类型。具体 slot 名称见语义接口。


模型提交 `Card → Region → 业务组件`，程序将外壳确定性展开为现有 Card/Stack/Grid，再进行真实渲染校验。2×2 仍使用原 Stack/Grid 写法。

## 父布局

Card 必填 `size="2x4"`、`appearance`、`layout`，可选 `aria-label`；不传 direction、gap、align、justify、padding。Region 只接受 slot 和下表要求的 variant。程序根据这些语义布局标识自动派生中文 `decision`，模型不得重复填写。

| layout | layoutPattern | Region.slot（全部必填） | variant |
|---|---|---|---|
| `top-bottom` | 上下双区 | title、primary、details | 均不传 |
| `split-panels` | 左右双区 | left、right | 每侧独立选择 compact；至多一侧使用 wide-title-double-progress 或 wide-quad-progress |
| `main-right-double` | 左内容右侧双槽 | main、side-top、side-bottom | main 选 wide；右侧不传 |
| `four-blocks` | 四槽宫格 | top-left、bottom-left、top-right、bottom-right | 均不传 |

派生结果中，`main` 对应 `subPattern.content`，left/right 对应同名键；上下双区与四槽宫格的 subPattern 为 `{}`。固定 144×64 槽放 InfoBlock 或 CardButton，合法组合沿用本 Skill 的容量规范。

上下双区：title 放标题及可选 Badge；primary 放一个内容组；details 放一组 TextBlock 或 TopTextBottomValue。可选 `Card.flow` 为 `continuous`、`footer`（默认）或 `equal`；阅读关系与容量见布局规范 4.1。

### InfoBlock 槽位限制

| Card.layout | 允许 InfoBlock 的 Region.slot |
|---|---|
| `top-bottom` | 无 |
| `split-panels` | 无，left/right 的所有 variant 均禁止 |
| `main-right-double` | 仅 side-top、side-bottom；main 的所有 variant 均禁止 |
| `four-blocks` | top-left、bottom-left、top-right、bottom-right |

InfoBlock 必须直接放入上述固定 Region，每槽一个；不能包裹 Stack/Grid 塞进普通内容槽。Plan 选择组件时就检查此表：不兼容时更换语义合适的内容组件；只有存在足够真实模块并保持 Action 归属时才改选固定槽布局。右侧双槽仍仅允许双 CardButton、双 InfoBlock、上 InfoBlock 下 CardButton，不得留空或补造模块。

## 子布局

| Region.variant | subPattern | 直接子元素顺序 | 程序保证 |
|---|---|---|---|
| compact-center | Sub-118-A 核心居中 | 内容 | 居中 |
| compact-title-content | Sub-118-B 标题单内容 | 标题、内容 | 内容左下对齐 |
| compact-title-primary-secondary | Sub-118-C 标题双内容 | 标题、核心、辅助 | 核心左上，辅助沉底 |
| compact-title-content-action | Sub-118-D 标题内容单按钮 | 标题、内容、PillButton | 内容承接剩余空间，按钮底部固定槽 |
| wide-center | Sub-140-A 核心居中 | 内容 | 居中 |
| wide-title-content | Sub-140-B 标题单内容 | 标题、内容 | 内容左下对齐 |
| wide-title-content-action | Sub-140-C 标题内容单按钮 | 标题、内容、PillButton | 按钮底部固定槽 |
| wide-title-double-progress | Sub-140-D 标题双列内容可选按钮 | 标题、两个 ProgressCircle、可选 PillButton | 双列等宽，按钮有则保留槽 |
| wide-title-primary-secondary-action | Sub-140-F 标题主次内容单按钮 | 标题、核心、辅助、PillButton | 主辅自然高度、间距 2vp，按钮沉底 |
| wide-title-primary-secondary | Sub-140-G 标题双内容 | 标题、核心、辅助 | 核心左上，辅助沉底 |
| wide-quad-progress | Sub-140-H 内容四宫格 | 四个 ProgressCircle | 两行两列 |

标题可用 SingleLineTitle 或 DoubleLineTitle，其后可紧跟一个 Badge，由程序组成标题行。外壳尺寸、安全边距、主要模块间距和按钮尺寸由程序按布局规范生成，不写入提交。

## 内容槽提交边界

每个内容模块必须作为 `Region` 的直属业务组件提交；不得输出 `Stack` 或 `Grid`，也不得用容器把多个业务组件伪装成一个内容槽。核心与辅助需要上下分离时，选择 `compact-title-primary-secondary` 或 `wide-title-primary-secondary`，并按核心、辅助顺序直接放入两个内容槽。恰好三个同级占比值需要内部排列时，使用一个 `NumericRatioStack`，通过其 `direction="row" | "column"` 选择方向；一项或两项不得使用。

固定外壳并不保证任意内容都能放下：超出容量时先替换紧凑组件、合并为组件原生 `items`，或在允许更换布局的阶段调整 variant/layout。始终提交语义 JSX，不把浏览器 findings 中程序展开的 `Stack/Grid` 复制回来。

## 带操作的单区骨架

```jsx
<Region slot="left" variant="compact-title-content-action">
  <SingleLineTitle title="本组标题" />
  {/* 一个直属业务内容组件 */}
  <PillButton label="本组操作" appearance="card" actionId="输入中的真实 Action ID" />
</Region>
```

此例只演示单区填槽结构，不预设另一侧 variant；每侧先按实际信息、标题和 Action 独立选择。内容不足不得填造信息，空间不足不得把 Action 移到不相关的业务区。
