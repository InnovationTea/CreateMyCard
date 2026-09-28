# Compact Modal / Confirm Patterns

`skills/a2ui/examples/flows/modal.md` 使用 `Extended.If`。本 skill **无 If 类型** — 用 **分区 Card** 或 **新 surface / 新根 Card** 表达「确认块」。

## Confirmation strip（同表面下的警告区）

```jsonl
{"@modal_item", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"modal_item", "root", "Card", {"title": "项目文档", "layout": "vertical", "gap": 12, "width": "matchParent", "padding": 12, "fill": "#F1F3F5", "radius": 20}, ["item_row", "confirm_card"]}
{"modal_item", "item_row", "Row", {"width": "matchParent", "justifyContent": "spaceBetween", "alignItems": "center", "space": 12}, ["item_info", "delete_trigger"]}
{"modal_item", "item_info", "Text", {"content": "Project Document", "fontSize": 14, "fontWeight": "500", "maxLines": 1, "textOverflow": "ellipsis", "fontColor": "#000000"}}
{"modal_item", "delete_trigger", "Button", {"label": "删除…", "borderRadius": 14, "fontSize": 12, "fontWeight": 400, "openUrl": "https://example.com/delete-prompt"}}
{"modal_item", "confirm_card", "Card", {"title": "删除该项？", "description": "此操作不可撤销。", "layout": "vertical", "gap": 12, "width": "matchParent", "fill": "#FFFFFF", "radius": 16, "padding": 12, "strokeThickness": 1, "strokeColor": "#E5E5E5"}, ["confirm_actions"]}
{"modal_item", "confirm_actions", "Row", {"width": "matchParent", "justifyContent": "center", "alignItems": "center", "space": 8}, ["cancel_btn", "confirm_btn"]}
{"modal_item", "cancel_btn", "Button", {"label": "取消", "borderRadius": 14, "fontSize": 12, "fontWeight": 400, "openUrl": "https://example.com/cancel"}}
{"modal_item", "confirm_btn", "Button", {"label": "删除", "borderRadius": 20, "fontSize": 16, "fontWeight": 500, "backgroundColor": "#E84026", "openUrl": "https://example.com/confirm-delete"}}
```

## Edit profile（表单区）

```jsonl
{"@modal_profile", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"modal_profile", "root", "Card", {"title": "个人资料", "layout": "vertical", "gap": 12, "width": "matchParent", "padding": 12, "fill": "#F1F3F5", "radius": 20}, ["profile_row", "edit_card"]}
{"modal_profile", "profile_row", "Row", {"width": "matchParent", "justifyContent": "spaceBetween", "alignItems": "center", "space": 12}, ["info_column", "edit_trigger"]}
{"modal_profile", "info_column", "Column", {"space": 4, "width": "matchParent"}, ["user_name", "user_email"]}
{"modal_profile", "user_name", "Text", {"content": "John Doe", "fontSize": 14, "fontWeight": "500", "fontColor": "#000000"}}
{"modal_profile", "user_email", "Text", {"content": "john@example.com", "fontSize": 12, "fontWeight": "400", "fontColor": "#999999"}}
{"modal_profile", "edit_trigger", "Button", {"label": "编辑", "borderRadius": 14, "fontSize": 12, "fontWeight": 400, "openUrl": "https://example.com/edit-profile"}}
{"modal_profile", "edit_card", "Card", {"title": "编辑资料", "layout": "vertical", "gap": 12, "width": "matchParent", "fill": "#FFFFFF", "radius": 16, "padding": 12}, ["name_field", "email_field", "edit_actions"]}
{"modal_profile", "name_field", "Input", {"label": "显示名", "name": "displayName", "type": "text", "placeholder": "Display Name"}}
{"modal_profile", "email_field", "Input", {"label": "邮箱", "name": "email", "type": "email", "placeholder": "Email"}}
{"modal_profile", "edit_actions", "Row", {"width": "matchParent", "justifyContent": "end", "alignItems": "center", "space": 8}, ["discard_btn", "save_btn"]}
{"modal_profile", "discard_btn", "Button", {"label": "取消", "borderRadius": 14, "fontSize": 12, "fontWeight": 400, "openUrl": "https://example.com/discard"}}
{"modal_profile", "save_btn", "Button", {"label": "保存", "borderRadius": 20, "fontSize": 16, "fontWeight": 500, "backgroundColor": "#0A59F7", "openUrl": "https://example.com/save-profile"}}
```

## Notes

- 若需要 **强 modal 覆盖层**（遮罩），由宿主壳层实现；极简行仅描述卡片内容树。
- 「关闭弹层」：宿主路由、**`deleteSurface`** 行，或 **新 `createSurface`** 替换当前展示（见 [`examples/capabilities/multi-surface.md`](capabilities/multi-surface.md)）。
