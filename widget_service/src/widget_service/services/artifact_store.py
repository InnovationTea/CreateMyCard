import hashlib
import json
import uuid

from widget_service.core.config import get_settings
from widget_service.models.artifact import WidgetArtifact


class ArtifactStore:
    def save(self, artifact: WidgetArtifact) -> tuple[str, str]:
        payload = json.dumps(
            artifact.model_dump(mode="json", exclude_none=True),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        digest = "sha256:" + hashlib.sha256(payload).hexdigest()

        # TODO: Replace this method with the team's OBS uploader. The uploader should store
        # the full artifact JSON, not only genui, and return the downloadable artifact URL.
        artifact_id = uuid.uuid4().hex
        return f"{get_settings().artifact_base_url}/{artifact_id}.json", digest
