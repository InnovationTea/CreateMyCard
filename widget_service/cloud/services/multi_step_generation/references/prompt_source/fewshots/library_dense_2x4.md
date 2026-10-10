---
name: phone-widget-fewshot-dense-2x4
description: 高密度输入的 2×4 结构化容量案例，按需检索。
---

# 高密度容量案例

## 示例 25：两场培训与现场保障

### 输入

```json
{"userQuery":"查看两场培训的名称、时间和地点，以及现场席位状态，并联系协调员。","size":"2x4","actions":[{"id":"training.coordinator.contact","description":"联系协调员"}],"data":[{"id":"training.first.title","type":"string","value":"设备入门"},{"id":"training.first.time","type":"string","value":"09:00"},{"id":"training.first.place","type":"string","value":"一教室"},{"id":"training.second.title","type":"string","value":"安全演练"},{"id":"training.second.time","type":"string","value":"14:00"},{"id":"training.second.place","type":"string","value":"二教室"},{"id":"training.seats.state","type":"string","value":"余位充足"}],"assetCandidates":[]}
```

### 分析

7 个必需数据、1 个 Action。六个日程字段由同一个 `EventCard.items` 承载两条完整事件；席位状态在右上固定信息槽，联系操作在右下，不拆成多个 EventCard 或删掉第二场培训。

### 提交

```js
submit_card_jsx({"jsx": `<Card size="2x4" appearance="solid-green" layout="main-right-double"><Region slot="main" variant="wide-title-content"><SingleLineTitle title="培训安排" /><EventCard density="compact" items={[{"title":"设备入门","time":"09:00","location":"一教室","dataIds":{"title":"training.first.title","time":"training.first.time","location":"training.first.place"}},{"title":"安全演练","time":"14:00","location":"二教室","dataIds":{"title":"training.second.title","time":"training.second.time","location":"training.second.place"}}]} /></Region><Region slot="side-top"><InfoBlock primaryText="余位充足" secondaryText="现场席位" dataIds={{primaryText:"training.seats.state"}} /></Region><Region slot="side-bottom"><CardButton text="联系协调员" actionId="training.coordinator.contact" /></Region></Card>`,"coverage":[{"requirement":"展示两场培训及现场保障和联系操作"}],"unmetRequirements":[]})
```

## 示例 26：两场工坊与两个独立状态

### 输入

```json
{"userQuery":"查看两场工坊的名称、时间和地点，同时看场地准备状态与签到状态。","size":"2x4","actions":[],"data":[{"id":"workshop.first.title","type":"string","value":"木工体验"},{"id":"workshop.first.time","type":"string","value":"10:00"},{"id":"workshop.first.place","type":"string","value":"南馆"},{"id":"workshop.second.title","type":"string","value":"陶艺入门"},{"id":"workshop.second.time","type":"string","value":"15:00"},{"id":"workshop.second.place","type":"string","value":"北馆"},{"id":"workshop.venue.state","type":"string","value":"准备完成"},{"id":"workshop.checkin.state","type":"string","value":"尚未开始"}],"assetCandidates":[]}
```

### 分析

8 个必需数据、0 个 Action。两条事件以一个紧凑 EventCard 表达；右侧两个固定槽各承载一个独立状态。数据多不等于要在单个 InfoBlock 塞入多个动态字段。

### 提交

```js
submit_card_jsx({"jsx": `<Card size="2x4" appearance="solid-blue" layout="main-right-double"><Region slot="main" variant="wide-title-content"><SingleLineTitle title="工坊安排" /><EventCard density="compact" items={[{"title":"木工体验","time":"10:00","location":"南馆","dataIds":{"title":"workshop.first.title","time":"workshop.first.time","location":"workshop.first.place"}},{"title":"陶艺入门","time":"15:00","location":"北馆","dataIds":{"title":"workshop.second.title","time":"workshop.second.time","location":"workshop.second.place"}}]} /></Region><Region slot="side-top"><InfoBlock primaryText="准备完成" secondaryText="场地" dataIds={{primaryText:"workshop.venue.state"}} /></Region><Region slot="side-bottom"><InfoBlock primaryText="尚未开始" secondaryText="签到" dataIds={{primaryText:"workshop.checkin.state"}} /></Region></Card>`,"coverage":[{"requirement":"展示两场工坊及场地和签到状态"}],"unmetRequirements":[]})
```

## 示例 27：一次活动与一项设备状态

### 输入

```json
{"userQuery":"查看社区活动名称、起止时间和地点，了解场地设备状态，并联系协调员。","size":"2x4","actions":[{"id":"activity.coordinator.contact","description":"联系协调员"}],"data":[{"id":"activity.title","type":"string","value":"社区讲座"},{"id":"activity.start","type":"string","value":"13:30"},{"id":"activity.end","type":"string","value":"15:00"},{"id":"activity.place","type":"string","value":"活动室"},{"id":"activity.device.state","type":"string","value":"已就绪"}],"assetCandidates":[]}
```

### 分析

5 个数据、1 个 Action。四个事件字段进入一个 EventCard；一个独立设备状态占右上固定槽，联络操作占右下固定槽。

### 提交

```js
submit_card_jsx({"jsx": `<Card size="2x4" appearance="solid-green" layout="main-right-double"><Region slot="main" variant="wide-title-content"><SingleLineTitle title="社区活动" /><EventCard items={[{"title":"社区讲座","time":"13:30 – 15:00","location":"活动室","dataIds":{"title":"activity.title","time":["activity.start","activity.end"],"location":"activity.place"}}]} /></Region><Region slot="side-top"><InfoBlock primaryText="已就绪" secondaryText="场地设备" dataIds={{primaryText:"activity.device.state"}} /></Region><Region slot="side-bottom"><CardButton text="联系协调员" actionId="activity.coordinator.contact" /></Region></Card>`,"coverage":[{"requirement":"展示活动、设备状态和联系操作"}],"unmetRequirements":[]})
```

## 示例 28：一次活动与两个必要操作

### 输入

```json
{"userQuery":"查看公开课名称、起止时间和地点，并能报名和查看课程。","size":"2x4","actions":[{"id":"class.signup","description":"报名"},{"id":"class.open","description":"查看课程"}],"data":[{"id":"class.title","type":"string","value":"摄影公开课"},{"id":"class.start","type":"string","value":"10:00"},{"id":"class.end","type":"string","value":"11:30"},{"id":"class.place","type":"string","value":"教学楼"}],"assetCandidates":[]}
```

### 分析

4 个数据、2 个 Action。事件字段在左侧一个组件内完整展示，两个不同动作各占右侧一个固定槽。

### 提交

```js
submit_card_jsx({"jsx": `<Card size="2x4" appearance="solid-purple" layout="main-right-double"><Region slot="main" variant="wide-title-content"><SingleLineTitle title="公开课" /><EventCard items={[{"title":"摄影公开课","time":"10:00 – 11:30","location":"教学楼","dataIds":{"title":"class.title","time":["class.start","class.end"],"location":"class.place"}}]} /></Region><Region slot="side-top"><CardButton text="报名" actionId="class.signup" /></Region><Region slot="side-bottom"><CardButton text="查看课程" actionId="class.open" /></Region></Card>`,"coverage":[{"requirement":"展示公开课并提供报名和查看操作"}],"unmetRequirements":[]})
```
