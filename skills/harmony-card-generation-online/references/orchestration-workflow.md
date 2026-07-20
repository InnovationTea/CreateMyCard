# 云侧编排工作流

本文档承接在线卡片 Skill 的职责边界和完整 create/edit 十步流程。工具字段与包装结构以 [`tool-contracts.md`](tool-contracts.md) 为准，候选构造以 [`candidate-planning.md`](candidate-planning.md) 为准，用户输出以 [`response-policy.md`](response-policy.md) 为准；此处不复制这些模块的详细契约。

## 职责与边界

主 Agent / Skill 负责识别创建或连续编辑场景，维护当前会话的卡片来源链，获取能力概述、选择候选、按需加载数据能力 schema，提交生成或编辑请求，并根据业务状态回复用户。编辑来源只从对应工具业务 payload 读取真实 `artifactUrl`，不解析或猜测普通回复中的 URL。

每次调用工具前检查是否仍有会影响核心卡片意图、候选选择或工具入参的用户待确认信息；有则先追问并等待用户回答。控制主要展示数据项不超过 4 项，编辑成功后使用本轮返回的新 `artifactUrl` 作为后续编辑的默认来源。

微服务负责真实设备能力过滤、最终 CardSpec、A2UI 模型输入、DSL 生成、校验、降级、失败重试和 artifact 上传。端侧负责下载、渲染、确认添加和运行时数据刷新。

主 Agent 不直接生成或输出 `genui`、CardSpec、A2UI prompt、替代 artifact 或校验修复结果；不下载、解析或修改来源 artifact；不把点击事件写入 CardSpec；不使用离线能力清单、历史模板或旧协议资料补足在线工具结果；不提前承诺任何动态能力一定可用。

## 十步流程

1. **触发与模式判断**：端侧显式标记且无编辑语义时视为 create；出现“修改、调整、删除、替换、换颜色、改尺寸、继续优化”等语义时视为 edit。用户明确指定目标时使用与该目标对应的最近一次 `success` / `degraded` 业务 payload 的真实 URL；未指定目标时默认最近结果，不因存在多张卡片额外追问；目标无法唯一对应时才追问。当前会话没有可用来源时要求先创建卡片，不把 edit 误走 create。
2. **初步回应**：不得提前承诺具体动态能力可用。需要过程回复时只说“我先检查当前设备支持情况，然后为你生成可用的卡片。”
3. **确认门禁与 schema 校验**：每次调用前检查核心需求、候选能力、目标对象、地点、日期或时间范围、动作目标和必填业务参数。存在用户可回答且会影响请求的未决信息时，集中追问最少必要内容并等待；可从用户原话、可信上下文或 schema 明确默认值安全确定的信息不重复确认。设备能力、能力 ID 和内部字段不向用户确认。门禁通过后读取当前运行时工具 schema，按 `SKILL.md` 的“调用前硬校验”检查 `functionName`、`bundleName`、必填字段、字段名、类型和嵌套结构。
4. **编辑请求分流**：先确认当前运行时 `generateWidgetCard` schema 声明 `sourceArtifactUrl`，否则按工具不可用结束，不得删除该字段后改走 create。纯视觉或布局 edit 只准备 `userQuery` 和来源 URL；标题、说明或尺寸 edit 只额外传用户明确修改的字段。删除数据能力或修改能力参数时，从同一会话恢复编辑后的完整数据候选集合，重新获取概述并加载 schema，最终显式传入完整 `candidateDataBindings`，`[]` 表示清空。本期 edit 不新增数据能力，也不修改事件或素材候选；遇到此类请求时建议重新创建。
5. **获取能力概述**：create 和需要删除数据能力或修改参数的 edit，在确认门禁通过后调用 `getWidgetCapabilityOverview`，除 `bundleName` 外不传字段。从 `items[].data` 解析业务 payload；原始插件包络先进入 `reply.items[].data`。`unavailableCapabilities` 缺失或为 `[]` 时按空集合处理；类型错误或 payload 无法解析时按异常结束。
6. **筛选候选能力**：数据能力只从实际可用的 `dataCapabilities` 选择，最多优先选 2 个核心候选；`unavailableCapabilities` 本期只适用于数据能力，不可用 ID 不加载 schema、不写入 binding。事件最多优先选 2 个主动作，素材只选强相关的少量 ID。部分数据不可用但剩余数据仍有价值时，记录缺失数据的用户可读名称并继续，不询问是否继续；用户明确要求“必须包含，否则不要生成”时保留该约束，由微服务作 `unsupported` 裁决。所有相关数据能力均不可用且没有生成价值时保留原始需求交给微服务，不伪造候选。
7. **加载数据能力 schema**：只为本轮概述中实际可用且已选中的数据能力调用 `getDataCapabilitySchemas`。候选选择存在会改变核心结果的歧义时先追问。schema 必填业务参数无法从用户原话、可信上下文或安全默认值取得时，用用户可理解的说法集中追问，不暴露字段名，也不为绕过追问删除核心候选。`missingCapabilityIds` 对应候选必须移除，并纳入部分或整体不支持判断。
8. **构造请求计划**：create 基于 schema 构造完整候选计划；edit 只传本轮明确替换的字段或候选类别。`size` 只使用 `2x2` 或 `2x4`；create 必传静态短 `title` 和 `description`，edit 仅在用户明确修改时传。`candidateDataBindings` 只包含运行时 schema 声明的 `capabilityId`、`arguments`、`writeResultTo` 和可选 `candidateOutputFields`；能力参数匹配 `inputSchema`，展示路径是可由对应 `outputSchema` 推导的 JSON Pointer 字符串数组，合计主要展示项不超过 4 项，无法确认时省略，禁止传 `updateModel`。被主动舍弃的用户明确展示需求保留在会话规划中，用于最终结果说明。事件候选每项包含 overview 返回的 `capabilityId` 和完整 `action:{call,args}`，无法安全填齐时不传；素材 ID 只来自 overview。`sourceArtifactUrl` 仅 edit 使用。本版不传 `slots`、`options`、`locale`、`uid`、`device` 等未声明字段。
9. **生成或编辑**：调用前再次执行确认门禁和当前运行时 `generateWidgetCard` schema 校验。核心业务信息缺失或存在歧义时先追问并重建计划；只影响非核心可选内容时可以删除该候选。删除 schema 未声明的可选字段，但不得删除 edit 必需的来源字段后继续；必填字段缺失、类型不匹配或嵌套结构不合法时停止。校验通过后调用 `generateWidgetCard`，不补做微服务负责的继承、过滤、协议选择、校验、重试或上传。
10. **回复与编辑链**：从生成工具的 `items[].data` 解析业务 payload；原始插件包络先进入 `reply.items[].data`。完整 `success`、部分数据不支持、`unsupported` 和其它异常均按回复策略处理。只有 `success` / `degraded` 且存在合法真实 URL 时才能输出 `genWidgetResult`；已知部分用户数据缺失时使用统一部分数据话术，不透传非完整状态的 `message`。edit 成功还要求新 URL 不同于来源 URL，并将新 URL 设为后续默认来源；失败、不支持或异常不更换默认来源。

## 场景加载顺序

- **create**：本文件 -> `candidate-planning.md` -> `tool-contracts.md` -> 调用工具 -> `response-policy.md`。
- **纯视觉、布局、文案或尺寸 edit**：本文件 -> `tool-contracts.md` 的 edit 契约 -> 调用工具 -> `response-policy.md`。
- **删除数据或修改参数 edit**：本文件 -> `candidate-planning.md` 的编辑恢复规则 -> `tool-contracts.md` -> 调用工具 -> `response-policy.md`。
- **联调或排障**：在对应路径基础上按需读取 `examples.md` 和 `tools/` 快照；实际调用始终以运行时 schema 为准。
