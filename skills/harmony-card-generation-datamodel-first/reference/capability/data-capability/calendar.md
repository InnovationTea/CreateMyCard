# 日历数据能力

## 使用规则

- 适用于今日、明日、未来 24 小时、指定标题、指定地点、指定 `entityId` 或 `entityIdList` 的紧凑日程卡。
- `timeInterval` 使用毫秒时间戳数组 `[startMs, endMs]`，按本地时区把 today、tomorrow、next24Hours 等相对时间换算为起止毫秒。
- UI 列表路径通常是 `/data/calendar/items`，对应 CardSpec `writeResultTo: "/data/calendar"`。
- 列表模板内优先展示 `dtStart`、`dtEnd`、`title`；`eventLocation`、`description`、`senderName` 作为可压缩次要文本。
- 日程详情点击使用 [`../event-capability/click-event.md`](../event-capability/click-event.md) 中的 `clickToIntent`，`intentName` 固定为 `ViewCalendarEvent`，`params.entityId` 绑定当前日程的 `entityId`；模板列表项内优先写作 `{"path":"entityId"}`。
- 本文档只声明日历数据能力的输入、输出和常用路径；通用 data capability 选择、CardSpec 映射、事件参数绑定和最终门禁见 [`../cardspec.md`](../cardspec.md)、[`../event-capability/`](../event-capability/)、[`../../protocol/data-binding.md`](../../protocol/data-binding.md) 和 [`../../core-rules.md`](../../core-rules.md)。
- 初始 `updateDataModel` 使用空数组和加载态，不要写死真实日程内容：

```json
{
  "data": {
    "calendar": {
      "items": []
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
  "id": "calendar.events.search",
  "version": "1.0",
  "description": "查询用户手机本地日历事件。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "entityId": {
        "type": "string",
        "description": "索引项唯一标识符"
      },
      "entityIdList": {
        "type": "array",
        "description": "索引项唯一标识符列表，类型是字符列表",
        "items": {
          "type": "string"
        }
      },
      "title": {
        "type": "string",
        "description": "日程标题"
      },
      "eventLocation": {
        "type": "string",
        "description": "事件发生的位置"
      },
      "timeInterval": {
        "type": "array",
        "description": "搜索的时间段，包括开始时间和结束时间",
        "minItems": 2,
        "maxItems": 2,
        "items": {
          "type": "integer"
        }
      },
      "senderName": {
        "type": "string",
        "description": "应用来源包名"
      },
      "ownerAppName": {
        "type": "string",
        "description": "应用来源包名，同senderName"
      }
    }
  },
  "outputSchema": {
    "type": "object",
    "description": "搜索日程的返回结果",
    "properties": {
      "items": {
        "type": "array",
        "description": "执行具体结果",
        "items": {
          "type": "object",
          "description": "日程项",
          "properties": {
            "entityName": {
              "type": "string",
              "description": "内容的类别，区分于应用、图库、文件、邮件等的类别说明，属公共属性"
            },
            "entityId": {
              "type": "string",
              "description": "索引项唯一标识符，属公共属性"
            },
            "instanceId": {
              "type": "string",
              "description": "实例Id"
            },
            "senderName": {
              "type": "string",
              "description": "应用来源包名"
            },
            "title": {
              "type": "string",
              "description": "日程标题"
            },
            "eventLocation": {
              "type": "string",
              "description": "日程发生的位置"
            },
            "description": {
              "type": "string",
              "description": "日程描述"
            },
            "dtStart": {
              "type": "string",
              "description": "事件起始时间，如果是当天的为HH:MM格式"
            },
            "dtEnd": {
              "type": "string",
              "description": "事件结束时间, 如果是当天的为HH:MM格式"
            },
            "importantEventType": {
              "type": "integer",
              "description": "与重要日的关系，0普通(默认)，1为正数日，2为倒数日"
            },
            "remindTime": {
              "type": "array",
              "description": "日程提醒时间，字符串数组",
              "items": {
                "type": "string",
                "description": "提醒时间字符串"
              }
            },
            "oneClickServiceType": {
              "type": "string",
              "description": "一键服务类型"
            },
            "oneClickServiceLink": {
              "type": "string",
              "description": "一键服务Link"
            },
            "isServiceValid": {
              "type": "integer",
              "description": "一键服务Link校验状态，0校验失败(默认值)，1校验中，2校验成功"
            },
            "accountId": {
              "type": "integer",
              "description": "账号标识符"
            }
          },
          "required": [
            "entityName",
            "entityId",
            "title",
            "dtStart",
            "dtEnd"
          ]
        }
      }
    }
  }
}
```
