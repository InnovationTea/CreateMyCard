# getWidgetCapabilityOverview 测试报告

- 生成时间：2026-07-07T13:49:37.171706+00:00
- 接口名：`getWidgetCapabilityOverview`
- WebSocket path：`/api/v1/ws/tools/getWidgetCapabilityOverview`
- 请求协议：content/deviceInfo/session 外层包络
- requestId：`7676c2c8-a6d3-413c-8074-c62ed30db8de&1`
- ready 状态：`ready`
- 消息状态：`result`
- 业务状态：`result`

## ready 消息

```json
{
  "type": "ready",
  "tool": "getWidgetCapabilityOverview",
  "operations": [
    "getWidgetCapabilityOverview"
  ]
}
```

## 入参

```json
{
  "content": {
    "bundleName": "com.omega_w_0823.hmservice"
  },
  "deviceInfo": {
    "countryCode": "CN",
    "deviceFormation": "HDSpeaker",
    "deviceType": 0,
    "locale": "zh-CN",
    "phoneType": "CLS-AL30",
    "prdVer": "11.7.5.205",
    "sysVer": "EmotionUI_9.0.0",
    "time": "20260707115342975"
  },
  "pagination": {
    "limit": 5,
    "start": ""
  },
  "session": {
    "interactionId": "1",
    "isNew": false,
    "sessionId": "7676c2c8-a6d3-413c-8074-c62ed30db8de"
  },
  "userAuth": {
    "user": {
      "userId": "test-user-001"
    }
  },
  "utterance": {
    "original": "",
    "type": "text"
  },
  "version": "1.0",
  "bundleName": "com.omega_w_0823.hmservice"
}
```

## 出参

```json
{
  "type": "result",
  "tool": "getWidgetCapabilityOverview",
  "operation": "getWidgetCapabilityOverview",
  "requestId": "7676c2c8-a6d3-413c-8074-c62ed30db8de&1",
  "data": {
    "apiVersion": "v1",
    "capabilityRegistryVersion": "app-11.7.5.205_rom-36",
    "dataCapabilities": [
      {
        "id": "ViewWeather",
        "description": "查询指定地区或用户当前位置的当前天气与未来数日天气预报。"
      },
      {
        "id": "calendar.events.search",
        "description": "查询用户手机本地日历事件。"
      }
    ],
    "eventCapabilities": [
      {
        "id": "event.call.phone",
        "type": "event",
        "call": "clickToCallPhone",
        "description": "打开拨号界面",
        "targetScene": "拨号界面",
        "argsTemplate": {},
        "parametersSchema": {
          "phoneNumber": "string"
        },
        "dependencies": {
          "minRomVersion": "7.0.0",
          "requiredPackages": [],
          "requiredProviders": [],
          "requiredIntentTargets": [],
          "requiredPermissions": []
        }
      },
      {
        "id": "event.open.settings.dnd",
        "type": "event",
        "call": "clickToDeeplink",
        "description": "打开设置情景模式、免打扰或专注模式",
        "targetApp": "设置",
        "targetScene": "情景模式，免打扰或专注模式",
        "argsTemplate": {
          "bundleName": "com.huawei.hmos.settings",
          "abilityName": "com.huawei.hmos.settings.MainAbility",
          "uri": "intelligent_scene_entry"
        },
        "parametersSchema": {
          "bundleName": "string",
          "abilityName": "string",
          "uri": "string"
        },
        "dependencies": {
          "minRomVersion": "7.0.0",
          "requiredPackages": [],
          "requiredProviders": [],
          "requiredIntentTargets": [],
          "requiredPermissions": []
        }
      },
      {
        "id": "event.open.settings.bluetooth",
        "type": "event",
        "call": "clickToDeeplink",
        "description": "打开蓝牙设置页",
        "targetApp": "设置",
        "targetScene": "蓝牙设置页",
        "argsTemplate": {
          "bundleName": "com.huawei.hmos.settings",
          "abilityName": "com.huawei.hmos.settings.MainAbility",
          "uri": "bluetooth_entry"
        },
        "parametersSchema": {
          "bundleName": "string",
          "abilityName": "string",
          "uri": "string"
        },
        "dependencies": {
          "minRomVersion": "7.0.0",
          "requiredPackages": [],
          "requiredProviders": [],
          "requiredIntentTargets": [],
          "requiredPermissions": []
        }
      },
      {
        "id": "event.open.settings.battery",
        "type": "event",
        "call": "clickToDeeplink",
        "description": "打开设置电池页",
        "targetApp": "设置",
        "targetScene": "电池页",
        "argsTemplate": {
          "bundleName": "com.huawei.hmos.settings",
          "abilityName": "com.huawei.hmos.settings.MainAbility",
          "uri": "battery"
        },
        "parametersSchema": {
          "bundleName": "string",
          "abilityName": "string",
          "uri": "string"
        },
        "dependencies": {
          "minRomVersion": "7.0.0",
          "requiredPackages": [],
          "requiredProviders": [],
          "requiredIntentTargets": [],
          "requiredPermissions": []
        }
      },
      {
        "id": "event.open.settings.batteryHealth",
        "type": "event",
        "call": "clickToDeeplink",
        "description": "打开设置电池健康页",
        "targetApp": "设置",
        "targetScene": "电池健康页",
        "argsTemplate": {
          "bundleName": "com.huawei.hmos.settings",
          "abilityName": "com.huawei.hmos.settings.MainAbility",
          "uri": "smart_charge_battery_health"
        },
        "parametersSchema": {
          "bundleName": "string",
          "abilityName": "string",
          "uri": "string"
        },
        "dependencies": {
          "minRomVersion": "7.0.0",
          "requiredPackages": [],
          "requiredProviders": [],
          "requiredIntentTargets": [],
          "requiredPermissions": []
        }
      },
      {
        "id": "event.open.settings.parentControl",
        "type": "event",
        "call": "clickToDeeplink",
        "description": "打开健康使用 App 页面，设置应用使用时长",
        "targetApp": "设置",
        "targetScene": "健康使用 App 页面，设置应用使用时长",
        "argsTemplate": {
          "bundleName": "com.huawei.hmos.settings",
          "abilityName": "com.huawei.hmos.settings.MainAbility",
          "uri": "parent_control"
        },
        "parametersSchema": {
          "bundleName": "string",
          "abilityName": "string",
          "uri": "string"
        },
        "dependencies": {
          "minRomVersion": "7.0.0",
          "requiredPackages": [],
          "requiredProviders": [],
          "requiredIntentTargets": [],
          "requiredPermissions": []
        }
      },
      {
        "id": "event.open.settings.storage",
        "type": "event",
        "call": "clickToDeeplink",
        "description": "打开设置存储空间页",
        "targetApp": "设置",
        "targetScene": "存储空间页",
        "argsTemplate": {
          "bundleName": "com.huawei.hmos.settings",
          "abilityName": "com.huawei.hmos.settings.MainAbility",
          "uri": "storage_settings"
        },
        "parametersSchema": {
          "bundleName": "string",
          "abilityName": "string",
          "uri": "string"
        },
        "dependencies": {
          "minRomVersion": "7.0.0",
          "requiredPackages": [],
          "requiredProviders": [],
          "requiredIntentTargets": [],
          "requiredPermissions": []
        }
      },
      {
        "id": "event.open.weather",
        "type": "event",
        "call": "clickToDeeplink",
        "description": "打开天气应用某城市页，uri 固定勿改",
        "targetApp": "天气",
        "targetScene": "天气应用某城市页",
        "argsTemplate": {
          "bundleName": "",
          "abilityName": "",
          "uri": "hww://www.huawei.com/totemweather?enterType=share&cityCode="
        },
        "parametersSchema": {
          "bundleName": "string",
          "abilityName": "string",
          "uri": "string"
        },
        "dependencies": {
          "minRomVersion": "7.0.0",
          "requiredPackages": [],
          "requiredProviders": [],
          "requiredIntentTargets": [],
          "requiredPermissions": []
        }
      },
      {
        "id": "event.open.clock.alarm",
        "type": "event",
        "call": "clickToDeeplink",
        "description": "打开闹钟应用首页",
        "targetApp": "闹钟",
        "targetScene": "闹钟应用首页",
        "argsTemplate": {
          "bundleName": "com.huawei.hmos.clock",
          "abilityName": "com.huawei.hmos.clock.phone",
          "uri": ""
        },
        "parametersSchema": {
          "bundleName": "string",
          "abilityName": "string",
          "uri": "string"
        },
        "dependencies": {
          "minRomVersion": "7.0.0",
          "requiredPackages": [],
          "requiredProviders": [],
          "requiredIntentTargets": [],
          "requiredPermissions": []
        }
      },
      {
        "id": "event.open.music.daily",
        "type": "event",
        "call": "clickToDeeplink",
        "description": "打开音乐每日 30 首歌单，uri 固定勿改",
        "targetApp": "音乐",
        "targetScene": "每日 30 首歌单",
        "argsTemplate": {
          "bundleName": "",
          "abilityName": "",
          "uri": "hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4"
        },
        "parametersSchema": {
          "bundleName": "string",
          "abilityName": "string",
          "uri": "string"
        },
        "dependencies": {
          "minRomVersion": "7.0.0",
          "requiredPackages": [],
          "requiredProviders": [],
          "requiredIntentTargets": [],
          "requiredPermissions": []
        }
      },
      {
        "id": "event.open.music.favorite",
        "type": "event",
        "call": "clickToDeeplink",
        "description": "打开音乐收藏歌单/心动歌单，uri 固定勿改",
        "targetApp": "音乐",
        "targetScene": "收藏歌单/心动歌单",
        "argsTemplate": {
          "bundleName": "",
          "abilityName": "",
          "uri": "hwmusic://com.huawei.hmsapp.music/showMusicList?code=favoriteSong&type=412"
        },
        "parametersSchema": {
          "bundleName": "string",
          "abilityName": "string",
          "uri": "string"
        },
        "dependencies": {
          "minRomVersion": "7.0.0",
          "requiredPackages": [],
          "requiredProviders": [],
          "requiredIntentTargets": [],
          "requiredPermissions": []
        }
      },
      {
        "id": "event.open.health.sport",
        "type": "event",
        "call": "clickToDeeplink",
        "description": "打开运动健康锻炼 Tab 页",
        "targetApp": "运动健康",
        "targetScene": "锻炼 Tab 页",
        "argsTemplate": {
          "bundleName": "",
          "abilityName": "",
          "uri": "huaweischeme://healthapp/home/sport?sportType=2"
        },
        "parametersSchema": {
          "bundleName": "string",
          "abilityName": "string",
          "uri": "string"
        },
        "dependencies": {
          "minRomVersion": "7.0.0",
          "requiredPackages": [
            {
              "packageName": "com.huawei.hmos.health.core",
              "minVersion": "16.0.0"
            }
          ],
          "requiredProviders": [],
          "requiredIntentTargets": [],
          "requiredPermissions": []
        }
      },
      {
        "id": "event.open.health.sleep",
        "type": "event",
        "call": "clickToDeeplink",
        "description": "打开运动健康睡眠详情页",
        "targetApp": "运动健康",
        "targetScene": "睡眠详情页",
        "argsTemplate": {
          "bundleName": "",
          "abilityName": "",
          "uri": "huaweischeme://healthapp/router/sleepDetail"
        },
        "parametersSchema": {
          "bundleName": "string",
          "abilityName": "string",
          "uri": "string"
        },
        "dependencies": {
          "minRomVersion": "7.0.0",
          "requiredPackages": [
            {
              "packageName": "com.huawei.hmos.health.core",
              "minVersion": "16.0.0"
            }
          ],
          "requiredProviders": [],
          "requiredIntentTargets": [],
          "requiredPermissions": []
        }
      },
      {
        "id": "event.viewCalendarEvent",
        "type": "event",
        "call": "clickToIntent",
        "description": "查看日程详情",
        "targetScene": "ViewCalendarEvent",
        "argsTemplate": {
          "intentName": "ViewCalendarEvent",
          "params": {
            "entityId": {
              "path": "entityId"
            }
          }
        },
        "parametersSchema": {
          "intentName": "ViewCalendarEvent",
          "params": {
            "entityId": "string"
          }
        },
        "dependencies": {
          "minRomVersion": "7.0.0",
          "requiredPackages": [],
          "requiredProviders": [],
          "requiredIntentTargets": [
            "ViewCalendarEvent"
          ],
          "requiredPermissions": []
        }
      },
      {
        "id": "event.startNavigate",
        "type": "event",
        "call": "clickToIntent",
        "description": "地图导航",
        "targetScene": "StartNavigate",
        "argsTemplate": {
          "intentName": "StartNavigate",
          "params": {
            "dstLocation": {
              "latitude": {
                "path": "/destination/latitude"
              },
              "longitude": {
                "path": "/destination/longitude"
              }
            },
            "trafficpe": "Drive"
          }
        },
        "parametersSchema": {
          "intentName": "StartNavigate",
          "params": {
            "dstLocation": {
              "latitude": "string",
              "longitude": "string"
            },
            "trafficpe": "Drive|Walk|Cycle|Bus"
          }
        },
        "dependencies": {
          "minRomVersion": "7.0.0",
          "requiredPackages": [],
          "requiredProviders": [],
          "requiredIntentTargets": [
            "StartNavigate"
          ],
          "requiredPermissions": []
        }
      },
      {
        "id": "event.setPowerSavingMode",
        "type": "event",
        "call": "clickToIntent",
        "description": "开启省电模式",
        "targetScene": "SetSettingSwitch",
        "argsTemplate": {
          "intentName": "SetSettingSwitch",
          "params": {
            "appBundleName": "com.huawei.hmos.settings",
            "itemName": "battery_saving_mode",
            "switchFlag": 0
          }
        },
        "parametersSchema": {
          "intentName": "SetSettingSwitch",
          "params": {
            "appBundleName": "com.huawei.hmos.settings",
            "itemName": "battery_saving_mode",
            "switchFlag": "number"
          }
        },
        "dependencies": {
          "minRomVersion": "7.0.0",
          "requiredPackages": [],
          "requiredProviders": [],
          "requiredIntentTargets": [
            "SetSettingSwitch"
          ],
          "requiredPermissions": []
        }
      }
    ],
    "assetCandidates": [
      {
        "id": "asset.air_fill",
        "type": "asset",
        "src": "resources/base/media/air_fill.svg",
        "description": "空调/空气循环实心图标，黑色，图形呈矩形风口加出风箭头造型，适用场景：空调控制面板、智能家居空气管理",
        "sceneTags": [
          "air",
          "home"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.air_open_fill",
        "type": "asset",
        "src": "resources/base/media/air_open_fill.svg",
        "description": "空调开启/新风实心图标，黑色，图形为开启状态的风口造型，适用场景：空调开启状态展示、新风系统控制",
        "sceneTags": [
          "air",
          "home"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.airplane_departure",
        "type": "asset",
        "src": "resources/base/media/airplane_departure.svg",
        "description": "飞机起飞图标，黑色，图形为飞机从跑道起飞的侧视图，适用场景：出行计划、航班出发信息、旅行日程",
        "sceneTags": [
          "travel",
          "flight"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.airplane_fill_1",
        "type": "asset",
        "src": "resources/base/media/airplane_fill_1.svg",
        "description": "飞机实心图标，黑色，图形为正面朝上的飞机俯视轮廓，适用场景：旅行场景、航班信息展示、出行卡片",
        "sceneTags": [
          "travel",
          "flight"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.alarm_fill_1",
        "type": "asset",
        "src": "resources/base/media/alarm_fill_1.svg",
        "description": "闹钟实心图标，黑白双色，图形为带铃铛的圆形表盘，适用场景：闹钟设置、定时提醒、日程提醒",
        "sceneTags": [
          "alarm",
          "reminder"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.backward_fill",
        "type": "asset",
        "src": "resources/base/media/backward_fill.svg",
        "description": "快退/后退实心图标，黑色，图形为两个向左的三角箭头，适用场景：音乐播放器快退控制、视频回退",
        "sceneTags": [
          "media",
          "control"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.battery_leaf_fill",
        "type": "asset",
        "src": "resources/base/media/battery_leaf_fill.svg",
        "description": "电池与绿叶组合实心图标，黑色，图形为电池加叶片造型，适用场景：节能模式、绿色用电、环保出行",
        "sceneTags": [
          "battery",
          "power"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.bell_fill",
        "type": "asset",
        "src": "resources/base/media/bell_fill.svg",
        "description": "铃铛实心图标，黑色，图形为经典吊铃造型，适用场景：通知提醒、消息提示、闹铃开启状态",
        "sceneTags": [
          "notification",
          "alarm"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.bell_slash_fill",
        "type": "asset",
        "src": "resources/base/media/bell_slash_fill.svg",
        "description": "铃铛加斜杠实心图标，黑白双色，图形为铃铛上叠加删除线，适用场景：静音模式、关闭通知、勿扰设置",
        "sceneTags": [
          "notification",
          "silent"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.bolt_fill",
        "type": "asset",
        "src": "resources/base/media/bolt_fill.svg",
        "description": "闪电实心图标，黑色，图形为竖向闪电符号，适用场景：充电状态、快充指示、用电量展示",
        "sceneTags": [
          "battery",
          "power"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.bus_fill",
        "type": "asset",
        "src": "resources/base/media/bus_fill.svg",
        "description": "公交车实心图标，黑色，图形为正面视角公共汽车轮廓，适用场景：公共交通出行、路线导航、公交到站提醒",
        "sceneTags": [
          "traffic",
          "bus"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.calendar_fill",
        "type": "asset",
        "src": "resources/base/media/calendar_fill.svg",
        "description": "日历实心图标，黑色，图形为带格线的日历本造型，适用场景：日程管理、日历事件查看、当日安排",
        "sceneTags": [
          "calendar",
          "schedule"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.checkmark_calendar_fill",
        "type": "asset",
        "src": "resources/base/media/checkmark_calendar_fill.svg",
        "description": "带对勾的日历实心图标，黑白双色，图形为日历上叠加对勾，适用场景：已完成日程、日程确认、任务打卡",
        "sceneTags": [
          "calendar",
          "task"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.clean_fill",
        "type": "asset",
        "src": "resources/base/media/clean_fill.svg",
        "description": "清洁实心图标，黑色，图形为清洁工具或净化造型，适用场景：清洁模式、空气净化、家居清洁提醒",
        "sceneTags": [
          "clean",
          "home"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.clock",
        "type": "asset",
        "src": "resources/base/media/clock.svg",
        "description": "时钟线框图标，黑色，图形为圆形表盘加指针的线性轮廓，适用场景：时间显示、定时功能、倒计时",
        "sceneTags": [
          "time",
          "clock"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.clock_fill",
        "type": "asset",
        "src": "resources/base/media/clock_fill.svg",
        "description": "时钟实心图标，黑白双色，图形为圆形实心表盘加白色指针，适用场景：时间显示、闹钟设置、定时器",
        "sceneTags": [
          "time",
          "clock"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.cold",
        "type": "asset",
        "src": "resources/base/media/cold.svg",
        "description": "寒冷/雪花图标，黑色，图形为六角雪花晶体造型，适用场景：制冷模式、低温天气展示、空调冷风设置",
        "sceneTags": [
          "weather",
          "cold"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.drop_1",
        "type": "asset",
        "src": "resources/base/media/drop_1.svg",
        "description": "水滴图标，黑色，图形为圆润水滴轮廓，适用场景：湿度数据展示、饮水提醒、天气降雨信息",
        "sceneTags": [
          "weather",
          "water"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.earphone_case_16644",
        "type": "asset",
        "src": "resources/base/media/earphone_case_16644.svg",
        "description": "耳机收纳盒实心图标，黑色，图形为无线耳机充电盒造型，适用场景：蓝牙耳机设备连接、音频设备管理",
        "sceneTags": [
          "device",
          "audio"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.externaldrive_fill",
        "type": "asset",
        "src": "resources/base/media/externaldrive_fill.svg",
        "description": "外置存储设备实心图标，黑色，图形为矩形硬盘盒造型，适用场景：本地存储管理、数据备份、文件传输",
        "sceneTags": [
          "storage",
          "device"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.face",
        "type": "asset",
        "src": "resources/base/media/face.svg",
        "description": "人脸图标，黑色，图形为简洁人脸轮廓，适用场景：人脸识别解锁、用户头像占位、个人身份展示",
        "sceneTags": [
          "identity",
          "person"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.fast_forward",
        "type": "asset",
        "src": "resources/base/media/fast_forward.svg",
        "description": "快进图标，黑色，图形为两个向右的三角箭头，适用场景：音乐播放器快进控制、视频快进",
        "sceneTags": [
          "media",
          "control"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.figure_pool_swim",
        "type": "asset",
        "src": "resources/base/media/figure_pool_swim.svg",
        "description": "游泳人物图标，黑色，图形为人体游泳动作侧视轮廓，适用场景：运动记录、游泳锻炼追踪、健康运动卡片",
        "sceneTags": [
          "health",
          "sport"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.figure_run",
        "type": "asset",
        "src": "resources/base/media/figure_run.svg",
        "description": "跑步人物图标，黑色，图形为人体奔跑动作侧视轮廓，适用场景：运动记录、跑步锻炼追踪、步数统计",
        "sceneTags": [
          "health",
          "sport"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.flame_fill",
        "type": "asset",
        "src": "resources/base/media/flame_fill.svg",
        "description": "火焰实心图标，黑色，图形为向上燃烧的火焰造型，适用场景：热量消耗展示、加热功能、高温天气提示",
        "sceneTags": [
          "health",
          "heat"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.heart_fill",
        "type": "asset",
        "src": "resources/base/media/heart_fill.svg",
        "description": "心形实心图标，黑色，图形为标准爱心轮廓，适用场景：健康数据、心率监测展示、收藏/喜欢功能",
        "sceneTags": [
          "health",
          "heart"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.heat_generation",
        "type": "asset",
        "src": "resources/base/media/heat_generation.svg",
        "description": "发热/暖气图标，黑色，图形为散热或暖气片波浪造型，适用场景：暖气控制、制热模式、冬季取暖设置",
        "sceneTags": [
          "heat",
          "home"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.house_fill",
        "type": "asset",
        "src": "resources/base/media/house_fill.svg",
        "description": "房屋实心图标，黑白双色，图形为三角屋顶加矩形门洞的家形造型，适用场景：首页导航、智能家居入口、回家提醒",
        "sceneTags": [
          "home"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.id_fill",
        "type": "asset",
        "src": "resources/base/media/id_fill.svg",
        "description": "身份证/工牌实心图标，黑色，图形为矩形证件卡片造型，适用场景：身份识别、工牌/证件展示、当下日程身份信息",
        "sceneTags": [
          "identity"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.kidswatch_fill",
        "type": "asset",
        "src": "resources/base/media/kidswatch_fill.svg",
        "description": "儿童手表实心图标，黑色，图形为圆形表盘加表带的手表造型，适用场景：儿童设备管理、家长控制、儿童安全",
        "sceneTags": [
          "device",
          "watch"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.l_circle_fill",
        "type": "asset",
        "src": "resources/base/media/l_circle_fill.svg",
        "description": "字母L圆形实心图标，黑色，图形为圆形背景内白色L字母，适用场景：标签分类标识、左侧导航标记",
        "sceneTags": [
          "label"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.lamp_ceiling",
        "type": "asset",
        "src": "resources/base/media/lamp_ceiling.svg",
        "description": "吸顶灯图标（关灯状态），黑色，图形为圆形灯盘加固定架造型，适用场景：智能照明控制、灯光管理、家居灯光",
        "sceneTags": [
          "home",
          "light"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.lamp_ceiling_light",
        "type": "asset",
        "src": "resources/base/media/lamp_ceiling_light.svg",
        "description": "吸顶灯亮起图标（开灯状态），黑色，图形为圆形灯盘加射线光芒造型，适用场景：灯光开启状态展示、智能照明控制",
        "sceneTags": [
          "home",
          "light"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.local_fill",
        "type": "asset",
        "src": "resources/base/media/local_fill.svg",
        "description": "本地/定位实心图标，黑色，图形为圆形加中心圆点的定位标记，适用场景：本地内容、当前位置标注、定位功能",
        "sceneTags": [
          "location"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.location_north_up_right_fill",
        "type": "asset",
        "src": "resources/base/media/location_north_up_right_fill.svg",
        "description": "方向导航实心图标，黑色，图形为指向右上方的导航箭头，适用场景：地图导航、方向指引、路线规划",
        "sceneTags": [
          "location",
          "navigation"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.moon_circle_fill",
        "type": "asset",
        "src": "resources/base/media/moon_circle_fill.svg",
        "description": "月亮圆形实心图标，黑白双色，图形为圆形背景内白色月牙，适用场景：夜间模式、睡眠追踪、勿扰模式",
        "sceneTags": [
          "sleep",
          "night"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.moon_z_fill_1",
        "type": "asset",
        "src": "resources/base/media/moon_z_fill_1.svg",
        "description": "月亮加Z睡眠实心图标，黑色，图形为月牙旁附带字母Z表示入睡，适用场景：睡眠模式开启、休息提醒、晚安场景",
        "sceneTags": [
          "sleep",
          "night"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.music_fill",
        "type": "asset",
        "src": "resources/base/media/music_fill.svg",
        "description": "音乐音符实心图标，黑色，图形为双音符连接造型，适用场景：音乐播放卡片、音频功能入口、歌单展示",
        "sceneTags": [
          "music",
          "media"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.pause_fill",
        "type": "asset",
        "src": "resources/base/media/pause_fill.svg",
        "description": "暂停实心图标，黑色，图形为两条竖向平行矩形，适用场景：音乐/视频播放暂停控制",
        "sceneTags": [
          "media",
          "control"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.person_3_fill",
        "type": "asset",
        "src": "resources/base/media/person_3_fill.svg",
        "description": "三人组实心图标，黑色，图形为三个人形轮廓并排排列，适用场景：群组联系人、团队成员展示、家庭成员列表",
        "sceneTags": [
          "person",
          "group"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.phone_fill",
        "type": "asset",
        "src": "resources/base/media/phone_fill.svg",
        "description": "电话实心图标，黑色，图形为经典听筒造型，适用场景：拨打电话、通话功能入口",
        "sceneTags": [
          "phone",
          "call"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.phone_fill_1",
        "type": "asset",
        "src": "resources/base/media/phone_fill_1.svg",
        "description": "电话实心图标（变体），黑色，图形为听筒加信号波形，适用场景：来电接听、通话状态展示",
        "sceneTags": [
          "phone",
          "call"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.play_fill",
        "type": "asset",
        "src": "resources/base/media/play_fill.svg",
        "description": "播放实心图标，黑色，图形为向右的实心三角形，适用场景：音乐/视频播放控制、媒体播放器",
        "sceneTags": [
          "media",
          "control"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.qrcode",
        "type": "asset",
        "src": "resources/base/media/qrcode.svg",
        "description": "二维码图标，黑色，图形为标准方形二维码点阵图案，适用场景：扫码功能、快速连接设备、信息分享",
        "sceneTags": [
          "qrcode",
          "share"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.r_circle_fill",
        "type": "asset",
        "src": "resources/base/media/r_circle_fill.svg",
        "description": "字母R圆形实心图标，黑色，图形为圆形背景内白色R字母，适用场景：标签分类标识、录制状态标记",
        "sceneTags": [
          "label"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.stopwatch_fill",
        "type": "asset",
        "src": "resources/base/media/stopwatch_fill.svg",
        "description": "秒表实心图标，黑白双色，图形为带按钮的圆形秒表造型，适用场景：计时功能、运动计时、倒计时",
        "sceneTags": [
          "time",
          "sport"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.sun_max",
        "type": "asset",
        "src": "resources/base/media/sun_max.svg",
        "description": "太阳最大亮度图标，黑色，图形为圆形太阳加多条粗放射线，适用场景：天气晴朗展示、屏幕亮度最大值",
        "sceneTags": [
          "weather",
          "sun"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.sun_min",
        "type": "asset",
        "src": "resources/base/media/sun_min.svg",
        "description": "太阳最小亮度图标，黑色，图形为圆形太阳加短细放射线，适用场景：低亮度调节、柔和光线、日出/日落场景",
        "sceneTags": [
          "weather",
          "sun"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.tram_fill",
        "type": "asset",
        "src": "resources/base/media/tram_fill.svg",
        "description": "有轨电车实心图标，黑色，图形为带导线的有轨电车侧视轮廓，适用场景：城市公共交通、地铁/轻轨出行导航",
        "sceneTags": [
          "traffic",
          "tram"
        ],
        "minXiaoyiVersion": "1.0.0"
      },
      {
        "id": "asset.z_alarm_fill",
        "type": "asset",
        "src": "resources/base/media/z_alarm_fill.svg",
        "description": "带Z的闹钟贪睡实心图标，黑色，图形为闹钟旁附带字母Z表示贪睡，适用场景：闹钟贪睡功能、延迟提醒、睡眠场景",
        "sceneTags": [
          "alarm",
          "sleep"
        ],
        "minXiaoyiVersion": "1.0.0"
      }
    ]
  }
}
```
