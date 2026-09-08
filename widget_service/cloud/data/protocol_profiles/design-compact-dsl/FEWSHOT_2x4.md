# 2x4 Few-shot

示例中的数据路径、事件和素材候选取自能力清单；真实输出只能使用当前 TaskSpec 实际提供的 path、icon 和 onClick。示例用于参考布局，背景选择、业务映射及内容配色统一遵循 PROMPT.md 第十二节；用户明确配色要求优先，未指定时不得沿用旧色值或自由取色。融球示例仅在本次尺寸、业务、密度和运行时条件均满足时使用，否则按主业务切换到对应浅色纯色及配套内容色。

## 示例八（2x4-V01）：三行近期日程列表（W7-list-rows·黄色纯色）
### user
```json
{"userQuery":"显示最近三项日程，使用三行列表骨架。","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"calendar":{"events":[{"title":{"type":"string","description":"日程标题","sampleValue":"项目阶段性汇报"}},{"title":{"type":"string","description":"日程标题","sampleValue":"确认Q3设计需求"}},{"title":{"type":"string","description":"日程标题","sampleValue":"申请下周出差"}}]}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":20,"clip":true,"backgroundColor":"#FFFFF3E6"},["content"]]
["content","Column",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":4},["title","list"]]
["title","Text",{"content":"近期日程","width":296,"height":17,"fontSize":12,"fontWeight":700,"fontColor":"#FF99661F","maxLines":1}]
["list","Column",{"width":296,"height":115,"itemMargin":8},["item0","item1","item2"]]
["item0","Row",{"width":296,"height":33,"padding":{"left":12,"right":12},"borderRadius":8,"backgroundColor":"#1A99661F","alignItems":"center"},["text0"]]
["text0","Text",{"content":{"path":"/data/calendar/events/0/title"},"width":248,"fontSize":12,"fontWeight":400,"fontColor":"#FF99661F","maxLines":1}]
["item1","Row",{"width":296,"height":33,"padding":{"left":12,"right":12},"borderRadius":8,"backgroundColor":"#1A99661F","alignItems":"center"},["text1"]]
["text1","Text",{"content":{"path":"/data/calendar/events/1/title"},"width":248,"fontSize":12,"fontWeight":400,"fontColor":"#FF99661F","maxLines":1}]
["item2","Row",{"width":296,"height":33,"padding":{"left":12,"right":12},"borderRadius":8,"backgroundColor":"#1A99661F","alignItems":"center"},["text2"]]
["text2","Text",{"content":{"path":"/data/calendar/events/2/title"},"width":248,"fontSize":12,"fontWeight":400,"fontColor":"#FF99661F","maxLines":1}]
["/data/calendar/events/0/title","项目阶段性汇报"]
["/data/calendar/events/1/title","确认Q3设计需求"]
["/data/calendar/events/2/title","申请下周出差"]
```
## 示例九（2x4-V02）：手机电量大环与右侧说明（W3-ring-detail·青色纯色）
### user
```json
{"userQuery":"用大环显示手机电量，右侧给出电量等级和充电状态。","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"phoneBattery":{"batterySOC":{"type":"integer","description":"0到100的手机电量百分比","sampleValue":68},"batterySOCText":{"type":"string","description":"格式化电量文本","sampleValue":"68%"},"batteryCapacityLevelDesc":{"type":"string","description":"电量等级","sampleValue":"正常电量"},"chargingStatusDesc":{"type":"string","description":"充电状态","sampleValue":"未充电"}}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":20,"clip":true,"backgroundColor":"#FFE6FDFF"},["content"]]
["content","Column",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":6},["title","main"]]
["title","Text",{"content":"手机电量","width":296,"height":17,"fontSize":12,"fontWeight":700,"fontColor":"#FF1F8F99","maxLines":1}]
["main","Row",{"width":296,"height":113,"itemMargin":8,"alignItems":"center"},["ringArea","info"]]
["ringArea","Column",{"width":144,"height":113,"justifyContent":"center","alignItems":"center"},["ringStack"]]
["ringStack","Stack",{"width":92,"height":92,"alignContent":"center"},["ring","ringValue"]]
["ring","Progress",{"type":"ring","width":92,"height":92,"strokeWidth":8,"value":{"path":"/data/phoneBattery/batterySOC"},"total":100,"color":"#FF1F8F99","backgroundColor":"#1F1F8F99"}]
["ringValue","Text",{"content":{"path":"/data/phoneBattery/batterySOCText"},"width":76,"fontSize":20,"fontWeight":700,"fontColor":"#FF1F8F99","textAlign":"center","maxLines":1}]
["info","Column",{"width":144,"height":113,"itemMargin":4,"justifyContent":"center"},["infoTitle","level","status"]]
["infoTitle","Text",{"content":"当前电量","width":144,"fontSize":16,"fontWeight":700,"fontColor":"#FF1F8F99","maxLines":1}]
["level","Text",{"content":{"path":"/data/phoneBattery/batteryCapacityLevelDesc"},"width":144,"fontSize":12,"fontWeight":400,"fontColor":"#991F8F99","maxLines":1}]
["status","Text",{"content":{"path":"/data/phoneBattery/chargingStatusDesc"},"width":144,"fontSize":12,"fontWeight":400,"fontColor":"#991F8F99","maxLines":1}]
["/data/phoneBattery/batterySOC",68]
["/data/phoneBattery/batterySOCText","68%"]
["/data/phoneBattery/batteryCapacityLevelDesc","正常电量"]
["/data/phoneBattery/chargingStatusDesc","未充电"]
```
## 示例十（2x4-V03）：睡眠恢复度线性进度与双详情（W5-progress-detail·紫色纯色）
### user
```json
{"userQuery":"用线性进度展示睡眠恢复度，并显示睡眠时长和深睡时长。","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"healthSport":{"sleepScore":{"type":"integer","description":"0到100的睡眠综合得分","sampleValue":82},"nightSleepDurationText":{"type":"string","description":"夜间睡眠总时长","sampleValue":"7小时1分"},"deepSleepDurationText":{"type":"string","description":"深睡时长","sampleValue":"2小时15分"}}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":20,"clip":true,"backgroundColor":"#FFEDE6FF"},["content"]]
["content","Column",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":8},["title","body"]]
["title","Text",{"content":"睡眠恢复度","width":296,"height":20,"fontSize":12,"fontWeight":700,"fontColor":"#FF401F99","maxLines":1}]
["body","Column",{"width":296,"height":108,"itemMargin":8},["progressSlot","details"]]
["progressSlot","Column",{"width":296,"height":50,"itemMargin":4,"justifyContent":"center"},["progressText","progress"]]
["progressText","Row",{"width":296,"alignItems":"bottom","itemMargin":6},["score","scoreLabel"]]
["score","Text",{"content":"{{ ${/data/healthSport/sleepScore} + '分' }}","fontSize":20,"fontWeight":700,"fontColor":"#FF401F99","maxLines":1}]
["scoreLabel","Text",{"content":"睡眠综合得分","fontSize":10,"fontWeight":400,"fontColor":"#99401F99","padding":{"bottom":2},"maxLines":1}]
["progress","Progress",{"type":"linear","width":296,"height":8,"strokeWidth":8,"borderRadius":4,"value":{"path":"/data/healthSport/sleepScore"},"total":100,"color":"#FF401F99","backgroundColor":"#1F401F99"}]
["details","Row",{"width":296,"height":50,"itemMargin":8},["night","deep"]]
["night","Column",{"width":144,"height":50,"padding":{"left":8,"right":8,"top":6,"bottom":6},"borderRadius":10,"backgroundColor":"#1A401F99","itemMargin":2,"justifyContent":"center"},["nightLabel","nightValue"]]
["nightLabel","Text",{"content":"睡眠时长","width":128,"fontSize":12,"fontWeight":700,"fontColor":"#FF401F99","maxLines":1}]
["nightValue","Text",{"content":{"path":"/data/healthSport/nightSleepDurationText"},"width":128,"fontSize":10,"fontWeight":400,"fontColor":"#99401F99","maxLines":1}]
["deep","Column",{"width":144,"height":50,"padding":{"left":8,"right":8,"top":6,"bottom":6},"borderRadius":10,"backgroundColor":"#1A401F99","itemMargin":2,"justifyContent":"center"},["deepLabel","deepValue"]]
["deepLabel","Text",{"content":"深睡时长","width":128,"fontSize":12,"fontWeight":700,"fontColor":"#FF401F99","maxLines":1}]
["deepValue","Text",{"content":{"path":"/data/healthSport/deepSleepDurationText"},"width":128,"fontSize":10,"fontWeight":400,"fontColor":"#99401F99","maxLines":1}]
["/data/healthSport/sleepScore",82]
["/data/healthSport/nightSleepDurationText","7小时1分"]
["/data/healthSport/deepSleepDurationText","2小时15分"]
```
## 示例十一（2x4-V04）：倒计时与双训练卡（W1-progress-aux·var-a 双份区域·黄色纯色）
### user
```json
{"userQuery":"HK100倒计时：左侧显示剩余天数和恢复度，右侧固定展示最近两项训练日程。","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"countdown":{"countdownDays":{"type":"integer","description":"距离赛事的自然日天数","sampleValue":32}},"healthSport":{"sleepScore":{"type":"integer","description":"0到100的睡眠恢复分","sampleValue":82}},"calendar":{"events":[{"title":{"type":"string","description":"训练标题","sampleValue":"周一训练计划"},"description":{"type":"string","description":"训练说明","sampleValue":"30min户外跑步"}},{"title":{"type":"string","description":"训练标题","sampleValue":"周三训练计划"},"description":{"type":"string","description":"训练说明","sampleValue":"30min户外跑步"}}]}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":20,"clip":true,"backgroundColor":"#FFFFF3E6"},["content"]]
["content","Row",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":10},["hero","plans"]]
["hero","Column",{"width":146,"height":136,"justifyContent":"spaceBetween"},["tag","count","recovery"]]
["tag","Text",{"content":"距离HK100越野赛","width":146,"height":20,"fontSize":12,"fontWeight":400,"fontColor":"#9999661F","maxLines":1}]
["count","Row",{"width":146,"height":44,"itemMargin":5,"alignItems":"bottom"},["days","unit"]]
["days","Text",{"content":{"path":"/data/countdown/countdownDays"},"fontSize":40,"fontWeight":700,"fontColor":"#FF99661F","maxLines":1}]
["unit","Text",{"content":"天剩余","fontSize":12,"fontWeight":400,"fontColor":"#9999661F","padding":{"bottom":6},"maxLines":1}]
["recovery","Column",{"width":146,"height":28,"itemMargin":3},["recoveryBar","recoveryLabels"]]
["recoveryBar","Progress",{"type":"linear","width":146,"height":8,"strokeWidth":8,"borderRadius":4,"value":{"path":"/data/healthSport/sleepScore"},"total":100,"color":"#FF99661F","backgroundColor":"#4799661F"}]
["recoveryLabels","Row",{"width":146,"justifyContent":"spaceBetween"},["recoveryName","recoveryValue"]]
["recoveryName","Text",{"content":"训练恢复度","fontSize":10,"fontWeight":400,"fontColor":"#9999661F","maxLines":1}]
["recoveryValue","Text",{"content":"{{ ${/data/healthSport/sleepScore} + '分' }}","fontSize":10,"fontWeight":400,"fontColor":"#9999661F","maxLines":1}]
["plans","Column",{"width":140,"height":136,"itemMargin":8},["plan0","plan1"]]
["plan0","Column",{"width":140,"height":64,"padding":{"left":10,"right":10,"top":8,"bottom":8},"borderRadius":12,"backgroundColor":"#1A99661F","itemMargin":3,"justifyContent":"center"},["plan0Title","plan0Desc"]]
["plan0Title","Text",{"content":{"path":"/data/calendar/events/0/title"},"width":120,"fontSize":12,"fontWeight":700,"fontColor":"#FF99661F","maxLines":1}]
["plan0Desc","Text",{"content":{"path":"/data/calendar/events/0/description"},"width":120,"fontSize":10,"fontWeight":400,"fontColor":"#9999661F","maxLines":1}]
["plan1","Column",{"width":140,"height":64,"padding":{"left":10,"right":10,"top":8,"bottom":8},"borderRadius":12,"backgroundColor":"#1A99661F","itemMargin":3,"justifyContent":"center"},["plan1Title","plan1Desc"]]
["plan1Title","Text",{"content":{"path":"/data/calendar/events/1/title"},"width":120,"fontSize":12,"fontWeight":700,"fontColor":"#FF99661F","maxLines":1}]
["plan1Desc","Text",{"content":{"path":"/data/calendar/events/1/description"},"width":120,"fontSize":10,"fontWeight":400,"fontColor":"#9999661F","maxLines":1}]
["/data/countdown/countdownDays",32]
["/data/healthSport/sleepScore",82]
["/data/calendar/events/0/title","周一训练计划"]
["/data/calendar/events/0/description","30min户外跑步"]
["/data/calendar/events/1/title","周三训练计划"]
["/data/calendar/events/1/description","30min户外跑步"]
```
## 示例十二（2x4-V05）：健康三指标（W4-metric-triple·绿色纯色）
### user
```json
{"userQuery":"我的健康数据：睡眠得分、今日消耗热量和今日步数三项并排，用分割线分隔。","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"healthSport":{"sleepScore":{"type":"integer","description":"0到100的睡眠得分","sampleValue":80},"dailyTotalCaloriesText":{"type":"string","description":"含单位的今日总消耗热量","sampleValue":"92 千卡"},"dailySteps":{"type":"integer","description":"今日累计步数","sampleValue":2031}}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":20,"clip":true,"backgroundColor":"#FFF0FFE6"},["content"]]
["content","Column",{"width":"matchParent","height":"matchParent","padding":12,"justifyContent":"spaceBetween"},["title","metrics"]]
["title","Text",{"content":"我的健康数据","width":296,"height":22,"fontSize":18,"fontWeight":700,"fontColor":"#9952991F","maxLines":1}]
["metrics","Row",{"width":296,"height":84,"justifyContent":"spaceBetween","alignItems":"center"},["metric0","sep0","metric1","sep1","metric2"]]
["metric0","Column",{"width":96,"height":84,"itemMargin":4,"justifyContent":"center","alignItems":"center"},["label0","value0"]]
["label0","Text",{"content":"睡眠得分","width":96,"fontSize":12,"fontWeight":400,"fontColor":"#9952991F","textAlign":"center","maxLines":1}]
["value0","Text",{"content":"{{ ${/data/healthSport/sleepScore} + '分' }}","width":96,"fontSize":20,"fontWeight":700,"fontColor":"#FF52991F","textAlign":"center","maxLines":1}]
["sep0","Divider",{"width":1,"height":64,"vertical":true,"color":"#5952991F"}]
["metric1","Column",{"width":96,"height":84,"itemMargin":4,"justifyContent":"center","alignItems":"center"},["label1","value1"]]
["label1","Text",{"content":"消耗热量","width":96,"fontSize":12,"fontWeight":400,"fontColor":"#9952991F","textAlign":"center","maxLines":1}]
["value1","Text",{"content":{"path":"/data/healthSport/dailyTotalCaloriesText"},"width":96,"fontSize":20,"fontWeight":700,"fontColor":"#FF52991F","textAlign":"center","maxLines":1}]
["sep1","Divider",{"width":1,"height":64,"vertical":true,"color":"#5952991F"}]
["metric2","Column",{"width":96,"height":84,"itemMargin":4,"justifyContent":"center","alignItems":"center"},["label2","value2"]]
["label2","Text",{"content":"今日步数","width":96,"fontSize":12,"fontWeight":400,"fontColor":"#9952991F","textAlign":"center","maxLines":1}]
["value2","Text",{"content":"{{ ${/data/healthSport/dailySteps} + '步' }}","width":96,"fontSize":20,"fontWeight":700,"fontColor":"#FF52991F","textAlign":"center","maxLines":1}]
["/data/healthSport/sleepScore",80]
["/data/healthSport/dailyTotalCaloriesText","92 千卡"]
["/data/healthSport/dailySteps",2031]
```
## 示例十三（2x4-V06）：无标题设备电量四联（W8-quad-cells·青色纯色）
### user
```json
{"userQuery":"无标题显示手机、左耳、右耳和耳机盒电量，使用2×2等分格。","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"phoneBattery":{"batterySOC":{"type":"integer","description":"手机电量百分比0到100","sampleValue":68},"batterySOCText":{"type":"string","description":"手机电量文本","sampleValue":"68%"},"batteryCapacityLevelDesc":{"type":"string","description":"手机电量等级","sampleValue":"正常电量"}},"earphone":{"leftBatteryLevel":{"type":"integer","description":"左耳电量0到100","sampleValue":76},"leftChargingStatusDesc":{"type":"string","description":"左耳充电状态","sampleValue":"未充电"},"rightBatteryLevel":{"type":"integer","description":"右耳电量0到100","sampleValue":78},"rightChargingStatusDesc":{"type":"string","description":"右耳充电状态","sampleValue":"未充电"},"batteryLevel":{"type":"integer","description":"耳机盒电量0到100","sampleValue":80},"chargingStatusDesc":{"type":"string","description":"耳机盒充电状态","sampleValue":"未充电"}}}},"assetCandidates":[{"src":"resources/base/media/phone_fill.svg","description":"本地手机图标"},{"src":"resources/base/media/l_circle_fill.svg","description":"本地左耳图标"},{"src":"resources/base/media/r_circle_fill.svg","description":"本地右耳图标"},{"src":"resources/base/media/earphone_case_16644.svg","description":"本地耳机盒图标"}]}
```
### assistant
```genui
["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":20,"clip":true,"backgroundColor":"#FFE6FDFF"},["grid"]]
["grid","Column",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":8},["row0","row1"]]
["row0","Row",{"width":296,"height":64,"itemMargin":8},["phoneCell","leftCell"]]
["row1","Row",{"width":296,"height":64,"itemMargin":8},["rightCell","caseCell"]]
["phoneCell","Row",{"width":144,"height":64,"padding":12,"borderRadius":16,"backgroundColor":"#1A1F8F99","justifyContent":"spaceBetween","alignItems":"center"},["phoneText","phoneRing"]]
["phoneText","Column",{"width":64,"itemMargin":2},["phoneValue","phoneStatus"]]
["phoneValue","Text",{"content":{"path":"/data/phoneBattery/batterySOCText"},"width":64,"fontSize":16,"fontWeight":700,"fontColor":"#FF1F8F99","maxLines":1}]
["phoneStatus","Text",{"content":{"path":"/data/phoneBattery/batteryCapacityLevelDesc"},"width":64,"fontSize":10,"fontWeight":400,"fontColor":"#991F8F99","maxLines":1}]
["phoneRing","Stack",{"width":40,"height":40,"alignContent":"center"},["phoneArc","phoneCore"]]
["phoneArc","Progress",{"type":"ring","width":40,"height":40,"strokeWidth":4,"value":{"path":"/data/phoneBattery/batterySOC"},"total":100,"color":"#FF1F8F99","backgroundColor":"#331F8F99"}]
["phoneCore","Image",{"src":"resources/base/media/phone_fill.svg","width":16,"height":16,"objectFit":"contain","fillColor":"#FF1F8F99"}]
["leftCell","Row",{"width":144,"height":64,"padding":12,"borderRadius":16,"backgroundColor":"#1A1F8F99","justifyContent":"spaceBetween","alignItems":"center"},["leftText","leftRing"]]
["leftText","Column",{"width":64,"itemMargin":2},["leftValue","leftStatus"]]
["leftValue","Text",{"content":"{{ ${/data/earphone/leftBatteryLevel} + '%' }}","width":64,"fontSize":16,"fontWeight":700,"fontColor":"#FF1F8F99","maxLines":1}]
["leftStatus","Text",{"content":{"path":"/data/earphone/leftChargingStatusDesc"},"width":64,"fontSize":10,"fontWeight":400,"fontColor":"#991F8F99","maxLines":1}]
["leftRing","Stack",{"width":40,"height":40,"alignContent":"center"},["leftArc","leftCore"]]
["leftArc","Progress",{"type":"ring","width":40,"height":40,"strokeWidth":4,"value":{"path":"/data/earphone/leftBatteryLevel"},"total":100,"color":"#FF1F8F99","backgroundColor":"#331F8F99"}]
["leftCore","Image",{"src":"resources/base/media/l_circle_fill.svg","width":16,"height":16,"objectFit":"contain","fillColor":"#FF1F8F99"}]
["rightCell","Row",{"width":144,"height":64,"padding":12,"borderRadius":16,"backgroundColor":"#1A1F8F99","justifyContent":"spaceBetween","alignItems":"center"},["rightText","rightRing"]]
["rightText","Column",{"width":64,"itemMargin":2},["rightValue","rightStatus"]]
["rightValue","Text",{"content":"{{ ${/data/earphone/rightBatteryLevel} + '%' }}","width":64,"fontSize":16,"fontWeight":700,"fontColor":"#FF1F8F99","maxLines":1}]
["rightStatus","Text",{"content":{"path":"/data/earphone/rightChargingStatusDesc"},"width":64,"fontSize":10,"fontWeight":400,"fontColor":"#991F8F99","maxLines":1}]
["rightRing","Stack",{"width":40,"height":40,"alignContent":"center"},["rightArc","rightCore"]]
["rightArc","Progress",{"type":"ring","width":40,"height":40,"strokeWidth":4,"value":{"path":"/data/earphone/rightBatteryLevel"},"total":100,"color":"#FF1F8F99","backgroundColor":"#331F8F99"}]
["rightCore","Image",{"src":"resources/base/media/r_circle_fill.svg","width":16,"height":16,"objectFit":"contain","fillColor":"#FF1F8F99"}]
["caseCell","Row",{"width":144,"height":64,"padding":12,"borderRadius":16,"backgroundColor":"#1A1F8F99","justifyContent":"spaceBetween","alignItems":"center"},["caseText","caseRing"]]
["caseText","Column",{"width":64,"itemMargin":2},["caseValue","caseStatus"]]
["caseValue","Text",{"content":"{{ ${/data/earphone/batteryLevel} + '%' }}","width":64,"fontSize":16,"fontWeight":700,"fontColor":"#FF1F8F99","maxLines":1}]
["caseStatus","Text",{"content":{"path":"/data/earphone/chargingStatusDesc"},"width":64,"fontSize":10,"fontWeight":400,"fontColor":"#991F8F99","maxLines":1}]
["caseRing","Stack",{"width":40,"height":40,"alignContent":"center"},["caseArc","caseCore"]]
["caseArc","Progress",{"type":"ring","width":40,"height":40,"strokeWidth":4,"value":{"path":"/data/earphone/batteryLevel"},"total":100,"color":"#FF1F8F99","backgroundColor":"#331F8F99"}]
["caseCore","Image",{"src":"resources/base/media/earphone_case_16644.svg","width":16,"height":16,"objectFit":"contain","fillColor":"#FF1F8F99"}]
["/data/phoneBattery/batterySOC",68]
["/data/phoneBattery/batterySOCText","68%"]
["/data/phoneBattery/batteryCapacityLevelDesc","正常电量"]
["/data/earphone/leftBatteryLevel",76]
["/data/earphone/leftChargingStatusDesc","未充电"]
["/data/earphone/rightBatteryLevel",78]
["/data/earphone/rightChargingStatusDesc","未充电"]
["/data/earphone/batteryLevel",80]
["/data/earphone/chargingStatusDesc","未充电"]
```
## 示例十四（2x4-V07）：单列日程安排（W2-text-flow·黄色纯色）
### user
```json
{"userQuery":"展示下一项日程的标题、说明和日期，使用单列文本流。","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"calendar":{"events":[{"title":{"type":"string","description":"日程标题","sampleValue":"需求评审会"},"description":{"type":"string","description":"日程说明","sampleValue":"评审卡片数据接口与视觉还原结果"},"startDate":{"type":"string","description":"日程开始日期MM-DD","sampleValue":"12-18"}}]}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":20,"clip":true,"backgroundColor":"#FFFFF3E6"},["content"]]
["content","Column",{"width":"matchParent","height":"matchParent","padding":12,"justifyContent":"start"},["kicker","lower"]]
["kicker","Text",{"content":"日程安排","width":296,"fontSize":12,"fontWeight":400,"fontColor":"#9999661F","maxLines":1}]
["event","Column",{"width":296,"height":76,"itemMargin":6,"justifyContent":"end"},["eventTitle","eventDesc"]]
["eventTitle","Text",{"content":{"path":"/data/calendar/events/0/title"},"width":296,"fontSize":24,"fontWeight":700,"fontColor":"#FF99661F","maxLines":1}]
["eventDesc","Text",{"content":{"path":"/data/calendar/events/0/description"},"width":296,"height":34,"fontSize":10,"fontWeight":400,"fontColor":"#9999661F","maxLines":2}]
["lower","Column",{"width":296,"height":113,"justifyContent":"end"},["event","date"]]
["date","Text",{"content":{"path":"/data/calendar/events/0/startDate"},"width":296,"fontSize":10,"fontWeight":400,"fontColor":"#9999661F","maxLines":1}]
["/data/calendar/events/0/title","需求评审会"]
["/data/calendar/events/0/description","评审卡片数据接口与视觉还原结果"]
["/data/calendar/events/0/startDate","12-18"]
```
## 示例十五（2x4-V08）：下一日程与双真实入口（W6-agenda-cta·黄色纯色）
### user
```json
{"userQuery":"显示下一项日程的标题、地点和时间，并提供查看日程与专注模式两个入口。","size":"2x4","eventCandidates":[{"call":"clickToIntent","args":{"intentName":"ViewCalendarEvent","params":{"entityId":"{{ ${/data/calendar/events/0/entityId} }}"}}},{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"intelligent_scene_entry"}}],"dataModelSchema":{"data":{"calendar":{"events":[{"title":{"type":"string","description":"日程标题","sampleValue":"需求评审会"},"eventLocation":{"type":"string","description":"日程地点","sampleValue":"五和大道华为基地"},"dtStart":{"type":"string","description":"开始时间","sampleValue":"14:00"},"dtEnd":{"type":"string","description":"结束时间","sampleValue":"15:30"},"entityId":{"type":"string","description":"日程实体ID","sampleValue":"calendar-event-001"}}]}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":20,"clip":true,"backgroundColor":"#FFFFF3E6"},["content"]]
["content","Column",{"width":"matchParent","height":"matchParent","padding":12,"justifyContent":"spaceBetween"},["kicker","event","actions"]]
["kicker","Text",{"content":"下一个日程","width":296,"fontSize":12,"fontWeight":400,"fontColor":"#9999661F","maxLines":1}]
["event","Column",{"width":296,"height":48,"itemMargin":4},["eventName","eventTime"]]
["eventName","Text",{"content":"{{ ${/data/calendar/events/0/title} + '·' + ${/data/calendar/events/0/eventLocation} }}","width":296,"fontSize":18,"fontWeight":700,"fontColor":"#FF99661F","maxLines":1}]
["eventTime","Text",{"content":"{{ ${/data/calendar/events/0/dtStart} + ' - ' + ${/data/calendar/events/0/dtEnd} }}","width":296,"fontSize":12,"fontWeight":400,"fontColor":"#9999661F","maxLines":1}]
["actions","Row",{"width":296,"height":36,"justifyContent":"spaceBetween"},["calendarButton","focusButton"]]
["calendarButton","Button",{"label":"查看日程","width":140,"height":36,"borderRadius":18,"backgroundColor":"#3399661F","fontColor":"#FF99661F","fontSize":12,"fontWeight":500,"onClick":[{"call":"clickToIntent","args":{"intentName":"ViewCalendarEvent","params":{"entityId":"{{ ${/data/calendar/events/0/entityId} }}"}}}]}]
["focusButton","Button",{"label":"专注模式","width":140,"height":36,"borderRadius":18,"backgroundColor":"#3399661F","fontColor":"#FF99661F","fontSize":12,"fontWeight":500,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"intelligent_scene_entry"}}]}]
["/data/calendar/events/0/title","需求评审会"]
["/data/calendar/events/0/eventLocation","五和大道华为基地"]
["/data/calendar/events/0/dtStart","14:00"]
["/data/calendar/events/0/dtEnd","15:30"]
["/data/calendar/events/0/entityId","calendar-event-001"]
```
