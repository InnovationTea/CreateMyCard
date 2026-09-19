# 2×4 端到端示例

这些示例只演示如何把信息关系闭合为当前工具参数和布局，不是可复用的业务答案。

- 示例中的实体、字段 ID、数值、文案和 Action 均为虚构；实际生成只能使用当前输入。
- “信息分区”是生成时需要考虑的简短结论，不要求额外输出。
- 固定槽限制的是业务组件数量，不是原始字段数量；一个支持多字段的组件可以在同一槽内表达一个完整且紧凑的信息组。
- 高密度不等于优先使用键值表。时间事件优先保留“事件名—时间范围—地点”的阅读层级；主值与状态优先使用有主次关系的组件；同单位指标可使用横向指标组。只有多个字段确实是同一对象的平行属性、且行标签对理解不可缺少时，才使用 `TableText` 或 `TextBlock`。
- 同一显示 Prop 合并多个字段时，每个值必须自身带有必要语义，或组合关系一眼可知。不得把无标签的温度、湿度、开始时间和结束时间等不同含义的裸值用 `｜` 并列后交给用户猜测。
- `submit_card_plan` 和 `submit_card_jsx` 必须遵守当前工具 Schema；若示例与组件或布局合同冲突，以合同为准。
- 不要因为当前任务与示例领域相似就复制组件、标题或布局；应根据当前信息数量、分区关系、Action 归属和真实占位重新选择。

## 示例一：一个主题的汇总与三项同级明细

### 输入

```json
{
  "userQuery": "展示本周工作室总用电量，以及照明、空调和设备用电分别是多少。",
  "size": "2x4",
  "actions": [],
  "data": [
    { "id": "studioPower.week.totalText", "type": "string", "description": "本周工作室总用电量。", "value": "96千瓦时" },
    { "id": "studioPower.week.lightingText", "type": "string", "description": "本周照明用电量。", "value": "18千瓦时" },
    { "id": "studioPower.week.coolingText", "type": "string", "description": "本周空调用电量。", "value": "34千瓦时" },
    { "id": "studioPower.week.equipmentText", "type": "string", "description": "本周设备用电量。", "value": "29千瓦时" }
  ],
  "assetCandidates": []
}
```

### 信息分区（不输出）

- 只有“本周工作室用电”一个信息分区。
- 总用电量是汇总；照明、空调和设备用电是三个短小、同级的格式化明细。
- 输入没有 Action，因此允许选择“上下双区”。上区用字号适中的 `EmphasisText` 建立汇总主次，下区用一个三项 `TextBlock` 表达同级明细；`TextBlock` 在这里承担横向信息块，而不是纵向键值表。

### `submit_card_plan`

```js
submit_card_plan({
  "info_required": [
    {
      "requirement": "本周工作室总用电量。",
      "dataId": "studioPower.week.totalText"
    },
    {
      "requirement": "本周照明用电量。",
      "dataId": "studioPower.week.lightingText"
    },
    {
      "requirement": "本周空调用电量。",
      "dataId": "studioPower.week.coolingText"
    },
    {
      "requirement": "本周设备用电量。",
      "dataId": "studioPower.week.equipmentText"
    }
  ],
  "layout_optionA": {
    "layoutPattern": "上下双区",
    "subPattern": {},
    "content": "整卡标题下，上区用 EmphasisText 表达总用电量及其含义；下区用一个三项 TextBlock 横向展示短小的同级明细。"
  }
})
```

### `submit_card_jsx`

```js
submit_card_jsx({
  "decision": { "layoutPattern": "上下双区", "subPattern": {} },
  "jsx": `<Card direction="column" size="2x4" appearance="solid-blue" gap={4}>
  <Stack direction="column" flex={0} width="full" height={20}>
    <SingleLineTitle title="本周工作室用电" />
  </Stack>
  <Stack direction="column" flex={1} width="full" gap={8} justify="space-between">
    <Stack direction="column" flex={0} width="full">
      <EmphasisText
        mainText="96千瓦时"
        secondaryText="总用电量"
        dataIds={{ mainText: "studioPower.week.totalText" }}
      />
    </Stack>
    <Stack direction="column" flex={0} width="full">
      <TextBlock items={[
        { label: "照明", parameter: "18千瓦时", dataIds: { parameter: "studioPower.week.lightingText" } },
        { label: "空调", parameter: "34千瓦时", dataIds: { parameter: "studioPower.week.coolingText" } },
        { label: "设备", parameter: "29千瓦时", dataIds: { parameter: "studioPower.week.equipmentText" } }
      ]} />
    </Stack>
  </Stack>
</Card>`,
  "coverage": [
    { "requirement": "展示本周工作室总用电量" },
    { "requirement": "展示照明、空调和设备用电量" }
  ],
  "unmetRequirements": []
})
```

## 示例二：两个复杂分区，各自带一个直属操作

### 输入

```json
{
  "userQuery": "做张设施卡片，同时查看温室的温度、湿度和通风模式并能调节通风，也查看冷藏区的温度、门状态和告警状态并能查看告警。",
  "size": "2x4",
  "actions": [
    { "id": "facility.greenhouse.adjustVentilation", "description": "调节通风" },
    { "id": "facility.coldRoom.viewAlerts", "description": "查看告警" }
  ],
  "data": [
    { "id": "facility.greenhouse.temperatureText", "type": "string", "description": "温室当前温度。", "value": "24℃" },
    { "id": "facility.greenhouse.humidityText", "type": "string", "description": "带标签的温室当前湿度文案。", "value": "湿度63%" },
    { "id": "facility.greenhouse.ventilationMode", "type": "string", "description": "温室当前通风模式。", "value": "自动档" },
    { "id": "facility.coldRoom.temperatureText", "type": "string", "description": "冷藏区当前温度。", "value": "-4℃" },
    { "id": "facility.coldRoom.doorStatusText", "type": "string", "description": "冷藏区当前门状态。", "value": "门已关" },
    { "id": "facility.coldRoom.alertStatusText", "type": "string", "description": "冷藏区当前告警状态。", "value": "无告警" }
  ],
  "assetCandidates": []
}
```

### 信息分区（不输出）

- 温室的三个状态字段和“调节通风”组成一个完整分区；冷藏区的三个状态字段和“查看告警”组成另一个完整分区。
- 每侧用一个 `EmphasisText` 建立“温度主值 + 带语义的环境状态”层级。湿度字段自身包含“湿度”标签，结合所属分区与“调节通风”操作后，“自动档”的含义仍然明确；不使用“环境：24℃｜63%”这种需要反推字段含义的写法。
- 两个 Action 分别直属不同分区，不应抽到统一按钮列。两侧各形成“标题 + 一个多字段主次组件 + PillButton”，选择两个 `Sub-118-D`。

### `submit_card_plan`

```js
submit_card_plan({
  "info_required": [
    {
      "requirement": "温室当前温度。",
      "dataId": "facility.greenhouse.temperatureText"
    },
    {
      "requirement": "带标签的温室当前湿度文案。",
      "dataId": "facility.greenhouse.humidityText"
    },
    {
      "requirement": "温室当前通风模式。",
      "dataId": "facility.greenhouse.ventilationMode"
    },
    {
      "requirement": "冷藏区当前温度。",
      "dataId": "facility.coldRoom.temperatureText"
    },
    {
      "requirement": "冷藏区当前门状态。",
      "dataId": "facility.coldRoom.doorStatusText"
    },
    {
      "requirement": "冷藏区当前告警状态。",
      "dataId": "facility.coldRoom.alertStatusText"
    },
    {
      "requirement": "调节通风",
      "actionId": "facility.greenhouse.adjustVentilation"
    },
    {
      "requirement": "查看告警",
      "actionId": "facility.coldRoom.viewAlerts"
    }
  ],
  "layout_optionA": {
    "layoutPattern": "左右双区",
    "subPattern": {
      "left": "Sub-118-D 标题内容单按钮",
      "right": "Sub-118-D 标题内容单按钮"
    },
    "content": "左右各保留独立标题；每侧用一个 EmphasisText 突出温度，并以带标签的状态文案补充湿度、通风或门与告警状态；底部 PillButton 只绑定本组 Action。"
  }
})
```

### `submit_card_jsx`

```js
submit_card_jsx({
  "decision": {
    "layoutPattern": "左右双区",
    "subPattern": {
      "left": "Sub-118-D 标题内容单按钮",
      "right": "Sub-118-D 标题内容单按钮"
    }
  },
  "jsx": `<Card direction="row" size="2x4" appearance="solid-green" gap={12}>
  <Stack direction="column" surface="backplate" flex={0} width={142} height={136} align="center" justify="center">
    <Stack direction="column" flex={0} width={118} height={112} gap={6}>
      <Stack direction="column" flex={0} width={118}>
        <SingleLineTitle title="温室" />
      </Stack>
      <Stack direction="column" flex={1} width={118}>
        <EmphasisText
          mainText="24℃"
          secondaryText="湿度63% ｜ 自动档"
          dataIds={{
            mainText: "facility.greenhouse.temperatureText",
            secondaryText: ["facility.greenhouse.humidityText", "facility.greenhouse.ventilationMode"]
          }}
        />
      </Stack>
      <Stack direction="column" flex={0} width={118} height={36}>
        <PillButton label="调节通风" appearance="card" actionId="facility.greenhouse.adjustVentilation" />
      </Stack>
    </Stack>
  </Stack>
  <Stack direction="column" surface="backplate" flex={0} width={142} height={136} align="center" justify="center">
    <Stack direction="column" flex={0} width={118} height={112} gap={6}>
      <Stack direction="column" flex={0} width={118}>
        <SingleLineTitle title="冷藏区" />
      </Stack>
      <Stack direction="column" flex={1} width={118}>
        <EmphasisText
          mainText="-4℃"
          secondaryText="门已关 ｜ 无告警"
          dataIds={{
            mainText: "facility.coldRoom.temperatureText",
            secondaryText: ["facility.coldRoom.doorStatusText", "facility.coldRoom.alertStatusText"]
          }}
        />
      </Stack>
      <Stack direction="column" flex={0} width={118} height={36}>
        <PillButton label="查看告警" appearance="card" actionId="facility.coldRoom.viewAlerts" />
      </Stack>
    </Stack>
  </Stack>
</Card>`,
  "coverage": [
    { "requirement": "展示温室温度、湿度、通风模式并提供调节通风操作" },
    { "requirement": "展示冷藏区温度、门状态、告警状态并提供查看告警操作" }
  ],
  "unmetRequirements": []
})
```

## 示例三：丰富主内容与复合信息、操作槽

### 输入

```json
{
  "userQuery": "展示周末展会布置任务的任务名、开始和结束时间、场馆和入口，也看现场设备数量、故障情况和巡检状态，并能联系现场负责人。",
  "size": "2x4",
  "actions": [
    { "id": "exhibition.manager.contact", "description": "联系负责人" }
  ],
  "data": [
    { "id": "exhibition.setup.taskName", "type": "string", "description": "展会布置任务名称。", "value": "主展区布置" },
    { "id": "exhibition.setup.startTime", "type": "string", "description": "任务开始时间。", "value": "09:00" },
    { "id": "exhibition.setup.endTime", "type": "string", "description": "任务结束时间。", "value": "11:30" },
    { "id": "exhibition.setup.locationText", "type": "string", "description": "任务所在场馆与入口。", "value": "A馆东入口" },
    { "id": "exhibition.device.countText", "type": "string", "description": "现场设备数量。", "value": "12台设备" },
    { "id": "exhibition.device.faultText", "type": "string", "description": "现场设备故障情况。", "value": "1台故障" },
    { "id": "exhibition.device.inspectionStatus", "type": "string", "description": "现场设备巡检状态。", "value": "已巡检" }
  ],
  "assetCandidates": []
}
```

### 信息分区（不输出）

- 布置任务的任务名、开始和结束时间、场馆入口属于一条事件信息。使用 `EventCard` 保留“任务名为主、时间范围与地点为次”的固有层级；开始和结束时间显示为明确的 `09:00 – 11:30` 范围，而不是两个并列时间点。
- 设备数量、故障情况和巡检状态组成一个可独立阅读的紧凑设备信息组，放入一个 `InfoBlock`：数量为主文本，故障与巡检状态共同组成副文本。
- “联系负责人”必须保留在独立操作槽。最终形成“左侧丰富主内容 + 右上复合 InfoBlock + 右下 CardButton”，选择“左内容右侧双槽”。

### `submit_card_plan`

```js
submit_card_plan({
  "info_required": [
    {
      "requirement": "展会布置任务名称。",
      "dataId": "exhibition.setup.taskName"
    },
    {
      "requirement": "任务开始时间。",
      "dataId": "exhibition.setup.startTime"
    },
    {
      "requirement": "任务结束时间。",
      "dataId": "exhibition.setup.endTime"
    },
    {
      "requirement": "任务所在场馆与入口。",
      "dataId": "exhibition.setup.locationText"
    },
    {
      "requirement": "现场设备数量。",
      "dataId": "exhibition.device.countText"
    },
    {
      "requirement": "现场设备故障情况。",
      "dataId": "exhibition.device.faultText"
    },
    {
      "requirement": "现场设备巡检状态。",
      "dataId": "exhibition.device.inspectionStatus"
    },
    {
      "requirement": "联系负责人",
      "actionId": "exhibition.manager.contact"
    }
  ],
  "layout_optionA": {
    "layoutPattern": "左内容右侧双槽",
    "subPattern": { "content": "Sub-140-B 标题单内容" },
    "content": "左侧标题下用 EventCard 展示任务名、明确的起止时间范围和场馆入口；右上一个 InfoBlock 聚合三个设备字段，右下 CardButton 保留联系操作。"
  }
})
```

### `submit_card_jsx`

```js
submit_card_jsx({
  "decision": {
    "layoutPattern": "左内容右侧双槽",
    "subPattern": { "content": "Sub-140-B 标题单内容" }
  },
  "jsx": `<Card direction="row" size="2x4" appearance="solid-purple" gap={12}>
  <Stack direction="column" flex={0} width={140} height={136} gap={8}>
    <Stack direction="column" flex={0} width={140}>
      <SingleLineTitle title="展会布置" />
    </Stack>
    <Stack direction="column" flex={1} width={140} align="flex-start" justify="flex-end">
      <EventCard
        items={[{
          title: "主展区布置",
          time: "09:00 – 11:30",
          location: "A馆东入口",
          dataIds: {
            title: "exhibition.setup.taskName",
            time: ["exhibition.setup.startTime", "exhibition.setup.endTime"],
            location: "exhibition.setup.locationText"
          }
        }]}
      />
    </Stack>
  </Stack>
  <Stack direction="column" flex={0} width={144} height={136} gap={8}>
    <Stack direction="column" flex={0} width={144} height={64}>
      <InfoBlock
        primaryText="12台设备"
        secondaryText="1台故障 ｜ 已巡检"
        dataIds={{
          primaryText: "exhibition.device.countText",
          secondaryText: ["exhibition.device.faultText", "exhibition.device.inspectionStatus"]
        }}
      />
    </Stack>
    <Stack direction="column" flex={0} width={144} height={64}>
      <CardButton text="联系负责人" actionId="exhibition.manager.contact" />
    </Stack>
  </Stack>
</Card>`,
  "coverage": [
    { "requirement": "展示展会布置任务名、时间范围、场馆和入口" },
    { "requirement": "展示设备数量、故障情况和巡检状态" },
    { "requirement": "提供联系现场负责人操作" }
  ],
  "unmetRequirements": []
})
```

## 示例四：四个固定模块，其中信息槽表达复合信息组

### 输入

```json
{
  "userQuery": "做张咖啡店运营卡片，看当前顾客数、排队情况和空位，也看待取订单、低库存情况和下批到货时间，并能打开收银和查看补货。",
  "size": "2x4",
  "actions": [
    { "id": "cafe.cashier.open", "description": "打开收银" },
    { "id": "cafe.stock.viewRestock", "description": "查看补货" }
  ],
  "data": [
    { "id": "cafe.customer.currentText", "type": "string", "description": "店内当前顾客数。", "value": "28位顾客" },
    { "id": "cafe.customer.queueText", "type": "string", "description": "当前排队情况。", "value": "排队4人" },
    { "id": "cafe.customer.seatText", "type": "string", "description": "当前空位情况。", "value": "空位12个" },
    { "id": "cafe.order.pendingText", "type": "string", "description": "当前待取订单数量。", "value": "6单待取" },
    { "id": "cafe.stock.lowText", "type": "string", "description": "当前低库存情况。", "value": "低库存3项" },
    { "id": "cafe.stock.nextArrivalText", "type": "string", "description": "下一批物料到货时间。", "value": "16:30到货" }
  ],
  "assetCandidates": []
}
```

### 信息分区（不输出）

- 顾客数、排队情况和空位组成一个“客流”信息模块；待取订单、低库存和到货时间组成一个“订单与库存”信息模块。
- 两个模块分别压缩为一个 `InfoBlock`，每个 InfoBlock 都绑定三个字段，而不是把六个字段拆成六个槽位。
- 两个信息模块与两个真实 Action 共同形成四个同级固定模块。左列放两个 InfoBlock，右列放两个 CardButton，选择“四槽宫格”。

### `submit_card_plan`

```js
submit_card_plan({
  "info_required": [
    {
      "requirement": "店内当前顾客数。",
      "dataId": "cafe.customer.currentText"
    },
    {
      "requirement": "当前排队情况。",
      "dataId": "cafe.customer.queueText"
    },
    {
      "requirement": "当前空位情况。",
      "dataId": "cafe.customer.seatText"
    },
    {
      "requirement": "当前待取订单数量。",
      "dataId": "cafe.order.pendingText"
    },
    {
      "requirement": "当前低库存情况。",
      "dataId": "cafe.stock.lowText"
    },
    {
      "requirement": "下一批物料到货时间。",
      "dataId": "cafe.stock.nextArrivalText"
    },
    {
      "requirement": "打开收银",
      "actionId": "cafe.cashier.open"
    },
    {
      "requirement": "查看补货",
      "actionId": "cafe.stock.viewRestock"
    }
  ],
  "layout_optionA": {
    "layoutPattern": "四槽宫格",
    "subPattern": {},
    "content": "左列上下为两个复合 InfoBlock，每个承载三个相关字段；右列上下为打开收银和查看补货两个 CardButton。"
  }
})
```

### `submit_card_jsx`

```js
submit_card_jsx({
  "decision": { "layoutPattern": "四槽宫格", "subPattern": {} },
  "jsx": `<Card direction="row" size="2x4" appearance="solid-cyan" gap={8}>
  <Stack direction="column" flex={0} width={144} height={136} gap={8}>
    <Stack direction="column" flex={0} width={144} height={64}>
      <InfoBlock
        primaryText="28位顾客"
        secondaryText="排队4人 ｜ 空位12个"
        dataIds={{
          primaryText: "cafe.customer.currentText",
          secondaryText: ["cafe.customer.queueText", "cafe.customer.seatText"]
        }}
      />
    </Stack>
    <Stack direction="column" flex={0} width={144} height={64}>
      <InfoBlock
        primaryText="6单待取"
        secondaryText="低库存3项 ｜ 16:30到货"
        dataIds={{
          primaryText: "cafe.order.pendingText",
          secondaryText: ["cafe.stock.lowText", "cafe.stock.nextArrivalText"]
        }}
      />
    </Stack>
  </Stack>
  <Stack direction="column" flex={0} width={144} height={136} gap={8}>
    <Stack direction="column" flex={0} width={144} height={64}>
      <CardButton text="打开收银" actionId="cafe.cashier.open" />
    </Stack>
    <Stack direction="column" flex={0} width={144} height={64}>
      <CardButton text="查看补货" actionId="cafe.stock.viewRestock" />
    </Stack>
  </Stack>
</Card>`,
  "coverage": [
    { "requirement": "展示当前顾客数、排队情况和空位" },
    { "requirement": "展示待取订单、低库存情况和下批到货时间" },
    { "requirement": "提供打开收银和查看补货操作" }
  ],
  "unmetRequirements": []
})
```
