```cardspec
{
  "title": "TRE-044 测试卡片",
  "description": "2x4应选择wide Variant，不能误报尺寸失败。",
  "suggestSize": "2x4",
  "dataBindings": [
    {
      "capabilityId": "GetAppUsageDuration",
      "arguments": {
        "appBundleName": "测试值"
      },
      "writeResultTo": "/data/appUsageStats"
    }
  ]
}
```
```genui
{"version":"v0.9","createSurface":{"surfaceId":"surface_card","catalogId":"ohos.a2ui.extended.catalog.form"}}
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["root_0"],"itemMargin":8,"styles":{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"backgroundColor":"#FFFFFFFF","justifyContent":"spaceBetween","alignItems":"start","linearGradient":{"direction":"Bottom","colors":[["#1A0A59F7",0],["#00FFFFFF",1]]}}},{"id":"root_0","component":"Column","children":["root_0_0"],"itemMargin":4,"styles":{"width":"matchParent","height":"matchParent","justifyContent":"start","alignItems":"start","clip":true}},{"id":"root_0_0","component":"Column","children":["root_0_0_0","root_0_0_1"],"itemMargin":4,"styles":{"width":"matchParent","height":"matchParent","justifyContent":"start","alignItems":"start","clip":true,"constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_0","component":"Row","children":["root_0_0_0_0"],"itemMargin":4,"styles":{"width":"matchParent","justifyContent":"spaceBetween","alignItems":"top","height":20,"clip":true,"constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_0_0","component":"Text","content":"{{ ${/data/appUsageStats/appUsage/appName} }}","styles":{"fontSize":12,"fontWeight":600,"fontColor":"#E6000000","minFontSize":12,"maxLines":1,"textOverflow":"clip","layoutWeight":1,"constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_1","component":"Column","children":["root_0_0_1_0"],"itemMargin":4,"styles":{"width":"matchParent","layoutWeight":1,"justifyContent":"end","alignItems":"start","clip":true,"constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_1_0","component":"Row","children":["root_0_0_1_0_0","root_0_0_1_0_1"],"itemMargin":2,"styles":{"width":"matchParent","justifyContent":"start","alignItems":"bottom","clip":true,"constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_1_0_0","component":"Text","content":"{{ ${/data/appUsageStats/_templateProjection/AppUsageOverview/durationPrimaryValueText} }}","styles":{"fontSize":30,"fontWeight":700,"fontColor":"#E6000000","minFontSize":30,"maxLines":1,"textOverflow":"clip","constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_1_0_1","component":"Text","content":"{{ ${/data/appUsageStats/_templateProjection/AppUsageOverview/durationPrimaryUnitText} }}","styles":{"fontSize":12,"fontWeight":400,"fontColor":"#99000000","minFontSize":12,"maxLines":1,"textOverflow":"clip","constraintSize":{"minWidth":0,"minHeight":0}}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"appUsageStats":{"_templateProjection":{"AppUsageOverview":{"appName":"示例应用","durationText":"25 分钟","durationPrimaryValueText":"25","durationPrimaryUnitText":"分钟"}},"appUsage":{"appName":"示例应用","durationText":"25 分钟"}}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "做一张2x4的应用使用时长卡",
  "size": "2x4",
  "eventCandidates": [],
  "dataModelSchema": {
    "data": {
      "appUsageStats": {
        "_templateProjection": {
          "AppUsageOverview": {
            "appName": {
              "type": "string",
              "description": "可信单应用名称",
              "sampleValue": "示例应用"
            },
            "durationText": {
              "type": "string",
              "description": "可信单应用今日使用时长原文",
              "sampleValue": "25 分钟"
            },
            "durationPrimaryValueText": {
              "type": "string",
              "description": "从可信使用时长无损解析的主数值",
              "sampleValue": "25"
            },
            "durationPrimaryUnitText": {
              "type": "string",
              "description": "从可信使用时长无损解析的主单位",
              "sampleValue": "分钟"
            }
          }
        },
        "appUsage": {
          "appName": {
            "type": "string",
            "description": "应用名称文本，例如：“抖音”",
            "sampleValue": "示例应用"
          },
          "durationText": {
            "type": "string",
            "description": "应用今日运行总时间文本（自带单位），例如：“25 秒”或“1 分钟 21 秒”",
            "sampleValue": "25 分钟"
          }
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
    "GetAppUsageDuration"
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
      "capabilityId": "GetAppUsageDuration",
      "arguments": {
        "appBundleName": "测试值"
      },
      "writeResultTo": "/data/appUsageStats",
      "candidateOutputFields": [
        "/appUsage/appName",
        "/appUsage/durationText"
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
  "artifactId": "57e7d0ef-a4d4-4317-a67a-7a14caaa704f",
  "createdAt": 1787203226031
}
```
```designcompactdsl
["root","Column",{"width":320,"height":160,"padding":12,"borderRadius":18,"clip":true,"backgroundColor":"#FFFFFFFF","justifyContent":"spaceBetween","alignItems":"start","linearGradient":{"direction":"Bottom","colors":[["#1A0A59F7",0],["#00FFFFFF",1]]},"itemMargin":8},["root_0"]]
["root_0","Column",{"width":"100%","height":"100%","justifyContent":"start","alignItems":"start","clip":true,"itemMargin":4},["root_0_0"]]
["root_0_0","Column",{"width":"matchParent","height":"matchParent","justifyContent":"start","alignItems":"start","clip":true,"constraintSize":{"minWidth":0,"minHeight":0},"itemMargin":4},["root_0_0_0","root_0_0_1"]]
["root_0_0_0","Row",{"width":"matchParent","justifyContent":"spaceBetween","alignItems":"top","height":20,"clip":true,"constraintSize":{"minWidth":0,"minHeight":0},"itemMargin":4},["root_0_0_0_0"]]
["root_0_0_0_0","Text",{"fontSize":12,"fontWeight":600,"fontColor":"#E6000000","minFontSize":12,"maxLines":1,"textOverflow":"ellipsis","layoutWeight":1,"constraintSize":{"minWidth":0,"minHeight":0},"content":"{{ ${/data/appUsageStats/appUsage/appName} }}"}]
["root_0_0_1","Column",{"width":"matchParent","layoutWeight":1,"justifyContent":"end","alignItems":"start","clip":true,"constraintSize":{"minWidth":0,"minHeight":0},"itemMargin":4},["root_0_0_1_0"]]
["root_0_0_1_0","Row",{"width":"matchParent","justifyContent":"start","alignItems":"bottom","clip":true,"constraintSize":{"minWidth":0,"minHeight":0},"itemMargin":2},["root_0_0_1_0_0","root_0_0_1_0_1"]]
["root_0_0_1_0_0","Text",{"fontSize":30,"fontWeight":700,"fontColor":"#E6000000","minFontSize":30,"maxLines":1,"textOverflow":"ellipsis","constraintSize":{"minWidth":0,"minHeight":0},"content":"{{ ${/data/appUsageStats/_templateProjection/AppUsageOverview/durationPrimaryValueText} }}"}]
["root_0_0_1_0_1","Text",{"fontSize":12,"fontWeight":400,"fontColor":"#99000000","minFontSize":12,"maxLines":1,"textOverflow":"ellipsis","constraintSize":{"minWidth":0,"minHeight":0},"content":"{{ ${/data/appUsageStats/_templateProjection/AppUsageOverview/durationPrimaryUnitText} }}"}]
["/",{"data":{"appUsageStats":{"_templateProjection":{"AppUsageOverview":{"appName":"示例应用","durationText":"25 分钟","durationPrimaryValueText":"25","durationPrimaryUnitText":"分钟"}},"appUsage":{"appName":"示例应用","durationText":"25 分钟"}}}}]
```
