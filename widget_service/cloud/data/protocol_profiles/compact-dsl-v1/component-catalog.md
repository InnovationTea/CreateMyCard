# Compact DSL 组件目录

## 支持范围

- 允许组件：`Row`、`Column`、`List`、`Stack`、`Grid`、`Text`、`Image`、`Divider`、`Progress`、`Button`、`TextInput`、`Radio`、`Toggle`、`Checkbox`、`Select`、`Web`。
- 核心展示组件：`Row`、`Column`、`List`、`Stack`、`Text`、`Image`、`Divider`、`Progress`、`Button`。
- 明确交互场景才使用：`TextInput`、`Radio`、`Toggle`、`Checkbox`、`Select`。
- 明确宫格或网页嵌入场景才使用：`Grid`、`Web`。

## 必需属性

| Type | 必需 props |
| --- | --- |
| Row / Column / List | `space` |
| Stack / Grid / Divider | 无 |
| Text | `content` |
| Image | `src` |
| Progress | `value`、`total` |
| Button | `label`、`enabled`、`action` |
| TextInput | `text`、`placeholder`、`enabled`、`maxLength`、`type` |
| Radio | `value`、`checked`、`group`、`indicatorType` |
| Toggle | `label`、`isOn`、`enabled` |
| Checkbox | `label`、`group`、`select` |
| Select | `options`、`selected`、`value` |
| Web | `url` |

`Text.content`、`Image.src`、`Button.label` 等字符串属性可直接写字符串，也可使用 path 绑定。`TextInput.text` 必须使用 path 绑定。
