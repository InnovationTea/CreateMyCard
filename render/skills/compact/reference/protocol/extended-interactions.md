# Extended declarative interactions (`openUrl`)

In **minimal GenUI** **updateComponent** lines, navigation is expressed with **top-level `openUrl`** on **`Button`** and **`Text`** props. The host maps these to full-protocol **`action.functionCall` + `openUrl`** on the component.

This document parallels [`../../../a2ui/reference/protocol/extended-interactions.md`](../../../a2ui/reference/protocol/extended-interactions.md) for **agent expectations**.

---

## When to set `openUrl`

- **`Button`**: when the control should open a browser / WebView / in-app browser to an **absolute** `http://` or `https://` URL supplied by structured input or an explicitly confirmed user URL.
- **`Text`**: optional `openUrl` for inline link-like copy (same absolute URL rules).

## Structured payload → `openUrl` (mandatory mapping)

When the user JSON includes **`webURL`** / **`webUrl`** for a specific affordance:

1. **Per-row CTAs** — e.g. `listSubTitle3ButtonLink1.webURL` for 「电话咨询」 on that row → the **`Button`** in **that** row **must** set **`openUrl`** to that exact string.
2. **Header 「更多」** — `moreLink.webURL` → the 「更多」 **Text** or **Button** uses **`openUrl`**.
3. **Row / detail taps** — `listItemLink.webURL` (or similar) → the tappable **Text** / **Button** for that row.

**Omit `openUrl`** only when the payload truly has **no** URL for that control (disabled, host-only action). **Do not** invent URLs.

---

## What *not* to emit

- Do **not** use deprecated `actionText` on **Button** — use **`openUrl`** (mapped to **`action.functionCall`**).

---

## Minimal examples (updateComponent lines)

```jsonl
{"demo", "cta", "Button", {"label": "打开详情", "openUrl": "https://example.com/detail"}}
{"demo", "more", "Text", {"content": "更多 >", "fontColor": "#0A59F7", "openUrl": "https://example.com/more"}}
```

---

## Events not modeled in minimal GenUI schema

`onChange`, `onAppear`, checkbox semantics, etc. are **host-defined**. Only **`openUrl`** is specified here as a portable navigation hook.
