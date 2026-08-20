```cardspec
{
  "title": "TRE-055 测试卡片",
  "description": "三个同字段候选按稳定variantName排序，charging应先于low和normal。",
  "suggestSize": "2x2",
  "dataBindings": [
    {
      "capabilityId": "GetPhoneBatteryInfo",
      "arguments": {},
      "writeResultTo": "/data/phoneBattery"
    }
  ]
}
```
```genui
{"version":"v0.9","createSurface":{"surfaceId":"surface_card","catalogId":"ohos.a2ui.extended.catalog.form"}}
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["root_0"],"itemMargin":8,"styles":{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"backgroundColor":"#FFFFFFFF","justifyContent":"spaceBetween","alignItems":"start","linearGradient":{"direction":"Bottom","colors":[["#1AF9A01E",0],["#00FFFFFF",1]]}}},{"id":"root_0","component":"Column","children":["root_0_0"],"itemMargin":4,"styles":{"width":"matchParent","height":"matchParent","justifyContent":"start","alignItems":"start","clip":true}},{"id":"root_0_0","component":"Column","children":["root_0_0_0","root_0_0_1","root_0_0_2"],"itemMargin":4,"styles":{"width":"matchParent","height":"matchParent","justifyContent":"spaceBetween","alignItems":"start","clip":true,"constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_0","component":"Text","content":"设备电量","styles":{"fontSize":12,"fontWeight":500,"fontColor":"#E6000000","width":"matchParent","maxLines":1,"textOverflow":"clip","constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_1","component":"Text","content":"{{ '电量 ' + ${/data/phoneBattery/batterySOCText} + '，' + ${/data/phoneBattery/batteryCapacityLevelDesc} + '，' + ${/data/phoneBattery/chargingStatusDesc} }}","styles":{"fontSize":12,"fontWeight":400,"fontColor":"#99000000","width":"matchParent","maxLines":1,"textOverflow":"clip","constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_2","component":"Stack","children":["root_0_0_2_0"],"styles":{"width":"matchParent","height":"matchParent","layoutWeight":1,"alignContent":"bottomStart","constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_2_0","component":"Stack","children":["root_0_0_2_0_0"],"styles":{"width":52,"height":52,"alignContent":"center","flexShrink":0}},{"id":"root_0_0_2_0_0","component":"Progress","value":"{{ ${/data/phoneBattery/batterySOC} }}","total":100,"styles":{"type":"ring","color":"#FFF9A01E","backgroundColor":"#1A000000","width":52,"height":52,"strokeWidth":6}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"phoneBattery":{"_templateProjection":{"BatteryOverview":{"batterySOC":68,"batterySOCText":"68%","batteryCapacityLevelDesc":"正常电量","chargingStatusDesc":"未充电"}},"batterySOC":68,"batterySOCText":"68%","chargingStatusDesc":"未充电","batteryCapacityLevelDesc":"正常电量"}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "做一个手机电量卡，显示百分比、充电状态和电量等级",
  "size": "2x2",
  "eventCandidates": [],
  "dataModelSchema": {
    "data": {
      "phoneBattery": {
        "_templateProjection": {
          "BatteryOverview": {
            "batterySOC": {
              "type": "integer",
              "description": "可信手机本机电量百分比数值",
              "sampleValue": 68
            },
            "batterySOCText": {
              "type": "string",
              "description": "可信手机本机电量百分比文本",
              "sampleValue": "68%"
            },
            "batteryCapacityLevelDesc": {
              "type": "string",
              "description": "可信电量等级描述",
              "sampleValue": "正常电量"
            },
            "chargingStatusDesc": {
              "type": "string",
              "description": "可信充电状态描述",
              "sampleValue": "未充电"
            }
          }
        },
        "batterySOC": {
          "type": "integer",
          "description": "当前手机设备剩余电池电量百分比纯数字，取值范围为 0 到 100。",
          "sampleValue": 68
        },
        "batterySOCText": {
          "type": "string",
          "description": "当前手机设备剩余电池电量百分比格式化文本。",
          "sampleValue": "68%"
        },
        "chargingStatusDesc": {
          "type": "string",
          "description": "当前设备电池的充电状态文本描述。",
          "sampleValue": "未充电"
        },
        "batteryCapacityLevelDesc": {
          "type": "string",
          "description": "设备电池电量等级的语义化文本描述。",
          "sampleValue": "正常电量"
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
    "GetPhoneBatteryInfo"
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
      "capabilityId": "GetPhoneBatteryInfo",
      "arguments": {},
      "writeResultTo": "/data/phoneBattery",
      "candidateOutputFields": [
        "/batterySOC",
        "/batterySOCText",
        "/chargingStatusDesc",
        "/batteryCapacityLevelDesc"
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
  "artifactId": "de8f1c33-60d2-40ff-ad4c-1c8a5acc1c72",
  "createdAt": 1787203260907
}
```
```designcompactdsl
["root","Column",{"width":160,"height":160,"padding":12,"borderRadius":18,"clip":true,"backgroundColor":"#FFFFFFFF","justifyContent":"spaceBetween","alignItems":"start","linearGradient":{"direction":"Bottom","colors":[["#1AF9A01E",0],["#00FFFFFF",1]]},"itemMargin":8},["root_0"]]
["root_0","Column",{"width":"100%","height":"100%","justifyContent":"start","alignItems":"start","clip":true,"itemMargin":4},["root_0_0"]]
["root_0_0","Column",{"width":"matchParent","height":"matchParent","justifyContent":"spaceBetween","alignItems":"start","clip":true,"constraintSize":{"minWidth":0,"minHeight":0},"itemMargin":4},["root_0_0_0","root_0_0_1","root_0_0_2"]]
["root_0_0_0","Text",{"fontSize":12,"fontWeight":500,"fontColor":"#E6000000","width":"matchParent","maxLines":1,"textOverflow":"ellipsis","constraintSize":{"minWidth":0,"minHeight":0},"content":"设备电量"}]
["root_0_0_1","Text",{"fontSize":12,"fontWeight":400,"fontColor":"#99000000","width":"matchParent","maxLines":2,"textOverflow":"ellipsis","constraintSize":{"minWidth":0,"minHeight":0},"content":"{{ '电量 ' + ${/data/phoneBattery/batterySOCText} + '，' + ${/data/phoneBattery/batteryCapacityLevelDesc} + '，' + ${/data/phoneBattery/chargingStatusDesc} }}"}]
["root_0_0_2","Stack",{"width":"matchParent","height":"matchParent","layoutWeight":1,"alignContent":"bottomStart","constraintSize":{"minWidth":0,"minHeight":0}},["root_0_0_2_0"]]
["root_0_0_2_0","Stack",{"width":52,"height":52,"alignContent":"center","flexShrink":0},["root_0_0_2_0_0"]]
["root_0_0_2_0_0","Progress",{"type":"ring","color":"#FFF9A01E","backgroundColor":"#1A000000","width":52,"height":52,"strokeWidth":6,"value":"{{ ${/data/phoneBattery/batterySOC} }}","total":100}]
["/",{"data":{"phoneBattery":{"_templateProjection":{"BatteryOverview":{"batterySOC":68,"batterySOCText":"68%","batteryCapacityLevelDesc":"正常电量","chargingStatusDesc":"未充电"}},"batterySOC":68,"batterySOCText":"68%","chargingStatusDesc":"未充电","batteryCapacityLevelDesc":"正常电量"}}}]
```
