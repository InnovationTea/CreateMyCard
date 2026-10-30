---
name: static-components
description: 组件触发条件、语义字段及单组件示例；样式由Runtime合同维护。
---

# 组件

## 总表

| 组件 | 适用条件 | 承载内容 | 使用边界 |
|---|---|---|---|
| SingleLineTitle | 概括整卡的共同主题 | title、可选icon | 优先放置主题或主体名称，不与正文重复 |
| TextList | 两到三条各有主副信息的记录 | items[].primaryText、secondaryText、可选value | 2项必须带SingleLineTitle；3项允许无标题 |
| SingleLineList | 每项一行可完整表达 | items[].text、assist | 必须与SingleLineTitle标题配套使用；最多5项 |
| EmphasisText | 一项核心结论及其从属说明 | mainText、可选secondaryText与bottomText | 围绕同一对象或结论 |

## SingleLineTitle

### 选择条件
用于输入用途或内容的简短共同主题，也可承载单一主体名称；对象名已在正文完整出现时不再复制为装饰标题。
### 语义字段
title为非空短标题；icon为可选的合法素材引用。
### 示例
```genui
["header","SingleLineTitle",{"title":"阅读计划"}]
```

## TextList

### 选择条件
每个对象都有明确名称和一条必要说明，需要逐条查看；一项内部的主副信息不能拆散给别项。
对象名之外还有状态、说明、趋势或多个限定时优先本组件；对象名、主读数与状态并存时，
主读数放value、状态放secondaryText。TextList为2项时必须与SingleLineTitle标题配套使用；3项时允许无标题。
确需三项时不使用标题，让正文使用完整高度。共同主题若不可省略，在Plan中并入首条或改用其它可承载标题的结构，
不能生成标题加三条TextList。
### 语义字段
items为2–3项，每项primaryText与secondaryText必填，value可选，只放本项短数值。
### Runtime规则
按Design System v16 4.8：主文本12/16、500；副文本10/13、400；数值12/16、500。
主副间距4，数值与主副组合间距12；分割线1px，末项自动隐藏。
两项采用线前/线后各12的间距，三项各6；含标题区时最多两项。
primaryText和secondaryText固定单行，超出可用宽度时显示省略号。有value时先为右侧完整value预留宽度；
没有value时主副文字使用正文可用行宽，仍在超出一行后显示省略号。
### 示例
```genui
["body","TextList",{"items":[{"primaryText":"示例公园","secondaryText":"建议2小时","value":"免费"},{"primaryText":"示例展馆","secondaryText":"建议1小时","value":"20元"}]}]
```

## SingleLineList

### 选择条件
若干短标签与对应内容，每项都能在一行内完整理解；不把长段落、趋势或多个限定压成右侧窄栏。
只有“短标签 + 短值”这一层语义时使用，且必须与SingleLineTitle标题配套使用；没有可展示的共同标题时改用其它正文组件。
若右侧需要解释状态、条件或多段信息，或记录名、右侧内容无法完整单行显示时，
仅在记录数为2–3、含标题最多两项且主副字段均能承载时，才改用TextList。
条件不满足时不要机械换型；生成时按同一对象关系选择其它已登记组件，修复时保持已接受分组及必要公共标题。
### 语义字段
items为1–5项，每项text、assist必填；assist可为文字或数值，数值仍需有可理解的标签与单位。
### Runtime规则
按v16 4.9：左侧12/16、400、次要色，右侧12/16、500、主要色；垂直居中，右侧右对齐。
外观、逐项间距及分布由Runtime提供；完整单行及总高度均须成立。
### 示例
```genui
["body","SingleLineList",{"items":[{"text":"最晚入场","assist":"16:30"},{"text":"须知","assist":"请携带有效证件"}]}]
```

## EmphasisText

### 选择条件
mainText突出实际结论、状态、读数或任务内容；整卡主题和主体名称交给SingleLineTitle。
secondaryText解释这个结论；bottomText补充条件、提示或来源。不把标题或对象名称再放到强调位置。
### 语义字段
mainText必填，secondaryText与bottomText可选，均为静态文字。不用主文本塞入全部事实。
### Runtime规则
主文本最多两行；两段辅助各最多三行，超出后沿用辅助文字省略策略，仍须共同满足整卡高度。
Runtime将主文本左上对齐；只有一段非空辅助时放左下；两段都有时secondaryText紧随主文，bottomText左下。
字体、间距与对齐均由Runtime提供。
### 示例
```genui
["body","EmphasisText",{"mainText":"证件和充电器随身携带","secondaryText":"出发前检查"}]
```
