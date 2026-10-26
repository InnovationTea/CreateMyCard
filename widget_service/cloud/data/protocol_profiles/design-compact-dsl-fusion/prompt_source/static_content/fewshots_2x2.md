# 静态 2x2 完整参考

案例仅用于结构，不提供本轮事实。所有业务文字及动作必须来自当前输入与已接受Plan。

## 2x2-V91

```json
{"userQuery":"制作示例演出卡：周末音乐分享会，预计周六19:30，示例剧场。","size":"2x2","dataModelSchema":{"data":{}},"eventCandidates":[],"assetCandidates":[]}
```

```genui
["root","Layout",{"layout":"S-static-content"},["body"]]
["body","ContentBlock",{"title":"周末音乐分享会","body":"预计周六19:30","attributes":[{"label":"地点","value":"示例剧场"}]}]
["/state/ready",true]
```

## 2x2-V92

```json
{"userQuery":"制作备忘：出发前检查，证件和充电器随身携带。","size":"2x2","dataModelSchema":{"data":{}},"eventCandidates":[],"assetCandidates":[]}
```

```genui
["root","Layout",{"layout":"S-static-content"},["body"]]
["body","ContentBlock",{"title":"出发前检查","body":"证件和充电器随身携带"}]
["/state/ready",true]
```

## 2x2-V93

```json
{"userQuery":"展示两项行程：Day1游览示例公园，建议2小时，免费；Day2参观示例展馆，建议1小时，20元。","size":"2x2","dataModelSchema":{"data":{}},"eventCandidates":[],"assetCandidates":[]}
```

```genui
["root","Layout",{"layout":"S-static-content"},["body"]]
["body","RecordList",{"items":[{"title":"示例公园","description":"建议2小时 · 免费"},{"title":"示例展馆","description":"建议1小时 · 20元"}],"variant":"plain"}]
["/state/ready",true]
```

## 2x2-V94

```json
{"userQuery":"展示活动：阅读分享会，周六；摄影交流会，周日。","size":"2x2","dataModelSchema":{"data":{}},"eventCandidates":[],"assetCandidates":[]}
```

```genui
["root","Layout",{"layout":"S-static-content"},["body"]]
["body","RecordList",{"items":[{"title":"阅读分享会","description":"周六"},{"title":"摄影交流会","description":"周日"}],"variant":"panel"}]
["/state/ready",true]
```

## 2x2-V95

```json
{"userQuery":"完整备忘三项：带证件、带雨伞、带充电器。","size":"2x2","dataModelSchema":{"data":{}},"eventCandidates":[],"assetCandidates":[]}
```

```genui
["root","Layout",{"layout":"S-static-content"},["body"]]
["body","RecordList",{"items":[{"title":"带证件"},{"title":"带雨伞"},{"title":"带充电器"}],"variant":"plain"}]
["/state/ready",true]
```

## 2x2-V96

```json
{"userQuery":"出发备忘：带证件，并提供打开日历按钮。","size":"2x2","dataModelSchema":{"data":{}},"eventCandidates":[{"id":"event.open.calendar","call":"clickToDeeplink","args":{"uri":"hww://calendar"}}],"assetCandidates":[]}
```

```genui
["root","Layout",{"layout":"S-title-content-action"},["title","content","action"]]
["title","SingleLineTitle",{"title":"出发备忘","fontSize":12}]
["content","ContentBlock",{"body":"带证件"}]
["action","PillButton",{"label":"打开日历","onClick":[{"call":"clickToDeeplink","args":{"uri":"hww://calendar"}}]}]
["/state/ready",true]
```

## 2x2-V97

```json
{"userQuery":"上海博物馆自2008年3月10日起向社会免费开放。来源：维基百科。","size":"2x2","dataModelSchema":{"data":{}},"eventCandidates":[],"assetCandidates":[]}
```

```genui
["root","Layout",{"layout":"S-static-content"},["body","note"]]
["body","ContentBlock",{"title":"上海博物馆","body":"自2008年3月10日起向社会免费开放"}]
["note","SecondaryBody",{"items":[{"value":"来源：维基百科","maxLines":2}],"columns":1,"fontSize":12}]
["/state/ready",true]
```
