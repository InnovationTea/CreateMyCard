# Widget Service

Python 3.12 FastAPI microservice for AI widget card generation.

The service follows `docs/AGENTS.md`:

- Main Agent selects candidate capabilities.
- The first interface applies IDS installed-app matching only to dependency package names listed in `WIDGET_SERVICE_IDS_INSTALLATION_FILTER_PACKAGE_NAMES`; the default list contains only `com.huawei.hmos.health.core`. The generation interface consumes the available list, builds final `CardSpec`, constructs `TaskSpec`, calls the A2UI model client, validates artifact, and returns structured status.
- Data capabilities, event capabilities, and assets are versioned by `prdVer+romVersion`
  folder name under `cloud/data/capabilities/`.
- `TaskSpec.dataModelSchema` is projected directly from each capability `outputSchema`: the service reads `type`, `description`, and `sampleValue` from the selected leaf and writes it at `writeResultTo + candidateOutputFields` path. There is no separate data-model mapping file or runtime field-renaming layer.
- `romVersion` is the only accepted ROM field name. A full value such as `CLS-AL30 6.0.0.328` is normalized to the major/minor version `6.0`.
- All three interfaces fall back to `app-11.7.5.205_rom-6.0` when the requested registry is missing and `WIDGET_SERVICE_ENABLE_DEFAULT_CAPABILITY_REGISTRY_FALLBACK=true`. The generation interface records the actual fallback version in artifact metadata.
- `WIDGET_SERVICE_ENABLE_IDS_MOCK=true` by default. In this mode the service reads only `WIDGET_SERVICE_MOCK_IDS_RESPONSE_PATH`, whose default path is the service-internal `cloud/data/mock/ids_res.json`; a missing or invalid mock produces an empty IDS result and never falls back to remote IDS. When set to `false`, the service ignores the mock and queries only the real remote IDS; remote failure produces an empty result and never falls back to mock.
- `WIDGET_SERVICE_ENABLE_VALIDATION_FAILURE_RETRY=false` by default. Validation failures are logged without blocking artifact persistence or invoking the model again; setting it to `true` enables at most one regeneration attempt.
- Create and edit prompts are loaded from `WIDGET_SERVICE_SYSTEM_PROMPT_FILE` and `WIDGET_SERVICE_EDIT_SYSTEM_PROMPT_FILE`. Their defaults are `docs/system_prompt.txt` and `docs/edit_system_prompt.txt` relative to the repository root.
- `WIDGET_SERVICE_ENABLE_ARTIFACT_DOWNLOAD_MOCK=true` by default. Multi-round source artifacts are read only from `cloud/workspace/mock_obs`; missing mock files do not fall back to the network. Set it to `false` to download from the validated HTTPS artifact URL.
- Structured values embedded in log messages are serialized as standard JSON with double-quoted keys and strings. Request `uid` remains part of the API contract but must never be logged in raw, masked, or hashed form; IDS request logs omit `callingUid` as well.
- The server logs process-wide WebSocket `active_connections`, cumulative `total_connections`, and `running_tasks` every 10 seconds.
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
py -3.12 cloud\main.py
```

本地验证最新校验 API 和“校验失败不阻断保存”时，建议显式开启校验并关闭重试：

```powershell
$env:WIDGET_SERVICE_ENABLE_ARTIFACT_VALIDATION="true"
$env:WIDGET_SERVICE_ENABLE_VALIDATION_FAILURE_RETRY="false"
py -3.12 cloud\main.py
```

服务启动后，在另一个终端执行真实 WebSocket 联调脚本：

```powershell
cd widget_service
py -3.12 tests\test_running_ws_server.py
```

该脚本会调用真实 `generateWidgetCard`，读取服务保存的 artifact，通过
`cloud/services/card_validation/` Python API 再校验一次并打印诊断。当前 mock 输出包含
确定的校验问题，因此脚本还会断言接口依然成功返回 artifact，用于证明校验失败不会阻塞主流程。

本地多轮编辑联调需要先开启开关：

```powershell
$env:WIDGET_SERVICE_ENABLE_WIDGET_EDIT="true"
py -3.12 cloud\main.py
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

真实 WebSocket 联调时，业务日志由单独运行的 `cloud/main.py` 进程输出，应在服务终端查看；
本地文件日志位于 `cloud/logs/agent_YYYYMMDD.log`。客户端测试终端只显示请求响应和脚本打印的校验报告。

## API

```text
GET  /health
WS   /api/v1/ws/tools/getWidgetCapabilityOverview
WS   /api/v1/ws/tools/getDataCapabilitySchemas
WS   /api/v1/ws/tools/generateWidgetCard
WS   /api/v1/ws/tools/generateWidgetCardCompactDsl
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

See `docs/method_usage.md` for detailed method and API usage.
