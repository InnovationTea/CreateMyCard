# 核心规则

本文是默认必读的单页质量门。先看 P0 阻断项，再按 L0 协议、L1 数值布局、L2 内容视觉展开检查。

## P0 先决阻断

以下任一组失败都不要输出：

- 输出契约：必须是两个代码块，`genui` 为三行 JSONL，`cardspec` 为 JSON；`version`、`catalogId`、CardSpec 尺寸、surface 尺寸和 root 尺寸/圆角一致。
- Surface/root：`createSurface` 只声明 surface、catalog 和尺寸，`createSurface.styles` 若出现仅限 `borderRadius`、`clip` 等卡片级形状/裁切；`updateComponents.root` 引用已存在组件；root 承载 `width`、`height`、`padding`、`borderRadius`、`clip` 和至少一种明确的表面背景（优先 `backgroundColor` 或 `linearGradient`，也可由 root 下的真实背景组件承载），否则可能渲染默认白底。
- 协议范围：只使用 Form 允许组件；`children` 只引用组件 id；模板循环只用 `{ "componentId": "...", "path": "..." }`；不用禁用组件、网络图、SVG、emoji 或未声明事件能力。
- 绑定/DataModel：所有可见静态绑定路径和 `formatString` 路径都能在 `updateDataModel.value` 找到；数据能力运行时字段至少初始化到可推导根结构；模板相对路径除外。
- 布局可渲染：Row/Column 宽高预算成立且包含子项 `margin`；关键父容器和关键子项不依赖默认伸缩；Row 内 `Text + Button` 并排时，父 Row、Text、Button 都有明确宽高预算。

## L0 协议

- `genui` 必须是三行 JSONL：`createSurface`、`updateComponents`、`updateDataModel`。
- 使用 `version: "v0.9"` 和 `catalogId: "ohos.a2ui.extended.catalog"`。
- 尺寸只允许 `2x2` 或 `2x4`，且 CardSpec 与 DSL 一致：
  - `2x2`: `width: 140`、`height: 140`、root `borderRadius: 18`、`clip: true`。
  - `2x4`: `width: 300`、`height: 140`、root `borderRadius: 22`、`clip: true`。
- `updateComponents.root` 必须引用一个已存在组件；root 组件是卡片 shell 和组件树入口。
- root 组件必须写稳定 `width`、`height`、`padding`、`borderRadius`、`clip` 和表面样式；`createSurface.styles` 不替代 root shell，且只用于卡片级形状/裁切；`backgroundColor`、`linearGradient`、`backgroundImage` 等背景字段必须写在 `root.styles` 或 root 下的真实背景组件，不写进 `createSurface.styles`，因为 root 默认不透明白底会遮挡 surface 层背景。
- 只使用 `Text`、`Image`、`Divider`、`Progress`、`Button`、`Checkbox`、`Row`、`Column`、`List`、`Stack`。
- 禁用 `TextInput`、`Toggle`、`Radio`、`CheckboxGroup`、`Select`、`NavContainer`、`Tabs`、`TabContent`、`Web`、`Grid`、`If`、`theme`、`Button.action`、非 `onClick` 事件、预定义扩展函数、`$__widthBreakpoint`、`$__colorMode`。
- `children` 只能是组件 ID 数组；模板循环只允许 `{ "componentId": "...", "path": "..." }`。
- 动态值优先 `{"path":"/..."}`；字符串拼接用 `formatString`；表达式只做兜底。
- 点击只写 DSL `onClick`，且 `call` 必须来自已声明 event capability；CardSpec 不写点击行为。
- `Image.src` / `backgroundImage` 只使用用户提供或素材库声明的本地/资源路径；禁用网络 URL、SVG、emoji、占位图。

## L1 数值布局

- 默认安全区为 root `padding: 12`：`2x2` 内容区 `116 x 116`，`2x4` 内容区 `276 x 116`。
- 未指定尺寸时先尝试 `2x2`；只有受保护文本、热区、并列关系、关键媒体或布局预算具体失败时才升级 `2x4`。
- `2x2` 最多 3 个主区域和 1 个显式动作；`2x4` 最多 4 个主区域和 2 个动作区。
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

- 先确定一个主答案；最多展示 4 项用户字段、2 条支撑事实和 1 个主动作，未入选字段留给详情页。
- 可见组件的信息职责必须互斥：对象、状态、设定值、实际值、差值、比例/进度、趋势、时间点/段、位置、金额、数量、动作入口等，每个事实只由一个组件主承载。
- 写前把文案和数值归入“事实等价类”：单位换算、别名/简称、同义标签、短标签扩写、父子包含、聚合/拆分、差值/比例/状态等，只要回答同一事实或判断，就算重复。
- 派生事实只有承担新判断时才展示；进度条只作可视化承载，旁边文案不要复述两端值，除非该值是唯一主事实。
- 信息不足时调整比例、层级和留白，不加空标签、同义指标或装饰填空。
- 颜色优先回溯到 HarmonyOS 语义 token、`ohos_id_color_*`、`multi_color_*` 或 `multi_color_aux_*`；场景拓展色必须说明场景锚点、来源色族、用途角色和克制边界。
- 渐变只用线性渐变，stop 来自官方色板或合规场景拓展色板；禁用无依据手调色、插值色、无来源 alpha、径向装饰、orb 或 bokeh。
- 同一卡片只用一个主场景色族；`confirm` / `warning` / `alert` 只服务真实状态。氛围渐变只在不挤压受保护文本和动作区时使用。

## 生成后校验

先做模型内置校验，不要为了校验新建、输出或保留草稿文件。先查协议、绑定、布局、颜色、事件和尺寸，再查信息职责、事实等价类和派生判断。仅在用户要求校验既有文件、修复本地草稿或调试脚本时运行 `scripts/validate_card.py`。
