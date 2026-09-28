# Compact List Examples

平行于 `skills/a2ui/examples/flows/list.md`：单外框 + 轻分组列表（`createSurface` + `updateComponent`）。

## Restaurant list

```jsonl
{"@list_resto", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"list_resto", "root", "Card", {"title": "附近餐厅", "description": "按距离排序", "layout": "vertical", "gap": 12, "width": "matchParent", "padding": 12, "fill": "#F1F3F5", "radius": 20}, ["header_row", "list_col"]}
{"list_resto", "header_row", "Row", {"width": "matchParent", "justifyContent": "spaceBetween", "alignItems": "center", "space": 12}, ["title", "filter_btn"]}
{"list_resto", "title", "Text", {"content": "Nearby Restaurants", "fontSize": 18, "fontWeight": "500", "maxLines": 1, "textOverflow": "ellipsis", "fontColor": "#000000"}}
{"list_resto", "filter_btn", "Button", {"label": "筛选", "borderRadius": 14, "fontSize": 12, "fontWeight": 400, "openUrl": "https://example.com/filter"}}
{"list_resto", "list_col", "Column", {"space": 12, "width": "matchParent"}, ["rest1_body", "rest2_body"]}
{"list_resto", "rest1_body", "Card", {"layout": "vertical", "gap": 8, "width": "matchParent", "fill": "#FFFFFF", "radius": 12, "padding": 8, "strokeThickness": 1, "strokeColor": "#E5E5E5"}, ["rest1_header", "rest1_meta"]}
{"list_resto", "rest1_header", "Row", {"width": "matchParent", "justifyContent": "spaceBetween", "alignItems": "center", "space": 8}, ["rest1_name", "rest1_tag"]}
{"list_resto", "rest1_name", "Text", {"content": "Luna Bistro", "fontSize": 16, "fontWeight": "500", "maxLines": 1, "textOverflow": "ellipsis", "fontColor": "#000000"}}
{"list_resto", "rest1_tag", "Text", {"content": "Italian", "fontSize": 12, "fontWeight": "400", "maxLines": 1, "textOverflow": "ellipsis", "fontColor": "#999999"}}
{"list_resto", "rest1_meta", "Row", {"width": "matchParent", "alignItems": "center", "space": 8}, ["rest1_rating", "rest1_price", "rest1_spacer", "rest1_menu", "rest1_book"]}
{"list_resto", "rest1_rating", "Text", {"content": "Rating 4.7", "fontSize": 14, "fontWeight": "400", "fontColor": "#000000"}}
{"list_resto", "rest1_price", "Text", {"content": "$$$", "fontSize": 14, "fontWeight": "400", "fontColor": "#666666"}}
{"list_resto", "rest1_spacer", "Text", {"content": "", "layoutWeight": 1, "width": "matchParent"}}
{"list_resto", "rest1_menu", "Button", {"label": "菜单", "borderRadius": 14, "fontSize": 12, "fontWeight": 400, "openUrl": "https://example.com/menu/1"}}
{"list_resto", "rest1_book", "Button", {"label": "订座", "borderRadius": 20, "fontSize": 16, "fontWeight": 500, "backgroundColor": "#0A59F7", "openUrl": "https://example.com/book/1"}}
{"list_resto", "rest2_body", "Card", {"layout": "vertical", "gap": 8, "width": "matchParent", "fill": "#FFFFFF", "radius": 12, "padding": 8, "strokeThickness": 1, "strokeColor": "#E5E5E5"}, ["rest2_header", "rest2_meta"]}
{"list_resto", "rest2_header", "Row", {"width": "matchParent", "justifyContent": "spaceBetween", "alignItems": "center", "space": 8}, ["rest2_name", "rest2_tag"]}
{"list_resto", "rest2_name", "Text", {"content": "River & Stone", "fontSize": 16, "fontWeight": "500", "maxLines": 1, "textOverflow": "ellipsis", "fontColor": "#000000"}}
{"list_resto", "rest2_tag", "Text", {"content": "Seafood", "fontSize": 12, "fontWeight": "400", "maxLines": 1, "textOverflow": "ellipsis", "fontColor": "#999999"}}
{"list_resto", "rest2_meta", "Row", {"width": "matchParent", "alignItems": "center", "space": 8}, ["rest2_rating", "rest2_price", "rest2_spacer", "rest2_menu", "rest2_book"]}
{"list_resto", "rest2_rating", "Text", {"content": "Rating 4.5", "fontSize": 14, "fontWeight": "400", "fontColor": "#000000"}}
{"list_resto", "rest2_price", "Text", {"content": "$$", "fontSize": 14, "fontWeight": "400", "fontColor": "#666666"}}
{"list_resto", "rest2_spacer", "Text", {"content": "", "layoutWeight": 1, "width": "matchParent"}}
{"list_resto", "rest2_menu", "Button", {"label": "菜单", "borderRadius": 14, "fontSize": 12, "fontWeight": 400, "openUrl": "https://example.com/menu/2"}}
{"list_resto", "rest2_book", "Button", {"label": "订座", "borderRadius": 20, "fontSize": 16, "fontWeight": 500, "backgroundColor": "#0A59F7", "openUrl": "https://example.com/book/2"}}
```

## Horizontal categories

```jsonl
{"@list_cat", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"list_cat", "root", "Card", {"title": "分类", "layout": "vertical", "gap": 12, "width": "matchParent", "padding": 12, "fill": "#F1F3F5", "radius": 20}, ["category_row"]}
{"list_cat", "category_row", "Row", {"width": "matchParent", "justifyContent": "start", "alignItems": "center", "space": 8}, ["cat1", "cat2", "cat3"]}
{"list_cat", "cat1", "Text", {"content": "Italian", "fontSize": 12, "fontWeight": "400", "fontColor": "#0A59F7", "padding": [8, 12, 8, 12], "borderRadius": 4, "borderWidth": 1, "borderColor": "#CFE0FF", "backgroundColor": "#EEF4FF"}}
{"list_cat", "cat2", "Text", {"content": "Seafood", "fontSize": 12, "fontWeight": "400", "fontColor": "#0A59F7", "padding": [8, 12, 8, 12], "borderRadius": 4, "borderWidth": 1, "borderColor": "#CFE0FF", "backgroundColor": "#EEF4FF"}}
{"list_cat", "cat3", "Text", {"content": "Asian", "fontSize": 12, "fontWeight": "400", "fontColor": "#0A59F7", "padding": [8, 12, 8, 12], "borderRadius": 4, "borderWidth": 1, "borderColor": "#CFE0FF", "backgroundColor": "#EEF4FF"}}
```

## Empty state

```jsonl
{"@list_empty", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"list_empty", "root", "Card", {"title": "无结果", "description": "试试调整筛选条件", "layout": "vertical", "gap": 12, "width": "matchParent", "padding": 16, "fill": "#F1F3F5", "radius": 20}, ["empty_message", "action_btn"]}
{"list_empty", "empty_message", "Text", {"content": "Try adjusting your search or filters", "fontSize": 14, "fontWeight": "400", "fontColor": "#666666"}}
{"list_empty", "action_btn", "Button", {"label": "清除筛选", "borderRadius": 20, "fontSize": 16, "fontWeight": 500, "openUrl": "https://example.com/clear"}}
```
