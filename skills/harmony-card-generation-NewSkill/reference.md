# Harmony 卡片生成参考索引

此 skill 是云侧工具编排版。默认只负责候选选择、工具调用和用户回复组织；当 `generateWidgetCard` 不可用、调用失败或生成结果不符合预期时，可进入主 Agent 兜底链路生成最终可交付结果。

若与旧版 `harmony-card-generation` 或历史模板冲突，以项目根目录 `AGENTS.md` 和 `docs/云侧方案设计.md` 中的云侧链路边界为准。

## 默认读取

- [`reference/tool-contracts.md`](reference/tool-contracts.md)：三个微服务工具的输入、输出和调用规则。
- [`reference/candidate-planning.md`](reference/candidate-planning.md)：如何从能力概述中筛选候选能力、构造候选 dataBindings、event candidates、asset ids 和 size。
- [`reference/response-policy.md`](reference/response-policy.md)：如何处理 `success`、`degraded`、`unsupported`、`failed`。
- [`reference/tools/`](reference/tools/)：三个工具的 JSON 声明。工具联调、schema 排查、更新 `metadata.tools` 或核对真实工具入参时读取。

## 样例

- [`reference/examples.md`](reference/examples.md)：10 条回归 query、工具调用样例、用户回复话术样例。

## 边界

旧 A2UI 协议、组件、布局、CardSpec、data capability 和 event capability 资料不放入本重构目录。本版默认不要读取旧资料来拼 DSL、生成最终 CardSpec 或校验 A2UI 产物；这些职责优先下沉到微服务。

只有在工具调试、接口联调或兜底生成时，才可读取旧资料核对能力 ID 或字段名。读取后不得伪造动态能力、事件目标、素材 ID 或 artifact URL。
