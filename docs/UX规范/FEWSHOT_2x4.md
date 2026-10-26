# 2x4 Few-shot

配套规范：[通用卡片 UX 规范](UX-SPEC.md)。本文件按原有“示例说明 → user → assistant”格式，同步当前 Fusion 完整案例，不再使用旧单步走的自由基础组件案例。

**来源版本：2026-10-23，main `56c3e7827f080c3250caac4c580008679811698f`。** 维护源：[`prompt_source/fewshots/2x4.md`](https://github.com/InnovationTea/CreateMyCard/blob/56c3e7827f080c3250caac4c580008679811698f/widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/fewshots/2x4.md)，共 11 例。案例 ID 保留维护源编号，不按本文件顺序重新编号。

以下案例仅用于参考信息关系、组件组合和布局表达；当前 TaskSpec、已接受 Plan、组件与布局合同优先。不得复制本轮输入没有的事实、路径、事件、素材或样例数据，不为贴合案例删减、补造或静态化信息。

**主题与容量说明：** 下列输入与 DSL 代码块原样同步维护源，不是最终模型请求或主题后 A2UI。维护源中保留的颜色、渐变、design 及标题中的主题名，在实际布局提示组装时按 layout-only 规则清理，布局定稿后统一应用本轮主题；不能直接认定最终沿用示例颜色。历史标题中的 Sub-118 / Sub-140 仅是维护说明，不是当前允许输出的布局名，实际以示例的 Region.variant 为准。几何数字是参考容量，不是固定生产宿主。案例同步不代表本轮重新生成或真机验收通过。

## 示例一（2x4-V03）：睡眠得分与双详情（`W-top-bottom` · 紧密连续 · 紫色微渐变）
组件选择：`EmphasizedData`、`TextBlock`。
按本例对象、事实与动作归属组合；读数、完整单位与动态路径保留，不按字段机械拆组件。标题、动作和组件行高使用固定设计值，正文承接所属区域剩余空间；实例只示范合同，不授权额外事实或事件。
82分改用强调数值；主体按自然高度排列，明细承接剩余高度，主体至明细8vp。
TextBlock 撑满父槽，因此选择 continuous；不把只有最小高度的明细区当作确定可分配高度。

### user
```json
{"userQuery":"昨晚睡得怎么样？帮我做张卡片，看看睡眠得分、总共睡了多久、深睡了多久。","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"healthSport":{"sleepScore":{"type":"integer","description":"0到100的睡眠综合得分","sampleValue":82},"nightSleepDurationText":{"type":"string","description":"夜间睡眠总时长","sampleValue":"7小时1分"},"deepSleepDurationText":{"type":"string","description":"深睡时长","sampleValue":"2小时15分"}}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Layout",{"layout":"W-top-bottom","linearGradient":{"direction":"RightBottom","colors":[["#FFDBCCFF",0],["#FFF6F2FF",1]]},"variant":"continuous"},["primary","details"]]
["primary_label","SecondaryBody",{"items":[{"value":"睡眠得分"}],"fontSize":14}]
["primary_value","EmphasizedData",{"value":{"path":"/data/healthSport/sleepScore"},"unit":"分","fontSize":30}]
["primary","Group",{"variant":"label-value"},["primary_label","primary_value"]]
["details","TextBlock",{"items":[{"label":"睡眠时长","value":{"path":"/data/healthSport/nightSleepDurationText"}},{"label":"深睡时长","value":{"path":"/data/healthSport/deepSleepDurationText"}}]}]
["/data/healthSport/sleepScore",82]
["/data/healthSport/nightSleepDurationText","7小时1分"]
["/data/healthSport/deepSleepDurationText","2小时15分"]
```

## 示例二（2x4-V16）：一个主题的汇总与三项明细（`W-top-bottom` · 紧密连续）
组件选择：`SingleLineTitle`、`EmphasizedData`、`TextBlock`。
按本例对象、事实与动作归属组合；读数、完整单位与动态路径保留，不按字段机械拆组件。标题、动作和组件行高使用固定设计值，正文承接所属区域剩余空间；实例只示范合同，不授权额外事实或事件。
96与千瓦时分离；标题至内容区6vp，内容区内主值至明细8vp，明细承接剩余空间。没有动作消费素材，
电力图标与整张用电卡片主题匹配，因此默认分配给标题；带图标标题按20vp参与预算，20×20vp图标由20vp高Row在右侧垂直居中。

### user
```json
{"userQuery":"展示本周工作室总用电量，以及照明、空调和设备用电分别是多少。","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"studioPower":{"lightingText":{"type":"string","description":"本周照明用电量","sampleValue":"18千瓦时"},"coolingText":{"type":"string","description":"本周空调用电量","sampleValue":"34千瓦时"},"equipmentText":{"type":"string","description":"本周设备用电量","sampleValue":"29千瓦时"},"totalKwh":{"type":"number","description":"本周工作室总用电量（千瓦时）","sampleValue":96}}}},"assetCandidates":[{"src":"resources/base/media/bolt_fill.svg","description":"可染色的闪电实心图标，适用于电力、用电量和供电状态"}]}
```

### assistant
```genui
["root","Layout",{"layout":"W-top-bottom","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]},"variant":"continuous"},["title","primary","details"]]
["title","SingleLineTitle",{"title":"本周工作室用电","icon":"resources/base/media/bolt_fill.svg","fontSize":12}]
["primary","EmphasizedData",{"value":{"path":"/data/studioPower/totalKwh"},"unit":"千瓦时","fontSize":30}]
["details","TextBlock",{"items":[{"label":"照明","value":{"path":"/data/studioPower/lightingText"}},{"label":"空调","value":{"path":"/data/studioPower/coolingText"}},{"label":"设备","value":{"path":"/data/studioPower/equipmentText"}}]}]
["/data/studioPower/totalKwh",96]
["/data/studioPower/lightingText","18千瓦时"]
["/data/studioPower/coolingText","34千瓦时"]
["/data/studioPower/equipmentText","29千瓦时"]
```

## 示例三（2x4-V28）：本周睡眠汇总与三个指标（`W-top-bottom` · 紧密连续）

### 选型依据
4 个必需数据、0 个 Action；一个汇总进入主槽，3 个同级短明细合入唯一 TextBlock。

沿用信息归属和同级关系；标题至内容区6vp，主值使用自然高度，明细以8vp间距承接剩余空间。组件使用当前合同，示例字段和动作仅来自本例输入。

### user
```json
{"userQuery":"查看本周平均睡眠时长、平均入睡时间、醒来时间和深睡时长。","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"sleepWeek":{"average":{"type":"string","description":"sleepWeek.average","sampleValue":"7小时20分"},"fallAsleep":{"type":"string","description":"sleepWeek.fallAsleep","sampleValue":"23:10"},"wakeUp":{"type":"string","description":"sleepWeek.wakeUp","sampleValue":"06:30"},"deep":{"type":"string","description":"sleepWeek.deep","sampleValue":"1小时45分"}}}},"assetCandidates":[]}
```
### assistant
```genui
["root","Layout",{"layout":"W-top-bottom","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]},"variant":"continuous"},["title","primary","details"]]
["title","SingleLineTitle",{"title":"平均睡眠","fontSize":12}]
["primary","EmphasisText",{"mainText":{"path":"/data/sleepWeek/average"},"fontSize":18}]
["details","TextBlock",{"items":[{"label":"入睡","value":{"path":"/data/sleepWeek/fallAsleep"}},{"label":"醒来","value":{"path":"/data/sleepWeek/wakeUp"}},{"label":"深睡","value":{"path":"/data/sleepWeek/deep"}}]}]
["/data/sleepWeek/average","7小时20分"]
["/data/sleepWeek/fallAsleep","23:10"]
["/data/sleepWeek/wakeUp","06:30"]
["/data/sleepWeek/deep","1小时45分"]
```

## 示例四（2x4-V39）：行程汇总与三条短摘要（`W-top-bottom` · `SummaryList`）

### 选型依据
同一行程主题下只有一行汇总和三条等权、可单行显示的摘要。省略独立title槽，将汇总行作为primary；
SummaryList进入details并由Runtime贴底。组件只提交items，不输出颜色属性或内部几何。

### user
```json
{"userQuery":"做张杭州2天1晚秋日漫游卡片，显示距离出发还有多少天，以及第一天上午、午餐和下午的安排。","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"trip":{"countdownDays":{"type":"integer","description":"距离杭州行程出发的天数","sampleValue":30},"day1MorningText":{"type":"string","description":"第一天上午的时间与安排摘要","sampleValue":"Day1 · 09:00-11:30 · 灵隐寺祈福"},"day1LunchText":{"type":"string","description":"第一天午餐的时间与安排摘要","sampleValue":"Day1 · 11:30-13:00 · 知竹素菜馆午餐"},"day1AfternoonText":{"type":"string","description":"第一天下午的时间与安排摘要","sampleValue":"Day1 · 13:30-16:30 · 浙江省博物馆新馆"}}}},"assetCandidates":[]}
```

### assistant
```genui
["root","Layout",{"layout":"W-top-bottom","linearGradient":{"direction":"RightBottom","colors":[["#FFFFE0CC",0],["#FFFFF7F2",1]]},"variant":"continuous"},["primary","details"]]
["primary","SingleLineTitle",{"title":"{{ '杭州2天1晚秋日漫游 · 距离出发还有 ' + ${/data/trip/countdownDays} + ' 天' }}","fontSize":12}]
["details","SummaryList",{"items":[{"path":"/data/trip/day1MorningText"},{"path":"/data/trip/day1LunchText"},{"path":"/data/trip/day1AfternoonText"}]}]
["/data/trip/countdownDays",30]
["/data/trip/day1MorningText","Day1 · 09:00-11:30 · 灵隐寺祈福"]
["/data/trip/day1LunchText","Day1 · 11:30-13:00 · 知竹素菜馆午餐"]
["/data/trip/day1AfternoonText","Day1 · 13:30-16:30 · 浙江省博物馆新馆"]
```

## 示例五（2x4-V09）：天气与手机电量双业务（`W-split-panels` · `Sub-118-D × 2` · 蓝色微渐变）
组件选择：`SingleLineTitle`、`EmphasisText`、`PillButton`。
按本例对象、事实与动作归属组合；读数、完整单位与动态路径保留，不按字段机械拆组件。标题、动作和组件行高使用固定设计值，正文承接所属区域剩余空间；实例只示范合同，不授权额外事实或事件。
保留双侧标题；每侧主值与状态合入一个 EmphasisText 内容组，标题、内容组和按钮按6vp排列。

### user
```json
{"userQuery":"做张卡片，看看上海现在的天气和手机剩余电量，还能分别打开天气详情和电池设置。","size":"2x4","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"Weather_CityCode","uri":"{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' + ${/data/weather/location/cityCode} }}"}},{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"battery"}},{"call":"clickToDeeplink","args":{"intentName":"Music","bundleName":"","abilityName":"","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4"}}],"dataModelSchema":{"data":{"weather":{"location":{"cityCode":{"type":"string","description":"城市编码","sampleValue":"101020100"}},"current":{"condition":{"type":"string","description":"天气状况","sampleValue":"多云"},"temperatureC":{"type":"integer","description":"当前温度","sampleValue":29}}},"phoneBattery":{"batterySOC":{"type":"integer","description":"手机电量百分比","sampleValue":68},"chargingStatusDesc":{"type":"string","description":"充电状态","sampleValue":"未充电"}}}},"assetCandidates":[{"src":"resources/base/media/music_fill.svg","description":"样式：音乐音符实心图标，默认黑色，图形为双音符连接造型；适用：音乐播放卡片、音频功能入口、歌单展示。"},{"src":"resources/base/media/alarm_fill_1.svg","description":"样式：默认黑色的单色闹钟实心图标，内部通过镂空表现表盘指针，支持通过 fillColor 与卡片配色统一；适用：闹钟设置、定时提醒、日程提醒。"}]}
```
### assistant
```genui
["root","Layout",{"layout":"W-split-panels","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["left","right"]]
["left_title","SingleLineTitle",{"title":"天气","fontSize":12}]
["left_action","PillButton",{"label":"查看天气","onClick":[{"call":"clickToDeeplink","args":{"intentName":"Weather_CityCode","uri":"{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' + ${/data/weather/location/cityCode} }}"}}]}]
["left_body","EmphasisText",{"mainText":"{{ ${/data/weather/current/temperatureC} + '°C' }}","secondaryText":{"path":"/data/weather/current/condition"},"fontSize":18}]
["left","Region",{"variant":"title-content-action"},["left_title","left_body","left_action"]]
["right_title","SingleLineTitle",{"title":"手机电量","fontSize":12}]
["right_action","PillButton",{"label":"电池设置","onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"battery"}}]}]
["right_body","EmphasisText",{"mainText":"{{ ${/data/phoneBattery/batterySOC} + '%' }}","secondaryText":{"path":"/data/phoneBattery/chargingStatusDesc"},"fontSize":18}]
["right","Region",{"variant":"title-content-action"},["right_title","right_body","right_action"]]
["/data/weather/location/cityCode","101020100"]
["/data/weather/current/condition","多云"]
["/data/weather/current/temperatureC",29]
["/data/phoneBattery/batterySOC",68]
["/data/phoneBattery/chargingStatusDesc","未充电"]
```

## 示例六（2x4-V08）：下一日程与双真实入口（`W-content-side-slots` · `Sub-140-B` · 黄色微渐变）
组件选择：`SingleLineTitle`、`EventCard`、`CardButton`。
按本例对象、事实与动作归属组合；读数、完整单位与动态路径保留，不按字段机械拆组件。标题、动作和组件行高使用固定设计值，正文承接所属区域剩余空间；实例只示范合同，不授权额外事实或事件。
### user
```json
{"userQuery":"做张日程提醒卡片，看看下一件事是什么、在哪里、几点开始和结束，再放上查看这条日程和打开专注设置的按钮。","size":"2x4","eventCandidates":[{"call":"clickToIntent","args":{"intentName":"ViewCalendarEvent","params":{"entityId":"{{ ${/data/calendar/events/0/entityId} }}"}}},{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"intelligent_scene_entry"}}],"dataModelSchema":{"data":{"calendar":{"events":[{"title":{"type":"string","description":"日程标题","sampleValue":"需求评审会"},"eventLocation":{"type":"string","description":"日程地点","sampleValue":"五和大道华为基地"},"dtStart":{"type":"string","description":"开始时间","sampleValue":"14:00"},"dtEnd":{"type":"string","description":"结束时间","sampleValue":"15:30"},"entityId":{"type":"string","description":"日程实体ID","sampleValue":"calendar-event-001"}}]}}},"assetCandidates":[{"src":"resources/base/media/calendar_fill.svg","description":"可染色的日历图标，适用于查看日程详情"},{"src":"resources/base/media/icon_focus.svg","description":"可染色的专注图标，适用于打开专注设置"}]}
```
### assistant
```genui
["root","Layout",{"layout":"W-content-side-slots","linearGradient":{"direction":"RightBottom","colors":[["#FFFFE0CC",0],["#FFFFF7F2",1]]}},["content","upper","lower"]]
["content_title","SingleLineTitle",{"title":"下一个日程","fontSize":12}]
["content_body","EventCard",{"items":[{"title":{"path":"/data/calendar/events/0/title"},"time":"{{ ${/data/calendar/events/0/dtStart} + ' - ' + ${/data/calendar/events/0/dtEnd} }}","location":{"path":"/data/calendar/events/0/eventLocation"}}]}]
["content","Region",{"variant":"title-content"},["content_title","content_body"]]
["upper","CardButton",{"label":"查看日程","icon":"resources/base/media/calendar_fill.svg","onClick":[{"call":"clickToIntent","args":{"intentName":"ViewCalendarEvent","params":{"entityId":"{{ ${/data/calendar/events/0/entityId} }}"}}}]}]
["lower","CardButton",{"label":"专注模式","icon":"resources/base/media/icon_focus.svg","onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"intelligent_scene_entry"}}]}]
["/data/calendar/events/0/title","需求评审会"]
["/data/calendar/events/0/eventLocation","五和大道华为基地"]
["/data/calendar/events/0/dtStart","14:00"]
["/data/calendar/events/0/dtEnd","15:30"]
["/data/calendar/events/0/entityId","calendar-event-001"]
```

## 示例七（2x4-V10）：天气、手机与耳机三数据（`W-content-side-slots` · `Sub-140-F` · 蓝色微渐变）
组件选择：`SingleLineTitle`、`EmphasizedData`、`SecondaryBody`、`PillButton`、`InfoBlock`。
按本例对象、事实与动作归属组合；读数、完整单位与动态路径保留，不按字段机械拆组件。标题、动作和组件行高使用固定设计值，正文承接所属区域剩余空间；实例只示范合同，不授权额外事实或事件。
标题至读数组8vp，温度与多云2vp；动作按8vp外间距沉底，明确手机电量68%。

### user
```json
{"userQuery":"帮我做张卡片，主要看上海现在的天气，顺便看看手机剩余电量、有没有在充电，以及耳机连上没有。还要能打开天气详情。","size":"2x4","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"Weather_CityCode","uri":"{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' + ${/data/weather/location/cityCode} }}"}}],"dataModelSchema":{"data":{"weather":{"location":{"cityCode":{"type":"string","description":"城市编码","sampleValue":"101020100"}},"current":{"condition":{"type":"string","description":"天气状况","sampleValue":"多云"},"temperatureC":{"type":"integer","description":"当前温度","sampleValue":29}}},"phoneBattery":{"batterySOC":{"type":"integer","description":"手机电量百分比","sampleValue":68},"chargingStatusDesc":{"type":"string","description":"充电状态","sampleValue":"未充电"}},"earphone":{"isConnected":{"type":"boolean","description":"耳机是否连接","sampleValue":true}}}},"assetCandidates":[{"src":"resources/base/media/earphone_case_16644.svg","description":"本地耳机盒图标"}]}
```
### assistant
```genui
["root","Layout",{"layout":"W-content-side-slots","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["content","upper","lower"]]
["content_title","SingleLineTitle",{"title":"上海天气","fontSize":12}]
["content_action","PillButton",{"label":"查看天气","onClick":[{"call":"clickToDeeplink","args":{"intentName":"Weather_CityCode","uri":"{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' + ${/data/weather/location/cityCode} }}"}}]}]
["content_primary","EmphasizedData",{"value":{"path":"/data/weather/current/temperatureC"},"unit":"°C","fontSize":30}]
["content_support","SecondaryBody",{"items":[{"value":{"path":"/data/weather/current/condition"}}],"fontSize":14}]
["content","Region",{"variant":"title-hero-support-action"},["content_title","content_primary","content_support","content_action"]]
["upper","InfoBlock",{"variant":"slot","primaryText":"{{ '手机电量 ' + ${/data/phoneBattery/batterySOC} + '%' }}","secondaryText":{"path":"/data/phoneBattery/chargingStatusDesc"},"backgroundColor":"#99FFFFFF"}]
["lower","InfoBlock",{"variant":"slot","primaryText":"{{ ${/data/earphone/isConnected} ? '已连接' : '未连接' }}","secondaryText":"耳机","backgroundColor":"#99FFFFFF","icon":"resources/base/media/earphone_case_16644.svg","fillColor":"#FF1F4799"}]
["/data/weather/location/cityCode","101020100"]
["/data/weather/current/condition","多云"]
["/data/weather/current/temperatureC",29]
["/data/phoneBattery/batterySOC",68]
["/data/phoneBattery/chargingStatusDesc","未充电"]
["/data/earphone/isConnected",true]
```

## 示例八（2x4-V23）：五项必要事实与单动作（`W-content-side-slots` · `Sub-140-G`）
组件选择：`SingleLineTitle`、`InfoBlock`、`SecondaryBody`、`CardButton`、`EmphasizedData`。
按本例对象、事实与动作归属组合；读数、完整单位与动态路径保留，不按字段机械拆组件。标题、动作和组件行高使用固定设计值，正文承接所属区域剩余空间；实例只示范合同，不授权额外事实或事件。
温度使用数值28与独立单位°C，数值强调、单位小字号，沿用组件底部对齐规范；电流、电压和更新时间使用次要文本。

### user
```json
{"userQuery":"查看监测器温度、电流、电压、连接状态和更新时间，并打开设备设置。","size":"2x4","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"DeviceSettings","bundleName":"com.example.sensor","abilityName":"SettingsAbility","uri":"sensor://settings"}}],"dataModelSchema":{"data":{"sensor":{"currentText":{"type":"string","description":"已含单位的电流","sampleValue":"-151mA"},"voltageText":{"type":"string","description":"已含单位的电压","sampleValue":"4V"},"connectionText":{"type":"string","description":"连接状态","sampleValue":"连接正常"},"updatedAt":{"type":"string","description":"数据更新时间","sampleValue":"09:00"},"temperatureC":{"type":"number","description":"监测器温度（摄氏度）","sampleValue":28}}}},"assetCandidates":[{"src":"resources/base/media/gearshape_fill.svg","description":"可染色的齿轮设置图标，适用于打开设备设置"}]}
```

### assistant
```genui
["root","Layout",{"layout":"W-content-side-slots","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["content","upper","lower"]]
["content_title","SingleLineTitle",{"title":"监测器温度","fontSize":12}]
["content_primary","EmphasizedData",{"value":{"path":"/data/sensor/temperatureC"},"unit":"℃","fontSize":30}]
["content_support","SecondaryBody",{"columns":1,"items":[{"label":"电流","value":{"path":"/data/sensor/currentText"}},{"label":"电压","value":{"path":"/data/sensor/voltageText"}},{"label":"更新","value":{"path":"/data/sensor/updatedAt"}}],"separator":"｜","fontSize":12}]
["content","Region",{"variant":"title-hero-support"},["content_title","content_primary","content_support"]]
["upper","InfoBlock",{"variant":"slot","primaryText":{"path":"/data/sensor/connectionText"},"secondaryText":"连接状态","backgroundColor":"#99FFFFFF"}]
["lower","CardButton",{"label":"设备设置","icon":"resources/base/media/gearshape_fill.svg","onClick":[{"call":"clickToDeeplink","args":{"intentName":"DeviceSettings","bundleName":"com.example.sensor","abilityName":"SettingsAbility","uri":"sensor://settings"}}]}]
["/data/sensor/temperatureC",28]
["/data/sensor/currentText","-151mA"]
["/data/sensor/voltageText","4V"]
["/data/sensor/connectionText","连接正常"]
["/data/sensor/updatedAt","09:00"]
```

## 示例九（2x4-V06）：无标题四业务速览（`W-four-slots` · 蓝色微渐变）
组件选择：`InfoBlock`。
四个固定槽分别使用输入候选中的温度、电池、耳机仓、日历图标；图标辅助识别，不替代对象标签和值。
按本例对象、事实与动作归属组合；读数、完整单位与动态路径保留，不按字段机械拆组件。标题、动作和组件行高使用固定设计值，正文承接所属区域剩余空间；实例只示范合同，不授权额外事实或事件。
### user
```json
{"userQuery":"帮我做张卡片，一起看看现在的气温、手机和耳机盒还剩多少电，还有下一场日程几点开始。","size":"2x4","eventCandidates":[],"assetCandidates":[{"src":"resources/base/media/icon_weather_thermometer_medium.svg","description":"温度计图标，用于当前气温"},{"src":"resources/base/media/battery_leaf_fill.svg","description":"电池图标，用于手机电量"},{"src":"resources/base/media/earphone_case_16644.svg","description":"耳机仓图标，用于耳机盒电量"},{"src":"resources/base/media/calendar_fill.svg","description":"日历图标，用于日程开始时间"}],"dataModelSchema":{"data":{"weather":{"current":{"temperatureText":{"type":"string","description":"含单位的当前温度","sampleValue":"26°C"}}},"phoneBattery":{"batterySOCText":{"type":"string","description":"含单位的手机电量","sampleValue":"68%"}},"earphone":{"batteryLevel":{"type":"integer","description":"耳机盒电量百分比0到100","sampleValue":80}},"calendar":{"events":[{"dtStart":{"type":"string","description":"开始时间","sampleValue":"14:00"}}]}}}}
```
### assistant
```genui
["root","Layout",{"layout":"W-four-slots","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["weather","phone","ear","calendar"]]
["weather","InfoBlock",{"variant":"slot","primaryText":{"path":"/data/weather/current/temperatureText"},"secondaryText":"天气","backgroundColor":"#99FFFFFF","icon":"resources/base/media/icon_weather_thermometer_medium.svg","fillColor":"#FF1F4799"}]
["phone","InfoBlock",{"variant":"slot","primaryText":{"path":"/data/phoneBattery/batterySOCText"},"secondaryText":"手机电量","backgroundColor":"#99FFFFFF","icon":"resources/base/media/battery_leaf_fill.svg","fillColor":"#FF1F4799"}]
["ear","InfoBlock",{"variant":"slot","primaryText":"{{ ${/data/earphone/batteryLevel} + '%' }}","secondaryText":"耳机盒","backgroundColor":"#99FFFFFF","icon":"resources/base/media/earphone_case_16644.svg","fillColor":"#FF1F4799"}]
["calendar","InfoBlock",{"variant":"slot","primaryText":{"path":"/data/calendar/events/0/dtStart"},"secondaryText":"日程开始","backgroundColor":"#99FFFFFF","icon":"resources/base/media/calendar_fill.svg","fillColor":"#FF1F4799"}]
["/data/weather/current/temperatureText","26°C"]
["/data/phoneBattery/batterySOCText","68%"]
["/data/earphone/batteryLevel",80]
["/data/calendar/events/0/dtStart","14:00"]
```

## 示例十（2x4-V19）：四个同级必要动作（`W-four-slots`）
组件选择：`CardButton`。
按本例对象、事实与动作归属组合；读数、完整单位与动态路径保留，不按字段机械拆组件。标题、动作和组件行高使用固定设计值，正文承接所属区域剩余空间；实例只示范合同，不授权额外事实或事件。
### user
```json
{"userQuery":"做张居家快捷操作卡片，可以打开客厅灯、开启空调、开启新风和启动扫地机器人。","size":"2x4","eventCandidates":[{"call":"clickToDeeplink","args":{"intentName":"LivingRoomLightOn","bundleName":"com.example.home","abilityName":"LightAbility","uri":"home://light/on"}},{"call":"clickToDeeplink","args":{"intentName":"AirConditionerOn","bundleName":"com.example.home","abilityName":"ClimateAbility","uri":"home://air/on"}},{"call":"clickToDeeplink","args":{"intentName":"VentilationOn","bundleName":"com.example.home","abilityName":"ClimateAbility","uri":"home://ventilation/on"}},{"call":"clickToDeeplink","args":{"intentName":"RobotVacuumStart","bundleName":"com.example.home","abilityName":"CleanAbility","uri":"home://vacuum/start"}}],"dataModelSchema":{"data":{}},"assetCandidates":[{"src":"resources/base/media/lamp_ceiling_light.svg","description":"可染色的客厅吸顶灯单色图标"},{"src":"resources/base/media/air_fill.svg","description":"可染色的空调单色图标"},{"src":"resources/base/media/air_open_fill.svg","description":"可染色的新风单色图标"},{"src":"resources/base/media/clean_fill.svg","description":"可染色的清洁单色图标"}]}
```

### assistant
```genui
["root","Layout",{"layout":"W-four-slots","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["top_left","top_right","bottom_left","bottom_right"]]
["top_left","CardButton",{"label":"打开客厅灯","icon":"resources/base/media/lamp_ceiling_light.svg","onClick":[{"call":"clickToDeeplink","args":{"intentName":"LivingRoomLightOn","bundleName":"com.example.home","abilityName":"LightAbility","uri":"home://light/on"}}]}]
["top_right","CardButton",{"label":"开启空调","icon":"resources/base/media/air_fill.svg","onClick":[{"call":"clickToDeeplink","args":{"intentName":"AirConditionerOn","bundleName":"com.example.home","abilityName":"ClimateAbility","uri":"home://air/on"}}]}]
["bottom_left","CardButton",{"label":"开启新风","icon":"resources/base/media/air_open_fill.svg","onClick":[{"call":"clickToDeeplink","args":{"intentName":"VentilationOn","bundleName":"com.example.home","abilityName":"ClimateAbility","uri":"home://ventilation/on"}}]}]
["bottom_right","CardButton",{"label":"启动扫地","icon":"resources/base/media/clean_fill.svg","onClick":[{"call":"clickToDeeplink","args":{"intentName":"RobotVacuumStart","bundleName":"com.example.home","abilityName":"CleanAbility","uri":"home://vacuum/start"}}]}]
```

## 示例十一（2x4-V38）：四个独立设备状态（`W-four-slots`）

### 选型依据
四个彼此独立的设备各自占一个固定信息槽；每槽使用一个 `InfoBlock` 同时展示电量和连接状态，不重复绑定。
四槽按业务阅读顺序组成两行两列，横纵间距均为12vp。

### user
```json
{"userQuery":"查看车钥匙、手表、耳机和相机各自的电量与连接状态。","size":"2x4","eventCandidates":[],"dataModelSchema":{"data":{"devices":{"key":{"battery":{"type":"string","description":"车钥匙电量百分比文本","sampleValue":"81%"},"state":{"type":"string","description":"车钥匙连接状态","sampleValue":"已连接"}},"watch":{"battery":{"type":"string","description":"手表电量百分比文本","sampleValue":"54%"},"state":{"type":"string","description":"手表连接状态","sampleValue":"已连接"}},"buds":{"battery":{"type":"string","description":"耳机电量百分比文本","sampleValue":"63%"},"state":{"type":"string","description":"耳机连接状态","sampleValue":"已连接"}},"camera":{"battery":{"type":"string","description":"相机电量百分比文本","sampleValue":"72%"},"state":{"type":"string","description":"相机连接状态","sampleValue":"未连接"}}}}},"assetCandidates":[]}
```

### assistant
```genui
["root","Layout",{"layout":"W-four-slots","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["top_left","top_right","bottom_left","bottom_right"]]
["top_left","InfoBlock",{"primaryText":"{{ '车钥匙电量 ' + ${/data/devices/key/battery} }}","secondaryText":{"path":"/data/devices/key/state"},"variant":"slot","backgroundColor":"#99FFFFFF"}]
["top_right","InfoBlock",{"primaryText":"{{ '耳机电量 ' + ${/data/devices/buds/battery} }}","secondaryText":{"path":"/data/devices/buds/state"},"variant":"slot","backgroundColor":"#99FFFFFF"}]
["bottom_left","InfoBlock",{"primaryText":"{{ '手表电量 ' + ${/data/devices/watch/battery} }}","secondaryText":{"path":"/data/devices/watch/state"},"variant":"slot","backgroundColor":"#99FFFFFF"}]
["bottom_right","InfoBlock",{"primaryText":"{{ '相机电量 ' + ${/data/devices/camera/battery} }}","secondaryText":{"path":"/data/devices/camera/state"},"variant":"slot","backgroundColor":"#99FFFFFF"}]
["/data/devices/key/battery","81%"]
["/data/devices/key/state","已连接"]
["/data/devices/buds/battery","63%"]
["/data/devices/buds/state","已连接"]
["/data/devices/watch/battery","54%"]
["/data/devices/watch/state","已连接"]
["/data/devices/camera/battery","72%"]
["/data/devices/camera/state","未连接"]
```
