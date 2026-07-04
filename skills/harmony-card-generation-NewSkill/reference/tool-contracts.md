# 微服务工具契约

主 Agent 只调用工具并传候选计划。工具层负责注入 ROM/App/device/uid/小艺版本等上下文；除非工具 schema 明确要求，主 Agent 不手写这些环境字段。

## 总原则

- 工具返回结构化 JSON；可以附加 `descriptionForLLM` 等便于主 Agent 筛选的文本字段。
- overview 只表示“可作为候选”，不是当前设备最终可用结论。
- 主 Agent 只生成候选，不生成最终 DSL、最终 CardSpec、最终 onClick 或 artifact。
- `candidateDataBindings`、`candidateEventCandidates`、`candidateAssetIds` 都允许被微服务删除、改写或规范化。
- 本版主 Agent 不传 `slots` 和 `options`；语义补充和用户约束保留在 `userQuery`，微服务使用默认 `allowDegradation: true` 和 `returnArtifactInline: false`。

## getWidgetCapabilityOverview

用途：获取当前环境可供候选筛选的能力概述。该结果不是最终可用能力结论，最终可用性由 `generateWidgetCard` 内部过滤决定。

建议输入：

```json
{
  "locale": "zh-CN"
}
```

典型输出：

```json
{
  "dataCapabilities": [
    {
      "id": "ViewWeather",
      "description": "查询当前天气、空气质量和未来预报。用户需要天气、温度、空气质量、未来预报时可选择。"
    }
  ],
  "eventCapabilities": [
    {
      "id": "event.open.weather",
      "call": "clickToDeeplink",
      "description": "打开天气应用",
      "actionTemplate": {
        "call": "clickToDeeplink",
        "args": {
          "bundleName": "",
          "abilityName": "",
          "uri": "hww://www.huawei.com/totemweather?enterType=share&cityCode="
        }
      }
    }
  ],
  "assetCandidates": [
    {
      "id": "asset.weather.rain",
      "src": "resources/base/media/icon_weather1.png",
      "description": "天气雨伞图标"
    }
  ]
}
```

调用规则：

- 先调该工具，再做候选选择。
- 不因 overview 中出现某能力就向用户承诺设备一定可用。
- overview 中不存在的能力、事件或素材不要编造。
- 若工具仍使用 `summary`/`functionCall` 等旧字段，按 `description`/`call` 的语义兼容读取，但生成候选计划时使用本文件的规范字段。

## getDataCapabilitySchemas

用途：按需加载被选中数据能力的完整 schema。只针对数据能力调用；事件能力和素材通常使用 overview 信息即可。

输入：

```json
{
  "dataCapabilityIds": ["ViewWeather", "calendar.events.search"]
}
```

典型输出字段：

```json
{
  "dataCapabilities": [
    {
      "id": "ViewWeather",
      "inputSchema": {},
      "outputSchema": {},
      "defaultWriteResultTo": "/data/weather"
    }
  ]
}
```

调用规则：

- 只传本轮候选数据能力 ID。
- 如果某 schema 没有返回，候选计划中移除该数据能力。
- 不把完整 schema 暴露给用户；schema 只用于构造候选计划。
- 若工具仍返回 `schemas`，按 `dataCapabilities` 等价处理。

## generateWidgetCard

用途：提交用户 query 和候选计划，由微服务完成能力过滤、最终 CardSpec、DSL 生成、校验、上传和状态话术。

输入形态：

```json
{
  "requestId": "uuid",
  "userQuery": "帮我做通勤卡片，包含天气和今日日程",
  "size": "2x4",
  "candidateDataBindings": [
    {
      "capabilityId": "ViewWeather",
      "arguments": {
        "districtName": "青浦区",
        "forecastDays": 1
      },
      "writeResultTo": "/data/weather",
      "required": false
    }
  ],
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
  ],
  "candidateAssetIds": ["asset.weather.rain"]
}
```

输出形态：

```json
{
  "status": "success",
  "artifactUrl": "https://obs.example/widget/uuid.json",
  "artifactDigest": "sha256:...",
  "suggestSize": "2x4",
  "userMessage": "已为你生成通勤卡片。",
  "removedCapabilities": [],
  "errorCode": ""
}
```

状态：

- `success`: 完整成功。
- `degraded`: 已生成可用卡片，但部分能力不可用或被移除。
- `unsupported`: 核心能力不可用且静态卡无价值。
- `failed`: 服务异常、生成失败或校验重试后仍失败。

常见 `errorCode`：

- `UNKNOWN_CAPABILITY`
- `ROM_VERSION_UNSUPPORTED`
- `APP_VERSION_UNSUPPORTED`
- `PACKAGE_NOT_INSTALLED`
- `PACKAGE_VERSION_TOO_LOW`
- `PROVIDER_NOT_FOUND`
- `INTENT_TARGET_NOT_FOUND`
- `PERMISSION_DENIED`
- `PERMISSION_UNKNOWN`
- `INVALID_ARGUMENTS`
- `WRITE_RESULT_CONFLICT`
- `NO_EFFECTIVE_CAPABILITY`
- `A2UI_GENERATION_FAILED`
- `VALIDATION_FAILED`
- `ARTIFACT_UPLOAD_FAILED`
- `TIMEOUT`

调用规则：

- `candidateDataBindings` 是候选，不是最终 CardSpec。
- `candidateEventCandidates` 是候选事件单数组，每项必须包含 `capabilityId`，可选包含 `action`。
- `candidateEventCandidates[].capabilityId` 必须来自 overview 的事件能力 ID。
- `candidateEventCandidates[].action` 必须来自 overview 的 `actionTemplate` 或已返回的完整事件描述；可以用用户 query 或 DataModel 路径填值，但不能编造 `call`、目标或参数名。
- 如果事件参数无法安全填齐，只传 `{ "capabilityId": "..." }`，把最终事件动作交给微服务生成。
- 微服务过滤某个事件能力时，删除整个 `candidateEventCandidates[]` 项；不要拆分 ID 和 action 后分别过滤。
- `candidateAssetIds` 是候选素材 ID，不传自造资源路径。
- 不传 `slots` 和 `options`；如果未来工具 schema 临时要求这两个字段，优先传空对象并推动接口改为可省略。
- 允许微服务删除、改写或规范化候选能力。
- 不重试工具，除非工具返回明确可重试错误并要求主 Agent 重试。
