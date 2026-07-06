# 最新云侧方案对比说明

本文档对比 `docs/云侧方案设计.md` 与当前微服务实现，并记录本次已经按最新方案调整的点。

## 1. 工具形态

分歧点：

- 旧实现：曾对外抽象为一个工具 `widgetCardService`，通过 `operation` 分发三个能力。
- 当前部署要求：对外恢复为 `getWidgetCapabilityOverview`、`getDataCapabilitySchemas`、`generateWidgetCard` 三个 WebSocket path。

当前处理：

- 当前保留三个业务 WebSocket 入口：
  `WS /api/v1/ws/tools/getWidgetCapabilityOverview`、
  `WS /api/v1/ws/tools/getDataCapabilitySchemas`、
  `WS /api/v1/ws/tools/generateWidgetCard`。
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

- 三个 WebSocket 入口不需要传 `operation`。
- 内部 `GenerateWidgetCardRequest` 暂时保留 `options`，便于服务内部测试和后续调试。

## 4. 自动注入上下文

分歧点：

- 旧实现：本地测试通常手动传外层 `appVersion/romVersion/xiaoyiVersion`。
- 最新方案：工具层自动注入用户和 `device`，服务使用 `device.romVersion` 与 `device.ohosApiVersion`。

当前处理：

- 请求模型移除外层 `appVersion/romVersion/xiaoyiVersion`，本地测试必须显式传 `uid` 和 `device`。
- 生产调用时由工具层注入，主 Agent 不需要主动填写。

## 5. 最新推荐调用方式

能力概述：

```json
{
  "uid": "test-user-001",
  "device": {
    "romVersion": "ALN-AL00 7.0.0.36",
    "ohosApiVersion": 36
  }
}
```

加载数据能力 schema：

```json
{
  "uid": "test-user-001",
  "device": {
    "romVersion": "ALN-AL00 7.0.0.36",
    "ohosApiVersion": 36
  },
  "dataCapabilityIds": ["ViewWeather"]
}
```

生成卡片：

```json
{
  "uid": "test-user-001",
  "device": {
    "romVersion": "ALN-AL00 7.0.0.36",
    "ohosApiVersion": 36
  },
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
      "updateModel": {
        "location": {
          "districtName": ""
        },
        "current": {
          "temperatureText": "",
          "condition": "",
          "airQuality": ""
        },
        "updatedAt": ""
      }
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
