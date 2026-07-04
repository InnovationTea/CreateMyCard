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
curl http://127.0.0.1:8000/health
```

返回：

```json
{
  "status": "ok"
}
```

## 2. 目录和版本规则

能力清单按 `appVersion + romVersion` 生成的文件夹名做版本隔离：

```text
cloud/data/capabilities/{capabilityRegistryVersion}/
├─ data_capabilities.json
├─ event_capabilities.json
└─ asset_capabilities.json
```

当前默认版本：

```text
app-1.0.0_rom-7.0.0
```

A2UI 协议 profile 也按文件夹隔离：

```text
cloud/data/protocol_profiles/{protocolProfileId}/profile.json
```

当前默认 profile：

```text
a2ui-form-rom7-v1
```

工具入参里可以传：

```json
{
  "capabilityRegistryVersion": "app-1.0.0_rom-7.0.0",
  "protocolProfileId": "a2ui-form-rom7-v1"
}
```

不传时使用 `.env` 或默认配置。

## 3. WebSocket 接口

最新云侧方案把微服务对外抽象成一个工具：`widgetCardService`。主 Agent 只需要传 `operation` 和该操作需要的参数；`uid`、`device`、`appVersion`、`romVersion`、`xiaoyiVersion` 等上下文由工具层自动注入，本地测试时可以显式传入。

唯一业务入口：

```text
WS /api/v1/ws/tools/widgetCardService
```

连接成功后服务先返回 ready 消息：

```json
{
  "type": "ready",
  "tool": "widgetCardService",
  "operations": [
    "getWidgetCapabilityOverview",
    "getDataCapabilitySchemas",
    "generateWidgetCard"
  ]
}
```

统一消息最小结构：

```json
{
  "requestId": "overview-1",
  "arguments": {
    "uid": "test-user-001",
    "appVersion": "1.0.0",
    "romVersion": "7.0.0",
    "xiaoyiVersion": "1.0.0",
    "device": {
      "deviceId": "5e64f3e9-0a80-d719-d689-3c36eca5eeb6",
      "deviceType": "ALN-AL00",
      "romVersion": "ALN-AL00 7.0.0.36",
      "ohosApiVersion": 36
    },
    "operation": "getWidgetCapabilityOverview"
  }
}
```

支持的 `operation`：

```text
getWidgetCapabilityOverview
getDataCapabilitySchemas
generateWidgetCard
```

### 3.1 GET /health

用途：服务健康检查。

请求：

```bash
curl http://127.0.0.1:8000/health
```

响应：

```json
{
  "status": "ok"
}
```

### 3.2 operation=getWidgetCapabilityOverview

对应工具能力：`getWidgetCapabilityOverview`

用途：返回主 Agent 可用于候选筛选的能力概述。数据能力只返回概述，不返回完整 schema；事件能力和素材候选在这里返回较完整信息。

请求示例：

```json
{
  "requestId": "overview-1",
  "arguments": {
    "uid": "test-user-001",
    "operation": "getWidgetCapabilityOverview",
    "locale": "zh-CN",
    "appVersion": "1.0.0",
    "romVersion": "7.0.0",
    "xiaoyiVersion": "1.0.0",
    "device": {
      "deviceId": "5e64f3e9-0a80-d719-d689-3c36eca5eeb6",
      "deviceType": "ALN-AL00",
      "romVersion": "ALN-AL00 7.0.0.36",
      "ohosApiVersion": 36
    },
    "capabilityRegistryVersion": "app-1.0.0_rom-7.0.0"
  }
}
```

响应消息核心字段：

```json
{
  "type": "result",
  "tool": "widgetCardService",
  "operation": "getWidgetCapabilityOverview",
  "requestId": "overview-1",
  "data": {
    "apiVersion": "v1",
    "capabilityRegistryVersion": "app-1.0.0_rom-7.0.0",
    "dataCapabilities": [
      {
        "id": "ViewWeather",
        "description": "查询当前天气、空气质量和未来预报"
      }
    ],
    "eventCapabilities": [],
    "assetCandidates": []
  }
}
```

### 3.3 operation=getDataCapabilitySchemas

对应工具能力：`getDataCapabilitySchemas`

用途：针对主 Agent 已选中的数据能力渐进加载完整 schema。

请求示例：

```json
{
  "requestId": "schema-1",
  "arguments": {
    "uid": "test-user-001",
    "operation": "getDataCapabilitySchemas",
    "appVersion": "1.0.0",
    "romVersion": "7.0.0",
    "xiaoyiVersion": "1.0.0",
    "device": {
      "deviceId": "5e64f3e9-0a80-d719-d689-3c36eca5eeb6",
      "deviceType": "ALN-AL00",
      "romVersion": "ALN-AL00 7.0.0.36",
      "ohosApiVersion": 36
    },
    "dataCapabilityIds": ["ViewWeather", "calendar.events.search"],
    "capabilityRegistryVersion": "app-1.0.0_rom-7.0.0"
  }
}
```

响应消息核心字段：

```json
{
  "type": "result",
  "tool": "widgetCardService",
  "operation": "getDataCapabilitySchemas",
  "requestId": "schema-1",
  "data": {
    "apiVersion": "v1",
    "capabilityRegistryVersion": "app-1.0.0_rom-7.0.0",
    "dataCapabilities": [
      {
        "id": "ViewWeather",
        "inputSchema": {},
        "outputSchema": {},
        "defaultWriteResultTo": "/data/weather",
        "dataModelSkeleton": {}
      }
    ],
    "missingCapabilityIds": []
  }
}
```

`missingCapabilityIds` 用来告诉主 Agent 哪些能力 ID 没有注册。

### 3.4 operation=generateWidgetCard

对应统一工具能力：`widgetCardService`，`operation=generateWidgetCard`

用途：主生成接口。能力过滤属于这个接口内部流程。

请求示例：

```json
{
  "requestId": "generate-1",
  "arguments": {
    "uid": "test-user-001",
    "operation": "generateWidgetCard",
    "userQuery": "帮我做通勤卡片，包含天气和今日日程",
    "size": "2x4",
    "appVersion": "1.0.0",
    "romVersion": "7.0.0",
    "xiaoyiVersion": "1.0.0",
    "device": {
      "deviceId": "5e64f3e9-0a80-d719-d689-3c36eca5eeb6",
      "deviceType": "ALN-AL00",
      "romVersion": "ALN-AL00 7.0.0.36",
      "ohosApiVersion": 36
    },
    "protocolProfileId": "a2ui-form-rom7-v1",
    "candidateDataBindings": [
      {
        "capabilityId": "ViewWeather",
        "arguments": {
          "districtName": "青浦区",
          "forecastDays": 1
        },
        "writeResultTo": "/data/weather"
      },
      {
        "capabilityId": "calendar.events.search",
        "arguments": {
          "timeRange": "today"
        },
        "writeResultTo": "/data/calendar"
      }
    ],
    "candidateEventCandidates": [
      {
        "capabilityId": "event.open.weather",
        "action": {
          "call": "clickToDeeplink",
          "args": {
            "uri": "hww://www.huawei.com/totemweather?enterType=share"
          }
        }
      }
    ],
    "candidateAssetIds": ["asset.drop_1", "asset.calendar_fill"]
  }
}
```

响应消息核心字段：

```json
{
  "type": "result",
  "tool": "widgetCardService",
  "operation": "generateWidgetCard",
  "requestId": "generate-1",
  "data": {
    "apiVersion": "v1",
    "status": "success",
    "artifactUrl": "https://obs.todo.local/widget/xxx.json",
    "artifactDigest": "sha256:xxx",
    "suggestSize": "2x4",
    "userMessage": "已为你生成可用的桌面卡片。",
    "removedCapabilities": [],
    "errorCode": "",
    "effectiveCapabilities": {
      "data": ["ViewWeather", "calendar.events.search"],
      "event": [],
      "asset": ["asset.drop_1", "asset.calendar_fill"]
    }
  }
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
          "uri": "hww://weather"
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

用途：读取指定版本的能力清单，返回主 Agent 做候选筛选需要的概述。

使用示例：

```python
from api.schemas import CapabilityOverviewRequest
from services.widget_generation_service import WidgetGenerationService

service = WidgetGenerationService()
response = service.get_widget_capability_overview(
    CapabilityOverviewRequest(appVersion="1.0.0", romVersion="7.0.0")
)
```

内部流程：

```text
CapabilityRegistry(version)
 -> list_data_capabilities()
 -> list_event_capabilities()
 -> list_asset_capabilities()
 -> 组装 CapabilityOverviewResponse
```

### 4.2 WidgetGenerationService.get_data_capability_schemas

签名：

```python
get_data_capability_schemas(
    request: DataCapabilitySchemasRequest,
) -> DataCapabilitySchemasResponse
```

用途：按能力 ID 返回完整 schema、默认写入路径和 DataModel 骨架。

使用示例：

```python
response = service.get_data_capability_schemas(
    DataCapabilitySchemasRequest(
        dataCapabilityIds=["ViewWeather", "calendar.events.search"],
        capabilityRegistryVersion="app-1.0.0_rom-7.0.0",
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

用途：主生成编排方法。

内部流程：

```text
1. 读取 CapabilityRegistry
2. 读取 A2UIProtocolRegistry
3. DeviceCapabilityResolver 过滤候选 dataBindings
4. 规范化事件候选
5. 过滤事件候选
6. 过滤素材候选
7. 无可用能力且无入口时返回 unsupported
8. CardSpecBuilder 生成最终 CardSpec
9. TaskSpecBuilder 生成 TaskSpec
10. PromptBuilder 生成模型输入
11. A2UIModelClient mock 生成 genui
12. RetryController 控制最多 1 次重试
13. ArtifactValidator 校验完整 artifact
14. ArtifactStore 保存 artifact，当前为 OBS TODO hook
15. ResponsePlanner 生成 status 和 userMessage
```

使用示例：

```python
from api.schemas import GenerateWidgetCardRequest
from models.generation import CandidateDataBinding

response = service.generate_widget_card(
    GenerateWidgetCardRequest(
        userQuery="帮我做一个只显示今天上海天气的桌面卡片",
        size="2x4",
        romVersion="7.0.0",
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

### 4.5 WidgetGenerationService._build_artifact

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

用途：封装 IDS 查询与 mock IDS 响应解析，输出稳定的 `IDSDeviceCapabilityState`。当前读取 `docs/ids_res.txt`；后续接真实 IDS 时优先替换这个客户端，`DeviceCapabilityResolver` 不直接读取 IDS 文件。

构造：

```python
registry = CapabilityRegistry("app-1.0.0_rom-7.0.0")
```

不传版本时使用默认版本：

```python
registry = CapabilityRegistry()
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
registry = A2UIProtocolRegistry("a2ui-form-rom7-v1")
```

#### get_profile

```python
get_profile() -> dict
```

读取：

```text
data/protocol_profiles/{profile_id}/profile.json
```

返回协议版本、catalogId、尺寸、组件白名单、样式白名单等。

## 6. 能力过滤方法

### 6.1 DeviceCapabilityResolver.resolve_data_bindings

位置：

```text
cloud/services/device_capability_resolver.py
```

签名：

```python
resolve_data_bindings(
    candidate_bindings: list[CandidateDataBinding],
    rom_version: str,
    app_version: str,
    xiaoyi_version: str,
) -> tuple[list[CandidateDataBinding], list[DataCapability], list[RemovedCapability]]
```

用途：第三个接口内部的数据能力过滤。

过滤顺序：

```text
能力 ID 是否注册
 -> ROM/App/小艺版本是否满足
 -> 依赖 App 是否安装且版本满足
 -> IDS provider/intent 是否存在
 -> 权限状态是否允许
 -> arguments 是否符合 inputSchema
 -> writeResultTo 是否位于 /data/ 且无冲突
```

返回：

```text
effective_bindings       可进入最终 CardSpec 的 dataBindings
effective_capabilities   可进入 TaskSpec DataModel 的能力定义
removed                  被移除的能力和原因
```

使用示例：

```python
resolver = DeviceCapabilityResolver(registry)
effective_bindings, effective_caps, removed = resolver.resolve_data_bindings(
    candidate_bindings=request.candidateDataBindings,
    rom_version="7.0.0",
    app_version="1.0.0",
    xiaoyi_version="1.0.0",
)
```

### 6.2 DeviceCapabilityResolver.resolve_event_candidates

签名：

```python
resolve_event_candidates(
    candidates: list[EventAction],
    rom_version: str,
    app_version: str,
    xiaoyi_version: str,
) -> tuple[list[EventAction], list[RemovedCapability]]
```

用途：过滤点击事件候选。点击事件不会进入 CardSpec，只进入 TaskSpec 的 `eventCandidates`。

### 6.3 IDSClient.get_device_capability_state

签名：

```python
get_device_capability_state() -> IDSDeviceCapabilityState
```

用途：读取 mock IDS 响应并转换为内部判断用的结构：

```text
installed_apps    已安装应用包名与版本
providers         设备可用 provider 集合
intent_targets    设备可用 intent target 集合
permissions       设备权限状态
```

当前默认补了一批一方能力 provider/intent，方便 mock 流程跑通。后续接真实 IDS 时优先替换 `IDSClient`，不需要让 `DeviceCapabilityResolver` 直接读取 IDS 文件。

### 6.4 DeviceCapabilityResolver._check_common_dependencies

用途：检查能力依赖，包括最低版本、依赖包、provider、intent、权限。

一般不外部调用。

### 6.5 DeviceCapabilityResolver._valid_arguments

用途：用 JSON Schema 校验候选能力参数。

一般不外部调用。

### 6.6 DeviceCapabilityResolver._find_write_result_conflict

用途：检查多个 `writeResultTo` 是否相同、互为父子或互相覆盖。

一般不外部调用。

### 6.7 DeviceCapabilityResolver._version_gte / _extract_version

用途：版本比较和从复杂 ROM 字符串里提取版本号。

例如：

```text
ALN-AL00 7.0.0.36 -> 7.0.0.36
```

### 6.8 DeviceCapabilityResolver._removed

用途：把错误码转换成 `RemovedCapability`，包含内部 reason 和用户可读原因。

## 7. 构建方法

### 7.1 CardSpecBuilder.build

位置：

```text
cloud/services/card_spec_builder.py
```

签名：

```python
build(size: WidgetSize, effective_bindings: list[CandidateDataBinding]) -> CardSpec
```

用途：根据过滤后的有效能力生成最终 CardSpec。

规则：

```text
有有效 dataBindings -> 动态 CardSpec
无有效 dataBindings -> 静态 CardSpec
点击事件不进入 CardSpec
静态 CardSpec 不强制改尺寸，按请求 size 返回
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
dataModel
assetCandidates
```

### 7.3 TaskSpecBuilder._deep_merge

用途：合并多个能力的 `dataModelSkeleton`。

例如天气和日历会合并为：

```json
{
  "data": {
    "weather": {},
    "calendar": {}
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
) -> dict
```

用途：构造 A2UI 模型输入。当前是 mock prompt 结构，后续可替换为真实模型服务需要的 messages。

### 8.2 A2UIModelClient.generate

位置：

```text
cloud/services/a2ui_model_client.py
```

签名：

```python
generate(task_spec: TaskSpec, protocol_profile: dict, prompt: dict) -> str
```

用途：mock 生成三行 genui JSONL。

输出固定满足：

```text
第 1 行 createSurface
第 2 行 updateComponents
第 3 行 updateDataModel
```

后续接真实 A2UI 模型服务时替换这个类。

### 8.3 A2UIModelClient._title

用途：mock 阶段从用户 query 截取标题。

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
updateDataModel.value 与 TaskSpec.dataModel.value 一致
组件在白名单内
CardSpec writeResultTo 位于 /data/
```

返回空列表表示校验通过；否则返回错误列表。

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
) -> tuple[str, int, list[str]]
```

用途：执行生成操作并校验，失败最多重试 1 次。

返回：

```text
result       最后一次生成结果
retry_count  重试次数，0 或 1
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
save(artifact: WidgetArtifact) -> tuple[str, str]
```

用途：保存完整 artifact 并返回 URL 和 sha256 digest。

当前实现：

```text
计算完整 artifact 的 sha256 digest
返回 mock OBS URL
```

代码里已按要求留 TODO：

```text
Replace this method with the team's OBS uploader.
```

后续你们只需要在这里接自己的 OBS 上传方法，注意上传内容必须是完整 artifact JSON，不能只上传 genui。

### 9.2 ResponsePlanner.plan

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
) -> tuple[GenerationStatus, str, str]
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
cloud/core/config.py
```

用途：读取环境变量和默认配置。

支持环境变量：

```text
WIDGET_SERVICE_ENV
WIDGET_SERVICE_CAPABILITY_REGISTRY_VERSION
WIDGET_SERVICE_PROTOCOL_PROFILE_ID
WIDGET_SERVICE_MOCK_IDS_RESPONSE_PATH
WIDGET_SERVICE_ARTIFACT_BASE_URL
```

常用属性：

```text
package_root
data_root
repo_root
resolved_mock_ids_response_path
```

### 10.2 get_settings

```python
get_settings() -> Settings
```

用途：获取缓存后的配置对象。

### 10.3 configure_logging

位置：

```text
cloud/core/logging.py
```

用途：配置 structlog JSON 日志。

### 10.4 load_json

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

`RequiredPackage`：依赖应用包名和最低版本。

`Dependencies`：能力依赖，包括最低 ROM/App/小艺版本、依赖包、provider、intent、权限。

`DataCapability`：数据能力完整定义，用于 schema 返回、过滤、CardSpec 和 TaskSpec 构造。

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

1. 在新版本目录或当前版本目录编辑 `data_capabilities.json`。
2. 补齐 `id`、`inputSchema`、`outputSchema`、`defaultWriteResultTo`、`dataModelSkeleton`、`dependencies`。
3. 增加或更新测试，覆盖 schema 获取、过滤和生成。

新增事件能力：

1. 编辑 `event_capabilities.json`。
2. 补齐 `id`、`call`、`parametersSchema`、`dependencies.requiredIntentTargets`。
3. 第三个接口里通过 `candidateEventCandidates` 传入。

新增素材：

1. 编辑 `asset_capabilities.json`。
2. 补齐 `id`、`src`、`description`、`sceneTags`。
3. 第三个接口里通过 `candidateAssetIds` 传入。

新增能力版本：

```text
复制 data/capabilities/app-1.0.0_rom-7.0.0 为新文件夹
修改 JSON 文件
请求时传 capabilityRegistryVersion=新文件夹名
```

## 13. 验证命令

```bash
cd D:\ai-workspace\code-github\CreateMyCard-team-lff
$env:PYTHONPATH='widget_service\src'
python -m pytest widget_service\tests
python -m ruff check widget_service
python -m compileall -q widget_service\src widget_service\tests
```
