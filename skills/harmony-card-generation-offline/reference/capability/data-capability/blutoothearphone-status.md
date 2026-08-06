# 蓝牙耳机状态数据能力

```json
{
  "id": "GetEarphoneInfo",
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

## 使用规则

- 适用于蓝牙耳机连接状态、耳机名称、耳机盒/左右耳电量和充电状态。
- CardSpec 的 `capabilityId` 使用本文档 manifest 的 `id`：`GetEarphoneInfo`。
- `arguments` 不传字段；不要自行增加设备名、蓝牙地址或包名等入参。
- 推荐 `writeResultTo: "/data/earphone"`；UI 访问路径必须由 `writeResultTo + outputSchema` 推导。
- 常用展示路径：`/data/earphone/isConnected`、`/data/earphone/earphoneName`、`/data/earphone/batteryLevel`、`/data/earphone/chargingStatusDesc`、`/data/earphone/leftBatteryLevel`、`/data/earphone/rightBatteryLevel`、`/data/earphone/updatedAt`。
- `2x2` 优先展示连接状态、设备名和一个主电量；左右耳电量作为并列小状态时要确认布局预算。`2x4` 可展示盒、左耳、右耳三项。
- 初始 `updateDataModel` 可以使用示例值；`/data/earphone` 中出现的字段、层级、类型和数值范围必须符合本文 `outputSchema`。示例值只用于首帧展示，不表示已经读取用户真实设备状态：

```json
{
  "data": {
    "earphone": {
      "isConnected": true,
      "earphoneName": "示例耳机",
      "batteryLevel": 80,
      "chargingStatusDesc": "未充电",
      "leftBatteryLevel": 76,
      "leftChargingStatusDesc": "未充电",
      "rightBatteryLevel": 78,
      "rightChargingStatusDesc": "未充电",
      "updatedAt": "2026-08-06 09:00"
    }
  },
  "state": {
    "loading": true
  }
}
```
