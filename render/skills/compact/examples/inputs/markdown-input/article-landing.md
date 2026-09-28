# Markdown → Compact UI（旅游攻略落地页）

平行于 `skills/a2ui/examples/inputs/markdown-input/article-landing.md` 的 **意图**：把 Markdown 结构映射为 **Info Page**（阅读优先），输出 **极简 GenUI** 行。

## 映射要点

- **H1** → root **Card** `title` / `description` + hero **Text** 子块。
- **H2** → 子 **Card** 分节，`title` 为章节名。
- **列表项** → **Column** 内多条 **Text** 或紧凑 **Row**。
- **引用块** → 浅底 **Card** + **Text**，避免过度 `ellipsis` 长段落。

## 输入（节选 Markdown）

```markdown
# 东京 3 天游玩攻略

## 概览
- 适合季节：3–4 月 / 10–11 月
- 建议时长：3 天

## 天气（本周）
- 周三：16–22°C，多云
```

## 输出（极简 JSONL 节选）

```jsonl
{"@tokyo_article", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"tokyo_article", "root", "Card", {"title": "东京 3 天游玩攻略", "description": "第一次去也能照着走", "layout": "vertical", "gap": 12, "width": "matchParent", "padding": 16, "fill": "#FFFFFF", "radius": 20}, ["sec_overview", "sec_weather"]}
{"tokyo_article", "sec_overview", "Card", {"title": "概览", "layout": "vertical", "gap": 8, "width": "matchParent", "padding": 12, "fill": "#F1F3F5", "radius": 16}, ["ov1", "ov2"]}
{"tokyo_article", "ov1", "Text", {"content": "适合季节：3–4 月 / 10–11 月", "fontSize": 14, "fontWeight": "400", "fontColor": "#000000"}}
{"tokyo_article", "ov2", "Text", {"content": "建议时长：3 天", "fontSize": 14, "fontWeight": "400", "fontColor": "#000000"}}
{"tokyo_article", "sec_weather", "Card", {"title": "天气（本周）", "layout": "vertical", "gap": 8, "width": "matchParent", "padding": 12, "fill": "#F1F3F5", "radius": 16}, ["wx1"]}
{"tokyo_article", "wx1", "Text", {"content": "周三：16–22°C，多云", "fontSize": 14, "fontWeight": "400", "fontColor": "#000000"}}
```

完整页面继续追加 **Card** 分节与 **Text** 段落即可；保持 **4px 网格** 间距。
