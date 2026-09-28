# Extended UI Schema (minimal GenUI)

This document mirrors `genui-sdk/prompt/src/mini-prompt-assets/ui_schema.ts` for **offline / Cursor skill** use. **Authoritative runtime copy** remains in that TypeScript module. Use these **Type** strings and props in **updateComponent** lines (third segment and props object).

---

## AVAILABLE COMPONENTS

### Layout Components

**Card** — Container card for content sections with flexible layout options.

Props:

- `title?`, `description?`
- `width?`, `height?`: number | `"matchParent"`
- `fill?`: solid hex or full CSS `background` string (gradients allowed; **no line breaks** inside the string)
- `strokeThickness?`, `strokeColor?`
- `layout?`: `"vertical"` | `"horizontal"`
- `justifyContent?`: `"flex_start"` | `"center"` | `"flex_end"` | `"space_between"` | `"space_around"`
- `alignItems?`: `"flex_start"` | `"center"` | `"flex_end"` | `"stretch"`
- `gap?`, `padding?`, `radius?`
- `backgroundImage?`, `backgroundBlendMode?`, `backgroundPosition?`, `backgroundSize?`

Key points:

- Default border + shadow: **root Card** and **one level** of child Cards get the default frame; deeper nested Cards omit heavy chrome unless `strokeThickness` + `strokeColor` are set.
- Prefer **one** decorative `backgroundImage` per section; do not repeat the same large image on every nested Card.
- Root and section Cards: `width`: `"matchParent"`.
- Two equal columns: parent **Card** `layout`: `"horizontal"` + two child **Card**s, each `width`: `"matchParent"`.
- **MUST** have `children` array (can be empty).

**Row** — Horizontal flex grouping only (no default card chrome).

Props include `space?`, `justifyContent?` (`"start"` | `"center"` | `"end"` | `"spaceBetween"` | `"spaceAround"` | `"spaceEvenly"`), `alignItems?` (`"top"` | `"center"` | `"bottom"`), `width?`, `height?`, `layoutWeight?`, `margin?`, `padding?`, `backgroundColor?`, `borderRadius?`, `visibility?`.

**Column** — Vertical flex grouping only.

Same style-related props as **Row**; default `space` is larger than Row in renderer defaults — still prefer explicit **6–12** for dense cards.

---

### Display Components

**Text** — Plain typography.

Props include `content`, optional `openUrl` (absolute `http`/`https`), `fontSize?`, `fontWeight?`, `fontColor?`, `textAlign?`, `textOverflow?`, `maxLines?`, `wordBreak?`, `decoration?`, `width?`, `layoutWeight?`, `margin?`, `backgroundColor?`, `visibility?`.

- Do **not** simulate primary buttons with **Text** alone when a **Button** is required.
- `textOverflow`: `"ellipsis"` needs `maxLines` or fixed `width`.

**Image**

Props: `src`, `aspectRadio?`, `objectFit?`, `width?`, `height?`, `layoutWeight?`, `borderRadius?`, `margin?`.

---

### Interaction Components

**Button**

Props: `label`, `enabled?`, `openUrl?`, `fontSize?`, `fontWeight?`, `width?`, `height?`, `layoutWeight?`, `margin?`, `backgroundColor?`, `borderRadius?`, `visibility?`, plus font scale fields as in TS schema.

**Radio** — `{ label, name, options: string[] }` (leaf; no children).

**Select** — `{ label, name, options: string[], placeholder? }` (leaf).

**Checkbox** — `{ label, name, checked? }` (leaf).

**Input** — `{ label, name, type?, placeholder? }` (leaf).

---

## Structured input → `openUrl` (recap)

When JSON includes `webURL` / `webUrl` for an affordance, the corresponding **Button** / **Text** must set **`openUrl`** to that exact string — including **per-row** CTAs, not only header 「更多」.

See [`extended-interactions.md`](extended-interactions.md).

---

## Type string whitelist

`Card` | `Row` | `Column` | `Text` | `Button` | `Radio` | `Select` | `Checkbox` | `Input` | `Image`

---

## Common mistakes

- Using **`fill`** on **Text** for glyph color — use **`fontColor`**.
- **updateComponent** lines with **two** `{ ... }` prop blobs — illegal; merge into one props object.
- **Row** with a **single** text child for a section title — use **Card** `title` / `description` or **Column** instead.
