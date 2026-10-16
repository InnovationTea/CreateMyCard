---
name: card-plan
description: 工具字段、事实粒度、优先级与软候选；不重复组件选型表、布局目录或修复预算。
---

# 信息计划

<!-- prompt:contract -->
# Compact Info Plan

当前阶段为 plan 时，按本轮工具 Schema 提交一个完整 `{"name":"submit_card_plan","arguments":{...}}` 对象，不输出 DSL。仅填写 Schema 声明的字段。

## 1. 必要事实 info_required

每项一个原子事实，简短 requirement 描述用途，并恰选一个来源：

| 来源 | 填写方式 |
|---|---|
| dataId | 本轮工具列出的真实动态字段 ID，不改名、不把样例改静态 |
| actionId | 用户要求的真实操作 ID，参数不是额外正文事实 |
| text | 用户明确要求展示的原文连续片段；编辑时可取上一版可见静态正文 |

text 不重排、不改写；概括性装饰标题由 DSL 按需生成，不加入硬事实。修复来源时恢复真实原文，不删除用户要求。号码、地址或链接若仅用于事件传参，不增加展示事实；用户明确要求显示时才同时保留。
用户要求集合多项时，逐项覆盖每个必要成员的字段；一个 `/0` 字段不能代表其它数组成员。对象名称、数量、时间范围及各组成项按真实展示需求核对，不因候选存在全选，也不因已进入事件参数漏掉明确展示需求。

priority：所有 Action、核心及不可缺少的事实为 must；省略不改变卡片主要用途的补充为 should。用户提及不自动等于 must，也不因保守全标 must。正常生成和无损修复仍保留全部 must/should；删除只由后续修复反馈明确授权，Plan 不自行删减。Action 始终不可删除。

## 2. 实现偏好

| 字段 | 要求 |
|---|---|
| componentHints | 按优先级1–3个当前尺寸合法组件，不凑数；必须有可承载该事实的真实 Prop |
| layoutHints | 至多两个正式父布局，能容纳全部事实与动作；不确定可省略 |

先判断事实在同组中是主值、标签、单位、补充还是事件要素，再推荐组件。多个事实推荐同名组件可表示同一实例的多个属性，不表示逐字段创建组件；不同对象也不因同名混组。语义、类型、容量都成立时落实首选，不成立可改选，候选不冻结数量、区域或几何。
dataId/text 不推荐按钮，actionId 仅推荐合法动作组件。标题按标题合同，事件要素合到一个 EventCard item，多事件合一实例；不向 location 塞状态。比例、多段时长、完整单焦点、正文辅助等选择执行组件合同，不用大数值组件承载普通长文本。
2x4 含 actionId 时不推荐无合法动作槽的 W-top-bottom。2x2 图标操作只有满足 CircleButton 的全部条件才首选 S-title-anchor，缺独立支撑事实时排除它；不能为偏好某布局增造事实。

## 3. 素材分配（仅 Schema 含 assetAssignments 时）

actions 按 info_required 动作顺序逐项选择匹配 assetId；无匹配填 null 及具体 reason。之后 title 从未用且语义匹配的候选中选择；有匹配不能仅以“装饰/空间紧张”填 null。一个素材只分配一次，不牺牲准确按钮图标为标题腾素材。容量计入所选标题是否带图标的实际高度。

## 4. 实例安排（仅 Schema 含 composition 时）

- layout/variant 选择一个完整合法父布局及从1开始的变体；动作数适配。
- regions.path 使用从 root 开始的实际子序号；referenceWidth/referenceHeight 是扣除内边距和动作后的真实容量，不输出固定几何。
- groups 每项代表一个组件实例。factIndexes 为 info_required 的0起始索引；placements 逐项对应真实可见 Prop，如 items[0].value、title、label。
- 同一事件要素在同一 item；同一进度事实可重复索引对应 value/displayValue，但不增重复 info_required。静态单位不占事实索引，独立单位字段才有自己的索引。
- 装饰 SingleLineTitle 可用空 factIndexes/placements，仍计高度；其它组件不得空事实。各事实和动作落在唯一正确对象，不能在父区和子区重复安排同一槽。
- 填实际 component 及必要 variant/density/columns/lines/labelLines，按组件规格和布局预算合计。双列分别放下完整标签和值；长值用合法单列/多行。SecondaryBody 仍须搭配整卡核心组件。
- 必填 Props、角色数及全部事实齐全；S-title-anchor 独立支撑不能为零，TextBlock 一个实例须承载所分配的2–4项。任一区 remainingHeight 为负则重组，不靠权重、缩字或遗漏闭合。

提交前核对：事实来源准确、原子项无遗漏、不重复；候选实际可承载；完整序列化 name/arguments，不在已闭合对象后追加重复括号。
<!-- /prompt:contract -->
