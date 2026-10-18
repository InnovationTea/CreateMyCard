# Multi-surface with minimal GenUI

多个 **`surfaceId`** 对应多次 **`createSurface`**（不同 `@id`）或单流中交替出现；**并行 UI 由产品 / 宿主**决定如何路由各行。

## Option A — 多个独立通道

- 每通道一条 JSONL 流。Agent 在各自流内为 **`surfaceId`** 发 **`createSurface` + `updateComponent`**。

## Option B — 单通道、单表面内分栏

- 更常见：一次 **`createSurface`**，在一棵树里用 **横向 `Card`（`layout` `"horizontal"`）** 模拟 sidebar + main。

## Option B 示例（单流 · 单 surface）

```jsonl
{"@workbench_surf", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"workbench_surf", "root", "Card", {"title": "工作台", "layout": "horizontal", "gap": 12, "width": "matchParent", "padding": 12, "fill": "#F1F3F5", "radius": 20}, ["sidebar", "main"]}
{"workbench_surf", "sidebar", "Card", {"title": "导航", "layout": "vertical", "gap": 8, "width": "matchParent", "fill": "#FFFFFF", "radius": 16, "padding": 12}, ["nav_dash", "nav_orders"]}
{"workbench_surf", "nav_dash", "Button", {"label": "仪表盘", "borderRadius": 14, "fontSize": 12, "fontWeight": 400, "width": "matchParent", "openUrl": "https://example.com/dash"}}
{"workbench_surf", "nav_orders", "Button", {"label": "订单", "borderRadius": 14, "fontSize": 12, "fontWeight": 400, "width": "matchParent", "openUrl": "https://example.com/orders"}}
{"workbench_surf", "main", "Card", {"title": "主内容", "layout": "vertical", "gap": 12, "width": "matchParent", "fill": "#FFFFFF", "radius": 16, "padding": 12}, ["main_body"]}
{"workbench_surf", "main_body", "Text", {"content": "Dashboard content…", "fontSize": 14, "fontWeight": "400", "fontColor": "#000000"}}
```

## Option C — 关闭某表面

- 发 **`deleteSurface`** 行：`{"~<surfaceId>"}`（`surfaceId` 不含 `~` 前缀在宿主模型中如何还原由下游处理）。
- 或 **新 `createSurface`** 覆盖当前会话的展示意图（由宿主定义）。
