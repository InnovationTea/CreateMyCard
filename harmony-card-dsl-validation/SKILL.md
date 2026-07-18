---
name: harmony-card-dsl-validation
description: "校验、评审、分析或修复 HarmonyOS A2UI Form 服务卡片的 genui JSONL、DSL、CardSpec 或完整 artifact。用于用户提供卡片产物、草稿或错误日志并要求定位 JSON 语法、消息顺序、surface/root、组件属性、children 引用、DataModel 绑定、表达式、事件、素材、CardSpec 一致性、2x2/2x4 布局、色彩、对比度、信息层级、美观度或模型稳定性问题时；也用于把重复问题反馈到卡片生成 Skill。"
---

# Harmony 卡片 DSL 校验

把确定性程序检查与模型评审结合起来：程序负责可复现的协议、结构、绑定和静态美学诊断；模型负责解释根因、判断业务影响和提出最小修复方案。默认只诊断，不修改输入文件；只有用户明确要求修复时才输出修复后的产物。

## 执行流程

1. 识别输入形态：三行 `genui` JSONL、同时包含 `genui`/`cardspec` 的 Markdown、独立 CardSpec、完整 artifact，或局部组件/错误日志。
2. 读取 [`references/validation-rules.md`](references/validation-rules.md)，确定严重度、校验阶段、证据要求和输出格式。
3. 对可解析的完整输入运行校验器。优先使用模型格式快速定位，再在需要保留完整证据时使用 JSON 格式：

```bash
python <skill-dir>/scripts/validate_card.py <draft-or-jsonl> --format model --stop-on-stage-error
python <skill-dir>/scripts/validate_card.py <draft-or-jsonl> --format json --stop-on-stage-error
```

4. 根据诊断按需读取参考资料，不泛读无关长文：
   - 消息、surface、root、事件边界：[`references/protocol/protocol.md`](references/protocol/protocol.md)
   - 组件字段、样式和枚举：[`references/protocol/component-catalog.md`](references/protocol/component-catalog.md)
   - DataModel、Expression、PathBinding、模板：[`references/protocol/data-binding.md`](references/protocol/data-binding.md)
   - CardSpec 和动态数据契约：[`references/capability/cardspec.md`](references/capability/cardspec.md)
   - 点击目标与参数：[`references/capability/event-capability/click-event.md`](references/capability/event-capability/click-event.md)
   - 布局预算、文本、热区和留白：[`references/design/layout-system.md`](references/design/layout-system.md)
   - 主焦点、表面层级和构图：[`references/design/design-heuristics.md`](references/design/design-heuristics.md)
   - 色彩合法性、前景背景配对：[`references/design/color-token-system.md`](references/design/color-token-system.md)
   - 素材路径：[`references/design/asset-library.md`](references/design/asset-library.md)
   - 全量质量门：[`references/core-rules.md`](references/core-rules.md)
5. 把程序诊断与人工检查合并，去重后按严重度排序。明确区分“程序已证实”“模型根据规范推断”“需要端侧渲染或能力上下文确认”。
6. 用户要求修复时，先修 hard，再修 semantic，最后修 quality；每轮修复后重新运行校验器。不得为消除诊断而改变用户核心意图、编造动态能力、事件目标或资源路径。

## 输入命令

组合草稿或裸 JSONL：

```bash
python <skill-dir>/scripts/validate_card.py draft.md --format json
```

独立 DSL 和 CardSpec：

```bash
python <skill-dir>/scripts/validate_card.py --dsl card.genui.jsonl --cardspec card.cardspec.json --format json
```

完整 artifact：

```bash
python <skill-dir>/scripts/validate_card.py --artifact artifact.json --format json
```

有真实设备过滤结果时，将其作为唯一动态能力依据：

```bash
python <skill-dir>/scripts/validate_card.py --artifact artifact.json --effective effective.json --format json
```

可用参数：

- `--stage hard|semantic|quality|all`：`hard` 只跑硬校验，`semantic` 跑 hard+semantic，`quality`/`all` 跑全部阶段；默认 `all`。
- `--strict`：warning 也返回非零退出码。
- `--stop-on-stage-error`：hard/semantic 出错后停止后续阶段，避免美学噪声。
- `--no-aesthetic`：仅在用户明确只要协议检查时关闭静态美学分析。
- `--max-errors N`：限制 error 数量。

## 分析原则

- 不把“脚本没有报错”等同于视觉验收通过。动态文本、图片背景、真实字体、设备缩放和运行时数据仍需要端侧渲染复核。
- 不把缺少能力上下文直接判成能力不存在。没有 CardSpec、有效能力集合或能力 schema 时，标记为“待补充上下文”。
- 不根据历史模板、截图或通用 A2UI 知识放行当前 Form 子集未声明的组件、属性、函数或素材。
- 不只复述错误码。每条问题都说明位置、现象、规范依据、影响和最小修改建议。
- 发现同类问题反复出现时，判断应修改生成 Skill 的硬规则、参考资料、能力 manifest、校验器还是仅修当前产物。

## 输出格式

默认使用中文，先给结论，再列问题：

```text
结论：有阻塞问题 / 协议通过但有高风险 / 可渲染但需视觉优化 / 未发现明显问题

问题：
- [P0][程序已证实] 位置：... 问题：... 影响：... 建议：...
- [P1][模型复核] 位置：... 问题：... 依据：... 建议：...

待确认：
- 需要端侧渲染、有效能力集合或业务语义才能裁决的事项。

生成 Skill 改进：
- 只列具有重复性、应进入生成规则或校验器的问题。
```

如果用户要求修复，先简要列出关键改动，再输出完整、可重新校验的 `genui` 与可选 `cardspec`；不要只输出局部 patch，除非用户明确要求。
