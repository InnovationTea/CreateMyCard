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

当前迁移范围：

- `weather`：`ViewWeather` → 9 个 UI 模板
- `calendar`：`GetCalendarEvents` → 10 个日期/日程 UI 模板
- `battery`：`GetPhoneBatteryInfo` → 17 个电量 UI 模板
- `system-memory`：`GetSystemMemInfo` → 2 个内存 UI 模板
- `app-usage`：`GetAppUsageDuration` → 5 个应用时长 UI 模板
- `health-sport`：`GetHealthAndSportSummary` → 17 个活动、运动、心率和睡眠 UI 模板
- `countdown`：`GetCountdownDays` → `CountdownOverviewFull@1`
- `earphone`：`GetEarphoneInfo` → 14 个耳机状态/电量 UI 模板
- `layout`：无数据能力 → 10 个支持 `...children` 的布局模板
- `action`：无数据能力 → `PillAction@1`、`IconAction@1` 两个 Props 驱动的动作模板

除 `GetSystemMemInfo` 使用 Bundle 本地 Schema 外，
其余能力均只读引用正式能力注册表。新增或修改 `.cardtpl` 后必须重新加载 Provider Bundle，
再重建 CardPlan 清单并运行 Provider Template 测试。

Provider 若需要覆盖外层布局 Action 的底托透明度，可在模板根组件样式中声明受信内部属性
`_layoutActionBackgroundOpacity`。运行时仅在该 Provider Template 独占业务区时，
以主题 Action 前景色的 RGB 和声明透明度生成底托色；多业务组合仍使用主题默认 Action 样式。

在 `widget_service` 目录执行：

```bash
.venv312/bin/python scripts/build_cardplan_bundle.py
PYTHONPATH=cloud .venv312/bin/python -m pytest -q \
  cloud/services/template_generation/tests
```

上述 Provider CardTemplate 均已接入 UX Registry 默认实现。运行时按 `primaryData`、`secondaryData`、
`optionalData`、`dataDomain`、
CardSpec `writeResultTo` 和 TaskSpec 字段进行准入，并在 Compiler 中继续复用原业务组件的组合顺序、
角色校验。Action 使用第一层独立选择的零到两个 `eventId`，由第二层按业务模板后缀调用布局末尾的
`PillAction@1` 或 `IconAction@1` 并填写 Props；Action Provider 拥有组件结构，微服务只注入主题色和
将模板内 `EventAction(props.actionId)` 声明实体化后的可信事件。
