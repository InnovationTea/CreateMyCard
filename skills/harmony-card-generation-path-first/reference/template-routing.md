# 合规模板路由

本文在从零生成完成内容分级后，出现模板候选时读取；读取本文就是为了判断布局是否能由模板固定槽位和区域预算承载。模板用于降低布局自由度，不替代 `core-rules.md`、协议规则、绑定规则、颜色规则或最终校验。

## 内部闭环

- 生成时只读取本 skill 内部文件：`assets/templates/index.json`、选中模板的 `manifest.json`、`template.genui.jsonl`、`cardspec.json`，以及本 skill 的 reference 文档。
- 不要读取 skill 包外的历史样例、截图、布局目录或其它本地文件作为生成依据。旧样例已经折叠为 `index.json.sourceAuditSummary` 和各模板 `manifest.sourceObservation`。
- 维护本 skill 时也以本包内 `assets/templates/`、`reference/` 和已声明素材为准；新增模板规则必须先折叠为本包内 manifest、模板骨架、合规素材索引和参考规则后再被使用。
- 不要从外部链接、网络 URL、未声明本地路径或相似路径补素材。素材只允许来自本 skill 的 `reference/design/asset-library.md` 或用户在当前任务中明确提供的资源。
- 历史样例里的旧尺寸、多段组件更新、base64 图片、未声明 SVG、emoji 和旧动作写法不得复制。正式模板统一按本 skill 校验口径输出：`2x2 = 140 x 140`，`2x4 = 300 x 140`。

## 使用前判定

先用 `assets/templates/index.json` 查是否存在同尺寸候选，再判断槽位；`useWhen` 只作候选提示，不是业务关键词白名单。只有同时满足以下条件才使用模板：

- 用户没有指定必须自定义的复杂布局。
- 卡片能收敛到一个服务对象或主问题，并能映射到同一个模板的角色槽位；不要同时承载两个服务对象、两个主任务或两个动作目标。
- 候选模板尺寸与用户指定尺寸或 `best-fit` 尺寸一致；索引中没有同尺寸模板时，直接回到非模板流程。
- 用户字段能映射到模板 manifest 的槽位，并且受保护文本按 `layout-system.md` 估算能完整显示。
- 所需素材存在于 `reference/design/asset-library.md`，或模板在删除素材后仍成立。
- 动作能力能从用户需求、宿主能力或 `reference/capability/event-capability/click-event.md` 推导；否则删除事件，只保留非误导的支撑区域。

任一条件不满足，回到非模板流程；跳过模板前必须形成内部否决理由，例如用户要求固定复杂布局、无同尺寸模板、两个主任务、两个动作、槽位文本超预算、素材/事件能力不成立，或删除槽位后模板结构已不成立。

## 一致性决策

- 角色槽位可收敛的短需求优先尝试模板；非标准需求、用户指定固定布局，或索引中无同尺寸模板的需求走非模板流程。
- `useWhen`、`avoidWhen` 和 pattern 名只帮助缩小候选；真正是否使用模板，以槽位结构、尺寸预算、动作数量、素材需求、受保护文本长度和 manifest 约束为准。
- 同时命中多个模板时，按 `assets/templates/index.json` 中出现顺序选择第一个满足全部条件的模板，不重新排序候选。
- 模板生成默认采用 manifest 槽位模式：按 `object`、`primary`、`support`、`metric/tile/status/badge`、`action`、`asset` 分配内容；未被用户要求、无法提供独立判断或会重复 `primary` 的可选槽位直接删除。
- 保留模板的尺寸、root shell、核心层级、ID 命名和 `colorPolicy` 角色约束；删除槽位时同步删除组件引用、DataModel 字段和 CardSpec 冗余。
- 不使用表达式填充模板。需要条件、计算或长字符串时，优先在 `updateDataModel` 中预计算展示字段，再用 `path` 或 `formatString` 绑定。

## 读取顺序

1. 读取 `assets/templates/index.json`，根据任务特征选择一个候选。
2. 只读取该候选的 `manifest.json`，确认槽位、锁定结构、删除规则、预算和 `colorPolicy`。
3. 读取该候选的 `template.genui.jsonl` 作为骨架。
4. 按当前需求重填 DataModel、文案、素材、颜色和可证明合法的事件；颜色必须沿用 manifest `colorPolicy` 的 token 角色或按 `color-token-system.md` 做同角色重映射，不要照搬模板示例文案。
5. 按 `core-rules.md` 做输出前校验；若预算失败，先删可选槽位，再回退非模板流程。

## 模板索引

模板顺序、`useWhen`、`avoidWhen`、槽位清单和文件路径只以 `assets/templates/index.json` 为准；本文不重复维护表格。选中模板后只读取该模板的 `manifest.json`、`template.genui.jsonl` 和 `cardspec.json`，并以 manifest 的 `lockedStructure`、`slots`、`colorPolicy`、`allowedEdits`、`forbiddenEdits` 和 `deleteRules` 做最终约束。

## 当前模板 Pattern 速查

这些 pattern 名只用于模板路由和 manifest 对齐，不输出给用户：

- `meter-side-action`：一个进度环/仪表、1-2 条短事实、底部动作或支撑胶囊。
- `multi-meter-action`：一个主容量/健康指标 + 2-3 个同类小状态，适合设备清理或多状态概览。
- `bar-dual-metric-action`：一个横向阈值/进度条 + 两个小指标 + 一个动作或支撑提示。
- `countdown-panel`：一个 `32/40fp` 倒计时或数字主值 + 一个支撑背板。
- `meeting-action-badge`：会议/日程标题、时间/地点短信息、一个徽标值和一个动作。
- `product-stat-tiles`：产品图片或设备图 + 两个状态 tile；需要真实产品素材。
- `quadrant-ambient-action`：场景色 root 中放主值、状态图标、一个支撑块和一个图标动作。
- `spotlight-context-action`：主数值/主图标 + 一个上下文背板 + 底部动作。
- `stacked-schedule-action`：日程对象、事件标题、时间、提醒行和底部动作纵向堆叠。

## 模板图片内容折叠结论

维护模板规则时，历史模板图已经折叠为本包内 manifest 和当前速查，不要求生成时读取旧图片。容量判断按角色槽位而不是普通事实条数：

- `support.*` 是一个支撑组，可以由 label/value、短说明或两行同组文本构成。
- `metric.*`、`tile.*`、`status.*` 是结构化并列小事实；只要互不重复且 manifest 声明了槽位，2 个 metric、2 个 tile 或 2-3 个小状态环可以保留。
- `badge.*` 是短徽标、计数或日期提示；不得重复时间、主数值或动作文案。
- `action` 可以是文字 pill，也可以是 manifest 声明的图标动作目标。图标动作若可点击，视觉尺寸不小于 `24vp`，且必须由相邻对象、图标语义或当前场景明确说明用途；语义不清时删除点击或改用带文字动作槽位。

## 被移除的重复模板

- `meter-plus-fact`：与“进度环/仪表 + 短事实 + 底部动作”模板重叠，且缺少语义图标和动作图标槽位。
- `top-hero-pill`：抽象度过高，已拆成主数值上下文、场景色象限、倒计时面板和日程堆叠四类模板。
- `paper-panel`：作为抽象信息面板有用，但在当前样例集中和 `meeting-action-badge` 重叠，指导生成时容易回到上/中/下三段且缺少具体场景槽位的布局。

## 槽位映射

先把用户输入映射为内部槽位，再写 DSL：

- `object`：卡片对象，例如会议、设备、城市、亲人、应用。
- `primary.value` / `primary.title` / `primary.time`：主显示组，只回答同一个主问题；倒计时双数字、睡眠时长拆行等可由多个组件显示同一主值。
- `primary.caption` / `primary.meta`：主显示组的短说明，不重复主值。
- `support.*`：支撑组，只保留能提供新判断的信息；同一组内可以有短标签和值。
- `metric.*` / `tile.*` / `status.*`：并列小事实，不计入 `support.*` 条数，但每个只承载一个独立判断，并受 manifest 数量和字符上限限制。
- `badge.*`：短徽标或计数，不作为第二主显示组；如果与 `primary` 或 `support` 重复则删除。
- `action.label` / `asset.actionIcon`：底部动作、支撑提示或图标动作目标；文字动作优先 2-6 个中文字，图标动作必须有可证明语义。只有事件能力完整时才视为主动作。
- `asset.*`：只从 `asset-library.md` 选择；没有匹配素材时删除 Image 并重新分配宽度。

## 模板专项规则

模板特有规则只维护在对应 manifest 中。比如 `2x2-bar-dual-metric-action` 的阈值条处理读取 manifest 的 `adaptiveProgressGuidance`，不要在本文复制或改写。

## 回退规则

- 槽位超过宽度：先缩短标签，删可选角色槽位，再降低到同阶梯字号；仍失败则放弃模板。
- 动作能力不明：删除 `onClick`，必要时把动作区改成非动作支撑区域；不要虚构 `call` 或宿主参数。
- 素材不在素材库：删除图片并重分配宽度；不要用网络图、未声明 SVG、emoji 或相似路径替代。
- 颜色无法说明来源：改用 `color-token-system.md` 中的 token 或删除装饰色。
- 删除两个以上主区域后仍需大改：停止使用模板，走非模板流程。
