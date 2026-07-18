# Widget Service 方法使用说明

本文档说明 `widget_service` 当前微服务里的接口、核心服务方法、模型对象和配置文件如何使用。项目入口遵循 `docs/AGENTS.md`，微服务本身可以被当作一个工具服务使用。

## 1. 启动方式

推荐使用 Python 3.12。

```bash
cd widget_service
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
set PYTHONPATH=cloud
uvicorn main:app --reload
```

健康检查：

```bash
curl http://127.0.0.1:8855/health
```

返回：

```json
{
  "status": "ok"
}
```

## 2. 目录和版本规则

能力清单按 `deviceInfo.prdVer + romVersion` 生成的文件夹名做版本隔离。当前 `romVersion` 暂时统一使用主次版本 `6.0`：

```text
cloud/data/capabilities/{capabilityRegistryVersion}/
├─ data_capabilities.json
├─ event_capabilities.json
└─ asset_capabilities.json
```

当前默认能力清单：

```text
app-11.7.5.205_rom-6.0
```

三个接口在请求版本目录不存在且
`WIDGET_SERVICE_ENABLE_DEFAULT_CAPABILITY_REGISTRY_FALLBACK=true` 时，统一回退到上述默认能力清单。关闭开关时，第一、第二接口返回空清单/缺失能力，第三接口返回版本不支持。

第一接口的 IDS 安装过滤范围由
`WIDGET_SERVICE_IDS_INSTALLATION_FILTER_PACKAGE_NAMES` 配置，值为 JSON 字符串数组。默认只包含
`["com.huawei.hmos.health.core"]`，因此当前只对运动健康数据和事件能力执行安装包过滤；配置为空数组时跳过 IDS 查询和安装过滤。

IDS 数据源由 `WIDGET_SERVICE_ENABLE_IDS_MOCK` 显式控制，默认值为 `true`：

- `true`：只读取 `WIDGET_SERVICE_MOCK_IDS_RESPONSE_PATH` 指定的 mock 文件；文件不存在、不可读、JSON 无效或响应结构无效时返回空 IDS 结果，不请求远程 IDS。
- `false`：忽略 mock 文件，只请求 `WIDGET_SERVICE_IDS_QUERY_URL` 指定的真实远程 IDS；远程未配置、请求失败或响应无效时返回空 IDS 结果，不回退 mock。

不能再根据 mock 文件是否存在自动选择或切换数据源。

DSL 校验失败重试由 `WIDGET_SERVICE_ENABLE_VALIDATION_FAILURE_RETRY` 控制，默认值为 `false`。关闭时校验失败只记录日志并继续保存首次输出；开启时最多重新生成一次。

A2UI 协议 profile 也按文件夹隔离：

```text
cloud/data/protocol_profiles/{protocolProfileId}/
├─ protocol.md
├─ component-catalog.md
└─ data-binding.md
```

当前默认 profile：

```text
a2ui-form-rom6.0-v1
```

工具入参里可以传：

```json
{
  "capabilityRegistryVersion": "app-11.7.5.205_rom-6.0",
  "protocolProfileId": "a2ui-form-rom6.0-v1"
}
```

不传时使用 `.env` 或默认配置。

## 3. WebSocket 接口

当前微服务提供三个正式工具能力，并额外保留一个 Compact DSL 生成变体。客户端连接目标 path 后，
消息体只需要传该能力自己的参数，不需要再传 `operation`。新协议中的 `odid` 位于 `content.odid`，
字段可选；服务会将其映射到内部设备上下文，缺失或为空时 IDS 查询继续使用固定兜底值，且不从
`deviceInfo` 读取同名字段。用户和设备上下文由工具层自动注入，本地测试时可以显式传入。

业务入口：

```text
WS /api/v1/ws/tools/getWidgetCapabilityOverview
WS /api/v1/ws/tools/getDataCapabilitySchemas
WS /api/v1/ws/tools/generateWidgetCard
WS /api/v1/ws/tools/generateWidgetCardCompactDsl
```

`generateWidgetCard` 固定使用原 A2UI Form profile；
`generateWidgetCardCompactDsl` 固定使用 `compact-dsl-v1`。两个入口共享业务入参和响应结构，
调用方不需要传 `protocolProfileId`。

连接成功后客户端直接发送业务消息，服务不再返回 ready 帧。统一消息最小结构：

```json
{
  "requestId": "overview-1",
  "arguments": {
    "uid": "test-user-001",
    "device": {
      "deviceId": "5e64f3e9-0a80-d719-d689-3c36eca5eeb6",
      "deviceType": "ALN-AL00",
      "romVersion": "CLS-AL30 6.0.0.328"
    }
  }
}
```

接口 schema 文件：

```text
docs/schemas/getWidgetCapabilityOverview.schema.json
docs/schemas/getDataCapabilitySchemas.schema.json
docs/schemas/generateWidgetCard.schema.json
docs/schemas/generateWidgetCardCompactDsl.schema.json
```

### 3.1 GET /health

用途：服务健康检查。

请求：

```bash
curl http://127.0.0.1:8855/health
```

响应：

```json
{
  "status": "ok"
}
```

### 3.2 WS /api/v1/ws/tools/getWidgetCapabilityOverview

对应工具能力：`getWidgetCapabilityOverview`

用途：先按 `romVersion`、`prdVer` 选择注册表，再读取 IDS 安装过滤包名配置。当前默认只查询并精确匹配运动健康包 `com.huawei.hmos.health.core`；天气、日历等未命中配置范围的依赖不参与安装过滤。包版本、ROM/App 依赖版本、provider、intent、权限和素材版本不参与本阶段过滤。响应不包含 TaskSpec；数据能力只返回概述，不返回完整 schema。

请求示例：

```json
{
  "requestId": "overview-1",
  "arguments": {
    "uid": "test-user-001",
    "locale": "zh-CN",
    "device": {
      "deviceId": "5e64f3e9-0a80-d719-d689-3c36eca5eeb6",
      "deviceType": "ALN-AL00",
      "romVersion": "CLS-AL30 6.0.0.328"
    },
    "capabilityRegistryVersion": "app-11.7.5.205_rom-6.0"
  }
}
```

响应消息核心字段：

```json
{
  "type": "result",
  "tool": "getWidgetCapabilityOverview",
  "operation": "getWidgetCapabilityOverview",
  "requestId": "overview-1",
  "data": {
    "dataCapabilities": [
      {
        "id": "ViewWeather",
        "description": "查询当前天气、空气质量和未来预报"
      }
    ],
    "eventCapabilities": [],
    "assetCandidates": [],
    "unavailableCapabilities": []
  },
  "status": "success",
  "errorCode": "",
  "error": {}
}
```

### 3.3 WS /api/v1/ws/tools/getDataCapabilitySchemas

对应工具能力：`getDataCapabilitySchemas`

用途：针对主 Agent 已选中的数据能力渐进加载完整 schema。请求版本目录不存在且回退开关开启时，读取默认 205/6.0 注册表。

请求示例：

```json
{
  "requestId": "schema-1",
  "arguments": {
    "uid": "test-user-001",
    "device": {
      "deviceId": "5e64f3e9-0a80-d719-d689-3c36eca5eeb6",
      "deviceType": "ALN-AL00",
      "romVersion": "CLS-AL30 6.0.0.328"
    },
    "dataCapabilityIds": ["ViewWeather", "GetCalendarEvents"],
    "capabilityRegistryVersion": "app-11.7.5.205_rom-6.0"
  }
}
```

响应消息核心字段：

```json
{
  "type": "result",
  "tool": "getDataCapabilitySchemas",
  "operation": "getDataCapabilitySchemas",
  "requestId": "schema-1",
  "data": {
    "apiVersion": "v1",
    "capabilityRegistryVersion": "app-11.7.5.205_rom-6.0",
    "dataCapabilities": [
      {
        "id": "ViewWeather",
        "inputSchema": {},
        "outputSchema": {
          "type": "object",
          "properties": {
            "current": {
              "type": "object",
              "properties": {
                "condition": {
                  "type": "string",
                  "description": "当前天气现象，例如‘阴’‘多云’‘小雨’。",
                  "sampleValue": "多云"
                }
              }
            }
          }
        },
        "defaultWriteResultTo": "/data/weather",
        "dataModelSkeleton": {}
      }
    ],
    "missingCapabilityIds": []
  },
  "status": "success",
  "errorCode": "",
  "error": {}
}
```

`missingCapabilityIds` 用来告诉主 Agent 哪些能力 ID 没有注册。`defaultWriteResultTo` 是可选建议字段：缺少该字段不代表能力缺失或不可用，也不得阻断能力清单加载；第三接口实际使用请求中的 `candidateDataBindings[].writeResultTo`。

### 3.4 WS /api/v1/ws/tools/generateWidgetCard

对应工具能力：`generateWidgetCard`

用途：首次生成或基于上一版 artifact 继续编辑卡片。接收主 Agent 从能力概述中规划的候选并生成 artifact；不再查询 IDS 或重复执行 `dependencies` 过滤。请求版本目录不存在时，使用统一的默认注册表回退配置。

请求示例：

```json
{
  "requestId": "generate-1",
  "arguments": {
    "uid": "test-user-001",
    "userQuery": "帮我做通勤卡片，包含天气和今日日程",
    "size": "2x4",
    "title": "通勤助手",
    "description": "天气日程速览",
    "device": {
      "deviceId": "5e64f3e9-0a80-d719-d689-3c36eca5eeb6",
      "deviceType": "ALN-AL00",
      "romVersion": "CLS-AL30 6.0.0.328"
    },
    "protocolProfileId": "a2ui-form-rom6.0-v1",
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
      },
      {
        "capabilityId": "GetCalendarEvents",
        "arguments": {
          "futureDays": 1
        },
        "writeResultTo": "/data/calendar",
        "candidateOutputFields": [
          "/events/0/title",
          "/events/0/dtStart",
          "/events/0/eventLocation"
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
    "candidateAssetIds": ["asset.drop_1", "asset.calendar_fill"]
  }
}
```

编辑请求通过 `sourceArtifactUrl` 指向上一轮真实产物。省略尺寸、标题、说明或某类候选数组表示继承；显式传入数组表示整体替换，空数组表示清空。首次生成仍必须传非空 `title/description`。

```json
{
  "requestId": "edit-1",
  "arguments": {
    "uid": "test-user-001",
    "userQuery": "整体改成蓝色风格",
    "sourceArtifactUrl": "https://obs.todo.local/widget/artifact_uuid.md",
    "device": {
      "romVersion": "CLS-AL30 6.0.0.328"
    }
  }
}
```

只有包含 `generationplan` 的 `widget-artifact-v2` 可作为编辑来源。编辑开关默认关闭。Compact DSL 调试入口不支持多轮编辑。

响应消息核心字段：

```json
{
  "type": "result",
  "tool": "generateWidgetCard",
  "operation": "generateWidgetCard",
  "requestId": "generate-1",
  "data": {
    "apiVersion": "v1",
    "status": "success",
    "artifactUrl": "https://obs.todo.local/widget/artifact_uuid.md",
    "artifactDigest": "sha256:xxx",
    "suggestSize": "2x4",
    "message": "已为你生成可用的桌面卡片。",
    "removedCapabilities": [],
    "errorCode": "",
    "effectiveCapabilities": {
      "data": ["ViewWeather", "GetCalendarEvents"],
      "event": [],
      "asset": ["asset.drop_1", "asset.calendar_fill"]
    }
  },
  "status": "success",
  "errorCode": "",
  "error": {}
}
```

状态说明：

```text
success      完整满足用户需求并生成成功
degraded     部分能力不可用，已降级生成可用卡片
unsupported  能力或协议限制导致不应生成卡片
failed       系统异常、模型失败、OBS 失败等工程失败
```

事件候选按最新云侧方案只使用 `candidateEventCandidates`：

```json
{
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
  ]
}
```

## 4. 核心服务方法

### 4.1 WidgetGenerationService.get_widget_capability_overview

位置：

```text
cloud/services/widget_generation_service.py
```

签名：

```python
get_widget_capability_overview(
    request: CapabilityOverviewRequest,
) -> CapabilityOverviewResponse
```

用途：读取指定版本的能力清单，并在注册表依赖命中配置的安装过滤范围时查询一次 IDS，返回当前设备实际可用的能力概述及不可用清单。

使用示例：

```python
from api.schemas import CapabilityOverviewRequest
from services.widget_generation_service import WidgetGenerationService

service = WidgetGenerationService()
response = service.get_widget_capability_overview(
    CapabilityOverviewRequest(
        uid="test-user-001",
        device={"romVersion": "CLS-AL30 6.0.0.328"},
    )
)
```

内部流程：

```text
CapabilityRegistry(version)
 -> 读取 ids_installation_filter_package_names
 -> 命中配置范围时按 enable_ids_mock 选择唯一 IDS 数据源
 -> IDSClient.get_device_capability_state()
 -> DeviceCapabilityResolver.resolve_capability_overview()
 -> 组装 CapabilityOverviewResponse
```

### 4.2 WidgetGenerationService.get_data_capability_schemas

签名：

```python
get_data_capability_schemas(
    request: DataCapabilitySchemasRequest,
) -> DataCapabilitySchemasResponse
```

用途：按能力 ID 返回完整 schema、可选的建议写入路径和 DataModel 骨架。

使用示例：

```python
response = service.get_data_capability_schemas(
    DataCapabilitySchemasRequest(
        dataCapabilityIds=["ViewWeather", "GetCalendarEvents"],
        uid="test-user-001",
        device={"romVersion": "CLS-AL30 6.0.0.328"},
        capabilityRegistryVersion="app-11.7.5.205_rom-6.0",
    )
)
```

返回说明：

```text
dataCapabilities      已注册的数据能力完整定义
missingCapabilityIds  未注册的数据能力 ID
```

### 4.3 WidgetGenerationService.generate_widget_card

签名：

```python
generate_widget_card(
    request: GenerateWidgetCardRequest,
) -> GenerateWidgetCardResponse
```

用途：第三接口的主生成编排方法，只消费主 Agent 从第一接口可用清单中规划的能力。

内部流程：

```text
1. 读取 CapabilityRegistry
2. 读取 A2UIProtocolRegistry
3. 解析候选 data/event/asset；校验参数、写入路径和注册表存在性，不查询 IDS
4. CardSpecBuilder 生成最终 CardSpec
5. TaskSpecBuilder 根据 writeResultTo、outputSchema 和候选字段投影生成 TaskSpec.dataModelSchema
6. PromptBuilder 生成模型输入
7. A2UIModelClient mock 生成 genui
8. RetryController 按 `enable_validation_failure_retry` 控制校验失败后是否重试，默认不重试
9. ArtifactValidator 校验完整 artifact；最终失败记录日志但不阻断保存和响应
10. ArtifactStore 保存 artifact，当前为 OBS TODO hook
11. ResponsePlanner 生成 status 和 message
```

使用示例：

```python
from api.schemas import GenerateWidgetCardRequest
from models.generation import CandidateDataBinding

response = service.generate_widget_card(
    GenerateWidgetCardRequest(
        userQuery="帮我做一个只显示今天上海天气的桌面卡片",
        size="2x4",
        title="天气速览",
        description="查看上海天气",
        uid="test-user-001",
        device={"romVersion": "CLS-AL30 6.0.0.328"},
        candidateDataBindings=[
            CandidateDataBinding(
                capabilityId="ViewWeather",
                arguments={"districtName": "上海", "forecastDays": 1},
                writeResultTo="/data/weather",
            )
        ],
    )
)
```

### 4.4 WidgetGenerationService._normalize_event_candidates

签名：

```python
_normalize_event_candidates(
    request: GenerateWidgetCardRequest,
) -> list[EventAction]
```

用途：把最新方案中的 `candidateEventCandidates` 统一成内部 `EventAction` 列表。

支持来源：

```text
candidateEventCandidates
```

一般不从外部直接调用，由 `generate_widget_card` 内部调用。

### 4.6 WidgetGenerationService._build_artifact

签名：

```python
_build_artifact(...) -> WidgetArtifact
```

用途：把 genui、CardSpec、TaskSpec、有效能力、移除能力和版本元数据组装为完整 artifact。

一般不从外部直接调用，由生成流程内部调用。

## 5. Registry 方法

### 5.1 CapabilityRegistry

位置：

```text
cloud/services/capability_registry.py
```

### 5.2 IDSClient

位置：

```text
cloud/services/ids_client.py
```

用途：封装 IDS mock/真实远程数据源选择、已安装应用查询和响应解析，输出稳定的 `IDSDeviceCapabilityState`。`enable_ids_mock` 默认开启；开启时只读 mock，关闭时忽略 mock 并只查真实远程 IDS，任一路径失败都返回空 IDS 结果且不跨数据源回退。`DeviceCapabilityResolver` 不直接读取 IDS 文件。

构造：

```python
registry = CapabilityRegistry("app-11.7.5.205_rom-6.0")
```

不传版本时可使用 device 版本推导：

```python
registry = CapabilityRegistry(device_rom_version="CLS-AL30 6.0.0.328")
```

#### list_data_capabilities

```python
list_data_capabilities() -> list[DataCapability]
```

读取当前版本 `data_capabilities.json`。

#### list_event_capabilities

```python
list_event_capabilities() -> list[EventCapability]
```

读取当前版本 `event_capabilities.json`。

#### list_asset_capabilities

```python
list_asset_capabilities() -> list[AssetCapability]
```

读取当前版本 `asset_capabilities.json`。

#### get_data_capability

```python
get_data_capability(capability_id: str) -> DataCapability | None
```

按 ID 获取数据能力。不存在时返回 `None`。

#### get_event_capability

```python
get_event_capability(capability_id: str) -> EventCapability | None
```

按 ID 获取事件能力。不存在时返回 `None`。

#### get_asset_capability

```python
get_asset_capability(asset_id: str) -> AssetCapability | None
```

按 ID 获取素材能力。不存在时返回 `None`。

### 5.2 A2UIProtocolRegistry

位置：

```text
cloud/services/protocol_registry.py
```

构造：

```python
registry = A2UIProtocolRegistry("a2ui-form-rom6.0-v1")
```

#### get_profile

```python
get_profile() -> dict
```

读取：

```text
data/protocol_profiles/{profile_id}/protocol.md
data/protocol_profiles/{profile_id}/component-catalog.md
data/protocol_profiles/{profile_id}/data-binding.md
```

返回协议版本、catalogId、尺寸、组件白名单、样式白名单和 md 原文。

## 6. 能力过滤方法

### 6.1 DeviceCapabilityResolver.resolve_capability_overview

位置：

```text
cloud/services/device_capability_resolver.py
```

签名：

```python
resolve_capability_overview(
    device: DeviceContext,
) -> tuple[list[DataCapability], list[EventCapability], list[AssetCapability], list[RemovedCapability]]
```

用途：第一个接口内部只对命中配置包名范围的数据和事件能力做安装包可用性过滤；默认范围仅包含 `com.huawei.hmos.health.core`。一次 IDS 已安装应用快照供本次裁决复用，素材直接保留。

过滤顺序：

```text
读取 ids_installation_filter_package_names
 -> 找出 requiredPackages 中命中配置范围的包名
 -> 存在命中项时读取 IDS t_ids_kv_ohos_installed_apps
 -> 提取 values[].data.bundleName
 -> 精确匹配受检包名
 -> 缺少任一受检包名时以 PACKAGE_NOT_INSTALLED 移除能力
```

配置为空或注册表没有依赖命中配置范围时，不查询 IDS；范围外的依赖只保留为注册表元数据，不影响本次可用性。

返回：

```text
data_capabilities   可用数据能力
event_capabilities  可用事件能力
asset_capabilities  可用素材能力
removed             不可用能力和原因
```

使用示例：

```python
data_caps, event_caps, assets, removed = resolver.resolve_capability_overview(
    device=request.device,
)
```

### 6.2 DeviceCapabilityResolver.resolve_generation_data_bindings

签名：

```python
resolve_generation_data_bindings(
    candidate_bindings: list[CandidateDataBinding],
) -> tuple[list[CandidateDataBinding], list[DataCapability], list[RemovedCapability]]
```

用途：第三接口只校验能力仍在当前注册表中、参数符合 `inputSchema`、`writeResultTo` 合法且无冲突；不查询 IDS，也不重复执行 `dependencies` 过滤。

### 6.3 IDSClient.get_device_capability_state

签名：

```python
get_device_capability_state(device: DeviceContext, request_id: str) -> IDSDeviceCapabilityState
```

用途：按 `enable_ids_mock` 选择唯一数据源，并把响应转换为内部包名集合：

```text
enable_ids_mock=true
 -> 只读取 mock_ids_response_path
 -> 文件不存在、不可读、JSON/结构无效时使用空 nameSpaces
 -> 不构造或发送远程 IDS 请求

enable_ids_mock=false
 -> 忽略 mock_ids_response_path
 -> 构造真实 IDS 请求，只请求 t_ids_kv_ohos_installed_apps namespace
 -> 远程未配置、失败或响应无效时使用空 nameSpaces
 -> 不回退 mock
```

```text
installed_apps    已安装应用 bundleName 集合；不保留也不比较 versionName
```

默认 mock 文件为微服务内部的 `cloud/data/mock/ids_res.json`，只声明 mock 已安装应用。相对路径统一从 `cloud/` 解析，不读取仓库根目录或 Skill 目录。mock 文件是否存在不决定运行模式；运行模式只由 `enable_ids_mock` 决定。

### 6.4 DeviceCapabilityResolver._check_required_packages

用途：对能力 `requiredPackages[].packageName` 中命中 `ids_installation_filter_package_names` 的包名做区分大小写的精确匹配；全部受检包名都存在才通过，不比较包版本。当前默认只匹配运动健康包。

一般不外部调用。

### 6.5 DeviceCapabilityResolver._valid_arguments

用途：用 JSON Schema 校验候选能力参数。

一般不外部调用。

### 6.6 DeviceCapabilityResolver._find_write_result_conflict

用途：检查多个 `writeResultTo` 是否相同、互为父子或互相覆盖。

一般不外部调用。

### 6.7 DeviceCapabilityResolver._removed

用途：把错误码转换成 `RemovedCapability`，包含内部 reason 和用户可读原因。

## 7. 构建方法

### 7.1 CardSpecBuilder.build

位置：

```text
cloud/services/card_spec_builder.py
```

签名：

```python
build(
    size: WidgetSize,
    effective_bindings: list[CandidateDataBinding],
    title: str,
    description: str,
) -> CardSpec
```

用途：根据过滤后的有效能力生成最终 CardSpec。

其中 `title` 和 `description` 来自第三个接口 `generateWidgetCard` 的入参，
由 `WidgetGenerationService` 传给 `CardSpecBuilder`，最终随 CardSpec 写入 artifact。

规则：

```text
有有效 dataBindings -> 动态 CardSpec
无有效 dataBindings -> 静态 CardSpec
点击事件不进入 CardSpec
静态 CardSpec 不强制改尺寸，按请求 size 返回
动态和静态 CardSpec 都保留 title、description
```

### 7.2 TaskSpecBuilder.build

位置：

```text
cloud/services/task_spec_builder.py
```

签名：

```python
build(
    user_query: str,
    size: WidgetSize,
    effective_bindings: list[CandidateDataBinding],
    effective_data_capabilities: list[DataCapability],
    event_candidates: list[EventAction],
    asset_candidates: list[AssetCapability],
) -> TaskSpec
```

用途：构造传给 A2UI 模型的 TaskSpec。

TaskSpec 顶层只包含：

```text
userQuery
size
eventCandidates
dataModelSchema
assetCandidates
```

### 7.3 TaskSpecBuilder 字段投影

用途：按 JSON Pointer 校验 `candidateOutputFields` 是否能直接解析到能力 `outputSchema` 叶子，从该叶子读取必需的 `type` 和 `description`；优先使用显式 `sampleValue`，缺省时按类型生成受控默认值：`string` 为 `"示例"`，`integer/number` 为 `0`，`boolean` 为 `false`，`null` 为 `null`。随后按 `writeResultTo + 原叶子路径` 合并多个能力的 `dataModelSchema`。数组元素 schema 统一使用 canonical 下标 `0`，例如 `/events/0/title`；其它数组下标视为非法投影。部分非法路径被忽略；未传投影或全部路径非法时回退到该能力全部合法叶子字段。缺少 `sampleValue` 不阻断注册表加载或字段投影；显式 `sampleValue` 的 JSON 类型与 `type` 不一致时仍拒绝能力配置。

端侧会将符合 `outputSchema` 的能力结果整体写入 `writeResultTo`，当前没有字段重命名、扁平化或派生字段转换层。因此 TaskSpec 不得使用独立映射表改写目标路径；未来需要转换时，应先增加并版本化实际运行时转换契约。

例如天气和日历会合并为：

```json
{
  "data": {
    "weather": {
      "current": {
        "temperatureText": {
          "type": "string",
          "description": "适合直接显示的温度文本，例如‘29°C’。",
          "sampleValue": "26℃"
        }
      }
    },
    "calendar": {
      "events": [
        {
          "title": {
            "type": "string",
            "description": "日程标题，例如‘会议’、‘咪咕视频《西班牙 VS 奥地利》’。",
            "sampleValue": "产品评审"
          }
        }
      ]
    }
  }
}
```

## 8. 模型调用、Prompt、校验、重试

### 8.1 PromptBuilder.build

位置：

```text
cloud/services/prompt_builder.py
```

签名：

```python
build(
    task_spec: TaskSpec,
    protocol_profile: dict,
    removed_capability_summary: str = "",
    previous_genui: str | None = None,
) -> list[dict[str, str]]
```

用途：构造 A2UI 模型输入。首次生成从 `system_prompt_file` 读取系统提示词；编辑模式从 `edit_system_prompt_file` 读取提示词，通过 `{{CREATE_SYSTEM_PROMPT}}` 组合通用生成规则，并额外把本轮指令、新 TaskSpec 和来源 genui 作为结构化用户数据传入，不传来源 URL。

### 8.2 A2UIModelClient.generate

位置：

```text
cloud/custom/a2ui_model_client.py
```

签名：

```python
generate(task_spec: TaskSpec, protocol_profile: dict, prompt: dict) -> str
```

用途：根据 `enable_a2ui_model_mock` 开关选择 A2UI 输出来源。

- 开关为 `true`：直接读取并返回与客户端同目录的 `mock.dat` 原始内容，不做字段替换或结构调整。
- 开关为 `false`：进入真实模型调用预留方法；当前保留 TODO 并抛出 `NotImplementedError`。

环境变量：

```text
WIDGET_SERVICE_ENABLE_A2UI_MODEL_MOCK=true
```

输出固定满足：

```text
第 1 行 createSurface
第 2 行 updateComponents
第 3 行 updateDataModel
```

后续接真实 A2UI 模型服务时实现 `_generate_from_real_model()`，无需改动上层生成流程。

### 8.3 A2UIModelClient._load_mock_data

用途：读取 `cloud/custom/mock.dat` 的完整 UTF-8 文本并直接返回。

### 8.4 ArtifactValidator.validate

位置：

```text
cloud/services/validator.py
```

签名：

```python
validate(artifact: WidgetArtifact, protocol_profile: dict) -> list[str]
```

用途：校验完整 artifact，而不是只校验 DSL。

当前校验项：

```text
genui 恰好三行 JSONL
createSurface/updateComponents/updateDataModel 顺序正确
surfaceId 三行一致
catalogId 与 profile 一致
root 尺寸与 size/profile 一致
DSL 动态绑定路径可从 TaskSpec.dataModelSchema 或能力 outputSchema 推导
组件在白名单内
CardSpec writeResultTo 位于 /data/
```

返回空列表表示校验通过；否则返回错误列表。默认记录非阻断错误日志并继续构造、保存首次模型输出，不重新调用模型；`enable_validation_failure_retry=true` 时才会触发最多一次重新生成。

### 8.5 RetryController.run

位置：

```text
cloud/services/retry_controller.py
```

签名：

```python
run(
    operation: Callable[[], str],
    validate: Callable[[str], list[str]],
    *,
    retry_on_validation_failure: bool = False,
) -> RetryResult
```

用途：执行生成操作并校验。`retry_on_validation_failure=false` 时校验失败直接返回首次结果；为 `true` 时最多重试 1 次。最终校验错误由生成服务记录，但不阻断后续 artifact 流程。

返回：

```text
result       最后一次生成结果
retryCount   重试次数，0 或 1
errors       最后一次校验错误
```

## 9. Artifact 和响应方法

### 9.1 ArtifactStore.save

位置：

```text
cloud/services/artifact_store.py
```

签名：

```python
save(artifact: WidgetArtifact) -> ArtifactSaveResult
```

用途：把完整 artifact 写成具名 Markdown 代码块、上传并返回 URL 和服务端追踪摘要。

当前实现：

```text
计算完整 artifact 的服务端追踪摘要
按 cardspec/genui/schema/taskspec/effectivecapabilities/removedcapabilities/generationplan/meta 顺序写入代码块
使用 artifact UUID 生成不可覆盖的对象名
上传文件并返回 URL
```

代码里已按要求留 TODO：

```text
Replace this method with the team's OBS uploader.
```

后续接入 OBS 上传方法时必须保留全部具名代码块，不能只上传 genui 或 cardspec。返回的摘要用于日志关联和版本识别，调用方无需对下载文件重新计算摘要。

### 9.2 SourceArtifactRepository.load

位置：

```text
cloud/services/source_artifact_repository.py
```

用途：在 edit 模式下读取 `widget-artifact-v2` 并解析具名代码块。repository 不校验 URL 的协议、host、端口、query、fragment 或对象前缀；`enable_artifact_download_mock=true` 时从 URL path 提取文件名并只读取本地 mock OBS，默认为该模式且缺文件不回退网络；关闭后将原始 URL 交给 `utils/download_file_from_url.py` 的公共 `download_file` 方法。两种模式仍限制文件大小和超时，远程模式不跟随重定向，也不记录完整 URL。

### 9.3 ResponsePlanner.plan

位置：

```text
cloud/services/response_planner.py
```

签名：

```python
plan(
    requested_count: int,
    effective_count: int,
    removed: list[RemovedCapability],
    has_artifact: bool,
    generation_mode: str = "create",
) -> ResponsePlan
```

用途：把内部生成结果转换成主 Agent 可感知的状态和话术。

规则：

```text
无 artifact -> unsupported
请求能力全部有效且无移除 -> success
有能力被移除但仍生成 artifact -> degraded
其它可生成情况 -> success
```

## 10. 配置和工具函数

### 10.1 Settings

位置：

```text
cloud/config/config.py
```

用途：读取环境变量和默认配置。

支持环境变量：

```text
WIDGET_SERVICE_ENV
WIDGET_SERVICE_CAPABILITY_REGISTRY_VERSION
WIDGET_SERVICE_ENABLE_DEFAULT_CAPABILITY_REGISTRY_FALLBACK
WIDGET_SERVICE_IDS_INSTALLATION_FILTER_PACKAGE_NAMES
WIDGET_SERVICE_ENABLE_IDS_MOCK
WIDGET_SERVICE_PROTOCOL_PROFILE_ID
WIDGET_SERVICE_MOCK_IDS_RESPONSE_PATH
WIDGET_SERVICE_IDS_QUERY_URL
WIDGET_SERVICE_SYSTEM_PROMPT_FILE
WIDGET_SERVICE_EDIT_SYSTEM_PROMPT_FILE
WIDGET_SERVICE_ENABLE_ARTIFACT_VALIDATION
WIDGET_SERVICE_ENABLE_VALIDATION_FAILURE_RETRY
WIDGET_SERVICE_ENABLE_WIDGET_EDIT
WIDGET_SERVICE_ARTIFACT_BASE_URL
WIDGET_SERVICE_ENABLE_ARTIFACT_DOWNLOAD_MOCK
WIDGET_SERVICE_SOURCE_ARTIFACT_MAX_BYTES
WIDGET_SERVICE_SOURCE_ARTIFACT_READ_TIMEOUT_SECONDS
WIDGET_SERVICE_SOURCE_GENUI_MAX_CHARS
```

常用属性：

```text
package_root
data_root
resolved_mock_ids_response_path
```

### 10.2 get_settings

```python
get_settings() -> Settings
```

用途：获取缓存后的配置对象。

### 10.3 json_for_log

位置：

```text
cloud/app/logger.py
```

```python
json_for_log(value: Any) -> str
```

用途：将日志中的对象、数组、布尔值和空值序列化为紧凑的标准 JSON。键名和字符串使用双引号，布尔值使用 `true/false`，空值使用 `null`，避免 Python `dict/list` 的单引号 `repr`。

### 10.4 logger

位置：

```text
cloud/app/logger.py
```

用途：统一业务日志对象。流程节点使用 `info`，参数异常或业务失败使用 `error`；日志行可保留 `key=value` 形式，但其中的结构化值必须先调用 `json_for_log`。

日志约束：

- Pydantic 校验错误写入日志或接口错误详情前必须转换为 JSON-safe 结构，只保留 `loc`、`type`、`msg` 等可安全序列化字段，不得携带 `input` 或 `ctx` 中的原始对象。
- `uid` 是合法请求字段，请求示例和接口模型继续保留；但任何日志均不得记录 `uid` 原值、脱敏值或哈希值，也不得直接打印包含 `uid` 的完整请求对象；IDS 请求日志中的 `callingUid` 同样排除。
- 每次 `getWidgetCapabilityOverview` 的能力包过滤只记录一条汇总结果，集中包含 `requestId`、IDS 数据源、过滤是否执行、数量统计和被移除能力摘要；禁止逐能力打印依赖包检查日志。
- 接口开始、结束等生命周期日志可以保留，但不能重复打印能力包过滤明细或第二份过滤汇总。

示例：

```python
from app.logger import json_for_log, logger

logger.info(
    "flow_started "
    f"operation=generateWidgetCard candidates={json_for_log(['ViewWeather'])}"
)
```

### 10.5 load_json

位置：

```text
cloud/services/json_loader.py
```

签名：

```python
load_json(path: Path) -> Any
```

用途：按 UTF-8 读取 JSON 文件。

## 11. 数据模型说明

### 11.1 capability.py

`RequiredPackage`：依赖应用包名。运行时只保留 `packageName`，旧清单中的 `minVersion` 等额外字段兼容忽略。

`Dependencies`：能力安装依赖，当前只消费 `requiredPackages[].packageName`；能力未声明时按空依赖处理。旧清单中的 ROM/App 版本、provider、intent 和权限等额外字段加载时忽略，不参与可用性过滤。

`DataCapability`：数据能力完整定义，用于 schema 返回、过滤、CardSpec 和 TaskSpec 构造。其中 `defaultWriteResultTo` 是可选建议字段，存在时才校验路径；第三接口实际使用请求中的 `writeResultTo`。`outputSchema` 叶子的 `type` 和 `description` 必需，`sampleValue` 可选；显式样例类型错误时拒绝能力配置，缺省样例由 TaskSpecBuilder 按字段类型生成受控默认值。

`EventCapability`：事件能力定义，用于入口事件过滤。

`AssetCapability`：素材能力定义，用于 TaskSpec 的素材白名单。

`RemovedCapability`：被过滤掉的能力，包含：

```text
id
type
reason
userReadableReason
```

### 11.2 generation.py

`DeviceContext`：工具层注入的设备上下文。

`CandidateDataBinding`：主 Agent 候选数据绑定。

`EventAction`：候选事件动作。

`GenerationOptions`：生成选项。

`CardSpec`：最终 CardSpec。

`TaskSpec`：传给 A2UI 模型的输入契约。

### 11.3 artifact.py

`ArtifactMeta`：artifact 版本元数据，包含 apiVersion、taskSpecVersion、cardSpecVersion、protocolProfileId、capabilityRegistryVersion 等。

`WidgetArtifact`：完整 artifact，包含：

```text
schemaVersion
genui
cardSpec
taskSpec
effectiveCapabilities
removedCapabilities
meta
```

### 11.4 api/schemas.py

`VersionedToolRequest`：所有工具请求的版本字段基类。

`CapabilityOverviewRequest / Response`：能力概述接口请求和响应。

`DataCapabilitySchemasRequest / Response`：数据能力 schema 接口请求和响应。

`GenerateWidgetCardRequest / Response`：卡片生成接口请求和响应。

`WidgetCardServiceRequest`：最新统一工具入口请求体。


## 12. 新增能力的方法

新增数据能力：

1. 直接更新当前版本目录中的 `data_capabilities.json`；它是微服务运行时的权威数据源。
2. 可选声明合法的 `/data/...` JSON Pointer `defaultWriteResultTo`；只有能力确实需要按安装包过滤时才声明仅含包名的 `dependencies.requiredPackages`，缺省依赖按 `requiredPackages=[]` 处理。非空、可遍历的 `outputSchema` 每个叶子必须包含 `type/description`，并推荐维护高质量、脱敏受控的 `sampleValue`。缺少 `sampleValue` 不阻断注册表加载，TaskSpecBuilder 会按类型补充受控默认值；显式 `sampleValue` 的 JSON 类型必须与 `type` 一致。当前内置注册表继续为所有叶子维护高质量样例。
3. 增加或更新测试，覆盖第一接口过滤、schema 获取和生成。

新增事件能力：

1. 直接更新当前版本目录中的 `event_capabilities.json`，保持事件 ID 稳定；只有事件确实需要按安装包过滤时才在对应目标项声明仅含包名的 `dependencies.requiredPackages`，缺省按空依赖处理。
2. 第一接口确认可用后，在第三接口里通过 `candidateEventCandidates` 传入。

新增素材：

1. 直接更新当前版本目录中的 `asset_capabilities.json`，补齐唯一的 `id`、`src`、`description` 和 `sceneTags`。
2. 第一接口确认可用后，在第三接口里通过 `candidateAssetIds` 传入。

新增能力版本：

```text
复制 data/capabilities/app-11.7.5.205_rom-6.0 为新文件夹
修改 JSON 文件
请求时传 capabilityRegistryVersion=新文件夹名
```

## 13. 验证命令

```bash
cd D:\ai-workspace\code-github\CreateMyCard-team-lff
$env:PYTHONPATH='widget_service\src'
python -m pytest widget_service\tests
python -m ruff check widget_service
python -m compileall -q widget_service\cloud widget_service\tests
```
