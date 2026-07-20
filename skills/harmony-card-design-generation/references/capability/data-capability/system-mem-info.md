# 系统内存详情数据能力

```json
{
  "id": "GetSystemMemInfo",
  "description": "查询系统当前的内存使用情况，包括总内存、完全空闲内存、可用内存以及真实内存占用百分比。",
  "inputSchema": {
    "type": "object",
    "properties": {},
    "required": []
  },
  "outputSchema": {
    "type": "object",
    "description": "系统内存的当前状态概要，已经过端侧单位换算（GB/MB）和占用百分比计算，适合直接展示在卡片或开发者工具仪表盘上。",
    "properties": {
      "totalMemText": {
        "type": "string",
        "description": "系统总内存，格式化后的文本（如 '8.00 GB'）。"
      },
      "freeMemText": {
        "type": "string",
        "description": "系统完全空闲的内存，格式化后的文本（如 '1.20 GB'）。注意：在现代 OS 架构中，系统常驻缓存会导致此值偏小，不代表系统真正吃紧。"
      },
      "availableMemText": {
        "type": "string",
        "description": "系统可用于重新分配的可用内存，格式化后的文本（如 '4.50 GB'）。判断系统是否存在内存瓶颈的核心指标。"
      },
      "usagePercent": {
        "type": "number",
        "description": "当前系统内存真实占用百分比（计算方式：(总内存-可用内存)/总内存 * 100），取值范围 0-100。"
      }
    }
  }
}
```

## 使用规则

- 适用于系统内存、可用内存、空闲内存、总内存和内存占用比例展示。
- CardSpec 的 `capabilityId` 使用本文档 manifest 的 `id`：`GetSystemMemInfo`。
- `arguments` 不传字段；不要自行增加清理阈值或应用包名等入参。
- 推荐 `writeResultTo: "/data/systemMem"`；UI 访问路径必须由 `writeResultTo + outputSchema` 推导。
- 常用展示路径：`/data/systemMem/totalMemText`、`/data/systemMem/freeMemText`、`/data/systemMem/availableMemText`、`/data/systemMem/usagePercent`。
- 进度条或环形进度只在 `usagePercent` 是主焦点时使用；旁边文案不要重复展示同一百分比，除非它是唯一主事实。
- 初始 `updateDataModel` 使用空值、0 值和加载态，不要写死用户真实系统状态：

```json
{
  "data": {
    "systemMem": {
      "totalMemText": "",
      "freeMemText": "",
      "availableMemText": "",
      "usagePercent": 0
    }
  },
  "state": {
    "loading": true
  }
}
```
