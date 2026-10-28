# Compact 错误驱动修正器方案

## 1. 目标与范围

修正器接收原校验器报告的 error，先使用确定性脚本修改 Compact DSL；脚本无法消除的错误，交回原模型修复流程。校验通过或只有 warning 时，不启动脚本优化。

本方案在现有处理与校验之后补充空间与组件合同修复规则，保留主线已有的重组与候选搜索。不修改校验器判定、严重程度、模型重试次数，也不增加评分或审美优化。

修正对象是 Compact 源码，而不是最终 A2UI。每次候选都重新转换和校验，采用版本的 Compact、A2UI 和诊断共同传递。

## 2. 执行流程

```text
当前 Compact
  → 原静态评估：Compact 校验、转换、按配置执行完整产物校验
  → 没有 error：继续原主题与交付流程
  → 存在 error：根据结构化诊断选择脚本规则
       → 生成一个修改候选
       → 使用原静态评估复检
       → 有安全进展：采用候选，继续处理剩余 error
       → 无安全进展：拒绝候选，尝试下一候选
  → 没有适用规则或候选预算耗尽：返回当前采用版本及剩余 error
  → 原模型修复开启且有剩余次数：模型修 Compact，再进入上述流程
  → 原模型修复关闭、策略不允许或次数耗尽：沿用原失败处理
```

“静态评估”不需要截图，不启动浏览器。程序根据 DSL、协议、数据定义和参考布局计算可确定的问题；该过程不是实际端侧排版。

## 3. 脚本规则

| 规则 | 输入依据 | 修改动作 | 不处理的情况 |
| --- | --- | --- | --- |
| 按钮空间 `button-slot` | 宽高超限诊断、组件及超限量 | 对包含按钮的非根布局容器，尝试扩展已明确声明的宽或高 | 没有数值尺寸、不能定位源容器、修改后没有安全进展 |
| 父容器预算 `parent-budget` | 宽高超限诊断 | 尝试减少正数间距，或扩展非根容器已声明的宽高 | 无明确空间依据，或变换、复杂约束使规则不适用 |
| 兄弟空间 `sibling-space` | 横向超限诊断、父 Row 和原权重 | 在有限倍率中尝试调整原有正数 `layoutWeight` | 不是父 Row 内的加权区域，或没有原权重 |
| 重复点击 `duplicate-click` | `COMPACT_CLICK_HANDLER_COUNT` | 全部 handler 的 `call/args` 完整且完全相同时，仅保留第一个 | 不同动作、不同参数、JSON 类型不同、缺字段；不会补 Intent 或猜动作 |
| 高度闭合 `height-closure` | `COMPACT_LAYOUT_HEIGHT_UNRESOLVED` | 共享布局求解器确认直接父 Row 高度后，为缺 height 的 Column 尝试补 `matchParent` | 父高度未知、存在不支持约束，或候选引入新的超限 |
| 语义布局 `semantic-layout` | 已有宽高超限诊断和本轮处理上下文 | 尝试登记的动作／上下变体、只读 Group 横纵重组、主辅内容分组、SecondaryBody 列数 | 不删减内容，不调整字号，不移动固定 InfoBlock 槽或动作，不改展开节点；原校验不通过则拒绝 |

前三类空间规则处理源文件中显式存在的 Row/Column；语义布局规则处理 Layout、Region、Group 及其关联辅助内容。只处理报错子树及祖先，原文字、表达式、数据行和动作保留。无法从诊断定位源节点时不改内部展开节点。

### 3.1 组件与内容合同扩展

| 规则 | 修改依据与范围 |
| --- | --- |
| `known-component` | 仅识别已知的纯正文 ContentBlock.body 形状，转换为登记的 EmphasisText；未知字段不丢弃、不通用猜测组件名 |
| `primary-content` | 辅助信息是唯一信息主体时，将完整标签／值条目放入登记的 TableText 或其只读分组，不删条目、不压小字号 |
| `action-slot` | 已有完整点击动作的按钮类型与声明槽位不符时，只改为该槽位要求的按钮类型；不生成 Intent 或 onClick |
| `asset-reference` | 素材 ID 精确映射本轮候选 src；已接受 Plan 分配的标题图标未落实且标题唯一时补齐，不做相近名替换 |
| `plan-fact` | 仅补至多两项可从 Plan 精确定位、已授权且已初始化的缺失事实；字符串使用原绑定，布尔值按“是／否”展示；不写入或虚构数据。无标题且 Plan 指定标题组件时可补单项标题 |
| `fixed-slot` | 宽卡内容区误嵌一个固定 InfoBlock 时，将完整原组件移至已登记四槽布局；其余标题、信息和动作全部保留 |
| `numeric-label` | DataDisplay 绑定 Schema 中的数值且缺 label 时，使用一至八字的 CardSpec 标题补标签；图标已由标题承载时才可在数值区转用文字标签 |
| `event-target` | Plan 动作在 TaskSpec 中仅对应一个精确候选时，纠正同 Intent 的已有 handler；多个候选或缺动作时不猜改 |

各规则独立开关与 `enable_compact_*_repair` 配置一一对应，新增规则仍受脚本总开关控制。
确定性组件修复可能先解除早期合同阻断、再暴露布局错误。初始候选后允许最多追加三步前瞻，所有候选复检均
计入原预算；未满足 `_improved()` 的中间版本只保存在 Trace，不作为当前采用源传给下游。
前瞻最终结果仍与本轮采用源比较，不用“错误层级向后移动”冒充修复成功。

## 4. 候选采用标准

静态脚本调用 `repair_static_errors()`，每个候选通过原评估回调复检后，按 `_improved()` 判断：

1. 错误事实减少，或同一处已定位问题的量化超限严格下降，不只是错误消息变了。
2. 没有新增错误事实。
3. 剩余错误中，已知的超限量没有增大或变为未知。
4. 没有新增 warning。

符合条件时允许采用部分修复成果。例如两个错误修好一个，可以把已采用版本和剩余一个错误继续交给脚本或模型。部分修复不是最终通过；最终仍有 error 时不得作为成功产物交付。

展开节点映射到同一源组件时，用独立证据组件和属性区分各处错误，避免只留下最后一条超限。
语义角色修复保持 EventCard 的全部条目和字段，把它移入允许承载该组件的 Region；不将十条行程压成两三条摘要。

2×4 容量错误还允许在已登记的 `W-top-bottom` 与 `W-split-panels` 之间转换：
上下一体的标题、主内容和完整明细可分入两个只读 Region；反向仅识别
`title-content`＋`center` 两分区，且明细为原上下布局允许的 SummaryList 或 TopTextBottomValue。
不更换业务组件、不改叶子属性和数据行。只有标题而没有独立主内容的明细卡不自动拆成左右分区。
文字单行超宽使用校验器补充的结构化宽度诊断，不通过字符串匹配报错文案判断。

失败候选仅写入调试记录，不替换当前采用版本。没有 error 的样本保持原文，不为统一样式而改写。

## 5. 配置开关

| 配置 | 默认 | 用途 |
| --- | --- | --- |
| `enable_compact_script_repair` | `false` | 静态脚本总开关，显式开启后生效 |
| `enable_compact_button_slot_repair` | `true` | 按钮空间规则 |
| `enable_compact_parent_budget_repair` | `true` | 父容器预算规则 |
| `enable_compact_sibling_space_repair` | `true` | 兄弟空间规则 |
| `enable_compact_duplicate_click_repair` | `true` | 完全重复点击去重 |
| `enable_compact_height_closure_repair` | `true` | 高度关系闭合 |
| `enable_compact_semantic_layout_repair` | `true` | 尝试已登记布局，优先保持方向 |
| `enable_compact_known_component_repair` | `true` | 纠正已知正文组件形状 |
| `enable_compact_primary_content_repair` | `true` | 辅助信息的主体合同 |
| `enable_compact_action_slot_repair` | `true` | 已有按钮槽位角色 |
| `enable_compact_asset_reference_repair` | `true` | 本轮素材 ID 精确映射与标题分配 |
| `enable_compact_plan_fact_repair` | `true` | 至多两项已初始化的缺失事实 |
| `enable_compact_fixed_slot_repair` | `true` | 固定信息组件移入登记槽位 |
| `enable_compact_numeric_label_repair` | `true` | 补数值标签，不丢唯一图标 |
| `enable_compact_event_target_repair` | `true` | 唯一动作候选的参数纠正 |
| `compact_script_max_candidates` | `12` | 单次生成流程的累计脚本候选上限；模型质量重试不重置 |
| `enable_validation_failure_retry` | 沿用原配置 | 是否允许剩余 error 进入模型修复 |
| `validation_failure_max_repair_attempts` | 沿用原配置 | 模型质量修复次数，不被脚本候选次数占用 |

不需要图片输入，也不需要 OCR。Web 画廊可以在批跑后单独出图，供查看效果；截图不是本修正器的输入或通过依据。

## 6. 代码与职责

| 位置 | 职责 |
| --- | --- |
| `widget_service/cloud/services/widget_generation_service.py`：`evaluate_source_dsl_sync` | 原静态评估，返回源文、A2UI 和完整诊断 |
| 同文件：`evaluate_source_dsl` | 有 error 时调用脚本，更新当前采用版本与剩余错误 |
| `widget_service/cloud/services/compact_script_repair.py`：`static_candidates` | 调度合同候选，并根据结构化诊断生成结构及空间候选 |
| `widget_service/cloud/services/compact_contract_repair.py` | 结合明确报错、登记合同与本轮上下文生成八类组件／内容候选 |
| 同文件：`repair_static_errors`、`_improved` | 管理候选预算、复检、采用与拒绝 |
| `widget_service/cloud/services/widget_generation_service.py`：`repair_source_dsl` | 将当前采用的 Compact 和对应错误交给原模型修复 |
| `debug_tools/batch_testing/trace_semantics.py` | 调试记录的中文名称 |
| `debug_tools/platform/src/components/TraceViewer.tsx`（复用现有实现） | 查看候选的输入、输出、诊断和采用原因 |

依赖方向为 Debug Tools 调用微服务；微服务不依赖 Debug Tools。默认静态修复不调用渲染器。

## 7. Debug Tools 实跑步骤

### 7.1 启动

在仓库根目录安装锁定依赖后启动调试平台（Python 3.12）：

```powershell
uv sync
$env:NO_PROXY = "127.0.0.1,localhost,::1"
uv run python -m debug_tools --mode frontend
```

在浏览器打开启动日志给出的 `/debug/` 地址。真实模型凭据仅通过本地私有配置或环境变量提供，不写入本文或测试数据。

`NO_PROXY` 仅设置当前进程及其子进程的本机地址代理绕过，避免 WebSocket 请求被 Windows 系统代理转发；不修改系统代理设置。

### 7.2 对照批跑

1. 选择一个实际数据集，先取少量样本探测服务与模型连通性。
2. 固定样本、请求版本、模型参数及原校验配置。
3. 基线任务关闭脚本总开关；实验任务开启脚本及目标规则；两边均开启 Trace。
4. 每个任务产生新的执行目录，保留全部原始输入和历史产物。
5. 先检查模型是否确实返回 DSL，再统计脚本是否命中、修改是否采用，以及错误是否消除。
6. 需要看卡片时，再显式执行浏览器画廊后处理并查看最终 DSL、图片和 Trace。

两次重新生成不是同一份初始 DSL，因此只能反映端到端表现，不能把全部差异归因于修正器。严格的规则效果对照应固定同一份历史初始 Compact 和同次上下文，分别关闭、开启脚本回放。

### 7.3 结果判读

逐样本至少记录：来源、初始 error、规则命中、候选数、采用修改、最终 error、剩余原因、模型修复次数、产物是否存在。

批次至少区分：

- 原本无 error，未修改；
- 脚本修复后静态通过；
- 脚本部分修复，仍有 error；
- 无规则或全部候选被拒绝；
- 模型或服务调用失败，未生成 DSL；
- 检测或上下文不足，无法完成评估。

查看 Trace 中的 `compact.script.candidate` 和 `compact.script.decision`，重点看 `accepted`、前后错误数、`reasonCode` 和 `next`。步骤执行完成不等于修复成功。

服务或模型连通性失败时停止扩大批次，不使用 Mock 结果代替真实实跑结果。测试夹具回归与真实批跑分别报告。

## 8. 验收口径

本方案的直接目标是：原校验器确认的 error 被安全减少或消除，原本通过的样本不被额外修改。静态通过、Web 预览正常、原生渲染正常和训练集最终验收是不同结果，应分别记录。

验证命令在 `widget_service/` 下执行：

```bash
python -m pytest tests/test_compact_contract_repair.py tests/test_compact_script_repair.py tests/test_compact_script_extensions.py tests/test_compact_semantic_repair.py tests/test_compact_repair_progress.py tests/test_compact_script_main_chain.py -q
python -m ruff check cloud/services/compact_contract_repair.py cloud/services/compact_script_repair.py cloud/services/widget_generation_service.py cloud/config/config.py
git diff --check
```

正式入口回归使用真实 WebSocket 路由、转换、校验、脚本、模型重试控制器和保存逻辑，
只替换模型输出与主题阶段；另验证候选预算跨两轮模型修复不重置。它不调用付费模型或渲染器。

历史开发版本固定输入回放共 114 份：73 份原本通过且未修改，18 份脚本修复后静态通过，
8 份部分改善，15 份未解决。此为开发基线的回放结果，不是最新 main 的在线成功率。
新增 15 份静态修复样本的 Web 预览中，14 份未命中当前 Web 检查，1 份仍有日程时间裁剪：
窄列内标题换成两行，实际高度超过静态固定行盒。该问题属于文字换行后的高度检测缺口，
本次不改变校验阈值或宣称已解决。

合入前运行当前分支的定向回归、主链回归、Ruff 和差异检查；实际结果记录于 PR。
企业 CodeCheck、端侧渲染与训练集最终验收分别执行，不以单元测试替代。
