# Compact/Terse 模板路由与双产物设计

## 设计目标

模板是 Compact 和 TerseDSL-Nested-2 create 场景的内部生成方式，不新增外部协议。原始入口构造既有
`GenerationRoutePolicy`，显式提供模板所需依赖并接收模板生成结果。模板模块不持有主服务对象，也不具备
调用原协议生成链的能力。Compact 的回退由公开入口负责；Terse 生产入口不允许回退。

## 路由状态机

```text
generateWidgetCardCompactDsl
  ├─ edit → 模板接口抛出异常 → 原始 Compact 流程
  └─ create
       ├─ generate_template_artifact
       │    ├─ 准备 dev 能力裁决、CardSpec、TaskSpec
       │    ├─ 第一层 LLM：从 TaskSpec 全量字段中判断 query 必显字段，只输出 theme/component/action
       │    ├─ 服务端完整覆盖校验
       │    │    ├─ 显式字段未完整覆盖、模板 requiredData 不完整或 dataDomain 不一致 → 抛出异常
       │    │    └─ 全部覆盖 → 锁定模板路由
       │    ├─ 第二层 LLM：只生成 Layout Template、业务 Template 和可选 PillAction
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
  ├─ edit → failed
  └─ create
       ├─ generate_template_artifact
       │    ├─ 第一层 LLM 只输出 theme/component/action，并执行服务端完整覆盖校验
       │    │    └─ 未匹配、字段未完整覆盖或模型不可用 → 抛出异常
       │    ├─ 第二层 LLM、参数校验和模板展开
       │    │    └─ 任一失败 → 抛出异常
       │    ├─ 展开后的 TerseDSL-Nested-2 → 模块内隔离转换器 → 最终 A2UI
       │    ├─ dev ArtifactValidator
       │    └─ ArtifactStore 保存 genui + 展开后的 TerseDSL-Nested-2
       └─ 任一异常 → failed（禁止回退旧 TerseDSL-Nested-2 流程）
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

| 阶段 | Compact | TerseDSL-Nested-2 |
|---|---|---|
| edit 请求 | 执行原 Compact 流程 | 返回 `failed` |
| 无真实模型运行时 | 执行原 Compact 流程 | 返回 `failed` |
| 第一层拒绝或确定性覆盖失败 | 执行原 Compact 流程 | 返回 `failed` |
| 第二层、模板编译、归档、Validator 或保存失败 | 执行原 Compact 流程 | 返回 `failed` |

`candidateOutputFields` 只负责形成 TaskSpec 的候选数据投影，不等于本轮全部必须显示字段。第一层结合
`userQuery` 与 TaskSpec 中的全量字段说明，在模型内部选出必须显示字段，再用 Provider 首层 MD 中的
“高级组件 → TaskSpec 绝对路径”映射选择能够完整覆盖这些字段的组件。任一显式字段无法承载即失败；
显式字段满足后，还必须检查模板 `requiredData` 在 TaskSpec 中全部存在。中间字段集合不回传，服务端继续
确定性复核所选组件存在可从本轮 TaskSpec/CardSpec 展开的 Provider Template。

第一层输出严格限制为：

```json
{
  "theme": "theme.id",
  "componentCandidates": [
    {
      "componentId": "ComponentId",
      "availableTemplateIds": ["BusinessTemplate@1"]
    }
  ],
  "action": "event.id"
}
```

不匹配时保留最匹配的候选 Theme，并固定输出
`{"theme":"theme.id","componentCandidates":[],"action":null}`。空 `componentCandidates` 是模板失败标志；
`availableTemplateIds` 是交给第二层的非空业务模板候选集，必须属于同一 `componentId` 且在当前
TaskSpec/CardSpec 下可展开。`action` 是批准的事件 ID，不是
数据项；SystemPrompt 只保留这一通用语义和输出约束。Provider 首层 MD 描述“高级组件 → TaskSpec 数据
路径”，Theme 首层 MD 描述主题适用场景；两类文档都只按本轮候选动态加载。第一层根据用户动作意图
从 TaskSpec 事件候选中输出对应 `eventId`，不判断 Action 属于哪个组件；没有动作时输出 `null`。
Action 不参与数据字段覆盖。首层 LLM 与后续 Search 都必须生成同一 `TemplateRouteDecision`，并共用
同一个确定性路由门禁，不得各自实现 Provider、事件或模板可用性校验。

第二层从所选 Provider 的二层 MD 读取规则，只能在首层的 `availableTemplateIds` 中选择最终业务模板，
并生成 props、Layout 与 Action。业务模板 ID 已表达 UI 形态，
不再输出 Variant；组件骨架也通过 Layout Provider 的 `Template("...Layout@1", {}, ...children)` 表达。
选中的 `eventId` 与业务组件解耦，统一生成布局模板末尾唯一的 `PillAction`。Python 只保留候选过滤、可信事实投影、事件 ID 校验、模板签名
与编译校验，不再把全部领域规则拼入 SystemPrompt。

旧 Python 模板流水线仅通过 `legacy_python.route_legacy_python_terse_generation(...)` 作为问题定位入口保留；
生产默认入口不引用该函数。

## 对原始 dev 的修改边界

`widget_generation_service.py` 只新增一个模板接口 import；Compact、Terse 两个公开入口均调用
`generate_template_artifact`。两者只在捕获异常后的接口策略不同：Compact 继续调用原协议流程，Terse 直接
返回失败。edit 判断由公共模板接口完成并以异常表达。模板 artifact 在隔离模块内部组装，不修改主服务原有
`_build_artifact`。

模板渲染需要的附加候选字段由 `binding_dependencies.py` 在模板路由内补齐，不修改通用能力模型、能力注册表
或 `DeviceCapabilityResolver`。
