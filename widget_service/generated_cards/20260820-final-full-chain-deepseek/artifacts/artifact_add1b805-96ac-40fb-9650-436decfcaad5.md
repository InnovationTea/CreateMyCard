```cardspec
{
  "title": "TRE-066 测试卡片",
  "description": "最近运动三字段均为强诉求。",
  "suggestSize": "2x2",
  "dataBindings": [
    {
      "capabilityId": "GetHealthAndSportSummary",
      "arguments": {},
      "writeResultTo": "/data/healthSport"
    }
  ]
}
```
```genui
{"version":"v0.9","createSurface":{"surfaceId":"surface_card","catalogId":"ohos.a2ui.extended.catalog.form"}}
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["root_0"],"itemMargin":8,"styles":{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"backgroundColor":"#FFFFFFFF","justifyContent":"spaceBetween","alignItems":"start","linearGradient":{"direction":"Bottom","colors":[["#1AE84026",0],["#00FFFFFF",1]]}}},{"id":"root_0","component":"Column","children":["root_0_0"],"itemMargin":4,"styles":{"width":"matchParent","height":"matchParent","justifyContent":"start","alignItems":"start","clip":true}},{"id":"root_0_0","component":"Column","children":["root_0_0_0","root_0_0_1"],"itemMargin":4,"styles":{"width":"matchParent","height":"matchParent","justifyContent":"spaceBetween","alignItems":"start","constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_0","component":"Column","children":["root_0_0_0_0","root_0_0_0_1","root_0_0_0_2"],"itemMargin":4,"styles":{"width":"matchParent","justifyContent":"start","constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_0_0","component":"Row","children":["root_0_0_0_0_0"],"itemMargin":4,"styles":{"width":"matchParent","justifyContent":"start","alignItems":"center","constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_0_0_0","component":"Text","content":"{{ ${/data/healthSport/exerciseTypeName} }}","styles":{"fontSize":12,"fontWeight":500,"fontColor":"#99000000","width":"matchParent","maxLines":1,"textOverflow":"clip","constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_0_1","component":"Row","children":["root_0_0_0_1_0"],"itemMargin":4,"styles":{"width":"matchParent","justifyContent":"start","alignItems":"bottom","constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_0_1_0","component":"Text","content":"{{ ${/data/healthSport/exerciseCalorieText} }}","styles":{"fontSize":30,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textOverflow":"clip","constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_0_2","component":"Progress","value":20,"total":100,"styles":{"color":"#FFFFFFFF","backgroundColor":"#1AFFFFFF","strokeWidth":8,"height":12,"width":"matchParent"}},{"id":"root_0_0_1","component":"Column","children":["root_0_0_1_0","root_0_0_1_1"],"itemMargin":4,"styles":{"width":"matchParent","justifyContent":"start","constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_1_0","component":"Row","children":["root_0_0_1_0_0"],"itemMargin":4,"styles":{"width":"matchParent","justifyContent":"start","alignItems":"center","constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_1_0_0","component":"Text","content":"{{ ${/data/healthSport/exerciseDurationText} }}","styles":{"fontSize":12,"fontWeight":400,"fontColor":"#E5000000","maxLines":1,"textOverflow":"clip","constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_1_1","component":"Row","children":["root_0_0_1_1_0"],"itemMargin":4,"styles":{"width":"matchParent","justifyContent":"start","alignItems":"center","constraintSize":{"minWidth":0,"minHeight":0}}},{"id":"root_0_0_1_1_0","component":"Text","content":"{{ ${/data/healthSport/exerciseEndTimeText} }}","styles":{"fontSize":12,"fontWeight":400,"fontColor":"#E5000000","maxLines":1,"textOverflow":"clip","constraintSize":{"minWidth":0,"minHeight":0}}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"healthSport":{"_templateProjection":{"WorkoutOverview":{"exerciseTypeName":"户外跑步","exerciseCalorieText":"260 千卡","exerciseDurationText":"40分","exerciseEndTimeText":"19:10"}},"exerciseTypeName":"户外跑步","exerciseCalorieText":"260 千卡","exerciseDurationText":"40分","exerciseEndTimeText":"19:10"}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "显示我这次运动的类型、持续时间和消耗热量",
  "size": "2x2",
  "eventCandidates": [],
  "dataModelSchema": {
    "data": {
      "healthSport": {
        "_templateProjection": {
          "WorkoutOverview": {
            "exerciseTypeName": {
              "type": "string",
              "description": "可信最近运动类型",
              "sampleValue": "户外跑步"
            },
            "exerciseCalorieText": {
              "type": "string",
              "description": "可信最近运动热量文本",
              "sampleValue": "260 千卡"
            },
            "exerciseDurationText": {
              "type": "string",
              "description": "可信最近运动时长文本",
              "sampleValue": "40分"
            },
            "exerciseEndTimeText": {
              "type": "string",
              "description": "可信最近运动结束时刻",
              "sampleValue": "19:10"
            }
          }
        },
        "exerciseTypeName": {
          "type": "string",
          "description": "最近一次发生的单次专业运动训练类型的中文映射名称，如“羽毛球”、“自由训练”、“户外跑步”。若无记录则返回“暂无运动”。",
          "sampleValue": "户外跑步"
        },
        "exerciseCalorieText": {
          "type": "string",
          "description": "该单次专业运动所产生的净热量消耗文本（已转换千卡），例如“98 千卡”。",
          "sampleValue": "260 千卡"
        },
        "exerciseDurationText": {
          "type": "string",
          "description": "该单次专业运动的实际持续时长文本，例如“1小时40分”。",
          "sampleValue": "40分"
        },
        "exerciseEndTimeText": {
          "type": "string",
          "description": "专业运动结束的确切时刻文本（HH:mm），例如“19:50”。",
          "sampleValue": "19:10"
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
    "GetHealthAndSportSummary"
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
      "capabilityId": "GetHealthAndSportSummary",
      "arguments": {},
      "writeResultTo": "/data/healthSport",
      "candidateOutputFields": [
        "/exerciseTypeName",
        "/exerciseDurationText",
        "/exerciseCalorieText",
        "/exerciseEndTimeText"
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
  "artifactId": "add1b805-96ac-40fb-9650-436decfcaad5",
  "createdAt": 1787203277586
}
```
```designcompactdsl
["root","Column",{"width":160,"height":160,"padding":12,"borderRadius":18,"clip":true,"backgroundColor":"#FFFFFFFF","justifyContent":"spaceBetween","alignItems":"start","linearGradient":{"direction":"Bottom","colors":[["#1AE84026",0],["#00FFFFFF",1]]},"itemMargin":8},["root_0"]]
["root_0","Column",{"width":"100%","height":"100%","justifyContent":"start","alignItems":"start","clip":true,"itemMargin":4},["root_0_0"]]
["root_0_0","Column",{"width":"matchParent","height":"matchParent","justifyContent":"spaceBetween","alignItems":"start","constraintSize":{"minWidth":0,"minHeight":0},"itemMargin":4},["root_0_0_0","root_0_0_1"]]
["root_0_0_0","Column",{"width":"matchParent","justifyContent":"start","constraintSize":{"minWidth":0,"minHeight":0},"itemMargin":4},["root_0_0_0_0","root_0_0_0_1","root_0_0_0_2"]]
["root_0_0_0_0","Row",{"width":"matchParent","justifyContent":"start","alignItems":"center","constraintSize":{"minWidth":0,"minHeight":0},"itemMargin":4},["root_0_0_0_0_0"]]
["root_0_0_0_0_0","Text",{"fontSize":12,"fontWeight":500,"fontColor":"#99000000","width":"matchParent","maxLines":1,"textOverflow":"ellipsis","constraintSize":{"minWidth":0,"minHeight":0},"content":"{{ ${/data/healthSport/exerciseTypeName} }}"}]
["root_0_0_0_1","Row",{"width":"matchParent","justifyContent":"start","alignItems":"bottom","constraintSize":{"minWidth":0,"minHeight":0},"itemMargin":4},["root_0_0_0_1_0"]]
["root_0_0_0_1_0","Text",{"fontSize":30,"fontWeight":800,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis","constraintSize":{"minWidth":0,"minHeight":0},"content":"{{ ${/data/healthSport/exerciseCalorieText} }}"}]
["root_0_0_0_2","Progress",{"color":"#FFFFFFFF","backgroundColor":"#1AFFFFFF","strokeWidth":8,"height":12,"width":"matchParent","value":20,"total":100}]
["root_0_0_1","Column",{"width":"matchParent","justifyContent":"start","constraintSize":{"minWidth":0,"minHeight":0},"itemMargin":4},["root_0_0_1_0","root_0_0_1_1"]]
["root_0_0_1_0","Row",{"width":"matchParent","justifyContent":"start","alignItems":"center","constraintSize":{"minWidth":0,"minHeight":0},"itemMargin":4},["root_0_0_1_0_0"]]
["root_0_0_1_0_0","Text",{"fontSize":12,"fontWeight":400,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis","constraintSize":{"minWidth":0,"minHeight":0},"content":"{{ ${/data/healthSport/exerciseDurationText} }}"}]
["root_0_0_1_1","Row",{"width":"matchParent","justifyContent":"start","alignItems":"center","constraintSize":{"minWidth":0,"minHeight":0},"itemMargin":4},["root_0_0_1_1_0"]]
["root_0_0_1_1_0","Text",{"fontSize":12,"fontWeight":400,"fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis","constraintSize":{"minWidth":0,"minHeight":0},"content":"{{ ${/data/healthSport/exerciseEndTimeText} }}"}]
["/",{"data":{"healthSport":{"_templateProjection":{"WorkoutOverview":{"exerciseTypeName":"户外跑步","exerciseCalorieText":"260 千卡","exerciseDurationText":"40分","exerciseEndTimeText":"19:10"}},"exerciseTypeName":"户外跑步","exerciseCalorieText":"260 千卡","exerciseDurationText":"40分","exerciseEndTimeText":"19:10"}}}]
```
