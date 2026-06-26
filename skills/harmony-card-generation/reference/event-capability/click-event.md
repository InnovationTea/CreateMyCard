# 点击事件能力

```json
{
  "schemaVersion": "1.0",
  "manifestId": "xiaoyi-widget-mvp-v1",
  "capabilities": [
    {
      "functionCall": "clickToCallPhone",
      "description": "点击可跳转至指定号码的拨号界面",
      "parameters": {
        "phoneNumber": {
          "type": "string",
          "description": "需要拨打的电话号码"
        }
      }
    },
    {
      "functionCall": "clickToDeeplink",
      "description": "点击可跳转到指定某应用的某页面。只能使用 supportedTargets 中列出的合法 bundleName、abilityName、uri 组合，不要自行编造参数。",
      "parameters": {
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
        "核心校验规则：bundleName、abilityName、uri 这三个参数中，必须至少有一个是有值的。允许出现只有 uri 有值，而 bundleName 和 abilityName 为空字符串的情况（如音乐、运动健康场景）。",
        "必须严格复制 supportedTargets 对应页面的结构和值，如果某个字段在 target 中没有定义或为空，请务必传入空字符串 ''，严禁自行拼凑或不传。"
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
            },
            {
              "uri": "bluetooth_entry",
              "description": "打开系统设置中的蓝牙设置页"
            },
            {
              "uri": "battery",
              "description": "打开系统设置中的电池页"
            },
            {
              "uri": "smart_charge_battery_health",
              "description": "打开系统设置中的电池健康页"
            },
            {
              "uri": "parent_control",
              "description": "打开系统设置中的健康使用App页面"
            },
            {
              "uri": "storage_settings",
              "description": "打开系统设置中的存储空间页"
            },
            {
              "uri": "app_time_management",
              "description": "打开系统设置中的应用时长设置页面（管控按钮跳转目标）"
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
              "description": "打开闹钟应用首页"
            }
          ]
        },
        {
          "appName": "音乐",
          "description": "通过长 Scheme URI 打开音乐应用的指定歌单",
          "bundleName": "",
          "abilityName": "",
          "pages": [
            {
              "uri": "hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4",
              "description": "打开音乐app的每日30首歌单"
            },
            {
              "uri": "hwmusic://com.huawei.hmsapp.music/showMusicList?code=favoriteSong&type=412",
              "description": "打开音乐app的收藏歌单/心动歌单"
            }
          ]
        },
        {
          "appName": "运动健康",
          "description": "根据长 Scheme URI 打开运动健康应用的某页",
          "bundleName": "",
          "abilityName": "",
          "pages": [
            {
              "uri": "huaweischeme://healthapp/home/sport?sportType=2",
              "description": "打开运动健康应用的锻炼Tab页"
            },
            {
              "uri": "huaweischeme://healthapp/router/sleepDetail",
              "description": "打开运动健康应用的睡眠详情页"
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
          "description": "点击日程卡片或日程按钮，跳转到日程 App 查看该日程的详情",
          "params": {
            "entityId": ""
          }
        },
        {
          "intentName": "StartNavigate",
          "description": "点击导航按钮，跳转到地图应用进行导航。大模型需根据用户说的目的地解析出经纬度坐标返回",
          "params": {
            "dstLocation": {
              "latitude": {
                "type": "string",
                "description": "目标地点的纬度坐标，大模型根据用户说的目的地（如公司名称、地址等）解析出纬度并返回"
              },
              "longitude": {
                "type": "string",
                "description": "目标地点的经度坐标，大模型根据用户说的目的地（如公司名称、地址等）解析出经度并返回"
              }
            },
            "trafficpe": {
              "type": "string",
              "description": "出行方式，大模型根据用户表达确定。如用户说'开车去'则传Drive，'走路去'则传Walk。枚举值：Drive(开车)、Walk(步行)、Cycle(骑行)、Bus(公共交通)"
            }
          }
        },
        {
          "intentName": "SetSettingSwitch",
          "description": "点击一键开启/关闭省电模式。大模型根据用户表达确定是开启还是关闭，然后传对应的switchFlag值",
          "params": {
            "appBundleName": {
              "type": "string",
              "description": "固定值：com.huawei.hmos.settings（设置应用包名）"
            },
            "itemName": {
              "type": "string",
              "description": "固定值：battery_saving_mode（省电模式配置项名称）"
            },
            "switchFlag": {
              "type": "number",
              "description": "开关状态：0表示开启省电模式，1表示关闭省电模式。大模型根据用户意图判断，用户说'开启省电模式'传0，'关闭省电模式'传1"
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
- 拨号能力参数名必须严格使用 manifest 中声明的 `phoneNumber`，不要使用其它大小写变体。
- `clickToIntent.args.params` 必须严格匹配所选 `supportedTargets` 里的 `params` 结构。不同 intent 的参数不同，不要把某个示例参数当成通用字段。
- 事件参数可以来自安全静态值、DataModel 绝对路径，或模板列表项的相对路径。来自 data capability 输出的字段，必须能从 `writeResultTo + outputSchema` 推导。

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
- 后续新增事件能力时，应继续放入 `reference/event-capability/`；生成卡片时按 manifest 选择能力，不要把事件逻辑写死到某个数据场景。
