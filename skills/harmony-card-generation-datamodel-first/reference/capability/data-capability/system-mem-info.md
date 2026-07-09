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