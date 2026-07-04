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
- 要求主 Agent 直接输出 DSL/CardSpec；本 skill 已改为云侧生成链路，只能调用微服务生成可添加卡片。

## 能力概述筛选 Prompt

拿到 `getWidgetCapabilityOverview` 后，在内部按以下标准筛选：

```text
从用户 query 中抽取：
1. 核心场景：天气、日历、系统设置、应用使用、运动健康、音乐、电话、会议、导航等。
2. 用户想看的动态数据：当前状态、列表、用量、耗电、时间范围、地点、应用。
3. 用户想执行的动作：打开应用、查看详情、拨号、清理内存、入会、导航、切换设置。
4. 视觉素材意图：天气图标、日历图标、应用图标、系统状态图标等。

只从 overview 返回的 dataCapabilities、eventCapabilities、assetCandidates 中选择候选。
能力 description 与核心场景或动作强相关才选择。
不能仅凭名称相似选择会改变用户意图的能力。
```

筛选上限：

- 数据能力：最多 2 个核心候选。超过 2 个时优先保留用户明确点名、能回答主问题、能形成动态价值的能力。
- 事件能力：最多 2 个主动作候选。高风险动作只在用户明确要求且 overview 明确支持时选择。
- 素材候选：保留强相关少量 ID，通常 1 到 4 个；没有强匹配就传空数组。

## 尺寸选择

- 默认 `2x2`：一个核心状态、一个动作、一个简单提醒。
- 选择 `2x4`：两个以上核心信息区、动态列表、天气+日程、主指标+上下文+动作都需要完整展示。
- 如果不确定，优先 `2x2`，让微服务在必要时降级或调整。

## 数据能力候选

生成 `candidateDataBindings` 时遵守：

- `capabilityId` 必须来自已加载 schema。
- `arguments` 只使用 `inputSchema.properties` 中声明的字段。
- 必填字段缺失且无法从用户 query、端侧安全上下文或 schema 默认说明推导时，不要编造；移除该候选，让微服务基于 `userQuery` 做静态降级或 unsupported 决策。
- `writeResultTo` 优先使用 schema 返回的 `defaultWriteResultTo`；没有时使用 `/data/{semanticKey}`，且多个候选不能相同或互为父子。
- `required` 默认 `false`。只有用户核心诉求完全依赖该能力时才设为 `true`。
- 不把候选 binding 当最终 CardSpec；微服务会过滤和规范化。
- 相对时间必须转换成能力 schema 要求的参数。若日历 schema 要 `timeInterval`，把 today/tomorrow/next24Hours 按本地时区换算为毫秒区间；不要把 `timeRange` 写进 `arguments`。
- 地点、联系人、App 包名等无法可靠解析时，移除对应候选，不用猜测值。

本版不传 `slots`。地点、时间范围、目标动作、模板 ID、缺失字段和不支持部分都保留在 `userQuery` 中，由微服务解析或降级。

## 事件能力候选

- 使用单数组 `candidateEventCandidates`，不要使用并行的 ID 数组和 action 数组。
- 每个候选项必须包含 `capabilityId`，且必须来自 overview。
- 如果 overview 给出 `actionTemplate` 或完整事件描述，并且参数可以安全填齐，在同一个候选项内写 `action`。
- `action` 只是候选事件动作，不是最终 DSL `onClick`；微服务仍要做依赖过滤、参数校验和最终写入。
- 打开应用、打开详情、拨号、入会、导航、清理内存、切换设置等都通过 overview 的事件能力选择。
- 如果用户没有明确动作，但场景有自然入口，可以选一个低风险入口候选，例如打开天气或日历详情。
- 涉及高风险或不可逆动作时，只选 overview 中明确支持且用户明确要求的能力。
- 不编造 `call`、`args` 字段名、deeplink、intentName、bundleName、abilityName 或拨号号码。
- 事件参数可以来自静态安全值、用户明确输入或候选数据能力可推导路径；如果路径依赖最终 CardSpec 或列表项上下文且当前无法确定，候选项只写 `capabilityId`，不写 `action`。
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

本版不传 `options`。微服务默认 `allowDegradation: true`、`returnArtifactInline: false`。如果用户明确要求“必须包含某能力，否则不要生成”，该约束保留在 `userQuery` 中，由微服务解析并决定是否 unsupported。

## 不支持场景

- overview 没有任何相关数据能力，但存在可用入口事件或静态价值时，仍可提交静态/入口候选，由微服务决定 degraded 或 unsupported。
- 用户请求三方实时数据、跨端数据、输入表单、长列表或复杂页面时，不编造动态能力；保留原始 `userQuery`，由微服务决定是否生成静态降级卡或返回 unsupported。
- 如果所有核心能力都缺失且没有入口或静态价值，不要自行输出 `genWidgetResult`；调用微服务后按其 `unsupported` 回复，或在工具不可用时说明当前环境无法生成。
