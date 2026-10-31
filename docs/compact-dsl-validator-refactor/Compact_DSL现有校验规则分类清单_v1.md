# Compact DSL 现有校验规则分类清单 v1

2026-10-29 模板宽卡组合修订：Hero + Compact 必须有一个 PillAction，Full + Compact 不接受动作。
此项属于模板语义／布局组合合同，实际判定继续位于
`template_generation/engine/cardplan/compiler.py::_validate_provider_template_layout_action_requirements`，
复用布局注册表的子项数量检查，不向 Compact DSL 校验目录复制模板规则。
`wide_template_planner.py` 负责合法候选与动作归属，`advanced/ux_mixed_prompt.py` 负责二层候选投影；
回归见 `test_wide_hero_compact_layout.py`，画廊独立断言正例及缺按钮、错角色等反例。

2026-10-28 日程条目点击：`items[].onClick` 的字段和单 handler 形状归语法／组件，
委托 `compact_high_level_components.py` 共享合同及展开后 `syntax/components.py`；
有效日程详情、展示与参数的同数组记录归属、重复详情入口归语义／有效能力，
唯一落点为 `semantic/event_items.py`，诊断为 `COMPACT_EVENT_ITEM_MISMATCH`、
`COMPACT_EVENT_ITEM_DUPLICATE`。记录路径解析复用公共 BindingValidator，不按标题或样例值推断。
动作实例引用由 `compact_action_instances.py` 统一提供，Plan 覆盖仍归 `compact_plan.py`，
条目点击的素材豁免仍归语义／跨文件一致性的 `semantic/plan_contracts.py`。
新增规则只作用于 EventCard 条目点击，不迁移历史规则；建议在 `repair_hints.json`，
回归在 `test_event_card_item_clicks.py`，规则目录及归属快照同步登记。

2026-10-28 重复动作补漏：重复按钮属于语义／展示，由
`semantic/action_display.py` 基于原始可达树、完整事件数组及已接受 Action 判定；Plan 覆盖编排
携带独立 `duplicateActions` 定位，沿用 `COMPACT_PLAN_COVERAGE_FAILED`；
`generation_pipeline.py` 只传递诊断，不构造按钮自动删除或布局变体调整候选。
`compact_repair_strategy.py` 负责局部／必要父布局路由，`prompt_builder.py` 格式化动作反馈。
不恢复旧 W9 特例，不修改候选事件匹配、组件合同、容量门禁、模板豁免或重试预算。

2026-10-27 单位校验补充：缺失、重复单位归语义／展示语义，继续由公共
`card_validation/display_unit_validator.py` 判定，`display_unit_rules.py` 提供绑定单位与相邻拼接匹配。
单位后允许空白或标点分隔，不跨动态字段借用单位，不按业务文案新增后缀特例。
缺失与重复单位在既有检查范围内统一为 error，删除百分比缺失降为 warning 的符号特例。
自动去重仍只删除独立纯单位片段，不删除带业务文案的字符串；判定归展示语义，修复边界保持不变。
`validator.py` 适配专项结果；`widget_generation_service.py` 仅编排：Compact 创建关闭完整产物校验时仍执行
同一单位检查，使错误进入已有质量修复。开启完整校验时不重复调用专项检查；模板豁免保持不变。
不新增 Compact 转换前检查、不移动既有规则、不增加重试预算。回归见 `test_display_units.py` 与
`test_generation_unit_validation.py`；复杂表达式仍沿用现有支持范围，不引入通用解析器。

2026-10-27：Plan Action 覆盖仍由 `compact_plan.py` 的生成编排层检查，动作素材履约仍归
语义／跨文件一致性的 `semantic/plan_contracts.py`。已接受 Plan 含至少三个不同 Action，且 DSL
已从 root 可达地保留至少两个不同、handler 精确匹配的合法按钮时，未落位的第三个及
后续 Action 覆盖缺失降为 warning，对应素材“无匹配按钮”不重复阻断。这是生成阶段的容量降级，
不迁移校验归属，不放宽单按钮合同、事件参数、可达性、重复动作或布局槽位检查。

2026-10-26：动态 `info_required[].text` 是否为 `userQuery` 连续原文片段，归信息计划合同，判定位于
`compact_plan.py`，不迁入 Compact DSL 校验目录。该来源不匹配由阻断错误调整为 warning，保留模型提交的
事实，不单独触发 Plan 修复；初始 Plan 提示仍要求优先逐字引用。`dataId`、`actionId` 来源、Action 合同及
后续 Plan 覆盖、绑定、协议和布局容量检查不受影响。

2026-10-28 非容量修复：Plan 单调用包装、参数层级及重复 JSON 键由 `compact_plan_output.py`
解析规范化，`compact_plan.py` 保留本轮字段与事实校验，并依据真实不同动作数约束双动作候选。
静态分组／省略账本由 `compact_plan_feedback.py` 格式化已有关系错误，`prompt_builder.py` 只在
失败静态 Plan 的原修复轮次注入，不猜补事实归属或改变省略许可。动态重复事实仍由原 Plan 覆盖规则判定；
`compact_duplicate_display.py` 只构造独立重复项的有界去重候选及说明，`generation_pipeline.py`
通过原完整处理链复检后才采用。不新增容量规则或错误码，不修改宽高、字体、组件合同与成功源。

2026-10-25 静态展示质量增量：`displayRole`、`presentationStyle`、`paletteFamily` 的静态专属形状与
枚举检查归 `compact_plan.py` 的信息计划合同；动态 Plan 不接受这些字段。可省略属性标签的字段形状
由 `static_content_components.py` 共享展开检查，归语法／组件；value 仍必填，显式 label 不得为空。
属性列参考宽度与行盒沿用共享文字度量，实际整卡容量仍由原语义／布局规则判定。
候选只消费模型角色、结构偏好及可选事实授权，委托公共校验，不根据 query 或业务词裁决内容。
静态主题稳定选择与浅色面板属于后置主题策略，不新增校验诊断或改变动态规则。

2026-10-25 摘要职责修订（替代此前静态提取式规则）：
sourceTexts当前输入可追溯与明确原文约束仍归semantic/cross_file.py；
删除数字/原文标签匹配、分句限定词检查，语义交给既有Plan与DSL模型阶段。
已接受展示版本的同组落实与可选遗漏归semantic/static_content.py，不再识别数字或条件词。
容量仍归semantic/layout及共享static_text_capacity.py，数值词元仅用于换行。
static_content_planning.py仅试排完整计划，不删选事实、不匹配关系词、不自动归位保护或补证据；
有限候选未命中不再硬拒Plan。调用编排与闭域错误严重程度不变，不新增诊断码。
历史条目中的提取式匹配、程序筛选与尾部截短规则以本修订为准。

2026-10-25：混合标识/日期边界与分隔符来源比较归semantic/cross_file及共享static_text_capacity；
同组保护片段归位属于compact_plan委托的计划标准化。真实截短与最终覆盖归semantic/static_content；
规划说明与实际删减分离、内部试排源字段形状归compact_plan，响应继续委托原ResponsePlanner。
static_content_presentation只构造有限候选并委托正式校验，不增加入口校验或复制几何公式；
候选采用归generation_pipeline，重复停止归compact_repair_strategy。沿用现有诊断码及闭域严重程度。


2026-10-24 交付优先修订：来源引用只核验被选读数与局部条件（semantic/cross_file.py）；
删除 Plan 全卡三对象及粗估高度门禁，实际组件/整卡容量仍归 semantic/layout/text_capacity.py 和原布局规则。
可选 should、省略号、属性表逐行及分隔符规范化归 semantic/static_content.py，覆盖与交付反馈共用；
Plan selectionNotes 仅为内部取舍字段，由 compact_plan.py 校验形状，现有响应规划返回 degraded。
语法准入、动作、原文保护和闭域严重程度不变，未新增诊断码。

2026-10-24 收敛补充：

| 检查项 | 分类与实际位置 | 归属理由 |
| --- | --- | --- |
| 开域模型源禁止旧正文及基础节点 | 语法／组件，syntax/components.py，api.py 在展开前委托 | 是模型可提交类型集合，复用既有禁止组件诊断，不检查生成容器 |
| 同组已选读数、单位及相应分句限定词完整性 | 语义／跨文件，semantic/cross_file.py | 核对来源与计划，允许同对象跨事实拆分，不跨对象借用 |
| Plan 动作数量与正文角色 | 语义／布局，semantic/layout/text_capacity.py，由 compact_plan.py 委托 | 不以记录数替代全卡容量，不承担布局选择 |
| 关键片段换行与详细文字容量 | 语义／布局，共享 static_text_capacity.py；text_capacity.py 发布原容量诊断 | 展开与校验同一度量，语义组件负责生成固定行 |
| 静态生成单行宽度 | 语义／布局，semantic/layout/text_width.py | 静态生成标记继续采用共享静态文字度量和省略号合同，不改静态字号与行数 |
| 普通完整单行文字宽度 | 语义／布局，semantic/layout/text_width.py | 仅Runtime Recipe明确标记的EmphasisText.main与compact_composition_planner._text_width共用压力估算；其它普通Text、SummaryList等保持原保守估算，静态专用度量及省略号合同保持。固定强调文字的必要父级修复范围归compact_repair_strategy；2x4主文超宽且无次文本时，由该策略附条件化主次字段重排建议，不在校验器改写文字或授权省略 |

以上沿用已登记诊断，不新增规则码，不迁移其它检查或更改闭域严重程度。

2026-10-24：开域静态内容采用请求级准入，不改变原动态集合和校验默认值。

| 检查项 | 分类与实际文件 | 归属理由 |
| --- | --- | --- |
| sourceTexts 当前输入引用、连续片段与完整数字词 | 语义／跨文件一致性，`semantic/cross_file.py` | 比较静态 Plan 与本轮来源，不能靠来源存在证明自由摘要正确 |
| 对象顺序、同组覆盖、shared 位置、核心和原文保护 | 语义／展示，`semantic/static_content.py` | 比较已接受分组与原语义条目；同对象连续属性行及合法组件内完整公共说明共用归属映射。多对象续行仅在对象名唯一、首行和续行明示本对象、完整补足本组新事实且不覆盖别组名称或事实时成立；同值或同名歧义、残词、未知文字及重复条目仍拒绝。覆盖、最小删减和实际省略反馈共用判定；不调整几何和容量 |
| 静态上下文缺失 | 语义／跨文件一致性，`semantic/static_content.py` | 缺少受信服务上下文时拒绝，不能由模型标记授权 |
| 单字宽、完整行数及固定行高 | 语义／布局，`semantic/layout/text_capacity.py`；度量合同 `static_text_capacity.py` | 共享文字度量及参数，不在入口复制容量判断；总高、横向预算仍委托原布局校验 |
| 新组件属性与静态值形状 | 共享展开 `static_content_components.py`、组件／绑定准入模块 | 新组件展开为原 Text / Row / Column / Divider，保留旧组件默认合同 |
| 静态布局角色、贴底组合 | 共享编译 `compact_semantic_layout.py`、`compact_layout_runtime.py` | 几何和角色仅一个实现；单独有效 scope，不向动态范围加入新布局 |
| 主题后文字、可达性及前景冻结 | 保存前语义复核 `static_content_context.py` | 复用既有主题前景签名；主题不能改变文字或祖先容量关系 |

Plan 的来源字段、contentGroups 结构和去重索引映射归 `compact_plan.py`；
静态名称与展示版本的核对提醒归 `static_content_planning.py`，只附于已有试排失败反馈，
不是别名推断或新的校验门禁；最终名称及同对象事实覆盖仍归 `semantic/static_content.py`。
建议格式化归 `repair_guidance.py` 和 `repair_hints.json`，调用编排归 `generation_pipeline.py`、
`widget_generation_service.py`，有界修复授权归 `compact_repair_strategy.py`。
六个新增诊断已登记到规则目录与回归清单，不进行其它校验整体迁移。

2026-10-21：编辑目标履约属于标准 A2UI 的语义／编辑目标一致性，判定位于
`card_validation/edit_validation/artifact.py`；模型意图形状、字段权限及可比较性属于
`widget_edit_contract.py`。提示词加载与修复格式化位于 `widget_edit_prompt.py`，编排仍在
`widget_edit_service.py`。复用现有样式合同，不新增或搬迁 Compact 检查，不影响创建入口。

2026-10-21：标准 A2UI 编辑的固定高度与子文字最小字号矛盾归入
`card_validation/edit_validation/artifact.py`（语义／布局与可读性）。比较父子组合的新旧不足差额，
父容器未变化而子字号增大仍检查；不复制 Compact 几何规则，不改变首次生成校验。

2026-10-21：`W-top-bottom.details` 允许的直属组件增加 `EventCard`，归属语义／布局合同，
唯一判定落点仍为 `services/compact_semantic_layout.py`。该变更只放宽已登记父布局的 details 角色；
EventCard 的 Props、事件顺序与总高继续由共享组件和容量校验负责，不在语义编译器重复实现，
不新增错误码，不改变 `InfoBlock` 与 `CardButton` 在该槽位中的禁止边界。

2026-10-20：2×2外层重组结构整理归生成修复编排，落点仍为
`services/compact_outer_recomposition.py`。候选生成与有限搜索分离，32个实际候选使用显式预算；
候选顺序、首个合格即采用及原稿回退语义保持不变。Compact规则判定仍委托公共校验入口，
Plan事实动作覆盖仍委托`compact_plan_coverage_errors`；不新增或迁移语法／语义检查项。
重组仅返回结果，现有Trace仍由`generation_pipeline.py`记录，本次不调整日志打点。

2026-10-21：经用户确认，2×2双必要动作由PillButton改为CardButton。
组件尺寸可用性和单行/两行槽预算委托共享Recipe及高阶组件转换；
固定角色与36/57vp槽位归共享语义布局编译和布局合同；
actions-only恰好两个不同动作且无正文的授权仍归semantic/plan_contracts.py。
Plan候选标准化只改动作组件，不删除事实或改变事件/素材授权；不新增错误码或放宽溢出校验。

2026-10-17：纯双动作布局与开关事件比较补充：

| 检查项 | 分类与实际落点 | 归属理由及边界 |
|---|---|---|
| actions-only 结构与几何 | 共享语义布局编译 `compact_semantic_layout.py`、布局合同 | 只增加同名布局的无内容变体，按钮尺寸与标准内容变体不变 |
| 无正文动作变体必要事实授权 | 语义／跨文件一致性，`semantic/plan_contracts.py` | `actions-only` 必须恰好两个不同动作；`title-action` 必须恰好一个动作；两者均不得含展示事实，不豁免覆盖检查 |
| 组件槽位角色与确定容量下界 | 生成侧共享 `compact_slot_compatibility.py`，组合候选复用 | 读取既有布局和 Recipe；未知不判可行，不新增发布错误码或复制几何校验 |
| 已登记开关历史标记兼容 | 语义／有效能力，`semantic/effective.py`；共享规范化与比较 `event_matching.py` | 2026-10-20 覆盖八类已登记开关；注册表不声明历史标记，预检仅在 schema 校验副本中处理，Plan、素材与最终产物共用省略和整数 0/1 等价规则；其它参数精确比较，非法显式值不通过转换修正放行 |


> 2026-10-12 Fusion 融合修订：本文原有数量、源码位置和验证结果描述融合前版本。当前分支同步 main `69c153f5`；本次按用户要求将 PR 净差异压成单个提交，SVG 填色按用户要求保留 PR497 前规则，迁移去向与实际验证见 [Fusion 融合记录](Compact_DSL_Fusion融合记录.md)。旧规则不得因目录合并重新启用。

- 日期：2026-09-30
- 依据：[Compact DSL 校验器重构方案 v3](Compact_DSL校验器重构方案_v3.md)
- 状态：保留重构前盘点；已完成本次范围的迁移及确定性验证，当前落点见第 10 节，既有待决问题及验证限制见实施记录。
- 分类澄清（2026-10-08）：一级分类统一为语法和语义，素材字段的格式与表示要求并入语法／组件；历史观察位置、实际规则归属及错误码不变。
- 统计基线：提交 `9d567c5f994903882802dab620171d010124ad90` 中的主校验脚本；第 5 节行号是该基线的历史位置，不是拆分后的源码行号。


## Fusion 融合后的当前生效约定

2026-10-17：2×2 单业务唯一只读详情支持服务端派生的整卡动作承载。
compact_whole_card_click.py 只提供已登记动作、对象与用户按钮要求的共享适用性合同，
compact_plan.py 在接受阶段保留动作事实并派生 wholeCardActionId，不由模型自行授权。
根点击与完整 handler、唯一入口、按钮素材的一致性归语义／跨文件一致性，落点
semantic/plan_contracts.py；布局动作槽计数仍归语义／布局，委托 compact_layout_runtime.py，
api.py 仅透传复核后的 handler，不复制适用性或计数判定。组件、绑定、容量及端侧事件协议不变；
无已接受整卡上下文、2×4、模板与无 Plan 路径继续原合同。

2026-10-17：请求内跨结构、容量、覆盖与动作素材的联合重组归生成修复编排，
由 compact_repair_strategy.py 消费历史类别及源稿拓扑摘要；compact_repair_context.py
仅提取拓扑和已接受合同摘要，不产生校验错误。PromptBuilder 交接联合核对清单。
结构、事实、动作、素材及几何的判定、严重级别、顺序和 Drop 授权均保留原归属与行为。

2026-10-17：TextBlock 槽位容量属于生成合同与组合建议，宽度参数仍由
compact_component_runtime.py 的 Recipe 提供，compact_composition_context.py 交接实际槽宽，
compact_composition_planner.py 共用最小宽度合同；不改语义／布局的横向预算判定。
组件树的重复引用、多父引用、空容器仍归语法／组件；不可达等编译检查保留原落点。
compact_repair_strategy.py 仅消费已有诊断与兼容说明，统一路由至布局结构重组；
不在修复路由复制判定、不新增校验项或错误码。

2026-10-16：修复语义布局展开重新解析时遗漏模板来源上下文的问题（issue #570）。
组件类型白名单仍属语法／组件，唯一判定位置为 compact_dsl_a2ui_converter.py 的
_parse_component_header；generation_pipeline.py 只透传 skip_compact_dsl_validation，
expand_compact_semantic_layout 将其交给共享解析器。不新增校验分支或错误码，普通模型输入、
未知组件、保留属性及语义布局角色／尺寸约束保持不变；覆盖模板内部组件与普通输入边界回归。

2026-10-15：TextBlock.items[].label 与 items[].value 一致允许静态值、完整 Expression 和
PathBinding。该调整归属语法／组件的共享绑定合同，落点 compact_component_bindings.py；直接
PathBinding 的 string/number/integer 类型相容性仍归属语义／数据绑定，不在分类入口复制检查。

2026-10-15：Plan 展示事实覆盖调整为请求级一次硬校验。首次 DSL 评估仍严格检查全部
Plan 事实；进入第一次模型 Repair 后，compact_plan.py 仅将非 Action 展示事实缺失转为
warning，2×2 与 2×4 共用该逻辑。此项属于生成编排层的降级政策，不新增语法／语义校验器。
Action 事实、事件 handler、动作素材、动作槽及其它 Compact 校验不降级。
enable_drop_plan_fact_validation 默认关闭；开启时在 Repair 阶段恢复严格事实覆盖，仅保留程序明确
授权的 Drop 豁免范围。

2026-10-19：修正首次 Plan 静态事实覆盖的严重程度。`compact_plan.py` 不再将 `text`
未完整可见无条件写为 warning；首次 DSL 评估与数据事实一样生成覆盖 error，进入
模型 Repair 后才按上述请求级政策决定是否降为 warning。归属仍为生成编排层的 Plan
覆盖检查，不在 Compact 语法／语义校验器内重复实现。
静态路线同样遵守该政策：首次修复后的非 Action 分组覆盖缺失由编排层记为 warning，
Compact 静态分组检查不再对同一缺失重复生成阻断错误；其它静态组件与容量检查不变。
容量恢复的第二轮接口继承该 warning 状态，不重复消耗同一请求的覆盖硬校验次数。

2026-10-15：SecondaryBody.items数量上限由4改为6，归属语法／组件合同，仍委托
compact_high_level_components.py的共享组件校验，不在分类入口重复实现。实际数量超过6时进入
既有组件修复，由compact_repair_strategy.py说明可选补充项清理与Plan保护；容量归属与Drop授权不变。
`COMPACT_LAYOUT_HEIGHT_OVERFLOW` 可附带 `SecondaryBody` 可保留行与 `doesNotFit` 条目证据；
该证据仍归属语义／布局几何，Drop 选择与核心组件保护仍归属修复编排，不在校验入口重复判定。

2026-10-28：`TableText.items` 的 2–3 项限制继续归共享语法／组件合同；当既有诊断明确表明条目超过
三项时，`compact_repair_strategy.py` 仅消费该诊断并直接路由到条目级有界 Drop，逐项删至三项。
此变更不复制组件判定、不改变错误严重等级；事实优先级、Action 保护和核心组件保护仍归修复编排。

2026-10-14 单例检视补充：2×4 SecondaryBody 单行的完整值与静态标签共同核算宽度。
归属语义／布局与视觉约束，落点 semantic/layout/text_width.py，复用现有同行压力函数及建议；
api.py 仅启用该尺寸的检查。未知值或兄弟标签不估猜，不恢复其它旧门禁，2×2 发布判定不变。

同日补充 2×4 语义编译反馈：共享 Runtime compact_semantic_layout.py 的既有角色数、父区变体
检查在原失败信息中列出有序角色及该父区允许的变体；仍委托该编译器判定，校验分类入口不重复实现。
不改变成功/失败边界、几何或检查顺序，不包含业务答案，仍通过既有转换错误路径传递。
2026-10-15 将 `W-content-side-slots` 中“上方 CardButton、下方 InfoBlock”的顺序检查从转换错误降为
warning；共享 Runtime 继续确定性展开原顺序，版本化物理布局合同同步登记左右方向下的反向混合槽，
避免后续布局匹配将同一建议重新升级为错误。校验入口只收集建议，不复制槽位判断；槽位数量、组件角色、
事件归属、父区变体与几何检查仍为原有硬校验。

2×4 多字段文本宽度检查在同一 semantic/layout/text_width.py 中复用既有安全解析器，
不增加任意表达式求值器。已知字符串连接与简单布尔分支按完整文案核算，未知值和算术不猜测；
2×2 原行为不变，继续沿用已有宽度错误及建议。

### 2026-10-12 最终设计对照复核

当前基线为 main `69c153f5`（已包含 #506 和 #500）。语法／语义分类及 32 个活动结构化错误码不变，
共享解析、组件合同、布局运行时和完整产物校验继续委托原模块，不为补齐分类而复制规则。
复核修正高度溢出、进度与读数对象不一致的事实／约束／建议混写，并将组件白名单的指导语移出事实描述；
旧异常文案、顺序和判定保留。默认建议现有 8 条，按条件覆盖的专用函数接口仍按需注册。
#506 的 Plan 警告、程序授权省略、累计省略及重试路由均保留；fixHint 不覆盖程序授权范围，
警告不进入 Compact 修复错误列表。repair_context 位于主线已有参数之后，保持原有参数顺序。
本次用户明确要求将 PR 合成单个提交，之前“保留历史提交”的说明仅描述当时的操作，
天气降雨概率数值 schema 与模板按 #500 原样同步，不新增 Compact 专属规则。
原分支已备份为本地 `codex/backup-compact-before-review-squash-20261012`。
完整审查、主线失败对照及单提交文件清单见 [Fusion 融合记录末节](Compact_DSL_Fusion融合记录.md#最终设计复核与单提交整理2026-10-12)。



2026-10-12 经逐项 review 后恢复三项明确校验，属于已批准的行为补充，不是重构时自动复活旧规则。
详细范围、兼容边界及本轮验证见 [Fusion 融合记录](Compact_DSL_Fusion融合记录.md#融合后经确认的规则恢复)。

| 检查项 | 当前落点及分类 | 执行范围 |
|---|---|---|
| 模型素材候选范围 | `semantic/effective.py`，语义／有效能力，`COMPACT_ASSET_NOT_ALLOWED` | 展开前登记 icon、visual.icon、items[].icon；保留展开后背景检查。兼容引用提取不重新开放 Image 等内部组件 |
| 可染色 SVG 漏色 | `semantic/layout/assets.py`，语义／布局与视觉约束，`COMPACT_SVG_FILL_COLOR_MISSING` | 仅 ProgressCircle；CardButton 等自动着色组件和 PNG 不触发 |
| CardButton 图标字段合法性 | 共享高阶组件合同，语法／组件 | `CardButton.icon` 可省略；存在时必须是非空静态字符串。省略业务 icon 时，转换器注入固定回退图标 `resources/base/media/ic_fallback_light.svg`，保留图标槽及对应文字宽度预算；不生成额外圆形、分隔线等占位视觉 |
| CardButton 与 Plan 素材分配一致性 | `semantic/plan_contracts.py`，语义／跨文件一致性 | Plan 为动作分配非空素材时，DSL 继续使用该 ID 的原始 `src`；Plan 为空或没有素材候选时允许 DSL 省略业务 icon，由转换器注入固定回退图标，不得伪造业务素材或额外占位视觉 |
| 按钮可见文案长度 | `semantic/display.py`，语义／展示，`COMPACT_DISPLAY_ACTION_LABEL_TOO_LONG` | 原始 `PillButton`、`CardButton` 的静态 `label` 最多6个非空白字符；超限只授权缩短可见文案，完整保留 `onClick`、动作目标、组件与布局；由既有 DSL 质量修复处理，不占 Plan 重试预算 |
| 数值组件选型 | `semantic/numeric_display.py`，语义／展示，`COMPACT_DISPLAY_NUMERIC_COMPONENT_MISUSE` | 仅原始 EmphasizedData 的确定误用；未知字符串类型、表达式、配速及占位值不一概拒绝 |

2026-10-12 合入标题图标：`SingleLineTitle.icon` 纳入原始素材引用登记，继续使用上述两个素材错误码。
图标与颜色的类型、格式和关联字段仍委托共享组件合同（语法／组件）；标题高度预算属于语义／布局，
由 `semantic/layout/geometry.py` 根据有无图标读取共享 Recipe，分别预占 20vp／12vp。
无图标的历史标题行为不变，不恢复旧全局颜色门禁；合并方式与逐项验证见 Fusion 融合记录末节。

后续 #498 的宽高预算继续属于语义／布局：预算树先按共享文字对齐规范化，小卡高度采用主线 2vp 容差；
`flows/text_pressure.py` 只编排修复用文字压力提示，不将其升级为新的发布门禁。

新增原始组件检查在既有绑定／多段时长检查后、展开前执行；错误在原始上下文中定位，
并沿用现有异常与修复反馈。规则不内嵌建议，默认建议由 repair_hints.json 按规则码提供。
模板生成来源继续跳过 Compact 校验；不恢复旧全局字号、布局、动作或事实去重规则。
历史产物编辑前预检同样执行当前规则，不自动迁移旧不合规产物。


本轮继续融合 PR489/492：多段时长选型归入 `semantic/display.py`，完整文案及标签时长组合宽度归入
`semantic/layout/text_width.py`，TextBlock 标签只在同项 Recipe 内查找。这些新错误保持主线原文路径；
该次融合的 30 个结构化错误码不变；后续经确认的规则恢复见下文。修复范围由现有 `repairStrategy` 编排决定；可选 fixHint 不承担重试路由，
`compositionRecovery` 遵守主线运行时容量提示开关，关闭时不沿用历史参考。

以 main `a42d86a5` 为行为基线，当前模块及规则去向见 [Fusion 融合记录](Compact_DSL_Fusion融合记录.md)。
后续章节中的 153 个历史观察位置、147 个旧错误码、旧 W9/S4/ActionUnit 目录及旧版验证数量均属于融合前快照，
不能据此恢复旧规则或要求当前实现维持旧的组件合同。
当前保留语法／语义两类；32 个活动结构化错误码之外的共享运行时错误按原文传递。
公开入口新增参数是主线 protocol_profile、layout_scope、enforce_model_component_types 与重构
original_source、repair_context 的并集，默认行为、错误顺序、去重及 warning 保持主线。
高阶组件展开前后使用独立树；展开事实标为 expanded，没有可靠来源映射时不发送原文位置。
Plan 独立错误码、Occupancy、Alternatives、previousFailures、compositionRecovery 和 Trace 均保留。
提示词说明只写入 fusion/prompt_source/repair.md，不恢复已删除的旧 REPAIR_SYSTEM_PROMPT.md。
高度建议要求保留固定设计量，重组合法布局；新增规则仍按约束性质归类并复用已有运行时合同。


## 横向固定内容预算补充（2026-10-14，Issue #538）

2026-10-19：满宽四项 TextBlock 的横向校验上限放宽至 280vp，允许实际满宽参考槽位
至多 4vp 的预算差额。判定仍归 `semantic/layout/horizontal.py`，共享预算计算放在
`compact_component_runtime.py`，Plan/生成容量说明复用；校验入口仅透传展开前组件。
不调整渲染 Recipe、窄分区、其它 Row、动作或高度规则，不新增诊断码。

2026-10-21：TextBlock 将容量评估下限与渲染最小宽拆分。`minimumItemWidth:64` 继续由
`compact_component_runtime.py` 提供给 Plan、组合与 `semantic/layout/horizontal.py`；展开后的
item 使用 `layoutWeight:1`、`flexShrink:1` 和 `constraintSize.minWidth:0` 等权适配实际父槽。
本项不改变检查项分类、四项280vp参考预算、窄分区拦截或8vp间距，只修复合法满宽四项在端侧
突破安全边距的问题。

| 检查项 | 分类与实际文件 | 归属理由及边界 |
|---|---|---|
| `COMPACT_LAYOUT_WIDTH_OVERFLOW` | 语义／布局与视觉约束，`semantic/layout/horizontal.py` | 判断展开后 Row 的固定内容、嵌套后代、margin 和间距能否放入当前参考分区；属于空间预算，不属于语法或绑定 |

共享 `reference_region_boxes` 提供画布与权重分配，当前组件 Recipe 提供固定设计尺寸；
不另建标题高度或文字字体估算，也不整体迁入 PR #470 的二维几何引擎。
执行位置在 `api.py` 的现有高度与文字宽度预算之后，保持前置校验、warning 和模板跳过语义。
错误事实通过 `CompactDiagnostic` 返回，建议在 `repair_hints.json` 登记；流水线继续负责修复编排。
本次新增 1 个活动结构化错误码（合计 33 个），规则登记夹具与 `test_compact_horizontal_budget.py` 同步。
未知几何、未建模约束、任意二维相交及字形裁切不在本项覆盖范围内，不把未报错等同于像素验证通过。

2026-10-17 根据 2x2 与 2x4 灵动布局实测增加严重程度分级：当前 Row 的有效间距能够完全吸收溢出
且溢出不超过 16vp 时降为 warning；根 Row 的 2x2/2x4 阈值分别为 10vp/32vp；位于父 Row 分配的
正数 `layoutWeight` 横向权重区域内时，2x2/2x4 阈值分别为 24vp/52vp。判断顺序为间距、根布局、
横向权重区域，warning 保留 Occupancy 与降级原因。固定局部 Row、超过对应阈值和无法确定分配的场景
仍为 error。文字宽度预算先于本项执行并保持严格；同一产物存在文字宽度错误时，不能被本项 warning
放行。该调整不改变检查项分类、实际文件、错误码及调用顺序。

2026-10-19：高度与宽度经验阈值统一由
`data/validator_rules/compact/layout_overflow_tolerances.json` 提供，配置声明 vp 单位、2x2/2x4 和各适用
场景，并在加载时校验。横向权重区域向上查找遇到数值宽度且 `flexShrink:0` 的固定宽度边界即停止，
不得继续凭更高层祖先权重降级；间距完全吸收仍独立判断。阈值只表示经验容忍，不证明端侧必然消除
溢出。本项仍归 `semantic/layout/horizontal.py`，配置解析归同目录 `overflow_tolerances.py`。

2026-10-20：收紧纵向高度策略，从上述配置删除高度容忍规则，取消根 Column、正数
`layoutWeight` Column 和可压缩 `itemMargin` 的 warning 豁免。2×2 仅保留整树 `2vp` 数值容差，
2×4 不设高度容差；超过容差且最小占用及可用高度已可确定时，统一产生
`COMPACT_LAYOUT_HEIGHT_OVERFLOW` error 并进入布局容量修复。横向 warning 策略保持不变；纵向规则
仍归 `semantic/layout/geometry.py`。

同日补充 TextBlock：本规则读取顶层及 constraintSize 内静态 minWidth/maxWidth，
高度专用约束不阻止横向检查。TextBlock item 另读取 Recipe 的参考容量下限，避免渲染约束改为
可收缩后绕过窄分区门禁。最小宽度参与子树需求；参考分配尚未计算上下限重分配，
受约束影响的后代槽位继续按未知处理，避免把分配前宽度当作实际宽度。
该补充仍归 horizontal.py，不增加诊断码；原始 3:1 分区案例记录于 text-block-input.jsonl。

## CodeCheck 整改范围收敛（2026-10-12）

本 PR 只保留 Compact 自身的等价整改：`compact_validation/constants.py` 的测量样本正则拆分长行，
正则内容、单位集合及匹配行为不变。原 MR609 中涉及 JSX Runner 的 8 个源码文件和专属测试已从本 PR
净差异撤销；这些独立整改应另行提交，不再列为 Compact 分类迁移内容。历史 commit 不改写。

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

语法检查写法和组件结构是否符合协议；语义检查数据、能力和展示是否正确合理。
结构契约仅用于解释语法类中的属性和父子结构要求，不单独作为分类名称。
语法包含协议、组件、CardSpec、表达式四个子类，语义包含数据绑定、跨文件一致性、有效能力、展示语义、布局与视觉约束五个子类。

| 一级分类 | 二级分类 | 判断依据 | Compact 本次迁移目标 |
|---|---|---|---|
| 语法 | 协议 | 输入行、记录结构与解析是否合法 | 沿用已有解析器，不复制实现 |
| 语法 | 组件 | 组件自身属性（含素材字段的类型、引用格式与表示要求）、事件对象、父子结构是否合法 | `syntax/components.py`，组合组件继续沿用转换器委托 |
| 语法 | CardSpec | CardSpec 自身字段和 schema 是否合法 | 主脚本无完整校验，保留现有完整产物校验 |
| 语法 | 表达式 | 包装、引用及路径表示是否合法 | `syntax/expressions.py` |
| 语义 | 数据绑定 | DSL 引用能否取得首帧数据，绑定源类型是否适合目标组件 | `semantic/bindings.py` |
| 语义 | 跨文件一致性 | DSL 与 CardSpec、生成上下文的结构化声明和使用是否一致 | `semantic/cross_file.py` |
| 语义 | 有效能力 | 具体事件、素材是否在本次候选范围内 | `semantic/effective.py` |
| 语义 | 展示语义 | 值形态、单位、标签与业务归属是否正确，内容和必要动作是否完整，是否重复展示 | `semantic/display.py` |
| 语义 | 布局与视觉约束 | 空间、密度、字号、骨架、对齐和染色是否符合要求 | `semantic/layout/` 下对应模块 |

表中模块路径均相对于已实现的 `card_validation/compact_validation/`，实际迁移情况见第 10 节。
素材是被检查的对象，不单列语法子类：字段类型与表示要求归入组件，可用范围归入有效能力，染色要求归入布局与视觉约束。
每个具体检查项只有一个主要归属；输入跨多个对象，不自动意味着它属于跨文件检查。
例如字段标签是否清楚属于展示语义，而首帧值是否符合外部声明类型属于跨文件一致性。
语义分类不意味着警告或非阻断；分类、严重程度、Compact 内部调用位置保持独立。

与方案统一采用以下判断问题：数据绑定看“能否取值并用于目标组件”；跨文件看“结构化声明是否一致”；
有效能力看“是否允许使用”；展示语义看“含义与完整性、重复或遗漏”；布局看“如何摆放及空间视觉约束”。
读取外部上下文不自动归为跨文件，读取候选能力不自动归为有效能力。
需求完整性和动作使用约束作为展示语义的内部规则组，不增加一级或二级类别。

| 易混淆的检查 | 主要归属 | 判定理由 |
|---|---|---|
| 胶囊 ActionUnit 的 `icon` 为数字，如 `123` | 语法／组件 | `syntax/components.py` 的 `_collect_action_unit_errors` 检查非空字符串要求，错误码为 `COMPACT_ACTION_ICON_INVALID` |
| 素材字段为非空字符串，但不在本轮候选集合内 | 语义／有效能力 | `semantic/effective.py` 的 `_collect_model_asset_source_errors` 检查原始图标是否允许使用，错误码为 `COMPACT_ASSET_NOT_ALLOWED` |
| ProgressCircle 的可染色 SVG 缺少显式颜色 | 语义／布局与视觉约束 | `semantic/layout/assets.py` 的 `_collect_asset_color_errors` 检查视觉要求，错误码为 `COMPACT_SVG_FILL_COLOR_MISSING`；CardButton 由转换器自动补色 |
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
| 语法／组件 | 14 |
| 语法／表达式 | 6 |
| 语义／数据绑定 | 2 |
| 语义／跨文件一致性 | 3 |
| 语义／有效能力 | 2 |
| 语义／展示语义 | 28 |
| 语义／布局与视觉约束 | 96 |
| 委托检查，按被调函数内部约束再分类 | 2 |

### 5.1 语法／组件

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

### 5.2 语法／表达式

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

- **OBS-L4139**：`_collect_semantic_text_errors`，主脚本第 4139 行，2026-10-14 已停用。

  历史诊断：component {component.component_id}: calendar eventCount must not be shown as a standalone number or unit. Combine it with its time scope and schedule meaning, for example 未来7天 2项安排, inside the calendar region.

- **OBS-L4153**：`_collect_semantic_text_errors`，主脚本第 4153 行。

  原始诊断：component {component.component_id}: reminder value must keep its minute semantics, such as 提前 15 分钟; do not display a bare numeric reminder value.

- **OBS-L4163**：`_collect_semantic_text_errors`，主脚本第 4163 行，2026-10-15 已停用。

  历史诊断：component {component.component_id}: windLevel must include the metric label 风力, for example 风力 2级; do not show a bare 2级.

- **OBS-L4207**：`_collect_unbound_action_hint_errors`，主脚本第 4207 行。

  原始诊断：component {component.component_id}: action-like Text {text} has no clickable ancestor. Bind the matching event to its action slot or remove the action wording.

- **OBS-L4285**：`_collect_ambiguous_metric_text_errors`，主脚本第 4285 行。

  原始诊断：component {component.component_id}: value {path} has ambiguous meaning ({detail}); add a nearby metric label such as 感冒指数、紫外线指数 or 睡眠得分 instead of showing the value alone.
  2026-10-21 调整为非阻断 warning；继续保留 `COMPACT_DISPLAY_AMBIGUOUS_METRIC`、组件、路径与字段描述，
  但不再加入 `CompactDslValidationError` 或单独触发 Repair。归属仍为 `semantic/display.py` 的展示语义检查。

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

  当前归属：语义／布局与视觉约束，`semantic/layout/geometry.py`。2026-10-15 按确认仅在高度校验
  视图中忽略 2x4 语义展开生成 Column 的 8vp 纵向间距；参考槽位同步使用该视图，其它高度约束不变。
  使用语义来源映射识别，不按任意 ID 前缀豁免；不改变 DSL、A2UI 和 Renderer。2026-10-17 将
  2026-10-20 取消上述纵向 warning 降级：2×2 仅保留整树 `2vp` 数值容差，2×4 不设高度容差；
  超过容差后，只要最小占用及可用高度可确定，根 Column、正数 `layoutWeight` Column 和可压缩
  `itemMargin` 都继续输出 `COMPACT_LAYOUT_HEIGHT_OVERFLOW` error，进入布局容量修复。不改变本项的
  语义／布局与视觉约束分类及实际文件。

  原始诊断：component {component.component_id}: vertical layout requires at least {_format_vp(required_height)}vp within {_format_vp(available_height)}vp; it overflows by {_format_vp(overflow)}vp. Reduce child heights, margins, or gaps instead of relying on clipping, flex shrink, or distributed alignment.

  补漏检查 `COMPACT_LAYOUT_HEIGHT_UNRESOLVED`：语义／布局与视觉约束；实际文件
  `compact_validation/semantic/layout/geometry.py`。Column 可用高度未知且直接子项依赖
  matchParent 高度或正数纵向权重时阻断。归属理由：检查布局分配能否闭合，不检查文本内容或
  组件字段合法性；复用 reference_region_boxes，不复制求解器，保留现有高度溢出检查顺序。

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
- 素材字段的格式与表示：归入语法／组件，保留现有组件规则和转换器委托；来源集合与 SVG 染色检查分别属于有效能力和视觉约束，不等于覆盖所有素材格式。
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
| BASE-04：eventCount 适用边界 | OBS-L4139 曾检查所有 eventCount 引用的时间范围和日程文案 | 硬校验过度约束文案实现，并会阻断仍可读的紧凑结果 | 2026-10-14 已暂时停用；保留 Prompt 指导而不作硬拒绝 |

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

## 10. 当前迁移落点与验证状态

下表对应本次实施后的实际代码；第 5 节继续保留重构前的 153 个观察位置，不将历史行号改为新文件行号。
每项的原函数、当前文件及函数、稳定错误码、旧文案表达式摘要和关联测试见
[规则迁移登记](../../widget_service/tests/fixtures/compact_validation_rule_inventory.json)。
该登记由 `test_compact_validation_architecture.py` 对照实际源码检查，重复旧文案按原输出位置分别登记。

| 分类 | 已结构化的位置数 | 实际规则模块（相对 compact_validation） |
|---|---:|---|
| 语法／组件 | 14 | `syntax/components.py` |
| 语法／表达式 | 6 | `syntax/expressions.py` |
| 语义／数据绑定 | 2 | `semantic/bindings.py` |
| 语义／跨文件一致性 | 3 | `semantic/cross_file.py` |
| 语义／有效能力 | 2 | `semantic/effective.py` |
| 语义／展示语义 | 27 | `semantic/display.py` |
| 语义／布局与视觉约束 | 94 | `semantic/layout/` 下的各职责文件，包括 W1、W9 和布局路由规则 |
| 保留旧字符串路径 | 5 | `api.py` 的两个委托位置；`display.py` 的 BASE-04；`two_by_four.py` 和 `w9.py` 的 BASE-02 |

148 个结构化位置对应 147 个稳定错误码；两处相同的 S4 对象数量约束共用一个错误码。
`flows/hero.py`、`flows/w1.py`、`flows/w9.py`、`flows/two_by_two.py` 和 `flows/layout.py`
只编排跨类别的检查，不直接产生规则诊断。原适用条件、提前返回和交错调用顺序继续保留。
公共事实查询仍按原位置执行，表达式扫描仅在正式扫描位置向全局集合发布诊断。

迁移登记中的 `behaviorCovered` 只表示关联的通过用例直接触发过该错误码，不表示该规则的所有边界均已覆盖。
当前 147 个结构化规则码均已有关联通过用例；保留的字符串位置不冒充已完成结构化迁移。
未来出现 `false` 的位置仍需补充分支用例；静态迁移一致性通过不等同于行为或整条修复链路验收通过。
最新测试结果与待完成事项见[实施与验证记录](Compact_DSL重构实施与验证记录.md)。
# 后置主题阶段补充（2026-10-14）

- `theme_phase_validator.py`：语法／阶段边界。布局颜色字段只接受内部语义角色，最终产物
  不得残留角色；不改变既有组件、事实、绑定和几何判定。
- `semantic/layout/assets.py`：语义／布局与视觉。内部无颜色布局不要求作者提供 SVG 色值，
  由展开器标注角色并在末尾填色；原色素材保留，原素材候选校验仍执行。
- `pipeline.py`：编排。内部布局推迟 quality 对比度检查；末尾主题使用完整发布校验。
- `contrast_validator.py`：质量／视觉对比度。后置主题全幅图片兄弟层无法由祖先底色推导，
  记录渲染复核警告，不伪报默认白底1:1；显式不透明背板恢复确定底色检查。
  2026-10-21：根包装的不透明兜底色位于图片下方，不清除图片场景；仅前景子树的不透明背板
  恢复纯色判定。缺少完整图片包装仍不豁免，阈值与诊断码不变。
  仅识别固定后置图片包装，不改变模板方案及普通纯色/渐变检查，不属于 Compact 布局规则。

## 2026-10-24 关联字段与动态进度来源

| 检查项 | 分类与实际落点 | 归属理由 |
| --- | --- | --- |
| 动态进度必须为已声明数值类型 | 语义／数据绑定，`semantic/bindings.py`；复用 `compact_component_bindings.py` 的组件绑定合同 | 检查绑定源类型；去除 `/__display` 私有路径豁免，沿用 `COMPACT_BINDING_PROGRESS_TYPE` |
| InfoBlock 进度主值的数值来源 | 语义／数据绑定，`semantic/bindings.py` | 复用既有类型检查，以 `COMPACT_BINDING_INFO_BLOCK_PROGRESS_SOURCE` 携带展示路径、登记的 `numericSource` 和精确修复建议；不新增拒绝条件 |
| 进度驱动与展示文字的登记关系 | 语义／数据绑定，`semantic/bindings.py` | 检查同对象同指标关系，不扩展布局或 Plan 编排职责 |
| 完整产物进度引用首帧副本或非数值来源 | 公共绑定校验，`card_validation/progress_sources.py`，由公共 `BindingValidator` 调用 | 基于原始依赖和声明判断动态来源；代码 `BINDING_PROGRESS_SOURCE_INVALID`；转换后及保存前复用同一判定 |

关联字段补齐属于预检编排，位于 `related_output_fields.py`，注册关系由能力模型验证；不加入 Compact 语法或布局规则。
模板仍可跳过 Compact 专项，但不能跳过转换后及保存前的动态数值来源门禁。进度错误修复建议保留在现有提示词与建议配置中。
测试见 `test_related_progress_sources.py`、转换器/绑定合同回归及浏览器预览连续数据更新测试；不新增端侧字符串转换函数或派生数据协议。


## 2026-10-25 开域静态容量反馈、名称与展示覆盖修订

| 检查或行为 | 分类与实际文件 | 理由与边界 |
| --- | --- | --- |
| identity形状、shared为null、新提交显式键、displayRole别名 | Plan合同，compact_plan.py | 模型提交的展示规划，不推断用户语义；动态工具不扩字段，历史解析保持兼容 |
| 同对象名称可见、带标签字段完整覆盖、完整字段换序 | 语义／展示，semantic/static_content.py | 检查接受计划的落实，复用对象分组读取与COMPACT_STATIC_CORE_MISSING；不复制布局、来源或语义理解 |
| 数字和ASCII词元边界、逐字要求 | 语义／展示，同上 | 防止部分读数或单字集合误覆盖；名称、单位与必要限定不能跨对象补齐；原文约束不放宽 |
| 有界试排无命中时的反馈 | 候选构造static_content_presentation.py、传递compact_plan.py、编排widget_generation_service.py | 仅反馈有限候选失败，在原两次Plan预算内修订，不新增校验拒绝或模型阶段 |
| compact区块间距、无label属性与辅助说明行盒 | 展开static_content_components.py、compact_semantic_layout.py；共享合同static-content-v1.json | 等字号使用登记行盒，不放宽实际宽高门禁，动态布局合同不变 |

修复说明继续由静态repair提示词承载，既有错误分类与诊断码不变；不在入口重复实现检查。
回归位置：test_static_content_contracts.py、test_static_content_generation.py、test_static_content_quality.py。


2026-10-25 字号档位修订（用户允许最小10）：参数枚举属于静态组件合同，沿用
static_content_components.py的参数展开检查，不向公共入口或动态组件添加判断。
12/11/10字号及对应行盒、配置引用完整性归static_text_capacity.py与共享静态运行合同；
实际宽高继续由semantic/layout/text_capacity及原布局校验负责，后置冻结检查不变。
候选排序归static_content_presentation.py，修复说明只改repair_hints.json中的静态容量诊断项。
不新增业务关键词、正则分流或诊断码。回归：test_static_content_contracts.py的档位下限、
标题层级、完整内容先于省略，以及test_static_content_generation.py的11字号容量恢复。


## 2026-10-25 英文边界、静态标题及遗漏对账

| 检查项 | 分类、实际文件 | 归属理由 |
| --- | --- | --- |
| 英文名称与读数词元边界 | 语义／展示，semantic/static_content.py | 对已冻结展示文字做局部覆盖，保留分隔后的词元边界；身份不使用词序重排或词片段拼凑，沿用核心缺失码 |
| 属性可见文字与角色元数据隔离 | 语义／展示，同上 | 只收集label/value，valueRole不得补充事实覆盖 |
| flow/compact的实际间距匹配 | 语义／布局合同，compact_layout_runtime.py | 两个模式都从静态运行合同登记；原动态合同保持不变，不放宽任意几何 |
| 静态标题完整行盒、图标占宽、超宽拒绝 | 静态组件参数及共享容量展开，static_content_components.py；分支接入compact_high_level_components.py | 在既有静态组件展开单一位置检查，复用require_static_text_capacity；旧动态标题配方不变 |
| 引用式遗漏的类型、范围、去重映射与核心保护 | Plan合同，compact_plan.py | 仅解析模型声明，不推断业务语义；最终遗漏继续复用static_fact_coverage，不在入口再做覆盖判定 |
| 省略后恢复及实际遗漏消息 | 既有compact_plan_omitted_facts格式化 | 候选声明不是实际遗漏；无保护should确实缺失才报告，历史自由声明保守兼容 |
| 左右对齐与通用标点禁则 | 静态展开与共享文字度量，static_content_components.py、static_text_capacity.py | 模型显式角色决定对齐；标点只用于排版，全部行盒仍经过正式宽高检查 |

候选构造与guided试排归static_content_presentation.py，不复制判定；静态提示词负责模型说明。
复验包括英文完整词/反例、两尺寸flow与compact、标题裁切拒绝和替代组织、事实引用恢复/省略、
去重与保护、对齐元数据不计可见文字，以及真实超容量失败。新诊断码为零。

## 2026-10-27 阶段输出、Plan反馈与静态候选优化

| 检查或行为 | 分类、实际文件 | 归属理由 |
| --- | --- | --- |
| 错误阶段对象、组件头类型先于兼容修复 | 语法／协议与组件，共享解析器compact_dsl_a2ui_converter.py | 复用原解析责任及转换异常，不在Compact入口复制检查，不从Plan内部数组猜测DSL |
| 静态分组引用与来源结构问题汇总 | Plan合同，compact_plan.py；来源判定复用semantic/cross_file.py | 校验本次模型提交结构，准确路径及范围不新增语义判断；既有拒绝条件保持 |
| Plan JSON位置及修复说明 | compact_plan.py解析反馈、prompt_builder.py模型说明 | 不补造JSON内容或索引，静态修复保留忠实摘要权限，重试编排不变 |
| 共享标题位置的有限候选 | static_content_presentation.py | 只构造已有合法结构；覆盖及实际容量继续委托原展示与布局规则，不复制判定 |

回归由test_static_content_reliability.py覆盖，并执行既有静态、转换器、Plan与生成链路回归。
不新增Compact诊断码，不修改语义展示、容量阈值或动态合同；未涉及历史待裁决规则。

## 2026-10-28 静态组件单行省略号

| 检查或行为 | 分类、实际文件 | 归属理由 |
| --- | --- | --- |
| TextList 主副文字单行省略号与可收缩几何 | 静态展开，`static_content_components.py`；运行合同 `static-content-v1.json` | 展开器保留完整文字，产生单行省略号和最小宽度约束；不由校验器截断内容 |
| 有值时保留右侧宽度、无值时主文字占满 | 静态展开，`static_content_components.py` | 属于组件内部几何；值区按实际文字宽度固定且不收缩，不猜测端侧卡片尺寸 |
| 已登记 TextList 省略号的宽度溢出 | 语义／布局与视觉，`semantic/layout/text_width.py` | 只对 `static-content-v1:TextList.` 运行配方降为 warning；不接受模型自行声明省略号来绕过通用宽度门禁 |
| TextList 省略配置完整性 | 静态运行合同，`static_text_capacity.py` | 校验共享配置必须为主副文字登记 `ellipsis`，避免配置与展开行为漂移 |
| ComparisonGroup 四项宫格主副文字单行省略 | 静态展开，`static_content_components.py`；运行合同 `static-content-v1.json` | 只在四项 2×2 宫格使用登记的单行省略策略；`details` 不放宽 |
| ComparisonGroup 两到三项次文字两行省略 | 静态展开，`static_content_components.py`；运行合同 `static-content-v1.json` | `secondaryText` 保留完整原文、最多两行，超出由端侧省略；`primaryText` 仍须通过完整文字容量校验 |
| 已登记 ComparisonGroup 省略的宽度溢出 | 语义／布局与视觉，`semantic/layout/text_width.py` | 仅运行展开生成带 `static-content-v1:ComparisonGroup.` 配方的省略属性，降为 warning 不改变模型字段合同 |
| EmphasisText 次文本三行省略 | 静态展开，`static_content_components.py`；运行合同 `static-content-v1.json` | 保留完整原文和实际1–3行高度，超出由端侧在第三行省略；`mainText` 的两行合同不变 |
| 已登记 EmphasisText 次文本的宽度溢出 | 语义／布局与视觉，`semantic/layout/text_width.py` | 只对 `static-content-v1:EmphasisText.secondaryText` 配方降为 warning，不影响主文本或动态 EmphasisText |

本次不新增诊断码，不改变文字宽度阈值、值区容量、未登记配方或动态组件的错误级别。
回归位于 `test_static_semantic_components.py`，覆盖 TextList 有值不遮挡、无值占满，ComparisonGroup
四项宫格的主副文字单行省略、两到三项的次文字两行省略，以及 EmphasisText 次文本的实际行高和三行省略。

## 2026-10-28 静态 SingleLineList 容量修复与受控 Drop

2026-10-31 静态标题履约归语义／布局合同：`static_content_layout.requires_static_header`登记
仅三项TextList可无标题，`compact_semantic_layout`展开静态外框时检查可达header/SingleLineTitle。
原校验入口与最终转换共用展开，不复制覆盖或几何判定；缺标题不属于容量超限，不授权Drop。
不合成模型标题、不改变字号、安全区、单行背板尺寸或间距，动态路线不变。

| 检查或行为 | 分类、实际文件 | 归属理由 |
| --- | --- | --- |
| SingleLineList 完整单行容量失败 | 语义／布局与视觉，`semantic/layout/text_capacity.py`、`static_content_components.py` | 继续使用既有 `COMPACT_STATIC_TEXT_CAPACITY`，不新增检查或放宽单行合同 |
| 改用 TextList 的修复指导 | 修复策略，`compact_repair_strategy.py`；提示源 `static_content/repair.md` | 仅在静态容量错误且失败源使用 SingleLineList 时追加；未授权时不允许模型自行删减 |
| 超出记录逐轮删减 | 计划／Drop 候选，`compact_plan.py` | 保持 should 优先、must 兜底和每轮一事实授权；允许移除只含一条事实的对象，但整卡至少保留一个正文对象 |

修复只在一轮无损容量尝试仍失败后进入既有静态 Drop；保护原文、Action、
未授权事实和最后一个正文对象仍为阻断边界。

## 2026-10-29 静态容量恢复与事实定位

| 检查或行为 | 分类、实际文件 | 归属理由 |
| --- | --- | --- |
| 既有候选失败后的有限换型与公共说明承载 | 生成恢复，`static_content_presentation.py`、`generation_pipeline.py` | 只组合已有静态组件；原候选及已成功输出优先，原模型调用与重试预算不增加 |
| 新恢复候选全文能否容纳 | 共享展开，`static_content_components.py` 复用原 `require_static_text_capacity` | 请求作用域内检查实际字段宽度和固定行数，不能靠省略号把新候选判成全文恢复；正常组件的既有省略号样式不变 |
| 显式展示方式与旧组件提示的优先关系 | 语义／布局，`semantic/layout/text_capacity.py` | 已接受的显式展示方式决定记录组织，不再由旧 TextList 提示覆盖；真正生成 TextList 时仍执行原项数上限 |
| 当前容量错误的证据与定位 | 修复编排，`compact_repair_context.py` | 复用共享度量重新核对当前字段；字段超宽只定位该字段，纯项数上界定位当前列表；空字段、项数下界和未知位置不授权删除 |
| 定位字段与所属事实对应 | 语义／展示，`semantic/static_content.py` | 复用已有对象顺序和完整事实覆盖，累计批准参与映射；不跨对象猜测同值事实，不把批准等同于实际遗漏 |
| 一次无损容量修复后的逐条 Drop | 修复编排，`compact_repair_strategy.py`、`compact_plan.py` | 只对证据范围内事实沿用 should 优先、低顺位 must 兜底；前一次授权未落实不追加，语法修复不算无损容量尝试 |
| 静态恢复前完整文字存在性 | 语义／展示元数据，`semantic/static_content.py`；恢复编排消费于 `compact_plan.py` | 复用单条可达展示的原匹配；只防止将错组但完整存在的事实排除，不改变 visible 或通过规则，不跨展示条目拼词 |
| 恢复事实范围的提示交接 | 提示编排，`prompt_builder.py` | 静态恢复完整传递已有账本，与原严格事实校验一致；首次及动态提示、重试预算不变 |
| 撤销省略授权后的真实损失反馈 | Plan 标准化与实际遗漏，`compact_plan.py` | 全部索引有效而因 must/保护被拒时只留诊断，由最终覆盖报告真实损失；未知引用和历史无索引说明保持保守反馈，不凭描述推断事实 |
| 静态分组错误与展开容量联合反馈 | 调用编排，`compact_validation/api.py`；原容量诊断仍归 `semantic/layout/text_capacity.py` | 仅已通过源语法及组件类型检查、存在静态分组错误的源继续一次既有组件展开；分组错误仍阻断，补充展开器独立确认的原容量诊断，不复制容量判定。未知转换异常保留原文及 cause，不伪装容量；其它原错误提前返回及无原错误路径不变 |
| 公共文字补齐候选的同源修复交接 | 失败候选构造，`static_content_presentation.py`；调用编排，`generation_pipeline.py` | 既有试排全失败后，原正文全等且原分组覆盖缺失消失的单一候选继续原完整检查；只剩可独立识别的当前容量错误时原子交接候选源和诊断，不混入原稿错误、不更改 Drop 判定或授权 |

不新增错误码、字号档位、几何阈值或预算。纯整卡高度但缺少可靠当前事实定位的诊断仍进入原修复，
不凭错误字符串给无关事实新增删除许可；有限候选未找到解不代表所有合法排版均不可行。
Plan 试排原有的无保护 should 省略候选保持原优先级与遗漏反馈，不能把这种省略称作完整恢复。
联合反馈的自包含回归位于 `test_static_validation_joint_capacity.py`，覆盖公共说明缺失与真实单行超宽、
未知转换异常、布局错误不重复、仅其它原错误提前返回以及静态／非静态无原错误路径；不增加修复预算或省略授权。

### 同组件数值和单位的 Plan 覆盖

`compact_plan.py` 的既有结构化静态文字收集补充可达 `EmphasizedData` 的合法静态 `value+unit`，
归入 Plan 语义／信息覆盖，与同条 `SecondaryBody` 标签和值的组合遵守相同边界。
不跨节点、跨条目拼接，不执行动态表达式，不改写数字、单位或错误级别；无单位、数值或单位不匹配仍按原规则判断。
回归扩展已有 `test_compact_plan.py`，同时核对原转换结果不变；不新增几何检查、诊断码或重试权限。
