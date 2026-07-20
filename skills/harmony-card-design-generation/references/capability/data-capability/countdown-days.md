# 日期倒计时能力

```json
{
  "id": "GetCountdownDays",
  "description": "计算指定的日历日期距离今天还有多少天（倒数日/纪念日）。注意：大模型只需负责提取或推算出目标日期，实际的天数差值计算由端侧完成。",
  "inputSchema": {
    "type": "object",
    "description": "计算倒数日需要的入参。",
    "properties": {
      "targetDate": {
        "type": "string",
        "description": "目标日期。大模型必须将用户输入的自然语言时间（如'明天'、'下周一'、'2026年10月1日'）转换为标准的 'YYYY-MM-DD' 格式，例如 '2026-10-01'。"
      }
    },
    "required": ["targetDate"]
  },
  "outputSchema": {
    "type": "object",
    "description": "计算得出的倒数日天数结果实体。",
    "properties": {
      "countdownDays": {
        "type": "integer",
        "description": "距离目标日期的自然日天数。正数代表未来（还有几天），0 代表就是今天，负数代表已经过去的天数（已过去几天）。"
      }
    }
  }
}
```

## 使用规则

- 适用于指定日期倒数日、纪念日、节日、考试或截止日期提醒；普通系统日程仍使用 `calendar.md`。
- CardSpec 的 `capabilityId` 使用本文档 manifest 的 `id`：`GetCountdownDays`。
- `arguments` 只能使用必填字段 `targetDate`，并将用户给出的自然语言日期转换为 `YYYY-MM-DD`；无法可靠确定具体日期时先向用户确认，不要猜测。
- 推荐 `writeResultTo: "/data/countdown"`；常用展示路径为 `/data/countdown/countdownDays`。
- 初始 `updateDataModel` 使用 `countdownDays: 0` 和加载态，不要预先计算或写死真实倒数天数：

```json
{
  "data": {
    "countdown": {
      "countdownDays": 0
    }
  },
  "state": {
    "loading": true
  }
}
```
