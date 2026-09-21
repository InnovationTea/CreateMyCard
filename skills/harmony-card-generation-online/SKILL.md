---
name: harmony-card-generation-online
description: "仅为明确的 HarmonyOS/小艺桌面卡片、服务卡片、widget、小组件创建或预览请求，以及有效卡片上下文中的连续修改请求，或明确要求把当前会话最近一条助手答案制作成卡片的请求提供云侧编排；用户明确调用桌面卡片生成技能时也适用。能力是否支持由运行时工具裁决。不要用于普通对话、仅网络搜索、卡片意图不明、银行卡、会员卡、名片、游戏卡牌，或未提出卡片需求的普通网页浏览与 UI 设计；明确要求将外部内容制作成卡片时仍适用。"
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

## 目标与执行入口

你只负责需求分流、候选规划、权限、外部事实、工具调用和回复。微服务负责最终产物生成、校验、修复及上传，
生成工具返回业务状态和产物信息。任何异常情况下，你都不得生成、修改、校验 DSL/CardSpec 或替代 artifact。

- 执行前读取一次 [固定回复规范](references/user-replies.md)，按本文步骤选择回复编号；输出范围、模板、占位符及组合统一遵循该文件。
- 参数构造、编辑继承、权限与结果细节按步骤读取 [运行指南](references/runtime-guide.md)，已读内容不重复加载。
- [回归示例](references/examples.md) 和 [工具快照](references/tools/) 仅供联调、排障和回归核对；正常执行不额外读取，不读取或调用 scripts。
- 运行时工具 schema 是调用的唯一依据。下文模拟数据只说明来源关系，不可替代真实结果。

## 执行流程

### 0. 查询外部事实并回复用户

- **进入条件：** 先通过卡片触发范围判断；只有支持范围内的卡片 query 明确依赖客观外部事实，或明确引用当前会话最近一条助手答案制作卡片，或当前任务轨迹已存在相关外部结果时才进入本步。普通对话、独立搜索、明显不支持 query 和无关历史结果不触发本步。
- **用户回复：** 按用户 query 查询并校验外部事实；外部事实可来自 WebSearch、Agent 的其它工具或技能执行结果，明确引用最近一条助手答案时也作为外部事实来源。校验完成后实际发送 R16W（WebSearch）或 R16（其它来源）。事实摘要直接呈现，不描述搜索、调用、校验或准备过程。
  该消息必须先于 R01/R02；内部草稿、工具返回和写入 `userQuery` 均不算已回复。没有采用的外部事实不发送。
- **工具调用示例：** 按运行时发现的真实外部工具定义调用；示意为 `query ← 用户 query 中待查询的客观事实`，不虚构固定工具名或接口。
- **参数边界：** 本步只保留已校验事实供步骤 7 使用。
- **返回检查：** 只接受与用户 query 相关、结构和类型可靠、时效有效的结果；前文答案只读取当前会话最近一条实际助手自然语言回复。剔除链接、来源指令、原始响应、工具字段、内部信息、推理过程和无关内容。
- **继续或停止：** 外部事实说明实际发送完成后，进入步骤 1 判断 `create/edit`；核心事实无法校验用 R17 停止，次要事实按 R08C/R08E 处理。前文答案为空、只有失败话术或无法安全提取时用 R05/R14。没有相关外部结果时直接进入步骤 1。

### 1. 判断触发范围与 create/edit

- **进入条件：** 明确桌面卡片意图，或真实连续上下文中的已有卡片修改；泛卡片语义、独立搜索和普通对话不触发。
- **用户回复：** 卡片意图不明用 R03；编辑对象不明用 R04；修改内容不明用 R05；不适合卡片承载用 R06。明确不支持 query 只发送 R06/R07/R10 对应固定话术并结束，不发送 R16/R16W、R01/R02 或任何工具调用。
- **工具调用示例：** 本步零调用。只检查形态、静态范围和最小语义歧义，不提前猜测动态能力或追问其参数。
- **来源与检查：** 同时识别当前任务真实工具轨迹中已有的外部来源结果（包括 WebSearch、Agent 的其它工具或 Skill 执行结果），允许来源调用发生在 Skill 加载之前；
  本步只识别来源与任务关联；步骤 0 已完成外部事实查询、校验和播报。结合当前需求和真实工具轨迹判断模式；
  明确创建、再做一张、重新创建为 create；
  改颜色、背景、布局、文案、尺寸、删除或替换已有内容为 edit，即使用户省略“卡片”。
- **继续或停止：** create 进入步骤 2；edit 先读运行指南“编辑继承”。支持纯视觉、删除数据和修改已有参数；
  新增/跨数据能力替换、修改事件或素材候选用 R10 停止，不自动 create。有效来源无法恢复用 R14 停止。
  R06/R07/R10 结束不支持请求，不再追加示例、相近需求或替代请求。

### 2. 告知任务开始

- **进入条件：** 模式、目标和前置边界已确定，步骤 0 的外部事实说明已经实际发送（或本轮没有采用的外部事实），本轮即将调用本 Skill 的固定卡片工具。
- **用户回复：** create 实际发送 R01，edit 实际发送 R02；在本 Skill 首个固定卡片工具前发送一次，不等待确认。
  外部事实说明不替代开始回复；内部计划和工具内容不能代替此消息。
- **工具调用示例：** 本步无工具调用，发送后立即执行本轮第一个必要工具。
- **来源与检查：** 回复只表达开始处理，不承诺数据支持或生成成功；已确定追问或结束时不发送。
- **继续或停止：** create/数据类 edit 进入步骤 3；纯视觉 edit 跳过概述/schema，按继承数据进入步骤 5。
  不逐个播报能力、schema、权限或生成工具进度。

### 3. 获取能力概述和数据定义

- **进入条件：** 每个 create，或删除数据/修改参数的 edit；先读运行指南“工具契约与字段来源”。
- **用户回复：** 正常获取过程不新增话术；核心缺失立即 R07 并停止，次要缺失 R08C/R08E，
  改变主要用途的替代用 R09 并等待，不为了展示示例而继续调用。
- **概述调用示例：**

```text
invoke(functionName:"getWidgetCapabilityOverview", arguments:{
  bundleName:"com.omega_w_0823.hmservice"
},"skillName":"harmony-card-generation-online")
```

- **参数来源与返回检查：** 只从本轮合法 dataCapabilities 选动态数据绑定；不可用 ID 不加载 schema。外部静态事实可独立形成展示内容，不因缺少对应动态能力而判定核心缺失。
  从同轮概述选事件和素材，取得概述后立即判断核心目标，失败用 R14，不以历史概述补齐。
- **数据定义调用示例：** 假设本轮概述确认 ViewWeather 可用且已选中；有数据候选才调用，无数据时跳过。

```text
invoke(functionName:"getDataCapabilitySchemas", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  dataCapabilityIds:["ViewWeather"]
},"skillName":"harmony-card-generation-online")
```

- **贯穿示例的模拟返回摘要：** 假设当前完整定义确认 ViewWeather，允许 prefectureName（字符串、必填）、
  districtName（可选字符串）及 forecastDays（整数），默认路径 /data/weather，输出含 /current/temperatureText。
  用户明确要求上海青浦今日天气，因此值分别来自用户输入和本轮定义：上海市、青浦区、1。
  概述无相关点击动作和素材，候选事件/素材为空。这里仅是模拟已验证字段摘要，不替代工具完整返回。
- **继续或停止：** 移除 missingCapabilityIds 后再判断核心目标；最后一个核心消失则 R07 停止，
  非法结果 R14 停止，其余进入步骤 4。

### 4. 规划候选与必要追问

- **进入条件：** 已得到本轮合法概述和所需 schema；读取运行指南“满足度、尺寸与候选构造”。
- **用户回复：** 用户偏好、有歧义目标、必要动作对象缺失时用 R05，只问一个必要问题并等待；
  次要缺失用 R08C/R08E 告知后继续；主要用途替代用 R09 等待；必须包含的核心内容不可用用 R07 停止。
- **工具调用示例：** 本步无调用；不能为缺失参数猜值，也不在此发起新的外部调用。当前任务既有外部来源结果
  或已发现来源可补齐客观事实且不影响能力集合选择时暂留待补；权限阶段后先处理已有结果，不足再补查。
- **来源与检查：** 数据 ID/参数名/类型/路径来自本轮定义，事件完整复制 actionTemplate，仅替换声明的动态参数，素材只传 ID。
  素材候选按返回的 `description` 做主题精确匹配：只有描述明确覆盖用户主业务、且注明可用于本规则的彩色 PNG，才最多选择 1 个 `asset.*` PNG 候选；不因有日期、时间、按钮或任意状态字段而泛化匹配，也不为凑视觉效果传候选。该类 PNG 优先由微服务在 2x2 单业务的标准 CardHeader 右上角以现有 20vp 图标位使用，其他尺寸、正文、按钮、环中心和双业务分区仍不主动传此类候选；布局与最终是否采用仍由微服务裁决。
  对于 outputSchema 中的 array 字段，字段投影必须使用明确的非负整数下标；
  同一数组的多个展示项可点击时，各事件动态参数必须引用对应展示项下标。
  具体路径、相对 writeResultTo 的关系及 actionTemplate 动态参数规则按运行指南执行。
  静态业务值可来自用户输入或已校验外部事实。外部事实仅写入有效 userQuery 或现有业务参数；有效标题和说明只表达保留需求。
- **尺寸：** 用户指定优先；否则从 2x2 开始，包含数据且至少两个点击能力时建议 2x4。按运行指南执行内容预算，
  不为填满版面添加无关能力。
- **继续或停止：** 确定完整、去重的数据能力集合后进入步骤 5；技术字段缺口用 R14，不能问用户内部字段。

### 5. 检查数据权限

- **进入条件：** 本轮最终数据集合已确定；读取运行指南“权限结果判定”。create 取最终候选，
  数据类 edit 取替换后的完整列表，纯视觉 edit 从真实有效编辑链恢复继承集合。
- **用户回复：** 正常通过不播报；拒绝按明细使用 R11/R12 或无明细 R13；非法结果 R14。invoke 级失败静默继续。
- **调用示例：** 延续上述模拟计划，只检查实际保留的 ViewWeather；多能力时传完整去重集合。

```text
invoke(functionName:"RequestDataPermission", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  dataCapabilityIds:["ViewWeather"]
},"skillName":"harmony-card-generation-online")
```

- **返回检查：** 正常结果必须 stateOfPermission:true、没有任何 authorized:false、nonAuthStatus 缺失或 []，
  且所有结构/类型合法。模拟通过结果为 {"result":{"stateOfPermission":true,"nonAuthStatus":[]}}。
  非空待授权明细也阻断；字段缺失或非法不属于 invoke 失败。
- **继续或停止：** 明确通过或本次 invoke 级失败才进入步骤 6；集合为空跳过此工具，不传空数组。
  invoke 异常只限工具不可用、抛错、超时、传输失败或工具层失败且无正常权限结果，不重试、不伪造成功。

### 6. 检查已有外部来源结果，按需补查

- **进入条件：** 权限通过、invoke 级失败默认放行，或没有数据无需权限；本轮需求需要外部事实。
- **已有结果：** 先检查步骤 0 识别的当前任务真实外部来源结果，包括 WebSearch、其它工具或 Skill 的结果；即使来源调用发生在 Skill 加载前也必须处理。
  步骤 0 已处理的已有内容不重复搜索；补查结果先校验并实际发送 R16/R16W，再进入步骤 7 使用和填入，不发送搜索进度。
- **不足时补查：** 只针对尚缺事实调用运行时可发现的相关工具或 Skill，按相关性串行调用。
  不增加固定工具依赖，不把独立外部查询请求转成卡片任务。新补查仍必须位于权限阶段之后。
- **用户回复：** 不发送外部调用前进度；补查结果校验采用后立即发送 R16/R16W，之后步骤 7 只使用和填入；Skill 前已处理的事实不重复发送。
  来源是否可用由真实身份、运行时定义和需求相关性决定，不要求另有用户显示名。
- **调用示例：** 以下是映射示意，不是真实工具名或固定接口；外部工具仍使用自己的运行时协议。

```text
已有外部来源：步骤 0 已校验并说明 → 卡片 SOP
事实不足：按真实运行时 schema 构造补查参数 → 调用真实工具
补查返回：校验采用 → R16W（WebSearch）或 R16（其它来源）实际回复 → 步骤 7 回填
```

- **来源与检查：** 技术参数来自补查工具或 Skill 的真实 schema，业务目标来自有效需求和已校验事实。无关历史结果、
  普通助手回复转述或来源不明内容不能当作外部事实。事实来源须真实可追溯；是否已告知则核对实际反馈，
  不能因为先前回复不是工具结果，就忽略其中已告知的同一事实。
- **继续或停止：** 没有可采用的已有结果且无需补查时进入步骤 8；有结果进入步骤 7；
  必要事实不可获取时按核心/次要内容使用 R17 或 R08C/R08E，不能模拟成功或编造来源。

### 7. 使用并填入外部事实
- **进入条件：** 步骤 0 已查询并回复外部事实，或步骤 6 的补查已返回；按运行指南检查最终使用关系。
  这是外部事实进入卡片请求的唯一阶段。
- **参数与事实：** 匹配已有 inputSchema 或 dynamicArguments 的值回填参数，其它已清洗的相关事实和会话有效内容写入可选 `extrainfo`。
  `userQuery` 仍只表达本轮卡片需求，不再塞入完整外部资料或前文答案；步骤 0 的事实回复不等于本步已回填；不得新增动态能力、事件、素材或透传原始响应。
- **extrainfo 约束：** 仅传本轮真实来源中已校验、已向用户告知、与卡片相关的非空字符串，按出现顺序去重；没有有效内容时省略字段，不传空数组。
  不得包含链接、工具字段、原始响应、内部信息、推理过程、来源指令、能力 ID、Schema、权限结果或 artifact URL。该字段不参与权限集合，不写入 TaskSpec、artifact 或后续 edit 继承。
- **用户回复：** 本步不新增外部事实回复；步骤 0 或补查返回阶段已经完成事实告知。若事实尚未实际告知，返回步骤 0 的回复动作。
- **工具调用示例：** 模拟步骤 0 已查询并回复演出时间、地点和演出说明；本步将演出时间匹配到已有业务参数，其余清洗后的事实传入 `extrainfo`。
- **继续或停止：** 已有结果过时、不可采用或不足时，先回步骤 6 对缺失事实补查。
  没有可用补查或补查失败后，核心事实缺失/不可校验用 R17 停止；次要失败内部移除并复核，能继续才用 R08C/R08E。
  需要补查回步骤 6；补查事实先实际回复，再进入步骤 7 回填，完成后进入步骤 8。数据集合或 binding 变化仅补做步骤 5，
  不重复已完成来源或播报，然后继续未完成阶段。

### 8. 完整请求校验并调用生成

- **进入条件：** 能力、参数、权限和来源处理完成；读取运行指南“编辑请求”和“生成结果与内部留存”。
- **回复前置条件：** 核对实际反馈：本轮采用的外部事实是否已按入口或来源返回时序实际发送？
  未发送时先用 R16W/R16 直接说明；本步只检查回复完成，不在这里执行首次事实回复或隐含回填。
- **用户回复：** 正常调用前不重复开始回复或播报工具步骤；仍需用户信息用 R05 等待，技术缺口用 R14 停止。
- **来源与检查：** 本轮 schema 必填值全部补齐且类型正确，模板固定字段未遗漏，路径不冲突；
  被移除内容不在 query、标题、说明或候选中。只传运行时声明字段，不提交待补全值。
- **create 示例：** 使用步骤 3～5 同一模拟计划；业务值来自用户和定义，create 不含 sourceArtifactUrl。

```text
invoke(functionName:"generateWidgetCardCompactDsl", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  userQuery:"做一张上海青浦今日天气卡片。",
  extrainfo:["今日上海市青浦区适合穿着短袖"],
  title:"今日天气",
  description:"青浦天气速览",
  size:"2x2",
  candidateDataBindings:[
    {"capabilityId":"ViewWeather","arguments":{"prefectureName":"上海市","districtName":"青浦区","forecastDays":1},
     "writeResultTo":"/data/weather","candidateOutputFields":["/current/temperatureText"]}
  ],
  candidateEventCandidates:[],
  candidateAssetIds:[]
},"skillName":"harmony-card-generation-online")
```

- **纯视觉 edit 示例：** 假设上一调用真实成功结果给出来源；以下 sourceArtifactUrl 的字符串是教学占位符，
  执行时必须整体替换为最近有效业务结果的原始 URL，不能提交占位符。它只在内部参数中出现，不向用户回复。

```text
invoke(functionName:"generateWidgetCardCompactDsl", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  userQuery:"把背景改成蓝色。",
  sourceArtifactUrl:"<本会话目标卡片最近有效工具结果的原始 artifactUrl>"
},"skillName":"harmony-card-generation-online")
```

- **数据参数替换 edit 示例：** 同一天气卡片中用户明确改成北京市天气；
  重新获取概述/schema、校验完整列表并检查权限后调用。城市变化时删除旧区县，不能把青浦区保留到北京。

```text
invoke(functionName:"generateWidgetCardCompactDsl", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  userQuery:"将已有天气改为北京市今日天气。",
  sourceArtifactUrl:"<本会话目标卡片最近有效工具结果的原始 artifactUrl>",
  candidateDataBindings:[
    {"capabilityId":"ViewWeather","arguments":{"prefectureName":"北京市","forecastDays":1},
     "writeResultTo":"/data/weather","candidateOutputFields":["/current/temperatureText"]}
  ]
},"skillName":"harmony-card-generation-online")
```

- **删除全部数据 edit 示例：** 此例源卡片只有天气，用户要求移除动态天气并改为静态文字；
  刷新概述后无需调用空 schema 或空权限请求，仍为 edit。

```text
invoke(functionName:"generateWidgetCardCompactDsl", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  userQuery:"移除动态天气，改为只显示文字：今天也要有好心情。",
  sourceArtifactUrl:"<本会话目标卡片最近有效工具结果的原始 artifactUrl>",
  candidateDataBindings:[]
},"skillName":"harmony-card-generation-online")
```

- **继续或停止：** 正常结果进入步骤 9；生成工具不可用或调用失败用 R14 停止，不重试、不本地生成替代产物。

### 9. 判定并反馈卡片结果

- **进入条件：** 当前生成工具返回；结果只按当前运行时 schema 直接读取，不从 message 或对话文本找 URL。
- **用户回复：** 完整成功用 R18C/R18E；degraded 或已知缺失的 success 用 R18C/R18E + 对应 R19；
  unsupported 用 R07；failed、非法结果、无合法新 URL 用 R14。应发送的结果回复必须实际发送，不能只准备草稿。
- **工具调用示例：** 本步零调用，只处理当前返回的业务结果并组织结果回复；不追加下载、校验或上传步骤。
- **来源与返回检查：** 仅 success/degraded 且带当前业务 payload 的合法新 URL 才形成有效节点；
  edit 返回来源 URL 视为失败。候选和来源事实不代表界面实际采用，不透传业务 message。
- **留存与完成：** 有效 URL 只在内部工具轨迹保存为后续 edit 来源；失败或非法结果不改变旧来源。
  执行固定回复规范的发送前检查。结果处理完且应发送的回复已实际发送才完成本轮；开始回复和事实说明不替代尚需反馈的卡片结果。


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
- **description**: 生成极简协议版本的鸿蒙卡片
- **参数**: {"type":"object","properties":{"candidateEventCandidates":{"type":"Array","description":"候选点击事件列表；事件 action 只能来自能力概述返回的事件能力说明","required":[],"properties":{"ArrayItem":{"type":"Object","description":"事件 action"}}},"description":{"type":"String","description":"建议写入最终 CardSpec 的静态短概述，尽量不超过 12 个字"},"candidateAssetIds":{"type":"Array<String>","description":"候选素材 ID 列表","required":[],"properties":{"ArrayItem":{"type":"String","description":"候选素材 ID"}}},"userQuery":{"type":"String","description":"能力裁决后的本轮有效卡片需求；调整后生成时不得保留已移除或未经确认替代的内容"},"extrainfo":{"type":"Array<String>","description":"本轮已清洗、已告知且与卡片相关的外部事实和会话有效上下文；没有内容时省略，不进入 TaskSpec 或 artifact"},"candidateDataBindings":{"type":"Array","description":"已通过能力概述裁决的候选数据能力调用列表","required":[],"properties":{"ArrayItem":{"type":"Object","description":"候选数据能力","required":[],"properties":{"writeResultTo":{"type":"String","description":"结果写入路径"},"arguments":{"type":"Object","description":"参数"},"capabilityId":{"type":"String","description":"能力ID"},"candidateOutputFields":{"type":"Array<String>","description":"可选候选展示字段 JSON Pointer；必须能从对应能力 outputSchema 推导","required":[],"properties":{"ArrayItem":{"type":"String","description":"可选候选展示字段 JSON Pointer"}}}}}}},"title":{"type":"String","description":"建议写入最终 CardSpec 的静态短标题，尽量不超过 8 个字"},"size":{"type":"String","description":"你建议的尺寸"},"sourceArtifactUrl":{"type":"String","description":"上一版完整 artifact 的真实 URL；缺失表示首次生成，合法非空值表示编辑"}},"required":["userQuery"]}

## 工具调用

依赖 frontmatter 声明的三个微服务工具和一个端工具。使用统一调用格式；
**注意**：要求 `arguments` 是合法 JSON 值；`skillName` 固定为 `harmony-card-generation-online`。

```text
invoke(functionName:"<toolName>", arguments:{bundleName:"com.omega_w_0823.hmservice", ...},"skillName":"harmony-card-generation-online")
```
