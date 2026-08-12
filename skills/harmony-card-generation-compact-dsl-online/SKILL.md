---
name: harmony-card-generation-compact-dsl-online
description: "仅当用户在当前请求中明确要求‘使用极简协议’或‘使用 Compact DSL’创建、生成、预览或添加 HarmonyOS 桌面卡片、服务卡片、widget、小组件时使用，并优先于通用卡片 skill。普通卡片请求、只讨论或比较极简协议、仅在历史消息中提过极简协议、明确要求 A2UI、以及未显式指定协议的请求不得使用本 skill，应交由 harmony-card-generation-online 处理。本 skill 调用 getWidgetCapabilityOverview、getDataCapabilitySchemas 和 generateWidgetCardCompactDsl，并只返回真实 artifact URL。"
metadata:
  tools:
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "getWidgetCapabilityOverview"
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "getDataCapabilitySchemas"
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "generateWidgetCardCompactDsl"
---

# Harmony 卡片生成（极简协议）

## 触发门禁（最高优先级）

只有当前用户请求同时满足以下两个条件，才执行本 skill：

1. 用户正在请求创建、生成、预览或添加 HarmonyOS 桌面卡片、服务卡片、widget 或小组件。
2. 用户明确说出“使用极简协议”“用极简协议生成”“使用 Compact DSL”或语义完全等价的表达。

两个条件都满足时，本 skill 对该请求具有排他优先级，不再调用原
`harmony-card-generation-online` skill。

以下情况不得触发本 skill：

- “帮我生成天气卡片”“做一张桌面卡片”等未指定协议的普通请求。
- 只询问、解释、讨论、调试或比较极简协议，并未要求生成卡片。
- 只有历史消息提到极简协议，当前生成请求没有再次明确指定。
- 用户明确要求原协议、A2UI 或普通卡片生成链路。
- 用户只要求查看或输出 DSL、CardSpec、prompt、日志或协议示例。

门禁不满足时，不调用任何工具，不向用户推荐或追问是否改用极简协议，直接让原
`harmony-card-generation-online` skill 处理。若用户同时明确要求极简协议和 A2UI，先请用户选择一种协议，
在用户确认前不调用工具。

## 职责

本 skill 只负责极简协议首次生成链路的工具编排：

- 获取当前设备可用的数据、事件和素材能力。
- 按需加载已选数据能力的输入、输出 Schema。
- 构造候选数据绑定、事件、素材、尺寸、标题和说明。
- 调用 `generateWidgetCardCompactDsl` 生成并上传卡片 artifact。
- 根据工具返回的结构化状态和真实 `artifactUrl` 回复用户。

## 边界

- 不调用 `generateWidgetCard`；该工具属于原 A2UI 链路。
- 不在 `generateWidgetCardCompactDsl` 失败后回退到 `generateWidgetCard`。
- 不支持基于 `sourceArtifactUrl` 的多轮编辑；用户明确要求重新生成时才按首次生成处理。
- 不传 `protocolProfileId`；服务端固定使用 `compact-dsl-v1`。
- 不传 `sourceArtifactUrl`、`options`、`slots`、`updateModel` 或工具 Schema 未声明的字段。
- 不直接生成、修改或展示 Compact DSL、CardSpec、prompt、校验日志或内部候选计划。
- 不编造能力 ID、事件目标、素材 ID、artifact URL 或工具结果。
- 不提前承诺任一动态能力在当前设备可用。

## 唯一事实来源

- 当前运行时工具 Schema 是工具参数的唯一事实来源。
- `getWidgetCapabilityOverview` 的真实业务结果是能力 ID、事件和素材的唯一事实来源。
- `getDataCapabilitySchemas` 的真实业务结果是数据能力参数和输出字段的唯一事实来源。
- `generateWidgetCardCompactDsl` 的真实业务结果是状态、话术和 `artifactUrl` 的唯一事实来源。
- 本文中的结构和示例只帮助理解，不得覆盖当前运行时工具 Schema。

## 工作流

1. **执行触发门禁**：不满足“当前请求显式指定极简协议生成桌面卡片”时立即退出本 skill。
2. **检查业务信息**：地点、时间范围、动作目标等缺失且会改变核心需求时，先追问并等待用户回答。
   不向用户询问能力 ID、Schema 字段或设备能力是否可用。
3. **获取能力概述**：调用 `getWidgetCapabilityOverview`。除 `bundleName` 外不主动传其它字段。
4. **解析工具结果**：优先从 `items[].data` 读取业务结果；收到原始插件包络时读取
   `reply.items[].data`。无法解析时终止本轮生成。
5. **筛选候选能力**：先排除 `unavailableCapabilities`，再选择与用户需求直接相关的数据能力最多
   2 个、事件能力最多 2 个和少量强相关素材 ID。
6. **加载数据 Schema**：选中数据能力后，调用 `getDataCapabilitySchemas`。没有返回完整 Schema 的能力
   不得进入生成请求。
7. **构造候选计划**：
   - `size` 只使用 `2x2` 或 `2x4`。
   - `title` 和 `description` 必传，使用简短静态文本。
   - `candidateDataBindings` 每项包含 `capabilityId`、`arguments`、`writeResultTo`，可选
     `candidateOutputFields`。
   - `arguments` 只使用对应 `inputSchema` 声明的字段。
   - `writeResultTo` 必须是 `/data/` 下的 JSON Pointer。
   - `candidateOutputFields` 只能包含可由对应 `outputSchema` 推导出的 JSON Pointer；拿不准时省略。
   - 禁止传 `updateModel`。
   - `candidateEventCandidates` 每项包含 overview 返回的 `capabilityId`，并将同项 `actionTemplate` 完整
     深拷贝为 `action`；固定字段和空字符串不得省略，只能按 `dynamicArguments` 替换动态值。无法安全
     填齐时移除该事件候选。
   - `candidateAssetIds` 只能来自 overview 返回的素材 ID。
8. **生成卡片**：再次执行调用前硬校验，然后调用 `generateWidgetCardCompactDsl`。
9. **回复结果**：`success` 或 `degraded` 且存在有效 `artifactUrl` 时，输出业务 `message` 和
   `genWidgetResult`；`unsupported` 或 `failed` 时不输出 `genWidgetResult`。

## 工具定义

本 skill 依赖 frontmatter `metadata.tools` 中声明的三个云插件工具。所有工具必须通过 `invoke` 调用：

用于小艺平台导入的完整工具 JSON 定义：

- [`references/tools/com.omega_w_0823.hmservice__getWidgetCapabilityOverview.json`](references/tools/com.omega_w_0823.hmservice__getWidgetCapabilityOverview.json)
- [`references/tools/com.omega_w_0823.hmservice__getDataCapabilitySchemas.json`](references/tools/com.omega_w_0823.hmservice__getDataCapabilitySchemas.json)
- [`references/tools/com.omega_w_0823.hmservice__generateWidgetCardCompactDsl.json`](references/tools/com.omega_w_0823.hmservice__generateWidgetCardCompactDsl.json)

```text
invoke(functionName:"<toolName>", arguments:{bundleName:"<bundleName>", ...},"skillName":"harmony-card-generation-compact-dsl-online")
```

`skillName` 必须显式传入，并与本 skill frontmatter 的 `name` 完全一致。不要直接连接 WebSocket，
也不要手写 `content`、`deviceInfo`、`session`、`reply` 等插件包络。

### 调用前硬校验

每次 `invoke` 前必须完成以下检查：

1. 当前请求仍满足本 skill 的触发门禁。
2. 当前运行时存在与 `metadata.tools` 中 `bundleName + toolName` 完全匹配的工具。
3. `functionName`、`arguments.bundleName` 和 `skillName` 与本 skill 的声明完全一致。
4. 除 `bundleName` 外，只传当前工具运行时 Schema 已声明的顶层字段。
5. 必填字段、字段类型、数组元素类型和嵌套结构均符合当前运行时 Schema。
6. 所有能力和素材 ID 均来自本轮真实工具结果，且不在 `unavailableCapabilities` 中。
7. 数据能力 `arguments` 和 `candidateOutputFields` 分别符合本轮对应的输入、输出 Schema。
8. 任一检查失败时不调用工具，不猜测、不补 `null`，也不改走原 A2UI 工具。

### Function: getWidgetCapabilityOverview

- **bundleName**: `com.omega_w_0823.hmservice`
- **toolName**: `getWidgetCapabilityOverview`
- **接口路径**: `/api/v1/ws/tools/getWidgetCapabilityOverview`
- **描述**: 获取当前设备版本可用的能力概述。数据能力返回 ID 和描述；事件返回可直接复制的动作模板
  和动态参数说明；素材只返回 ID 和描述；同时返回不可用能力 ID。
- **业务参数**: `{}`
- **主要业务出参**:
  - `dataCapabilities`: 可用数据能力概述列表。
  - `eventCapabilities`: 可用事件能力列表。
  - `assetCandidates`: 可用素材候选列表。
  - `unavailableCapabilities`: 当前设备不可用的能力 ID 列表。

### Function: getDataCapabilitySchemas

- **bundleName**: `com.omega_w_0823.hmservice`
- **toolName**: `getDataCapabilitySchemas`
- **接口路径**: `/api/v1/ws/tools/getDataCapabilitySchemas`
- **描述**: 按数据能力 ID 加载完整 `inputSchema`、`outputSchema`、依赖信息和 DataModel 骨架。
- **参数**:

```json
{
  "type": "object",
  "properties": {
    "dataCapabilityIds": {
      "type": "Array<String>",
      "description": "需要加载完整 Schema 的数据能力 ID 列表，至少一个。"
    }
  },
  "required": ["dataCapabilityIds"]
}
```

- **约束**: 必须先调用 `getWidgetCapabilityOverview`，且每个 ID 都来自本轮可用数据能力列表。
- **主要业务出参**: 所请求能力的完整 Schema、依赖信息和建议 DataModel 写入结构。

### Function: generateWidgetCardCompactDsl

- **bundleName**: `com.omega_w_0823.hmservice`
- **toolName**: `generateWidgetCardCompactDsl`
- **接口路径**: `/api/v1/ws/tools/generateWidgetCardCompactDsl`
- **描述**: 提交用户原始需求和候选能力计划，使用服务端固定的 `compact-dsl-v1` profile 生成并上传
  HarmonyOS 极简协议卡片 artifact。
- **参数**:

```json
{
  "type": "object",
  "properties": {
    "userQuery": {
      "type": "String",
      "description": "用户当前明确要求使用极简协议生成桌面卡片的原始需求。"
    },
    "size": {
      "type": "String",
      "description": "建议尺寸，只能是 2x2 或 2x4；省略时服务默认使用 2x4。"
    },
    "title": {
      "type": "String",
      "description": "建议写入 CardSpec 的非空静态短标题。"
    },
    "description": {
      "type": "String",
      "description": "建议写入 CardSpec 的非空静态短说明。"
    },
    "candidateDataBindings": {
      "type": "Array<Object>",
      "description": "候选数据能力调用列表。每项包含 capabilityId、arguments、writeResultTo，可选 candidateOutputFields。"
    },
    "candidateEventCandidates": {
      "type": "Array<Object>",
      "description": "候选事件列表。每项包含 capabilityId 和 action；action 包含 call 和 args。"
    },
    "candidateAssetIds": {
      "type": "Array<String>",
      "description": "从能力概述中选出的素材 ID 列表。"
    },
    "capabilityRegistryVersion": {
      "type": "String",
      "description": "可选能力清单版本；通常省略，由设备版本推导。"
    }
  },
  "required": ["userQuery", "title", "description"]
}
```

`candidateDataBindings` 单项结构：

```json
{
  "capabilityId": "ViewWeather",
  "arguments": {
    "districtName": "青浦区",
    "forecastDays": 1
  },
  "writeResultTo": "/data/weather",
  "candidateOutputFields": [
    "/current/temperatureText",
    "/current/condition"
  ]
}
```

`candidateEventCandidates` 单项结构：

```json
{
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
}
```

- **主要业务出参**:
  - `status`: `success`、`degraded`、`unsupported` 或 `failed`。
  - `artifactUrl`: 成功或降级成功时返回的真实 artifact 地址。
  - `artifactDigest`: artifact 内容摘要。
  - `suggestSize`: 最终卡片尺寸。
  - `message`: 可展示给用户的结果说明。
  - `removedCapabilities`: 被服务端移除的候选能力及原因。
  - `effectiveCapabilities`: 最终进入 artifact 的有效能力集合。
  - `errorCode`: 失败或不支持时的业务错误码。

## 工具调用示例

示例仅适用于用户明确说“请使用极简协议生成一张青浦天气桌面卡片”的场景：

```text
invoke(functionName:"getWidgetCapabilityOverview", arguments:{bundleName:"com.omega_w_0823.hmservice"},"skillName":"harmony-card-generation-compact-dsl-online")

invoke(functionName:"getDataCapabilitySchemas", arguments:{bundleName:"com.omega_w_0823.hmservice", dataCapabilityIds:["ViewWeather"]},"skillName":"harmony-card-generation-compact-dsl-online")

invoke(functionName:"generateWidgetCardCompactDsl", arguments:{bundleName:"com.omega_w_0823.hmservice", userQuery:"请使用极简协议生成一张青浦天气桌面卡片", title:"青浦天气", description:"实时天气与预报", size:"2x2", candidateDataBindings:[{capabilityId:"ViewWeather", arguments:{districtName:"青浦区", forecastDays:1}, writeResultTo:"/data/weather", candidateOutputFields:["/current/temperatureText", "/current/condition", "/current/humidityPercent"]}], candidateEventCandidates:[{capabilityId:"event.open.weather", action:{call:"clickToDeeplink", args:{intentName:"Weather_CityCode", bundleName:"", abilityName:"", uri:"{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' + ${/data/weather/location/cityCode} }}"}}}], candidateAssetIds:["asset.sun_max", "asset.drop_1"]},"skillName":"harmony-card-generation-compact-dsl-online")
```

示例中的能力、事件、素材和字段路径只有在本轮工具真实返回且当前运行时 Schema 允许时才能使用。

## 输出

先从工具包装结构的 `items[].data` 解析业务结果；如果收到原始插件包络，则读取
`reply.items[].data`。

`success` 或 `degraded` 且存在有效 `artifactUrl` 时，最终回复包含业务 `message` 和以下标记：

````text
```genWidgetResult
{
  "result": "https://obs.example/widget/request-id.json"
}
```
````

规则：

- `result` 必须等于 `generateWidgetCardCompactDsl` 业务结果中的真实 `artifactUrl`。
- `degraded` 时同时保留工具返回的降级说明。
- `success` 或 `degraded` 缺少有效 `artifactUrl` 时按失败处理。
- `unsupported` 或 `failed` 时不输出 `genWidgetResult`。
- 不向用户输出 Compact DSL、CardSpec、内部错误详情、requestId、Schema 或候选计划。

## 安全红线

- 不满足触发门禁时绝不调用本 skill 的任何工具。
- 不模拟工具调用或结果。
- 不使用离线能力清单、历史工具结果或示例补足本轮缺失数据。
- 不把内部包络、错误码、日志、Schema 或原始 payload 暴露给用户。
- 不在极简协议工具失败后调用原 A2UI 生成工具。
