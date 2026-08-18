# 素材库

生成卡片需要图标、图片、媒体路径或视觉锚点时读取本文档。只要入选内容存在可由素材承担的识别、状态、动作、主媒体或视觉锚点职责，也先读取本文档再决定是否使用 `Image`。读完后只从下表选择 `src`，不要编造相似路径、重命名文件或替换目录。

## 选择规则

- 先按用户场景、语义角色和下表 `description` 匹配素材。
- 触发素材检查看内容职责，不靠业务名枚举：对象需要被快速识别、状态需要图形化、动作需要方向/播放/拨打等视觉指示、主媒体或地点需要可视锚点、模板含 `asset` 槽位，或设计正准备用文字字形/自绘图形/背景图替代素材时，都先查表。
- 用户未提供素材不等于素材不可用；本表声明的本地素材就是可用素材。
- 如果存在明确匹配的素材，且卡片仍需要该语义图标、图片、媒体或视觉锚点，必须使用匹配素材的 `src`。
- 图标数量不设独立硬上限，按角色槽位和 L1 布局预算判断：非模板 `2x2` 默认优先 1 个主视觉/身份图标；模板 `2x2` 可按 manifest 槽位保留两个 tile/metric 图标、2-3 个同组状态图标或一个图标动作；`2x4` 可随主媒体、并列事实、时间线或动作区扩展，但每个图标必须承担识别、状态、动作或主媒体职责。
- 匹配成功后，不要用 `Text` 字形、emoji、自绘形状、相似资源路径、未声明 SVG 或未声明图片替代该语义素材。
- SVG 默认可使用 `fillColor` 染色；仅多色、渐变、透明、位图或染色后会丢失细节的例外素材在描述中注明限制。
- 只有没有语义匹配素材、加入图标会破坏 L1 布局预算，或用户明确要求不用图片/图标素材时，才省略 `Image`。

## 本地素材索引

所有 `src` 均以 `resources/base/media` 为前缀，素材格式为 `.svg` 或 `.png`。

| src | description |
| --- | --- |
| `resources/base/media/air_fill.svg` | 样式：默认黑色的单色实心空调室内机图标，正面矩形机身，顶部有三个圆点，底部为横向出风口；适用：空调设备、空调关闭或普通状态、智能家居空气设备。 |
| `resources/base/media/air_open_fill.svg` | 样式：默认黑色的单色实心空调室内机图标，正面矩形机身，底部有三条向下气流线；适用：空调开启、送风、新风或空气循环运行状态。 |
| `resources/base/media/airplane_departure.svg` | 样式：飞机起飞图标，默认黑色，图形为飞机从跑道起飞的侧视图；适用：出行计划、航班出发信息、旅行日程。 |
| `resources/base/media/airplane_fill_1.svg` | 样式：默认黑色的单色实心飞机俯视图，机头朝右上方倾斜；适用：航空旅行、航班概览、飞行状态。 |
| `resources/base/media/alarm_fill_1.svg` | 样式：闹钟实心图标，黑白双色，图形为带铃铛的圆形表盘，建议保留原色；适用：闹钟设置、定时提醒、日程提醒。 |
| `resources/base/media/backward_fill.svg` | 样式：快退/后退实心图标，默认黑色，图形为两个向左的三角箭头；适用：音乐播放器快退控制、视频回退。 |
| `resources/base/media/battery_leaf_fill.svg` | 样式：默认黑色的单色实心横向电池图标，电池内部为叶片留白；适用：省电模式、节能电池、绿色用电状态。 |
| `resources/base/media/bell_fill.svg` | 样式：铃铛实心图标，默认黑色，图形为经典吊铃造型；适用：通知提醒、消息提示、闹铃开启状态。 |
| `resources/base/media/bell_slash_fill.svg` | 样式：铃铛加斜杠实心图标，黑白双色，图形为铃铛上叠加删除线，建议保留原色；适用：静音模式、关闭通知、勿扰设置。 |
| `resources/base/media/bolt_fill.svg` | 样式：默认黑色的单色实心竖向闪电图标；适用：正在充电、快充、电能或闪电状态。 |
| `resources/base/media/bus_fill.svg` | 样式：公交车实心图标，默认黑色，图形为正面视角公共汽车轮廓；适用：公共交通出行、路线导航、公交到站提醒。 |
| `resources/base/media/calendar_fill.svg` | 样式：日历实心图标，默认黑色，图形为带格线的日历本造型；适用：日程管理、日历事件查看、当日安排。 |
| `resources/base/media/checkmark_calendar_fill.svg` | 样式：带对勾的日历实心图标，黑白双色，图形为日历上叠加对勾，建议保留原色；适用：已完成日程、日程确认、任务打卡。 |
| `resources/base/media/clean_fill.svg` | 样式：默认黑色的单色实心扫帚图标，竖向手柄，下方为三束刷毛；适用：清扫、垃圾清理、系统清理或家居清洁动作。 |
| `resources/base/media/clock.svg` | 样式：时钟线框图标，默认黑色，图形为圆形表盘加指针的线性轮廓；适用：时间显示、定时功能、倒计时。 |
| `resources/base/media/clock_fill.svg` | 样式：时钟实心图标，黑白双色，图形为圆形实心表盘加白色指针，建议保留原色；适用：时间显示、闹钟设置、定时器。 |
| `resources/base/media/cold.svg` | 样式：默认黑色的单色线框圆形人脸，口鼻处佩戴口罩；适用：佩戴口罩、防护、呼吸道健康或传染风险提示。 |
| `resources/base/media/drop_1.svg` | 样式：水滴图标，默认黑色，图形为圆润水滴轮廓；适用：湿度数据展示、饮水提醒、天气降雨信息。 |
| `resources/base/media/earphone_case_16644.svg` | 样式：耳机收纳盒实心图标，默认黑色，图形为无线耳机充电盒造型；适用：蓝牙耳机设备连接、音频设备管理。 |
| `resources/base/media/externaldrive_fill.svg` | 样式：外置存储设备实心图标，默认黑色，图形为矩形硬盘盒造型；适用：本地存储管理、数据备份、文件传输。 |
| `resources/base/media/face.svg` | 样式：默认黑色的单色线框圆形笑脸，带眼睛、鼻子和微笑嘴形；适用：愉悦状态、用户形象占位、满意度或友好提示。 |
| `resources/base/media/fast_forward.svg` | 样式：快进图标，默认黑色，图形为两个向右的三角箭头；适用：音乐播放器快进控制、视频快进。 |
| `resources/base/media/figure_pool_swim.svg` | 样式：游泳人物图标，默认黑色，图形为人体游泳动作侧视轮廓；适用：运动记录、游泳锻炼追踪、健康运动卡片。 |
| `resources/base/media/figure_run.svg` | 样式：跑步人物图标，默认黑色，图形为人体奔跑动作侧视轮廓；适用：运动记录、跑步锻炼追踪、步数统计。 |
| `resources/base/media/flame_fill.svg` | 样式：默认黑色的单色实心火焰图标；适用：运动热量消耗、燃烧、火焰或加热状态。 |
| `resources/base/media/heart_fill.svg` | 样式：默认黑色的单色实心爱心图标；适用：喜欢、收藏、关爱、心脏健康或心率栏目入口。 |
| `resources/base/media/heat_generation.svg` | 样式：默认黑色的单色线框温度计，底部为圆形感温泡，内部带弧形刻度；适用：温度、升温、制热或体感温度。 |
| `resources/base/media/house_fill.svg` | 样式：房屋实心图标，黑白双色，图形为三角屋顶加矩形门洞的家形造型，建议保留原色；适用：首页导航、智能家居入口、回家提醒。 |
| `resources/base/media/hourglass_fill.svg` | 样式：沙漏和齿轮组合图标，图形为沙漏线性右下角齿轮组合的造型，建议保留原色；适用：应用时长。 |
| `resources/base/media/id_fill.svg` | 样式：默认黑色的单色圆角矩形徽标，内部以留白显示大写 ID；适用：会议 ID、身份编号、证件编号或标识码。 |
| `resources/base/media/kidswatch_fill.svg` | 样式：默认黑色的单色实心智能手表正视图，矩形圆角表盘和上下表带；适用：儿童手表、可穿戴设备、手表连接或设备管理。 |
| `resources/base/media/l_circle_fill.svg` | 样式：黑色实心圆形徽标，内部以留白显示大写 L，建议保留原色；适用：左耳、左声道、左侧设备或 L 标记。 |
| `resources/base/media/lamp_ceiling.svg` | 样式：吸顶灯图标（关灯状态），默认黑色，图形为圆形灯盘加固定架造型；适用：智能照明控制、灯光管理、家居灯光。 |
| `resources/base/media/lamp_ceiling_light.svg` | 样式：吸顶灯亮起图标（开灯状态），默认黑色，图形为圆形灯盘加射线光芒造型；适用：灯光开启状态展示、智能照明控制。 |
| `resources/base/media/local_fill.svg` | 样式：默认黑色的单色实心地图定位针，中央为圆形留白；适用：当前位置、地点、地图标记、位置服务。 |
| `resources/base/media/location_north_up_right_fill.svg` | 样式：方向导航实心图标，默认黑色，图形为指向右上方的导航箭头；适用：地图导航、方向指引、路线规划。 |
| `resources/base/media/moon_circle_fill.svg` | 样式：月亮圆形实心图标，黑白双色，图形为圆形背景内白色月牙，建议保留原色；适用：夜间模式、睡眠追踪、勿扰模式。 |
| `resources/base/media/moon_z_fill_1.svg` | 样式：月亮加Z睡眠实心图标，默认黑色，图形为月牙旁附带字母Z表示入睡；适用：睡眠模式开启、休息提醒、晚安场景。 |
| `resources/base/media/music_fill.svg` | 样式：音乐音符实心图标，默认黑色，图形为双音符连接造型；适用：音乐播放卡片、音频功能入口、歌单展示。 |
| `resources/base/media/pause_fill.svg` | 样式：暂停实心图标，默认黑色，图形为两条竖向平行矩形；适用：音乐/视频播放暂停控制。 |
| `resources/base/media/person_3_fill.svg` | 样式：三人组实心图标，默认黑色，图形为三个人形轮廓并排排列；适用：群组联系人、团队成员展示、家庭成员列表。 |
| `resources/base/media/phone_fill.svg` | 样式：电话实心图标，默认黑色，图形为经典听筒造型；适用：拨打电话、通话功能入口。 |
| `resources/base/media/play_fill.svg` | 样式：播放实心图标，默认黑色，图形为向右的实心三角形；适用：音乐/视频播放控制、媒体播放器。 |
| `resources/base/media/qrcode.svg` | 样式：默认黑色的单色线面结合二维码符号，包含三个定位方块和右下点阵；适用：扫码入口、二维码功能、设备配对或分享入口。 |
| `resources/base/media/r_circle_fill.svg` | 样式：黑色实心圆形徽标，内部以留白显示大写 R，建议保留原色；适用：右耳、右声道、右侧设备或 R 标记。 |
| `resources/base/media/stopwatch_fill.svg` | 样式：秒表实心图标，黑白双色，图形为带按钮的圆形秒表造型，建议保留原色；适用：计时功能、运动计时、倒计时。 |
| `resources/base/media/sun_max.svg` | 样式：默认黑色的单色线框太阳，中央大圆环，周围为八条较长放射线；适用：高亮度、强光、晴天或亮度增大。 |
| `resources/base/media/sun_min.svg` | 样式：默认黑色的单色线框太阳，中央圆环，周围为八个较短圆点式光芒；适用：低亮度、柔和阳光、亮度减小。 |
| `resources/base/media/thermometer_snowflake.svg` | 样式：温度计/雪花组合图标，默认黑色，图形为温度计右侧叠加雪花造型；适用：寒冷预警、体感指数。 |
| `resources/base/media/thermometer_sun_fill.svg` | 样式：温度计/太阳组合图标，默认黑色，图形为温度计右侧叠加太阳造型；适用：高温预警、体感指数。 |
| `resources/base/media/thunder_storm.svg` | 样式：下雨和闪电造型组合图标，图形为下雨中带有闪电的造型；适用：雷暴预警。 |
| `resources/base/media/tram_fill.svg` | 样式：默认黑色的单色实心有轨电车正视图，顶部带受电弓，底部带车轮；适用：有轨电车、轻轨、轨道交通站点或线路。 |
| `resources/base/media/typhoon_fill.svg` | 样式：台风黑色图标，图形为台风漩涡造型；适用：台风预警、台风路径。 |
| `resources/base/media/z_alarm_fill.svg` | 样式：带Z的闹钟贪睡实心图标，默认黑色，图形为闹钟旁附带字母Z表示贪睡；适用：闹钟贪睡功能、延迟提醒、睡眠场景。 |

## 场景图标索引

所有 `src` 均以 `resources/base/media` 为前缀。除 `icon_tiktok.png` 外，本节图标均为 `.svg`。

| src | description |
| --- | --- |
| `resources/base/media/icon_id.svg` | 样式：米灰色半透明圆角矩形徽标，内部以浅色显示大写 ID，原始尺寸为 12×12，保留原色与透明度；适用：会议 ID、身份编号或日程中的标识码。 |
| `resources/base/media/icon_meeting.svg` | 样式：纯白色单色线面结合的会议演示板图标，画板内有两条横线，原始尺寸为 14×14；适用：会议、汇报、演示、议程。 |
| `resources/base/media/icon_watermark.svg` | 样式：米灰色低透明度的大型日历轮廓装饰，画布和图形尺寸关系特殊，保留原色与透明层级；适用：日程卡片的弱化背景水印或装饰锚点。 |
| `resources/base/media/icon_allergy.svg` | 样式：默认黑色的单色侧面人头轮廓，面部周围分布颗粒点，表现过敏原或空气刺激；适用：过敏、花粉、空气刺激、呼吸道敏感提示。 |
| `resources/base/media/icon_high_temperature.svg` | 样式：默认黑色的单色线框温度计，内部温度柱较高，源文件语义指向体温；适用：体温偏高、发热、人体温度提醒。 |
| `resources/base/media/icon_weather1.svg` | 样式：黄、白、浅灰多组渐变的彩色天气图标，太阳从云层右上方露出，表示多云或晴间多云，保留原色；适用：多云、晴间多云、天气概览或天气入口。 |
| `resources/base/media/icon_tiktok.png` | 样式：黑色圆形底上的抖音品牌音符，包含青色、红色和白色叠色，64×64 PNG，PNG 位图需保留品牌原色；适用：抖音应用、抖音使用时长或防沉迷统计。 |
| `resources/base/media/icon_timing.svg` | 样式：白色实心秒表配黑色指针，顶部有按钮，属于高对比双色图标，建议保留原色；适用：计时、使用时长、倒计时或时限。 |
| `resources/base/media/icon_earphone.svg` | 样式：黑色实心左右分体式开放耳机，局部有白色高光与分隔，建议保留原色；适用：无线耳机本体、耳机连接、左右耳设备状态。 |
| `resources/base/media/icon_phone.svg` | 样式：默认黑色的单色线框竖向智能手机，内部有屏幕轮廓；适用：手机设备、手机状态、专注模式中的手机对象。 |
| `resources/base/media/icon_car.svg` | 样式：默认黑色的单色汽车正视图，带前窗、车灯和车轮；适用：汽车、打车、驾车出行或车辆状态。 |
| `resources/base/media/icon_focus.svg` | 样式：默认黑色的单色实心月牙图标，无圆形底和睡眠字样；适用：专注模式、勿扰模式、夜间状态。 |
| `resources/base/media/icon_schedule.svg` | 样式：纯白色单色实心日历图标，顶部双装订环，内部为六个日期点，浅色背景需染色；适用：日程、日期、日历入口或当日安排。 |
| `resources/base/media/icon_save_power.svg` | 样式：默认黑色的单色实心横向电池图标，内部为叶片造型；适用：省电模式、节能设置、绿色电池状态。 |
| `resources/base/media/icon_run.svg` | 样式：纯白色单色奔跑人物侧视图，浅色背景需染色；适用：跑步、运动锻炼、活动日程。 |
| `resources/base/media/icon_left.svg` | 样式：黑色实心圆形徽标，内部以白色显示大写 L，源文件语义为左耳机，建议保留原色；适用：左耳、左声道、左侧耳机电量。 |
| `resources/base/media/icon_music.svg` | 样式：黑色实心双音符图标，内部使用白色分隔形成音符结构，建议保留原色；适用：音乐、歌曲、歌单或音频内容。 |
| `resources/base/media/icon_right.svg` | 样式：黑色实心圆形徽标，内部以白色显示大写 R，源文件语义为右耳机，建议保留原色；适用：右耳、右声道、右侧耳机电量。 |

## 布局规则

- 所有 `Image` 必须写明确 `width`、`height` 和 `objectFit: "contain"`。
- 小语义图标通常 16-24vp；主视觉图标在 `2x2` 通常 44-64vp，在 `2x4` 通常 48-72vp。
- 图标和文字之间保留 4-8vp；先扣除图标宽度和 gap，再估算文本能否完整显示。
- 不要为了使用图标压缩 CTA、日期、时间、标题、状态或主指标。

## 输出规则

- 静态素材可直接写入 `Image.src`，例如 `"src": "resources/base/media/calendar_fill.svg"` 或 `"src": "resources/base/media/icon_meeting.svg"`。
- 如果素材选择需要由 DataModel 管理，将 `Image.src` 写成完整表达式（例如 `"{{ ${/asset/icon} }}"`），并在 `updateDataModel.value` 中把该字段初始化为上表声明过的 `src`。
- 不要把素材库写入 CardSpec；CardSpec 只描述端侧 data capability。
