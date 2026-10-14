---
name: phone-widget-fewshots-2x2
description: 用六个虚构输入展示 2×2 从简短信息分析、Info Plan 到当前语义 JSX 的端到端选择。
---

# 2×2 端到端示例

实体、ID、数值和文案均为虚构；实际任务只使用当前输入。分析只示范信息关系、组件取舍和容量判断，不作为额外输出。`componentHints` 是软候选，不冻结布局或组件。

## 示例一：完整事件优先保留事件结构

### 输入

```json
{
  "userQuery": "展示社区夜跑的活动名称、开始和结束时间，以及集合地点。",
  "size": "2x2",
  "actions": [],
  "data": [
    { "id": "community.run.name", "type": "string", "description": "活动名称。", "value": "社区夜跑" },
    { "id": "community.run.start", "type": "string", "description": "开始时间。", "value": "19:00" },
    { "id": "community.run.end", "type": "string", "description": "结束时间。", "value": "20:30" },
    { "id": "community.run.place", "type": "string", "description": "集合地点。", "value": "南门广场" }
  ],
  "assetCandidates": []
}
```

### 分析

四个字段共同描述同一活动；名称、时间范围、地点不拆成零散文本。一个 `EventCard` 保留事件层级；没有 Action，使用标题加单内容的 `wide-title-content`。夜跑属于运动场景，选用 `orb-orange`。

### 计划

```js
submit_card_plan({
  "info_required": [
    { "requirement": "活动名称", "dataId": "community.run.name", "componentHints": ["EventCard"] },
    { "requirement": "活动开始时间", "dataId": "community.run.start", "componentHints": ["EventCard"] },
    { "requirement": "活动结束时间", "dataId": "community.run.end", "componentHints": ["EventCard"] },
    { "requirement": "集合地点", "dataId": "community.run.place", "componentHints": ["EventCard"] }
  ]
})
```

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x2" appearance="orb-orange" layout="single">
  <Region slot="main" variant="wide-title-content">
    <SingleLineTitle title="活动安排" />
    <EventCard items={[{"title":"社区夜跑","time":"19:00 – 20:30","location":"南门广场","dataIds":{"title":"community.run.name","time":["community.run.start","community.run.end"],"location":"community.run.place"}}]} />
  </Region>
</Card>`,
  "coverage": [{ "requirement": "展示活动名称、时间范围和集合地点" }],
  "unmetRequirements": []
})
```

## 示例二：单一占比与必须保留的操作

### 输入

```json
{
  "userQuery": "看儿童手表还剩多少电、是否正在充电，并打开设备设置。",
  "size": "2x2",
  "actions": [{ "id": "wearable.settings.open", "description": "打开设备设置" }],
  "data": [
    { "id": "wearable.watch.batteryPercent", "type": "integer", "description": "儿童手表剩余电量百分比。", "value": 73 },
    { "id": "wearable.watch.chargeStatus", "type": "string", "description": "儿童手表充电状态。", "value": "未充电" }
  ],
  "assetCandidates": [{ "src": "kidswatch_fill.svg", "description": "儿童手表" }]
}
```

### 分析

电量是真实百分比，充电状态属于同一设备，可由一个 `ProgressCircleSingle` 表达；不再重复放第二个电量文本。单个 Action 使用合法的底部按钮槽。

### 计划

```js
submit_card_plan({
  "info_required": [
    { "requirement": "儿童手表剩余电量", "dataId": "wearable.watch.batteryPercent", "componentHints": ["ProgressCircleSingle"] },
    { "requirement": "儿童手表充电状态", "dataId": "wearable.watch.chargeStatus", "componentHints": ["ProgressCircleSingle"] },
    { "requirement": "打开设备设置", "actionId": "wearable.settings.open", "componentHints": ["PillButton"] }
  ]
})
```

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x2" appearance="solid-green" layout="single">
  <Region slot="main" variant="wide-title-content-action">
    <SingleLineTitle title="儿童手表" />
    <ProgressCircleSingle value={73} icon="kidswatch_fill.svg" label="剩余电量" secondaryLabel="未充电" ariaLabel="儿童手表剩余电量73%，未充电" appearance="card" dataIds={{"value":"wearable.watch.batteryPercent","secondaryLabel":"wearable.watch.chargeStatus"}} />
    <PillButton label="设备设置" appearance="card" actionId="wearable.settings.open" />
  </Region>
</Card>`,
  "coverage": [{ "requirement": "展示手表电量与充电状态并提供设备设置操作" }],
  "unmetRequirements": []
})
```

## 示例三：图标可独立表达的右下操作

### 输入

```json
{
  "userQuery": "显示正在播放的曲目、所属歌单和剩余时间，提供暂停播放操作。",
  "size": "2x2",
  "actions": [{ "id": "music.player.pause", "description": "暂停播放" }],
  "data": [
    { "id": "music.current.track", "type": "string", "description": "当前曲目。", "value": "夜航" },
    { "id": "music.current.playlist", "type": "string", "description": "曲目所属歌单。", "value": "专注歌单" },
    { "id": "music.current.remainingText", "type": "string", "description": "带说明的剩余时间。", "value": "剩余02:40" }
  ],
  "assetCandidates": [{ "src": "pause_fill.svg", "description": "暂停播放" }]
}
```

### 分析

曲目是主信息，歌单是其属性；剩余时间独立放在下方。暂停图标语义明确，使用右下 `CircleButton`。三个字段各绑定一次，不把辅助字段挤入一个无标签的主文本。

### 计划

```js
submit_card_plan({
  "info_required": [
    { "requirement": "当前曲目", "dataId": "music.current.track", "componentHints": ["EmphasisText"] },
    { "requirement": "所属歌单", "dataId": "music.current.playlist", "componentHints": ["EmphasisText"] },
    { "requirement": "剩余时间", "dataId": "music.current.remainingText", "componentHints": ["SecondaryBody"] },
    { "requirement": "暂停播放", "actionId": "music.player.pause", "componentHints": ["CircleButton"] }
  ]
})
```

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x2" appearance="solid-purple" layout="single">
  <Region slot="main" variant="wide-title-anchor-action">
    <SingleLineTitle title="播放中" />
    <EmphasisText mainText="夜航" secondaryText="专注歌单" dataIds={{"mainText":"music.current.track","secondaryText":"music.current.playlist"}} />
    <SecondaryBody items={[{"value":"剩余02:40","dataIds":{"value":"music.current.remainingText"}}]} />
    <CircleButton icon="pause_fill.svg" ariaLabel="暂停播放" appearance="card" actionId="music.player.pause" />
  </Region>
</Card>`,
  "coverage": [{ "requirement": "展示曲目、歌单和剩余时间并提供暂停操作" }],
  "unmetRequirements": []
})
```

## 示例四：两个对象各占一个完整信息块

### 输入

```json
{
  "userQuery": "同时看台灯的工作模式与亮度、空气净化器的运行和空气状态。",
  "size": "2x2",
  "actions": [],
  "data": [
    { "id": "home.lamp.mode", "type": "string", "description": "台灯模式。", "value": "阅读模式" },
    { "id": "home.lamp.brightnessText", "type": "string", "description": "台灯亮度。", "value": "亮度70%" },
    { "id": "home.purifier.runningText", "type": "string", "description": "净化器运行状态。", "value": "运行中" },
    { "id": "home.purifier.airText", "type": "string", "description": "净化器空气状态。", "value": "空气优" }
  ],
  "assetCandidates": []
}
```

### 分析

台灯和净化器各有一组主辅状态，适合上下两个固定 `InfoBlock`。没有 Action。对象名用单字段 Template 标明，不错误绑定成额外数据。智能家居属于系统场景，选用 `orb-blue`。

### 计划

```js
submit_card_plan({
  "info_required": [
    { "requirement": "台灯模式", "dataId": "home.lamp.mode", "componentHints": ["InfoBlock"] },
    { "requirement": "台灯亮度", "dataId": "home.lamp.brightnessText", "componentHints": ["InfoBlock"] },
    { "requirement": "净化器运行状态", "dataId": "home.purifier.runningText", "componentHints": ["InfoBlock"] },
    { "requirement": "净化器空气状态", "dataId": "home.purifier.airText", "componentHints": ["InfoBlock"] }
  ]
})
```

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x2" appearance="orb-blue" layout="double-blocks">
  <Region slot="top">
    <InfoBlock primaryText="阅读模式" primaryTextTemplate="台灯 {value}" secondaryText="亮度70%" dataIds={{"primaryText":"home.lamp.mode","secondaryText":"home.lamp.brightnessText"}} />
  </Region>
  <Region slot="bottom">
    <InfoBlock primaryText="运行中" primaryTextTemplate="净化器 {value}" secondaryText="空气优" dataIds={{"primaryText":"home.purifier.runningText","secondaryText":"home.purifier.airText"}} />
  </Region>
</Card>`,
  "coverage": [{ "requirement": "展示台灯与净化器各自的主辅状态" }],
  "unmetRequirements": []
})
```

## 示例五：两个同级占比与一个操作

### 输入

```json
{
  "userQuery": "一起看手机与儿童手表的电量百分比，并进入电量设置。",
  "size": "2x2",
  "actions": [{ "id": "device.power.settings", "description": "进入电量设置" }],
  "data": [
    { "id": "device.phone.batteryText", "type": "string", "description": "手机电量百分比。", "value": "64%" },
    { "id": "device.watch.batteryText", "type": "string", "description": "儿童手表电量百分比。", "value": "47%" }
  ],
  "assetCandidates": [
    { "src": "phone_fill.svg", "description": "手机" },
    { "src": "kidswatch_fill.svg", "description": "儿童手表" }
  ]
}
```

### 分析

两个值的尺度和层级相同，使用专用双环而非一主一次文本，也不拆成两个 `ProgressCircleSingle`。底部 Action 有独立槽位，两个图环均用 `sm` 规格。

### 计划

```js
submit_card_plan({
  "info_required": [
    { "requirement": "手机电量", "dataId": "device.phone.batteryText", "componentHints": ["ProgressCircle"] },
    { "requirement": "儿童手表电量", "dataId": "device.watch.batteryText", "componentHints": ["ProgressCircle"] },
    { "requirement": "进入电量设置", "actionId": "device.power.settings", "componentHints": ["PillButton"] }
  ]
})
```

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x2" appearance="solid-green" layout="single">
  <Region slot="main" variant="wide-two-column-action">
    <SingleLineTitle title="设备电量" />
    <ProgressCircle icon="phone_fill.svg" externalText="64%" size="sm" appearance="card" ariaLabel="手机电量64%" dataIds={{"externalText":"device.phone.batteryText"}} />
    <ProgressCircle icon="kidswatch_fill.svg" externalText="47%" size="sm" appearance="card" ariaLabel="儿童手表电量47%" dataIds={{"externalText":"device.watch.batteryText"}} />
    <PillButton label="电量设置" appearance="card" actionId="device.power.settings" />
  </Region>
</Card>`,
  "coverage": [{ "requirement": "展示两台设备电量并提供设置操作" }],
  "unmetRequirements": []
})
```

## 示例六：两个必要操作挤占内容高度

### 输入

```json
{
  "userQuery": "显示当前园艺待办数量，并能打开清单和新增一项。",
  "size": "2x2",
  "actions": [
    { "id": "garden.tasks.open", "description": "打开清单" },
    { "id": "garden.tasks.create", "description": "新增待办" }
  ],
  "data": [{ "id": "garden.tasks.countText", "type": "string", "description": "园艺待办数量。", "value": "2项待办" }],
  "assetCandidates": []
}
```

### 分析

两个 Action 都必须保留，只选有两个底部按钮槽的 `wide-content-two-actions`。内容槽仅 38vp，放一个短强调文本；不放环形组件，也不为装饰增加标题。

### 计划

```js
submit_card_plan({
  "info_required": [
    { "requirement": "园艺待办数量", "dataId": "garden.tasks.countText", "componentHints": ["EmphasisText"] },
    { "requirement": "打开园艺待办清单", "actionId": "garden.tasks.open", "componentHints": ["PillButton"] },
    { "requirement": "新增园艺待办", "actionId": "garden.tasks.create", "componentHints": ["PillButton"] }
  ]
})
```

### 提交

```js
submit_card_jsx({
  "jsx": `<Card size="2x2" appearance="solid-blue" layout="single">
  <Region slot="main" variant="wide-content-two-actions">
    <EmphasisText mainText="2项待办" dataIds={{"mainText":"garden.tasks.countText"}} />
    <PillButton label="打开清单" appearance="card" actionId="garden.tasks.open" />
    <PillButton label="新增待办" appearance="card" actionId="garden.tasks.create" />
  </Region>
</Card>`,
  "coverage": [{ "requirement": "展示待办数量并提供打开清单和新增操作" }],
  "unmetRequirements": []
})
```
