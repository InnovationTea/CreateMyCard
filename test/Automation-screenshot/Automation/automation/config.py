from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

# Local test-machine configuration.
# Update this one path if DevEco Studio is installed somewhere else.
LOCAL_DEVECO_STUDIO_HOME = Path("D:/DevEco Studio")
LOCAL_DEVECO_SDK_HOME = LOCAL_DEVECO_STUDIO_HOME / "sdk"
LOCAL_JAVA_HOME = LOCAL_DEVECO_STUDIO_HOME / "jbr"

@dataclass(frozen=True)
class AutomationConfig:
    project_root: Path
    hdc: str = "hdc"
    sn: str | None = None
    remote_dump: str = "/data/local/tmp/current_ui_tree.json"
    remote_snapshot: str = "/data/local/tmp/snapshot_display.jpeg"
    ready_timeout: float = 60
    reply_timeout: float = 120
    extract_delay: float = 30
    post_query_wait: float = 30
    query_attempt_timeout: float = 90
    query_max_attempts: int = 3
    poll_interval: float = 2
    scroll_limit: int = 12
    render_wait: float = 5
    build_timeout: float = 300
    deveco_sdk_home: Path | None = LOCAL_DEVECO_SDK_HOME
    java_home: Path | None = LOCAL_JAVA_HOME
    bundle_name: str = "yyx.test.test"
    ability_name: str = "EntryAbility"
    module_name: str = "entry"
    screenshot_min_bytes: int = 1000
    screenshot_retries: int = 3
    screenshot_write_wait: float = 1
    enable_card_crop: bool = False
    card_crop_config: Path | None = None
    card_crop_debug: bool = False
    debug: bool = False

    @property
    def queries_path(self) -> Path:
        return self.project_root / "queries.jsonl"

    @property
    def dsl_dir(self) -> Path:
        if self.safe_sn:
            return self.project_root / "dsl" / self.safe_sn
        return self.project_root / "dsl"

    @property
    def output_dir(self) -> Path:
        if self.safe_sn:
            return self.project_root / "output" / self.safe_sn
        return self.project_root / "output"

    @property
    def source_arkts_dir(self) -> Path:
        return self.project_root / "ArkTs"

    @property
    def arkts_dir(self) -> Path:
        return self.work_dir / "ArkTs"

    @property
    def rawfile_target(self) -> Path:
        return self.arkts_dir / self.module_name / "src" / "main" / "resources" / "rawfile" / "sample.jsonl"

    @property
    def hap_output_dir(self) -> Path:
        return self.arkts_dir / self.module_name / "build" / "default" / "outputs" / "default"

    @property
    def signed_hap_path(self) -> Path:
        return self.hap_output_dir / f"{self.module_name}-default-signed.hap"

    @property
    def work_dir(self) -> Path:
        base = self.project_root / "Automation" / ".work"
        if self.safe_sn:
            return base / "devices" / self.safe_sn
        return base

    @property
    def safe_sn(self) -> str | None:
        if not self.sn:
            return None
        return safe_path_name(self.sn)

    def artifact_stem(self, qid: str) -> str:
        safe_qid = safe_path_name(qid)
        if self.safe_sn:
            return f"{self.safe_sn}_{safe_qid}"
        return safe_qid

    def dsl_path_for(self, qid: str) -> Path:
        return self.dsl_dir / f"{self.artifact_stem(qid)}.jsonl"

    def screenshot_path_for(self, qid: str) -> Path:
        return self.output_dir / f"{self.artifact_stem(qid)}.jpeg"

    def card_screenshot_path_for(self, qid: str) -> Path:
        return self.output_dir / f"{self.artifact_stem(qid)}_card.png"

    @property
    def card_crop_debug_dir(self) -> Path:
        return self.output_dir / "_debug"

    @property
    def default_card_crop_config_path(self) -> Path:
        return self.project_root / "Automation" / "config" / "card_crop.json"
    
    @property
    def scores_jsonl_path(self) -> Path:
        """审美打分结果jsonl路径"""
        return self.output_dir / "scores.jsonl"
    
    @property
    def report_html_path(self) -> Path:
        """审美可视化报告路径"""
        return self.output_dir / "report.html"

def safe_path_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value)).strip("._")
    return cleaned or "item"
