# 2×4 语义布局提交接口

先按 `layout_patterns_2x4.md` 选择业务分区、父布局和子布局并检查容量，再用本接口填槽提交 JSX。few-shot 展示完整的语义提交与绑定；语义骨架不替代信息分组。

模型提交 `Card → Region → 业务组件`，程序将外壳确定性展开为现有 Card/Stack/Grid，再进行真实渲染校验。2×2 仍使用原 Stack/Grid 写法。

## 父布局

Card 必填 `size="2x4"`、`appearance`、`layout`，可选 `aria-label`；不传 direction、gap、align、justify、padding。Region 只接受 slot 和下表要求的 variant。程序根据这些语义布局标识自动派生中文 `decision`，模型不得重复填写。

| layout | layoutPattern | Region.slot（全部必填） | variant |
|---|---|---|---|
| `top-bottom` | 上下双区 | details 必填；title、primary 可选 | 均不传 |
| `split-panels` | 左右双区 | left、right | 每侧独立选择 compact |
| `main-right-double` | 左内容右侧双槽 | main、side-top、side-bottom | main 选 wide；右侧不传 |
| `double-left-main` | 左侧双槽右内容 | side-top、side-bottom、main | main 选 wide；左侧不传 |
| `four-blocks` | 四槽宫格 | top-left、bottom-left、top-right、bottom-right | 均不传 |

派生结果中，`main` 对应 `subPattern.content`，left/right 对应同名键；上下双区与四槽宫格的 subPattern 为 `{}`。固定 132×57vp 槽放 InfoBlock 或 CardButton，合法组合沿用原布局规范。

上下双区：title 可选，放标题及可选 Badge；primary 可选，放一个内容组；details 必填，放一组 TextBlock 或 TopTextBottomValue。标题与第一个内容区间距 6vp；若标题存在但 primary 缺省，标题与 details 间距 8vp。可选 `Card.flow` 为 `continuous`、`footer`（默认）或 `equal`。

### InfoBlock 槽位限制

| Card.layout | 允许 InfoBlock 的 Region.slot |
|---|---|
| `top-bottom` | 无 |
| `split-panels` | 无，left/right 的所有 variant 均禁止 |
| `main-right-double` | 仅 side-top、side-bottom；main 的所有 variant 均禁止 |
| `double-left-main` | 仅 side-top、side-bottom；main 的所有 variant 均禁止 |
| `four-blocks` | top-left、bottom-left、top-right、bottom-right |

InfoBlock 必须直接放入上述固定 Region，每槽一个；不能包裹 Stack/Grid 塞进普通内容槽。Plan 选择组件时就检查此表：不兼容时更换语义合适的内容组件；只有存在足够真实模块并保持 Action 归属时才改选固定槽布局。右侧双槽仍仅允许双 CardButton、双 InfoBlock、上 InfoBlock 下 CardButton，不得留空或补造模块。

## 子布局

| Region.variant | subPattern | 直接子元素顺序 | 程序保证 |
|---|---|---|---|
| compact-center | Sub-118-A 核心居中 | 内容 | 居中 |
| compact-title-content | Sub-118-B 标题单内容 | 标题、内容 | 内容左下对齐 |
| compact-title-primary-secondary | Sub-118-C 标题双内容 | 标题、核心、辅助 | 核心左上，辅助沉底 |
| compact-title-content-action | Sub-118-D 标题内容单按钮 | 标题、内容、PillButton | 内容承接剩余空间，按钮底部固定槽 |
| compact-two-column-action | Sub-118-E 标题双列内容可选按钮 | 单行标题、两个 ProgressCircle、可选 PillButton | 54 + 8 + 54vp 自适应双列；标题间距 4vp；按钮 116 × 36vp，存在时前置 6vp 间距 |
| compact-content-two-actions | Sub-118-F 内容双按钮 | 内容、两个 PillButton | 内容 116 × 26vp；按钮间距 6vp |
| wide-center | Sub-140-A 核心居中 | 内容 | 居中 |
| wide-title-content | Sub-140-B 标题单内容 | 标题、内容 | 内容左下对齐 |
| wide-title-content-action | Sub-140-C 标题内容单按钮 | 标题、内容、PillButton | 按钮底部固定槽 |
| wide-title-double-progress | Sub-140-D 标题双列内容可选按钮 | 标题、两个 ProgressCircle、可选 PillButton | 双列等宽，按钮有则保留槽 |
| wide-title-primary-secondary-action | Sub-140-F 标题主次内容单按钮 | 标题、核心、辅助、PillButton | 主辅自然高度、间距 2vp，按钮沉底 |
| wide-title-primary-secondary | Sub-140-G 标题双内容 | 标题、核心、辅助 | 核心左上，辅助沉底 |
| wide-quad-progress | Sub-140-H 内容四宫格 | 四个 ProgressCircle | 两行两列 |
| wide-quad-content | Sub-140-H 内容四宫格 | 四个同级内容 | 62 × 59vp，两行两列、间距 8vp |
| wide-two-column-action | Sub-140-I 标题双列内容可选按钮 | 单行标题、两个 ProgressCircle、可选 PillButton | 62 + 8 + 62vp 自适应双列；标题间距 6vp；按钮 132 × 36vp，存在时前置 8vp 间距 |
| wide-content-two-actions | Sub-140-J 内容双按钮 | 内容、两个 PillButton | 内容 132 × 38vp；按钮间距 8vp |

标题通常可用 SingleLineTitle 或 DoubleLineTitle，其后可紧跟一个 Badge，由程序组成标题行；`compact-two-column-action` 与 `wide-two-column-action` 固定使用 `SingleLineTitle`，两个内容固定使用 `ProgressCircle size="sm"`。“左右双区”标题至第一个内容区为 4vp、父容器四边安全边距为 8vp；“左内容右侧双槽／左侧双槽右内容”标题至第一个内容区为 6vp，PillButton 为 132 × 36vp 并撑满内容区。外壳尺寸、安全边距、其余间距和按钮尺寸由程序按布局规范生成，不写入提交。

## 保留内容内部的 Stack 灵活性

一个内容槽可放业务组件，或使用 Stack/Grid 组合**需要紧密连续阅读、整体对齐的同组内容**。需要核心在上、辅助沉底时，必须选择 `compact-title-primary-secondary` 或 `wide-title-primary-secondary`，两个内容模块按核心、辅助顺序直接放在 Region 下，不能包装成单内容。分组不新增语义分区，也不允许把标题、InfoBlock、Action 藏进内容槽。

内容分组根使用自然高度、`flex={0}`，不能设置 height/minHeight/maxHeight 或上下外边距；内部 Stack 仍可设置 direction、flex、width、height、gap、align、justify（遵循 core 的生成子集）。例如三个 NumericRatio 可横排或纵排，内部横向子列可用 flex={1} 分配宽度。禁止绝对定位、偏移或新背板越过槽位边界。

```jsx
<Region slot="main" variant="wide-title-content">
  <SingleLineTitle title="空间占比" />
  <Stack direction="row" flex={0} width="full" gap={6} align="center">
    {/* 同组业务组件；内部子列可用 flex={1} */}
  </Stack>
</Region>
```

固定外壳并不保证任意内容都能放下：超出容量时先替换紧凑组件、合并表达或调整槽内组合；允许更换布局的兜底阶段可改 variant/layout。始终提交语义 JSX，不把浏览器 findings 中展开后的 Stack 复制回来手改，不通过分组或裁剪绕过最小尺寸与信息保留要求。

## 带操作的单区骨架

```jsx
<Region slot="left" variant="compact-title-content-action">
  <SingleLineTitle title="本组标题" />
  {/* 本组内容组件或自然高度内容组 */}
  <PillButton label="本组操作" appearance="card" actionId="输入中的真实 Action ID" />
</Region>
```

此例只演示单区填槽结构，不预设另一侧 variant；每侧先按实际信息、标题和 Action 独立选择。内容不足不得填造信息，空间不足不得把 Action 移到不相关的业务区。
