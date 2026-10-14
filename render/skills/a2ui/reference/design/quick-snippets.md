# Extended DSL 样式速用片段（已对齐新规范）

本文件只给“可复制的样式片段”，不定义协议逻辑。
模式路由与优先级见 `DESIGN.md`。

---

## §1 统一约束

- 仅使用 `Extended.*` 与协议已定义 `styles` 字段。
- `TextInput.text` 仅允许 `{"path":"..."}`（见 `SKILL.md §0`）。
- 每条 `updateComponents` 仍保持 `components` 长度 1（逻辑规则不变）。
- 样式值优先语义 token 对应值；避免沿用过期硬编码常量。
- 本文件中的 hex 值是当前 token 的展开值示例，不是自由取色依据；生成时仍以 token 语义和当前模式（Light/Dark）为准。

---

## §2 createSurface（主题）

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

---

## §3 UI Mode（Markdown / Query）根布局

```json
{
  "id": "root",
  "component": "Extended.Column",
  "children": ["section_header", "section_body"],
  "space": 12,
  "styles": {
    "width": "matchParent",
    "backgroundColor": "#FFFFFFFF",
    "padding": { "top": 16, "right": 16, "bottom": 16, "left": 16 }
  }
}
```

> UI Mode 不强制卡片壳，仅遵循 token + 组件样式。

---

## §4 Card Mode（JSON）容器骨架

```json
{
  "id": "card_root",
  "component": "Extended.Column",
  "children": ["card_name", "card_content"],
  "space": 12,
  "styles": {
    "width": "matchParent",
    "constraintSize": { "maxWidth": 336 },
    "backgroundColor": "#FFFFFFFF",
    "borderRadius": 16,
    "padding": { "top": 12, "right": 12, "bottom": 12, "left": 12 }
  }
}
```

> Card Mode 下结构与样式仍以 `harmony-card-spec.md` 为强约束：**A4** 最外层圆角 16vp；**A5.1** 底板 `#FFFFFFFF`；**C3** 内边距 12vp、`maxWidth` 336；`theme.primaryColor` 用 `#FF0A59F7`。

---

## §5 Text（层级）

```json
{
  "id": "title",
  "component": "Extended.Text",
  "styles": {
    "fontSize": 16,
    "fontWeight": "500",
    "fontColor": "#E5000000",
    "maxLines": 1,
    "textOverflow": "ellipsis"
  },
  "content": "标题文案"
}
```

---

## §6 TextInput（路径绑定）

```json
{
  "id": "field_email",
  "component": "Extended.TextInput",
  "enabled": true,
  "maxLength": 120,
  "type": "email",
  "styles": {
    "width": "matchParent",
    "height": 56,
    "borderRadius": 20,
    "backgroundColor": "#0C000000",
    "padding": { "top": 16, "right": 16, "bottom": 16, "left": 16 },
    "fontSize": 16,
    "fontWeight": 400,
    "fontColor": "#E5000000",
    "placeholderColor": "#99000000",
    "caretColor": "#FF0A59F7",
    "showUnderline": false
  },
  "placeholder": "Email",
  "text": { "path": "/form/email" }
}
```

---

## §7 Button（普通弱底 / 小）

- **普通按钮（弱底）**：`comp_background_tertiary` 展开示例 `#0C000000`（Light）。
- **主 CTA / 强调按钮**：用 `background_emphasize` 展开示例 `#FF0A59F7`（Light），见 §7b。

```json
{
  "id": "btn_normal",
  "component": "Extended.Button",
  "enabled": true,
  "styles": {
    "height": 40,
    "borderRadius": 20,
    "fontSize": 16,
    "fontWeight": 500,
    "backgroundColor": "#0C000000"
  },
  "label": "确认"
}
```

### §7b Button（强调 / 主 CTA）

```json
{
  "id": "btn_emphasize",
  "component": "Extended.Button",
  "enabled": true,
  "styles": {
    "height": 40,
    "borderRadius": 20,
    "fontSize": 16,
    "fontWeight": 500,
    "backgroundColor": "#FF0A59F7"
  },
  "label": "提交"
}
```

```json
{
  "id": "btn_small",
  "component": "Extended.Button",
  "enabled": true,
  "styles": {
    "height": 28,
    "borderRadius": 14,
    "fontSize": 14,
    "fontWeight": 500,
    "backgroundColor": "#0C000000"
  },
  "label": "下载"
}
```

---

## §8 Divider（弱化使用）

```json
{
  "id": "divider_soft",
  "component": "Extended.Divider",
  "styles": {
    "strokeWidth": 1,
    "vertical": false,
    "color": "#33000000"
  }
}
```

---

## §9 单条 NDJSON 包装示例

```jsonl
{"version":"v0.9","updateComponents":{"surfaceId":"main","components":[{"id":"title","component":"Extended.Text","styles":{"fontSize":16,"fontWeight":"500","fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"},"content":"标题文案"}]}}
```

---

## §10 参考示例

- `../../examples/inputs/json-input/product-compact-card.md`（JSON -> Card Mode）
- `../../examples/flows/list.md`（列表布局）
- `../../examples/flows/form.md`（输入与按钮组合）

这些示例继续用于结构与布局参考；样式值以当前规范口径为准。若与 `style-runtime-index.md` 不一致，以 `style-runtime-index.md` 为最高优先级。
