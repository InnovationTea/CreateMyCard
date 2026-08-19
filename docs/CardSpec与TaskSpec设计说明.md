# CardSpec 与 TaskSpec 设计说明

> 面向卡片云侧、端侧和模型接入团队的快速参考。本文只解释两类契约的定位与协作关系；字段或流程发生冲突时，以 [`云侧方案设计.md`](./云侧方案设计.md) 为准。

## 1. 一句话定位

- **CardSpec 是端侧运行契约**：描述卡片的展示元信息、建议尺寸，以及端侧应调用哪些数据能力、把结果写到哪里。
- **TaskSpec 是模型生成契约**：把用户需求、目标尺寸、可用事件、可展示的数据结构和素材候选整理成 A2UI 模型可消费的受控上下文。
- 两者都由**微服务生成**。A2UI 模型只生成 `genui` DSL，不生成或修改 CardSpec。

| 对比项 | CardSpec | TaskSpec |
| --- | --- | --- |
| 主要消费者 | 端侧卡片运行时 | A2UI 模型 |
| 核心作用 | 数据能力调用与结果写入 | 约束 DSL 能展示什么、绑定什么、点击什么 |
| 是否随卡片持久化 | 是，端侧最小依赖之一 | 否，主要用于生成、排障和回放 |
| 是否包含事件与素材候选 | 否 | 是 |
| 是否包含完整能力 schema | 否 | 否，只包含生成所需的字段投影 |

## 2. 构建顺序

```text
用户需求与主 Agent 候选计划
  -> 微服务完成能力过滤与参数校验
  -> effectiveDataBindings
  -> 构建最终 CardSpec
  -> 根据 CardSpec、能力 outputSchema 和字段投影构建 TaskSpec
  -> A2UI 模型依据 TaskSpec 生成 genui
  -> 校验 genui + CardSpec + 有效能力的一致性
  -> 组装 widget-artifact-v2
```

这个顺序保证运行契约先确定，模型只能在已裁决的能力边界内设计界面。

## 3. CardSpec：端侧可执行的数据契约

### 3.1 字段

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `title` | 是 | 用户可见的静态短标题；当前校验配置上限为 8 个字符 |
| `description` | 是 | 用户可见的静态短概述；当前校验配置上限为 12 个字符 |
| `suggestSize` | 是 | 微服务最终裁决的尺寸，仅支持 `2x2`、`2x4` |
| `dataBindings` | 动态卡必填 | 每项表示一次端侧数据能力调用；静态卡不写空数组 |

`dataBindings[]` 由三项组成：

- `capabilityId`：已通过能力裁决的数据能力标识。
- `arguments`：符合该能力 `inputSchema` 的静态 JSON 入参。
- `writeResultTo`：能力结果写入 A2UI DataModel 的 JSON Pointer，必须位于 `/data/...`。

### 3.2 示例

```json
{
  "title": "通勤助手",
  "description": "天气日程速览",
  "suggestSize": "2x2",
  "dataBindings": [
    {
      "capabilityId": "ViewWeather",
      "arguments": { "districtName": "青浦区", "forecastDays": 1 },
      "writeResultTo": "/data/weather"
    }
  ]
}
```

静态卡只保留展示元信息和尺寸：

```json
{
  "title": "天气入口",
  "description": "快速打开天气",
  "suggestSize": "2x2"
}
```

### 3.3 运行时语义

端侧读取每个 binding，使用 `arguments` 调用 `capabilityId` 对应能力，再将符合 `outputSchema` 的完整结果写入 `writeResultTo`。例如结果写入 `/data/weather` 后，DSL 可绑定 `/data/weather/current/temperatureText`。

CardSpec 不复制 `outputSchema`，也不是 DataModel 本身。三者分工如下：

- CardSpec：声明“调用什么、传什么、写到哪里”。
- `outputSchema`：声明能力返回值的合法结构。
- DataModel：保存卡片当前运行时状态，由 `updateDataModel` 更新并触发重渲染。

### 3.4 核心约束

- 不可用或未声明的数据能力不得进入 CardSpec。
- 多个 `writeResultTo` 不得相同、互为父子或互相覆盖。
- `title`、`description`、`arguments` 不写表达式、绑定路径或真实隐私数据。
- 点击、拨号、打开应用等事件只写入 DSL，不写入 CardSpec。
- `suggestSize` 与 DSL 目标尺寸一致；用户未指定时，优先选择能完整承载核心需求的 `2x2`。

## 4. TaskSpec：A2UI 模型的受控输入

TaskSpec 顶层固定为五个字段：

| 字段 | 作用 |
| --- | --- |
| `userQuery` | 保留用户原始意图，帮助模型理解信息优先级与表达方式 |
| `size` | 已由微服务确定的目标尺寸，模型不得自行升级 |
| `eventCandidates` | 过滤后的可用点击动作及完整参数 |
| `dataModelSchema` | DSL 可绑定的必要数据结构、字段说明与受控样例 |
| `assetCandidates` | 可在 DSL 中使用的素材路径和语义说明 |

```json
{
  "userQuery": "做一张上海天气卡片，显示温度和天气情况",
  "size": "2x2",
  "eventCandidates": [],
  "dataModelSchema": {
    "data": {
      "weather": {
        "current": {
          "temperatureText": {
            "type": "string",
            "description": "当前温度展示文本",
            "sampleValue": "26℃"
          },
          "condition": {
            "type": "string",
            "description": "当前天气现象",
            "sampleValue": "多云"
          }
        }
      }
    }
  },
  "assetCandidates": [
    {
      "src": "resources/base/media/icon_weather1.svg",
      "description": "天气图标"
    }
  ]
}
```

### 4.1 `dataModelSchema` 的设计

它是面向模型的**必要字段投影**，不是完整能力 schema：

- 根路径与最终 CardSpec 的 `writeResultTo` 对齐。
- 叶子字段由 `type`、`description`、`sampleValue` 描述。
- `sampleValue` 只帮助模型理解展示形态，不是真实用户数据，也不能替代动态绑定。
- 数组投影使用 `/0` 表示元素 schema；DSL 展示数组时应使用模板循环。
- 模型可以少用候选字段，但不能在动态能力路径下编造未授权字段。

### 4.2 不应加入的内容

TaskSpec 顶层不得扩展 `cardSpec`、`rules`、`capabilitySchemas`、`dataModel`、`title`、`description`、布局或字体等字段。协议和美观规则由微服务通过模型提示词和 profile 提供，不通过 TaskSpec 私自扩展。

## 5. 两类契约如何保持一致

需要重点校验三组关系：

1. **尺寸一致**：`CardSpec.suggestSize == TaskSpec.size == DSL 目标尺寸`。
2. **数据路径一致**：TaskSpec 和 DSL 使用的动态路径，必须能由 `CardSpec.writeResultTo + outputSchema` 推导。
3. **能力边界一致**：CardSpec 只使用有效数据能力；TaskSpec 只使用有效事件和素材；DSL 不得越过这些白名单。

事件参数若引用动态数据，也必须能从同一数据路径推导。事件能力本身仍不进入 CardSpec。

## 6. Artifact 与多轮编辑

完整 artifact 同时保存 `cardSpec`、`genui`、`taskSpec`、有效/移除能力、候选计划和生成元数据。其中端侧运行最小依赖只有 `genui + cardSpec`；TaskSpec 主要服务于云侧排障、回放和编辑重建。

编辑时不让模型直接修改旧 CardSpec，也不直接复用旧 TaskSpec：微服务基于当前有效候选重新构建 CardSpec，再重建 TaskSpec，最后生成一份新的完整 artifact。这样可以处理能力变化、字段删除和协议升级，避免旧契约残留。

## 7. 评审检查清单

- CardSpec 是否只包含最终有效的数据能力，且入参符合 `inputSchema`？
- 静态卡是否省略 `dataBindings`，动态卡是否存在合法 binding？
- 所有 `writeResultTo` 是否位于 `/data/...` 且互不冲突？
- TaskSpec 是否严格只有五个顶层字段？
- `dataModelSchema` 是否仅保留界面需要的字段，并使用脱敏样例？
- DSL 的动态绑定和事件参数是否都可从 CardSpec、能力 schema 或 TaskSpec 投影推导？
- 事件与素材是否只来自本次有效候选？
- 多轮编辑是否重新构建两类契约并生成新 artifact？
