# Compact Booking Flow

平行于 `skills/a2ui/examples/flows/booking-flow.md`：多步流程。每一步可 **新的 `createSurface`（新 `@surfaceId`）** 表示整场景替换，或 **同一 `surfaceId` 上继续发 `updateComponent`**（取决于宿主）。下面示例采用 **每步一个新 surface**（`booking_s1` … `booking_s4`），最清晰。

## Step 1 — Search

```jsonl
{"@booking_s1", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"booking_s1", "root", "Card", {"title": "找餐厅", "layout": "vertical", "gap": 12, "width": "matchParent", "padding": 16, "fill": "#FFFFFF", "radius": 20}, ["search_form"]}
{"booking_s1", "search_form", "Column", {"space": 12, "width": "matchParent"}, ["location_field", "datetime_field", "guests_field", "search_btn"]}
{"booking_s1", "location_field", "Input", {"label": "位置", "name": "location", "type": "text", "placeholder": "Location"}}
{"booking_s1", "datetime_field", "Input", {"label": "时间", "name": "when", "type": "text", "placeholder": "When (e.g., 2026-04-09 19:30)"}}
{"booking_s1", "guests_field", "Input", {"label": "人数", "name": "guests", "type": "number", "placeholder": "Guests (1-10)"}}
{"booking_s1", "search_btn", "Button", {"label": "搜索", "backgroundColor": "#0A59F7", "borderRadius": 20, "fontSize": 16, "fontWeight": 500, "width": "matchParent", "openUrl": "https://example.com/search"}}
```

## Step 2 — Results（新场景：整树替换）

```jsonl
{"@booking_s2", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"booking_s2", "root", "Card", {"title": "搜索结果", "layout": "vertical", "gap": 12, "width": "matchParent", "padding": 16, "fill": "#FFFFFF", "radius": 20}, ["header2", "results_col"]}
{"booking_s2", "header2", "Row", {"width": "matchParent", "alignItems": "center", "space": 12}, ["back_btn", "title2"]}
{"booking_s2", "back_btn", "Button", {"label": "返回", "borderRadius": 14, "fontSize": 12, "fontWeight": 400, "openUrl": "https://example.com/back"}}
{"booking_s2", "title2", "Text", {"content": "Search Results", "fontSize": 18, "fontWeight": "500", "fontColor": "#000000"}}
{"booking_s2", "results_col", "Column", {"space": 12, "width": "matchParent"}, ["rest1_card"]}
{"booking_s2", "rest1_card", "Card", {"title": "Luna Bistro", "description": "Italian · Rating 4.7", "layout": "vertical", "gap": 8, "width": "matchParent", "padding": 12, "fill": "#F1F3F5", "radius": 16}, ["rest1_actions"]}
{"booking_s2", "rest1_actions", "Row", {"width": "matchParent", "justifyContent": "end", "alignItems": "center", "space": 8}, ["rest1_menu", "rest1_select"]}
{"booking_s2", "rest1_menu", "Button", {"label": "菜单", "borderRadius": 14, "fontSize": 12, "fontWeight": 400, "openUrl": "https://example.com/menu"}}
{"booking_s2", "rest1_select", "Button", {"label": "选择", "borderRadius": 20, "fontSize": 16, "fontWeight": 500, "backgroundColor": "#0A59F7", "openUrl": "https://example.com/select"}}
```

## Step 3 — Booking form

```jsonl
{"@booking_s3", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"booking_s3", "root", "Card", {"title": "完成订座", "layout": "vertical", "gap": 12, "width": "matchParent", "padding": 16, "fill": "#FFFFFF", "radius": 20}, ["summary", "booking_form"]}
{"booking_s3", "summary", "Card", {"title": "餐厅", "description": "Luna Bistro", "layout": "vertical", "gap": 6, "width": "matchParent", "padding": 12, "fill": "#F1F3F5", "radius": 16}, []}
{"booking_s3", "booking_form", "Column", {"space": 12, "width": "matchParent"}, ["name_field", "email_field", "phone_field", "submit_row"]}
{"booking_s3", "name_field", "Input", {"label": "姓名", "name": "name", "type": "text", "placeholder": "Your Name"}}
{"booking_s3", "email_field", "Input", {"label": "邮箱", "name": "email", "type": "email", "placeholder": "Email"}}
{"booking_s3", "phone_field", "Input", {"label": "手机", "name": "phone", "type": "text", "placeholder": "Phone"}}
{"booking_s3", "submit_row", "Row", {"width": "matchParent", "justifyContent": "end", "alignItems": "center", "space": 8}, ["cancel_btn", "confirm_btn"]}
{"booking_s3", "cancel_btn", "Button", {"label": "取消", "borderRadius": 14, "fontSize": 12, "fontWeight": 400, "openUrl": "https://example.com/cancel-booking"}}
{"booking_s3", "confirm_btn", "Button", {"label": "提交", "borderRadius": 20, "fontSize": 16, "fontWeight": 500, "backgroundColor": "#0A59F7", "openUrl": "https://example.com/submit-booking"}}
```

## Step 4 — Confirmation

```jsonl
{"@booking_s4", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"booking_s4", "root", "Card", {"title": "预订已提交", "description": "我们已收到你的请求。", "layout": "vertical", "gap": 12, "width": "matchParent", "padding": 16, "fill": "#F1F3F5", "radius": 20}, ["done_btn"]}
{"booking_s4", "done_btn", "Button", {"label": "完成", "backgroundColor": "#0A59F7", "borderRadius": 20, "fontSize": 16, "fontWeight": 500, "width": "matchParent", "openUrl": "https://example.com/done"}}
```
