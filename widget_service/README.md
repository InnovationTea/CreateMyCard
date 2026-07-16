# Widget Service

Python 3.12 FastAPI microservice for AI widget card generation.

The service follows `docs/AGENTS.md`:

- Main Agent selects candidate capabilities.
- The first interface applies IDS installed-app matching only to dependency package names listed in `WIDGET_SERVICE_IDS_INSTALLATION_FILTER_PACKAGE_NAMES`; the default list contains only `com.huawei.hmos.health.core`. The generation interface consumes the available list, builds final `CardSpec`, constructs `TaskSpec`, calls the A2UI model client, validates artifact, and returns structured status.
- Data capabilities, event capabilities, and assets are versioned by `prdVer+romVersion`
  folder name under `cloud/data/capabilities/`.
- `TaskSpec.dataModelSchema` is projected directly from each capability `outputSchema`: the service reads `type`, `description`, and `sampleValue` from the selected leaf and writes it at `writeResultTo + candidateOutputFields` path. There is no separate data-model mapping file or runtime field-renaming layer.
- `romVersion` currently uses the numeric compatibility level `36`.
- The first two interfaces fall back to `app-11.7.5.205_rom-36` when the requested registry is missing and `WIDGET_SERVICE_ENABLE_DEFAULT_CAPABILITY_REGISTRY_FALLBACK=true`; generation interfaces never use this fallback.
- `WIDGET_SERVICE_ENABLE_IDS_MOCK=true` by default. In this mode the service reads only `WIDGET_SERVICE_MOCK_IDS_RESPONSE_PATH`, whose default path is the service-internal `cloud/data/mock/ids_res.json`; a missing or invalid mock produces an empty IDS result and never falls back to remote IDS. When set to `false`, the service ignores the mock and queries only the real remote IDS; remote failure produces an empty result and never falls back to mock.
- Structured values embedded in log messages are serialized as standard JSON with double-quoted keys and strings. Request `uid` remains part of the API contract but must never be logged in raw, masked, or hashed form; IDS request logs omit `callingUid` as well.
- Package filtering emits exactly one summary result per capability-overview request; per-capability dependency-check logs are not emitted.
- OBS upload is intentionally left as a TODO hook in `ArtifactStore`.

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
      "romVersion": "36"
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
