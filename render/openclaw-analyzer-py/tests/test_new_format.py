from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openclaw_analyzer.log_parser import parse_log_file
from openclaw_analyzer.query_analyzer import ActionKind, analyze_queries


NEW_FORMAT_LOG = """\
{"type":"session","version":3,"id":"test-session","timestamp":"2026-05-24T13:24:00.000Z","cwd":"/tmp/workspace"}
{"type":"message","id":"user1","parentId":"x","timestamp":"2026-05-24T13:24:51.335Z","message":{"role":"user","content":[{"type":"text","text":"帮我查看麦当劳的甜品，并用genui dsl生成"}],"timestamp":1779629091333}}
{"type":"custom_message","customType":"openclaw.runtime-context","content":"Sender metadata here","display":false,"details":{"source":"openclaw-runtime-context"},"id":"ctx1","parentId":"user1","timestamp":"2026-05-24T13:24:51.336Z"}
{"type":"message","id":"asst1","parentId":"ctx1","timestamp":"2026-05-24T13:25:08.753Z","message":{"role":"assistant","content":[{"type":"thinking","thinking":"需要先 read user profile。"},{"type":"toolCall","id":"call_1","name":"read","arguments":{"path":"~/profile.md"}}],"stopReason":"stop","timestamp":1779629091338}}
{"type":"message","id":"tool1","parentId":"asst1","timestamp":"2026-05-24T13:25:10.000Z","message":{"role":"toolResult","toolCallId":"call_1","toolName":"read","content":[{"type":"text","text":"profile content"}],"details":{"status":"completed","durationMs":12},"isError":false,"timestamp":1779629100000}}
{"type":"message","id":"asst2","parentId":"tool1","timestamp":"2026-05-24T13:25:20.000Z","message":{"role":"assistant","content":[{"type":"thinking","thinking":"继续查门店菜单。"},{"type":"toolCall","id":"call_2","name":"exec","arguments":{"command":"curl api"}}],"stopReason":"stop","timestamp":1779629120000}}
{"type":"message","id":"tool2","parentId":"asst2","timestamp":"2026-05-24T13:25:21.000Z","message":{"role":"toolResult","toolCallId":"call_2","toolName":"exec","content":[{"type":"text","text":"desserts json"}],"details":{"status":"completed","durationMs":200},"isError":false,"timestamp":1779629121000}}
{"type":"message","id":"asst3","parentId":"tool2","timestamp":"2026-05-24T13:25:40.000Z","message":{"role":"assistant","content":[{"type":"text","text":"这是甜品 GenUI 输出"}],"stopReason":"stop","timestamp":1779629140000}}
"""

GLUED_JSON_LOG = (
    '{"type":"message","id":"a","parentId":null,"timestamp":"2026-05-24T13:30:00.000Z",'
    '"message":{"role":"user","content":[{"type":"text","text":"hi"}],"timestamp":1}}'
    '{"type":"message","id":"b","parentId":"a","timestamp":"2026-05-24T13:30:01.000Z",'
    '"message":{"role":"assistant","content":[{"type":"text","text":"ok"}],"stopReason":"stop","timestamp":2}}'
)


class NewFormatTests(unittest.TestCase):
    def test_custom_message_parsed(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".jsonl", delete=False) as f:
            f.write(NEW_FORMAT_LOG)
            path = Path(f.name)
        try:
            log = parse_log_file(path)
            ctx = next(e for e in log.events if e.id == "ctx1")
            self.assertEqual(ctx.type, "custom_message")
            self.assertEqual(ctx.text_content, "Sender metadata here")
            self.assertTrue(ctx.hidden_from_ui)
        finally:
            path.unlink(missing_ok=True)

    def test_stop_with_toolcall_does_not_truncate_turn(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".jsonl", delete=False) as f:
            f.write(NEW_FORMAT_LOG)
            path = Path(f.name)
        try:
            queries = analyze_queries(parse_log_file(path))
            self.assertEqual(len(queries), 1)
            q = queries[0]
            self.assertEqual(len(q.steps), 6)
            kinds = [s.kind for s in q.steps]
            self.assertEqual(kinds[0], ActionKind.CUSTOM_MESSAGE)
            self.assertEqual(kinds[-1], ActionKind.ASSISTANT_RESPONSE)
            self.assertEqual(sum(1 for s in q.steps if s.kind == ActionKind.TOOL_RESULT), 2)
        finally:
            path.unlink(missing_ok=True)

    def test_glued_json_objects_recovered(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".jsonl", delete=False) as f:
            f.write('{"type":"session","id":"s","timestamp":"2026-05-24T13:00:00.000Z","cwd":"/tmp"}\n')
            f.write(GLUED_JSON_LOG)
            path = Path(f.name)
        try:
            log = parse_log_file(path)
            self.assertGreaterEqual(log.parse_stats.json_objects, 3)
            self.assertEqual(len([e for e in log.events if e.type == "message"]), 2)
        finally:
            path.unlink(missing_ok=True)

    def test_real_log_q3_has_custom_message_step(self) -> None:
        real_log = Path(__file__).resolve().parents[2] / (
            "1d99e2db-408f-43a8-b156-78184ee51d07.jsonl.reset.2026-05-21T13-22-57.351Z"
        )
        if not real_log.is_file():
            self.skipTest("sample log not found")

        queries = analyze_queries(parse_log_file(real_log))
        q3 = queries[2]
        self.assertEqual(q3.steps[0].kind, ActionKind.CUSTOM_MESSAGE)
        self.assertIn("runtime-context", q3.steps[0].description)

    def test_latency_uses_log_timestamp_not_message_timestamp(self) -> None:
        """message.timestamp on assistant can be backdated; wall-clock ISO must win."""
        log_text = """\
{"type":"session","id":"s","timestamp":"2026-05-21T13:15:31.693Z","cwd":"/tmp"}
{"type":"message","id":"user1","parentId":"x","timestamp":"2026-05-21T13:15:31.693Z","message":{"role":"user","content":[{"type":"text","text":"查优惠券"}],"timestamp":1779369331693}}
{"type":"message","id":"fetch1","parentId":"user1","timestamp":"2026-05-21T13:16:01.685Z","message":{"role":"toolResult","toolCallId":"c1","toolName":"web_fetch","content":[{"type":"text","text":"doc"}],"details":{"tookMs":392},"isError":false,"timestamp":1779369361683}}
{"type":"message","id":"asst1","parentId":"fetch1","timestamp":"2026-05-21T13:16:09.719Z","message":{"role":"assistant","content":[{"type":"text","text":"试试 exec"},{"type":"toolCall","id":"c2","name":"exec","arguments":{"command":"curl"}}],"stopReason":"toolUse","timestamp":1779369361685}}
{"type":"message","id":"exec1","parentId":"asst1","timestamp":"2026-05-21T13:16:09.985Z","message":{"role":"toolResult","toolCallId":"c2","toolName":"exec","content":[{"type":"text","text":"404"}],"details":{"durationMs":257},"isError":false,"timestamp":1779369369983}}
{"type":"message","id":"asst2","parentId":"exec1","timestamp":"2026-05-21T13:16:20.967Z","message":{"role":"assistant","content":[{"type":"text","text":"完成"}],"stopReason":"stop","timestamp":1779369382417}}
"""
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".jsonl", delete=False) as f:
            f.write(log_text)
            path = Path(f.name)
        try:
            log = parse_log_file(path)
            fetch = next(e for e in log.events if e.id == "fetch1")
            asst1 = next(e for e in log.events if e.id == "asst1")
            exec1 = next(e for e in log.events if e.id == "exec1")

            self.assertEqual(fetch.timestamp_ms, parse_iso_from_test("2026-05-21T13:16:01.685Z"))
            self.assertEqual(asst1.timestamp_ms, parse_iso_from_test("2026-05-21T13:16:09.719Z"))
            self.assertEqual(asst1.message_timestamp_ms, 1779369361685)
            self.assertNotEqual(asst1.timestamp_ms, asst1.message_timestamp_ms)

            queries = analyze_queries(log)
            steps = queries[0].steps
            asst_step = next(s for s in steps if s.event_id == "asst1")
            exec_step = next(s for s in steps if s.event_id == "exec1")

            # ~8s LLM inference after web_fetch, not ~2ms
            self.assertGreaterEqual(asst_step.latency_from_prev_ms, 8000)
            self.assertLess(asst_step.latency_from_prev_ms, 8200)

            # tool step ~266ms wall clock, not ~8.3s from backdated assistant timestamp
            self.assertGreaterEqual(exec_step.latency_from_prev_ms, 200)
            self.assertLess(exec_step.latency_from_prev_ms, 400)
            self.assertEqual(exec_step.reported_duration_ms, 257)
            self.assertLess(exec_step.scheduling_overhead_ms, 100)
        finally:
            path.unlink(missing_ok=True)


def parse_iso_from_test(iso: str) -> int:
    from openclaw_analyzer.time_utils import parse_iso_timestamp_ms

    return parse_iso_timestamp_ms(iso)


if __name__ == "__main__":
    unittest.main()
