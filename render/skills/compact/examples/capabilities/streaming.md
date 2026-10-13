# Compact Streaming Example

平行于 `skills/a2ui/examples/capabilities/streaming.md`：用 **首回合 `createSurface` + 根节点与子节点**，后续回合以新的 **updateComponent** 行更新同一 `surfaceId`（合并策略由宿主决定）。

同一会话内续传时，**通常不再重复** `createSurface`；下列 Step 2–4 与 Strategy 2 的代码块为 **续传片段**（不含 `@` 行），便于对照。

## Strategy 1 — Skeleton first

### Step 1 — New surface + root + placeholders

```jsonl
{"@stream_surf", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"stream_surf", "root", "Card", {"title": "搜索结果", "layout": "vertical", "gap": 12, "width": "matchParent", "padding": 12, "fill": "#F1F3F5", "radius": 20}, ["header", "loading", "results"]}
{"stream_surf", "header", "Text", {"content": "Search Results", "fontSize": 18, "fontWeight": "500", "fontColor": "#000000"}}
{"stream_surf", "loading", "Text", {"content": "Loading…", "fontSize": 12, "fontWeight": "400", "fontColor": "#999999"}}
{"stream_surf", "results", "Column", {"space": 12, "width": "matchParent", "alignItems": "stretch"}, []}
```

### Step 2 — Append first result

```jsonl
{"stream_surf", "results", "Column", {"space": 12, "width": "matchParent", "alignItems": "stretch"}, ["result_1"]}
{"stream_surf", "result_1", "Card", {"layout": "vertical", "gap": 8, "width": "matchParent", "fill": "#FFFFFF", "radius": 12, "padding": 8, "strokeThickness": 1, "strokeColor": "#E5E5E5"}, ["result_1_title", "result_1_body"]}
{"stream_surf", "result_1_title", "Text", {"content": "First Result", "fontSize": 16, "fontWeight": "500", "fontColor": "#000000"}}
{"stream_surf", "result_1_body", "Text", {"content": "Description here…", "fontSize": 14, "fontWeight": "400", "fontColor": "#666666", "maxLines": 2, "textOverflow": "ellipsis"}}
```

### Step 3 — Append second result

```jsonl
{"stream_surf", "results", "Column", {"space": 12, "width": "matchParent", "alignItems": "stretch"}, ["result_1", "result_2"]}
{"stream_surf", "result_2", "Card", {"layout": "vertical", "gap": 8, "width": "matchParent", "fill": "#FFFFFF", "radius": 12, "padding": 8, "strokeThickness": 1, "strokeColor": "#E5E5E5"}, ["result_2_title", "result_2_body"]}
{"stream_surf", "result_2_title", "Text", {"content": "Second Result", "fontSize": 16, "fontWeight": "500", "fontColor": "#000000"}}
{"stream_surf", "result_2_body", "Text", {"content": "Another description…", "fontSize": 14, "fontWeight": "400", "fontColor": "#666666", "maxLines": 2, "textOverflow": "ellipsis"}}
```

### Step 4 — Clear loading copy

```jsonl
{"stream_surf", "loading", "Text", {"content": ""}}
```

## Strategy 2 — Live KPI text

```jsonl
{"stream_surf", "stat1_value", "Text", {"content": "1,234", "fontWeight": "600", "fontColor": "#000000"}}
```

## Notes

- 每个 **新 componentId** 先出现在 **父节点的 `children`** 里（通过 **updateComponent** 行更新父 **Column** / **Card** 的 `children`），再发子节点自己的 **updateComponent** 行（与宿主合并顺序一致即可）。
- 长文拆多个 **Text**，避免单节点超大 `content` 难以流式渲染。
