# Widget Service

Python 3.12 FastAPI microservice for AI widget card generation.

The service follows `docs/AGENTS.md`:

- Main Agent selects candidate capabilities.
- This microservice resolves device capability, builds final `CardSpec`, constructs `TaskSpec`, calls the A2UI model client, validates artifact, and returns structured status.
- Data capabilities, event capabilities, and assets are versioned by `device.ohosApiVersion+device.romVersion`
  folder name under `cloud/data/capabilities/`.
- OBS upload is intentionally left as a TODO hook in `ArtifactStore`.

## Run

```bash
cd widget_service
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
# or:
pip install -r requirements.txt
set PYTHONPATH=cloud
uvicorn main:app --reload
```

## API

```text
GET  /health
WS   /api/v1/ws/tools/widgetCardService
```

Latest tool-style entry:

```json
{
  "requestId": "overview-1",
  "arguments": {
    "uid": "test-user-001",
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

Supported operations:

- `getWidgetCapabilityOverview`
- `getDataCapabilitySchemas`
- `generateWidgetCard`

See `docs/method_usage.md` for detailed method and API usage.
