---
name: phone-widget-2x4-repair
description: 收到合同、绑定或浏览器校验反馈后，按错误层级修复 JSX。
---

# 校验反馈修复

## 非布局错误的局部修复

当所有 ERROR 仅涉及数据绑定、静态文字绑定或组件 Prop，且不存在 `layout-structure`、`layout-budget` 或浏览器布局错误时：

- 保持上一版 `Card.layout` 不变；
- 保持所有 `Region.slot` 和 `Region.variant` 不变；
- 保持未被 findings 指向的组件和区域不变；
- 只修改 findings 明确指出的组件 Prop；
- 不得把双内容 variant 改成单内容，也不得用 `Stack`／`Grid` 合包已有内容。

只有 findings 明确证明当前布局结构或容量不成立，或者 Runner 明确进入布局兜底阶段时，才允许更换 layout 和 variant；decision 由 Runner 自动派生。

## 浏览器重叠修复

#### 浏览器重叠时的紧凑替换规则

当浏览器校验通过 `browser-semantic-overlap` 明确确认 `EmphasizedData` 与相邻业务组件重叠时，必须先复核该字段的业务语义。若内容属于短文本、状态或完整格式化字符串，优先尝试改用 `EmphasisText`；有真实且必要的第二个文本字段时填写 `secondaryText`，否则省略，随后重新执行语义与浏览器布局校验。

替换时必须完整保留可见内容和动态绑定：原 `value` 迁移到 `mainText`，原 `dataIds.value` 迁移到 `dataIds.mainText`；不得拆分格式化字符串、删除数据、把动态值改为静态文本或虚构 `secondaryText`。纯数值与单位、进度关系，以及根据组件选择规则应使用 `EventCard` 的日程事件，不得仅为解决重叠而替换。

```jsx
<EmphasisText
  mainText="15分钟"
  secondaryText="距离开始"
  dataIds={{ mainText: "countdown.remainingText" }}
/>
```

## 语义布局修复

把带静态标签的字段迁移进 `InfoBlock` 时，必须用 `primaryTextTemplate`／`secondaryTextTemplate` 保留标签；不得只保留动态值和单位，使“今日步数”“距离”等语义退化为孤立数值。

### 必需 Action 缺失

缺少 Info Plan 中的必需 Action 属于操作槽与布局结构错误，不是组件 Prop 的局部错误。每个 Action 必须占用一个合法操作槽；单 Action variant 只能包含一个位于最后的 `PillButton`，不得在同一 Region 追加第二个按钮，也不得在 `compact_component` 或 `drop_optional_component` 阶段删除 Action。

当 `main-right-double` 有两个必需 Action 时，先按业务归属分配：如果 `main` 业务组拥有一个 Action，优先使用 `wide-title-content-action` 或 `wide-title-primary-secondary-action`，并将该 Action 作为 `main` Region 最后的 `PillButton`；另一个 Action 放入 `side-top` 或 `side-bottom` 的 `CardButton`，剩余固定侧槽可保留一个 `InfoBlock`。若侧边不需要信息模块，也可以使用两个 `CardButton`。只有 `main` 无法使用合法 Action variant 且侧边槽不足时，才更换父布局。

### 双 Action 固定槽迁移

当 `main-right-double` 主区中的 `PillButton` 与内容发生间距或重叠错误，并且任务恰好有两个必需 Action 时，优先移除主区的 Action variant，将两个 Action 分别迁移为 `side-top`、`side-bottom` 的 `CardButton`。主区改用对应的无 Action variant；不得保留主区 `PillButton`，也不得保留或虚构 `InfoBlock` 占据任一固定操作槽。

### 提交前检查

1. 信息分区和 Action 归属保持一致，必需事实、绑定和操作未因容量不足而丢失。
2. Card.layout／Region.variant 与内容关系一致；各 Region 恰好填入所需标题、内容和操作，固定双槽、四槽均有效。
3. 依据组件实际宽高和标题高度检查容量，紧凑模式不以截断地点、设备名等必要信息换取通过。
4. JSX 只包含 Card、Region 与直属业务组件，不输出或复制程序展开的 Stack/Grid。正常修复保持上一版合法布局；只有布局类 findings 或 Runner 明确进入布局兜底阶段时，才允许更换语义布局标识，decision 由 Runner 自动派生。

新增或恢复组件时重新检查内容关系：核心在上、辅助沉底时使用双内容 variant，两个模块直接放在 Region 下；仅恰好三个紧凑占比使用 `NumericRatioStack`，一项或两项必须改选其他组件。更换布局不得删除 Info Plan 冻结的事实、绑定或 Action。
