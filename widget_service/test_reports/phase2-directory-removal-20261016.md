# 一期能力目录移除与 PR 验证记录

日期：2026-10-16。基线：主仓 main `35e478556e2eec03c139983b9d90a3205c4adb71`。
实施位置：独立工作树 `remove-phase-one-registry/CreateMyCard-S`，分支
`codex/remove-phase-one-registry-20261016`。原工作区未提交修改、暂存状态均保留。

## 变更边界

- 主仓已合并 #502 的模板迁移，本次不重复修改 provider 或模板内容。
- 删除一期能力目录的三个文件。Git 可从基线恢复，不删除历史结果文件。
- 二期数据、事件、素材清单内容不变，App [11.7.7.330, 12.0.0.0)、ROM [6.0, 8.0) 区间不变。
- 默认能力版本改为二期，索引移除一期。区间外请求仅在默认回退开关开启时使用二期。
- 参数修复沿用默认配置；配置环境变量覆盖能力保留。部署时应清理显式指向一期的旧覆盖值。
- 历史一期结果编辑时，只将素材恢复使用的清单定向到二期；不改写原结果、摘要及历史版本元数据。
  新生成结果使用本轮实际版本，业务能力和参数仍重新校验；其它未知版本不静默迁移。
  已从二期删除的能力或素材不会因此被放行，可能被移除或返回不支持。
- 协议 Profile 配置不变，标准校验规则不变。
- 根目录 `docs/云侧方案设计.md` 仍包含旧双版本说明；按本任务只操作 widget_service 的边界，
  未修改根目录文档，应由方案维护者同步为已确认的只保留二期策略。

## 全部提交文件及用途

以下路径均相对于仓库根目录。

| 文件 | 用途 |
| --- | --- |
| widget_service/cloud/data/capabilities/app-11.7.5.205_rom-6.0/asset_capabilities.json | 删除一期素材清单 |
| widget_service/cloud/data/capabilities/app-11.7.5.205_rom-6.0/data_capabilities.json | 删除一期数据清单 |
| widget_service/cloud/data/capabilities/app-11.7.5.205_rom-6.0/event_capabilities.json | 删除一期事件清单 |
| widget_service/cloud/data/capabilities/registry_ranges.json | 移除一期匹配项，保留二期原区间 |
| widget_service/cloud/config/config.py | 默认回退版本切到二期 |
| widget_service/cloud/services/source_artifact_repository.py | 历史一期素材恢复兼容及日志 |
| widget_service/cloud/services/template_generation/tests/test_image_color_policy.py | 素材测试读取二期 |
| widget_service/cloud/services/template_generation/tests/test_retired_app_usage.py | 下线能力测试只检查在用二期 |
| widget_service/tests/test_phase_two_registry_defaults.py | 新增 111 个版本、回退、模板路径、历史素材恢复测试 |
| widget_service/tests/test_service_units.py | 能力选择、参数、过滤及校验测试迁到二期 |
| widget_service/tests/test_argument_json_recovery.py | 参数修复测试使用二期清单 |
| widget_service/tests/test_generation_preflight.py | 生成前检查测试使用二期清单 |
| widget_service/tests/test_compact_dsl_interface_retry.py | 接口重试测试元数据切到二期 |
| widget_service/tests/test_compact_validation_repair_integration.py | 修复测试元数据切到二期 |
| widget_service/tests/test_compact_validation_restoration_integration.py | 素材恢复测试元数据切到二期 |
| widget_service/tests/test_asset_mapping_generation.py | 一期/二期历史结果连续编辑两轮，断言新版本与原文件不变；隔离主题阶段 |
| widget_service/tests/test_capability_overview_descriptions.py | 旧 App 请求回退到二期素材描述 |
| widget_service/README.md | 更新默认版本、版本区间和历史素材恢复说明 |
| widget_service/docs/method_usage.md | 更新使用与部署迁移说明 |
| widget_service/docs/latest_design_diff.md | 更新版本策略差异说明 |
| widget_service/docs/generateWidgetCard数据流.md | 更新回退示例 |
| widget_service/test_reports/phase2-directory-removal-20261016.md | 本记录：文件清单、验证结果和已知失败 |

## 实际验证

- 未修改基线的同范围回归：475 个，459 通过、15 失败、1 跳过。
- 最终同范围加新增回归：587 个，577 通过、9 失败、1 跳过。失败集合是基线失败集合的子集，无新增失败。
- 参数恢复、生成前检查、接口重试、校验修复、素材恢复及版本专项：290 通过。
- service_units 中 registry / capability_overview / capability_schemas / self_contained /
  generation_stops_before_model_when_event_data_dependency_is_missing：65 通过、1 跳过、190 未选择。
- 13 个修改或新增 Python 文件 Ruff 检查通过，compileall 通过。
- git diff --check 通过；二期三个清单的 git diff 为空。
- provider 的 dataSchema 路径均为现存二期文件（测试自动遍历），一期不再有运行配置引用。
- 未跑全仓测试、远端模型调用、真实端侧渲染；此次是注册表退役，不宣称整体项目测试全绿。

回归命令（在 widget_service 下执行）：

```powershell
D:/Python312/python.exe -m pytest tests/test_phase_two_registry_defaults.py tests/test_service_units.py tests/test_asset_mapping_generation.py tests/test_compact_validation_repair_integration.py tests/test_compact_validation_restoration_integration.py tests/test_argument_json_recovery.py tests/test_generation_preflight.py tests/test_compact_dsl_interface_retry.py tests/test_capability_overview_descriptions.py cloud/services/template_generation/tests/test_image_color_policy.py cloud/services/template_generation/tests/test_retired_app_usage.py -q --tb=no --junitxml=test_reports/phase2-delete-final.xml
```

## 剩余 9 个已有失败

| 测试 | 原因（基线已复现） |
| --- | --- |
| test_service_units.py::test_anyio_thread_pool_uses_configured_capacity | 默认模型路由期待 deepseek_platform，实际 llmclient |
| test_service_units.py::test_design_compact_few_shots_are_disabled_by_default_and_can_be_enabled | 期待默认关闭，配置实际开启 |
| test_service_units.py::test_design_compact_edit_prompt_contains_previous_design_token | 旧断言禁止 DSL 一词，当前提示词包含该词 |
| test_service_units.py::test_model_runtime_collects_llmclient_stream | HTTP 路由走 SOCKS，环境缺少 socksio；原 mock 与当前路由不一致 |
| test_service_units.py::test_design_converter_expands_latest_design_tokens | 旧组件输入不符合当前转换协议 |
| test_service_units.py::test_missing_action_unit_on_click_enters_validation_repair | 当前先报告 ActionUnit 不支持，旧断言期待 onClick 缺失 |
| test_capability_overview_descriptions.py::test_short_description_preserves_selection_boundaries | 断言中的旧素材 ID 已不在当前清单 |
| test_image_color_policy.py::test_two_support_final_a2ui_preserves_weather_template_fill[False-icon_weather_thermometer.svg] | 温度计素材已从当前清单删除，旧测试仍查找 |
| test_image_color_policy.py::test_two_support_final_a2ui_preserves_weather_template_fill[True-icon_weather_thermometer.svg] | 同上 |

本次顺带使 6 个原失败恢复：两项二期能力测试按现有能力集合校验；4 项素材生成测试使用已有
isolated_theme_stage fixture 隔离本测试不负责的异步主题阶段，不改变生产主题逻辑。
