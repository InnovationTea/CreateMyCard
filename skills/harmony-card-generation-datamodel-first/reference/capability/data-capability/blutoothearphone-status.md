# 蓝牙耳机状态数据能力

```json
{
  "id": "GetBluetoothEarphoneStatus",
  "description": "查询当前手机连接的蓝牙耳机状态，包括耳机名称、主盒与左右耳的当前独立剩余电量百分比，以及它们各自的充电状态。",
  "inputSchema": {
    "type": "object",
    "properties": {},
    "required": []
  },
  "outputSchema": {
    "type": "object",
    "description": "聚合清洗后的标准化耳机状态数据，适合桌面小部件或快捷控制中心直接绑定显示。",
    "properties": {
      "isConnected": {
        "type": "boolean",
        "description": "当前是否有蓝牙耳机处于连接活跃状态。"
      },
      "earphoneName": {
        "type": "string",
        "description": "耳机的设备广播名称，如果未连接则返回'未连接耳机'。如: 'FreeBuds Pro 3'。"
      },
      "batteryLevel": {
        "type": "integer",
        "description": "耳机盒（或整体）的当前电量百分比，取值范围 0-100。"
      },
      "chargingStatusDesc": {
        "type": "string",
        "description": "耳机盒（或整体）当前的充电状态中文语义描述，'充电中' 或 '未充电'。"
      },
      "leftBatteryLevel": {
        "type": "integer",
        "description": "左耳机的当前电量百分比，取值范围 0-100。若未连接则为 0。"
      },
      "leftChargingStatusDesc": {
        "type": "string",
        "description": "左耳机当前的充电状态中文语义描述，'充电中' 或 '未充电'。"
      },
      "rightBatteryLevel": {
        "type": "integer",
        "description": "右耳机的当前电量百分比，取值范围 0-100。若未连接则为 0。"
      },
      "rightChargingStatusDesc": {
        "type": "string",
        "description": "右耳机当前的充电状态中文语义描述，'充电中' 或 '未充电'。"
      },
      "updatedAt": {
        "type": "string",
        "description": "端侧完成多源数据感知和融合的时间戳字符串。如：2026-07-02 20:15"
      }
    }
  }
}
```