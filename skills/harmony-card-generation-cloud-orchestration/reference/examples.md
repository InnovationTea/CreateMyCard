# 样例

## 10 条回归 Query

1. 帮我做一张 2x2 天气卡片，显示上海青浦今天的温度、天气和空气质量，点一下能打开天气详情。
2. 生成一个通勤卡片，早上看天气、今天第一个会议和去公司的入口。
3. 做一个今天日程卡，显示下一场会议的标题和时间，点击可以进入会议详情。
4. 帮我创建一个一键入会卡片，显示下一场线上会议并提供加入按钮。
5. 做一个手机状态卡，展示内存状态，底部按钮可以一键清理运行内存。
6. 给我做一张抖音使用时长和耗电卡，显示前台时长、前台耗电和更新时间。
7. 做一个给妈妈打电话的桌面卡片，按钮点一下进入拨号界面。
8. 创建一个导航卡片，按钮用于导航回家，只要一个明确入口。
9. 帮我做一个音乐卡片，点击打开每日推荐歌单。
10. 做一个省电模式卡片，可以一键开启省电模式，并展示当前是系统设置相关操作。

## 工具调用样例：天气通勤卡

1. `getWidgetCapabilityOverview`

```json
{
  "locale": "zh-CN"
}
```

2. `getDataCapabilitySchemas`

```json
{
  "dataCapabilityIds": ["ViewWeather", "calendar.events.search"]
}
```

3. `generateWidgetCard`

```json
{
  "requestId": "auto-generated-uuid",
  "userQuery": "生成一个通勤卡片，早上看天气、今天第一个会议和去公司的入口。",
  "size": "2x4",
  "candidateDataBindings": [
    {
      "capabilityId": "ViewWeather",
      "arguments": {
        "districtName": "青浦区",
        "forecastDays": 1
      },
      "writeResultTo": "/data/weather",
      "required": false
    },
    {
      "capabilityId": "calendar.events.search",
      "arguments": {
        "timeRange": "today"
      },
      "writeResultTo": "/data/calendar",
      "required": false
    }
  ],
  "candidateEventCapabilityIds": [
    "clickToDeeplink.weather",
    "clickToIntent.StartNavigate"
  ],
  "candidateAssetIds": [
    "asset.weather.rain",
    "asset.calendar.schedule"
  ],
  "slots": {
    "districtName": "青浦区",
    "timeRange": "today",
    "target": "company"
  },
  "options": {
    "allowDegradation": true,
    "returnMode": "obs_url"
  }
}
```

## 工具调用样例：应用使用时长

```json
{
  "requestId": "auto-generated-uuid",
  "userQuery": "给我做一张抖音使用时长和耗电卡，显示前台时长、前台耗电和更新时间。",
  "size": "2x2",
  "candidateDataBindings": [
    {
      "capabilityId": "GetAppUsageDurationAndPower",
      "arguments": {
        "appBundleName": "com.ss.hm.ugc.aweme",
        "itemName": "foreground_time_power"
      },
      "writeResultTo": "/data/appUsageStats",
      "required": true
    }
  ],
  "candidateEventCapabilityIds": [],
  "candidateAssetIds": [],
  "slots": {
    "appName": "抖音",
    "appBundleName": "com.ss.hm.ugc.aweme"
  },
  "options": {
    "allowDegradation": true,
    "returnMode": "obs_url"
  }
}
```

## 用户回复话术样例

success：

````text
已为你生成通勤卡片。

```genWidgetResult:"https://obs.example/widget/123.json"```
````

degraded：

````text
日历权限当前未开启，我先为你生成只包含天气和通勤入口的卡片。开启日历权限后可以再生成包含今日日程的版本。

```genWidgetResult:"https://obs.example/widget/456.json"```
````

unsupported：

```text
当前设备上没有可用的外卖配送数据能力，也没有可打开的应用入口，所以暂时不能生成实时外卖卡片。

可以试试天气、日历、系统状态、应用使用时长或打开应用入口类卡片。
```

failed：

```text
卡片生成服务暂时不可用，请稍后再试。
```
