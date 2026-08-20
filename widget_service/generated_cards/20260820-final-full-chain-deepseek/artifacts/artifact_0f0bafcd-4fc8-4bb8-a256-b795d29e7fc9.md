```cardspec
{
  "title": "TRE-049 测试卡片",
  "description": "完整耳机字段集合需要full wide Variant。",
  "suggestSize": "2x4",
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
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["root_0"],"itemMargin":8,"styles":{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"backgroundColor":"#FFFFFFFF","linearGradient":{"direction":"RightBottom","colors":[["#1A64BB5C",0],["#00FFFFFF",1]]},"alignItems":"start"}},{"id":"root_0","component":"Column","children":["root_0_0"],"itemMargin":4,"styles":{"width":"matchParent","height":"matchParent","justifyContent":"start","alignItems":"start","clip":true}},{"id":"root_0_0","component":"Column","children":["root_0_0_0","root_0_0_1","root_0_0_2"],"itemMargin":4,"styles":{"width":"matchParent","height":"matchParent","justifyContent":"spaceBetween","alignItems":"start","clip":true,"constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_0","component":"Row","children":["root_0_0_0_0"],"itemMargin":4,"styles":{"width":"matchParent","justifyContent":"spaceBetween","alignItems":"top","height":20,"constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_0_0","component":"Text","content":"{{ ${/data/earphone/isConnected} ? ${/data/earphone/earphoneName} + ' · 已连接' : ${/data/earphone/earphoneName} + ' · 未连接' }}","styles":{"fontSize":12,"fontWeight":400,"fontColor":"#99000000","width":"matchParent","maxLines":1,"textAlign":"start","textOverflow":"clip","layoutWeight":1,"constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_1","component":"Row","children":["root_0_0_1_0","root_0_0_1_1"],"itemMargin":8,"styles":{"width":"matchParent","justifyContent":"center","alignItems":"center","height":56,"constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_1_0","component":"Column","children":["root_0_0_1_0_0","root_0_0_1_0_1"],"itemMargin":1,"styles":{"width":"matchParent","layoutWeight":1,"justifyContent":"center","alignItems":"center","constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_1_0_0","component":"Stack","children":["root_0_0_1_0_0_0"],"styles":{"width":40,"height":40,"alignContent":"center","flexShrink":0}},{"id":"root_0_0_1_0_0_0","component":"Progress","value":"{{ ${/data/earphone/leftBatteryLevel} }}","total":100,"styles":{"type":"ring","color":"{{ ${/data/earphone/leftBatteryLevel} <= 20 ? '#FFF9A01E' : '#FF64BB5C' }}","backgroundColor":"#1A000000","width":40,"height":40,"strokeWidth":6}},{"id":"root_0_0_1_0_1","component":"Text","content":"{{ '' + ${/data/earphone/leftBatteryLevel} + '%' }}","styles":{"fontSize":12,"fontWeight":500,"fontColor":"#E6000000","width":"matchParent","maxLines":1,"textAlign":"center","textOverflow":"clip","constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_1_1","component":"Column","children":["root_0_0_1_1_0","root_0_0_1_1_1"],"itemMargin":1,"styles":{"width":"matchParent","layoutWeight":1,"justifyContent":"center","alignItems":"center","constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_1_1_0","component":"Stack","children":["root_0_0_1_1_0_0"],"styles":{"width":40,"height":40,"alignContent":"center","flexShrink":0}},{"id":"root_0_0_1_1_0_0","component":"Progress","value":"{{ ${/data/earphone/rightBatteryLevel} }}","total":100,"styles":{"type":"ring","color":"{{ ${/data/earphone/rightBatteryLevel} <= 20 ? '#FFF9A01E' : '#FF64BB5C' }}","backgroundColor":"#1A000000","width":40,"height":40,"strokeWidth":6}},{"id":"root_0_0_1_1_1","component":"Text","content":"{{ '' + ${/data/earphone/rightBatteryLevel} + '%' }}","styles":{"fontSize":12,"fontWeight":500,"fontColor":"#E6000000","width":"matchParent","maxLines":1,"textAlign":"center","textOverflow":"clip","constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_2","component":"Text","content":"{{ '充电盒 ' + ${/data/earphone/batteryLevel} + '%' }}","styles":{"fontSize":11,"fontWeight":400,"fontColor":"#99000000","width":"matchParent","maxLines":1,"textAlign":"start","textOverflow":"clip","constraintSize":{"minWidth":0,"minHeight":0}}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"earphone":{"_templateProjection":{"BluetoothDeviceOverview":{"isConnected":true,"earphoneName":"示例耳机","leftBatteryLevel":76,"rightBatteryLevel":78,"batteryLevel":80}},"isConnected":true,"earphoneName":"示例耳机","batteryLevel":80,"leftBatteryLevel":76,"rightBatteryLevel":78}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "耳机状态卡显示左右耳和总电量",
  "size": "2x4",
  "eventCandidates": [],
  "dataModelSchema": {
    "data": {
      "earphone": {
        "_templateProjection": {
          "BluetoothDeviceOverview": {
            "isConnected": {
              "type": "boolean",
              "description": "可信蓝牙耳机连接状态",
              "sampleValue": true
            },
            "earphoneName": {
              "type": "string",
              "description": "可信蓝牙耳机名称",
              "sampleValue": "示例耳机"
            },
            "leftBatteryLevel": {
              "type": "integer",
              "description": "可信左耳电量百分比",
              "sampleValue": 76
            },
            "rightBatteryLevel": {
              "type": "integer",
              "description": "可信右耳电量百分比",
              "sampleValue": 78
            },
            "batteryLevel": {
              "type": "integer",
              "description": "可信充电盒电量百分比",
              "sampleValue": 80
            }
          }
        },
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
  "artifactId": "0f0bafcd-4fc8-4bb8-a256-b795d29e7fc9",
  "createdAt": 1787203238079
}
```
```designcompactdsl
["root","Column",{"width":320,"height":160,"padding":12,"borderRadius":18,"clip":true,"backgroundColor":"#FFFFFFFF","linearGradient":{"direction":"RightBottom","colors":[["#1A64BB5C",0],["#00FFFFFF",1]]},"alignItems":"start","itemMargin":8},["root_0"]]
["root_0","Column",{"width":"100%","height":"100%","justifyContent":"start","alignItems":"start","clip":true,"itemMargin":4},["root_0_0"]]
["root_0_0","Column",{"width":"matchParent","height":"matchParent","justifyContent":"spaceBetween","alignItems":"start","clip":true,"constraintSize":{"minWidth":0,"minHeight":0},"itemMargin":4},["root_0_0_0","root_0_0_1","root_0_0_2"]]
["root_0_0_0","Row",{"width":"matchParent","justifyContent":"spaceBetween","alignItems":"top","height":20,"constraintSize":{"minWidth":0,"minHeight":0},"itemMargin":4},["root_0_0_0_0"]]
["root_0_0_0_0","Text",{"fontSize":12,"fontWeight":400,"fontColor":"#99000000","width":"matchParent","maxLines":1,"textAlign":"start","textOverflow":"ellipsis","layoutWeight":1,"constraintSize":{"minWidth":0,"minHeight":0},"content":"{{ ${/data/earphone/isConnected} ? ${/data/earphone/earphoneName} + ' · 已连接' : ${/data/earphone/earphoneName} + ' · 未连接' }}"}]
["root_0_0_1","Row",{"width":"matchParent","justifyContent":"center","alignItems":"center","height":56,"constraintSize":{"minWidth":0,"minHeight":0},"itemMargin":8},["root_0_0_1_0","root_0_0_1_1"]]
["root_0_0_1_0","Column",{"width":"matchParent","layoutWeight":1,"justifyContent":"center","alignItems":"center","constraintSize":{"minWidth":0,"minHeight":0},"itemMargin":1},["root_0_0_1_0_0","root_0_0_1_0_1"]]
["root_0_0_1_0_0","Stack",{"width":40,"height":40,"alignContent":"center","flexShrink":0},["root_0_0_1_0_0_0"]]
["root_0_0_1_0_0_0","Progress",{"type":"ring","color":"{{ ${/data/earphone/leftBatteryLevel} <= 20 ? '#FFF9A01E' : '#FF64BB5C' }}","backgroundColor":"#1A000000","width":40,"height":40,"strokeWidth":6,"value":"{{ ${/data/earphone/leftBatteryLevel} }}","total":100}]
["root_0_0_1_0_1","Text",{"fontSize":12,"fontWeight":500,"fontColor":"#E6000000","width":"matchParent","maxLines":1,"textAlign":"center","textOverflow":"ellipsis","constraintSize":{"minWidth":0,"minHeight":0},"content":"{{ '' + ${/data/earphone/leftBatteryLevel} + '%' }}"}]
["root_0_0_1_1","Column",{"width":"matchParent","layoutWeight":1,"justifyContent":"center","alignItems":"center","constraintSize":{"minWidth":0,"minHeight":0},"itemMargin":1},["root_0_0_1_1_0","root_0_0_1_1_1"]]
["root_0_0_1_1_0","Stack",{"width":40,"height":40,"alignContent":"center","flexShrink":0},["root_0_0_1_1_0_0"]]
["root_0_0_1_1_0_0","Progress",{"type":"ring","color":"{{ ${/data/earphone/rightBatteryLevel} <= 20 ? '#FFF9A01E' : '#FF64BB5C' }}","backgroundColor":"#1A000000","width":40,"height":40,"strokeWidth":6,"value":"{{ ${/data/earphone/rightBatteryLevel} }}","total":100}]
["root_0_0_1_1_1","Text",{"fontSize":12,"fontWeight":500,"fontColor":"#E6000000","width":"matchParent","maxLines":1,"textAlign":"center","textOverflow":"ellipsis","constraintSize":{"minWidth":0,"minHeight":0},"content":"{{ '' + ${/data/earphone/rightBatteryLevel} + '%' }}"}]
["root_0_0_2","Text",{"fontSize":11,"fontWeight":400,"fontColor":"#99000000","width":"matchParent","maxLines":1,"textAlign":"start","textOverflow":"ellipsis","constraintSize":{"minWidth":0,"minHeight":0},"content":"{{ '充电盒 ' + ${/data/earphone/batteryLevel} + '%' }}"}]
["/",{"data":{"earphone":{"_templateProjection":{"BluetoothDeviceOverview":{"isConnected":true,"earphoneName":"示例耳机","leftBatteryLevel":76,"rightBatteryLevel":78,"batteryLevel":80}},"isConnected":true,"earphoneName":"示例耳机","batteryLevel":80,"leftBatteryLevel":76,"rightBatteryLevel":78}}}]
```
