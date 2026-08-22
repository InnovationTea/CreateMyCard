# 2x4 金标卡片 Few-shot 集（8 张）

从 `few-shot-2x4.md` 抽取的 2026-08-21 校准定稿集：A02/A04/A05/A06/A07/A08/A09/A10。

校准依据（与 2x2 金标集同一套规则，2x4 侧补充）：

1. `Design-guide/DESIGN.md` 按钮配对：浅色遮罩卡 = primaryHue 10% 底（19 alpha）+ 100% 前景；彩色渐变卡 = 白底 + primaryHue。
2. 色板锚定：confirm 绿 #64BB5C、warning 红 #E84026、低电量/橙 #F9A01E、brand/进度蓝 #0A59F7、天气蓝 #317AF7；RingUnit/ProgressUnit 语义色经转换器映射到色板（green→#64BB5C、red→#E84026、orange→#F9A01E、blue→#317AF7、progress blue→#0A59F7）。
3. 强色卡（sports）用注册渐变 #ED6F21→#F9A01E；装饰与数据可视化前景 #FFFFFFFF。
4. 进度/环底槽中性；文字显式 fontColor；混排行小字单位补 `padding:{"bottom":N}` 基线补偿（44/12 组合 N=6）。
5. 面性图标（sun_max_fill）+ 场景色染色。

渲染产物对照：`render/2x4-v2/`；渲染 jsonl 需注入 `{"__viewport__":"2x4"}`。编号与主文件一致，改动先改主文件再同步本文件。

## 渲染依赖（DSL 无法表达，需转换器支持）

以下效果依赖 `compact_dsl_a2ui_converter_2x4.py` 的配套改动；旧版转换器的退化行为：

1. **条形图条厚 8vp**：ProgressUnit 的 `strokeWidth` 由转换器 `_linear_progress` 固定输出；旧版（无 strokeWidth）实际条厚 4vp（协议默认值），DSL 写 strokeWidth 会被旧版忽略。
2. **环内 icon 二级色与尺寸**：RingUnit centerIcon 的 `fillColor:#99000000`（icon_secondary）与 `size*0.4`（40 环→16×16）由转换器注入，DSL 无对应属性；旧版 icon 为素材默认色、尺寸偏大（环径一半）。
3. **tile 高度 115**：金标 tc-H2-H2 变体 tile 为 68×115；旧版转换器钳制上限 112（退化 3vp，可接受）。
4. 语义色已改为 hex 直写（可移植）；若仍写 `green/red/orange/blue`，颜色取决于转换器映射表版本。

素材依赖：`sun_max_fill.svg`、`icon_earphone.svg` 等需存在于渲染工程 media 库（部分工程仅有 .png 版本会导致图标空白）。

---

## 示例二（2x4-A02）：todo-list，三条待办清单
### user
```json
{"userQuery":"生成todo-list，三条待办清单","size":"2x4","eventCandidates":[],"dataModelSchema":{},"assetCandidates":[{"src":"resources/base/media/checkmark_calendar_fill.svg","description":"当前示例使用的本地素材"}]}
```
### assistant
```genui
["root","Stack",{"width":320,"height":160,"borderRadius":20,"clip":true,"linearGradient":{"angle":180,"colors":[["#FFFFF1C7",0],["#FFFFF9E6",0.58],["#FFFFFFFF",1]]}},["content_root"]]
["content_root","Column",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":4,"justifyContent":"start","alignItems":"start"},["title_area","todo_list"]]
["title_area","Row",{"width":296,"height":17,"justifyContent":"spaceBetween","alignItems":"center","flexShrink":0},["title_text","title_icon"]]
["title_text","Text",{"content":"待处理事项","width":240,"height":17,"fontSize":12,"fontWeight":700,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
["title_icon","Image",{"src":"resources/base/media/checkmark_calendar_fill.svg","width":16,"height":16,"objectFit":"contain","flexShrink":0}]
["todo_list","Column",{"width":296,"height":115,"itemMargin":8,"justifyContent":"start","alignItems":"center","flexShrink":0},["todo_item_1","todo_item_2","todo_item_3"]]
["todo_item_1","Row",{"width":296,"height":33,"padding":{"left":10,"right":12,"top":0,"bottom":0},"borderRadius":8,"backgroundColor":"#0C000000","itemMargin":12,"alignItems":"center","flexShrink":0},["check_1","todo_text_1"]]
["check_1","Text",{"content":"","width":14,"height":14,"borderRadius":7,"borderWidth":1,"borderColor":"#99000000","backgroundColor":"#00FFFFFF","flexShrink":0}]
["todo_text_1","Text",{"content":"项目阶段性汇报","width":240,"height":20,"fontSize":12,"fontWeight":400,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"}]
["todo_item_2","Row",{"width":296,"height":33,"padding":{"left":10,"right":12,"top":0,"bottom":0},"borderRadius":8,"backgroundColor":"#0C000000","itemMargin":12,"alignItems":"center","flexShrink":0},["check_2","todo_text_2"]]
["check_2","Text",{"content":"","width":14,"height":14,"borderRadius":7,"borderWidth":1,"borderColor":"#99000000","backgroundColor":"#00FFFFFF","flexShrink":0}]
["todo_text_2","Text",{"content":"确认Q3设计需求","width":240,"height":20,"fontSize":12,"fontWeight":400,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"}]
["todo_item_3","Row",{"width":296,"height":33,"padding":{"left":10,"right":12,"top":0,"bottom":0},"borderRadius":8,"backgroundColor":"#0C000000","itemMargin":12,"alignItems":"center","flexShrink":0},["check_3","todo_text_3"]]
["check_3","Text",{"content":"","width":14,"height":14,"borderRadius":7,"borderWidth":1,"borderColor":"#99000000","backgroundColor":"#00FFFFFF","flexShrink":0}]
["todo_text_3","Text",{"content":"申请下周出差","width":240,"height":20,"fontSize":12,"fontWeight":400,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"}]
```

## 示例四（2x4-A04）：large-ring，大环 + 右侧说明
### user
```json
{"userQuery":"生成large-ring，大环 + 右侧说明","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"memory":{"usedPercent":{"type":"number","description":"示例字段","sampleValue":43.75}}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Stack",{"width":320,"height":160,"borderRadius":20,"clip":true,"linearGradient":{"angle":180,"colors":[["#FFFFE4D2",0],["#FFFFF5EC",0.58],["#FFFFFFFF",1]]}},["content_root"]]
["content_root","Column",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":4,"justifyContent":"start","alignItems":"start"},["title_area","content_row"]]
["title_area","Row",{"width":296,"height":17,"justifyContent":"start","alignItems":"center","flexShrink":0},["title_text"]]
["title_text","Text",{"content":"内存使用","width":240,"height":17,"fontSize":12,"fontWeight":700,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
["content_row","Row",{"width":296,"height":115,"itemMargin":8,"justifyContent":"start","alignItems":"center","flexShrink":0},["ring_area","info_area"]]
["ring_area","Column",{"width":144,"height":115,"justifyContent":"center","alignItems":"center","flexShrink":0},["memory_ring"]]
["memory_ring","RingUnit",{"state":"center-text","size":92,"value":{"path":"/data/memory/usedPercent"},"total":100,"reading":{"path":"/data/memory/usedPercent","unit":"%"},"color":"#FFF9A01E","flexShrink":0}]
["info_area","Column",{"width":144,"height":115,"itemMargin":4,"justifyContent":"center","alignItems":"start","flexShrink":1},["info_title","info_value","info_desc"]]
["info_title","Text",{"content":"可用内存","width":144,"height":22,"fontSize":16,"fontWeight":700,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"}]
["info_value","Text",{"content":"4.50 GB","width":144,"height":22,"fontSize":14,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
["info_desc","Text",{"content":"总容量 8.00 GB","width":144,"height":18,"fontSize":12,"fontWeight":400,"fontColor":"#66000000","maxLines":1,"textOverflow":"ellipsis"}]
["/data/memory/usedPercent",43.75]
```

## 示例五（2x4-A05）：strong-focus，橙色强背景 + 左进度右计划
### user
```json
{"userQuery":"生成strong-focus，橙色强背景 + 左进度右计划","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"countdown":{"days":{"type":"integer","description":"示例字段","sampleValue":7}}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Stack",{"width":320,"height":160,"borderRadius":20,"clip":true,"linearGradient":{"angle":180,"colors":[["#FFED6F21",0],["#FFF9A01E",1]]}},["content_root"]]
["content_root","Column",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":4,"justifyContent":"start","alignItems":"start"},["title_area","content_row"]]
["title_area","Row",{"width":296,"height":17,"justifyContent":"start","alignItems":"center","flexShrink":0},["title_text"]]
["title_text","Text",{"content":"距越野赛","width":240,"height":17,"fontSize":12,"fontWeight":700,"fontColor":"#FFFFFFFF","maxLines":1,"textOverflow":"ellipsis"}]
["content_row","Row",{"width":296,"height":115,"itemMargin":8,"justifyContent":"start","alignItems":"center","flexShrink":0},["focus_area","plan_panel"]]
["focus_area","Column",{"width":144,"height":115,"itemMargin":6,"justifyContent":"center","alignItems":"start","flexShrink":0},["days_row","distance_progress","range_row"]]
["days_row","Row",{"width":144,"height":48,"itemMargin":4,"alignItems":"bottom","flexShrink":0},["days_text","days_unit"]]
["days_text","Text",{"content":{"path":"/data/countdown/days"},"height":48,"fontSize":44,"fontWeight":800,"fontColor":"#FFFFFFFF","maxLines":1,"textOverflow":"clip"}]
["days_unit","Text",{"content":"天剩余","width":60,"height":20,"fontSize":12,"fontWeight":400,"fontColor":"#CCFFFFFF","padding":{"bottom":6},"maxLines":1,"textOverflow":"ellipsis"}]
["distance_progress","ProgressUnit",{"state":"bar","value":32,"total":103,"color":"#FFFFFFFF","flexShrink":0}]
["range_row","Text",{"content":"0km | 103km","width":144,"height":16,"fontSize":10,"fontWeight":500,"fontColor":"#CCFFFFFF","maxLines":1,"textOverflow":"clip"}]
["plan_panel","Column",{"width":144,"height":115,"padding":12,"borderRadius":12,"backgroundColor":"#26FFFFFF","itemMargin":8,"justifyContent":"center","alignItems":"start","flexShrink":0},["plan_title","plan_desc"]]
["plan_title","Text",{"content":"越野赛训练计划","width":120,"height":22,"fontSize":16,"fontWeight":700,"fontColor":"#FFFFFFFF","maxLines":1,"textOverflow":"ellipsis"}]
["plan_desc","Text",{"content":"从本周一开始每天晨跑，配速训练30分钟以上","width":120,"height":54,"fontSize":12,"fontWeight":400,"fontColor":"#CCFFFFFF","maxLines":3,"textOverflow":"ellipsis"}]
["/data/countdown/days",7]
```

## 示例六（2x4-A06）：split-two-column，左主信息 + 右双卡片
### user
```json
{"userQuery":"生成split-two-column，左主信息 + 右双卡片","size":"2x4","eventCandidates":[],"dataModelSchema":{},"assetCandidates":[{"src":"resources/base/media/calendar_fill.svg","description":"当前示例使用的本地素材"}]}
```
### assistant
```genui
["root","Stack",{"width":320,"height":160,"borderRadius":20,"clip":true,"linearGradient":{"angle":180,"colors":[["#FFFFE2E9",0],["#FFFFF4F7",0.58],["#FFFFFFFF",1]]}},["content_root"]]
["content_root","Column",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":4,"justifyContent":"start","alignItems":"start"},["title_area","content_row"]]
["title_area","Row",{"width":296,"height":17,"justifyContent":"spaceBetween","alignItems":"center","flexShrink":0},["title_text","title_icon"]]
["title_text","Text",{"content":"8月","width":240,"height":17,"fontSize":12,"fontWeight":700,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
["title_icon","Image",{"src":"resources/base/media/calendar_fill.svg","width":16,"height":16,"objectFit":"contain","flexShrink":0}]
["content_row","Row",{"width":296,"height":115,"itemMargin":8,"justifyContent":"start","alignItems":"center","flexShrink":0},["left_col","right_col"]]
["left_col","Column",{"width":144,"height":115,"justifyContent":"spaceBetween","alignItems":"start","flexShrink":0},["main_value","desc_col"]]
["main_value","Text",{"content":"27","width":144,"height":44,"fontSize":40,"fontWeight":800,"fontColor":"#FFE84026","maxLines":1,"textOverflow":"clip"}]
["desc_col","Column",{"width":144,"itemMargin":2,"justifyContent":"end","alignItems":"start","flexShrink":0},["desc_1","desc_2"]]
["desc_1","Text",{"content":"妈妈生日","width":144,"height":20,"fontSize":14,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}]
["desc_2","Text",{"content":"农历七月二日","width":144,"height":18,"fontSize":12,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}]
["right_col","Column",{"width":144,"height":115,"itemMargin":8,"justifyContent":"center","alignItems":"center","flexShrink":0},["side_card_1","side_card_2"]]
["side_card_1","Column",{"width":144,"height":53.5,"borderRadius":12,"backgroundColor":"#0C000000","padding":8,"itemMargin":2,"justifyContent":"center","alignItems":"start","flexShrink":0},["side_title_1","side_time_1"]]
["side_title_1","Text",{"content":"取妈妈的蛋糕","width":128,"height":18,"fontSize":12,"fontWeight":700,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"}]
["side_time_1","Text",{"content":"12:00","width":128,"height":16,"fontSize":12,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}]
["side_card_2","Column",{"width":144,"height":53.5,"borderRadius":12,"backgroundColor":"#0C000000","padding":8,"itemMargin":2,"justifyContent":"center","alignItems":"start","flexShrink":0},["side_title_2","side_time_2"]]
["side_title_2","Text",{"content":"晚上聚餐","width":128,"height":18,"fontSize":12,"fontWeight":700,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"}]
["side_time_2","Text",{"content":"19:00","width":128,"height":16,"fontSize":12,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}]
```

## 示例七（2x4-A07）：primary-action-pair，左主状态 + 右双操作
### user
```json
{"userQuery":"生成primary-action-pair，左主状态 + 右双操作","size":"2x4","eventCandidates":[{"call":"clickToIntent","args":{"intentName":"StartNavigate","params":{"dstLocation":{"location":"company","latitude":"","longitude":""}}}},{"call":"clickToIntent","args":{"intentName":"SetSettingSwitch","params":{"appBundleName":"com.huawei.hmos.settings","itemName":"battery_saving_mode","switchFlag":0}}}],"dataModelSchema":{},"assetCandidates":[{"src":"resources/base/media/location_north_up_right_fill.svg","description":"当前示例使用的本地素材"},{"src":"resources/base/media/bolt_fill.svg","description":"当前示例使用的本地素材"}]}
```
### assistant
```genui
["root","Stack",{"width":320,"height":160,"borderRadius":20,"clip":true,"linearGradient":{"angle":180,"colors":[["#FFDDF5E8",0],["#FFF1FAF5",0.58],["#FFFFFFFF",1]]}},["content_root"]]
["content_root","Column",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":4,"justifyContent":"start","alignItems":"start"},["title_area","content_row"]]
["title_area","Row",{"width":296,"height":17,"justifyContent":"start","alignItems":"center","flexShrink":0},["title_text"]]
["title_text","Text",{"content":"出行助手","width":240,"height":17,"fontSize":12,"fontWeight":700,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
["content_row","Row",{"width":296,"height":115,"itemMargin":8,"justifyContent":"start","alignItems":"center","flexShrink":0},["primary_panel","action_group"]]
["primary_panel","Column",{"width":144,"height":115,"justifyContent":"spaceBetween","alignItems":"start","flexShrink":0},["temperature","home_status"]]
["temperature","Text",{"content":"26°C","width":144,"height":44,"fontSize":36,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textOverflow":"clip"}]
["home_status","Text",{"content":"天气良好 | 适合出行","width":144,"height":40,"fontSize":12,"fontWeight":400,"fontColor":"#99000000","maxLines":2,"textOverflow":"ellipsis"}]
["action_group","Row",{"width":144,"height":115,"itemMargin":8,"justifyContent":"start","alignItems":"center","flexShrink":0},["navigate_action","power_action"]]
["navigate_action","ActionUnit",{"state":"tile","label":"开始导航","icon":"resources/base/media/location_north_up_right_fill.svg","width":68,"height":115,"onClick":[{"call":"clickToIntent","args":{"intentName":"StartNavigate","params":{"dstLocation":{"location":"company","latitude":"","longitude":""}}}}],"actionInk":"#FF64BB5C","actionSurface":"#1964BB5C","flexShrink":0}]
["power_action","ActionUnit",{"state":"tile","label":"开启省电","icon":"resources/base/media/bolt_fill.svg","width":68,"height":115,"onClick":[{"call":"clickToIntent","args":{"intentName":"SetSettingSwitch","params":{"appBundleName":"com.huawei.hmos.settings","itemName":"battery_saving_mode","switchFlag":0}}}],"actionInk":"#FF64BB5C","actionSurface":"#1964BB5C","flexShrink":0}]
```

## 示例八（2x4-A08）：linear-progress，进度 + 双详情背板
### user
```json
{"userQuery":"生成linear-progress，进度 + 双详情背板","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"storage":{"usedPercent":{"type":"integer","description":"示例字段","sampleValue":81}}}},"assetCandidates":[{"src":"resources/base/media/externaldrive_fill.svg","description":"当前示例使用的本地素材"}]}
```
### assistant
```genui
["root","Stack",{"width":320,"height":160,"borderRadius":20,"clip":true,"linearGradient":{"angle":180,"colors":[["#FFDCEAFF",0],["#FFF0F6FF",0.58],["#FFFFFFFF",1]]}},["content_root"]]
["content_root","Column",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":8,"justifyContent":"start","alignItems":"start"},["title_area","content_area"]]
["title_area","Row",{"width":296,"height":20,"justifyContent":"spaceBetween","alignItems":"center","flexShrink":0},["title_text","title_icon"]]
["title_text","Text",{"content":"存储空间监控","width":238,"height":20,"fontSize":12,"fontWeight":700,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
["title_icon","Image",{"src":"resources/base/media/externaldrive_fill.svg","width":16,"height":16,"objectFit":"contain","flexShrink":0}]
["content_area","Column",{"width":296,"height":108,"itemMargin":8,"justifyContent":"start","alignItems":"start","flexShrink":0},["progress_slot","detail_row"]]
["progress_slot","Column",{"width":296,"height":50,"justifyContent":"center","alignItems":"start","flexShrink":0},["storage_progress"]]
["storage_progress","ProgressUnit",{"state":"plain","label":"手机存储空间","value":{"path":"/data/storage/usedPercent"},"total":100,"color":"#FF0A59F7","flexShrink":0}]
["detail_row","Row",{"width":296,"height":50,"itemMargin":8,"justifyContent":"start","alignItems":"center","flexShrink":0},["system_card","other_card"]]
["system_card","Column",{"width":144,"height":50,"padding":{"left":8,"right":8,"top":6,"bottom":6},"borderRadius":10,"backgroundColor":"#0C000000","itemMargin":2,"justifyContent":"center","alignItems":"start","flexShrink":0},["system_label","system_value"]]
["system_label","Text",{"content":"系统数据","width":128,"height":18,"fontSize":12,"fontWeight":700,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"}]
["system_value","Text",{"content":"18.92GB","width":128,"height":16,"fontSize":10,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}]
["other_card","Column",{"width":144,"height":50,"padding":{"left":8,"right":8,"top":6,"bottom":6},"borderRadius":10,"backgroundColor":"#0C000000","itemMargin":2,"justifyContent":"center","alignItems":"start","flexShrink":0},["other_label","other_value"]]
["other_label","Text",{"content":"其它数据","width":128,"height":18,"fontSize":12,"fontWeight":700,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"}]
["other_value","Text",{"content":"23.35GB","width":128,"height":16,"fontSize":10,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}]
["/data/storage/usedPercent",81]
```

## 示例九（2x4-A09）：metric-series，三项同构天气
### user
```json
{"userQuery":"生成metric-series，三项同构天气","size":"2x4","eventCandidates":[],"dataModelSchema":{},"assetCandidates":[{"src":"resources/base/media/sun_max_fill.svg","description":"当前示例使用的本地素材"}]}
```
### assistant
```genui
["root","Stack",{"width":320,"height":160,"borderRadius":20,"clip":true,"linearGradient":{"angle":180,"colors":[["#FFE1ECFF",0],["#FFF3F7FF",0.58],["#FFFFFFFF",1]]}},["content_root"]]
["content_root","Column",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":8,"justifyContent":"start","alignItems":"start"},["title_text","metrics_row"]]
["title_text","Text",{"content":"常用天气","width":296,"height":20,"fontSize":12,"fontWeight":700,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis","flexShrink":0}]
["metrics_row","Row",{"width":296,"height":108,"itemMargin":12,"justifyContent":"start","alignItems":"center","flexShrink":0},["city_card_1","city_card_2","city_card_3"]]
["city_card_1","Column",{"width":90.67,"height":108,"padding":8,"borderRadius":12,"backgroundColor":"#19317AF7","itemMargin":4,"justifyContent":"center","alignItems":"start","flexShrink":0},["weather_icon_1","temperature_1","city_1"]]
["weather_icon_1","Image",{"src":"resources/base/media/sun_max_fill.svg","width":24,"height":24,"objectFit":"contain","fillColor":"#FF317AF7","flexShrink":0}]
["temperature_1","Text",{"content":"38°","width":74,"height":36,"fontSize":32,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textOverflow":"clip"}]
["city_1","Text",{"content":"深圳 | 多云","width":74,"height":18,"fontSize":12,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
["city_card_2","Column",{"width":90.67,"height":108,"padding":8,"borderRadius":12,"backgroundColor":"#19317AF7","itemMargin":4,"justifyContent":"center","alignItems":"start","flexShrink":0},["weather_icon_2","temperature_2","city_2"]]
["weather_icon_2","Image",{"src":"resources/base/media/sun_max_fill.svg","width":24,"height":24,"objectFit":"contain","fillColor":"#FF317AF7","flexShrink":0}]
["temperature_2","Text",{"content":"35°","width":74,"height":36,"fontSize":32,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textOverflow":"clip"}]
["city_2","Text",{"content":"南京 | 多云","width":74,"height":18,"fontSize":12,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
["city_card_3","Column",{"width":90.67,"height":108,"padding":8,"borderRadius":12,"backgroundColor":"#19317AF7","itemMargin":4,"justifyContent":"center","alignItems":"start","flexShrink":0},["weather_icon_3","temperature_3","city_3"]]
["weather_icon_3","Image",{"src":"resources/base/media/sun_max_fill.svg","width":24,"height":24,"objectFit":"contain","fillColor":"#FF317AF7","flexShrink":0}]
["temperature_3","Text",{"content":"27°","width":74,"height":36,"fontSize":32,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textOverflow":"clip"}]
["city_3","Text",{"content":"新疆 | 多云","width":74,"height":18,"fontSize":12,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
```

## 示例十（2x4-A10）：quad-rings，四个设备电量/占比
### user
```json
{"userQuery":"生成quad-rings，四个设备电量/占比","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"device":{"phoneBattery":{"type":"integer","description":"示例字段","sampleValue":20},"phoneBatteryText":{"type":"string","description":"示例字段","sampleValue":"20%"},"earbudBattery":{"type":"integer","description":"示例字段","sampleValue":80},"earbudBatteryText":{"type":"string","description":"示例字段","sampleValue":"80%"},"boxBattery":{"type":"integer","description":"示例字段","sampleValue":76},"boxBatteryText":{"type":"string","description":"示例字段","sampleValue":"76%"},"watchBattery":{"type":"integer","description":"示例字段","sampleValue":74},"watchBatteryText":{"type":"string","description":"示例字段","sampleValue":"74%"}}}},"assetCandidates":[{"src":"resources/base/media/bolt_fill.svg","description":"当前示例使用的本地素材"},{"src":"resources/base/media/icon_earphone.svg","description":"当前示例使用的本地素材"},{"src":"resources/base/media/earphone_case_16644.svg","description":"当前示例使用的本地素材"},{"src":"resources/base/media/kidswatch_fill.svg","description":"当前示例使用的本地素材"}]}
```
### assistant
```genui
["root","Stack",{"width":320,"height":160,"borderRadius":20,"clip":true,"linearGradient":{"angle":180,"colors":[["#FFDDF5E8",0],["#FFF1FAF5",0.58],["#FFFFFFFF",1]]}},["content_root"]]
["content_root","Column",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":8,"justifyContent":"start","alignItems":"center"},["title_text","battery_grid"]]
["title_text","Text",{"content":"电量监控","width":296,"height":20,"fontSize":12,"fontWeight":700,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis","flexShrink":0}]
["battery_grid","Column",{"width":296,"height":108,"itemMargin":8,"justifyContent":"start","alignItems":"center","flexShrink":0},["grid_row_1","grid_row_2"]]
["grid_row_1","Row",{"width":296,"height":50,"itemMargin":8,"justifyContent":"spaceBetween","alignItems":"center","flexShrink":0},["battery_card_1","battery_card_2"]]
["grid_row_2","Row",{"width":296,"height":50,"itemMargin":8,"justifyContent":"spaceBetween","alignItems":"center","flexShrink":0},["battery_card_3","battery_card_4"]]
["battery_card_1","Row",{"width":144,"height":50,"padding":{"left":8,"right":10,"top":4,"bottom":4},"borderRadius":10,"backgroundColor":"#0C000000","itemMargin":10,"alignItems":"center","flexShrink":0},["ring_1","battery_texts_1"]]
["ring_1","RingUnit",{"state":"center-icon","size":40,"value":{"path":"/data/device/phoneBattery"},"total":100,"centerIcon":"resources/base/media/bolt_fill.svg","color":"#FFE84026","flexShrink":0}]
["battery_texts_1","Column",{"width":70,"height":38,"itemMargin":2,"justifyContent":"center","alignItems":"start","flexShrink":1},["percent_text_1","status_text_1"]]
["percent_text_1","Text",{"content":{"path":"/data/device/phoneBatteryText"},"width":70,"height":22,"fontSize":16,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textOverflow":"clip"}]
["status_text_1","Text",{"content":"手机","width":70,"height":16,"fontSize":12,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
["battery_card_2","Row",{"width":144,"height":50,"padding":{"left":8,"right":10,"top":4,"bottom":4},"borderRadius":10,"backgroundColor":"#0C000000","itemMargin":10,"alignItems":"center","flexShrink":0},["ring_2","battery_texts_2"]]
["ring_2","RingUnit",{"state":"center-icon","size":40,"value":{"path":"/data/device/earbudBattery"},"total":100,"centerIcon":"resources/base/media/icon_earphone.svg","color":"#FF64BB5C","flexShrink":0}]
["battery_texts_2","Column",{"width":70,"height":38,"itemMargin":2,"justifyContent":"center","alignItems":"start","flexShrink":1},["percent_text_2","status_text_2"]]
["percent_text_2","Text",{"content":{"path":"/data/device/earbudBatteryText"},"width":70,"height":22,"fontSize":16,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textOverflow":"clip"}]
["status_text_2","Text",{"content":"耳机","width":70,"height":16,"fontSize":12,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
["battery_card_3","Row",{"width":144,"height":50,"padding":{"left":8,"right":10,"top":4,"bottom":4},"borderRadius":10,"backgroundColor":"#0C000000","itemMargin":10,"alignItems":"center","flexShrink":0},["ring_3","battery_texts_3"]]
["ring_3","RingUnit",{"state":"center-icon","size":40,"value":{"path":"/data/device/boxBattery"},"total":100,"centerIcon":"resources/base/media/earphone_case_16644.svg","color":"#FF64BB5C","flexShrink":0}]
["battery_texts_3","Column",{"width":70,"height":38,"itemMargin":2,"justifyContent":"center","alignItems":"start","flexShrink":1},["percent_text_3","status_text_3"]]
["percent_text_3","Text",{"content":{"path":"/data/device/boxBatteryText"},"width":70,"height":22,"fontSize":16,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textOverflow":"clip"}]
["status_text_3","Text",{"content":"盒电量","width":70,"height":16,"fontSize":12,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
["battery_card_4","Row",{"width":144,"height":50,"padding":{"left":8,"right":10,"top":4,"bottom":4},"borderRadius":10,"backgroundColor":"#0C000000","itemMargin":10,"alignItems":"center","flexShrink":0},["ring_4","battery_texts_4"]]
["ring_4","RingUnit",{"state":"center-icon","size":40,"value":{"path":"/data/device/watchBattery"},"total":100,"centerIcon":"resources/base/media/kidswatch_fill.svg","color":"#FF64BB5C","flexShrink":0}]
["battery_texts_4","Column",{"width":70,"height":38,"itemMargin":2,"justifyContent":"center","alignItems":"start","flexShrink":1},["percent_text_4","status_text_4"]]
["percent_text_4","Text",{"content":{"path":"/data/device/watchBatteryText"},"width":70,"height":22,"fontSize":16,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textOverflow":"clip"}]
["status_text_4","Text",{"content":"手表","width":70,"height":16,"fontSize":12,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
["/data/device/phoneBattery",20]
["/data/device/phoneBatteryText","20%"]
["/data/device/earbudBattery",80]
["/data/device/earbudBatteryText","80%"]
["/data/device/boxBattery",76]
["/data/device/boxBatteryText","76%"]
["/data/device/watchBattery",74]
["/data/device/watchBatteryText","74%"]
```

