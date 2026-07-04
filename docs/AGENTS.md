# AI 卡片云侧开发指导

本文档面向参与本项目开发的工程师和 AI 编码助手。目标是把 `docs/云侧方案设计.md` 中已经确定的边界固化为开发约束，避免实现时把职责重新揉回主 Agent，或让微服务、A2UI 模型、端侧之间的契约漂移。

## 项目背景

本项目服务于小艺 App 的 AI 卡片生成功能。小艺 App 已具备对话式 Agent 能力，用户可以通过自然语言让 Agent 完成任务。本项目要在现有对话链路上扩展“创建桌面卡片”能力：用户输入需求描述，例如“帮我做一个通勤日常卡片，包含今天天气和今日会议”，云侧生成可在端侧预览和添加到桌面的 HarmonyOS A2UI Form 卡片。

本文档中提到的“App”“宿主 App”“小艺 App”均指小艺 App，除非上下文明确说明为天气、日历、运动健康等被调用的一方应用。

目标链路是：

```text
用户在小艺 App 发起卡片生成请求
 -> 主 Agent 识别场景并选择候选能力
 -> 微服务按用户设备实际能力裁决并生成 artifact
 -> 端侧下载 artifact，渲染 DSL 并持久化 DSL + CardSpec
 -> 卡片运行时按 CardSpec 调端侧数据能力刷新 DataModel
```

一期重点只覆盖一方应用和系统能力，例如天气、日历、系统设置、运动健康等。三方 App 数据、跨端数据和复杂页面型需求不作为默认动态能力支持，必须通过能力注册表明确声明后才能生成动态 CardSpec。

## 最高优先级

开发时按以下优先级处理冲突：

1. `docs/云侧方案设计.md`
2. 本文件
3. `skills/harmony-card-generation-path-first/` 下的协议、布局、能力和校验规则
4. 历史模板、样例 `.dat`、旧版 skill 文档

历史模板只能作为视觉参考，不能作为协议依据。模板中出现的旧尺寸、`theme`、emoji、网络图、未声明事件或不合规属性，不得复制到新实现。

## 总体边界

核心原则：

```text
主 Agent 做轻量 SOP 和候选选择。
微服务做真实能力裁决、最终 CardSpec、A2UI 模型输入构造、DSL 生成、校验、降级和落库。
A2UI 模型只生成 genui DSL。
端侧负责下载 artifact、渲染、确认添加和运行时刷新。
```

不要让主 Agent 重新承担 DSL 生成、最终 CardSpec 生成、真实设备能力判断或 A2UI 协议细节。

## 端到端链路

```text
App 中控
 -> ROM/App 版本判断，决定是否加载 Skill
 -> 主 Agent 识别卡片创建场景
 -> 主 Agent 调微服务获取能力概述
 -> 主 Agent 选择候选能力、候选 dataBindings、size
 -> 主 Agent 调 generateWidgetCard
 -> 微服务查询 IDS / 设备能力
 -> 微服务过滤候选能力
 -> 微服务生成最终 CardSpec
 -> 微服务构造 TaskSpec / A2UI prompt
 -> A2UI 模型生成 genui
 -> 微服务校验 artifact，失败最多重试 1 次
 -> 微服务上传 OBS
 -> 主 Agent 输出自然语言 + genWidgetResult 标记
 -> 端侧下载 artifact，渲染并持久化 genui + CardSpec
```

## 主 Agent / Skill 职责

主 Agent 负责：

- 识别用户是否在请求创建桌面卡片。
- 调 `getWidgetCapabilityOverview` 获取能力概述。
- 按用户 query 选择候选数据能力、候选事件能力和候选素材。
- 按需调 `getDataCapabilitySchemas` 获取数据能力完整 schema。
- 生成候选 `candidateDataBindings` 或候选能力计划。
- 调 `generateWidgetCard`。
- 根据微服务返回的 `status/userMessage/artifactUrl` 组织用户回复。

主 Agent 不负责：

- 不直接生成 `genui`。
- 不生成最终 CardSpec。
- 不判断用户设备上能力最终可用。
- 不维护完整 A2UI 协议、组件白名单、样式白名单或美观规则。
- 不向用户提前承诺“可以生成某个动态卡片”。

推荐用户过程话术：

```text
我先检查当前设备支持情况，然后为你生成可用的卡片。
```

## 微服务职责

微服务是卡片生成编排器，至少包含以下模块：

```text
WidgetGenerationService
├─ CapabilityRegistry        能力注册表
├─ A2UIProtocolRegistry      A2UI 协议版本表
├─ DeviceCapabilityResolver  IDS 查询与能力过滤
├─ CardSpecBuilder           最终 CardSpec 生成
├─ TaskSpecBuilder           A2UI 模型输入数据构造
├─ PromptBuilder             A2UI system prompt / user message 构造
├─ A2UIModelClient           DSL 模型调用
├─ Validator                 DSL/CardSpec/artifact 校验
├─ RetryController           失败重试
├─ ArtifactStore             artifact 生成与 OBS 上传
└─ ResponsePlanner           降级、拒答、用户话术
```

第一期不要引入复杂工作流引擎。普通服务编排即可。

## 工具接口

微服务以工具形式提供三个能力。

### getWidgetCapabilityOverview

用途：返回主 Agent 可用于候选筛选的能力概述。

输入：

```json
{
  "locale": "zh-CN",
  "appVersion": "x.x.x",
  "romVersion": "7.0.0"
}
```

输出应为结构化 JSON，不要只返回自然语言文本。可以额外提供面向 LLM 的描述字段。

```json
{
  "dataCapabilities": [
    {
      "id": "ViewWeather",
      "description": "查询当前天气、空气质量和未来预报",
      "descriptionForLLM": "用户需要天气、温度、空气质量、未来预报时可选择。"
    }
  ],
  "eventCapabilities": [
    {
      "id": "event.open.weather",
      "call": "clickToDeeplink",
      "description": "打开天气应用"
    }
  ],
  "assetCandidates": [
    {
      "id": "asset.weather.rain",
      "description": "天气雨伞图标"
    }
  ]
}
```

### getDataCapabilitySchemas

用途：针对主 Agent 已选中的数据能力渐进加载完整 schema。

输入：

```json
{
  "dataCapabilityIds": ["ViewWeather", "calendar.events.search"]
}
```

输出：

```json
{
  "dataCapabilities": [
    {
      "id": "ViewWeather",
      "inputSchema": {},
      "outputSchema": {},
      "defaultWriteResultTo": "/data/weather"
    }
  ]
}
```

### generateWidgetCard

用途：主生成接口。

推荐入参：

```json
{
  "userQuery": "帮我做通勤卡片，包含天气和今日日程",
  "size": "2x4",
  "candidateDataBindings": [
    {
      "capabilityId": "ViewWeather",
      "arguments": {
        "districtName": "青浦区",
        "forecastDays": 1
      },
      "writeResultTo": "/data/weather"
    }
  ],
  "candidateEventCapabilityIds": ["event.open.weather"],
  "candidateEventActions": [
    {
      "call": "clickToDeeplink",
      "args": {
        "bundleName": "",
        "abilityName": "",
        "uri": "hww://www.huawei.com/totemweather?enterType=share&cityCode="
      }
    }
  ],
  "candidateAssetIds": ["asset.weather.rain"],
  "options": {
    "allowDegradation": true,
    "returnArtifactInline": false
  }
}
```

工具层会自动注入：

```json
{
  "uid": "...",
  "device": {},
  "appVersion": "...",
  "romVersion": "...",
  "xiaoyiVersion": "..."
}
```

输出：

```json
{
  "status": "success",
  "artifactUrl": "https://obs.xxx/widget/uuid.json",
  "artifactDigest": "sha256:xxx",
  "suggestSize": "2x4",
  "userMessage": "已为你生成通勤卡片。",
  "removedCapabilities": [],
  "errorCode": ""
}
```

## 生成接口状态码

`status` 只使用以下枚举：

```text
success      完整满足用户需求并生成成功
degraded     部分能力不可用，已降级生成可用卡片
unsupported  能力或协议限制导致不应生成卡片
failed       系统异常、模型失败、OBS 失败等工程失败
```

不要把 `unsupported` 和 `failed` 混用。

推荐错误码：

```text
UNKNOWN_CAPABILITY
ROM_VERSION_UNSUPPORTED
APP_VERSION_UNSUPPORTED
PACKAGE_NOT_INSTALLED
PACKAGE_VERSION_TOO_LOW
PROVIDER_NOT_FOUND
INTENT_TARGET_NOT_FOUND
PERMISSION_DENIED
PERMISSION_UNKNOWN
INVALID_ARGUMENTS
WRITE_RESULT_CONFLICT
NO_EFFECTIVE_CAPABILITY
A2UI_GENERATION_FAILED
VALIDATION_FAILED
ARTIFACT_UPLOAD_FAILED
TIMEOUT
```

## 能力注册表

微服务维护能力注册表。数据能力、事件能力和素材能力要分开建模。

数据能力示例：

```json
{
  "id": "calendar.events.search",
  "type": "data",
  "description": "查询用户手机本地日历事件",
  "inputSchema": {},
  "outputSchema": {},
  "defaultWriteResultTo": "/data/calendar",
  "dataModelSkeleton": {
    "data": {
      "calendar": {
        "items": []
      }
    }
  },
  "dependencies": {
    "minRomVersion": "7.0.0",
    "minAppVersion": "x.x.x",
    "requiredPackages": [
      {
        "packageName": "com.huawei.hmos.calendar",
        "minVersion": "14.0.0"
      }
    ],
    "requiredProviders": ["UG.calendar.events.search"],
    "requiredPermissions": ["calendar.read"]
  }
}
```

事件能力示例：

```json
{
  "id": "event.viewCalendarEvent",
  "type": "event",
  "call": "clickToIntent",
  "description": "点击日程进入日程详情",
  "requiredIntentTargets": ["ViewCalendarEvent"],
  "parametersSchema": {
    "intentName": "ViewCalendarEvent",
    "params": {
      "entityId": "string"
    }
  },
  "dependencies": {
    "minRomVersion": "7.0.0",
    "requiredProviders": [],
    "requiredPackages": []
  }
}
```

素材能力示例：

```json
{
  "id": "asset.weather.rain",
  "type": "asset",
  "src": "resources/base/media/icon_weather1.png",
  "description": "天气雨伞图标，适合表达天气信息",
  "sceneTags": ["weather", "rain"],
  "minXiaoyiVersion": "x.x.x"
}
```

## 能力过滤

微服务过滤顺序固定为：

```text
能力 ID 是否注册
 -> ROM/App 版本是否满足
 -> 依赖 App 是否安装且版本满足
 -> IDS 返回的意图/provider 是否存在
 -> 权限状态是否允许
 -> arguments 是否符合 inputSchema
 -> writeResultTo 是否合法且无冲突
```

约束：

- App 安装只是必要条件，不是充分条件。
- 最终以 IDS 返回的意图列表、provider 列表和资源可用性为准。
- 第一阶段可以简化权限实现，但接口、错误码和日志必须预留权限字段。
- 不可用能力必须从最终 CardSpec 和 TaskSpec 候选中移除。

权限状态预留枚举：

```text
GRANTED       可直接使用
ASK_RUNTIME   可生成，但端侧运行时需要授权
DENIED        不生成动态 dataBinding，除非产品明确要做授权引导卡
UNKNOWN       按策略降级或触发端侧运行时判断
```

## CardSpec 生成

主 Agent 传的是候选 `candidateDataBindings`。微服务过滤后得到 `effectiveDataBindings`，再生成最终 CardSpec。

动态 CardSpec：

```json
{
  "suggestSize": "2x4",
  "dataBindings": [
    {
      "capabilityId": "ViewWeather",
      "arguments": {
        "districtName": "青浦区",
        "forecastDays": 1
      },
      "writeResultTo": "/data/weather"
    }
  ]
}
```

静态 CardSpec：

```json
{
  "suggestSize": "2x4"
}
```

规则：

- `suggestSize` 使用微服务最终尺寸决策，不因静态卡片强制改为 `2x2`。
- 点击事件不进入 CardSpec。
- 不可用能力不进入 CardSpec。
- 不编造 capabilityId。
- `writeResultTo` 必须位于 `/data/...`。
- 多个 `writeResultTo` 不得相同、互为父子或互相覆盖。
- `arguments` 必须符合能力 `inputSchema`。

## TaskSpec 构造

TaskSpec 是微服务传给 A2UI 模型的输入契约。顶层只允许：

```json
{
  "userQuery": "...",
  "size": "2x4",
  "eventCandidates": [],
  "dataModel": {
    "value": {}
  },
  "assetCandidates": []
}
```

不要在 TaskSpec 顶层加入：

```text
cardSpec
rules
capabilitySchemas
displayCandidates
role
component
layout
fontSize
```

`dataModel.value` 根据最终 CardSpec 和能力 `dataModelSkeleton/outputSchema` 生成，必须包含必要根结构和加载态：

```json
{
  "data": {
    "weather": {
      "location": {},
      "current": {},
      "daily": [],
      "updatedAt": ""
    }
  }
}
```

A2UI 模型生成的 `updateDataModel.value` 必须与 TaskSpec 的 `dataModel.value` 完全一致。

## A2UI 协议 profile

微服务根据 ROM/App/小艺版本选择协议 profile：

```text
romVersion + appVersion + xiaoyiVersion
 -> protocolProfileId
 -> 组件白名单、属性白名单、尺寸、绑定策略、事件策略、素材策略
```

第一期默认遵循：

- `2x2`: `140 x 140`
- `2x4`: `300 x 140`
- `catalogId`: `ohos.a2ui.extended.catalog`
- `version`: `v0.9`
- 只允许组件：`Text`、`Image`、`Divider`、`Progress`、`Button`、`Checkbox`、`Row`、`Column`、`List`、`Stack`
- 禁止网络图、未声明事件和禁用组件

## A2UI 模型输入

微服务构造模型输入，不允许主 Agent 直接拼 prompt。

输入内容包括：

- 用户原始 query
- 目标尺寸
- TaskSpec
- 协议 profile 摘要
- 美观规则
- 不可用能力的降级上下文

A2UI 模型输出只接受一个 `genui` 代码块，且恰好三行 JSONL：

```genui
{"version":"v0.9","createSurface":{}}
{"version":"v0.9","updateComponents":{}}
{"version":"v0.9","updateDataModel":{}}
```

## Artifact

微服务上传完整 artifact，不只上传 DSL。

推荐结构：

```json
{
  "schemaVersion": "widget-artifact-v1",
  "genui": "三行 JSONL",
  "cardSpec": {},
  "taskSpec": {},
  "effectiveCapabilities": {
    "data": [],
    "event": [],
    "asset": []
  },
  "removedCapabilities": [],
  "meta": {
    "protocolProfileId": "a2ui-form-rom7-v1",
    "capabilityRegistryVersion": "2026-07-03",
    "createdAt": 1780000000000
  }
}
```

端侧最少依赖：

- `genui`
- `cardSpec`

其它字段主要用于排障、回放和灰度分析。

## 校验与重试

校验对象是完整 artifact。

必查项：

```text
genui 恰好三行 JSONL
createSurface/updateComponents/updateDataModel 顺序正确
surfaceId 三行一致
catalogId 与 profile 一致
root 尺寸与 size/profile 一致
CardSpec suggestSize 与 DSL 一致
组件、属性、事件、素材都在白名单内
children 引用可解析
updateDataModel.value 与 TaskSpec.dataModel.value 一致
DSL 绑定路径可从 dataModel 或 CardSpec outputSchema 推导
事件只能来自有效 eventCandidates
图片只能来自有效 assetCandidates 或用户明确提供的本地资源
CardSpec 只包含有效 dataBindings
writeResultTo 不冲突
```

失败后最多重新生成 1 次。重试 prompt 只追加错误摘要，不追加完整日志。

如果重试后仍失败：

- 可以降级为简单结构再生成一次，前提是仍在时延预算内。
- 否则返回 `failed`，并记录 `VALIDATION_FAILED` 或 `A2UI_GENERATION_FAILED`。

## 降级与拒答

规则：

```text
核心能力可用
 -> 正常生成

部分能力不可用
 -> 降级生成，说明少了什么

组件样式不支持
 -> 不拒答，改写为支持组件表达

数据能力不存在
 -> 不伪造动态 CardSpec，可做静态卡或入口卡

App 未安装
 -> 有入口或静态价值则降级，否则提示安装或启用

所有核心能力不可用且静态卡无价值
 -> 不调用 A2UI 模型，直接 unsupported
```

示例 unsupported：

```text
当前设备上没有可用的外卖配送数据能力，也没有可打开的应用入口，所以暂时不能生成实时外卖卡片。你可以试试天气、日历或系统状态类卡片。
```

示例 degraded：

```text
日历权限当前未开启，我先为你生成只包含天气和通勤入口的卡片。开启日历权限后可以再生成包含今日日程的版本。
```

## 美观质量

不要靠主 Agent 保证视觉质量。微服务通过 prompt、候选素材和校验器保证。

硬规则：

- 单一主焦点。
- `2x2` 最多 3 个主区域。
- `2x4` 最多 4 个主区域。
- 受保护文本不截断。
- 字号只使用批准阶梯：`10/12/14/16/18/20/32/40`。
- 间距只使用批准阶梯：`2/4/6/8/10/12/14/16`。
- root shell 必须完整：`width/height/padding/borderRadius/clip/background`。
- Row/Column 宽高预算必须成立。
- 图片必须来自素材白名单，且设置明确 `width/height/objectFit`。
- 禁止网络图、SVG、emoji 和纯装饰堆叠。

生成失败或视觉风险高时，强制降级为：

```text
标题 + 主状态 + 1 条支撑信息 + 1 个入口
```

## OBS 与端侧标记

Skill 输出流式标记：

````text
```genWidgetResult:"https://obs.xxx/widget/uuid.json"```
````

端侧识别该标记后下载 artifact。不要在普通自然语言中伪造该标记。

OBS 存储内容必须是完整 artifact，不是单独 DSL。

## 版本兼容

所有产物和关键配置必须带版本：

```text
apiVersion
taskSpecVersion
cardSpecVersion
dslProtocolVersion
skillVersion
protocolProfileId
capabilityRegistryVersion
artifactSchemaVersion
```

版本兼容要求：

- ROM < 7.0 不加载本 Skill。
- 微服务按 ROM/App/小艺版本选择 A2UI profile。
- 能力注册表支持最小 ROM、最小 App、最小包版本。
- artifact 记录生成时的 profile 和能力注册表版本。
- 新增能力、组件或属性必须先进入 profile 和 validator，再进入 prompt。

## 开发约束

开发代码时遵守：

- 不把最终 CardSpec 生成逻辑放到主 Agent。
- 不把 A2UI 协议白名单散落在多个模块中；统一由 `A2UIProtocolRegistry` 提供。
- 不让 A2UI 模型自行选择未过滤能力。
- 不让 A2UI 模型生成或修改 CardSpec。
- 不把点击事件写入 CardSpec。
- 不在 TaskSpec 顶层扩展非协议字段。
- 不在校验失败后无限重试。
- 不在能力不可用时伪造动态 dataBinding。
- 不上传半成品 artifact。
- 不只返回 OBS URL 而丢失结构化状态。

## 最小测试集

至少覆盖：

```text
帮我做一个通勤日常卡片，包含今天天气和今日会议
帮我做一个只显示今天上海天气的桌面卡片
帮我做一个今日会议提醒卡片，可以点击查看日程
帮我做一个低电量省电卡片
帮我做一个雨天打车提醒卡片
帮我做一个睡眠监督卡片
帮我做一个美团外卖配送状态卡片
帮我做一个可以输入文字的备忘录卡片
帮我做一个包含天气、日历、新闻、股票的大卡片
帮我做一个打开天气应用的入口卡片
```

测试维度：

- 正常动态卡片。
- 部分能力不可用后的 degraded。
- 全部核心能力不可用后的 unsupported。
- App 未安装。
- 权限 denied / ask runtime / unknown。
- 素材不可用。
- A2UI 模型输出非法 DSL。
- OBS 上传失败。
- `writeResultTo` 冲突。
- 老版本 ROM 不加载 Skill。

## 日志与监控

每次生成必须记录：

```text
requestId
uid/deviceId 脱敏标识
queryHash
skillVersion
protocolProfileId
capabilityRegistryVersion
candidateCapabilities
effectiveCapabilities
removedCapabilities + reason
status
errorCode
latencyByStage
retryCount
artifactDigest
```

关键指标：

- 生成成功率
- 降级率
- unsupported 率
- failed 率
- 校验失败率
- 重试成功率
- 平均耗时 / P95 耗时
- 各能力不可用原因分布

## 给 AI 编码助手的要求

当你被要求修改本项目代码时：

1. 先阅读 `docs/云侧方案设计.md` 和本文件。
2. 先确认改动属于主 Agent、微服务、A2UI 模型调用、端侧解析还是测试。
3. 不要跨边界实现职责，除非用户明确要求改方案。
4. 新增接口时同时补 schema、错误码和测试样例。
5. 新增能力时同时补注册表、DataModel 骨架、CardSpec 映射、过滤依赖和校验规则。
6. 新增 A2UI 协议能力时先补 profile 和 validator，再改 prompt。
7. 遇到不支持场景，优先实现 degraded/unsupported 决策，不要绕过能力过滤。
8. 输出给用户的结果不要暴露内部字段名，例如 capability、provider、TaskSpec；日志和接口中可以保留。

