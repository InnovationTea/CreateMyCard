# Extended interactions: `action.functionCall` and `action.event`

This document defines **local and relayed** UI behaviors carried under **`action`** on components (e.g. **Extended.Button**, **Extended.Text**).

- **`functionCall`**: **`{ "call": "<name>", "args": { … } }`** — built-ins such as **`openUrl`**.
- **`event`**: **`{ "name": "<name>", "context": { … } }`** — built-in **`submit_form`** for path-resolved form snapshots to the agent / LLM.

Use **one** of these shapes per control (do not mix **`functionCall`** and **`event`** on the same **`action`**).

---

## 本地行为（Local Action）

通过在交互组件（如Button）中的action属性中设置functionCall字段值定义具体交互，并可以携带args字段上传指定参数。

### Canonical payload: `openUrl`

When the user triggers a control that should open a URL, the **minimal** object is:

```json
{
  "action": {
    "functionCall": {
      "call": "openUrl",
      "args": {
        "url": "https://example.com/path"
      }
    }
  }
}
```

| Field | Meaning |
|-------|---------|
| `action.functionCall.call` | Built-in name, e.g. **`openUrl`**. |
| `action.functionCall.args.url` | **String**: absolute `http://` or `https://` URL for this control, from your context (structured fields, resolved bindings, or explicit text). **Do not** invent URLs. |

Optional siblings on **`action`** (e.g. **`action.context`** with **`componentId`**, data snippets) are **host-defined**; see [`schema.md`](schema.md#client-to-server-messages) if present in your transport.

---

## 服务端行为（Server Action）

通过在交互组件（如Button）中的action属性中设置event字段值定义具体交互，并可以携带可选的context字段上传数据。

### Canonical payload: `action.event`

When the user should send **structured context + data** to the agent (e.g. form submit), use **`action.event`** with **`name`** and a **`context`** object.

**Minimal** shape:

```json
{
  "id": "submit-btn",
  "component": "Button",
  "label": "确认选择并下单",
  "action": {
    "event": {
      "name": "submit_form",
      "context": {
        "itemId": "123",
        "address": { "path":"/result/address"},
        "foodChoice": { "call":"getSelectedValues", "args":{"groupID": "点餐选择项"}},
        "moneyChoice": { "call":"getSelectedValues", "args":{"groupID": "价格范围"}}
      }
    }
  }
}
```

| Field | Meaning |
|-------|---------|
| `action.event.name` | **String**: Event name; use **`submit_form`** for form-like relay to the agent. |
| `action.event.context` | **Object**: Each key is a **field name** you choose; the **value** is one of **three** shapes (see below). |

**`action.event.context` — three value shapes (per key):**

1. **Data model / `Extended.TextInput` (and other path-bound fields):** **`{ "path": "/…" }`**. The JSON Pointer string **must** match the same model path as **`TextInput.text`** (or the bound prop) and any **`updateDataModel`** for that **`surfaceId`**. The **object must use the property name `path`** — do **not** put the pointer string under a key named `value` (wrong: `{"value":"/form/text"}`; right: `{"path":"/form/text"}`). If you want the **upstream payload** to use a key called `value`, name the **context** key `value` and still use a `path` leaf: **`"value": { "path": "/form/text" }`**.

2. **Same-`surfaceId` `Extended.Radio` (or other grouped controls the host allows here):** **`{ "call": "getSelectedValues", "args": { "groupID": "…" } }`** with **`groupID` equal** to the Radio components’ **`group`** string.

3. **Stable non-interactive ids only:** a **string**, **number**, or **boolean** literal (e.g. row id, **SKU** when it is not chosen via a path/Radio in this `context`). **Do not** use **`intent`** (or a long prose **value**) **instead of** (1) or (2) when the agent must receive the real field data — see [`../../SKILL.md`](../../SKILL.md) **§0a (3)**.

**Minimal example (single `TextInput` + submit):**

```json
{
  "action": {
    "event": {
      "name": "submit_form",
      "context": {
        "text": { "path": "/form/text" }
      }
    }
  }
}
```

(Requires `Extended.TextInput` with **`"text": { "path": "/form/text" }`** and a matching **`updateDataModel`** for `/form` or `/form/text` on the same **`surfaceId`**.)

The client should resolve **`path`** and **`getSelectedValues`** at **click** time; the message upstream carries **literals** in **`context`** only (no separate `formValues` merge in the reference client). **Renderer behavior** may vary by product; the **streamed** `action.event.context` must still use the shapes above.

---

客户端向服务端发送的**消息**形态示例（**解析后**可能仅为字面量；以下为示意）如下所示：

```json
{
  "name": "submit_form",
  "surfaceId": "id",
  "sourceComponentId": "submit-btn",
  "timestamp": "2026-03-12T06:12:16:444Z",
  "context": {
    "itemId": "123",
    "address": "杭州西湖",
    "foodChoice": "汉堡套餐",
    "moneyChoice": "10~25"
  }
}
```

### Path and group resolution in `context` (recommended)

To include **current** text and other **data model** values, add **`{ "path": "/form/…" }`** under each key you need in **`action.event.context`** (see [`schema.md`](schema.md) **`updateDataModel`** / JSON Pointer rules and [`../../SKILL.md`](../../SKILL.md) **§0**). The **client** should resolve these leaves at **click** time (same path rules as **`functionCall.args`** where applicable), then send a **fully literal** `context` upstream for those keys.

**Example (stream definition — path + literal; no `intent` as a stand-in for fields):**

```json
{
  "action": {
    "event": {
      "name": "submit_form",
      "context": {
        "itemId": "123",
        "userText": { "path": "/form/text" }
      }
    }
  }
}
```

After resolution, the host may see only literals in **`context`** (e.g. **`"userText": "…"`** typed by the user, **`"itemId": "123"`**).

**Whole subtree:** a single key bound to **`{ "path": "/form" }`** is valid if the full form state lives under `/form` in the data model.

**Host / LLM:** the reference platform turns the full **client→server** message (`name`, `surfaceId`, `sourceComponentId`, `timestamp`, **`context`**) into a user message, together with the **current UI tree** for incremental JSONL patches—see product notes (e.g. `submitForm` request kind). **Authoritative** field wiring for the agent is **`path`** + **`getSelectedValues`** as above, not prose **`intent`** keys.

### Who fires `submit_form`?

`submit_form` is sent when a component **`action` is triggered** (e.g. the user **clicks** an **`Extended.Button`** or another control your renderer maps to `action`). **Changing** a radio or checkbox **updates form state** but **does not** by itself emit `submit_form` in the default reference flow—add a **primary** button whose `action.event` is **`submit_form`** if the user must **explicitly confirm** before the agent receives the payload. (Auto-submit on every change is **host-specific**.)

---

## See also

- [schema.md](schema.md) — **Client-to-Server Messages** (transport may wrap `action` with `version`).
- [extended-ui-schema.md](extended-ui-schema.md) — Extended props and `styles`.
- [extended-output-format.md](extended-output-format.md) — NDJSON line discipline for **server → client** streams.
- [schema.md](schema.md) — **`updateDataModel`** and **`path`** bindings; [../../SKILL.md](../../SKILL.md) **§0** — streaming **`updateDataModel` tail** rule.
