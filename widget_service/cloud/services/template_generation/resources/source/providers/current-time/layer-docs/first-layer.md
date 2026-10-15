# 当前时间高级组件首层规则

## CurrentTimeOverview

- 支持的 TaskSpec 数据路径：`{{dataRoot:GetCurrentTime}}/currentDate`、`{{dataRoot:GetCurrentTime}}/dayOfWeek`、`{{dataRoot:GetCurrentTime}}/lunarDate`、`{{dataRoot:GetCurrentTime}}/updatedAt`。
- 适用于用户询问今天日期、星期几、农历或数据更新时间等当前时间信息：`currentDate`、`dayOfWeek`、`lunarDate` 表达今天本身，`updatedAt` 只是端侧完成该时间数据组装的新鲜度时间戳，不代表任何事件的发生或提醒时间。
- 用户只要日期、星期或农历时优先 `CurrentTimeOverviewDateFull@1`；只有用户明确要求查看数据更新时间或时间戳时，才使用 `CurrentTimeOverviewUpdatedFull@1` 或 `CurrentTimeOverviewSupport@1`，更新时间不得冒充日期主卡。
- 农历由 DateFull 可选行承载，端侧缺失或为空字符串时省略该行，不得补造农历信息。
- 本业务全部模板无操作入口、无素材槽位；是否单独成卡、是否与其它业务（如日程、天气、电量）组合由服务端二层规划决定，首层只负责选举用户显式要求的字段。
- 本业务为配对专用：不得单独成卡，只能与其它业务组合出现在同一张卡片中。用户仅询问日期、星期、农历或更新时间而不涉及其它业务时，同样按上述规则选举字段，由服务端判定无法组合后拒绝；不得为此虚构其它业务。
- 根据 `userQuery` 判断出的必须显示字段不是上述四个路径时，不得选择。
