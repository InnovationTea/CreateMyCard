# Layer C 场景金样 · 按模板生成管线组织的分组说明

目录结构 = 模板生成管线阶段（`1_pipeline/`）→ 业务域垂直（`2_domain/`）→ 工具数据集（`3_tooling/`）。
场景 ID 保持 `<prefix>__<family>[_<key>]` 不变；**前缀 → 目录** 的映射登记在
`test_support/golden_scenarios.py` 的 `_SCENARIO_STAGE_MAP`（新增前缀登记一行即归位，
未登记的落 `unsorted/`）。改动引擎/模板后：
`python3 -m services.template_generation.test_support.golden_cli check --diff` 复核，
`bless --declared <场景ID>` 固化。

```
请求 → 能力注册表/协议 → preflight → ①检索计划 → ②组合展开(指令/动作/标记/转换/策略)
     → ③契约校验 → (stub LLM) → ④端到端矩阵 → DSL/A2UI        （域垂直套件贯穿全程）
```

## 1_pipeline/ — 按管线阶段

### retrieval/ · 第一层：检索与计划
| 分组 | 来源文件 | 冻结内容 |
|---|---|---|
| `retrieval` | test_template_retrieval.py | 双业务检索矩阵（30 组合的模板选择）、选择/拒绝矩阵 |
| `plan_planner` | test_template_plan_planner.py | 计划器组合（IconAction 资产约束、双根、仅步骤卡等） |
| `plan_data` | test_template_plan_data_usage.py | 计划的数据使用/覆盖契约 |
| `retired_app_usage` | test_retired_app_usage.py | 退役 App 使用域的检索兜底 |

### composition/ · 第二层：展开与组合
| 子组 | 分组 | 冻结内容 |
|---|---|---|
| directives/ | `provider_elseif` `provider_presence` `runtime_if` | `#if/#elseif` 指令矩阵、`#match present(...)` 基数选择、运行时延迟求值 |
| actions/ | `pill_action` `support_action` | Pill/IconAction 展开+降级树、Support 动作归属策略 |
| markers/ | `non_fusion` `provider_marker` | 安全边距包裹与 `__genui_render_component__` 骨架标记、组件标记契约 |
| conversion/ | `tersel_protocol` `a2ui_expression` `provider_expr` `style_enum` `text_heights` | Tersel 协议、A2UI 表达式、运行时表达式、样式枚举、文本高度 |
| policies/ | `image_color` `ux_title` `battery_palette` | 图片颜色策略、UX 标题策略、电池绿色主题策略 |
| templgen/ | `templgen` | 组合渲染：布局+动作+融合球、Q001/Q025/Q034/Q043 场景、绑定子集变体（stub LLM） |

### contracts/ · 契约与目录
| 分组 | 来源文件 | 冻结内容 |
|---|---|---|
| `internal_contracts` | test_template_internal_contracts.py | 7 布局蓝图、cardtpl 错误矩阵、主题解析、日志脱敏形状 |
| `provider_asset` | test_provider_asset_semantics.py | 每插槽允许资产来源集合、双业务并集、唯一匹配修复、清单拒绝 |

### matrix/ · 端到端矩阵
| 分组 | 来源文件 | 冻结内容 |
|---|---|---|
| `pipeline_combo` | test_template_pipeline_matrix.py | **TaskSpec→全链路 DSL 矩阵**：每个 2x2 模板 × 可选数据 2^k 缺席子集（stub LLM，其余真实管线），含拒绝组合冻结；`golden_cli combo-gallery` 可整表导出到 eval 应用端侧画廊（`pipeline_combo_gallery/`，ProviderScenarioGalleryPage 以 `dataset=pipelineCombo` 渲染每组合真实卡片） |
| `pipeline_combo_fusion` | test_template_pipeline_matrix.py | 同上矩阵的**融球模式变体**（`enable_fusion_ball=True`），与常规逐模板成对 |

`pipeline_combo` 家族的目录与文件名约定（本组特殊，其余分组文件名 = 场景 ID）::

    matrix/pipeline_combo/
      normal/<family>.json        ← 场景 ID pipeline_combo__<family>
      fusion_ball/<family>.json   ← 场景 ID pipeline_combo_fusion__<family>

文件名去掉 ID 前缀（目录已表达变体语义）；家庭 JSON 内含
`"fusionBall": true|false` 自述字段，以及顶层 ``sampleIds`` 映射
（`{组合键 → C001…C470}`，端侧画廊用例的顺序编号；两个变体共享同一编号，
单一事实来源 = 矩阵模块的 `combo_sample_ids()`）。前缀↔目录 ↔文件名的
双向映射在 `test_support/golden_scenarios.py`（`scenario_file_stem` /
`scenario_id_for_path`）。

## 2_domain/ — 业务域垂直套件（贯穿各阶段）
| 子目录 | 分组 | 冻结内容 |
|---|---|---|
| battery/ | `battery_action` `battery_caseext` | 电池域动作策略矩阵、用例扩展契约 |
| calendar/ | `calendar_geometry` `calendar_fullext` `calendar_reqcase` | 9 模板几何变体、header 变体、10 手工用例运行时绑定 |
| earphone/ | `earbud` `earbud_triple` `earphone` `bluetooth_hero` | 耳机投影/拒绝/facts、三电量完整 A2UI、耳盒意图、Hero 内容 |
| support/ | `support_refresh` | 21 Support × 数据/动作 4 组合的间距/字号/右图标矩阵 |
| travel/ | `travel_weather` | 出行卡片 Support 组合与动作落位 |
| weather/ | `weather_hero` | 天气 HeroTitle 数据分层与可选分支选择矩阵 |

## 3_tooling/ — 工具数据集产物
| 分组 | 来源文件 | 冻结内容 |
|---|---|---|
| `gallery_input` | test_provider_gallery_batch.py | gallery 输入数据集请求 JSON（双城/单城/跨业务配对） |
| `template_examples` | test_template_examples.py | template_examples 工具的示例渲染 |
| `preview_dataset` | test_template_preview_dataset.py | 预览数据集数据分层目录（Layer A 的数据档案） |

## unsorted/
未在 `_SCENARIO_STAGE_MAP` 登记的新前缀落在这里；登记一行即归位，正常情况应为空。
