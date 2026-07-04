# Widget Service

Python 3.12 FastAPI microservice for AI widget card generation.

The service follows `docs/AGENTS.md`:

- Main Agent selects candidate capabilities.
- This microservice resolves device capability, builds final `CardSpec`, constructs `TaskSpec`, calls the A2UI model client, validates artifact, and returns structured status.
- Data capabilities, event capabilities, and assets are versioned by `appVersion+romVersion`
  folder name under `src/widget_service/data/capabilities/`.
- OBS upload is intentionally left as a TODO hook in `ArtifactStore`.

## Run

```bash
cd widget_service
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
# or:
pip install -r requirements.txt
uvicorn widget_service.main:app --reload
```

## API

```text
GET  /health
WS   /ws
POST /api/v1/widget/capability-overview
POST /api/v1/widget/data-capability-schemas
WS   /api/v1/ws/widget/generate
POST /api/v1/tools/{tool_name}
```

`/api/v1/tools/{tool_name}` accepts:

- `getWidgetCapabilityOverview`
- `getDataCapabilitySchemas`
- `generateWidgetCard` uses WebSocket at `/api/v1/ws/widget/generate`

Local WebSocket test:

```bash
python tools/ws_generate_client.py
```

See `docs/method_usage.md` for detailed method and API usage.
