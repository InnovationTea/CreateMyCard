# A2UI Modal Examples

Examples of dialog and popup patterns using the Modal component, following HarmonyOS design specification.

## Confirmation Modal

A warning confirmation dialog for destructive actions.

```jsonl
{"version":"v0.9","createSurface":{"surfaceId":"main","catalogId":"https://xxx/specification/ohos/extended_catalog.json","theme":{"primaryColor":"#FF0A59F7"}}}
{"version":"v0.9","updateComponents":{"surfaceId":"main","components":[{"id":"root","component":"Extended.Column","children":["content","confirm_if"],"space":12,"styles":{"width":"matchParent","constraintSize":{"maxWidth":336},"borderRadius":16,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"main","components":[{"id":"content","component":"Extended.Column","children":["item_row"],"space":8,"styles":{"width":"matchParent"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"main","components":[{"id":"item_row","component":"Extended.Row","children":["item_info","delete_trigger"],"space":12,"styles":{"width":"matchParent","justifyContent":"spaceBetween","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"main","components":[{"id":"item_info","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"Project Document"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"main","components":[{"id":"delete_trigger","component":"Extended.Button","enabled":true,"styles":{"height":28,"borderRadius":14,"fontSize":14,"fontWeight":400,"backgroundColor":"#0C000000"},"label":"Delete…"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"main","components":[{"id":"confirm_if","component":"Extended.If","condition":true,"childrenIf":["confirm_body"],"childrenElse":[],"styles":{}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"main","components":[{"id":"confirm_body","component":"Extended.Column","children":["confirm_title","confirm_message","confirm_actions"],"space":12,"styles":{"width":"matchParent","alignItems":"center","padding":{"top":8,"right":0,"bottom":8,"left":0}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"main","components":[{"id":"confirm_title","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"Delete item?"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"main","components":[{"id":"confirm_message","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":2,"textOverflow":"ellipsis","fontColor":"#99000000"},"content":"This action cannot be undone."}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"main","components":[{"id":"confirm_actions","component":"Extended.Row","children":["cancel_btn","confirm_btn"],"space":8,"styles":{"width":"matchParent","justifyContent":"center","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"main","components":[{"id":"cancel_btn","component":"Extended.Button","enabled":true,"styles":{"height":28,"borderRadius":14,"fontSize":14,"fontWeight":400,"backgroundColor":"#0C000000"},"label":"Cancel"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"main","components":[{"id":"confirm_btn","component":"Extended.Button","enabled":true,"styles":{"height":40,"borderRadius":20,"fontSize":16,"fontWeight":500,"backgroundColor":"#FF0A59F7"},"label":"Delete"}]}}
```

## Form Modal (Edit Profile)

An edit dialog with form fields.

```jsonl
{"version":"v0.9","createSurface":{"surfaceId":"profile","catalogId":"https://xxx/specification/ohos/extended_catalog.json","theme":{"primaryColor":"#FF0A59F7"}}}
{"version":"v0.9","updateComponents":{"surfaceId":"profile","components":[{"id":"root","component":"Extended.Column","children":["profile_card","edit_if"],"space":12,"styles":{"width":"matchParent","constraintSize":{"maxWidth":336},"borderRadius":16,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"profile","components":[{"id":"profile_card","component":"Extended.Column","children":["profile_content"],"space":8,"styles":{"width":"matchParent"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"profile","components":[{"id":"profile_content","component":"Extended.Row","children":["info_column","edit_trigger"],"space":12,"styles":{"width":"matchParent","justifyContent":"spaceBetween","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"profile","components":[{"id":"info_column","component":"Extended.Column","children":["user_name","user_email"],"space":4,"styles":{"width":"matchParent"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"profile","components":[{"id":"user_name","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"John Doe"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"profile","components":[{"id":"user_email","component":"Extended.Text","styles":{"fontSize":12,"fontWeight":"400","maxLines":1,"textOverflow":"ellipsis","fontColor":"#66000000"},"content":"john@example.com"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"profile","components":[{"id":"edit_trigger","component":"Extended.Button","enabled":true,"styles":{"height":28,"borderRadius":14,"fontSize":14,"fontWeight":400,"backgroundColor":"#0C000000"},"label":"Edit"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"profile","components":[{"id":"edit_if","component":"Extended.If","condition":true,"childrenIf":["edit_form"],"childrenElse":[],"styles":{}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"profile","components":[{"id":"edit_form","component":"Extended.Column","children":["edit_title","name_field","email_field","edit_actions"],"space":12,"styles":{"width":"matchParent","alignItems":"top","padding":{"top":8,"right":0,"bottom":8,"left":0}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"profile","components":[{"id":"edit_title","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000","margin":{"bottom":4}},"content":"Edit Profile"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"profile","components":[{"id":"name_field","component":"Extended.TextInput","enabled":true,"maxLength":80,"type":"normal","styles":{"width":"matchParent","height":56,"borderRadius":20,"backgroundColor":"#0C000000","padding":{"top":16,"right":16,"bottom":16,"left":16},"fontSize":16,"fontWeight":400,"fontColor":"#E5000000","placeholderColor":"#99000000","caretColor":"#FF0A59F7","showUnderline":false},"placeholder":"Display Name","text":{"path":"/profile/name"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"profile","path":"/profile","value":{"name":"","email":""}}}
{"version":"v0.9","updateComponents":{"surfaceId":"profile","components":[{"id":"email_field","component":"Extended.TextInput","enabled":true,"maxLength":120,"type":"email","styles":{"width":"matchParent","height":56,"borderRadius":20,"backgroundColor":"#0C000000","padding":{"top":16,"right":16,"bottom":16,"left":16},"fontSize":16,"fontWeight":400,"fontColor":"#E5000000","placeholderColor":"#99000000","caretColor":"#FF0A59F7","showUnderline":false},"placeholder":"Email","text":{"path":"/profile/email"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"profile","components":[{"id":"edit_actions","component":"Extended.Row","children":["discard_btn","save_btn"],"space":8,"styles":{"width":"matchParent","justifyContent":"end","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"profile","components":[{"id":"discard_btn","component":"Extended.Button","enabled":true,"styles":{"height":28,"borderRadius":14,"fontSize":14,"fontWeight":400,"backgroundColor":"#0C000000"},"label":"Cancel"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"profile","components":[{"id":"save_btn","component":"Extended.Button","enabled":true,"styles":{"height":40,"borderRadius":20,"fontSize":16,"fontWeight":500,"backgroundColor":"#FF0A59F7"},"label":"Save Changes"}]}}
```

## Key Design Patterns

1. **Shell**（`harmony-card-spec.md` **A4**）：对话框外框圆角 **16vp**，底板 **`#FFFFFFFF`**，**`maxWidth` 336**，内边距 **12vp**；`theme.primaryColor` **`#FF0A59F7`**。
2. **层次**：标题 **`fontColor` `#E5000000`**，说明 **`#99000000`**；`Extended.Text` 在密排区须显式着色。
3. **主按钮**（`quick-snippets` §7b / **B1**）：**height 40**、**borderRadius 20**、**`#FF0A59F7`**。
4. **次按钮 / 列表小按钮**（**A4.1**）：**height 28**、**borderRadius 14**、**fontSize 14**，弱底 **`#0C000000`**。
5. **表单类**：内容左对齐，行尾动作区右对齐（`Row` + `justifyContent":"end"`）。
