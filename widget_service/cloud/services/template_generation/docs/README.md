# Template Generation 文档中心

本目录维护 `template_generation` 模块的实现说明。模块为
`generateWidgetCardCompactDsl` 和 `generateWidgetCardTerseDslNested2` 的 create 请求提供受控
Template source DSL，但不负责能力裁决、CardSpec/TaskSpec 构造、最终校验、artifact 保存或业务响应。

> 本目录统一使用协议名 `Tersel`。`Tersel-Nest2`、`TerseDSL-Nested-2`、`Nested-2` 和 `Terse`
> 只作为兼容代码名或历史名称保留。

## 文档层级

| 文档 | 用途 | 是否权威契约 |
| --- | --- | --- |
| [云侧方案设计](../../../../../docs/云侧方案设计.md) | 系统边界、对外接口、协议、校验和降级规则 | 是，唯一权威来源 |
| [architecture.md](architecture.md) | 当前代码的路由、Template 生成流程和失败边界 | 否，实现说明 |
| [modules.md](modules.md) | 目录、类、函数和代码责任索引 | 否，实现说明 |
| [tersel-protocol.md](tersel-protocol.md) | Tersel 语法、DesignToken、内联样式和安全边界 | 否，模块内协议说明 |
| [compact-dsl-data-flow.md](compact-dsl-data-flow.md) | Compact 入口的数据流和回退策略 | 否，接口实现说明 |
| [tersel-data-flow.md](tersel-data-flow.md) | Tersel 入口的数据流和严格失败策略 | 否，接口实现说明 |
| [provider-template-contract.md](provider-template-contract.md) | Provider Bundle、CardTpl、Layout 与 Action 接入规则 | 否，模块内契约 |
| [provider-template-capability-checklist.md](provider-template-capability-checklist.md) | 业务模板、数据分层和运行状态清单 | 否，从 Provider 事实源派生 |
| [provider-template-preview-gallery.md](provider-template-preview-gallery.md) | 确定性 A2UI 预览数据集的生成与验证 | 否，开发辅助 |
| [migration-notes.md](migration-notes.md) | 历史合入边界和决策背景 | 否，仅供追溯 |

Provider 的 `first-layer.md` 和 `second-layer.md` 是模型输入资源，不是开发者总体设计文档；
它们应与对应 `provider.json` 和 `.cardtpl` 一起修改。

## 生产入口

模块对生产调用方只暴露一个源 DSL 生成入口：

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

入口返回当前公共 Processor 可直接消费的字符串。当前 Compact 与
Tersel 生产路线都使用 `DESIGN_COMPACT` Processor，因此模块最终返回 Design Compact DSL。
模块内部仍使用受限 Tersel 和 CardTpl 表达布局与模板，但这些不是对外产物。

## 边界速查

模块负责：

- 加载并校验 Template Controls、Provider Bundle、Theme、Layout 和 CardTpl。
- 从已裁决的 TaskSpec、CardSpec 和有效数据绑定中判断模板是否可完整覆盖需求。
- 让模型只做受控的字段标定、Theme/Action 选择、Layout/Template 组合和 Props 填充。
- 确定性执行语法校验、数据准入、布局约束、Action 绑定和 CardTpl 展开。
- 生成标准 A2UI，并适配为当前 Processor 的源 DSL。

模块不负责：

- 不查询 IDS，不执行设备能力或权限裁决。
- 不生成 CardSpec、TaskSpec、artifact 或 `GenerateWidgetCardResponse`。
- 不调用 `ArtifactValidator`、`ArtifactStore` 或 `ResponsePlanner`。
- 不持有 `WidgetGenerationService` 实例，不反向调用原协议生成链。
- 不决定 Compact 和 Tersel 入口的回退、edit 和业务响应策略。

## 开发入口

修改前建议按以下顺序定位：

1. 路由差异：阅读 [architecture.md](architecture.md) 和对应接口数据流。
2. 函数职责：阅读 [modules.md](modules.md)。
3. Provider 或 CardTpl：阅读 [provider-template-contract.md](provider-template-contract.md)。
4. 新增或修改资源：同时检查 `provider.json`、分层规则、`.cardtpl` 和能力清单。
5. 回归：运行模块测试和预览数据集校验，具体命令见预览文档。

## 目录概览

```text
template_generation/
├── facade.py                  生产窄入口
├── controls.py                模板细粒度开关
├── binding_dependencies.py    有效绑定隔离
├── model_client.py            共享模型运行时窄适配
├── source_adapter.py          A2UI 到公共 Processor 源格式的适配
├── legacy_python.py           旧路线诊断入口
├── engine/
│   ├── pipeline.py            模板生成主编排
│   ├── advanced/              数据轮廓、首层选择和二层 Prompt
│   └── cardplan/              Provider Registry、Search、CardTpl 编译与展开
├── resources/source/          受信 Provider、Theme、Prompt 和 CardTpl 资源
├── tests/                     模块回归测试
└── docs/                      实现文档
```
