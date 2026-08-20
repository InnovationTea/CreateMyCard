```cardspec
{
  "title": "TRE-032 测试卡片",
  "description": "虽然存在support变体，检索只选hero，结果必须稳定为dateHero。",
  "suggestSize": "2x2",
  "dataBindings": [
    {
      "capabilityId": "GetCalendarEvents",
      "arguments": {},
      "writeResultTo": "/data/calendar"
    }
  ]
}
```
```genui
{"version":"v0.9","createSurface":{"surfaceId":"surface_card","catalogId":"ohos.a2ui.extended.catalog.form"}}
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["dateValue","dateLabel"],"styles":{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFFFE9DE",0],["#FFFFFCF8",1]]},"justifyContent":"center","alignItems":"center"}},{"id":"dateValue","component":"Text","content":"{{ ${/data/calendar/events/0/startDate} }}","styles":{"width":136,"height":56,"fontSize":40,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textAlign":"center","textOverflow":"clip"}},{"id":"dateLabel","component":"Text","content":"今天","styles":{"width":136,"height":20,"fontSize":12,"fontWeight":500,"fontColor":"#99000000","maxLines":1,"textAlign":"center","textOverflow":"clip"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"calendar":{"events":[{"startDate":"08-06"}]}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "做一个只显示今天日期的2x2卡",
  "size": "2x2",
  "eventCandidates": [],
  "dataModelSchema": {
    "data": {
      "calendar": {
        "events": [
          {
            "startDate": {
              "type": "string",
              "description": "日程开始日期格式化文本，例如 '07-03'。",
              "sampleValue": "08-06"
            }
          }
        ],
        "updatedAt": {
          "type": "string",
          "description": "端侧完成数据组装的时间戳字符串，格式如 '2026-07-03 15:30'。",
          "sampleValue": "2026-08-06 09:00"
        }
      }
    }
  },
  "assetCandidates": []
}
```
```effectivecapabilities
{
  "data": [
    "GetCalendarEvents"
  ],
  "event": [],
  "asset": []
}
```
```removedcapabilities
[]
```
```generationplan
{
  "candidateDataBindings": [
    {
      "capabilityId": "GetCalendarEvents",
      "arguments": {},
      "writeResultTo": "/data/calendar",
      "candidateOutputFields": [
        "/events/0/startDate",
        "/updatedAt"
      ]
    }
  ],
  "candidateEventCandidates": [],
  "candidateAssetIds": []
}
```
```meta
{
  "apiVersion": "v1",
  "taskSpecVersion": "task-spec-v1",
  "cardSpecVersion": "card-spec-v1",
  "dslProtocolVersion": "v0.9",
  "skillVersion": "skill-widget-v1",
  "protocolProfileId": "a2ui-form-rom6.0-v1",
  "capabilityRegistryVersion": "app-11.7.5.205_rom-6.0",
  "artifactSchemaVersion": "widget-artifact-v2",
  "generationMode": "create",
  "artifactId": "bb2f4526-acfc-4ee5-bd8c-3aa4c7474d02",
  "createdAt": 1787203192395
}
```
```designcompactdsl
["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFFFE9DE",0],["#FFFFFCF8",1]]},"justifyContent":"center","alignItems":"center"},["dateValue","dateLabel"]]
["dateValue","Text",{"width":136,"height":56,"fontSize":40,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textAlign":"center","content":"{{ ${/data/calendar/events/0/startDate} }}"}]
["dateLabel","Text",{"width":136,"height":20,"fontSize":12,"fontWeight":500,"fontColor":"#99000000","maxLines":1,"textAlign":"center","content":"今天"}]
["/data/calendar/events/0/startDate","08-06"]
```
