# Extended Output Format (NDJSON, v0.9)

**Authoritative:** All NDJSON / streaming rules live in **[`SKILL.md` §0](../../SKILL.md)**. This file adds unique examples; it must stay aligned with §0 and never contradict it.

**`updateDataModel`**: one NDJSON line patches the surface data model (`surfaceId`, optional JSON Pointer `path`, optional `value`) so bound widgets refresh without replaying `updateComponents` lines. Full shape: [`schema.md`](schema.md) § **updateDataModel Schema**. When input is **structured JSON** (explicit keys), **payload-driven values** belong in the model and **`updateDataModel`**, not duplicated as **literals** on the same bound props in `updateComponents`—see **[`SKILL.md` §0](../../SKILL.md)**.

**Streaming order ([`SKILL.md` §0](../../SKILL.md)):** when an `updateComponents` line first introduces **`{"path":"..."}`** bindings, finish the matching **`updateDataModel` tail** for that **`surfaceId`** before the next `createSurface` / `updateComponents` / `deleteSurface` for the **same** surface; **single-surface** = no lines in between; **multi-surface** = other `surfaceId` lines may interleave (§0).

**Mode A structured JSON ([`SKILL.md` §0](../../SKILL.md)):** payload-driven **`Extended.Text.content`** / **`Extended.Image.src`** (and other Dynamic fields) use **`{"path":"..."}`**; the stream includes **≥ 1** `updateDataModel` per `surfaceId`. **Default (this skill):** for each `updateComponents` line that first introduces new payload paths, emit matching `updateDataModel` tail(s) **immediately on the next line** (single-surface). **Single `/` write is allowed only immediately after the first binding line** for that surface; an end-of-stream `/` write is invalid for streaming.

### Example — bound field + `updateDataModel`

One envelope per line (**single-surface** minimal pattern): the line after `text: {"path":"/status"}` is the matching **`updateDataModel`** (then continue with more `updateComponents` for that surface if needed):

```jsonl
{"version":"v0.9","createSurface":{"surfaceId":"demo_bind","catalogId":"https://xxx/specification/ohos/extended_catalog.json","theme":{"primaryColor":"#FF0A59F7"}}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_bind","components":[{"id":"root","component":"Extended.Column","children":["status_input"],"space":12,"styles":{"width":"matchParent","constraintSize":{"maxWidth":336},"borderRadius":16,"clip":true,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_bind","components":[{"id":"status_input","component":"Extended.TextInput","enabled":true,"maxLength":80,"type":"normal","styles":{"width":"matchParent","height":56,"borderRadius":20,"backgroundColor":"#0C000000","padding":{"top":16,"right":16,"bottom":16,"left":16},"showUnderline":false,"fontSize":16,"fontWeight":400,"fontColor":"#E5000000","placeholderColor":"#99000000","caretColor":"#FF0A59F7"},"placeholder":"状态","text":{"path":"/status"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"demo_bind","path":"/status","value":"已刷新"}}
```

### Example — Mode A structured JSON (default progressive tails)

Each introducing line is followed **immediately** by a tail for the newly introduced paths:

```jsonl
{"version":"v0.9","createSurface":{"surfaceId":"demo_struct","catalogId":"https://xxx/specification/ohos/extended_catalog.json","theme":{"primaryColor":"#FF0A59F7"}}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_struct","components":[{"id":"root","component":"Extended.Column","children":["title_text","logo_img"],"space":12,"styles":{"width":"matchParent","constraintSize":{"maxWidth":336},"borderRadius":16,"clip":true,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_struct","components":[{"id":"title_text","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":{"path":"/globalContent/abilityName"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"demo_struct","path":"/globalContent/abilityName","value":"Example App"}}
{"version":"v0.9","updateComponents":{"surfaceId":"demo_struct","components":[{"id":"logo_img","component":"Extended.Image","styles":{"width":24,"height":24,"borderRadius":12,"objectFit":"cover"},"src":{"path":"/globalContent/logo"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"demo_struct","path":"/globalContent/logo","value":"https://example.com/logo.png"}}
```

---

## First turn (empty UI)

Emit JSONL:

1. **createSurface**

```json
{ "version": "v0.9", "createSurface": { "surfaceId": "main", "catalogId": "https://xxx/specification/ohos/extended_catalog.json" } }
```

2. **updateComponents** (one line = one component node)

```json
{
  "version": "v0.9",
  "updateComponents": {
    "surfaceId": "main",
    "components": [
      { "id": "root", "component": "Extended.Column", "children": [], "space": 12, "styles": { "width": "matchParent" } }
    ]
  }
}
```

Repeat (2) for every component id.

---

## Mandatory layout rule

- The outermost layout (usually `id: "root"`) MUST set `styles.width` to `"matchParent"` so the UI spans the full preview area.

---

## Example — first turn (minimal)

```jsonl
{"version":"v0.9","createSurface":{"surfaceId":"main","catalogId":"https://xxx/specification/ohos/extended_catalog.json","theme":{"primaryColor":"#FF0A59F7"}}}
{"version":"v0.9","updateComponents":{"surfaceId":"main","components":[{"id":"root","component":"Extended.Column","children":["hint","save_btn"],"space":12,"styles":{"width":"matchParent","constraintSize":{"maxWidth":336},"borderRadius":16,"clip":true,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"main","components":[{"id":"hint","component":"Extended.Text","styles":{"fontSize":12,"fontWeight":"400","maxLines":2,"textOverflow":"ellipsis","fontColor":"#99000000"},"content":"保存后立即生效。"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"main","components":[{"id":"save_btn","component":"Extended.Button","enabled":true,"styles":{"width":"matchParent","height":40,"borderRadius":20,"fontSize":16,"fontWeight":500,"backgroundColor":"#FF0A59F7"},"label":"保存"}]}}
```
