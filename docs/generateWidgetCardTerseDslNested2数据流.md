# generateWidgetCardTerseDslNested2 数据流

本文描述 `generateWidgetCardTerseDslNested2` WebSocket 接口在当前微服务代码中的真实数据流。接口契约
及规则仍以 `云侧方案设计.md` 为准；本文用于开发、联调和问题定位。

## 1. 接口定位

- WebSocket 路径：`/api/v1/ws/tools/generateWidgetCardTerseDslNested2`
- 请求模型：`GenerateWidgetCardRequest`
- 模型源格式：TerseDSL-Nested-2
- 最终 `genui`：由本地受限转换器生成的标准三段 A2UI JSONL
- 默认模型后端：`design_compact_model_backend`，当前默认值为 `openai`
- 支持创建：是
- 支持多轮编辑：是，由 `enable_widget_edit` 控制
- 当前代码是否允许动态数据和事件入参：否
- 转换或最终校验错误是否阻断保存：是

## 2. 方法调用链

```text
generate_widget_card_terse_dsl_nested2_ws
→ _serve_operation_websocket
→ _normalize_payload
→ _arguments_from_envelope
→ GenerateWidgetCardRequest
→ WidgetGenerationService.generate_widget_card_terse_dsl_nested2
→ WidgetGenerationService._compact_protocol_selection
→ WidgetGenerationService._generate_widget_card_with_policy
→ WidgetGenerationService._policy_unsupported_response
→ WidgetGenerationService.generate_widget_card
→ EditRequestNormalizer.normalize_create / normalize_edit
→ WidgetGenerationService._capability_registry
→ DeviceCapabilityResolver.resolve_generation_data_bindings
→ CardSpecBuilder.build
→ TaskSpecBuilder.build
→ PromptBuilder.build_terse_dsl_nested2
→ A2UIModelClient.generate
→ TerseNested2Processor.process
→ convert_terse_dsl_nested2_to_a2ui
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
- Terse 解析转换：`../widget_service/cloud/services/terse_dsl_nested2_converter.py`
- Prompt：`../widget_service/cloud/services/prompt_builder.py`
- Artifact 校验：`../widget_service/cloud/services/validator.py`
- Artifact 保存：`../widget_service/cloud/services/artifact_store.py`

## 3. WebSocket 请求

静态卡片示例：

```json
{
  "content": {
    "userQuery": "生成一张静态天气卡片",
    "size": "2x2",
    "title": "天气",
    "description": "天气速览",
    "candidateDataBindings": [],
    "candidateEventCandidates": [],
    "candidateAssetIds": []
  },
  "deviceInfo": {
    "locale": "zh-CN",
    "prdVer": "11.7.5.205",
    "romVersion": "CLS-AL30 6.0.0.328"
  },
  "session": {
    "sessionId": "session-001",
    "interactionId": "interaction-terse-001"
  },
  "utterance": {
    "original": "生成一张静态天气卡片",
    "type": "text"
  }
}
```

路由归一化结果：

```text
requestId = session-001&interaction-terse-001
prdVer = 11.7.5.205
device.romVersion = 6.0
device._source_rom_version = CLS-AL30 6.0.0.328
```

请求通过 Pydantic 校验后，服务发送 `start` 帧，并每 6 秒发送一次空内容 `partial` 心跳。

## 4. 协议选择和路由策略

该接口同样调用 `_compact_protocol_selection()` 选择最终标准 A2UI Profile。

当前 App/ROM 示例命中：

```json
{
  "protocolProfileId": "a2ui-form-rom6.0-v1",
  "designProfileId": "design-compact-dsl"
}
```

但第五接口不会使用选择结果中的 `designProfileId` 作为模型格式，而是将模型格式固定为
`terse-dsl-nested-2`。

最终策略：

```text
operation = generateWidgetCardTerseDslNested2
protocol_profile_id = a2ui-form-rom6.0-v1
backend = design_compact_model_backend
processor_kind = TERSE_NESTED2
source_format = terse-dsl-nested-2
model_profile_id = terse-dsl-nested-2
model_format = terse-dsl-nested-2
design_profile_id = terse-dsl-nested-2
supports_edit = true
supports_dynamic_capabilities = false
validation_failure_blocking = true
stores_design_token = true
```

其中：

- 最终标准 A2UI 按 `a2ui-form-rom6.0-v1` 校验和保存。
- 模型 Prompt 从 `terse-dsl-nested-2` 目录读取。
- 确定性转换参数从 `terse-dsl-nested-2/protocol.json` 读取。
- 请求中的 `protocolProfileId` 不能覆盖路由策略。

## 5. 创建和编辑请求

创建模式由 `EditRequestNormalizer.normalize_create()` 补齐默认值。编辑模式执行：

```text
SourceArtifactRepository.load(sourceArtifactUrl)
→ 读取 designcompactdsl 中的上一轮 TerseDSL-Nested-2
→ 使用 Terse Processor 校验源格式
→ EditRequestNormalizer.normalize_edit(request, sourceArtifact)
```

缺少、为空、超长或无法按 Terse 格式解析的 `designcompactdsl` 返回
`SOURCE_ARTIFACT_INVALID`，不得使用标准 `genui` 或首次生成兜底。

## 6. 能力裁决

创建请求进入公共生成主流程后，能力处理与另外两个生成接口一致：

```text
_capability_registry
→ resolve_generation_data_bindings
→ 事件注册检查
→ 素材注册检查
```

生成阶段只检查：

- 数据能力是否注册。
- `arguments` 是否符合 `inputSchema`。
- `writeResultTo` 是否为 `/data/...` 路径。
- 多个写入路径是否冲突。
- 事件和素材是否注册。

不会查询 IDS，也不会重新检查应用安装状态。

当前代码的 `supports_dynamic_capabilities=true`，因此下面的请求不会在路由策略层被拒绝：

```json
{
  "candidateDataBindings": [
    {
      "capabilityId": "ViewWeather",
      "arguments": {
        "prefectureName": "上海市",
        "districtName": "青浦区"
      },
      "writeResultTo": "/data/weather",
      "candidateOutputFields": [
        "/current/temperatureText",
        "/current/condition"
      ]
    }
  ]
}
```

这与当前方案文档中“首版只支持静态卡片”的描述存在差异；本文记录的是当前代码实际行为。

## 7. CardSpec 和 TaskSpec

静态请求的 CardSpec：

```json
{
  "title": "天气",
  "description": "天气速览",
  "suggestSize": "2x2"
}
```

静态请求的 TaskSpec：

```json
{
  "userQuery": "生成一张静态天气卡片",
  "size": "2x2",
  "eventCandidates": [],
  "dataModelSchema": {
    "data": {}
  },
  "assetCandidates": []
}
```

如果传入当前代码允许的动态天气候选，则 TaskSpecBuilder 仍会执行字段投影：

```text
/data/weather + /current/temperatureText
→ /data/weather/current/temperatureText
```

得到：

```json
{
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
        }
      }
    }
  }
}
```

投影仍采用宽容策略，数组只接受 `/0/`，缺失示例值时生成受控默认值。

## 8. TerseDSL-Nested-2 Prompt

调用：

```text
PromptBuilder.build_terse_dsl_nested2()
```

System 消息读取：

```text
cloud/data/protocol_profiles/terse-dsl-nested-2/PROMPT.md
```

User 消息是完整 TaskSpec JSON：

```json
[
  {
    "role": "system",
    "content": "TerseDSL-Nested-2 完整系统提示词"
  },
  {
    "role": "user",
    "content": "{\"userQuery\":\"生成一张静态天气卡片\",\"size\":\"2x2\",...}"
  }
]
```

编辑模式仍保持上述 `PROMPT.md` 原文作为 system，并将第二条 user 消息改为：

```json
{
  "mode": "edit",
  "userQuery": "修改背景",
  "taskSpec": {},
  "previousDesignToken": {
    "format": "terse-dsl-nested-2",
    "content": "来源 artifact 的 designcompactdsl 原文"
  }
}
```

## 9. 模型调用

`A2UIModelClient` 接收到的模型 Profile：

```json
{
  "id": "terse-dsl-nested-2",
  "format": "terse-dsl-nested-2"
}
```

数据源：

- `enable_a2ui_model_mock=true`：读取 `cloud/custom/mock.terse-dsl-nested-2.dat`。
- mock 关闭：调用 `design_compact_model_backend`，当前默认 `openai`。该复合后端默认先调用
  DeepSeek Platform，模型异常重试耗尽后再切换到 llmclient。

模型输出示例：

```text
Column("card",
  Text("天气速览", "title"),
  Column("section",
    Text("26℃", "success"),
    Text("晴 · 空气优", "subtitle")
  ),
  Button("查看详情", "primary")
);
```

`A2UIModelClient` 只提取代码块内容，不在客户端中把该 DSL 转成标准 A2UI。真正的转换发生在
`TerseNested2Processor`。

## 10. 受限解析和确定性转换

调用：

```text
TerseNested2Processor.process
→ convert_terse_dsl_nested2_to_a2ui
```

转换上下文：

```text
size = CardSpec.suggestSize
protocol_profile = terse-dsl-nested-2/protocol.json
card_spec = 当前 CardSpec
task_spec = 当前 TaskSpec
```

转换器只允许：

- 单棵直接嵌套的组件调用树。
- 白名单组件。
- 字面量字符串、数值、布尔值和受控对象。
- 白名单 Design Token。
- 白名单 LayoutPreset。
- 安全对象键。

转换器拒绝：

- 未知函数和未知组件。
- 任意变量读取。
- 函数执行表达式。
- 不受支持的构造参数。
- 根组件不符合约束的布局。
- 额外的可执行语句。

转换结果固定为标准三段 A2UI：

```text
第 1 行：createSurface
第 2 行：updateComponents
第 3 行：updateDataModel
```

转换失败会产生 `TERSE_CONVERSION_FAILED`，不会保存源 DSL 作为正式 `genui`。

## 11. 校验和 repair

转换后的标准 A2UI 进入：

```text
ArtifactValidator.validate
→ services.card_validation.validate_card
```

重试流程：

```text
首次 Terse 模型输出
→ Terse Processor
→ 转换 error，或转换成功后标准 A2UI Validator 返回 error
→ enable_validation_failure_retry=true
→ PromptBuilder.build_repair
→ 模型重新输出完整 TerseDSL-Nested-2
→ 再次转换和校验
```

repair Prompt 中的 `dslFormat` 固定为 `terse-dsl-nested-2`，`invalidSourceDsl` 保存当前最新 Terse DSL，
`qualityErrors` 传递结构化的 `stage/code/message`，不允许模型改为标准 A2UI 或 Design Compact DSL。

本接口为严格模式：

- Terse 解析或转换失败且修复未成功：返回 `VALIDATION_FAILED`。
- 标准 A2UI 校验仍有 error：返回 `VALIDATION_FAILED`。
- 严格失败时不构造、不上传 artifact。

## 12. Artifact 保存

成功时：

- `artifact.genui` 保存转换后的标准 A2UI。
- 模型原始 Terse DSL 作为调试源 DSL 保存。
- `meta.protocolProfileId` 保存最终标准 A2UI Profile。
- `meta.generationMode` 为 `create` 或 `edit`；edit 同时记录来源摘要。

当前 Markdown 文件块顺序：

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
```

第四、第五接口约定复用 `designcompactdsl` 代码块。第五接口在该块保存本轮最终 TerseDSL-Nested-2
原始输出，用于下一轮编辑；正式渲染内容仍是 `genui` 中转换后的标准 A2UI。

保存过程：

```text
生成 UUID artifactId
→ 写本地临时 Markdown
→ file_obs.upload_file
→ 返回 artifactUrl 和 artifactDigest
→ 删除本地临时文件
```

## 13. 响应数据流

成功响应示例：

```json
{
  "status": "success",
  "artifactUrl": "上传后的地址",
  "artifactDigest": "sha256:...",
  "suggestSize": "2x2",
  "message": "已为你生成卡片。",
  "removedCapabilities": [],
  "errorCode": "",
  "effectiveCapabilities": {
    "data": [],
    "event": [],
    "asset": []
  }
}
```

WebSocket final 帧：

```json
{
  "errorCode": "0",
  "errorMessage": "",
  "reply": {
    "streamInfo": {
      "streamContent": "完整旧业务消息的字符串形式",
      "streamingTextId": "session-001&interaction-terse-001",
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
| 来源缺少或无法解析 `designcompactdsl` | 返回 `SOURCE_ARTIFACT_INVALID`，不调用模型 |
| 原请求包含数据绑定，但最终既无有效数据绑定也无有效事件 | 返回不支持，不调用模型 |
| 模型失败或空输出 | 返回模型生成失败，不保存 artifact |
| Terse DSL 语法或白名单校验失败 | 可选 repair；最终失败则不保存 |
| Terse 到标准 A2UI 转换失败 | 可选 repair；最终失败则不保存 |
| 标准 A2UI Validator 失败 | 可选 repair；最终失败则不保存 |
| OBS 上传失败 | 异常上抛到 WebSocket 路由，返回服务失败 final 帧 |

## 15. 兼容约束

第四、第五接口虽然复用 `designcompactdsl` 块名，但源语法不同。编辑前必须用目标接口对应 Processor
验证来源 Token；跨接口来源不得交给模型，也不得回退标准 `genui`。
