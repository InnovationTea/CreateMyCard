# 日历数据能力

```json
{
  "id": "GetCalendarEvents",
  "description": "查询用户系统日历中的日程安排。高度精简的结构化日历模型，包含日程倒计时计算、日程开始/截止时间文本，以及支持一键拉起第三方应用（如视频会议、赛事直播）的深度跳转链接。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "futureDays": {
        "type": "integer",
        "description": "需要查询的未来时间窗口天数。例如用户想看'这周'或'未来7天'的日程则传 7。若不传，端侧默认查询未来7天。"
      }
    },
    "required": []
  },
  "outputSchema": {
    "type": "object",
    "description": "经过端侧高级清洗后的系统日程概要，包含命中该时间段的日程总数以及按时间升序排列的具体日程明细列表。",
    "properties": {
      "eventCount": {
        "type": "integer",
        "description": "查询到的日程记录总数量。"
      },
      "events": {
        "type": "array",
        "description": "高密度结构化日程信息实体列表，已按开始时间由早到晚进行升序排列。",
        "items": {
          "type": "object",
          "properties": {
            "entityName": {
              "type": "string",
              "description": "固定为 'CalendarEvent'，用于系统底层实体识别。"
            },
            "entityId": {
              "type": "string",
              "description": "系统日程的全局唯一实体ID。"
            },
            "senderName": {
              "type": "string",
              "description": "日程数据标识符或发起方标识（如邀请人），若无则为空字符串。"
            },
            "title": {
              "type": "string",
              "description": "日程标题，例如"咪咕视频《西班牙 VS 奥地利》"或航班、车次信息。"
            },
            "eventLocation": {
              "type": "string",
              "description": "日程的具体地点描述，若未填写则为空字符串。"
            },
            "description": {
              "type": "string",
              "description": "日程的备注或摘要。注意：某些三方应用写入时，此字段可能仅为时间的补充描述（如'07月03日 03:00'）或补充检票口、座位号等短文本。"
            },
            "dtStart": {
              "type": "string",
              "description": "格式化后的日程开始时间短文本，如 '03:00'，若为全天日程可能为特殊标记。"
            },
            "dtEnd": {
              "type": "string",
              "description": "格式化后的日程结束时间短文本，如 '05:00'。"
            },
            "timeZone": {
              "type": "string",
              "description": "日程所处的时区标识，例如 'Asia/Shanghai'。"
            },
            "importantEventType": {
              "type": "integer",
              "description": "日程事件的重要程度或分类枚举值（Type）。"
            },
            "remindTime": {
              "type": "array",
              "description": "预设的提前提醒时间跨度数组（字符串化），例如 ['15'] 代表提前15分钟提醒。",
              "items": {
                "type": "string"
              }
            },
            "oneClickServiceType": {
              "type": "string",
              "enum": ["Meeting", "Watching", "Repayment", "Live", "Shopping", "Trip", "Class", "SportsEvents", "SportsExercise", ""],
              "description": "绑定的轻服务类型名称。大模型在生成一键服务按钮文案时可参考此映射：Meeting(加入会议), Watching(立即观看), Repayment(马上还款), Live(开启直播), Shopping(开始选购), Trip(立即查看), Class(开始上课), SportsEvents(立即观看), SportsExercise(开始运动)。"
            },
            "oneClickServiceLink": {
              "type": "string",
              "description": "一键直达的 URI 深度跳转链接，UI 卡片可直接通过此链接拉起第三方 App 落地页。"
            },
            "isServiceValid": {
              "type": "integer",
              "description": "跳转服务连接是否有效。1代表存在有效跳转链接，0代表没有。"
            },
            "startDate": {
              "type": "string",
              "description": "日程开始日期格式化文本，例如 '07-03'。"
            },
            "countdownDays": {
              "type": "integer",
              "description": "纯数字的倒数日天数。0代表今天发生（或已发生），正整数代表距离日程开始还有多少天。"
            },
            "isAllDay": {
              "type": "boolean",
              "description": "标识该日程是否为全天日程。"
            }
          }
        }
      },
      "updatedAt": {
        "type": "string",
        "description": "端侧完成数据组装的时间戳字符串，格式如 '2026-07-03 15:30'。"
      }
    }
  }
}
```

## 使用规则

- 适用于今日会议、未来日程、倒计时、日历提醒、赛事日程等系统日历场景。
- CardSpec 的 `capabilityId` 使用本文档 manifest 的 `id`：`GetCalendarEvents`。
- `arguments` 只能使用 `inputSchema.properties` 声明的字段：`futureDays`；不传时端侧默认查询未来 7 天。
- `2x2` 通常只展示下一项或今日首个关键日程；`2x4` 可展示 2-3 条短日程摘要，不做完整列表。
- 推荐 `writeResultTo: "/data/calendar"`；UI 访问路径必须由 `writeResultTo + outputSchema` 推导。
- 常用展示路径：`/data/calendar/eventCount`、`/data/calendar/events`、`/data/calendar/events/0/title`、`/data/calendar/events/0/dtStart`、`/data/calendar/events/0/dtEnd`、`/data/calendar/events/0/eventLocation`、`/data/calendar/events/0/countdownDays`。
- 事件参数常用 `/data/calendar/events/0/entityId` 或模板项内 `entityId`；必须配合已声明事件能力使用。
- 初始 `updateDataModel` 使用空数组和加载态，不要写死用户真实日程：

```json
{
  "data": {
    "calendar": {
      "eventCount": 0,
      "events": [],
      "updatedAt": ""
    }
  },
  "state": {
    "loading": true
  }
}
```
