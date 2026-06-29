# 素材库

本文件是可扩展的本地/资源素材清单。生成卡片需要图标、图片、媒体路径或视觉锚点时，先按用户场景语义和 `description` 匹配这里的素材。

```json
[
  {
    "src": "resources/base/media/icon_id.png",
    "description": "工牌/ID图标，适用场景：当下日程"
  },
  {
    "src": "resources/base/media/icon_meeting.png",
    "description": "会议图标，适用场景：当下日程"
  },
  {
    "src": "resources/base/media/icon_time.png",
    "description": "时间图标，适用场景：当下日程"
  },
  {
    "src": "resources/base/media/icon_watermark.png",
    "description": "水印图标，适用场景：当下日程"
  },
  {
    "src": "resources/base/media/icon_allergy.png",
    "description": "过敏源图标，适用场景：亲人关怀"
  },
  {
    "src": "resources/base/media/icon_call.png",
    "description": "电话图标，适用场景：亲人关怀"
  },
  {
    "src": "resources/base/media/icon_high_temperature.png",
    "description": "高温/温度计图标，适用场景：亲人关怀"
  },
  {
    "src": "resources/base/media/icon_weather1.png",
    "description": "天气/雨伞图标，适用场景：亲人关怀"
  },
  {
    "src": "resources/base/media/icon_tiktok.png",
    "description": "抖音图标，适用场景：防沉迷"
  },
  {
    "src": "resources/base/media/icon_timing.png",
    "description": "计时图标，适用场景：防沉迷"
  },
  {
    "src": "resources/base/media/icon_charge.png",
    "description": "充电/闪电图标，适用场景：低电模式"
  },
  {
    "src": "resources/base/media/icon_clear.png",
    "description": "清除图标，适用场景：清理无忧"
  },
  {
    "src": "resources/base/media/icon_earphone.png",
    "description": "耳机图标，适用场景：戴耳机播控"
  },
  {
    "src": "resources/base/media/icon_phone.png",
    "description": "手机图标，适用场景：专注模式"
  },
  {
    "src": "resources/base/media/icon_car.png",
    "description": "汽车/打车图标，适用场景：雨天打车"
  },
  {
    "src": "resources/base/media/icon_time1.png",
    "description": "时间图标，适用场景：雨天打车"
  },
  {
    "src": "resources/base/media/icon_weathe2.png",
    "description": "天气图标，适用场景：雨天打车"
  },
  {
    "src": "resources/base/media/icon_alarm_clock.png",
    "description": "闹钟图标，适用场景：当下日程"
  },
  {
    "src": "resources/base/media/icon_focus.png",
    "description": "专注图标，适用场景：专注模式"
  },
  {
    "src": "resources/base/media/icon_schedule.png",
    "description": "日程图标，适用场景：当下日程"
  },
  {
    "src": "resources/base/media/icon_electricity.png",
    "description": "电池图标，适用场景：低电模式"
  },
  {
    "src": "resources/base/media/icon_save_power.png",
    "description": "省电图标，适用场景：低电模式"
  },
  {
    "src": "resources/base/media/icon_alarm_clock1.png",
    "description": "闹钟图标，适用场景：睡眠监督"
  },
  {
    "src": "resources/base/media/icon_remind.png",
    "description": "提醒图标，适用场景：睡眠监督"
  },
  {
    "src": "resources/base/media/icon_sleep.png",
    "description": "睡眠图标，适用场景：睡眠监督"
  },
  {
    "src": "resources/base/media/icon_run.png",
    "description": "运动/跑步图标，适用场景：当下日程"
  },
  {
    "src": "resources/base/media/icon_schedule2.png",
    "description": "日程图标，适用场景：当下日程"
  },
  {
    "src": "resources/base/media/icon_left.png",
    "description": "上一首图标，适用场景：戴耳机播控"
  },
  {
    "src": "resources/base/media/icon_like.png",
    "description": "收藏/心形图标，适用场景：戴耳机播控"
  },
  {
    "src": "resources/base/media/icon_music.png",
    "description": "音乐图标，适用场景：戴耳机播控"
  },
  {
    "src": "resources/base/media/icon_right.png",
    "description": "下一首图标，适用场景：戴耳机播控"
  }
]
```

## 选择规则

- 必须先按用户场景、语义角色和 `description` 匹配素材。
- 如果存在明确匹配的素材，且卡片仍需要该语义图标、图片、媒体或视觉锚点，必须使用匹配素材的 `src`。
- 匹配成功后，不要用 `Text` 字形、emoji、SVG、自绘形状、相似资源路径或未声明图片替代该语义素材。
- 只使用清单中声明过的 `src`，不要编造相似路径、重命名文件或替换目录。
- 只有没有语义匹配素材，或用户明确要求不用图片/图标素材时，才省略 `Image`，改用渐变、半透明块、文本字形、`Progress`、`Divider` 或 `Stack` 等非媒体视觉技法。

## 输出规则

- 静态素材可直接写入 `Image.src`，例如 `"src": "resources/base/media/icon_meeting.png"`。
- 如果素材选择需要由 DataModel 管理，将 `Image.src` 绑定到 `/asset/...`，并在 `updateDataModel.value` 中把该字段初始化为清单中声明过的 `src`。
- 不要把素材库写入 CardSpec；CardSpec 只描述端侧 data capability。
