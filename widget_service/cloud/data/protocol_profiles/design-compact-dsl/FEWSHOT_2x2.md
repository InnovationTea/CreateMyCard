# 2x2 Few-shot

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

## 示例二（2x2-V02）：FreeBuds 状态 + 蓝牙设置（S2 状态亚型·融球青绿）
### user
```json
{"userQuery":"实时展示华为耳机连接状态、左右耳及充电盒电量，并提供蓝牙设置入口","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"bluetooth_entry"}}],"dataModelSchema":{"data":{"earphone":{"isConnected":{"type":"boolean","description":"当前是否处于耳机连接活跃状态","sampleValue":true},"earphoneName":{"type":"string","description":"耳机广播名称","sampleValue":"FreeBuds Pro 3"},"leftBatteryLevel":{"type":"integer","description":"左耳电量百分比0到100","sampleValue":47},"rightBatteryLevel":{"type":"integer","description":"右耳电量百分比0到100","sampleValue":62},"batteryLevel":{"type":"integer","description":"充电盒电量百分比0到100","sampleValue":95}}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":20,"clip":true,"justifyContent":"start","alignItems":"center","itemMargin":4,"design":"fusion-ball-battery-teal"},["title_area","content_area","action_area"]]
["title_area","CardHeader",{"title":{"path":"/data/earphone/earphoneName"},"fontColor":"#99FFFFFF"}]
["content_area","Column",{"width":136,"layoutWeight":1,"justifyContent":"start","alignItems":"start","itemMargin":4,"flexShrink":1},["status_text","battery_row"]]
["status_text","Text",{"content":"{{ ${/data/earphone/isConnected} ? '已连接' : '未连接' }}","width":136,"height":28,"fontSize":20,"fontWeight":700,"fontColor":"#FFFFFFFF","maxLines":1}]
["battery_row","Row",{"width":136,"justifyContent":"start","alignItems":"center","itemMargin":8},["left_item","right_item","case_item"]]
["left_item","Row",{"width":40,"justifyContent":"start","alignItems":"center","itemMargin":2},["left_badge","left_num","left_unit"]]
["left_badge","Text",{"content":"L","width":10.5,"height":10.5,"borderRadius":5.25,"backgroundColor":"#1AFFFFFF","fontSize":10,"fontWeight":500,"fontColor":"#FFFFFFFF","textAlign":"center","maxLines":1}]
["left_num","Text",{"content":{"path":"/data/earphone/leftBatteryLevel"},"fontSize":10,"fontWeight":500,"fontColor":"#99FFFFFF","maxLines":1}]
["left_unit","Text",{"content":"%","fontSize":10,"fontWeight":500,"fontColor":"#99FFFFFF","maxLines":1}]
["right_item","Row",{"width":40,"justifyContent":"start","alignItems":"center","itemMargin":2},["right_badge","right_num","right_unit"]]
["right_badge","Text",{"content":"R","width":10.5,"height":10.5,"borderRadius":5.25,"backgroundColor":"#1AFFFFFF","fontSize":10,"fontWeight":500,"fontColor":"#FFFFFFFF","textAlign":"center","maxLines":1}]
["right_num","Text",{"content":{"path":"/data/earphone/rightBatteryLevel"},"fontSize":10,"fontWeight":500,"fontColor":"#99FFFFFF","maxLines":1}]
["right_unit","Text",{"content":"%","fontSize":10,"fontWeight":500,"fontColor":"#99FFFFFF","maxLines":1}]
["case_item","Row",{"width":40,"justifyContent":"start","alignItems":"center","itemMargin":2},["case_badge","case_num","case_unit"]]
["case_badge","Text",{"content":"盒","width":10.5,"height":10.5,"borderRadius":5.25,"backgroundColor":"#1AFFFFFF","fontSize":10,"fontWeight":500,"fontColor":"#FFFFFFFF","textAlign":"center","maxLines":1}]
["case_num","Text",{"content":{"path":"/data/earphone/batteryLevel"},"fontSize":10,"fontWeight":500,"fontColor":"#99FFFFFF","maxLines":1}]
["case_unit","Text",{"content":"%","fontSize":10,"fontWeight":500,"fontColor":"#99FFFFFF","maxLines":1}]
["action_area","Column",{"width":136,"flexShrink":0},["cta"]]
["cta","ActionUnit",{"state":"capsule","label":"蓝牙设置","actionSurface":"#33FFFFFF","actionInk":"#E6FFFFFF","fontSize":14,"fontWeight":400,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"bluetooth_entry"}}],"flexShrink":0}]
["/data/earphone/isConnected",true]
["/data/earphone/earphoneName","FreeBuds Pro 3"]
["/data/earphone/leftBatteryLevel",47]
["/data/earphone/rightBatteryLevel",62]
["/data/earphone/batteryLevel",95]
```

## 示例三（2x2-V03）：Free Clip 2 歌单（S3 单信息+双按钮·融球青绿）
### user
```json
{"userQuery":"展示耳机名称与左右耳电量，同时提供每日歌单和收藏歌单两个入口。","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4"}},{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=favoriteSong&type=412"}}],"dataModelSchema":{"data":{"earphone":{"earphoneName":{"type":"string","description":"耳机广播名称","sampleValue":"Free Clip 2"},"leftBatteryLevel":{"type":"integer","description":"左耳电量百分比","sampleValue":47},"rightBatteryLevel":{"type":"integer","description":"右耳电量百分比","sampleValue":95}}}},"assetCandidates":[{"src":"resources/base/media/music_fill.svg","description":"每日歌单音乐图标"},{"src":"resources/base/media/heart_fill.svg","description":"收藏歌单心形图标"}]}
```
### assistant
```genui
["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":20,"clip":true,"justifyContent":"spaceBetween","alignItems":"center","itemMargin":8,"design":"fusion-ball-battery-teal"},["header_area","action_area"]]
["header_area","Column",{"width":136,"justifyContent":"start","alignItems":"start","itemMargin":6,"padding":{"bottom":10},"flexShrink":1},["device_name","battery_row"]]
["device_name","Text",{"content":{"path":"/data/earphone/earphoneName"},"width":136,"fontSize":16,"fontWeight":700,"fontColor":"#FFFFFFFF","maxLines":1}]
["battery_row","Row",{"justifyContent":"start","alignItems":"center","itemMargin":0},["left_item","right_item"]]
["left_item","Row",{"width":52,"justifyContent":"start","alignItems":"center","itemMargin":2},["left_badge","left_num","left_unit"]]
["left_badge","Text",{"content":"L","width":10.5,"height":10.5,"borderRadius":5.25,"backgroundColor":"#1AFFFFFF","fontSize":10,"fontWeight":500,"fontColor":"#FFFFFFFF","textAlign":"center","maxLines":1}]
["left_num","Text",{"content":{"path":"/data/earphone/leftBatteryLevel"},"fontSize":10,"fontWeight":400,"fontColor":"#99FFFFFF","maxLines":1}]
["left_unit","Text",{"content":"%","fontSize":10,"fontWeight":400,"fontColor":"#99FFFFFF","maxLines":1}]
["right_item","Row",{"width":52,"justifyContent":"start","alignItems":"center","itemMargin":2},["right_badge","right_num","right_unit"]]
["right_badge","Text",{"content":"R","width":10.5,"height":10.5,"borderRadius":5.25,"backgroundColor":"#1AFFFFFF","fontSize":10,"fontWeight":500,"fontColor":"#FFFFFFFF","textAlign":"center","maxLines":1}]
["right_num","Text",{"content":{"path":"/data/earphone/rightBatteryLevel"},"fontSize":10,"fontWeight":400,"fontColor":"#99FFFFFF","maxLines":1}]
["right_unit","Text",{"content":"%","fontSize":10,"fontWeight":400,"fontColor":"#99FFFFFF","maxLines":1}]
["action_area","Column",{"width":136,"itemMargin":8,"flexShrink":0},["cta_play","cta_fav"]]
["cta_play","ActionUnit",{"state":"capsule","label":"每日歌单","icon":"resources/base/media/music_fill.svg","actionSurface":"#33FFFFFF","actionInk":"#E6FFFFFF","fontSize":14,"fontWeight":500,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4"}}],"flexShrink":0}]
["cta_fav","ActionUnit",{"state":"capsule","label":"收藏歌单","icon":"resources/base/media/heart_fill.svg","actionSurface":"#33FFFFFF","actionInk":"#E6FFFFFF","fontSize":14,"fontWeight":500,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=favoriteSong&type=412"}}],"flexShrink":0}]
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
["weather_status","Text",{"content":{"path":"/data/weather/current/condition"},"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["temp_range","Text",{"content":{"path":"/data/weather/daily/0/temperatureRangeText"},"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["/data/weather/current/temperatureC",38]
["/data/weather/current/condition","晴｜空气优"]
["/data/weather/daily/0/temperatureRangeText","26°C/16°C"]
["/data/weather/location/prefectureName","深圳"]
```




## 示例五（2x2-V05）：手机+耳机电量（S4 横行亚型·青色纯色）
### user
```json
{"userQuery":"使用2*2规格，同时展示手机电量和耳机盒电量及各自充电状态。","size":"2x2","eventCandidates":[],"dataModelSchema":{"data":{"phoneBattery":{"batterySOC":{"type":"integer","description":"手机剩余电量百分比0到100","sampleValue":68},"chargingStatusDesc":{"type":"string","description":"手机当前充电状态","sampleValue":"未充电"}},"earphone":{"batteryLevel":{"type":"integer","description":"耳机盒电量百分比0到100","sampleValue":47},"chargingStatusDesc":{"type":"string","description":"耳机盒当前充电状态","sampleValue":"充电中"}}}},"assetCandidates":[{"src":"resources/base/media/phone_fill.svg","description":"本地手机图标"},{"src":"resources/base/media/earphone_case_16644.svg","description":"本地耳机盒图标"}]}
```
### assistant
```genui
["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":20,"clip":true,"justifyContent":"start","alignItems":"center","itemMargin":8,"backgroundColor":"#FFE6FDFF"},["phone_row","ear_row"]]
["phone_row","Row",{"width":136,"height":64,"justifyContent":"start","alignItems":"center","itemMargin":8},["phone_ring","phone_col"]]
["phone_ring","Stack",{"width":52,"height":52,"alignContent":"center","flexShrink":0},["phone_progress","phone_icon"]]
["phone_progress","Progress",{"type":"ring","width":52,"height":52,"strokeWidth":5,"value":{"path":"/data/phoneBattery/batterySOC"},"total":100,"color":"#FF1F8F99","backgroundColor":"#331F8F99"}]
["phone_icon","Image",{"src":"resources/base/media/phone_fill.svg","width":20,"height":20,"objectFit":"contain","fillColor":"#FF1F8F99","flexShrink":0}]
["phone_col","Column",{"width":76,"justifyContent":"center","alignItems":"start","itemMargin":4,"flexShrink":1},["phone_label","phone_value"]]
["phone_label","Text",{"content":"手机电量","fontSize":12,"fontWeight":700,"fontColor":"#FF1F8F99","maxLines":1}]
["phone_value","Text",{"content":"{{ ${/data/phoneBattery/batterySOC} + '% · ' + ${/data/phoneBattery/chargingStatusDesc} }}","width":76,"fontSize":10,"fontWeight":500,"fontColor":"#991F8F99","maxLines":1}]
["ear_row","Row",{"width":136,"justifyContent":"start","alignItems":"center","itemMargin":8},["ear_ring","ear_col"]]
["ear_ring","Stack",{"width":52,"height":52,"alignContent":"center","flexShrink":0},["ear_progress","ear_icon"]]
["ear_progress","Progress",{"type":"ring","width":52,"height":52,"strokeWidth":5,"value":{"path":"/data/earphone/batteryLevel"},"total":100,"color":"#FF1F8F99","backgroundColor":"#331F8F99"}]
["ear_icon","Image",{"src":"resources/base/media/earphone_case_16644.svg","width":20,"height":20,"objectFit":"contain","fillColor":"#FF1F8F99","flexShrink":0}]
["ear_col","Column",{"width":76,"justifyContent":"center","alignItems":"start","itemMargin":4,"flexShrink":1},["ear_label","ear_value"]]
["ear_label","Text",{"content":"耳机盒电量","fontSize":12,"fontWeight":700,"fontColor":"#FF1F8F99","maxLines":1}]
["ear_value","Text",{"content":"{{ ${/data/earphone/batteryLevel} + '% · ' + ${/data/earphone/chargingStatusDesc} }}","width":76,"fontSize":10,"fontWeight":500,"fontColor":"#991F8F99","maxLines":1}]
["/data/phoneBattery/batterySOC",68]
["/data/phoneBattery/chargingStatusDesc","未充电"]
["/data/earphone/batteryLevel",47]
["/data/earphone/chargingStatusDesc","充电中"]
```

## 示例六（2x2-V06）：日程待办（S2 状态亚型·信息列·会议冷色融球）
### user
```json
{"userQuery":"我今天会排得很满，帮我做个日程卡片，展示下一场日程的名称、开始时间和地点，并提供查看日程入口。","size":"2x2","eventCandidates":[{"call":"clickToIntent","args":{"intentName":"ViewCalendarEvent","params":{"entityId":"{{ ${/data/calendar/events/0/entityId} }}"}}}],"dataModelSchema":{"data":{"calendar":{"events":[{"entityId":{"type":"string","description":"系统日程唯一实体ID","sampleValue":"calendar-event-001"},"title":{"type":"string","description":"日程标题","sampleValue":"UI需求评审会"},"dtStart":{"type":"string","description":"开始时间HH:mm","sampleValue":"14:00"},"eventLocation":{"type":"string","description":"日程地点","sampleValue":"五和大道华为基地"},"countdownDays":{"type":"integer","description":"距离日程开始的自然日天数，0代表今天","sampleValue":0}}]}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":20,"clip":true,"justifyContent":"start","alignItems":"center","itemMargin":4,"design":"fusion-ball-schedule-cool"},["title_area","content_area","action_area"]]
["title_area","CardHeader",{"title":"今天","fontColor":"#FFFFFFFF"}]
["content_area","Column",{"width":136,"layoutWeight":1,"padding":{"top":4},"itemMargin":6,"justifyContent":"start","alignItems":"start","flexShrink":1},["event_title","event_time","event_place"]]
["event_title","Text",{"content":{"path":"/data/calendar/events/0/title"},"fontSize":12,"fontWeight":700,"width":"matchParent","fontColor":"#FFFFFFFF","maxLines":1}]
["event_time","Text",{"content":{"path":"/data/calendar/events/0/dtStart"},"fontSize":12,"fontWeight":400,"width":"matchParent","fontColor":"#99FFFFFF","maxLines":1}]
["event_place","Text",{"content":{"path":"/data/calendar/events/0/eventLocation"},"fontSize":12,"fontWeight":400,"width":"matchParent","fontColor":"#99FFFFFF","maxLines":1}]
["action_area","Column",{"width":136,"flexShrink":0},["cta"]]
["cta","ActionUnit",{"state":"capsule","label":"查看日程","actionSurface":"#33FFFFFF","actionInk":"#E6FFFFFF","fontSize":14,"fontWeight":400,"onClick":[{"call":"clickToIntent","args":{"intentName":"ViewCalendarEvent","params":{"entityId":"{{ ${/data/calendar/events/0/entityId} }}"}}}],"flexShrink":0}]
["/data/calendar/events/0/entityId","calendar-event-001"]
["/data/calendar/events/0/title","UI需求评审会"]
["/data/calendar/events/0/dtStart","14:00"]
["/data/calendar/events/0/eventLocation","五和大道华为基地"]
```

## 示例七（2x2-V07）：今日步数（S2 数值亚型·整卡隐式入口·运动橙色融球）
### user
```json
{"userQuery":"我今天活动量如何，帮我做个运动小组件，看看走了多少步和消耗多少热量，点击可以进入运动详情。","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"Health","bundleName":"","abilityName":"","uri":"huaweischeme://healthapp/home/sport?sportType=2"}}],"dataModelSchema":{"data":{"healthSport":{"dailySteps":{"type":"integer","description":"全天累计步数","sampleValue":2319},"dailyDistanceText":{"type":"string","description":"总距离文本（含单位）","sampleValue":"1.19 公里"},"dailyTotalCaloriesText":{"type":"string","description":"总消耗热量文本（含单位）","sampleValue":"59 千卡"}}}},"assetCandidates":[{"src":"resources/base/media/figure_run.svg","description":"跑步人形图标"}]}
```
### assistant
```genui
["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":20,"clip":true,"justifyContent":"start","alignItems":"center","itemMargin":4,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Health","bundleName":"","abilityName":"","uri":"huaweischeme://healthapp/home/sport?sportType=2"}}],"design":"fusion-ball-sport-orange"},["title_area","content_area","bottom_area"]]
["title_area","CardHeader",{"title":"今日步数","fontColor":"#99FFFFFF","icon":"resources/base/media/figure_run.svg","fillColor":"#99FFFFFF"}]
["content_area","Column",{"width":136,"layoutWeight":1,"justifyContent":"start","alignItems":"start","itemMargin":4,"flexShrink":1},["value_row","step_bar"]]
["value_row","Row",{"width":136,"justifyContent":"start","alignItems":"bottom","itemMargin":2},["value_num","value_unit"]]
["value_num","Text",{"content":{"path":"/data/healthSport/dailySteps"},"fontSize":30,"fontWeight":700,"fontColor":"#FFFFFFFF","maxLines":1}]
["value_unit","Text",{"content":"步","fontSize":12,"fontWeight":500,"fontColor":"#FFFFFFFF","padding":{"bottom":4},"maxLines":1}]
["step_bar","Progress",{"type":"linear","width":136,"height":8,"strokeWidth":8,"borderRadius":4,"value":{"path":"/data/healthSport/dailySteps"},"total":8760,"color":"#FFFFFFFF","backgroundColor":"#33FFFFFF"}]
["bottom_area","Column",{"width":136,"height":34,"itemMargin":2,"justifyContent":"start","flexShrink":0},["aux_1","aux_2"]]
["aux_1","Row",{"itemMargin":4,"alignItems":"center"},["aux_1_t","aux_1_v"]]
["aux_1_t","Text",{"content":"运动距离","fontSize":12,"fontWeight":400,"fontColor":"#99FFFFFF","maxLines":1}]
["aux_1_v","Text",{"content":{"path":"/data/healthSport/dailyDistanceText"},"fontSize":12,"fontWeight":700,"fontColor":"#FFFFFFFF","maxLines":1}]
["aux_2","Row",{"itemMargin":4,"alignItems":"center"},["aux_2_t","aux_2_v"]]
["aux_2_t","Text",{"content":"消耗热量","fontSize":12,"fontWeight":400,"fontColor":"#99FFFFFF","maxLines":1}]
["aux_2_v","Text",{"content":{"path":"/data/healthSport/dailyTotalCaloriesText"},"fontSize":12,"fontWeight":700,"fontColor":"#FFFFFFFF","maxLines":1}]
["/data/healthSport/dailySteps",2319]
["/data/healthSport/dailyDistanceText","1.19 公里"]
["/data/healthSport/dailyTotalCaloriesText","59 千卡"]
```
