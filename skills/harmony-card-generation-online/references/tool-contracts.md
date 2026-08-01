# 工具契约

本文档只定义工具调用、字段结构和返回解析。候选取舍见 [`candidate-planning.md`](candidate-planning.md)，用户回复见 [`response-policy.md`](response-policy.md)。

## 导航

- [调用总则](#调用总则)
- [微服务包装结果](#微服务包装结果)
- [getWidgetCapabilityOverview](#getwidgetcapabilityoverview)
- [getDataCapabilitySchemas](#getdatacapabilityschemas)
- [RequestDataPermission](#requestdatapermission)
- [generateWidgetCardCompactDsl](#generatewidgetcardcompactdsl)
- [编辑继承语义](#编辑继承语义)

## 调用总则

统一格式：

```text
invoke(functionName:"<toolName>", arguments:{bundleName:"com.omega_w_0823.hmservice", ...},"skillName":"harmony-card-generation-online")
```

每次调用前：

1. 从当前运行时 `tools` 找到与 frontmatter `bundleName + toolName` 完全匹配的工具；找不到时按工具不可用处理。
2. `functionName` 使用工具名，`arguments.bundleName` 使用工具声明的 bundleName，`skillName` 固定为 `harmony-card-generation-online`。
3. 除 `bundleName` 外，只传当前 `arguments.properties` 声明字段，并满足 `required`、类型、数组元素和嵌套结构。
4. 运行时 schema 是唯一入参依据。本文档、静态快照、示例和内部类与其冲突时，删除冲突字段。
5. 业务必填值缺失且用户可回答时先追问；工具接入或 schema 技术缺口直接终止。不得猜测、传 `null`、降格为字符串或把对象字符串化。
6. 能力 `arguments` 还必须匹配本轮 `getDataCapabilitySchemas` 返回的对应 `inputSchema`。

不要手写插件内部包络，例如 `content`、`deviceInfo`、`session`、`pagination`、`userAuth`、`utterance` 或 `version`；不要传未声明的 `uid`、`device`、`locale`、`protocolProfileId`、`options`、`slots`。

典型 create 顺序：

```text
getWidgetCapabilityOverview → getDataCapabilitySchemas（有数据候选时）→ RequestDataPermission（数据集合非空时）→ generateWidgetCardCompactDsl
```

## 微服务包装结果

三个微服务工具可能返回原始插件包络，也可能已归一化：

- 原始包络：先检查顶层 `errorCode/errorMessage/reply`。`errorCode` 非 `"0"` 表示失败；为 `"0"` 时从 `reply.items` 读取。
- 已归一化：直接从顶层 `items` 读取。
- `streamInfo` 只用于展示或调试，不替代结构化业务结果。

从 `items` 中优先选择 `tool` 等于当前工具名且包含 `data` 的项；没有 `tool` 时选择第一个包含 `data` 的项。`data` 是 JSON 字符串时先解析为对象，已经是对象时直接使用。

以下情况按工具异常终止：

- 没有可解析的 `items[].data`。
- `items[].error` 表示失败。
- payload 缺少本工具要求的结构，或字段类型非法。

工具层 `items[].status/errorCode/requestId` 不等于生成业务状态，也不向用户展示。`RequestDataPermission` 是端工具，直接读取其运行时输出，不套用微服务包装解析。

## getWidgetCapabilityOverview

调用：

```text
invoke(functionName:"getWidgetCapabilityOverview", arguments:{bundleName:"com.omega_w_0823.hmservice"},"skillName":"harmony-card-generation-online")
```

除 `bundleName` 外不传业务字段。业务 payload：

| 字段 | 类型 | 语义 |
| --- | --- | --- |
| `dataCapabilities` | `DataCapabilityOverview[]` | 当前用户实际可用的数据能力概述 |
| `unavailableCapabilities` | `string[]`，可选 | 云侧支持但用户本地不可用的数据能力 ID |
| `eventCapabilities` | `EventCapability[]` | 事件候选说明 |
| `assetCandidates` | `AssetCapability[]` | 素材候选说明 |

`unavailableCapabilities` 缺失或为 `[]` 时按空集合处理；存在但不是字符串数组时 payload 非法。数据候选只从 `dataCapabilities` 选择，不为不可用能力加载 schema。

## getDataCapabilitySchemas

调用：

```text
invoke(functionName:"getDataCapabilitySchemas", arguments:{bundleName:"com.omega_w_0823.hmservice", dataCapabilityIds:["ViewWeather"]},"skillName":"harmony-card-generation-online")
```

`dataCapabilityIds` 必须非空，只能来自本轮 overview 的 `dataCapabilities`。业务 payload：

| 字段 | 类型 | 语义 |
| --- | --- | --- |
| `dataCapabilities` | `DataCapability[]` | 已找到能力的完整 `inputSchema/outputSchema/defaultWriteResultTo` 等定义 |
| `missingCapabilityIds` | `string[]` | 当前版本未找到的候选 ID |

命中 `missingCapabilityIds` 的候选必须移除，并重新执行能力满足度门禁。完整 schema 不向用户展示。

## RequestDataPermission

调用：

```text
invoke(functionName:"RequestDataPermission", arguments:{bundleName:"com.omega_w_0823.hmservice", dataCapabilityIds:["ViewWeather", "GetCalendarEvents"]},"skillName":"harmony-card-generation-online")
```

`dataCapabilityIds` 必须是本轮最终、完整、去重后的数据能力集合；空集合不调用。调用后等待正常结果或明确的 invoke 异常结论；两者均未确定前不得生成或改变数据集合。

合法结构：

```json
{
  "result": {
    "stateOfPermission": false,
    "nonAuthStatus": [
      {
        "capabilityId": "GetAppUsageDurationAndPower",
        "authorized": false,
        "authType": "NON_CONFIGURABLE",
        "name": "应用使用时长",
        "settingsPath": "设置-健康使用设备-使用统计和管理"
      }
    ]
  }
}
```

判定：

- 只有 `stateOfPermission` 为 Boolean `true`、`nonAuthStatus` 缺失或为空数组，且所有返回权限项都未出现 Boolean `authorized:false` 时通过。
- `stateOfPermission:false` 或任一 `authorized:false` 一票否决，立即终止并拒绝继续生成。
- `nonAuthStatus` 非空时，每项必须是对象且 `name` 为非空字符串；`settingsPath` 缺失时按空字符串处理。按 [`response-policy.md`](response-policy.md) 引导手动授权。
- 工具不可用、invoke 抛错、超时、传输失败，或工具层明确报告执行失败时，按权限默认开启继续调用 `generateWidgetCardCompactDsl`。不要重试权限工具，不要构造 `stateOfPermission:true`，不要改变已检查的数据集合，也不要向用户展示异常或宣称权限已开启。
- 工具正常返回后，缺少 `result`、`stateOfPermission` 非 Boolean 或明细字段类型非法仍按结果非法终止，不适用默认开启。

用户回复只使用 `name` 和 `settingsPath`，不输出 `capabilityId`、`authType` 或 `authorized`。

## generateWidgetCardCompactDsl

运行时 schema 允许时使用以下业务字段：

| 字段 | create | edit | 说明 |
| --- | --- | --- | --- |
| `userQuery` | 必填 | 必填 | create 为原始需求；edit 只表达本轮修改 |
| `sourceArtifactUrl` | 不传 | 必填 | 目标卡片最近一次真实 artifact URL |
| `size` | 可选 | 仅修改时传 | 只使用 `2x2` / `2x4` |
| `title` | 条件必填 | 仅修改时传 | create 必须非空，建议不超过 8 字 |
| `description` | 条件必填 | 仅修改时传 | create 必须非空，建议不超过 12 字 |
| `candidateDataBindings` | 可选 | 替换数据类别时传 | edit 显式数组表示完整替换，`[]` 表示清空 |
| `candidateEventCandidates` | 可选 | 本期不修改 | 候选事件单数组 |
| `candidateAssetIds` | 可选 | 本期不修改 | overview 返回的素材 ID |

调用示例：

```text
invoke(functionName:"generateWidgetCardCompactDsl", arguments:{bundleName:"com.omega_w_0823.hmservice", userQuery:"生成天气卡片", title:"天气速览", description:"今日天气信息", size:"2x2", candidateDataBindings:[...], candidateEventCandidates:[...], candidateAssetIds:[...]},"skillName":"harmony-card-generation-online")
```

### CandidateDataBinding

仅在运行时 schema 声明 `candidateDataBindings` 时，按以下内部结构组装数组项：

```json
{
  "capabilityId": "ViewWeather",
  "arguments": {
    "districtName": "青浦区",
    "forecastDays": 1
  },
  "writeResultTo": "/data/weather",
  "candidateOutputFields": [
    "/location/districtName",
    "/current/temperatureText",
    "/current/condition"
  ]
}
```

- `capabilityId`、`arguments`、`writeResultTo` 必须完整。
- `candidateOutputFields` 可选，只能是能从同一能力 `outputSchema` 推导的 JSON Pointer 字符串数组。
- 不传能力 schema、`required`、`updateModel` 或其它未声明字段。

### CandidateEventCandidate

仅在运行时 schema 声明 `candidateEventCandidates` 时，按以下内部结构组装数组项：

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

每项必须同时包含能力 ID 和完整 `action.call/action.args`；无法从 overview 或用户明确输入中安全填齐时不传该候选。宽类型 `Object` 只允许补足该字段内部结构，不能扩展工具顶层参数。

### 业务结果

业务 payload 常用字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | `success/degraded/unsupported/failed` | 生成业务状态 |
| `message` | `string` | 仅完整 `success` 可作为成功说明 |
| `artifactUrl` | `string`，可选 | 真实产物地址 |
| `suggestSize` | `string`，可选 | 最终尺寸 |
| `removedCapabilities` | `array`，可选 | 被移除的能力及原因 |
| `effectiveCapabilities` | `object`，可选 | 最终有效的数据、事件和素材能力 |

只认可四种状态；其它值按 payload 非法。`success` / `degraded` 缺少合法 URL 时按其它异常。只要 payload 存在合法真实 URL，就按响应策略输出 `genWidgetResult`，状态只决定自然语言。

## 编辑继承语义

- 未指定目标时使用当前会话最近一次有效结果；指定目标时使用该卡片最近一次有效结果。
- 来源 URL 必须直接来自工具业务 payload，不从普通回复、示例或代码块猜测。
- edit 省略 `size/title/description` 或某类候选数组时，由微服务从来源继承并重新校验。
- 显式候选数组是编辑后的完整集合，不是增量；空数组表示清空。
- 来源 URL 为空、类型错误或运行时 schema 未声明 `sourceArtifactUrl` 时不得调用，也不得删除该字段后改走 create。
- 成功 edit 必须返回不同于来源的新 URL；缺失、无效或相同均按其它异常，且不更新默认来源。
- 本期 edit 不新增数据能力，不修改事件或素材候选；这些请求引导重新创建。
