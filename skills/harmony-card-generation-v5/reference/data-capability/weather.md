# 天气数据能力

```json
{
  "id": "weather.overview.get",
  "version": "1.0",
  "description": "查询当前位置或指定地区的当前天气及未来天气。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "districtName": {
        "type": "string",
        "description": "区县名。不传表示查询用户当前位置。"
      },
      "prefectureName": {
        "type": "string",
        "description": "城市名，用于同名区县消歧，可不传。"
      },
      "forecastDays": {
        "type": "integer",
        "description": "返回预报天数，支持 1 至 5 天；不传时端侧按 3 天处理。"
      }
    }
  },
  "outputSchema": {
    "type": "object",
    "description": "端侧归一化后的天气概要。",
    "properties": {
      "location": {
        "type": "object",
        "properties": {
          "districtName": {
            "type": "string",
            "description": "实际查询的区县名。"
          },
          "prefectureName": {
            "type": "string",
            "description": "实际查询的城市名。"
          }
        }
      },
      "current": {
        "type": "object",
        "properties": {
          "temperatureC": {
            "type": "number",
            "description": "当前摄氏温度。"
          },
          "temperatureText": {
            "type": "string",
            "description": "可直接展示的温度文本，例如 29°C。"
          },
          "condition": {
            "type": "string",
            "description": "当前天气现象，例如阴、小雨。"
          },
          "humidityPercent": {
            "type": "number",
            "description": "当前相对湿度百分比。"
          }
        }
      },
      "daily": {
        "type": "array",
        "description": "从今天开始的每日预报，数量不超过 forecastDays。",
        "items": {
          "type": "object",
          "properties": {
            "weekday": {
              "type": "string",
              "description": "星期文本。"
            },
            "condition": {
              "type": "string",
              "description": "当日天气现象。"
            },
            "temperatureRangeText": {
              "type": "string",
              "description": "可直接展示的温度范围。"
            },
            "rainProbabilityPercent": {
              "type": "number",
              "description": "当日降雨概率百分比。"
            }
          }
        }
      },
      "updatedAt": {
        "type": "string",
        "description": "端侧完成查询和归一化的时间。"
      }
    }
  }
}
```

## 使用规则

- 适用于当前位置天气、指定区县天气、未来 1 到 3 天预报速览。
- `forecastDays` 在 2x2 中通常取 1；在 2x4 中通常取 2 到 3。
- UI 当前天气路径通常是 `/data/weather/current`。
- UI 预报列表路径通常是 `/data/weather/daily`。
- 优先展示 `temperatureText`、`condition`、`temperatureRangeText` 这类端侧格式化字段。
- 不要写死用户当前位置或天气结果；初始 `updateDataModel` 使用空对象、空数组和加载态。
