---
name: harmony-card-generation-online
description: "用于为小艺/HarmonyOS 创建或连续编辑可添加到桌面的服务卡片。仅当用户明确要求桌面卡片、服务卡片、widget、小组件、添加到桌面或修改已有桌面卡片时使用。动态数据范围仅限：天气与未来预报、日历日程与会议、指定日期倒计时、指定 App 今日使用时长、蓝牙耳机连接与电量、手机电池与充电健康、睡眠与健康运动。点击动作范围仅限：拨号、清理运行内存，打开指定设置页，打开天气城市页、闹钟、音乐歌单、运动健康锻炼或睡眠页、日程详情或会议，导航确切位置，以及开启或关闭省电模式。卡片组合需求的每项动态数据和动作都必须在上述范围内。不要用于普通对话、卡片意图不明、其他任意非华为自带 App 数据或操作、银行卡、会员卡、名片、游戏卡牌、普通网页/UI 等泛卡片语义。"
metadata:
  tools:
    - bundleName: "com.huawei.genui"
      toolName: "getWidgetCapabilityOverview"
    - bundleName: "com.huawei.genui"
      toolName: "getDataCapabilitySchemas"
    - bundleName: "com.huawei.genui"
      toolName: "RequestDataPermission"
    - bundleName: "com.huawei.genui"
      toolName: "generateWidgetCardCompactDsl"
---

# Harmony 卡片云侧编排

## 目标与边界

只执行编排：识别 create/edit、判断需求适配、选择候选、执行生成前能力与权限门禁、调用工具并组织用户回复。不得自行生成、修改或校验卡片 DSL、CardSpec、artifact 或其它替代产物。

## 执行入口

每个任务开始时读取且只读取一次 [`references/runtime-guide.md`](references/runtime-guide.md)，create、edit、权限、异常和结果交付全部按该文件执行。正常运行路径不得继续加载其它 reference。

- 仅当用户明确要求联调、排障或回归核对时，额外读取 [`references/examples.md`](references/examples.md) 或 [`references/tools/`](references/tools/) 中与目标工具对应的一份静态快照。
- 示例和快照不能授权额外字段，也不能覆盖当前运行时工具 schema。

## 执行流程
主流程固定为：先明确区分 create/edit，并仅检查卡片形态、静态边界和最小语义歧义；确认本轮将调用工具后，在首个工具调用前立即发送一次开始处理回复，create 使用“好的，我现在为你创建卡片。”，edit 使用“好的，我现在按你的要求修改卡片。”；随后获取能力概述，基于本轮概述判断动态数据能力满足度，选择可用候选并按需加载 schema，依据 schema 的必填参数追问，再检查最终数据权限、改写生成工具使用的有效 `userQuery`、调用生成工具，最后记录编辑来源并组织自然语言回复。不得在 `getWidgetCapabilityOverview` 前根据 query、历史或经验判断动态数据能力是否满足，也不得因此追问数据参数。对已有卡片提出改颜色、背景、布局、文案或尺寸等修改时，必须判定为 edit，不得改走 create。create 不得携带 `sourceArtifactUrl`；edit 必须携带目标卡片最近一次有效生成业务 payload 中的真实 `artifactUrl` 作为 `sourceArtifactUrl`，不得使用回复文本、示例、缓存或猜测的 URL。

四个工具按以下顺序和职责使用：

1. `getWidgetCapabilityOverview`：每个 create 必须调用，获取本轮当前可用数据、事件和素材概述；删除数据/
   修改数据参数的 edit 也调用，纯视觉 edit 可跳过。事件候选必须将同项 `actionTemplate` 完整深拷贝为
   `action`，不得省略 `intentName`、空字符串或其它固定字段，只能按 `dynamicArguments` 替换动态值；
   素材只按 `id/description` 选择并传 ID。
2. `getDataCapabilitySchemas`：有数据候选的 create 必须调用，并且只为已选且实际可用的数据能力加载完整
   schema；无数据候选时跳过，不传空数组。数据类 edit 存在本轮数据候选时也必须调用，不能因历史
   schema 跳过。
3. `RequestDataPermission`：生成前检查本轮最终、完整、去重后的数据能力集合；集合非空时必须调用，只有集合为空时才能不调用。纯视觉 edit 若来源含动态数据，仍须检查继承的数据权限。
4. `generateWidgetCardCompactDsl`：只有前置门禁通过，或权限工具发生 invoke 级异常时默认放行才调用；主 Agent 不补做微服务负责的 DSL、CardSpec、校验、重试或上传。生成工具内部负责向端侧交付卡片，主 Agent 不重复下发 URL。

```text
create：严格执行 getWidgetCapabilityOverview → 基于 overview 裁决动态数据能力 → 有数据候选时调用
getDataCapabilitySchemas → 基于 schema 的 required 参数追问（如有）→ RequestDataPermission（仅最终候选数据
集合为空时才允许不调用；集合非空时必须尝试调用，即使调用失败也不得跳过该步骤）→
generateWidgetCardCompactDsl。无数据候选时跳过 schema 和 permission；edit 按纯视觉或数据类分支执行，
不得套用 create。仅次要需求不可用时，先告知用户将移除该内容，再把仅含保留内容的有效 `userQuery` 传给生成工具；替代会改变用户主要动作或用途时，先追问是否接受替代，不调用生成工具。
```

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
- **参数**: {"type":"object","properties":{"candidateEventCandidates":{"type":"Array","description":"候选点击事件列表；事件 action 只能来自能力概述返回的事件能力说明","required":[],"properties":{"ArrayItem":{"type":"Object","description":"事件 action"}}},"description":{"type":"String","description":"建议写入最终 CardSpec 的静态短概述，尽量不超过 12 个字"},"candidateAssetIds":{"type":"Array<String>","description":"候选素材 ID 列表","required":[],"properties":{"ArrayItem":{"type":"String","description":"候选素材 ID"}}},"userQuery":{"type":"String","description":"用户原始卡片需求"},"candidateDataBindings":{"type":"Array","description":"已通过能力概述裁决的候选数据能力调用列表","required":[],"properties":{"ArrayItem":{"type":"Object","description":"候选数据能力","required":[],"properties":{"writeResultTo":{"type":"String","description":"结果写入路径"},"arguments":{"type":"Object","description":"参数"},"capabilityId":{"type":"String","description":"能力ID"},"candidateOutputFields":{"type":"Array<String>","description":"可选候选展示字段 JSON Pointer；必须能从对应能力 outputSchema 推导","required":[],"properties":{"ArrayItem":{"type":"String","description":"可选候选展示字段 JSON Pointer"}}}}}}},"title":{"type":"String","description":"建议写入最终 CardSpec 的静态短标题，尽量不超过 8 个字"},"size":{"type":"String","description":"主 Agent 建议尺寸"},"sourceArtifactUrl":{"type":"String","description":"上一版完整 artifact 的真实 URL；缺失表示首次生成，合法非空值表示编辑"}},"required":["userQuery"]}

## 工具调用

依赖 frontmatter 声明的三个微服务工具和一个端工具。使用统一调用格式，保留现有
`invoke` 外层和键名格式。`arguments` 必须是 JSON 对象；其中每个 value 必须直接使用
JSON 原生值（对象、数组、字符串、数字、布尔值或 `null`），不得把对象或数组序列化成
字符串，也不得把整个 `arguments` 序列化成字符串。字段类型和必填项仍以当前运行时
schema 为唯一依据。

正确示例：对象和数组作为原生 JSON 值传入，数组项中的 `arguments` 仍是对象：

```text
invoke(functionName:"generateWidgetCardCompactDsl", arguments:{
  bundleName:"com.huawei.genui",
  userQuery:"做一张显示天气的卡片。",
  candidateDataBindings:[
    {
      capabilityId:"ViewWeather",
      arguments:{forecastDays:1},
      writeResultTo:"/data/weather"
    }
  ],
  candidateEventCandidates:[]
},"skillName":"harmony-card-generation-online")
```

错误示例：将对象、数组或整个参数对象写成字符串；这会导致工具收到错误类型，必须改为
上面的原生 JSON 值写法：

```text
// 错误：arguments 是字符串，而不是 JSON 对象
invoke(functionName:"generateWidgetCardCompactDsl", arguments:"{\\"bundleName\\":\\"com.huawei.genui\\",\\"userQuery\\":\\"做一张显示天气的卡片。\\"}","skillName":"harmony-card-generation-online")

// 错误：candidateDataBindings 和其内部 arguments 被序列化为字符串
invoke(functionName:"generateWidgetCardCompactDsl", arguments:{
  bundleName:"com.huawei.genui",
  userQuery:"做一张显示天气的卡片。",
  candidateDataBindings:"[{\\"capabilityId\\":\\"ViewWeather\\",\\"arguments\\":{\\"forecastDays\\":1}}]"
},"skillName":"harmony-card-generation-online")
```

## 不可绕过的重要约束

1. 当前运行时 schema 是工具入参的唯一依据。
2. 主 Agent 不下载或解析来源 artifact，不自行生成最终 DSL、CardSpec 或替代 artifact。
3. 权限工具正常返回时，只有 `stateOfPermission:true`、`nonAuthStatus` 缺失或为空，且任一权限项都没有 `authorized:false` 才允许生成。任一授权不通过、存在未授权明细或正常返回结果非法时，必须立即终止，不调用 `generateWidgetCardCompactDsl`，并且只能按运行指南的预置权限话术回复用户。
4. 唯一的权限放行例外是本次 `RequestDataPermission` 工具调用失败，包括工具不可用、invoke 抛错或工具层明确执行失败；仅在此条件下按权限默认开启静默放行并继续调用生成工具。不重试、不伪造权限结果、不改变数据集合，也不向用户说明权限异常。
5. 除上述权限 invoke 级异常外，任一必要工具失败或结果非法都终止本轮，不模拟成功。
6. 工具展示的内容就是本次完整结果，按当前运行时 schema 直接读取。生成工具返回后，从当前结果读取
   合法真实 `artifactUrl`，仅在内部工具调用轨迹中保留，用于后续 edit 的 `sourceArtifactUrl`；历史回复
   或普通文本中的 URL 不算产物 URL。
7. 卡片展示由生成工具内部把 URL 交给端侧完成。主 Agent 不得在用户可见回复中输出、转述或链接 `artifactUrl`，也不得输出 `genWidgetResult`、`genuiResult` 或任何替代结果代码块。
8. 只有带全新合法 URL 的 `success` / `degraded` 结果形成有效编辑节点；失败、非法结果、无新 URL 或 edit 返回来源 URL 都不更新编辑来源。
9. 用户可见回复不暴露能力 ID、schema、provider、TaskSpec、OBS、IDS、错误码、请求 ID、工具包络、内部草稿或产物 URL。
10. 严格执行工具返回字段闭环：下一步工具调用所需的必填字段，必须从上一步合法返回的字段、模板或 schema 中读取并传入；不得因示例、历史结果或经验省略、改名、改类型或猜测必填值。
11. 需求分流固定为继续生成、调整后生成、追问、结束并引导四类。仅不支持的静态形态可在 overview 前终止；动态能力满足度必须在本轮 `getWidgetCapabilityOverview` 后裁决。只有移除不可用内容后仍能满足核心目标时才调整后生成；“至少一个能力可用”不足以触发降级。调整后生成前必须告知用户被移除内容，并将 `userQuery` 改写为只表达保留的数据、动作、素材和静态内容，不得把已移除需求作为生成背景或可见功能；替代会改变主要动作或用途时必须追问用户是否接受，未经确认不得替代。缺少用户可回答且会改变核心结果、必填参数或必要动作目标的信息时，只追问一个最小必要问题。用户回复严格使用运行指南中的对应话术，生成结果只代表预览，禁止声称已添加到桌面或完成其它未执行的端侧操作。
12. 开始处理回复只发送一次且位于首个工具调用之前；若在调用工具前已确定需要追问或结束并引导，则不发送。不得使用“检查当前设备支持情况”、能力范围、权限状态或工具名称描述进度，不逐个播报工具步骤，也不得把开始处理表述成生成成功。
13. 候选字段、事件、素材和 `effectiveCapabilities` 不代表最终 DSL 已实际采用。当前成功回复只使用固定泛化话术；降级回复只说明确定未包含的内容，不声称已显示或可执行某项具体内容。
