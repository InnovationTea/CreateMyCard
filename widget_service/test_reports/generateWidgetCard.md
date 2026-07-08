# generateWidgetCard 测试报告

- 生成时间：2026-07-08T07:08:00.405946+00:00
- 接口名：`generateWidgetCard`
- WebSocket path：`/api/v1/ws/tools/generateWidgetCard`
- 请求协议：content/deviceInfo/session 外层包络
- requestId：`7676c2c8-a6d3-413c-8074-c62ed30db8de&3`
- 消息状态：`result`
- 业务状态：`success`

## 入参

```json
{
  "content": {
    "bundleName": "com.omega_w_0823.hmservice",
    "userQuery": "帮我做通勤卡片，包含天气",
    "size": "2x4",
    "candidateDataBindings": [
      {
        "capabilityId": "ViewWeather",
        "arguments": {
          "districtName": "上海",
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
    "candidateAssetIds": [
      "asset.drop_1"
    ]
  },
  "deviceInfo": {
    "countryCode": "CN",
    "deviceFormation": "HDSpeaker",
    "deviceType": 0,
    "locale": "zh-CN",
    "phoneType": "CLS-AL30",
    "prdVer": "11.7.5.205",
    "sysVer": "EmotionUI_9.0.0",
    "time": "20260707115342975"
  },
  "pagination": {
    "limit": 5,
    "start": ""
  },
  "session": {
    "interactionId": "3",
    "isNew": false,
    "sessionId": "7676c2c8-a6d3-413c-8074-c62ed30db8de"
  },
  "userAuth": {
    "user": {
      "userId": "test-user-001"
    }
  },
  "utterance": {
    "original": "帮我做通勤卡片，包含天气",
    "type": "text"
  },
  "version": "1.0",
  "bundleName": "com.omega_w_0823.hmservice"
}
```

## 出参

```json
{
  "type": "result",
  "tool": "generateWidgetCard",
  "operation": "generateWidgetCard",
  "requestId": "7676c2c8-a6d3-413c-8074-c62ed30db8de&3",
  "data": {
    "apiVersion": "v1",
    "status": "success",
    "artifactUrl": "https://obs.todo.local/widget/bf47c202b34e41f6b0861c33b445ca67.json",
    "artifactDigest": "sha256:30ac5937d345c46be7574859a80768eaa5c7d64d5b7c49e927645110182703f6",
    "suggestSize": "2x4",
    "message": "已为你生成可用的桌面卡片。",
    "removedCapabilities": [],
    "errorCode": "",
    "effectiveCapabilities": {
      "data": [
        "ViewWeather"
      ],
      "event": [
        {
          "id": "event.open.weather",
          "call": "clickToDeeplink",
          "args": {
            "uri": "hww://weather"
          }
        }
      ],
      "asset": [
        "asset.drop_1"
      ]
    }
  },
  "status": "success",
  "errorCode": "",
  "error": {}
}
```
