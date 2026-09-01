# 第二层业务模板使用规则

- Provider：`com.huawei.calendar.cli`；业务领域统一为 `CalendarOverview`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 当前日历 Provider 没有 `Support` 或 `Compact` 模板，因此不进入双业务或单业务双 Action 的 `2x2`
  组合；不得用 Hero、Full 或 WideFull 冒充缺失形态。
- 可用模板：
  - `ScheduleOverviewNextEventHero@1`：下一个日程 Hero；标题为主数据，起止时间和地点为次要数据；
    可选 `calendarIcon` 与 `headerLabel`。
  - `ScheduleOverviewReminderHero@1`：日程提醒 Hero；展示标题、开始时间和提前提醒；可选
    `headerLabel`。
  - `ScheduleOverviewTimezoneFull@1`：时区日程 Full；展示时区、标题、起止时间和地点；可选
    `headerLabel`。
  - `ScheduleOverviewDateFull@1`：日期日程 Full；展示真实日期、标题、起止时间和地点；可选
    `headerLabel`。
  - `ScheduleOverviewDatedMeetingHero@1`：带日期会议 Hero；展示真实日期、标题、起止时间和地点，
    不接收展示 Prop。
  - `ScheduleOverviewNextEventLocationFull@1`：下一个日程 Full；展示标题、起止时间和地点；可选
    `calendarIcon` 与 `headerLabel`。
  - `ScheduleOverviewMeetingWideFull@1`：宽版会议摘要；展示标题、起止时间和地点；可选
    `timeIcon` 与 `locationIcon`。
  - `ScheduleOverviewMeetingSourceWideFull@1`：带来源图标的宽版会议摘要；`sourceIcon` 必填，
    `timeIcon` 与 `locationIcon` 可选。
- Hero 只用于 `HeroActionLayout@1` 加一个 `PillAction@1`；Full 只用于 `SingleFocusLayout@1`，
  或在存在语义匹配图标素材时用于 `FullIconActionLayout@1` 加一个 `IconAction@1`。WideFull 当前只作
  `2x4` 预留。
- `headerLabel` 只能逐字复用 `cardComposition.businessTitleCandidate`，没有可信标题时省略。
- 已有 Provider 全局路径的值必须由模板 `data` 绑定；Props 只能使用本轮 Prompt 下发的可信文本或素材，
  不得输出数据路径。
- 选择能够完整表达用户显式字段且自身 `primaryData` 与 `secondaryData` 全部可用的模板。缺少真实日期、
  时间、提醒、时区或地点时，不得用静态文案补齐。
- 素材参数不绑定固定素材 ID，只从本轮素材候选中按语义匹配：
  - `sourceIcon`：日历应用、日程来源或会议来源语义，使用 Theme 主内容色着色；
  - `calendarIcon`：日历本或日程管理语义，使用 Theme 辅助内容色着色；
  - `timeIcon`：时钟、时间或日程时刻语义；
  - `locationIcon`：地点、位置、会议室或地图标记语义。
- 同一模板的多个素材槽位必须分别匹配语义，不得复用同一素材填充来源、时间和地点。
- Action 图标必须与动作语义一致；`PillAction@1` 没有匹配素材时省略 `icon`，不得复用业务内容素材。
