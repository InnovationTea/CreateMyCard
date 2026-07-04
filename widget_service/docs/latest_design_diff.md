# 最新云侧方案对比说明

本文档对比 `docs/云侧方案设计.md` 与当前微服务实现，并记录本次已经按最新方案调整的点。

## 1. 工具形态

分歧点：

- 旧实现：对外暴露 `getWidgetCapabilityOverview`、`getDataCapabilitySchemas`、`generateWidgetCard` 三个工具名，其中生成接口主走 WebSocket。
- 最新方案：对外抽象为一个工具 `widgetCardService`，通过 `operation` 分发三个能力。

当前处理：

- 仅保留 `WS /api/v1/ws/tools/widgetCardService` 作为服务请求入口。
- 旧 HTTP 接口已移除。

## 2. 生成入参

分歧点：

- 旧实现：事件候选支持 `candidateEventCapabilityIds`、`candidateEventActions`、`candidateEventCapabilities`。
- 最新方案：只使用 `candidateEventCandidates`，每项同时携带 `capabilityId` 和 `action`。

当前处理：

- 公共生成请求已改为 `candidateEventCandidates`。
- 微服务内部会把每个候选转换为带 `id/call/args` 的内部 `EventAction`。

## 3. options 字段

分歧点：

- 旧实现：外部可传 `options.allowDegradation` 和 `options.returnArtifactInline`。
- 最新方案：主 Agent 不传 `options`，微服务默认 `allowDegradation=true`、`returnArtifactInline=false`。

当前处理：

- `widgetCardService` 统一工具入口不暴露 `options`。
- 内部 `GenerateWidgetCardRequest` 暂时保留 `options`，便于服务内部测试和后续调试。

## 4. 自动注入上下文

分歧点：

- 旧实现：本地测试通常手动传 `appVersion/romVersion/device/uid`。
- 最新方案：工具层自动注入设备、用户、ROM/App/小艺版本信息。

当前处理：

- 请求模型保留这些字段和默认值，本地可直接测试。
- 生产调用时由工具层注入，主 Agent 不需要主动填写。

## 5. 最新推荐调用方式

能力概述：

```json
{
  "operation": "getWidgetCapabilityOverview"
}
```

加载数据能力 schema：

```json
{
  "operation": "getDataCapabilitySchemas",
  "dataCapabilityIds": ["ViewWeather"]
}
```

生成卡片：

```json
{
  "operation": "generateWidgetCard",
  "userQuery": "帮我做通勤卡片，包含天气和今日日程",
  "size": "2x4",
  "candidateDataBindings": [
    {
      "capabilityId": "ViewWeather",
      "arguments": {
        "districtName": "青浦区",
        "forecastDays": 1
      },
      "writeResultTo": "/data/weather"
    }
  ],
  "candidateEventCandidates": [
    {
      "capabilityId": "event.open.weather",
      "action": {
        "call": "clickToDeeplink",
        "args": {
          "uri": "hww://weather"
        }
      }
    }
  ],
  "candidateAssetIds": ["asset.drop_1"]
}
```
