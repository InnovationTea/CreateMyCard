# updateDataModel (minimal GenUI)

Use a dedicated **minimal line** when you need a JSON Pointer patch into the surface data model, instead of inlining that value in a **Text** / **Button** prop.

## Line shape

Second segment: **string** whose first character is **`/`** (path). Third: `value` (any JSON).

```jsonl
{"my_surface", "/title", "欢迎回来"}
{"my_surface", "/stats/clicks", 42}
```

Downstream code maps this to full-protocol `updateDataModel`; you **do not** need to output envelopes in the minimal stream.

## When to use

- **Bound** values that the renderer reads from the data model by path.
- Cross-cutting state that is not a single component’s `props` literal.

## When to prefer updateComponent

- Static or known-in-place copy: set **`Text` `content`**, **`Button` `label`**, etc. on the **updateComponent** line for that `componentId`.

## Relation to streaming

Re-emit **updateDataModel** when only the model changes; re-emit **updateComponent** when the node’s props or children change.
