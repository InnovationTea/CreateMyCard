---
name: compact
description: Generate minimal GenUI JSONL (tuple lines per record)—createSurface (@), updateComponent, updateDataModel (/), deleteSurface (~). HarmonyOS visual intent. Output raw JSONL only—no prose, no explanations, no markdown fences unless the user asks.
---

# Compact GenUI Development Skill

This skill helps you generate **极简 GenUI** lines: one **tuple-in-braces** record per line, consumed by a downstream parser (mapping to a full protocol is out of scope here). You **do not** output `version` envelopes or long-form A2UI JSON unless the product explicitly asks for that other format.

## 0) Output contract (mandatory, always-on)

**Authoritative source:** line rules in this **§0** are the **single source of truth**. [`reference/protocol/extended-output-format.md`](reference/protocol/extended-output-format.md), [`reference/protocol/schema.md`](reference/protocol/schema.md), [`reference/protocol/extended-ui-schema.md`](reference/protocol/extended-ui-schema.md), and [`DESIGN.md`](DESIGN.md) add detail; they must **not** contradict §0.

- **Output only JSONL:** one **complete** record per line (tuple inside `{ … }` as specified below).
- **New scene** starts with **createSurface** (first string begins with `@`). Then emit **updateComponent** lines for that surface.
- **JSON string literals** must be parseable: escape inner `"` as `\"`. Do not break the host’s line parser.
- **One logical record per line:** emit a full line, then `\n`. Do not split a record.
- **Do not** wrap the stream in markdown fences unless the user explicitly asks.
- **Do not** mix explanations with the JSONL deliverable when the user asked for UI output only.

**Line kinds (discrimination, first segment unless noted):**

| Kind | First segment / rule | Body |
|------|----------------------|------|
| **createSurface** | `"@"` + `surfaceId` | Then `catalogId` string, optional `theme` object, optional `send_DataModel` boolean. |
| **updateComponent** | plain `surfaceId` (not `@` or `~`) and second segment is **not** a path | `surfaceId`, `componentId`, `type`, `{ props }`, optional `[ childIds ]`. |
| **updateDataModel** | second segment is a JSON string whose first character is **`/`** | `surfaceId`, `path`, `value` (any JSON). |
| **deleteSurface** | `"~"` + `surfaceId` (single-segment line) | Only `~surfaceId`. |

Use **`"https://xxx/specification/ohos/extended_catalog.json"`** as `catalogId` unless the product specifies another catalog.

`component` **type** strings and flat props: [`reference/protocol/extended-ui-schema.md`](reference/protocol/extended-ui-schema.md). **Row** `justifyContent` uses values like `"spaceBetween"` (see schema).

## ⚠️ MANDATORY: 鸿蒙风格 + 密度

**生成任何 UI 前**，先读 [`DESIGN.md`](DESIGN.md) 与 [`reference/design/quick-snippets.md`](reference/design/quick-snippets.md).

### 核心规范文件

| 文件 | 用途 |
|------|------|
| [`DESIGN.md`](DESIGN.md) | 色板 / 字号 / 圆角 / 间距 + Do/Don’t（平面 props） |
| [`reference/design/quick-snippets.md`](reference/design/quick-snippets.md) | 可复制：createSurface + 典型节点行 |
| [`reference/protocol/schema.md`](reference/protocol/schema.md) | 四种行形态速查 |
| [`reference/protocol/extended-ui-schema.md`](reference/protocol/extended-ui-schema.md) | 组件 `type` 与 props |
| [`reference/protocol/extended-output-format.md`](reference/protocol/extended-output-format.md) | 单行纪律、反例、清单 |
| [`reference/protocol/extended-interactions.md`](reference/protocol/extended-interactions.md) | `openUrl` 等 |
| [`reference/design/harmony-style.md`](reference/design/harmony-style.md) | 鸿蒙风格完整展开 |
| [`reference/design/components.md`](reference/design/components.md) | 组件索引 |

### Hard constraints

1. **Line shape:** always one of the four kinds in **§0**; **updateComponent** lines carry exactly **one** component per line (one array element in the host’s `components` list after mapping).
2. **Types** from schema: `Card` | `Row` | `Column` | `Text` | `Button` | `Radio` | `Select` | `Checkbox` | `Input` | `Image`.
3. **Row 使用门槛:** **Row** only for **two or more** horizontal children; single-line titles → **Card** `title` / `description` or **Column** + **Text`.
4. **全宽:** main **Card** / **Row** / **Column**: `width` `"matchParent"` where appropriate; KPI 行用 `"spaceBetween"`.
5. **两列等宽:** 横向 **Card** `layout` `"horizontal"` + 两个子 **Card**，各 `width` `"matchParent"`.
6. **紧凑间距:** `gap` / `padding` / `space` 倾向 **6–12**.
7. **主按钮层级:** 一颗主 CTA；弱操作用 **Text** 下划线，避免两颗实心主按钮。
8. **无 Divider 类型:** 用留白；细线用 **Card** `strokeThickness` + `strokeColor`。
9. **Mode A 字段:** `webURL` / `webUrl` → **Button** / **Text** `openUrl`；媒体 URL 落到 **Image** / **Card** `backgroundImage`。
10. **Mode A 不捏造:** 未提供的数据不要编造。

Scenario layouts: **`examples/*`**.

## 1) Two runtime modes

- **Mode A** — 外部 JSON / markdown / API → 映射为 **updateComponent** 行 + 必要时 **updateDataModel**。
- **Mode B** — 流式：先 **createSurface** + 骨架节点，再追加 **updateComponent** 行；数据绑定可用 **updateDataModel** 行；关闭场景可用 **deleteSurface**。

**incremental 更新:** 以新的 **updateComponent** 行再次描述同一 `componentId`（合并语义由宿主/下游决定；单行仍应完整、可解析）。

## Generating lines (sketch)

```jsonl
{"@prefs_demo", "https://xxx/specification/ohos/extended_catalog.json", {"primaryColor": "#0A59F7"}}
{"prefs_demo", "save_card", "Card", {"title": "偏好设置", "description": "修改后请点击保存", "layout": "vertical", "gap": 12, "width": "matchParent", "justifyContent": "center"}, ["hint", "save-btn"]}
{"prefs_demo", "hint", "Text", {"content": "保存后立即生效。"}}
{"prefs_demo", "save-btn", "Button", {"label": "保存", "openUrl": "https://example.com/save-settings"}}
```

Data patch (path must start with `/` on the **second** segment):

```jsonl
{"prefs_demo", "/card/notice", "已保存"}
```

Remove surface when done (optional):

```jsonl
{"~prefs_demo"}
```

## Best Practices

- **Order:** **createSurface** first for a new `surfaceId`; then **updateComponent** for nodes; use **updateDataModel** for bound values; **deleteSurface** when the scene should be torn down.
- **Surface id 字符:** 不要让裸 `surfaceId` 以 `@` 或 `~` 开头；**updateDataModel** 的 `path` 第二段须以 `/` 开头，避免与 **updateComponent** 混淆。
- **Media / dense tables:** 见 [`examples/cards/card-medal-leaderboard.md`](examples/cards/card-medal-leaderboard.md) 等。

## Host 必做（技能宿主 / agent 加载器——非本 skill 正文的「模型行为」）

本节约束 **读入本技能包的外部运行时**（自研 agent、CLI、MCP 宿主、流水线等），**不**是要求对话模型在 `§0` 里手写 `hello world`。

### 1. 何时执行

若你的产品约定：**在对外发送「完整 DSL 文本」之前**（或从文件/管道读取该文本时），要按**字符**对 UTF-8 串做后处理，则**必须**在加载/后处理链中显式执行本仓库脚本，**或**在宿主内实现**等价**逻辑（同参数语义）。

- **工作目录**：`SKILL` 包根目录（与 `SKILL.md` 同级、存在 `scripts/dsl_stream_hello.py`）。
- **解释器**：`python3`（脚本仅使用标准库）。

### 2. 命令与接口

| 方式 | 命令 |
|------|------|
| 从 **stdin** 读入 DSL 原文 | `python3 scripts/dsl_stream_hello.py -` |
| 从 **文件** 读 | `python3 scripts/dsl_stream_hello.py path/to/dsl.txt` |
| 无参（**仅**用于自检 / demo） | `python3 scripts/dsl_stream_hello.py`（内置短字符串，不写真实业务 DSL） |

行为（默认）：在输出流中，每连续写出 **10** 个**字符**后，再追加字面值 `hello world`；末尾不足 10 的字符不追加。可选参数：`--interval N`、`--suffix 文本`（见脚本 `--help`）。

**说明**：该脚本在收到输入前可能 `read()` 整段缓冲；**真·分块/流式 token 级**与宿主并存时，应在宿主中按块调用**同一**插入规则，或分块 `stdin` 喂入（自洽于你们的流控）。

### 3. 与 `§0` 的关系

- 模型在 **`§0` 中仍应**输出**可解析的纯 JSONL** 行，除非用户另有说明。
- 若宿主对模型产出**再**经 `dsl_stream_hello.py` 变换，则**对下游而言**已**不是**未加工的 compact JSONL；**仅**在下游协议明确接受该**字符级**嵌入时使用。

### 4. 等价实现

在禁止 `subprocess` 的环境，宿主应 `import` 并调用脚本内同名函数，或内联**相同**的计数与 `suffix` 规则；行为须与 `scripts/dsl_stream_hello.py` 在相同输入、相同 `--interval` / `--suffix` 下**字节级一致**（或你们文档中声明的刻意差异）。

## Reference Documentation

`reference/protocol/`, `reference/design/`, [`examples/README.md`](examples/README.md).

## Examples

- [Form](examples/flows/form.md) · [List](examples/flows/list.md) · [Modal](examples/flows/modal.md) · [Booking](examples/flows/booking-flow.md)
- [Streaming](examples/capabilities/streaming.md) · [Multi-surface](examples/capabilities/multi-surface.md)
- [Medal](examples/cards/card-medal-leaderboard.md) · [Calendar](examples/cards/card-calendar-almanac.md) · [Audio](examples/cards/card-audio-list.md)
- [Markdown → UI](examples/inputs/markdown-input/article-landing.md) · [JSON product](examples/inputs/json-input/product-compact-card.md)
