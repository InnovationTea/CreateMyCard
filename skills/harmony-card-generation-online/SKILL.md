---
name: harmony-card-generation-online
description: "为小艺/HarmonyOS 创建或修改桌面服务卡片（widget、小组件），并在卡片上下文中判断需求是否适合桌面卡片、能力是否足以生成以及是否需要提前引导。当用户想把天气、日程、提醒、设备状态、应用数据、运动健康或快捷操作等内容做成桌面卡片，或提出“创建卡片”“生成卡片”“做一张卡片”“服务卡片”“桌面卡片”“widget”“小组件”“添加到桌面”“预览卡片”“修改或继续优化刚才的卡片”等需求时使用；在卡片创建页面、模板选择上下文或带有 /harmony-card-generation 标记时也应使用。不要因普通非卡片对话召回。"
metadata:
  tools:
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "getWidgetCapabilityOverview"
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "getDataCapabilitySchemas"
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "generateWidgetCard"
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "RequestDataPermission"
---

# Harmony 卡片生成（云侧工具编排版）

## 执行入口

先判断 create/edit 模式，再按场景加载最少必要资料：

- 所有请求先读取 [`references/orchestration-workflow.md`](references/orchestration-workflow.md)，按完整十三步流程推进。
- create、删除数据能力或修改数据参数：再读取 [`references/candidate-planning.md`](references/candidate-planning.md) 和 [`references/tool-contracts.md`](references/tool-contracts.md)。
- 纯视觉、布局、文案或尺寸 edit：只继续读取 [`references/tool-contracts.md`](references/tool-contracts.md) 的 edit 契约。
- 生成前需要追问、结束、引导、说明部分满足，或处理最终工具结果时读取 [`references/response-policy.md`](references/response-policy.md)。
- 仅在联调、排障或核对回归格式时读取 [`references/examples.md`](references/examples.md) 和 [`references/tools/`](references/tools/) 中的工具 JSON 快照。

完整索引见 [`references.md`](references.md)。

## 模式与调用门禁

- 创建请求走 create；“修改、调整、删除、替换、换颜色、改尺寸、继续优化”等请求走 edit。
- 普通对话且不在卡片上下文时不召回本 Skill；已在卡片上下文但需求明确是非卡片任务、长报告、完整页面或复杂表单时，不调用工具，按回复策略说明桌面卡片边界并引导。
- 是否要做成卡片仍有歧义时，只追问一个最小必要问题并等待回答，不调用工具。
- 用户未指定尺寸时必须优先建议能够满足核心需求的最小尺寸：先按 `2x2` 规划，只有 `2x2` 无法容纳必须保留的核心内容、受保护文本、必要热区、关键并列关系或关键媒体时才建议 `2x4`。不得仅因信息较多、横版更舒展、视觉更丰富或存在两个数据能力而选择 `2x4`；用户明确指定尺寸时优先尊重。
- edit 未指定目标时使用当前会话最近一次成功或降级结果；明确目标无法对应时才追问。来源只能取目标卡片工具业务 payload 的真实 `artifactUrl`；没有可用来源时要求先创建，不得改走 create。
- 每次调用工具前检查是否缺少会改变核心意图、候选选择、目标对象、地点、时间范围、动作目标或业务入参的用户信息；有则集中追问并等待回答。设备能力、能力 ID、schema 等内部信息不向用户确认。
- 每次调用前读取当前运行时 `tools` schema，并执行下方“调用前硬校验”。参考资料、示例、历史字段和内部类结构不能覆盖运行时 schema。
- 在每次 `generateWidgetCard` 前确定本轮最终数据能力 ID 集合；非空时必须调用 `RequestDataPermission` 并等待结果。只有 Boolean `result.stateOfPermission` 明确为 `true` 且 `result.nonAuthStatus` 缺失或为空数组时才能生成；`nonAuthStatus` 为非空数组时终止并按回复策略使用其中的 `name` 与 `settingsPath` 引导用户手动授权；为 `false` 且没有授权明细时使用通用权限不可用提示。字段缺失、类型错误或其它非法结果按工具异常终止。数据集合变化后必须重新检查；空集合表示无动态数据权限需要检查。

## 生成前能力门禁

- 把本轮请求归为继续生成、调整后生成、追问、结束并引导四类，具体判定和推荐排序按 `references/candidate-planning.md` 执行。
- 能力概述或 schema 无法满足核心数据、核心动作或用户声明必须使用的素材，且不能形成满足原意图的静态或入口卡时，停止后续 schema 或 `generateWidgetCard` 调用，按回复策略引导。
- 核心内容可满足而仅次要数据、动作或用户明确要求的非核心素材不可用时，先说明缺失项和保留项，再自动继续生成，不等待确认。
- 用户明确“必须包含，否则不要生成”的能力不可用时，结束并引导，不生成降级版本。
- 静态入口或动作本身就是核心目标时，即使没有数据 binding 也继续生成。

## 职责边界

本 Skill 只负责模式识别、需求适配、候选编排、生成前能力满足度判断、工具调用和用户回复。微服务负责真实设备能力裁决、最终 CardSpec、A2UI DSL、校验、降级、重试和 artifact 上传；端侧负责下载、渲染、安装与运行时刷新。

不自行生成、下载、解析或修改 DSL、CardSpec、A2UI prompt 或 artifact；不使用离线能力清单、历史模板或旧协议补足在线结果；不提前承诺任何动态能力一定可用。

## 工具定义

本 skill 依赖三个微服务工具和一个端工具，声明于 frontmatter `metadata.tools`。必须通过 `invoke` 调用，固定格式为 `invoke(functionName:"<toolName>", arguments:{bundleName:"<bundleName>", ...},"skillName":"harmony-card-generation-online")`。`skillName` 必须显式传当前 Skill frontmatter 的 `name`，本 Skill 固定为 `harmony-card-generation-online`；不要省略、传空字符串或使用显示名称。

### 调用前硬校验

每一次 `invoke` 都必须先完成以下检查：

1. 检查当前已知信息中是否存在用户可回答、且会影响核心意图、候选选择或本次业务入参的未决项；有则先追问并等待回答，本轮不得执行 `invoke`。只有用户回答后才能重新进入调用前检查。可安全推导或有明确默认值的信息不追问；微服务负责裁决的能力可用性和内部技术字段不向用户确认。
2. 从当前运行时 `tools` 中找到与 `metadata.tools` 的 `bundleName + toolName` 完全匹配的工具；找不到时按工具不可用处理。
3. `functionName` 只使用该工具的 `toolName`，`arguments.bundleName` 只使用该工具的 `bundleName`，`skillName` 必须与当前 Skill frontmatter 的 `name` 完全一致，即 `"harmony-card-generation-online"`。
4. 除 `bundleName` 外，只从当前工具 schema 的 `arguments.properties` 选择顶层字段；schema 未声明的字段全部删除。
5. 逐项满足当前工具 schema 的 `required`、字段类型、数组元素类型和已声明嵌套结构。缺少用户可提供的核心业务值时先追问；属于工具接入、schema 不兼容或用户无法确认的技术缺口时停止调用，不把问题转嫁给用户，不猜测、不降格为字符串，也不补 `null` 占位。
6. 参考资料、调用样例和内部类结构只能帮助理解 schema，不能授权新增 schema 外字段；它们与当前运行时 schema 冲突时，无条件以当前运行时 schema 为准。
7. `candidateDataBindings[].arguments` 等能力业务参数还必须逐字段匹配本轮 `getDataCapabilitySchemas` 返回的对应 `inputSchema`；未声明字段不得传入。
8. `candidateDataBindings[].candidateOutputFields` 必须是字符串数组，且每个 JSON Pointer 都能从同一能力本轮返回的 `outputSchema` 推导；不匹配的路径删除，全部不匹配时省略该字段。禁止传 `updateModel`。
9. edit 模式必须确认当前 schema 声明 `sourceArtifactUrl` 且值为目标卡片真实的非空 `artifactUrl`；字段未声明或值不可取得时停止编辑，不得改为 create 请求。

工具声明里部分入参可能只暴露为 `Array<Object>` 或 `Object`。只有当前运行时 schema 已声明对应数组或对象字段时，才按 `references/tool-contracts.md` 中的 `CandidateDataBinding`、`CandidateEventCandidate` 和 `EventAction` 结构组装；不得借助内部类结构向 `arguments` 顶层添加 schema 外字段。

### Function: getWidgetCapabilityOverview
- **toolName**: getWidgetCapabilityOverview
- **description**: 获取当前用户实际可用的数据能力、不可用数据能力 ID，以及事件和素材概述。
- **参数**: {}
- **语义**: `dataCapabilities` 是当前用户实际可用的数据能力；`unavailableCapabilities` 只用于记录本地不可用的数据能力，不进入 schema 加载或数据候选。

### Function: getDataCapabilitySchemas
- **toolName**: getDataCapabilitySchemas
- **description**: 按数据能力 ID 加载完整 inputSchema、outputSchema、依赖和 DataModel 骨架。
- **参数**: {"type":"object","properties":{"dataCapabilityIds":{"type":"Array<String>","description":"需要加载完整 schema 的数据能力 ID 列表，至少 1 个。","required":[],"properties":{"ArrayItem":{"type":"String","description":"完整 schema 的数据能力 ID "}}}},"required":["dataCapabilityIds"]}
- **约束**: 必须在调用 getWidgetCapabilityOverview 获取能力列表之后调用。入参 dataCapabilityIds 从能力概述返回的数据能力 ID 中选取。

### Function: generateWidgetCard
- **toolName**: generateWidgetCard
- **description**: 提交用户需求和候选计划首次生成卡片，或通过上一版 artifact URL 连续编辑卡片。
- **参数**: {"type":"object","properties":{"sourceArtifactUrl":{"type":"String","description":"可选。上一版完整 artifact 的真实 URL；缺失表示首次生成，非空表示编辑"},"size":{"type":"String","description":"建议尺寸"},"candidateDataBindings":{"type":"Array","description":"已通过能力概述裁决的候选数据能力调用列表","required":[],"properties":{"ArrayItem":{"type":"Object","description":"候选数据能力","required":[],"properties":{"candidateOutputFields":{"type":"Array<String>","description":"可选候选展示字段 JSON Pointer；必须能从对应能力 outputSchema 推导","required":[],"properties":{"ArrayItem":{"type":"String","description":"可选候选展示字段 JSON Pointer"}}},"arguments":{"type":"Object","description":"参数"},"capabilityId":{"type":"String","description":"能力ID"},"writeResultTo":{"type":"String","description":"结果写入路径"}}}}},"candidateEventCandidates":{"type":"Array","description":"候选点击事件列表；事件 action 只能来自能力概述返回的事件能力说明","required":[],"properties":{"ArrayItem":{"type":"Object","description":"事件 action"}}},"userQuery":{"type":"String","description":"首次生成时为原始需求，编辑时只表达本轮修改"},"candidateAssetIds":{"type":"Array<String>","description":"候选素材 ID 列表","required":[],"properties":{"ArrayItem":{"type":"String","description":"候选素材 ID"}}},"title":{"type":"String","description":"建议写入最终 CardSpec 的静态短标题，尽量不超过 8 个字"},"description":{"type":"String","description":"建议写入最终 CardSpec 的静态短概述，尽量不超过 12 个字"}},"required":["userQuery"]}

### Function: RequestDataPermission
- **toolName**: RequestDataPermission
- **description**: 获取特定场景的数据权限能力
- **参数**: {"type":"object","properties":{"dataCapabilityIds":{"type":"Array<String>","description":"需要加载完整 schema 的数据能力 ID 列表，至少 1 个。","required":[],"properties":{"ArrayItem":{"type":"String","description":"完整 schema 的数据能力 ID "}}}},"required":["dataCapabilityIds"]}

## 输出与安全

- 业务状态、固定回复、`XX` 提炼和 `genWidgetResult` 格式只以 [`references/response-policy.md`](references/response-policy.md) 为准；调用样例只以 [`references/examples.md`](references/examples.md) 为准。
- 只输出 `generateWidgetCard` 业务 payload 返回的真实 `artifactUrl`；edit 成功的新 URL 必须不同于来源 URL。
- 生成前结束时不伪造 `unsupported` payload，不输出 `genWidgetResult`；推荐内容只用于引导下一轮请求，不代表能力承诺。
- 不编造能力 ID、事件目标、素材 ID、用户数据或 URL；不选择、加载或传递不可用数据能力；不暴露 schema、provider、错误码、requestId、items、原始 data 或内部草稿。
- 任一必要工具不可用、调用失败、结果无法解析或字段不合法时终止本轮，按回复策略处理；不得模拟成功、输出替代产物或读取离线资料补足结果。
- 未取得本轮最终数据能力集合的明确权限通过结果时，不得调用 `generateWidgetCard`；返回非空 `nonAuthStatus` 或权限拒绝时不输出 `genWidgetResult`。
- 存在用户待确认信息时不得抢先调用工具；追问后等待用户回答，再重新执行调用门禁。
