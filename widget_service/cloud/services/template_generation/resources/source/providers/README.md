# Provider CardTemplate

本目录按数据能力提供方组织声明式垂域模板。
每个子目录必须以 `provider.json` 为入口；业务能力关联声明
`capabilityId`、`dataDomain`、`dataSchema` 和 `templates`。
业务 Provider 根级必须另外登记 `firstLayerRule.path` 和 `secondLayerRule.path`，分别指向首层组件/数据路径
规则和二层具体模板/props 规则。领域规则只从这些 MD 按候选动态加载；无数据的 Layout Provider 不需要
这两个规则文件。

Provider 的业务组件索引直接由 `provider.json#templates[].businessId` 派生，Template 实现只来自对应
`.cardtpl`。根资源目录不得再维护 `advanced-component-registry.json` 或 `template-registry.json`，也不得
加入兼容读取形成第二份事实源；未被现有 Provider 接管的历史条目不进入运行时 Registry。

所有 `.cardtpl` 组件均使用 [Tersel Option 3](../../../docs/tersel-protocol.md)，直接声明内联样式，不使用
DesignToken。Provider 模板是受信资源，不需要用 DesignToken 缩短模型 Prompt；主题色通过受限
`$theme('<path>')` 内联值声明，并在可信展开阶段解析。
仅按数据路径或 Prop 可用性选择值时使用逐层加括号的生成期三元表达式；编译器只删除三元选择结构，
选中的 `data.xxx` 继续作为直接 A2UI 数据绑定，不能用 TaskSpec 的 `sampleValue` 固化展示内容。

当前迁移范围：

- `weather`：`ViewWeather` → 9 个 UI 模板
- `calendar`：`GetCalendarEvents` → 8 个日期/日程 UI 模板
- `battery`：`GetPhoneBatteryInfo` → 7 个电量 UI 模板
- `system-memory`：`GetSystemMemInfo` → 3 个内存 UI 模板
- `app-usage`：`GetAppUsageDuration` → 6 个应用时长 UI 模板
- `health-sport`：`GetHealthAndSportSummary` → 30 个活动、运动、心率和睡眠 UI 模板
- `countdown`：`GetCountdownDays` → `CountdownOverviewFull@1`
- `earphone`：`GetEarphoneInfo` → 9 个耳机状态/电量 UI 模板
- `layout`：无数据能力 → 6 个支持 `...children` 的布局模板；仅含 `Wide` 的布局用于 `2x4`
- `action`：无数据能力 → `PillAction@1`、`IconAction@1` 两个 Props 驱动的动作模板

除 `GetSystemMemInfo` 使用 Bundle 本地 Schema 外，
其余能力均只读引用正式能力注册表。新增或修改 `.cardtpl` 后必须重新加载 Provider Bundle，
再重建 CardPlan 清单并运行 Provider Template 测试。

Provider 若需要覆盖外层布局 Action 的底托透明度，可在模板根组件样式中声明受信内部属性
`_layoutActionBackgroundOpacity`。运行时仅在该 Provider Template 独占业务区时，
以主题 Action 前景色的 RGB 和声明透明度生成底托色。当前生产 Search 的 `2x2` 路径只接收单业务及
零到两个 Action，多业务会在进入第二层前显式拒绝；兼容的 LLM 选择链路仍使用主题默认 Action 样式。

在 `widget_service` 目录执行：

```bash
.venv312/bin/python cloud/services/template_generation/tools/build_cardplan_bundle.py
PYTHONPATH=cloud .venv312/bin/python -m pytest -q \
  cloud/services/template_generation/tests
```

上述 Provider CardTemplate 均已接入 UX Registry 默认实现。运行时按 `primaryData`、`secondaryData`、
`optionalData`、`dataDomain`、
CardSpec `writeResultTo` 和 TaskSpec 字段进行准入，并在 Compiler 中继续复用原业务组件的组合顺序、
角色校验。Action 使用第一层独立选择的零到两个 `eventId`，由第二层按业务模板后缀调用布局末尾的
`PillAction@1` 或 `IconAction@1` 并填写 Props；Action Provider 拥有组件结构，微服务只注入主题色和
将模板内 `EventAction(props.actionId)` 声明实体化后的可信事件；Support 模板可使用
`EventAction(props?.actionId)`，未提供 `actionId` 时不生成 `onClick`。
