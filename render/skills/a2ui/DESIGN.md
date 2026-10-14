# 鸿蒙风格 DESIGN.md（A2UI / Extended DSL）

本文件是 skill 的样式总纲，仅定义「如何读规范」与「样式决策边界」。

## 1. 样式输入模式路由

### 1.1 Card Mode（仅 JSON 输入）

当输入为结构化 JSON 且目标是卡片渲染：

1. `reference/design/design_token.md`（鸿蒙设计参数真理源）
2. `reference/design/harmony_card_spec.md`（仅卡片布局与样式强约束）
3. `reference/design/harmony_ui_components_a2ui.md`（A2UI 可生成组件样式子集）

### 1.2 UI Mode（Markdown / Query 输入）

当输入为 Markdown 或问答 query 且目标是通用 UI：

1. `reference/design/design_token.md`
2. `reference/design/harmony_ui_components_a2ui.md`
3. `reference/design/harmony_card_spec.md` 仅可借鉴，不强制

> 关键边界：`card_spec` 只对 Card Mode 强约束；UI Mode 不强制卡片结构。

## 2. 样式规则优先级（仅样式层）

- 以语义 token 为主，不以旧 hex 常量为主。
- 若本地样式文档与三份规范冲突，以三份规范为准。
- 若出现待确认/冲突项，不进入运行时主规则，按已定稿稳定默认或降级策略执行。

## 3. 本 skill 的不变边界（禁止改动）

以下属于逻辑层，不在本次样式升级范围：

- NDJSON 输出规则与流式顺序
- `updateComponents.components` 单组件粒度约束
- `path` 绑定与 `updateDataModel` 尾随约束
- 结构化 JSON 保真、防幻觉、URL 合法性校验
- 交互协议与上送机制（`action.*` / `submit_form`）

## 4. 样式表达原则

- 使用 `Extended.*` + 协议已定义的 `styles` 字段。
- 优先写语义含义，避免传播过期硬编码值。
- 保持 4vp 网格密度：默认使用 8/12，避免在同一卡片叠加大间距。
- 对于列表/表格/媒体行等高风险布局，沿用已验证的稳定布局模式（两层 Row、显式列宽等）。

## 5. 组件样式来源

- 组件样式矩阵、可变/不可变规则：`reference/design/harmony-style.md`
- 可复制 NDJSON 片段：`reference/design/quick-snippets.md`
- 交互策略：见 `reference/design/interaction-design.md`（本文件不展开）

## 6. 运行时禁止项

- 禁止为补齐视觉效果新增协议未定义字段。
- 禁止把 `待UX确认` 文案直接作为生成依据输出。
- 禁止在 UI Mode 下强行套用 Card Mode 的结构约束。
