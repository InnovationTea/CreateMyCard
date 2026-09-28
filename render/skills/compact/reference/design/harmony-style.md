# 鸿蒙风格设计规范（minimal GenUI）

本规范适用于 **极简 GenUI** 的 **updateComponent** 行（`Card`, `Row`, `Column`, `Text`, `Button`, `Input`, … 的 `type` 与 props）。数值单位使用 **px**（与 `radius` / `gap` / `space` / `padding` / `fontSize` 一致）。

源码镜像：`genui-sdk/prompt/src/mini-prompt-assets/harmony_style.ts`。

---

## 1. Typography

- **HarmonyOS Sans** 由宿主渲染；用 **`Text`** 的 `fontSize` / `fontWeight` / `fontColor` 表达层级。
- **最小字号**：≥ **10** px。
- **层级表**（与 `extended-ui-schema` 一致）：

| Role | fontSize (px) | fontWeight |
|------|-----------------|------------|
| Display | 38–56（步进 2） | `"600"` / `"700"` |
| Emphasis | 14 / 16 / 18 | `"500"` / `"600"` |
| Body | 12–16 | `"400"` |
| Hint | 10–12 | `"300"` / `"400"` |

---

## 2. Text color (`fontColor` on **Text**)

- 需要偏离宿主默认时，**显式设置** `fontColor`。
- Light：**#000000** / **#666666** / **#999999**；链接/强调：**#0A59F7**。
- Dark：**#FFFFFF** / **#999999** / **#666666**；链接：**#3B8CFF**。

---

## 3. Corners

- **Card**：`radius` **20**（外层对话卡片）。
- **Button**：`borderRadius` **20**（大）/ **14**（小）。
- **Chip / 小标签**：小 **Card** 或 **Text** 边框方案 — **4** px 级圆角。

---

## 4. Surfaces (`fill` on **Card**)

- **非沉浸**：`#FFFFFF` / `#F1F3F5`。
- **沉浸**：单行字符串写完整 CSS `linear-gradient(...)` / `radial-gradient(...)`；可加 `backgroundImage` 与 `backgroundBlendMode`。

---

## 5. Width

- Root 与 section **Card**、主 **Row** / **Column**：`width`: `"matchParent"`。

---

## 6. Padding & grid

- **Card** `padding`：默认 **12**，强调 **16**。
- **4px 网格**：优先 **4 / 8 / 12 / 16**；避免在同一卡片堆叠超大 padding + gap + margin。

---

## 7. Buttons

- **主按钮**：`backgroundColor`: `#0A59F7`，`borderRadius` **20**，`fontSize` **16** 左右。
- **次按钮 / 链接型**：优先 **Text** + `fontColor` `#0A59F7`，避免第二颗同材质实心主按钮。
- **`openUrl`**：绝对 `http`/`https`，与结构化 **`webURL`** 对齐。

---

## 8. Input

- **Input** 为 schema 简模：`label`, `name`, `type`, `placeholder`；成组放在 **Column** `space` **8–12** 内。

---

## 9. Dividers

- 本 schema **无 Divider 类型** — 用留白；必要时细线 **Card** `strokeThickness`: 1。

---

## 10. Chips / tags

- 小 **Card** `radius` **4** + 紧 `padding`，子节点仅 **Text**。

---

## 11. Palette quick ref

| Role | Where |
|------|--------|
| Primary CTA / link | **Button** `backgroundColor` / **Text** `fontColor` `#0A59F7` |
| Surface | **Card** `fill` `#FFFFFF` / `#F1F3F5` |
| Hairline | **Card** `strokeColor` `#E5E5E5` |

---

## 12. Mapping from A2UI mental model

| A2UI idea | 极简 GenUI `type` + props |
|-----------|----------------|
| `Extended.Text` + styles | **Text** + `fontSize` / `fontWeight` / `fontColor` / … |
| `Extended.Card` + styles | **Card** + `fill` / `radius` / `padding` / `gap` / `layout` / `width` |
| `Extended.Button` + styles | **Button** + `backgroundColor` / `borderRadius` / `label` / `openUrl` |
| `Extended.Column` / `Row` + space | **Column** / **Row** + `space` |

---

## 13. 极简 JSONL 片段（先 createSurface，再 updateComponent）

新表面 + 根 **Card**（`surfaceId` 示例为 `page_demo`）：

```jsonl
{"@page_demo", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"page_demo", "root", "Card", {"title": "页面标题", "description": "副标题一行", "layout": "vertical", "gap": 12, "width": "matchParent", "padding": 16, "fill": "#FFFFFF", "radius": 20}, ["section-a", "section-b"]}
```

主按钮 + 文字链：

```jsonl
{"page_demo", "actions", "Row", {"width": "matchParent", "justifyContent": "spaceBetween", "alignItems": "center", "space": 12}, ["btn_primary", "link_forgot"]}
{"page_demo", "btn_primary", "Button", {"label": "确认", "openUrl": "https://example.com/confirm", "backgroundColor": "#0A59F7", "borderRadius": 20, "fontSize": 16, "fontWeight": 500}}
{"page_demo", "link_forgot", "Text", {"content": "忘记密码？", "fontSize": 12, "fontWeight": "400", "fontColor": "#0A59F7"}}
```

---

## 14. 对话卡片密度（小艺向）

- **padding 12**（少数 **16**）；**gap / space 8–12**；列表行 **6–10**。
- 避免 **padding 20 + 大 gap + 大 space** 与多层重 **Card** 同框堆叠。

---

## 15. 与 `skills/a2ui/examples` 的关系

`skills/a2ui/examples` 下的 Markdown 是 **布局意图参考**。在本 skill 中请用 **schema 的 types** 与 **极简行** 重建结构；不要把完整协议信封与极简行混为同一套输出，除非产品要求。
