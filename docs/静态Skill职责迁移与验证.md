# 静态 Skill 职责迁移与验证

## 范围

以main 448b6502为基线，仅归位与去重静态模型规则并调整装配。
不改变Plan Schema、组件/布局合同、试排、校验、删除授权、模型阶段或重试预算。
动态阶段Prompt按尺寸与阶段逐项计算SHA-256，与冻结基线一致。

## 规则迁移

| 原来源 | 新位置（均在static_content内） | 保留内容 |
|---|---|---|
| common开头、DSL素材与主题说明 | core.md | 静态快照、来源权限、动作素材、主题及试排证明边界 |
| common摘要与归属、Plan取舍原则 | information/common.md | 核心/补充、忠实摘要、对象关系、共同条件、原文要求 |
| common组件段及各阶段重复文字规则 | components/common.md | 共享正文、辅助标题/说明/动作、字号档位 |
| common对比组件段 | components/2x4.md | ComparisonGroup选型、数量、字段与细节上限 |
| common布局段、重复根变体说明 | layouts/common.md | header/body/note、顺序、贴底互斥、完整容量核算 |
| common及DSL的小卡动作例外 | layouts/2x2.md | S布局、title-action、无正文单Action及回退条件 |
| common宽卡动作路由 | layouts/2x4.md | W布局、分区动作与纯四CardButton |
| common执行组织、Plan综合选型 | composition/common.md | 综合流程、超限完整要求、先完整后should |
| Plan的小卡/宽卡建议 | composition/2x2.md、2x4.md | 小卡一个重点/两短记录，宽卡两说明记录/三短记录 |
| Plan同构活动记录触发 | components/common.md的RecordList | 原有活动/日程/演出/行程及分类压缩限制，未新增领域 |
| Plan记录组上限与取舍 | plan.md | records最多3个object，明确优先级或原顺序，其余登记遗漏 |
| Plan字段、引用、分组与自查 | plan.md | 24事实、sourceTexts、identity、索引、规划与遗漏记录 |
| DSL执行段 | dsl.md | 忠实复核、核心冻结、共同范围补充的原有例外 |
| Repair操作段 | repair.md | 修复顺序、合法形态、核心/原文保护、无解如实失败 |
| 原两个fewshots文件 | fewshots/2x2.md、2x4.md | 7+8完整案例的模型可见正文逐字不变 |

每个文件以YAML维护description明确职责，模型只收到正文。
各模块采用总表后细则；组件参数和父布局角色分别归各自模块，没有新增万能组合层。

## 装配

staticContent.modules登记适用尺寸。创建合同按Core、信息、组件、布局、综合流程装配。
加载器按目录和尺寸缓存，拒绝重复登记、阶段内/跨阶段重复引用、未知尺寸、未登记引用、
路径越界、未闭合维护头、空资源、未使用模块及不一致的示例索引。
Few-shot仍在Plan之后追加，Repair仍在反馈后追加，不重建第二份共享System上下文。
初始static_capacity_prompt保留完整运行时容量JSON，Plan仅补参考画布，不再展开相同规格。

| 尺寸 | few-shot模型正文SHA-256 |
|---|---|
| 2x2 | 30aeaabea14ee9906ef519fb9efd6452c471af69596b9ddf76640e1c1ce7a192 |
| 2x4 | 1a0592c7390c0fb69a8b69068135a97d96d25541d40ca3581ec24cd5a7a0aa08 |

## 修改文件清单

以下Prompt路径相对`widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/`：

- `manifest.yaml`：模块尺寸、阶段顺序和新案例路径。
- `static_content/core.md`：静态协议。
- `static_content/information/common.md`：信息组织。
- `static_content/components/common.md`：共享组件。
- `static_content/components/2x4.md`：宽卡对比组件。
- `static_content/layouts/common.md`：共享布局角色与容量。
- `static_content/layouts/2x2.md`：小卡路由。
- `static_content/layouts/2x4.md`：宽卡路由。
- `static_content/composition/common.md`：综合流程。
- `static_content/composition/2x2.md`：小卡现有建议。
- `static_content/composition/2x4.md`：宽卡现有建议。
- `static_content/plan.md`：阶段字段与引用。
- `static_content/dsl.md`：阶段执行。
- `static_content/repair.md`：反馈修复。
- `static_content/fewshots/2x2.md`、`2x4.md`：原案例迁移和维护头。
- `static_content/common.md`（删除）：原混合合同归入上述职责。

其它文件均为仓库相对路径：

- `widget_service/cloud/services/static_prompt_source.py`：静态装配、验证、过滤及缓存。
- `widget_service/cloud/services/compact_prompt_loader.py`：公开入口委托，动态装配不变。
- `widget_service/cloud/services/prompt_builder.py`：删除两尺寸重复预加载。
- `widget_service/tests/test_static_prompt_source.py`：职责、尺寸、缓存、异常及案例不变回归。
- `widget_service/tests/test_static_content_generation.py`：新路径与阶段装配断言。
- `docs/云侧方案设计.md`：总方案登记。
- `docs/开域静态内容卡片技术方案.md`：专项装配设计。
- `docs/开域静态内容卡片实施与验证记录.md`：历史路径迁移说明。
- `docs/plans/2026-10-28-static-skill-boundaries.md`：实施计划。
- 本文件：迁移、文件清单与验证。

## 自动化验证

- 静态及装配回归：352项通过。
- 公共Prompt、Plan、Repair及校验扩展：347项通过，1项既有失败。
- 既有失败为`test_compact_plan_output.py::test_wrapped_plan_keeps_original_contract_errors[fact2]`，
  在未修改的448b6502独立检出中同样失败；本轮不修改其行为或断言。
- 对变更Python执行Ruff、检查差异空白和职责边界；未执行企业CodeCheck与真机验收。

## 真实模型验证

两组均使用448b6502、open_domain原始55条、DeepSeek官方通道、全部同尺寸few-shot、检索关闭，
每轮最多5次质量修复、最多两次完整生成，批跑脚本不额外重跑。原始输入逐文件SHA-256一致。

| 尺寸 | 未重构：成功/降级/失败 | 重构后：成功/降级/失败 | 平均完整请求耗时：前→后 |
|---|---|---|---|
| 2x2（15条） | 11 / 4 / 0 | 11 / 4 / 0 | 6.41s → 7.26s |
| 2x4（40条） | 22 / 18 / 0 | 26 / 14 / 0 | 7.43s → 6.48s |
| 合计55条 | 33 / 22 / 0 | 37 / 18 / 0 | 7.15s → 6.69s |

两组全部55条进入static_content并成功交付，均由build_gallery.mjs渲染55/55。
重构后有一个小卡样本使用5次质量修复，最终在第二轮成功；总计两条样本进入第二轮，对照为七条。
降级及成功状态由原公共响应判定，未修改其标准。时延包含Plan、完整生成、修复、主题与交付。

从Trace读取每条样本第一次Plan模型请求，统计所有消息content的字符数：

| 尺寸 | 重构前平均字符 | 重构后平均字符 | 减少 |
|---|---|---|---|
| 2x2 | 22,003.8 | 19,840.8 | 9.83% |
| 2x4 | 22,021.5 | 20,037.5 | 9.01% |

这是实际装配请求字符，不是Token数量，也不是单个md文件的长度。
初始共享合同变长，后续Plan/DSL/Repair明显变短，不能只用某一阶段增减解释总效果。
已接受Plan落实不代表原输入摘要忠实，本次单轮结果只证明回归未见失败率恶化，不证明统计上的质量提升。
之前31ea5ec9的45/7/3结果仅作历史参考，因主仓已合入PR668，不能作为本轮重构因果对照。
