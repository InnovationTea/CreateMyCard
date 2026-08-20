# 30 条未出卡样本：逐条真实原因

本文件只基于 `problem-rerun.log` 和本次 `results.jsonl`。前 18 条没有进入 DeepSeek 的全量 DSL 生成；后 12 条已经真实调用 DeepSeek 并拿到了 DSL，但被 A2UI/产物校验拒绝。

## 一、18 条在全量生成前被拒

### 请求字段不在当前 capability 的 outputSchema（10 条）

这些不是检索漏掉字段，也不是 DeepSeek 生成失败。测试请求自己要求了设备能力根本不会返回的字段；`generation_preflight` 在调用 DeepSeek 前按 outputSchema 拒绝请求。

| 样本 | 用户要什么 | 实际请求中的非法字段 | 为什么不能出卡 |
| --- | --- | --- | --- |
| TRE-026 | 日程卡显示参会人 | `GetCalendarEvents:/events/0/attendees` | 当前日历能力只给标题、开始/结束时间等字段，没有 attendees。不能让卡片显示一个数据源不存在的参会人。 |
| TRE-027 | 日程提醒显示会议号 | `GetCalendarEvents:/events/0/conferenceId` | 当前日历能力没有 conferenceId；会议号不是已注册日程输出。 |
| TRE-036 | 倒计时写出目标日期 | `GetCountdownDays:/targetDate` | 当前倒计时能力没有 targetDate。本条属于已知日期数据问题。 |
| TRE-037 | 倒计时显示进度百分比 | `GetCountdownDays:/progressPercent` | 当前倒计时能力没有 progressPercent，只有倒计天数等已有输出，不能凭空画“进度”。 |
| TRE-042 | 应用使用上限和剩余时长 | `GetAppUsageDuration:/dailyLimitText`、`/remainingTimeText` | 当前应用使用能力没有“每日上限”或“剩余时长”的数据；它只能给实际用时，不能推导出上限。 |
| TRE-052 | 耳机展示降噪模式 | `GetEarphoneInfo:/noiseCancelMode` | 当前耳机能力没有降噪模式输出；请求里只有连接状态和耳机名称等。 |
| TRE-059 | 电量卡显示预计充满时间 | `GetPhoneBatteryInfo:/estimatedFullTimeText` | 当前电池能力没有充满时间估算，因而不能承诺显示该文案。 |
| TRE-060 | 电量卡显示电池健康度 | `GetPhoneBatteryInfo:/batteryHealthText` | 当前电池能力没有健康度字段；电量百分比不等于电池健康度。 |
| TRE-074 | 运动卡展示配速 | `GetHealthAndSportSummary:/paceText` | 实际 TaskSpec 只有 `exerciseTypeName`、`exerciseDurationText`、`exerciseCalorieText`；没有配速。 |
| TRE-075 | 睡眠评分和各阶段图 | `GetHealthAndSportSummary:/sleepStages` | 睡眠评分可以提供，但“各阶段图”依赖的 sleepStages 不在当前输出中；一个请求里有一个强字段缺失，就不能假装完整满足。 |

共同的日志结论是 `OUTPUT_FIELD_PATH_INVALID`：要求的 JSON Pointer 不是对应 outputSchema 中的规范叶子路径。最小修复是改测试集/调用方的 candidateOutputFields，使它只要求当前能力真实提供的字段；不是改模板，也不是改 DeepSeek。

### 测试运行器把参数构造成字符串（8 条）

| 样本 | 用户请求 | 本次实际拦截点 |
| --- | --- | --- |
| TRE-081 | 内存占用比例、可用内存、总内存 | `GetSystemMemInfo` 的 `arguments` 被临时运行器填成字符串 `"测试值"`，但 API 要求对象（字典）。 |
| TRE-082 | 剩余多少内存 | 同上。 |
| TRE-083 | 存储空间使用情况 | 同上。 |
| TRE-084 | 内存趋势/历史曲线 | 同上。 |
| TRE-085 | 系统内存占用 | 同上。 |
| TRE-086 | 赛跑主题的内存卡 | 同上。 |
| TRE-087 | 可用内存 | 同上。 |
| TRE-090 | 股票价格和涨跌 | `GetStockQuote` 的 `arguments` 同样被填成字符串 `"测试值"`。 |

这 8 条的真实异常完全相同：`candidateDataBindings.0.arguments: Input should be a valid dictionary (input_value='测试值')`。它发生在 `GenerateWidgetCardRequest(...)` 的 Pydantic 入参校验，服务、检索和 DeepSeek 都没有开始运行。因此本次不能据此判断“内存能力/股票能力是否支持”，更不能归因给模板。要重测它们，先把运行器的参数样例函数改成传 `{}` 或符合各 capability inputSchema 的字典。

## 二、12 条 DeepSeek DSL 被 A2UI 校验拒绝

这 12 条都已经真实跑到全量生成。DeepSeek 输出的 DSL 都在 `genui:2` 的 `updateComponents` 中创建了一个图标组件，并给它的 `src` 填了一个资源路径；但本次请求的 `candidateAssetIds=[]`，有效资源能力集合为空。校验器不允许模型自己发明图片资源，所以报 `EFFECTIVE_ASSET_NOT_ALLOWED`。这不是数据字段不足，也不是模板匹配问题。

| 样本 | 用户请求 | DSL 中实际违规的位置 | 人话原因 |
| --- | --- | --- | --- |
| TRE-039 | 应用名称和今天使用多久 | `/updateComponents/componentsById/usageIcon/src` | DeepSeek 加了使用时长图标，但请求没有提供任何可用图标资源。 |
| TRE-041 | 应用使用概览、显示应用名 | `/updateComponents/componentsById/appIcon/src` | DeepSeek 画了应用图标，但没有获准使用这个图标资源。 |
| TRE-043 | 应用使用卡显示上次更新时间 | `/updateComponents/componentsById/usageIcon/src` | 生成了使用图标；资源集合为空，不能引用。 |
| TRE-053 | 耳机连接状态、会议纸张主题 | `/updateComponents/componentsById/statusIcon/src` | 生成了连接状态图标；请求没有传该图标。 |
| TRE-068 | 平均心率和更新时间 | `/updateComponents/componentsById/heartIcon/src` | 生成了心形图标；没有可用的 heartIcon 资源。 |
| TRE-076 | 显示平均心率 | `/updateComponents/componentsById/heartRateIcon/src` | 生成了心率图标；资源未授权。 |
| TRE-080 | 深色专注风平均心率 | `/updateComponents/componentsById/heartIcon/src` | 生成了心形图标；资源未授权。 |
| TRE-091 | 天气卡显示温度 | `/updateComponents/componentsById/weatherIcon/src` | 生成了天气图标；资源未授权。 |
| TRE-092 | 做一个天气卡 | `/updateComponents/componentsById/weatherIcon/src` | 生成了天气图标；资源未授权。 |
| TRE-093 | 天气卡显示温度 | `/updateComponents/componentsById/weatherIcon/src` | 生成了天气图标；资源未授权。 |
| TRE-094 | 天气卡显示温度 | `/updateComponents/componentsById/weatherIcon/src` | 生成了天气图标；资源未授权。另有非致命警告：第二个 dataBinding 的 `writeResultTo` 根结构没有在 data model 里初始化；真正导致失败的仍是 weatherIcon。 |
| TRE-097 | 显示平均心率 | `/updateComponents/componentsById/heartIcon/src` | 生成了心形图标；资源未授权。 |

所有这 12 条的致命错误都是同一个规则：`EFFECTIVE_ASSET_NOT_ALLOWED`。要让它们通过，只有两种契约正确的办法：调用请求显式提供允许使用的 asset capability/asset id，或在全量生成提示与 DSL 约束中明确“没有 asset 时只能用 Text/Shape 等无资源组件，不能写 Icon 的 src”。不能让校验器放行任意模型编造的资源路径。
