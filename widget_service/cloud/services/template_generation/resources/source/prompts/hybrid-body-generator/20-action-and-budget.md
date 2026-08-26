---
promptGroup: hybrid-body-generator
fragmentId: action-and-budget
order: 20
promptVersion: hybrid-body-prompt/0.25
protocolVersion: tersedsl-nested-2-hybrid/0.2
contractVersion: hybrid-body-contract/0.5
---

<!-- prompt:start -->
标题、标题图标和整卡主 Action 写在根 card@1 的 cardParams 中，并且必须逐字使用本次候选。整卡主 Action 使用 `{ action: { label, id } }`，最多一个；required 指定时必须选择。

只有契约显式给出 contentActionCandidates 时，content 子树才允许消费局部 Action，并且每个批准 ID 必须恰好消费一次。局部 Action 只能通过本次允许且声明 actionPolicy 的 Template 参数，或使用批准 ID 的标准 Button 表达；模型禁止直接输出 onClick、call 或 args。没有 contentActionCandidates 时，content 子树禁止 Button、action、onClick、事件和 Action Template。

若已请求且参数完整的局部 Template 声明了匹配的 actionPolicy，必须由它消费对应 content Action；只有不存在这种完整匹配的 Action Template 时才能使用标准 Button，并严格使用 Action 规则中为该 Action 指定的 Design Token，不得用图标或其他 Design Token 替代。

必须完整保留 mustKeep。空间不足时先删除装饰与 shouldKeep，再合并相邻短文案；不得通过 Template 绕过展开后节点、深度、Action 或空间预算。不得发明输入中不存在的业务事实。
<!-- prompt:end -->
