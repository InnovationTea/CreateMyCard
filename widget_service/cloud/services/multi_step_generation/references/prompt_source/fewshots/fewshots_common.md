---
name: phone-widget-fewshots-common
description: 维护两种尺寸共同的端到端示例结构和使用边界；不放具体领域答案、尺寸布局或可直接复制的任务 ID。
---

# 端到端示例约定

- 示例用于展示“输入规模与信息关系 → 合法槽位中的 JSX”如何应用正式合同；部分完整案例还附有 Plan，但实际运行仅在当前 Plan 已接受后检索，不覆盖 core、components、component-combinations、layouts 或 composition 的规则。
- 示例中的业务领域、静态文案、`dataIds`、`actionId`、Icon 和布局选择都不是当前任务答案；生成时必须重新读取当前输入并使用真实 ID 与资源。
- 简短分析只说明信息关系、组件候选和布局取舍，不作为额外输出。
- Plan 保留必要数据、必要 Action 和组件软候选，也可填写至多两个父布局软候选。最终 JSX 再确定布局，并满足当前尺寸的槽位、绑定和组件合同。
- 示例不能为了展示某种布局而补造字段、Action、Icon 或标题，也不能省略输入明确要求的内容。
