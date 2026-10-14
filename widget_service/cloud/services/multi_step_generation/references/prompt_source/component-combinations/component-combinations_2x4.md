---
name: phone-widget-component-combinations-2x4
description: 规定共享组合语义在 2×4 中的组件形态、合法 variant、固定槽与尺寸示例；成立条件见 component-combinations_common.md。
---

# 2×4 多组件组合

## 1. 组合实现总表

| 类型 | 组合名称 | 本尺寸实现 | 布局 / variant | 本尺寸限制 |
|---|---|---|---|---|
| 标题组合 | 标题与数量 | 标题组件 + `Badge` | 任一支持标题的 compact／wide variant，或 `top-bottom.title` | 作为一个标题单元；`Badge` 紧跟标题 |
| 主次组合 | 核心与补充 | 标题 + 2 个内容组件 | `compact-title-primary-secondary` 或 `wide-title-primary-secondary` | 按标题、核心、补充顺序提交 |
| 主次操作 | 核心、补充与操作 | 标题 + 2 个宽内容组件 + `PillButton` | `wide-title-primary-secondary-action` | 仅宽内容区；按钮为最后一个直属节点 |
| 内容操作 | 单内容与操作 | 标题 + 内容组件 + `PillButton` | `compact-title-content-action` 或 `wide-title-content-action` | 内容必须符合当前 compact／wide 闭集 |
| 占比组合 | 双占比 | `ProgressCircle × 2` + 可选 `PillButton` | `wide-title-double-progress` | 恰好 2 个 `ProgressCircle size="sm"`；可选 1 个共同 Action |
| 占比组合 | 三占比 | 一个 `NumericRatioStack` | compact／wide 通用单内容位 | 恰好 3 项；整体算 1 个内容组件 |
| 占比组合 | 四占比 | `ProgressCircle × 4` | `wide-quad-progress` | 无标题、无 Action |
| 固定模块 | 双信息块 | `InfoBlock × 2` | `main-right-double` 的 `side-top` 与 `side-bottom` | 左侧 `main` 仍必须有真实主内容 |
| 操作组合 | 双操作 | `CardButton × 2` | `main-right-double` 的 `side-top` 与 `side-bottom` | 恰好 2 个 Action；不用 `PillButton` 填固定槽 |
| 信息操作 | 信息与操作槽 | `InfoBlock` + `CardButton` | `main-right-double` 的右侧双槽 | 固定为上信息、下操作 |
| 固定模块 | 四固定模块 | `InfoBlock`／`CardButton` 共 4 个 | `four-blocks` | 恰好 4 个完整模块；每槽 1 个 |

## 2. 标题、主次与操作实现

### 2.1 标题与数量

一个 `SingleLineTitle`／`DoubleLineTitle` 后紧跟一个 `Badge`，两者作为一个标题单元进入同一标题位。

```jsx
<Region slot="main" variant="wide-title-content">
  <SingleLineTitle title="未来7天日程" />
  <Badge value={1} color="pink" dataIds={{ value: "calendar.eventCount" }} />
  <EventCard
    items={[{
      title: "项目例会",
      time: "14:00",
      dataIds: {
        title: "calendar.events.0.title",
        time: "calendar.events.0.dtStart",
      }
    }]}
  />
</Region>
```

### 2.2 核心与补充

使用 `compact-title-primary-secondary` 或 `wide-title-primary-secondary`，标题后依次提交核心组件和短补充组件。两个都很高的连续组件不能进入同一主次变体；应改用更高密度组件或其他父布局。

```jsx
<Region slot="main" variant="wide-title-primary-secondary">
  <SingleLineTitle title="饮水进度" />
  <ProgressLine2
    currentValue={1200}
    totalValue={2000}
    value="1200毫升"
    mode="light"
    dataIds={{ value: "hydration.consumedText" }}
  />
  <SecondaryBody
    items={[
      { label: "目标", value: "2000毫升", dataIds: { value: "hydration.targetText" } },
      { label: "剩余", value: "800毫升", dataIds: { value: "hydration.remainingText" } }
    ]}
  />
</Region>
```

### 2.3 单内容与操作

紧凑内容区使用 `compact-title-content-action`，宽内容区使用 `wide-title-content-action`。紧凑版本的主体必须短；宽版本仍只允许一个宽内容组件。

```jsx
<Region slot="right" variant="compact-title-content-action">
  <SingleLineTitle title="健康数据" />
  <EmphasisText mainText="6200" secondaryText="今日步数" dataIds={{ mainText: "healthSport.dailySteps" }} />
  <PillButton label="进入锻炼" icon="figure_run.svg" appearance="card" actionId="event.open.health.sport" />
</Region>
```

### 2.4 核心、补充与操作

仅使用 `wide-title-primary-secondary-action`。标题、核心、补充和 `PillButton` 依次为直属子节点；任一内容无法在宽内容位中闭合时，当前组合实现不成立。

```jsx
<Region slot="main" variant="wide-title-primary-secondary-action">
  <SingleLineTitle title="家庭用电" />
  <EmphasisText mainText="6.8度" secondaryText="今日用电" dataIds={{ mainText: "energy.today" }} />
  <SecondaryBody
    items={[
      { label: "峰值", value: "1.2千瓦", dataIds: { value: "energy.peak" } },
      { label: "较昨日", value: "-8%", dataIds: { value: "energy.change" } }
    ]}
  />
  <PillButton label="用电详情" appearance="card" actionId="energy.open" />
</Region>
```

## 3. 占比组合实现

### 3.1 双占比

`wide-title-double-progress` 中依次放标题、2 个 `ProgressCircle size="sm"` 和可选的 `PillButton`。

```jsx
<Region slot="main" variant="wide-title-double-progress">
  <SingleLineTitle title="储物空间" />
  <ProgressCircle icon="photo.svg" externalText="72%" size="sm" appearance="card" ariaLabel="照片占用72%" dataIds={{ externalText: "storage.photosPercent" }} />
  <ProgressCircle icon="video.svg" externalText="41%" size="sm" appearance="card" ariaLabel="视频占用41%" dataIds={{ externalText: "storage.videosPercent" }} />
  <PillButton label="清理空间" appearance="card" actionId="storage.clean" />
</Region>
```

### 3.2 三占比

使用一个 `NumericRatioStack` 进入通用单内容位：

```jsx
<NumericRatioStack
  direction="column"
  appearance="card"
  items={[
    { icon: "work.svg", value: 50, unit: "%", dataIds: { value: "focus.work" } },
    { icon: "study.svg", value: 30, unit: "%", dataIds: { value: "focus.study" } },
    { icon: "rest.svg", value: 20, unit: "%", dataIds: { value: "focus.rest" } }
  ]}
/>
```

### 3.3 四占比

使用 `wide-quad-progress`，子节点恰好为 4 个 `ProgressCircle`：

```jsx
<Region slot="left" variant="wide-quad-progress">
  <ProgressCircle icon="app-a.svg" externalText="80%" size="sm" appearance="card" ariaLabel="应用A占用80%" dataIds={{ externalText: "apps.a" }} />
  <ProgressCircle icon="app-b.svg" externalText="65%" size="sm" appearance="card" ariaLabel="应用B占用65%" dataIds={{ externalText: "apps.b" }} />
  <ProgressCircle icon="app-c.svg" externalText="45%" size="sm" appearance="card" ariaLabel="应用C占用45%" dataIds={{ externalText: "apps.c" }} />
  <ProgressCircle icon="app-d.svg" externalText="30%" size="sm" appearance="card" ariaLabel="应用D占用30%" dataIds={{ externalText: "apps.d" }} />
</Region>
```

## 4. 2×4 固定模块组合

### 4.1 双信息块

分别放入 `main-right-double` 的 `side-top` 和 `side-bottom`。左侧 `main` 必须有一组真实、完整且不使用 `InfoBlock` 的内容；如果只有两组信息而没有可构成主内容区的其他信息，不能使用该父布局。

```jsx
<Region slot="side-top">
  <InfoBlock
    primaryText="昨夜7小时1分"
    secondaryText="午睡0分"
    visual={{ type: "icon", icon: "moon_z_fill_1.svg" }}
    dataIds={{
      primaryText: "healthSport.nightSleepDurationText",
      secondaryText: "healthSport.totalNapDurationText",
    }}
  />
</Region>
<Region slot="side-bottom">
  <InfoBlock
    primaryText="昨夜82分"
    secondaryText="睡眠状态良好"
    visual={{ type: "icon", icon: "moon_z_fill_1.svg" }}
    dataIds={{
      primaryText: "healthSport.sleepScore",
      secondaryText: "healthSport.sleepStatus",
    }}
  />
</Region>
```

### 4.2 双操作

两个 `CardButton` 分别放入 `main-right-double` 的 `side-top` 和 `side-bottom`：

```jsx
<Region slot="side-top">
  <CardButton text="打开门锁" icon="lock.svg" actionId="home.unlock" />
</Region>
<Region slot="side-bottom">
  <CardButton text="查看监控" icon="camera.svg" actionId="home.camera" />
</Region>
```

固定操作槽不使用 `PillButton`。

### 4.3 信息与操作槽

固定为上 `InfoBlock`、下 `CardButton`。两者不必直接语义绑定，但都应服务当前卡片目标。

```jsx
<Region slot="side-top">
  <InfoBlock primaryText="正常" secondaryText="门窗状态" dataIds={{ primaryText: "home.entryStatus" }} />
</Region>
<Region slot="side-bottom">
  <CardButton text="布防" icon="shield.svg" actionId="home.arm" />
</Region>
```

### 4.4 四固定模块

恰好 4 个层级相近的真实模块分别放入 `four-blocks` 的四个槽。混用 `InfoBlock` 与 `CardButton` 时，同类模块必须同列并按上到下排列。

```jsx
<Card size="2x4" appearance="solid-blue" layout="four-blocks">
  <Region slot="top-left"><InfoBlock primaryText="22°" secondaryText="客厅" dataIds={{ primaryText: "home.living.temperature" }} /></Region>
  <Region slot="top-right"><CardButton text="打开空调" icon="ac.svg" actionId="home.ac.open" /></Region>
  <Region slot="bottom-left"><InfoBlock primaryText="48%" secondaryText="湿度" dataIds={{ primaryText: "home.living.humidity" }} /></Region>
  <Region slot="bottom-right"><CardButton text="打开加湿器" icon="humidifier.svg" actionId="home.humidifier.open" /></Region>
</Card>
```
