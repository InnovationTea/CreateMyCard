---
name: phone-widget-2x2-repair
description: 收到合同、绑定或浏览器校验反馈后，按错误层级修复 JSX。
---

# 校验反馈修复

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

## 2×2 常见错误

## 4. 常见错误

- 不要把 `position`、`right`、`bottom` 传给 `CircleButton`；定位属于外层 `Stack`。
- `CircleButton` 没有可用 Icon 或 action 需要显示文字时，改用带底部 `PillButton` 的布局，不得将 `PillButton` 塞进右下圆形操作槽。
- 安全内容区内使用 `right={0}`、`bottom={0}`；`Card` 已提供 12vp padding，不要重复写 12。圆形操作槽固定为 40 × 40vp。
- 不要同时用父级 `gap` 和空白 `Stack` 表示同一段间距。
- 不要让整宽组件在 `align="flex-start"` 的父容器内按内容宽度收缩。
- 带 `DoubleLineTitle` 的布局必须先计算剩余高度；不足以容纳业务组件时不得生成。
