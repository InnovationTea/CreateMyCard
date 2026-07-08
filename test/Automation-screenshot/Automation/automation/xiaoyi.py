from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from .config import AutomationConfig
from .dsl import DSL_KEYWORDS, DslExtraction, DslExtractor
from .hdc import HdcClient, HdcError
from .logger import get_logger
from .ui_tree import UiTree


@dataclass(frozen=True)
class QueryResult:
    qid: str
    dsl_path: Path
    extraction: DslExtraction


class XiaoyiClient:
    def __init__(self, config: AutomationConfig, hdc: HdcClient, extractor: DslExtractor | None = None):
        self.config = config
        self.hdc = hdc
        self.extractor = extractor or DslExtractor()
        self.dump_path = config.work_dir / "current_ui_tree.json"
        self.last_dsl_fingerprint: str | None = None
        self._log = get_logger("xiaoyi", sn=config.safe_sn or "", log_dir=config.output_dir, debug=config.debug)

    def dump_tree(self) -> UiTree:
        self.hdc.dump_layout(self.dump_path, self.config.remote_dump)
        try:
            return UiTree.from_file(self.dump_path)
        except (OSError, json.JSONDecodeError) as exc:
            raise HdcError(f"Failed to read dumped UI tree: {self.dump_path}") from exc

    def wait_ready(self) -> None:
        deadline = time.monotonic() + self.config.ready_timeout
        while time.monotonic() <= deadline:
            tree = self.dump_tree()
            if tree.is_chat_ready():
                return
            time.sleep(self.config.poll_interval)
        self._log.error("wait_ready timeout after %.0fs", self.config.ready_timeout)
        raise TimeoutError("Timed out waiting for Xiaoyi chat UI to become ready")

    def send_query(self, query: str) -> None:
        input_xy = self._ensure_input()
        self._clear_input(*input_xy)
        self.hdc.ui_input("inputText", *input_xy, query)
        tree = self.dump_tree()
        send = tree.locate_control("send")
        if not send:
            self._log.error("send_query: Send button not found")
            raise RuntimeError("Send button not found after text input")
        self.hdc.ui_input("click", *send.center)

    def collect_dsl_for_query(self, qid: str, query: str) -> QueryResult:
        t0 = time.monotonic()
        last_error: Exception | None = None
        for attempt in range(1, self.config.query_max_attempts + 1):
            try:
                self.wait_ready()
                self.send_query(query)
                deadline = time.monotonic() + self.config.query_attempt_timeout
                time.sleep(min(self.config.post_query_wait, max(0, deadline - time.monotonic())))
                self._scroll_down(check=False)
                extraction = self._wait_and_extract(qid, deadline)
                self.last_dsl_fingerprint = dsl_fingerprint(extraction)
                dsl_path = self.config.dsl_path_for(qid)
                self.extractor.save_jsonl(extraction, dsl_path)
                self._log.info("[%s] stage=DSL_READY dsl=%s elapsed_ms=%d", qid, dsl_path.name, int((time.monotonic() - t0) * 1000))
                return QueryResult(qid=qid, dsl_path=dsl_path, extraction=extraction)
            except (TimeoutError, HdcError) as exc:
                last_error = exc
                self._log.error("[%s] stage=DSL_ATTEMPT_FAILED attempt=%d error=%s", qid, attempt, exc)
                if attempt < self.config.query_max_attempts:
                    continue
        raise TimeoutError(f"DSL not found for query {qid} after {self.config.query_max_attempts} attempts") from last_error

    def _ensure_input(self) -> tuple[int, int]:
        tree = self.dump_tree()
        candidate = tree.locate_control("input")
        if candidate:
            return candidate.center
        toggle = tree.locate_control("keyboard_toggle")
        if not toggle:
            self._log.error("_ensure_input: no input or keyboard toggle found")
            raise RuntimeError("Neither text input nor keyboard toggle was found")
        self.hdc.ui_input("click", *toggle.center)
        tree = self.dump_tree()
        candidate = tree.locate_control("input")
        if not candidate:
            raise RuntimeError("Text input was not found after clicking keyboard toggle")
        return candidate.center

    def _clear_input(self, x: int, y: int) -> None:
        self.hdc.ui_input("click", x, y)
        self.hdc.ui_input("keyEvent", 2072, 2017, check=False)
        self.hdc.ui_input("keyEvent", 2055, check=False)

    def _wait_and_extract(self, qid: str, deadline: float) -> DslExtraction:
        last_len = -1
        stable_count = 0
        latest_tree: UiTree | None = None

        while time.monotonic() <= deadline:
            tree = self.dump_tree()
            latest_tree = tree
            busy, has_dsl, reply_len = tree.reply_state(DSL_KEYWORDS)
            if reply_len == last_len:
                stable_count += 1
            else:
                stable_count = 0
                last_len = reply_len

            if has_dsl and not busy and stable_count >= 1:
                extraction = self.extractor.extract_from_tree(qid, tree)
                if self._is_new_extraction(extraction):
                    return extraction
            time.sleep(self.config.poll_interval)

        if latest_tree is not None:
            extraction = self.extractor.extract_from_tree(qid, latest_tree)
            if self._is_new_extraction(extraction):
                return extraction
        return self._scroll_scan_for_dsl(qid, deadline)

    def _scroll_scan_for_dsl(self, qid: str, deadline: float) -> DslExtraction:
        for _ in range(self.config.scroll_limit):
            if time.monotonic() > deadline:
                break
            self._scroll_down(check=False)
            tree = self.dump_tree()
            extraction = self.extractor.extract_from_tree(qid, tree)
            if self._is_new_extraction(extraction):
                return extraction
        raise TimeoutError(f"DSL not found for query {qid}")

    def _scroll_down(self, check: bool = True) -> None:
        self.hdc.ui_input("swipe", 600, 1800, 600, 500, 600, check=check)

    def _is_new_extraction(self, extraction: DslExtraction) -> bool:
        if not extraction.found:
            return False
        fingerprint = dsl_fingerprint(extraction)
        return fingerprint != self.last_dsl_fingerprint


def dsl_fingerprint(extraction: DslExtraction) -> str:
    return json.dumps(extraction.records, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

