---
name: phone-widget-repair-examples-2x4
description: 按几何 findings 与修复范围检索的 2×4 前后对照；不随首轮 Prompt 整体加载。
---

# 2×4 几何修复示例库

示例中输入值、ID 和文案为合成示范。先保留每个必要数据绑定和 Action，再调整承载组件或语义布局；不能通过删除、裁剪或静态化取得表面通过。

## 修复 merge-event | component | overlap

### 情况

输入是一条预约的标题、起止时间、地点，加一个查看操作。两个时间点被拆成独立文本后在主内容区重叠。将同一事件无损收拢为一个 `EventCard`，操作槽不变。

### 失败版

```jsx
<Card size="2x4" appearance="solid-blue" layout="main-right-double"><Region slot="main" variant="wide-title-primary-secondary"><SingleLineTitle title="预约" /><EmphasisText mainText="设备检修" secondaryText="09:00" dataIds={{mainText:"repair.booking.title",secondaryText:"repair.booking.start"}} /><EmphasisText mainText="10:30" secondaryText="A区" dataIds={{mainText:"repair.booking.end",secondaryText:"repair.booking.place"}} /></Region><Region slot="side-top"><InfoBlock primaryText="待确认" secondaryText="预约状态" dataIds={{primaryText:"repair.booking.state"}} /></Region><Region slot="side-bottom"><CardButton text="查看预约" actionId="repair.booking.open" /></Region></Card>
```

### findings

`browser-semantic-overlap`，`repairScope=component`。

### 修复版

```jsx
<Card size="2x4" appearance="solid-blue" layout="main-right-double"><Region slot="main" variant="wide-title-content"><SingleLineTitle title="预约" /><EventCard items={[{"title":"设备检修","time":"09:00 – 10:30","location":"A区","dataIds":{"title":"repair.booking.title","time":["repair.booking.start","repair.booking.end"],"location":"repair.booking.place"}}]} /></Region><Region slot="side-top"><InfoBlock primaryText="待确认" secondaryText="预约状态" dataIds={{primaryText:"repair.booking.state"}} /></Region><Region slot="side-bottom"><CardButton text="查看预约" actionId="repair.booking.open" /></Region></Card>
```

## 修复 short-labels | component | overflow

### 情况

主体和三个短明细都能保留，但明细标签过长导致右边缘溢出。只缩短静态标签，不改数据值、绑定和槽位。

### 失败版

```jsx
<Card size="2x4" appearance="solid-green" layout="top-bottom"><Region slot="title"><SingleLineTitle title="今日饮水" /></Region><Region slot="primary"><EmphasisText mainText="1600毫升" secondaryText="今日合计" dataIds={{mainText:"repair.water.total"}} /></Region><Region slot="details"><TextBlock items={[{"label":"清晨第一次饮水","parameter":"300毫升","dataIds":{"parameter":"repair.water.a"}},{"label":"中午前饮水量","parameter":"450毫升","dataIds":{"parameter":"repair.water.b"}},{"label":"午后补充饮水","parameter":"500毫升","dataIds":{"parameter":"repair.water.c"}}]} /></Region></Card>
```

### findings

`browser-visible-horizontal-overflow`，`repairScope=component`。

### 修复版

```jsx
<Card size="2x4" appearance="solid-green" layout="top-bottom"><Region slot="title"><SingleLineTitle title="今日饮水" /></Region><Region slot="primary"><EmphasisText mainText="1600毫升" secondaryText="今日合计" dataIds={{mainText:"repair.water.total"}} /></Region><Region slot="details"><TextBlock items={[{"label":"清晨","parameter":"300毫升","dataIds":{"parameter":"repair.water.a"}},{"label":"午前","parameter":"450毫升","dataIds":{"parameter":"repair.water.b"}},{"label":"午后","parameter":"500毫升","dataIds":{"parameter":"repair.water.c"}}]} /></Region></Card>
```

## 修复 variant-density | sublayout | overflow

### 情况

同一侧两项可比较的同单位数据被放成两个独立强调组件；改用单个比较组件及相应单内容变体，另一侧保持原样。

### 失败版

```jsx
<Card size="2x4" appearance="solid-cyan" layout="split-panels"><Region slot="left" variant="compact-title-primary-secondary"><SingleLineTitle title="房间用电" /><EmphasisText mainText="4.2千瓦时" secondaryText="客厅" dataIds={{mainText:"repair.energy.living"}} /><EmphasisText mainText="2.1千瓦时" secondaryText="书房" dataIds={{mainText:"repair.energy.study"}} /></Region><Region slot="right" variant="compact-title-content"><SingleLineTitle title="空气" /><EmphasisText mainText="良好" secondaryText="当前状态" dataIds={{mainText:"repair.air.status"}} /></Region></Card>
```

### findings

`browser-semantic-content-overflow`，`repairScope=sublayout`。

### 修复版

```jsx
<Card size="2x4" appearance="solid-cyan" layout="split-panels"><Region slot="left" variant="compact-title-content"><SingleLineTitle title="房间用电" /><H_BarChart mode="light" items={[{"label":"客厅","valueUnit":"4.2千瓦时","percent":100,"dataIds":{"valueUnit":"repair.energy.living"}},{"label":"书房","valueUnit":"2.1千瓦时","percent":50,"dataIds":{"valueUnit":"repair.energy.study"}}]} /></Region><Region slot="right" variant="compact-title-content"><SingleLineTitle title="空气" /><EmphasisText mainText="良好" secondaryText="当前状态" dataIds={{mainText:"repair.air.status"}} /></Region></Card>
```

## 修复 variant-action | sublayout | overlap

### 情况

左侧操作放在无操作变体中与正文相撞。保持两个分区和全部绑定，仅把左侧改成带直属操作的变体。

### 失败版

```jsx
<Card size="2x4" appearance="solid-purple" layout="split-panels"><Region slot="left" variant="compact-title-content"><SingleLineTitle title="快递" /><EmphasisText mainText="派送中" secondaryText="当前状态" dataIds={{mainText:"repair.parcel.status"}} /><PillButton appearance="card" label="查看快递" actionId="repair.parcel.open" /></Region><Region slot="right" variant="compact-title-content"><SingleLineTitle title="天气" /><EmphasisText mainText="多云" secondaryText="当前天气" dataIds={{mainText:"repair.weather.state"}} /></Region></Card>
```

### findings

`layout-structure` 或 `browser-semantic-overlap`，`repairScope=sublayout`。

### 修复版

```jsx
<Card size="2x4" appearance="solid-purple" layout="split-panels"><Region slot="left" variant="compact-title-content-action"><SingleLineTitle title="快递" /><EmphasisText mainText="派送中" secondaryText="当前状态" dataIds={{mainText:"repair.parcel.status"}} /><PillButton appearance="card" label="查看快递" actionId="repair.parcel.open" /></Region><Region slot="right" variant="compact-title-content"><SingleLineTitle title="天气" /><EmphasisText mainText="多云" secondaryText="当前天气" dataIds={{mainText:"repair.weather.state"}} /></Region></Card>
```

## 修复 parent-summary | parent-layout | overflow

### 情况

一个主题的核心值和两个独立状态勉强进入上下布局，明细标签和值超出横排空间。多次缩短标签仍不闭合后，改为主内容 + 右侧两个真实信息槽；三个数据均保留。

### 失败版

```jsx
<Card size="2x4" appearance="solid-blue" layout="top-bottom"><Region slot="title"><SingleLineTitle title="园区用水" /></Region><Region slot="primary"><EmphasisText mainText="62吨" secondaryText="总量" dataIds={{mainText:"repair.water.total"}} /></Region><Region slot="details"><TextBlock items={[{"label":"冷却系统用水","parameter":"19吨","dataIds":{"parameter":"repair.water.cooling"}},{"label":"清洁系统用水","parameter":"18吨","dataIds":{"parameter":"repair.water.cleaning"}}]} /></Region></Card>
```

### findings

连续 `browser-visible-horizontal-overflow`，`repairScope=parent-layout`。

### 修复版

```jsx
<Card size="2x4" appearance="solid-blue" layout="main-right-double"><Region slot="main" variant="wide-title-content"><SingleLineTitle title="园区用水" /><EmphasisText mainText="62吨" secondaryText="总量" dataIds={{mainText:"repair.water.total"}} /></Region><Region slot="side-top"><InfoBlock primaryText="19吨" secondaryText="冷却" dataIds={{primaryText:"repair.water.cooling"}} /></Region><Region slot="side-bottom"><InfoBlock primaryText="18吨" secondaryText="清洁" dataIds={{primaryText:"repair.water.cleaning"}} /></Region></Card>
```

## 修复 parent-actions | parent-layout | structure

### 情况

同一设备的两项必要操作不能塞进 split-panels 的同一侧。改为主内容 + 右侧双操作，两个 Action 均保留，且不虚构第二个业务主题。

### 失败版

```jsx
<Card size="2x4" appearance="solid-green" layout="split-panels"><Region slot="left" variant="compact-title-content-action"><SingleLineTitle title="清洁设备" /><EmphasisText mainText="待机" secondaryText="设备状态" dataIds={{mainText:"repair.cleaner.state"}} /><PillButton appearance="card" label="开始清洁" actionId="repair.cleaner.start" /><PillButton appearance="card" label="打开设置" actionId="repair.cleaner.settings" /></Region><Region slot="right" variant="compact-title-content"><SingleLineTitle title="剩余电量" /><EmphasisText mainText="78%" secondaryText="电池" dataIds={{mainText:"repair.cleaner.battery"}} /></Region></Card>
```

### findings

`layout-structure`，`repairScope=parent-layout`。

### 修复版

```jsx
<Card size="2x4" appearance="solid-green" layout="main-right-double"><Region slot="main" variant="wide-title-content"><SingleLineTitle title="清洁设备" /><EmphasisText mainText="待机" secondaryText="78%" secondaryTextTemplate="电量 {value}" dataIds={{mainText:"repair.cleaner.state",secondaryText:"repair.cleaner.battery"}} /></Region><Region slot="side-top"><CardButton text="开始清洁" actionId="repair.cleaner.start" /></Region><Region slot="side-bottom"><CardButton text="打开设置" actionId="repair.cleaner.settings" /></Region></Card>
```
