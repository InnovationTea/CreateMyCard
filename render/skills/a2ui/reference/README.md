# Reference 索引（建议分类）

本目录用于承载 **A2UI 协议、Extended 组件体系、运行时能力、样式基线与可复用模板** 等参考文档。

目标：让 Agent/开发者在需要时能快速定位「该看哪份 reference」。

---

## 1) 协议与 Schema（强相关：格式正确性/可解析）

- `protocol/schema.md`：A2UI v0.9 协议结构（createSurface / updateComponents / updateDataModel / deleteSurface 等）
- `protocol/extended-output-format.md`：NDJSON 输出格式约束（每行一个 JSON、字符串转义等）
- `protocol/extended-ui-schema.md`：Extended.\* 组件与 Common Styles 字段全集

---

## 2) 设计基线与组件使用（强相关：Harmony 一致性/视觉品质）

- `design/style-runtime-index.md`：运行时样式索引（Card/UI 双模式、三份规范映射、白名单边界）
- `design/design_token.md`：鸿蒙设计参数真理源（颜色/字号/间距/圆角）
- `design/harmony_ui_components_a2ui.md`：A2UI 可生成组件样式子集（含组合与降级策略）
- `design/harmony_card_spec.md`：卡片结构、布局与卡片专属样式约束（Card Mode 强约束）
- `design/harmony-style.md`：Harmony 样式详规（token 语义、组件口径、降级策略）
- `design/quick-snippets.md`：可复制片段（按 Card/UI 模式组织）
- `design/interaction-design.md`：何时用 **TextInput / Toggle / Radio / Checkbox / CheckboxGroup / Select** 等**交互组件**替代表达型 `Extended.Text`；含 **六合一 + `submit_form` 主按钮** NDJSON；`examples/flows/recommendation-radio.md` Few-shot 可配合阅读

---

## 推荐阅读顺序（新同学/快速上手）

1. `protocol/extended-output-format.md`（先保证可解析与 NDJSON 纪律）
2. `protocol/schema.md`（再理解协议动作）
3. `protocol/extended-ui-schema.md`（最后查组件字段）
4. `design/style-runtime-index.md`
5. `design/harmony-style.md`
