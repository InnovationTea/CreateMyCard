# 点击事件能力

```json
{
  "schemaVersion": "1.0",
  "manifestId": "xiaoyi-widget-mvp-v1",
  "capabilities": [
    {
      "functionCall": "clickToApi",
      "description": "执行注册表声明的系统或业务 API 动作。",
      "parameters": {
        "intentName": {
          "type": "string",
          "description": "跳转或调用的系统API功能名称"
        },
        "params": {
          "type": "object",
          "description": "API 执行所需的输入参数对象"
        }
      },
      "notes": [
        "intentName 和 params 为固定对象外壳，不可更改。",
        "如果用户意图无法匹配 supportedTargets 中的任一目标，严禁调用此工具。"
      ],
      "supportedTargets": [
        {
          "intentName": "CallPhone",
          "description": "打开拨号界面；提供电话号码时预填该号码。",
          "params": {
            "phoneNumber": {
              "type": "string",
              "description": "用户提供电话号码时填写；未提供时填写空字符串。"
            }
          }
        },
        {
          "intentName": "CleanRAMMemory",
          "description": "立即清理手机运行内存并释放系统资源。",
          "params": {}
        }
      ]
    },
    {
      "functionCall": "clickToDeeplink",
      "description": "打开注册表声明的应用或页面。",
      "parameters": {
        "intentName": {
          "type": "string",
          "description": "目标应用的英文意图名称（如 Settings, Weather, Clock, Music, Health），必须与 supportedTargets 中定义的 intentName 严格保持一致。"
        },
        "bundleName": {
          "type": "string",
          "description": "应用包名。如果目标页面是通过长 URI 直接拉起（如音乐、运动健康），则此处传空字符串 ''。"
        },
        "abilityName": {
          "type": "string",
          "description": "Ability 名称。如果目标页面是通过长 URI 直接拉起，则此处传空字符串 ''。"
        },
        "uri": {
          "type": "string",
          "description": "页面路径或完整的 Scheme URI。若打开应用首页则传空字符串 ''；若目标提供了长 Scheme（如 hwmusic://...），则直接填入此处。"
        }
      },
      "notes": [
        "核心校验规则：intentName 必须输出。且 bundleName、abilityName、uri 这三个参数中，必须至少有一个是有值的。允许出现只有 uri 有值，而 bundleName 和 abilityName 为空字符串的情况（如音乐、运动健康场景）。",
        "必须严格复制 supportedTargets 对应页面的结构和值，如果某个字段在 target 中没有定义或为空，请务必传入空字符串 ''，严禁自行拼凑或不传。"
      ],
      "supportedTargets": [
        {
          "appName": "设置",
          "intentName": "Settings",
          "description": "打开手机系统设置中的某个页面，能力由uri指定页面",
          "bundleName": "com.huawei.hmos.settings",
          "abilityName": "com.huawei.hmos.settings.MainAbility",
          "pages": [
            {
              "uri": "intelligent_scene_entry",
              "description": "打开系统设置的情景模式页，可配置免打扰或专注模式。"
            },
            {
              "uri": "bluetooth_entry",
              "description": "打开系统设置的蓝牙设置页。"
            },
            {
              "uri": "battery",
              "description": "打开系统设置的电池页。"
            },
            {
              "uri": "smart_charge_battery_health",
              "description": "打开系统设置的电池健康页。"
            },
            {
              "uri": "parent_control",
              "description": "打开系统设置的健康使用设备页，可设置应用使用时长。"
            },
            {
              "uri": "storage_settings",
              "description": "打开系统设置的存储空间页。"
            }
          ]
        },
        {
          "appName": "天气",
          "intentName": "Weather_CityCode",
          "description": "打开手机天气应用",
          "bundleName": "",
          "abilityName": "",
          "pages": [
            {
              "uri": "{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' + ${/data/weather/location/cityCode} }}",
              "description": "打开天气应用中与当前卡片城市对应的天气详情页。"
            }
          ]
        },
        {
          "appName": "闹钟",
          "intentName": "Clock",
          "description": "打开时钟应用的闹钟首页。",
          "bundleName": "com.huawei.hmos.clock",
          "abilityName": "com.huawei.hmos.clock.phone",
          "pages": [
            {
              "uri": "",
              "description": "打开时钟应用的闹钟首页。"
            }
          ]
        },
        {
          "appName": "音乐",
          "intentName": "Music",
          "description": "通过长 Scheme URI 打开音乐应用的指定歌单",
          "bundleName": "",
          "abilityName": "",
          "pages": [
            {
              "uri": "hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4",
              "description": "打开音乐应用的“每日30首”歌单。"
            },
            {
              "uri": "hwmusic://com.huawei.hmsapp.music/showMusicList?code=favoriteSong&type=412",
              "description": "打开音乐应用的收藏歌单（心动歌单）。"
            }
          ]
        },
        {
          "appName": "运动健康",
          "intentName": "Health",
          "description": "根据长 Scheme URI 打开运动健康应用的某页",
          "bundleName": "",
          "abilityName": "",
          "pages": [
            {
              "uri": "huaweischeme://healthapp/home/sport?sportType=2",
              "description": "打开运动健康应用的锻炼页。"
            },
            {
              "uri": "huaweischeme://healthapp/router/sleepDetail",
              "description": "打开运动健康应用的睡眠详情页。"
            }
          ]
        },
        {
          "appName": "日程",
          "intentName": "EnterMeeting",
          "description": "打开手机日程应用",
          "bundleName": "",
          "abilityName": "",
          "pages": [
            {
              "uri": "{{ ${/data/calendar/events/i/oneClickServiceLink} }}",
              "description": "打开所选日程关联的会议链接。"
            }
          ]
        }
      ]
    },
    {
      "functionCall": "clickToIntent",
      "description": "执行注册表声明的应用或页面意图。",
      "parameters": {
        "intentName": {
          "type": "string",
          "description": "跳转使用的意图能力名称，"
        },
        "params": {
          "type": "object",
          "description": "意图执行所需输入参数"
        }
      },
      "notes": [
        "intentName和params为固定字段，不可更改",
        "如果用户意图无法匹配 supportedTargets 中的任一目标，不要调用工具。"
      ],
      "supportedTargets": [
        {
          "intentName": "ViewCalendarEvent",
          "description": "打开所选日程的详情页。",
          "params": {
            "entityId": "{{ ${/data/calendar/events/i/entityId} }}",
            "description": "值取自 GetCalendarEvents 返回的 events[i].entityId；将 i 替换为所选日程在 events 数组中的实际索引。"
          }
        },
        {
          "intentName": "StartNavigate",
          "description": "打开地图应用，导航回家或前往公司。",
          "params": {
            "dstLocation": {
              "location": {
                "type": "string",
                "description": "根据用户目的地填写：回家为 home，前往公司为 company。"
              },
              "latitude": {
                "type": "string",
                "description": "当前能力不接收纬度，固定填写空字符串。"
              },
              "longitude": {
                "type": "string",
                "description": "当前能力不接收经度，固定填写空字符串。"
              }
            }
          }
        },
        {
          "intentName": "SetSettingSwitch",
          "description": "开启或关闭系统省电模式。",
          "params": {
            "appBundleName": {
              "type": "string",
              "description": "固定填写设置应用包名 com.huawei.hmos.settings。"
            },
            "itemName": {
              "type": "string",
              "description": "固定填写省电模式配置项 battery_saving_mode。"
            },
            "switchFlag": {
              "type": "number",
              "description": "根据用户要求填写：开启为 0，关闭为 1。"
            }
          }
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
- `clickToDeeplink.args` 必须包含 manifest `parameters` 声明的 `intentName`、`bundleName`、`abilityName`、`uri`，其中 `intentName` 必须严格复制所选 `supportedTargets` 的值；页面级 `uri` 也必须从所选 target 的 `pages[]` 复制，允许按 target 传空字符串。
- `clickToApi.args.params` 和 `clickToIntent.args.params` 必须严格匹配所选 `supportedTargets` 里的 `params` 结构。不同 `intentName` 的参数不同，不要把某个示例参数当成通用字段。
- 拨号使用 `clickToApi` 中 `intentName: "CallPhone"` 的 target；`params` 只包含 `phoneNumber`，参数名必须严格使用 manifest 中声明的大小写。用户未提供电话号码时，按 manifest 传空字符串。
- 当所选 target 的 `params` 是空对象时，`args.params` 也传空对象，不要补造字段。
- 当 `supportedTargets.params` 的叶子节点是 `type`、`description` 等 schema 说明时，生成 `onClick.args.params` 只保留参数 key 和实际运行时值；不要把 schema 元数据复制到 DSL。若说明中声明固定值，使用该固定值；若说明中要求由用户意图或 DataModel 推导，则填入安全静态值或 `{ "path": "..." }` 绑定。
- 事件参数可以来自安全静态值、DataModel 绝对路径，或模板列表项的相对路径。来自 data capability 输出的字段，必须能从 `writeResultTo + outputSchema` 推导。
- 日程会议链接和日程详情标识分别取自 `GetCalendarEvents` 的 `events[i].oneClickServiceLink` 与 `events[i].entityId`；`i` 必须替换为所选日程的实际数组索引。

下面仅示例 `ViewCalendarEvent` 这个 supported target 的映射方式；其它 intent 必须按各自 target 的 `params` 结构生成。

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
- 后续新增事件能力时，应继续放入 `reference/capability/event-capability/`；生成卡片时按 manifest 选择能力，不要把事件逻辑写死到某个数据场景。
