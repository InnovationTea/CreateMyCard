# Design Compact Reference Templates 2x4

这些模板由服务端在通用生成前按当前 TaskSpec 自动检索。它们是风格和布局参考库，不是 PROMPT 系统规则。

# ==================== BEGIN MAINTAINABLE FEW-SHOT ====================
以下示例可由维护者整体替换。规则正文优先于示例。每组 assistant 输出都必须保持一个 `genui` 代码块，代码块内只包含当前 Design Compact DSL JSONL。示例只学习布局骨架、尺寸、对齐、背景、按钮和高级组件规格；真实输出时必须替换成当前 TaskSpec 里的真实 path、icon 和 onClick。

## 示例一：meeting-timeline，纯日程详情，无 action
### user
```json
{"userQuery":"生成meeting-timeline，纯日程详情，无 action","size":"2x4","eventCandidates":[],"dataModelSchema":{},"assetCandidates":[]}
```
### assistant
```genui
["root","Stack",{"width":320,"height":160,"borderRadius":20,"clip":true,"linearGradient":{"angle":180,"colors":[["#FFEDE4FF",0],["#FFF8F4FF",0.58],["#FFFFFFFF",1]]}},["content_root"]]
["content_root","Column",{"width":"matchParent","height":"matchParent","padding":16,"itemMargin":8,"justifyContent":"start","alignItems":"center"},["title_area","content_area"]]
["title_area","Row",{"width":288,"height":24,"justifyContent":"spaceBetween","alignItems":"center","flexShrink":0},["title_text","date_badge"]]
["title_text","Text",{"content":"日程安排","width":220,"height":20,"fontSize":12,"fontWeight":700,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"}]
["date_badge","Text",{"content":"今","width":22,"height":20,"fontSize":12,"fontWeight":700,"fontColor":"#E5000000","maxLines":1,"textOverflow":"clip","textAlign":"center"}]
["content_area","Row",{"width":288,"height":72,"itemMargin":10,"justifyContent":"start","alignItems":"start","flexShrink":0},["event_timeline","event_texts"]]
["event_timeline","TimelineUnit",{"height":72,"color":"#FFE84026","lineColor":"#1A000000","flexShrink":0}]
["event_texts","Column",{"width":262,"height":72,"itemMargin":4,"justifyContent":"start","alignItems":"start","flexShrink":1},["event_title","event_time","event_place"]]
["event_title","Text",{"content":"需求评审会","width":262,"height":28,"fontSize":20,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"}]
["event_time","Text",{"content":"14:00 - 15:30","width":262,"height":20,"fontSize":16,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}]
["event_place","Text",{"content":"会议室 A302","width":262,"height":16,"fontSize":12,"fontWeight":400,"fontColor":"#66000000","maxLines":1,"textOverflow":"ellipsis"}]
```

## 示例二：todo-list，三条待办清单
### user
```json
{"userQuery":"生成todo-list，三条待办清单","size":"2x4","eventCandidates":[],"dataModelSchema":{},"assetCandidates":[{"src":"resources/base/media/icon_task.svg","description":"当前示例使用的本地素材"}]}
```
### assistant
```genui
["root","Stack",{"width":320,"height":160,"borderRadius":20,"clip":true,"linearGradient":{"angle":180,"colors":[["#FFFFF1C7",0],["#FFFFF9E6",0.58],["#FFFFFFFF",1]]}},["content_root"]]
["content_root","Column",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":8,"justifyContent":"start","alignItems":"center"},["title_area","todo_list"]]
["title_area","Row",{"width":296,"height":24,"justifyContent":"spaceBetween","alignItems":"center","flexShrink":0},["title_text","title_icon"]]
["title_text","Text",{"content":"待处理事项","width":240,"height":20,"fontSize":12,"fontWeight":700,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
["title_icon","Image",{"src":"resources/base/media/icon_task.svg","width":24,"height":24,"objectFit":"contain","flexShrink":0}]
["todo_list","Column",{"width":296,"height":112,"itemMargin":8,"justifyContent":"start","alignItems":"center","flexShrink":0},["todo_item_1","todo_item_2","todo_item_3"]]
["todo_item_1","Row",{"width":296,"height":32,"padding":{"left":10,"right":12,"top":0,"bottom":0},"borderRadius":8,"backgroundColor":"#FFF5F1E6","itemMargin":12,"alignItems":"center","flexShrink":0},["check_1","todo_text_1"]]
["check_1","Text",{"content":"","width":14,"height":14,"borderRadius":7,"borderWidth":1,"borderColor":"#99000000","backgroundColor":"#00FFFFFF","flexShrink":0}]
["todo_text_1","Text",{"content":"项目阶段性汇报","width":240,"height":20,"fontSize":14,"fontWeight":700,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"}]
["todo_item_2","Row",{"width":296,"height":32,"padding":{"left":10,"right":12,"top":0,"bottom":0},"borderRadius":8,"backgroundColor":"#FFF5F1E6","itemMargin":12,"alignItems":"center","flexShrink":0},["check_2","todo_text_2"]]
["check_2","Text",{"content":"","width":14,"height":14,"borderRadius":7,"borderWidth":1,"borderColor":"#99000000","backgroundColor":"#00FFFFFF","flexShrink":0}]
["todo_text_2","Text",{"content":"确认Q3设计需求","width":240,"height":20,"fontSize":14,"fontWeight":700,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"}]
["todo_item_3","Row",{"width":296,"height":32,"padding":{"left":10,"right":12,"top":0,"bottom":0},"borderRadius":8,"backgroundColor":"#FFF5F1E6","itemMargin":12,"alignItems":"center","flexShrink":0},["check_3","todo_text_3"]]
["check_3","Text",{"content":"","width":14,"height":14,"borderRadius":7,"borderWidth":1,"borderColor":"#99000000","backgroundColor":"#00FFFFFF","flexShrink":0}]
["todo_text_3","Text",{"content":"申请下周出差","width":240,"height":20,"fontSize":14,"fontWeight":700,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"}]
```

## 示例三：meeting-timeline，日程 + 左下胶囊按钮
### user
```json
{"userQuery":"生成meeting-timeline，日程 + 左下胶囊按钮","size":"2x4","eventCandidates":[],"dataModelSchema":{},"assetCandidates":[{"src":"resources/base/media/calendar_fill.svg","description":"当前示例使用的本地素材"}]}
```
### assistant
```genui
["root","Stack",{"width":320,"height":160,"borderRadius":20,"clip":true,"linearGradient":{"angle":180,"colors":[["#FFEDE4FF",0],["#FFF8F4FF",0.58],["#FFFFFFFF",1]]}},["content_root"]]
["content_root","Column",{"width":"matchParent","height":"matchParent","padding":16,"itemMargin":4,"justifyContent":"start","alignItems":"start"},["title_area","content_area","action_area"]]
["title_area","Row",{"width":288,"height":24,"justifyContent":"spaceBetween","alignItems":"center","flexShrink":0},["title_text","title_icon"]]
["title_text","Text",{"content":"下一个日程","width":238,"height":20,"fontSize":12,"fontWeight":700,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
["title_icon","Image",{"src":"resources/base/media/calendar_fill.svg","width":24,"height":24,"objectFit":"contain","flexShrink":0}]
["content_area","Row",{"width":288,"height":64,"itemMargin":10,"justifyContent":"start","alignItems":"start","flexShrink":0},["event_timeline","event_texts"]]
["event_timeline","TimelineUnit",{"height":64,"color":"#FFE84026","lineColor":"#1A000000","flexShrink":0}]
["event_texts","Column",{"width":262,"height":64,"itemMargin":4,"justifyContent":"start","alignItems":"start","flexShrink":1},["event_title","event_time","event_place"]]
["event_title","Text",{"content":"需求评审会","width":262,"height":26,"fontSize":20,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"}]
["event_time","Text",{"content":"14:00 - 15:30","width":262,"height":18,"fontSize":14,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}]
["event_place","Text",{"content":"会议室 A302","width":262,"height":16,"fontSize":12,"fontWeight":400,"fontColor":"#66000000","maxLines":1,"textOverflow":"ellipsis"}]
["action_area","Column",{"width":136,"height":32,"flexShrink":0},["cta"]]
["cta","ActionUnit",{"state":"capsule","label":"专注模式","onClick":[...],"actionInk":"#FF8B5CF6","actionSurface":"#1A8B5CF6","flexShrink":0}]
```

## 示例四：large-ring，大环 + 右侧说明
### user
```json
{"userQuery":"生成large-ring，大环 + 右侧说明","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"memory":{"usedPercent":{"type":"number","description":"示例字段","sampleValue":43.75}}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Stack",{"width":320,"height":160,"borderRadius":20,"clip":true,"linearGradient":{"angle":180,"colors":[["#FFFFE4D2",0],["#FFFFF5EC",0.58],["#FFFFFFFF",1]]}},["content_root"]]
["content_root","Row",{"width":"matchParent","height":"matchParent","padding":16,"itemMargin":16,"alignItems":"center","justifyContent":"start"},["visual_area","info_area"]]
["visual_area","Column",{"width":112,"height":128,"justifyContent":"center","alignItems":"center","flexShrink":0},["memory_ring"]]
["memory_ring","RingUnit",{"state":"center-text","size":92,"value":{"path":"/data/memory/usedPercent"},"total":100,"reading":{"path":"/data/memory/usedPercent","unit":"%"},"color":"orange","flexShrink":0}]
["info_area","Column",{"width":160,"height":100,"itemMargin":4,"justifyContent":"center","alignItems":"start","flexShrink":1},["info_title","info_value","info_desc"]]
["info_title","Text",{"content":"可用内存","width":160,"height":22,"fontSize":16,"fontWeight":700,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"}]
["info_value","Text",{"content":"4.50 GB","width":160,"height":22,"fontSize":14,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
["info_desc","Text",{"content":"总容量 8.00 GB","width":160,"height":18,"fontSize":12,"fontWeight":400,"fontColor":"#66000000","maxLines":1,"textOverflow":"ellipsis"}]
["/data/memory/usedPercent",43.75]
```

## 示例五：strong-focus，橙色强背景 + 左进度右计划
### user
```json
{"userQuery":"生成strong-focus，橙色强背景 + 左进度右计划","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"countdown":{"days":{"type":"integer","description":"示例字段","sampleValue":7}}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Stack",{"width":320,"height":160,"borderRadius":20,"clip":true,"linearGradient":{"angle":180,"colors":[["#FFFF6A12",0],["#FFFF8616",0.55],["#FFFFA31A",1]]}},["content_root"]]
["content_root","Row",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":12,"justifyContent":"start","alignItems":"center"},["focus_area","plan_panel"]]
["focus_area","Column",{"width":132,"height":136,"itemMargin":6,"justifyContent":"start","alignItems":"start","flexShrink":0},["title_text","days_row","distance_progress","range_row"]]
["title_text","Text",{"content":"距越野赛","width":132,"height":20,"fontSize":12,"fontWeight":700,"fontColor":"#FFFFFFFF","maxLines":1,"textOverflow":"ellipsis"}]
["days_row","Row",{"width":132,"height":48,"itemMargin":4,"alignItems":"bottom","flexShrink":0},["days_text","days_unit"]]
["days_text","Text",{"content":{"path":"/data/countdown/days"},"width":64,"height":48,"fontSize":44,"fontWeight":800,"fontColor":"#FFFFFFFF","maxLines":1,"textOverflow":"clip"}]
["days_unit","Text",{"content":"天剩余","width":60,"height":20,"fontSize":12,"fontWeight":400,"fontColor":"#CCFFFFFF","maxLines":1,"textOverflow":"ellipsis"}]
["distance_progress","ProgressUnit",{"state":"bar","value":32,"total":103,"color":"#FFFFFFFF","flexShrink":0}]
["range_row","Text",{"content":"0km | 103km","width":132,"height":16,"fontSize":10,"fontWeight":500,"fontColor":"#CCFFFFFF","maxLines":1,"textOverflow":"clip"}]
["plan_panel","Column",{"width":152,"height":112,"padding":12,"borderRadius":12,"backgroundColor":"#26FFFFFF","itemMargin":8,"justifyContent":"center","alignItems":"start","flexShrink":0},["plan_title","plan_desc"]]
["plan_title","Text",{"content":"越野赛训练计划","width":128,"height":22,"fontSize":16,"fontWeight":700,"fontColor":"#FFFFFFFF","maxLines":1,"textOverflow":"ellipsis"}]
["plan_desc","Text",{"content":"从本周一开始每天晨跑，配速训练30分钟以上","width":128,"height":54,"fontSize":12,"fontWeight":400,"fontColor":"#CCFFFFFF","maxLines":3,"textOverflow":"ellipsis"}]
["/data/countdown/days",7]
```

## 示例六：split-two-column，左主信息 + 右双卡片
### user
```json
{"userQuery":"生成split-two-column，左主信息 + 右双卡片","size":"2x4","eventCandidates":[],"dataModelSchema":{},"assetCandidates":[{"src":"resources/base/media/calendar_fill.svg","description":"当前示例使用的本地素材"}]}
```
### assistant
```genui
["root","Stack",{"width":320,"height":160,"borderRadius":20,"clip":true,"linearGradient":{"angle":180,"colors":[["#FFFFE2E9",0],["#FFFFF4F7",0.58],["#FFFFFFFF",1]]}},["content_root"]]
["content_root","Row",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":12,"justifyContent":"start","alignItems":"center"},["left_col","right_col"]]
["left_col","Column",{"width":190,"height":136,"itemMargin":8,"justifyContent":"start","alignItems":"start","flexShrink":0},["title_area","main_value","main_desc"]]
["title_area","Row",{"width":190,"height":24,"justifyContent":"spaceBetween","alignItems":"center","flexShrink":0},["title_text","title_icon"]]
["title_text","Text",{"content":"8月","width":150,"height":20,"fontSize":12,"fontWeight":700,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"}]
["title_icon","Image",{"src":"resources/base/media/calendar_fill.svg","width":24,"height":24,"objectFit":"contain","flexShrink":0}]
["main_value","Text",{"content":"27","width":190,"height":44,"fontSize":40,"fontWeight":800,"fontColor":"#FFE84B3C","maxLines":1,"textOverflow":"clip"}]
["main_desc","Text",{"content":"妈妈生日 | 农历七月二日","width":190,"height":40,"fontSize":14,"fontWeight":400,"fontColor":"#99000000","maxLines":2,"textOverflow":"ellipsis"}]
["right_col","Column",{"width":86,"height":112,"itemMargin":8,"justifyContent":"center","alignItems":"center","flexShrink":0},["side_card_1","side_card_2"]]
["side_card_1","Column",{"width":86,"height":48,"borderRadius":12,"backgroundColor":"#FFFBE7EC","padding":8,"itemMargin":2,"justifyContent":"center","alignItems":"start"},["side_title_1","side_time_1"]]
["side_title_1","Text",{"content":"取妈妈的蛋糕","width":70,"height":18,"fontSize":12,"fontWeight":700,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"}]
["side_time_1","Text",{"content":"12:00","width":70,"height":16,"fontSize":12,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}]
["side_card_2","Column",{"width":86,"height":48,"borderRadius":12,"backgroundColor":"#FFFBE7EC","padding":8,"itemMargin":2,"justifyContent":"center","alignItems":"start"},["side_title_2","side_time_2"]]
["side_title_2","Text",{"content":"晚上聚餐","width":70,"height":18,"fontSize":12,"fontWeight":700,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"}]
["side_time_2","Text",{"content":"19:00","width":70,"height":16,"fontSize":12,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}]
```

## 示例七：primary-action-pair，左主状态 + 右双操作
### user
```json
{"userQuery":"生成primary-action-pair，左主状态 + 右双操作","size":"2x4","eventCandidates":[],"dataModelSchema":{},"assetCandidates":[{"src":"resources/base/media/location_north_up_fill.svg","description":"当前示例使用的本地素材"},{"src":"resources/base/media/lightbulb_fill.svg","description":"当前示例使用的本地素材"}]}
```
### assistant
```genui
["root","Stack",{"width":320,"height":160,"borderRadius":20,"clip":true,"linearGradient":{"angle":180,"colors":[["#FFDDF5E8",0],["#FFF1FAF5",0.58],["#FFFFFFFF",1]]}},["content_root"]]
["content_root","Row",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":12,"justifyContent":"start","alignItems":"center"},["primary_panel","action_group"]]
["primary_panel","Column",{"width":132,"height":136,"itemMargin":8,"justifyContent":"start","alignItems":"start","flexShrink":0},["title_text","temperature","home_status"]]
["title_text","Text",{"content":"智能我家","width":132,"height":20,"fontSize":12,"fontWeight":700,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"}]
["temperature","Text",{"content":"26°C","width":132,"height":44,"fontSize":36,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textOverflow":"clip"}]
["home_status","Text",{"content":"空调关闭 | 灯光关闭","width":132,"height":40,"fontSize":12,"fontWeight":400,"fontColor":"#99000000","maxLines":2,"textOverflow":"ellipsis"}]
["action_group","Row",{"width":152,"height":112,"itemMargin":8,"justifyContent":"start","alignItems":"center","flexShrink":0},["navigate_action","light_action"]]
["navigate_action","ActionUnit",{"state":"tile","label":"开始导航","icon":"resources/base/media/location_north_up_fill.svg","width":72,"height":112,"onClick":[...],"actionInk":"#FF18B87A","actionSurface":"#FFE5F4EC","flexShrink":0}]
["light_action","ActionUnit",{"state":"tile","label":"打开灯光","icon":"resources/base/media/lightbulb_fill.svg","width":72,"height":112,"onClick":[...],"actionInk":"#FF18B87A","actionSurface":"#FFE5F4EC","flexShrink":0}]
```

## 示例八：linear-progress，进度 + 双详情背板
### user
```json
{"userQuery":"生成linear-progress，进度 + 双详情背板","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"storage":{"usedPercent":{"type":"integer","description":"示例字段","sampleValue":81}}}},"assetCandidates":[{"src":"resources/base/media/storage_fill.svg","description":"当前示例使用的本地素材"}]}
```
### assistant
```genui
["root","Stack",{"width":320,"height":160,"borderRadius":20,"clip":true,"linearGradient":{"angle":180,"colors":[["#FFE1ECFF",0],["#FFF3F7FF",0.58],["#FFFFFFFF",1]]}},["content_root"]]
["content_root","Column",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":8,"justifyContent":"start","alignItems":"start"},["title_area","storage_progress","detail_row"]]
["title_area","Row",{"width":296,"height":24,"justifyContent":"spaceBetween","alignItems":"center","flexShrink":0},["title_text","title_icon"]]
["title_text","Text",{"content":"存储空间监控","width":238,"height":20,"fontSize":12,"fontWeight":700,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
["title_icon","Image",{"src":"resources/base/media/storage_fill.svg","width":24,"height":24,"objectFit":"contain","flexShrink":0}]
["storage_progress","ProgressUnit",{"state":"plain","label":"手机存储空间","value":{"path":"/data/storage/usedPercent"},"total":100,"color":"blue","flexShrink":0}]
["detail_row","Row",{"width":296,"height":48,"itemMargin":8,"justifyContent":"start","alignItems":"center","flexShrink":0},["system_card","other_card"]]
["system_card","Column",{"width":144,"height":48,"padding":8,"borderRadius":10,"backgroundColor":"#FFE8EEF7","itemMargin":2,"justifyContent":"center","alignItems":"start","flexShrink":0},["system_label","system_value"]]
["system_label","Text",{"content":"系统数据","width":128,"height":18,"fontSize":12,"fontWeight":700,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"}]
["system_value","Text",{"content":"18.92GB","width":128,"height":16,"fontSize":10,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}]
["other_card","Column",{"width":144,"height":48,"padding":8,"borderRadius":10,"backgroundColor":"#FFE8EEF7","itemMargin":2,"justifyContent":"center","alignItems":"start","flexShrink":0},["other_label","other_value"]]
["other_label","Text",{"content":"其它数据","width":128,"height":18,"fontSize":12,"fontWeight":700,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"}]
["other_value","Text",{"content":"23.35GB","width":128,"height":16,"fontSize":10,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}]
["/data/storage/usedPercent",81]
```

## 示例九：metric-series，三项同构天气
### user
```json
{"userQuery":"生成metric-series，三项同构天气","size":"2x4","eventCandidates":[],"dataModelSchema":{},"assetCandidates":[{"src":"resources/base/media/sun_cloud_fill.svg","description":"当前示例使用的本地素材"}]}
```
### assistant
```genui
["root","Stack",{"width":320,"height":160,"borderRadius":20,"clip":true,"linearGradient":{"angle":180,"colors":[["#FFFFF1C7",0],["#FFFFF9E6",0.58],["#FFFFFFFF",1]]}},["content_root"]]
["content_root","Column",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":8,"justifyContent":"start","alignItems":"start"},["title_text","metrics_row"]]
["title_text","Text",{"content":"常用天气","width":296,"height":20,"fontSize":12,"fontWeight":700,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis","flexShrink":0}]
["metrics_row","Row",{"width":296,"height":108,"itemMargin":8,"justifyContent":"start","alignItems":"center","flexShrink":0},["city_card_1","city_card_2","city_card_3"]]
["city_card_1","Column",{"width":93,"height":108,"padding":8,"borderRadius":12,"backgroundColor":"#FFF5F1E6","itemMargin":4,"justifyContent":"center","alignItems":"start","flexShrink":0},["weather_icon_1","temperature_1","city_1"]]
["weather_icon_1","Image",{"src":"resources/base/media/sun_cloud_fill.svg","width":24,"height":24,"objectFit":"contain","flexShrink":0}]
["temperature_1","Text",{"content":"38°","width":77,"height":36,"fontSize":32,"fontWeight":800,"fontColor":"#FF355A99","maxLines":1,"textOverflow":"clip"}]
["city_1","Text",{"content":"深圳 | 多云","width":77,"height":18,"fontSize":12,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
["city_card_2","Column",{"width":93,"height":108,"padding":8,"borderRadius":12,"backgroundColor":"#FFF5F1E6","itemMargin":4,"justifyContent":"center","alignItems":"start","flexShrink":0},["weather_icon_2","temperature_2","city_2"]]
["weather_icon_2","Image",{"src":"resources/base/media/sun_cloud_fill.svg","width":24,"height":24,"objectFit":"contain","flexShrink":0}]
["temperature_2","Text",{"content":"35°","width":77,"height":36,"fontSize":32,"fontWeight":800,"fontColor":"#FF355A99","maxLines":1,"textOverflow":"clip"}]
["city_2","Text",{"content":"南京 | 多云","width":77,"height":18,"fontSize":12,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
["city_card_3","Column",{"width":93,"height":108,"padding":8,"borderRadius":12,"backgroundColor":"#FFF5F1E6","itemMargin":4,"justifyContent":"center","alignItems":"start","flexShrink":0},["weather_icon_3","temperature_3","city_3"]]
["weather_icon_3","Image",{"src":"resources/base/media/sun_cloud_fill.svg","width":24,"height":24,"objectFit":"contain","flexShrink":0}]
["temperature_3","Text",{"content":"27°","width":77,"height":36,"fontSize":32,"fontWeight":800,"fontColor":"#FF355A99","maxLines":1,"textOverflow":"clip"}]
["city_3","Text",{"content":"新疆 | 多云","width":77,"height":18,"fontSize":12,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
```

## 示例十：quad-rings，四个设备电量/占比
### user
```json
{"userQuery":"生成quad-rings，四个设备电量/占比","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"device":{"phoneBattery":{"type":"integer","description":"示例字段","sampleValue":20},"phoneBatteryText":{"type":"string","description":"示例字段","sampleValue":"20%"},"earbudBattery":{"type":"integer","description":"示例字段","sampleValue":80},"earbudBatteryText":{"type":"string","description":"示例字段","sampleValue":"80%"},"boxBattery":{"type":"integer","description":"示例字段","sampleValue":76},"boxBatteryText":{"type":"string","description":"示例字段","sampleValue":"76%"},"watchBattery":{"type":"integer","description":"示例字段","sampleValue":74},"watchBatteryText":{"type":"string","description":"示例字段","sampleValue":"74%"}}}},"assetCandidates":[{"src":"resources/base/media/bolt_fill.svg","description":"当前示例使用的本地素材"},{"src":"resources/base/media/earbuds_fill.svg","description":"当前示例使用的本地素材"},{"src":"resources/base/media/earphone_case_fill.svg","description":"当前示例使用的本地素材"},{"src":"resources/base/media/watch_fill.svg","description":"当前示例使用的本地素材"}]}
```
### assistant
```genui
["root","Stack",{"width":320,"height":160,"borderRadius":20,"clip":true,"linearGradient":{"angle":180,"colors":[["#FFDDF5E8",0],["#FFF1FAF5",0.58],["#FFFFFFFF",1]]}},["content_root"]]
["content_root","Column",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":10,"justifyContent":"start","alignItems":"center"},["title_text","battery_grid"]]
["title_text","Text",{"content":"电量监控","width":296,"height":20,"fontSize":12,"fontWeight":700,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis","flexShrink":0}]
["battery_grid","Column",{"width":296,"height":104,"itemMargin":8,"justifyContent":"start","alignItems":"center","flexShrink":0},["grid_row_1","grid_row_2"]]
["grid_row_1","Row",{"width":296,"height":48,"itemMargin":8,"justifyContent":"spaceBetween","alignItems":"center","flexShrink":0},["battery_card_1","battery_card_2"]]
["grid_row_2","Row",{"width":296,"height":48,"itemMargin":8,"justifyContent":"spaceBetween","alignItems":"center","flexShrink":0},["battery_card_3","battery_card_4"]]
["battery_card_1","Row",{"width":144,"height":48,"padding":{"left":8,"right":10,"top":4,"bottom":4},"borderRadius":10,"backgroundColor":"#FFE5F4EC","itemMargin":10,"alignItems":"center","flexShrink":0},["ring_1","battery_texts_1"]]
["ring_1","RingUnit",{"state":"center-icon","size":40,"value":{"path":"/data/device/phoneBattery"},"total":100,"centerIcon":"resources/base/media/bolt_fill.svg","color":"red","flexShrink":0}]
["battery_texts_1","Column",{"width":70,"height":38,"itemMargin":2,"justifyContent":"center","alignItems":"start","flexShrink":1},["percent_text_1","status_text_1"]]
["percent_text_1","Text",{"content":{"path":"/data/device/phoneBatteryText"},"width":70,"height":22,"fontSize":18,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textOverflow":"clip"}]
["status_text_1","Text",{"content":"手机电量","width":70,"height":16,"fontSize":12,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
["battery_card_2","Row",{"width":144,"height":48,"padding":{"left":8,"right":10,"top":4,"bottom":4},"borderRadius":10,"backgroundColor":"#FFE5F4EC","itemMargin":10,"alignItems":"center","flexShrink":0},["ring_2","battery_texts_2"]]
["ring_2","RingUnit",{"state":"center-icon","size":40,"value":{"path":"/data/device/earbudBattery"},"total":100,"centerIcon":"resources/base/media/earbuds_fill.svg","color":"green","flexShrink":0}]
["battery_texts_2","Column",{"width":70,"height":38,"itemMargin":2,"justifyContent":"center","alignItems":"start","flexShrink":1},["percent_text_2","status_text_2"]]
["percent_text_2","Text",{"content":{"path":"/data/device/earbudBatteryText"},"width":70,"height":22,"fontSize":18,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textOverflow":"clip"}]
["status_text_2","Text",{"content":"耳机电量","width":70,"height":16,"fontSize":12,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
["battery_card_3","Row",{"width":144,"height":48,"padding":{"left":8,"right":10,"top":4,"bottom":4},"borderRadius":10,"backgroundColor":"#FFE5F4EC","itemMargin":10,"alignItems":"center","flexShrink":0},["ring_3","battery_texts_3"]]
["ring_3","RingUnit",{"state":"center-icon","size":40,"value":{"path":"/data/device/boxBattery"},"total":100,"centerIcon":"resources/base/media/earphone_case_fill.svg","color":"blue","flexShrink":0}]
["battery_texts_3","Column",{"width":70,"height":38,"itemMargin":2,"justifyContent":"center","alignItems":"start","flexShrink":1},["percent_text_3","status_text_3"]]
["percent_text_3","Text",{"content":{"path":"/data/device/boxBatteryText"},"width":70,"height":22,"fontSize":18,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textOverflow":"clip"}]
["status_text_3","Text",{"content":"盒电量","width":70,"height":16,"fontSize":12,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
["battery_card_4","Row",{"width":144,"height":48,"padding":{"left":8,"right":10,"top":4,"bottom":4},"borderRadius":10,"backgroundColor":"#FFE5F4EC","itemMargin":10,"alignItems":"center","flexShrink":0},["ring_4","battery_texts_4"]]
["ring_4","RingUnit",{"state":"center-icon","size":40,"value":{"path":"/data/device/watchBattery"},"total":100,"centerIcon":"resources/base/media/watch_fill.svg","color":"orange","flexShrink":0}]
["battery_texts_4","Column",{"width":70,"height":38,"itemMargin":2,"justifyContent":"center","alignItems":"start","flexShrink":1},["percent_text_4","status_text_4"]]
["percent_text_4","Text",{"content":{"path":"/data/device/watchBatteryText"},"width":70,"height":22,"fontSize":18,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textOverflow":"clip"}]
["status_text_4","Text",{"content":"手表电量","width":70,"height":16,"fontSize":12,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
["/data/device/phoneBattery",20]
["/data/device/phoneBatteryText","20%"]
["/data/device/earbudBattery",80]
["/data/device/earbudBatteryText","80%"]
["/data/device/boxBattery",76]
["/data/device/boxBatteryText","76%"]
["/data/device/watchBattery",74]
["/data/device/watchBatteryText","74%"]
```

# ===================== END MAINTAINABLE FEW-SHOT =====================
