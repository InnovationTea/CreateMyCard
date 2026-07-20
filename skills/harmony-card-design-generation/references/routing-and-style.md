# 分层路由与风格

## 1. 特征过滤

先从 query 提取 Feature Profile，再检查：尺寸、顶层模块数、动作数、能力数、素材职责、受保护文本长度和主视觉语义。不满足单一服务对象或单一主问题时先收敛需求。

## 2. 布局选择

运行：

```text
python scripts/query_design_system.py --layouts --size 2x2
```

按信息关系选择布局，不按业务关键词选择成品卡：

- 对象、主内容、动作：`header-main-footer`。
- 并列指标、主状态、动作：`metrics-main-footer`。
- 标题、进度与双指标、动作：`header-dashboard-footer`。
- 标题、单一大值、支撑面板：`header-hero-support`。
- 产品媒体和状态整体构图：`full-surface-stack`。
- 上下两组对照信息：`two-row-grid`。
- 主视觉、上下文、动作：`hero-context-footer`。
- 标题、复合日程、动作：`header-schedule-footer`。
- 宽标题和正文/动作侧栏：`header-content-sidebar`。
- 宽内容和两个动作：`content-action-stack`。
- 宽主视觉和上下文/动作：`hero-context-split`。
- 主指标、多指标和窄动作列：`metric-dashboard`。

## 3. 模块选择

对每个 region 查询兼容模块：

```text
python scripts/query_design_system.py --compatible-modules <layout-id> <region-id>
```

模块必须同时满足：

- role 位于 region 的 `allowedModuleRoles`。
- footprint 宽高与 region 完全相等。
- 必选槽位能覆盖 `mustKeep`。
- 模块语义适合主视觉类型。
- 动作目标、素材和文本预算合法。

不要读取多个旧成品模板比较，也不要跨模块复制局部组件树。

## 4. 元素与内容选择

查询选中模块变体：

```text
python scripts/query_design_system.py --module <module-id> --variant <variant-id>
```

为所有实际 `allowedTokens` 节点选择一个 token。可选节点没有对应内容时直接省略。内容只能填入模块 `slots`，绑定方式必须在 `bindingKinds` 中，静态文本不得超过 `maxChars`。

## 5. 风格档案

- `neutral-light`：浅色中性表面加一个强调色，适合日程、工具和信息摘要。
- `dark-focus`：深色中性表面和高对比强调色，适合使用时长、设备状态和告警。
- `ambient-scene`：受控场景渐变和高对比前景，适合天气、睡眠和倒计时。
- `media-surface`：主媒体承担识别，文字落在可验证的中性表面，适合产品与设备。

选择优先级为用户明确要求、query 场景、布局和模块的可读性。最终 DSL 由装配器写 hex，不输出风格名或颜色 token。

## 6. 无匹配处理

依次删除 `shouldKeep`、选择同尺寸更简单布局、尝试 `2x4`。仍不成立时要求简化需求，不调用其它 Skill，也不退回自由布局。
