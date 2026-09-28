# Compact Medal Leaderboard Card

平行于 `skills/a2ui/examples/cards/card-medal-leaderboard.md` 的布局意图：

- **表头与每行**：**外层 `Row` 恰好两子** — `[left_group, right_group]`，`justifyContent`: `"spaceBetween"`（**Row** schema）；左组内 `space` **8** 放「排名 + 国家列」，右组内 `space` **8** 放「金/银/铜/总数」列，避免 6 个格子同一 Row 被均匀拉伸。
- **氛围底图**：使用 **Card** `backgroundImage` / `backgroundSize` / `backgroundPosition`（单行 props，与 `extended-ui-schema` 一致）。宿主若不支持多层 CSS 背景，不要用逗号拼接的复杂 `fill` 替代图。
- 下列为 **精简 3 行** 示例（完整多行请按同样模式扩展）。

```jsonl
{"@medal_board", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"medal_board", "root", "Card", {"title": "体育奖牌榜", "layout": "vertical", "gap": 0, "width": "matchParent", "padding": 12, "radius": 20, "strokeThickness": 1, "strokeColor": "#E5E5E5", "backgroundImage": "https://picsum.photos/seed/medal-bg/800/400", "backgroundSize": "cover", "backgroundPosition": "center bottom"}, ["medal_brand", "medal_head", "medal_r1", "medal_r2", "medal_r3"]}
{"medal_board", "medal_brand", "Row", {"width": "matchParent", "justifyContent": "spaceBetween", "alignItems": "center", "space": 0}, ["medal_brand_left", "medal_more"]}
{"medal_board", "medal_brand_left", "Row", {"space": 8, "alignItems": "center"}, ["medal_logo", "medal_brand_txt"]}
{"medal_board", "medal_logo", "Image", {"src": "https://picsum.photos/seed/logo/40/40", "width": 20, "height": 20, "borderRadius": 4, "objectFit": "cover"}}
{"medal_board", "medal_brand_txt", "Text", {"content": "体育奖牌榜", "fontSize": 14, "fontWeight": "500", "fontColor": "#000000"}}
{"medal_board", "medal_more", "Text", {"content": "更多 >", "fontSize": 12, "fontWeight": "400", "fontColor": "#0A59F7", "openUrl": "https://example.com/more-medals"}}
{"medal_board", "medal_head", "Row", {"width": "matchParent", "justifyContent": "spaceBetween", "alignItems": "center", "space": 0}, ["mh_left_wrap", "mh_right_wrap"]}
{"medal_board", "mh_left_wrap", "Row", {"space": 8, "alignItems": "center"}, ["mh_rank", "mh_country"]}
{"medal_board", "mh_rank", "Text", {"content": "排名", "fontSize": 11, "fontWeight": "400", "fontColor": "#999999", "width": 36}}
{"medal_board", "mh_country", "Text", {"content": "国家/地区", "fontSize": 11, "fontWeight": "400", "fontColor": "#999999", "width": 96, "maxLines": 1, "textOverflow": "ellipsis"}}
{"medal_board", "mh_right_wrap", "Row", {"space": 8, "alignItems": "center"}, ["mh_g", "mh_s", "mh_b", "mh_tot"]}
{"medal_board", "mh_g", "Text", {"content": "金", "fontSize": 11, "fontWeight": "400", "fontColor": "#999999", "width": 36, "textAlign": "center"}}
{"medal_board", "mh_s", "Text", {"content": "银", "fontSize": 11, "fontWeight": "400", "fontColor": "#999999", "width": 36, "textAlign": "center"}}
{"medal_board", "mh_b", "Text", {"content": "铜", "fontSize": 11, "fontWeight": "400", "fontColor": "#999999", "width": 36, "textAlign": "center"}}
{"medal_board", "mh_tot", "Text", {"content": "总数", "fontSize": 11, "fontWeight": "400", "fontColor": "#999999", "width": 40, "textAlign": "end"}}
{"medal_board", "medal_r1", "Row", {"width": "matchParent", "justifyContent": "spaceBetween", "alignItems": "center", "space": 0, "padding": [12, 0, 12, 0]}, ["r1_left", "r1_right"]}
{"medal_board", "r1_left", "Row", {"space": 8, "alignItems": "center"}, ["m1_rank", "m1_nat"]}
{"medal_board", "m1_rank", "Text", {"content": "1", "fontSize": 15, "fontWeight": "500", "fontColor": "#000000", "width": 36}}
{"medal_board", "m1_nat", "Row", {"space": 4, "alignItems": "center", "width": 96}, ["m1_flag", "m1_name"]}
{"medal_board", "m1_flag", "Image", {"src": "https://picsum.photos/seed/flag1/52/36", "width": 26, "height": 18, "borderRadius": 2, "objectFit": "cover"}}
{"medal_board", "m1_name", "Text", {"content": "美国", "fontSize": 14, "fontWeight": "400", "fontColor": "#000000", "maxLines": 1, "textOverflow": "ellipsis"}}
{"medal_board", "r1_right", "Row", {"space": 8, "alignItems": "center"}, ["m1_g", "m1_s", "m1_b", "m1_t"]}
{"medal_board", "m1_g", "Text", {"content": "40", "fontSize": 14, "fontWeight": "400", "fontColor": "#000000", "width": 36, "textAlign": "center"}}
{"medal_board", "m1_s", "Text", {"content": "44", "fontSize": 14, "fontWeight": "400", "fontColor": "#000000", "width": 36, "textAlign": "center"}}
{"medal_board", "m1_b", "Text", {"content": "42", "fontSize": 14, "fontWeight": "400", "fontColor": "#000000", "width": 36, "textAlign": "center"}}
{"medal_board", "m1_t", "Text", {"content": "126", "fontSize": 14, "fontWeight": "500", "fontColor": "#0A59F7", "width": 40, "textAlign": "end"}}
{"medal_board", "medal_r2", "Row", {"width": "matchParent", "justifyContent": "spaceBetween", "alignItems": "center", "space": 0, "padding": [12, 0, 12, 0]}, ["r2_left", "r2_right"]}
{"medal_board", "r2_left", "Row", {"space": 8, "alignItems": "center"}, ["m2_rank", "m2_nat"]}
{"medal_board", "m2_rank", "Text", {"content": "2", "fontSize": 15, "fontWeight": "500", "fontColor": "#000000", "width": 36}}
{"medal_board", "m2_nat", "Row", {"space": 4, "alignItems": "center", "width": 96}, ["m2_flag", "m2_name"]}
{"medal_board", "m2_flag", "Image", {"src": "https://picsum.photos/seed/flag2/52/36", "width": 26, "height": 18, "borderRadius": 2, "objectFit": "cover"}}
{"medal_board", "m2_name", "Text", {"content": "中国", "fontSize": 14, "fontWeight": "400", "fontColor": "#000000", "maxLines": 1, "textOverflow": "ellipsis"}}
{"medal_board", "r2_right", "Row", {"space": 8, "alignItems": "center"}, ["m2_g", "m2_s", "m2_b", "m2_t"]}
{"medal_board", "m2_g", "Text", {"content": "40", "fontSize": 14, "fontWeight": "400", "fontColor": "#000000", "width": 36, "textAlign": "center"}}
{"medal_board", "m2_s", "Text", {"content": "27", "fontSize": 14, "fontWeight": "400", "fontColor": "#000000", "width": 36, "textAlign": "center"}}
{"medal_board", "m2_b", "Text", {"content": "24", "fontSize": 14, "fontWeight": "400", "fontColor": "#000000", "width": 36, "textAlign": "center"}}
{"medal_board", "m2_t", "Text", {"content": "91", "fontSize": 14, "fontWeight": "500", "fontColor": "#0A59F7", "width": 40, "textAlign": "end"}}
{"medal_board", "medal_r3", "Row", {"width": "matchParent", "justifyContent": "spaceBetween", "alignItems": "center", "space": 0, "padding": [12, 0, 12, 0]}, ["r3_left", "r3_right"]}
{"medal_board", "r3_left", "Row", {"space": 8, "alignItems": "center"}, ["m3_rank", "m3_nat"]}
{"medal_board", "m3_rank", "Text", {"content": "3", "fontSize": 15, "fontWeight": "500", "fontColor": "#000000", "width": 36}}
{"medal_board", "m3_nat", "Row", {"space": 4, "alignItems": "center", "width": 96}, ["m3_flag", "m3_name"]}
{"medal_board", "m3_flag", "Image", {"src": "https://picsum.photos/seed/flag3/52/36", "width": 26, "height": 18, "borderRadius": 2, "objectFit": "cover"}}
{"medal_board", "m3_name", "Text", {"content": "日本", "fontSize": 14, "fontWeight": "400", "fontColor": "#000000", "maxLines": 1, "textOverflow": "ellipsis"}}
{"medal_board", "r3_right", "Row", {"space": 8, "alignItems": "center"}, ["m3_g", "m3_s", "m3_b", "m3_t"]}
{"medal_board", "m3_g", "Text", {"content": "20", "fontSize": 14, "fontWeight": "400", "fontColor": "#000000", "width": 36, "textAlign": "center"}}
{"medal_board", "m3_s", "Text", {"content": "12", "fontSize": 14, "fontWeight": "400", "fontColor": "#000000", "width": 36, "textAlign": "center"}}
{"medal_board", "m3_b", "Text", {"content": "13", "fontSize": 14, "fontWeight": "400", "fontColor": "#000000", "width": 36, "textAlign": "center"}}
{"medal_board", "m3_t", "Text", {"content": "45", "fontSize": 14, "fontWeight": "500", "fontColor": "#0A59F7", "width": 40, "textAlign": "end"}}
```
