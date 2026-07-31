---
name: harmony-card-generation-online
description: "为小艺/HarmonyOS 创建或连续编辑桌面服务卡片，并在生成前判断卡片形态是否适配、候选能力是否满足核心需求以及数据权限是否通过。用户提出创建、生成、修改、优化、预览、添加桌面卡片、服务卡片、widget、小组件等需求，处于卡片创建/模板上下文，或带有 /harmony-card-generation 标记时使用；普通非卡片对话不使用。"
metadata:
  tools:
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "getWidgetCapabilityOverview"
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "getDataCapabilitySchemas"
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "RequestDataPermission"
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "generateWidgetCardCompactDsl"
---

# Harmony 卡片云侧编排

## 目标与边界

只执行编排：识别 create/edit、判断需求适配、选择候选、执行生成前能力与权限门禁、调用工具并组织用户回复。
不得自行生成、修改或校验卡片DSL、artifact 或其它产物；

## 执行入口

先读取 [`references/orchestration-workflow.md`](references/orchestration-workflow.md)，再按场景只加载必要资料：

- create、删除数据能力或修改数据参数：读取 [`references/candidate-planning.md`](references/candidate-planning.md) 和 [`references/tool-contracts.md`](references/tool-contracts.md)。
- 纯视觉、布局、文案或尺寸 edit：只读取 [`references/tool-contracts.md`](references/tool-contracts.md) 的 edit 契约。
- 需要追问、说明部分满足、结束并引导、处理权限或生成结果：读取 [`references/response-policy.md`](references/response-policy.md)。
- 仅在联调、排障或回归核对时读取 [`references/examples.md`](references/examples.md) 和 [`references/tools/`](references/tools/) 中的静态快照；快照不能覆盖当前运行时 schema。

## 不可绕过的门禁

1. **需求适配**：明确非卡片任务、长报告、完整页面或复杂表单不调用工具；卡片意图仍有歧义时只追问一个最小必要问题并等待回答。
2. **用户确认**：每次工具调用前，若仍缺少会改变核心意图、候选选择、目标卡片或业务必填参数的用户信息，先追问；设备能力、能力 ID、schema 等内部信息不向用户确认。
3. **运行时 schema**：每次调用前读取当前运行时工具 schema。只传其声明字段并满足必填、类型和嵌套结构；Skill 文案、示例、快照和内部类均不能授权额外字段。
4. **能力满足度**：数据候选只从本轮概述的 `dataCapabilities` 选择；`unavailableCapabilities` 不进入 schema 或候选。核心能力无法满足且静态/入口卡不能保持原意图时，生成前结束并引导。
5. **部分满足**：仅次要数据、动作或非核心素材不可用时，先说明缺失与保留内容，再自动继续，不等待确认；用户明确“必须包含，否则不要生成”时不得降级。
6. **最小尺寸**：用户未指定时从 `2x2` 开始，只有必须保留的核心内容无法成立时才建议 `2x4`；用户明确指定时优先尊重。
7. **权限一票否决**：每次生成前确定最终数据能力 ID 集合。非空时必须调用 `RequestDataPermission`；只有权限契约明确判定通过才能生成。任一权限为 `false`、存在非空未授权明细、结果缺失或非法时立即终止；集合变化后重新检查。空集合跳过权限工具。
8. **编辑来源**：edit 只使用目标卡片最近一次有效业务 payload 的真实 `artifactUrl`；无来源、运行时 schema 未声明 `sourceArtifactUrl` 或权限集合无法可靠恢复时停止编辑，不改走 create，不读取 artifact 猜测。
9. **编辑范围**：本期 edit 支持纯视觉/布局/文案/尺寸、删除数据能力和修改已有数据参数；新增数据能力、修改事件或素材候选时不调用编辑接口，引导用户重新创建。
10. **结果 URL**：业务 payload 只要返回合法真实 `artifactUrl`，就必须输出 `genWidgetResult`；`degraded` 也不能省略。没有 URL 时绝不输出或伪造标记；edit 的新 URL 必须不同于来源 URL。

## 工具调用

依赖 frontmatter 声明的三个微服务工具和一个端工具。统一使用：

```text
invoke(functionName:"<toolName>", arguments:{bundleName:"com.omega_w_0823.hmservice", ...},"skillName":"harmony-card-generation-online")
```

`skillName` 必须与 frontmatter `name` 完全一致。四个工具的调用顺序、字段结构、包装结果解析和 edit 继承语义只以 [`references/tool-contracts.md`](references/tool-contracts.md) 为准。

## 生成结果原子交付

`generateWidgetCardCompactDsl` 返回后，必须在结束本轮前连续完成以下步骤，不得只回复 `message`、先结束回复、等待用户确认或留到下一轮补发：

1. 按工具契约解析当前调用的业务 payload，并只从其中读取 `artifactUrl`；`streamInfo`、普通文本、历史回复、示例和模型猜测都不是产物 URL。
2. 在判断 `status` 和选择话术前，先锁存 `mustEmitGenWidgetResult = artifactUrl 合法真实`。edit 返回来源 URL 时按无有效新 URL 处理。
3. `status` 只决定自然语言，不能清除或覆盖 `mustEmitGenWidgetResult`。`success`、`degraded`、`unsupported`、`failed` 或其它可解析异常 payload 只要带有效 URL，都必须下发标记。
4. `mustEmitGenWidgetResult` 为 `true` 时，在同一条最终回复中输出且只输出一个以下代码块，将占位符替换为当前 payload 的原始 URL：

````text
```genWidgetResult
{
  "result": "{artifactUrl}"
}
```
````

5. 发送前执行硬检查：`合法 artifactUrl` 当且仅当回复中存在一个 `genWidgetResult` 代码块；块内必须是可解析 JSON，唯一字段 `result` 必须是字符串并与当前 payload 的 `artifactUrl` 完全一致。检查失败时先修正回复，不得发送半成品。

自然语言可以位于代码块之前，但不得把代码块改成普通链接、行内代码、无语言标签代码块或其它字段名；不得在代码块之后追加会干扰端侧识别的内容。

## 输出与安全

- 完整 `success` 可使用业务 `message`；其它状态使用 [`references/response-policy.md`](references/response-policy.md) 的受控话术。
- 生成前合法结束不伪造 `unsupported` payload，不输出 `genWidgetResult`。
- 任一必要工具不可用、调用失败、结果无法解析或字段非法时终止本轮，不模拟成功、不重试补偿、不生成替代产物。
- 用户可见回复不暴露能力 ID、schema、provider、TaskSpec、OBS、IDS、错误码、请求 ID、工具包络或内部草稿。
