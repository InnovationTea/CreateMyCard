# 通用组件合同（维护源）

> 维护说明不发给模型；仅 `prompt` 标记内正文参与构建。

## 边界与阅读顺序

基础布局组件 → 组件总表 → 组件选型 → Props/绑定/样式 → 图标规范。组件边界不等于组合边界。

## 基础布局组件总表（维护导航，不发模型）

| 名称 | 布局职责 | 容量与约束 |
|---|---|---|
| `Row` | 横向排列子组件 | 子组件与横向预算必须成立 |
| `Column` | 纵向排列子组件 | 子组件与纵向预算必须成立 |
| `Stack` | 叠放子组件 | 只用于环心读数、背景与前景等真实叠放 |

只有基础布局组件通过组件行第 4 项声明 `children`。它们只负责排列和承载，不替代任何信息、视觉、
进度、标题或操作组件。

## 组件总表（维护导航，不发模型）

| 类型 | 名称 | 内容结构 | 适用场景 | 容量与约束 |
|---|---|---|---|---|
| 标题 | `CardHeader` | 单行标题 + 可选主题图标 | 卡级标题或任意内容分区标题 | 保留 `CardHeader` 命名，承载原 `SingleLineTitle` 能力 |
| 文本 | `Text` | 单段文本或读数 | 灵活承载重点文字、正文、标签、状态和补充说明 | 必须有 `content`；可组合表达原 `EmphasisText` / `SecondaryBody` 能力 |
| 核心信息 | `EmphasizedData` | 核心数值 + 可选单位 | 突出唯一量化主值 | 一个核心值；不吸收辅助信息 |
| 分隔 | `Divider` | 水平或竖直分隔线 | 确有分组关系的内容之间 | 不作为装饰填空 |
| 占比 | `ProgressCircle` | 环心图标 + 环外数值 | 一个或多个对象的真实占比或有界进度 | `externalText` 同时驱动圆环和读数；模型可控制组件宽高 |
| 核心信息 | `DataDisplay` | 标签 + 主值 + 支撑文本 | 2x2 单一量化焦点 | 三项各一行；不吸收动作或第二指标 |
| 紧凑信息 | `InfoBlock` | 主信息 + 辅助信息 + 可选图标 | 固定小槽中的完整主辅信息 | 每槽一个；两行文字保持单行可读 |
| 多项属性 | `TableText` | 多行标签—值 | 同一主题的 2–3 项属性 | 当前只进入 2x2 紧凑明细区 |
| 明细信息 | `TextBlock` | 2–4 组标签—值背板 | 2x4 同级详情 | 每项等宽；只进入 `W-top-bottom` 的详情槽 |
| 摘要列表 | `SummaryList` | 2–3 条同级摘要 | 2x4 短列表 | 每项固定为单行背板 |
| 线性进度 | `ProgressLine2` | 可见读数 + 线性进度 | 当前值相对明确总量 | 只进入 `W-top-bottom` 的 progress-detail 预设 |
| 环形进度 | `ProgressCircleSingle` | 紧凑环形读数组 | 单个真实比例及同对象说明 | `W-top-bottom` 的 ring-summary 内容预设 |
| 日程 | `EventCard` | 时间线 + 标题 + 时间 + 可选地点 | 2x2 单事件 | 内容必须来自同一事件，完整信息与布局预算成立 |
| 等权指标 | `TopTextBottomValue` | 三组标签—数值—单位 | 2x4 三个同级指标 | 恰好三项；只进入 `W-top-bottom` 的 metric-triple 预设 |
| 操作 | `PillButton` | 操作文案 + 可选图标 | 2x2 底部卡级 CTA | 一个实例绑定一个真实动作 |
| 操作 | `CircleButton` | 纯图标操作 | 2x2 右下锚点 CTA | `36×36vp` 按钮进入 `40×40vp` 槽 |
| 操作 | `CardButton` | 文案 + 可选图标 | 2x4 固定动作槽 | 一个实例绑定一个真实动作 |
| 视觉 | `Image` | 单个本地素材 | 存在语义准确且状态安全的素材 | 固定使用当前素材候选；不使用网络图或 emoji |

每个组件以正文合同为准，单组件的绑定支持不能推导到其它 Props。完整案例在 `../fewshots/`，组合条件在
`../combinations/`，不把示例中的属性自动扩展为通用合同。除基础布局组件外，组件均不带 children。
使用视觉 Recipe 的组件仍只输出一行；内容字段支持 Text.content 已允许的静态值、Expression 或
PathBinding，其内部字号、行高、间距、图标和子节点 ID 由视觉 Recipe 展开。
可选外部布局 Props 为 `width`、`height`、`layoutWeight`、`flexShrink`、`margin`，只作用于组件根。
横向填充组件默认跟随父槽位；放入 Row 时未显式指定宽度则等权分配。内部排版不能用外部 Props 覆盖。
组件的 `fontColor` 表示 100% 内容色；设计系统规定的辅助文字、单位、时间线和环心图标由转换器
确定性派生为 60% 内容色，模型不额外传辅助色。
`InfoBlock` 的外层和内部组件均不支持事件；无图标时不生成图标节点或空槽。
`CardButton` 无图标时由确定性视觉配方补充中性的固定视觉占位，模型仍不得伪造图标路径。`ProgressCircle`、
完整业务父级完整内容区不属于 `InfoBlock`。

## 片段索引

| 片段 |
|---|
| `progress-type` |
| `progress-trigger` |
| `catalog` |
| `selection` |
| `icon-style` |

片段由 manifest 编排；修改正文后运行构建与回归，禁止手改 generated。

<!-- prompt:selection -->
## 组件选型：先看语义，再看可绑定内容与容量

Plan 和 DSL 使用同一选型规则。组件不是按业务名分配的模板；先识别对象、核心/辅助/并列关系、
必须展示的事实与动作，再选能完整承载它们的组件。不要对每条事实机械推荐三个名字；没有合适的
专用组件时使用 Text、Image 与基础布局组件形成合法组合，或省略软候选，不删除事实。

| 组件 | 适用内容与可见绑定 | 不适用情况 |
|---|---|---|
| Text | 原 `EmphasisText` / `SecondaryBody` 覆盖的重点文字、正文、标签、状态和补充说明；多行或多层内容由 Row/Column 组合多个 Text | 不用多个 Text 重造已有组件的固定结构；唯一核心量化值优先 EmphasizedData |
| CardHeader | 稳定的单行卡级或分区主题，title 可绑定真实名称；位置由最终布局决定 | 不用温度、状态、日期时间或数量冒充标题；不承载动作 |
| EmphasizedData | 一个短的核心量化读数，value 与可选 unit；名称和指标标签留在所属信息组 | 地区、天气现象、连接状态、长日期时间不是大数值；多个同级值不能各自强造主焦点 |
| InfoBlock | 一个对象的两行短信息，primaryText/secondaryText，可选准确图标 | 不承载动作、第三行或完整密集记录；图标不能挤掉读数；尺寸变体见下表 |
| ProgressCircle | 一个真实占比的环＋语义准确的环心图标＋环外读数；同级占比可成组使用 | 单个占比需要右侧完整说明时优先 ProgressCircleSingle；无真实范围或对象无法由图标区分时不用 |

数值进度组件只用于真实比例：`ProgressCircle.externalText` 的动态绑定必须为 number/integer；
`ProgressLine2`、`ProgressCircleSingle` 的数值与展示值必须来自同一对象同一指标，不借用另一对象数值，
不从样例截取数字、不把普通绝对量除以猜测的总量。若只有格式化字符串，保留完整文字，不推荐进度。
Plan 将组件候选写在它实际承载的事实上；动作只能推荐真实支持事件的按钮，不能推荐 EventCard
或 InfoBlock。多个事实推荐同一组件表示可以合并到一个实例，不表示每条事实创建一个实例。
内部字体、图标、间距和颜色角色由现有 Recipe 决定；外部尺寸不得改变内部视觉或掩盖溢出。
<!-- /prompt:selection -->

<!-- prompt:progress-type -->
**进度数值类型前置约束**：`ProgressCircle.externalText`、`ProgressLine2.value` 和 `ProgressCircleSingle.value` 的动态绑定必须引用 number/integer 字段。若 TaskSpec 只有 `batterySOCText:"68%"` 一类格式化字符串，改用完整 Text 主读数；禁止从动态字符串中猜测、截取或隐式转换数值。`ProgressCircle.externalText` 仅允许静态值直接写 `68` 或 `"68%"`。

<!-- /prompt:progress-type -->

<!-- prompt:progress-trigger -->
**进度生成前置约束**：默认不生成进度组件。只有 TaskSpec 的字段描述明确表示百分比、完成度、使用率、电量等比例语义，并且范围可验证时才允许；温度、日期、时间、时长、倒计时、状态、名称和普通数值一律禁止。不得仅因字段是 number/integer、位于小内容背板或示例中存在环图就生成进度组件，也不得自行猜测范围；两座城市天气的 `S-dual-info` 分区只能使用合法天气 Image 或无 visual，绝不使用温度进度环。

<!-- /prompt:progress-trigger -->

<!-- prompt:catalog -->
# 五、组件协议

只允许以下三种基础布局组件：

`Row`、`Column`、`Stack`

除基础布局组件外，只允许以下组件：`Text`、`Image`、`Divider`、`ProgressCircle`、`EmphasizedData`、
`InfoBlock`、`ProgressLine2`、`TableText`、`TextBlock`、`CardButton`、`ProgressCircleSingle`、
`EventCard`、`DataDisplay`、`TopTextBottomValue`、`SummaryList`，以及 5.13 的 `PillButton`、
`CircleButton` 和 5.14 的 `CardHeader`。其中使用视觉 Recipe 的组件由转换器展开为标准 A2UI 组件树；
该实现差异不构成另一类模型组件。禁止输出未登记组件。

禁止：

`Button`、`List`、`TextInput`、`Toggle`、`Radio`、`Select`、`NavContainer`、`Tabs`、`TabContent`、`Web`、`Grid`、`If`

禁止所有组件的 `theme`、`onAppear`、`onChange`、`onSelect`、`onReachStart`、`onReachEnd`。
动作必须使用 `PillButton`、`CircleButton` 或 `CardButton`；短摘要列表必须使用 `SummaryList` 或
`Row`/`Column` 组织其它合法组件，不得直接生成 `Button` 或 `List`。

## 5.1 通用 props 字段

每个组件行的第三项 `props` 可使用：

- `content`：Text 必填；字符串、完整 Expression 或 PathBinding。
- `src`：Image 必填；assetCandidates 中的本地资源路径、完整 Expression 或 PathBinding。
- `value/total`：仅按 `ProgressLine2`、`ProgressCircleSingle` 等对应组件规则使用；`ProgressCircle` 使用 `externalText`。
- `children`：禁止写入 props；只有基础布局组件可在组件行第 4 项声明 children。
- `itemMargin`：Row、Column 可选数字 vp；`space` 是兼容别名，优先使用 `itemMargin`。
- `onClick`：可选 EventHandler 数组，只在有匹配事件候选时使用。
- `accessibility`：可选对象，只允许静态短字符串 `label` 和 `description`。
- `design`：可选语义化设计令牌；只能使用本节列出的有意义命名，不使用缩写、尺寸编号或颜色编号。

## 5.2 通用布局与样式 props

以下字段直接写在组件行第三项 `props`，不得嵌套 `styles`：

`width`、`height`、`constraintSize`、`aspectRatio`、`margin`、`padding`、`borderRadius`、`borderWidth`、`borderColor`、`backgroundColor`、`backgroundImage`、`backgroundImageSizeWithStyle`、`linearGradient`、`shadow`、`layoutWeight`、`flexShrink`、`visibility`、`clip`

规则：

- root 的 `width/height` 一律写 `"matchParent"`（2x2/2x4 画布尺寸由 surface 决定，不写数值）；关键内部容器、主图、按钮和 `ProgressCircle` 使用数值宽高。
- 端侧实际 surface 尺寸可能随设备变化。root 为 `Column` 时必须显式写 `alignItems:"center"`，使按参考安全宽度生成的一级内容组始终相对实际画布水平居中；一级内容组内部仍按语义使用 `alignItems:"start|center|end"`，不得因为 root 居中就把标题、正文和数值文字全部改成居中排版。root 为 `Row` 时，水平位置由 `justifyContent` 控制：直接子内容使用固定参考宽度且设计意图为整组居中时必须写 `justifyContent:"center"`，`alignItems` 只负责垂直方向。root 为 `Stack` 时使用 `alignContent` 控制直接子内容的位置。禁止混淆三个容器的轴向属性。
- `margin/padding` 使用数字，或完整的 `{top,right,bottom,left}` 对象；不要缺边依赖默认值完成关键预算。
- `linearGradient` 使用 `{direction,colors}`（用户自定义可使用协议支持的 angle），默认按第十二节两色标微渐变；用户自定义背景也必须遵守协议。
- 未有用户自定义要求时，root 只能使用第十二节蓝、紫、暖三套微渐变或五套融球。
- `backgroundImageSizeWithStyle` 优先使用 `cover|contain|fill|auto`。
- `visibility` 只取 `visible|hidden|none`：`hidden` 不显示但继续占用布局空间，`none` 不显示且不占用空间。不得依赖 `hidden` 或 `none` 掩盖预算失败，也不得动态隐藏用户核心内容、受保护文本或主动作。
- `flexShrink` 只使用 `[0,1]` 范围内的静态数值；`0` 表示不参与主轴压缩，值越大越优先被压缩。受保护文本或 CTA 可设为 `0`，但仍须按完整内容预留空间，不能把 `flexShrink` 当作布局预算替代品。
- `aspectRatio` 必须是大于 `0` 的静态数值。关键组件优先显式写 `width/height` 并省略 `aspectRatio`；`constraintSize` 的约束优先级高于 `aspectRatio`。
- `shadow` 只允许静态字符串枚举 `outerDefaultXS|outerDefaultSM|outerDefaultMD|outerDefaultLG|outerFloatingSM|outerFloatingMD`，或对象 `{offsetX,offsetY,radius,color,fill,type}`；对象中的 `radius` 必填且不小于 `0`，`type` 只取 `color|blur`。
- 不使用 catalog 未声明的 `gap`、`position`、`top`、`left`、`zIndex`、`opacity`、`transform`、`display` 或 CSS 字段。

### 5.2.1 显式样式口径

除 root 融球 Style Design Token 外，不使用 design 语义令牌或色彩令牌；字号、字重、颜色、圆角、间距一律按批准档位显式写在 props（`fontSize`、`fontWeight`、`fontColor`、`fillColor`、`backgroundColor` 等，颜色只写 `#AARRGGBB`），取色逻辑见第十二节。模型不直接生成基础 `Progress`；环形占比使用 `ProgressCircle` 或 `ProgressCircleSingle`，线性进度使用 `ProgressLine2`。

- 融球的业务、尺寸、密度和运行时条件统一按第十二节执行；满足条件且无用户自定义背景要求时优先使用对应融球。
- 不满足融球条件时使用第十二节固定浅色微渐变；多业务按主要业务取色，无明确主次或未覆盖业务默认蓝色。
- 使用融球 Design Token 时，root 的背景只写 `design`，不再写 `backgroundColor`、`linearGradient` 或 `backgroundImage`；尺寸、内边距、圆角、裁剪和布局属性仍按 root 规则显式填写。转换器会确定性展开融球背景，并把前景根的原 ID `root` 加上 `__genui_render_component__` 前缀，生成 `__genui_render_component__root` 防溢出标识；展开后的外层卡片根仍使用 `root`。

## 5.3 Text

`Text` 是可直接选用的通用内容组件，在 Fusion 中统一承载 claw-widget 原
`EmphasisText` 与 `SecondaryBody` 的语义，且可按当前槽位显式设置字号、字重、颜色、行数和对齐。
`Text` 不是“没有合适组件时才能使用”的降级项；当内容是重点文字、完整正文、标签、状态或补充说明，
而不符合其他组件的固定语义合同时，应直接使用 `Text`。

顶层：

- 必填 `content`：字符串、完整 Expression 或 PathBinding。
- `content` 不得是空字符串或纯空白。不得用空 Text 绘制圆点、占位、留白或承担尺寸撑开；圆点等必要标记使用可见短符号，纯间距使用父容器布局，无法用合法组件表达时删除该装饰。

props 可用样式字段：

`fontSize`、`fontWeight`、`fontColor`、`maxLines`、`minFontSize`、`maxFontSize`、`textAlign`，以及通用布局与样式 props。

- `fontWeight` 使用 `100-900`，按 100 递增。
- `textAlign` 只取 `start|center|end|justify`。
- 重点短文本通常使用 `16–18fp/500–700`；正文和主要补充信息通常使用 `14–16fp/400–500`；
  标签、状态和次要说明通常使用 `12fp/400–500`。只有 5.6 规定的 ring 环外读数可使用 `10fp/500`；最终字号仍须符合当前布局预算和通用字号规则。
- 一个 `Text` 只承载一段连续内容；需要“重点 + 说明”、“标签 + 状态”或多段正文时，用
  `Row` / `Column` 组合多个 `Text`，并为每段分别绑定；不把独立动态事实拼成静态字符串。
- 已符合 `EmphasizedData`、`InfoBlock`、`TableText`、`EventCard` 等固定内容结构时，直接使用对应组件，
  不用多个 `Text` 手写复制其结构和样式。但内容结构不匹配这些合同时，不得为了套组件而删减事实，应改用 `Text` 组合。
- 生成的极简 DSL 不输出 `textOverflow`。转换器可能在完整 DSL 中补充防御性 `clip`，但生成阶段仍必须证明完整压力文本可以放入槽位；不能把转换器兜底当作截断策略，也不能用 `ellipsis`、裁切或遮罩掩盖布局不足。
- 使用 `minFontSize/maxFontSize` 时两者必须同时设置；它们只能作为字体适配兜底，仍要保证完整压力测试字符串在 `minFontSize` 下能够放入文本框。

## 5.4 Image

顶层：

- 必填 `src`：assetCandidates 中的本地/资源路径，或读取已声明资源路径的 Expression/PathBinding。

props 可用样式字段：

`objectFit`、`fillColor`、`aspectRatio`，以及通用布局与样式 props。

- 必须显式写 `width`、`height` 和 `objectFit`。
- `objectFit` 优先 `contain`；主媒体确实需要裁切时才用 `cover`。
- `fillColor` 会覆盖 SVG 内部原有填充色。除非 `description` 明确要求“不可染色、禁止染色、保留原色”，或强调必须保留的多色、渐变、品牌色彩语义，否则所有 SVG 默认设置 `fillColor`，值必须是 `#AARRGGBB`。PNG 等位图不写 `fillColor`；不要抹掉描述明确要求保留的状态、层级或品牌信息。
- 选择 `fillColor` 时必须以图标所在的直接背景为准，而不是只看 root 背景。图标位于面板、按钮或标签中时，应按该容器的实际底色判断明暗与对比度；半透明容器还要考虑其下方背景。
- 按图标角色选择颜色：单色图标与同组文字完全同色；没有同组文字的主视觉图标使用内容色 100%；融球按钮图标白色 60%、文字白色 90%；真实状态色保留例外，详见第十二节。
- `fillColor` 必须复用本卡已经确定的颜色角色，不为单个图标临时增加新的强调色。描述给出的推荐色或色系可用于确定最合适的颜色角色，但最终颜色必须与直接背景形成清晰对比。
- 图标必须与直接背景清晰可辨；优先换用合适素材或删除非必要图标，不自行修改第十二节固定色值，不通过描边、阴影或额外底板补救。
- 同一层级、同一语义的图标使用同一染色角色；同一素材在相同语义下不反复使用不同染色。默认黑色的 SVG 不应直接沿用黑色，除非黑色就是当前浅色表面上的 `primaryText` 颜色且符合整体配色。
- 只有描述明确要求保留原色的 SVG 才省略 `fillColor`；若其原色在当前背景上不可辨认，则改用其他候选素材或不用图标，不擅自覆盖其颜色。

## 5.5 Divider

- 无额外必填顶层字段。
- props 使用 `strokeWidth`、`vertical`、`color` 和必要宽高。
- 只用于真实分隔、时间线或强调线，不做装饰堆叠。

## 5.6 `ProgressCircle`

`ProgressCircle` 是环形占比组件。模型只输出一行 Compact DSL，不直接生成其内部的 `Progress`、
`Stack`、`Image` 或环外 `Text`。

必填 Props：

- `externalText`：`0–100` 的静态 number、静态百分比字符串，或指向 `number/integer` 字段的 PathBinding。
  它同时驱动圆环进度和环外读数；动态格式化字符串不能直接绑定。
- `icon`：来自当前素材候选、能准确区分对象的图标路径。
- `accessibility`：至少包含非空静态 `label`；可选 `description`。
- `fontColor`、`color`、`backgroundColor`：分别表示环外文字色、完成轨道色和未完成轨道色，均为静态
  `#AARRGGBB`；可选 `fillColor` 控制单色环心图标。
- `width`、`height`：模型根据当前槽位和整组预算填写的正数 vp。两者是组件整体尺寸，可自由取不同值；
  转换器会在扣除 `14vp` 环外读数和 `2vp` 间距后，按剩余空间的短边生成至少 `40vp` 的正圆，
  不把圆环拉伸为椭圆。

只有数据具有明确目标、总量、范围或百分比语义，且可以证明值落在 `0–100` 时才使用。没有进度语义、
无法保证动态值范围、只能依赖字符串转数字，或没有准确环心图标时改用 `Text`。同级占比通常成组使用；
单个占比需要右侧标签、读数和状态说明时使用 `ProgressCircleSingle`。

组件视觉固定展开为：圆环描边 `6vp`、环心图标 `20×20vp`、环外读数 `10fp/500` 且高 `14vp`，
内部间距 `2vp`。模型不得传 `value`、`total`、`type`、`strokeWidth`、`size`、`trackColor` 或 children。

示例：

```genui
["ratio","ProgressCircle",{"externalText":{"path":"/data/device/batteryPercent"},"icon":"resources/base/media/battery_leaf_fill.svg","accessibility":{"label":"设备电量百分比"},"width":52,"height":68,"fontColor":"#FF1F4799","fillColor":"#991F4799","color":"#FF1F4799","backgroundColor":"#331F4799"}]
```

## 5.7 Row

顶层：

- 必填 `children`：组件 id 字符串数组。
- 可选 `itemMargin`：数字 vp。

props 可用样式字段：

- `justifyContent`：`start|center|end|spaceAround|spaceBetween|spaceEvenly`。
- `alignItems`：`top|center|bottom`。
- `justifyContent` 为 `spaceAround|spaceBetween|spaceEvenly` 时，`itemMargin` 仍作为相邻子项之间必须保留的最小间距；扣除该间距后，只能将非负剩余空间交给分布式对齐。两者可以同时设置，但不能依赖分布式对齐消除负剩余空间。

## 5.8 Column

顶层：

- 必填 `children`：组件 id 字符串数组。
- 可选 `itemMargin`：数字 vp。

props 可用样式字段：

- `justifyContent`：`start|center|end|spaceAround|spaceBetween|spaceEvenly`。
- `alignItems`：`start|center|end`。
- `justifyContent` 为 `spaceAround|spaceBetween|spaceEvenly` 时，`itemMargin` 仍作为相邻子项之间必须保留的最小间距；扣除该间距后，只能将非负剩余空间交给分布式对齐。两者可以同时设置，但不能依赖分布式对齐消除负剩余空间。

## 5.9 Stack

顶层：

- 必填 `children`：只能是组件 id 字符串数组，不支持模板对象。

props 可用样式字段：

- `alignContent`：`topStart|top|topEnd|start|center|end|bottomStart|bottom|bottomEnd`。

只用于真实叠加，例如背景与前景或图标底板；`ProgressCircle` 已自行包含圆环与环心图标，不手写其内部 Stack。

## 5.12 生成时的动态绑定边界

属性是否支持动态值必须逐项判断。本服务为稳定布局采用以下受控子集：

| props 字段 | 允许的动态形式 | 约束 |
|---|---|---|
| Text.content / CardHeader.title | Expression、PathBinding | 结果必须可展示为文本 |
| Image.src | Expression、PathBinding | 首帧值及运行时可能值都必须是 assetCandidates 中的原始 `src`；不能证明时使用静态素材 |
| ProgressCircle.externalText | PathBinding | 引用 number/integer；转换器统一生成环和环外百分比读数 |
| 事件参数 | 仅复用候选中已有的动态值 | 不自行新增、改写或移动绑定 |
| Row/Column.children | 不允许动态模板 | 只能使用组件 id 字符串数组 |
| Stack.children | 不允许 | 只能使用静态组件 id 字符串数组 |

为减少布局漂移，生成新卡片时所有布局样式 props 默认使用静态合法值，不动态绑定尺寸、间距、圆角、排版、背景或对齐。不要因为组件的某个属性支持 Expression，就推断其它属性也支持。

## 5.12.1 组件共同规则

先按信息语义保留可行组件，再结合尺寸文件中的合法槽位决定是否使用。不要为了套用某个组件而补造字段、
合并无关事实或改变主次关系。除基础布局组件外，每个组件只输出一行且不带 children；只允许使用该组件属性表列出的 Props，
可另传共同规则中的外部布局 Props；不传 padding、圆角、字号或对齐覆盖内部样式。内容字段支持静态值、完整
Expression 或 PathBinding；颜色必须是静态 `#AARRGGBB`。

组件按内容结构直接选择，不存在先生成一种组件、再替换为另一种组件的流程。先核对必需内容，再按组件实际
行高、字号、padding、图标和剩余文字宽度核算；不够放时优先取消可选图标，仍不够则选择能完整承载内容的
其它组件或组件组合。例如 `DataDisplay` 不是多指标卡的通用回退，`InfoBlock` 不能装下任意长的单位串，进度组件不能从
带单位字符串中猜测数值。Recipe 内部不可调的字号不等于卡片其余区域必须跟着放大。

### 5.12.2 `EmphasizedData`

#### 选择条件

用于一个内容区中唯一需要突出的核心数值或完整格式化数值。没有真实主次时保持并列；多个同级
指标和普通文本结论不使用该组件；真实进度的可见读数可以使用它，并与同指标进度图保持一组。

#### 组件属性

| Prop | 类型 | 要求 |
|---|---|---|
| `value` | 显示值 | 必填；静态值、Expression 或 PathBinding |
| `unit` | string | 可选；仅用于静态单位 |
| `fontColor` | `#AARRGGBB` | 必填 |

#### 槽位与容量

只承载一个核心值；合法槽位和固定宽度由当前尺寸文件规定。组件不吸收标题、辅助信息或第二个指标。

#### 示例

```genui
["reading","EmphasizedData",{"value":{"path":"/data/healthSport/sleepScore"},"unit":"分","fontColor":"#FF563D99"}]
```

#### 注意事项

值已经包含单位时原样放入 `value`，不再传 `unit`。不要为缩短 DSL 而把多个同级值拼进一个 `value`。

### 5.12.3 `InfoBlock`

#### 选择条件

用于固定小槽中天然属于同一对象或指标的一组“主信息 + 辅助信息”。可附加一个语义匹配图标，但不承载
点击动作；完整业务区、两个同级指标以及无主辅关系的字段不使用该组件。

#### 组件属性

| Prop | 类型 | 要求 |
|---|---|---|
| `primaryText` | 显示值 | 必填；静态值、Expression 或 PathBinding |
| `secondaryText` | 显示值 | 必填；与主信息属于同一对象或指标 |
| `fontColor` | `#AARRGGBB` | 必填 |
| `backgroundColor` | `#AARRGGBB` | 必填 |
| `variant` | string | 按尺寸文件填写；2x2 可省略，2x4 必填 |
| `icon` | string | 可选；逐字使用当前素材候选的本地路径 |
| `fillColor` | `#AARRGGBB` | 可选；仅在传入可着色 `icon` 时使用 |

#### 槽位与容量

每个合法固定槽只放一个 `InfoBlock`，两行文字都必须保持单行可读。尺寸、variant 和具体槽位由 2x2/2x4
组件文件规定。

文字宽度不是背板宽度：扣除左右各8vp，带图标再扣24vp及4vp间距。当前2x2文字区无图标118vp、
有图标90vp；2x4为116vp或88vp。先放完整必要值，再用另一行表达短标签或状态，不把“会议开始”等
长前缀拼在时间前导致时间省略。用户没要求会议名时不为凑主辅行添加会议名；必要值放不下先取消图标，
仍不够则使用 Row/Column 组织 Text 等适合组件。组件自带 ellipsis 只是防御机制，不是允许裁掉必要信息。

#### 示例

```genui
["battery","InfoBlock",{"variant":"small","primaryText":"{{ ${/data/phoneBattery/batterySOC} + '%' }}","secondaryText":{"path":"/data/phoneBattery/chargingStatusDesc"},"fontColor":"#FF1F4799","backgroundColor":"#99FFFFFF"}]
```

#### 注意事项

无图标时不生成图标节点或空槽。`fillColor` 不能脱离 `icon` 单独出现；外层和内部组件均不得写
`onClick`。`ProgressCircle` 和 `W-split-panels` 的完整父区不属于 `InfoBlock`。

### 5.12.4 `ProgressLine2`

#### 选择条件

用于一个当前数值相对明确总量的真实线性进度，并同时展示该进度的可见读数。没有真实分母、总量或比例
关系时不使用；普通数值和仅因包含 `%` 的属性不自动成为进度。

#### 组件属性

| Prop | 类型 | 要求 |
|---|---|---|
| `value` | number 绑定 | 必填；绑定 number/integer 字段并驱动进度条 |
| `total` | number | 必填；静态正数 |
| `displayValue` | 显示值 | 必填；与 `value/total` 表达同一进度关系 |
| `unit` | string | 可选；读数未包含单位时填写静态单位 |
| `fontColor` | `#AARRGGBB` | 必填 |
| `color` | `#AARRGGBB` | 必填；进度色 |
| `backgroundColor` | `#AARRGGBB` | 必填；轨道色 |

#### 槽位与容量

只进入 2x4 `W-top-bottom` 的 progress-detail 整宽进度槽；读数固定使用与 `EmphasizedData` 相同的
`30fp/700` 主值和可选 `12fp/500` 单位，不用于 2x2。

#### 示例

```genui
["score","ProgressLine2",{"value":{"path":"/data/healthSport/sleepScore"},"total":100,"displayValue":{"path":"/data/healthSport/sleepScore"},"unit":"分","fontColor":"#FF563D99","color":"#FF563D99","backgroundColor":"#33563D99"}]
```

#### 注意事项

`value`、`total` 和 `displayValue` 必须属于同一事实，不能用一个字段驱动进度、另一个无关字段充当读数。
格式化字符串不能直接绑定给 `value`。

### 5.12.5 `TableText`

#### 选择条件

用于同一主题下 2–3 项同级“标签—值”。单项信息、存在唯一核心值的内容、事件时间线和需要表达比例
关系的内容不使用该组件。

#### 组件属性

| Prop | 类型 | 要求 |
|---|---|---|
| `items` | Array | 必填；2–3 项，每项只能包含 `label`、`value` |
| `items[].label` | string | 必填；静态非空标签 |
| `items[].value` | 显示值 | 必填；静态值、Expression 或 PathBinding |
| `fontColor` | `#AARRGGBB` | 必填 |

#### 槽位与容量

只进入 2x2 `S-title-dual-content` 的紧凑明细区。卡级标题、沉底上下文和动作不进入 `items`。

两行真实最小高度为 `16+2+16=34vp`，三行为 `52vp`；外面用明确高度、不可收缩的 Column 槽承载。
外部还有主信息或按钮时，先从总高度扣除它们。不能把组件的 layoutWeight 当成零高度，也不能放进
不足34/52vp的剩余空间。带动作卡中的全部正文只有约56–58vp时，优先用三行完整基础短文本，
不要同时使用大号主值、额外标签和表格。

#### 示例

```genui
["metrics","TableText",{"items":[{"label":"紫外线","value":{"path":"/data/weatherHealth/ultravioletLevel"}},{"label":"空气质量","value":{"path":"/data/weatherHealth/airQualityLevel"}}],"fontColor":"#FF1F4799"}]
```

#### 注意事项

标签和值分别对齐，每项只表达一个事实。不要将同一个值同时作为核心读数和表格项重复展示。

### 5.12.6 `TextBlock`

#### 选择条件

用于 2–4 个同级详情，每项由一个静态标签和一个值组成。当前布局需要一组等权详情背板时使用，不承担
主进度、卡级标题或动作。

#### 组件属性

| Prop | 类型 | 要求 |
|---|---|---|
| `items` | Array | 必填；2–4 项，每项只能包含 `label`、`value` |
| `items[].label` | string | 必填；静态非空标签 |
| `items[].value` | 显示值 | 必填；静态值、Expression 或 PathBinding |
| `fontColor` | `#AARRGGBB` | 必填 |
| `backgroundColor` | `#AARRGGBB` | 必填 |

#### 槽位与容量

只进入 2x4 `W-top-bottom` 的详情槽；转换器按 `items` 顺序生成 2–4 个等宽并列背板，项间距保持
`8vp`，每项高 `48vp`。项数增加时必须用压力文本检查单项宽度；不用于 2x2。

#### 示例

```genui
["details","TextBlock",{"items":[{"label":"睡眠时长","value":{"path":"/data/healthSport/nightSleepDurationText"}},{"label":"深睡时长","value":{"path":"/data/healthSport/deepSleepDurationText"}}],"fontColor":"#FF563D99","backgroundColor":"#99FFFFFF"}]
```

#### 注意事项

2–4 项必须同级且同属当前主题。不要把主指标或无关业务为了凑数放入同一个 `TextBlock`；
也不得删除第三、第四个必要同级详情来保留两项外观。

### 5.12.7 `CardButton`

#### 选择条件

用于 2x4 固定动作槽中的单个真实动作。只有当前事件候选提供匹配动作时使用；纯信息背板和没有候选的
操作文案不使用该组件。

#### 组件属性

| Prop | 类型 | 要求 |
|---|---|---|
| `label` | 显示值 | 必填；静态值、Expression 或 PathBinding |
| `onClick` | EventHandler[] | 必填；恰好一个当前事件候选中的 handler |
| `fontColor` | `#AARRGGBB` | 必填 |
| `backgroundColor` | `#AARRGGBB` | 必填 |
| `icon` | string | 可选；逐字使用当前素材候选的本地路径 |
| `fillColor` | `#AARRGGBB` | 可选；仅在传入可着色 `icon` 时使用 |

#### 槽位与容量

只进入 2x4 `W-content-side-slots` 或 `W-four-slots` 的 `132×57vp` 固定动作槽；一个实例只绑定一个动作，不用于 2x2。

#### 示例

```genui
["settings","CardButton",{"label":"蓝牙设置","fontColor":"#FF1F4799","backgroundColor":"#99FFFFFF","onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"bluetooth_entry"}}]}]
```

#### 注意事项

事件必须逐字复用当前候选。当前 Recipe 即使无图标也保留24vp中性视觉占位，文字宽度按槽宽减去
左右24vp内边距、24vp视觉位及8vp间距计算；132vp槽只剩76vp。动作应使用“查看天气”“电池设置”
这类完整短命令，已有分区标识时不重复拼城市或设备名。放不下且无法无歧义缩短时使用同槽位合法可点击
Row，不改 Recipe、不伪造图标、不让必要动作名省略。`fillColor` 不能脱离 `icon` 使用。

### 5.12.8 `ProgressCircleSingle`

#### 选择条件

用于一个具有真实比例范围的环形主指标。环心显示对象图标，右侧显示标签、读数和可选状态。普通数值、温度、时间和
无可靠总量的数据不使用。

#### 组件属性

| Prop | 类型 | 要求 |
|---|---|---|
| `value` | number 绑定 | 必填；绑定 number/integer 字段 |
| `total` | number | 必填；静态正数 |
| `icon` | string | 必填；逐字使用当前素材候选的本地路径 |
| `displayValue` | 显示值 | 必填；与环形进度表达同一数值 |
| `label` | string | 必填；静态非空说明 |
| `secondaryLabel` | 显示值 | 可选；同一对象的一条状态说明 |
| `fontColor`、`color`、`backgroundColor` | `#AARRGGBB` | 必填 |

#### 槽位与容量

只进入 2x4 `W-split-panels` 的 ring-detail 预设，环形主指标和右侧说明各占一个 `132×126vp` 父区。

#### 示例

```genui
["main","ProgressCircleSingle",{"value":{"path":"/data/phoneBattery/batterySOC"},"total":100,"icon":"resources/base/media/battery_leaf_fill.svg","displayValue":{"path":"/data/phoneBattery/batterySOCText"},"label":"手机电量","secondaryLabel":{"path":"/data/phoneBattery/chargingStatusDesc"},"fontColor":"#FF1F4799","color":"#FF1F4799","backgroundColor":"#331F4799"}]
```

#### 注意事项

`value`、`displayValue` 与 `secondaryLabel` 必须属于同一对象；图标只标识该对象，不代替可见读数。

### 5.12.9 `EventCard`

#### 选择条件

只用于 2x2 整卡唯一业务为 calendar 的单会议；多会议或混合其它业务时不使用。

#### 组件属性

| Prop | 类型 | 要求 |
|---|---|---|
| `title` | 显示值 | 必填；会议标题 |
| `time` | 显示值 | 必填；会议时间 |
| `location` | 显示值 | 可选；用户要求且有合法字段时使用 |
| `fontColor` | `#AARRGGBB` | 必填；标题使用该颜色，时间线及辅助文字由转换器生成 60% 内容色 |

#### 槽位与容量

固定作为 2x2 `S-title-content-action` root 的第二个直接子组件，前一项必须是日期上下文；最多显示标题、时间和地点三行。

#### 示例

```genui
["content_area","EventCard",{"title":{"path":"/data/calendar/events/0/title"},"time":{"path":"/data/calendar/events/0/dtStart"},"fontColor":"#FF8C4B1C"}]
```

#### 注意事项

组件已包含时间线轨道和文字列，不再手写轨道 Divider 或重复的标题、时间 Text。

### 5.12.10 `DataDisplay`

#### 选择条件

用于 2x2 中一个短标签、一个唯一核心数值和一条短支撑文本，例如倒计时名称、天数与静态单位。

#### 组件属性

| Prop | 类型 | 要求 |
|---|---|---|
| `label`、`supportingText` | string | 必填；静态非空短文本 |
| `value` | 显示值 | 必填；唯一核心值 |
| `fontColor` | `#AARRGGBB` | 必填；主值使用该颜色，标签和支撑文本由转换器生成 60% 内容色 |

#### 槽位与容量

只进入 2x2 `S-center` 的唯一内容区；三项各占一行，不吸收动作或第二个指标。

#### 示例

```genui
["display","DataDisplay",{"label":"运动会倒计时","value":{"path":"/data/countdown/countdownDays"},"supportingText":"天","fontColor":"#FFFFFFFF"}]
```

#### 注意事项

`supportingText` 是静态单位或短说明；值已含完整单位时改用其它合适组件，不重复单位。

### 5.12.11 `TopTextBottomValue`

#### 选择条件

用于 2x4 中恰好三个同级指标。存在唯一主指标、项目不足三项或字段不是同级关系时不使用。

#### 组件属性

| Prop | 类型 | 要求 |
|---|---|---|
| `items` | Array | 必填；恰好 3 项，每项只含 `label`、`value`、`unit` |
| `items[].label` | string | 必填；静态非空标签 |
| `items[].value` | 显示值 | 必填 |
| `items[].unit` | string | 必填；静态非空单位 |
| `fontColor`、`dividerColor` | `#AARRGGBB` | 必填 |

#### 槽位与容量

只进入 2x4 `W-top-bottom` 的 metric-triple 预设；转换器固定生成三个等宽指标区和两个分隔线。

#### 示例

```genui
["metrics","TopTextBottomValue",{"items":[{"label":"睡眠得分","value":80,"unit":"分"},{"label":"消耗热量","value":92,"unit":"千卡"},{"label":"今日步数","value":2031,"unit":"步"}],"fontColor":"#FF563D99","dividerColor":"#33563D99"}]
```

#### 注意事项

固定视觉顺序为标签在上、数值居中、单位在下；单位不得再次拼进 `value`。

### 5.12.12 `SummaryList`

#### 选择条件

用于 2–3 条同级、可单行完整显示的短摘要；长正文、标签—值或存在主次关系的内容不使用。

#### 组件属性

| Prop | 类型 | 要求 |
|---|---|---|
| `items` | Array | 必填；2–3 条显示值 |
| `fontColor`、`backgroundColor` | `#AARRGGBB` | 必填 |

#### 槽位与容量

只进入 2x4 `W-top-bottom` 的 list-rows 预设；每项固定为一个 `276×28vp` 单行背板。

#### 示例

```genui
["list","SummaryList",{"items":[{"path":"/data/calendar/events/0/title"},{"path":"/data/calendar/events/1/title"},{"path":"/data/calendar/events/2/title"}],"fontColor":"#FF8C4B1C","backgroundColor":"#99FFFFFF"}]
```

#### 注意事项

不使用动态模板，不在条目中再嵌套标签、按钮或图标；超出三条时切换布局或删去低优先级项。

### 5.12.13 选择检查

- 组件内容结构与真实信息关系一致，没有为了使用组件而合并无关字段或补造信息。
- 每个组件只使用自身属性表中的 Props，必填字段、绑定、素材和事件均来自当前输入。
- 组件进入当前尺寸文件允许的槽位，`InfoBlock.variant` 与槽位严格对应。
- 同一事实没有在多个组件中重复展示。
- 内容超出固定容量时更换组件或布局，不通过缩字号、增加行数或传入几何 Props 改写组件合同。

## 5.13 操作组件（PillButton / CircleButton）

两种操作组件都只输出一行且不带 children，由转换器展开为标准 A2UI 组件树；事件必须逐字使用当前候选。

### 5.13.1 `PillButton`

#### 选择条件

用于需要显示明确动作文字的内容区 CTA。只有当前事件候选提供匹配动作时使用；2x2 能显示动作文字时
优先于 `CircleButton`，2x4 用于完整内容区中的 `116×36vp` 或 `132×36vp` 直属动作，不进入固定模块槽。

#### 组件属性

| Prop | 类型 | 要求 |
|---|---|---|
| `label` | string | 必填；静态非空动作文字 |
| `onClick` | EventHandler[] | 必填；恰好一个当前事件候选中的 handler |
| `actionSurface` | `#AARRGGBB` | 必填；按钮背景色 |
| `actionInk` | `#AARRGGBB` | 必填；文字及单色图标前景色 |
| `icon` | string | 可选；逐字使用当前素材候选路径 |
| `fontSize` | number | 可选；只允许 `14` |
| `fontWeight` | number | 可选；只允许 `400` 或 `500` |
| `width` | number / `matchParent` | 可选；2x2 为 `126|matchParent`，2x4 为 `116|132|matchParent` |

#### 槽位与容量

固定为底部胶囊按钮，高 `36vp`、圆角 `30vp`。2x2 单动作放在带动作布局的末尾
`action_area Column` 内，`S-content-dual-action` 直接纵排两个实例；2x4 按槽位显式填写
`width:116|132`，只进入 `W-split-panels` 或 `W-content-side-slots` 的完整内容区动作位。

#### 示例

```genui
["cta","PillButton",{"label":"蓝牙设置","actionSurface":"#331F4799","actionInk":"#FF1F4799","fontSize":14,"fontWeight":400,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"bluetooth_entry"}}]}]
```

#### 注意事项

有 icon 时转换器固定生成 `20×20vp` 图标与文字、间距 `8vp` 并整体居中。浅色与融球配色按第十二节成对填写；不要再手写相同的可点击 Row 皮肤。
CTA 文案只保留“动作 + 必要对象”，但不能改变真实目标；2x2 优先 2–4 个汉字、最多 6 个，2x4
优先不超过 6 个、最多 8 个。标签仍无法完整容纳时更换布局，不裁切、不缩到 `12fp` 以下，也不回退为基础 `Button`。

### 5.13.2 `CircleButton`

#### 选择条件

仅用于 2x2 右下锚点的纯图标动作。只有正文无法容纳底部 `PillButton`、图标语义明确且存在准确素材时使用。

#### 组件属性

| Prop | 类型 | 要求 |
|---|---|---|
| `icon` | string | 必填；逐字使用当前素材候选路径 |
| `accessibility` | object | 必填；必须包含静态非空 `label`，可选静态 `description` |
| `onClick` | EventHandler[] | 必填；恰好一个当前事件候选中的 handler |
| `actionSurface` | `#AARRGGBB` | 必填；按钮背景色 |
| `actionInk` | `#AARRGGBB` | 必填；单色图标前景色 |

#### 槽位与容量

按钮本体固定 `36×36vp`、圆角 `18vp`，中心图标固定 `20×20vp`；外层必须使用当前尺寸文件规定的 `40×40vp` 右下锚点槽。

#### 示例

```genui
["play_action","CircleButton",{"icon":"resources/base/media/play_fill.svg","accessibility":{"label":"播放音乐"},"actionSurface":"#331F4799","actionInk":"#FF1F4799","onClick":[{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://play"}}]}]
```

#### 注意事项

禁止 `label`，也不传 width、height、position、边距或排版属性。`accessibility.label` 写完整动作名称；同一动作不得同时生成 `CircleButton` 和 `PillButton`。

## 5.14 `CardHeader`（2x2/2x4）

- `CardHeader` 是 claw-widget `SingleLineTitle` 在 Compact DSL 中的对应版本，命名继续使用 `CardHeader`。它可以表示卡级标题，
  也可以表示任意内容分区的单行标题；标题的层级由它在组件树中的位置决定，不新增 `role`。只输出一行，
  不带 children 或动作。标题必须是稳定的业务、对象、事项或分组主题，禁止把 `eventCount`、电量、温度、状态等数值或业务数据冒充标题。
  日期、时间、时长和倒计时短语放在内容区，不把 userQuery 中的时间硬编码为标题。日程、会议或提醒优先使用真实事项名称或用户明确主题；
  没有可用事项主题时使用“日程”。
- 必填 `title`（非空文字、完整 Expression 或 PathBinding）、`fontColor`（所在卡级或分区标题色）；可选 `icon`（候选原始 src）、`fillColor`（单色图标与标题完全同色，多色/品牌图标及位图省略）。不传 icon 就只显示标题，是否传入在布局前按 2.5 节决定，CardHeader 不自行增加图标。
- 卡级 CardHeader 每卡最多一个，必须是对应前景根 Column 的第一个直接子组件；分区 CardHeader 作为所属内容分区的第一个直接子组件，
  每个分区最多一个，同一卡可按真实分区数使用多个。不嵌入指标值、进度环、按钮或其他内容组件内部；所属内容在它下方排列。
- 转换器固定标题行高度 `20vp`、不可收缩，文字左对齐、垂直居中、`12fp/400`；可选图标固定 `20×20vp`，文字与图标间距 `8vp`。
  卡级标题宽度由当前尺寸安全区决定；分区标题跟随所在分区宽度。无图标时文字槽占满，不留空槽。
- 可按所属卡级或分区槽位传正数 `width` 或 `"matchParent"`；`height` 省略或只能写 `20`，不接受 padding/margin/fontSize/fontWeight 等内部视觉覆盖。保留完整标题文字要求，
  槽位不足时缩短非必要标题文案，不靠缩字号或截断掩盖；固定标题行计入 `20vp` 高度预算。
- 转换器展开为同 id 的 Row，以及 `<id>_title`、可选 `<id>_icon`；源 DSL 不得再声明这些子组件 id。非法结构或定位属性报错并进入现有修复链路，不自动搬移组件。

卡级示例：`["header","CardHeader",{"title":"天气","fontColor":"#FF1F4799","icon":"resources/base/media/sun_max.svg","fillColor":"#FF1F4799"}]`

分区示例：`["phone_header","CardHeader",{"title":"手机","fontColor":"#FF1F4799","width":116}]`

<!-- /prompt:catalog -->

<!-- prompt:icon-style -->
# 十一、图标、按钮与图表

## 11.1 图标

- 标题文字固定 `12fp/400`，不得加粗，不得因场景或示例升到 `14/16fp` 或 `500/700`。
- `2x2` 顶部第一行文字信息若不是 CardHeader，必须为纯文字，不在文字前后或该行右侧配图标；无论它被命名为标题、倒计时、状态或业务说明，也无论左对齐、居中、单业务或多业务，都执行本条。例如「北京出差还有 30 天出发」不生成飞机 Image 或图标槽。其他居中标题或说明行同样只用文字；用户明确要求图标时除外。不得将首行前缀图标解释为内容区主视觉来绕过本条；`S-dual-info` 双业务分区主视觉不属于顶部标题行，仅与进度环内图标、图文按钮一起按 2.5 节允许位置、总数和互斥规则执行。
- 标题图标仅在已分配图标名额时显示，固定 `20×20vp`，位于所属 CardHeader 右侧；`2x2` 卡级标题图标贴安全区右上角，
  右边缘距 root 右边 `12vp`。分区标题图标跟随所属分区的 CardHeader 右边缘，不跨区对齐到卡片边缘。
- 由基础布局组件直接组织的 Image 遵循所在布局预算，未单独规定时使用 `20×20vp`；组件 Recipe 内部图标尺寸由 Recipe 决定，例如 `InfoBlock` 与 `CardButton` 的 `24×24vp` 视觉，不以通用图标规则覆盖。按钮点击外框、进度环和真实内容图片不属于图标尺寸。
- 同一卡片图标风格、色彩角色和视觉重量保持一致。
- 多来源组合卡不使用某一个 App 图标冒充整卡身份。

<!-- /prompt:icon-style -->
