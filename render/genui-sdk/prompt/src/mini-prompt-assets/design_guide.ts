export const DESIGN_GUIDE = `
## DESIGN GUIDE — (MUST FOLLOW FIRST)

### Color & restraint
- STRICT color limit. Count background colors (fill on Card / Button) AND text colors (fill on Text) together.
  The total number of DISTINCT hex values MUST NOT exceed 4.
  Example: #FAFAF7, #0F0F0F, #E0E0E0, #C41E3A — that is 4. Do NOT add extra grays; reuse one of the four.
- **Gradients** (Card/Button \`fill\`, \`fillHover\`): each **hex stop** in \`linear-gradient\` / \`radial-gradient\` counts toward those four colors — reuse the same hex codes across stops when possible. Do not introduce new hexes only for gradient midpoints unless you stay within the limit.
- **Readability**: gradient button/card backgrounds must keep **label and body text** legible; avoid all-light gradients for primary actions unless contrast remains acceptable.

### Hierarchy (critical)
- **Card** frames a section (title, description, grouping). Root plus **one level** of child Cards get a visible frame in the renderer; go deeper only when structure needs it, and prefer **Text** + spacing inside a section instead of many nested Cards. For lists or rows of values inside a section, prefer **Row** / **Column** + **Text** instead of stacking many nested **Card**s.
- **Text** is plain typography only: no borders, no pill/badge chrome. Hierarchy = fontSize, fontWeight, fill.
- Put related copy inside **one** container when it belongs together; use **horizontal** layout and sibling
  children for a single row of values instead of many tiny nested containers for each value.

### Row / Column (avoid layout bugs)
- **Section titles** (e.g. “营收增长”, “用户概览”): put them in **Card** \`title\` / \`description\`, or as a **Text** child directly under **Card** or **Column** — **do not** wrap a **single** line of title text in **Row** alone.
- Use **Row** only when there are **two or more** siblings in one horizontal line (e.g. label + value + action, or multiple metrics). For one block of copy, use **Column** or plain **Text**.
- **KPI / metric rows**: one **Row** with multiple **Text** nodes (or **Text** + **Button**), set \`space\`, \`alignItems\`: \`"center"\`, and usually \`width\`: \`"matchParent"\` on the **Row** so the row spans the card.
- **Vertical stacks** (title line + number line): use **Column** with two **Text** children, not a **Row** with one **Text**.

### Compact density (default)
- Prefer **tight, efficient** layouts: small \`gap\` and \`padding\` unless the user or scene clearly calls for airy editorial space.
- Typical ranges: **Card** / **Row** / **Column** \`gap\` **6–10** px; **Card** \`padding\` **12–16** px (single number or modest tuples). Horizontal toolbars with few items: **gap** ~**10–14**.
- **Root** Card: set \`width\`: \`"matchParent"\` so content uses the full width; avoid huge \`gap\` (20+) or \`padding\` (28+) for dense dashboards and forms.

### Full-width & side-by-side (critical — avoid a narrow left column)
- **Every main block must span the usable row width.** Root and section **Card**s: \`width\`: \`"matchParent"\`. **Row** / **Column** that wrap primary content: same. Do **not** leave most of the screen empty on the right.
- On a **vertical** root **Card**, use \`alignItems\`: \`"stretch"\` (default) — **do not** use \`"flex_start"\` on the root Card body unless you intentionally want a narrow strip (rare).
- **KPI / metric rows**: one **Row**, \`width\`: \`"matchParent"\`, \`justifyContent\`: \`"spaceBetween"\` or \`"spaceAround"\` so metrics **spread across the full width**, not clustered on the left.
- **Two related panels** (e.g. “趋势” + “规格”, two summaries): if both are short/medium, put them **on one row** using a parent **Card** with \`layout\`: \`"horizontal"\`, \`width\`: \`"matchParent"\`, **gap** ~**10–14**, and **two** child **Card**s each with \`width\`: \`"matchParent"\` — the renderer splits horizontal space evenly between siblings. (A plain **Row** of two Cards does **not** auto-expand each card’s width.) Only stack the two Cards vertically on **narrow** or mobile-first briefs.
- **Action buttons** at the bottom: prefer one **Row**, \`width\`: \`"matchParent"\`, \`justifyContent\`: \`"spaceBetween"\` or \`"start"\` with consistent \`space\`, so the row uses the full width instead of a tiny cluster in the corner.

## RULES & CONSTRAINTS

### Layout Guidelines (MANDATORY — Follow All)

#### 1. Section Rhythm
- Alternate text-heavy and visual sections. Never stack multiple text-only sections back-to-back.
- After text, shift to: imagery, card grid, or visual variety. Visual sections must clarify/support content, not just decorate.

#### 2. Spatial Composition & Creative Variation
- **Spatial composition**: Default to **controlled density** (compact). You may use asymmetry, overlap, or grid-breaking for one focal moment; reserve **large** negative space only for hero/editorial screens, not routine forms or data views.
- **Creative variation**: Introduce 1-3 small creative variations: asymmetric layouts, unusual cropping, alternative card structures, shape language, depth/layering. Every generation should choose DIFFERENT variations. Never repeat.
- **Text-heavy screens**: When screen has no visual, let typography lead. Oversized type, unexpected alignment, asymmetric layout. Break the grid if it serves the message.
- **Footer/Closing**: Include one expressive element — abstract graphic, background treatment, unexpected layout. Decorative, not functional. Readability first.

#### 3. Layout
- Clear hierarchy and variation: same-row items may differ in font size or weight; different rows may
  use different Card layouts (vertical vs horizontal).
- Keep **vertical rhythm tight**: avoid stacking large \`gap\` / \`padding\` on nested **Card**s; one comfortable outer padding beats many padded nested boxes.

#### 4. Font family
- The font family must be controlled within 2 to 3 types.
  Avoid using only one type of font, and do not exceed three types

## Never use Situation

### emoij
- The use of emojis is prohibited in any location
`;
