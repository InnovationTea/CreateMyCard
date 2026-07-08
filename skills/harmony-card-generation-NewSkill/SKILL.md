---
name: harmony-card-generation-cloud-orchestration
description: "编排云侧微服务生成 HarmonyOS A2UI Form 服务卡片。用于用户用自然语言请求创建、生成、预览、添加桌面 widget/服务卡片，或端侧以 /harmony-card-generation 等标记触发卡片生成时，识别场景、获取能力概述、筛选候选数据/事件/素材能力、构造候选 dataBindings/event candidates/asset ids/size，调用 getWidgetCapabilityOverview、getDataCapabilitySchemas、generateWidgetCard，并根据 success/degraded/unsupported/failed 返回 genWidgetResult 链接或可理解说明；当 generateWidgetCard 不可用、调用失败或结果不符合预期时，主 Agent 可进入兜底链路生成最终可交付结果，但不得伪造动态能力或 artifact URL。"
metadata:
  tools:
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "getWidgetCapabilityOverview"
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "getDataCapabilitySchemas"
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "generateWidgetCard"
---

# Harmony 卡片生成（云侧工具编排版）

## 职责

本 skill 优先负责工具编排：

- 识别用户是否在请求创建 HarmonyOS 桌面服务卡片。
- 调用微服务工具获取当前环境下可供候选筛选的能力概述。
- 根据用户 query 选择候选数据能力、事件能力和素材。
- 按需加载选中数据能力 schema。
- 构造 `candidateDataBindings`、`candidateEventCandidates`、`candidateAssetIds` 和 `size`。
- 调用 `generateWidgetCard` 生成卡片 artifact。
- 根据微服务返回状态组织用户回复。
- 当 `generateWidgetCard` 不可用、调用失败或结果不符合预期时，进入主 Agent 兜底链路生成最终可交付结果。

## 触发场景

典型触发 query：

- 端侧显式带 `/harmony-card-generation`、模板 ID 或创建卡片页面上下文的请求。
- "帮我做一张天气卡片"
- "生成一个通勤 widget，包含天气和日程"
- "做一个一键清理内存的桌面卡"
- "给我做一个看抖音使用时长和耗电的卡片"
- "创建一个会议提醒卡片，可以一键入会"
- 任何包含"桌面卡片"、"widget"、"服务卡片"、"生成卡片"、"创建卡片"等表述的请求。

不进入或直接说明边界的 query：

- 纯聊天、百科、写作、代码任务。
- 要求完整 App 页面、复杂表单、长报告。
- 要求直接输出 DSL/CardSpec。

## 边界

- 默认不直接输出 `genui` 或 `cardspec` 代码块。
- 默认不直接生成最终 DSL、最终 CardSpec、A2UI prompt 或校验修复结果；只有 `generateWidgetCard` 不可用、调用失败或结果不符合预期时才允许兜底生成最终结果。
- 不维护完整 A2UI 协议、组件白名单、美观规则、素材合法性或版本兼容矩阵。
- 不提前承诺设备一定支持天气、日历、应用、跳转或任一动态能力。
- 不编造能力 ID、事件目标、素材 ID、OBS 链接或 `genWidgetResult`。
- 不把点击事件写入 CardSpec；点击候选只作为 `candidateEventCandidates` 传给微服务裁决。
- 不把 `generateWidgetCard` 返回前的候选计划、schema、DSL 草稿或校验细节暴露给用户。

微服务默认负责真实设备能力过滤、最终 CardSpec、A2UI DSL 生成、校验、降级、失败重试、OBS 上传和最终用户话术。兜底链路只在生成工具不可用或结果不可靠时启用。

## 工作流

1. **触发判断**：判断用户 query 是否是创建卡片、生成 widget、生成服务卡片、添加桌面卡片、卡片预览等场景。端侧显式标记如 `/harmony-card-generation` 直接视为卡片创建场景。

2. **初步回应**：不要说"可以生成某动态卡片"。需要过程回复时只说："我先检查当前设备支持情况，然后为你生成可用的卡片。"

3. **获取能力概述**：调用 `getWidgetCapabilityOverview` 获取数据能力、事件能力和素材概述。`uid` 和 `device` 由工具层自动注入，不要手写。

4. **筛选候选能力**：按 `reference/candidate-planning.md` 从概述中筛选候选能力：
   - 数据能力最多优先选 2 个核心候选。
   - 事件能力最多优先选 2 个主动作候选。
   - 素材候选只选和场景强相关的少量 ID。

5. **加载数据能力 Schema**：如果选中了数据能力，调用 `getDataCapabilitySchemas` 加载这些数据能力的完整 schema。

6. **构造候选计划**：基于 schema 构造候选计划：
   - `size`：`"2x2"` 或 `"2x4"`。
   - `candidateDataBindings`：候选数据能力调用，不是最终 CardSpec。
   - `candidateEventCandidates`：事件候选单数组；每项包含来自 overview 的 `capabilityId` 和完整 `action`。如果无法安全填齐 `action.call/args`，不要传该事件候选。
   - `candidateAssetIds`：来自 overview 的素材 ID。
   - 本版不传 `slots`；生产默认不传 `options`。

7. **生成卡片**：调用 `generateWidgetCard` 生成卡片。正常情况下不要自行补做微服务负责的过滤、协议 profile、校验、重试或上传。

8. **回复用户**：按 `reference/response-policy.md` 回复：
   - `success` / `degraded`：输出微服务 `message`，并输出 `genWidgetResult` 标记。
   - `unsupported` / `failed`：不输出 `genWidgetResult`，只输出用户可理解说明和可尝试的替代方向。

9. **兜底生成**：如果 `generateWidgetCard` 不可用、调用失败或结果不符合预期，按 `reference/tool-contracts.md` 的“兜底生成”规则由主 Agent 生成最终可交付结果。兜底结果不得伪造动态能力、事件目标、素材 ID、artifact URL 或 `genWidgetResult`。

## 工具定义

本 skill 依赖三个微服务工具，声明于 frontmatter `metadata.tools`。必须通过 `invoke` 调用，格式为 `invoke(functionName:"<toolName>", arguments:{bundleName:"<bundleName>", ...})`。

### Function: getWidgetCapabilityOverview
- **toolName**: getWidgetCapabilityOverview
- **description**: 获取当前设备版本可用的能力概述。数据能力只返回 id 和描述；事件能力和素材能力全量返回
- **参数**: {}

### Function: getDataCapabilitySchemas
- **toolName**: getDataCapabilitySchemas
- **description**: 按数据能力 ID 加载完整 inputSchema、outputSchema、依赖和 DataModel 骨架
- **参数**: {"type":"object","properties":{"dataCapabilityIds":{"type":"Array<String>","description":"需要加载完整 schema 的数据能力 ID 列表，至少 1 个。","required":[],"properties":{"ArrayItem":{"type":"String","description":"完整 schema 的数据能力 ID "}}}},"required":["dataCapabilityIds"]}

### Function: generateWidgetCard
- **toolName**: generateWidgetCard
- **description**: 提交用户需求、候选数据绑定、候选事件和素材，生成可下载的 HarmonyOS A2UI Form 卡片 artifact
- **参数**: {"type":"object","properties":{"candidateEventCandidates":{"type":"Array","description":"候选点击事件列表；事件 action 只能来自能力概述返回的事件能力说明","required":[],"properties":{"ArrayItem":{"type":"Object","description":"事件 action"}}},"candidateAssetIds":{"type":"Array<String>","description":"候选素材 ID 列表","required":[],"properties":{"ArrayItem":{"type":"String","description":"候选素材 ID"}}},"candidateDataBindings":{"type":"Array","description":"候选数据能力调用列表；微服务会按注册表和 IDS 状态裁决最终可用项","required":[],"properties":{"ArrayItem":{"type":"Object","description":"候选数据能力"}}},"userQuery":{"type":"String","description":"用户原始卡片需求"},"size":{"type":"String","description":"主 Agent 建议尺寸"}},"required":["userQuery"]}

## 工具调用示例

```text
invoke(functionName:"getWidgetCapabilityOverview", arguments:{bundleName:"com.omega_w_0823.hmservice"})

invoke(functionName:"getDataCapabilitySchemas", arguments:{bundleName:"com.omega_w_0823.hmservice", dataCapabilityIds:["ViewWeather", "calendar.events.search"]})

invoke(functionName:"generateWidgetCard", arguments:{bundleName:"com.omega_w_0823.hmservice", userQuery:"生成一个通勤卡片", size:"2x4", candidateDataBindings:[{capabilityId:"ViewWeather", arguments:{districtName:"青浦区", forecastDays:1}, writeResultTo:"/data/weather"}], candidateEventCandidates:[{capabilityId:"event.open.weather", action:{call:"clickToDeeplink", args:{bundleName:"", abilityName:"", uri:"hww://www.huawei.com/totemweather?enterType=share&cityCode="}}}], candidateAssetIds:["asset.weather.rain"]})
```


## 输出

成功或降级成功时，最终回复必须包含微服务返回的 artifact URL 标记：

````text
```genWidgetResult:"https://obs.example/widget/request-id.json"```
````

规则：

- 只使用 `generateWidgetCard` 返回的真实 `artifactUrl`。
- `degraded` 时保留微服务给出的降级原因，轻量润色即可。
- `unsupported` 或 `failed` 时不要输出标记，除非兜底链路真的完成 artifact 上传并拿到真实 URL。
- 正常链路不输出 `genui`、`cardspec`、A2UI JSONL、CardSpec JSON、校验日志或内部工具草稿；兜底链路需要交付最终结果时，可以输出必要产物，但必须说明未走云侧 artifact 生成链路。

## 参考

- 参考索引：[`reference.md`](reference.md)
- 微服务工具契约：[`reference/tool-contracts.md`](reference/tool-contracts.md)
- 候选能力和 dataBindings 规划：[`reference/candidate-planning.md`](reference/candidate-planning.md)
- 回复策略：[`reference/response-policy.md`](reference/response-policy.md)
- 测试、工具调用和话术样例：[`reference/examples.md`](reference/examples.md)

## 安全红线

- 不编造能力 ID、事件目标、素材 ID 或 artifact URL。
- 不把 `uid`、`device`、能力 schema、内部错误码暴露给用户。
- 不模拟工具结果；工具不可用或生成结果不符合预期时，进入兜底链路或说明当前环境尚未接入云侧卡片生成工具。
- 兜底链路不得伪造动态能力、事件目标、素材 ID、artifact URL 或 `genWidgetResult`。
