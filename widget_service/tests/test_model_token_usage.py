# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from custom.a2ui_model_client import A2UIModelClient
from models.model_usage import ModelTokenUsage, sum_model_token_usage


class ModelTokenUsageTest(unittest.TestCase):
    def test_compact_client_returns_streamed_ndjson_without_a2ui_conversion(self) -> None:
        dsl = '["root","Column",{"width":"matchParent"},[]]'

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, _exc_type, _exc, _traceback):
                return False

            @staticmethod
            def raise_for_status() -> None:
                return None

            @staticmethod
            def iter_lines(decode_unicode=True):
                assert decode_unicode is True
                content_chunk = {
                    "choices": [{"delta": {"content": dsl}}],
                }
                yield f"data: {json.dumps(content_chunk)}"
                yield (
                    'data: {"choices":[],"usage":{"prompt_tokens":100,'
                    '"completion_tokens":20,"total_tokens":120}}'
                )
                yield "data: [DONE]"

        client = A2UIModelClient(use_mock=False)
        with (
            patch.object(client, "calc_sign", return_value="signature"),
            patch.object(
                client,
                "convert_dsl",
                side_effect=AssertionError("Compact output must not use A2UI conversion"),
            ),
            patch("custom.a2ui_model_client.requests.post", return_value=FakeResponse()),
        ):
            result = client._generate_compact_from_real_model(
                [{"role": "user", "content": "weather"}],
                "compact-dsl-v1",
            )

        usage, record_count = client.get_token_usage_summary()
        self.assertEqual(result, dsl)
        self.assertEqual(usage, ModelTokenUsage(100, 20, 120, 0))
        self.assertEqual(record_count, 1)

    def test_reads_cumulative_usage_from_stream_chunk(self) -> None:
        chunk = {
            "usage": {
                "prompt_tokens": 959,
                "completion_tokens": 526,
                "total_tokens": 1485,
                "completion_tokens_details": {"reasoning_tokens": 21},
            }
        }

        usage = ModelTokenUsage.from_stream_chunk(chunk)

        self.assertEqual(
            usage,
            ModelTokenUsage(
                prompt_tokens=959,
                completion_tokens=526,
                total_tokens=1485,
                reasoning_tokens=21,
            ),
        )

    def test_supports_alternate_usage_keys_and_total_fallback(self) -> None:
        chunk = {
            "usage": {
                "inputToken": 100,
                "outputToken": 40,
                "reasoning_tokens": 12,
            }
        }

        usage = ModelTokenUsage.from_stream_chunk(chunk)

        self.assertEqual(
            usage,
            ModelTokenUsage(
                prompt_tokens=100,
                completion_tokens=40,
                total_tokens=140,
                reasoning_tokens=12,
            ),
        )

    def test_sums_final_usage_once_per_model_request(self) -> None:
        first_request = ModelTokenUsage(100, 20, 120, 5)
        retry_request = ModelTokenUsage(110, 30, 140, 8)

        total = sum_model_token_usage((first_request, retry_request))

        self.assertEqual(total, ModelTokenUsage(210, 50, 260, 13))

    def test_returns_none_when_chunk_has_no_usage(self) -> None:
        self.assertIsNone(ModelTokenUsage.from_stream_chunk({"choices": []}))

    def test_compact_generation_uses_normal_stream_completion(self) -> None:
        source_path = (
            Path(__file__).resolve().parents[1]
            / "cloud"
            / "custom"
            / "a2ui_model_client.py"
        )
        source = source_path.read_text(encoding="utf-8")

        self.assertNotIn("COMPACT_DSL_MAX_TOKENS", source)
        self.assertNotIn("max_duration", source)
        self.assertNotIn("stop_when_compact_complete", source)

    def test_usage_summary_includes_card_and_duration_dimensions(self) -> None:
        source_path = (
            Path(__file__).resolve().parents[1]
            / "cloud"
            / "services"
            / "widget_generation_service.py"
        )
        source = source_path.read_text(encoding="utf-8")

        for field_name in (
            "card_type=",
            "card_size=",
            "generation_status=",
            "model_generation_duration_ms=",
            "input_to_output_duration_ms=",
        ):
            self.assertIn(field_name, source)


if __name__ == "__main__":
    unittest.main()
