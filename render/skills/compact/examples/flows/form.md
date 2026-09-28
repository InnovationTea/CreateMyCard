# Compact Form Examples

与 `skills/a2ui/examples/flows/form.md` 同场景的 **极简 GenUI** 版本（`createSurface` + `updateComponent`，Harmony 风格 props）。

## Login

```jsonl
{"@login_surf", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"login_surf", "root", "Card", {"title": "欢迎回来", "description": "登录你的账户", "layout": "vertical", "gap": 12, "width": "matchParent", "padding": 16, "fill": "#F1F3F5", "radius": 20}, ["form_fields", "submit_btn", "forgot_row"]}
{"login_surf", "form_fields", "Column", {"space": 12, "width": "matchParent"}, ["email_field", "password_field"]}
{"login_surf", "email_field", "Input", {"label": "邮箱", "name": "email", "type": "email", "placeholder": "Email"}}
{"login_surf", "password_field", "Input", {"label": "密码", "name": "password", "type": "password", "placeholder": "Password"}}
{"login_surf", "submit_btn", "Button", {"label": "登录", "backgroundColor": "#0A59F7", "borderRadius": 20, "fontSize": 16, "fontWeight": 500, "width": "matchParent", "openUrl": "https://example.com/sign-in"}}
{"login_surf", "forgot_row", "Row", {"width": "matchParent", "justifyContent": "end", "alignItems": "center", "space": 0}, ["forgot_text"]}
{"login_surf", "forgot_text", "Text", {"content": "忘记密码？", "fontSize": 12, "fontWeight": "400", "fontColor": "#0A59F7", "decoration": {"type": "underline", "color": "#0A59F7", "style": "solid"}}}
```

## Registration

```jsonl
{"@reg_surf", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"reg_surf", "root", "Card", {"title": "创建账户", "description": "填写以下信息", "layout": "vertical", "gap": 12, "width": "matchParent", "padding": 16, "fill": "#F1F3F5", "radius": 20}, ["form_fields", "terms_row", "submit_btn"]}
{"reg_surf", "form_fields", "Column", {"space": 12, "width": "matchParent"}, ["name_field", "email_field", "password_field"]}
{"reg_surf", "name_field", "Input", {"label": "姓名", "name": "fullName", "type": "text", "placeholder": "Full Name"}}
{"reg_surf", "email_field", "Input", {"label": "邮箱", "name": "email", "type": "email", "placeholder": "Email"}}
{"reg_surf", "password_field", "Input", {"label": "密码", "name": "password", "type": "password", "placeholder": "Password"}}
{"reg_surf", "terms_row", "Row", {"width": "matchParent", "alignItems": "center", "space": 8}, ["terms_check", "terms_text"]}
{"reg_surf", "terms_check", "Checkbox", {"label": "同意条款", "name": "terms", "checked": false}}
{"reg_surf", "terms_text", "Text", {"content": "我同意服务条款", "fontSize": 14, "fontWeight": "400", "fontColor": "#000000"}}
{"reg_surf", "submit_btn", "Button", {"label": "创建账户", "backgroundColor": "#0A59F7", "borderRadius": 20, "fontSize": 16, "fontWeight": 500, "width": "matchParent", "openUrl": "https://example.com/register"}}
```

## Booking

```jsonl
{"@book_surf", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"book_surf", "root", "Card", {"title": "订座", "description": "填写时间与人数", "layout": "vertical", "gap": 12, "width": "matchParent", "padding": 16, "fill": "#F1F3F5", "radius": 20}, ["name_field", "datetime_field", "guests_field", "notes_field", "submit_btn"]}
{"book_surf", "name_field", "Input", {"label": "姓名", "name": "guestName", "type": "text", "placeholder": "Your Name"}}
{"book_surf", "datetime_field", "Input", {"label": "时间", "name": "when", "type": "text", "placeholder": "Date & Time (e.g., 2026-04-09 19:30)"}}
{"book_surf", "guests_field", "Input", {"label": "人数", "name": "guests", "type": "number", "placeholder": "1-10"}}
{"book_surf", "notes_field", "Input", {"label": "备注", "name": "notes", "type": "text", "placeholder": "Special Requests"}}
{"book_surf", "submit_btn", "Button", {"label": "确认订座", "backgroundColor": "#0A59F7", "borderRadius": 20, "fontSize": 16, "fontWeight": 500, "width": "matchParent", "openUrl": "https://example.com/booking/confirm"}}
```

## Key patterns

1. **One primary Button** per screen; tertiary uses **Text** underline.
2. **Root Card** `width`: `"matchParent"`, `radius` **20**, `padding` **12–16**.
3. **Column** `space` **8–12** between fields.
