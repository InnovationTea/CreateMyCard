# 2×4 Compact语义布局：实现与验证记录

## 状态

实现位于隔离工作树`compact_dsl/semantic-layout-2x4`，分支`codex/compact-semantic-layout-2x4-v1`，
基于PR #512的`2d43d55`。原`compact_dsl/CreateMyCard`未切换、未覆盖，原`.env`保留。
没有推送上游。验证沿用Code技能的计划、实现、逐链路验证流程。

## 模型输出和Runtime边界

- `Layout`：四个原有W父布局；上下布局三种对齐变体、侧双槽镜像仍支持。
- `Region.variant`：由父区决定紧凑/宽版。原居中、标题内容、主辅、内容按钮、双环、主辅按钮、四环及普通四格均保留。
- `Group.variant`：紧密主辅、标签与值、并列双项、标题与真实数量。双行标题及标题+Badge没有丢失。
- Runtime展开固定边距、间距、对齐、权重、背板；事实组件ID、绑定路径、数据行及事件不因编译改变。
- 语义源与展开源分别记录；绑定修复、素材恢复及编辑保存语义源。语法已修正的源行写入产物，不再保存坏JSON。
- 原空间与业务校验仍作用于展开树。布局诊断映射至语义行，标记expanded；不让模型编辑生成几何。
- 指标标签校验不把生成的承载层算成语义距离，真实业务Region仍计层，不借用另一分区标题。
- 2×2原有协议、旧Compact读取及PR #512的连续对话Plan→DSL→Repair、Drop策略保留。

没有加入浏览器重叠校验。模板几何受控不代表文字无限可放；原静态预算与人工截图检查仍有各自边界。

## 示例与真实任务

10个既有few-shot均迁移为语义布局，最终再次通过原Processor。输入、事实、动作、颜色未改，
唯一内容排布修正为V23辅助信息`columns:1`，避免电流单位mA在原双列里被裁切。
没有增加与测试任务相似的新业务答案。

### 首批完整32条

输入为原Runner的cardSpec24/Q*.json；每条只发一个外层请求，串行，内部最多10次修复。
few-shot启用、筛选关闭、runtime prompt context关闭、接口/模型失败外层重试关闭；未引入Drop/Reset实验。

| 指标 | 结果 |
|---|---|
| 服务成功 | 26/32 |
| 降级通过 | 1/32 |
| 校验通过合计 | 27/32，84.4% |
| 最终失败 | 5/32：63、64、71、84、85 |
| 不经质量修复通过 | 1/32 |
| 平均完整任务耗时 | 19.18秒，含Plan、生成、修复、校验及产物读取 |
| 中位完整任务耗时 | 14.10秒 |
| 整批耗时 | 615.41秒 |
| 内部修复总数 | 152 |
| 最终源的语义布局使用 | 32/32；侧双槽24，左右双区5，上下3 |
| 可渲染预览 | 32/32，不等于32条都校验通过 |

本批在指标标签承载层适配和产物源序列化修复前运行，不能将84.4%宣称为最终补丁后的完整成功率。
预览仅规范化源JSON，原始产物与状态不变。失败卡面使用最后受检源预览，不冒充成功结果。
首批失败63/85包含模板层导致的标签误判；64/71/84最终仍遗漏必要信息或动作。
截图还可见53左右耳层级不一致、65较多留白、69主文字过大、88温度重复；这次不声称解决这些语义/选组件问题。

### 兼容修复后5条定点复测

57、63、69、74、85重新生成，仍是每条一个外层请求、最多10次内部修复。
63、69、85通过，57、74失败。平均完整任务22.03秒。63/85标签误判已消失，成功产物均可正确提取Compact源。
57/74失败仍涉及必要事实/Action遗漏或容量组织，并非模板几何被模型篡改。
这一轮未运行后来补充的标题+Badge/双行标题/普通四格回归；这些是旧能力的附加映射，另有单元转换测试。
两轮没有选优或混成一轮，不做公平A/B提升结论。

产物位置（相对phone-widget工作区）：

- 示例：`compact_dsl/output/1013-semantic-fewshots-v2/gallery/gallery.html`
- 完整32条：`compact_dsl/output/1013-semantic-layout-2x4-full-v1/gallery/gallery.html`
- 5条复测：`compact_dsl/output/1013-semantic-layout-2x4-compat-v2/gallery/gallery.html`
- 原始Trace与逐请求meta保存在各run目录；统计为`semantic-metrics.json`。

## 实际验证

- 相关Python回归：500项通过、37个子测试通过，其中49项语义布局测试。
- 扩展服务/编辑回归：262项通过、1项跳过、9项既有失败；这9项已在未修改的PR #512上复现。
- Node Gallery回归：8项通过。
- 既有10个few-shot全部通过原Processor，并用新Python转换器和统一CardRenderer渲染。
- 所有修改的Python文件Ruff通过；`git diff --check`通过。

9项既有失败不是本次修复范围：

| 测试 | 原因 |
|---|---|
| test_anyio_thread_pool_uses_configured_capacity | 断言旧backend默认值，而当前默认llmclient |
| test_design_compact_few_shots_are_disabled_by_default_and_can_be_enabled | 仍断言默认关闭，当前默认开启 |
| test_phase_two_version_returns_phase_two_capability_overview | 能力注册表与旧断言不同 |
| test_phase_two_version_returns_phase_two_capability_schemas | 同上 |
| test_design_compact_edit_prompt_contains_previous_design_token | 旧提示词内容断言 |
| test_model_runtime_collects_llmclient_stream | 当前运行时与旧模拟返回断言不同 |
| test_design_converter_expands_latest_design_tokens | 当前组件合同与旧fixture不同 |
| test_missing_action_unit_on_click_enters_validation_repair | 旧ActionUnit已不受支持 |
| test_edit_prompt_contains_previous_genui_but_not_source_url | 旧提示词标题断言 |

## 逐文件改动

以下路径相对本工作树根目录。Prompt前缀为
`widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/`。

| 文件 | 用途 |
|---|---|
| docs/云侧方案设计.md | 公开语义协议、编译/来源/产物和校验边界 |
| docs/plans/2026-10-13-compact-semantic-2x4.md | 实施计划 |
| docs/plans/2026-10-13-compact-semantic-2x4-results.md | 本记录、验证结果及文件清单 |
| Prompt core.md | 2×4根节点及输出契约 |
| Prompt layouts/2x4.md | 父/子布局总表、语义Props、固定角色、模板及容量 |
| Prompt layouts/common.md | 明确2×4几何属于模板，保留原预算要求 |
| Prompt combinations/2x4.md | Group定义及旧组合映射 |
| Prompt combinations/common.md | 消除禁止Region和要求2×4输出Row/Column的冲突 |
| Prompt composition.md | 生成流程不再要求2×4输出weight等内部参数 |
| Prompt repair.md | 修复语义变体/组件，不修改展开几何；Drop后闭合角色 |
| Prompt fewshots/2x4.md | 10个已有案例的布局表达迁移 |
| widget_service/cloud/services/compact_semantic_layout.py | 唯一语义模板编译器及结构/Props检查 |
| widget_service/cloud/services/compact_dsl_a2ui_converter.py | raw/expanded公共解析、编译及合法源序列化 |
| widget_service/cloud/services/asset_url_mapper.py | 素材恢复保持语义源 |
| widget_service/cloud/services/generation_pipeline.py | 编译链路及源/展开Trace分离 |
| widget_service/cloud/services/widget_generation_service.py | 保存已解析的2×4源行，保留原始Trace |
| widget_service/cloud/services/card_validation/compact_validation/api.py | 原检查入口接入编译与来源上下文 |
| widget_service/cloud/services/card_validation/compact_validation/context.py | 编译来源映射 |
| widget_service/cloud/services/card_validation/compact_validation/source_locations.py | 诚实定位生成布局诊断 |
| widget_service/cloud/services/card_validation/compact_validation/semantic/display.py | 指标标签跨模板承载层，不跨真实业务分区 |
| widget_service/cloud/services/card_validation/字段约束与演进记录.md | 校验归属与适配登记 |
| widget_service/tests/test_compact_semantic_layout.py | 父/子布局、镜像、旧协议、绑定/素材、空间、标签、产物、修复路由测试 |
| widget_service/tests/test_compact_layout_runtime.py | 原低阶匹配测试先展开语义fixture |
| widget_service/tests/test_compact_prompt_bundle.py | 新语义Prompt合同断言 |
| widget_service/tests/test_service_units.py | warning-only测试改用合法Compact源，仍隔离warning行为 |
| widget_service/tools/migrate_compact_semantic_fewshots.py | 机械迁移已有布局，不构造业务答案 |
| widget_service/tools/verify_compact_semantic_examples.py | 检查输入/业务不变，验证并导出示例，无模型调用 |
| widget_service/tools/run_compact_semantic_batch.py | 串行单外层请求、记录完整耗时和真实修复数 |
| widget_service/tools/analyze_compact_semantic_run.py | 保存原始状态，生成可审阅预览及布局/失败统计 |

本工作树外的共享Gallery工具还有两处改动，不属于本Git分支提交：

- `compact_dsl/build-gallery.cjs`：`--repository`指定实际转换器仓库，默认行为不变。
- `compact_dsl/build-gallery.test.cjs`：新增仓库选择回归。

渲染不使用另一套JS布局展开器；新语义源经同一Python编译器、高阶Recipe及A2UI转换，再交给统一CardRenderer。
