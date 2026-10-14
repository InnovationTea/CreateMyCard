---
name: phone-widget-fewshot-library-2x2
description: 按必要数据、Action 与组件容量检索的 2×2 合成示例；不整体加载。
---

# 2×2 容量示例库

各例独立检索，不复制示范 ID 或业务值。

## 示例 07：书房温度

### 输入

```json
{
  "userQuery": "查看书房当前温度。",
  "size": "2x2",
  "actions": [],
  "data": [
    {
      "id": "roomStudy.temperature",
      "type": "string",
      "description": "roomStudy.temperature",
      "value": "23℃"
    }
  ],
  "assetCandidates": []
}
```

### 分析

一个短业务值；标题 + 一个有主次关系的显示组件即可，不占操作槽。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x2" appearance="orb-blue" layout="single"><Region slot="main" variant="wide-title-content"><SingleLineTitle title="书房温度" /><EmphasisText mainText="23℃" secondaryText="当前温度" dataIds={{mainText:"roomStudy.temperature"}} /></Region></Card>`,
  "coverage": [{"requirement": "查看书房当前温度。"}],
  "unmetRequirements": []
})
```

## 示例 08：今天步数

### 输入

```json
{
  "userQuery": "查看今天的步数。",
  "size": "2x2",
  "actions": [],
  "data": [
    {
      "id": "dailyMotion.steps",
      "type": "string",
      "description": "dailyMotion.steps",
      "value": "7200步"
    }
  ],
  "assetCandidates": []
}
```

### 分析

一个短业务值；标题 + 一个有主次关系的显示组件即可，不占操作槽。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x2" appearance="orb-blue" layout="single"><Region slot="main" variant="wide-title-content"><SingleLineTitle title="今天步数" /><EmphasisText mainText="7200步" secondaryText="今日步数" dataIds={{mainText:"dailyMotion.steps"}} /></Region></Card>`,
  "coverage": [{"requirement": "查看今天的步数。"}],
  "unmetRequirements": []
})
```

## 示例 09：门锁状态

### 输入

```json
{
  "userQuery": "查看家门锁状态。",
  "size": "2x2",
  "actions": [],
  "data": [
    {
      "id": "homeDoor.state",
      "type": "string",
      "description": "homeDoor.state",
      "value": "已锁定"
    }
  ],
  "assetCandidates": []
}
```

### 分析

一个短业务值；标题 + 一个有主次关系的显示组件即可，不占操作槽。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x2" appearance="orb-blue" layout="single"><Region slot="main" variant="wide-title-content"><SingleLineTitle title="门锁状态" /><EmphasisText mainText="已锁定" secondaryText="门锁" dataIds={{mainText:"homeDoor.state"}} /></Region></Card>`,
  "coverage": [{"requirement": "查看家门锁状态。"}],
  "unmetRequirements": []
})
```

## 示例 10：航班状态

### 输入

```json
{
  "userQuery": "查看当前航班状态。",
  "size": "2x2",
  "actions": [],
  "data": [
    {
      "id": "flightNow.state",
      "type": "string",
      "description": "flightNow.state",
      "value": "登机中"
    }
  ],
  "assetCandidates": []
}
```

### 分析

一个短业务值；标题 + 一个有主次关系的显示组件即可，不占操作槽。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x2" appearance="orb-blue" layout="single"><Region slot="main" variant="wide-title-content"><SingleLineTitle title="航班状态" /><EmphasisText mainText="登机中" secondaryText="航班" dataIds={{mainText:"flightNow.state"}} /></Region></Card>`,
  "coverage": [{"requirement": "查看当前航班状态。"}],
  "unmetRequirements": []
})
```

## 示例 11：台灯与操作

### 输入

```json
{
  "userQuery": "查看台灯状态并打开控制。",
  "size": "2x2",
  "actions": [
    {
      "id": "lamp.control",
      "description": "控制台灯"
    }
  ],
  "data": [
    {
      "id": "deskLamp.state",
      "type": "string",
      "description": "deskLamp.state",
      "value": "已开启"
    }
  ],
  "assetCandidates": []
}
```

### 分析

一项数据 + 一个必要 Action；为按钮预留专属操作槽，避免把显示组件压入按钮区域。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x2" appearance="solid-green" layout="single"><Region slot="main" variant="wide-title-content-action"><SingleLineTitle title="台灯与操作" /><EmphasisText mainText="已开启" secondaryText="灯光状态" dataIds={{mainText:"deskLamp.state"}} /><PillButton appearance="card" label="控制台灯" actionId="lamp.control" /></Region></Card>`,
  "coverage": [{"requirement": "查看台灯状态并打开控制。"}],
  "unmetRequirements": []
})
```

## 示例 12：洗衣机与操作

### 输入

```json
{
  "userQuery": "查看洗衣进度并打开洗衣机。",
  "size": "2x2",
  "actions": [
    {
      "id": "washer.open",
      "description": "打开设备"
    }
  ],
  "data": [
    {
      "id": "washerWork.phase",
      "type": "string",
      "description": "washerWork.phase",
      "value": "漂洗中"
    }
  ],
  "assetCandidates": []
}
```

### 分析

一项数据 + 一个必要 Action；为按钮预留专属操作槽，避免把显示组件压入按钮区域。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x2" appearance="solid-green" layout="single"><Region slot="main" variant="wide-title-content-action"><SingleLineTitle title="洗衣机与操作" /><EmphasisText mainText="漂洗中" secondaryText="当前阶段" dataIds={{mainText:"washerWork.phase"}} /><PillButton appearance="card" label="打开设备" actionId="washer.open" /></Region></Card>`,
  "coverage": [{"requirement": "查看洗衣进度并打开洗衣机。"}],
  "unmetRequirements": []
})
```

## 示例 13：空气与操作

### 输入

```json
{
  "userQuery": "查看空气质量并打开净化器。",
  "size": "2x2",
  "actions": [
    {
      "id": "purifier.open",
      "description": "打开净化器"
    }
  ],
  "data": [
    {
      "id": "airRoom.quality",
      "type": "string",
      "description": "airRoom.quality",
      "value": "良好"
    }
  ],
  "assetCandidates": []
}
```

### 分析

一项数据 + 一个必要 Action；为按钮预留专属操作槽，避免把显示组件压入按钮区域。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x2" appearance="solid-green" layout="single"><Region slot="main" variant="wide-title-content-action"><SingleLineTitle title="空气与操作" /><EmphasisText mainText="良好" secondaryText="空气质量" dataIds={{mainText:"airRoom.quality"}} /><PillButton appearance="card" label="打开净化器" actionId="purifier.open" /></Region></Card>`,
  "coverage": [{"requirement": "查看空气质量并打开净化器。"}],
  "unmetRequirements": []
})
```

## 示例 14：车辆与操作

### 输入

```json
{
  "userQuery": "查看车辆剩余里程并打开车辆详情。",
  "size": "2x2",
  "actions": [
    {
      "id": "car.details",
      "description": "车辆详情"
    }
  ],
  "data": [
    {
      "id": "carRange.remaining",
      "type": "string",
      "description": "carRange.remaining",
      "value": "186公里"
    }
  ],
  "assetCandidates": []
}
```

### 分析

一项数据 + 一个必要 Action；为按钮预留专属操作槽，避免把显示组件压入按钮区域。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x2" appearance="solid-green" layout="single"><Region slot="main" variant="wide-title-content-action"><SingleLineTitle title="车辆与操作" /><EmphasisText mainText="186公里" secondaryText="续航里程" dataIds={{mainText:"carRange.remaining"}} /><PillButton appearance="card" label="车辆详情" actionId="car.details" /></Region></Card>`,
  "coverage": [{"requirement": "查看车辆剩余里程并打开车辆详情。"}],
  "unmetRequirements": []
})
```

## 示例 15：专注任务双操作

### 输入

```json
{
  "userQuery": "查看专注状态并可暂停或结束。",
  "size": "2x2",
  "actions": [
    {
      "id": "focus.pause",
      "description": "暂停"
    },
    {
      "id": "focus.stop",
      "description": "结束"
    }
  ],
  "data": [
    {
      "id": "focusNow.state",
      "type": "string",
      "description": "focusNow.state",
      "value": "进行中"
    }
  ],
  "assetCandidates": []
}
```

### 分析

两个必要 Action 占据大部分高度，只使用一个短紧凑内容；无标题变体保留两枚按钮。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x2" appearance="solid-blue" layout="single"><Region slot="main" variant="wide-content-two-actions"><EmphasisText mainText="进行中" dataIds={{mainText:"focusNow.state"}} /><PillButton appearance="card" label="暂停" actionId="focus.pause" /><PillButton appearance="card" label="结束" actionId="focus.stop" /></Region></Card>`,
  "coverage": [{"requirement": "查看专注状态并可暂停或结束。"}],
  "unmetRequirements": []
})
```

## 示例 16：播放器双操作

### 输入

```json
{
  "userQuery": "查看播放状态并可切歌或暂停。",
  "size": "2x2",
  "actions": [
    {
      "id": "music.next",
      "description": "下一首"
    },
    {
      "id": "music.pause",
      "description": "暂停"
    }
  ],
  "data": [
    {
      "id": "musicNow.state",
      "type": "string",
      "description": "musicNow.state",
      "value": "播放中"
    }
  ],
  "assetCandidates": []
}
```

### 分析

两个必要 Action 占据大部分高度，只使用一个短紧凑内容；无标题变体保留两枚按钮。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x2" appearance="solid-blue" layout="single"><Region slot="main" variant="wide-content-two-actions"><EmphasisText mainText="播放中" dataIds={{mainText:"musicNow.state"}} /><PillButton appearance="card" label="下一首" actionId="music.next" /><PillButton appearance="card" label="暂停" actionId="music.pause" /></Region></Card>`,
  "coverage": [{"requirement": "查看播放状态并可切歌或暂停。"}],
  "unmetRequirements": []
})
```

## 示例 17：两个房间温度

### 输入

```json
{
  "userQuery": "查看客厅和书房的温度。",
  "size": "2x2",
  "actions": [],
  "data": [
    {
      "id": "pair.living",
      "type": "string",
      "description": "pair.living",
      "value": "22℃"
    },
    {
      "id": "pair.study",
      "type": "string",
      "description": "pair.study",
      "value": "24℃"
    }
  ],
  "assetCandidates": []
}
```

### 分析

两个可独立阅读的主辅信息各占一个固定 InfoBlock；不加标题或额外组件。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x2" appearance="orb-purple" layout="double-blocks"><Region slot="top"><InfoBlock primaryText="22℃" secondaryText="客厅" dataIds={{primaryText:"pair.living"}} /></Region><Region slot="bottom"><InfoBlock primaryText="24℃" secondaryText="书房" dataIds={{primaryText:"pair.study"}} /></Region></Card>`,
  "coverage": [{"requirement": "查看客厅和书房的温度。"}],
  "unmetRequirements": []
})
```

## 示例 18：两个设备状态

### 输入

```json
{
  "userQuery": "查看净化器与加湿器状态。",
  "size": "2x2",
  "actions": [],
  "data": [
    {
      "id": "pair.purifier",
      "type": "string",
      "description": "pair.purifier",
      "value": "运行中"
    },
    {
      "id": "pair.humidifier",
      "type": "string",
      "description": "pair.humidifier",
      "value": "待机"
    }
  ],
  "assetCandidates": []
}
```

### 分析

两个可独立阅读的主辅信息各占一个固定 InfoBlock；不加标题或额外组件。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x2" appearance="orb-purple" layout="double-blocks"><Region slot="top"><InfoBlock primaryText="运行中" secondaryText="净化器" dataIds={{primaryText:"pair.purifier"}} /></Region><Region slot="bottom"><InfoBlock primaryText="待机" secondaryText="加湿器" dataIds={{primaryText:"pair.humidifier"}} /></Region></Card>`,
  "coverage": [{"requirement": "查看净化器与加湿器状态。"}],
  "unmetRequirements": []
})
```

## 示例 19：两个独立健康指标

### 输入

```json
{
  "userQuery": "查看昨晚睡眠时长和今晨静息心率。",
  "size": "2x2",
  "actions": [],
  "data": [
    {
      "id": "pair.sleep",
      "type": "string",
      "description": "pair.sleep",
      "value": "7小时"
    },
    {
      "id": "pair.heart",
      "type": "string",
      "description": "pair.heart",
      "value": "62次/分"
    }
  ],
  "assetCandidates": []
}
```

### 分析

两个可独立阅读的主辅信息各占一个固定 InfoBlock；不加标题或额外组件。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x2" appearance="orb-purple" layout="double-blocks"><Region slot="top"><InfoBlock primaryText="7小时" secondaryText="睡眠" dataIds={{primaryText:"pair.sleep"}} /></Region><Region slot="bottom"><InfoBlock primaryText="62次/分" secondaryText="静息心率" dataIds={{primaryText:"pair.heart"}} /></Region></Card>`,
  "coverage": [{"requirement": "查看昨晚睡眠时长和今晨静息心率。"}],
  "unmetRequirements": []
})
```

## 示例 20：两个预约状态

### 输入

```json
{
  "userQuery": "查看理发和体检两项预约的状态。",
  "size": "2x2",
  "actions": [],
  "data": [
    {
      "id": "pair.hair",
      "type": "string",
      "description": "pair.hair",
      "value": "已确认"
    },
    {
      "id": "pair.checkup",
      "type": "string",
      "description": "pair.checkup",
      "value": "待确认"
    }
  ],
  "assetCandidates": []
}
```

### 分析

两个可独立阅读的主辅信息各占一个固定 InfoBlock；不加标题或额外组件。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x2" appearance="orb-purple" layout="double-blocks"><Region slot="top"><InfoBlock primaryText="已确认" secondaryText="理发" dataIds={{primaryText:"pair.hair"}} /></Region><Region slot="bottom"><InfoBlock primaryText="待确认" secondaryText="体检" dataIds={{primaryText:"pair.checkup"}} /></Region></Card>`,
  "coverage": [{"requirement": "查看理发和体检两项预约的状态。"}],
  "unmetRequirements": []
})
```

## 示例 21：预约事件一

### 输入

```json
{
  "userQuery": "查看设备检修的时间和地点。",
  "size": "2x2",
  "actions": [],
  "data": [
    {
      "id": "serviceTask.title",
      "type": "string",
      "description": "serviceTask.title",
      "value": "设备检修"
    },
    {
      "id": "serviceTask.time",
      "type": "string",
      "description": "serviceTask.time",
      "value": "14:00"
    },
    {
      "id": "serviceTask.location",
      "type": "string",
      "description": "serviceTask.location",
      "value": "维修区"
    }
  ],
  "assetCandidates": []
}
```

### 分析

三项字段是同一事件，不拆成三个文本；由一个 EventCard 在单内容位保留事件层级。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x2" appearance="orb-orange" layout="single"><Region slot="main" variant="wide-title-content"><SingleLineTitle title="预约事件一" /><EventCard items={[{"title":"设备检修","time":"14:00","location":"维修区","dataIds":{"title":"serviceTask.title","time":"serviceTask.time","location":"serviceTask.location"}}]} /></Region></Card>`,
  "coverage": [{"requirement": "查看设备检修的时间和地点。"}],
  "unmetRequirements": []
})
```

## 示例 22：预约事件二

### 输入

```json
{
  "userQuery": "查看体检预约的时间和地点。",
  "size": "2x2",
  "actions": [],
  "data": [
    {
      "id": "checkupTask.title",
      "type": "string",
      "description": "checkupTask.title",
      "value": "健康体检"
    },
    {
      "id": "checkupTask.time",
      "type": "string",
      "description": "checkupTask.time",
      "value": "08:30"
    },
    {
      "id": "checkupTask.location",
      "type": "string",
      "description": "checkupTask.location",
      "value": "门诊楼"
    }
  ],
  "assetCandidates": []
}
```

### 分析

三项字段是同一事件，不拆成三个文本；由一个 EventCard 在单内容位保留事件层级。

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x2" appearance="orb-orange" layout="single"><Region slot="main" variant="wide-title-content"><SingleLineTitle title="预约事件二" /><EventCard items={[{"title":"健康体检","time":"08:30","location":"门诊楼","dataIds":{"title":"checkupTask.title","time":"checkupTask.time","location":"checkupTask.location"}}]} /></Region></Card>`,
  "coverage": [{"requirement": "查看体检预约的时间和地点。"}],
  "unmetRequirements": []
})
```
