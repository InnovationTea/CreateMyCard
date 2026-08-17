# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json

import pytest

import repair_compact_dsl as repair_module
from services.card_validation.diagnostics import Diagnostic, Reporter

_VALID_COMPACT_DSL = "\n".join(
    [
        '["root","Column",{"width":160,"height":160,"padding":8,'
        '"borderRadius":18,"clip":true},["title"]]',
        '["title","Text",{"content":"Repair Demo","fontSize":20,'
        '"fontColor":"#E5000000"}]',
        '["/ui/state","ready"]',
    ]
)


@pytest.mark.asyncio
async def test_repair_compact_dsl_repairs_validation_failure(monkeypatch):
    validation_calls = 0
    repair_prompts: list[list[dict[str, str]]] = []
    client_closed = False

    def validate_once(**_kwargs):
        nonlocal validation_calls
        validation_calls += 1
        reporter = Reporter()
        if validation_calls == 1:
            reporter.diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TEST_VALIDATION_FAILED",
                    stage="semantic",
                    file_kind="genui",
                    message="test validation failure",
                )
            )
        return reporter

    class FakeModelClient:
        def __init__(self, **_kwargs):
            pass

        async def generate_repair(self, prompt, _profile):
            repair_prompts.append(prompt)
            return _VALID_COMPACT_DSL

        async def aclose(self):
            nonlocal client_closed
            client_closed = True

    monkeypatch.setattr(repair_module, "validate_card", validate_once)
    monkeypatch.setattr(repair_module, "A2UIModelClient", FakeModelClient)

    result = await repair_module.repair_compact_dsl(_VALID_COMPACT_DSL)

    assert result.repair_count == 1
    assert validation_calls == 2
    assert client_closed is True
    assert len(result.dsl.splitlines()) == 3
    repair_payload = json.loads(repair_prompts[0][1]["content"])
    assert repair_payload["invalidSourceDsl"] == _VALID_COMPACT_DSL
    assert repair_payload["qualityErrors"][0]["stage"] == "validation"
