# PR256 最新主线集成记录

## 分支与范围

- 核验日期：2026-09-08。
- 目标远端仓库：`yanshuifeng/CreateMyCard`。
- 新分支：`codex/main-pr256-20260908`；本地上游跟踪 `innovationtea/main`，
  推送远端单独配置为 `yanshuifeng`。远端分支不会自动同步未来的 main 提交。
- 主线基点：`8f3a9b88a6e29f92ba9313d72c4d9cecceb3c21d`。
- 来源：[InnovationTea/CreateMyCard PR256](https://github.com/InnovationTea/CreateMyCard/pull/256)，
  头提交 `5d19efba68cc38deb4494aff90456b591b6c5481`，
  与主线共同祖先 `ce15128e8aca197e6611ed6c9fcceb7257d585ac`。
- 将 PR 的有效树差异 squash 到最新主线；不改动原 PR 分支，不合并主线。
- 原 PR 有效差异为 74 个文件，全部位于 `template_generation`。
  本次另外新增本记录，合计 75 个文件；未携带 HTTP 补丁、凭据或临时交付文档。
- 原工作区已有修改与未跟踪文件保持不变。

## 集成处理

1. 解决编译器、Bundle、天气使用说明和 3 份测试文件的文本冲突。
2. 保留主线新增天气模板、多根数据绑定和天气内容安全边距；保留 PR 的前置 Planner、
   Support 业务事件和 Image 显式着色/原色保护规则。
3. 新 Search 使用全部数据根检查字段和类型，避免误用旧单根接口。
4. 主线新增的双城、关怀天气端到端用例改用无主题的一层输出，主题仍由 Planner 决定。
5. 同步天气图标参数说明及预览/画廊数量：105 个业务模板、114 个注册模板，
   129 项自动化输入（14 项缺能力，115 项待生成）。这些计数不是实际 LLM 生成成功数。

## 实际验证

在 `widget_service` 目录，使用 Python 3.12 虚拟环境、`LOCAL_FLAG=true PYTHONPATH=cloud`：

- 修改的 28 个 Python 文件执行 Ruff：通过。
- `python cloud/services/template_generation/tools/build_cardplan_bundle.py --check`：通过。
- 双根 Search/Planner 的完整数据、缺字段、类型不匹配用例：3 通过、7 排除。
- 双城与关怀天气编译、素材参数语义说明用例：3 通过、234 排除。
- 模板子系统完整测试：1189 通过、5 失败，耗时 109.80 秒；没有全绿。
- 干净主线独立基线：593 通过、10 失败，耗时 99.04 秒。
- 原 PR 充电状态相关基线：4 通过、1 失败、13 排除，耗时 0.42 秒。
- 差异空白与冲突标记检查：通过。
- 本次未运行真实 LLM 批量生成，也未重新打包或安装 HAP。

完整测试命令：

```bash
LOCAL_FLAG=true PYTHONPATH=cloud .venv312/bin/python -m pytest \
  cloud/services/template_generation/tests -q --tb=short
```

### 保留的已有失败

以下失败均已在未叠加的来源版本复现，不作为本次迁移新增问题，也未为了测试通过而修改既有业务表现。

| 测试 | 失败表现 | 复现基线 |
| --- | --- | --- |
| `test_charging_summary_guards_every_optional_status[names2]` | Text 数量实际 2，断言为 3 | PR256 头提交 |
| `test_weather_care_alert_full_uses_three_section_layout` | 明细高度实际 40，断言为 36 | 最新 main |
| `test_form_validator_allows_empty_stack_children_but_rejects_empty_column_children` | 校验器拒绝空 Stack.children | 最新 main |
| `test_q094_multi_business_search_is_rejected_before_second_layer` | 候选字段排序与固定顺序断言不一致 | 最新 main |
| `test_first_layer_action_is_independent_from_selected_components` | 候选多出主线新增 WeatherOverviewConditionHero | 最新 main |

## 完整提交文件清单

以下路径相对于 `widget_service/cloud/services/template_generation/`；每项列出用途。

- [docs/README.md](README.md)：更新模板子系统文档入口。
- [docs/architecture.md](architecture.md)：同步第一层、Search、Planner、第二层与验证器职责。
- [docs/modules.md](modules.md)：更新模块划分、输入输出和调用链。
- [docs/pr256-main-integration.md](pr256-main-integration.md)：记录本次基线、冲突处理、验证结果及完整提交文件清单。
- [docs/provider-template-capability-checklist.md](provider-template-capability-checklist.md)：同步模板字段、动作和资源覆盖检查项。
- [docs/provider-template-contract.md](provider-template-contract.md)：同步可选字段变换、Support 和图标颜色契约，保留主线多绑定契约。
- [docs/provider-template-e2e-gallery.md](provider-template-e2e-gallery.md)：更新组合画廊规则、交付流程及集成后的 129 项输入规模。
- [docs/provider-template-preview-gallery.md](provider-template-preview-gallery.md)：更新原子预览规格与集成后的 105 个业务模板计数。
- [docs/support-template-action-policy.md](support-template-action-policy.md)：记录各 Support 的业务事件白名单。
- [docs/template-generation-design.md](template-generation-design.md)：更新模板生成设计索引与边界。
- [docs/template-search-planner-contract.md](template-search-planner-contract.md)：记录 Search 与前置 Planner 的输入输出契约。
- [docs/tersel-protocol.md](tersel-protocol.md)：补充模板协议相关说明。
- [engine/advanced/ux_mixed_prompt.py](../engine/advanced/ux_mixed_prompt.py)：将完整候选 Plan、动作和资源约束传给第二层。
- [engine/cardplan/business_actions.py](../engine/cardplan/business_actions.py)：集中定义业务自有事件策略。
- [engine/cardplan/compiler.py](../engine/cardplan/compiler.py)：支持绑定计划验证与显式图标颜色策略，保留主线安全边距及多绑定编译。
- [engine/cardplan/models.py](../engine/cardplan/models.py)：增加完整 Plan 数据模型并保留主线 binding_count。
- [engine/cardplan/preview_dataset.py](../engine/cardplan/preview_dataset.py)：同步业务原子预览样例和图标。
- [engine/cardplan/prompt.py](../engine/cardplan/prompt.py)：同步动作、模板候选和提示词约束。
- [engine/cardplan/provider_bundle.py](../engine/cardplan/provider_bundle.py)：支持 present 可选字段与有值变换、事件及资源验证，保留主线多绑定。
- [engine/cardplan/retrieval_index.py](../engine/cardplan/retrieval_index.py)：将 optionalData 纳入字段覆盖索引。
- [engine/cardplan/template_plan_planner.py](../engine/cardplan/template_plan_planner.py)：按尺寸、字段、主焦点、动作和布局生成最多 3 个完整 Plan。
- [engine/cardplan/template_retrieval.py](../engine/cardplan/template_retrieval.py)：实现数据职责单一的 Search，并适配主线多根数据绑定。
- [engine/pipeline.py](../engine/pipeline.py)：串接第一层、Search、Planner、第二层与计划验证。
- [resources/source/providers/app-usage/provider.json](../resources/source/providers/app-usage/provider.json)：同步应用使用模板注册、字段要求、参数或资源/动作约束。
- [resources/source/providers/app-usage/templates/app-usage-overview.cardtpl](../resources/source/providers/app-usage/templates/app-usage-overview.cardtpl)：迁移应用使用正式模板的布局、文本、绑定、图标与交互调整。
- [resources/source/providers/battery/layer-docs/first-layer.md](../resources/source/providers/battery/layer-docs/first-layer.md)：同步手机电量第一层显式字段与意图说明。
- [resources/source/providers/battery/layer-docs/second-layer.md](../resources/source/providers/battery/layer-docs/second-layer.md)：同步手机电量第二层模板使用、资源和业务动作约束。
- [resources/source/providers/battery/provider.json](../resources/source/providers/battery/provider.json)：同步手机电量模板注册、字段要求、参数或资源/动作约束。
- [resources/source/providers/battery/templates/battery-overview.cardtpl](../resources/source/providers/battery/templates/battery-overview.cardtpl)：迁移手机电量正式模板的布局、文本、绑定、图标与交互调整。
- [resources/source/providers/calendar/layer-docs/first-layer.md](../resources/source/providers/calendar/layer-docs/first-layer.md)：同步日程第一层显式字段与意图说明。
- [resources/source/providers/calendar/layer-docs/second-layer.md](../resources/source/providers/calendar/layer-docs/second-layer.md)：同步日程第二层模板使用、资源和业务动作约束。
- [resources/source/providers/calendar/provider.json](../resources/source/providers/calendar/provider.json)：同步日程模板注册、字段要求、参数或资源/动作约束。
- [resources/source/providers/calendar/templates/schedule-overview.cardtpl](../resources/source/providers/calendar/templates/schedule-overview.cardtpl)：迁移日程正式模板的布局、文本、绑定、图标与交互调整。
- [resources/source/providers/countdown/layer-docs/first-layer.md](../resources/source/providers/countdown/layer-docs/first-layer.md)：同步倒计时第一层显式字段与意图说明。
- [resources/source/providers/countdown/layer-docs/second-layer.md](../resources/source/providers/countdown/layer-docs/second-layer.md)：同步倒计时第二层模板使用、资源和业务动作约束。
- [resources/source/providers/countdown/provider.json](../resources/source/providers/countdown/provider.json)：同步倒计时模板注册、字段要求、参数或资源/动作约束。
- [resources/source/providers/countdown/templates/countdown-overview.cardtpl](../resources/source/providers/countdown/templates/countdown-overview.cardtpl)：迁移倒计时正式模板的布局、文本、绑定、图标与交互调整。
- [resources/source/providers/earphone/layer-docs/second-layer.md](../resources/source/providers/earphone/layer-docs/second-layer.md)：同步耳机第二层模板使用、资源和业务动作约束。
- [resources/source/providers/earphone/provider.json](../resources/source/providers/earphone/provider.json)：同步耳机模板注册、字段要求、参数或资源/动作约束。
- [resources/source/providers/earphone/templates/bluetooth-device-overview.cardtpl](../resources/source/providers/earphone/templates/bluetooth-device-overview.cardtpl)：迁移耳机正式模板的布局、文本、绑定、图标与交互调整。
- [resources/source/providers/health-sport/layer-docs/second-layer.md](../resources/source/providers/health-sport/layer-docs/second-layer.md)：同步运动健康第二层模板使用、资源和业务动作约束。
- [resources/source/providers/health-sport/provider.json](../resources/source/providers/health-sport/provider.json)：同步运动健康模板注册、字段要求、参数或资源/动作约束。
- [resources/source/providers/health-sport/templates/activity-overview.cardtpl](../resources/source/providers/health-sport/templates/activity-overview.cardtpl)：迁移运动健康正式模板的布局、文本、绑定、图标与交互调整。
- [resources/source/providers/health-sport/templates/heart-rate-overview.cardtpl](../resources/source/providers/health-sport/templates/heart-rate-overview.cardtpl)：迁移运动健康正式模板的布局、文本、绑定、图标与交互调整。
- [resources/source/providers/health-sport/templates/sleep-overview.cardtpl](../resources/source/providers/health-sport/templates/sleep-overview.cardtpl)：迁移运动健康正式模板的布局、文本、绑定、图标与交互调整。
- [resources/source/providers/health-sport/templates/workout-overview.cardtpl](../resources/source/providers/health-sport/templates/workout-overview.cardtpl)：迁移运动健康正式模板的布局、文本、绑定、图标与交互调整。
- [resources/source/providers/layout/provider.json](../resources/source/providers/layout/provider.json)：同步固定布局模板注册、字段要求、参数或资源/动作约束。
- [resources/source/providers/layout/templates/layout.cardtpl](../resources/source/providers/layout/templates/layout.cardtpl)：迁移固定布局正式模板的布局、文本、绑定、图标与交互调整。
- [resources/source/providers/system-memory/provider.json](../resources/source/providers/system-memory/provider.json)：同步系统内存模板注册、字段要求、参数或资源/动作约束。
- [resources/source/providers/system-memory/templates/resource-usage-overview.cardtpl](../resources/source/providers/system-memory/templates/resource-usage-overview.cardtpl)：迁移系统内存正式模板的布局、文本、绑定、图标与交互调整。
- [resources/source/providers/weather/layer-docs/second-layer.md](../resources/source/providers/weather/layer-docs/second-layer.md)：同步天气第二层模板使用、资源和业务动作约束。
- [resources/source/providers/weather/provider.json](../resources/source/providers/weather/provider.json)：同步天气模板注册、字段要求、参数或资源/动作约束。
- [resources/source/providers/weather/templates/weather-overview.cardtpl](../resources/source/providers/weather/templates/weather-overview.cardtpl)：迁移天气正式模板的布局、文本、绑定、图标与交互调整。
- [resources/source/themes/2x2-two-support/first-layer.md](../resources/source/themes/2x2-two-support/first-layer.md)：同步双业务 Support 主题的适用业务与选择规则。
- [resources/source/themes/2x2-two-support/theme.json](../resources/source/themes/2x2-two-support/theme.json)：同步双业务 Support 主题的适用业务与选择规则。
- [resources/source/themes/README.md](../resources/source/themes/README.md)：同步主题配置说明。
- [resources/source/themes/fusion-battery-teal/theme.json](../resources/source/themes/fusion-battery-teal/theme.json)：同步电量融球主题配色。
- [resources/source/themes/sleep-night-violet/theme.json](../resources/source/themes/sleep-night-violet/theme.json)：同步睡眠主题配色。
- [test_support/provider_gallery.py](../test_support/provider_gallery.py)：同步双业务组合、业务图标和动作自动化输入。
- [tests/test_bluetooth_hero_content.py](../tests/test_bluetooth_hero_content.py)：回归耳机 Hero 左右标识去重。
- [tests/test_calendar_timeline_geometry.py](../tests/test_calendar_timeline_geometry.py)：验证日程模板最新布局与时间轴几何。
- [tests/test_image_color_policy.py](../tests/test_image_color_policy.py)：验证 Image 显式着色与保留原色策略。
- [tests/test_provider_asset_semantics.py](../tests/test_provider_asset_semantics.py)：验证素材归属、图标语义及单/双业务天气选择规则。
- [tests/test_provider_component_markers.py](../tests/test_provider_component_markers.py)：同步合法业务组件标记断言。
- [tests/test_provider_gallery_batch.py](../tests/test_provider_gallery_batch.py)：验证组合输入、资源、动作及 129 项画廊计数。
- [tests/test_provider_presence_match.py](../tests/test_provider_presence_match.py)：验证 present 按序压缩、有值变换和运行时绑定。
- [tests/test_support_action_policy.py](../tests/test_support_action_policy.py)：验证业务事件白名单、Planner 与编译器一致性。
- [tests/test_support_template_refresh.py](../tests/test_support_template_refresh.py)：验证双行业务模板布局、字段、图标及样例。
- [tests/test_template_contrast.py](../tests/test_template_contrast.py)：将对比度预览覆盖计数同步为 105。
- [tests/test_template_generation.py](../tests/test_template_generation.py)：同步综合链路回归，并适配主线双城/关怀天气用例的一层输出格式。
- [tests/test_template_internal_contracts.py](../tests/test_template_internal_contracts.py)：验证模板内部契约与配置。
- [tests/test_template_plan_planner.py](../tests/test_template_plan_planner.py)：验证 Plan 原子性、主焦点和字段覆盖，新增双根完整/缺字段/错类型 3 项回归。
- [tests/test_template_preview_dataset.py](../tests/test_template_preview_dataset.py)：验证 105 个业务模板及各尺寸、布局预览计数。
- [tests/test_template_retrieval.py](../tests/test_template_retrieval.py)：同步检索职责、模板字段覆盖与可用性回归。
- [tests/test_weather_hero_title.py](../tests/test_weather_hero_title.py)：验证天气可选字段标题行为。
