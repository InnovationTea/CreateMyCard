---
promptGroup: hybrid-body-generator
fragmentId: template-composition
order: 10
promptVersion: hybrid-body-prompt/0.25
protocolVersion: tersedsl-nested-2-hybrid/0.2
contractVersion: hybrid-body-contract/0.5
---

<!-- prompt:start -->
输出必须以 `Template("card@1", cardParams, content)` 为唯一根。card@1 是可组合的 Card 外壳 Template，负责 Card 背景、标题区、内容预算和底部 Action；它接受恰好一个 content 容器子树。第一层 requestTemplate 中除 card@1 外的 Template 是可选局部宏，合适时用于减少 Token 和复用 UX；不合适时直接使用标准组件，不得为了命中 Template 丢失 mustKeep。

普通组件和局部 Template 可以作为兄弟或嵌套在 content 中；局部 Template 不接收 children。card@1 只允许出现在根并接收一个 content。Template 参数只能使用本次可信字面量。Action Template 仅在本次契约显式下发 contentActionCandidates 时可用。最终 A2UI 中不存在 Template 节点；服务端会先做静态展开，再执行完整 Catalog、节点、深度、Action 和安全校验。

当已请求的局部 Template 参数可由 dataFacts 完整满足，并且它恰好覆盖一个完整语义组时，优先用该 Template 表达这个局部单元；标准组件继续负责各单元之间的组合，以及 Template 未覆盖的事实。不得为了使用基础组件而拆散一个已完整匹配的 Template 语义组。

请求若包含 `advancedComposition`，其中的 `primaryDomain`、`advancedComponentIds` 和 `adaptiveTemplateId` 是服务端根据数据 Schema、领域组合白名单与尺寸预算确定的只读语义计划。content 必须保持其中的主次和并列关系，但这些名称不是可输出的运行时组件，也不授权新增数据、字面量、Template 或 Action。没有 `adaptiveTemplateId` 时按现有 Template 能力和数据事实自由编排；最终仍只输出批准的标准组件与局部 Template。

选择 Template variant 时，不仅类型必须匹配，参数值还必须符合参数 description 的语义；在同一语义组可用的 variant 中，选择能够消费全部相关 dataFacts 的 variant。禁止仅因为 string 类型相同就把素材地址填入文字、标题、符号、标签或数值参数。

局部 Template 应表达可复用的局部语义和排版单元；content 根布局和各信息区编排优先使用标准 Column、Row、Text、Image。存在多个信息区时，应按输入事实的主副、并列关系和 Template 的 small、medium、hero 尺寸说明选择布局，并与标准组件组合。card@1 只提供通用外壳，不固定内部内容组织。

根据 request 与 data 自主组织信息层级，不得依赖预置场景源码、固定组件数量或固定 Template 次数。同级的重复数据应逐项保留，并根据可用空间选择 Row、Column 或 Grid；高优先级信息可使用 hero，辅助信息可使用 small/medium。Template 的调用次数由输入数据和信息层级决定，不能依赖任何固定数量。

同一局部 Template 同时使用多种 size 时，先按信息优先级和 size 分组：同级 small/medium 单元放入共同的 Row 或 Grid，hero 作为独立的全宽兄弟区；只有输入明确表示同等主次时，才把 hero 与 small/medium 放入同一行。每组数量完全由独立 dataFacts 决定。

`dataFacts` 用 source/path 标识相互独立的输入事实。每条事实都必须被标准组件或 Template 参数消费；相同的数值、文案或素材不代表同一事实，禁止按值去重。一个字段作为 hero 主指标后，也不能据此删除 path 不同的并列 small/medium 指标。最终输出前必须逐项核对所有 dataFacts，允许 total、单位等字段由 Template 内部语义隐式消费，但不得遗漏独立实体或指标。

只能显示 dataFacts、Card 候选或 Action 候选中明确给出的文字。裸值没有伴随标签时，只显示该值，禁止自行补充字段名、解释、单位或标签。

Template Registry 若声明“建议组合容器 LayoutToken”，在同一 Template 重复出现或混合多个尺寸时，优先把该 Token 用在这些局部单元的最近公共容器；它只是可复用的排版建议，若 request 与 data 需要其他组织方式，可以选择别的允许布局。

Template Registry 若声明“同一语义组多尺寸建议顺序”，同一 Template 的不同 size 分组按该顺序排列；每个 size 的调用数量仍完全由独立 dataFacts 决定。没有声明时，继续按输入的主副与并列关系自主排序。

Template Registry 若声明“多尺寸布局”，inlineSizes 的实例放入共同 Row/Grid 并按 maxInlineItems 自动换组，fullWidthSizes 的实例作为最近公共容器的独立全宽子项；若同时声明 inlineLayoutToken/fullWidthLayoutToken，优先把对应 Token 用于该分组的最近容器。这只约束相应 Template 实例的组合方式，不改变数据决定的实例数量。

Template 参数必须保持 data 中的原始类型和值：string 逐字复制已提供字符串，number 直接使用已提供数值。不得把数值自行格式化成带 `%`、单位或说明的新字符串；若某个 Template 的参数类型无法由当前 data/素材直接满足，改用其他 Template 或标准组件。

传给 Template 的同一 source/path 会由 Template 自己渲染；该事实不得再用 Text、Image 或兄弟 Template 重复展示。只有 source/path 相同才算重复；输入含多个不同 path 的独立实例时必须分别保留，即使它们的值相同。

为每条 dataFact 选择唯一消费位置后再输出。除非 Template 参数说明明确要求 Action 展示文案，Action Template 中除 actionId 外的 label、value、title、detail 等业务展示参数必须来自 dataFacts；不得用 contentActionCandidates 的 label 替换业务数据，也不得在 Template 外重复同一事实。

素材候选中的 id 只用于识别候选。Image 第一参数和 Template 的图片参数必须使用本次 Prompt 明确列出的素材 src，不能把 asset id 当作图片地址。

素材不是必须全部消费的数据事实。为 Image 或 Template 图片参数选择素材时，按参数说明、相邻业务事实与素材 description 的语义匹配选择，不得为了用完候选而把无关素材填入局部单元。

若契约显式声明 requiredAssetSources，这些内容素材必须各消费至少一次；优先传给语义匹配的 Template 图片参数，否则使用标准 Image。未列入 requiredAssetSources 的其余素材仍按语义需要选择。

Template Registry 若为素材参数声明语义标签，并且素材候选提供 semanticTags，则该参数只能选择至少包含全部声明标签的素材；标签约束优先于名称猜测。

素材 src 只能传给参数说明中明确表示 icon、image、asset、source、src、图标、图片、素材或资源的参数；其他 string 参数禁止使用素材 src。

若 Card 外壳字段约束不允许 title/subtitle，而未被 Template 消费的 dataFact 是上下文标题，则把它保留在 content 中；存在语义匹配素材时可用标准 Row 组合 Image 与 Text，否则使用 Text。已经由 Template 消费的标题不得再次显示。
<!-- prompt:end -->
