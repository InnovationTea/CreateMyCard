# 天气数据能力

```json
{
  "id": "weather.overview.get",
  "version": "1.0",
  "description": "查看天气，返回指定地区的当前天气状况和未来多日天气预报",
  "inputSchema": {
    "type": "object",
    "description": "查看天气输入的信息描述",
    "properties": {
      "districtName": {
        "type": "string",
        "description": "区/县名，用于指定要查询天气的地区"
      },
      "prefectureName": {
        "type": "string",
        "description": "城市名，用于指定要查询天气的城市"
      },
      "forecastDays": {
        "type": "integer",
        "description": "返回预报天数，支持1至5天；不传时默认返回3天。"
      }
    }
  },
  "outputSchema": {
    "type": "object",
    "description": "查看天气的返回结果，包含城市信息、实时天气和未来天气预报",
    "properties": {
      "items": {
        "type": "object",
        "properties": {
          "cityInfo": {
            "type": "object",
            "properties": {
              "cityCode": {
                "type": "string",
                "description": "城市代码，如60814代表青浦区"
              },
              "cityName": {
                "type": "string",
                "description": "城市名称，如青浦区"
              },
              "prefectureName": {
                "type": "string",
                "description": "所属上级行政区名称，如上海市"
              }
            }
          },
          "cityType": {
            "type": "string",
            "description": "城市类型标识"
          },
          "hasDressIndices": {
            "type": "string",
            "description": "是否有穿衣指数，true表示有"
          },
          "needAnimate": {
            "type": "string",
            "description": "是否需要动画效果"
          },
          "weatherDailyData": {
            "type": "array",
            "description": "未来多日天气预报数组，每个元素包含一天的天气信息",
            "items": {
              "type": "object",
              "properties": {
                "airQualityValue": {
                  "type": "string",
                  "description": "空气质量等级，如优、良等"
                },
                "cloud": {
                  "type": "integer",
                  "description": "云量百分比，0-100"
                },
                "dayRainProb": {
                  "type": "integer",
                  "description": "白天降雨概率百分比，0-100"
                },
                "day_time": {
                  "type": "string",
                  "description": "预报日期，格式YYYY-MM-DD"
                },
                "high_temp": {
                  "type": "integer",
                  "description": "最高温度，单位摄氏度"
                },
                "isRain": {
                  "type": "boolean",
                  "description": "当天是否下雨"
                },
                "low_temp": {
                  "type": "integer",
                  "description": "最低温度，单位摄氏度"
                },
                "nightRainProb": {
                  "type": "integer",
                  "description": "夜间降雨概率百分比，0-100"
                },
                "night_high_temp": {
                  "type": "integer",
                  "description": "夜间最高温度"
                },
                "night_low_temp": {
                  "type": "integer",
                  "description": "夜间最低温度"
                },
                "night_weather_icon": {
                  "type": "string",
                  "description": "夜间天气图标名称，如小雨、多云"
                },
                "night_windDir": {
                  "type": "string",
                  "description": "夜间风向，如东风、南风"
                },
                "night_windLevel": {
                  "type": "integer",
                  "description": "夜间风力等级"
                },
                "night_wind_direction": {
                  "type": "string",
                  "description": "夜间风向（英文缩写）"
                },
                "snowProb": {
                  "type": "string",
                  "description": "降雪概率"
                },
                "totalLiquid": {
                  "type": "string",
                  "description": "总降水量，单位毫米"
                },
                "uvIndex": {
                  "type": "string",
                  "description": "紫外线指数等级，如弱、中等、强"
                },
                "weather_icon": {
                  "type": "string",
                  "description": "白天天气图标名称，如小雨、晴天"
                },
                "weekday": {
                  "type": "string",
                  "description": "星期几，如星期一、星期二"
                },
                "windDir": {
                  "type": "string",
                  "description": "白天风向，如东南风、东北风"
                },
                "windGustPow": {
                  "type": "string",
                  "description": "阵风功率等级"
                },
                "windLevel": {
                  "type": "integer",
                  "description": "白天风力等级"
                },
                "wind_direction": {
                  "type": "string",
                  "description": "白天风向（英文缩写）"
                }
              }
            }
          },
          "weatherData": {
            "type": "object",
            "description": "当前实时天气数据",
            "properties": {
              "aqivalue": {
                "type": "string",
                "description": "空气质量指数值，如优、良"
              },
              "cloud_cover": {
                "type": "integer",
                "description": "云覆盖率百分比"
              },
              "co": {
                "type": "number",
                "description": "一氧化碳浓度"
              },
              "eveningGlowQuality": {
                "type": "integer",
                "description": "晚霞质量指数"
              },
              "eveningGlowQualityProb": {
                "type": "integer",
                "description": "晚霞出现概率"
              },
              "evening_glow_end_time": {
                "type": "string",
                "description": "晚霞结束时间，格式HH:MM"
              },
              "evening_glow_prop": {
                "type": "integer",
                "description": "晚霞比例"
              },
              "evening_glow_start_time": {
                "type": "string",
                "description": "晚霞开始时间，格式HH:MM"
              },
              "high_temp": {
                "type": "integer",
                "description": "今日最高温度"
              },
              "humidity": {
                "type": "integer",
                "description": "湿度百分比"
              },
              "low_temp": {
                "type": "integer",
                "description": "今日最低温度"
              },
              "moon_rise_date": {
                "type": "string",
                "description": "月亮升起时间"
              },
              "moon_set_date": {
                "type": "string",
                "description": "月亮落下时间"
              },
              "morning_glow_end_time": {
                "type": "string",
                "description": "朝霞结束时间"
              },
              "morning_glow_prop": {
                "type": "integer",
                "description": "朝霞比例"
              },
              "morning_glow_quality": {
                "type": "integer",
                "description": "朝霞质量指数"
              },
              "morning_glow_quality_prob": {
                "type": "integer",
                "description": "朝霞出现概率"
              },
              "morning_glow_start_time": {
                "type": "string",
                "description": "朝霞开始时间"
              },
              "no2": {
                "type": "integer",
                "description": "二氧化氮浓度"
              },
              "o3": {
                "type": "integer",
                "description": "臭氧浓度"
              },
              "pm10": {
                "type": "integer",
                "description": "PM10浓度"
              },
              "pm25": {
                "type": "integer",
                "description": "PM2.5浓度"
              },
              "pressure": {
                "type": "integer",
                "description": "气压，单位hPa"
              },
              "real_feel": {
                "type": "integer",
                "description": "体感温度"
              },
              "so2": {
                "type": "integer",
                "description": "二氧化硫浓度"
              },
              "sun_rise_date": {
                "type": "string",
                "description": "日出时间，格式HH:MM"
              },
              "sun_set_date": {
                "type": "string",
                "description": "日落时间，格式HH:MM"
              },
              "temperature": {
                "type": "integer",
                "description": "当前温度，单位摄氏度"
              },
              "uv_index": {
                "type": "string",
                "description": "紫外线指数等级"
              },
              "visibility": {
                "type": "integer",
                "description": "能见度，单位公里"
              },
              "weather_icon": {
                "type": "string",
                "description": "天气图标或图标ID"
              },
              "wind_direction": {
                "type": "string",
                "description": "风向，如东北风"
              },
              "wind_gust_level": {
                "type": "integer",
                "description": "阵风等级"
              },
              "wind_level": {
                "type": "integer",
                "description": "风力等级"
              }
            }
          },
          "weatherHoursData": {
            "type": "array",
            "description": "逐小时天气预报数组",
            "items": {
              "type": "object",
              "properties": {
                "forcase_date_time": {
                  "type": "string",
                  "description": "预报时间点，格式HH:MM或时间戳"
                },
                "hour_temperature": {
                  "type": "integer",
                  "description": "小时温度"
                },
                "rain_probability": {
                  "type": "integer",
                  "description": "降雨概率百分比"
                },
                "uv_index": {
                  "type": "string",
                  "description": "紫外线指数等级"
                },
                "weather_icon": {
                  "type": "string",
                  "description": "天气图标"
                }
              }
            }
          }
        }
      }
    }
  }
}
```

## 使用规则

- 适用于当前位置天气、指定区县天气、未来 1 到 5 天预报、逐小时预报、空气质量、日出日落和风力等天气速览。
- `forecastDays` 在 `2x2` 中通常取 1；在 `2x4` 中通常取 2 到 3。不要为了长预报突破卡片密度。
- CardSpec 通常使用 `writeResultTo: "/data/weather"`；UI 当前天气路径使用 `/data/weather/items/weatherData`。
- 常用当前天气字段：`temperature`、`weather_icon`、`aqivalue`、`humidity`、`high_temp`、`low_temp`、`real_feel`、`wind_direction`、`wind_level`、`sun_rise_date`、`sun_set_date`。
- 每日预报列表路径通常是 `/data/weather/items/weatherDailyData`，优先展示 `weekday`、`weather_icon`、`high_temp`、`low_temp`、`dayRainProb`。
- 小时预报列表路径通常是 `/data/weather/items/weatherHoursData`，字段名以 capability 原始 schema 为准，例如 `forcase_date_time`、`hour_temperature`、`rain_probability`。
- 保留上游字段名和类型，不要自行改名或改类型。例如 `hasDressIndices`、`needAnimate` 是字符串，`forcase_date_time` 保持原拼写。
- 本文档只声明天气数据能力的输入、输出和常用路径；通用 data capability 选择、CardSpec 映射、事件参数绑定和最终评审规则见 `reference/cardspec.md`、`reference/event-capability/`、`reference/data-binding.md` 和 `reference/final-review.md`。
- 初始 `updateDataModel` 使用空对象、空数组和加载态，不要写死用户当前位置或真实天气结果：

```json
{
  "data": {
    "weather": {
      "items": {
        "cityInfo": {},
        "weatherData": {},
        "weatherDailyData": [],
        "weatherHoursData": []
      }
    }
  },
  "state": {
    "loading": true
  }
}
```
