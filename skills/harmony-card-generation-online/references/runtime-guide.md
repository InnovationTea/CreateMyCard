# 在线卡片运行指南

本文档是本 Skill 正常 create/edit 路径唯一需要加载的运行时资料。一次任务只读取一次本文档，不再加载其它 reference；示例和静态工具快照仅用于用户明确要求的联调、排障或回归，且不能覆盖当前运行时 schema。

## 模式、编辑链与调用轨迹

### 模式判断

1. 明确创建、生成、预览或添加桌面卡片时走 create；修改、删除、替换、改颜色、改背景、改布局、改文案、改尺寸或继续优化已有卡片时走 edit。create 不传 `sourceArtifactUrl`，每轮从本轮 overview 重新规划；edit 必须传目标卡片最近一次有效生成业务 payload 的真实 `artifactUrl` 作为 `sourceArtifactUrl`，只能继承该来源，不得改走 create。
2. 本轮 query 未出现“卡片”等词时，先结合连续上下文判断：若上一轮已成功生成目标卡片，且本轮明确是在修改其颜色、背景、布局、文案、尺寸或已有数据，则仍走 edit；若本轮表达“再做一张/重新创建”或无法确认修改对象，则按 create 或追问处理，不能仅凭历史卡片自动走 edit。明确非卡片任务、长报告、完整页面或复杂表单时零工具调用并说明边界。
3. edit 未指定目标时使用当前会话最近有效卡片；明确目标无法对应时才追问。
4. edit 仅支持纯视觉/布局/文案/尺寸、删除数据能力和修改已有数据参数。新增数据能力、修改事件或素材候选时不调用工具，引导重新创建。

模式判断示例：

- 无有效卡片上下文，用户说“做一张天气卡片”或“生成一个天气 widget”：判定为 create，不传 `sourceArtifactUrl`。
- 上一轮已成功生成卡片，本轮 query 未提“卡片”，但说“颜色换成红色”“标题改成今天的天气”或“排版紧凑一点”：判定为 edit，必须将目标卡片最近一次有效业务 payload 的 `artifactUrl` 原样作为 `sourceArtifactUrl`。
- 上一轮已成功生成卡片，本轮说“再做一张日历卡片”或“重新创建一个更大的天气卡片”：判定为 create，不继承上一轮 URL。
- 上一轮有卡片但本轮只说“改一下”“继续优化”，无法确认修改对象或修改内容：先追问一个最小必要问题，不调用 create/edit 工具。

### 编辑链

主 Agent 不创建独立状态，只从当前对话中的真实工具调用参数和合法业务结果追溯：

- 仅本会话中目标卡片最近一次 `success` / `degraded` 生成业务 payload 的真实 `artifactUrl` 标识有效结果，并且必须原样作为下一轮 edit 的 `sourceArtifactUrl`；不能使用用户可见回复、示例、`streamInfo`、缓存或普通文本中的 URL。
- `candidateDataBindings` 取自生成该结果的真实 `generateWidgetCardCompactDsl` 调用；若该轮省略，则沿 `sourceArtifactUrl` 查找最近一次显式完整数组。
- 后续 `effectiveCapabilities.data` 和可靠对应的移除结果用于排除未生效能力。
- 失败、非法结果、无新 URL 或 edit 返回来源 URL 都不形成新节点，不改变追溯起点。
- 不从普通回复、任何结果代码块、示例或来源 artifact 恢复内部字段。链路无法可靠建立时停止 edit，不猜测或改走 create。

### 调用轨迹

| 场景 | 轨迹 |
| --- | --- |
| create，有数据候选 | overview → schema → permission → generate |
| create，无数据候选 | overview → schema（空数组）→ generate |
| 纯视觉/布局/文案/尺寸 edit，来源含动态数据 | permission → generate |
| 纯视觉/布局/文案/尺寸 edit，来源无动态数据 | generate |
| 删除数据或修改参数 edit | overview → schema → permission（集合非空时）→ generate |
| 非卡片、追问、edit 新增能力 | 零调用 |

箭头均以当前结果合法且门禁通过为前提。除权限工具 invoke 级异常按默认开启继续外，任一步失败立即终止，不调用后续工具。生成工具返回后不再调用其它工具补做交付。

### create 强制四工具链

一旦判定为 create，必须严格按本轮结果执行四工具链：`getWidgetCapabilityOverview` → `getDataCapabilitySchemas` → `RequestDataPermission` → `generateWidgetCardCompactDsl`。唯一允许不调用的工具是：最终候选数据集合为空时跳过 `RequestDataPermission`；集合非空时必须尝试调用权限工具，即使调用失败也只能按权限工具异常分支继续，不能事先省略。此时仍必须执行 overview、schema 和 generate。历史对话、此前 artifact、旧的能力概述或 schema、缓存、相似需求经验和用户之前的授权结果均不得替代本轮步骤或作为跳过理由。

- 每个 create 必须先调用本轮 `getWidgetCapabilityOverview`；未取得合法概述不得调用后续工具。
- 每个 create 都必须调用本轮 `getDataCapabilitySchemas`；无数据候选时传 `dataCapabilityIds:[]`，表示没有需要加载的数据 schema。
- 本轮最终数据集合非空时，必须调用 `RequestDataPermission`；只有最终集合为空时不发起该调用。
- 前述门禁均满足后才调用 `generateWidgetCardCompactDsl`。create 不得省略 overview、schema 或 generate；只有最终候选数据集合为空时跳过权限工具。

### 端到端十三步

1. 确认当前请求或上下文明确指向桌面卡片。
2. 执行卡片形态门禁，非卡片或不适配需求零工具调用。
3. 判断 create/edit 和目标卡片。
4. 按 edit 类型分流，新增能力直接引导重新创建。
5. 检查用户可回答且会改变核心结果的缺失信息。
6. 如需过程回复，只使用本文规定的话术。
7. create 每次都获取本轮能力概述，不得复用历史结果；数据类 edit 也获取，其它 edit 跳过。
8. 选择候选并执行第一次能力满足度门禁。
9. 只为已选可用数据能力加载 schema，移除 missing 后再次执行门禁。
10. 构造 create 完整候选计划或 edit 明确替换字段，并确定最终数据能力集合。
11. 集合非空时执行权限门禁，空集合跳过。
12. 前置门禁通过后调用生成工具，不补做微服务职责。
13. 在内部调用轨迹中锁存当前 payload 的有效 URL，按状态回复自然语言；端侧展示由生成工具内部完成，有效 edit 结果成为后续编辑链新节点。

## 生成前规划

### 用户确认与满足度

每次调用前检查核心对象、应用、联系人、地点、日期/时间范围、设备、动作目标和能力必填参数。用户可回答且答案会改变核心意图、候选或必填参数时先追问；不询问设备支持情况、应用安装情况、权限、能力 ID、schema、写入路径或协议版本。

确需说明进度时只说“我先检查当前设备支持情况，然后为你生成可用的卡片。”，不提前承诺具体能力。

区分核心与次要内容：缺失后改变主要用途的数据或动作是核心；“必须”“只要”“一键”等约束、主要动态数据和主要动作默认是核心。素材默认次要，只有用户明确要求必须使用时才是硬约束。静态入口或动作本身是核心目标时，无数据候选也可继续。

| 决策 | 条件 | 后续 |
| --- | --- | --- |
| 继续生成 | 核心可满足，或静态/入口卡保持原意图 | 继续 |
| 调整后生成 | 核心可满足，仅次要内容不可用 | 先说明缺失与保留项，再自动继续，不等待确认 |
| 追问 | 缺少会改变核心意图、候选或必填参数的用户信息 | 只问最小必要问题并等待 |
| 结束并引导 | 核心无法满足且静态/入口卡不能保持原意图 | 停止后续工具并给出相近需求 |

用户明确“必须包含，否则不要生成”的能力不可用时直接结束，不降级。工具异常不用于推断能力，也不据此推荐。

### 概述筛选

从 query 提取场景、动态数据、动作和素材，再从本轮 overview 选择：

- 数据只从 `dataCapabilities` 选择，最多 2 个核心候选；`unavailableCapabilities` 不加载 schema、不进入候选。
- 事件最多 2 个主动作，只选择语义强相关且参数可安全补齐的候选。
- 素材保留 1～4 个强相关 ID；无强匹配时传空数组。
- 不因名称相似选择会改变用户意图的能力，不编造数据、动作或素材。

概述或 schema 无法覆盖核心数据、核心动作或必需素材时重新执行满足度决策。生成前结束或生成返回 `unsupported` 时推荐 1～3 条可复述需求：已有合法概述时优先同领域、低风险且有完整卡片价值的描述；尚无概述时只用天气、日程、运动、设备电量或系统状态等通用示例，并使用“可以试试”，不承诺可用。

### 尺寸与元信息

- 用户明确 `2x2` / `2x4` 时优先尊重；未指定时从 `2x2` 开始，先移除可选信息、摘要列表或只保留首项。
- 只有核心内容、受保护文本、必要热区、必须同屏关系或关键媒体无法在 `2x2` 成立时才用 `2x4`。信息较多、横版更舒展、天气加日程或两个数据能力都不是升级理由。
- 主要展示数据项合计不超过 4 项；无法取舍且用户要求全部保留时再追问。
- create 的 `title` / `description` 必须稳定静态，建议分别不超过 8 / 12 个字，无法提炼时使用“桌面卡片”/“信息速览”；不写动态值、隐私、设备状态或可用性承诺。edit 仅在用户明确修改时传。

### 候选构造

数据候选：

- 仅在运行时 schema 声明 `candidateDataBindings` 时传。`capabilityId` 必须来自本轮完整数据 schema。
- `arguments` 只含对应 `inputSchema.properties` 字段；核心必填值缺失且用户可回答时先追问。
- `writeResultTo` 优先使用 schema 默认值，否则使用不冲突的 `/data/{semanticKey}`；多个路径不得相同、互为父子或覆盖。
- `candidateOutputFields` 可省略；传入时只能是从 `outputSchema` 推导的叶子 JSON Pointer，数组元素用 `/0`，去重后所有候选合计不超过 4 项。
- 不传 `required`、`inputSchema`、`outputSchema`、`updateModel` 或未声明字段。

```json
{
  "capabilityId": "ViewWeather",
  "arguments": {"districtName": "青浦区", "forecastDays": 1},
  "writeResultTo": "/data/weather",
  "candidateOutputFields": ["/location/districtName", "/current/temperatureText"]
}
```

事件与素材候选：

- `candidateEventCandidates` 每项同时包含 overview 返回的 `capabilityId`，并将同项 `actionTemplate` 完整
  深拷贝为 `action`。不得删除、重排或改写模板中的固定字段；`intentName` 以及值为空字符串的字段也必须
  保留。`dynamicArguments[].path` 是相对 `actionTemplate.args` 的 JSON Pointer，只允许按这些路径替换动态
  值；用户只补业务值，不编造 deeplink、intent、包名、ability、号码或参数名。模板中的动态占位符无法
  按说明安全解析且模板默认值也不合法时，移除整个候选；核心动作因此缺失时重新决策。
- 高风险或不可逆动作仅在用户明确要求且 overview 明确支持时选择。候选 action 不是最终 DSL `onClick`，最终过滤和写入由微服务负责。
- `candidateAssetIds` 只用 overview 返回的 ID；没有语义匹配时传空数组，不自造路径。
- 不传 `slots`、`options`、`locale`、`uid`、`device` 或运行时 schema 未声明的字段。

## 工具契约

### 调用与 schema 总则

统一调用格式保持不变。`arguments` 顶层键名沿用当前格式；每个键的 value 必须是合法 JSON 值，嵌套对象和数组元素递归使用 JSON 键和值：

```text
invoke(functionName:"<toolName>", arguments:{bundleName:"com.omega_w_0823.hmservice", ...},"skillName":"harmony-card-generation-online")
```

每次调用前从运行时 tools 找到与 frontmatter `bundleName + toolName` 完全匹配的工具。`skillName` 固定为 `harmony-card-generation-online`；除 `bundleName` 外只传当前 `arguments.properties` 声明字段，满足 required、类型、数组项和嵌套结构。能力 `arguments` 还必须匹配本轮能力 `inputSchema`。运行时 schema 是唯一入参依据；文档、示例、快照和内部类不能授权额外字段。

业务必填值缺失且用户可回答时先追问；工具/schema 技术缺口直接终止。不得猜测、传 `null`、降格为字符串、把对象字符串化，或手写 `content`、`deviceInfo`、`session`、`pagination`、`userAuth`、`utterance`、`version` 等插件包络。

### 微服务包装解析

三个微服务工具当前按快照返回统一包络：顶层必须包含 `streamInfo` 和 `items`，`items[]` 承载 `tool`、`data`、`status`、`error`、`errorCode`、`operation`、`type` 与 `requestId`。直接读取顶层 `items`。

- 从 `items` 优先选择 `tool` 等于当前工具名且含 `data` 的项；无 `tool` 时选第一个含 `data` 的项。`data` 为 JSON 字符串时解析为对象，已是对象时直接使用。
- 没有可解析的 `items[].data`、`items[].error` 表示失败、payload 缺结构或字段类型非法时按工具异常终止。
- `streamInfo` 只用于展示/调试；`items[].status/errorCode/requestId` 不是业务状态，也不向用户展示。

`RequestDataPermission` 是端工具，直接读取其运行时输出，不套用上述微服务包络。

### getWidgetCapabilityOverview

仅传 `bundleName`。payload 包含 `dataCapabilities`、可选 `unavailableCapabilities:string[]`、
`eventCapabilities` 和 `assetCandidates`。事件每项必须有 `id/description/actionTemplate/dynamicArguments`，
素材每项只读取 `id/description`；不得要求或猜测素材路径、版本或标签。`unavailableCapabilities` 缺失或
`[]` 视为空；非字符串数组则 payload 非法。数据候选只能来自 `dataCapabilities`。

### getDataCapabilitySchemas

传非空 `dataCapabilityIds`，ID 只能来自本轮 overview 的 `dataCapabilities`。payload 包含完整 `dataCapabilities` 和 `missingCapabilityIds:string[]`；移除 missing 候选后重新执行满足度门禁，最后一个核心能力被移除时不生成。完整 schema 不向用户展示。

### RequestDataPermission

每次生成前确定去重后的最终数据能力 ID：create 取最终 bindings；数据类 edit 取编辑后的完整 bindings；纯视觉/布局/文案/尺寸 edit 优先取目标结果的 `effectiveCapabilities.data`，缺失时按编辑链恢复。无法可靠恢复则停止；空集合跳过权限工具，集合或 binding 变化后重新检查。

传完整非空 `dataCapabilityIds` 后等待正常结果或明确 invoke 异常，结论未确定前不得生成：

- 只有 `result.stateOfPermission` 为 Boolean `true`、`nonAuthStatus` 缺失或为空数组，且任何权限项都未出现 Boolean `authorized:false` 时通过。
- `stateOfPermission:false` 或任一 `authorized:false` 一票否决并终止生成，必须按“权限未通过”预置话术回复，不得调用生成工具、追问、建议或改写话术。
- `nonAuthStatus` 非空时，每项必须是对象且 `name` 为非空字符串；`settingsPath` 缺失按空字符串。任一有效项即终止生成，必须按“权限未通过”预置话术逐项回复；同名项保留第一项，不输出 capabilityId、authType 或 authorized。
- 仅当本次 `RequestDataPermission` 调用失败时，才按权限默认开启静默继续生成。调用失败仅指工具不可用、invoke 抛错、或工具层明确执行失败；不重试、不伪造 `stateOfPermission:true`、不改变数据集合、不向用户说明异常或宣称已开启。
- 工具正常返回但缺少 `result`、`stateOfPermission` 非 Boolean 或明细非法时按结果非法终止，使用“其它异常”预置话术；这不是调用失败，不适用默认开启。

### generateWidgetCardCompactDsl

仅在运行时 schema 允许时传以下字段：

| 字段 | create | edit |
| --- | --- | --- |
| `userQuery` | 原始需求，必填 | 本轮修改，必填 |
| `sourceArtifactUrl` | 不传 | 目标卡片最近一次有效生成业务 payload 的真实 `artifactUrl`，必填 |
| `size` | 可选，只用 `2x2` / `2x4` | 仅修改时传 |
| `title` / `description` | 非空 | 仅修改时传 |
| `candidateDataBindings` | 可选 | 替换数据类别时传完整数组；`[]` 清空 |
| `candidateEventCandidates` / `candidateAssetIds` | 可选 | 本期不修改 |

payload 常用字段为 `status`、`message`、可选 `artifactUrl/suggestSize/removedCapabilities/effectiveCapabilities`。只认可 `success/degraded/unsupported/failed`；其它状态按 payload 非法。`success/degraded` 缺合法 URL 时按其它异常。合法 URL 仅用于确认有效结果和维护后续编辑链，不进入用户可见回复；卡片展示由生成工具内部交给端侧。

### 编辑请求构造与继承

| 修改类型 | 参数 |
| --- | --- |
| 纯视觉或布局 | `userQuery + sourceArtifactUrl` |
| 标题、说明或尺寸 | 再传用户明确修改的字段 |
| 删除数据或修改已有参数 | 再传编辑后的完整 `candidateDataBindings` |

数据类 edit 从真实编辑链恢复完整数组，删除目标 binding 或只修改目标 `arguments`，保留其它 binding；重新获取 overview/schema，校验全部参数、写入路径和投影后显式传完整数组，全部删除时传 `[]`。无法可靠恢复时不传不完整数组。

省略 `size/title/description` 或某类候选数组时由微服务从来源继承并重新校验；显式数组是完整替换，不是增量。来源为空、类型错误或运行时 schema 未声明 `sourceArtifactUrl` 时不调用，也不改走 create。成功 edit 必须返回不同于来源的新 URL；缺失、无效或相同均按其它异常，且不更新默认来源。

## 回复与内部结果留存

### 输出优先级

1. 仍有用户待确认信息：只追问并等待，不调用下一工具。
2. 权限正常返回未通过或非法：立即终止，不调用生成工具，并且只能输出对应预置话术。
3. 仅权限工具调用失败：静默放行并调用生成工具。
4. 生成返回后先从当前可解析业务 payload 读取合法真实 `artifactUrl`，再判断状态和话术；`streamInfo`、工具外层、历史结果和普通文本不是产物 URL。
5. URL 只在内部工具调用轨迹中留存。用户可见回复只输出状态对应的自然语言，不输出 URL、Markdown 链接、结果代码块或任何替代标记。

### 固定回复

生成前：

- 非卡片/形态不适配：`桌面卡片适合展示少量关键信息或提供快捷入口，暂不适合处理你这次的 XX。你可以试试：“建议一”、“建议二”`
- 核心能力缺失：`当前卡片能力暂无法满足你需要的 XX，因此这次先不生成。你可以试试：“建议一”、“建议二”`
- 部分满足预告：`当前暂无法提供 XX，我会保留 YY 继续为你生成卡片。` 输出后自动继续，不等待确认；若后续工具失败，最终只输出其它异常话术。
- edit 新增能力：`当前连续编辑暂不支持新增 XX，这次先不修改。你可以重新创建一张卡片，例如：“重新创建需求”`
- 生成前合法结束不伪造 `unsupported` payload，也不伪造产物 URL 或端侧展示结果。

权限未通过（仅限权限工具正常返回且明确拒绝）：

- `nonAuthStatus` 有有效项且路径非空：`请前往「{settingsPath}」，为「{name}」开启权限，然后再试。`
- 路径为空：`请为「{name}」开启权限，然后再试。` 多项逐行输出，不追加建议或承诺。
- `stateOfPermission:false` 或任一 `authorized:false` 且无有效明细：`当前生成卡片所需的数据权限不可用，已停止生成。` 不得改写或追加内容。
- 权限正常返回但非法：使用其它异常预置话术 `卡片创建过程遇到问题了，请稍后再试`，不调用生成工具。invoke 异常不输出权限话术，最终只按生成结果回复。

生成后自然语言：

| 情形 | 话术 |
| --- | --- |
| 完整 success | 仅使用不含产物 URL 和内部信息的 `message`；为空或不安全时 create 用“已为你生成卡片。”，edit 用“已按你的要求修改卡片。” |
| 部分数据缺失 | `本次卡片生成暂无你提及的 XX 数据，将基于可获取数据为你生成卡片` |
| 部分动作缺失 | `本次卡片暂不支持你提及的 XX 操作，将保留可展示内容为你生成卡片` |
| 部分素材缺失 | `本次卡片暂无法使用你提及的 XX 素材，将使用可用样式为你生成卡片` |
| 混合缺失 | `本次卡片暂无法完整支持你提及的 XX，将基于可用内容为你生成卡片` |
| unsupported | `抱歉，当前暂无法获取你提及的 XX 功能数据。你可以试试：“建议一”、“建议二”` |
| failed、必要工具异常、payload 异常、success/degraded 无 URL | `卡片创建过程遇到问题了，请稍后再试` |

`degraded + URL` 或已知部分缺失的 `success + URL` 使用部分满足话术。除完整 success 外不透传或润色业务 `message`。其它异常不追加建议、原因或 edit 专属话术。任何状态下都不得把 payload 中的 URL 输出给用户；`unsupported`、`failed` 或异常 payload 即使带 URL，也不形成有效编辑节点。

### 名称与建议

`XX/YY` 优先使用用户原话中的数据、动作、素材或需求类型，并用能力描述/移除结果核对；`YY` 使用仍保留的内容，多个名称去重后用“、”连接。无法提炼时 `XX` 用“相关内容”、`YY` 用“其他可用内容”。不输出能力 ID、包名、provider、schema、错误码，不编造动作目标、号码、deeplink、素材路径或用户数据。

回复不得声称“已添加到桌面”；这里只生成预览 artifact，端侧负责下载、渲染和确认添加。不要把部分满足描述成工程失败，不把整体不支持描述成系统异常，不引导安装不确定的 App，不承诺开启权限后一定可用，也不暴露来源 URL、CardSpec、DSL 或校验细节。

### URL 留存与保密不变量

- 卡片展示由生成工具内部将 URL 交给端侧，主 Agent 不重复承担交付职责。
- 只有当前业务 payload 中带全新合法 `artifactUrl` 的 `success` / `degraded` 结果才形成有效编辑节点。
- create 的有效 URL 作为该卡片后续 edit 的初始 `sourceArtifactUrl`；edit 的有效新 URL 替换该卡片此前的来源。
- `unsupported`、`failed`、非法 payload、缺失 URL 或 edit 返回来源 URL 都不更新编辑来源。
- 不从用户可见回复、历史自然语言、示例、`streamInfo` 或工具外层恢复 URL。
- 用户可见回复不得包含原始 URL、Markdown 链接、`genWidgetResult`、`genuiResult` 或任何替代结果代码块。

发送前检查：

```text
userVisibleContainsArtifactUrl == false
userVisibleContainsResultMarker == false
validEditNode == ((status == success || status == degraded) && hasNewValidArtifactUrl)
```
