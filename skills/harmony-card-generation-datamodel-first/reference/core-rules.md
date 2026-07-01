# 核心规则

本文是默认必读的单页质量门。先看 P0 阻断项，再按 L0 协议、L1 数值布局、L2 内容视觉展开检查。

## 单文件兜底

- `manifest`：指选中模板目录内的 `manifest.json`；未使用模板时忽略所有 manifest 约束。
- `support.*` 是支撑组；`metric/tile/status/badge` 是模板声明的并列小事实槽位，不按支撑条数折算。
- `受保护文本`：标题、时间、日期、状态、CTA、主指标、倒计时、价格/数量和入选用户字段，必须完整显示。

## P0 先决阻断

以下任一组失败都不要输出：

- 输出契约：必须是两个代码块，`genui` 为三行 JSONL，`cardspec` 为 JSON；`version`、`catalogId`、CardSpec 尺寸、surface 尺寸和 root 尺寸/圆角一致。
- Surface/root：`createSurface` 只声明 surface、catalog 和尺寸，默认不写 `styles`；只有宿主明确要求外层形状/裁切时才写 `createSurface.styles`，且仅限 `borderRadius`、`clip`；`updateComponents.root` 引用已存在组件；root 承载 `width`、`height`、`padding`、`borderRadius`、`clip` 和至少一种明确的表面背景（优先 `backgroundColor` 或 `linearGradient`，也可由 root 下的真实背景组件承载），否则可能渲染默认白底。
- 消息闭环：三行 JSONL 的 `surfaceId` 必须一致；新卡片默认 `updateDataModel.path: "/"`，`value` 初始化所有 UI 表达式引用的根结构和加载态。
- 协议范围：只使用 Form 允许组件；`children` 只引用组件 id；模板循环只用 `{ "componentId": "...", "path": "..." }`；不用禁用组件、网络图、内联/base64 SVG、emoji、未声明 SVG 或未声明事件能力。
- 绑定/DataModel：动态展示值、样式动态值和事件参数只用完整 `{{ ... }}` 表达式；所有可见表达式引用都能在 `updateDataModel.value`、`writeResultTo + outputSchema` 或模板当前项中推导；数据能力运行时字段至少初始化到可推导根结构。`updateDataModel.path`、`writeResultTo`、模板 `children.path` 仍是协议结构 JSON Pointer。
- 布局可渲染：Row/Column 宽高预算成立且包含子项 `margin`；关键父容器和关键子项不依赖默认伸缩；Row 内 `Text + Button` 并排时，父 Row、Text、Button 都有明确宽高预算。

## L0 协议

- `genui` 必须是三行 JSONL：`createSurface`、`updateComponents`、`updateDataModel`。
- 使用 `version: "v0.9"` 和 `catalogId: "ohos.a2ui.extended.catalog"`。
- 尺寸只允许 `2x2` 或 `2x4`，且 CardSpec 与 DSL 一致：
  - `2x2`: `width: 140`、`height: 140`、root `borderRadius: 18`、`clip: true`。
  - `2x4`: `width: 300`、`height: 140`、root `borderRadius: 22`、`clip: true`。
- `updateComponents.root` 必须引用一个已存在组件；root 组件是卡片 shell 和组件树入口。
- root 组件必须写稳定 `width`、`height`、`padding`、`borderRadius`、`clip` 和表面样式；新卡片不要为了同步 root 圆角而写 `createSurface.styles`，它只在宿主明确要求外层形状/裁切时作为可选辅助；`backgroundColor`、`linearGradient`、`backgroundImage` 等背景字段必须写在 `root.styles` 或 root 下的真实背景组件，不写进 `createSurface.styles`，因为 root 默认不透明白底会遮挡 surface 层背景。
- 只使用 `Text`、`Image`、`Divider`、`Progress`、`Button`、`Checkbox`、`Row`、`Column`、`List`、`Stack`。
- 禁用 `TextInput`、`Toggle`、`Radio`、`CheckboxGroup`、`Select`、`NavContainer`、`Tabs`、`TabContent`、`Web`、`Grid`、`If`、`theme`、`Button.action`、非 `onClick` 事件、预定义扩展函数、`$__widthBreakpoint`、`$__colorMode`。
- `children` 只能是组件 ID 数组；模板循环只允许 `{ "componentId": "...", "path": "..." }`。
- 动态值只用完整 `{{ ... }}` 表达式；单值、拼接、条件、数值和列表项字段都走表达式。不要用 `{"path":"/..."}` 或 `formatString` 做组件值绑定；复杂格式化可先写入 `updateDataModel` 预计算字段，再用表达式读取。
- 点击只写 DSL `onClick`，且 `call` 必须来自已声明 event capability；CardSpec 不写点击行为。
- `Image.src` / `backgroundImage` 只使用用户提供或素材库声明的本地/资源路径；禁用网络 URL、内联/base64 SVG、emoji、占位图和未声明 SVG。

## L1 数值布局

- 默认安全区为 root `padding: 12`：`2x2` 内容区 `116 x 116`，`2x4` 内容区 `276 x 116`。
- 未指定尺寸时先尝试 `2x2`；只有受保护文本、热区、并列关系、关键媒体或布局预算具体失败时才升级 `2x4`。
- `2x2` 非模板默认最多 3 个主区域和 1 个显式动作；模板按选中 manifest 的 `lockedStructure.sections`、`slots` 和 `deleteRules` 执行，但不得新增未声明主区域或第二动作。`2x4` 最多 4 个主区域和 2 个动作区。
- 间距只用 `2/4/6/8/10/12/14/16`；优先 `4/8/12/16`。组间距必须大于组内距。
- 字号只用 `10/12/14/16/18/20/32/40`；`10fp` 只给弱提示，`40fp` 只给单一主数值，CTA 用 `14fp Medium`。
- 文本估算：中文约 `fontSize`，英文/数字约 `0.6 * fontSize`，垂直高度按 `fontSize + 2-4` 预留。
- 受保护文本必须完整显示：标题、时间、日期、状态、CTA、主指标、倒计时、价格/数量和入选用户字段。不要用 `ellipsis`、`clip`、`marquee` 解决。
- 每个 Row/Column 必须预算成立：子项宽高 + 子项 margin + 父容器 padding + itemMargin 不得超过父容器。
- Row/Column 不得依赖默认伸缩完成关键布局；父容器、按钮、图标、进度图形和受保护文本必须能推导出明确宽高。
- Row 内 `Text + Button` 并排时，父 Row 必须有明确 `width`/`height`，Button 必须显式 `width`/`height`，Text 必须显式 `width` 或有明确剩余宽度。
- 并排布局自检公式：`sum(子项 width + 子项左右 margin) + itemMargin * 间隔数 + 父容器左右 padding <= 父容器 width`；纵向同理检查 `height + 上下 margin + 上下 padding`。
- 可点击视觉元素不小于 `24vp`；CTA 宽度要包含文字估算和按钮内边距。
- 底部支撑/动作区必须贴近安全区底部：`2x2` 底边距通常 `8-12vp`、最大 `16vp`；`2x4` 通常 `10-14vp`、最大 `16vp`。
- 紧凑 Row 中 `Button` 与小号文本并排时，不要只依赖 `alignItems: "center"`；优先用按钮槽位、明确高度或非对称 padding 校正。若 Button 高度已等于父 Row 高度，不要再加 `margin.top/bottom`。
- Stack 只用于背景、进度或明确叠加；不得覆盖受保护文本、CTA 或主数值。

## L2 内容与视觉

- 先确定一个服务对象或主问题；非模板 `2x2` 默认展示不超过 4 个可见字段，模板按 manifest 的 `object`、`primary`、`support`、`metric/tile/status/badge`、`action`、`asset` 槽位取舍。`metric/tile/status/badge` 是结构化并列槽位，不按 `support.*` 条数折算；未入选字段留给详情页。
- 可见组件的信息职责必须互斥：对象、状态、设定值、实际值、差值、比例/进度、趋势、时间点/段、位置、金额、数量、动作入口等，每个事实只由一个组件主承载。
- 写前把文案和数值归入“事实等价类”：单位换算、别名/简称、同义标签、短标签扩写、父子包含、聚合/拆分、差值/比例/状态等，只要回答同一事实或判断，就算重复。
- 派生事实只有承担新判断时才展示；进度条只作可视化承载，旁边文案不要复述两端值，除非该值是唯一主事实。
- 信息不足时调整比例、层级和留白，不加空标签、同义指标或装饰填空。
- 颜色优先回溯到 HarmonyOS 语义 token、`ohos_id_color_*`、`multi_color_*` 或 `multi_color_aux_*`；场景拓展色必须说明场景锚点、来源色族、用途角色和克制边界。
- 渐变只用线性渐变，stop 来自官方色板或合规场景拓展色板；禁用无依据手调色、插值色、无来源 alpha、径向装饰、orb 或 bokeh。
- 同一卡片只用一个主场景色族；`confirm` / `warning` / `alert` 只服务真实状态。氛围渐变只在不挤压受保护文本和动作区时使用。

## 人工阻断补充

以下项通常需要输出前复核；任一失败都先收敛内容、删除弱信息或回退非模板流程，不交付：

- 模板生成照搬示例文案、示例 DataModel、示例素材组合，或读取 skill 包外历史样例；模板只能提供骨架、槽位、预算和协议写法。
- 用同义标签、单位换算、父子包含、派生比例/差值填充空间，导致多个组件重复回答同一事实。
- 没有单一服务对象或主问题，出现多个互相竞争的主显示组、多个主色族、多个主动作，或动作抢走主信息焦点。
- 动作能力不明却保留可点击视觉；应删除 `onClick` 并把动作区降级为非误导支撑信息。
- 颜色无法说明 token、已声明素材语义或合规场景拓展来源，或 DSL 直接输出 token/拓展色名而不是 hex。
- 状态色服务装饰而非真实状态；渐变 stop 含无场景依据的手调色、机械插值色或无来源 alpha。
- 连续无意义空白超过 `18vp`，且不服务主视觉、媒体、进度或底部动作锚定。
- 文本、按钮、背板虽然通过宽高估算，但视觉上贴顶、悬浮、基线不齐或靠近圆角裁剪风险区。
- 修复已有 DSL 时仍保留 `{"path":...}` 或 `formatString` 值绑定，或没有把它改写为完整表达式。

## 生成后校验

先做输出前自检，不要为了校验新建、输出或保留草稿文件。先查协议、绑定、布局、颜色、事件和尺寸，再查信息职责、事实等价类、派生判断和模板槽位删除后的引用完整性。仅在用户要求校验既有文件、修复本地草稿或调试脚本时运行 `scripts/validate_card.py`。
