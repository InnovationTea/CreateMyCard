# Style Runtime Index（运行时样式索引）

本文件定义样式规则如何从仓内规范映射到本 skill。
仅样式层生效；逻辑层（NDJSON、绑定、时序、交互协议）不在此文件定义。

## 1. 仓内规范文件（必须使用本仓库版本）

- `reference/design/design_token.md`：颜色/字号/间距/圆角等设计参数真理源（Card + UI）。
- `reference/design/harmony_ui_components_a2ui.md`：A2UI 可生成组件样式子集、组合与降级规则（Card + UI）。
- `reference/design/harmony_card_spec.md`：卡片结构、布局和卡片专属样式约束（Card only）。

## 2. 输入模式路由

| 输入类型 | 运行模式 | 规则优先级 |
|---|---|---|
| JSON | Card Mode | design_token -> card_spec -> ui_components_a2ui |
| Markdown / Query | UI Mode | design_token -> ui_components_a2ui（card_spec 仅参考） |

## 3. 运行时白名单与边界

- 仅输出 `extended-ui-schema.md` 已定义的 `Extended.*` 组件与 styles 字段。
- `harmony_ui_components_a2ui.md` 中非一等组件只允许 `composed` / `degradable` / `gap` 处理。
- 不得新增协议未定义字段，不得虚构一等组件名。

## 4. 冲突与待确认项处理

- 标注为“待 UX 确认”或存在冲突/留空值的规则，不进入运行时主依据。
- 待确认项由规范维护流程线下确认后再回填到运行时规则。

## 5. 生效原则

- 运行时只使用“无歧义子集”。
- 若请求字段未在运行时子集中定义：不臆造，按降级或既定稳定默认处理。
