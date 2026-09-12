# 2x2 Few-shot

示例中的图标位置不可迁移到普通内容行：内容区仅允许环中心或 S4 双对象分区主视觉图标，其他内容不生成 Image，L/R/盒 Text 标识保留。S4 包括同类双对象，如两个城市天气；有合法素材时每个天气区各放 1 个主视觉图标（可复用 src，分别计数），不是给温度、日期等文字逐行配图，按钮及标题不再配图标。用户明确指定图标的例外仍按主提示词执行。

示例中的数据路径、事件和素材候选取自能力清单；真实输出只能使用当前 TaskSpec 实际提供的 path、icon 和 onClick。示例用于参考布局，背景选择、业务映射及内容配色统一遵循 PROMPT.md 第十二节；用户明确配色要求优先，未指定时不得沿用旧色值或自由取色。融球示例仅在本次尺寸、业务、密度和运行时条件均满足时使用，否则按主业务切换到对应浅色纯色及配套内容色。

## 示例一（2x2-V01）：马拉松倒计时（S1 单信息·融球暖橙）
### user
```json
{"userQuery":"使用2*2规格，做个运动会倒数日卡片。展示距离运动会的倒计时天数","size":"2x2","eventCandidates":[],"dataModelSchema":{"data":{"countdown":{"countdownDays":{"type":"integer","description":"距离目标日期的自然日天数","sampleValue":32}}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":20,"clip":true,"justifyContent":"start","alignItems":"center","itemMargin":8,"design":"fusion-ball-sport-orange"},["title_area","value_group"]]
["title_area","Row",{"width":136,"height":20,"justifyContent":"center","alignItems":"center","flexShrink":0},["title_text"]]
["title_text","Text",{"content":"马拉松倒计时","width":112,"fontSize":12,"fontWeight":400,"fontColor":"#99FFFFFF","textAlign":"center","maxLines":1}]
["value_group","Column",{"width":136,"justifyContent":"center","alignItems":"center","itemMargin":2,"flexShrink":1},["value_num","value_unit"]]
["value_num","Text",{"content":{"path":"/data/countdown/countdownDays"},"fontSize":38,"fontWeight":700,"fontColor":"#FFFFFFFF","maxLines":1}]
["value_unit","Text",{"content":"天","fontSize":12,"fontWeight":500,"fontColor":"#FFFFFFFF","textAlign":"center","maxLines":1}]
["/data/countdown/countdownDays",32]
```

## 示例二（2x2-V02）：FreeBuds 状态 + 蓝牙设置（S2 状态亚型·青色纯色）
### user
```json
{"userQuery":"实时展示华为耳机连接状态、左右耳及充电盒电量，并提供蓝牙设置入口","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"bluetooth_entry"}}],"dataModelSchema":{"data":{"earphone":{"isConnected":{"type":"boolean","description":"当前是否处于耳机连接活跃状态","sampleValue":true},"earphoneName":{"type":"string","description":"耳机广播名称","sampleValue":"FreeBuds Pro 3"},"leftBatteryLevel":{"type":"integer","description":"左耳电量百分比0到100","sampleValue":47},"rightBatteryLevel":{"type":"integer","description":"右耳电量百分比0到100","sampleValue":62},"batteryLevel":{"type":"integer","description":"充电盒电量百分比0到100","sampleValue":95}}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":20,"clip":true,"justifyContent":"start","alignItems":"center","itemMargin":4,"backgroundColor":"#FFE6FDFF"},["title_area","content_area","action_area"]]
["title_area","CardHeader",{"title":{"path":"/data/earphone/earphoneName"},"fontColor":"#991F8F99"}]
["content_area","Column",{"width":136,"layoutWeight":1,"justifyContent":"start","alignItems":"start","itemMargin":4,"flexShrink":1},["status_text","battery_row"]]
["status_text","Text",{"content":"{{ ${/data/earphone/isConnected} ? '已连接' : '未连接' }}","width":136,"height":28,"fontSize":20,"fontWeight":700,"fontColor":"#FF1F8F99","maxLines":1}]
["battery_row","Row",{"width":136,"justifyContent":"start","alignItems":"center","itemMargin":8},["left_item","right_item","case_item"]]
["left_item","Row",{"width":40,"justifyContent":"start","alignItems":"center","itemMargin":2},["left_badge","left_num","left_unit"]]
["left_badge","Text",{"content":"L","width":10.5,"height":10.5,"borderRadius":5.25,"backgroundColor":"#1A1F8F99","fontSize":10,"fontWeight":500,"fontColor":"#991F8F99","textAlign":"center","maxLines":1}]
["left_num","Text",{"content":{"path":"/data/earphone/leftBatteryLevel"},"fontSize":10,"fontWeight":500,"fontColor":"#991F8F99","maxLines":1}]
["left_unit","Text",{"content":"%","fontSize":10,"fontWeight":500,"fontColor":"#991F8F99","maxLines":1}]
["right_item","Row",{"width":40,"justifyContent":"start","alignItems":"center","itemMargin":2},["right_badge","right_num","right_unit"]]
["right_badge","Text",{"content":"R","width":10.5,"height":10.5,"borderRadius":5.25,"backgroundColor":"#1A1F8F99","fontSize":10,"fontWeight":500,"fontColor":"#991F8F99","textAlign":"center","maxLines":1}]
["right_num","Text",{"content":{"path":"/data/earphone/rightBatteryLevel"},"fontSize":10,"fontWeight":500,"fontColor":"#991F8F99","maxLines":1}]
["right_unit","Text",{"content":"%","fontSize":10,"fontWeight":500,"fontColor":"#991F8F99","maxLines":1}]
["case_item","Row",{"width":40,"justifyContent":"start","alignItems":"center","itemMargin":2},["case_badge","case_num","case_unit"]]
["case_badge","Text",{"content":"盒","width":10.5,"height":10.5,"borderRadius":5.25,"backgroundColor":"#1A1F8F99","fontSize":10,"fontWeight":500,"fontColor":"#991F8F99","textAlign":"center","maxLines":1}]
["case_num","Text",{"content":{"path":"/data/earphone/batteryLevel"},"fontSize":10,"fontWeight":500,"fontColor":"#991F8F99","maxLines":1}]
["case_unit","Text",{"content":"%","fontSize":10,"fontWeight":500,"fontColor":"#991F8F99","maxLines":1}]
["action_area","Column",{"width":136,"flexShrink":0},["cta"]]
["cta","ActionUnit",{"state":"capsule","label":"蓝牙设置","actionSurface":"#331F8F99","actionInk":"#FF1F8F99","fontSize":14,"fontWeight":400,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"bluetooth_entry"}}],"flexShrink":0}]
["/data/earphone/isConnected",true]
["/data/earphone/earphoneName","FreeBuds Pro 3"]
["/data/earphone/leftBatteryLevel",47]
["/data/earphone/rightBatteryLevel",62]
["/data/earphone/batteryLevel",95]
```

## 示例三（2x2-V03）：Free Clip 2 歌单（S3 单信息+双按钮·青色纯色）
### user
```json
{"userQuery":"展示耳机名称与左右耳电量，同时提供每日歌单和收藏歌单两个入口。","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4"}},{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=favoriteSong&type=412"}}],"dataModelSchema":{"data":{"earphone":{"earphoneName":{"type":"string","description":"耳机广播名称","sampleValue":"Free Clip 2"},"leftBatteryLevel":{"type":"integer","description":"左耳电量百分比","sampleValue":47},"rightBatteryLevel":{"type":"integer","description":"右耳电量百分比","sampleValue":95}}}},"assetCandidates":[{"src":"resources/base/media/music_fill.svg","description":"每日歌单音乐图标"},{"src":"resources/base/media/heart_fill.svg","description":"收藏歌单心形图标"}]}
```
### assistant
```genui
["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":20,"clip":true,"justifyContent":"spaceBetween","alignItems":"center","itemMargin":8,"backgroundColor":"#FFE6FDFF"},["header_area","action_area"]]
["header_area","Column",{"width":136,"justifyContent":"start","alignItems":"start","itemMargin":6,"padding":{"bottom":10},"flexShrink":1},["device_name","battery_row"]]
["device_name","Text",{"content":{"path":"/data/earphone/earphoneName"},"width":136,"fontSize":16,"fontWeight":700,"fontColor":"#FF1F8F99","maxLines":1}]
["battery_row","Row",{"justifyContent":"start","alignItems":"center","itemMargin":0},["left_item","right_item"]]
["left_item","Row",{"width":52,"justifyContent":"start","alignItems":"center","itemMargin":2},["left_badge","left_num","left_unit"]]
["left_badge","Text",{"content":"L","width":10.5,"height":10.5,"borderRadius":5.25,"backgroundColor":"#1A1F8F99","fontSize":10,"fontWeight":500,"fontColor":"#991F8F99","textAlign":"center","maxLines":1}]
["left_num","Text",{"content":{"path":"/data/earphone/leftBatteryLevel"},"fontSize":10,"fontWeight":400,"fontColor":"#991F8F99","maxLines":1}]
["left_unit","Text",{"content":"%","fontSize":10,"fontWeight":400,"fontColor":"#991F8F99","maxLines":1}]
["right_item","Row",{"width":52,"justifyContent":"start","alignItems":"center","itemMargin":2},["right_badge","right_num","right_unit"]]
["right_badge","Text",{"content":"R","width":10.5,"height":10.5,"borderRadius":5.25,"backgroundColor":"#1A1F8F99","fontSize":10,"fontWeight":500,"fontColor":"#991F8F99","textAlign":"center","maxLines":1}]
["right_num","Text",{"content":{"path":"/data/earphone/rightBatteryLevel"},"fontSize":10,"fontWeight":400,"fontColor":"#991F8F99","maxLines":1}]
["right_unit","Text",{"content":"%","fontSize":10,"fontWeight":400,"fontColor":"#991F8F99","maxLines":1}]
["action_area","Column",{"width":136,"itemMargin":8,"flexShrink":0},["cta_play","cta_fav"]]
["cta_play","ActionUnit",{"state":"capsule","label":"每日歌单","icon":"resources/base/media/music_fill.svg","actionSurface":"#331F8F99","actionInk":"#FF1F8F99","fontSize":14,"fontWeight":500,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4"}}],"flexShrink":0}]
["cta_fav","ActionUnit",{"state":"capsule","label":"收藏歌单","icon":"resources/base/media/heart_fill.svg","actionSurface":"#331F8F99","actionInk":"#FF1F8F99","fontSize":14,"fontWeight":500,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=favoriteSong&type=412"}}],"flexShrink":0}]
["/data/earphone/earphoneName","Free Clip 2"]
["/data/earphone/leftBatteryLevel",47]
["/data/earphone/rightBatteryLevel",95]
```


## 示例四（2x2-V04）：天气（S2 无动作变体·蓝色纯色）
### user
```json
{"userQuery":"创建一张包含深圳今日天气信息的小卡片，展示当前温度、天气状况、空气质量以及今日温度范围","size":"2x2","eventCandidates":[],"dataModelSchema":{"data":{"weather":{"current":{"temperatureC":{"type":"number","description":"当前摄氏温度","sampleValue":38},"condition":{"type":"string","description":"白天天气现象","sampleValue":"晴｜空气优"}},"location":{"prefectureName":{"type":"string","description":"城市名称","sampleValue":"深圳"}},"daily":[{"temperatureRangeText":{"type":"string","description":"当日温度范围文本","sampleValue":"26°C/16°C"}}]}}},"assetCandidates":[{"src":"resources/base/media/sun_max.svg","description":"单色线框太阳图标，用于晴天与强光天气提示"}]}
```
### assistant
```genui
["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":20,"clip":true,"justifyContent":"start","alignItems":"center","itemMargin":4,"backgroundColor":"#FFE5EDFE"},["title_area","content_area","bottom_area"]]
["title_area","CardHeader",{"title":{"path":"/data/weather/location/prefectureName"},"fontColor":"#991F4799","icon":"resources/base/media/sun_max.svg","fillColor":"#991F4799"}]
["content_area","Column",{"width":136,"layoutWeight":1,"justifyContent":"start","alignItems":"start","padding":{"top":4},"flexShrink":1},["value_row"]]
["value_row","Row",{"width":136,"justifyContent":"start","alignItems":"bottom","itemMargin":3},["value_num","value_unit"]]
["value_num","Text",{"content":{"path":"/data/weather/current/temperatureC"},"fontSize":38,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["value_unit","Text",{"content":"°C","fontSize":12,"fontWeight":500,"fontColor":"#FF1F4799","padding":{"bottom":5},"maxLines":1,"flexShrink":0}]
["bottom_area","Column",{"width":136,"height":40,"itemMargin":4,"justifyContent":"start","flexShrink":0},["weather_status","temp_range"]]
["weather_status","Text",{"content":{"path":"/data/weather/current/condition"},"fontSize":12,"fontWeight":400,"fontColor":"#991F4799","maxLines":1}]
["temp_range","Text",{"content":{"path":"/data/weather/daily/0/temperatureRangeText"},"fontSize":12,"fontWeight":400,"fontColor":"#991F4799","maxLines":1}]
["/data/weather/current/temperatureC",38]
["/data/weather/current/condition","晴｜空气优"]
["/data/weather/daily/0/temperatureRangeText","26°C/16°C"]
["/data/weather/location/prefectureName","深圳"]
```




## 示例五（2x2-V05）：手机+耳机电量（S4 上下双蒙版·青色纯色）
本例仅因 `phoneBattery` 与 `earphone` 是两个独立展示对象才使用 S4；单个对象的多个字段或两个动作不得仿照本例拆成两个分区。
### user
```json
{"userQuery":"使用2*2规格，同时展示手机电量和耳机盒电量及各自充电状态，点击对应区域进入电池或蓝牙设置。","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"battery"}},{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"bluetooth_entry"}}],"dataModelSchema":{"data":{"phoneBattery":{"batterySOC":{"type":"integer","description":"手机剩余电量百分比0到100","sampleValue":68},"chargingStatusDesc":{"type":"string","description":"手机当前充电状态","sampleValue":"未充电"}},"earphone":{"batteryLevel":{"type":"integer","description":"耳机盒电量百分比0到100","sampleValue":47},"chargingStatusDesc":{"type":"string","description":"耳机盒当前充电状态","sampleValue":"充电中"}}}},"assetCandidates":[{"src":"resources/base/media/phone_fill.svg","description":"本地手机图标"},{"src":"resources/base/media/earphone_case_16644.svg","description":"本地耳机盒图标"}]}
```
### assistant
```genui
["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":20,"clip":true,"justifyContent":"start","alignItems":"center","itemMargin":8,"backgroundColor":"#FFE6FDFF"},["phone_row","ear_row"]]
["phone_row","Row",{"width":136,"height":64,"padding":{"left":12,"right":12,"top":0,"bottom":0},"borderRadius":16,"backgroundColor":"#1A1F8F99","justifyContent":"start","alignItems":"center","itemMargin":8,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"battery"}}]},["phone_ring","phone_col"]]
["phone_ring","Stack",{"width":48,"height":48,"alignContent":"center","flexShrink":0},["phone_progress","phone_icon"]]
["phone_progress","Progress",{"type":"ring","width":48,"height":48,"strokeWidth":5,"value":{"path":"/data/phoneBattery/batterySOC"},"total":100,"color":"#FF1F8F99","backgroundColor":"#331F8F99"}]
["phone_icon","Image",{"src":"resources/base/media/phone_fill.svg","width":20,"height":20,"objectFit":"contain","fillColor":"#FF1F8F99","flexShrink":0}]
["phone_col","Column",{"width":52,"justifyContent":"center","alignItems":"start","itemMargin":2,"flexShrink":1},["phone_label","phone_value","phone_status"]]
["phone_label","Text",{"content":"手机电量","fontSize":12,"fontWeight":700,"fontColor":"#FF1F8F99","maxLines":1}]
["phone_value","Text",{"content":"{{ ${/data/phoneBattery/batterySOC} + '%' }}","width":52,"fontSize":14,"fontWeight":700,"fontColor":"#FF1F8F99","maxLines":1}]
["phone_status","Text",{"content":{"path":"/data/phoneBattery/chargingStatusDesc"},"width":52,"fontSize":10,"fontWeight":400,"fontColor":"#991F8F99","maxLines":1}]
["ear_row","Row",{"width":136,"height":64,"padding":{"left":12,"right":12,"top":0,"bottom":0},"borderRadius":16,"backgroundColor":"#1A1F8F99","justifyContent":"start","alignItems":"center","itemMargin":8,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"bluetooth_entry"}}]},["ear_ring","ear_col"]]
["ear_ring","Stack",{"width":48,"height":48,"alignContent":"center","flexShrink":0},["ear_progress","ear_icon"]]
["ear_progress","Progress",{"type":"ring","width":48,"height":48,"strokeWidth":5,"value":{"path":"/data/earphone/batteryLevel"},"total":100,"color":"#FF1F8F99","backgroundColor":"#331F8F99"}]
["ear_icon","Image",{"src":"resources/base/media/earphone_case_16644.svg","width":20,"height":20,"objectFit":"contain","fillColor":"#FF1F8F99","flexShrink":0}]
["ear_col","Column",{"width":52,"justifyContent":"center","alignItems":"start","itemMargin":2,"flexShrink":1},["ear_label","ear_value","ear_status"]]
["ear_label","Text",{"content":"耳机盒电量","fontSize":12,"fontWeight":700,"fontColor":"#FF1F8F99","maxLines":1}]
["ear_value","Text",{"content":"{{ ${/data/earphone/batteryLevel} + '%' }}","width":52,"fontSize":14,"fontWeight":700,"fontColor":"#FF1F8F99","maxLines":1}]
["ear_status","Text",{"content":{"path":"/data/earphone/chargingStatusDesc"},"width":52,"fontSize":10,"fontWeight":400,"fontColor":"#991F8F99","maxLines":1}]
["/data/phoneBattery/batterySOC",68]
["/data/phoneBattery/chargingStatusDesc","未充电"]
["/data/earphone/batteryLevel",47]
["/data/earphone/chargingStatusDesc","充电中"]
```

## 示例六（2x2-V06）：日程待办（S2 会议时间线亚型·黄色纯色）
### user
```json
{"userQuery":"我今天会排得很满，帮我做个日程卡片，看看下一场会叫什么、几点开始。能直接点击入会。","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"uri":"demo://replace-with-candidate-meeting"}}],"dataModelSchema":{"data":{"calendar":{"events":[{"title":{"type":"string","description":"日程标题","sampleValue":"UI需求评审会"},"dtStart":{"type":"string","description":"开始时间","sampleValue":"14:00 - 15:30"},"eventLocation":{"type":"string","description":"地点","sampleValue":"深圳市龙岗区五和大..."},"countdownDays":{"type":"integer","description":"纯数字的倒数日天数，0代表今天","sampleValue":0}}]}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":20,"clip":true,"backgroundColor":"#FFFFF3E6","justifyContent":"start","alignItems":"center","itemMargin":4},["day_area","content_area","action_area"]]
["day_area","Row",{"width":136,"height":16,"justifyContent":"start","alignItems":"center","flexShrink":0},["day_tag"]]
["day_tag","Text",{"content":"今天","fontSize":12,"fontWeight":700,"fontColor":"#FF99661F","maxLines":1,"textOverflow":"clip"}]
["content_area","Row",{"width":136,"layoutWeight":1,"padding":{"top":4},"itemMargin":8,"alignItems":"start","justifyContent":"start","flexShrink":1},["timeline","meeting_texts"]]
["timeline","Column",{"width":8,"height":44,"itemMargin":0,"alignItems":"center","flexShrink":0},["timeline_dot","timeline_line"]]
["timeline_dot","Text",{"content":"●","width":8,"height":8,"fontSize":8,"fontWeight":400,"fontColor":"#FF99661F","maxLines":1,"flexShrink":0}]
["timeline_line","Divider",{"width":1.5,"height":36,"strokeWidth":1.5,"vertical":true,"color":"#1A99661F","flexShrink":0}]
["meeting_texts","Column",{"width":"matchParent","layoutWeight":1,"itemMargin":6,"justifyContent":"start","alignItems":"start","flexShrink":1},["event_title","event_time","event_place"]]
["event_title","Text",{"content":{"path":"/data/calendar/events/0/title"},"fontSize":12,"fontWeight":700,"width":"matchParent","fontColor":"#FF99661F","maxLines":1,"textOverflow":"clip"}]
["event_time","Text",{"content":{"path":"/data/calendar/events/0/dtStart"},"fontSize":12,"fontWeight":400,"width":"matchParent","fontColor":"#9999661F","maxLines":1,"textOverflow":"clip"}]
["event_place","Text",{"content":{"path":"/data/calendar/events/0/eventLocation"},"fontSize":12,"fontWeight":400,"width":"matchParent","fontColor":"#9999661F","maxLines":1,"textOverflow":"ellipsis"}]
["action_area","Column",{"width":136,"flexShrink":0},["cta"]]
["cta","ActionUnit",{"state":"capsule","label":"加入会议","actionSurface":"#3399661F","actionInk":"#FF99661F","fontSize":14,"fontWeight":400,"onClick":[{"call":"clickToDeeplink","args":{"uri":"demo://replace-with-candidate-meeting"}}],"flexShrink":0}]
["/data/calendar/events/0/title","UI需求评审会"]
["/data/calendar/events/0/dtStart","14:00 - 15:30"]
["/data/calendar/events/0/eventLocation","深圳市龙岗区五和大..."]
```

## 示例七（2x2-V07）：今日步数（S2 数值亚型·整卡隐式入口·绿色纯色）
### user
```json
{"userQuery":"我今天活动量如何，帮我做个运动小组件，看看走了多少步和消耗多少热量，点击可以进入运动详情。","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"Health","bundleName":"","abilityName":"","uri":"huaweischeme://healthapp/home/sport?sportType=2"}}],"dataModelSchema":{"data":{"healthSport":{"dailySteps":{"type":"integer","description":"全天累计步数","sampleValue":2319},"dailyDistanceText":{"type":"string","description":"总距离文本（含单位）","sampleValue":"1.19 公里"},"dailyTotalCaloriesText":{"type":"string","description":"总消耗热量文本（含单位）","sampleValue":"59 千卡"}}}},"assetCandidates":[{"src":"resources/base/media/figure_run.svg","description":"跑步人形图标"}]}
```
### assistant
```genui
["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":20,"clip":true,"justifyContent":"start","alignItems":"center","itemMargin":4,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Health","bundleName":"","abilityName":"","uri":"huaweischeme://healthapp/home/sport?sportType=2"}}],"backgroundColor":"#FFF0FFE6"},["title_area","content_area","bottom_area"]]
["title_area","CardHeader",{"title":"今日步数","fontColor":"#9952991F","icon":"resources/base/media/figure_run.svg","fillColor":"#9952991F"}]
["content_area","Column",{"width":136,"layoutWeight":1,"justifyContent":"start","alignItems":"start","itemMargin":4,"flexShrink":1},["value_row","step_bar"]]
["value_row","Row",{"width":136,"justifyContent":"start","alignItems":"bottom","itemMargin":2},["value_num","value_unit"]]
["value_num","Text",{"content":{"path":"/data/healthSport/dailySteps"},"fontSize":30,"fontWeight":700,"fontColor":"#FF52991F","maxLines":1}]
["value_unit","Text",{"content":"步","fontSize":12,"fontWeight":500,"fontColor":"#FF52991F","padding":{"bottom":4},"maxLines":1}]
["step_bar","Progress",{"type":"linear","width":136,"height":8,"strokeWidth":8,"borderRadius":4,"value":{"path":"/data/healthSport/dailySteps"},"total":8760,"color":"#FF52991F","backgroundColor":"#3352991F"}]
["bottom_area","Column",{"width":136,"height":34,"itemMargin":2,"justifyContent":"start","flexShrink":0},["aux_1","aux_2"]]
["aux_1","Row",{"itemMargin":4,"alignItems":"center"},["aux_1_t","aux_1_v"]]
["aux_1_t","Text",{"content":"运动距离","fontSize":12,"fontWeight":400,"fontColor":"#9952991F","maxLines":1}]
["aux_1_v","Text",{"content":{"path":"/data/healthSport/dailyDistanceText"},"fontSize":12,"fontWeight":700,"fontColor":"#9952991F","maxLines":1}]
["aux_2","Row",{"itemMargin":4,"alignItems":"center"},["aux_2_t","aux_2_v"]]
["aux_2_t","Text",{"content":"消耗热量","fontSize":12,"fontWeight":400,"fontColor":"#9952991F","maxLines":1}]
["aux_2_v","Text",{"content":{"path":"/data/healthSport/dailyTotalCaloriesText"},"fontSize":12,"fontWeight":700,"fontColor":"#9952991F","maxLines":1}]
["/data/healthSport/dailySteps",2319]
["/data/healthSport/dailyDistanceText","1.19 公里"]
["/data/healthSport/dailyTotalCaloriesText","59 千卡"]
```
