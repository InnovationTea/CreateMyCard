# getDataCapabilitySchemas 测试报告

- 生成时间：2026-07-07T13:06:15.287858+00:00
- 接口名：`getDataCapabilitySchemas`
- WebSocket path：`/api/v1/ws/tools/getDataCapabilitySchemas`
- 请求协议：content/deviceInfo/session 外层包络
- requestId：`7676c2c8-a6d3-413c-8074-c62ed30db8de&2`
- ready 状态：`ready`
- 消息状态：`result`
- 业务状态：`result`

## ready 消息

```json
{
  "type": "ready",
  "tool": "getDataCapabilitySchemas",
  "operations": [
    "getDataCapabilitySchemas"
  ]
}
```

## 入参

```json
{
  "content": {
    "bundleName": "com.omega_w_0823.hmservice",
    "dataCapabilityIds": [
      "ViewWeather"
    ]
  },
  "deviceInfo": {
    "countryCode": "CN",
    "deviceFormation": "HDSpeaker",
    "deviceType": 0,
    "locale": "zh-CN",
    "phoneType": "CLS-AL30",
    "apiVersion": "11.7.5.205",
    "sysVer": "EmotionUI_9.0.0",
    "time": "20260707115342975"
  },
  "pagination": {
    "limit": 5,
    "start": ""
  },
  "session": {
    "interactionId": "2",
    "isNew": false,
    "sessionId": "7676c2c8-a6d3-413c-8074-c62ed30db8de"
  },
  "userAuth": {
    "user": {
      "userId": "test-user-001"
    }
  },
  "utterance": {
    "original": "",
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
  "tool": "getDataCapabilitySchemas",
  "operation": "getDataCapabilitySchemas",
  "requestId": "7676c2c8-a6d3-413c-8074-c62ed30db8de&2",
  "data": {
    "apiVersion": "v1",
    "capabilityRegistryVersion": "ohos-36_rom-7.0.0",
    "dataCapabilities": [
      {
        "id": "ViewWeather",
        "type": "data",
        "description": "查询指定地区或用户当前位置的当前天气与未来数日天气预报。",
        "descriptionForLLM": "",
        "inputSchema": {
          "type": "object",
          "properties": {
            "districtName": {
              "type": "string",
              "description": "区县名。"
            },
            "prefectureName": {
              "type": "string",
              "description": "城市名，用于同名区县消歧，可不传。"
            },
            "forecastDays": {
              "type": "integer",
              "description": "返回预报天数，支持1至5天；不传时默认返回3天。"
            }
          },
          "required": [
            "districtName"
          ]
        },
        "outputSchema": {
          "type": "object",
          "description": "适合桌面卡片展示的标准化天气概要。current 是固定对象，daily 是数量由 forecastDays 决定的数组。",
          "properties": {
            "location": {
              "type": "object",
              "description": "实际查询成功的地区。",
              "properties": {
                "cityCode": {
                  "type": "string",
                  "description": "城市代码，如60814代表青浦区"
                },
                "districtName": {
                  "type": "string",
                  "description": "区或县名称"
                },
                "prefectureName": {
                  "type": "string",
                  "description": "城市名称"
                }
              }
            },
            "current": {
              "type": "object",
              "description": "当日天气实况",
              "properties": {
                "temperatureC": {
                  "type": "number",
                  "description": "当前摄氏温度。"
                },
                "temperatureText": {
                  "type": "string",
                  "description": "适合直接显示的温度文本，例如“29°C”。"
                },
                "condition": {
                  "type": "string",
                  "description": "当前天气现象，例如“阴”“多云”“小雨”。"
                },
                "feelsLikeC": {
                  "type": "number",
                  "description": "当前体感摄氏温度。"
                },
                "humidityPercent": {
                  "type": "number",
                  "minimum": 0,
                  "maximum": 100,
                  "description": "当前相对湿度百分比。"
                },
                "airQuality": {
                  "type": "string",
                  "description": "当前空气质量等级，例如“优”“良”。"
                },
                "windDirection": {
                  "type": "string",
                  "description": "当前风向。"
                },
                "windLevel": {
                  "type": "integer",
                  "minimum": 0,
                  "description": "当前风力等级。"
                },
                "uvIndex": {
                  "type": "string",
                  "description": "当前紫外线等级，例如“弱”“中等”“强”。"
                },
                "coldLevel": {
                  "type": "string",
                  "description": "感冒指数。"
                },
                "alertLevel": {
                  "type": "string",
                  "description": "预警信息。"
                }
              }
            },
            "daily": {
              "type": "array",
              "description": "从今天开始按日期升序排列的每日预报。",
              "items": {
                "type": "object",
                "properties": {
                  "date": {
                    "type": "string",
                    "description": "预报日期，来源于 day_time。"
                  },
                  "weekday": {
                    "type": "string",
                    "description": "星期文本，例如“星期日”。"
                  },
                  "condition": {
                    "type": "string",
                    "description": "白天天气现象。"
                  },
                  "temperatureRangeText": {
                    "type": "string",
                    "description": "适合直接显示的温度范围，例如“24° / 32°”。"
                  },
                  "rainProbabilityPercent": {
                    "type": "string",
                    "description": "白天降雨概率百分比。如：73%"
                  },
                  "airQuality": {
                    "type": "string",
                    "description": "当天空气质量等级。"
                  },
                  "uvIndex": {
                    "type": "string",
                    "description": "当天紫外线等级。"
                  },
                  "coldLevel": {
                    "type": "string",
                    "description": "感冒指数。"
                  }
                }
              }
            },
            "updatedAt": {
              "type": "string",
              "description": "端侧完成天气查询和归一化的时间。如：2026-06-14 15:30"
            }
          }
        },
        "dataModelSkeleton": {},
        "dependencies": {
          "requiredPackages": [],
          "requiredProviders": [],
          "requiredIntentTargets": [],
          "requiredPermissions": []
        }
      }
    ],
    "missingCapabilityIds": []
  }
}
```
