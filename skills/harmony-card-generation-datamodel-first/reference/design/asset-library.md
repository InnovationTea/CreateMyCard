# 素材库

生成卡片需要图标、图片、媒体路径或视觉锚点时读取本文档。只要入选内容存在可由素材承担的识别、状态、动作、主媒体或视觉锚点职责，也先读取本文档再决定是否使用 `Image`。读完后只从下表选择 `src`，不要编造相似路径、重命名文件或替换目录。

## 选择规则

- 先按用户场景、语义角色和下表 `description` 匹配素材。
- 触发素材检查看内容职责，不靠业务名枚举：对象需要被快速识别、状态需要图形化、动作需要方向/播放/拨打等视觉指示、主媒体或地点需要可视锚点、模板含 `asset` 槽位，或设计正准备用文字字形/自绘图形/背景图替代素材时，都先查表。
- 用户未提供素材不等于素材不可用；本表声明的本地 SVG 就是可用素材。
- 如果存在明确匹配的素材，且卡片仍需要该语义图标、图片、媒体或视觉锚点，必须使用匹配素材的 `src`。
- 图标数量不设独立硬上限，按角色槽位和 L1 布局预算判断：非模板 `2x2` 默认优先 1 个主视觉/身份图标；模板 `2x2` 可按 manifest 槽位保留两个 tile/metric 图标、2-3 个同组状态图标或一个图标动作；`2x4` 可随主媒体、并列事实、时间线或动作区扩展，但每个图标必须承担识别、状态、动作或主媒体职责。
- 匹配成功后，不要用 `Text` 字形、emoji、自绘形状、相似资源路径、未声明 SVG 或未声明图片替代该语义素材。
- 只有没有语义匹配素材、加入图标会破坏 L1 布局预算，或用户明确要求不用图片/图标素材时，才省略 `Image`。

## SVG 图标索引

所有 `src` 均以 `resources/base/media` 为前缀，素材格式统一为 `.svg`。

| src | description |
| --- | --- |
| `resources/base/media/air_fill.svg` | 空调/空气循环实心图标，黑色，图形呈矩形风口加出风箭头造型，适用场景：空调控制面板、智能家居空气管理 |
| `resources/base/media/air_open_fill.svg` | 空调开启/新风实心图标，黑色，图形为开启状态的风口造型，适用场景：空调开启状态展示、新风系统控制 |
| `resources/base/media/airplane_departure.svg` | 飞机起飞图标，黑色，图形为飞机从跑道起飞的侧视图，适用场景：出行计划、航班出发信息、旅行日程 |
| `resources/base/media/airplane_fill_1.svg` | 飞机实心图标，黑色，图形为正面朝上的飞机俯视轮廓，适用场景：旅行场景、航班信息展示、出行卡片 |
| `resources/base/media/alarm_fill_1.svg` | 闹钟实心图标，黑白双色，图形为带铃铛的圆形表盘，适用场景：闹钟设置、定时提醒、日程提醒 |
| `resources/base/media/backward_fill.svg` | 快退/后退实心图标，黑色，图形为两个向左的三角箭头，适用场景：音乐播放器快退控制、视频回退 |
| `resources/base/media/battery_leaf_fill.svg` | 电池与绿叶组合实心图标，黑色，图形为电池加叶片造型，适用场景：节能模式、绿色用电、环保出行 |
| `resources/base/media/bell_fill.svg` | 铃铛实心图标，黑色，图形为经典吊铃造型，适用场景：通知提醒、消息提示、闹铃开启状态 |
| `resources/base/media/bell_slash_fill.svg` | 铃铛加斜杠实心图标，黑白双色，图形为铃铛上叠加删除线，适用场景：静音模式、关闭通知、勿扰设置 |
| `resources/base/media/bolt_fill.svg` | 闪电实心图标，黑色，图形为竖向闪电符号，适用场景：充电状态、快充指示、用电量展示 |
| `resources/base/media/bus_fill.svg` | 公交车实心图标，黑色，图形为正面视角公共汽车轮廓，适用场景：公共交通出行、路线导航、公交到站提醒 |
| `resources/base/media/calendar_fill.svg` | 日历实心图标，黑色，图形为带格线的日历本造型，适用场景：日程管理、日历事件查看、当日安排 |
| `resources/base/media/checkmark_calendar_fill.svg` | 带对勾的日历实心图标，黑白双色，图形为日历上叠加对勾，适用场景：已完成日程、日程确认、任务打卡 |
| `resources/base/media/clean_fill.svg` | 清洁实心图标，黑色，图形为清洁工具或净化造型，适用场景：清洁模式、空气净化、家居清洁提醒 |
| `resources/base/media/clock.svg` | 时钟线框图标，黑色，图形为圆形表盘加指针的线性轮廓，适用场景：时间显示、定时功能、倒计时 |
| `resources/base/media/clock_fill.svg` | 时钟实心图标，黑白双色，图形为圆形实心表盘加白色指针，适用场景：时间显示、闹钟设置、定时器 |
| `resources/base/media/cold.svg` | 寒冷/雪花图标，黑色，图形为六角雪花晶体造型，适用场景：制冷模式、低温天气展示、空调冷风设置 |
| `resources/base/media/drop_1.svg` | 水滴图标，黑色，图形为圆润水滴轮廓，适用场景：湿度数据展示、饮水提醒、天气降雨信息 |
| `resources/base/media/earphone_case_16644.svg` | 耳机收纳盒实心图标，黑色，图形为无线耳机充电盒造型，适用场景：蓝牙耳机设备连接、音频设备管理 |
| `resources/base/media/externaldrive_fill.svg` | 外置存储设备实心图标，黑色，图形为矩形硬盘盒造型，适用场景：本地存储管理、数据备份、文件传输 |
| `resources/base/media/face.svg` | 人脸图标，黑色，图形为简洁人脸轮廓，适用场景：人脸识别解锁、用户头像占位、个人身份展示 |
| `resources/base/media/fast_forward.svg` | 快进图标，黑色，图形为两个向右的三角箭头，适用场景：音乐播放器快进控制、视频快进 |
| `resources/base/media/figure_pool_swim.svg` | 游泳人物图标，黑色，图形为人体游泳动作侧视轮廓，适用场景：运动记录、游泳锻炼追踪、健康运动卡片 |
| `resources/base/media/figure_run.svg` | 跑步人物图标，黑色，图形为人体奔跑动作侧视轮廓，适用场景：运动记录、跑步锻炼追踪、步数统计 |
| `resources/base/media/flame_fill.svg` | 火焰实心图标，黑色，图形为向上燃烧的火焰造型，适用场景：热量消耗展示、加热功能、高温天气提示 |
| `resources/base/media/heart_fill.svg` | 心形实心图标，黑色，图形为标准爱心轮廓，适用场景：健康数据、心率监测展示、收藏/喜欢功能 |
| `resources/base/media/heat_generation.svg` | 发热/暖气图标，黑色，图形为散热或暖气片波浪造型，适用场景：暖气控制、制热模式、冬季取暖设置 |
| `resources/base/media/house_fill.svg` | 房屋实心图标，黑白双色，图形为三角屋顶加矩形门洞的家形造型，适用场景：首页导航、智能家居入口、回家提醒 |
| `resources/base/media/id_fill.svg` | 身份证/工牌实心图标，黑色，图形为矩形证件卡片造型，适用场景：身份识别、工牌/证件展示、当下日程身份信息 |
| `resources/base/media/kidswatch_fill.svg` | 儿童手表实心图标，黑色，图形为圆形表盘加表带的手表造型，适用场景：儿童设备管理、家长控制、儿童安全 |
| `resources/base/media/l_circle_fill.svg` | 字母L圆形实心图标，黑色，图形为圆形背景内白色L字母，适用场景：标签分类标识、左侧导航标记 |
| `resources/base/media/lamp_ceiling.svg` | 吸顶灯图标（关灯状态），黑色，图形为圆形灯盘加固定架造型，适用场景：智能照明控制、灯光管理、家居灯光 |
| `resources/base/media/lamp_ceiling_light.svg` | 吸顶灯亮起图标（开灯状态），黑色，图形为圆形灯盘加射线光芒造型，适用场景：灯光开启状态展示、智能照明控制 |
| `resources/base/media/local_fill.svg` | 本地/定位实心图标，黑色，图形为圆形加中心圆点的定位标记，适用场景：本地内容、当前位置标注、定位功能 |
| `resources/base/media/location_north_up_right_fill.svg` | 方向导航实心图标，黑色，图形为指向右上方的导航箭头，适用场景：地图导航、方向指引、路线规划 |
| `resources/base/media/moon_circle_fill.svg` | 月亮圆形实心图标，黑白双色，图形为圆形背景内白色月牙，适用场景：夜间模式、睡眠追踪、勿扰模式 |
| `resources/base/media/moon_z_fill_1.svg` | 月亮加Z睡眠实心图标，黑色，图形为月牙旁附带字母Z表示入睡，适用场景：睡眠模式开启、休息提醒、晚安场景 |
| `resources/base/media/music_fill.svg` | 音乐音符实心图标，黑色，图形为双音符连接造型，适用场景：音乐播放卡片、音频功能入口、歌单展示 |
| `resources/base/media/pause_fill.svg` | 暂停实心图标，黑色，图形为两条竖向平行矩形，适用场景：音乐/视频播放暂停控制 |
| `resources/base/media/person_3_fill.svg` | 三人组实心图标，黑色，图形为三个人形轮廓并排排列，适用场景：群组联系人、团队成员展示、家庭成员列表 |
| `resources/base/media/phone_fill.svg` | 电话实心图标，黑色，图形为经典听筒造型，适用场景：拨打电话、通话功能入口 |
| `resources/base/media/phone_fill_1.svg` | 电话实心图标（变体），黑色，图形为听筒加信号波形，适用场景：来电接听、通话状态展示 |
| `resources/base/media/play_fill.svg` | 播放实心图标，黑色，图形为向右的实心三角形，适用场景：音乐/视频播放控制、媒体播放器 |
| `resources/base/media/qrcode.svg` | 二维码图标，黑色，图形为标准方形二维码点阵图案，适用场景：扫码功能、快速连接设备、信息分享 |
| `resources/base/media/r_circle_fill.svg` | 字母R圆形实心图标，黑色，图形为圆形背景内白色R字母，适用场景：标签分类标识、录制状态标记 |
| `resources/base/media/stopwatch_fill.svg` | 秒表实心图标，黑白双色，图形为带按钮的圆形秒表造型，适用场景：计时功能、运动计时、倒计时 |
| `resources/base/media/sun_max.svg` | 太阳最大亮度图标，黑色，图形为圆形太阳加多条粗放射线，适用场景：天气晴朗展示、屏幕亮度最大值 |
| `resources/base/media/sun_min.svg` | 太阳最小亮度图标，黑色，图形为圆形太阳加短细放射线，适用场景：低亮度调节、柔和光线、日出/日落场景 |
| `resources/base/media/tram_fill.svg` | 有轨电车实心图标，黑色，图形为带导线的有轨电车侧视轮廓，适用场景：城市公共交通、地铁/轻轨出行导航 |
| `resources/base/media/z_alarm_fill.svg` | 带Z的闹钟贪睡实心图标，黑色，图形为闹钟旁附带字母Z表示贪睡，适用场景：闹钟贪睡功能、延迟提醒、睡眠场景 |

## 布局规则

- 所有 `Image` 必须写明确 `width`、`height` 和 `objectFit: "contain"`。
- 小语义图标通常 16-24vp；主视觉图标在 `2x2` 通常 44-64vp，在 `2x4` 通常 48-72vp。
- 图标和文字之间保留 4-8vp；先扣除图标宽度和 gap，再估算文本能否完整显示。
- 不要为了使用图标压缩 CTA、日期、时间、标题、状态或主指标。

## 输出规则

- 静态素材可直接写入 `Image.src`，例如 `"src": "resources/base/media/calendar_fill.svg"`。
- 如果素材选择需要由 DataModel 管理，将 `Image.src` 写成完整表达式（例如 `"{{ ${/asset/icon} }}"`），并在 `updateDataModel.value` 中把该字段初始化为上表声明过的 `src`。
- 不要把素材库写入 CardSpec；CardSpec 只描述端侧 data capability。
