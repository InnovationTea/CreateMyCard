"""导入已有 DSL、截图和 Query，校验后保存为独立批次。

批次有两个用途（``purpose``）：``expect`` 是期望输出基线，``actual`` 是外部产出的真实输出，
两者落盘结构完全相同，只在期望对比里分居左右两侧，因此共用同一份校验与尺寸判定口径。
导入只强制样本 ID 与截图：DSL、CardSpec、Query、尺寸与三类期望项都可留空，
留空时指纹只由显式填写的那几项提供；尺寸缺失或证据不足时按契约缺省值记录来源。

尺寸按协议契约只承认 2x2 与 2x4；导入时若缺失或声明与实际证据冲突，会用
`card_size` 从 DSL（布局名前缀、仅 2x4 可用的组件、root 数值）和截图宽高比判定，
判定结果连同来源一起落盘，供期望对比把尺寸作为指纹之一使用。
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import re
import shutil
import tempfile
import uuid
import warnings
from pathlib import Path
from typing import Any

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, StrictStr, ValidationError, field_validator

from .card_size import judge, normalize
from .runner import atomic_write_json, utc_now

MAX_REQUEST_BYTES = 64 * 1024 * 1024
SOURCE_TYPE = "external-quality"
# 导入批次的用途：期望基线（默认）或外部真实输出。落盘结构相同，只在对比里分侧。
PURPOSE_EXPECT = "expect"
PURPOSE_ACTUAL = "actual"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_RESERVED = {"CON", "PRN", "AUX", "NUL"}
_RESERVED.update(f"COM{i}" for i in range(1, 10))
_RESERVED.update(f"LPT{i}" for i in range(1, 10))


def import_purpose(summary: Any) -> str:
    """导入批次用途；普通批跑运行返回空串，历史批次没有 purpose 字段时按期望处理。"""
    if not isinstance(summary, dict) or summary.get("sourceType") != SOURCE_TYPE:
        return ""
    return PURPOSE_ACTUAL if str(summary.get("purpose") or "") == PURPOSE_ACTUAL else PURPOSE_EXPECT


def generated_sample_id(sample: "ImportSample") -> str:
    """按内容哈希生成唯一 ID，取代人工保证唯一。

    ID 只是标识与管理用的「门牌号」，不参与配对：同内容必得同一个 ID，不同内容不会撞。
    期望与真实输出是不是同一条用例，由数据分类、数据、动作决定（见 expect_compare 的同用例判据）。
    """
    seed = "\x1f".join([
        " ".join(sample.query.split()),
        sample.dsl,
        *(sample.expectedData or []),
        *(sample.expectedActions or []),
        *(sample.expectedIcons or []),
        *(sample.expectedIntents or []),
        hashlib.sha256((sample.imageBase64 or "").encode("utf-8")).hexdigest(),
    ])
    return "H-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


class ImportSample(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: StrictStr = Field(
        default="", max_length=80,
        description="可留空：留空时按内容哈希生成，避免人工命名冲突",
    )
    query: StrictStr = Field(
        default="", max_length=20000,
        description="可以不填：留空时期望对比只按样本 ID 配对",
    )
    size: StrictStr | None = Field(
        default=None, max_length=8,
        description="只允许 2x2 或 2x4；留空由导入判定",
    )
    dsl: StrictStr = Field(
        default="", max_length=2 * 1024 * 1024,
        description="可留空：只导入 ID 与截图时，指纹由显式填写的期望项提供",
    )
    imageBase64: StrictStr | None = Field(
        default=None, max_length=12 * 1024 * 1024,
        description="参考截图，可留空；不参与指纹与筛选",
    )
    cardSpec: dict[str, Any] | None = None
    expectedIntents: list[StrictStr] | None = Field(default=None, max_length=100)
    expectedData: list[StrictStr] | None = Field(default=None, max_length=100)
    expectedActions: list[StrictStr] | None = Field(default=None, max_length=100)
    expectedIcons: list[StrictStr] | None = Field(default=None, max_length=100)
    category: StrictStr | None = Field(
        default=None, max_length=40, description="样本级数据分类，覆盖批次级分类",
    )
    sourceSha256: StrictStr | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    imageSha256: StrictStr | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")

    @field_validator("size")
    @classmethod
    def _validate_size(cls, value: str | None) -> str | None:
        """只接受 2x2／2x4；其它尺寸说明原因后拒绝，缺失则交给导入判定。"""
        if value is None or not value.strip():
            return None
        normalized = normalize(value)
        if not normalized:
            raise ValueError("尺寸只支持 2x2 或 2x4，其它尺寸请按最接近的一种声明")
        return normalized



class ImportBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: StrictStr = Field(min_length=1, max_length=120)
    imageSource: StrictStr = Field(pattern=r"^(web|native|unknown)$")
    purpose: StrictStr = Field(
        default=PURPOSE_EXPECT, pattern=r"^(expect|actual)$",
        description="expect＝期望基线（默认），actual＝外部真实输出，供期望对比右侧使用",
    )
    category: StrictStr | None = Field(
        default=None, max_length=40, description="批次级数据分类：天气、电量、日程等",
    )
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
    except (
        OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning,
    ) as exc:
        raise ValueError("截图损坏或像素过大") from exc
    return raw, extension


def cardspec_user_query(cardspec: Any) -> str:
    """CardSpec 顶层的 ``userQuery`` 是用户原话；DSL 与截图都不带它。

    导入页与批量清单都可能不填 Query（真实输出的清单常常只有 DSL 与截图），
    这里在落盘前从 CardSpec 补齐，保证按 Query 配对时两侧口径一致。
    """
    if not isinstance(cardspec, dict):
        return ""
    value = cardspec.get("userQuery")
    return value.strip() if isinstance(value, str) else ""


def _stage_sample(
    staging: Path,
    sample: ImportSample,
    *,
    purpose: str,
    batch_category: str,
    image_source: str,
    size_notes: list[str],
) -> dict[str, Any]:
    """校验一条样本并写进 staging，返回它的 result 行；新增导入与就地更新共用。"""
    sample_category = (sample.category or "").strip() or batch_category
    # Query 没填就从 CardSpec 的 userQuery 补：两边都留空时才只按样本 ID 配对。
    query = sample.query.strip() or cardspec_user_query(sample.cardSpec)
    # 显式填了 Query 却只剩空白字符属于误填，与「留空按 ID 配对」是两种语义，直接拒绝入库。
    if sample.query and not query:
        raise ValueError("Query 不能只填空白字符；需要按样本 ID 配对请留空")
    image, extension = _image(sample.imageBase64) if sample.imageBase64 else (None, "")
    verdict = judge(sample.size, sample.dsl, image)
    if verdict["warning"]:
        size_notes.append(f"{sample.id}：{verdict['warning']}")
    directory = staging / sample.id / "input"
    directory.mkdir(parents=True)
    source = sample.dsl.encode("utf-8")
    if len(source) > 2 * 1024 * 1024:
        raise ValueError("单条 DSL 不能超过 2 MiB")
    if sample.sourceSha256 and digest(source) != sample.sourceSha256.lower():
        raise ValueError("DSL 与导入清单的 SHA-256 不一致")
    if sample.imageSha256 and (image is None or digest(image) != sample.imageSha256.lower()):
        raise ValueError("截图与导入清单的 SHA-256 不一致")
    (directory / "genui.jsonl").write_bytes(source)
    if image is not None:
        (directory / ("image" + extension)).write_bytes(image)
    metadata = {
        "schemaVersion": "external-quality-input-v1",
        "id": sample.id,
        "purpose": purpose,
        "query": query,
        "size": verdict["size"],
        "sizeSource": verdict["source"],
        "derivedSize": verdict["derived"],
        "declaredSize": verdict["declared"],
        "sizeEvidence": verdict["evidence"],
        "sizeWarning": verdict["warning"],
        "cardSpec": sample.cardSpec or {},
        "expectedIntents": sample.expectedIntents,
        "expectedData": sample.expectedData,
        "expectedActions": sample.expectedActions,
        "expectedIcons": sample.expectedIcons,
        "category": sample_category,
        "imageSource": image_source,
        "pairing": "user-supplied-unverified",
        "sourceSha256": digest(source),
        "imageSha256": digest(image) if image is not None else "",
        "imageFile": ("image" + extension) if image is not None else "",
    }
    atomic_write_json(directory / "input.json", metadata)
    row = {
        "id": sample.id,
        "title": sample.id,
        "purpose": purpose,
        "query": query,
        "size": verdict["size"],
        "sizeSource": verdict["source"],
        "category": sample_category,
        "status": "imported",
        "sourceType": SOURCE_TYPE,
        "inputSha256": digest((directory / "input.json").read_bytes()),
        "attempts": 0,
        "elapsedMs": 0,
    }
    atomic_write_json(staging / sample.id / "result.json", row)
    return row


def import_batch(output_root: Path, payload: Any) -> dict[str, Any]:
    try:
        batch = ImportBatch.model_validate(payload)
    except ValidationError as exc:
        # 不把包含 DSL、图片或 Query 的完整校验输入返回错误日志。
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first.get("loc", []))
        reason = str(first.get("msg", "")).removeprefix("Value error, ")
        raise ValueError(f"导入字段格式错误：{location}：{reason}") from exc
    if not batch.name.strip():
        raise ValueError("批次名称不能为空")
    batch_category = (batch.category or "").strip()
    if batch.category is not None and not batch_category:
        raise ValueError("数据分类不能为空；不需要分类时留空")
    seen: set[str] = set()
    duplicates: list[str] = []
    resolved: list[ImportSample] = []
    for sample in batch.samples:
        provided = sample.id.strip()
        candidate = provided or generated_sample_id(sample)
        if provided and candidate.casefold() in seen:
            # ID 依旧唯一：人工写的重名直接拒绝（不静默改名），留空即由系统生成。
            raise ValueError(
                f"样本 ID 重复（忽略大小写）：{provided}；留空样本 ID 可让系统按内容哈希自动生成"
            )
        if not provided:
            # 自动生成的 ID 撞车只可能来自同批同内容，加后缀保证唯一并留一条提示。
            suffix = 2
            base = candidate
            renamed = False
            while candidate.casefold() in seen:
                candidate = f"{base}-{suffix}"
                suffix += 1
                renamed = True
            if renamed:
                duplicates.append(f"{base} → {candidate}")
        if not _ID.fullmatch(candidate) or candidate.endswith("."):
            raise ValueError("样本 ID 只能使用安全的英文、数字、点、短横线、下划线")
        if candidate.split(".")[0].upper() in _RESERVED:
            raise ValueError("样本 ID 不能是 Windows 保留名")
        seen.add(candidate.casefold())
        resolved.append(sample.model_copy(update={"id": candidate}))
        if sample.category is not None and not sample.category.strip():
            raise ValueError("样本的数据分类不能为空；不需要分类时留空")
        intents = sample.expectedIntents
        if intents is not None and any(not item.strip() for item in intents):
            raise ValueError("显式需求动作名称不能为空")
        for label, items in (
            ("数据", sample.expectedData), ("动作", sample.expectedActions),
        ):
            if items is not None and any(not item.strip() for item in items):
                raise ValueError(f"显式需求{label}名称不能为空")
    root = output_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    run_id = "batch_import_" + uuid.uuid4().hex[:16]
    now = utc_now()
    samples = []
    size_notes: list[str] = []
    size_notes.extend(f"同批重名，已改名：{item}" for item in duplicates)
    # 原子发布：所有输入验证并落盘后才出现在历史列表；失败仅清理本次临时目录。
    with tempfile.TemporaryDirectory(prefix=".quality-import-", dir=root) as temporary:
        staging = Path(temporary) / run_id
        staging.mkdir()
        for sample in resolved:
            samples.append(_stage_sample(
                staging, sample, purpose=batch.purpose,
                batch_category=batch_category, image_source=batch.imageSource,
                size_notes=size_notes,
            ))
        summary = {
            "runId": run_id,
            "name": batch.name,
            "sourceType": SOURCE_TYPE,
            "purpose": batch.purpose,
            "imageSource": batch.imageSource,
            "category": batch_category,
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
            "sizeWarnings": size_notes,
            "samples": samples,
        }
        atomic_write_json(staging / "summary.json", summary)
        atomic_write_json(
            staging / "manifest.json",
            {
                "schemaVersion": "external-quality-import-v1",
                "runId": run_id,
                "sourceType": SOURCE_TYPE,
                "purpose": batch.purpose,
                "generated": False,
                "renderVerified": False,
            },
        )
        staging.rename(root / run_id)
    return summary


def update_sample(
    output_root: Path,
    run_id: str,
    sample_id: str,
    payload: Any,
) -> dict[str, Any]:
    """就地更新一个已导入样本：只覆盖这一条，批次与其余样本都不动。

    同一个 ID 重新整批导入也能覆盖旧版本，但当批次里有多条样本时，整批重导会把
    其他样本一起带进来；发现某一条期望要修正时用这个接口，改动范围就是这一条。
    样本 ID 以路径为准（请求体里的 id 忽略），因此不会因为改名而丢失原位置。
    """
    if not _ID.fullmatch(sample_id) or sample_id.endswith("."):
        raise ValueError("样本 ID 只能使用安全的英文、数字、点、短横线、下划线")
    if sample_id.split(".")[0].upper() in _RESERVED:
        raise ValueError("样本 ID 不能是 Windows 保留名")
    if payload is not None and not isinstance(payload, dict):
        raise ValueError("更新内容必须是 JSON 对象")
    root = output_root.resolve()
    directory = (root / run_id).resolve()
    directory.relative_to(root)
    summary_path = directory / "summary.json"
    if not summary_path.is_file():
        raise KeyError(run_id)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(summary, dict) or summary.get("sourceType") != SOURCE_TYPE:
        raise ValueError("只有导入批次（期望输出或实际输出）可以修改")
    rows = [item for item in summary.get("samples") or [] if isinstance(item, dict)]
    index = next(
        (position for position, item in enumerate(rows)
         if str(item.get("id")) == sample_id),
        None,
    )
    if index is None:
        raise KeyError(sample_id)
    sample_dir = directory / sample_id
    input_dir = sample_dir / "input"
    stored_path = input_dir / "input.json"
    stored = json.loads(stored_path.read_text(encoding="utf-8")) if stored_path.is_file() else {}
    genui_path = input_dir / "genui.jsonl"
    # 只改传了的字段：先铺一层存量，再用请求体覆盖。
    # 因此画廊里只改分类不会把 Query／DSL／期望项清空；要清空就显式传空值。
    merged: dict[str, Any] = {
        "id": sample_id,
        "query": str(stored.get("query") or ""),
        "size": str(stored.get("declaredSize") or "") or None,
        "dsl": genui_path.read_text(encoding="utf-8") if genui_path.is_file() else "",
        "cardSpec": stored.get("cardSpec") or None,
        "expectedData": stored.get("expectedData"),
        "expectedActions": stored.get("expectedActions"),
        "expectedIcons": stored.get("expectedIcons"),
        # 存量里的空分类等价于「未分类」，按 None 处理，否则每次更新都会被空值判为非法。
        "category": stored.get("category") or None,
        **(payload or {}),
        "id": sample_id,
    }
    merged.pop("sourceSha256", None)
    merged.pop("imageSha256", None)
    try:
        sample = ImportSample.model_validate(merged)
    except ValidationError as exc:
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first.get("loc", []))
        reason = str(first.get("msg", "")).removeprefix("Value error, ")
        raise ValueError(f"导入字段格式错误：{location}：{reason}") from exc
    if sample.category is not None and not sample.category.strip():
        raise ValueError("样本的数据分类不能为空；不需要分类时留空")
    for label, items in (
        ("数据", sample.expectedData), ("动作", sample.expectedActions),
        ("图标", sample.expectedIcons),
    ):
        if items is not None and any(not item.strip() for item in items):
            raise ValueError(f"显式需求{label}名称不能为空")
    # 只保留这一条的尺寸提示，避免同一 ID 的旧提示越积越多。
    prefix = f"{sample_id}："
    size_notes = [
        str(note) for note in summary.get("sizeWarnings") or []
        if not str(note).startswith(prefix)
    ]
    # 页面无法把已有截图回填进 file 输入框，因此「不传截图」按保留处理：
    # 其余字段以请求为准（DSL 传空串就是清空），只有截图是继承语义。
    if sample.imageBase64 is None:
        if stored:
            saved = stored
            image_name = str(saved.get("imageFile") or "")
            # 只认导入时自己写下的固定文件名，避免落盘内容被当成路径使用。
            image_path = (
                input_dir / image_name
                if re.fullmatch(r"image\.(png|jpg)", image_name) else None
            )
            if image_path is not None and image_path.is_file():
                sample = sample.model_copy(update={
                    "imageBase64": base64.b64encode(image_path.read_bytes()).decode(),
                })
    fixed = sample.model_copy(update={"id": sample_id})
    with tempfile.TemporaryDirectory(prefix=".quality-update-", dir=root) as temporary:
        staging = Path(temporary)
        row = _stage_sample(
            staging, fixed, purpose=str(summary.get("purpose") or PURPOSE_EXPECT),
            batch_category=str(summary.get("category") or ""),
            image_source=str(summary.get("imageSource") or "unknown"),
            size_notes=size_notes,
        )
        target = directory / sample_id
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        shutil.move(str(staging / sample_id / "input"), str(target / "input"))
        shutil.move(str(staging / sample_id / "result.json"), str(target / "result.json"))
    rows[index] = {**rows[index], **row, "updatedAt": utc_now()}
    summary["samples"] = rows
    summary["sizeWarnings"] = size_notes
    summary["updatedAt"] = utc_now()
    atomic_write_json(summary_path, summary)
    return rows[index]


def update_run_category(output_root: Path, run_id: str, payload: Any) -> dict[str, Any]:
    """整批改数据分类：一次把这一批里所有样本的分类改成同一个值。

    分类是展示与筛选用的标签，不参与指纹，所以整批改只动 ``input.json`` 与 ``summary.json``，
    不重新判定尺寸、不重写 DSL 与截图。``category`` 传 null／空串表示清回「未分类」。
    """
    if not isinstance(payload, dict):
        raise ValueError("更新内容必须是 JSON 对象")
    raw = payload.get("category")
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        category = ""
    elif isinstance(raw, str):
        category = raw.strip()
        if len(category) > 40:
            raise ValueError("数据分类不能超过 40 个字符")
    else:
        raise ValueError("数据分类必须是字符串或 null")
    root = output_root.resolve()
    directory = (root / run_id).resolve()
    directory.relative_to(root)
    summary_path = directory / "summary.json"
    if not summary_path.is_file():
        raise KeyError(run_id)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(summary, dict) or summary.get("sourceType") != SOURCE_TYPE:
        raise ValueError("只有导入批次（期望输出或实际输出）可以修改")
    rows = [item for item in summary.get("samples") or [] if isinstance(item, dict)]
    for row in rows:
        sample_id = str(row.get("id") or "")
        if not _ID.fullmatch(sample_id):
            continue
        row["category"] = category
        meta_path = directory / sample_id / "input" / "input.json"
        if not meta_path.is_file():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["category"] = category
        atomic_write_json(meta_path, meta)
    summary["samples"] = rows
    summary["category"] = category
    summary["updatedAt"] = utc_now()
    atomic_write_json(summary_path, summary)
    return {"runId": run_id, "category": category, "sampleCount": len(rows)}
