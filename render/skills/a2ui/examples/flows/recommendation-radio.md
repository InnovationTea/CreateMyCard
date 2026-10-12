# 我的推荐：互斥多选一 → `Extended.Radio`（Few-shot）

**先看这一条（与完整菜单同屏时）**：下面 NDJSON 只教 **「我的推荐」+ Radio 段** 的形状，**不**表示整张卡片只有这一块。若素材里在「我的推荐」**之上**还有门店行、**「人气热卖 / 新品 / 超值…」** 等分区与价目，必须在**同一** `root` 的 `children` 里为它们各建 id（`Extended.Text` 或行布局），**排在 Radio 区之前**。**不得**为省事只输出本片段、省略前文——见 [`SKILL.md`](../../SKILL.md) **交互增强**「全文保真」与 **Hard Constraint 15**。

当对话/素材里出现**小结式推荐**（如 **「💡 我的推荐」**），且下列是 **2 条及以上互斥候选项**（带 SKU/价格/标签），**不要**把**该小结**压成**一条**长 `Extended.Text`；应使用 **同一 `group` 的多个 `Extended.Radio`**，让用户在卡片内直接点选。段落标题/场景句（如「如果你想尝鲜：」）仍用 **`Extended.Text`** 放在对应 Radio 上方。

**典型反面 A**：小结区只有长文本、无可点选项。
**典型反面 B（禁止）**：只渲染本 Few-shot，把上面的**整段菜单/分区**删掉。
**推荐做法**：菜单全文 `Text` + 小结区 Radio；收尾文案**点选导向**（如「点选上列一种套餐…」），与交互一致。

**参考**：[`reference/design/interaction-design.md`](../../reference/design/interaction-design.md)（同组件 JSONL 片段）；[`reference/protocol/extended-ui-schema.md`](../../reference/protocol/extended-ui-schema.md) `Extended.Radio`。

---

## NDJSON 示例（`surfaceId`: `meal_recommend`）

每行一个 `updateComponents`，`components` 仅含 **一个** 组件。以下为**仅含推荐段**的**片段**；**合并进完整卡片**时，请把实作中的 `root` 的 `children` 写为：
`[ … 各分区 Text 节点 id … , "rec_title", "opt1_caption", "r1", … , "foot_hint", "confirm_btn" ]`（**前半**为全量只读内容，**中间**为 Radio 区，**末尾**为说明文 + **主按钮**）。

```jsonl
{"version":"v0.9","createSurface":{"surfaceId":"meal_recommend","catalogId":"https://xxx/specification/ohos/extended_catalog.json","theme":{"primaryColor":"#FF0A59F7"}}}
{"version":"v0.9","updateComponents":{"surfaceId":"meal_recommend","components":[{"id":"root","component":"Extended.Column","children":["rec_title","opt1_caption","r1","opt2_caption","r2","opt3_caption","r3","foot_hint","confirm_btn"],"space":10,"styles":{"width":"matchParent","constraintSize":{"maxWidth":336},"borderRadius":16,"clip":true,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"meal_recommend","components":[{"id":"rec_title","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"600","maxLines":2,"fontColor":"#E5000000"},"content":"💡 我的推荐"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"meal_recommend","components":[{"id":"opt1_caption","component":"Extended.Text","styles":{"fontSize":12,"fontWeight":"400","fontColor":"#99000000","maxLines":1},"content":"如果你想吃得饱又划算："}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"meal_recommend","components":[{"id":"r1","component":"Extended.Radio","group":"my_recommend","indicatorType":"dot","styles":{"checkedBackgroundColor":"#1A0A59F7","uncheckedBorderColor":"#19000000","indicatorColor":"#FF0A59F7"},"value":"9900012439 培根芝士双牛堡大堡口福三件套 ￥23.9 ⭐ 性价比最高","checked":true}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"meal_recommend","components":[{"id":"opt2_caption","component":"Extended.Text","styles":{"fontSize":12,"fontWeight":"400","fontColor":"#99000000","maxLines":1},"content":"如果你想尝鲜："}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"meal_recommend","components":[{"id":"r2","component":"Extended.Radio","group":"my_recommend","indicatorType":"dot","styles":{"checkedBackgroundColor":"#1A0A59F7","uncheckedBorderColor":"#19000000","indicatorColor":"#FF0A59F7"},"value":"9900013819 芝士嘿凤梨板烧鸡腿堡三件套 ￥29.9 🍍 凤梨+芝士新口味","checked":false}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"meal_recommend","components":[{"id":"opt3_caption","component":"Extended.Text","styles":{"fontSize":12,"fontWeight":"400","fontColor":"#99000000","maxLines":1},"content":"如果你在减脂："}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"meal_recommend","components":[{"id":"r3","component":"Extended.Radio","group":"my_recommend","indicatorType":"dot","styles":{"checkedBackgroundColor":"#1A0A59F7","uncheckedBorderColor":"#19000000","indicatorColor":"#FF0A59F7"},"value":"9900011123 辣么快乐套餐 ￥24 🥗 约500大卡","checked":false}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"meal_recommend","components":[{"id":"foot_hint","component":"Extended.Text","styles":{"fontSize":12,"fontWeight":"400","fontColor":"#99000000","maxLines":2},"content":"点选一种套餐后，点「确认选择」将选项提交；无需在对话里手打餐品编号。"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"meal_recommend","components":[{"id":"confirm_btn","component":"Extended.Button","enabled":true,"styles":{"width":"matchParent","height":40,"borderRadius":20,"fontSize":16,"fontWeight":500,"backgroundColor":"#FF0A59F7"},"action":{"event":{"name":"submit_form","context":{"selectedMeal":{"call":"getSelectedValues","args":{"groupID":"my_recommend"}}}}},"label":"确认选择"}]}}
```

**说明**：

- 三个 `Extended.Radio` 共享 **`group": "my_recommend"`**，互斥单选。宿主实现中，**`value`** 会作为**可见标签**与表单值，故把 **SKU + 名称 + 价格 + 短标签** 写进 `value`（与 `interaction-design` 中套餐示例一致）。
- **主按钮上送（默认需要）**：`confirm_btn` 使用 **`action.event.name": "submit_form"`**，`context` 中通过 **`getSelectedValues`** + **`groupID": "my_recommend"`** 回传**当前** Radio 选择（与三个 `Extended.Radio` 的 **`group` 一致**）。在用户**点击**时由宿主向 Agent 上送；**仅点选 Radio 不会**在默认流里触发 `submit_form`（见 [`reference/protocol/extended-interactions.md`](../../reference/protocol/extended-interactions.md)）。若另有 **`TextInput`** 等，再叠加 **`{"path":"/…"}`**（见 [`reference/protocol/schema.md`](../../reference/protocol/schema.md)）。
- 将绑定的已选值同步进数据模型**且**在确认时解析进 **`submit_form`**，见上链；勿省略本按钮，除非产品约定「选完即上送」。
- **不得**因本例只有 `rec_title` 起子树，就在真实输出里省略同一来源中 **Radio 段之前的** 全部 `Extended.Text` 节点（**全文保真**）。
