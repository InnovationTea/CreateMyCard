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
- **description**: 获取特定场景的数据权限能力
- **参数**: {"type":"object","properties":{"dataCapabilityIds":{"type":"Array<String>","description":"需要加载完整 schema 的数据能力 ID 列表，至少 1 个。","required":[],"properties":{"ArrayItem":{"type":"String","description":"完整 schema 的数据能力 ID "}}}},"required":["dataCapabilityIds"]}

### Function: generateWidgetCardCompactDsl
- **toolName**: generateWidgetCardCompactDsl
- **description**: 生成极简协议版本的鸿蒙卡片
- **参数**: {"properties":{"candidateEventCandidates":{"type":"Array","description":"候选点击事件对象数组，每项仅含 capabilityId 和 action；将概述的 actionTemplate 值复制到 action，不提交 actionTemplate 或 dynamicArguments 定义。","required":[],"properties":{"ArrayItem":{"type":"Object","description":"来自本轮概述的事件候选","required":["capabilityId","action"],"additionalProperties":false,"properties":{"capabilityId":{"type":"String","description":"本轮事件概述 ID"},"action":{"type":"Object","description":"完整复制对应模板的值，只替换声明的动态参数","required":["call","args"],"additionalProperties":false,"properties":{"call":{"type":"String","description":"模板原始调用类型，不填事件 ID"},"args":{"type":"Object","description":"模板完整参数对象，保留固定值与空字符串，禁止序列化成字符串","additionalProperties":true}}}}}}},"description":{"type":"String","description":"建议写入最终 CardSpec 的静态短概述，尽量不超过 12 个字；新建必填非空，编辑未修改时省略并继承"},"candidateAssetIds":{"type":"Array<String>","description":"候选素材 ID 列表","required":[],"properties":{"ArrayItem":{"type":"String","description":"候选素材 ID"}}},"userQuery":{"type":"String","description":"能力裁决后的本轮有效卡片需求；有外部事实时在后方追加固定标题‘本轮卡片静态内容（用作展示的外部事实）：’及完整事实；调整后生成时不得保留已移除或未经确认替代的内容"},"candidateDataBindings":{"type":"Array","description":"已通过能力概述裁决的候选数据能力调用列表","required":[],"properties":{"ArrayItem":{"type":"Object","description":"候选数据能力","required":["capabilityId","arguments","writeResultTo"],"properties":{"writeResultTo":{"type":"String","description":"结果写入路径"},"arguments":{"type":"Object","description":"符合本轮 inputSchema 的 JSON 对象；无参用 {}，禁止 JSON 字符串、数组或 null","additionalProperties":true},"capabilityId":{"type":"String","description":"能力ID"},"candidateOutputFields":{"type":"Array<String>","description":"可选候选展示字段 JSON Pointer；必须能从对应能力 outputSchema 推导","required":[],"properties":{"ArrayItem":{"type":"String","description":"可选候选展示字段 JSON Pointer"}}}},"additionalProperties":false}}},"title":{"type":"String","description":"建议写入最终 CardSpec 的静态短标题，尽量不超过 8 个字；新建必填非空，编辑未修改时省略并继承"},"size":{"type":"String","description":"用户指定尺寸时必须显式传入，优先于默认或建议；未指定按尺寸规则。","enum":["2x2","2x4"]},"sourceArtifactUrl":{"type":"String","description":"上一版完整 artifact 的真实 URL；缺失表示首次生成，合法非空值表示编辑"}},"required":["userQuery"],"type":"object","additionalProperties":false,"description":"业务参数必须直接为 JSON 对象，不调用 JSON.stringify、不手工转义整个对象；创建和编辑共用此入口。"}

### 工具调用

依赖 frontmatter 声明的三个微服务工具和一个端工具。使用统一调用格式；
**注意**：要求 `arguments` 直接为 JSON 对象，禁止整体序列化成字符串；`skillName` 固定为 `harmony-card-generation-online`。

```text
{"functionName":"<toolName>","arguments":{"bundleName":"com.omega_w_0823.hmservice","<业务字段>":"<本轮合法值>"},"skillName":"harmony-card-generation-online"}
```

## 经验攻略

- 创建新卡片、修改已有卡片和替代需求按步骤 1 的模式判断；能力、Schema、权限和数据来源均以本轮真实结果为准。

## 操作规程

执行前读取[固定回复规范](references/user-replies.md)；参数、能力边界、编辑继承及判定按步骤读取[运行指南](references/runtime-guide.md)，已读不重复加载。
生成接口调用后可能没有自然语言回复机会：所有调用前已确定且需要告知的拒答、引导、澄清、缺失、限制和事实，
必须在调用前按对应模板实际发送，不能留到步骤 8。需要回答时等待，需停止时不调用；不得提前宣称成功或推测生成结果。
[回归示例](references/examples.md)和[工具快照](references/tools/)仅供联调核对，正常执行不额外读取，不读取或调用 scripts。运行时 schema 是调用唯一依据，示例不替代真实结果。

### 0. 查询外部事实并回复用户

- **进入条件：** 先通过卡片触发范围判断；仅明确需要外部静态内容时进入，包括将最近助手答案或本轮已有外部结果制成固定内容卡片。可能由动态能力覆盖的展示项先按步骤 2～3 判断来源，剩余必要外部内容在步骤 5 处理；不因已有相关结果就提前采用。普通对话、独立搜索及明确不支持的请求不触发本步。
- **用户回复：** 按用户 query 查询并校验外部事实；外部事实可来自 WebSearch、Agent 的其它工具或技能执行结果，明确引用最近一条助手答案时也作为外部事实来源。仅对采用且尚未告知的完整事实实际发送 R16W（WebSearch）或 R16（其它来源），不重复已告知内容，不描述搜索、调用、校验或准备过程。
  该消息必须先于 R01/R02；内部草稿、工具返回和写入 `userQuery` 均不算已回复。没有采用的外部事实不发送。
- **工具调用示例：** 按运行时发现的真实外部工具定义调用；示意为 `query ← 用户 query 中待查询的客观事实`，不虚构固定工具名或接口。
- **参数边界：** 本步只保留已校验事实供步骤 6 使用；纯静态普通创建先选择展示范围，再告知采用事实，不把所有检索详情默认纳入。
- **返回检查：** 按运行指南“来源有效性”校验、清洗；前文答案仅取用户明确引用的当前会话最近一条实际助手自然语言回复。
- **继续或停止：** 采用的外部事实均已告知后，进入步骤 1 判断 `create/edit`；核心事实无法校验用 R17 停止，次要事实按 R08C/R08E 处理。前文答案为空、只有失败话术或无法安全提取时用 R05/R14。没有相关外部结果时直接进入步骤 1。

### 1. 判断触发范围与 create/edit

- **进入条件：** 用户提出创建或修改卡片的意图即触发，包括未说明卡片类型、平台或形态的请求；真实连续上下文中的已有卡片修改也触发。不得在触发阶段按卡片产品类型排除请求，具体能否支持由后续流程判断。普通讨论卡片或独立搜索且没有创建、修改意图时不触发。
- **用户回复：** 卡片意图不明用 R03；编辑对象不明用 R04；修改内容不明用 R05；不适合卡片承载用 R06。明确不支持 query 只发送 R06/R07/R10 对应固定话术并结束，不发送 R16/R16W、R01/R02 或任何工具调用。
- **工具调用示例：** 本步零调用。只检查形态、静态范围和最小语义歧义，不提前猜测动态能力或追问其参数。
- **来源与检查：** 结合当前需求和真实工具轨迹判断模式；外部事实按步骤 0 处理，不因来源早于 Skill 而遗漏；
  明确创建、再做一张、重新创建为 create；
  改颜色、背景、布局、文案、尺寸、删除或替换已有内容为 edit，即使用户省略“卡片”。
- **继续或停止：** create 进入步骤 2；edit 先读运行指南“编辑继承”。支持纯视觉和修改已有参数；
  数据集合增删（包括删除部分、删除全部数据或改为纯静态内容）、跨数据能力替换、修改事件或素材候选用 R10 停止，
  不进入后续工具调用、不发送 R01/R02、不自动 create；已有参数调整须保留相同数据能力及写入路径。
  有效来源无法恢复用 R14 停止。

### 2. 获取能力概述和数据定义

- **进入条件：** 每个 create，或修改已有数据参数的 edit；先读运行指南“工具契约与字段来源”。
- **用户回复：** 正常获取不播报；概述缺少核心动态数据或交互立即 R07 停止，次要缺失 R08C/R08E；改变主要用途的可用替代 R09 等待。静态事实待步骤 5 检查，不提前拒答。
- **概述调用示例：**

```text
invoke(functionName:"getWidgetCapabilityOverview", arguments:{
  bundleName:"com.omega_w_0823.hmservice"
},"skillName":"harmony-card-generation-online")
```

- **参数来源与返回检查：** 逐项匹配数据需求与交互效果：动态数据只选本轮可用 dataCapabilities，交互只选语义匹配的 eventCapabilities；不可用 ID 不加载 Schema。不用相近入口、历史结果或生成模型补齐功能。
- **数据定义调用示例：** 假设本轮概述确认 ViewWeather 可用且已选中；有数据候选才调用，无数据时跳过。

```text
invoke(functionName:"getDataCapabilitySchemas", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  dataCapabilityIds:["ViewWeather"]
},"skillName":"harmony-card-generation-online")
```

- **Schema 满足度与停止条件：** 复查必填参数、类型、输出字段及写入路径，外部事实不增加能力或字段。Schema 不支持核心动态数据用 R07；缺业务值进入步骤 3 补全，次要缺失移除，已调用核心来源失败用 R17，结构非法用 R14。

### 3. 规划候选与必要追问

- **进入条件：** 已得到本轮合法概述和所需 schema；读取运行指南“满足度、尺寸与候选构造”。
- **用户回复：** 必要业务信息缺失或有歧义时，先用 R05 追问一个最小必要问题并等待，不得自行推测；
  例如个人事件倒计时缺少日期时先问日期。澄清前不进入权限、R01/R02 或生成，已明确的信息不重复询问。
  次要缺失用 R08C/R08E 告知后继续；主要用途替代用 R09 等待；必须包含的核心内容不可用用 R07 停止。
- **工具调用示例：** 本步无调用；不能为缺失参数猜值，也不在此发起新的外部调用。当前任务既有外部来源结果
  或已发现来源可补齐客观事实且不影响能力集合选择时暂留待补；权限阶段后先处理已有结果，不足再补查。
- **来源与候选：** 按运行指南构造数据与交互来源清单；核对事件效果、目标、模板、动态参数类型/枚举及依赖字段，页面入口不能冒充直接操作。动态字段来自本轮 Schema，事件完整复制 `actionTemplate`，只替换声明路径；素材只传本轮 ID。
  来源缺失的核心项停止，次要项移除，改变主要用途的替代等待确认；静态值仅来自用户明确陈述或已校验外部事实。
- **动态展示来源：** 本轮动态能力已覆盖的展示项，不再向 `userQuery` 追加同对象、同指标、同时间范围的外部静态值；填写 `candidateOutputFields` 时须选全用户所需展示字段，并保持对象与时间对应，不用外部文字补漏选字段。
- **使用提醒：** 从本轮实际采用能力的说明与完整定义中提取明确要求告知的使用前提或限制，如手动设置、连接方式、设备兼容条件及不满足时的影响；按运行指南“能力使用提醒”处理，不能只在内部记录。未采用能力的限制不播报。
- **尺寸：** create/edit 必须显式传用户指定尺寸，禁止默认或建议覆盖；未指定时 edit 继承原尺寸，create 从 2x2 开始，包含数据且至少两个点击能力时建议 2x4。预算见运行指南，不添加无关能力。
- **继续或停止：** 确定完整、去重的数据能力集合后进入步骤 4；技术字段缺口用 R14，不能问用户内部字段。

### 4. 检查数据权限

- **进入条件：** 本轮最终数据集合已确定；读取运行指南“权限结果判定”。create 取最终候选，
  修改已有数据参数的 edit 取调整参数后的完整列表，保留相同数据能力及写入路径；纯视觉 edit 从真实有效编辑链恢复继承集合。
- **用户回复与返回判定：** 按运行指南“权限结果判定”处理。正常通过不播报；拒绝/待授权用 R11/R12/R13，非法结果用 R14；invoke 级失败按既有规则静默放行。
  此处“不播报”仅指权限检查进度；能力要求的使用提醒仍须发送，权限通过不代表手动设置或其它使用条件已经满足。
- **调用示例：** 延续上述模拟计划，只检查实际保留的 ViewWeather；多能力时传完整去重集合。

```text
invoke(functionName:"RequestDataPermission", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  dataCapabilityIds:["ViewWeather"]
},"skillName":"harmony-card-generation-online")
```

- **返回检查：** 仅正常且完整的授权结果可通过；拒绝、待授权或非法结构分别按运行指南处理。
  正常返回 `result.errorMessage` 且精确等于“不能传入空的dataCapabilityIds，请重新调用工具”时，使用同一非空 ID 集合重试一次；不从错误文本猜 ID，也不向用户播报重试。
- **重试示例：** 首次返回参数错误时，不发送用户回复，使用同一份完整集合再次调用：

```text
返回:{"result":{"errorMessage":"不能传入空的dataCapabilityIds，请重新调用工具"}}
重试 invoke(functionName:"RequestDataPermission", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  dataCapabilityIds:["ViewWeather"]
},"skillName":"harmony-card-generation-online")
```

- **继续或停止：** 最终 ID 集合为空时跳过权限工具，不传空数组。有效通过才进入步骤 5；重试后拒绝/待授权按原规则停止，重试失败或结果仍非法用 R14 并禁止后续工具调用。首次 invoke 级异常保留既有默认放行。

### 5. 检查已有外部来源结果，按需补查

- **进入条件：** 权限通过、invoke 级失败默认放行，或没有数据无需权限；本轮需求需要外部事实。
- **已有结果与补查：** 纯静态普通创建仅补查选定展示范围内缺失的必要事实。检查当前任务轨迹中的 WebSearch、其它工具或 Skill 结果，包括 Skill 加载前的结果；步骤 0 已处理的内容不重复搜索。只为缺失事实调用运行时可发现的来源，权限阶段后串行补查，不增加固定工具依赖、不播报进度。
- **回复与来源：** 采用的新事实校验后立即实际发送 R16/R16W，再进入步骤 6；已告知事实不重复发送。来源须真实、相关且可追溯，参数按来源工具的运行时 schema 构造。
- **继续或停止：** 没有可采用的已有结果且无需补查时进入步骤 7；有结果进入步骤 6；
  必要事实不可获取时按核心/次要内容使用 R17 或 R08C/R08E，不能模拟成功或编造来源。

### 6. 使用并填入外部事实
- **进入条件：** 步骤 0 已查询并回复外部事实，或步骤 5 的补查已返回；按运行指南检查最终使用关系。
  这是外部事实进入卡片请求的唯一阶段。
- **参数与事实：** 纯静态普通创建先按运行指南选择展示范围，保留用户明确要求；已告知的全部相关信息不必全部采用。将有效需求与经来源选择后采用的静态展示事实按来源顺序完整拼接到 `userQuery` 固定标题段落，不总结、压缩、翻译、重排或改写。匹配现有 Schema 或 dynamicArguments 的事实可回填业务参数；仅用于参数补全的事实不自动进入展示段落，动态能力已覆盖的对应静态读数不追加。无静态展示事实时不加标题。
- **用户回复：** 本步不新增外部事实回复；步骤 0 或补查返回阶段已经完成事实告知。若事实尚未实际告知，返回步骤 0 的回复动作。
- **完整度：** 仅复制本轮已校验完整清单，不能从回复摘要重建；无法恢复则停止。清洗和 edit 不继承规则见运行指南“userQuery 中的外部事实”。
- **继续或停止：** 事实过时或不足回步骤 5；核心无合法来源 R07，已调用核心来源失败或不可校验 R17；次要失败复核可继续才 R08C/R08E。补查先实际回复再回填，完成后进入步骤 7；binding 变化补做步骤 4，不重复已完成来源或回复。

### 7. 完整请求校验并调用生成

- **编辑结果分支：** needs_clarification 按 R05 等待，unchanged 按 R20 结束；两者都不重试、不更新编辑来源。语义编辑规则见运行指南。
- **进入条件：** 能力、参数、权限和来源处理完成；读取运行指南“编辑请求”和“生成结果与内部留存”。
- **edit 参数门禁：** 用户明确要求修改且工具声明了对应参数时，本轮必须显式传入修改值，不得只写在 `userQuery` 或依赖来源继承。尺寸 edit 必须传本轮 `size`。
- **数据与交互门禁：** 核心数据有本轮动态定义、已校验外部事实或用户值；核心交互有语义匹配事件、完整模板及合法目标/参数/依赖绑定。次要缺失已从 query、标题、说明和候选移除，静态段只复制完整事实。不得留待生成模型补齐数据或交互。核心不支持 R07，次要移除 R08C/R08E，主要用途替代 R09 等待，技术缺口 R14；未通过不发送 R01/R02、不生成。
- **纯静态创建检查：** 包括用户直接提供的资料在内，确认已选择必要展示事实、保留完整对象名称与条件，并保留全部显式约束；有效需求不再重复附加整份原始资料。用户要求完整或原文的资料继续保留，不为提高成功率静默删减。动态、混合动态和 edit 不套用此检查。
- **外部事实回复检查：** 采用且尚未告知的外部事实须先按步骤 0/5 实际发送 R16W/R16，不以草稿或入参代替；用户直接提供的固定内容无需另行复述。
- **生成传参门禁：** 外层 `arguments` 和 `candidateDataBindings[].arguments` 必须为 JSON 对象，禁止 JSON 字符串。动态展示须传对应 `capabilityId`、Schema 必填参数及用户指定值，无参用 `{}`；不得只在 query 描述。`writeResultTo` 位于不冲突的 `/data/...`，输出字段为 Schema 叶子路径，数组用实际数字下标。
  调用前核对：外层与数据参数均为对象，事件结构完整，未夹带 Schema／模板定义，数组下标对应本轮目标对象与时间；不手工转义整份参数。
  事件项为 `{capabilityId, action}`，完整复制模板到 `action`，仅替换声明动态路径，保留固定字段及空字符串；不传 `actionTemplate`、`dynamicArguments` 定义。只用运行时声明字段；create 标题/说明非空，纯视觉 edit 可合法继承，不强制重传未修改列表。
  列表动作必须将模板中的 `i` 替换为实际展示对象的数字下标；未明确目标时不能默认填 `0`，也不能提交未替换的模板。预检返回下标错误时按真实对象修正，不能原样重试。
  `dataCapabilityIds` 仅用于加载数据定义和权限检查；生成接口禁止传入它或 `eventCapabilityIds`，必须使用完整的 `candidateDataBindings`、`candidateEventCandidates`，不能仅传 ID 列表。
- **纯静态 create：** 无动态需求时 `candidateDataBindings:[]`，无必要合法动作或匹配素材时对应候选传 `[]`；不为填满卡片补动态数据、动作或素材。完整事实与展示要求放入 `userQuery`，不只写在标题、说明中；摘要与排版由生成工具处理。
- **使用提醒门禁：** 生成前逐项复核实际采用能力明确要求告知的前提或限制；尚未实际告知的先单独发送 R15，再发送 R01/R02。内部计划、工具参数、卡片文案或权限通过均不等于已告知；同一任务条件未变不重复，提醒不替代既有授权与支持范围门禁。
- **调用前告知检查：** 前序已确定的拒答、权限引导、必要澄清、替代确认、次要缺失和采用事实均已实际处理；存在待回答问题或停止条件时不调用。纯静态内容 create 在 R01 前单独发送 R21，说明不会自动更新；仅快捷动作卡不适用，同一任务条件未变不重复。已知提醒不得留到生成后；实际成功、生成中省略、工程失败及编辑结果只能等真实返回后处理。
- **用户回复：** 所有前置检查及必要使用提醒完成后，紧邻生成工具调用前实际发送 create 的 R01 或 edit 的 R02；仍需用户信息用 R05 等待，技术缺口用 R14 停止。生成前停止时不发送 R01/R02。
- **create 示例：** 使用步骤 2～4 同一模拟计划；业务值来自用户和定义，create 不含 sourceArtifactUrl。

```text
invoke(functionName:"generateWidgetCardCompactDsl", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  userQuery:"做一张上海青浦今日天气卡片，显示温度和天气现象。",
  title:"今日天气",
  description:"青浦天气速览",
  size:"2x2",
  candidateDataBindings:[
    {"capabilityId":"ViewWeather","arguments":{"prefectureName":"上海市","districtName":"青浦区","forecastDays":1},
     "writeResultTo":"/data/weather","candidateOutputFields":["/current/temperatureText","/current/condition"]}
  ],
  candidateEventCandidates:[],
  candidateAssetIds:[]
},"skillName":"harmony-card-generation-online")
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
invoke(functionName:"generateWidgetCardCompactDsl", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  userQuery:"把已有卡片改成 2x4 尺寸。",
  size:"2x4",
  sourceArtifactUrl:"<本会话目标卡片最近有效工具结果的原始 artifactUrl>"
},"skillName":"harmony-card-generation-online")
```

- 纯视觉修改、已有数据参数调整的 edit 入参及删除数据的拒绝场景见[回归示例](references/examples.md)；执行时 sourceArtifactUrl 必须取真实最近有效结果。

- **继续或停止：** 生成调用串行等待结果；仅 failed 按返回修正后重试，含首次最多 3 次，不重发 R01/R02；其它结果转步骤 8，异常用 R14，不本地生成。

### 8. 判定卡片结果，按宿主规则反馈

- **进入条件：** 只读取当前工具的运行时返回，不从 message 或对话文本提取 URL；结果映射按运行指南“生成结果与内部留存”。
- **用户回复：** 宿主允许生成后文本回复时，完整成功用 R18C/R18E；degraded 或已知缺失用对应 R18 + R19，无缺失明细按回复规范保守说明；unsupported 用 R07；failed 按指南重试或 R14，非法结果或无合法新 URL 用 R14。编辑 needs_clarification 用 R05，unchanged 用 R20。纯静态不更新提醒已在生成前发送，不在成功回复中重复。
- **宿主边界：** 不假设生成后一定可以回复；仍按真实返回处理状态、重试和编辑来源，不把无文本机会当作成功或已告知。仅生成后才能确定的失败、实际省略及编辑澄清不能前置编造；其用户可见交付需要宿主联调确认，不新增通道、不为补回复重调生成，也不强制生成后沉默。
- **来源与完成：** success/degraded 后禁止重调，即使 URL 非法；仅这两种状态且有合法新 URL 才更新内部编辑来源；edit 返回原 URL 不成立。不透传业务 message，不追加下载、校验或上传；没有新来源时保留旧来源。


## 安全红线

- 你只负责需求分流、候选规划、权限、外部事实、工具调用和回复。微服务负责最终产物生成、校验、修复及上传，生成工具返回业务状态和产物信息。任何异常情况下，你都不得生成、修改、校验 DSL/CardSpec 或替代 artifact。
- 不得伪造数据能力、Schema 字段、事件、素材、权限结果、业务事实或生成结果；核心数据没有合法来源时按对应固定话术停止生成。
- 是否允许生成统一按运行指南“权限结果判定”执行，包括首次 invoke 级异常的既定放行；正常返回明确拒绝、待授权或非法结果时停止，权限参数仅取本轮最终数据能力集合。
- 不得向用户暴露工具字段、内部信息或产物 URL。
- 生成工具及其内部模型不能作为搜索、查询或补齐业务数据的来源。

## 与人协作

- 用户意图或编辑对象不清楚时，按流程使用 R03/R04/R05 澄清；核心内容不支持、次要内容降级和改变主要用途的替代分别按 R06/R07/R10、R08C/R08E、R09 处理。
- 用户可见回复只使用[固定回复规范](references/user-replies.md)中的模板和合法组合；不追加示例、替代建议或自由文本。
