# 静态小标题优先与最新 PR 同步验证

## 本次范围

- 在原 PR716 分支上合入最新 PR715 `aa094d9d`、PR717 `a1f37fda`；两者均已成为当前分支祖先。
- PR715 合并提交 `11c79646`，PR717 合并提交 `0dd429f2`。本地保留备份 `codex/backup-static716-before-title-20261030`。
- 合并时保留此前审阅的普通字重标题、自动列表背板、编号和双辅助文本样式。组件文档不重复声明全局五对象预算，保留首次 Plan 的实际组件容量提示。
- 上游删除的八条旧动作任务按原提交同步；本轮只使用此前明确授权的静态任务，不恢复或外发动作数据。

## 标题优化及职责

Information 区分整卡主题概括与虚构对象名；共同主题可以从输入用途忠实提炼，不要求原文已经是独立标题句。
Composition 在信息同样完整且容量合法时优先带标题的结构，不按“三条信息”直接默认三项 TextList。
Plan 负责将主题落实为有来源引用的 shared/title，使用 SingleLineTitle 提示；仅作装饰的主题用 should，必要主体和范围仍用 must。
Components 规定标题适用含义，Layouts 规定左上标题区与固定样式；模型不生成字号、字重或几何参数。
首次工具和容量提示与该策略一致，不增加模型阶段或后处理造标题。

没有放宽任何空间合同：两项 TextList 必须带标题，三项 TextList 不带独立标题；四项 ComparisonGroup 仍无标题。
标题优先不是以删减必要记录为代价的硬门禁。若内容确需上述无标题结构，仍允许省略装饰主题。
Fewshot 数量、输入和输出均保持原样，没有新业务示例或新增测试标签。

## 验证

- 定向测试：382 passed；完整静态测试及容量恢复反馈回归：805 passed。两套有重叠，不相加。
- 本次新增回归检查全部 2×2/2×4 fewshot 的标题均接入根外框，并通过实际生产转换，防止出现孤立标题。
- 对本次全部变更 Python 文件执行 Ruff，通过；`git diff --check` 通过。
- 未执行企业 CodeCheck 或端侧真机验收。
- 首次尝试将一个小卡三记录示例换成带标题单行背板时，真实宽度检查失败；该示例修改已完整撤销，没有修改 Runtime 或放宽校验来容纳它。
- 初次测试另遇系统 Temp 目录权限错误，改用工作区测试临时目录后复测全部通过；初次失败结果不计入通过数量。

### 六条官方接口小批验证

使用不变的 Q008、Q009、Q013、Q039、Q040、Q041 原始任务，官方 DeepSeek，最多两轮生成、每轮最多五次修复，不额外重跑或择优。
六条输入逐字节一致，全部 Trace 本地保留。共 75.47 秒，3 成功、3 降级、0 失败；build_gallery.mjs 统一 Renderer 渲染 6/6，页面无 JavaScript 错误。

| Case | 上一批状态 | 本轮状态 | 本轮独立标题 |
|---|---|---|---|
| Q008 | degraded | success | 无，三项 TextList |
| Q009 | degraded | success | 无，三项 TextList |
| Q013 | degraded | degraded | 5G套餐对比（2026年9月官网价） |
| Q039 | success | success | 无，三项 TextList |
| Q040 | success | degraded | 无，三项 TextList |
| Q041 | success | degraded | 无，三项 TextList |

所选六条上一批均无独立标题，本轮 1/6 有标题。Q013 本轮仍有套餐记录遗漏，不能以“增加了标题”推导信息完整；
Q040/Q041 的状态也有回落。两批都为三成功三降级，但逐例并不等效。
本轮同时包含上游修复更新和标题提示变化，加上单次采样，不能将这些变化单独归因于标题，也不能据此声称整体质量提升。
高密度记录受原容量约束，仍会采用无标题形态；本次实现的是标题优先策略，不是所有卡片必有标题。

本地产物：`compact_dsl/output/1030-static-title-pr716-validation/gallery.html`。
运行配置、原始状态、标题统计、测试日志与截图均在同目录，不提交任务、Trace 或密钥。

## 本次提交的文件和用途

下表覆盖相对原 PR716 `6a9a2227` 的上游融合及本地标题优化。

| 文件 | 用途 |
|---|---|
| `debug_tools/Datasets/open_domain/Q056.json` | 同步上游删除旧动作任务 |
| `debug_tools/Datasets/open_domain/Q057.json` | 同步上游删除旧动作任务 |
| `debug_tools/Datasets/open_domain/Q058.json` | 同步上游删除旧动作任务 |
| `debug_tools/Datasets/open_domain/Q059.json` | 同步上游删除旧动作任务 |
| `debug_tools/Datasets/open_domain/Q060.json` | 同步上游删除旧动作任务 |
| `debug_tools/Datasets/open_domain/Q061.json` | 同步上游删除旧动作任务 |
| `debug_tools/Datasets/open_domain/Q062.json` | 同步上游删除旧动作任务 |
| `debug_tools/Datasets/open_domain/Q063.json` | 同步上游删除旧动作任务 |
| `docs/云侧方案设计.md` | 同步容量与修复合同，明确小标题优先及容量例外 |
| `docs/compact-dsl-validator-refactor/Compact_DSL现有校验规则分类清单_v1.md` | 上游静态覆盖回退的检查归属登记 |
| `docs/静态小标题优先与最新PR同步验证.md` | 本报告，记录范围、取舍、逐例结果及全部文件 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/static_content/information/common.md` | 共同主题与真实对象名称的语义边界 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/static_content/components/common.md` | 标题触发条件与三项 TextList 的确切容量边界 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/static_content/composition/common.md` | 先按信息形态选择带标题结构；公共正文实际占位 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/static_content/layouts/common.md` | 固定小标题样式与标题区职责 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/static_content/plan.md` | 标题事实的来源、角色和优先级；实际容量核算 |
| `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/static_content/repair.md` | 同步上游定向容量修复指导 |
| `widget_service/cloud/services/compact_plan.py` | 同步 Plan 修复与覆盖回退，静态工具标题说明 |
| `widget_service/cloud/services/static_text_capacity.py` | 首次容量提示与合法标题优先策略一致 |
| `widget_service/cloud/services/card_validation/compact_validation/api.py` | 上游静态最终覆盖核对适配 |
| `widget_service/cloud/services/card_validation/字段约束与演进记录.md` | 上游覆盖反馈行为登记 |
| `widget_service/cloud/services/compact_repair_strategy.py` | 上游按当前容量诊断生成修复指导 |
| `widget_service/cloud/services/compact_semantic_layout.py` | 上游静态共同信息与布局回退适配 |
| `widget_service/cloud/services/generation_pipeline.py` | 上游跨轮 Plan/生成上下文适配 |
| `widget_service/cloud/services/widget_generation_service.py` | 上游生成入口行为适配 |
| `widget_service/tests/test_capacity_recovery_warning.py` | 上游容量恢复反馈回归 |
| `widget_service/tests/test_static_prompt_source.py` | 公共正文占位及完整示例标题接入、转换回归 |
| `widget_service/tests/test_static_shared_header_repair.py` | 上游公共标题修复回归 |
| `widget_service/tests/test_static_validation_joint_capacity.py` | 上游容量与覆盖组合回归 |
