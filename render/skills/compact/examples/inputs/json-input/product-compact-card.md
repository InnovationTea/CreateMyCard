# JSON → Compact Product Card

平行于 `skills/a2ui/examples/inputs/json-input/product-compact-card.md`：**Mode A** 将结构化 JSON 映射为 **Dialog Card**。

## Input (JSON)

```json
{
  "title": "MacBook Pro 14\"",
  "subtitle": "M4 Pro · 18GB · 512GB",
  "price": "¥14,999",
  "priceNote": "券后预计 ¥13,999",
  "badge": "新品",
  "imageUrl": "https://picsum.photos/seed/mbp14/480/480",
  "primaryUrl": "https://example.com/cart",
  "secondaryUrl": "https://example.com/save"
}
```

## Output (minimal GenUI JSONL)

```jsonl
{"@product_card", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"product_card", "root", "Card", {"title": "商品", "layout": "vertical", "gap": 8, "width": "matchParent", "padding": 12, "fill": "#F1F3F5", "radius": 20}, ["body"]}
{"product_card", "body", "Column", {"space": 8, "width": "matchParent", "alignItems": "stretch"}, ["row_top", "row_price", "row_actions"]}
{"product_card", "row_top", "Row", {"width": "matchParent", "alignItems": "center", "space": 8}, ["cover", "text_col"]}
{"product_card", "cover", "Image", {"src": "https://picsum.photos/seed/mbp14/480/480", "width": 72, "height": 72, "borderRadius": 12, "objectFit": "cover"}}
{"product_card", "text_col", "Column", {"space": 4, "layoutWeight": 1, "width": "matchParent", "alignItems": "stretch"}, ["title_row", "subtitle"]}
{"product_card", "title_row", "Row", {"width": "matchParent", "alignItems": "center", "space": 8}, ["title", "badge"]}
{"product_card", "title", "Text", {"content": "MacBook Pro 14\"", "fontSize": 16, "fontWeight": "500", "maxLines": 1, "textOverflow": "ellipsis", "fontColor": "#000000", "layoutWeight": 1}}
{"product_card", "badge", "Text", {"content": "新品", "fontSize": 12, "fontWeight": "500", "maxLines": 1, "textOverflow": "ellipsis", "fontColor": "#0A59F7", "padding": [4, 8, 4, 8], "borderRadius": 14, "borderWidth": 1, "borderColor": "#DCE7FF", "backgroundColor": "#EEF4FF"}}
{"product_card", "subtitle", "Text", {"content": "M4 Pro · 18GB · 512GB", "fontSize": 12, "fontWeight": "400", "maxLines": 1, "textOverflow": "ellipsis", "fontColor": "#666666", "width": "matchParent"}}
{"product_card", "row_price", "Row", {"width": "matchParent", "justifyContent": "spaceBetween", "alignItems": "center", "space": 8}, ["price", "price_note"]}
{"product_card", "price", "Text", {"content": "¥14,999", "fontSize": 16, "fontWeight": "500", "fontColor": "#000000"}}
{"product_card", "price_note", "Text", {"content": "券后 ¥13,999", "fontSize": 16, "fontWeight": "600", "fontColor": "#C62828", "textAlign": "end", "layoutWeight": 1}}
{"product_card", "row_actions", "Row", {"width": "matchParent", "alignItems": "center", "space": 8}, ["btn_primary", "btn_secondary"]}
{"product_card", "btn_primary", "Button", {"label": "加入购物车", "borderRadius": 14, "fontSize": 12, "fontWeight": 500, "backgroundColor": "#0A59F7", "openUrl": "https://example.com/cart"}}
{"product_card", "btn_secondary", "Button", {"label": "收藏", "borderRadius": 14, "fontSize": 12, "fontWeight": 400, "backgroundColor": "#F2F2F2", "openUrl": "https://example.com/save"}}
```

## Mapping notes

- **Badge**：小圆角 **Text** + `padding` + `borderWidth`（或外层小 **Card**），避免与标题同一 Row 被拉伸成宽药丸失控 — 已为 `title` 设置 `layoutWeight` **1**。
- **价格行**：**Row** 上 `justifyContent` `"spaceBetween"` 分离现价与券后价。
- **URLs**：来自 JSON 的链接填入 **`openUrl`**；无 URL 则省略或改宿主动作。
