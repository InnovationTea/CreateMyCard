# getWidgetCapabilityOverview 测试报告

- 生成时间：2026-07-10T02:03:51.676293+00:00
- 接口名：`getWidgetCapabilityOverview`
- WebSocket path：`/api/v1/ws/tools/getWidgetCapabilityOverview`
- 请求协议：content/deviceInfo/session 外层包络
- requestId：`7676c2c8-a6d3-413c-8074-c62ed30db8de&1`
- 消息状态：`result`
- 业务状态：`success`

## 入参

```json
{
  "content": {
    "bundleName": "com.omega_w_0823.hmservice"
  },
  "deviceInfo": {
    "countryCode": "CN",
    "deviceFormation": "HDSpeaker",
    "deviceType": 0,
    "locale": "zh-CN",
    "phoneType": "CLS-AL30",
    "prdVer": "11.7.5.205",
    "sysVer": "EmotionUI_9.0.0",
    "time": "20260707115342975"
  },
  "pagination": {
    "limit": 5,
    "start": ""
  },
  "session": {
    "interactionId": "1",
    "isNew": false,
    "sessionId": "7676c2c8-a6d3-413c-8074-c62ed30db8de"
  },
  "userAuth": {
    "user": {
      "userId": "test-user-001"
    }
  },
  "utterance": {
    "original": "",
    "type": "text"
  },
  "version": "1.0",
  "bundleName": "com.omega_w_0823.hmservice"
}
```

## 出参

```json
{
  "errorCode": "0",
  "errorMessage": "",
  "reply": {
    "streamInfo": {
      "streamContent": "type='result' tool='getWidgetCapabilityOverview' operation='getWidgetCapabilityOverview' requestId='7676c2c8-a6d3-413c-8074-c62ed30db8de&1' data={'apiVersion': 'v1', 'capabilityRegistryVersion': 'app-11.7.5.205_rom-36', 'dataCapabilities': [{'id': 'ViewWeather', 'description': '查询指定地区或用户当前位置的当前天气与未来数日天气预报。'}, {'id': 'GetCalendarEvents', 'description': '查询用户系统日历中的日程安排。高度精简的结构化日历模型，包含日程倒计时计算、日程开始/截止时间文本，以及支持一键拉起第三方应用（如视频会议、赛事直播）的深度跳转链接。'}, {'id': 'GetAppUsageDurationAndPower', 'description': '获取指定应用的使用时长和耗电量数据'}, {'id': 'GetBluetoothEarphoneStatus', 'description': '查询当前手机连接的蓝牙耳机状态，包括耳机名称、主盒与左右耳的当前独立剩余电量百分比，以及它们各自的充电状态。'}, {'id': 'GetHealthAndSportSummary', 'description': '一键合并查询用户指定时间段内的大健康、日常大盘活动与单次专业运动训练指标。包含极其精细的夜间科学睡眠分析、当日全天步数/热量/距离总合大盘，以及最近一次专业运动训练的起止时间、计划与详尽的心率区间剖析。'}, {'id': 'GetSystemMemInfo', 'description': '查询系统当前的内存使用情况，包括总内存、完全空闲内存、可用内存以及真实内存占用百分比。'}], 'eventCapabilities': [{'id': 'event.call.phone', 'type': 'event', 'call': 'clickToApi', 'description': '点击跳转至指定号码的拨号界面，给某个亲人打电话', 'targetScene': 'CallPhone', 'argsTemplate': {'intentName': 'CallPhone', 'params': {'relationship': '', 'phoneNumber': ''}}, 'parametersSchema': {'intentName': 'string', 'params': {'relationship': 'string', 'phoneNumber': 'string'}}, 'dependencies': {'requiredPackages': []}}, {'id': 'event.clean.memory', 'type': 'event', 'call': 'clickToApi', 'description': '点击清理手机运行时内存，释放系统资源', 'targetScene': 'CleanRAMMemory', 'argsTemplate': {'intentName': 'CleanRAMMemory', 'params': {}}, 'parametersSchema': {'intentName': 'string', 'params': {}}, 'dependencies': {'requiredPackages': []}}, {'id': 'event.enter.meeting', 'type': 'event', 'call': 'clickToApi', 'description': '点击一键加入下一个日程对应的在线会议', 'targetScene': 'EnterMeeting', 'argsTemplate': {'intentName': 'EnterMeeting', 'params': {}}, 'parametersSchema': {'intentName': 'string', 'params': {}}, 'dependencies': {'requiredPackages': []}}, {'id': 'event.open.settings.dnd', 'type': 'event', 'call': 'clickToDeeplink', 'description': '打开系统设置中的情景模式，用户可以打开免打扰或专注模式', 'targetApp': '设置', 'targetScene': 'Settings', 'argsTemplate': {'intentName': 'Settings', 'bundleName': 'com.huawei.hmos.settings', 'abilityName': 'com.huawei.hmos.settings.MainAbility', 'uri': 'intelligent_scene_entry'}, 'parametersSchema': {'intentName': 'string', 'bundleName': 'string', 'abilityName': 'string', 'uri': 'string'}, 'dependencies': {'requiredPackages': []}}, {'id': 'event.open.settings.bluetooth', 'type': 'event', 'call': 'clickToDeeplink', 'description': '打开系统设置中的蓝牙设置页', 'targetApp': '设置', 'targetScene': 'Settings', 'argsTemplate': {'intentName': 'Settings', 'bundleName': 'com.huawei.hmos.settings', 'abilityName': 'com.huawei.hmos.settings.MainAbility', 'uri': 'bluetooth_entry'}, 'parametersSchema': {'intentName': 'string', 'bundleName': 'string', 'abilityName': 'string', 'uri': 'string'}, 'dependencies': {'requiredPackages': []}}, {'id': 'event.open.settings.battery', 'type': 'event', 'call': 'clickToDeeplink', 'description': '打开系统设置中的电池页', 'targetApp': '设置', 'targetScene': 'Settings', 'argsTemplate': {'intentName': 'Settings', 'bundleName': 'com.huawei.hmos.settings', 'abilityName': 'com.huawei.hmos.settings.MainAbility', 'uri': 'battery'}, 'parametersSchema': {'intentName': 'string', 'bundleName': 'string', 'abilityName': 'string', 'uri': 'string'}, 'dependencies': {'requiredPackages': []}}, {'id': 'event.open.settings.batteryHealth', 'type': 'event', 'call': 'clickToDeeplink', 'description': '打开系统设置中的电池健康页', 'targetApp': '设置', 'targetScene': 'Settings', 'argsTemplate': {'intentName': 'Settings', 'bundleName': 'com.huawei.hmos.settings', 'abilityName': 'com.huawei.hmos.settings.MainAbility', 'uri': 'smart_charge_battery_health'}, 'parametersSchema': {'intentName': 'string', 'bundleName': 'string', 'abilityName': 'string', 'uri': 'string'}, 'dependencies': {'requiredPackages': []}}, {'id': 'event.open.settings.parentControl', 'type': 'event', 'call': 'clickToDeeplink', 'description': '打开系统设置中的健康使用App页面，为了设置应用使用时长', 'targetApp': '设置', 'targetScene': 'Settings', 'argsTemplate': {'intentName': 'Settings', 'bundleName': 'com.huawei.hmos.settings', 'abilityName': 'com.huawei.hmos.settings.MainAbility', 'uri': 'parent_control'}, 'parametersSchema': {'intentName': 'string', 'bundleName': 'string', 'abilityName': 'string', 'uri': 'string'}, 'dependencies': {'requiredPackages': []}}, {'id': 'event.open.settings.storage', 'type': 'event', 'call': 'clickToDeeplink', 'description': '打开系统设置中的存储空间页', 'targetApp': '设置', 'targetScene': 'Settings', 'argsTemplate': {'intentName': 'Settings', 'bundleName': 'com.huawei.hmos.settings', 'abilityName': 'com.huawei.hmos.settings.MainAbility', 'uri': 'storage_settings'}, 'parametersSchema': {'intentName': 'string', 'bundleName': 'string', 'abilityName': 'string', 'uri': 'string'}, 'dependencies': {'requiredPackages': []}}, {'id': 'event.open.weather', 'type': 'event', 'call': 'clickToDeeplink', 'description': '打开手机天气应用某城市页，uri为固定值勿更改', 'targetApp': '天气', 'targetScene': 'Weather_CityCode', 'argsTemplate': {'intentName': 'Weather_CityCode', 'bundleName': '', 'abilityName': '', 'uri': 'hww://www.huawei.com/totemweather?enterType=share&cityCode='}, 'parametersSchema': {'intentName': 'string', 'bundleName': 'string', 'abilityName': 'string', 'uri': 'string'}, 'dependencies': {'requiredPackages': []}}, {'id': 'event.open.clock.alarm', 'type': 'event', 'call': 'clickToDeeplink', 'description': '打开闹钟应用首页', 'targetApp': '闹钟', 'targetScene': 'Clock', 'argsTemplate': {'intentName': 'Clock', 'bundleName': 'com.huawei.hmos.clock', 'abilityName': 'com.huawei.hmos.clock.phone', 'uri': ''}, 'parametersSchema': {'intentName': 'string', 'bundleName': 'string', 'abilityName': 'string', 'uri': 'string'}, 'dependencies': {'requiredPackages': []}}, {'id': 'event.open.music.daily', 'type': 'event', 'call': 'clickToDeeplink', 'description': '打开音乐app的每日30首歌单，uri为固定值勿更改', 'targetApp': '音乐', 'targetScene': 'Music', 'argsTemplate': {'intentName': 'Music', 'bundleName': '', 'abilityName': '', 'uri': 'hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4'}, 'parametersSchema': {'intentName': 'string', 'bundleName': 'string', 'abilityName': 'string', 'uri': 'string'}, 'dependencies': {'requiredPackages': []}}, {'id': 'event.open.music.favorite', 'type': 'event', 'call': 'clickToDeeplink', 'description': '打开音乐app的收藏歌单/心动歌单，uri为固定值勿更改', 'targetApp': '音乐', 'targetScene': 'Music', 'argsTemplate': {'intentName': 'Music', 'bundleName': '', 'abilityName': '', 'uri': 'hwmusic://com.huawei.hmsapp.music/showMusicList?code=favoriteSong&type=412'}, 'parametersSchema': {'intentName': 'string', 'bundleName': 'string', 'abilityName': 'string', 'uri': 'string'}, 'dependencies': {'requiredPackages': []}}, {'id': 'event.open.health.sport', 'type': 'event', 'call': 'clickToDeeplink', 'description': '打开运动健康应用的锻炼Tab页', 'targetApp': '运动健康', 'targetScene': 'Health', 'argsTemplate': {'intentName': 'Health', 'bundleName': '', 'abilityName': '', 'uri': 'huaweischeme://healthapp/home/sport?sportType=2'}, 'parametersSchema': {'intentName': 'string', 'bundleName': 'string', 'abilityName': 'string', 'uri': 'string'}, 'dependencies': {'requiredPackages': [{'packageName': 'com.huawei.hmos.health.core'}]}}, {'id': 'event.open.health.sleep', 'type': 'event', 'call': 'clickToDeeplink', 'description': '打开运动健康应用的睡眠详情页', 'targetApp': '运动健康', 'targetScene': 'Health', 'argsTemplate': {'intentName': 'Health', 'bundleName': '', 'abilityName': '', 'uri': 'huaweischeme://healthapp/router/sleepDetail'}, 'parametersSchema': {'intentName': 'string', 'bundleName': 'string', 'abilityName': 'string', 'uri': 'string'}, 'dependencies': {'requiredPackages': [{'packageName': 'com.huawei.hmos.health.core'}]}}, {'id': 'event.viewCalendarEvent', 'type': 'event', 'call': 'clickToIntent', 'description': '点击日程卡片 or 日程按钮，跳转到日程 App 查看该日程的详情', 'targetScene': 'ViewCalendarEvent', 'argsTemplate': {'intentName': 'ViewCalendarEvent', 'params': {'entityId': {'path': 'entityId'}}}, 'parametersSchema': {'intentName': 'string', 'params': {'entityId': 'string'}}, 'dependencies': {'requiredPackages': []}}, {'id': 'event.startNavigate', 'type': 'event', 'call': 'clickToIntent', 'description': '点击导航按钮，跳转到地图应用进行导航。大模型需根据用户说的目的地选择location的值，只支持回家和去公司的导航', 'targetScene': 'StartNavigate', 'argsTemplate': {'intentName': 'StartNavigate', 'params': {'dstLocation': {'location': '', 'latitude': '', 'longitude': ''}}}, 'parametersSchema': {'intentName': 'string', 'params': {'dstLocation': {'location': 'string', 'latitude': 'string', 'longitude': 'string'}}}, 'dependencies': {'requiredPackages': []}}, {'id': 'event.setPowerSavingMode', 'type': 'event', 'call': 'clickToIntent', 'description': '点击一键开启/关闭省电模式。大模型根据用户表达确定是开启还是关闭，然后传对应的switchFlag值', 'targetScene': 'SetSettingSwitch', 'argsTemplate': {'intentName': 'SetSettingSwitch', 'params': {'appBundleName': 'com.huawei.hmos.settings', 'itemName': 'battery_saving_mode', 'switchFlag': 0}}, 'parametersSchema': {'intentName': 'string', 'params': {'appBundleName': 'string', 'itemName': 'string', 'switchFlag': 'number'}}, 'dependencies': {'requiredPackages': []}}], 'assetCandidates': [{'id': 'asset.air_fill', 'type': 'asset', 'src': 'resources/base/media/air_fill.svg', 'description': '空调/空气循环实心图标，黑色，图形呈矩形风口加出风箭头造型，适用场景：空调控制面板、智能家居空气管理', 'sceneTags': ['air', 'home'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.air_open_fill', 'type': 'asset', 'src': 'resources/base/media/air_open_fill.svg', 'description': '空调开启/新风实心图标，黑色，图形为开启状态的风口造型，适用场景：空调开启状态展示、新风系统控制', 'sceneTags': ['air', 'home'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.airplane_departure', 'type': 'asset', 'src': 'resources/base/media/airplane_departure.svg', 'description': '飞机起飞图标，黑色，图形为飞机从跑道起飞的侧视图，适用场景：出行计划、航班出发信息、旅行日程', 'sceneTags': ['travel', 'flight'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.airplane_fill_1', 'type': 'asset', 'src': 'resources/base/media/airplane_fill_1.svg', 'description': '飞机实心图标，黑色，图形为正面朝上的飞机俯视轮廓，适用场景：旅行场景、航班信息展示、出行卡片', 'sceneTags': ['travel', 'flight'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.alarm_fill_1', 'type': 'asset', 'src': 'resources/base/media/alarm_fill_1.svg', 'description': '闹钟实心图标，黑白双色，图形为带铃铛的圆形表盘，适用场景：闹钟设置、定时提醒、日程提醒', 'sceneTags': ['alarm', 'reminder'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.backward_fill', 'type': 'asset', 'src': 'resources/base/media/backward_fill.svg', 'description': '快退/后退实心图标，黑色，图形为两个向左的三角箭头，适用场景：音乐播放器快退控制、视频回退', 'sceneTags': ['media', 'control'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.battery_leaf_fill', 'type': 'asset', 'src': 'resources/base/media/battery_leaf_fill.svg', 'description': '电池与绿叶组合实心图标，黑色，图形为电池加叶片造型，适用场景：节能模式、绿色用电、环保出行', 'sceneTags': ['battery', 'power'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.bell_fill', 'type': 'asset', 'src': 'resources/base/media/bell_fill.svg', 'description': '铃铛实心图标，黑色，图形为经典吊铃造型，适用场景：通知提醒、消息提示、闹铃开启状态', 'sceneTags': ['notification', 'alarm'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.bell_slash_fill', 'type': 'asset', 'src': 'resources/base/media/bell_slash_fill.svg', 'description': '铃铛加斜杠实心图标，黑白双色，图形为铃铛上叠加删除线，适用场景：静音模式、关闭通知、勿扰设置', 'sceneTags': ['notification', 'silent'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.bolt_fill', 'type': 'asset', 'src': 'resources/base/media/bolt_fill.svg', 'description': '闪电实心图标，黑色，图形为竖向闪电符号，适用场景：充电状态、快充指示、用电量展示', 'sceneTags': ['battery', 'power'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.bus_fill', 'type': 'asset', 'src': 'resources/base/media/bus_fill.svg', 'description': '公交车实心图标，黑色，图形为正面视角公共汽车轮廓，适用场景：公共交通出行、路线导航、公交到站提醒', 'sceneTags': ['traffic', 'bus'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.calendar_fill', 'type': 'asset', 'src': 'resources/base/media/calendar_fill.svg', 'description': '日历实心图标，黑色，图形为带格线的日历本造型，适用场景：日程管理、日历事件查看、当日安排', 'sceneTags': ['calendar', 'schedule'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.checkmark_calendar_fill', 'type': 'asset', 'src': 'resources/base/media/checkmark_calendar_fill.svg', 'description': '带对勾的日历实心图标，黑白双色，图形为日历上叠加对勾，适用场景：已完成日程、日程确认、任务打卡', 'sceneTags': ['calendar', 'task'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.clean_fill', 'type': 'asset', 'src': 'resources/base/media/clean_fill.svg', 'description': '清洁实心图标，黑色，图形为清洁工具或净化造型，适用场景：清洁模式、空气净化、家居清洁提醒', 'sceneTags': ['clean', 'home'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.clock', 'type': 'asset', 'src': 'resources/base/media/clock.svg', 'description': '时钟线框图标，黑色，图形为圆形表盘加指针的线性轮廓，适用场景：时间显示、定时功能、倒计时', 'sceneTags': ['time', 'clock'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.clock_fill', 'type': 'asset', 'src': 'resources/base/media/clock_fill.svg', 'description': '时钟实心图标，黑白双色，图形为圆形实心表盘加白色指针，适用场景：时间显示、闹钟设置、定时器', 'sceneTags': ['time', 'clock'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.cold', 'type': 'asset', 'src': 'resources/base/media/cold.svg', 'description': '寒冷/雪花图标，黑色，图形为六角雪花晶体造型，适用场景：制冷模式、低温天气展示、空调冷风设置', 'sceneTags': ['weather', 'cold'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.cloudy', 'type': 'asset', 'src': 'resources/base/media/cloudy.png', 'description': '云朵组合，彩色图标，适用场景：天气、出行', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.cloudy_turning_sunny', 'type': 'asset', 'src': 'resources/base/media/cloudy_turning_sunny.png', 'description': '小云朵和太阳组合，彩色图标，适用场景：天气、出行', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.courier_box', 'type': 'asset', 'src': 'resources/base/media/courier_box.png', 'description': '快递箱子，彩色图标，适用场景：物流信息、取件提醒', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.drop_1', 'type': 'asset', 'src': 'resources/base/media/drop_1.svg', 'description': '水滴图标，黑色，图形为圆润水滴轮廓，适用场景：湿度数据展示、饮水提醒、天气降雨信息', 'sceneTags': ['weather', 'water'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.earphone_case_16644', 'type': 'asset', 'src': 'resources/base/media/earphone_case_16644.svg', 'description': '耳机收纳盒实心图标，黑色，图形为无线耳机充电盒造型，适用场景：蓝牙耳机设备连接、音频设备管理', 'sceneTags': ['device', 'audio'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.externaldrive_fill', 'type': 'asset', 'src': 'resources/base/media/externaldrive_fill.svg', 'description': '外置存储设备实心图标，黑色，图形为矩形硬盘盒造型，适用场景：本地存储管理、数据备份、文件传输', 'sceneTags': ['storage', 'device'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.face', 'type': 'asset', 'src': 'resources/base/media/face.svg', 'description': '人脸图标，黑色，图形为简洁人脸轮廓，适用场景：人脸识别解锁、用户头像占位、个人身份展示', 'sceneTags': ['identity', 'person'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.fast_forward', 'type': 'asset', 'src': 'resources/base/media/fast_forward.svg', 'description': '快进图标，黑色，图形为两个向右的三角箭头，适用场景：音乐播放器快进控制、视频快进', 'sceneTags': ['media', 'control'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.figure_pool_swim', 'type': 'asset', 'src': 'resources/base/media/figure_pool_swim.svg', 'description': '游泳人物图标，黑色，图形为人体游泳动作侧视轮廓，适用场景：运动记录、游泳锻炼追踪、健康运动卡片', 'sceneTags': ['health', 'sport'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.figure_run', 'type': 'asset', 'src': 'resources/base/media/figure_run.svg', 'description': '跑步人物图标，黑色，图形为人体奔跑动作侧视轮廓，适用场景：运动记录、跑步锻炼追踪、步数统计', 'sceneTags': ['health', 'sport'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.flame_fill', 'type': 'asset', 'src': 'resources/base/media/flame_fill.svg', 'description': '火焰实心图标，黑色，图形为向上燃烧的火焰造型，适用场景：热量消耗展示、加热功能、高温天气提示', 'sceneTags': ['health', 'heat'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.heart_fill', 'type': 'asset', 'src': 'resources/base/media/heart_fill.svg', 'description': '心形实心图标，黑色，图形为标准爱心轮廓，适用场景：健康数据、心率监测展示、收藏/喜欢功能', 'sceneTags': ['health', 'heart'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.heat_generation', 'type': 'asset', 'src': 'resources/base/media/heat_generation.svg', 'description': '发热/暖气图标，黑色，图形为散热或暖气片波浪造型，适用场景：暖气控制、制热模式、冬季取暖设置', 'sceneTags': ['heat', 'home'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.house_fill', 'type': 'asset', 'src': 'resources/base/media/house_fill.svg', 'description': '房屋实心图标，黑白双色，图形为三角屋顶加矩形门洞的家形造型，适用场景：首页导航、智能家居入口、回家提醒', 'sceneTags': ['home'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.hourglass_fill', 'type': 'asset', 'src': 'resources/base/media/hourglass_fill.svg', 'description': '沙漏和齿轮组合图标，图形为沙漏线性右下角齿轮组合的造型，适用场景：应用时长', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.id_fill', 'type': 'asset', 'src': 'resources/base/media/id_fill.svg', 'description': '身份证/工牌实心图标，黑色，图形为矩形证件卡片造型，适用场景：身份识别、工牌/证件展示、当下日程身份信息', 'sceneTags': ['identity'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.kidswatch_fill', 'type': 'asset', 'src': 'resources/base/media/kidswatch_fill.svg', 'description': '儿童手表实心图标，黑色，图形为圆形表盘加表带的手表造型，适用场景：儿童设备管理、家长控制、儿童安全', 'sceneTags': ['device', 'watch'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.l_circle_fill', 'type': 'asset', 'src': 'resources/base/media/l_circle_fill.svg', 'description': '字母L圆形实心图标，黑色，图形为圆形背景内白色L字母，适用场景：标签分类标识、左侧导航标记', 'sceneTags': ['label'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.lamp_ceiling', 'type': 'asset', 'src': 'resources/base/media/lamp_ceiling.svg', 'description': '吸顶灯图标（关灯状态），黑色，图形为圆形灯盘加固定架造型，适用场景：智能照明控制、灯光管理、家居灯光', 'sceneTags': ['home', 'light'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.lamp_ceiling_light', 'type': 'asset', 'src': 'resources/base/media/lamp_ceiling_light.svg', 'description': '吸顶灯亮起图标（开灯状态），黑色，图形为圆形灯盘加射线光芒造型，适用场景：灯光开启状态展示、智能照明控制', 'sceneTags': ['home', 'light'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.local_fill', 'type': 'asset', 'src': 'resources/base/media/local_fill.svg', 'description': '本地/定位实心图标，黑色，图形为圆形加中心圆点的定位标记，适用场景：本地内容、当前位置标注、定位功能', 'sceneTags': ['location'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.location_north_up_right_fill', 'type': 'asset', 'src': 'resources/base/media/location_north_up_right_fill.svg', 'description': '方向导航实心图标，黑色，图形为指向右上方的导航箭头，适用场景：地图导航、方向指引、路线规划', 'sceneTags': ['location', 'navigation'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.moon_circle_fill', 'type': 'asset', 'src': 'resources/base/media/moon_circle_fill.svg', 'description': '月亮圆形实心图标，黑白双色，图形为圆形背景内白色月牙，适用场景：夜间模式、睡眠追踪、勿扰模式', 'sceneTags': ['sleep', 'night'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.moon_z_fill_1', 'type': 'asset', 'src': 'resources/base/media/moon_z_fill_1.svg', 'description': '月亮加Z睡眠实心图标，黑色，图形为月牙旁附带字母Z表示入睡，适用场景：睡眠模式开启、休息提醒、晚安场景', 'sceneTags': ['sleep', 'night'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.music_fill', 'type': 'asset', 'src': 'resources/base/media/music_fill.svg', 'description': '音乐音符实心图标，黑色，图形为双音符连接造型，适用场景：音乐播放卡片、音频功能入口、歌单展示', 'sceneTags': ['music', 'media'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.pause_fill', 'type': 'asset', 'src': 'resources/base/media/pause_fill.svg', 'description': '暂停实心图标，黑色，图形为两条竖向平行矩形，适用场景：音乐/视频播放暂停控制', 'sceneTags': ['media', 'control'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.person_3_fill', 'type': 'asset', 'src': 'resources/base/media/person_3_fill.svg', 'description': '三人组实心图标，黑色，图形为三个人形轮廓并排排列，适用场景：群组联系人、团队成员展示、家庭成员列表', 'sceneTags': ['person', 'group'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.phone_fill', 'type': 'asset', 'src': 'resources/base/media/phone_fill.svg', 'description': '电话实心图标，黑色，图形为经典听筒造型，适用场景：拨打电话、通话功能入口', 'sceneTags': ['phone', 'call'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.phone_fill_1', 'type': 'asset', 'src': 'resources/base/media/phone_fill_1.svg', 'description': '电话实心图标（变体），黑色，图形为听筒加信号波形，适用场景：来电接听、通话状态展示', 'sceneTags': ['phone', 'call'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.play_fill', 'type': 'asset', 'src': 'resources/base/media/play_fill.svg', 'description': '播放实心图标，黑色，图形为向右的实心三角形，适用场景：音乐/视频播放控制、媒体播放器', 'sceneTags': ['media', 'control'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.partly_cloudy', 'type': 'asset', 'src': 'resources/base/media/partly_cloudy.png', 'description': '云朵在前、太阳在后的组合，彩色图标，适用场景：天气、出行', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.qrcode', 'type': 'asset', 'src': 'resources/base/media/qrcode.svg', 'description': '二维码图标，黑色，图形为标准方形二维码点阵图案，适用场景：扫码功能、快速连接设备、信息分享', 'sceneTags': ['qrcode', 'share'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.rain', 'type': 'asset', 'src': 'resources/base/media/rain.png', 'description': '云朵和雨滴组合，彩色图标，适用场景：天气、出行', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.r_circle_fill', 'type': 'asset', 'src': 'resources/base/media/r_circle_fill.svg', 'description': '字母R圆形实心图标，黑色，图形为圆形背景内白色R字母，适用场景：标签分类标识、录制状态标记', 'sceneTags': ['label'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.snow', 'type': 'asset', 'src': 'resources/base/media/snow.png', 'description': '雪花，彩色图标，适用场景：天气、出行', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.stopwatch_fill', 'type': 'asset', 'src': 'resources/base/media/stopwatch_fill.svg', 'description': '秒表实心图标，黑白双色，图形为带按钮的圆形秒表造型，适用场景：计时功能、运动计时、倒计时', 'sceneTags': ['time', 'sport'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.sunny', 'type': 'asset', 'src': 'resources/base/media/sunny.png', 'description': '太阳，彩色图标，适用场景：天气、出行', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.sun_max', 'type': 'asset', 'src': 'resources/base/media/sun_max.svg', 'description': '太阳最大亮度图标，黑色，图形为圆形太阳加多条粗放射线，适用场景：天气晴朗展示、屏幕亮度最大值', 'sceneTags': ['weather', 'sun'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.sun_min', 'type': 'asset', 'src': 'resources/base/media/sun_min.svg', 'description': '太阳最小亮度图标，黑色，图形为圆形太阳加短细放射线，适用场景：低亮度调节、柔和光线、日出/日落场景', 'sceneTags': ['weather', 'sun'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.thermometer_snowflake', 'type': 'asset', 'src': 'resources/base/media/thermometer_snowflake.svg', 'description': '温度计/雪花组合图标，黑色，图形为温度计右侧叠加雪花造型，适用场景：寒冷预警、体感指数', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.thermometer_sun_fill', 'type': 'asset', 'src': 'resources/base/media/thermometer_sun_fill.svg', 'description': '温度计/太阳组合图标，黑色，图形为温度计右侧叠加太阳造型，适用场景：高温预警、体感指数', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.thunder', 'type': 'asset', 'src': 'resources/base/media/thunder.png', 'description': '云朵和闪电组合，彩色图标，适用场景：天气、出行', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.thunder_storm', 'type': 'asset', 'src': 'resources/base/media/thunder_storm.svg', 'description': '下雨和闪电造型组合图标，图形为下雨中带有闪电的造型，适用场景：雷暴预警', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.thunderstorm', 'type': 'asset', 'src': 'resources/base/media/thunderstorm.png', 'description': '云朵、闪电和雨滴组合，彩色图标，适用场景：天气、出行', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.tornado', 'type': 'asset', 'src': 'resources/base/media/tornado.png', 'description': '龙卷风，彩色图标，适用场景：天气、出行', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.tram_fill', 'type': 'asset', 'src': 'resources/base/media/tram_fill.svg', 'description': '有轨电车实心图标，黑色，图形为带导线的有轨电车侧视轮廓，适用场景：城市公共交通、地铁/轻轨出行导航', 'sceneTags': ['traffic', 'tram'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.typhoon_fill', 'type': 'asset', 'src': 'resources/base/media/typhoon_fill.svg', 'description': '台风黑色图标，图形为台风漩涡造型，适用场景：台风预警、台风路径', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.z_alarm_fill', 'type': 'asset', 'src': 'resources/base/media/z_alarm_fill.svg', 'description': '带Z的闹钟贪睡实心图标，黑色，图形为闹钟旁附带字母Z表示贪睡，适用场景：闹钟贪睡功能、延迟提醒、睡眠场景', 'sceneTags': ['alarm', 'sleep'], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_id', 'type': 'asset', 'src': 'resources/base/media/icon_id.png', 'description': '工牌/ID图标，适用场景：当下日程', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_meeting', 'type': 'asset', 'src': 'resources/base/media/icon_meeting.png', 'description': '会议图标，适用场景：当下日程', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_time', 'type': 'asset', 'src': 'resources/base/media/icon_time.png', 'description': '时间图标，适用场景：当下日程', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_watermark', 'type': 'asset', 'src': 'resources/base/media/icon_watermark.png', 'description': '水印图标，适用场景：当下日程', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_allergy', 'type': 'asset', 'src': 'resources/base/media/icon_allergy.png', 'description': '过敏源图标，适用场景：亲人关怀', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_call', 'type': 'asset', 'src': 'resources/base/media/icon_call.png', 'description': '电话图标，适用场景：亲人关怀', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_high_temperature', 'type': 'asset', 'src': 'resources/base/media/icon_high_temperature.png', 'description': '高温/温度计图标，适用场景：亲人关怀', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_weather1', 'type': 'asset', 'src': 'resources/base/media/icon_weather1.png', 'description': '天气/雨伞图标，适用场景：亲人关怀', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_tiktok', 'type': 'asset', 'src': 'resources/base/media/icon_tiktok.png', 'description': '抖音图标，适用场景：防沉迷', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_timing', 'type': 'asset', 'src': 'resources/base/media/icon_timing.png', 'description': '计时图标，适用场景：防沉迷', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_charge', 'type': 'asset', 'src': 'resources/base/media/icon_charge.png', 'description': '充电/闪电图标，适用场景：低电模式', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_clear', 'type': 'asset', 'src': 'resources/base/media/icon_clear.png', 'description': '清除图标，适用场景：清理无忧', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_earphone', 'type': 'asset', 'src': 'resources/base/media/icon_earphone.png', 'description': '耳机图标，适用场景：戴耳机播控', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_phone', 'type': 'asset', 'src': 'resources/base/media/icon_phone.png', 'description': '手机图标，适用场景：专注模式', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_car', 'type': 'asset', 'src': 'resources/base/media/icon_car.png', 'description': '汽车/打车图标，适用场景：雨天打车', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_time1', 'type': 'asset', 'src': 'resources/base/media/icon_time1.png', 'description': '时间图标，适用场景：雨天打车', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_weathe2', 'type': 'asset', 'src': 'resources/base/media/icon_weathe2.png', 'description': '天气图标，适用场景：雨天打车', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_alarm_clock', 'type': 'asset', 'src': 'resources/base/media/icon_alarm_clock.png', 'description': '闹钟图标，适用场景：当下日程', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_focus', 'type': 'asset', 'src': 'resources/base/media/icon_focus.png', 'description': '专注图标，适用场景：专注模式', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_schedule', 'type': 'asset', 'src': 'resources/base/media/icon_schedule.png', 'description': '日程图标，适用场景：当下日程', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_electricity', 'type': 'asset', 'src': 'resources/base/media/icon_electricity.png', 'description': '电池图标，适用场景：低电模式', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_save_power', 'type': 'asset', 'src': 'resources/base/media/icon_save_power.png', 'description': '省电图标，适用场景：低电模式', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_alarm_clock1', 'type': 'asset', 'src': 'resources/base/media/icon_alarm_clock1.png', 'description': '闹钟图标，适用场景：睡眠监督', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_remind', 'type': 'asset', 'src': 'resources/base/media/icon_remind.png', 'description': '提醒图标，适用场景：睡眠监督', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_sleep', 'type': 'asset', 'src': 'resources/base/media/icon_sleep.png', 'description': '睡眠图标，适用场景：睡眠监督', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_run', 'type': 'asset', 'src': 'resources/base/media/icon_run.png', 'description': '运动/跑步图标，适用场景：当下日程', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_schedule2', 'type': 'asset', 'src': 'resources/base/media/icon_schedule2.png', 'description': '日程图标，适用场景：当下日程', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_left', 'type': 'asset', 'src': 'resources/base/media/icon_left.png', 'description': '上一首图标，适用场景：戴耳机播控', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_like', 'type': 'asset', 'src': 'resources/base/media/icon_like.png', 'description': '收藏/心形图标，适用场景：戴耳机播控', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_music', 'type': 'asset', 'src': 'resources/base/media/icon_music.png', 'description': '音乐图标，适用场景：戴耳机播控', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}, {'id': 'asset.icon_right', 'type': 'asset', 'src': 'resources/base/media/icon_right.png', 'description': '下一首图标，适用场景：戴耳机播控', 'sceneTags': [], 'minXiaoyiVersion': '1.0.0'}], 'unavailableCapabilities': []} status='success' errorCode='' error={}",
      "streamingTextId": "7676c2c8-a6d3-413c-8074-c62ed30db8de&1",
      "streamType": "final",
      "textType": "plainText"
    },
    "items": [
      {
        "type": "result",
        "tool": "getWidgetCapabilityOverview",
        "operation": "getWidgetCapabilityOverview",
        "requestId": "7676c2c8-a6d3-413c-8074-c62ed30db8de&1",
        "data": {
          "apiVersion": "v1",
          "capabilityRegistryVersion": "app-11.7.5.205_rom-36",
          "dataCapabilities": [
            {
              "id": "ViewWeather",
              "description": "查询指定地区或用户当前位置的当前天气与未来数日天气预报。"
            },
            {
              "id": "GetCalendarEvents",
              "description": "查询用户系统日历中的日程安排。高度精简的结构化日历模型，包含日程倒计时计算、日程开始/截止时间文本，以及支持一键拉起第三方应用（如视频会议、赛事直播）的深度跳转链接。"
            },
            {
              "id": "GetAppUsageDurationAndPower",
              "description": "获取指定应用的使用时长和耗电量数据"
            },
            {
              "id": "GetBluetoothEarphoneStatus",
              "description": "查询当前手机连接的蓝牙耳机状态，包括耳机名称、主盒与左右耳的当前独立剩余电量百分比，以及它们各自的充电状态。"
            },
            {
              "id": "GetHealthAndSportSummary",
              "description": "一键合并查询用户指定时间段内的大健康、日常大盘活动与单次专业运动训练指标。包含极其精细的夜间科学睡眠分析、当日全天步数/热量/距离总合大盘，以及最近一次专业运动训练的起止时间、计划与详尽的心率区间剖析。"
            },
            {
              "id": "GetSystemMemInfo",
              "description": "查询系统当前的内存使用情况，包括总内存、完全空闲内存、可用内存以及真实内存占用百分比。"
            }
          ],
          "eventCapabilities": [
            {
              "id": "event.call.phone",
              "type": "event",
              "call": "clickToApi",
              "description": "点击跳转至指定号码的拨号界面，给某个亲人打电话",
              "targetScene": "CallPhone",
              "argsTemplate": {
                "intentName": "CallPhone",
                "params": {
                  "relationship": "",
                  "phoneNumber": ""
                }
              },
              "parametersSchema": {
                "intentName": "string",
                "params": {
                  "relationship": "string",
                  "phoneNumber": "string"
                }
              },
              "dependencies": {
                "requiredPackages": []
              }
            },
            {
              "id": "event.clean.memory",
              "type": "event",
              "call": "clickToApi",
              "description": "点击清理手机运行时内存，释放系统资源",
              "targetScene": "CleanRAMMemory",
              "argsTemplate": {
                "intentName": "CleanRAMMemory",
                "params": {}
              },
              "parametersSchema": {
                "intentName": "string",
                "params": {}
              },
              "dependencies": {
                "requiredPackages": []
              }
            },
            {
              "id": "event.enter.meeting",
              "type": "event",
              "call": "clickToApi",
              "description": "点击一键加入下一个日程对应的在线会议",
              "targetScene": "EnterMeeting",
              "argsTemplate": {
                "intentName": "EnterMeeting",
                "params": {}
              },
              "parametersSchema": {
                "intentName": "string",
                "params": {}
              },
              "dependencies": {
                "requiredPackages": []
              }
            },
            {
              "id": "event.open.settings.dnd",
              "type": "event",
              "call": "clickToDeeplink",
              "description": "打开系统设置中的情景模式，用户可以打开免打扰或专注模式",
              "targetApp": "设置",
              "targetScene": "Settings",
              "argsTemplate": {
                "intentName": "Settings",
                "bundleName": "com.huawei.hmos.settings",
                "abilityName": "com.huawei.hmos.settings.MainAbility",
                "uri": "intelligent_scene_entry"
              },
              "parametersSchema": {
                "intentName": "string",
                "bundleName": "string",
                "abilityName": "string",
                "uri": "string"
              },
              "dependencies": {
                "requiredPackages": []
              }
            },
            {
              "id": "event.open.settings.bluetooth",
              "type": "event",
              "call": "clickToDeeplink",
              "description": "打开系统设置中的蓝牙设置页",
              "targetApp": "设置",
              "targetScene": "Settings",
              "argsTemplate": {
                "intentName": "Settings",
                "bundleName": "com.huawei.hmos.settings",
                "abilityName": "com.huawei.hmos.settings.MainAbility",
                "uri": "bluetooth_entry"
              },
              "parametersSchema": {
                "intentName": "string",
                "bundleName": "string",
                "abilityName": "string",
                "uri": "string"
              },
              "dependencies": {
                "requiredPackages": []
              }
            },
            {
              "id": "event.open.settings.battery",
              "type": "event",
              "call": "clickToDeeplink",
              "description": "打开系统设置中的电池页",
              "targetApp": "设置",
              "targetScene": "Settings",
              "argsTemplate": {
                "intentName": "Settings",
                "bundleName": "com.huawei.hmos.settings",
                "abilityName": "com.huawei.hmos.settings.MainAbility",
                "uri": "battery"
              },
              "parametersSchema": {
                "intentName": "string",
                "bundleName": "string",
                "abilityName": "string",
                "uri": "string"
              },
              "dependencies": {
                "requiredPackages": []
              }
            },
            {
              "id": "event.open.settings.batteryHealth",
              "type": "event",
              "call": "clickToDeeplink",
              "description": "打开系统设置中的电池健康页",
              "targetApp": "设置",
              "targetScene": "Settings",
              "argsTemplate": {
                "intentName": "Settings",
                "bundleName": "com.huawei.hmos.settings",
                "abilityName": "com.huawei.hmos.settings.MainAbility",
                "uri": "smart_charge_battery_health"
              },
              "parametersSchema": {
                "intentName": "string",
                "bundleName": "string",
                "abilityName": "string",
                "uri": "string"
              },
              "dependencies": {
                "requiredPackages": []
              }
            },
            {
              "id": "event.open.settings.parentControl",
              "type": "event",
              "call": "clickToDeeplink",
              "description": "打开系统设置中的健康使用App页面，为了设置应用使用时长",
              "targetApp": "设置",
              "targetScene": "Settings",
              "argsTemplate": {
                "intentName": "Settings",
                "bundleName": "com.huawei.hmos.settings",
                "abilityName": "com.huawei.hmos.settings.MainAbility",
                "uri": "parent_control"
              },
              "parametersSchema": {
                "intentName": "string",
                "bundleName": "string",
                "abilityName": "string",
                "uri": "string"
              },
              "dependencies": {
                "requiredPackages": []
              }
            },
            {
              "id": "event.open.settings.storage",
              "type": "event",
              "call": "clickToDeeplink",
              "description": "打开系统设置中的存储空间页",
              "targetApp": "设置",
              "targetScene": "Settings",
              "argsTemplate": {
                "intentName": "Settings",
                "bundleName": "com.huawei.hmos.settings",
                "abilityName": "com.huawei.hmos.settings.MainAbility",
                "uri": "storage_settings"
              },
              "parametersSchema": {
                "intentName": "string",
                "bundleName": "string",
                "abilityName": "string",
                "uri": "string"
              },
              "dependencies": {
                "requiredPackages": []
              }
            },
            {
              "id": "event.open.weather",
              "type": "event",
              "call": "clickToDeeplink",
              "description": "打开手机天气应用某城市页，uri为固定值勿更改",
              "targetApp": "天气",
              "targetScene": "Weather_CityCode",
              "argsTemplate": {
                "intentName": "Weather_CityCode",
                "bundleName": "",
                "abilityName": "",
                "uri": "hww://www.huawei.com/totemweather?enterType=share&cityCode="
              },
              "parametersSchema": {
                "intentName": "string",
                "bundleName": "string",
                "abilityName": "string",
                "uri": "string"
              },
              "dependencies": {
                "requiredPackages": []
              }
            },
            {
              "id": "event.open.clock.alarm",
              "type": "event",
              "call": "clickToDeeplink",
              "description": "打开闹钟应用首页",
              "targetApp": "闹钟",
              "targetScene": "Clock",
              "argsTemplate": {
                "intentName": "Clock",
                "bundleName": "com.huawei.hmos.clock",
                "abilityName": "com.huawei.hmos.clock.phone",
                "uri": ""
              },
              "parametersSchema": {
                "intentName": "string",
                "bundleName": "string",
                "abilityName": "string",
                "uri": "string"
              },
              "dependencies": {
                "requiredPackages": []
              }
            },
            {
              "id": "event.open.music.daily",
              "type": "event",
              "call": "clickToDeeplink",
              "description": "打开音乐app的每日30首歌单，uri为固定值勿更改",
              "targetApp": "音乐",
              "targetScene": "Music",
              "argsTemplate": {
                "intentName": "Music",
                "bundleName": "",
                "abilityName": "",
                "uri": "hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4"
              },
              "parametersSchema": {
                "intentName": "string",
                "bundleName": "string",
                "abilityName": "string",
                "uri": "string"
              },
              "dependencies": {
                "requiredPackages": []
              }
            },
            {
              "id": "event.open.music.favorite",
              "type": "event",
              "call": "clickToDeeplink",
              "description": "打开音乐app的收藏歌单/心动歌单，uri为固定值勿更改",
              "targetApp": "音乐",
              "targetScene": "Music",
              "argsTemplate": {
                "intentName": "Music",
                "bundleName": "",
                "abilityName": "",
                "uri": "hwmusic://com.huawei.hmsapp.music/showMusicList?code=favoriteSong&type=412"
              },
              "parametersSchema": {
                "intentName": "string",
                "bundleName": "string",
                "abilityName": "string",
                "uri": "string"
              },
              "dependencies": {
                "requiredPackages": []
              }
            },
            {
              "id": "event.open.health.sport",
              "type": "event",
              "call": "clickToDeeplink",
              "description": "打开运动健康应用的锻炼Tab页",
              "targetApp": "运动健康",
              "targetScene": "Health",
              "argsTemplate": {
                "intentName": "Health",
                "bundleName": "",
                "abilityName": "",
                "uri": "huaweischeme://healthapp/home/sport?sportType=2"
              },
              "parametersSchema": {
                "intentName": "string",
                "bundleName": "string",
                "abilityName": "string",
                "uri": "string"
              },
              "dependencies": {
                "requiredPackages": [
                  {
                    "packageName": "com.huawei.hmos.health.core"
                  }
                ]
              }
            },
            {
              "id": "event.open.health.sleep",
              "type": "event",
              "call": "clickToDeeplink",
              "description": "打开运动健康应用的睡眠详情页",
              "targetApp": "运动健康",
              "targetScene": "Health",
              "argsTemplate": {
                "intentName": "Health",
                "bundleName": "",
                "abilityName": "",
                "uri": "huaweischeme://healthapp/router/sleepDetail"
              },
              "parametersSchema": {
                "intentName": "string",
                "bundleName": "string",
                "abilityName": "string",
                "uri": "string"
              },
              "dependencies": {
                "requiredPackages": [
                  {
                    "packageName": "com.huawei.hmos.health.core"
                  }
                ]
              }
            },
            {
              "id": "event.viewCalendarEvent",
              "type": "event",
              "call": "clickToIntent",
              "description": "点击日程卡片 or 日程按钮，跳转到日程 App 查看该日程的详情",
              "targetScene": "ViewCalendarEvent",
              "argsTemplate": {
                "intentName": "ViewCalendarEvent",
                "params": {
                  "entityId": {
                    "path": "entityId"
                  }
                }
              },
              "parametersSchema": {
                "intentName": "string",
                "params": {
                  "entityId": "string"
                }
              },
              "dependencies": {
                "requiredPackages": []
              }
            },
            {
              "id": "event.startNavigate",
              "type": "event",
              "call": "clickToIntent",
              "description": "点击导航按钮，跳转到地图应用进行导航。大模型需根据用户说的目的地选择location的值，只支持回家和去公司的导航",
              "targetScene": "StartNavigate",
              "argsTemplate": {
                "intentName": "StartNavigate",
                "params": {
                  "dstLocation": {
                    "location": "",
                    "latitude": "",
                    "longitude": ""
                  }
                }
              },
              "parametersSchema": {
                "intentName": "string",
                "params": {
                  "dstLocation": {
                    "location": "string",
                    "latitude": "string",
                    "longitude": "string"
                  }
                }
              },
              "dependencies": {
                "requiredPackages": []
              }
            },
            {
              "id": "event.setPowerSavingMode",
              "type": "event",
              "call": "clickToIntent",
              "description": "点击一键开启/关闭省电模式。大模型根据用户表达确定是开启还是关闭，然后传对应的switchFlag值",
              "targetScene": "SetSettingSwitch",
              "argsTemplate": {
                "intentName": "SetSettingSwitch",
                "params": {
                  "appBundleName": "com.huawei.hmos.settings",
                  "itemName": "battery_saving_mode",
                  "switchFlag": 0
                }
              },
              "parametersSchema": {
                "intentName": "string",
                "params": {
                  "appBundleName": "string",
                  "itemName": "string",
                  "switchFlag": "number"
                }
              },
              "dependencies": {
                "requiredPackages": []
              }
            }
          ],
          "assetCandidates": [
            {
              "id": "asset.air_fill",
              "type": "asset",
              "src": "resources/base/media/air_fill.svg",
              "description": "空调/空气循环实心图标，黑色，图形呈矩形风口加出风箭头造型，适用场景：空调控制面板、智能家居空气管理",
              "sceneTags": [
                "air",
                "home"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.air_open_fill",
              "type": "asset",
              "src": "resources/base/media/air_open_fill.svg",
              "description": "空调开启/新风实心图标，黑色，图形为开启状态的风口造型，适用场景：空调开启状态展示、新风系统控制",
              "sceneTags": [
                "air",
                "home"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.airplane_departure",
              "type": "asset",
              "src": "resources/base/media/airplane_departure.svg",
              "description": "飞机起飞图标，黑色，图形为飞机从跑道起飞的侧视图，适用场景：出行计划、航班出发信息、旅行日程",
              "sceneTags": [
                "travel",
                "flight"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.airplane_fill_1",
              "type": "asset",
              "src": "resources/base/media/airplane_fill_1.svg",
              "description": "飞机实心图标，黑色，图形为正面朝上的飞机俯视轮廓，适用场景：旅行场景、航班信息展示、出行卡片",
              "sceneTags": [
                "travel",
                "flight"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.alarm_fill_1",
              "type": "asset",
              "src": "resources/base/media/alarm_fill_1.svg",
              "description": "闹钟实心图标，黑白双色，图形为带铃铛的圆形表盘，适用场景：闹钟设置、定时提醒、日程提醒",
              "sceneTags": [
                "alarm",
                "reminder"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.backward_fill",
              "type": "asset",
              "src": "resources/base/media/backward_fill.svg",
              "description": "快退/后退实心图标，黑色，图形为两个向左的三角箭头，适用场景：音乐播放器快退控制、视频回退",
              "sceneTags": [
                "media",
                "control"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.battery_leaf_fill",
              "type": "asset",
              "src": "resources/base/media/battery_leaf_fill.svg",
              "description": "电池与绿叶组合实心图标，黑色，图形为电池加叶片造型，适用场景：节能模式、绿色用电、环保出行",
              "sceneTags": [
                "battery",
                "power"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.bell_fill",
              "type": "asset",
              "src": "resources/base/media/bell_fill.svg",
              "description": "铃铛实心图标，黑色，图形为经典吊铃造型，适用场景：通知提醒、消息提示、闹铃开启状态",
              "sceneTags": [
                "notification",
                "alarm"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.bell_slash_fill",
              "type": "asset",
              "src": "resources/base/media/bell_slash_fill.svg",
              "description": "铃铛加斜杠实心图标，黑白双色，图形为铃铛上叠加删除线，适用场景：静音模式、关闭通知、勿扰设置",
              "sceneTags": [
                "notification",
                "silent"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.bolt_fill",
              "type": "asset",
              "src": "resources/base/media/bolt_fill.svg",
              "description": "闪电实心图标，黑色，图形为竖向闪电符号，适用场景：充电状态、快充指示、用电量展示",
              "sceneTags": [
                "battery",
                "power"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.bus_fill",
              "type": "asset",
              "src": "resources/base/media/bus_fill.svg",
              "description": "公交车实心图标，黑色，图形为正面视角公共汽车轮廓，适用场景：公共交通出行、路线导航、公交到站提醒",
              "sceneTags": [
                "traffic",
                "bus"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.calendar_fill",
              "type": "asset",
              "src": "resources/base/media/calendar_fill.svg",
              "description": "日历实心图标，黑色，图形为带格线的日历本造型，适用场景：日程管理、日历事件查看、当日安排",
              "sceneTags": [
                "calendar",
                "schedule"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.checkmark_calendar_fill",
              "type": "asset",
              "src": "resources/base/media/checkmark_calendar_fill.svg",
              "description": "带对勾的日历实心图标，黑白双色，图形为日历上叠加对勾，适用场景：已完成日程、日程确认、任务打卡",
              "sceneTags": [
                "calendar",
                "task"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.clean_fill",
              "type": "asset",
              "src": "resources/base/media/clean_fill.svg",
              "description": "清洁实心图标，黑色，图形为清洁工具或净化造型，适用场景：清洁模式、空气净化、家居清洁提醒",
              "sceneTags": [
                "clean",
                "home"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.clock",
              "type": "asset",
              "src": "resources/base/media/clock.svg",
              "description": "时钟线框图标，黑色，图形为圆形表盘加指针的线性轮廓，适用场景：时间显示、定时功能、倒计时",
              "sceneTags": [
                "time",
                "clock"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.clock_fill",
              "type": "asset",
              "src": "resources/base/media/clock_fill.svg",
              "description": "时钟实心图标，黑白双色，图形为圆形实心表盘加白色指针，适用场景：时间显示、闹钟设置、定时器",
              "sceneTags": [
                "time",
                "clock"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.cold",
              "type": "asset",
              "src": "resources/base/media/cold.svg",
              "description": "寒冷/雪花图标，黑色，图形为六角雪花晶体造型，适用场景：制冷模式、低温天气展示、空调冷风设置",
              "sceneTags": [
                "weather",
                "cold"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.cloudy",
              "type": "asset",
              "src": "resources/base/media/cloudy.png",
              "description": "云朵组合，彩色图标，适用场景：天气、出行",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.cloudy_turning_sunny",
              "type": "asset",
              "src": "resources/base/media/cloudy_turning_sunny.png",
              "description": "小云朵和太阳组合，彩色图标，适用场景：天气、出行",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.courier_box",
              "type": "asset",
              "src": "resources/base/media/courier_box.png",
              "description": "快递箱子，彩色图标，适用场景：物流信息、取件提醒",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.drop_1",
              "type": "asset",
              "src": "resources/base/media/drop_1.svg",
              "description": "水滴图标，黑色，图形为圆润水滴轮廓，适用场景：湿度数据展示、饮水提醒、天气降雨信息",
              "sceneTags": [
                "weather",
                "water"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.earphone_case_16644",
              "type": "asset",
              "src": "resources/base/media/earphone_case_16644.svg",
              "description": "耳机收纳盒实心图标，黑色，图形为无线耳机充电盒造型，适用场景：蓝牙耳机设备连接、音频设备管理",
              "sceneTags": [
                "device",
                "audio"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.externaldrive_fill",
              "type": "asset",
              "src": "resources/base/media/externaldrive_fill.svg",
              "description": "外置存储设备实心图标，黑色，图形为矩形硬盘盒造型，适用场景：本地存储管理、数据备份、文件传输",
              "sceneTags": [
                "storage",
                "device"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.face",
              "type": "asset",
              "src": "resources/base/media/face.svg",
              "description": "人脸图标，黑色，图形为简洁人脸轮廓，适用场景：人脸识别解锁、用户头像占位、个人身份展示",
              "sceneTags": [
                "identity",
                "person"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.fast_forward",
              "type": "asset",
              "src": "resources/base/media/fast_forward.svg",
              "description": "快进图标，黑色，图形为两个向右的三角箭头，适用场景：音乐播放器快进控制、视频快进",
              "sceneTags": [
                "media",
                "control"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.figure_pool_swim",
              "type": "asset",
              "src": "resources/base/media/figure_pool_swim.svg",
              "description": "游泳人物图标，黑色，图形为人体游泳动作侧视轮廓，适用场景：运动记录、游泳锻炼追踪、健康运动卡片",
              "sceneTags": [
                "health",
                "sport"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.figure_run",
              "type": "asset",
              "src": "resources/base/media/figure_run.svg",
              "description": "跑步人物图标，黑色，图形为人体奔跑动作侧视轮廓，适用场景：运动记录、跑步锻炼追踪、步数统计",
              "sceneTags": [
                "health",
                "sport"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.flame_fill",
              "type": "asset",
              "src": "resources/base/media/flame_fill.svg",
              "description": "火焰实心图标，黑色，图形为向上燃烧的火焰造型，适用场景：热量消耗展示、加热功能、高温天气提示",
              "sceneTags": [
                "health",
                "heat"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.heart_fill",
              "type": "asset",
              "src": "resources/base/media/heart_fill.svg",
              "description": "心形实心图标，黑色，图形为标准爱心轮廓，适用场景：健康数据、心率监测展示、收藏/喜欢功能",
              "sceneTags": [
                "health",
                "heart"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.heat_generation",
              "type": "asset",
              "src": "resources/base/media/heat_generation.svg",
              "description": "发热/暖气图标，黑色，图形为散热或暖气片波浪造型，适用场景：暖气控制、制热模式、冬季取暖设置",
              "sceneTags": [
                "heat",
                "home"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.house_fill",
              "type": "asset",
              "src": "resources/base/media/house_fill.svg",
              "description": "房屋实心图标，黑白双色，图形为三角屋顶加矩形门洞的家形造型，适用场景：首页导航、智能家居入口、回家提醒",
              "sceneTags": [
                "home"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.hourglass_fill",
              "type": "asset",
              "src": "resources/base/media/hourglass_fill.svg",
              "description": "沙漏和齿轮组合图标，图形为沙漏线性右下角齿轮组合的造型，适用场景：应用时长",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.id_fill",
              "type": "asset",
              "src": "resources/base/media/id_fill.svg",
              "description": "身份证/工牌实心图标，黑色，图形为矩形证件卡片造型，适用场景：身份识别、工牌/证件展示、当下日程身份信息",
              "sceneTags": [
                "identity"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.kidswatch_fill",
              "type": "asset",
              "src": "resources/base/media/kidswatch_fill.svg",
              "description": "儿童手表实心图标，黑色，图形为圆形表盘加表带的手表造型，适用场景：儿童设备管理、家长控制、儿童安全",
              "sceneTags": [
                "device",
                "watch"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.l_circle_fill",
              "type": "asset",
              "src": "resources/base/media/l_circle_fill.svg",
              "description": "字母L圆形实心图标，黑色，图形为圆形背景内白色L字母，适用场景：标签分类标识、左侧导航标记",
              "sceneTags": [
                "label"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.lamp_ceiling",
              "type": "asset",
              "src": "resources/base/media/lamp_ceiling.svg",
              "description": "吸顶灯图标（关灯状态），黑色，图形为圆形灯盘加固定架造型，适用场景：智能照明控制、灯光管理、家居灯光",
              "sceneTags": [
                "home",
                "light"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.lamp_ceiling_light",
              "type": "asset",
              "src": "resources/base/media/lamp_ceiling_light.svg",
              "description": "吸顶灯亮起图标（开灯状态），黑色，图形为圆形灯盘加射线光芒造型，适用场景：灯光开启状态展示、智能照明控制",
              "sceneTags": [
                "home",
                "light"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.local_fill",
              "type": "asset",
              "src": "resources/base/media/local_fill.svg",
              "description": "本地/定位实心图标，黑色，图形为圆形加中心圆点的定位标记，适用场景：本地内容、当前位置标注、定位功能",
              "sceneTags": [
                "location"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.location_north_up_right_fill",
              "type": "asset",
              "src": "resources/base/media/location_north_up_right_fill.svg",
              "description": "方向导航实心图标，黑色，图形为指向右上方的导航箭头，适用场景：地图导航、方向指引、路线规划",
              "sceneTags": [
                "location",
                "navigation"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.moon_circle_fill",
              "type": "asset",
              "src": "resources/base/media/moon_circle_fill.svg",
              "description": "月亮圆形实心图标，黑白双色，图形为圆形背景内白色月牙，适用场景：夜间模式、睡眠追踪、勿扰模式",
              "sceneTags": [
                "sleep",
                "night"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.moon_z_fill_1",
              "type": "asset",
              "src": "resources/base/media/moon_z_fill_1.svg",
              "description": "月亮加Z睡眠实心图标，黑色，图形为月牙旁附带字母Z表示入睡，适用场景：睡眠模式开启、休息提醒、晚安场景",
              "sceneTags": [
                "sleep",
                "night"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.music_fill",
              "type": "asset",
              "src": "resources/base/media/music_fill.svg",
              "description": "音乐音符实心图标，黑色，图形为双音符连接造型，适用场景：音乐播放卡片、音频功能入口、歌单展示",
              "sceneTags": [
                "music",
                "media"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.pause_fill",
              "type": "asset",
              "src": "resources/base/media/pause_fill.svg",
              "description": "暂停实心图标，黑色，图形为两条竖向平行矩形，适用场景：音乐/视频播放暂停控制",
              "sceneTags": [
                "media",
                "control"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.person_3_fill",
              "type": "asset",
              "src": "resources/base/media/person_3_fill.svg",
              "description": "三人组实心图标，黑色，图形为三个人形轮廓并排排列，适用场景：群组联系人、团队成员展示、家庭成员列表",
              "sceneTags": [
                "person",
                "group"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.phone_fill",
              "type": "asset",
              "src": "resources/base/media/phone_fill.svg",
              "description": "电话实心图标，黑色，图形为经典听筒造型，适用场景：拨打电话、通话功能入口",
              "sceneTags": [
                "phone",
                "call"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.phone_fill_1",
              "type": "asset",
              "src": "resources/base/media/phone_fill_1.svg",
              "description": "电话实心图标（变体），黑色，图形为听筒加信号波形，适用场景：来电接听、通话状态展示",
              "sceneTags": [
                "phone",
                "call"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.play_fill",
              "type": "asset",
              "src": "resources/base/media/play_fill.svg",
              "description": "播放实心图标，黑色，图形为向右的实心三角形，适用场景：音乐/视频播放控制、媒体播放器",
              "sceneTags": [
                "media",
                "control"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.partly_cloudy",
              "type": "asset",
              "src": "resources/base/media/partly_cloudy.png",
              "description": "云朵在前、太阳在后的组合，彩色图标，适用场景：天气、出行",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.qrcode",
              "type": "asset",
              "src": "resources/base/media/qrcode.svg",
              "description": "二维码图标，黑色，图形为标准方形二维码点阵图案，适用场景：扫码功能、快速连接设备、信息分享",
              "sceneTags": [
                "qrcode",
                "share"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.rain",
              "type": "asset",
              "src": "resources/base/media/rain.png",
              "description": "云朵和雨滴组合，彩色图标，适用场景：天气、出行",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.r_circle_fill",
              "type": "asset",
              "src": "resources/base/media/r_circle_fill.svg",
              "description": "字母R圆形实心图标，黑色，图形为圆形背景内白色R字母，适用场景：标签分类标识、录制状态标记",
              "sceneTags": [
                "label"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.snow",
              "type": "asset",
              "src": "resources/base/media/snow.png",
              "description": "雪花，彩色图标，适用场景：天气、出行",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.stopwatch_fill",
              "type": "asset",
              "src": "resources/base/media/stopwatch_fill.svg",
              "description": "秒表实心图标，黑白双色，图形为带按钮的圆形秒表造型，适用场景：计时功能、运动计时、倒计时",
              "sceneTags": [
                "time",
                "sport"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.sunny",
              "type": "asset",
              "src": "resources/base/media/sunny.png",
              "description": "太阳，彩色图标，适用场景：天气、出行",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.sun_max",
              "type": "asset",
              "src": "resources/base/media/sun_max.svg",
              "description": "太阳最大亮度图标，黑色，图形为圆形太阳加多条粗放射线，适用场景：天气晴朗展示、屏幕亮度最大值",
              "sceneTags": [
                "weather",
                "sun"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.sun_min",
              "type": "asset",
              "src": "resources/base/media/sun_min.svg",
              "description": "太阳最小亮度图标，黑色，图形为圆形太阳加短细放射线，适用场景：低亮度调节、柔和光线、日出/日落场景",
              "sceneTags": [
                "weather",
                "sun"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.thermometer_snowflake",
              "type": "asset",
              "src": "resources/base/media/thermometer_snowflake.svg",
              "description": "温度计/雪花组合图标，黑色，图形为温度计右侧叠加雪花造型，适用场景：寒冷预警、体感指数",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.thermometer_sun_fill",
              "type": "asset",
              "src": "resources/base/media/thermometer_sun_fill.svg",
              "description": "温度计/太阳组合图标，黑色，图形为温度计右侧叠加太阳造型，适用场景：高温预警、体感指数",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.thunder",
              "type": "asset",
              "src": "resources/base/media/thunder.png",
              "description": "云朵和闪电组合，彩色图标，适用场景：天气、出行",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.thunder_storm",
              "type": "asset",
              "src": "resources/base/media/thunder_storm.svg",
              "description": "下雨和闪电造型组合图标，图形为下雨中带有闪电的造型，适用场景：雷暴预警",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.thunderstorm",
              "type": "asset",
              "src": "resources/base/media/thunderstorm.png",
              "description": "云朵、闪电和雨滴组合，彩色图标，适用场景：天气、出行",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.tornado",
              "type": "asset",
              "src": "resources/base/media/tornado.png",
              "description": "龙卷风，彩色图标，适用场景：天气、出行",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.tram_fill",
              "type": "asset",
              "src": "resources/base/media/tram_fill.svg",
              "description": "有轨电车实心图标，黑色，图形为带导线的有轨电车侧视轮廓，适用场景：城市公共交通、地铁/轻轨出行导航",
              "sceneTags": [
                "traffic",
                "tram"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.typhoon_fill",
              "type": "asset",
              "src": "resources/base/media/typhoon_fill.svg",
              "description": "台风黑色图标，图形为台风漩涡造型，适用场景：台风预警、台风路径",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.z_alarm_fill",
              "type": "asset",
              "src": "resources/base/media/z_alarm_fill.svg",
              "description": "带Z的闹钟贪睡实心图标，黑色，图形为闹钟旁附带字母Z表示贪睡，适用场景：闹钟贪睡功能、延迟提醒、睡眠场景",
              "sceneTags": [
                "alarm",
                "sleep"
              ],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_id",
              "type": "asset",
              "src": "resources/base/media/icon_id.png",
              "description": "工牌/ID图标，适用场景：当下日程",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_meeting",
              "type": "asset",
              "src": "resources/base/media/icon_meeting.png",
              "description": "会议图标，适用场景：当下日程",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_time",
              "type": "asset",
              "src": "resources/base/media/icon_time.png",
              "description": "时间图标，适用场景：当下日程",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_watermark",
              "type": "asset",
              "src": "resources/base/media/icon_watermark.png",
              "description": "水印图标，适用场景：当下日程",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_allergy",
              "type": "asset",
              "src": "resources/base/media/icon_allergy.png",
              "description": "过敏源图标，适用场景：亲人关怀",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_call",
              "type": "asset",
              "src": "resources/base/media/icon_call.png",
              "description": "电话图标，适用场景：亲人关怀",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_high_temperature",
              "type": "asset",
              "src": "resources/base/media/icon_high_temperature.png",
              "description": "高温/温度计图标，适用场景：亲人关怀",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_weather1",
              "type": "asset",
              "src": "resources/base/media/icon_weather1.png",
              "description": "天气/雨伞图标，适用场景：亲人关怀",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_tiktok",
              "type": "asset",
              "src": "resources/base/media/icon_tiktok.png",
              "description": "抖音图标，适用场景：防沉迷",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_timing",
              "type": "asset",
              "src": "resources/base/media/icon_timing.png",
              "description": "计时图标，适用场景：防沉迷",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_charge",
              "type": "asset",
              "src": "resources/base/media/icon_charge.png",
              "description": "充电/闪电图标，适用场景：低电模式",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_clear",
              "type": "asset",
              "src": "resources/base/media/icon_clear.png",
              "description": "清除图标，适用场景：清理无忧",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_earphone",
              "type": "asset",
              "src": "resources/base/media/icon_earphone.png",
              "description": "耳机图标，适用场景：戴耳机播控",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_phone",
              "type": "asset",
              "src": "resources/base/media/icon_phone.png",
              "description": "手机图标，适用场景：专注模式",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_car",
              "type": "asset",
              "src": "resources/base/media/icon_car.png",
              "description": "汽车/打车图标，适用场景：雨天打车",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_time1",
              "type": "asset",
              "src": "resources/base/media/icon_time1.png",
              "description": "时间图标，适用场景：雨天打车",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_weathe2",
              "type": "asset",
              "src": "resources/base/media/icon_weathe2.png",
              "description": "天气图标，适用场景：雨天打车",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_alarm_clock",
              "type": "asset",
              "src": "resources/base/media/icon_alarm_clock.png",
              "description": "闹钟图标，适用场景：当下日程",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_focus",
              "type": "asset",
              "src": "resources/base/media/icon_focus.png",
              "description": "专注图标，适用场景：专注模式",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_schedule",
              "type": "asset",
              "src": "resources/base/media/icon_schedule.png",
              "description": "日程图标，适用场景：当下日程",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_electricity",
              "type": "asset",
              "src": "resources/base/media/icon_electricity.png",
              "description": "电池图标，适用场景：低电模式",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_save_power",
              "type": "asset",
              "src": "resources/base/media/icon_save_power.png",
              "description": "省电图标，适用场景：低电模式",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_alarm_clock1",
              "type": "asset",
              "src": "resources/base/media/icon_alarm_clock1.png",
              "description": "闹钟图标，适用场景：睡眠监督",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_remind",
              "type": "asset",
              "src": "resources/base/media/icon_remind.png",
              "description": "提醒图标，适用场景：睡眠监督",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_sleep",
              "type": "asset",
              "src": "resources/base/media/icon_sleep.png",
              "description": "睡眠图标，适用场景：睡眠监督",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_run",
              "type": "asset",
              "src": "resources/base/media/icon_run.png",
              "description": "运动/跑步图标，适用场景：当下日程",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_schedule2",
              "type": "asset",
              "src": "resources/base/media/icon_schedule2.png",
              "description": "日程图标，适用场景：当下日程",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_left",
              "type": "asset",
              "src": "resources/base/media/icon_left.png",
              "description": "上一首图标，适用场景：戴耳机播控",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_like",
              "type": "asset",
              "src": "resources/base/media/icon_like.png",
              "description": "收藏/心形图标，适用场景：戴耳机播控",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_music",
              "type": "asset",
              "src": "resources/base/media/icon_music.png",
              "description": "音乐图标，适用场景：戴耳机播控",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            },
            {
              "id": "asset.icon_right",
              "type": "asset",
              "src": "resources/base/media/icon_right.png",
              "description": "下一首图标，适用场景：戴耳机播控",
              "sceneTags": [],
              "minXiaoyiVersion": "1.0.0"
            }
          ],
          "unavailableCapabilities": []
        },
        "status": "success",
        "errorCode": "",
        "error": {}
      }
    ]
  }
}
```
