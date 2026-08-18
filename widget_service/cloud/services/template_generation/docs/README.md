# 模板生成模块

本目录是 `generateWidgetCardCompactDsl` 和 `generateWidgetCardTerseDslNested2` 的独立模板能力边界。
模板判断、模板展开、Provider 资源、A2UI/设计 Token 双产物归档、测试和设计文档都位于
`cloud/services/template_generation/`，原始 dev 生成链不承载模板实现细节。

## 对外接口

外部只调用：

```python
await route_compact_generation(
    host,
    request,
    policy,
    before_model_call=before_model_call,
)

await route_terse_nested2_generation(
    host,
    request,
    policy,
    before_model_call=before_model_call,
)
```

返回规则：

- edit 请求不做模板判断，直接执行原始 Compact 流程。
- create 请求先由第一层 LLM 判断一个或多个模板能否覆盖完整需求。
- 第一层拒绝、输出非法、调用失败或确定性覆盖检查不通过时，执行原始 Compact 流程。
- 第一层确认模板可用后，不再回退原始流程；模板生成、转换或校验失败返回明确失败。
- 模板成功时直接保存包含 `genui` 和 `designcompactdsl` 的标准 artifact。
- Terse create 只有模板完整匹配并成功生成才返回成功；不匹配或生成失败均返回失败。
- Terse edit 直接返回失败，不进入模板生成，也不进入原始更新流程。

旧 Python Terse 模板流水线只保留
`route_legacy_python_terse_generation(...)` 诊断入口，用于临时对比定位，不属于生产默认路由。

## 目录边界

```text
template_generation/
├── facade.py                 Compact/Terse 默认路由与 artifact 编排
├── binding_dependencies.py   仅供模板渲染使用的字段依赖补齐
├── legacy_python.py          旧 Python Terse 流水线诊断入口
├── model_client.py           第一层/第二层模型窄适配器
├── archive.py                A2UI 与 A2UI-Compact 双产物归档
├── engine/                   受限 DSL、模板匹配和确定性编译
├── resources/source/         Provider 清单、Schema、模板和主题资源
├── tests/                    模板能力独立测试
└── docs/                     本功能设计与接入文档
```

模块允许复用 dev 已有的能力注册表、CardSpec/TaskSpec Builder、Compact Processor、Validator 和
ArtifactStore；不得在模板目录中复制这些通用服务。这样可以保证模板路由和原始路由遵循同一份能力裁决、
协议与 artifact 契约。

详细流程见 [architecture.md](architecture.md)，Provider 接入见
[provider-template-contract.md](provider-template-contract.md)。
