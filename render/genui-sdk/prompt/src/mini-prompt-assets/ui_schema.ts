export const UI_SCHEMA_PROMPT = `
## AVAILABLE COMPONENTS

Component **type** strings below are the **third** segment in each **updateComponent** line: \`{"<surfaceId>", "<componentId>", "<Type>", { props }, [ children ]? }\` (after **createSurface**). Card **justifyContent** uses values like \`space_between\`; **Row** uses \`spaceBetween\` — see schema.

### Layout Components

**Card** - Container card for content sections with flexible layout options.
Props: {
  title?: string,
  description?: string,
  width?: number | "matchParent",
  height?: number | "matchParent",
  fill?: string,
  strokeThickness?: number | { "top"?: number; "right"?: number; "bottom"?: number; "left"?: number },
  strokeColor?: string,
  layout?: "vertical" | "horizontal",
  justifyContent?: "flex_start" | "center" | "flex_end" | "space_between" | "space_around",
  alignItems?: "flex_start" | "center" | "flex_end" | "stretch",
  gap?: number,
  padding?: number | [number, number] | [number, number, number, number],
  radius?: number | [number, number, number, number],
  backgroundImage?: string,
  backgroundBlendMode?: string,
  backgroundPosition?: string,
  backgroundSize?: string
}
Key Points:
- Default border + shadow: **root Card** and **one level of child Cards** (e.g. section blocks under the root). **Deeper** nested Cards omit the default border unless **strokeThickness** and **strokeColor** are set — use that to avoid triple-stacked heavy frames.
- **fill** (background): a **solid hex** (e.g. \`"#FAFAF7"\`) **or** a full CSS \`background\` value, including **\`linear-gradient(...)\`** / **\`radial-gradient(...)\`**. Use one JSON string for the whole gradient; **no line breaks** inside the string; keep syntax valid for the browser.
- **backgroundImage** (optional): URL served by the host (e.g. \`"/background_assets/ui_plum_blossom.png"\`). The image is **blended** with **fill** using **backgroundBlendMode** (default \`multiply\` / 正片叠底 so the image merges with the paper-like base instead of looking pasted). Omit **fill** when using an image to keep the default light gradient under the image; or set **fill** to a warm off-white hex for a rice-paper look. Prefer **one** decorative Card per section — do not repeat the same large **backgroundImage** on every nested Card.
- **backgroundBlendMode** (optional): CSS value; default is \`multiply\`. Try \`overlay\` or \`soft-light\` for a softer merge. Use \`normal\` only if you need the raw photo look.
- **backgroundPosition** / **backgroundSize** (optional): tune cropping (e.g. \`"bottom right"\`, \`"cover"\`) so busy areas stay away from text.
- 'layout' sets flex direction: "vertical" = column, "horizontal" = row
- 'gap' is spacing between children in pixels
- 'width'/'height': number values in pixels or "matchParent"
- 'radius' is corner radius in pixels (optional; default 12): a **single number** for uniform rounding, or a **4-tuple** \`[topLeft, topRight, bottomRight, bottomLeft]\` for per-corner radii
- **Renderer defaults** (when you omit props): Card inner \`gap\` **6** px, Card \`padding\` **14** px; Row/Column \`gap\` **6** px; **root** Card fills host width when \`width\` is omitted. Prefer **explicit** \`gap\`/\`padding\` in the **6–12** range for most screens; use larger values only for sparse or expressive layouts.
- **Full width**: Root and each **section** Card should set \`width\`: \`"matchParent"\`. Nested **Row**/**Column** that hold that section's main content should too.
- **Vertical Card + \`alignItems\`**: \`"flex_start"\` makes each child only as wide as its content → **large empty margin on the right**. For normal dashboards/reports use \`"stretch"\` (omit or set explicitly). Use \`flex_start\` only for deliberate narrow strips.
- **Two equal-width columns**: Prefer a parent **Card** with \`layout\`: \`"horizontal"\`, \`width\`: \`"matchParent"\`, and **two** child **Card**s (each \`width\`: \`"matchParent"\`). The host splits horizontal space between them. A **Row** of two Cards keeps each card content-sized unless you rely on other tricks — use **horizontal Card** for side-by-side panels.
- MUST have children array (can be empty)

**Row** - Horizontal flex layout container. **No background color, no border, no shadow** — use for grouping and alignment only; wrap content in Card when you need a visible frame.
Props: {
  space?: number,
  justifyContent?: "start" | "center" | "end" | "spaceBetween" | "spaceAround" | "spaceEvenly",
  alignItems?: "top" | "center" | "bottom",
  width?: number | "matchParent",
  height?: number | "matchParent",
  layoutWeight?: number,
  margin?: number | { top?: number, bottom?: number, left?: number, right?: number },
  padding?: number | { top?: number, bottom?: number, left?: number, right?: number },
  backgroundColor?: string,
  borderRadius?: number | { topLeft?: number, topRight?: number, bottomRight?: number, bottomLeft?: number },
  visibility?: "visible" | "hidden" | "none"
}
Key Points:
- \`space\` is gap between children in pixels (default 8).
- \`justifyContent\` / \`alignItems\` use Extended enum values (e.g. \`"spaceBetween"\`, \`"top"\`).
- Use \`layoutWeight: 1\` + \`width: "matchParent"\` on a child to let it grow inside the Row.
- MUST have children array (can be empty)

**Column** - Vertical flex layout container. **No background color, no border, no shadow** — use for stacking and alignment only; wrap content in Card when you need a visible frame.
Props: {
  space?: number,
  justifyContent?: "start" | "center" | "end" | "spaceBetween" | "spaceAround" | "spaceEvenly",
  alignItems?: "top" | "center" | "bottom",
  width?: number | "matchParent",
  height?: number | "matchParent",
  layoutWeight?: number,
  margin?: number | { top?: number, bottom?: number, left?: number, right?: number },
  padding?: number | { top?: number, bottom?: number, left?: number, right?: number },
  backgroundColor?: string,
  borderRadius?: number | { topLeft?: number, topRight?: number, bottomRight?: number, bottomLeft?: number },
  visibility?: "visible" | "hidden" | "none"
}
Key Points:
- \`space\` is gap between children in pixels (default 12).
- MUST have children array (can be empty)


### Display Components

**Text** — Body copy, labels, metrics. Renders as **plain text** (no border, no background).
Props: {
  content: string,
  /** Optional absolute \`http://\` / \`https://\` link; maps to A2UI \`action.functionCall\` + \`openUrl\` for inline tappable text. */
  openUrl?: string,
  fontSize?: number,
  fontWeight?: "300" | "400" | "500" | "600" | "700",
  fontColor?: string,
  textAlign?: "start" | "center" | "end" | "justify",
  textOverflow?: "ellipsis" | "clip" | "marquee" | "none",
  maxLines?: number,
  wordBreak?: "normal" | "breakAll" | "breakWord" | "hyphenation",
  maxFontSize?: number,
  fontScaleMode?: "followSystem" | "custom",
  minFontScale?: number,
  maxFontScale?: number,
  decoration?: {
    type: "none" | "underline" | "overline" | "lineThrough",
    color?: string,
    style?: "solid" | "doubleE" | "dotted" | "dashed" | "wavy"
  },
  width?: number | "matchParent",
  layoutWeight?: number,
  margin?: number | { top?: number, bottom?: number, left?: number, right?: number },
  backgroundColor?: string,
  visibility?: "visible" | "hidden" | "none"
}
Key Points:
- **Do not** try to simulate buttons or chips with Text — it will not draw boxes. Use Card + Text for grouping.
- \`fontSize\` is in pixels; use larger size / heavier fontWeight for primary numbers, smaller for captions.
- \`fontColor\` is text color hex (e.g., \`"#0F172A"\`, \`"#E11D48"\` for emphasis).
- \`textOverflow: "ellipsis"\` requires either \`maxLines\` or a fixed \`width\`.

**Image**
Props: {
  src: string,
  aspectRadio?: number,
  objectFit?: "fill" | "contain" | "cover" | "auto" | "none" | "scaleDown"
    | "topStart" | "top" | "topEnd" | "start" | "center" | "end"
    | "bottomStart" | "bottom" | "bottomEnd" | "matrix",
  width?: number | "matchParent",
  height?: number | "matchParent",
  layoutWeight?: number,
  borderRadius?: number | { topLeft?: number, topRight?: number, bottomRight?: number, bottomLeft?: number },
  margin?: number | { top?: number, bottom?: number, left?: number, right?: number }
}
- aspectRadio: 指定当前组件的宽高比
- objectFit: 字符串枚举值
"fill"：不保持宽高比进行放大缩小，使得图片或视频充满显示边界，对齐方式为水平居中,
"contain"：保持宽高比进行缩小或者放大，使得图片或视频完全显示在显示边界内，对齐方式为水平居中,
"cover"：保持宽高比进行缩小或者放大，使得图片或视频两边都大于或等于显示边界，对齐方式为水平居中,
"none"：保持原有尺寸进行显示，对齐方式为水平居中,
"scaleDown"：保持宽高比进行显示，图片或视频缩小或者保持不变，对齐方式为水平居中

### Interaction Components

**Button** - Clickable button.
Props: {
  label: string,
  enabled?: boolean,
  /** Absolute \`http://\` or \`https://\` URL; mapped to A2UI \`action.functionCall\` + \`openUrl\` on the host. Omit only when no URL exists for this control in structured input (see **Structured input → openUrl** below). */
  openUrl?: string,
  fontSize?: number,
  fontWeight?: 100 | 300 | 400 | 500 | 700 | 900,
  maxFontSize?: number,
  fontScaleMode?: "followSystem" | "custom",
  minFontScale?: number,
  maxFontScale?: number,
  width?: number | "matchParent",
  height?: number | "matchParent",
  layoutWeight?: number,
  margin?: number | { top?: number, bottom?: number, left?: number, right?: number },
  backgroundColor?: string,
  borderRadius?: number,
  visibility?: "visible" | "hidden" | "none"
}
Key Points:
- \`enabled\` defaults to true; set false to show a disabled state.
- **Do not** use \`actionText\`; use \`openUrl\` for opening a link (see \`openUrl\` above). For inline link-like **Text**, you may also set \`openUrl\` on **Text** (same mapping).

**Structured input → \`openUrl\` (binding)** — when the user's JSON / business payload includes a link field with **webURL** or **webUrl** for a given affordance, the **Button** or **Text** that represents that affordance **must** set **\`openUrl\`** to that same absolute \`http://\` / \`https://\` string (one control → same source URL as A2UI extended \`action.functionCall\` + \`openUrl\`).
- **Per-row CTAs**: e.g. \`listSubTitle3ButtonLink1.webURL\` for 「电话咨询」 on that list row → the **Button** in **that** row **must** include **\`openUrl\`** with that value. Do **not** wire only 「更多」 from \`moreLink.webURL\` while leaving row phone buttons without **\`openUrl\`** when the row payload includes a phone link.
- **Header / 「更多」**: \`moreLink.webURL\` (or paths like \`globalContent.moreLink.webURL\`) → **Text** or **Button** for 「更多」 with **\`openUrl\`**.
- **Row / detail taps**: when the product uses \`listItemLink.webURL\` (or similar) for opening a detail page, the tappable **Text**/**Button** for that row should use **\`openUrl\`** from that field when present.
- **Omit \`openUrl\`** only when the structured payload has **no** URL for that control (e.g. disabled, or host-only action with no webURL field), not to save tokens.

**Radio** - Radio button group.
Props: {
  label: string,
  name: string,
  options: string[]
}

**Select** - Dropdown select.
Props: {
  label: string,
  name: string,
  options: string[],
  placeholder?: string
}

**Checkbox** - Checkbox input.
Props: {
  label: string,
  name: string,
  checked?: boolean
}

**Input** - Single-line text input.
Props: {
  label: string,
  name: string,
  type?: "text" | "email" | "password" | "number",
  placeholder?: string
}

Key Points (form controls):
- **Radio**: \`options\` is the list of choices; all radios share \`name\`. Omit children on these nodes (they are leaf controls).
- **Select**: \`options\` becomes \`<option>\` entries; \`placeholder\` adds a disabled first option with empty value.
- **Checkbox**: \`checked\` sets initial checked state (boolean).
- **Input**: \`name\` is the form field name; \`type\` defaults to \`"text"\` if omitted.
`;
