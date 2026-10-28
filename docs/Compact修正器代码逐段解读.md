# Compact 修正器：算法原理与代码逐段解读

## 1. 阅读范围

本文随 PR #686 的代码维护，按函数和实际执行顺序解释修正器。涉及规则、开关、搜索与采用判定的说明均对应本分支实现。

核心代码分为两个文件：

- [`compact_script_repair.py`](../widget_service/cloud/services/compact_script_repair.py)：原有六类结构／空间规则、候选调度、有限搜索、复检与采用判定。
- [`compact_contract_repair.py`](../widget_service/cloud/services/compact_contract_repair.py)：新增八类组件／内容合同规则。

修正器接收 Compact DSL、校验 error 和本次生成上下文，执行确定性字段与结构修改，再复用调用方的静态评估函数验证结果。输入来自 DSL、协议、CardSpec、TaskSpec 和已接受 Plan。

阅读顺序建议：先看第 2 节流程和第 10 节主循环，再看第 6 节各条规则，最后看第 17 节优化空间。
第 6 节的数值算例对应回归测试；第 11 节给出真实批跑源的连续修复过程。

### 1.1 校验器与修正器分别做什么

| 模块 | 回答的问题 | 示例 |
| --- | --- | --- |
| 校验器 | 这份 DSL 违反了什么规则？ | 容器可用高度 20vp，内部至少需要 40vp，超出 20vp |
| 候选生成器 | 对这种明确错误，允许尝试哪些修改？ | 把该容器高度从 20 改成 40 |
| 复检函数 | 修改后的整份结果还存在哪些错误？ | 原错误消失，但是否挤压了父容器或兄弟区域？ |
| 采用判定 | 与当前采用版本相比，是否有可确认的进展？ | 错误减少、无新增错误和 warning，才采用 |

这套方法可概括为：**规则驱动的候选生成＋共享预算的有限前瞻＋按错误事实采用**。

当前采用策略会接受第一个满足进展条件的结果，并从这个版本继续修复。遇到组件合同类改写时，还会在同一预算内继续探索中间候选，最多追加三步。第 17 节说明如何进一步保留多条分支、比较修改代价。

## 2. 最小流程

```text
当前 DSL 与校验错误
        ↓
结合诊断、原组件、Plan 和 TaskSpec 定位修改目标
        ↓
按固定顺序产生候选
        ↓
复检这一个候选
        ↓
比较修改前后的错误事实
   ├─ 有进展且无已检测退化：采用，再处理剩余错误
   └─ 尚未符合条件：按前瞻条件追加后续候选，再尝试其它候选
        ↓
错误清零／没有可采用候选／预算耗尽：返回当前版本及诊断
```

脚本返回当前采用版本和对应诊断。剩余 error 由外层质量控制器按原配置继续处理；采用版本同时携带转换后的 A2UI。

## 3. 输入与输出

入口是 [`compact_script_repair.py`](../widget_service/cloud/services/compact_script_repair.py) 中的 `repair_static_errors()`：

```python
async def repair_static_errors(
    result: DslProcessingResult,
    *,
    settings: Any,
    evaluate: Callable[[str], Awaitable[DslProcessingResult]],
    budget: ScriptRepairBudget,
    context: DslProcessingContext | None = None,
) -> DslProcessingResult:
```

### 3.1 `result`：当前 DSL 和它的检查结果

`DslProcessingResult` 定义在 [`generation_pipeline.py`](../widget_service/cloud/services/generation_pipeline.py#L103)。

| 字段 | 含义 |
| --- | --- |
| `source_dsl` | 当前采用的 Compact 源码，是脚本修改的对象 |
| `standard_dsl` | 与当前源码一起得到的标准 A2UI；转换失败时可以为空 |
| `issues` | 全部问题，包括 error 和 warning |
| `errors` | 从 `issues` 中筛出的 error，只读属性，不是另算的一组问题 |

脚本返回的也是这个对象，而不是单独一段新 DSL。这样可以把被采用版本的源码、A2UI 和诊断一起交给后续流程。

### 3.2 `settings`：哪些规则允许使用

总开关为 `enable_compact_script_repair`，默认 `false`。
十四个规则开关分别控制十四类候选；显式开启总开关后，启用的规则参与修复。

关闭总开关时，函数直接返回输入结果，不调用 `evaluate()`。

### 3.3 `evaluate`：由调用方提供的复检函数

它接收候选 Compact，返回 `DslProcessingResult`。

服务接入时，回调使用 `evaluate_source_dsl_sync()`，执行现有处理、转换和按配置开启的完整产物校验。
定向回放时，回调可直接执行 Compact 校验、转换和完整产物布局校验。这两种接入使用相同的候选规则与采用判定；第 12 节展开实际调用关系。

### 3.4 `budget`：本次生成还允许试多少候选

预算对象定义为：

```python
@dataclass
class ScriptRepairBudget:
    max_candidates: int
    candidates_used: int = 0
```

例如上限 12，已经试过 5 个，还能试 7 个。候选被拒绝也消耗一次预算，因为已经实际执行了复检。

当前服务在生成主流程中创建一次预算对象，并在模型质量重试后继续传同一个对象。
它不是整个系统或所有接口重试共享的全局预算；重新进入一轮生成主流程会建立新的对象。

### 3.5 `context`：尺寸、协议和布局等已知上下文

上下文在本轮修复中保持稳定，各字段有明确用途：

| 字段 | 在修正器中的用途 |
| --- | --- |
| `size`、`design_profile_id` | 求解参考空间，选择登记布局变体 |
| `card_spec.title` | 为符合条件的数值组件补文字标签 |
| `task_spec.dataModelSchema` | 核对缺失展示事实的路径与数据类型 |
| `task_spec.assetCandidates` | 将素材 ID 精确映射为本轮允许的资源引用 |
| `task_spec.eventCandidates` | 核对动作与完整参数的唯一授权候选 |
| `compact_plan.info_required` | 定位已接受的必显事实、动作及展示要求 |
| `compact_plan.assetAssignments` | 找到已分配的标题图标 |

几何、内容、素材和动作的候选由这些明确事实共同约束。

## 4. DSL 是怎样被定位和修改的

### 4.1 解析原始组件，不编辑编译器内部节点

`static_candidates()` 中：

```python
rows = parse_compact_dsl_rows(result.source_dsl, expand_layouts=False)
```

Compact JSONL 中，每行都是一条 JSON 记录，例如：

```jsonl
["left","Column",{"height":20},["value"]]
["value","EmphasisText",{"mainText":"会议"}]
["/ui/state","ready"]
```

前两行是组件，最后一行是数据。组件行解析为 `ComponentRow`，包含：

- `component_id`：例如 `left`，组件 ID。
- `component_type`：例如 `Column`，组件类型。
- `props`：例如 `{"height":20}`，属性。
- `children`：例如 `("value",)`，子组件引用。

`expand_layouts=False` 保留 `Layout/Region/Group` 等作者层语义节点，避免把编译器生成的内部 Row/Column 当成可直接编辑的原稿。

### 4.2 建立两个索引

遍历组件记录时建立：

```text
nodes[组件 ID] = 组件本身
parents[子组件 ID] = 父组件 ID
```

这样收到 `componentId="left"` 时可以定位 `left`，也可以沿 `parents` 向上检查承载区。
不是按“第几行字符串”做替换；重新序列化导致行号变化，不会改变组件定位方式。

### 4.3 诊断如何对应到规则

`_diagnostics()` 从 error 的 `compactDiagnostics` 中取出结构化诊断，结构与空间规则主要使用以下字段：
主要读取：

| 字段 | 当前用途 |
| --- | --- |
| `code` | 选择错误类型，例如高度溢出、点击数量错误 |
| `componentId` | 定位可编辑的源组件 |
| `actual.overflow` | 确定已知超限量，供空间候选及进展比较使用 |
| `evidenceComponentId` | 区分实际出错的展开节点，供错误事实比较使用 |
| `evidencePropertyPath` / `propertyPath` | 区分出错属性，供错误事实比较使用 |

新增合同规则还识别三种既有明确报错：`ContentBlock` 类型错误、`SecondaryBody is auxiliary`、`Plan fact is missing from visible DSL:`。这些精确文本用于触发对应分支；具体修改值继续从源组件和本轮上下文读取。

例如缺失事实会同时核对报错中的完整路径、Plan 的 `dataId`、Schema 类型和原数据初始化记录。
按钮槽位、素材引用、数值标签和动作目标则按原节点形状与登记候选生成提案，再由完整复检决定采用。
`sourceLine` 供排障查看，实际编辑按组件 ID 进行。

### 4.4 修改对象后重新输出 JSONL

`_changed_source()` 的做法是：

1. 顺序遍历全部记录。
2. 遇到同 ID 的目标组件时，换成新的 `ComponentRow`。
3. 其它记录保留。
4. 使用共享 `_serialize()` 输出 JSONL。

示例：

```python
changed = replace(current, props={**current.props, "height": 40})
```

含义是复制原组件，只更新 `height`。这里没有修改文字、字号、数据或点击参数。
JSON 输出可能去掉空格、把 `40` 写成 `40.0`，因此核对真实修改应比较 JSON 字段，不应把每个格式变化都算成业务修改。

## 5. 参考几何从哪里来

### 5.1 `_reference_boxes()`：复用参考几何

这个函数把组件转成共享布局求解器接收的形状：

```text
id / component / styles / children
```

随后加载当前设计协议，调用 `reference_region_boxes()`。
`SingleLineTitle` 的预占高度从已有视觉 Recipe 获取，不在修正器中重新写一套标题高度。

这里得到的是**协议参考几何**，不是读取图片测得的像素位置，也不是模拟器返回的实际边界。
求解器使用 `None` 表达待确定尺寸，规则据此选择具有明确尺寸依据的候选。

### 5.2 `_height_is_known()`：确认父区高度

它用于高度闭合规则，检查：

1. 有请求上下文。
2. 父区满足该规则的普通布局条件。
3. 共享求解器得到该父区的正数高度。

这一步读取的是父区实际分配的参考高度，随后才用于子组件的高度继承。

### 5.3 `_growth_fits_parent()`：扩容前核对直接父区

扩容候选生成之前，先检查直接父区是否能放下候选尺寸。
有显式父尺寸时先读取它；有可求解参考尺寸时，也纳入限制，两者都有时取较小值。

判断式是：

```text
新尺寸 + 子组件沿该轴的 margin 总和
    ≤ 父尺寸 - 父组件沿该轴的 padding 总和 + 0.000001
```

例如父区高 60，上下 padding 各 4，子区上下 margin 各 2：

```text
父区内部空间 = 60 - 4 - 4 = 52
候选高 40：40 + 2 + 2 = 44，允许产生候选
候选高 55：55 + 2 + 2 = 59，不产生该扩容候选
```

直接父区预筛通过后，完整复检继续检查兄弟总占用、祖先预算及其它合同。

`_number()` 和 `_inset()` 复用 `compact_region_layout.py`：数值只接受有限、非负且非布尔的数；统一计算某一轴两侧的内外边距。

## 6. 十四类规则：到底改了哪个字段

原有六类规则在 `compact_script_repair.py`，新增八类规则在 `compact_contract_repair.py`。规则名称用于开关、候选调度和 Trace；多个规则可以共享几何与序列化函数。

### 6.1 按钮空间：`button-slot`

**触发依据：** 已有高度或宽度溢出诊断，且可定位的 Row/Column 子树中存在 `PillButton`、`CircleButton` 或 `CardButton`。

`static_candidates()` 对这类区域尝试：

```python
grown = explicit + overflow
```

例如当前容器高 20，校验报告需要再增加 20，候选高就是 40。

```jsonl
["action_area","Column",{"height":20},["button"]]
```

候选片段：

```jsonl
["action_area","Column",{"height":40},["button"]]
```

本规则修改承载按钮的显式布局容器，适用条件为：

- 对应规则开关开启。
- 目标不是 `root`。
- 原宽高是明确数值，不是表达式或 `matchParent`。
- 新尺寸通过直接父区预算预筛。

候选尺寸由原值与本次诊断中的超限量计算。

### 6.2 父容器预算：`parent-budget`

这类候选有两个动作。

**动作 A：扩展不包含上述按钮的显式 Row/Column。**

扩容计算与按钮空间相同：`原尺寸 + overflow`，仍检查父区预算。
因此 `button-slot` 与这个动作共享算法，区别是按钮子树识别和各自开关，不是两套几何引擎。

已执行的回归用例中：

```text
父 Row 高度：60
left 容器高度：20
left_inner 固定高度：40
```

校验器实际报告：

```json
{
  "code": "COMPACT_LAYOUT_HEIGHT_OVERFLOW",
  "componentId": "left",
  "actual": {"minimumRequiredHeight": 40.0, "overflow": 20.0}
}
```

修正器只把 `left.height` 从 20 改为 40.0；完整复检的 error 从 1 变为 0，使用 1 个候选。
这是仓库构造回归用例的执行结果，不是某张历史业务卡的修复统计。

**动作 B：减少正数 `itemMargin`。**

依次尝试两个值：

```text
0
原 itemMargin / 2
```

例如原间距 8，会依次试 0、4。先试 0 是为了避免反复减半只产生很小进展，消耗完整候选预算。

有限取值使一次评估直接验证一个明确改法；两种候选都经过同一完整复检。

### 6.3 同级空间：`sibling-space`

**触发条件：** 宽度超限、当前组件是 Row/Column、已有正数 `layoutWeight`，并且其直接父组件是 Row。

按以下倍数尝试：

```text
原权重 × 2、× 3、× 4、× 6
```

例如兄弟初始权重为 `1:1`，会尝试 `2:1`、`3:1`、`4:1`、`6:1`。
它只改变报错区的权重，不会同步把兄弟权重改成一组新值。

在简单的加权横排中，可用剩余宽度为 R 时，权重 `2:1` 约分得 `2R/3` 和 `R/3`；
固定宽度、边距和其它约束存在时，以原布局计算和复检为准。

复检同时检查另一侧空间、文字及 warning；采用判定要求整份结果满足进展条件。
这些倍率是规则中的有限候选值。

### 6.4 完全重复点击去重：`duplicate-click`

`_structural_candidates()` 处理 `COMPACT_CLICK_HANDLER_COUNT`：

它检查：

1. `onClick` 是列表，至少两个元素。
2. 每个元素恰好包含 `call` 和 `args`。
3. `call` 是非空字符串，`args` 是对象。
4. 每个 handler 用 `json.dumps(..., sort_keys=True)` 规范化后，所有结果完全相同。

只在全部相同时保留第一个。例如以下片段中的动作来自固定测试夹具：

```jsonl
["left","Column",{"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Weather","uri":"hww://weather"}},{"call":"clickToDeeplink","args":{"intentName":"Weather","uri":"hww://weather"}}]},["value"]]
```

候选片段：

```jsonl
["left","Column",{"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Weather","uri":"hww://weather"}}]},["value"]]
```

该固定用例重新执行后：1 个 error 变 0，使用 1 个候选。

完整比较包括 JSON 类型：数字 `1` 和布尔 `true` 的序列化结果不同。全部 handler 的调用与参数一致时，保留一个即可满足单动作合同，同时保持动作含义。

### 6.5 高度关系闭合：`height-closure`

`_structural_candidates()` 还处理 `COMPACT_LAYOUT_HEIGHT_UNRESOLVED`。

例子：父 Row 的高度是 60，内部 `left` Column 没声明 height，但它的子 Column 要 `matchParent`。
此时子项依赖父高，而父列的可用高没有明确闭合。

修前片段：

```jsonl
["row","Row",{"height":60},["left","right"]]
["left","Column",{"layoutWeight":1},["inner"]]
["inner","Column",{"height":"matchParent"},["value"]]
```

候选仅补这一项：

```jsonl
["left","Column",{"layoutWeight":1,"height":"matchParent"},["inner"]]
```

适用条件是源组件为缺少 height 的普通 Column、直接父组件为 Row，且共享求解器能确定父高。
该固定用例重新执行后：1 个 error 变 0，使用 1 个候选。候选随后继续参与内容占用检查。

### 6.6 已登记语义布局：`semantic-layout`

代码集中在 `_semantic_candidates()`、`_split_region_candidate()`、`_top_bottom_candidate()`，修改组件分组和已登记布局参数，保留原文字内容。

#### A. 尝试同一个布局的登记变体

| 原节点 | 当前枚举的候选 |
| --- | --- |
| 2×2 `S-title-content-action` | `direct`、`direct-dense`、`direct-tight`、`direct-flush` |
| 2×2 `S-title-primary-secondary-action` | `dense` |
| 2×4 `W-top-bottom` | `equal`、`bottom-details`、`continuous` |

跳过与原变体相同的值。具体几何由已有布局合同展开，修正器不自己画一个新模板。

#### B. 两个只读内容区改变排列方式

对于恰好两个孩子的 Group：

- 高度超限：原 `hero-support` 或 `label-value` 可以尝试 `peer-pair`。
- 宽度超限：原 `peer-pair` 可以尝试 `hero-support`。

前者通常由上下转为并排以减少高度；后者通常由并排转为上下以增加各自宽度。
这些是后置候选，不是在检测到错误后立即把全部卡片改为横排。

`_readonly()` 检查子树内有无 `onClick` 及 `InfoBlock/PillButton/CircleButton/CardButton`。
这里的“只读”是程序定义的可重组范围，不是用模型判断任意业务组件的语义。

#### C. 调整 `SecondaryBody.columns`

- 高度超限，尝试 2 列。
- 宽度超限，尝试 1 列。
- 原列数已等于目标值时不产生该候选。

items、文字和字号保留，但每列变窄后仍可能产生宽度问题，必须复检。

#### D. 把主内容和辅助内容组织为 Group

例如原 2×2 结构：

```text
root：S-title-primary-secondary-action
  title
  main
  support
  action
```

候选可以是：

```text
root：S-title-content-action
  title
  root_content_group：hero-support
    main
    support
  action
```

`title/main/support/action` 的业务内容不由该规则改写；增加的是中间分组。
新 Group 的 ID 使用共享 `_unique_id()` 避免撞掉已有业务组件。

支持的外层对应关系是：

| 原结构 | 候选结构 |
| --- | --- |
| `S-title-dual-content` | `S-title-content`＋Group |
| `S-title-primary-secondary-action` | `S-title-content-action`＋Group |
| Region `title-hero-support` | Region `title-content`＋Group |
| Region `title-hero-support-action` | Region `title-content-action`＋Group |

对主、辅区域继续执行只读检查。优先试 `hero-support`，之后才试 `peer-pair`；有底部动作的小卡还联合枚举四种已登记动作变体。

因此一个语义布局候选可以包含一组关联修改：外层布局、Group 和子引用一起形成完整结构。

### 6.7 已知正文组件纠正：`known-component`

入口是 `compact_contract_repair.py` 的 `_known_component()`。

执行顺序为：

1. 从 error 中识别 `unsupported component type ContentBlock.`。
2. 按行读取 JSON，找到三项组件记录 `[id, "ContentBlock", props]`。
3. 确认属性恰好为一个非空字符串 `body`。
4. 保留组件 ID 与正文，将其写成登记的 `EmphasisText.mainText`。

核心改写为：

```python
changed[index] = [row[0], "EmphasisText", {"mainText": body}]
source = "\n".join(json.dumps(item, ensure_ascii=False) for item in changed)
yield "known-component", source
```

对应字段变化：

```jsonl
["content","ContentBlock",{"body":"导航到公司"}]
```

变为：

```jsonl
["content","EmphasisText",{"mainText":"导航到公司"}]
```

本条规则解决组件类型和正文属性合同。候选仍携带原正文，继续接受内容、动作与布局检查。

### 6.8 辅助信息主体合同：`primary-content`

入口是 `_primary_content()`。先确认 error 指出了 `SecondaryBody is auxiliary`，且当前组件集合缺少登记的核心信息组件。

随后查找符合以下形状的 `SecondaryBody`：

- 无子组件；属性属于 `items/columns/fontSize/fontColor`。
- 恰好两项或四项，每项恰好包含 `label`、`value`。
- 原有效字号为 12。

两项时的核心代码：

```python
props = {"items": items, "fontSize": 12}
if "fontColor" in row.props:
    props["fontColor"] = row.props.get("fontColor")
if len(items) == 2:
    yield _changed(rows, replace(row, component_type="TableText", props=props))
```

即保留 ID、两项文字和绑定，使用能承担核心信息角色的 `TableText`。四项时，原四项按顺序分成两个双项 `TableText`，再放入 `peer-pair` 或 `hero-support` 的登记 Group。

这一规则的依据是已有信息的角色与形状，修改的是信息承载组件。真实用例 Q017 在第 11 节展开。

### 6.9 按钮角色纠正：`action-slot`

入口是 `_action_slots()`。函数读取父 Layout／Region 声明的动作槽位，再定位最后一个动作子组件。

当前登记为 `PillButton` 槽位的布局包括：

- `S-title-content-action`
- `S-title-primary-secondary-action`
- `S-title-dual-column-action`
- Region 的 `title-content-action`、`title-hero-support-action`

如果槽内是已有 label 和 onClick 的 `CardButton` 或 `CircleButton`，且属性都属于两种类型共享的 `label/icon/onClick/fontColor/fillColor`，候选只变更组件类型：

```python
yield replace(action, component_type=required)
```

原按钮 ID、文案、图标、点击动作及参数一起保留。复检确认新的按钮类型及其实际空间符合当前布局合同。

### 6.10 登记素材引用补齐：`asset-reference`

入口是 `_asset_references()`，分为两个动作。

**动作 A：把素材 ID 映射成精确 src。**

函数从本轮 `TaskSpec.assetCandidates` 建立 `id → src 集合`。源组件的 `icon` 或 `src` 恰好等于某个素材 ID，且该 ID 只有一个 src 时，使用该 src：

```python
matches = assets.get(value, set()) if isinstance(value, str) else set()
if len(matches) == 1:
    props[key] = next(iter(matches))
```

**动作 B：落实已接受 Plan 的标题图标。**

当整份源码恰好一个 `SingleLineTitle`、该标题缺少 icon 时，读取 `Plan.assetAssignments.title.assetId`，精确解析其唯一 src，再写入标题 icon。

两个动作均采用本轮候选中已经登记的素材引用；修改内容是资源字段。

### 6.11 明确授权事实补齐：`plan-fact`

入口是 `_missing_fact()`，它把“计划里已经要求展示、数据也已存在”的少量事实落实到组件。

#### A. 识别缺失事实

逐项读取 `Plan.info_required`，同时要求报错包含 `Plan fact is missing from visible DSL:` 及同一完整 `dataId` 路径。一次处理一至两项。

#### B. 核对数据来源和类型

从原 DSL 提取数据行，复用 `build_compact_data_model()` 构造原有初始数据；再对同一路径读取：

```python
found, schema = _json_pointer_value(context.task_spec.get("dataModelSchema", {}), path)
initialized, initial = _json_pointer_value(data, path)
```

`found` 对应 Schema 路径，`initialized` 对应原数据初始化路径。两处均存在且类型匹配后，按以下方式构造展示值：

```python
if schema.get("type") == "string" and isinstance(initial, str):
    value = {"path": path}
elif schema.get("type") == "boolean" and isinstance(initial, bool):
    value = f"{{{{ ${{{path}}} ? '是' : '否' }}}}"
```

字符串保持动态绑定；布尔值用“是／否”表达式展示。标签取自该 Plan 事实的 `requirement`。

#### C. 放入现有信息区域

已有 `SecondaryBody.items` 加入新项后总数至多六项时，候选为：

```python
changed = replace(host, props={**host.props, "items": [*items, *additions]})
yield _changed(rows, changed)
```

原有条目按原顺序保留。原数据行保持不变，新增的是对已有路径的展示引用。

#### D. 单项标题的登记形状

单项字符串事实被 Plan 提示为 `SingleLineTitle`、当前缺标题、根布局为 `S-content-dual-action` 时，可以将原正文和新标题组织进登记的 `hero-support` Group。

两个新增 ID 通过 `_unique_id()` 生成。原正文以新 ID 原样承载，原 host ID 改为 Group，外层引用关系随之闭合。

### 6.12 固定信息槽归位：`fixed-slot`

入口是 `_fixed_slot()`，识别一个明确的宽卡形状：

```text
root：W-content-side-slots
  content：Region / title-hero-support
    title
    primary：InfoBlock
    support
  upper
  lower
```

候选改成：

```text
root：W-four-slots
  content：Group / label-value
    title
    support
  primary：原 InfoBlock
  upper
  lower
```

对应核心代码：

```python
props = dict(root.props)
props["layout"] = "W-four-slots"
props.pop("orientation", None)
changed_root = replace(
    root, props=props, children=(content.component_id, primary_id, *root.children[1:])
)
```

固定 InfoBlock 的 ID、属性和内容保持原样，改动集中于根布局、原 content 的分组属性与子引用。`orientation` 随原布局一起移除，采用四槽布局自身的登记合同。

### 6.13 数值文字标签补齐：`numeric-label`

入口是 `_numeric_label()`。候选同时满足：

1. CardSpec 已有一至八字的标题。
2. 目标是缺 label 的 `DataDisplay`。
3. value 为单一 path 绑定，Schema 明确为 number 或 integer。
4. 若该组件已有 icon，同一个 icon 已由另一 `SingleLineTitle` 承载。

具体修改：

```python
props = {**row.props, "label": title}
props.pop("icon", None)
yield replace(row, props=props)
```

标签值就是当前 `CardSpec.title`。当原数字区的同一图标已经由标题承载时，数字区转为文字标签呈现；数字值、路径、单位及标题处图标保留。

### 6.14 唯一动作候选参数纠正：`event-target`

入口是 `_event_target()`，执行顺序为：

1. 收集 Plan 事实中的 actionId，要求只有一个动作 ID。
2. 找出有 onClick 的按钮，要求恰好一个。
3. 从 TaskSpec 找同 ID 的 eventCandidates，以完整 call／args 序列化去重。
4. 去重后恰好一个授权 handler，且原按钮恰好一个 handler。
5. 原 handler 与授权 handler 的 call、intentName 一致时，使用该精确候选纠正参数。

核心赋值为：

```python
if actual[0] != handler:
    yield replace(button, props={**button.props, "onClick": [handler]})
```

例如 Plan 确定动作，TaskSpec 又唯一确定日程实体路径时，规则可以把原按钮指向错误实体的参数改回授权路径。
这里的“唯一”比较完整参数，同一动作 ID 对应三个不同实体时会保留其歧义状态，交给后续处理选择目标。

### 6.15 合同规则的统一出口

`contract_candidates()` 使用当前结果、开关和上下文，依次生成以上八类候选，返回统一的二元组：

```python
yield rule, candidate_source
```

两部分分别是规则 ID 和完整候选 Compact。`_changed()` 复用 `_serialize()`：替换同 ID 组件，追加需要的新组件，保留其它记录顺序。
因此空间规则和合同规则可以共用后面的搜索、预算、复检与 Trace。

## 7. 2×4 整卡分区候选

`_split_region_candidate()` 与 `_top_bottom_candidate()` 都属于语义布局规则，不是第七、第八个开关。

### 7.1 `_split_region_candidate()`：上下布局转左右分区

只识别 root 为 `W-top-bottom`，有 2 或 3 个孩子的结构，并要求全部相关子树满足只读条件。

- 最后一个孩子是 `EventCard`：允许准备该候选，不额外要求宽高错误码。
- 最后一个孩子是 `SummaryList` 或 `TopTextBottomValue`：要求已有宽高错误，且 root 恰好三个孩子。

改为 `W-split-panels` 后新增两个 Region：原标题与主内容进入第一分区，原明细进入第二分区。
明细条目不被脚本删成摘要。

### 7.2 `_top_bottom_candidate()`：左右分区转上下布局

只识别严格形状：

```text
W-split-panels
  Region，仅含 variant=title-content，恰好两个孩子
  Region，仅含 variant=center，恰好一个孩子
```

明细必须是 `SummaryList` 或 `TopTextBottomValue`，且通过只读检查。
候选改为 `W-top-bottom/continuous`，移除两个用于分区的 Region 记录，保留其中的业务组件和数据记录。

### 7.3 从局部候选到整卡候选

一般语义候选围绕已定位的报错子树和祖先枚举；以上整卡分区候选则是特定根结构改写。
它们在诊断遍历之前准备，放入最后一组重排候选。

因此候选顺序是：优先局部修改，之后尝试明确列举的整卡结构候选。

## 8. 候选顺序：合同、局部修改、保持方向与重排

`static_candidates()` 是候选调度器。

实际顺序为：

1. 由 `contract_candidates()` 产生已知组件、主体角色、Plan 事实、固定槽、按钮角色、素材、数字标签和动作参数候选。
2. 按诊断顺序，检查重复点击和高度闭合候选。
3. 对已定位的低阶 Row/Column，从当前区域沿父链尝试扩容、间距、权重等局部修改。
4. 输出累积的保持方向语义候选 `same_direction`。
5. 最后输出重排候选 `reflows`，包括跨分区、Group 方向和列数变更。

局部候选通常一次改一个属性；它们不是先全部组合成一份“大改稿”。
采用一个候选后，会以新的当前版本重新生成下一轮候选。

还有三点实现细节：

- `seen` 去重相同候选或同处同属性同值修改，减少重复复检。
- `_subtree()` 用栈遍历孩子，`visited` 避免循环引用造成无限遍历。
- 低阶父链遇到非 Row/Column 或不处理的变换属性时停止，不越过未知几何继续猜尺寸。

“保持方向优先”由同层候选顺序实现。主循环还会把符合前瞻条件的后继候选放到队首，使一条组件合同修复链能够连续探索；具体队列操作见第 10 节。

## 9. 最关键部分：怎样判断修复有进展

不能只比较错误条数。把一个旧错误换成另一个新错误，也可能条数减少。

### 9.1 `_error_facts()`：建立可比较的错误身份

把错误整理成一张映射表：

```text
(错误码, 证据组件 ID, 证据属性路径) → overflow 或未知
```

优先使用 `evidenceComponentId/evidencePropertyPath`；没有时退回 `componentId/propertyPath`。

原因是编译器可能把多个内部错误都映射到源 `root`。例如：

```text
root 对应的 body 高度超限 26
root 对应的 primary 高度超限 8
```

若只用 root 作身份，两个事实会被合并。保留证据组件身份才能发现“一个减少但另一个变坏”。

相同身份出现多次时，已知超限取最大值；只要其中存在未知值，保留未知状态。
没有结构化诊断的错误使用 `(issue.code, issue.message)` 作为身份，不使用字符串相似度猜测是同一个错误。

### 9.2 `_improved()`：判断是否采用

它执行四个判断：

1. 修改后不能出现任何新的错误事实身份。
2. 错误事实集合严格减少，或者同一个已知问题的超限严格下降。
3. 原本已知超限的剩余问题，不能增大，也不能变为未知。
4. 不能新增 warning；warning 按 `(code, message)` 比较。

核心代码：

```python
old, new = _error_facts(before), _error_facts(after)
if not new.keys() <= old.keys():
    return False
improved = new.keys() < old.keys()
for key, overflow in new.items():
    previous = old.get(key)
    if previous is not None:
        if overflow is None or overflow > previous:
            return False
        if overflow < previous - 1e-6:
            improved = True
```

符号 `<=` 在这里比较集合的包含关系，不是比较错误数值大小。
`1e-6` 是判断严格改善时的浮点余量，不是允许额外溢出的 UX 容差。

例子：

| 修改前 | 修改后 | 是否采用 | 原因 |
| --- | --- | --- | --- |
| A 超限 26 | A 超限 8 | 是，部分改善 | 同处已知超限下降 |
| A 超限 26 | A 超限 26 | 否 | 没有进展 |
| A 超限 26 | A 超限 27 | 否 | 原问题恶化 |
| A 超限 26 | B 超限 8 | 否 | 出现新错误身份 |
| A=26、B=8 | A=8、B=9 | 否 | B 恶化，不能用 A 的改善抵消 |
| A=26、B=8 | 只剩 A=26 | 是，部分改善 | B 被消除，A 未恶化 |
| A 超限 26 | 无 error，但新增 warning | 否 | 当前策略不接受新警告 |
| A 超限 26 | A 超限未知 | 否 | 不能证明问题没有变坏 |

未知超限变为已知数值本身不算一次改善；若既没有减少错误事实，也没有已知超限严格下降，则不采用。

这里采用错误事实的集合关系和逐项超限比较。它将“一处改善”和“其它处保持”同时作为采用条件。

### 9.3 采用后的结果怎样继续使用

候选函数负责限定改写字段，评估函数负责检查整份结果，`_improved()` 负责比较前后进展。
采用时把完整 `DslProcessingResult` 作为新版本：源码、转换结果和剩余问题一起更新。
后续规则从这个版本继续；外层模型修复也接收这个版本及对应错误。

## 10. 主循环：预算、前瞻、复检和采用

入口 repair_static_errors() 按以下顺序执行。这里的“搜索状态”是一份候选 Compact 加上对应的完整复检结果。

### 10.1 进入条件：原校验存在 error，且总开关开启

~~~python
if not result.errors or not settings.enable_compact_script_repair:
    return result
~~~

条件满足时直接返回同一个结果对象。进入修复后，original 保存本轮起点，result 始终表示当前已采用版本。

### 10.2 建立本轮队列与源码去重集合

~~~python
original = result
attempted = 0
seen_sources = {result.source_dsl}
while result.errors and budget.candidates_used < budget.max_candidates:
    accepted = False
    remaining = budget.max_candidates - budget.candidates_used
    pending = deque()
    for rule, source in islice(static_candidates(result, settings, context=context), remaining):
        pending.append((rule, source, (), result.source_dsl))
~~~

逐句解释：

1. attempted 是本次函数调用实际评估的候选数。
2. seen_sources 保存本次调用已经评估过的完整源码；初始源也加入集合。
3. 外层 while 同时检查剩余 error 和共享预算。
4. remaining 是当前生成主流程还能使用的候选评估次数。
5. deque 是标准库双端队列，支持从左边取任务，也支持把后继任务放回左边。
6. islice 按 remaining 限定本次枚举范围。
7. 队列元素包含四项：规则 ID、候选源、已走过的规则链、生成该候选的父源。

第一个候选的 ancestors 为空。后继候选携带之前的规则链，便于控制深度和显示修改过程。

### 10.3 实际复检前消费一次预算

~~~python
rule, source, ancestors, parent_source = pending.popleft()
if source in seen_sources:
    continue
seen_sources.add(source)
chain = (*ancestors, rule)
budget.candidates_used += 1
attempted += 1
~~~

去重判断先执行，因此相同原文被再次提出时会跳过。真正进入评估的候选才消耗预算，采用和拒绝都计一次。

chain 是当前候选完整的改写链，例如：

~~~text
("fixed-slot",)
("fixed-slot", "plan-fact")
~~~

这两条分别表示“只移动固定槽”和“在移动固定槽后补展示事实”。

### 10.4 复检整个候选，并与当前采用版本比较

~~~python
candidate = await evaluate(source)
accepted = _improved(result, candidate)
~~~

evaluate 返回整份 DslProcessingResult。_improved 的左侧 result 是已采用版本，右侧 candidate 是这次完整候选。

即使候选来自连续两步、三步改写，最终也相对已采用版本比较。这样采用的是一条修复链的完整结果。

### 10.5 满足条件就更新当前版本

~~~python
if accepted:
    result = candidate
    break
~~~

一次采用后结束当前队列枚举，外层 while 根据新结果重新生成候选。已解决的错误随新诊断消失，后面的规则针对剩余错误工作。

原先的贪心采用保留在这一处：遇到第一个满足进展条件的结果就采用。有限前瞻扩大了找到这种结果的路径，第 17 节进一步说明多分支选择的优化方向。

### 10.6 合同类候选可以继续有限前瞻

~~~python
if len(ancestors) >= 3 or not any(name in CONTRACT_RULES for name in chain):
    continue
remaining = budget.max_candidates - budget.candidates_used
followups = []
for child_rule, child_source in islice(
    static_candidates(candidate, settings, context=context),
    remaining,
):
    followups.append((child_rule, child_source, chain, source))
pending.extendleft(reversed(followups))
~~~

按执行顺序解释：

1. 当前链包含八类合同规则之一时，允许继续探索。
2. ancestors 达到三项时停止向下扩展，所以最多是“初始一步＋追加三步”，共四次改写深度。
3. 在中间候选及其新诊断上再次调用 static_candidates()，找下一层可解释修改。
4. 每个后继携带父候选 source 和完整 chain。
5. reversed 与 extendleft 配合，使后继保持原生成顺序，并排在其它同层候选之前。
6. 所有后继实际评估仍消耗同一个 budget。

因此当前搜索是**按规则顺序、深度优先的有界前瞻**。只有满足采用条件的结果才赋给 result；前瞻中的中间状态留在队列和 Trace 中。

以 Q037 为例：第一步把 InfoBlock 放回登记槽位后，完整检查继续报告两个必显事实缺失；第二步补齐它们，整条链相对起点满足采用条件，于是采用两步之后的完整版本。

### 10.7 Trace 逐步保存什么

每次评估由 trace_span("compact.script.candidate") 包围，保存：

| 字段／附件 | 含义 |
| --- | --- |
| rule、ruleName | 当前规则 ID 与中文名 |
| ruleChain | 从本轮分支起点到当前候选的规则顺序 |
| candidate | 本次生成内累计候选编号 |
| compact_script_before | 当前已经采用的源码 |
| compact_script_parent | 当前候选的直接父源码 |
| compact_script_candidate | 本次提交给回调的候选源码 |
| compact_script_issues | 该候选的完整诊断，包含 severity |
| beforeErrorCount、afterErrorCount | 已采用版本与候选的 error 条数 |
| accepted、reasonCode | 是否采用及进展判定 |
| Trace 执行区间 | 本次评估耗时 |

采用原因 ERROR_FACTS_IMPROVED 对应第 9 节判定；NO_SAFE_PROGRESS 对应其余比较结果。结合前后诊断可查看新增事实、超限和 warning 的变化。

before 与 parent 的区别尤其适合阅读多步前瞻：前者是正式比较基线，后者是生成当前候选的搜索父状态。

### 10.8 结束与返回

以下条件结束本轮搜索：

- error 清零；
- 共享候选预算用完；
- 当前队列搜索完成；
- 源解析产生 CompactDslConversionError，记录 compact.script.parse_failed。

最终 compact.script.decision 记录 candidateCount、changed、remainingErrorCount 与 next，返回当前已采用的完整结果。

remainingErrorCount 为零时继续原后置流程；仍有 error 时，next 为 quality_controller，由原质量控制器处理。

## 11. 连续修复：算例与真实用例

### 11.1 两处独立空间错误：采用后继续修下一处

设 left、right 当前高度都是 20，各自内部需要 40：

~~~text
起点：left 超限 20，right 超限 20
  → 候选 1：left.height = 40
  → 复检：只剩 right 超限 20
  → 采用

采用版本
  → 候选 2：right.height = 40
  → 复检：error 清零
  → 采用并返回
~~~

预算为 1 时，返回已修改 left 的版本及 right 的剩余诊断。对应回归是 test_partial_progress_keeps_latest_source_and_remaining_errors。

### 11.2 Q017：已有两项信息更换主体承载组件

真实批跑源中，两项耳机信息由 SecondaryBody 承载，原校验报告其辅助角色缺少核心信息主体。

~~~text
原两项 label/value
  → primary-content：SecondaryBody 改为 TableText
  → 原信息、绑定和数据行保留
  → Compact 校验、标准转换、完整产物布局校验通过
~~~

该卡使用一个候选，error 从 1 变 0。

### 11.3 Q037：固定槽位＋事实覆盖的组合修复

真实批跑源把固定 InfoBlock 放入普通内容 Region。执行过程为：

~~~text
起点：固定 InfoBlock 槽位错误
  → fixed-slot：使用登记的 W-four-slots，保留原 InfoBlock
  → 复检继续报告 isConnected、chargingStatusDesc 两项展示事实缺失
  → plan-fact：在原辅助区追加两个已有数据路径的展示项
  → 完整复检 error 清零
  → 采用这条两步链的最终结果
~~~

第一步只保存在搜索过程；第二步结果满足 _improved 后整体采用。该卡用了两个候选。

回归进一步核对了：原上下文保持一致，原数据行保持一致，最终源重新复检仍通过；预算只有 1 时返回原采用版本。

### 11.4 同源真实回放结果

2026-10-28 的两组 Debug Tools 真实批跑共 28 个不同请求，得到 27 份原始模型 DSL。用相同源和上下文分别执行原六类规则与扩展十四类规则，结果如下：

| 结果 | 原六类 | 扩展十四类 |
| --- | ---: | ---: |
| 原本通过，保持原稿 | 14 | 14 |
| 原 error，脚本后完整静态通过 | 2 | 4 |
| 原 error，部分改善 | 1 | 2 |
| 原 error，保持当前版本 | 10 | 7 |
| Plan 阶段结束 | 1 | 1 |

13 份原 error DSL 中，完整静态修复通过由 2 份增加为 4 份；扩展后的通过样本是 Q017、Q037、Q103、Q104。
这里统计的通过口径为 Compact 校验、标准转换和完整产物布局校验。规则扩展回放复用了冻结源，本次回放模型调用为 0。

测试夹具在 tests/fixtures/compact_script_real_cases.json 保存五个真实批跑源及原上下文，包含 Q017、Q037 和用于核对采用条件的其它真实错误。

## 12. 服务、校验与模型修复如何衔接

### 12.1 服务的实际接入位置

widget_generation_service.py 的 evaluate_source_dsl() 先调用 evaluate_source_dsl_sync() 得到初次结果，再把同一静态评估函数适配为候选回调：

~~~python
async def evaluate_candidate(candidate: str) -> DslProcessingResult:
    return await to_thread.run_sync(evaluate_source_dsl_sync, candidate)
~~~

普通 Fusion Compact 创建在此调用 repair_static_errors()。配置、预算和当前 Plan 通过参数传入，返回结果赋给 latest_processing_result。

实际调用关系为：

~~~text
生成 Compact
  → 原处理、校验、转换与完整产物评估
  → 结果仍有 error
  → repair_static_errors()
      → 规则产生候选
      → 同一静态评估回调复检
      → 返回采用版本和剩余 error
  → 原质量控制器
      → error 清零：进入主题、保存与交付
      → 仍有 error 且模型修复开启并有预算：模型修当前 Compact，再评估
      → 其余情况：按原错误处理返回
~~~

evaluate_source_dsl_sync() 内部通过 processor.process() 执行原处理链，包括原有结构、绑定及适用的布局重组。脚本接入复用这一评估，保留已有处理顺序。

### 12.2 规则效果怎样单独核对

真实回放与 test_compact_contract_repair.py 的 evaluate() 使用直接校验适配：

~~~text
固定 Compact、Plan、TaskSpec、CardSpec 和协议
  → Plan 覆盖检查
  → validate_compact_dsl()
  → convert_compact_dsl_to_a2ui()
  → 组装 WidgetArtifact
  → ArtifactValidator.validate_layout()
  → DslProcessingResult
~~~

这条适配将原始模型源与候选源分别送入相同门禁，修复改写由本修正器产生。第 11.4 节使用这一口径对照六类／十四类规则。

核心函数通过 evaluate 参数复用同一搜索逻辑；服务接入与独立回放的区别集中在调用方的评估适配。

### 12.3 共享函数与依赖方向

~~~python
from services.compact_outer_recomposition import _serialize, _unique_id
~~~

这两个函数分别负责 Compact JSONL 序列化、生成未占用的组件 ID。规则模块复用它们处理记录与引用。

依赖方向是调试平台调用微服务。修正器在微服务内执行，Trace 由既有记录器落盘，Debug Tools 使用现有 Trace 查看器展示。

### 12.4 三种计数分别表示什么

| 计数 | 含义 |
| --- | --- |
| 候选次数 | 实际执行 evaluate(candidate) 的次数；默认共享上限 12 |
| 内部检查次数 | 每次完整评估内实际执行的多个校验步骤 |
| 模型调用次数 | 生成、Plan、主题或模型修复调用，由各自控制器记录 |

预算对象在本轮生成建立，并跨其模型质量重试共享；模型修复额度单独按原配置管理。

## 13. 开关如何对应代码

| 配置 | 默认 | 实际影响 |
| --- | --- | --- |
| enable_compact_script_repair | false | 静态脚本总开关，显式开启后生效 |
| enable_compact_button_slot_repair | true | 包含指定按钮类型的低阶容器扩容 |
| enable_compact_parent_budget_repair | true | 普通低阶容器扩容及正数间距候选 |
| enable_compact_sibling_space_repair | true | 已有正数权重的横向分配候选 |
| enable_compact_duplicate_click_repair | true | 完全相同 handler 去重 |
| enable_compact_height_closure_repair | true | 明确父 Row 高度后补 Column.height |
| enable_compact_semantic_layout_repair | true | 已登记语义变体、分组、列数及特定整卡分区 |
| enable_compact_known_component_repair | true | 已知正文组件形状纠正 |
| enable_compact_primary_content_repair | true | 辅助信息转登记主体承载组件 |
| enable_compact_action_slot_repair | true | 已有按钮适配登记动作槽位 |
| enable_compact_asset_reference_repair | true | 精确素材引用和 Plan 标题图标 |
| enable_compact_plan_fact_repair | true | 补展示已授权且已初始化的少量事实 |
| enable_compact_fixed_slot_repair | true | 固定 InfoBlock 归入登记四槽布局 |
| enable_compact_numeric_label_repair | true | 用 CardSpec 标题补数值标签 |
| enable_compact_event_target_repair | true | 唯一授权动作的已有参数纠正 |
| compact_script_max_candidates | 12 | 本轮生成累计候选上限，支持 0–32 |

开关是配置布尔值，相关 if 决定是否生成该类候选；每类候选都使用同一原校验门禁。

配置由 cloud/config/config.py 与 default_config.yaml 维护，Debug Tools 的 managed_config.py 提供对应中文选项。

## 14. 如何核对解释和代码一致

### 14.1 测试分别核对哪些行为

| 测试文件 | 主要核对内容 |
| --- | --- |
| test_compact_script_repair.py | 无 error 保持原稿、开关与预算、空间修改、拒绝候选、部分修复 |
| test_compact_script_extensions.py | 重复动作、高度依据、闭合后溢出、配置范围 |
| test_compact_semantic_repair.py | 登记布局、内容保留、方向优先、固定槽和唯一 ID |
| test_compact_repair_progress.py | 独立证据身份及逐项超限比较 |
| test_compact_script_main_chain.py | WebSocket 主链、部分修复后模型交接、零预算、累计预算 |
| test_compact_contract_repair.py | 真实 Q017／Q037 整卡修复、八个独立开关、数据路径、图标、动作候选、前瞻预算 |

回归按职责分别检查规则行为、真实错误重现和服务主链。真实整卡回放按第 11.4 节单独统计。

### 14.2 运行定向回归

在仓库 widget_service/ 目录执行：

~~~bash
python -m pytest tests/test_compact_contract_repair.py tests/test_compact_script_repair.py tests/test_compact_script_extensions.py tests/test_compact_semantic_repair.py tests/test_compact_repair_progress.py tests/test_compact_script_main_chain.py -q
python -m ruff check cloud/services/compact_script_repair.py cloud/services/compact_contract_repair.py cloud/config/config.py tests/test_compact_contract_repair.py tests/compact_script_helpers.py
~~~

在仓库根目录执行配置回归与差异检查：

~~~bash
python -m pytest debug_tools/tests/python/test_managed_config.py debug_tools/tests/python/test_debug_example_config.py debug_tools/tests/python/test_debug_shared_config.py -q
git diff --check
~~~

本轮修正器与主链回归 79 项通过，配置回归 27 项通过，共 106 项。主链接口测试以固定模型输出和主题阶段，执行校验、脚本、控制器及保存流程，可重复运行。

## 15. 源码阅读索引：按文件顺序逐段对应

按函数名定位，以下顺序与源码一致。

| 文件 | 对象 | 阅读重点 |
| --- | --- | --- |
| compact_script_repair.py | 导入、ScriptRepairBudget、规则表 | 共享依赖、累计预算、规则中文名与错误轴 |
| 同上 | _reference_boxes、_height_is_known、_growth_fits_parent | 参考空间、父高与扩容预筛 |
| 同上 | _structural_candidates | 完全重复点击、高度闭合 |
| 同上 | _changed_source、_subtree、_readonly | 记录替换、子树遍历与可重组范围 |
| 同上 | _semantic_candidates | 变体、方向、列数、主辅 Group |
| 同上 | _diagnostics | error 的结构化诊断 |
| 同上 | _split_region_candidate、_top_bottom_candidate | 特定整卡分区转换 |
| 同上 | _error_facts、_improved | 独立错误身份和采用条件 |
| 同上 | static_candidates | 各类候选顺序与去重 |
| 同上 | repair_static_errors | 预算、前瞻队列、复检、采用与 Trace |
| compact_contract_repair.py | CONTRACT_RULES、_changed | 八类规则名与统一源码输出 |
| 同上 | _known_component、_primary_content | 组件及主体信息承载 |
| 同上 | _action_slots、_asset_references | 槽位与精确素材 |
| 同上 | _missing_fact | Plan、Schema、初始化数据与展示引用 |
| 同上 | _fixed_slot、_numeric_label | 固定槽与数值文字标签 |
| 同上 | _event_target | 唯一候选的完整动作参数 |
| 同上 | contract_candidates | 开关调度与统一候选出口 |

若先读三处，按 repair_static_errors → static_candidates → _improved 阅读：先了解循环，再看怎么改，最后看采用依据。

## 16. 整体概括

修正器将已有 error 转为受上下文约束的字段与结构候选，在共享预算内复检和有限前瞻，采用有明确进展的 Compact，再把该版本与剩余诊断交给原后续流程。

## 17. 可优化空间

以下分清当前已实现能力与后续优化方向，作为代码继续演进的落点。

### 17.1 从贪心采用继续发展为有预算的多分支有限搜索

**当前已实现：** 默认最多 12 次候选评估，源码去重；合同类改写支持初始一步后追加至多三步前瞻。每次采用第一个满足 _improved() 的结果。

**继续优化：** 在相同总预算内，保留少量不同分支，比较完整修复效果与改动代价，再决定采用哪条链。

~~~text
当前采用版本
  ├─ 分支 A：局部空间修改 → 完整复检
  ├─ 分支 B：保持方向的登记变体 → 完整复检
  └─ 分支 C：组件合同修改 → 后继规则 → 完整复检
         ↓
  在预算内保留少量有希望的状态
         ↓
  选择满足采用条件、错误更少且改动更小的结果
~~~

代码落点仍是 repair_static_errors() 的 pending 队列与采用位置。候选生成函数、评估回调、错误事实比较、Trace 均可继续复用。

可按以下步骤推进：

1. 为候选状态附加规则链、深度、诊断和修改代价。
2. 以束搜索或优先队列保留少量候选，例如每层最多保留三条。
3. 全部分支继续共享 ScriptRepairBudget，每次真实复检计一次。
4. 先比较剩余错误，再比较已知超限及修改字段、结构改动量；保持方向的局部修改优先。
5. 以原采用版本为基线执行 _improved()，选择符合采用条件的结果。
6. 用同源真实错误回放比较整卡通过数、候选次数与耗时，确定搜索宽度及深度。

其中“每层三条”属于后续可试参数。现有代码的 deque 执行顺序是第 10 节描述的深度优先有限前瞻。

这一优化的目标是：同样有限的校验预算下，让几种合理改法得到比较，并支持多条规则共同解决整卡错误。

### 17.2 继续拓展真实错误对应的规则

**当前已实现：** 六类结构／空间规则加八类组件／内容合同规则，共十四类独立开关。

后续规则优先从真实批跑剩余 error 中归类，沿用当前已登记布局与组件合同。可按以下方向扩展：

| 方向 | 规则所用依据 | 候选改写思路 |
| --- | --- | --- |
| 父子空间联动 | 父区分配、子项最小占用、兄弟预算 | 同时计算报错区及相邻区的可行空间调整 |
| 文字换行后的高度 | 文字宽度合同、可用宽高及行高 | 按现有合同计算所需高度，选择可容纳的登记变体 |
| 主体、标签和图标承载 | 现有 Recipe、Plan 展示角色、原绑定 | 联合调整登记组件与承载区，使各项内容保留在合法位置 |
| 明确动作目标 | Plan 动作事实、TaskSpec 实体路径与参数 | 在上下文能确定唯一目标时，纠正原 handler 参数 |
| 多项展示事实 | 已接受 Plan、授权 Schema、初始化数据 | 先求信息区预算，再将已有事实放入可承载的登记组件 |
| 已登记布局组合 | 当前布局注册表、内容组件、参考几何 | 在现有布局集合中寻找更合适的结构与分组 |

每条规则按同一个开发顺序加入：

~~~text
收集真实原源和上下文
  → 归类 error 与定位字段
  → 明确适用条件和具体修改
  → 接入现有候选出口与独立开关
  → 原校验完整复检
  → 补同类成功、保留原稿、组合修复回归
  → 同源批跑比较通过数与预算消耗
~~~

这样新问题通常沉淀为现有修正器的一条候选规则，继续共用预算、评估、采用判定和调试页面。

### 17.3 让规则命中依据更结构化

空间规则已经使用错误码、源组件和量化超限。合同规则的明确报错识别可继续统一成结构化诊断，例如增加缺失事实的 dataId、要求组件类型和槽位角色。

代码落点是校验诊断的输出及对应候选触发处。这样既保留原报错展示，也让规则直接消费明确字段，便于统计不同错误类型的覆盖与修复效果。
