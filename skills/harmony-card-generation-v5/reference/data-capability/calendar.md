# 日历数据能力

```json
{
  "id": "calendar.events.search",
  "version": "1.0",
  "description": "查询用户手机本地日历事件。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "range": {
        "type": "string",
        "description": "查询范围，支持 today、tomorrow、next24Hours。"
      },
      "title": {
        "type": "string",
        "description": "可选的标题关键词。"
      },
      "eventLocation": {
        "type": "string",
        "description": "可选的地点关键词。"
      },
      "limit": {
        "type": "integer",
        "description": "最多返回 1 至 5 条，不传时端侧按 3 条处理。"
      }
    }
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "items": {
        "type": "array",
        "description": "按开始时间排序的日程数组。",
        "items": {
          "type": "object",
          "properties": {
            "eventId": {
              "type": "string",
              "description": "日程唯一标识。"
            },
            "title": {
              "type": "string",
              "description": "日程标题。"
            },
            "location": {
              "type": "string",
              "description": "日程地点，无地点时返回空字符串。"
            },
            "startAt": {
              "type": "string",
              "description": "ISO 8601 格式的开始时间。"
            },
            "endAt": {
              "type": "string",
              "description": "ISO 8601 格式的结束时间。"
            },
            "timeText": {
              "type": "string",
              "description": "可直接展示的本地时间文本。"
            }
          }
        }
      },
      "queriedAt": {
        "type": "string",
        "description": "端侧完成查询的时间。"
      }
    }
  }
}
```

## 使用规则

- 适用于今日、明日、未来 24 小时、指定标题或地点关键词的紧凑日程卡。
- `limit` 在卡片中通常取 1 到 3；不要为了长列表突破 V5 卡片密度。
- UI 列表路径通常是 `/data/calendar/items`。
- 列表模板内优先展示 `timeText`、`title`，地点作为可压缩次要文本。
- 不要把真实日程内容写死到初始 `updateDataModel`；使用空数组、加载态或空态文案。
