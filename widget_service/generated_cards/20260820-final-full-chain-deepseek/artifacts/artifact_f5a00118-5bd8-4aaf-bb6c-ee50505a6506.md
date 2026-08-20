```cardspec
{
  "title": "TRE-051 测试卡片",
  "description": "充电状态虽是能力字段但没有进入耳机模板required集合。",
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
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["header","earphoneContent","chargingStatus"],"styles":{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFE2F6EE",0],["#FFF8FCFA",1]]},"justifyContent":"spaceBetween","alignItems":"center"}},{"id":"header","component":"Row","children":["title","connectionIcon"],"styles":{"width":136,"height":20,"justifyContent":"spaceBetween","alignItems":"center"}},{"id":"title","component":"Text","content":"耳机状态","styles":{"width":104,"height":20,"fontSize":12,"fontWeight":600,"fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}},{"id":"connectionIcon","component":"Text","content":"{{ ${/data/earphone/isConnected} ? '已连' : '未连' }}","styles":{"width":20,"height":20,"fontSize":12,"fontWeight":600,"fontColor":"#FF0F8F78","maxLines":1,"textAlign":"center","textOverflow":"clip"}},{"id":"earphoneContent","component":"Column","children":["earphoneName","earphoneState"],"itemMargin":2,"styles":{"width":136,"height":60,"justifyContent":"center","alignItems":"start"}},{"id":"earphoneName","component":"Text","content":"{{ ${/data/earphone/earphoneName} }}","styles":{"width":136,"height":44,"fontSize":32,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textAlign":"start","textOverflow":"clip"}},{"id":"earphoneState","component":"Text","content":"{{ ${/data/earphone/isConnected} ? '已连接' : '未连接' }}","styles":{"width":136,"height":14,"fontSize":12,"fontWeight":600,"fontColor":"#E5000000","maxLines":1,"textAlign":"start","textOverflow":"clip"}},{"id":"chargingStatus","component":"Text","content":"{{ '充电状态：' + ${/data/earphone/chargingStatusDesc} }}","styles":{"width":136,"height":16,"fontSize":12,"fontWeight":500,"fontColor":"#99000000","maxLines":1,"textAlign":"start","textOverflow":"clip"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"earphone":{"isConnected":true,"earphoneName":"示例耳机","chargingStatusDesc":"未充电"}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "耳机卡还要告诉我是否在充电",
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
        "chargingStatusDesc": {
          "type": "string",
          "description": "耳机盒（或整体）当前的充电状态中文语义描述，'充电中' 或 '未充电'。",
          "sampleValue": "未充电"
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
        "/chargingStatusDesc"
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
  "artifactId": "f5a00118-5bd8-4aaf-bb6c-ee50505a6506",
  "createdAt": 1787203246406
}
```
```designcompactdsl
["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFE2F6EE",0],["#FFF8FCFA",1]]},"justifyContent":"spaceBetween","alignItems":"center"},["header","earphoneContent","chargingStatus"]]
["header","Row",{"width":136,"height":20,"justifyContent":"spaceBetween","alignItems":"center"},["title","connectionIcon"]]
["title","Text",{"width":104,"height":20,"fontSize":12,"fontWeight":600,"fontColor":"#99000000","maxLines":1,"content":"耳机状态"}]
["connectionIcon","Text",{"width":20,"height":20,"fontSize":12,"fontWeight":600,"fontColor":"#FF0F8F78","maxLines":1,"textAlign":"center","content":"{{ ${/data/earphone/isConnected} ? '已连' : '未连' }}"}]
["earphoneContent","Column",{"width":136,"height":60,"justifyContent":"center","alignItems":"start","itemMargin":2},["earphoneName","earphoneState"]]
["earphoneName","Text",{"width":136,"height":44,"fontSize":32,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textAlign":"start","content":"{{ ${/data/earphone/earphoneName} }}"}]
["earphoneState","Text",{"width":136,"height":14,"fontSize":12,"fontWeight":600,"fontColor":"#E5000000","maxLines":1,"textAlign":"start","content":"{{ ${/data/earphone/isConnected} ? '已连接' : '未连接' }}"}]
["chargingStatus","Text",{"width":136,"height":16,"fontSize":12,"fontWeight":500,"fontColor":"#99000000","maxLines":1,"textAlign":"start","content":"{{ '充电状态：' + ${/data/earphone/chargingStatusDesc} }}"}]
["/data/earphone/isConnected",true]
["/data/earphone/earphoneName","示例耳机"]
["/data/earphone/chargingStatusDesc","未充电"]
```
