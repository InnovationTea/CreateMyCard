# 素材库

生成卡片需要图标、图片、媒体路径或视觉锚点时读取本文档。只要入选内容存在可由素材承担的识别、状态、动作、主媒体或视觉锚点职责，也先读取本文档再决定是否使用 `Image`。读完后只从下表选择 `src`，不要编造相似路径、重命名文件或替换目录。

## 选择规则

- 先按用户场景、语义角色和下表 `description` 匹配素材。
- 触发素材检查看内容职责，不靠业务名枚举：对象需要被快速识别、状态需要图形化、动作需要方向/播放/拨打等视觉指示、主媒体或地点需要可视锚点、模板含 `asset` 槽位，或设计正准备用文字字形/自绘图形/背景图替代素材时，都先查表。
- 用户未提供素材不等于素材不可用；本表声明的本地素材就是可用素材。
- 如果存在明确匹配的素材，且卡片仍需要该语义图标、图片、媒体或视觉锚点，必须使用匹配素材的 `src`。
- 图标数量不设独立硬上限，按角色槽位和 L1 布局预算判断：非模板 `2x2` 默认优先 1 个主视觉/身份图标；模板 `2x2` 可按 manifest 槽位保留两个 tile/metric 图标、2-3 个同组状态图标或一个图标动作；`2x4` 可随主媒体、并列事实、时间线或动作区扩展，但每个图标必须承担识别、状态、动作或主媒体职责。
- 匹配成功后，不要用 `Text` 字形、emoji、自绘形状、SVG、相似资源路径或未声明图片替代该语义素材。
- 只有没有语义匹配素材、加入图标会破坏 L1 布局预算，或用户明确要求不用图片/图标素材时，才省略 `Image`。

## 本地素材索引

所有 `src` 均以 `resources/base/media` 为前缀，素材格式统一为 `.png`。

| src | description |
| --- | --- |
| `resources/base/media/cloudy.png` | 云朵组合，彩色图标，适用场景：天气、出行 |
| `resources/base/media/cloudy_turning_sunny.png` | 小云朵和太阳组合，彩色图标，适用场景：天气、出行 |
| `resources/base/media/courier_box.png` | 快递箱子，彩色图标，适用场景：物流信息、取件提醒 |
| `resources/base/media/partly_cloudy.png` | 云朵在前、太阳在后的组合，彩色图标，适用场景：天气、出行 |
| `resources/base/media/rain.png` | 云朵和雨滴组合，彩色图标，适用场景：天气、出行 |
| `resources/base/media/snow.png` | 雪花，彩色图标，适用场景：天气、出行 |
| `resources/base/media/sunny.png` | 太阳，彩色图标，适用场景：天气、出行 |
| `resources/base/media/thunder.png` | 云朵和闪电组合，彩色图标，适用场景：天气、出行 |
| `resources/base/media/thunderstorm.png` | 云朵、闪电和雨滴组合，彩色图标，适用场景：天气、出行 |
| `resources/base/media/tornado.png` | 龙卷风，彩色图标，适用场景：天气、出行 |

## PNG 图标索引

所有 `src` 均以 `resources/base/media` 为前缀，素材格式统一为 `.png`。

| src | description |
| --- | --- |
| `resources/base/media/icon_id.png` | 工牌/ID图标，适用场景：当下日程 |
| `resources/base/media/icon_meeting.png` | 会议图标，适用场景：当下日程 |
| `resources/base/media/icon_time.png` | 时间图标，适用场景：当下日程 |
| `resources/base/media/icon_watermark.png` | 水印图标，适用场景：当下日程 |
| `resources/base/media/icon_allergy.png` | 过敏源图标，适用场景：亲人关怀 |
| `resources/base/media/icon_call.png` | 电话图标，适用场景：亲人关怀 |
| `resources/base/media/icon_high_temperature.png` | 高温/温度计图标，适用场景：亲人关怀 |
| `resources/base/media/icon_weather1.png` | 天气/雨伞图标，适用场景：亲人关怀 |
| `resources/base/media/icon_tiktok.png` | 抖音图标，适用场景：防沉迷 |
| `resources/base/media/icon_timing.png` | 计时图标，适用场景：防沉迷 |
| `resources/base/media/icon_charge.png` | 充电/闪电图标，适用场景：低电模式 |
| `resources/base/media/icon_clear.png` | 清除图标，适用场景：清理无忧 |
| `resources/base/media/icon_earphone.png` | 耳机图标，适用场景：戴耳机播控 |
| `resources/base/media/icon_phone.png` | 手机图标，适用场景：专注模式 |
| `resources/base/media/icon_car.png` | 汽车/打车图标，适用场景：雨天打车 |
| `resources/base/media/icon_time1.png` | 时间图标，适用场景：雨天打车 |
| `resources/base/media/icon_weathe2.png` | 天气图标，适用场景：雨天打车 |
| `resources/base/media/icon_alarm_clock.png` | 闹钟图标，适用场景：当下日程 |
| `resources/base/media/icon_focus.png` | 专注图标，适用场景：专注模式 |
| `resources/base/media/icon_schedule.png` | 日程图标，适用场景：当下日程 |
| `resources/base/media/icon_electricity.png` | 电池图标，适用场景：低电模式 |
| `resources/base/media/icon_save_power.png` | 省电图标，适用场景：低电模式 |
| `resources/base/media/icon_alarm_clock1.png` | 闹钟图标，适用场景：睡眠监督 |
| `resources/base/media/icon_remind.png` | 提醒图标，适用场景：睡眠监督 |
| `resources/base/media/icon_sleep.png` | 睡眠图标，适用场景：睡眠监督 |
| `resources/base/media/icon_run.png` | 运动/跑步图标，适用场景：当下日程 |
| `resources/base/media/icon_schedule2.png` | 日程图标，适用场景：当下日程 |
| `resources/base/media/icon_left.png` | 上一首图标，适用场景：戴耳机播控 |
| `resources/base/media/icon_like.png` | 收藏/心形图标，适用场景：戴耳机播控 |
| `resources/base/media/icon_music.png` | 音乐图标，适用场景：戴耳机播控 |
| `resources/base/media/icon_right.png` | 下一首图标，适用场景：戴耳机播控 |

## 布局规则

- 所有 `Image` 必须写明确 `width`、`height` 和 `objectFit: "contain"`。
- 小语义图标通常 16-24vp；主视觉图标在 `2x2` 通常 44-64vp，在 `2x4` 通常 48-72vp。
- 图标和文字之间保留 4-8vp；先扣除图标宽度和 gap，再估算文本能否完整显示。
- 不要为了使用图标压缩 CTA、日期、时间、标题、状态或主指标。

## 输出规则

- 静态素材可直接写入 `Image.src`，例如 `"src": "resources/base/media/icon_meeting.png"`。
- 如果素材选择需要由 DataModel 管理，将 `Image.src` 写成完整表达式（例如 `"{{ ${/asset/icon} }}"`），并在 `updateDataModel.value` 中把该字段初始化为上表声明过的 `src`。
- 不要把素材库写入 CardSpec；CardSpec 只描述端侧 data capability。
