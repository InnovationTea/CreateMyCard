# 天气数据能力

## 使用规则

- 适用于当前位置天气、指定区县天气、未来 1 到 5 天预报、空气质量、感冒指数、紫外线、风力和预警等天气速览。
- CardSpec 的 `capabilityId` 使用本文档 manifest 的 `id`：`ViewWeather`。
- `arguments` 只能使用 `inputSchema.properties` 声明的字段：`districtName`、`prefectureName`、`forecastDays`；其中 `districtName` 是必填字段。
- `forecastDays` 在 `2x2` 中通常取 1；在 `2x4` 中通常取 2 到 3。不要为了长预报突破卡片密度。
- CardSpec 通常使用 `writeResultTo: "/data/weather"`；UI 访问路径必须由 `writeResultTo + outputSchema` 推导。
- 常用当前天气路径：`/data/weather/current/temperatureText`、`/data/weather/current/condition`、`/data/weather/current/airQuality`、`/data/weather/current/humidityPercent`、`/data/weather/current/windDirection`、`/data/weather/current/windLevel`、`/data/weather/current/uvIndex`、`/data/weather/current/coldLevel`、`/data/weather/current/alertLevel`。
- 地点路径使用 `/data/weather/location/districtName`、`/data/weather/location/prefectureName` 或 `/data/weather/location/cityCode`。
- 每日预报列表路径通常是 `/data/weather/daily`，模板项内优先展示 `weekday`、`condition`、`temperatureRangeText`、`rainProbabilityPercent`；`airQuality`、`uvIndex`、`coldLevel` 作为可选次要字段。
- 更新时间路径是 `/data/weather/updatedAt`，仅在卡片确实需要展示刷新时间时使用。
- 保留 manifest 中声明的字段名和类型，不要自行改名或改类型。
- 本文档只声明天气数据能力的输入、输出和常用路径；通用 data capability 选择、CardSpec 映射、事件参数绑定和最终门禁见 [`../cardspec.md`](../cardspec.md)、[`../event-capability/`](../event-capability/)、[`../../protocol/data-binding.md`](../../protocol/data-binding.md) 和 [`../../core-rules.md`](../../core-rules.md)。
- 初始 `updateDataModel` 使用空对象、空数组和加载态，不要写死用户当前位置或真实天气结果：

```json
{
  "data": {
    "weather": {
      "location": {},
      "current": {},
      "daily": [],
      "updatedAt": ""
    }
  },
  "state": {
    "loading": true
  }
}
```

## Manifest

```json
{
  "id": "ViewWeather",
  "description": "查询指定地区或用户当前位置的当前天气与未来数日天气预报。",
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
  }
}
```
