# 健康与运动数据能力

```json
{
  "id": "GetHealthAndSportSummary",
  "description": "一键合并查询用户指定时间段内的大健康与运动数据，包含详尽的夜间睡眠质量剖析、当日日常大盘活动（步数/卡路里/距离）以及最近一次的专业运动训练记录。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "startTimestamp": {
        "type": "number",
        "description": "查询的起始时间戳（毫秒级）。可不传，不传时端侧默认自动兜底为过去48小时，以完整覆盖昨夜睡眠。"
      },
      "endTimestamp": {
        "type": "number",
        "description": "查询的结束时间戳（毫秒级）。可不传，不传时端侧默认自动兜底为当前系统时间。"
      }
    },
    "required": []
  },
  "outputSchema": {
    "type": "object",
    "description": "融合清洗后的标准化大健康与运动概要数据，所有数值已在端侧完成千分位缩放、单位换算和文本格式化，适合桌面卡片高密度渲染或大模型直接进行健康状态总结。",
    "properties": {
      "sleepScore": {
        "type": "integer",
        "description": "睡眠综合得分，取值范围 0-100。"
      },
      "sleepTypeDesc": {
        "type": "string",
        "description": "睡眠数据类型语义描述，例如“科学睡眠”、“普通睡眠”、“手动输入睡眠”。"
      },
      "nightSleepDurationText": {
        "type": "string",
        "description": "夜间正式睡眠的总时长文本，例如“7小时42分”。"
      },
      "deepSleepDurationText": {
        "type": "string",
        "description": "夜间睡眠中的深睡时长文本，例如“2小时27分”。"
      },
      "shallowSleepDurationText": {
        "type": "string",
        "description": "夜间睡眠中的浅睡时长文本，例如“4小时23分”。"
      },
      "remSleepDurationText": {
        "type": "string",
        "description": "快速眼动（REM）/ 做梦时长文本，例如“1小时14分”。"
      },
      "wakeDurationText": {
        "type": "string",
        "description": "夜间中途清醒的总时长文本，例如“12分”。"
      },
      "wakeCount": {
        "type": "integer",
        "description": "夜间中途醒来的次数。"
      },
      "sleepEfficiency": {
        "type": "integer",
        "description": "睡眠效率百分比，取值范围 0-100。"
      },
      "respiratoryQualityScore": {
        "type": "integer",
        "description": "睡眠期间的呼吸质量评分，取值范围 0-100。"
      },
      "avgHeartRate": {
        "type": "integer",
        "description": "睡眠期间的平均心率（次/分钟）。"
      },
      "avgBreathRate": {
        "type": "integer",
        "description": "睡眠期间的平均呼吸率（次/分钟）。"
      },
      "totalNapDurationText": {
        "type": "string",
        "description": "与主睡眠同属一天的白天零星小睡（午休）合并总时长文本，例如“1小时52分”或“0分”。"
      },
      "fallAsleepTimeText": {
        "type": "string",
        "description": "精确格式化后的入睡时间，点位适合UI直显，例如“00:12”。"
      },
      "wakeupTimeText": {
        "type": "string",
        "description": "精确格式化后的醒来时间，点位适合UI直显，例如“08:02”。"
      },
      "dailySteps": {
        "type": "integer",
        "description": "与最新睡眠同属一天的日常全天活动总步数，例如 13366。"
      },
      "dailyCaloriesText": {
        "type": "string",
        "description": "与最新睡眠同属一天的日常活动总热量消耗文本（已转换千卡），例如“1248 千卡”。"
      },
      "dailyDistanceText": {
        "type": "string",
        "description": "与最新睡眠同属一天的全天活动总距离文本（根据数值自动变换米或公里），例如“5.42 公里”或“755 米”。"
      },
      "hasWorkoutRecord": {
        "type": "boolean",
        "description": "指示在该时间段内，用户是否存在专业的单次运动训练记录。"
      },
      "workoutTypeDesc": {
        "type": "string",
        "description": "最近一次专业运动训练的类型描述，如“自由训练”、“户外跑步”。若无则返回“暂无运动”。"
      },
      "workoutDurationText": {
        "type": "string",
        "description": "最近一次专业运动训练的持续时长文本，例如“1小时40分”。"
      },
      "workoutCaloriesText": {
        "type": "string",
        "description": "最近一次专业运动训练所消耗的净热量文本（已转换千卡），例如“998 千卡”。"
      },
      "workoutAvgHeartRate": {
        "type": "integer",
        "description": "最近一次专业运动训练期间的平均心率（次/分钟）。"
      },
      "updatedAt": {
        "type": "string",
        "description": "端侧完成双图谱实体组合查询和多维融合规整的时间戳字符串。如：2026-07-02 15:30"
      }
    }
  }
}
```
