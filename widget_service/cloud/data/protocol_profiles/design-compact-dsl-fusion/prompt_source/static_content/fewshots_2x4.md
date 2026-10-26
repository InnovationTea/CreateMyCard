# 静态 2x4 完整参考

案例仅用于结构，不提供本轮事实。所有业务文字及动作必须来自当前输入与已接受Plan。

## 2x4-V91

```json
{"userQuery":"示例剧场周末开放安排：周六09:00–17:00，最晚16:30入场，请携带有效证件。","size":"2x4","dataModelSchema":{"data":{}},"eventCandidates":[],"assetCandidates":[]}
```

```genui
["root","Layout",{"layout":"W-static-content"},["body"]]
["body","ContentBlock",{"title":"示例剧场周末开放安排","body":"周六09:00–17:00","attributes":[{"label":"最晚入场","value":"16:30"},{"label":"须知","value":"请携带有效证件"}]}]
["/state/ready",true]
```

## 2x4-V92

```json
{"userQuery":"周末行程：Day1示例公园，建议2小时，免费；Day2示例展馆，建议1小时，20元。","size":"2x4","dataModelSchema":{"data":{}},"eventCandidates":[],"assetCandidates":[]}
```

```genui
["root","Layout",{"layout":"W-static-content"},["body"]]
["body","RecordList",{"items":[{"leading":"Day1","title":"示例公园","description":"建议2小时","trailing":"免费"},{"leading":"Day2","title":"示例展馆","description":"建议1小时","trailing":"20元"}],"variant":"plain"}]
["/state/ready",true]
```

## 2x4-V93

```json
{"userQuery":"展示三场演出：示例乐队，示例剧场，周五；示例合唱，示例礼堂，周六；示例独奏，示例音乐厅，周日。","size":"2x4","dataModelSchema":{"data":{}},"eventCandidates":[],"assetCandidates":[]}
```

```genui
["root","Layout",{"layout":"W-static-content"},["body"]]
["body","RecordList",{"items":[{"title":"示例乐队","description":"示例剧场","trailing":"周五"},{"title":"示例合唱","description":"示例礼堂","trailing":"周六"},{"title":"示例独奏","description":"示例音乐厅","trailing":"周日"}],"variant":"plain"}]
["/state/ready",true]
```

## 2x4-V94

```json
{"userQuery":"对比方案：甲方案128元/月，含30GB；乙方案159元/月，含60GB。","size":"2x4","dataModelSchema":{"data":{}},"eventCandidates":[],"assetCandidates":[]}
```

```genui
["root","Layout",{"layout":"W-static-content"},["body"]]
["body","ComparisonGroup",{"items":[{"primaryText":"128元/月","secondaryText":"甲方案","details":["30GB"]},{"primaryText":"159元/月","secondaryText":"乙方案","details":["60GB"]}]}]
["/state/ready",true]
```

## 2x4-V95

```json
{"userQuery":"横向对比：甲128元/月，乙159元/月，丙199元/月；价格仅供本次参考。","size":"2x4","dataModelSchema":{"data":{}},"eventCandidates":[],"assetCandidates":[]}
```

```genui
["root","Layout",{"layout":"W-static-content"},["body","note"]]
["body","ComparisonGroup",{"items":[{"primaryText":"128元/月","secondaryText":"甲"},{"primaryText":"159元/月","secondaryText":"乙"},{"primaryText":"199元/月","secondaryText":"丙"}]}]
["note","SecondaryBody",{"items":[{"value":"价格仅供本次参考","maxLines":2}],"columns":1,"fontSize":12}]
["/state/ready",true]
```

## 2x4-V96

```json
{"userQuery":"阅读计划：读完示例书第一章，记录三个问题。","size":"2x4","dataModelSchema":{"data":{}},"eventCandidates":[],"assetCandidates":[]}
```

```genui
["root","Layout",{"layout":"W-static-content","variant":"bottom-content"},["header","body"]]
["header","SingleLineTitle",{"title":"阅读计划","fontSize":12}]
["body","ContentBlock",{"title":"示例书第一章","body":"记录三个问题"}]
["/state/ready",true]
```

## 2x4-V97

```json
{"userQuery":"出发备忘分两组：随身带证件，背包带雨伞；提供打开日历按钮。","size":"2x4","dataModelSchema":{"data":{}},"eventCandidates":[{"id":"event.open.calendar","call":"clickToDeeplink","args":{"uri":"hww://calendar"}}],"assetCandidates":[]}
```

```genui
["root","Layout",{"layout":"W-split-panels"},["left","right"]]
["left","Region",{"variant":"title-content-action"},["title","content","action"]]
["title","SingleLineTitle",{"title":"随身","fontSize":12}]
["content","ContentBlock",{"body":"带证件"}]
["action","PillButton",{"label":"打开日历","onClick":[{"call":"clickToDeeplink","args":{"uri":"hww://calendar"}}]}]
["right","Region",{"variant":"title-content"},["right_title","right_content"]]
["right_title","SingleLineTitle",{"title":"背包","fontSize":12}]
["right_content","ContentBlock",{"body":"带雨伞"}]
["/state/ready",true]
```

## 2x4-V98

```json
{"userQuery":"公积金贷款利率表：首套5年以上2.85%，首套5年以下含5年2.35%，二套5年以上3.325%，二套5年以下含5年2.775%。","size":"2x4","dataModelSchema":{"data":{}},"eventCandidates":[],"assetCandidates":[]}
```

```genui
["root","Layout",{"layout":"W-static-content"},["body"]]
["body","ContentBlock",{"title":"公积金贷款利率表","attributes":[{"label":"首套5年以上","value":"2.85%"},{"label":"首套5年以下含5年","value":"2.35%"},{"label":"二套5年以上","value":"3.325%"},{"label":"二套5年以下含5年","value":"2.775%"}]}]
["/state/ready",true]
```
