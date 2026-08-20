```cardspec
{
  "title": "TRE-011 测试卡片",
  "description": "湿度是明确强诉求，但WeatherOverview没有该required字段，必须失败而非悄悄遗漏。",
  "suggestSize": "2x2",
  "dataBindings": [
    {
      "capabilityId": "ViewWeather",
      "arguments": {
        "prefectureName": "测试值"
      },
      "writeResultTo": "/data/weather"
    }
  ]
}
```
```genui
{"version":"v0.9","createSurface":{"surfaceId":"surface_card","catalogId":"ohos.a2ui.extended.catalog.form"}}
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["header","weatherContent","humidityRow"],"styles":{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFDCEEFF",0],["#FFF4FAFF",1]]},"justifyContent":"spaceBetween","alignItems":"center"}},{"id":"header","component":"Row","children":["title","location"],"styles":{"width":136,"height":20,"justifyContent":"spaceBetween","alignItems":"center"}},{"id":"title","component":"Text","content":"天气速览","styles":{"width":104,"height":20,"fontSize":12,"fontWeight":600,"fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}},{"id":"location","component":"Text","content":"{{ ${/data/weather/location/districtName} }}","styles":{"width":32,"height":20,"fontSize":12,"fontWeight":600,"fontColor":"#99000000","maxLines":1,"textAlign":"end","textOverflow":"clip"}},{"id":"weatherContent","component":"Column","children":["temperatureText","conditionText"],"itemMargin":4,"styles":{"width":136,"height":64,"justifyContent":"center","alignItems":"start"}},{"id":"temperatureText","component":"Text","content":"{{ ${/data/weather/current/temperatureText} }}","styles":{"width":136,"height":44,"fontSize":40,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textAlign":"start","textOverflow":"clip"}},{"id":"conditionText","component":"Text","content":"{{ ${/data/weather/current/condition} }}","styles":{"width":136,"height":16,"fontSize":12,"fontWeight":500,"fontColor":"#99000000","maxLines":1,"textAlign":"start","textOverflow":"clip"}},{"id":"humidityRow","component":"Row","children":["humidityLabel","humidityValue"],"styles":{"width":136,"height":28,"padding":{"top":4,"right":8,"bottom":4,"left":8},"borderRadius":14,"backgroundColor":"#FFEAF4FF","justifyContent":"spaceBetween","alignItems":"center"}},{"id":"humidityLabel","component":"Text","content":"湿度","styles":{"width":60,"height":20,"fontSize":12,"fontWeight":500,"fontColor":"#99000000","maxLines":1,"textOverflow":"clip"}},{"id":"humidityValue","component":"Text","content":"{{ ${/data/weather/current/humidityPercent} + '%' }}","styles":{"width":60,"height":20,"fontSize":12,"fontWeight":700,"fontColor":"#FF1769E0","maxLines":1,"textAlign":"end","textOverflow":"clip"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"weather":{"location":{"districtName":"青浦区"},"current":{"temperatureText":"29°C","condition":"多云","humidityPercent":68}}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "做一个天气卡并显示湿度",
  "size": "2x2",
  "eventCandidates": [],
  "dataModelSchema": {
    "data": {
      "weather": {
        "location": {
          "districtName": {
            "type": "string",
            "description": "区或县名称",
            "sampleValue": "青浦区"
          }
        },
        "current": {
          "temperatureText": {
            "type": "string",
            "description": "适合直接显示的温度文本，例如“29°C”。",
            "sampleValue": "29°C"
          },
          "condition": {
            "type": "string",
            "description": "当前天气现象，例如“阴”“多云”“小雨”。",
            "sampleValue": "多云"
          },
          "airQuality": {
            "type": "string",
            "description": "当前空气质量等级，例如“优”“良”。",
            "sampleValue": "良"
          },
          "humidityPercent": {
            "type": "number",
            "description": "当前相对湿度百分比。",
            "sampleValue": 68
          }
        },
        "daily": [
          {
            "temperatureRangeText": {
              "type": "string",
              "description": "适合直接显示的温度范围，例如“24° / 32°”。",
              "sampleValue": "25° / 32°"
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
    "ViewWeather"
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
        "/location/districtName",
        "/current/temperatureText",
        "/current/condition",
        "/current/airQuality",
        "/daily/0/temperatureRangeText",
        "/current/humidityPercent"
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
  "artifactId": "4f5d5d32-69b2-45a7-85de-e092c4ceb5ee",
  "createdAt": 1787203110852
}
```
```designcompactdsl
["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFDCEEFF",0],["#FFF4FAFF",1]]},"justifyContent":"spaceBetween","alignItems":"center"},["header","weatherContent","humidityRow"]]
["header","Row",{"width":136,"height":20,"justifyContent":"spaceBetween","alignItems":"center"},["title","location"]]
["title","Text",{"width":104,"height":20,"fontSize":12,"fontWeight":600,"fontColor":"#99000000","maxLines":1,"content":"天气速览"}]
["location","Text",{"width":32,"height":20,"fontSize":12,"fontWeight":600,"fontColor":"#99000000","maxLines":1,"textAlign":"end","content":"{{ ${/data/weather/location/districtName} }}"}]
["weatherContent","Column",{"width":136,"height":64,"justifyContent":"center","alignItems":"start","itemMargin":4},["temperatureText","conditionText"]]
["temperatureText","Text",{"width":136,"height":44,"fontSize":40,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textAlign":"start","content":"{{ ${/data/weather/current/temperatureText} }}"}]
["conditionText","Text",{"width":136,"height":16,"fontSize":12,"fontWeight":500,"fontColor":"#99000000","maxLines":1,"textAlign":"start","content":"{{ ${/data/weather/current/condition} }}"}]
["humidityRow","Row",{"width":136,"height":28,"padding":{"top":4,"right":8,"bottom":4,"left":8},"borderRadius":14,"backgroundColor":"#FFEAF4FF","justifyContent":"spaceBetween","alignItems":"center"},["humidityLabel","humidityValue"]]
["humidityLabel","Text",{"width":60,"height":20,"fontSize":12,"fontWeight":500,"fontColor":"#99000000","maxLines":1,"content":"湿度"}]
["humidityValue","Text",{"width":60,"height":20,"fontSize":12,"fontWeight":700,"fontColor":"#FF1769E0","maxLines":1,"textAlign":"end","content":"{{ ${/data/weather/current/humidityPercent} + '%' }}"}]
["/data/weather/location/districtName","青浦区"]
["/data/weather/current/temperatureText","29°C"]
["/data/weather/current/condition","多云"]
["/data/weather/current/humidityPercent",68]
```
