```cardspec
{
  "title": "TRE-089 测试卡片",
  "description": "不得只返回日程或耳机而遗漏另一强诉求。",
  "suggestSize": "2x2",
  "dataBindings": [
    {
      "capabilityId": "GetCalendarEvents",
      "arguments": {},
      "writeResultTo": "/data/calendar"
    },
    {
      "capabilityId": "GetEarphoneInfo",
      "arguments": {},
      "writeResultTo": "/data/earphone"
    }
  ]
}
```
```genui
{"version":"v0.9","createSurface":{"surfaceId":"surface_card","catalogId":"ohos.a2ui.extended.catalog.form"}}
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["header","contentArea"],"styles":{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFE2F6EE",0],["#FFF8FCFA",1]]},"justifyContent":"spaceBetween","alignItems":"center"}},{"id":"header","component":"Row","children":["title","statusIcon"],"styles":{"width":136,"height":20,"justifyContent":"spaceBetween","alignItems":"center"}},{"id":"title","component":"Text","content":"日程与耳机","styles":{"width":104,"height":20,"fontSize":12,"fontWeight":600,"fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}},{"id":"statusIcon","component":"Text","content":"●","styles":{"width":20,"height":20,"fontSize":12,"fontWeight":600,"fontColor":"#FF0F8F78","maxLines":1,"textAlign":"center","textOverflow":"clip"}},{"id":"contentArea","component":"Column","children":["eventPanel","earphonePanel"],"styles":{"width":136,"height":108,"justifyContent":"spaceBetween","alignItems":"start"}},{"id":"eventPanel","component":"Column","children":["eventLabel","eventTitle"],"itemMargin":4,"styles":{"width":136,"height":52,"padding":{"top":8,"right":8,"bottom":8,"left":8},"borderRadius":10,"backgroundColor":"#FFE1F4ED","justifyContent":"center","alignItems":"start"}},{"id":"eventLabel","component":"Text","content":"下一日程","styles":{"width":120,"height":14,"fontSize":10,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}},{"id":"eventTitle","component":"Text","content":"{{ ${/data/calendar/events/0/title} }}","styles":{"width":120,"height":16,"fontSize":12,"fontWeight":600,"fontColor":"#E5000000","maxLines":1,"textOverflow":"clip"}},{"id":"earphonePanel","component":"Column","children":["earphoneLabel","earphoneName"],"itemMargin":4,"styles":{"width":136,"height":52,"padding":{"top":8,"right":8,"bottom":8,"left":8},"borderRadius":10,"backgroundColor":"#FFE1F4ED","justifyContent":"center","alignItems":"start"}},{"id":"earphoneLabel","component":"Text","content":"耳机状态","styles":{"width":120,"height":14,"fontSize":10,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}},{"id":"earphoneName","component":"Text","content":"{{ ${/data/earphone/earphoneName} }}","styles":{"width":120,"height":16,"fontSize":12,"fontWeight":600,"fontColor":"#E5000000","maxLines":1,"textOverflow":"clip"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"calendar":{"events":[{"title":"项目例会"}]},"earphone":{"isConnected":true,"earphoneName":"示例耳机"}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "做一张日程和耳机状态都展示的卡",
  "size": "2x2",
  "eventCandidates": [],
  "dataModelSchema": {
    "data": {
      "calendar": {
        "events": [
          {
            "title": {
              "type": "string",
              "description": "日程标题，例如“咪咕视频《西班牙 VS 奥地利》”或航班、车次信息。",
              "sampleValue": "项目例会"
            }
          }
        ]
      },
      "earphone": {
        "isConnected": {
          "type": "boolean",
          "description": "当前是否有蓝牙耳机处于连接活跃状态。",
          "sampleValue": true
        },
        "earphoneName": {
          "type": "string",
          "description": "耳机的设备广播名称，如果未连接则返回'未连接耳机'。如: 'FreeBuds Pro 3'。",
          "sampleValue": "示例耳机"
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
    "GetCalendarEvents",
    "GetEarphoneInfo"
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
        "/events/0/title"
      ]
    },
    {
      "capabilityId": "GetEarphoneInfo",
      "arguments": {},
      "writeResultTo": "/data/earphone",
      "candidateOutputFields": [
        "/isConnected",
        "/earphoneName"
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
  "artifactId": "5af5701f-9bf6-4b9e-9da8-0e7db78e2e15",
  "createdAt": 1787203340198
}
```
```designcompactdsl
["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFE2F6EE",0],["#FFF8FCFA",1]]},"justifyContent":"spaceBetween","alignItems":"center"},["header","contentArea"]]
["header","Row",{"width":136,"height":20,"justifyContent":"spaceBetween","alignItems":"center"},["title","statusIcon"]]
["title","Text",{"width":104,"height":20,"fontSize":12,"fontWeight":600,"fontColor":"#99000000","maxLines":1,"content":"日程与耳机"}]
["statusIcon","Text",{"width":20,"height":20,"fontSize":12,"fontWeight":600,"fontColor":"#FF0F8F78","maxLines":1,"textAlign":"center","content":"●"}]
["contentArea","Column",{"width":136,"height":108,"justifyContent":"spaceBetween","alignItems":"start"},["eventPanel","earphonePanel"]]
["eventPanel","Column",{"width":136,"height":52,"padding":{"top":8,"right":8,"bottom":8,"left":8},"borderRadius":10,"backgroundColor":"#FFE1F4ED","justifyContent":"center","alignItems":"start","itemMargin":4},["eventLabel","eventTitle"]]
["eventLabel","Text",{"width":120,"height":14,"fontSize":10,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"content":"下一日程"}]
["eventTitle","Text",{"width":120,"height":16,"fontSize":12,"fontWeight":600,"fontColor":"#E5000000","maxLines":1,"content":"{{ ${/data/calendar/events/0/title} }}"}]
["earphonePanel","Column",{"width":136,"height":52,"padding":{"top":8,"right":8,"bottom":8,"left":8},"borderRadius":10,"backgroundColor":"#FFE1F4ED","justifyContent":"center","alignItems":"start","itemMargin":4},["earphoneLabel","earphoneName"]]
["earphoneLabel","Text",{"width":120,"height":14,"fontSize":10,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"content":"耳机状态"}]
["earphoneName","Text",{"width":120,"height":16,"fontSize":12,"fontWeight":600,"fontColor":"#E5000000","maxLines":1,"content":"{{ ${/data/earphone/earphoneName} }}"}]
["/data/calendar/events/0/title","项目例会"]
["/data/earphone/isConnected",true]
["/data/earphone/earphoneName","示例耳机"]
```
