export const OUTPUT_FORMAT_PROMPT = `
## Output Rules — minimal GenUI JSONL (aligned with \`skills/compact\`)

One **tuple-in-braces** record per line. **New UI scene** → start with **createSurface**, then **updateComponent** lines for that surface. Do **not** emit \`version\` or full A2UI NDJSON envelopes unless the product explicitly asks.

### Line kinds (discriminate by shape)

1. **createSurface** — first string starts with \`@\` (surface id after \`@\`):
   \`{"@<surfaceId>", "<catalogId>", { theme? }, send_DataModel? }\`
   Use **\`"https://xxx/specification/ohos/extended_catalog.json"\`** as \`catalogId\` unless specified otherwise.

2. **updateComponent** — plain \`surfaceId\` (no \`@\` / \`~\`), and the **second** string is **not** a path starting with \`/\`:
   \`{"<surfaceId>", "<componentId>", "<Type>", { ...props... }, [ "childId", ... ]? }\`
   Exactly **one** component per line. **Type** ∈ Card | Row | Column | Text | Button | Radio | Select | Checkbox | Input | Image.

3. **updateDataModel** — **second** string is a JSON string whose first character is \`/\`:
   \`{"<surfaceId>", "/path/to/value", <value> }\`

4. **deleteSurface** — single segment only, first character \`~\`:
   \`{"~<surfaceId>"}\`

### Global rules

- Output **JSONL**: one complete record per line.
- **JSON strings** must be parseable (escape inner \`"\` as \`\\"\`).
- **No** \`className\` — only schema props.
- **Row** only when **two or more** horizontal siblings; section titles → **Card** \`title\`/\`description\` or **Column** + **Text**.
- **Row** \`justifyContent\` for spread layouts: use \`"spaceBetween"\` (not \`space_between\`).
- **Card** \`justifyContent\` / \`alignItems\` use schema enums (e.g. \`space_between\`, \`flex_start\` on **Card**).
- **Compact spacing**: \`gap\` / \`padding\` / \`space\` typically **6–12**; main **Card**/**Row**/**Column** \`width\`: \`"matchParent"\` where appropriate.
- **Parent ordering**: define a \`componentId\` in an **updateComponent** line **before** it appears in a parent’s \`children\` array when the host merges in stream order (extend parent’s children, then emit child lines — follow product if stricter).

### First turn (empty UI)

Emit **createSurface**, then **updateComponent** lines for the top **Card** (often \`componentId\` \`"root"\`) and descendants.

### Follow-up turns

Re-emit **updateComponent** with the same \`surfaceId\` + \`componentId\` to update props/children (merge semantics: host). No separate “props-only” / “children-only” tuple without \`type\` — always use full **updateComponent** shape when changing a node.

### New unrelated scene

Issue a new **createSurface** line with a **new** \`@surfaceId\`, then full **updateComponent** lines for that tree.

### Form submission follow-ups

When the user message is a **form submission** (action id + field values), **advance the workflow**: next screen / summary. Prefer a new **createSurface** or continued **updateComponent** on the same surface per product.

---

## Examples — first turn

### Example 1: settings card
\`\`\`jsonl
{"@prefs_demo", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"prefs_demo", "save_card", "Card", {"title": "偏好设置", "description": "修改后请点击保存", "layout": "vertical", "gap": 12, "width": "matchParent", "justifyContent": "center"}, ["hint", "save-btn"]}
{"prefs_demo", "hint", "Text", {"content": "保存后立即生效。"}}
{"prefs_demo", "save-btn", "Button", {"label": "保存", "openUrl": "https://example.com/save-settings"}}
\`\`\`

### Example 2: nested cards
\`\`\`jsonl
{"@post_demo", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"post_demo", "root", "Card", {"title": "文章", "description": "标题、摘要与操作", "width": "matchParent", "justifyContent": "center"}, ["post-title", "post-body"]}
{"post_demo", "post-title", "Text", {"content": "如何构建生成式 UI"}}
{"post_demo", "post-body", "Card", {"title": "要点", "description": "本文摘要与延伸阅读。", "justifyContent": "center", "layout": "vertical", "gap": 6, "width": "matchParent"}, ["trend1", "trend2", "read-more"]}
{"post_demo", "trend1", "Text", {"content": "要点一：组件与数据流"}}
{"post_demo", "trend2", "Text", {"content": "要点二：提示词与约束"}}
{"post_demo", "read-more", "Button", {"label": "阅读全文", "openUrl": "https://example.com/article"}}
\`\`\`

### Example 3: KPI row (**Row** uses \`spaceBetween\`)
\`\`\`jsonl
{"@kpi_demo", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"kpi_demo", "root", "Card", {"title": "数据概览", "description": "同一行展示多个指标与操作", "layout": "vertical", "gap": 10, "width": "matchParent", "alignItems": "stretch"}, ["kpi-row", "refresh-btn"]}
{"kpi_demo", "kpi-row", "Row", {"width": "matchParent", "justifyContent": "spaceBetween", "alignItems": "center", "space": 12}, ["metric-a", "metric-b", "metric-c"]}
{"kpi_demo", "metric-a", "Text", {"content": "访问量：1,234", "fontWeight": "600"}}
{"kpi_demo", "metric-b", "Text", {"content": "转化率：3.2%"}}
{"kpi_demo", "metric-c", "Text", {"content": "用户满意 9.6/10", "fontWeight": "600"}}
{"kpi_demo", "refresh-btn", "Button", {"label": "刷新", "openUrl": "https://example.com/refresh"}}
\`\`\`

### Example 4: data model + delete (optional)
\`\`\`jsonl
{"prefs_demo", "/card/notice", "已保存"}
{"~prefs_demo"}
\`\`\`

---

## Wrong examples (forbidden)

### Two \`{ }\` prop objects on one **updateComponent** line — merge into one.

### **updateComponent** without \`type\` and without full shape — use full \`{"surfaceId","id","Type",{...},[...]}\`.

### **Row** \`justifyContent\` with wrong enum — use \`"spaceBetween"\` on **Row**, not \`space_between\`.

---

## CHECKLIST

- New scene: **createSurface** (\`@...\`) first.
- Every **updateComponent** line: \`surfaceId\`, \`componentId\`, \`Type\`, one \`{props}\`, optional \`[children]\`.
- **updateDataModel**: second segment starts with \`/\`.
- **deleteSurface**: \`{"~..."}\` only.
- **Structured \`webURL\` / \`webUrl\`**: matching **Button**/**Text** \`openUrl\`.
- **Row**: ≥2 horizontal children; **Card**/**Column** for single title lines.

Generate JSONL:
`;
