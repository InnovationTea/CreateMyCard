# 微服务工具契约

只调用工具并传候选计划。真实设备能力裁决、最终 CardSpec、A2UI DSL 生成、校验、降级和 artifact 上传都由微服务完成。

## 调用总则

- create 模式通常按顺序使用 `getWidgetCapabilityOverview`、按需使用 `getDataCapabilitySchemas`，再对最终数据能力集合调用 `RequestDataPermission`；权限通过或本轮无需权限检查后，调用 `generateWidgetCard`。
- edit 模式按修改类型分流：纯视觉、布局、文案或尺寸修改不重新调用能力概述和数据 schema，但仍须对来源卡片的有效数据能力调用 `RequestDataPermission`；删除数据能力或修改能力参数时，重新调用能力概述和数据 schema，再检查编辑后的完整数据能力集合。
- 需求适配门禁判定为追问或结束并引导时，不调用任何工具。能力概述后无法满足核心数据、核心动作或用户声明必须使用的素材，且不能形成满足原意图的静态或入口卡时，不调用 schema 或生成接口；schema 移除最后一个核心能力时不调用生成接口。
- 核心内容可满足而仅次要数据、动作或非核心素材不可用时，先按回复策略告知调整，再自动继续工具链，不等待用户确认。
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
invoke(functionName:"RequestDataPermission", arguments:{bundleName:"com.omega_w_0823.hmservice", dataCapabilityIds:[...]},"skillName":"harmony-card-generation-online")
invoke(functionName:"generateWidgetCard", arguments:{bundleName:"com.omega_w_0823.hmservice", userQuery:"...", title:"...", description:"...", ...},"skillName":"harmony-card-generation-online")
```

## 包装输出

三个微服务工具通常返回包装结构。如果运行环境返回原始插件包络，则先处理顶层 `errorCode/errorMessage/reply`：`errorCode` 非 `"0"` 时按工具失败处理；`errorCode` 为 `"0"` 时从 `reply` 中继续读取 `streamInfo/items`。如果运行环境已归一化，则直接读取顶层 `streamInfo/items`。端工具 `RequestDataPermission` 按当前运行时输出 schema 读取 `result.stateOfPermission` 和可选的 `result.nonAuthStatus`，不套用微服务业务状态解析规则。

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
- `generateWidgetCard` 的 `data` 解析后应包含业务 `status`、`message`，成功或降级时还应包含真实 `artifactUrl`。`message` 只可在完整 `success` 时作为正常成功说明；其它状态按 `references/response-policy.md` 使用受控话术。
- `generateWidgetCard` 业务 payload 只要存在合法真实 `artifactUrl`，最终回复就必须按 `references/response-policy.md` 输出 `genWidgetResult` JSON 代码块，将 URL 写入 `result` 字段；`degraded` 也不得省略。业务 `status` 只决定配套自然语言；没有 URL 时不得输出标记。若 `success` 同时存在由 `unavailableCapabilities`、`missingCapabilityIds`、`removedCapabilities` 或本轮规划证明的用户需求缺失，也按数据、动作、素材或混合缺失回复。
- 如果没有可解析的 `data`，或 `items[].error` 表示工具失败，按工具调用异常处理，不输出 `genWidgetResult`。
- 生成前合法结束不属于工具失败，不伪造工具包络、生成业务状态或 `artifactUrl`。
- 用户可见回复不暴露 `items`、`requestId`、`errorCode`、工具层 `status` 或原始 `data` 字符串。

## getWidgetCapabilityOverview

用途：返回当前用户实际可用的数据能力、云侧支持但用户本地不可用的数据能力 ID，以及事件和素材概述。

参数：无。除 `bundleName` 外不传其它字段。

调用示例：

```text
invoke(functionName:"getWidgetCapabilityOverview", arguments:{bundleName:"com.omega_w_0823.hmservice"},"skillName":"harmony-card-generation-online")
```

业务 payload 字段，即 `items[].data` 解析后的字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `dataCapabilities` | `DataCapabilityOverview[]` | 是 | 当前用户实际可用的数据能力，只包含 `id` 和 `description`。 |
| `unavailableCapabilities` | `string[]` | 否 | 云侧支持但用户本地不可用的数据能力 ID；本期不返回原因。 |
| `eventCapabilities` | `EventCapability[]` | 是 | 事件能力完整列表。 |
| `assetCandidates` | `AssetCapability[]` | 是 | 素材能力完整列表。 |

调用规则：

- 调用前确认用户的核心卡片主题和明确要求不存在待追问项。
- 先调用该工具，再做候选选择。
- `dataCapabilities` 已完成用户实际可用性裁决，但不代表最终一定生成成功。
- 不为不可用能力调用 `getDataCapabilitySchemas`，也不把它写入 `candidateDataBindings`。
- 数据候选只从 `dataCapabilities` 中选择；`unavailableCapabilities` 本期仅适用于数据能力，事件和素材沿用各自返回列表。
- 解析成功后执行能力满足度门禁。核心数据、核心动作或用户声明必须使用的素材无法满足，且不能形成满足原意图的静态或入口卡时，停止后续调用，并基于本轮概述提供相近建议。
- 数据候选为空但用户原本只要求 overview 中可安全填齐的静态入口或动作时，可以继续调用 `generateWidgetCard`。

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
- 只传本轮从 `dataCapabilities` 中选出的数据能力 ID。
- 如果某 ID 出现在 `missingCapabilityIds`，候选计划中移除该数据能力。
- 移除后重新执行能力满足度门禁；最后一个核心能力被移除且不存在满足原意图的静态或入口价值时，不调用 `generateWidgetCard`。
- `candidateDataBindings[].arguments` 只能使用对应 `inputSchema.properties` 中声明的字段。
- `writeResultTo` 优先使用能力 schema 提供的默认写入路径；没有默认值时使用 `/data/{semanticKey}`，且多个候选不得相同或互为父子。
- `candidateDataBindings[].candidateOutputFields` 为可选 JSON Pointer 字符串数组；传入时每一项必须能由对应能力 `outputSchema` 推导。无需投影时省略。
- 不再传 `candidateDataBindings[].updateModel`。
- 不把完整 schema 暴露给用户。

## RequestDataPermission

用途：在 `generateWidgetCard` 前判断本轮卡片将使用的数据能力是否有权限。

调用：

```text
invoke(functionName:"RequestDataPermission", arguments:{bundleName:"com.omega_w_0823.hmservice", dataCapabilityIds:["ViewWeather", "GetCalendarEvents"]},"skillName":"harmony-card-generation-online")
```

调用规则：

- `dataCapabilityIds` 必须是本轮最终数据能力集合，去重后传入；create 和数据类 edit 取最终 `candidateDataBindings[].capabilityId`，纯视觉、布局、文案或尺寸 edit 取目标卡片最近一次有效业务 payload 的 `effectiveCapabilities.data`。
- 无法从会话中的有效结果或完整候选链可靠恢复 edit 的数据能力集合时停止编辑，不读取来源 artifact 猜测。
- `dataCapabilityIds` 为空时不调用；这表示本轮卡片不使用动态数据。
- 调用后必须等待并解析权限结果；在得到明确结果前不得调用 `generateWidgetCard`，也不得继续修改待生成的数据能力集合。
- 当前工具快照的输出包含 `result.stateOfPermission: Boolean` 和可选的 `result.nonAuthStatus: Array<Object>`。只有 `stateOfPermission` 为 `true`、`nonAuthStatus` 缺失或为空数组，且返回中的权限项均未出现 Boolean `false` 时才允许继续。
- 权限结果一票否决：`stateOfPermission` 为 `false`，或任一权限项的 Boolean `authorized` 为 `false`，立即结束任务并拒绝继续生成，不调用生成工具。`nonAuthStatus` 非空时每项读取 `name` 和 `settingsPath`；`name` 用作用户可见授权名称，非空 `settingsPath` 用作手动授权路径。
- 用户回复不输出 `capabilityId`、`authType` 或 `authorized`。同名项去重；路径非空时使用“请前往「{settingsPath}」，为「{name}」开启权限，然后再试。”，路径为空时使用“请为「{name}」开启权限，然后再试。”。
- `stateOfPermission` 为 `false` 且 `nonAuthStatus` 缺失或为空数组时，使用通用权限不可用回复。缺少 `result`、`stateOfPermission` 非 Boolean、`nonAuthStatus` 非数组、数组项非对象、`name` 为空、字段类型非法、工具不可用或调用失败均按其它异常终止，不调用生成工具。
- 权限通过后只能继续执行已检查的同一组数据能力；集合或数据 binding 发生变化时必须重新调用。

## generateWidgetCard

用途：提交用户需求和候选计划首次生成卡片，或携带上一版 artifact URL 连续编辑卡片。

参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `userQuery` | `String` | 是 | create 模式为原始需求；edit 模式只表达本轮修改。 |
| `sourceArtifactUrl` | `String` | 否 | 上一版完整 artifact 的真实 URL；缺失表示 create，合法非空值表示 edit。 |
| `size` | `String` | 否 | 建议尺寸，只使用 `"2x2"` 或 `"2x4"`；用户未指定时优先能够满足核心需求的 `"2x2"`，只有必须保留的核心内容无法在 `"2x2"` 中成立时才使用 `"2x4"`。 |
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
invoke(functionName:"generateWidgetCard", arguments:{bundleName:"com.omega_w_0823.hmservice", userQuery:"生成一个通勤卡片", title:"通勤助手", description:"天气日程速览", size:"2x2", candidateDataBindings:[...], candidateEventCandidates:[...], candidateAssetIds:[...]},"skillName":"harmony-card-generation-online")
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
- create 模式的尺寸遵循最小充分原则：用户未指定时先选择 `2x2`；只有必须保留的核心内容、受保护文本、必要热区、关键并列关系或关键媒体无法在 `2x2` 布局预算内成立时才选择 `2x4`。信息较多、横版更舒展或存在两个数据能力本身不构成升级理由；用户明确指定尺寸时优先尊重。
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
- edit 请求新增数据能力、修改事件或素材候选时，不调用编辑接口，按回复策略给出重新创建新卡片的可直接复述需求。
- 不重试工具，除非工具返回明确可重试错误并要求重试。
- `success` 或 `degraded` 缺少有效 `artifactUrl` 时按 `failed` 处理，不生成替代产物。
- 任一必要工具不可用、调用失败或结果无法解析时终止本轮生成，不使用离线资料补足。
- edit 模式失败且没有合法新 URL 时保留来源 URL 作为当前默认卡片，不输出新结果标记，并使用统一的其它异常话术，不追加编辑专属说明。

面向端侧的非完整满足或异常回复映射如下：

- URL 输出规则：业务 payload 只要有合法真实 `artifactUrl` 就必须输出 `genWidgetResult`；`degraded` 不得省略，状态只影响自然语言。
- 部分满足：`degraded` 有有效 `artifactUrl`，或 `success` 有有效 `artifactUrl` 但本轮已知部分用户需求缺失。按数据、动作、素材或混合缺失使用受控话术并输出真实 `genWidgetResult`。
- 整体不支持：`unsupported`。使用受控核心句，追加最多 3 条安全建议；没有合法 URL 时不输出 `genWidgetResult`。
- 其它异常：`failed`、必要工具异常、payload 异常，或成功/降级状态缺少有效 `artifactUrl`。使用固定的其它异常话术；没有合法 URL 时不输出 `genWidgetResult`。

生成前与生成后话术、名称提炼和推荐规则以 `references/response-policy.md` 为准。
