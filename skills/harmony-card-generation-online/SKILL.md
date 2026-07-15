---
name: harmony-card-generation-online
description: "编排云侧微服务生成 HarmonyOS A2UI Form 服务卡片。用于用户用自然语言请求创建、生成、预览、添加桌面 widget/服务卡片，或端侧以 /harmony-card-generation 等标记触发卡片生成时，识别场景、获取能力概述、筛选候选数据/事件/素材能力、构造候选 dataBindings/event candidates/asset ids/size，调用 getWidgetCapabilityOverview、getDataCapabilitySchemas、generateWidgetCard，并根据 success/degraded/unsupported/failed 返回 genWidgetResult JSON 标记或可理解说明。"
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
- 构造 `candidateDataBindings`、`candidateEventCandidates`、`candidateAssetIds`、`size`、`title` 和 `description`。
- 调用 `generateWidgetCard` 生成卡片 artifact。
- 根据微服务返回状态组织用户回复。

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
- 要求本 skill 直接输出 DSL/CardSpec；说明本 skill 只通过云侧插件生成卡片，不自行拼装协议产物。

## 边界

- 不直接输出 `genui` 或 `cardspec` 代码块。
- 不直接生成最终 DSL、最终 CardSpec、A2UI prompt、本地 artifact 或校验修复结果。
- 不维护完整 A2UI 协议、组件白名单、美观规则、素材合法性或版本兼容矩阵。
- 不提前承诺设备一定支持天气、日历、应用、跳转或任一动态能力。
- 不编造能力 ID、事件目标、素材 ID、OBS 链接或 `genWidgetResult`。
- 不把点击事件写入 CardSpec；点击候选只作为 `candidateEventCandidates` 传给微服务裁决。
- 不把 `generateWidgetCard` 返回前的候选计划、schema、DSL 草稿或校验细节暴露给用户。
- 任一依赖工具不可用、调用失败或返回无法解析时终止本轮生成，不使用离线能力清单或历史资料补足。

微服务负责真实设备能力过滤、最终 CardSpec、A2UI DSL 生成、校验、降级、失败重试、OBS 上传和最终用户话术。

## 工作流

1. **触发判断**：判断用户 query 是否是创建卡片、生成 widget、生成服务卡片、添加桌面卡片、卡片预览等场景。端侧显式标记如 `/harmony-card-generation` 直接视为卡片创建场景。

2. **初步回应**：不要说"可以生成某动态卡片"。需要过程回复时只说："我先检查当前设备支持情况，然后为你生成可用的卡片。"

3. **获取能力概述**：调用 `getWidgetCapabilityOverview` 获取数据能力、事件能力和素材概述。除 `bundleName` 外不传其它字段；工具返回后从包装结构 `items[].data` 中解析业务 payload；如果返回原始插件包络，则先进入 `reply.items[].data`。工具不可用、调用失败或 payload 无法解析时，按 `references/response-policy.md` 回复并终止本轮生成。

4. **筛选候选能力**：按 `references/candidate-planning.md` 从概述中筛选候选能力：
   - 数据能力最多优先选 2 个核心候选。
   - 事件能力最多优先选 2 个主动作候选。
   - 素材候选只选和场景强相关的少量 ID。

5. **加载数据能力 Schema**：如果选中了数据能力，调用 `getDataCapabilitySchemas` 加载这些数据能力的完整 schema。工具不可用、调用失败或 payload 无法解析时，按 `references/response-policy.md` 回复并终止本轮生成。

6. **构造候选计划**：基于 schema 构造候选计划：
   - `size`：`"2x2"` 或 `"2x4"`。
   - `candidateDataBindings`：候选数据能力调用，不是最终 CardSpec。
   - 虽然对外工具 schema 中 `candidateDataBindings` 只是 `Array<Object>`，每一项仍必须按内部 `CandidateDataBinding` 类结构组装：`capabilityId`、`arguments`、`writeResultTo`，可选 `updateModel`；不要传松散对象或额外字段。
   - `candidateEventCandidates`：事件候选单数组；每项包含来自 overview 的 `capabilityId` 和完整 `action`。如果无法安全填齐 `action.call/args`，不要传该事件候选。
   - 虽然对外工具 schema 中事件项只是 `Object`，每一项仍必须按内部 `CandidateEventCandidate` 类结构组装：`capabilityId` 和 `action:{call,args}`。
   - `candidateAssetIds`：来自 overview 的素材 ID。
   - `title` / `description`：必传的静态短标题和短概述；无法提炼时使用稳定默认文案。
   - 本版不传 `slots`、`options`、`locale`、`uid`、`device` 等当前工具 schema 未声明的字段。

7. **生成卡片**：调用 `generateWidgetCard` 生成卡片。不要自行补做微服务负责的过滤、协议 profile、校验、重试或上传。工具不可用、调用失败或 payload 无法解析时，按 `references/response-policy.md` 回复并终止本轮生成。

8. **回复用户**：按 `references/response-policy.md` 回复：
   - 先从 `generateWidgetCard` 返回的 `items[].data` 解析业务 payload；如果返回原始插件包络，则先进入 `reply.items[].data`。
   - `success` / `degraded` 且存在有效 `artifactUrl`：输出业务 payload 的 `message`，并按“输出”章节格式输出 `genWidgetResult` JSON 标记。
   - `success` / `degraded` 但缺少有效 `artifactUrl`：按 `failed` 处理，不输出 `genWidgetResult`。
   - `unsupported`：不输出 `genWidgetResult`，输出用户可理解的能力边界和可尝试的替代方向。
   - `failed`：不输出 `genWidgetResult`，只输出生成服务暂时不可用的说明。

## 工具定义

本 skill 依赖三个微服务工具，声明于 frontmatter `metadata.tools`。必须通过 `invoke` 调用，格式为 `invoke(functionName:"<toolName>", arguments:{bundleName:"<bundleName>", ...})`。除 `bundleName` 外，只传工具 JSON 已声明的业务字段；不要手写内部 `content/deviceInfo/session` 包络。

注意：工具声明里部分入参只暴露为 `Array<Object>` 或 `Object`，但微服务内部会按具体类解析。传参时必须遵守 `references/tool-contracts.md` 中的类结构，尤其是 `CandidateDataBinding`、`CandidateEventCandidate` 和 `EventAction`；不要因为外层 schema 宽松就传任意键值。

### Function: getWidgetCapabilityOverview
- **toolName**: getWidgetCapabilityOverview
- **description**: 获取当前设备版本可用的能力概述。数据能力只返回 id 和描述；事件能力、素材能力全量返回。
- **参数**: {}
- **语义**: 在工作流的**获取能力概述**调用，了解当前设备支持哪些数据能力、事件、素材，为后续选择数据绑定和事件提供依据。

### Function: getDataCapabilitySchemas
- **toolName**: getDataCapabilitySchemas
- **description**: 按数据能力 ID 加载完整 inputSchema、outputSchema、依赖和 DataModel 骨架。
- **参数**: {"type":"object","properties":{"dataCapabilityIds":{"type":"Array<String>","description":"需要加载完整 schema 的数据能力 ID 列表，至少 1 个。","required":[],"properties":{"ArrayItem":{"type":"String","description":"完整 schema 的数据能力 ID "}}}},"required":["dataCapabilityIds"]}
- **约束**: 必须在调用 getWidgetCapabilityOverview 获取能力列表之后调用。入参 dataCapabilityIds 从能力概述返回的数据能力 ID 中选取。

### Function: generateWidgetCard
- **toolName**: generateWidgetCard
- **description**: 提交用户需求、候选数据绑定、候选事件和素材，生成可下载的 HarmonyOS A2UI Form 卡片 artifact。
- **参数**: {"type":"object","properties":{"userQuery":{"type":"String","description":"用户原始卡片需求"},"size":{"type":"String","description":"主 Agent 建议尺寸"},"candidateDataBindings":{"type":"Array","description":"候选数据能力调用列表；微服务会按注册表和 IDS 状态裁决最终可用项","required":[],"properties":{"ArrayItem":{"type":"Object","description":"候选数据能力；可包含 capabilityId、arguments、writeResultTo 和可选 updateModel"}}},"description":{"type":"String","description":"必传静态短概述，尽量不超过 12 个字"},"title":{"type":"String","description":"必传静态短标题，尽量不超过 8 个字"},"candidateEventCandidates":{"type":"Array","description":"候选点击事件列表；事件 action 只能来自能力概述返回的事件能力说明","required":[],"properties":{"ArrayItem":{"type":"Object","description":"事件 action"}}},"candidateAssetIds":{"type":"Array<String>","description":"候选素材 ID 列表","required":[],"properties":{"ArrayItem":{"type":"String","description":"候选素材 ID"}}}},"required":["userQuery","title","description"]}

## 工具调用示例

```text
invoke(functionName:"getWidgetCapabilityOverview", arguments:{bundleName:"com.omega_w_0823.hmservice"})

invoke(functionName:"getDataCapabilitySchemas", arguments:{bundleName:"com.omega_w_0823.hmservice", dataCapabilityIds:["ViewWeather", "calendar.events.search"]})

invoke(functionName:"generateWidgetCard", arguments:{bundleName:"com.omega_w_0823.hmservice", userQuery:"生成一个通勤卡片", title:"通勤助手", description:"天气日程速览", size:"2x4", candidateDataBindings:[{capabilityId:"ViewWeather", arguments:{districtName:"青浦区", forecastDays:1}, writeResultTo:"/data/weather"}], candidateEventCandidates:[{capabilityId:"event.open.weather", action:{call:"clickToDeeplink", args:{bundleName:"", abilityName:"", uri:"hww://www.huawei.com/totemweather?enterType=share&cityCode="}}}], candidateAssetIds:["asset.weather.rain"]})
```


## 输出

成功或降级成功时，最终回复必须包含微服务返回的 artifact URL JSON 标记：

````text
```genWidgetResult
{
  "result": "https://obs.example/widget/request-id.json"
}
```
````

规则：

- 只使用 `generateWidgetCard` 包装结构中业务 payload 返回的真实 `artifactUrl`。
- 标记必须是 `genWidgetResult` 代码块，代码块内容必须是合法 JSON 对象，且 `result` 的值必须等于真实 `artifactUrl`；不要再输出旧格式 `genWidgetResult:"url"`。
- `degraded` 时保留微服务给出的降级原因，轻量润色即可。
- `success` 或 `degraded` 缺少有效 `artifactUrl` 时按 `failed` 处理，不输出标记。
- `unsupported` 或 `failed` 时不要输出标记。
- 任何状态都不输出 `genui`、`cardspec`、A2UI JSONL、CardSpec JSON、校验日志或内部工具草稿。

## 参考

- 参考索引：[`references.md`](references.md)
- 微服务工具契约：[`references/tool-contracts.md`](references/tool-contracts.md)
- 候选能力和 dataBindings 规划：[`references/candidate-planning.md`](references/candidate-planning.md)
- 回复策略：[`references/response-policy.md`](references/response-policy.md)
- 测试、工具调用和话术样例：[`references/examples.md`](references/examples.md)

## 安全红线

- 不编造能力 ID、事件目标、素材 ID 或 artifact URL。
- 不把能力 schema、内部错误码、requestId、items、原始 data 字符串等内部信息暴露给用户。
- 不模拟工具结果；任一工具不可用、调用失败、结果无法解析或缺少必要字段时，说明卡片生成服务暂时不可用并终止本轮生成。
- 不读取离线能力清单、历史模板或旧协议资料来补足工具结果。
