# generateWidgetCardTerseDslNested2 数据流

本文描述 `generateWidgetCardTerseDslNested2` WebSocket 接口在当前微服务代码中的真实数据流。接口契约
及规则仍以 `云侧方案设计.md` 为准；本文用于开发、联调和问题定位。

## 1. 接口定位

- WebSocket 路径：`/api/v1/ws/tools/generateWidgetCardTerseDslNested2`
- 请求模型：`GenerateWidgetCardRequest`
- 模板源格式：Design Compact DSL，由模板 A2UI 确定性回转
- 最终 `genui`：由公共 Design Compact 转换器生成的标准三段 A2UI JSONL
- 默认模型后端：`design_compact_model_backend`，当前默认值为 `openai`
- 支持创建：是
- 支持多轮编辑：否，当前生产入口严格限定为模板 create 路线
- 当前代码是否允许动态数据和事件入参：是
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
→ edit 请求在 Terse 入口直接返回 failed
→ WidgetGenerationService._generate_widget_card_with_policy
→ WidgetGenerationService._policy_unsupported_response
→ WidgetGenerationService.generate_widget_card
→ EditRequestNormalizer.normalize_create
→ WidgetGenerationService._capability_registry
→ GenerationPreflight.run 统一构造 CardSpec / TaskSpec
→ PromptBuilder 与 A2UIModelClient 构造 Compact repair 所需上下文
→ generate_source_dsl 统一发送模型开始通知
→ generate_source_dsl 先调用 request_template_source_dsl
→ 模板内部补齐自身绑定依赖，生成 A2UI 并回转 Design Compact DSL
→ 模板 source generator 任意异常时，generate_source_dsl 直接返回失败
→ DesignCompactProcessor.process
→ ArtifactValidator.validate
→ RetryController.run
→ WidgetGenerationService._build_artifact
→ ArtifactStore.save
→ ResponsePlanner.plan
→ _build_plugin_stream_response
```

edit 由 `generate_widget_card_terse_dsl_nested2` 入口直接返回 failed。create 的模板不匹配、生成或模板内部
源格式转换异常都直接返回 failed，不再调用原 Terse 模型。模板 Design Compact DSL 已返回后的转换或
Validator 错误只进入公共 Compact repair，不重试模板，也不重新执行通用首次生成。保存异常不触发
生成路由回退。

主要代码位置：

- 路由入口：`../widget_service/cloud/api/routes.py`
- 生成编排：`../widget_service/cloud/services/widget_generation_service.py`
- 路由策略和 Processor：`../widget_service/cloud/services/generation_pipeline.py`
- Design Compact 转换：`../widget_service/cloud/services/compact_dsl_a2ui_converter.py`
- Prompt：`../widget_service/cloud/services/prompt_builder.py`
- Artifact 校验：`../widget_service/cloud/services/validator.py`
- Artifact 保存：`../widget_service/cloud/services/artifact_store.py`
- 模板 source DSL 窄接口：`../widget_service/cloud/services/template_generation/facade.py`
- 模板源格式适配：`../widget_service/cloud/services/template_generation/source_adapter.py`

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

路由仍使用 `TERSE_NESTED2` 标识第五接口，以便 `generate_source_dsl` 对模板失败执行终止策略；模板
成功后的实际源格式和 Processor 使用选择结果中的 `designProfileId`。

路由标识与模板有效处理策略：

```text
operation = generateWidgetCardTerseDslNested2
protocol_profile_id = a2ui-form-rom6.0-v1
backend = design_compact_model_backend
processor_kind = TERSE_NESTED2
template_source_processor = DESIGN_COMPACT
template_source_format = design-compact-dsl
template_model_profile_id = design-compact-dsl
template_model_format = compact-dsl
design_profile_id = design-compact-dsl
supports_edit = false
supports_dynamic_capabilities = true
validation_failure_blocking = true
stores_design_token = true
```

其中：

- 最终标准 A2UI 按 `a2ui-form-rom6.0-v1` 校验和保存。
- 公共 repair Prompt 和确定性转换参数从选中的 Design Compact Profile 读取。
- `TERSE_NESTED2` 只用于路由身份和模板失败策略，不处理模板成功产物。
- 请求中的 `protocolProfileId` 不能覆盖路由策略。

## 5. 创建和编辑请求

创建模式由 `EditRequestNormalizer.normalize_create()` 补齐默认值。携带 `sourceArtifactUrl` 的编辑请求在
`generate_widget_card_terse_dsl_nested2` 入口直接返回 failed，不加载来源 artifact，也不校验来源
`designcompactdsl`。

```text
sourceArtifactUrl 存在
→ GenerateWidgetCardResponse(status=failed, errorCode=A2UI_GENERATION_FAILED)
```

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

## 8. 模板 Prompt 与源格式

模板模块使用自己的首层和二层 Prompt 选择 Theme、业务模板、布局与可选 Action。公共生成链仍构造
Compact Prompt 和 `A2UIModelClient`，用于模板源 DSL 返回后的公共 repair，不参与模板首层和二层选择。

模板引擎先生成标准三段 A2UI，再由 `template_generation/source_adapter.py` 执行：

```text
模板 A2UI
→ 适配当前 Form Profile
→ convert_a2ui_to_compact_dsl
→ Design Compact DSL
```

模板不匹配、模板模型失败、可信展开失败或 A2UI 回转 Compact 失败都会从模板 source generator 抛出；
`generate_source_dsl` 检测当前路由的 `processor_kind` 为 `TERSE_NESTED2` 后直接转换为生成失败，不调用
原 Terse 模型。

## 9. 公共模型调用

模板成功时不执行通用首次模型生成。`A2UIModelClient` 使用当前 App/ROM 选择出的 Design Compact Profile，
仅在 Compact 源 DSL 转换或最终校验触发 repair 时调用。模板异常发生在源 DSL 返回之前，因此不会触发
repair，也不会调用通用首次生成。

旧 Terse Prompt、mock 和 `TerseNested2Processor` 只保留给显式的
`route_legacy_python_terse_generation(...)` 诊断入口，不属于第五接口生产模板路线。

## 10. Design Compact 确定性转换

生产模板路线调用：

```text
DesignCompactProcessor.process
→ repair_compact_dsl_binding_paths
→ validate_compact_dsl_context
→ convert_compact_dsl_to_a2ui
```

转换上下文包含当前 CardSpec、TaskSpec、尺寸和 App/ROM 选择出的 Design Compact Profile。模板 Theme
已经转换为根节点背景色、渐变和前景样式，公共 Compact Processor 必须保持这些属性。

转换结果固定为标准三段 A2UI：

```text
第 1 行：createSurface
第 2 行：updateComponents
第 3 行：updateDataModel
```

## 11. 校验和 repair

转换后的标准 A2UI 进入：

```text
ArtifactValidator.validate
→ services.card_validation.validate_card
```

重试流程：

```text
模板 Design Compact DSL
→ Design Compact Processor
→ 转换 error，或转换成功后标准 A2UI Validator 返回 error
→ enable_validation_failure_retry=true
→ PromptBuilder.build_repair
→ 模型重新输出完整 Design Compact DSL
→ 再次转换和校验
```

repair Prompt 的 `dslFormat` 使用当前 Design Compact Profile，`invalidSourceDsl` 保存最新 Compact DSL，
`qualityErrors` 传递结构化的 `stage/code/message`。repair 不重试模板，也不切回 Terse 源格式。

本接口为严格模式：

- Design Compact 解析或转换失败且修复未成功：返回 `VALIDATION_FAILED`。
- 标准 A2UI 校验仍有 error：返回 `VALIDATION_FAILED`。
- 严格失败时不构造、不上传 artifact。

## 12. Artifact 保存

成功时：

- `artifact.genui` 保存转换后的标准 A2UI。
- `designcompactdsl` 保存模板 A2UI 回转后的 Design Compact DSL。
- `meta.protocolProfileId` 保存最终标准 A2UI Profile。
- `meta.generationMode` 固定为 `create`，Terse 模板入口不支持 edit。

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

第四、第五接口约定复用 `designcompactdsl` 代码块，并统一保存 Design Compact DSL；正式渲染内容仍是
`genui` 中转换后的标准 A2UI。第五接口当前不使用该块进行下一轮编辑。

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
  "apiVersion": "v1",
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
| 请求携带 `sourceArtifactUrl` | 入口直接返回生成失败，不加载来源 artifact |
| 原请求包含数据绑定，但最终既无有效数据绑定也无有效事件 | 返回不支持，不调用模型 |
| 模板不匹配或模板 source generator 异常 | 直接返回模型生成失败，不调用原 Terse 模型 |
| Design Compact DSL 语法或上下文校验失败 | 可选 Compact repair；最终失败则不保存 |
| Design Compact 到标准 A2UI 转换失败 | 可选 Compact repair；最终失败则不保存 |
| 标准 A2UI Validator 失败 | 可选 repair；最终失败则不保存 |
| OBS 上传失败 | 异常上抛到 WebSocket 路由，返回服务失败 final 帧 |

## 15. 兼容约束

第四、第五接口的生产模板路线统一在 `designcompactdsl` 保存 Design Compact DSL。第四接口支持按来源
Token 编辑；第五接口仍在入口拒绝 edit，不把来源 Token 交给模型，也不回退标准 `genui`。
