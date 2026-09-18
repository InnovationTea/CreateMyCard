# 2x2 Few-shot

示例中的图标位置不可迁移到普通内容行：内容区仅允许环中心或 S4 双对象分区主视觉图标，其他内容不生成 Image，L/R/盒 Text 标识保留。S4 包括同类双对象，如两个城市天气，并且必须完整生成上下两个 `136×64vp` 分区；单对象绝对禁止仿照 V05 生成单个分区。S4 会议分区固定用两行表达：第一行只放会议标题 `14fp/700`，第二行只放时间 `12fp/400`；背板已绑定入会动作时，不生成“点击卡片”、“一键入会”等动作提示 Text，不将时间和标题拼在同一行。有语义准确且状态安全的候选素材时，每个天气区可放 1 个主视觉图标（可复用 src，分别计数），不是给温度、日期等文字逐行配图，按钮及标题不再配图标。S4 的 1-2 项数据是否保留右侧图标不得由文字字符数、是否超过 6 个字或占用行数决定；图标固定在右侧且距背板右边 12vp。V05 的环只适用于具有明确 0-100 比例语义的电量，不得迁移到温度、时间、时长、倒计时或普通数值；两座城市天气禁止使用进度环。用户明确指定图标的例外仍按主提示词执行。

示例中的数据路径、事件和素材候选取自能力清单；真实输出只能使用当前 TaskSpec 实际提供的 path、icon 和 onClick。示例用于参考布局，背景选择、业务映射及内容配色统一遵循 PROMPT.md 第十二节；用户明确配色要求优先，未指定时不得沿用旧色值或自由取色。融球示例仅在本次尺寸、业务、密度和运行时条件均满足时使用，否则按主业务切换到对应浅色纯色及配套内容色。

图标与动作必须逐一匹配当前对象和真实目标；候选中允许存在干扰项。示例里的动作不是业务默认配置，跨业务组合只在用户明确要求时保留。没有准确图标就用纯文字；不要按分区数复制共享动作。

## 示例一（2x2-V01）：运动会倒计时（S1 单信息·融球暖橙）
倒计时是“量化主值第一行”的位置例外：目标名称固定在顶部居中，大数字主值组位于其下方的卡片中部。`value_group` 最多两行视觉内容：第一行是数字，第二行无明确时间时只放单位“天”；有明确时间时第二行使用 `meta_row`，在同一行显示“天 · 时间”。禁止第三行辅助文字，也禁止在中部重复目标名称。仅当用户明确要求一个动作且实际候选的目标匹配时，在 root 末尾追加 `action_area` 和胶囊 `ActionUnit`；`value_group` 使用 `layoutWeight:1` 占满中间剩余高度，使 36vp 按钮固定距卡片底部 12vp。
干扰候选示范：输入虽含一个歌单事件和音符素材，但本次只要求倒计时；输出不生成按钮、图标或隐式点击，不把候选数量当作用户意图。
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
["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":20,"clip":true,"justifyContent":"start","alignItems":"center","itemMargin":4,"linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["title_area","content_area","bottom_area"]]
["title_area","CardHeader",{"title":{"path":"/data/weather/location/prefectureName"},"fontColor":"#FF1F4799","icon":"resources/base/media/icon_weather_temperature1.svg"}]
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
两个分区都使用固定的左文字、右电量环结构；环外框距背板右边 12vp，环与 Progress 固定 `44×44vp`、`strokeWidth:6`，中心图标固定 `20×20vp`。文字长度不得改变环的位置或尺寸。
### user
```json
{"userQuery":"使用2*2规格，同时展示手机电量和耳机盒电量及各自充电状态，点击对应区域进入电池或蓝牙设置。","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"battery"}},{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"bluetooth_entry"}}],"dataModelSchema":{"data":{"phoneBattery":{"batterySOC":{"type":"integer","description":"手机剩余电量百分比0到100","sampleValue":68},"chargingStatusDesc":{"type":"string","description":"手机当前充电状态","sampleValue":"未充电"}},"earphone":{"batteryLevel":{"type":"integer","description":"耳机盒电量百分比0到100","sampleValue":47},"chargingStatusDesc":{"type":"string","description":"耳机盒当前充电状态","sampleValue":"充电中"}}}},"assetCandidates":[{"src":"resources/base/media/phone_fill.svg","description":"本地手机图标"},{"src":"resources/base/media/earphone_case_16644.svg","description":"本地耳机盒图标"}]}
```
### assistant
```genui
["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":20,"clip":true,"justifyContent":"start","alignItems":"center","itemMargin":8,"linearGradient":{"direction":"RightBottom","colors":[["#FFCCFCFF",0],["#FFF2FEFF",1]]}},["phone_row","ear_row"]]
["phone_row","Row",{"width":136,"height":64,"padding":{"left":12,"right":12,"top":0,"bottom":0},"borderRadius":16,"backgroundColor":"#CCFFFFFF","justifyContent":"start","alignItems":"center","itemMargin":8,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"battery"}}]},["phone_col","phone_ring"]]
["phone_col","Column",{"width":60,"justifyContent":"center","alignItems":"start","itemMargin":2,"flexShrink":0},["phone_value","phone_status"]]
["phone_value","Text",{"content":"{{ ${/data/phoneBattery/batterySOC} + '%' }}","width":60,"fontSize":14,"fontWeight":700,"fontColor":"#FF1C838C","maxLines":1}]
["phone_status","Text",{"content":{"path":"/data/phoneBattery/chargingStatusDesc"},"width":60,"fontSize":12,"fontWeight":400,"fontColor":"#FF1C838C","maxLines":1}]
["phone_ring","Stack",{"width":44,"height":44,"alignContent":"center","flexShrink":0},["phone_progress","phone_icon"]]
["phone_progress","Progress",{"type":"ring","width":44,"height":44,"strokeWidth":6,"value":{"path":"/data/phoneBattery/batterySOC"},"total":100,"color":"#FF1C838C","backgroundColor":"#331C838C"}]
["phone_icon","Image",{"src":"resources/base/media/phone_fill.svg","width":20,"height":20,"objectFit":"contain","fillColor":"#FF1C838C","flexShrink":0}]
["ear_row","Row",{"width":136,"height":64,"padding":{"left":12,"right":12,"top":0,"bottom":0},"borderRadius":16,"backgroundColor":"#CCFFFFFF","justifyContent":"start","alignItems":"center","itemMargin":8,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"bluetooth_entry"}}]},["ear_col","ear_ring"]]
["ear_col","Column",{"width":60,"justifyContent":"center","alignItems":"start","itemMargin":2,"flexShrink":0},["ear_value","ear_status"]]
["ear_value","Text",{"content":"{{ ${/data/earphone/batteryLevel} + '%' }}","width":60,"fontSize":14,"fontWeight":700,"fontColor":"#FF1C838C","maxLines":1}]
["ear_status","Text",{"content":{"path":"/data/earphone/chargingStatusDesc"},"width":60,"fontSize":12,"fontWeight":400,"fontColor":"#FF1C838C","maxLines":1}]
["ear_ring","Stack",{"width":44,"height":44,"alignContent":"center","flexShrink":0},["ear_progress","ear_icon"]]
["ear_progress","Progress",{"type":"ring","width":44,"height":44,"strokeWidth":6,"value":{"path":"/data/earphone/batteryLevel"},"total":100,"color":"#FF1C838C","backgroundColor":"#331C838C"}]
["ear_icon","Image",{"src":"resources/base/media/earphone_case_16644.svg","width":20,"height":20,"objectFit":"contain","fillColor":"#FF1C838C","flexShrink":0}]
["/data/phoneBattery/batterySOC",68]
["/data/phoneBattery/chargingStatusDesc","未充电"]
["/data/earphone/batteryLevel",47]
["/data/earphone/chargingStatusDesc","充电中"]
```

## 示例六（2x2-V06）：单个或下一场会议（S2 会议时间线亚型·黄色微渐变）
2x2 整卡唯一业务为 calendar、最终只展示一个会议，且 userQuery、事件候选或 TaskSpec 的标题/描述/sampleValue 明确表达会议语义时，强制使用本例；sampleValue 只用于路由判断，不得代替动态绑定。`day_area` 必须保留为首个左对齐 `136×16vp Row`。会议标题必须作为内容区第一行 `14fp/700`：优先绑定 `events[0].title`，无真实标题字段且用户未给出名称时固定写“日程”，不得省略或用 `eventCount`、日期、时间替代。标题下最多两行辅助信息，时间、地点固定 `12fp/400`，且不增加普通 Image。出现任一其他业务时改走 S4，禁止使用本例和 TimelineUnit。仅按当前 TaskSpec 替换字段和动作，不改成普通信息列。
### user
```json
{"userQuery":"帮我做张会议提醒卡片，看看下一场会叫什么、几点开始、在哪里开，还能点一下直接入会。","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"EnterMeeting","bundleName":"","abilityName":"","uri":"{{ ${/data/calendar/events/0/oneClickServiceLink} }}"}}],"dataModelSchema":{"data":{"calendar":{"events":[{"title":{"type":"string","description":"日程标题","sampleValue":"UI需求评审会"},"dtStart":{"type":"string","description":"开始时间","sampleValue":"14:00 - 15:30"},"eventLocation":{"type":"string","description":"会议地点","sampleValue":"C5会议室"},"oneClickServiceLink":{"type":"string","description":"一键入会链接","sampleValue":"wemeet://join/example"}}]}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":20,"clip":true,"backgroundColor":"#FFFFF3E6","justifyContent":"start","alignItems":"center","itemMargin":4},["day_area","content_area","action_area"]]
["day_area","Row",{"width":136,"height":16,"justifyContent":"start","alignItems":"center","flexShrink":0},["day_tag"]]
["day_tag","Text",{"content":"下一场会议","fontSize":12,"fontWeight":700,"fontColor":"#FF8C4B1C","maxLines":1}]
["content_area","Row",{"width":136,"layoutWeight":1,"padding":{"top":4},"itemMargin":8,"alignItems":"top","justifyContent":"start","flexShrink":1},["timeline","meeting_texts"]]
["timeline","TimelineUnit",{"color":"#FF8C4B1C","lineColor":"#1A8C4B1C"}]
["meeting_texts","Column",{"width":"matchParent","height":48,"layoutWeight":1,"itemMargin":4,"justifyContent":"start","alignItems":"start","flexShrink":1},["event_title","event_time","event_place"]]
["event_title","Text",{"content":{"path":"/data/calendar/events/0/title"},"fontSize":14,"fontWeight":700,"width":"matchParent","fontColor":"#FF8C4B1C","maxLines":1}]
["event_time","Text",{"content":{"path":"/data/calendar/events/0/dtStart"},"fontSize":12,"fontWeight":400,"width":"matchParent","fontColor":"#FF8C4B1C","maxLines":1}]
["event_place","Text",{"content":{"path":"/data/calendar/events/0/eventLocation"},"fontSize":12,"fontWeight":400,"width":"matchParent","fontColor":"#FF8C4B1C","maxLines":1}]
["action_area","Column",{"width":136,"flexShrink":0,"alignItems":"start"},["cta"]]
["cta","ActionUnit",{"state":"capsule","label":"加入会议","actionSurface":"#338C4B1C","actionInk":"#FF8C4B1C","fontSize":14,"fontWeight":400,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"EnterMeeting","bundleName":"","abilityName":"","uri":"{{ ${/data/calendar/events/0/oneClickServiceLink} }}"}}],"flexShrink":0}]
["/data/calendar/events/0/title","UI需求评审会"]
["/data/calendar/events/0/dtStart","14:00 - 15:30"]
["/data/calendar/events/0/eventLocation","C5会议室"]
["/data/calendar/events/0/oneClickServiceLink","wemeet://join/example"]
```

## 示例七（2x2-V07）：今日步数（S2 数值亚型·整卡隐式入口·绿色纯色）
### user
```json
{"userQuery":"做张运动卡片，看看我今天走了多少步、走了多远、消耗多少热量，点一下能看运动详情。","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"Health","bundleName":"","abilityName":"","uri":"huaweischeme://healthapp/home/sport?sportType=2"}}],"dataModelSchema":{"data":{"healthSport":{"dailySteps":{"type":"integer","description":"全天累计步数","sampleValue":2319},"dailyDistanceText":{"type":"string","description":"总距离文本（含单位）","sampleValue":"1.19 公里"},"dailyTotalCaloriesText":{"type":"string","description":"总消耗热量文本（含单位）","sampleValue":"59 千卡"}}}},"assetCandidates":[{"src":"resources/base/media/figure_run.svg","description":"跑步人形图标"}]}
```
### assistant
```genui
["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":20,"clip":true,"justifyContent":"start","alignItems":"center","itemMargin":4,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Health","bundleName":"","abilityName":"","uri":"huaweischeme://healthapp/home/sport?sportType=2"}}],"design":"fusion-ball-sport-orange"},["title_area","content_area","bottom_area"]]
["title_area","CardHeader",{"title":"今日步数","fontColor":"#CCFFFFFF","icon":"resources/base/media/figure_run.svg","fillColor":"#FFFFFFFF"}]
["content_area","Column",{"width":136,"layoutWeight":1,"justifyContent":"center","alignItems":"start","itemMargin":4,"flexShrink":1},["value_row"]]
["value_row","Row",{"width":136,"justifyContent":"start","alignItems":"bottom","itemMargin":2},["value_num","value_unit"]]
["value_num","Text",{"content":{"path":"/data/healthSport/dailySteps"},"fontSize":30,"fontWeight":700,"fontColor":"#FFFFFFFF","maxLines":1}]
["value_unit","Text",{"content":"步","fontSize":12,"fontWeight":500,"fontColor":"#FFFFFFFF","padding":{"bottom":4},"maxLines":1}]
["bottom_area","Column",{"width":136,"height":34,"itemMargin":2,"justifyContent":"start","flexShrink":0,"alignItems":"start"},["aux_1","aux_2"]]
["aux_1","Row",{"itemMargin":4,"alignItems":"center"},["aux_1_t","aux_1_v"]]
["aux_1_t","Text",{"content":"运动距离","fontSize":12,"fontWeight":400,"fontColor":"#CCFFFFFF","maxLines":1}]
["aux_1_v","Text",{"content":{"path":"/data/healthSport/dailyDistanceText"},"fontSize":12,"fontWeight":400,"fontColor":"#CCFFFFFF","maxLines":1}]
["aux_2","Row",{"itemMargin":4,"alignItems":"center"},["aux_2_t","aux_2_v"]]
["aux_2_t","Text",{"content":"消耗热量","fontSize":12,"fontWeight":400,"fontColor":"#9952991F","maxLines":1}]
["aux_2_v","Text",{"content":{"path":"/data/healthSport/dailyTotalCaloriesText"},"fontSize":12,"fontWeight":700,"fontColor":"#9952991F","maxLines":1}]
["/data/healthSport/dailySteps",2319]
["/data/healthSport/dailyDistanceText","1.19 公里"]
["/data/healthSport/dailyTotalCaloriesText","59 千卡"]
```
