# 候选规划

目标：把用户 query 转成微服务可裁决的候选计划。候选计划只表达“用户可能需要什么”，不表达最终设备一定支持什么。

## 场景判断

进入本 skill 的典型 query：

- 端侧显式带 `/harmony-card-generation`、模板 ID 或创建卡片页面上下文的请求。
- “帮我做一张天气卡片”
- “生成一个通勤 widget，包含天气和日程”
- “做一个一键清理内存的桌面卡”
- “给我做一个看抖音使用时长和耗电的卡片”
- “创建一个会议提醒卡片，可以一键入会”

不进入或直接说明边界的 query：

- 纯聊天、百科、写作、代码任务。
- 要求完整 App 页面、复杂表单、长报告。
- 要求本 skill 直接输出 DSL/CardSpec；说明本 skill 只走云侧插件生成链路，不自行输出 DSL/CardSpec。

## 用户确认门禁

每次调用工具前都检查是否存在会影响卡片核心意图、候选能力或业务入参的待确认信息。存在时先集中追问最少必要问题，等待用户明确回答后再继续；不要先调用工具再补问。

需要追问的典型情况：

- 核心目标对象不明确，例如要查看哪个应用、联系人、地点、日期或设备。
- 用户给出多个互斥选择但未说明优先项，且不同选择会改变核心候选能力或动作。
- 核心能力的必填业务参数无法从用户原话、可信会话上下文或 schema 明确默认值安全推导。
- 拨号、导航、入会、切换设置等动作的目标或范围不明确，或高风险动作并非用户明确要求。

以下情况不追问：

- `size`、`title`、`description` 可按本文件的稳定规则和默认值确定，且不会改变用户意图。
- 设备是否真正支持某能力、应用是否安装、权限是否可用；这些由微服务裁决。
- 能力 ID、内部字段名、协议版本、写入路径等内部技术信息。
- 仅影响非核心可选内容；可删除该可选候选，不阻断核心卡片生成。

## 能力概述筛选 Prompt

拿到 `getWidgetCapabilityOverview` 后，先从包装输出 `items[].data` 中解析业务 payload，再在内部按以下标准筛选：

```text
从用户 query 中抽取：
1. 核心场景：天气、日历、系统设置、应用使用、运动健康、音乐、电话、会议、导航等。
2. 用户想看的动态数据：当前状态、列表、用量、耗电、时间范围、地点、应用。
3. 用户想执行的动作：打开应用、查看详情、拨号、清理内存、入会、导航、切换设置。
4. 视觉素材意图：天气图标、日历图标、应用图标、系统状态图标等。

把 overview 业务 payload 的可选 `unavailableCapabilities` 转成不可用数据能力 ID 集合；字段缺失或为 `[]` 时使用空集合，再从 `dataCapabilities` 中排除集合内 ID。
只从过滤后的 dataCapabilities、eventCapabilities、assetCandidates 中选择候选。
能力 description 与核心场景或动作强相关才选择。
不能仅凭名称相似选择会改变用户意图的能力。
```

筛选上限：

- `unavailableCapabilities` 是可选字符串数组；字段缺失或为 `[]` 时表示没有预先不可用项，不阻断后续流程。字段存在但类型错误时按 overview payload 无法解析处理。
- 同一数据能力同时出现在 `dataCapabilities` 和 `unavailableCapabilities` 时，以不可用为准；不得继续加载 schema 或构造 binding。

- 数据能力：最多 2 个核心候选。超过 2 个时优先保留用户明确点名、能回答主问题、能形成动态价值的能力。
- 事件能力：最多 2 个主动作候选。高风险动作只在用户明确要求且 overview 明确支持时选择。
- 素材候选：保留强相关少量 ID，通常 1 到 4 个；没有强匹配就传空数组。

## 尺寸选择

- 默认 `2x2`：一个核心状态、一个动作、一个简单提醒。
- 选择 `2x4`：两个以上核心信息区、动态列表、天气+日程、主指标+上下文+动作都需要完整展示。
- 如果不确定，优先 `2x2`，让微服务在必要时降级或调整。

## 标题与概述

调用 `generateWidgetCard` 时必须传 `title` 和 `description`，作为进入 TaskSpec 的静态短文案候选。

- `title` 尽量不超过 8 个字，表达卡片主题，例如“通勤助手”“天气速览”“会议提醒”。
- `description` 尽量不超过 12 个字，表达卡片用途，例如“天气日程速览”“今日安排提醒”。
- 只写稳定、静态、用户可理解的概述，不写动态值、隐私内容、未经确认的设备状态或能力可用性承诺。
- `title` 和 `description` 不替代 `userQuery`，也不替代数据能力、事件能力或素材能力。
- 无法提炼出合适短文案时也不能省略；使用“桌面卡片”和“信息速览”等稳定默认文案。

## 数据能力候选

生成 `candidateDataBindings` 时遵守：

- 先确认当前运行时 `generateWidgetCard` schema 已声明 `candidateDataBindings`；未声明时不传。schema 将数组项写成 `Object` 时，每一项按内部 `CandidateDataBinding` 类结构传入，但该内部结构不得用于扩展工具 `arguments` 顶层字段。
- `capabilityId` 必须来自已加载 schema。
- `arguments` 只使用 `inputSchema.properties` 中声明的字段。
- `arguments` 必须放在 binding 的 `arguments` 对象内，不要把能力入参平铺到 binding 顶层。
- 核心候选的必填字段缺失且用户可以补充时，先追问并等待回答，再继续调用工具；不要编造，也不要为了绕过追问直接移除核心候选。只影响非核心可选候选时可以移除，让微服务基于 `userQuery` 做降级或 unsupported 决策。
- `writeResultTo` 优先使用 schema 返回的 `defaultWriteResultTo`；没有时使用 `/data/{semanticKey}`，且多个候选不能相同或互为父子。
- 不传未在工具 schema 中声明的控制字段，例如 `required`；“必须包含某能力，否则不要生成”这类约束保留在 `userQuery` 中。
- 不把候选 binding 当最终 CardSpec；微服务会过滤和规范化。
- `candidateOutputFields` 是可选候选展示字段投影。无需精确投影时省略，交给微服务根据 `userQuery` 和能力 schema 构造模型输入。
- 需要表达投影时只传 `candidateOutputFields`，值必须是 JSON Pointer 字符串数组；每个路径都必须能从对应能力本轮返回的 `outputSchema` 推导，去重后传入。不能写入真实用户数据、字段类型、字段描述或模型自造字段。
- 不再传 `updateModel`。
- 相对时间必须转换成能力 schema 要求的参数。若日历 schema 要 `timeInterval`，把 today/tomorrow/next24Hours 按本地时区换算为毫秒区间；不要把 `timeRange` 写进 `arguments`。
- 地点、联系人、App 包名等核心目标无法可靠解析且用户可以确认时，先追问并等待回答；仅属于非核心可选候选时才移除，不猜测值。

本版不传 `slots`、`options`、`locale`、`uid`、`device` 等当前工具 schema 未声明的字段。已经明确的地点、时间范围、目标动作、模板 ID 和不支持部分保留在 `userQuery` 中，由微服务解析或降级；会改变核心意图的缺失字段必须先向用户追问，不得只保留模糊原文后继续调用。

## 事件能力候选

- 使用单数组 `candidateEventCandidates`，不要使用并行的 ID 数组和 action 数组。
- 先确认当前运行时 `generateWidgetCard` schema 已声明 `candidateEventCandidates`；未声明时不传。schema 将数组项写成 `Object` 时，每一项按内部 `CandidateEventCandidate` 类结构传入，但该内部结构不得用于扩展工具 `arguments` 顶层字段。
- 每个候选项必须包含 `capabilityId` 和完整 `action`，且 `capabilityId` 必须来自 overview。
- `action` 必须是对象，内部包含 `call` 和 `args`；不要把 `call`、`args` 平铺到事件候选顶层。
- `args` 必须是对象，不要传字符串化 JSON。
- `action` 必须来自 overview 给出的 `actionTemplate` 或完整事件描述；只有参数可以安全填齐时才传该事件候选。
- `action` 只是候选事件动作，不是最终 DSL `onClick`；微服务仍要做依赖过滤、参数校验和最终写入。
- 打开应用、打开详情、拨号、入会、导航、清理内存、切换设置等都通过 overview 的事件能力选择。
- 如果用户没有明确动作，但场景有自然入口，可以选一个低风险入口候选，例如打开天气或日历详情。
- 涉及高风险或不可逆动作时，只选 overview 中明确支持且用户明确要求的能力；用户未明确要求时先追问确认，不得根据场景自行补充。
- 不编造 `call`、`args` 字段名、deeplink、intentName、bundleName、abilityName 或拨号号码。
- 事件参数可以来自静态安全值、用户明确输入或候选数据能力可推导路径；如果路径依赖最终 CardSpec 或列表项上下文且当前无法确定，不传该事件候选。
- 微服务过滤事件能力时删除整个候选项；不存在 ID 和 action 下标错配问题。

候选动作示例：

```json
{
  "candidateEventCandidates": [
    {
      "capabilityId": "event.open.weather",
      "action": {
        "call": "clickToDeeplink",
        "args": {
          "bundleName": "",
          "abilityName": "",
          "uri": "hww://www.huawei.com/totemweather?enterType=share&cityCode="
        }
      }
    }
  ]
}
```

## 素材候选

- 只传 `candidateAssetIds`，不要自造图片路径。
- 素材候选必须和场景、状态或动作有明确语义关系。
- 没有匹配素材时传空数组，由微服务决定是否用无素材设计。

## 降级

不传 `options`。如果用户明确要求“必须包含某能力，否则不要生成”，该约束保留在 `userQuery` 中，由微服务解析并决定是否 unsupported。

## 不支持场景

- overview 过滤 `unavailableCapabilities` 后没有任何相关数据能力，但存在可用入口事件或静态价值时，仍可提交静态/入口候选，由微服务决定 degraded 或 unsupported。
- 用户请求三方实时数据、跨端数据、输入表单、长列表或复杂页面时，不编造动态能力；保留原始 `userQuery`，由微服务决定是否生成静态降级卡或返回 unsupported。
- 如果所有核心能力都缺失且没有入口或静态价值，不要自行输出 `genWidgetResult`；调用微服务后按其 `unsupported` 回复。任一工具不可用时终止本轮生成并说明服务暂时不可用。
