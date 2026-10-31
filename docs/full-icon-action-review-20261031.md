# FullIconActionLayout 真机验收（2026-10-31）

共 92 个 Full 模板；90 个适用，2 个仅支持宽卡。常规、长文本、关闭可选图标共 270 张有效截图，另对 4 个通过项补测状态/100 数值。数组长文本修复后重拍 39 张，旧图保留但不用于最终结论。

- 当前白名单：24 个（初审通过 4 个、用户确认纳入 20 个）；排除：66 个；不适用：2 个。
- 真机：已连接验收设备；测试宿主 150×150vp；截图 469×469 像素；默认字体。
- 初审判定结合实际截图、组件边界和模板源码。文本框相交不直接代表字形重叠；仅 FI018、FI024 和 FI026 的固定/居中字形在边界提示后人工复核放行。
- 仅检查本地模板展开的布局；独立验收图标按钮省略点击处理器，尺寸/布局保持真实 IconAction 蓝图。不构成在线端到端或点击验收，也不代表其它屏幕或字号通过。
- 本地证据目录：`outputs/full-icon-action-20261031/`，包含全量 HTML、逐项 JSON/CSV、原始截图和下载包；PDF 位于 `output/pdf/`。这些验收产物不随源码提交。

## 白名单

### FI008

`BatteryOverviewFull@1`：正文位于上部，左下进度环与右下动作分离。

常规截图：`FI008-0.png`（保存在本地验收包）。

### FI018

`BluetoothDeviceOverviewConnectionTextFull@1`：底部只有左对齐的固定“已连接/未连接”；整行文本框相交，但字形不与按钮重叠。

常规截图：`FI018-0.png`（保存在本地验收包）。

### FI024

`BluetoothDeviceOverviewEarphonePercentTextFull@1`：固定居中的“耳机状态”与右下动作保持间隔，100% 数值位于上部。

常规截图：`FI024-0.png`（保存在本地验收包）。

### FI026

`CountdownOverviewFull@1`：数字与“天”居中，右下动作与实际字形分离；100天状态复核通过。

常规截图：`FI026-0.png`（保存在本地验收包）。

## 用户确认纳入（2026-10-31）

本轮用户明确确认以下 20 项可加入白名单。最终准入结论按用户确认更新，原始截图、长文本压力结果、边界交集与样式告警均保留；这不表示重新测得全部状态无重叠。初审 JSON 已另存为 `visual-review-before-user-confirmation.json`。

| 用例 | 用户提供名称 | 注册模板名称 |
|---|---|---|
| <a id="fi034"></a>FI034 | `SechduleOverviewDataAllDayFull@1` | `ScheduleOverviewDateAllDayFull@1` |
| <a id="fi036"></a>FI036 | `ScheduleOverviewDataEndFull@1` | `ScheduleOverviewDateEndFull@1` |
| <a id="fi056"></a>FI056 | `SheduleOverviewTimezoneDataEndFull@1` | `ScheduleOverviewTimezoneDateEndFull@1` |
| <a id="fi058"></a>FI058 | `ScheduleOverviewTimezoneTimeFull@1` | `ScheduleOverviewTimezoneTimeFull@1` |
| <a id="fi059"></a>FI059 | `ScheduleOverviewTitleStartFull@1` | `ScheduleOverviewTitleStartFull@1` |
| <a id="fi060"></a>FI060 | `ScheduleOverviewTitleTimeFull@1` | `ScheduleOverviewTitleTimeFull@1` |
| <a id="fi067"></a>FI067 | `WeatherOverviewAlertInfoFull@1` | `WeatherOverviewAlertInfoFull@1` |
| <a id="fi068"></a>FI068 | `WeatherOverviewCardAlertFull@1` | `WeatherOverviewCareAlertFull@1` |
| <a id="fi069"></a>FI069 | `WeatherOverviewConditionFeelsLikeAlertFull@1` | `WeatherOverviewConditionFeelsLikeAlertFull@1` |
| <a id="fi072"></a>FI072 | `WeatherOverviewDailyDateFull@1` | `WeatherOverviewDailyDateFull@1` |
| <a id="fi073"></a>FI073 | `WeatherOverviewDailyHealthFull@1` | `WeatherOverviewDailyHealthFull@1` |
| <a id="fi074"></a>FI074 | `WeatherOverviewDailyRainFull@1` | `WeatherOverviewDailyRainFull@1` |
| <a id="fi076"></a>FI076 | `WeatherOverviewDailyUvColdFull@1` | `WeatherOverviewDailyUvColdFull@1` |
| <a id="fi079"></a>FI079 | `WeatherOverviewFeelsLikeAlertFull@1` | `WeatherOverviewFeelsLikeAlertFull@1` |
| <a id="fi080"></a>FI080 | `WeatherOverviewFull@1` | `WeatherOverviewFull@1` |
| <a id="fi082"></a>FI082 | `WeatherOverviewHumodityWindFull@1` | `WeatherOverviewHumidityWindFull@1` |
| <a id="fi084"></a>FI084 | `WeatherOverviewRainWindFull@1` | `WeatherOverviewRainWindFull@1` |
| <a id="fi085"></a>FI085 | `WeatherOverviewTargetDayHealthFull@1` | `WeatherOverviewTargetDayHealthFull@1` |
| <a id="fi088"></a>FI088 | `WeatherOverviewUvColdFull@1` | `WeatherOverviewUvColdFull@1` |
| <a id="fi090"></a>FI090 | `WeatherOverviewUvOnlyFull@1` | `WeatherOverviewUvOnlyFull@1` |

## 全量记录

|用例|模板|结论|
|---|---|---|
|FI001|`ActivityOverviewFull@1`|排除|
|FI002|`ActivityOverviewTrainingSummaryFull@1`|排除|
|FI003|`BatteryOverviewChargingDiagnosticsFull@1`|排除|
|FI004|`BatteryOverviewChargingProgressFull@1`|排除|
|FI005|`BatteryOverviewChargingTemperatureFull@1`|排除|
|FI006|`BatteryOverviewChargingTypePercentFull@1`|排除|
|FI007|`BatteryOverviewCurrentVoltageFull@1`|排除|
|FI008|`BatteryOverviewFull@1`|白名单通过|
|FI009|`BatteryOverviewHealthLevelFull@1`|排除|
|FI010|`BatteryOverviewPercentDetailsFull@1`|排除|
|FI011|`BatteryOverviewPercentHealthCurrentDetailsFull@1`|排除|
|FI012|`BatteryOverviewPercentHealthDetailsFull@1`|排除|
|FI013|`BatteryOverviewPercentLevelFull@1`|排除|
|FI014|`BatteryOverviewPercentStatusFull@1`|排除|
|FI015|`BatteryOverviewPercentTextFull@1`|排除|
|FI016|`BatteryOverviewTemperatureFull@1`|排除|
|FI017|`BatteryOverviewTemperatureStatusFull@1`|排除|
|FI018|`BluetoothDeviceOverviewConnectionTextFull@1`|白名单通过|
|FI019|`BluetoothDeviceOverviewEarbudPairChargingFull@1`|排除|
|FI020|`BluetoothDeviceOverviewEarbudPairFull@1`|排除|
|FI021|`BluetoothDeviceOverviewEarbudPairRingFull@1`|排除|
|FI022|`BluetoothDeviceOverviewEarbudsFull@1`|排除|
|FI023|`BluetoothDeviceOverviewEarphoneCasePercentTextFull@1`|排除|
|FI024|`BluetoothDeviceOverviewEarphonePercentTextFull@1`|白名单通过|
|FI025|`BluetoothDeviceOverviewMusicFull@1`|排除|
|FI026|`CountdownOverviewFull@1`|白名单通过|
|FI027|`CountdownOverviewTargetDetailFull@1`|排除|
|FI028|`CurrentTimeOverviewDateFull@1`|排除|
|FI029|`CurrentTimeOverviewUpdatedFull@1`|排除|
|FI030|`HeartRateOverviewFull@1`|排除|
|FI031|`HeartRateOverviewMinMaxFull@1`|排除|
|FI032|`HeartRateOverviewUpdatedFull@1`|排除|
|FI033|`ScheduleOverviewAllDayLocationFull@1`|排除|
|FI034|`ScheduleOverviewDateAllDayFull@1`|白名单通过（用户确认）|
|FI035|`ScheduleOverviewDateCountdownReminderFull@1`|排除|
|FI036|`ScheduleOverviewDateEndFull@1`|白名单通过（用户确认）|
|FI037|`ScheduleOverviewDateFull@1`|排除|
|FI038|`ScheduleOverviewDateLocationFull@1`|排除|
|FI039|`ScheduleOverviewDateLocationTimeFull@1`|排除|
|FI040|`ScheduleOverviewDateStartLocationFull@1`|排除|
|FI041|`ScheduleOverviewDateTitleFull@1`|不适用|
|FI042|`ScheduleOverviewEventCountDatedLocationFull@1`|排除|
|FI043|`ScheduleOverviewEventCountDetailsFull@1`|排除|
|FI044|`ScheduleOverviewEventCountNotesFull@1`|排除|
|FI045|`ScheduleOverviewEventCountTwoEventsFull@1`|排除|
|FI046|`ScheduleOverviewLocationDescriptionEndFull@1`|排除|
|FI047|`ScheduleOverviewMeetingSenderFull@1`|排除|
|FI048|`ScheduleOverviewNextEventLocationFull@1`|排除|
|FI049|`ScheduleOverviewReminderDetailsFull@1`|排除|
|FI050|`ScheduleOverviewReminderFull@1`|排除|
|FI051|`ScheduleOverviewReminderSourceFull@1`|排除|
|FI052|`ScheduleOverviewReminderStartFull@1`|排除|
|FI053|`ScheduleOverviewSourceReminderFull@1`|排除|
|FI054|`ScheduleOverviewThreeMeetingsFull@1`|排除|
|FI055|`ScheduleOverviewTimezoneAllDayFull@1`|排除|
|FI056|`ScheduleOverviewTimezoneDateEndFull@1`|白名单通过（用户确认）|
|FI057|`ScheduleOverviewTimezoneFull@1`|排除|
|FI058|`ScheduleOverviewTimezoneTimeFull@1`|白名单通过（用户确认）|
|FI059|`ScheduleOverviewTitleStartFull@1`|白名单通过（用户确认）|
|FI060|`ScheduleOverviewTitleTimeFull@1`|白名单通过（用户确认）|
|FI061|`ScheduleOverviewTwoEventsFull@1`|排除|
|FI062|`SleepOverviewFull@1`|排除|
|FI063|`SleepOverviewNapFull@1`|排除|
|FI064|`SleepOverviewScoreFull@1`|排除|
|FI065|`WeatherOverviewAirQualitySummaryFull@1`|排除|
|FI066|`WeatherOverviewAlertFull@1`|排除|
|FI067|`WeatherOverviewAlertInfoFull@1`|白名单通过（用户确认）|
|FI068|`WeatherOverviewCareAlertFull@1`|白名单通过（用户确认）|
|FI069|`WeatherOverviewConditionFeelsLikeAlertFull@1`|白名单通过（用户确认）|
|FI070|`WeatherOverviewDailyCompareFull@1`|排除|
|FI071|`WeatherOverviewDailyConditionWeekdayFull@1`|排除|
|FI072|`WeatherOverviewDailyDateFull@1`|白名单通过（用户确认）|
|FI073|`WeatherOverviewDailyHealthFull@1`|白名单通过（用户确认）|
|FI074|`WeatherOverviewDailyRainFull@1`|白名单通过（用户确认）|
|FI075|`WeatherOverviewDailySummaryFull@1`|排除|
|FI076|`WeatherOverviewDailyUvColdFull@1`|白名单通过（用户确认）|
|FI077|`WeatherOverviewDestinationDayFull@1`|排除|
|FI078|`WeatherOverviewDualCityFull@1`|排除|
|FI079|`WeatherOverviewFeelsLikeAlertFull@1`|白名单通过（用户确认）|
|FI080|`WeatherOverviewFull@1`|白名单通过（用户确认）|
|FI081|`WeatherOverviewHumidityFull@1`|排除|
|FI082|`WeatherOverviewHumidityWindFull@1`|白名单通过（用户确认）|
|FI083|`WeatherOverviewNextDayHealthFull@1`|排除|
|FI084|`WeatherOverviewRainWindFull@1`|白名单通过（用户确认）|
|FI085|`WeatherOverviewTargetDayHealthFull@1`|白名单通过（用户确认）|
|FI086|`WeatherOverviewThreeDayForecastFull@1`|不适用|
|FI087|`WeatherOverviewUpdatedAtFull@1`|排除|
|FI088|`WeatherOverviewUvColdFull@1`|白名单通过（用户确认）|
|FI089|`WeatherOverviewUvFull@1`|排除|
|FI090|`WeatherOverviewUvOnlyFull@1`|白名单通过（用户确认）|
|FI091|`WeatherOverviewWindFull@1`|排除|
|FI092|`WorkoutOverviewFull@1`|排除|

## 样式告警

45 张全量截图及 1 张边界截图带既有样式告警，主要是 `textAlign=left`、Row 的 `alignItems=start/end`。通过项 FI018 的 4 张截图有 `left` 枚举告警，已核对端侧回退后的实际左对齐及字形范围，无重叠；本次不扩大为模板样式整改，视觉通过不等于样式告警清零。完整原始告警保存在截图清单与逐项 JSON。

## 准入与维护

`resources/source/full-icon-action-allowlist.json` 是唯一准入配置；注册表读取后由 Planner、二层候选过滤和编译入口共同消费。白名单绑定业务模板、布局和动作定义的 SHA-256；任一定义变化后旧记录不生效。没有合格 Full 候选时沿用原有其它布局和不匹配语义，不删减字段或动作。新增模板先运行全量验收工具并完成逐图确认，再更新白名单；不得自动将无边界告警等同于视觉通过。

## 可复现环境

生成与测试使用项目 `.venv`。当前配置缺失 `ids_flow_control_id`，仅在本次进程内为离线验收补入不参与调用的占位值；未改配置文件、未调用在线服务。生成器显式枚举全部 Full，绕过的是运行时准入过滤，不绕过正式生成入口的白名单。真机截图宿主为独立临时副本，未修改端侧仓库源码。


## 提交范围

本次提交包含 24 项白名单配置、Planner 与第二层候选过滤、编译准入、验收生成和核对工具、回归测试及设计说明。
验收工具使用 `_preview_root` 新增的可选 `fill_available_height` 参数，使 Full 容器跟随宿主可用高度；默认值为 `False`，原有预览调用保持原行为。其它预览间距和图片主题修改不纳入本次提交。

初审及用户确认分别保留：4 项初审通过，20 项按用户明确确认纳入。用户确认不等于长文本压力结果或端侧样式告警已经消失。运行时持续校验模板、布局与动作定义的摘要，源内容变化后旧准入记录失效。

## Rebase 后验证

最终基线为 InnovationTea/main `6061e3ba2252ba3432fe5cd798d80ddbbf1e26da`（#723）。两次迁移均无冲突；本次提交不重复携带已通过 #711 合入的天气健康提交。

- 第一次基线 `31e9966f3`：5 个相关测试文件共 419 项，396 通过、23 失败。
- main 更新后，在最终基线复跑核心 48 项及上述 23 个失败项：48 通过、23 失败。23 项在未修改的最终 main 上全部复现，用例 ID 和报错信息一致，没有新增失败。未在最终基线重跑全部 419 项。
- Ruff 0.16.9 检查本次 11 个 Python 文件通过。Pylint 4.0.8 / astroid 4.0.4 使用用户级基础规则，仍有 `ux_mixed_prompt.py` 中 3 条既有 E0606；与未修改 main 一致。没有屏蔽规则；正式 CodeCheck 未取得对应入口与规则包，未复扫。
- CardPlan bundle 同步检查、工作区与暂存区差异空白检查通过。
- 最终基线重新生成 276 条画廊记录（270 成功、6 不适用）和 4 个补充边界状态，模板摘要及 A2UI 产物摘要与真机截图对应版本全部一致；24 项白名单均有效。
- 本次 rebase 没有重新采集真机截图，没有执行在线模型或动作点击验收。原 274 张有效截图仍只证明已声明的设备、测试尺寸和字体范围。
- 本地测试沿用项目已有依赖环境；当前默认配置缺失 `ids_flow_control_id`，仅在测试进程中注入不参与外部调用的独立测试值，没有修改配置文件或调用 IDS。

### 最终 main 已复现的 23 个失败用例

- `test_template_generation.py::test_business_template_suffix_or_declaration_drives_size_and_data_tiers`
- `test_template_generation.py::test_weather_daily_templates_declare_exact_item_contracts[WeatherOverviewDailyDateFull@1-primary_data0-secondary_data0-optional_data0-required_bindings0-optional_bindings0]`
- `test_template_generation.py::test_weather_daily_templates_declare_exact_item_contracts[WeatherOverviewDailyRainFull@1-primary_data1-secondary_data1-optional_data1-required_bindings1-optional_bindings1]`
- `test_template_generation.py::test_weather_daily_templates_declare_exact_item_contracts[WeatherOverviewDailyCompareFull@1-primary_data2-secondary_data2-optional_data2-required_bindings2-optional_bindings2]`
- `test_template_generation.py::test_weather_daily_templates_declare_exact_item_contracts[WeatherOverviewDailyHealthFull@1-primary_data3-secondary_data3-optional_data3-required_bindings3-optional_bindings3]`
- `test_template_generation.py::test_weather_daily_item_word_labels_match_bound_daily_index`
- `test_template_generation.py::test_weather_daily_item_binding_uses_the_exact_array_index`
- `test_template_generation.py::test_weather_daily_item_binding_does_not_fallback_to_index_zero`
- `test_template_generation.py::test_business_groups_are_derived_from_provider_templates`
- `test_template_generation.py::test_health_sport_templates_follow_latest_display_contract`
- `test_template_generation.py::test_pr7_visual_fixes_are_encoded_in_provider_cardtpl_variants`
- `test_template_generation.py::test_calendar_templates_follow_latest_schedule_contract`
- `test_template_generation.py::test_bluetooth_music_action_uses_hero_pair_data`
- `test_template_generation.py::test_template_exception_obeys_route_failure_policy[generation-error-generate_widget_card_compact_dsl-False]`
- `test_template_generation.py::test_template_exception_obeys_route_failure_policy[route-not-applicable-generate_widget_card_compact_dsl-False]`
- `test_template_generation.py::test_template_quality_failure_obeys_entry_fallback_policy[compact]`
- `test_template_generation.py::test_template_quality_failure_obeys_entry_fallback_policy[terse]`
- `test_template_generation.py::test_terse_edit_is_rejected_before_template_source_request`
- `test_template_plan_planner.py::test_wide_plan_tie_prefers_two_compact_over_hero_action_layout`
- `test_template_internal_contracts.py::test_wide_two_full_layout_owns_support_surface_for_each_slot`
- `test_template_preview_dataset.py::test_earphone_hero_uses_title_parameter_without_title_binding`
- `test_template_preview_dataset.py::test_earphone_ring_previews_include_required_device_icon[BluetoothDeviceOverviewMusicFull@1-earphone_case_16644.svg]`
- `test_template_preview_dataset.py::test_weather_rain_previews_keep_numbers_and_format_text_units`
