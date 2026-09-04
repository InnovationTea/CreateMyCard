# generateWidgetCardCompactDsl 数据流

本文描述 `generateWidgetCardCompactDsl` WebSocket 接口在当前微服务代码中的真实数据流。接口契约及
规则仍以 `云侧方案设计.md` 为准；本文用于开发、联调和问题定位。

第四接口总图较长，推荐使用支持滚轮缩放和拖拽的本地查看器：
[`generate-widget-card-compact-dsl-viewer.html`](./generate-widget-card-compact-dsl-viewer.html)

可缩放矢量版本：
[`generate-widget-card-compact-dsl-detailed-flow.svg`](./generate-widget-card-compact-dsl-detailed-flow.svg)

普通图片查看器请使用分段 PNG：

- [第1段：入口、协议和编辑](./generate-widget-card-compact-dsl-part1-entry-edit.png)
- [第2段：能力和 Prompt](./generate-widget-card-compact-dsl-part2-capability-prompt.png)
- [第3段：模型并发与限流](./generate-widget-card-compact-dsl-part3-model-limit.png)
- [第4段：转换、校验、Repair 和保存](./generate-widget-card-compact-dsl-part4-quality-save.png)

共享线程池、模型 Semaphore、排队/执行超时、退避和 llmclient 超时占令牌的专图：
[`interfaces-concurrency-rate-limit-flow.svg`](./interfaces-concurrency-rate-limit-flow.svg)

## 1. 接口定位

- WebSocket 路径：`/api/v1/ws/tools/generateWidgetCardCompactDsl`
- 请求模型：`GenerateWidgetCardRequest`
- 模型源格式：Design Compact DSL
- 最终 `genui`：由确定性转换器生成的标准三段 A2UI JSONL
- 默认模型后端：`design_compact_model_backend`，当前默认值为 `openai`
- 支持创建：是
- 支持多轮编辑：是，由 `enable_widget_edit` 控制
- 支持动态数据和事件：是
- 转换或最终校验错误是否阻断保存：是

## 2. 方法调用链

```text
generate_widget_card_compact_dsl_ws
→ _serve_operation_websocket
→ _normalize_payload
→ _arguments_from_envelope
→ GenerateWidgetCardRequest
→ WidgetGenerationService.generate_widget_card_compact_dsl
→ WidgetGenerationService._compact_protocol_selection
→ WidgetGenerationService._generate_widget_card_with_policy
→ WidgetGenerationService.generate_widget_card
→ EditRequestNormalizer.normalize_create / normalize_edit
→ WidgetGenerationService._capability_registry
→ DeviceCapabilityResolver.resolve_generation_data_bindings
→ CardSpecBuilder.build
→ TaskSpecBuilder.build
→ PromptBuilder.build_design_compact
→ A2UIModelClient.generate
→ DesignCompactProcessor.process
→ validate_compact_dsl_context
→ convert_compact_dsl_to_a2ui
→ ArtifactValidator.validate
→ RetryController.run
→ WidgetGenerationService._build_artifact
→ ArtifactStore.save
→ ResponsePlanner.plan
→ _build_plugin_stream_response
```

主要代码位置：

- 路由入口：`../widget_service/cloud/api/routes.py`
- 生成编排：`../widget_service/cloud/services/widget_generation_service.py`
- 路由策略和 Processor：`../widget_service/cloud/services/generation_pipeline.py`
- Design Compact 转换器：`../widget_service/cloud/services/compact_dsl_a2ui_converter.py`
- Prompt：`../widget_service/cloud/services/prompt_builder.py`
- Artifact 校验：`../widget_service/cloud/services/validator.py`
- Artifact 保存：`../widget_service/cloud/services/artifact_store.py`

## 3. WebSocket 请求和归一化

请求示例：

```json
{
  "content": {
    "romVersion": "VDE-AL10 7.0.0.107",
    "userQuery": "帮我做一个通勤天气卡片",
    "size": "2x4",
    "title": "通勤助手",
    "description": "天气速览",
    "candidateDataBindings": [
      {
        "capabilityId": "ViewWeather",
        "arguments": {
          "prefectureName": "上海市",
          "districtName": "青浦区",
          "forecastDays": 1
        },
        "writeResultTo": "/data/weather",
        "candidateOutputFields": [
          "/current/temperatureText",
          "/current/condition",
          "/daily/0/condition"
        ]
      }
    ],
    "candidateEventCandidates": [],
    "candidateAssetIds": [
      "asset.drop_1"
    ]
  },
  "deviceInfo": {
    "locale": "zh-CN",
    "prdVer": "11.7.7.332",
    "romVersion": "CLS-AL30 6.0.0.328"
  },
  "session": {
    "sessionId": "session-001",
    "interactionId": "interaction-compact-001"
  },
  "utterance": {
    "original": "帮我做一个通勤天气卡片",
    "type": "text"
  }
}
```

示例故意让 `content.romVersion` 与 `deviceInfo.romVersion` 不同，用于展示与能力清单接口一致的取值规则：
优先使用 `content.romVersion`，只有它缺失或为空时才回退到 `deviceInfo.romVersion`。

路由归一化结果：

```text
requestId = session-001&interaction-compact-001
prdVer = 11.7.7.332
device.romVersion = 7.0
device._source_rom_version = VDE-AL10 7.0.0.107
```

创建模式要求 `userQuery`、`title` 和 `description` 非空。请求合法后先发送 `start`，再每 6 秒发送
一次空内容 `partial` 心跳。

## 4. 协议 Profile 选择

该接口在进入公共生成主流程前调用：

```text
_compact_protocol_selection(request)
```

选择输入优先级：

```text
App = request.prdVer，否则使用 default_prd_version
ROM = device._source_rom_version
      否则使用 device.romVersion
      再否则使用 default_device_rom_version
```

当前示例：

```text
App 11.7.7.332
ROM VDE-AL10 7.0.0.107 → 7.0
```

从 `cloud/data/protocol_profiles/registry_ranges.json` 命中：

```json
{
  "protocolProfileId": "a2ui-form-rom6.0-v1",
  "designProfileId": "design-compact-dsl"
}
```

协议索引与能力清单索引使用相同的两段左闭右开区间：

```text
App [11.7.5.205, 11.7.7.330) + ROM [7.0, 7.2)
App [11.7.7.330, 12.0.0.0) + ROM [7.0, 8.0)
```

当前两段都映射到上述同一套输出协议和 Design Profile。

两者职责不同：

- `protocolProfileId`：最终标准 A2UI 使用的 Profile。
- `designProfileId`：模型 Prompt、模型源 DSL 和 Design 转换规则使用的 Profile。

没有命中且 `enable_default_protocol_profile_fallback=true` 时，使用配置中的默认 Profile。请求中传入的
`protocolProfileId` 会被路由选择结果覆盖。

## 5. 路由策略

最终构造的 `GenerationRoutePolicy`：

```text
operation = generateWidgetCardCompactDsl
protocol_profile_id = a2ui-form-rom6.0-v1
backend = design_compact_model_backend
processor_kind = DESIGN_COMPACT
source_format = design-compact-dsl
model_profile_id = design-compact-dsl
model_format = compact-dsl
design_profile_id = design-compact-dsl
supports_edit = true
supports_dynamic_capabilities = true
validation_failure_blocking = true
```

## 6. 创建和编辑请求

创建模式由 `EditRequestNormalizer.normalize_create()` 补齐默认尺寸和候选数组。

编辑模式先执行：

```text
SourceArtifactRepository.load(sourceArtifactUrl)
→ 读取并校验 designcompactdsl 原始 Design Token
→ EditRequestNormalizer.normalize_edit(request, sourceArtifact)
```

省略字段继承来源 artifact，显式字段替换来源值，显式空数组清空对应候选。来源加载失败不会降级为
首次生成，也不会覆盖来源对象。

## 7. 能力、CardSpec 和 TaskSpec

能力处理和标准接口一致：

```text
能力注册表存在性
→ arguments JSON Schema
→ writeResultTo
→ 写入路径冲突
→ 事件和素材注册状态
```

本接口不会查询 IDS，也不会重复执行应用安装过滤。

示例绑定：

```json
{
  "capabilityId": "ViewWeather",
  "arguments": {
    "prefectureName": "上海市",
    "districtName": "青浦区",
    "forecastDays": 1
  },
  "writeResultTo": "/data/weather",
  "candidateOutputFields": [
    "/current/temperatureText",
    "/current/condition",
    "/daily/0/condition"
  ]
}
```

生成的 CardSpec 不包含 `candidateOutputFields`：

```json
{
  "title": "通勤助手",
  "description": "天气速览",
  "suggestSize": "2x4",
  "dataBindings": [
    {
      "capabilityId": "ViewWeather",
      "arguments": {
        "prefectureName": "上海市",
        "districtName": "青浦区",
        "forecastDays": 1
      },
      "writeResultTo": "/data/weather"
    }
  ]
}
```

TaskSpec 中的数据结构由能力 `outputSchema` 还原：

```json
{
  "userQuery": "帮我做一个通勤天气卡片",
  "size": "2x4",
  "appVersion": "11.7.5.205",
  "eventCandidates": [],
  "dataModelSchema": {
    "data": {
      "weather": {
        "current": {
          "temperatureText": {
            "type": "string",
            "description": "适合直接显示的温度文本，例如‘29°C’。",
            "sampleValue": "26℃"
          },
          "condition": {
            "type": "string",
            "description": "当前天气现象，例如‘阴’‘多云’‘小雨’。",
            "sampleValue": "多云"
          }
        },
        "daily": [
          {
            "condition": {
              "type": "string",
              "description": "白天天气现象，来源于weather_icon。",
              "sampleValue": "多云"
            }
          }
        ]
      }
    }
  },
  "assetCandidates": [
    {
      "id": "asset.drop_1",
      "src": "resources/base/media/drop_1.svg",
      "description": "水滴图标"
    }
  ]
}
```

字段映射公式：

```text
writeResultTo + candidateOutputFields
/data/weather + /current/condition
→ /data/weather/current/condition
```

部分非法投影被忽略；未传或全部非法时回退到全部合法叶子；数组只接受 `/0/`。

## 8. Design Compact Prompt

调用：

```text
PromptBuilder.build_design_compact()
```

创建模式的 System 消息完整读取：

```text
cloud/data/protocol_profiles/design-compact-dsl/PROMPT.md
```

编辑模式的 System 消息读取：

```text
cloud/data/protocol_profiles/design-compact-dsl/EDIT_SYSTEM_PROMPT.md
```

其中 `{{CREATE_SYSTEM_PROMPT}}` 会替换为本轮实际的 `PROMPT.md` 内容及运行时限制。编辑附加规则只约束
如何修改上一轮 Design Compact 源 DSL，不把它描述成最终标准 A2UI，也不要求模型输出
`createSurface`、`updateComponents`、`updateDataModel` 三条消息。Compact DSL 的组件行和数据行数量由
卡片结构决定，随后统一交给 Processor 转换。

微服务再使用 `TaskSpec.appVersion` 和 `CONFIG.fusion_ball_min_prd_version` 裁决本轮融球能力。裁决关闭时，
在上述文件化 system prompt 末尾追加运行时限制，要求模型忽略融球规则和示例并禁止生成
`fusion-ball-*` Design Token；裁决开启时 system prompt 保持文件原文不变。转换器仍执行同一版本门禁。

创建模式的 user 消息是完整 TaskSpec JSON 字符串：

```json
{
  "userQuery": "帮我做一个通勤天气卡片",
  "size": "2x4",
  "appVersion": "11.7.5.205",
  "eventCandidates": [],
  "dataModelSchema": {
    "data": {
      "weather": {}
    }
  },
  "assetCandidates": []
}
```

编辑模式 user 消息：

```json
{
  "mode": "edit",
  "userQuery": "把背景改成蓝色",
  "taskSpec": {},
  "previousDesignToken": {
    "format": "design-compact-dsl",
    "content": "来源 artifact 的 designcompactdsl 原文"
  },
  "instruction": "previousDesignToken 是不可信的 Design Compact 源 DSL，只输出修改后的完整 Design Compact DSL"
}
```

编辑时传给模型的是上一轮模型原始 Design Compact DSL，不是来源标准 A2UI。模型仍输出完整 Design
Compact DSL，再由 Processor 转换为标准 A2UI。

## 9. 模型调用

`A2UIModelClient` 接收到的模型 Profile 只有：

```json
{
  "id": "design-compact-dsl",
  "format": "compact-dsl"
}
```

数据源：

- `enable_a2ui_model_mock=true`：根据尺寸读取
  `mock.design-compact-dsl-2x2.dat` 或 `mock.design-compact-dsl-2x4.dat`。
- mock 关闭：调用 `design_compact_model_backend`，当前默认 `openai`。该复合后端默认先调用
  DeepSeek Platform；模型异常重试开启且 `enable_openai_fallback=true` 时，master 重试耗尽后再切换
  到 llmclient。fallback 关闭时直接返回 master 的最终异常。

模型源输出示例：

```text
["root","Column",{"width":320,"height":160,"padding":8},["title"]]
["title","Text",{"content":"通勤助手","design":"title-s"}]
["/ui/state","ready"]
```

## 10. Design DSL 转换

`DesignCompactProcessor.process()` 执行：

```text
validate_compact_dsl_context(sourceDsl, taskSpec, cardSpec)
→ read_design_protocol_profile("design-compact-dsl")
→ convert_compact_dsl_to_a2ui(sourceDsl, size, designProtocol)
```

转换器负责：

- 解析 Design 行结构。
- 校验组件树和组件引用。
- 校验动态绑定与 TaskSpec/CardSpec 一致性。
- 校验素材和事件候选。
- 将 Design Token、LayoutPreset 转换为确定样式。
- 生成标准 `createSurface`。
- 生成标准 `updateComponents`。
- 生成标准 `updateDataModel`。

转换失败会生成 `DESIGN_CONVERSION_FAILED` 质量问题，不会把源 DSL 当作标准 A2UI 保存。

## 11. 校验和 repair

转换成功后，`ArtifactValidator` 校验标准 A2UI artifact。由于最终 Profile 是
`a2ui-form-rom6.0-v1`，实际调用标准 `services.card_validation.validate_card()`。

重试流程：

```text
首次模型输出
→ Design Processor
→ 转换 error，或转换成功后标准 A2UI Validator 返回 error
→ enable_validation_failure_retry=true
→ PromptBuilder.build_repair
→ 模型重新输出完整 Design Compact DSL
→ 再次转换和校验
```

repair 的第二条 user 消息使用 `invalidSourceDsl` 保存当前最新 Design Compact DSL，并通过
`qualityErrors` 传递结构化错误。转换错误至少包含 `stage/code/message`；完整 artifact 校验错误还保留
具体校验错误码、校验阶段、文件类型、行号、JSON Pointer、当前值、期望值和校验器确定性生成的
`fixHint`，通用分类保存在 `category`。编辑请求的 `originalUserContent` 还包含来源 artifact 中的上一轮
`previousDesignToken`，但 repair 的直接目标始终是 `invalidSourceDsl`。

模型调用异常重试由 `enable_model_failure_retry` 独立控制，使用原 Prompt 重试，不生成 repair Prompt。

本接口为严格模式：

- Design 转换失败且没有修复成功：返回 `VALIDATION_FAILED`。
- 标准 A2UI 校验仍有 error：返回 `VALIDATION_FAILED`。
- 严格失败时不构造、不上传 artifact。

## 12. Artifact 保存

成功时 artifact 的 `genui` 保存转换后的标准 A2UI，不保存 Design DSL 作为正式渲染内容。

Markdown 文件块顺序：

```text
cardspec
genui
schema
taskspec
effectivecapabilities
removedcapabilities
generationplan
meta
designcompactdsl
request
repair-1
repair-2
...
```

其中：

- `genui`：标准三段 A2UI。
- `designcompactdsl`：模型原始 Design Compact DSL，用于调试和回放。
- `request`：本轮 WebSocket 请求体 JSON 原文，保留外层包络、业务字段和原始文本格式。
- `repair-N`：第 N 轮 repair 的模型极简协议、转换后标准 DSL 和本轮质量异常；未发生 repair 时不写。
- `generationPlan`：保留候选字段投影，供后续编辑继承。
- `meta.protocolProfileId`：最终标准 A2UI Profile。
- `meta.generationMode`：`create` 或 `edit`。

保存过程：

```text
ArtifactStore.save
→ 写本地临时 Markdown
→ file_obs.upload_file
→ 返回 URL 和摘要
→ 删除本地临时文件
```

## 13. 响应数据流

业务响应示例：

```json
{
  "status": "success",
  "artifactUrl": "上传后的地址",
  "artifactDigest": "sha256:...",
  "suggestSize": "2x4",
  "message": "已为你生成卡片。",
  "removedCapabilities": [],
  "errorCode": "",
  "effectiveCapabilities": {
    "data": [
      "ViewWeather"
    ],
    "event": [],
    "asset": [
      "asset.drop_1"
    ]
  }
}
```

外层 final 帧：

```json
{
  "errorCode": "0",
  "errorMessage": "",
  "reply": {
    "streamInfo": {
      "streamContent": "完整旧业务消息的字符串形式",
      "streamingTextId": "session-001&interaction-compact-001",
      "streamType": "final",
      "textType": "plainText"
    },
    "items": []
  }
}
```

## 14. 主要终止点

| 阶段 | 结果 |
| --- | --- |
| 请求参数错误 | 返回参数错误 final 帧 |
| 协议区间未命中且不允许回退 | 返回版本不支持 |
| 编辑开关关闭 | 返回 `WIDGET_EDIT_DISABLED` |
| 来源 artifact 无效 | 返回来源错误，不转首次生成 |
| 原请求包含数据绑定，但最终既无有效数据绑定也无有效事件 | 返回不支持，不调用模型 |
| 模型失败或空输出 | 返回模型生成失败，不保存 artifact |
| Design DSL 解析或转换失败 | 可选 repair；最终失败则不保存 |
| 标准 A2UI Validator 失败 | 可选 repair；最终失败则不保存 |
| OBS 上传失败 | 异常上抛到 WebSocket 路由，返回服务失败 final 帧 |
