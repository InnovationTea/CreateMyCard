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
uvicorn start_websocket_server:app --reload
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

能力清单由 `cloud/data/capabilities/registry_ranges.json` 统一维护 App/ROM 二维左闭右开区间，目录只作为实际注册表版本：

```text
cloud/data/capabilities/{capabilityRegistryVersion}/
├─ data_capabilities.json
├─ event_capabilities.json
└─ asset_capabilities.json
```

当前能力清单及命中区间：

```text
App [11.7.5.205, 11.7.7.330) + ROM [7.0, 7.2) -> app-11.7.5.205_rom-6.0
App [11.7.7.330, 12.0.0.0) + ROM [7.0, 8.0) -> app-11.7.7.300_rom-7.0
```

App 使用完整数字版本，ROM 从完整 `romVersion` 中抽取主次版本。索引加载时会拒绝倒置区间、App 与
ROM 同时重叠的配置以及不存在的目标目录。

能力目录名是快照标识，不用于推导实际命中范围。当前配置下 ROM 6.x、旧 App 搭配 ROM 7.2 及以上，
以及其它未覆盖组合没有直接命中；是否使用默认清单由回退开关决定。

五个接口在能力清单版本未命中或目标目录不可用且
`WIDGET_SERVICE_ENABLE_DEFAULT_CAPABILITY_REGISTRY_FALLBACK=true` 时，统一回退到默认的
`app-11.7.5.205_rom-6.0` 能力清单。
关闭开关时，第一、第二接口返回空清单/缺失能力，三个生成接口返回版本不支持。

第一接口的 IDS 安装过滤范围由
`WIDGET_SERVICE_IDS_INSTALLATION_FILTER_PACKAGE_NAMES` 配置，值为 JSON 字符串数组。默认包含
`["com.huawei.hmsapp.totemweather","com.huawei.hmos.health","com.huawei.hmos.calendar"]`，因此当前对天气、运动健康和日历能力执行安装包过滤；配置为空数组时跳过 IDS 查询和安装过滤。

IDS 数据源由 `WIDGET_SERVICE_ENABLE_IDS_MOCK` 显式控制，默认值为 `true`：

- `true`：只读取 `WIDGET_SERVICE_MOCK_IDS_RESPONSE_PATH` 指定的 mock 文件；文件不存在、不可读、JSON 无效或响应结构无效时返回空 IDS 结果，不请求远程 IDS。
- `false`：忽略 mock 文件，只请求 `WIDGET_SERVICE_IDS_QUERY_URL` 指定的真实远程 IDS；远程未配置、请求失败或响应无效时返回空 IDS 结果，不回退 mock。

不能再根据 mock 文件是否存在自动选择或切换数据源。

DSL 质量失败重试由 `WIDGET_SERVICE_ENABLE_VALIDATION_FAILURE_RETRY` 控制，默认值为 `false`，同时覆盖
源 DSL 转换 error 和 Validator error。最大 repair 次数由
`WIDGET_SERVICE_VALIDATION_FAILURE_MAX_REPAIR_ATTEMPTS` 控制，默认 `1`，范围 `1～10`；warning 不触发
repair，全部 error 消失时提前停止。

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

`capabilityRegistryVersion` 和 `protocolProfileId` 均不由公开工具调用方选择；旧调用方继续传入时会被
静默忽略，不能绕过区间匹配或接口固定路由。

## 3. WebSocket 接口

当前微服务提供五个正式工具能力，其中第四个是 Design Compact DSL 生成变体，第五个是
TerseDSL-Nested-2 静态生成变体。客户端连接目标 path 后，
消息体只需要传该能力自己的参数，不需要再传 `operation`。新协议优先读取 `content.uid` 和
`content.romVersion`，对应字段缺失或为空时分别回退到 `userAuth.user.userId` 和
`deviceInfo.romVersion`。`odid` 只从可选的 `content.odid` 读取并映射到内部设备上下文；缺失或为空时
IDS 查询继续使用固定兜底值。用户和设备上下文通常由工具层自动注入，本地测试时可以显式传入。

业务入口：

```text
WS /api/v1/ws/tools/getWidgetCapabilityOverview
WS /api/v1/ws/tools/getDataCapabilitySchemas
WS /api/v1/ws/tools/generateWidgetCard
WS /api/v1/ws/tools/generateWidgetCardCompactDsl
WS /api/v1/ws/tools/generateWidgetCardTerseDslNested2
```

第四接口的 `AIWidgetStart/AIWidgetEnd` 指令由全局开关控制。每个生成请求会创建一个 UUID 格式的
`cardId`，放在指令的
`payload.executeParam.cardId`；同一请求的开始、成功和失败指令共用该值，不同请求使用不同值。指令的
`payload.executeParam.size` 优先使用 `content.size`；首次生成未传时为 `2x2`，编辑未传时继承来源
artifact 的 `cardSpec.suggestSize`。指令帧
`streamContent` 外层为 command 消息 JSON，`content` 保存原指令 JSON 字符串，`content_type` 固定为
`aIWidgetDirectives`，`event` 固定为 `command`，`process_time` 使用当前本地时间，`task_id` 使用 requestId。

`generateWidgetCard` 固定使用标准 A2UI Form profile，后端由
`WIDGET_SERVICE_A2UI_FORM_MODEL_BACKEND` 选择；`generateWidgetCardCompactDsl` 根据 App/ROM 区间选择
Design profile，后端由 `WIDGET_SERVICE_DESIGN_COMPACT_MODEL_BACKEND` 选择并生成
Design Compact DSL，再由服务内转换器读取该 Design profile 下的 `protocol.json`，生成标准三段 A2UI DSL。
第三至第五入口共享同一策略驱动生成管线、校验和 repair 语义，
调用方不需要传 `protocolProfileId`，旧值也不能覆盖路由选择结果。

主 Agent 调用第四接口时不感知 WebSocket 的 `content` 字段，只使用标准工具调用格式：`arguments`、
`functionName`、`skillName` 位于同层。`arguments` 必须直接传 JSON 对象，并包含 `bundleName`、
`userQuery`、`title`、`description` 等工具字段；若误传为 JSON 字符串，服务会在模型调用前返回
`/arguments` 错误，要求将字符串反序列化为对象后重新调用。

`generateWidgetCardTerseDslNested2` 从
`cloud/data/protocol_profiles/terse-dsl-nested-2/PROMPT.md` 读取本地 Prompt。模型输出只进入
`cloud/services/terse_dsl_nested2_converter.py` 的受限 Parser，不作为 Python 或 JavaScript 执行；
Parser 只接受单根组件调用、字面量、白名单组件和安全对象键，再复用标准 A2UI 转换与 artifact 校验。
该接口支持静态 create/edit；动态数据绑定和点击事件返回 `PROTOCOL_CAPABILITY_UNSUPPORTED`。edit 与
第四接口共用 `enable_widget_edit` 和 artifact 的 `designcompactdsl` 块，但会按 TerseDSL-Nested-2
语法验证其中的上一轮模型原始输出。第五接口沿用 Design Compact 后端配置；两项后端配置都可取
`mep` 或 `openai`。其它配置值会在启动配置校验阶段直接报错，不做自动迁移。

第四接口的协议区间索引位于 `cloud/data/protocol_profiles/registry_ranges.json`，其 App/ROM 区间与能力清单
保持一致：App `[11.7.5.205, 11.7.7.330)` 且 ROM `[7.0, 7.2)`，以及 App
`[11.7.7.330, 12.0.0.0)` 且 ROM `[7.0, 8.0)`。当前两段都映射到同一套 A2UI Form Profile 和
`design-compact-dsl`；未命中时，只有 `WIDGET_SERVICE_ENABLE_DEFAULT_PROTOCOL_PROFILE_FALLBACK=true`
才回退到 `WIDGET_SERVICE_PROTOCOL_PROFILE_ID`。

所有帧的插件顶层 `errorCode` 固定为 `"0"`，`errorMessage` 固定为空字符串，`items`
固定为空数组。业务错误码、异常详情和业务响应只放在 final 帧的 `streamContent` 中。
异常内容以中文类型说明开头，后面保留完整 `str(legacy_message)`，调用方应继续读取其中
的 `status`、`errorCode`、`error` 和 `data`，不能用插件顶层字段判断业务成功与否。
中文说明面向主 Agent，包含异常原因和建议动作。例如：

```text
工具参数传入有误，请检查必填字段、字段类型和字段取值后重新调用。报错信息如下：
type='error' ... errorCode='INVALID_ARGUMENTS' error={...}
```

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
docs/schemas/generateWidgetCardTerseDslNested2.schema.json
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

用途：先按 `romVersion`、`prdVer` 选择注册表，再读取 IDS 安装过滤包名配置。当前默认查询并精确匹配天气包 `com.huawei.hmsapp.totemweather`、运动健康包 `com.huawei.hmos.health` 和日历包 `com.huawei.hmos.calendar`。包版本、ROM/App 依赖版本、provider、intent、权限和素材版本不参与本阶段过滤。响应不包含 TaskSpec；数据能力、事件能力和素材都只返回主 Agent 决策所需的精简概述。

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
    }
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
    "eventCapabilities": [
      {
        "id": "event.open.weather",
        "description": "打开天气应用",
        "actionTemplate": {
          "call": "clickToDeeplink",
          "args": {
            "intentName": "Weather_CityCode",
            "bundleName": "",
            "abilityName": "",
            "uri": "{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' + ${/data/weather/location/cityCode} }}"
          }
        },
        "dynamicArguments": [
          {
            "path": "/uri",
            "description": "cityCode 取自天气结果中的城市编码，保留完整 URI 模板。",
            "type": "string"
          }
        ]
      }
    ],
    "assetCandidates": [
      {
        "id": "asset.drop_1",
        "description": "水滴图标，适合湿度和降雨场景"
      }
    ],
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
    "dataCapabilityIds": ["ViewWeather", "GetCalendarEvents"]
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
          "prefectureName": "上海市",
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
            "uri": "{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' + ${/data/weather/location/cityCode} }}"
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

只有包含 `generationplan` 的 `widget-artifact-v2` 可作为编辑来源。编辑开关默认关闭。标准 A2UI 和
Design Compact 两个生成入口都受同一个编辑开关控制，并沿用相同的继承、替换和清空语义。

响应消息核心字段：

```json
{
  "type": "result",
  "tool": "generateWidgetCard",
  "operation": "generateWidgetCard",
  "requestId": "generate-1",
  "data": {
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
          "uri": "{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' + ${/data/weather/location/cityCode} }}"
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

用途：读取指定版本的能力清单，并在注册表依赖命中配置的安装过滤范围时查询一次 IDS，返回当前设备实际可用的精简能力概述及不可用清单。事件返回可直接复制的完整 `actionTemplate` 和动态参数说明；素材只返回 `id` 与 `description`。完整注册信息仍保留在微服务内，第三接口按 ID 还原。

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
async generate_widget_card(
    request: GenerateWidgetCardRequest,
    *,
    policy: GenerationRoutePolicy,
) -> GenerateWidgetCardResponse
```

用途：第三至第五接口的共用异步生成编排方法，只消费主 Agent 从第一接口可用清单中规划的能力。
公开包装方法只负责选择一次 `GenerationRoutePolicy`，其中集中定义协议/Profile、模型后端、源 DSL
格式、Processor、编辑/动态能力支持范围和 Validator error 是否阻断。

内部流程：

```text
1. 读取 CapabilityRegistry
2. 读取 A2UIProtocolRegistry
3. 解析候选 data/event/asset；校验参数、写入路径和注册表存在性，不查询 IDS
4. CardSpecBuilder 生成最终 CardSpec
5. TaskSpecBuilder 根据 writeResultTo、outputSchema 和候选字段投影生成 TaskSpec.dataModelSchema
6. PromptBuilder 生成模型输入
7. 异步 A2UIModelClient 生成当前策略要求的源 DSL
8. 对应 Processor 把源 DSL 转成标准 A2UI，并返回带阶段的结构化质量问题
9. 启用 Validator 时校验标准 artifact；转换 error 与 Validator error 统一交给 RetryController
10. RetryController 按开关和最大次数执行有限 repair，每轮重新经过同一 Processor 和 Validator
11. ArtifactStore 异步保存可用 artifact，当前为 OBS TODO hook
12. ResponsePlanner 生成 status 和 message
```

使用示例：

```python
from api.schemas import GenerateWidgetCardRequest
from models.generation import CandidateDataBinding

response = await service.generate_widget_card_a2ui_form(
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
                arguments={"prefectureName": "上海市", "forecastDays": 1},
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

用途：第一个接口内部只对命中配置包名范围的数据和事件能力做安装包可用性过滤；默认范围包含天气、运动健康和日历包。一次 IDS 已安装应用快照供本次裁决复用，素材直接保留。

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

### 6.2 GenerationPreflight.run

签名：

```python
run(request: GenerateWidgetCardRequest) -> GenerationPreflightResult
```

用途：生成接口在构造 Prompt 和调用模型前执行统一硬门禁。一次性校验数据、事件和素材候选，并在没有
blocking issue 时构造 CardSpec 和 TaskSpec；不查询 IDS，也不重复执行 `dependencies` 过滤。

阻断项包括未注册 ID、参数 schema 错误、静态数据入参中的绑定表达式、非法或冲突的
`writeResultTo`、无法从 outputSchema 推导的字段投影、事件 call/args、缺失或错误的数据引用，以及未注册
素材。字段投影不按布局区域数设置入口上限，数组数字下标只按 `items` Schema 校验。天气详情事件兼容
当前动态 URI 和历史静态 URI。issue 返回
`path/expected/actualType/agentAction/repairInstruction/referenceSource/retryable`，既不回显实际参数值，又能让
主 Agent 回到第一或第二接口结果完成定点修正。

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

用途：对能力 `requiredPackages[].packageName` 中命中 `ids_installation_filter_package_names` 的包名做区分大小写的精确匹配；全部受检包名都存在才通过，不比较包版本。当前默认匹配天气、运动健康和日历包。

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
由 `GenerationPreflight` 传给 `CardSpecBuilder`，最终随 CardSpec 写入 artifact。

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

`eventCandidates[]` 固定包含同层级的 `id/description/call/args`。其中 `description` 来自事件能力注册表，
只帮助模型理解事件用途；生成的事件处理器仍必须逐字段复用候选 `call/args`。

### 7.3 TaskSpecBuilder 字段投影

用途：按 JSON Pointer 读取已经由 `GenerationPreflight` 校验通过的 `candidateOutputFields`，从能力
`outputSchema` 叶子取得必需的 `type` 和 `description`；优先使用显式 `sampleValue`，缺省时按类型生成
受控默认值：`string` 为 `"示例"`，`integer/number` 为 `0`，`boolean` 为 `false`，`null` 为 `null`。随后
按 `writeResultTo + 原叶子路径` 合并多个能力的 `dataModelSchema`。显式展示投影不按布局主区域数量设置
字段上限；事件动作引用的合法数据叶子会自动补入，避免事件依赖延迟到 DSL 校验阶段才失败。数组元素
接受 `/events/0/title`、`/events/1/title`、`/events/2/title` 等数字下标，统一使用数组 `items` Schema
校验，不读取运行时实际数组长度。指向标量数组的投影会展开到其元素 Schema。
未传投影或传入空数组时回退到该能力全部合法叶子字段。缺少 `sampleValue` 不阻断注册表加载或字段投影；
显式 `sampleValue` 的 JSON 类型与 `type` 不一致时仍拒绝能力配置。

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

第四、第五接口不使用上述标准 A2UI edit system prompt。两者保持对应 Profile 的 `PROMPT.md` 原文作为
第一条 system 消息，并在第二条 user 消息中传入 `userQuery`、完整 TaskSpec 和
`previousDesignToken:{format,content}`。`content` 来自来源 artifact 的 `designcompactdsl` 原文，禁止以
标准 `genui` 兜底。

`build_repair()` 在首次调用实际使用的 system prompt 后追加 `repair_system_prompt_file`，并把首次 user
内容、当前最新源 DSL、`dslFormat` 和结构化 `qualityErrors` 编码成标准 JSON user 消息。转换错误至少包含
`stage`、`code`、`message`；完整 artifact 校验错误还传递具体校验错误码、`validatorStage`、`fileKind`、
`line`、`jsonPointer`、`actual`、`expected` 和校验器确定性生成的 `fixHint`，并用 `category` 保留通用错误
分类。编辑模式的首次 user 内容保留上一轮 `previousDesignToken`。模型返回修复后的同格式源 DSL，再次
执行对应 Processor 和标准 A2UI Validator。

修复模型调用会对完整 prompt 日志做脱敏，只记录修复类型和错误数量。

### 8.2 A2UIModelClient.generate

位置：

```text
cloud/custom/a2ui_model_client.py
```

签名：

```python
async generate(
    prompt: list[dict[str, str]],
    protocol_profile: dict | None = None,
) -> str
```

用途：通过统一入口生成模型 DSL。先根据 `enable_a2ui_model_mock` 判断是否使用 mock；真实模型后端由
生成接口的服务端路由配置选择，调用方不能通过请求参数切换。

- 开关为 `true`：直接读取并返回与客户端同目录的 `mock.dat` 原始内容，不做字段替换或结构调整。
- 第三接口读取 `WIDGET_SERVICE_A2UI_FORM_MODEL_BACKEND`；第四、第五接口读取
  `WIDGET_SERVICE_DESIGN_COMPACT_MODEL_BACKEND`。两项均可配置 `mep` 或 `openai`。
- `A2UIModelClient` 通过 `UnifiedModelClient` 调用物理模型。`mep` 路由直接使用 MEP；`openai` 路由默认
  使用 DeepSeek Platform master，模型异常重试耗尽后切换到 llmclient fallback。
- MEP 使用应用生命周期共享的异步 HTTP 连接池，DeepSeek Platform 使用异步 WebSocket；
  `cloud/custom/llmclient.py` 本体保持同步且不修改，通过模型 Runtime 的专用线程池适配。
- 模型调用边界内的请求异常、未规范化内部异常、流式响应显式错误或最终没有非空 DSL，统一按模型
  生成失败处理，不依赖上游错误码。模型失败重试开关关闭时直接返回
  `failed/A2UI_GENERATION_FAILED`；开启时使用同一提示词执行有限次数的异步指数退避重试。最终失败
  不调用 Validator、RepairController 或 ArtifactStore。

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

用途：校验完整 artifact，而不是只校验 DSL。标准 A2UI 直接调用 `cloud/services/card_validation/` 暴露的 Python API；不会执行 Skill 校验脚本或启动子进程。静态规则从 `cloud/data/validator_rules/` 加载，动态能力白名单从 artifact 和其能力版本目录加载；第四接口校验转换后的标准 A2UI，不保存转换前的 Design Token。

当前校验项：

```text
genui 恰好三行 JSONL
createSurface/updateComponents/updateDataModel 顺序正确
surfaceId 三行一致
catalogId 符合当前校验规则配置
createSurface 不声明 width/height，root width/height 使用 matchParent
DSL 动态绑定路径可从 updateDataModel.value、CardSpec outputSchema 或有效能力写入路径推导
组件类型和顶层字段符合规则配置
CardSpec 必填字段、suggestSize、dataBindings 和 writeResultTo 合法
事件及素材只能使用本次有效能力
```

返回空列表表示没有 error；warning 只记录日志，不触发修复。Processor 的转换问题和 Validator 问题
统一携带 `stage`、`code`、`message`。`enable_validation_failure_retry=true` 时才会携带当前最新源 DSL、
源格式和错误位置执行有限次数定向 repair。第四、第五接口转换失败始终阻断保存；Validator error 的
最终阻断策略由接口路由策略决定。

### 8.5 RetryController.run

位置：

```text
cloud/services/retry_controller.py
```

签名：

```python
async run(
    operation: Callable[[], str | Awaitable[str]],
    evaluate: Callable[[str], list[str] | Awaitable[list[str]]],
    *,
    retry_on_quality_failure: bool = False,
    max_repair_attempts: int = 1,
    repair: Callable[[str, list[str]], str | Awaitable[str]] | None = None,
) -> RetryResult
```

用途：执行生成并评估转换/校验质量。开关关闭时直接返回当前结果；开启时最多执行
`max_repair_attempts` 轮 repair，并在每轮重新评估，error 清空后提前停止。达到上限后的阻断或保存
行为由接口路由策略决定。

返回：

```text
result       最后一次生成结果
retryCount   实际 repair 次数，0 到配置上限
errors       最后一次校验错误
initialErrors 首次校验错误
repairAttempted 是否执行过修复
```

## 9. Artifact 和响应方法

### 9.1 ArtifactStore.save

位置：

```text
cloud/services/artifact_store.py
```

签名：

```python
async save(artifact: WidgetArtifact) -> ArtifactSaveResult
```

用途：把完整 artifact 写成具名 Markdown 代码块、上传并返回 URL 和服务端追踪摘要。

当前实现：

```text
计算完整 artifact 的服务端追踪摘要
按 cardspec/genui/schema/taskspec/effectivecapabilities/removedcapabilities/generationplan/meta 顺序写入正式块
在正式块和可选 designcompactdsl 后追加 request，以及实际发生的 repair-1/2/3 等回放块
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
WIDGET_SERVICE_ENABLE_DEFAULT_PROTOCOL_PROFILE_FALLBACK
WIDGET_SERVICE_DEFAULT_DEVICE_ROM_VERSION
WIDGET_SERVICE_DEFAULT_PRD_VERSION
WIDGET_SERVICE_MOCK_IDS_RESPONSE_PATH
WIDGET_SERVICE_IDS_QUERY_URL
WIDGET_SERVICE_SYSTEM_PROMPT_FILE
WIDGET_SERVICE_EDIT_SYSTEM_PROMPT_FILE
WIDGET_SERVICE_REPAIR_SYSTEM_PROMPT_FILE
WIDGET_SERVICE_A2UI_FORM_MODEL_BACKEND
WIDGET_SERVICE_DESIGN_COMPACT_MODEL_BACKEND
WIDGET_SERVICE_OPENAI_MASTER_CLIENT
WIDGET_SERVICE_OPENAI_FALLBACK_CLIENT
WIDGET_SERVICE_ENABLE_OPENAI_FALLBACK
WIDGET_SERVICE_DEEPSEEK_PLATFORM_ACCESS_KEY
WIDGET_SERVICE_DEEPSEEK_PLATFORM_SECRET_KEY_STS_CONFIG_KEY
WIDGET_SERVICE_DEEPSEEK_PLATFORM_WS_URL
WIDGET_SERVICE_DEEPSEEK_PLATFORM_MODEL_NAME
WIDGET_SERVICE_DEEPSEEK_PLATFORM_API_KEY
WIDGET_SERVICE_DEEPSEEK_PLATFORM_SENDER
WIDGET_SERVICE_DEEPSEEK_PLATFORM_RECEIVER
WIDGET_SERVICE_DEEPSEEK_PLATFORM_MESSAGE_NAME
WIDGET_SERVICE_DEEPSEEK_PLATFORM_DEFAULT_COUNTRY_CODE
WIDGET_SERVICE_DEEPSEEK_PLATFORM_DEFAULT_APP_NAME
WIDGET_SERVICE_DEEPSEEK_API_KEY
WIDGET_SERVICE_DEEPSEEK_MODEL
WIDGET_SERVICE_DEEPSEEK_WS_URL
WIDGET_SERVICE_DEEPSEEK_USER
WIDGET_SERVICE_DEEPSEEK_REQUEST_ID
WIDGET_SERVICE_DEEPSEEK_TEMPERATURE
WIDGET_SERVICE_DEEPSEEK_TOP_P
WIDGET_SERVICE_DEEPSEEK_TOP_K
WIDGET_SERVICE_DEEPSEEK_MAX_TOKENS
WIDGET_SERVICE_DEEPSEEK_ENABLE_THINKING
WIDGET_SERVICE_DEEPSEEK_INCLUDE_USAGE
WIDGET_SERVICE_DEEPSEEK_DEBUG_USAGE
WIDGET_SERVICE_DEEPSEEK_RECV_TIMEOUT
WIDGET_SERVICE_MODEL_APPID
WIDGET_SERVICE_MODEL_URL
WIDGET_SERVICE_MODEL_PATH
WIDGET_SERVICE_MODEL_NAME
WIDGET_SERVICE_MODEL_BID
WIDGET_SERVICE_MODEL_FLOW_ID
WIDGET_SERVICE_MODEL_TEMPERATURE
WIDGET_SERVICE_MODEL_TOP_K
WIDGET_SERVICE_MODEL_PROMPT_LOG_PREVIEW_CHARS
WIDGET_SERVICE_ENABLE_ARTIFACT_VALIDATION
WIDGET_SERVICE_ENABLE_MODEL_FAILURE_RETRY
WIDGET_SERVICE_MODEL_FAILURE_MAX_RETRY_ATTEMPTS
WIDGET_SERVICE_FALLBACK_MODEL_FAILURE_MAX_RETRY_ATTEMPTS
WIDGET_SERVICE_MODEL_FAILURE_RETRY_INITIAL_DELAY_SECONDS
WIDGET_SERVICE_MODEL_FAILURE_RETRY_MAX_DELAY_SECONDS
WIDGET_SERVICE_MODEL_FAILURE_RETRY_BACKOFF_MULTIPLIER
WIDGET_SERVICE_MODEL_FAILURE_RETRY_JITTER_RATIO
WIDGET_SERVICE_ENABLE_VALIDATION_FAILURE_RETRY
WIDGET_SERVICE_VALIDATION_FAILURE_MAX_REPAIR_ATTEMPTS
WIDGET_SERVICE_MODEL_MAX_CONCURRENCY
WIDGET_SERVICE_MODEL_QUEUE_TIMEOUT_SECONDS
WIDGET_SERVICE_MODEL_REQUEST_TIMEOUT_SECONDS
WIDGET_SERVICE_ENABLE_WIDGET_EDIT
WIDGET_SERVICE_ARTIFACT_BASE_URL
WIDGET_SERVICE_ENABLE_ARTIFACT_DOWNLOAD_MOCK
WIDGET_SERVICE_SOURCE_ARTIFACT_MAX_BYTES
WIDGET_SERVICE_SOURCE_ARTIFACT_READ_TIMEOUT_SECONDS
WIDGET_SERVICE_SOURCE_GENUI_MAX_CHARS
WIDGET_SERVICE_ANYIO_THREAD_POOL_TOKENS
```

`WIDGET_SERVICE_ANYIO_THREAD_POOL_TOKENS` 默认值为 `80`，在应用启动时写入 AnyIO
默认线程限制器，仅控制第一、第二接口和短时同步 IO/校验任务的并发容量。第三至第五接口直接等待
异步生成 Service，不让完整模型链路占用该线程池。

`WIDGET_SERVICE_ENABLE_MODEL_FAILURE_RETRY` 默认值为 `false`。关闭时每个模型阶段只调用 master 一次，
不重试且不切换 fallback。开启后，首次生成或 repair 模型调用边界内发生任意异常或空 DSL 时，master
使用同一提示词进行异步指数退避重试。`WIDGET_SERVICE_ENABLE_OPENAI_FALLBACK=true` 时，master 耗尽后
立即切换 fallback；关闭该开关时直接返回 master 的最终异常。master 额外重试次数由
`WIDGET_SERVICE_MODEL_FAILURE_MAX_RETRY_ATTEMPTS` 控制；fallback 使用独立的
`WIDGET_SERVICE_FALLBACK_MODEL_FAILURE_MAX_RETRY_ATTEMPTS`。两者默认 `1`，合法范围 `1～10`。退避等待
不占用工作线程或模型并发令牌，等待结束后重新参与模型并发排队。conversion/Validator error 不直接切换
fallback，而是由 `WIDGET_SERVICE_ENABLE_VALIDATION_FAILURE_RETRY` 触发定向 repair；每轮 repair 重新从
master 开始。

若 master/fallback 的额外重试次数是 `M/F`、repair 上限是 `R`，开启重试后单个模型阶段最多调用
`(1 + M) + (1 + F)` 次，整个请求最多调用 `(1 + R) × [(1 + M) + (1 + F)]` 次。关闭重试时每个模型
阶段只调用 master `1` 次；仅关闭 fallback 时分别降为 `1 + M` 和 `(1 + R) × (1 + M)` 次。

`WIDGET_SERVICE_MODEL_PROMPT_LOG_PREVIEW_CHARS` 默认值为 `30`。首次生成日志只记录 system prompt 的前
N 个字符、system prompt 总字符数和消息数量，不记录完整 system/user 消息；配置为 `0` 时不记录任何
提示词正文。repair 请求继续保持完整载荷不落日志。

`WIDGET_SERVICE_MODEL_MAX_CONCURRENCY` 默认 `20`，由应用生命周期唯一模型 Runtime 的共享 Semaphore
执行。MEP、DeepSeek Platform、llmclient、三个生成接口、create/edit、模型失败重试和 repair 的每一次
真实模型调用都要单独获取令牌；mock 不占令牌。排队和执行分别由
`WIDGET_SERVICE_MODEL_QUEUE_TIMEOUT_SECONDS` 与 `WIDGET_SERVICE_MODEL_REQUEST_TIMEOUT_SECONDS` 控制，
默认均为 120 秒。llmclient 超时后令牌保留到同步后台调用真正结束，避免物理并发超限。

`WIDGET_SERVICE_OPENAI_MASTER_CLIENT` 和 `WIDGET_SERVICE_OPENAI_FALLBACK_CLIENT` 只允许配置
`deepseek_platform` 或 `llmclient`，并且不能相同。DeepSeek Platform 的 SK 只从
`WIDGET_SERVICE_DEEPSEEK_PLATFORM_SECRET_KEY_STS_CONFIG_KEY` 指定的 STS key 读取，默认 key 为
`genui.deepseek.platform.secret.key`；普通配置和日志中不保存 SK。AK、WebSocket URL、模型名、业务 API
Key、sender、receiver、messageName、默认国家和默认 App 使用 `WIDGET_SERVICE_DEEPSEEK_PLATFORM_*`
配置。会话、交互、设备、国家、App 版本和 App 名称由每次 WebSocket 请求构造，同一请求的首次生成、
重试和 repair 复用，后续请求不会串用。

`WIDGET_SERVICE_DEEPSEEK_*` 仍只用于 fallback llmclient：配置 WebSocket 地址、鉴权和请求身份、模型采样参数、最大
Token、思考/usage 开关及连接接收超时。默认值与配置抽离前 llmclient 的固定参数一致；生产环境应通过
部署环境变量覆盖鉴权、地址和请求身份。

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

`EventCapabilityOverview`：第一接口的精简事件定义，包含事件 ID、用途描述、可直接复制的完整动作模板，以及
允许替换的动态参数路径和填写规则；不暴露依赖和完整参数 schema。顶层 `description` 只描述事件用途和
用户可感知结果，固定值由 `actionTemplate` 承载，数据路径、索引替换和枚举映射由 `dynamicArguments` 承载；
动态值来自数据能力输出时，参数说明同时写明来源数据能力 ID 和输出字段路径。

`AssetCapabilityOverview`：第一接口的精简素材定义，只包含素材 ID 和描述；素材路径和版本信息由微服务
内部保留并在生成阶段按 ID 还原。

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

1. 直接更新当前版本目录中的 `event_capabilities.json`，保持事件 ID 稳定；顶层 `description` 只写用途，不混入 URI、字段路径、索引替换或模型操作指令；固定动作写入 `actionTemplate`，允许替换的参数规则写入 `dynamicArguments`，并与内部 `parametersSchema` 保持一致。动态值来自数据能力输出时，参数说明必须包含来源数据能力 ID 和输出字段路径。只有事件确实需要按安装包过滤时才在对应目标项声明仅含包名的 `dependencies.requiredPackages`，缺省按空依赖处理。
2. 第一接口确认可用后，在第三接口里通过 `candidateEventCandidates` 传入。

新增素材：

1. 直接更新当前版本目录中的 `asset_capabilities.json`，补齐唯一的 `id`、`src`、`description` 和 `sceneTags`。
2. 第一接口确认可用后，在第三接口里通过 `candidateAssetIds` 传入。

新增能力版本：

```text
复制 data/capabilities/app-11.7.5.205_rom-6.0 为新文件夹
修改 JSON 文件
在 data/capabilities/registry_ranges.json 中新增不重叠的 App/ROM 区间并指向新文件夹
```

## 13. 验证命令

```bash
cd D:\ai-workspace\code-github\CreateMyCard-team-lff
$env:PYTHONPATH='widget_service\src'
python -m pytest widget_service\tests
python -m ruff check widget_service
python -m compileall -q widget_service\cloud widget_service\tests
```
