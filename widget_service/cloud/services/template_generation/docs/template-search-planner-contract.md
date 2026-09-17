# Template Search 与 Planner 交互契约

本文描述默认 `firstLayerComponentSelector=search` 链路中五个模块的职责和数据边界。目标是让 Search
只回答“哪些模板在当前卡片尺寸与数据条件下可用”，由确定性 Planner 统一处理布局、主题、Action
消费位置和业务顺序，第二层 LLM 只在不超过三个完整 Plan 中选择。该默认链路同时用于 2x2 和 2x4。

## 1. 总体链路

```text
第一层 LLM
  -> 数据可用性 Search
  -> 确定性 Template Planner
  -> 第二层 LLM
  -> Validator / Compiler
```

任何模块都不得接管相邻模块的决策：Search 不读取布局和 Action，第二层 LLM 不重新组合 Plan，校验器
不推测模型意图。

## 2. 第一层 LLM

输入包括用户描述、TaskSpec 中可展示的数据字段和 Action 候选，以及 Provider 的字段语义说明。第一层只做
用户意图标定，输出：

```json
{
  "requiredOutputFieldsByCapability": {
    "ViewWeather": [
      "/current/temperatureText",
      "/current/airQuality",
      "/location/districtName"
    ]
  },
  "primaryOutputFieldByCapability": {
    "ViewWeather": "/current/temperatureText"
  },
  "action": []
}
```

- `requiredOutputFieldsByCapability` 只包含用户显式要求展示的字段。
- `primaryOutputFieldByCapability` 是稀疏映射。每个业务最多一个显式主焦点；无法从描述中确定时不输出该
  capability。值必须同时存在于该 capability 的显式字段数组中。
- `action` 只包含用户显式要求且来自 TaskSpec 候选的事件 ID。第一层按尺寸声明上限：2x2 为两个、2x4 为四个；Planner 再检查实际布局容量。
- 输出不包含 `themeId`、`schemaVersion`、组件、模板、布局或 Props。服务内部仍使用严格模型校验字段、
  JSON Pointer、唯一性和关联关系。

## 3. Search

Search 输入第一层意图、卡片尺寸、TaskSpec、CardSpec 已批准的数据绑定以及同一份 Template Registry。
它只执行：

1. 校验 capability 和显式字段均来自上游候选。
2. 按卡片尺寸过滤模板 Variant。
3. 使用模板定义中的必需字段检查运行时数据可用性与类型。
4. 使用 `primaryData + secondaryData + optionalData` 计算显式字段覆盖；`optionalData` 可以形成覆盖，
   但不会成为模板准入的必需数据。
5. 2x2 只保留独立完整覆盖的模板；2x4 保留已验证的部分覆盖候选，将组合覆盖交给 Planner。宽版 Search 不按前 24 个模板截断，避免可选字段增多挤掉可行形态；第二层只接收最终最多三个 Plan 的候选并集。

Search 不读取主题、布局、Action 数量或 Action 消费位置，也不对业务顺序做判断。输出不重复模板自身的
输入定义：

```json
{
  "cardSize": "2x2",
  "businessCandidates": [
    {
      "capabilityId": "ViewWeather",
      "businessId": "WeatherOverview",
      "explicitFields": [
        "/current/temperatureText",
        "/current/airQuality",
        "/location/districtName"
      ],
      "candidates": [
        {
          "templateId": "WeatherOverviewFull@1",
          "coveredExplicitFields": [
            "/current/temperatureText",
            "/current/airQuality",
            "/location/districtName"
          ]
        }
      ]
    }
  ]
}
```

这里 `required_paths` 是模板运行所需的硬前置数据，缺失时模板不可用；`available_paths` 是模板能够消费并
展示的全部字段集合，包含 required、secondary 和 optional。用户显式字段用 `available_paths` 判断覆盖，
不能用 `required_paths` 代替。

## 4. Template Planner

Planner 是确定性服务模块，输入第一层意图、Search 结果、卡片尺寸、TaskSpec 和 Registry。它通过
`templateId` 从 Registry 重新取得模板定义，并联合规划：

- 精确 Layout Template；
- 有序业务槽位及每个槽位的精确业务 Template；通用指标通过 `fieldBindings` 锁定每个实例的路径参数；
- Theme；
- 每个 Action 的消费者：根 Action Template 或某个支持 `actionId` 的垂域业务 Template；
- 显式字段覆盖与主焦点匹配信号。

硬约束是每个 Plan 必须覆盖用户全部显式字段并消费每个已选 Action 恰好一次。`2x2` 单业务有显式主焦点
时，优先只保留该字段命中模板 `primaryData` 的 Plan；未声明主焦点时按模板主数据、次数据、可选数据的
匹配程度稳定排序。双业务 Action 可以由 `HeroTitleContentActionLayout` 的根 Action 消费，也可以由
`TwoSupportLayout` 中声明了可选 `actionId` 的 Support 模板消费，因此 Planner 不会先固定布局再判断
Action。

Planner 去重、排序后最多输出三个原子 Plan。当前二层可信 Contract 使用单一 Theme，因此同一批下发的
Plan 共享排名第一的可用 Theme；不同 Theme 不在第二层混合。单业务与 HeroContent 主业务的 Theme
在请求级 Registry 可用集合内按业务语义和主题场景元数据稳定选择；`TwoSupportLayout` 使用覆盖全部业务
能力的布局专用 Theme。

每个业务组至少提供一个可进入 `TwoSupportLayout` 的规范化 Support。单个 Support 槽位固定为两行文本
信息：第一行使用主内容色表达主信息，第二行使用辅助内容色表达辅助信息；两行均为单行省略。Support
提供可选 `actionId`，仅在 Planner 把已批准事件分配给该业务槽位时消费，未分配时编译器省略 `onClick`。

Support 通过模板条目的 `supportedEventIds` 声明内嵌事件白名单。Planner 按事件类型过滤业务位置，
保留完整动作实例 ID，再枚举合法分配；不能仅根据是否声明 actionId 分配。缺失或空白名单禁止绑定。
天气必须同城市，日程必须同一展示项；无合法归属时该 Plan 不可用，不能移给搭档业务或静默丢弃动作。
完整清单和验证规则见 [Support 事件归属契约](support-template-action-policy.md)。

## 5. 第二层 LLM

第二层输入最多三个完整 Plan，以及这些 Plan 涉及的 Template 完整 Props 签名、可信字符串、数字、素材
和 Provider 二层说明。它只能：

1. 完整选择一个 Plan；
2. 按所选 Template 的签名补全开放 Props 和可信素材；
3. 输出一棵以该 Plan 的 Layout Template 为根的调用树。

它不能更换 Layout、调整业务顺序、替换业务 Template、移动 Action 消费位置，或从多个 Plan 抽取部分
元素重新组合。

## 6. Validator / Compiler

编译前先对调用树执行原子 Plan 校验：根 Layout、直接业务 Template 的 ID 与顺序、根 Action Template
及事件 ID、业务 Template 内嵌 `actionId` 的槽位、通用指标路径参数必须完整匹配同一个 Plan。若调用树跨 Plan 混用，或同时
匹配零个或多个 Plan，直接拒绝；唯一匹配的 `planId` 记录到内部展开统计和日志。之后才进入原有 Props、
数据绑定、Action 唯一消费、节点预算、主题展开和 A2UI 转换校验。

业务模板展开前独立执行与 Planner 共用的事件白名单和对象归属校验，覆盖错误 Plan 与旧兼容入口。

旧 `firstLayerComponentSelector=llm` 路径保留原有 `TemplateRouteSelection` 行为用于兼容，不使用新的
Planner 原子 Plan 契约。

## 7. 横版组合规则

`wide_template_planner.py` 为公共 Planner 提供完整横版组合，复用同一套主题裁决、排序、去重与编译契约。
它按每个 capability 的显式字段枚举完整覆盖，再匹配已登记布局的业务形态与动作位置。布局失败仅淘汰
该组合；不得因为候选集合中存在 Full + Compact 就拒绝其中可行的 Hero + Hero 或 Full + Full。

- 最多四个业务实例；同一通用指标模板可以出现两次，但分别固定不同的 `valuePath`。
- 双指标模板固定 `firstValuePath`、`secondValuePath`，两个字段必须不同。通用指标只消费未被专用模板
  覆盖的已验证标量字段；按实际实例数计数，不能覆盖或替换其它 capability 的必选槽位。
- 第一层声明主焦点时优先匹配专用模板主字段，再优先减少通用实例数和业务实例总数；其它排序沿用
  主、次、可选字段匹配，并在可行时保持请求中的业务顺序。同一批 Plan 共享主题和业务集合。
- 双面板根按钮在 `businessPosition` 中记录归属，按面板位置排列。归属来自当前业务已启用模板的
  `supportedEventIds`，动态天气/日程跳转还须匹配该模板的数据对象。已批准固定目标可通过业务事件
  白名单证明入口归属；没有可证明归属的动作只能进入独立共享操作区，不能放到搭档面板下。
- 根按钮声明 `actionTemplateId`；内置按钮声明业务位置且不占根动作槽位。每个动作实例只消费一次。
- 单业务单动作若存在支持该事件、覆盖全部字段的 WideFull，优先使用 WideFullOnlyLayout 的内置按钮
  计划，继续执行 `supports_business_action` 的严格对象校验；未满足条件时继续枚举其它完整布局。
- 2x4 四个动作仅支持单业务 + 四个 LargeIconAction 的既有专用布局；三个动作或容量不足返回未命中。
  2x2 不扩展动作容量。动作、字段或业务不能静默删除。

通用指标在数据投影时使用 Plan 的精确路径并集，不按同领域其它模板的字段并集扣除；编译器把相对路径
拼接到唯一的健康数据绑定根，缺失或多根均拒绝。缺少可选评分等字段时，睡眠 Full 的主信息区弹性占位，
可选辅行直接位于业务根，避免产生空容器。

`retrieve_template_variants`、`plan_embedded_wide_full` 与无 Plan 的二层布局推导仅保留给旧兼容入口和
直接调用者；默认生产链路不回落到这些路径。已选完整 Plan 生成失败时沿用现有第二层修复与失败语义。
