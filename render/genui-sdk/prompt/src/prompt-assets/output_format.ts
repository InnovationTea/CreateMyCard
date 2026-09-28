export const OUTPUT_FORMAT_PROMPT = `
## Output Rules

### Ultra-compact UI (MANDATORY in emitted JSON)
- **Single-line fields**: Prefer one \`Extended.Text\` per data row with inline separators (\` | \`, \` · \`) instead of stacking one field per line when everything fits one line.
- **Homogeneous lists**: N similar entries → **one** parent (one \`Extended.Column\`); each entry is a \`Text\` or \`Row\`. Keep \`gap\`/\`space\` small (2–6) between entries.

### Row — media + text (no misalignment)
- For **left image / right copy** (stores, feeds): \`Extended.Row\` with \`styles.justifyContent: "start"\` (or omit), \`styles.width: "matchParent"\` on the Row; fixed numeric \`width\` on **Image**; **Column** for copy with \`styles.layoutWeight: 1\` and \`styles.width: "matchParent"\`. **Do not** set \`justifyContent: "spaceBetween"\` when there are only two Row children.

### First turn (empty UI)
Emit **JSONL**: one logical line per JSON object (valid JSON on each line).
1. **createSurface** — \`{ "version": "v0.9", "createSurface": { "surfaceId": string } }\`
2. **updateComponents** — either:
   - \`{ "version": "v0.9", "updateComponents": { "surfaceId": string, "component": Component } }\` — **one line = exactly one component**, or
   - \`{ "version": "v0.9", "updateComponents": { "surfaceId": string, "components": Component[] } }\` — batch components in one line.

Each \`Component\` must use \`component\` from **AVAILABLE COMPONENTS** (e.g. \`Extended.Text\`, \`Extended.Button\`, \`Extended.Column\`). Include \`id\`, \`component\`, type-specific props, and \`styles\`. **Common Styles** in \`styles\`: \`backgroundImageSizeWithStyle\`, \`flexShrink\`, \`width\` (number or \`"matchParent"\`), \`height\` ("matchParent").

**Preview width (mandatory):** The outermost layout (usually \`id\` \`root\`) MUST use \`styles.width\`: \`"matchParent"\` so the UI spans the full preview area. Do **not** use a small fixed pixel \`width\` on \`root\`. Use numeric \`width\` / \`height\` only for inner sections (buttons, nested columns).

---

Generate JSONL:
`;
