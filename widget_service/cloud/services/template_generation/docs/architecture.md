# Compact/Terse 模板路由与双产物设计

## 设计目标

模板是 Compact 和 TerseDSL-Nested-2 create 场景的内部生成方式，不新增外部协议。原始入口构造既有
`GenerationRoutePolicy`，显式提供模板所需依赖并接收模板生成结果。模板模块不持有主服务对象，也不具备
调用原协议生成链的能力；两种协议的回退都由公开入口负责。

## 路由状态机

```text
generateWidgetCardCompactDsl
  ├─ edit → 原始 Compact 流程
  └─ create
       ├─ generate_template_artifact
       │    ├─ 准备 dev 能力裁决、CardSpec、TaskSpec
       │    ├─ 第一层 LLM：从候选字段中提取 query 必显字段，选择 Theme 和业务模板
       │    ├─ 服务端完整覆盖校验
       │    │    ├─ 必显字段不属于候选或模板未消费任一必显字段 → 抛出回退信号
       │    │    └─ 全部覆盖 → 锁定模板路由
       │    ├─ 第二层 LLM：只生成受限布局和模板调用
       │    ├─ 服务端解析、参数校验、模板展开
       │    ├─ 内部 A2UI 适配当前 dev Form profile
       │    ├─ A2UI → A2UI-Compact
       │    ├─ dev Compact Processor → 最终 A2UI
       │    ├─ dev ArtifactValidator
       │    └─ ArtifactStore 保存 genui + designcompactdsl
       └─ 回退信号 → 原始 Compact 流程
```

```text
generateWidgetCardTerseDslNested2
  ├─ edit → 原始 TerseDSL-Nested-2 流程
  └─ create
       ├─ generate_template_artifact
       │    ├─ 第一层 LLM 提取 query 必显字段并执行服务端完整覆盖校验
       │    │    └─ 未匹配、字段未完整覆盖或模型不可用 → 抛出回退信号
       │    ├─ 第二层 LLM、参数校验和模板展开
       │    │    └─ 任一失败 → 抛出回退信号
       │    ├─ 展开后的 TerseDSL-Nested-2 → 模块内隔离转换器 → 最终 A2UI
       │    ├─ dev ArtifactValidator
       │    └─ ArtifactStore 保存 genui + 展开后的 TerseDSL-Nested-2
       └─ 回退信号 → 原始 TerseDSL-Nested-2 流程
```

## 为什么先归档 Compact 再确定最终 A2UI

模板编译器先产生内部 A2UI，但 artifact 中的 A2UI-Compact 会在后续 edit 中由原始 dev Processor 读取。
如果首次展示直接保存模板编译器输出，后续 Processor 的规范化可能造成视觉或逻辑漂移。

因此本模块执行以下闭环：

1. 模板内部 A2UI 仅作为中间结果。
2. 适配当前 dev 的 `catalogId`、root 尺寸、圆角和裁剪约束。
3. 确定性生成 A2UI-Compact。
4. 使用原始 dev Compact Processor 将该 Token 转回标准 A2UI。
5. 将回转结果作为首次展示的最终 A2UI，并将同一个 Token 写入 `designcompactdsl`。

这样首次展示和二次更新共享同一条 Compact 转换链。

## 失败与回退边界

| 阶段 | 行为 | 原因 |
|---|---|---|
| edit 请求 | 公开入口执行原协议流程 | 二次更新不重新选择模板 |
| 无真实模型运行时 | 公开入口执行原协议流程 | 保持 dev mock 和既有测试行为 |
| 第一层拒绝或异常 | 公开入口执行原协议流程 | 模板无法证明完整表达时保留原能力 |
| 确定性覆盖失败 | 公开入口执行原协议流程 | 任一用户选定字段无法由模板表达 |
| 第二层或模板编译失败 | 公开入口执行原协议流程 | 模板异常不阻断既有协议能力 |
| 归档、Validator 或保存失败 | 公开入口执行原协议流程 | 不保存半成品，改走原协议重新生成 |

`candidateOutputFields` 是可用候选集合，不是强制展示集合。第一层只能从候选集合中输出 query 实际要求的
必显字段；服务端随后证明这些字段被所选模板直接绑定或作为派生参数来源消费。模板可以为了保持原始视觉
额外展示其必需事实，但不得遗漏 query 必显事实。

`before_model_call` 由公开入口包装为单次通知。第一层已经触发通知时，即使回退原始模型，也不会重复下发
开始事件。旧 Python 模板流水线仅通过 `legacy_python.route_legacy_python_terse_generation(...)` 作为问题
定位入口保留；生产默认入口不引用该函数。

## 对原始 dev 的修改边界

`widget_generation_service.py` 在 Compact、Terse 两个公开入口统一持有模板尝试和原协议回退；模板模块只返回
结果或回退信号。共享 artifact 组装位于独立 Builder，避免模板模块依赖主服务私有方法。

模板渲染需要的附加候选字段由 `binding_dependencies.py` 在模板路由内补齐，不修改通用能力模型、能力注册表
或 `DeviceCapabilityResolver`。
