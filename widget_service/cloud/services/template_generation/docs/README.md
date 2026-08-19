# 模板生成模块

本目录是 `generateWidgetCardCompactDsl` 和 `generateWidgetCardTerseDslNested2` 的独立模板能力边界。
模板判断、模板展开、Provider 资源、A2UI/设计 Token 双产物归档、测试和设计文档都位于
`cloud/services/template_generation/`，原始 dev 生成链不承载模板实现细节。

## 对外接口

外部只调用模板生成接口，并显式提供模板所需依赖：

```python
await generate_template_artifact(
    request,
    policy,
    registry=registry,
    model_runtime=model_runtime,
    model_request_context=model_request_context,
    before_model_call=before_model_call,
)
```

返回规则：

- 模板模块只负责模板生成结果，不接收主服务对象，也不调用原始生成逻辑。
- 模板接口内部识别 edit 请求并抛出不适用异常，由 Compact 或 Terse 公开入口执行原协议流程。
- create 请求先由第一层 LLM 判断一个或多个模板能否覆盖完整需求。
- 第一层拒绝、输出非法、调用失败、确定性覆盖检查不通过，以及后续生成、转换、校验或保存异常，均向公开
  入口抛出异常。
- Compact 与 Terse 公开入口捕获异常后，分别执行各自原协议流程。
- 模板成功时直接保存包含 `genui` 和 `designcompactdsl` 的标准 artifact。

旧 Python Terse 模板流水线只保留
`route_legacy_python_terse_generation(...)` 诊断入口，用于临时对比定位，不属于生产默认路由。

## 目录边界

```text
template_generation/
├── facade.py                 Compact/Terse 模板结果与 artifact 编排
├── artifact_builder.py       模板模块内部的 artifact 组装
├── binding_dependencies.py   仅供模板渲染使用的字段依赖补齐
├── legacy_python.py          旧 Python Terse 流水线诊断入口
├── model_client.py           第一层/第二层模型窄适配器
├── archive.py                A2UI 与 A2UI-Compact 双产物归档
├── engine/                   受限 DSL、模板匹配和确定性编译
├── resources/source/         Provider 清单、Schema、模板和主题资源
├── tests/                    模板能力独立测试
└── docs/                     本功能设计与接入文档
```

模块允许复用 dev 已有的 CardSpec/TaskSpec Builder、Compact Processor、Validator 和 ArtifactStore；
能力注册表、模型运行时和请求上下文由公开入口显式提供。模板模块自行组装完整 artifact，不得通过主服务对象
调用私有能力或反向调用原协议逻辑。

详细流程见 [architecture.md](architecture.md)，Provider 接入见
[provider-template-contract.md](provider-template-contract.md)。
