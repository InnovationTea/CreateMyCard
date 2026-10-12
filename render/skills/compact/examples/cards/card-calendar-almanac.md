# Compact Calendar / Almanac Card

平行于 `skills/a2ui/examples/cards/card-calendar-almanac.md`：品牌行 + 日期主行 + 宜忌行。宽卡用 **`Row` + `justifyContent` `"spaceBetween"`**；右侧星期列放在 **Column** 内 **`layoutWeight`** 拉满。

```jsonl
{"@cal_surf", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"cal_surf", "root", "Card", {"title": "万年历", "layout": "vertical", "gap": 12, "width": "matchParent", "padding": 12, "fill": "#F1F3F5", "radius": 20}, ["cal_brand", "cal_main", "cal_yi", "cal_ji"]}
{"cal_surf", "cal_brand", "Row", {"width": "matchParent", "justifyContent": "spaceBetween", "alignItems": "center", "space": 0}, ["cal_brand_left", "cal_brand_zodiac"]}
{"cal_surf", "cal_brand_left", "Row", {"space": 8, "alignItems": "center"}, ["cal_icon", "cal_brand_txt"]}
{"cal_surf", "cal_icon", "Image", {"src": "https://picsum.photos/seed/cal-icon/48/48", "width": 24, "height": 24, "borderRadius": 12, "objectFit": "cover"}}
{"cal_surf", "cal_brand_txt", "Text", {"content": "小艺", "fontSize": 14, "fontWeight": "400", "fontColor": "#000000"}}
{"cal_surf", "cal_brand_zodiac", "Text", {"content": "【属蛇】", "fontSize": 12, "fontWeight": "400", "fontColor": "#666666", "layoutWeight": 1, "textAlign": "end"}}
{"cal_surf", "cal_main", "Row", {"width": "matchParent", "justifyContent": "spaceBetween", "alignItems": "center", "space": 0}, ["cal_main_left", "cal_main_right"]}
{"cal_surf", "cal_main_left", "Row", {"space": 8, "alignItems": "center"}, ["cal_day_tile", "cal_text_col"]}
{"cal_surf", "cal_day_tile", "Card", {"layout": "vertical", "gap": 0, "fill": "#0A59F7", "radius": 14, "padding": 8, "width": 48, "height": 48}, ["cal_day_num"]}
{"cal_surf", "cal_day_num", "Text", {"content": "6", "fontSize": 24, "fontWeight": "500", "textAlign": "center", "fontColor": "#FFFFFF"}}
{"cal_surf", "cal_text_col", "Column", {"space": 4, "alignItems": "stretch"}, ["cal_solar", "cal_lunar"]}
{"cal_surf", "cal_solar", "Text", {"content": "2026年5月6日", "fontSize": 16, "fontWeight": "500", "fontColor": "#000000"}}
{"cal_surf", "cal_lunar", "Text", {"content": "丙午年 四月初九", "fontSize": 12, "fontWeight": "400", "fontColor": "#666666"}}
{"cal_surf", "cal_main_right", "Column", {"layoutWeight": 1, "alignItems": "bottom", "space": 0}, ["cal_week"]}
{"cal_surf", "cal_week", "Text", {"content": "星期二", "fontSize": 14, "fontWeight": "500", "textAlign": "end", "fontColor": "#000000", "width": "matchParent"}}
{"cal_surf", "cal_yi", "Row", {"width": "matchParent", "alignItems": "center", "space": 8}, ["cal_yi_badge", "cal_yi_txt"]}
{"cal_surf", "cal_yi_badge", "Card", {"layout": "vertical", "gap": 0, "fill": "#E8F5E9", "radius": 8, "padding": [2, 8, 2, 8]}, ["cal_yi_lbl"]}
{"cal_surf", "cal_yi_lbl", "Text", {"content": "宜", "fontSize": 11, "fontWeight": "500", "fontColor": "#2E7D32"}}
{"cal_surf", "cal_yi_txt", "Text", {"content": "打扫 破屋 祭祀 馀事勿取 坏垣", "fontSize": 12, "fontWeight": "400", "fontColor": "#000000", "layoutWeight": 1, "maxLines": 3, "textOverflow": "ellipsis"}}
{"cal_surf", "cal_ji", "Row", {"width": "matchParent", "alignItems": "center", "space": 8}, ["cal_ji_badge", "cal_ji_txt"]}
{"cal_surf", "cal_ji_badge", "Card", {"layout": "vertical", "gap": 0, "fill": "#FFEBEE", "radius": 8, "padding": [2, 8, 2, 8]}, ["cal_ji_lbl"]}
{"cal_surf", "cal_ji_lbl", "Text", {"content": "忌", "fontSize": 11, "fontWeight": "500", "fontColor": "#C62828"}}
{"cal_surf", "cal_ji_txt", "Text", {"content": "诸事不宜", "fontSize": 12, "fontWeight": "400", "fontColor": "#000000", "layoutWeight": 1, "maxLines": 2, "textOverflow": "ellipsis"}}
```
