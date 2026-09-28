# 修复案例边界

本次基线没有独立的 DSL 修复 few-shot，manifest 的 `fewshots.repair` 因此为空；
不为补齐目录而向线上提示词加入未经评审的新案例。已有 JSON 参数恢复案例完整保留在
`../../argument_repair.md`，不能当作 DSL 视觉修复案例发送。

新增案例应各占一文件，完整包含原始 TaskSpec、待修复的完整 genui、实际 qualityErrors、
修复后的完整 genui，并说明仅改变哪些节点。修复输出必须通过同尺寸上下文校验和 A2UI 转换，
确认动态绑定、事件/素材、未受影响区域不漂移，再明确是否以及如何进入 repair 提示词。
尺寸预算引用 layouts，不在修复案例中另设一套规则。
