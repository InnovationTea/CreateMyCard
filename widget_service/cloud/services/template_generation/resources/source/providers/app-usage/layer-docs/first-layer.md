# 应用使用时长高级组件首层规则

## AppUsageOverview

- 支持的 TaskSpec 数据路径：
  - `{{dataRoot:GetAppUsageDuration}}/appUsage/appName`
  - `{{dataRoot:GetAppUsageDuration}}/appUsage/durationText`
  - `{{dataRoot:GetAppUsageDuration}}/updatedAt`
- 只支持用户明确指定的单个应用及其当日使用时长；请求更新时间时必须有 `updatedAt`。
- 不支持总屏幕时间、多应用、排行、限额、超限、剩余时长、比例、进度、趋势或分类汇总。
- 根据 `userQuery` 判断出的必须显示应用使用字段存在支持集合之外的路径时，不得选择。
