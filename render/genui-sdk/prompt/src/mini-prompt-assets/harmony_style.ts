/**
 * HarmonyOS-oriented visual spec for **mini** / minimal GenUI output
 * (\`createSurface\` + \`updateComponent\` lines). Numeric values → same number in
 * \`radius\` / \`gap\` (Card) / \`space\` (Row, Column) / \`padding\` / \`fontSize\` (px) unless the brief says otherwise.
 */
export const HARMONY_STYLE_PROMPT = `
## HARMONY STYLE — MUST layer on top of schema + output rules (minimal GenUI)

After **createSurface** (\`{"@surfaceId", ...}\`), every component is one **updateComponent** line: \`{"<surfaceId>", "<componentId>", "<Type>", { props }, [ children ]? }\` (see output format). Do **not** emit \`version\` / full A2UI NDJSON in the same stream unless the product asks.

### 1. Typography
- **Font**: HarmonyOS Sans is applied by the host; express hierarchy with **Text** \`fontSize\`, \`fontWeight\`, and \`fontColor\` (per schema — **do not** use \`fill\` on **Text** for glyph color; \`fill\` is for **Card** backgrounds only).
- **Minimum**: all visible text **≥ 10** px.
- **Levels** (map to **Text** \`fontSize\`; \`fontWeight\` string: \`"300"\`–\`"700"\`):

| Role | Use | fontSize (px) | Limit |
|------|-----|-----------------|-------|
| Display | Big numbers / hero phrase | 38–56 (step 2) | ≤ **1** per card |
| Emphasis | Summary, key facts, titles | 14, 16, 18 | main copy |
| Body | lists, detail | 12–16 | default |
| Hint | captions, labels | 10–12 | secondary |

- **Weight** (strong → weak): display / KPI → \`"600"\` or \`"700"\`; emphasis / primary buttons → \`"500"\` or \`"600"\`; body → \`"400"\`; light hints → \`"300"\` or \`"400"\`.

### 2. Text color (\`fontColor\` on **Text**)
- Set \`fontColor\` on every **Text** that should not use the host default (see schema: hex / \`#rgb\` / \`rgba(...)\`).
- Light base: **#000000**; dark base: **#FFFFFF**.
- Practical hex steps: primary **#000000** / **#FFFFFF**; secondary **#666666** (light) or **#999999** (dark mode secondary); tertiary **#999999** / **#666666**; disabled / faint: **#CCCCCC**-class grays. Links / accent phrases: **#0A59F7** (light) or **#3B8CFF** (dark).

### 3. Corners
- **Card**: \`radius\` (single number or 4-tuple) — **outer card** **20** px uniform (\`radius\`: 20).
- **Button**: \`borderRadius\` (schema) — **small 14**, **large 20** px typical.
- Inner chrome (chips, media blocks): follow **2 + 2n** px: tag **4**, input **8** or **12**, image blocks **8** or **12**.

### 4. Surfaces (\`fill\` on **Card**)
- **Non-immersive**: flat **Card** \`fill\` only — light **#FFFFFF** or **#F1F3F5**; dark **#1A1A1A** / **#2D2D2D**.
- **Immersive**: full CSS \`linear-gradient(...)\` / \`radial-gradient(...)\` or **backgroundImage** on **Card**; pick colors from content; need not follow system light/dark.

### 5. Card header row (optional)
If the product shows an app strip: **Row** \`space\` **8** (schema), \`alignItems\`: \`"center"\`; icon in a small **Card** or image node if present; **Text** 12px name (\`fontColor\` **#000000** / **#FFFFFF**); “更多” line **Text** \`fontColor\` **#999999** (≈40% look). Micro gap between “更多” and chevron: **2** px in **Row** \`space\`.

### 6. Width
- Root and section **Card** / main **Row** / **Column**: \`width\`: \`"matchParent"\`. Treat “panel minus 12/24 px margin” as host chrome; your tree should still **fill** the content column.

### 7. Card padding
- Default **12** px all sides: \`padding\`: 12 or \`[12,12,12,12]\`. Emphasis sections: **16**. Match with **Card** \`gap\` **8–12** for chat-density cards.

### 8. Spacing grid (4 px; allow 2 for micro)
- **Card** \`gap\` between children; **Row** / **Column** \`space\` between children (schema names): prefer **4**, **8**, **12**; section breaks **16**; page-level **20–24** only on **root**, not stacked with large inner **padding** on every nested **Card**.

### 9. Copy & density (**Text** truncation per schema)
- **Text** supports \`maxLines\`, \`textOverflow\` (\`"ellipsis"\` needs \`maxLines\` or fixed \`width\`), and \`wordBreak\` — use them instead of stuffing unreadable single lines.
- Write **short** titles and labels; one idea per **Text** node when possible; split long body into multiple **Text** siblings with **Column** \`space\` / **Card** \`gap\` **6–8**.
- Title + subtitle: keep title one short line; subtitle one line.
- Tags: **≤ 6** Han chars or **≤ 12** Latin letters; single line.
- Buttons: short **label**; prefer **width** \`"matchParent"\` + sensible \`padding\` before shrinking \`fontSize\` (stay ≥ 10).

### 10. Buttons (**Button** — \`backgroundColor\`, \`borderRadius\` per schema)
- Types: **primary** (solid **#0A59F7** via \`backgroundColor\`), **filled ghost** (very light \`backgroundColor\` e.g. \`rgba(0,0,0,0.05)\` + optional **Text** sibling with \`fontColor\` **#0A59F7** for a link label — avoid a second solid **Button** that looks like a duplicate primary), **text-like** → prefer **Text** with \`fontColor\` **#0A59F7** inside a **Row** with \`justifyContent\`: \`"end"\` (schema enums) for “忘记密码”类辅操作.
- Sizes: large feel → \`padding\` **16** + \`fontSize\` **16**, \`borderRadius\` **20**; small → \`padding\` **8**, \`fontSize\` **12**, \`borderRadius\` **14**.
- For **Button** (and link-like **Text**), set **openUrl** to an absolute \`https://\` or \`http://\` string when the control should open a URL; the runtime maps it to A2UI \`action.functionCall\` + \`openUrl\`. Do **not** use \`actionText\`.
- **Structured payload → same row / same field**: If JSON includes **\`webURL\`** (or **\`webUrl\`**) on a nested object (e.g. \`listSubTitle3ButtonLink1\`, \`moreLink\`, \`listItemLink\`), the **Button**/**Text** that corresponds to that entity **must** use **\`openUrl\`** with that exact string. **Per-row** phone / consult buttons are **not** optional when the row carries \`*ButtonLink*.webURL\`; do **not** only attach **\`openUrl\`** to 「更多」 and skip row CTAs.

### 11. Input (**Input**)
- Mini **Input** is schema-simple (\`label\`, \`name\`, \`type\`, \`placeholder\`); **8** px corner look is from the renderer. Group fields in a **Column** \`space\` **8–12** inside a **Card** with **#FFFFFF** / **#F1F3F5** \`fill\`.

### 12. Dividers
- There is no **Divider** type. Prefer extra **Column** \`space\` / **Card** \`gap\`. If a line is needed: thin **Card** \`strokeThickness\`: 1, \`strokeColor\`: **#E5E5E5**, minimal height, or a full-width **Row** with a 1 px-tall **Card** child — sparingly.

### 13. Chips / tags
- Small **Card**: \`radius\` **4**, tight \`padding\` (e.g. **8** vertical, **12** horizontal), \`gap\` **0**, child **Text** only — do **not** reuse **20** radius for chips.

### 14. Palette quick ref (match component props in schema)
- **Card** surfaces / gradients: \`fill\` (and optional \`backgroundImage\`, \`radius\`, \`strokeColor\` / \`strokeThickness\`).
- **Button** fills: \`backgroundColor\`; corners: \`borderRadius\`.
- **Text** glyph colors: \`fontColor\` only (not \`fill\`).

Light:
- Primary actions / links (**Text** or accents): **#0A59F7**
- Page/card surface: **#FFFFFF**, alt surface **#F1F3F5**
- Text: **#000000**, secondary **#666666**, tertiary **#999999**
- Hairline: **#E5E5E5**

Dark:
- Primary accent: **#3B8CFF**
- Surface **#1A1A1A** / **#2D2D2D**
- Text **#FFFFFF** / **#999999** / **#666666**
- Hairline **#3D3D3D**

### 15. Harmony → schema mapping cheat sheet
| Harmony idea | minimal GenUI **Type** + props (same names as **ui_schema** where listed) |
|--------------|------|
| \`Extended.Text\` + styles.fontSize / fontWeight / fontColor | **Text** + \`fontSize\` + \`fontWeight\` + \`fontColor\` |
| \`Extended.Card\` + styles | **Card** + \`fill\`, \`radius\`, \`padding\`, \`gap\`, \`layout\`, \`width\`, … |
| \`Extended.Button\` + styles | **Button** + \`backgroundColor\`, \`borderRadius\`, \`fontSize\`, \`fontWeight\`, \`margin\`, \`label\`, \`openUrl\`, … |
| \`Extended.Column\` / \`Row\` + space | **Column** / **Row** + \`space\` (vertical/horizontal gap between children) |
| Card corner DSL \`radius\` | **Card** \`radius\`; **Button** uses \`borderRadius\` |
| \`styles.margin.bottom\` for rhythm | parent **Column**/**Card** \`gap\` / **Row**/**Column** \`space\`, or **Text**/**Button** \`margin\` per schema — prefer layout \`gap\`/\`space\` |

### 16. Minimal GenUI snippets (\`createSurface\` + \`updateComponent\`)

**Surface + root page (white column):**
{"@page_demo", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"page_demo", "root", "Card", {"title": "页面标题", "description": "副标题一行", "layout": "vertical", "gap": 12, "width": "matchParent", "padding": 16, "fill": "#FFFFFF", "radius": 20}, ["section-a", "section-b"]}

**Standard inner card:**
{"page_demo", "card_main", "Card", {"layout": "vertical", "gap": 12, "width": "matchParent", "fill": "#FFFFFF", "radius": 20, "padding": 12}, ["card_inner"]}

**Text levels (set \`fontColor\` on **Text**):**
{"page_demo", "page_title", "Text", {"content": "区块标题", "fontSize": 18, "fontWeight": "500", "fontColor": "#000000", "width": "matchParent"}}
{"page_demo", "row_title", "Text", {"content": "列表主名", "fontSize": 16, "fontWeight": "500", "fontColor": "#000000"}}
{"page_demo", "body", "Text", {"content": "正文说明……", "fontSize": 14, "fontWeight": "400", "fontColor": "#000000"}}
{"page_demo", "muted", "Text", {"content": "次要说明", "fontSize": 14, "fontWeight": "400", "fontColor": "#666666"}}
{"page_demo", "hint", "Text", {"content": "弱提示", "fontSize": 12, "fontWeight": "400", "fontColor": "#999999"}}

**Primary + secondary (secondary = **Text**, not a second solid **Button**):**
{"page_demo", "actions", "Row", {"width": "matchParent", "justifyContent": "spaceBetween", "alignItems": "center", "space": 12}, ["btn_primary", "link_forgot"]}
{"page_demo", "btn_primary", "Button", {"label": "确认", "openUrl": "https://example.com/confirm", "backgroundColor": "#0A59F7", "borderRadius": 20, "fontSize": 16, "fontWeight": 500, "padding": 16}}
{"page_demo", "link_forgot", "Text", {"content": "忘记密码？", "fontSize": 12, "fontWeight": "400", "fontColor": "#0A59F7"}}

**List row + \`webURL\` on same row:**
{"page_demo", "list_row", "Row", {"width": "matchParent", "justifyContent": "spaceBetween", "alignItems": "center", "space": 8}, ["lr_title", "lr_phone"]}
{"page_demo", "lr_title", "Text", {"content": "门店 A · 1.2km", "fontSize": 14, "fontColor": "#000000", "width": "matchParent"}}
{"page_demo", "lr_phone", "Button", {"label": "电话咨询", "openUrl": "https://example.com/phone-from-payload", "borderRadius": 14, "fontSize": 12, "fontWeight": 500}}

**Chip:**
{"page_demo", "chip_tag", "Card", {"layout": "vertical", "gap": 0, "fill": "#FFFFFF", "radius": 4, "padding": [8, 12, 8, 12]}, ["chip_text"]}
{"page_demo", "chip_text", "Text", {"content": "标签", "fontSize": 12, "fontWeight": "400", "fontColor": "#666666"}}

### 17. Chat card density (Xiaoyi-style)
- Prefer **padding 12** (sometimes **16**) on the **Card**; block **gap** (**Card**) **8–12**; **Column**/**Row** row rhythm \`space\` **6–10**. Do **not** stack **padding 20** + large **Card** \`gap\` + large **Column** \`space\` **16** + many heavy nested **Card** frames — it reads looser than Harmony reference art.

### 18. Reference \`skills/a2ui\` / \`skills/compact\` examples
\`skills/a2ui/examples/\` 与 \`skills/compact/examples/\` 的 Markdown 是 **布局意图**；用本 schema 的 **Type** 与 **minimal GenUI** 行（\`createSurface\` + \`updateComponent\`）重建层次，不要照抄 \`Extended.*\` 或完整协议信封进模型流。
`;
