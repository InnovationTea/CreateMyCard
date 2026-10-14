export const DESIGN_GUIDE = `
## DESIGN GUIDE — (MUST FOLLOW FIRST)

### Extreme density — zero wasted whitespace (MANDATORY)
- **Single line first**: If label + value + short meta fits one readable line, use **one** \`Extended.Text\` (or one \`Row\` of siblings). Join fields with \` · \`, \` | \`, \`，\`, or ASCII \`/\` — do **not** break into stacked lines or extra wrappers unless wrapping is unavoidable at preview width.
- **No fake segmentation**: Do not add vertical “breathing room” between items of the **same** category (e.g. multiple job posts, SKUs, notifications). **Required**: **one** \`Column\` holds **all** same-type rows; separate rows with **small** \`space\`/\`gap\` (2–6px) or a thin \`Divider\`.
- **Homogeneous lists = one frame**: Treat “N pieces of the same thing” as a single block. Inner structure = \`Column\` of \`Text\` lines or \`Row\`s; keep \`Column.space\`/\`Row.space\` in the **4–8** range unless a true new section (different topic) needs a single larger step once.
- **Overrides decoration rules**: For dashboards, feeds, resumes, search results, settings lists — **compactness beats** asymmetric “hero” whitespace, alternating section rhythm, and decorative footers. Reserve large gaps / overlap / grid-breaking **only** for explicit marketing/hero screens; default everything else to **tight**.

### Color & restraint
- STRICT color limit. Count background colors (fill on Button) AND text colors (fill on Text) together.
  The total number of DISTINCT hex values MUST NOT exceed 4.
  Example: #FAFAF7, #0F0F0F, #E0E0E0, #C41E3A — that is 4. Do NOT add extra grays; reuse one of the four.
- **Gradients** (Button \`fill\`, \`fillHover\`): each **hex stop** in \`linear-gradient\` / \`radial-gradient\` counts toward those four colors — reuse the same hex codes across stops when possible. Do not introduce new hexes only for gradient midpoints unless you stay within the limit.
- **Readability**: gradient button backgrounds must keep **label and body text** legible; avoid all-light gradients for primary actions unless contrast remains acceptable.

### Hierarchy (critical)
- **Text** is plain typography only: no borders, no pill/badge chrome. Hierarchy = fontSize, fontWeight, fill.
- Put related copy inside **one** container when it belongs together; use **horizontal** layout and sibling
  children for a single row of values instead of many tiny nested containers for each value.

### Row / Column (avoid layout bugs)
- Use **Row** only when there are **two or more** siblings in one horizontal line (e.g. label + value + action, or multiple metrics). For one block of copy, use **Column** or plain **Text**.
- **Thumbnail / image + text** (e.g. store list, news row, avatar + body): **Row** with \`justifyContent: "start"\` (default left pack). Put the text block in **Extended.Column** with \`styles.layoutWeight: 1\` and \`styles.width: "matchParent"\` so it fills space after the fixed-width image. **Forbidden**: \`justifyContent: "spaceBetween"\` when there are only **two** children (image + column) — it pins the text to the trailing edge and causes staggered misalignment when text width varies.
- **KPI / metric rows**: one **Row** with multiple **Text** nodes (or **Text** + **Button**), set \`gap\`, \`alignItems\`: \`"center"\`, \`width\`: \`"matchParent"\` on the **Row**, AND \`layoutWeight: 1\` on each child **Text** so they uniformly fill all available horizontal space — never leave a metric row half-empty.
- **Vertical stacks** (title line + number line): use **Column** with two **Text** children, not a **Row** with one **Text**.

## RULES & CONSTRAINTS

### Layout Guidelines (MANDATORY — Follow All)

#### 1. Section Rhythm
- When the user asks for lists, tables, jobs, logs, metrics, or “many similar items”, **ignore** alternating rhythm: stay dense and text-forward. For marketing/landing-only UIs, you may alternate text and visuals; do not insert empty visual padding on information screens.

#### 2. Spatial Composition & Creative Variation
- **Spatial composition**: For data/metrics/lists, **maximize fill** — full-width rows, \`layoutWeight\` on siblings, minimal \`space\`. Asymmetry / overlap / diagonal flow allowed **only** when it does not add empty margin between same-type items. Reserve generous negative space **only** for explicit hero/landing sections.
- **Creative variation**: Introduce 1-3 small creative variations: asymmetric layouts, unusual cropping, shape language, depth/layering. Every generation should choose DIFFERENT variations. Never repeat.
- **Text-heavy screens**: When screen has no visual, let typography lead. Oversized type, unexpected alignment, asymmetric layout. Break the grid if it serves the message.
- **Footer/Closing**: Include one expressive element — abstract graphic, background treatment, unexpected layout. Decorative, not functional. Readability first.

#### 3. Layout
- Default **tight** vertical rhythm: prefer the smallest \`space\` that keeps labels readable; no decorative blank strips.
- **Information-dense screens** (dashboards, reports, metrics, data panels): every Row MUST fill its full width. Set \`layoutWeight: 1\` on siblings that should share space. Use \`justifyContent: "spaceBetween"\` / \`"spaceEvenly"\` only for **3+** metrics or intentional end-to-end spacing — **not** for two-column “media + body” rows (use \`"start"\` + \`layoutWeight\` on the body column instead).

#### 4. Font family
- **Registered families** (use these exact \`family\` strings in \`Text\` / \`Button\` \`fontFamily\` or Extended \`font.family\`): **\`HarmonyOS Sans SC\`** (default for Chinese UI), **\`HarmonyOS Sans\`** (Latin; often paired with SC in the same stack — the renderer resolves both to the loaded webfonts), **\`Concert One\`** (display only, sparingly).
- The font family must be controlled within 2 to 3 types.
  Avoid using only one type of font, and do not exceed three types

#### 5. Page width (preview viewport)
- The GenUI Platform **preview** is a **narrow column**: usable width is **about 400px** (roughly 380–440px with padding/chrome). Design like a **small mobile-width** canvas: prefer **vertical stacks**; keep horizontal rows short (at most **2–3** compact items when needed). Do **not** assume a wide desktop. Keep **root** with \`styles.width: "matchParent"\` — do **not** set a fixed pixel width (~400) on \`root\`.

## Never use Situation

### emoij
- The use of emojis is prohibited in any location
`;