# Widget Service

Python 3.12 FastAPI microservice for AI widget card generation.

The service follows `docs/AGENTS.md`:

- Main Agent selects candidate capabilities.
- The first interface applies IDS installed-app matching only to dependency package names listed in `WIDGET_SERVICE_IDS_INSTALLATION_FILTER_PACKAGE_NAMES`; the default list contains weather, health, and calendar package names. The generation interface consumes the available list, builds final `CardSpec`, constructs `TaskSpec`, calls the A2UI model client, validates artifact, and returns structured status.
- Data capabilities, event capabilities, and assets are selected by App/ROM left-closed,
  right-open ranges in `cloud/data/capabilities/registry_ranges.json`.
- `TaskSpec.dataModelSchema` is projected directly from each capability `outputSchema`: the service reads `type`, `description`, and `sampleValue` from the selected leaf and writes it at `writeResultTo + candidateOutputFields` path. There is no separate data-model mapping file or runtime field-renaming layer.
- `romVersion` is the only accepted ROM field name. A full value such as `CLS-AL30 6.0.0.328` is normalized to the major/minor version `6.0`.
- All five interfaces use the ranges in `cloud/data/capabilities/registry_ranges.json`: App
  `[11.7.5.205, 11.7.7.330)` with ROM `[7.0, 7.2)` maps to
  `app-11.7.5.205_rom-6.0`, while App `[11.7.7.330, 12.0.0.0)` with ROM
  `[7.0, 8.0)` maps to `app-11.7.7.300_rom-7.0`. An unmatched version falls back
  to the configured default when
  `WIDGET_SERVICE_ENABLE_DEFAULT_CAPABILITY_REGISTRY_FALLBACK=true`.
- `generateWidgetCard` selects `mep` or the composite `openai` route through
  `WIDGET_SERVICE_A2UI_FORM_MODEL_BACKEND`.
  `generateWidgetCardCompactDsl` selects its backend through `WIDGET_SERVICE_DESIGN_COMPACT_MODEL_BACKEND`, loads
  the Design profile from `data/protocol_profiles/registry_ranges.json`, whose App/ROM intervals mirror the capability
  registry intervals, and converts Design Compact DSL with that profile's `protocol.json` before validation and
  storage. Create requests first try the controlled Template route;
  a Template mismatch can fall back to the ordinary Design Compact model route. The generation routes share one
  policy-driven pipeline and the same model-failure, quality-repair, and validation switches. Tool callers cannot
  select or override either backend.
- `generateWidgetCardTerseDslNested2` is currently a strict Template-only create route. It uses the same Design
  Compact public Processor after the Template module has compiled its internal TerseDSL-Nested-2/CardTpl result to
  A2UI and adapted it to Design Compact source DSL. Template mismatch and edit requests fail without falling back to
  the ordinary model route. See `cloud/services/template_generation/docs/README.md` for the current architecture and
  module documentation.
- `cloud/services/template_generation/config/template_controls.json` owns the Template Provider and individual
  Template denylists. Filtering happens before the first-layer prompt, and the same filtered set constrains
  second-layer Provider rules, layout candidates, and deterministic output validation.
- Temporary route `generateWidgetCardCompactDslWithDirective` directly reuses the fourth route's generation service
  and schema, but always emits widget directive command frames even when the global directive switch is disabled.
  Its forced behavior is isolated in the router so the route can be removed without changing the generation pipeline.
- `WIDGET_SERVICE_ENABLE_IDS_MOCK=true` by default. In this mode the service reads only `WIDGET_SERVICE_MOCK_IDS_RESPONSE_PATH`, whose default path is the service-internal `cloud/data/mock/ids_res.json`; a missing or invalid mock produces an empty IDS result and never falls back to remote IDS. When set to `false`, the service ignores the mock and queries only the real remote IDS; remote failure produces an empty result and never falls back to mock.
- `WIDGET_SERVICE_ENABLE_VALIDATION_FAILURE_RETRY=false` by default. It controls targeted repair for both source
  DSL conversion errors and Validator errors. `WIDGET_SERVICE_VALIDATION_FAILURE_MAX_REPAIR_ATTEMPTS=1` limits
  repair to 1-10 attempts, and processing stops early when all errors disappear. Warnings never trigger repair.
  Conversion remains mandatory when Validator is disabled. Unconverted Design/Terse output is never saved;
  remaining Validator errors are non-blocking only for the standard third interface.
- `WIDGET_SERVICE_ENABLE_MODEL_FAILURE_RETRY=false` by default. Model transport errors,
  explicit model errors, and empty DSL output return `failed/A2UI_GENERATION_FAILED`;
  when disabled, the selected route calls only its master once and does not use fallback. When enabled, every initial
  or repair call retries its master with asynchronous exponential backoff and jitter, then switches to the configured
  fallback after the master budget is exhausted. Set `WIDGET_SERVICE_ENABLE_OPENAI_FALLBACK=false` to keep master
  retries but disable fallback calls. Configure the master and fallback additional retry counts with
  `WIDGET_SERVICE_MODEL_FAILURE_MAX_RETRY_ATTEMPTS` and
  `WIDGET_SERVICE_FALLBACK_MODEL_FAILURE_MAX_RETRY_ATTEMPTS` (1-10), and tune their shared delay with the
  `WIDGET_SERVICE_MODEL_FAILURE_RETRY_INITIAL_DELAY_SECONDS`, `WIDGET_SERVICE_MODEL_FAILURE_RETRY_MAX_DELAY_SECONDS`,
  `WIDGET_SERVICE_MODEL_FAILURE_RETRY_BACKOFF_MULTIPLIER`, and
  `WIDGET_SERVICE_MODEL_FAILURE_RETRY_JITTER_RATIO` settings. Backoff does not hold a worker thread or model permit.
  Conversion and Validator errors still trigger immediate targeted repair through the separate validation retry switch.
  Final model failures never enter validation or artifact persistence.
- With model mock disabled, all three generation routes use `A2UIModelClient.generate()` and the internal
  `UnifiedModelClient.generate()` entry. The `openai` route uses DeepSeek Platform as master and the existing
  `cloud/custom/llmclient.py` as fallback by default. Configure them with `WIDGET_SERVICE_OPENAI_MASTER_CLIENT` and
  `WIDGET_SERVICE_OPENAI_FALLBACK_CLIENT`, and control fallback with `WIDGET_SERVICE_ENABLE_OPENAI_FALLBACK`; tool
  callers cannot select a backend or physical client directly.
- DeepSeek Platform reads its SK only from the STS key configured by
  `WIDGET_SERVICE_DEEPSEEK_PLATFORM_SECRET_KEY_STS_CONFIG_KEY`, whose default is
  `genui.deepseek.platform.secret.key`. Its remaining static request fields use the
  `WIDGET_SERVICE_DEEPSEEK_PLATFORM_*` settings; session, interaction, device, country, App version, and App name
  prefer the current WebSocket request context.
- The llmclient WebSocket request is configured by the `WIDGET_SERVICE_DEEPSEEK_*` settings in `.env.example`,
  covering credentials, endpoint, model/user/request identifiers, sampling, maximum tokens, thinking/usage flags,
  and receive timeout. These fields have defaults matching the client behavior before configuration extraction.
- All real model calls share one application-lifetime runtime and one process-level concurrency limit. MEP uses a
  shared async `httpx.AsyncClient`, DeepSeek Platform uses async WebSocket, and the unchanged synchronous llmclient
  runs in a dedicated executor. Configure the
  shared limit with `WIDGET_SERVICE_MODEL_MAX_CONCURRENCY`, queue timeout with
  `WIDGET_SERVICE_MODEL_QUEUE_TIMEOUT_SECONDS`, and execution timeout with
  `WIDGET_SERVICE_MODEL_REQUEST_TIMEOUT_SECONDS`. Queue waits are coroutine waits and do not occupy worker threads.
  A timed-out llmclient call retains its permit until the underlying synchronous call actually finishes.
- If MEP ends a Design request with `6241/Early stop due to aborted` after emitting a non-empty candidate, the
  candidate continues through the strict Design converter and validation flow. Empty output and non-Design requests
  remain model failures.
- Standard create, edit, and repair prompts are loaded from `WIDGET_SERVICE_SYSTEM_PROMPT_FILE`,
  `WIDGET_SERVICE_EDIT_SYSTEM_PROMPT_FILE`, and `WIDGET_SERVICE_REPAIR_SYSTEM_PROMPT_FILE`. The Design and Terse
  routes keep their selected profile's `PROMPT.md` as the system message. Their edit user message contains the
  current query, TaskSpec, and the previous raw model output read from the artifact `designcompactdsl` block.
  Repair appends the same repair constraints when enabled. Prompt logs never write the full messages;
  `WIDGET_SERVICE_MODEL_PROMPT_LOG_PREVIEW_CHARS=30` limits the logged system-prompt prefix, and `0` disables prompt
  text while retaining message and character counts.
- `WIDGET_SERVICE_ENABLE_ARTIFACT_DOWNLOAD_MOCK=true` by default. Multi-round source artifacts are read only from `cloud/workspace/mock_obs`; missing mock files do not fall back to the network. Set it to `false` to download from the validated HTTPS artifact URL.
- The WebSocket router logs each received request object as compact standard JSON before protocol normalization. Structured values embedded in other log messages use the same double-quoted JSON format. Sensitive `uid`/`userId`/`callingUid` and `odid` are recursively omitted; `sourceArtifactUrl` is retained in the raw request log.
- The server logs process-wide WebSocket `active_connections`, cumulative `total_connections`, and `running_tasks` every 10 seconds.
- Starlette synchronous handlers use the AnyIO worker pool with 80 concurrent tokens by default.
  Override it with `WIDGET_SERVICE_ANYIO_THREAD_POOL_TOKENS` when deployment capacity requires a different limit.
  The three generation WebSocket handlers directly await the async generation service; heartbeat send failure does
  not cancel generation, repair, or artifact persistence.
- Package filtering emits exactly one summary result per capability-overview request; per-capability dependency-check logs are not emitted.
- OBS upload is intentionally left as a TODO hook in `ArtifactStore`; remote source artifact reads reuse `utils/download_file_from_url.py`.

## Run

```bash
cd widget_service
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
# or:
pip install -r requirements.txt
py -3.12 cloud\start_websocket_server.py
```

本地验证最新校验 API 和“校验失败不阻断保存”时，建议显式开启校验并关闭重试：

```powershell
$env:WIDGET_SERVICE_ENABLE_ARTIFACT_VALIDATION="true"
$env:WIDGET_SERVICE_ENABLE_VALIDATION_FAILURE_RETRY="false"
py -3.12 cloud\start_websocket_server.py
```

服务启动后，在另一个终端执行真实 WebSocket 联调脚本：

```powershell
cd widget_service
py -3.12 tests\test_running_ws_server.py
```

该脚本会调用真实 `generateWidgetCard`，读取服务保存的 artifact，通过
`cloud/services/card_validation/` Python API 再校验一次并打印诊断。当前 mock 输出包含
确定的校验问题，因此脚本还会断言接口依然成功返回 artifact，用于证明校验失败不会阻塞主流程。

需要像单元测试一样逐项调试本地服务时，使用单功能真实 WS 测试：

```powershell
cd widget_service
# 运行全部单功能用例
py -3.12 -m pytest tests\test_running_ws_features.py -s -q
# 只测能力概述
py -3.12 -m pytest tests\test_running_ws_features.py::test_live_widget_capability_overview -s -q
# 只测一个数据能力 schema
py -3.12 -m pytest "tests\test_running_ws_features.py::test_live_each_data_capability_schema[ViewWeather]" -s -q
# 只测 A2UI Form 或 Compact DSL 生成
py -3.12 -m pytest tests\test_running_ws_features.py::test_live_generate_widget_card -s -q
py -3.12 -m pytest tests\test_running_ws_features.py::test_live_generate_widget_card_compact_dsl -s -q
```

该文件中的健康检查、四个 WS 接口、八个数据能力 schema、缺失能力和参数异常都是独立
pytest 节点。默认等待模型响应 180 秒，可通过 `WIDGET_SERVICE_TEST_RESPONSE_TIMEOUT`
调整；服务未启动时整组用例会明确跳过。

本地多轮编辑联调需要先开启开关：

```powershell
$env:WIDGET_SERVICE_ENABLE_WIDGET_EDIT="true"
py -3.12 cloud\start_websocket_server.py
```

服务启动后，在另一个终端执行真实 WebSocket 多轮测试：

```powershell
cd widget_service
py -3.12 tests\test_running_ws_multi_round.py
# 或显示每轮响应：
py -3.12 -m pytest tests\test_running_ws_multi_round.py -s -q
```

测试会依次执行首次生成、纯视觉继承编辑和显式清空数据三轮，并断言每轮返回新的 artifact URL。

Pytest 默认捕获 stdout/stderr，因此测试通过时通常看不到 `print` 和控制台日志。需要实时显示时使用：

```powershell
py -3.12 -m pytest tests\test_service_units.py -s -q
```

真实 WebSocket 联调时，业务日志由单独运行的 `cloud/start_websocket_server.py` 进程输出，应在服务终端查看；
本地文件日志位于 `cloud/logs/agent_YYYYMMDD.log`。客户端测试终端只显示请求响应和脚本打印的校验报告。

## API

```text
GET  /health
WS   /api/v1/ws/tools/getWidgetCapabilityOverview
WS   /api/v1/ws/tools/getDataCapabilitySchemas
WS   /api/v1/ws/tools/generateWidgetCard
WS   /api/v1/ws/tools/generateWidgetCardCompactDsl
WS   /api/v1/ws/tools/generateWidgetCardTerseDslNested2
```

Example request:

```json
{
  "requestId": "overview-1",
  "arguments": {
    "uid": "test-user-001",
    "device": {
      "deviceId": "5e64f3e9-0a80-d719-d689-3c36eca5eeb6",
      "deviceType": "ALN-AL00",
      "romVersion": "CLS-AL30 6.0.0.328"
    },
    "locale": "zh-CN"
  }
}
```

Schema files:

- `docs/schemas/getWidgetCapabilityOverview.schema.json`
- `docs/schemas/getDataCapabilitySchemas.schema.json`
- `docs/schemas/generateWidgetCard.schema.json`
- `docs/schemas/generateWidgetCardCompactDsl.schema.json`
- `docs/schemas/generateWidgetCardTerseDslNested2.schema.json`

See `docs/method_usage.md` for detailed method and API usage.
