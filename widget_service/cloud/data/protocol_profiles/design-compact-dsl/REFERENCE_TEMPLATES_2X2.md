# 2x2 金标卡片 Few-shot 集（8 张）

从 `few-shot-2x2.md` 抽取的 2026-08-21 校准定稿集：A03/A04/A06/A09/A12/A15/B01/B03。

校准依据（按最终生效顺序）：

1. `Design-guide/DESIGN.md` 主题色板与按钮配对规则：浅色遮罩卡按钮 = 主题色 10% 底（19 alpha 档）+ 主题色 100% 前景；白底（`actionSurface:"white"`）仅用于不透明渐变卡（天气/雨天/运动）。
2. 色板锚定：confirm 绿 #64BB5C、低电量 #F9A01E、日程红 #E84026、天气 #317AF7、雨天 #467794、运动 #ED6F21；#18B87A 不在色板。
3. 进度/环底槽统一中性 #19000000；进度条高度 8vp（linear-bar 设计令牌）。
4. 文字必须显式 fontColor（主 #E5000000 / 次 #99000000），渲染器默认白字会隐形。
5. 混排行基线对齐：小字号单位补 `padding:{"bottom":2}`（16/30、12/24 组合）或 4（14/30 组合）。
6. 面性图标：sun_max_fill.svg、drop_fill.svg（库内派生资产）；彩色渐变卡装饰图标一律 #FFFFFFFF。

渲染产物对照：`render/v6/`（截图）、`render_src/`（A2UI jsonl）。编号与主文件一致，改动请先改主文件再同步本文件。

## 示例三（2x2-A03）：环内图片 + 右下 icon-round（Want/q9）
### user
```json
{"userQuery":"生成环内图片 + 右下 icon-round（Want/q9）","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"uri":"demo://replace-with-candidate"}}],"dataModelSchema":{"data":{"battery":{"level":{"type":"integer","description":"示例字段","sampleValue":20}}}},"assetCandidates":[{"src":"resources/base/media/battery_leaf_fill.svg","description":"当前示例使用的本地素材"},{"src":"resources/base/media/bolt_fill.svg","description":"当前示例使用的本地素材"}]}
```
### assistant
```genui
["root","Column",{"width":160,"height":160,"padding":12,"borderRadius":20,"clip":true,"design":"Surface.orangeSoft","justifyContent":"start","itemMargin":8},["title_area","content_area","bottom_area"]]
["title_area","Row",{"width":136,"height":20,"justifyContent":"start","alignItems":"top","flexShrink":0},["title_text"]]
["title_text","Text",{"content":"手机电量","design":"card-title","width":136,"fontColor":"#E5000000","maxLines":1,"textOverflow":"clip"}]
["content_area","Column",{"width":136,"layoutWeight":1,"justifyContent":"start","alignItems":"start","itemMargin":4,"flexShrink":1},["status_text"]]
["status_text","Text",{"content":"电量偏低，建议开启省电","design":"body-m","width":136,"fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}]
["bottom_area","Row",{"width":136,"height":66,"itemMargin":8,"justifyContent":"spaceBetween","alignItems":"bottom","flexShrink":0},["ring_icon_stack","action_area"]]
["ring_icon_stack","Stack",{"width":52,"height":52,"alignContent":"center","flexShrink":0},["ring_progress","ring_icon"]]
["ring_progress","Progress",{"design":"ring","width":52,"height":52,"strokeWidth":6,"value":{"path":"/data/battery/level"},"total":100,"color":"#FFF9A01E","backgroundColor":"#19000000"}]
["ring_icon","Image",{"src":"resources/base/media/battery_leaf_fill.svg","width":24,"height":24,"objectFit":"contain","fillColor":"#FFF9A01E","flexShrink":0}]
["action_area","Column",{"width":40,"height":40,"flexShrink":0},["cta"]]
["cta","ActionUnit",{"state":"icon-round","icon":"resources/base/media/bolt_fill.svg","actionInk":"#FFF9A01E","onClick":[{"call":"clickToDeeplink","args":{"uri":"demo://replace-with-candidate"}}]}]
["/data/battery/level",20]
```

## 示例四（2x2-A04）：环内图片 + 环外长数值 + 底部 capsule（q6 兜底）
### user
```json
{"userQuery":"生成环内图片 + 环外长数值 + 底部 capsule（q6 兜底）","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"uri":"demo://replace-with-candidate"}}],"dataModelSchema":{"data":{"systemMem":{"usagePercent":{"type":"number","description":"示例字段","sampleValue":43.75}}}},"assetCandidates":[{"src":"resources/base/media/clean_fill.svg","description":"当前示例使用的本地素材"}]}
```
### assistant
```genui
["root","Column",{"width":160,"height":160,"padding":12,"borderRadius":20,"clip":true,"design":"Surface.greenSoft","justifyContent":"start","itemMargin":8},["title_area","content_area","action_area"]]
["title_area","Row",{"width":136,"height":20,"alignItems":"top","justifyContent":"start","flexShrink":0},["title_col"]]
["title_col","Column",{"width":"matchParent","layoutWeight":1,"flexShrink":1},["title_text"]]
["title_text","Text",{"content":"内存使用","design":"card-title","width":"matchParent","fontColor":"#E5000000","maxLines":1,"textOverflow":"clip"}]
["content_area","Row",{"width":136,"layoutWeight":1,"alignItems":"center","justifyContent":"start","itemMargin":8},["ring_icon_stack","text_block"]]
["ring_icon_stack","Stack",{"width":52,"height":52,"alignContent":"center","flexShrink":0},["ring_progress","ring_icon"]]
["ring_progress","Progress",{"design":"ring","width":52,"height":52,"strokeWidth":6,"value":{"path":"/data/systemMem/usagePercent"},"total":100,"color":"#FF64BB5C","backgroundColor":"#19000000"}]
["ring_icon","Image",{"src":"resources/base/media/clean_fill.svg","width":24,"height":24,"objectFit":"contain","fillColor":"#FF64BB5C","flexShrink":0}]
["text_block","Column",{"width":"matchParent","layoutWeight":1,"flexShrink":1,"itemMargin":8,"justifyContent":"center","alignItems":"start"},["value_row","primary_label"]]
["value_row","Row",{"width":"matchParent","alignItems":"bottom","itemMargin":1},["value_num","value_unit"]]
["value_num","Text",{"content":{"path":"/data/systemMem/usagePercent"},"design":"title-m","fontColor":"#E5000000","maxLines":1,"textOverflow":"clip"}]
["value_unit","Text",{"content":"%","design":"body-s","fontColor":"#99000000","padding":{"bottom":2},"maxLines":1,"textOverflow":"clip"}]
["primary_label","Text",{"content":"内存占用","design":"hero-label","width":"matchParent","fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}]
["action_area","Column",{"width":"matchParent","height":36,"flexShrink":0},["cta"]]
["cta","ActionUnit",{"state":"capsule","label":"立即优化","onClick":[{"call":"clickToDeeplink","args":{"uri":"demo://replace-with-candidate"}}],"actionInk":"#FF64BB5C","flexShrink":0}]
["/data/systemMem/usagePercent",43.75]
```

## 示例六（2x2-A06）：meeting-timeline + 底部 capsule
### user
```json
{"userQuery":"生成meeting-timeline + 底部 capsule","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"uri":"demo://replace-with-candidate"}}],"dataModelSchema":{"data":{"calendar":{"events":[{"title":{"type":"string","description":"示例字段","sampleValue":"项目例会"},"dtStart":{"type":"string","description":"示例字段","sampleValue":"14:00 - 15:00"},"eventLocation":{"type":"string","description":"示例字段","sampleValue":"会议室"}}]}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Column",{"width":160,"height":160,"padding":12,"borderRadius":20,"clip":true,"design":"Surface.redSoft","justifyContent":"start","itemMargin":8},["date_badge_area","meeting_area","action_area"]]
["date_badge_area","Row",{"width":136,"height":20,"alignItems":"top","justifyContent":"spaceBetween","flexShrink":0},["title_text","date_badge"]]
["title_text","Text",{"content":"今日日程","design":"card-title","width":92,"fontSize":14,"fontWeight":500,"fontColor":"#E5000000","maxLines":1,"textOverflow":"clip"}]
["date_badge","Text",{"content":"22","width":28,"height":24,"borderRadius":6,"backgroundColor":"#FFFFFFFF","fontSize":16,"fontWeight":700,"fontColor":"#E5000000","textAlign":"center","maxLines":1,"textOverflow":"clip","shadow":{"radius":4,"color":"#1A000000","offsetX":0,"offsetY":1}}]
["meeting_area","Row",{"width":136,"layoutWeight":1,"itemMargin":6,"alignItems":"center","justifyContent":"start","flexShrink":1},["timeline","meeting_texts"]]
["timeline","TimelineUnit",{"height":48,"color":"#FFE84026","lineColor":"#1A000000","flexShrink":0}]
["meeting_texts","Column",{"width":"matchParent","layoutWeight":1,"itemMargin":2,"justifyContent":"start","alignItems":"start","flexShrink":1},["event_title","event_time","event_place"]]
["event_title","Text",{"content":{"path":"/data/calendar/events/0/title"},"fontSize":20,"fontWeight":700,"width":"matchParent","fontColor":"#E5000000","maxLines":1,"textOverflow":"clip"}]
["event_time","Text",{"content":{"path":"/data/calendar/events/0/dtStart"},"fontSize":14,"fontWeight":400,"width":"matchParent","fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}]
["event_place","Text",{"content":{"path":"/data/calendar/events/0/eventLocation"},"fontSize":12,"fontWeight":400,"width":"matchParent","fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}]
["action_area","Column",{"width":"matchParent","height":36,"flexShrink":0},["cta"]]
["cta","ActionUnit",{"state":"capsule","label":"查看安排","onClick":[{"call":"clickToDeeplink","args":{"uri":"demo://replace-with-candidate"}}],"actionInk":"#FFE84026","flexShrink":0}]
["/data/calendar/events/0/title","项目例会"]
["/data/calendar/events/0/dtStart","14:00 - 15:00"]
["/data/calendar/events/0/eventLocation","会议室"]
```

## 示例九（2x2-A09）：强蓝天气卡 + 右下 icon-round
### user
```json
{"userQuery":"生成强蓝天气卡 + 右下 icon-round","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"uri":"demo://replace-with-candidate"}}],"dataModelSchema":{},"assetCandidates":[{"src":"resources/base/media/sun_max_fill.svg","description":"单色可染色的面性太阳图标，适合晴天状态"},{"src":"resources/base/media/phone_fill.svg","description":"当前示例使用的本地素材"}]}
```
### assistant
```genui
["root","Column",{"width":160,"height":160,"padding":12,"borderRadius":20,"clip":true,"itemMargin":8,"justifyContent":"start","design":"Surface.weatherStrongBlue"},["title_area","content_area","bottom_area"]]
["title_area","Row",{"width":136,"height":20,"alignItems":"center","justifyContent":"spaceBetween","flexShrink":0},["title_text","title_icon"]]
["title_text","Text",{"content":"深圳天气","design":"card-title","fontColor":"#FFFFFFFF","width":108,"maxLines":1,"textOverflow":"clip"}]
["title_icon","Image",{"src":"resources/base/media/sun_max_fill.svg","width":20,"height":20,"fillColor":"#FFFFFFFF","flexShrink":0}]
["content_area","Column",{"width":136,"layoutWeight":1,"justifyContent":"center","alignItems":"start","flexShrink":1},["value_row"]]
["value_row","Row",{"width":136,"layoutWeight":1,"alignItems":"bottom","itemMargin":2,"justifyContent":"start","flexShrink":1},["value_num","value_unit"]]
["value_num","Text",{"content":"38","design":"hero-value","fontColor":"#FFFFFFFF","maxLines":1,"textOverflow":"clip"}]
["value_unit","Text",{"content":"°C","design":"hero-unit","fontColor":"#FFFFFFFF","padding":{"bottom":2},"maxLines":1,"textOverflow":"clip"}]
["bottom_area","Row",{"width":136,"height":40,"itemMargin":8,"justifyContent":"spaceBetween","alignItems":"bottom","flexShrink":0},["weather_texts","action_area"]]
["weather_texts","Column",{"width":96,"height":34,"itemMargin":8,"justifyContent":"start"},["weather_status","temp_range"]]
["weather_status","Text",{"content":"晴 | 空气优","design":"body-m","fontColor":"#FFFFFFFF","width":96,"maxLines":1,"textOverflow":"clip"}]
["temp_range","Text",{"content":"26°/16°","design":"caption-l","fontColor":"#CCFFFFFF","width":96,"maxLines":1,"textOverflow":"clip"}]
["action_area","Column",{"width":40,"height":40,"flexShrink":0},["cta"]]
["cta","ActionUnit",{"state":"icon-round","icon":"resources/base/media/phone_fill.svg","actionSurface":"white","actionInk":"#FF317AF7","onClick":[{"call":"clickToDeeplink","args":{"uri":"demo://replace-with-candidate"}}]}]
```

## 示例十二（2x2-A12）：存储清理卡 + 横向进度 + 右下 icon-round
### user
```json
{"userQuery":"生成存储清理卡 + 横向进度 + 右下 icon-round","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"uri":"demo://replace-with-candidate"}}],"dataModelSchema":{"data":{"storage":{"cleanablePercent":{"type":"integer","description":"示例字段","sampleValue":68}}}},"assetCandidates":[{"src":"resources/base/media/clean_fill.svg","description":"当前示例使用的本地素材"}]}
```
### assistant
```genui
["root","Column",{"width":160,"height":160,"padding":12,"borderRadius":20,"clip":true,"itemMargin":8,"justifyContent":"start","design":"Surface.greenSoft"},["title_text","main_area","bottom_row"]]
["title_text","Text",{"content":"存储清理","design":"card-title","width":136,"fontColor":"#E5000000","maxLines":1,"textOverflow":"clip"}]
["main_area","Column",{"width":136,"layoutWeight":1,"itemMargin":6,"justifyContent":"center","alignItems":"start"},["value_row","primary_label","progress_bar"]]
["value_row","Row",{"width":136,"height":36,"alignItems":"bottom","itemMargin":2},["value_num","value_unit"]]
["value_num","Text",{"content":"1.2","design":"hero-value","fontColor":"#E5000000","maxLines":1,"textOverflow":"clip"}]
["value_unit","Text",{"content":"GB","design":"hero-unit","fontColor":"#99000000","padding":{"bottom":2},"maxLines":1,"textOverflow":"clip"}]
["primary_label","Text",{"content":"可清理","design":"hero-label","width":136,"fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}]
["progress_bar","Progress",{"design":"linear-bar","value":{"path":"/data/storage/cleanablePercent"},"total":100,"color":"#FF64BB5C","backgroundColor":"#19000000"}]
["bottom_row","Row",{"width":136,"height":40,"justifyContent":"spaceBetween","alignItems":"bottom","flexShrink":0},["tip_text","cta"]]
["tip_text","Text",{"content":"缓存偏多","design":"caption-l","width":96,"fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}]
["cta","ActionUnit",{"state":"icon-round","icon":"resources/base/media/clean_fill.svg","actionInk":"#FF64BB5C","onClick":[{"call":"clickToDeeplink","args":{"uri":"demo://replace-with-candidate"}}]}]
["/data/storage/cleanablePercent",68]
```

## 示例十五（2x2-A15）：赛事倒计时强橙背景 + 底部胶囊
### user
```json
{"userQuery":"生成赛事倒计时强橙背景 + 底部胶囊","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"uri":"demo://replace-with-candidate"}}],"dataModelSchema":{},"assetCandidates":[{"src":"resources/base/media/stopwatch_fill.svg","description":"当前示例使用的本地素材"},{"src":"resources/base/media/figure_run.svg","description":"当前示例使用的本地素材"}]}
```
### assistant
```genui
["root","Column",{"width":160,"height":160,"padding":12,"borderRadius":20,"clip":true,"itemMargin":8,"justifyContent":"start","design":"Surface.sportStrongOrange"},["title_area","content_area","cta"]]
["title_area","Row",{"width":136,"height":20,"justifyContent":"spaceBetween","alignItems":"center","flexShrink":0},["title_text","title_icon"]]
["title_text","Text",{"content":"运动会倒数","design":"card-title","fontColor":"#FFFFFFFF","width":108,"maxLines":1,"textOverflow":"clip"}]
["title_icon","Image",{"src":"resources/base/media/stopwatch_fill.svg","width":20,"height":20,"fillColor":"#FFFFFFFF","flexShrink":0}]
["content_area","Column",{"width":136,"layoutWeight":1,"itemMargin":8,"justifyContent":"center"},["days_row","desc_text"]]
["days_row","Row",{"width":136,"height":40,"alignItems":"bottom","itemMargin":4},["days_value","days_unit"]]
["days_value","Text",{"content":"32","design":"hero-value","fontColor":"#FFFFFFFF","maxLines":1,"textOverflow":"clip"}]
["days_unit","Text",{"content":"天","design":"body-m","fontColor":"#CCFFFFFF","padding":{"bottom":4},"maxLines":1,"textOverflow":"clip"}]
["desc_text","Text",{"content":"距离开幕","design":"caption-l","fontColor":"#CCFFFFFF","width":136,"maxLines":1,"textOverflow":"clip"}]
["cta","ActionUnit",{"state":"capsule","label":"30km慢跑","icon":"resources/base/media/figure_run.svg","actionSurface":"white","actionInk":"#FFED6F21","onClick":[{"call":"clickToDeeplink","args":{"uri":"demo://replace-with-candidate"}}]}]
```

## 示例一（2x2-B01）：低电量状态与单一动作，主动舍弃无关候选
### user
```json
{"userQuery":"做个低电量卡片，显示电量和电量等级，点一下就开启省电模式。","size":"2x2","eventCandidates":[{"call":"clickToIntent","args":{"intentName":"SetSettingSwitch","params":{"appBundleName":"com.huawei.hmos.settings","itemName":"battery_saving_mode","switchFlag":0}}},{"call":"clickToDeeplink","args":{"intentName":"Weather_CityCode","bundleName":"","abilityName":"","uri":"hww://www.huawei.com/totemweather?enterType=share&cityCode="}}],"dataModelSchema":{"data":{"phoneBattery":{"batterySOCText":{"type":"string","description":"手机剩余电量百分比文本","sampleValue":"18%"},"batteryCapacityLevelDesc":{"type":"string","description":"当前电池电量等级","sampleValue":"低电量"}}}},"assetCandidates":[{"src":"resources/base/media/battery_leaf_fill.svg","description":"单色可染色的电池与绿叶实心图标，适合省电模式和绿色用电"},{"src":"resources/base/media/icon_weather1.svg","description":"自带多色渐变、需要保留原始颜色的天气状态图标，适合天气应用入口"}]}
```
### assistant
```genui
["root","Column",{"width":160,"height":160,"padding":12,"borderRadius":20,"clip":true,"design":"Surface.orangeSoft","justifyContent":"start","itemMargin":8},["title_area","content_area","action_area"]]
["title_area","Row",{"width":136,"height":20,"justifyContent":"spaceBetween","alignItems":"center","flexShrink":0},["title_text","battery_icon"]]
["title_text","Text",{"content":"电量提醒","design":"card-title","width":108,"fontColor":"#E5000000","maxLines":1,"textOverflow":"clip"}]
["battery_icon","Image",{"src":"resources/base/media/battery_leaf_fill.svg","width":20,"height":20,"objectFit":"contain","fillColor":"#FFF9A01E","flexShrink":0}]
["content_area","Column",{"width":136,"layoutWeight":1,"justifyContent":"center","alignItems":"start","itemMargin":8,"flexShrink":1},["battery_value","battery_state"]]
["battery_value","Text",{"content":{"path":"/data/phoneBattery/batterySOCText"},"design":"hero-value","width":136,"fontColor":"#E5000000","maxLines":1,"textOverflow":"clip"}]
["battery_state","Text",{"content":{"path":"/data/phoneBattery/batteryCapacityLevelDesc"},"design":"body-m","width":136,"fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}]
["action_area","Column",{"width":"matchParent","height":36,"flexShrink":0},["cta"]]
["cta","ActionUnit",{"state":"capsule","label":"开启省电","onClick":[{"call":"clickToIntent","args":{"intentName":"SetSettingSwitch","params":{"appBundleName":"com.huawei.hmos.settings","itemName":"battery_saving_mode","switchFlag":0}}}],"actionInk":"#FFF9A01E","flexShrink":0}]
["/data/phoneBattery/batterySOCText","18%"]
["/data/phoneBattery/batteryCapacityLevelDesc","低电量"]
```

## 示例三（2x2-B03）：带单位天气主值与精简导航动作，主动舍弃次要字段
### user
```json
{"userQuery":"做一张雨天出行卡片，显示当前温度和天气，给我一个导航回家的按钮。","size":"2x2","eventCandidates":[{"call":"clickToIntent","args":{"intentName":"StartNavigate","params":{"dstLocation":{"location":"home","latitude":"","longitude":""}}}}],"dataModelSchema":{"data":{"weather":{"current":{"temperatureText":{"type":"string","description":"当前温度展示文本，可能包含负号和摄氏度单位","sampleValue":"26℃"},"condition":{"type":"string","description":"当前天气现象","sampleValue":"小雨"}}},"phoneBattery":{"batterySOCText":{"type":"string","description":"手机剩余电量百分比文本","sampleValue":"68%"},"chargingStatusDesc":{"type":"string","description":"当前充电状态描述","sampleValue":"充电中"}}}},"assetCandidates":[{"src":"resources/base/media/drop_fill.svg","description":"单色可染色的面性水滴图标，适合雨天和降雨提示"},{"src":"resources/base/media/location_north_up_right_fill.svg","description":"单色可染色的方向导航图标，适合地图导航和路线规划"}]}
```
### assistant
```genui
["root","Column",{"width":160,"height":160,"padding":12,"borderRadius":20,"clip":true,"design":"Surface.trafficStrongDark","justifyContent":"start","itemMargin":8},["title_area","content_area","action_area"]]
["title_area","Row",{"width":136,"height":20,"justifyContent":"spaceBetween","alignItems":"center","flexShrink":0},["title_text","weather_icon"]]
["title_text","Text",{"content":"雨天出行提醒","design":"card-title","width":108,"fontColor":"#FFFFFFFF","maxLines":1,"textOverflow":"clip"}]
["weather_icon","Image",{"src":"resources/base/media/drop_fill.svg","width":20,"height":20,"objectFit":"contain","fillColor":"#FFFFFFFF","flexShrink":0}]
["content_area","Column",{"width":136,"layoutWeight":1,"justifyContent":"center","alignItems":"start","itemMargin":8,"flexShrink":1},["temperature_text","condition_text"]]
["temperature_text","Text",{"content":{"path":"/data/weather/current/temperatureText"},"design":"hero-value","width":136,"fontColor":"#FFFFFFFF","maxLines":1,"textOverflow":"clip"}]
["condition_text","Text",{"content":{"path":"/data/weather/current/condition"},"design":"body-m","width":136,"fontColor":"#99FFFFFF","maxLines":1,"textOverflow":"clip"}]
["action_area","Column",{"width":"matchParent","height":36,"flexShrink":0},["cta"]]
["cta","ActionUnit",{"state":"capsule","label":"导航回家","onClick":[{"call":"clickToIntent","args":{"intentName":"StartNavigate","params":{"dstLocation":{"location":"home","latitude":"","longitude":""}}}}],"actionSurface":"white","actionInk":"#FF467794","flexShrink":0}]
["/data/weather/current/temperatureText","26℃"]
["/data/weather/current/condition","小雨"]
```
