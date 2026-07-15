# 应用时长和耗电数据能力

```json
{
  "id": "GetAppUsageDurationAndPower",
  "description": "获取指定应用的使用时长和耗电量数据",
  "inputSchema": {
    "type": "object",
    "description": "查询应用使用时长和耗电量的输入参数",
    "properties": {
      "appBundleName": {
        "type": "string",
        "description": "目标应用的包名，例如：com.ss.hm.ugc.aweme"
      },
      "itemName": {
        "type": "string",
        "description": "查询的数据项标识，例如查询前后台时长与功耗固定传：foreground_time_power"
      }
    },
    "required": [
      "appBundleName",
      "itemName"
    ]
  },
  "outputSchema": {
    "type": "object",
    "description": "适合桌面卡片展示的应用耗电和时长概要。",
    "properties": {
      "appUsage": {
        "type": "object",
        "description": "应用具体的耗电量和使用时长详情",
        "properties": {
          "appName": {
            "type": "string",
            "description": "应用名称文本，例如：“抖音”"
          },
          "foreGroundDuration": {
            "type": "string",
            "description": "前台运行时间文本（自带单位），例如：“25 秒”或“1 分钟 21 秒”"
          },
          "foreGroundPower": {
            "type": "string",
            "description": "前台耗电量文本（自带单位），例如：“5.72 mAh”或“< 1 mAh”"
          },
          "backGroundDuration": {
            "type": "string",
            "description": "后台运行时间文本（自带单位），例如：“47 秒”"
          },
          "backGroundPower": {
            "type": "string",
            "description": "后台耗电量文本（自带单位），例如：“5.2 mAh”"
          }
        }
      },
      "updatedAt": {
        "type": "string",
        "description": "端侧完成数据查询和归一化的时间，格式如：2026-06-23 11:30"
      }
    }
  }
}
```

## 使用规则

- 适用于展示指定应用的前台使用时长、前台耗电、后台运行时长、后台耗电、更新时间等紧凑状态卡。
- CardSpec 的 `capabilityId` 使用本文档 manifest 的 `id`：`GetAppUsageDurationAndPower`。
- `arguments` 只能使用 `inputSchema.properties` 声明的字段：`appBundleName`、`itemName`，且二者都是必填字段。
- `itemName` 按 manifest 固定传 `foreground_time_power`；`appBundleName` 必须来自用户、宿主上下文或可靠的应用包名映射。只有应用显示名但无法确定包名时，不要编造包名，改用静态降级方案或说明需要宿主补充包名映射。
- 推荐 `writeResultTo` 使用语义化路径，例如 `/data/appUsageStats`。UI 访问路径必须由 `writeResultTo + outputSchema` 推导。
- 常用展示路径：`/data/appUsageStats/appUsage/appName`、`/data/appUsageStats/appUsage/foreGroundDuration`、`/data/appUsageStats/appUsage/foreGroundPower`、`/data/appUsageStats/appUsage/backGroundDuration`、`/data/appUsageStats/appUsage/backGroundPower`。
- 更新时间路径是 `/data/appUsageStats/updatedAt`，仅在卡片确实需要展示刷新时间时使用。
- 初始 `updateDataModel` 使用空对象和加载态，不要写死用户真实应用使用数据：

```json
{
  "data": {
    "appUsageStats": {
      "appUsage": {},
      "updatedAt": ""
    }
  },
  "state": {
    "loading": true
  }
}
```

- 本文档只声明应用使用时长和耗电数据能力的输入、输出和常用路径；通用 data capability 选择、CardSpec 映射见 `../cardspec.md`，事件参数绑定见 `../event-capability/` 和 `../../protocol/data-binding.md`。
