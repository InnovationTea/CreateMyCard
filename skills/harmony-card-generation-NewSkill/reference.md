# Harmony 卡片生成参考索引

此 skill 是云侧工具编排版。主 Agent 不直接生成 DSL/CardSpec，只负责候选选择、工具调用和用户回复组织。

## 默认读取

- [`reference/tool-contracts.md`](reference/tool-contracts.md)：三个微服务工具的输入、输出和调用规则。
- [`reference/candidate-planning.md`](reference/candidate-planning.md)：如何从能力概述中筛选候选能力、构造候选 dataBindings、slots 和 size。
- [`reference/response-policy.md`](reference/response-policy.md)：如何处理 `success`、`degraded`、`unsupported`、`failed`。

## 样例

- [`reference/examples.md`](reference/examples.md)：10 条回归 query、主 Agent 工具调用样例、用户回复话术样例。

## 边界

旧 A2UI 协议、组件、布局、CardSpec、data capability 和 event capability 资料不放入本重构目录。本版默认不要读取旧资料来拼 DSL、生成最终 CardSpec 或校验 A2UI 产物；这些职责已下沉到微服务。
