# 生成流程

新卡片生成、尺寸偏好冲突、内容取舍不明确，或需要从自然语言需求推导卡片概念时读取本文。本文只做 UX 与信息架构规划，不替代 `core-rules.md` 的协议门禁、`layout-system.md` 的尺寸预算或 `color-token-system.md` 的色值校验。

## 闭环边界

- 本 skill 运行时只依赖 `SKILL.md`、`reference/`、`assets/templates/` 和用户当前输入；不要读取 skill 包外 UX 文档、旧样例、截图或网页作为生成依据。
- 本文吸收了生成顺序、尺寸适配、场景向量、布局原型和色彩前置决策；落地 DSL 时仍以本 skill 内部协议、模板、事件、CardSpec 和校验文件为准。
- 所有流程对象只在内部推理使用，不输出给用户。模式 1/2 的最终回答仍只给 `genui` 与 `cardspec` 两个代码块。

## 术语最小定义

这些术语只用于内部推理。任一参考文件单独读取时，也按本节含义理解。

- `evidence`：用户明确给出的事实、字段、动作、尺寸或素材。
- `inferred`：为补足卡片而做的保守默认；不能改变主对象、主动作或用户给出的事实。
- `intent vector`：意图字段组，记录服务对象、主对象、主问题、动作必要性、时间焦点、尺寸偏好和可用内容。
- `scene vector`：场景字段组，记录目的、表达调性、内容密度、主信息类型、层级数、时间性、交互方式和内容数量。
- `mustKeep`：没有它卡片无法回答需求；必须完整显示。
- `shouldKeep`：空间允许才保留；不得挤占 `mustKeep`、受保护文本或动作热区。
- `dropOrMoveToDetail`：不进卡片；只在详情页、宿主页面或说明中承载。
- `best-fit`：按内容数量、受保护文本、热区、媒体和并列关系推导出的最小可承载尺寸。

`compositionPattern` 是构图枚举，每张卡只选 1 个：

- `plain-card`：中性工具卡；主信息靠字号、位置和留白建立层级。
- `single-panel`：中性 root + 1 个内容背板；用于把同一组事实归拢。
- `ambient-root`：root 承载天气、睡眠、音乐或环境场景色；文本仍在安全区内。
- `dark-focus`：暗色表面本身有场景语义，例如夜间、演出、睡眠或专注。
- `meter-dashboard`：单一仪表、进度或比例是主焦点；不是多仪表盘。
- `split-action`：主内容区和动作/状态区横向分区；动作能力必须已声明。
- `media-card`：真实图片、票券、产品或媒体是主对象；文本放遮罩或独立背板。

`surfaceStrategy` 是表面策略枚举，每张卡最多选 1 个主策略：

- `plain`：中性 root，无额外场景表面。
- `tinted-surface`：中性 root + 1 个同族低强度支撑背板。
- `colored-root`：root 使用场景色或渐变，前景用 on-color 或中性前景。
- `split-surface`：主区和支撑区使用两个明确表面，但仍共享一个主色族。
- `image-derived`：真实图片主导，文本区域使用遮罩或中性背板。
- `dark-stage`：暗色 root 或重点面表达夜间、睡眠、舞台或专注。
- `soft-material`：`comp_background_secondary/tertiary` 材质层或 2-stop 合规线性渐变。

## 总流程

1. 拆事实：区分用户明确给出的 `evidence` 和为补足卡片所作的 `inferred`。如果低置信缺口会改变主对象或主动作，先问一个简短问题；否则用保守默认值继续。
2. 建 `intent vector`：明确服务对象、用户 1-2 秒内要知道/完成什么、动作是否必需、时间焦点、尺寸偏好和可用内容。
3. 做内容分级：先列 `mustKeep`、`shouldKeep`、`dropOrMoveToDetail`，再写布局。不要先写组件结构再把内容硬塞进槽位。
4. 定尺寸与适配方向：未指定先算 `best-fit`；用户指定 `2x2` 或 `2x4` 时优先尊重，并通过删减或扩展保留意图。
5. 建 `scene vector`：用场景目的、密度、主信息类型、层级、时间性和交互方式推导布局原型与配色范围。
6. 选布局原型和比例带：用固定比例、区域宽高和角色槽位承载主角色组、并列事实组、动作区或媒体区。
7. 选 palette 方向：用具体物理/文化锚点选择一个主色族、表面策略、状态色策略和按钮材质默认值。
8. 写 DSL 前进入专项文件：布局预算读 `design/layout-system.md`，颜色读 `design/color-token-system.md`，事件读 event capability，CardSpec 读 `capability/cardspec.md`。
9. 输出前回到 `core-rules.md` 做 P0/L0/L1/L2 与人工阻断门禁。

## Intent Vector

内部记录这些字段：

```txt
intent = {
  service,
  primaryObject,
  primaryNeed,
  primaryQuestion,
  actionImportance: required | optional | absent,
  timeFocus: now | today | date | countdown | schedule | none,
  requestedSize: none | 2x2 | 2x4 | both | unsupported,
  availableContent: measured fields/items/actions/media
}
```

字段说明：

- `service`：卡片所属服务、应用或能力域，例如天气、会议、设备清理、睡眠监督；不要写成具体数值或动作。
- `primaryObject`：卡片当前展示的对象，例如深圳、项目阶段性汇报、Free Clip 2、手机内存；没有明确对象时用服务对象，不另造对象。
- `primaryNeed`：用户打开卡片想知道或完成的目标，例如看状态、看下一项、看剩余量、入会、拨打、开始清理。
- `primaryQuestion`：卡片 1-2 秒内必须回答的问题；必须能写成一句话，并由 `primary` 主显示组直接回答。
- `actionImportance`：`required` 表示没有动作就不能完成用户目标；`optional` 表示动作只是入口或补充；`absent` 表示不展示显式动作。
- `timeFocus`：只记录主信息的时间焦点；`now` 是当前状态，`today` 是今天摘要，`date` 是具体日期，`countdown` 是距离某时点，`schedule` 是日程/下一项，`none` 是无时间焦点。
- `requestedSize`：只记录用户或上游明确指定的尺寸；未指定为 `none`，同时要两套为 `both`，非 `2x2/2x4` 为 `unsupported`。
- `availableContent`：当前可用内容清单和数量，按 `fields/items/actions/media` 计数；只记录已有证据或保守默认，不把推测内容当成已给字段。

规则：

- `primaryQuestion` 必须能用一句话回答，例如“下一场会议何时开始”“今天温度和天气如何”“这个包裹当前到哪一步”。
- 动作不能单独成为卡片目的；卡片必须先呈现服务状态或内容，再提供动作。
- 长描述、规则解释、第三层元信息、营销入口、长列表和表格默认移出卡片。

## 内容分级

`mustKeep`：没有它卡片就无法回答需求。

- 主对象或主标签，例如城市、会议、设备、联系人、票券、包裹。
- 主状态/数值/时间，例如温度、倒计时、下一场时间、进度阶段、取件码。
- 主动作，仅当动作是用户目标的一部分，例如拨打、入会、开始、确认。
- 媒体主对象，仅当卡片以照片、票券、内容预览为核心。

`shouldKeep`：空间允许才保留。

- 一个短地点、短状态、趋势、更新时间、辅助图标或一条支撑信息。
- 非模板 `2x2` 默认最多保留一个支撑组；非模板 `2x4` 最多保留两个支撑组。选用模板时以 manifest 的 `slots` 为上限：`support.*` 归入支撑组，`metric.*`、`tile.*`、`status.*`、`badge.*` 是结构化并列槽位，只有能提供独立判断且不重复 `primary` 时才保留。

`dropOrMoveToDetail`：不要塞进卡片。

- 重复服务名、装饰标签、长说明、完整规则、额外动作、第三层 metadata、密集列表、表格、广告和运营活动。

## 尺寸适配

先判断 `best-fit`：

- `2x2`：一个服务对象或主问题；非模板默认是 1 个主视觉/主数值、1 个支撑组和可选 1 个动作。模板按选中 manifest 的 `slots` / `sections` 上限执行，例如两个小指标、两个状态 tile、2-3 个小状态环、一个短徽标或一个图标动作都可以成立，但不能新增第二个服务对象或第二个主任务。
- `2x4`：一个主信息组需要一个支撑组；短时间线最多 3 项；周/小矩阵/媒体预览/显式动作需要横向空间；最多 2 个热区，且每个热区有明确 `onClick`、标签和不小于 `24vp` 的点击视觉尺寸。
- 超过 `2x4`：摘要、截断、显示 `+N` 或进入详情，不生成 `4x4`、长列表或密集仪表盘。

用户指定尺寸时：

- `native`：requested 与 best-fit 相同，正常生成。
- `contract`：best-fit 为 `2x4` 但用户要 `2x2`，保留一个主对象和必要动作，删掉 `shouldKeep` 支撑和第二热区。
- `expand`：best-fit 为 `2x2` 但用户要 `2x4`，增加相关支撑信息、可读宽度或动作标签/热区，不拉伸原布局、不加无关模块。
- `both`：分别生成两套内容计划，不能裁剪或拉伸同一个布局。
- `unsupported`：不输出未支持尺寸，改给最接近的 `2x2` 或 `2x4`。

## Scene Vector

内部记录这些字段：

```txt
scene = {
  purpose: status | metric | timeline | matrix | calendar | media | action | text,
  register: functional | editorial | playful | ambient,
  density: hero | sparse | normal | dense,
  keyInfo: number | text | matrix | timeline | media | status | action,
  hierarchy: 1 | 2 | 3,
  temporality: none | now | today | week | countdown | timeOfDay | seasonal | event | night,
  interaction: wholeCard | oneAction | twoZones,
  contentAmount: measured counts/lengths
}
```

字段说明：

- `purpose`：卡片主要用途；`status` 看状态，`metric` 看数值/额度，`timeline` 看进程或下一项，`matrix/calendar` 看小矩阵/日历，`media` 看图片或内容预览，`action` 强动作辅助，`text` 短文本提示。
- `register`：视觉表达方式；只影响表面、颜色和氛围选择，不改变内容取舍。
- `density`：由入选内容数量决定；`hero` 只有一个强主值，`sparse` 内容少但仍需填满主区域，`normal` 为常规信息卡，`dense` 为字段多但仍不能突破字号和区域预算。
- `keyInfo`：主显示组的信息类型；用于决定数字、文本、矩阵、时间线、媒体、状态或动作哪一种最先被看见。
- `hierarchy`：可见信息层级数，最多 3；超过 3 时先删 `shouldKeep` 或回退详情。
- `temporality`：场景时间性；只在主信息确实与当前、今天、本周、倒计时、日夜、季节或事件相关时填写对应值。
- `interaction`：交互结构；`wholeCard` 整卡入口，`oneAction` 一个显式动作，`twoZones` 两个可点击热区且每个都有明确事件能力。
- `contentAmount`：入选后的数量统计，例如文本行数、并列指标数、动作数、媒体数和受保护文本长度。

取值指导：

- `density` 来自真实内容数量，不靠视觉猜测。`dense` 不等于可以降低字号到阶梯之外。
- `hierarchy` 最多 3 层；如果每层都很重要，说明内容过载。
- `interaction` 默认 `wholeCard`；显式动作只在动作有已声明事件能力、标签和热区时保留。
- `register` 只影响是否使用场景色、渐变、暗色表面或中性表面，不覆盖安全区、字号、协议和颜色来源。

## 布局原型

- `number/status`：主数值或状态为主视觉，单位/原因/时间为支撑。`2x4` 可左侧放主视觉、右侧放支撑/动作。
- `timeline`：`2x2` 只展示当前/下一项；`2x4` 最多 3 项，当前/下一项使用该组最大字号、最靠前位置或唯一状态色。
- `matrix/calendar`：只做小矩阵、周视图或单日；月历、年历和复杂表格改为摘要或详情入口。
- `media`：真实媒体或内容预览优先；文字放安全遮罩或中性背板，不做装饰拼贴。
- `action`：状态先行，动作次之；不要生成纯快捷方式或按钮网格。
- `text`：标题加一句短支撑，不写段落。

固定比例带只用：`62/38`、`55/45`、`50/50`、`30/70`、`15/85`。

- 数字/状态常用 `55/45` 或 `50/50`。
- 时间线常用 `30/70`。
- 媒体常用 `62/38`。
- 矩阵常用 `15/85`。
- `2x2` 把比例理解为主视觉/主数值占比或纵向分区，不要把小方卡切碎。

## 进度可视化选择

先问主内容是否回答“距离目标/总量/范围还有多少”或“处在有序阶段的哪一步”。

- 没有参考点：用普通文本/数字，不发明百分比或环形图。
- 有序阶段：用分段/step bar，并配当前阶段标签；不要用连续百分比条替代阶段语义。
- 单一目标/范围：当它是唯一主焦点时可用 ring；数值默认放在 ring 旁边，不塞进小环洞。
- 多个同类比例：2-4 项可用 repeated small ring；超过约 4 项或需要精确比较时用 linear bar row。

几何和尺寸细节进入 `design/layout-system.md`；颜色和 track/fill 来源进入 `design/color-token-system.md`。

## 配色前置决策

写颜色前先命名 2-4 个具体锚点，例如雨玻璃、日历纸、跑道、票纸、电池环、包裹标签、药盒、收据纸、夜间舞台。不要使用“高级、现代、清新、可信、科技感、漂亮”等抽象词当锚点。

内部选择：

- `compositionPattern`: `plain-card`、`single-panel`、`ambient-root`、`dark-focus`、`meter-dashboard`、`split-action`、`media-card`。
- `surfaceStrategy`: `plain`、`tinted-surface`、`colored-root`、`split-surface`、`image-derived`、`dark-stage`、`soft-material`。
- `sceneAccent`: 一个主色族。
- `statusColorPolicy`: `none`、`state-only` 或 `primary-action-only`。
- `actionMaterial`: 默认中性/磨砂；只有颜色本身表达确认、风险、破坏、品牌，或拨打、入会、开始、连接、清理、导航等必要动作时才用实色。

随后用 `design/color-token-system.md` 映射到合法 hex。

## 输出前计划门禁

- 是否只有一个服务对象或主问题、一个主色族？显式可点击动作是否不超过当前尺寸或模板允许上限，且没有第二个主任务？
- `mustKeep` 是否都能完整显示，`shouldKeep` 是否没有挤占主显示组？
- requested size 是否被尊重，或 unsupported size 是否被降级说明？
- `scene vector` 是否能推导出布局原型、比例带、字号层级和配色方向？
- ring/bar/图标/媒体是否由 `mustKeep`、`shouldKeep`、主动作或主媒体触发？
- 动作能力不明时，是否删除了点击并降级为支撑信息？
