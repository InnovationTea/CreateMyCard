# Template Search 与 Planner 交互契约

本文描述默认 `firstLayerComponentSelector=search` 链路中五个模块的职责和数据边界。目标是让 Search
只回答“哪些模板在当前卡片尺寸与数据条件下可用”，由确定性 Planner 统一处理布局、主题、Action
消费位置和业务顺序，第二层 LLM 只在不超过三个完整 Plan 中选择。

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
- `action` 只包含用户显式要求且来自 TaskSpec 候选的事件 ID。
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
5. 只保留能够独立覆盖该业务全部显式字段的模板。

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
- 有序业务槽位及每个槽位的精确业务 Template；
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
及事件 ID、业务 Template 内嵌 `actionId` 的槽位必须完整匹配同一个 Plan。若调用树跨 Plan 混用，或同时
匹配零个或多个 Plan，直接拒绝；唯一匹配的 `planId` 记录到内部展开统计和日志。之后才进入原有 Props、
数据绑定、Action 唯一消费、节点预算、主题展开和 A2UI 转换校验。

旧 `firstLayerComponentSelector=llm` 路径保留原有 `TemplateRouteSelection` 行为用于兼容，不使用新的
Planner 原子 Plan 契约。
