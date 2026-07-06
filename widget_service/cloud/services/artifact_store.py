import hashlib
import json
import uuid

from app.logger import logger
from core.config import get_settings
from models.artifact import WidgetArtifact
from models.service import ArtifactSaveResult


class ArtifactStore:
    def save(self, artifact: WidgetArtifact) -> ArtifactSaveResult:
        """保存 artifact 并返回访问地址和摘要。

        入参：
        - artifact：完整卡片产物。
        出参：artifact 保存结果，包含访问 URL 和 sha256 摘要。
        """
        payload = json.dumps(
            artifact.model_dump(mode="json", exclude_none=True),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        digest = "sha256:" + hashlib.sha256(payload).hexdigest()
        logger.info("artifact_payload_built", payload_bytes=len(payload), digest=digest)

        # 待办：替换为团队自己的 OBS 上传方法。上传内容必须是完整产物 JSON，
        # 不能只上传界面描述，返回值应为端侧可下载的产物地址。
        artifact_id = uuid.uuid4().hex
        artifact_url = f"{get_settings().artifact_base_url}/{artifact_id}.json"
        logger.info("artifact_saved_mock", artifact_url=artifact_url)
        return ArtifactSaveResult(artifactUrl=artifact_url, artifactDigest=digest)
