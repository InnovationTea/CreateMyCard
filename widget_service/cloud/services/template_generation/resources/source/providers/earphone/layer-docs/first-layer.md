# 蓝牙耳机高级组件首层规则

## BluetoothDeviceOverview

- 支持的 TaskSpec 数据路径：
  - `{{dataRoot:GetEarphoneInfo}}/isConnected`
  - `{{dataRoot:GetEarphoneInfo}}/earphoneName`
  - `{{dataRoot:GetEarphoneInfo}}/batteryLevel`
  - `{{dataRoot:GetEarphoneInfo}}/chargingStatusDesc`
  - `{{dataRoot:GetEarphoneInfo}}/leftBatteryLevel`
  - `{{dataRoot:GetEarphoneInfo}}/rightBatteryLevel`
- 只支持蓝牙耳机/耳塞连接状态、设备名和盒/左/右电量；明确请求的部位必须有对应路径。
- 不支持手表、车机、键鼠、音箱、播放状态、曲目或进度。
- 根据 `userQuery` 判断出的必须显示设备字段存在支持集合之外的路径时，不得选择。
