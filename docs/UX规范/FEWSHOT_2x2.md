# 2x2 Few-shot

配套规范：[通用卡片 UX 规范](UX-SPEC.md)。本文件按原有“示例说明 → user → assistant”格式，同步当前 Fusion 完整案例，不再使用旧单步走的自由基础组件案例。

**来源版本：2026-10-23，main `56c3e7827f080c3250caac4c580008679811698f`。** 维护源：[`prompt_source/fewshots/2x2.md`](https://github.com/InnovationTea/CreateMyCard/blob/56c3e7827f080c3250caac4c580008679811698f/widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/fewshots/2x2.md)，共 19 例。案例 ID 保留维护源编号，不按本文件顺序重新编号。

以下案例仅用于参考信息关系、组件组合和布局表达；当前 TaskSpec、已接受 Plan、组件与布局合同优先。不得复制本轮输入没有的事实、路径、事件、素材或样例数据，不为贴合案例删减、补造或静态化信息。

**主题与容量说明：** 下列输入与 DSL 代码块原样同步维护源，不是最终模型请求或主题后 A2UI。维护源中保留的颜色、渐变、design 及标题中的主题名，在实际布局提示组装时按 layout-only 规则清理，布局定稿后统一应用本轮主题；不能直接认定最终沿用示例颜色。历史标题中的 Sub-118 / Sub-140 仅是维护说明，不是当前允许输出的布局名，实际以示例的 Region.variant 为准。案例中的区域宽高是参考预算，不能直接规定所有设备尺寸；当前仍保留的组件内部规格与自适应条件见[主规范附录 A](UX-SPEC.md#附录-a-当前实现的参考预算与固定内部规格)。案例同步不代表本轮重新生成或真机验收通过。

## 示例一（2x2-V01）：运动会倒计时（`S-center`·融球暖橙）
本例使用“核心居中”：唯一量化焦点由 `DataDisplay` 同时承载短标签、核心数值和单位，作为 root 的唯一内容组件。仅当用户明确要求一个动作且实际候选目标匹配时，改选带动作布局，不在 `S-center` 中临时增加标题或动作槽。
干扰候选示范：输入虽含一个歌单事件和音符素材，但本次只要求倒计时；输出不生成按钮、图标或隐式点击，不把候选数量当作用户意图。
### user
```json
{"userQuery":"帮我做张运动会倒计时卡片，看看离运动会还有多少天。","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4"}}],"dataModelSchema":{"data":{"countdown":{"countdownDays":{"type":"integer","description":"距离目标日期的自然日天数","sampleValue":32}}}},"assetCandidates":[{"src":"resources/base/media/music_fill.svg","description":"样式：音乐音符实心图标，默认黑色，图形为双音符连接造型；适用：音乐播放卡片、音频功能入口、歌单展示。"}]}
```
### assistant
```genui
["root","Layout",{"layout":"S-center","design":"fusion-ball-sport-orange"},["content"]]
["content","DataDisplay",{"label":"运动会倒计时","value":{"path":"/data/countdown/countdownDays"},"supportingText":"天"}]
["/data/countdown/countdownDays",32]
```

## 示例二（2x2-V09）：单核心数值及单位说明（`S-center`）

root 双轴居中且只包含一个全宽 `DataDisplay`；组件以静态“当前任务”为标签，动态绑定任务数量，并以静态“项”作为支撑文本。本例没有标题、动作或其它内容组件。

### user
```json
{"userQuery":"展示当前任务数，并注明单位是项","size":"2x2","eventCandidates":[],"dataModelSchema":{"data":{"view":{"value":{"type":"integer","description":"当前任务数量，单位项","sampleValue":42}}}},"assetCandidates":[]}
```

### assistant
```genui
["root","Layout",{"layout":"S-center","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["content"]]
["content","DataDisplay",{"label":"当前任务","value":{"path":"/data/view/value"},"supportingText":"项"}]
["/data/view/value",42]
```

## 示例三（2x2-V15）：天气预警文本结论（`S-center`）

本例展示 `DataDisplay` 的短文本模式：root 只包含一个居中信息组，不额外生成标题或
动作。真实天气预警图标占用上方 label 槽；核心结论使用 24fp，并将更新日期作为紧密支撑文本。
图标只能来自当前素材候选；无真实预警时不能套用本例。

### user
```json
{"userQuery":"用居中卡片展示当前天气预警等级和更新日期，不需要按钮。","size":"2x2","eventCandidates":[],"dataModelSchema":{"data":{"weather":{"current":{"alertLevel":{"type":"string","description":"当前气象预警的短文本结论","sampleValue":"蓝色预警"}},"updatedAtText":{"type":"string","description":"天气数据更新日期文本","sampleValue":"2026-9-19 更新"}}}},"assetCandidates":[{"src":"resources/base/media/ic_weatherWarning.svg","description":"渐变云朵预警图标；仅用于真实气象预警，保留原色。"}]}
```

### assistant
```genui
["root","Layout",{"layout":"S-center","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["content"]]
["content","DataDisplay",{"icon":"resources/base/media/ic_weatherWarning.svg","value":{"path":"/data/weather/current/alertLevel"},"supportingText":{"path":"/data/weather/updatedAtText"}}]
["/data/weather/current/alertLevel","蓝色预警"]
["/data/weather/updatedAtText","2026-9-19 更新"]
```

## 示例四（2x2-V10）：完整事件信息（`S-title-content`）

活动名称、时间范围和地点属于同一事件，完整匹配 `EventCard` 的标题、时间和地点结构；该组件不要求必须带动作。
没有动作消费素材，跑步图标与“社区夜跑”和整张卡片主题语义匹配，因此默认分配给标题。

### user
```json
{"userQuery":"展示社区夜跑的活动名称、开始和结束时间，以及集合地点。","size":"2x2","eventCandidates":[],"dataModelSchema":{"data":{"communityRun":{"name":{"type":"string","description":"活动名称","sampleValue":"社区夜跑"},"start":{"type":"string","description":"开始时间","sampleValue":"19:00"},"end":{"type":"string","description":"结束时间","sampleValue":"20:30"},"place":{"type":"string","description":"集合地点","sampleValue":"南门广场"}}}},"assetCandidates":[{"src":"resources/base/media/figure_run.svg","description":"可染色的跑步人物图标，适用于跑步、夜跑和运动活动"}]}
```

### assistant
```genui
["root","Layout",{"layout":"S-title-content","linearGradient":{"direction":"RightBottom","colors":[["#FFFFE0CC",0],["#FFFFF7F2",1]]}},["title","content"]]
["title","SingleLineTitle",{"title":"活动安排","icon":"resources/base/media/figure_run.svg","fontSize":12}]
["content","EventCard",{"items":[{"title":{"path":"/data/communityRun/name"},"time":"{{ ${/data/communityRun/start} + ' – ' + ${/data/communityRun/end} }}","location":{"path":"/data/communityRun/place"}}]}]
["/data/communityRun/name","社区夜跑"]
["/data/communityRun/start","19:00"]
["/data/communityRun/end","20:30"]
["/data/communityRun/place","南门广场"]
```

## 示例五（2x2-V19）：无动作的数值主信息与状态补充（`S-title-dual-content`）

温度是主信息，用EmphasizedData；状态是同对象补充，用SecondaryBody。没有Action，不预留按钮，不把两项机械拆成表格。温度原字段已含单位，保留完整动态绑定，不再填写unit以免重复；不假设组件能拆分格式化字符串。

### user
```json
{"userQuery":"只展示电池温度和充电状态，以温度为主，不需要操作入口。","size":"2x2","assetCandidates":[],"eventCandidates":[],"dataModelSchema":{"data":{"phoneBattery":{"batteryTemperatureText":{"type":"string","description":"包含单位的电池温度文本","sampleValue":"29.0°C"},"chargingStatusDesc":{"type":"string","description":"当前充电状态","sampleValue":"未充电"}}}}}
```

### assistant
```genui
["root","Layout",{"layout":"S-title-dual-content","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["title","temperature","status"]]
["title","SingleLineTitle",{"title":"电池温度","fontSize":12}]
["temperature","EmphasizedData",{"value":{"path":"/data/phoneBattery/batteryTemperatureText"},"fontSize":30}]
["status","SecondaryBody",{"items":[{"label":"状态","value":{"path":"/data/phoneBattery/chargingStatusDesc"}}],"fontSize":14}]
["/data/phoneBattery/batteryTemperatureText","29.0°C"]
["/data/phoneBattery/chargingStatusDesc","未充电"]
```

## 示例六（2x2-V16）：无动作的文本主信息与同级补充（`S-title-dual-content`）

连接状态用EmphasisText；左右耳电量保持同级，进入同一个SecondaryBody，不把一侧作为另一侧的辅助。三项属于同一对象的结论和属性，不使用双分区或动作槽；动态读数分别绑定并补完整百分比单位。

### user
```json
{"userQuery":"只看耳机连接状态，并补充左右耳的电量，不需要操作入口。","size":"2x2","eventCandidates":[],"dataModelSchema":{"data":{"earphone":{"isConnected":{"type":"boolean","description":"当前是否处于耳机连接活跃状态","sampleValue":true},"leftBatteryLevel":{"type":"integer","description":"左耳电量百分比0到100","sampleValue":47},"rightBatteryLevel":{"type":"integer","description":"右耳电量百分比0到100","sampleValue":62}}}},"assetCandidates":[]}
```

### assistant
```genui
["root","Layout",{"layout":"S-title-dual-content","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["title","status","batteries"]]
["title","SingleLineTitle",{"title":"耳机状态","fontSize":12}]
["status","EmphasisText",{"mainText":"{{ ${/data/earphone/isConnected} ? '已连接' : '未连接' }}","fontSize":18}]
["batteries","SecondaryBody",{"items":[{"label":"左耳","value":"{{ ${/data/earphone/leftBatteryLevel} + '%' }}"},{"label":"右耳","value":"{{ ${/data/earphone/rightBatteryLevel} + '%' }}"}],"columns":1,"fontSize":12}]
["/data/earphone/isConnected",true]
["/data/earphone/leftBatteryLevel",47]
["/data/earphone/rightBatteryLevel",62]
```

## 示例七（2x2-V12）：四台设备电量（`S-quad-content`）

四台设备是四个同级真实占比，并且每个对象都有准确图标。使用四个 `ProgressCircle` 进入固定 2×2 槽位，
图标区分对象，环外读数显示真实百分比；不使用 `ProgressCircleSingle` 重造多对象组合，也不手写文字卡块。

### user
```json
{"userQuery":"做张纯展示卡片，同时看手机、儿童手表、相机和耳机盒的电量百分比。","size":"2x2","eventCandidates":[],"dataModelSchema":{"data":{"phoneBattery":{"percent":{"type":"integer","description":"手机电量百分比0到100","sampleValue":68}},"watchBattery":{"percent":{"type":"integer","description":"儿童手表电量百分比0到100","sampleValue":47}},"cameraBattery":{"percent":{"type":"integer","description":"相机电量百分比0到100","sampleValue":82}},"earphoneBattery":{"percent":{"type":"integer","description":"耳机盒电量百分比0到100","sampleValue":59}}}},"assetCandidates":[{"src":"resources/base/media/phone_fill.svg","description":"可染色的手机单色图标"},{"src":"resources/base/media/kidswatch_fill.svg","description":"可染色的儿童手表单色图标"},{"src":"resources/base/media/camera_fill.svg","description":"可染色的相机单色图标"},{"src":"resources/base/media/earphone_case_16644.svg","description":"可染色的耳机盒单色图标"}]}
```

### assistant
```genui
["root","Layout",{"layout":"S-quad-content","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["top_left","top_right","bottom_left","bottom_right"]]
["top_left","ProgressCircle",{"externalText":{"path":"/data/phoneBattery/percent"},"icon":"resources/base/media/phone_fill.svg","accessibility":{"label":"手机电量百分比"},"fillColor":"#991F4799","color":"#FF1F4799","backgroundColor":"#331F4799"}]
["top_right","ProgressCircle",{"externalText":{"path":"/data/watchBattery/percent"},"icon":"resources/base/media/kidswatch_fill.svg","accessibility":{"label":"儿童手表电量百分比"},"fillColor":"#991F4799","color":"#FF1F4799","backgroundColor":"#331F4799"}]
["bottom_left","ProgressCircle",{"externalText":{"path":"/data/cameraBattery/percent"},"icon":"resources/base/media/camera_fill.svg","accessibility":{"label":"相机电量百分比"},"fillColor":"#991F4799","color":"#FF1F4799","backgroundColor":"#331F4799"}]
["bottom_right","ProgressCircle",{"externalText":{"path":"/data/earphoneBattery/percent"},"icon":"resources/base/media/earphone_case_16644.svg","accessibility":{"label":"耳机盒电量百分比"},"fillColor":"#991F4799","color":"#FF1F4799","backgroundColor":"#331F4799"}]
["/data/phoneBattery/percent",68]
["/data/watchBattery/percent",47]
["/data/cameraBattery/percent",82]
["/data/earphoneBattery/percent",59]
```

## 示例八（2x2-V04）：下一场会议（`S-title-content-action`·黄色微渐变）
单个会议的标题、时间与入会动作分别保留。一个或多个具有标题和时间的事件使用同一个 `EventCard`；多项普通
高度放不下时使用 compact。更多事件或必要明细无法闭合时改选更大布局，不拆成普通正文绕过专用组件。
### user
```json
{"userQuery":"帮我做张会议提醒卡片，看看下一场会叫什么、几点开始，还能点一下直接入会。","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"EnterMeeting","bundleName":"","abilityName":"","uri":"{{ ${/data/calendar/events/0/oneClickServiceLink} }}"}}],"dataModelSchema":{"data":{"calendar":{"events":[{"title":{"type":"string","description":"日程标题","sampleValue":"UI需求评审会"},"dtStart":{"type":"string","description":"开始时间","sampleValue":"14:00 - 15:30"},"oneClickServiceLink":{"type":"string","description":"一键入会链接","sampleValue":"wemeet://join/example"}}]}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Layout",{"layout":"S-title-content-action","linearGradient":{"direction":"RightBottom","colors":[["#FFFFE0CC",0],["#FFFFF7F2",1]]}},["title","content","action"]]
["title","SingleLineTitle",{"title":"下一场会议","fontSize":12}]
["content","EventCard",{"items":[{"title":{"path":"/data/calendar/events/0/title"},"time":{"path":"/data/calendar/events/0/dtStart"}}]}]
["action","PillButton",{"label":"加入会议","onClick":[{"call":"clickToDeeplink","args":{"intentName":"EnterMeeting","bundleName":"","abilityName":"","uri":"{{ ${/data/calendar/events/0/oneClickServiceLink} }}"}}]}]
["/data/calendar/events/0/title","UI需求评审会"]
["/data/calendar/events/0/dtStart","14:00 - 15:30"]
["/data/calendar/events/0/oneClickServiceLink","wemeet://join/example"]
```

## 示例九（2x2-V11）：单一占比与必要动作（`S-title-content-action`）

一个设备的真实电量占比是唯一内容，并且输入提供了准确的儿童手表图标，因此使用
`ProgressCircleSingle`；动作放在独立 `PillButton` 槽，不用普通数值组件弱化比例语义。

### user
```json
{"userQuery":"看儿童手表还剩多少电，并打开设备设置。","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"WearableSettings","bundleName":"com.example.wearable","abilityName":"MainAbility","uri":"wearable://settings"}}],"dataModelSchema":{"data":{"wearable":{"batteryPercent":{"type":"integer","description":"儿童手表剩余电量百分比0到100","sampleValue":73}}}},"assetCandidates":[{"src":"resources/base/media/kidswatch_fill.svg","description":"可染色的儿童手表单色图标"}]}
```

### assistant
```genui
["root","Layout",{"layout":"S-title-content-action","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["title","content","action"]]
["title","SingleLineTitle",{"title":"儿童手表","fontSize":12}]
["content","ProgressCircleSingle",{"value":{"path":"/data/wearable/batteryPercent"},"total":100,"icon":"resources/base/media/kidswatch_fill.svg","displayValue":"{{ ${/data/wearable/batteryPercent} + '%' }}","label":"剩余电量","color":"#FF1F4799","backgroundColor":"#331F4799"}]
["action","PillButton",{"label":"设备设置","onClick":[{"call":"clickToDeeplink","args":{"intentName":"WearableSettings","bundleName":"com.example.wearable","abilityName":"MainAbility","uri":"wearable://settings"}}]}]
["/data/wearable/batteryPercent",73]
```

## 示例十（2x2-V13）：进度环、状态与单动作（`S-title-content-action`）

环形比例是用户明确要求，单个对象的真实占比、可见读数与同对象状态完整匹配 `ProgressCircleSingle`。
标题按 Recipe 实际单行高度参与预算；标题后间距6、正文到动作间距8、动作高36，并保留独立动作槽。
只有这一项电量和一项状态时适用，更多必需事实须重新分配正文，不能删事实套例。

### user
```json
{"userQuery":"用进度环显示手机电量和充电状态，提供电池设置按钮。","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"battery"}}],"dataModelSchema":{"data":{"phoneBattery":{"batterySOC":{"type":"integer","description":"手机剩余电量百分比0到100","sampleValue":68},"chargingStatusDesc":{"type":"string","description":"手机充电状态","sampleValue":"未充电"}}}},"assetCandidates":[{"src":"resources/base/media/battery_leaf_fill.svg","description":"可染色的电量单色图标"}]}
```

### assistant
```genui
["root","Layout",{"layout":"S-title-content-action","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["title","content","action"]]
["title","SingleLineTitle",{"title":"手机电量","fontSize":12}]
["content","ProgressCircleSingle",{"value":{"path":"/data/phoneBattery/batterySOC"},"total":100,"icon":"resources/base/media/battery_leaf_fill.svg","displayValue":"{{ ${/data/phoneBattery/batterySOC} + '%' }}","label":"剩余电量","secondaryLabel":{"path":"/data/phoneBattery/chargingStatusDesc"},"backgroundColor":"#331F4799","color":"#FF1F4799"}]
["action","PillButton",{"label":"电池设置","onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"battery"}}]}]
["/data/phoneBattery/batterySOC",68]
["/data/phoneBattery/chargingStatusDesc","未充电"]
```

## 示例十一（2x2-V05）：发布会倒计时（`S-title-primary-secondary-action`·左对齐主值·开始时间）
倒计时存在底部按钮或另一类可见数据时，改用带动作布局，不再使用 V01 的无动作标题单内容结构。标题、主值组和辅助信息
统一左对齐；标题使用 `SingleLineTitle`，倒计时使用量化主值，普通开始时间使用 `SecondaryBody`，主次内容的纵向间距为 2vp，底部动作沉底。`/data/countdown`
与 `/data/calendar` 在这里共同描述同一个发布会目标，不拆成 `S-dual-info` 两个业务对象。
### user
```json
{"userQuery":"下一场日程是18天后的产品发布会，显示离发布会还有几天、日程标题和开始时间，并提供查看详情按钮。","size":"2x2","eventCandidates":[{"call":"clickToIntent","args":{"intentName":"ViewCalendarEvent","params":{"entityId":"{{ ${/data/calendar/events/0/entityId} }}"}}}],"dataModelSchema":{"data":{"countdown":{"countdownDays":{"type":"integer","description":"距离目标日期的自然日天数纯整数，返回值不包含‘天’","sampleValue":18}},"calendar":{"events":[{"title":{"type":"string","description":"日程标题","sampleValue":"产品发布会"},"dtStart":{"type":"string","description":"格式化后的日程开始时间短文本","sampleValue":"上午10:00"},"entityId":{"type":"string","description":"系统日程的全局唯一实体ID","sampleValue":"event-001"}}]}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Layout",{"layout":"S-title-primary-secondary-action","design":"fusion-ball-sport-orange"},["title","primary","support","action"]]
["title","SingleLineTitle",{"title":{"path":"/data/calendar/events/0/title"},"fontSize":12}]
["primary","EmphasizedData",{"value":{"path":"/data/countdown/countdownDays"},"unit":"天","fontSize":30}]
["support","SecondaryBody",{"items":[{"value":{"path":"/data/calendar/events/0/dtStart"}}],"fontSize":14}]
["action","PillButton",{"label":"查看详情","onClick":[{"call":"clickToIntent","args":{"intentName":"ViewCalendarEvent","params":{"entityId":"{{ ${/data/calendar/events/0/entityId} }}"}}}]}]
["/data/countdown/countdownDays",18]
["/data/calendar/events/0/title","产品发布会"]
["/data/calendar/events/0/dtStart","上午10:00"]
["/data/calendar/events/0/entityId","event-001"]
```

## 示例十二（2x2-V06）：电池温度与充电状态（`S-title-primary-secondary-action`·单动作）
卡级标题为“电池温度”。正文依次使用左对齐的全宽 `EmphasizedData` 绑定已包含单位的温度文本，并用 `SecondaryBody` 绑定充电状态，两者纵向间距为 2vp；不拆分或重复追加温度单位。正文与 36vp 底部动作区之间保留 8vp，“电池设置”使用 `PillButton`。
### user
```json
{"userQuery":"显示电池温度和充电状态，使用蓝色渐变，并能打开电池设置。","size":"2x2","assetCandidates":[],"eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"battery"}}],"dataModelSchema":{"data":{"phoneBattery":{"batteryTemperatureText":{"type":"string","description":"包含单位的电池温度文本","sampleValue":"29.0°C"},"chargingStatusDesc":{"type":"string","description":"当前充电状态","sampleValue":"未充电"}}}}}
```
### assistant
```genui
["root","Layout",{"layout":"S-title-primary-secondary-action","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["title","primary","support","action"]]
["title","SingleLineTitle",{"title":"电池温度","fontSize":12}]
["primary","EmphasizedData",{"value":{"path":"/data/phoneBattery/batteryTemperatureText"},"fontSize":30}]
["support","SecondaryBody",{"items":[{"value":{"path":"/data/phoneBattery/chargingStatusDesc"}}],"fontSize":14}]
["action","PillButton",{"label":"电池设置","onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"battery"}}]}]
["/data/phoneBattery/batteryTemperatureText","29.0°C"]
["/data/phoneBattery/chargingStatusDesc","未充电"]
```

## 示例十三（2x2-V02）：FreeBuds 状态 + 蓝牙设置（`S-title-anchor`·蓝色微渐变）
本例使用“标题锚点内容”：耳机名称进入标题，连接状态放在主内容区；左耳、右耳和耳机仓是三个图标可区分的同级占比，使用纵向 `NumericRatioStack` 放在左下支撑区；蓝牙设置使用准确图标的 `CircleButton` 放在右下角。
底部锚点行高56vp，左侧支撑区宽78vp，右侧动作槽为40×40vp并底对齐；不得增加歌单按钮，也不用音乐图标表达耳机电量。
### user
```json
{"userQuery":"做张耳机小卡片，看看耳机叫什么、连上没有，左右耳和充电盒还剩多少电，再放个打开蓝牙设置的按钮。","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"bluetooth_entry"}},{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4"}}],"dataModelSchema":{"data":{"earphone":{"isConnected":{"type":"boolean","description":"当前是否处于耳机连接活跃状态","sampleValue":true},"earphoneName":{"type":"string","description":"耳机广播名称","sampleValue":"FreeBuds Pro 3"},"leftBatteryLevel":{"type":"integer","description":"左耳电量百分比0到100","sampleValue":47},"rightBatteryLevel":{"type":"integer","description":"右耳电量百分比0到100","sampleValue":62},"batteryLevel":{"type":"integer","description":"充电盒电量百分比0到100","sampleValue":95}}}},"assetCandidates":[{"src":"resources/base/media/l_circle_fill.svg","description":"左耳电量使用的单色L圆形图标"},{"src":"resources/base/media/r_circle_fill.svg","description":"右耳电量使用的单色R圆形图标"},{"src":"resources/base/media/earphone_case_16644.svg","description":"耳机仓电量使用的单色耳机仓图标"},{"src":"resources/base/media/ic_Bluetooth.svg","description":"打开蓝牙设置使用的单色蓝牙图标"},{"src":"resources/base/media/music_fill.svg","description":"音乐播放入口使用的音符图标，与本次耳机状态需求无关"}]}
```
### assistant
```genui
["root","Layout",{"layout":"S-title-anchor","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["title","primary","support","action"]]
["title","SingleLineTitle",{"title":{"path":"/data/earphone/earphoneName"},"fontSize":12}]
["primary","EmphasisText",{"mainText":"{{ ${/data/earphone/isConnected} ? '已连接' : '未连接' }}","fontSize":18}]
["support","NumericRatioStack",{"direction":"column","items":[{"icon":"resources/base/media/l_circle_fill.svg","value":{"path":"/data/earphone/leftBatteryLevel"},"unit":"%"},{"icon":"resources/base/media/r_circle_fill.svg","value":{"path":"/data/earphone/rightBatteryLevel"},"unit":"%"},{"icon":"resources/base/media/earphone_case_16644.svg","value":{"path":"/data/earphone/batteryLevel"},"unit":"%"}],"fillColor":"#FF1F4799"}]
["action","CircleButton",{"icon":"resources/base/media/ic_Bluetooth.svg","accessibility":{"label":"打开蓝牙设置"},"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"bluetooth_entry"}}]}]
["/data/earphone/isConnected",true]
["/data/earphone/earphoneName","FreeBuds Pro 3"]
["/data/earphone/leftBatteryLevel",47]
["/data/earphone/rightBatteryLevel",62]
["/data/earphone/batteryLevel",95]
```

## 示例十四（2x2-V08）：耳机状态与右下蓝牙设置（`S-title-anchor`）
连接状态是主信息；左下耳机仓电量使用SecondaryBody作为辅助信息，不再以第二个EmphasisText形成两个视觉重点。
主内容、能够独立表达信息的左下内容和准确图标动作天然形成左文右动作关系时，可直接选择 `S-title-anchor`，
不需要先证明底部文字按钮失败。动作可以由准确图标表达且不要求显示文字时使用 `CircleButton`。按钮本体固定
`36×36vp`，放在底部 Row 末项的 `40×40vp` 居中 Stack 中；完整动作名称写入 `accessibility.label`。
### user
```json
{"userQuery":"做张耳机状态卡片，显示名称、连接状态和电量，右下角用蓝牙图标打开蓝牙设置。","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"bluetooth_entry"}}],"dataModelSchema":{"data":{"earphone":{"earphoneName":{"type":"string","description":"耳机名称","sampleValue":"FreeBuds Pro 3"},"isConnected":{"type":"boolean","description":"当前是否连接","sampleValue":true},"batteryLevel":{"type":"integer","description":"耳机盒电量百分比0到100","sampleValue":68}}}},"assetCandidates":[{"src":"resources/base/media/bluetooth_fill.svg","description":"蓝牙设置入口的单色蓝牙图标"}]}
```
### assistant
```genui
["root","Layout",{"layout":"S-title-anchor","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["title_area","connection","battery","settings_action"]]
["title_area","SingleLineTitle",{"title":{"path":"/data/earphone/earphoneName"},"fontSize":12}]
["connection","EmphasisText",{"mainText":"{{ ${/data/earphone/isConnected} ? '已连接' : '未连接' }}","fontSize":18}]
["battery","SecondaryBody",{"columns":1,"items":[{"label":"耳机仓","value":"{{ ${/data/earphone/batteryLevel} + '%' }}"}],"fontSize":14}]
["settings_action","CircleButton",{"icon":"resources/base/media/bluetooth_fill.svg","accessibility":{"label":"打开蓝牙设置"},"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"bluetooth_entry"}}]}]
["/data/earphone/earphoneName","FreeBuds Pro 3"]
["/data/earphone/isConnected",true]
["/data/earphone/batteryLevel",68]
```

## 示例十五（2x2-V14）：线上评审与右下入会（`S-title-anchor`）
会议标题和开始时间属于同一个日程事件，使用 `EventCard` 放在上方主内容区；事件标题保持单行，为下方时间
保留固定的 16vp。耳机连接状态和耳机仓电量是两项同级辅助属性，使用两行 `SecondaryBody` 放在左下
38vp 支撑区。候选中存在与入会动作准确匹配的
会议 SVG，且用户没有要求卡面显示按钮文案，因此入会动作优先使用右下角 `CircleButton`，不能先选择
`PillButton`，再把 `EventCard` 降级为普通正文来腾出空间。会议演示板图标已分配给按钮，标题不得重复
使用；标题表达的是会议主信息，应从剩余素材中选择同属会议日程语义的日历图标，不能使用只对应次要
耳机状态的耳机图标，也不能因首选会议图标冲突直接省略。

### user
```json
{"userQuery":"下午三点有合作方线上评审会，日程中有可用的入会链接，帮我做个卡片，看会议开始时间、耳机是否连接和耳机仓电量，点击按钮一键入会。","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"EnterMeeting","bundleName":"","abilityName":"","uri":"{{ ${/data/calendar/events/0/oneClickServiceLink} }}"}}],"dataModelSchema":{"data":{"calendar":{"events":[{"dtStart":{"type":"string","description":"格式化后的日程开始时间短文本","sampleValue":"15:00"},"oneClickServiceLink":{"type":"string","description":"一键入会链接","sampleValue":"wemeet://join/review"}}]},"earphone":{"isConnected":{"type":"boolean","description":"当前是否有蓝牙耳机处于连接活跃状态","sampleValue":true},"batteryLevel":{"type":"integer","description":"耳机仓当前剩余电量百分比0到100，展示时追加%","sampleValue":80}}}},"assetCandidates":[{"src":"resources/base/media/icon_meeting.svg","description":"可染色的会议演示板图标，适用于会议、汇报、演示和议程入口"},{"src":"resources/base/media/calendar_fill.svg","description":"可染色的日历实心图标，适用于会议日程、日历事件和当日安排"},{"src":"resources/base/media/icon_earphone.svg","description":"可染色的无线耳机图标，适用于耳机连接状态"},{"src":"resources/base/media/earphone_case_16644.svg","description":"可染色的耳机仓图标，适用于耳机仓电量"}]}
```

### assistant
```genui
["root","Layout",{"layout":"S-title-anchor","linearGradient":{"direction":"RightBottom","colors":[["#FFFFE0CC",0],["#FFFFF7F2",1]]}},["title_area","event","earphone_summary","meeting_action"]]
["title_area","SingleLineTitle",{"title":"线上评审","icon":"resources/base/media/calendar_fill.svg","fontSize":12}]
["event","EventCard",{"items":[{"title":"合作方线上评审","time":{"path":"/data/calendar/events/0/dtStart"}}]}]
["earphone_summary","SecondaryBody",{"columns":1,"items":[{"label":"耳机","value":"{{ ${/data/earphone/isConnected} ? '已连接' : '未连接' }}"},{"label":"耳机仓","value":"{{ ${/data/earphone/batteryLevel} + '%' }}"}],"fontSize":12}]
["meeting_action","CircleButton",{"icon":"resources/base/media/icon_meeting.svg","accessibility":{"label":"一键入会"},"onClick":[{"call":"clickToDeeplink","args":{"intentName":"EnterMeeting","bundleName":"","abilityName":"","uri":"{{ ${/data/calendar/events/0/oneClickServiceLink} }}"}}]}]
["/data/calendar/events/0/dtStart","15:00"]
["/data/calendar/events/0/oneClickServiceLink","wemeet://join/review"]
["/data/earphone/isConnected",true]
["/data/earphone/batteryLevel",80]
```

## 示例十六（2x2-V03）：耳机盒电量与双入口（`S-content-dual-action`）
紧凑信息区固定 38vp，两个CardButton各占36vp，三个区域之间分别保留 8vp，满足 `38 + 8 + 36 + 8 + 36 = 126vp`。电量与充电状态是两项需要逐项查看的等权信息，使用两行 `TableText`，不把两个 `SecondaryBody` 与按钮组成无核心信息区；不生成标题组件、独立大数字区或标题图标。示例的两个入口均由用户明确要求，不能因候选存在而自动增加按钮。
### user
```json
{"userQuery":"显示耳机盒电量和充电状态，并提供每日歌单和收藏歌单两个入口。","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4"}},{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=favoriteSong&type=412"}}],"dataModelSchema":{"data":{"earphone":{"batteryLevel":{"type":"integer","description":"耳机盒电量百分比0到100，展示时追加%","sampleValue":80},"chargingStatusDesc":{"type":"string","description":"充电状态","sampleValue":"未充电"}}}},"assetCandidates":[{"src":"resources/base/media/music_fill.svg","description":"每日歌单音乐图标"},{"src":"resources/base/media/heart_fill.svg","description":"收藏歌单心形图标"}]}
```
### assistant
```genui
["root","Layout",{"layout":"S-content-dual-action","linearGradient":{"direction":"RightBottom","colors":[["#FFDBCCFF",0],["#FFF6F2FF",1]]}},["battery_summary","cta_play","cta_fav"]]
["battery_summary","TableText",{"items":[{"label":"耳机盒","value":"{{ ${/data/earphone/batteryLevel} + '%' }}"},{"label":"状态","value":{"path":"/data/earphone/chargingStatusDesc"}}],"fontSize":12}]
["cta_play","CardButton",{"label":"每日歌单","icon":"resources/base/media/music_fill.svg","onClick":[{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4"}}]}]
["cta_fav","CardButton",{"label":"收藏歌单","icon":"resources/base/media/heart_fill.svg","onClick":[{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=favoriteSong&type=412"}}]}]
["/data/earphone/batteryLevel",80]
["/data/earphone/chargingStatusDesc","未充电"]
```

## 示例十七（2x2-V17）：纯双操作卡片（`S-content-dual-action` · `actions-only`）

只有两个必要操作，没有展示事实。两个CardButton分别承载原始候选事件，使用actions-only，不补标题或占位正文。按钮各57vp、间距8vp，在126vp安全区内整体居中；图标来自候选，尺寸由布局决定。

### user
```json
{"userQuery":"只放每日歌单、收藏歌单两个独立入口，不显示状态和其它信息。","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4"}},{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=favoriteSong&type=412"}}],"dataModelSchema":{"data":{}},"assetCandidates":[{"src":"resources/base/media/music_fill.svg","description":"每日歌单音乐图标"},{"src":"resources/base/media/heart_fill.svg","description":"收藏歌单心形图标"}]}
```

### assistant
```genui
["root","Layout",{"layout":"S-content-dual-action","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]},"variant":"actions-only"},["daily","favorite"]]
["daily","CardButton",{"label":"每日歌单","icon":"resources/base/media/music_fill.svg","onClick":[{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4"}}]}]
["favorite","CardButton",{"label":"收藏歌单","icon":"resources/base/media/heart_fill.svg","onClick":[{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=favoriteSong&type=412"}}]}]
```

## 示例十八（2x2-V18）：单一读数与双卡片按钮（`S-content-dual-action`）

正文只有耳机盒电量这一项；使用EmphasizedData，数值与百分比单位分别表达，在38vp内容预算内承载。两个CardButton各36vp、间距8vp；不改回PillButton，不把动态读数静态写进label。与V03的两项属性不同，本例没有额外补充，不为填满正文增加状态。

### user
```json
{"userQuery":"展示耳机盒电量，再放每日歌单和收藏歌单两个入口。","size":"2x2","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4"}},{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=favoriteSong&type=412"}}],"dataModelSchema":{"data":{"earphone":{"batteryLevel":{"type":"integer","description":"耳机盒电量百分比0到100，展示时追加%","sampleValue":80}}}},"assetCandidates":[{"src":"resources/base/media/music_fill.svg","description":"每日歌单音乐图标"},{"src":"resources/base/media/heart_fill.svg","description":"收藏歌单心形图标"}]}
```

### assistant
```genui
["root","Layout",{"layout":"S-content-dual-action","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["summary","daily","favorite"]]
["summary","EmphasizedData",{"value":{"path":"/data/earphone/batteryLevel"},"unit":"%","fontSize":30}]
["daily","CardButton",{"label":"每日歌单","icon":"resources/base/media/music_fill.svg","onClick":[{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4"}}]}]
["favorite","CardButton",{"label":"收藏歌单","icon":"resources/base/media/heart_fill.svg","onClick":[{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=favoriteSong&type=412"}}]}]
["/data/earphone/batteryLevel",80]
```

## 示例十九（2x2-V07）：双城市天气（`S-dual-info`）
root 纵向放置两个等权 `InfoBlock`，间距为 8vp。每个信息块的 `primaryText` 在同一条表达式中拼接动态城市名与完整温度文本，`secondaryText` 绑定天气状况；本例不使用图标、标题或动作。
### user
```json
{"userQuery":"同时看上海和北京现在的温度与天气，不需要按钮。","size":"2x2","assetCandidates":[],"eventCandidates":[],"dataModelSchema":{"data":{"shanghai":{"location":{"prefectureName":{"type":"string","description":"城市名称","sampleValue":"上海"}},"current":{"temperatureText":{"type":"string","description":"含单位的当前温度文本","sampleValue":"29°C"},"condition":{"type":"string","description":"天气状况","sampleValue":"多云"}}},"beijing":{"location":{"prefectureName":{"type":"string","description":"城市名称","sampleValue":"北京"}},"current":{"temperatureText":{"type":"string","description":"含单位的当前温度文本","sampleValue":"18°C"},"condition":{"type":"string","description":"天气状况","sampleValue":"晴"}}}}}}
```
### assistant
```genui
["root","Layout",{"layout":"S-dual-info","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["first","second"]]
["first","InfoBlock",{"primaryText":"{{ ${/data/shanghai/location/prefectureName} + ' ' + ${/data/shanghai/current/temperatureText} }}","secondaryText":{"path":"/data/shanghai/current/condition"},"backgroundColor":"#CCFFFFFF"}]
["second","InfoBlock",{"primaryText":"{{ ${/data/beijing/location/prefectureName} + ' ' + ${/data/beijing/current/temperatureText} }}","secondaryText":{"path":"/data/beijing/current/condition"},"backgroundColor":"#CCFFFFFF"}]
["/data/shanghai/location/prefectureName","上海"]
["/data/shanghai/current/temperatureText","29°C"]
["/data/shanghai/current/condition","多云"]
["/data/beijing/location/prefectureName","北京"]
["/data/beijing/current/temperatureText","18°C"]
["/data/beijing/current/condition","晴"]
```
