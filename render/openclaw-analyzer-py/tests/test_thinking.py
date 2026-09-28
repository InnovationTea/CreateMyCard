from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from openclaw_analyzer.log_parser import parse_log_file
from openclaw_analyzer.query_analyzer import analyze_queries


SAMPLE_LOG = """\
{"type":"session","version":3,"id":"test-session","timestamp":"2026-05-21T13:15:00.000Z","cwd":"/tmp/workspace"}
{"type":"message","id":"user1","parentId":null,"timestamp":"2026-05-21T13:15:31.693Z","message":{"role":"user","content":[{"type":"text","text":"[Thu 2026-05-21 21:15 GMT+8] 测试 query"}],"timestamp":1779369331690}}
{"type":"message","id":"asst1","parentId":"user1","timestamp":"2026-05-21T13:15:35.479Z","message":{"role":"assistant","content":[{"type":"thinking","thinking":"先在内部推理：用户要测试，应调用 read 工具。"},{"type":"text","text":"好的，我来读取文件。"},{"type":"toolCall","id":"call_1","name":"read","arguments":{"path":"/tmp/a.txt"}}],"stopReason":"toolUse","timestamp":1779369331694}}
{"type":"message","id":"tool1","parentId":"asst1","timestamp":"2026-05-21T13:15:35.496Z","message":{"role":"toolResult","toolCallId":"call_1","toolName":"read","content":[{"type":"text","text":"file body"}],"details":{"status":"completed","durationMs":10},"isError":false,"timestamp":1779369335493}}
{"type":"message","id":"asst2","parentId":"tool1","timestamp":"2026-05-21T13:15:40.000Z","message":{"role":"assistant","content":[{"type":"thinking","thinking":"工具返回成功，可以给出最终答复。"},{"type":"text","text":"已完成读取。"}],"stopReason":"stop","timestamp":1779369340000}}
{"type":"message","id":"user2","parentId":"asst2","timestamp":"2026-05-21T13:16:00.000Z","message":{"role":"user","content":[{"type":"text","text":"[Thu 2026-05-21 21:16 GMT+8] 仅思考后执行"}],"timestamp":1779369360000}}
{"type":"message","id":"asst3","parentId":"user2","timestamp":"2026-05-21T13:16:05.000Z","message":{"role":"assistant","content":[{"type":"thinking","thinking":"用户要求直接执行，无需对外 text，只调用 exec。"},{"type":"toolCall","id":"call_2","name":"exec","arguments":{"command":"echo hi"}}],"stopReason":"toolUse","timestamp":1779369365000}}
{"type":"message","id":"tool2","parentId":"asst3","timestamp":"2026-05-21T13:16:05.010Z","message":{"role":"toolResult","toolCallId":"call_2","toolName":"exec","content":[{"type":"text","text":"hi\\n"}],"details":{"status":"completed","durationMs":5},"isError":false,"timestamp":1779369365010}}
{"type":"message","id":"asst4","parentId":"tool2","timestamp":"2026-05-21T13:16:10.000Z","message":{"role":"assistant","content":[{"type":"text","text":"执行完毕。"}],"stopReason":"stop","timestamp":1779369370000}}
"""


class ThinkingContentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".jsonl", delete=False)
        self.temp.write(SAMPLE_LOG)
        self.temp.close()
        self.log_path = Path(self.temp.name)

    def tearDown(self) -> None:
        self.log_path.unlink(missing_ok=True)

    def test_parse_thinking_and_text_separately(self) -> None:
        log = parse_log_file(self.log_path)
        assistant = next(e for e in log.events if e.id == "asst1")
        self.assertEqual(assistant.thinking_content, "先在内部推理：用户要测试，应调用 read 工具。")
        self.assertEqual(assistant.text_content, "好的，我来读取文件。")

    def test_thinking_only_assistant_step(self) -> None:
        log = parse_log_file(self.log_path)
        assistant = next(e for e in log.events if e.id == "asst3")
        self.assertEqual(assistant.text_content, "")
        self.assertIn("只调用 exec", assistant.thinking_content)

    def test_analyze_queries_includes_thinking_in_steps(self) -> None:
        log = parse_log_file(self.log_path)
        queries = analyze_queries(log)
        self.assertEqual(len(queries), 2)

        q1_first_llm = queries[0].steps[0]
        self.assertIn("先在内部推理", q1_first_llm.thinking_content)
        self.assertEqual(q1_first_llm.full_content, "好的，我来读取文件。")

        q2_first_llm = queries[1].steps[0]
        self.assertIn("[思考链]", q2_first_llm.description)
        self.assertIn("只调用 exec", q2_first_llm.thinking_content)
        self.assertEqual(q2_first_llm.full_content, "")

    def test_real_log_file_has_thinking_entries(self) -> None:
        real_log = Path(__file__).resolve().parents[2] / (
            "1d99e2db-408f-43a8-b156-78184ee51d07.jsonl.reset.2026-05-21T13-22-57.351Z"
        )
        if not real_log.is_file():
            self.skipTest("sample log not found")

        log = parse_log_file(real_log)
        thinking_events = [e for e in log.events if e.thinking_content]
        self.assertGreaterEqual(len(thinking_events), 2)

        queries = analyze_queries(log)
        thinking_steps = [s for q in queries for s in q.steps if s.thinking_content]
        self.assertGreaterEqual(len(thinking_steps), 2)
        self.assertTrue(any("mcd-ordering" in s.thinking_content for s in thinking_steps))


if __name__ == "__main__":
    unittest.main()
