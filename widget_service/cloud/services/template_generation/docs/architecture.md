# Compact/Terse 模板 source DSL 路由设计

## 设计目标

模板是 Compact 和 TerseDSL-Nested-2 create 场景的内部生成方式，不新增外部协议。
`_generate_widget_card_with_policy` 只负责向单次公共生成链注入模板 source generator。公共生成链负责
前置裁决、CardSpec、TaskSpec、原协议 Prompt 和模型客户端、Processor、校验、保存和响应组装。
模板模块不持有主服务对象，对外只返回当前 Processor 可直接消费的源 DSL 字符串。

## 公共入口契约

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

输入中的 TaskSpec、CardSpec 和有效数据绑定均由主生成链构造。输出是公共处理链可消费的源 DSL
字符串：Compact 和 Terse 模板路线统一为 Design Compact DSL，标准路由为三行 A2UI JSONL。
模板模块不得导入 `GenerateWidgetCardResponse`、ArtifactStore、Validator 或通用 CardSpec/TaskSpec Builder。

## 路由状态机

```text
generateWidgetCardCompactDsl
  ├─ edit → _generate_widget_card_with_policy 直接进入原 Compact 流程
  └─ create
       ├─ 公共生成链：能力前置裁决 → CardSpec → TaskSpec → 原协议 Prompt/Client
       ├─ generate_source_dsl → request_template_source_dsl
       │    ├─ 第一层 LLM：选择 Theme、业务模板候选和 Action
       │    ├─ 服务端完整覆盖校验
       │    ├─ 第二层 LLM：只选择受控 Layout、Template 和可选 PillAction
       │    ├─ 受信解析、参数校验与模板展开
       │    └─ A2UI 适配当前 Profile 后回转 Design Compact DSL
       ├─ 模板 source generator 异常 → 同一 generate_source_dsl 调用原 Compact 模型
       └─ 公共生成链：DesignCompactProcessor → Validator → RetryController
                            → ArtifactStore → ResponsePlanner → GenerateWidgetCardResponse
```

```text
generateWidgetCardTerseDslNested2
  ├─ edit → generate_widget_card_terse_dsl_nested2 入口返回 failed
  └─ create
       ├─ Design Compact 原始策略：能力前置裁决 → CardSpec → TaskSpec → Compact Prompt/Client
       ├─ generate_source_dsl → request_template_source_dsl → Design Compact DSL
       ├─ try_template=true、need_fallback=false → 模板异常直接返回失败
       └─ 公共生成链：DesignCompactProcessor → Validator → RetryController
                            → ArtifactStore → ResponsePlanner → GenerateWidgetCardResponse
```

## Compact 归档一致性

模板引擎先产生 A2UI，模板 source adapter 再执行以下闭环：

1. 适配当前 Form Profile 的 `catalogId`、root 尺寸、圆角和裁剪约束。
2. 确定性生成 A2UI-Compact Token。
3. 使用原 Compact Processor 将 Token 转回最终 A2UI。
4. 使用同一 Token 写入 `designcompactdsl`，保持后续 edit 转换一致。

源 DSL 转换位于 `template_generation/source_adapter.py`，最终转换、校验和归档仍由公共生成链
负责。Terse 模板路线当前不支持 edit；成功时与 Compact 模板路线一样把 Design Compact DSL 写入
`designcompactdsl`，不再经过 `TerseNested2Processor`。

## 失败与回退边界

| 阶段 | Compact | TerseDSL-Nested-2 |
|---|---|---|
| edit 请求 | 原 Compact 流程 | `failed` |
| 模板首层拒绝、模板生成或源格式转换异常 | 同次调用回退原 Compact 生成 | 直接 `failed` |
| 模板源 DSL 的 Processor/Validator 失败 | 公共 Compact repair | 公共 Compact repair |
| repair 最终失败 | `failed` | `failed` |
| ArtifactStore 失败 | 异常上抛 | 异常上抛 |

`generate_source_dsl` 在选择模板或原协议模型之前统一调用 `before_model_call`。Compact 模板尝试和
异常后的原模型回退共用同一次开始通知，不在 `_generate_widget_card_with_policy` 或模板模块中新增
去重状态；Terse 模板异常不再调用原模型。模板 source generator 一旦返回，后续质量失败不再重试模板。

## 模板资源边界

Provider 和 Layout 资源仍由模板 Registry 管理：

- 业务模板在 Provider 中声明 `businessId`、`capabilityId`、数据域和受控参数。
- Layout Provider 声明尺寸、子节点、Action 和 Lowering 约束。
- 中央 UX Registry 只保留跨 Provider 的 UX Token、场景、Theme 映射和尺寸预算。
- `config/template_controls.json` 在首层 Prompt 前过滤禁用 Provider 和模板，受信展开前再做确定性检查。

模板渲染需要的附加候选字段由 `binding_dependencies.py` 在 `request_template_source_dsl` 内部补齐，
只影响传给模板引擎的 bindings 副本。公共前置裁决、TaskSpec、CardSpec 以及原协议回退仍使用调用方
原始有效绑定，模板模块不另行组装或替换这些公共对象。
