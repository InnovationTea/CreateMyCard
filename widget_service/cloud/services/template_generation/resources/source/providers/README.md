# Provider CardTemplate

本目录按数据能力提供方组织声明式垂域模板。
每个子目录必须以 `provider.json` 为入口；业务能力关联声明
`capabilityId`、`dataDomain`、`dataSchema` 和 `templates`。
业务 Provider 根级必须另外登记 `firstLayerRule.path` 和 `secondLayerRule.path`，分别指向首层组件/数据路径
规则和二层具体模板/props 规则。领域规则只从这些 MD 按候选动态加载；无数据的 Layout Provider 不需要
这两个规则文件。

当前迁移范围：

- `weather`：`ViewWeather` → `WeatherOverviewCompact@1` 等 4 个 UI 模板
- `calendar`：`GetCalendarEvents` → 10 个日期/日程 UI 模板
- `battery`：`GetPhoneBatteryInfo` → 15 个电量 UI 模板
- `system-memory`：`GetSystemMemInfo` → 2 个内存 UI 模板
- `app-usage`：`GetAppUsageDuration` → 4 个应用时长 UI 模板
- `health-sport`：`GetHealthAndSportSummary` → 23 个活动、运动、心率和睡眠 UI 模板
- `countdown`：`GetCountdownDays` → `CountdownOverview@1`
- `earphone`：`GetEarphoneInfo` → 14 个耳机状态/电量 UI 模板
- `layout`：无数据能力 → 10 个支持 `...children` 的布局模板

除 `GetSystemMemInfo` 使用 Bundle 本地 Schema 外，
其余能力均只读引用正式能力注册表。新增或修改 `.cardtpl` 后必须更新对应 SHA-256，
再重建 CardPlan 清单并运行 Provider Template 测试。

Provider 若需要覆盖外层布局 Action 的底托透明度，可在模板根组件样式中声明受信内部属性
`_layoutActionBackgroundOpacity`。运行时仅在该 Provider Template 独占业务区时，
以主题 Action 前景色的 RGB 和声明透明度生成底托色；多业务组合仍使用主题默认 Action 样式。

```bash
.venv/bin/python scripts/build_cardplan_bundle.py
PYTHONPATH=cloud .venv/bin/pytest -q tests/test_provider_template_bundle.py
```

上述 Provider CardTemplate 均已接入 UX Registry 默认实现。运行时按 `requiredData`、`dataDomain`、
CardSpec `writeResultTo` 和 TaskSpec 字段进行准入，并在 Compiler 中继续复用原业务组件的组合顺序、
角色校验。Action 使用第一层独立选择的 `eventId`，由第二层统一生成布局末尾 `PillAction`；可信 Python
构造器仅作为代码级回滚和影子测试基线，不再出现在默认 Prompt。
