# 最新云侧方案对比说明

本文档对比 `docs/云侧方案设计.md` 与当前微服务实现，并记录本次已经按最新方案调整的点。

## 1. 工具形态

分歧点：

- 旧实现：曾对外抽象为一个工具 `widgetCardService`，通过 `operation` 分发多个能力。
- 当前部署要求：正式链路为能力概述、数据 schema、生成三个接口；实际可用性校验属于第一个能力概述接口。

当前处理：

- 当前保留三个正式业务 WebSocket 入口：
  `WS /api/v1/ws/tools/getWidgetCapabilityOverview`、
  `WS /api/v1/ws/tools/getDataCapabilitySchemas`、
  `WS /api/v1/ws/tools/generateWidgetCard`。
- 旧 HTTP 接口已移除。

## 2. 生成入参

分歧点：

- 旧实现：事件候选支持 `candidateEventCapabilityIds`、`candidateEventActions`、`candidateEventCapabilities`。
- 最新方案：只使用 `candidateEventCandidates`，每项同时携带 `capabilityId` 和 `action`。

当前处理：

- 公共生成请求已改为 `candidateEventCandidates`。
- 微服务内部会把每个候选转换为带 `id/call/args` 的内部 `EventAction`。

## 3. options 字段

分歧点：

- 旧实现：外部可传 `options.allowDegradation` 和 `options.returnArtifactInline`，后者会把包含 TaskSpec 的完整 artifact 放进响应。
- 最新方案：主 Agent 不传 `options`，微服务默认 `allowDegradation=true`，生成接口只返回 artifact 地址和摘要。

当前处理：

- 各 WebSocket 入口不需要传 `operation`。
- `GenerateWidgetCardRequest` 仅保留 `options.allowDegradation`；不再支持内联 artifact。

## 4. 自动注入上下文

分歧点：

- 旧实现：本地测试通常手动传外层 `appVersion/romVersion/xiaoyiVersion`。
- 最新方案：工具层自动注入用户和 `device`，服务只使用 `device.romVersion`。

当前处理：

- 请求模型移除外层 `appVersion/romVersion/xiaoyiVersion`，本地测试必须显式传 `uid` 和 `device`。
- 生产调用时由工具层注入，主 Agent 不需要主动填写。
- 当前 `romVersion` 暂时统一为数字兼容级别 `36`；不再定义第二个同义版本字段。

## 5. 能力裁决职责

- 旧实现：在 `generateWidgetCard` 内查询 IDS 并过滤候选能力。
- 当前实现：第一接口 `getWidgetCapabilityOverview` 读取 `ids_installation_filter_package_names`，只将命中配置范围的 `dependencies.requiredPackages[].packageName` 与 IDS `bundleName` 精确匹配。默认范围只有 `com.huawei.hmos.health.core`，所以当前过滤只对运动健康数据和事件能力生效；配置为空时跳过 IDS 查询。不比较 ROM/App/包版本，也不查询 provider、intent 或权限；旧清单中的这些额外依赖字段兼容忽略，不再触发注册表加载失败。第三接口只消费主 Agent 从可用清单中规划的候选，不重复查询 IDS。
- 第一接口响应不包含 TaskSpec；TaskSpec 只在生成接口内部构造并存入 artifact。

## 6. 能力注册表回退

- 配置项 `enable_default_capability_registry_fallback` 默认开启。
- 三个接口的请求版本目录不存在时，统一回退到 `app-11.7.5.205_rom-36`。
- 能力概述响应不暴露版本字段；数据 Schema 响应仍返回实际加载的版本，生成接口将实际版本写入 artifact meta。关闭开关时三个接口都不回退。

## 7. IDS mock 与真实远程模式

- 新增显式配置项 `enable_ids_mock`，默认开启；环境变量为 `WIDGET_SERVICE_ENABLE_IDS_MOCK=true`。
- 开启时只读取 `mock_ids_response_path` 指定的 mock 文件。文件不存在、不可读、JSON 无效或响应结构无效时返回空 IDS 结果，不再自动请求真实远程 IDS。
- 关闭时忽略 mock 文件，只请求真实远程 IDS。远程未配置、请求失败或响应无效时返回空 IDS 结果，不回退 mock。
- mock 文件是否存在不再决定 IDS 数据源，两个模式之间没有自动回退。

## 8. DSL 校验失败重试开关

- 新增配置项 `enable_validation_failure_retry`，环境变量为 `WIDGET_SERVICE_ENABLE_VALIDATION_FAILURE_RETRY`，默认关闭。
- 关闭时 `validate_genui` 失败只记录非阻断日志，保留首次模型输出并继续 artifact 保存，不再调用模型生成第二次。
- 开启时沿用最多重试一次的行为；重试后仍失败也不阻断 artifact 流程。

## 9. 字段投影直推

- `candidateOutputFields` 按 JSON Pointer 直接解析对应能力的 `outputSchema` 叶子，不再维护独立的 `data_model_mappings.json`。
- `outputSchema` 叶子的 `type/description` 仍为必需元数据；`sampleValue` 是推荐维护的脱敏受控元数据，缺失不阻断注册表加载，显式样例类型错误仍拒绝能力配置。当前内置注册表继续维护高质量样例。
- `TaskSpecBuilder` 从命中的 `outputSchema` 叶子读取 `type/description`，优先使用显式 `sampleValue`；缺失时按类型补充受控默认值：`string="示例"`、`integer/number=0`、`boolean=false`、`null=null`，再按 `writeResultTo + 原叶子路径` 生成 `dataModelSchema`。
- 部分非法路径被忽略；未传投影或全部路径非法时回退到该能力全部合法叶子字段。
- 端侧当前会把能力输出整体写入 `writeResultTo`，没有字段重命名、扁平化或派生字段转换层，因此生成链路不得把源字段映射到另一个目标路径。未来需要转换时，必须先单独设计并版本化实际运行时转换契约。

## 10. 结构化日志格式

- 日志里的字典、数组、布尔值和空值统一通过 `json_for_log` 输出为标准 JSON。
- JSON 键名和字符串使用双引号，布尔值使用 `true/false`，空值使用 `null`，不再输出 Python 单引号 `repr`。
- Pydantic 校验错误写入日志或接口错误详情前转换为 JSON-safe 结构，只保留 `loc/type/msg` 等诊断字段，不携带 `input/ctx` 原始对象。
- `uid` 继续作为合法请求字段保留在接口契约和调用示例中，但禁止写入日志，包括原值、脱敏值和哈希值；打印请求结构前必须显式排除 `uid`，IDS 请求日志也排除 `callingUid`。
- 每次能力概述请求的包过滤只打印一条汇总结果日志，不再逐项输出每个能力的依赖检查；汇总统一记录 `requestId`、IDS 数据源、数量统计和被移除能力摘要。

## 11. 最新推荐调用方式

能力概述：

```json
{
  "uid": "test-user-001",
  "device": {
    "romVersion": "36"
  }
}
```

加载数据能力 schema：

```json
{
  "uid": "test-user-001",
  "device": {
    "romVersion": "36"
  },
  "dataCapabilityIds": ["ViewWeather"]
}
```

生成卡片：

```json
{
  "uid": "test-user-001",
  "device": {
    "romVersion": "36"
  },
  "userQuery": "帮我做一个天气卡片",
  "title": "天气速览",
  "description": "查看当前天气",
  "size": "2x4",
  "candidateDataBindings": [
    {
      "capabilityId": "ViewWeather",
      "arguments": {
        "districtName": "青浦区",
        "forecastDays": 1
      },
      "writeResultTo": "/data/weather",
      "candidateOutputFields": [
        "/location/districtName",
        "/current/temperatureText",
        "/current/condition",
        "/current/airQuality",
        "/updatedAt"
      ]
    }
  ],
  "candidateEventCandidates": [
    {
      "capabilityId": "event.open.weather",
      "action": {
        "call": "clickToDeeplink",
        "args": {
          "intentName": "Weather_CityCode",
          "bundleName": "",
          "abilityName": "",
          "uri": "hww://www.huawei.com/totemweather?enterType=share&cityCode="
        }
      }
    }
  ],
  "candidateAssetIds": ["asset.drop_1"]
}
```

主 Agent 只能从第一接口返回的可用能力中规划候选；保留第一接口的 `unavailableCapabilities` 组织降级说明，不把它传入生成接口。
