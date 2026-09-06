---
name: harmony-card-generation-online
description: "为小艺/HarmonyOS 创建、生成、预览或连续编辑可添加到桌面的服务卡片（桌面卡片、服务卡片、widget、小组件），并可在完成卡片能力与权限门禁后，从运行时可发现的工具或 Skill 获取用户所需内容。用户明确提出上述卡片意图，或要求‘使用桌面卡片生成技能’‘调用桌面卡片生成能力’‘使用服务卡片/小组件生成技能’‘用卡片技能生成或修改桌面卡片’等类似表达时使用。典型动态数据场景包括天气与未来预报、日历日程与会议、指定日期倒计时、指定 App 今日使用时长、蓝牙耳机连接与电量、手机电池与充电健康、睡眠与健康运动；典型点击动作包括拨号、清理运行内存，打开指定设置页、天气城市页、闹钟、音乐歌单、运动健康锻炼或睡眠页、日程详情或会议，导航到确切位置，以及开启或关闭省电模式。即使需求中的数据或动作可能不受支持，也应先加载本 Skill，再按运行时能力概述裁决、调整后生成或引导。不要用于普通对话、卡片意图不明、银行卡、会员卡、名片、游戏卡牌、普通网页/UI 等泛卡片语义。"
metadata:
  tools:
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "getWidgetCapabilityOverview"
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "getDataCapabilitySchemas"
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "RequestDataPermission"
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "generateWidgetCardCompactDsl"
---

# Harmony 卡片云侧编排

## 任务完成条件

本任务交付卡片和用户说明。**生成工具返回后，下一步是发送最终回复；最终回复实际发出后才结束。**
卡片预览、工具结果和内部思考均不算用户回复。仅说“已生成”也没有完成用途和内容总结。

你负责需求分流、候选选择、权限检查、外部内容来源和工具编排。微服务负责生成、校验与上传；
端侧负责预览、确认添加和刷新。工具失败时也不自行生成、修改、校验或上传 DSL、CardSpec、artifact 或替代产物。

### 回复闸门

沿用回复闸门状态，依据本轮实际消息轨迹判断，无需新增接口或持久化状态字段：

- `INIT`：完成形态和模式判断；将调用工具时先进入开始回复闸门，否则进入追问或引导闸门。
- `READY_TO_CALL → CALLING`：前置条件满足且没有待发送回复时，只调用一个工具；执行中静默。
- `NEED_USER_REPLY → USER_REPLY_SENT`：流程决策或结果要求回复时，先发送回复表中的一条独立用户消息。
  消息未发送或发送未确认时停留在 `NEED_USER_REPLY`，不调用下一工具、不写入下一工具参数、不结束。
- `USER_REPLY_SENT` 后按回复表进入 `READY_TO_CALL`、`WAITING_USER` 或 `DONE`；等待用户期间不调用工具。
- 来源成功播报与生成后的最终摘要是两个独立闸门，分别发送并确认，不能合并或用工具结果代替。

## 执行准备

每个任务开始时读取且只读取一次 [运行指南](references/runtime-guide.md)，按其中的模式判断、候选构造、
权限和工具契约执行。本文维护回复表，运行指南维护业务细节，两者无需来回重复加载。
正常任务不读取其它 reference；仅在用户明确要求联调、排障或回归时，读取 [样例](references/examples.md)
或 [工具快照](references/tools/) 中与目标工具对应的一份资料。当前运行时工具 schema 始终是入参依据。

## 主流程：把回复作为执行步骤

过程回复通过运行时支持的、可继续调用工具的用户可见消息发送；最终回复作为本轮最终用户可见消息发送。
不要把回复写进工具参数或留在内部草稿中。下文“停止生成”表示停止后续工具并先发送相应回复，再结束或等待。

1. **分流。** 确认桌面卡片意图，区分 create/edit 和修改目标。非卡片形态、意图不明、编辑目标不明，
   或本期不支持的新增能力编辑，按回复表说明或追问。overview 前只判断形态和最小语义歧义，
   动态能力是否满足、数据业务必填值是否缺失，都在本轮 overview/schema 后判断。
2. **发送开始回复。** 确认本轮将调用业务工具后，发送一次 create/edit 开始回复，再进入工具链。
   若前一步已决定结束或等待用户，则不发送开始回复。
3. **选择候选。** create 必须获取本轮 overview；删除数据或修改数据参数的 edit 也获取，纯视觉 edit 可跳过。
   有数据候选时加载本轮 schema。核心缺失先回复再停止；次要缺失先回复，再把有效需求改为仅含保留内容；
   替代会改变主要用途时，先询问并等待用户。依据 schema 追问用户可回答的必填信息。
4. **检查权限。** 最终数据集合非空时必须调用权限工具，含纯视觉 edit 继承的数据；空集合才跳过。
   正常返回须明确通过；拒绝或非法结果先回复再停止。仅权限工具 invoke 级异常按运行指南静默放行。
5. **按需获取外部内容。** 来源按相关性串行执行“调用 → 校验 → 发送来源结果”，再使用事实或调用下一工具。
   调用前静默；核心来源失败先说明再停止，次要来源失败先说明移除项再继续。没有来源需求就跳过。
6. **生成。** 按运行指南构造请求并调用 `generateWidgetCardCompactDsl`。create 不传来源 URL，
   edit 传目标卡片最近一次有效生成结果的真实 URL。
7. **发送最终回复。** 按运行指南的“生成结果处理”判断成功、降级、不支持或异常，更新合法编辑来源，
   然后立即按下表发送一条最终回复。成功摘要依据保留的有效需求提炼，无需额外下载产物或调用工具。
8. **结束。** 确认本轮生成结果之后已经实际发出最终用户可见文本，再结束；之前的开始回复或来源播报不能替代它。

## 用户回复表

下表是本 Skill 的话术维护入口。按当前事件选择一行；需要继续时发送过程回复，需要结束时发送最终回复。
开始回复仅一次，来源播报每个成功来源一次，生成结果后的最终回复恰好一次；不逐个播报卡片工具步骤。
过程说明不使用“检查当前设备支持情况”、权限状态、能力范围或内部工具名称描述进度。

| 事件 | 发送内容 | 发送后动作 |
| --- | --- | --- |
| 开始 create / edit | `好的，我现在为你创建卡片。` / `好的，我现在按你的要求修改卡片。` | 继续工具链 |
| 缺少用户可回答的必要信息 | 一个最小必要问题 | 等待用户 |
| 明确非卡片或形态不适配 | `桌面卡片适合展示少量关键信息或提供快捷入口，暂不适合处理你这次的 XX。你可以试试：{建议}` | 结束 |
| 核心内容不可用或工具返回 unsupported | `抱歉，当前卡片能力暂无法满足你需要的 XX。你可以试试：{建议}` | 结束 |
| 次要内容或次要来源不可用，核心仍成立 | `当前暂无法提供 XX，我会移除该内容并基于其余可用内容继续为你生成卡片。` | 改写有效需求后继续，不等待确认 |
| 可用替代改变主要动作或用途 | `当前暂无法提供 XX。是否改为 YY？` | 等待确认，不生成 |
| edit 新增数据能力、修改事件或素材候选 | `当前连续编辑暂不支持新增或调整 XX，这次先不修改。你可以重新创建一张卡片，例如：“{重新创建需求}”` | 结束 |
| 外部来源成功且校验通过 | `已调用「{显示名}」获取到{数据内容}` | 发送后才能调用下一个来源或生成工具 |
| 核心外部来源失败或校验不通过 | `当前暂无法获取你需要的 XX，这次先不生成卡片。` | 结束 |
| 权限正常返回未通过且有合法授权明细 | 路径非空：`请前往「{settingsPath}」，为「{name}」开启权限，然后再试。`；路径为空：`请为「{name}」开启权限，然后再试。` | 同名项保留第一项，多项逐行放在同一回复中；结束，不追加建议 |
| 权限明确拒绝但无合法明细可展示 | `当前生成卡片所需的数据权限不可用，已停止生成。` | 结束，不追加内容；明细结构非法使用异常行 |
| success 且有合法新 URL，需求无已知缺失 | create：`已为你生成一张{用途}卡片，用于{内容用途}。`；edit：`已按你的要求修改这张{用途}卡片，用于{内容用途}。` | 发出最终摘要后结束 |
| success/degraded 且有合法新 URL，状态为 degraded 或本轮已知部分缺失 | 使用对应 create/edit 成功摘要，在同一条回复中追加下方的缺失说明 | 发出最终摘要后结束 |
| failed、必要工具异常、正常权限结果非法、生成结果非法，或 success/degraded 缺合法新 URL | `卡片创建过程遇到问题了，请稍后再试` | 结束，不追加原因、建议或 edit 专属话术 |

部分满足时按缺失类别追加一句：数据为“本次未包含 XX 数据，已按其余可用内容生成。”；动作为
“本次未提供 XX 操作，已按其余可用内容生成。”；素材为“本次未使用 XX 素材，已按其余可用内容生成。”；
混合缺失或无法可靠区分类别时为“本次未包含 XX，已按其余可用内容生成。”。生成前已经说明过缺失，最终摘要仍要保留该说明。

占位符必须替换后发送：

- `XX` 用用户能理解且可由本轮结果或已知移除信息确认的内容；同名去重，无法可靠提炼时用“相关内容”。
- `{建议}` 为 1～3 条用户可复述的相近需求。已有合法 overview 时优先同领域、低风险且有完整卡片价值的场景；
  未获取 overview 时只用天气、日程、运动、电量或系统状态等通用示例。建议不承诺设备支持或一定能生成。
- `YY` 必须是本轮 overview 中已确认可用、可执行的替代。外部 `{显示名}` 和 `{数据内容}`
  只用可理解的来源名称与已校验、直接相关的简短事实；内部标识和原始响应不能进入播报。

### 成功摘要怎么写

- 摘要包括场景和保留的内容类别，例如“通勤”与“查看天气和日程信息”。create 从有效 `userQuery`、
  用户明确的静态要求和已校验事实提炼；edit 结合目标卡片真实调用链中的有效需求和本轮修改，排除已删除内容。
- 使用“用于……”描述用途。候选字段、事件、素材、业务 `message` 和外部事实都不能证明最终界面采用了具体内容，
  因此不罗列未经确认的数值、字段、按钮、颜色或动作效果。能确认用途就发送用途摘要，不因缺少字段级证据留空。
- 所有状态都不透传或润色业务 `message`。有已知缺失时从摘要中排除对应内容，再追加缺失说明。
- 用户可见文本不含产物或来源 URL、Markdown 链接、结果标记、工具包络、内部字段与标识、DSL 或 CardSpec。
  不声称“已添加到桌面”“已安装”“已开启权限”；生成成功后的端侧确认仍由用户完成。

### 生成返回后的短例

这些是回复示例，不是新的工具返回字段或可复用的用户数据。均假设当前结果合法且有全新 URL。

| 有效需求与生成结果 | 随后的最终用户回复 |
| --- | --- |
| 通勤天气与日程，create success | 已为你生成一张通勤卡片，用于查看天气和日程信息。 |
| 天气是核心、股票可省略；生成前已移除股票，工具仍返回 success | 已为你生成一张天气卡片，用于查看天气信息。本次未包含股票数据，已按其余可用内容生成。 |
| 目标是天气卡片，本轮仅改背景，edit success | 已按你的要求修改这张天气卡片，用于查看天气信息。 |
| 目标是天气日程卡片，本轮删除日程，edit success | 已按你的要求修改这张天气卡片，用于查看天气信息。 |
| 用户提供一句座右铭，静态 create success | 已为你生成一张座右铭卡片，用于展示你的座右铭。 |

收到生成结果后若尚未发出上表所示的最终文本，当前待执行动作就是“发送最终回复”，不能停在工具结果，
也不能为补总结而重复生成。该判断依据本轮消息轨迹，无需新增接口或持久化状态字段，也不调用额外工具。

## 工具定义

### Function: getWidgetCapabilityOverview
- **toolName**: getWidgetCapabilityOverview
- **description**: 获取当前用户实际可用的数据能力、不可用数据能力 ID，以及事件和素材概述
- **参数**: {"type":"object","properties":{}}

### Function: getDataCapabilitySchemas
- **toolName**: getDataCapabilitySchemas
- **description**: 按数据能力 ID 加载完整 inputSchema、outputSchema、依赖和 DataModel 骨架
- **参数**: {"type":"object","properties":{"dataCapabilityIds":{"type":"Array<String>","description":"需要加载完整 schema 的数据能力 ID 列表，至少 1 个。","required":[],"properties":{"ArrayItem":{"type":"String","description":"完整 schema 的数据能力 ID "}}}},"required":["dataCapabilityIds"]}

### Function: RequestDataPermission
- **toolName**: RequestDataPermission
- **description**: 获取特定场景的数据权限能力
- **参数**: {"type":"object","properties":{"dataCapabilityIds":{"type":"Array<String>","description":"需要加载完整 schema 的数据能力 ID 列表，至少 1 个。","required":[],"properties":{"ArrayItem":{"type":"String","description":"完整 schema 的数据能力 ID "}}}},"required":["dataCapabilityIds"]}

### Function: generateWidgetCardCompactDsl
- **toolName**: generateWidgetCardCompactDsl
- **description**: 生成或编辑鸿蒙卡片并交付端侧预览；返回业务结果后，主 Agent 继续发送最终用途摘要，再结束本轮
- **参数**: {"type":"object","properties":{"candidateEventCandidates":{"type":"Array","description":"候选点击事件列表；事件 action 只能来自能力概述返回的事件能力说明","required":[],"properties":{"ArrayItem":{"type":"Object","description":"事件 action"}}},"description":{"type":"String","description":"建议写入最终 CardSpec 的静态短概述，尽量不超过 12 个字"},"candidateAssetIds":{"type":"Array<String>","description":"候选素材 ID 列表","required":[],"properties":{"ArrayItem":{"type":"String","description":"候选素材 ID"}}},"userQuery":{"type":"String","description":"能力裁决后的本轮有效卡片需求；调整后生成时不得保留已移除或未经确认替代的内容"},"candidateDataBindings":{"type":"Array","description":"已通过能力概述裁决的候选数据能力调用列表","required":[],"properties":{"ArrayItem":{"type":"Object","description":"候选数据能力","required":[],"properties":{"writeResultTo":{"type":"String","description":"结果写入路径"},"arguments":{"type":"Object","description":"参数"},"capabilityId":{"type":"String","description":"能力ID"},"candidateOutputFields":{"type":"Array<String>","description":"可选候选展示字段 JSON Pointer；必须能从对应能力 outputSchema 推导","required":[],"properties":{"ArrayItem":{"type":"String","description":"可选候选展示字段 JSON Pointer"}}}}}}},"title":{"type":"String","description":"建议写入最终 CardSpec 的静态短标题，尽量不超过 8 个字"},"size":{"type":"String","description":"你建议的尺寸"},"sourceArtifactUrl":{"type":"String","description":"上一版完整 artifact 的真实 URL；缺失表示首次生成，合法非空值表示编辑"}},"required":["userQuery"]}
