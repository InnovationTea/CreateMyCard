# 模板生成模块

本目录是 `generateWidgetCardCompactDsl` 和 `generateWidgetCardTerseDslNested2` 共用的模板 source DSL 生成能力边界。
模板判断、模板展开、Provider 资源、测试和设计文档位于 `cloud/services/template_generation/`；通用
生成编排仍由 `WidgetGenerationService` 统一负责。

## 对外接口

外部只调用源 DSL 字符串生成接口，并显式提供主生成流程已构造的依赖：

```python
await request_template_source_dsl(
    task_spec,
    card_spec,
    effective_bindings,
    processor_kind=processor_kind,
    protocol_profile=protocol_profile,
    model_runtime=model_runtime,
    model_request_context=model_request_context,
)
```

返回规则：

- `config/template_controls.json` 是模板模块内的唯一管控配置。`disabledProviderIds` 按 Provider 关闭
  整个业务模板集合，`disabledTemplateIds` 只关闭指定完整模板 ID。
- 业务模板在对应 Provider 的 `templates` 条目中直接声明 `businessId` 与 `capabilityId`，Registry 按模板
  派生业务分组；布局组件由 Layout Provider 的 `provider.json#layoutComponents` 定义。中央 UX 配置不重复
  维护组件和模板归属。
- 禁用项在首层 Prompt 构造前过滤，二层 Provider 规则和布局候选也应用同一结果；服务端契约会再次拒绝
  被禁用的模板。
- 模板模块只返回当前 Processor 可直接消费的源 DSL 字符串，不接收主服务对象，也不调用
  原始生成逻辑。
- 能力前置裁决以及 CardSpec、TaskSpec、artifact、`GenerateWidgetCardResponse` 的组装不属于模板模块。
- edit 是否尝试模板由 `_generate_widget_card_with_policy` 判定；create 的模板异常由公共
  `generate_source_dsl` 在同一次调用内回退原协议模型。
- create 请求先由第一层 LLM 只输出 `theme`、`componentCandidates`、`action`；每个组件候选同时给出
  当前可交给第二层继续选择的 `availableTemplateIds`。
- 第一层失败时仍返回最匹配的候选 Theme，以空 `componentCandidates` 和空 `action` 表示模板不适用。
- Search 模板路由仅支持一个数据业务组件，以及一个数据业务组件加可选 Action；多个数据能力或必须联合
  多个业务组件覆盖字段时，在调用第二层前判定模板不适用。
- 第二层的业务 UI 和布局骨架都使用 `Template` 调用；模板 ID 直接表达形态，不再输出 Variant。
- 第一层拒绝、输出非法、调用失败、确定性覆盖检查不通过，以及后续生成异常，由字符串接口直接抛出。
- Compact 与 Terse 共用 `request_template_source_dsl`；模板内部把 A2UI 或模板 Terse 中间产物
  转为当前 Processor 的源格式。
- Compact 和 Terse create 的模板 source generator 任意异常都回退原协议首次生成。模板源 DSL 已
  返回后的 Processor 或 Validator 错误只走公共 repair，不重试模板。
- 模板成功后的 Processor、最终校验、artifact 保存和响应组装全部复用主生成链。

旧 Python Terse 模板流水线只保留
`route_legacy_python_terse_generation(...)` 诊断入口，用于临时对比定位，不属于生产默认路由。

## 目录边界

```text
template_generation/
├── facade.py                 仅对外提供源 DSL 字符串生成接口
├── source_adapter.py          将模板产物转为当前 Processor 的源格式
├── binding_dependencies.py   仅供模板渲染使用的字段依赖补齐
├── legacy_python.py          旧 Python Terse 流水线诊断入口
├── model_client.py           第一层/第二层模型窄适配器
├── engine/                   受限 DSL、模板匹配和确定性编译
├── resources/source/         Provider 清单、Schema、模板和主题资源
├── tests/                    模板能力独立测试
└── docs/                     本功能设计与接入文档
```

模块只复用已构造的 TaskSpec、CardSpec 和有效数据绑定；模型运行时和请求上下文由调用方显式提供。
模板模块不依赖通用 Builder、Validator、ArtifactStore 或 API Response，不得通过主服务对象调用私有能力或
反向调用原协议逻辑。

领域选择规则不直接写入 Python SystemPrompt。每个业务 Provider 通过 `provider.json` 显式登记
`dataDomain`、首层和二层 MD；布局 Provider 只登记可接收 `...children` 的布局模板。
Theme 通过 `theme-profiles.json` 登记只供首层使用的 MD。首层只加载候选 Provider/Theme 文档，二层只加载
已选 Provider 文档。

详细流程见 [architecture.md](architecture.md)，Provider 接入见
[provider-template-contract.md](provider-template-contract.md)。
