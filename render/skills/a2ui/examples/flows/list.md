# A2UI List Examples

Examples of list layouts following HarmonyOS design specification.

## Restaurant List

A vertical restaurant list using a single outer frame and lightweight item grouping.

```jsonl
{"version":"v0.9","createSurface":{"surfaceId":"restaurants","catalogId":"https://xxx/specification/ohos/extended_catalog.json","theme":{"primaryColor":"#FF0A59F7"}}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"root","component":"Extended.Column","children":["header","list_col"],"space":12,"styles":{"width":"matchParent","constraintSize":{"maxWidth":336},"borderRadius":16,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"header","component":"Extended.Row","children":["title","filter_btn"],"space":12,"styles":{"width":"matchParent","justifyContent":"spaceBetween","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"title","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"Nearby Restaurants"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"filter_btn","component":"Extended.Button","enabled":true,"styles":{"height":28,"fontSize":14,"fontWeight":400,"borderRadius":14,"backgroundColor":"#0C000000"},"label":"Filter"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"list_col","component":"Extended.Column","children":["rest1_body","rest2_body","rest3_body"],"space":12,"styles":{"width":"matchParent"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest1_body","component":"Extended.Column","children":["rest1_header","rest1_meta"],"space":8,"styles":{"width":"matchParent","alignItems":"top","padding":{"top":8,"right":8,"bottom":8,"left":8},"borderRadius":12,"borderWidth":1,"borderColor":"#33000000","backgroundColor":"#FFFFFFFF"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest1_header","component":"Extended.Row","children":["rest1_name","rest1_tag"],"space":8,"styles":{"width":"matchParent","justifyContent":"spaceBetween","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest1_name","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"Luna Bistro"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest1_tag","component":"Extended.Text","styles":{"fontSize":12,"fontWeight":"400","maxLines":1,"textOverflow":"ellipsis","fontColor":"#66000000"},"content":"Italian"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest1_meta","component":"Extended.Row","children":["rest1_rating","rest1_price","rest1_spacer","rest1_menu","rest1_book"],"space":8,"styles":{"width":"matchParent","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest1_rating","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":1,"textOverflow":"ellipsis","fontColor":"#99000000"},"content":"Rating 4.7"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest1_price","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":1,"textOverflow":"ellipsis","fontColor":"#99000000"},"content":"$$$"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest1_spacer","component":"Extended.Text","styles":{"layoutWeight":1},"content":""}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest1_menu","component":"Extended.Button","enabled":true,"styles":{"height":28,"borderRadius":14,"fontSize":14,"fontWeight":400,"backgroundColor":"#0C000000"},"label":"Menu"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest1_book","component":"Extended.Button","enabled":true,"styles":{"height":28,"borderRadius":14,"fontSize":14,"fontWeight":500,"backgroundColor":"#FF0A59F7"},"label":"Book"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest2_body","component":"Extended.Column","children":["rest2_header","rest2_meta"],"space":8,"styles":{"width":"matchParent","padding":{"top":8,"right":8,"bottom":8,"left":8},"borderRadius":12,"borderWidth":1,"borderColor":"#33000000","backgroundColor":"#FFFFFFFF"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest2_header","component":"Extended.Row","children":["rest2_name","rest2_tag"],"space":8,"styles":{"width":"matchParent","justifyContent":"spaceBetween","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest2_name","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"River & Stone"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest2_tag","component":"Extended.Text","styles":{"fontSize":12,"fontWeight":"400","maxLines":1,"textOverflow":"ellipsis","fontColor":"#66000000"},"content":"Seafood"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest2_meta","component":"Extended.Row","children":["rest2_rating","rest2_price","rest2_spacer","rest2_menu","rest2_book"],"space":8,"styles":{"width":"matchParent","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest2_rating","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":1,"textOverflow":"ellipsis","fontColor":"#99000000"},"content":"Rating 4.5"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest2_price","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":1,"textOverflow":"ellipsis","fontColor":"#99000000"},"content":"$$"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest2_spacer","component":"Extended.Text","styles":{"layoutWeight":1},"content":""}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest2_menu","component":"Extended.Button","enabled":true,"styles":{"height":28,"borderRadius":14,"fontSize":14,"fontWeight":400,"backgroundColor":"#0C000000"},"label":"Menu"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest2_book","component":"Extended.Button","enabled":true,"styles":{"height":28,"borderRadius":14,"fontSize":14,"fontWeight":500,"backgroundColor":"#FF0A59F7"},"label":"Book"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest3_body","component":"Extended.Column","children":["rest3_header","rest3_meta"],"space":8,"styles":{"width":"matchParent","padding":{"top":8,"right":8,"bottom":8,"left":8},"borderRadius":12,"borderWidth":1,"borderColor":"#33000000","backgroundColor":"#FFFFFFFF"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest3_header","component":"Extended.Row","children":["rest3_name","rest3_tag"],"space":8,"styles":{"width":"matchParent","justifyContent":"spaceBetween","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest3_name","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"Orchid Noodle Bar"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest3_tag","component":"Extended.Text","styles":{"fontSize":12,"fontWeight":"400","maxLines":1,"textOverflow":"ellipsis","fontColor":"#66000000"},"content":"Asian"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest3_meta","component":"Extended.Row","children":["rest3_rating","rest3_price","rest3_spacer","rest3_menu","rest3_book"],"space":8,"styles":{"width":"matchParent","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest3_rating","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":1,"textOverflow":"ellipsis","fontColor":"#99000000"},"content":"Rating 4.3"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest3_price","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":1,"textOverflow":"ellipsis","fontColor":"#99000000"},"content":"$"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest3_spacer","component":"Extended.Text","styles":{"layoutWeight":1},"content":""}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest3_menu","component":"Extended.Button","enabled":true,"styles":{"height":28,"borderRadius":14,"fontSize":14,"fontWeight":400,"backgroundColor":"#0C000000"},"label":"Menu"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"restaurants","components":[{"id":"rest3_book","component":"Extended.Button","enabled":true,"styles":{"height":28,"borderRadius":14,"fontSize":14,"fontWeight":500,"backgroundColor":"#FF0A59F7"},"label":"Book"}]}}
```

## Horizontal Category Scroll

A horizontal scrolling list of categories.

```jsonl
{"version":"v0.9","createSurface":{"surfaceId":"categories","catalogId":"https://xxx/specification/ohos/extended_catalog.json","theme":{"primaryColor":"#FF0A59F7"}}}
{"version":"v0.9","updateComponents":{"surfaceId":"categories","components":[{"id":"root","component":"Extended.Column","children":["section_title","category_row"],"space":12,"styles":{"width":"matchParent","constraintSize":{"maxWidth":336},"borderRadius":16,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"categories","components":[{"id":"section_title","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"Categories"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"categories","components":[{"id":"category_row","component":"Extended.Row","children":["cat1","cat2","cat3","cat4"],"space":8,"styles":{"width":"matchParent","justifyContent":"start","alignItems":"center"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"categories","components":[{"id":"cat1","component":"Extended.Text","styles":{"fontSize":12,"fontWeight":"400","maxLines":1,"textOverflow":"ellipsis","fontColor":"#FF0A59F7","backgroundColor":"#EEF4FF","borderRadius":4,"borderWidth":1,"borderColor":"#CFE0FF","padding":{"top":8,"right":12,"bottom":8,"left":12}},"content":"Italian"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"categories","components":[{"id":"cat2","component":"Extended.Text","styles":{"fontSize":12,"fontWeight":"400","maxLines":1,"textOverflow":"ellipsis","fontColor":"#FF0A59F7","backgroundColor":"#EEF4FF","borderRadius":4,"borderWidth":1,"borderColor":"#CFE0FF","padding":{"top":8,"right":12,"bottom":8,"left":12}},"content":"Seafood"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"categories","components":[{"id":"cat3","component":"Extended.Text","styles":{"fontSize":12,"fontWeight":"400","maxLines":1,"textOverflow":"ellipsis","fontColor":"#FF0A59F7","backgroundColor":"#EEF4FF","borderRadius":4,"borderWidth":1,"borderColor":"#CFE0FF","padding":{"top":8,"right":12,"bottom":8,"left":12}},"content":"Asian"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"categories","components":[{"id":"cat4","component":"Extended.Text","styles":{"fontSize":12,"fontWeight":"400","maxLines":1,"textOverflow":"ellipsis","fontColor":"#FF0A59F7","backgroundColor":"#EEF4FF","borderRadius":4,"borderWidth":1,"borderColor":"#CFE0FF","padding":{"top":8,"right":12,"bottom":8,"left":12}},"content":"Dessert"}]}}
```

## Empty State

A friendly empty state with illustration and action.

```jsonl
{"version":"v0.9","createSurface":{"surfaceId":"empty","catalogId":"https://xxx/specification/ohos/extended_catalog.json","theme":{"primaryColor":"#FF0A59F7"}}}
{"version":"v0.9","updateComponents":{"surfaceId":"empty","components":[{"id":"root","component":"Extended.Column","children":["empty_content"],"space":0,"styles":{"width":"matchParent","constraintSize":{"maxWidth":336},"borderRadius":16,"clip":true,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"empty","components":[{"id":"empty_content","component":"Extended.Column","children":["empty_title","empty_message","action_btn"],"space":12,"styles":{"width":"matchParent","alignItems":"top"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"empty","components":[{"id":"empty_title","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000","margin":{"bottom":4}},"content":"No results found"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"empty","components":[{"id":"empty_message","component":"Extended.Text","styles":{"fontSize":14,"fontWeight":"400","maxLines":2,"textOverflow":"ellipsis","margin":{"bottom":4},"fontColor":"#99000000"},"content":"Try adjusting your search or filters"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"empty","components":[{"id":"action_btn","component":"Extended.Button","enabled":true,"styles":{"width":"matchParent","height":40,"borderRadius":20,"fontSize":16,"fontWeight":500,"backgroundColor":"#FF0A59F7"},"label":"Clear Search"}]}}
```

## Key Design Patterns

1. **Card shell**（`harmony-card-spec.md`）：最外层 **`#FFFFFFFF`**、圆角 **16vp**、**`maxWidth` 336**、内边距 **12vp**；`theme.primaryColor` **`#FF0A59F7`**。
2. **List item grouping**：轻量 **`borderRadius` 12** + `borderColor` **`#33000000`** + 内边距 **8vp**（与列表子块一致）。
3. **Typography**：列表主行 **`Body_L` 16** + **`fontColor` `#E5000000`**；副行 **`#99000000`** / **`#66000000`**（须显式写出）。
4. **行尾按钮**（`A4.1` 列表小按钮）：**height 28**、**borderRadius 14**、**fontSize 14**；弱底 **`#0C000000`**，主操作 **`#FF0A59F7`**。
5. **整卡主 CTA**（空状态等）：**height 40**、**borderRadius 20**、**`#FF0A59F7`**（同 `quick-snippets` §7b）。
