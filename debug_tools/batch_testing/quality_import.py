"""导入已有 DSL、截图和 Query，校验后保存为独立批次。"""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import re
import tempfile
import uuid
import warnings
from pathlib import Path
from typing import Any

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, StrictStr, ValidationError

from .runner import atomic_write_json, utc_now

MAX_REQUEST_BYTES = 64 * 1024 * 1024
SOURCE_TYPE = "external-quality"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_RESERVED = {"CON", "PRN", "AUX", "NUL"}
_RESERVED.update(f"COM{i}" for i in range(1, 10))
_RESERVED.update(f"LPT{i}" for i in range(1, 10))


class ImportSample(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: StrictStr = Field(min_length=1, max_length=80)
    query: StrictStr = Field(min_length=1, max_length=20000)
    size: StrictStr = Field(pattern=r"^(2x2|2x4|4x4)$")
    dsl: StrictStr = Field(min_length=1, max_length=2 * 1024 * 1024)
    imageBase64: StrictStr = Field(min_length=1, max_length=12 * 1024 * 1024)
    cardSpec: dict[str, Any] | None = None
    expectedIntents: list[StrictStr] | None = Field(default=None, max_length=100)
    sourceSha256: StrictStr | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    imageSha256: StrictStr | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")


class ImportBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: StrictStr = Field(min_length=1, max_length=120)
    imageSource: StrictStr = Field(pattern=r"^(web|native|unknown)$")
    samples: list[ImportSample] = Field(min_length=1, max_length=500)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _image(data: str) -> tuple[bytes, str]:
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("截图不是有效 Base64") from exc
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("单张图片不能超过 8 MiB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as picture:
                if picture.format not in {"PNG", "JPEG"}:
                    raise ValueError("只支持 PNG/JPEG 截图")
                if picture.width * picture.height > 16000000:
                    raise ValueError("截图像素不能超过 1600 万")
                extension = ".png" if picture.format == "PNG" else ".jpg"
                picture.verify()
    except (OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("截图损坏或像素过大") from exc
    return raw, extension


def import_batch(output_root: Path, payload: Any) -> dict[str, Any]:
    try:
        batch = ImportBatch.model_validate(payload)
    except ValidationError as exc:
        # 不把包含 DSL、图片或 Query 的完整校验输入返回错误日志。
        location = ".".join(str(part) for part in exc.errors()[0].get("loc", []))
        raise ValueError(f"导入字段格式错误：{location}") from exc
    if not batch.name.strip():
        raise ValueError("批次名称不能为空")
    seen: set[str] = set()
    for sample in batch.samples:
        if not _ID.fullmatch(sample.id) or sample.id.endswith("."):
            raise ValueError("样本 ID 只能使用安全的英文、数字、点、短横线、下划线")
        if sample.id.split(".")[0].upper() in _RESERVED:
            raise ValueError("样本 ID 不能是 Windows 保留名")
        if sample.id.casefold() in seen:
            raise ValueError("样本 ID 重复（忽略大小写）；不同批次请保留独立身份")
        seen.add(sample.id.casefold())
        if not sample.query.strip() or not sample.dsl.strip():
            raise ValueError("Query 和 DSL 不能为空")
        intents = sample.expectedIntents
        if intents is not None and any(not item.strip() for item in intents):
            raise ValueError("显式需求动作名称不能为空")
    root = output_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    run_id = "batch_import_" + uuid.uuid4().hex[:16]
    now = utc_now()
    samples = []
    # 原子发布：所有输入验证并落盘后才出现在历史列表；失败仅清理本次临时目录。
    with tempfile.TemporaryDirectory(prefix=".quality-import-", dir=root) as temporary:
        staging = Path(temporary) / run_id
        staging.mkdir()
        for sample in batch.samples:
            image, extension = _image(sample.imageBase64)
            directory = staging / sample.id / "input"
            directory.mkdir(parents=True)
            source = sample.dsl.encode("utf-8")
            if len(source) > 2 * 1024 * 1024:
                raise ValueError("单条 DSL 不能超过 2 MiB")
            if sample.sourceSha256 and digest(source) != sample.sourceSha256.lower():
                raise ValueError("DSL 与导入清单的 SHA-256 不一致")
            if sample.imageSha256 and digest(image) != sample.imageSha256.lower():
                raise ValueError("截图与导入清单的 SHA-256 不一致")
            (directory / "genui.jsonl").write_bytes(source)
            (directory / ("image" + extension)).write_bytes(image)
            metadata = {
                "schemaVersion": "external-quality-input-v1",
                "id": sample.id,
                "query": sample.query,
                "size": sample.size,
                "cardSpec": sample.cardSpec or {},
                "expectedIntents": sample.expectedIntents,
                "imageSource": batch.imageSource,
                "pairing": "user-supplied-unverified",
                "sourceSha256": digest(source),
                "imageSha256": digest(image),
                "imageFile": "image" + extension,
            }
            atomic_write_json(directory / "input.json", metadata)
            row = {
                "id": sample.id,
                "title": sample.id,
                "query": sample.query,
                "size": sample.size,
                "status": "imported",
                "sourceType": SOURCE_TYPE,
                "inputSha256": digest((directory / "input.json").read_bytes()),
                "attempts": 0,
                "elapsedMs": 0,
            }
            atomic_write_json(staging / sample.id / "result.json", row)
            samples.append(row)
        summary = {
            "runId": run_id,
            "name": batch.name,
            "sourceType": SOURCE_TYPE,
            "imageSource": batch.imageSource,
            "status": "completed",
            "startedAt": now,
            "finishedAt": now,
            "total": len(samples),
            "completed": len(samples),
            "success": 0,
            "failed": 0,
            "degraded": 0,
            "cancelled": 0,
            "imported": len(samples),
            "samples": samples,
        }
        atomic_write_json(staging / "summary.json", summary)
        atomic_write_json(
            staging / "manifest.json",
            {
                "schemaVersion": "external-quality-import-v1",
                "runId": run_id,
                "sourceType": SOURCE_TYPE,
                "generated": False,
                "renderVerified": False,
            },
        )
        staging.rename(root / run_id)
    return summary
