# Compact Audio List Card

平行于 `skills/a2ui/examples/cards/card-audio-list.md`：品牌行 + 媒体行；每行 **外层 Row** = `[左组, 播放]` + `"spaceBetween"`；**内层 Row** = `[封面, 文案列]` + `space` **8**。

```jsonl
{"@audio_surf", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"audio_surf", "root", "Card", {"title": "有声", "layout": "vertical", "gap": 8, "width": "matchParent", "padding": 12, "fill": "#F1F3F5", "radius": 20}, ["audio_head", "audio_i1", "audio_i2"]}
{"audio_surf", "audio_head", "Row", {"width": "matchParent", "alignItems": "center", "space": 8}, ["audio_hico", "audio_htitle"]}
{"audio_surf", "audio_hico", "Image", {"src": "https://picsum.photos/seed/audio-icon/40/40", "width": 20, "height": 20, "borderRadius": 10, "objectFit": "cover"}}
{"audio_surf", "audio_htitle", "Text", {"content": "有声", "fontSize": 16, "fontWeight": "500", "fontColor": "#000000"}}
{"audio_surf", "audio_i1", "Row", {"width": "matchParent", "justifyContent": "spaceBetween", "alignItems": "center", "space": 0}, ["audio_i1_left", "audio_p1"]}
{"audio_surf", "audio_i1_left", "Row", {"space": 8, "width": "matchParent", "layoutWeight": 1, "alignItems": "center"}, ["audio_t1", "audio_c1"]}
{"audio_surf", "audio_t1", "Image", {"src": "https://picsum.photos/seed/audio-cover1/128/128", "width": 64, "height": 64, "borderRadius": 12, "objectFit": "cover"}}
{"audio_surf", "audio_c1", "Column", {"space": 4, "layoutWeight": 1, "alignItems": "top"}, ["audio_t1_title", "audio_t1_meta", "audio_t1_tag"]}
{"audio_surf", "audio_t1_title", "Text", {"content": "晨间新闻：科技与生活", "fontSize": 16, "fontWeight": "500", "maxLines": 2, "textOverflow": "ellipsis", "fontColor": "#000000", "width": "matchParent"}}
{"audio_surf", "audio_t1_meta", "Text", {"content": "106万次播放 · 时长 12:08", "fontSize": 12, "fontWeight": "400", "fontColor": "#999999", "width": "matchParent"}}
{"audio_surf", "audio_t1_tag", "Text", {"content": "喜马拉雅", "fontSize": 11, "fontWeight": "400", "fontColor": "#666666", "padding": [2, 8, 2, 8], "borderRadius": 4, "borderWidth": 1, "borderColor": "#E5E5E5", "backgroundColor": "#FFFFFF"}}
{"audio_surf", "audio_p1", "Button", {"label": "播放", "borderRadius": 14, "fontSize": 14, "fontWeight": 500, "backgroundColor": "#F2F2F2", "openUrl": "https://example.com/play/1"}}
{"audio_surf", "audio_i2", "Row", {"width": "matchParent", "justifyContent": "spaceBetween", "alignItems": "center", "space": 0}, ["audio_i2_left", "audio_p2"]}
{"audio_surf", "audio_i2_left", "Row", {"space": 8, "width": "matchParent", "layoutWeight": 1, "alignItems": "center"}, ["audio_t2", "audio_c2"]}
{"audio_surf", "audio_t2", "Image", {"src": "https://picsum.photos/seed/audio-cover2/128/128", "width": 64, "height": 64, "borderRadius": 12, "objectFit": "cover"}}
{"audio_surf", "audio_c2", "Column", {"space": 4, "layoutWeight": 1, "alignItems": "top"}, ["audio_t2_title", "audio_t2_meta", "audio_t2_tag"]}
{"audio_surf", "audio_t2_title", "Text", {"content": "深度对话：城市与慢生活", "fontSize": 16, "fontWeight": "500", "maxLines": 2, "textOverflow": "ellipsis", "fontColor": "#000000", "width": "matchParent"}}
{"audio_surf", "audio_t2_meta", "Text", {"content": "42万次播放 · 时长 28:40", "fontSize": 12, "fontWeight": "400", "fontColor": "#999999", "width": "matchParent"}}
{"audio_surf", "audio_t2_tag", "Text", {"content": "平台精选", "fontSize": 11, "fontWeight": "400", "fontColor": "#666666", "padding": [2, 8, 2, 8], "borderRadius": 4, "borderWidth": 1, "borderColor": "#E5E5E5", "backgroundColor": "#FFFFFF"}}
{"audio_surf", "audio_p2", "Button", {"label": "播放", "borderRadius": 14, "fontSize": 14, "fontWeight": 500, "backgroundColor": "#F2F2F2", "openUrl": "https://example.com/play/2"}}
```
