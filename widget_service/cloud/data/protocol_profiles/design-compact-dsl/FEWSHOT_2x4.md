# 2x4 Few-shot

示例中的数据路径、事件和素材候选取自能力清单；真实输出只能使用当前 TaskSpec 实际提供的 path、icon 和 onClick。示例用于参考布局，浅色示例使用同色相微渐变、80% 白色内容背板和同色相 60% 透明度辅助文字；背景选择、业务映射及内容配色统一遵循 PROMPT.md 第十二节；用户明确配色要求优先，未指定时不得沿用旧纯色和同色背板或自由取色。融球示例仅在本次尺寸、业务、密度和运行时条件均满足时使用，否则按主业务切换到对应浅色微渐变及配套内容色。

2x4 最终恰好两个业务数据块时必须参考 V09：root 必须是 Row，并直接使用左右两个 `144×136vp` 大内容背板，不生成公共标题、公共内容区或公共按钮行，每个业务的数据和按钮只放在所属背板内。禁止复用 2x2 S4，禁止 `root Stack -> content Column`，禁止生成上下两个 `296×64vp` 背板或任何其它上下双业务布局。

图标与动作必须逐一匹配当前对象和真实目标；候选中允许存在干扰项。示例里的动作不是业务默认配置，跨业务组合只在用户明确要求时保留。没有准确图标就用纯文字；不要按分区数复制共享动作。

## 示例八（2x4-V01）：三行近期日程列表（W7-list-rows·黄色微渐变）
### user
```json
{"userQuery":"帮我做张日程卡片，列出接下来三件要做的事。","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"calendar":{"events":[{"title":{"type":"string","description":"日程标题","sampleValue":"项目阶段性汇报"}},{"title":{"type":"string","description":"日程标题","sampleValue":"确认Q3设计需求"}},{"title":{"type":"string","description":"日程标题","sampleValue":"申请下周出差"}}]}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":20,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFFFE0CC",0],["#FFFFF7F2",1]]}},["content"]]
["content","Column",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":4,"justifyContent":"start","alignItems":"start"},["title","list"]]
["title","CardHeader",{"title":"近期日程","fontColor":"#FF8C4B1C"}]
["list","Column",{"width":296,"height":112,"itemMargin":8,"alignItems":"start"},["item0","item1","item2"]]
["item0","Row",{"width":296,"height":32,"padding":{"left":12,"right":12},"borderRadius":8,"backgroundColor":"#CCFFFFFF","alignItems":"center"},["text0"]]
["text0","Text",{"content":{"path":"/data/calendar/events/0/title"},"width":248,"fontSize":12,"fontWeight":400,"fontColor":"#FF8C4B1C","maxLines":1}]
["item1","Row",{"width":296,"height":32,"padding":{"left":12,"right":12},"borderRadius":8,"backgroundColor":"#CCFFFFFF","alignItems":"center"},["text1"]]
["text1","Text",{"content":{"path":"/data/calendar/events/1/title"},"width":248,"fontSize":12,"fontWeight":400,"fontColor":"#FF8C4B1C","maxLines":1}]
["item2","Row",{"width":296,"height":32,"padding":{"left":12,"right":12},"borderRadius":8,"backgroundColor":"#CCFFFFFF","alignItems":"center"},["text2"]]
["text2","Text",{"content":{"path":"/data/calendar/events/2/title"},"width":248,"fontSize":12,"fontWeight":400,"fontColor":"#FF8C4B1C","maxLines":1}]
["/data/calendar/events/0/title","项目阶段性汇报"]
["/data/calendar/events/1/title","确认Q3设计需求"]
["/data/calendar/events/2/title","申请下周出差"]
```
## 示例九（2x4-V02）：手机电量大环与右侧说明（W3-ring-detail·青色微渐变）
### user
```json
{"userQuery":"做张手机电量卡片，让我一眼看清还剩多少电，电量是否正常、有没有在充电。","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"phoneBattery":{"batterySOC":{"type":"integer","description":"0到100的手机电量百分比","sampleValue":68},"batterySOCText":{"type":"string","description":"格式化电量文本","sampleValue":"68%"},"batteryCapacityLevelDesc":{"type":"string","description":"电量等级","sampleValue":"正常电量"},"chargingStatusDesc":{"type":"string","description":"充电状态","sampleValue":"未充电"}}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":20,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFCCFCFF",0],["#FFF2FEFF",1]]}},["content"]]
["content","Column",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":2,"justifyContent":"start","alignItems":"start"},["title","main"]]
["title","CardHeader",{"title":"手机电量","fontColor":"#FF1C838C"}]
["main","Row",{"width":296,"height":113,"itemMargin":8,"alignItems":"center"},["ringArea","info"]]
["ringArea","Column",{"width":144,"height":113,"justifyContent":"center","alignItems":"center"},["ringStack"]]
["ringStack","Stack",{"width":92,"height":92,"alignContent":"center"},["ring","ringValue"]]
["ring","Progress",{"type":"ring","width":92,"height":92,"strokeWidth":8,"value":{"path":"/data/phoneBattery/batterySOC"},"total":100,"color":"#FF1C838C","backgroundColor":"#331C838C"}]
["ringValue","Text",{"content":{"path":"/data/phoneBattery/batterySOCText"},"width":76,"fontSize":18,"fontWeight":700,"fontColor":"#FF1C838C","textAlign":"center","maxLines":1}]
["info","Column",{"width":144,"height":113,"itemMargin":4,"justifyContent":"center"},["infoTitle","level","status"]]
["infoTitle","Text",{"content":"当前电量","width":144,"fontSize":16,"fontWeight":400,"fontColor":"#FF1C838C","maxLines":1}]
["level","Text",{"content":{"path":"/data/phoneBattery/batteryCapacityLevelDesc"},"width":144,"fontSize":12,"fontWeight":400,"fontColor":"#FF1C838C","maxLines":1}]
["status","Text",{"content":{"path":"/data/phoneBattery/chargingStatusDesc"},"width":144,"fontSize":12,"fontWeight":400,"fontColor":"#FF1C838C","maxLines":1}]
["/data/phoneBattery/batterySOC",68]
["/data/phoneBattery/batterySOCText","68%"]
["/data/phoneBattery/batteryCapacityLevelDesc","正常电量"]
["/data/phoneBattery/chargingStatusDesc","未充电"]
```
## 示例十（2x4-V03）：睡眠恢复度线性进度与双详情（W5-progress-detail·紫色微渐变）
### user
```json
{"userQuery":"昨晚睡得怎么样？帮我做张卡片，看看睡眠得分、总共睡了多久、深睡了多久。","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"healthSport":{"sleepScore":{"type":"integer","description":"0到100的睡眠综合得分","sampleValue":82},"nightSleepDurationText":{"type":"string","description":"夜间睡眠总时长","sampleValue":"7小时1分"},"deepSleepDurationText":{"type":"string","description":"深睡时长","sampleValue":"2小时15分"}}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":20,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFDBCCFF",0],["#FFF6F2FF",1]]}},["content"]]
["content","Column",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":8,"justifyContent":"start","alignItems":"start"},["title","body"]]
["title","CardHeader",{"title":"睡眠恢复度","fontColor":"#FF563D99"}]
["body","Column",{"width":296,"height":108,"itemMargin":8,"alignItems":"start"},["progressSlot","details"]]
["progressSlot","Column",{"width":296,"height":50,"itemMargin":4,"justifyContent":"center","alignItems":"start"},["progressText","progress"]]
["progressText","Row",{"width":296,"alignItems":"bottom","itemMargin":6},["score","scoreLabel"]]
["score","Text",{"content":"{{ ${/data/healthSport/sleepScore} + '分' }}","fontSize":18,"fontWeight":700,"fontColor":"#FF563D99","maxLines":1}]
["scoreLabel","Text",{"content":"睡眠综合得分","fontSize":12,"fontWeight":400,"fontColor":"#FF563D99","padding":{"bottom":2},"maxLines":1}]
["progress","Progress",{"type":"linear","width":296,"height":8,"strokeWidth":8,"borderRadius":4,"value":{"path":"/data/healthSport/sleepScore"},"total":100,"color":"#FF563D99","backgroundColor":"#33563D99"}]
["details","Row",{"width":296,"height":50,"itemMargin":8},["night","deep"]]
["night","Column",{"width":144,"height":50,"padding":{"left":8,"right":8,"top":6,"bottom":6},"borderRadius":10,"backgroundColor":"#CCFFFFFF","itemMargin":2,"justifyContent":"center"},["nightLabel","nightValue"]]
["nightLabel","Text",{"content":"睡眠时长","width":128,"fontSize":12,"fontWeight":400,"fontColor":"#FF563D99","maxLines":1}]
["nightValue","Text",{"content":{"path":"/data/healthSport/nightSleepDurationText"},"width":128,"fontSize":12,"fontWeight":400,"fontColor":"#FF563D99","maxLines":1}]
["deep","Column",{"width":144,"height":50,"padding":{"left":8,"right":8,"top":6,"bottom":6},"borderRadius":10,"backgroundColor":"#CCFFFFFF","itemMargin":2,"justifyContent":"center"},["deepLabel","deepValue"]]
["deepLabel","Text",{"content":"深睡时长","width":128,"fontSize":12,"fontWeight":400,"fontColor":"#FF563D99","maxLines":1}]
["deepValue","Text",{"content":{"path":"/data/healthSport/deepSleepDurationText"},"width":128,"fontSize":12,"fontWeight":400,"fontColor":"#FF563D99","maxLines":1}]
["/data/healthSport/sleepScore",82]
["/data/healthSport/nightSleepDurationText","7小时1分"]
["/data/healthSport/deepSleepDurationText","2小时15分"]
```
## 示例十一（2x4-V04）：睡眠得分与双详情（W1-progress-aux·var-a 双份区域·紫色微渐变）
### user
```json
{"userQuery":"帮我做张睡眠卡片，我最关心昨晚睡眠得了多少分，也想看看睡了多久、其中深睡多久。","size":"2x4","eventCandidates":[],"assetCandidates":[],"dataModelSchema":{"data":{"healthSport":{"sleepScore":{"type":"integer","description":"0到100的睡眠综合得分","sampleValue":82},"nightSleepDurationText":{"type":"string","description":"包含单位的夜间睡眠时长","sampleValue":"7小时1分"},"deepSleepDurationText":{"type":"string","description":"包含单位的深睡时长","sampleValue":"2小时15分"}}}}}
```
### assistant
```genui
["root","Row",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":20,"clip":true,"itemMargin":10,"justifyContent":"center","alignItems":"center","linearGradient":{"direction":"RightBottom","colors":[["#FFDBCCFF",0],["#FFF6F2FF",1]]}},["hero","details"]]
["hero","Column",{"width":146,"height":136,"itemMargin":8},["reading","bar"]]
["reading","Column",{"width":146,"layoutWeight":1,"justifyContent":"center","itemMargin":4},["valueRow","label"]]
["valueRow","Row",{"width":146,"itemMargin":4,"alignItems":"bottom"},["value","unit"]]
["value","Text",{"content":{"path":"/data/healthSport/sleepScore"},"fontSize":38,"fontWeight":700,"fontColor":"#FF563D99","maxLines":1}]
["label","Text",{"content":"睡眠得分 / 100分","width":146,"fontSize":12,"fontWeight":400,"fontColor":"#FF563D99","maxLines":1}]
["bar","Progress",{"type":"linear","width":146,"height":8,"strokeWidth":8,"value":{"path":"/data/healthSport/sleepScore"},"total":100,"color":"#FF563D99","backgroundColor":"#33563D99"}]
["details","Column",{"width":140,"height":136,"itemMargin":8},["night","deep"]]
["unit","Text",{"content":"分","width":20,"fontSize":12,"fontWeight":400,"fontColor":"#FF563D99","maxLines":1}]
["night","Column",{"width":140,"height":64,"padding":10,"borderRadius":12,"backgroundColor":"#CCFFFFFF","itemMargin":4,"justifyContent":"center"},["nightLabel","nightValue"]]
["nightLabel","Text",{"content":"夜间睡眠","width":120,"fontSize":12,"fontWeight":400,"fontColor":"#FF563D99","maxLines":1}]
["nightValue","Text",{"content":{"path":"/data/healthSport/nightSleepDurationText"},"width":120,"fontSize":12,"fontWeight":400,"fontColor":"#FF563D99","maxLines":1}]
["deep","Column",{"width":140,"height":64,"padding":10,"borderRadius":12,"backgroundColor":"#CCFFFFFF","itemMargin":4,"justifyContent":"center"},["deepLabel","deepValue"]]
["deepLabel","Text",{"content":"深睡时长","width":120,"fontSize":12,"fontWeight":400,"fontColor":"#FF563D99","maxLines":1}]
["deepValue","Text",{"content":{"path":"/data/healthSport/deepSleepDurationText"},"width":120,"fontSize":12,"fontWeight":400,"fontColor":"#FF563D99","maxLines":1}]
["/data/healthSport/sleepScore",82]
["/data/healthSport/nightSleepDurationText","7小时1分"]
["/data/healthSport/deepSleepDurationText","2小时15分"]
```
## 示例十二（2x4-V05）：健康三指标（W4-metric-triple·绿色微渐变）
### user
```json
{"userQuery":"做张健康卡片，把睡眠得分、今天消耗的热量和走的步数放在一起，方便我随时看看。","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"healthSport":{"sleepScore":{"type":"integer","description":"0到100的睡眠得分","sampleValue":80},"dailyTotalCaloriesText":{"type":"string","description":"含单位的今日总消耗热量","sampleValue":"92 千卡"},"dailySteps":{"type":"integer","description":"今日累计步数","sampleValue":2031}}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":20,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFCCFFDD",0],["#FFF2FFF6",1]]}},["content"]]
["content","Column",{"width":"matchParent","height":"matchParent","padding":12,"justifyContent":"spaceBetween","alignItems":"start"},["title","metrics"]]
["title","CardHeader",{"title":"我的健康数据","fontColor":"#FF1C8C41"}]
["metrics","Row",{"width":296,"height":84,"justifyContent":"spaceBetween","alignItems":"center"},["metric0","sep0","metric1","sep1","metric2"]]
["metric0","Column",{"width":96,"height":84,"itemMargin":4,"justifyContent":"center","alignItems":"center"},["value0","label0"]]
["label0","Text",{"content":"睡眠得分","width":96,"fontSize":12,"fontWeight":400,"fontColor":"#FF1C8C41","textAlign":"center","maxLines":1}]
["value0","Text",{"content":"{{ ${/data/healthSport/sleepScore} + '分' }}","width":96,"fontSize":18,"fontWeight":700,"fontColor":"#FF1C8C41","textAlign":"center","maxLines":1}]
["sep0","Divider",{"width":1,"height":64,"vertical":true,"color":"#331C8C41"}]
["metric1","Column",{"width":96,"height":84,"itemMargin":4,"justifyContent":"center","alignItems":"center"},["value1","label1"]]
["label1","Text",{"content":"消耗热量","width":96,"fontSize":12,"fontWeight":400,"fontColor":"#FF1C8C41","textAlign":"center","maxLines":1}]
["value1","Text",{"content":{"path":"/data/healthSport/dailyTotalCaloriesText"},"width":96,"fontSize":18,"fontWeight":700,"fontColor":"#FF1C8C41","textAlign":"center","maxLines":1}]
["sep1","Divider",{"width":1,"height":64,"vertical":true,"color":"#331C8C41"}]
["metric2","Column",{"width":96,"height":84,"itemMargin":4,"justifyContent":"center","alignItems":"center"},["value2","label2"]]
["label2","Text",{"content":"今日步数","width":96,"fontSize":12,"fontWeight":400,"fontColor":"#FF1C8C41","textAlign":"center","maxLines":1}]
["value2","Text",{"content":"{{ ${/data/healthSport/dailySteps} + '步' }}","width":96,"fontSize":18,"fontWeight":700,"fontColor":"#FF1C8C41","textAlign":"center","maxLines":1}]
["/data/healthSport/sleepScore",80]
["/data/healthSport/dailyTotalCaloriesText","92 千卡"]
["/data/healthSport/dailySteps",2031]
```
## 示例十三（2x4-V06）：无标题四业务速览（W8-quad-cells·蓝色微渐变）
W8 四数据布局自身固定无卡级标题，不依赖用户额外提出“无标题”；四个 `144×64vp` 小内容背板必须占满安全内容区，不为 header 压缩高度。
### user
```json
{"userQuery":"帮我做张卡片，一起看看现在的气温、手机和耳机盒还剩多少电，还有下一场日程几点开始。","size":"2x4","eventCandidates":[],"assetCandidates":[],"dataModelSchema":{"data":{"weather":{"current":{"temperatureText":{"type":"string","description":"含单位的当前温度","sampleValue":"26°C"}}},"phoneBattery":{"batterySOCText":{"type":"string","description":"含单位的手机电量","sampleValue":"68%"}},"earphone":{"batteryLevel":{"type":"integer","description":"耳机盒电量百分比0到100","sampleValue":80}},"calendar":{"events":[{"dtStart":{"type":"string","description":"开始时间","sampleValue":"14:00"}}]}}}}
```
### assistant
```genui
["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":20,"clip":true,"alignItems":"center","itemMargin":8,"linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["top","bottom"]]
["top","Row",{"width":296,"height":64,"itemMargin":8},["weather","phone"]]
["bottom","Row",{"width":296,"height":64,"itemMargin":8},["ear","calendar"]]
["weather","Column",{"width":144,"height":64,"padding":12,"borderRadius":16,"backgroundColor":"#CCFFFFFF","itemMargin":2,"justifyContent":"center"},["weatherValue","weatherLabel"]]
["weatherValue","Text",{"content":{"path":"/data/weather/current/temperatureText"},"width":120,"fontSize":14,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["weatherLabel","Text",{"content":"天气","width":120,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["/data/weather/current/temperatureText","26°C"]
["phone","Column",{"width":144,"height":64,"padding":12,"borderRadius":16,"backgroundColor":"#CCFFFFFF","itemMargin":2,"justifyContent":"center"},["phoneValue","phoneLabel"]]
["phoneValue","Text",{"content":{"path":"/data/phoneBattery/batterySOCText"},"width":120,"fontSize":14,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["phoneLabel","Text",{"content":"手机电量","width":120,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["/data/phoneBattery/batterySOCText","68%"]
["ear","Column",{"width":144,"height":64,"padding":12,"borderRadius":16,"backgroundColor":"#CCFFFFFF","itemMargin":2,"justifyContent":"center"},["earValue","earLabel"]]
["earValue","Text",{"content":"{{ ${/data/earphone/batteryLevel} + '%' }}","width":120,"fontSize":14,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["earLabel","Text",{"content":"耳机盒","width":120,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["/data/earphone/batteryLevel",80]
["calendar","Column",{"width":144,"height":64,"padding":12,"borderRadius":16,"backgroundColor":"#CCFFFFFF","itemMargin":2,"justifyContent":"center"},["calendarValue","calendarLabel"]]
["calendarValue","Text",{"content":{"path":"/data/calendar/events/0/dtStart"},"width":120,"fontSize":14,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["calendarLabel","Text",{"content":"日程开始","width":120,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["/data/calendar/events/0/dtStart","14:00"]
```
## 示例十四（2x4-V07）：单列日程安排（W2-text-flow·黄色微渐变）
### user
```json
{"userQuery":"帮我做张日程卡片，告诉我下一件事是什么、具体要做什么，以及是哪一天。","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"calendar":{"events":[{"title":{"type":"string","description":"日程标题","sampleValue":"需求评审会"},"description":{"type":"string","description":"日程说明","sampleValue":"评审卡片数据接口与视觉还原结果"},"startDate":{"type":"string","description":"日程开始日期MM-DD","sampleValue":"12-18"}}]}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":20,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFFFE0CC",0],["#FFFFF7F2",1]]}},["content"]]
["content","Column",{"width":"matchParent","height":"matchParent","padding":12,"justifyContent":"start","alignItems":"start"},["kicker","lower"]]
["kicker","Text",{"content":"日程安排","width":296,"fontSize":12,"fontWeight":400,"fontColor":"#FF8C4B1C","maxLines":1}]
["event","Column",{"width":296,"height":76,"itemMargin":6,"justifyContent":"end","alignItems":"start"},["eventTitle","eventDesc"]]
["eventTitle","Text",{"content":{"path":"/data/calendar/events/0/title"},"width":296,"fontSize":18,"fontWeight":500,"fontColor":"#FF8C4B1C","maxLines":1}]
["eventDesc","Text",{"content":{"path":"/data/calendar/events/0/description"},"width":296,"height":34,"fontSize":12,"fontWeight":400,"fontColor":"#FF8C4B1C","maxLines":2}]
["lower","Column",{"width":296,"height":113,"justifyContent":"end","alignItems":"start"},["event","date"]]
["date","Text",{"content":{"path":"/data/calendar/events/0/startDate"},"width":296,"fontSize":12,"fontWeight":400,"fontColor":"#FF8C4B1C","maxLines":1}]
["/data/calendar/events/0/title","需求评审会"]
["/data/calendar/events/0/description","评审卡片数据接口与视觉还原结果"]
["/data/calendar/events/0/startDate","12-18"]
```
## 示例十五（2x4-V08）：下一日程与双真实入口（W6-agenda-cta·黄色微渐变）
### user
```json
{"userQuery":"做张日程提醒卡片，看看下一件事是什么、在哪里、几点开始和结束，再放上查看这条日程和打开专注设置的按钮。","size":"2x4","eventCandidates":[{"call":"clickToIntent","args":{"intentName":"ViewCalendarEvent","params":{"entityId":"{{ ${/data/calendar/events/0/entityId} }}"}}},{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"intelligent_scene_entry"}}],"dataModelSchema":{"data":{"calendar":{"events":[{"title":{"type":"string","description":"日程标题","sampleValue":"需求评审会"},"eventLocation":{"type":"string","description":"日程地点","sampleValue":"五和大道华为基地"},"dtStart":{"type":"string","description":"开始时间","sampleValue":"14:00"},"dtEnd":{"type":"string","description":"结束时间","sampleValue":"15:30"},"entityId":{"type":"string","description":"日程实体ID","sampleValue":"calendar-event-001"}}]}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":20,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFFFE0CC",0],["#FFFFF7F2",1]]}},["content"]]
["content","Column",{"width":"matchParent","height":"matchParent","padding":12,"justifyContent":"start","alignItems":"start","itemMargin":8},["kicker","event","actions"]]
["kicker","Text",{"content":"下一个日程","width":296,"fontSize":12,"fontWeight":400,"fontColor":"#FF8C4B1C","maxLines":1}]
["event","Column",{"width":296,"itemMargin":4,"alignItems":"start","layoutWeight":1,"justifyContent":"center"},["eventName","eventTime"]]
["eventName","Text",{"content":"{{ ${/data/calendar/events/0/title} + ' | ' + ${/data/calendar/events/0/eventLocation} }}","width":296,"fontSize":16,"fontWeight":500,"fontColor":"#FF8C4B1C","maxLines":1}]
["eventTime","Text",{"content":"{{ ${/data/calendar/events/0/dtStart} + ' - ' + ${/data/calendar/events/0/dtEnd} }}","width":296,"fontSize":12,"fontWeight":400,"fontColor":"#FF8C4B1C","maxLines":1}]
["actions","Row",{"width":296,"height":36,"justifyContent":"spaceBetween"},["calendarButton","focusButton"]]
["calendarButton","Button",{"label":"查看日程","width":140,"height":36,"borderRadius":18,"backgroundColor":"#338C4B1C","fontColor":"#FF8C4B1C","fontSize":14,"fontWeight":500,"onClick":[{"call":"clickToIntent","args":{"intentName":"ViewCalendarEvent","params":{"entityId":"{{ ${/data/calendar/events/0/entityId} }}"}}}]}]
["focusButton","Button",{"label":"专注模式","width":140,"height":36,"borderRadius":18,"backgroundColor":"#338C4B1C","fontColor":"#FF8C4B1C","fontSize":14,"fontWeight":500,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"intelligent_scene_entry"}}]}]
["/data/calendar/events/0/title","需求评审会"]
["/data/calendar/events/0/eventLocation","五和大道华为基地"]
["/data/calendar/events/0/dtStart","14:00"]
["/data/calendar/events/0/dtEnd","15:30"]
["/data/calendar/events/0/entityId","calendar-event-001"]
```

## 示例十六（2x4-V09）：天气与手机电量双业务（W9-dual-backboards·蓝色微渐变）
W9 先按对象合并字段再布局：同一耳机的连接状态、耳机仓电量和充电状态只能共同放在一个背板，不能拆成右侧两个小背板来伪造 W10；action 不增加数据块，也不能为了放按钮改变骨架或把音乐动作放进天气背板。两个业务只能左右排列，禁止改成上下两个全宽背板。双业务中的倒计时只使用同一行 `14fp/700` 普通主数据（如 `30天`），不使用单业务倒计时 hero，不将“天”拆成第三行。多日天气每一天合并成一行 `12fp/400` 文本，不拆成星期、温度、降雨三行，也不在日期间增加 Divider。
归属示范：音乐入口和音乐/闹钟素材是干扰候选，不属于本轮明确的天气、电量需求，全部舍弃。天气与电池按钮分别保留在所属背板，缺少准确图标时使用纯文字，不能为左右对称复制同一动作。动作参数引用的数据根必须与所在背板的数据根一致，例如引用 `/data/weather/` 的按钮必须放在天气背板。
### user
```json
{"userQuery":"做张卡片，看看上海现在的天气和手机剩余电量，还能分别打开天气详情和电池设置。","size":"2x4","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"Weather_CityCode","uri":"{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' + ${/data/weather/location/cityCode} }}"}},{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"battery"}},{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4"}}],"dataModelSchema":{"data":{"weather":{"location":{"cityCode":{"type":"string","description":"城市编码","sampleValue":"101020100"}},"current":{"condition":{"type":"string","description":"天气状况","sampleValue":"多云"},"temperatureC":{"type":"integer","description":"当前温度","sampleValue":29}}},"phoneBattery":{"batterySOC":{"type":"integer","description":"手机电量百分比","sampleValue":68},"chargingStatusDesc":{"type":"string","description":"充电状态","sampleValue":"未充电"}}}},"assetCandidates":[{"src":"resources/base/media/music_fill.svg","description":"样式：音乐音符实心图标，默认黑色，图形为双音符连接造型；适用：音乐播放卡片、音频功能入口、歌单展示。"},{"src":"resources/base/media/alarm_fill_1.svg","description":"样式：默认黑色的单色闹钟实心图标，内部通过镂空表现表盘指针，支持通过 fillColor 与卡片配色统一；适用：闹钟设置、定时提醒、日程提醒。"}]}
```
### assistant
```genui
["root","Row",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":8,"borderRadius":20,"clip":true,"alignItems":"center","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]},"justifyContent":"center"},["weatherZone","batteryZone"]]
["weatherZone","Column",{"width":144,"height":136,"padding":12,"itemMargin":4,"borderRadius":16,"backgroundColor":"#CCFFFFFF"},["weatherContent","weatherButton"]]
["weatherTitle","Text",{"content":"上海天气","width":120,"height":16,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["weatherContent","Column",{"width":120,"layoutWeight":1,"itemMargin":2,"justifyContent":"center"},["weatherTitle","weatherValue","weatherStatus"]]
["weatherValue","Text",{"content":"{{ ${/data/weather/current/temperatureC} + '°C' }}","width":120,"fontSize":18,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["weatherStatus","Text",{"content":{"path":"/data/weather/current/condition"},"width":120,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["weatherButton","Button",{"label":"查看天气","width":120,"height":36,"borderRadius":18,"backgroundColor":"#331F4799","fontColor":"#FF1F4799","fontSize":14,"fontWeight":400,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Weather_CityCode","uri":"{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' + ${/data/weather/location/cityCode} }}"}}]}]
["batteryZone","Column",{"width":144,"height":136,"padding":12,"itemMargin":4,"borderRadius":16,"backgroundColor":"#CCFFFFFF"},["batteryContent","batteryButton"]]
["batteryTitle","Text",{"content":"手机电量","width":120,"height":16,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["batteryContent","Column",{"width":120,"layoutWeight":1,"itemMargin":2,"justifyContent":"center"},["batteryTitle","batteryValue","batteryStatus"]]
["batteryValue","Text",{"content":"{{ ${/data/phoneBattery/batterySOC} + '%' }}","width":120,"fontSize":18,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["batteryStatus","Text",{"content":{"path":"/data/phoneBattery/chargingStatusDesc"},"width":120,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["batteryButton","Button",{"label":"电池设置","width":120,"height":36,"borderRadius":18,"backgroundColor":"#331F4799","fontColor":"#FF1F4799","fontSize":14,"fontWeight":400,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"battery"}}]}]
["/data/weather/location/cityCode","101020100"]
["/data/weather/current/condition","多云"]
["/data/weather/current/temperatureC",29]
["/data/phoneBattery/batterySOC",68]
["/data/phoneBattery/chargingStatusDesc","未充电"]
```

## 示例十七（2x4-V10）：天气、手机与耳机三数据（W10-triple-backboards·蓝色微渐变）
### user
```json
{"userQuery":"帮我做张卡片，主要看上海现在的天气，顺便看看手机剩余电量、有没有在充电，以及耳机连上没有。还要能打开天气详情、电池设置和蓝牙设置。","size":"2x4","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"Weather_CityCode","uri":"{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' + ${/data/weather/location/cityCode} }}"}},{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"battery"}},{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"bluetooth_entry"}}],"dataModelSchema":{"data":{"weather":{"location":{"cityCode":{"type":"string","description":"城市编码","sampleValue":"101020100"}},"current":{"condition":{"type":"string","description":"天气状况","sampleValue":"多云"},"temperatureC":{"type":"integer","description":"当前温度","sampleValue":29}}},"phoneBattery":{"batterySOC":{"type":"integer","description":"手机电量百分比","sampleValue":68},"chargingStatusDesc":{"type":"string","description":"充电状态","sampleValue":"未充电"}},"earphone":{"isConnected":{"type":"boolean","description":"耳机是否连接","sampleValue":true}}}},"assetCandidates":[{"src":"resources/base/media/earphone_case_16644.svg","description":"本地耳机盒图标"}]}
```
### assistant
```genui
["root","Row",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":8,"borderRadius":20,"clip":true,"justifyContent":"center","alignItems":"center","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["weatherZone","secondaryColumn"]]
["weatherZone","Column",{"width":144,"height":136,"padding":12,"itemMargin":4,"borderRadius":16,"backgroundColor":"#CCFFFFFF"},["weatherContent","weatherButton"]]
["weatherLabel","Text",{"content":"上海天气","width":120,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["weatherContent","Column",{"width":120,"layoutWeight":1,"itemMargin":2,"justifyContent":"center"},["weatherValue","weatherLabel","weatherStatus"]]
["weatherValue","Text",{"content":"{{ ${/data/weather/current/temperatureC} + '°C' }}","width":120,"fontSize":18,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["weatherStatus","Text",{"content":{"path":"/data/weather/current/condition"},"width":120,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["weatherButton","Button",{"label":"查看天气","width":120,"height":36,"borderRadius":18,"backgroundColor":"#331F4799","fontColor":"#FF1F4799","fontSize":14,"fontWeight":400,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Weather_CityCode","uri":"{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' + ${/data/weather/location/cityCode} }}"}}]}]
["secondaryColumn","Column",{"width":144,"height":136,"itemMargin":8},["batteryZone","earphoneZone"]]
["batteryZone","Column",{"width":144,"height":64,"padding":12,"itemMargin":2,"borderRadius":16,"backgroundColor":"#CCFFFFFF","justifyContent":"center","onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"battery"}}]},["batteryValue","batteryAux"]]
["batteryValue","Text",{"content":"{{ ${/data/phoneBattery/batterySOC} + '%' }}","width":120,"fontSize":14,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["batteryAux","Text",{"content":{"path":"/data/phoneBattery/chargingStatusDesc"},"width":120,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["earphoneZone","Row",{"width":144,"height":64,"padding":12,"itemMargin":8,"borderRadius":16,"backgroundColor":"#CCFFFFFF","justifyContent":"start","alignItems":"center","onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"bluetooth_entry"}}]},["earphoneText","earphoneIcon"]]
["earphoneText","Column",{"width":92,"itemMargin":2,"justifyContent":"center"},["earphoneValue","earphoneStatus"]]
["earphoneValue","Text",{"content":"耳机","width":92,"fontSize":14,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["earphoneStatus","Text",{"content":"{{ ${/data/earphone/isConnected} ? '已连接' : '未连接' }}","width":92,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["earphoneIcon","Image",{"src":"resources/base/media/earphone_case_16644.svg","width":20,"height":20,"objectFit":"contain","fillColor":"#FF1F4799","flexShrink":0}]
["/data/weather/location/cityCode","101020100"]
["/data/weather/current/condition","多云"]
["/data/weather/current/temperatureC",29]
["/data/phoneBattery/batterySOC",68]
["/data/phoneBattery/chargingStatusDesc","未充电"]
["/data/earphone/isConnected",true]
```
