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

说明：以下示例统一通过 `invoke(functionName:"工具名", arguments:{bundleName:"com.omega_w_0823.hmservice", ...},"skillName":"harmony-card-generation-online")` 调用工具。`skillName` 必须与当前 Skill frontmatter 的 `name` 完全一致。每次调用前先检查是否有会影响核心意图、候选选择或业务入参的用户待确认项；有则先追问并等待回答，再以当前运行时 `tools` 中对应工具的 schema 校验字段名、必填项、类型和嵌套结构。schema 未声明字段一律不传，示例不能覆盖运行时 schema。不要构造内部 `content/deviceInfo/session` 包络。示例中的 `timeInterval` 使用 2026-07-06 Asia/Shanghai 的当天毫秒区间；实际执行时按用户本地时区和当前日期计算。

## 调用前追问样例

用户说“做一个给家人打电话的桌面卡片”，但没有说明联系人或号码。该目标会影响核心动作参数，因此在调用第一个工具前先追问：

```text
你希望卡片拨打哪位联系人或哪个号码？
```

等待用户回答后再从工作流当前步骤继续。不要先调用 overview，不要猜测联系人，也不要把拨号动作静默删除后生成另一种卡片。

1. `getWidgetCapabilityOverview`

```text
invoke(functionName:"getWidgetCapabilityOverview", arguments:{
  bundleName:"com.omega_w_0823.hmservice"
},"skillName":"harmony-card-generation-online")
```

解析业务 `data` 后先应用不可用能力过滤。例如：

```json
{
  "dataCapabilities": [
    {"id": "ViewWeather", "description": "查询天气"},
    {"id": "GetAppUsageDurationAndPower", "description": "查询应用使用时长和耗电"}
  ],
  "unavailableCapabilities": ["GetAppUsageDurationAndPower"],
  "eventCapabilities": [],
  "assetCandidates": []
}
```

此时只能继续选择 `ViewWeather`；不得为 `GetAppUsageDurationAndPower` 请求 schema 或构造数据绑定。

如果 `unavailableCapabilities` 缺失或为 `[]`，表示没有预先标记的不可用数据能力，继续从全部 `dataCapabilities` 中筛选。

2. `getDataCapabilitySchemas`

```text
invoke(functionName:"getDataCapabilitySchemas", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  dataCapabilityIds:["ViewWeather", "calendar.events.search"]
},"skillName":"harmony-card-generation-online")
```

3. `generateWidgetCard`

```text
invoke(functionName:"generateWidgetCard", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  userQuery:"生成一个通勤卡片，早上看天气、今天第一个会议和去公司的入口。",
  title:"通勤助手",
  description:"天气日程速览",
  size:"2x4",
  candidateDataBindings:[
    {
      capabilityId:"ViewWeather",
      arguments:{
        districtName:"青浦区",
        forecastDays:1
      },
      writeResultTo:"/data/weather",
      candidateOutputFields:[
        "/location/name",
        "/current/temperatureText",
        "/current/weatherText"
      ]
    },
    {
      capabilityId:"calendar.events.search",
      arguments:{
        timeInterval:[1783238400000, 1783324799999]
      },
      writeResultTo:"/data/calendar",
      candidateOutputFields:[
        "/events/0/title",
        "/events/0/startTimeText",
        "/events/0/location"
      ]
    }
  ],
  candidateEventCandidates:[
    {
      capabilityId:"event.open.weather",
      action:{
        call:"clickToDeeplink",
        args:{
          bundleName:"",
          abilityName:"",
          uri:"hww://www.huawei.com/totemweather?enterType=share&cityCode="
        }
      }
    }
  ],
  candidateAssetIds:["asset.weather.rain", "asset.calendar.schedule"]
},"skillName":"harmony-card-generation-online")
```

## 工具调用样例：应用使用时长

仅当 `getWidgetCapabilityOverview` 返回 `GetAppUsageDurationAndPower`，且该 ID 不在 `unavailableCapabilities` 中时才使用该候选。

```text
invoke(functionName:"generateWidgetCard", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  userQuery:"给我做一张抖音使用时长和耗电卡，显示前台时长、前台耗电和更新时间。",
  title:"使用时长",
  description:"时长耗电统计",
  size:"2x2",
  candidateDataBindings:[
    {
      capabilityId:"GetAppUsageDurationAndPower",
      arguments:{
        appBundleName:"com.ss.hm.ugc.aweme",
        itemName:"foreground_time_power"
      },
      writeResultTo:"/data/appUsageStats"
    }
  ],
  candidateEventCandidates:[],
  candidateAssetIds:[]
},"skillName":"harmony-card-generation-online")
```

## 工具调用样例：打开天气应用入口

没有动态数据需求时，`candidateDataBindings` 可以为空；让微服务决定是否生成静态入口卡。

```text
invoke(functionName:"generateWidgetCard", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  userQuery:"帮我做一个打开天气应用的入口卡片",
  title:"天气入口",
  description:"快速打开天气",
  size:"2x2",
  candidateDataBindings:[],
  candidateEventCandidates:[
    {
      capabilityId:"event.open.weather",
      action:{
        call:"clickToDeeplink",
        args:{
          bundleName:"",
          abilityName:"",
          uri:"hww://www.huawei.com/totemweather?enterType=share&cityCode="
        }
      }
    }
  ],
  candidateAssetIds:["asset.weather.rain"]
},"skillName":"harmony-card-generation-online")
```

## 工具调用样例：不支持的外卖实时状态

如果 overview 没有外卖配送数据能力，也没有打开对应应用的事件能力，不要编造能力；仍可把原始意图交给微服务裁决。

```text
invoke(functionName:"generateWidgetCard", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  userQuery:"帮我做一个美团外卖配送状态卡片",
  title:"外卖状态",
  description:"配送进度提醒",
  size:"2x2",
  candidateDataBindings:[],
  candidateEventCandidates:[],
  candidateAssetIds:[]
},"skillName":"harmony-card-generation-online")
```

## 工具返回解析示例

三个工具都返回包装结构，业务结果需要从 `items[].data` 解析：

```json
{
  "streamInfo": "",
  "items": [
    {
      "tool": "generateWidgetCard",
      "status": "success",
      "data": "{\"status\":\"success\",\"message\":\"已为你生成通勤卡片。\",\"artifactUrl\":\"https://obs.example/widget/123.json\",\"suggestSize\":\"2x4\"}"
    }
  ]
}
```

解析 `data` 后，再按其中的业务 `status/message/artifactUrl` 回复用户。最终 `genWidgetResult` 必须使用 JSON 代码块格式，`result` 的值取业务 payload 的真实 `artifactUrl`。

## 对象结构注意事项

当前工具 schema 已显式声明 `candidateDataBindings` 数组项的 `capabilityId`、`arguments`、`writeResultTo` 和可选 `candidateOutputFields`；必须严格按这些字段组装。`candidateEventCandidates` 数组项仍是宽类型 `Object`，按内部事件契约组装，但不得扩展工具顶层入参。

正确的 `CandidateDataBinding`：

```json
{
  "capabilityId": "ViewWeather",
  "arguments": {
    "districtName": "青浦区",
    "forecastDays": 1
  },
  "writeResultTo": "/data/weather",
  "candidateOutputFields": [
    "/location/name",
    "/current/temperatureText",
    "/current/weatherText"
  ]
}
```

`candidateOutputFields` 是可选字符串数组；每个 JSON Pointer 必须存在于该能力本轮返回的 `outputSchema`。不要传旧字段 `updateModel`。

不要把能力参数平铺成：

```json
{
  "capabilityId": "ViewWeather",
  "districtName": "青浦区",
  "forecastDays": 1,
  "writeResultTo": "/data/weather"
}
```

正确的 `CandidateEventCandidate`：

```json
{
  "capabilityId": "event.open.weather",
  "action": {
    "call": "clickToDeeplink",
    "args": {
      "bundleName": "",
      "abilityName": "",
      "uri": "hww://www.huawei.com/totemweather?enterType=share&cityCode="
    }
  }
}
```

不要把事件动作平铺成：

```json
{
  "capabilityId": "event.open.weather",
  "call": "clickToDeeplink",
  "uri": "hww://www.huawei.com/totemweather?enterType=share&cityCode="
}
```

## 用户回复话术样例

success：

````text
已为你生成通勤卡片。

```genWidgetResult
{
  "result": "https://obs.example/widget/123.json"
}
```
````

degraded：

````text
日历权限当前未开启，我先为你生成只包含天气和通勤入口的卡片。开启日历权限后可以再生成包含今日日程的版本。

```genWidgetResult
{
  "result": "https://obs.example/widget/456.json"
}
```
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

工具不可用或结果异常：

```text
卡片生成服务暂时不可用，请稍后再试。
```
