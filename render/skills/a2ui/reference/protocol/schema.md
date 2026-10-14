# A2UI JSON Schema Reference (Extended.*)

## Message Types

A2UI uses JSONL (JSON Lines) format. Each line is one of these message types:

| Message | Purpose |
|--------|---------|
| `createSurface` | Create a surface (`surfaceId`, `catalogId`, optional `theme`, optional `sendDataModel`) |
| `updateComponents` | Define **exactly one** component per message (`components` array length **1**) |
| `updateDataModel` | Patch the surface **data model** (`surfaceId`, optional `path`, optional `value`) |
| `deleteSurface` | Remove a surface |
| `action` (client → server) | User / host interaction: top-level **`action`** with **`functionCall`** and/or **`event`** (see [Client-to-Server Messages](#client-to-server-messages)). |

The first four row kinds are **server → client** (the agent / UI stream). The last one is **client → server** (user or host-originated responses).

## createSurface Schema

```json
{
  "version": "v0.9",
  "createSurface": {
    "surfaceId": "main",
    "catalogId": "https://xxx/specification/ohos/extended_catalog.json",
    "theme": { "primaryColor": "#FF0A59F7" }
  }
}
```

### Value Types (mutually exclusive)

| Field | Required | Description |
|-------|----------|-------------|
| `surfaceId` | Yes | Unique surface id |
| `catalogId` | Yes | Catalog id (basic catalog: `https://xxx/specification/ohos/extended_catalog.json` in bundled `basic_catalog.json`) |
| `theme` | No | Theme object per catalog |
| `sendDataModel` | No | If true, client may include full data model in A2A metadata (see schema description) |

## updateComponents Schema

```json
{
  "version": "v0.9",
  "updateComponents": {
    "surfaceId": "main",
    "components": [
      {
        "id": "root",
        "component": "Extended.Column",
        "children": ["header", "body"],
        "space": 12,
        "styles": { "width": "matchParent" }
      }
    ]
  }
}
```

Link children with **`child`** / **`children`** as **string ids** only; each id must be defined in its **own** `updateComponents` line (streaming-friendly).

## Interactions

**Authoritative spec:** [`extended-interactions.md`](extended-interactions.md).

## updateDataModel Schema

Server → client: update the **data model** that backs bound fields (`path` bindings on components) **without** resending the full component tree.

| Field | Required | Description |
|-------|----------|-------------|
| `surfaceId` | Yes | Target surface |
| `path` | No | JSON Pointer into the data model; omit or `/` replaces the **entire** model (v0.9 default) |
| `value` | No | New value at `path`; if omitted at `path`, that key is **removed** (per v0.9) |

```json
{
  "version": "v0.9",
  "updateDataModel": {
    "surfaceId": "user_profile_card",
    "path": "/user/name",
    "value": "Jane Doe"
  }
}
```

Authoritative wording: [A2UI Protocol v0.9 — updateDataModel](https://a2ui.org/specification/v0.9-a2ui/#updateDataModel).

## deleteSurface Schema

```json
{
  "version": "v0.9",
  "deleteSurface": {
    "surfaceId": "main"
  }
}
```

## Dynamic values Schema

Bindable fields use **`DynamicString`**, **`DynamicNumber`**, **`DynamicBoolean`**, or **`DynamicStringList`** (and related types) as declared on each component in the catalog. There are **no** `literalString` / `literalNumber` wrapper objects in v0.9.

- **Literal:** use a plain JSON value of the right type (`"Hello"`, `42`, `true`, `["a","b"]`).
- **Path (binding):** `{ "path": "/user/name" }` — JSON Pointer-style path for form inputs, list templates, and action context (`DataBinding`).
- **This skill (Mode A structured JSON):** treat **`Extended.Text.content`** and **`Extended.Image.src`** as **`DynamicString`** (plain string **or** `{ "path": "..." }`) so payload-backed copy and media URLs can bind to the surface model — see [`SKILL.md`](../../SKILL.md) §0 and [`extended-ui-schema.md`](extended-ui-schema.md).

Examples (same field may accept string **or** path depending on component):

```json
"Login"
```

```json
{ "path": "/user/name" }
```

```json
{ "path": "/form/email" }
```

Initial values for form fields like `/form/email` and `/form/password` are managed by the client.

## Child / Children Schema

Extended layout nodes use `children` as a **JSON array of component id strings**: `["a","b"]`.

## Complete Message Example

```jsonl
{"version":"v0.9","createSurface":{"surfaceId":"main","catalogId":"https://xxx/specification/ohos/extended_catalog.json","theme":{"primaryColor":"#FF0A59F7"}}}
{"version":"v0.9","updateComponents":{"surfaceId":"main","components":[{"id":"root","component":"Extended.Column","children":["title","form"],"space":12,"styles":{"width":"matchParent","constraintSize":{"maxWidth":336},"borderRadius":16,"clip":true,"backgroundColor":"#FFFFFFFF","padding":{"top":12,"right":12,"bottom":12,"left":12}}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"main","components":[{"id":"title","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","maxLines":1,"textOverflow":"ellipsis","fontColor":"#E5000000"},"content":"Login"}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"main","components":[{"id":"form","component":"Extended.Column","children":["email","password","submit"],"space":12,"styles":{"width":"matchParent","alignItems":"top"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"main","components":[{"id":"email","component":"Extended.TextInput","enabled":true,"maxLength":120,"type":"email","styles":{"width":"matchParent","height":56,"borderRadius":20,"backgroundColor":"#0C000000","padding":{"top":16,"right":16,"bottom":16,"left":16},"fontSize":16,"fontWeight":400,"fontColor":"#E5000000","placeholderColor":"#99000000","caretColor":"#FF0A59F7","showUnderline":false},"placeholder":"Email","text":{"path":"/form/email"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"main","path":"/form","value":{"email":"","password":""}}}
{"version":"v0.9","updateComponents":{"surfaceId":"main","components":[{"id":"password","component":"Extended.TextInput","enabled":true,"maxLength":120,"type":"password","styles":{"width":"matchParent","height":56,"borderRadius":20,"backgroundColor":"#0C000000","padding":{"top":16,"right":16,"bottom":16,"left":16},"fontSize":16,"fontWeight":400,"fontColor":"#E5000000","placeholderColor":"#99000000","caretColor":"#FF0A59F7","showUnderline":false},"placeholder":"Password","text":{"path":"/form/password"}}]}}
{"version":"v0.9","updateComponents":{"surfaceId":"main","components":[{"id":"submit","component":"Extended.Button","enabled":true,"styles":{"width":"matchParent","height":40,"borderRadius":20,"fontSize":16,"fontWeight":500,"backgroundColor":"#FF0A59F7"},"label":"Sign In"}]}}
```

## Standard Catalog ID

```
https://xxx/specification/ohos/extended_catalog.json
```

## Validation tips

1. **`version`**: Every **server → client** NDJSON line in this doc includes `"version": "v0.9"`. **Client `action` / `error` payloads** may be bare objects or the same line with optional `version`—see [Client-to-Server Messages](#client-to-server-messages).
2. **`surfaceId`**: Consistent across `createSurface` / `updateComponents` / `updateDataModel` / `deleteSurface` for one surface.
3. **Component ids**: Unique per surface; **`updateComponents.components` length is 1** per line.
4. **References**: Every `child` / `children` string and template `componentId` must have a matching `updateComponents` definition.
5. **Dynamic values**: Literal JSON **or** `{ "path": "..." }` — do not use `literalString` / keyed `valueMap` trees. **`Extended.TextInput.text`**: use **`{ "path": "..." }` only** in this skill (see [`SKILL.md`](../../SKILL.md) §0).
