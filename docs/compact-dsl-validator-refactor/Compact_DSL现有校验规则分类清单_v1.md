# Compact DSL 现有校验规则分类清单 v1

- 日期：2026-09-30
- 依据：[Compact DSL 校验器重构方案 v3](Compact_DSL校验器重构方案_v3.md)
- 状态：现状盘点与迁移归属建议，尚未修改校验实现。
- 统计基线：当前工作区源码，不代表某个发布版本；行号随后续修改可能变化，定位优先使用函数名。

## 1. 范围和阅读方式

本清单盘点 `widget_service/cloud/services/card_validation/compact_dsl_validator.py` 的现有校验，
并说明它直接调用的解析器、双动作校验和组合组件校验的边界。
不将整个转换器或转换后的标准 A2UI 校验规则混算为该脚本中的规则。

按源码 AST 统计，主脚本有 **153 个 `errors.append` 位置，分布于 47 个函数**。
其中 2 个位置只是转发 CardHeader、TimelineUnit 的异常，不是两条独立业务规则。
另有 1 个未使用数据声明的警告输出位置，以及入口的解析异常包装。
这些是静态输出位置数量，不是错误码数量、全部触发条件数量或一次调用的报错数量。
循环可多次触发同一位置；不同分支也可能输出相同文案，再由现有异常按文案去重。

第 5 节按分类列出全部 153 个位置，保留原始诊断模板供核对。花括号中的内容表示源码动态插值，
不表示已经建立可配置 fixHint。`OBS-L行号` 仅是本次盘点定位编号，不是拟定的稳定错误码。

## 2. 分类标准与迁移目标

| 一级分类 | 二级分类 | 判断依据 | Compact 本次迁移目标 |
|---|---|---|---|
| 语法与结构契约 | 协议 | 输入行、记录结构与解析是否合法 | 沿用已有解析器，不复制实现 |
| 语法与结构契约 | 组件 | 组件自身属性、事件对象、父子结构是否合法 | `syntax/components.py` |
| 语法与结构契约 | CardSpec | CardSpec 自身字段和 schema 是否合法 | 主脚本无完整校验，保留现有完整产物校验 |
| 语法与结构契约 | 表达式 | 包装、引用及路径表示是否合法 | `syntax/expressions.py` |
| 语法与结构契约 | 素材 | 素材的表示形式及引用格式是否合法 | 不因有素材来源检查就新增独立素材语法模块 |
| 语义 | 数据绑定 | DSL 引用能否取得首帧数据，绑定源类型是否适合目标组件 | `semantic/bindings.py` |
| 语义 | 跨文件一致性 | DSL 与 CardSpec、生成上下文的结构化声明和使用是否一致 | `semantic/cross_file.py` |
| 语义 | 有效能力 | 具体事件、素材是否在本次候选范围内 | `semantic/effective.py` |
| 语义 | 展示语义 | 值形态、单位、标签与业务归属是否正确，内容和必要动作是否完整，是否重复展示 | `semantic/display.py` |
| 语义 | 布局与视觉约束 | 空间、密度、字号、骨架、对齐和染色是否符合要求 | `semantic/layout/` 下对应模块 |

目标模块均相对于方案中的 `card_validation/compact_validation/`，目前尚未创建。
每个具体检查项只有一个主要归属；输入跨多个对象，不自动意味着它属于跨文件检查。
例如字段标签是否清楚属于展示语义，而首帧值是否符合外部声明类型属于跨文件一致性。
语义分类不意味着警告或非阻断；分类、严重程度、Compact 内部调用位置保持独立。

与方案统一采用以下判断问题：数据绑定看“能否取值并用于目标组件”；跨文件看“结构化声明是否一致”；
有效能力看“是否允许使用”；展示语义看“含义与完整性、重复或遗漏”；布局看“如何摆放及空间视觉约束”。
读取外部上下文不自动归为跨文件，读取候选能力不自动归为有效能力。
需求完整性和动作使用约束作为展示语义的内部规则组，不增加一级或二级类别。

| 易混淆的检查 | 主要归属 | 判定理由 |
|---|---|---|
| Progress.value 绑定源不是数值（OBS-L1590） | 数据绑定 | 源字段类型与目标组件的数值输入不相容 |
| 首帧值与外部声明 schema 类型不一致（OBS-L4824） | 跨文件一致性 | 产物数据与结构化声明不一致 |
| 直接展示布尔值（OBS-L1564） | 展示语义 | 数据类型本身可以合法，错误在面向用户的表达方式 |
| W9/W1 遗漏要求的动作（OBS-L2009、OBS-L2609） | 展示语义／需求完整性 | 检查必要功能是否保留，不是结构化声明之间的匹配 |
| W9 可见动作数超过候选数（OBS-L1981） | 展示语义／动作使用约束 | 即使各 handler 都合法也可能超量，数量超限本身不能证明能力越界 |
| handler 不匹配本次候选（OBS-L4595） | 有效能力 | 检查具体调用及参数是否允许使用 |

## 3. 输入依赖和内部调用位置

| 类别 | 主要输入依赖 | Compact 内的调用位置与说明 |
|---|---|---|
| 协议解析 | 传入校验入口的 Compact 文本 | 入口首先调用 `parse_compact_dsl_rows`；失败包装后立即抛出；该文本可能已经过确定性修复，不等同于模型原始输出 |
| 组件契约 | 组件列表、children、属性、事件结构 | 素材检查后、融球检查前；组合组件继续委托转换器函数 |
| 表达式 | 组件属性、表达式和 PathBinding | 原绑定扫描位置；递归收集全部绑定及可见内容绑定 |
| 数据绑定 | 已收集路径、首帧数据模型、绑定字段类型及目标组件用途 | Progress 类型检查在布尔值展示检查后，首帧检查在布局检查及数据构建后 |
| 跨文件一致性 | 数据行、声明 schema、CardSpec 数据根 | 数据上下文检查内；未使用声明的警告在无错误时返回 |
| 有效能力 | 原始素材路径、本次素材候选、具体事件处理器及事件候选 | 素材来源在入口检查，事件候选在组件契约检查内；不重新进行设备能力裁决 |
| 展示语义 | 文本、字段类型及描述、相邻节点、需求与动作使用情况、候选数量、布局适用条件 | 入口文本语义检查及各布局检查的原调用点；不少检查受尺寸和布局条件约束 |
| 布局与视觉约束 | 组件树、尺寸、字号、字段样例、布局路由和素材描述 | 入口及各布局函数的原调用点；保留既有适用条件和豁免 |

当前入口大体按素材、组件契约、融球与文本语义、主数值、高度、双动作、绑定收集、
布局路由、数据上下文的顺序执行，再汇总错误；无错误时计算未使用数据声明警告。
此处只说明 Compact 内部的现有调用位置，分类展示顺序不作为新的执行顺序；不划分整条生成链路的阶段。

模板主文字豁免、主数值样式适用条件、尺寸优先级、条件不满足时的跳过和提前返回都需要保留。
解析器内已有归一化和修复，不应在本次分类时改成全量严格拒绝。

### 3.1 原始文本、校验文本与诊断位置

当前 `DesignCompactProcessor.process` 先调用 `repair_compact_dsl_binding_paths`，再校验修复后的文本。
该修复可能替换绑定路径或事件、内联本地值、删除已内联的数据行并重新序列化；解析器本身也有归一化。
因此，模型原始输出、处理器传给校验器的文本、解析后的组件记录不能共用未经核实的行号或属性值。

- 保留原始 DSL 和本次校验 DSL 的身份；诊断中的实际值来自校验时观察到的事实，并明确其文本来源。
- 面向模型的定位以本轮修复请求实际携带的 DSL 为准。若携带原始输出，应先核对组件及属性在原文中存在，
  且确实对应同一问题；不能把校验文本中的新路径或替换值冒充原文已有值。
- 只有可靠映射到修复输入时才输出源行号；否则省略行号。组件或属性也无法可靠映射时，
  省略相应精细定位并保留可证实的事实，不使用解析后序号凑出位置。
- 第 5 节的 `OBS-L` 仍只表示 Python 源码中的诊断输出位置，不是 DSL 源行号。

## 4. 重点复合函数拆分

| 当前函数或检查簇 | 分支归属 | 迁移注意事项 |
|---|---|---|
| `_collect_component_contract_errors` | 组件结构、组合组件委托、有效事件 | 保持调用顺序；委托转发不是新增规则 |
| `_collect_on_click_errors` | 前 5 个输出位置属于组件语法；候选匹配属于有效能力 | 无效结构提前返回，不能继续执行候选匹配而多报错误 |
| `_collect_data_context_errors` | 首帧路径存在性属于数据绑定；上下文 schema 前提及声明检查属于跨文件 | schema 缺失属于服务输入问题，不能要求模型修改服务上下文 |
| `_collect_progress_value_errors` | 绑定源类型与 Progress 数值输入不相容，归数据绑定 | 保留现有类型判定、修复文案及执行位置 |
| `_collect_hero_value_errors` | 大字号适用性属于布局；格式化值及单位归属属于展示语义 | 保留模板豁免；调用的子检查另行登记 |
| `_collect_adjacent_display_unit_errors` | 非数字附单位属于展示语义；基线补偿、宽度、间距属于布局 | 不能把整个函数都归入展示语义 |
| `_collect_two_by_four_detached_unit_errors` | 当前单条诊断主要约束同 Row、相邻及对齐，归布局 | 涉及单位但直接约束是空间组合；修复提示中的 padding 规则按现状保留 |
| `_collect_two_by_four_w9_content_errors` | 文本密度归布局；业务归属、重复动作、动作数量及必要动作保留归展示 | 按第 5 节逐位置拆分，不整函数搬迁；handler 合法性另归有效能力 |
| `_collect_two_by_four_w1_focus_aux_errors` | 焦点和单元结构归布局；重复事实、进度用途、事实完整性及显式动作保留归展示 | 仍依赖 W1 适用条件，共享上下文计算 |
| `_collect_two_by_four_w9_weather_triplet_errors` | 字段出现次数与标签归展示；图标、行数和字号归布局 | 保持三项天气摘要的原触发条件 |
| `_collect_2x2_countdown_group_errors` | 单位重复归展示；数字与单位分组、行数和对齐归布局 | 不在分类时调整倒计时形态 |
| `_collect_two_by_two_s4_text_errors` | 动作文案归展示；行数、压力宽度、标题和时间排版归布局 | 保留所有场景门禁 |
| `_collect_layout_route_errors` | 骨架选择与路由约束归布局；被调函数按各自分支归属 | 编排函数不是一个单一错误码 |

本表与 [v3 方案](Compact_DSL校验器重构方案_v3.md) 第 2.4 节采用相同归属：
相邻单位检查按展示语义和布局分支拆分，分离单位的同 Row、相邻及对齐要求归布局。
Progress 绑定类型归数据绑定，必要动作保留和 W9 动作数量归展示语义。
后续实施以第 5 节的具体检查项为迁移单位；分类不改变现有触发条件、修复文案或行为。

## 5. 主脚本诊断输出位置全量清单

以下原始英文诊断仅用于技术核对；中文分类和迁移说明在各节中给出。
模板原样保留现状，包括源码已有的文案细节，不在盘点时修正或背书具体建议。

| 主要分类 | 静态输出位置数 |
|---|---:|
| 语法与结构契约／组件 | 14 |
| 语法与结构契约／表达式 | 6 |
| 语义／数据绑定 | 2 |
| 语义／跨文件一致性 | 3 |
| 语义／有效能力 | 2 |
| 语义／展示语义 | 28 |
| 语义／布局与视觉约束 | 96 |
| 委托检查，按被调函数内部约束再分类 | 2 |

### 5.1 语法与结构契约／组件

迁移目标：`syntax/components.py`。

- **OBS-L4324**：`_collect_component_parent_errors`，主脚本第 4324 行。

  原始诊断：component {component.component_id}.children references {child_id} more than once.

- **OBS-L4336**：`_collect_component_parent_errors`，主脚本第 4336 行。

  原始诊断：component {child_id} has multiple parents: {existing_parent} and {component.component_id}. Each component may appear in exactly one parent children list.

- **OBS-L4351**：`_collect_container_errors`，主脚本第 4351 行。

  原始诊断：component {component.component_id}: {component.component_type}.children must be non-empty; use parent itemMargin, padding, or layout alignment instead of an empty spacer container.

- **OBS-L4527**：`_collect_action_unit_errors`，主脚本第 4527 行。

  原始诊断：{location}: ActionUnit.state must be "capsule" or "icon-round".

- **OBS-L4532**：`_collect_action_unit_errors`，主脚本第 4532 行。

  原始诊断：{location}: ActionUnit must not declare children.

- **OBS-L4534**：`_collect_action_unit_errors`，主脚本第 4534 行。

  原始诊断：{location}: ActionUnit.onClick is required.

- **OBS-L4543**：`_collect_action_unit_errors`，主脚本第 4543 行。

  原始诊断：{location}: capsule ActionUnit.icon must be a non-empty string when provided.

- **OBS-L4554**：`_collect_action_unit_errors`，主脚本第 4554 行。

  原始诊断：{location}: icon-round ActionUnit must not declare label.

- **OBS-L4564**：`_collect_required_non_empty_string`，主脚本第 4564 行。

  原始诊断：{field} must be a non-empty string.

- **OBS-L4577**：`_collect_on_click_errors`，主脚本第 4577 行。

  原始诊断：{location}: onClick must contain exactly one handler.

- **OBS-L4581**：`_collect_on_click_errors`，主脚本第 4581 行。

  原始诊断：{location}[0]: handler must be an object.

- **OBS-L4584**：`_collect_on_click_errors`，主脚本第 4584 行。

  原始诊断：{location}[0]: handler must contain only call and args.

- **OBS-L4589**：`_collect_on_click_errors`，主脚本第 4589 行。

  原始诊断：{location}[0].call: call must be a non-empty string.

- **OBS-L4592**：`_collect_on_click_errors`，主脚本第 4592 行。

  原始诊断：{location}[0].args: args must be an object.

### 5.2 语法与结构契约／表达式

迁移目标：`syntax/expressions.py`。

- **OBS-L4683**：`_collect_expression_context`，主脚本第 4683 行。

  原始诊断：{location}: expression must occupy the full string as "{{ ... }}" and contain exactly one wrapper.

- **OBS-L4692**：`_collect_expression_context`，主脚本第 4692 行。

  原始诊断：{location}: expression wraps quoted JSON Pointer "{path}"; use ${{path}} for a dynamic binding, or use a plain static value without {{ }}.

- **OBS-L4701**：`_collect_expression_context`，主脚本第 4701 行。

  原始诊断：{location}: expression has no ${/json/pointer} reference; use a plain static value instead.

- **OBS-L4708**：`_collect_expression_context`，主脚本第 4708 行。

  原始诊断：{location}: expression contains an incomplete ${...} reference.

- **OBS-L4712**：`_collect_expression_context`，主脚本第 4712 行。

  原始诊断：{location}: expression reference "{path}" must be an absolute JSON Pointer.

- **OBS-L4762**：`_collect_path_binding`，主脚本第 4762 行。

  原始诊断：{location}: PathBinding.path must be an absolute JSON Pointer.

### 5.3 语义／数据绑定

迁移目标：`semantic/bindings.py`。

- **OBS-L1590**：`_collect_progress_value_errors`，主脚本第 1590 行。

  原始诊断：component {component.component_id}: Progress.value path {value_path} has schema type {schema_type or 'unknown'}; bind a number/integer field such as 68, not formatted text such as '68%'. If only formatted text exists, remove Progress and show the complete value with Text.

- **OBS-L4776**：`_collect_data_context_errors`，主脚本第 4776 行。

  原始诊断：{path}: binding path has no matching Compact DSL data row.

### 5.4 语义／跨文件一致性

迁移目标：`semantic/cross_file.py`。

- **OBS-L4780**：`_collect_data_context_errors`，主脚本第 4780 行。

  原始诊断：TaskSpec.dataModelSchema must be an object.

- **OBS-L4800**：`_collect_undeclared_data_path_error`，主脚本第 4800 行。

  原始诊断：{path}: path is not declared by TaskSpec.dataModelSchema; remove it or use a declared field.

- **OBS-L4824**：`_collect_data_type_error`，主脚本第 4824 行。

  原始诊断：{row.path}: data row type {actual_type} does not match schema type {expected_type} declared by TaskSpec.

### 5.5 语义／有效能力

迁移目标：`semantic/effective.py`。

- **OBS-L290**：`_collect_asset_source_errors`，主脚本第 290 行。

  原始诊断：component {component.component_id}.props.{key}: asset must use an original src from TaskSpec.assetCandidates.

- **OBS-L4595**：`_collect_on_click_errors`，主脚本第 4595 行。

  原始诊断：{location}[0]: handler must exactly match a TaskSpec eventCandidate.

### 5.6 语义／展示语义

迁移目标：`semantic/display.py`。

- **OBS-L406**：`_collect_hero_value_errors`，主脚本第 406 行。

  原始诊断：component {component.component_id}: formatted value {child_id} already contains its unit; do not append Text {suffix.component_id} or a field label.

- **OBS-L425**：`_collect_hero_value_errors`，主脚本第 425 行。

  原始诊断：component {component.component_id}: Text {suffix.component_id} after the large numeric value must contain only a real unit for {value_source}. Move labels or descriptions to a separate line.

- **OBS-L461**：`_collect_two_by_two_weather_date_errors`，主脚本第 461 行。

  原始诊断：component {component.component_id}: 2x2 single-day weather must not concatenate date and weekday in one Text. Keep weekday by default, or keep date alone when the user explicitly requests the exact date.

- **OBS-L763**：`_collect_adjacent_display_unit_errors`，主脚本第 763 行。

  原始诊断：component {component.component_id}: large primary Text {value.component_id} binds non-numeric field {value_path} and must occupy its own row; do not append {suffix.component_id} as a unit or label.

- **OBS-L836**：`_collect_adjacent_display_unit_errors`，主脚本第 836 行。

  原始诊断：component {component.component_id}: display unit {unit} cannot follow non-numeric binding {value_path}. Remove the unit or bind a number/integer value.

- **OBS-L1564**：`_collect_raw_boolean_text_errors`，主脚本第 1564 行。

  原始诊断：component {component.component_id}: boolean field(s) {', '.join(boolean_paths)} must be mapped to user-facing Text with a conditional expression; do not display raw true/false.

- **OBS-L1851**：`_collect_two_by_four_w9_content_errors`，主脚本第 1851 行。

  原始诊断：2x4 W9 backboard {zone.component_id} mixes data roots {sorted(content_roots)}. Each backboard must display exactly one business object; move every field to its owning backboard.

- **OBS-L1875**：`_collect_two_by_four_w9_content_errors`，主脚本第 1875 行。

  原始诊断：2x4 W9 action {action.component_id} binds data root(s) {sorted(action_roots)} but is placed in backboard {zone.component_id}, which displays {sorted(content_roots)}. Move the action to its owning business backboard.

- **OBS-L1899**：`_collect_two_by_four_w9_content_errors`，主脚本第 1899 行。

  原始诊断：2x4 W9 countdown backboard {zone.component_id} must contain exactly one unit Text \`天\`, placed below the numeric hero. Do not generate both an inline unit and another unit below it.

- **OBS-L1945**：`_collect_two_by_four_w9_content_errors`，主脚本第 1945 行。

  原始诊断：2x4 W9 compact weather day {component_id} must not show both full date and weekday in the same 114vp row. Keep the weekday and remove the redundant date.

- **OBS-L1976**：`_collect_two_by_four_w9_content_errors`，主脚本第 1976 行。

  原始诊断：2x4 W9 must not duplicate the same action across both backboards. Keep each requested candidate action exactly once.

- **OBS-L1981**：`_collect_two_by_four_w9_content_errors`，主脚本第 1981 行。

  原始诊断：2x4 W9 contains {total_action_count} visible actions but TaskSpec provides only {candidate_count} candidates. Do not copy an action to fill the other backboard.

- **OBS-L2009**：`_collect_two_by_four_w9_content_errors`，主脚本第 2009 行。

  原始诊断：2x4 W9 must keep explicitly requested actions inside their owning backboards ({total_action_count}/{expected_action_count}). Remove lower-priority text before dropping an action.

- **OBS-L2069**：`_collect_two_by_two_s4_text_errors`，主脚本第 2069 行。

  原始诊断：2x2 S4 clickable backboard {zone.component_id} must not show action hint Text {text_component.component_id}; bind the action only to the backboard.

- **OBS-L2469**：`_collect_two_by_four_w1_focus_aux_errors`，主脚本第 2469 行。

  原始诊断：2x4 W1-focus-aux must not repeat the same visible fact in the left focus and a right auxiliary cell. Reassign each requested field to one region only; duplicated paths: {duplicate_text_paths}.

- **OBS-L2526**：`_collect_two_by_four_w1_focus_aux_errors`，主脚本第 2526 行。

  原始诊断：2x4 W1-focus-aux must not add Progress unless the user explicitly requests a progress visualization. Use the left focus for the primary value and its necessary status instead.

- **OBS-L2609**：`_collect_two_by_four_w1_focus_aux_errors`，主脚本第 2609 行。

  原始诊断：2x4 W1-focus-aux must reserve right auxiliary cells for explicit actions ({actual_action_cells}/{expected_action_cells}). Drop or merge lower-priority facts instead of omitting the requested action.

- **OBS-L2692**：`_collect_two_by_four_w1_focus_aux_errors`，主脚本第 2692 行。

  原始诊断：2x4 W1-focus-aux cell {cell.component_id} must place each of its two dynamic facts in a separate complete Text line. Do not put both labels on one line and both values on the other line.

- **OBS-L2722**：`_collect_two_by_four_w1_focus_aux_errors`，主脚本第 2722 行。

  原始诊断：2x4 W1-focus-aux cell {cell.component_id} mixes data roots {sorted(cell_roots)}. Each auxiliary cell must belong to one business object.

- **OBS-L2766**：`_collect_two_by_four_w9_weather_triplet_errors`，主脚本第 2766 行。

  原始诊断：2x4 W9 weather backboard {zone.component_id} must display {field_name} exactly once in its compact three-row summary.

- **OBS-L2787**：`_collect_two_by_four_w9_weather_triplet_errors`，主脚本第 2787 行。

  原始诊断：2x4 W9 weather Text {component.component_id} must include the short label {label} so the value remains identifiable and is not clipped.

- **OBS-L3800**：`_collect_2x2_countdown_group_errors`，主脚本第 3800 行。

  原始诊断：2x2 countdown must display the day unit exactly once; do not place '天' beside the value and repeat it again in a second metadata row.

- **OBS-L4116**：`_collect_semantic_text_errors`，主脚本第 4116 行。

  原始诊断：component {component.component_id}: time/date range ends with a dangling separator. Bind both start and end values, or remove the separator and display the available value only.

- **OBS-L4139**：`_collect_semantic_text_errors`，主脚本第 4139 行。

  原始诊断：component {component.component_id}: calendar eventCount must not be shown as a standalone number or unit. Combine it with its time scope and schedule meaning, for example 未来7天 2项安排, inside the calendar region.

- **OBS-L4153**：`_collect_semantic_text_errors`，主脚本第 4153 行。

  原始诊断：component {component.component_id}: reminder value must keep its minute semantics, such as 提前 15 分钟; do not display a bare numeric reminder value.

- **OBS-L4163**：`_collect_semantic_text_errors`，主脚本第 4163 行。

  原始诊断：component {component.component_id}: windLevel must include the metric label 风力, for example 风力 2级; do not show a bare 2级.

- **OBS-L4207**：`_collect_unbound_action_hint_errors`，主脚本第 4207 行。

  原始诊断：component {component.component_id}: action-like Text {text} has no clickable ancestor. Bind the matching event to its action slot or remove the action wording.

- **OBS-L4285**：`_collect_ambiguous_metric_text_errors`，主脚本第 4285 行。

  原始诊断：component {component.component_id}: value {path} has ambiguous meaning ({detail}); add a nearby metric label such as 感冒指数、紫外线指数 or 睡眠得分 instead of showing the value alone.

### 5.7 语义／布局与视觉约束

迁移目标：`semantic/layout/`。

- **OBS-L332**：`_collect_asset_color_errors`，主脚本第 332 行。

  原始诊断：component {component.component_id}: tintable SVG {source} must set fillColor explicitly; omitting it renders the asset's default black.

- **OBS-L391**：`_collect_hero_value_errors`，主脚本第 391 行。

  原始诊断：component {component.component_id}: fontSize {_format_vp(font_size)} requires a pure number/integer or a supported primary value. A directly bound measurement with a declared unit may use 20/24fp in a full-width area or 2x4 large panel when its text budget fits; ordinary names, dates, times, and statuses remain at most 18fp.

- **OBS-L825**：`_collect_adjacent_display_unit_errors`，主脚本第 825 行。

  原始诊断：component {component.component_id}: numeric value and unit {suffix.component_id} must use Row alignItems "bottom"; the unit must use capped visual bottom padding for its font-size difference and must not use the numeric value's fixed height; both Text nodes must use intrinsic width and their Row itemMargin must not exceed 4.

- **OBS-L1130**：`_collect_mixed_font_row_alignment_errors`，主脚本第 1130 行。

  原始诊断：component {component.component_id}: a Row containing mixed Text font sizes must use alignItems bottom so every visible text bottom aligns.

- **OBS-L1154**：`_collect_mixed_font_row_alignment_errors`，主脚本第 1154 行。

  原始诊断：component {child.component_id}: smaller Text in mixed-size Row {component.component_id} must use padding.bottom {expected_padding} to compensate the visible glyph baseline after Row alignItems "bottom" aligns the Text boxes.

- **OBS-L1203**：`_collect_two_by_four_small_backboard_errors`，主脚本第 1203 行。

  原始诊断：2x4 small backboard {backboard.component_id} may contain at most two Text nodes. Keep one primary line and one supporting line instead of clipping a third line.

- **OBS-L1214**：`_collect_two_by_four_small_backboard_errors`，主脚本第 1214 行。

  原始诊断：2x4 small backboard {backboard.component_id} with a visual must use Row so its text stays on the left and the visual stays on the right.

- **OBS-L1221**：`_collect_two_by_four_small_backboard_errors`，主脚本第 1221 行。

  原始诊断：2x4 small backboard {backboard.component_id} without a visual must use Column; do not place two Text nodes side by side where the second line can be clipped.

- **OBS-L1227**：`_collect_two_by_four_small_backboard_errors`，主脚本第 1227 行。

  原始诊断：2x4 small backboard {backboard.component_id} without a visual must vertically center its one or two Text lines.

- **OBS-L1320**：`_collect_two_by_four_action_backboard_errors`，主脚本第 1320 行。

  原始诊断：2x4 large backboard {backboard.component_id} must place its action as the final direct child.

- **OBS-L1328**：`_collect_two_by_four_action_backboard_errors`，主脚本第 1328 行。

  原始诊断：2x4 large backboard {backboard.component_id} action must be {_TWO_BY_FOUR_MULTI_INNER_WIDTH}x36.

- **OBS-L1337**：`_collect_two_by_four_action_backboard_errors`，主脚本第 1337 行。

  原始诊断：2x4 large backboard {backboard.component_id} with a Button must have exactly [content, Button] as direct children.

- **OBS-L1344**：`_collect_two_by_four_action_backboard_errors`，主脚本第 1344 行。

  原始诊断：2x4 large backboard {backboard.component_id} content must be a Column.

- **OBS-L1349**：`_collect_two_by_four_action_backboard_errors`，主脚本第 1349 行。

  原始诊断：2x4 large backboard {backboard.component_id} content must use layoutWeight 1 so the Button stays at the bottom.

- **OBS-L1354**：`_collect_two_by_four_action_backboard_errors`，主脚本第 1354 行。

  原始诊断：2x4 large backboard {backboard.component_id} with a Button may contain at most four Text nodes across no more than three visual rows. Merge or remove lower-priority fields.

- **OBS-L1374**：`_collect_two_by_four_action_row_errors`，主脚本第 1374 行。

  原始诊断：2x4 graphical action Row {action.component_id} must use itemMargin 8, at least 8vp left/right padding, justifyContent center, and alignItems center so its icon and label stay centered.

- **OBS-L1423**：`_collect_two_by_two_narrow_graphical_action_errors`，主脚本第 1423 行。

  原始诊断：2x2 narrow graphical action Row {action.component_id} must be centered by parent Column {parent.component_id}; set alignItems to center when the action is narrower than the parent's content width.

- **OBS-L1454**：`_collect_two_by_four_full_width_action_errors`，主脚本第 1454 行。

  原始诊断：2x4 full-width action {action.component_id} must be a direct child of the matchParent foreground Column; do not nest it inside a fixed-height main/body container where content can overlap.

- **OBS-L1464**：`_collect_two_by_four_full_width_action_errors`，主脚本第 1464 行。

  原始诊断：2x4 full-width action {action.component_id} must be the final direct child of foreground Column {parent.component_id}.

- **OBS-L1473**：`_collect_two_by_four_full_width_action_errors`，主脚本第 1473 行。

  原始诊断：2x4 content immediately above full-width action {action.component_id} must use layoutWeight 1 so the 276x36 action remains fixed at the bottom without overlapping content.

- **OBS-L1729**：`_collect_two_by_four_w9_density_errors`，主脚本第 1729 行。

  原始诊断：2x4 W9 backboard {zone.component_id} displays multiple peer quantitative fields and must keep all of them as ordinary complete text lines with the same typography; do not promote one field to a 30fp/38fp hero.

- **OBS-L1736**：`_collect_two_by_four_w9_density_errors`，主脚本第 1736 行。

  原始诊断：2x4 W9 backboard {zone.component_id} contains multiple 30fp/38fp values. Keep peer metrics as ordinary complete text lines instead of manufacturing multiple hero values.

- **OBS-L1742**：`_collect_two_by_four_w9_density_errors`，主脚本第 1742 行。

  原始诊断：2x4 W9 backboard {zone.component_id} with a 30fp/38fp numeric hero may contain only the value/unit line and one 12fp/400 auxiliary line after its business title. Merge auxiliary fields with ' | '.

- **OBS-L1814**：`_collect_two_by_four_w9_content_errors`，主脚本第 1814 行。

  原始诊断：2x4 W9 backboard {zone.component_id} may contain at most four content Text rows. Merge same-object fields instead of stacking additional rows.

- **OBS-L1842**：`_collect_two_by_four_w9_content_errors`，主脚本第 1842 行。

  原始诊断：2x4 W9 text {component.component_id} joins {len(paths)} dynamic facts in one narrow row. Keep at most two short facts per Text; split them into separate 12fp rows or remove the lowest-priority field. A compact multi-day weather row is the only exception.

- **OBS-L1894**：`_collect_two_by_four_w9_content_errors`，主脚本第 1894 行。

  原始诊断：2x4 W9 countdown {component.component_id} must use a 30fp/38fp, 700-weight numeric hero in its own backboard.

- **OBS-L1919**：`_collect_two_by_four_w9_content_errors`，主脚本第 1919 行。

  原始诊断：2x4 W9 countdown value {countdown_text.component_id} must not share a Row with unit \`天\`; keep the single unit below the numeric hero.

- **OBS-L1955**：`_collect_two_by_four_w9_content_errors`，主脚本第 1955 行。

  原始诊断：2x4 W9 compact weather day {component_id} must use 12fp/400 auxiliary text.

- **OBS-L1960**：`_collect_two_by_four_w9_content_errors`，主脚本第 1960 行。

  原始诊断：2x4 W9 weather day {day_index} in backboard {zone.component_id} is split across multiple Text rows {sorted(component_ids)}. Merge each day into one 12fp/400 row.

- **OBS-L1969**：`_collect_two_by_four_w9_content_errors`，主脚本第 1969 行。

  原始诊断：2x4 W9 multi-day weather backboard {zone.component_id} must not insert Divider components between compact day rows.

- **OBS-L2032**：`_collect_two_by_two_s4_text_errors`，主脚本第 2032 行。

  原始诊断：2x2 S4 backboard {zone.component_id} contains {len(text_components)} Text rows; keep at most two single-line Text components.

- **OBS-L2039**：`_collect_two_by_two_s4_text_errors`，主脚本第 2039 行。

  原始诊断：2x2 S4 Text {text_component.component_id} must use maxLines 1; a backboard must never render a third line.

- **OBS-L2056**：`_collect_two_by_two_s4_text_errors`，主脚本第 2056 行。

  原始诊断：2x2 S4 static Text {text_component.component_id} exceeds its {text_width}vp single-line width; shorten the wording while keeping its meaning. Do not wrap it, add a third line, or move the visual.

- **OBS-L2087**：`_collect_two_by_two_s4_text_errors`，主脚本第 2087 行。

  原始诊断：2x2 S4 meeting time {text_component.component_id} must use its own 12fp/400 auxiliary row; do not combine it with the 14fp/700 meeting title.

- **OBS-L2099**：`_collect_two_by_two_s4_text_errors`，主脚本第 2099 行。

  原始诊断：2x2 S4 calendar backboard {zone.component_id} must keep a separate 14fp/700 meeting title above its 12fp/400 time row.

- **OBS-L2130**：`_collect_two_by_two_s4_vertical_alignment_errors`，主脚本第 2130 行。

  原始诊断：2x2 S4 backboard {zone.component_id} without a visual must vertically center its one or two text lines with justifyContent center; do not reserve an empty third line.

- **OBS-L2147**：`_collect_two_by_two_s4_vertical_alignment_errors`，主脚本第 2147 行。

  原始诊断：2x2 S4 text group {text_group.component_id} must use justifyContent center so its one or two lines remain vertically centered beside the visual.

- **OBS-L2191**：`_collect_two_by_two_ring_group_alignment_errors`，主脚本第 2191 行。

  原始诊断：2x2 compact ring group {content_group.component_id} must use alignItems "center" so the ring and its single status line remain horizontally centered.

- **OBS-L2235**：`_collect_two_by_two_s4_palette_errors`，主脚本第 2235 行。

  原始诊断：2x2 S4 must use one card palette across both business zones. Text, tintable Image, Progress, and Divider colors must share one RGB and may differ only in alpha. Found mixed palette colors: {details}.

- **OBS-L2326**：`_collect_two_by_four_aux_icon_errors`，主脚本第 2326 行。

  原始诊断：2x4 130x59 auxiliary backboard {cell.component_id} with an icon must contain exactly one one-line Text or one 1-2 line text Column plus one Image. The converter normalizes the cell to left-aligned text and a 20x20vp Image on the right.

- **OBS-L2392**：`_collect_two_by_four_w1_focus_alignment_errors`，主脚本第 2392 行。

  原始诊断：2x4 W1-focus-aux left focus may contain at most four Text nodes. Use at most three visual layers for value-led content, merge a closely related pair, or move one necessary fact to an auxiliary cell instead of filling the left zone with a dense list.

- **OBS-L2401**：`_collect_two_by_four_w1_focus_alignment_errors`，主脚本第 2401 行。

  原始诊断：2x4 W1-focus-aux compact left content must use justifyContent center so its information group is vertically centered instead of being pinned to the top.

- **OBS-L2408**：`_collect_two_by_four_w1_focus_alignment_errors`，主脚本第 2408 行。

  原始诊断：2x4 W1-focus-aux sparse or value-led left content must use alignItems center. Event lists and dense summaries may remain left-aligned, but their full group must still be vertically centered.

- **OBS-L2430**：`_collect_two_by_four_w1_focus_alignment_errors`，主脚本第 2430 行。

  原始诊断：2x4 W1-focus-aux left content group {child.component_id} must use justifyContent center so its compact text group is not pinned to the top or left.

- **OBS-L2437**：`_collect_two_by_four_w1_focus_alignment_errors`，主脚本第 2437 行。

  原始诊断：2x4 W1-focus-aux left content Column {child.component_id} must use alignItems center.

- **OBS-L2491**：`_collect_two_by_four_w1_focus_aux_errors`，主脚本第 2491 行。

  原始诊断：2x4 W1-focus-aux left focus Image {component.component_id} is decorative and must be removed. Only an Image centered inside a Stack that also contains a valid ring Progress is allowed there.

- **OBS-L2504**：`_collect_two_by_four_w1_focus_aux_errors`，主脚本第 2504 行。

  原始诊断：2x4 W1-focus-aux may contain only one 20fp-or-larger primary focus in the left zone. Keep peer metrics as ordinary auxiliary content instead of manufacturing a second hero.

- **OBS-L2510**：`_collect_two_by_four_w1_focus_aux_errors`，主脚本第 2510 行。

  原始诊断：2x4 W1-focus-aux actions must occupy a right auxiliary cell; do not bind actions inside the left focus zone.

- **OBS-L2541**：`_collect_two_by_four_w1_focus_aux_errors`，主脚本第 2541 行。

  原始诊断：2x4 W1-focus-aux Progress must be paired with a visible primary value Text of at least 18fp in the left focus zone. Do not output a standalone progress line or ring without its readout.

- **OBS-L2571**：`_collect_two_by_four_w1_focus_aux_errors`，主脚本第 2571 行。

  原始诊断：2x4 phone-and-earphone W1 focus must use a compact ring Progress for numeric phone battery percentage; do not use a horizontal linear bar. If only formatted battery text exists, remove Progress and display that complete text instead.

- **OBS-L2641**：`_collect_two_by_four_w1_focus_aux_errors`，主脚本第 2641 行。

  原始诊断：2x4 W1-focus-aux cell {cell.component_id} must keep its text group left-aligned. Use Row justifyContent start or Column alignItems start, and Text textAlign start; only vertical centering is allowed.

- **OBS-L2651**：`_collect_two_by_four_w1_focus_aux_errors`，主脚本第 2651 行。

  原始诊断：2x4 W1-focus-aux cell {cell.component_id} may contain at most two Text nodes. Merge its auxiliary information.

- **OBS-L2673**：`_collect_two_by_four_w1_focus_aux_errors`，主脚本第 2673 行。

  原始诊断：2x4 W1-focus-aux cell {cell.component_id} references {len(visible_paths)} dynamic facts. Keep at most two facts that fit as two short lines; drop lower-priority fields.

- **OBS-L2679**：`_collect_two_by_four_w1_focus_aux_errors`，主脚本第 2679 行。

  原始诊断：2x4 W1-focus-aux cell {cell.component_id} displays two dynamic facts in one Text. Use two single-line Text nodes, one fact per line, instead of joining them with '|'.

- **OBS-L2702**：`_collect_two_by_four_w1_focus_aux_errors`，主脚本第 2702 行。

  原始诊断：2x4 W1-focus-aux cell {cell.component_id} must bind onClick to the auxiliary backboard itself; do not nest a Button or ActionUnit inside it.

- **OBS-L2757**：`_collect_two_by_four_w9_weather_triplet_errors`，主脚本第 2757 行。

  原始诊断：2x4 W9 weather backboard {zone.component_id} with temperature, rain and air-quality rows must omit decorative icons so all three facts fit in the 114vp content width.

- **OBS-L2774**：`_collect_two_by_four_w9_weather_triplet_errors`，主脚本第 2774 行。

  原始诊断：2x4 W9 weather Text {component.component_id} must contain one dynamic fact only; keep temperature, rain and air quality on three separate rows.

- **OBS-L2781**：`_collect_two_by_four_w9_weather_triplet_errors`，主脚本第 2781 行。

  原始诊断：2x4 W9 weather Text {component.component_id} must use 12fp/400 in the compact three-row summary.

- **OBS-L3131**：`_collect_two_by_two_centered_hero_errors`，主脚本第 3131 行。

  原始诊断：2x2 sparse single-value Hero with one bottom action must use a 126vp layoutWeight content_area centered on both axes, containing one centered 106x58vp hero_box and a centered 106vp value_row.

- **OBS-L3139**：`_collect_two_by_two_centered_hero_errors`，主脚本第 3139 行。

  原始诊断：2x2 centered single-value Hero must use one approved value font tier: 38fp, 30fp, 24fp, or 20fp.

- **OBS-L3151**：`_collect_two_by_two_centered_hero_errors`，主脚本第 3151 行。

  原始诊断：2x2 centered single-value Hero unit must declare a fontSize.

- **OBS-L3156**：`_collect_two_by_two_centered_hero_errors`，主脚本第 3156 行。

  原始诊断：2x2 centered single-value Hero must downgrade value and unit together using 38/16fp, 30/14fp, 24/12fp, or 20/12fp limits.

- **OBS-L3178**：`_collect_two_by_two_centered_hero_errors`，主脚本第 3178 行。

  原始诊断：2x2 centered single-value Hero exceeds the 106vp width pressure budget; downgrade value/unit together through 38/16fp -> 30/14fp -> 24/12fp -> 20/12fp until it fits.

- **OBS-L3195**：`_collect_two_by_two_centered_hero_errors`，主脚本第 3195 行。

  原始诊断：2x2 centered single-value Hero exceeds the 58vp height pressure budget; downgrade value/unit together instead of clipping it.

- **OBS-L3266**：`_collect_two_by_two_content_density_errors`，主脚本第 3266 行。

  原始诊断：2x2 150vp single-business content displays multiple peer quantitative fields and must keep all of them as ordinary complete text lines with the same typography; do not promote one field to a 30fp/38fp hero.

- **OBS-L3273**：`_collect_two_by_two_content_density_errors`，主脚本第 3273 行。

  原始诊断：2x2 150vp single-business content contains multiple 30fp/38fp values. Treat peer metrics as ordinary complete text lines instead of manufacturing multiple hero values.

- **OBS-L3279**：`_collect_two_by_two_content_density_errors`，主脚本第 3279 行。

  原始诊断：2x2 150vp single-business content with a 30fp/38fp numeric hero may contain only the value/unit line and one 12fp/400 auxiliary line. Merge auxiliary fields into that line with ' | '.

- **OBS-L3296**：`_collect_two_by_two_content_density_errors`，主脚本第 3296 行。

  原始诊断：2x2 150vp single-business pure-text content with an action may contain at most one prominent line and two 12fp/400 auxiliary lines. Merge related auxiliary fields with ' | ' and remove lower-priority update text.

- **OBS-L3310**：`_collect_two_by_two_content_density_errors`，主脚本第 3310 行。

  原始诊断：2x2 150vp single-business content with an action and three information lines must keep its prominent text at 18fp or smaller so the 36vp action remains unobstructed.

- **OBS-L3378**：`_collect_two_by_four_detached_unit_errors`，主脚本第 3378 行。

  原始诊断：2x4 numeric value {component.component_id} and unit {detached_unit.component_id} must be adjacent Text children of the same Row. Use Row alignItems bottom without bottom padding on the smaller Text; do not place a non-countdown unit on the next line.

- **OBS-L3419**：`_collect_two_by_four_weather_calendar_alignment_errors`，主脚本第 3419 行。

  原始诊断：2x4 weather-and-calendar cards must combine current temperature and condition in one single-line Text, such as 29° · 多云. Do not split them into separate Text nodes with different font metrics because their visible baselines will not align.

- **OBS-L3455**：`_collect_two_by_four_countdown_backboard_errors`，主脚本第 3455 行。

  原始诊断：2x4 countdown backboard {backboard.component_id} without an action must directly contain exactly three Text children: target title, numeric countdown, and unit \`天\`. Do not nest a content/readout Column or add a fourth auxiliary line.

- **OBS-L3469**：`_collect_two_by_four_countdown_backboard_errors`，主脚本第 3469 行。

  原始诊断：2x4 countdown backboard {backboard.component_id} must order its three Text children as target title, countdownDays value, and unit \`天\`.

- **OBS-L3479**：`_collect_two_by_four_countdown_backboard_errors`，主脚本第 3479 行。

  原始诊断：2x4 countdown backboard {backboard.component_id} must use justifyContent "spaceBetween" and alignItems "center" so the title, number, and unit have balanced vertical spacing.

- **OBS-L3488**：`_collect_two_by_four_countdown_backboard_errors`，主脚本第 3488 行。

  原始诊断：2x4 countdown Text {child.component_id} must use width 114 and textAlign center inside the balanced countdown backboard.

- **OBS-L3595**：`_collect_layout_route_errors`，主脚本第 3595 行。

  原始诊断：2x4 cards must not stack two or more full-width 276x48-59 content backboards vertically. Select the matching W skeleton; two semantic data blocks must use W9 left/right backboards.

- **OBS-L3614**：`_collect_layout_route_errors`，主脚本第 3614 行。

  原始诊断：2x4 large backboard {component.component_id} may contain at most one action control. Do not stack two buttons inside a 138x134 backboard; remove duplicate or lower-priority actions.

- **OBS-L3626**：`_collect_layout_route_errors`，主脚本第 3626 行。

  原始诊断：2x2 S4 requires exactly two independent display objects. Fields from one object must remain in one single-business layout instead of being split across two 134x63 backboards.

- **OBS-L3634**：`_collect_layout_route_errors`，主脚本第 3634 行。

  原始诊断：2x2 card has one data root and must use a full-width single-business layout; do not generate an isolated 134x63 S4 backboard.

- **OBS-L3660**：`_collect_layout_route_errors`，主脚本第 3660 行。

  原始诊断：2x4 card has one dominant focus and at most two auxiliary slots and must use W1-focus-aux: root Row padding 12/itemMargin 10, a left 136x126 focus zone without a backboard, and a right 130x126 Column containing two 130x59 backboards separated by itemMargin 8.

- **OBS-L3674**：`_collect_layout_route_errors`，主脚本第 3674 行。

  原始诊断：2x4 card displays at least four semantic metric groups and must use W8: root must be a Column with padding 8 and two direct 284x63 Rows separated by itemMargin 8; each Row must contain two 138x63 backboards separated by itemMargin 8. Merge naturally related weather facts before dropping the lowest-priority group.

- **OBS-L3685**：`_collect_layout_route_errors`，主脚本第 3685 行。

  原始诊断：2x4 card displays three semantic data blocks and must use W10: root must be a Row with padding 8 and itemMargin 8, containing one 138x134 large backboard and one 138x134 Column with two 138x63 backboards separated by itemMargin 8.

- **OBS-L3698**：`_collect_layout_route_errors`，主脚本第 3698 行。

  原始诊断：2x2 S4 requires exactly two independent display objects. Fields from one object must remain in one single-business layout instead of being split across two 134x63 backboards.

- **OBS-L3743**：`_collect_layout_route_errors`，主脚本第 3743 行。

  原始诊断：2x2 S4 countdown must be displayed as ordinary 14fp/700 primary text inside its backboard; do not reuse the V01 30fp/38fp hero or standalone countdown group.

- **OBS-L3751**：`_collect_layout_route_errors`，主脚本第 3751 行。

  原始诊断：2x2 card displays two data roots ({roots}) and must use S4: root must be a Column with padding 8 and exactly two direct 134x63 Row/Column backboards with itemMargin 8. Countdown remains ordinary 14fp/700 primary text inside its backboard.

- **OBS-L3769**：`_collect_layout_route_errors`，主脚本第 3769 行。

  原始诊断：2x4 card displays two semantic data blocks ({roots}) and must use W9: root must be a Row with padding 8 and exactly two direct 138x134 Column backboards with itemMargin 8. Do not use a shared title, a shared action area, or stacked full-width business rows.

- **OBS-L3834**：`_collect_2x2_countdown_group_errors`，主脚本第 3834 行。

  原始诊断：2x2 countdown with an action or additional visible data must place the countdown number in a left-aligned value_row; do not keep the V01 centered vertical number/unit layout.

- **OBS-L3842**：`_collect_2x2_countdown_group_errors`，主脚本第 3842 行。

  原始诊断：2x2 expanded countdown value_row must belong to a full-width value_group Column.

- **OBS-L3850**：`_collect_2x2_countdown_group_errors`，主脚本第 3850 行。

  原始诊断：2x2 countdown with an action or additional visible data must left-align value_group and value_row; centered countdown values are reserved for the display-only V01 layout.

- **OBS-L3856**：`_collect_2x2_countdown_group_errors`，主脚本第 3856 行。

  原始诊断：2x2 expanded countdown value_row must be the first child of value_group.

- **OBS-L3860**：`_collect_2x2_countdown_group_errors`，主脚本第 3860 行。

  原始诊断：2x2 expanded countdown value_group may contain only the value_row and one optional auxiliary-data row.

- **OBS-L3869**：`_collect_2x2_countdown_group_errors`，主脚本第 3869 行。

  原始诊断：2x2 V01 countdown value_group must contain exactly two visual rows: the countdown number and a second-line unit/meta row. Do not add a third aux_text or repeat the target name.

- **OBS-L3879**：`_collect_2x2_countdown_group_errors`，主脚本第 3879 行。

  原始诊断：2x2 V01 countdown meta_row may contain only the unit and the optional time on the same line.

- **OBS-L3909**：`_collect_two_by_four_w9_sparse_layout_errors`，主脚本第 3909 行。

  原始诊断：2x4 W9 sparse backboard {zone.component_id}{suffix} must use a direct content Column with layoutWeight 1 and justifyContent center so the primary content group remains vertically centered.

- **OBS-L4030**：`_collect_fusion_composition_errors`，主脚本第 4030 行。

  原始诊断：2x2 fusion-ball cards must not combine a title/auxiliary icon, a ring Progress, multiple status texts, and a button. Keep one primary visual focus: remove the icon or ring, merge status text, or fall back to a non-fusion layout.

- **OBS-L4383**：`_collect_height_budget_errors`，主脚本第 4383 行。

  原始诊断：component {component.component_id}: vertical layout requires at least {_format_vp(required_height)}vp within {_format_vp(available_height)}vp; it overflows by {_format_vp(overflow)}vp. Reduce child heights, margins, or gaps instead of relying on clipping, flex shrink, or distributed alignment.

### 5.8 委托检查，按被调函数内部约束再分类

迁移目标：`现有转换器辅助函数`。

- **OBS-L4302**：`_collect_component_contract_errors`，主脚本第 4302 行。

  原始诊断：str(exc)

- **OBS-L4306**：`_collect_component_contract_errors`，主脚本第 4306 行。

  原始诊断：str(exc)

## 6. 警告、异常包装与委托检查

### 6.1 主脚本之外的输出路径

| 路径 | 分类 | 行为与迁移说明 |
|---|---|---|
| `_unused_data_capability_warnings`（4905 行） | 语义／跨文件一致性 | CardSpec 声明的数据根没有被任何绑定使用时返回 warning；事件绑定也在已使用路径中，不只看可见内容 |
| `validate_compact_dsl` 的解析异常处理（200–202 行） | 语法／协议错误的包装 | 将解析器异常转换为现有校验异常；不另发一条独立重复错误 |
| `CompactDslValidationError`（183 行） | 诊断汇总，不是校验规则 | 保留错误出现顺序，按完整字符串去重，生成异常文本 |
| `build_compact_data_model` | 数据模型构建及底层路径契约 | 保留现有异常行为；它在解析异常 try 块之外，不能假定所有异常均已包装 |

### 6.2 2×2 双胶囊动作

来源：`widget_service/cloud/services/card_validation/compact_dual_action_validator.py`。
`collect_dual_action_errors` 仅在 2×2 且恰好存在两个 capsule ActionUnit 时执行。
`_structure_error` 返回首个失败原因，外层只有一个错误追加位置；不能统计为每次返回全部子规则。

下列检查整体属于语义／布局与视觉约束，因为它们限定特定双动作骨架，不是通用组件合法性：

1. 存在 root，且为恰好两个直接分区的 Column。
2. root padding 为 12，间距为 8。
3. 信息区和动作区均存在，分别为 126×40、126×78 的 Column。
4. 两个胶囊都是动作区直接子项，动作间距为 6。
5. 信息区只有一到两个直接 Text，不允许标题组件、图标或嵌套大数字区。
6. 首行字号 12–14fp，次行 12fp；显式高度至少为字号的 1.4 倍，且 maxLines 为 1。

初期保留该模块，通过布局编排接入；保留首错返回、适用条件和事件不丢失的修复要求。

### 6.3 组合组件委托

主脚本 `_collect_component_contract_errors` 调用转换器中的：

- `validate_card_header_layout`：组合组件的尺寸、数量、父容器、首项位置、样式约束、图标颜色和展开 ID 等检查。
- `validate_timeline_unit_layout`：时间线的尺寸、数据用途及布局约束检查。

这些函数同时包含组件契约和特定布局限制，本次保留现有委托调用与异常转发；
本清单只统计主脚本的两个异常转发位置，不宣称已经逐分支盘点整个转换器。
继续复用现有实现，不拆分转换器内部规则，也不把标准组件展开和转换规则复制进 Compact 分类目录。

### 6.4 外部依赖与不变边界

- 协议语法：由现有解析器和转换器提供；主脚本没有另一套完整解析器。
- CardSpec 语法：主脚本读取尺寸和数据绑定等信息，不等于完整校验 CardSpec。
- 素材语法：主脚本的来源集合与 SVG 染色检查分别属于有效能力和视觉约束，不等于覆盖所有素材格式。
- 完整有效能力校验：本次候选检查不能替代标准产物中基于有效能力及注册信息的最终检查。

解析器、转换器及完整产物校验沿用现状，不纳入本次 Compact 模块拆分。
调用方仅做上下文传递、旧错误兼容和修复诊断传递所必需的适配；不重构整条生成链路，
也不将本文的分类标识替换现有调用方的 stage 或 category。

## 7. 公共辅助逻辑的归属

| 辅助逻辑 | 归属建议 | 是否新增报错 |
|---|---|---|
| 组件索引、父子关系、后代遍历 | 公共上下文或布局共享辅助 | 否 |
| 路径提取、JSON Pointer 解析 | 表达式与绑定共享的基础模块 | 否；保留调用位置已有的错误 |
| schema 路径解析、类型判断 | 数据绑定、跨文件与展示共享的 schema 辅助 | 否 |
| 高度、padding、margin、文字压力计算 | 布局 geometry/typography | 否 |
| 布局识别、业务块数、焦点适用条件 | 布局 routing | 否；不能因移动函数改变门禁 |
| 素材描述和事件候选提取 | 有效能力上下文 | 否 |
| 错误去重与异常文本格式化 | diagnostics | 否 |

上述函数不是独立规则，不能因为被多个类别使用就多次执行并重复报错。
混合规则拆分时保留共享计算和原输出顺序；尤其不要将“先收集所有语法，再执行所有语义”直接作为等价迁移。

### 7.1 公共上下文的兼容约束

公共上下文先保存有序的原始组件记录和父子引用，不能用单个父节点字典覆盖全部调用点的行为。
重复组件 ID、重复 children 引用和多个父节点等非法输入也属于等价迁移的回归范围。

| 当前查询方式 | 已有使用示例 | 迁移要求 |
|---|---|---|
| 首次父节点 | `_collect_component_parent_errors` 保留首次父节点，与后续父节点比较 | 提供 first 兼容视图；重复引用检查仍按原 children 顺序执行 |
| 最后父节点 | `_collect_two_by_four_w9_content_errors` 等循环赋值构建父节点字典 | 提供 last 兼容视图，不悄然改成首次父节点 |
| 全部父节点 | `_is_large_2x4_panel`、`_has_parent_column` 构建父节点列表后遍历 | 保留 all 关系、顺序及原有栈式遍历和去重方式 |

`_collect_binding_context` 与 `_collect_expression_context` 当前既收集绑定路径，也向传入的错误列表追加诊断。
迁移后可以复用已计算的事实，但必须区分“收集事实”和“发布诊断”：
公共上下文预计算不得直接向全局列表报错；编排层应在原调用位置按原顺序发布相应诊断。
原来用临时空列表只提取路径的调用不能因复用上下文而新增对外错误；也不能让全量绑定和可见绑定的复用
导致额外发布或漏发。首次拆分保留原始诊断序列及最终按文案去重的结果，不提前合并错误或改变路径顺序。

## 8. 错误信息与 fixHint 的解耦方式

第一期先在具体报错位置区分错误事实、合法约束和修复建议，再提供简单的建议扩展接口。
第 5 节保留的原始文案是盘点和兼容基线，不直接作为默认建议配置，也不通过匹配字符串自动拆分。

| 信息 | 迁移要求 |
|---|---|
| `message` | 描述本次错误事实；没有合适建议的错误仍可正常输出 |
| `expected` | 保存必须满足的合法约束；原文中用修改指导语气表达的硬约束也放在这里 |
| `fixHint` | 可选的操作建议；不参与是否报错、严重程度和合法性判定，不得放宽 `expected` |
| `legacyMessage` | 精确保留原有完整文案，包括其中已有建议；继续用于旧错误列表、异常文本和按文案去重 |

例如 OBS-L825 中的底部对齐、视觉补偿 padding、固有宽度和间距上限属于硬约束，
不能仅因句子像修改指导就放进可省略的 `fixHint`。OBS-L461 中“不能在同一 Text 拼接日期和星期”
属于约束，“默认保留星期，明确要求日期时保留日期”则可作为根据已知需求选择的建议。
布局规则中的数值、对齐和豁免以源码基线及方案总文档核对为准；发现冲突单独确认，不在拆分时消除。

建议统一经 `resolve_fix_hint(diagnostic, context=None)` 生成，使用以下顺序：

1. 根据稳定错误码查找可选的专用 Python 函数。函数读取本次诊断事实和可信上下文，
   有适用建议时返回建议文本；返回 `None` 表示无覆盖，继续查找默认建议。
2. 没有专用函数或函数返回 `None` 时，使用按错误码配置的默认建议。
3. 默认建议也不存在时，省略 `fixHint`，保留错误事实、合法约束和旧错误出口。

默认建议按具体规则码配置，不要求每条错误都配置建议；只有确实受入参或环境影响的规则才注册专用函数。
第一期不引入配置条件 DSL、优先级排序或通用策略引擎。专用函数使用普通 Python 分支，
不存在建议覆盖、无法生成建议或建议生成失败，都不能吞掉原错误或把失败判为通过。

- 分类只负责组织规则，稳定错误码应按具体违规含义设计，不能使用 OBS 行号作为长期错误码。
- 同一函数内不同原因可以使用不同错误码；重复实现同一含义时先核对适用范围，再决定是否共用错误码。
- 输入、环境和事实必须有可靠来源；未知条件保持未知，不臆造内容可删、布局可改或能力可用等前提。
- 默认建议须在该规则所有适用场景中均安全，因为专用函数返回 None 或失败也会回落到默认；仅在特定条件合法的方向只放入专用函数。
  原文案中的删减字段、移除动作等建议需按必要性约束
  逐项审阅。有明确证据表明内容可选或重复时才能给出删减方向，不能把旧文案盲目复制为默认建议。
- 所有建议只能引导模型修改本轮修复请求携带的 Compact DSL，定位遵守第 3.1 节；
  服务端 schema 缺失等上下文问题不能伪装成可由模型修复。
- 新建议独立输出，不拼回 `legacyMessage`；旧文案保留用于兼容，不赋予其中的建议高于硬约束的优先权。

结构化诊断保留在内部，模型输入按 [v3 方案第 6 节](Compact_DSL校验器重构方案_v3.md) 统一格式化。
内部质量问题的旧 message 及异常出口不变；构造模型请求时，为每个 qualityErrors 项生成新的 message，
按具体规则码、分类、可靠位置、问题、实际值及来源、硬约束和可选建议组织说明。
保留列表的 stage、code、数量和顺序，不再同时向模型发送旧错误全文和新诊断字段。
无可靠位置或建议时省略对应部分；只有旧字符串、同组混合迁移或格式化失败时沿用原说明。
旧字符串不包装成已迁移诊断；同组仍含字符串时不附加 compactDiagnostics，已有诊断继续保存在异常中。
同一旧文案关联多条诊断时，在同一模型错误项内分段列出，不按新文案再次去重。
模型请求使用副本，不修改内部数据；to_prompt_payload() 还用于修复记录，继续保留结构化对象输出。
仅带新诊断的 Compact 校验问题采用此格式，其他转换和标准产物校验问题沿用现有载荷。
warning 保持原字符串返回及流水线警告码、日志路径，不进入模型修复错误列表。

## 9. 盘点校验与后续维护

本清单通过 AST 提取主脚本中所有直接 `errors.append` 位置，并将 153 个位置逐项归入第 5 节；
同时单列 warning、异常包装、双动作和组合组件委托。
这证明静态诊断位置的覆盖，不证明业务规则完整性或运行时行为通过测试。

后续实现前，每个位置还需补充稳定错误码和对应测试用例。源码变动后，应重新核对位置集合、
函数名、触发前提及分类；尤其复核混合函数新增分支，避免默认归入布局。

### 9.1 已知基线差异与待决项

| 项目 | 当前代码基线 | 对照依据与问题 | 本次处理与后续决策 |
|---|---|---|---|
| BASE-01：纵向最小高度参考画布 | `compact_dsl_validator.py` 的 `_REFERENCE_CANVAS_HEIGHT` 将 `2x2`、`2x4`、`4x2` 设为 `150.0` | [云侧方案设计](../云侧方案设计.md)“校验与重试”规定 Compact 最小高度校验采用 `160vp` | 登记差异，不在分类或等价拆分中改常量、阈值、报错文案或快照；实施行为修正前单独确认依据并补充边界回归 |
| BASE-02：W9 无动作倒计时结构冲突 | OBS-L3455 要求背板直接包含三个 Text，OBS-L3909 又要求直接内容 Column | 同一稀疏倒计时背板同时触发，两种结构不能同时满足 | 待确认适用条件和优先级；保留等价行为及两种结构的复现，不生成保证可解的新建议 |
| BASE-03：分离单位建议冲突 | OBS-L3378 要求同 Row 且较小文字不加 bottom padding | OBS-L825、OBS-L1154 对混合字号要求底部补偿；照旧建议修改后仍会失败 | 旧文案逐字保留；新 expected 保留实际对齐约束，不复制冲突建议，不借调整建议改变阈值 |
| BASE-04：eventCount 适用边界 | OBS-L4139 检查所有 eventCount 引用的时间范围和日程文案 | 当前 design-compact-dsl/PROMPT.md 讲的是数量摘要；条件表达式仅输出状态时也被当前实现检查 | 作为边界待裁决，补充数量展示与条件状态、时间范围已知与未知用例，不臆造时间范围 |

保留代码基线只是等价拆分的验收依据，不表示认可它符合总方案。最终实施前必须明确该差异是独立修复
还是另行延期；未经确认不能同时宣称“现有行为完全一致”和“高度约定已符合总方案”。
BASE-02 至 BASE-04 同样不在本次文档更新中修正规则。新反馈涉及这些项时先审阅适用性，
事实与约束仍有争议则暂缓迁移该项、保留旧字符串路径，并在验收中列明未决范围。

### 9.2 迁移验收补充

- 使用相同校验输入比较原始错误序列、最终字符串去重结果、警告、异常类型、异常文本及异常链。
  补充重复 ID、重复 children、多父节点和含多个表达式错误的非法输入，验证第 7.1 节约束。
- 核对报错拆分后硬约束未落入可省略建议；覆盖纯错误、默认建议、专用函数返回建议或 `None`、
  上下文未知及建议生成失败。缺少建议不影响原校验结果，`legacyMessage` 和旧错误出口保持不变。
- 验证在线及独立修复入口使用同一说明格式；字段与事实来源完整，关联问题分段保留，无位置或建议时正确省略。
  覆盖旧字符串、同组混合迁移和格式化失败兜底，核对错误数量及顺序不变；内部字段及修复记录仍为原结构，不被模型说明覆盖。
  warning 继续从原结果出口发布，不升级为待修复错误。
- 覆盖绑定路径修复、事件替换、字面量内联及数据行删除，检查第 3.1 节的文本来源和定位；
  无可靠映射时省略位置，不能把错误行号传给模型。
- 修复链路的兼容测试固定每轮模型返回的 DSL 序列，再比较错误出口、重试次数和最终响应。
  真实模型在新增建议后可能生成不同文本，其修复效果单独评估，不要求最终异常文本天然相同。
- 线上验收同时比较状态、业务错误码、中文提示和是否保存产物，区分 Compact 严格校验与标准产物质量观测，
  覆盖重试关闭、开启及耗尽；详细兼容矩阵以 [v3 方案](Compact_DSL校验器重构方案_v3.md) 为准。
