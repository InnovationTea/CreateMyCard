---
promptGroup: ux-mixed-generator
fragmentId: ux-mixed-kernel
order: 0
promptVersion: ux-mixed-prompt/0.7
protocolVersion: tersedsl-nested-2-ux-mixed/0.3
contractVersion: hybrid-body-contract/0.5
---

<!-- prompt:start -->
第五接口 UX 混合模式覆盖规则：

1. 这是第二层生成。第一层已经确定 Theme、业务高级组件和可选 Action eventId；不得重新选择或改写。
2. 禁止 card@1。根必须直接使用一个批准的布局 Template；服务端展开布局模板并统一补可信 CardFrame。
3. 布局 Template 的 businessChildren 数量不含 Action。业务 child 可由批准的业务 Template 与标准组件混排。
   Action 与业务组件解耦；存在 selectedActionEventId 时，必须作为布局根唯一的末尾直接 child，
   写成 `PillAction({"actionId":"<selectedActionEventId>"})`。不存在时不得输出 Action。
4. 每个 template 实现必须从本次 requiredLocalTemplateGroups 对应组中至少使用一个可信局部 Template。
   标准组件不能完整替代已选业务高级组件。
5. 所有业务字符串必须逐字复制 dataFacts、businessTitleCandidate 或可信候选；禁止补写状态、单位、标签或解释。
6. trustedStringLiterals 是非素材 string 参数的完整白名单；素材参数只从 trustedAssetSources 选择。
7. 2x2 通常使用 1 到 2 个业务单元，最多 3 个；2x4 通常使用 2 到 3 个，最多 4 个。
   整卡最多一个 PillAction 和一个主图表。
8. UX Token 只由服务端静态降级使用，模型不得把 Token 数值写进 DSL。
9. 这是受限数据语法，不是 JavaScript/TypeScript。只输出一棵以分号结束的调用树；不得输出 Markdown、
   解释、JSX、自由颜色、自由尺寸、事件对象、URL、Data Path、组件 ID 或 A2UI。
10. 业务 Template 严格写成 `Template("templateId@version", { prop: value })`，模板 ID 已表达 UI 形态，禁止输出 Variant。
11. 每条 mustKeep/mustKeepNumbers 必须由一个标准组件或局部 Template 消费；素材按 description 与参数语义匹配。
12. Action 只能使用 selectedActionEventId，且只能输出 PillAction。不得输出 label、call、args、onClick、图标、
    IconAction、ActionTile、标准 Button 或 Action Template；可见文案与事件由服务端根据 Contract 注入。
13. providerSecondLayerRules 是业务模板、props 和素材使用规则的唯一垂域来源；只应用其中与已选组件对应的规则。
<!-- prompt:end -->
