# 日历日程业务首层规则

## CalendarOverview

- 展示需求与可用候选分开：只根据原始 query 的展示要求标记必需字段，不因为候选、schema 样例、
  派生标题描述或外部事实包含日期、倒计时、标题、多个日程，就把它们全设为必需。外部事实中真正明确的
  展示要求仍须保留；时间段保留起止时刻，全天状态的 false 是有效数据，不按真假判断字段存在性。
- 用户明确两条、三条、各条或全部时保留真实索引及全部要求；未指定列表范围不能仅从候选条数推定
  必须展示所有项。只有一项投影不能证明完整列表，不以 eventCount 样例补造其他日程。
- 数量、开始时间和备注的概览请求仅有首项投影时，可以使用固定标注“首项”“首项备注”的摘要；
  首项标题必须真实可用且已获候选授权，总数仍绑定真实字段。明确要求完整列表、逐条、各自、固定
  多项、禁止只显示首项或禁止额外标题时，不进入该补充分支；不删改首层字段来迁就摘要。
- 原匹配失败后，服务端才尝试受限无动作补充：标题与全天允许缺日期，提醒详情宽卡允许缺更新时间，
  单项会议宽卡允许缺日期或结束时间；缺失项不使用静态文案补齐。日期与结束时间可复用已授权的标题
  上下文，但不能违反用户禁止标题或额外字段的要求。原有完整输入路径保持。
- 新宽卡支持单项日期标题全天、备注结束地点、全天地点及可选时区；双项时间允许各项真实标题、结束
  时间、地点作为可选数据；三项数量详情完整保留每项标题、开始和备注。列表必须完整匹配真实索引和
  字段角色，不能以首项替换其他项，也不能通过删除明确字段迁就模板。
- 新补充分支中的可选显示字段也必须位于候选范围内；schema 单独存在该字段不代表可以展示。
  用户只要下一项时不得扩为两项，明确要求两件事或逐项时不得缩为首项。
- 日程标题地点与天气现象的双业务宽卡可在旧匹配失败后进入受限双 Hero 组合，不要求开始时间、
  日期、温度或按钮。其他业务仍按各自规则处理，首层不为上述后备路线选择模板或补字段。
- 除明确声明双项、三项或四项列表的模板外，其余模板只表达首项日程及其可信附属信息。
- 支持的 TaskSpec 数据路径：
  - `{{dataRoot:GetCalendarEvents}}/eventCount`
  - `{{dataRoot:GetCalendarEvents}}/updatedAt`
  - `{{dataRoot:GetCalendarEvents}}/events/0/startDate`
  - `{{dataRoot:GetCalendarEvents}}/events/0/title`
  - `{{dataRoot:GetCalendarEvents}}/events/0/dtStart`
  - `{{dataRoot:GetCalendarEvents}}/events/0/dtEnd`
  - `{{dataRoot:GetCalendarEvents}}/events/0/eventLocation`
  - `{{dataRoot:GetCalendarEvents}}/events/0/description`
  - `{{dataRoot:GetCalendarEvents}}/events/0/remindTime/0`
  - `{{dataRoot:GetCalendarEvents}}/events/0/timeZone`
  - `{{dataRoot:GetCalendarEvents}}/events/0/isAllDay`
  - `{{dataRoot:GetCalendarEvents}}/events/0/senderName`
  - `{{dataRoot:GetCalendarEvents}}/events/0/importantEventType`
  - `{{dataRoot:GetCalendarEvents}}/events/1/title`
  - `{{dataRoot:GetCalendarEvents}}/events/1/dtStart`
  - `{{dataRoot:GetCalendarEvents}}/events/1/eventLocation`
  - `{{dataRoot:GetCalendarEvents}}/events/2/title`
  - `{{dataRoot:GetCalendarEvents}}/events/2/dtStart`
  - `{{dataRoot:GetCalendarEvents}}/events/2/eventLocation`
- 双日程摘要只有在前两项日程的标题和开始时间四个字段都存在时可选；双日程清点 Full 还必须有
  `eventCount`。`events/1` 必须对应真实第二项，不得用首项数据回退补齐。三场会议 Full 只有在前三项
  日程各自的标题、开始时间和地点九个字段都存在时可选；`events/1`、`events/2` 必须对应真实日程项，
  不得用首项数据回退补齐。其它模板请求地点时必须有首项地点路径。
- 标题日程 Hero 与地点日程 Hero 分开准入：前者要求标题和开始时间，后者要求地点和开始时间，结束时间均可选。
  每个候选必须独立覆盖用户显式要求的展示字段；同时显式要求标题和地点时，不得用其中任一 Hero 丢弃另一字段。
- 日期、全天状态、时区、备注、提醒详情和日程总数只在相应专用模板的完整字段组合可用时展示，缺少字段时
  不得用静态文案或其它日程字段补齐。日程清点 Full 的完整字段组合为 `eventCount`、首项日程标题、
  开始时间和全天状态（备注为可选展示）。`updatedAt` 只用于包含发起人、重要类型和提前提醒的提醒详情 Hero/Full。
- 全天地点 Full 必须有标题、全天状态和地点，不要求时区或起止时间；清点日期地点 Full 必须有日程总数、
  首项日程标题、开始日期、开始时间和地点。这两个 Full 与时区全天、日程清点分别整组匹配，
  不能拼接覆盖或互相回退。
- 带日期会议 WideFull 的原五字段输入完整匹配时保持原布局；受限补充分支可在标题、开始和地点
  真实可用时省略日期或结束时间，不得拆用 `2x2` 模板丢失明确需求。
- 标题时间 Full 必须有标题和开始时间；提醒 Full 必须有标题、开始时间和提前提醒分钟数，
  二者是无显式动作场景下的 Full 形态；用户显式要求动作且对应 Hero 可完整覆盖时，仍走 Hero 加动作路线。
- 原时区日期结束时间 Full 保留完整字段要求。新增同版式的时区起止时间 Full 必须有标题、时区、开始和结束时间；
  日期地点 Full 必须有标题、开始日期和地点；提醒详情 Full 必须有发起人、重要程度、提醒分钟数和更新时间。
  这三组分别匹配，不能拼接覆盖或要求用户补充另一组的字段。提醒详情不要求额外的日程标题或动作。
- 提醒来源 Full 必须有发起人和提前提醒分钟数，不要求重要程度、更新时间或日程标题；日期地点时间 Full
  必须有标题、开始日期、开始时间和地点，不要求结束时间或时区。这两个 Full 与提醒详情、日期地点分别
  整组匹配，不能拼接覆盖或互相回退。
- 下一个日程 Full 的标题、开始时间和地点仍必需；结束时间可选，存在时保持原时间段展示，缺少时只显示开始时间。
  用户明确要求结束时间时，仍必须有真实结束时间路径，不能以开始时间代替。
- 系统当前日期、月/年、农历和相对日期不在当前模板范围内。
- `oneClickServiceLink`、`oneClickServiceType`、`isServiceValid` 和 `entityId` 是日历 Action 的执行或选择参数，
  不是默认展示字段。用户要求“一键加入会议”或“查看日程”时，应选择语义匹配的 Action，不得因为 Action
  引用了这些路径就把它们加入 `requiredOutputFieldsByCapability`；仅当用户明确要求把链接、服务类型、
  服务有效状态或日程 ID 显示在卡片上时，才按展示字段处理，并在模板不能覆盖时退出模板路线。
- 双日程清点 Full 收到引用 `events/0/entityId` 的 `event.viewCalendarEvent` 时，可以把动作绑定到第一条
  日程；第二条仅展示，不得把首项动作复用为第二项动作，也不得将 `entityId` 显示在卡片上。
- 例如“显示下一场会议的标题和时间，并支持一键加入会议”只要求展示
  `{{dataRoot:GetCalendarEvents}}/events/0/title`、`{{dataRoot:GetCalendarEvents}}/events/0/dtStart` 和
  `{{dataRoot:GetCalendarEvents}}/events/0/dtEnd`，同时选择 `event.enter.meeting`；不得额外要求展示其 Action 参数。
- 用户同时要求日期、标题、起止时间和地点，并带一个日历动作时，可以选择带日期的会议 Hero；缺少其中任一必选字段时不得用静态文案补齐。
- 不支持超出已登记列表形态的任意条数、实时状态、分钟倒计时、会议号或待办。三场会议列表仅在九个字段
  完整匹配三场会议 Full 时支持；三项/四项备注详情仅在对应列表合同完整时支持。
  发起人和备注只在完整匹配提醒详情、提醒来源、备注详情或日程清点
  模板时支持，不能据此放宽其它模板。
- 根据 `userQuery` 判断出的必须显示日历字段存在上述支持集合之外的路径时，不得选择。
- `2x2` 多业务场景中，日程 Support 按时间、标题加地点、标题加开始时间或标题加日期四种组合分别覆盖。
  时间 Support 以开始时间为必需数据，标题、结束时间和地点可选；无标题时把开始时间放在 14vp 主行，
  地点或查看提示放在 12vp 辅助行。其余辅助字段按对应模板必需；显式要求的结束时间仍必须可用。
  第一层只提取显式字段与主焦点，由 Search 和 Planner 选择能独立完整覆盖的模板；不得合并多个候选
  的字段覆盖来凑足一个槽位。
- `2x2` 恰好包含两个数据业务和一个显式 Action 时，日历也可以在标题、起止时间和地点都可用且能完整
  使用 `ScheduleOverviewHeroContent@1` 时进入 HeroTitle + HeroContent 组合，并固定作为第二个业务位置。
- 当前存在提醒 Compact（`ScheduleOverviewReminderCompact@1`）与会议详情 Full
  （`ScheduleOverviewMeetingSenderFull@1`）；单业务双 Action 场景当显式字段被对应模板完整覆盖时
  进入模板路线。`2x4` 场景下，会议详情 Full 居中展示可信业务标题、首项日程时间和地点，
  结束时间可选；静态业务标题不覆盖 `/events/0/title`，显式要求日程标题时必须选择实际绑定该字段的模板。
  两个 Action 由 `WideFullTwoCompactLayout@1` 的 `CompactAction@1` 槽位按语义消费。
- 使用包含 `allowCalendarViewFallback` 的 Search 首层协议时，单日历日程且用户未明确禁止按钮、
  操作或跳转，应标记 `allowCalendarViewFallback=true`；旧 LLM 选择器不输出此字段。
  “显示标题和时间”等未提到按钮的需求允许此兜底，“不要按钮”“不需要操作”“只展示不交互”等不允许。
  `action` 仍只提取用户显式要求的动作；不得在首层为了迁就 Hero 而直接选择查看动作。
  Search 后服务端优先匹配 Full，只有没有 Full 但有合适 Hero，且已有唯一、对象一致的
  `event.viewCalendarEvent` 候选时，才默认补一个“查看日程”按钮；不得补展示字段或编造事件。
