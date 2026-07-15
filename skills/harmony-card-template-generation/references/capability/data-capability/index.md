# 数据能力渐进加载索引

本文只用于选择需要读取的 data capability manifest。不要把本目录全部加载进上下文；先按用户意图和 CardSpec 需求命中候选，再打开对应文件。

## 加载顺序

1. 先读 `../cardspec.md`，确认静态卡还是动态卡、`writeResultTo` 规则和 DataModel 映射规则。
2. 用下方场景路由选择最多 1-2 个必要能力文件；如果用户请求超出已声明能力，不要编造 `capabilityId`，改成静态降级或能力边界说明。
3. 打开命中的 manifest 后，只抽取这些信息：`id`、`inputSchema.properties`、`required`、`outputSchema.properties`、推荐 `writeResultTo`、常用展示路径和初始化 DataModel。
4. 生成 CardSpec 时只写该 manifest 声明的入参字段；UI 表达式只能访问 `writeResultTo + outputSchema` 可推导字段。

## 场景路由

| 用户意图 | 读取文件 | 能力 ID | 推荐 `writeResultTo` |
| --- | --- | --- | --- |
| 天气、空气质量、温湿度、未来预报、雨天提醒、紫外线、风力 | `weather.md` | `ViewWeather` | `/data/weather` |
| 今日/未来日程、会议、倒计时、日历提醒、赛事日程 | `calendar.md` | `GetCalendarEvents` | `/data/calendar` |
| 指定应用使用时长、前后台耗电、应用电量消耗 | `app-usage.md` | `GetAppUsageDurationAndPower` | `/data/appUsageStats` |
| 蓝牙耳机连接、电量、左右耳/耳机盒充电状态 | `blutoothearphone-status.md` | `GetBluetoothEarphoneStatus` | `/data/earphone` |
| 睡眠、步数、热量、距离、最近运动、心率 | `healthy-sport.md` | `GetHealthAndSportSummary` | `/data/healthSport` |
| 系统内存、可用内存、空闲内存、内存占用比例 | `system-mem-info.md` | `GetSystemMemInfo` | `/data/systemMem` |

## 组合约束

- `2x2` 默认只保留一个核心数据能力；确有必要时可加一个动作入口或极短支撑能力，但不能形成两个主问题。
- `2x4` 最多组合两个核心数据能力；第三个能力通常降级为详情入口或不进入卡片。
- 多个 `writeResultTo` 不得相同、互为父子或覆盖，例如不要同时写 `/data/weather` 与 `/data/weather/current`。
- 同一卡片中不同能力的初始化 DataModel 要合并到同一个 `updateDataModel.value` 根对象，不要发送多张卡或多套 CardSpec。
- 事件参数若来自数据能力输出，必须在已读 manifest 的 `outputSchema` 中存在。

## 未声明能力

外卖配送、新闻、股票、跨端数据、可输入备忘录、复杂页面型需求等若没有对应 manifest，不要生成动态 `dataBindings`。可以输出静态入口卡、摘要卡或说明当前需要端侧补充能力。
