# 第二层业务模板使用规则

- Provider：`com.huawei.earphone.cli`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
  - `BluetoothDeviceOverviewDisconnected@1`：蓝牙耳机连接与电量摘要，可展示设备名、盒电量和左右耳电量。 组件形态：disconnected。 必需数据：/isConnected, /earphoneName；可选数据：无。
  - `BluetoothDeviceOverviewConnection@1`：蓝牙耳机连接与电量摘要，可展示设备名、盒电量和左右耳电量。 组件形态：connection。 必需数据：/isConnected, /earphoneName；可选数据：无。
  - `BluetoothDeviceOverviewDisconnectedPhone@1`：蓝牙耳机连接与电量摘要，可展示设备名、盒电量和左右耳电量。 组件形态：disconnectedPhone。 必需数据：/isConnected；可选数据：无。
  - `BluetoothDeviceOverviewEarbudsPhone@1`：蓝牙耳机连接与电量摘要，可展示设备名、盒电量和左右耳电量。 组件形态：earbudsPhone。 必需数据：/isConnected；可选数据：/batteryLevel, /leftBatteryLevel, /rightBatteryLevel。
  - `BluetoothDeviceOverviewEarbudsPhoneWide@1`：蓝牙耳机连接与电量摘要，可展示设备名、盒电量和左右耳电量。 组件形态：earbudsPhoneWide。 必需数据：/isConnected, /earphoneName；可选数据：/batteryLevel, /leftBatteryLevel, /rightBatteryLevel。
  - `BluetoothDeviceOverviewEarbudsDynamicWide@1`：蓝牙耳机连接与电量摘要，可展示设备名、盒电量和左右耳电量。 组件形态：earbudsDynamicWide。 必需数据：/isConnected, /earphoneName；可选数据：/batteryLevel, /leftBatteryLevel, /rightBatteryLevel。
  - `BluetoothDeviceOverviewEarbuds@1`：蓝牙耳机连接与电量摘要，可展示设备名、盒电量和左右耳电量。 组件形态：earbuds。 必需数据：/isConnected, /earphoneName, /batteryLevel；可选数据：无。
  - `BluetoothDeviceOverviewLeftEarbud@1`：蓝牙耳机连接与电量摘要，可展示设备名、盒电量和左右耳电量。 组件形态：leftEarbud。 必需数据：/isConnected, /earphoneName, /leftBatteryLevel；可选数据：无。
  - `BluetoothDeviceOverviewRightEarbud@1`：蓝牙耳机连接与电量摘要，可展示设备名、盒电量和左右耳电量。 组件形态：rightEarbud。 必需数据：/isConnected, /earphoneName, /rightBatteryLevel；可选数据：无。
  - `BluetoothDeviceOverviewEarbudPair@1`：蓝牙耳机连接与电量摘要，可展示设备名、盒电量和左右耳电量。 组件形态：earbudPair。 必需数据：/isConnected, /earphoneName, /leftBatteryLevel, /rightBatteryLevel；可选数据：无。
  - `BluetoothDeviceOverviewEarbudsFull@1`：蓝牙耳机连接与电量摘要，可展示设备名、盒电量和左右耳电量。 组件形态：earbudsFull。 必需数据：/isConnected, /earphoneName, /leftBatteryLevel, /rightBatteryLevel；可选数据：无。
  - `BluetoothDeviceOverviewEarbudsFullWide@1`：蓝牙耳机连接与电量摘要，可展示设备名、盒电量和左右耳电量。 组件形态：earbudsFullWide。 必需数据：/isConnected, /earphoneName, /batteryLevel, /leftBatteryLevel, /rightBatteryLevel；可选数据：无。
  - `BluetoothDeviceOverviewEarbudPairPhone@1`：蓝牙耳机连接与电量摘要，可展示设备名、盒电量和左右耳电量。 组件形态：earbudPairPhone。 必需数据：/isConnected, /leftBatteryLevel, /rightBatteryLevel；可选数据：无。
  - `BluetoothDeviceOverviewEarbudsFullPhoneWide@1`：蓝牙耳机连接与电量摘要，可展示设备名、盒电量和左右耳电量。 组件形态：earbudsFullPhoneWide。 必需数据：/isConnected, /earphoneName, /batteryLevel, /leftBatteryLevel, /rightBatteryLevel；可选数据：无。

- props 只能使用本次 Prompt 下发的可信文本、数值或素材；不得输出数据路径。
- 选择能够完整表达用户显式要求字段且自身 requiredData 全部可用的模板。
