```cardspec
{
  "title": "TRE-028 测试卡片",
  "description": "DateOverview的必需日期参数允许updatedAt作为来源，验证多源参数字段Token。",
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
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["header","dateContent","syncInfo"],"styles":{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFFFE9DE",0],["#FFFFFCF8",1]]},"justifyContent":"spaceBetween","alignItems":"center"}},{"id":"header","component":"Row","children":["title","dateIcon"],"styles":{"width":136,"height":20,"justifyContent":"spaceBetween","alignItems":"center"}},{"id":"title","component":"Text","content":"日期","styles":{"width":104,"height":20,"fontSize":12,"fontWeight":600,"fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}},{"id":"dateIcon","component":"Text","content":"📅","styles":{"width":20,"height":20,"fontSize":12,"fontWeight":600,"fontColor":"#FFE56A3A","maxLines":1,"textAlign":"center","textOverflow":"clip"}},{"id":"dateContent","component":"Column","children":["dateValue","dateLabel"],"itemMargin":4,"styles":{"width":136,"height":64,"justifyContent":"center","alignItems":"start"}},{"id":"dateValue","component":"Text","content":"{{ ${/data/calendar/events/0/startDate} }}","styles":{"width":136,"height":44,"fontSize":40,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textAlign":"start","textOverflow":"clip"}},{"id":"dateLabel","component":"Text","content":"下次日程","styles":{"width":136,"height":16,"fontSize":12,"fontWeight":500,"fontColor":"#99000000","maxLines":1,"textAlign":"start","textOverflow":"clip"}},{"id":"syncInfo","component":"Text","content":"{{ '上次同步 ' + ${/data/calendar/updatedAt} }}","styles":{"width":136,"height":16,"fontSize":10,"fontWeight":400,"fontColor":"#66000000","maxLines":1,"textAlign":"start","textOverflow":"clip"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"calendar":{"events":[{"startDate":"08-06"}],"updatedAt":"2026-08-06 09:00"}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "做日期卡，显示上次同步时间",
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
  "artifactId": "6abba01d-b46a-4ed0-9984-f0fb8115c09d",
  "createdAt": 1787203182927
}
```
```designcompactdsl
["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFFFE9DE",0],["#FFFFFCF8",1]]},"justifyContent":"spaceBetween","alignItems":"center"},["header","dateContent","syncInfo"]]
["header","Row",{"width":136,"height":20,"justifyContent":"spaceBetween","alignItems":"center"},["title","dateIcon"]]
["title","Text",{"width":104,"height":20,"fontSize":12,"fontWeight":600,"fontColor":"#99000000","maxLines":1,"content":"日期"}]
["dateIcon","Text",{"width":20,"height":20,"fontSize":12,"fontWeight":600,"fontColor":"#FFE56A3A","maxLines":1,"textAlign":"center","content":"📅"}]
["dateContent","Column",{"width":136,"height":64,"justifyContent":"center","alignItems":"start","itemMargin":4},["dateValue","dateLabel"]]
["dateValue","Text",{"width":136,"height":44,"fontSize":40,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textAlign":"start","content":"{{ ${/data/calendar/events/0/startDate} }}"}]
["dateLabel","Text",{"width":136,"height":16,"fontSize":12,"fontWeight":500,"fontColor":"#99000000","maxLines":1,"textAlign":"start","content":"下次日程"}]
["syncInfo","Text",{"width":136,"height":16,"fontSize":10,"fontWeight":400,"fontColor":"#66000000","maxLines":1,"textAlign":"start","content":"{{ '上次同步 ' + ${/data/calendar/updatedAt} }}"}]
["/data/calendar/events/0/startDate","08-06"]
["/data/calendar/updatedAt","2026-08-06 09:00"]
```
