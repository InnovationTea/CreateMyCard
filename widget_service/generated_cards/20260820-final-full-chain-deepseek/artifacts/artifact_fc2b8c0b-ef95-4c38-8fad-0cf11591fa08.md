```cardspec
{
  "title": "TRE-047 测试卡片",
  "description": "总电量是用户强诉求，选择包含battery的最小hero Variant。",
  "suggestSize": "2x2",
  "dataBindings": [
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
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["header","batteryContent"],"styles":{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFE2F6EE",0],["#FFF8FCFA",1]]},"justifyContent":"spaceBetween","alignItems":"center"}},{"id":"header","component":"Row","children":["title","status"],"styles":{"width":136,"height":20,"justifyContent":"spaceBetween","alignItems":"center"}},{"id":"title","component":"Text","content":"{{ ${/data/earphone/earphoneName} }}","styles":{"width":104,"height":20,"fontSize":12,"fontWeight":600,"fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}},{"id":"status","component":"Text","content":"{{ ${/data/earphone/isConnected} ? '已连接' : '未连接' }}","styles":{"width":24,"height":20,"fontSize":12,"fontWeight":600,"fontColor":"#FF64BB5C","maxLines":1,"textAlign":"end","textOverflow":"clip"}},{"id":"batteryContent","component":"Column","children":["batteryValue","batteryLabel"],"itemMargin":4,"styles":{"width":136,"height":64,"justifyContent":"center","alignItems":"start"}},{"id":"batteryValue","component":"Text","content":"{{ ${/data/earphone/batteryLevel} + '%' }}","styles":{"width":136,"height":44,"fontSize":40,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textAlign":"start","textOverflow":"clip"}},{"id":"batteryLabel","component":"Text","content":"总电量","styles":{"width":136,"height":16,"fontSize":12,"fontWeight":500,"fontColor":"#99000000","maxLines":1,"textAlign":"start","textOverflow":"clip"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"earphone":{"isConnected":true,"earphoneName":"示例耳机","batteryLevel":80}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "给我一个低电量蓝牙耳机卡，显示总电量",
  "size": "2x2",
  "eventCandidates": [],
  "dataModelSchema": {
    "data": {
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
        },
        "batteryLevel": {
          "type": "integer",
          "description": "耳机盒（或整体）的当前电量百分比，取值范围 0-100。",
          "sampleValue": 80
        },
        "leftBatteryLevel": {
          "type": "integer",
          "description": "左耳机的当前电量百分比，取值范围 0-100。若未连接则为 0。",
          "sampleValue": 76
        },
        "rightBatteryLevel": {
          "type": "integer",
          "description": "右耳机的当前电量百分比，取值范围 0-100。若未连接则为 0。",
          "sampleValue": 78
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
      "capabilityId": "GetEarphoneInfo",
      "arguments": {},
      "writeResultTo": "/data/earphone",
      "candidateOutputFields": [
        "/isConnected",
        "/earphoneName",
        "/batteryLevel",
        "/leftBatteryLevel",
        "/rightBatteryLevel"
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
  "artifactId": "fc2b8c0b-ef95-4c38-8fad-0cf11591fa08",
  "createdAt": 1787203234756
}
```
```designcompactdsl
["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFE2F6EE",0],["#FFF8FCFA",1]]},"justifyContent":"spaceBetween","alignItems":"center"},["header","batteryContent"]]
["header","Row",{"width":136,"height":20,"justifyContent":"spaceBetween","alignItems":"center"},["title","status"]]
["title","Text",{"width":104,"height":20,"fontSize":12,"fontWeight":600,"fontColor":"#99000000","maxLines":1,"content":"{{ ${/data/earphone/earphoneName} }}"}]
["status","Text",{"width":24,"height":20,"fontSize":12,"fontWeight":600,"fontColor":"#FF64BB5C","maxLines":1,"textAlign":"end","content":"{{ ${/data/earphone/isConnected} ? '已连接' : '未连接' }}"}]
["batteryContent","Column",{"width":136,"height":64,"justifyContent":"center","alignItems":"start","itemMargin":4},["batteryValue","batteryLabel"]]
["batteryValue","Text",{"width":136,"height":44,"fontSize":40,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textAlign":"start","content":"{{ ${/data/earphone/batteryLevel} + '%' }}"}]
["batteryLabel","Text",{"width":136,"height":16,"fontSize":12,"fontWeight":500,"fontColor":"#99000000","maxLines":1,"textAlign":"start","content":"总电量"}]
["/data/earphone/isConnected",true]
["/data/earphone/earphoneName","示例耳机"]
["/data/earphone/batteryLevel",80]
```
