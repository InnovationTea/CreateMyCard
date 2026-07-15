# 微服务工具契约

只调用工具并传候选计划。真实设备能力裁决、最终 CardSpec、A2UI DSL 生成、校验、降级和 artifact 上传都由微服务完成。

## 调用总则

- 三个工具按顺序使用：
  1. `getWidgetCapabilityOverview`
  2. `getDataCapabilitySchemas`
  3. `generateWidgetCard`
- 必须使用 `invoke(functionName:"<toolName>", arguments:{bundleName:"<bundleName>", ...})` 调用工具。
- `arguments` 必须包含 `bundleName: "com.omega_w_0823.hmservice"`。
- 除 `bundleName` 外，只传工具 JSON `arguments.properties` 中声明的业务字段。
- 对外工具 schema 中的 `Array<Object>` / `Object` 只是插件层宽类型；具体数组项和对象必须按本文件定义的内部类结构传入。
- 不手写内部 WebSocket 包络字段，例如 `content`、`deviceInfo`、`session`、`pagination`、`userAuth`、`utterance`、`version`。
- 不手写或猜测 `uid`、`device`、`locale`、`protocolProfileId`、`capabilityRegistryVersion`、`options` 等未在当前对外工具 schema 中声明的字段。
- 不传 `slots`。

调用顺序：

```text
invoke(functionName:"getWidgetCapabilityOverview", arguments:{bundleName:"com.omega_w_0823.hmservice"})
invoke(functionName:"getDataCapabilitySchemas", arguments:{bundleName:"com.omega_w_0823.hmservice", dataCapabilityIds:[...]})
invoke(functionName:"generateWidgetCard", arguments:{bundleName:"com.omega_w_0823.hmservice", userQuery:"...", title:"...", description:"...", ...})
```

## 包装输出

当前三个工具通常返回包装结构。如果运行环境返回原始插件包络，则先处理顶层 `errorCode/errorMessage/reply`：`errorCode` 非 `"0"` 时按工具失败处理；`errorCode` 为 `"0"` 时从 `reply` 中继续读取 `streamInfo/items`。如果运行环境已归一化，则直接读取顶层 `streamInfo/items`。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `streamInfo` | `String/Object` | 是 | 流式信息。只用于工具层展示或调试，不直接作为业务结果。 |
| `items` | `Array<ToolItem>` | 是 | 结构化工具项列表。业务结果位于其中某个工具项的 `data` 字段。 |

`ToolItem`：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `tool` | `String` | 否 | 当前工具名。 |
| `operation` | `String` | 否 | 本次动作。 |
| `status` | `String` | 否 | 工具层状态，不等同于 `generateWidgetCard` 的业务生成状态。 |
| `type` | `String` | 否 | 回复类型。 |
| `requestId` | `String` | 否 | 请求 ID，仅用于排障。 |
| `errorCode` | `String` | 否 | 工具层错误码，仅用于内部判断。 |
| `error` | `String` | 否 | 工具层错误内容。 |
| `data` | `String` | 是 | 工具业务返回结果，通常是 JSON 字符串。 |

解析规则：

- 优先从 `items` 中选择 `tool` 等于当前工具名且包含 `data` 的项；没有 `tool` 时选择第一个包含 `data` 的项。
- `data` 是 JSON 字符串时，先解析为对象；如果运行环境已将其解析成对象，可直接使用。不要把原始 `data` 字符串展示给用户。
- `getWidgetCapabilityOverview` 的 `data` 解析后应包含 `dataCapabilities`、`eventCapabilities`、`assetCandidates`。
- `getDataCapabilitySchemas` 的 `data` 解析后应包含 `dataCapabilities`、`missingCapabilityIds`。
- `generateWidgetCard` 的 `data` 解析后应包含业务 `status`、`message`，成功或降级时还应包含真实 `artifactUrl`。
- `generateWidgetCard` 业务 `status` 为 `success` 或 `degraded` 且存在真实 `artifactUrl` 时，最终用户回复必须按 `response-policy.md` 输出 `genWidgetResult` JSON 代码块，将 `artifactUrl` 写入 `result` 字段。
- 如果没有可解析的 `data`，或 `items[].error` 表示工具失败，按工具调用异常处理，不输出 `genWidgetResult`。
- 用户可见回复不暴露 `items`、`requestId`、`errorCode`、工具层 `status` 或原始 `data` 字符串。

## getWidgetCapabilityOverview

用途：获取当前设备版本可用的能力概述。数据能力只返回 `id` 和描述；事件能力、素材能力全量返回。

参数：无。除 `bundleName` 外不传其它字段。

调用示例：

```text
invoke(functionName:"getWidgetCapabilityOverview", arguments:{bundleName:"com.omega_w_0823.hmservice"})
```

业务 payload 字段，即 `items[].data` 解析后的字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `dataCapabilities` | `DataCapabilityOverview[]` | 是 | 数据能力概述列表，只包含 `id` 和 `description`。 |
| `eventCapabilities` | `EventCapability[]` | 是 | 事件能力完整列表。 |
| `assetCandidates` | `AssetCapability[]` | 是 | 素材能力完整列表。 |

调用规则：

- 先调用该工具，再做候选选择。
- 不因 overview 中出现某能力就向用户承诺设备一定可用。
- 只从解析后的 `dataCapabilities`、`eventCapabilities`、`assetCandidates` 中选择候选；不要编造能力 ID、事件目标或素材 ID。

## getDataCapabilitySchemas

用途：按数据能力 ID 加载完整 `inputSchema`、`outputSchema`、依赖和 DataModel 骨架。

参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `dataCapabilityIds` | `Array<String>` | 是 | 需要加载完整 schema 的数据能力 ID 列表，至少 1 个。 |

调用示例：

```text
invoke(functionName:"getDataCapabilitySchemas", arguments:{bundleName:"com.omega_w_0823.hmservice", dataCapabilityIds:["ViewWeather"]})
```

业务 payload 字段，即 `items[].data` 解析后的字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `dataCapabilities` | `DataCapability[]` | 是 | 已找到的数据能力完整定义。 |
| `missingCapabilityIds` | `string[]` | 是 | 当前能力清单版本中未找到的数据能力 ID。 |

调用规则：

- 只传本轮从 overview 中选出的数据能力 ID。
- 如果某 ID 出现在 `missingCapabilityIds`，候选计划中移除该数据能力。
- `candidateDataBindings[].arguments` 只能使用对应 `inputSchema.properties` 中声明的字段。
- `writeResultTo` 优先使用能力 schema 提供的默认写入路径；没有默认值时使用 `/data/{semanticKey}`，且多个候选不得相同或互为父子。
- 默认不传输出字段投影；如果必须表达投影，只能使用 `candidateDataBindings[].updateModel`，且字段必须能由对应能力 `outputSchema` 推导。
- 不把完整 schema 暴露给用户。

## generateWidgetCard

用途：提交用户需求、候选数据绑定、候选事件、素材和静态标题文案建议，生成可下载的 HarmonyOS A2UI Form 卡片 artifact。

参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `userQuery` | `String` | 是 | 用户原始卡片需求。 |
| `size` | `String` | 否 | 主 Agent 建议尺寸；推荐 `"2x2"` 或 `"2x4"`。 |
| `title` | `String` | 是 | 主 Agent 建议的卡片标题；必须非空，会进入 TaskSpec 标题候选。 |
| `description` | `String` | 是 | 主 Agent 建议的卡片说明；必须非空，会进入 TaskSpec 摘要候选。 |
| `candidateDataBindings` | `Array<CandidateDataBinding>` | 否 | 候选数据能力调用列表。 |
| `candidateEventCandidates` | `Array<CandidateEventCandidate>` | 否 | 候选点击事件列表。 |
| `candidateAssetIds` | `Array<String>` | 否 | 候选素材 ID 列表。 |

`CandidateDataBinding`：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `capabilityId` | `string` | 是 | 数据能力 ID，必须来自已加载 schema。 |
| `arguments` | `object` | 是 | 能力入参，只能使用该能力 `inputSchema` 声明的字段。 |
| `writeResultTo` | `string` | 是 | 写入 DataModel 的 JSON Pointer，必须位于 `/data/` 下。 |
| `updateModel` | `object` | 否 | 可选输出字段投影结构，内部层级会原样写入 DataModel。拿不准时不要传。 |

`CandidateDataBinding` 结构模板：

```json
{
  "capabilityId": "ViewWeather",
  "arguments": {
    "districtName": "青浦区",
    "forecastDays": 1
  },
  "writeResultTo": "/data/weather"
}
```

结构规则：

- `candidateDataBindings` 必须是数组；数组元素必须是完整对象，不要只传能力 ID 字符串。
- `arguments` 必须是对象，即使只有一个参数也不要展开到 binding 顶层。
- `writeResultTo` 必须是 `/data/...` JSON Pointer；不要传 `data.weather`、`weather` 或空字符串。
- 不传 `required`、`outputSchema`、`inputSchema`、`candidateOutputFields` 等非内部类字段。

`CandidateEventCandidate`：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `capabilityId` | `string` | 是 | 事件能力 ID，必须来自 overview。 |
| `action` | `EventAction` | 是 | 包含 `call` 和 `args`；只能来自 overview 返回的事件能力说明。 |

`CandidateEventCandidate` / `EventAction` 结构模板：

```json
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
```

结构规则：

- `candidateEventCandidates` 必须是数组；数组元素必须同时包含 `capabilityId` 和 `action`。
- `action` 必须是对象，且必须包含 `call` 和 `args`；不要把 `call`、`args` 平铺到事件候选顶层。
- `args` 必须是对象；不要传字符串化 JSON。
- `action.call/action.args` 只能来自 overview 返回的事件能力说明或用户明确输入；无法安全填齐时移除整个事件候选。

调用示例：

```text
invoke(functionName:"generateWidgetCard", arguments:{bundleName:"com.omega_w_0823.hmservice", userQuery:"生成一个通勤卡片", title:"通勤助手", description:"天气日程速览", size:"2x4", candidateDataBindings:[...], candidateEventCandidates:[...], candidateAssetIds:[...]})
```

业务 payload 字段，即 `items[].data` 解析后的字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `status` | `String` | 是 | 生成状态；约定取值 `"success"`、`"degraded"`、`"unsupported"`、`"failed"`。 |
| `suggestSize` | `String` | 否 | 最终生成卡片尺寸；通常为 `"2x2"` 或 `"2x4"`。 |
| `message` | `string` | 是 | 可展示给用户的生成结果说明。 |
| `artifactUrl` | `string` | 否 | artifact 下载地址；成功或降级成功时返回。 |
| `artifactDigest` | `string` | 否 | artifact 内容摘要。 |
| `removedCapabilities` | `RemovedCapability[]` | 否 | 被微服务裁决移除的能力及原因。 |
| `errorCode` | `string` | 否 | 失败或不支持时返回的错误码。 |
| `artifact` | `object|null` | 否 | 调试时可选内联 artifact；生产默认不返回。 |
| `effectiveCapabilities` | `object` | 否 | 最终进入 artifact 的有效 data、event、asset 能力集合。 |

状态：

- `success`: 完整成功。
- `degraded`: 已生成可用卡片，但部分能力不可用或被移除。
- `unsupported`: 核心能力不可用且静态卡无价值。
- `failed`: 服务异常、生成失败或校验重试后仍失败。

调用规则：

- `title` 和 `description` 必须始终传非空字符串；无法从需求提炼时，使用“桌面卡片”和“信息速览”等稳定默认文案。
- `title`、`description` 不填入动态数据、隐私数据或不确定状态，不用于替代数据能力。
- `candidateDataBindings` 是候选，不是最终 CardSpec。
- 默认不要传字段投影；如果确实需要投影，只能传 `updateModel`，不要传 `candidateOutputFields`。
- `candidateEventCandidates` 每项必须同时包含 `capabilityId` 和完整 `action`。
- 如果事件 `action.call/args` 无法从 overview 返回内容或用户明确输入中安全填齐，不传该事件候选。
- `candidateAssetIds` 只传 overview 返回的素材 ID，不传自造资源路径。
- 不重试工具，除非工具返回明确可重试错误并要求重试。
- `success` 或 `degraded` 缺少有效 `artifactUrl` 时按 `failed` 处理，不生成替代产物。
- 任一工具不可用、调用失败或结果无法解析时终止本轮生成，不使用离线资料补足。
