---
name: phone-widget-fewshot-library-2x4
description: 按必要数据与 Action 数量、组件和布局候选检索的 2×4 合成示例；不整体加载。
---

# 2×4 容量示例库

每个案例独立检索。业务值和 ID 仅为合成示范，不是当前输入的答案。

## 示例 07：街区用电汇总与两项明细

### 输入

```json
{
  "userQuery": "查看街区本周总用电及路灯和充电桩用电。",
  "size": "2x4",
  "actions": [],
  "data": [
    {
      "id": "blockPower.total",
      "type": "string",
      "description": "blockPower.total",
      "value": "58千瓦时"
    },
    {
      "id": "blockPower.lamp",
      "type": "string",
      "description": "blockPower.lamp",
      "value": "21千瓦时"
    },
    {
      "id": "blockPower.charger",
      "type": "string",
      "description": "blockPower.charger",
      "value": "16千瓦时"
    }
  ],
  "assetCandidates": []
}
```

### 分析

3 个必需数据、0 个 Action；一个汇总进入主槽，2 个同级短明细合入唯一 TextBlock。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x4" appearance="solid-blue" layout="top-bottom"><Region slot="title"><SingleLineTitle title="本周用电" /></Region><Region slot="primary"><EmphasisText mainText="58千瓦时" secondaryText="本周用电" dataIds={{"mainText":"blockPower.total"}} /></Region><Region slot="details"><TextBlock items={[{"label":"路灯","parameter":"21千瓦时","dataIds":{"parameter":"blockPower.lamp"}},{"label":"充电桩","parameter":"16千瓦时","dataIds":{"parameter":"blockPower.charger"}}]} /></Region></Card>`,
  "coverage": [{"requirement": "查看街区本周总用电及路灯和充电桩用电。"}],
  "unmetRequirements": []
})
```


## 示例 09：本周睡眠汇总与三个指标

### 输入

```json
{
  "userQuery": "查看本周平均睡眠时长、平均入睡时间、醒来时间和深睡时长。",
  "size": "2x4",
  "actions": [],
  "data": [
    {
      "id": "sleepWeek.average",
      "type": "string",
      "description": "sleepWeek.average",
      "value": "7小时20分"
    },
    {
      "id": "sleepWeek.fallAsleep",
      "type": "string",
      "description": "sleepWeek.fallAsleep",
      "value": "23:10"
    },
    {
      "id": "sleepWeek.wakeUp",
      "type": "string",
      "description": "sleepWeek.wakeUp",
      "value": "06:30"
    },
    {
      "id": "sleepWeek.deep",
      "type": "string",
      "description": "sleepWeek.deep",
      "value": "1小时45分"
    }
  ],
  "assetCandidates": []
}
```

### 分析

4 个必需数据、0 个 Action；一个汇总进入主槽，3 个同级短明细合入唯一 TextBlock。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x4" appearance="solid-blue" layout="top-bottom"><Region slot="title"><SingleLineTitle title="平均睡眠" /></Region><Region slot="primary"><EmphasisText mainText="7小时20分" secondaryText="平均睡眠" dataIds={{"mainText":"sleepWeek.average"}} /></Region><Region slot="details"><TextBlock items={[{"label":"入睡","parameter":"23:10","dataIds":{"parameter":"sleepWeek.fallAsleep"}},{"label":"醒来","parameter":"06:30","dataIds":{"parameter":"sleepWeek.wakeUp"}},{"label":"深睡","parameter":"1小时45分","dataIds":{"parameter":"sleepWeek.deep"}}]} /></Region></Card>`,
  "coverage": [{"requirement": "查看本周平均睡眠时长、平均入睡时间、醒来时间和深睡时长。"}],
  "unmetRequirements": []
})
```

## 示例 10：车库能耗汇总与设备分项

### 输入

```json
{
  "userQuery": "查看车库今日总能耗与照明、通风、充电设备能耗。",
  "size": "2x4",
  "actions": [],
  "data": [
    {
      "id": "garageEnergy.total",
      "type": "string",
      "description": "garageEnergy.total",
      "value": "42千瓦时"
    },
    {
      "id": "garageEnergy.lighting",
      "type": "string",
      "description": "garageEnergy.lighting",
      "value": "8千瓦时"
    },
    {
      "id": "garageEnergy.ventilation",
      "type": "string",
      "description": "garageEnergy.ventilation",
      "value": "11千瓦时"
    },
    {
      "id": "garageEnergy.charging",
      "type": "string",
      "description": "garageEnergy.charging",
      "value": "23千瓦时"
    }
  ],
  "assetCandidates": []
}
```

### 分析

4 个必需数据、0 个 Action；一个汇总进入主槽，3 个同级短明细合入唯一 TextBlock。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x4" appearance="solid-blue" layout="top-bottom"><Region slot="title"><SingleLineTitle title="今日能耗" /></Region><Region slot="primary"><EmphasisText mainText="42千瓦时" secondaryText="今日能耗" dataIds={{"mainText":"garageEnergy.total"}} /></Region><Region slot="details"><TextBlock items={[{"label":"照明","parameter":"8千瓦时","dataIds":{"parameter":"garageEnergy.lighting"}},{"label":"通风","parameter":"11千瓦时","dataIds":{"parameter":"garageEnergy.ventilation"}},{"label":"充电","parameter":"23千瓦时","dataIds":{"parameter":"garageEnergy.charging"}}]} /></Region></Card>`,
  "coverage": [{"requirement": "查看车库今日总能耗与照明、通风、充电设备能耗。"}],
  "unmetRequirements": []
})
```

## 示例 11：空气与日程各占一侧

### 输入

```json
{
  "userQuery": "查看书房空气质量，也看今天下一场会议时间。",
  "size": "2x4",
  "actions": [],
  "data": [
    {
      "id": "airStudy.quality",
      "type": "string",
      "description": "airStudy.quality",
      "value": "优良"
    },
    {
      "id": "meetingNext.time",
      "type": "string",
      "description": "meetingNext.time",
      "value": "15:30"
    }
  ],
  "assetCandidates": []
}
```

### 分析

两个独立主题各占一侧；2 个数据、0 个 Action。Action 只进入所属侧的操作位。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x4" appearance="solid-cyan" layout="split-panels"><Region slot="left" variant="compact-title-content"><SingleLineTitle title="书房空气" /><EmphasisText mainText="优良" secondaryText="空气质量" dataIds={{"mainText":"airStudy.quality"}} /></Region><Region slot="right" variant="compact-title-content"><SingleLineTitle title="会议" /><EmphasisText mainText="15:30" secondaryText="下一场时间" dataIds={{"mainText":"meetingNext.time"}} /></Region></Card>`,
  "coverage": [{"requirement": "查看书房空气质量，也看今天下一场会议时间。"}],
  "unmetRequirements": []
})
```

## 示例 12：天气和耳机分别展示，耳机有操作

### 输入

```json
{
  "userQuery": "查看天气体感和耳机电量，并打开音乐。",
  "size": "2x4",
  "actions": [
    {
      "id": "music.open",
      "description": "打开音乐"
    }
  ],
  "data": [
    {
      "id": "weatherTrip.feels",
      "type": "string",
      "description": "weatherTrip.feels",
      "value": "22℃"
    },
    {
      "id": "budsTrip.battery",
      "type": "string",
      "description": "budsTrip.battery",
      "value": "64%"
    }
  ],
  "assetCandidates": []
}
```

### 分析

两个独立主题各占一侧；2 个数据、1 个 Action。Action 只进入所属侧的操作位。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x4" appearance="solid-cyan" layout="split-panels"><Region slot="left" variant="compact-title-content"><SingleLineTitle title="天气" /><EmphasisText mainText="22℃" secondaryText="体感" dataIds={{"mainText":"weatherTrip.feels"}} /></Region><Region slot="right" variant="compact-title-content-action"><SingleLineTitle title="耳机" /><EmphasisText mainText="64%" secondaryText="剩余电量" dataIds={{"mainText":"budsTrip.battery"}} /><PillButton appearance="card" label="打开音乐" actionId="music.open" /></Region></Card>`,
  "coverage": [{"requirement": "查看天气体感和耳机电量，并打开音乐。"}],
  "unmetRequirements": []
})
```

## 示例 13：步数与快递两个主题

### 输入

```json
{
  "userQuery": "查看今日步数和快递状态，并查看快递详情。",
  "size": "2x4",
  "actions": [
    {
      "id": "parcel.open",
      "description": "查看详情"
    }
  ],
  "data": [
    {
      "id": "stepsToday.steps",
      "type": "string",
      "description": "stepsToday.steps",
      "value": "8400步"
    },
    {
      "id": "parcelNow.status",
      "type": "string",
      "description": "parcelNow.status",
      "value": "派送中"
    }
  ],
  "assetCandidates": []
}
```

### 分析

两个独立主题各占一侧；2 个数据、1 个 Action。Action 只进入所属侧的操作位。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x4" appearance="solid-cyan" layout="split-panels"><Region slot="left" variant="compact-title-content"><SingleLineTitle title="运动" /><EmphasisText mainText="8400步" secondaryText="今日步数" dataIds={{"mainText":"stepsToday.steps"}} /></Region><Region slot="right" variant="compact-title-content-action"><SingleLineTitle title="快递" /><EmphasisText mainText="派送中" secondaryText="物流状态" dataIds={{"mainText":"parcelNow.status"}} /><PillButton appearance="card" label="查看详情" actionId="parcel.open" /></Region></Card>`,
  "coverage": [{"requirement": "查看今日步数和快递状态，并查看快递详情。"}],
  "unmetRequirements": []
})
```

## 示例 14：日程和门锁两个主题，各有操作

### 输入

```json
{
  "userQuery": "查看下一场日程与门锁状态，并分别打开日程和门锁。",
  "size": "2x4",
  "actions": [
    {
      "id": "agenda.open",
      "description": "打开日程"
    },
    {
      "id": "lock.open",
      "description": "打开门锁"
    }
  ],
  "data": [
    {
      "id": "agendaOne.event",
      "type": "string",
      "description": "agendaOne.event",
      "value": "团队复盘"
    },
    {
      "id": "doorLock.state",
      "type": "string",
      "description": "doorLock.state",
      "value": "已锁定"
    }
  ],
  "assetCandidates": []
}
```

### 分析

两个独立主题各占一侧；2 个数据、2 个 Action。Action 只进入所属侧的操作位。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x4" appearance="solid-cyan" layout="split-panels"><Region slot="left" variant="compact-title-content-action"><SingleLineTitle title="日程" /><EmphasisText mainText="团队复盘" secondaryText="下一场" dataIds={{"mainText":"agendaOne.event"}} /><PillButton appearance="card" label="打开日程" actionId="agenda.open" /></Region><Region slot="right" variant="compact-title-content-action"><SingleLineTitle title="门锁" /><EmphasisText mainText="已锁定" secondaryText="门锁状态" dataIds={{"mainText":"doorLock.state"}} /><PillButton appearance="card" label="打开门锁" actionId="lock.open" /></Region></Card>`,
  "coverage": [{"requirement": "查看下一场日程与门锁状态，并分别打开日程和门锁。"}],
  "unmetRequirements": []
})
```

## 示例 15：健康状态与天气提醒

### 输入

```json
{
  "userQuery": "查看今天的心率状态和降雨提醒。",
  "size": "2x4",
  "actions": [],
  "data": [
    {
      "id": "heartDaily.rate",
      "type": "string",
      "description": "heartDaily.rate",
      "value": "72次/分"
    },
    {
      "id": "rainHint.forecast",
      "type": "string",
      "description": "rainHint.forecast",
      "value": "傍晚有雨"
    }
  ],
  "assetCandidates": []
}
```

### 分析

两个独立主题各占一侧；2 个数据、0 个 Action。Action 只进入所属侧的操作位。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x4" appearance="solid-cyan" layout="split-panels"><Region slot="left" variant="compact-title-content"><SingleLineTitle title="健康" /><EmphasisText mainText="72次/分" secondaryText="当前心率" dataIds={{"mainText":"heartDaily.rate"}} /></Region><Region slot="right" variant="compact-title-content"><SingleLineTitle title="天气" /><EmphasisText mainText="傍晚有雨" secondaryText="降雨提醒" dataIds={{"mainText":"rainHint.forecast"}} /></Region></Card>`,
  "coverage": [{"requirement": "查看今天的心率状态和降雨提醒。"}],
  "unmetRequirements": []
})
```

## 示例 16：室内环境主值加两项固定信息

### 输入

```json
{
  "userQuery": "查看室内温度、湿度、净化器滤芯状态和更换时间。",
  "size": "2x4",
  "actions": [],
  "data": [
    {
      "id": "roomClimate.temperature",
      "type": "string",
      "description": "roomClimate.temperature",
      "value": "24℃"
    },
    {
      "id": "roomClimate.filter",
      "type": "string",
      "description": "roomClimate.filter",
      "value": "正常"
    },
    {
      "id": "roomClimate.replace",
      "type": "string",
      "description": "roomClimate.replace",
      "value": "14天后"
    }
  ],
  "assetCandidates": []
}
```

### 分析

3 个数据、0 个 Action；主内容只表达核心，右侧两个真实固定槽填满且不重复绑定。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x4" appearance="solid-green" layout="main-right-double"><Region slot="main" variant="wide-title-content"><SingleLineTitle title="室内环境" /><EmphasisText mainText="24℃" secondaryText="室温" dataIds={{"mainText":"roomClimate.temperature"}} /></Region><Region slot="side-top"><InfoBlock primaryText="正常" secondaryText="滤芯状态" dataIds={{"primaryText":"roomClimate.filter"}} /></Region><Region slot="side-bottom"><InfoBlock primaryText="14天后" secondaryText="预计更换" dataIds={{"primaryText":"roomClimate.replace"}} /></Region></Card>`,
  "coverage": [{"requirement": "查看室内温度、湿度、净化器滤芯状态和更换时间。"}],
  "unmetRequirements": []
})
```

## 示例 17：行程主信息加信息和操作

### 输入

```json
{
  "userQuery": "查看当前行程目的地和交通状态，并打开导航。",
  "size": "2x4",
  "actions": [
    {
      "id": "navigation.open",
      "description": "打开导航"
    }
  ],
  "data": [
    {
      "id": "routeNow.destination",
      "type": "string",
      "description": "routeNow.destination",
      "value": "中心广场"
    },
    {
      "id": "routeNow.traffic",
      "type": "string",
      "description": "routeNow.traffic",
      "value": "通畅"
    }
  ],
  "assetCandidates": []
}
```

### 分析

2 个数据、1 个 Action；主内容只表达核心，右侧两个真实固定槽填满且不重复绑定。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x4" appearance="solid-green" layout="main-right-double"><Region slot="main" variant="wide-title-content"><SingleLineTitle title="当前行程" /><EmphasisText mainText="中心广场" secondaryText="目的地" dataIds={{"mainText":"routeNow.destination"}} /></Region><Region slot="side-top"><InfoBlock primaryText="通畅" secondaryText="路况" dataIds={{"primaryText":"routeNow.traffic"}} /></Region><Region slot="side-bottom"><CardButton text="打开导航" actionId="navigation.open" /></Region></Card>`,
  "coverage": [{"requirement": "查看当前行程目的地和交通状态，并打开导航。"}],
  "unmetRequirements": []
})
```

## 示例 18：读书进度加两个操作

### 输入

```json
{
  "userQuery": "查看阅读进度，并打开图书和阅读设置。",
  "size": "2x4",
  "actions": [
    {
      "id": "book.open",
      "description": "打开图书"
    },
    {
      "id": "reader.settings",
      "description": "阅读设置"
    }
  ],
  "data": [
    {
      "id": "readingBook.progress",
      "type": "string",
      "description": "readingBook.progress",
      "value": "68%"
    }
  ],
  "assetCandidates": []
}
```

### 分析

1 个数据、2 个 Action；主内容只表达核心，右侧两个真实固定槽填满且不重复绑定。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x4" appearance="solid-green" layout="main-right-double"><Region slot="main" variant="wide-title-content"><SingleLineTitle title="阅读进度" /><EmphasisText mainText="68%" secondaryText="已阅读" dataIds={{"mainText":"readingBook.progress"}} /></Region><Region slot="side-top"><CardButton text="打开图书" actionId="book.open" /></Region><Region slot="side-bottom"><CardButton text="阅读设置" actionId="reader.settings" /></Region></Card>`,
  "coverage": [{"requirement": "查看阅读进度，并打开图书和阅读设置。"}],
  "unmetRequirements": []
})
```

## 示例 19：会议主信息加会场和联系操作

### 输入

```json
{
  "userQuery": "查看会议主题、会场和门禁状态，并联系组织者。",
  "size": "2x4",
  "actions": [
    {
      "id": "host.contact",
      "description": "联系组织者"
    }
  ],
  "data": [
    {
      "id": "meetingRoom.topic",
      "type": "string",
      "description": "meetingRoom.topic",
      "value": "产品评审"
    },
    {
      "id": "meetingRoom.access",
      "type": "string",
      "description": "meetingRoom.access",
      "value": "已开放"
    }
  ],
  "assetCandidates": []
}
```

### 分析

2 个数据、1 个 Action；主内容只表达核心，右侧两个真实固定槽填满且不重复绑定。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x4" appearance="solid-green" layout="main-right-double"><Region slot="main" variant="wide-title-content"><SingleLineTitle title="会议" /><EmphasisText mainText="产品评审" secondaryText="会议主题" dataIds={{"mainText":"meetingRoom.topic"}} /></Region><Region slot="side-top"><InfoBlock primaryText="已开放" secondaryText="门禁状态" dataIds={{"primaryText":"meetingRoom.access"}} /></Region><Region slot="side-bottom"><CardButton text="联系组织者" actionId="host.contact" /></Region></Card>`,
  "coverage": [{"requirement": "查看会议主题、会场和门禁状态，并联系组织者。"}],
  "unmetRequirements": []
})
```

## 示例 20：家用电器主状态加两项说明

### 输入

```json
{
  "userQuery": "查看洗衣机剩余时间、当前阶段、预约状态和门锁状态。",
  "size": "2x4",
  "actions": [],
  "data": [
    {
      "id": "washerNow.remaining",
      "type": "string",
      "description": "washerNow.remaining",
      "value": "18分钟"
    },
    {
      "id": "washerNow.stage",
      "type": "string",
      "description": "washerNow.stage",
      "value": "漂洗"
    },
    {
      "id": "washerNow.door",
      "type": "string",
      "description": "washerNow.door",
      "value": "已锁定"
    }
  ],
  "assetCandidates": []
}
```

### 分析

3 个数据、0 个 Action；主内容只表达核心，右侧两个真实固定槽填满且不重复绑定。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x4" appearance="solid-green" layout="main-right-double"><Region slot="main" variant="wide-title-content"><SingleLineTitle title="洗衣机" /><EmphasisText mainText="18分钟" secondaryText="剩余时间" dataIds={{"mainText":"washerNow.remaining"}} /></Region><Region slot="side-top"><InfoBlock primaryText="漂洗" secondaryText="当前阶段" dataIds={{"primaryText":"washerNow.stage"}} /></Region><Region slot="side-bottom"><InfoBlock primaryText="已锁定" secondaryText="门锁状态" dataIds={{"primaryText":"washerNow.door"}} /></Region></Card>`,
  "coverage": [{"requirement": "查看洗衣机剩余时间、当前阶段、预约状态和门锁状态。"}],
  "unmetRequirements": []
})
```

## 示例 21：四个独立设备状态

### 输入

```json
{
  "userQuery": "查看四台设备各自状态。",
  "size": "2x4",
  "actions": [],
  "data": [
    {
      "id": "quick.heater",
      "type": "string",
      "description": "quick.heater",
      "value": "运行中"
    },
    {
      "id": "quick.fan",
      "type": "string",
      "description": "quick.fan",
      "value": "自动"
    },
    {
      "id": "quick.lamp",
      "type": "string",
      "description": "quick.lamp",
      "value": "开启"
    },
    {
      "id": "quick.purifier",
      "type": "string",
      "description": "quick.purifier",
      "value": "待机"
    }
  ],
  "assetCandidates": []
}
```

### 分析

四个彼此独立的真实模块；4 个数据、0 个 Action，各占一槽，不虚构填充项。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x4" appearance="solid-purple" layout="four-blocks"><Region slot="top-left"><InfoBlock primaryText="运行中" secondaryText="暖气" dataIds={{"primaryText":"quick.heater"}} /></Region><Region slot="top-right"><InfoBlock primaryText="自动" secondaryText="新风" dataIds={{"primaryText":"quick.fan"}} /></Region><Region slot="bottom-left"><InfoBlock primaryText="开启" secondaryText="照明" dataIds={{"primaryText":"quick.lamp"}} /></Region><Region slot="bottom-right"><InfoBlock primaryText="待机" secondaryText="净化" dataIds={{"primaryText":"quick.purifier"}} /></Region></Card>`,
  "coverage": [{"requirement": "查看四台设备各自状态。"}],
  "unmetRequirements": []
})
```

## 示例 22：四个独立设备状态

### 输入

```json
{"userQuery":"查看厨房四台设备各自状态。","size":"2x4","actions":[],"data":[{"id":"kitchen.oven","type":"string","value":"预热中"},{"id":"kitchen.fridge","type":"string","value":"正常"},{"id":"kitchen.hood","type":"string","value":"关闭"},{"id":"kitchen.stove","type":"string","value":"待机"}],"assetCandidates":[]}
```

### 分析

四个真实的同级状态，每个 InfoBlock 只承载一个动态值；无操作，不虚构按钮。

### 提交

```js
submit_card_jsx({"jsx": `<Card size="2x4" appearance="solid-purple" layout="four-blocks"><Region slot="top-left"><InfoBlock primaryText="预热中" secondaryText="烤箱" dataIds={{primaryText:"kitchen.oven"}} /></Region><Region slot="top-right"><InfoBlock primaryText="正常" secondaryText="冰箱" dataIds={{primaryText:"kitchen.fridge"}} /></Region><Region slot="bottom-left"><InfoBlock primaryText="关闭" secondaryText="油烟机" dataIds={{primaryText:"kitchen.hood"}} /></Region><Region slot="bottom-right"><InfoBlock primaryText="待机" secondaryText="灶具" dataIds={{primaryText:"kitchen.stove"}} /></Region></Card>`,"coverage":[{"requirement":"展示四台设备状态"}],"unmetRequirements":[]})
```

## 示例 23：两个独立状态和两个操作

### 输入

```json
{
  "userQuery": "查看书房灯与空调状态，并能操作窗帘和新风。",
  "size": "2x4",
  "actions": [
    {
      "id": "curtain.open",
      "description": "打开窗帘"
    },
    {
      "id": "airflow.open",
      "description": "开启新风"
    }
  ],
  "data": [
    {
      "id": "quick.studyLamp",
      "type": "string",
      "description": "quick.studyLamp",
      "value": "已开启"
    },
    {
      "id": "quick.studyAC",
      "type": "string",
      "description": "quick.studyAC",
      "value": "26℃"
    }
  ],
  "assetCandidates": []
}
```

### 分析

四个彼此独立的真实模块；2 个数据、2 个 Action，各占一槽，不虚构填充项。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x4" appearance="solid-purple" layout="four-blocks"><Region slot="top-left"><InfoBlock primaryText="已开启" secondaryText="书房灯" dataIds={{"primaryText":"quick.studyLamp"}} /></Region><Region slot="top-right"><CardButton text="打开窗帘" actionId="curtain.open" /></Region><Region slot="bottom-left"><InfoBlock primaryText="26℃" secondaryText="空调" dataIds={{"primaryText":"quick.studyAC"}} /></Region><Region slot="bottom-right"><CardButton text="开启新风" actionId="airflow.open" /></Region></Card>`,
  "coverage": [{"requirement": "查看书房灯与空调状态，并能操作窗帘和新风。"}],
  "unmetRequirements": []
})
```

## 示例 24：四项独立电量与状态

### 输入

```json
{"userQuery":"查看车钥匙、耳机、手表和相机的电量与连接状态。","size":"2x4","actions":[],"data":[{"id":"devices.key.battery","type":"string","value":"81%"},{"id":"devices.key.state","type":"string","value":"已连接"},{"id":"devices.buds.battery","type":"string","value":"63%"},{"id":"devices.buds.state","type":"string","value":"已连接"},{"id":"devices.watch.battery","type":"string","value":"54%"},{"id":"devices.watch.state","type":"string","value":"已连接"},{"id":"devices.camera.battery","type":"string","value":"72%"},{"id":"devices.camera.state","type":"string","value":"未连接"}],"assetCandidates":[]}
```

### 分析

8 个数据、0 个 Action。四个对象各占一个固定信息槽；每槽主、次文本各绑定一个同对象字段，不把别的对象塞进同一 InfoBlock。四个电量都是百分比，主文本用模板保留对象名，避免只看到四个无法区分归属的数值。

### 提交

```js
submit_card_jsx({"jsx": `<Card size="2x4" appearance="solid-blue" layout="four-blocks"><Region slot="top-left"><InfoBlock primaryText="车钥匙 81%" primaryTextTemplate="车钥匙 {value}" secondaryText="已连接" dataIds={{primaryText:"devices.key.battery",secondaryText:"devices.key.state"}} /></Region><Region slot="top-right"><InfoBlock primaryText="耳机 63%" primaryTextTemplate="耳机 {value}" secondaryText="已连接" dataIds={{primaryText:"devices.buds.battery",secondaryText:"devices.buds.state"}} /></Region><Region slot="bottom-left"><InfoBlock primaryText="手表 54%" primaryTextTemplate="手表 {value}" secondaryText="已连接" dataIds={{primaryText:"devices.watch.battery",secondaryText:"devices.watch.state"}} /></Region><Region slot="bottom-right"><InfoBlock primaryText="相机 72%" primaryTextTemplate="相机 {value}" secondaryText="未连接" dataIds={{primaryText:"devices.camera.battery",secondaryText:"devices.camera.state"}} /></Region></Card>`,"coverage":[{"requirement":"展示四组设备电量和连接状态"}],"unmetRequirements":[]})
```
