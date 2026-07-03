# 最终阻断清单

仅在人工复核、修复已有 DSL 或 validator 不可用时读取。顺序与 `core-rules.md` 的 P0 阻断保持一致：先看输出契约，再看 Surface/root，再看组件/绑定，最后看渲染和视觉。任一项失败都先修复，不交付。

## 协议阻断

- 不是两个代码块，或 `genui` 不是三行 JSONL。
- JSONL 顺序不是 `createSurface`、`updateComponents`、`updateDataModel`。
- `version`、`catalogId`、CardSpec `suggestSize` 或 `createSurface.width/height` 不正确。
- `updateComponents.root` 缺失，或没有引用 `components` 中存在的组件 id。
- root 组件没有承载卡片 shell：`width`、`height`、`padding`、`borderRadius`、`clip` 和明确表面背景（`backgroundColor`、`linearGradient` 或 root 下的真实背景组件）。
- `createSurface` 承载了内容布局、安全区或非形状/裁切类 shell 样式，导致 root shell 不完整；`createSurface.styles` 只允许 `borderRadius`、`clip` 等卡片级形状/裁切辅助。
- 背景色、渐变或背景图写在 `createSurface.styles` 而非 `root.styles`，或 root 缺少明确背景，导致 root 默认不透明白底遮挡 surface 背景并显示默认白底。
- 使用禁用组件、禁用事件、`theme`、`Button.action`、网络图片、SVG、emoji 或占位素材。
- `children` 内联组件对象，或绑定路径/DataModel/事件参数无法对应。
- CardSpec 写入点击行为，或静态卡片虚构数据能力。

## 渲染阻断

- 文本、按钮、图形、图片、背板越过 `12vp` 安全区。
- Row/Column 宽高预算不成立，未把子项 `margin` 计入预算，或依赖默认伸缩承载关键布局，导致溢出、碰撞、重叠或显示不全。
- Row 内 `Text + Button` 并排但父 Row、Text 或 Button 缺少明确宽高预算。
- 受保护文本被省略、裁剪、跑马灯或窄宽度隐藏。
- 字号、间距不在批准阶梯内，或 `10fp` 承载主信息。
- 底部支撑/动作区不贴底，按钮看起来悬浮、贴顶、贴底、被 margin 推出槽位，或和邻近文本基线不适。
- Stack 覆盖受保护文本、CTA、点击元素或主数值。

## 视觉阻断

- 重复展示同一语义信息，或用同义指标填充空间。
- 没有单一主答案，出现多个 hero、多个主色族或动作抢焦点。
- 颜色既无法回溯到鸿蒙色板来源，也无法用合规场景拓展色说明来源、场景和用途；或 DSL 直接输出 token/拓展色名而不是 hex。
- 状态色被当装饰，渐变 stop 含无场景依据的手调色、机械插值色或无来源 alpha。
- 连续无意义空白超过 `18vp`，且不服务主视觉、媒体或进度。
