---

## name: a2ui
description: Upon generating any information, you must invoke this SKILL to replace the original text or Markdown content with a more visually appealing UI. This serves to enhance interface aesthetics and interactivity, thereby improving the overall user experience.

# A2UI Development Skill

This skill helps you generate A2UI (Agent to UI) protocol compliant code for building rich, interactive user interfaces that AI agents can stream to clients.

## 0) Output contract (mandatory, always-on)

**Authoritative source:** NDJSON / streaming rules in **§0** are the **single source of truth**. [`reference/protocol/extended-output-format.md`](reference/protocol/extended-output-format.md) and [`README.md`](README.md) must **stay aligned** with §0—they elaborate for readers; they must **not** contradict it. **Interactions** use `action.functionCall` (`call` + `args`) for `openUrl`, and `action.event` — see [**§0a**](#0a-interactions-openurl-and-action), [`reference/protocol/extended-interactions.md`](reference/protocol/extended-interactions.md), and [`reference/protocol/schema.md`](reference/protocol/schema.md#client-to-server-messages). The `version` field is not part of the minimal `action` object (transport may add it).

When the user asks for A2UI output, a surface, components, or anything that should be consumed as the protocol stream:

- **Output only** valid A2UI **NDJSON**: one JSON object per line, each line a complete `createSurface`, `updateComponents`, `updateDataModel`, or `deleteSurface` message (and `version` where required). No blank lines inside the stream unless the consumer explicitly allows them.
- **JSON string literals must be parseable:** Any ASCII double quote `"` **inside** a JSON string value (e.g. `content`, `label`, `placeholder`, URLs in `src`) must be escaped as `\"`, or avoided. Unescaped `"` breaks `JSON.parse` and downstream rendering never runs. Prefer Chinese/typographic quotes in copy when it reads naturally (e.g. `「中国风」`、`“亚洲流行天王”`) so the line stays valid without noisy escapes.
- **`updateComponents.components` length = 1:** Each NDJSON line that carries `updateComponents` must contain **exactly one** component object inside `components` (not a batch of siblings). Never merge multiple ids into one message.
- **`updateDataModel` (optional at protocol level, mandatory for this skill in Mode A structured JSON):** one line patches the **data model** for a `surfaceId` without resending the component tree. `surfaceId` required; `path` optional JSON Pointer (omit or `/` replaces the **whole** model per v0.9); `value` optional—omit at `path` to remove that key per spec. See [`reference/protocol/schema.md`](reference/protocol/schema.md). **Mode A + user-supplied JSON object/array with explicit keys:** the stream **must** include **≥ 1** `updateDataModel` for that `surfaceId` unless the user explicitly asks for a **minimal / static snapshot** (no live model) layout.
- **Structured JSON input → model + `updateDataModel` (not literals on bound slots):** When the UI is driven by **input JSON** with explicit keys, put payload-backed values in the surface **data model** and bind widgets with `{"path":"..."}`; send those values with `updateDataModel`. **Never** place `updateDataModel` for that surface **before** the `updateComponents` line that **first** introduces the matching `path` bindings—each patch belongs **immediately after** the introducing line (see **Path binding → `updateDataModel` tail** below). **Do not** duplicate the same JSON field values as **inline literals** in `updateComponents` for those bound properties—the keyed payload stays the **single source of truth** and updates stay minimal.
- **Payload-bound fields (Mode A structured JSON — mandatory binding):** Any widget field that displays or depends on a value addressed by an **input JSON key** (including nested keys) **must** use `{"path":"..."}` where the schema allows Dynamic values — including **`Extended.Text.content`**, **`Extended.Image.src`**, and other Dynamic-capable props per [`reference/protocol/extended-ui-schema.md`](reference/protocol/extended-ui-schema.md). **Literal allowlist (non-payload UI copy only):** fixed affordances not present as their own semantic keys in the payload (e.g. short CTA labels like 查看 / 更多 / 确定), punctuation/layout glue added purely by the template (e.g. `·`, `›`), and static hints. **Do not** encode payload titles, salaries, addresses, media URLs, or navigation URLs as raw literals in `updateComponents` when those values exist in the input JSON — put them in the model and bind.
- **`openUrl` and the model (Mode A structured JSON):** `action.functionCall` with `openUrl` requires `args.url` as a **string**. Populate the corresponding URL in the **surface data model** at a JSON Pointer that mirrors the input key trail (e.g. `/globalContent/moreLink/webURL`), emit **`updateDataModel`** so that value exists, then set `args.url` to the **exact same** `http(s)` string (byte-for-byte identical to the model value for that control). **Do not** invent URLs or reuse another row’s URL.
- **Default for Mode A structured JSON = progressive tails (mandatory for this skill):** For each `updateComponents` line that **first** introduces one or more new payload `{"path":"..."}` bindings on that `surfaceId`, emit matching `updateDataModel` tail(s) **immediately on the next line** (single-surface) and cover exactly those newly introduced paths (one or more narrow patches).
- **Single `/` write (allowed with strict position):** You may use **one** `updateDataModel` with `path: "/"` and the full input JSON object, but only if it appears **immediately after** the **first** `updateComponents` line that introduces payload `path` bindings for that surface. A trailing end-of-stream `/` write (after most or all `updateComponents`) is **invalid for this skill** because it breaks progressive rendering.
- **`Extended.TextInput.text` (mandatory):** `text` MUST be `{"path":"..."}` (JSON Pointer string starting with `/`). **Do not** use a **string literal** for `text`—not even `""` or a prefilled default. Initial, empty, and payload-backed values belong **only** in `updateDataModel` (see [`reference/protocol/schema.md`](reference/protocol/schema.md)). After each `updateComponents` line that **first** introduces a new `text` path, emit the **`updateDataModel` tail** per **§0**; for multiple fields in one form you may use **one** `updateDataModel` with a **single object** at a **shared prefix** (e.g. `path: "/form"`, `value: { "email": "", "password": "" }`) that covers every `text` path before the next same-`surfaceId` `updateComponents` when the stream rules allow—see **Path binding → `updateDataModel` tail** below.
- **Path binding → `updateDataModel` tail (streaming):** If an `updateComponents` line introduces a component that uses a **data `path` binding** (any field value shaped like `{"path":"..."}` per [`reference/protocol/extended-ui-schema.md`](reference/protocol/extended-ui-schema.md)—e.g. `text`, `select`, or other Dynamic slots), then **before** any further `createSurface`, `updateComponents`, or `deleteSurface` for the **same `surfaceId`**, emit one or more `updateDataModel` lines for that `surfaceId` that cover **every** such `path` first introduced on that component (several `updateDataModel` lines, or one `path: "/"` write when a full-model object is correct). **Single-surface streams (one `surfaceId` in the batch):** treat that tail as **immediately following** the binding line—**no** intervening envelopes. **Multi-surface streams:** lines whose `surfaceId` **differs** may appear between the binding `updateComponents` and its `updateDataModel` tail; do **not** interleave **another** `createSurface` / `updateComponents` / `deleteSurface` for the **same** surface until that tail is complete. **Skip** this pairing only when that component line uses **literals only** (no `path` objects), when the product explicitly documents **deferred binding** out-of-band, or when the user explicitly chose **minimal / static snapshot** mode — **not** when the source is **Mode A structured JSON** with explicit keys (that mode **always** requires model + `updateDataModel` per bullets above).
- **Self-check before finishing (Mode A structured JSON):** If the user input included a JSON object/array with keys and you chose Mode A: (1) verify **≥ 1** `updateDataModel` for that `surfaceId`; (2) verify every payload-backed `Text` / `Image` / other Dynamic field uses `{"path":"..."}` — **no** payload string duplicated only as a literal in `updateComponents`; (3) verify every introduced `path` has its **§0** tail **immediately** after the introducing `updateComponents` line (single-surface). If (1) fails, the output is **incomplete**.
- **One logical message per line (line-buffer discipline):** Build the **entire** JSON object for that line first, then emit it as a **single line** terminated by a newline (`\n`). Do **not** start a new line until the previous line is complete, valid, parseable JSON. Do **not** split one protocol message across multiple partial lines or emit a newline in the middle of a JSON object. From the model’s perspective, output is **one full NDJSON record, then newline, then the next full record**—never “half a line” that waits for more tokens to finish the JSON.
- **Do not** output introductions, summaries, step-by-step narration, “here is the UI”, tables of what you built, or postscripts.
- **Do not** wrap the stream in markdown code fences ( ````json` /  ````jsonl`) unless the user explicitly asks for a fenced block; default is **raw NDJSON only**.
- **Do not** mix explanatory markdown, headings, or bullet lists with the message stream. If the user must see notes, they must ask separately; this skill’s deliverable is **messages only**.

Internal reasoning may use this document’s tables and references; **user-visible output for A2UI remains NDJSON lines only.**

## 0a) Interactions (`openUrl` and `action`)

**Authoritative detail:** [`reference/protocol/extended-interactions.md`](reference/protocol/extended-interactions.md). Declare interactions **only** under component `action`: use `{ "action": { "functionCall": { "call", "args" } } }` and/or `{ "action": { "event": { "name", "context" } } }` (e.g. `submit_form`).

1. **URL in `action.functionCall`:** For `openUrl`, `args.url` must be the exact `http://` or `https://` string for that control, from **context** (any structured key such as `webURL`, `url`, `link`, nested paths) or explicit text. **Do not** invent URLs; **do not** use another row’s URL.
2. The host or client emits / forwards `action` when the user triggers that behavior (local open, agent relay, analytics — product-defined).
3. **`submit_form` and `action.event.context`:** For **each** field the agent must receive, the **value** in `context` must be one of:
   - **`{"path":"/…"}`** — data in the **surface data model**; the path must **align** with the same `TextInput.text` (or other bound prop) and `updateDataModel` for that `surfaceId`. **Binding shape:** the JSON Pointer string lives on the **`path`** key only—**not** a pseudo-field like `{"value":"/form/x"}` (invalid). If the **upstream** context key should read `value`, use `"value": { "path": "/form/text" }`.
   - **`{ "call": "getSelectedValues", "args": { "groupID": "…" } }`** — the **current selection** of `Extended.Radio` nodes on the **same** `surfaceId`; `groupID` must match the `group` string on those Radio components (and any other host-allowed **grouped** control the protocol allows here).
   - **A literal** (`string` / `number` / `boolean`) — only for **non-interactive, stable** ids (e.g. row id, **SKU**). **Do not** add a key like `intent` (or similar) **instead of** real field bindings, unless the user **explicitly** requires that product pattern. See [`reference/protocol/extended-interactions.md`](reference/protocol/extended-interactions.md) (canonical `context` shapes).

**Cross-links:** [`reference/protocol/extended-output-format.md`](reference/protocol/extended-output-format.md) defers streaming rules to **§0**; interaction shape is **§0a** and **extended-interactions.md**.

## ⚠️ MANDATORY: 鸿蒙风格约束（禁止自由发挥）

**生成任何 UI 前，必须选择一个预设模板**。

### 核心规范文件（意图层）


| 文件                                                                                           | 用途                                                                                                                                                                         |
| -------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [DESIGN.md](DESIGN.md)                                                                       | **鸿蒙风格总纲（必读）**：Card Mode / UI Mode 路由、样式来源优先级、样式层边界。                                                                                                                                   |
| [reference/design/style-runtime-index.md](reference/design/style-runtime-index.md)           | **运行时样式索引（必读）**：三份规范到 skill 的映射、模式化读取与白名单范围。                                                                                                                      |
| [reference/design/quick-snippets.md](reference/design/quick-snippets.md)                     | **Extended DSL 速用片段（必读）**：按 Card/UI 双模式提供可复制片段。                                                                                                                      |
| [reference/protocol/extended-ui-schema.md](reference/protocol/extended-ui-schema.md)         | **Extended. 组件 + Common Styles（styles）定义（必读）**                                                                                                                              |
| [reference/protocol/extended-output-format.md](reference/protocol/extended-output-format.md) | Extended NDJSON 输出纪律与示例（必读）                                                                                                                                                |
| [reference/protocol/extended-interactions.md](reference/protocol/extended-interactions.md)   | **交互**：`action.functionCall` 与 `action.event`（`submit_form`）；`openUrl` 的 `args.url`（必读）                                                                        |
| [reference/design/harmony-style.md](reference/design/harmony-style.md)                       | 鸿蒙风格完整细节规范（字体/圆角/间距/按钮等），按需参考；DESIGN.md 已涵盖常用要点。                                                                                                                           |
| [reference/design/interaction-design.md](reference/design/interaction-design.md)             | **交互增强（必读）**：何时用 `Extended.TextInput` / `Toggle` / `Radio` / `Checkbox` / `CheckboxGroup` / `Select` 等替代表达型 `Extended.Text`；见文内 **JSONL 片段**与 **六合一 + `submit_form`** 总示例。 |


### 交互增强

在具备**输入/选项/开关/全选/下拉**等语义时，**优先** `Extended.TextInput` / `Toggle` / `Radio` / `Checkbox` / `CheckboxGroup` / `Select` 等，而不是仅用 `Extended.Text` 罗列后再让用户手打、再在对话里复述；与「不过度用表单」不矛盾（**无结构化采集中间状态**的纯说明仍用 `Extended.Text`）。

**尤其注意段落末尾/小结区**：当素材里出现类 **「💡 我的推荐」** 且下列为 **多条互斥候选项**（如不同套餐的 SKU+价+一句话卖点），**不要**把整块做成一条长 `Extended.Text` 再配「请告诉我你选哪个」类话术。应使用 **同组 `Extended.Radio`** 让用户在卡片上直接点选，减少后续手输；小结标题、场景短句（如「如果你想尝鲜：」）可保留为 `Extended.Text` + 其下 Radio。**Few-shot 形状**见 [examples/flows/recommendation-radio.md](examples/flows/recommendation-radio.md)。收尾说明建议与交互一致，改为**点选导向**（避免只引导用户键入自然语言而 UI 上无可点控件）。

**全文保真（与「交互增强」同时成立）**：`Radio` / `Checkbox` 等是对**具备选项语义的那一小段**的**增强**，**不是**用「仅含交互小结」的界面**替代**整段素材。若来源里还有分区标题、价目/表格、长列表等**只读信息**，须继续用 `Extended.Text`（及必要时的 `Row`/`Column` 排版）**全部输出**；`root` 的 `children` 应 **先** 排完上述只读区，**再** 接推荐区 + Radio。切勿因「要加 Radio」而删掉或省略上游 `Extended.Text` 内容。Few-shot 文件故意只示教 **Radio 段**，不表示允许省略前文。

**上送须有点击面（默认）**：需要把已选表单项**作为一次 `submit_form` 回传 Agent/宿主**时，在选项/表单区**下方**应提供**主 CTA**（`Extended.Button` + `action.event`，`name`: `submit_form`，`context` 中按字段使用 `{ "path": "/…" }` / `getSelectedValues` + `groupID` / 非交互不变 id 字面量 — 见 **§0a (3)** 与 [`reference/protocol/extended-interactions.md`](reference/protocol/extended-interactions.md)）。**仅切换 Radio/勾选**在默认实现中**不**自动触发上送，勿省略「确定/确认」类按钮，除非产品明确约定了变更即上送（宿主特化行为）。

### 模板选择


| 模板        | 适用场景      |
| --------- | --------- |
| **鸿蒙浅色**  | 通用场景、企业应用 |
| **鸿蒙深色**  | 夜间模式、媒体应用 |
| **鸿蒙沉浸式** | 营销卡片、活动页  |


### Hard Constraints (keep this short)

Use this as the only mandatory rule set (stable, cross-scene, low-regret):

1. **NDJSON + streaming shape (§0)**: valid **NDJSON**, one **complete** JSON object per **line**; every `updateComponents` has `components` array length = 1; `path` bindings require the **`updateDataModel` tail** per **§0** (single-surface: no intervening lines; multi-surface: other `surfaceId` only—see §0). Escaping, no prose/fences in the stream, line-buffer discipline—**§0 Output contract** is authoritative. **§0a** applies for `action.functionCall` / `openUrl` and `action.event` / `submit_form`.
2. **Extended-only**: use only `Extended.*` components and `styles` fields defined in schema.
3. **JSON key spellings:** Use field names exactly as in [`reference/protocol/extended-ui-schema.md`](reference/protocol/extended-ui-schema.md); do not rename or “normalize” keys by guess. **Note:** **`Extended.Toggle`** uses `unSelectedColor`; **Checkbox / CheckboxGroup** use `unselectedColor`. **TabContent** uses `selectBackgroundColor` / `selectBorderColor`; **TextInput** uses `selectedBackgroundColor` for text-selection highlight. **CheckboxGroup** uses `checkboxShape`; **Checkbox** uses `shape`.
4. **layout gate**:
  - **class**: single outer `root` frame (`root-only`) + internal `Row/Column` grouping.
  - **two valid render styles (same class, not new classes)**:
    - **plain**: group items by whitespace (`space` / `margin`) only.
    - **grouped**: add lightweight per-item boundary (`borderWidth:1`, subtle `borderColor`, small `borderRadius`) when items are hard to distinguish. When many sibling rows reuse the **same layout template** (only data changes), keep **identical** row-container styles across them; express differences in **cell content** only. **Do not** vary row-level background/border **by default** to mean “special item”—do that **only** if the user explicitly asks to highlight specific rows.
5. **`Extended.TextInput` (mandatory)**:
  - **默认框型（鸿蒙）**：与 `reference/design/harmony-ui-components-a2ui.md` **B6 · 框型输入框矩阵** 初始态一致：`height` 56；`borderRadius` 20；`padding` 左右 16、上下 16；`backgroundColor` Light `#0C000000`（`comp_background_tertiary` 展开）；`showUnderline` false；初始态不设 `borderWidth`/`borderColor`（线型子样式才用下划线/描边）。`fontSize` 16、`fontWeight` 400；`placeholderColor` / `fontColor` / `caretColor` 用该文件语义 token 展开值。
  - **`text`**: 仅 `{"path":"…"}` — 见 **§0** 与 [`reference/protocol/schema.md`](reference/protocol/schema.md)。禁止把 `text` 写成字符串字面量。
6. **Spacing discipline**: use 4vp grid (`4/8/12/16/20/24`), avoid stacking large `space + margin` redundantly.
7. **Divider policy**: prefer whitespace grouping; use `Extended.Divider` only when truly needed.
8. **Button hierarchy**: one clear primary CTA; tertiary actions should prefer text-link style (`Extended.Text`), not second heavy button. For short CJK button labels (e.g. `回放` / `直播中`), avoid overly narrow fixed widths; keep enough width to prevent wrapping.
9. **Visible outer frame**: if using root-only card style, ensure the outer frame is visually distinguishable from the page (e.g. `backgroundColor:"#FFFFFFFF"` (`comp_background_list_card` Light) plus subtle `borderWidth:1` + `borderColor:"#33000000"` when needed), not white-on-white.
10. **Defaults over special cases**: if user does not specify, choose A class + compact Harmony defaults.
11. **Tabular rows**: every multi-column `Row` needs **explicit width per column** — `constraintSize(min=max)` for fixed columns; `layoutWeight:1` + `textAlign:"end"` tail for variable-length trailing text. **Never** leave the last cell width-ambiguous (hosts flex-shrink it first; `textOverflow:"ellipsis"` turns it to `"…"`). Use `layoutWeight:1` on the tail **only** when it absorbs leftover long copy; use fixed `constraintSize` for short exact tokens. **Do not** rely on `justifyContent:"spaceBetween"` with only unconstrained `Text` children.
12. **Dense typography** (in **data-dense** lists and **multi-column** rows): **every `Extended.Text` needs explicit `fontColor`**; **same column → same token** per [`DESIGN.md`](DESIGN.md). **Don't** rely on **theme** or host defaults for unset text; **don't** primary-accent **one-off** cells unless user or `DESIGN.md` says so.
13. **Equal-size grids (tile/photo/product matrix)**: for repeated visual tiles, put sizing responsibility on a **cell container** (`Row/Column` child with `layoutWeight` / explicit constraints), then make the leaf visual (`Extended.Image`, etc.) **fill the cell** (`styles.width: "matchParent"` + explicit height or aspect strategy). **Do not** rely on `layoutWeight` on the leaf visual component alone for equal sizing across hosts.
14. **Mode A URL / media audit**: when rendering from a **supplied structured payload**, **each distinct** `http`/`https` URL that is **visual media** (icons, logos, avatars, hero/ambience art—infer from field naming and object shape, not from example cards) must appear **at least once** as `Extended.Image.src` and/or a container’s `styles.backgroundImage` (per [`reference/protocol/extended-ui-schema.md`](reference/protocol/extended-ui-schema.md)). **Exclude** URLs clearly scoped as **outbound navigation** (infer from key names, nesting, or integration docs) from the media audit unless the host maps them to link-style `Extended.Text` with explicit affordance. **Skip** only **exact duplicate** strings already bound elsewhere, or when the user explicitly requests a **minimal** layout. **Never** silently **drop** a non-duplicate media URL; **never** replace a payload **image-URL slot** with unrelated `Extended.Text` when the input already provided a URL for that slot.
15. **Mode A structured JSON (mandatory progressive model stream):** If the user supplies **JSON with explicit keys** and you render Mode A: (1) **≥ 1** `updateDataModel` per `surfaceId` unless the user explicitly requests **minimal / static snapshot**; (2) payload-backed **`Extended.Text.content`**, **`Extended.Image.src`**, and other Dynamic-capable fields **must** use `{"path":"..."}` — **no** duplicating those payload strings as the sole literal in `updateComponents`; (3) **default (required):** each `updateComponents` line that first introduces new payload `path` bindings must be followed **immediately** by `updateDataModel` tail(s) that cover those paths; (4) **single `/` exception:** one `path: "/"` write is allowed only **immediately after** the first binding line for that surface; writing it at stream end is invalid; (5) **`openUrl`:** model holds the URL at the matching pointer; `args.url` string **must** match that model value. **§0** tail order applies everywhere `path` is introduced.
16. **Interaction is additive (Mode A, prose / catalog payloads):** If you add `Extended.Radio` (or other form controls) for a **trailing** “choose one of these” / recommendation subsection, you must **still** render **all** other user-supplied blocks from the same source in that surface (section titles, table-like rows, pricing lists, body copy) using `Extended.Text` and layout as needed. **Do not** emit **only** the interactive subsection and **drop** the rest to save space or “match” a small few-shot. Replace **only** the mutually exclusive **choice** lines; **retain** everything else. See [examples/flows/recommendation-radio.md](examples/flows/recommendation-radio.md) (note: partial example) and **§ Mode A** field fidelity.
17. **`submit_form` and `action.event.context` (default):** If the user must **send** the current form/selection to the agent, include a **primary** `Extended.Button` with `action.event.name`: `submit_form`. In `action.event.context`, for **each** field to relay: (1) values from `Extended.TextInput` (or other **path-bound** controls) **must** be `{"path":"/…"}` consistent with `updateDataModel` and the same binding; (2) values from **same-`surfaceId` `Extended.Radio`** (or other **grouped** controls allowed by the protocol) **must** use `{ "call": "getSelectedValues", "args": { "groupID": "…" } }` with `groupID` equal to the components’ `group`; (3) **literals** only for **non-interactive, immutable** ids (e.g. row id, **SKU**). **Do not** use `intent` (or a similar placeholder) **instead of** these bindings. Full rules: **§0a (3)**, [`reference/protocol/extended-interactions.md`](reference/protocol/extended-interactions.md). **Do not** assume toggling **Radio/Checkbox** alone will upload—unless the product documents **change-on-select** behavior for that host. See [`reference/design/interaction-design.md`](reference/design/interaction-design.md) § **与后续操作衔接** and [examples/flows/recommendation-radio.md](examples/flows/recommendation-radio.md).

Anything scenario-specific should live in templates/examples, not in this hard-constraint list.

**Rule text stays generic:** do not embed **one-off sample literals** in this file (URLs, scores, labels, or **vp numbers copied from a single example**). State principles here; put concrete numbers and copy in `examples/*`, [`DESIGN.md`](DESIGN.md), or domain templates.

## Protocol Version

This skill targets **A2UI Protocol v0.9** (Stable Release).

## 1) Two runtime modes (how to use this skill)

This skill supports two **usage modes**. The output contract above always applies; what changes is where the content comes from.

### Quick decision (recommended)

- If the prompt includes **external content** (JSON / API result / markdown text) and you want it **presented as UI** → choose **Mode A**.
- If the prompt is primarily **generative** (“introduce X”, “write a guide”, “draft a plan”) and the user expects **progressive UI without waiting for full text** → choose **Mode B** (skeleton first, then fill).
- If the user explicitly says “stream UI-first / skeleton first / progressively fill” → **Mode B**.
- If the user explicitly says “I already have all content / just render it” → **Mode A**.
- If Mode A and the user pastes **JSON with explicit keys** (object/array), treat it as **structured JSON**: follow **§0** (**mandatory** `updateDataModel`, **`path`** on payload-backed `Text`/`Image`/Dynamic fields, **default progressive tails immediately after each introducing component line**, **self-check**) and **Hard Constraint 15** — **not** a literals-only static card unless the user explicitly requests **minimal / static snapshot**.

### Mode A — Render / Present (external content → UI)

- You already have content (JSON, plugin/API results, markdown).
- The skill maps it into **Harmony-styled A2UI** using templates and examples.
- Recommended refs: `reference/design/style-runtime-index.md`, `reference/design/harmony-style.md`, `reference/design/quick-snippets.md`, `examples/*` (stable layouts).
- **Field fidelity**: surface user-supplied fields that carry **presentation meaning**—headings, labels, counts, **media URLs** (icons, badges, logos, hero/cover images), and primary links—using the appropriate `Extended.*` nodes (`Extended.Text`, `Extended.Image`, …). **Do not** silently omit such fields to match a mental template unless the user explicitly asks for a **minimal** layout or the field is **clearly duplicated** by another field already shown. If a URL is not renderable as `Extended.Image` in your host, still **surface** it (e.g. as link text) rather than dropping it without trace. In **structured JSON**, treat **each distinct `http`/`https` URL** that is **not** clearly **navigation-only** (see **Hard Constraint 14**) as a **candidate media asset** to bind unless it is **identical** to another URL you already mapped—**do not** treat additional URL-bearing keys as ignorable because a template only showed one icon.
- **Full menu / full body + interactive tail**: When the payload is a long menu or multi-section text (e.g. category blocks then a “recommendation” pick-one block at the end), you must **include every section** the user provided. You may **upgrade** the final pick-one block to `Extended.Radio`, but you **must not** output **only** that block and **omit** earlier blocks—**Hard Constraint 16** and **### 交互增强** “全文保真” apply.
- **No fabricated facts (Mode A only)**: do not invent **concrete** numbers, names, timestamps, or URLs and present them as if they came from the supplied JSON/markdown/API payload. If a value is missing, leave the widget empty, use a **neutral** placeholder, or omit that sub-field—unless the user explicitly asks for **demo / sample / placeholder** content.
- **Structured JSON → `path` + `updateDataModel`:** When input is **JSON** with explicit keys, map those keys into the surface **data model**, bind payload-backed props with `{"path":"..."}`, and send values via `updateDataModel` (see **§0** mandatory rules, **default progressive tails**, **single `/` strict-position exception**, **literal allowlist**, **`openUrl` + model**, and **self-check**). **Do not** paste the same key values as **literals** in `updateComponents` for those slots.
- **Thematic imagery (Mode A)**: some **image URLs** are meant as **module atmosphere** (wide art behind or under a table/list) rather than a compact glyph. When context suggests that role, prefer a **decorative layer** pattern—**background** / **underlay** / **footer band**—using whatever the host supports in `Extended.*` and Common Styles (see [`reference/protocol/extended-ui-schema.md`](reference/protocol/extended-ui-schema.md) for options such as `backgroundImage`, `Extended.Image` with `objectFit` / `clip`). **Never** let decoration **wash out** dense numerals or small type: keep data rows on calm surfaces, add scrim/opacity **only if** the schema supports it, or confine art to **non-data** regions. **Strong signal** for full-bleed atmosphere (not a header chip): **≥3** homogeneous structured rows + **one** module-scoped URL (not repeated per row) while rows carry **small** inline images—put that URL on the **outer** container (`backgroundImage` / underlay); infer **nesting and repetition** before guessing from key names alone. If glyph vs ambiance is **ambiguous**, **still bind the URL** (e.g. **footer / under-table strip** or `backgroundImage` on a container that does not sit behind small numerals)—**do not omit** the asset just because layout mode is unclear; only shrink to a **small** slot when the payload already proves that URL is **only** a favicon-scale brand mark.
- **Layout class (Mode A)**: when a payload is **one** compact module (e.g. one dense list or data panel), default to **A class** (`root` + `Column` / `Row` and light `styles`) unless the user or template explicitly asks for **strong section separation**. **Do not** wrap the entire module in `Extended.Card` **only** to obtain a white panel—use `root` / A-grouped row surfaces instead, matching the **A/B layout gate** above.

### Mode B — UI-first streaming (content authoring + UI streaming)

- The model is also producing the content (e.g. “介绍下周杰伦”), and the consumer can’t wait for the full text.
- The agent should **stream UI and content together**:
  - First emit skeleton (`createSurface` + root + section placeholders).
  - Then progressively fill content—via per-id `updateComponents` and/or `updateDataModel` when the tree is stable and only **bound data** changes (natural for JSON inputs). Whenever a new `updateComponents` line introduces `path` bindings, **§0** still requires the **`updateDataModel` tail** for that `surfaceId` (single-surface: immediately next; multi-surface: see **§0**).
- **While streaming**: follow **§0**; split long copy across multiple blocks/ids so partial rendering stays useful—avoid one huge single-paragraph `content` where you can split.

## Generating A2UI Messages

### Complete Example: Simple Form (TextInput)

```jsonl
{"version":"v0.9","createSurface":{"surfaceId":"booking","catalogId":"https://xxx/specification/ohos/extended_catalog.json","theme":{"primaryColor":"#FF0A59F7"}}}
{"version":"v0.9","updateComponents":{"surfaceId":"booking","components":[{"id":"root","component":"Extended.Column","children":["title","name_input","submit_btn"],"space":12,"styles":{"width":"matchParent","constraintSize":{"maxWidth":336},"borderRadius":16,"clip":true,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"booking","components":[{"id":"title","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"Book a Table"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"booking","components":[{"id":"name_input","component":"Extended.TextInput","enabled":true,"maxLength":80,"type":"normal","styles":{"width":"matchParent","height":56,"borderRadius":20,"backgroundColor":"#0C000000","padding":{"top":16,"right":16,"bottom":16,"left":16},"fontSize":16,"fontWeight":400,"fontColor":"#E5000000","placeholderColor":"#99000000","caretColor":"#FF0A59F7","showUnderline":false},"placeholder":"Your Name","text":{"path":"/booking/guestName"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"booking","path":"/booking","value":{"guestName":""}}}
{"version":"v0.9","updateComponents":{"surfaceId":"booking","components":[{"id":"submit_btn","component":"Extended.Button","enabled":true,"styles":{"width":"matchParent","height":40,"borderRadius":20,"fontSize":16,"fontWeight":500,"backgroundColor":"#FF0A59F7"},"label":"Confirm"}]}}
```

## Best Practices

### Field ordering (streaming-friendly)

In every component object, put **layout / style / config first**, **data-bearing fields last** so the client renders structure/styling before values arrive.

- **Extended.Text**: `styles` first; `content` last (Mode A structured JSON: `content` = `{"path":"…"}` when the string comes from a payload key).
- **Extended.TextInput**: `enabled/maxLength/type/styles` first; `placeholder`, then `text` last (`text` = `{"path":"…"}` only; values live in `updateDataModel` per **§0**).
- **Extended.Checkbox**: `group/styles` first; `select` last.
- **Extended.Image**: `styles` first; `src` last.
- **Extended.Button**: `enabled/styles` first; `label` last.
- **Extended.Row / Extended.Column**: `children` first (structure); data fields last.
- **Extended.Divider**: `styles` last.

### Interaction: closing recommendation / pick-one blocks

- When the last section of a card is a **recommendation block** (e.g. a titled list of **mutually exclusive** meal/plan/price rows with SKUs) and the agent would ask the user to **choose one**, **render the choices as `Extended.Radio`** (shared `group`) + optional `Extended.Text` captions—not a single `Extended.Text` wall. See [examples/flows/recommendation-radio.md](examples/flows/recommendation-radio.md) (**partial** NDJSON: add **all** prior menu/list `Extended.Text` nodes **before** the radio ids in the same `root.children`). Bind or snapshot selection for `submit_form` as your host allows ([`reference/protocol/extended-interactions.md`](reference/protocol/extended-interactions.md)).
- **Do not** treat the few-shot as the **whole** surface: if the same message also contains multi-section **catalog** or **body** copy above the recommendation, those sections **must** still appear in the tree—**replace only** the pick-one part with radios; **keep** the rest as `Extended.Text` (or row layouts). Same rule as **Hard Constraint 16** and **### 交互增强** “全文保真”.
- **Submit affordance:** After the radio/checkbox group, add a **primary** `Extended.Button` with `submit_form` (see **Hard Constraint 17** and [examples/flows/recommendation-radio.md](examples/flows/recommendation-radio.md) optional lines) so the user can **confirm** and upload—selection alone is **not** a substitute in the default flow.

### Layout patterns (cross-host stable)

- **Media list rows (thumb + text + action)**: Use **two nested `Row`s**. **Outer** row: exactly **two** children — `[left_group, button]` — with `justifyContent: "spaceBetween"` so the play/action control **aligns to the trailing edge**. **Inner** row (`layoutWeight: 1`): `[thumbnail, text_column]` with `space: 8` (8vp image–title gap per Harmony grid). Do **not** put thumbnail, text, and button as **three siblings** in one row: hosts often mis-measure flex and create a huge thumb–text gap or a button that does not pin right. Text column: `Extended.Column` with `alignItems: "top"` (schema 仅允许 `top` | `center` | `bottom`)，子项 `Extended.Text` 设 `styles.width: "matchParent"` 与 `textAlign: "start"` 以占满横向宽度。
- **Equal tile grids (2x2 / 3xN)**: build each row from **cell containers** first, then place visuals inside cells. Recommended pattern: `Row(children:[cellA, cellB, ...])` where each `cell*` gets `styles.layoutWeight: 1`; each visual inside the cell uses `styles.width: "matchParent"` plus explicit `height` (or ratio policy used by your host). Avoid putting only visuals as direct row children with `layoutWeight` and no container layer—some hosts resolve intrinsic size first and leave large blank gaps.
- **Header + list in one rounded root (preferred for compact modules)**:
  - If content is a **homogeneous list** (≥2 items of the same shape) and there is a **shared header** (title / icon / "more"), prefer making `root` itself the single rounded container (no extra shell card): use `root: Extended.Column` with **`styles.borderRadius: 16`** (16vp — Harmony **卡片最外层容器** per [`reference/design/harmony-card-spec.md`](reference/design/harmony-card-spec.md) **A4** / `corner_radius_level8`), a module background (commonly `#FFFFFFFF`), and inner `padding` (commonly `12`, per **C3**).
  - Inside the container, render items as **rows/sections** (`Extended.Row` / `Extended.Column`) and use **spacing** to separate items. Avoid `Extended.Divider`.
   **Inline tags/chips (MUST hug content width)**:
  - Do **not** set `styles.width:"matchParent"` on the chip.
  - Do **not** set `styles.layoutWeight` on the chip.
  - Add `styles.flexShrink: 0` to prevent some hosts from stretching the text box to the full row width.
  - **Host-compat safety**: some renderers still measure `Extended.Text` as full-width even without `styles.width`. To prevent a “full-row border” chip, add a conservative `styles.constraintSize.maxWidth` (e.g. 64–96) + `textAlign:"center"`. This keeps the chip visually compact while remaining stable across hosts.
  - Implement chip as `Extended.Text` with `padding` / `borderWidth` / `borderRadius` / `borderColor` (and optional `backgroundColor`) so the box hugs the label.
   Minimal chip snippet:
   See `examples/flows/list.md`.
- **List card single-action placement (compact + cross-host stable)**:
  - For list-style cards (orders, deliveries, trips, schedules, store rows), a **single action** like 「回放/查看/去支付/导航」should be placed at the **trailing end of the primary info row** (the row that contains the key content such as title/amount/score). This reduces card height and keeps scan → action in one line.
  - Avoid adding a dedicated bottom `action_row` when there is only one action and no explanatory text.
  - If you must use a separate action row (multiple actions, or needs helper copy), do **not** rely on a single-child `Row` + `justifyContent:"end"` (some hosts mis-align it). Use a **spacer** pattern: `children: [spacer, action]` where `spacer` is an `Extended.Text` (or other lightweight node) with `styles.layoutWeight: 1` so the action pins to the trailing edge.
- **Leaderboard / table rows**: `justifyContent:"spaceBetween"` + `space:0` + fixed `constraintSize(min=max)` on **every** column (including last). Do **not** use `spaceEvenly`. Do **not** leave trailing columns width-ambiguous—give the last cell `constraintSize` or `layoutWeight:1`. For dense stat rows, prefer fewer row children; size numeric columns from digit count + `fontSize` + 4vp grid (never copy widths from examples as universal constants). If a tight cell loses meaning under `maxLines:1` + ellipsis, split into `Extended.Column` with shorter `Extended.Text` lines. Same discipline for forecasts, timetables, ledgers.

### Content / readability defaults

- **Long paragraphs vs. `maxLines`**: If `Extended.Text` sets both `maxLines` and `textOverflow:"ellipsis"`, the client **will** truncate at that line count—often mid-phrase (e.g. biography ending inside a quoted title). For “介绍/说明/正文段落” by default **do not** use ellipsis truncation; reserve truncation for constrained summaries (list rows, chips, table columns, compact cards), or when the user explicitly requests a short summary.

## Reference Documentation

See `reference/README.md` for the categorized reference index (protocol/runtime/design/templates) and recommended reading order.

## Examples

### Basic Patterns

- [Form Example](examples/flows/form.md) - Registration and booking forms; login shows **text link** for tertiary actions
- [Recommendation + Radio](examples/flows/recommendation-radio.md) - **「我的推荐」** 三选一：`Extended.Text` 小标题 + **同组 `Extended.Radio`**，避免长文本墙 + 手打编号
- [List Example](examples/flows/list.md) - A-class list (`root-only`) with lightweight item grouping
- [Modal Example](examples/flows/modal.md) - Confirmation patterns via `Extended.If` / surfaces
