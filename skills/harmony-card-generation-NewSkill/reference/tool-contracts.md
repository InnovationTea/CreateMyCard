# 微服务工具契约

只调用工具并传候选计划。真实设备能力裁决、最终 CardSpec、A2UI DSL 生成、校验、降级和 artifact 上传都由微服务完成。

## 调用总则

- 三个工具按顺序使用：
  1. `getWidgetCapabilityOverview`
  2. `getDataCapabilitySchemas`
  3. `generateWidgetCard`
- 必须使用 `invoke(functionName:"<toolName>", arguments:{bundleName:"<bundleName>", ...})` 调用工具。
- `arguments` 必须包含 `bundleName: "com.omega_w_0823.hmservice"`。
- `uid`、`device` 等环境字段由工具层自动拼接，不要手写或猜测。
- 工具参数以 `references/tools/` 下各工具 JSON 的 `arguments` 为准；不传 schema 未声明的字段。
- 不传 `slots`。

调用顺序：

```text
invoke(functionName:"getWidgetCapabilityOverview", arguments:{bundleName:"com.omega_w_0823.hmservice"})
invoke(functionName:"getDataCapabilitySchemas", arguments:{bundleName:"com.omega_w_0823.hmservice", dataCapabilityIds:[...]})
invoke(functionName:"generateWidgetCard", arguments:{bundleName:"com.omega_w_0823.hmservice", userQuery:"...", ...})
```

## 自动注入的设备上下文

工具层至少应注入：

```json
{
  "uid": "user-id",
  "device": {
    "deviceId": "device-id",
    "odid": "odid",
    "romVersion": "ALN-AL00 6.0.0.36",
    "ohosApiVersion": 36
  }
}
```

`DeviceContext` 的接口必填字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `romVersion` | `string` | 是 | ROM 版本，用于选择能力目录和协议 profile。 |
| `ohosApiVersion` | `integer` | 是 | OHOS API 版本，用于选择能力目录。 |
| `deviceId` | `string|null` | 否 | 设备 ID。 |
| `odid` | `string|null` | 否 | 设备 odid，IDS 查询优先使用。 |

## getWidgetCapabilityOverview

用途：获取当前设备版本可用的能力概述。数据能力只返回 `id` 和描述；事件能力、素材能力全量返回。

参数：无（`arguments: {}`）。`bundleName` 由 `invoke` 调用语法携带。

输出字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `apiVersion` | `string` | 是 | 接口版本。 |
| `capabilityRegistryVersion` | `string` | 是 | 本次实际使用的能力清单版本目录名。 |
| `dataCapabilities` | `DataCapabilityOverview[]` | 是 | 数据能力概述列表，只包含 `id` 和 `description`。 |
| `eventCapabilities` | `EventCapability[]` | 是 | 事件能力完整列表。 |
| `assetCandidates` | `AssetCapability[]` | 是 | 素材能力完整列表。 |

调用规则：

- 先调用该工具，再做候选选择。
- 不因 overview 中出现某能力就向用户承诺设备一定可用。
- 只从返回的 `dataCapabilities`、`eventCapabilities`、`assetCandidates` 中选择候选；不要编造能力 ID、事件目标或素材 ID。

## getDataCapabilitySchemas

用途：按数据能力 ID 加载完整 `inputSchema`、`outputSchema`、依赖和 DataModel 骨架。

参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `dataCapabilityIds` | `Array<String>` | 是 | 需要加载完整 schema 的数据能力 ID 列表，至少 1 个。 |

输出字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `apiVersion` | `string` | 是 | 接口版本。 |
| `capabilityRegistryVersion` | `string` | 是 | 本次实际使用的能力清单版本目录名。 |
| `dataCapabilities` | `DataCapability[]` | 是 | 已找到的数据能力完整定义。 |
| `missingCapabilityIds` | `string[]` | 是 | 当前能力清单版本中未找到的数据能力 ID。 |

调用规则：

- 只传本轮从 overview 中选出的数据能力 ID。
- 如果某 ID 出现在 `missingCapabilityIds`，候选计划中移除该数据能力。
- `candidateDataBindings[].arguments` 只能使用对应 `inputSchema.properties` 中声明的字段。
- `writeResultTo` 优先使用能力 schema 提供的默认写入路径；没有默认值时使用 `/data/{semanticKey}`，且多个候选不得相同或互为父子。
- 不把完整 schema 暴露给用户。

## generateWidgetCard

用途：提交用户需求、候选数据绑定、候选事件和素材，生成可下载的 HarmonyOS A2UI Form 卡片 artifact。

参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `userQuery` | `String` | 是 | 用户原始卡片需求。 |
| `size` | `String` | 否 | 主 Agent 建议尺寸；推荐 `"2x2"` 或 `"2x4"`。 |
| `candidateDataBindings` | `Array<CandidateDataBinding>` | 否 | 候选数据能力调用列表。 |
| `candidateEventCandidates` | `Array<CandidateEventCandidate>` | 否 | 候选点击事件列表。 |
| `candidateAssetIds` | `Array<String>` | 否 | 候选素材 ID 列表。 |

`CandidateDataBinding`：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `capabilityId` | `string` | 是 | 数据能力 ID，必须来自已加载 schema。 |
| `arguments` | `object` | 是 | 能力入参，只能使用该能力 `inputSchema` 声明的字段。 |
| `writeResultTo` | `string` | 是 | 写入 DataModel 的 JSON Pointer，必须位于 `/data/` 下。 |
| `updateModel` | `object` | 否 | 可选输出字段投影结构，内部层级会原样写入 DataModel。 |

`CandidateEventCandidate`：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `capabilityId` | `string` | 是 | 事件能力 ID，必须来自 overview。 |
| `action` | `EventAction` | 是 | 包含 `call` 和 `args`；只能来自 overview 返回的事件能力说明。 |

输出字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `apiVersion` | `string` | 是 | 接口版本。 |
| `status` | `String` | 是 | 生成状态；约定取值 `"success"`、`"degraded"`、`"unsupported"`、`"failed"`。 |
| `suggestSize` | `String` | 是 | 最终生成卡片尺寸；通常为 `"2x2"` 或 `"2x4"`。 |
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

- `candidateDataBindings` 是候选，不是最终 CardSpec。
- `candidateEventCandidates` 每项必须同时包含 `capabilityId` 和完整 `action`。
- 如果事件 `action.call/args` 无法从 overview 返回内容或用户明确输入中安全填齐，不传该事件候选。
- `candidateAssetIds` 只传 overview 返回的素材 ID，不传自造资源路径。
- 不重试工具，除非工具返回明确可重试错误并要求重试。
