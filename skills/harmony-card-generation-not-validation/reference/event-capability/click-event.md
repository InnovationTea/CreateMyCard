# 点击事件能力

```json
{
  "schemaVersion": "1.0",
  "manifestId": "xiaoyi-weather-widget-mvp-v1",
  "capabilities": [
    {
      "functionCall": "clickToCallPhone",
      "description": "点击可跳转至指定号码的拨号界面",
      "parameters": {
        "phonenumber": {
          "type": "string",
          "description": "需要拨打的电话号码"
        }
      }
    },
    {
      "functionCall": "clickToDeeplink",
      "description": "跳转到指定应用或页面。只能使用 supportedTargets 中列出的合法 bundleName、abilityName、uri 组合，不要自行编造参数。",
      "parameters": {
        "bundleName": {
          "type": "string",
          "description": "应用包名，例如 com.huawei.hmos.settings"
        },
        "abilityName": {
          "type": "string",
          "description": "Ability 名称，例如 com.huawei.hmos.settings.MainAbility"
        },
        "uri": {
          "type": "string",
          "description": "uri路径，用于进入应用内指定页面。打开应用首页时传空字符串。"
        }
      },
      "notes": [
        "bundleName、abilityName、uri 存在固定组合关系，不可自由组合，三个必有一个有值，否则为无效数据。",
        "如果目标页面没有的字段，则使用空字符串。",
        "如果用户意图无法匹配 supportedTargets 中的任一目标，不要调用工具。"
      ],
      "supportedTargets": [
        {
          "appName": "设置",
          "description": "打开手机系统设置中的某个页面，能力由uri指定页面",
          "bundleName": "com.huawei.hmos.settings",
          "abilityName": "com.huawei.hmos.settings.MainAbility",
          "pages": [
            {
              "uri": "intelligent_scene_entry",
              "description": "打开系统设置中的情景模式，用户可以打开免打扰或专注模式"
            }
          ]
        },
        {
          "appName": "天气",
          "description": "打开手机天气应用",
          "bundleName": "com.huawei.hmsapp.totemweather",
          "abilityName": "com.huawei.hmsapp.totemweather.MainAbility",
          "pages": [
            {
              "uri": "",
              "description": "打开手机天气应用首页"
            }
          ]
        },
        {
          "appName": "闹钟",
          "description": "打开闹钟应用首页",
          "bundleName": "com.huawei.hmos.clock",
          "abilityName": "com.huawei.hmos.clock.phone",
          "pages": [
            {
              "uri": "",
              "description": "开闹钟应用首页"
            }
          ]
        }
      ]
    },
    {
      "functionCall": "clickToIntent",
      "description": "点击跳转到指定应用或页面。只能使用 supportedTargets 中列出的合法intentName和params不要自行编造参数。",
      "parameters": {
        "intentName": {
          "type": "string",
          "description": "跳转使用的意图能力名称"
        },
        "params": {
          "type": "object",
          "description": "查看日程输入参数描述",
          "properties": {
            "entityId": {
              "description": "索引项唯一标识符，来源在端侧提供",
              "type": "string"
            }
          }
        }
      },
      "notes": [
        "intentName为固定字段，不可更改，entityId为必要key，内容为空也需提供",
        "如果用户意图无法匹配 supportedTargets 中的任一目标，不要调用工具。"
      ],
      "supportedTargets": [
        {
          "intentName": "ViewCalendarEvent",
          "description": "根据entityId跳到日程app查看该日程的详情",
          "params": [
            {
              "entityId": "",
              "description": "entityId为点击日程的Id,具体值由端侧提供，只需体现key为entityId"
            }
          ]
        }
      ]
    }
  ]
}
```

## DSL 映射规则

- 本文件只指导 DSL `onClick`，不进入 CardSpec，也不新增第三个输出代码块。
- `onClick.call` 必须使用 `capabilities[].functionCall` 中声明的值。不要把 `description`、应用名或页面名写成 `call`。
- 先按用户意图匹配 `capabilities[].description`，再校验该能力的 `parameters` 和 `supportedTargets`；不能匹配时不要伪造点击能力。
- `args` 只能包含该能力 `parameters` 中声明的参数。跳转类能力必须使用 `supportedTargets` 中列出的合法目标和值组合。
- 事件参数可以来自安全静态值、DataModel 绝对路径，或模板列表项的相对路径。来自 data capability 输出的字段，必须能从 `writeResultTo + outputSchema` 推导。

```json
{
  "call": "clickToIntent",
  "args": {
    "intentName": "ViewCalendarEvent",
    "params": {
      "entityId": {"path": "entityId"}
    }
  }
}
```

- 模板列表项内使用当前项字段时优先写相对路径，例如 `{"path": "entityId"}`；非模板区域使用绝对路径，例如 `{"path": "/data/calendar/items/0/entityId"}`。
- 如果用户意图无法匹配本文件任一能力或目标，不要伪造点击能力；改为静态展示或说明需要宿主补充 event-capability manifest。
- 后续新增事件能力时，应继续放入 `reference/event-capability/`；生成卡片时按 manifest 选择能力，不要把事件逻辑写死到某个数据场景。
