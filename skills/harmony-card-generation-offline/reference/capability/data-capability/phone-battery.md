# 手机电量能力

```json
{
  "id": "GetPhoneBatteryInfo",
  "description": "获取手机本机的全量电池状态快照。所有底层数字枚举及物理量均已在端侧完成高度语义化和字符化转换，适合桌面组件直渲染及大模型直接分析设备健康度。",
  "inputSchema": {
    "type": "object",
    "properties": {},
    "required": []
  },
  "outputSchema": {
    "type": "object",
    "description": "经过完全字符化、中文语义化清洗后的手机本机电池物理状态大盘字典。",
    "properties": {
      "batterySOC": {
        "type": "integer",
        "description": "当前手机设备剩余电池电量百分比纯数字，取值范围 [0, 100]。"
      },
      "batterySOCText": {
        "type": "string",
        "description": "当前手机设备剩余电池电量百分比格式化文本，例如: '100%'。"
      },
      "chargingStatusDesc": {
        "type": "string",
        "description": "当前设备电池的充电状态文本描述。例如: '使使能状态/充电中'、'停止状态'、'已充满状态'、'未充电'。"
      },
      "batteryCapacityLevelDesc": {
        "type": "string",
        "description": "设备电池电量等级高语义文本描述。例如: '满电量'、'高电量'、'正常电量'、'低电量'、'告警电量'、'极低电量'、'关机电量'。"
      },
      "healthStatusDesc": {
        "type": "string",
        "description": "当前设备电池的物理健康状态文本描述。例如: '正常'、'过热'、'过压'、'低温'、'僵死状态'。"
      },
      "pluggedTypeDesc": {
        "type": "string",
        "description": "当前设备连接的充电器类型文本描述。例如: '交流充电器'、'USB'、'无线充电器'、'未连接充电器'。"
      },
      "batteryTemperatureText": {
        "type": "string",
        "description": "当前设备电池的实时温度文本（已由0.1摄氏度缩放完成换算），带有单位。例如: '29.0 ℃' 或 '2.9 ℃'。"
      },
      "nowCurrentText": {
        "type": "string",
        "description": "当前设备电池的实时电流文本，带有毫安单位。负值通常代表放电，正值代表充电。例如: '-151 mA'。"
      },
      "voltageText": {
        "type": "string",
        "description": "当前设备电池的实时电压文本，带有伏特单位。例如: '4 V'。"
      },
      "isBatteryPresentText": {
        "type": "string",
        "description": "当前设备物理电池是否在位或支持的在位状态描述，返回 '在位' 或 '不在位'。"
      },
      "updatedAt": {
        "type": "string",
        "description": "端侧完成全量电量状态字符化转换的系统时间文本。如: 2026-07-03 15:09"
      }
    }
  }
}
```

## 使用规则

- 适用于手机电量、充电状态、电池健康、温度、电流和电压等本机电池状态卡。
- CardSpec 的 `capabilityId` 使用本文档 manifest 的 `id`：`GetPhoneBatteryInfo`。
- `arguments` 不传字段；不要自行增加设备 ID、阈值或充电器参数。
- 推荐 `writeResultTo: "/data/phoneBattery"`；UI 访问路径必须由 `writeResultTo + outputSchema` 推导。
- 常用展示路径：`/data/phoneBattery/batterySOC`、`/data/phoneBattery/batterySOCText`、`/data/phoneBattery/chargingStatusDesc`、`/data/phoneBattery/batteryCapacityLevelDesc`、`/data/phoneBattery/healthStatusDesc`、`/data/phoneBattery/batteryTemperatureText`、`/data/phoneBattery/updatedAt`。
- `2x2` 只保留电量主值和 1-2 条关键状态；`2x4` 才考虑温度、电流、电压等更多指标。
- 初始 `updateDataModel` 使用空值、0 值和加载态，不要写死用户真实电池数据：

```json
{
  "data": {
    "phoneBattery": {
      "batterySOC": 0,
      "batterySOCText": "",
      "chargingStatusDesc": "",
      "batteryCapacityLevelDesc": "",
      "healthStatusDesc": "",
      "pluggedTypeDesc": "",
      "batteryTemperatureText": "",
      "nowCurrentText": "",
      "voltageText": "",
      "isBatteryPresentText": "",
      "updatedAt": ""
    }
  },
  "state": {
    "loading": true
  }
}
```
