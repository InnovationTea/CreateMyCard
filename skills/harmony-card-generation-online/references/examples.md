# 联调与回归样例

仅在联调、排障或核对回归行为时读取。所有调用都必须再次按当前运行时 schema 校验；示例不能授权额外字段。

## 导航

- [场景矩阵](#场景矩阵)
- [动态 create：天气与下一场日程](#动态-create天气与下一场日程)
- [静态入口 create](#静态入口-create)
- [权限未通过](#权限未通过)
- [连续编辑](#连续编辑)
- [结果映射速查](#结果映射速查)
- [URL 交付回归](#url-交付回归)

## 场景矩阵

| 请求或上下文 | 预期决策 | 调用轨迹 |
| --- | --- | --- |
| 卡片创建页面要求撰写长报告 | 结束并引导 | 零调用 |
| 外卖实时配送卡，overview 无相关核心能力 | 结束并引导 | overview |
| 天气和股票都要，股票没有就不生成 | 结束并引导 | overview |
| 天气加股票，只有天气可用且仍有独立价值 | 调整后生成 | overview → schema → permission → generate |
| 天气卡片，点击详情是次要诉求但事件不可用 | 调整后生成 | overview → schema → permission → generate |
| 打开天气详情是唯一核心动作但事件不可用 | 结束并引导 | overview |
| 最后一个核心数据能力进入 `missingCapabilityIds` | 结束并引导 | overview → schema |
| 打开天气应用的静态入口卡 | 继续生成 | overview → generate |
| edit“背景改成蓝色”，来源含动态数据 | 继续编辑 | permission → generate |
| edit“背景改成蓝色”，来源无动态数据 | 继续编辑 | generate |
| edit“去掉日历，只保留天气” | 继续编辑 | overview → schema → permission → generate |
| edit“再加股票数据” | 引导重新创建 | 零调用 |
| overview、权限或生成工具结果非法 | 其它异常 | 当前工具后终止 |

尺寸回归：

- 未指定尺寸，天气与下一场日程可通过摘要在一个主问题中表达：使用 `2x2`。
- 未指定尺寸，删去可选项后仍无法容纳必须同屏的核心内容和必要热区：允许使用 `2x4`。
- 用户明确指定 `2x4`：优先遵从。

## 动态 create：天气与下一场日程

用户：

```text
做一张通勤卡片，显示上海青浦今天的天气和下一场日程。
```

### 1. 能力概述

```text
invoke(functionName:"getWidgetCapabilityOverview", arguments:{
  bundleName:"com.omega_w_0823.hmservice"
},"skillName":"harmony-card-generation-online")
```

假设业务 payload 提供 `ViewWeather`、`GetCalendarEvents`，且未返回可用点击事件。

### 2. 加载 schema

```text
invoke(functionName:"getDataCapabilitySchemas", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  dataCapabilityIds:["ViewWeather","GetCalendarEvents"]
},"skillName":"harmony-card-generation-online")
```

候选参数和字段必须取自本轮 schema。日历使用当前契约的 `futureDays`，不得使用旧参数或旧能力 ID。

### 3. 权限门禁

```text
invoke(functionName:"RequestDataPermission", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  dataCapabilityIds:["ViewWeather","GetCalendarEvents"]
},"skillName":"harmony-card-generation-online")
```

只有以下结果，且不存在任何权限项为 Boolean `false` 时才继续：

```json
{
  "result": {
    "stateOfPermission": true
  }
}
```

### 4. 生成

天气和下一场日程经过摘要可以在 `2x2` 完整表达，因此不因存在两个数据能力升级为 `2x4`：

```text
invoke(functionName:"generateWidgetCardCompactDsl", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  userQuery:"做一张通勤卡片，显示上海青浦今天的天气和下一场日程。",
  title:"通勤助手",
  description:"天气日程速览",
  size:"2x2",
  candidateDataBindings:[
    {
      capabilityId:"ViewWeather",
      arguments:{
        districtName:"青浦区",
        forecastDays:1
      },
      writeResultTo:"/data/weather",
      candidateOutputFields:[
        "/current/temperatureText",
        "/current/condition"
      ]
    },
    {
      capabilityId:"GetCalendarEvents",
      arguments:{
        futureDays:1
      },
      writeResultTo:"/data/calendar",
      candidateOutputFields:[
        "/events/0/title",
        "/events/0/dtStart"
      ]
    }
  ],
  candidateEventCandidates:[],
  candidateAssetIds:[]
},"skillName":"harmony-card-generation-online")
```

若返回：

```json
{
  "status": "success",
  "message": "已为你生成通勤卡片。",
  "artifactUrl": "https://obs.example/widget/123.md"
}
```

回复：

````text
已为你生成通勤卡片。

```genWidgetResult
{
  "result": "https://obs.example/widget/123.md"
}
```
````

## 静态入口 create

用户：

```text
做一个打开天气应用的入口卡片。
```

overview 返回可安全填齐的天气入口事件后，不加载数据 schema，也不调用权限工具：

```text
invoke(functionName:"generateWidgetCardCompactDsl", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  userQuery:"做一个打开天气应用的入口卡片。",
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
  candidateAssetIds:[]
},"skillName":"harmony-card-generation-online")
```

事件 action 必须来自本轮 overview；示例值不能替代实际返回。

## 权限未通过

假设权限结果：

```json
{
  "result": {
    "stateOfPermission": false,
    "nonAuthStatus": [
      {
        "capabilityId": "GetAppUsageDurationAndPower",
        "authorized": false,
        "authType": "NON_CONFIGURABLE",
        "name": "应用使用时长",
        "settingsPath": "设置-健康使用设备-使用统计和管理"
      }
    ]
  }
}
```

立即终止，不调用生成工具，只回复：

```text
请前往「设置-健康使用设备-使用统计和管理」，为「应用使用时长」开启权限，然后再试。
```

没有有效授权明细时固定回复：

```text
当前生成卡片所需的数据权限不可用，已停止生成。
```

## 连续编辑

假设上一轮有效业务结果为：

```json
{
  "status": "success",
  "artifactUrl": "https://obs.example/widget/v1.md",
  "effectiveCapabilities": {
    "data": ["ViewWeather", "GetCalendarEvents"]
  }
}
```

### 纯视觉 edit

用户：“背景改成蓝色，信息排紧凑一点。”

先对来源的完整数据能力集合执行权限门禁，通过后调用：

```text
invoke(functionName:"generateWidgetCardCompactDsl", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  userQuery:"背景改成蓝色，信息排紧凑一点",
  sourceArtifactUrl:"https://obs.example/widget/v1.md"
},"skillName":"harmony-card-generation-online")
```

不重复传未修改的标题、尺寸或候选数组。

### 删除日历

用户：“去掉日历，只保留天气。”

重新获取 overview 和天气 schema，恢复并校验编辑后的完整数据候选，只对 `ViewWeather` 检查权限。通过后调用：

```text
invoke(functionName:"generateWidgetCardCompactDsl", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  userQuery:"去掉日历，只保留天气",
  sourceArtifactUrl:"https://obs.example/widget/v1.md",
  candidateDataBindings:[
    {
      capabilityId:"ViewWeather",
      arguments:{
        districtName:"青浦区",
        forecastDays:1
      },
      writeResultTo:"/data/weather",
      candidateOutputFields:[
        "/location/districtName",
        "/current/temperatureText",
        "/current/condition"
      ]
    }
  ]
},"skillName":"harmony-card-generation-online")
```

这里的数组是完整替换，不是增量。删除全部动态数据时传 `candidateDataBindings:[]`，并跳过权限工具。

若 edit 成功返回 `https://obs.example/widget/v2.md`，下一轮默认使用 v2；新 URL 缺失、无效或仍为 v1 时按其它异常，继续保留 v1。

### 新增能力

用户：“再加上股票数据。”

本期不调用工具：

```text
当前连续编辑暂不支持新增股票数据，这次先不修改。你可以重新创建一张卡片，例如：“重新创建一张同时展示天气和股票的桌面卡片”
```

## 结果映射速查

| 结果 | 回复 |
| --- | --- |
| 完整 `success` + URL | 使用 `message`，输出 URL 标记 |
| `degraded` + URL | 使用对应部分满足话术，输出 URL 标记 |
| 已知部分缺失的 `success` + URL | 按部分满足处理，输出 URL 标记 |
| `unsupported` 无 URL | 整体不支持话术 + 安全建议 |
| `failed` 或工具异常无 URL | 固定其它异常话术 |
| 任意可解析 payload 含合法真实 URL | 无论状态均输出 URL 标记 |

## URL 交付回归

生成工具返回后，以业务 payload 的 `artifactUrl` 作为唯一交付触发器。至少回归以下场景：

| 业务 payload | 最终回复要求 |
| --- | --- |
| `success` + 合法 URL + 非空 `message` | `message` 后紧接且只接一个 URL 标记 |
| `degraded` + 合法 URL | 受控部分满足话术后紧接且只接一个 URL 标记 |
| `unsupported` / `failed` + 合法 URL | 对应受控话术后仍紧接且只接一个 URL 标记 |
| 可解析异常 payload + 合法 URL | 其它异常话术后仍紧接且只接一个 URL 标记 |
| `success` / `degraded` 无合法 URL | 其它异常话术，不输出标记 |
| 只有 `streamInfo` 或普通文本含 URL | 不输出标记 |
| edit 返回与 `sourceArtifactUrl` 相同的 URL | 按无有效新 URL 处理，不输出标记，不更新来源 |

每个有 URL 的用例都必须同时断言：代码块数量为 1、语言标签为 `genWidgetResult`、块内 JSON 可解析、仅有 `result` 字段、字段值与当前业务 payload URL 完全一致、代码块后无其它内容。仅检查自然语言包含“已生成”不算通过。
