---
name: harmony-card-generation-compact-dsl-online
description: "编排云侧微服务生成 Compact DSL 格式的 HarmonyOS 服务卡片。用于用户用自然语言请求创建、生成、预览或添加桌面 widget/服务卡片时，调用 getWidgetCapabilityOverview、getDataCapabilitySchemas 和 generateWidgetCardCompactDsl，返回真实 artifact URL；本 skill 不调用原 A2UI Form 生成工具 generateWidgetCard。"
metadata:
  tools:
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "getWidgetCapabilityOverview"
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "getDataCapabilitySchemas"
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "generateWidgetCardCompactDsl"
---

# Harmony 卡片生成（Compact DSL 验证版）

## 职责

只负责主 Agent 侧编排：

- 识别创建 HarmonyOS 桌面服务卡片的请求。
- 获取当前设备的候选数据、事件和素材能力。
- 按需加载选中数据能力的 Schema。
- 构造候选数据绑定、事件、素材、尺寸、标题和说明。
- 调用 `generateWidgetCardCompactDsl` 生成并上传卡片 artifact。
- 根据工具的结构化状态回复用户。

## 边界

- 不调用 `generateWidgetCard`；该工具属于原 A2UI Form 验证链路。
- 不传 `protocolProfileId`；工具4在服务端固定使用 `compact-dsl-v1`。
- 不直接生成、修改或展示 Compact DSL、CardSpec、prompt、校验日志。
- 不编造能力 ID、事件目标、素材 ID、artifact URL 或工具结果。
- 不提前承诺某项动态能力在当前设备可用。
- 工具4不可用或失败时直接说明，不回退到工具3。

## 工作流

1. 判断用户是否要求创建卡片、widget、服务卡片或桌面卡片。
2. 调用 `getWidgetCapabilityOverview` 获取候选能力概述。
3. 从真实返回值中选择和用户需求直接相关的候选：数据能力最多 2 个，事件能力最多 2 个，素材只选少量强相关 ID。
4. 选中数据能力时，调用 `getDataCapabilitySchemas` 加载完整 Schema。未返回 Schema 的能力必须移除。
5. 按 Schema 构造候选计划：
   - `size` 只使用 `2x2` 或 `2x4`。
   - `title` 和 `description` 必传，使用简短静态文本。
   - `candidateDataBindings` 每项包含 `capabilityId`、`arguments`、`writeResultTo`，可选 `updateModel`。
   - `candidateEventCandidates` 每项包含 overview 中的 `capabilityId` 和完整 `action:{call,args}`；无法安全填齐时不传该事件。
   - `candidateAssetIds` 只能来自 overview。
6. 调用 `generateWidgetCardCompactDsl`。不要传 `slots`、`options`、`protocolProfileId` 或服务内部上下文字段。
7. 从工具包装结构的 `items[].data` 读取业务结果；如果收到原始插件包络，则读取 `reply.items[].data`。
8. `success` 或 `degraded` 时输出业务结果的 `message` 和真实 artifact URL；`unsupported` 或 `failed` 时不输出 artifact 标记。

## 工具调用

所有工具通过 `invoke` 调用。除 `bundleName` 外，只传对应工具声明的业务参数，不手写 `content/deviceInfo/session` 包络。

```text
invoke(functionName:"getWidgetCapabilityOverview", arguments:{bundleName:"com.omega_w_0823.hmservice"})

invoke(functionName:"getDataCapabilitySchemas", arguments:{bundleName:"com.omega_w_0823.hmservice", dataCapabilityIds:["ViewWeather"]})

invoke(functionName:"generateWidgetCardCompactDsl", arguments:{bundleName:"com.omega_w_0823.hmservice", userQuery:"生成一个通勤卡片", title:"通勤助手", description:"天气速览", size:"2x4", candidateDataBindings:[{capabilityId:"ViewWeather", arguments:{districtName:"青浦区", forecastDays:1}, writeResultTo:"/data/weather"}], candidateEventCandidates:[], candidateAssetIds:[]})
```

## 生成工具参数

`generateWidgetCardCompactDsl` 使用以下业务字段：

- `userQuery`：必传，用户原始卡片需求。
- `title`：必传，简短静态标题。
- `description`：必传，简短静态说明。
- `size`：可选，`2x2` 或 `2x4`，默认 `2x4`。
- `candidateDataBindings`：可选，候选数据能力调用列表。
- `candidateEventCandidates`：可选，候选事件列表。
- `candidateAssetIds`：可选，候选素材 ID 列表。
- `capabilityRegistryVersion`：仅在工具 Schema 明确要求时传入。

## 输出

成功或降级成功时，最终回复必须包含工具返回的真实 artifact URL：

````text
```genWidgetResult
{
  "result": "https://obs.example/widget/request-id.json"
}
```
````

规则：

- `result` 必须等于 `generateWidgetCardCompactDsl` 业务结果中的 `artifactUrl`。
- `degraded` 时同时保留工具返回的降级说明。
- `unsupported` 或 `failed` 时不输出 `genWidgetResult`。
- 不向用户输出 Compact DSL、CardSpec、内部错误详情或候选计划。

## 安全红线

- 不模拟工具调用或结果。
- 不把 Schema、requestId、原始 items 包装或内部错误码暴露给用户。
- 不在工具4失败后偷偷调用工具3；两条协议验证链路必须隔离。
