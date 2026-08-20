```cardspec
{
  "title": "TRE-018 测试卡片",
  "description": "当前检索只接受一个能力，双业务不得任取其中一个造成遗漏。",
  "suggestSize": "2x2",
  "dataBindings": [
    {
      "capabilityId": "ViewWeather",
      "arguments": {
        "prefectureName": "测试值"
      },
      "writeResultTo": "/data/weather"
    },
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
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["header","dualFacts"],"styles":{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFDCEEFF",0],["#FFF4FAFF",1]]},"justifyContent":"spaceBetween","alignItems":"center"}},{"id":"header","component":"Text","content":"天气与电量","styles":{"width":136,"height":20,"fontSize":12,"fontWeight":600,"fontColor":"#99000000","maxLines":1,"textAlign":"start","textOverflow":"clip"}},{"id":"dualFacts","component":"Row","children":["weatherFact","batteryFact"],"itemMargin":8,"styles":{"width":136,"height":108,"justifyContent":"start","alignItems":"center"}},{"id":"weatherFact","component":"Column","children":["weatherLabel","weatherValue"],"itemMargin":4,"styles":{"width":64,"height":108,"padding":{"top":8,"right":4,"bottom":8,"left":4},"borderRadius":12,"backgroundColor":"#FFEAF4FF","justifyContent":"center","alignItems":"center"}},{"id":"weatherLabel","component":"Text","content":"当前温度","styles":{"width":56,"height":14,"fontSize":10,"fontWeight":500,"fontColor":"#99000000","maxLines":1,"textAlign":"center","textOverflow":"clip"}},{"id":"weatherValue","component":"Text","content":"{{ ${/data/weather/current/temperatureText} }}","styles":{"width":56,"height":40,"fontSize":32,"fontWeight":800,"fontColor":"#FF1769E0","maxLines":1,"textAlign":"center","textOverflow":"clip"}},{"id":"batteryFact","component":"Column","children":["batteryLabel","batteryValue"],"itemMargin":4,"styles":{"width":64,"height":108,"padding":{"top":8,"right":4,"bottom":8,"left":4},"borderRadius":12,"backgroundColor":"#FFE1F4ED","justifyContent":"center","alignItems":"center"}},{"id":"batteryLabel","component":"Text","content":"手机电量","styles":{"width":56,"height":14,"fontSize":10,"fontWeight":500,"fontColor":"#99000000","maxLines":1,"textAlign":"center","textOverflow":"clip"}},{"id":"batteryValue","component":"Text","content":"{{ ${/data/phoneBattery/batterySOCText} }}","styles":{"width":56,"height":40,"fontSize":32,"fontWeight":800,"fontColor":"#FF0F8F78","maxLines":1,"textAlign":"center","textOverflow":"clip"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"weather":{"current":{"temperatureText":"29°C"}},"phoneBattery":{"batterySOCText":"68%"}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "做一张天气加手机电量的卡，天气和电量都要显示",
  "size": "2x2",
  "eventCandidates": [],
  "dataModelSchema": {
    "data": {
      "weather": {
        "current": {
          "temperatureText": {
            "type": "string",
            "description": "适合直接显示的温度文本，例如“29°C”。",
            "sampleValue": "29°C"
          }
        }
      },
      "phoneBattery": {
        "batterySOCText": {
          "type": "string",
          "description": "当前手机设备剩余电池电量百分比格式化文本。",
          "sampleValue": "68%"
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
    "ViewWeather",
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
      "capabilityId": "ViewWeather",
      "arguments": {
        "prefectureName": "测试值"
      },
      "writeResultTo": "/data/weather",
      "candidateOutputFields": [
        "/current/temperatureText"
      ]
    },
    {
      "capabilityId": "GetPhoneBatteryInfo",
      "arguments": {},
      "writeResultTo": "/data/phoneBattery",
      "candidateOutputFields": [
        "/batterySOCText"
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
  "artifactId": "ea842ec7-07d8-40ec-9430-b74ee0e43ebf",
  "createdAt": 1787203147181
}
```
```designcompactdsl
["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFDCEEFF",0],["#FFF4FAFF",1]]},"justifyContent":"spaceBetween","alignItems":"center"},["header","dualFacts"]]
["header","Text",{"width":136,"height":20,"fontSize":12,"fontWeight":600,"fontColor":"#99000000","maxLines":1,"textAlign":"start","content":"天气与电量"}]
["dualFacts","Row",{"width":136,"height":108,"justifyContent":"start","alignItems":"center","itemMargin":8},["weatherFact","batteryFact"]]
["weatherFact","Column",{"width":64,"height":108,"padding":{"top":8,"right":4,"bottom":8,"left":4},"borderRadius":12,"backgroundColor":"#FFEAF4FF","justifyContent":"center","alignItems":"center","itemMargin":4},["weatherLabel","weatherValue"]]
["weatherLabel","Text",{"width":56,"height":14,"fontSize":10,"fontWeight":500,"fontColor":"#99000000","maxLines":1,"textAlign":"center","content":"当前温度"}]
["weatherValue","Text",{"width":56,"height":40,"fontSize":32,"fontWeight":800,"fontColor":"#FF1769E0","maxLines":1,"textAlign":"center","content":"{{ ${/data/weather/current/temperatureText} }}"}]
["batteryFact","Column",{"width":64,"height":108,"padding":{"top":8,"right":4,"bottom":8,"left":4},"borderRadius":12,"backgroundColor":"#FFE1F4ED","justifyContent":"center","alignItems":"center","itemMargin":4},["batteryLabel","batteryValue"]]
["batteryLabel","Text",{"width":56,"height":14,"fontSize":10,"fontWeight":500,"fontColor":"#99000000","maxLines":1,"textAlign":"center","content":"手机电量"}]
["batteryValue","Text",{"width":56,"height":40,"fontSize":32,"fontWeight":800,"fontColor":"#FF0F8F78","maxLines":1,"textAlign":"center","content":"{{ ${/data/phoneBattery/batterySOCText} }}"}]
["/data/weather/current/temperatureText","29°C"]
["/data/phoneBattery/batterySOCText","68%"]
```
