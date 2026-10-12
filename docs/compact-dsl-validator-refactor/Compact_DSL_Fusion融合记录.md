# Compact DSL 与 Fusion 融合记录

- 日期：2026-10-12
- 当前分支合入：main `a19fef3ae101d2be805271e7249b05af127052bd`；按用户要求排除 PR497 的颜色行为变更
- 分类迁移行为基线：main `a42d86a523fb5a50971996bddb14cfec352fcc4c`
- 首次融合基线：main `030b0aa2c2bf08fa4c911b6d24c9d252b8cce9fa`
- 原重构分支：`c3fa7eda`
- 状态：代码融合、文档更新与确定性回归完成；提交与发布状态以 Git 历史和 PR 为准。

> 下方融合记录保留当时的规则与回归结果；当前颜色规则以「PR497 颜色规则更正」及文末标题图标融合补充为准。

## 融合原则

以当前主线的通过/失败判断、错误文本、顺序、去重、异常和 warning 为行为基准。
语法／语义分类及诊断基础设施继续保留；共享绑定、组件展开、视觉和布局合同保持单一实现。
不复活被删除或已退出公共入口的规则；无可靠来源映射时，不推测高阶组件展开节点的原文位置。
转换器保持现有职责，外部模块返回的纯字符串错误先按原文透传，不解析英文错误文本生成结构化事实。

## 规则去向

| 范围 | 去向 | 执行边界 |
|---|---|---|
| 表达式、父子结构、点击结构 | syntax | 保留主线调用顺序 |
| 首帧数据、进度类型、高阶组件绑定 | semantic/bindings | 高阶绑定先于展开，复用共享注册表 |
| 数据声明与值类型 | semantic/cross_file | 保留原数据遍历及去重 |
| 事件候选、背景素材 | semantic/effective | 不恢复已删除的 Image/ActionUnit 素材检查 |
| 指标标签、布尔值、时间范围、进度读数对象 | semantic/display | 作用于展开结果，保留 Recipe 特例 |
| 参考区域与最小高度 | semantic/layout/geometry | 保留主线 Occupancy 和固定设计高度 |
| 正式布局 | 现有 compact_layout_runtime | 展开前匹配，保留完整 Alternatives |
| 高阶 Props 与展开 | 现有 compact_high_level_components | 不复制合同，不扩大转换器职责 |
| 主文字辅助检查 | 兼容辅助模块 | 只保留直接调用，公共入口不执行 |
| 旧 W9/S4/W1、双动作、素材染色和 fusion 启发式 | 退出当前重构包 | 不声称所有旧规则均已被等价替代，独立需求另行评审 |

## 链路兼容

公开 API 同时保留主线 protocol_profile、layout_scope、enforce_model_component_types 和重构的
original_source、repair_context。绑定修复原文用于位置核对，展开前后树分别建立索引。
内部诊断与模型展示分离；外层通用错误码、Plan 独立错误码及旧错误记录均兼容。
模型格式化只修改副本；默认建议按错误码配置，动态建议函数仍是可选接口。
保留 Plan 两轮调用、原先的提前返回、Trace、修复历史、组合恢复和素材还原顺序。
旧 REPAIR_SYSTEM_PROMPT.md 接受主线删除，只向新 repair.md 增加诊断阅读说明。

## 验证策略

先对未修改 main 运行相关回归并捕获真实校验调用；融合后以相同输入逐条比对异常、文案、顺序和 warning。
主线相关回归基线：770 passed、39 failed、1 skipped、26 subtests passed。
已有失败与新增失败按测试 ID 对比，不将既有失败记作通过。
补充新诊断、展开来源、提示词历史/组合上下文、规则归属与无旧依赖检查。
运行 Ruff、相关测试与差异空白检查；真实模型效果、端侧截图和外部 CodeCheck 单独说明。

## 当前模块与诊断边界

当前有 30 个结构化发布位置、30 个活动错误码。保留旧含义的错误码，新增模型组件白名单及进度读数对象错误码。
共享高阶组件绑定合同、正式布局匹配、解析/展开失败、标题合同，以及现有 eventCount 文案仍走纯字符串路径；
它们不是未执行的规则，也不会因没有 compactDiagnostics 而被丢弃。DiagnosticCollector.extend 逐条记录布局错误。
旧主文字辅助函数保留直接调用，不参与公共入口，位置在 compatibility/hero.py。

| 模块 | 职责 |
|---|---|
| api.py | 主线顺序编排、展开前后上下文及异常装配 |
| flows/contracts.py | 组合组件结构、事件和数据检查，保留原交错顺序 |
| syntax/components.py | 父子结构、点击形状和模型组件白名单 |
| syntax/expressions.py | 表达式、PathBinding 写法与位置候选 |
| semantic/bindings.py | 首帧数据、进度字段类型和共享高阶绑定合同入口 |
| semantic/cross_file.py | 数据声明、数据值类型与未使用能力 warning |
| semantic/effective.py | 背景素材及事件候选范围 |
| semantic/display.py | 文本含义、动作提示、进度与读数对象一致性 |
| semantic/layout/geometry.py | 区域参考预算、最小高度、Occupancy |
| constants.py、schema.py、text.py | 当前规则共享的常量、路径解析和文本辅助，不复制运行时合同 |
| context.py、source_locations.py | 原文与展开树分别索引；无法定位时省略原文位置 |
| diagnostics.py、model_feedback.py | 内部记录与模型文字分离，扩展 expanded 事实来源 |
| repair_guidance.py、rule_catalog.py | 可选建议接口及当前活动错误码 |

## 旧测试处理

87 组固定输入来自未修改 main 的实际回归调用，包含公开入口的参数和成功/异常结果。
它们替换融合前的 82 组基线。旧 91 组私有函数样例及 W9 专项测试针对已退出的流程，撤下相应文件；
当前主线原有测试全部保留（含已有失败），不修改断言以掩盖主线问题。
架构测试重新核对当前 30 个发布位置和单向依赖；诊断、两条修复入口和 Fusion 边界测试独立维护。

## 主线已有失败清单

以下失败在未修改 main 已出现；最终验证逐项比较测试 ID 与失败原因。两个错误对象的展开内容因新增诊断变化；其他差异仅涉及运行时地址和外部请求 ID。此表不代表问题已解决。

| 测试 | 基线失败摘要 |
|---|---|
| `tests.test_compact_dsl_validator.test_rejects_sparse_w9_without_vertical_center_and_layout_weight` | Failed: DID NOT RAISE CompactDslValidationError |
| `tests.test_compact_dsl_validator.test_rejects_sparse_w9_with_legacy_backboard_geometry` | Failed: DID NOT RAISE CompactDslValidationError |
| `tests.test_compact_dsl_validator.test_rejects_centered_single_value_hero_without_safe_box` | Failed: DID NOT RAISE CompactDslValidationError |
| `tests.test_compact_dsl_validator.test_rejects_centered_single_value_hero_that_exceeds_width_pressure` | Failed: DID NOT RAISE CompactDslValidationError |
| `tests.test_compact_dsl_validator.test_rejects_centered_single_value_hero_that_exceeds_height_pressure` | AssertionError: Regex pattern did not match. |
| `tests.test_compact_dsl_validator.test_rejects_large_hero_for_peer_metrics_on_150vp_card` | Failed: DID NOT RAISE CompactDslValidationError |
| `tests.test_compact_hero_typography.test_template_keeps_other_compact_validations[empty-non-empty]` | AssertionError: Regex pattern did not match. |
| `tests.test_compact_hero_typography.test_non_template_formatted_readout_keeps_original_contract[expression]` | AssertionError: assert False is ('expression' != 'none') |
| `tests.test_compact_hero_typography.test_non_template_formatted_readout_keeps_original_contract[inherited-width]` | AssertionError: assert False is ('inherited-width' != 'none') |
| `tests.test_compact_hero_typography.test_non_template_formatted_readout_keeps_original_contract[percent-description]` | AssertionError: assert False is ('percent-description' != 'none') |
| `tests.test_compact_plan.test_processor_reports_missing_plan_fact_with_dedicated_code` | assert 2 == 1 |
| `tests.test_fusion_ball_version_gate.test_design_processor_copies_task_spec_app_version_into_profile` | assert not (QualityIssue(stage='validation', code='COMPACT_DSL_VALIDATION_FAILED', message='component title: Text is converter-internal and cannot be generated directly; use a semantic Compact component.', severity='error', prompt_context={}),) |
| `tests.test_generation_trace_recorder.test_compact_mock_flow_records_intermediate_artifacts` | AssertionError: assert <GenerationStatus.FAILED: 'failed'> in {<GenerationStatus.DEGRADED: 'degraded'>, <GenerationStatus.SUCCESS: 'success'>} |
| `tests.test_generation_trace_recorder.test_compact_flow_does_not_write_trace_when_disabled` | AssertionError: assert <GenerationStatus.FAILED: 'failed'> in {<GenerationStatus.DEGRADED: 'degraded'>, <GenerationStatus.SUCCESS: 'success'>} |
| `tests.test_generation_trace_recorder.test_upload_failure_keeps_trace_terminal_state` | Failed: DID NOT RAISE ArtifactUploadError |
| `tests.test_service_units.test_anyio_thread_pool_uses_configured_capacity` | AssertionError: assert 'llmclient' == 'deepseek_platform' |
| `tests.test_service_units.test_design_compact_few_shots_are_disabled_by_default_and_can_be_enabled` | AssertionError: assert True is False |
| `tests.test_service_units.test_phase_two_version_returns_phase_two_capability_overview` | AssertionError: assert False |
| `tests.test_service_units.test_phase_two_version_returns_phase_two_capability_schemas` | AssertionError: assert ['GetCurrentT...ilyMostUsage'] == ['GetMemoData...ilyMostUsage'] |
| `tests.test_service_units.test_design_compact_edit_prompt_contains_previous_design_token` | AssertionError: assert 'DSL' not in 'design rule...没有发生无意义漂移。\n' |
| `tests.test_service_units.test_model_runtime_collects_llmclient_stream` | 外部模型 HTTP 401 认证失败；最终回归不重复执行此项。 |
| `tests.test_service_units.test_design_converter_expands_latest_design_tokens` | custom.a2ui_model_client.A2UIModelGenerationError: design DSL conversion failed |
| `tests.test_service_units.test_model_failure_skips_validator_and_artifact_store[empty-generate_widget_card_compact_dsl]` | TypeError: test_model_failure_skips_validator_and_artifact_store.<locals>.fail_generate() got an unexpected keyword argument 'suppress_prompt_log' |
| `tests.test_service_units.test_model_failure_skips_validator_and_artifact_store[exception-generate_widget_card_compact_dsl]` | TypeError: test_model_failure_skips_validator_and_artifact_store.<locals>.fail_generate() got an unexpected keyword argument 'suppress_prompt_log' |
| `tests.test_service_units.test_design_compact_validation_error_retries_then_does_not_save` | AssertionError: assert 'A2UI_GENERATION_FAILED' == 'VALIDATION_FAILED' |
| `tests.test_service_units.test_missing_action_unit_on_click_enters_validation_repair` | AssertionError: assert <GenerationSt...LED: 'failed'> == <GenerationSt...SS: 'success'> |
| `tests.test_service_units.test_conversion_failure_repair_uses_latest_source_format[generate_widget_card_compact_dsl-["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":20,"clip":true,"backgroundColor":"comp_background_primary"},["foreground"]]\n["foreground","Column",{"width":"matchParent","height":"matchParent","padding":12,"alignItems":"start","justifyContent":"start"},["title"]]\n["title","SecondaryBody",{"role":"body","items":[{"value":"Design Compact Mock","maxLines":1}],"fontColor":"#FF1F4799"}]\n["/ui/state","ready"]\n-design-compact-dsl]` | AssertionError: assert <GenerationSt...LED: 'failed'> == <GenerationSt...SS: 'success'> |
| `tests.test_service_units.test_source_format_validation_error_repairs_original_source_dsl[generate_widget_card_compact_dsl-["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":20,"clip":true,"backgroundColor":"comp_background_primary"},["foreground"]]\n["foreground","Column",{"width":"matchParent","height":"matchParent","padding":12,"alignItems":"start","justifyContent":"start"},["title"]]\n["title","SecondaryBody",{"role":"body","items":[{"value":"Design Compact Mock","maxLines":1}],"fontColor":"#FF1F4799"}]\n["/ui/state","ready"]\n-design-compact-dsl]` | AssertionError: assert <GenerationSt...LED: 'failed'> == <GenerationSt...SS: 'success'> |
| `tests.test_service_units.test_quality_repair_distinguishes_source_and_artifact_validation[generate_widget_card_compact_dsl-["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":20,"clip":true,"backgroundColor":"comp_background_primary"},["foreground"]]\n["foreground","Column",{"width":"matchParent","height":"matchParent","padding":12,"alignItems":"start","justifyContent":"start"},["title"]]\n["title","SecondaryBody",{"role":"body","items":[{"value":"Design Compact Mock","maxLines":1}],"fontColor":"#FF1F4799"}]\n["/ui/state","ready"]\n-design-compact-dsl]` | IndexError: list index out of range |
| `tests.test_service_units.test_source_format_validation_repair_stops_at_configured_maximum[generate_widget_card_compact_dsl-["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":20,"clip":true,"backgroundColor":"comp_background_primary"},["foreground"]]\n["foreground","Column",{"width":"matchParent","height":"matchParent","padding":12,"alignItems":"start","justifyContent":"start"},["title"]]\n["title","SecondaryBody",{"role":"body","items":[{"value":"Design Compact Mock","maxLines":1}],"fontColor":"#FF1F4799"}]\n["/ui/state","ready"]\n-design-compact-dsl]` | IndexError: list index out of range |
| `tests.test_service_units.test_unknown_processor_exception_does_not_trigger_model_repair` | Failed: DID NOT RAISE RuntimeError |
| `tests.test_service_units.test_unknown_validator_exception_does_not_trigger_model_repair` | Failed: DID NOT RAISE RuntimeError |
| `tests.test_service_units.test_source_format_warning_does_not_trigger_repair[generate_widget_card_compact_dsl-design-compact]` | AssertionError: assert <GenerationSt...LED: 'failed'> == <GenerationSt...SS: 'success'> |
| `tests.test_service_units.test_conversion_failure_does_not_repair_when_switch_is_disabled[generate_widget_card_compact_dsl]` | TypeError: test_conversion_failure_does_not_repair_when_switch_is_disabled.<locals>.generate_invalid() got an unexpected keyword argument 'suppress_prompt_log' |
| `tests.test_service_units.test_conversion_repair_stops_at_configured_maximum[generate_widget_card_compact_dsl]` | assert 2 == 3 |
| `tests.test_asset_url_mapper.test_mapping_covers_expanded_action_icon` | services.compact_high_level_components.CompactDslConversionError: action: PillButton does not allow actionInk, actionSurface. |
| `tests.test_asset_url_mapper.test_final_validator_recognizes_exact_mapped_asset[resources/base/media/drop_1.svg-True]` | services.compact_high_level_components.CompactDslConversionError: action: PillButton does not allow actionInk, actionSurface. |
| `tests.test_asset_url_mapper.test_final_validator_recognizes_exact_mapped_asset[https://hagres-drcn.dbankcdn.com/assets/drop_1.svg?version=1-True]` | services.compact_high_level_components.CompactDslConversionError: action: PillButton does not allow actionInk, actionSurface. |
| `tests.test_asset_url_mapper.test_final_validator_recognizes_exact_mapped_asset[https://hagres-drcn.dbankcdn.com/assets/drop_1.svg?version=1-other-False]` | services.compact_high_level_components.CompactDslConversionError: action: PillButton does not allow actionInk, actionSurface. |

## 最终验证结果

- 融合前 main：770 passed、39 failed、1 skipped、26 subtests passed。
- 最终 21 个测试文件：911 passed、38 failed、1 skipped、1 deselected、26 subtests passed。
- 38 个失败 ID 与主线基线一致，无新增失败；1 个 deselected 是基线已确认 HTTP 401 的外部模型测试，
  避免重复外部请求。原有失败未在本次顺带修复，具体原因见上表。
- 新增／迁移的五个专项测试文件共 141 passed，包含 87 个公开行为固定样例、39 个诊断测试、
  2 个架构测试、3 个实际修复入口测试、10 个 Fusion 边界测试。
- 相对 main 新增或修改的 36 个 Python 文件全部通过 Ruff；本次差异的 `git diff main --check` 通过。
- 6 个 Git 冲突均已解决，无残留冲突标记；保留 main 的共享组件、Recipe、布局合同及执行顺序。
- 合并整体暂存差异中，主线原有 14 处文件末尾空行告警未改动；它们不在相对 main 的重构差异内。
- 未运行仓库全部测试、外部 CodeCheck、真实模型修复效果评测或端侧截图验收；不据单元测试推断视觉效果。

验证发现并修正了测试隔离问题：在线入口测试改为 patch 实际处理器单例，避免前序测试留下实例方法后
导致类级 patch 失效。这是测试组织修正，不改变生成链路的实际处理器选择。

## 逐文件变更清单

以下以融合后的 main 为比较基准，包含原重构中继续保留的文件，排除单纯随 main 合入的其他业务变更。
相对于原重构分支撤下的旧模块另见下一节。

| 文件 | 用途 |
|---|---|
| [AGENTS.md](../../AGENTS.md) | 保留原重构的归属检查流程，本轮不新增协议细节 |
| [docs/compact-dsl-validator-refactor/Compact_DSL_Fusion融合记录.md](../../docs/compact-dsl-validator-refactor/Compact_DSL_Fusion融合记录.md) | 记录迁移去向、已有失败、验证结果和逐文件清单 |
| [docs/compact-dsl-validator-refactor/Compact_DSL校验器重构方案_v3.md](../../docs/compact-dsl-validator-refactor/Compact_DSL校验器重构方案_v3.md) | 补充当前生效约定，将旧目录及数量标为历史快照 |
| [docs/compact-dsl-validator-refactor/Compact_DSL现有校验规则分类清单_v1.md](../../docs/compact-dsl-validator-refactor/Compact_DSL现有校验规则分类清单_v1.md) | 区分历史盘点与现行 30 个结构化规则 |
| [docs/compact-dsl-validator-refactor/Compact_DSL重构实施与验证记录.md](../../docs/compact-dsl-validator-refactor/Compact_DSL重构实施与验证记录.md) | 保留历史验证并指向本轮融合记录 |
| [docs/云侧方案设计.md](../../docs/云侧方案设计.md) | 同步 Fusion 融合基线、执行边界与定位约定 |
| [widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/repair.md](../../widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/repair.md) | 新提示词包内增加结构化错误及展开结果阅读说明 |
| [widget_service/cloud/data/validator_rules/compact/repair_hints.json](../../widget_service/cloud/data/validator_rules/compact/repair_hints.json) | 保留可选建议，修正高度建议与固定设计量的冲突 |
| [widget_service/cloud/repair_compact_dsl.py](../../widget_service/cloud/repair_compact_dsl.py) | 独立修复同时传递布局范围与建议上下文 |
| [widget_service/cloud/services/artifact_store.py](../../widget_service/cloud/services/artifact_store.py) | 保留支持嵌套诊断的记录类型 |
| [widget_service/cloud/services/card_validation/compact_dsl_validator.py](../../widget_service/cloud/services/card_validation/compact_dsl_validator.py) | 保留公开入口与主文字辅助兼容导出 |
| [widget_service/cloud/services/card_validation/compact_validation/__init__.py](../../widget_service/cloud/services/card_validation/compact_validation/__init__.py) | 声明对应职责包，不放置规则或执行流程 |
| [widget_service/cloud/services/card_validation/compact_validation/api.py](../../widget_service/cloud/services/card_validation/compact_validation/api.py) | 依主线顺序组织原始树与展开树校验 |
| [widget_service/cloud/services/card_validation/compact_validation/compatibility/__init__.py](../../widget_service/cloud/services/card_validation/compact_validation/compatibility/__init__.py) | 声明对应职责包，不放置规则或执行流程 |
| [widget_service/cloud/services/card_validation/compact_validation/compatibility/hero.py](../../widget_service/cloud/services/card_validation/compact_validation/compatibility/hero.py) | 保留直接调用辅助，不恢复公共主文字流程 |
| [widget_service/cloud/services/card_validation/compact_validation/constants.py](../../widget_service/cloud/services/card_validation/compact_validation/constants.py) | 集中当前规则所需常量 |
| [widget_service/cloud/services/card_validation/compact_validation/context.py](../../widget_service/cloud/services/card_validation/compact_validation/context.py) | 分别保存展开前后组件及缓存索引 |
| [widget_service/cloud/services/card_validation/compact_validation/diagnostics.py](../../widget_service/cloud/services/card_validation/compact_validation/diagnostics.py) | 保留旧异常语义、诊断分组，补齐 extend 记录和 expanded 来源 |
| [widget_service/cloud/services/card_validation/compact_validation/flows/__init__.py](../../widget_service/cloud/services/card_validation/compact_validation/flows/__init__.py) | 声明对应职责包，不放置规则或执行流程 |
| [widget_service/cloud/services/card_validation/compact_validation/flows/contracts.py](../../widget_service/cloud/services/card_validation/compact_validation/flows/contracts.py) | 按原顺序组合结构、点击和数据校验 |
| [widget_service/cloud/services/card_validation/compact_validation/model_feedback.py](../../widget_service/cloud/services/card_validation/compact_validation/model_feedback.py) | 仅在模型请求副本格式化诊断，识别展开事实来源 |
| [widget_service/cloud/services/card_validation/compact_validation/repair_guidance.py](../../widget_service/cloud/services/card_validation/compact_validation/repair_guidance.py) | 保留按码默认建议及动态函数扩展接口 |
| [widget_service/cloud/services/card_validation/compact_validation/rule_catalog.py](../../widget_service/cloud/services/card_validation/compact_validation/rule_catalog.py) | 登记当前 30 个活动错误码，不复用退役含义 |
| [widget_service/cloud/services/card_validation/compact_validation/schema.py](../../widget_service/cloud/services/card_validation/compact_validation/schema.py) | 保留等价路径及类型辅助，去除旧布局专用辅助 |
| [widget_service/cloud/services/card_validation/compact_validation/semantic/__init__.py](../../widget_service/cloud/services/card_validation/compact_validation/semantic/__init__.py) | 声明对应职责包，不放置规则或执行流程 |
| [widget_service/cloud/services/card_validation/compact_validation/semantic/bindings.py](../../widget_service/cloud/services/card_validation/compact_validation/semantic/bindings.py) | 保留主线绑定、首帧数据及进度类型规则 |
| [widget_service/cloud/services/card_validation/compact_validation/semantic/cross_file.py](../../widget_service/cloud/services/card_validation/compact_validation/semantic/cross_file.py) | 数据声明与类型一致性和原 warning |
| [widget_service/cloud/services/card_validation/compact_validation/semantic/display.py](../../widget_service/cloud/services/card_validation/compact_validation/semantic/display.py) | 展示语义与进度读数对象一致性 |
| [widget_service/cloud/services/card_validation/compact_validation/semantic/effective.py](../../widget_service/cloud/services/card_validation/compact_validation/semantic/effective.py) | 保留主线背景素材及事件候选校验 |
| [widget_service/cloud/services/card_validation/compact_validation/semantic/layout/__init__.py](../../widget_service/cloud/services/card_validation/compact_validation/semantic/layout/__init__.py) | 声明对应职责包，不放置规则或执行流程 |
| [widget_service/cloud/services/card_validation/compact_validation/semantic/layout/geometry.py](../../widget_service/cloud/services/card_validation/compact_validation/semantic/layout/geometry.py) | 保留区域预算、Recipe 高度和完整占用明细 |
| [widget_service/cloud/services/card_validation/compact_validation/source_locations.py](../../widget_service/cloud/services/card_validation/compact_validation/source_locations.py) | 展开节点无法证明原文来源时省略位置 |
| [widget_service/cloud/services/card_validation/compact_validation/syntax/__init__.py](../../widget_service/cloud/services/card_validation/compact_validation/syntax/__init__.py) | 声明对应职责包，不放置规则或执行流程 |
| [widget_service/cloud/services/card_validation/compact_validation/syntax/components.py](../../widget_service/cloud/services/card_validation/compact_validation/syntax/components.py) | 组件结构、点击形状与模型组件白名单 |
| [widget_service/cloud/services/card_validation/compact_validation/syntax/expressions.py](../../widget_service/cloud/services/card_validation/compact_validation/syntax/expressions.py) | 保留表达式规则与结构化定位 |
| [widget_service/cloud/services/card_validation/compact_validation/text.py](../../widget_service/cloud/services/card_validation/compact_validation/text.py) | 复用当前文本及视觉标记辅助 |
| [widget_service/cloud/services/generation_pipeline.py](../../widget_service/cloud/services/generation_pipeline.py) | 叠加诊断分组，保留 Plan 错误码、Trace 与主线参数 |
| [widget_service/cloud/services/prompt_builder.py](../../widget_service/cloud/services/prompt_builder.py) | 只转换 qualityErrors，保留失败历史及组合恢复上下文 |
| [widget_service/cloud/services/widget_generation_service.py](../../widget_service/cloud/services/widget_generation_service.py) | 在线入口传递 create/edit 建议上下文 |
| [widget_service/tests/fixtures/compact_validation_baseline.json](../../widget_service/tests/fixtures/compact_validation_baseline.json) | 冻结 main 的 87 组实际校验调用与输出 |
| [widget_service/tests/fixtures/compact_validation_rule_inventory.json](../../widget_service/tests/fixtures/compact_validation_rule_inventory.json) | 登记当前 30 个诊断发布位置与分类 |
| [widget_service/tests/test_compact_validation_architecture.py](../../widget_service/tests/test_compact_validation_architecture.py) | 检查活动错误码、归属及无旧流程依赖 |
| [widget_service/tests/test_compact_validation_diagnostics.py](../../widget_service/tests/test_compact_validation_diagnostics.py) | 保留诊断与位置验证，使用当前模型组件合同 |
| [widget_service/tests/test_compact_validation_equivalence.py](../../widget_service/tests/test_compact_validation_equivalence.py) | 对比 main 的公开结果、异常与 warning |
| [widget_service/tests/test_compact_validation_fusion.py](../../widget_service/tests/test_compact_validation_fusion.py) | 白名单、展开定位、布局文本、Plan 与恢复信息回归 |
| [widget_service/tests/test_compact_validation_repair_integration.py](../../widget_service/tests/test_compact_validation_repair_integration.py) | 两条修复入口、素材还原和内部记录验证 |

## 从旧重构包撤下的文件

下列删除是相对原重构 HEAD 的变化，不代表删除主线现行规则。旧提示词文件遵循 main 删除。

- `widget_service/cloud/data/protocol_profiles/design-compact-dsl/REPAIR_SYSTEM_PROMPT.md`
- `widget_service/cloud/services/card_validation/compact_validation/flows/hero.py`
- `widget_service/cloud/services/card_validation/compact_validation/flows/layout.py`
- `widget_service/cloud/services/card_validation/compact_validation/flows/two_by_two.py`
- `widget_service/cloud/services/card_validation/compact_validation/flows/w1.py`
- `widget_service/cloud/services/card_validation/compact_validation/flows/w9.py`
- `widget_service/cloud/services/card_validation/compact_validation/semantic/layout/assets.py`
- `widget_service/cloud/services/card_validation/compact_validation/semantic/layout/fusion.py`
- `widget_service/cloud/services/card_validation/compact_validation/semantic/layout/regions.py`
- `widget_service/cloud/services/card_validation/compact_validation/semantic/layout/routing.py`
- `widget_service/cloud/services/card_validation/compact_validation/semantic/layout/two_by_four.py`
- `widget_service/cloud/services/card_validation/compact_validation/semantic/layout/two_by_two.py`
- `widget_service/cloud/services/card_validation/compact_validation/semantic/layout/typography.py`
- `widget_service/cloud/services/card_validation/compact_validation/semantic/layout/w1.py`
- `widget_service/cloud/services/card_validation/compact_validation/semantic/layout/w9.py`
- `widget_service/tests/fixtures/compact_validation_rule_cases.json`
- `widget_service/tests/test_compact_validation_rule_cases.py`
- `widget_service/tests/test_compact_validation_w9.py`


## PR489/492 继续融合

当前行为基线更新为 `a42d86a5`，在首次融合提交 `cc53114b` 之上合入 PR489/492。
主线新增的运行时容量提示开关、分级修复策略、无损紧凑替换、组件合同与渲染规则均保留。
实际冲突仅在旧校验入口与修复提示词；自动合并后的调用方仍保留结构化反馈的副本格式化边界。

### 规则分类和错误兼容

| 检查项 | 分类及位置 | 合并方式 |
|---|---|---|
| 多段时长误用数值组件 | 语义／展示语义，`semantic/display.py` | 共享绑定合同后、组件展开前检查，保留完整原绑定建议及错误顺序 |
| TextBlock 标签和值的关系 | 语义／展示语义，`semantic/display.py` | 只查询同一项的 Recipe 标签，避免跨项或跨分区借用含义 |
| 完整单行文字的宽度 | 语义／布局与视觉约束，`semantic/layout/text_width.py` | 高度检查后执行；未知实际宽度仅使用已知祖先内宽上界 |
| 标签与多段时长的同行压力 | 语义／布局与视觉约束，`semantic/layout/text_width.py` | 保留完整标签、值、间距与已有字号；未知兄弟宽度不猜测 |

新增校验输出保持主线字符串形式，既有 30 个结构化错误码不变。字符串与结构化记录可同时存在，
经旧错误聚合及模型反馈边界输出，不丢失宽度错误。7 个迁移或修改的规则函数经 AST 对比与主线一致。
组件白名单、绑定合同、布局、展开、宽度/高度与首帧数据检查保持主线顺序。

修复提示词同时保留诊断阅读说明和主线 repairStrategy 的四种范围；full_dsl 不被旧“局部修复”文案覆盖。
fixHint 仅提供建议，重试与升级由主线 CompactRepairStrategyTracker 编排，不增加另一套策略。
容量提示关闭时不沿用旧 compositionRecovery；开启且发生容量错误时才提供参考或重算。
qualityErrors 在路由判断时仍保留原记录；模型副本可格式化，previousFailures 与 repairStrategy 均不回写。

### 最新验证

- 使用 upstream/main 的独立源码副本，与当前工作区相同的本地配置运行基线；初次未加载本地配置的
  27 项失败结果不用于最终比较。同配置基线为 **814 passed、39 failed、1 skipped、1 deselected、35 subtests passed**。
- 24 个相关测试文件回归：**987 passed、39 failed、1 skipped、1 deselected、35 subtests passed**。
  39 个失败的测试 ID 与同配置主线完全一致，没有新增失败；两项异常展示包含新增诊断元数据，
  一项断言含进程内对象地址，这些不改变失败原因。
- 重构专项 **173 项全部通过**：原 87 组输入及新捕获输入去重后共 112 组，以未修改主线计算期望。
  原 87 组期望全部不变；另覆盖宽度与高度错误并存、多段时长提前拦截、同项标签、范围升级、容量提示开关。
- 本次涉及的 26 个 Python 文件 Ruff 通过；冲突标记扫描、相对 HEAD/upstream/main 的差异空白检查通过。
- 依赖外部模型服务的 `test_model_runtime_collects_llmclient_stream` 延续排除，不重复发出真实请求。
  未运行全仓库测试、真实模型/设备验收、外部 CodeCheck；本地没有渲染端 Node 依赖，未执行 TypeScript 渲染测试。
  渲染端文件按主线原样合入，未额外改写。

### 最新主线既有失败明细

以下均在主线独立副本与合并后同时失败，不计作通过。

| 测试 ID | 失败摘要 |
|---|---|
| `tests.test_asset_url_mapper.test_final_validator_recognizes_exact_mapped_asset[https://hagres-drcn.dbankcdn.com/assets/drop_1.svg?version=1-True]` | services.compact_high_level_components.CompactDslConversionError: action: PillButton does not allow actionInk, actionSurface. |
| `tests.test_asset_url_mapper.test_final_validator_recognizes_exact_mapped_asset[https://hagres-drcn.dbankcdn.com/assets/drop_1.svg?version=1-other-False]` | services.compact_high_level_components.CompactDslConversionError: action: PillButton does not allow actionInk, actionSurface. |
| `tests.test_asset_url_mapper.test_final_validator_recognizes_exact_mapped_asset[resources/base/media/drop_1.svg-True]` | services.compact_high_level_components.CompactDslConversionError: action: PillButton does not allow actionInk, actionSurface. |
| `tests.test_asset_url_mapper.test_mapping_covers_expanded_action_icon` | services.compact_high_level_components.CompactDslConversionError: action: PillButton does not allow actionInk, actionSurface. |
| `tests.test_compact_dsl_validator.test_rejects_centered_single_value_hero_that_exceeds_height_pressure` | AssertionError: Regex pattern did not match. |
| `tests.test_compact_dsl_validator.test_rejects_centered_single_value_hero_that_exceeds_width_pressure` | Failed: DID NOT RAISE CompactDslValidationError |
| `tests.test_compact_dsl_validator.test_rejects_centered_single_value_hero_without_safe_box` | Failed: DID NOT RAISE CompactDslValidationError |
| `tests.test_compact_dsl_validator.test_rejects_large_hero_for_peer_metrics_on_150vp_card` | Failed: DID NOT RAISE CompactDslValidationError |
| `tests.test_compact_dsl_validator.test_rejects_sparse_w9_with_legacy_backboard_geometry` | Failed: DID NOT RAISE CompactDslValidationError |
| `tests.test_compact_dsl_validator.test_rejects_sparse_w9_without_vertical_center_and_layout_weight` | Failed: DID NOT RAISE CompactDslValidationError |
| `tests.test_compact_hero_typography.test_non_template_formatted_readout_keeps_original_contract[expression]` | AssertionError: assert False is ('expression' != 'none') |
| `tests.test_compact_hero_typography.test_non_template_formatted_readout_keeps_original_contract[inherited-width]` | AssertionError: assert False is ('inherited-width' != 'none') |
| `tests.test_compact_hero_typography.test_non_template_formatted_readout_keeps_original_contract[percent-description]` | AssertionError: assert False is ('percent-description' != 'none') |
| `tests.test_compact_hero_typography.test_template_keeps_other_compact_validations[empty-non-empty]` | AssertionError: Regex pattern did not match. |
| `tests.test_compact_plan.test_processor_reports_missing_plan_fact_with_dedicated_code` | assert 2 == 1 |
| `tests.test_compact_runtime_prompt_context.test_enabled_runtime_prompt_context_includes_plan_dsl_and_recovery` | AssertionError: assert '# 本轮组合容量工作表' in 'design rules\n\n# 本轮组件与布局选择\n\n当前尺寸 2x2，合法布局范围：S-center、S-title-content、S-title-dual-content、S-title-primary-secondar...x2 单业务且内容较少，运行时已允许融球。若最终仍是单内容 |
| `tests.test_fusion_ball_version_gate.test_design_processor_copies_task_spec_app_version_into_profile` | assert not (QualityIssue(stage='validation', code='COMPACT_DSL_VALIDATION_FAILED', message='component title: Text is converter-in...'TopTextBottomValue']}, 'actual': 'Text', 'evidenceSource' |
| `tests.test_generation_trace_recorder.test_compact_flow_does_not_write_trace_when_disabled` | AssertionError: assert <GenerationStatus.FAILED: 'failed'> in {<GenerationStatus.DEGRADED: 'degraded'>, <GenerationStatus.SUCCESS: 'success'>} |
| `tests.test_generation_trace_recorder.test_compact_mock_flow_records_intermediate_artifacts` | AssertionError: assert <GenerationStatus.FAILED: 'failed'> in {<GenerationStatus.DEGRADED: 'degraded'>, <GenerationStatus.SUCCESS: 'success'>} |
| `tests.test_generation_trace_recorder.test_upload_failure_keeps_trace_terminal_state` | Failed: DID NOT RAISE ArtifactUploadError |
| `tests.test_service_units.test_anyio_thread_pool_uses_configured_capacity` | AssertionError: assert 'llmclient' == 'deepseek_platform' |
| `tests.test_service_units.test_conversion_failure_does_not_repair_when_switch_is_disabled[generate_widget_card_compact_dsl]` | TypeError: test_conversion_failure_does_not_repair_when_switch_is_disabled.<locals>.generate_invalid() got an unexpected keyword argument 'suppress_prompt_log' |
| `tests.test_service_units.test_conversion_failure_repair_uses_latest_source_format[generate_widget_card_compact_dsl-["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":20,"clip":true,"backgroundColor":"comp_background_primary"},["foreground"]]\n["foreground","Column",{"width":"matchParent","height":"matchParent","padding":12,"alignItems":"start","justifyContent":"start"},["title"]]\n["title","SecondaryBody",{"role":"body","items":[{"value":"Design Compact Mock","maxLines":1}],"fontColor":"#FF1F4799"}]\n["/ui/state","ready"]\n-design-compact-dsl]` | AssertionError: assert <GenerationSt...LED: 'failed'> == <GenerationSt...SS: 'success'> |
| `tests.test_service_units.test_conversion_repair_stops_at_configured_maximum[generate_widget_card_compact_dsl]` | assert 2 == 3 |
| `tests.test_service_units.test_design_compact_edit_prompt_contains_previous_design_token` | AssertionError: assert 'DSL' not in 'design rule...没有发生无意义漂移。\n' |
| `tests.test_service_units.test_design_compact_few_shots_are_disabled_by_default_and_can_be_enabled` | AssertionError: assert True is False |
| `tests.test_service_units.test_design_compact_validation_error_retries_then_does_not_save` | AssertionError: assert 'A2UI_GENERATION_FAILED' == 'VALIDATION_FAILED' |
| `tests.test_service_units.test_design_converter_expands_latest_design_tokens` | custom.a2ui_model_client.A2UIModelGenerationError: design DSL conversion failed |
| `tests.test_service_units.test_missing_action_unit_on_click_enters_validation_repair` | AssertionError: assert <GenerationSt...LED: 'failed'> == <GenerationSt...SS: 'success'> |
| `tests.test_service_units.test_model_failure_skips_validator_and_artifact_store[empty-generate_widget_card_compact_dsl]` | TypeError: test_model_failure_skips_validator_and_artifact_store.<locals>.fail_generate() got an unexpected keyword argument 'suppress_prompt_log' |
| `tests.test_service_units.test_model_failure_skips_validator_and_artifact_store[exception-generate_widget_card_compact_dsl]` | TypeError: test_model_failure_skips_validator_and_artifact_store.<locals>.fail_generate() got an unexpected keyword argument 'suppress_prompt_log' |
| `tests.test_service_units.test_phase_two_version_returns_phase_two_capability_overview` | AssertionError: assert False |
| `tests.test_service_units.test_phase_two_version_returns_phase_two_capability_schemas` | AssertionError: assert ['GetCurrentT...ilyMostUsage'] == ['GetMemoData...ilyMostUsage'] |
| `tests.test_service_units.test_quality_repair_distinguishes_source_and_artifact_validation[generate_widget_card_compact_dsl-["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":20,"clip":true,"backgroundColor":"comp_background_primary"},["foreground"]]\n["foreground","Column",{"width":"matchParent","height":"matchParent","padding":12,"alignItems":"start","justifyContent":"start"},["title"]]\n["title","SecondaryBody",{"role":"body","items":[{"value":"Design Compact Mock","maxLines":1}],"fontColor":"#FF1F4799"}]\n["/ui/state","ready"]\n-design-compact-dsl]` | IndexError: list index out of range |
| `tests.test_service_units.test_source_format_validation_error_repairs_original_source_dsl[generate_widget_card_compact_dsl-["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":20,"clip":true,"backgroundColor":"comp_background_primary"},["foreground"]]\n["foreground","Column",{"width":"matchParent","height":"matchParent","padding":12,"alignItems":"start","justifyContent":"start"},["title"]]\n["title","SecondaryBody",{"role":"body","items":[{"value":"Design Compact Mock","maxLines":1}],"fontColor":"#FF1F4799"}]\n["/ui/state","ready"]\n-design-compact-dsl]` | AssertionError: assert <GenerationSt...LED: 'failed'> == <GenerationSt...SS: 'success'> |
| `tests.test_service_units.test_source_format_validation_repair_stops_at_configured_maximum[generate_widget_card_compact_dsl-["root","Stack",{"width":"matchParent","height":"matchParent","borderRadius":20,"clip":true,"backgroundColor":"comp_background_primary"},["foreground"]]\n["foreground","Column",{"width":"matchParent","height":"matchParent","padding":12,"alignItems":"start","justifyContent":"start"},["title"]]\n["title","SecondaryBody",{"role":"body","items":[{"value":"Design Compact Mock","maxLines":1}],"fontColor":"#FF1F4799"}]\n["/ui/state","ready"]\n-design-compact-dsl]` | IndexError: list index out of range |
| `tests.test_service_units.test_source_format_warning_does_not_trigger_repair[generate_widget_card_compact_dsl-design-compact]` | AssertionError: assert <GenerationSt...LED: 'failed'> == <GenerationSt...SS: 'success'> |
| `tests.test_service_units.test_unknown_processor_exception_does_not_trigger_model_repair` | Failed: DID NOT RAISE RuntimeError |
| `tests.test_service_units.test_unknown_validator_exception_does_not_trigger_model_repair` | Failed: DID NOT RAISE RuntimeError |

### 本次融合提交文件清单

相对前次提交 `cc53114b` 共 49 个文件（含主线原样合入内容）。

| 文件 | 用途 |
|---|---|
| [docs/compact-dsl-validator-refactor/Compact_DSL_Fusion融合记录.md](../../docs/compact-dsl-validator-refactor/Compact_DSL_Fusion融合记录.md) | 更新行为基线、分类、回归与完整文件清单 |
| [docs/compact-dsl-validator-refactor/Compact_DSL校验器重构方案_v3.md](../../docs/compact-dsl-validator-refactor/Compact_DSL校验器重构方案_v3.md) | 同步当前生效约定与修复策略边界 |
| [docs/compact-dsl-validator-refactor/Compact_DSL现有校验规则分类清单_v1.md](../../docs/compact-dsl-validator-refactor/Compact_DSL现有校验规则分类清单_v1.md) | 登记本轮新增展示与宽度规则归属 |
| [docs/compact-dsl-validator-refactor/Compact_DSL重构实施与验证记录.md](../../docs/compact-dsl-validator-refactor/Compact_DSL重构实施与验证记录.md) | 登记最新融合和验证结果 |
| [docs/云侧方案设计.md](../../docs/云侧方案设计.md) | 保留主线新方案并同步分类校验与修复反馈边界 |
| [render/platform/lib/compact-components.ts](../../render/platform/lib/compact-components.ts) | 原样合入主线渲染组件合同 |
| [render/platform/tests/high-level-components.test.ts](../../render/platform/tests/high-level-components.test.ts) | 原样合入主线组件合同、修复或提示词回归 |
| [uv.lock](../../uv.lock) | 原样合入主线依赖锁定版本 |
| [widget_service/.env.example](../../widget_service/.env.example) | 原样合入主线容量提示开关及配置 |
| [widget_service/cloud/config/config.py](../../widget_service/cloud/config/config.py) | 原样合入主线容量提示开关及配置 |
| [widget_service/cloud/config/default_config.yaml](../../widget_service/cloud/config/default_config.yaml) | 原样合入主线容量提示开关及配置 |
| [widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/README.md](../../widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/README.md) | 原样合入主线合同说明和字段演进记录 |
| [widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/components/2x2.md](../../widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/components/2x2.md) | 原样合入主线完整文案与无损紧凑组件提示合同 |
| [widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/components/2x4.md](../../widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/components/2x4.md) | 原样合入主线完整文案与无损紧凑组件提示合同 |
| [widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/components/common.md](../../widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/components/common.md) | 原样合入主线完整文案与无损紧凑组件提示合同 |
| [widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/core.md](../../widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/core.md) | 原样合入主线完整文案与无损紧凑组件提示合同 |
| [widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/fewshots/2x2.md](../../widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/fewshots/2x2.md) | 原样合入主线完整文案与无损紧凑组件提示合同 |
| [widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/fewshots/2x4.md](../../widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/fewshots/2x4.md) | 原样合入主线完整文案与无损紧凑组件提示合同 |
| [widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/layouts/2x4.md](../../widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/layouts/2x4.md) | 原样合入主线完整文案与无损紧凑组件提示合同 |
| [widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/plan.md](../../widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/plan.md) | 原样合入主线完整文案与无损紧凑组件提示合同 |
| [widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/repair.md](../../widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/repair.md) | 融合诊断阅读说明与主线范围升级策略 |
| [widget_service/cloud/services/card_validation/compact_validation/api.py](../../widget_service/cloud/services/card_validation/compact_validation/api.py) | 按主线顺序接入多段时长和文案宽度检查 |
| [widget_service/cloud/services/card_validation/compact_validation/semantic/display.py](../../widget_service/cloud/services/card_validation/compact_validation/semantic/display.py) | 承接多段时长选型和 TextBlock 同项标签识别 |
| [widget_service/cloud/services/card_validation/compact_validation/semantic/layout/text_width.py](../../widget_service/cloud/services/card_validation/compact_validation/semantic/layout/text_width.py) | 承接完整文案及标签时长同行宽度校验 |
| [widget_service/cloud/services/card_validation/字段约束与演进记录.md](../../widget_service/cloud/services/card_validation/字段约束与演进记录.md) | 原样合入主线合同说明和字段演进记录 |
| [widget_service/cloud/services/compact_component_bindings.py](../../widget_service/cloud/services/compact_component_bindings.py) | 原样合入主线组合求解、组件展开或修复策略实现 |
| [widget_service/cloud/services/compact_composition_context.py](../../widget_service/cloud/services/compact_composition_context.py) | 原样合入主线组合求解、组件展开或修复策略实现 |
| [widget_service/cloud/services/compact_composition_planner.py](../../widget_service/cloud/services/compact_composition_planner.py) | 原样合入主线组合求解、组件展开或修复策略实现 |
| [widget_service/cloud/services/compact_high_level_components.py](../../widget_service/cloud/services/compact_high_level_components.py) | 原样合入主线组合求解、组件展开或修复策略实现 |
| [widget_service/cloud/services/compact_plan.py](../../widget_service/cloud/services/compact_plan.py) | 原样合入主线组合求解、组件展开或修复策略实现 |
| [widget_service/cloud/services/compact_region_layout.py](../../widget_service/cloud/services/compact_region_layout.py) | 原样合入主线组合求解、组件展开或修复策略实现 |
| [widget_service/cloud/services/compact_repair_strategy.py](../../widget_service/cloud/services/compact_repair_strategy.py) | 原样合入主线组合求解、组件展开或修复策略实现 |
| [widget_service/cloud/services/prompt_builder.py](../../widget_service/cloud/services/prompt_builder.py) | 合入主线修复策略和容量开关，保留模型副本格式化 |
| [widget_service/cloud/services/retry_controller.py](../../widget_service/cloud/services/retry_controller.py) | 原样合入主线组合求解、组件展开或修复策略实现 |
| [widget_service/cloud/services/widget_generation_service.py](../../widget_service/cloud/services/widget_generation_service.py) | 合入主线重试策略跟踪与兜底，保留可选建议上下文 |
| [widget_service/tests/fixtures/compact_validation_baseline.json](../../widget_service/tests/fixtures/compact_validation_baseline.json) | 以最新主线重放 112 组输入，保留原 87 组期望 |
| [widget_service/tests/test_compact_component_bindings.py](../../widget_service/tests/test_compact_component_bindings.py) | 原样合入主线组件合同、修复或提示词回归 |
| [widget_service/tests/test_compact_dsl_a2ui_converter.py](../../widget_service/tests/test_compact_dsl_a2ui_converter.py) | 原样合入主线组件合同、修复或提示词回归 |
| [widget_service/tests/test_compact_dsl_validator.py](../../widget_service/tests/test_compact_dsl_validator.py) | 原样合入主线组件合同、修复或提示词回归 |
| [widget_service/tests/test_compact_prompt_bundle.py](../../widget_service/tests/test_compact_prompt_bundle.py) | 原样合入主线组件合同、修复或提示词回归 |
| [widget_service/tests/test_compact_repair_strategy.py](../../widget_service/tests/test_compact_repair_strategy.py) | 原样合入主线组件合同、修复或提示词回归 |
| [widget_service/tests/test_compact_runtime_prompt_context.py](../../widget_service/tests/test_compact_runtime_prompt_context.py) | 原样合入主线组件合同、修复或提示词回归 |
| [widget_service/tests/test_compact_validation_equivalence.py](../../widget_service/tests/test_compact_validation_equivalence.py) | 标明当前等价测试的行为基线 |
| [widget_service/tests/test_compact_validation_fusion.py](../../widget_service/tests/test_compact_validation_fusion.py) | 同时验证容量提示开启与关闭的反馈边界 |
| [widget_service/tests/test_compact_validation_fusion_followup.py](../../widget_service/tests/test_compact_validation_fusion_followup.py) | 新增 6 项跨规则、标签和修复策略回归 |
| [widget_service/tests/test_design_compact_few_shots.py](../../widget_service/tests/test_design_compact_few_shots.py) | 原样合入主线组件合同、修复或提示词回归 |
| [widget_service/tests/test_design_compact_repair_prompt.py](../../widget_service/tests/test_design_compact_repair_prompt.py) | 原样合入主线组件合同、修复或提示词回归 |
| [widget_service/tests/test_service_units.py](../../widget_service/tests/test_service_units.py) | 原样合入主线组件合同、修复或提示词回归 |
| [widget_service/uv.lock](../../widget_service/uv.lock) | 原样合入主线依赖锁定版本 |


## 融合后经确认的规则恢复

2026-10-12，在 `106e8501` 上按用户确认的三项范围补回遗漏校验。此节是对融合时“保留主线行为”的
明确补充，不改变上文历史测试结论；不将旧规则清单整批重新接入。

| 检查 | 当前规则码 | 分类与边界 |
|---|---|---|
| 模型素材范围 | `COMPACT_ASSET_NOT_ALLOWED` | 语义／有效能力；检查原始 ProgressCircle、ProgressCircleSingle、PillButton、CircleButton、CardButton、InfoBlock 的 icon，以及 InfoBlock.visual.icon、NumericRatioStack.items[].icon。兼容引用提取支持 Image.src，但不重新开放内部组件。背景检查仍在原位置执行 |
| SVG 显式颜色缺失 | `COMPACT_SVG_FILL_COLOR_MISSING` | 语义／布局与视觉约束；仅 ProgressCircle、带 icon 的 CardButton 的候选可染色 SVG，缺失属性时报告。颜色格式仍由组件合同校验 |
| 数值组件误用 | `COMPACT_DISPLAY_NUMERIC_COMPONENT_MISUSE` | 语义／展示；只检查原始 EmphasizedData.value 的明确非量化内容，不恢复通用大字号限制 |

当前活动结构化规则由 30 个增至 32 个。素材范围共用一个诊断发布位置；规则清单通过 AST 测试验证
唯一归属。新规则在既有高阶绑定和多段时长检查通过后、组件展开前执行；失败时保留布局错误，并在
原始上下文定位属性及行号。其他既有检查顺序和 112 项历史调用预期不改。

### 兼容与修复边界

- 候选缺失或不是列表时保留旧入口行为；明确空列表不允许图标。未声明 SVG 只报告素材范围错误，
  不叠加无法判断的着色错误。原始引用按组件合同枚举，不递归搜同名 icon，不把内部生成 Image 当输入。
- 自动着色的 PillButton、CircleButton、ProgressCircleSingle 不要求额外颜色属性；InfoBlock 的默认
  着色和 native 模式保留；NumericRatioStack 复用既有必填颜色检查。明确原色的 SVG 与 PNG 不触发缺色错误。
- 数字、数字字符串、千分位、科学计数法、单一测量读数、中文数词、未知表达式及缺数据占位均不新增阻断。
  `05:30` 可能是配速或用时，静态值不凭冒号认定时刻；纯绑定需字段描述与合同样值共同证明误用，
  不以 string 类型或首帧占位代替语义证据。现有多段时长错误仍由原规则负责。
- 事实诊断和修复建议分离，默认建议在 repair_hints.json 配置。保留异常类型、外层通用错误码、
  模型说明格式及内部记录；修复不引导删除必要事实、改变绑定、强转数值或改动固定 Recipe。
- 原有素材还原阶段补齐 InfoBlock.visual.icon、NumericRatioStack.items[].icon 的历史 URL 映射。
  已登记地址还原后再执行新检查；未知或歧义地址继续拒绝，文案、数据、事件、源文件与下载摘要不改。
- 模板生成路径继续跳过 Compact 校验。普通历史来源产物编辑前同样执行当前校验：真正漏色或误用数值
  组件的旧产物会被来源预检拒绝，不自动迁移或修改；嵌套 URL 还原只修复表示形式，不放宽规则。
- 本轮没有恢复全局动作／事实去重、旧 W1/W9/S4 布局、图标数量或通用字号启发式。

### 本轮修改文件

以下路径均相对仓库根目录。

| 文件 | 用途 |
|---|---|
| `docs/云侧方案设计.md` | 先登记已确认三项范围、例外、来源预检及模板边界 |
| `docs/compact-dsl-validator-refactor/Compact_DSL校验器重构方案_v3.md` | 更新当前实现、32 个规则及分类落点 |
| `docs/compact-dsl-validator-refactor/Compact_DSL现有校验规则分类清单_v1.md` | 登记恢复范围并区分历史盘点 |
| `docs/compact-dsl-validator-refactor/Compact_DSL_Fusion融合记录.md` | 本轮实施、逐文件明细与验证记录 |
| `docs/校验、重试与兜底机制入门指南.md` | 更新当前活动规则数量 |
| `widget_service/cloud/services/card_validation/字段约束与演进记录.md` | 登记素材条件必填、数值选型与兼容变化 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/core.md` | 说明各组件显式／自动着色边界 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/components/common.md` | 澄清数值组件用途、ProgressCircle 条件必填颜色 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/components/2x2.md` | 为两个可染色图标示例补充颜色 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/components/2x4.md` | 补齐 CardButton 条件必填颜色合同 |
| `widget_service/cloud/data/validator_rules/compact/repair_hints.json` | 三项规则的独立默认修改建议 |
| `widget_service/cloud/services/card_validation/compact_validation/api.py` | 新增原始组件检查阶段，沿用异常装配 |
| `widget_service/cloud/services/card_validation/compact_validation/rule_catalog.py` | 注册两个活动错误码 |
| `widget_service/cloud/services/card_validation/compact_validation/semantic/asset_references.py` | 提取登记的原始素材引用与位置 |
| `widget_service/cloud/services/card_validation/compact_validation/semantic/effective.py` | 素材候选校验，保留背景检查行为并共用诊断发布位置 |
| `widget_service/cloud/services/card_validation/compact_validation/semantic/layout/assets.py` | 有组件边界的 SVG 缺色检查 |
| `widget_service/cloud/services/card_validation/compact_validation/semantic/numeric_display.py` | 证据充分时检查数值组件误用 |
| `widget_service/cloud/services/asset_url_mapper.py` | 原有还原阶段补齐嵌套图标 |
| `widget_service/tests/fixtures/compact_validation_rule_inventory.json` | 同步 32 个规则发布位置，供架构测试核对 |
| `widget_service/tests/test_compact_validation_assets.py` | 素材范围、颜色例外、原始位置与内部节点回归 |
| `widget_service/tests/test_compact_validation_numeric_display.py` | 数值、文本、绑定、配速、占位及表达式正反例 |
| `widget_service/tests/test_compact_validation_restoration_integration.py` | 正式示例、新错误到修复、颜色实际转换、模板跳过及历史还原交叉回归 |
| `widget_service/tests/test_asset_url_mapper.py` | 嵌套还原、未知／歧义地址及非素材字段不变回归 |

### 本轮验证

- 修改前基线：`106e8501` 独立 git archive，同一虚拟环境和相同本地配置。
- 同范围扩大回归：基线 **926 passed / 64 failed / 53 subtests passed**；改后
  **1128 passed / 64 failed / 53 subtests passed**。失败 node ID 与错误信息逐项相同，新增失败为零。
  新增的 202 项全部通过：素材 68、数值选型 83、集成 45、嵌套 URL 还原 6。
- 扩大回归后再增加 2 项“同时失败→部分修复→全部修复”的交叉测试，普通 reading ID 和
  template_root ID 均验证，防止规则互相遮蔽及伪模板标记绕过。最终专项集 **449 passed / 0 failed**，
  含完整 112 项历史行为重放、32 项规则归属核对、组件合同、提示词加载和两条修复入口。
  各测试集有重叠，不能把这些通过数直接相加。
- 代表性独立模板 **64 passed**：颜色 26、动作编译 10、素材语义 25、合同 3。
- 全部 23 个正式 Few-shot 通过新增三项规则且输入不变；公开入口与正式布局另验证三类坏例和修复结果。
  自动着色、显式着色、原色保留通过实际高阶展开到标准 A2UI 的矩阵测试。
- 修改／新增的 11 个 Python 文件 Ruff 通过；`git diff --check` 通过；提示词组装、建议配置和
  规则归属由专项测试覆盖。原始 112 项行为基线文件没有修改。

既有失败仍需独立治理，本轮不通过修改旧断言掩盖问题：

| 测试模块 | 失败数 | 修改前后的共同原因 |
|---|---:|---|
| test_compact_dsl_validator | 6 | 旧布局／主文字规则预期及旧错误文案 |
| test_compact_hero_typography | 4 | 旧主文字字号与安全盒预期 |
| test_compact_plan | 1 | 样例使用模型侧不允许的 Text |
| test_fusion_ball_version_gate | 1 | 样例使用模型侧不允许的 Text |
| test_generation_trace_recorder | 3 | 既有成功状态或调用路径断言不符 |
| test_asset_url_mapper | 4 | 旧 PillButton 夹具仍提交 actionInk/actionSurface |
| test_compact_runtime_prompt_context | 1 | 期待已撤下的容量工作表 |
| test_template_ring_geometry | 17 | 旧 Progress/Divider 基础组件解析被拒绝 |
| test_asset_mapping_generation | 23 | 旧 Image／动作样例不满足当前模型组件合同 |
| test_service_units（本轮选取节点） | 4 | 既有修复路径／状态断言不符 |

扩大回归实际范围为：27 个 Compact／素材／修复相关测试文件、4 个 Processor／repair 用例节点、
2 个模板测试文件及 6 个模板素材／合同节点；改后额外运行 3 个新测试文件。
详细命令、XML、逐项失败原因和差异保存在本轮本地 TEMP 的
`compact-restoration-20261012-120032/focused-*`、`message-comparison.json`；最终专项结果保存在
TEMP 的 `compact-restoration-focused.xml` 与同名 log。

完整 3670 用例集包含全部模板目录，因耗时且大量无关场景未完成，已停止并保留部分日志，
不能计作全量通过。没有进行真实模型调用、端侧渲染或外部 CodeCheck；这里的兼容结论以
上述确定性测试和修改前后对照为边界。

## 2026-10-12 主线 rebase（历史记录）

> 本节记录当时采用 PR497 的处理，SVG 相关规则已按用户要求恢复；当前行为以后文更正记录为准。

当前分支以保留合并结构的方式 rebase 到 upstream/main `bdb6d84d`，本地 main 同步到该提交。
原分支 `18d1e2c2` 保存在 `codex/backup-compact-before-rebase-20261012`，没有执行远端推送。
纳入的三个主线提交为 `aa7dceb4`（耳机单动作与请求标题）、`175759b0`（日程模板）、
`bdb6d84d`（SVG 填色合同）。主线变更共 45 个文件；模板实现及高阶转换器保持主线版本。

### 冲突与合同衔接

- 重新应用历史合并时恢复当时已经迁移到分类目录的规则、测试基线和修复提示，
  没有把主线的整块校验器重新堆回兼容入口，也没有丢弃 PR489/492 的修复范围升级。
- SVG 合同采用本次主线更新：不再解析素材描述中的原色例外；显式颜色组件必须填色。
  原始 ProgressCircle、CardButton 仍提前输出 `COMPACT_SVG_FILL_COLOR_MISSING`；
  InfoBlock 等其余组件由主线展开阶段统一检查，保留其原始错误文本。
- InfoBlock 不再默认补充颜色，SVG 的 native 模式会被拒绝；位图可保留原色。
  自动着色组件、素材候选检查、数值组件检查以及模板跳过入口保持原有职责。
- 主线新增的 SVG 缺色测试改为验证本分支的结构化诊断码，不依赖转换器内部英文句式。
  专项测试覆盖描述无法豁免 SVG 缺色、SVG native 拒绝，以及三类显式配色组件的 PNG 原色保留。

### 本次额外适配提交的完整文件清单

| 文件 | 用途 |
|---|---|
| `docs/云侧方案设计.md` | 同步主线颜色合同及当前基线 |
| `docs/compact-dsl-validator-refactor/Compact_DSL校验器重构方案_v3.md` | 更新分类边界与主线基线 |
| `docs/compact-dsl-validator-refactor/Compact_DSL现有校验规则分类清单_v1.md` | 登记 SVG 规则范围与展开阶段委托 |
| `docs/compact-dsl-validator-refactor/Compact_DSL_Fusion融合记录.md` | 记录 rebase、冲突处置、文件清单和验证结果 |
| `widget_service/cloud/services/card_validation/字段约束与演进记录.md` | 移除已失效的原色 SVG 豁免说明 |
| `widget_service/cloud/services/card_validation/compact_validation/semantic/layout/assets.py` | 移除素材描述导致的 SVG 缺色豁免，保留原始位置诊断 |
| `widget_service/tests/test_compact_dsl_validator.py` | 衔接主线新增测试与结构化错误码 |
| `widget_service/tests/test_compact_validation_assets.py` | 验证颜色描述不再豁免 SVG 缺色 |
| `widget_service/tests/test_compact_validation_restoration_integration.py` | 验证 SVG 拒绝、显式颜色、PNG 原色及历史嵌套素材还原 |

### 验证

- 专项 12 个测试文件：452 passed，0 failed；包含 112 项历史行为基线。
- 纯主线对照：转换器、校验器、日程动作、日程模板扩展、日程请求案例及耳机意图共 6 个测试文件，
  347 passed、8 failed、35 subtests passed。失败为 6 个旧布局／hero 预期及 2 个模板基础组件解析问题。
- 本分支相同扩大范围：347 passed、8 failed、35 subtests passed；与纯主线失败集合完全一致，
  新增失败为 0。结果保存在本地 TEMP 的 `compact-rebase-main.xml`、
  `compact-rebase-upstream-final.xml` 及对应 log，专项结果为 `compact-rebase-focused.xml`。
- 4 个本次修改的 Python 文件 Ruff 通过；差异空白检查通过。
- 没有运行全量测试、真实模型批跑或端侧渲染。先前启动的调试服务没有重启，需重启后才能验证新代码。

## PR497 颜色规则更正

2026-10-12 用户明确要求保留原先 SVG 补色策略。此前 rebase 时直接采用 PR497（`bdb6d84d`）
及适配提交 `58965945` 的颜色行为不符合此要求，现已恢复 rebase 前 `18d1e2c2` 的颜色实现。
分支仍基于最新 main；主线的日程与耳机模板更新保留，不回退整个 rebase。

当前 SVG 颜色逻辑：

- 描述未声明原色限制的 SVG 默认可染色；原始 ProgressCircle、CardButton 缺少显式颜色时，
  仍由分类校验器输出 `COMPACT_SVG_FILL_COLOR_MISSING`，交给模型修复，不由校验器猜颜色。
- 描述包含不可染色、禁止染色、保留原色、多色、渐变、品牌色、品牌原色或插画原色时，
  不触发上述缺色检查。PNG 不参与 SVG 缺色判定。
- PillButton、CircleButton、ProgressCircleSingle 保留转换器的自动配色。
- InfoBlock 的 icon 模式优先使用显式 fillColor，否则使用 fontColor；native 模式不写 fillColor。
  progressCircle 模式优先使用显式 fillColor，否则使用主文字色的 60% 透明度。
- 移除 PR497 在所有展开 Image 上统一要求 SVG 填色／禁止位图填色的门禁；
  原有组件合同仍生效，不能把移除此门禁解释为允许任意非法属性或颜色值。

### 更正文件清单

| 文件 | 用途 |
|---|---|
| `docs/compact-dsl-validator-refactor/Compact_DSL_Fusion融合记录.md` | 记录纠正原因、完整文件清单与验证 |
| `docs/compact-dsl-validator-refactor/Compact_DSL校验器重构方案_v3.md` | 恢复原色豁免与组件职责说明 |
| `docs/compact-dsl-validator-refactor/Compact_DSL现有校验规则分类清单_v1.md` | 恢复 SVG 检查的原有范围 |
| `docs/云侧方案设计.md` | 恢复描述驱动的颜色策略，登记用户要求排除 PR497 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/components/2x2.md` | 恢复 PR497 前的素材颜色说明及组件提示词 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/components/2x4.md` | 恢复 PR497 前的素材颜色说明及组件提示词 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/components/common.md` | 恢复 PR497 前的素材颜色说明及组件提示词 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/composition.md` | 恢复 PR497 前的素材颜色说明及组件提示词 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/core.md` | 恢复 PR497 前的素材颜色说明及组件提示词 |
| `widget_service/cloud/services/card_validation/compact_validation/semantic/layout/assets.py` | 恢复素材描述中的原色 SVG 豁免 |
| `widget_service/cloud/services/card_validation/字段约束与演进记录.md` | 恢复字段颜色策略与历史登记 |
| `widget_service/cloud/services/compact_high_level_components.py` | 移除展开后全局填色门禁，恢复 InfoBlock 默认颜色和 native |
| `widget_service/tests/compact_dsl_validate/_collect_asset_color_errors/01/expected.json` | 恢复原色 SVG 校验预期 |
| `widget_service/tests/compact_dsl_validate/_collect_asset_color_errors/01/sample_compact.dsl` | 恢复原色 SVG 回归样例 |
| `widget_service/tests/compact_dsl_validate/coverage.json` | 恢复上述样例的规则覆盖登记 |
| `widget_service/tests/test_compact_dsl_a2ui_converter.py` | 恢复 PR497 前测试合同 |
| `widget_service/tests/test_compact_dsl_validator.py` | 移除要求全部 SVG 填色的 PR497 测试，原有缺色检查由专项测试覆盖 |
| `widget_service/tests/test_compact_prompt_bundle.py` | 恢复提示词描述驱动颜色策略断言 |
| `widget_service/tests/test_compact_validation_assets.py` | 恢复原色 SVG 豁免测试 |
| `widget_service/tests/test_compact_validation_restoration_integration.py` | 恢复 InfoBlock 默认补色和 SVG native 测试，保留新增 PNG 原色测试 |

### 更正后的验证

- 专项 12 个测试文件：452 passed，0 failed。包含原色 SVG 豁免、InfoBlock 默认补色／native、
  自动着色、高阶展开、原始诊断位置与模板跳过边界；额外保留 3 个 PNG 原色回归。
- 转换器、校验器及正式示例共 3 个测试文件：317 passed、6 failed、35 subtests passed。
  6 项失败与先前纯主线对照中的 W9／hero 旧预期完全一致，没有新增失败。
- 7 个本次变更 Python 文件 Ruff 通过；`git diff --check` 通过。
- 所有相关生产代码与 rebase 前备份对应实现相同；非 PR497 的主线文件保持不变。
- 日志与 JUnit 报告位于本地 TEMP 的 `compact-svg-original-focused.*`、
  `compact-svg-original-expanded.*`；没有重新调用真实模型或执行端侧渲染。

## PR423 提交整理

按用户要求，将原先的草案、逐步迁移、冲突修复及融合历史整理为三个提交；以 main `bdb6d84d` 为父提交，
保留最终文件内容，包含上节已确认的 PR497 颜色规则更正。历史章节中的旧提交号只用于追溯，
不表示整理后的 PR 仍有对应独立提交。完整旧历史和更正后的工作区保存到本地备份分支。

- 文档：设计方案、分类清单、实施记录、融合记录、入门指南和协作规范。
- 校验：分类实现、诊断与建议基础设施、素材和数值检查、原有 SVG 补色策略、对应单元测试。
- 反馈：生成流程、模型修复提示、修复记录及对应集成测试。

本次仅整理提交边界；通过完整 Git tree 比较确保整理前后已跟踪文件内容一致。
代码验证沿用上节当前版本的 452 项专项通过、317 项扩大回归通过及 6 项既有失败，
35 个子测试通过；另在中间校验提交运行独立单元测试，避免提交拆分造成依赖缺失。

### 三个提交的完整文件清单

#### 文档与协作规范（9 个文件）

- `AGENTS.md`
- `README.md`
- `docs/compact-dsl-validator-refactor/Compact_DSL_Fusion融合记录.md`
- `docs/compact-dsl-validator-refactor/Compact_DSL校验器重构方案_v3.md`
- `docs/compact-dsl-validator-refactor/Compact_DSL现有校验规则分类清单_v1.md`
- `docs/compact-dsl-validator-refactor/Compact_DSL重构实施与验证记录.md`
- `docs/云侧方案设计.md`
- `docs/校验、重试与兜底机制入门指南.md`
- `widget_service/cloud/services/card_validation/字段约束与演进记录.md`

#### 校验器与单元测试（51 个文件）

- `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/components/2x2.md`
- `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/components/2x4.md`
- `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/components/common.md`
- `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/composition.md`
- `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/core.md`
- `widget_service/cloud/data/validator_rules/compact/repair_hints.json`
- `widget_service/cloud/services/asset_url_mapper.py`
- `widget_service/cloud/services/card_validation/compact_dsl_validator.py`
- `widget_service/cloud/services/card_validation/compact_validation/__init__.py`
- `widget_service/cloud/services/card_validation/compact_validation/api.py`
- `widget_service/cloud/services/card_validation/compact_validation/compatibility/__init__.py`
- `widget_service/cloud/services/card_validation/compact_validation/compatibility/hero.py`
- `widget_service/cloud/services/card_validation/compact_validation/constants.py`
- `widget_service/cloud/services/card_validation/compact_validation/context.py`
- `widget_service/cloud/services/card_validation/compact_validation/diagnostics.py`
- `widget_service/cloud/services/card_validation/compact_validation/flows/__init__.py`
- `widget_service/cloud/services/card_validation/compact_validation/flows/contracts.py`
- `widget_service/cloud/services/card_validation/compact_validation/model_feedback.py`
- `widget_service/cloud/services/card_validation/compact_validation/repair_guidance.py`
- `widget_service/cloud/services/card_validation/compact_validation/rule_catalog.py`
- `widget_service/cloud/services/card_validation/compact_validation/schema.py`
- `widget_service/cloud/services/card_validation/compact_validation/semantic/__init__.py`
- `widget_service/cloud/services/card_validation/compact_validation/semantic/asset_references.py`
- `widget_service/cloud/services/card_validation/compact_validation/semantic/bindings.py`
- `widget_service/cloud/services/card_validation/compact_validation/semantic/cross_file.py`
- `widget_service/cloud/services/card_validation/compact_validation/semantic/display.py`
- `widget_service/cloud/services/card_validation/compact_validation/semantic/effective.py`
- `widget_service/cloud/services/card_validation/compact_validation/semantic/layout/__init__.py`
- `widget_service/cloud/services/card_validation/compact_validation/semantic/layout/assets.py`
- `widget_service/cloud/services/card_validation/compact_validation/semantic/layout/geometry.py`
- `widget_service/cloud/services/card_validation/compact_validation/semantic/layout/text_width.py`
- `widget_service/cloud/services/card_validation/compact_validation/semantic/numeric_display.py`
- `widget_service/cloud/services/card_validation/compact_validation/source_locations.py`
- `widget_service/cloud/services/card_validation/compact_validation/syntax/__init__.py`
- `widget_service/cloud/services/card_validation/compact_validation/syntax/components.py`
- `widget_service/cloud/services/card_validation/compact_validation/syntax/expressions.py`
- `widget_service/cloud/services/card_validation/compact_validation/text.py`
- `widget_service/cloud/services/compact_high_level_components.py`
- `widget_service/tests/compact_dsl_validate/_collect_asset_color_errors/01/expected.json`
- `widget_service/tests/compact_dsl_validate/_collect_asset_color_errors/01/sample_compact.dsl`
- `widget_service/tests/compact_dsl_validate/coverage.json`
- `widget_service/tests/fixtures/compact_validation_baseline.json`
- `widget_service/tests/fixtures/compact_validation_rule_inventory.json`
- `widget_service/tests/test_asset_url_mapper.py`
- `widget_service/tests/test_compact_dsl_a2ui_converter.py`
- `widget_service/tests/test_compact_dsl_validator.py`
- `widget_service/tests/test_compact_prompt_bundle.py`
- `widget_service/tests/test_compact_validation_architecture.py`
- `widget_service/tests/test_compact_validation_assets.py`
- `widget_service/tests/test_compact_validation_equivalence.py`
- `widget_service/tests/test_compact_validation_numeric_display.py`

#### 修复反馈与集成测试（11 个文件）

- `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/repair.md`
- `widget_service/cloud/repair_compact_dsl.py`
- `widget_service/cloud/services/artifact_store.py`
- `widget_service/cloud/services/generation_pipeline.py`
- `widget_service/cloud/services/prompt_builder.py`
- `widget_service/cloud/services/widget_generation_service.py`
- `widget_service/tests/test_compact_validation_fusion.py`
- `widget_service/tests/test_compact_validation_fusion_followup.py`
- `widget_service/tests/test_compact_validation_repair_integration.py`
- `widget_service/tests/test_compact_validation_restoration_integration.py`
- `widget_service/tests/test_compact_validation_diagnostics.py`

## 最新 main 同步与三提交重整

2026-10-12 再次同步 main 到 `7cfde5d0`，纳入 `15fbdef8` 的双业务模板补充及 `7cfde5d0` 的
2x2 留白调整。旧 PR 分支保存在 `codex/backup-pr423-before-main-sync-20261012`。
提交仍按上节的文档（9 文件）、校验（51 文件）、反馈（11 文件）三组组织，文件清单不变。

冲突仅发生在总方案的主内容槽说明：保留最新主线的合规槽位与自适应条件，同时保留分类重构
不重新启用历史辅助规则的边界。自动合并后额外逐项核对：

- DataDisplay 支持短文本结论、18fp 视觉变体及 supportingText 动态绑定；转换函数 AST 与最新 main 相同。
- InfoBlock 补色函数和高阶展开入口 AST 与同步前本分支相同，未重新引入 PR497 全局填色门禁。
- 模板目录全部文件与最新 main 完全一致；保留新增电量、耳机、天气双业务模板。
- Prompt、共享绑定合同及视觉 Recipe 保留最新主线更新；既有分类模块、修复反馈与 SVG 描述策略保留。

验证：专项 455 passed，0 failed；扩大回归 342 passed、6 failed，另有 35 subtests passed。
扩大范围覆盖 Compact 转换器、校验器、正式示例、JSX 提示词与新增 Support 模板扩展。
纯最新主线同范围为 348 passed、6 failed、35 subtests passed；本分支按确认要求撤下了
PR497 的 6 项强制填色测试，因此通过数相差 6。失败 ID 集合完全相同，均为旧 W9／hero 预期；不算作通过。
Ruff、差异空白检查通过。没有执行全量测试、真实模型批跑或端侧渲染。
本地报告为 TEMP 下 `compact-main-sync-focused.xml`、`compact-main-sync-expanded.xml`、
`compact-main-sync-baseline.xml` 及对应 log。

## 标题图标融合：保留既有提交

2026-10-12 合入 main `bf022115`，包括 `9ec6947f` 的 22 个彩色 SVG 与标题图标、anchor 选型更新。
采用新增 merge commit，第一父提交为 `5e41778e`，第二父提交为 `bf022115`；已有三组重构提交及后续
CodeCheck 提交全部保留，不执行 rebase、squash、amend 或强制推送。
同步前备份为 `codex/backup-pr423-before-title-merge-20261012`。

冲突发生在总方案、旧兼容入口和转换器测试三处。兼容入口维持原导出，主线新增检查迁入现有分类：

| 内容 | 合并后的落点与处理 |
|---|---|
| 标题图标输入合同 | 共享 `compact_high_level_components.py` 保留主线支持；非法显式颜色（包括 null 和非字符串）返回正常校验异常 |
| 标题素材来源 | `semantic/asset_references.py` 登记 SingleLineTitle，沿用 `semantic/effective.py` 的候选集合检查与原始位置 |
| 标题 SVG 颜色 | `semantic/layout/assets.py` 只对候选内可染色 SVG 要求显式颜色；原色 SVG 可省略，不在转换器统一强制补色 |
| 标题高度 | `semantic/layout/geometry.py` 读取共享 Recipe 的 withIcon 变体，预占与子树最小高度均按 20vp／12vp 计算 |
| 主线其它改动 | 保留 anchor 选型、Plan、JSX 标题图标、视觉 Recipe、在线 Skill 说明和新增素材 |
| 旧功能边界 | InfoBlock 原色与默认补色函数、高阶展开入口 AST 与第一父提交一致；模板目录与 main 完全一致；既有 jsx_runner 与 constants 的 CodeCheck 改写未动 |

不新增结构化错误码；标题素材错误继续沿用 COMPACT_ASSET_NOT_ALLOWED、COMPACT_SVG_FILL_COLOR_MISSING，
进入既有分组、可选建议与模型错误文本链路。没有改变模板跳过规则，也没有恢复历史布局门禁。
Compact 组件提示词同步注明可染色与原色 SVG 的区别，避免模型被要求给原色标题图标强制填色。

### 本次验证结果

- 专项 16 个测试文件：532 passed、1 failed，包括新加标题融合 23 项、既有素材自动配色、结构化反馈、
  模板跳过、公开入口基线、组件运行时、提示词、Plan 与 CodeCheck 回归。
- 扩大 5 个测试文件：347 passed、6 failed、35 subtests passed，覆盖转换器、校验器、正式示例、JSX 提示词、
  Support 模板扩展。
- 纯 main `bf022115` 在扩大范围加 Plan／composition planner 的 7 个文件上：372 passed、7 failed、
  35 subtests passed。通过 XML 比较，本分支两组测试的失败 ID 并集与纯 main 完全一致，没有新增失败。
- 冻结行为快照保持不变；112 项回放中的两项旧“标题不允许 icon/fillColor”由测试里的显式预期映射登记为
  可染色 SVG 缺色和无图标却指定颜色。其余历史预期不改，不能以重新采集当前输出掩盖差异。
- 对本次全部变动 Python 文件运行 Ruff；执行暂存差异空白检查，均通过。
- 未执行全量测试、真实模型批跑、端侧渲染或外部 CodeCheck 服务。没有修改线上状态或重启本地调试服务。

已复现的 7 项主线失败（不计作通过）：

| 测试 | 原因 |
|---|---|
| test_rejects_sparse_w9_without_vertical_center_and_layout_weight | 仍期待已停用的旧 W9 校验抛错 |
| test_rejects_sparse_w9_with_legacy_backboard_geometry | 仍期待已停用的旧 W9 校验抛错 |
| test_rejects_centered_single_value_hero_without_safe_box | 仍期待旧 hero 专项门禁 |
| test_rejects_centered_single_value_hero_that_exceeds_width_pressure | 仍期待旧 hero 专项门禁 |
| test_rejects_centered_single_value_hero_that_exceeds_height_pressure | 实际由高度预算拒绝，测试期待旧 hero 文案 |
| test_rejects_large_hero_for_peer_metrics_on_150vp_card | 仍期待旧 hero 专项门禁 |
| test_processor_reports_missing_plan_fact_with_dedicated_code | 输入使用已禁用的直接 Text，实际返回 Plan 和组件两条错误，测试期待一条 |

本地报告：TEMP 下 `compact-title-merge-focused.xml`、`compact-title-merge-expanded.xml`、
`compact-title-merge-baseline.xml` 与同名 log。最后一份由独立 git archive 的纯主线目录执行，未污染当前工作区。

### 本次合并提交文件清单

下表以第一父提交为比较基准，包含直接带入的主线文件及本次冲突适配。未出现在差异中的兼容入口保持原样。

共 62 个文件；逐项用途如下。

| 文件 | 用途 |
|---|---|
| `docs/compact-dsl-validator-refactor/Compact_DSL_Fusion融合记录.md` | 记录冲突取舍、验证结果与完整提交文件清单 |
| `docs/compact-dsl-validator-refactor/Compact_DSL校验器重构方案_v3.md` | 更新当前基线及标题图标分类边界 |
| `docs/compact-dsl-validator-refactor/Compact_DSL现有校验规则分类清单_v1.md` | 登记标题素材、颜色与高度校验归属 |
| `docs/compact-dsl-validator-refactor/Compact_DSL重构实施与验证记录.md` | 同步最新合并方式、回归结果及限制 |
| `docs/云侧方案设计.md` | 融合主线标题图标与 anchor 规则，保留 SVG 描述策略 |
| `resources/base/media/ic_batteryTemperature_bule.svg` | 直接合入主线新增彩色 SVG 素材，内容不改 |
| `resources/base/media/ic_batteryTemperature_purple.svg` | 直接合入主线新增彩色 SVG 素材，内容不改 |
| `resources/base/media/ic_batteryTemperature_yellow.svg` | 直接合入主线新增彩色 SVG 素材，内容不改 |
| `resources/base/media/ic_call_bule.svg` | 直接合入主线新增彩色 SVG 素材，内容不改 |
| `resources/base/media/ic_call_purple.svg` | 直接合入主线新增彩色 SVG 素材，内容不改 |
| `resources/base/media/ic_call_yellow.svg` | 直接合入主线新增彩色 SVG 素材，内容不改 |
| `resources/base/media/ic_ring_bule.svg` | 直接合入主线新增彩色 SVG 素材，内容不改 |
| `resources/base/media/ic_ring_purple.svg` | 直接合入主线新增彩色 SVG 素材，内容不改 |
| `resources/base/media/ic_ring_yellow.svg` | 直接合入主线新增彩色 SVG 素材，内容不改 |
| `resources/base/media/ic_sportsHealth_bule.svg` | 直接合入主线新增彩色 SVG 素材，内容不改 |
| `resources/base/media/ic_sportsHealth_purple.svg` | 直接合入主线新增彩色 SVG 素材，内容不改 |
| `resources/base/media/ic_sportsHealth_yellow.svg` | 直接合入主线新增彩色 SVG 素材，内容不改 |
| `resources/base/media/ic_storage_bule.svg` | 直接合入主线新增彩色 SVG 素材，内容不改 |
| `resources/base/media/ic_storage_purple.svg` | 直接合入主线新增彩色 SVG 素材，内容不改 |
| `resources/base/media/ic_storage_yellow.svg` | 直接合入主线新增彩色 SVG 素材，内容不改 |
| `resources/base/media/ic_sun.svg` | 直接合入主线新增彩色 SVG 素材，内容不改 |
| `resources/base/media/ic_temperature_bule.svg` | 直接合入主线新增彩色 SVG 素材，内容不改 |
| `resources/base/media/ic_temperature_purple.svg` | 直接合入主线新增彩色 SVG 素材，内容不改 |
| `resources/base/media/ic_temperature_yellow.svg` | 直接合入主线新增彩色 SVG 素材，内容不改 |
| `resources/base/media/ic_warning_bule.svg` | 直接合入主线新增彩色 SVG 素材，内容不改 |
| `resources/base/media/ic_warning_purple.svg` | 直接合入主线新增彩色 SVG 素材，内容不改 |
| `resources/base/media/ic_warning_yellow.svg` | 直接合入主线新增彩色 SVG 素材，内容不改 |
| `skills/harmony-card-generation-online/SKILL.md` | 保留主线在线生成对 anchor 的选择说明 |
| `skills/harmony-card-generation-online/references/runtime-guide.md` | 保留主线在线生成对 anchor 的选择说明 |
| `widget_service/cloud/data/capabilities/app-11.7.7.300_rom-7.0/asset_capabilities.json` | 保留主线新增素材候选说明 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/combinations/2x2.md` | 融合主线标题图标与 anchor 提示规则 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/components/2x2.md` | 融合主线标题图标与 anchor 提示规则 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/components/common.md` | 融合主线标题图标与 anchor 提示规则；Compact 标题颜色按候选描述区别处理 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/composition.md` | 融合主线标题图标与 anchor 提示规则 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/core.md` | 融合主线标题图标与 anchor 提示规则 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/fewshots/2x2.md` | 融合主线标题图标与 anchor 提示规则 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/layouts/2x2.md` | 融合主线标题图标与 anchor 提示规则 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/layouts/common.md` | 融合主线标题图标与 anchor 提示规则 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/plan.md` | 融合主线标题图标与 anchor 提示规则 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/runtime/visual-recipes-v1.json` | 保留主线 SingleLineTitle.withIcon 视觉变体 |
| `widget_service/cloud/services/card_validation/compact_validation/semantic/asset_references.py` | 原始素材引用登记增加 SingleLineTitle |
| `widget_service/cloud/services/card_validation/compact_validation/semantic/layout/assets.py` | 标题可染色 SVG 复用显式颜色检查与原色豁免 |
| `widget_service/cloud/services/card_validation/compact_validation/semantic/layout/geometry.py` | 按标题是否有图标读取 Recipe 高度 |
| `widget_service/cloud/services/card_validation/字段约束与演进记录.md` | 登记标题 icon／fillColor 字段与高度变体规则 |
| `widget_service/cloud/services/compact_composition_planner.py` | 保留主线 anchor 构图选型更新 |
| `widget_service/cloud/services/compact_high_level_components.py` | 融合标题图标转换与合同，保留原色 SVG、补充颜色类型异常 |
| `widget_service/cloud/services/compact_plan.py` | 保留主线 anchor 规划与组件候选更新 |
| `widget_service/cloud/services/multi_step_generation/design-system-runtime.jsx` | 保留主线 JSX 标题图标运行时 |
| `widget_service/cloud/services/multi_step_generation/jsx_to_a2ui/catalog/contracts.py` | 保留主线 JSX 标题属性合同与静态图标约束 |
| `widget_service/cloud/services/multi_step_generation/jsx_to_a2ui/converters/high_level/single_line_title.py` | 保留主线 JSX 标题图标转换 |
| `widget_service/cloud/services/multi_step_generation/references/prompt_source/components/components_common.md` | 融合主线标题图标与 anchor 提示规则 |
| `widget_service/cloud/services/multi_step_generation/references/prompt_source/composition/composition_common.md` | 融合主线标题图标与 anchor 提示规则 |
| `widget_service/cloud/services/multi_step_generation/references/prompt_source/core/core_common.md` | 融合主线标题图标与 anchor 提示规则 |
| `widget_service/tests/test_compact_component_runtime.py` | 主线标题 withIcon Recipe 回归 |
| `widget_service/tests/test_compact_composition_planner.py` | 主线 anchor 组合求解回归 |
| `widget_service/tests/test_compact_dsl_a2ui_converter.py` | 保留主线标题图标展开及高度反例，排除旧全局填色测试 |
| `widget_service/tests/test_compact_dsl_validator.py` | 保留主线标题合法素材与非法来源回归 |
| `widget_service/tests/test_compact_plan.py` | 保留主线 anchor 规划回归 |
| `widget_service/tests/test_compact_validation_assets.py` | 补充标题原始素材范围及各类 SVG 描述策略 |
| `widget_service/tests/test_compact_validation_equivalence.py` | 保持冻结快照，仅登记两项标题合同预期变化 |
| `widget_service/tests/test_compact_validation_title_icon.py` | 新增 23 项公开入口、颜色异常、反馈与高度预算交叉回归 |
| `widget_service/tests/test_jsx_runner_prompt.py` | 保留主线 JSX 标题图标提示词与合同回归 |

## 同日晚间继续融合 #498

标题图标已保存为合并提交 `c6f333ec`。提交前再次检查远端发现 main 于 20:41 新增 `a19fef3a`（#498），
因此以第二个新增 merge commit 继续同步，第一父提交为 `c6f333ec`、第二父提交为 `a19fef3a`。
之前的所有提交原样保留，后续也不 amend 第一个合并提交。

本批仅旧兼容入口产生文本冲突，保留导出结构，并把主线逻辑迁入已有分类：

- `api.py` 在宽高预算前使用共享 `normalize_mixed_font_text_rows`，绑定等校验仍使用原工作树。
- `semantic/layout/geometry.py` 保留小卡整树溢出计量与 2vp 高度容差；结构化诊断补充 heightTolerance，
  不对宽度或 2x4 放宽，也不修改标题 12vp／20vp 的实际展开高度。
- `semantic/layout/text_width.py` 采用主线完整显示文本与可选标签压力测量；4 个迁移辅助函数 AST 与主线一致。
- `flows/text_pressure.py` 编排修复压力估计，兼容入口导出 small_card_text_pressure，解析失败返回空提示并记录原因。
- 原始模型源仍由已有上下文与 Trace 保留；外层重排、首次显示规格保护和提示词新增参数按主线接入。
  既有结构化诊断、分组和可选 fixHint 保留，不靠解析新错误文案推导事实。
- 保留主线数值短单位规范化、混合字号对齐、正文完整性、嵌套正文与 Plan／调试测试更新。
  InfoBlock 和标题 SVG 颜色函数仍与第一批融合一致，不重新引入 PR497 全局填色循环。

### 最终验证与环境差异

- 分类及主线专项 16 文件：533 passed；新增修复压力／高度容差测试 4 passed，合计 537 passed。
- 扩大回归 13 文件：显式 `WIDGET_SERVICE_ENABLE_A2UI_MODEL_MOCK=true` 时 487 passed，另有 35 subtests passed。
  共计 1024 项通过、0 项失败；一条 Starlette TestClient 的上游弃用警告不影响结果。
- 初次扩大回归在本机关闭 mock 的配置下为 483 passed、4 failed：素材映射测试用 DSL 桩代替模型，
  进入 Plan 阶段后无法解析为 JSON。独立纯 main 默认 mock 模式 488 passed；将其 mock 同样关闭后，
  素材测试复现完全相同的 4 个失败（19 passed、4 failed）。未复制本地密钥配置，也未改写测试来掩盖问题。
- 上一批的 6 项旧布局和 1 项 Plan 失败已由 #498 的主线测试更新修复；此处不沿用上一批失败结论。
- 新源码通过 Ruff；暂存差异空白检查通过；共享迁移函数 AST、模板主线内容及先前 CodeCheck 改写已核对。
  第一批新带入的 2 个 JSON 可解析、22 个 SVG XML 可解析且与主线 blob 一致。
- 未执行全量测试、真实模型批跑、端侧渲染或外部 CodeCheck。模型 mock 仅设置于测试子进程，未改服务配置。

报告位于 TEMP：`compact-498-merge-focused.xml`、`compact-498-merge-expanded.xml`（初次失败）、
`compact-498-merge-expanded-mock.xml`、`compact-498-merge-baseline.xml`、
`compact-498-baseline-assets-real-mode.xml` 及各自 log。

### 第二个合并提交完整文件清单

以下以第一父提交 `c6f333ec` 为比较基准，包含直接带入主线的文件与分类适配。

共 37 个文件。

| 文件 | 用途 |
|---|---|
| `docs/compact-dsl-validator-refactor/Compact_DSL_Fusion融合记录.md` | 同步主线方案、分类归属、字段演进或本次验证记录 |
| `docs/compact-dsl-validator-refactor/Compact_DSL校验器重构方案_v3.md` | 同步主线方案、分类归属、字段演进或本次验证记录 |
| `docs/compact-dsl-validator-refactor/Compact_DSL现有校验规则分类清单_v1.md` | 同步主线方案、分类归属、字段演进或本次验证记录 |
| `docs/compact-dsl-validator-refactor/Compact_DSL重构实施与验证记录.md` | 同步主线方案、分类归属、字段演进或本次验证记录 |
| `docs/云侧方案设计.md` | 同步主线方案、分类归属、字段演进或本次验证记录 |
| `widget_service/cloud/custom/mock.design-compact-dsl-2x2.dat` | 主线小卡 mock 示例更新 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/combinations/2x2.md` | 主线小卡组合、组件与布局指导更新 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/components/common.md` | 主线小卡组合、组件与布局指导更新 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/layouts/2x2.md` | 主线小卡组合、组件与布局指导更新 |
| `widget_service/cloud/services/card_validation/compact_dsl_validator.py` | 兼容导出新增 small_card_text_pressure，保留分类入口 |
| `widget_service/cloud/services/card_validation/compact_validation/api.py` | 预算前接入共享文字对齐规范化 |
| `widget_service/cloud/services/card_validation/compact_validation/flows/text_pressure.py` | 编排修复压力估计，保留失败时可选提示语义 |
| `widget_service/cloud/services/card_validation/compact_validation/semantic/layout/geometry.py` | 接入主线整树最小占用与 2vp 容差，保留结构化诊断 |
| `widget_service/cloud/services/card_validation/compact_validation/semantic/layout/text_width.py` | 复用主线完整显示文本与标签压力测量 |
| `widget_service/cloud/services/card_validation/字段约束与演进记录.md` | 同步主线方案、分类归属、字段演进或本次验证记录 |
| `widget_service/cloud/services/compact_composition_context.py` | 主线完整显示文本、首次显示规格与上下文更新 |
| `widget_service/cloud/services/compact_composition_planner.py` | 主线小卡组合容量更新 |
| `widget_service/cloud/services/compact_dsl_a2ui_converter.py` | 主线混合字号对齐与嵌套正文完整性 |
| `widget_service/cloud/services/compact_high_level_components.py` | 主线小卡短单位规范化及等价格式整改 |
| `widget_service/cloud/services/compact_outer_recomposition.py` | 主线有界外层重排，保留事实、动作和字体规格 |
| `widget_service/cloud/services/compact_plan.py` | 主线小卡 Plan 合法性与容量更新 |
| `widget_service/cloud/services/generation_pipeline.py` | 外层重排、Trace 与结构化校验反馈共同接入 |
| `widget_service/cloud/services/prompt_builder.py` | 保留结构化模型说明，接入原规格与文字压力提示 |
| `widget_service/cloud/services/widget_generation_service.py` | 修复链路保留首次显示规格及已有上下文 |
| `widget_service/tests/test_asset_mapping_generation.py` | 保留 #498 对 asset_mapping_generation 的回归更新 |
| `widget_service/tests/test_asset_url_mapper.py` | 保留 #498 对 asset_url_mapper 的回归更新 |
| `widget_service/tests/test_compact_dsl_a2ui_converter.py` | 保留 #498 对 compact_dsl_a2ui_converter 的回归更新 |
| `widget_service/tests/test_compact_dsl_validator.py` | 保留 #498 对 compact_dsl_validator 的回归更新 |
| `widget_service/tests/test_compact_nested_text_bottom.py` | 保留 #498 对 compact_nested_text_bottom 的回归更新 |
| `widget_service/tests/test_compact_plan.py` | 保留 #498 对 compact_plan 的回归更新 |
| `widget_service/tests/test_compact_validation_small_card_merge.py` | 新增 4 项压力提示、异常兼容及高度容差交叉回归 |
| `widget_service/tests/test_compact_validation_title_icon.py` | 高度反例适配主线 2vp 容差，仍检查有无图标的 Recipe |
| `widget_service/tests/test_debug_quality_score.py` | 保留 #498 对 debug_quality_score 的回归更新 |
| `widget_service/tests/test_debug_quality_workflow.py` | 保留 #498 对 debug_quality_workflow 的回归更新 |
| `widget_service/tests/test_generation_trace_recorder.py` | 保留 #498 对 generation_trace_recorder 的回归更新 |
| `widget_service/tests/test_model_routing.py` | 保留 #498 对 model_routing 的回归更新 |
| `widget_service/tests/test_template_ring_geometry.py` | 保留 #498 对 template_ring_geometry 的回归更新 |


## PR 范围收敛复核（2026-10-12）

本节记录 `16d187c6` 之后的清理，覆盖前文“保留 JSX CodeCheck 整改”的当前状态说明；前文提交和验收结果
保留为历史记录。已有 commit 均不改写，以新增普通提交清理净差异。

### 撤销与精简

- 撤销 JSX Runner 的 8 个源码文件改动，删除仅服务于这些整改的 `test_jsx_runner_codecheck.py`。
  它们属于独立 CodeCheck／CLI 导入兼容整改，与 Compact 分类及修复反馈没有依赖。
  8 个文件与共同基线 `a19fef3a`、本轮检查时的最新 main `5f6d59e1` 均一致。
- 公共上下文仅保留有生产调用方的组件 ID 缓存，移除未被规则使用的组件图快照及 first／last／all 父节点缓存。
  原始组件列表、重复 ID、重复 child 及各规则已有的父子查询方式保留；对应测试改为验证真实调用的索引行为。
- 恢复 main 的两个正向测试：位图无需填色、PillButton 自动填色的 SVG 可通过；恢复四处转换测试中与其测试目标
  无关的显式颜色字段。撤销 PR497 的全局 SVG 填色规则，不应连带删除这些合法场景或改动无关测试输入。

### 其余净差异的必要性

以 PR 共同基线为比较基准，净差异从 83 个文件收敛为 74 个；JSX Runner 源码和专属整改测试不再出现在净差异中。
本次没有为范围清理额外合并 main 的后续 #506；该更新不属于本次撤销任务。

| 保留范围 | 必要性 |
|---|---|
| Compact 分类模块、旧入口、诊断、可选建议及来源定位 | 重构主体；维持公开异常行为并组织模型修复信息 |
| legacy hero 兼容模块 | 既有直接导入测试仍使用；不因当前主流程不调用就移除兼容符号 |
| pipeline、prompt_builder、artifact_store、独立修复入口和 generation_service | 传递诊断与可信上下文，保留最终抛错和修复链路 |
| 嵌套素材地址还原、SVG 描述策略、数值误用检查及对应提示词 | 已确认恢复的规则；使原始组件校验与高阶组件展开相容 |
| Compact 常量的正则长行拆分 | 属于本模块的等价格式整改，正则内容和匹配语义不变 |
| 冻结行为样本、规则清单及专项／集成测试 | 验证错误顺序、模板边界和高阶组件兼容；历史快照不重生成 |
| 总方案、专项方案、字段演进、AGENTS 分类落点 | 对应已实施的职责、行为及协作约束 |
| README 与校验、重试入门指南 | 用户明确要求将 #437 文档纳入本 PR |

本轮按上述用途核查净差异，未发现其他应撤销的独立功能整改。

### 清理后验证

- 核心专项 17 文件：519 passed；扩大回归 12 文件：485 passed，另有 35 subtests passed。
  合计 1004 项通过、0 项失败。扩大回归显式启用模型 mock，未改变本地服务配置。
- PR 净差异中的全部 53 个 Python 文件 Ruff 通过。
- 恢复后的 8 个 JSX 文件单独检查有 168 条 main 已有的 Ruff 告警（I001 6、B010 25、E501 126、B905 8、B023 3）。
  已核对这些文件与 main 一致；本轮不再次整改，否则会重新扩大 PR 范围。
- 差异空白检查通过。存在一条 Starlette TestClient 上游弃用警告。
- 未执行全量测试、真实模型批跑、端侧渲染和外部 CodeCheck。

报告位于 TEMP：`compact-scope-focused.xml`、`compact-scope-expanded.xml` 及对应 log；
JSX 基线告警为 `compact-scope-jsx-ruff-main.json`。

### 本次清理提交完整文件清单

以下 17 个文件是相对 `16d187c6` 的清理提交清单，与 PR 相对 main 的净差异清单不同。

| 文件 | 用途 |
|---|---|
| `docs/compact-dsl-validator-refactor/Compact_DSL_Fusion融合记录.md` | 记录清理范围、保留依据、验证及完整文件清单 |
| `docs/compact-dsl-validator-refactor/Compact_DSL校验器重构方案_v3.md` | 明确只缓存实际使用的 ID 索引，父节点语义作为兼容约束 |
| `docs/compact-dsl-validator-refactor/Compact_DSL现有校验规则分类清单_v1.md` | 移除将 JSX CodeCheck 纳入本次重构的说明 |
| `docs/compact-dsl-validator-refactor/Compact_DSL重构实施与验证记录.md` | 同步本次清理后的最新验收结果 |
| `widget_service/cloud/services/card_validation/compact_validation/context.py` | 删除无调用方的父节点缓存，保留 ID 索引 |
| `widget_service/cloud/services/multi_step_generation/jsx_runner/agent.py` | 撤销独立 JSX 整改，与 main 一致 |
| `widget_service/cloud/services/multi_step_generation/jsx_runner/fewshot_retrieval.py` | 撤销独立 JSX 整改，与 main 一致 |
| `widget_service/cloud/services/multi_step_generation/jsx_runner/info_block_fallback.py` | 撤销独立 JSX 整改，与 main 一致 |
| `widget_service/cloud/services/multi_step_generation/jsx_runner/python_geometry.py` | 撤销独立 JSX 整改，与 main 一致 |
| `widget_service/cloud/services/multi_step_generation/jsx_runner/python_validate.py` | 撤销独立 JSX CLI 导入调整，与 main 一致 |
| `widget_service/cloud/services/multi_step_generation/jsx_runner/resources.py` | 撤销独立 JSX 整改，与 main 一致 |
| `widget_service/cloud/services/multi_step_generation/jsx_runner/validation.py` | 撤销独立 JSX 整改，与 main 一致 |
| `widget_service/cloud/services/multi_step_generation/jsx_runner/workflow.py` | 撤销独立 JSX 整改，与 main 一致 |
| `widget_service/tests/test_compact_dsl_a2ui_converter.py` | 恢复四处无关测试输入的原始颜色字段 |
| `widget_service/tests/test_compact_dsl_validator.py` | 恢复两项不应删除的 main 正向测试 |
| `widget_service/tests/test_compact_validation_diagnostics.py` | 验证 ID 索引、原始顺序和重复项兼容 |
| `widget_service/tests/test_jsx_runner_codecheck.py` | 删除与本次重构无关的 JSX 专属整改测试 |


## 最终设计复核与单提交整理（2026-10-12）

用户在本轮明确授权重新审视设计实现并将 PR 合成一个提交；这替代此前不改写历史的要求。
旧头 `1acdb936` 已保存在本地备份分支 `codex/backup-compact-before-review-squash-20261012`。
同步 main `69c153f5`（包含 #506、#500）后，将全部净差异作为它的一个直接子提交提交，使用精确 lease 推送。
前文的提交编号与测试数量作为历史记录保留，不代表当前 PR 仍有多条提交。

### 设计对照与修正

| 设计要求 | 复核结果 |
|---|---|
| 两级分类与职责边界 | 保留语法／语义分类；32 个活动结构化规则各有唯一归属，解析、共享组件合同及完整产物校验不重复实现 |
| 顺序与兼容 | 旧构造、异常字符串、错误顺序和去重保留；53 个迁移辅助函数与当前 main 的 AST 完全相同，复合函数按职责拆分 |
| 事实、硬约束、建议分离 | 修正高度溢出与进度对象错误的混写，组件白名单 message 仅描述事实；旧 legacyMessage 原样保留 |
| 可配置建议 | 8 条默认建议；按错误码注册专用函数的可选接口保留，未接通的环境条件不臆测；失败只影响建议 |
| 原文位置与事实来源 | 原文、预处理文本和展开组件分开；无法证明的原文位置省略，expanded 事实明确标识 |
| 模型说明与记录 | 模型请求边界组织 message，保留外层 stage/code；日志与产物保留旧说明及诊断，格式化失败回退旧说明 |
| Fusion 与模板 | 已批准的有限素材／数值规则保留；高阶组件和模板豁免不受影响，退出的旧规则不重新启用 |
| #506 增量融合 | 合并两个新增参数／导入冲突；保留 Plan 警告、程序批准省略与累计省略、重试策略；建议不得覆盖授权范围 |

更新设计文档中遗留的 asset 子类、缺少 expanded 的来源枚举、ActionUnit 例子和修改固定高度的旧建议示例。
新增／调整交叉测试：有无 fixHint 均保留硬约束，旧异常文案保持不变；Plan 错误、警告、累计省略与 Compact 诊断共存。
冻结样本原文件不变：#506 的 compact EventCard 项间距由 8vp 改为 4vp，三项高度由 112vp 降至 104vp，
原 case91 现合法，已在纯 main 验证后登记一个精确预期变更；此前两个标题合同变更继续保留。

提交前新增的 #500 天气数值 schema 与模板更新原样同步；增加 5 个相关测试文件，142 项全部通过。

### 最终验证与限制

- 实际执行 44 个测试文件：1653 passed、14 failed、1 skipped、1 deselected，另有 55 subtests passed。
- 重构专项 416 项全部通过（包含在上述数量中），冻结行为回放 112 项通过。
- 14 个失败在独立纯 main `69c153f5` 快照逐项复现，失败 ID 集合完全相同；未通过改写旧测试消除主线问题。
- 初次扩大回归中的外部模型认证测试返回 HTTP 401；最终回归排除该单项，未重复发起外部请求。
- PR 净差异 53 个 Python 文件 Ruff 通过；差异空白检查通过。JSX Runner 与 main 一致，不再出现在净差异中。
- 初次冻结样本差异按上述主线 EventCard 变化登记后通过；本轮无已知新增阻塞失败。
- 未执行仓库全量测试、真实模型批跑、端侧渲染和外部 CodeCheck；存在 Starlette TestClient 弃用警告。
  #506 的 renderer 文件直接沿用 main，无本 PR 净差异，未额外执行前端测试。

纯 main 已有失败分布：重试接口旧样例 3 项、历史 hero 规则预期 4 项、服务配置／能力注册／旧提示词及
旧转换组件预期 7 项。具体失败如下：

- `tests/test_compact_dsl_interface_retry_routes.py::test_real_generation_pipeline_retries_to_valid_artifact[model]`
- `tests/test_compact_dsl_interface_retry_routes.py::test_real_generation_pipeline_retries_to_valid_artifact[validation]`
- `tests/test_compact_dsl_interface_retry_routes.py::test_real_generation_pipeline_retries_to_valid_artifact[upload]`
- `tests/test_compact_hero_typography.py::test_template_keeps_other_compact_validations[empty-non-empty]`
- `tests/test_compact_hero_typography.py::test_non_template_formatted_readout_keeps_original_contract[expression]`
- `tests/test_compact_hero_typography.py::test_non_template_formatted_readout_keeps_original_contract[inherited-width]`
- `tests/test_compact_hero_typography.py::test_non_template_formatted_readout_keeps_original_contract[percent-description]`
- `tests/test_service_units.py::test_anyio_thread_pool_uses_configured_capacity`
- `tests/test_service_units.py::test_design_compact_few_shots_are_disabled_by_default_and_can_be_enabled`
- `tests/test_service_units.py::test_phase_two_version_returns_phase_two_capability_overview`
- `tests/test_service_units.py::test_phase_two_version_returns_phase_two_capability_schemas`
- `tests/test_service_units.py::test_design_compact_edit_prompt_contains_previous_design_token`
- `tests/test_service_units.py::test_design_converter_expands_latest_design_tokens`
- `tests/test_service_units.py::test_missing_action_unit_on_click_enters_validation_repair`

外部认证项：`tests/test_service_units.py::test_model_runtime_collects_llmclient_stream`。
报告位于 TEMP：`compact-final-review-latest.xml`、`compact-final-review-latest-main.xml` 及 log；
初次运行保存在 `compact-final-review.xml`，测试文件清单为 `compact-final-review-latest-test-files.txt`。

### 单提交完整文件清单

相对 main `69c153f5` 共 74 个文件。该清单是最终单提交范围，main 带入的 renderer、Plan 和运行时文件
不重复计入 PR 改动；此前 JSX 整改也不计入。

| 文件 | 用途 |
|---|---|
| `AGENTS.md` | 记录 Compact 改动归属和校验／建议／编排边界检查流程 |
| `README.md` | 补充用户要求纳入的校验重试指南入口 |
| `docs/compact-dsl-validator-refactor/Compact_DSL_Fusion融合记录.md` | 记录逐次融合、设计复核、验证与完整文件清单 |
| `docs/compact-dsl-validator-refactor/Compact_DSL校验器重构方案_v3.md` | 维护当前设计、历史边界及事实／建议解耦约定 |
| `docs/compact-dsl-validator-refactor/Compact_DSL现有校验规则分类清单_v1.md` | 维护规则归属和当前生效范围 |
| `docs/compact-dsl-validator-refactor/Compact_DSL重构实施与验证记录.md` | 登记实施结果、基线和最新验收限制 |
| `docs/云侧方案设计.md` | 同步分类、反馈、已批准规则恢复及主线兜底边界 |
| `docs/校验、重试与兜底机制入门指南.md` | 合入用户指定的 #437 入门说明 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/components/2x2.md` | 同步已确认 SVG 颜色策略及数值组件选型指导 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/components/2x4.md` | 同步已确认 SVG 颜色策略及数值组件选型指导 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/components/common.md` | 同步已确认 SVG 颜色策略及数值组件选型指导 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/composition.md` | 同步已确认 SVG 颜色策略及数值组件选型指导 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/core.md` | 同步已确认 SVG 颜色策略及数值组件选型指导 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/repair.md` | 说明结构化错误阅读与程序授权范围 |
| `widget_service/cloud/data/validator_rules/compact/repair_hints.json` | 提供 8 条可选默认修复建议，规则不内嵌建议 |
| `widget_service/cloud/repair_compact_dsl.py` | 独立修复入口传递可选建议上下文 |
| `widget_service/cloud/services/artifact_store.py` | 允许保存诊断嵌套对象，保留历史字符串字段 |
| `widget_service/cloud/services/asset_url_mapper.py` | 还原 InfoBlock 与 NumericRatioStack 的嵌套素材引用 |
| `widget_service/cloud/services/card_validation/compact_dsl_validator.py` | 保留公开异常、校验函数和压力提示的兼容导出 |
| `widget_service/cloud/services/card_validation/compact_validation/__init__.py` | 声明职责包 |
| `widget_service/cloud/services/card_validation/compact_validation/api.py` | 保留主线规则执行顺序，编排定位与可选建议 |
| `widget_service/cloud/services/card_validation/compact_validation/compatibility/__init__.py` | 声明职责包 |
| `widget_service/cloud/services/card_validation/compact_validation/compatibility/hero.py` | 兼容旧私有函数直接调用，不恢复主流程调用 |
| `widget_service/cloud/services/card_validation/compact_validation/constants.py` | 共享原有常量及等价正则长行拆分 |
| `widget_service/cloud/services/card_validation/compact_validation/context.py` | 组织本轮事实并仅缓存实际使用的组件 ID 索引 |
| `widget_service/cloud/services/card_validation/compact_validation/diagnostics.py` | 事实模型、旧异常兼容、按旧文案有序分组 |
| `widget_service/cloud/services/card_validation/compact_validation/flows/__init__.py` | 声明职责包 |
| `widget_service/cloud/services/card_validation/compact_validation/flows/contracts.py` | 编排复合合同并保留原诊断顺序 |
| `widget_service/cloud/services/card_validation/compact_validation/flows/text_pressure.py` | 迁移主线修复压力提示，失败保持可选 |
| `widget_service/cloud/services/card_validation/compact_validation/model_feedback.py` | 生成模型说明副本并在失败时回退旧说明 |
| `widget_service/cloud/services/card_validation/compact_validation/repair_guidance.py` | 默认配置与可选专用函数接口，隔离建议失败 |
| `widget_service/cloud/services/card_validation/compact_validation/rule_catalog.py` | 登记 32 个稳定活动错误码 |
| `widget_service/cloud/services/card_validation/compact_validation/schema.py` | 复用数据声明、类型及路径查询 |
| `widget_service/cloud/services/card_validation/compact_validation/semantic/__init__.py` | 声明职责包 |
| `widget_service/cloud/services/card_validation/compact_validation/semantic/asset_references.py` | 登记原始高阶组件素材位置 |
| `widget_service/cloud/services/card_validation/compact_validation/semantic/bindings.py` | 绑定存在性及进度数值类型检查 |
| `widget_service/cloud/services/card_validation/compact_validation/semantic/cross_file.py` | 数据声明一致性及原有警告 |
| `widget_service/cloud/services/card_validation/compact_validation/semantic/display.py` | 展示语义检查，分离进度对象错误事实与建议 |
| `widget_service/cloud/services/card_validation/compact_validation/semantic/effective.py` | 当前事件与素材候选范围检查 |
| `widget_service/cloud/services/card_validation/compact_validation/semantic/layout/__init__.py` | 声明职责包 |
| `widget_service/cloud/services/card_validation/compact_validation/semantic/layout/assets.py` | 有限 SVG 漏色检查及原色豁免 |
| `widget_service/cloud/services/card_validation/compact_validation/semantic/layout/geometry.py` | 主线高度预算，分离错误事实与硬约束 |
| `widget_service/cloud/services/card_validation/compact_validation/semantic/layout/text_width.py` | 迁移主线完整文字与标签时长压力检查 |
| `widget_service/cloud/services/card_validation/compact_validation/semantic/numeric_display.py` | 仅恢复确定的数值组件误用检查 |
| `widget_service/cloud/services/card_validation/compact_validation/source_locations.py` | 保守定位原始 DSL，不将展开节点冒充原文 |
| `widget_service/cloud/services/card_validation/compact_validation/syntax/__init__.py` | 声明职责包 |
| `widget_service/cloud/services/card_validation/compact_validation/syntax/components.py` | 组件结构、事件结构和模型类型语法检查 |
| `widget_service/cloud/services/card_validation/compact_validation/syntax/expressions.py` | 表达式包装、引用与路径语法检查 |
| `widget_service/cloud/services/card_validation/compact_validation/text.py` | 复用文本、单位、绑定和数值查询 |
| `widget_service/cloud/services/card_validation/字段约束与演进记录.md` | 登记原始素材、标题与字段演进边界 |
| `widget_service/cloud/services/compact_high_level_components.py` | 恢复经确认的 SVG 原色／默认着色组件合同 |
| `widget_service/cloud/services/generation_pipeline.py` | 传递原文及建议条件，按旧错误分组适配诊断，保留主线 Plan 警告 |
| `widget_service/cloud/services/prompt_builder.py` | 只在模型请求边界将诊断副本组织成说明 |
| `widget_service/cloud/services/widget_generation_service.py` | 传递可信 create/edit 建议上下文，保留主线省略授权 |
| `widget_service/tests/compact_dsl_validate/_collect_asset_color_errors/01/expected.json` | 同步已确认 SVG 漏色场景与旧测试覆盖记录 |
| `widget_service/tests/compact_dsl_validate/_collect_asset_color_errors/01/sample_compact.dsl` | 同步已确认 SVG 漏色场景与旧测试覆盖记录 |
| `widget_service/tests/compact_dsl_validate/coverage.json` | 同步已确认 SVG 漏色场景与旧测试覆盖记录 |
| `widget_service/tests/fixtures/compact_validation_baseline.json` | 固定历史行为样本或活动规则归属，快照不随主线变化重生成 |
| `widget_service/tests/fixtures/compact_validation_rule_inventory.json` | 固定历史行为样本或活动规则归属，快照不随主线变化重生成 |
| `widget_service/tests/test_asset_url_mapper.py` | 验证 asset_url_mapper 对应行为及兼容边界 |
| `widget_service/tests/test_compact_dsl_a2ui_converter.py` | 验证 compact_dsl_a2ui_converter 对应行为及兼容边界 |
| `widget_service/tests/test_compact_dsl_validator.py` | 验证 compact_dsl_validator 对应行为及兼容边界 |
| `widget_service/tests/test_compact_prompt_bundle.py` | 验证 compact_prompt_bundle 对应行为及兼容边界 |
| `widget_service/tests/test_compact_validation_architecture.py` | 验证 compact_validation_architecture 对应行为及兼容边界 |
| `widget_service/tests/test_compact_validation_assets.py` | 验证 compact_validation_assets 对应行为及兼容边界 |
| `widget_service/tests/test_compact_validation_diagnostics.py` | 验证 compact_validation_diagnostics 对应行为及兼容边界 |
| `widget_service/tests/test_compact_validation_equivalence.py` | 验证 compact_validation_equivalence 对应行为及兼容边界 |
| `widget_service/tests/test_compact_validation_fusion.py` | 验证 compact_validation_fusion 对应行为及兼容边界 |
| `widget_service/tests/test_compact_validation_fusion_followup.py` | 验证 compact_validation_fusion_followup 对应行为及兼容边界 |
| `widget_service/tests/test_compact_validation_numeric_display.py` | 验证 compact_validation_numeric_display 对应行为及兼容边界 |
| `widget_service/tests/test_compact_validation_repair_integration.py` | 验证 compact_validation_repair_integration 对应行为及兼容边界 |
| `widget_service/tests/test_compact_validation_restoration_integration.py` | 验证 compact_validation_restoration_integration 对应行为及兼容边界 |
| `widget_service/tests/test_compact_validation_small_card_merge.py` | 验证 compact_validation_small_card_merge 对应行为及兼容边界 |
| `widget_service/tests/test_compact_validation_title_icon.py` | 验证 compact_validation_title_icon 对应行为及兼容边界 |
