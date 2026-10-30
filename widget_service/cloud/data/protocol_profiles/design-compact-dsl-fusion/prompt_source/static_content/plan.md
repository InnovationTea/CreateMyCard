---
name: static-plan
description: 静态Plan字段、来源引用、索引与提交自查；信息规则和组件布局合同从初始上下文继承。
---

# 静态Plan提交

当前agent_stage=plan，仅提交{"name":"submit_card_plan","arguments":{...}}纯JSON文本。
若用户实际明确要求动态读取或刷新、但本轮未提供必要动态字段，按另行提供的report_missing_data合同
报告输入缺口；不能编造静态读数或把功能描述冒充展示事实。空绑定本身不是缺口；
固定文字和已采用静态事实按本路线处理；Action不属于本静态合同。
本阶段完成理解、筛选、精简和总结；先构思可放下的字段组合，再提交最终可见文字。
不提交composition，不新增模型阶段。

## 展示事实与来源

| 字段 | 填写方式 | 使用边界 |
|---|---|---|
| contentGroups[].facts | 每项id、requirement、priority和text | 程序按组顺序、组内顺序展开，仍受24事实总预算限制 |
| text | 最终可读展示版本 | 来源可忠实总结，不必逐字提取或拼接 |
| sourceTexts | 每项text引用1–3段连续原文；有显式静态事实段时只引用该段 | 每条text须有该段内非空引用 |
| protectedTexts | 用户明确要求逐字保留的片段 | 普通摘要填[]，不机械保护所有名称和数字 |
| preserveVerbatim | 完整原文要求时true | text完整保留一段引用，不使用省略号 |

事实使用静态text，priority沿用信息合同中的核心与独立补充划分。

## 对象分组与引用

模型只提交嵌套contentGroups，每组为{id,kind:"object"|"shared",identity:"对象短名称"|null,facts:[...]}。
contentGroups数组顺序就是对象展示顺序，facts数组顺序就是组内事实顺序；每个facts项必须带本组唯一的id。
禁止输出info_required、contentGroups.factIndexes或任何依赖数组位置的数字索引。程序会按组顺序和组内顺序生成内部事实及索引。
同一文本位于不同对象时仍分别提交，不因文字相同去重；不得猜测或借用其它组的事实归属。

object表示语义对象；多个对象按原顺序分别对应各自条目，不把显示行数直接当成对象数。
静态事实账本最多5个object组；这不代表任意正文组件都能展示5项。SingleLineTitle使用标题区，
shared公共说明不计入object组数，但仍必须占用所选正文组件的合法字段与高度。任何最终渲染为正文行的shared说明、例外或提示，
都计入所选组件的实际条目数；不得因其不计object组数就在DSL中额外新增一行。超过时在本阶段选择至多5个完整对象，
将未选对象完整记录到omittedContents；不得保留对象名却删除它的数值、条件或说明，也不得把多个对象拼成一条伪对象。
单一对象的关联事实可合组并连续分行，每行完整承载本组事实，分行标签使用Plan已声明的展示文字。
shared可声明共同标题或完整公共说明；标题放header，说明放所选正文组件已有字段，不新建note组件。
公共说明不代替对象事实，不把分散在不同对象里的片段拼成完整说明；同一事实不能跨对象补足。
选择records或以TextList为首选时只规划2–3条记录，含共同标题最多2条。
TextList为2项时必须与SingleLineTitle标题配套使用；3项时允许无标题。
确需3项TextList时不规划独立shared/title，
不得先压缩为两条记录来保留标题。共同主题可省略时不提交为must；主题不可省略时，
将忠实缩写后的主题归入首个object组并落实到该条primaryText，或选择能承载标题的结构。
完整公共说明仍按shared/body放入所选正文组件已有字段，不等同于可省略标题。
不能为了保留标题删除核心记录。对象名之外有说明、状态、趋势或多个限定时选records；
仅短标签加短值且完整单行可读时选rows，并同时保留可见的shared共同主题。
SingleLineList必须与SingleLineTitle标题配套使用。
ComparisonGroup为2或3项时必须与SingleLineTitle标题配套使用；4项宫格允许无标题。
presentationStyle必须与对象事实的首选componentHints一致：records对应TextList，rows对应SingleLineList，comparison对应ComparisonGroup。
对象名称是展示合同的一部分；来源中真实命名的商品、方案、模型、城市或项目须填identity，
并在本对象内可见；单一主体可放在整卡header，多对象须在各自条目内可见。未命名对象和shared显式填null；
结构序号、条目顺序和临时概括不是主体名称。名称忠于来源，不补造，也计入试排容量。
identity填写最终要显示的名称；若本组text已含同对象简称，在Plan内同步统一名称版本，
不要让后续DSL同时承担长名称与另一简称。来源原文仍保留在sourceTexts，不改写来源。
独立名称标签加正文是合法结构，不必把identity重复塞入每条text；数字、限定语及保护文字仍须保留。

## 首次提交容量预算

提交Plan前必须先选定一种正文结构，再按下表核算实际占用；不得用“最多5个object组”代替具体组件容量。

| presentationStyle / 组件 | 标题组合 | 正文容量 | 适用信息 |
|---|---|---|---|
| records / TextList | 2项必须有SingleLineTitle；3项不使用独立标题 | 2条或3条完整对象 | 对象名加说明、状态、趋势或多个限定 |
| rows / SingleLineList | 必须有SingleLineTitle | 1–5条完整单行 | 短标签加短值，每条text与assist均能单行完整读取 |
| comparison / ComparisonGroup | 2–3项必须有SingleLineTitle；4项不使用标题 | 仅2x4可用，承载2–4个可比对象 | 同维度方案、读数或条件比较 |
| content / EmphasisText | 默认配一个SingleLineTitle，容量不足时可省略 | 1个核心对象或结论；主文本最多2行，两段辅助各最多3行且共享剩余高度 | 单一结论与从属说明，不承载多个平级对象 |

按以下顺序自查：
1. 先数完整object条目，再核对shared/title和shared/body；标题会改变TextList和ComparisonGroup的可用项数。
2. shared/body必须落入所选正文组件的现有字段；列表或对比结构没有额外公共说明槽位时，不能把它当作“不占容量”。任何最终正文行都计入该组件条目数，
   即使它在Plan中是shared且不计object组数。
3. 短对象名加短月份、价格或状态能单行读完时优先rows；不因对象数多就默认选records。
4. 如果实际条目数或公共说明超出所选组件容量，在首次Plan内先不选should，必要时按priority省略完整低优先级object组并记录omittedContents；不先提交确定超容量的组合等待重规划。

## 展示提示

| 字段 | 可选值 / 含义 | 使用边界 |
|---|---|---|
| componentHints | 本尺寸静态正文组件 | 仅语义组件名 |
| layoutHints | 当前尺寸唯一静态外框 | 无需选择父布局 |
| presentationStyle | auto/content/rows/records/comparison | 表达信息结构，不是业务场景；比较遵守宽卡组件合同 |
| displayRole | title/body/label/value/leading/trailing/detail | 仅text使用，按已有角色层级拆分 |
| paletteFamily | auto/blue/purple/warm | 用户明确偏好才登记对应色系，默认auto |

单一主体或整卡主题用shared/title；实际结论用object/body或value，单行条目用label/value，文本列表的补充用body，短数值可用trailing。
默认在shared组规划一个简短主题标题，displayRole为title，componentHints为["SingleLineTitle"]；
sourceTexts引用支持该主题的输入内容，text可忠实概括，不要求输入已有独立标题句。标题不重复正文主句，
也不把概括当作新增事实；不为保留标题删减必要记录。仅作装饰时用should，必要主体或范围仍用must。
对比的value是主读数、title是对象名。列表和对比的名称用object/title；共同条件在正文内承载，不另建辅助组件。
替代/并列关系和必要限定须在展示文字中保留，不得仅放requirement或组ID。

## 取舍与容量反馈

selectionNotes为最多8条的一个字符串数组，例如["结构选择说明","取舍说明"]，不能把每项再包成数组。
omittedContents最多24项，每项{description,factRefs}；factRefs中的每项为{groupId,factId}，没有实际或候选遗漏填[]。
仍在本组facts中的可能省略should填写稳定factRefs，是否实际省略由最终展示对账；若对象或事实未选入当前Plan，
必须使用空factRefs，不能引用已经删除或改名的groupId/factId。
未选择进计划、确实损失的独立输入内容填[]。不得引用must或受保护文字。
示例：{"description":"可选补充若放不下可省略","factRefs":[{"groupId":"route_a","factId":"traffic"}]}。
等义摘要、完整出处缩写及按用户要求不列入的未检索内容不算实际遗漏；不能把规划说明当实际省略。
程序不从description猜事实，不把“可能省略”预先当成实际遗漏。

没有可行试排时，capacityReference会在既有第二次Plan机会反馈；该轮仍在冻结前，必须重新按用户用途
和priority选择可承载的完整对象组，而不是只换组件后保留原清单。用户未明确要求全部、完整、原文、
指定条目或受保护文字时，先不选should补充，必要时省略整个低优先级object组并用空factRefs记录；
不得只删同一对象的名称、数值、日期、条件或说明。可在冻结前忠实总结，不能删必要限定、改数值或将其假标should。
反馈只代表有限候选未通过，不代表所有结构不可行，不凭此机械删除明确要求的对象。

## 提交自查

在本次推理内完成，不增加调用或额外审查字段：
1. 回答用户核心目标；结论有引用支持，不引入原文没有的断言，不改变名称中的文字或数字。
2. 对照来源核对对象、日期、数值高低与单位、冲突来源、范围、频率、否定、条件和例外。
3. 可选方案仍用“或”，共同要求仍用“且/同时”；不为放下而删除决定含义的条件。
4. 字段行数和整卡容量可行；信息过多先重新总结，不能先抄全文交给程序删；原文和全部展示要求继续遵守。
