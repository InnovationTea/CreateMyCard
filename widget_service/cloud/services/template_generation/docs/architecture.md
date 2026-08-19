# Compact/Terse 模板路由与双产物设计

## 设计目标

模板是 Compact 和 TerseDSL-Nested-2 create 场景的内部生成方式，不新增外部协议。原始入口构造既有
`GenerationRoutePolicy`，显式提供模板所需依赖并接收模板生成结果。模板模块不持有主服务对象，也不具备
调用原协议生成链的能力；两种协议的回退都由公开入口负责。

## 路由状态机

```text
generateWidgetCardCompactDsl
  ├─ edit → 模板接口抛出异常 → 原始 Compact 流程
  └─ create
       ├─ generate_template_artifact
       │    ├─ 准备 dev 能力裁决、CardSpec、TaskSpec
       │    ├─ 第一层 LLM：从 TaskSpec 全量字段中判断 query 必显字段，只输出 theme/component/action
       │    ├─ 服务端完整覆盖校验
       │    │    ├─ 所选组件无可展开 Provider Variant 或缺少可信字段 → 抛出异常
       │    │    └─ 全部覆盖 → 锁定模板路由
       │    ├─ 第二层 LLM：只生成受限布局和模板调用
       │    ├─ 服务端解析、参数校验、模板展开
       │    ├─ 内部 A2UI 适配当前 dev Form profile
       │    ├─ A2UI → A2UI-Compact
       │    ├─ dev Compact Processor → 最终 A2UI
       │    ├─ dev ArtifactValidator
       │    └─ ArtifactStore 保存 genui + designcompactdsl
       └─ 任一异常 → 原始 Compact 流程
```

```text
generateWidgetCardTerseDslNested2
  ├─ edit → 模板接口抛出异常 → 原始 TerseDSL-Nested-2 流程
  └─ create
       ├─ generate_template_artifact
       │    ├─ 第一层 LLM 只输出 theme/component/action，并执行服务端完整覆盖校验
       │    │    └─ 未匹配、字段未完整覆盖或模型不可用 → 抛出异常
       │    ├─ 第二层 LLM、参数校验和模板展开
       │    │    └─ 任一失败 → 抛出异常
       │    ├─ 展开后的 TerseDSL-Nested-2 → 模块内隔离转换器 → 最终 A2UI
       │    ├─ dev ArtifactValidator
       │    └─ ArtifactStore 保存 genui + 展开后的 TerseDSL-Nested-2
       └─ 任一异常 → 原始 TerseDSL-Nested-2 流程
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

`candidateOutputFields` 只负责形成 TaskSpec 的候选数据投影，不等于本轮全部必须显示字段。第一层结合
`userQuery` 与 TaskSpec 中的全量字段说明，在模型内部选出必须显示字段，再用 Provider 首层 MD 中的
“高级组件 → TaskSpec 绝对路径”映射选择能够完整覆盖这些字段的组件。中间字段集合不回传，服务端继续
确定性复核所选组件存在可从本轮 TaskSpec/CardSpec 展开的 Provider Variant。

第一层输出严格限制为：

```json
{"theme":"theme.id","component":["ComponentId"],"action":"event.id"}
```

不匹配时固定输出 `{"theme":null,"component":[],"action":null}`。`action` 是批准的事件 ID，不是
数据项；SystemPrompt 只保留这一通用语义和输出约束。Provider 首层 MD 描述“高级组件 → TaskSpec 数据
路径”，Theme 首层 MD 描述主题适用场景；两类文档都只按本轮候选动态加载。第一层根据用户动作意图
从 TaskSpec 事件候选中输出对应 `eventId`，不判断 Action 属于哪个组件；没有动作时输出 `null`。
Action 不参与数据字段覆盖。

第二层从所选 Provider 的二层 MD 读取 Variant、参数和素材使用规则。选中的 `eventId` 与业务组件解耦，
统一生成布局根末尾唯一的 `PillAction`。Python 只保留候选过滤、可信事实投影、事件 ID 校验、模板签名
与编译校验，不再把全部领域规则拼入 SystemPrompt。

旧 Python 模板流水线仅通过 `legacy_python.route_legacy_python_terse_generation(...)` 作为问题定位入口保留；
生产默认入口不引用该函数。

## 对原始 dev 的修改边界

`widget_generation_service.py` 只新增模板接口 import，并在 Compact、Terse 两个公开入口各增加一段简单的
`try/except`：尝试模板，任一异常后继续调用原协议流程。edit 判断由模板接口内部完成。模板 artifact 在隔离
模块内部组装，不修改主服务原有 `_build_artifact`。

模板渲染需要的附加候选字段由 `binding_dependencies.py` 在模板路由内补齐，不修改通用能力模型、能力注册表
或 `DeviceCapabilityResolver`。
