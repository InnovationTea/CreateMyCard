# 素材库

本文件是可扩展的本地/资源素材清单。生成卡片需要图标、图片、媒体路径或视觉锚点时，先按用户场景语义和 `description` 匹配这里的素材。

```json
[
  { "src": "resource/会议widget/icon_id.png", "description": "工牌/ID图标" },
  { "src": "resource/会议widget/icon_meeting.png", "description": "会议图标" },
  { "src": "resource/会议widget/icon_time.png", "description": "时间图标" },
  { "src": "resource/会议widget/icon_watermark.png", "description": "水印图标" },
  { "src": "resource/关怀widget/icon_allergy.png", "description": "过敏源图标" },
  { "src": "resource/关怀widget/icon_call.png", "description": "电话图标" },
  { "src": "resource/关怀widget/icon_high_temperature.png", "description": "高温/温度计图标" },
  { "src": "resource/关怀widget/icon_weather1.png", "description": "天气/雨伞图标" },
  { "src": "resource/应用时长widget/icon_tiktok.png", "description": "抖音图标" },
  { "src": "resource/应用时长widget/icon_timing.png", "description": "计时图标" },
  { "src": "resource/手机状态widget/icon_charge.png", "description": "充电/闪电图标" },
  { "src": "resource/手机状态widget/icon_clear.png", "description": "清除图标" },
  { "src": "resource/手机状态widget/icon_earphone.png", "description": "耳机图标" },
  { "src": "resource/手机状态widget/icon_phone.png", "description": "手机图标" },
  { "src": "resource/打车widget/icon_car.png", "description": "汽车/打车图标" },
  { "src": "resource/打车widget/icon_time1.png", "description": "时间图标" },
  { "src": "resource/打车widget/icon_weathe2.png", "description": "天气图标" },
  { "src": "resource/日程widget/icon_alarm_clock.png", "description": "闹钟图标" },
  { "src": "resource/日程widget/icon_focus.png", "description": "专注图标" },
  { "src": "resource/日程widget/icon_schedule.png", "description": "日程图标" },
  { "src": "resource/电量widget/icon_electricity.png", "description": "电池图标" },
  { "src": "resource/电量widget/icon_save_power.png", "description": "省电图标" },
  { "src": "resource/睡眠widget/icon_alarm_clock1.png", "description": "闹钟图标" },
  { "src": "resource/睡眠widget/icon_remind.png", "description": "提醒图标" },
  { "src": "resource/睡眠widget/icon_sleep.png", "description": "睡眠图标" },
  { "src": "resource/运动计划widget/icon_run.png", "description": "运动/跑步图标" },
  { "src": "resource/运动计划widget/icon_schedule2.png", "description": "日程图标" },
  { "src": "resource/音乐widget/icon_left.png", "description": "上一首图标" },
  { "src": "resource/音乐widget/icon_like.png", "description": "收藏/心形图标" },
  { "src": "resource/音乐widget/icon_music.png", "description": "音乐图标" },
  { "src": "resource/音乐widget/icon_right.png", "description": "下一首图标" }
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
