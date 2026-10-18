---
name: phone-widget-repair-common
description: 根据校验 findings 选择最小语义修复层级，并保持事实、绑定、Action 与未报错区域不变；不负责首轮生成策略。
---

# 校验反馈修复

## 1. 反馈总表

| 反馈类型 | 优先修复对象 | 默认保持不变 |
|---|---|---|
| JSX 语法、未知组件或未知 Prop | 报错节点及其 Prop | 信息、布局和其他组件 |
| 数据或 Action 绑定 | 唯一可见 owner、`dataIds` 或 `actionId` | 组件语义和布局 |
| 组件合同 | 当前组件，必要时改用语义等价组件 | 必要语义配对和 Action 作用范围 |
| Region 子节点、variant 或固定槽 | 当前 Region 或 variant | 其他 Region 与父布局 |
| 父布局容量或槽位不成立 | `Card.layout` 及受影响 Region | 必需事实、绑定和 Action |
| 浏览器重叠、溢出或截断必要事实 | 先检查组件密度和 variant，再检查父布局 | 未报错区域 |

## 2. 固定边界

修复仍遵守核心生成协议的语义 JSX 边界。浏览器反馈中的展开结构只是定位证据，不复制回 JSX，不通过新增底层布局 Prop 修复。

## 3. 保持不变的内容

1. 普通修复与 `compact_component` 保留用户明确要求的事实、真实 `dataIds`、全部 Action、必要语义配对和 Action 作用范围。分区边界默认沿用；只有 findings 或容量证明当前组织无法闭合时，才在不改变这些保持项的前提下调整。
2. 未被 findings 指出的组件、Region、静态标签和绑定保持不变。
3. 普通修复与 compact 不用删除信息、改写动态值、虚构内容、重复绑定或移动 Action 到无关分区换取通过。只有 Runner 明确进入 `drop_optional_component`，才允许按专用反馈省略一个最低优先级的非 Action 业务显示组件，并标记 partial；任何阶段都不得删除 Action 或静态化动态值。
4. 新增、删除或替换组件后，重新检查标题、内容数、Action 数和固定槽是否仍符合当前 variant。

## 4. 按错误类别修复

- **未知 Prop**：改用组件合同中的真实 Prop；布局性质不能改写成业务组件 Prop。
- **缺失或重复绑定**：把真实 ID 放到唯一可见 owner；不得用静态文案掩盖绑定错误。
- **Boolean 文本**：补齐同名 `dataIds` 与完整 `dataValueMaps`，或改绑输入已有的描述性字符串。
- **缺失 Action**：选择合法操作槽并保留 Action 归属；不把按钮改成普通文本。
- **内容数不匹配**：优先使用组件原生多 item 或合法组件组合；否则更换匹配的 variant。
- **组件不适合槽位**：改用语义等价且容量匹配的组件，或更换 variant；不套容器伪装槽位。
- **容量或视觉错误**：先使用合法紧凑形态和高密度组件，再更换 variant，最后才更换父布局。

## 5. 修复层级

### 5.1 `targeted`

只修改一个 Prop、绑定、静态标签或 Action ID。适用于语法、类型、重复绑定和单点合同错误。

### 5.2 `component`

替换一个业务组件或组件内部表达方式。新组件必须表达相同事实并保留全部相关绑定。

### 5.3 `sublayout`

更换当前 Region 的 `variant`，重新核对该 Region 的直属标题、内容与 Action；其他 Region 不变。

### 5.4 `parent-layout`

只有 findings 证明父布局的区域数、固定槽或容量无法成立时，才更换 `Card.layout` 并重新分配受影响 Region。普通修复与 compact 不得拆散必要语义配对、改变事实或绑定、改变 Action 作用范围，或删除必需内容；专用 drop 阶段按第 3 节的例外处理。

## 6. 重试中的递进

同一 failure fingerprint（错误类型与语义目标都相同）在修复后再次出现时，不继续改写不存在的几何 Prop；按 `targeted → component → sublayout → parent-layout` 逐级重新评估。错误类型或语义目标已变化时，从新 findings 所需的最小层级重新开始。

## 7. 重新提交前检查

1. 当前 findings 已被直接处理。
2. 除 drop 阶段明确省略的非 Action 信息外，保持项全部仍有唯一、合法的可见 owner。
3. 未引入新的校验错误；其余提交检查按核心生成协议执行。
