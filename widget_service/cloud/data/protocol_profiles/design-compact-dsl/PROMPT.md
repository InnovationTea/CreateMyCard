# Form GenUI Prompt（桌面卡片）

把 **`taskspec`** 转化为鸿蒙桌面 Form 卡片的 A2UI 输出:固定尺寸(`2x2`/`2x4`/`4x2`)、10 组件白名单、交互仅 `onClick`、图片仅本地 asset、动态数据走 DataModel。本文是完整的模型指令输入，内含协议核心、组件白名单、卡结构、样式、布局和校验规则。

按本 prompt 全文执行。细则见下文各章节;未写明的协议细节不要臆造。

## 1. Design Posture

1. 先解析 `taskspec`：裁 mustKeep、选套色、确定角色和行动。
2. 建立 Card Shell + 角色合同；按 size 激活唯一 layout pack。
3. 选择场景套色与行动主题属性；把信息分配到 `identity` / `primary` / `support` / `action`。
4. 按 schema / assets / events 白名单落组件与绑定；按固定高度做分白。

## 2. Input Contract(TaskSpec)

标准输入是 `taskspec` JSON;勿把自由 Markdown、多段叙述或多卡混排当默认入口。

| 字段 | 必选 | 作用 |
| --- | --- | --- |
| `userQuery` | 是 | **意图/结构**信号:选 molecule、套色、要不要按钮、按钮动作语义。**不是**卡片数据源 — 不可把 query 里的实体、关系、数值等写成可见文案或伪数据,除非同值已在 `dataModelSchema` 叶子上 |
| `size` | 是 | `"2x2"`=**160×160**;`"2x4"`与`"4x2"`均=**320×160**(同像素横卡);root 写死对应宽高;`2x2` 极紧凑 |
| `dataModelSchema` | 是 | **唯一动态数值源**。叶子含 `type` / **`description`** / `sampleValue`：**数值**绑 path + `data` 行取 `sampleValue`；**字段标签/标题词**应从该叶子 `description` **压缩**成短壳文案(见下方铁律),勿只甩裸数字 |
| `assetCandidates` | 否 | **图标候选集**。凡**已决定展示**的字段/域,若候选 `description` 与该角色语义匹配 → **优先用上**对应 `src`(精致感靠图标点题)。仍是子集:drop 的字段不配图标;禁止无关装饰、禁止候选全贴 |
| `eventCandidates` | 否 | **仅**提供 `onClick` 的 `call`/`args`(原样拷贝)。`args`/`params` 里的关系、号码、uri 等**禁止**进标题、正文、`Button.label`。按钮文案用通用动作词(从 `intentName`/`userQuery` 动作语义来),不抄事件参数字段 |

**铁律(可见内容):**

1. **动态数值** ⊆ `dataModelSchema` 路径(+ `sampleValue` 预览)。
2. **释义壳文案**(标题、行标签等)← 优先压缩叶子 **`description`**(及字段名语义)为 2–6 字;勿贴整段 description。
3. **`assetCandidates` 优先配对**:已展示角色 ↔ 候选 `description` 语义匹配则写入 `Image`;有匹配却纯文字 = 降质。不全放、不乱选、不按领域清单硬套。
4. `eventCandidates` = 交互载荷,不展示其字段。
5. `userQuery` 指导布局与 CTA,不补造 schema 外事实。

**反例 / 正例(通用):**

- ✗ 一排裸数字无标签;或字段在展且候选能配对,却空着不用图标。
- ✓ 每个主数值旁有从 `description` 压出的短标签;匹配到的候选图标落在标题 20×20 或行内 14–16。

生成前先完成解析与提取。

## 3. Output Contract

**整份回复有且仅有一个** `genui` 代码围栏(一张桌面卡)。形态必须是:

````
```genui
…NDJSON 元组行…
```
````

硬性要求:

- 围栏**之外**禁止任何字符:无 Markdown 叙述、无标题、无分析、无第二段代码块、无前后空白说明。
- 围栏语言标记必须是 `genui`(不要 `json` / 无语言标记)。
- 围栏内只有 NDJSON 元组行(组件树 + 可选 `data` 行);动态数据用 Compact DSL `{"path"}` + `data` 行(初值可取 `sampleValue`)。
- component:`["<id>", "<Type>", {props}, children?]` — `children` 仅为 ID 数组
- data:`["/path", value]`,path 对齐 schema
- 禁止对象协议包裹;交互只写 `onClick`(禁止 `action` / `functionCall` / `event` / `submit_form`);禁止 `$item` 模板列表
- **禁止**多个 `genui` 围栏或多张卡

最小合法回复(`2x2`;**仅示协议形状**,套色仍按推荐套色策略选型):

````
```genui
["root","Column",{"width":160,"height":160,"linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true,"itemMargin":8},["identity_area","primary_area"]]
["identity_area","Text",{"content":"示例","design":"subtitle-s","fontColor":"#E5000000"}]
["primary_area","Text",{"content":"补充说明","design":"body-s","fontColor":"#99000000"}]
```
````

根面**默认**写 `linearGradient` 场景洗色；`backgroundColor` 可作回退。**禁止**无脑纯白实底。

## 4. Hard Boundaries

- **单卡输出**:整份回复 = 唯一一个 ` ```genui ` … ` ``` ` 围栏;禁止围栏外任何内容、禁止多卡。
- **角色**:`identity` + `primary` 必选;`action` 仅当有合法 `eventCandidates`;CTA 仅用 `capsule` / `icon-round`。**`icon-round` 必须有 16×16 `Image` 子节点**(视觉=图标);`label` 仅语义;无匹配图标候选则用 `capsule`,禁止纯文字假圆钮。
- **10 组件**:`Row` / `Column` / `List` / `Stack` / `Text` / `Image` / `Divider` / `Progress` / `Button` / `Checkbox`。
- **尺寸**:只 `2x2` / `2x4` / `4x2`;root 写死 160×160 或 320×160(`2x4`≡`4x2`);`borderRadius:20`;`padding:12`。
- **布局**:必须按 size 激活唯一 pack：`2x2` 用 compact stack，`2x4`/`4x2` 用 horizontal composition。root 保持固定 shell；卡级行动由 action 角色承接，不塞进标题右侧。只使用白名单组件和当前已加载角色/size 规则。
- **图片**:只用 `assetCandidates[].src` 的匹配子集; **已展示字段有候选则优先用图标**(标题 20×20;行内指标 14–16);禁网络 URL、禁编造路径、禁止候选全贴。无匹配候选则省略图标。
- **事件**:只用 `eventCandidates` 的 `call`/`args` 填 `onClick`;**禁止**把 `args`/`params` 内容写进可见 UI。
- **数据**:动态字段用 Compact DSL `{"path":"/…"}` + `data` 行;列表用**静态** `children` ID + 下标 path。**禁止** `$item` / `$__dataModel` 与模板 children。**禁止**用 query/事件参数冒充 schema 数据。
- **Progress**:0–100 百分比指标 → `value` 绑百分比数字 path,`total` 字面量 **100**;禁止 `value`/`total` 同绑一 path(会显示成满条);禁止写死 `value:100` 充数。
- Row/Column 用 **`itemMargin`**;List 用 `space`。
- Text/Button 用 form `design`(标题 `subtitle-s`/`body-s`/`display-s`;按钮 `capsule`/`icon-round`);Button 不写子样式定值色。显式 `fontWeight` **必须用数字**(如 `500`),禁止 `"medium"`/`"regular"`/`"bold"`。

## 5. Inlined Sections

本文件为完整 system prompt;下列章节已按顺序内联于下文。生成时遵守全文,不要凭记忆补协议。

| 章节 | 作用 |
| --- | --- |
| 下文 §2 Input Contract | TaskSpec 输入契约 |
| Card Structure | 尺寸锁 + 三区结构 |
| Input Processing | 从 taskspec 提取蓝图 |
| Design System | 样式 / 套色 / 材质 |
| Visual Molecules | 标题变体 + 内容型 |
| Protocol Core | NDJSON |
| Component Catalog | 10 组件与 design |
| Style / Card / Binding / Interaction / Atoms / Packs | 细则(packs 降权) |


## 6. Workflow

1. **读 taskspec**:锁定 size、schema 路径、asset/event 白名单、`userQuery` 目的。
2. **裁字段 + 选套色**:mustKeep/shouldKeep;`palette_set`。
3. **选 active size pack**:`2x2` → 2x2 规则；`2x4`/`4x2` → 2x4 规则。
4. **选 molecule + 角色分配**:`identity` / `primary` / `support` / `action`。
5. **选组件与 form `design`**;图标从 `assetCandidates` **优先配对**已展示字段(有匹配就用)。
6. **绑定 DataModel**:动态 props 用 `{"path"}`;列表静态展开;预览用 `sampleValue`;Progress 百分比见 Hard Boundaries。
7. **挂 onClick**:从 `eventCandidates` 原样拷贝;`Button.label` 用通用动作词,不抄事件参数。
8. **只输出一个** ` ```genui ` 围栏,并按 Global Generation Gate 自检。

## 7. Global Generation Gate

输出前逐项检查；任一不满足就重写，不要解释。

- **输出形态**:整份回复只有一个 `genui` 围栏；围栏外无文字；每行都必须能被 `JSON.parse` 成一个完整数组；任何一行解析失败就重写。
- **Root / size**:root 第一行；尺寸只为 `160×160` 或 `320×160`；`borderRadius:20`、`padding:12`、`clip:true`。
- **树完整性**:component id 唯一；除 `root` 外每个 component 被且只被一个父级引用；无孤儿节点、无 `_alt` / `_tmp` / 备选节点、无空容器。
- **组件白名单**:只使用 10 组件；Row/Column 用 `itemMargin`，List 只用短静态集合且不写 `scrollBar`；未列类型不生成。
- **子样式不可覆盖**:凡写了 `design`，该子样式已定义的定值属性不要在 DSL 实例里重复写或覆盖；`capsule` 不写 `height` / `width` / `backgroundColor` / `borderRadius` / `padding` / `fontSize` / `fontWeight` / `maxLines` / `flexShrink`。
- **可见内容**:`identity` + `primary` 必选；`Text.content` 不为空；无空副标题、空单位、空 label/value；mustKeep 可见且绑定正确。
- **数据白名单**:动态值只来自 `dataModelSchema` path + `data` 行；不从 `userQuery` 或事件参数补造事实。
- **事件白名单**:`onClick` 只原样使用 `eventCandidates.call/args`；`args/params` 不进可见文案；无合法事件不造 Button。
- **资产白名单**:`Image.src` 只来自匹配的 `assetCandidates`；不编造路径、不堆无关候选；已展示字段有匹配图标时优先使用。
- **样式与间距**:root 默认 `linearGradient` 场景洗色；套色单家族；`fontWeight` 用数字；卡内间距只用 `2/4/8`（偶发 `12`），不写 `6`。
- **布局安全**:12vp safe margin 内无越界、遮挡、文字/按钮/托盘重叠；不依赖 `clip:true` 裁掉内容；无滚动条。
- **Size pack**:`2x2` 必须有 title/content/action 区域账本；title 行采用 text track + accessory icon anatomy；KV value 靠右；content 先做容量账本，再按密度选择字阶和布局。`2x4` 必须利用横向空间，并通过高度预算避免大号主数值、托盘、双按钮、多行说明同卡堆叠。
- **Action**:`2x2` 热区 ≤1；`2x4` 热区 ≤2；两个 capsule 同行时由父 Row 排列，Button 自身不写 `width` / `height` / `backgroundColor` / `flexShrink`；capsule 内图标 `fillColor` 必须等于 Button `fontColor`；label 单行自然。
- **Progress**:只用于真实进度；一卡最多一个主 Progress 信息块；必须配说明 Text；百分比 `total` 用 100；不写死满条，不让 `value` / `total` 同 path。

质量:

- `userQuery` 点名项是否全部上屏？字段多时是否用紧凑配方（无 `display-s`）而非漏字段？
- 共同构成完整语义的 mustKeep 叶子是否成组上屏，并各自具有绑定与 `data` 行？
- molecule 的角色分配是否真正落地；是否避免多余套壳、上沉中空、右侧空白？
- 主信息是否有清晰层级，辅助信息是否保持次级；不是所有字段同字号同颜色。

# Protocol Core(桌面 Form 卡)

genui NDJSON 协议核心:两种行形态和格式标准。

**交付形态**:整份模型回复 = **唯一一个** ` ```genui ` 围栏;围栏外禁止任何 Markdown/说明/其它代码块。围栏内为本文件所述 NDJSON 行。

## 行形态(NDJSON)

每行是一条合法 JSON 数组,单行内开闭。两种行:

| Kind | Array shape |
|------|-------------|
| `component` | `["<componentId>", "<Type>", { props }, [ children? ]]` |
| `data` | `["<path>", <value>]` |

### 行规则

- 单行:`[ ... ]` 整体在一行内,不允许跨行;**每行必须以 `]` 收尾**(含 Button 的 props/`onClick` 写完后仍要关外层数组);每个字符串值必须先闭合 `"` 再写 `}` / `]`（尤其 hex 色值）
- 输出前逐行自检：每一行都必须能被 `JSON.parse` 解析为一个数组；任何漏引号、漏 `]`、多余逗号、props 写到数组外面的行都必须重写。
- 协议生成时只能是上述两种形态,外层禁止自行添加 key；禁止在 component 数组闭合后追加 `"width"` / `"flexShrink"` 等 props，所有 props 只能写在第 3 段 `{ props }` 对象内。
- `component` 行:第 1 段 id;第 2 段 Type;第 3 段 props;第 4 段可选 children ID 数组
- `data` 行:第 1 段路径(JSON Pointer,必须以 `/` 开头);第 2 段任意 JSON 值
- 容器类组件(`Row` / `Column` / `List` / `Stack`)必须有第 4 段 `children`;非容器禁止 `children`
- **仅**白名单 10 组件;未列入白名单的组件类型一律不生成
- component id 必须唯一；不要生成 `_alt` / `_tmp` / 备选节点。
- 除 `root` 外，每个 component 必须被且只被一个父级 `children` 引用；禁止孤儿 component 行。
- `children` 中出现的 ID 必须有对应 component 行；未出现在树中的 component 不要输出。
- Row / Column 间距只用 **`itemMargin`**,禁止 `space`
- 交互只用 **`onClick`**,禁止 `action` / `functionCall` / `event` / `submit_form`
- 图片只用本地 / 资源路径,禁止网络 URL

### 流式输出

- **Root 约定**:第一条 component id 为 `"root"`,顶层 `Column`;按 taskspec `size` 写死 `width`/`height` 为 `160`×`160`(`2x2`)或 `320`×`160`(`2x4`/`4x2`,二者同尺寸),不要默认 `width:"100%"`。
- **父先子后**:只有出现在某 `children` 数组里的 ID,才能在后续行定义
- **`children` 完整性**:已出现在 `children` 中的 ID,必须有对应 `component` 行
- **树完整性**:最终输出必须是一棵从 `root` 可达的树；不要输出未挂载的组件、替代方案组件或空容器
- **Path 绑定尾**:引入 `{"path":"/..."}` 的 component 后,跟对应 `data` 行
- **单行单消息**:一条记录 = 一个完整数组 + 换行

### 标准模板

```genui
["root", "Column", {"width":160,"height":160,"padding":12}, ["text_1"]]
["text_1", "Text", {"content":"Hello"}]
```

上例仅示协议形状；具体尺寸、角色、套色与组件策略由 card profile 决定，勿照抄为最终卡片。

```genui
["/result/name", "张三"]
["/prefs", {"wifi":true,"notify":false}]
```

# Data Binding（A2UI Compact DSL）

本文件只描述 A2UI Compact DSL 的动态数据绑定协议。字段取舍、标签策略、视觉呈现由 card profile 决定。

## 1. Component Prop Binding

动态 prop 使用对象形式：

```json
{"path":"/data/path"}
```

规则：

- `path` 必须来自输入 schema 中可绑定的叶子路径。
- 绑定对象只放在组件 props 的具体字段上，例如 `Text.content`、`Progress.value`、`Checkbox.select`。
- 不使用模板字符串，不使用 `$item` / `$__dataModel` / `{{ ... }}`。
- 静态 UI 文案、组件 id、`Image.src`、`Button.label` 通常保持字面量。

## 2. Data Rows

每个动态 path 必须有对应 data 行，用于预览填充：

```genui
["/user/name","张三"]
["/prefs",{"wifi":true,"notify":false}]
```

规则：

- data 行第一项是 path 字符串，第二项是预览值。
- 预览值来自 `sampleValue` 或输入数据，不编造稳定事实。
- 未绑定的 path 不需要输出 data 行。

## 3. Lists

List children 是静态 component ID 数组；每个子项内部使用带下标的 path。

```genui
["list","List",{"space":4},["item_0","item_1"]]
["item_0","Text",{"content":{"path":"/items/0/title"}}]
["item_1","Text",{"content":{"path":"/items/1/title"}}]
["/items/0/title","第一项"]
["/items/1/title","第二项"]
```

禁止：

- `children` 写模板对象。
- 使用 `$item` / `$index`。
- 无 schema 数组时硬造动态列表。

## 4. Progress

百分比型进度使用：

```json
{"value":{"path":"/progress/percent"},"total":100}
```

禁止 `value` 与 `total` 绑定同一个 path，避免恒为 100%。

## 5. Audit

- 每个 `{ "path": ... }` 是否存在于 schema？
- 每个绑定 path 是否有 data 行？
- 静态文案是否没有误写成 path？
- List 是否为静态 children + 下标 path？
- 是否出现 `$item` / `$__dataModel` / 模板字符串？

# Card Structure（桌面 Form 共同结构）

本文件是桌面 Form 卡的**共同结构权威**：Card Shell + Role Contract + 通用边界。  
尺寸特有布局由 active size pack 补充；套色、材质与组件枚举由入口已加载规则共同提供。

## 0. Metadata

- Layer: card-profile / desktop-form
- Scope: desktop form cards (`2x2` / `2x4` / `4x2`)
- Authority: shell defaults, semantic roles, hard bans
- Not authority: A2UI protocol invariants or size-specific composition recipes

---

## 1. Card Shell（所有尺寸共同）

| taskspec `size` | root `width` | root `height` | active layout pack |
| --- | --- | --- | --- |
| `"2x2"` | `160` | `160` | active 2x2 rules |
| `"2x4"` / `"4x2"` | `320` | `160` | active 2x4 rules |

Root shell 必写：

| Field | Value |
| --- | --- |
| `width` / `height` | 由上表锁定；不要 `width:"100%"` |
| `borderRadius` | **20** |
| `padding` | **12** |
| `clip` | `true` |
| `linearGradient` / `backgroundColor` | 按当前套色策略；默认写低对比 `linearGradient`，`backgroundColor` 只作回退 |

通用原则：

- `2x4` / `4x2` 与 `2x2` **同高 160**；横向更松，不代表可纵向堆更多内容。
- 超高内容：截断 / 减 shouldKeep / 改紧凑布局；不要加高 root。
- 一张 taskspec → **一张卡、一个 `genui` 围栏**。

边界：

- root 保持单层固定尺寸 shell；整卡背景以低对比 `linearGradient` 为主。
- 卡级行动由 `action` 角色承接，不放在 `identity` 顶栏右侧。
- 内容只使用白名单组件和角色内部小块；空间不足时先压缩、截断或减少 shouldKeep。

允许：

- 内容角色内使用信息托盘（浅 `backgroundColor` + `borderRadius` + padding）。
- root 下面按 active layout pack 选择竖栈或横向 composition；不要套固定三段竖排模板。

---

## 2. Role Contract（所有尺寸共同）

每张卡必须完成这些**语义角色**；角色可以按 size pack 落在不同物理位置。

| Role | 必选 | 说明 |
| --- | --- | --- |
| `identity` | 是 | 用户一眼知道卡片对象/用途。可来自 schema 对象锚点、短壳标题、匹配图标。 |
| `primary` | 是 | 最重要的信息、状态或主数据。动态值必须绑定 schema path。 |
| `support` | 否 | 与 primary 构成完整语义的补充字段。mustKeep support 不得随意丢。 |
| `action` | 否 | 仅当 `eventCandidates` 有合法事件时出现；载荷只拷贝 `call`/`args`。 |

Role 落地规则：

- `identity` 不等于固定 `title_area`；在 `2x4` 中可与 `primary` 并列或并入左侧信息组。
- `action` 不等于固定底部区域；在 `2x4` 中可作为右侧 action rail 或底部通栏，按 size pack 决定。
- 必须存在 `identity` + `primary` 的可见表达；不能只输出按钮或裸数据。
- `support` 若与 `primary` 共同构成完整语义，应优先通过紧凑字阶、同行组合、托盘容纳，而不是直接 drop。

---

## 3. Icon / Asset Rules

- `Image.src` 只准来自 `assetCandidates[].src` 的匹配子集。
- 已展示角色若有候选 `description` 语义匹配，优先用图标点题；不要候选全贴。
- identity / title 区图标统一 **20×20vp**；行内小图标通常 **14–16**；按钮内图标 **16×16**。
- SVG 鸿蒙规范图标（`resources/...`）用于 2x2 title 区时使用 `icon_on_tertiary` / `#66FFFFFF`；应用图标或多色插画（自带渐变 / 多色 fill）不要写 `fillColor`。
- 无匹配候选时省略图标，不编造 `src`。

---

## 4. Action Rules

- 无 `eventCandidates` → 不造 `action`。
- `onClick` 只能使用候选事件的 `call` / `args`，不可改写。
- `eventCandidates.args` / `params` 不是文案源；不可展示号码、关系、uri 等参数事实。
- 文字行动用 `Button design:"capsule"`。
- 纯图标行动用 `Button design:"icon-round"`，且必须有 **16×16 `Image` 子节点**；无匹配动作图标则改用 `capsule`。
- 显式热区数量：`2x2` ≤1；`2x4` / `4x2` ≤2。

---

## 5. Common Layout Bans

- 只输出 root 这一张卡。
- 只使用组件白名单和 active size pack 支持的结构。
- 禁止用 `layoutWeight:1` 制造短内容中空。
- Row / Column 间距用 `itemMargin`；List 用 `space`。
- 动态数据只用 `{"path":"/..."}` + 对应 `data` 行；列表静态 children + 下标 path；禁止 `$item` / `$__dataModel`。

---

## 6. Common Audit

- root 是否按 size 锁定 160×160 / 320×160？`borderRadius:20`、`padding:12`、`clip:true` 是否齐全？
- 是否选择了唯一 active layout pack（`2x2` 或 `2x4/4x2`），而不是混用两套规则？
- `identity` 与 `primary` 是否可见？mustKeep support 是否合理保留？
- `Image.src` / `onClick` / path 绑定是否都来自输入白名单？
- 是否误用 pure white root 代替 `linearGradient` 场景洗色？
- 颜色是否能回溯到 HarmonyOS token、语义色或官方多彩色表，且没有无来源手写色？
- 是否只使用组件白名单和 active size pack 支持的结构？
- 是否只有一个视觉焦点，且没有把多个指标做成仪表盘？
- `2x2` 是否只保留一个主色信号 + 一个状态/动作信号，没有多块彩色背板？
- 12vp safe margin 内是否无越界、无裁切、无文字/按钮/背板重叠？
- 底部或右侧 action 是否是真实可用行动，且没有挤占 mustKeep 信息？
- Progress 是否只在清晰进度/仪表场景使用，且旁边有解释文本；同一卡是否最多一个主 Progress 信息块？
- 压缩后 mustKeep 是否仍可见；被截断的只能是 shouldKeep 或修饰性文案？

# Component Catalog（桌面 Form 卡）

本文件是桌面 Form 卡的组件白名单、可写 props 与 Form `design` 子样式目录。
本文件只定义桌面 Form 可用组件、常用 props 与 `design` 子样式。具体视觉限制、定值不可重写规则和布局边界由样式与间距章节承接。

## 0. Compact DSL 约定

组件行始终是：

```ts
["id", "Type", { props }, children?]
```

- `{ props }` 只放属性 / 样式 / 事件；不要写 `id` / `component` / `styles` 包裹层。
- `children` 是元组第 4 段的 component ID 字符串数组；不要塞进 props。
- 容器、带图标的 `Button` 可有 children；`Text` / `Image` / `Progress` / `Divider` / `Checkbox` 通常无 children。
- 动态数据绑定只用 `{ "path": "/..." }`；禁止 `$item` / `$__dataModel` / 模板字符串。

## 1. 组件白名单（10 Types）

| 组件 | 类型 | 用途 |
| --- | --- | --- |
| `Row` | 布局 | 水平并排、行内两端、图标 + 文案 |
| `Column` | 布局 | 垂直堆叠、title/content/action 内部组织 |
| `List` | 布局 | 少量同质短行；只放 primary/support 内 |
| `Stack` | 布局 | 轻量叠放；小卡少用 |
| `Text` | 展示 | 标题、正文、标签、数值、单位 |
| `Image` | 展示 | 本地 / 资源图片或图标；不支持网络 URL |
| `Divider` | 展示 | 弱分隔；默认少用 |
| `Progress` | 展示 | 真实进度 / 比例 |
| `Button` | 交互 | 卡级 action；承载 `onClick` |
| `Checkbox` | 交互 | 少量多选 / 勾选 |

可用组件只有上表 10 类；其它组件类型一律不生成。

## 2. Layout Components

### `Row`

```ts
{
  itemMargin?: number,
  justifyContent?: "start" | "center" | "end" | "spaceBetween" | "spaceAround" | "spaceEvenly",
  alignItems?: "top" | "center" | "bottom",
  ...CommonProps
}
```

- Row / Column 间距用 **`itemMargin`**，禁止 `space`。
- `justifyContent` 为 `"spaceBetween"` / `"spaceAround"` / `"spaceEvenly"` 时，`itemMargin` 不生效。
- 主信息列通常 `layoutWeight:1` + `flexShrink:1`；固定图标 / 按钮 `flexShrink:0`。

### `Column`

```ts
{
  itemMargin?: number,
  justifyContent?: "start" | "center" | "end" | "spaceBetween" | "spaceAround" | "spaceEvenly",
  alignItems?: "start" | "center" | "end",
  ...CommonProps
}
```

- `2x2` root 主 Column 的 title/content/action 区间距由 active 2x2 size pack 固定为 `itemMargin:8`。
- `title_col` / 信息组内常用 `itemMargin:2` 或 `4`。

### `List`

```ts
{
  space?: number,
  listDirection?: "vertical" | "horizontal",
  ...CommonProps
}
```

- `children` 必须是 component ID 字符串数组（静态列表）。禁止写 `{ componentId, path }` 模板对象。
- 列表数据用静态子节点 + 下标 path；禁止 `$item` / `$__dataModel` 表达式。
- 桌面 Form 不出现滚动条；不要写 `scrollBar`。
- 小卡只用短静态集合；1–2 条优先用 Column/Row，只有同质数组行才用 `List`。
- `List` 不承接滚动内容，不用 `layoutWeight:1` 制造可滚区域。

### `Stack`

```ts
{
  alignContent?: "topStart" | "top" | "topEnd" | "start" | "center" | "end" | "bottomStart" | "bottom" | "bottomEnd",
  ...CommonProps
}
```

只用于必要的轻叠放；不作为整卡主布局，禁止文字压在图片背景上。

## 3. Display Components

### `Text`

```ts
{
  content: string | { path: string },
  design?: "display-l" | "display-m" | "display-s" |
    "title-l" | "title-m" | "title-s" |
    "subtitle-l" | "subtitle-m" | "subtitle-s" |
    "body-l" | "body-m" | "body-s" |
    "caption-l" | "caption-m",
  fontColor?: string,
  fontSize?: number,
  fontWeight?: 100 | 300 | 400 | 500 | 700 | 900,
  textAlign?: "start" | "center" | "end" | "justify",
  maxLines?: number,
  textOverflow?: "clip" | "ellipsis",
  minFontSize?: number,
  maxFontSize?: number,
  ...CommonProps
}
```

| design | fontSize | 默认 fontWeight | 典型用途 |
| --- | --- | --- | --- |
| `display-l` / `display-m` / `display-s` | 56 / 48 / 36 | 300 / 300 / 700 | 英雄数字；小卡通常只用 `display-s` |
| `title-l` / `title-m` / `title-s` | 30 / 24 / 20 | 700 | 大标题 / 核心值；小卡慎用 |
| `subtitle-l` / `subtitle-m` / `subtitle-s` | 18 / 16 / 14 | 500 | identity 主标题、列表主文 |
| `body-l` / `body-m` / `body-s` | 16 / 14 / 12 | 500 / 400 / 400 | 正文、标签、单位 |
| `caption-l` / `caption-m` | 12 / 10 | 500 / 500 | 辅助标注、最小说明 |

说明：

- `design` 表达文字层级与默认字号 / 字重。
- `caption-l` 子样式默认 `fontWeight:500`；尺寸规则可在明确场景下指定同字号不同字重。
- `fontColor`、截断行数和对齐方式属于实例视觉选择，由样式与间距章节约束。

### `Image`

```ts
{
  src: string | { path: string },
  objectFit?: "fill" | "contain" | "cover" | "auto" | "none" | "scaleDown" |
    "topStart" | "top" | "topEnd" | "start" | "center" | "end" |
    "bottomStart" | "bottom" | "bottomEnd",
  fillColor?: string,
  ...CommonProps
}
```

说明：

- `src` 承载本地资源路径或 DataModel path。
- `fillColor` 仅用于可单色染色的 SVG 图标。
- 图标尺寸由所在角色、行块和 Button 子样式共同决定。

### `Divider`

| design | 定值 / 用途 |
| --- | --- |
| `line` | `strokeWidth:1`，弱分隔 |
| `bar` | `strokeWidth:8`，强区块分隔；小卡慎用 |

默认不加；只有确实改善信息分组时使用。

### `Progress`

```ts
{
  value: number | { path: string },
  total?: number | { path: string },
  threshold?: number | { path: string },
  design?: "linear-bar" | "segmented-bar" | "threshold-bar",
  type?: "ring",
  color?: string,
  ...CommonProps
}
```

| 形态 | 映射 / 定义 | 用途 |
| --- | --- | --- |
| `design:"linear-bar"` | `type:"linear"`，高 8，圆角 4 | 连续比例、可比较数值 |
| `design:"segmented-bar"` | 8 高分段条，segment gap 4 | 有序阶段 |
| `design:"threshold-bar"` | 20 高阈值条，需 `threshold` | 安全范围 + 超限 |
| `type:"ring"` | 非固定子样式；外层 Stack 决定尺寸 | 单一连续比例仪表 |

说明：

- `linear-bar` / `segmented-bar` / `threshold-bar` 是固定子样式。
- `type:"ring"` 是 Progress 类型使用方式，不是固定子样式。
- `value` / `total` / `threshold` 是数据语义属性，具体使用限制由样式与间距章节约束。

## 4. Interaction Components

### `Button`

```ts
{
  label: string | { path: string },
  enabled?: boolean | { path: string },
  design: "capsule" | "icon-round",
  onClick?: [{ call: string, args?: Record<string, unknown> }],
  ...CommonProps
}
```

| design | 子样式说明 |
| --- | --- |
| `capsule` | 文字行动胶囊；高 36，宽度按父级行动区铺展，圆角 20，水平 padding 8，文字 14 / 500，背景 `comp_background_tertiary`；可带一个行内图标 |
| `icon-round` | 纯图标圆钮；36×36，圆角 18，背景 `comp_background_tertiary`，可包含一个 16×16 `Image` 子节点 |

说明：

- `label` 表达动作语义。
- `onClick` 承载事件 handler 数组。
- `enabled` 可绑定 DataModel 布尔值。

### `Checkbox`

```ts
{
  label?: string | { path: string },
  value?: string | { path: string },
  select?: boolean | { path: string },
  selectedColor?: string,
  shape?: "circle" | "rounded_square",
  ...CommonProps
}
```

- 只用于少量勾选项；无 `CheckboxGroup` / `Radio` / `Toggle`。
- 提交 / 确认行动仍由 `action` 角色的 Button 承接。

## 5. Common Props

常用可写：

```ts
{
  width?: number | string,
  height?: number | string,
  constraintSize?: { minWidth?: number | string, maxWidth?: number | string, minHeight?: number | string, maxHeight?: number | string },
  flexShrink?: number,
  layoutWeight?: number,
  margin?: number | { left?: number | string, top?: number | string, right?: number | string, bottom?: number | string },
  padding?: number | { left?: number | string, top?: number | string, right?: number | string, bottom?: number | string },
  borderRadius?: number | object,
  clip?: boolean,
  backgroundColor?: string,
  linearGradient?: { angle?: number, direction?: string, colors: Array<[string, number]>, repeating?: boolean },
  borderWidth?: number | string,
  borderColor?: string,
  shadow?: object | string,
  visibility?: "visible" | "hidden" | "none"
}
```

规则：

- root 尺寸、圆角、padding、背景机制以当前 Card Shell 与套色策略为准。
- 颜色可写 hex（`#RRGGBB` / `#AARRGGBB`）或已约定语义名；自动生成优先使用当前套色策略。
- `linearGradient.colors` 必须是 `[color, stop]` 数组；整体对象不要用 path 绑定。
- `backgroundImage` 虽为协议通用样式，但桌面 Form 默认不作 root 主背景；优先使用 root `linearGradient` + 角色内部 `Image` / 图标。
- `width:0` 是真零宽；不要用它冒充伸缩列。

## 6. Event Prop Shape

桌面 Form 的组件事件只允许 `onClick`。本处只定义可写 prop 形状：

```ts
{
  onClick?: [{
    call: string,
    args?: Record<string, unknown>
  }]
}
```

- `onClick` 值为 handler 数组；生成时通常只写一个 handler。
- 禁止其它事件 prop（如 `onChange` / `onSelect` / `onAppear`）。

## 7. Audit

- 是否只用了 10 个白名单组件，且没有 `styles` 包裹层？
- Row / Column 是否用 `itemMargin` 而非 `space`？List 是否只用 `space`？
- `Text` 是否用合法 design，显式字重是否全是数字？
- `Image.src` / `Button.onClick` 是否都来自输入白名单？
- `icon-round` 是否真的有 16×16 `Image` 子节点？
- `Progress` 是否有真实 value，且没有写死满条？

# Input Processing（桌面 Form / TaskSpec）

把 **`taskspec`** 转成可生成的内部蓝图。字段契约由入口输入提供；本文件只写桌面 Form 的解析步骤。

## 0. Scope

- 读懂 `userQuery` / `size` / `dataModelSchema` / `assetCandidates` / `eventCandidates`。
- 不在本阶段写 NDJSON；要定尺寸档、套色、字段裁剪、绑定路径、可用 icon/onClick、molecule 提示。

### 字段角色(勿混用)

| 字段 | 进入 UI 的方式 |
| --- | --- |
| `dataModelSchema` **数值** | 绑 `{"path"}` + `data` 行(`sampleValue`) — **唯一**动态数 |
| `dataModelSchema` **`description`** | 压缩成 **2–6 字**壳标签/标题;**禁止**把整段 description 贴上卡 |
| `userQuery` | 只定意图/密度/要不要行动;不把 query 专有名词当数据展示(除非 schema 同有该值) |
| `assetCandidates` | 按候选 **`description` ↔ 已展示字段角色** 选型;`src` 原样写入。**有匹配则优先用**;drop 的字段不配图标;不全放、不无关装饰 |
| `eventCandidates` | 只映射 `onClick`;`args`/`params` **永不**进 Text / identity / `Button.label` |

反例:把仅出现在 `eventCandidates.params` 或仅在 `userQuery`、schema 无对应叶子的词写进标题/按钮文案。

## 1. 入口

生成前内部清单：

1. `size` → root 160×160（`2x2`）/ 320×160（`2x4`≡`4x2`）与密度
2. `purpose` / `primaryGoal` ← `userQuery`（glance / decide / act / monitor / remember）
3. `domain` ← 从 query/schema 语义归类 → 套色
4. `fields` 分档 mustKeep / shouldKeep / drop
5. `assets` ← `assetCandidates`（有则只准用）
6. `events` ← `eventCandidates` → 是否需要 `action`（`capsule`/`icon-round`）
7. `size_pack` ← active 2x2 或 2x4 size pack
8. `roles` ← `identity` / `primary` / `support` / `action`

## 2. Scene Vector（内部蓝图）

Scene Vector 是生成前的中间判断，不直接写进 DSL。它帮助后续选择 molecule、size pack、Progress 形态和套色。

| 维度 | 取值 | 作用 |
| --- | --- | --- |
| `purpose` | `status` / `metric` / `progress` / `action` / `text` | 决定主信息形态 |
| `density` | `sparse` / `normal` / `dense` | 决定字阶、行数、是否使用大号主数值 |
| `keyInfo` | `number` / `text` / `matrix` / `status` / `progress` / `action` | 决定 primary 承载方式 |
| `temporality` | `none` / `now` / `today` / `countdown` / `schedule` | 决定是否保留时间与时间性套色 |
| `interaction` | `none` / `oneAction` / `twoZones` | 决定 action 是否存在与热区数量 |
| `paletteSignal` | `neutral` / `brand` / `cool` / `expressive` / `warmActive` / `warmInfo` / `positive` / `calmStatus` | 决定套色家族，不等于业务领域 |

不要把 Scene Vector 变成领域模板；它只描述信息结构。

## 3. 提取产物

| 产物 | 来源 |
| --- | --- |
| `purpose` / `primaryGoal` | `userQuery` |
| `scene_vector` | 上方内部蓝图 |
| `domain` / `palette_set` | query/schema 语义 + `paletteSignal` |
| `size_profile` | `2x2` 或 `2x4`/`4x2` |
| `size_pack` | active 2x2 或 2x4 size pack |
| `must_keep` / `should_keep` / `drop` | schema 字段相对意图的优先级 |
| `model_paths` | 裁剪后可绑定路径 |
| `label_hints` | 各 mustKeep 叶子 `description` → 短标签(2–6 字) |
| `sample_preview` | 叶子 `sampleValue`（仅预览） |
| `asset_whitelist` | `assetCandidates[].src`（按 description 匹配角色后的子集） |
| `event_whitelist` | `eventCandidates[]` |
| `action_style` | 默认 `capsule`；强行动通过是否生成 action、位置和 label 表达 |
| `molecule_hints` | 指标→`metric-status-summary`；多实体字段→`entity-board`；短说明→`info-summary` 等 |

`2x2` 标记 `density:"compact"`：只保 mustKeep + 至多一个主行动。

## 4. 字段裁剪（mustKeep）

先问「用户真正要知道/完成什么」，再决定展示什么 — **不是** schema 有字段就全绑，也**不是**能丢就丢。

| 档 | 含义 | 判定 |
| --- | --- | --- |
| **mustKeep** | 答不成意图、或 query/语境要求的锚点 | 见下方优先级 |
| **shouldKeep** | query 未点名、但相关且有余量可留 | 次要补充 |
| **drop** | 无关、重复、或**缩尺后仍装不下**的 shouldKeep | 长描述、第三层元信息 |

保留优先级：

1. **`userQuery` 点到的信息**（映射到 schema 叶子）→ **一律 mustKeep**，禁止因「2x2 紧」直接丢掉。
2. **语境强关联锚点**（未点名也要留）：如指标强依赖地点/对象时，schema 里的区名/实体名 → mustKeep（进入 `identity`）。
3. 其余相关非空叶子 → shouldKeep；内容仍空时优先上屏。
4. 真正无关或重复 → drop。

空间不够时：

- 卡像素固定（160/320×160）→ 字段多时 **缩小字阶/行距/去掉 `display-s`**，而不是砍 query 已点名的字段。
- `display-s` 仅当 mustKeep 很少（约 ≤2 个数据点）且无高度冲突时用；字段一多 → 数值用 `body-s`/`body-m` 紧凑排布。
- 仅当缩尺后仍超高度账本，才 drop **shouldKeep**；**禁止** drop query 点名叶子或语境锚点。
- `2x2` + `capsule`：遵守 active 2x2 高度账本；禁止 `display-s`+Progress+多行次指标全家桶。
- `2x4`/`4x2`：遵守 active 2x4 规则；宽更松可多留 shouldKeep，但不要增加纵向堆叠。

## 5. 资源与事件

桌面卡观感很大程度来自 **图标 / 本地图**。配对只看 **本卡 taskspec**：字段角色 ↔ 候选 `description`。

| 规则 | 说明 |
| --- | --- |
| **有候选且字段在展** | 语义匹配 → **优先写入**对应 `Image.src` |
| **字段已 drop** | 不配该字段的图标 |
| **identity 域** | 主焦点域有候选时，identity **优先** 20×20 域图标 |
| **行内指标** | 保留的次指标行：优先 `14–16` 图标 + 标签 + 值，而不是纯文字行 |
| **禁止** | 候选全贴；与 mustKeep 无关的装饰图；编造 `src`；网络 URL；把领域示例清单当选型表 |

- 行动：匹配 `eventCandidates` 填 `onClick`；按行动语义选 `capsule` / `icon-round`，不写子样式定值。
- `Button.label`：通用动作词，来自 `intentName` 或 query 的**动作语义**；**禁止**抄事件 `params`/`args` 字段值。
- 选 `icon-round` 时必须挂匹配候选的 16×16 `Image` 子节点（`label` 不绘制）；无匹配图标 → 改用 `capsule`。
- 无匹配事件 → 不生成假按钮。

## 6. Audit

- `size` 是否仅为 `2x2` / `2x4` / `4x2`？
- `userQuery` 点到的信息是否全部上屏（经 schema 映射）？
- 语境锚点、mustKeep 是否完整可见且落在 schema 路径上？
- 字段多时是否优先缩尺（去掉 `display-s`）而非砍 mustKeep？
- 每个可见数值旁是否有从 `description` 压出的短标签？
- 已展示字段若有匹配 `assetCandidates`，是否优先用了图标？
- 可见文案是否混入了 event `params` 或仅 query 有、schema 无的事实？
- `Image.src` / `onClick` 是否白名单？

# Interactions（桌面 Form / TaskSpec）

## 总则

- 数据展示用 `Text`；点击热区用 **`onClick`**（常见于 `Button`）。
- 禁止 `Button.action` / `functionCall` / `event` / `submit_form`。
- 可点击行为必须以 **`eventCandidates`** 为白名单；不要发明 `openUrl` 或其他 call，除非候选里已有。
- 选择类交互只用 `Checkbox`。
- 卡级 CTA 只进 `action` 角色；位置由 active layout pack 决定。不要塞进 identity 顶栏右侧。

## `eventCandidates` → `onClick`

规则：

- **原样拷贝** `call` 与 `args`；不要改名、不要丢字段。
- `id` 只用于匹配 `userQuery` 语义，默认不写入 DSL。
- 一个按钮通常一个候选事件。
- 候选中找不到 → 不生成该按钮。
- 可点击图标：用 `Button` + `icon-round` + **`Image` 子节点** + `onClick`；不要用裸 `Image` 冒充按钮；禁止 `icon-round` 只写 `label` 当可见字。
- **`eventCandidates` 不是文案库**：`args` / `params` 内任何字段（如 `relationship`、`phoneNumber`、`uri`）禁止出现在 identity、正文、`Button.label` 或其他可见 Text。

## CTA 文案

- `Button.label` 来自动作语义 + 当前卡片已可见的对象；不要从事件 `args` / `params` 抽字段拼文案。
- 电话类动作：无可见联系人时写「拨打电话」或「联系」；有可见联系人 / 关系短称时写「打给{短称}」或「联系{短称}」。
- 禁止机械拼接「拨打{人称/姓名}」；中文读起来不顺的 label 必须改成自然动作短语。
- `capsule` label 建议 ≤6 字；读不顺时宁可用通用动作词。

## 按钮形态

| 语义 | `design` | 说明 |
| --- | --- | --- |
| 查看/打开/详情/入会/拨打/确认/提交/开始 | `capsule` | 文字行动；背景由子样式提供 |
| 纯图标行动 | `icon-round` | 必须有动作匹配的候选图标；否则改 `capsule` |

Button 的 `height` / `width` / `backgroundColor` / `borderRadius` / `padding` / `fontSize` / `fontWeight` / `maxLines` / `flexShrink` 等由 `design` 子样式提供；不要在 DSL 实例中重复写。

示例：

```genui
["join_btn","Button",{"label":"加入会议","design":"capsule","onClick":[{"call":"clickToApi","args":{"intentName":"EnterMeeting","params":{}}}]}]
```

图标圆钮示例（`label` 仅语义；可见为 `Image`）：

```genui
["call_btn","Button",{"label":"拨打电话","design":"icon-round","onClick":[{"call":"clickToApi","args":{"intentName":"CallPhone","params":{"phoneNumber":"","relationship":"哥哥"}}}]},["call_icon"]]
["call_icon","Image",{"src":"resources/base/media/icon_call.svg","width":16,"height":16,"flexShrink":0,"fillColor":"#E5000000"}]
```

## Checkbox

- `label` / `value` / `select`；动态选中态绑定 DataModel。
- 无 `CheckboxGroup` / `Radio` / `Toggle`。

## 关闭约定

- Button `label` 非空且表达动作；`capsule` 建议 ≤6 字；不要写 `minFontSize` 覆盖子样式定值。
- `icon-round`：`label` 必填但不绘制；视觉靠 16×16 `Image` 子节点。
- 热区：`2x2` ≤1 显式动作；`2x4` ≤2 清楚分离热区；勿为吸引点击硬加按钮。
- `2x4` 两个行动同区同行放置；主次清楚。按钮都应单行显示，不用换行承载长 label。
- 无事件 → 不造 action。

# Layout Atoms（桌面 Form 角色内部行级块）

先确定 Card Shell / roles，再按 active size pack 定整卡 composition。
本文件只描述 `identity` / `primary` / `support` / `action` 角色内部可复用的小块，禁止当作整卡拼装入口。

## 1. 总则

- 根/`Row`/`Column` 默认可按需要写 `width:"matchParent"`。
- 间距：`itemMargin` 取 `4`/`8`；同组内优先 4，异质角色间优先 8。
- 根面保持固定 shell；图像作为小图标或角色内部 `Image` 使用，不做文字叠图背景。
- 允许：primary/support 内信息托盘。

## 2. 可用块

### A. 主副文 Column

`Column [title, subtitle?]` + `itemMargin:2`/`4`；副文 `maxLines:1` + `ellipsis`；无副文不输出节点。

### B. 左锚点 + 内容 Row

`Row [anchor, content]` — 时间、小图标 + 文案。

- `anchor`：`flexShrink:0`
- `content`：`layoutWeight:1` + `flexShrink:1`

### C. KV Row

`Row [label, value]`；父 Row `width:"matchParent"`；label `layoutWeight:1` + `flexShrink:1`，value `flexShrink:0` + `textAlign:"end"`。

- label：`maxLines:1` + `textOverflow:"ellipsis"`。
- value：`maxLines:1` + `textOverflow:"ellipsis"`；靠右显示，不贴在 label 后面。

### D. 托盘容器

`Column` + 浅/`#19000000` 类 `backgroundColor` + `borderRadius` + 内边距；仅放在 primary/support 角色内。

### E. 短列表

List 只放在 primary/support 角色容器内；`children` 使用静态 ID + 下标 path。
行形态优先 `Row [primary_col, trailing?]`；项级勿通栏 `capsule`，卡级行动进 `action`。短列表不要 `layoutWeight:1` 制造中空。

### F. 勾选组

`Column [Checkbox…]` — 位于 primary/support；提交行动由 `action` 角色承接。

### G. Progress 信息块

Progress 不是自解释组件，必须和说明 Text 组成信息块。

- `ring-meter`：`Stack [Progress type:"ring", center_icon_or_text?]` + 旁侧 / 下方说明；中心只放图标或极短文本。
- `linear-bar row`：`Column/Row [label/value, Progress design:"linear-bar"]`；多个同类 bar 高度、圆角、宽度基准一致。
- `segmented status`：`Progress design:"segmented-bar"` + 当前阶段 Text；`value` 为当前阶段，`total` 为阶段数。
- `threshold status`：`Progress design:"threshold-bar"` + 阈值 / 已用 / 剩余或超限说明；必须有 `threshold`。
- 信息块的 children 应同时包含说明文本与 Progress 本体；定义出的 Progress 节点必须从 root 可达。

## 3. 使用边界（整卡级）

- 用 atoms 绕过 `identity` / `primary` 必选角色。
- 不新增本文未列出的组合母型。
- 把卡级 CTA 做成信息块顶栏右钮。
- 无 schema 数组时硬造 List。
- 裸 Progress（没有 label / value / status 说明）。

## 4. Audit

- 是否只使用本文列出的角色内部 atoms？
- 时间/图标锚点是否可收缩截断？
- 短内容是否避免空 `layoutWeight`？
- 托盘是否只用于 primary/support，而非整卡第二层壳？

# Style and Spacing（桌面小卡）

共享视觉底座。Card Shell 固定 `padding` 默认 **12**；整卡 composition 以 active size pack 为准。
本文件只补间距档位、字阶路由与定高分白。

primary/support 内可使用信息托盘；root 保持固定 shell 和清晰角色分区。

## 1. Style Priority

1. 用户明确样式（不破协议）
2. Card Shell / roles + active size pack
3. 当前套色 / 材质 / 字色 hex
4. 可选 `design` 快捷档（Text/Button/Progress/Divider）
5. 布局属性（`width`/`itemMargin`/`justifyContent`/`layoutWeight`/`linearGradient`…）

## 2. Visual Routing

| 信号 | 处理 |
| --- | --- |
| identity 图标 | `Image` **20×20** |
| 主指标/状态 | 先按 active size pack 做容量账本；低密度 primary 可用 `Display_S` / `display-s` + `700`，高密度 2x2 随内容块数降到 `title-s` / `subtitle-l` / `body-m` |
| 常规短说明 | identity + primary 短文 |
| 多字段一组 | primary/support 信息托盘、双列或同行组合 |
| 同质短行 | 角色内部 List/Column |
| 勾选 | primary/support Checkbox 组 |
| 卡级行动 | `action` 角色内 `capsule` / `icon-round` + `onClick` |
| 价格/风险 | `fontColor` warning hex |
| 正向 | `fontColor` confirm hex |

主方案只从 Visual Routing 和 active size pack 选择；不要新增未定义布局母型。

## 3. Component Rules

### Text

- identity：`subtitle-s` / `body-s`
- primary：`body-s` / `body-m` / `subtitle-l` / `title-s`；宽松单主视觉可升到 `display-s`
- support：`body-s`；副信息 `#99000000`
- 饱和/深色根面上优先 `#FFFFFFFF`
- `content` 禁止空字符串；空副标题、空单位、空 label/value 直接省略节点
- 窄列默认 `maxLines:1` + `textOverflow:"ellipsis"`
- 字段拆分，不拼进同一 `content`
- 显式 `fontWeight` 必须用数字；禁止 `"medium"` / `"regular"` / `"bold"` 等字符串
- `fontWeight:700` 只给主指标 / 关键时间；正文勿再叠加
- 2x2 的 Progress 百分比、阈值说明、已用/剩余说明先作为解释层参与容量账本；内容紧时用 `title-s` / `subtitle-l` / `body-m` 承载

### Button

- 点击用 `onClick`，不用 `action`
- 卡级 action 由 Card Shell、当前套色策略和 active size pack 共同约束。
- Button `design` 仅允许 `capsule` / `icon-round`
- Button 子样式定值由 `design` 展开；实例只写 `label` / `design` / `onClick` / `enabled` / `fontColor`，不写 `height` / `width` / `backgroundColor` / `borderRadius` / `padding` / `fontSize` / `fontWeight` / `maxLines` / `flexShrink`。
- `capsule` 背景固定来自子样式；行动强弱通过是否生成 action、位置和 label 表达，不通过改背景表达。
- `capsule` 若包含行内 `Image` 图标，图标 `fillColor` 必须与 Button `fontColor` 完全一致；未显式写 `fontColor` 时，图标使用同一默认文字色，不另配独立图标色。
- `icon-round` 必须有唯一可见 16×16 `Image` 子节点；`label` 仅语义，不绘制。
- `2x2` ≤1 显式动作；`2x4` ≤2 分离热区
- 无 `eventCandidates` → 不造 action

### Image / Progress / Divider / Checkbox

- Image：`src` ∈ `assetCandidates`；禁止网络 URL、base64 SVG、编造路径；多色插画不要写 `fillColor`
- Image：identity 图标 20×20，行内图标 14–16，按钮内图标 16×16；不要把候选图标全贴上
- Progress：仅在 `meter-dashboard` 或明确进度场景中使用；一卡最多一个；必须配 label / value / status Text，禁止裸 Progress
- Progress 形态：单一比例仪表用 `type:"ring"` + Stack 中心图标/短文本；可比较连续值用 `linear-bar`；有序阶段用 `segmented-bar`；阈值/超限用 `threshold-bar`
- Progress：`linear-bar` / `ring` 用 `value / total` 表示比例；`segmented-bar` 用 `value` 表示当前阶段、`total` 表示阶段数；`threshold-bar` 必须有 `threshold`
- Progress：禁止 `value` / `total` / `threshold` 同 path；禁止无数据时写死满条
- Divider：默认不加
- Checkbox：无 design；动态态绑 DataModel

## 4. Layout & Spacing

容器：

- root：`padding`/`itemMargin`/`clip`/固定宽高；`justifyContent` 用于定高分白
- Row/Column：`itemMargin`（`spaceBetween`/`spaceAround`/`spaceEvenly` 时 `itemMargin` 不生效）
- List：`space`（仅角色内部）
- Stack：小卡少用

硬规则：

- 12vp safe margin 零例外：文字、按钮、背板、图标、highlight、溢出内容都不能触碰或越过卡片边缘。
- 固定尺寸内的文字、图标、按钮、背板必须允许 shrink / 截断；必要时容器 `clip:true` 兜底，禁止互相压住。
- 按钮和内容背板不能重叠；同列堆叠时二者独立，保留 8vp 间距。
- `2x4` 右侧零散 label/value 必须进入背板、托盘或成组 Row；不要直接浮在根面上。
- 底部锚定 action 上方必须有真实内容；否则改居中、减少内容或取消显式 action。

滚动：桌面 Form 卡片不出现滚动条。1–2 条短项优先用 Column/Row 静态排布；如使用 List，也只作短静态集合，不写 `scrollBar`，不靠滚动承载内容。

合法档位：`2` / `4` / `8`（偶发 `12`）。卡内禁止 `6`、`16+`。

| 关系 | 推荐 | 写在 |
| --- | --- | --- |
| 同行主副文 | `2` | 内层 Column `itemMargin` |
| 2x2 常规 title 主标题↔副标题 | `2` | title_area Column `itemMargin` |
| 2x2 title↔右侧图标 | `4` 最小 | title_main_row / metric_title_row `itemMargin`；主标题 / 数字标题吃弹性空间，图标在同一行尾 |
| 2x2 数字 title 标题行↔数字行 | `2` | title_area Column `itemMargin` |
| 2x2 数字 title 数字↔单位 | `4` | metric_row `itemMargin` |
| 同源紧密块（icon+标题） | `4` | Row/Column `itemMargin` |
| 异质角色（identity↔primary、primary↔action） | `8` | root 或主容器 `itemMargin` |
| 2x2 title_area↔content_area↔action_area | `8` | root 或主 Column `itemMargin` |
| 列表项之间 | `4`（密）/ `8`（稀） | List `space` |

## 5. 定高剩余高度分配

- `2x2` 的 `content_area` 是区域分配例外：title 固定在顶部、action 固定在底部，中间剩余高度由 `content_area layoutWeight:1` 接住。
- `content_area` 吃剩余高度不等于内部节点也要拉伸；内部短文 / KV / Progress 仍按内容自然高度和 size pack 对齐策略排布。
- 只给「应当占满剩余且内部会排满」的角色容器 `layoutWeight:1`。
- 短列表保持 intrinsic 高度。
- 禁止短静态内容再设 `layoutWeight:1` 且默认贴顶 → 「上半坨 + 中段大空 + action 沉底」。
- 短内容可用 `justifyContent:"spaceBetween"` 或 `justifyContent:"center"`，不要靠加大 `itemMargin` 消除中空。

## 6. Audit

- root `padding` 是否为 **12**？roles 命名是否清晰？
- 是否使用 active size pack，而非旧三段模板？
- 卡级 action 是否 `capsule`/`icon-round`？是否误写 Button 子样式定值？
- 定高短内容是否「上沉 + 中空 + 底部 action」？
- 是否误用大面积第二层背景或 identity 右侧强塞 CTA？

# Harmony Desktop Form Style Core

本文件是桌面 Form 卡**样式与套色**的主权威。Card Shell / Role Contract 与 active layout pack 由入口上下文共同提供。

目标：固定画布上的高端精致 — 单焦点、场景洗色、材质对、定高分白。

## 1. North Star

- **One focus**：每卡一个主锚点；不做仪表盘。
- **Material honesty**：Button 背景由 `capsule` / `icon-round` 子样式提供；行动强弱通过是否生成 action、位置和 label 表达，不改 Button 背景定值。
- **Scene wash**：根面默认写 `linearGradient` 场景洗色；一卡一个主色家族。纯白实底不是默认。
- **Optical calm**：定高分白；角色间距 8；空副文不占位。
- **Compact first**：160×160 / 320×160；优先减 shouldKeep，不丢 mustKeep。

## 2. Color Lexicon

| 角色 | Hex | 用途 |
| --- | --- | --- |
| 主文字 | `#E5000000` | identity、主文 |
| 次文字 | `#99000000` | 标签、副文 |
| 弱文字 | `#66000000` | 更弱说明 |
| 反白字 | `#FFFFFFFF` | 深色根面 / 深色托盘上 |
| 品牌蓝 | `#FF0A59F7` | 主行动、品牌强调 |
| 品牌浅 | `#190A59F7` | 轻强调底 |
| 磨砂填充 | `#19000000` | 信息托盘 / 轻底 |
| 白描边 10% | `#19FFFFFF` | 可选 1px 描边 |
| 确认绿 | `#FF64BB5C` | 正向行动或成功状态 |
| 警告红 | `#FFE84026` | 风险(小面积) |
| 提醒橙 | `#FFED6F21` | alert / 行动感 |

禁止：与场景无关的随机「好看色」；一卡多个多彩色家族做主题；用 warning 整卡染色。

## 3. Palette Contract

| 角色 | DSL | 约束 |
| --- | --- | --- |
| `cardSurface` | root `linearGradient` 和/或 `backgroundColor` | 按 §4 选型；低对比洗色 |
| `contentSurface` | primary/support 子容器 `backgroundColor` ≈ `#0C000000` / `#19000000` | 仅信息托盘；不抢主文、不粘 action |
| `sceneAccent` | 同家族 `multi_color_*` / `multi_color_aux_*` 或对应 hex | Progress、icon `fillColor`、小面积强调 |
| `action` | Button `capsule`/`icon-round` | 见 §6 |
| `status` | 警告/提醒/确认/品牌色 | 只表状态 |

颜色来源：所有可落地颜色必须来自本文件 Color Lexicon、本文摘录的 HarmonyOS token / 官方多彩色表、或由这些颜色推导的同家族低强度渐变。禁止手写无来源的「好看色」。

渐变写法：

```json
"linearGradient": {
  "angle": 145,
  "colors": [["#FFFFFFFF", 0.0], ["#F0F5FF", 0.44], ["#FF8EB3FF", 1.0]]
}
```

## 4. Recommended Sets

默认姿态：先选有色调的套色并在 root 写 `linearGradient`；不要先写纯白再找理由。`backgroundColor:"#FFFFFFFF"` 仅可作回退，不能代替洗色。

| 套色 | 选择信号 | root 建议 | 行动 |
| --- | --- | --- | --- |
| **Brand Action** | 存在唯一高优先级主行动 | angle 145:`#FFFFFFFF→#FFF0F5FF→#FF8EB3FF` | 可生成明确 action |
| **Cool Context** | 语义偏冷静、清晰、客观 | angle 142:`#FFFFFFFF→#FFF4FBFF→#FF86C5E3` | 默认 tertiary |
| **Expressive Context** | 语义偏沉浸、个性或庆祝 | angle 145:`#FFFFFFFF→#FFF6EFFF→#FFC386F0` | 默认 tertiary |
| **Warm Active** | 语义偏活跃、临近或需要注意 | angle 135:`#FFFFFFFF→#FFFFF3E9→#FFED955F` | 可生成明确 action |
| **Warm Informational** | 语义偏温和、记录或提示 | angle 132:`#FFFFFFFF→#FFFFF9DF→#FFF9BC64` | 默认 tertiary |
| **Positive Status** | 语义明确为正向、健康或成功 | angle 145:`#FFFFFFFF→#FFF4FBEF→#FF92C48D` | 可生成明确 action |
| **Calm Status** | 资源/进度/系统状态等可量化状态 | angle 145:`#FFFFFFFF→#FFF0FBF8→#FF92D6CC` | 次级 tertiary |
| **Neutral Material** | 仅兜底：无明显色调/动作/状态信号 | 极轻灰渐变 `#FFFFFFFF→#FFE5E5EA` | 次级 tertiary |

不得从字段名或业务类别硬映射套色；也不得因为「怕选错」而一律 Neutral 纯白。

### Palette Signal → Multi Color Family

`paletteSignal` 只描述意图，不描述业务领域。选色时从同一行取一个主色家族，辅色用于渐变、Progress、图标或小面积强调。

| `paletteSignal` | 颜色家族 | 使用边界 |
| --- | --- | --- |
| `brand` | 品牌蓝 / `multi_color_08` | 仅品牌或强行动语境；不要整卡品牌蓝 |
| `cool` | `multi_color_02` + `multi_color_aux_02` | 冷静、清晰、客观信息；默认低对比洗色 |
| `calmStatus` | `multi_color_03` + `multi_color_aux_03` | 可量化状态、资源、进度；Progress 跟随同家族 |
| `positive` | `multi_color_04` + `multi_color_aux_04` | 成功、可用、完成；只在状态或小面积强调上使用 |
| `expressive` | `multi_color_06` + `multi_color_aux_06` | 沉浸、个性、夜间感；仍保持单家族 |
| `warmActive` | `multi_color_09` / `multi_color_10` + 对应 aux | 临近、行动、提醒；避免整卡警告化 |
| `warmInfo` | `multi_color_10` / `multi_color_11` + 对应 aux | 温和记录、轻提示；不使用饱和黄大面积压白字 |
| `neutral` | `font_*` / `comp_background_*` / 极轻灰渐变 | 只兜底；不能变成默认偷懒 |

### Time Of Day Modulation

`temporality` 只允许在已选主色家族内微调色温、明度或渐变方向，不允许跨家族加第二套主题色。

- functional / 信息型场景：只做 3–6% 明度或色温变化。
- `now` / `today` / `countdown`：可以略增强方向感或暖度，但主信息仍优先高对比。
- 夜间、沉浸、行动感：可比 functional 更明显，但仍是一张卡一个主色家族。
- `2x2` 不使用复杂渐变或多块彩色背板。

## 5. Color Pairing

- 白色、浅灰、低强度渐变底：主信息用 `font_primary`，标签/说明用 `font_secondary` / `font_tertiary`。
- 品牌蓝、确认绿等实色只用于小面积状态或强调；Button 背景保持子样式定值。
- 饱和 / 深色 root 上，前景优先使用 `#FFFFFFFF` 或低饱和反色；图标也保持单色。不要把 warning / alert / confirm / brand 强调色直接压在彩色根面上。
- 状态色是状态，不是主题；需要强调时放在中性托盘、浅背板、小图标或小面积文本里。
- 普通背景或中性背板上，才使用正常文本阶、品牌强调、warning / alert / confirm 状态色。
- 一卡一个主色家族；Progress / icon / 小面积强调必须跟随同一场景色系，避免多彩仪表盘。

## 6. Action Material

卡级 action 的位置由 active layout pack 决定。

| 语义 | `design` | 说明 |
| --- | --- | --- |
| 文字行动 | `capsule` | 背景由子样式提供；强弱靠位置、文案和是否出现 action 表达 |
| 纯图标行动 | `icon-round` | 必须有匹配候选作 `Image` 子节点；否则改 `capsule` |

- 查看、打开、详情、进入、切换等常规动作也用 `capsule`，不改背景。
- `icon-round` 可见内容只能是图标；要文字用 `capsule`。
- 热区：`2x2` ≤1；`2x4` ≤2。
- 无 `eventCandidates` → 不造 action。

## 7. Typography

| 层级 | 建议 | 字重 |
| --- | --- | --- |
| 2x2 常规 title 主标题 | `subtitle-s`(14) 或 `subtitle-l`(18) | 500 |
| 2x2 常规 title 副标题 / 辅助信息 | `caption-l`(12) | 400 |
| 2x2 数字 title 标签 | `body-s`(12) | 400 |
| 2x2 数字 title 数字 | `Display_S` / `display-s` | 700 |
| 2x2 数字 title 单位辅助信息 | `caption-l`(12) | 400 |
| primary/support 正文 | `body-s` / `body-m` | 400–500 |
| 按钮字 | `capsule` design 定值 14 | 500 |

正文不要再叠 `fontWeight:700`（英雄数字除外）。空副文省略节点。

2x2 数字 title 中，单位辅助信息与数字底部对齐；标签到数字行的距离可在 2/4/8 网格内微调，以整体重心和不裁切为准。

## 8. Gate

1. 160×160 / 320×160 装得下？identity/primary/action 角色清楚？单焦点？
2. root 是否写出 `linearGradient` 场景洗色？是否误用纯白实底？
3. 颜色是否能回溯到官方 token / 语义色 / 多彩色表？是否有无来源手写色？
4. 套色单家族、渐变低对比、前景可读？时间性变化是否仍在同家族内？
5. `2x2` 是否只保留一个主色信号 + 一个状态/动作信号？
6. Progress 是否只用场景主色或状态色，且同一卡最多一个主 Progress 信息块？
7. 卡级按钮是否 `capsule`/`icon-round`？是否误改 Button 背景定值？
8. mustKeep 在；`2x2` 已丢 should/drop？
9. 绑定 / asset / event 白名单？

# Visual Molecules（桌面 Form 角色分配 → 尺寸布局）

分子只回答「**信息形态 + 角色分配**」。物理布局由 active size pack 决定。

先裁 mustKeep / shouldKeep，再选分子；再把角色交给 size pack 落地。

## 1. Decision Table

| Molecule | Strong Signal | Role Allocation | Notes |
| --- | --- | --- | --- |
| `metric-status-summary` | 单主指标/状态 | `identity`=指标标签/对象；`primary`=主数值/状态或 Progress 信息块；`support`=Progress 说明/极少辅助；`action`=可选 | Progress 仅限 meter-dashboard / 明确进度；mustKeep 少时可用大号主数值；字段多时禁用大号主数值；禁止裸 Progress |
| `info-summary` | 短说明/状态文案 | `identity`=对象/用途；`primary`=说明正文；`support`=可选短副文 | 单段说明，避免多余托盘 |
| `entity-board` | 同一信息对象含多个相关 mustKeep 叶子 | `identity`=对象锚点；`primary`=主字段组；`support`=相关字段；`action`=可选 | 多字段优先托盘/双列/同行组合 |
| `actionable-rows` | 同质短行 + 可选卡级行动 | `identity`=列表域/用途；`primary`=短行集合；`action`=卡级行动 | 短列表只在角色内部；不要每行大按钮 |
| `media-entity` | 小图标 + 标题副文 | `identity`=图标+对象；`primary`=标题/状态；`support`=副文 | 只允许小图标或小图，不作整卡主视觉 |
| `form-selection` | Checkbox + 确认 | `identity`=选择任务；`primary`=选项组；`action`=确认 | 提交用 capsule |
| `threshold-status` | 安全阈值 + 超限状态 | `identity`=受限对象；`primary`=`threshold-bar` + 已用/剩余/超限说明；`support`=阈值标签；`action`=可选管控动作 | 必须有 `threshold`；不用普通 linear-bar 伪装超限 |

不要新增表外 molecule；无法稳定归类时，选择最接近的现有 molecule 并简化为 Text / Image / Progress 信息块。

## 2. Card Blueprint（内部）

| Field | Meaning |
| --- | --- |
| `purpose` | 来自 `userQuery` |
| `size` | `2x2` / `2x4` / `4x2` |
| `size_pack` | active 2x2 / 2x4 rules |
| `palette_set` | 当前套色策略 |
| `molecule` | 上表之一 |
| `roles.identity` | 卡片对象/用途锚点 |
| `roles.primary` | 主信息 |
| `roles.support` | 补充字段 |
| `roles.action` | 合法事件行动 |
| `reject_if` | `overflow_2x2`、`missing_identity`、`missing_primary`、`fake_asset`、`unsupported_structure` |

## 3. Size-Aware Notes

### `2x2`

按 active 2x2 rules 落 compact stack。字段多时先收紧字阶和行数，不要为了大号主数值漏 mustKeep。

### `2x4` / `4x2`

按 active 2x4 rules 落 horizontal composition。利用宽度做分组/并排/action rail；不要把 `2x2` 三段竖栈简单拉宽。

## 4. Slot Audit

- 是否已经选择唯一 active size pack？
- `identity` / `primary` 是否都可见？
- 共同构成完整语义的 mustKeep 叶子是否全部有可见节点、绑定和 `data` 行？
- molecule 的角色分配是否按当前 size pack 落地？
- 是否新增了表外 molecule 或未定义结构？
- 空副文是否仍输出节点？
- 图标/事件是否越权白名单？

# 2x2 Pack（160×160 标题/内容/按钮竖栈）

本 pack 仅在 taskspec `size:"2x2"` 时生效。共同 shell、角色合同和小构件规则由入口已加载上下文提供。

## 1. Composition

`2x2` 使用固定竖向三区：

```text
root Column itemMargin:8 [
  title_area flexShrink:0,
  content_area layoutWeight:1,
  action_area? flexShrink:0
]
```

要求：

- `title_area` 必选，对应 role `identity`。
- `content_area` 必选，对应 role `primary` + 必要 `support`。
- `action_area` 可选，仅当有合法 `eventCandidates`，对应 role `action`。
- `title_area` 固定在顶部；`action_area` 固定在底部；除标题区和按钮区外，中间剩余高度全部归 `content_area`。
- `content_area` 是 2x2 唯一默认吃剩余高度的区域，写 `layoutWeight:1`；其内部短内容不要再滥用 `layoutWeight:1` 制造空白。
- 三个区域之间的垂直间距固定 **8vp**；写在 root 或主 Column 的 `itemMargin:8`。
- root 仍为 `width:160,height:160,borderRadius:20,padding:12,clip:true`。

## 2. Title Area

`title_area` 由「title + 可选图标」组成；如有图标，图标放在主标题行 / 数字标题行的最右侧，不和整组 title_col 垂直居中。

### 2.1 Icon

- 图标可选；有与 `assetCandidates[].description` 匹配的已展示字段时优先使用。
- 图标大小统一 **20×20vp**。
- 图标可使用：
  - SVG 鸿蒙规范图标（`resources/...` 路径）
  - 应用图标
- 使用 SVG 鸿蒙规范图标时，图标色使用 `icon_on_tertiary`，即 `#66FFFFFF`。在 DSL 中可通过 `fillColor:"#66FFFFFF"` 落地。
- 应用图标 / 多色图标保持原样，不写 `fillColor`。
- 图标与同一行 title 的水平间距最小 **4vp**；主标题 / 数字标题占左侧弹性空间，图标贴该行右边界。
- Title row anatomy：左侧是可伸缩 text track，右侧是可选 accessory icon。DSL 的 children 顺序按视觉从左到右写，因此 title 文本 track 在前，accessory icon 在后。

### 2.2 常规 Title

用于普通对象标题、下一项、状态摘要等。

结构：

```text
title_area Column [
  title_main_row Row [
    title_main layoutWeight:1,
    icon?
  ],
  title_sub?
]
```

字阶：

| 元素 | 字体 |
| --- | --- |
| 主标题 | `Subtitle_S` + `500`，或信息密度允许时 `Subtitle_L` + `500` |
| 副标题 / 辅助信息 | `Caption_L` + `400`，可选 |

布局：

- `title_main_row` 承载主标题和可选图标，写 `width:"matchParent"` + `alignItems:"center"` + `itemMargin:4`。
- `title_main_row` 的视觉解剖为 `[title_main text track, accessory icon?]`；副标题在下一行，不参与图标对齐。
- 主标题和副标题之间的垂直间距固定 **2vp**；有副标题时写在 `title_area` Column 的 `itemMargin:2`。
- 只有一行主标题时，不输出空副标题节点。
- `title_main` 应 `layoutWeight:1` + `flexShrink:1`，文本可 `maxLines:1` + `textOverflow:"ellipsis"`。
- 右侧图标 `flexShrink:0`；图标只是 identity 装饰，不是 title_area 右侧行动按钮。

### 2.3 Numeric Title（数字呈现 title）

用于主视觉是数字 / 倒计时 / 进度剩余等场景。

结构：

```text
title_area Column [
  metric_title_row Row [
    metric_label layoutWeight:1,
    icon?
  ],
  metric_row Row [
    metric_value,
    metric_unit
  ]
]
```

字阶：

| 元素 | 字体 |
| --- | --- |
| 标题 / 标签 | `Body_S` + `400` |
| 数字 | `Display_S` + `700` |
| 单位辅助信息 | `Caption_L` + `400` |

布局：

- `metric_title_row` 承载数字 title 的标题 / 标签和可选图标，写 `width:"matchParent"` + `alignItems:"center"` + `itemMargin:4`。
- `metric_title_row` 的视觉解剖为 `[metric_label text track, accessory icon?]`；数字行仍只放数字与单位。
- 标签在上，位置相对稳定。
- 数字在标签下方靠左。
- 单位辅助信息在数字右侧，与数字底部对齐。
- 标题行到数字行的垂直距离固定 **2vp**；写在承载 `metric_title_row` 与 `metric_row` 的 `title_area` Column `itemMargin:2`。
- 数字和单位之间使用 **4vp** 左右间距。

## 3. Height Budget

可用内容高 ≈ `160 - 24`(上下 padding) = **136**。

| 先扣项 | 约高 |
| --- | --- |
| `capsule` action | **36** |
| title/content/action 区间距 | 每段 **8** |
| 常规 title | **20–36** |
| 数字 title | **50–64** |

有 action 时，title + content 需要在约 **84–92** 高内完成。数字呈现 title 占高更大，content 必须更克制。

## 4. Content Area（待补占位）

`content_area` 的正式布局规则暂不展开；这里只定义过渡期边界。

- `content_area` 必选，对应 role `primary` + 必要 `support`。
- `content_area` 仍写 `layoutWeight:1`，接住 title_area 与 action_area 之间的剩余高度。
- `content_area` 内部只使用已定义的角色内部 atoms：主副文 Column、左锚点 + 内容 Row、KV Row、托盘容器、短列表、勾选组、Progress 信息块。
- 内部节点按自然高度排布；短内容不要再写 `layoutWeight:1` 制造空白。
- `content_area` 内部 `itemMargin` 只用 `2` / `4` / `8`；不要写 `6` 这类非网格值。
- KV Row 必须让 label 吃弹性空间、value 靠右：label `layoutWeight:1` + `flexShrink:1`，value `flexShrink:0` + `textAlign:"end"`。
- 生成 content 前先做容量账本：用 root 内高 136 扣掉 title、action 和 8vp 区间距，得到 content_area 可用高；每个候选信息块按自然高度估算后再落 DSL。
- 2x2 Capacity Worksheet：
  - `innerH = 160 - padding*2 = 136`
  - `contentBudget = innerH - titleH - actionH - rootGaps`
  - 常规 title 单行约 20；常规 title 双行约 34；`capsule` action 约 36；三区竖栈有 action 时 rootGaps 通常为 16。
  - 常见内容块估高：单行 KV 16–20；带图标 KV 16–20；紧凑 Progress 信息块 20–28；`title-s` 数值行约 24；`display-s` 数值行约 40+。
  - `sum(blockH) + internalGaps` 应小于等于 `contentBudget`。若预算只剩约 50–60，选择「一个 Progress 信息块 + 一个紧凑 support 行」或「两行 KV」，而不是三段 Column 堆叠。
- 字阶由容量账本决定：宽松内容可用大号主数值；均衡内容用 `title-s` / `subtitle-l` / `body-m`；紧凑内容用 `body-s` / `caption-l` 和同行 KV。
- Progress 本身已经表达比例时，百分比 / 阈值 / 已用剩余文本是解释层，优先跟 Progress 组成紧凑信息块，而不是再升级成独立大号主视觉。
- 若候选内容超出 content 高度，按顺序调整：减少嵌套层级、把 label/value 同行化、降低字阶、合并 support 文案、将 shouldKeep 压成最短表达；mustKeep 保持可见。
- 过渡期不要新增 content_area 专属母型；后续由正式内容区规范替换。

## 5. Action Area

`action_area` 位于 2x2 卡片底部，只承接 role `action`。

| Button design | action_area 规则 |
| --- | --- |
| `capsule` | 按钮视觉占整行；`action_area` 写 `width:"matchParent"`，Button 实例不写 `width` / `height` |
| `icon-round` | 圆钮尺寸由子样式提供；action_area 用 Row / 容器右对齐（`justifyContent:"end"`），按钮靠右 |

规则：

- `capsule` 不做短按钮、不居中浮动。
- `capsule` 的宽高由子样式和父级 `action_area` 共同决定，不在 Button 实例中重写。
- `icon-round` 不占整行，不居中；靠右但仍在底部 action_area 内。
- 不把 action 放进 `title_area` 右侧；title 右侧图标只是 identity 装饰。

## 6. Role Placement

| Role | 2x2 落点 |
| --- | --- |
| `identity` | `title_area`；可为常规 title 或数字 title |
| `primary` | `content_area`；按过渡期 atoms 承载 |
| `support` | `content_area` 内只保留必要字段；优先 1–2 行内解决 |
| `action` | `action_area`；底部 `capsule` 或 `icon-round`；显式热区 ≤1 |

## 7. Temporary Atom Choices

- 短说明：主副文 Column。
- 小图标 / 时间锚点：左锚点 + 内容 Row。
- 标签和值：KV Row；值列靠右。
- 多个相关字段：一个托盘容器内放 1–2 行。
- 同质短行：短列表最多 1–2 项。
- 选择任务：少量 Checkbox 组；提交行动仍归 action_area。
- 进度：一个 Progress 信息块，必须带说明文本。

## 8. Fit Gate

生成前按顺序过一遍：

- title_area / content_area 都已落位，content_area 接住 title_area 与 action_area 之间的剩余高度。
- title / content / action 的区间距是 8vp；没有用额外大间距制造中空。
- title 行符合 anatomy：text track 在左侧吃弹性空间，accessory icon 在右侧贴边。
- content_area 的实际块数、字阶、间距与容量账本匹配；不会依赖 `clip:true` 裁掉内容。
- `capsule` action 占底部行动行；`icon-round` action 靠右。
- mustKeep 都有可见表达；shouldKeep 在空间不足时使用最短表达。
- content_area 只使用当前过渡期 atoms。

## 9. Audit

- root 是否 `160×160`、`borderRadius:20`、`padding:12`？
- title_area / content_area 是否必选存在？action_area 是否仅合法事件才出现？
- title 是否在最上、action 是否在最下、content_area 是否占满中间剩余高度？
- title/content/action 之间是否固定 8vp？
- content_area 是否只使用过渡期 atoms，没有新增专属母型？
- `capsule` action 是否整行宽？`icon-round` action 是否靠右？
- 常规 title 是否按主标题 + 可选副标题，行距 2vp？
- 有 title 图标时，title 行是否符合 text track + accessory icon anatomy？
- 数字 title 是否按标签 / 数字 / 单位，且单位与数字底部对齐？
- content_area 是否先完成容量账本，再选择字阶、块数和紧凑布局？
- SVG 鸿蒙规范图标是否 20×20 且使用 `icon_on_tertiary` / `#66FFFFFF`？
- 有 action 时是否 ≤1 热区且不裁切？
- mustKeep 是否保留；字段多时是否禁用 `Display_S`？

# 2x4 Pack（320×160 横卡占位）

本 pack 仅在 taskspec `size:"2x4"` 或 `"4x2"` 时生效。正式 2x4 布局规则待补；当前只提供过渡期边界。

## 1. Fixed Shell

- root 写死 `width:320,height:160,borderRadius:20,padding:12,clip:true`。
- `2x4` / `4x2` 与 `2x2` 同高 **160**；宽度变大只提供横向组织空间，不提供额外纵向容量。
- 不复用 2x2 的 title/content/action 三段竖栈作为唯一结构。

## 2. Placeholder Composition

当前只允许浅层 composition：

```text
root Column or Row [
  identity / primary / support group,
  action group?
]
```

边界：

- 必须保留 `identity` + `primary` 的可见表达。
- `support` 可比 2x2 多保留少量字段，但仍应紧凑分组。
- `action` 仅当有合法事件时出现；显式热区 ≤2。
- `2x4` 必须主动利用横向空间；不要把内容缩在左侧窄列后留下大片空白。
- 有 action 时，优先用外层 Row 或 body Row 做横向组织：主信息组 `layoutWeight:1` + `flexShrink:1`，行动组 `flexShrink:0`。
- 若 root 使用 Column，主体区必须有一个 `width:"matchParent"` 的 body Row / content group 来吃满宽度；底部通栏 action 只在信息确实横向排满时使用。
- 多条短行优先用 Column 静态 rows；不要用带剩余高度的 List 做滚动区域。
- 不新增 2x4 专属母型；后续由正式 2x4 规范替换。

## 3. Temporary Atom Choices

过渡期只使用角色内部 atoms：

- 主副文 Column。
- 左锚点 + 内容 Row。
- KV Row。
- 托盘容器。
- 短列表。
- 勾选组。
- Progress 信息块。

## 4. Action Placeholder

- 单行动可放在独立 action group；具体位置暂不固定。
- 双行动仅当 `eventCandidates` 提供两个清晰合法动作。
- 一卡最多一个主行动语义；不通过改 Button 背景表达主次。
- action 不得挤掉 mustKeep 信息。

## 5. Height Budget Gate

- 可用内容高仍只有 `160 - 24 = 136`；宽度增加不增加垂直容量。
- 若同时有 identity、主体内容和底部 action，生成前必须估算高度；装不下时优先把 action 放入横向 action group，或压缩 content。
- 不要同时堆叠大号主数值、带 padding 的 support 托盘、两枚底部按钮和多行说明；这类组合必须降级其中一项。
- 使用 `display-s` 时，support 只能是极短行 / 小型 Progress 信息块；不要再加多行托盘。
- 使用带 padding 的 support 托盘时，主数值和 action 都要保持克制，不能依赖 `clip:true` 裁掉溢出。

## 6. Audit

- root 是否为 `320×160`、`borderRadius:20`、`padding:12`？
- 是否承认 2x4 仍是 160 高固定卡，而不是纵向高容量卡？
- 是否只使用浅层 composition 和过渡期 atoms？
- 是否吃满 320 宽的横向空间，而不是左侧窄列 + 右侧空白？
- 是否通过高度预算避免遮挡、裁切和换行？
- `identity / primary / support / action` 是否各自有清晰角色？
- action 是否没有挤掉 mustKeep？
