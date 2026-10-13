"""第二层空输出的有界退避与既有重试策略隔离。"""

import asyncio
import json

import pytest

from config.config import Settings
from custom.model_transport import ModelTransportError
from models.generation import ModelRequestContext
from services.generation_trace_recorder import GenerationTraceRecorder
from services.template_generation.model_client import TemplateModelClient


class SequenceRuntime:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0

    async def generate_once(self, *_args, **_kwargs):
        self.calls += 1
        response = next(self.responses)
        if isinstance(response, BaseException):
            raise response
        return response


def make_client(monkeypatch, responses, *, global_retry=False):
    settings = Settings(
        _env_file=None,
        design_compact_model_backend="openai",
        openai_master_client="llmclient",
        enable_model_failure_retry=global_retry,
        model_failure_max_retry_attempts=5,
        enable_openai_fallback=False,
        model_failure_retry_initial_delay_seconds=1.0,
    )
    monkeypatch.setattr("services.template_generation.model_client.get_settings", lambda: settings)
    runtime = SequenceRuntime(responses)
    context = ModelRequestContext("session", "interaction", "device", "CN", "test", "test")
    client = TemplateModelClient(runtime, context)
    delays = []

    async def record_sleep(seconds):
        delays.append(seconds)

    client._sleep = record_sleep
    client._random_uniform = lambda lower, upper: (lower + upper) / 2
    client._client._sleep = record_sleep
    client._client._random_uniform = lambda lower, upper: (lower + upper) / 2
    return client, runtime, delays


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["advanced-mixed-body", "advanced-mixed-body-repair"])
@pytest.mark.parametrize(
    "empty", ["", "  \n", ModelTransportError("empty", code="MODEL_EMPTY_OUTPUT")]
)
async def test_second_layer_recovers_once_with_backoff(monkeypatch, tmp_path, phase, empty):
    client, runtime, delays = make_client(monkeypatch, [empty, "Template();"])
    recorder = GenerationTraceRecorder()
    recorder.bind_request("retry-abcdefgh-00001-000", enabled=True, trace_root=tmp_path)
    token = recorder.activate()
    try:
        assert await client.generate([], phase=phase) == "Template();"
        recorder.finalize(status="success")
    finally:
        recorder.deactivate(token)
    assert runtime.calls == 2
    assert delays == [1.0]
    records = []
    for line in next(tmp_path.rglob("trace.jsonl")).read_text().splitlines():
        records.append(json.loads(line))
    summary = records[-1].get("details")
    assert summary is not None
    assert summary.get("attemptCounts") == {"modelLogicalCalls": 2, "modelPhysicalAttempts": 2}
    assert summary.get("retryCounts") == {"templateEmptyOutputRetries": 1}


@pytest.mark.asyncio
@pytest.mark.parametrize("global_retry", [False, True])
async def test_second_empty_stops_even_with_larger_global_budget(monkeypatch, global_retry):
    client, runtime, delays = make_client(
        monkeypatch, ["", "", "unexpected"], global_retry=global_retry
    )
    with pytest.raises(ModelTransportError) as error:
        await client.generate([])
    assert error.value.code == "MODEL_EMPTY_OUTPUT"
    assert runtime.calls == 2
    assert delays == [1.0]


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["business-decision", "initial", "repair"])
async def test_other_phases_do_not_gain_empty_retry(monkeypatch, phase):
    client, runtime, delays = make_client(monkeypatch, [""])
    with pytest.raises(ModelTransportError) as error:
        await client.generate([], phase=phase)
    assert error.value.code == "MODEL_EMPTY_OUTPUT"
    assert runtime.calls == 1
    assert not delays


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code", ["MODEL_OUTPUT_TRUNCATED", "MODEL_TIMEOUT", "MODEL_TRANSPORT_ERROR"]
)
async def test_other_failures_keep_original_budget(monkeypatch, code):
    client, runtime, delays = make_client(monkeypatch, [ModelTransportError("failed", code=code)])
    with pytest.raises(ModelTransportError) as error:
        await client.generate([])
    assert error.value.code == code
    assert runtime.calls == 1
    assert not delays


@pytest.mark.asyncio
async def test_first_layer_keeps_existing_global_retry_policy(monkeypatch):
    client, runtime, delays = make_client(monkeypatch, [""] * 6, global_retry=True)
    with pytest.raises(ModelTransportError) as error:
        await client.generate_json([], phase="business-decision")
    assert error.value.code == "MODEL_EMPTY_OUTPUT"
    assert runtime.calls == 6
    assert len(delays) == 5


@pytest.mark.asyncio
async def test_nonempty_invalid_json_does_not_trigger_transport_retry(monkeypatch):
    client, runtime, delays = make_client(monkeypatch, ["not JSON"])
    with pytest.raises(ValueError, match="JSON object"):
        await client.generate_json([], phase="advanced-mixed-body")
    assert runtime.calls == 1
    assert not delays


@pytest.mark.asyncio
async def test_first_success_does_not_wait_or_repeat(monkeypatch):
    client, runtime, delays = make_client(monkeypatch, ["Template();"])
    assert await client.generate([]) == "Template();"
    assert runtime.calls == 1
    assert not delays


@pytest.mark.asyncio
async def test_cancellation_does_not_retry(monkeypatch):
    client, runtime, delays = make_client(monkeypatch, [asyncio.CancelledError()])
    with pytest.raises(asyncio.CancelledError):
        await client.generate([])
    assert runtime.calls == 1
    assert not delays
