# Harmony 卡片生成参考索引

此 skill 是云侧工具编排版。主 Agent 不直接生成 DSL/CardSpec，只负责候选选择、工具调用和用户回复组织。

若与旧版 `harmony-card-generation` 或历史模板冲突，以项目根目录 `AGENTS.md` 和 `docs/云侧方案设计.md` 中的云侧链路边界为准。

## 默认读取

- [`reference/tool-contracts.md`](reference/tool-contracts.md)：三个微服务工具的输入、输出和调用规则。
- [`reference/candidate-planning.md`](reference/candidate-planning.md)：如何从能力概述中筛选候选能力、构造候选 dataBindings、event candidates、asset ids 和 size。
- [`reference/response-policy.md`](reference/response-policy.md)：如何处理 `success`、`degraded`、`unsupported`、`failed`。

## 样例

- [`reference/examples.md`](reference/examples.md)：10 条回归 query、主 Agent 工具调用样例、用户回复话术样例。

## 边界

旧 A2UI 协议、组件、布局、CardSpec、data capability 和 event capability 资料不放入本重构目录。本版默认不要读取旧资料来拼 DSL、生成最终 CardSpec 或校验 A2UI 产物；这些职责已下沉到微服务。

只有在工具调试或接口联调时，才可读取旧资料核对能力 ID 或字段名；读取后仍只能产出候选计划，不直接产出最终 DSL/CardSpec。
