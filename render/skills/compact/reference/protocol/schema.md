# Compact minimal GenUI — line kinds

Each **line** is one **tuple in braces** (see [`extended-output-format.md`](extended-output-format.md)). This profile is the **极简 GenUI** stream; downstream code may map lines to a richer protocol.

## Record kinds

| Kind | Shape (tuple segments) | Notes |
|------|-------------------------|--------|
| **createSurface** | `{"@<surfaceId>", "<catalogId>", { theme? }, send_DataModel? }` | `surfaceId` is **without** the `@` in the host model — the first string is `"@..."`. Optional theme object; optional boolean for `send_DataModel`. |
| **updateComponent** | `{"<surfaceId>", "<componentId>", "<Type>", { props }, [ children? ]}` | `surfaceId` does **not** start with `@` or `~`. Second segment is **not** a JSON string starting with `/` (else this line is **updateDataModel**). `components` post-map has one element per line. |
| **updateDataModel** | `{"<surfaceId>", "<path>", <value> }` | **Second** string must start with `/` (JSON Pointer path). `value` is any JSON value. |
| **deleteSurface** | `{"~<surfaceId>"}` | Single string segment only; `surfaceId` is the part after `~`. |

## Root / tree root

- There is no required id name like `"root"`. A **top-level card** is just another `componentId` (many examples still use `"root"` for the main card for clarity).
- **Parent before children in stream order:** lines that define a `componentId` should appear before lines that only reference it as a child, when the host merges in order (follow product rules if stricter).

## Classic JSON

If the product accepts generic JSONL objects in addition to tuples, that is a **host** concern. This skill standardizes the **tuple** lines above.

## Component props

`Type` and props: [`extended-ui-schema.md`](extended-ui-schema.md).

## Further reading

- [`extended-output-format.md`](extended-output-format.md)
- [`extended-interactions.md`](extended-interactions.md)
- [`extended-updateDataModel.md`](extended-updateDataModel.md) — `updateDataModel` minimal lines
