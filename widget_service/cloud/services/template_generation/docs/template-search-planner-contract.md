# Template Search 与 Planner 交互契约

本文描述默认 `firstLayerComponentSelector=search` 链路中五个模块的职责和数据边界。目标是让 Search
只回答“哪些模板在当前卡片尺寸与数据条件下可用”，由确定性 Planner 统一处理布局、主题、Action
消费位置和业务顺序，第二层 LLM 只在不超过三个完整 Plan 中选择。

## 1. 总体链路

```text
第一层 LLM
  -> 数据可用性 Search
  -> 日历默认查看动作策略（仅适用场景）
  -> 电量默认设置动作策略（仅适用场景）
  -> 确定性 Template Planner
  -> 第二层 LLM
  -> Validator / Compiler
```

任何模块都不得接管相邻模块的决策：Search 不读取布局和 Action，第二层 LLM 不重新组合 Plan，校验器
不推测模型意图。

## 2. 第一层 LLM

默认 Search 路线对日程提醒父路径执行受限归一化：仅 `2x2 / GetCalendarEvents` 的候选
`/events/<原索引>/remindTime`，且所有同能力绑定根的 TaskSpec 都将该位置投影为非空标量字段数组时，
映射为同一日程的 `/remindTime/0`。不根据样例值补造字段；空数组、对象数组、嵌套数组与缺失字段不转换。
已显式指定提醒索引的路径不变，原始请求和 TaskSpec 不变。归一化副本用于首层候选字段及白名单；
首层若仍返回原候选父路径，在可信模板限制和 Search 前同步归一化显式字段与主焦点，并按原顺序去重。
Search 直接入口也使用同一规则，之后仍严格检查候选白名单、字段类型与模板覆盖。其它业务、其它字段、
宽卡与旧 LLM 选择路线保持原行为；不将任意数组父路径与任意元素视为等价。

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
- `allowCalendarViewFallback` 是可选布尔值，兼容旧首层输出时默认为 `false`。仅当用户请求单日历日程
  且未明确禁止按钮、操作或跳转时，首层标记为 `true`；它只表达用户是否允许默认查看入口，不代表已选
  Action。首层仍不判断 Full/Hero 是否可用，也不直接把默认查看事件加入 `action`。
- 输出不包含 `themeId`、`schemaVersion`、组件、模板、布局或 Props。服务内部仍使用严格模型校验字段、
  JSON Pointer、唯一性和关联关系。

`allowBatterySettingsFallback` 同样是可选严格布尔值，旧首层输出缺省为 `false`。仅向 `2x2`、候选
能力只有 `GetPhoneBatteryInfo` 的首层提示词暴露该字段及电量专用说明，其余业务的提示词保持不变。
首层只标记用户是否允许默认入口：未明确禁止按钮、操作或跳转为 `true`，明确禁止为 `false`；
`action` 仍只包含显式要求的动作，不为适配 Hero 补字段、删字段或判断模板可用性。

## 3. Search

Search 输入第一层意图、卡片尺寸、TaskSpec、CardSpec 已批准的数据绑定以及同一份 Template Registry。
它只执行：

1. 校验 capability 和显式字段均来自上游候选。
2. 按卡片尺寸过滤模板 Variant。
3. 使用模板定义中的必需字段检查运行时数据可用性与类型。
4. 使用 `primaryData + secondaryData + optionalData` 计算显式字段覆盖；`optionalData` 可以形成覆盖，
   但不会成为模板准入的必需数据。
5. 只保留能够独立覆盖该业务全部显式字段的模板。
6. 为每个候选返回 `availableDataFields`：本轮候选字段中被模板实际引用、TaskSpec 已提供且类型兼容的
   完整绑定路径，包含可用的非显式字段。按完整路径去重，不同绑定根分别计算；缺失字段、未引用字段、
   静态文案、图标和仅用于事件参数的字段不计入。该字段只提供数据事实，不在 Search 中排序。

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
          ],
          "availableDataFields": [
            "/data/weather/current/airQuality",
            "/data/weather/current/temperatureText",
            "/data/weather/location/districtName"
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

进入 Planner 前，服务端仅对 `2x2`、唯一 `GetCalendarEvents / CalendarOverview` 业务、无显式已选
Action 且 `allowCalendarViewFallback=true` 的请求应用默认查看策略：

1. Search 存在能覆盖全部显式字段且必需数据齐全的 Full 时，保持无动作。
2. 没有 Full、但有同样通过 Search 的 Hero 时，检查已批准候选中是否恰好有一个
   `event.viewCalendarEvent`，且参数引用与所有候选 Hero 展示的日程对象一致；满足才补选该事件。
3. 没有 Hero、动作缺失、重复或指向其他日程时不补选。禁止凭空构造事件、补数据或删除用户要求的字段。

补选结果同时用于 Planner 和后续 TaskSpec 动作筛选，保证二层按钮、事件参数及最终编译一致。
默认文案沿用已注册的“查看日程”，可信候选显式提供文案时仍优先使用该文案。显式动作请求保留原语义；
双业务、其他业务和宽卡不使用此兜底。用户说“不要按钮”“不需要操作”“只展示不交互”等时禁止补选；
单纯没有提到按钮不属于禁止。此策略不改变 Search 的纯数据职责。

电量策略独立应用于 `2x2`、唯一 `GetPhoneBatteryInfo / BatteryOverview` 业务、无已选 Action 且
`allowBatterySettingsFallback=true` 的请求：

1. 已有可用 Full 时保持原结果；没有 Full 且有通过 Search 的 Hero 时才检查设置入口。
2. 已批准候选中必须恰有一个 `event.open.settings.battery`，调用为 `clickToDeeplink`，参数精确为
   `intentName=Settings`、`bundleName=com.huawei.hmos.settings`、
   `abilityName=com.huawei.hmos.settings.MainAbility`、`uri=battery`，才补选该事件。
3. 默认文案沿用已注册的“电池设置”，候选提供可信文案时仍沿用该文案。候选缺失、重复、参数不符、
   只有 Compact/Support 也不触发。完全没有电池设置候选且显式字段包含 `/healthStatusDesc` 时，
   可改为复用唯一合法的 `event.open.settings.batteryHealth` 候选，按钮文案为“电池健康”，
   目标参数除 `uri=smart_charge_battery_health` 外与上述系统设置参数一致。
   有电池设置候选但其重复或非法时，不用健康入口掩盖错误；省电模式不用于默认入口。

显式动作和画廊指定动作保持原集合，Full 不会删除它们。禁止按钮、其他业务、混合业务、宽卡和旧 LLM
选择路线不受此策略影响。原始 TaskSpec、候选数据和显式字段不变，仍由 Planner 校验完整字段覆盖及
动作消费；该策略只增加此前无 Full 的合法 Hero 入口，不放宽 Search 或全局动作规则。

`BatteryOverviewPercentLevelHero@1` 是 Search 专用的电量补充分支：仅单电量 `2x2`，且用户显式字段
恰好为 `/batterySOCText` 和 `/batteryCapacityLevelDesc`，才检查该模板。在类型、必需输入和完整覆盖
校验后，只要任一旧模板仍能完整覆盖，就移除新变体候选；旧模板无完整覆盖时才保留它。
额外候选字段不触发此分支；混合业务、宽卡、旧检索适配器和旧 LLM 选择路线不暴露该变体。
禁用模板与可信画廊模板限制仍生效，不能用新变体绕过；不从百分比样例反推数值绑定。

Planner 是确定性服务模块，输入第一层意图、Search 结果、卡片尺寸、TaskSpec 和 Registry。它通过
`templateId` 从 Registry 重新取得模板定义，并联合规划：

- 精确 Layout Template；
- 有序业务槽位及每个槽位的精确业务 Template；
- Theme；
- 每个 Action 的消费者：根 Action Template 或某个支持 `actionId` 的垂域业务 Template；
- 显式字段覆盖与主焦点匹配信号。

硬约束是每个 Plan 必须覆盖用户全部显式字段并消费每个已选 Action 恰好一次。`2x2` 单业务有显式主焦点
时，优先只保留该字段命中模板 `primaryData` 的 Plan。排序依次比较显式主焦点命中数、显式字段的主数据
匹配数、数据使用量、次数据匹配数，最后减少仅落在可选数据中的显式字段数。数据使用量取 Plan 全部业务
模板 `availableDataFields` 的去重并集大小；同一请求可用数据总量固定，因此按使用字段数排序等价于按
数据使用率排序。主数据优先级保持高于使用量，同分时保留既有候选顺序。双业务 Action 可以由
`HeroTitleContentActionLayout` 的根 Action 消费，也可以由
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

1. 按下发优先级，在能合法补全开放 Props 的候选中优先完整选择排名靠前的 Plan；
2. 按所选 Template 的签名补全开放 Props 和可信素材；
3. 输出一棵以该 Plan 的 Layout Template 为根的调用树。

它不能更换 Layout、调整业务顺序、替换业务 Template、移动 Action 消费位置，或从多个 Plan 抽取部分
元素重新组合。

## 6. Validator / Compiler

编译前先对调用树执行原子 Plan 校验：根 Layout、直接业务 Template 的 ID 与顺序、根 Action Template
及事件 ID、业务 Template 内嵌 `actionId` 的槽位必须完整匹配同一个 Plan。若调用树跨 Plan 混用，或同时
匹配零个或多个 Plan，直接拒绝；唯一匹配的 `planId` 记录到内部展开统计和日志。之后才进入原有 Props、
数据绑定、Action 唯一消费、节点预算、主题展开和 A2UI 转换校验。

业务模板展开前独立执行与 Planner 共用的事件白名单和对象归属校验，覆盖错误 Plan 与旧兼容入口。

旧 `firstLayerComponentSelector=llm` 路径保留原有 `TemplateRouteSelection` 行为用于兼容，不使用新的
Planner 原子 Plan 契约。
