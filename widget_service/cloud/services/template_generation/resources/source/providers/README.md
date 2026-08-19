# Provider CardTemplate

本目录按数据能力提供方组织声明式垂域模板。
每个子目录必须以 `provider.json` 为入口；单个能力关联只允许
`capabilityId`、`dataSchema` 和 `templates` 三个字段。

当前迁移范围：

- `weather`：`ViewWeather` → `WeatherOverview@1`
- `calendar`：`GetCalendarEvents` → `DateOverview@1`、`ScheduleOverview@1`
- `battery`：`GetPhoneBatteryInfo` → `BatteryOverview@1`
- `system-memory`：`GetSystemMemInfo` → `ResourceUsageOverview@1`
- `app-usage`：`GetAppUsageDuration` → `AppUsageOverview@1`
- `health-sport`：`GetHealthAndSportSummary` → `ActivityOverview@1`、
  `WorkoutOverview@1`、`HeartRateOverview@1`、`SleepOverview@1`
- `countdown`：`GetCountdownDays` → `CountdownOverview@1`
- `earphone`：`GetEarphoneInfo` → `BluetoothDeviceOverview@1`

除 `GetSystemMemInfo` 使用 Bundle 本地 Schema 外，
其余能力均只读引用正式能力注册表。新增或修改 `.cardtpl` 后必须更新对应 SHA-256，
再重建 CardPlan 清单并运行 Provider Template 测试。

Provider 若需要覆盖外层布局 Action 的底托透明度，可在 `#Template` 中声明
`layoutActionStyle: { backgroundOpacity: 0.1 }`。运行时仅在该 Provider Template 独占业务区时，
以主题 Action 前景色的 RGB 和声明透明度生成底托色；多业务组合仍使用主题默认 Action 样式。

```bash
.venv/bin/python scripts/build_cardplan_bundle.py
PYTHONPATH=cloud .venv/bin/pytest -q tests/test_provider_template_bundle.py
```

上述 Provider CardTemplate 均已接入 UX Registry 默认实现。运行时按 Variant 的 `requiredBindings`、
CardSpec `writeResultTo`、卡片尺寸和主题进行准入，并在 Compiler 中继续复用原业务组件的组合顺序、
角色和 Action 归属校验。可信 Python 构造器仅作为代码级回滚和影子测试基线，不再出现在默认 Prompt。
