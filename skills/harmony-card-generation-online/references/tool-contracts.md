# 微服务工具契约

只调用工具并传候选计划。真实设备能力裁决、最终 CardSpec、A2UI DSL 生成、校验、降级和 artifact 上传都由微服务完成。

## 调用总则

- create 模式通常按顺序使用 `getWidgetCapabilityOverview`、按需使用 `getDataCapabilitySchemas`，最后调用 `generateWidgetCard`。
- edit 模式按修改类型分流：纯视觉、布局、文案或尺寸修改直接调用 `generateWidgetCard`；删除数据能力或修改能力参数时才重新调用能力概述和数据 schema。
- 每次调用前先执行用户确认门禁：如果当前已知信息中存在用户可回答、且会影响核心卡片意图、候选选择或业务入参的未决项，先追问并等待用户回答；回答前不得调用任何工具。能安全推导或有明确默认值的信息不重复确认，微服务负责的设备能力裁决和内部技术字段不向用户询问。
- 必须使用 `invoke(functionName:"<toolName>", arguments:{bundleName:"<bundleName>", ...},"skillName":"harmony-card-generation-online")` 调用工具；`skillName` 必须与当前 Skill frontmatter 的 `name` 完全一致，不得省略、传空字符串或使用显示名称。
- `arguments` 必须包含 `bundleName: "com.omega_w_0823.hmservice"`。
- 每次调用前必须读取当前运行时对应工具的 schema；除 `bundleName` 外，只传其 `arguments.properties` 中声明的业务字段，并满足 `required`、类型、数组元素类型和已声明嵌套结构。
- 当前运行时 schema 是调用入参的唯一依据。本文件、Skill 文案、参考 JSON、历史示例或内部类结构与其冲突时，以当前运行时 schema 为准；schema 未声明字段一律删除。
- 对外工具 schema 中的 `Array<Object>` / `Object` 是插件层宽类型。只有 schema 已声明对应数组或对象字段时，才按本文件定义的内部类结构组装其值；内部类结构不能授权新增 schema 外的顶层字段。
- 必填字段无法可靠补齐时先区分原因：缺少用户可提供的核心业务值则追问并等待回答；工具接入、schema 不兼容或用户无法确认的技术缺口则停止调用。任何情况都不猜测字段、不传 `null` 占位、不把对象字符串化规避校验。
- 不手写内部 WebSocket 包络字段，例如 `content`、`deviceInfo`、`session`、`pagination`、`userAuth`、`utterance`、`version`。
- 不手写或猜测 `uid`、`device`、`locale`、`protocolProfileId`、`capabilityRegistryVersion`、`options` 等未在当前对外工具 schema 中声明的字段。
- 不传 `slots`。

调用顺序：

```text
invoke(functionName:"getWidgetCapabilityOverview", arguments:{bundleName:"com.omega_w_0823.hmservice"},"skillName":"harmony-card-generation-online")
invoke(functionName:"getDataCapabilitySchemas", arguments:{bundleName:"com.omega_w_0823.hmservice", dataCapabilityIds:[...]},"skillName":"harmony-card-generation-online")
invoke(functionName:"generateWidgetCard", arguments:{bundleName:"com.omega_w_0823.hmservice", userQuery:"...", title:"...", description:"...", ...},"skillName":"harmony-card-generation-online")
invoke(functionName:"generateWidgetCard", arguments:{bundleName:"com.omega_w_0823.hmservice", userQuery:"背景改成蓝色", sourceArtifactUrl:"https://obs.example/widget/previous.json"},"skillName":"harmony-card-generation-online")
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
- `getWidgetCapabilityOverview` 的 `data` 解析后应包含 `dataCapabilities`、`eventCapabilities`、`assetCandidates`，并可选包含 `unavailableCapabilities`；该字段存在时必须是字符串数组，缺失或为 `[]` 时按空集合处理。
- `getDataCapabilitySchemas` 的 `data` 解析后应包含 `dataCapabilities`、`missingCapabilityIds`。
- `generateWidgetCard` 的 `data` 解析后应包含业务 `status`、`message`，成功或降级时还应包含真实 `artifactUrl`。`message` 只可在完整 `success` 时作为正常成功说明；其它状态按 `response-policy.md` 使用固定话术。
- `generateWidgetCard` 业务 `status` 为 `success` 或 `degraded` 且存在真实 `artifactUrl` 时，最终用户回复必须按 `response-policy.md` 输出 `genWidgetResult` JSON 代码块，将 `artifactUrl` 写入 `result` 字段；若 `success` 同时存在由 `unavailableCapabilities`、`missingCapabilityIds` 或 `removedCapabilities` 证明的用户提及数据缺失，也按部分数据不支持回复。
- 如果没有可解析的 `data`，或 `items[].error` 表示工具失败，按工具调用异常处理，不输出 `genWidgetResult`。
- 用户可见回复不暴露 `items`、`requestId`、`errorCode`、工具层 `status` 或原始 `data` 字符串。

## getWidgetCapabilityOverview

用途：获取当前设备版本可用的能力概述。数据能力只返回 `id` 和描述；事件能力、素材能力全量返回。

参数：无。除 `bundleName` 外不传其它字段。

调用示例：

```text
invoke(functionName:"getWidgetCapabilityOverview", arguments:{bundleName:"com.omega_w_0823.hmservice"},"skillName":"harmony-card-generation-online")
```

业务 payload 字段，即 `items[].data` 解析后的字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `dataCapabilities` | `DataCapabilityOverview[]` | 是 | 数据能力概述列表，只包含 `id` 和 `description`。 |
| `unavailableCapabilities` | `string[]` | 否 | 当前不可用的数据能力 ID；缺失或为 `[]` 时不额外排除，非空时在候选筛选前从 `dataCapabilities` 中排除。 |
| `eventCapabilities` | `EventCapability[]` | 是 | 事件能力完整列表。 |
| `assetCandidates` | `AssetCapability[]` | 是 | 素材能力完整列表。 |

调用规则：

- 调用前确认用户的核心卡片主题和明确要求不存在待追问项。
- 先调用该工具，再做候选选择。
- 不因 overview 中出现某能力就向用户承诺设备一定可用。
- `unavailableCapabilities` 存在且非空时，先从 `dataCapabilities` 中排除其中 ID；同一 ID 同时出现时以不可用为准。字段缺失或为空数组时不额外排除。
- 不为不可用能力调用 `getDataCapabilitySchemas`，也不把它写入 `candidateDataBindings`。
- 只从过滤后的 `dataCapabilities`、`eventCapabilities`、`assetCandidates` 中选择候选；不要编造能力 ID、事件目标或素材 ID。

## getDataCapabilitySchemas

用途：按数据能力 ID 加载完整 `inputSchema`、`outputSchema`、依赖和 DataModel 骨架。

参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `dataCapabilityIds` | `Array<String>` | 是 | 需要加载完整 schema 的数据能力 ID 列表，至少 1 个。 |

调用示例：

```text
invoke(functionName:"getDataCapabilitySchemas", arguments:{bundleName:"com.omega_w_0823.hmservice", dataCapabilityIds:["ViewWeather"]},"skillName":"harmony-card-generation-online")
```

业务 payload 字段，即 `items[].data` 解析后的字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `dataCapabilities` | `DataCapability[]` | 是 | 已找到的数据能力完整定义。 |
| `missingCapabilityIds` | `string[]` | 是 | 当前能力清单版本中未找到的数据能力 ID。 |

调用规则：

- 调用前确认候选能力选择不依赖未解决的用户歧义；存在会改变核心候选的选择时先追问并等待回答。
- 只传本轮从 overview 中选出且不在 `unavailableCapabilities` 中的数据能力 ID。
- 如果某 ID 出现在 `missingCapabilityIds`，候选计划中移除该数据能力。
- `candidateDataBindings[].arguments` 只能使用对应 `inputSchema.properties` 中声明的字段。
- `writeResultTo` 优先使用能力 schema 提供的默认写入路径；没有默认值时使用 `/data/{semanticKey}`，且多个候选不得相同或互为父子。
- `candidateDataBindings[].candidateOutputFields` 为可选 JSON Pointer 字符串数组；传入时每一项必须能由对应能力 `outputSchema` 推导。无需投影时省略。
- 不再传 `candidateDataBindings[].updateModel`。
- 不把完整 schema 暴露给用户。

## generateWidgetCard

用途：提交用户需求和候选计划首次生成卡片，或携带上一版 artifact URL 连续编辑卡片。

参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `userQuery` | `String` | 是 | create 模式为原始需求；edit 模式只表达本轮修改。 |
| `sourceArtifactUrl` | `String` | 否 | 上一版完整 artifact 的真实 URL；缺失表示 create，合法非空值表示 edit。 |
| `size` | `String` | 否 | 主 Agent 建议尺寸；推荐 `"2x2"` 或 `"2x4"`。 |
| `title` | `String` | 条件必填 | create 模式必须非空；edit 模式省略时继承来源 CardSpec，显式传入时替换。 |
| `description` | `String` | 条件必填 | create 模式必须非空；edit 模式省略时继承来源 CardSpec，显式传入时替换。 |
| `candidateDataBindings` | `Array<CandidateDataBinding>` | 否 | 候选数据能力调用列表。 |
| `candidateEventCandidates` | `Array<CandidateEventCandidate>` | 否 | 候选点击事件列表。 |
| `candidateAssetIds` | `Array<String>` | 否 | 候选素材 ID 列表。 |

`CandidateDataBinding`：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `capabilityId` | `string` | 是 | 数据能力 ID，必须来自已加载 schema。 |
| `arguments` | `object` | 是 | 能力入参，只能使用该能力 `inputSchema` 声明的字段。 |
| `writeResultTo` | `string` | 是 | 写入 DataModel 的 JSON Pointer，必须位于 `/data/` 下。 |
| `candidateOutputFields` | `string[]` | 否 | 可选候选展示字段 JSON Pointer；每一项必须能从对应能力 `outputSchema` 推导。 |

`CandidateDataBinding` 结构模板：

```json
{
  "capabilityId": "ViewWeather",
  "arguments": {
    "districtName": "青浦区",
    "forecastDays": 1
  },
  "writeResultTo": "/data/weather",
  "candidateOutputFields": [
    "/location/name",
    "/current/temperatureText",
    "/current/weatherText"
  ]
}
```

结构规则：

- `candidateDataBindings` 必须是数组；数组元素必须是完整对象，不要只传能力 ID 字符串。
- `arguments` 必须是对象，即使只有一个参数也不要展开到 binding 顶层。
- `writeResultTo` 必须是 `/data/...` JSON Pointer；不要传 `data.weather`、`weather` 或空字符串。
- `candidateOutputFields` 只能传字符串数组，元素必须是合法 JSON Pointer，并逐项存在于对应能力 `outputSchema`；无法确认时省略。
- 不传 `required`、`outputSchema`、`inputSchema`、`updateModel` 等 schema 未声明字段。

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
invoke(functionName:"generateWidgetCard", arguments:{bundleName:"com.omega_w_0823.hmservice", userQuery:"生成一个通勤卡片", title:"通勤助手", description:"天气日程速览", size:"2x4", candidateDataBindings:[...], candidateEventCandidates:[...], candidateAssetIds:[...]},"skillName":"harmony-card-generation-online")
```

edit 模式示例：

```text
invoke(functionName:"generateWidgetCard", arguments:{bundleName:"com.omega_w_0823.hmservice", userQuery:"整体改成蓝色风格", sourceArtifactUrl:"https://obs.example/widget/previous.json"},"skillName":"harmony-card-generation-online")
```

编辑语义：

- 用户没有指定目标卡片时，使用当前会话最近一次 `success` / `degraded` 业务 payload 的真实 `artifactUrl`。
- 用户明确指定某张卡片时，使用与该目标对应的最近结果；只有目标无法对应时才追问。
- `sourceArtifactUrl` 必须直接来自工具业务 payload，不从普通回复、示例或 `genWidgetResult` 代码块猜测。
- edit 模式省略 `size`、`title`、`description` 或某类候选数组时，微服务从来源 artifact 继承并重新校验。
- edit 模式显式传入候选数组时，该数组表示编辑后的完整集合，不是增量；`[]` 表示清空。
- 来源 URL 为空、`null`、类型错误，或当前运行时 schema 未声明 `sourceArtifactUrl` 时不得调用；不得删除字段后按 create 模式继续。
- 每次编辑成功必须返回新的真实 `artifactUrl`，且不得等于 `sourceArtifactUrl`；否则按 `failed` 处理。来源 artifact 保持不变。

业务 payload 字段，即 `items[].data` 解析后的字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `status` | `String` | 是 | 生成状态；约定取值 `"success"`、`"degraded"`、`"unsupported"`、`"failed"`。 |
| `suggestSize` | `String` | 否 | 最终生成卡片尺寸；通常为 `"2x2"` 或 `"2x4"`。 |
| `message` | `string` | 是 | 微服务生成结果说明；仅完整 `success` 可直接展示，`degraded`、`unsupported`、`failed` 不透传。 |
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

- 调用前再次检查核心目标、地点、日期/时间范围、动作目标和能力必填业务参数；存在用户可确认的缺失或歧义时先追问并等待回答，再重建候选计划。
- create 模式的 `title` 和 `description` 必须传非空字符串；无法从需求提炼时，使用“桌面卡片”和“信息速览”等稳定默认文案。edit 模式只有用户明确修改时才传，未修改时省略。
- `title`、`description` 不填入动态数据、隐私数据或不确定状态，不用于替代数据能力。
- `candidateDataBindings` 是候选，不是最终 CardSpec。
- 无需字段投影时省略 `candidateOutputFields`；需要投影时只传可由对应 `outputSchema` 推导的 JSON Pointer 字符串数组。
- 不传 `updateModel`。
- `candidateEventCandidates` 每项必须同时包含 `capabilityId` 和完整 `action`。
- 如果事件 `action.call/args` 无法从 overview 返回内容或用户明确输入中安全填齐，不传该事件候选。
- `candidateAssetIds` 只传 overview 返回的素材 ID，不传自造资源路径。
- 纯视觉、布局、文案或尺寸编辑不重新调用 overview/schema，也不重复传未修改的候选数组。
- 删除已有数据能力或修改其参数时，传编辑后的完整 `candidateDataBindings`；无法从同一会话可靠恢复完整集合时停止编辑，不发送可能误删其它能力的不完整数组。
- 本期 edit 模式不新增数据能力，也不修改事件或素材候选；这类需求建议重新创建卡片。
- 不重试工具，除非工具返回明确可重试错误并要求重试。
- `success` 或 `degraded` 缺少有效 `artifactUrl` 时按 `failed` 处理，不生成替代产物。
- 任一工具不可用、调用失败或结果无法解析时终止本轮生成，不使用离线资料补足。
- edit 模式失败时保留来源 URL 作为当前默认卡片，不输出新结果标记，并使用统一的其它异常话术，不追加编辑专属说明。

面向端侧的非完整满足或异常回复固定映射如下：

- 部分数据不支持：`degraded` 有有效 `artifactUrl`，或 `success` 有有效 `artifactUrl` 但本轮 `unavailableCapabilities`、`missingCapabilityIds` 或 `removedCapabilities` 已表明用户提及的部分数据不可用。使用固定的部分数据不支持话术并输出真实 `genWidgetResult`。
- 整体不支持：`unsupported`。使用固定的整体不支持话术，不输出 `genWidgetResult`。
- 其它异常：`failed`、工具异常、payload 异常，或成功/降级状态缺少有效 `artifactUrl`。使用固定的其它异常话术，不输出 `genWidgetResult`。

三类固定话术及 `XX` 提炼规则以 `response-policy.md` 为准。
