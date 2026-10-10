# Compact DSL 校验器重构实施与验证记录

- 日期：2026-09-30
- 依据：[重构方案 v3](Compact_DSL校验器重构方案_v3.md)
- 状态：v3 阶段一至五已实现并完成确定性验证；已知基线问题及真实模型效果评估单列，不计作通过。
- 重构前提交：`9d567c5f994903882802dab620171d010124ad90`。
- 开始时受版本控制的文件无本地修改；两份未跟踪的代码导读文档不属于本次改动。

## 实施范围

完成 v3 阶段一至五：固定基线、分类拆分、结构化诊断、简单建议接口及模型修复链路。
不实施第 7 节的错误合并、重排和抑制，不改变 BASE-01 至 BASE-04 的既有判定。
有争议的检查保留旧字符串路径，不能将等价测试当作规则合规结论。

## 基线与验证

基线包含 Compact 校验、转换、主文字、双动作、提示词、Few-shot、修复路由、素材映射及相关模板回归。
重构前相关回归：559 个测试中 541 通过、18 失败，另有 24 个子测试通过。
这些失败发生在运行代码修改之前；后续回归比较失败集合与原因，不将已有失败计作通过。
公开入口另保存了 82 组去重后的输入与原错误／警告结果，覆盖文案、顺序、去重与异常链。
源文件 SHA-256：`11d9181f89a9c9e80a201738b6ddd999501d8cc6592a7fb7f0828f4172735bdc`。

既有失败：

- `tests.test_compact_hero_typography::test_template_keeps_other_compact_validations[empty-non-empty]`
- `tests.test_compact_hero_typography::test_non_template_formatted_readout_keeps_original_contract[expression]`
- `tests.test_compact_hero_typography::test_non_template_formatted_readout_keeps_original_contract[inherited-width]`
- `tests.test_compact_hero_typography::test_non_template_formatted_readout_keeps_original_contract[percent-description]`
- `tests.test_design_compact_few_shots::test_w9_allows_battery_percentage_formatted_hero[20-28]`
- `tests.test_design_compact_few_shots::test_w9_allows_battery_percentage_formatted_hero[24-34]`
- `tests.test_asset_mapping_generation::test_generation_maps_before_validation_and_saves_separate_sources[True-compact_dsl-model]`
- `tests.test_asset_mapping_generation::test_generation_maps_before_validation_and_saves_separate_sources[False-compact_dsl-model]`
- `tests.test_asset_mapping_generation::test_edit_and_legacy_url_migration_preserve_source_artifact`
- `tests.test_asset_mapping_generation::test_repair_uses_original_paths_and_remaps_final_output`
- `cloud.services.template_generation.tests.test_runtime_if_deferred::test_public_compact_pipeline_rejects_deferred_runtime_if[If]`
- `cloud.services.template_generation.tests.test_runtime_if_deferred::test_public_compact_pipeline_rejects_deferred_runtime_if[IF]`
- `cloud.services.template_generation.tests.test_runtime_if_deferred::test_runtime_expression_still_passes_public_processor[0]`
- `cloud.services.template_generation.tests.test_runtime_if_deferred::test_runtime_expression_still_passes_public_processor[1]`
- `cloud.services.template_generation.tests.test_runtime_if_deferred::test_runtime_expression_still_passes_public_processor[None]`
- `cloud.services.template_generation.tests.test_runtime_if_deferred::test_runtime_expression_still_passes_public_processor[]`
- `cloud.services.template_generation.tests.test_reviewed_wide_spacing::test_wide_layout_fixed_slots_fit_content_budget[False-WideSingleFocusLayout@1]`
- `cloud.services.template_generation.tests.test_reviewed_wide_spacing::test_wide_layout_fixed_slots_fit_content_budget[True-WideSingleFocusLayout@1]`

扩展回归另发现以下两个失败，已从上述重构前提交加载原校验器、流水线、提示词与生成服务复现：

- `tests.test_service_units::test_phase_two_version_returns_phase_two_capability_overview`
- `tests.test_service_units::test_phase_two_version_returns_phase_two_capability_schemas`

两项均与能力清单缺少 `GetMemoData`、`GetPhoneCallRecords` 有关，不属于此次校验器重构。
最终 20 个失败的用例标识及失败原因与旧实现一致；比较时忽略异常类所在模块前缀和进程内对象地址。

## 当前实现进度

- 原 4972 行入口已缩减为兼容导出；校验编排、上下文、诊断、建议接口和模型说明分别实现。
- 153 个原报错位置中，148 个已迁移为结构化诊断，对应 147 个稳定错误码；两处相同 S4 约束共用错误码。
- 组件 14、表达式 6、数据绑定 2、跨文件 3、有效能力 2、展示语义 27、布局 94 个位置已迁移。
- 仍保留 5 个字符串位置：两个外部委托，BASE-02 的两个冲突位置，以及 BASE-04 的适用边界位置。
- 主文字、W1、W9、S4、倒计时及布局路由使用独立流程文件；分类模块不反向导入流程或修复建议模块。
- 默认建议仍只配置已审阅的通用方向；专用函数按规则码显式注册，尚无可信特殊条件的规则不增加虚构策略。
- 在线与独立修复共享模型说明格式化；旧错误字符串和内部修复记录保留。
- 缺少硬约束的新诊断视为不完整，模型请求回退旧说明；大背板的内容加动作约束使用当前动作类型，避免把合法图文动作错误地指导成 Button。

逐项迁移登记保存在
[规则迁移登记](../../widget_service/tests/fixtures/compact_validation_rule_inventory.json)，
包含原观察编号、原函数、当前模块与函数、错误码、旧文案表达式摘要及测试关联。
其中 `behaviorCovered: false` 表示尚缺该规则的直接触发用例，不能解释为已完成行为验证。
当前全部 147 个稳定错误码已有关联的通过用例直接触发；这不代表每条规则的所有分支和边界已覆盖。

## 本轮检查结果

| 检查 | 实际结果 | 证明范围与限制 |
|---|---|---|
| 完整相关基线、专项及生成服务扩展回归 | 1028 通过、20 失败、1 跳过，24 个子测试通过 | 21 个测试文件；20 个失败均与旧实现一致，不能宣称全量通过；另有一条既有依赖弃用警告 |
| 最终新增专项测试 | 220 通过 | 82 个公开入口基线、91 个规则基线、39 个诊断与接口测试、3 个 W9 测试、2 个结构归属测试、3 个修复集成测试；包含 5 个上下文建议用例及末次修订复核；已纳入第六批完整回归 |
| 独立修复旧实现对照 | 2 通过 | 固定两轮 DSL 返回序列，旧实现与新实现的成功结果、重试耗尽异常、错误数量及客户端关闭行为一致，模型说明按设计变化 |
| 153 个历史输出位置核对 | 通过 | 全部旧文案表达式保持等价，迁移登记与实际模块一致；不代替逐分支运行验证 |
| 修改的 Python 文件 Ruff | 通过 | 分类包、兼容入口、调用方及所有新增或修改的测试 |
| 配置及依赖检查 | 通过 | 默认配置与函数注册校验包含在专项测试；35 个包文件静态导入无环，分类模块不反向导入流程或修复层 |
| 差异和新增文件空白检查 | 通过 | `git diff --check`，另检查新增文件的行末空白及 Tab；Git 的 LF/CRLF 转换提示不属于差异错误 |

91 个规则用例的预期错误从重构前脚本独立捕获，另保存源码摘要；比较原始错误列表及顺序，
覆盖 W1、S4、倒计时、动作背板、全宽动作、小背板、素材组合等提前返回与交错检查。
其产生的诊断同时验证可 JSON 序列化、序列化前后模型说明等价、规则码及硬约束完整保留。
在线入口用固定的“失败、失败、通过”序列核对模型调用数、素材还原先后顺序和内部记录；
独立入口分别验证“失败、失败、通过”和“失败、失败、失败”，继续使用原最终异常文案。
其他既有回归覆盖首次通过、重试关闭、耗尽、转换失败、warning、模板跳过及阻断／非阻断路由。
`test_service_units.py` 仅将一处模型说明断言更新为新规则码与约束标签；未修改旧异常预期。
没有执行真实模型效果对照，不宣称新的错误说明提高了修复成功率。
没有调用外部 CodeCheck 服务；本次已执行 Ruff 和本地结构复核，不将其表述为服务端 CodeCheck 通过。

## 验收清单

- [x] 规则按分类迁移，复合函数按检查项拆分，旧入口仅作兼容。
- [x] 公共上下文保留顺序、first/last/all 索引、尺寸来源与模板豁免。
- [x] 已迁移规则具有具体错误码、事实、硬约束；源码定位仅在可证明映射时提供。
- [x] 旧字符串、混合迁移、异常链、warning、错误数量与顺序兼容。
- [x] fixHint 配置、专用函数及失败回退可验证，不引入条件语言。
- [x] 在线和独立修复使用模型说明副本，内部记录保持完整。
- [x] 分类清单更新实际模块、规则码及测试覆盖，待决范围明确。
- [x] Ruff、相关及扩展回归、配置校验、差异空白检查完成，已有失败逐项列明。
- [x] 固定修复返回序列下行为等价；实际模型效果与确定性测试分开报告。

## 实际文件清单

本次涉及 58 个文件。目录内规则的具体观察编号与错误码以迁移登记为准。

| 批次 | 文件（相对仓库根目录） | 用途 |
|---:|---|---|
| 1 | [AGENTS.md](../../AGENTS.md) | 登记新增、修改和迁移校验的归属检查流程。 |
| 7 | [docs/compact-dsl-validator-refactor/Compact_DSL校验器重构方案_v3.md](../../docs/compact-dsl-validator-refactor/Compact_DSL校验器重构方案_v3.md) | 登记实施状态与实际改动位置。 |
| 7 | [docs/compact-dsl-validator-refactor/Compact_DSL现有校验规则分类清单_v1.md](../../docs/compact-dsl-validator-refactor/Compact_DSL现有校验规则分类清单_v1.md) | 保留历史观察位置，补充实际模块、规则码及验证关联。 |
| 1 | [docs/云侧方案设计.md](../../docs/云侧方案设计.md) | 同步已批准的分类、诊断、建议及兼容约定。 |
| 6 | [widget_service/cloud/data/protocol_profiles/design-compact-dsl/REPAIR_SYSTEM_PROMPT.md](../../widget_service/cloud/data/protocol_profiles/design-compact-dsl/REPAIR_SYSTEM_PROMPT.md) | 解释模型接收的规则、位置、事实、约束及可选建议。 |
| 6 | [widget_service/cloud/repair_compact_dsl.py](../../widget_service/cloud/repair_compact_dsl.py) | 独立修复入口接收可选建议上下文。 |
| 6 | [widget_service/cloud/services/artifact_store.py](../../widget_service/cloud/services/artifact_store.py) | 修复记录允许嵌套诊断类型，保留序列化行为。 |
| 5 | [widget_service/cloud/services/card_validation/compact_dsl_validator.py](../../widget_service/cloud/services/card_validation/compact_dsl_validator.py) | 保留公开兼容导出及既有辅助函数导入。 |
| 6 | [widget_service/cloud/services/generation_pipeline.py](../../widget_service/cloud/services/generation_pipeline.py) | 保留原始文本、适配诊断分组并保持旧字符串出口。 |
| 6 | [widget_service/cloud/services/prompt_builder.py](../../widget_service/cloud/services/prompt_builder.py) | 仅在模型请求副本中组织 Compact 错误说明。 |
| 6 | [widget_service/cloud/services/widget_generation_service.py](../../widget_service/cloud/services/widget_generation_service.py) | 注入有可信来源的创建／编辑条件。 |
| 6 | [widget_service/tests/test_service_units.py](../../widget_service/tests/test_service_units.py) | 同步一处模型说明断言，保留外层 stage/code。 |
| 7 | [docs/compact-dsl-validator-refactor/Compact_DSL重构实施与验证记录.md](../../docs/compact-dsl-validator-refactor/Compact_DSL重构实施与验证记录.md) | 记录基线、已知失败、验收证据及逐文件清单。 |
| 2 | [widget_service/cloud/data/validator_rules/compact/repair_hints.json](../../widget_service/cloud/data/validator_rules/compact/repair_hints.json) | 按具体规则码配置四项通用修复建议。 |
| 2 | [widget_service/cloud/services/card_validation/compact_validation/__init__.py](../../widget_service/cloud/services/card_validation/compact_validation/__init__.py) | 声明对应职责包。 |
| 5 | [widget_service/cloud/services/card_validation/compact_validation/api.py](../../widget_service/cloud/services/card_validation/compact_validation/api.py) | 按原时机编排校验，定位和附加可选建议，保持警告出口。 |
| 2 | [widget_service/cloud/services/card_validation/compact_validation/context.py](../../widget_service/cloud/services/card_validation/compact_validation/context.py) | 复用本轮组件索引、重复引用与各类父节点视图。 |
| 2 | [widget_service/cloud/services/card_validation/compact_validation/diagnostics.py](../../widget_service/cloud/services/card_validation/compact_validation/diagnostics.py) | 保存事实、硬约束与旧文案，形成兼容分组及异常。 |
| 5 | [widget_service/cloud/services/card_validation/compact_validation/flows/__init__.py](../../widget_service/cloud/services/card_validation/compact_validation/flows/__init__.py) | 声明对应职责包。 |
| 5 | [widget_service/cloud/services/card_validation/compact_validation/flows/hero.py](../../widget_service/cloud/services/card_validation/compact_validation/flows/hero.py) | 编排 主文字 的跨分类检查，保留原调用顺序和提前返回。 |
| 5 | [widget_service/cloud/services/card_validation/compact_validation/flows/layout.py](../../widget_service/cloud/services/card_validation/compact_validation/flows/layout.py) | 编排 布局路由 的跨分类检查，保留原调用顺序和提前返回。 |
| 5 | [widget_service/cloud/services/card_validation/compact_validation/flows/two_by_two.py](../../widget_service/cloud/services/card_validation/compact_validation/flows/two_by_two.py) | 编排 2x2 的跨分类检查，保留原调用顺序和提前返回。 |
| 5 | [widget_service/cloud/services/card_validation/compact_validation/flows/w1.py](../../widget_service/cloud/services/card_validation/compact_validation/flows/w1.py) | 编排 W1 的跨分类检查，保留原调用顺序和提前返回。 |
| 5 | [widget_service/cloud/services/card_validation/compact_validation/flows/w9.py](../../widget_service/cloud/services/card_validation/compact_validation/flows/w9.py) | 编排 W9 的跨分类检查，保留原调用顺序和提前返回。 |
| 2 | [widget_service/cloud/services/card_validation/compact_validation/model_feedback.py](../../widget_service/cloud/services/card_validation/compact_validation/model_feedback.py) | 确定性格式化模型说明，失败回退旧文案。 |
| 2 | [widget_service/cloud/services/card_validation/compact_validation/repair_guidance.py](../../widget_service/cloud/services/card_validation/compact_validation/repair_guidance.py) | 解析默认配置和专用函数，隔离建议生成失败。 |
| 2 | [widget_service/cloud/services/card_validation/compact_validation/rule_catalog.py](../../widget_service/cloud/services/card_validation/compact_validation/rule_catalog.py) | 登记 147 个稳定规则码。 |
| 2 | [widget_service/cloud/services/card_validation/compact_validation/schema.py](../../widget_service/cloud/services/card_validation/compact_validation/schema.py) | 提供数据声明和路径查询辅助逻辑。 |
| 3 | [widget_service/cloud/services/card_validation/compact_validation/semantic/__init__.py](../../widget_service/cloud/services/card_validation/compact_validation/semantic/__init__.py) | 声明对应职责包。 |
| 3 | [widget_service/cloud/services/card_validation/compact_validation/semantic/bindings.py](../../widget_service/cloud/services/card_validation/compact_validation/semantic/bindings.py) | 语义／绑定首帧数据及进度值类型。 |
| 3 | [widget_service/cloud/services/card_validation/compact_validation/semantic/cross_file.py](../../widget_service/cloud/services/card_validation/compact_validation/semantic/cross_file.py) | 语义／引用与数据声明一致性、既有警告。 |
| 3 | [widget_service/cloud/services/card_validation/compact_validation/semantic/display.py](../../widget_service/cloud/services/card_validation/compact_validation/semantic/display.py) | 语义／单位、文案、业务字段和展示组合。 |
| 3 | [widget_service/cloud/services/card_validation/compact_validation/semantic/effective.py](../../widget_service/cloud/services/card_validation/compact_validation/semantic/effective.py) | 语义／本轮有效素材和事件候选约束。 |
| 4 | [widget_service/cloud/services/card_validation/compact_validation/semantic/layout/__init__.py](../../widget_service/cloud/services/card_validation/compact_validation/semantic/layout/__init__.py) | 声明对应职责包。 |
| 4 | [widget_service/cloud/services/card_validation/compact_validation/semantic/layout/assets.py](../../widget_service/cloud/services/card_validation/compact_validation/semantic/layout/assets.py) | 布局／素材颜色及视觉约束。 |
| 4 | [widget_service/cloud/services/card_validation/compact_validation/semantic/layout/fusion.py](../../widget_service/cloud/services/card_validation/compact_validation/semantic/layout/fusion.py) | 布局／融球组成及位置约束。 |
| 4 | [widget_service/cloud/services/card_validation/compact_validation/semantic/layout/geometry.py](../../widget_service/cloud/services/card_validation/compact_validation/semantic/layout/geometry.py) | 布局／高度、边距、间距和几何预算。 |
| 4 | [widget_service/cloud/services/card_validation/compact_validation/semantic/layout/regions.py](../../widget_service/cloud/services/card_validation/compact_validation/semantic/layout/regions.py) | 布局／分区结构及共享事实查询。 |
| 4 | [widget_service/cloud/services/card_validation/compact_validation/semantic/layout/routing.py](../../widget_service/cloud/services/card_validation/compact_validation/semantic/layout/routing.py) | 布局／骨架识别门禁及路由约束。 |
| 4 | [widget_service/cloud/services/card_validation/compact_validation/semantic/layout/two_by_four.py](../../widget_service/cloud/services/card_validation/compact_validation/semantic/layout/two_by_four.py) | 布局／2x4 动作背板、稀疏布局等约束。 |
| 4 | [widget_service/cloud/services/card_validation/compact_validation/semantic/layout/two_by_two.py](../../widget_service/cloud/services/card_validation/compact_validation/semantic/layout/two_by_two.py) | 布局／2x2 主数值、S4、倒计时等约束。 |
| 4 | [widget_service/cloud/services/card_validation/compact_validation/semantic/layout/typography.py](../../widget_service/cloud/services/card_validation/compact_validation/semantic/layout/typography.py) | 布局／字号、对齐、主数值及单位排版。 |
| 4 | [widget_service/cloud/services/card_validation/compact_validation/semantic/layout/w1.py](../../widget_service/cloud/services/card_validation/compact_validation/semantic/layout/w1.py) | 布局／W1 分区和动作约束。 |
| 4 | [widget_service/cloud/services/card_validation/compact_validation/semantic/layout/w9.py](../../widget_service/cloud/services/card_validation/compact_validation/semantic/layout/w9.py) | 布局／W9 分区和图文密度约束。 |
| 2 | [widget_service/cloud/services/card_validation/compact_validation/source_locations.py](../../widget_service/cloud/services/card_validation/compact_validation/source_locations.py) | 从本轮原文提取可证明的组件、属性和行号。 |
| 2 | [widget_service/cloud/services/card_validation/compact_validation/syntax/__init__.py](../../widget_service/cloud/services/card_validation/compact_validation/syntax/__init__.py) | 声明对应职责包。 |
| 2 | [widget_service/cloud/services/card_validation/compact_validation/syntax/components.py](../../widget_service/cloud/services/card_validation/compact_validation/syntax/components.py) | 语法／组件结构契约，保持结构门禁。 |
| 2 | [widget_service/cloud/services/card_validation/compact_validation/syntax/expressions.py](../../widget_service/cloud/services/card_validation/compact_validation/syntax/expressions.py) | 语法／表达式和路径结构检查。 |
| 2 | [widget_service/cloud/services/card_validation/compact_validation/text.py](../../widget_service/cloud/services/card_validation/compact_validation/text.py) | 复用文本、单位及绑定事实查询。 |
| 1 | [widget_service/tests/fixtures/compact_validation_baseline.json](../../widget_service/tests/fixtures/compact_validation_baseline.json) | 固定 82 组公开入口的旧实现输出。 |
| 5 | [widget_service/tests/fixtures/compact_validation_rule_cases.json](../../widget_service/tests/fixtures/compact_validation_rule_cases.json) | 固定 91 组规则或流程输入与旧错误顺序。 |
| 5 | [widget_service/tests/fixtures/compact_validation_rule_inventory.json](../../widget_service/tests/fixtures/compact_validation_rule_inventory.json) | 逐项登记 153 个观察位置的归属和测试证据。 |
| 5 | [widget_service/tests/test_compact_validation_architecture.py](../../widget_service/tests/test_compact_validation_architecture.py) | 检查诊断归属、旧文案表达式、注册及依赖方向。 |
| 6 | [widget_service/tests/test_compact_validation_diagnostics.py](../../widget_service/tests/test_compact_validation_diagnostics.py) | 验证异常、分组、来源、建议配置和模型副本。 |
| 1 | [widget_service/tests/test_compact_validation_equivalence.py](../../widget_service/tests/test_compact_validation_equivalence.py) | 逐项比较公开入口与旧实现的异常及警告。 |
| 6 | [widget_service/tests/test_compact_validation_repair_integration.py](../../widget_service/tests/test_compact_validation_repair_integration.py) | 验证固定返回序列、素材还原和修复记录。 |
| 5 | [widget_service/tests/test_compact_validation_rule_cases.py](../../widget_service/tests/test_compact_validation_rule_cases.py) | 比较原规则输出顺序并验证诊断可序列化和说明完整。 |
| 5 | [widget_service/tests/test_compact_validation_w9.py](../../widget_service/tests/test_compact_validation_w9.py) | 验证复合 W9 检查的门禁、交错顺序及分类。 |

## 分批提交与独立快照验证

本次按依赖拆成七批提交。第二至四批只引入模块，继续使用旧入口；第五批在依赖完整后切换，
第六批接通模型反馈。代码和测试内容未因拆分调整；完整文件清单的“批次”列对应下表。

验证使用重构前版本导出的临时快照，逐批叠加暂存区文件，不读取工作区后续批次的实现。
每批提交前核对暂存清单，并执行差异检查；涉及 Python 的批次执行 Ruff。
第一批旧入口的 82 个基线测试通过；第二至四批逐批通过新增模块导入和 82 个基线测试；
第五批切换入口后 178 个测试通过。第六批重新执行完整相关与扩展回归，结果见上表。
第七批仅更新文档，复核引用、文件清单及差异空白。

| 批次 | 提交主题 | 文件数 |
|---:|---|---:|
| 1 | docs(test): 同步 Compact 重构约定并固定旧行为基线 | 4 |
| 2 | feat(validation): 引入 Compact 诊断基础与语法规则 | 13 |
| 3 | refactor(validation): 提取 Compact 语义规则 | 5 |
| 4 | refactor(validation): 按职责提取 Compact 布局规则 | 11 |
| 5 | refactor(validation): 切换分类校验入口并验证规则等价 | 13 |
| 6 | feat(repair): 接通 Compact 结构化修复反馈与可选建议 | 9 |
| 7 | docs: 记录 Compact 重构落点与分批验收结果 | 3 |
