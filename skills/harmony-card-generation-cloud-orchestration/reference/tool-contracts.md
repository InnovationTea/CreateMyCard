# 微服务工具契约

主 Agent 只调用工具并传候选计划。工具层负责注入 ROM/App/device/uid 等上下文；除非工具 schema 明确要求，主 Agent 不手写这些环境字段。

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
      "name": "天气",
      "summary": "查询当前天气、空气质量和未来预报",
      "tags": ["weather", "location"]
    }
  ],
  "eventCapabilities": [
    {
      "id": "clickToDeeplink.weather",
      "functionCall": "clickToDeeplink",
      "summary": "打开天气应用"
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
  "schemas": [
    {
      "id": "ViewWeather",
      "inputSchema": {},
      "outputSchema": {},
      "defaultWriteResultTo": "/data/weather",
      "dataModelSkeleton": {
        "data": {
          "weather": {
            "location": {},
            "current": {},
            "daily": [],
            "updatedAt": ""
          }
        }
      }
    }
  ]
}
```

调用规则：

- 只传本轮候选数据能力 ID。
- 如果某 schema 没有返回，候选计划中移除该数据能力。
- 不把完整 schema 暴露给用户；schema 只用于构造候选计划。

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
  "candidateEventCapabilityIds": ["clickToDeeplink.weather"],
  "candidateAssetIds": ["asset.weather.rain"],
  "slots": {
    "districtName": "青浦区",
    "timeRange": "today"
  },
  "options": {
    "allowDegradation": true,
    "returnMode": "obs_url"
  }
}
```

输出形态：

```json
{
  "status": "success",
  "artifactUrl": "https://obs.example/widget/uuid.json",
  "artifactDigest": "sha256:...",
  "suggestSize": "2x4",
  "userMessage": "已为你生成通勤卡片。"
}
```

状态：

- `success`: 完整成功。
- `degraded`: 已生成可用卡片，但部分能力不可用或被移除。
- `unsupported`: 核心能力不可用且静态卡无价值。
- `failed`: 服务异常、生成失败或校验重试后仍失败。

调用规则：

- `candidateDataBindings` 是候选，不是最终 CardSpec。
- `candidateEventCapabilityIds` 是候选事件 ID，不传自造 `onClick.args`。
- `candidateAssetIds` 是候选素材 ID，不传自造资源路径。
- 允许微服务删除、改写或规范化候选能力。
- 不重试工具，除非工具返回明确可重试错误并要求主 Agent 重试。
