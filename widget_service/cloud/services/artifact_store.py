# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json
import os
from dataclasses import dataclass
from typing import Any

from anyio import to_thread

from app.logger import logger
from config.config import get_settings
from models.artifact import WidgetArtifact
from models.service import ArtifactSaveResult
from services.source_artifact_repository import calculate_artifact_digest
from utils.file import save_txt_file
from utils.upload_file_obs import UploadFileOSMS

_MODULE = "[Artifact Store]"

file_obs = UploadFileOSMS()


@dataclass(frozen=True)
class RepairArtifactRecord:
    """记录一次模型 repair 及其确定性转换、校验结果。"""

    model_generated_compact_dsl: str
    generated_dsl: str
    validation_errors: tuple[dict[str, str], ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "modelGeneratedCompactDsl": self.model_generated_compact_dsl,
            "generatedDsl": self.generated_dsl,
            "validationErrors": list(self.validation_errors),
        }


class ArtifactStore:
    def __init__(
        self,
        design_token: str | None = None,
        request_body: str | dict[str, Any] | None = None,
        repair_records: list[RepairArtifactRecord] | None = None,
    ) -> None:
        """接收第四、第五接口最终模型源输出，两个接口沿用同一 artifact 块名。"""
        self.design_token = design_token
        self.request_body = {} if request_body is None else request_body
        self.repair_records = list(repair_records or [])

    async def save(self, artifact: WidgetArtifact) -> ArtifactSaveResult:
        """保存 artifact 并返回访问地址和摘要。

        入参：
        - artifact：完整卡片产物。
        出参：artifact 保存结果，包含访问 URL 和 sha256 摘要。
        """
        artifact_data = artifact.model_dump(mode="json", exclude_none=True)
        payload_bytes = len(
            json.dumps(
                artifact_data,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        digest = calculate_artifact_digest(artifact)
        logger.info(
            f"{_MODULE} artifact_payload_built "
            f"payload_bytes={payload_bytes} digest={digest}"
        )

        # Artifact 以具名 Markdown 代码块上传。每个块名与对应契约字段一致，
        # 既保留端侧现有的 genui/cardspec 解析方式，也完整携带排障和回放信息。
        json_blocks = {
            "cardspec": artifact_data["cardSpec"],
            "schema": {"schemaVersion": artifact_data["schemaVersion"]},
            "taskspec": artifact_data["taskSpec"],
            "effectivecapabilities": artifact_data["effectiveCapabilities"],
            "removedcapabilities": artifact_data["removedCapabilities"],
            "generationplan": artifact_data["generationPlan"],
            "meta": artifact_data["meta"],
        }
        blocks = [
            "```cardspec\n"
            + json.dumps(json_blocks["cardspec"], ensure_ascii=False, indent=2)
            + "\n```",
            f"```genui\n{artifact.genui}\n```",
        ]
        blocks.extend(
            "```" + name + "\n"
            + json.dumps(value, ensure_ascii=False, indent=2)
            + "\n```"
            for name, value in json_blocks.items()
            if name != "cardspec"
        )
        if self.design_token is not None:
            blocks.append(f"```designcompactdsl\n{self.design_token}\n```")
        request_block_body = self._request_block_body()
        request_block_separator = "" if request_block_body.endswith("\n") else "\n"
        blocks.append(
            f"```request\n{request_block_body}{request_block_separator}```"
        )
        blocks.extend(
            f"```repair-{index}\n"
            + json.dumps(record.to_payload(), ensure_ascii=False, indent=2)
            + "\n```"
            for index, record in enumerate(self.repair_records, start=1)
        )
        file_content = "\n".join(blocks) + "\n"

        # UUID 同时进入 meta 和对象名，避免毫秒时间戳在并发生成时发生覆盖。
        file_name = f"artifact_{artifact.meta.artifactId}.md"
        file_path = os.path.join(str(get_settings().WORKSPACE_ROOT), file_name)
        await to_thread.run_sync(save_txt_file, file_path, file_content)
        logger.info(f"{_MODULE} artifact_file_saved path={file_path}")

        # 上传只产生远端或 mock OBS 副本，本地 artifact 暂时保留在 workspace，
        # 便于排障和人工核对；后续如需清理应由独立生命周期策略处理。
        artifact_url = await file_obs.upload_file(file_path)
        if not artifact_url:
            raise RuntimeError("artifact upload to OBS failed")
        logger.info(
            f"{_MODULE} artifact_uploaded artifact_url={artifact_url} "
            f"local_file_retained={file_path}"
        )
        return ArtifactSaveResult(artifactUrl=artifact_url, artifactDigest=digest)

    def _request_block_body(self) -> str:
        """WebSocket 请求保留原文，本地直调请求按 JSON 输出。"""
        if isinstance(self.request_body, str):
            return self.request_body
        return json.dumps(self.request_body, ensure_ascii=False, indent=2)
