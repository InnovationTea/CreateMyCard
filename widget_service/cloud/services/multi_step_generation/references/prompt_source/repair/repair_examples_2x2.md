---
name: phone-widget-repair-examples-2x2
description: 根据 2×2 几何 findings 检索的修复前后示例；整张卡最多加载两例。
---

# 2×2 几何修复示例库

合成 ID 与值仅演示如何保留绑定和 Action；不可复制为当前任务答案。

## 修复 short-main | component | overflow

### 情况

一个短数值足以表达主信息，过长的静态说明在窄卡中溢出。只精简静态说明，保留数据和 Action。

### 失败版

```jsx
<Card size="2x2" appearance="solid-blue" layout="single"><Region slot="main" variant="wide-title-content-action"><SingleLineTitle title="室内温度" /><EmphasisText mainText="23℃" secondaryText="当前书房测量到的实时温度" dataIds={{mainText:"repair.room.temp"}} /><PillButton appearance="card" label="查看房间" actionId="repair.room.open" /></Region></Card>
```

### findings

`browser-semantic-content-overflow`，`repairScope=component`。

### 修复版

```jsx
<Card size="2x2" appearance="solid-blue" layout="single"><Region slot="main" variant="wide-title-content-action"><SingleLineTitle title="室内温度" /><EmphasisText mainText="23℃" secondaryText="书房" dataIds={{mainText:"repair.room.temp"}} /><PillButton appearance="card" label="查看房间" actionId="repair.room.open" /></Region></Card>
```

## 修复 merge-schedule | component | overlap

### 情况

同一预约的标题、时间和地点分占多个文本组件，在标题下相撞。合成单个 EventCard，不改变三个 ID。

### 失败版

```jsx
<Card size="2x2" appearance="orb-orange" layout="single"><Region slot="main" variant="wide-title-primary-secondary"><SingleLineTitle title="预约" /><EmphasisText mainText="设备维护" secondaryText="14:00" dataIds={{mainText:"repair.visit.title",secondaryText:"repair.visit.time"}} /><EmphasisText mainText="北区" secondaryText="地点" dataIds={{mainText:"repair.visit.place"}} /></Region></Card>
```

### findings

`browser-semantic-overlap`，`repairScope=component`。

### 修复版

```jsx
<Card size="2x2" appearance="orb-orange" layout="single"><Region slot="main" variant="wide-title-content"><SingleLineTitle title="预约" /><EventCard items={[{"title":"设备维护","time":"14:00","location":"北区","dataIds":{"title":"repair.visit.title","time":"repair.visit.time","location":"repair.visit.place"}}]} /></Region></Card>
```

## 修复 action-slot | sublayout | structure

### 情况

唯一 Action 被放进无操作变体。改成对应操作变体；标题、数据和 Action 不变。

### 失败版

```jsx
<Card size="2x2" appearance="solid-green" layout="single"><Region slot="main" variant="wide-title-content"><SingleLineTitle title="门锁" /><EmphasisText mainText="已锁定" secondaryText="当前状态" dataIds={{mainText:"repair.lock.state"}} /><PillButton appearance="card" label="打开门锁" actionId="repair.lock.open" /></Region></Card>
```

### findings

`layout-structure`，`repairScope=sublayout`。

### 修复版

```jsx
<Card size="2x2" appearance="solid-green" layout="single"><Region slot="main" variant="wide-title-content-action"><SingleLineTitle title="门锁" /><EmphasisText mainText="已锁定" secondaryText="当前状态" dataIds={{mainText:"repair.lock.state"}} /><PillButton appearance="card" label="打开门锁" actionId="repair.lock.open" /></Region></Card>
```

## 修复 two-actions | sublayout | overflow

### 情况

两个必要按钮与标题及大主值放不下。使用双操作变体的唯一紧凑内容位，保留两个 Action。

### 失败版

```jsx
<Card size="2x2" appearance="solid-purple" layout="single"><Region slot="main" variant="wide-title-content-action"><SingleLineTitle title="播放器" /><EmphasisText mainText="播放中" dataIds={{mainText:"repair.player.state"}} /><PillButton appearance="card" label="下一首" actionId="repair.player.next" /><PillButton appearance="card" label="暂停" actionId="repair.player.pause" /></Region></Card>
```

### findings

`browser-overflow`，`repairScope=sublayout`。

### 修复版

```jsx
<Card size="2x2" appearance="solid-purple" layout="single"><Region slot="main" variant="wide-content-two-actions"><EmphasisText mainText="播放中" dataIds={{mainText:"repair.player.state"}} /><PillButton appearance="card" label="下一首" actionId="repair.player.next" /><PillButton appearance="card" label="暂停" actionId="repair.player.pause" /></Region></Card>
```

## 修复 independent-blocks | parent-layout | overflow

### 情况

两个相互独立、各只有一项状态的对象被塞进单区双内容。改为两个固定 InfoBlock；无 Action 才能这样换。

### 失败版

```jsx
<Card size="2x2" appearance="orb-blue" layout="single"><Region slot="main" variant="wide-title-primary-secondary"><SingleLineTitle title="家庭设备" /><EmphasisText mainText="运行中" secondaryText="净化器" dataIds={{mainText:"repair.purifier.state"}} /><EmphasisText mainText="待机" secondaryText="加湿器" dataIds={{mainText:"repair.humidifier.state"}} /></Region></Card>
```

### findings

反复 `browser-semantic-overlap`，`repairScope=parent-layout`。

### 修复版

```jsx
<Card size="2x2" appearance="orb-blue" layout="double-blocks"><Region slot="top"><InfoBlock primaryText="运行中" secondaryText="净化器" dataIds={{primaryText:"repair.purifier.state"}} /></Region><Region slot="bottom"><InfoBlock primaryText="待机" secondaryText="加湿器" dataIds={{primaryText:"repair.humidifier.state"}} /></Region></Card>
```

## 修复 keep-action | parent-layout | structure

### 情况

双信息块没有操作槽，不能把必要 Action 塞入 InfoBlock。若两项数据属于同一设备，改用单区主次内容加操作变体。

### 失败版

```jsx
<Card size="2x2" appearance="solid-green" layout="double-blocks"><Region slot="top"><InfoBlock primaryText="22℃" secondaryText="当前温度" dataIds={{primaryText:"repair.thermostat.temp"}} /></Region><Region slot="bottom"><InfoBlock primaryText="自动" secondaryText="当前模式" dataIds={{primaryText:"repair.thermostat.mode"}} /><PillButton appearance="card" label="调节" actionId="repair.thermostat.adjust" /></Region></Card>
```

### findings

`layout-structure`，`repairScope=parent-layout`。

### 修复版

```jsx
<Card size="2x2" appearance="solid-green" layout="single"><Region slot="main" variant="wide-title-content-action"><SingleLineTitle title="室内温控" /><EmphasisText mainText="22℃" secondaryText="自动" secondaryTextTemplate="模式 {value}" dataIds={{mainText:"repair.thermostat.temp",secondaryText:"repair.thermostat.mode"}} /><PillButton appearance="card" label="调节" actionId="repair.thermostat.adjust" /></Region></Card>
```
