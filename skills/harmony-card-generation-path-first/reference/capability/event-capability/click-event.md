# 点击事件能力

本文只指导 DSL `onClick`，不进入 CardSpec，也不新增第三个输出代码块。生成时按“先匹配能力，再匹配目标，再填参数”的顺序执行；无法匹配时删除点击行为，改为静态展示或说明需要宿主补充 event-capability manifest。

## 生成规则

- 先按用户意图匹配能力说明，再校验 `parameters` 和目标清单；不能匹配时不要伪造点击能力。
- `onClick.call` 必须使用下表 `functionCall`，不要把应用名、页面名或 description 写成 `call`。
- `args` 只能包含对应能力的参数；跳转类能力还必须使用下表声明的合法目标和值组合。
- 事件参数可来自安全静态值、DataModel 绝对路径或模板列表项相对路径；来自 data capability 输出的字段，必须能由 `writeResultTo + outputSchema` 推导。
- `clickToIntent.args.params` 必须严格匹配目标的 `params` 结构。若目标参数说明里出现 `type`、`description` 等 schema 元数据，DSL 只保留参数 key 和实际运行时值；若目标声明固定值，使用固定值。
- 拨号参数名固定为 `phoneNumber`；地图导航参数名固定为 `trafficpe`，不要改成其它拼写。
- 模板列表项内优先用相对路径，例如 `{"path":"entityId"}`；非模板区域用绝对路径，例如 `{"path":"/data/calendar/items/0/entityId"}`。

## 能力速查

- `clickToCallPhone`：拨号界面；参数 `phoneNumber` string。
- `clickToDeeplink`：打开应用或页面；参数 `bundleName` string、`abilityName` string、`uri` string；三者至少一个有值。若目标通过长 URI 拉起，`bundleName` 和 `abilityName` 传空字符串 `""`。
- `clickToIntent`：执行声明的 intent；参数 `intentName` string、`params` object。

## 参数值类型

- 上表的 `string`、`number`、`object` 是运行时值类型；DSL 里可以填静态 JSON 值、`{"path":"/..."}` / `{"path":"..."}` 绑定，或 `formatString` 绑定来生成该运行时值。
- 目标表中声明为固定值的 `bundleName`、`abilityName`、`uri`、`intentName` 或固定 `params` 必须直接复制静态值；不要改成绑定，也不要拼接。
- 只有用户输入、DataModel 或 data capability 输出明确提供的参数才使用绑定；绑定路径必须能从 `updateDataModel.value`、模板当前项或 `writeResultTo + outputSchema` 推导。

## Deeplink 目标

`clickToDeeplink` 必须复制目标行中的 `bundleName`、`abilityName`、`uri` 结构和值；目标中为空的字段也传 `""`。

| 应用 | 场景 | bundleName | abilityName | uri |
| --- | --- | --- | --- | --- |
| 设置 | 情景模式，免打扰或专注模式 | `com.huawei.hmos.settings` | `com.huawei.hmos.settings.MainAbility` | `intelligent_scene_entry` |
| 设置 | 蓝牙设置页 | `com.huawei.hmos.settings` | `com.huawei.hmos.settings.MainAbility` | `bluetooth_entry` |
| 设置 | 电池页 | `com.huawei.hmos.settings` | `com.huawei.hmos.settings.MainAbility` | `battery` |
| 设置 | 电池健康页 | `com.huawei.hmos.settings` | `com.huawei.hmos.settings.MainAbility` | `smart_charge_battery_health` |
| 设置 | 健康使用 App 页面，设置应用使用时长 | `com.huawei.hmos.settings` | `com.huawei.hmos.settings.MainAbility` | `parent_control` |
| 设置 | 存储空间页 | `com.huawei.hmos.settings` | `com.huawei.hmos.settings.MainAbility` | `storage_settings` |
| 天气 | 天气应用某城市页，uri 固定勿改 | `""` | `""` | `hww://www.huawei.com/totemweather?enterType=share&cityCode=` |
| 闹钟 | 闹钟应用首页 | `com.huawei.hmos.clock` | `com.huawei.hmos.clock.phone` | `""` |
| 音乐 | 每日 30 首歌单，uri 固定勿改 | `""` | `""` | `hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4` |
| 音乐 | 收藏歌单/心动歌单，uri 固定勿改 | `""` | `""` | `hwmusic://com.huawei.hmsapp.music/showMusicList?code=favoriteSong&type=412` |
| 运动健康 | 锻炼 Tab 页 | `""` | `""` | `huaweischeme://healthapp/home/sport?sportType=2` |
| 运动健康 | 睡眠详情页 | `""` | `""` | `huaweischeme://healthapp/router/sleepDetail` |

## Intent 目标

- `ViewCalendarEvent`：查看日程详情；`params = { "entityId": <日程 id> }`。列表模板内用 `{"path":"entityId"}`，非模板区域用绝对路径。
- `StartNavigate`：地图导航；`params.dstLocation.latitude` string、`params.dstLocation.longitude` string，必须来自用户提供或已解析数据，不凭空估算；`params.trafficpe` string，取 `Drive|Walk|Cycle|Bus`，分别表示开车、步行、骑行、公共交通。
- `SetSettingSwitch`：开启/关闭省电模式；`params.appBundleName = "com.huawei.hmos.settings"`，`params.itemName = "battery_saving_mode"`，`params.switchFlag` number，`0` 表示开启省电模式，`1` 表示关闭省电模式。

最小写法：

```json
{"call":"clickToCallPhone","args":{"phoneNumber":{"path":"/contact/phoneNumber"}}}
{"call":"clickToDeeplink","args":{"bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"battery"}}
{"call":"clickToIntent","args":{"intentName":"ViewCalendarEvent","params":{"entityId":{"path":"entityId"}}}}
{"call":"clickToIntent","args":{"intentName":"StartNavigate","params":{"dstLocation":{"latitude":{"path":"/destination/latitude"},"longitude":{"path":"/destination/longitude"}},"trafficpe":"Drive"}}}
{"call":"clickToIntent","args":{"intentName":"SetSettingSwitch","params":{"appBundleName":"com.huawei.hmos.settings","itemName":"battery_saving_mode","switchFlag":0}}}
```

## 检查清单

- `call` 是已声明的 `functionCall`。
- `args` 字段名与所选能力参数完全一致。
- deeplink 目标来自上表，空字段显式传 `""`。
- intent 的 `params` 只保留运行时参数，不复制 schema 元数据。
- 动态事件参数路径能从 DataModel、模板当前项或 `writeResultTo + outputSchema` 推导。
