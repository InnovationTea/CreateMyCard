# 第二层业务模板使用规则

- Provider：`com.huawei.current-time.cli`；业务领域为 `CurrentTimeOverview`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- `CurrentTimeOverviewDateFull@1` 大号展示 `/currentDate` 公历日期，顶部可选 `/dayOfWeek`，底部可选 `/lunarDate`；用于 `SingleFocusLayout@1` 等无操作的 2x2 Full 槽位，用户只要日期、星期或农历时优先选择。
- `CurrentTimeOverviewUpdatedFull@1` 大号展示 `/updatedAt` 完整更新时间戳，顶部可选 `/currentDate`，底部可选 `/dayOfWeek`；只用于用户明确要求查看数据更新时间或时间戳的场景；`updatedAt` 是端侧完成时间数据组装的新鲜度时间戳，不得当作事件发生时间、提醒时间或“现在几点”展示。
- `CurrentTimeOverviewSupport@1` 主行展示 `/updatedAt`，辅助行固定“更新时间”，可选补充 `/currentDate` 与 `/dayOfWeek`（数据同时存在时并列展示，不得因日期存在而隐藏用户明确要求的星期）；只用于 `TwoSupportLayout@1` 的业务槽位，与另一业务的 Support 配对；不接收素材参数，不内嵌 Action，不占用操作位。
- 三个模板均不接收 Props、无素材语义标签、无操作入口；不得为时间数据虚构标题、地点或事件名。
- `/lunarDate` 端侧可能返回空字符串；DateFull 中缺失时整行省略，不得补造农历信息。
- `/currentDate` 与 `/updatedAt` 同时可用且用户显式要求更新时间时优先 UpdatedFull；只要日期时优先 DateFull；用户显式要求更新时间且卡片已分配另一业务 Support 时选择 Support 形态。
- 选择模板前必须确认主数据路径可用；三个模板的主数据均为必选绑定，缺失时不得选择。
