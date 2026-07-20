# Harmony 卡片生成参考索引

此 skill 是云侧工具编排版，只负责 create/edit 模式判断、候选选择、来源 URL 传递、工具调用和用户回复组织。卡片产物必须由 `generateWidgetCard` 生成；任一必要工具不可用、调用失败或结果不完整时终止本轮生成或编辑。

本版本只实现云侧工具编排。旧版 `harmony-card-generation`、历史模板和离线资料不能作为生产候选或产物依据。

## 按场景读取

- 所有请求先读取 [`references/orchestration-workflow.md`](references/orchestration-workflow.md)，按职责边界和完整十步流程推进。
- create、删除数据能力或修改数据参数：继续读取 [`references/candidate-planning.md`](references/candidate-planning.md) 和 [`references/tool-contracts.md`](references/tool-contracts.md)。
- 纯视觉、布局、文案或尺寸 edit：只继续读取 [`references/tool-contracts.md`](references/tool-contracts.md) 的 edit 契约。
- 工具调用结束后读取 [`references/response-policy.md`](references/response-policy.md)，映射完整成功及三类固定的非完整满足或异常回复。
- 工具联调、schema 排查或更新 `metadata.tools` 时按需读取 [`references/tools/`](references/tools/)；快照不能覆盖当前运行时 `tools` schema。

## 样例

- [`references/examples.md`](references/examples.md)：首次生成和连续编辑的回归 query、工具调用及用户回复样例。

## 边界

旧 A2UI 协议、组件、布局、CardSpec、data capability 和 event capability 资料不放入本重构目录。不要读取旧资料来拼 DSL、生成最终 CardSpec 或校验 A2UI 产物；这些职责由微服务完成。

工具调试或接口联调时可以读取旧资料核对历史字段，但不得用其补足本轮候选计划或生成用户产物。生产编排只使用本轮工具返回的能力、事件、素材和 artifact URL。
