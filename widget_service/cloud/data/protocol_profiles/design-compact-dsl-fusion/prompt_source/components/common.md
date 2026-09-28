# 通用组件合同（维护源）

> 维护说明不发给模型；仅 `prompt` 标记内正文参与构建。

## 边界与阅读顺序

基础组件总表 → Props/绑定/样式 → ActionUnit / CardHeader → 图标规范。组件边界不等于组合边界。

## 组件总表（维护导航，不发模型）

| 组件 | 用途 / 触发 | Props 与绑定入口 | 容量 / 样式及示例入口 |
|---|---|---|---|
| Text | 真实文本/读数 | 5.3、5.13；content | core typography；fewshots 各例 |
| Image | 语义准确且状态安全的素材 | 5.4；src/fillColor/objectFit | 11.1 与尺寸限制；2x2 V07 |
| Divider | 真实分隔 | 5.5；vertical/color/strokeWidth | 2x4 V05 |
| Progress | 真实比例且有数值与可靠范围 | 前置门禁、5.6/5.13；value/total/type | combinations 环图；2x4 V02/V03 |
| Button | 纯文字合法动作 | 5.7/5.13；label/enabled/onClick | combinations 动作；2x4 V09 |
| Checkbox | 用户明确的选择/完成状态 | 5.8；静态 label/value/select | 不推断动态绑定；不替代 Toggle |
| Row | 横向真实内容 | 5.9；children/轴向对齐/itemMargin | layouts 预算；各案例 |
| Column | 纵向真实内容 | 5.10；children/轴向对齐/itemMargin | layouts 预算；各案例 |
| List | 少量摘要列表 | 5.11；children/listDirection | 2–3 条，不使用动态模板 |
| Stack | 合法叠放 | 5.12；children/alignContent | combinations 环心；2x4 V02 |
| ActionUnit | 卡级 CTA 封装 | 5.14；state/label/icon/onClick/配色 | 转换器展开；2x2 V03 |
| CardHeader | 稳定卡片主题 | 5.15；title/fontColor/icon/fillColor | 不接受任意几何覆盖；本节单组件示例 |
| TimelineUnit | 小卡单会议 | 转至 components/2x2.md | 2x2 V06；宽卡禁止 |

每个组件以正文原有合同为准，单组件的绑定支持不能推导到其它 Props。
完整案例在 `../fewshots/`，组合条件在 `../combinations/`，不把示例中的属性自动扩展为通用合同。

## 片段索引

| 片段 | 基线来源 |
|---|---|
| `progress-type` | `PROMPT.md` |
| `progress-trigger` | `PROMPT.md` |
| `catalog` | `PROMPT.md` |
| `icon-style` | `PROMPT.md` |

正文保留原章节编号及引用，以保持生成后的章节裁剪行为。修改正文后运行构建与回归，禁止手改 generated。

<!-- prompt:progress-type -->
**Progress 数值类型前置约束**：`Progress.value` 必须绑定 number/integer 字段。若 TaskSpec 只有 `batterySOCText:"68%"` 一类格式化字符串，即使用户要求进度条也不得生成空环或空进度条，改用完整 Text 主读数；禁止从字符串中猜测、截取或隐式转换数值。

<!-- /prompt:progress-type -->

<!-- prompt:progress-trigger -->
**Progress 生成前置约束**：默认不生成 Progress。只有 TaskSpec 的字段描述明确表示百分比、完成度、使用率、电量等比例语义，并且同时存在可验证的固定范围或真实 `total` 时才允许；温度、日期、时间、时长、倒计时、状态、名称和普通数值一律禁止。不得仅因字段是 number/integer、位于小内容背板或示例中存在环图就生成 Progress，也不得自行猜测 `total`；两座城市天气的 `S-dual-info` 分区只能使用合法天气 Image 或无 visual，绝不使用温度进度环。2x2 单业务内容区若只有一个环形 Progress 和至多一行状态文字，两者必须作为一个紧凑组水平居中，承载它们的 Column 固定 `alignItems:"center"`，不得让环和状态沿左边缘排列。

<!-- /prompt:progress-trigger -->

<!-- prompt:catalog -->
# 五、组件协议

只允许以下十种基础组件：

`Text`、`Image`、`Divider`、`Progress`、`Button`、`Checkbox`、`Row`、`Column`、`List`、`Stack`

此外只允许使用 5.14 的 `ActionUnit`、5.15 的 `CardHeader` 和 5.16 的 `TimelineUnit`，均由转换器展开为基础组件，不是新增端侧组件；禁止自造其它高级组件。

禁止：

`TextInput`、`Toggle`、`Radio`、`CheckboxGroup`、`Select`、`NavContainer`、`Tabs`、`TabContent`、`Web`、`Grid`、`If`

禁止所有组件的 `theme`、`onAppear`、`onChange`、`onSelect`、`onReachStart`、`onReachEnd`；Button 禁止 `action`。

## 5.1 通用 props 字段

每个组件行的第三项 `props` 可使用：

- `content`：Text 必填；字符串、完整 Expression 或 PathBinding。
- `src`：Image 必填；assetCandidates 中的本地资源路径、完整 Expression 或 PathBinding。
- `label`：Button 必填；字符串、完整 Expression 或 PathBinding。
- `value/total/enabled/select`：按对应组件规则使用。
- `children`：禁止写入 props；容器 children 必须写在组件行第 4 项。
- `itemMargin`：Row、Column、List 可选数字 vp；`space` 是兼容别名，优先使用 `itemMargin`。
- `onClick`：可选 EventHandler 数组，只在有匹配事件候选时使用。
- `accessibility`：可选对象，只允许静态短字符串 `label` 和 `description`。
- `design`：可选语义化设计令牌；只能使用本节列出的有意义命名，不使用缩写、尺寸编号或颜色编号。

## 5.2 通用布局与样式 props

以下字段直接写在组件行第三项 `props`，不得嵌套 `styles`：

`width`、`height`、`constraintSize`、`aspectRatio`、`margin`、`padding`、`borderRadius`、`borderWidth`、`borderColor`、`backgroundColor`、`backgroundImage`、`backgroundImageSizeWithStyle`、`linearGradient`、`shadow`、`layoutWeight`、`flexShrink`、`visibility`、`clip`

规则：

- root 的 `width/height` 一律写 `"matchParent"`（2x2/2x4 画布尺寸由 surface 决定，不写数值）；关键内部容器、主图、按钮、Progress 使用数值宽高。
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

除 root 融球 Style Design Token 外，不使用 design 语义令牌或色彩令牌；字号、字重、颜色、圆角、间距一律按批准档位显式写在 props（`fontSize`、`fontWeight`、`fontColor`、`fillColor`、`backgroundColor` 等，颜色只写 `#AARRGGBB`），取色逻辑见第十二节。`Progress` 必须使用 `type` 明确形态：横向进度写 `type:"linear"`，环形进度写 `type:"ring"`；禁止给 Progress 写 `design`，也禁止省略 `type` 后依赖转换器猜测形态。

- 融球的业务、尺寸、密度和运行时条件统一按第十二节执行；满足条件且无用户自定义背景要求时优先使用对应融球。
- 不满足融球条件时使用第十二节固定浅色微渐变；多业务按主要业务取色，无明确主次或未覆盖业务默认蓝色。
- 使用融球 Design Token 时，root 的背景只写 `design`，不再写 `backgroundColor`、`linearGradient` 或 `backgroundImage`；尺寸、内边距、圆角、裁剪和布局属性仍按 root 规则显式填写。转换器会确定性展开融球背景，并把前景根的原 ID `root` 加上 `__genui_render_component__` 前缀，生成 `__genui_render_component__root` 防溢出标识；展开后的外层卡片根仍使用 `root`。

## 5.3 Text

顶层：

- 必填 `content`：字符串、完整 Expression 或 PathBinding。
- `content` 不得是空字符串或纯空白。不得用空 Text 绘制圆点、占位、留白或承担尺寸撑开；圆点等必要标记使用可见短符号，纯间距使用父容器布局，无法用合法组件表达时删除该装饰。

props 可用样式字段：

`fontSize`、`fontWeight`、`fontColor`、`maxLines`、`minFontSize`、`maxFontSize`、`textAlign`，以及通用布局与样式 props。

- `fontWeight` 使用 `100-900`，按 100 递增。
- `textAlign` 只取 `start|center|end|justify`。
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

## 5.6 Progress

顶层：

- 必填 `value`：number、完整 Expression 或 PathBinding，运行时可动态更新。
- 可选 `total`：优先使用大于 `0` 的稳定静态 number；未提供时按协议默认值处理。
- 首帧和运行时的 `value` 都必须是有限 number，并满足 `0 <= value <= total`。首帧数据行中的对应值也必须落在该范围内。
- 动态 `value` 只能引用 `number/integer` 字段，且字段说明、范围或业务语义必须足以证明其不会超过 `total`；格式化百分比字符串（如 `"18%"`）、温度文本或其它字符串不能直接绑定给 Progress。
- 无法可靠确定 `total`、无法保证动态值范围，或只能依赖越界值、负数、字符串到数字的隐式转换时，不生成 Progress，改用 Text 展示原始信息。

props 可用样式字段：

- `type` 必填且只取 `linear|ring`；横向进度固定使用 `linear`，环形进度固定使用 `ring`，不得使用其它形态值或别名。
- `color` 是纯色字符串或协议允许的动态值，不支持渐变。
- `strokeWidth` 是数字 vp。
- ring 必须写相同的稳定 `width/height`。

只有数据具有明确目标、总量、范围或百分比语义时才使用 Progress。没有进度语义时改用 Text，不把任意数值包装成环形图。

## 5.7 Button

顶层：

- 必填 `label`：字符串、完整 Expression 或 PathBinding。
- 可选 `enabled`：boolean、完整 Expression 或 PathBinding。
- 可选合法 `onClick`。

props 可用文字样式和通用布局与样式字段。

- 禁止 `Button.action`。
- 协议中的 Button 组件只支持 `label`，用于纯文字按钮；它本身不支持图标或 `children`。
- 可点击 Button 必须有匹配事件候选；没有事件时改成普通 Text/Row 支撑信息。
- 图文按钮是正式支持的交互形态。`2x2` 仅在用户明确指定或已按 2.5 节分配按钮图标名额时使用；`2x4` 沿用原选择规则。使用带 `onClick` 的 Row 作为完整按钮容器，内部放 Image 和 Text；不得因 Button 不支持图标而删除用户指定图标，也不得给 Button 增加协议外图标字段。
- CTA 是受保护文本，必须完整显示；但除非用户明确指定必须逐字保留，生成时应先将按钮文案压缩为不改变动作目标的最短自然表达。
- Button 文案只保留“动作 + 必要对象”，删除不影响动作的状态、原因、结果预告、礼貌词和交互提示。例如使用“导航回家”“打开天气”“查看详情”“清理内存”，不使用“下雨了，点击导航回家”“立即一键清理内存”“点击这里查看天气详情”。
- `2x2` 的 Button/图文按钮文案优先为 2 至 4 个汉字，最多 6 个汉字；`2x4` 优先不超过 6 个汉字，最多 8 个汉字。确需更长且不能等义缩短时，必须使用更宽按钮或降低到批准字号，不能裁切。
- Button 的最小内容宽度按 `压力文本宽度 × 1.2 + 左右 padding` 计算；先精简文案，再调整宽度，最后才允许降到 `12fp`。不得通过 `ellipsis`、`clip`、极窄宽度或低于 `12fp` 的按钮文字解决溢出。

## 5.8 Checkbox

顶层可用 `label`、`value`、`select` 和合法 `onClick`。

- `label/value` 只能是静态字符串。
- `select` 只能是静态 boolean 初始状态，不支持 Expression 或 PathBinding。
- props `selectedColor` 为颜色，`shape` 只取 `circle|rounded_square`。
- 只在用户明确需要完成状态或选择状态且事件能力可用时使用；不要用 Checkbox 伪造 Toggle 或 Radio。

## 5.9 Row

顶层：

- 必填 `children`：组件 id 字符串数组。
- 可选 `itemMargin`：数字 vp。

props 可用样式字段：

- `justifyContent`：`start|center|end|spaceAround|spaceBetween|spaceEvenly`。
- `alignItems`：`top|center|bottom`。
- `justifyContent` 为 `spaceAround|spaceBetween|spaceEvenly` 时，`itemMargin` 仍作为相邻子项之间必须保留的最小间距；扣除该间距后，只能将非负剩余空间交给分布式对齐。两者可以同时设置，但不能依赖分布式对齐消除负剩余空间。

## 5.10 Column

顶层：

- 必填 `children`：组件 id 字符串数组。
- 可选 `itemMargin`：数字 vp。

props 可用样式字段：

- `justifyContent`：`start|center|end|spaceAround|spaceBetween|spaceEvenly`。
- `alignItems`：`start|center|end`。
- `justifyContent` 为 `spaceAround|spaceBetween|spaceEvenly` 时，`itemMargin` 仍作为相邻子项之间必须保留的最小间距；扣除该间距后，只能将非负剩余空间交给分布式对齐。两者可以同时设置，但不能依赖分布式对齐消除负剩余空间。

## 5.11 List

顶层：

- 必填 `children`：组件 id 字符串数组。
- 可选 `space`：数字。

props 可用样式字段：

- `listDirection`：`vertical|horizontal`。
- `scrollBar`：`off|auto|on`，桌面卡片默认 `off`。

只展示 2 至 3 条短摘要；不生成长滚动列表。

## 5.12 Stack

顶层：

- 必填 `children`：只能是组件 id 字符串数组，不支持模板对象。

props 可用样式字段：

- `alignContent`：`topStart|top|topEnd|start|center|end|bottomStart|bottom|bottomEnd`。

只用于真实叠加，例如 Progress 环与中心数值、背景与前景或图标底板；不得覆盖受保护文本和动作。

## 5.13 生成时的动态绑定边界

属性是否支持动态值必须逐项判断。本服务为稳定布局采用以下受控子集：

| props 字段 | 允许的动态形式 | 约束 |
|---|---|---|
| Text.content / CardHeader.title | Expression、PathBinding | 结果必须可展示为文本 |
| Image.src | Expression、PathBinding | 首帧值及运行时可能值都必须是 assetCandidates 中的原始 `src`；不能证明时使用静态素材 |
| Progress.value | Expression、PathBinding | 引用 number/integer，或表达式计算结果为 number |
| Button.label / Button.enabled | Expression、PathBinding | 分别返回 string 和 boolean |
| 事件参数 | 仅复用候选中已有的动态值 | 不自行新增、改写或移动绑定 |
| Row/Column/List.children | 不允许动态模板 | 只能使用组件 id 字符串数组 |
| Checkbox.label / value / select、Progress.total、Stack.children | 不允许 | 只能使用对应的静态合法值 |

为减少布局漂移，生成新卡片时所有布局样式 props 默认使用静态合法值，不动态绑定尺寸、间距、圆角、排版、背景或对齐。不要因为组件的某个属性支持 Expression，就推断其它属性也支持。

## 5.14 高级组件（ActionUnit）

ActionUnit 是对卡级 CTA 的受控封装，只输出一行且不带 children，由转换器展开为完整结构；2x2 的卡级 CTA 优先使用它。

ActionUnit——卡级 CTA：

- `state:"capsule"`：底部通栏文字胶囊（126x36、radius 20、文字 14），必须有 `label` 和 `onClick`；有匹配动作图标且已按 2.5 节分配名额时可写 `icon`，转换器展开为图标+文字整体居中，图标与文字间距固定 `8vp`，配色按第十二节浅色微渐变、融球两种按钮规则执行。
- `state:"icon-round"`：仅用于 2x2 `S-title-anchor`；外层操作槽为 40×40vp，内部圆钮为 36×36vp，中心图标为 20×20vp。必须有 `icon` 和 `onClick`，禁止 `label`；按钮背景和单色图标按第十二节按钮规则取色，不另设白底模式。
- 可用字段：`state`、`label`、`icon`、`actionInk`、`actionSurface`、`fontSize`、`fontWeight`、`onClick`、`flexShrink`。
- `actionSurface` 是按钮背景色，`actionInk` 是按钮文字色，必须成对显式写 `#AARRGGBB`，按第十二节固定配对；浅色按钮使用第十二节按钮背景与主文字色，融球为白色 20% 按钮背景和 90% 文字，图标由转换器使用白色 60%。按钮文字使用 14/400-500。
- capsule 只能放在 root 最后一个 `action_area Column` 内且是其唯一子节点；双按钮（`S-content-dual-action` 骨架）在该 Column 内纵排两张 capsule。不要用基础 `Button` 手写 CTA 皮，也不要再额外输出 action_icon Image 行。

## 5.15 高级组件（CardHeader，2x2/2x4）

- CardHeader 封装独立卡片标题和可选右上角辅助图标，只输出一行，不带 children、动作或布局样式；标题必须是稳定的业务、对象或事项主题，禁止把 `eventCount`、电量、温度、状态等数值或业务数据冒充标题。日期、时间、时长和倒计时短语只能放在内容区，`明天上午10点`、`14:00`、`还有3天` 等即使出现在 userQuery 中也绝对不能作为 CardHeader；存在对应动态字段时更禁止把 userQuery 中的时间硬编码为标题。日程、会议或提醒优先使用真实事项名称或用户明确主题（如“医院复查”）；没有可用事项主题时固定使用默认标题“日程”，不得省略标题。2x2 仅用于 带标题布局 有独立标题的布局，`S-center`、`S-content-dual-action`、`S-dual-info` 不使用；2x4 仅允许单数据块布局按骨架使用，2-4 个数据块的 `W-four-slots`/`W-split-panels`/`W-content-side-slots` 不使用，无标题布局和作为正文上下文的 kicker 不使用，也不预留空标题位。
- 必填 `title`（非空文字、完整 Expression 或 PathBinding）、`fontColor`（本卡标题色）；可选 `icon`（候选原始 src）、`fillColor`（单色图标与标题完全同色，多色/品牌图标及位图省略）。不传 icon 就只显示标题，是否传入在布局前按 2.5 节决定，CardHeader 不自行增加图标。
- 每卡最多一个。2x2 中必须是 root 的第一个且唯一父级的直接子组件，root 必须为 Column；2x4 中必须是 `root Stack` 下全尺寸前景 Column 的第一个且唯一父级的直接子组件。承载 CardHeader 的 Column 必须显式 `width:"matchParent"`、`height:"matchParent"`（2x4）、`padding:12`，并显式使用 `justifyContent:"start"` 或保证首项贴顶的 `"spaceBetween"`，不加 borderWidth。其他内容在标题下方布局，不得嵌套、重复、错序或用 center/spaceAround/spaceEvenly 移动标题。
- 转换器固定标题行高度 `20vp`、不可收缩，2x2/2x4 宽度分别为 `126/276vp`，左上角均为 `(12,12)`。文字左对齐、垂直居中、`12fp/400`；有图标时文字槽宽分别为 `98/248vp`、间距 8vp，图标固定 20×20vp，左上角分别为 `(118,12)`/`(268,12)`；无图标时文字槽占满，不留空槽。
- 不接受 width/height/padding/margin/fontSize/fontWeight 等覆盖字段。保留完整标题文字要求，槽位不足时缩短非必要标题文案，不靠缩字号或截断掩盖；固定标题行计入 20vp 高度预算，长内容仍需做压力检查。
- 转换器展开为同 id 的 Row，以及 `<id>_title`、可选 `<id>_icon`；源 DSL 不得再声明这些子组件 id。非法结构或定位属性报错并进入现有修复链路，不自动搬移组件。

示例：`["header","CardHeader",{"title":"天气","fontColor":"#FF1F4799","icon":"resources/base/media/sun_max.svg","fillColor":"#FF1F4799"}]`

<!-- /prompt:catalog -->

<!-- prompt:icon-style -->
# 十一、图标、按钮与图表

## 11.1 图标

- 标题文字固定 `12fp/400`，不得加粗，不得因场景或示例升到 `14/16fp` 或 `500/700`。
- `2x2` 顶部第一行文字信息若不是 CardHeader，必须为纯文字，不在文字前后或该行右侧配图标；无论它被命名为标题、倒计时、状态或业务说明，也无论左对齐、居中、单业务或多业务，都执行本条。例如「北京出差还有 30 天出发」不生成飞机 Image 或图标槽。其他居中标题或说明行同样只用文字；用户明确要求图标时除外。不得将首行前缀图标解释为内容区主视觉来绕过本条；`S-dual-info` 双业务分区主视觉不属于顶部标题行，仅与进度环内图标、图文按钮一起按 2.5 节允许位置、总数和互斥规则执行。
- 标题图标仅在已分配图标名额时显示，固定 `20×20vp`，通常位于标题行右侧；在 `2x2` 标题行中必须贴安全区右上角，右边缘距 root 右边 `12vp`。
- `2x2` 和 `2x4` 的所有图标，包括标题、按钮、分区及进度环内图标，全部固定 `20×20vp`，不存在普通、辅助或主视觉图标的尺寸分档，也不因用户要求或布局角色改用其他尺寸；按钮点击外框、进度环和真实内容图片不属于图标尺寸，不随之修改。
- 同一卡片图标风格、色彩角色和视觉重量保持一致。
- 多来源组合卡不使用某一个 App 图标冒充整卡身份。

<!-- /prompt:icon-style -->
