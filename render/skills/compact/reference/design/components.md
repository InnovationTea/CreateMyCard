# Compact Components（极简 GenUI）

本 skill 使用与 schema 一致的组件名：**`Card`**, **`Row`**, **`Column`**, **`Text`**, **`Button`**, **`Input`**, **`Image`**, 以及 **`Radio`**, **`Select`**, **`Checkbox`**（表单）。在 **`updateComponent`** 行里，第三段为 **`<Type>`**，第四段为 **`{ ...props }`**。

## Authoritative reference

- **Schema**: [`../protocol/extended-ui-schema.md`](../protocol/extended-ui-schema.md)
- **Harmony intent**: [`harmony-style.md`](harmony-style.md)
- **Line kinds**: [`../protocol/extended-output-format.md`](../protocol/extended-output-format.md), [`../protocol/schema.md`](../protocol/schema.md)

## Component index

### Layout

- **`Column`**: vertical stack; **`space`** between children; align with `alignItems` / `justifyContent`.
- **`Row`**: horizontal row; use only with **≥ 2** siblings on one line; pair with `justifyContent` (e.g. `"spaceBetween"`) for KPI rows.
- **`Card`**: framed section; `title` / `description` for section chrome; `gap` / `padding` / `radius` / `fill`.

### Text & media

- **`Text`**: titles, body, labels, chips (border/padding on **Text**), link-styled actions (`fontColor` + `decoration` + optional `openUrl`).
- **`Image`**: `src` for thumbnails / icons / heroes when schema allows.

### Inputs (forms)

- **`Input`**: `label`, `name`, `type`, `placeholder`.
- **`Checkbox`**, **`Radio`**, **`Select`**: see schema for `name` / `options`.

### Actions

- **`Button`**: primary / secondary; **`openUrl`** when a URL is available.

### No `Extended.If`, no `Divider`

Conditional UI and dividers are **not** first-class types. Use:

- New **createSurface** + 新树，或
- 同一 surface 上追加 / 调整 **updateComponent** 行，或
- 细线 **`Card` `strokeThickness`**（少用）。

## Tiny snippets（须带 `surfaceId`）

```jsonl
{"@x", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"x", "title", "Text", {"content": "标题", "fontSize": 18, "fontWeight": "500", "maxLines": 1, "textOverflow": "ellipsis", "fontColor": "#000000"}}
{"x", "row", "Row", {"width": "matchParent", "justifyContent": "spaceBetween", "alignItems": "center", "space": 8}, ["left", "right"]}
```

## Practical examples

See `examples/flows/*.md`, `examples/cards/*.md`, and `examples/capabilities/streaming.md`.
