# 交互

在 A2UI 扩展组件中，通过组件对象上的 **`action`** 字段声明交互（与 [`skills/a2ui/reference/protocol/extended-interactions.md`](skills/a2ui/reference/protocol/extended-interactions.md) 一致）：

```json
{
  "id": "exp1",
  "component": "Extended.Button",
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

`functionCall.args` 中的字段可使用与展示数据相同的 **`{"path":"/…"}`** 绑定；点击时由宿主按当前数据模型解析。

当前参考实现中 **`functionCall.call`** 仅内置 **`openUrl`**；**把结构化信息交给 LLM** 统一通过 **`action.event`**（任意 `name`，常用 `submit_form`）与解析后的 **`context`** 表达，见 `extended-interactions.md`。

## 交互事件（表单等）

受控组件的 **`onChange`** 等仍由宿主/组件自身处理；**打开链接** 通过 **`action.functionCall`（`openUrl`）**；**整表/选项/模型字段上送** 通过 **`action.event`** 与 **`context`**（`path`、`getSelectedValues`、字面量等，点击时由客户端递归解析）表达，见 `extended-interactions.md`。

### 事件上下文（宿主上报可选）

```ts
interface EventContext {
  componentId: string;
  eventData?: { x: number; y: number } | unknown;
}
```

## 预定义 `functionCall.call` 示例

**`openUrl`** — 打开绝对地址 `http://` / `https://`：

```json
"action": {
  "functionCall": {
    "call": "openUrl",
    "args": { "url": "https://example.com" }
  }
}
```

**`submit_form`（`action.event`）** — `context` 中可混用字面量、`{"path":"…"}`、`getSelectedValues` 等，点击时递归解析后上报：

```json
"action": {
  "event": {
    "name": "submit_form",
    "context": {
      "itemId": "123",
      "value": "将表单信息发送给LLM",
      "agreed": { "path": "/form/agreed" }
    }
  }
}
```
