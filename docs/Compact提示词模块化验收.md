# Compact 提示词模块化交付与验收

## 基线和范围

- 分支：`Br_feature_fusion`。
- 干净检出基线：`81c64b843bf957e878a846bfdc498e09c7242b36`。
- 本次只迁移单步提示词的维护与加载，不修改 CompactDSL 协议、转换器、校验器、模型轮次或模板优先链路。
- 吸收 Multi-step 的信息 / 组件 / 组合 / 布局 / 编排分层；独立 Plan 调用与新的 JSX 高阶组件尚未接入。
- 原 `design-compact-dsl` 目录的 6 份 Markdown 已移除，可从 Git 基线恢复；该目录仅保留协议参数。
  正式提示词只读取新包的 `generated/`，不存在旧路径回退。协议身份保持不变。

## 验证方法与结果

测试环境：Python 3.12，独立测试 venv；未调用线上生成模型。

| 验证 | 结果 |
|---|---|
| 6 份产物与拆分前原文逐字比较（统一 UTF-8/LF） | SHA-256 全部相同 |
| 30 个案例 × 融球开/关 × 创建/编辑/修复 | 180 组完整模型消息摘要全部相同 |
| 新增迁移、构建、加载回归 | 204 通过；从服务目录及仓库根目录运行均通过 |
| 全部正式 few-shot 的上下文校验与 A2UI 转换 | 30 通过 |
| 迁移测试 + 上述案例专项 | 234 通过 |
| 原相关测试（拆分前） | 492 通过、5 失败、1 跳过 |
| 相关测试 + 新增测试（拆分后） | 696 通过、5 失败、1 跳过；失败集合不变 |
| 全量服务 + 模板测试（独立原始检出） | 2845 通过、43 失败、16 跳过、24 子测试通过 |
| 全量服务 + 模板测试（拆分后） | 3049 通过、43 失败、16 跳过、24 子测试通过；43 个失败 nodeid 集合完全一致 |
| ConfigHelper 测试 | 4 通过 |
| 修改 Python 文件 Ruff | 通过 |
| 构建器 `--check` | 源与 6 份产物一致 |
| Git 差异空白检查（含新增提示词包） | 通过 |

相关命令（在 `widget_service` 中运行）：

```text
python scripts/build_compact_prompts.py --check
python -m pytest tests/test_compact_prompt_bundle.py tests/test_design_compact_few_shots.py::test_few_shot_validates_and_converts -q
python -m pytest tests/test_compact_prompt_bundle.py tests/test_design_compact_few_shots.py tests/test_service_units.py tests/test_compact_dsl_validator.py -q --tb=no
python -m pytest tests cloud/services/template_generation/tests -q --tb=no
python -m ruff check scripts/build_compact_prompts.py cloud/services/protocol_registry.py cloud/services/prompt_builder.py tests/test_compact_prompt_bundle.py tests/test_design_compact_few_shots.py tests/test_compact_dsl_validator.py
git diff --check
```

相关范围的 5 个基线失败：

1. `test_w9_allows_battery_percentage_formatted_hero[20-28]`。
2. `test_w9_allows_battery_percentage_formatted_hero[24-34]`。
   上述测试构造的状态字段直接展示 boolean，与现有校验规则冲突；正式 30 个 few-shot 均通过。
3. `test_phase_two_version_returns_phase_two_capability_overview`。
4. `test_phase_two_version_returns_phase_two_capability_schemas`。
   上述断言仍期待当前注册表中不存在的能力。
5. `test_model_runtime_collects_llmclient_stream`：测试预期与现有模型配置不同。

不把上述原有失败改成跳过，也不在提示词拆分任务中修改业务规则来消除它们。
全量对照另在原提交的独立 Git worktree 中运行同一命令，原始范围 2904 项，拆分后 3108 项；
两次均有一个相同的 FastAPI/Starlette 测试客户端弃用告警。对两处 pytest `lastfailed` 的完整 nodeid
集合排序比较，无新增或减少失败。43 项分布如下，并非只比较失败数量：

| 测试文件 | 原始 / 当前失败数 |
|---|---:|
| `tests/test_asset_mapping_generation.py` | 4 / 4 |
| `tests/test_compact_hero_typography.py` | 4 / 4 |
| `tests/test_design_compact_few_shots.py` | 2 / 2 |
| `tests/test_generation_preflight.py` | 1 / 1 |
| `tests/test_service_units.py` | 3 / 3 |
| `tests/test_template_ring_geometry.py` | 10 / 10 |
| `template_generation/tests/test_provider_asset_semantics.py` | 7 / 7 |
| `template_generation/tests/test_provider_gallery_batch.py` | 1 / 1 |
| `template_generation/tests/test_runtime_if_deferred.py` | 6 / 6 |
| `template_generation/tests/test_template_examples.py` | 1 / 1 |
| `template_generation/tests/test_template_generation.py` | 2 / 2 |
| `template_generation/tests/test_template_retrieval.py` | 2 / 2 |

本次没有进行线上随机模型生成质量测试或真实端侧截图验收。等价输入和确定性转换回归证明拆分没有
改变这些受测链路，不能代替后续规则变化的端侧视觉验收。

## 修改文件及用途

### 加载、构建与测试

| 文件 | 用途 |
|---|---|
| `docs/云侧方案设计.md` | 先登记模块边界、加载和兼容策略、未来融合边界 |
| `docs/Compact提示词模块化验收.md` | 本交付清单与验证记录 |
| `widget_service/cloud/services/protocol_registry.py` | 协议身份到新生成目录的唯一正式路由；统一读取尺寸案例 |
| `widget_service/cloud/services/prompt_builder.py` | few-shot 改用同一注册表路由；原筛选和布局裁剪算法不变 |
| `widget_service/cloud/config/default_config.yaml` | 默认文件引用切到新目录 |
| `widget_service/scripts/build_compact_prompts.py` | 确定性构建与只读检查；拒绝缺失、重复、漏登记、越界路径等 |
| `widget_service/pyproject.toml` | 测试路径包含服务根，支持从仓库根导入构建脚本 |
| `widget_service/tests/test_compact_prompt_bundle.py` | 文本/模型消息等价、缺失不回退、构建错误与未同步检查 |
| `widget_service/tests/fixtures/compact_prompt_migration_baseline.json` | 原提交的 6 份文本与 180 组消息摘要；非运行时依赖 |
| `widget_service/tests/test_design_compact_few_shots.py` | 正式案例测试转向新产物路径 |
| `widget_service/tests/test_compact_dsl_validator.py` | 提示词约束测试转向新产物路径 |
| `widget_service/README.md` | 提示词维护入口与参数恢复文档路径 |
| `widget_service/docs/method_usage.md` | 同步参数恢复路径 |
| `widget_service/docs/arguments兜底流程说明.md` | 同步参数恢复路径 |
| `widget_service/docs/generateWidgetCardCompactDsl数据流.md` | 同步创建/编辑路径与构建说明 |
| `widget_service/docs/generate-widget-card-compact-dsl-flow.svg` | 数据流图标明模块化源到生成产物 |

### 提示词包

新增目录：`widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/`。
逐项职责、源文件与完整案例索引见 [提示词包 README](../widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/README.md)
及 [manifest](../widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/manifest.yaml)。

- `.gitattributes`：固定 LF，避免 Windows checkout 改写换行导致产物漂移。
- `README.md`：分工、构建、维护说明不入模、兼容与演进边界。
- `prompt_source/manifest.yaml`：全部 49 个入模源文件、尺寸范围、片段加载顺序、案例索引。
- `prompt_source/core.md`：全局输入输出、绑定/数据/事件/资源、视觉参数和禁止检查。
- `prompt_source/information/common.md`、`information/2x2.md`、`information/2x4.md`：信息归属、取舍及尺寸密度。
- `prompt_source/components/common.md`、`components/2x2.md`、`components/2x4.md`：组件 Props、绑定与尺寸限制。
- `prompt_source/combinations/common.md`、`combinations/2x2.md`、`combinations/2x4.md`：局部组合和适用边界。
- `prompt_source/layouts/common.md`、`layouts/2x2.md`、`layouts/2x4.md`：画布预算与 S/W 骨架。
- `prompt_source/composition.md`：一次调用内的决策顺序和冲突优先级。
- `prompt_source/repair.md`：DSL 修复合同。
- `prompt_source/edit.md`：编辑包装合同。
- `prompt_source/argument_repair.md`：JSON 参数恢复及其原有案例。
- `prompt_source/fewshots/2x2/preamble.md` 与 `fewshots/2x4/preamble.md`：保留原尺寸共用说明。
- `prompt_source/fewshots/2x2/2x2-V00.md` 至 `2x2-V14.md`：15 个各自完整的原小卡案例。
- `prompt_source/fewshots/2x4/2x4-V00.md` 至 `2x4-V14.md`：15 个各自完整的原宽卡案例。
- `prompt_source/fewshots/repair/README.md`：修复案例准入；基线没有独立 DSL 修复案例，本步不增加在线案例。
- `generated/PROMPT.md`、`EDIT_SYSTEM_PROMPT.md`、`REPAIR_SYSTEM_PROMPT.md`、
  `ARGUMENT_REPAIR_SYSTEM_PROMPT.md`、`FEWSHOT_2x2.md`、`FEWSHOT_2x4.md`：6 个自动产物。

上述 6 个产物分别替代并删除旧 `design-compact-dsl/` 下同名 Markdown，不删除 `protocol.json`。
维护人员只编辑源，构建后提交源和产物；不编辑生成文件，也不为使摘要测试通过而无评审地更新基线。
