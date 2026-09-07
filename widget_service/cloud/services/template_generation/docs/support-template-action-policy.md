# Support 模板事件归属契约

## 范围与配置

采用模板级白名单方案，在 provider.json 的业务模板条目声明 supportedEventIds。该字段只约束业务
模板内嵌的 actionId，不扩大事件注册能力，也不改变独立 PillAction、IconAction 的消费规则。
第一层输出、Search 输出、Plan 输出及 cardtpl 语法保持不变。

```json
{
  "templateId": "HeartRateOverviewSupport@1",
  "supportedEventIds": ["event.open.health.sport"]
}
```

supportedEventIds 必须为无重复的事件类型 ID；不能填写带实例后缀的 actionId。省略或空数组表示
禁止内嵌事件。模板同时必须声明可选 actionId Prop，才能实际消费事件。白名单不意味着自动增加点击：
只消费用户显式要求、已通过本轮能力和参数裁决的事件候选。

## 正式白名单

| 模板 | supportedEventIds |
| --- | --- |
| WeatherOverviewTemperatureSupport@1 | event.open.weather |
| WeatherOverviewTemperatureUvSupport@1 | event.open.weather |
| WeatherOverviewTemperaturecoldLevelSupport@1 | event.open.weather |
| BatteryOverviewSupport@1 | event.open.settings.battery、event.open.settings.batteryHealth、event.setPowerSavingMode |
| ScheduleOverviewTimeSupport@1 | event.viewCalendarEvent、event.enter.meeting |
| ScheduleOverviewLocationSupport@1 | event.viewCalendarEvent、event.enter.meeting |
| ScheduleOverviewStartTimeSupport@1 | event.viewCalendarEvent、event.enter.meeting |
| ScheduleOverviewDateSupport@1 | event.viewCalendarEvent、event.enter.meeting |
| CountdownOverviewSupport@1 | 空 |
| BluetoothDeviceOverviewEarbudsSupport@1 | event.open.settings.bluetooth |
| BluetoothDeviceOverviewChargeSupport@1 | event.open.settings.bluetooth |
| ActivityOverviewSupport@1 | event.open.health.sport |
| WorkoutOverviewSupport@1 | event.open.health.sport |
| HeartRateOverviewSupport@1 | event.open.health.sport |
| SleepOverviewSupport@1 | event.open.health.sleep |
| AppUsageOverviewSupport@1 | event.open.settings.parentControl |
| ResourceUsageOverviewSupport@1 | event.clean.memory |

事件含义及参数以请求版本的 event_capabilities.json 为准。步数、训练及运动心率允许锻炼页作为关联入口，
不得宣称直达步数、心率或某次训练详情。睡眠不能复用锻炼事件；耳机不能绑定手机电池设置或音乐歌单。
运行内存清理不是存储空间设置；倒计时不使用闹钟替代。应用时长及系统内存仍受原数据能力门禁约束。

## 分配和校验

1. 第一层仍只标定用户明确要求的事件，不指定业务位置；Search 仍只处理尺寸、场景和数据可用性。
2. Planner 使用原始 event_id 检查模板白名单，保留 action_id（含 #1、#2 等实例后缀）作为消费标识。
   实例 ID 必须由完整请求候选生成，不能在筛选子集后重新编号。
3. 先求每个事件的合法业务位置，再枚举不冲突的分配；每个 Support 最多一个事件，每个已选实例恰好一次。
   没有合法分配的 TwoSupport Plan 不可用，不能移给搭档业务、静默丢动作或强行补足两个动作。
4. 天气详情参数必须引用当前天气数据域的 /location/cityCode；日程详情和入会参数必须引用当前模板
   展示的同一 events 下标，分别使用 entityId 和 oneClickServiceLink。不依赖 sampleValue 判断实时值；
   事件候选本身仍须通过注册事件参数校验，运行时链接是否有效不由样例值证明。
5. 编译器除匹配原子 Plan 外，在业务模板展开前独立复核白名单和数据对象归属；即使 Plan 被错误构造，
   或走兼容的非 Planner 路径，也不能绕过该检查。
6. Prompt 的 actionId 参数候选由同一规则生成，只输出该模板实际可消费的动作实例；空列表必须省略。
   第二层只能遵循所选 Plan，不能跨 Plan 移动动作。不得复制 URI、call、args 到模板配置或模型输出。

事件参数依赖不等于用户显式展示字段，cityCode、entityId 等不需要额外显示在卡片中。省电模式保持注册
协议中 0=开启、1=关闭的固定语义，不实现自动切换。用户指定点击哪个业务区域的额外语义提取不在本次范围。

## 画廊与回归

双业务画廊的事件候选从模板白名单和当前事件注册表的交集选择，不再使用通用业务动作表凑数。
0/1/2 动作只生成可行组合；倒计时没有事件，搭档有事件时可生成 0/1 动作，不生成 2 动作案例。
单业务独立动作案例仍沿用原契约。端侧显示继续每组一张，操作差异由自动化测试覆盖。

回归覆盖：17 个模板白名单、未声明/空配置拒绝、同类事件实例编号、同城市/同日程约束、跨业务错绑、
无合法 Plan、篡改 Plan、非 Planner 编译入口、Prompt 白名单同步及画廊不生成不可行动作数量。
