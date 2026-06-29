# 素材库

生成卡片需要图标、图片、媒体路径或视觉锚点时读取本文档。读完后只从下表选择 `src`，不要编造相似路径、重命名文件或替换目录。

## 选择规则

- 先按用户场景、语义角色和上表场景匹配素材。
- 如果存在明确匹配的素材，且卡片仍需要该语义图标、图片、媒体或视觉锚点，必须使用匹配素材的 `src`。
- `2x2` 通常最多使用 1 个语义图标；`2x4` 可使用 1 个主图标，或 1-2 个同组小图标。
- 匹配成功后，不要用 `Text` 字形、emoji、SVG、自绘形状、相似资源路径或未声明图片替代该语义素材。
- 只有没有语义匹配素材、加入图标会破坏 L1 布局预算，或用户明确要求不用图片/图标素材时，才省略 `Image`。

## 场景索引

| 场景 | 可用语义 | `src` |
| --- | --- | --- |
| 当下日程/会议 | 工牌/ID | `resources/base/media/icon_id.png` |
| 当下日程/会议 | 会议 | `resources/base/media/icon_meeting.png` |
| 当下日程/会议 | 时间 | `resources/base/media/icon_time.png` |
| 当下日程/会议 | 水印 | `resources/base/media/icon_watermark.png` |
| 当下日程/提醒 | 闹钟 | `resources/base/media/icon_alarm_clock.png` |
| 当下日程/提醒 | 日程 | `resources/base/media/icon_schedule.png` |
| 运动日程 | 跑步 | `resources/base/media/icon_run.png` |
| 运动日程 | 日程 | `resources/base/media/icon_schedule2.png` |
| 亲人关怀 | 过敏源 | `resources/base/media/icon_allergy.png` |
| 亲人关怀 | 电话 | `resources/base/media/icon_call.png` |
| 亲人关怀 | 高温/温度计 | `resources/base/media/icon_high_temperature.png` |
| 亲人关怀 | 天气/雨伞 | `resources/base/media/icon_weather1.png` |
| 防沉迷/应用用量 | 抖音 | `resources/base/media/icon_tiktok.png` |
| 防沉迷/应用用量 | 计时 | `resources/base/media/icon_timing.png` |
| 低电/省电 | 充电/闪电 | `resources/base/media/icon_charge.png` |
| 低电/省电 | 电池 | `resources/base/media/icon_electricity.png` |
| 低电/省电 | 省电 | `resources/base/media/icon_save_power.png` |
| 手机状态/清理 | 清除 | `resources/base/media/icon_clear.png` |
| 手机状态/专注 | 手机 | `resources/base/media/icon_phone.png` |
| 手机状态/专注 | 专注 | `resources/base/media/icon_focus.png` |
| 戴耳机播控 | 耳机 | `resources/base/media/icon_earphone.png` |
| 戴耳机播控 | 音乐 | `resources/base/media/icon_music.png` |
| 戴耳机播控 | 收藏/心形 | `resources/base/media/icon_like.png` |
| 戴耳机播控 | 上一首 | `resources/base/media/icon_left.png` |
| 戴耳机播控 | 下一首 | `resources/base/media/icon_right.png` |
| 雨天打车 | 汽车/打车 | `resources/base/media/icon_car.png` |
| 雨天打车 | 时间 | `resources/base/media/icon_time1.png` |
| 雨天打车 | 天气 | `resources/base/media/icon_weathe2.png` |
| 睡眠监督 | 闹钟 | `resources/base/media/icon_alarm_clock1.png` |
| 睡眠监督 | 提醒 | `resources/base/media/icon_remind.png` |
| 睡眠监督 | 睡眠 | `resources/base/media/icon_sleep.png` |

## 布局规则

- 所有 `Image` 必须写明确 `width`、`height` 和 `objectFit: "contain"`。
- 小语义图标通常 16-24vp；主视觉图标在 `2x2` 通常 44-64vp，在 `2x4` 通常 48-72vp。
- 图标和文字之间保留 4-8vp；先扣除图标宽度和 gap，再估算文本能否完整显示。
- 不要为了使用图标压缩 CTA、日期、时间、标题、状态或主指标。

## 输出规则

- 静态素材可直接写入 `Image.src`，例如 `"src": "resources/base/media/icon_meeting.png"`。
- 如果素材选择需要由 DataModel 管理，将 `Image.src` 绑定到 `/asset/...`，并在 `updateDataModel.value` 中把该字段初始化为上表声明过的 `src`。
- 不要把素材库写入 CardSpec；CardSpec 只描述端侧 data capability。
