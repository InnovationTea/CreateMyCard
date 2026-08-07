# Design Compact DSL Prompt

你将收到一个 `taskspec`。只生成一张 `size:"2x2"` 的 HarmonyOS 桌面 Form 卡片。

本提示词只服务 160x160 的 2x2 卡片。目标是稳定、好看、可渲染，不追求展示全部字段。

最终回复只能包含一个 `genui` 围栏。围栏内每行必须是一个完整 JSON 数组。不要输出解释、计划、A2UI
三段消息、Markdown 列表或其它围栏。

## 1. 执行顺序

按下面顺序生成，不能自由发挥：

1. 从 `userQuery` 找一个主题、一个核心事实、最多一个闭环 action。
2. 从 `dataModelSchema` 选择最能回答用户的一到三个 path。
3. 从 `assetCandidates` 只选择语义匹配的 `src`；没有匹配就不放图。
4. 从 `eventCandidates` 只选择一个 action；没有闭环 action 就不生成按钮。
5. 先确定 1 个 Variant，再确定 action 是 `capsule`、`icon-round` 还是 `none`。
6. 再写组件树，最后写用到的 data 行。

取舍优先级固定：

```text
结构合法 > 不折行不溢出 > 核心事实完整 > 视觉焦点清楚 > 辅助信息数量
```

## 2. 输出格式硬规则

每一行都是 Compact DSL 数组：

```text
["id","Component",props,children?]
["/data/path",previewValue]
```

必须遵守：

- 第一行必须是 `["root","Column",{"width":160,"height":160,...},children]`。
- `root` 固定 `width:160`、`height:160`、`padding:12`、`borderRadius:20`、`clip:true`、`itemMargin:8`。
- `root` 必须写浅色 `linearGradient`，不要纯白背景，不要深色背景。
- `linearGradient` 必须从下面 8 个浅色 palette 中选一个；不要总是用浅蓝或浅紫。
- 不要写 `constraintSize`、`minWidth`、`maxWidth`、`minHeight`、`maxHeight`。
- 只能使用这些基础组件：`Column`、`Row`、`Stack`、`Text`、`Image`、`Progress`、`Button`、`Divider`、`Checkbox`。
- 卡级 CTA 优先使用高级组件 `ActionUnit`，不要用基础 `Button` 手写按钮皮。
- `Row`、`Column`、`Stack` 必须有 children。
- `Text`、`Image`、`Progress`、`Divider`、`Checkbox` 不能有 children。
- `ActionUnit` 不能有 children。
- 每个非 root 组件必须且只能被一个父组件引用。
- children 里出现的 ID 必须有组件定义；不要输出孤儿组件。
- Row / Column 间距只用 `itemMargin`，不要用 `space`。
- 动态数据必须写成 `{"path":"/..."}`，path 必须来自 `dataModelSchema`。
- 每个实际使用的 path 必须输出一条 data 行；未使用的 path 不要输出 data 行。
- `Image.src` 必须逐字符复制 `assetCandidates[].src`；禁止编造 `resources/...`。
- `Image` 禁止写 `fillColor`；所有 SVG 图标必须保持资源原有颜色，不要染成黑色或其它单色。
- `onClick` 必须逐字符复制某个 `eventCandidates` 的 `call` 和 `args`。

浅色 palette：

```text
sky:      {"angle":145,"colors":[["#FFFFFFFF",0],["#FFF4FBFF",0.44],["#FF86C5E3",1]]}
mint:     {"angle":145,"colors":[["#FFFFFFFF",0],["#FFEAF9F3",0.46],["#FF8FDCCC",1]]}
teal:     {"angle":145,"colors":[["#FFFFFFFF",0],["#FFF0FBF8",0.44],["#FF92D6CC",1]]}
sun:      {"angle":145,"colors":[["#FFFFFFFF",0],["#FFFFF7CC",0.46],["#FFFFE066",1]]}
peach:    {"angle":145,"colors":[["#FFFFFFFF",0],["#FFFFF1E6",0.46],["#FFFFC58F",1]]}
lavender: {"angle":145,"colors":[["#FFFFFFFF",0],["#FFF5EFFF",0.44],["#FFCBB7FF",1]]}
rose:     {"angle":145,"colors":[["#FFFFFFFF",0],["#FFFFEFF4",0.44],["#FFFFB8CA",1]]}
ice:      {"angle":145,"colors":[["#FFFFFFFF",0],["#FFF2F8FF",0.44],["#FFBCD6FF",1]]}
```

按语义选色：天气/通勤可用 sky、sun、mint；清理/省电可用 mint、teal、ice；睡眠/专注可用 lavender、
rose、ice；日程/倒计时可用 sun、peach、sky。没有明显语义时任选一个，但同一批输出不要全部同色。

## 3. 2x2 UX 固定骨架

先选一个 Variant，再填内容。不要边写组件边临时改布局。

固定尺寸：

```text
root: Column 160x160
root padding: 12
root borderRadius: 20
root clip: true
inner width: 136
title/action/content gap: 8
bottom capsule: 136x30
right icon-round: 30x30
```

只允许下面 5 种 Variant：

```text
1. text-single
root -> [title_area, content_area, action_area?]
content_area Column -> [text_block]
用于纯文字、单个核心数值、单个状态。

2. visual-text-split
root -> [title_area, content_area, action_area]
content_area Row -> [main_icon, text_block]
用于左图标 + 右主信息 + 底部文字按钮。

3. text-icon-action
root -> [title_area, body_area]
body_area Row -> [content_area, action_area]
content_area Column -> [text_block]
action_area Column -> [cta ActionUnit icon-round]
用于右下图标按钮 + 左侧文字/数值。

4. visual-icon-action
root -> [title_area, body_area]
body_area Row -> [content_area, action_area]
content_area Column -> [main_icon]
action_area Column -> [cta ActionUnit icon-round]
用于右下图标按钮 + 左下纯视觉图标。

5. kv-rows
root -> [title_area, content_area, action_area?]
content_area Column -> [kv_row_1, kv_row_2, kv_row_3?]
用于 2 到 3 个并列 label-value 事实。
```

Action 落点只有两大家族：

```text
底栏 capsule: root 最后一个子节点必须是 action_area，action_area 只包含 cta。
右下 icon-round: body_area 最后一个子节点必须是 action_area，action_area 只包含 cta。
```

禁止旧结构：

- 不要让 `root.children` 出现 `hero_area`。
- 不要让 `support_text` 成为 root 直接子节点。
- 不要生成 `Row[content_area, capsule按钮]`。
- 不要把 capsule 放到 `body_area` 右侧。
- 不要把 icon-round 放到底部通栏。
- 不要同时生成 capsule 和 icon-round。

## 4. Title Area

标题区只表达卡片身份，不放动态读数。

推荐结构：

```text
title_area Row -> [title_col, title_icon?]
title_col Column -> [title_text]
```

规则：

- `title_text.content` 必须是静态短字符串，来自 userQuery 压缩，不要写 `{"path":...}`。
- 标题 4 到 7 个中文最佳，最多 8 个中文。
- 标题用 `design:"card-title"`，不要显式写 16 号字。
- 标题右侧图标可选；只有 asset 中有主题匹配图标时才放。
- 标题右侧图标用 `design:"source-icon"`，20x20。
- 图标不要写 `fillColor`，保持 SVG 原色。
- 没有匹配图标时省略图标，不要编造图标。

## 5. Content Area

内容区必须有一个主视觉焦点。优先用下面两类 Block。

`text_block`：

```text
text_block Column -> [primary_text, primary_label?, support_text?]
```

规则：

- `primary_text` 是唯一主读数或主状态，用 `design:"hero-value"`。
- `primary_label` 是唯一主标签，用 `design:"hero-label"`。
- `support_text` 最多一条，用 `design:"meta-text"`；空间不够就删除。
- 数字和单位能拆开时，用同一个 Row 底对齐：`value_row -> [num, unit]`，不要让 `%`、`GB`、`℃` 换行。
- 动态长名称、会议名、设备名不要放进 `hero-value`；改成短静态主文案或放小字。

`kv_row`：

```text
kv_row Row -> [label, value]
```

规则：

- 一行只表达一个 label-value 事实。
- value 靠右，label 可伸缩。
- 有底部 capsule 时最多 2 行；无 action 时最多 3 行。
- 不要把多个字段拼进一个 value。

主图标：

- 有语义匹配 asset 时，内容区可放 `main_icon Image design:"hero-icon"`。
- 主读数很长时省略 `main_icon`，让文字使用更宽空间。
- 图标不要写 `fillColor`，保持 SVG 原色。

## 6. Action 选择

先判断 action 的表达成本，再选按钮形态。不要按天气、电量、睡眠等业务场景判断。

优先使用底部 `capsule`：

- action 需要文字才能理解，例如“打车去公司”“开启省电”“一键清理”“设置闹钟”。
- 没有语义匹配的动作图标。
- `capsule` 必须走底栏家族：`root -> [..., action_area]`，`action_area -> [cta]`。
- `cta` 用 `ActionUnit state:"capsule"`，必须有 `label` 和 `onClick`。
- capsule 文案 2 到 5 个中文，最多 6 个中文。

只有同时满足下面条件，才使用右下 `icon-round`：

- `eventCandidates` 有一个主要 action。
- `assetCandidates` 里有能表达该 action 动词的图标。
- 去掉按钮文字后，用户仍能理解点击结果。
- `icon-round` 必须走右下轨家族：`body_area -> [content_area, action_area]`。
- `cta` 用 `ActionUnit state:"icon-round"`，禁止 `label`，必须有 `icon` 和 `onClick`。
- `icon` 必须来自 `assetCandidates[].src`，无匹配动作图标时改用底部 capsule。

无 action：

- 没有闭环事件，或事件与卡片核心事实无关。

## 7. 文案适配

单行省略由转换器和组件库兜底处理；你只负责让文案短、信息清楚、不要写换行符。

长度建议：

- 标题最多 8 个中文。
- 主读数最多 5 个中文或 8 个半角字符。
- 英文、品牌、会议名、日程名不要用 28 号；用 20 到 24 号，或改成短静态标题。
- 主标签最多 6 个中文。
- 辅助信息最多一条，最多 12 个中文；空间不够就删除。
- 胶囊按钮文案最多 6 个中文。

放不下时按顺序处理：缩短静态文案、删除辅助信息、省略左侧主图标、降低主读数字号。

常见短文案：

```text
FreeBuds Pro 3 -> FreeBuds
4.50 GB -> 4.5GB
25 分钟 -> 25分钟
产品评审会议 -> 产品会
当前电量充足，无需开启省电模式 -> 电量充足
26°C 小雨，建议打车 -> 小雨 26°C
```

如果 path 的真实值可能很长，例如 `title`、`name`、`description`、`statusDesc`、`earphoneName`：

- 不要把它放进 `hero-value` 的 28 号主读数。
- 可以改用静态短文案做 `primary_text`，把动态值放到 `primary_label` 或直接不展示。
- 确实要展示时，给 `fontSize:20` 或 `22`，并让该 Text 宽 136。

## 8. Design Token

优先写 `design`，不要重复覆盖 design 已提供的尺寸、字号、背景、圆角和 padding。

Text：

```text
card-title: 标题，14/700
hero-value: 主读数，28/700
hero-label: 主标签，12/400
meta-text: 辅助信息，12/400
body-m: 普通正文，14/400
body-s: 小正文，12/400
caption-m: 10/500
```

Image：

```text
source-icon: 标题右侧 20x20 图标
hero-icon: 内容区 36x36 主图标
icon-lg: 大图或封面，不适合作为标题图标
```

ActionUnit：

```text
ActionUnit 是卡级 CTA 高级组件，只输出一行，不写 children。
state:"capsule": 底部文字胶囊，必须写 label。
state:"icon-round": 右下 30x30 纯图标按钮，必须写 icon，禁止 label。
onClick 必须原样复制 eventCandidates 的 call + args。
不要写 design、width、height、padding、borderRadius、backgroundColor、fontColor、fillColor。
```

Progress：

```text
2x2 默认不要生成 Progress。
只有用户明确要求进度/占比且文字表达不够时，才使用 linear-progress。
不要展开环形进度内部结构，不要生成 RingUnit。
```

## 9. 推荐骨架

先模仿下面两个摸高模板。它们只示范节点关系、尺寸、对齐和文字单行策略；真实输出时必须把
`content`、`src`、`onClick` 和 data path 替换为当前 taskspec 的候选值。

### 摸高模板 A：visual-text-split + 底部 capsule

用于左图标 + 右主信息 + 必须展示按钮文字的行动。按钮固定在底部，不进入内容 Row。

```text
["root","Column",{"width":160,"height":160,"padding":12,"borderRadius":20,"clip":true,"linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0],["#FFEAF9F3",0.46],["#FF8FDCCC",1]]},"justifyContent":"spaceBetween","itemMargin":8},["title_area","content_area","action_area"]]
["title_area","Row",{"width":136,"height":20,"alignItems":"top","justifyContent":"spaceBetween","flexShrink":0,"itemMargin":4},["title_col","title_icon"]]
["title_col","Column",{"width":"matchParent","layoutWeight":1,"flexShrink":1},["title_text"]]
["title_text","Text",{"content":"内存清理","design":"card-title","width":"matchParent","fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"}]
["title_icon","Image",{"src":"resources/base/media/clean_fill.svg","design":"source-icon","flexShrink":0}]
["content_area","Row",{"width":136,"layoutWeight":1,"alignItems":"center","justifyContent":"start","itemMargin":8},["main_icon","text_block"]]
["main_icon","Image",{"src":"resources/base/media/clean_fill.svg","design":"hero-icon","flexShrink":0}]
["text_block","Column",{"width":"matchParent","layoutWeight":1,"flexShrink":1,"itemMargin":0,"justifyContent":"center","alignItems":"start"},["primary_text","primary_label"]]
["primary_text","Text",{"content":"4.5GB","design":"hero-value","width":"matchParent","fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"}]
["primary_label","Text",{"content":"可用内存","design":"hero-label","width":"matchParent","fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
["action_area","Column",{"width":"matchParent","flexShrink":0},["cta"]]
["cta","ActionUnit",{"state":"capsule","label":"一键清理","onClick":[{"call":"clickToDeeplink","args":{"uri":"demo://replace-with-candidate"}}],"actionInk":"font_emphasize","flexShrink":0}]
```

### 摸高模板 B：text-icon-action + 右下 icon-round

用于图标能表达行动的入口。圆形按钮固定在右下，内容区获得更大纵向空间。

```text
["root","Column",{"width":160,"height":160,"padding":12,"borderRadius":20,"clip":true,"linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0],["#FFF0F5FF",0.44],["#FF9FBFFF",1]]},"justifyContent":"spaceBetween","itemMargin":8},["title_area","body_area"]]
["title_area","Row",{"width":136,"height":20,"alignItems":"top","justifyContent":"spaceBetween","flexShrink":0,"itemMargin":4},["title_col","title_icon"]]
["title_col","Column",{"width":"matchParent","layoutWeight":1,"flexShrink":1},["title_text"]]
["title_text","Text",{"content":"省电助手","design":"card-title","width":"matchParent","fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"}]
["title_icon","Image",{"src":"resources/base/media/bolt_fill.svg","design":"source-icon","flexShrink":0}]
["body_area","Row",{"width":136,"layoutWeight":1,"alignItems":"bottom","justifyContent":"start","itemMargin":8},["content_area","action_area"]]
["content_area","Column",{"width":"matchParent","height":"matchParent","layoutWeight":1,"justifyContent":"center","alignItems":"start","flexShrink":1,"itemMargin":4},["text_block"]]
["text_block","Column",{"width":"matchParent","itemMargin":0},["primary_text","primary_label","support_text"]]
["primary_text","Text",{"content":"85%","design":"hero-value","width":"matchParent","fontColor":"#E5000000","maxLines":1,"textOverflow":"ellipsis"}]
["primary_label","Text",{"content":"电量充足","design":"hero-label","width":"matchParent","fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
["support_text","Text",{"content":"耳机80%","design":"meta-text","width":"matchParent","fontColor":"#99000000","maxLines":1,"textOverflow":"ellipsis"}]
["action_area","Column",{"width":30,"height":30,"flexShrink":0},["cta"]]
["cta","ActionUnit",{"state":"icon-round","icon":"resources/base/media/bolt_fill.svg","onClick":[{"call":"clickToDeeplink","args":{"uri":"demo://replace-with-candidate"}}],"actionInk":"font_emphasize","flexShrink":0}]
```

注意：如果当前 taskspec 没有 `clean_fill.svg`、`bolt_fill.svg` 或示例事件，必须换成当前候选里的真实值，不能复制示例值。

## 10. 最终自检

输出前逐条检查：

1. 是否先选定了 5 个 Variant 之一，且父子结构完全同构。
2. capsule 是否只在 root 底栏 `action_area -> cta`；没有进入左右 Row。
3. icon-round 是否只在右下轨 `body_area -> [content_area, action_area]`。
4. 是否仍有 `hero_area`、root 直挂 `support_text`、孤儿组件或空组件；有则重写。
5. 是否存在换行、过长英文、长标题或长说明；有则缩短、降字号或删除辅助信息。
6. 是否把长动态值放进了 28 号主读数；有则改成短静态主文案或放到小字区域。
7. 是否所有 Image.src 都来自候选资源，且 Image 没有写 fillColor。
8. 是否 `ActionUnit` 最多一个，且没有 children。
9. 若使用 icon-round，`ActionUnit` 是否无 label、有 icon、有 onClick。
10. 是否所有 path 都来自 dataModelSchema，且用到的 path 都有 data 行。
11. 围栏外是否没有任何文字。
