# Interaction Design

交互增强，当用户需要填写信息、选择时，优先使用交互性组件（**Extended.TextInput**、**Extended.Toggle**、**Extended.Radio**、**Extended.Checkbox**、**Extended.CheckboxGroup**、**Extended.Select**）来替换普通的长段纯文本，增强交互体验。

## Interaction Components

下面是可以选择的交互组件；**详细 props / `styles` 以协议为准**：[`extended-ui-schema.md`](../protocol/extended-ui-schema.md) 中对应 **Extended.*** 节。

- **`Extended.TextInput`**：单行/受控输入；用于**无法被选项穷举**的自由文本（姓名、电话、备注、邮箱等）。**`text` 必须为** `{"path":"…"}`**（**禁止**字符串字面量作当前值）**；初值/空值用 **`updateDataModel`**。另见协议 **`placeholder`**、**`type`**（`normal` | `email` | `password` | `number`）。字段顺序与可复制片段见 [`quick-snippets.md`](quick-snippets.md) **§4** 与主 [`SKILL.md`](../../SKILL.md) **§0**。

- **`Extended.Toggle`**：滑块式二态开关；适合**整页设置/偏好**等「开/关」语义（如通知、功能开关）。关键字段 **`isOn`**、**`enabled`**、**`styles.selectedColor` / `unSelectedColor` / `switchPointColor`**（`unSelectedColor` 为协议字段名，与 Checkbox 的 `unselectedColor` 不同）。与 **`Extended.Checkbox`** 的边界：单条**条款/同意/确认**用 **Checkbox**；偏「系统设置感」的开关用 **Toggle**。

- **`Extended.Radio`**：互斥单选；2 个及以上**并列、只能选一**的候选项。同题共享 **`group`**。关键字段 **`value`**、**`checked`**、**`group`**。参考实现里常将 **`value` 同时作为展示文案**。

- **`Extended.Checkbox`**：单个布尔；协议 **`select`** 表示选中。`group` 在参考实现中常作**紧挨复选框的可见标签**（如同意条款整句）。适合**一条**是/否或同意类语义。

- **`Extended.CheckboxGroup`**：成组**全选/取消全选**；协议 **`selectAll`**。适合「多项可选 + 一屏全选头」的区块（见协议与宿主行为）。

- **`Extended.Select`**：下拉单选；**`options[]`** 每项含 **`value`**（及可选 `icon` 等），**`selected`** 为当前下标，**`value`** 为摘要/可访问名称。当候选项**较多**或要**省纵向版面**时优先于平铺多枚 **Radio**；**少而需并排通览对比**时仍用 **Radio**。

## 交互组件的选择原则

`Extended.Text` 适合说明、展示与阅读；**不承载「选中/提交」状态**。在对话里，若已具备**输入或选项结构**（自由输入、互斥、多选、全选、开关、下拉等），应优先用上表中的 **`Extended.*` 交互组件**，让用户**少打字、少误选**。

与「默认不过度使用表单控件」不矛盾：仍是 **无结构化的纯说明 → `Extended.Text`**；**需要采集中间状态、选项或结果 → 对应交互组件**。

**全文保真（重要）**：交互组件是对**局部**的增强，**不**以「只渲染交互区」替代整段素材。若同一输入里**前面**还有分区标题、价目/列表、说明段落等，仍须用 `Extended.Text`（及合适的 `Row`/`Column`）**原样出齐**；**同一** `root` 的 `children` 中，通常 **先** 只读区、**后** 小结 + 可点选/可输入区。**禁止**为套用 Few-shot 而删掉上游 `Extended.Text`。

---

### 与 `Extended.Text` 的取舍

| 情况 | 更合适的组件 |
|------|----------------|
| 仅说明背景、价格描述、无强引导的选项或输入 | `Extended.Text`（可分段、列表排版） |
| 需用户**键入**不可穷举的文本（电话、地址、留言等） | **`Extended.TextInput`**（`type` / `maxLength` 见协议；`text` / `updateDataModel` 见 [`schema.md`](../protocol/schema.md)、[`SKILL.md`](../../SKILL.md) **§0**） |
| 整页或区块级**开/关**（偏好/设置感） | **`Extended.Toggle`**；单条**同意条款/是否加购**等仍多用 **`Extended.Checkbox`** |
| 多个**互斥**候选项、且以平铺**可见对比**为主 | 同组多个 **`Extended.Radio`**（共享 `group`） |
| 多选一但**候选项多**、或要**收敛纵向占位** | **`Extended.Select`**；少而平铺更清晰的仍用 **Radio** |
| 单条是/否、单句同意、单个布尔项 | `Extended.Checkbox` |
| 多个**可叠加**的独立项，或需要**「全选/取消全选」** | `Extended.CheckboxGroup`（`selectAll` 等见协议） |

---

## `Extended.TextInput`：自由输入

**适用**：需要用户**键入**具体字符串，且**无法用固定 `Radio`/`Select` 选项**覆盖时（如联系人、地址、数字编码等）。

- **`type`** 选用 `email` / `password` / `number` 时须与业务一致；`maxLength` 可约束长度。
- **鸿蒙/DSL 习惯**：`styles` 与能力字段在前，**`placeholder` / `text` 置后**（与 [`quick-snippets.md`](quick-snippets.md) **§4** 及主 `SKILL.md` **Field ordering** 一致）。**`text` 须为** `{"path":"…"}`**；同 `surfaceId` 下按 §0 紧跟 **`updateDataModel`** 尾帧写入初值。

协议与字段：见 [`extended-ui-schema.md`](../protocol/extended-ui-schema.md) 中 **`Extended.TextInput`** 一节。

---

## `Extended.Toggle`：二态开关

**适用**：**设置类**、**成对开/关**的布尔状态（如是否接收营销通知、某功能总开关），且 UI 为**滑块**而非方框打勾时。

- **`isOn`** 为初态；**`enabled: false`** 为禁用。样式三色轨与滑点见协议 **`styles`**。

**与 `Extended.Checkbox` 的区分**：**条款/协议/单条确认**用 **Checkbox**；偏「首选项/设备式」开关用 **Toggle**（同一问题域不要两种混用，以免用户困惑）。

协议字段：见 [`extended-ui-schema.md`](../protocol/extended-ui-schema.md)（**Extended.Toggle**）。

**示例意图**：与标签同排 **`Extended.Row`**（左 `Extended.Text` 说明、右 `Toggle`），避免开关脱离语义单独出现。

---

## `Extended.Radio`：互斥单选

**适用**：助手已经列出 2 个及以上并列选项，且用户**只能选一个**（例如不同套餐、档位、时间槽）。

- 同一题内所有候选项使用**相同的 `group`** 字符串，使宿主表现为单选组。
- 每个单选项的 **`value`** 建议承载机器可读标识（如商品 ID、选项 key），`checked` 表示当前是否选中；初始可只将一项设为 `true` 或配合数据模型用 `path` 绑定（见 `schema.md`、`SKILL.md` **§0**）。
- **版式**：每个选项可旁边仍用 `Extended.Text` 展示名称、价签、角标，与 `Radio` 放在 `Row`/`Column` 中；核心是可点的选择与明确的 `value`。

**示例意图**（对应「请告诉我你想选哪个套餐，我可帮你算总价并准备下单信息」类话术）：把三条套餐从一整段 `Extended.Text` 改为三条「Radio + 说明文案」或「可点击行」，用户**点击即选中**，无需在输入框里输入 SKU 或口头复述。

协议字段：`value`、`checked`、`group`、`indicatorType`（`tick` | `dot`）等见 [`extended-ui-schema.md`](../protocol/extended-ui-schema.md) 文内 **Extended.Radio** 一节。

---

### `Extended.Checkbox`：独立布尔

**适用**：单个勾选框——同意协议、加入可选加购、是否开发票等。

- 使用 `group` 区分问题域；`select` 为是否选中。支持与 `/form/...` 的 `path` 绑定（见 `schema.md`、`examples/flows/form.md`）。

---

### `Extended.CheckboxGroup`：成组多选 / 全选

**适用**：需要**多选**且项之间**不互斥**；或一屏内要提供 **「全选 / 反选」** 与多枚勾选项的联动时（协议提供 `selectAll`）。

- 子选项仍用与组一致的 `group` 标识（具体以宿主与 catalog 实现为准；schema 中 `Extended.CheckboxGroup` 为独立容器型控件）。
- 与 `Radio` 的区分：Radio = **最多一个**；CheckboxGroup 场景 = **可多个** 或 **全选语义**。

---

## `Extended.Select`：下拉单选

**适用**：**互斥单选**且候选项**较多**、或需要**少占纵向空间**的输入（如城市、区、仓库）。**少而需要一眼扫全表对比**的仍用 **`Extended.Radio`** 平铺。

- **`options`** 为项列表，每项至少 **`value`**（展示与取值）；**`selected`** 为当前选中**下标**；**`value`** 可作文案摘要或旁路可访问名（以宿主与协议为准）。详见 [`extended-ui-schema.md`](../protocol/extended-ui-schema.md) 中 **Extended.Select**。

---

### 与后续操作衔接

- 用户操作 **`Extended.TextInput` / `Extended.Toggle` / `Extended.Radio` / `Extended.Checkbox` / `Extended.Select`** 等后，值应能进入**数据模型**（`updateDataModel` + JSON Pointer，若宿主支持绑定），供后续上报使用；**`Toggle`** 在部分宿主上仅驻留本地，是否写入模型以 **`schema.md` / 宿主实现**为准。

- **上送 Agent / 后端**：在默认协议中，**`submit_form` 需由带 `action` 的控件触发**（见 [`extended-interactions.md`](../protocol/extended-interactions.md)）。**仅改选控件**一般会更新界面或本地状态，**不会自动**向服务端发出 `submit_form`，除非宿主单独做了「变更即上送」的定制。需要把**整卡结果作为一次正式提交**时，应在交互区**下方**放一枚 **主 `Extended.Button`**，配置 `action.event`：`name` 为 **`submit_form`**，**`context` 中按字段**使用 **`{"path":"/…"}`**（与 `TextInput` / `updateDataModel` 一致）、**`getSelectedValues` + 与 `Extended.Radio` 相同的 `groupID`**、以及**非交互**稳定 id 的**字面量**；**不要**用 **`intent` + 长说明**代替这些绑定。参考实现上送为完整 **client→server** 消息（含 `surfaceId` / `sourceComponentId` / `timestamp` / 解析后的 `context`），见 `genui-sdk/interactions`。

- 主按钮文案示例：「确认选择」「确定」「提交」；**避免**只依赖用户再在对话里打字复述已选内容。

---

### 字段顺序（流式与可读）

生成组件对象时，遵循本 skill 的 **「结构/样式优先，数据靠后」**：例如 **`Extended.Checkbox`** 为 `group` / `styles` 在前，`select` 在最后（见主 `SKILL.md` § **Field ordering**）。**`Extended.TextInput`** 宜 `enabled` / `type` / `maxLength` / `styles` 在前，`placeholder` / `text` 在后；**`text` 仅** `{"path":"…"}`。 **`Radio`** 保持 `group`、展示相关样式、再 `value` / `checked`；**`Select`** 将 **`options` / `selected` / `value`** 中偏「数据面」的字段置后（与主 skill 的 ordering 表一致时优先）。

---

## 示例（JSONL v0.9）

本仓库 **参考实现** 中（`genui-sdk`）：`Extended.Radio` 将 **`value` 同时作为展示文案**；`Extended.Checkbox` 将 **`group` 作为紧挨复选框的展示文案**；`Extended.CheckboxGroup` 为带 **`group` 作标题/legend** 的 **「全选」** 控件，不会在树内再展开多枚子 `Checkbox`；**`Extended.TextInput`** 与 **`Extended.Select`** 为常见表单控；**`Extended.Toggle`** 为自洽局部开关（是否与全局 **`form`/`formValues` 联动** 取决于宿主注入）。下述为可直接对照的 NDJSON 片段。

### `Extended.Toggle` + 标签：开关行（`Extended.Row`）

```jsonl
{"version":"v0.9","createSurface":{"surfaceId":"demo_toggle","catalogId":"https://xxx/specification/ohos/extended_catalog.json","theme":{"primaryColor":"#FF0A59F7"}}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_toggle","components":[{"id":"root","component":"Extended.Column","children":["toggle_row"],"space":0,"styles":{"width":"matchParent","constraintSize":{"maxWidth":336},"borderRadius":16,"clip":true,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_toggle","components":[{"id":"toggle_row","component":"Extended.Row","children":["toggle_label","toggle_switch"],"space":8,"styles":{"width":"matchParent","justifyContent":"spaceBetween","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_toggle","components":[{"id":"toggle_label","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"500","maxLines":1,"fontColor":"#E5000000"},"content":"消息推送"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_toggle","components":[{"id":"toggle_switch","component":"Extended.Toggle","isOn":true,"enabled":true,"styles":{"selectedColor":"#FF0A59F7","unSelectedColor":"#19000000","switchPointColor":"#FFFFFF"}}]}}
```

### `Extended.TextInput`：单行输入

完整字段顺序与 `styles` 见 [`quick-snippets.md`](quick-snippets.md) **§4**；此处为与上文卡片风格一致的最小例。

```jsonl
{"version":"v0.9","createSurface":{"surfaceId":"demo_ti","catalogId":"https://xxx/specification/ohos/extended_catalog.json","theme":{"primaryColor":"#FF0A59F7"}}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_ti","components":[{"id":"root","component":"Extended.Column","children":["field_note"],"space":0,"styles":{"width":"matchParent","constraintSize":{"maxWidth":336},"borderRadius":16,"clip":true,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_ti","components":[{"id":"field_note","component":"Extended.TextInput","enabled":true,"maxLength":80,"type":"normal","styles":{"width":"matchParent","height":56,"borderRadius":20,"backgroundColor":"#0C000000","padding":{"top":16,"right":16,"bottom":16,"left":16},"fontSize":16,"fontWeight":400,"fontColor":"#E5000000","placeholderColor":"#99000000","caretColor":"#FF0A59F7","showUnderline":false},"placeholder":"备注（选填）","text":{"path":"/demoTi/note"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"demo_ti","path":"/demoTi/note","value":""}}
```

### `Extended.Select`：三选一区域

```jsonl
{"version":"v0.9","createSurface":{"surfaceId":"demo_sel","catalogId":"https://xxx/specification/ohos/extended_catalog.json","theme":{"primaryColor":"#FF0A59F7"}}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_sel","components":[{"id":"root","component":"Extended.Column","children":["district_select"],"space":0,"styles":{"width":"matchParent","constraintSize":{"maxWidth":336},"borderRadius":16,"clip":true,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_sel","components":[{"id":"district_select","component":"Extended.Select","options":[{"value":"朝阳区"},{"value":"海淀区"},{"value":"丰台区"}],"selected":0,"value":"配送区域","styles":{"fontColor":"#E5000000","optionBgColor":"#FFFFFFFF","menuBackgroundColor":"#FFFFFFFF","selectedOptionBgColor":"#1A0A59F7","selectedOptionFontColor":"#FF0A59F7"}}]}}
```

### `Extended.Radio`：互斥三选一（套餐 / SKU）

```jsonl
{"version":"v0.9","createSurface":{"surfaceId":"demo_radio","catalogId":"https://xxx/specification/ohos/extended_catalog.json","theme":{"primaryColor":"#FF0A59F7"}}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_radio","components":[{"id":"root","component":"Extended.Column","children":["hint","r1","r2","r3"],"space":8,"styles":{"width":"matchParent","constraintSize":{"maxWidth":336},"borderRadius":16,"clip":true,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_radio","components":[{"id":"hint","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"500","maxLines":3,"fontColor":"#E5000000"},"content":"请选一个套餐，可直接点击选项，无需再输入编号。"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_radio","components":[{"id":"r1","component":"Extended.Radio","group":"meal_plan","indicatorType":"dot","styles":{"checkedBackgroundColor":"#1A0A59F7","uncheckedBorderColor":"#33000000","indicatorColor":"#FF0A59F7"},"value":"9900012439 培根芝士双牛堡三件套 ￥23.9","checked":true}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_radio","components":[{"id":"r2","component":"Extended.Radio","group":"meal_plan","indicatorType":"dot","styles":{"checkedBackgroundColor":"#1A0A59F7","uncheckedBorderColor":"#33000000","indicatorColor":"#FF0A59F7"},"value":"9900013819 芝士嘿凤梨三件套 ￥29.9","checked":false}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_radio","components":[{"id":"r3","component":"Extended.Radio","group":"meal_plan","indicatorType":"dot","styles":{"checkedBackgroundColor":"#1A0A59F7","uncheckedBorderColor":"#33000000","indicatorColor":"#FF0A59F7"},"value":"9900011123 辣么快乐套餐 ￥24","checked":false}]}}
```

### `Extended.Checkbox`：单条布尔（同意类）

`group` 在参考实现中即**可见标签**，可写完整一句；`group` / `styles` 在前，`select` 在后。

```jsonl
{"version":"v0.9","createSurface":{"surfaceId":"demo_check","catalogId":"https://xxx/specification/ohos/extended_catalog.json","theme":{"primaryColor":"#FF0A59F7"}}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_check","components":[{"id":"root","component":"Extended.Column","children":["agree_check"],"space":0,"styles":{"width":"matchParent","constraintSize":{"maxWidth":336},"borderRadius":16,"clip":true,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_check","components":[{"id":"agree_check","component":"Extended.Checkbox","group":"已阅读并同意《用户协议》与《隐私政策》","styles":{"shape":"rounded_square","selectedColor":"#FF0A59F7","unselectedColor":"#33000000","mark":{"strokeColor":"#FFFFFF","size":12,"strokeWidth":2}},"select":false}]}}
```

### `Extended.CheckboxGroup`：带标题的「全选」

```jsonl
{"version":"v0.9","createSurface":{"surfaceId":"demo_cbg","catalogId":"https://xxx/specification/ohos/extended_catalog.json","theme":{"primaryColor":"#FF0A59F7"}}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_cbg","components":[{"id":"root","component":"Extended.Column","children":["addon_group","note"],"space":8,"styles":{"width":"matchParent","constraintSize":{"maxWidth":336},"borderRadius":16,"clip":true,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_cbg","components":[{"id":"addon_group","component":"Extended.CheckboxGroup","group":"可选加购（示例）","selectAll":false,"styles":{"selectedColor":"#FF0A59F7","unselectedColor":"#33000000","mark":{"strokeColor":"#FFFFFF","size":12,"strokeWidth":2},"checkboxShape":"rounded_square"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_cbg","components":[{"id":"note","component":"Extended.Text","styles":{"fontSize":12,"fontColor":"#99000000","maxLines":2},"content":"成组多选时，可在同卡片内再排多个 Extended.Checkbox；全选与具体项是否联动取决于宿主/数据模型。"}]}}
```

### 总示例：六类交互 + `submit_form` 主按钮

**意图**：**同一** `surfaceId` 下，自上而下依次包含 **TextInput → Toggle（Row）→ Radio（2）→ Checkbox → CheckboxGroup → Select → 主按钮**。仅选/改中间控件**不会**在默认流里上送，需用户点击**「提交本页信息」**触发 **`action.event`：`submit_form`**；`context` 中示例使用 **`path`**（与 **`field_nickname`** 绑定一致）+ **`getSelectedValues`**（与 Radio **`group": "demo_meal"`** 一致），不用 **`intent`/`value` 长文案**代替。详见 [`schema.md`](../protocol/schema.md)、[`SKILL.md`](../../SKILL.md) **§0** 与 [`extended-interactions.md`](../protocol/extended-interactions.md)。

```jsonl
{"version":"v0.9","createSurface":{"surfaceId":"demo_all_six","catalogId":"https://xxx/specification/ohos/extended_catalog.json","theme":{"primaryColor":"#FF0A59F7"}}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_all_six","components":[{"id":"root","component":"Extended.Column","children":["page_title","page_hint","label_nick","field_nickname","toggle_row","sec_radio","r1","r2","agree_check","addon_group","sec_select","district_select","foot_hint","submit_btn"],"space":10,"styles":{"width":"matchParent","constraintSize":{"maxWidth":336},"borderRadius":16,"clip":true,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_all_six","components":[{"id":"page_title","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"600","maxLines":2,"fontColor":"#E5000000"},"content":"本页总示例：六类交互组件"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_all_six","components":[{"id":"page_hint","component":"Extended.Text","styles":{"fontSize":12,"fontWeight":"400","fontColor":"#66000000","maxLines":3},"content":"以下依次为：单行输入、开关、互斥二选一、单条同意、全选加购、下拉区域，最后点击提交上送。"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_all_six","components":[{"id":"label_nick","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"500","maxLines":1,"fontColor":"#E5000000"},"content":"称呼（TextInput）"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_all_six","components":[{"id":"field_nickname","component":"Extended.TextInput","enabled":true,"maxLength":32,"type":"normal","styles":{"width":"matchParent","height":56,"borderRadius":20,"backgroundColor":"#0C000000","padding":{"top":16,"right":16,"bottom":16,"left":16},"fontSize":16,"fontWeight":400,"fontColor":"#E5000000","placeholderColor":"#99000000","caretColor":"#FF0A59F7","showUnderline":false},"placeholder":"怎么称呼您","text":{"path":"/demoAllSix/nickname"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"demo_all_six","path":"/demoAllSix/nickname","value":""}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_all_six","components":[{"id":"toggle_row","component":"Extended.Row","children":["toggle_label","toggle_push"],"space":8,"styles":{"width":"matchParent","justifyContent":"spaceBetween","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_all_six","components":[{"id":"toggle_label","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"500","maxLines":1,"fontColor":"#E5000000"},"content":"接收订单通知（Toggle）"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_all_six","components":[{"id":"toggle_push","component":"Extended.Toggle","isOn":true,"enabled":true,"styles":{"selectedColor":"#FF0A59F7","unSelectedColor":"#19000000","switchPointColor":"#FFFFFF"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_all_six","components":[{"id":"sec_radio","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"500","maxLines":1,"fontColor":"#E5000000","margin":{"top":4,"bottom":0}},"content":"餐型（Radio，二选一）"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_all_six","components":[{"id":"r1","component":"Extended.Radio","group":"demo_meal","indicatorType":"dot","styles":{"checkedBackgroundColor":"#1A0A59F7","uncheckedBorderColor":"#33000000","indicatorColor":"#FF0A59F7"},"value":"标配套餐 A","checked":true}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_all_six","components":[{"id":"r2","component":"Extended.Radio","group":"demo_meal","indicatorType":"dot","styles":{"checkedBackgroundColor":"#1A0A59F7","uncheckedBorderColor":"#33000000","indicatorColor":"#FF0A59F7"},"value":"大份套餐 B","checked":false}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_all_six","components":[{"id":"agree_check","component":"Extended.Checkbox","group":"已阅读本页说明并同意按选项处理（Checkbox）","styles":{"shape":"rounded_square","selectedColor":"#FF0A59F7","unselectedColor":"#33000000","mark":{"strokeColor":"#FFFFFF","size":12,"strokeWidth":2}},"select":false}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_all_six","components":[{"id":"addon_group","component":"Extended.CheckboxGroup","group":"可选加购全选区（CheckboxGroup）","selectAll":false,"styles":{"selectedColor":"#FF0A59F7","unselectedColor":"#33000000","mark":{"strokeColor":"#FFFFFF","size":12,"strokeWidth":2},"checkboxShape":"rounded_square"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_all_six","components":[{"id":"sec_select","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"500","maxLines":1,"fontColor":"#E5000000","margin":{"top":4,"bottom":0}},"content":"配送区（Select）"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_all_six","components":[{"id":"district_select","component":"Extended.Select","options":[{"value":"东片区"},{"value":"西片区"},{"value":"南片区"}],"selected":0,"value":"请选择配送区","styles":{"fontColor":"#E5000000","optionBgColor":"#FFFFFFFF","menuBackgroundColor":"#FFFFFFFF","selectedOptionBgColor":"#1A0A59F7","selectedOptionFontColor":"#FF0A59F7"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_all_six","components":[{"id":"foot_hint","component":"Extended.Text","styles":{"fontSize":12,"fontWeight":"400","fontColor":"#66000000","maxLines":2},"content":"点「提交本页信息」后由宿主上送 submit_form；仅改选组件通常不会自动提交。"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_all_six","components":[{"id":"submit_btn","component":"Extended.Button","enabled":true,"styles":{"width":"matchParent","height":40,"borderRadius":20,"fontSize":16,"fontWeight":500,"backgroundColor":"#FF0A59F7"},"action":{"event":{"name":"submit_form","context":{"nickname":{"path":"/demoAllSix/nickname"},"mealSelection":{"call":"getSelectedValues","args":{"groupID":"demo_meal"}}}}},"label":"提交本页信息"}]}}
```

---

## 另见

- **同场景 Few-shot（我的推荐 + 小标题 + 三 Radio）**：[`../../examples/flows/recommendation-radio.md`](../../examples/flows/recommendation-radio.md)
- **速用 JSON 片段（含 TextInput §4）**：[`quick-snippets.md`](quick-snippets.md)
- 组件形态与 `styles`：[`../protocol/extended-ui-schema.md`](../protocol/extended-ui-schema.md)
- 路径绑定与 `updateDataModel`：[`../protocol/schema.md`](../protocol/schema.md)、[`SKILL.md`](../../SKILL.md) **§0**
- 表单上送：[`../protocol/extended-interactions.md`](../protocol/extended-interactions.md)
