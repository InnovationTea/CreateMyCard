# Extended output format (minimal GenUI JSONL)

**Authoritative:** streaming rules in **[`SKILL.md` §0](../../../SKILL.md)**. This file adds examples; it must not contradict §0.

Each line is a **single-line** tuple inside `{ }`. Segments are comma-separated. The host’s tokenizer (not necessarily strict JSON) ingests the same shape as today’s **compact tuple** parsers: **not** always valid standard JSON, but **conventionally** `{"a", "b", 1}`-style **brace-tuple** lines.

---

## createSurface (new scene)

First string **must** start with `@`.

```jsonl
{"@weather_card", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
```

Optional: theme omitted; fourth segment `true` / `false` for `send_DataModel` if your pipeline supports it.

---

## updateComponent (one component per line)

```jsonl
{"weather_card", "save_card", "Card", {"title": "偏好设置", "description": "修改后请点击保存", "layout": "vertical", "gap": 12, "width": "matchParent", "justifyContent": "center"}, ["hint", "save-btn"]}
```

- **First** segment: `surfaceId` (plain name, no `@` / `~`).
- **Fifth** segment optional: `["child1", "child2"]` child ids.
- `type` and props: [`extended-ui-schema.md`](extended-ui-schema.md).

**Incremental / streaming:** emit another **updateComponent** line for the same `surfaceId` + `componentId` with updated `props` and/or `children` (merge semantics: host).

---

## updateDataModel

**Second** segment must be a string starting with `/`.

```jsonl
{"weather_card", "/card/xxx", "123"}
```

---

## deleteSurface

Single segment, first character `~`.

```jsonl
{"~weather_card"}
```

---

## Anti-patterns (forbidden)

1. **Two** separate `{ }` prop objects on one **updateComponent** line — use **one** props object.
2. Bare k/v pairs outside that props object.
3. **updateComponent** with first segment looking like a path: keep `surfaceId` as the surface name; use **updateDataModel** for `/...` paths on **second** segment.
4. Omitting **createSurface** for a new `surfaceId` when the product expects an explicit new surface (always follow §0).

---

## Checklist

- [ ] createSurface first when opening a new surface (`@...`).
- [ ] updateComponent: `surfaceId`, `componentId`, `type`, `{ props }`, optional `[ children ]`.
- [ ] updateDataModel: second string starts with `/`.
- [ ] deleteSurface: one segment `~...`.
- [ ] **DESIGN.md** density and **openUrl** rules for Mode A.
- [ ] `justifyContent` for Row: e.g. `"spaceBetween"` per schema (not snake_case).
