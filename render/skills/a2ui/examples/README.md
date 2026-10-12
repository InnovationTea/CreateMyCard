# Examples index

本目录的示例用于让 Agent 在不同 **Page Type / 运行模式** 下快速类比出稳定的 UI 形状。**样式取值**以 `reference/design/harmony-design-token.md` 与 `harmony-ui-components-a2ui.md` 的语义 token 展开为准；示例中的 hex 为 Light 模式下 token 展开示例，非任意选色。

## Mode A — Render / Present（已有内容 → UI）

### Form / Flow（表单/流程）

- `flows/form.md`：基础表单与按钮层级
- `flows/recommendation-radio.md`：小结式 **「我的推荐」** 互斥多选一 → `Extended.Radio` + 可选小标题 `Extended.Text`（Few-shot，避免长文本墙）
- `flows/list.md`：A 类列表（单外框 + 行列分组；可选轻边界增强区分）
- `flows/modal.md`：确认/条件渲染

## Mode A — Markdown input → UI

- `inputs/markdown-input/article-landing.md`：输入 Markdown 文本 → 输出精致信息页 NDJSON

## Mode A — JSON input → UI

- `inputs/json-input/product-compact-card.md`：商品 JSON → 每个绑定字段在 **`updateComponents`（`{"path":"…"}`）** 之后按 [`SKILL.md`](../SKILL.md) §0 完成 **`updateDataModel` tail**（单 surface 通常为紧邻下一行；多字段表单亦可用 **共享前缀** 一条 `updateDataModel` 覆盖多个 `text` path，见 §0）
- **勿**在 **尚未** 用 `updateComponents` **首次引入** 对应 `path` 之前，就为该 surface 单独堆 **`updateDataModel`**
- 协议形状见 `reference/protocol/schema.md` § **updateDataModel Schema**
