# 通用组合（维护源）

> 维护说明不发给模型；仅 `prompt` 标记内正文参与构建。

## 边界与阅读顺序

并列指标 → 数字/单位 → 小背板文字/visual → 图文动作 → 环图。只组合已注册组件，不定义新组件名称。

## 组合总表（维护导航，不发模型）

| 组合 | 成立条件 / 构成 | 内容与绑定关系 | 示例 / 不适用 |
|---|---|---|---|
| 数值 + 单位 | number/integer；Row 中相邻 Text | 一个真实字段 + 一次真实单位；字底补偿 | 2x2 V07；已带单位字符串不拆 |
| 同级双指标 | 同对象、天然对照且宽度成立；Row → 两 Column | 每列值和自己的标签成组、统一强调 | 2x2 V13；非同级不强做对称 |
| 三状态标签值 | 三项同级状态；纵排对齐 | 标签和值一一对应，不造 hero | 2x2 V14；不横向硬塞 |
| 图文动作 | 合法事件与准确图标；clickable Row → Image/Text | onClick 只放外层，子组件不重复绑定 | 2x2 V11；`W-content-side-slots`/`W-content-side-slots` 有专属左右顺序 |
| 环心内容 | 真比例；Stack → ring Progress + 中心内容 | Progress 与读数可共享路径，不额外复制事实 | 2x4 V02；linear 不得叠放 |
| 小背板文字 + visual | 固定小背板；Row → 文字列 + visual | 对象名、主数据、辅助数据归同一对象 | 2x2 V05、2x4 V06；三事实移除 visual |

这是组合定位表，规范正文和尺寸变体优先；不新增组件名称。片段代码以对应完整案例的局部组件树为准。

## 片段索引

| 片段 | 基线来源 |
|---|---|
| `peer-metrics` | `PROMPT.md` |
| `baseline-correction` | `PROMPT.md` |
| `small-panel` | `PROMPT.md` |
| `value-unit` | `PROMPT.md` |
| `action-combination` | `PROMPT.md` |
| `progress-combination` | `PROMPT.md` |

正文保留原章节编号及引用，以保持生成后的章节裁剪行为。修改正文后运行构建与回归，禁止手改 generated。

<!-- prompt:peer-metrics -->
**单业务并行指标生成前置约束**：大数字 `value_row` 只能包含纯数字 Text 和紧邻的真实单位 Text，禁止在该 Row 内放入标签、方向、状态、名称、说明或其它字段；这些信息必须放在主值下一行。`value_row` 固定使用 `alignItems:"bottom"`，单位 Text 不设置与数字相同的固定高度，并按字号差使用 `min(8, ceil((最大字号-单位字号)/4))` 的 `padding.bottom` 校正可见字底。主值绑定 string、名称或状态时不得生成相邻单位 Text，例如 `exerciseTypeName="户外跑步"` 后不能再追加“跑步”。先依据 userQuery 和字段 description 判断各指标是主辅关系还是同级关系，不得按字段顺序、文本长度或 sampleValue 大小任意选择 hero。同一业务对象内存在最高/最低、当前/目标、已用/剩余、左/右等同级量化指标时，禁止选中其中一项使用 `30fp/38fp` hero、数值与标签混合字号 Row 以及多个大数字 `value_row`。两个同级指标只有都具备可靠比例语义时，才能进入已登记的双列环形指标布局；2x2 使用 59 + 8 + 59vp，Sub-118 使用 54 + 8 + 54vp，Sub-140 使用 62 + 8 + 62vp，每列一个环形 Progress 及其自己的值和标签。普通文字、状态或无可靠 total 的指标一律使用两条对齐的纵向“标签—值”行，不得自造普通等宽文字列或竖向 Divider。恰好三个同级状态、等级或分类指标时，不从中制造无标签 hero；使用最多三条纵向标签—值行，标签列和值列分别共享对齐线，值统一 `14fp/16fp` 与字重，整组在剩余内容区垂直居中。日期、地点、来源、更新时间等元数据放到底部弱提示，不参与并列焦点组。此规则适用于 2x2 普通布局，也适用于 2x4 Sub-118/Sub-140；不适用于 V01、V06、`S-content-dual-action`、`S-dual-info` 和 2x4 固定小背板。

<!-- /prompt:peer-metrics -->

<!-- prompt:baseline-correction -->
**同行文字可见字底校正约束**：2x2 与 2x4 的同一 Row 只要包含不同字号 Text，Row 固定 `alignItems:"bottom"`；每个较小 Text 的 `padding.bottom` 使用 `min(8, ceil((最大字号-自身字号)/4))`，最多补偿 `8vp`。数字与单位 Row 另固定 `itemMargin:2`，数字和单位都使用内容自适应宽度。

<!-- /prompt:baseline-correction -->

<!-- prompt:small-panel -->
- 小内容区域统一指 2x2 `S-dual-info` 的 `134×63vp` 分区和 2x4 `W-four-slots`/`W-content-side-slots` 的 `132×57vp` 固定槽，只允许两个单行 Text：第一行对象名与主数据使用 `14fp/700`，第二行辅助数据使用 `12fp/400`；两个 Text 都必须显式设置 `maxLines:1`。1-2 项数据可在存在准确素材时使用一个右侧图标；3 项时不使用 visual，并在容量不足时删除最低优先级项。固定槽不得嵌套胶囊按钮或第三行文字。
- 小内容蒙版使用图标时固定为 `Row -> [text_column, visual]`，即使只有一行文字也必须用定宽 `text_column` 包装；父 Row 的 `itemMargin` 只能是 `8vp`，不得按通用组间距改成 10/12/16vp，也不得省略或写 0。visual 固定在右侧并垂直居中，右边缘距蒙版右边固定 12vp。独立 Image 固定 `20×20vp`：2x2 文字列宽 74vp，并满足 `12 + 74 + 8 + 20 + 12 = 126`；2x4 文字列宽 82vp，并满足 `12 + 82 + 8 + 20 + 12 = 134`。仅有 1-2 项信息，且目标字段通过 11.3 节 Progress 比例语义与可靠 `total` 检查时，visual 才可以是右侧环图；否则只能使用合法 Image 或删除 visual，严禁把任意数值包装成环。合法环按环外框右边缘距蒙版右边 12vp：2x2 `S-dual-info` 使用 `44×44vp` 环和 60vp 文字列，2x4 `W-four-slots` 使用 `40×40vp` 环和 72vp 文字列；中心图标保持 20×20vp。3 项时必须删除包括 Image、Progress 和环中心内容在内的整个 visual；无合法图标且无合法环图时同样删除 visual，文字列占满蒙版内部宽度。
<!-- /prompt:small-panel -->

<!-- prompt:value-unit -->
数字与单位拆分：

- 同一动态字段或同一语义事实在一张卡片中最多由一个可见 Text 展示一次，禁止同时放入主值、`value_unit`、辅助行或其它 Text；Progress 与紧邻数值 Text 共用数值路径、事件参数引用该路径不算重复展示。
- 日程 `eventCount` 不是独立主信息。用户要求安排数量时，只能在日程所属区域与时间范围或“项安排”等上下文组成一条完整摘要，例如“未来7天 2项安排”；禁止把纯 `eventCount`、`1`、`1件` 或 `1项` 单独占一行，更不得放进倒计时背板。
- `remindTime`、`remindMinutes` 等数值提醒字段必须显示完整分钟语义，例如“提前 15 分钟”；禁止只显示裸数字。`windLevel` 必须显示为“风力 2级”或与明确的“风力”标签紧邻，禁止只显示“2级”。
- 时间范围必须同时绑定开始值和结束值。任一端缺失时只显示已有的完整单值并删除范围分隔符；禁止输出以 `-`、`~`、`至` 结尾的残缺日期或时间范围。
- “点击/打开/查看/设置/导航/拨打”等动作措辞只允许出现在具有合法 `onClick` 的 Button、ActionUnit 或可点击背板中；没有点击祖先时必须删除动作措辞或绑定匹配的候选动作，禁止把动作提示伪装成普通 Text。
- 原始数值需要补充静态单位且存在字号层级时，优先在同一 Row 中拆成 `value_row -> [value_num, value_unit]` 并底对齐；`value_unit.content` 只能写声明单位本身。“后开始”“已使用”等说明文字必须另起一行。
- `value_unit` 只能承载主值自身的真实单位，不得承载直接后缀，也不得绑定睡眠类型、状态、名称等独立辅助字段；格式化动态字符串已经包含单位时只生成一个主值 Text，辅助字段另放在主值下一行且不得重复主值。
- 大字号数值同行的小字号 Text 只允许写真实单位，例如 `%`、`°C`、`天`、`小时`、`分钟`、`秒`、`步`、`次`、`件`、`个`、`km`、`mA`、`V`、`kcal`，或该数值字段 description 明确声明的其它单位；“电流”“电压”“当前状态”“最近安排”“后开始”等字段标签或说明文字不是单位，必须移到主值上一行/下一行。schema 已返回带单位的格式化字符串时，优先只生成一个完整绑定 Text，不再拆出单位或追加字段标签。除下方受控格式化主读数例外，只有 number/integer 字段或纯数字静态值可以使用大于 `18fp` 的字号，名称、日期、时间、状态和普通格式化字符串即使放入名为 `value_num` 的组件也不能放大。
- `value_row` 只在 Row 上写总宽度；`value_num`、`value_unit` 不写 `width:"matchParent"`，两者按内容自然宽度并写 `flexShrink:0`，避免右侧单位被挤出卡面。
- 数字与单位拆成同一 Row 内的两个 Text 时，不论数字使用 14/18/20/30/38fp 中的哪一档，Row 都必须使用 `alignItems:"bottom"` 和 `itemMargin:2`；数值与单位 Text 均不设置固定 `width`，让二者按实际内容紧邻排列。`value_suffix` 或 `value_unit` 字号 12-16，按字号差使用 `min(8, ceil((最大字号-自身字号)/4))` 的 `padding.bottom`，不设置与数字相同的固定高度，单位不能用 30 号字。同一 Row 内其它不同字号 Text 使用相同字底补偿；固定文字槽仍会拉开数值与单位，必须使用内容自适应宽度。补充说明使用相同或更弱的字号、字重和颜色，不得争夺主数值焦点。
- 合并多个独立文本字段成一行时，中间固定使用 ASCII `" | "`；数值与自身单位、日期范围、时间范围不算独立字段。
- 受控格式化主读数包括带单位的温度、时长、百分比、电量和其它明确测量值（如电流、电压、功率、频率、速度、距离、容量、湿度、压力、海拔或重量）；只有字段 description 明确表达测量语义（“电量/剩余电量”也属于测量语义）、首帧样例可解析为“数字 + 合法单位”、文本单行压力预算通过，且该值位于单业务全宽主内容或 2x4 大分区时，才可使用 20/24fp。2x4 大分区优先使用 20fp；只有分配至少 `34vp` 行高且压力字符串在剩余宽度内完整可读时才使用 24fp。2x2 多指标卡最多突出一个格式化主读数，其余测量值使用 12/14/18fp 辅助行；schema 只有 `durationText:"25分钟"`、`voltageText:"4 V"` 或 `currentText:"-151 mA"` 这类带单位字符串时，不拆出单位，不在大字号值后追加“时长”“电压”“电流”等标签。
- 动态长名称、会议名、设备名和“可点击入口/对象名称”类内容（音乐入口、设置项、蓝牙设备名、联系人）不用 30fp 大字；改短静态主文案、放小字，默认 `fontSize:16`，内容少且空间充足时最大 `18fp` 并让 Text 占整行。
- 8.3 节小内容蒙版严格使用左文字、右 visual 和对应固定文字列宽；其他图标或环与文字并排的布局中，文字组至少留 `76vp` 宽。主读数最多 4 个中文或 6 个半角字符（`29°C`、`82`、`4.5GB`、`25分`），放不下时省略可选 visual 或降到批准字号，不截断主读数。
- `W-split-panels` 的 `116vp` 天气内容区同时展示温度范围、降雨概率和空气质量时，每项各占一个 `12fp` 单行 Text，使用短标签，不加图标、不把两项挤进同一行。

<!-- /prompt:value-unit -->

<!-- prompt:action-combination -->
## 11.2 按钮

- 卡级 CTA 优先使用高级组件 `ActionUnit`（见 5.14）；基础 `Button`/图文 Row 用于 2x4 或 ActionUnit 不适用时：默认高 `36vp`、圆角 `18vp`、文字 `14fp/400-500`，左右内边距至少 `8vp`，底色与文字色按第十二节按钮两模式成对显式声明。
- 普通图文按钮使用 `Row + Image + Text + onClick`，高度默认 `36vp`、圆角 `18vp`、左右 padding 至少 `8vp`、`itemMargin:8`、内部内容居中。`W-content-side-slots`/`W-content-side-slots` 的 `132×57vp` 固定动作槽是明确例外，执行“文字在左、Image 在右”的结构。
- Button 和图文按钮的文案必须先做语义压缩：只保留动作和必要对象，优先 2 至 4 个汉字。状态说明、条件、原因和结果提示放在按钮外；“点击、立即、一键、请、去、一下、这里”等不改变动作目标的词默认删除。
- Text 只承载业务数据和说明，不得代替 CTA；禁止在 `bottom_area`、`hint_text`、内容列或其他普通 Text 中输出“点击查看……”、“点击导航……”、“打开……”等动作文案。需要显示的显式动作必须改用带实际 `onClick` 的合法按钮；隐式点击则直接省略该文字。
- 图文按钮的最低宽度必须覆盖 `左右 padding + Image.width + itemMargin + 标签压力宽度 × 1.2`。采用默认 `20vp` 图标、`8vp` 间距、`14fp` 文字时，通常不小于 `80vp`；不得生成父 Row 比内部 Image、Text 和间距总和还窄的动作栏。
- `2x4` 单个动作必须进入所属父内容区：`W-split-panels` 使用 `116×36vp` 胶囊槽，`W-content-side-slots` 内容区使用 `132×36vp` 胶囊槽；固定槽列中的动作使用整个 `132×57vp` 槽作为点击边界。禁止生成横跨 276vp 安全区的卡级按钮。
- 图文按钮的 `onClick` 只写在外层 Row，内部 Image/Text 不再绑定事件，也不在 Row 中嵌套 Button。只要用户明确要求图文按钮且存在语义准确的候选图标，就必须保留图标并采用该 Row 组合；只有没有合法候选图标时才退化为纯文字 Button。
- 2x2 独立图标动作只用于 `S-title-anchor`：40×40vp 操作槽内居中放置 36×36vp 点击 Row，中心 Image 固定 20×20vp，并提供静态 accessibility.label。2x4 禁止 CircleButton 式独立圆形动作；没有精确图标时不生成。
- 动作区应在内容之后并贴近底部。按钮必须按第十二节固定配色与直接背景清晰区分；唯一主 CTA 只能通过尺寸、位置和留白增强层级，不得提高背板不透明度、改用实心内容色或白色前景。
- 同一动作不同时绑定 root 和按钮。

<!-- /prompt:action-combination -->

<!-- prompt:progress-combination -->
## 11.3 Progress 与环

- Progress 只表达占比、使用率、完成度、电量等由 TaskSpec 字段描述明确声明、且具有可靠 `value/total` 关系的比例语义；字段仅为 number/integer 不构成进度语义。主值是时长、日期、时间、倒计时、状态、名称、温度、容量文本或其它普通数值时禁止生成 Progress。只有明确百分比或明确 `0-100` 范围才能写 `total:100`；其它 `total` 必须来自 TaskSpec 声明的固定范围或真实绑定字段，并满足 `total > 0` 且 `0 <= value <= total`，禁止根据常识、示例或视觉需要编造。
- 每个 Progress 都必须显式写 `type`，只使用两种标准形态：横向进度 `type:"linear"`，环形进度 `type:"ring"`。禁止使用 `design:"linear-bar"`、`design:"ring"` 或其它形态别名，禁止省略 `type`，禁止同时写 `type` 和 `design`。
- 横向进度固定写法：`Progress type:"linear"`，2x2 宽 126、高 8、圆角 4，写 `value`、`total`、`color`、`backgroundColor`；颜色基准跟随本卡内容色，轨道使用内容色 20%，不得使用其它色值或黑灰色。不要生成 4vp 细进度条。
- 横向进度优先放在主读数下方，不放进按钮、不放进标题区、不与底部动作重叠。
- 图标与进度条的组合仅允许环形图：图标叠放在进度上使用 `Stack -> [Progress type:"ring", Image]`（ring_icon_stack）；`type:"linear"` 的 Progress 上不得叠放任何图标或文字。
- 横向进度与数值读数、图标同卡组合须先满足 2.5 节位置限制，不能据此为 2x2 单业务内容区添加独立图标；合法组合只允许纵向排列：进度条与读数/图标必须是 Column 中上下相邻的兄弟节点，不得放进同一个 Stack 叠放。包含 Progress 的 Stack 只允许环形组合，子节点固定为 `[Progress type:"ring", center_content]`；`center_content` 只能是一个 Image、一个 Text，或一个仅含“数字 + 短单位”的 Row。任何 Stack 不得同时容纳横向进度与其他元素。
- 环形进度固定写法：`Progress type:"ring"`，2x2 单业务的 Stack 与 Progress 只能是 `48×48vp`，`S-dual-info` 双业务每区的 Stack 与 Progress 只能是 `44×44vp`，两者的 `strokeWidth` 都只能是 `6vp`，禁止使用其它数值。环内语义 Image 在 `2x2` 固定 `20×20vp`，`2x4` 保持原骨架尺寸；环内需要百分比读数时使用 Text，或使用只含数值 Text 与单位 Text 的紧凑 Row；小数、长字符串和多行说明必须放在环外。
- 融球上的环线、中心主图标、环内主读数和单位使用白色 100%，轨道沿用 `#33FFFFFF`；次要信息用白色 80%。
- Progress.value 可以绑定 TaskSpec 中的 number/integer 字段并随运行时更新；不能可靠得到数值总量时不输出误导性百分比或进度图，也不编造假进度。

<!-- /prompt:progress-combination -->
