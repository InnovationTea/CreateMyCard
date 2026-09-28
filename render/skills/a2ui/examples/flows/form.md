# A2UI Form Examples

Examples of form layouts following HarmonyOS design specification.

## Login Form

A clean login form with HarmonyOS styling.

```jsonl
{"version":"v0.9","createSurface":{"surfaceId":"login","catalogId":"https://xxx/specification/ohos/extended_catalog.json","theme":{"primaryColor":"#FF0A59F7"}}}
{"version":"v0.9","updateComponents":{"surfaceId":"login","components":[{"id":"root","component":"Extended.Column","children":["form_content"],"space":0,"styles":{"width":"matchParent","constraintSize":{"maxWidth":336},"borderRadius":16,"clip":true,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"login","components":[{"id":"form_content","component":"Extended.Column","children":["title","subtitle","form_fields","submit_btn","forgot_row"],"space":0,"styles":{"width":"matchParent","alignItems":"top"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"login","components":[{"id":"title","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000","margin":{"bottom":4}},"content":"Welcome back"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"login","components":[{"id":"subtitle","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":2,"textOverflow":"ellipsis","fontColor":"#99000000","margin":{"bottom":16}},"content":"Sign in to your account"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"login","components":[{"id":"form_fields","component":"Extended.Column","children":["email_field","password_field"],"space":12,"styles":{"width":"matchParent","margin":{"bottom":16}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"login","components":[{"id":"email_field","component":"Extended.TextInput","enabled":true,"maxLength":120,"type":"email","styles":{"width":"matchParent","height":56,"borderRadius":20,"backgroundColor":"#0C000000","padding":{"top":16,"right":16,"bottom":16,"left":16},"fontSize":16,"fontWeight":400,"fontColor":"#E5000000","placeholderColor":"#99000000","caretColor":"#FF0A59F7","showUnderline":false},"placeholder":"Email","text":{"path":"/form/email"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"login","path":"/form","value":{"email":"","password":""}}}
{"version":"v0.9","updateComponents":{"surfaceId":"login","components":[{"id":"password_field","component":"Extended.TextInput","enabled":true,"maxLength":120,"type":"password","styles":{"width":"matchParent","height":56,"borderRadius":20,"backgroundColor":"#0C000000","padding":{"top":16,"right":16,"bottom":16,"left":16},"fontSize":16,"fontWeight":400,"fontColor":"#E5000000","placeholderColor":"#99000000","caretColor":"#FF0A59F7","showUnderline":false},"placeholder":"Password","text":{"path":"/form/password"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"login","components":[{"id":"submit_btn","component":"Extended.Button","enabled":true,"styles":{"width":"matchParent","height":40,"borderRadius":20,"fontSize":16,"fontWeight":500,"backgroundColor":"#FF0A59F7","margin":{"bottom":8}},"label":"Sign In"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"login","components":[{"id":"forgot_row","component":"Extended.Row","children":["forgot_text"],"space":0,"styles":{"width":"matchParent","justifyContent":"end","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"login","components":[{"id":"forgot_text","component":"Extended.Text","styles":{"fontSize":12,"fontWeight":"400","maxLines":1,"textOverflow":"ellipsis","fontColor":"#FF0A59F7","decoration":{"type":"underline","color":"#FF0A59F7","style":"solid"}},"content":"Forgot password?"}]}}
```

## Registration Form

A multi-field registration form with validation.

```jsonl
{"version":"v0.9","createSurface":{"surfaceId":"register","catalogId":"https://xxx/specification/ohos/extended_catalog.json","theme":{"primaryColor":"#FF0A59F7"}}}
{"version":"v0.9","updateComponents":{"surfaceId":"register","components":[{"id":"root","component":"Extended.Column","children":["form_content"],"space":0,"styles":{"width":"matchParent","constraintSize":{"maxWidth":336},"borderRadius":16,"clip":true,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"register","components":[{"id":"form_content","component":"Extended.Column","children":["title","form_fields","terms_row","submit_btn"],"space":12,"styles":{"width":"matchParent","alignItems":"top"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"register","components":[{"id":"title","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000","margin":{"bottom":4}},"content":"Create account"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"register","components":[{"id":"form_fields","component":"Extended.Column","children":["name_field","email_field","password_field"],"space":12,"styles":{"width":"matchParent","margin":{"bottom":4}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"register","components":[{"id":"name_field","component":"Extended.TextInput","enabled":true,"maxLength":80,"type":"normal","styles":{"width":"matchParent","height":56,"borderRadius":20,"backgroundColor":"#0C000000","padding":{"top":16,"right":16,"bottom":16,"left":16},"fontSize":16,"fontWeight":400,"fontColor":"#E5000000","placeholderColor":"#99000000","caretColor":"#FF0A59F7","showUnderline":false},"placeholder":"Full Name","text":{"path":"/register/name"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"register","path":"/register","value":{"name":"","email":"","password":""}}}
{"version":"v0.9","updateComponents":{"surfaceId":"register","components":[{"id":"email_field","component":"Extended.TextInput","enabled":true,"maxLength":120,"type":"email","styles":{"width":"matchParent","height":56,"borderRadius":20,"backgroundColor":"#0C000000","padding":{"top":16,"right":16,"bottom":16,"left":16},"fontSize":16,"fontWeight":400,"fontColor":"#E5000000","placeholderColor":"#99000000","caretColor":"#FF0A59F7","showUnderline":false},"placeholder":"Email","text":{"path":"/register/email"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"register","components":[{"id":"password_field","component":"Extended.TextInput","enabled":true,"maxLength":120,"type":"password","styles":{"width":"matchParent","height":56,"borderRadius":20,"backgroundColor":"#0C000000","padding":{"top":16,"right":16,"bottom":16,"left":16},"fontSize":16,"fontWeight":400,"fontColor":"#E5000000","placeholderColor":"#99000000","caretColor":"#FF0A59F7","showUnderline":false},"placeholder":"Password","text":{"path":"/register/password"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"register","components":[{"id":"terms_row","component":"Extended.Row","children":["terms_check","terms_text"],"space":8,"styles":{"width":"matchParent","alignItems":"center","margin":{"bottom":4}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"register","components":[{"id":"terms_check","component":"Extended.Checkbox","group":"terms","styles":{"shape":"rounded_square","selectedColor":"#FF0A59F7","unselectedColor":"#33000000","mark":{"strokeColor":"#FFFFFF","size":12,"strokeWidth":2}},"select":false}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"register","components":[{"id":"terms_text","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":2,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"I agree to the Terms of Service"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"register","components":[{"id":"submit_btn","component":"Extended.Button","enabled":true,"styles":{"width":"matchParent","height":40,"borderRadius":20,"fontSize":16,"fontWeight":500,"backgroundColor":"#FF0A59F7"},"label":"Create Account"}]}}
```

## Booking Form

A restaurant booking form with date/time selection.

```jsonl
{"version":"v0.9","createSurface":{"surfaceId":"booking","catalogId":"https://xxx/specification/ohos/extended_catalog.json","theme":{"primaryColor":"#FF0A59F7"}}}
{"version":"v0.9","updateComponents":{"surfaceId":"booking","components":[{"id":"root","component":"Extended.Column","children":["form_content"],"space":0,"styles":{"width":"matchParent","constraintSize":{"maxWidth":336},"borderRadius":16,"clip":true,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"booking","components":[{"id":"form_content","component":"Extended.Column","children":["title","form_fields","submit_btn"],"space":12,"styles":{"width":"matchParent","alignItems":"top"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"booking","components":[{"id":"title","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000","margin":{"bottom":4}},"content":"Book a Table"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"booking","components":[{"id":"form_fields","component":"Extended.Column","children":["name_field","datetime_field","guests_field","notes_field"],"space":12,"styles":{"width":"matchParent","margin":{"bottom":4}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"booking","components":[{"id":"name_field","component":"Extended.TextInput","enabled":true,"maxLength":80,"type":"normal","styles":{"width":"matchParent","height":56,"borderRadius":20,"backgroundColor":"#0C000000","padding":{"top":16,"right":16,"bottom":16,"left":16},"fontSize":16,"fontWeight":400,"fontColor":"#E5000000","placeholderColor":"#99000000","caretColor":"#FF0A59F7","showUnderline":false},"placeholder":"Your Name","text":{"path":"/booking/fields/name"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"booking","path":"/booking/fields","value":{"name":"","datetime":"","guests":"","notes":""}}}
{"version":"v0.9","updateComponents":{"surfaceId":"booking","components":[{"id":"datetime_field","component":"Extended.TextInput","enabled":true,"maxLength":40,"type":"normal","styles":{"width":"matchParent","height":56,"borderRadius":20,"backgroundColor":"#0C000000","padding":{"top":16,"right":16,"bottom":16,"left":16},"fontSize":16,"fontWeight":400,"fontColor":"#E5000000","placeholderColor":"#99000000","caretColor":"#FF0A59F7","showUnderline":false},"placeholder":"Date & Time (e.g., 2026-04-09 19:30)","text":{"path":"/booking/fields/datetime"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"booking","components":[{"id":"guests_field","component":"Extended.TextInput","enabled":true,"maxLength":2,"type":"number","styles":{"width":"matchParent","height":56,"borderRadius":20,"backgroundColor":"#0C000000","padding":{"top":16,"right":16,"bottom":16,"left":16},"fontSize":16,"fontWeight":400,"fontColor":"#E5000000","placeholderColor":"#99000000","caretColor":"#FF0A59F7","showUnderline":false},"placeholder":"Number of Guests (1-10)","text":{"path":"/booking/fields/guests"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"booking","components":[{"id":"notes_field","component":"Extended.TextInput","enabled":true,"maxLength":200,"type":"normal","styles":{"width":"matchParent","height":56,"borderRadius":20,"backgroundColor":"#0C000000","padding":{"top":16,"right":16,"bottom":16,"left":16},"fontSize":16,"fontWeight":400,"maxLines":3,"fontColor":"#E5000000","placeholderColor":"#99000000","caretColor":"#FF0A59F7","showUnderline":false},"placeholder":"Special Requests","text":{"path":"/booking/fields/notes"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"booking","components":[{"id":"submit_btn","component":"Extended.Button","enabled":true,"styles":{"width":"matchParent","height":40,"borderRadius":20,"fontSize":16,"fontWeight":500,"backgroundColor":"#FF0A59F7"},"label":"Confirm Booking"}]}}
```

## Key Design Patterns

1. **HarmonyOS theme**: `theme.primaryColor` 使用 **`#FF0A59F7`**（`font_emphasize` / Light 展开）；卡片底板 **`#FFFFFFFF`**（`comp_background_list_card`）。
2. **Card shell**（`harmony-card-spec.md` **A4** / **C3**）：最外层圆角 **16vp**；左右内边距 **12vp**；**`constraintSize.maxWidth`: 336**。
3. **Spacing**: 4vp 网格（4 / 8 / 12 / 16 …）。
4. **Typography**: 主标题 `Body_L` **16** + `fontColor` **`#E5000000`**；副文 **`#99000000`**；弱提示 **`#66000000`**。
5. **Primary CTA**（`harmony-ui-components-a2ui.md` **B1** 强调按钮 / `quick-snippets` §7b）：**height 40**、**borderRadius 20**、**`backgroundColor` `#FF0A59F7`**、**fontSize 16**、**fontWeight 500**。
6. **Tertiary / link**（如忘记密码）：**`Extended.Text`** + **`fontColor` `#FF0A59F7`** + **`decoration` underline**，不要用第二枚实心 `Button`。
