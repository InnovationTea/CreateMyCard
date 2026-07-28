# 云侧编排工作流

本文档承接在线卡片 Skill 的职责边界和完整 create/edit 十三步流程。工具字段与包装结构以 `references/tool-contracts.md` 为准，候选构造以 `references/candidate-planning.md` 为准，生成前及生成后用户输出以 `references/response-policy.md` 为准。

## 职责与边界

识别创建或连续编辑场景，判断需求是否适合桌面卡片，维护当前会话的卡片来源链，获取能力概述，选择候选，按需加载数据能力 schema，在生成前判断能力满足度并检查本轮数据权限，提交生成或编辑请求，并根据决策、权限结果或业务状态回复用户。编辑来源只从对应工具业务 payload 读取真实 `artifactUrl`，不解析或猜测普通回复中的 URL。

每次调用工具前检查是否仍有会影响核心卡片意图、候选选择或工具入参的用户待确认信息；有则只追问最小必要内容并等待用户回答。控制主要展示数据项不超过 4 项，编辑成功后使用本轮返回的新 `artifactUrl` 作为后续编辑的默认来源。

微服务负责真实设备能力过滤、最终 CardSpec、A2UI 模型输入、DSL 生成、校验、降级、失败重试和 artifact 上传。端侧负责下载、渲染、确认添加和运行时数据刷新。

不要直接生成或输出 `genui`、CardSpec、A2UI prompt、替代 artifact 或校验修复结果；不要下载、解析或修改来源 artifact；不要把点击事件写入 CardSpec；不要使用离线能力清单、历史模板或旧协议资料补足在线工具结果；不要提前承诺任何动态能力一定可用。

## 十三步流程

1. **触发与卡片上下文判断**：普通对话且不在卡片上下文时不召回本 Skill。端侧显式标记、卡片创建页面、模板选择上下文或明确创建桌面卡片的请求进入本流程。
2. **需求适配门禁**：明确要求纯聊天、写作、代码、长报告、完整 App 页面或复杂表单时，不调用工具，按回复策略说明桌面卡片边界并提供 1 至 3 条可直接复述的卡片需求。是否要做成卡片仍有歧义时，只追问一个最小必要问题并等待回答。
3. **模式判断**：端侧显式标记且无编辑语义时视为 create；出现“修改、调整、删除、替换、换颜色、改尺寸、继续优化”等语义时视为 edit。用户明确指定目标时使用与该目标对应的最近一次 `success` / `degraded` 业务 payload 的真实 URL；未指定目标时默认最近结果。目标无法唯一对应时才追问；当前会话没有可用来源时要求先创建卡片，不把 edit 误走 create。
4. **编辑请求分流**：先确认当前运行时 `generateWidgetCard` schema 声明 `sourceArtifactUrl`，否则按工具不可用结束，不得删除该字段后改走 create。纯视觉或布局 edit 只准备 `userQuery` 和来源 URL；标题、说明或尺寸 edit 只额外传明确修改的字段，其权限集合优先取目标卡片最近一次业务 payload 的 `effectiveCapabilities.data`。删除数据能力或修改能力参数时，从同一会话恢复编辑后的完整数据候选集合，重新获取概述并加载 schema，最终显式传入完整 `candidateDataBindings`，权限集合取编辑后的完整数据能力 ID。无法从有效结果或完整候选链可靠恢复权限集合时停止编辑，不下载来源 artifact 猜测。本期 edit 不新增数据能力，也不修改事件或素材候选；遇到此类请求时不调用编辑接口，按回复策略引导用户重新创建。
5. **确认门禁与运行时 schema 校验**：检查核心目标、候选选择、地点、日期或时间范围、动作目标和必填业务参数。存在用户可回答且会改变请求的未决信息时，只追问最小必要内容并等待；设备能力、能力 ID 和内部字段不向用户确认。门禁通过后按 `SKILL.md` 的“调用前硬校验”检查当前运行时工具 schema。
6. **初步回应**：不得提前承诺具体动态能力可用。需要过程回复时只说“我先检查当前设备支持情况，然后为你生成可用的卡片。”
7. **获取能力概述**：create 和需要删除数据能力或修改参数的 edit 调用 `getWidgetCapabilityOverview`，除 `bundleName` 外不传字段。从 `items[].data` 解析业务 payload；原始插件包络先进入 `reply.items[].data`。`unavailableCapabilities` 缺失或为 `[]` 时按空集合处理；类型错误或 payload 无法解析时按异常结束，不追加能力建议。
8. **筛选候选并执行第一次能力满足度门禁**：数据能力只从 `dataCapabilities` 选择，最多优先选 2 个核心候选；事件最多优先选 2 个主动作；素材只选强相关的少量 ID。按候选规划区分核心与次要内容：
   - 核心数据、核心动作或用户声明必须使用的素材无法满足，且不能形成满足原意图的静态或入口卡：停止后续 schema 和生成调用，结束并引导。
   - 用户明确“必须包含，否则不要生成”的能力不可用：结束并引导。
   - 核心内容可满足而仅次要内容不可用：记录缺失项与保留项，按回复策略先告知，再自动继续。
   - 静态入口或动作本身就是核心目标：允许没有数据候选，继续生成。
9. **加载 schema 并执行第二次能力满足度门禁**：只为本轮实际可用且已选中的数据能力调用 `getDataCapabilitySchemas`。候选选择或必填业务参数仍有核心歧义时先追问。移除 `missingCapabilityIds` 对应候选后重新执行第 8 步的能力满足度门禁；最后一个核心能力被移除时不调用 `generateWidgetCard`。
10. **构造请求与权限集合**：create 基于 schema 构造完整候选计划；edit 只传本轮明确替换的字段或候选类别。`size` 只使用 `2x2` 或 `2x4`；用户未指定时先按 `2x2` 收敛非核心可选信息，只有必须保留的核心内容、受保护文本、必要热区、关键并列关系或关键媒体无法在 `2x2` 中成立时才传 `2x4`，不得仅因横版更舒展、信息较多或存在两个数据能力而升级。用户明确指定尺寸时优先尊重。create 必传静态短 `title` 和 `description`，edit 仅在用户明确修改时传。数据 binding、展示字段、事件 action 和素材 ID 必须分别来自本轮 schema 或 overview。本版不传 `slots`、`options`、`locale`、`uid`、`device` 等未声明字段。同步确定本轮最终数据能力 ID 集合并去重：create 取最终候选 binding，数据类 edit 取编辑后的完整 binding，其它 edit 取目标卡片有效数据集合；纯静态或仅入口卡片可为空。
11. **数据权限门禁**：先对完整生成参数再次执行确认门禁、能力满足度门禁和当前运行时 `generateWidgetCard` schema 校验。数据能力 ID 集合非空时，读取当前运行时 `RequestDataPermission` schema，传完整 `dataCapabilityIds` 并等待结果；未返回前不得生成。只有 Boolean `result.stateOfPermission: true`、`result.nonAuthStatus` 缺失或为空数组，且返回中的权限项均未出现 Boolean `false` 时继续。`stateOfPermission: false` 或任一权限项 `authorized: false` 都一票否决，立即结束任务并拒绝继续生成；有授权明细时使用有效项的 `name` 与 `settingsPath` 引导用户手动授权，无明细时使用通用权限不可用话术。字段缺失、类型非法、工具不可用或调用失败时按其它异常终止。权限检查后若数据集合发生变化，必须重新检查；集合为空时跳过权限工具。
12. **生成或编辑**：仅在前置门禁通过，且数据权限已明确通过或本轮数据集合为空无需检查时，按既定参数调用 `generateWidgetCard`。不补做微服务负责的继承、过滤、协议选择、校验、重试或上传。
13. **回复与编辑链**：从生成工具的 `items[].data` 解析业务 payload。合法真实 `artifactUrl` 对端侧输出具有最高优先级：只要存在就必须输出 `genWidgetResult`，`degraded` 也不得省略；没有 URL 时不得输出。完整 `success`、按数据/动作/素材/混合分类的部分满足、`unsupported` 和其它异常仍按回复策略组织自然语言。`unsupported` 在保留受控核心句后，优先使用本轮概述提供相近建议；`failed`、权限工具异常或生成工具异常不追加建议。edit 成功还要求新 URL 不同于来源 URL，并将新 URL 设为后续默认来源；其它结果不更换默认来源。

## 场景加载顺序

- **所有已召回请求**：先读取 `references/orchestration-workflow.md`；需要追问、生成前说明、结束并引导或处理工具结果时读取 `references/response-policy.md`。
- **create**：继续读取 `references/candidate-planning.md` 和 `references/tool-contracts.md`。
- **纯视觉、布局、文案或尺寸 edit**：继续读取 `references/tool-contracts.md` 的 edit 契约。
- **删除数据或修改参数 edit**：继续读取 `references/candidate-planning.md` 的编辑恢复规则和 `references/tool-contracts.md`。
- **联调或排障**：在对应路径基础上按需读取 `references/examples.md` 和 `references/tools/` 快照；实际调用始终以运行时 schema 为准。
