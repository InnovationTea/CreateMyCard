# Compact 速用片段（极简 GenUI）

本文件与 `skills/a2ui/reference/design/quick-snippets.md` 的定位类似，但输出为 **极简 GenUI 行**（`createSurface` + `updateComponent`）。行纪律见 [`../protocol/extended-output-format.md`](../protocol/extended-output-format.md)。

以下示例共用一个 **`demo_surf`** 表面；生产环境中每个场景以 **`{"@<surfaceId>", "https://xxx/specification/ohos/extended_catalog.json", ...}`** 起头。

## §0 起盘（每个新 surface 发一次）

```jsonl
{"@demo_surf", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
```

## §1 Root `Card`（浅色 · 全宽白底流）

```jsonl
{"demo_surf", "root", "Card", {"title": "模块标题", "description": "一行说明", "layout": "vertical", "gap": 12, "width": "matchParent", "padding": 16, "fill": "#FFFFFF", "radius": 20}, ["section_body"]}
{"demo_surf", "section_body", "Column", {"space": 12, "width": "matchParent", "alignItems": "stretch"}, ["block_a", "block_b"]}
```

## §2 标准内层 `Card`

```jsonl
{"demo_surf", "card_main", "Card", {"title": "分组", "layout": "vertical", "gap": 12, "width": "matchParent", "fill": "#FFFFFF", "radius": 20, "padding": 12}, ["card_inner"]}
{"demo_surf", "card_inner", "Column", {"space": 8, "width": "matchParent"}, ["line1", "line2"]}
```

## §3 `Text` 层级（务必设置 `fontColor`）

```jsonl
{"demo_surf", "page_title", "Text", {"content": "页标题", "fontSize": 18, "fontWeight": "500", "maxLines": 1, "textOverflow": "ellipsis", "fontColor": "#000000"}}
{"demo_surf", "subtitle", "Text", {"content": "次要说明", "fontSize": 14, "fontWeight": "400", "fontColor": "#666666"}}
{"demo_surf", "hint", "Text", {"content": "弱提示", "fontSize": 12, "fontWeight": "400", "fontColor": "#999999"}}
```

## §4 `Input` 字段组

```jsonl
{"demo_surf", "form_col", "Column", {"space": 12, "width": "matchParent"}, ["field_email", "field_pw"]}
{"demo_surf", "field_email", "Input", {"label": "邮箱", "name": "email", "type": "email", "placeholder": "you@example.com"}}
{"demo_surf", "field_pw", "Input", {"label": "密码", "name": "password", "type": "password", "placeholder": "••••••••"}}
```

## §5 `Button` 主 CTA

```jsonl
{"demo_surf", "btn_primary", "Button", {"label": "确认", "backgroundColor": "#0A59F7", "borderRadius": 20, "fontSize": 16, "fontWeight": 500, "openUrl": "https://example.com/confirm"}}
```

## §6 辅助链接（`Text` 下划线）

```jsonl
{"demo_surf", "forgot_row", "Row", {"width": "matchParent", "justifyContent": "end", "alignItems": "center", "space": 0}, ["forgot_text"]}
{"demo_surf", "forgot_text", "Text", {"content": "忘记密码？", "fontSize": 12, "fontWeight": "400", "fontColor": "#0A59F7", "decoration": {"type": "underline", "color": "#0A59F7", "style": "solid"}}}
```

## §7 Chip（小圆角 **Card** 包 **Text**）

```jsonl
{"demo_surf", "chip_tag", "Card", {"layout": "vertical", "gap": 0, "fill": "#FFFFFF", "radius": 4, "padding": [8, 12, 8, 12]}, ["chip_text"]}
{"demo_surf", "chip_text", "Text", {"content": "新品", "fontSize": 12, "fontWeight": "500", "fontColor": "#0A59F7"}}
```

## §8 媒体行（外 Row = 左组 + 按钮，`spaceBetween`）

```jsonl
{"demo_surf", "audio_i1", "Row", {"width": "matchParent", "justifyContent": "spaceBetween", "alignItems": "center", "space": 0}, ["audio_i1_left", "audio_p1"]}
{"demo_surf", "audio_i1_left", "Row", {"space": 8, "width": "matchParent", "layoutWeight": 1, "alignItems": "center"}, ["audio_t1", "audio_c1"]}
{"demo_surf", "audio_t1", "Image", {"src": "https://picsum.photos/seed/cover/128/128", "width": 64, "height": 64, "borderRadius": 12, "objectFit": "cover"}}
{"demo_surf", "audio_c1", "Column", {"space": 4, "layoutWeight": 1, "alignItems": "top"}, ["audio_t1_title", "audio_t1_meta"]}
{"demo_surf", "audio_t1_title", "Text", {"content": "标题两行内", "fontSize": 16, "fontWeight": "500", "maxLines": 2, "textOverflow": "ellipsis", "fontColor": "#000000", "width": "matchParent"}}
{"demo_surf", "audio_t1_meta", "Text", {"content": "次行元数据", "fontSize": 12, "fontWeight": "400", "fontColor": "#999999", "width": "matchParent"}}
{"demo_surf", "audio_p1", "Button", {"label": "播放", "borderRadius": 14, "fontSize": 14, "fontWeight": 500, "openUrl": "https://example.com/play"}}
```

## §9 数据补丁（`updateDataModel` 行，path 以 `/` 开头）

```jsonl
{"demo_surf", "/ui/title", "行程已更新"}
```

## §10 参考卡片示例索引

- [`../../examples/cards/card-medal-leaderboard.md`](../../examples/cards/card-medal-leaderboard.md)
- [`../../examples/cards/card-calendar-almanac.md`](../../examples/cards/card-calendar-almanac.md)
- [`../../examples/cards/card-audio-list.md`](../../examples/cards/card-audio-list.md)

### 对话卡片密度

与鸿蒙向产品目标一致：**padding 12 优先**；区块 **gap / space 8–12**；列表行 **6–10**。
