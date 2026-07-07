---
name: harmony-card-dsl-validator
description: "校验 HarmonyOS A2UI Form 服务卡片 DSL、genui JSONL 和 cardspec 结果。用于用户提供模型生成的 DSL/CardSpec 后，定位 JSON 语法、消息顺序、surface、catalog、组件属性、children 引用、DataModel 绑定、表达式、onClick 行为链、CardSpec 数据契约、2x2/2x4 布局、美观度和卡片生成 skill 遵循情况的问题，并给出可执行修改建议。"
---

# HarmonyOS A2UI Form DSL 校验

## 目标

对用户提供的 HarmonyOS A2UI Form 卡片产物做校验。产物可能是：

- `genui` JSONL 消息流。
- `cardspec` JSON。
- 两者组成的完整卡片结果。
- 裸 JSONL、代码块、局部组件树或错误日志。

校验目标不是只判断“能不能解析”，还要帮助定位为什么模型生成结果不符合协议、为什么落地风险高，以及如何修改生成 skill 或本次 DSL。

## 必读参考

先读本文件。按任务需要再读取：

- 日常校验必须优先读取：[`references/validation-rules.md`](references/validation-rules.md)。
- 需要协议依据、组件/表达式/事件细节时，读取精简摘要：[`references/form-protocol-summary.md`](references/form-protocol-summary.md)。
- 只有当摘要和规则仍无法判断、用户要求“按原文核对”、或需要查完整表格/示例时，才读取完整原文：[`references/harmonyos-a2ui-form-protocol-full.md`](references/harmonyos-a2ui-form-protocol-full.md)。

不要默认读取完整原文。完整原文较长，主要作为争议兜底，不作为日常校验上下文。

如果用户明确说“按 CreateMyCard 生成 skill 校验”或产物来自 `$harmony-card-generation`，同时按生成 skill 的更严格约束检查：禁用表达式、模板只使用 `{componentId,path}`、CardSpec 只引用已声明 data capability、点击只引用已声明 event capability。

## 快速流程

1. 提取用户输入中的 `genui` 与 `cardspec`。优先使用 fenced code block；没有代码块时，把每个非空行视为 JSONL。
2. 如可运行脚本，先用 [`scripts/validate_genui.py`](scripts/validate_genui.py) 做静态检查：

```bash
python scripts/validate_genui.py input.txt
```

也可以从 stdin 读取：

```bash
python scripts/validate_genui.py - < input.txt
```

3. 读取 [`references/validation-rules.md`](references/validation-rules.md) 和按需读取 [`references/form-protocol-summary.md`](references/form-protocol-summary.md)，根据脚本结果做人工复核。脚本只能抓结构性问题，不能替代协议语义、动态能力和视觉质量判断。
4. 输出问题清单，按严重度排序，并给出改法。不要只说“不符合协议”，要指出具体字段、组件 id、消息行或路径。
5. 如果用户希望修复 DSL，给出修复后的 `genui` 和 `cardspec` 代码块；否则只给诊断和建议。

## 严重度

- `P0 阻塞`：JSON 无法解析、消息形状错误、surface 无法创建、组件树不可解析、使用不支持组件、必需属性缺失、CardSpec 与 DSL 不一致等会导致无法渲染或无法执行的问题。
- `P1 高风险`：协议允许但落地可能失败或违背当前生成 skill 的问题，例如未声明点击函数、未声明数据能力、表达式复杂/不稳定、路径无法由 DataModel 推导、关键内容截断。
- `P2 建议`：能渲染但质量差的问题，例如信息过密、主焦点不清、2x2/2x4 选择不合理、CTA 不明显、颜色/层级/间距不协调。
- `P3 提示`：风格、可维护性或生成 skill 优化建议。

## 必查项目

- JSONL：每行一个 JSON object；`version` 为 `"v0.9"`。
- 消息：`createSurface`、`updateComponents`、`updateDataModel`/`deleteSurface` 形状正确；Form 卡片通常只应有一次完整 `updateComponents`。
- surface：`surfaceId` 一致；`createSurface.catalogId` 为 `"ohos.a2ui.extended.catalog"`；`createSurface` 不含 `theme`。
- 组件：只使用 Form 支持组件或明确 catalog 注册的自定义组件；默认支持 `Text`、`Image`、`Divider`、`Progress`、`Button`、`Checkbox`、`Row`、`Column`、`List`、`Stack`。
- 属性：使用 extended 属性名，如 `Text.content`、`Image.src`、`Button.label`；不要混用 `Text.text`、`Image.url`、`Button.child`、`Button.action`。
- children：组件树是扁平邻接表；`children` 字符串引用能解析；模板 children 只用于 `Row`、`Column`、`List`。
- 事件：Form 只支持 `onClick` 通用事件；EventHandler 数组非空；每个 handler 有 `call`；`call` 是函数名，不是表达式。
- DataModel：`updateDataModel.path` 是 JSON Pointer；绑定路径和模板路径能从 DataModel 或 CardSpec 输出推导。
- 表达式：最终落地协议允许表达式，所以不要把 `{{ ... }}` 一律判为错误；但要提示当前生成 skill 默认禁用表达式，并检查表达式完整性、作用域、长度、嵌套、多表达式拼接和 `$__widthBreakpoint`/`$__colorMode` 禁用项。
- 媒体：`Image.src` 与 `styles.backgroundImage` 不应使用网络 URL、SVG、占位图 URL 或未声明资源路径。
- CardSpec：`suggestSize` 与 DSL 尺寸一致；动态卡片有 `dataBindings`；`capabilityId`、`arguments`、`writeResultTo` 合法；点击能力不要写进 CardSpec。
- 布局：目标尺寸为 `2x2 = 160 x 160vp` 或 `2x4 = 320 x 160vp`；主区域数量合理；关键文本完整显示；不要把桌面卡片做成页面。

## 输出格式

默认用中文输出，结构如下：

```text
结论：可渲染 / 有阻塞问题 / 需要补充能力 manifest / 只能做静态降级

问题清单：
- [P0] 位置：... 问题：... 原因：... 建议：...
- [P1] 位置：... 问题：... 原因：... 建议：...

其他建议：
- ...

生成 skill 优化建议：
- 如果该错误来自模型稳定复现，建议把 ... 加入生成 skill 的不可妥协项/最终评审。
```

如果用户只要求“修复”，先简短列出关键阻塞，再给修复后的代码块。修复时不要引入未声明组件、未声明数据能力、未声明事件函数或未声明资源路径。

## 表达式策略

完整 A2UI Form 协议支持表达式、`$__dataModel`、`$item`/`$index`、`itemVar`/`indexVar`、EventHandler `condition` 和 `as`。因此校验 skill 对表达式采用“允许但审慎”的策略：

- 协议层：表达式可用时，只校验它是否符合协议语法和作用域。
- 生成 skill 层：如果用户在验证 `$harmony-card-generation` 的输出，表达式是偏离生成 skill 的问题，标为 `P1 高风险` 或 `P3 提示`，不要误判为 A2UI Form 协议错误。
- 落地建议：简单展示优先建议用原生 `{path}` 或预计算字段；复杂条件或行为链可以保留表达式，但需要端侧函数/变量作用域明确。

## 反馈闭环

校验结果要服务于优化生成 skill。对于每类问题，尽量判断它属于：

- 协议硬错误：应加入生成 skill 的不可妥协项或 final review。
- 能力 manifest 缺失：应补充 data-capability 或 event-capability。
- 布局质量问题：应补充构图规则、宽度预算或设计评审。
- 产物局部错误：只需修复当前 DSL，不一定改 skill。
