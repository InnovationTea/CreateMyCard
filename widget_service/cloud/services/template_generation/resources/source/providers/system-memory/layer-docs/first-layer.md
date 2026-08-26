# 系统内存高级组件首层规则

## ResourceUsageOverview

- 支持的 TaskSpec 数据路径：
  - `{{dataRoot:GetSystemMemInfo}}/usagePercent`
  - `{{dataRoot:GetSystemMemInfo}}/availableMemText`
  - `{{dataRoot:GetSystemMemInfo}}/totalMemText`
- 当前只支持内存占用，三项路径必须完整，0% 合法。
- 不支持存储/磁盘、缓存、进程、CPU/GPU、swap、趋势、历史曲线或仅 `freeMemText`。
- 根据 `userQuery` 判断出的必须显示系统资源字段存在支持集合之外的路径时，不得选择。
