# Compact DSL Form 协议硬约束

本 profile 继承 `a2ui-form-rom6.0-v1` 的卡片语义、组件范围、布局、视觉、事件、素材和
DataModel 约束。Compact DSL 只改变序列化格式，不改变卡片的设计目标和运行行为。

- `version`："v1"
- `format`："compact-dsl"
- `catalogId`："ohos.genui.compact.catalog"

## 决策顺序

1. 先按 Form 规则完成卡片结构、视觉布局、数据绑定和事件设计。
2. 只使用 Form 允许的 10 个组件；禁用能力不因 Compact DSL 示例出现而放行。
3. 按 Compact DSL 把组件树序列化为父先子后的 tuple NDJSON。
4. 把 A2UI 的动态表达式序列化为 `{"path":"/..."}` 和对应数据行。
5. 组件、DataModel、事件能力、图片资源和颜色规则按本 profile 的专项文档校验。

## 输出边界

`genui` 只包含裸 NDJSON，不带 Markdown 围栏、解释文字、外层 JSON 对象，也不输出
`createSurface`、`updateComponents` 或 `updateDataModel`。

协议只有两种行：

```text
["<componentId>","<Type>",{<props>},["<childId>",...]]
["/<json-pointer>",<value>]
```

规则：

- 每个物理行是一个完整 JSON 数组；不把所有行包进外层数组，不在行之间写逗号。
- `Row`、`Column`、`List`、`Stack` 必须有第四段 children；其它组件禁止有 children。
- 第一行创建 `root`，类型只能是 `Column` 或 `Stack`，props 必须包含
  `"width":"matchParent"`。
- 父组件先于子组件；除 root 外，每个组件必须先出现在更早父组件的 children 中。
- A2UI 顶层语义字段和 `styles` 字段统一平铺到 props；禁止输出 `style` 或 `styles` 包装层。
- A2UI `Row.itemMargin`、`Column.itemMargin` 在 Compact DSL 中写为 `space`；
  `List.space` 保持为 `space`。
- 静态值直接写入 props；动态值使用 path 绑定，并在组件行之后输出对应数据行。

## 卡片 shell 与尺寸

- root 是唯一卡片 shell，承载尺寸、安全区、圆角、裁切、背景和内容布局。
- `2x2` 的宿主 surface 是 `140 x 140`；root 使用 `width:"matchParent"`、`height:140`、
  `borderRadius:18`、`clip:true`，默认四边 `padding:12`。
- `2x4` 的宿主 surface 是 `300 x 140`；root 使用 `width:"matchParent"`、`height:140`、
  `borderRadius:22`、`clip:true`，默认四边 `padding:12`。
- `backgroundColor`、`linearGradient`、`backgroundImage` 等背景字段必须写在 root props，
  或由 root 下真实背景组件承载，避免默认白底遮挡背景。
- root 必须显式提供背景字段，不依赖默认白底；优先使用与场景匹配且保证文字对比度的渐变背景，
  禁止生成无背景卡片或浅色文字叠在近白背景上的卡片。
- 视觉完成度不得低于同任务的 A2UI Form：root 必须有明确表面设计，信息层级包含主信息、辅助信息
  和可用事件对应的 CTA；禁止只满足协议结构而输出无背景、无主次关系的占位布局。
- 同任务的信息集合不得少于 A2UI Form。Compact DSL 只优化序列化格式，不得删除 userQuery 明确要求的
  字段、语义标签、状态或动作；图标、位置和裸数值不能替代字段标签。
- root 的直接子项必须落在扣除 padding 后的安全区内；Row 子项宽度、Column/List 子项高度和
  `space` 总和不得超过容器可用空间。
- root 为 Column 且子项高度可计算时，末段底部空隙通常保持 `8-14`；超过 `16` 视为
  排版错误，小于 `8` 作为拥挤风险提示。
- 视觉密度、分组、主次关系、字体阶梯、间距阶梯和 CTA 位置均沿用 Form 卡片规则；
  Compact DSL 不额外引入固定的三行模板或另一套设计风格。

## Form 裁剪范围

- 允许组件只有 `Text`、`Image`、`Divider`、`Progress`、`Button`、`Checkbox`、`Row`、
  `Column`、`List`、`Stack`。
- 默认不使用自定义组件；宿主没有明确声明 catalog 注册时不得自行扩展。

禁用：

- 组件：`TextInput`、`Toggle`、`Radio`、`CheckboxGroup`、`Select`、`NavContainer`、
  `Tabs`、`TabContent`、`Web`、`Grid`、`If`
- 能力：`theme`、`onAppear`、`onChange`、`onSelect`、`onReachStart`、`onReachEnd`
- 函数/变量：`setDataModel`、`setAttributes`、`navigate`、`scrollTo`、`sendToAssistant`、
  `$__widthBreakpoint`、`$__colorMode`
- 媒体：网络图片、内联/base64 SVG、未声明 SVG、`data:image/svg+xml`

## 事件与函数

事件能力与工具3一致，只使用输入 `eventCandidates` 中已声明的 call 和 args，不虚构函数、
参数、URL 或跳转目标。A2UI 的单个 `onClick` EventHandler 在 Compact DSL 中序列化为
Button 的 `action.functionCall`：

```json
["action","Button",{"label":"打开","enabled":true,"action":{"functionCall":{"call":"clickToDeeplink","args":{"uri":"..."}}}}]
```

规则：

- 需要点击行为时使用语义 `Button`；其它组件不写 `action` 或 `onClick`。
- `action` 只包含一个 `functionCall`；`call` 和完整 `args` 必须精确匹配候选事件。
- 动态事件参数使用 path 绑定；静态固定目标直接写 JSON 值。
- 没有已声明事件能力时删除点击行为，不生成空按钮或占位跳转。
- 不引入 Compact DSL 通用 profile 的表单提交、`submit_form` 或 `openUrl` 扩展语义。

## DataModel 与媒体

- CardSpec `dataBindings[].writeResultTo` 仍是结构 JSON Pointer，不改变其路径。
- 每个可见动态值必须绑定到 `writeResultTo` 与 capability `outputSchema` 能推导出的字段。
- `Image.src` 和 `backgroundImage` 只使用用户提供或素材库声明的本地资源路径。
- 没有真实本地资源时，使用渐变、半透明块、文字、`Progress` 或 `Divider` 表达状态，
  不编造图标、网络图片或资源路径。

## 样式位置

Compact DSL 不使用 `styles` 包装层。原 Form `styles.xxx` 在 props 中写为同名字段，例如
`fontSize`、`fontColor`、`justifyContent`、`alignItems`、`padding`、`borderRadius`、
`backgroundColor`、`linearGradient`。详细取值和视觉约束见 `component-catalog.md`。
