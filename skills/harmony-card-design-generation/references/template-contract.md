# 分层设计系统契约

## 资产闭环

- `index.json`：`design-system-v1` 入口、四种风格和尺寸上限。
- `layouts/catalog.json`：固定 root 和顶层 region 几何。
- `modules/catalog.json`：模块 footprint、抽象组件树、内容槽位和事件目标。
- `elements/catalog.json`：有限 element token 和组件规格。
- `cardspec/base.json`：CardSpec 基础形态。
- `schemas/`：Feature Profile、Design Plan 和三个 catalog schema。

使用 `query_design_system.py` 渐进查询，不在普通生成任务中一次性读取完整 catalog。

## Layout

每个布局声明 `id`、`size`、root 组件、`itemMargin` 和有序 regions。每个 region 声明角色、固定宽高、必选性和允许模块角色。

布局只负责顶层几何：

- `2x2` 画布 160x160vp、padding 12vp、内容区 136x136vp、最多三个顶层模块。
- `2x4` 画布 320x160vp、padding 12vp、内容区 296x136vp、最多四个顶层模块。
- region 外框、顺序、root shell 和间距不可在 Design Plan 中修改。

## Module

模块声明稳定 `id`、语义 `role` 和一个或多个 variants。每个 variant 固定包含：

- `footprint`：必须与目标 region 完全相等。
- `rootLocalId`：模块局部组件树入口。
- `nodes`：容器节点或允许 element token 的内容节点。
- `slots`：内容角色、目标节点、组件属性、必选性、绑定方式和字符预算。
- `eventTargets`：允许附加 `onClick` 的局部节点。

容器只能使用 Row、Column 或 Stack。内容节点不能直接声明组件类型，只能从 `allowedTokens` 选择。

装配时，模块 root 使用 region ID；其它本地节点命名为 `regionId__moduleId__localId`。不得自行新增、复用或改名。

## Element

每个 element token 固定声明组件类型、语义角色、样式和可选默认属性。Design Plan 只记录 token ID，不能记录宽高、字号、颜色或组件类型。

Text 只使用批准字号 `10/12/14/16/18/20/32/40`。Image、Progress 和 Button 的宽高由 token 固定；模块节点只能补充 catalog 已声明的受控容器宽度、对齐和文本盒宽度。

## Design Plan

Design Plan 顶层固定包含：

```text
schemaVersion
surfaceId
featureProfile
layoutId
styleProfile
regions
dataModel
cardSpec
degradations
```

每个 region 选择一个 `moduleId + variantId`，为实际元素节点选择 token，并把内容项映射到 slots。内容值三选一：`static`、`expression`、`path`；`path` 在装配后转换为 PathBinding object。

所有 `mustKeep` 恰好映射一次。可选节点没有内容时由装配器删除，并自动清理父节点 children 引用。

## 确定性装配

`assemble_card.py` 是唯一产物生成入口：

1. 校验 catalog 和 Design Plan。
2. 创建固定 root 和 region 顺序。
3. 展开模块节点并命名组件 ID。
4. 解析 element token 和风格颜色角色。
5. 注入内容、事件和初始 DataModel。
6. 生成 `.form` catalog 的三行 JSONL 与 CardSpec。

装配后的 DSL 不允许手工修改。`validate_card.py --design-plan` 会重新装配并比较完整消息和 CardSpec。

## 扩展顺序

新增能力时先更新 `方案设计.md`，再更新相应 schema/catalog、查询与装配脚本、严格校验和参考 fixture。新增模块必须解决现有模块无法表达的职责或 footprint，不能只复制旧成品卡。
