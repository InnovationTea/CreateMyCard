# 2026-09-06 Support 模板调整配套说明

后续经用户确认，已完成端侧同步与 HAP 安装，见
[安装及实机启动记录](provider-gallery-hap-install-2026-09-06.md)。下文保留此前文件验证阶段的范围和结果。

## 本轮范围

以用户在 `38f9e4bf` 后修改的 10 个模板文件为准，保留 TwoSupport 两个等权 Row 槽位及各业务的
字号、间距、内边距和 24vp 图标设计。配置按实际展示字段更新，不通过回退用户样式解决契约不一致。

| 业务 | 当前模板变化与数据规则 |
| --- | --- |
| 手机电量 | 44vp 电量环与主辅文本；数值电量存在时显示环及百分比，否则使用带单位电量文本，再缺失则显示“电量信息异常”；充电状态必需 |
| 日程 | 原通用 Support 拆为时间段、地点、开始时间、日期四种；标题必需，辅助信息按模板分别绑定；时间段的结束时间仍可选，缺失时不保留分隔符 |
| 耳机 | 新增 ChargeSupport，展示盒或整体电量、充电状态及 44vp 环；独立于左右耳电量 Support，图标分别使用充电盒与耳机本体语义 |
| 心率 | 收敛为 HeartRateOverviewSupport，心率值与单位同排，支持可选 heartIcon；移除三个已删除的旧 Support 注册，不恢复旧样式 |
| 睡眠 | 只展示睡眠时长和说明，不再要求或宣称展示睡眠得分；保留可选睡眠图标及段落点击 |
| 训练 | 主信息为运动热量，辅助为时长及可选运动类型；同步主次数据，不把主焦点继续误标为时长 |
| 天气 | 基础温度、紫外线、感冒风险分成三种 Support；城市/区县可选并保留 location 兜底，仅基础温度形态有可选天气状态图标 |

新感冒风险模板沿用用户声明的 `WeatherOverviewTemperaturecoldLevelSupport@1`，
不擅自更改 ID。天气图标仍表达天气状态，不使用温度计；多云样例缺少合法资源时省略。
电池绿叶素材表达省电模式，普通未充电样例不借用该图标；耳机盒素材仅用于盒或整体电量模板。

## 配套修复边界

- 补齐模板声明和条件块：batteryIcon、location 拼写、日程条件结束以及可选数据引用保护。
- 睡眠恢复业务标记及根节点 onClick；训练修正 onClick 大小写。操作数仍由自动化覆盖 0/1/2。
- 心率 Row 移除仅 Stack 支持的 alignContent；新增 ChargeSupport 纳入耳机盒电量及充电状态校验，
  仍拒绝缺少任一必选字段的调用，不以新增模板名绕过状态校验。
- 新增模板注册、删除悬空条目，同步主次/可选字段、素材语义、两层规则与当前能力清单。
- 画廊按当前模板清单重新展开，不复用旧数量；此前生成成功的目录保留不覆盖。
- 本轮只验证文件，不推送 PR、不同步端侧资源、不构建或安装 HAP。

## 验证记录

### 执行环境与产物

- 工作树：`/Users/yansf/workspace/GenerateUI/.codex-worktrees/provider-gallery-two-support-20260906`，
  分支 `codex/provider-gallery-two-support-20260906`；本轮未提交。
- Python：原工作区 `widget_service/.venv312/bin/python`，本轮业务代码均从上述隔离工作树加载。
- HTTP 使用已有本地验证适配，不把原工作区 HTTP 传输补丁带入本轮源码；有效配置为
  `deepseek_http`、`deepseek-v4-flash`、mock=false、fallback=false；请求 prdVer 为 `11.7.5.206`。
- [原子预览清单](../test/template_preview_refresh_20260906/manifest.json)：96 个模板，
  其中 85 个 2x2、11 个 2x4、17 个 Support。
- [最终 HTTP 画廊清单](../test/provider_gallery_output_refresh_verified_20260906/manifest.json)：
  121 个自动化场景，107 成功、0 失败、14 缺失、0 未生成。产物位于忽略目录，不作为手写源文件修改。
- 初次 HTTP 批跑为 104 成功、3 失败、14 缺失，三个失败均为新 ChargeSupport 未进入状态校验白名单。
  修复后在新的 `provider_gallery_output_refresh_verified_20260906` 目录完整重跑成功，保留首轮目录作排障证据，
  不覆盖此前交付的 `provider_gallery_output_assets_20260906`。

### 检查结果

| 检查 | 实际结果 |
| --- | --- |
| 本轮 13 个 Python 修改/新增文件 Ruff | 全部通过 |
| CardPlan Bundle `--check` | 通过，无生成物漂移 |
| `git diff --check` | 通过 |
| 全量 `template_generation/tests` | 655 通过、2 个既有失败，共 657 项 |
| 最终相关链路定向回归 | 86 通过；包含新增 23 项 Support 回归 |
| 原子预览 | 96 份 A2UI 全部编译，消息/字段层级/对比度由相关测试覆盖 |
| HTTP 画廊文件复核 | 107 份 JSON 均为三条 v0.9 消息；组件 ID 唯一、child 引用存在、无业务标记泄漏 |
| 全量画廊素材复核 | 58 个 Image 均能在指定版本的正式 asset_capabilities.json 找到 |
| TwoSupport 文件复核 | 45 份成功文件、90 个等权 Row 业务槽位；全为非融球 |
| TwoSupport 图标/操作 | 39 个图标全部与所在业务匹配，无预期图标遗漏；45 次点击按 0/1/2 场景准确归属 |

14 个缺失场景来自数据能力未注册（应用时长、内存）或正式模板形态缺失（日程/倒计时 Compact、
内存 Hero），不是本轮生成失败。双业务分组共有 51 个场景，其中 45 成功、6 缺失；
继续保留 17 个模板组的 0/1/2 操作自动化差异。显示去重规则仍是每组一张，本轮未同步到端侧验证显示数量。

全量回归保留的两个既有失败，本轮未修改其行为：

1. `test_provider_component_markers.py::test_charging_summary_guards_every_optional_status[names2]`：
   仅健康状态时旧断言期望 3 个 Text，当前模板输出 2 个。
2. `test_template_generation.py::test_form_validator_allows_empty_stack_children_but_rejects_empty_column_children`：
   空 Stack 被现有 Form 校验器拒绝，与旧测试期望冲突。

最终定向测试覆盖文件：`test_support_template_refresh.py`、`test_provider_asset_semantics.py`、
`test_provider_gallery_batch.py`、`test_template_preview_dataset.py`、`test_template_contrast.py`、
`test_template_plan_planner.py`。未执行端侧构建、安装或实机视觉测试，文件验证不等同于端侧渲染验收。

## 文件清单与用途

路径均相对于 `template_generation/`。表中明确区分配套修改与仅保留的用户样式。

| 文件 | 用途 |
| --- | --- |
| [docs/provider-support-refresh-2026-09-06.md](../docs/provider-support-refresh-2026-09-06.md) | 本轮变更、逐文件清单、真实验证结果及遗留项 |
| [docs/provider-template-contract.md](../docs/provider-template-contract.md) | 96 个业务模板、17 个 Support 及等权 Row 槽位约束 |
| [docs/provider-template-capability-checklist.md](../docs/provider-template-capability-checklist.md) | 同步主次/可选字段、模板增删和分组数量 |
| [docs/provider-template-e2e-gallery.md](../docs/provider-template-e2e-gallery.md) | 121 个自动化场景、分业务素材及显示去重口径 |
| [docs/provider-template-preview-gallery.md](../docs/provider-template-preview-gallery.md) | 96 个原子预览及 Support 素材说明 |
| [engine/cardplan/compiler.py](../engine/cardplan/compiler.py) | 将 ChargeSupport 纳入耳机盒电量/充电状态校验 |
| [engine/cardplan/prompt.py](../engine/cardplan/prompt.py) | 增加 earphone-case 素材语义识别 |
| [engine/cardplan/preview_dataset.py](../engine/cardplan/preview_dataset.py) | 补齐日历/心率素材、日期/电量样例，区分耳机本体与盒 |
| [resources/source/providers/battery/provider.json](../resources/source/providers/battery/provider.json) | 可选电量字段、batteryIcon 声明语义及描述 |
| [resources/source/providers/calendar/provider.json](../resources/source/providers/calendar/provider.json) | 以四种 Support 替换通用 Support |
| [resources/source/providers/earphone/provider.json](../resources/source/providers/earphone/provider.json) | 注册 ChargeSupport 及充电盒素材语义 |
| [resources/source/providers/health-sport/provider.json](../resources/source/providers/health-sport/provider.json) | 删除三个旧心率 Support，修正睡眠覆盖与训练主焦点 |
| [resources/source/providers/weather/provider.json](../resources/source/providers/weather/provider.json) | 三种天气 Support 的主次/可选字段及图标能力 |
| [resources/source/providers/battery/layer-docs/first-layer.md](../resources/source/providers/battery/layer-docs/first-layer.md) | 明确可选电量不能替代用户显式字段 |
| [resources/source/providers/battery/layer-docs/second-layer.md](../resources/source/providers/battery/layer-docs/second-layer.md) | 数值环、文本电量、异常提示降级及可选素材 |
| [resources/source/providers/calendar/layer-docs/first-layer.md](../resources/source/providers/calendar/layer-docs/first-layer.md) | 四种 Support 独立覆盖，不合并候选字段凑槽位 |
| [resources/source/providers/calendar/layer-docs/second-layer.md](../resources/source/providers/calendar/layer-docs/second-layer.md) | 四种 Support 的选择、字段及可选图标规则 |
| [resources/source/providers/earphone/layer-docs/second-layer.md](../resources/source/providers/earphone/layer-docs/second-layer.md) | 充电 Support、耳机本体与耳机盒图标隔离 |
| [resources/source/providers/health-sport/layer-docs/second-layer.md](../resources/source/providers/health-sport/layer-docs/second-layer.md) | 四个现有 Support 的字段、图标与内部事件规则 |
| [resources/source/providers/weather/layer-docs/second-layer.md](../resources/source/providers/weather/layer-docs/second-layer.md) | 三种 Support、城市兜底及无图标风险形态 |
| [resources/source/providers/battery/templates/battery-overview.cardtpl](../resources/source/providers/battery/templates/battery-overview.cardtpl) | 保留用户样式；声明 batteryIcon 并保护可选数值环 |
| [resources/source/providers/calendar/templates/schedule-overview.cardtpl](../resources/source/providers/calendar/templates/schedule-overview.cardtpl) | 保留用户四种形态；补齐条件结束和结束时间缺失分支 |
| [resources/source/providers/health-sport/templates/heart-rate-overview.cardtpl](../resources/source/providers/health-sport/templates/heart-rate-overview.cardtpl) | 保留用户合并形态；移除 Row 不支持的 alignContent |
| [resources/source/providers/health-sport/templates/sleep-overview.cardtpl](../resources/source/providers/health-sport/templates/sleep-overview.cardtpl) | 保留用户样式；移除无显示的得分绑定并恢复标记/点击 |
| [resources/source/providers/health-sport/templates/workout-overview.cardtpl](../resources/source/providers/health-sport/templates/workout-overview.cardtpl) | 保留用户样式；修正 onClick 大小写 |
| [resources/source/providers/weather/templates/weather-overview.cardtpl](../resources/source/providers/weather/templates/weather-overview.cardtpl) | 保留用户样式及新 ID；修正 UV 模板 location 参数拼写 |
| [resources/source/providers/health-sport/templates/activity-overview.cardtpl](../resources/source/providers/health-sport/templates/activity-overview.cardtpl) | 仅保留用户样式改动，未额外修改 |
| [resources/source/providers/earphone/templates/bluetooth-device-overview.cardtpl](../resources/source/providers/earphone/templates/bluetooth-device-overview.cardtpl) | 仅保留用户新增充电形态，未额外修改 |
| [resources/source/providers/countdown/templates/countdown-overview.cardtpl](../resources/source/providers/countdown/templates/countdown-overview.cardtpl) | 仅保留用户内边距改动，未额外修改 |
| [resources/source/providers/layout/templates/layout.cardtpl](../resources/source/providers/layout/templates/layout.cardtpl) | 仅保留用户两个等权 Row 槽位，未额外修改 |
| [test_support/provider_gallery.py](../test_support/provider_gallery.py) | 更新双业务素材映射，时间段画廊补充结束时间输入 |
| [tests/test_support_template_refresh.py](../tests/test_support_template_refresh.py) | 新增 23 项模板清单、可选分支、点击、状态/布局和预览回归 |
| [tests/test_provider_asset_semantics.py](../tests/test_provider_asset_semantics.py) | 14 个素材槽位及耳机/充电盒、四种日程的跨业务隔离 |
| [tests/test_provider_component_markers.py](../tests/test_provider_component_markers.py) | 补充新天气感冒风险模板的业务标记预期 |
| [tests/test_provider_gallery_batch.py](../tests/test_provider_gallery_batch.py) | 121 总场景及 51 个 Support 操作场景的计数与覆盖 |
| [tests/test_template_contrast.py](../tests/test_template_contrast.py) | 96 份原子预览的对比度校验 |
| [tests/test_template_generation.py](../tests/test_template_generation.py) | 模板总数、日程入口、环形进度、图标着色及用户样式断言 |
| [tests/test_template_plan_planner.py](../tests/test_template_plan_planner.py) | 更新日程 Support ID 的完整规划测试 |
| [tests/test_template_preview_dataset.py](../tests/test_template_preview_dataset.py) | 96/17 个模板计数及电量无主数据契约 |
| [tests/test_template_retrieval.py](../tests/test_template_retrieval.py) | 新增日程候选后仍拒绝不满足单业务 Full 的组合 |
