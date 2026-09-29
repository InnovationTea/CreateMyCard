# 画布与布局通则（维护源）

> 维护说明不发给模型；仅 `prompt` 标记内正文参与构建。

## 片段索引

| 片段 | 生成文件 |
|---|---|
| `height-gate` | `PROMPT.md` |
| `canvas-heading` | `PROMPT.md` |
| `canvas-budget` | `PROMPT.md` |
| `surface-budget` | `PROMPT.md` |
| `routing` | `PROMPT.md` |
| `layout-check` | `PROMPT.md` |

<!-- prompt:height-gate -->
## 3.1 一级高度算账硬门禁

输出 DSL 前必须先计算 root 一级区域高度：

1. 普通 `2x2`、`2x4` 的有效高度为 `126vp`；`S-dual-info` 为 `134vp`。
2. `H_required = 子项高度之和 + 纵向 margin 之和 + itemMargin × 间隔数`。
3. 无显式高度的容器按其后代实际最小高度、padding、margin 和间距计算；无 height 的 Text 也占行高，不能按零计算。基础 Text 单行至少预留约 `1.4 × fontSize`，多行逐行累计；高阶组件按其展开后的真实行高。包含 `36vp` 按钮时不得按 `0vp` 处理。
4. `layoutWeight`、`flexShrink`、`clip` 和分布式对齐不能抵消固定高度或最小间距。
5. `H_required` 超出有效高度时，删除可选装饰或改选同尺寸布局，不得删必要事实、动作或依赖裁切。
6. 有动作的正文必须先算剩余高度，再显式声明承载槽高度；不使用无 height 的多层弹性 Column 承载长内容。2x2 标题20、标题间距4、正文58、动作间距8、按钮36，合计126；正文三行18加两段2，恰为58，不再放24/30fp大值。2x4 双背板内高110，局部标题20、两段4和按钮36扣除后正文只有46，不能再放三行18；应合并短标签、取消可选标题或回退布局。

例如：`63 + 8 + 63 = 134vp` 成立；再增加 `20vp` 标题即超高。`59 + 40 + 36 + 8 × 2 = 151vp`
也不能通过 `spaceBetween` 修复。
<!-- /prompt:height-gate -->

<!-- prompt:canvas-heading -->
# 八、画布、密度与布局预算
<!-- /prompt:canvas-heading -->

<!-- prompt:canvas-budget -->
## 8.1 参考画布

| 尺寸 | 参考画布 | root padding | 安全内容区 |
|---|---|---|---|
| `2x2` | `150×150vp` | `12vp` | `126×126vp` |
| `2x2 S-dual-info` | `150×150vp` | `8vp` | `134×134vp` |
| `2x4` | `300×150vp` | `12vp` | `276×126vp` |

- 参考尺寸用于生成预算；实际 surface 变化时，固定宽度内容组在 root 内居中，不把差值堆到单侧。
- root 固定 `borderRadius:20`、`clip:true`；背景按第十二节的色板或 design 规则生成。
- 2x2 带标题布局使用 `CardHeader 20vp`；`S-center`、`S-content-dual-action`、`S-dual-info` 和其它无标题布局不使用 CardHeader。
- 2x4 只有 `W-top-bottom` 可使用卡级 CardHeader；其它布局的标题必须归属具体内容区。

## 8.2 数值预算

- 每个 Row/Column 都按父容器扣除 padding 后的宽高计算；子项尺寸、margin 和 `itemMargin` 全部计入。
- `start|center|end` 和 `spaceAround|spaceBetween|spaceEvenly` 都必须先满足最小占用量不超界。
- 动态 Text、Button 或图文动作完成压力预算后，主轴至少保留 `4vp` 余量。
- 间距只使用 `2、4、6、8、10、12、14、16vp`；紧密内容用 `2-6vp`，独立信息组至少 `8vp`。
- 数字与单位可以使用 `0-4vp`；其它独立信息不得使用 `itemMargin:0`。
- 固定间距使用 padding 或 `itemMargin`，不得用空容器占位；无布局职责的单子节点容器应折叠。
- 窄于父容器的主焦点或动作必须由父容器明确设置交叉轴位置。
- `clip:true` 只约束外形，不能掩盖文本、图标、Progress 或动作越界。
- 可点击元素宽高不得小于 `24vp`；主文字按钮高 `36vp`，底部动作贴近安全区底部。
- 同一信息组共享左边界、中心线或基线；Stack 不得制造遮挡。
- 单业务主辅区按实际内容分配高度，不机械等分剩余空间。正文可用 `layoutWeight:1` 承接剩余空间，
  但必须先扣除标题、按钮、辅助行和间距；每个弹性区域仍须容纳后代的实际行高。稀疏正文居中，
  多事实正文连续纵排，按钮沉底。组件或文字溢出时不能靠 `flexShrink` 隐藏问题。

## 8.3 区域上限

| 布局 | 一级区域上限 |
|---|---|
| 2x2 普通布局 | 最多 3 个直接区域、默认最多 1 个动作 |
| `S-content-dual-action` | 1 个内容区 + 2 个动作区 |
| `S-dual-info` | 2 个等高背板 |
| `S-quad-content` | 4 个固定内容格 |
| `W-top-bottom` | title/primary/details |
| `W-split-panels` | 2 个 `132×126vp` 父区 |
| `W-content-side-slots` | 1 个 `132×126vp` 内容区 + 2 个 `132×57vp` 固定槽 |
| `W-four-slots` | 4 个 `132×57vp` 固定槽 |
<!-- /prompt:canvas-budget -->

<!-- prompt:surface-budget -->
- 一个表面只强化背景填充、边框或阴影中的一种，不生成密集仪表盘、海报、完整页面或按钮矩阵。
- 2x2 单对象布局无法通过压力检查时，回退为“标题 20vp + 主显示组 46-54vp + 可选全宽动作 36vp
  或支撑信息 16-28vp”；全部区域和间距仍须闭合在 `126vp` 内。
- 回退时保留全部 `mustKeep` 事实和动作；长读数按纵向完整行组织，不增加侧边文字动作或独立弱 footer。
<!-- /prompt:surface-budget -->

<!-- prompt:routing -->
# 九、固定布局路由

每张卡只选择一个正式布局。路由顺序：

1. 按业务对象实例和共同任务划分数据块。同一对象的字段保持在同一数据块；字段、组件和动作数量不增加对象数。
2. 跨垂域内容只有存在明确共同任务时才能合并；不存在共同任务时保留主问题，其余内容按未满足或另行生成处理。
3. 动作归入其直接服务的数据块；无法确定归属的动作不进入布局。
4. 用户明确要求且已通过校验的动作标记为 `mustKeep`；容量不足时先删除 `shouldKeep`，再改选布局。
5. 固定槽必须由真实内容或动作填满；可选槽不存在时同时删除槽和相邻间距，不生成空容器或占位。
6. 根据尺寸和信息关系选择正式布局；S1-S4、W1-W10 只作为输入别名。

2x2：单核心用 `S-center`；两个对象用 `S-dual-info`；四个同级短模块用 `S-quad-content`；其余按
标题、主辅关系和动作数量选择对应布局。

2x4：单语义组连续阅读用 `W-top-bottom`；两个完整内容区用 `W-split-panels`；一个完整内容区加两个
固定槽用 `W-content-side-slots`；四个同级模块用 `W-four-slots`。两个独立业务各有一个直属动作且均能
使用 Sub-118-D 时，固定使用 `W-split-panels`。

Few-shot 只能示范已登记布局。提示词末尾存在固定场景路由或本轮路由摘要时按其允许范围选择，不从案例
或通用知识补回已被裁剪的布局。
<!-- /prompt:routing -->

<!-- prompt:layout-check -->
布局落地时检查：

- 一级区域数量、尺寸、间距和动作上限与所选布局一致。
- 标题、主体、支撑信息和动作保持在所属父区域内，不跨业务共享标题或按钮。
- 普通单业务采用明确主辅；固定分区布局保持登记尺寸，不改成自由比例。
- 专用 Progress、EventCard 和内容预设只替换所属内容槽，不改变一级几何。
- 颜色按第十二节选择；布局 ID 不决定业务色。
<!-- /prompt:layout-check -->
