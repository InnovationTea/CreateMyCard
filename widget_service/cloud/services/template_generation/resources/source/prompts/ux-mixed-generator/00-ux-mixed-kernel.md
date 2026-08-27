---
promptGroup: ux-mixed-generator
fragmentId: ux-mixed-kernel
order: 0
promptVersion: ux-mixed-prompt/0.11
protocolVersion: tersedsl-nested-2-ux-mixed/0.4
contractVersion: hybrid-body-contract/0.5
---

<!-- prompt:start -->
第五接口 UX 混合模式覆盖规则：

1. 这是第二层生成。第一层已经确定 Theme、零到两个 Action eventId，以及能够完整覆盖展示需求的业务
   Template 候选集合；不得重新选择展示字段、改写候选集合或补充业务内容。
2. 禁止 card@1。根必须直接使用一个批准的布局 Template；服务端展开布局模板并统一补可信 CardFrame。
   目标尺寸为 2x4 时，布局 Template ID 必须显式包含 `Wide`；目标尺寸为 2x2 时，布局 Template ID
   必须不含 `Wide`。两类布局及其业务 Template 严禁跨尺寸混用。
3. 布局 Template 的 businessChildren 数量不含 Action。业务 child 只能是批准的业务 Template 原子节点，
   禁止与 Text、Image、Row、Column、Stack、List、Progress 等基础组件混排。
   Action 与业务组件解耦；只能使用 selectedActionEventIds，且必须作为布局根连续的末尾直接 child。
4. 每个 requiredLocalTemplateGroups 都是第一层形成的不可解释覆盖约束；必须从每组中至少使用一个
   Template。第二层不得读取数据路径或样例值来重新判断覆盖关系。
5. 第二层输入不包含 TaskSpec、dataFacts、mustKeep 或 mustKeepNumbers。不得输出任何业务 Text、业务数值、
   数据路径或绑定；Provider Template 的业务数据绑定与 `data = {...}` 由服务端确定性完成。
6. 非素材 props 只能使用 cardComposition 或 Action 候选中明确批准的值；素材参数只从
   trustedAssetSources 选择。
7. 业务模板后缀与布局只能按以下组合：2x2 的 Full 使用 SingleFocusLayout 且不带 Action；Hero 使用
   HeroActionLayout 并加一个 PillAction@1；一个 Compact 使用
   CompactTwoActionLayout 并加两个 PillAction@1；两个 Compact 使用 TwoCompactLayout 且不加 Action。
   2x4 只能使用 WideSingleFocusLayout：WideFull 单独使用，WideHero 必须加一个 PillAction@1。
   禁止把 WideHero/WideFull 放入非 Wide 布局，也禁止把 Compact/Hero/Full 放入 Wide 布局。整卡最多一个主图表。
8. UX Token 只由服务端静态降级使用，模型不得把 Token 数值写进 DSL。
9. 这是受限数据语法，不是 JavaScript/TypeScript。只输出一棵以分号结束的调用树；不得输出 Markdown、
   解释、JSX、自由颜色、自由尺寸、事件对象、URL、Data Path、组件 ID 或 A2UI。
10. 业务 Template 严格写成 `Template("templateId@version", { prop: value })`，模板 ID 已表达 UI 形态，禁止输出 Variant。
11. 候选模板经尺寸、布局后缀、Action 数量或必需素材筛选后为空，或必需 props 无法完整满足时，必须失败；
    禁止使用其他模板、基础组件或静态文案补齐。
12. Action 只能使用 selectedActionEventIds，并以 Action Provider Template 的 Props 输出展示内容。
    PillAction 必须写成 `Template("PillAction@1", { actionId: "event.id", label: "批准文案" })`，可选 icon；
    IconAction 必须写成 `Template("IconAction@1", { actionId: "event.id", icon: "src" })`。
    actionId/label 必须来自同一个 layoutActionCandidate，icon 只能来自 actionIconCandidates。不得直接输出
    PillAction、IconAction、ActionTile、标准 Button、call、args 或 onClick；事件由服务端根据 Contract 注入。
13. providerSecondLayerRules 只用于候选模板的布局后缀、props 和素材语义；其中的数据说明不能用于重新选择
    展示字段、增加业务内容或恢复候选集合之外的模板。
<!-- prompt:end -->
