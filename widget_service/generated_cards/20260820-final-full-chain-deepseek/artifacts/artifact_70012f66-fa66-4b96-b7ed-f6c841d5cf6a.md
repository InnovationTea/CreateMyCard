```cardspec
{
  "title": "TRE-025 测试卡片",
  "description": "同能力但日期和会议属于不同模板，不得错误挑一个而遗漏另一项。",
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
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["dateHeader","nextMeeting"],"styles":{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFFFE9DE",0],["#FFFFFCF8",1]]},"justifyContent":"spaceBetween","alignItems":"center"}},{"id":"dateHeader","component":"Column","children":["dateTitle","dateValue"],"itemMargin":2,"styles":{"width":136,"height":48,"justifyContent":"center","alignItems":"start"}},{"id":"dateTitle","component":"Text","content":"今天","styles":{"width":136,"height":14,"fontSize":10,"fontWeight":500,"fontColor":"#99000000","maxLines":1,"textAlign":"start","textOverflow":"clip"}},{"id":"dateValue","component":"Text","content":"{{ ${/data/calendar/events/0/startDate} }}","styles":{"width":136,"height":32,"fontSize":32,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textAlign":"start","textOverflow":"clip"}},{"id":"nextMeeting","component":"Column","children":["meetingTitle","meetingTime"],"itemMargin":4,"styles":{"width":136,"height":76,"padding":{"top":8,"right":8,"bottom":8,"left":8},"borderRadius":12,"backgroundColor":"#FFFFF5EF","justifyContent":"center","alignItems":"start"}},{"id":"meetingTitle","component":"Text","content":"{{ ${/data/calendar/events/0/title} }}","styles":{"width":120,"height":16,"fontSize":12,"fontWeight":600,"fontColor":"#E5000000","maxLines":1,"textOverflow":"clip"}},{"id":"meetingTime","component":"Text","content":"{{ ${/data/calendar/events/0/dtStart} + '-' + ${/data/calendar/events/0/dtEnd} }}","styles":{"width":120,"height":14,"fontSize":10,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"calendar":{"events":[{"startDate":"08-06","title":"项目例会","dtStart":"14:00","dtEnd":"15:00"}]}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "帮我做一个今天日期和下个会议都展示的卡",
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
            },
            "title": {
              "type": "string",
              "description": "日程标题，例如“咪咕视频《西班牙 VS 奥地利》”或航班、车次信息。",
              "sampleValue": "项目例会"
            },
            "dtStart": {
              "type": "string",
              "description": "格式化后的日程开始时间短文本，如 '03:00'，若为全天日程可能为特殊标记。",
              "sampleValue": "14:00"
            },
            "dtEnd": {
              "type": "string",
              "description": "格式化后的日程结束时间短文本，如 '05:00'。",
              "sampleValue": "15:00"
            }
          }
        ]
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
        "/events/0/title",
        "/events/0/dtStart",
        "/events/0/dtEnd"
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
  "artifactId": "70012f66-fa66-4b96-b7ed-f6c841d5cf6a",
  "createdAt": 1787203173380
}
```
```designcompactdsl
["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFFFE9DE",0],["#FFFFFCF8",1]]},"justifyContent":"spaceBetween","alignItems":"center"},["dateHeader","nextMeeting"]]
["dateHeader","Column",{"width":136,"height":48,"justifyContent":"center","alignItems":"start","itemMargin":2},["dateTitle","dateValue"]]
["dateTitle","Text",{"width":136,"height":14,"fontSize":10,"fontWeight":500,"fontColor":"#99000000","maxLines":1,"textAlign":"start","content":"今天"}]
["dateValue","Text",{"width":136,"height":32,"fontSize":32,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textAlign":"start","content":"{{ ${/data/calendar/events/0/startDate} }}"}]
["nextMeeting","Column",{"width":136,"height":76,"padding":{"top":8,"right":8,"bottom":8,"left":8},"borderRadius":12,"backgroundColor":"#FFFFF5EF","justifyContent":"center","alignItems":"start","itemMargin":4},["meetingTitle","meetingTime"]]
["meetingTitle","Text",{"width":120,"height":16,"fontSize":12,"fontWeight":600,"fontColor":"#E5000000","maxLines":1,"content":"{{ ${/data/calendar/events/0/title} }}"}]
["meetingTime","Text",{"width":120,"height":14,"fontSize":10,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"content":"{{ ${/data/calendar/events/0/dtStart} + '-' + ${/data/calendar/events/0/dtEnd} }}"}]
["/data/calendar/events/0/startDate","08-06"]
["/data/calendar/events/0/title","项目例会"]
["/data/calendar/events/0/dtStart","14:00"]
["/data/calendar/events/0/dtEnd","15:00"]
```
