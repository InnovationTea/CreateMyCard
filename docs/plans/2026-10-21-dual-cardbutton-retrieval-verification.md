# 双CardButton与结构检索验证记录

## 范围与结论

基于main `cffe6094`，分支 `codex/2x2-dual-cardbutton-fewshots-20261021`。
2×2双动作改为两个CardButton，组件Props、语义槽位、Plan归一化、容量和校验同步；单动作不改。
2×4案例及其A2UI产物逐例对比10/10不变，但默认检索开启后只加载结构匹配的最多4例。
未更改测试输入、必要事实/动作校验、warning降级政策、修复次数或模型提供方。

## 开关

```bash
# 默认开启：Plan后按结构检索最多4例
WIDGET_SERVICE_ENABLE_DESIGN_COMPACT_FEW_SHOT_SELECTION=true
# 关闭检索：加载本尺寸全部案例（当前2×2为18例，2×4为10例）
WIDGET_SERVICE_ENABLE_DESIGN_COMPACT_FEW_SHOT_SELECTION=false
# 独立总开关：false时完全不加载案例
WIDGET_SERVICE_ENABLE_DESIGN_COMPACT_FEW_SHOTS=false
```

Plan阶段不加载案例。检索按同尺寸和运行时动作容量过滤，再按密度35%、动作30%、布局20%、组件15%
评分；缺失候选维度重归一化，匿名结构去重。少于4个合法结构时不以错误布局补足。无关键词、无测试标签。

## 官方DeepSeek真实生成

原始20261016_request_baseline中的Q044/Q046/Q048，每条运行一次，最多5次修复、失败最多再请求一轮。
实际三条均首轮成功、零修复、各两个CardButton。每条Plan要求的动态字段2/2、动作2/2覆盖。

| 案例 | 当前校验结果 | 修复 | 端到端耗时 | 仍存在的视觉warning |
|---|---|---:|---:|---|
| Q044 | success | 0 | 10.634秒 | 正文42/38vp，长按钮标签省略 |
| Q046 | success | 0 | 5.797秒 | 长按钮标签省略 |
| Q048 | success | 0 | 5.869秒 | 正文44/38vp，图文仍偏拥挤 |

这是合同成功，不是视觉无瑕疵或多次稳定性结论。保留main现有warning行为，没有为证明成功放宽校验。
仍需后续处理小卡紧凑正文的视觉容量和长标签，这次不加入针对这三条业务内容的规则。

统一build_gallery.mjs渲染3/3成功，浏览器0脚本错误、0损坏图片；截图人工复核发现上述限制。
模型调用含Plan、DSL及主题阶段，耗时不是仅末次DSL请求。

## 检索对照

固定此前88条已接受Plan，用同一算法比较原14/10例库与新18/10例库，不调用模型、不以输出做标签。

| 尺寸 | 历史Plan | 新增示例前 | 新增示例后 | 检索排序变化 | Top1事实数差距中位数 |
|---|---:|---|---|---:|---|
| 2×2 | 52 | 6条取1例，46条取4例 | 6条取3例，46条取4例 | 27条 | 0 → 0 |
| 2×4 | 36 | 36条取4例 | 36条取4例 | 0条 | 1 → 1 |

三条双动作真实生成均注入V03、V18、V17，Plan阶段案例数0；没有混入单按钮或无按钮的父布局。
平均被选案例字符约6172/9844，相比全量30503/21654少约80%/55%；仅指示例段，不是总Prompt或Token。

## 泄露审计

新增V15来自旧V06子集，V16来自V02子集，V17/V18来自V03子集；无新增业务路径、动作目标或字段共现对。
两套仓库数据414处输入、202条不同userQuery，与4个新例子均无原文相同；没有搬用测试正确卡片。
新增结构示范仍增加教学信息，不承诺泄露风险绝对为零，不以三条通过声称泛化提升。

## 本地检查

- 相关与扩大回归：668 passed、1 skipped、14 deselected、62 subtests passed。
- 额外Prompt边界、运行时上下文、Repair与配置：61 passed。合计729项通过，不含子测试。
- 14项历史迁移快照断言因旧示例输入/ID不一致单独排除，不计作通过；没有为其更新业务快照。
- 所有改动Python通过Ruff；git diff --check通过。未运行整个仓库的全量测试。
- 全部28例正式转换、统一渲染通过；2×4原10例输入/DSL/A2UI不变。

## 全部修改文件及用途

以下目录前缀简写仅用于维护清单，不发给模型：
`P = widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/`；
`R = widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/runtime/`；
`S = widget_service/cloud/services/`；`T = widget_service/tests/`。

| 文件 | 用途 |
|---|---|
| docs/云侧方案设计.md | 双动作组件合同、默认结构检索与开关，清理相反旧描述 |
| docs/compact-dsl-validator-refactor/Compact_DSL现有校验规则分类清单_v1.md | 登记槽位和纯动作校验归属 |
| docs/plans/2026-10-21-small-dual-cardbutton.md | 双CardButton实施范围及验收 |
| docs/plans/2026-10-21-structural-fewshot-selection.md | 结构检索接入与验证计划 |
| docs/plans/2026-10-21-dual-cardbutton-retrieval-verification.md | 本验证记录及全部文件清单 |
| widget_service/cloud/config/config.py | 检索默认开启；等价导入排序 |
| widget_service/cloud/config/default_config.yaml | 默认开关及用途说明 |
| P/components/common.md | 共享CardButton Props与边界 |
| P/components/2x2.md | 小卡双槽可用性和单/双行容量 |
| P/components/2x4.md | CardButton通用细则迁往Common，保留宽卡差异 |
| P/layouts/2x2.md | 双CardButton角色与标准/纯动作模板 |
| P/fewshots/2x2.md | 更新V03、增加V15–V18，无新增测试答案 |
| P/manifest.yaml | 新示例片段及加载顺序 |
| P/plan.md | 双动作CardButton推荐与提示 |
| P/repair.md | 纯双动作修复合同保持一致 |
| R/layout-contracts-v1.json | 36vp/57vp双CardButton槽和角色 |
| R/visual-recipes-v1.json | 2×2 CardButton视觉Recipe，不改2×4 Recipe |
| S/compact_component_semantics.py | 小卡候选枚举增加CardButton |
| S/compact_composition_planner.py | 动作按槽选组件，使用对应槽高验算 |
| S/compact_high_level_components.py | 小卡CardButton展开及两行标签容量检查 |
| S/compact_plan.py | 双必要动作软候选与上下文归一化 |
| S/compact_semantic_layout.py | 双槽只收CardButton，固定内部几何和角色检查 |
| S/prompt_builder.py | Plan后注入结构精选，关闭检索时保持全量 |
| S/compact_structural_fewshots.py | 纯结构特征、容量过滤、评分、匿名去重与完整案例选择 |
| S/card_validation/compact_validation/semantic/plan_contracts.py | 纯双CardButton仍须Plan授权且无信息丢失 |
| S/card_validation/字段约束与演进记录.md | 同步纯双动作校验记录 |
| T/test_small_card_button_slots.py | 新增双槽、旧组件拒绝、绑定/动作/容量保护测试 |
| T/test_compact_structural_fewshots.py | 新增结构检索与开关测试 |
| T/test_compact_actions_only.py | 纯双动作样例同步CardButton |
| T/test_compact_plan.py | 小卡候选枚举与双动作Plan期望 |
| T/test_compact_plan_selection.py | 双动作归一化期望 |
| T/test_compact_prompt_bundle.py | 18例加载及组件共享合同 |
| T/test_compact_semantic_small_layout.py | 语义双槽角色与几何转换回归 |
| T/test_design_compact_few_shots.py | 28例正式转换、纯动作Plan与字号回归 |

运行产物位于compact_dsl/output/1021-dual-cardbutton-live-v1和1021-small-dual-cardbutton，
不提交输入、请求、Trace、密钥、原始模型输出或Gallery到仓库。
