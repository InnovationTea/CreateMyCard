# PR #522 文件清单与验证

对照上游 main `ca27f1f`；本清单只列 PR 自身差异，不重复列出从 main 合入的素材、模板等文件。

当前实现合并提交：`26c1450`、`d69f666`。优化备份：`b4dea9c`，分支 `codex/backup-pr522-casewise-before-main-20261014`。

| 文件 | 用途 |
|---|---|
| `debug_tools/card_renderer/frontend/tests/badge-intrinsic-width.test.tsx` | 对应文件所指链路的回归测试；覆盖语义协议或当前主仓合同 |
| `debug_tools/card_renderer/runtime/components/src/extended/common-styles.ts` | wrapContent 按内容宽度显示，避免 Badge 被放到下一行 |
| `debug_tools/card_renderer/runtime/scripts/sync-runtime.mjs` | 保留本地适配并兼容 CRLF 同步标记 |
| `debug_tools/dist/assets/index-BfKZLSvq.js` → `debug_tools/dist/assets/index-w3kbIa1d.js` | 由渲染器源代码构建的预览产物，不手写修改 |
| `debug_tools/dist/index.html` | 由渲染器源代码构建的预览产物，不手写修改 |
| `docs/compact-dsl-validator-refactor/Compact_DSL现有校验规则分类清单_v1.md` | 对应功能的设计、校验职责或单例/融合验证记录 |
| `docs/plans/2026-10-13-compact-semantic-2x4-results.md` | 对应功能的设计、校验职责或单例/融合验证记录 |
| `docs/plans/2026-10-13-compact-semantic-2x4.md` | 对应功能的设计、校验职责或单例/融合验证记录 |
| `docs/plans/2026-10-14-2x4-casewise-q57.md` | 对应功能的设计、校验职责或单例/融合验证记录 |
| `docs/plans/2026-10-14-2x4-casewise-q58.md` | 对应功能的设计、校验职责或单例/融合验证记录 |
| `docs/plans/2026-10-14-2x4-casewise-q59.md` | 对应功能的设计、校验职责或单例/融合验证记录 |
| `docs/plans/2026-10-14-2x4-casewise-q61.md` | 对应功能的设计、校验职责或单例/融合验证记录 |
| `docs/plans/2026-10-14-2x4-casewise-q65.md` | 对应功能的设计、校验职责或单例/融合验证记录 |
| `docs/plans/2026-10-14-pr522-main-integration.md` | 对应功能的设计、校验职责或单例/融合验证记录 |
| `docs/云侧方案设计.md` | 对应功能的设计、校验职责或单例/融合验证记录 |
| `render/genui-sdk/components/src/extended/common-styles.ts` | wrapContent 按内容宽度显示，避免 Badge 被放到下一行 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/combinations/2x4.md` | 2×4 对应职责的语义组合、组件、布局或示例（以所在目录为准） |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/combinations/common.md` | 对应职责的通用约束，明确 2×4 语义协议例外 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/components/2x4.md` | 2×4 对应职责的语义组合、组件、布局或示例（以所在目录为准） |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/components/common.md` | 对应职责的通用约束，明确 2×4 语义协议例外 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/composition.md` | 综合组件与布局时使用受控语义模板 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/core.md` | 尺寸对应输出协议、真实数据与集合数量上下文 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/fewshots/2x4.md` | 2×4 对应职责的语义组合、组件、布局或示例（以所在目录为准） |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/layouts/2x4.md` | 2×4 对应职责的语义组合、组件、布局或示例（以所在目录为准） |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/layouts/common.md` | 对应职责的通用约束，明确 2×4 语义协议例外 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/plan.md` | 保留主仓 Plan 合同并完善归属/组件软候选 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/repair.md` | 按错误保持局部修复，容量冲突改语义组合而非固定几何 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/runtime/visual-recipes-v1.json` | Badge 内容宽度与当前 InfoBlock 文本/间距规范 |
| `widget_service/cloud/services/asset_url_mapper.py` | 保持语义源结构，同时还原主仓归档模板素材 |
| `widget_service/cloud/services/card_validation/compact_validation/api.py` | 语义展开和宽卡完整标签预算接入 |
| `widget_service/cloud/services/card_validation/compact_validation/context.py` | 携带语义展开来源上下文 |
| `widget_service/cloud/services/card_validation/compact_validation/semantic/display.py` | 指标标签穿越模板承载层，不跨真实分区 |
| `widget_service/cloud/services/card_validation/compact_validation/semantic/layout/text_width.py` | 已知多字段拼接和布尔分支的完整文字预算 |
| `widget_service/cloud/services/card_validation/compact_validation/source_locations.py` | 将展开节点诊断映射回原语义源 |
| `widget_service/cloud/services/card_validation/字段约束与演进记录.md` | 对应职责的兼容与回归适配 |
| `widget_service/cloud/services/compact_dsl_a2ui_converter.py` | 统一展开入口、语义源保存及主仓模板归档解析兼容 |
| `widget_service/cloud/services/compact_plan.py` | 语义结构下的覆盖与删除候选兼容 |
| `widget_service/cloud/services/compact_semantic_layout.py` | 受控语义布局编译、槽位角色反馈及环形参考尺寸注入 |
| `widget_service/cloud/services/generation_pipeline.py` | 记录语义源和展开源及诊断来源 |
| `widget_service/cloud/services/prompt_builder.py` | 按尺寸区分阶段协议、补齐 Action/Data 的最小修复指引 |
| `widget_service/cloud/services/widget_generation_service.py` | 保存真实 Compact 源，排除 JSX 标准输出误解析，兼容模板专用入口 |
| `widget_service/tests/test_compact_calendar_badge_context.py` | 对应文件所指链路的回归测试；覆盖语义协议或当前主仓合同 |
| `widget_service/tests/test_compact_component_bindings.py` | 对应文件所指链路的回归测试；覆盖语义协议或当前主仓合同 |
| `widget_service/tests/test_compact_infoblock_text_geometry.py` | 对应文件所指链路的回归测试；覆盖语义协议或当前主仓合同 |
| `widget_service/tests/test_compact_layout_runtime.py` | 对应文件所指链路的回归测试；覆盖语义协议或当前主仓合同 |
| `widget_service/tests/test_compact_prompt_bundle.py` | 对应文件所指链路的回归测试；覆盖语义协议或当前主仓合同 |
| `widget_service/tests/test_compact_semantic_layout.py` | 对应文件所指链路的回归测试；覆盖语义协议或当前主仓合同 |
| `widget_service/tests/test_compact_semantic_ratio_conversion.py` | 对应文件所指链路的回归测试；覆盖语义协议或当前主仓合同 |
| `widget_service/tests/test_compact_wide_expression_budget.py` | 对应文件所指链路的回归测试；覆盖语义协议或当前主仓合同 |
| `widget_service/tests/test_compact_wide_label_budget.py` | 对应文件所指链路的回归测试；覆盖语义协议或当前主仓合同 |
| `widget_service/tests/test_design_compact_few_shots.py` | 对应文件所指链路的回归测试；覆盖语义协议或当前主仓合同 |
| `widget_service/tests/test_design_compact_repair_prompt.py` | 对应文件所指链路的回归测试；覆盖语义协议或当前主仓合同 |
| `widget_service/tests/test_service_units.py` | 对应文件所指链路的回归测试；覆盖语义协议或当前主仓合同 |
| `widget_service/tools/analyze_compact_semantic_run.py` | 分析模型运行结果和失败类型 |
| `widget_service/tools/migrate_compact_semantic_fewshots.py` | 将原有示例迁移为语义结构 |
| `widget_service/tools/run_compact_semantic_batch.py` | 语义分支运行与追踪入口 |
| `widget_service/tools/verify_compact_semantic_examples.py` | 以最新 main 核对输入和事实并通过真实 Processor，不调用模型 |

本清单另为本次新增文档，不改变执行逻辑。

## 验证

- 相关链路：571 passed、41 subtests passed；补充入口：61 passed。
- 全 widget_service/tests：2151 passed、19 failed、16 skipped、59 subtests passed。
- 独立 main `a376ba4`：2049 passed、19 failed、16 skipped、59 subtests passed；失败集合相同，无新增失败。
- `ca27f1f` 后续仅改蓝牙能力说明；合入后能力与语义链路定向回归：325 passed。
- 十个既有 2×4 示例的输入/业务事实核对和完整 Processor 均通过；渲染器 27 项通过。
- Ruff、差异空白与 Runtime 同步检查通过。
- 没有重新请求 DeepSeek；未新增浏览器重叠校验，不宣称全量视觉效果已改善。

## 主仓对照中同样存在的 19 个失败

- `tests/test_compact_dsl_interface_retry_routes.py::test_real_generation_pipeline_retries_to_valid_artifact[model]`
- `tests/test_compact_dsl_interface_retry_routes.py::test_real_generation_pipeline_retries_to_valid_artifact[validation]`
- `tests/test_compact_dsl_interface_retry_routes.py::test_real_generation_pipeline_retries_to_valid_artifact[upload]`
- `tests/test_compact_hero_typography.py::test_template_keeps_other_compact_validations[empty-non-empty]`
- `tests/test_compact_hero_typography.py::test_non_template_formatted_readout_keeps_original_contract[expression]`
- `tests/test_compact_hero_typography.py::test_non_template_formatted_readout_keeps_original_contract[inherited-width]`
- `tests/test_compact_hero_typography.py::test_non_template_formatted_readout_keeps_original_contract[percent-description]`
- `tests/test_deepseek_official_http_transport.py::test_debug_agent_prefers_official_http_when_api_key_is_configured`
- `tests/test_fusion_ball_version_gate.py::test_design_processor_copies_task_spec_app_version_into_profile`
- `tests/test_multi_round_edit.py::test_edit_prompt_contains_previous_genui_but_not_source_url`
- `tests/test_service_units.py::test_anyio_thread_pool_uses_configured_capacity`
- `tests/test_service_units.py::test_design_compact_few_shots_are_disabled_by_default_and_can_be_enabled`
- `tests/test_service_units.py::test_phase_two_version_returns_phase_two_capability_overview`
- `tests/test_service_units.py::test_phase_two_version_returns_phase_two_capability_schemas`
- `tests/test_service_units.py::test_design_compact_edit_prompt_contains_previous_design_token`
- `tests/test_service_units.py::test_model_runtime_collects_llmclient_stream`
- `tests/test_service_units.py::test_design_converter_expands_latest_design_tokens`
- `tests/test_service_units.py::test_missing_action_unit_on_click_enters_validation_repair`
- `tests/test_tool_dispatch_routes.py::test_compact_valid_request_breaks_stringified_argument_streak`
