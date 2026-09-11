# 2×4 端到端示例

这些示例只演示如何把信息关系闭合为当前工具参数和布局，不是可复用的业务答案。

- 示例中的实体、字段 ID、数值、文案和 Action 均为虚构；实际生成只能使用当前输入。
- “信息分区”是生成时需要考虑的简短结论，不要求额外输出。
- `submit_card_plan` 和 `submit_card_jsx` 必须遵守当前工具 Schema；若示例与组件或布局合同冲突，以合同为准。
- 不要因为当前任务与示例领域相似就复制组件、标题或布局；应根据当前信息数量、分区关系、Action 归属和真实占位重新选择。

## 示例一：一个主题的汇总与同级明细

### 输入

```json
{
  "userQuery": "展示本周家庭总用水量，以及洗浴、厨房和洗衣分别用了多少水。",
  "size": "2x4",
  "actions": [],
  "data": [
    { "id": "homeWater.week.totalText", "type": "string", "description": "本周家庭总用水量。", "value": "418升" },
    { "id": "homeWater.week.bathText", "type": "string", "description": "本周洗浴用水量。", "value": "170升" },
    { "id": "homeWater.week.kitchenText", "type": "string", "description": "本周厨房用水量。", "value": "96升" },
    { "id": "homeWater.week.laundryText", "type": "string", "description": "本周洗衣用水量。", "value": "152升" }
  ],
  "assetCandidates": []
}
```

### 信息分区（不输出）

- 只有“本周家庭用水”一个信息分区。
- 总用水量是汇总；洗浴、厨房、洗衣是构成它的三个同级明细。
- 输入 `actions` 为空，`userQuery` 也没有要求任何按钮或操作，因此允许考虑不支持 Action 的“上下双区”。
- 汇总使用一个突出数值组件，三个明细合并为一个 `TextBlock`，选择“上下双区”。

### `submit_card_plan`

```js
submit_card_plan({
  "info_required": "家庭总用水 homeWater.week.totalText；洗浴 homeWater.week.bathText、厨房 homeWater.week.kitchenText、洗衣 homeWater.week.laundryText。总量为汇总，三项为同级明细；无 Action。",
  "layout_optionA": {
    "layoutPattern": "上下双区",
    "subPattern": {},
    "content": "标题下以上区 EmphasizedData 突出总用水量，下区用一个 TextBlock 并列三项构成明细。"
  }
})
```

### `submit_card_jsx`

```js
submit_card_jsx({
  "decision": { "layoutPattern": "上下双区", "subPattern": {} },
  "jsx": `<Card direction="column" size="2x4" appearance="solid-blue" gap={4}>
  <Stack direction="column" flex={0} width="full" height={20}>
    <SingleLineTitle title="本周家庭用水" />
  </Stack>
  <Stack direction="column" flex={1} width="full" gap={8} justify="space-between">
    <Stack direction="column" flex={0} width="full">
      <EmphasizedData value="418升" dataIds={{ value: "homeWater.week.totalText" }} />
    </Stack>
    <Stack direction="column" flex={0} width="full">
      <TextBlock items={[
        { label: "洗浴", parameter: "170升", dataIds: { parameter: "homeWater.week.bathText" } },
        { label: "厨房", parameter: "96升", dataIds: { parameter: "homeWater.week.kitchenText" } },
        { label: "洗衣", parameter: "152升", dataIds: { parameter: "homeWater.week.laundryText" } }
      ]} />
    </Stack>
  </Stack>
</Card>`,
  "coverage": [
    { "requirement": "展示本周家庭总用水量" },
    { "requirement": "展示洗浴、厨房和洗衣用水量" }
  ],
  "unmetRequirements": []
})
```

## 示例二：两个独立分区，各自带一个操作

### 输入

```json
{
  "userQuery": "做张家务卡片，左边看洗衣还剩多久并能暂停，右边看烘干进度并能延长烘干。",
  "size": "2x4",
  "actions": [
    { "id": "laundry.washer.pause", "description": "暂停洗衣" },
    { "id": "laundry.dryer.extend", "description": "延长烘干" }
  ],
  "data": [
    { "id": "laundry.washer.remainingText", "type": "string", "description": "洗衣剩余时间。", "value": "18分钟" },
    { "id": "laundry.dryer.progressText", "type": "string", "description": "烘干完成进度。", "value": "72%" }
  ],
  "assetCandidates": []
}
```

### 信息分区（不输出）

- “洗衣剩余时间 + 暂停洗衣”是一个完整分区；“烘干进度 + 延长烘干”是另一个完整分区。
- 两个 Action 分别直属不同分区，不应抽到同一个按钮列。
- 两侧都能使用“标题 + 单内容 + PillButton”，选择“左右双区”的两个 `Sub-118-D`。

### `submit_card_plan`

```js
submit_card_plan({
  "info_required": "洗衣剩余时间 laundry.washer.remainingText 与暂停洗衣 laundry.washer.pause 同组；烘干进度 laundry.dryer.progressText 与延长烘干 laundry.dryer.extend 同组。两个分区和两个 Action 都必须保留。",
  "layout_optionA": {
    "layoutPattern": "左右双区",
    "subPattern": {
      "left": "Sub-118-D 标题内容单按钮",
      "right": "Sub-118-D 标题内容单按钮"
    },
    "content": "左右各用一个背板分区；每侧以 EmphasisText 展示本组状态，并在底部放置直属的 PillButton。"
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
        <SingleLineTitle title="洗衣" />
      </Stack>
      <Stack direction="column" flex={1} width={118}>
        <EmphasisText mainText="18分钟" secondaryText="剩余时间" dataIds={{ mainText: "laundry.washer.remainingText" }} />
      </Stack>
      <Stack direction="column" flex={0} width={118} height={36}>
        <PillButton label="暂停洗衣" appearance="card" actionId="laundry.washer.pause" />
      </Stack>
    </Stack>
  </Stack>
  <Stack direction="column" surface="backplate" flex={0} width={142} height={136} align="center" justify="center">
    <Stack direction="column" flex={0} width={118} height={112} gap={6}>
      <Stack direction="column" flex={0} width={118}>
        <SingleLineTitle title="烘干" />
      </Stack>
      <Stack direction="column" flex={1} width={118}>
        <EmphasisText mainText="72%" secondaryText="完成进度" dataIds={{ mainText: "laundry.dryer.progressText" }} />
      </Stack>
      <Stack direction="column" flex={0} width={118} height={36}>
        <PillButton label="延长烘干" appearance="card" actionId="laundry.dryer.extend" />
      </Stack>
    </Stack>
  </Stack>
</Card>`,
  "coverage": [
    { "requirement": "展示洗衣剩余时间并提供暂停操作" },
    { "requirement": "展示烘干进度并提供延长烘干操作" }
  ],
  "unmetRequirements": []
})
```

## 示例三：完整内容区与右侧固定信息、操作槽

### 输入

```json
{
  "userQuery": "展示国际包裹的当前节点、预计送达时间和包裹件数，突出预计关税，并能联系承运商。",
  "size": "2x4",
  "actions": [
    { "id": "shipment.carrier.contact", "description": "联系承运商" }
  ],
  "data": [
    { "id": "shipment.route.currentHub", "type": "string", "description": "包裹当前所在转运节点。", "value": "北区转运中心" },
    { "id": "shipment.delivery.etaText", "type": "string", "description": "预计送达时间。", "value": "周五下午" },
    { "id": "shipment.package.count", "type": "integer", "description": "本次包裹件数。", "value": 3 },
    { "id": "shipment.customs.estimateText", "type": "string", "description": "预计需要支付的关税。", "value": "86元" }
  ],
  "assetCandidates": []
}
```

### 信息分区（不输出）

- 当前节点、预计送达和件数共同描述运输进程，放入左侧完整内容区。
- 预计关税是独立、紧凑且需要突出的属性；联系承运商是必须保留的操作。
- 右侧恰好形成“上 InfoBlock + 下 CardButton”，选择“左内容右侧双槽”。

### `submit_card_plan`

```js
submit_card_plan({
  "info_required": "运输进程：当前节点 shipment.route.currentHub、预计送达 shipment.delivery.etaText、件数 shipment.package.count；独立属性：关税 shipment.customs.estimateText；操作：联系承运商 shipment.carrier.contact。",
  "layout_optionA": {
    "layoutPattern": "左内容右侧双槽",
    "subPattern": { "content": "Sub-140-G 标题双内容" },
    "content": "左侧标题下用 EmphasisText 表达当前节点，并用 SecondaryBody 补充预计送达和件数；右上 InfoBlock 展示关税，右下 CardButton 保留联系操作。"
  }
})
```

### `submit_card_jsx`

```js
submit_card_jsx({
  "decision": {
    "layoutPattern": "左内容右侧双槽",
    "subPattern": { "content": "Sub-140-G 标题双内容" }
  },
  "jsx": `<Card direction="row" size="2x4" appearance="solid-purple" gap={12}>
  <Stack direction="column" flex={0} width={140} height={136} gap={8}>
    <Stack direction="column" flex={0} width={140}>
      <SingleLineTitle title="国际包裹" />
    </Stack>
    <Stack direction="column" flex={1} width={140} gap={8}>
      <Stack direction="column" flex={1} width={140} align="flex-start" justify="flex-start">
        <EmphasisText mainText="北区转运中心" secondaryText="当前节点" dataIds={{ mainText: "shipment.route.currentHub" }} />
      </Stack>
      <Stack direction="column" flex={0} width={140} align="flex-start" justify="flex-end">
        <SecondaryBody items={[
          { label: "预计送达", value: "周五下午", dataIds: { value: "shipment.delivery.etaText" } },
          { label: "包裹", value: 3, dataIds: { value: "shipment.package.count" } }
        ]} />
      </Stack>
    </Stack>
  </Stack>
  <Stack direction="column" flex={0} width={144} height={136} gap={8}>
    <Stack direction="column" flex={0} width={144} height={64}>
      <InfoBlock primaryText="86元" secondaryText="预计关税" dataIds={{ primaryText: "shipment.customs.estimateText" }} />
    </Stack>
    <Stack direction="column" flex={0} width={144} height={64}>
      <CardButton text="联系承运商" actionId="shipment.carrier.contact" />
    </Stack>
  </Stack>
</Card>`,
  "coverage": [
    { "requirement": "展示包裹当前节点、预计送达时间和件数" },
    { "requirement": "展示预计关税" },
    { "requirement": "提供联系承运商操作" }
  ],
  "unmetRequirements": []
})
```

## 示例四：四个同级固定模块

### 输入

```json
{
  "userQuery": "做张工作间卡片，查看二氧化碳和环境噪声，并能启动通风、关闭遮阳帘。",
  "size": "2x4",
  "actions": [
    { "id": "workspace.ventilation.start", "description": "启动通风" },
    { "id": "workspace.blind.close", "description": "关闭遮阳帘" }
  ],
  "data": [
    { "id": "workspace.air.co2Text", "type": "string", "description": "工作间当前二氧化碳浓度。", "value": "760ppm" },
    { "id": "workspace.noise.statusText", "type": "string", "description": "工作间当前噪声状态。", "value": "安静" }
  ],
  "assetCandidates": []
}
```

### 信息分区（不输出）

- 两项环境状态和两项环境控制共同服务“工作间环境”这一主题，是四个同级紧凑模块。
- 两个信息模块分别使用 `InfoBlock`，两个操作分别使用 `CardButton`；同类组件各占一列。
- 四个真实模块恰好填满固定槽，选择“四槽宫格”。

### `submit_card_plan`

```js
submit_card_plan({
  "info_required": "工作间环境信息：二氧化碳 workspace.air.co2Text、噪声 workspace.noise.statusText；操作：启动通风 workspace.ventilation.start、关闭遮阳帘 workspace.blind.close。四项均为同级有效模块。",
  "layout_optionA": {
    "layoutPattern": "四槽宫格",
    "subPattern": {},
    "content": "左列上下放两个 InfoBlock，右列上下放两个 CardButton；四槽全部填满，同一列不混用组件类型。"
  }
})
```

### `submit_card_jsx`

```js
submit_card_jsx({
  "decision": { "layoutPattern": "四槽宫格", "subPattern": {} },
  "jsx": `<Card direction="row" size="2x4" appearance="solid-blue" gap={8}>
  <Stack direction="column" flex={0} width={144} height={136} gap={8}>
    <Stack direction="column" flex={0} width={144} height={64}>
      <InfoBlock primaryText="760ppm" secondaryText="二氧化碳" dataIds={{ primaryText: "workspace.air.co2Text" }} />
    </Stack>
    <Stack direction="column" flex={0} width={144} height={64}>
      <InfoBlock primaryText="安静" secondaryText="环境噪声" dataIds={{ primaryText: "workspace.noise.statusText" }} />
    </Stack>
  </Stack>
  <Stack direction="column" flex={0} width={144} height={136} gap={8}>
    <Stack direction="column" flex={0} width={144} height={64}>
      <CardButton text="启动通风" actionId="workspace.ventilation.start" />
    </Stack>
    <Stack direction="column" flex={0} width={144} height={64}>
      <CardButton text="关闭遮阳帘" actionId="workspace.blind.close" />
    </Stack>
  </Stack>
</Card>`,
  "coverage": [
    { "requirement": "展示二氧化碳和环境噪声" },
    { "requirement": "提供启动通风和关闭遮阳帘操作" }
  ],
  "unmetRequirements": []
})
```
