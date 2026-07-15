# Harmony 卡片生成参考索引

此 skill 是云侧工具编排版，只负责候选选择、工具调用和用户回复组织。卡片产物必须由 `generateWidgetCard` 生成；任一工具不可用、调用失败或结果不完整时终止本轮生成。

本版本只实现云侧工具编排。旧版 `harmony-card-generation`、历史模板和离线资料不能作为生产候选或产物依据。

## 默认读取

- [`references/tool-contracts.md`](references/tool-contracts.md)：三个微服务工具的输入、包装输出解析和调用规则。
- [`references/candidate-planning.md`](references/candidate-planning.md)：如何从能力概述中筛选候选能力、构造候选 dataBindings、event candidates、asset ids、size、title 和 description。
- [`references/response-policy.md`](references/response-policy.md)：如何处理 `success`、`degraded`、`unsupported`、`failed`。
- [`references/tools/`](references/tools/)：三个工具的 JSON 声明。工具联调、schema 排查、更新 `metadata.tools` 或核对真实工具入参时读取。

## 样例

- [`references/examples.md`](references/examples.md)：10 条回归 query、工具调用样例、用户回复话术样例。

## 边界

旧 A2UI 协议、组件、布局、CardSpec、data capability 和 event capability 资料不放入本重构目录。不要读取旧资料来拼 DSL、生成最终 CardSpec 或校验 A2UI 产物；这些职责由微服务完成。

工具调试或接口联调时可以读取旧资料核对历史字段，但不得用其补足本轮候选计划或生成用户产物。生产编排只使用本轮工具返回的能力、事件、素材和 artifact URL。
