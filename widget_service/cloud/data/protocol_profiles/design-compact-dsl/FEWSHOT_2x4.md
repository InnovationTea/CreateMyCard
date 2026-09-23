# 2x4 Few-shot

示例中的数据路径、事件和素材候选取自能力清单；真实输出只能使用当前 TaskSpec 实际提供的 path、icon 和 onClick。示例用于参考布局，浅色示例使用同色相微渐变、80% 白色内容背板和同色相 60% 透明度辅助文字；背景选择、业务映射及内容配色统一遵循 PROMPT.md 第十二节；用户明确配色要求优先，未指定时不得沿用旧纯色和同色背板或自由取色。融球示例仅在本次尺寸、业务、密度和运行时条件均满足时使用，否则按主业务切换到对应浅色微渐变及配套内容色。

2x4 最终恰好两个业务数据块时先判断主次：存在一个明确主焦点、其余必要内容能压入两个辅助槽时使用 V04 的 W1-focus-aux；只有两个业务等权且都需要完整内容区时才使用 W9。W9 若业务组合与 V09 的天气+手机电量一致，可以参考 V09 的内容组织；其它等权组合只参考 W9 结构硬约束，不复制 V09 的业务语义。W9 root 必须是 Row、`padding:8`，并直接使用左右两个 `138×134vp` 大内容背板，不生成公共标题、公共内容区或公共按钮行，每个业务的数据和按钮只放在所属背板内。禁止复用 2x2 S4，禁止 `root Stack -> content Column`，禁止生成上下两个全宽背板或任何其它上下双业务布局。

2x4 的外框固定不等于内部内容固定。先为每个背板选择一个主焦点变体：`value-led` 让数值占据第一视觉位置，使用纯数字与小号单位；`status-led` 让核心状态句成为最大文字；`event-led` 让事项标题与时间形成连续信息组；`action-led` 让唯一明确动作沉底但不压过主状态；字段较多时使用 `dense-summary`，只保留一项主值和必要辅助。除 W8/W9/W10 的固定区域边界外，允许改变内部顺序、对齐、留白和是否保留弱字段，禁止每个分区机械复用“标题 + 两行 14/12fp”。普通窄行最多合并两个能完整显示的短事实，三个以上动态字段必须拆行或删去最低优先级字段；多日天气的单日摘要除外。同一 Row 内存在不同字号 Text 时，Row 一律使用 `alignItems:"bottom"`，较小 Text 不设置 `padding.bottom`，由 Row 直接统一文字底边。

同行不同字号 Text 的可见字底统一使用封顶补偿：Row 写 `alignItems:"bottom"`，较小 Text 的 `padding.bottom` 使用 `min(4, round((最大字号-自身字号)/2))`，最多 `4vp`；数字与单位 Row 另写 `itemMargin:2` 并移除二者固定宽度。本条覆盖上文“不设置 padding.bottom”的旧描述。

2x4 单业务不要默认把内容平均摊满高度：先让主值或主状态占据连续的视觉区域，再把单位、状态和辅助指标贴近主焦点。只有用户明确要求多个并列指标时才使用等权布局；如果一个字段能回答主要问题，宁可保留稳定留白，也不要添加重复标签、空背板或弱装饰。

事件候选只是可用动作范围，不等于必须生成按钮；只有 `userQuery` 明确要求查看、加入、设置、导航等显式入口且存在匹配事件时，才参考 W6/V08 的双入口构图。若候选是与当前业务严格匹配且无副作用的详情入口，即使 query 很简短，也可以把整卡或所属分区作为唯一点击入口；不要为了显示入口额外增加按钮。动作槽只保留一个完整命令，禁止再用第二行重复“点击打开”“进入设置”等同义提示。没有明确动作时优先保留业务主焦点和稳定留白。

图标与动作必须逐一匹配当前对象和真实目标；候选中允许存在干扰项。示例里的动作不是业务默认配置，跨业务组合只在用户明确要求时保留。没有准确图标就用纯文字；不要按分区数复制共享动作。

## 示例零（2x4-V00）：中性单业务骨架（未知业务回退）
本例只提供 2x4 的主信息、辅助信息和稳定留白，不携带天气、设备、健康或日程语义。未知业务、字段含义不足或多业务组合无法匹配已知示例时，只参考本例的结构，不复制“主信息”等文案。
### user
```json
{"userQuery":"生成一张信息卡片","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"view":{"primary":{"type":"string","description":"主要展示值","sampleValue":"示例值"},"secondary":{"type":"string","description":"辅助展示值","sampleValue":"辅助信息"}}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["content"]]
["content","Column",{"width":"matchParent","height":"matchParent","padding":12,"justifyContent":"center","alignItems":"start","itemMargin":8},["primary","secondary"]]
["primary","Text",{"content":{"path":"/data/view/primary"},"width":276,"fontSize":18,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["secondary","Text",{"content":{"path":"/data/view/secondary"},"width":276,"fontSize":14,"fontWeight":400,"fontColor":"#991F4799","maxLines":2}]
["/data/view/primary","示例值"]
["/data/view/secondary","辅助信息"]
```

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
["list","Column",{"width":276,"height":102,"itemMargin":8,"alignItems":"start"},["item0","item1","item2"]]
["item0","Row",{"width":276,"height":28,"padding":{"left":12,"right":12},"borderRadius":8,"backgroundColor":"#99FFFFFF","alignItems":"center"},["text0"]]
["text0","Text",{"content":{"path":"/data/calendar/events/0/title"},"width":228,"fontSize":12,"fontWeight":400,"fontColor":"#FF8C4B1C","maxLines":1}]
["item1","Row",{"width":276,"height":28,"padding":{"left":12,"right":12},"borderRadius":8,"backgroundColor":"#99FFFFFF","alignItems":"center"},["text1"]]
["text1","Text",{"content":{"path":"/data/calendar/events/1/title"},"width":228,"fontSize":12,"fontWeight":400,"fontColor":"#FF8C4B1C","maxLines":1}]
["item2","Row",{"width":276,"height":28,"padding":{"left":12,"right":12},"borderRadius":8,"backgroundColor":"#99FFFFFF","alignItems":"center"},["text2"]]
["text2","Text",{"content":{"path":"/data/calendar/events/2/title"},"width":228,"fontSize":12,"fontWeight":400,"fontColor":"#FF8C4B1C","maxLines":1}]
["/data/calendar/events/0/title","项目阶段性汇报"]
["/data/calendar/events/1/title","确认Q3设计需求"]
["/data/calendar/events/2/title","申请下周出差"]
```
## 示例九（2x4-V02）：手机电量大环与右侧说明（W3-ring-detail·蓝色微渐变）
### user
```json
{"userQuery":"做张手机电量卡片，让我一眼看清还剩多少电，电量是否正常、有没有在充电。","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"phoneBattery":{"batterySOC":{"type":"integer","description":"0到100的手机电量百分比","sampleValue":68},"batterySOCText":{"type":"string","description":"格式化电量文本","sampleValue":"68%"},"batteryCapacityLevelDesc":{"type":"string","description":"电量等级","sampleValue":"正常电量"},"chargingStatusDesc":{"type":"string","description":"充电状态","sampleValue":"未充电"}}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":20,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["content"]]
["content","Column",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":2,"justifyContent":"start","alignItems":"start"},["title","main"]]
["title","CardHeader",{"title":"手机电量","fontColor":"#FF1F4799"}]
["main","Row",{"width":296,"height":113,"itemMargin":8,"alignItems":"center"},["ringArea","info"]]
["ringArea","Column",{"width":144,"height":113,"justifyContent":"center","alignItems":"center"},["ringStack"]]
["ringStack","Stack",{"width":92,"height":92,"alignContent":"center"},["ring","ringValue"]]
["ring","Progress",{"type":"ring","width":92,"height":92,"strokeWidth":8,"value":{"path":"/data/phoneBattery/batterySOC"},"total":100,"color":"#FF1F4799","backgroundColor":"#331F4799"}]
["ringValue","Text",{"content":{"path":"/data/phoneBattery/batterySOCText"},"width":76,"fontSize":18,"fontWeight":700,"fontColor":"#FF1F4799","textAlign":"center","maxLines":1}]
["info","Column",{"width":144,"height":113,"itemMargin":4,"justifyContent":"center"},["infoTitle","level","status"]]
["infoTitle","Text",{"content":"当前电量","width":144,"fontSize":16,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["level","Text",{"content":{"path":"/data/phoneBattery/batteryCapacityLevelDesc"},"width":144,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["status","Text",{"content":{"path":"/data/phoneBattery/chargingStatusDesc"},"width":144,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
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
["body","Column",{"width":276,"height":98,"itemMargin":8,"alignItems":"start"},["progressSlot","details"]]
["progressSlot","Column",{"width":276,"height":45,"itemMargin":4,"justifyContent":"center","alignItems":"start"},["progressText","progress"]]
["progressText","Row",{"width":276,"alignItems":"bottom","itemMargin":6},["score","scoreLabel"]]
["score","Text",{"content":"{{ ${/data/healthSport/sleepScore} + '分' }}","fontSize":18,"fontWeight":700,"fontColor":"#FF563D99","maxLines":1}]
["scoreLabel","Text",{"content":"睡眠综合得分","fontSize":12,"fontWeight":400,"fontColor":"#FF563D99","padding":{"bottom":3},"maxLines":1}]
["progress","Progress",{"type":"linear","width":276,"height":8,"strokeWidth":8,"borderRadius":4,"value":{"path":"/data/healthSport/sleepScore"},"total":100,"color":"#FF563D99","backgroundColor":"#33563D99"}]
["details","Row",{"width":276,"height":45,"itemMargin":8},["night","deep"]]
["night","Column",{"width":134,"height":45,"padding":{"left":8,"right":8,"top":6,"bottom":6},"borderRadius":10,"backgroundColor":"#99FFFFFF","itemMargin":2,"justifyContent":"center"},["nightLabel","nightValue"]]
["nightLabel","Text",{"content":"睡眠时长","width":118,"fontSize":12,"fontWeight":400,"fontColor":"#FF563D99","maxLines":1}]
["nightValue","Text",{"content":{"path":"/data/healthSport/nightSleepDurationText"},"width":118,"fontSize":12,"fontWeight":400,"fontColor":"#FF563D99","maxLines":1}]
["deep","Column",{"width":134,"height":45,"padding":{"left":8,"right":8,"top":6,"bottom":6},"borderRadius":10,"backgroundColor":"#99FFFFFF","itemMargin":2,"justifyContent":"center"},["deepLabel","deepValue"]]
["deepLabel","Text",{"content":"深睡时长","width":118,"fontSize":12,"fontWeight":400,"fontColor":"#FF563D99","maxLines":1}]
["deepValue","Text",{"content":{"path":"/data/healthSport/deepSleepDurationText"},"width":118,"fontSize":12,"fontWeight":400,"fontColor":"#FF563D99","maxLines":1}]
["/data/healthSport/sleepScore",82]
["/data/healthSport/nightSleepDurationText","7小时1分"]
["/data/healthSport/deepSleepDurationText","2小时15分"]
```
## 示例十一（2x4-V04）：睡眠得分与双详情（W1-focus-aux·var-a 双辅助区域·紫色微渐变）

本例的固定结构是“左侧唯一主焦点 + 右侧上下两个辅助背板”，不是 Progress 专用布局。左侧可以按真实业务替换为大数字、环形进度、最多三项的事项列表或一条突出状态；value/ring-focus 的三层信息使用“顶部上下文 + 中部弹性居中的主焦点 + 底部支撑信息”，纯文字 status-focus 的 2-4 行短文本则组成一个紧凑 Column 整体垂直居中，不能全部堆在顶部。只有一个主信息组、最多再加一条短辅助信息时，内容组同时水平和垂直居中。事项列表、长提醒正文和真正的多行摘要仍保持左对齐；底部存在两个短支撑事实且高度充足时分别占两行，不要为了减少 Text 用 `|` 挤成一行。左侧最多只有一个 20fp 以上主焦点，同级步数、温度或心率不能同时放大；普通数值/文字焦点不添加装饰图标，只有合法环形 Progress 的中心图标例外。右侧每个 `130×59vp` 背板只放一项辅助指标、一组紧密相关的两行状态摘要或动作；使用图标时统一采用“最多两行文字在左、20vp 图标在右”的固定结构。右侧无论是否带图标，文字 Column 和 Text 始终左对齐，只让整个文字组垂直居中；只有一个有效状态时只显示一行，不用重复状态或无关更新时间填满槽位。左右耳等天然成对对象可各占一行，每行最多两个事实。示例中的线性 Progress 与可见睡眠得分共同组成主焦点，任何 Progress 都不能单独代替数值读数。动作进入右侧辅助背板并绑定整个背板，不另加满宽底部按钮。

W1 的左侧与右侧必须先分配字段再生成，禁止同一路径或同一事实左右重复。value-led 左侧最多三个视觉层，event/status/dense-summary 左侧最多四个 Text；超出的必要事实优先进入空闲辅助槽，仍放不下时删除最低优先级弱字段。Progress.value 只绑定 number/integer；只有 `batterySOCText:"68%"` 等格式化字符串时，保留完整 Text 主读数并删除 Progress，不能输出只有轨道的空环。
### user
```json
{"userQuery":"帮我做张睡眠卡片，我最关心昨晚睡眠得了多少分，也想看看睡了多久、其中深睡多久。","size":"2x4","eventCandidates":[],"assetCandidates":[],"dataModelSchema":{"data":{"healthSport":{"sleepScore":{"type":"integer","description":"0到100的睡眠综合得分","sampleValue":82},"nightSleepDurationText":{"type":"string","description":"包含单位的夜间睡眠时长","sampleValue":"7小时1分"},"deepSleepDurationText":{"type":"string","description":"包含单位的深睡时长","sampleValue":"2小时15分"}}}}}
```
### assistant
```genui
["root","Row",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":20,"clip":true,"itemMargin":10,"justifyContent":"center","alignItems":"center","linearGradient":{"direction":"RightBottom","colors":[["#FFDBCCFF",0],["#FFF6F2FF",1]]}},["hero","details"]]
["hero","Column",{"width":136,"height":126,"itemMargin":8,"alignItems":"center"},["reading","bar"]]
["reading","Column",{"width":136,"layoutWeight":1,"justifyContent":"center","alignItems":"center","itemMargin":4},["valueRow","label"]]
["valueRow","Row",{"width":136,"itemMargin":4,"justifyContent":"center","alignItems":"bottom"},["value","unit"]]
["value","Text",{"content":{"path":"/data/healthSport/sleepScore"},"fontSize":38,"fontWeight":700,"fontColor":"#FF563D99","maxLines":1}]
["label","Text",{"content":"睡眠得分 / 100分","width":136,"fontSize":12,"fontWeight":400,"fontColor":"#FF563D99","textAlign":"center","maxLines":1}]
["bar","Progress",{"type":"linear","width":136,"height":8,"strokeWidth":8,"value":{"path":"/data/healthSport/sleepScore"},"total":100,"color":"#FF563D99","backgroundColor":"#33563D99"}]
["details","Column",{"width":130,"height":126,"itemMargin":8},["night","deep"]]
["unit","Text",{"content":"分","fontSize":12,"fontWeight":400,"fontColor":"#FF563D99","padding":{"bottom":4},"maxLines":1}]
["night","Column",{"width":130,"height":59,"padding":10,"borderRadius":12,"backgroundColor":"#99FFFFFF","itemMargin":4,"justifyContent":"center"},["nightLabel","nightValue"]]
["nightLabel","Text",{"content":"夜间睡眠","width":110,"fontSize":12,"fontWeight":400,"fontColor":"#FF563D99","maxLines":1}]
["nightValue","Text",{"content":{"path":"/data/healthSport/nightSleepDurationText"},"width":110,"fontSize":12,"fontWeight":400,"fontColor":"#FF563D99","maxLines":1}]
["deep","Column",{"width":130,"height":59,"padding":10,"borderRadius":12,"backgroundColor":"#99FFFFFF","itemMargin":4,"justifyContent":"center"},["deepLabel","deepValue"]]
["deepLabel","Text",{"content":"深睡时长","width":110,"fontSize":12,"fontWeight":400,"fontColor":"#FF563D99","maxLines":1}]
["deepValue","Text",{"content":{"path":"/data/healthSport/deepSleepDurationText"},"width":110,"fontSize":12,"fontWeight":400,"fontColor":"#FF563D99","maxLines":1}]
["/data/healthSport/sleepScore",82]
["/data/healthSport/nightSleepDurationText","7小时1分"]
["/data/healthSport/deepSleepDurationText","2小时15分"]
```
## 示例十二（2x4-V05）：健康三指标（W4-metric-triple·紫色微渐变）
### user
```json
{"userQuery":"做张健康卡片，把睡眠得分、今天消耗的热量和走的步数放在一起，方便我随时看看。","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"healthSport":{"sleepScore":{"type":"integer","description":"0到100的睡眠得分","sampleValue":80},"dailyTotalCaloriesText":{"type":"string","description":"含单位的今日总消耗热量","sampleValue":"92 千卡"},"dailySteps":{"type":"integer","description":"今日累计步数","sampleValue":2031}}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":20,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFDBCCFF",0],["#FFF6F2FF",1]]}},["content"]]
["content","Column",{"width":"matchParent","height":"matchParent","padding":12,"justifyContent":"spaceBetween","alignItems":"start"},["title","metrics"]]
["title","CardHeader",{"title":"我的健康数据","fontColor":"#FF563D99"}]
["metrics","Row",{"width":296,"height":84,"justifyContent":"spaceBetween","alignItems":"center"},["metric0","sep0","metric1","sep1","metric2"]]
["metric0","Column",{"width":96,"height":84,"itemMargin":4,"justifyContent":"center","alignItems":"center"},["value0","label0"]]
["label0","Text",{"content":"睡眠得分","width":96,"fontSize":12,"fontWeight":400,"fontColor":"#FF563D99","textAlign":"center","maxLines":1}]
["value0","Text",{"content":"{{ ${/data/healthSport/sleepScore} + '分' }}","width":96,"fontSize":18,"fontWeight":700,"fontColor":"#FF563D99","textAlign":"center","maxLines":1}]
["sep0","Divider",{"width":1,"height":64,"vertical":true,"color":"#33563D99"}]
["metric1","Column",{"width":96,"height":84,"itemMargin":4,"justifyContent":"center","alignItems":"center"},["value1","label1"]]
["label1","Text",{"content":"消耗热量","width":96,"fontSize":12,"fontWeight":400,"fontColor":"#FF563D99","textAlign":"center","maxLines":1}]
["value1","Text",{"content":{"path":"/data/healthSport/dailyTotalCaloriesText"},"width":96,"fontSize":18,"fontWeight":700,"fontColor":"#FF563D99","textAlign":"center","maxLines":1}]
["sep1","Divider",{"width":1,"height":64,"vertical":true,"color":"#33563D99"}]
["metric2","Column",{"width":96,"height":84,"itemMargin":4,"justifyContent":"center","alignItems":"center"},["value2","label2"]]
["label2","Text",{"content":"今日步数","width":96,"fontSize":12,"fontWeight":400,"fontColor":"#FF563D99","textAlign":"center","maxLines":1}]
["value2","Text",{"content":"{{ ${/data/healthSport/dailySteps} + '步' }}","width":96,"fontSize":18,"fontWeight":700,"fontColor":"#FF563D99","textAlign":"center","maxLines":1}]
["/data/healthSport/sleepScore",80]
["/data/healthSport/dailyTotalCaloriesText","92 千卡"]
["/data/healthSport/dailySteps",2031]
```
## 示例十三（2x4-V06）：无标题四业务速览（W8-quad-cells·蓝色微渐变）
W8 四数据布局自身固定无卡级标题，不依赖用户额外提出“无标题”；root 固定 `padding:8`，四个 `138×63vp` 小内容背板必须占满 `284×134vp` 安全内容区，不为 header 压缩高度。
### user
```json
{"userQuery":"帮我做张卡片，一起看看现在的气温、手机和耳机盒还剩多少电，还有下一场日程几点开始。","size":"2x4","eventCandidates":[],"assetCandidates":[],"dataModelSchema":{"data":{"weather":{"current":{"temperatureText":{"type":"string","description":"含单位的当前温度","sampleValue":"26°C"}}},"phoneBattery":{"batterySOCText":{"type":"string","description":"含单位的手机电量","sampleValue":"68%"}},"earphone":{"batteryLevel":{"type":"integer","description":"耳机盒电量百分比0到100","sampleValue":80}},"calendar":{"events":[{"dtStart":{"type":"string","description":"开始时间","sampleValue":"14:00"}}]}}}}
```
### assistant
```genui
["root","Column",{"width":"matchParent","height":"matchParent","padding":8,"borderRadius":20,"clip":true,"alignItems":"center","itemMargin":8,"linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["top","bottom"]]
["top","Row",{"width":284,"height":63,"itemMargin":8},["weather","phone"]]
["bottom","Row",{"width":284,"height":63,"itemMargin":8},["ear","calendar"]]
["weather","Column",{"width":138,"height":63,"padding":12,"borderRadius":16,"backgroundColor":"#99FFFFFF","itemMargin":2,"justifyContent":"center"},["weatherValue","weatherLabel"]]
["weatherValue","Text",{"content":{"path":"/data/weather/current/temperatureText"},"width":114,"fontSize":14,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["weatherLabel","Text",{"content":"天气","width":114,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["/data/weather/current/temperatureText","26°C"]
["phone","Column",{"width":138,"height":63,"padding":12,"borderRadius":16,"backgroundColor":"#99FFFFFF","itemMargin":2,"justifyContent":"center"},["phoneValue","phoneLabel"]]
["phoneValue","Text",{"content":{"path":"/data/phoneBattery/batterySOCText"},"width":114,"fontSize":14,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["phoneLabel","Text",{"content":"手机电量","width":114,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["/data/phoneBattery/batterySOCText","68%"]
["ear","Column",{"width":138,"height":63,"padding":12,"borderRadius":16,"backgroundColor":"#99FFFFFF","itemMargin":2,"justifyContent":"center"},["earValue","earLabel"]]
["earValue","Text",{"content":"{{ ${/data/earphone/batteryLevel} + '%' }}","width":114,"fontSize":14,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["earLabel","Text",{"content":"耳机盒","width":114,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["/data/earphone/batteryLevel",80]
["calendar","Column",{"width":138,"height":63,"padding":12,"borderRadius":16,"backgroundColor":"#99FFFFFF","itemMargin":2,"justifyContent":"center"},["calendarValue","calendarLabel"]]
["calendarValue","Text",{"content":{"path":"/data/calendar/events/0/dtStart"},"width":114,"fontSize":14,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["calendarLabel","Text",{"content":"日程开始","width":114,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
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
["kicker","Text",{"content":"日程安排","width":276,"fontSize":12,"fontWeight":400,"fontColor":"#FF8C4B1C","maxLines":1}]
["event","Column",{"width":276,"height":66,"itemMargin":6,"justifyContent":"end","alignItems":"start"},["eventTitle","eventDesc"]]
["eventTitle","Text",{"content":{"path":"/data/calendar/events/0/title"},"width":276,"fontSize":18,"fontWeight":500,"fontColor":"#FF8C4B1C","maxLines":1}]
["eventDesc","Text",{"content":{"path":"/data/calendar/events/0/description"},"width":276,"height":34,"fontSize":12,"fontWeight":400,"fontColor":"#FF8C4B1C","maxLines":2}]
["lower","Column",{"width":276,"height":103,"justifyContent":"end","alignItems":"start"},["event","date"]]
["date","Text",{"content":{"path":"/data/calendar/events/0/startDate"},"width":276,"fontSize":12,"fontWeight":400,"fontColor":"#FF8C4B1C","maxLines":1}]
["/data/calendar/events/0/title","需求评审会"]
["/data/calendar/events/0/description","评审卡片数据接口与视觉还原结果"]
["/data/calendar/events/0/startDate","12-18"]
```
## 示例十五（2x4-V08）：下一日程与双真实入口（W6-agenda-cta·左焦点右双入口·黄色微渐变）
### user
```json
{"userQuery":"做张日程提醒卡片，看看下一件事是什么、在哪里、几点开始和结束，再放上查看这条日程和打开专注设置的按钮。","size":"2x4","eventCandidates":[{"call":"clickToIntent","args":{"intentName":"ViewCalendarEvent","params":{"entityId":"{{ ${/data/calendar/events/0/entityId} }}"}}},{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"intelligent_scene_entry"}}],"dataModelSchema":{"data":{"calendar":{"events":[{"title":{"type":"string","description":"日程标题","sampleValue":"需求评审会"},"eventLocation":{"type":"string","description":"日程地点","sampleValue":"五和大道华为基地"},"dtStart":{"type":"string","description":"开始时间","sampleValue":"14:00"},"dtEnd":{"type":"string","description":"结束时间","sampleValue":"15:30"},"entityId":{"type":"string","description":"日程实体ID","sampleValue":"calendar-event-001"}}]}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Row",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":20,"clip":true,"itemMargin":10,"justifyContent":"center","alignItems":"center","linearGradient":{"direction":"RightBottom","colors":[["#FFFFE0CC",0],["#FFFFF7F2",1]]}},["focus","actions"]]
["focus","Column",{"width":136,"height":126,"itemMargin":4,"justifyContent":"start","alignItems":"start"},["kicker","eventBody","eventLocation"]]
["kicker","Text",{"content":"下一个日程","width":136,"fontSize":12,"fontWeight":400,"fontColor":"#998C4B1C","maxLines":1}]
["eventBody","Column",{"width":136,"layoutWeight":1,"itemMargin":4,"justifyContent":"center","alignItems":"start"},["eventName","eventTime"]]
["eventName","Text",{"content":{"path":"/data/calendar/events/0/title"},"width":136,"fontSize":18,"fontWeight":700,"fontColor":"#FF8C4B1C","maxLines":1}]
["eventTime","Text",{"content":"{{ ${/data/calendar/events/0/dtStart} + ' - ' + ${/data/calendar/events/0/dtEnd} }}","width":136,"fontSize":12,"fontWeight":400,"fontColor":"#FF8C4B1C","maxLines":1}]
["eventLocation","Text",{"content":{"path":"/data/calendar/events/0/eventLocation"},"width":136,"fontSize":12,"fontWeight":400,"fontColor":"#998C4B1C","maxLines":1}]
["actions","Column",{"width":130,"height":126,"itemMargin":8},["calendarAction","focusAction"]]
["calendarAction","Row",{"width":130,"height":59,"padding":{"left":12,"right":12},"borderRadius":12,"backgroundColor":"#99FFFFFF","justifyContent":"start","alignItems":"center","onClick":[{"call":"clickToIntent","args":{"intentName":"ViewCalendarEvent","params":{"entityId":"{{ ${/data/calendar/events/0/entityId} }}"}}}]},["calendarLabel"]]
["calendarLabel","Text",{"content":"查看日程","width":106,"fontSize":14,"fontWeight":500,"fontColor":"#FF8C4B1C","textAlign":"start","maxLines":1}]
["focusAction","Row",{"width":130,"height":59,"padding":{"left":12,"right":12},"borderRadius":12,"backgroundColor":"#99FFFFFF","justifyContent":"start","alignItems":"center","onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"intelligent_scene_entry"}}]},["focusLabel"]]
["focusLabel","Text",{"content":"专注模式","width":106,"fontSize":14,"fontWeight":500,"fontColor":"#FF8C4B1C","textAlign":"start","maxLines":1}]
["/data/calendar/events/0/title","需求评审会"]
["/data/calendar/events/0/eventLocation","五和大道华为基地"]
["/data/calendar/events/0/dtStart","14:00"]
["/data/calendar/events/0/dtEnd","15:30"]
["/data/calendar/events/0/entityId","calendar-event-001"]
```

## 示例十六（2x4-V09）：天气与手机电量双业务（W9-dual-backboards·蓝色微渐变）
W9 先按对象合并字段再布局：同一耳机的连接状态、耳机仓电量和充电状态只能共同放在一个背板，不能拆成右侧两个小背板来伪造 W10；action 不增加数据块，也不能为了放按钮改变骨架或把音乐动作放进天气背板。两个业务只能左右排列，禁止改成上下两个全宽背板。每个大背板在排除自己的 `12fp/400` 业务标题和底部 action 后，独立选择内容变体并遵守 2x2 的 `150×150vp` 内容密度：大数字主值后最多一条辅助信息，纯文字最多一条突出信息和两条辅助信息，并行数据最多三条普通字号完整信息。无动作的倒计时大背板固定直接包含目标标题、`30fp/38fp` 纯数字、单位“天”三个 Text，使用 `justifyContent:"spaceBetween"`、`alignItems:"center"` 和全宽居中 Text 形成均衡的三层留白；禁止嵌套 content/readout Column、增加第四行或借用另一个业务根的字段。多日天气每一天合并成一行 `12fp/400` 文本，同日同时有完整日期和星期时只保留星期，再按天气、温度、降雨顺序保留能完整显示的字段；不拆成多行，也不在日期间增加 Divider。
归属示范：音乐入口和音乐/闹钟素材是干扰候选，不属于本轮明确的天气、电量需求，全部舍弃。天气与电池按钮分别保留在所属背板，缺少准确图标时使用纯文字，不能为左右对称复制同一动作。动作参数引用的数据根必须与所在背板的数据根一致，例如引用 `/data/weather/` 的按钮必须放在天气背板。
### user
```json
{"userQuery":"做张卡片，看看上海现在的天气和手机剩余电量，还能分别打开天气详情和电池设置。","size":"2x4","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"Weather_CityCode","uri":"{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' + ${/data/weather/location/cityCode} }}"}},{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"battery"}},{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4"}}],"dataModelSchema":{"data":{"weather":{"location":{"cityCode":{"type":"string","description":"城市编码","sampleValue":"101020100"}},"current":{"condition":{"type":"string","description":"天气状况","sampleValue":"多云"},"temperatureC":{"type":"integer","description":"当前温度","sampleValue":29}}},"phoneBattery":{"batterySOC":{"type":"integer","description":"手机电量百分比","sampleValue":68},"chargingStatusDesc":{"type":"string","description":"充电状态","sampleValue":"未充电"}}}},"assetCandidates":[{"src":"resources/base/media/music_fill.svg","description":"样式：音乐音符实心图标，默认黑色，图形为双音符连接造型；适用：音乐播放卡片、音频功能入口、歌单展示。"},{"src":"resources/base/media/alarm_fill_1.svg","description":"样式：默认黑色的单色闹钟实心图标，内部通过镂空表现表盘指针，支持通过 fillColor 与卡片配色统一；适用：闹钟设置、定时提醒、日程提醒。"}]}
```
### assistant
```genui
["root","Row",{"width":"matchParent","height":"matchParent","padding":8,"itemMargin":8,"borderRadius":20,"clip":true,"alignItems":"center","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]},"justifyContent":"center"},["weatherZone","batteryZone"]]
["weatherZone","Column",{"width":138,"height":134,"padding":12,"itemMargin":4,"borderRadius":16,"backgroundColor":"#99FFFFFF"},["weatherContent","weatherButton"]]
["weatherTitle","Text",{"content":"上海天气","width":114,"height":16,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["weatherContent","Column",{"width":114,"layoutWeight":1,"itemMargin":2,"justifyContent":"center"},["weatherTitle","weatherValue","weatherStatus"]]
["weatherValue","Text",{"content":"{{ ${/data/weather/current/temperatureC} + '°C' }}","width":114,"height":34,"fontSize":24,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["weatherStatus","Text",{"content":{"path":"/data/weather/current/condition"},"width":114,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["weatherButton","Button",{"label":"查看天气","width":114,"height":36,"borderRadius":18,"backgroundColor":"#331F4799","fontColor":"#FF1F4799","fontSize":14,"fontWeight":400,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Weather_CityCode","uri":"{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' + ${/data/weather/location/cityCode} }}"}}]}]
["batteryZone","Column",{"width":138,"height":134,"padding":12,"itemMargin":4,"borderRadius":16,"backgroundColor":"#99FFFFFF"},["batteryContent","batteryButton"]]
["batteryTitle","Text",{"content":"手机电量","width":114,"height":16,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["batteryContent","Column",{"width":114,"layoutWeight":1,"itemMargin":2,"justifyContent":"center"},["batteryTitle","batteryValue","batteryStatus"]]
["batteryValue","Text",{"content":"{{ ${/data/phoneBattery/batterySOC} + '%' }}","width":114,"height":28,"fontSize":20,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["batteryStatus","Text",{"content":{"path":"/data/phoneBattery/chargingStatusDesc"},"width":114,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["batteryButton","Button",{"label":"电池设置","width":114,"height":36,"borderRadius":18,"backgroundColor":"#331F4799","fontColor":"#FF1F4799","fontSize":14,"fontWeight":400,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"battery"}}]}]
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
["root","Row",{"width":"matchParent","height":"matchParent","padding":8,"itemMargin":8,"borderRadius":20,"clip":true,"justifyContent":"center","alignItems":"center","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["weatherZone","secondaryColumn"]]
["weatherZone","Column",{"width":138,"height":134,"padding":12,"itemMargin":4,"borderRadius":16,"backgroundColor":"#99FFFFFF"},["weatherContent","weatherButton"]]
["weatherLabel","Text",{"content":"上海天气","width":114,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["weatherContent","Column",{"width":114,"layoutWeight":1,"itemMargin":2,"justifyContent":"center"},["weatherLabel","weatherReadout","weatherStatus"]]
["weatherReadout","Row",{"width":114,"height":42,"alignItems":"bottom","itemMargin":2},["weatherValue","weatherUnit"]]
["weatherValue","Text",{"content":{"path":"/data/weather/current/temperatureC"},"fontSize":30,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["weatherUnit","Text",{"content":"°C","fontSize":12,"fontWeight":500,"fontColor":"#FF1F4799","padding":{"bottom":4},"maxLines":1}]
["weatherStatus","Text",{"content":{"path":"/data/weather/current/condition"},"width":114,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["weatherButton","Button",{"label":"查看天气","width":114,"height":36,"borderRadius":18,"backgroundColor":"#331F4799","fontColor":"#FF1F4799","fontSize":14,"fontWeight":400,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Weather_CityCode","uri":"{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' + ${/data/weather/location/cityCode} }}"}}]}]
["secondaryColumn","Column",{"width":138,"height":134,"itemMargin":8},["batteryZone","earphoneZone"]]
["batteryZone","Column",{"width":138,"height":63,"padding":12,"itemMargin":2,"borderRadius":16,"backgroundColor":"#99FFFFFF","justifyContent":"center","onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"battery"}}]},["batteryValue","batteryAux"]]
["batteryValue","Text",{"content":"{{ ${/data/phoneBattery/batterySOC} + '%' }}","width":114,"fontSize":14,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["batteryAux","Text",{"content":{"path":"/data/phoneBattery/chargingStatusDesc"},"width":114,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["earphoneZone","Row",{"width":138,"height":63,"padding":12,"itemMargin":8,"borderRadius":16,"backgroundColor":"#99FFFFFF","justifyContent":"start","alignItems":"center","onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"bluetooth_entry"}}]},["earphoneText","earphoneIcon"]]
["earphoneText","Column",{"width":86,"itemMargin":2,"justifyContent":"center"},["earphoneValue","earphoneStatus"]]
["earphoneValue","Text",{"content":"耳机","width":86,"fontSize":14,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["earphoneStatus","Text",{"content":"{{ ${/data/earphone/isConnected} ? '已连接' : '未连接' }}","width":86,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["earphoneIcon","Image",{"src":"resources/base/media/earphone_case_16644.svg","width":20,"height":20,"objectFit":"contain","fillColor":"#FF1F4799","flexShrink":0}]
["/data/weather/location/cityCode","101020100"]
["/data/weather/current/condition","多云"]
["/data/weather/current/temperatureC",29]
["/data/phoneBattery/batterySOC",68]
["/data/phoneBattery/chargingStatusDesc","未充电"]
["/data/earphone/isConnected",true]
```

## 示例十八（2x4-V11）：单城市天气主读数（单业务 value-led·蓝色微渐变）
本例仅用于信息稀疏的单城市天气：主温度占据连续的视觉区域，单位紧贴主值，天气现象和温度范围作为辅助信息；不使用双背板，也不为了填满高度增加弱指标。若天气字段扩展为预警、空气质量、紫外线、感冒指数等四项以上，且还有明确动作或提醒文案，应切换 W1，把提醒/动作放进右侧两个辅助槽，不能沿用本例继续堆叠通栏文字，也不能生成第三个右侧背板。
### user
```json
{"userQuery":"做一张上海天气卡片，让我一眼看到当前温度和天气情况。","size":"2x4","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"Weather_CityCode","uri":"{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' + ${/data/weather/location/cityCode} }}"}}],"dataModelSchema":{"data":{"weather":{"location":{"districtName":{"type":"string","description":"当前城市或地区名称","sampleValue":"上海市"},"cityCode":{"type":"string","description":"城市编码","sampleValue":"101020100"}},"current":{"temperatureText":{"type":"string","description":"包含单位的当前温度文本","sampleValue":"29°C"},"condition":{"type":"string","description":"当前天气现象","sampleValue":"多云"},"temperatureRangeText":{"type":"string","description":"当天温度范围文本","sampleValue":"25°C / 32°C"}}}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":20,"clip":true,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Weather_CityCode","uri":"{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' + ${/data/weather/location/cityCode} }}"}}],"linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["content"]]
["content","Column",{"width":"matchParent","height":"matchParent","padding":12,"itemMargin":6,"justifyContent":"start","alignItems":"start"},["header","hero","support"]]
["header","CardHeader",{"title":{"path":"/data/weather/location/districtName"},"fontColor":"#FF1F4799"}]
["hero","Column",{"width":276,"height":60,"justifyContent":"center","alignItems":"start","itemMargin":2},["temperature","condition"]]
["temperature","Text",{"content":{"path":"/data/weather/current/temperatureText"},"width":276,"height":34,"fontSize":24,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["condition","Text",{"content":{"path":"/data/weather/current/condition"},"width":276,"fontSize":16,"fontWeight":500,"fontColor":"#FF1F4799","maxLines":1}]
["support","Row",{"width":276,"height":34,"itemMargin":8,"alignItems":"center"},["range"]]
["range","Text",{"content":{"path":"/data/weather/current/temperatureRangeText"},"width":276,"fontSize":12,"fontWeight":400,"fontColor":"#991F4799","maxLines":1}]
["/data/weather/location/districtName","上海市"]
["/data/weather/location/cityCode","101020100"]
["/data/weather/current/temperatureText","29°C"]
["/data/weather/current/condition","多云"]
["/data/weather/current/temperatureRangeText","25°C / 32°C"]
```

## 示例十九（2x4-V12）：耳机连接状态与辅助入口（W1-focus-aux·蓝色微渐变）
本例用于单耳机业务的 `status-led` 变体：连接状态与设备名称构成左侧第一焦点，成对电量压入右上摘要，蓝牙设置占右下动作槽。若用户明确要求两个动作，两个右侧槽都用于动作，左右电量在左侧合并为一条辅助信息；不要生成满宽底部按钮。
### user
```json
{"userQuery":"做张耳机状态卡片，优先让我看到是否已连接和耳机名称，底部放蓝牙设置。","size":"2x4","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"bluetooth_entry"}}],"dataModelSchema":{"data":{"earphone":{"isConnected":{"type":"boolean","description":"当前是否处于耳机连接活跃状态","sampleValue":true},"earphoneName":{"type":"string","description":"耳机广播名称","sampleValue":"FreeBuds Pro 3"},"leftBatteryLevel":{"type":"integer","description":"左耳电量百分比0到100","sampleValue":76},"rightBatteryLevel":{"type":"integer","description":"右耳电量百分比0到100","sampleValue":78}}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Row",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":20,"clip":true,"itemMargin":10,"justifyContent":"center","alignItems":"center","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["focus","details"]]
["focus","Column",{"width":136,"height":126,"itemMargin":4,"justifyContent":"start","alignItems":"start"},["name","statusArea"]]
["name","Text",{"content":{"path":"/data/earphone/earphoneName"},"width":136,"fontSize":12,"fontWeight":400,"fontColor":"#991F4799","maxLines":1}]
["statusArea","Column",{"width":136,"layoutWeight":1,"justifyContent":"center","alignItems":"start"},["status"]]
["status","Text",{"content":"{{ ${/data/earphone/isConnected} ? '已连接' : '未连接' }}","width":136,"fontSize":18,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["details","Column",{"width":130,"height":126,"itemMargin":8},["batterySummary","settingsAction"]]
["batterySummary","Column",{"width":130,"height":59,"padding":{"left":12,"right":12,"top":6,"bottom":6},"borderRadius":12,"backgroundColor":"#99FFFFFF","itemMargin":2,"justifyContent":"center"},["leftBattery","rightBattery"]]
["leftBattery","Text",{"content":"{{ '左耳 ' + ${/data/earphone/leftBatteryLevel} + '%' }}","width":106,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["rightBattery","Text",{"content":"{{ '右耳 ' + ${/data/earphone/rightBatteryLevel} + '%' }}","width":106,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["settingsAction","Row",{"width":130,"height":59,"padding":{"left":12,"right":12},"borderRadius":12,"backgroundColor":"#99FFFFFF","justifyContent":"start","alignItems":"center","onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"bluetooth_entry"}}]},["settingsLabel"]]
["settingsLabel","Text",{"content":"蓝牙设置","width":106,"fontSize":14,"fontWeight":500,"fontColor":"#FF1F4799","textAlign":"start","maxLines":1}]
["/data/earphone/isConnected",true]
["/data/earphone/earphoneName","FreeBuds Pro 3"]
["/data/earphone/leftBatteryLevel",76]
["/data/earphone/rightBatteryLevel",78]
```

## 示例二十（2x4-V13）：中性稀疏双业务（W9-dual-backboards·蓝色微渐变）

本例是未知业务组合的 W9 稀疏金标，不提供可复制的业务文案。两侧各保留一个主焦点和一条必要上下文，真实内容组稳定居中；候选素材与对象精确匹配，因此放在各自标题右侧。若真实 TaskSpec 没有合法素材，只删除图标并让标题占满宽度，不留空槽、不猜测路径。

### user
```json
{"userQuery":"做张横向卡片，同时看看项目状态和下一次同步时间。","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"project":{"name":{"type":"string","description":"项目名称","sampleValue":"新品设计"},"status":{"type":"string","description":"项目当前状态","sampleValue":"评审中"}},"sync":{"title":{"type":"string","description":"同步事项名称","sampleValue":"方案同步"},"time":{"type":"string","description":"下次同步时间","sampleValue":"14:00"}}}},"assetCandidates":[{"src":"resources/base/media/project_fill.svg","description":"项目概览的中性单色图标，适用于项目状态分区。"},{"src":"resources/base/media/calendar_fill.svg","description":"日历与时间安排的中性单色图标，适用于同步时间分区。"}]}
```

### assistant
```genui
["root","Row",{"width":"matchParent","height":"matchParent","padding":8,"itemMargin":8,"borderRadius":20,"clip":true,"justifyContent":"center","alignItems":"center","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["projectZone","syncZone"]]
["projectZone","Column",{"width":138,"height":134,"padding":12,"itemMargin":8,"borderRadius":16,"backgroundColor":"#99FFFFFF"},["projectHeader","projectContent"]]
["projectHeader","Row",{"width":114,"height":20,"itemMargin":8,"alignItems":"center"},["projectLabel","projectIcon"]]
["projectLabel","Text",{"content":{"path":"/data/project/name"},"width":86,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["projectIcon","Image",{"src":"resources/base/media/project_fill.svg","width":20,"height":20,"objectFit":"contain","fillColor":"#FF1F4799","flexShrink":0}]
["projectContent","Column",{"width":114,"layoutWeight":1,"justifyContent":"center","itemMargin":4},["projectStatus","projectContext"]]
["projectStatus","Text",{"content":{"path":"/data/project/status"},"width":114,"height":24,"fontSize":18,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["projectContext","Text",{"content":"当前进度","width":114,"height":16,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["syncZone","Column",{"width":138,"height":134,"padding":12,"itemMargin":8,"borderRadius":16,"backgroundColor":"#99FFFFFF"},["syncHeader","syncContent"]]
["syncHeader","Row",{"width":114,"height":20,"itemMargin":8,"alignItems":"center"},["syncLabel","syncIcon"]]
["syncLabel","Text",{"content":{"path":"/data/sync/title"},"width":86,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["syncIcon","Image",{"src":"resources/base/media/calendar_fill.svg","width":20,"height":20,"objectFit":"contain","fillColor":"#FF1F4799","flexShrink":0}]
["syncContent","Column",{"width":114,"layoutWeight":1,"justifyContent":"center","itemMargin":4},["syncTime","syncContext"]]
["syncTime","Text",{"content":{"path":"/data/sync/time"},"width":114,"height":24,"fontSize":18,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["syncContext","Text",{"content":"下次同步","width":114,"height":16,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["/data/project/name","新品设计"]
["/data/project/status","评审中"]
["/data/sync/title","方案同步"]
["/data/sync/time","14:00"]
```

## 示例二十一（2x4-V14）：手机电量与耳机状态（W9 稀疏双业务金标·蓝色微渐变）

本例是常见设备组合的稀疏 W9 金标。每侧只有 2～3 项必要事实且没有动作，直接 content Column 必须使用 `layoutWeight:1` 与 `justifyContent:"center"`，让主读数或核心状态位于背板视觉中心。手机电量使用 20fp 完整格式化主读数，耳机连接状态使用 18fp；业务标签和必要状态保持 12fp。禁止把全部内容缩成顶部小字，也不添加更新时间、图标、进度环或重复电量来填充留白。

### user
```json
{"userQuery":"做张横向卡片，主要看手机剩余电量，也看看耳机是否连接和充电盒电量。","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"phoneBattery":{"batterySOCText":{"type":"string","description":"当前手机剩余电量文本，已包含%单位","sampleValue":"68%"},"chargingStatusDesc":{"type":"string","description":"手机当前充电状态","sampleValue":"未充电"}},"earphone":{"earphoneName":{"type":"string","description":"耳机设备名称","sampleValue":"FreeBuds Pro"},"isConnected":{"type":"boolean","description":"耳机当前是否连接","sampleValue":true},"batteryLevel":{"type":"integer","description":"充电盒电量百分比0到100，展示时追加%","sampleValue":80}}}},"assetCandidates":[]}
```

### assistant
```genui
["root","Row",{"width":"matchParent","height":"matchParent","padding":8,"itemMargin":8,"borderRadius":20,"clip":true,"justifyContent":"center","alignItems":"center","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["phoneZone","earphoneZone"]]
["phoneZone","Column",{"width":138,"height":134,"padding":12,"borderRadius":16,"backgroundColor":"#99FFFFFF"},["phoneContent"]]
["phoneContent","Column",{"width":114,"layoutWeight":1,"justifyContent":"center","alignItems":"start","itemMargin":4},["phoneLabel","phoneValue","phoneStatus"]]
["phoneLabel","Text",{"content":"手机电量","width":114,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["phoneValue","Text",{"content":{"path":"/data/phoneBattery/batterySOCText"},"width":114,"height":28,"fontSize":20,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["phoneStatus","Text",{"content":{"path":"/data/phoneBattery/chargingStatusDesc"},"width":114,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["earphoneZone","Column",{"width":138,"height":134,"padding":12,"borderRadius":16,"backgroundColor":"#99FFFFFF"},["earphoneContent"]]
["earphoneContent","Column",{"width":114,"layoutWeight":1,"justifyContent":"center","alignItems":"start","itemMargin":4},["earphoneName","earphoneStatus","caseBattery"]]
["earphoneName","Text",{"content":{"path":"/data/earphone/earphoneName"},"width":114,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["earphoneStatus","Text",{"content":"{{ ${/data/earphone/isConnected} ? '已连接' : '未连接' }}","width":114,"height":26,"fontSize":18,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1}]
["caseBattery","Text",{"content":"{{ '充电盒 ' + ${/data/earphone/batteryLevel} + '%' }}","width":114,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1}]
["/data/phoneBattery/batterySOCText","68%"]
["/data/phoneBattery/chargingStatusDesc","未充电"]
["/data/earphone/earphoneName","FreeBuds Pro"]
["/data/earphone/isConnected",true]
["/data/earphone/batteryLevel",80]
```
