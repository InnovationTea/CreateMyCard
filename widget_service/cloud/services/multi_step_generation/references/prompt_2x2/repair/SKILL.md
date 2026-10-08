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

## 2×2 语义布局修复

- 普通修复与 compact 保留 Info Plan 事实和绑定；仅 Runner 明确进入 `drop_optional_component` 时，可按专用反馈省略一个非 Action 业务显示组件并记为 partial。任何阶段均不得删除 Action 或把动态值静态化。
- 修复后仍只提交 `Card.layout + Region.slot/variant`；浏览器反馈中的 `Stack`、`Grid`、宽高、间距、flex 与定位是程序展开结果，不得复制或手改。
- `CircleButton` 没有可用 Icon 或 Action 需要显示文字时，将 `wide-title-anchor-action` 改为带底部 `PillButton` 的合法 variant；不得把 `PillButton` 塞进圆形操作槽。
- 当错误来自槽位数量或组件类型不匹配时，优先更换与现有业务组件数量相符的 variant；不得用容器把多个业务组件伪装成一个槽。
- 整宽组件发生收缩时，改选能提供完整宽度的合法 variant；不得补写 width、align 或包装容器。
- 带 `DoubleLineTitle` 的布局必须先计算剩余容量；不足以容纳业务组件时，改用更紧凑的合法组件或其他 variant。
- 双信息块必须同时保留两个 `InfoBlock`；任一组缺少主副文本、有 Action 或需要第三个模块时，改用 `single` 与相符的 variant。
