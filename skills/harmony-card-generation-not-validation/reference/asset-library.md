# 素材库

本文件是可扩展的本地/资源素材清单。生成卡片需要图标、图片、媒体路径或视觉锚点时，先按用户场景语义和 `description` 匹配这里的素材。

```json
[
  {
    "src": "resource/meeting_widget/icon_id.png",
    "description": "工牌/ID图标，适用场景：当下日程"
  },
  {
    "src": "resource/meeting_widget/icon_meeting.png",
    "description": "会议图标，适用场景：当下日程"
  },
  {
    "src": "resource/meeting_widget/icon_time.png",
    "description": "时间图标，适用场景：当下日程"
  },
  {
    "src": "resource/meeting_widget/icon_watermark.png",
    "description": "水印图标，适用场景：当下日程"
  },
  {
    "src": "resource/care_widget/icon_allergy.png",
    "description": "过敏源图标，适用场景：亲人关怀"
  },
  {
    "src": "resource/care_widget/icon_call.png",
    "description": "电话图标，适用场景：亲人关怀"
  },
  {
    "src": "resource/care_widget/icon_high_temperature.png",
    "description": "高温/温度计图标，适用场景：亲人关怀"
  },
  {
    "src": "resource/care_widget/icon_weather1.png",
    "description": "天气/雨伞图标，适用场景：亲人关怀"
  },
  {
    "src": "resource/app_usage_widget/icon_tiktok.png",
    "description": "抖音图标，适用场景：防沉迷"
  },
  {
    "src": "resource/app_usage_widget/icon_timing.png",
    "description": "计时图标，适用场景：防沉迷"
  },
  {
    "src": "resource/phone_status_widget/icon_charge.png",
    "description": "充电/闪电图标，适用场景：低电模式"
  },
  {
    "src": "resource/phone_status_widget/icon_clear.png",
    "description": "清除图标，适用场景：清理无忧"
  },
  {
    "src": "resource/phone_status_widget/icon_earphone.png",
    "description": "耳机图标，适用场景：戴耳机播控"
  },
  {
    "src": "resource/phone_status_widget/icon_phone.png",
    "description": "手机图标，适用场景：专注模式"
  },
  {
    "src": "resource/taxi_widget/icon_car.png",
    "description": "汽车/打车图标，适用场景：雨天打车"
  },
  {
    "src": "resource/taxi_widget/icon_time1.png",
    "description": "时间图标，适用场景：雨天打车"
  },
  {
    "src": "resource/taxi_widget/icon_weathe2.png",
    "description": "天气图标，适用场景：雨天打车"
  },
  {
    "src": "resource/schedule_widget/icon_alarm_clock.png",
    "description": "闹钟图标，适用场景：当下日程"
  },
  {
    "src": "resource/schedule_widget/icon_focus.png",
    "description": "专注图标，适用场景：专注模式"
  },
  {
    "src": "resource/schedule_widget/icon_schedule.png",
    "description": "日程图标，适用场景：当下日程"
  },
  {
    "src": "resource/battery_widget/icon_electricity.png",
    "description": "电池图标，适用场景：低电模式"
  },
  {
    "src": "resource/battery_widget/icon_save_power.png",
    "description": "省电图标，适用场景：低电模式"
  },
  {
    "src": "resource/sleep_widget/icon_alarm_clock1.png",
    "description": "闹钟图标，适用场景：睡眠监督"
  },
  {
    "src": "resource/sleep_widget/icon_remind.png",
    "description": "提醒图标，适用场景：睡眠监督"
  },
  {
    "src": "resource/sleep_widget/icon_sleep.png",
    "description": "睡眠图标，适用场景：睡眠监督"
  },
  {
    "src": "resource/exercise_plan_widget/icon_run.png",
    "description": "运动/跑步图标，适用场景：当下日程"
  },
  {
    "src": "resource/exercise_plan_widget/icon_schedule2.png",
    "description": "日程图标，适用场景：当下日程"
  },
  {
    "src": "resource/music_widget/icon_left.png",
    "description": "上一首图标，适用场景：戴耳机播控"
  },
  {
    "src": "resource/music_widget/icon_like.png",
    "description": "收藏/心形图标，适用场景：戴耳机播控"
  },
  {
    "src": "resource/music_widget/icon_music.png",
    "description": "音乐图标，适用场景：戴耳机播控"
  },
  {
    "src": "resource/music_widget/icon_right.png",
    "description": "下一首图标，适用场景：戴耳机播控"
  }
]
```

## 选择规则

- 优先选择与用户场景、语义角色和 `description` 明确匹配的素材。
- 只使用清单中声明过的 `src`，不要编造相似路径、重命名文件或替换目录。
- 如果没有语义匹配素材，省略 `Image`，改用渐变、半透明块、文本字形、`Progress`、`Divider` 或 `Stack` 等非媒体视觉技法。

## 输出规则

- 静态素材可直接写入 `Image.src`，例如 `"src": "resource/会议widget/icon_meeting.png"`。
- 如果素材选择需要由 DataModel 管理，将 `Image.src` 绑定到 `/asset/...`，并在 `updateDataModel.value` 中把该字段初始化为清单中声明过的 `src`。
- 不要把素材库写入 CardSpec；CardSpec 只描述端侧 data capability。
