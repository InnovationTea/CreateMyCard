# Compact Info Plan（维护源）

> 维护说明不发给模型；仅 `prompt` 标记内正文参与构建。

## 边界

Plan 只确定必须展示的信息与操作；组件和布局只给软候选。最终 Compact DSL 仍由创建 Prompt 生成。

<!-- prompt:contract -->
# Compact Info Plan

本轮不要生成 Compact DSL，只调用 `submit_card_plan`：

1. 将用户要求展示的内容拆成原子事实，每项填写简短 `requirement`。
2. 动态事实使用工具合同列出的真实 `dataId`；用户明确要求的操作使用真实 `actionId`；
   只有用户原文中的静态正文才使用 `text`；编辑时也可保留 previousDesignToken 已有的可见静态正文。
   每项三者恰好选择一个。
3. 不展示仅供事件传参、内部识别、背景计算或与 `userQuery` 无关的字段。不要把动态样例值改成静态文本。
4. `componentHints` 按优先级填写一至三个组件软候选；同一组件出现在多项事实中，表示这些事实可以
   合并到一个组件，不表示生成多个实例。候选不冻结组件、数量、区域或几何。
5. `layoutHints` 可按偏好填写至多两个能容纳全部事实和操作的正式父布局；它不冻结最终布局，
   不得为了匹配布局删除事实。没有把握时省略。
6. 提交前逐句核对用户要求的对象、数量、时间范围、信息和操作，确保 Plan 是最终卡片的最小充分信息合同。
<!-- /prompt:contract -->
