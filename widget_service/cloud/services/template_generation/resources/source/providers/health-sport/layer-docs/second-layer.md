# 健康运动高级组件二层规则

## ActivityOverview

- 调用：`Template("ActivityOverview@1", "steps|stepsSupport|dailySummary|dailySummaryWide", params)`。
- 只有热量和距离完整时使用 `dailySummary`；2x4 单业务使用 `dailySummaryWide`；多业务 Support 使用 `stepsSupport`。
- `params` 只允许语义匹配的 `stepsIcon`、`caloriesIcon`、`distanceIcon`。

## WorkoutOverview

- 调用：`Template("WorkoutOverview@1", "latest", params)`。
- `params` 只允许语义匹配的 `sourceIcon`、`caloriesIcon`。

## HeartRateOverview

- 调用：`Template("HeartRateOverview@1", variant, params)`。
- 单业务使用 `hero*`，多业务固定使用 `support*`；有更新时间使用 `*Updated*`，有匹配素材使用 `*Icon`。
- `params` 仅 Icon Variant 可传 `sourceIcon`，否则使用 `{}`。

## SleepOverview

- 调用：`Template("SleepOverview@1", variant, params)`。
- 多业务使用 `durationSupport|durationDetailedSupport`；可信不足状态使用 `insufficient*`；2x4 且作息完整时使用 `schedule*`；其余使用 `duration*`。
- 时长分段由服务端投影补齐；Hero 可传语义匹配的 `sourceIcon`，Support 或无素材时使用 `{}`。

所有图标参数只能逐字复制 `trustedAssetSources`；不得输出旧业务构造器或自行传业务数据值。
