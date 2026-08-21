# Compact/Terse 模板 A2UI 路由设计

## 设计目标

模板是 Compact 和 TerseDSL-Nested-2 create 场景的内部生成方式，不新增外部协议。
`_generate_widget_card_with_policy` 统一持有模板尝试与回退策略，公共生成链负责前置裁决、CardSpec、
TaskSpec、协议适配、校验、保存和响应组装。模板模块不持有主服务对象，对外只返回 A2UI 字符串。

## 公共入口契约

```python
await request_template_a2ui(
    task_spec,
    card_spec,
    effective_bindings,
    model_runtime=model_runtime,
    model_request_context=model_request_context,
)
```

输入中的 TaskSpec、CardSpec 和有效数据绑定均由主生成链构造。输出仅为三行 A2UI JSONL 字符串。
模板模块不得导入 `GenerateWidgetCardResponse`、ArtifactStore、Validator 或通用 CardSpec/TaskSpec Builder。

## 路由状态机

```text
generateWidgetCardCompactDsl
  ├─ edit → _generate_widget_card_with_policy 直接进入原 Compact 流程
  └─ create
       ├─ 公共生成链：能力前置裁决 → CardSpec → TaskSpec
       ├─ request_template_a2ui
       │    ├─ 第一层 LLM：选择 Theme、业务模板候选和 Action
       │    ├─ 服务端完整覆盖校验
       │    ├─ 第二层 LLM：只选择受控 Layout、Template 和可选 PillAction
       │    ├─ 受信解析、参数校验与模板展开
       │    └─ 返回三行 A2UI JSONL
       ├─ 公共生成链：Profile 适配 → A2UI-Compact 回转 → Validator
       │                    → ArtifactStore → ResponsePlanner → GenerateWidgetCardResponse
       └─ 模板或模板 A2UI 处理异常 → 原 Compact 流程
```

```text
generateWidgetCardTerseDslNested2
  ├─ edit → _generate_widget_card_with_policy 返回 failed
  └─ create
       ├─ 公共生成链：能力前置裁决 → CardSpec → TaskSpec
       ├─ request_template_a2ui → 三行 A2UI JSONL
       ├─ 公共生成链：Profile 适配 → Validator → ArtifactStore
       │                    → ResponsePlanner → GenerateWidgetCardResponse
       └─ 模板或模板 A2UI 处理异常 → failed，不进入旧 Terse 生成流程
```

## Compact 归档一致性

模板引擎先产生 A2UI，Compact 主生成链再执行以下闭环：

1. 适配当前 Form Profile 的 `catalogId`、root 尺寸、圆角和裁剪约束。
2. 确定性生成 A2UI-Compact Token。
3. 使用原 Compact Processor 将 Token 转回最终 A2UI。
4. 使用同一 Token 写入 `designcompactdsl`，保持后续 edit 转换一致。

该归档逻辑位于主生成服务一侧，不属于 `template_generation` 公共接口。Terse 模板路线当前不支持
edit，因此只保存最终 A2UI，不另行暴露模板内部源 Token。

## 失败与回退边界

| 阶段 | Compact | TerseDSL-Nested-2 |
|---|---|---|
| edit 请求 | 原 Compact 流程 | `failed` |
| 无真实模型运行时 | 原 Compact 流程 | `failed` |
| 第一层拒绝或确定性覆盖失败 | 原 Compact 流程 | `failed` |
| 第二层、模板编译或 A2UI 适配失败 | 原 Compact 流程 | `failed` |
| Validator 或保存失败 | 原 Compact 流程 | `failed` |

`before_model_call` 在 `_generate_widget_card_with_policy` 中包装为单次通知。模板尝试已下发开始事件时，
Compact 回退到原模型不会重复下发。

## 模板资源边界

Provider 和 Layout 资源仍由模板 Registry 管理：

- 业务模板在 Provider 中声明 `businessId`、`capabilityId`、数据域和受控参数。
- Layout Provider 声明尺寸、子节点、Action 和 Lowering 约束。
- 中央 UX Registry 只保留跨 Provider 的 UX Token、场景、Theme 映射和尺寸预算。
- `config/template_controls.json` 在首层 Prompt 前过滤禁用 Provider 和模板，受信展开前再做确定性检查。

模板渲染需要的附加候选字段由 `binding_dependencies.py` 在主生成服务准备模板尝试请求时补齐，
原协议回退请求不继承这些模板专用变更。
