---
name: harmony-card-generation-cloud-orchestration
description: "编排云侧微服务生成 HarmonyOS A2UI Form 服务卡片。用于用户用自然语言请求创建、生成、预览或添加桌面 widget/服务卡片时，主 Agent 识别场景、获取能力概述、筛选候选数据/事件/素材能力、构造候选 dataBindings/slots/size，调用 getWidgetCapabilityOverview、getDataCapabilitySchemas、generateWidgetCard，并根据 success/degraded/unsupported/failed 返回 genWidgetResult 链接或可理解说明；本 skill 不直接输出 genui/cardspec，不直接生成最终 DSL/CardSpec。"
---

# Harmony 卡片生成（云侧工具编排版）

## 职责

本 skill 只负责主 Agent 侧编排：

- 识别用户是否在请求创建 HarmonyOS 桌面服务卡片。
- 调用微服务工具获取能力概述。
- 根据用户 query 选择候选数据能力、事件能力和素材。
- 按需加载选中数据能力 schema。
- 构造 `candidateDataBindings`、`candidateEventCapabilityIds`、`candidateAssetIds`、`slots` 和 `size`。
- 调用 `generateWidgetCard` 生成卡片 artifact。
- 根据微服务返回状态组织用户回复。

## 边界

- 不直接输出 `genui` 或 `cardspec` 代码块。
- 不直接生成最终 DSL、最终 CardSpec、A2UI prompt 或校验修复结果。
- 不维护完整 A2UI 协议、组件白名单、美观规则、素材合法性或版本兼容矩阵。
- 不提前承诺设备一定支持天气、日历、应用、跳转或任一动态能力。
- 不编造能力 ID、事件目标、素材 ID、OBS 链接或 `genWidgetResult`。
- 不把点击事件写入 CardSpec；点击候选只作为 `candidateEventCapabilityIds` 传给微服务。

微服务负责真实设备能力过滤、最终 CardSpec、A2UI DSL 生成、校验、降级、失败重试、OBS 上传和最终用户话术。

## 工作流

1. 判断用户 query 是否是创建卡片、生成 widget、生成服务卡片、添加桌面卡片、卡片预览等场景。不是卡片创建场景时，简短说明本 skill 只处理卡片生成。
2. 不要说“可以生成某动态卡片”。先回复或内部执行“我先检查当前设备支持情况，然后为你生成可用的卡片。”这类中性承接。
3. 调用 `getWidgetCapabilityOverview` 获取数据能力、事件能力和素材概述。工具层通常自动注入 ROM/App/device/uid；只有工具 schema 要求时才显式传 `locale`、`appVersion`、`romVersion`。
4. 按 [`reference/candidate-planning.md`](reference/candidate-planning.md) 从概述中筛选候选能力：
   - 数据能力最多优先选 2 个核心候选。
   - 事件能力最多优先选 2 个主动作候选。
   - 素材候选只选和场景强相关的少量 ID。
5. 如果选中了数据能力，调用 `getDataCapabilitySchemas` 渐进加载这些数据能力的完整 schema。
6. 基于 schema 构造候选计划：
   - `size`: `"2x2"` 或 `"2x4"`。
   - `candidateDataBindings`: 候选数据能力调用，不是最终 CardSpec。
   - `candidateEventCapabilityIds`: 来自 overview 的事件能力 ID。
   - `candidateAssetIds`: 来自 overview 的素材 ID。
   - `slots`: 从用户 query 提取的地点、时间范围、应用名、包名、目标动作等语义槽位。
   - `options.allowDegradation`: 默认 `true`。
   - `options.returnMode`: `"obs_url"`。
7. 调用 `generateWidgetCard`。不要自行补做微服务负责的过滤、协议 profile、校验、重试或上传。
8. 按 [`reference/response-policy.md`](reference/response-policy.md) 回复：
   - `success` / `degraded`: 输出微服务 `userMessage`，并输出 `genWidgetResult` 标记。
   - `unsupported` / `failed`: 不输出 `genWidgetResult`，只输出用户可理解说明和可尝试的替代方向。

## 输出

成功或降级成功时，最终回复必须包含微服务返回的 artifact URL 标记：

````text
```genWidgetResult:"https://obs.example/widget/request-id.json"```
````

规则：

- 只使用 `generateWidgetCard` 返回的真实 `artifactUrl`。
- `degraded` 时保留微服务给出的降级原因，轻量润色即可。
- `unsupported` 或 `failed` 时不要输出标记。
- 不输出 `genui`、`cardspec`、A2UI JSONL、CardSpec JSON、校验日志或内部工具草稿。

## 工具

本 skill 依赖三个微服务工具，契约见 [`reference/tool-contracts.md`](reference/tool-contracts.md)：

- `getWidgetCapabilityOverview`
- `getDataCapabilitySchemas`
- `generateWidgetCard`

如果工具没有以精确名称暴露，先在当前工具/MCP/插件列表中查找语义等价工具；仍不可用时，不要模拟工具结果，直接说明暂时无法完成云侧卡片生成，并提示需要接入对应微服务工具。

## 参考

- 参考索引：[`reference.md`](reference.md)
- 微服务工具契约：[`reference/tool-contracts.md`](reference/tool-contracts.md)
- 候选能力和 dataBindings 规划：[`reference/candidate-planning.md`](reference/candidate-planning.md)
- 回复策略：[`reference/response-policy.md`](reference/response-policy.md)
- 测试、工具调用和话术样例：[`reference/examples.md`](reference/examples.md)
