# 蓝牙耳机高级组件首层规则

## BluetoothDeviceOverview

- 支持的 TaskSpec 数据路径：
  - `{{dataRoot:GetEarphoneInfo}}/isConnected`
  - `{{dataRoot:GetEarphoneInfo}}/earphoneName`
  - `{{dataRoot:GetEarphoneInfo}}/batteryLevel`
  - `{{dataRoot:GetEarphoneInfo}}/leftBatteryLevel`
  - `{{dataRoot:GetEarphoneInfo}}/rightBatteryLevel`
  - `{{dataRoot:GetEarphoneInfo}}/chargingStatusDesc`
- 只支持蓝牙耳机/耳塞连接状态、设备名、盒/左/右电量和充电状态；明确请求的部位或状态必须有对应路径。
- 不支持手表、车机、键鼠、音箱、播放状态、曲目或进度。
- 根据 `userQuery` 判断出的必须显示设备字段存在支持集合之外的路径时，不得选择。
- `2x4` 多业务场景中，用户要求展示耳机仓充电状态且 `chargingStatusDesc` 可用时，可以选择
  `BluetoothDeviceOverviewStatusHero@1`；该模板占据 `WideTwoFocus` 系列左右双焦点布局的一个
  Hero 槽位，充电状态为硬必选。
