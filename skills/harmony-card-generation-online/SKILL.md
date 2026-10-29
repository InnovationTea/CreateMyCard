---
name: harmony-card-generation-online
description: "用户提出创建、修改卡片或指定使用“桌面卡片生成技能”时，使用本 Skill。用户无需说明卡片类型、平台或生成方式；信息不清楚时由本 Skill 澄清，具体能否支持由后续流程判断。"
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

## 必读文件与读取时点

使用 `SkillLoad` 加载参考文件，`path` 为相对本 Skill 根目录的文件路径，不含章节锚点。以下调用按下述时点执行：

```text
SkillLoad({"skillName":"harmony-card-generation-online","path":"references/user-replies.md"})
SkillLoad({"skillName":"harmony-card-generation-online","path":"references/runtime-guide.md"})
```

- [固定回复规范](references/user-replies.md)：开始执行卡片流程前必须读取，用于选择回复模板和告知内容。
- [运行指南](references/runtime-guide.md)：处理外部事实、判断编辑范围或首次调用卡片工具前必须读取；后文标明各步骤适用的章节。
- 仅当所需完整内容已加载到当前上下文且仍可用时，才可跳过重复加载；主文摘要、链接或历史会话中的阅读记录不能替代。后文按章节执行时，无需逐步重新加载文件。
- [回归示例](references/examples.md)和[工具快照](references/tools/)仅供联调核对，正常执行不额外读取；不读取或调用 scripts。运行时 schema 是调用唯一依据，示例不替代真实结果。

## 领域知识

本 Skill 编排小艺 App 中 HarmonyOS A2UI Form 卡片的在线创建与修改。

按用户期待的数据来源和更新行为区分：需要卡片读取设备／应用实际数据，或随时间、状态变化更新的，属于动态需求；仅展示用户提供或本轮查询取得的固定内容，属于静态需求。混合需求逐项判断。
“今天、最新、提醒”等词本身不能决定类别；静态来源不能替代用户要求的动态读取或更新。

卡片业务数据必须来自本轮真实数据能力定义、已校验外部事实或用户明确提供的事实。外部事实指来源，静态内容指固定展示方式；用户提供的固定文字也可作为静态内容，无需外部查询。生成工具不是数据或交互能力来源。

纯静态普通创建先按[展示范围选择](references/runtime-guide.md#纯静态创建的展示范围选择)确定必要事实，查询也围绕该范围；
在采用及告知外部事实前完成选择，再完整传入选定事实。开放式需求突出重点，用户明确的数量、字段、原文及全部展示要求不得擅自缩减。
动态、混合动态及编辑不套用这项选择规则。

动态数据覆盖天气、日历、倒数日、蓝牙耳机、电池、运动健康、日期、应用排行、通话和备忘录；点击仅限本轮事件。打开闹钟页不等于创建闹钟，音乐入口不等于播放控制，备忘录入口不等于勾选待办，导航仅支持声明目标。完整范围见[能力边界](references/runtime-guide.md#动态数据与点击能力边界)，本轮概述与完整 Schema 优先；静态事实不能新增交互。

## 工具定义

以下所有打开与跳转事件统一遵守：仅支持对应的华为自带应用，如华为天气、音乐、地图、日历等，不能更换为其他应用；
不支持网易云音乐、QQ 音乐、百度地图、高德地图等第三方应用，也不支持任意指定应用。
用户指定第三方应用时，不得直接改用华为应用，不得修改动作模板的包名、URI 或目标；
按既有支持范围门禁处理，仅在改变主要用途的可用替代已获用户确认时继续。
日程提供的链接不授权打开清单外应用。

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
- **description**: 检查本轮数据能力的授权状态
- **参数**: {"type":"object","properties":{"dataCapabilityIds":{"type":"Array<String>","description":"本轮需要检查权限的数据能力 ID 列表，至少 1 个。","required":[],"properties":{"ArrayItem":{"type":"String","description":"数据能力 ID"}}}},"required":["dataCapabilityIds"]}

### Function: generateWidgetCardCompactDsl
- **toolName**: generateWidgetCardCompactDsl
- **description**: 生成极简协议版本的鸿蒙卡片
- **参数**: {"properties":{"candidateEventCandidates":{"type":"Array","description":"候选点击事件对象数组，每项仅含 capabilityId 和 action；将概述的 actionTemplate 值复制到 action，不提交 actionTemplate 或 dynamicArguments 定义。","required":[],"properties":{"ArrayItem":{"type":"Object","description":"来自本轮概述的事件候选","required":["capabilityId","action"],"additionalProperties":false,"properties":{"capabilityId":{"type":"String","description":"本轮事件概述 ID"},"action":{"type":"Object","description":"完整复制对应模板的值，只替换声明的动态参数","required":["call","args"],"additionalProperties":false,"properties":{"call":{"type":"String","description":"模板原始调用类型，不填事件 ID"},"args":{"type":"Object","description":"模板完整参数对象，保留固定值与空字符串，禁止序列化成字符串","additionalProperties":true}}}}}}},"description":{"type":"String","description":"建议写入最终 CardSpec 的静态短概述，尽量不超过 12 个字；新建必填非空，编辑未修改时省略并继承"},"candidateAssetIds":{"type":"Array<String>","description":"候选素材 ID 列表","required":[],"properties":{"ArrayItem":{"type":"String","description":"候选素材 ID"}}},"userQuery":{"type":"String","description":"能力裁决后的本轮有效卡片需求；有外部事实时在后方追加固定标题‘本轮卡片静态内容（用作展示的外部事实）：’及完整事实；调整后生成时不得保留已移除或未经确认替代的内容"},"candidateDataBindings":{"type":"Array","description":"已通过能力概述裁决的候选数据能力调用列表","required":[],"properties":{"ArrayItem":{"type":"Object","description":"候选数据能力","required":["capabilityId","arguments","writeResultTo"],"properties":{"writeResultTo":{"type":"String","description":"结果写入路径"},"arguments":{"type":"Object","description":"符合本轮 inputSchema 的 JSON 对象；无参用 {}，禁止 JSON 字符串、数组或 null","additionalProperties":true},"capabilityId":{"type":"String","description":"能力ID"},"candidateOutputFields":{"type":"Array<String>","description":"可选候选展示字段 JSON Pointer；必须能从对应能力 outputSchema 推导","required":[],"properties":{"ArrayItem":{"type":"String","description":"可选候选展示字段 JSON Pointer"}}}},"additionalProperties":false}}},"title":{"type":"String","description":"建议写入最终 CardSpec 的静态短标题，尽量不超过 8 个字；新建必填非空，编辑未修改时省略并继承"},"size":{"type":"String","description":"用户指定尺寸时必须显式传入，优先于默认或建议；未指定按尺寸规则。","enum":["2x2","2x4"]},"sourceArtifactUrl":{"type":"String","description":"上一版完整 artifact 的真实 URL；缺失表示首次生成，合法非空值表示编辑"}},"required":["userQuery"],"type":"object","additionalProperties":false,"description":"业务参数必须直接为 JSON 对象，不调用 JSON.stringify、不手工转义整个对象；创建和编辑共用此入口。"}

### 业务工具调用

卡片业务使用 frontmatter 声明的三个微服务工具和一个端工具，通过 `invoke` 调用，参数统一使用下列 JSON 对象；
**注意**：要求 `arguments` 直接为 JSON 对象，禁止整体序列化成字符串；`skillName` 固定为 `harmony-card-generation-online`。

```text
{"functionName":"<toolName>","arguments":{"bundleName":"com.omega_w_0823.hmservice","<业务字段>":"<本轮合法值>"},"skillName":"harmony-card-generation-online"}
```

## 操作规程

先执行步骤 0 分流；只有明确需要外部静态事实时才提前进入步骤 1。创建和已有数据参数修改走步骤 2，纯视觉、文案和尺寸编辑直接走步骤 3。
生成接口调用后可能没有自然语言回复机会：所有调用前已确定且需要告知的拒答、引导、澄清、缺失、限制和事实，
必须在调用前按对应模板实际发送，不能留到步骤 8。需要回答时等待，需停止时不调用；不得提前宣称成功或推测生成结果。

### 0. 判断触发范围与 create/edit

- **进入条件：** 用户提出创建或修改卡片的意图即触发，包括未说明卡片类型、平台或形态的请求；真实连续上下文中的已有卡片修改也触发。不得在触发阶段按卡片产品类型排除请求，具体能否支持由后续流程判断。普通讨论卡片或独立搜索且没有创建、修改意图时不触发。
- **用户回复：** 卡片意图不明用 R03；编辑对象不明用 R04；修改内容不明用 R05；不适合卡片承载用 R06。明确不支持 query 只发送 R06/R07/R10 对应固定话术并结束，不发送 R16/R16W、R01/R02 或调用任何业务工具。
- **工具调用示例：** 本步不调用业务工具，必读资料仍按开头要求加载。只检查形态、静态范围和最小语义歧义，不提前猜测动态能力或追问其参数。
- **来源与检查：** 结合当前需求和真实工具轨迹判断模式；已有外部事实留待步骤 1 或 5 校验，不因来源早于 Skill 而遗漏；
  明确创建、再做一张、重新创建为 create；
  改颜色、背景、布局、文案、尺寸、删除或替换已有内容为 edit，即使用户省略“卡片”。
- **编辑边界：** 数据集合增删（包括删除部分、全部数据或改为纯静态内容）、跨数据能力替换、修改事件或素材候选用 R10 停止，不查询外部事实、不调用卡片工具，也不自动 create。支持的 edit 再按运行指南“编辑继承”恢复有效来源，无法恢复用 R14 停止。
- **下一步：** 明确需要外部静态事实且已通过上述判断时先走步骤 1；可能由动态能力覆盖的内容不提前搜索。
  否则 create 或修改已有数据参数的 edit 进入步骤 2；纯视觉、文案和尺寸 edit 继承未修改候选，直接进入步骤 3，不重新查询概述或 schema。

### 1. 查询必要外部事实并告知

- **进入条件：** 步骤 0 已确认可继续，且需求明确依赖外部静态事实，包括用户明确引用的最近助手答案；已有相关结果直接复用。可能由动态能力覆盖的展示项先完成步骤 2～3 判断，剩余必要外部内容在步骤 5 处理。
- **来源与范围：** 按运行时可用的外部工具查询，并按运行指南“来源有效性”校验、清洗。纯静态普通创建先选择必要展示范围，不把全部检索详情默认纳入；前文答案只取用户明确引用的当前会话最近一条实际助手自然语言回复。
- **用户回复：** 仅对采用且尚未告知的完整事实实际发送 R16W（WebSearch）或 R16（其它来源），不播报查询过程，也不重复已告知内容；必须先于 R01/R02。内部草稿、工具结果和请求参数不能代替告知。
- **下一步：** 本步只保留已校验事实，步骤 6 才回填请求。核心来源失败或不可校验用 R17 停止，次要失败按 R08C/R08E；前文答案为空、只有失败话术或无法安全提取时用 R05/R14。
  完成后 create 或已有数据参数修改进入步骤 2，纯视觉、文案和尺寸 edit 进入步骤 3。

### 2. 获取能力概述和数据定义

- **进入条件：** 每个 create，或修改已有数据参数的 edit；参数构造与检查按运行指南“工具契约与字段来源”执行。
- **用户回复：** 正常获取不播报；概述缺少核心动态数据或交互立即 R07 停止，次要缺失 R08C/R08E；改变主要用途的可用替代 R09 等待。静态事实待步骤 5 检查，不提前拒答。
- **概述调用示例：**

```text
{"functionName":"getWidgetCapabilityOverview","skillName":"harmony-card-generation-online","arguments":{"bundleName":"com.omega_w_0823.hmservice"}}
```

- **参数来源与返回检查：** 逐项匹配数据需求与交互效果：动态数据只选本轮可用 dataCapabilities，交互只选语义匹配的 eventCapabilities；不可用 ID 不加载 Schema。不用相近入口、历史结果或生成模型补齐功能。
- **数据定义调用示例：** 假设本轮概述确认 ViewWeather 可用且已选中；有数据候选才调用，无数据时跳过。

```text
{"functionName":"getDataCapabilitySchemas","skillName":"harmony-card-generation-online","arguments":{"bundleName":"com.omega_w_0823.hmservice","dataCapabilityIds":["ViewWeather"]}}
```

- **Schema 满足度与停止条件：** 复查必填参数、类型、输出字段及写入路径，外部事实不增加能力或字段。Schema 不支持核心动态数据用 R07；次要缺失移除，已调用核心来源失败用 R17，结构非法用 R14。可继续时进入步骤 3，缺业务值在那里澄清；无数据候选只跳过 schema 调用，仍进入步骤 3。

### 3. 规划候选与必要追问

- **进入条件：** create 和已有数据参数修改已取得本轮概述及所需 schema；纯视觉、文案和尺寸 edit 已恢复有效来源及继承候选，无需本轮概述或 schema。按运行指南“满足度、尺寸与候选构造”规划。
- **用户回复：** 必要业务信息缺失或有歧义时，先用 R05 追问一个最小必要问题并等待，不得自行推测；
  例如个人事件倒计时缺少日期时先问日期。澄清前不进入权限、R01/R02 或生成，已明确的信息不重复询问。
  次要缺失用 R08C/R08E 告知后继续；主要用途替代用 R09 等待；必须包含的核心内容不可用用 R07 停止。
- **工具调用示例：** 本步不调用业务工具；不能为缺失参数猜值，也不在此发起新的外部调用。当前任务既有外部来源结果
  或已发现来源可补齐客观事实且不影响能力集合选择时暂留待补；权限阶段后先处理已有结果，不足再补查。
- **来源与候选：** create 和已有数据参数修改按本轮结果核对数据字段、事件目标及参数、依赖和素材，页面入口不能冒充直接操作。事件完整复制 `actionTemplate`，只替换声明动态路径；已有数据参数修改保留原数据能力及写入路径，不替换事件或素材。纯视觉、文案和尺寸 edit 不重建未修改候选，按真实编辑链恢复权限集合。
  来源缺失的核心项停止，次要项移除，改变主要用途的替代等待确认；静态值仅来自用户明确陈述或已校验外部事实。
- **动态展示来源：** 本轮动态能力已覆盖的展示项，不再向 `userQuery` 追加同对象、同指标、同时间范围的外部静态值；填写 `candidateOutputFields` 时须选全用户所需展示字段，并保持对象与时间对应，不用外部文字补漏选字段。
- **使用提醒：** 从本轮实际采用能力的说明与完整定义中提取明确要求告知的使用前提或限制，如手动设置、连接方式、设备兼容条件及不满足时的影响；按运行指南“能力使用提醒”处理，不能只在内部记录。未采用能力的限制不播报。
- **尺寸：** 用户指定时必须显式传入 `size`，edit 未指定时继承原尺寸；create 未指定时按内容结构选满足核心需求的最小尺寸，并显式传入。
  **优先 2x2：** 一个核心及简短补充、两组各自完整的短信息，或紧凑内容与必要动作；同一对象的多个短字段可以合组，不等于多个分区。
  **选择 2x4：** 两个对象各需独立标题和完整正文、需要分栏呈现完整对比信息，或长文字、必要明细与动作难以在小卡共同承载。
  两个动作不必然选大卡：条目详情、符合条件的整卡点击或模板内嵌动作可复用内容区域，独立按钮则须与正文一起估算空间；不同目标不能合并。
  不只按字段数或点击能力数判断，也不为坚持小卡删核心要求。具体组件和容量由生成工具判断，不保证宽卡一定装得下；详见运行指南“筛选和尺寸预算”。
- **继续或停止：** 确定完整、去重的数据能力集合后进入步骤 4；技术字段缺口用 R14，不能问用户内部字段。

### 4. 检查数据权限

- **权限集合：** create 取最终数据候选；已有数据参数修改取调整后的完整列表；纯视觉、文案和尺寸 edit 从有效结果或真实编辑链恢复。去重后为空则跳过权限调用、进入步骤 5；非空必须调用并等待结果，期间不改变集合。
- **调用示例：** 检查本轮实际保留的数据能力，多能力时传完整去重集合。

```text
{"functionName":"RequestDataPermission","skillName":"harmony-card-generation-online","arguments":{"bundleName":"com.omega_w_0823.hmservice","dataCapabilityIds":["ViewWeather"]}}
```

| 实际结果 | 下一步 |
| --- | --- |
| 正常返回 result.errorMessage 精确为“不能传入空的dataCapabilityIds，请重新调用工具” | 复用已确定的非空集合重试一次；取得合法结果后按下列正常结果判断，否则 R14 停止，不适用异常放行 |
| 正常结果结构合法，总权限为 true、无明确拒绝且无待授权项 | 静默进入步骤 5 |
| 正常结果明确拒绝，或合法待授权明细非空 | 按 R11/R12/R13 告知并停止，不进入来源或生成 |
| 正常结果缺必要字段、类型或结构非法 | R14 停止 |
| 首次调用工具不可用、invoke 抛错、超时或执行失败，且没有正常权限结果 | 按既有策略静默进入步骤 5，不伪造授权成功；已有正常拒绝结果时不适用 |

字段细则按运行指南“权限结果判定”执行；不播报权限检查或重试进度。能力使用提醒仍须按步骤 7 复核，权限通过不证明使用前提已满足。

### 5. 检查已有外部来源结果，按需补查

- **进入条件：** 步骤 4 已允许继续或因无数据跳过；不需要外部事实时直接进入步骤 7，已有采用事实或仍需补齐时执行本步。
- **已有结果与补查：** 纯静态普通创建仅补查选定展示范围内缺失的必要事实。检查当前任务轨迹中的 WebSearch、其它工具或 Skill 结果，包括 Skill 加载前的结果；步骤 1 已处理的内容不重复搜索。只为缺失事实调用运行时可发现的来源，权限阶段后串行补查，不增加固定工具依赖、不播报进度。
- **回复与来源：** 采用的新事实校验后立即实际发送 R16/R16W，再进入步骤 6；已告知事实不重复发送。来源须真实、相关且可追溯，参数按来源工具的运行时 schema 构造。
- **继续或停止：** 没有可采用的已有结果且无需补查时进入步骤 7；有结果进入步骤 6；
  必要事实不可获取时按核心/次要内容使用 R17 或 R08C/R08E，不能模拟成功或编造来源。

### 6. 使用并填入外部事实
- **进入条件：** 已有可采用的外部结果，或步骤 1/5 的查询已返回；按运行指南检查最终使用关系。
  这是外部事实进入卡片请求的唯一阶段。
- **参数与事实：** 纯静态普通创建先按运行指南选择展示范围，保留用户明确要求；已告知的全部相关信息不必全部采用。将有效需求与经来源选择后采用的静态展示事实按来源顺序完整拼接到 `userQuery` 固定标题段落，不总结、压缩、翻译、重排或改写。匹配现有 Schema 或 dynamicArguments 的事实可回填业务参数；仅用于参数补全的事实不自动进入展示段落，动态能力已覆盖的对应静态读数不追加。无静态展示事实时不加标题。
- **用户回复：** 采用事实须已在步骤 1/5 告知；尚未告知的先按对应回复动作发送，再回填请求，不重复已告知内容。
- **完整度：** 仅复制本轮已校验完整清单，不能从回复摘要重建；无法恢复则停止。edit 不继承的是请求中的旧外部事实段落，原卡未修改内容仍按有效来源保留；细则见运行指南“userQuery 中的外部事实”。
- **继续或停止：** 事实过时或不足回步骤 5；核心无合法来源 R07，已调用核心来源失败或不可校验 R17；次要失败复核可继续才 R08C/R08E。补查先实际回复再回填，完成后进入步骤 7；binding 变化补做步骤 4，不重复已完成来源或回复。

### 7. 完整请求校验并调用生成

- **进入条件：** 能力、参数、权限和来源处理完成；请求按运行指南“生成工具传参核对”构造，edit 同时遵守“编辑请求”。
- **edit 参数门禁：** 用户明确要求修改且工具声明了对应参数时，本轮必须显式传入修改值，不得只写在 `userQuery` 或依赖来源继承。尺寸 edit 必须传本轮 `size`。
- **数据与交互门禁：** 动态数据和交互有本轮合法绑定与候选，或属于纯视觉、文案和尺寸 edit 的有效继承；静态事实来自用户或本轮已校验来源。必要动作的目标、参数和依赖完整，次要缺失已从有效需求及候选移除；edit 不得借此删除原有数据。核心不支持 R07，次要移除 R08C/R08E，主要用途替代 R09 等待，技术缺口 R14；未通过不发送 R01/R02、不生成。
- **纯静态创建检查：** 包括用户直接提供的资料在内，确认已选择必要展示事实、保留完整对象名称与条件，并保留全部显式约束；有效需求不再重复附加整份原始资料。用户要求完整或原文的资料继续保留，不为提高成功率静默删减。动态、混合动态和 edit 不套用此检查。
- **外部事实回复检查：** 采用且尚未告知的外部事实须先按步骤 1/5 实际发送 R16W/R16，不以草稿或入参代替；用户直接提供的固定内容无需另行复述。
- **生成传参门禁：** 外层 `arguments` 和 `candidateDataBindings[].arguments` 必须为 JSON 对象，不整体序列化或手工转义。创建或修改已有数据参数时，动态展示须传完整绑定、Schema 必填参数及用户指定值，无参用 `{}`；纯视觉、文案和尺寸 edit 可省略未修改列表并继承，不能只凭 query 另造动态内容。`writeResultTo` 位于不冲突的 `/data/...`，输出投影取 Schema 叶子路径，数组下标对应本轮对象和时间。
  事件项为 `{capabilityId, action}`，完整复制模板到 `action`，仅替换声明动态路径，保留固定字段及空字符串；不传 `actionTemplate`、`dynamicArguments` 定义。只用运行时声明字段；create 标题/说明非空，纯视觉 edit 可合法继承，不强制重传未修改列表。
  列表动作必须将模板中的 `i` 替换为真实目标下标，不默认填 `0` 或提交未替换的模板；不能夹带 Schema／模板定义。
  `dataCapabilityIds` 仅用于加载数据定义和权限检查；生成接口禁止传入它或 `eventCapabilityIds`，必须使用完整的 `candidateDataBindings`、`candidateEventCandidates`，不能仅传 ID 列表。
- **纯静态 create：** 无动态需求时 `candidateDataBindings:[]`，无必要合法动作或匹配素材时对应候选传 `[]`；不为填满卡片补动态数据、动作或素材。完整事实与展示要求放入 `userQuery`，不只写在标题、说明中；摘要与排版由生成工具处理。
- **必要告知：** 前序的拒答、权限引导、澄清、替代确认、次要缺失和采用事实均已实际处理；有待回答问题或停止条件时不调用。实际采用能力要求的使用前提或限制尚未告知时单独发送 R15；纯静态内容 create 单独发送 R21，仅快捷动作卡不适用。同一任务条件未变不重复，内部计划、参数或权限通过不能代替告知。
- **开始与调用：** 全部前置检查通过后，紧邻首次生成调用发送 create 的 R01 或 edit 的 R02，再串行调用工具。生成前停止不发送开始话术；等待最终结果后统一进入步骤 8。
- **create 示例：** 使用步骤 2～4 同一模拟计划；业务值来自用户和定义，create 不含 sourceArtifactUrl。

```text
{
  "functionName":"generateWidgetCardCompactDsl",
  "skillName":"harmony-card-generation-online",
  "arguments":{
    "bundleName":"com.omega_w_0823.hmservice",
    "userQuery":"做一张上海青浦今日天气卡片，显示温度和天气现象。",
    "title":"今日天气",
    "description":"青浦天气速览",
    "size":"2x2",
    "candidateDataBindings":[
      {"capabilityId":"ViewWeather","arguments":{"prefectureName":"上海市","districtName":"青浦区","forecastDays":1},
       "writeResultTo":"/data/weather","candidateOutputFields":["/current/temperatureText","/current/condition"]}
    ],
    "candidateEventCandidates":[],
    "candidateAssetIds":[]
  }
}
```

- **带事件的结构示例：** 仅当本轮概述确认对应天气事件及相同模板时使用；将模板的值放到 `action`，不把模板字段名一起复制。实际包名、事件值及引用按本轮返回构造。

```json
{
  "functionName": "generateWidgetCardCompactDsl",
  "skillName": "harmony-card-generation-online",
  "arguments": {
    "bundleName": "com.omega_w_0823.hmservice",
    "userQuery": "显示明天的天气和星期，点击查看同一城市天气详情",
    "title": "明日天气",
    "description": "明日出行速览",
    "size": "2x2",
    "candidateDataBindings": [{
      "capabilityId": "ViewWeather",
      "arguments": {"forecastDays": 1},
      "writeResultTo": "/data/weather",
      "candidateOutputFields": ["/daily/0/weekday", "/daily/0/condition"]
    }],
    "candidateEventCandidates": [{
      "capabilityId": "event.open.weather",
      "action": {
        "call": "clickToDeeplink",
        "args": {
          "intentName": "Weather_CityCode",
          "bundleName": "",
          "abilityName": "",
          "uri": "{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' + ${/data/weather/location/cityCode} }}"
        }
      }
    }],
    "candidateAssetIds": []
  }
}
```

- **尺寸 edit 示例：** 多轮用户明确要求改变已有卡片尺寸时，仍使用 edit，并在生成工具入参中显式传入本轮目标 `size`；
  不能只在 `userQuery` 中描述尺寸而省略字段。

```text
{
  "functionName":"generateWidgetCardCompactDsl",
  "skillName":"harmony-card-generation-online",
  "arguments":{
    "bundleName":"com.omega_w_0823.hmservice",
    "userQuery":"把已有卡片改成 2x4 尺寸。",
    "size":"2x4",
    "sourceArtifactUrl":"<本会话目标卡片最近有效工具结果的原始 artifactUrl>"
  }
}
```

- 联调时可参考[回归示例](references/examples.md)中的 edit 入参与拒绝场景；实际执行时 sourceArtifactUrl 必须取真实最近有效结果。

### 8. 判定卡片结果，按宿主规则反馈

- **读取结果：** 只按当前工具返回和运行时契约判断，不从 message 或对话文本提取 URL。失败可返回仅含 message、retryable、requiredActions、agentInstruction、issues 的简版对象，读取顶层控制及 issues 的 path、message，不要求 status 或 error.details；兼容旧版失败结果。

| 实际结果 | 处理 |
| --- | --- |
| success/degraded 且有合法新 URL | 立即结束生成调用并更新内部编辑来源；完整成功用 R18C/R18E，degraded 或已知缺失用对应 R18 + R19，无缺失明细按回复规范说明 |
| success/degraded 缺合法新 URL，或 edit 返回原 URL | R14 结束，保留旧来源，不为补 URL 重调 |
| unsupported | R07 结束，不重试、不更新来源 |
| needs_clarification / unchanged（仅 edit） | 分别用 R05 等待 / R20 结束，不重试、不更新来源 |
| 结构合法的简版错误对象或旧版 failed | 保留旧来源，仅按下述条件判断是否修正重试；不重试时按反馈的停止或澄清指引选择固定话术，无有效指引则 R14 结束 |
| 非法结果、工具不可用、invoke 抛错、超时或调用状态不确定 | R14 结束，不重试、不更新来源 |

- **重试条件：** 按运行指南“生成调用次数与失败重试”执行。仅当实际反馈 retryable 为 true、未要求 STOP/NOTIFY_USER，且有新的可执行修正依据时继续；相同错误再次出现即停止，不从笼统错误猜修法。含首次最多 3 次生成调用，串行等待，不重发 R01/R02。
- **修正路径：** 保留本轮 create/edit、原有效来源和用户指定尺寸，修正后回步骤 7；数据集合或 binding 变化先回步骤 4。create 的动态输入缺口还须按指南核对本轮能力、按需加载定义并补齐绑定或字段，缺口说明不证明能力可用或已获权限。核心不支持、缺必要业务值或权限问题仍按原停止／澄清流程处理，edit 不借此增删数据或转创建。
- **回复与完成：** 生成后话术仅在宿主允许文本回复时发送，无文本机会仍按真实结果处理，不提前编造成功、失败或实际省略。成功后不为美化、补内容或补回复重调，不透传业务 message，不下载、校验、修改或上传产物；URL 仅留在内部工具轨迹。


## 安全红线

- 你只负责需求分流、候选规划、权限、外部事实、工具调用和回复。微服务负责最终产物生成、校验、修复及上传，生成工具返回业务状态和产物信息。任何异常情况下，你都不得生成、修改、校验 DSL/CardSpec 或替代 artifact。
- 不得伪造数据能力、Schema 字段、事件、素材、权限结果、业务事实或生成结果；核心数据没有合法来源时按对应固定话术停止生成。
- 权限按步骤 4 和运行指南“权限结果判定”执行，不绕过停止条件，不伪造授权结果。
- 不得向用户暴露工具字段、内部信息或产物 URL。
- 生成工具及其内部模型不能作为搜索、查询或补齐业务数据的来源。

## 与人协作

- 用户可见回复只使用[固定回复规范](references/user-replies.md)中的模板和合法组合；不追加示例、替代建议或自由文本。
