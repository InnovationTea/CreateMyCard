# A2UI JSON Input Example — Product compact card (Dialog Card)



This example demonstrates **Mode A (Render / Present)** with **structured JSON**: every payload-backed field—including **`actions[].label`** and the full **`actions`** entries (so **`style`** is not dropped)—uses **`{"path":"..."}`** plus an **`updateDataModel` line immediately after** the `updateComponents` that introduces that binding ([**`SKILL.md`**](../../../SKILL.md) §0 / **HC 14**). **Do not** omit keys from the input object; **do not** invent fields or copy that are not in the JSON.



## Input (JSON)



```json

{
  "title": "MacBook Pro 14\"",
  "subtitle": "M4 Pro · 18GB · 512GB",
  "price": "¥14,999",
  "priceNote": "券后预计 ¥13,999",
  "badge": "新品",
  "imageUrl": "https://picsum.photos/seed/mbp14/480/480",
  "actions": [
    { "label": "加入购物车", "style": "primary" },
    { "label": "收藏", "style": "secondary" }
  ]
}

```



## Mapping notes



- **Page Type**: Dialog / compact card; `maxLines` + `ellipsis` on titles.

- **Data**: one **`updateDataModel` per introducing `updateComponents` line** (same `surfaceId`, next NDJSON line). Pointers mirror the input object (`/title`, `/actions/0/label`, …).

- **`actions`**: first button binds **`/actions/0/label`**; the tail line writes the **entire `/actions` array** from the input (each object’s **`label`** + **`style`**—与输入逐字一致). Second button binds **`/actions/1/label`**; the tail line writes **`/actions/1`** 整项（`label` + `style`），满足 §0「绑定行后紧跟 `updateDataModel`」且不省略 **`style`**。**`Extended.Button` 的 `styles`** 为鸿蒙对 **`primary` / `secondary`** 的固定视觉映射，不新增输入中不存在的 token。下述 hex 均为 **Light** 下语义 token 展开示例（见 `harmony-design-token.md`）：如 `font_emphasize`→`#FF0A59F7`、`warning`→`#FFE84026`、`comp_emphasize_tertiary`→`#190A59F7`、`brand20` 描边→`#330A59F7`、`background_emphasize` 主按钮底→`#FF0A59F7`。



## Output (A2UI v0.9 NDJSON)



```jsonl
{"version":"v0.9","createSurface":{"surfaceId":"json_product","catalogId":"https://xxx/specification/ohos/extended_catalog.json","theme":{"primaryColor":"#FF0A59F7"}}}
{"version":"v0.9","updateComponents":{"surfaceId":"json_product","components":[{"id":"root","component":"Extended.Column","children":["body"],"space":0,"styles":{"width":"matchParent","constraintSize":{"maxWidth":336},"borderRadius":16,"clip":true,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"json_product","components":[{"id":"body","component":"Extended.Column","children":["row_top","row_price","row_actions"],"space":8,"styles":{"width":"matchParent","alignItems":"top"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"json_product","components":[{"id":"row_top","component":"Extended.Row","children":["cover","text_col"],"space":8,"styles":{"width":"matchParent","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"json_product","components":[{"id":"cover","component":"Extended.Image","styles":{"constraintSize":{"minWidth":72,"maxWidth":72,"minHeight":72,"maxHeight":72},"borderRadius":12,"objectFit":"cover"},"src":{"path":"/imageUrl"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"json_product","path":"/imageUrl","value":"https://picsum.photos/seed/mbp14/480/480"}}
{"version":"v0.9","updateComponents":{"surfaceId":"json_product","components":[{"id":"text_col","component":"Extended.Column","children":["title_row","subtitle"],"space":4,"styles":{"layoutWeight":1,"width":"matchParent","alignItems":"top"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"json_product","components":[{"id":"title_row","component":"Extended.Row","children":["title","badge"],"space":8,"styles":{"width":"matchParent","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"json_product","components":[{"id":"title","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000","layoutWeight":1},"content":{"path":"/title"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"json_product","path":"/title","value":"MacBook Pro 14\""}}
{"version":"v0.9","updateComponents":{"surfaceId":"json_product","components":[{"id":"badge","component":"Extended.Text","styles":{"fontSize":10,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#FFE84026","padding":{"top":2,"right":4,"bottom":2,"left":4},"borderRadius":4,"borderWidth":1,"borderColor":"#FFE84026"},"content":{"path":"/badge"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"json_product","path":"/badge","value":"新品"}}
{"version":"v0.9","updateComponents":{"surfaceId":"json_product","components":[{"id":"subtitle","component":"Extended.Text","styles":{"fontSize":12,"fontWeight":"400","maxLines":1,"textOverflow":"ellipsis","fontColor":"#99000000","width":"matchParent"},"content":{"path":"/subtitle"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"json_product","path":"/subtitle","value":"M4 Pro · 18GB · 512GB"}}
{"version":"v0.9","updateComponents":{"surfaceId":"json_product","components":[{"id":"row_price","component":"Extended.Row","children":["price","price_note"],"space":8,"styles":{"width":"matchParent","justifyContent":"spaceBetween","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"json_product","components":[{"id":"price","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":{"path":"/price"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"json_product","path":"/price","value":"¥14,999"}}
{"version":"v0.9","updateComponents":{"surfaceId":"json_product","components":[{"id":"price_note","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"600","maxLines":1,"textOverflow":"ellipsis","fontColor":"#FFE84026","textAlign":"end","layoutWeight":1},"content":{"path":"/priceNote"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"json_product","path":"/priceNote","value":"券后预计 ¥13,999"}}
{"version":"v0.9","updateComponents":{"surfaceId":"json_product","components":[{"id":"row_actions","component":"Extended.Row","children":["btn_primary","btn_secondary"],"space":8,"styles":{"width":"matchParent","justifyContent":"start","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"json_product","components":[{"id":"btn_primary","component":"Extended.Button","enabled":true,"styles":{"height":28,"borderRadius":14,"fontSize":14,"fontWeight":500,"padding":{"top":6,"right":12,"bottom":6,"left":12},"backgroundColor":"#FF0A59F7"},"label":{"path":"/actions/0/label"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"json_product","path":"/actions","value":[{"label":"加入购物车","style":"primary"},{"label":"收藏","style":"secondary"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"json_product","components":[{"id":"btn_secondary","component":"Extended.Button","enabled":true,"styles":{"height":28,"borderRadius":14,"fontSize":14,"fontWeight":400,"padding":{"top":6,"right":12,"bottom":6,"left":12},"backgroundColor":"#0C000000"},"label":{"path":"/actions/1/label"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"json_product","path":"/actions/1","value":{"label":"收藏","style":"secondary"}}}
```
