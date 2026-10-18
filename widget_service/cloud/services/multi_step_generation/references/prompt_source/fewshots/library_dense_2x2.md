---
name: phone-widget-fewshot-dense-2x2
description: 2×2 具有多个必要数据和操作的紧凑绑定案例，按需检索。
---

# 2×2 紧凑容量案例

## 示例 23：天气主状态与两个短属性

### 输入

```json
{"userQuery":"查看天气状态、气温和湿度，并打开详细天气。","size":"2x2","actions":[{"id":"weather.detail.open","description":"详细天气"}],"data":[{"id":"weather.condition","type":"string","value":"多云"},{"id":"weather.temperature","type":"string","value":"22℃"},{"id":"weather.humidity","type":"string","value":"40%"}],"assetCandidates":[]}
```

### 分析

3 个数据、1 个必要 Action；一个天气主题，主状态和两个很短的带标签属性由一个组件承载。按钮占固定底部槽，不额外增加文本组件。

### 提交

```js
submit_card_jsx({"jsx": `<Card size="2x2" appearance="solid-blue" layout="single"><Region slot="main" variant="wide-title-content-action"><SingleLineTitle title="天气" /><EmphasisText mainText="多云" secondaryText="温22℃ ｜ 湿40%" secondaryTextTemplate="温{0} ｜ 湿{1}" dataIds={{mainText:"weather.condition",secondaryText:["weather.temperature","weather.humidity"]}} /><PillButton appearance="card" label="详细天气" actionId="weather.detail.open" /></Region></Card>`,"coverage":[{"requirement":"展示天气状态、气温、湿度和详情操作"}],"unmetRequirements":[]})
```
