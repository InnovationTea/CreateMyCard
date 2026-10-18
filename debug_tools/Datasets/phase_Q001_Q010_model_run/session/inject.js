// 把 Phase Q001–Q010 的真实批跑结果写进「本次会话调试记录」。
// 用法：打开 http://127.0.0.1:8888/debug/ 任意页面，F12 控制台整段粘贴执行后会自动刷新。
const RECORDS = [
  {
    "id": "run-Q001",
    "operation": "generateWidgetCardCompactDsl",
    "source": "interface",
    "status": "success",
    "startedAt": "2026-10-18T03:09:28+00:00",
    "finishedAt": "2026-10-18T03:09:32+00:00",
    "completedAt": "2026-10-18T03:09:32+00:00",
    "durationMs": 4000,
    "request": {
      "content": {
        "bundleName": "com.omega_w_0823.hmservice",
        "userQuery": "帮我做个卡片，看杭州市西湖区现在是什么天气，点一下查看杭州天气详情。",
        "candidateDataBindings": [
          {
            "capabilityId": "ViewWeather",
            "arguments": {
              "prefectureName": "杭州市",
              "districtName": "西湖区",
              "forecastDays": 1
            },
            "writeResultTo": "/data/weather",
            "candidateOutputFields": [
              "/location/cityCode",
              "/location/districtName",
              "/location/prefectureName",
              "/current/condition"
            ]
          }
        ],
        "title": "西湖天气",
        "size": "2x2",
        "candidateEventCandidates": [
          {
            "capabilityId": "event.open.weather",
            "action": {
              "call": "clickToDeeplink",
              "args": {
                "intentName": "Weather_CityCode",
                "bundleName": "",
                "abilityName": "",
                "uri": "{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' + ${/data/weather/location/cityCode} }}"
              }
            }
          }
        ],
        "description": "西湖天气和详情",
        "candidateAssetIds": [
          "asset.local_fill",
          "asset.sun_max"
        ]
      },
      "deviceInfo": {
        "countryCode": "CN",
        "deviceFormation": "HDSpeaker",
        "deviceType": 0,
        "locale": "zh-CN",
        "phoneType": "SGT-AL10",
        "prdVer": "11.9.9.342",
        "romVersion": "7.0",
        "sysVer": "EmotionUI_9.0.0",
        "time": "20260828000000000"
      },
      "pagination": {
        "limit": 5,
        "start": ""
      },
      "session": {
        "interactionId": "001",
        "isNew": true,
        "sessionId": "taskspec-829.2"
      },
      "userAuth": {
        "user": {
          "userId": ""
        }
      },
      "utterance": {
        "original": "帮我做个卡片，看杭州市西湖区现在是什么天气，点一下查看杭州天气详情。",
        "type": "text"
      },
      "version": "1.0",
      "bundleName": "com.omega_w_0823.hmservice",
      "userQuery": "帮我做个卡片，看杭州市西湖区现在是什么天气，点一下查看杭州天气详情。",
      "candidateDataBindings": [
        {
          "capabilityId": "ViewWeather",
          "arguments": {
            "prefectureName": "杭州市",
            "districtName": "西湖区",
            "forecastDays": 1
          },
          "writeResultTo": "/data/weather",
          "candidateOutputFields": [
            "/location/cityCode",
            "/location/districtName",
            "/location/prefectureName",
            "/current/condition"
          ]
        }
      ],
      "title": "西湖天气",
      "size": "2x2",
      "candidateEventCandidates": [
        {
          "capabilityId": "event.open.weather",
          "action": {
            "call": "clickToDeeplink",
            "args": {
              "intentName": "Weather_CityCode",
              "bundleName": "",
              "abilityName": "",
              "uri": "{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' + ${/data/weather/location/cityCode} }}"
            }
          }
        }
      ],
      "description": "西湖天气和详情",
      "candidateAssetIds": [
        "asset.local_fill",
        "asset.sun_max"
      ]
    },
    "response": {
      "data": {
        "genui": "[\"root\", \"Layout\", {\"layout\": \"S-title-primary-secondary-action\", \"linearGradient\": {\"direction\": \"RightBottom\", \"colors\": [[\"#FF86C5E3\", 0], [\"#FFF5DC62\", 1]]}}, [\"header\", \"current\", \"region\", \"detail\"]]\n[\"header\", \"SingleLineTitle\", {\"title\": \"西湖天气\", \"icon\": \"resources/base/media/local_fill.svg\", \"fontSize\": 12}]\n[\"current\", \"EmphasisText\", {\"mainText\": {\"path\": \"/data/weather/current/condition\"}, \"fontSize\": 18}]\n[\"/data/weather/current/condition\", \"晴\"]\n[\"region\", \"SecondaryBody\", {\"items\": [{\"label\": \"区域\", \"value\": \"{{ ${/data/weather/location/prefectureName} + ' ' + ${/data/weather/location/districtName} }}\"}], \"fontSize\": 14}]\n[\"detail\", \"PillButton\", {\"label\": \"查看详情\", \"icon\": \"resources/base/media/sun_max.svg\", \"onClick\": [{\"call\": \"clickToDeeplink\", \"args\": {\"intentName\": \"Weather_CityCode\", \"uri\": \"{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' + ${/data/weather/location/cityCode} }}\"}}]}]\n[\"/data/weather/location/prefectureName\", \"杭州市\"]\n[\"/data/weather/location/districtName\", \"西湖区\"]\n[\"/data/weather/location/cityCode\", \"101210101\"]\n",
        "title": "西湖天气",
        "cardSpec": {
          "suggestSize": "2x2"
        }
      }
    }
  },
  {
    "id": "run-Q002",
    "operation": "generateWidgetCardCompactDsl",
    "source": "interface",
    "status": "success",
    "startedAt": "2026-10-18T03:10:28+00:00",
    "finishedAt": "2026-10-18T03:10:32+00:00",
    "completedAt": "2026-10-18T03:10:32+00:00",
    "durationMs": 4000,
    "request": {
      "content": {
        "bundleName": "com.omega_w_0823.hmservice",
        "userQuery": "明天在重庆安排户外活动，帮我做个卡片，看明天的日期、星期和天气。",
        "candidateDataBindings": [
          {
            "capabilityId": "ViewWeather",
            "arguments": {
              "prefectureName": "重庆市",
              "forecastDays": 2
            },
            "writeResultTo": "/data/weather",
            "candidateOutputFields": [
              "/daily/1/date",
              "/daily/1/weekday",
              "/daily/1/condition"
            ]
          }
        ],
        "title": "明日天气",
        "size": "2x2",
        "candidateEventCandidates": [],
        "description": "日期星期和天气",
        "candidateAssetIds": [
          "asset.calendar_fill",
          "asset.sun_max"
        ]
      },
      "deviceInfo": {
        "countryCode": "CN",
        "deviceFormation": "HDSpeaker",
        "deviceType": 0,
        "locale": "zh-CN",
        "phoneType": "SGT-AL10",
        "prdVer": "11.9.9.342",
        "romVersion": "7.0",
        "sysVer": "EmotionUI_9.0.0",
        "time": "20260828000000000"
      },
      "pagination": {
        "limit": 5,
        "start": ""
      },
      "session": {
        "interactionId": "002",
        "isNew": true,
        "sessionId": "taskspec-829.2"
      },
      "userAuth": {
        "user": {
          "userId": ""
        }
      },
      "utterance": {
        "original": "明天在重庆安排户外活动，帮我做个卡片，看明天的日期、星期和天气。",
        "type": "text"
      },
      "version": "1.0",
      "bundleName": "com.omega_w_0823.hmservice",
      "userQuery": "明天在重庆安排户外活动，帮我做个卡片，看明天的日期、星期和天气。",
      "candidateDataBindings": [
        {
          "capabilityId": "ViewWeather",
          "arguments": {
            "prefectureName": "重庆市",
            "forecastDays": 2
          },
          "writeResultTo": "/data/weather",
          "candidateOutputFields": [
            "/daily/1/date",
            "/daily/1/weekday",
            "/daily/1/condition"
          ]
        }
      ],
      "title": "明日天气",
      "size": "2x2",
      "candidateEventCandidates": [],
      "description": "日期星期和天气",
      "candidateAssetIds": [
        "asset.calendar_fill",
        "asset.sun_max"
      ]
    },
    "response": {
      "data": {
        "genui": "[\"root\", \"Layout\", {\"layout\": \"S-title-content\", \"linearGradient\": {\"direction\": \"RightBottom\", \"colors\": [[\"#FFA8D8EA\", 0], [\"#FFF7E6C4\", 1]]}}, [\"header\", \"summary\"]]\n[\"header\", \"SingleLineTitle\", {\"title\": \"明日天气\", \"icon\": \"resources/base/media/calendar_fill.svg\", \"fontSize\": 12}]\n[\"summary\", \"EmphasisText\", {\"mainText\": {\"path\": \"/data/weather/daily/1/condition\"}, \"secondaryText\": [{\"path\": \"/data/weather/daily/1/date\"}, {\"path\": \"/data/weather/daily/1/weekday\"}], \"fontSize\": 18}]\n[\"/data/weather/daily/1/condition\", \"晴\"]\n[\"/data/weather/daily/1/date\", \"9月15日\"]\n[\"/data/weather/daily/1/weekday\", \"星期二\"]\n",
        "title": "明日天气",
        "cardSpec": {
          "suggestSize": "2x2"
        }
      }
    }
  },
  {
    "id": "run-Q003",
    "operation": "generateWidgetCardCompactDsl",
    "source": "interface",
    "status": "success",
    "startedAt": "2026-10-18T03:11:28+00:00",
    "finishedAt": "2026-10-18T03:11:32+00:00",
    "completedAt": "2026-10-18T03:11:32+00:00",
    "durationMs": 4000,
    "request": {
      "content": {
        "bundleName": "com.omega_w_0823.hmservice",
        "userQuery": "下一场日程是18天后上午十点的产品发布会，帮我做个卡片，看离发布会还有几天、日程标题和开始时间，点一下查看日程详情。",
        "candidateDataBindings": [
          {
            "capabilityId": "GetCountdownDays",
            "arguments": {
              "targetDate": "2026-09-15"
            },
            "writeResultTo": "/data/countdown",
            "candidateOutputFields": [
              "/countdownDays"
            ]
          },
          {
            "capabilityId": "GetCalendarEvents",
            "arguments": {
              "futureDays": 29
            },
            "writeResultTo": "/data/calendar",
            "candidateOutputFields": [
              "/events/0/title",
              "/events/0/dtStart",
              "/events/0/entityId"
            ]
          }
        ],
        "title": "发布会提醒",
        "size": "2x2",
        "candidateEventCandidates": [
          {
            "capabilityId": "event.viewCalendarEvent",
            "action": {
              "call": "clickToIntent",
              "args": {
                "intentName": "ViewCalendarEvent",
                "params": {
                  "entityId": "{{ ${/data/calendar/events/0/entityId} }}"
                }
              }
            }
          }
        ],
        "description": "倒数日和日程",
        "candidateAssetIds": [
          "asset.alarm_fill_1",
          "asset.calendar_fill",
          "asset.stopwatch_fill"
        ]
      },
      "deviceInfo": {
        "countryCode": "CN",
        "deviceFormation": "HDSpeaker",
        "deviceType": 0,
        "locale": "zh-CN",
        "phoneType": "SGT-AL10",
        "prdVer": "11.9.9.342",
        "romVersion": "7.0",
        "sysVer": "EmotionUI_9.0.0",
        "time": "20260828000000000"
      },
      "pagination": {
        "limit": 5,
        "start": ""
      },
      "session": {
        "interactionId": "003",
        "isNew": true,
        "sessionId": "taskspec-829.2"
      },
      "userAuth": {
        "user": {
          "userId": ""
        }
      },
      "utterance": {
        "original": "下一场日程是18天后上午十点的产品发布会，帮我做个卡片，看离发布会还有几天、日程标题和开始时间，点一下查看日程详情。",
        "type": "text"
      },
      "version": "1.0",
      "bundleName": "com.omega_w_0823.hmservice",
      "userQuery": "下一场日程是18天后上午十点的产品发布会，帮我做个卡片，看离发布会还有几天、日程标题和开始时间，点一下查看日程详情。",
      "candidateDataBindings": [
        {
          "capabilityId": "GetCountdownDays",
          "arguments": {
            "targetDate": "2026-09-15"
          },
          "writeResultTo": "/data/countdown",
          "candidateOutputFields": [
            "/countdownDays"
          ]
        },
        {
          "capabilityId": "GetCalendarEvents",
          "arguments": {
            "futureDays": 29
          },
          "writeResultTo": "/data/calendar",
          "candidateOutputFields": [
            "/events/0/title",
            "/events/0/dtStart",
            "/events/0/entityId"
          ]
        }
      ],
      "title": "发布会提醒",
      "size": "2x2",
      "candidateEventCandidates": [
        {
          "capabilityId": "event.viewCalendarEvent",
          "action": {
            "call": "clickToIntent",
            "args": {
              "intentName": "ViewCalendarEvent",
              "params": {
                "entityId": "{{ ${/data/calendar/events/0/entityId} }}"
              }
            }
          }
        }
      ],
      "description": "倒数日和日程",
      "candidateAssetIds": [
        "asset.alarm_fill_1",
        "asset.calendar_fill",
        "asset.stopwatch_fill"
      ]
    },
    "response": {
      "data": {
        "genui": "[\"root\", \"Layout\", {\"layout\": \"S-title-primary-secondary-action\", \"linearGradient\": {\"direction\": \"RightBottom\", \"colors\": [[\"#FFC7D8FB\", 0], [\"#FFEFE6FB\", 1]]}}, [\"header\", \"countdown\", \"event\", \"detail\"]]\n[\"header\", \"SingleLineTitle\", {\"title\": \"发布会提醒\", \"icon\": \"resources/base/media/alarm_fill_1.svg\", \"fontSize\": 12}]\n[\"countdown\", \"EmphasizedData\", {\"value\": {\"path\": \"/data/countdown/countdownDays\"}, \"unit\": \"天后\", \"fontSize\": 30}]\n[\"/data/countdown/countdownDays\", 18]\n[\"event\", \"EventCard\", {\"items\": [{\"title\": {\"path\": \"/data/calendar/events/0/title\"}, \"time\": {\"path\": \"/data/calendar/events/0/dtStart\"}}]}]\n[\"detail\", \"PillButton\", {\"label\": \"查看日程\", \"icon\": \"resources/base/media/calendar_fill.svg\", \"onClick\": [{\"call\": \"clickToIntent\", \"args\": {\"intentName\": \"ViewCalendarEvent\", \"params\": {\"entityId\": \"{{ ${/data/calendar/events/0/entityId} }}\"}}}]}]\n[\"/data/calendar/events/0/title\", \"产品发布会\"]\n[\"/data/calendar/events/0/dtStart\", \"上午10:00\"]\n[\"/data/calendar/events/0/entityId\", \"event-001\"]\n",
        "title": "发布会提醒",
        "cardSpec": {
          "suggestSize": "2x2"
        }
      }
    }
  },
  {
    "id": "run-Q004",
    "operation": "generateWidgetCardCompactDsl",
    "source": "interface",
    "status": "success",
    "startedAt": "2026-10-18T03:12:28+00:00",
    "finishedAt": "2026-10-18T03:12:32+00:00",
    "completedAt": "2026-10-18T03:12:32+00:00",
    "durationMs": 4000,
    "request": {
      "content": {
        "bundleName": "com.omega_w_0823.hmservice",
        "userQuery": "帮我做个天气预警卡片，重点看长沙当前天气预警和信息更新时间。",
        "candidateDataBindings": [
          {
            "capabilityId": "ViewWeather",
            "arguments": {
              "prefectureName": "长沙市",
              "forecastDays": 1
            },
            "writeResultTo": "/data/weather",
            "candidateOutputFields": [
              "/current/alertLevel",
              "/updatedAt"
            ]
          }
        ],
        "title": "天气预警",
        "size": "2x2",
        "candidateEventCandidates": [],
        "description": "预警和更新时间",
        "candidateAssetIds": [
          "asset.bell_fill",
          "asset.emoji_time",
          "asset.typhoon_fill"
        ]
      },
      "deviceInfo": {
        "countryCode": "CN",
        "deviceFormation": "HDSpeaker",
        "deviceType": 0,
        "locale": "zh-CN",
        "phoneType": "SGT-AL10",
        "prdVer": "11.9.9.342",
        "romVersion": "7.0",
        "sysVer": "EmotionUI_9.0.0",
        "time": "20260828000000000"
      },
      "pagination": {
        "limit": 5,
        "start": ""
      },
      "session": {
        "interactionId": "004",
        "isNew": true,
        "sessionId": "taskspec-829.2"
      },
      "userAuth": {
        "user": {
          "userId": ""
        }
      },
      "utterance": {
        "original": "帮我做个天气预警卡片，重点看长沙当前天气预警和信息更新时间。",
        "type": "text"
      },
      "version": "1.0",
      "bundleName": "com.omega_w_0823.hmservice",
      "userQuery": "帮我做个天气预警卡片，重点看长沙当前天气预警和信息更新时间。",
      "candidateDataBindings": [
        {
          "capabilityId": "ViewWeather",
          "arguments": {
            "prefectureName": "长沙市",
            "forecastDays": 1
          },
          "writeResultTo": "/data/weather",
          "candidateOutputFields": [
            "/current/alertLevel",
            "/updatedAt"
          ]
        }
      ],
      "title": "天气预警",
      "size": "2x2",
      "candidateEventCandidates": [],
      "description": "预警和更新时间",
      "candidateAssetIds": [
        "asset.bell_fill",
        "asset.emoji_time",
        "asset.typhoon_fill"
      ]
    },
    "response": {
      "data": {
        "genui": "[\"root\", \"Layout\", {\"layout\": \"S-center\", \"linearGradient\": {\"direction\": \"RightBottom\", \"colors\": [[\"#FFF3B6A6\", 0], [\"#FFF7E6C4\", 1]]}}, [\"display\"]]\n[\"display\", \"DataDisplay\", {\"label\": \"长沙天气预警\", \"value\": {\"path\": \"/data/weather/current/alertLevel\"}, \"supportingText\": {\"path\": \"/data/weather/updatedAt\"}, \"fontSize\": 18}]\n[\"/data/weather/current/alertLevel\", \"黄色预警\"]\n[\"/data/weather/updatedAt\", \"08:20\"]\n",
        "title": "天气预警",
        "cardSpec": {
          "suggestSize": "2x2"
        }
      }
    }
  },
  {
    "id": "run-Q005",
    "operation": "generateWidgetCardCompactDsl",
    "source": "interface",
    "status": "success",
    "startedAt": "2026-10-18T03:13:28+00:00",
    "finishedAt": "2026-10-18T03:13:32+00:00",
    "completedAt": "2026-10-18T03:13:32+00:00",
    "durationMs": 4000,
    "request": {
      "content": {
        "bundleName": "com.omega_w_0823.hmservice",
        "userQuery": "明天要在广州出门办事，帮我做个降雨卡片，看明天下雨概率，再看温度范围。",
        "candidateDataBindings": [
          {
            "capabilityId": "ViewWeather",
            "arguments": {
              "prefectureName": "广州市",
              "forecastDays": 2
            },
            "writeResultTo": "/data/weather",
            "candidateOutputFields": [
              "/daily/1/temperatureRangeText",
              "/daily/1/rainProbabilityPercent"
            ]
          }
        ],
        "title": "广州出行",
        "size": "2x2",
        "candidateEventCandidates": [],
        "description": "降雨概率和温度",
        "candidateAssetIds": [
          "asset.icon_weather_thermometer_medium",
          "asset.drop_1",
          "asset.calendar_fill"
        ]
      },
      "deviceInfo": {
        "countryCode": "CN",
        "deviceFormation": "HDSpeaker",
        "deviceType": 0,
        "locale": "zh-CN",
        "phoneType": "SGT-AL10",
        "prdVer": "11.9.9.342",
        "romVersion": "7.0",
        "sysVer": "EmotionUI_9.0.0",
        "time": "20260828000000000"
      },
      "pagination": {
        "limit": 5,
        "start": ""
      },
      "session": {
        "interactionId": "005",
        "isNew": true,
        "sessionId": "taskspec-829.2"
      },
      "userAuth": {
        "user": {
          "userId": ""
        }
      },
      "utterance": {
        "original": "明天要在广州出门办事，帮我做个降雨卡片，看明天下雨概率，再看温度范围。",
        "type": "text"
      },
      "version": "1.0",
      "bundleName": "com.omega_w_0823.hmservice",
      "userQuery": "明天要在广州出门办事，帮我做个降雨卡片，看明天下雨概率，再看温度范围。",
      "candidateDataBindings": [
        {
          "capabilityId": "ViewWeather",
          "arguments": {
            "prefectureName": "广州市",
            "forecastDays": 2
          },
          "writeResultTo": "/data/weather",
          "candidateOutputFields": [
            "/daily/1/temperatureRangeText",
            "/daily/1/rainProbabilityPercent"
          ]
        }
      ],
      "title": "广州出行",
      "size": "2x2",
      "candidateEventCandidates": [],
      "description": "降雨概率和温度",
      "candidateAssetIds": [
        "asset.icon_weather_thermometer_medium",
        "asset.drop_1",
        "asset.calendar_fill"
      ]
    },
    "response": {
      "data": {
        "genui": "[\"root\", \"Layout\", {\"layout\": \"S-title-dual-content\", \"linearGradient\": {\"direction\": \"RightBottom\", \"colors\": [[\"#FFBEE0F5\", 0], [\"#FFDFF0D8\", 1]]}}, [\"header\", \"rain\", \"temperature\"]]\n[\"header\", \"SingleLineTitle\", {\"title\": \"广州明天\", \"icon\": \"resources/base/media/calendar_fill.svg\", \"fontSize\": 12}]\n[\"rain\", \"ProgressCircleSingle\", {\"value\": {\"path\": \"/data/weather/daily/1/rainProbabilityPercent\"}, \"total\": 100, \"icon\": \"resources/base/media/drop_1.svg\", \"displayValue\": \"{{ ${/data/weather/daily/1/rainProbabilityPercent} + '%' }}\", \"label\": \"降雨概率\", \"color\": \"#FF1F4799\", \"backgroundColor\": \"#331F4799\"}]\n[\"temperature\", \"SecondaryBody\", {\"items\": [{\"label\": \"温度范围\", \"value\": {\"path\": \"/data/weather/daily/1/temperatureRangeText\"}}], \"fontSize\": 14}]\n[\"/data/weather/daily/1/rainProbabilityPercent\", 60]\n[\"/data/weather/daily/1/temperatureRangeText\", \"18~24℃\"]\n",
        "title": "广州出行",
        "cardSpec": {
          "suggestSize": "2x2"
        }
      }
    }
  },
  {
    "id": "run-Q006",
    "operation": "generateWidgetCardCompactDsl",
    "source": "interface",
    "status": "success",
    "startedAt": "2026-10-18T03:14:28+00:00",
    "finishedAt": "2026-10-18T03:14:32+00:00",
    "completedAt": "2026-10-18T03:14:32+00:00",
    "durationMs": 4000,
    "request": {
      "content": {
        "bundleName": "com.omega_w_0823.hmservice",
        "userQuery": "明天上午九点有产品立项会，下午三点有客户交流会，帮我做个卡片，分别看两场会议的标题和开始时间。",
        "candidateDataBindings": [
          {
            "capabilityId": "GetCalendarEvents",
            "arguments": {
              "futureDays": 1
            },
            "writeResultTo": "/data/calendar",
            "candidateOutputFields": [
              "/events/0/title",
              "/events/0/dtStart",
              "/events/1/title",
              "/events/1/dtStart"
            ]
          }
        ],
        "title": "明日双会",
        "size": "2x2",
        "candidateEventCandidates": [],
        "description": "两场会议安排",
        "candidateAssetIds": [
          "asset.calendar_fill",
          "asset.icon_schedule",
          "asset.icon_meeting"
        ]
      },
      "deviceInfo": {
        "countryCode": "CN",
        "deviceFormation": "HDSpeaker",
        "deviceType": 0,
        "locale": "zh-CN",
        "phoneType": "SGT-AL10",
        "prdVer": "11.9.9.342",
        "romVersion": "7.0",
        "sysVer": "EmotionUI_9.0.0",
        "time": "20260828000000000"
      },
      "pagination": {
        "limit": 5,
        "start": ""
      },
      "session": {
        "interactionId": "006",
        "isNew": true,
        "sessionId": "taskspec-829.2"
      },
      "userAuth": {
        "user": {
          "userId": ""
        }
      },
      "utterance": {
        "original": "明天上午九点有产品立项会，下午三点有客户交流会，帮我做个卡片，分别看两场会议的标题和开始时间。",
        "type": "text"
      },
      "version": "1.0",
      "bundleName": "com.omega_w_0823.hmservice",
      "userQuery": "明天上午九点有产品立项会，下午三点有客户交流会，帮我做个卡片，分别看两场会议的标题和开始时间。",
      "candidateDataBindings": [
        {
          "capabilityId": "GetCalendarEvents",
          "arguments": {
            "futureDays": 1
          },
          "writeResultTo": "/data/calendar",
          "candidateOutputFields": [
            "/events/0/title",
            "/events/0/dtStart",
            "/events/1/title",
            "/events/1/dtStart"
          ]
        }
      ],
      "title": "明日双会",
      "size": "2x2",
      "candidateEventCandidates": [],
      "description": "两场会议安排",
      "candidateAssetIds": [
        "asset.calendar_fill",
        "asset.icon_schedule",
        "asset.icon_meeting"
      ]
    },
    "response": {
      "data": {
        "genui": "[\"root\", \"Layout\", {\"layout\": \"S-title-content\", \"linearGradient\": {\"direction\": \"RightBottom\", \"colors\": [[\"#FFD5DDF3\", 0], [\"#FFF0E3F5\", 1]]}}, [\"header\", \"meetings\"]]\n[\"header\", \"SingleLineTitle\", {\"title\": \"明日两场会议\", \"icon\": \"resources/base/media/calendar_fill.svg\", \"fontSize\": 12}]\n[\"meetings\", \"EventCard\", {\"items\": [{\"title\": {\"path\": \"/data/calendar/events/0/title\"}, \"time\": {\"path\": \"/data/calendar/events/0/dtStart\"}}, {\"title\": {\"path\": \"/data/calendar/events/1/title\"}, \"time\": {\"path\": \"/data/calendar/events/1/dtStart\"}}]}]\n[\"/data/calendar/events/0/title\", \"产品立项会\"]\n[\"/data/calendar/events/0/dtStart\", \"09:00\"]\n[\"/data/calendar/events/1/title\", \"客户交流会\"]\n[\"/data/calendar/events/1/dtStart\", \"15:00\"]\n",
        "title": "明日双会",
        "cardSpec": {
          "suggestSize": "2x2"
        }
      }
    }
  },
  {
    "id": "run-Q007",
    "operation": "generateWidgetCardCompactDsl",
    "source": "interface",
    "status": "success",
    "startedAt": "2026-10-18T03:15:28+00:00",
    "finishedAt": "2026-10-18T03:15:32+00:00",
    "completedAt": "2026-10-18T03:15:32+00:00",
    "durationMs": 4000,
    "request": {
      "content": {
        "bundleName": "com.omega_w_0823.hmservice",
        "userQuery": "下一场日程是明天下午两点的客户方案交流会，帮我做个卡片，看会议地点、备注和结束时间。",
        "candidateDataBindings": [
          {
            "capabilityId": "GetCalendarEvents",
            "arguments": {
              "futureDays": 7
            },
            "writeResultTo": "/data/calendar",
            "candidateOutputFields": [
              "/events/0/eventLocation",
              "/events/0/description",
              "/events/0/dtEnd"
            ]
          }
        ],
        "title": "客户交流",
        "size": "2x2",
        "candidateEventCandidates": [],
        "description": "地点备注和结束",
        "candidateAssetIds": [
          "asset.icon_meeting",
          "asset.local_fill",
          "asset.icon_schedule"
        ]
      },
      "deviceInfo": {
        "countryCode": "CN",
        "deviceFormation": "HDSpeaker",
        "deviceType": 0,
        "locale": "zh-CN",
        "phoneType": "SGT-AL10",
        "prdVer": "11.9.9.342",
        "romVersion": "7.0",
        "sysVer": "EmotionUI_9.0.0",
        "time": "20260828000000000"
      },
      "pagination": {
        "limit": 5,
        "start": ""
      },
      "session": {
        "interactionId": "007",
        "isNew": true,
        "sessionId": "taskspec-829.2"
      },
      "userAuth": {
        "user": {
          "userId": ""
        }
      },
      "utterance": {
        "original": "下一场日程是明天下午两点的客户方案交流会，帮我做个卡片，看会议地点、备注和结束时间。",
        "type": "text"
      },
      "version": "1.0",
      "bundleName": "com.omega_w_0823.hmservice",
      "userQuery": "下一场日程是明天下午两点的客户方案交流会，帮我做个卡片，看会议地点、备注和结束时间。",
      "candidateDataBindings": [
        {
          "capabilityId": "GetCalendarEvents",
          "arguments": {
            "futureDays": 7
          },
          "writeResultTo": "/data/calendar",
          "candidateOutputFields": [
            "/events/0/eventLocation",
            "/events/0/description",
            "/events/0/dtEnd"
          ]
        }
      ],
      "title": "客户交流",
      "size": "2x2",
      "candidateEventCandidates": [],
      "description": "地点备注和结束",
      "candidateAssetIds": [
        "asset.icon_meeting",
        "asset.local_fill",
        "asset.icon_schedule"
      ]
    },
    "response": {
      "data": {
        "genui": "[\"root\", \"Layout\", {\"layout\": \"S-title-dual-content\", \"linearGradient\": {\"direction\": \"RightBottom\", \"colors\": [[\"#FFCFE0EE\", 0], [\"#FFE9E3F7\", 1]]}}, [\"header\", \"place\", \"detail\"]]\n[\"header\", \"SingleLineTitle\", {\"title\": \"客户方案交流会\", \"icon\": \"resources/base/media/icon_meeting.svg\", \"fontSize\": 12}]\n[\"place\", \"EmphasisText\", {\"mainText\": {\"path\": \"/data/calendar/events/0/eventLocation\"}, \"fontSize\": 18}]\n[\"/data/calendar/events/0/eventLocation\", \"珠江新城办公室\"]\n[\"detail\", \"SecondaryBody\", {\"items\": [{\"label\": \"备注\", \"value\": {\"path\": \"/data/calendar/events/0/description\"}}, {\"label\": \"结束\", \"value\": {\"path\": \"/data/calendar/events/0/dtEnd\"}}], \"columns\": 1, \"fontSize\": 12}]\n[\"/data/calendar/events/0/description\", \"带方案 PPT 初稿\"]\n[\"/data/calendar/events/0/dtEnd\", \"17:30\"]\n",
        "title": "客户交流",
        "cardSpec": {
          "suggestSize": "2x2"
        }
      }
    }
  },
  {
    "id": "run-Q008",
    "operation": "generateWidgetCardCompactDsl",
    "source": "interface",
    "status": "success",
    "startedAt": "2026-10-18T03:16:28+00:00",
    "finishedAt": "2026-10-18T03:16:32+00:00",
    "completedAt": "2026-10-18T03:16:32+00:00",
    "durationMs": 4000,
    "request": {
      "content": {
        "bundleName": "com.omega_w_0823.hmservice",
        "userQuery": "2天后要去北京出差，帮我做个卡片，看还有几天出发和北京当天的天气、温度范围。",
        "candidateDataBindings": [
          {
            "capabilityId": "GetCountdownDays",
            "arguments": {
              "targetDate": "2026-08-30"
            },
            "writeResultTo": "/data/countdown",
            "candidateOutputFields": [
              "/countdownDays"
            ]
          },
          {
            "capabilityId": "ViewWeather",
            "arguments": {
              "prefectureName": "北京市",
              "forecastDays": 3
            },
            "writeResultTo": "/data/weather",
            "candidateOutputFields": [
              "/daily/2/condition",
              "/daily/2/temperatureRangeText"
            ]
          }
        ],
        "title": "北京出差",
        "size": "2x2",
        "candidateEventCandidates": [],
        "description": "出发倒数和天气",
        "candidateAssetIds": [
          "asset.airplane_fill_1",
          "asset.icon_weather_thermometer_medium",
          "asset.stopwatch_fill",
          "asset.calendar_fill"
        ]
      },
      "deviceInfo": {
        "countryCode": "CN",
        "deviceFormation": "HDSpeaker",
        "deviceType": 0,
        "locale": "zh-CN",
        "phoneType": "SGT-AL10",
        "prdVer": "11.9.9.342",
        "romVersion": "7.0",
        "sysVer": "EmotionUI_9.0.0",
        "time": "20260828000000000"
      },
      "pagination": {
        "limit": 5,
        "start": ""
      },
      "session": {
        "interactionId": "008",
        "isNew": true,
        "sessionId": "taskspec-829.2"
      },
      "userAuth": {
        "user": {
          "userId": ""
        }
      },
      "utterance": {
        "original": "2天后要去北京出差，帮我做个卡片，看还有几天出发和北京当天的天气、温度范围。",
        "type": "text"
      },
      "version": "1.0",
      "bundleName": "com.omega_w_0823.hmservice",
      "userQuery": "2天后要去北京出差，帮我做个卡片，看还有几天出发和北京当天的天气、温度范围。",
      "candidateDataBindings": [
        {
          "capabilityId": "GetCountdownDays",
          "arguments": {
            "targetDate": "2026-08-30"
          },
          "writeResultTo": "/data/countdown",
          "candidateOutputFields": [
            "/countdownDays"
          ]
        },
        {
          "capabilityId": "ViewWeather",
          "arguments": {
            "prefectureName": "北京市",
            "forecastDays": 3
          },
          "writeResultTo": "/data/weather",
          "candidateOutputFields": [
            "/daily/2/condition",
            "/daily/2/temperatureRangeText"
          ]
        }
      ],
      "title": "北京出差",
      "size": "2x2",
      "candidateEventCandidates": [],
      "description": "出发倒数和天气",
      "candidateAssetIds": [
        "asset.airplane_fill_1",
        "asset.icon_weather_thermometer_medium",
        "asset.stopwatch_fill",
        "asset.calendar_fill"
      ]
    },
    "response": {
      "data": {
        "genui": "[\"root\", \"Layout\", {\"layout\": \"S-title-content\", \"linearGradient\": {\"direction\": \"RightBottom\", \"colors\": [[\"#FFBFE3E0\", 0], [\"#FFE9F5C4\", 1]]}}, [\"header\", \"trip\"]]\n[\"header\", \"SingleLineTitle\", {\"title\": \"北京出差\", \"icon\": \"resources/base/media/airplane_fill_1.svg\", \"fontSize\": 12}]\n[\"trip\", \"Group\", {\"variant\": \"hero-support\"}, [\"countdown\", \"weather\"]]\n[\"countdown\", \"EmphasizedData\", {\"value\": {\"path\": \"/data/countdown/countdownDays\"}, \"unit\": \"天后\", \"fontSize\": 30}]\n[\"/data/countdown/countdownDays\", 2]\n[\"weather\", \"SecondaryBody\", {\"items\": [{\"label\": \"天气\", \"value\": {\"path\": \"/data/weather/daily/2/condition\"}}, {\"label\": \"温度\", \"value\": {\"path\": \"/data/weather/daily/2/temperatureRangeText\"}}], \"fontSize\": 14}]\n[\"/data/weather/daily/2/condition\", \"多云\"]\n[\"/data/weather/daily/2/temperatureRangeText\", \"18~24℃\"]\n",
        "title": "北京出差",
        "cardSpec": {
          "suggestSize": "2x2"
        }
      }
    }
  },
  {
    "id": "run-Q009",
    "operation": "generateWidgetCardCompactDsl",
    "source": "interface",
    "status": "success",
    "startedAt": "2026-10-18T03:17:28+00:00",
    "finishedAt": "2026-10-18T03:17:32+00:00",
    "completedAt": "2026-10-18T03:17:32+00:00",
    "durationMs": 4000,
    "request": {
      "content": {
        "bundleName": "com.omega_w_0823.hmservice",
        "userQuery": "帮我做个耳机状态卡片，分别看左右耳机电量，再看各自是否在充电。",
        "candidateDataBindings": [
          {
            "capabilityId": "GetEarphoneInfo",
            "arguments": {},
            "writeResultTo": "/data/earphone",
            "candidateOutputFields": [
              "/leftBatteryLevel",
              "/leftChargingStatusDesc",
              "/rightBatteryLevel",
              "/rightChargingStatusDesc"
            ]
          }
        ],
        "title": "左右耳机",
        "size": "2x2",
        "candidateEventCandidates": [],
        "description": "双耳电量和充电状态",
        "candidateAssetIds": [
          "asset.icon_left",
          "asset.icon_right",
          "asset.icon_earphone",
          "asset.bolt_fill"
        ]
      },
      "deviceInfo": {
        "countryCode": "CN",
        "deviceFormation": "HDSpeaker",
        "deviceType": 0,
        "locale": "zh-CN",
        "phoneType": "SGT-AL10",
        "prdVer": "11.9.9.342",
        "romVersion": "7.0",
        "sysVer": "EmotionUI_9.0.0",
        "time": "20260828000000000"
      },
      "pagination": {
        "limit": 5,
        "start": ""
      },
      "session": {
        "interactionId": "009",
        "isNew": true,
        "sessionId": "taskspec-829.2"
      },
      "userAuth": {
        "user": {
          "userId": ""
        }
      },
      "utterance": {
        "original": "帮我做个耳机状态卡片，分别看左右耳机电量，再看各自是否在充电。",
        "type": "text"
      },
      "version": "1.0",
      "bundleName": "com.omega_w_0823.hmservice",
      "userQuery": "帮我做个耳机状态卡片，分别看左右耳机电量，再看各自是否在充电。",
      "candidateDataBindings": [
        {
          "capabilityId": "GetEarphoneInfo",
          "arguments": {},
          "writeResultTo": "/data/earphone",
          "candidateOutputFields": [
            "/leftBatteryLevel",
            "/leftChargingStatusDesc",
            "/rightBatteryLevel",
            "/rightChargingStatusDesc"
          ]
        }
      ],
      "title": "左右耳机",
      "size": "2x2",
      "candidateEventCandidates": [],
      "description": "双耳电量和充电状态",
      "candidateAssetIds": [
        "asset.icon_left",
        "asset.icon_right",
        "asset.icon_earphone",
        "asset.bolt_fill"
      ]
    },
    "response": {
      "data": {
        "genui": "[\"root\", \"Layout\", {\"layout\": \"S-dual-info\", \"linearGradient\": {\"direction\": \"RightBottom\", \"colors\": [[\"#FFD7E3F0\", 0], [\"#FFE8D9F5\", 1]]}}, [\"left\", \"right\"]]\n[\"left\", \"InfoBlock\", {\"primaryText\": {\"path\": \"/data/earphone/leftBatteryLevel\"}, \"unit\": \"%\", \"secondaryText\": {\"path\": \"/data/earphone/leftChargingStatusDesc\"}, \"backgroundColor\": \"#CCFFFFFF\", \"visual\": {\"type\": \"icon\", \"icon\": \"resources/base/media/icon_left.svg\"}}]\n[\"/data/earphone/leftBatteryLevel\", 82]\n[\"/data/earphone/leftChargingStatusDesc\", \"充电中\"]\n[\"right\", \"InfoBlock\", {\"primaryText\": {\"path\": \"/data/earphone/rightBatteryLevel\"}, \"unit\": \"%\", \"secondaryText\": {\"path\": \"/data/earphone/rightChargingStatusDesc\"}, \"backgroundColor\": \"#CCFFFFFF\", \"visual\": {\"type\": \"icon\", \"icon\": \"resources/base/media/icon_right.svg\"}}]\n[\"/data/earphone/rightBatteryLevel\", 76]\n[\"/data/earphone/rightChargingStatusDesc\", \"未充电\"]\n",
        "title": "左右耳机",
        "cardSpec": {
          "suggestSize": "2x2"
        }
      }
    }
  },
  {
    "id": "run-Q010",
    "operation": "generateWidgetCardCompactDsl",
    "source": "interface",
    "status": "success",
    "startedAt": "2026-10-18T03:18:28+00:00",
    "finishedAt": "2026-10-18T03:18:32+00:00",
    "completedAt": "2026-10-18T03:18:32+00:00",
    "durationMs": 4000,
    "request": {
      "content": {
        "bundleName": "com.omega_w_0823.hmservice",
        "userQuery": "周末准备去杭州露营，帮我做个卡片，分别看杭州明天和后天的天气、空气质量。",
        "candidateDataBindings": [
          {
            "capabilityId": "ViewWeather",
            "arguments": {
              "prefectureName": "杭州市",
              "forecastDays": 3
            },
            "writeResultTo": "/data/weather",
            "candidateOutputFields": [
              "/daily/1/condition",
              "/daily/1/airQuality",
              "/daily/2/condition",
              "/daily/2/airQuality"
            ]
          }
        ],
        "title": "周末露营",
        "size": "2x2",
        "candidateEventCandidates": [],
        "description": "天气和空气质量",
        "candidateAssetIds": [
          "asset.sun_max",
          "asset.local_fill"
        ]
      },
      "deviceInfo": {
        "countryCode": "CN",
        "deviceFormation": "HDSpeaker",
        "deviceType": 0,
        "locale": "zh-CN",
        "phoneType": "SGT-AL10",
        "prdVer": "11.9.9.342",
        "romVersion": "7.0",
        "sysVer": "EmotionUI_9.0.0",
        "time": "20260828000000000"
      },
      "pagination": {
        "limit": 5,
        "start": ""
      },
      "session": {
        "interactionId": "010",
        "isNew": true,
        "sessionId": "taskspec-829.2"
      },
      "userAuth": {
        "user": {
          "userId": ""
        }
      },
      "utterance": {
        "original": "周末准备去杭州露营，帮我做个卡片，分别看杭州明天和后天的天气、空气质量。",
        "type": "text"
      },
      "version": "1.0",
      "bundleName": "com.omega_w_0823.hmservice",
      "userQuery": "周末准备去杭州露营，帮我做个卡片，分别看杭州明天和后天的天气、空气质量。",
      "candidateDataBindings": [
        {
          "capabilityId": "ViewWeather",
          "arguments": {
            "prefectureName": "杭州市",
            "forecastDays": 3
          },
          "writeResultTo": "/data/weather",
          "candidateOutputFields": [
            "/daily/1/condition",
            "/daily/1/airQuality",
            "/daily/2/condition",
            "/daily/2/airQuality"
          ]
        }
      ],
      "title": "周末露营",
      "size": "2x2",
      "candidateEventCandidates": [],
      "description": "天气和空气质量",
      "candidateAssetIds": [
        "asset.sun_max",
        "asset.local_fill"
      ]
    },
    "response": {
      "data": {
        "genui": "[\"root\", \"Layout\", {\"layout\": \"S-title-dual-content\", \"variant\": \"stacked-info\", \"linearGradient\": {\"direction\": \"RightBottom\", \"colors\": [[\"#FFA9DCC8\", 0], [\"#FFDDEFC1\", 1]]}}, [\"header\", \"tomorrow\", \"after\"]]\n[\"header\", \"SingleLineTitle\", {\"title\": \"杭州周末\", \"icon\": \"resources/base/media/local_fill.svg\", \"fontSize\": 12}]\n[\"tomorrow\", \"InfoBlock\", {\"variant\": \"stacked\", \"primaryText\": \"{{ '明天 ' + ${/data/weather/daily/1/condition} }}\", \"secondaryText\": \"{{ '空气质量 ' + ${/data/weather/daily/1/airQuality} }}\", \"backgroundColor\": \"#CCFFFFFF\"}]\n[\"/data/weather/daily/1/condition\", \"晴\"]\n[\"/data/weather/daily/1/airQuality\", \"优\"]\n[\"after\", \"InfoBlock\", {\"variant\": \"stacked\", \"primaryText\": \"{{ '后天 ' + ${/data/weather/daily/2/condition} }}\", \"secondaryText\": \"{{ '空气质量 ' + ${/data/weather/daily/2/airQuality} }}\", \"backgroundColor\": \"#CCFFFFFF\"}]\n[\"/data/weather/daily/2/condition\", \"多云\"]\n[\"/data/weather/daily/2/airQuality\", \"良\"]\n",
        "title": "周末露营",
        "cardSpec": {
          "suggestSize": "2x2"
        }
      }
    }
  }
];
const KEY = 'ai-widget-debug-call-history:v1';
const stored = JSON.parse(sessionStorage.getItem(KEY) || '{"calls":[]}');
const fresh = (record) => !RECORDS.some((item) => item.id === record.id);
stored.calls = [...(stored.calls || []).filter(fresh), ...RECORDS];
stored.selectedCallId = RECORDS[RECORDS.length - 1].id;
sessionStorage.setItem(KEY, JSON.stringify(stored));
location.reload();
