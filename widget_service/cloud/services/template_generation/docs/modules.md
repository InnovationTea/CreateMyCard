# Template Generation 模块与代码说明

## 1. 调用链索引

从 WebSocket 请求到模板引擎的代码路径如下：

```text
cloud/api/routes.py
  -> WidgetGenerationService.generate_widget_card_compact_dsl()
     或 generate_widget_card_terse_dsl_nested2()
  -> WidgetGenerationService._generate_widget_card_with_policy()
  -> WidgetGenerationService.generate_widget_card()
  -> generate_source_dsl()
  -> template_generation.request_template_source_dsl()
  -> engine.generate_template_a2ui()
  -> source_adapter.prepare_template_source_dsl()
  -> 公共 DesignCompactProcessor
```

对应源码：

- [WebSocket 路由](../../../api/routes.py)
- [公共生成编排](../../widget_generation_service.py)
- [公共 DSL Processor](../../generation_pipeline.py)
- [模板窄入口](../facade.py)
- [模板主流水线](../engine/pipeline.py)
- [source DSL 适配](../source_adapter.py)

## 2. 顶层文件

### `__init__.py`

文件：[../__init__.py](../__init__.py)

公开导出：

- `request_template_source_dsl`：生产模板 source DSL 入口。

外部调用方不应穿过该文件直接调用 `engine` 内部方法。

### `source_generator.py` 与公共融球门控

文件：[../source_generator.py](../source_generator.py)、
[../../fusion_ball_expander.py](../../fusion_ball_expander.py)

`TemplateSourceGenerator` 从公共生成链接收已构造的 `TaskSpec`，直接使用其中已有的 `appVersion`。
公共 `fusion_ball_enabled()` 将该值与 `CONFIG.fusion_ball_min_prd_version` 比较；任一值缺失、类型错误、
版本非法或低于最低版本时均关闭。模板模块不重新实现门控，不重新读取接口请求，也不复制或规范化版本字段。

### `facade.py`

文件：[../facade.py](../facade.py)

`request_template_source_dsl()` 是主责任边界：

1. 使用调用方传入的 `ModelExecutionRuntime` 和 `ModelRequestContext` 创建模板模型客户端。
2. 要求调用方显式传入 `enable_fusion_ball: bool`，并将 `TemplateSourceGenerator` 基于
   `TaskSpec.appVersion` 和 `CONFIG.fusion_ball_min_prd_version` 得出的请求级决策透传给模板引擎；配置或版本
   缺失、非法、低于配置版本时该决策为关闭。
   有融球 Theme 命中任一候选业务时，第一层 LLM 只接收匹配的
   融球 Theme 候选。
3. 复制已裁决的 `effective_bindings`，不增加新数据能力或字段。
4. 调用 `generate_template_a2ui()` 获得受信展开后的 A2UI 和诊断信息。
5. 调用 `prepare_template_source_dsl()` 转成当前 Processor 要求的源格式。
6. 只记录 Template ID、融球开关和展开节点数，返回 DSL 字符串。

该文件不导入业务响应、artifact 或 Validator 类型，这是防止模板模块反向接管主生成链的关键限制。

### `controls.py`

文件：[../controls.py](../controls.py)；配置：[../config/template_controls.json](../config/template_controls.json)

- `TemplateControls`：严格、冻结的 Pydantic 配置模型。
- `load_template_controls()`：带缓存加载配置，拒绝非法 JSON、额外字段和重复 ID。

配置字段：

| 字段 | 作用 |
| --- | --- |
| `disabledProviderIds` | 在候选构造前禁用整个 Provider |
| `disabledTemplateIds` | 只禁用指定完整 Template ID |
| `firstLayerComponentSelector` | `search` 使用“LLM 字段标定 + 确定性 Search”；`llm` 使用旧首层候选决策 |

### `binding_dependencies.py`

文件：[../binding_dependencies.py](../binding_dependencies.py)

`enrich_template_bindings()` 当前只逐项复制有效绑定。函数名保留了边界语义：模板不能因为缺字段就
自行扩展 `candidateOutputFields`；缺失应导致候选不匹配。

### `model_client.py`

文件：[../model_client.py](../model_client.py)

- `TemplateModelClient.generate_json()`：用于首层结构化决策，支持去除 Markdown fence 和 JSON repair。
- `TemplateModelClient.generate()`：用于二层受限 DSL 文本。
- `create_template_model_client()`：复用公共模型运行时和 `design_compact_model_backend`。

当运行时缺失或 `enable_a2ui_model_mock=true` 时，工厂抛出 `TemplateModelUnavailable`。
这不会在模板模块内生成伪造产物；Compact/Tersel 由外层按各自回退策略处理。

### `source_adapter.py`

文件：[../source_adapter.py](../source_adapter.py)

`prepare_template_source_dsl()` 先用 `_adapt_to_protocol_profile()` 确定性对齐：

- 三段 A2UI 的 `surfaceId` 一致性。
- `createSurface.catalogId` 与当前 Form Profile。
- 根组件 `width/height="matchParent"`、`borderRadius=18`、`clip=true`。

当 Processor 为 `DESIGN_COMPACT` 时，再调用模板内部 `convert_a2ui_to_compact_dsl()` 回转源 Token。
这一回转不替代公共 `DesignCompactProcessor`；后者仍会完成最终转换和校验。

## 3. `engine/pipeline.py`

文件：[../engine/pipeline.py](../engine/pipeline.py)

### 核心类型

- `TemplateGenerationError`：首层已确认候选后，二层生成或编译失败。
- `TemplateEngineOutput`：保存标准 A2UI、内部 Tersel、投影 TaskSpec、Template ID、
  受信素材、展开节点数和 Theme ID。

### `generate_template_a2ui()`

模块主编排函数：

1. `2x4` 在 Registry、首层 Prompt 和模型调用前直接返回模板不适用；当前模板 Search 只支持 `2x2`。
2. 按 `TemplateSourceGenerator` 使用 `TaskSpec.appVersion` 和配置最低版本确定的 `enable_fusion_ball` 加载
   请求级 Registry 视图；关闭时先移除所有融球 Theme，开启时按本轮候选业务过滤
   Theme，只要存在融球匹配就移除全部非融球 Theme，再从 CardSpec 取得已批准能力 ID。
3. 应用领域 content selectors，建立 `DataShape`。
4. 根据 `firstLayerComponentSelector` 进入 Search 或旧 LLM 首层路线。
5. 将请求转换为 `TemplateRouteSelection`；Search 结果只允许一个业务组件，候选解析后命中多个业务时，在布局后缀过滤和
   二层调用前显式失败；单业务可保留零到两个显式 Action。
6. 调用 `_generate_selected_templates()` 完成二层生成、受信编译和 A2UI 产出。

### `_generate_selected_templates()`

- `project_content_component_facts()` 保留已选业务所需的事实。
- `_with_provider_template_runtime_data()` 补回 Provider 必需路径和事件表达式依赖。
- `build_ux_mixed_prompt()` 生成二层专用轻量 Prompt 和硬契约；静态部分只保留类 Tersel 语法，
  布局、候选模板、Action 和完整 Props 签名均按本轮 Search 结果动态下发。
- `_generate_hybrid_body()` 调用共享模型生成受限布局/Template 调用。
- `frame_ux_layout_root_children()` 补全根布局包装。
- `compile_ux_layout_card()` 完成硬校验和展开；质量错误最多进行两次二层修复。

## 4. `engine/advanced/`

### `data_shape.py`

文件：[../engine/advanced/data_shape.py](../engine/advanced/data_shape.py)

`extract_data_shape()` 把 TaskSpec 的数据模式转为稳定的字段轮廓，供首层标定和确定性准入使用。

### `content_selectors.py`

文件：[../engine/advanced/content_selectors.py](../engine/advanced/content_selectors.py)

该文件包含两类逻辑：

- `extract_*_facts()` 和 `*Facts` 类型：从 TaskSpec 中提取受信业务事实。
- `*_is_eligible()`、`*_variants()`、`apply_content_selectors()`：执行领域准入与内容投影。

该文件不应根据 `sampleValue` 相等关系推测字段身份。新领域应先定义 Provider 契约，再补最小必要的
受信事实提取和回归测试。

### `scope_planner.py`

文件：[../engine/advanced/scope_planner.py](../engine/advanced/scope_planner.py)

- `TemplateRouteNotApplicable`：模板无法完整覆盖当前请求。
- `plan_template_route_with_llm()`：`firstLayerComponentSelector=llm` 时的旧首层路线。
- `resolve_available_capability_ids()`：对齐 TaskSpec、Registry 和 CardSpec 中的能力边界。
- `task_spec_with_selected_action()`：只保留首层显式选中的 Action。

Search 默认路线仍复用该文件的能力和 Action 边界函数，但不调用旧的最终候选 LLM 决策。

### `ux_mixed_prompt.py` 与 `ux_mixed_framer.py`

文件：[Prompt](../engine/advanced/ux_mixed_prompt.py)，[Framer](../engine/advanced/ux_mixed_framer.py)

- `build_ux_mixed_prompt()` 将首层候选、唯一 Layout、Action、Theme ID、可信素材和相关
  Provider 指导组合为二层契约，不再拼接通用 Hybrid Prompt。
- `build_ux_mixed_validation_retry_prompt()` 针对二层受限输出的具体校验错误构造修复消息，
  首次失败后最多重试两次。
- `frame_ux_layout_root_children()` 确保二层产物只在已批准 Layout 根内组合。

### `models.py`

文件：[../engine/advanced/models.py](../engine/advanced/models.py)

严格 Pydantic 模型定义首层输入输出、业务组件候选、尺寸预算和 `TemplateRouteSelection`。
其 `extra="forbid"` 是模型输出闭包的一部分，不应为兼容模型幻觉而放宽。

## 5. `engine/cardplan/`

### `template_retrieval.py` 与 `retrieval_index.py`

文件：[Search](../engine/cardplan/template_retrieval.py)，[索引](../engine/cardplan/retrieval_index.py)

- `build_template_retrieval_prompt()` 让首层只输出 Theme、显式字段和 Action。
- `retrieve_template_variants()` 根据字段 Token、数据能力、尺寸和 CardSpec 确定性返回二层候选。
- `TemplateRetrievalMiss` 表示当前 Search 约束下无完整覆盖。

Search 不选最终 Template、Layout 或 Props，也不改写用户尺寸。

### `registry.py`

文件：[../engine/cardplan/registry.py](../engine/cardplan/registry.py)

`CardPlanRegistry` 是受信模板资产的只读索引，负责：

- 加载 Provider Bundle、Theme、UX 预算和 Template Controls。
- 派生业务组、数据能力、Provider 和 Template 映射。
- 提供禁用过滤后的 Template、Layout、Theme 和分层规则。
- 按 `TaskSpec.appVersion` 与配置最低版本裁决出的请求级 `enable_fusion_ball` 过滤融球 Theme，并让 Prompt、
  检索、Theme 查找和编译共享同一视图。
- 构造 Search 索引与尺寸/组合准入。

`get_cardplan_registry()` 按融球开关分别缓存两个只读视图。测试如果修改资源或 Controls，必须清理相关
缓存后再断言。

### `provider_bundle.py`

文件：[../engine/cardplan/provider_bundle.py](../engine/cardplan/provider_bundle.py)

主要入口：

- `load_provider_bundles()` / `load_provider_bundle()`：加载并严格校验 `provider.json`、分层 MD、Schema 和 CardTpl。
- `compile_card_template()`：将 `cardtpl/1` 编译为 `TemplateDefinition`，并把仅判断数据路径或 Prop
  可用性的带括号三元表达式降为受信的生成期条件 IR。
- `provider_template_admission()` 等准入函数：校验数据路径、尺寸、业务上下文和变体可用性。

安全限制包括文件大小、源文本长度、闭包组件集、禁止对象键、模板 ID/Provider ID 格式和
children 槽位数量。

### `prompt.py`

文件：[../engine/cardplan/prompt.py](../engine/cardplan/prompt.py)

`build_hybrid_prompt()` 仍用于构造可信素材、Action 和 Hybrid Contract，但它的通用消息文本不进入
第二层模型。`build_template_prompt_contracts()` 只为本轮候选动态生成完整 Props 签名；
`build_ux_mixed_prompt()` 把这些签名与唯一 Layout 和 Action 契约组合成最终轻量 Prompt。

### `parser.py`

文件：[../engine/cardplan/parser.py](../engine/cardplan/parser.py)

`parse_hybrid_card()` 和 `parse_ux_layout_card()` 使用 Python AST/tokenize 只解析闭包数据语法。
输出 `ParsedCall` 和 `SourceSpan`，供编译错误精确定位。它们不执行模型生成的任意 Python 代码。

### `compiler.py`

文件：[../engine/cardplan/compiler.py](../engine/cardplan/compiler.py)

- `compile_ux_layout_card()`：当前二层主入口。
- `compile_hybrid_card()`：执行通用受信展开、Theme/Action Lowering 和 A2UI 生成。
- `HybridCompilation`：同时保留原始输出、有效内部 DSL、A2UI 和展开统计。

编译器是模型输出的主要硬门禁，不应把布局、Action 或数据准入只放在 Prompt 文案中。

### `models.py`

文件：[../engine/cardplan/models.py](../engine/cardplan/models.py)

定义 `TemplateDefinition`、`TemplateVariant`、`TemplateNode`、`TemplateBinding`、`HybridBodyContract`、
`ThemeDefinition` 和 `ExpansionStats` 等受信结构。

### `fusion_ball_background.py`

文件：[编译期背景](../engine/cardplan/fusion_ball_background.py)

- `apply_fusion_ball_background()` 在 CardPlan 编译期读取 Theme 三色，直接展开标准 `Stack` 球体树并标记
  相邻内容 ID。

该模块不能自行维护场景色板；业务门禁由 CardPlan 在展开前确定性执行。Tersel、A2UI-Compact 和最终 A2UI
不允许残留 `FusionBall` 云端组件。

### `tersel_converter.py`

文件：[../engine/tersel_converter.py](../engine/tersel_converter.py)

模板内部 Tersel 解析与 A2UI 转换器，负责闭包语法、组件数、嵌套深度、表达式路径和
TaskSpec 数据序列化。旧 Python 诊断链和兼容 TerseDSL 转换器已删除，项目只保留这份模板内部实现；
表达式归一化复用 [A2UI 表达式模块](../engine/a2ui_expression.py)。协议参数由
[模板内部 Profile](../profile.py) 从 `resources/protocol_profiles/` 加载。

### `compact_dsl_a2ui_converter.py`

文件：[../engine/compact_dsl_a2ui_converter.py](../engine/compact_dsl_a2ui_converter.py)

模板内部归档/回转转换器，同时提供 `convert_a2ui_to_compact_dsl()`。生产最终 Processor 使用的是
[公共 Compact 转换器](../../compact_dsl_a2ui_converter.py)。修改两份实现时必须评估归档闭环和公共 Processor
是否仍保持等价，不能只验证单向转换。

### `preview_dataset.py`

文件：[../engine/cardplan/preview_dataset.py](../engine/cardplan/preview_dataset.py)

`build_template_preview_cases()` 和 `write_template_preview_dataset()` 不调用 LLM，直接从 Registry 展开所有
业务 Template，用于视觉预览、资产路径检查和统计回归。预览颜色优先使用能力匹配的非融球 Theme，其次使用
能力匹配的融球 Theme；某业务没有生产 Theme 时，仅在开发预览中使用应用时长中性主题解析 `$theme`。
该回退不参与生产 Registry 候选、Prompt 或模板路由。

## 6. `resources/source/`

目录：[../resources/source/](../resources/source/)

| 资源 | 职责 |
| --- | --- |
| `providers/*/provider.json` | Provider、能力数据根、业务归属、Template 清单和分层文档入口 |
| `providers/*/templates/*.cardtpl` | 受信 UI、Layout 或 Action 模板源码 |
| `providers/*/layer-docs/*.md` | 按候选动态加载的首层/二层垂域规则 |
| `themes/*/theme.json` | 单个 Theme 的真实颜色、根样式、Action 样式和场景归属 |
| `themes/*/first-layer.md` | 单个 Theme 的首层选择规则 |
| `themes/base/theme-base.json` | 跨 Theme 共享的 UX Token、尺寸预算和内容颜色属性映射 |
| `prompts/` | 由构建流程组合的首层/二层 Prompt 片段 |

Provider 契约的唯一事实源是 `provider.json` 和它引用的资源；Theme 契约的唯一事实源是对应主题目录和
`themes/base`。根目录不再维护 Template、Advanced Component、Theme 或 UX 的重复 Registry 文件。
模块文档中的数量和列表只是派生视图。

## 7. 测试分层

目录：[../tests/](../tests/)

| 文件 | 覆盖范围 |
| --- | --- |
| `test_template_generation.py` | 主流水线、准入、Prompt、展开、Theme、Action 和路由回归 |
| `test_template_retrieval.py` | 首层字段标定与确定性 Search |
| `test_template_internal_contracts.py` | CardTpl 语法、children 槽位、Action 和布局后缀契约 |
| `test_template_preview_dataset.py` | 预览数据集、模板统计、A2UI 结构和素材路径 |
| `test_a2ui_expression.py` | Tersel、CardTpl 共用表达式语法与路径归一化 |
| `test_tersel_protocol.py` | 当前模板内部 Tersel 解析与转换契约 |

修改 Python 代码后还需执行 Ruff、相关单元测试和 `git diff --check`；修改 Provider 资源时还应重建
CardPlan 清单并运行预览数据集测试。模块构建和画廊工具统一位于 `tools/`。
